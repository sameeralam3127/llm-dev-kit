"""Cloud chat providers through LiteLLM.

One class covers OpenAI, Gemini, Anthropic and anything else LiteLLM knows:
LiteLLM normalises request and response shapes and streams real tokens from
every backend. Local Ollama has its own plugin (it also serves embeddings).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import MappingProxyType
from typing import Any

import litellm

from ldk_core.errors import ErrorCode, ServiceError, code_for_status
from ldk_core.ports import CompletionRequest

# Don't fail a request because one provider rejects an optional param.
litellm.drop_params = True
litellm.suppress_debug_info = True
# Sovereignty: LiteLLM must not phone home (D5 telemetry kill list).
litellm.telemetry = False

DEFAULT_CLOUD_MODELS = MappingProxyType(
    {
        "openai": ("gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o4-mini"),
        "gemini": ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"),
        "anthropic": ("claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5-20251001"),
    }
)
"""Curated model lists, shown without a network call or a configured key."""

DEFAULT_TEMPERATURE = 0.7


class LiteLLMProvider:
    """One cloud provider (``openai``, ``gemini``, ``anthropic``, ...).

    Args:
        name: LiteLLM provider prefix; also the registry name.
        api_key: Server-side key. A request's own ``api_key`` takes priority.
        base_url: Override the provider's API base.
        timeout_seconds: Per-request timeout.
    """

    def __init__(
        self,
        name: str,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 120,
    ) -> None:
        self.name = name
        self._api_key = api_key
        self.base_url = base_url
        self.timeout = timeout_seconds

    async def list_models(self) -> list[str]:
        """Return the curated model list for this provider."""
        return list(DEFAULT_CLOUD_MODELS.get(self.name, ()))

    async def complete(self, request: CompletionRequest) -> str:
        """Return the full answer."""
        kwargs = self._call_kwargs(request)
        try:
            res = await litellm.acompletion(**kwargs)
        except Exception as exc:  # LiteLLM raises many unrelated types
            raise self._wrap(exc) from exc
        text = (res.choices[0].message.content or "") if res.choices else ""
        if not text:
            raise ServiceError(ErrorCode.UPSTREAM_ERROR, f"{self.name} returned no text content")
        return str(text)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Yield text deltas as the provider streams them."""
        kwargs = self._call_kwargs(request)
        try:
            stream = await litellm.acompletion(**kwargs, stream=True)
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield str(delta.content)
        except ServiceError:
            raise
        except Exception as exc:  # LiteLLM raises many unrelated types
            raise self._wrap(exc) from exc

    def _call_kwargs(self, request: CompletionRequest) -> dict[str, Any]:
        """LiteLLM arguments; raises ``unauthorized`` when there is no key."""
        key = request.api_key or self._api_key
        if not key:
            raise ServiceError(
                ErrorCode.UNAUTHORIZED,
                f"No API key for provider '{self.name}'. Set {self.name.upper()}_API_KEY "
                "in .env or pass api_key with the request.",
            )
        temperature = request.temperature
        if temperature is None:
            temperature = request.extra.get("temperature", DEFAULT_TEMPERATURE)
        kwargs: dict[str, Any] = {
            "model": f"{self.name}/{request.model}",
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "api_key": key,
            "temperature": temperature,
            "timeout": self.timeout,
        }
        max_tokens = request.max_tokens or request.extra.get("max_tokens")
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if self.base_url:
            kwargs["api_base"] = self.base_url
        return kwargs

    def _wrap(self, exc: Exception) -> ServiceError:
        """Map a LiteLLM exception to a ServiceError by its HTTP status."""
        status = getattr(exc, "status_code", None)
        code = code_for_status(status) if isinstance(status, int) else ErrorCode.UPSTREAM_ERROR
        return ServiceError(code, f"{self.name} error: {str(exc)[:300]}")
