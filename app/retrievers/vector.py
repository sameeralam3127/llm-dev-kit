from app.interfaces import EmbeddingProvider, VectorStore


class VectorRetriever:
    def __init__(
        self,
        *,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        score_threshold: float,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.score_threshold = score_threshold

    async def retrieve_with_metadata(self, question: str, limit: int = 5) -> list[dict]:
        embedding = await self.embedding_provider.embed_one(question)
        if not embedding:
            return []
        results = await self.vector_store.search(embedding, limit=limit)
        return [
            result
            for result in results
            if float(result.get("score", 0.0)) >= self.score_threshold
        ]

    async def retrieve(self, question: str) -> list[str]:
        results = await self.retrieve_with_metadata(question)
        return [str(result.get("payload", {}).get("text", "")) for result in results]
