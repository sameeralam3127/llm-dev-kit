"""Ollama as an :class:`~ldk_core.ports.LLMProvider`."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import CompletionRequest

DEFAULT_OPTIONS: dict[str, Any] = {"temperature": 0.7, "num_predict": 1024}
"""Ollama options applied unless the request overrides them."""


class OllamaProvider:
    """Chat completions from a local Ollama server.

    A request holding exactly one user message goes to ``/api/generate`` with
    that message as the prompt, which is what the rag-service sends and how
    this provider has always behaved. Anything else (a system message, a
    conversation) goes to ``/api/chat``, where Ollama applies the model's
    chat template.

    Args:
        host: Ollama base URL.
        timeout_seconds: Per-request timeout.
        transport: Replaces the network transport; for tests.
    """

    name = "ollama"

    def __init__(
        self,
        host: str,
        *,
        timeout_seconds: float = 120,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.host, timeout=timeout_seconds, transport=transport
        )

    async def list_models(self) -> list[str]:
        """Return the models installed in Ollama (``/api/tags``)."""
        try:
            res = await self._client.get("/api/tags")
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise _unreachable(exc) from exc
        return [m["name"] for m in res.json().get("models", [])]

    async def complete(self, request: CompletionRequest) -> str:
        """Generate the whole answer in one call."""
        path, payload = _payload(request, stream=False)
        try:
            res = await self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise _unreachable(exc) from exc
        if res.is_error:
            raise _upstream(res.status_code, res.text)
        data = res.json()
        text = _text(data)
        if text is None:
            raise ServiceError(
                ErrorCode.UPSTREAM_ERROR, f"Ollama returned no response: {str(data)[:200]}"
            )
        return text

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Yield text as Ollama generates it (newline-delimited JSON)."""
        path, payload = _payload(request, stream=True)
        try:
            async with self._client.stream("POST", path, json=payload) as res:
                if res.status_code >= 400:
                    body = (await res.aread()).decode(errors="replace")
                    raise _upstream(res.status_code, body)
                async for line in res.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise ServiceError(
                            ErrorCode.UPSTREAM_ERROR, f"Ollama error: {data['error']}"
                        )
                    if text := _text(data):
                        yield text
                    if data.get("done"):
                        return
        except httpx.HTTPError as exc:
            raise _unreachable(exc) from exc

    async def aclose(self) -> None:
        """Close the HTTP connection pool."""
        await self._client.aclose()


def _payload(request: CompletionRequest, *, stream: bool) -> tuple[str, dict[str, Any]]:
    """Choose the endpoint and build its body."""
    options = dict(DEFAULT_OPTIONS)
    if request.temperature is not None:
        options["temperature"] = request.temperature
    if request.max_tokens is not None:
        options["num_predict"] = request.max_tokens
    options.update(request.extra)

    messages = list(request.messages)
    if len(messages) == 1 and messages[0].role == "user":
        return "/api/generate", {
            "model": request.model,
            "prompt": messages[0].content,
            "stream": stream,
            "options": options,
        }
    return "/api/chat", {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": stream,
        "options": options,
    }


def _text(data: dict[str, Any]) -> str | None:
    """Text from a ``/api/generate`` or ``/api/chat`` response object."""
    if "response" in data:
        return str(data["response"])
    message = data.get("message")
    if isinstance(message, dict) and "content" in message:
        return str(message["content"])
    return None


def _unreachable(exc: httpx.HTTPError) -> ServiceError:
    return ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, f"Ollama unreachable: {exc}")


def _upstream(status: int, body: str) -> ServiceError:
    # Always 502: Ollama answering with an error (unknown model included) is
    # an upstream failure from the caller's point of view.
    return ServiceError(ErrorCode.UPSTREAM_ERROR, f"Ollama error {status}: {body[:200]}")
