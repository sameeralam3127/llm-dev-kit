import asyncio

import pytest

from rag_service import cache


def test_make_key_is_stable_for_prompt_and_model():
    assert cache.make_key("  hello  ", "llama3.1") == cache.make_key("hello", "llama3.1")


def test_make_key_changes_by_model():
    assert cache.make_key("hello", "model-a") != cache.make_key("hello", "model-b")


def test_make_key_is_namespaced():
    assert cache.make_key("hello", "llama3.1").startswith(cache.CHAT_PREFIX)


def test_make_key_changes_when_the_revision_bumps():
    assert cache.make_key("hello", "m", 0) != cache.make_key("hello", "m", 1)


def test_make_key_is_stable_for_the_same_revision():
    assert cache.make_key("hello", "m", 3) == cache.make_key(" hello ", "m", 3)


def test_make_key_differs_by_model_within_a_revision():
    assert cache.make_key("hello", "a", 2) != cache.make_key("hello", "b", 2)


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.broken = False

    def _check(self) -> None:
        if self.broken:
            raise ConnectionError("redis down")

    async def get(self, key):
        self._check()
        return self.data.get(key)

    async def setex(self, key, ttl, value):
        self._check()
        self.data[key] = value

    async def incr(self, key):
        self._check()
        self.data[key] = str(int(self.data.get(key, "0")) + 1)
        return int(self.data[key])

    async def delete(self, key):
        self._check()
        self.data.pop(key, None)

    async def scan_iter(self, match):
        self._check()
        prefix = match.rstrip("*")
        for key in list(self.data):
            if key.startswith(prefix):
                yield key

    async def aclose(self):
        pass


@pytest.fixture
def chat_cache(monkeypatch: pytest.MonkeyPatch) -> cache.ChatCache:
    redis = FakeRedis()
    monkeypatch.setattr(cache.Redis, "from_url", lambda *a, **k: redis)
    return cache.ChatCache("redis://fake", ttl=60)


def test_a_cached_answer_is_a_miss_after_the_revision_bumps(chat_cache: cache.ChatCache):
    async def scenario():
        await chat_cache.set("q", "m", "old answer")
        assert await chat_cache.get("q", "m") == "old answer"
        await chat_cache.bump_revision()
        return await chat_cache.get("q", "m")

    assert asyncio.run(scenario()) is None


def test_an_answer_started_before_a_bump_is_not_served_after_it(chat_cache: cache.ChatCache):
    async def scenario():
        started_at = await chat_cache.revision()  # the question starts
        await chat_cache.bump_revision()  # a document is ingested meanwhile
        await chat_cache.set("q", "m", "stale answer", revision=started_at)
        return await chat_cache.get("q", "m")

    assert asyncio.run(scenario()) is None


def test_clear_removes_answers_but_keeps_the_revision(chat_cache: cache.ChatCache):
    async def scenario():
        await chat_cache.bump_revision()
        await chat_cache.set("q", "m", "a")
        cleared = await chat_cache.clear()
        return cleared, await chat_cache.revision(), await chat_cache.get("q", "m")

    assert asyncio.run(scenario()) == (1, 1, None)


def test_redis_failure_never_raises(chat_cache: cache.ChatCache):
    chat_cache.client.broken = True

    async def scenario():
        assert await chat_cache.revision() is None
        assert await chat_cache.get("q", "m") is None
        await chat_cache.set("q", "m", "a")
        await chat_cache.bump_revision()

    asyncio.run(scenario())
