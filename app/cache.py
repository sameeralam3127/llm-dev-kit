import redis
import os
import hashlib

r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379)

def make_key(text):
    return hashlib.md5(text.encode()).hexdigest()

def get_cached(prompt):
    key = make_key(prompt)
    val = r.get(key)
    return val.decode() if val else None

def set_cache(prompt, response):
    key = make_key(prompt)
    r.set(key, response)