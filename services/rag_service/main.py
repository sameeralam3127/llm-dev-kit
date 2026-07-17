import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile

from devkit_common.config import get_settings
from devkit_common.models import ChatRequest, ChatResponse, IngestResponse
from devkit_common.qdrant_store import QdrantVectorStore
from rag_service.cache import ChatCache
from rag_service.chat import answer_query
from rag_service.chroma_store import ChromaStore
from rag_service.llm_client import LLMServiceClient
from rag_service.openai_api import router as openai_router
from rag_service.pdf import chunk_text, load_pdf
from rag_service.retrieval import HybridRetriever

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.llm = LLMServiceClient(
        settings.llm_service_url, settings.request_timeout_seconds
    )
    app.state.cache = ChatCache(settings.redis_url, settings.cache_ttl)
    app.state.chroma = ChromaStore(settings.chroma_host, settings.chroma_port)
    app.state.qdrant = QdrantVectorStore.from_settings(settings)
    app.state.retriever = HybridRetriever(
        chroma=app.state.chroma,
        qdrant=app.state.qdrant,
        score_threshold=settings.retriever_score_threshold,
    )
    yield
    await app.state.llm.close()
    await app.state.cache.close()


app = FastAPI(title=f"{settings.app_name} — RAG Service", version="0.2.0", lifespan=lifespan)
app.include_router(openai_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "rag-service"}


@app.get("/models")
async def models(request: Request) -> list[str]:
    return await request.app.state.llm.models()


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


@app.post("/ingest/pdf", response_model=IngestResponse)
async def ingest_pdf(request: Request, file: UploadFile = File(...)) -> IngestResponse:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    try:
        chunks = chunk_text(load_pdf(file.file))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    embeddings = await request.app.state.llm.embed_many(chunks)
    await asyncio.to_thread(request.app.state.chroma.add, chunks, embeddings)
    return IngestResponse(chunks=len(chunks))


@app.get("/cache/stats")
async def cache_stats(request: Request) -> dict:
    return await request.app.state.cache.stats()


@app.post("/cache/clear")
async def cache_clear(request: Request) -> dict:
    return {"cleared": await request.app.state.cache.clear()}


@app.get("/documents/stats")
async def document_stats(request: Request) -> dict:
    try:
        count = await asyncio.to_thread(request.app.state.chroma.count)
        return {"status": "connected", "document_count": count}
    except Exception:
        return {"status": "offline", "document_count": 0}


@app.post("/documents/clear")
async def documents_clear(request: Request) -> dict:
    return {"cleared": await asyncio.to_thread(request.app.state.chroma.clear)}
