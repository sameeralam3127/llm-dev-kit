import asyncio
import json

import pytest

from ldk_core.errors import ErrorCode, ServiceError
from rag_service.chat import answer_query, stream_answer
from rag_service.retrieval import Retriever


class FakeLLM:
    def __init__(self, embedding=None, response="generated"):
        self.embedding = embedding
        self.response = response
        self.prompts = []

    async def embed_one(self, text):
        return self.embedding

    async def generate(self, prompt, model=None, api_key=None, options=None):
        self.prompts.append(prompt)
        return {"response": self.response, "model": model, "provider": "ollama"}

    async def generate_stream(self, prompt, model=None, api_key=None, options=None):
        self.prompts.append(prompt)
        for token in self.response.split(" "):
            yield token + " "


class FakeCache:
    def __init__(self, preset=None):
        self.preset = preset
        self.saved = {}

    async def revision(self):
        return 0

    async def get(self, prompt, model=None, *, revision=None):
        return self.preset

    async def set(self, prompt, model, value, *, revision=None):
        self.saved[(prompt, model)] = value


class FakeRetriever:
    def __init__(self, docs):
        self.docs = docs
        self.calls = 0

    async def retrieve(self, embedding):
        self.calls += 1
        return self.docs


def test_cached_response_is_returned():
    result = asyncio.run(
        answer_query(
            "hello",
            "llama3.1",
            llm=FakeLLM(),
            cache=FakeCache(preset="cached answer"),
            retriever=FakeRetriever([]),
        )
    )

    assert result.response == "cached answer"
    assert result.cached is True


def test_retrieved_context_is_used_and_response_cached():
    llm = FakeLLM(embedding=[0.1, 0.2], response="rag answer")
    cache = FakeCache()

    result = asyncio.run(
        answer_query(
            "hello",
            "llama3.1",
            llm=llm,
            cache=cache,
            retriever=FakeRetriever(["doc context"]),
        )
    )

    assert result.response == "rag answer"
    assert result.sources == ["doc context"]
    assert "doc context" in llm.prompts[0]
    assert cache.saved == {("hello", "llama3.1"): "rag answer"}


def test_missing_embedding_skips_retrieval():
    retriever = FakeRetriever(["doc context"])

    result = asyncio.run(
        answer_query(
            "hello",
            "llama3.1",
            llm=FakeLLM(embedding=None),
            cache=FakeCache(),
            retriever=retriever,
        )
    )

    assert result.response == "generated"
    assert result.sources == []
    assert retriever.calls == 0


async def _collect(gen):
    return [json.loads(line) for line in [chunk async for chunk in gen]]


def test_stream_cache_hit_streams_cached_answer():
    events = asyncio.run(
        _collect(
            stream_answer(
                "hello",
                "llama3.1",
                llm=FakeLLM(),
                cache=FakeCache(preset="cached answer"),
                retriever=FakeRetriever([]),
            )
        )
    )

    assert events[0]["meta"]["cached"] is True
    assert events[1]["delta"] == "cached answer"
    assert events[-1]["done"] is True


def test_stream_emits_sources_then_deltas_and_caches_result():
    llm = FakeLLM(embedding=[0.1, 0.2], response="rag answer")
    cache = FakeCache()

    events = asyncio.run(
        _collect(
            stream_answer(
                "hello",
                "llama3.1",
                llm=llm,
                cache=cache,
                retriever=FakeRetriever(["doc context"]),
            )
        )
    )

    assert events[0]["meta"] == {"cached": False, "sources": ["doc context"]}
    deltas = "".join(e["delta"] for e in events if "delta" in e)
    assert deltas == "rag answer "
    assert events[-1]["done"] is True
    assert cache.saved == {("hello", "llama3.1"): "rag answer "}


class DownRetriever:
    """A vector store outage: retrieval raises instead of returning nothing."""

    async def retrieve(self, embedding):
        raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Chroma unavailable")


def test_a_retrieval_outage_is_an_error_not_an_ungrounded_answer():
    llm = FakeLLM(embedding=[0.1, 0.2])

    with pytest.raises(ServiceError) as raised:
        asyncio.run(
            answer_query("hello", "m", llm=llm, cache=FakeCache(), retriever=DownRetriever())
        )

    assert raised.value.code is ErrorCode.UPSTREAM_UNAVAILABLE
    assert llm.prompts == []


def test_a_retrieval_outage_streams_an_error_and_no_delta():
    llm = FakeLLM(embedding=[0.1, 0.2])

    events = asyncio.run(
        _collect(stream_answer("hello", "m", llm=llm, cache=FakeCache(), retriever=DownRetriever()))
    )

    assert events == [{"error": "Chroma unavailable"}]
    assert llm.prompts == []


class DownStore:
    name = "chroma"

    async def search(self, embedding, *, scope, top_k):
        raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Chroma unavailable")


def test_the_retriever_lets_a_store_failure_propagate():
    with pytest.raises(ServiceError):
        asyncio.run(Retriever(store=DownStore()).retrieve([0.1]))


def test_healthy_but_empty_retrieval_still_answers_ungrounded():
    llm = FakeLLM(embedding=[0.1, 0.2], response="general answer")

    result = asyncio.run(
        answer_query("hello", "m", llm=llm, cache=FakeCache(), retriever=FakeRetriever([]))
    )

    assert result.response == "general answer"
    assert result.sources == []


class RevisionedCache:
    """Records the revision each save used, with a bumpable corpus revision."""

    def __init__(self):
        self.rev = 0
        self.saved = []

    async def revision(self):
        return self.rev

    async def get(self, prompt, model=None, *, revision=None):
        return None

    async def set(self, prompt, model, value, *, revision=None):
        self.saved.append((value, revision))


class IngestingLLM(FakeLLM):
    """A document is ingested while the answer is being generated."""

    def __init__(self, cache, **kw):
        super().__init__(**kw)
        self.cache = cache

    async def generate(self, prompt, model=None, api_key=None, options=None):
        self.cache.rev += 1
        return await super().generate(prompt, model, api_key, options)


def test_an_answer_generated_across_an_ingest_is_saved_under_the_old_revision():
    cache = RevisionedCache()
    llm = IngestingLLM(cache, embedding=[0.1], response="stale")

    asyncio.run(answer_query("q", "m", llm=llm, cache=cache, retriever=FakeRetriever([])))

    assert cache.saved == [("stale", 0)]
