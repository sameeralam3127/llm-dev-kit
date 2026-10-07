import hashlib
from typing import cast

from redis.asyncio import Redis

from ldk_core.observability import get_logger

logger = get_logger(__name__)

CHAT_PREFIX = "chat:"


def make_key(prompt: str, model: str | None = None) -> str:
    raw = f"{prompt.strip()}::{model}"
    return CHAT_PREFIX + hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()


class ChatCache:
    """Redis-backed response cache.

    Best-effort by design: every Redis failure degrades to a cache miss or a
    no-op instead of failing the chat, and is logged as a warning.

    Keys are namespaced under "chat:" so clearing the chat cache never touches
    other tenants of the Redis instance (e.g. the GitHub sync worker's keys).
    """

    def __init__(self, redis_url: str, ttl: int) -> None:
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl

    async def get(self, prompt: str, model: str | None = None) -> str | None:
        try:
            # decode_responses=True, so redis returns str, not bytes
            return cast(str | None, await self.client.get(make_key(prompt, model)))
        except Exception as exc:  # noqa: BLE001 - never fail a chat over the cache
            _warn("get", exc)
            return None

    async def set(self, prompt: str, model: str | None, value: str) -> None:
        try:
            await self.client.setex(make_key(prompt, model), self.ttl, value)
        except Exception as exc:  # noqa: BLE001 - never fail a chat over the cache
            _warn("set", exc)

    async def clear(self) -> int:
        cleared = 0
        try:
            async for key in self.client.scan_iter(match=CHAT_PREFIX + "*"):
                await self.client.delete(key)
                cleared += 1
        except Exception as exc:  # noqa: BLE001 - report what was cleared so far
            _warn("clear", exc)
        return cleared

    async def stats(self) -> dict:
        try:
            keys = 0
            async for _ in self.client.scan_iter(match=CHAT_PREFIX + "*"):
                keys += 1
            return {"status": "connected", "keys": keys}
        except Exception as exc:  # noqa: BLE001 - stats report "offline" rather than fail
            _warn("stats", exc)
            return {"status": "offline", "keys": 0}

    async def close(self) -> None:
        await self.client.aclose()


def _warn(operation: str, exc: Exception) -> None:
    logger.warning("cache unavailable", operation=operation, error=f"{type(exc).__name__}: {exc}")
