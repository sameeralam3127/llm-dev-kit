import asyncio
import json

from rag_service.chat import answer_query, stream_answer


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

    async def get(self, prompt, model=None):
        return self.preset

    async def set(self, prompt, model, value):
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
