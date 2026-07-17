import hashlib

from redis.asyncio import Redis

CHAT_PREFIX = "chat:"


def make_key(prompt: str, model: str | None = None) -> str:
    raw = f"{prompt.strip()}::{model}"
    return CHAT_PREFIX + hashlib.md5(raw.encode()).hexdigest()


class ChatCache:
    """Redis-backed response cache.

    Keys are namespaced under "chat:" so clearing the chat cache never touches
    other tenants of the Redis instance (e.g. the GitHub sync worker's keys).
    """

    def __init__(self, redis_url: str, ttl: int) -> None:
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl

    async def get(self, prompt: str, model: str | None = None) -> str | None:
        try:
            return await self.client.get(make_key(prompt, model))
        except Exception:
            return None

    async def set(self, prompt: str, model: str | None, value: str) -> None:
        try:
            await self.client.setex(make_key(prompt, model), self.ttl, value)
        except Exception:
            pass

    async def clear(self) -> int:
        cleared = 0
        try:
            async for key in self.client.scan_iter(match=CHAT_PREFIX + "*"):
                await self.client.delete(key)
                cleared += 1
        except Exception:
            pass
        return cleared

    async def stats(self) -> dict:
        try:
            keys = 0
            async for _ in self.client.scan_iter(match=CHAT_PREFIX + "*"):
                keys += 1
            return {"status": "connected", "keys": keys}
        except Exception:
            return {"status": "offline", "keys": 0}

    async def close(self) -> None:
        await self.client.aclose()
