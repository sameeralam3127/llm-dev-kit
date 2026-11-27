"""rag-service's client for llm-service forwards the caller's request id."""

import asyncio
import json

import httpx
import pytest

from ldk_core.auth import credential_scope
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.observability import correlation_scope
from rag_service.llm_client import LLMServiceClient


def _client(seen: list[str | None], header: str = "x-request-id") -> LLMServiceClient:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get(header))
        if request.url.path == "/generate/stream":
            lines = [{"delta": "hi"}, {"done": True}]
            return httpx.Response(200, text="\n".join(json.dumps(line) for line in lines))
        if request.url.path == "/embed":
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})
        return httpx.Response(200, json={"models": ["llama3.1"]})

    return LLMServiceClient("http://llm.test", 5, transport=httpx.MockTransport(handle))


def test_every_call_to_llm_service_carries_the_request_id() -> None:
    seen: list[str | None] = []
    client = _client(seen)

    async def calls() -> None:
        with correlation_scope("req-42"):
            await client.models()
            await client.embed_one("text")
            assert [d async for d in client.generate_stream("prompt")] == ["hi"]
        await client.close()

    asyncio.run(calls())
    assert seen == ["req-42", "req-42", "req-42"]


def test_no_header_outside_a_request() -> None:
    seen: list[str | None] = []
    client = _client(seen)

    async def call() -> None:
        await client.models()
        await client.close()

    asyncio.run(call())
    assert seen == [None]


def test_every_call_to_llm_service_carries_the_callers_credential() -> None:
    seen: list[str | None] = []
    client = _client(seen, header="authorization")

    async def calls() -> None:
        with credential_scope("token-of-the-caller"):
            await client.models()
            assert [d async for d in client.generate_stream("prompt")] == ["hi"]
        await client.models()
        await client.close()

    asyncio.run(calls())
    assert seen == ["Bearer token-of-the-caller", "Bearer token-of-the-caller", None]


def test_http_and_stream_failures_omit_backend_details() -> None:
    detail = {"message": "synthetic-provider-detail", "Authorization": "synthetic-key"}

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/stream"):
            return httpx.Response(200, text=json.dumps({"error": detail}) + "\n")
        return httpx.Response(401, json={"error": detail})

    async def check() -> None:
        client = LLMServiceClient("http://llm.test", 5, transport=httpx.MockTransport(handle))
        try:
            with pytest.raises(ServiceError) as request_error:
                await client.generate("prompt")
            assert request_error.value.code is ErrorCode.UNAUTHORIZED
            assert request_error.value.message == "LLM service request failed (HTTP 401)"
            with pytest.raises(ServiceError) as stream_error:
                async for _ in client.generate_stream("prompt"):
                    pass
            assert stream_error.value.code is ErrorCode.UPSTREAM_ERROR
            assert stream_error.value.message == "LLM service stream failed"
        finally:
            await client.close()

    asyncio.run(check())


# ------------------------------------------------------------------ batching
# A document's chunks go to llm-service in bounded batches, never as one
# request that has to finish inside a single timeout.


def _embedding_client(calls: list[list[str]], fail_call: int | None = None) -> LLMServiceClient:
    def handle(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["texts"]
        calls.append(texts)
        if len(calls) == fail_call:
            return httpx.Response(
                503, json={"error": {"code": "upstream_unavailable", "message": "busy"}}
            )
        return httpx.Response(200, json={"embeddings": [[float(len(t))] for t in texts]})

    return LLMServiceClient("http://llm.test", 5, transport=httpx.MockTransport(handle))


def test_embed_many_sends_bounded_batches_and_keeps_the_order() -> None:
    from rag_service.llm_client import EMBED_BATCH_SIZE

    calls: list[list[str]] = []
    texts = ["x" * (i % 7 + 1) for i in range(2 * EMBED_BATCH_SIZE + 5)]
    vectors = asyncio.run(_embedding_client(calls).embed_many(texts))

    assert sorted(len(c) for c in calls) == sorted([EMBED_BATCH_SIZE, EMBED_BATCH_SIZE, 5])
    assert vectors == [[float(len(t))] for t in texts]


def test_embed_many_fails_when_any_batch_fails() -> None:
    from rag_service.llm_client import EMBED_BATCH_SIZE

    calls: list[list[str]] = []
    client = _embedding_client(calls, fail_call=2)
    with pytest.raises(ServiceError, match="Embedding failed"):
        asyncio.run(client.embed_many(["t"] * (EMBED_BATCH_SIZE * 3)))


def test_a_small_document_is_still_one_call() -> None:
    calls: list[list[str]] = []
    asyncio.run(_embedding_client(calls).embed_many(["a", "b", "c"]))
    assert calls == [["a", "b", "c"]]
