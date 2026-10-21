"""Settings for core-api, from the environment (Docker secrets arrive in step g)."""

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from ldk_core.config import CoreSettings


class Settings(CoreSettings):
    """core-api configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", frozen=True, env_ignore_empty=True
    )

    #: libpq URL, e.g. postgresql://core_api:...@postgres:5432/llm_dev_kit
    database_url: str = Field(alias="DATABASE_URL")
    #: Server-side secret mixed into every API-key hash. Never stored in the database.
    api_key_pepper: SecretStr = Field(alias="API_KEY_PEPPER", min_length=32)

    # The web app is the identity issuer (decision 2); these find and check its tokens.
    auth_jwks_url: str = Field(
        default="http://web:3000/.well-known/jwks.json", alias="AUTH_JWKS_URL"
    )
    auth_token_url: str = Field(
        default="http://web:3000/api/identity/token", alias="AUTH_TOKEN_URL"
    )
    auth_issuer: str = Field(default="llm-dev-kit-web", alias="AUTH_ISSUER")
    auth_audience: str = Field(default="llm-dev-kit", alias="AUTH_AUDIENCE")

    # model-gateway is the only path to a model (architecture decision 3).
    model_gateway_url: str = Field(default="http://model-gateway:8010", alias="MODEL_GATEWAY_URL")
    #: core-api's own service credential for model-gateway.
    model_gateway_token: SecretStr = Field(alias="MODEL_GATEWAY_TOKEN")
    default_chat_model: str = Field(default="llama3.1", alias="DEFAULT_CHAT_MODEL")
    embed_model: str = Field(default="nomic-embed-text", alias="EMBED_MODEL")
    embed_dimension: int = Field(default=768, alias="EMBED_DIMENSION")
    #: Candidates from each search before fusion, and chunks given to the model.
    retrieval_top_k: int = Field(default=20, gt=0, alias="RETRIEVAL_TOP_K")
    context_chunks: int = Field(default=5, gt=0, alias="CONTEXT_CHUNKS")
