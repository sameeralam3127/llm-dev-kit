from ldk_core.errors import ServiceError
from ldk_core.observability import get_logger
from ldk_core.ports import SearchScope, VectorStore

logger = get_logger(__name__)

LEGACY_COLLECTION = "documents"
"""The single shared collection every upload lands in until Phase 5 adds
per-user collections."""


class Retriever:
    """Retrieves context for a query embedding from the vector store."""

    def __init__(
        self, *, store: VectorStore, collection_id: str = LEGACY_COLLECTION, top_k: int = 3
    ) -> None:
        self.store = store
        self.scope = SearchScope(collection_ids=frozenset({collection_id}))
        self.top_k = top_k

    async def retrieve(self, embedding: list[float]) -> list[str]:
        try:
            results = await self.store.search(embedding, scope=self.scope, top_k=self.top_k)
        except ServiceError as exc:
            # Retrieval degrades to answering without context rather than failing.
            logger.warning("retrieval failed", store=self.store.name, error=exc.message)
            return []

        return [r.text for r in results if r.text.strip()]
