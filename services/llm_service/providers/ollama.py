import json
from collections.abc import AsyncIterator

import httpx

from llm_service.providers.base import ProviderError


class OllamaProvider:
    name = "ollama"

    def __init__(self, host: str, client: httpx.AsyncClient) -> None:
        self.host = host.rstrip("/")
        self.client = client

    async def list_models(self) -> list[str]:
        try:
            res = await self.client.get(f"{self.host}/api/tags")
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama unreachable: {exc}", status_code=503) from exc
        return [m["name"] for m in res.json().get("models", [])]

    async def generate(self, model: str, prompt: str, options: dict) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 1024, **options},
        }
        try:
            res = await self.client.post(f"{self.host}/api/generate", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama unreachable: {exc}", status_code=503) from exc
        if res.is_error:
            raise ProviderError(f"Ollama error {res.status_code}: {res.text[:200]}")
        data = res.json()
        if "response" not in data:
            raise ProviderError(f"Ollama returned no response: {str(data)[:200]}")
        return data["response"]

    async def generate_stream(
        self, model: str, prompt: str, options: dict
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.7, "num_predict": 1024, **options},
        }
        try:
            async with self.client.stream(
                "POST", f"{self.host}/api/generate", json=payload
            ) as res:
                if res.status_code >= 400:
                    body = (await res.aread()).decode(errors="replace")
                    raise ProviderError(
                        f"Ollama error {res.status_code}: {body[:200]}"
                    )
                async for line in res.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("response"):
                        yield data["response"]
                    if data.get("done"):
                        return
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama unreachable: {exc}", status_code=503) from exc

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            try:
                res = await self.client.post(
                    f"{self.host}/api/embeddings",
                    json={"model": model, "prompt": text},
                )
            except httpx.HTTPError as exc:
                raise ProviderError(
                    f"Ollama unreachable: {exc}", status_code=503
                ) from exc
            if res.is_error:
                raise ProviderError(
                    f"Ollama embedding error {res.status_code}: {res.text[:200]}"
                )
            embedding = res.json().get("embedding")
            if not embedding:
                raise ProviderError(
                    f"Ollama returned an empty embedding for model '{model}'"
                )
            embeddings.append(list(embedding))
        return embeddings
