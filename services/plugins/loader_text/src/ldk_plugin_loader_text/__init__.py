"""llm-dev-kit plugin: plain text and Markdown loader (``loader.text``)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.plugins import Plugin, load_manifest
from ldk_core.ports import LoadedDocument, Page


class TextLoader:
    """Loads UTF-8 text and Markdown files as a single page.

    Markdown is left as raw text; rendering is not performed.
    """

    name = "text"
    media_types = frozenset({"text/plain", "text/markdown"})

    def load(self, data: bytes, *, filename: str | None = None) -> LoadedDocument:
        """Decode UTF-8 text bytes into a single-page document.

        Raises:
            ServiceError: ``invalid_request`` if the bytes are not valid UTF-8.
        """
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ServiceError(
                ErrorCode.INVALID_REQUEST, f"Could not decode text as UTF-8: {str(exc)[:200]}"
            ) from exc
        page = Page(1, text)
        document = LoadedDocument(pages=[page], metadata={"filename": filename} if filename else {})
        return document


def _factory(_: Mapping[str, Any]) -> TextLoader:
    return TextLoader()


plugin = Plugin(load_manifest(__name__, "manifests/loader.text.json"), _factory)

__all__ = ["TextLoader", "plugin"]
