import json
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException


class LLMServiceClient:
    """HTTP client for the llm-service. All chat/embedding traffic goes here."""

    def __init__(self, base_url: str, timeout: float) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout
        )

    async def models(self) -> list[str]:
        try:
            res = await self._client.get("/models")
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"LLM service unavailable: {exc}")
        return res.json().get("models", [])

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
                raise HTTPException(
                    status_code=502,
                    detail=f"Embedding failed: {_detail(exc.response)}",
                )
            return []
        except httpx.HTTPError as exc:
            if strict:
                raise HTTPException(
                    status_code=503, detail=f"LLM service unavailable: {exc}"
                )
            return []
        return res.json()["embeddings"]

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        api_key: str | None = None,
        options: dict | None = None,
    ) -> dict:
        payload = {
            "prompt": prompt,
            "model": model,
            "api_key": api_key,
            "options": options or {},
        }
        try:
            res = await self._client.post("/generate", json=payload)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"LLM service unavailable: {exc}")
        if res.is_error:
            status = res.status_code if res.status_code < 500 else 502
            raise HTTPException(status_code=status, detail=_detail(res))
        return res.json()

    async def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        api_key: str | None = None,
        options: dict | None = None,
    ) -> AsyncIterator[str]:
        payload = {
            "prompt": prompt,
            "model": model,
            "api_key": api_key,
            "options": options or {},
        }
        try:
            async with self._client.stream(
                "POST", "/generate/stream", json=payload
            ) as res:
                if res.status_code >= 400:
                    body = (await res.aread()).decode(errors="replace")
                    raise HTTPException(status_code=502, detail=body[:200])
                async for line in res.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise RuntimeError(data["error"])
                    if data.get("delta"):
                        yield data["delta"]
                    if data.get("done"):
                        return
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"LLM service unavailable: {exc}")

    async def close(self) -> None:
        await self._client.aclose()


def _detail(response) -> str:
    try:
        return response.json().get("detail", response.text[:200])
    except Exception:
        return response.text[:200]
