"""Settings for the ingest-worker."""

import socket

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from ldk_core.config import CoreSettings


class Settings(CoreSettings):
    """ingest-worker configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", frozen=True, env_ignore_empty=True
    )

    database_url: str = Field(alias="DATABASE_URL")
    model_gateway_url: str = Field(default="http://model-gateway:8010", alias="MODEL_GATEWAY_URL")
    #: The worker's own credential for model-gateway (a service, not a user).
    model_gateway_token: SecretStr = Field(alias="MODEL_GATEWAY_TOKEN")
    embed_model: str = Field(default="nomic-embed-text", alias="EMBED_MODEL")
    #: Must match ``core.chunks.embedding vector(768)``.
    embed_dimension: int = Field(default=768, alias="EMBED_DIMENSION")
    embed_batch_size: int = Field(default=32, gt=0, alias="EMBED_BATCH_SIZE")
    worker_id: str = Field(default_factory=socket.gethostname, alias="WORKER_ID")
    #: A claimed job not finished within this long is assumed abandoned.
    lease_seconds: float = Field(default=900, gt=0, alias="LEASE_SECONDS")
    poll_seconds: float = Field(default=2, gt=0, alias="POLL_SECONDS")
