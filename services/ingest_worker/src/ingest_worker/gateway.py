"""An ``Embedder`` that calls model-gateway, the only service allowed to reach a model."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

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
