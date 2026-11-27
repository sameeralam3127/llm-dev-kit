import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ldk_core.auth import auth_headers
from ldk_core.errors import ErrorCode, ServiceError, code_for_status
from ldk_core.observability import outgoing_headers

EMBED_BATCH_SIZE = 64
"""Chunks per /embed request. A document never travels as one request, which
would have to finish inside a single timeout."""

EMBED_CONCURRENCY = 4
"""Batches in flight at once, so a long document neither waits on one batch at
a time nor floods llm-service."""


class LLMServiceClient:
    """HTTP client for the llm-service. All chat/embedding traffic goes here.

    Failures raise ServiceError: upstream_unavailable when llm-service cannot
    be reached, otherwise the code matching its response status.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            event_hooks={"request": [_forward_context]},
        )

    async def models(self) -> list[str]:
        try:
            res = await self._client.get("/models")
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise _unavailable() from exc
        models: list[str] = res.json().get("models", [])
        return models

    async def embed_one(self, text: str) -> list[float] | None:
        embeddings = await self._embed([text], strict=False)
        return embeddings[0] if embeddings else None

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts`` in order, in bounded batches; any failed batch fails all."""
        batches = [texts[i : i + EMBED_BATCH_SIZE] for i in range(0, len(texts), EMBED_BATCH_SIZE)]
        if len(batches) <= 1:
            return await self._embed(texts, strict=True)
        limit = asyncio.Semaphore(EMBED_CONCURRENCY)

        async def one(batch: list[str]) -> list[list[float]]:
            async with limit:
                return await self._embed(batch, strict=True)

        results = await asyncio.gather(*(one(batch) for batch in batches))
        return [vector for result in results for vector in result]

    async def _embed(self, texts: list[str], *, strict: bool) -> list[list[float]]:
        try:
            res = await self._client.post("/embed", json={"texts": texts})
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if strict:
                raise ServiceError(ErrorCode.UPSTREAM_ERROR, "Embedding failed") from exc
            return []
        except httpx.HTTPError as exc:
            if strict:
                raise _unavailable() from exc
            return []
        embeddings: list[list[float]] = res.json()["embeddings"]
        return embeddings

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "prompt": prompt,
            "model": model,
            "api_key": api_key,
        }
        try:
            res = await self._client.post("/generate", json=payload)
        except httpx.HTTPError as exc:
            raise _unavailable() from exc
        if res.is_error:
            # As before: a 4xx keeps its meaning (a missing cloud key stays a
            # 401); any 5xx from llm-service is a 502 from here.
            status = res.status_code
            code = code_for_status(status) if status < 500 else ErrorCode.UPSTREAM_ERROR
            raise ServiceError(code, f"LLM service request failed (HTTP {status})")
        body: dict[str, Any] = res.json()
        return body

    async def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        api_key: str | None = None,
    ) -> AsyncIterator[str]:
        payload = {
            "prompt": prompt,
            "model": model,
            "api_key": api_key,
        }
        try:
            async with self._client.stream("POST", "/generate/stream", json=payload) as res:
                if res.status_code >= 400:
                    raise ServiceError(ErrorCode.UPSTREAM_ERROR, "LLM service stream failed")
                async for line in res.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise ServiceError(ErrorCode.UPSTREAM_ERROR, "LLM service stream failed")
                    if data.get("delta"):
                        yield data["delta"]
                    if data.get("done"):
                        return
        except httpx.HTTPError as exc:
            raise _unavailable() from exc

    async def close(self) -> None:
        await self._client.aclose()


async def _forward_context(request: httpx.Request) -> None:
    """Carry the caller's request id and identity to llm-service.

    One id then spans both logs, and llm-service verifies the same caller
    rather than trusting rag-service.
    """
    for name, value in {**outgoing_headers(), **auth_headers()}.items():
        request.headers.setdefault(name, value)


def _unavailable() -> ServiceError:
    return ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "LLM service unavailable")
