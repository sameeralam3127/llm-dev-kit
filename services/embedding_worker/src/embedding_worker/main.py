import asyncio
import json
import logging
import time
from typing import Any

import httpx

from devkit_common.config import Settings, get_settings
from devkit_common.events import (
    DocsChangedEvent,
    DocsFailedEvent,
    DocsIndexedEvent,
    DocumentEventType,
)
from devkit_common.github_client import HttpGitHubClient
from devkit_common.interfaces import (
    Cache,
    EmbeddingClient,
    EventBus,
    GitHubClient,
    VectorStore,
)
from devkit_common.kafka_bus import JsonKafkaConsumer, KafkaEventBus
from devkit_common.qdrant_store import QdrantVectorStore
from devkit_common.redis_cache import RedisCache
from embedding_worker.chunking import chunk_markdown

logger = logging.getLogger(__name__)


def log_json(message: str, **fields: Any) -> None:
    logger.info(json.dumps({"message": message, **fields}, default=str))


class LlmServiceEmbeddingClient:
    """Embeds via the llm-service HTTP API (which uses the local Ollama model)."""

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        res = await self._client.post("/embed", json={"texts": texts})
        res.raise_for_status()
        return res.json()["embeddings"]

    async def close(self) -> None:
        await self._client.aclose()


async def process_embedding_event(
    event: DocsChangedEvent,
    *,
    github: GitHubClient,
    vector_store: VectorStore,
    embedding_client: EmbeddingClient,
    event_bus: EventBus,
    cache: Cache | None,
    settings: Settings,
    kafka_context: dict[str, Any] | None = None,
) -> None:
    started = time.perf_counter()
    log_fields = {
        "repo": event.repo,
        "branch": event.branch,
        "path": event.path,
        "commit": event.commit,
        **(kafka_context or {}),
    }

    try:
        if event.event == DocumentEventType.REMOVED:
            await vector_store.delete_by_repo_path(repo=event.repo, path=event.path)
            log_json("docs.deleted", **log_fields)
            return

        owner = event.owner or settings.github_default_owner
        if not owner:
            raise ValueError("GitHub owner is required for document download")

        duplicate_key = f"github:processed:{event.event_id}"
        if cache and await cache.get(duplicate_key):
            log_json("docs.event.duplicate", **log_fields)
            return

        cache_key = (
            f"github:raw:{owner}:{event.repo}:{event.branch}:"
            f"{event.commit}:{event.path}"
        )
        markdown = await cache.get(cache_key) if cache else None
        if markdown is None:
            markdown = await github.download_markdown(
                owner, event.repo, event.path, event.branch
            )
            if cache:
                await cache.set(cache_key, markdown, ttl=settings.github_cache_ttl)

        chunks = chunk_markdown(markdown, path=event.path)
        embeddings = await embedding_client.embed_many([chunk.text for chunk in chunks])
        metadata = [
            {
                "repo": event.repo,
                "owner": owner,
                "branch": event.branch,
                "path": event.path,
                "title": chunk.title,
                "url": str(event.url) if event.url else "",
                "commit": event.commit,
                "chunk_id": chunk.chunk_id,
                "source": "github",
            }
            for chunk in chunks
        ]
        # Drop chunks from previous revisions of this file before writing the
        # new ones, so edits never leave stale vectors behind.
        await vector_store.delete_by_repo_path(repo=event.repo, path=event.path)
        await vector_store.upsert_documents(
            [chunk.text for chunk in chunks], embeddings, metadata
        )
        await event_bus.publish(
            settings.kafka_topic_docs_indexed,
            DocsIndexedEvent(
                repo=event.repo,
                branch=event.branch,
                path=event.path,
                commit=event.commit,
                chunk_count=len(chunks),
            ),
            key=event.path,
        )
        if cache:
            await cache.set(duplicate_key, "1", ttl=settings.github_cache_ttl)
        log_json(
            "docs.indexed",
            duration=round(time.perf_counter() - started, 4),
            chunks=len(chunks),
            **log_fields,
        )
    except Exception as exc:
        # Publish the failure and keep consuming; re-raising here would put the
        # worker in a crash/restart loop on a single poison message.
        await event_bus.publish(
            settings.kafka_topic_docs_failed,
            DocsFailedEvent(
                repo=event.repo,
                branch=event.branch,
                path=event.path,
                commit=event.commit,
                error=str(exc),
            ),
            key=event.path,
        )
        log_json(
            "docs.failed",
            duration=round(time.perf_counter() - started, 4),
            error=str(exc),
            **log_fields,
        )


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    consumer = JsonKafkaConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.kafka_topic_docs_changed,
        group_id="embedding-workers",
    )
    github = HttpGitHubClient.from_settings(settings)
    vector_store = QdrantVectorStore.from_settings(settings)
    embedding_client = LlmServiceEmbeddingClient(settings.llm_service_url)
    event_bus = KafkaEventBus.from_settings(settings)
    cache = RedisCache.from_settings(settings)

    try:
        async for payload, context in consumer.messages():
            try:
                event = DocsChangedEvent.model_validate(payload)
            except Exception as exc:
                log_json("docs.event.invalid", error=str(exc), payload=str(payload)[:500])
                await consumer.commit()
                continue
            await process_embedding_event(
                event,
                github=github,
                vector_store=vector_store,
                embedding_client=embedding_client,
                event_bus=event_bus,
                cache=cache,
                settings=settings,
                kafka_context=context,
            )
            await consumer.commit()
    finally:
        await consumer.stop()
        await event_bus.close()
        await embedding_client.close()
        await github.close()
        await cache.close()


if __name__ == "__main__":
    asyncio.run(run())
