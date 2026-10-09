from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ldk_core.config import CoreSettings, load_settings


class Settings(CoreSettings):
    """Settings shared by llm-, rag- and mcp-service.

    Inherits LOG_LEVEL and LOG_FORMAT from CoreSettings. Plugin-specific
    values are read here and handed to each plugin's configure() call, so a
    plugin never reads the environment itself.
    """

    # env_ignore_empty: compose passes unset optional variables as "", which
    # must mean "not set" rather than an invalid value.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", frozen=True, env_ignore_empty=True
    )

    app_name: str = "LLM Dev Kit"

    # Service mesh (internal URLs; overridden for local development)
    llm_service_url: str = Field(default="http://llm-service:8010", alias="LLM_SERVICE_URL")
    rag_service_url: str = Field(default="http://rag-service:8020", alias="RAG_SERVICE_URL")

    # Offline LLM runtime (Ollama)
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    default_chat_model: str = Field(default="llama3.1", alias="DEFAULT_CHAT_MODEL")
    default_embedding_model: str = Field(
        default="nomic-embed-text", alias="DEFAULT_EMBEDDING_MODEL"
    )
    # Needed only for embedding models the Ollama plugin does not already know.
    embedding_dimension: int | None = Field(default=None, gt=0, alias="EMBEDDING_DIMENSION")
    request_timeout_seconds: int = Field(default=120, gt=0, alias="REQUEST_TIMEOUT_SECONDS")

    # Cloud providers (optional — the stack is fully functional offline without them)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY", repr=False)
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY", repr=False)
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY", repr=False)
    anthropic_base_url: str = Field(default="https://api.anthropic.com", alias="ANTHROPIC_BASE_URL")

    # Cache
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    cache_ttl: int = Field(default=3600, alias="CACHE_TTL")

    # Vector store (PDF uploads)
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8000, alias="CHROMA_PORT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings(Settings)
