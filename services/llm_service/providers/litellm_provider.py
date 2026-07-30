"""Cloud chat providers routed through LiteLLM.

One class covers OpenAI, Gemini, Anthropic and any other provider LiteLLM
knows about — LiteLLM normalises request/response shapes and gives us true
token streaming for every cloud backend. Local Ollama stays on the direct
provider (it also serves embeddings).
"""

from collections.abc import AsyncIterator

import litellm

from llm_service.providers.base import ProviderError

# Don't fail a request because one provider rejects an optional param.
litellm.drop_params = True
litellm.suppress_debug_info = True

# Curated model lists — shown in the UI without needing a network call or a
# configured key (users can paste their own key per request).
DEFAULT_CLOUD_MODELS: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o4-mini"),
    "gemini": ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"),
    "anthropic": ("claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5-20251001"),
}


class LiteLLMProvider:
    """A single cloud provider (openai, gemini, anthropic, ...) via LiteLLM."""

    def __init__(
        self,
        name: str,
        api_key: str | None,
        base_url: str | None = None,
        timeout: float = 120,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def list_models(self) -> list[str]:
        return list(DEFAULT_CLOUD_MODELS.get(self.name, ()))

    def _key(self, api_key: str | None) -> str:
        key = api_key or self.api_key
        if not key:
            raise ProviderError(
                f"No API key for provider '{self.name}'. Set "
                f"{self.name.upper()}_API_KEY in .env or pass api_key with the "
                "request.",
                status_code=401,
            )
        return key

    def _call_kwargs(self, model: str, prompt: str, options: dict, api_key: str | None) -> dict:
        kwargs = {
            "model": f"{self.name}/{model}",
            "messages": [{"role": "user", "content": prompt}],
            "api_key": self._key(api_key),
            "temperature": options.get("temperature", 0.7),
            "timeout": self.timeout,
        }
        if "max_tokens" in options:
            kwargs["max_tokens"] = options["max_tokens"]
        if self.base_url:
            kwargs["api_base"] = self.base_url
        return kwargs

    async def generate(
        self, model: str, prompt: str, options: dict, api_key: str | None = None
    ) -> str:
        try:
            res = await litellm.acompletion(
                **self._call_kwargs(model, prompt, options, api_key)
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise self._wrap(exc) from exc
        text = (res.choices[0].message.content or "") if res.choices else ""
        if not text:
            raise ProviderError(f"{self.name} returned no text content")
        return text

    async def generate_stream(
        self, model: str, prompt: str, options: dict, api_key: str | None = None
    ) -> AsyncIterator[str]:
        try:
            stream = await litellm.acompletion(
                **self._call_kwargs(model, prompt, options, api_key), stream=True
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except ProviderError:
            raise
        except Exception as exc:
            raise self._wrap(exc) from exc

    def _wrap(self, exc: Exception) -> ProviderError:
        status = getattr(exc, "status_code", None) or 502
        return ProviderError(f"{self.name} error: {str(exc)[:300]}", status_code=status)
