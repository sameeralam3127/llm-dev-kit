import httpx

from llm_service.providers.base import ProviderError

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self, base_url: str, api_key: str | None, client: httpx.AsyncClient
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self, api_key: str | None) -> dict[str, str]:
        key = api_key or self.api_key
        if not key:
            raise ProviderError(
                "No API key for provider 'anthropic'. Set ANTHROPIC_API_KEY in .env "
                "or pass api_key with the request.",
                status_code=401,
            )
        return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}

    async def list_models(self, api_key: str | None = None) -> list[str]:
        try:
            res = await self.client.get(
                f"{self.base_url}/v1/models", headers=self._headers(api_key)
            )
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"anthropic models error {exc.response.status_code}: "
                f"{exc.response.text[:200]}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"anthropic unreachable: {exc}", status_code=503) from exc
        return [m["id"] for m in res.json().get("data", [])]

    async def generate(
        self,
        model: str,
        prompt: str,
        options: dict,
        api_key: str | None = None,
    ) -> str:
        payload = {
            "model": model,
            "max_tokens": options.get("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
        }
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        try:
            res = await self.client.post(
                f"{self.base_url}/v1/messages",
                json=payload,
                headers=self._headers(api_key),
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"anthropic unreachable: {exc}", status_code=503) from exc
        if res.is_error:
            raise ProviderError(
                f"anthropic error {res.status_code}: {res.text[:200]}",
                status_code=res.status_code,
            )
        blocks = res.json().get("content") or []
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        if not text:
            raise ProviderError("anthropic returned no text content")
        return text
