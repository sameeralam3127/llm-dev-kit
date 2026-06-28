import asyncio

from app.services.ollama_client import embed


class OllamaEmbeddingProvider:
    async def embed_one(self, text: str) -> list[float] | None:
        return await asyncio.to_thread(embed, text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        embeddings = await asyncio.gather(*(self.embed_one(text) for text in texts))
        if any(embedding is None for embedding in embeddings):
            raise ValueError("Embedding provider returned an empty embedding")
        return [embedding for embedding in embeddings if embedding is not None]
