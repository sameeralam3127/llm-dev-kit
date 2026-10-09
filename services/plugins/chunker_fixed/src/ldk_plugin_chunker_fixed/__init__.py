"""llm-dev-kit plugin: fixed-size window chunker (``chunker.fixed``).

This is the original ``rag_service.pdf.chunk_text`` behind the
:class:`~ldk_core.ports.Chunker` port, producing exactly the same chunks.
Structure-aware chunkers (recursive, markdown, sentence) arrive in Phase 5.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from typing import Any

from ldk_core.plugins import Plugin, load_manifest
from ldk_core.ports import LoadedDocument, TextChunk


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split ``text`` into stripped windows of ``chunk_size`` characters.

    Each window starts ``chunk_size - overlap`` characters after the previous
    one; windows that are only whitespace are dropped.

    Raises:
        ValueError: ``chunk_size`` is not positive, or ``overlap`` is outside
            ``[0, chunk_size)``.
    """
    return [text for _, text in _windows(text, chunk_size, overlap)]


class FixedWindowChunker:
    """Fixed-size character windows over the whole document.

    Windows can span pages; each chunk is attributed to the page its first
    non-space character is on.

    Args:
        size: Window length in characters.
        overlap: Characters shared by consecutive windows.
    """

    name = "fixed"

    def __init__(self, size: int = 500, overlap: int = 50) -> None:
        _validate(size, overlap)
        self.size = size
        self.overlap = overlap

    def chunk(self, document: LoadedDocument) -> list[TextChunk]:
        """Split ``document`` exactly as :func:`split_text` splits its text."""
        starts: list[int] = []
        numbers: list[int] = []
        offset = 0
        for page in document.pages:
            if not page.text:
                continue
            starts.append(offset)
            numbers.append(page.number)
            offset += len(page.text) + 1  # LoadedDocument.text joins with "\n"

        def page_at(position: int) -> int | None:
            index = bisect_right(starts, position) - 1
            return numbers[index] if index >= 0 else None

        return [
            TextChunk(index=i, text=text, page=page_at(position))
            for i, (position, text) in enumerate(_windows(document.text, self.size, self.overlap))
        ]


def _validate(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")


def _windows(text: str, chunk_size: int, overlap: int) -> list[tuple[int, str]]:
    """``(position of first non-space character, stripped text)`` per window."""
    _validate(chunk_size, overlap)
    windows: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        raw = text[start : start + chunk_size]
        stripped = raw.strip()
        if stripped:
            windows.append((start + len(raw) - len(raw.lstrip()), stripped))
        start += chunk_size - overlap
    return windows


def _factory(config: Mapping[str, Any]) -> FixedWindowChunker:
    return FixedWindowChunker(config.get("size", 500), config.get("overlap", 50))


plugin = Plugin(load_manifest(__name__, "manifests/chunker.fixed.json"), _factory)

__all__ = ["FixedWindowChunker", "plugin", "split_text"]
