"""A real Postgres with pgvector for the v3 services' tests, via testcontainers.

One container per test session, shared by core-api's and model-gateway's
tests; each test gets a freshly migrated database, so tests cannot leak rows
into each other. Skipped when Docker is not running.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from postgres import IMAGE, alembic_config


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
