"""``VectorStore``: stores chunk embeddings and answers similarity queries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    """A chunk ready to store.

    Attributes:
        id: Unique, stable id for the chunk; upserting the same id replaces it.
        document_id: The source document, for citations and deletion.
        text: Chunk text returned on a match.
        embedding: Vector from the configured :class:`~ldk_core.ports.embedding.Embedder`.
        page: 1-based source page, if known.
        metadata: Extra JSON-serialisable fields kept alongside the chunk.
    """

    id: str
    document_id: str
    text: str
    embedding: Sequence[float] = field(repr=False)
    page: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchScope:
    """Which chunks a query may see.

    The store enforces this in the query itself (in SQL for pgvector), so a
    caller cannot see another user's documents by forgetting a filter.

    Attributes:
        collection_ids: Collections to search. Empty means nothing matches.
        user_id: The requesting user, for stores that check grants per user.
            ``None`` only for trusted internal callers.
    """

    collection_ids: frozenset[str]
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One match, best first in a result list.

    Attributes:
        score: Similarity; higher is closer. Comparable only within one store.
    """

    chunk_id: str
    document_id: str
    text: str
    score: float
    page: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """Persists chunk embeddings per collection and searches them.

    Failures raise :class:`ldk_core.errors.ServiceError` with
    ``upstream_unavailable``. A store never silently returns an empty result
    for an outage; deciding to degrade is the caller's job.
    """

    @property
    def name(self) -> str:
        """Registry name, e.g. ``"pgvector"``."""
        ...

    async def upsert(self, collection_id: str, chunks: Sequence[ChunkRecord]) -> None:
        """Insert or replace ``chunks`` in ``collection_id``, all or nothing."""
        ...

    async def search(
        self, embedding: Sequence[float], *, scope: SearchScope, top_k: int
    ) -> list[SearchResult]:
        """Return up to ``top_k`` chunks within ``scope``, most similar first."""
        ...

    async def delete_document(self, collection_id: str, document_id: str) -> int:
        """Remove every chunk of one document; return how many were removed."""
        ...

    async def clear(self, collection_id: str) -> None:
        """Remove every chunk in ``collection_id``."""
        ...

    async def count(self, collection_id: str | None = None) -> int:
        """Count chunks in one collection, or across all when ``None``."""
        ...
