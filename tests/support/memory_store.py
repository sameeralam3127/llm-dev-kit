"""An in-memory VectorStore: the reference implementation for tests."""

import math
from collections.abc import Sequence

from ldk_core.ports import ChunkRecord, SearchResult, SearchScope


class MemoryVectorStore:
    def __init__(self, name: str = "memory") -> None:
        self.name = name
        self._collections: dict[str, dict[str, ChunkRecord]] = {}

    async def upsert(self, collection_id: str, chunks: Sequence[ChunkRecord]) -> None:
        target = self._collections.setdefault(collection_id, {})
        target.update({c.id: c for c in chunks})

    async def search(
        self, embedding: Sequence[float], *, scope: SearchScope, top_k: int
    ) -> list[SearchResult]:
        hits = [
            SearchResult(c.id, c.document_id, c.text, _cosine(embedding, c.embedding), c.page)
            for cid in scope.collection_ids
            for c in self._collections.get(cid, {}).values()
        ]
        return sorted(hits, key=lambda r: r.score, reverse=True)[:top_k]

    async def delete_document(self, collection_id: str, document_id: str) -> int:
        chunks = self._collections.get(collection_id, {})
        doomed = [cid for cid, c in chunks.items() if c.document_id == document_id]
        for cid in doomed:
            del chunks[cid]
        return len(doomed)

    async def clear(self, collection_id: str) -> None:
        self._collections.pop(collection_id, None)

    async def count(self, collection_id: str | None = None) -> int:
        if collection_id is not None:
            return len(self._collections.get(collection_id, {}))
        return sum(len(c) for c in self._collections.values())


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    norm = math.hypot(*a) * math.hypot(*b)
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0
