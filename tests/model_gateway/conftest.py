"""Fixtures for model-gateway's tests. The Postgres ones are in ``tests/conftest.py``."""

import pytest


@pytest.fixture
def ollama():
    """A fake Ollama with one local model and one that runs on ollama.com."""
    from fake_ollama import FakeOllama

    return FakeOllama(models=("llama3.1", "gpt-oss:120b-cloud"))


@pytest.fixture
def cloud():
    """A cloud provider that records calls; sovereign mode must never reach it."""
    from gateway_helpers import FakeCloud

    return FakeCloud("openai")


@pytest.fixture
def gateway(db_url, ollama, cloud):
    """Build a gateway app: ``gateway(sovereign=..., audit=..., **env)``.

    The cloud fake is passed in even in sovereign mode, so tests prove the
    policy refuses egress rather than relying on the plugin not being loaded.
    """
    from gateway_helpers import CORE_TOKEN, WORKER_TOKEN

    from ldk_plugin_ollama import OllamaEmbedder, OllamaProvider
    from model_gateway.config import Settings
    from model_gateway.main import create_app

    def build(*, sovereign=True, audit=None, llms=None, **env):
        settings = Settings(
            DATABASE_URL=db_url,
            SOVEREIGN_MODE=sovereign,
            CORE_API_TOKEN=CORE_TOKEN,
            INGEST_WORKER_TOKEN=WORKER_TOKEN,
            LOG_FORMAT="console",
            **env,
        )
        local = OllamaProvider("http://ollama.test", transport=ollama.transport())
        embedder = OllamaEmbedder(
            "http://ollama.test", model="nomic-embed-text", transport=ollama.transport()
        )
        return create_app(
            settings,
            llms=llms if llms is not None else {"ollama": local, "openai": cloud},
            embedder=embedder,
            audit=audit,
        )

    return build


@pytest.fixture
def client(gateway):
    """A client for the default (sovereign) gateway, with its lifespan running."""
    from fastapi.testclient import TestClient

    with TestClient(gateway()) as c:
        yield c
