"""rag-service endpoints through the registry: the real PDF loader and
chunker plugins, an in-memory vector store, and fakes for llm-service and Redis.
"""

import pytest
from fastapi.testclient import TestClient
from identity import Issuer
from memory_store import MemoryVectorStore
from pdfs import make_pdf

import rag_service.main as main
from devkit_common.config import Settings
from ldk_core.auth import auth_headers
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
        self.api_keys: list[str | None] = []
        # The Authorization this client would send to llm-service, per call.
        self.forwarded: list[str | None] = []
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
        self.api_keys.append(api_key)
        self.forwarded.append(auth_headers().get("Authorization"))
        return {"response": "grounded answer", "model": model, "provider": "ollama"}

    async def generate_stream(self, prompt: str, model=None, api_key=None, options=None):
        self.prompts.append(prompt)
        self.api_keys.append(api_key)
        self.forwarded.append(auth_headers().get("Authorization"))
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
def issuer() -> Issuer:
    return Issuer()


def _patch(monkeypatch: pytest.MonkeyPatch, store: MemoryVectorStore, issuer: Issuer, **auth):
    monkeypatch.setattr(main, "build_registry", lambda settings: _registry(store))
    monkeypatch.setattr(main, "LLMServiceClient", FakeLLMClient)
    monkeypatch.setattr(main, "ChatCache", NoCache)
    monkeypatch.setattr(
        main, "build_authenticator", lambda registry, settings: issuer.authenticator(**auth)
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, store: MemoryVectorStore, issuer: Issuer):
    """Every request carries an admin token unless the test says otherwise."""
    _patch(monkeypatch, store, issuer)
    with TestClient(main.app, headers=issuer.bearer("admin")) as client:
        yield client


@pytest.fixture
def legacy_client(monkeypatch: pytest.MonkeyPatch, store: MemoryVectorStore, issuer: Issuer):
    """ALLOW_LEGACY_ANONYMOUS=true, and no default credential."""
    _patch(monkeypatch, store, issuer, allow_anonymous=True)
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


def test_store_outage_degrades_like_before(monkeypatch: pytest.MonkeyPatch, issuer: Issuer) -> None:
    _patch(monkeypatch, OfflineStore(name="chroma"), issuer)
    with TestClient(main.app, headers=issuer.bearer("admin")) as client:
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


# ------------------------------------------------------------ authentication

NO_CREDENTIAL = {"Authorization": ""}
PROTECTED = [
    ("GET", "/models"),
    ("POST", "/chat"),
    ("POST", "/chat/stream"),
    ("POST", "/ingest/pdf"),
    ("GET", "/cache/stats"),
    ("POST", "/cache/clear"),
    ("GET", "/documents/stats"),
    ("POST", "/documents/clear"),
    ("GET", "/v1/models"),
    ("POST", "/v1/chat/completions"),
]


def test_every_route_but_health_needs_a_credential(client) -> None:
    assert client.get("/health", headers=NO_CREDENTIAL).status_code == 200
    for method, path in PROTECTED:
        res = client.request(method, path, headers=NO_CREDENTIAL)
        assert res.status_code == 401, path
        assert res.json()["error"]["code"] == "unauthorized", path
        assert res.headers["www-authenticate"].startswith("Bearer"), path


def test_a_viewer_can_chat_but_not_ingest(client, issuer: Issuer) -> None:
    viewer = issuer.bearer("viewer")
    assert client.post("/chat", json={"message": "hi"}, headers=viewer).status_code == 200

    res = client.post(
        "/ingest/pdf", files={"file": ("a.pdf", make_pdf(["x"]), "application/pdf")}, headers=viewer
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "forbidden"


def test_plugin_inventory_is_admin_only_and_lists_no_configuration(client, issuer: Issuer) -> None:
    assert client.get("/plugins", headers=issuer.bearer("user")).status_code == 403

    res = client.get("/plugins")  # the fixture's default token is an admin's
    assert res.status_code == 200
    rows = {(p["kind"], p["name"]): p for p in res.json()}
    assert {("loader", "pdf"), ("chunker", "fixed"), ("vector_store", "chroma")} & set(rows)
    assert all(
        set(row) == {"kind", "name", "version", "enabled", "description", "permissions"}
        for row in rows.values()
    )


def test_a_user_can_ingest_but_only_an_admin_can_clear(client, issuer: Issuer) -> None:
    user = issuer.bearer("user")
    res = client.post(
        "/ingest/pdf", files={"file": ("a.pdf", make_pdf(["x"]), "application/pdf")}, headers=user
    )
    assert res.status_code == 200
    assert client.post("/documents/clear", headers=user).status_code == 403
    assert client.post("/cache/clear", headers=user).status_code == 403
    assert client.post("/documents/clear").status_code == 200  # the fixture's admin


def test_v1_accepts_a_personal_api_key(client, issuer: Issuer) -> None:
    issuer.api_keys["sk-ldk-sdk-key-0001"] = "viewer"
    res = client.post(
        "/v1/chat/completions",
        json={"model": "llama3.1", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer sk-ldk-sdk-key-0001"},
    )
    assert res.status_code == 200
    # llm-service gets the exchanged token, never the key itself, and the
    # Bearer is an identity, not a cloud key.
    llm = client.app.state.llm
    assert llm.forwarded[-1].startswith("Bearer ey")
    assert llm.api_keys[-1] is None


def test_the_callers_token_reaches_llm_service_while_streaming(client, issuer: Issuer) -> None:
    token = issuer.token("user")
    res = client.post(
        "/chat/stream", json={"message": "hi"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert client.app.state.llm.forwarded == [f"Bearer {token}"]


def test_legacy_anonymous_keeps_the_old_v1_contract(legacy_client) -> None:
    body = {"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
    assert legacy_client.post("/v1/chat/completions", json=body).status_code == 200
    legacy_client.post(
        "/v1/chat/completions", json=body, headers={"Authorization": "Bearer sk-openai-real"}
    )
    legacy_client.post(
        "/v1/chat/completions", json=body, headers={"Authorization": "Bearer sk-local-x"}
    )

    llm = legacy_client.app.state.llm
    # No key, a cloud key forwarded as before, a placeholder ignored as before.
    assert llm.api_keys == [None, "sk-openai-real", None]
    assert llm.forwarded == [None, None, None]


def test_one_requests_identity_does_not_leak_into_the_next(legacy_client, issuer: Issuer) -> None:
    legacy_client.post("/chat", json={"message": "a"}, headers=issuer.bearer("user"))
    legacy_client.post("/chat", json={"message": "b"})
    forwarded = legacy_client.app.state.llm.forwarded
    assert forwarded[0] and forwarded[0].startswith("Bearer ")
    assert forwarded[1] is None
