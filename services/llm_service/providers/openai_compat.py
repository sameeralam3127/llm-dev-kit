import httpx

from llm_service.providers.base import ProviderError


class OpenAICompatProvider:
    """Provider for OpenAI and any OpenAI-compatible API (Groq, Together, etc.).

    The API key comes from the environment by default; callers may override it
    per request so users can bring their own key.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None,
        client: httpx.AsyncClient,
    ) -> None:
        self.name = name
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
                f"No API key for provider '{self.name}'. Set OPENAI_API_KEY in .env "
                "or pass api_key with the request.",
                status_code=401,
            )
        return {"Authorization": f"Bearer {key}"}

    async def list_models(self, api_key: str | None = None) -> list[str]:
        try:
            res = await self.client.get(
                f"{self.base_url}/models", headers=self._headers(api_key)
            )
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"{self.name} models error {exc.response.status_code}: "
                f"{exc.response.text[:200]}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"{self.name} unreachable: {exc}", status_code=503
            ) from exc
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
            "messages": [{"role": "user", "content": prompt}],
            "temperature": options.get("temperature", 0.7),
        }
        if "max_tokens" in options:
            payload["max_tokens"] = options["max_tokens"]
        try:
            res = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(api_key),
            )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"{self.name} unreachable: {exc}", status_code=503
            ) from exc
        if res.is_error:
            raise ProviderError(
                f"{self.name} error {res.status_code}: {res.text[:200]}",
                status_code=res.status_code,
            )
        choices = res.json().get("choices") or []
        if not choices:
            raise ProviderError(f"{self.name} returned no choices")
        return choices[0].get("message", {}).get("content", "")
