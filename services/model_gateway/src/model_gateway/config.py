"""Settings for model-gateway, from the environment (Docker secrets arrive in step g)."""

from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict

from ldk_core.config import CoreSettings
from model_gateway.domain.egress import is_ollama_cloud


class Settings(CoreSettings):
    """model-gateway configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", frozen=True, env_ignore_empty=True
    )

    #: Where audit events are written. Only ``INSERT`` on ``core.audit_events`` is needed.
    database_url: str = Field(alias="DATABASE_URL")
    #: On by default: nothing leaves the network unless an operator turns it off.
    sovereign_mode: bool = Field(default=True, alias="SOVEREIGN_MODE")

    # One credential per calling service, so each can be given only what it needs.
    core_api_token: SecretStr = Field(alias="CORE_API_TOKEN", min_length=32)
    ingest_worker_token: SecretStr = Field(alias="INGEST_WORKER_TOKEN", min_length=32)

    ollama_host: str = Field(default="http://ollama:11434", alias="OLLAMA_HOST")
    embed_model: str = Field(default="nomic-embed-text", alias="EMBED_MODEL")
    #: Must match ``core.chunks.embedding vector(768)``.
    embed_dimension: int = Field(default=768, alias="EMBED_DIMENSION")
    #: Most texts one ``POST /embed`` may carry; the worker sends 32 at a time.
    embed_max_texts: int = Field(default=256, gt=0, alias="EMBED_MAX_TEXTS")
    request_timeout_seconds: float = Field(default=300, gt=0, alias="REQUEST_TIMEOUT_SECONDS")

    # Cloud providers. Read only when SOVEREIGN_MODE=false; a provider without a key is off.
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.core_api_token.get_secret_value() == self.ingest_worker_token.get_secret_value():
            raise ValueError("CORE_API_TOKEN and INGEST_WORKER_TOKEN must differ")
        if self.sovereign_mode and is_ollama_cloud(self.embed_model):
            raise ValueError(
                f"EMBED_MODEL '{self.embed_model}' runs on ollama.com, not locally; "
                "sovereign mode cannot use it"
            )
        return self

    def cloud_keys(self) -> dict[str, str]:
        """Each cloud provider with a key, by registry name; empty in sovereign mode."""
        if self.sovereign_mode:
            return {}
        keys = {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "anthropic": self.anthropic_api_key,
        }
        return {name: key.get_secret_value() for name, key in keys.items() if key}
