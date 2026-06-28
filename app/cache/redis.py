from redis.asyncio import Redis

from app.config import Settings, get_settings


class RedisCache:
    def __init__(self, redis_url: str, default_ttl: int = 600) -> None:
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = default_ttl

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "RedisCache":
        settings = settings or get_settings()
        return cls(settings.redis_url, settings.github_cache_ttl)

    async def get(self, key: str) -> str | None:
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self.client.setex(key, ttl or self.default_ttl, value)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def close(self) -> None:
        await self.client.aclose()
