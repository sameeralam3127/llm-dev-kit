import asyncio
import json
import logging
import time
from typing import Any

from app.cache.redis import RedisCache
from app.config import Settings, get_settings
from app.github.client import HttpGitHubClient
from app.interfaces import Cache, EmbeddingProvider, EventBus, GitHubClient, VectorStore
from app.kafka.consumer import JsonKafkaConsumer
from app.kafka.producer import KafkaEventBus
from app.models.events import (
    DocsChangedEvent,
    DocsFailedEvent,
    DocsIndexedEvent,
    DocumentEventType,
)
from app.services.chunk_service import chunk_markdown
from app.services.embedding_service import OllamaEmbeddingProvider
from app.vectorstore.qdrant import QdrantVectorStore
from app.workers.delete_worker import process_delete_event


logger = logging.getLogger(__name__)


def log_json(message: str, **fields: Any) -> None:
    logger.info(json.dumps({"message": message, **fields}, default=str))


async def process_embedding_event(
    event: DocsChangedEvent,
    *,
    github: GitHubClient,
    vector_store: VectorStore,
    embedding_provider: EmbeddingProvider,
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
            await process_delete_event(event, vector_store=vector_store)
            return

        owner = event.owner or settings.github_default_owner
        if not owner:
            raise ValueError("GitHub owner is required for document download")

        duplicate_key = f"github:processed:{event.event_id}"
        if cache and await cache.get(duplicate_key):
            log_json("docs.event.duplicate", **log_fields)
            return

        cache_key = f"github:raw:{owner}:{event.repo}:{event.branch}:{event.path}"
        markdown = await cache.get(cache_key) if cache else None
        if markdown is None:
            markdown = await github.download_markdown(
                owner, event.repo, event.path, event.branch
            )
            if cache:
                await cache.set(cache_key, markdown, ttl=settings.github_cache_ttl)

        chunks = chunk_markdown(markdown, path=event.path)
        embeddings = await embedding_provider.embed_many([chunk.text for chunk in chunks])
        metadata = [
            {
                "repo": event.repo,
                "owner": event.owner or settings.github_default_owner or "",
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
        raise


async def run() -> None:
    settings = get_settings()
    consumer = JsonKafkaConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.kafka_topic_docs_changed,
        group_id="embedding-workers",
    )
    github = HttpGitHubClient.from_settings(settings)
    vector_store = QdrantVectorStore.from_settings(settings)
    embeddings = OllamaEmbeddingProvider()
    event_bus = KafkaEventBus.from_settings(settings)
    cache = RedisCache.from_settings(settings)

    async for payload, context in consumer.messages():
        event = DocsChangedEvent.model_validate(payload)
        await process_embedding_event(
            event,
            github=github,
            vector_store=vector_store,
            embedding_provider=embeddings,
            event_bus=event_bus,
            cache=cache,
            settings=settings,
            kafka_context=context,
        )
        await consumer.commit()


if __name__ == "__main__":
    asyncio.run(run())
