import asyncio

from app.config import Settings
from app.models.events import DocsChangedEvent, DocumentEventType
from app.workers.embedding_worker import process_embedding_event


class FakeGitHub:
    async def download_markdown(self, owner, repo, path, branch):
        return "# Title\n\nHello documentation"

    async def latest_commit_sha(self, owner, repo, path, branch):
        return "sha"

    async def repository_metadata(self, owner, repo):
        return {}

    async def search_markdown(self, owner, repo, query, branch):
        return []


class FakeVectorStore:
    def __init__(self) -> None:
        self.upserts = []
        self.deletes = []

    async def upsert_documents(self, documents, embeddings, metadata):
        self.upserts.append((documents, embeddings, metadata))

    async def search(self, query_embedding, limit=5):
        return []

    async def delete_by_repo_path(self, repo, path):
        self.deletes.append((repo, path))


class FakeEmbeddings:
    async def embed_many(self, texts):
        return [[0.1, 0.2] for _ in texts]

    async def embed_one(self, text):
        return [0.1, 0.2]


class FakeBus:
    def __init__(self) -> None:
        self.published = []

    async def publish(self, topic, event, key=None):
        self.published.append((topic, event, key))


class FakeCache:
    def __init__(self) -> None:
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ttl=None):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)


def test_process_embedding_event_upserts_and_publishes_indexed():
    settings = Settings(GITHUB_DEFAULT_OWNER="acme")
    vector_store = FakeVectorStore()
    bus = FakeBus()

    asyncio.run(
        process_embedding_event(
            DocsChangedEvent(
                owner="acme",
                repo="docs",
                branch="main",
                path="docs/a.md",
                commit="sha",
                event=DocumentEventType.MODIFIED,
            ),
            github=FakeGitHub(),
            vector_store=vector_store,
            embedding_provider=FakeEmbeddings(),
            event_bus=bus,
            cache=FakeCache(),
            settings=settings,
        ),
    )

    assert vector_store.upserts
    assert bus.published[0][0] == settings.kafka_topic_docs_indexed
    assert vector_store.upserts[0][2][0]["source"] == "github"


def test_process_delete_event_removes_vectors():
    settings = Settings(GITHUB_DEFAULT_OWNER="acme")
    vector_store = FakeVectorStore()

    asyncio.run(
        process_embedding_event(
            DocsChangedEvent(
                owner="acme",
                repo="docs",
                branch="main",
                path="docs/a.md",
                commit="sha",
                event=DocumentEventType.REMOVED,
            ),
            github=FakeGitHub(),
            vector_store=vector_store,
            embedding_provider=FakeEmbeddings(),
            event_bus=FakeBus(),
            cache=None,
            settings=settings,
        ),
    )

    assert vector_store.deletes == [("docs", "docs/a.md")]
