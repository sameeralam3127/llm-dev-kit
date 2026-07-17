import asyncio

from rag_service.chat import answer_query


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
