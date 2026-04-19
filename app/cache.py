"""
Redis Cache Module
Handles response caching to improve performance
"""
import redis
import os
import hashlib
from typing import Optional

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))  # 1 hour default

# Redis client instance
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get or create Redis client with connection pooling
    
    Returns:
        Redis client instance or None if connection fails
    """
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
            health_check_interval=30
        )
        # Test connection
        _redis_client.ping()
        print(f"✅ Redis connected at {REDIS_HOST}:{REDIS_PORT}")
        return _redis_client
    except Exception as e:
        print(f"⚠️  Redis not available: {e}")
        print("💡 Cache will be disabled")
        return None


def generate_cache_key(prompt: str, model: str) -> str:
    """
    Generate a unique cache key based on prompt and model
    
    Args:
        prompt: User prompt
        model: Model name
    
    Returns:
        MD5 hash of the combined input
    """
    raw_key = f"{prompt.strip()}::{model}"
    return hashlib.md5(raw_key.encode()).hexdigest()


def get_cached_response(prompt: str, model: str) -> Optional[str]:
    """
    Retrieve cached response if available
    
    Args:
        prompt: User prompt
        model: Model name
    
    Returns:
        Cached response or None
    """
    client = get_redis_client()
    
    if not client:
        return None
    
    try:
        key = generate_cache_key(prompt, model)
        value = client.get(key)
        
        if value:
            print(f"✅ CACHE HIT: {key[:16]}...")
            return value
        else:
            print(f"❌ CACHE MISS: {key[:16]}...")
            return None
    
    except Exception as e:
        print(f"⚠️  Cache read error: {e}")
        return None


def set_cached_response(
    prompt: str,
    response: str,
    model: str,
    ttl: Optional[int] = None
) -> bool:
    """
    Store response in cache
    
    Args:
        prompt: User prompt
        response: Model response
        model: Model name
        ttl: Time to live in seconds (uses default if None)
    
    Returns:
        True if successful, False otherwise
    """
    client = get_redis_client()
    
    if not client:
        return False
    
    try:
        key = generate_cache_key(prompt, model)
        cache_ttl = ttl or CACHE_TTL
        
        client.setex(key, cache_ttl, response)
        print(f"✅ CACHE SET: {key[:16]}... (TTL: {cache_ttl}s)")
        return True
    
    except Exception as e:
        print(f"⚠️  Cache write error: {e}")
        return False


def clear_cache() -> bool:
    """
    Clear all cached responses
    
    Returns:
        True if successful, False otherwise
    """
    client = get_redis_client()
    
    if not client:
        return False
    
    try:
        client.flushdb()
        print("✅ Cache cleared")
        return True
    except Exception as e:
        print(f"⚠️  Cache clear error: {e}")
        return False


def get_cache_stats() -> dict:
    """
    Get cache statistics
    
    Returns:
        Dictionary with cache stats
    """
    client = get_redis_client()
    
    if not client:
        return {"status": "unavailable"}
    
    try:
        info = client.info()
        return {
            "status": "connected",
            "keys": client.dbsize(),
            "memory_used": info.get("used_memory_human", "N/A"),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Made with Bob
