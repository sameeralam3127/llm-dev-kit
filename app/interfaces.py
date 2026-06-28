from typing import Any, Protocol

from app.models.events import DocsChangedEvent


class EventBus(Protocol):
    async def publish(self, topic: str, event: Any, key: str | None = None) -> None: ...


class Retriever(Protocol):
    async def retrieve(self, question: str) -> list[str]: ...


class VectorStore(Protocol):
    async def upsert_documents(
        self, documents: list[str], embeddings: list[list[float]], metadata: list[dict]
    ) -> None: ...

    async def search(
        self, query_embedding: list[float], limit: int = 5
    ) -> list[dict[str, Any]]: ...

    async def delete_by_repo_path(self, repo: str, path: str) -> None: ...


class EmbeddingProvider(Protocol):
    async def embed_many(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_one(self, text: str) -> list[float] | None: ...


class GitHubClient(Protocol):
    async def download_markdown(
        self, owner: str, repo: str, path: str, branch: str
    ) -> str: ...

    async def latest_commit_sha(
        self, owner: str, repo: str, path: str, branch: str
    ) -> str: ...

    async def repository_metadata(self, owner: str, repo: str) -> dict[str, Any]: ...

    async def search_markdown(
        self, owner: str, repo: str, query: str, branch: str
    ) -> list[DocsChangedEvent]: ...


class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...
