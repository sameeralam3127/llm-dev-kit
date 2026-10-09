import contextlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from devkit_common.config import Settings, get_settings
from devkit_common.http import install_service
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.plugins import EMBEDDER, LLM, PluginKind, PluginNotFoundError, PluginRegistry
from ldk_core.ports import ChatMessage, CompletionRequest, Embedder, LLMProvider
from llm_service.providers.router import CLOUD_PROVIDERS, LOCAL_PROVIDER, split_model

settings = get_settings()


def build_registry(settings: Settings) -> tuple[PluginRegistry, dict[str, bool]]:
    """Discover installed plugins and configure them from the environment.

    Returns the registry and, per cloud provider, whether a server-side key
    is configured (shown by /health and /providers). A first-party plugin
    that is missing fails startup here, not on the first request.
    """
    registry = PluginRegistry()
    registry.load_entry_points()
    timeout = settings.request_timeout_seconds

    registry.configure(
        PluginKind.LLM, LOCAL_PROVIDER, {"host": settings.ollama_host, "timeout_seconds": timeout}
    )
    embedder_config: dict[str, Any] = {
        "host": settings.ollama_host,
        "model": settings.default_embedding_model,
        "timeout_seconds": timeout,
    }
    if settings.embedding_dimension is not None:
        embedder_config["dimension"] = settings.embedding_dimension
    registry.configure(PluginKind.EMBEDDER, LOCAL_PROVIDER, embedder_config)

    cloud = {
        "openai": (settings.openai_api_key, settings.openai_base_url),
        "gemini": (settings.gemini_api_key, None),
        "anthropic": (settings.anthropic_api_key, None),
    }
    for name, (api_key, base_url) in cloud.items():
        config = {"api_key": api_key, "base_url": base_url, "timeout_seconds": timeout}
        registry.configure(PluginKind.LLM, name, config)
    configured = {name: bool(api_key) for name, (api_key, _) in cloud.items()}
    return registry, configured


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    registry, configured = build_registry(settings)
    app.state.registry = registry
    app.state.cloud_configured = configured
    # Fail at startup if the embedder cannot be built (unknown dimension).
    registry.get(EMBEDDER, LOCAL_PROVIDER)
    yield
    await registry.aclose()


app = FastAPI(title=f"{settings.app_name} — LLM Service", version="0.3.0", lifespan=lifespan)
install_service(app, service="llm-service", settings=settings)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str | None = None
    api_key: str | None = None
    options: dict[str, Any] = {}


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    model: str | None = None


def _registry(request: Request) -> PluginRegistry:
    registry: PluginRegistry = request.app.state.registry
    return registry


def _cloud_providers(request: Request) -> list[str]:
    """Enabled cloud providers: the original three in their usual order, then
    any other LLM plugin alphabetically."""
    names = [name for name in _registry(request).names(LLM) if name != LOCAL_PROVIDER]
    known = [name for name in CLOUD_PROVIDERS if name in names]
    return known + [name for name in names if name not in CLOUD_PROVIDERS]


def _route(request: Request, model: str) -> tuple[str, str, LLMProvider]:
    provider_name, model_name = split_model(model, _cloud_providers(request))
    try:
        provider = _registry(request).get(LLM, provider_name)
    except PluginNotFoundError as exc:
        raise ServiceError(
            ErrorCode.INVALID_REQUEST, f"Unknown provider '{provider_name}'"
        ) from exc
    return provider_name, model_name, provider


def _completion(req: GenerateRequest, provider_name: str, model_name: str) -> CompletionRequest:
    return CompletionRequest(
        model=model_name,
        messages=[ChatMessage("user", req.prompt)],
        # The local provider never needs a key; don't hand it one.
        api_key=None if provider_name == LOCAL_PROVIDER else req.api_key,
        extra=req.options,
    )


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    offline_ready = True
    try:
        await _registry(request).get(LLM, LOCAL_PROVIDER).list_models()
    except ServiceError:
        offline_ready = False
    configured: dict[str, bool] = request.app.state.cloud_configured
    return {
        "status": "ok" if offline_ready else "degraded",
        "offline_ready": offline_ready,
        "cloud_providers": {
            name: configured.get(name, False) for name in _cloud_providers(request)
        },
    }


@app.get("/providers")
async def providers(request: Request) -> list[dict[str, Any]]:
    configured: dict[str, bool] = request.app.state.cloud_configured
    entries: list[dict[str, Any]] = [
        {"name": LOCAL_PROVIDER, "type": "offline", "configured": True, "prefix": ""}
    ]
    entries.extend(
        {
            "name": name,
            "type": "cloud",
            "configured": configured.get(name, False),
            "prefix": f"{name}/",
        }
        for name in _cloud_providers(request)
    )
    return entries


@app.get("/models")
async def models(request: Request) -> dict[str, list[str]]:
    """Local models come from Ollama live; cloud models are curated LiteLLM
    lists (always shown — users can bring their own key per request)."""
    registry = _registry(request)
    available: list[str] = []
    with contextlib.suppress(ServiceError):
        available.extend(await registry.get(LLM, LOCAL_PROVIDER).list_models())
    for name in _cloud_providers(request):
        available.extend(f"{name}/{m}" for m in await registry.get(LLM, name).list_models())
    return {"models": available}


@app.post("/generate")
async def generate(req: GenerateRequest, request: Request) -> dict[str, Any]:
    model = req.model or settings.default_chat_model
    provider_name, model_name, provider = _route(request, model)
    text = await provider.complete(_completion(req, provider_name, model_name))
    return {"response": text, "model": model, "provider": provider_name}


@app.post("/generate/stream")
async def generate_stream(req: GenerateRequest, request: Request) -> StreamingResponse:
    model = req.model or settings.default_chat_model
    provider_name, model_name, provider = _route(request, model)

    async def event_gen() -> AsyncIterator[str]:
        try:
            async for chunk in provider.stream(_completion(req, provider_name, model_name)):
                yield json.dumps({"delta": chunk}) + "\n"
            yield json.dumps({"done": True, "model": model, "provider": provider_name}) + "\n"
        except ServiceError as exc:
            yield json.dumps({"error": exc.message}) + "\n"

    return StreamingResponse(event_gen(), media_type="application/x-ndjson")


@app.post("/embed")
async def embed(req: EmbedRequest, request: Request) -> dict[str, Any]:
    embedder: Embedder = _registry(request).get(EMBEDDER, LOCAL_PROVIDER)
    if req.model and req.model != embedder.model:
        # Vectors from another model would not be comparable with the index.
        raise ServiceError(
            ErrorCode.INVALID_REQUEST,
            f"This deployment embeds with '{embedder.model}'; "
            "set DEFAULT_EMBEDDING_MODEL to change it",
        )
    embeddings = await embedder.embed(req.texts)
    return {"embeddings": embeddings, "model": embedder.model, "dimension": len(embeddings[0])}
