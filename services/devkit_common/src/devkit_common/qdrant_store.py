from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from devkit_common.config import Settings, get_settings


class QdrantVectorStore:
    def __init__(self, *, url: str, collection: str) -> None:
        self.url = url
        self.collection = collection
        self._client = None

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "QdrantVectorStore":
        settings = settings or get_settings()
        return cls(url=settings.qdrant_url, collection=settings.qdrant_collection)

    def _get_client(self):
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient
            except ImportError as exc:
                raise RuntimeError("Install qdrant-client to use Qdrant") from exc
            self._client = AsyncQdrantClient(url=self.url)
        return self._client

    async def _ensure_collection(self, vector_size: int) -> None:
        from qdrant_client.http import models

        client = self._get_client()
        collections = await client.get_collections()
        existing = {collection.name for collection in collections.collections}
        if self.collection not in existing:
            await client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

    async def upsert_documents(
        self,
        documents: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]],
    ) -> None:
        if not documents or not embeddings:
            return
        if len(documents) != len(embeddings) or len(documents) != len(metadata):
            raise ValueError("documents, embeddings, and metadata must have same length")

        from qdrant_client.http import models

        await self._ensure_collection(len(embeddings[0]))
        points = []
        for text, vector, payload in zip(documents, embeddings, metadata, strict=True):
            chunk_key = (
                f"{payload['repo']}:{payload['branch']}:{payload['path']}:"
                f"{payload['chunk_id']}"
            )
            points.append(
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, chunk_key)),
                    vector=vector,
                    payload={
                        **payload,
                        "text": text,
                        "source": "github",
                        "last_indexed": datetime.now(UTC).isoformat(),
                    },
                )
            )
        await self._get_client().upsert(collection_name=self.collection, points=points)

    async def search(
        self, query_embedding: list[float], limit: int = 5
    ) -> list[dict[str, Any]]:
        results = await self._get_client().search(
            collection_name=self.collection,
            query_vector=query_embedding,
            limit=limit,
            with_payload=True,
        )
        return [
            {"score": result.score, "payload": result.payload or {}}
            for result in results
        ]

    async def delete_by_repo_path(self, repo: str, path: str) -> None:
        from qdrant_client.http import models

        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="repo", match=models.MatchValue(value=repo)
                    ),
                    models.FieldCondition(
                        key="path", match=models.MatchValue(value=path)
                    ),
                    models.FieldCondition(
                        key="source", match=models.MatchValue(value="github")
                    ),
                ]
            )
        )
        await self._get_client().delete(
            collection_name=self.collection, points_selector=selector
        )
