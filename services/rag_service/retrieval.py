import asyncio
import logging

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Retrieves context from ChromaDB (PDF uploads) and Qdrant (GitHub docs).

    Both stores are populated with embeddings from the same local model, so the
    query embedding is valid against either. Each backend failing is non-fatal.
    """

    def __init__(self, *, chroma, qdrant, score_threshold: float, top_k: int = 3) -> None:
        self.chroma = chroma
        self.qdrant = qdrant
        self.score_threshold = score_threshold
        self.top_k = top_k

    async def retrieve(self, embedding: list[float]) -> list[str]:
        docs: list[str] = []

        try:
            docs.extend(await asyncio.to_thread(self.chroma.query, embedding, self.top_k))
        except Exception as exc:
            logger.warning("Chroma retrieval failed: %s", exc)

        try:
            hits = await self.qdrant.search(embedding, limit=self.top_k)
            docs.extend(
                str(hit["payload"].get("text", ""))
                for hit in hits
                if float(hit.get("score", 0.0)) >= self.score_threshold
            )
        except Exception as exc:
            logger.warning("Qdrant retrieval failed: %s", exc)

        return [doc for doc in docs if doc.strip()]
