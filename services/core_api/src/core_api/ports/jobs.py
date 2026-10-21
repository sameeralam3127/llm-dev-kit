"""The ingestion job queue and the document storage it drives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from core_api.domain.ingestion import IndexedChunk


@dataclass(frozen=True, slots=True)
class Job:
    """A claimed ingestion job. ``attempts`` already counts this attempt."""

    id: int
    document_id: UUID
    workspace_id: UUID
    attempts: int
    max_attempts: int
    locked_by: str


@dataclass(frozen=True, slots=True)
class Blob:
    """An upload's original bytes."""

    data: bytes
    media_type: str
    filename: str


class JobQueue(Protocol):
    """Claim, release and finish jobs. Every method is safe with many workers."""

    async def claim(self, worker_id: str) -> Job | None:
        """Take the next due job, or ``None``. Uses ``FOR UPDATE SKIP LOCKED``."""
        ...

    async def reclaim_expired(self, lease_seconds: float) -> int:
        """Return jobs whose worker vanished to the queue; count them."""
        ...

    async def retry_later(self, job: Job, error: str, run_after: datetime) -> bool:
        """Put the job back for another attempt. ``False`` if the lease was lost."""
        ...

    async def fail(self, job: Job, error: str) -> bool:
        """Give up on the job for good. ``False`` if the lease was lost."""
        ...


class IngestionStore(Protocol):
    """Document data the worker reads and writes."""

    async def blob_of(self, document_id: UUID) -> Blob | None:
        """The upload a document was created from."""
        ...

    async def replace_chunks(self, job: Job, chunks: list[IndexedChunk], embed_model: str) -> bool:
        """Swap the document's chunks and finish the job, in one transaction.

        Readers see the old chunks or the new ones, never a mix or an empty
        document. ``False`` (and nothing written) if the job's lease was lost.
        """
        ...
