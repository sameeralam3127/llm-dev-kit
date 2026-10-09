"""``Chunker``: a loaded document to retrieval-sized pieces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ldk_core.ports.loader import LoadedDocument


@dataclass(frozen=True, slots=True)
class TextChunk:
    """One retrievable piece of a document.

    Attributes:
        index: 0-based position within the document; stable for a given
            chunker configuration, so a re-index produces the same ids.
        text: The chunk text, stripped.
        page: 1-based page the chunk starts on, or ``None`` if unknown.
    """

    index: int
    text: str
    page: int | None = None


@runtime_checkable
class Chunker(Protocol):
    """Splits a document into chunks for embedding.

    Synchronous and CPU-bound, like loading. Never returns empty chunks.
    """

    @property
    def name(self) -> str:
        """Registry name, e.g. ``"recursive"``."""
        ...

    def chunk(self, document: LoadedDocument) -> list[TextChunk]:
        """Split ``document``, in reading order."""
        ...
