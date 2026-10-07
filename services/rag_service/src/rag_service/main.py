import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import StreamingResponse

from devkit_common.config import Settings, get_settings
from devkit_common.http import install_service
from devkit_common.models import ChatRequest, ChatResponse, IngestResponse
from ldk_core.errors import ServiceError, bad_request
from ldk_core.plugins import CHUNKER, LOADER, VECTOR_STORE, PluginKind, PluginRegistry
from ldk_core.ports import ChunkRecord, VectorStore
from rag_service.cache import ChatCache
from rag_service.chat import answer_query, stream_answer
from rag_service.llm_client import LLMServiceClient
from rag_service.openai_api import router as openai_router
from rag_service.retrieval import LEGACY_COLLECTION, Retriever

settings = get_settings()

# Which plugin fills each port. Fixed for now; Phase 5 makes them selectable.
VECTOR_STORE_PLUGIN = "chroma"
LOADER_PLUGIN = "pdf"
CHUNKER_PLUGIN = "fixed"


def build_registry(settings: Settings) -> PluginRegistry:
    """Discover installed plugins and configure the ones rag-service uses."""
    registry = PluginRegistry()
    registry.load_entry_points()
    registry.configure(
        PluginKind.VECTOR_STORE,
        VECTOR_STORE_PLUGIN,
        {"host": settings.chroma_host, "port": settings.chroma_port},
    )
    registry.configure(PluginKind.LOADER, LOADER_PLUGIN, {})
    registry.configure(PluginKind.CHUNKER, CHUNKER_PLUGIN, {"size": 500, "overlap": 50})
    return registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    registry = build_registry(settings)
    app.state.settings = settings
    app.state.registry = registry
    app.state.llm = LLMServiceClient(settings.llm_service_url, settings.request_timeout_seconds)
    app.state.cache = ChatCache(settings.redis_url, settings.cache_ttl)
    app.state.retriever = Retriever(store=registry.get(VECTOR_STORE, VECTOR_STORE_PLUGIN))
    yield
    await app.state.llm.close()
    await app.state.cache.close()
    await registry.aclose()


app = FastAPI(title=f"{settings.app_name} — RAG Service", version="0.2.0", lifespan=lifespan)
install_service(app, service="rag-service", settings=settings)
app.include_router(openai_router)


def _store(request: Request) -> VectorStore:
    registry: PluginRegistry = request.app.state.registry
    return registry.get(VECTOR_STORE, VECTOR_STORE_PLUGIN)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "rag-service"}


@app.get("/models")
async def models(request: Request) -> list[str]:
    result: list[str] = await request.app.state.llm.models()
    return result


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    return await answer_query(
        body.message,
        body.model or settings.default_chat_model,
        llm=request.app.state.llm,
        cache=request.app.state.cache,
        retriever=request.app.state.retriever,
        api_key=body.api_key,
    )


@app.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    return StreamingResponse(
        stream_answer(
            body.message,
            body.model or settings.default_chat_model,
            llm=request.app.state.llm,
            cache=request.app.state.cache,
            retriever=request.app.state.retriever,
            api_key=body.api_key,
        ),
        media_type="application/x-ndjson",
    )


@app.post("/ingest/pdf", response_model=IngestResponse)
async def ingest_pdf(request: Request, file: UploadFile = File(...)) -> IngestResponse:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise bad_request("Only PDF uploads are supported")

    registry: PluginRegistry = request.app.state.registry
    loader = registry.get(LOADER, LOADER_PLUGIN)
    chunker = registry.get(CHUNKER, CHUNKER_PLUGIN)

    data = await file.read()
    document = await asyncio.to_thread(loader.load, data, filename=file.filename)
    chunks = await asyncio.to_thread(chunker.chunk, document)

    embeddings = await request.app.state.llm.embed_many([c.text for c in chunks])
    document_id = uuid4().hex
    metadata = {"filename": file.filename} if file.filename else {}
    records = [
        ChunkRecord(
            id=f"{document_id}:{chunk.index}",
            document_id=document_id,
            text=chunk.text,
            embedding=embedding,
            page=chunk.page,
            metadata=metadata,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    await _store(request).upsert(LEGACY_COLLECTION, records)
    return IngestResponse(chunks=len(chunks))


@app.get("/cache/stats")
async def cache_stats(request: Request) -> dict[str, Any]:
    stats: dict[str, Any] = await request.app.state.cache.stats()
    return stats


@app.post("/cache/clear")
async def cache_clear(request: Request) -> dict[str, int]:
    return {"cleared": await request.app.state.cache.clear()}


@app.get("/documents/stats")
async def document_stats(request: Request) -> dict[str, Any]:
    try:
        count = await _store(request).count(LEGACY_COLLECTION)
    except ServiceError:
        return {"status": "offline", "document_count": 0}
    return {"status": "connected", "document_count": count}


@app.post("/documents/clear")
async def documents_clear(request: Request) -> dict[str, bool]:
    try:
        await _store(request).clear(LEGACY_COLLECTION)
    except ServiceError:
        return {"cleared": False}
    return {"cleared": True}
