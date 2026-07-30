import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from devkit_common.config import get_settings
from llm_service.providers.base import ProviderError
from llm_service.providers.litellm_provider import LiteLLMProvider
from llm_service.providers.ollama import OllamaProvider
from llm_service.providers.router import CLOUD_PROVIDERS, split_model

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    app.state.http = client
    timeout = settings.request_timeout_seconds
    app.state.providers = {
        "ollama": OllamaProvider(settings.ollama_host, client),
        "openai": LiteLLMProvider(
            "openai",
            settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=timeout,
        ),
        "gemini": LiteLLMProvider("gemini", settings.gemini_api_key, timeout=timeout),
        "anthropic": LiteLLMProvider(
            "anthropic", settings.anthropic_api_key, timeout=timeout
        ),
    }
    yield
    await client.aclose()


app = FastAPI(title=f"{settings.app_name} — LLM Service", version="0.3.0", lifespan=lifespan)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str | None = None
    api_key: str | None = None
    options: dict = {}


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    model: str | None = None


def _provider(request: Request, name: str):
    provider = request.app.state.providers.get(name)
    if provider is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{name}'")
    return provider


@app.get("/health")
async def health(request: Request) -> dict:
    offline_ready = True
    try:
        await _provider(request, "ollama").list_models()
    except ProviderError:
        offline_ready = False
    return {
        "status": "ok" if offline_ready else "degraded",
        "offline_ready": offline_ready,
        "cloud_providers": {
            name: request.app.state.providers[name].configured
            for name in CLOUD_PROVIDERS
        },
    }


@app.get("/providers")
async def providers(request: Request) -> list[dict]:
    entries = [{"name": "ollama", "type": "offline", "configured": True, "prefix": ""}]
    entries.extend(
        {
            "name": name,
            "type": "cloud",
            "configured": request.app.state.providers[name].configured,
            "prefix": f"{name}/",
        }
        for name in CLOUD_PROVIDERS
    )
    return entries


@app.get("/models")
async def models(request: Request) -> dict:
    """Local models come from Ollama live; cloud models are curated LiteLLM
    lists (always shown — users can bring their own key per request)."""
    available: list[str] = []
    try:
        available.extend(await _provider(request, "ollama").list_models())
    except ProviderError:
        pass
    for name in CLOUD_PROVIDERS:
        provider = request.app.state.providers[name]
        available.extend(f"{name}/{m}" for m in provider.list_models())
    return {"models": available}


@app.post("/generate")
async def generate(req: GenerateRequest, request: Request) -> dict:
    model = req.model or settings.default_chat_model
    provider_name, model_name = split_model(model)
    provider = _provider(request, provider_name)
    try:
        if provider_name == "ollama":
            text = await provider.generate(model_name, req.prompt, req.options)
        else:
            text = await provider.generate(
                model_name, req.prompt, req.options, api_key=req.api_key
            )
    except ProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"response": text, "model": model, "provider": provider_name}


@app.post("/generate/stream")
async def generate_stream(req: GenerateRequest, request: Request) -> StreamingResponse:
    model = req.model or settings.default_chat_model
    provider_name, model_name = split_model(model)
    provider = _provider(request, provider_name)

    async def event_gen():
        try:
            if provider_name == "ollama":
                stream = provider.generate_stream(model_name, req.prompt, req.options)
            else:
                stream = provider.generate_stream(
                    model_name, req.prompt, req.options, api_key=req.api_key
                )
            async for chunk in stream:
                yield json.dumps({"delta": chunk}) + "\n"
            yield json.dumps(
                {"done": True, "model": model, "provider": provider_name}
            ) + "\n"
        except ProviderError as exc:
            yield json.dumps({"error": str(exc)}) + "\n"

    return StreamingResponse(event_gen(), media_type="application/x-ndjson")


@app.post("/embed")
async def embed(req: EmbedRequest, request: Request) -> dict:
    model = req.model or settings.default_embedding_model
    try:
        embeddings = await _provider(request, "ollama").embed(req.texts, model)
    except ProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"embeddings": embeddings, "model": model, "dimension": len(embeddings[0])}
