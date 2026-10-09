"""Deprecated: the PDF loader and the chunker are plugins now.

These two functions keep the old call signatures working by delegating to
``loader.pdf`` and ``chunker.fixed``. rag-service itself no longer uses
them; they go when Phase 5 (#15) replaces the ingestion path.
"""

from typing import BinaryIO

from ldk_core.errors import ServiceError
from ldk_plugin_chunker_fixed import split_text
from ldk_plugin_loader_pdf import PdfLoader


def load_pdf(file: BinaryIO) -> str:
    try:
        return PdfLoader().load(file.read()).text
    except ServiceError as exc:
        raise ValueError(exc.message) from exc


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    return split_text(text, chunk_size, overlap)
