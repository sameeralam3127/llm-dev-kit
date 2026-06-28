from fastapi import FastAPI, File, HTTPException, UploadFile

from app.api.github_webhook import router as github_webhook_router
from app.config import get_settings
from app.models import ChatRequest, ChatResponse, HealthResponse, IngestResponse
from app.services.cache import clear_cache, get_cache_stats
from app.services.ollama_client import get_models
from app.services.rag import hybrid_query, ingest_pdf
from app.services.vector_store import clear_all_documents, get_collection_stats


settings = get_settings()
api = FastAPI(title=settings.app_name, version="0.1.0")
api.include_router(github_webhook_router)


@api.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    models = get_models()
    return HealthResponse(status="ok", ollama_models=len(models))


@api.get("/models", response_model=list[str])
def models() -> list[str]:
    return get_models()


@api.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    model = request.model or settings.default_chat_model
    return hybrid_query(request.message, model=model)


@api.post("/ingest/pdf", response_model=IngestResponse)
def ingest_pdf_endpoint(file: UploadFile = File(...)) -> IngestResponse:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    try:
        return IngestResponse(chunks=ingest_pdf(file.file))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.get("/cache/stats")
def cache_stats() -> dict:
    return get_cache_stats()


@api.post("/cache/clear")
def clear_cache_endpoint() -> dict:
    return {"cleared": clear_cache()}


@api.get("/documents/stats")
def document_stats() -> dict:
    return get_collection_stats()


@api.post("/documents/clear")
def clear_documents_endpoint() -> dict:
    return {"cleared": clear_all_documents()}
