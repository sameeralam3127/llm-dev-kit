"""llm-service endpoints, end to end through the registry and the real plugins.

Only the network is faked: Ollama by an in-process HTTP double, the cloud by
replacing litellm.acompletion.
"""

import json

import httpx
import pytest
from fake_litellm import FakeLiteLLM
from fake_ollama import FakeOllama
from fastapi.testclient import TestClient

import ldk_plugin_litellm.provider as litellm_module
import llm_service.main as main
from devkit_common.config import Settings
from ldk_core.plugins import EMBEDDER, LLM, Plugin, PluginKind, PluginRegistry
from ldk_plugin_litellm import anthropic_plugin, gemini_plugin, openai_plugin
from ldk_plugin_ollama import (
    OllamaEmbedder,
    OllamaProvider,
    embedder_plugin,
    llm_plugin,
)


@pytest.fixture
def ollama() -> FakeOllama:
    return FakeOllama(models=("llama3.1",))


@pytest.fixture
def cloud(monkeypatch: pytest.MonkeyPatch) -> FakeLiteLLM:
    fake = FakeLiteLLM()
    monkeypatch.setattr(litellm_module.litellm, "acompletion", fake.acompletion)
    return fake


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, ollama: FakeOllama, cloud: FakeLiteLLM):
    def build_registry(settings: Settings):
        registry = PluginRegistry()
        transport = ollama.transport()
        registry.register(
            Plugin(llm_plugin.manifest, lambda c: OllamaProvider(c["host"], transport=transport))
        )
        registry.register(
            Plugin(
                embedder_plugin.manifest,
                lambda c: OllamaEmbedder(c["host"], model=c["model"], transport=transport),
            )
        )
        for plugin in (openai_plugin, gemini_plugin, anthropic_plugin):
            registry.register(plugin)
        registry.configure(PluginKind.LLM, "ollama", {"host": "http://ollama.test"})
        registry.configure(
            PluginKind.EMBEDDER,
            "ollama",
            {"host": "http://ollama.test", "model": "nomic-embed-text"},
        )
        registry.configure(PluginKind.LLM, "openai", {"api_key": "sk-server"})
        return registry, {"openai": True, "gemini": False, "anthropic": False}

    monkeypatch.setattr(main, "build_registry", build_registry)
    with TestClient(main.app) as client:
        yield client


def _ndjson(res: httpx.Response) -> list[dict]:
    return [json.loads(line) for line in res.text.splitlines() if line]


def test_models_lists_local_then_curated_cloud(client) -> None:
    models = client.get("/models").json()["models"]
    assert models[0] == "llama3.1"
    providers = list(dict.fromkeys(m.split("/")[0] for m in models[1:]))
    assert providers == ["openai", "gemini", "anthropic"]  # same order as before
    assert "openai/gpt-4o" in models
    assert "anthropic/claude-sonnet-5" in models


def test_generate_local(client, ollama: FakeOllama) -> None:
    res = client.post("/generate", json={"prompt": "hi", "model": "llama3.1", "api_key": "x"})
    assert res.json() == {"response": "answer to: hi", "model": "llama3.1", "provider": "ollama"}
    assert ollama.requests[-1][1]["prompt"] == "hi"


def test_generate_cloud_uses_server_key(client, cloud: FakeLiteLLM) -> None:
    res = client.post("/generate", json={"prompt": "hi", "model": "openai/gpt-4o"})
    assert res.json()["provider"] == "openai"
    assert res.json()["response"] == "gpt-4o says: hi"
    assert cloud.calls[-1]["api_key"] == "sk-server"


def test_generate_cloud_without_any_key_is_a_401_envelope(client) -> None:
    res = client.post("/generate", json={"prompt": "hi", "model": "gemini/gemini-2.5-flash"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"
    assert "GEMINI_API_KEY" in res.json()["error"]["message"]


def test_unknown_local_model_is_a_502_envelope(client) -> None:
    res = client.post("/generate", json={"prompt": "hi", "model": "mistral"})
    assert res.status_code == 502
    assert "model 'mistral' not found" in res.json()["error"]["message"]


def test_stream_ndjson_protocol_is_unchanged(client) -> None:
    res = client.post("/generate/stream", json={"prompt": "hi", "model": "llama3.1"})
    events = _ndjson(res)
    assert "".join(e.get("delta", "") for e in events) == "answer to: hi"
    assert events[-1] == {"done": True, "model": "llama3.1", "provider": "ollama"}


def test_stream_errors_are_reported_inline(client) -> None:
    events = _ndjson(client.post("/generate/stream", json={"prompt": "hi", "model": "nope"}))
    assert len(events) == 1
    assert "model 'nope' not found" in events[0]["error"]


def test_embed(client) -> None:
    body = client.post("/embed", json={"texts": ["a", "b"]}).json()
    assert body["model"] == "nomic-embed-text"
    assert body["dimension"] == 768
    assert len(body["embeddings"]) == 2


def test_embed_refuses_a_different_model(client) -> None:
    res = client.post("/embed", json={"texts": ["a"], "model": "all-minilm"})
    assert res.status_code == 400
    assert "embeds with 'nomic-embed-text'" in res.json()["error"]["message"]


def test_validation_uses_the_envelope(client) -> None:
    res = client.post("/embed", json={"texts": []})
    assert res.status_code == 400
    assert res.json()["error"]["details"][0]["path"] == "body.texts"


def test_health_and_providers(client) -> None:
    health = client.get("/health").json()
    assert health == {
        "status": "ok",
        "offline_ready": True,
        "cloud_providers": {"anthropic": False, "gemini": False, "openai": True},
    }
    providers = client.get("/providers").json()
    assert providers[0] == {"name": "ollama", "type": "offline", "configured": True, "prefix": ""}
    assert {p["name"]: p["configured"] for p in providers[1:]} == health["cloud_providers"]


def test_health_degrades_when_ollama_is_down(client, ollama: FakeOllama) -> None:
    ollama.down = True
    assert client.get("/health").json()["status"] == "degraded"
    assert client.get("/models").json()["models"][0] == "openai/gpt-4o"


def test_responses_carry_a_request_id(client) -> None:
    assert client.get("/models", headers={"X-Request-ID": "r-1"}).headers["x-request-id"] == "r-1"


def test_real_build_registry_configures_every_first_party_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.test:11434")
    registry, configured = main.build_registry(Settings())

    assert registry.names(LLM) == ["anthropic", "gemini", "ollama", "openai"]
    assert registry.names(EMBEDDER) == ["ollama"]
    assert configured == {"openai": True, "gemini": False, "anthropic": False}
    ollama = registry.get(LLM, "ollama")
    assert isinstance(ollama, OllamaProvider)
    assert ollama.host == "http://ollama.test:11434"
    assert registry.get(EMBEDDER, "ollama").dimension == 768
