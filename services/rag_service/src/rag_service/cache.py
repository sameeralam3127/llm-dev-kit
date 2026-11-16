import hashlib
from typing import cast

from redis.asyncio import Redis

from ldk_core.observability import get_logger

logger = get_logger(__name__)

CHAT_PREFIX = "chat:"
REVISION_KEY = CHAT_PREFIX + "rev"
"""Counter of the document set's revision. It lives under the chat prefix but is
not an answer: clear() and stats() skip it, so a clear never resets it."""


def make_key(prompt: str, model: str | None = None, revision: int = 0) -> str:
    raw = f"{prompt.strip()}::{model}"
    digest = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()
    return f"{CHAT_PREFIX}{revision}:{digest}"


class ChatCache:
    """Redis-backed response cache.

    Best-effort by design: every Redis failure degrades to a cache miss or a
    no-op instead of failing the chat, and is logged as a warning.

    Keys are namespaced under "chat:" so clearing the chat cache never touches
    other tenants of the Redis instance (e.g. the GitHub sync worker's keys).

    Every key also carries the document-set revision ("chat:{rev}:{md5}").
    Ingesting or clearing documents bumps the revision, which orphans every
    older answer at once (they expire by TTL), whoever made the change.

    In-flight answers: a caller reads revision() once when the question
    starts and passes it to get() and set(). An answer generated across an
    ingest is therefore stored under the old revision, which nobody reads
    again, and can never be served as an answer about the new documents.
    Called without a revision, get() and set() read it themselves.
    """

    def __init__(self, redis_url: str, ttl: int) -> None:
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl

    async def revision(self) -> int | None:
        """The current document-set revision, or None if Redis is unavailable."""
        try:
            value = await self.client.get(REVISION_KEY)
            return int(value) if value else 0
        except Exception as exc:  # noqa: BLE001 - never fail a chat over the cache
            _warn("revision", exc)
            return None

    async def bump_revision(self) -> None:
        try:
            await self.client.incr(REVISION_KEY)
        except Exception as exc:  # noqa: BLE001 - never fail an upload over the cache
            _warn("bump_revision", exc)

    async def get(
        self, prompt: str, model: str | None = None, *, revision: int | None = None
    ) -> str | None:
        if revision is None:
            revision = await self.revision()
        if revision is None:
            return None
        try:
            # decode_responses=True, so redis returns str, not bytes
            return cast(str | None, await self.client.get(make_key(prompt, model, revision)))
        except Exception as exc:  # noqa: BLE001 - never fail a chat over the cache
            _warn("get", exc)
            return None

    async def set(
        self, prompt: str, model: str | None, value: str, *, revision: int | None = None
    ) -> None:
        if revision is None:
            revision = await self.revision()
        if revision is None:
            return
        try:
            await self.client.setex(make_key(prompt, model, revision), self.ttl, value)
        except Exception as exc:  # noqa: BLE001 - never fail a chat over the cache
            _warn("set", exc)

    async def clear(self) -> int:
        cleared = 0
        try:
            async for key in self.client.scan_iter(match=CHAT_PREFIX + "*"):
                if key == REVISION_KEY:
                    continue
                await self.client.delete(key)
                cleared += 1
        except Exception as exc:  # noqa: BLE001 - report what was cleared so far
            _warn("clear", exc)
        return cleared

    async def stats(self) -> dict:
        try:
            keys = 0
            async for key in self.client.scan_iter(match=CHAT_PREFIX + "*"):
                if key != REVISION_KEY:
                    keys += 1
            return {"status": "connected", "keys": keys}
        except Exception as exc:  # noqa: BLE001 - stats report "offline" rather than fail
            _warn("stats", exc)
            return {"status": "offline", "keys": 0}

    async def close(self) -> None:
        await self.client.aclose()


def _warn(operation: str, exc: Exception) -> None:
    logger.warning("cache unavailable", operation=operation, error=f"{type(exc).__name__}: {exc}")
