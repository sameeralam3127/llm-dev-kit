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

BATCH_SIZE = 64
"""Texts per request to Ollama's batch endpoint, ``/api/embed``."""


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
        """Embed each text, in order, in batches of :data:`BATCH_SIZE`.

        One request per batch to ``/api/embed``: a long document used to be
        one sequential request per chunk.
        """
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(await self._embed_batch(list(texts[start : start + BATCH_SIZE])))
        return vectors

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        try:
            res = await self._client.post("/api/embed", json={"model": self.model, "input": batch})
        except httpx.HTTPError as exc:
            raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Ollama unreachable") from exc
        if res.is_error:
            raise ServiceError(
                ErrorCode.UPSTREAM_ERROR,
                f"Ollama embedding failed (HTTP {res.status_code})",
            )
        embeddings = res.json().get("embeddings") or []
        if len(embeddings) != len(batch):
            raise ServiceError(
                ErrorCode.UPSTREAM_ERROR,
                f"Ollama returned {len(embeddings)} embeddings for {len(batch)} texts",
            )
        for embedding in embeddings:
            if len(embedding) != self.dimension:
                raise ServiceError(
                    ErrorCode.UPSTREAM_ERROR,
                    f"Ollama model '{self.model}' returned {len(embedding)} dimensions, "
                    f"expected {self.dimension}",
                )
        return [[float(x) for x in embedding] for embedding in embeddings]

    async def aclose(self) -> None:
        """Close the HTTP connection pool."""
        await self._client.aclose()
