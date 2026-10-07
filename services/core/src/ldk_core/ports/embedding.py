"""``Embedder``: text to vectors."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """Turns text into fixed-length vectors for similarity search.

    ``model`` and ``dimension`` are recorded on every stored chunk. A vector
    store refuses an embedder whose dimension does not match its index at
    startup, not at query time (risk R9).
    """

    @property
    def name(self) -> str:
        """Registry name, e.g. ``"ollama"``."""
        ...

    @property
    def model(self) -> str:
        """The embedding model id, e.g. ``"nomic-embed-text"``."""
        ...

    @property
    def dimension(self) -> int:
        """Length of every vector this embedder returns."""
        ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed each text, preserving order: one vector per input.

        Raises:
            ldk_core.errors.ServiceError: ``upstream_unavailable`` or
                ``upstream_error``. No partial result is returned.
        """
        ...
