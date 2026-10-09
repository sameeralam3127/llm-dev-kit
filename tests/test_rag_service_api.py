"""rag-service endpoints through the registry: the real PDF loader and
chunker plugins, an in-memory vector store, and fakes for llm-service and Redis.
"""

import pytest
from fastapi.testclient import TestClient
from memory_store import MemoryVectorStore
from pdfs import make_pdf

import rag_service.main as main
from devkit_common.config import Settings
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.plugins import CHUNKER, LOADER, VECTOR_STORE, Plugin, PluginRegistry, parse_manifest
from ldk_plugin_chroma import ChromaVectorStore
from ldk_plugin_chunker_fixed import FixedWindowChunker
from ldk_plugin_chunker_fixed import plugin as chunker_plugin
from ldk_plugin_loader_pdf import PdfLoader
from ldk_plugin_loader_pdf import plugin as loader_plugin


class FakeLLMClient:
    """Stands in for llm-service: every text embeds to the same vector."""

    def __init__(self, *_: object) -> None:
        self.prompts: list[str] = []
        self.embed_error: ServiceError | None = None

    async def models(self) -> list[str]:
        return ["llama3.1"]

    async def embed_one(self, text: str) -> list[float] | None:
        return [1.0, 0.0]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if self.embed_error:
            raise self.embed_error
        return [[1.0, 0.0] for _ in texts]

    async def generate(self, prompt: str, model=None, api_key=None, options=None) -> dict:
        self.prompts.append(prompt)
        return {"response": "grounded answer", "model": model, "provider": "ollama"}

    async def generate_stream(self, prompt: str, model=None, api_key=None, options=None):
        self.prompts.append(prompt)
        yield "grounded "
        yield "answer"

    async def close(self) -> None:
        pass


class NoCache:
    def __init__(self, *_: object) -> None:
        pass

    async def get(self, prompt, model=None):
        return None

    async def set(self, prompt, model, value):
        pass

    async def stats(self):
        return {"status": "connected", "keys": 0}

    async def clear(self):
        return 0

    async def close(self):
        pass


class OfflineStore(MemoryVectorStore):
    async def count(self, collection_id=None) -> int:
        raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Chroma unavailable")

    async def clear(self, collection_id: str) -> None:
        raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Chroma unavailable")


def _registry(store: MemoryVectorStore) -> PluginRegistry:
    registry = PluginRegistry()
    manifest = parse_manifest(
        {"name": "chroma", "version": "0.0.0", "kind": "vector_store", "description": "memory"}
    )
    registry.register(Plugin(manifest, lambda _: store))
    registry.register(loader_plugin)
    registry.register(chunker_plugin)
    return registry


@pytest.fixture
def store() -> MemoryVectorStore:
    # Registered under the name rag-service asks for.
    return MemoryVectorStore(name="chroma")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, store: MemoryVectorStore):
    monkeypatch.setattr(main, "build_registry", lambda settings: _registry(store))
    monkeypatch.setattr(main, "LLMServiceClient", FakeLLMClient)
    monkeypatch.setattr(main, "ChatCache", NoCache)
    with TestClient(main.app) as client:
        yield client


def _upload(client: TestClient, data: bytes, content_type: str = "application/pdf"):
    return client.post("/ingest/pdf", files={"file": ("notes.pdf", data, content_type)})


def test_ingest_then_chat_uses_the_document(client, store: MemoryVectorStore) -> None:
    res = _upload(client, make_pdf(["Sovereign mode keeps every byte local.", "Page two."]))
    assert res.status_code == 200
    assert res.json() == {"chunks": 1}

    stored = list(store._collections["documents"].values())
    assert len(stored) == 1
    assert stored[0].page == 1
    assert stored[0].metadata == {"filename": "notes.pdf"}
    assert stored[0].id.endswith(":0")

    chat = client.post("/chat", json={"message": "What does sovereign mode do?"}).json()
    assert chat["response"] == "grounded answer"
    assert chat["sources"] == ["Sovereign mode keeps every byte local.\nPage two."]
    assert "every byte local" in client.app.state.llm.prompts[-1]


def test_document_stats_and_clear(client) -> None:
    assert client.get("/documents/stats").json() == {"status": "connected", "document_count": 0}
    _upload(client, make_pdf(["x " * 400]))
    assert client.get("/documents/stats").json()["document_count"] == 2
    assert client.post("/documents/clear").json() == {"cleared": True}
    assert client.get("/documents/stats").json()["document_count"] == 0


def test_store_outage_degrades_like_before(monkeypatch: pytest.MonkeyPatch) -> None:
    offline = OfflineStore(name="chroma")
    monkeypatch.setattr(main, "build_registry", lambda settings: _registry(offline))
    monkeypatch.setattr(main, "LLMServiceClient", FakeLLMClient)
    monkeypatch.setattr(main, "ChatCache", NoCache)
    with TestClient(main.app) as client:
        assert client.get("/documents/stats").json() == {
            "status": "offline",
            "document_count": 0,
        }
        assert client.post("/documents/clear").json() == {"cleared": False}


def test_bad_uploads_are_400_envelopes(client) -> None:
    wrong_type = _upload(client, b"hello", content_type="text/plain")
    assert wrong_type.status_code == 400
    assert wrong_type.json()["error"]["message"] == "Only PDF uploads are supported"

    not_a_pdf = _upload(client, b"%PDF-1.4 garbage")
    assert not_a_pdf.status_code == 400
    assert not_a_pdf.json()["error"]["code"] == "invalid_request"

    no_text = _upload(client, make_pdf([""]))
    assert no_text.json()["error"]["message"] == "No readable text in PDF"


def test_embedding_failure_surfaces_as_the_upstream_error(client) -> None:
    client.app.state.llm.embed_error = ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "down")
    res = _upload(client, make_pdf(["text"]))
    assert res.status_code == 503
    assert res.json()["error"] == {"code": "upstream_unavailable", "message": "down"}


def test_openai_endpoint_without_a_user_message(client) -> None:
    res = client.post(
        "/v1/chat/completions", json={"messages": [{"role": "system", "content": "x"}]}
    )
    assert res.status_code == 400
    assert res.json()["error"]["message"] == "No user message provided"


def test_openai_streaming_still_works(client) -> None:
    res = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert res.text.endswith("data: [DONE]\n\n")
    assert '"content": "grounded "' in res.text


def test_real_build_registry_configures_the_rag_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHROMA_HOST", "chroma.test")
    monkeypatch.setenv("CHROMA_PORT", "9000")
    registry = main.build_registry(Settings())
    store = registry.get(VECTOR_STORE, "chroma")
    assert isinstance(store, ChromaVectorStore)
    assert (store.host, store.port, store.prefix) == ("chroma.test", 9000, "")
    assert isinstance(registry.get(LOADER, "pdf"), PdfLoader)
    chunker = registry.get(CHUNKER, "fixed")
    assert isinstance(chunker, FixedWindowChunker)
    assert (chunker.size, chunker.overlap) == (500, 50)
