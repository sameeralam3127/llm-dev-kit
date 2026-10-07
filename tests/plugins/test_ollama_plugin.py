import asyncio

import httpx
import pytest
from fake_ollama import FakeOllama

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.plugins import EMBEDDER, LLM, ManifestError, PluginKind, PluginRegistry
from ldk_core.ports import ChatMessage, CompletionRequest
from ldk_core.testing.contracts import EmbedderContract, LLMProviderContract
from ldk_plugin_ollama import OllamaEmbedder, OllamaProvider, embedder_plugin, llm_plugin

HOST = "http://ollama.test:11434"


@pytest.fixture
def fake() -> FakeOllama:
    return FakeOllama()


class TestOllamaProviderContract(LLMProviderContract):
    @pytest.fixture
    def provider(self, fake: FakeOllama) -> OllamaProvider:
        return OllamaProvider(HOST, transport=fake.transport())

    @pytest.fixture
    def model(self) -> str:
        return "llama3.1"


class TestOllamaEmbedderContract(EmbedderContract):
    @pytest.fixture
    def embedder(self, fake: FakeOllama) -> OllamaEmbedder:
        return OllamaEmbedder(HOST, transport=fake.transport())


def _ask(*messages: ChatMessage, **kwargs) -> CompletionRequest:
    return CompletionRequest(model="llama3.1", messages=list(messages), **kwargs)


def test_single_user_message_uses_generate_with_the_old_defaults(fake: FakeOllama) -> None:
    provider = OllamaProvider(HOST, transport=fake.transport())
    text = asyncio.run(provider.complete(_ask(ChatMessage("user", "hi"))))
    assert text == "answer to: hi"
    path, body = fake.requests[-1]
    assert path == "/api/generate"
    assert body == {
        "model": "llama3.1",
        "prompt": "hi",
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 1024},
    }


def test_request_fields_and_extra_override_the_defaults(fake: FakeOllama) -> None:
    provider = OllamaProvider(HOST, transport=fake.transport())
    request = _ask(
        ChatMessage("user", "hi"), temperature=0.1, max_tokens=50, extra={"num_ctx": 8192}
    )
    asyncio.run(provider.complete(request))
    assert fake.requests[-1][1]["options"] == {
        "temperature": 0.1,
        "num_predict": 50,
        "num_ctx": 8192,
    }


def test_extra_options_pass_through_like_before(fake: FakeOllama) -> None:
    # llm-service forwards its request's "options" as extra.
    provider = OllamaProvider(HOST, transport=fake.transport())
    asyncio.run(provider.complete(_ask(ChatMessage("user", "hi"), extra={"temperature": 0.2})))
    assert fake.requests[-1][1]["options"] == {"temperature": 0.2, "num_predict": 1024}


def test_conversations_use_chat(fake: FakeOllama) -> None:
    provider = OllamaProvider(HOST, transport=fake.transport())
    request = _ask(ChatMessage("system", "be brief"), ChatMessage("user", "hi"))
    assert asyncio.run(provider.complete(request)) == "chat answer to: hi"
    path, body = fake.requests[-1]
    assert path == "/api/chat"
    assert body["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ]


def test_streaming_a_conversation(fake: FakeOllama) -> None:
    provider = OllamaProvider(HOST, transport=fake.transport())
    request = _ask(ChatMessage("assistant", "earlier"), ChatMessage("user", "go on"))

    async def collect() -> str:
        return "".join([d async for d in provider.stream(request)])

    assert asyncio.run(collect()) == "chat answer to: go on"


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def test_unreachable_host_is_upstream_unavailable() -> None:
    provider = OllamaProvider(HOST, transport=httpx.MockTransport(_down))
    with pytest.raises(ServiceError) as info:
        asyncio.run(provider.list_models())
    assert info.value.code is ErrorCode.UPSTREAM_UNAVAILABLE
    assert info.value.status == 503
    assert info.value.message.startswith("Ollama unreachable:")


def test_unknown_model_is_a_502_with_ollamas_message(fake: FakeOllama) -> None:
    provider = OllamaProvider(HOST, transport=fake.transport())
    with pytest.raises(ServiceError) as info:
        asyncio.run(provider.complete(CompletionRequest("nope", [ChatMessage("user", "hi")])))
    assert info.value.status == 502
    assert "model 'nope' not found" in info.value.message


def test_an_error_line_mid_stream_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='{"response": "par", "done": false}\n{"error": "oom"}\n')

    provider = OllamaProvider(HOST, transport=httpx.MockTransport(handler))

    async def collect() -> list[str]:
        out: list[str] = []
        async for delta in provider.stream(_ask(ChatMessage("user", "hi"))):
            out.append(delta)
        return out

    with pytest.raises(ServiceError, match="oom"):
        asyncio.run(collect())


def test_embedder_knows_common_models_and_strips_tags(fake: FakeOllama) -> None:
    embedder = OllamaEmbedder(HOST, model="all-minilm:latest", transport=fake.transport())
    assert embedder.dimension == 384
    assert len(asyncio.run(embedder.embed(["x"]))[0]) == 384


def test_embedder_refuses_an_unknown_model_without_a_dimension() -> None:
    with pytest.raises(ValueError, match="set EMBEDDING_DIMENSION"):
        OllamaEmbedder(HOST, model="my-custom-embedder")
    assert OllamaEmbedder(HOST, model="my-custom-embedder", dimension=512).dimension == 512


def test_embedder_rejects_vectors_of_the_wrong_length(fake: FakeOllama) -> None:
    fake.wrong_dimension = True
    embedder = OllamaEmbedder(HOST, transport=fake.transport())
    with pytest.raises(ServiceError, match="returned 767 dimensions, expected 768"):
        asyncio.run(embedder.embed(["x"]))


def test_plugins_build_through_the_registry() -> None:
    registry = PluginRegistry()
    registry.register(llm_plugin)
    registry.register(embedder_plugin)
    registry.configure(PluginKind.LLM, "ollama", {"host": HOST})
    registry.configure(PluginKind.EMBEDDER, "ollama", {"host": HOST, "model": "bge-m3"})
    assert isinstance(registry.get(LLM, "ollama"), OllamaProvider)
    embedder = registry.get(EMBEDDER, "ollama")
    assert (embedder.model, embedder.dimension) == ("bge-m3", 1024)
    with pytest.raises(ManifestError, match="host"):
        registry.configure(PluginKind.LLM, "ollama", {"hots": HOST})
    asyncio.run(registry.aclose())
