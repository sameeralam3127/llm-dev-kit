import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from devkit_common.config import get_settings
from llm_service.providers.anthropic import AnthropicProvider
from llm_service.providers.base import ProviderError
from llm_service.providers.ollama import OllamaProvider
from llm_service.providers.openai_compat import OpenAICompatProvider
from llm_service.providers.router import split_model

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    app.state.http = client
    app.state.providers = {
        "ollama": OllamaProvider(settings.ollama_host, client),
        "openai": OpenAICompatProvider(
            "openai", settings.openai_base_url, settings.openai_api_key, client
        ),
        "anthropic": AnthropicProvider(
            settings.anthropic_base_url, settings.anthropic_api_key, client
        ),
    }
    yield
    await client.aclose()


app = FastAPI(title=f"{settings.app_name} — LLM Service", version="0.2.0", lifespan=lifespan)


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
            "openai": request.app.state.providers["openai"].configured,
            "anthropic": request.app.state.providers["anthropic"].configured,
        },
    }


@app.get("/providers")
async def providers(request: Request) -> list[dict]:
    return [
        {"name": "ollama", "type": "offline", "configured": True, "prefix": ""},
        {
            "name": "openai",
            "type": "cloud",
            "configured": request.app.state.providers["openai"].configured,
            "prefix": "openai/",
        },
        {
            "name": "anthropic",
            "type": "cloud",
            "configured": request.app.state.providers["anthropic"].configured,
            "prefix": "anthropic/",
        },
    ]


@app.get("/models")
async def models(request: Request) -> dict:
    available: list[str] = []
    try:
        available.extend(await _provider(request, "ollama").list_models())
    except ProviderError:
        pass
    for name in ("openai", "anthropic"):
        provider = request.app.state.providers[name]
        if not provider.configured:
            continue
        try:
            available.extend(f"{name}/{m}" for m in await provider.list_models())
        except ProviderError:
            pass
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
                async for chunk in provider.generate_stream(
                    model_name, req.prompt, req.options
                ):
                    yield json.dumps({"delta": chunk}) + "\n"
            else:
                text = await provider.generate(
                    model_name, req.prompt, req.options, api_key=req.api_key
                )
                yield json.dumps({"delta": text}) + "\n"
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
