"""ChromaDB as a :class:`~ldk_core.ports.VectorStore`.

Deprecated by design: Chroma cannot enforce per-user access in the query,
which is why Phase 5 replaces it with pgvector. Until then this adapter keeps
today's behaviour, where every chunk lives in the ``documents`` collection,
behind the port.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import ChunkRecord, SearchResult, SearchScope


class ChromaVectorStore:
    """Chroma over HTTP, run in worker threads (the client is synchronous).

    Each collection id becomes the Chroma collection
    ``f"{collection_prefix}{collection_id}"``. Chunks ingested before v2 have
    no metadata; they come back with an empty ``document_id`` and no page.

    Args:
        host: Chroma server host.
        port: Chroma server port.
        collection_prefix: Namespaces collection names, e.g. per test run.
        client: A ready ``chromadb`` client; for tests.
    """

    name = "chroma"

    def __init__(
        self, host: str, port: int = 8000, *, collection_prefix: str = "", client: Any = None
    ) -> None:
        self.host = host
        self.port = port
        self.prefix = collection_prefix
        self._client = client

    async def upsert(self, collection_id: str, chunks: Sequence[ChunkRecord]) -> None:
        """Insert or replace chunks by id."""
        if not chunks:
            return

        def run() -> None:
            self._collection(collection_id).upsert(
                ids=[c.id for c in chunks],
                documents=[c.text for c in chunks],
                embeddings=[list(c.embedding) for c in chunks],
                metadatas=[_metadata(c) for c in chunks],
            )

        await self._call(run)

    async def search(
        self, embedding: Sequence[float], *, scope: SearchScope, top_k: int
    ) -> list[SearchResult]:
        """Query each collection in scope and merge by similarity."""
        if not scope.collection_ids or top_k <= 0:
            return []

        def run() -> list[SearchResult]:
            hits: list[SearchResult] = []
            for collection_id in sorted(scope.collection_ids):
                collection = self._collection(collection_id)
                res = collection.query(
                    query_embeddings=[list(embedding)],
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"],
                )
                hits.extend(_results(res))
            return sorted(hits, key=lambda h: h.score, reverse=True)[:top_k]

        return await self._call(run)

    async def delete_document(self, collection_id: str, document_id: str) -> int:
        """Delete every chunk whose metadata names ``document_id``."""

        def run() -> int:
            collection = self._collection(collection_id)
            ids = collection.get(where={"document_id": document_id}, include=[])["ids"]
            if ids:
                collection.delete(ids=ids)
            return len(ids)

        return await self._call(run)

    async def clear(self, collection_id: str) -> None:
        """Drop the collection; the next upsert recreates it empty."""

        def run() -> None:
            self._collection(collection_id)  # create-if-missing keeps delete simple
            self._get_client().delete_collection(name=self._name(collection_id))

        await self._call(run)

    async def count(self, collection_id: str | None = None) -> int:
        """Chunks in one collection, or in every collection under the prefix."""

        def run() -> int:
            if collection_id is not None:
                return int(self._collection(collection_id).count())
            client = self._get_client()
            return sum(
                int(client.get_collection(name=c.name).count())
                for c in client.list_collections()
                if c.name.startswith(self.prefix)
            )

        return await self._call(run)

    def _name(self, collection_id: str) -> str:
        return f"{self.prefix}{collection_id}"

    def _get_client(self) -> Any:
        if self._client is None:
            import chromadb  # heavy; imported only once the store is used

            self._client = chromadb.HttpClient(host=self.host, port=self.port)
        return self._client

    def _collection(self, collection_id: str) -> Any:
        return self._get_client().get_or_create_collection(name=self._name(collection_id))

    async def _call[T](self, fn: Callable[[], T]) -> T:
        """Run ``fn`` in a thread; any Chroma failure becomes upstream_unavailable."""
        try:
            return await asyncio.to_thread(fn)
        except ServiceError:
            raise
        except Exception as exc:  # chromadb raises many unrelated types
            raise ServiceError(
                ErrorCode.UPSTREAM_UNAVAILABLE, f"Chroma unavailable: {str(exc)[:200]}"
            ) from exc


def _metadata(chunk: ChunkRecord) -> dict[str, Any]:
    """Chroma metadata for a chunk; Chroma rejects None values, so omit them."""
    meta: dict[str, Any] = {k: v for k, v in chunk.metadata.items() if v is not None}
    meta["document_id"] = chunk.document_id
    if chunk.page is not None:
        meta["page"] = chunk.page
    return meta


def _results(res: Any) -> list[SearchResult]:
    """Flatten one Chroma query result (a single query embedding)."""
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0] or [None] * len(ids)
    dists = (res.get("distances") or [[]])[0]
    hits = []
    for chunk_id, text, meta, distance in zip(ids, docs, metas, dists, strict=True):
        meta = dict(meta or {})
        page = meta.pop("page", None)
        hits.append(
            SearchResult(
                chunk_id=chunk_id,
                document_id=str(meta.pop("document_id", "")),
                text=text or "",
                # Chroma returns distances; 1 / (1 + d) is higher for closer.
                score=1.0 / (1.0 + float(distance)),
                page=int(page) if page is not None else None,
                metadata=meta,
            )
        )
    return hits
