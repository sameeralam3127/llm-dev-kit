from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class DocumentEventType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


class DocsChangedEvent(BaseModel):
    repo: str
    branch: str
    path: str
    commit: str
    event: DocumentEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    owner: str | None = None
    installation_id: int | None = None
    url: HttpUrl | None = None

    @property
    def event_id(self) -> str:
        return f"{self.repo}:{self.branch}:{self.path}:{self.commit}:{self.event}"


class DocsIndexedEvent(BaseModel):
    repo: str
    branch: str
    path: str
    commit: str
    chunk_count: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocsFailedEvent(BaseModel):
    repo: str
    branch: str
    path: str
    commit: str
    error: str
    retryable: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
