"""Reference loader and chunker, proving the suites run and pass."""

import pytest

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import LoadedDocument, Page, TextChunk
from ldk_core.testing.contracts import ChunkerContract, DocumentLoaderContract


class PlainTextLoader:
    """UTF-8 text; a form feed separates pages."""

    name = "text"
    media_types = frozenset({"text/plain"})

    def load(self, data: bytes, *, filename: str | None = None) -> LoadedDocument:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ServiceError(ErrorCode.INVALID_REQUEST, "File is not UTF-8 text") from None
        if not text.strip():
            raise ServiceError(ErrorCode.INVALID_REQUEST, "File has no text")
        return LoadedDocument(
            pages=[Page(n, part.strip()) for n, part in enumerate(text.split("\f"), start=1)]
        )


class WordWindowChunker:
    """Windows of ``size`` words overlapping by ``overlap``, never crossing a page."""

    name = "word_window"

    def __init__(self, size: int = 20, overlap: int = 5) -> None:
        self.size, self.overlap = size, overlap

    def chunk(self, document: LoadedDocument) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for page in document.pages:
            words = page.text.split()
            for start in range(0, len(words), self.size - self.overlap):
                window = words[start : start + self.size]
                chunks.append(TextChunk(len(chunks), " ".join(window), page.number))
                if start + self.size >= len(words):
                    break
        return chunks


class TestPlainTextLoader(DocumentLoaderContract):
    @pytest.fixture
    def loader(self) -> PlainTextLoader:
        return PlainTextLoader()

    @pytest.fixture
    def sample(self) -> bytes:
        return b"First page about sovereignty.\fSecond page."

    @pytest.fixture
    def expected_text(self) -> str:
        return "about sovereignty"

    @pytest.fixture
    def malformed(self) -> bytes:
        return b"\xff\xfe\x00not utf-8"


class TestWordWindowChunker(ChunkerContract):
    @pytest.fixture
    def chunker(self) -> WordWindowChunker:
        return WordWindowChunker()
