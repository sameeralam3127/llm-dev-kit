from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Dev Kit"
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    cache_ttl: int = Field(default=3600, alias="CACHE_TTL")
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8000, alias="CHROMA_PORT")
    default_chat_model: str = Field(default="llama3.1", alias="DEFAULT_CHAT_MODEL")
    default_embedding_model: str = Field(default="nomic-embed-text", alias="DEFAULT_EMBEDDING_MODEL")
    request_timeout_seconds: int = Field(default=60, alias="REQUEST_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
