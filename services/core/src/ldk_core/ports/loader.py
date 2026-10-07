"""``DocumentLoader``: raw file bytes to page-aware text."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Page:
    """Text from one page (or the whole file, for formats without pages).

    Attributes:
        number: 1-based page number, used in citations.
        text: Extracted text; may be empty for an image-only page.
    """

    number: int
    text: str


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    """A parsed document, kept page by page so citations can name a page."""

    pages: Sequence[Page]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """All non-empty pages joined by newlines."""
        return "\n".join(page.text for page in self.pages if page.text)


@runtime_checkable
class DocumentLoader(Protocol):
    """Parses one file format.

    Loading is CPU-bound and synchronous; async callers run it in a worker
    thread.
    """

    @property
    def name(self) -> str:
        """Registry name, e.g. ``"pdf"``."""
        ...

    @property
    def media_types(self) -> frozenset[str]:
        """MIME types this loader accepts, e.g. ``{"application/pdf"}``."""
        ...

    def load(self, data: bytes, *, filename: str | None = None) -> LoadedDocument:
        """Parse ``data`` into pages.

        Raises:
            ldk_core.errors.ServiceError: ``invalid_request`` when the file is
                malformed or has no extractable text.
        """
        ...
