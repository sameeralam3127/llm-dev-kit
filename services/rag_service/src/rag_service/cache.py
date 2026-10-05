import hashlib
from typing import cast

from redis.asyncio import Redis

CHAT_PREFIX = "chat:"


def make_key(prompt: str, model: str | None = None) -> str:
    raw = f"{prompt.strip()}::{model}"
    return CHAT_PREFIX + hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()


class ChatCache:
    """Redis-backed response cache.

    Best-effort by design: every Redis failure degrades to a cache miss or a
    no-op instead of failing the chat. Logging those failures is #11.

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
        except Exception:  # noqa: BLE001
            return None

    async def set(self, prompt: str, model: str | None, value: str) -> None:
        try:  # noqa: SIM105 - kept symmetric with get/clear until #11
            await self.client.setex(make_key(prompt, model), self.ttl, value)
        except Exception:  # noqa: BLE001, S110
            pass

    async def clear(self) -> int:
        cleared = 0
        try:
            async for key in self.client.scan_iter(match=CHAT_PREFIX + "*"):
                await self.client.delete(key)
                cleared += 1
        except Exception:  # noqa: BLE001, S110
            pass
        return cleared

    async def stats(self) -> dict:
        try:
            keys = 0
            async for _ in self.client.scan_iter(match=CHAT_PREFIX + "*"):
                keys += 1
            return {"status": "connected", "keys": keys}
        except Exception:  # noqa: BLE001
            return {"status": "offline", "keys": 0}

    async def close(self) -> None:
        await self.client.aclose()
