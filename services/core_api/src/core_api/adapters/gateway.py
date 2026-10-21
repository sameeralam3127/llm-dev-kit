"""Clients for model-gateway, the only service allowed to reach a model.

The gateway speaks SSE for streams (architecture decision 8). Each event is
``data: <json>``:

* ``{"delta": "text"}``: a piece of the answer;
* ``{"done": true, "model": "...", "usage": {"tokens_in": n, "tokens_out": n}}``;
* ``{"error": {"code": "...", "message": "..."}}``: the shared error envelope.

Every call carries the caller's service credential and, for chat, who it is on
behalf of (``X-On-Behalf-Of``, ``X-Workspace-Id``), so the gateway can audit
each model call against a user and a workspace.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from core_api.domain.retrieval import ChatMessage
from core_api.ports.models import Delta, Done, OnBehalfOf, StreamEvent
from ldk_core.errors import ErrorCode, ServiceError, code_for_status
from ldk_core.observability import outgoing_headers


class GatewayEmbedder:
    """Embeds through model-gateway's ``POST /embed``.

    Args:
        base_url: model-gateway's internal URL.
        token: The worker's service credential.
        model: Embedding model, recorded on every chunk as ``embed_model``.
        dimension: Expected vector length; anything else is refused.
    """

    name = "model-gateway"

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        model: str,
        dimension: int,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )

    @property
    def model(self) -> str:
        """The embedding model id."""
        return self._model

    @property
    def dimension(self) -> int:
        """Vector length."""
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in order. Callers batch; this sends what it is given."""
        try:
            res = await self._client.post(
                "/embed",
                json={"texts": list(texts), "model": self._model},
                headers={"Authorization": f"Bearer {self._token}", **outgoing_headers()},
            )
        except httpx.HTTPError as exc:
            raise ServiceError(
                ErrorCode.UPSTREAM_UNAVAILABLE, f"model-gateway unreachable: {exc}"
            ) from exc
        if res.is_error:
            raise ServiceError(
                code_for_status(res.status_code), f"model-gateway returned {res.status_code}"
            )
        vectors: list[list[float]] = res.json()["embeddings"]
        if len(vectors) != len(texts) or any(len(v) != self._dimension for v in vectors):
            raise ServiceError(
                ErrorCode.UPSTREAM_ERROR, "model-gateway returned malformed embeddings"
            )
        return vectors

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


class GatewayModelClient:
    """Implements :class:`~core_api.ports.models.ModelClient` over HTTP and SSE."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )

    def _headers(self, caller: OnBehalfOf | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}", **outgoing_headers()}
        if caller is not None:
            headers["X-On-Behalf-Of"] = caller.user_id
            headers["X-Workspace-Id"] = str(caller.workspace_id)
        return headers

    async def models(self) -> list[str]:
        """The gateway's model list."""
        try:
            res = await self._client.get("/models", headers=self._headers())
        except httpx.HTTPError as exc:
            raise ServiceError(
                ErrorCode.UPSTREAM_UNAVAILABLE, f"model-gateway unreachable: {exc}"
            ) from exc
        if res.is_error:
            raise ServiceError(
                code_for_status(res.status_code), "model-gateway refused the request"
            )
        models: list[str] = res.json()["models"]
        return models

    async def stream_chat(
        self, messages: Sequence[ChatMessage], *, model: str, caller: OnBehalfOf
    ) -> AsyncIterator[StreamEvent]:
        """Stream one answer as :class:`Delta` events, then a :class:`Done`."""
        body = {
            "model": model,
            "stream": True,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        try:
            async with self._client.stream(
                "POST", "/chat", json=body, headers=self._headers(caller)
            ) as res:
                if res.is_error:
                    await res.aread()
                    raise ServiceError(
                        code_for_status(res.status_code), _error_message(res.text, res.status_code)
                    )
                async for line in res.aiter_lines():
                    if not line.startswith("data:"):
                        continue  # blank separators and comments
                    event = json.loads(line[5:].strip())
                    if "error" in event:
                        error = event["error"]
                        raise ServiceError(
                            ErrorCode(error.get("code", "upstream_error")),
                            error.get("message", "model-gateway failed"),
                        )
                    if event.get("done"):
                        usage = event.get("usage") or {}
                        yield Done(
                            model=event.get("model", model),
                            tokens_in=usage.get("tokens_in"),
                            tokens_out=usage.get("tokens_out"),
                        )
                        return
                    if text := event.get("delta"):
                        yield Delta(text)
        except httpx.HTTPError as exc:
            raise ServiceError(
                ErrorCode.UPSTREAM_UNAVAILABLE, f"model-gateway unreachable: {exc}"
            ) from exc

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


def _error_message(body: str, status: int) -> str:
    try:
        return str(json.loads(body)["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"model-gateway returned {status}"
