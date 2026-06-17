import hashlib

import redis

from app.config import get_settings


settings = get_settings()


def get_redis_client() -> redis.Redis | None:
    try:
        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        client.ping()
        return client
    except Exception as exc:
        print(f"Redis not available: {exc}")
        return None


r = get_redis_client()


def make_key(prompt: str, model: str | None = None) -> str:
    raw = f"{prompt.strip()}::{model}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached(prompt: str, model: str | None = None) -> str | None:
    if not r:
        return None

    try:
        return r.get(make_key(prompt, model))
    except Exception as exc:
        print(f"Cache read error: {exc}")
        return None


def set_cache(prompt: str, response: str, model: str | None = None) -> None:
    if not r:
        return

    try:
        r.setex(make_key(prompt, model), settings.cache_ttl, response)
    except Exception as exc:
        print(f"Cache write error: {exc}")


def clear_cache() -> bool:
    if not r:
        return False

    try:
        r.flushdb()
        return True
    except Exception as exc:
        print(f"Cache clear error: {exc}")
        return False


def get_cache_stats() -> dict:
    if not r:
        return {"status": "offline", "keys": 0}

    try:
        return {"status": "connected", "keys": r.dbsize()}
    except Exception as exc:
        print(f"Cache stats error: {exc}")
        return {"status": "error", "keys": 0}
