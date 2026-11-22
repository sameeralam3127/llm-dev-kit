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

    # Authentication. The web app is the identity service: it signs short-lived
    # access tokens and exchanges personal API keys for them. These services
    # verify every caller themselves and never trust the gateway.
    auth_jwks_url: str = Field(
        default="http://web:3000/.well-known/jwks.json", alias="AUTH_JWKS_URL"
    )
    auth_token_url: str = Field(
        default="http://web:3000/api/identity/token", alias="AUTH_TOKEN_URL"
    )
    auth_issuer: str = Field(default="llm-dev-kit-web", alias="AUTH_ISSUER")
    auth_audience: str = Field(default="llm-dev-kit", alias="AUTH_AUDIENCE")
    # Optional: also accept tokens from an OIDC issuer directly (e.g. Keycloak).
    auth_oidc_issuer: str | None = Field(default=None, alias="AUTH_OIDC_ISSUER")
    auth_oidc_discovery_url: str | None = Field(default=None, alias="AUTH_OIDC_DISCOVERY_URL")
    auth_oidc_audience: str = Field(default="llm-dev-kit", alias="AUTH_OIDC_AUDIENCE")
    auth_oidc_roles_claim: str = Field(default="realm_access.roles", alias="AUTH_OIDC_ROLES_CLAIM")
    # Pre-v2 behaviour: no credential means full access. Removed in 2.0.0, and
    # refused at startup unless the gateway listens on loopback only.
    allow_legacy_anonymous: bool = Field(default=False, alias="ALLOW_LEGACY_ANONYMOUS")
    # The interface the gateway publishes on, as docker compose sets it.
    gateway_bind: str = Field(default="127.0.0.1", alias="GATEWAY_BIND")
    # mcp-service's own credential, a personal API key (sk-ldk-...).
    ldk_api_key: str | None = Field(default=None, alias="LDK_API_KEY", repr=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings(Settings)
