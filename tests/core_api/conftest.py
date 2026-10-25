"""Fixtures for core-api's tests. The Postgres ones are in ``tests/conftest.py``."""

import pytest


@pytest.fixture
def issuer():
    """Signs session tokens the way the web app does."""
    from identity import Issuer

    return Issuer()


@pytest.fixture
def embedder():
    """The embedder core-api uses for questions (a deterministic fake)."""
    from core_api_helpers import FakeEmbedder

    return FakeEmbedder()


@pytest.fixture
def model_client():
    """The model-gateway client core-api uses (a fake that records requests)."""
    from core_api_helpers import FakeModelClient

    return FakeModelClient()


@pytest.fixture
def app(db_url, issuer, embedder, model_client):
    """core-api against the migrated test database."""
    from core_api_helpers import PEPPER

    from core_api.config import Settings
    from core_api.main import create_app

    settings = Settings(
        DATABASE_URL=db_url,
        API_KEY_PEPPER=PEPPER,
        MODEL_GATEWAY_TOKEN="svc-token",
        LOG_FORMAT="console",
    )
    return create_app(settings, sessions=issuer.provider(), embedder=embedder, models=model_client)


@pytest.fixture
def client(app):
    """An HTTP client for ``app``, with its lifespan running."""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
