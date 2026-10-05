import asyncio
import logging

logger = logging.getLogger(__name__)


class Retriever:
    """Retrieves context from ChromaDB (PDF uploads)."""

    def __init__(self, *, chroma, top_k: int = 3) -> None:
        self.chroma = chroma
        self.top_k = top_k

    async def retrieve(self, embedding: list[float]) -> list[str]:
        try:
            docs = await asyncio.to_thread(self.chroma.query, embedding, self.top_k)
        except Exception as exc:  # noqa: BLE001 - retrieval degrades to no context
            logger.warning("Chroma retrieval failed: %s", exc)
            return []

        return [doc for doc in docs if doc.strip()]
