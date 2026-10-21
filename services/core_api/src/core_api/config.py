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
