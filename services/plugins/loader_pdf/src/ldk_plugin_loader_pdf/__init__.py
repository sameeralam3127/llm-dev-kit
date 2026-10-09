"""llm-dev-kit plugin: PDF loader (``loader.pdf``)."""

from __future__ import annotations

import io
from collections.abc import Mapping
from typing import Any

from pypdf import PdfReader

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.plugins import Plugin, load_manifest
from ldk_core.ports import LoadedDocument, Page


class PdfLoader:
    """Extracts text with pypdf, one :class:`Page` per PDF page.

    Image-only pages give empty text; a file with no text at all is refused,
    since there would be nothing to index.
    """

    name = "pdf"
    media_types = frozenset({"application/pdf"})

    def load(self, data: bytes, *, filename: str | None = None) -> LoadedDocument:
        """Parse PDF bytes.

        Raises:
            ServiceError: ``invalid_request`` for an unreadable file or one
                without extractable text.
        """
        try:
            reader = PdfReader(io.BytesIO(data), strict=False)
            pages = [
                Page(number, page.extract_text() or "")
                for number, page in enumerate(reader.pages, start=1)
            ]
        except Exception as exc:  # pypdf raises many types on malformed input
            raise ServiceError(
                ErrorCode.INVALID_REQUEST, f"Could not read PDF: {str(exc)[:200]}"
            ) from exc
        document = LoadedDocument(pages=pages, metadata={"filename": filename} if filename else {})
        if not document.text.strip():
            raise ServiceError(ErrorCode.INVALID_REQUEST, "No readable text in PDF")
        return document


def _factory(_: Mapping[str, Any]) -> PdfLoader:
    return PdfLoader()


plugin = Plugin(load_manifest(__name__, "manifests/loader.pdf.json"), _factory)

__all__ = ["PdfLoader", "plugin"]
