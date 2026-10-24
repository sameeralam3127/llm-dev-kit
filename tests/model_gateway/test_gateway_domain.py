"""model-gateway's pure rules: routing, egress, service tokens and settings."""

import pytest
from gateway_helpers import CLOUD_KEY, CORE_TOKEN, WORKER_TOKEN
from pydantic import ValidationError

from model_gateway.config import Settings
from model_gateway.domain.callers import core_api, identify, ingest_worker
from model_gateway.domain.egress import Route, is_ollama_cloud, route


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("llama3.1", Route("ollama", "llama3.1", egress=False)),
        ("llama3.1:8b-instruct-q4_K_M", Route("ollama", "llama3.1:8b-instruct-q4_K_M", False)),
        ("hf.co/org/model:Q4_K_M", Route("ollama", "hf.co/org/model:Q4_K_M", False)),
        ("openai/gpt-4o", Route("openai", "gpt-4o", egress=True)),
        ("anthropic/claude-sonnet-5", Route("anthropic", "claude-sonnet-5", egress=True)),
        ("gemini/gemini-2.5-flash", Route("gemini", "gemini-2.5-flash", egress=True)),
        # Ollama cloud models run on ollama.com.
        ("gpt-oss:120b-cloud", Route("ollama", "gpt-oss:120b-cloud", egress=True)),
        ("glm-4.6:cloud", Route("ollama", "glm-4.6:cloud", egress=True)),
        ("kimi-k2-cloud", Route("ollama", "kimi-k2-cloud", egress=True)),
        ("GPT-OSS:120B-CLOUD", Route("ollama", "GPT-OSS:120B-CLOUD", egress=True)),
        # An unknown prefix is a local model name; the local Ollama cannot
        # send it anywhere, it can only fail to find it.
        ("mistral/large", Route("ollama", "mistral/large", egress=False)),
    ],
)
def test_routes_and_classifies_egress(model, expected) -> None:
    assert route(model) == expected


def test_a_loaded_cloud_plugin_is_egress_too() -> None:
    assert route("mistral/large", cloud=["mistral"]) == Route("mistral", "large", egress=True)


def test_cloud_suffix_needs_the_whole_word() -> None:
    assert not is_ollama_cloud("cloudy-llama")
    assert not is_ollama_cloud("llama:cloudless")


def test_identifies_services_by_their_own_token() -> None:
    services = [core_api(CORE_TOKEN), ingest_worker(WORKER_TOKEN)]
    assert identify(CORE_TOKEN, services).name == "core-api"
    assert identify(WORKER_TOKEN, services).permissions == {"embed"}
    assert identify(CORE_TOKEN[:-1], services) is None
    assert identify("", services) is None
    assert identify(None, services) is None
    assert CORE_TOKEN not in repr(services)


def settings(**env) -> Settings:
    base = {
        "DATABASE_URL": "postgresql://unused",
        "CORE_API_TOKEN": CORE_TOKEN,
        "INGEST_WORKER_TOKEN": WORKER_TOKEN,
    }
    return Settings(**{**base, **env})


def test_sovereign_mode_is_on_by_default_and_ignores_cloud_keys() -> None:
    s = settings(OPENAI_API_KEY=CLOUD_KEY)
    assert s.sovereign_mode is True
    assert s.cloud_keys() == {}
    assert settings(SOVEREIGN_MODE=False, OPENAI_API_KEY=CLOUD_KEY).cloud_keys() == {
        "openai": CLOUD_KEY
    }


def test_refuses_unsafe_settings() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        settings(INGEST_WORKER_TOKEN=CORE_TOKEN)
    with pytest.raises(ValidationError, match="sovereign mode cannot use it"):
        settings(EMBED_MODEL="embeddinggemma:cloud")
    with pytest.raises(ValidationError):
        settings(CORE_API_TOKEN="too-short")
