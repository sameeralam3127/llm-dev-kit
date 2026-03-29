import redis
import os
import hashlib

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))


# ------------------ REDIS CLIENT ------------------

def get_redis_client():
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        client.ping()
        print("Redis connected")
        return client
    except Exception as e:
        print(f"Redis not available: {e}")
        return None


r = get_redis_client()


# ------------------ KEY GENERATION ------------------

def make_key(prompt, model=None):
    """
    Cache key based ONLY on:
    - prompt
    - model

    Do NOT include context → avoids mismatch
    """
    raw = f"{prompt.strip()}::{model}"
    return hashlib.md5(raw.encode()).hexdigest()


# ------------------ CACHE GET ------------------

def get_cached(prompt, model=None):
    if not r:
        print("CACHE SKIP (Redis unavailable)")
        return None

    try:
        key = make_key(prompt, model)
        value = r.get(key)

        if value:
            print(f"CACHE HIT: {key}")
        else:
            print(f"CACHE MISS: {key}")

        return value

    except Exception as e:
        print(f"Cache read error: {e}")
        return None


# ------------------ CACHE SET ------------------

def set_cache(prompt, response, model=None):
    if not r:
        return

    try:
        key = make_key(prompt, model)
        r.setex(key, CACHE_TTL, response)
        print(f"CACHE SET: {key}")
    except Exception as e:
        print(f"Cache write error: {e}")