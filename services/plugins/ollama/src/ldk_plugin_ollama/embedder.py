"""Ollama as an :class:`~ldk_core.ports.Embedder`."""

from __future__ import annotations

from collections.abc import Sequence
from types import MappingProxyType

import httpx

from ldk_core.errors import ErrorCode, ServiceError

KNOWN_DIMENSIONS = MappingProxyType(
    {
        "nomic-embed-text": 768,
        "mxbai-embed-large": 1024,
        "snowflake-arctic-embed": 1024,
        "bge-m3": 1024,
        "all-minilm": 384,
    }
)
"""Vector length of common Ollama embedding models, by name without tag."""


class OllamaEmbedder:
    """Embeddings from one Ollama model.

    The dimension is fixed at construction, from :data:`KNOWN_DIMENSIONS` or
    the ``dimension`` argument, so a mismatch with the vector index fails at
    startup rather than at query time (risk R9). Every returned vector is
    checked against it.

    Args:
        host: Ollama base URL.
        model: Embedding model, e.g. ``"nomic-embed-text"`` or ``"bge-m3:latest"``.
        dimension: Vector length; required if ``model`` is not known.
        timeout_seconds: Per-request timeout.
        transport: Replaces the network transport; for tests.

    Raises:
        ValueError: ``model`` is unknown and no ``dimension`` was given.
    """

    name = "ollama"

    def __init__(
        self,
        host: str,
        *,
        model: str = "nomic-embed-text",
        dimension: int | None = None,
        timeout_seconds: float = 120,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        known = KNOWN_DIMENSIONS.get(model.split(":", 1)[0])
        if dimension is None and known is None:
            raise ValueError(
                f"Unknown embedding dimension for Ollama model '{model}'; set EMBEDDING_DIMENSION"
            )
        self.model = model
        self.dimension: int = dimension or known or 0
        self._client = httpx.AsyncClient(
            base_url=host.rstrip("/"), timeout=timeout_seconds, transport=transport
        )

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed each text in order (Ollama takes one text per request)."""
        vectors: list[list[float]] = []
        for text in texts:
            try:
                res = await self._client.post(
                    "/api/embeddings", json={"model": self.model, "prompt": text}
                )
            except httpx.HTTPError as exc:
                raise ServiceError(
                    ErrorCode.UPSTREAM_UNAVAILABLE, f"Ollama unreachable: {exc}"
                ) from exc
            if res.is_error:
                raise ServiceError(
                    ErrorCode.UPSTREAM_ERROR,
                    f"Ollama embedding error {res.status_code}: {res.text[:200]}",
                )
            embedding = res.json().get("embedding")
            if not embedding:
                raise ServiceError(
                    ErrorCode.UPSTREAM_ERROR,
                    f"Ollama returned an empty embedding for model '{self.model}'",
                )
            if len(embedding) != self.dimension:
                raise ServiceError(
                    ErrorCode.UPSTREAM_ERROR,
                    f"Ollama model '{self.model}' returned {len(embedding)} dimensions, "
                    f"expected {self.dimension}",
                )
            vectors.append([float(x) for x in embedding])
        return vectors

    async def aclose(self) -> None:
        """Close the HTTP connection pool."""
        await self._client.aclose()
