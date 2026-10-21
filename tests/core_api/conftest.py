"""A real Postgres with pgvector for core-api's tests, via testcontainers.

One container per test session; each test gets a freshly migrated database,
so tests cannot leak rows into each other. Skipped when Docker is not running.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config

IMAGE = "pgvector/pgvector:0.8.1-pg16"


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[str]:
    try:
        from testcontainers.community.postgres import PostgresContainer

        container = PostgresContainer(IMAGE, driver=None)
        container.start()
    except Exception as exc:  # Docker missing or not running
        pytest.skip(f"needs Docker for a real Postgres: {exc}")
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", "core_api:migrations")
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def empty_db(postgres_server: str) -> Iterator[str]:
    """A brand-new, unmigrated database on the shared server."""
    name = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(postgres_server, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    base, _, _ = postgres_server.rpartition("/")
    yield f"{base}/{name}"
    with psycopg.connect(postgres_server, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def db_url(empty_db: str) -> str:
    """A database migrated to the latest revision."""
    command.upgrade(alembic_config(empty_db), "head")
    return empty_db


@pytest.fixture
def conn(db_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(db_url, autocommit=True) as connection:
        yield connection


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
