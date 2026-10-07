import asyncio
from typing import Any

import pytest
from fake_litellm import FakeLiteLLM, UpstreamError

import ldk_plugin_litellm.provider as provider_module
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.plugins import LLM, PluginKind, PluginRegistry
from ldk_core.ports import ChatMessage, CompletionRequest
from ldk_core.testing.contracts import LLMProviderContract
from ldk_plugin_litellm import LiteLLMProvider, anthropic_plugin, gemini_plugin, openai_plugin


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeLiteLLM:
    fake = FakeLiteLLM()
    monkeypatch.setattr(provider_module.litellm, "acompletion", fake.acompletion)
    return fake


class TestLiteLLMContract(LLMProviderContract):
    @pytest.fixture
    def provider(self, fake: FakeLiteLLM) -> LiteLLMProvider:
        return LiteLLMProvider("openai", "sk-server")

    @pytest.fixture
    def model(self) -> str:
        return "gpt-4o"


def _ask(**kwargs: Any) -> CompletionRequest:
    return CompletionRequest(model="gpt-4o", messages=[ChatMessage("user", "hi")], **kwargs)


def test_call_matches_the_previous_provider(fake: FakeLiteLLM) -> None:
    provider = LiteLLMProvider("openai", "sk-server", base_url="https://proxy.test/v1")
    asyncio.run(provider.complete(_ask()))
    assert fake.calls[-1] == {
        "model": "openai/gpt-4o",
        "messages": [{"role": "user", "content": "hi"}],
        "api_key": "sk-server",
        "temperature": 0.7,
        "timeout": 120,
        "api_base": "https://proxy.test/v1",
    }


def test_options_from_extra_and_request(fake: FakeLiteLLM) -> None:
    provider = LiteLLMProvider("anthropic", "k")
    asyncio.run(
        provider.complete(
            CompletionRequest(
                "claude-sonnet-5",
                [ChatMessage("user", "hi")],
                extra={"temperature": 0.2, "max_tokens": 64},
            )
        )
    )
    assert (fake.calls[-1]["temperature"], fake.calls[-1]["max_tokens"]) == (0.2, 64)
    assert "api_base" not in fake.calls[-1]


def test_request_key_wins_over_server_key(fake: FakeLiteLLM) -> None:
    asyncio.run(LiteLLMProvider("openai", "sk-server").complete(_ask(api_key="sk-user")))
    assert fake.calls[-1]["api_key"] == "sk-user"


def test_missing_key_is_unauthorized_with_guidance(fake: FakeLiteLLM) -> None:
    with pytest.raises(ServiceError) as info:
        asyncio.run(LiteLLMProvider("gemini", None).complete(_ask()))
    assert info.value.code is ErrorCode.UNAUTHORIZED
    assert "GEMINI_API_KEY" in info.value.message
    assert fake.calls == []


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, ErrorCode.UNAUTHORIZED),
        (429, ErrorCode.RATE_LIMITED),
        (400, ErrorCode.INVALID_REQUEST),
        (500, ErrorCode.UPSTREAM_ERROR),
        (None, ErrorCode.UPSTREAM_ERROR),
    ],
)
def test_upstream_errors_map_by_status(fake: FakeLiteLLM, status, code) -> None:
    fake.fail_with = UpstreamError("quota exceeded", status)
    with pytest.raises(ServiceError) as info:
        asyncio.run(LiteLLMProvider("openai", "k").complete(_ask()))
    assert info.value.code is code
    assert info.value.message == "openai error: quota exceeded"


def test_stream_errors_are_service_errors(fake: FakeLiteLLM) -> None:
    fake.fail_with = UpstreamError("overloaded", 529)

    async def collect() -> list[str]:
        return [d async for d in LiteLLMProvider("anthropic", "k").stream(_ask())]

    with pytest.raises(ServiceError) as info:
        asyncio.run(collect())
    assert info.value.code is ErrorCode.UPSTREAM_ERROR


def test_telemetry_is_off() -> None:
    assert provider_module.litellm.telemetry is False


def test_three_plugins_one_class() -> None:
    registry = PluginRegistry()
    for plugin in (openai_plugin, gemini_plugin, anthropic_plugin):
        registry.register(plugin)
    registry.configure(PluginKind.LLM, "openai", {"api_key": "k", "base_url": None})
    assert registry.names(LLM) == ["anthropic", "gemini", "openai"]
    for name in registry.names(LLM):
        provider = registry.get(LLM, name)
        assert isinstance(provider, LiteLLMProvider)
        assert provider.name == name
    models = asyncio.run(registry.get(LLM, "anthropic").list_models())
    assert "claude-sonnet-5" in models
