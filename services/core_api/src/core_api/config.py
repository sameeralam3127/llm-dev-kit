"""Settings for core-api, read from the environment (and Docker secrets later)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """core-api configuration.

    ``database_url`` is a libpq URL, e.g.
    ``postgresql://core_api:...@postgres:5432/llm_dev_kit``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    database_url: str = Field(alias="DATABASE_URL")
