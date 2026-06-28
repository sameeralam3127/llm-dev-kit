from pydantic import BaseModel, Field

from app.models.events import (
    DocsChangedEvent,
    DocsFailedEvent,
    DocsIndexedEvent,
    DocumentEventType,
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    model: str | None = None


class ChatResponse(BaseModel):
    response: str
    model: str
    cached: bool = False
    sources: list[str] = []


class IngestResponse(BaseModel):
    chunks: int


class HealthResponse(BaseModel):
    status: str
    ollama_models: int


__all__ = [
    "ChatRequest",
    "ChatResponse",
    "DocsChangedEvent",
    "DocsFailedEvent",
    "DocsIndexedEvent",
    "DocumentEventType",
    "HealthResponse",
    "IngestResponse",
]
