"""One job, start to finish. Every outcome leaves the queue consistent."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from core_api.domain.ingestion import IndexedChunk, backoff_seconds, batched, is_permanent
from core_api.ports.jobs import IngestionStore, Job, JobQueue
from ldk_core.observability import correlation_scope, get_logger
from ldk_core.ports import Chunker, DocumentLoader, Embedder

Outcome = Literal["succeeded", "retrying", "failed", "lease_lost"]

_log = get_logger(__name__)


async def process_next(
    *,
    queue: JobQueue,
    store: IngestionStore,
    loader: DocumentLoader,
    chunker: Chunker,
    embedder: Embedder,
    worker_id: str,
    batch_size: int = 32,
    rand: Callable[[], float] = random.random,
) -> Outcome | None:
    """Claim one due job and run it. ``None`` when the queue has nothing due."""
    job = await queue.claim(worker_id)
    if job is None:
        return None
    with correlation_scope(f"job-{job.id}"):
        try:
            chunks = await _index(job, store, loader, chunker, embedder, batch_size)
        except Exception as exc:  # noqa: BLE001 - every failure must settle the job
            return await _settle_failure(queue, job, exc, rand)
        if not await store.replace_chunks(job, chunks, embedder.model):
            _log.warning("lease lost before commit; another worker owns the job", job=job.id)
            return "lease_lost"
        _log.info("document indexed", job=job.id, document=str(job.document_id), chunks=len(chunks))
        return "succeeded"


async def _index(
    job: Job,
    store: IngestionStore,
    loader: DocumentLoader,
    chunker: Chunker,
    embedder: Embedder,
    batch_size: int,
) -> list[IndexedChunk]:
    blob = await store.blob_of(job.document_id)
    if blob is None:
        raise LookupError(f"document {job.document_id} has no stored upload")
    # Parsing and chunking are CPU-bound pure Python. Running them in a thread
    # keeps this process's event loop responsive; running the worker as its own
    # process keeps that work away from the API's GIL entirely.
    document = await asyncio.to_thread(loader.load, blob.data, filename=blob.filename)
    pieces = await asyncio.to_thread(chunker.chunk, document)

    indexed: list[IndexedChunk] = []
    for batch in batched(pieces, batch_size):
        vectors = await embedder.embed([piece.text for piece in batch])
        indexed.extend(
            IndexedChunk(ord=piece.index, text=piece.text, page=piece.page, embedding=vector)
            for piece, vector in zip(batch, vectors, strict=True)
        )
    return indexed


async def _settle_failure(
    queue: JobQueue, job: Job, exc: BaseException, rand: Callable[[], float]
) -> Outcome:
    error = f"{type(exc).__name__}: {exc}"[:2000]
    if is_permanent(exc) or job.attempts >= job.max_attempts:
        settled = await queue.fail(job, error)
        _log.warning("job failed", job=job.id, attempts=job.attempts, error=error)
        return "failed" if settled else "lease_lost"
    delay = backoff_seconds(job.attempts, rand)
    settled = await queue.retry_later(job, error, datetime.now(UTC) + timedelta(seconds=delay))
    _log.info(
        "job will retry", job=job.id, attempts=job.attempts, in_seconds=round(delay, 1), error=error
    )
    return "retrying" if settled else "lease_lost"
