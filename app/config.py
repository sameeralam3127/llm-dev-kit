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
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_topic_docs_changed: str = Field(
        default="docs.changed", alias="KAFKA_TOPIC_DOCS_CHANGED"
    )
    kafka_topic_docs_indexed: str = Field(
        default="docs.indexed", alias="KAFKA_TOPIC_DOCS_INDEXED"
    )
    kafka_topic_docs_failed: str = Field(
        default="docs.failed", alias="KAFKA_TOPIC_DOCS_FAILED"
    )
    kafka_topic_cache_invalidate: str = Field(
        default="cache.invalidate", alias="KAFKA_TOPIC_CACHE_INVALIDATE"
    )
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    github_webhook_secret: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET")
    github_default_owner: str | None = Field(default=None, alias="GITHUB_DEFAULT_OWNER")
    github_default_repo: str | None = Field(default=None, alias="GITHUB_DEFAULT_REPO")
    github_default_branch: str = Field(default="main", alias="GITHUB_DEFAULT_BRANCH")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_collection: str = Field(
        default="github_documents", alias="QDRANT_COLLECTION"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    github_cache_ttl: int = Field(default=600, alias="GITHUB_CACHE_TTL")
    retriever_score_threshold: float = Field(
        default=0.72, alias="RETRIEVER_SCORE_THRESHOLD"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
