import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from devkit_common.http import error_detail
from ldk_core.errors import ErrorCode, ServiceError, code_for_status


class LLMServiceClient:
    """HTTP client for the llm-service. All chat/embedding traffic goes here.

    Failures raise ServiceError: upstream_unavailable when llm-service cannot
    be reached, otherwise the code matching its response status.
    """

    def __init__(self, base_url: str, timeout: float) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def models(self) -> list[str]:
        try:
            res = await self._client.get("/models")
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise _unavailable(exc) from exc
        models: list[str] = res.json().get("models", [])
        return models

    async def embed_one(self, text: str) -> list[float] | None:
        embeddings = await self._embed([text], strict=False)
        return embeddings[0] if embeddings else None

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, strict=True)

    async def _embed(self, texts: list[str], *, strict: bool) -> list[list[float]]:
        try:
            res = await self._client.post("/embed", json={"texts": texts})
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if strict:
                raise ServiceError(
                    ErrorCode.UPSTREAM_ERROR, f"Embedding failed: {_detail(exc.response)}"
                ) from exc
            return []
        except httpx.HTTPError as exc:
            if strict:
                raise _unavailable(exc) from exc
            return []
        embeddings: list[list[float]] = res.json()["embeddings"]
        return embeddings

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        api_key: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "prompt": prompt,
            "model": model,
            "api_key": api_key,
            "options": options or {},
        }
        try:
            res = await self._client.post("/generate", json=payload)
        except httpx.HTTPError as exc:
            raise _unavailable(exc) from exc
        if res.is_error:
            # As before: a 4xx keeps its meaning (a missing cloud key stays a
            # 401); any 5xx from llm-service is a 502 from here.
            status = res.status_code
            code = code_for_status(status) if status < 500 else ErrorCode.UPSTREAM_ERROR
            raise ServiceError(code, _detail(res))
        body: dict[str, Any] = res.json()
        return body

    async def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        api_key: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        payload = {
            "prompt": prompt,
            "model": model,
            "api_key": api_key,
            "options": options or {},
        }
        try:
            async with self._client.stream("POST", "/generate/stream", json=payload) as res:
                if res.status_code >= 400:
                    body = (await res.aread()).decode(errors="replace")
                    raise ServiceError(ErrorCode.UPSTREAM_ERROR, _text_detail(body))
                async for line in res.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise ServiceError(ErrorCode.UPSTREAM_ERROR, str(data["error"]))
                    if data.get("delta"):
                        yield data["delta"]
                    if data.get("done"):
                        return
        except httpx.HTTPError as exc:
            raise _unavailable(exc) from exc

    async def close(self) -> None:
        await self._client.aclose()


def _unavailable(exc: httpx.HTTPError) -> ServiceError:
    return ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, f"LLM service unavailable: {exc}")


def _detail(response: httpx.Response) -> str:
    """The upstream's error message, from the envelope or a legacy body."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    return error_detail(body) or response.text[:200]


def _text_detail(body: str) -> str:
    try:
        return error_detail(json.loads(body)) or body[:200]
    except ValueError:
        return body[:200]
