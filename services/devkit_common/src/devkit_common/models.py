from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    model: str | None = None
    api_key: str | None = None


class ChatResponse(BaseModel):
    response: str
    model: str
    provider: str | None = None
    cached: bool = False
    sources: list[str] = []


class IngestResponse(BaseModel):
    chunks: int


class HealthResponse(BaseModel):
    status: str
    info: dict[str, Any] = {}
