"""Alembic configuration for the `core` schema, for tests that migrate a database."""

from alembic.config import Config

IMAGE = "pgvector/pgvector:0.8.1-pg16"


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", "core_api:migrations")
    config.set_main_option("sqlalchemy.url", url)
    return config
