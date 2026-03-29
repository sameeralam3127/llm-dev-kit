import redis
import os

r = redis.Redis(host=os.getenv("REDIS_HOST"), port=6379)

def get_cache(key):
    return r.get(key)

def set_cache(key, value):
    r.set(key, value)