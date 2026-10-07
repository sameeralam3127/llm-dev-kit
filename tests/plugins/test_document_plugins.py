"""loader.pdf and chunker.fixed: contracts, plus proof nothing changed."""

import io
import random
import string

import pytest
from pdfs import make_pdf
from pypdf import PdfReader

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import LoadedDocument, Page
from ldk_core.testing.contracts import ChunkerContract, DocumentLoaderContract
from ldk_plugin_chunker_fixed import FixedWindowChunker, split_text
from ldk_plugin_loader_pdf import PdfLoader
from rag_service.pdf import chunk_text, load_pdf


def _old_load_pdf(data: bytes) -> str:
    """rag_service.pdf.load_pdf as it was before v2."""
    reader = PdfReader(io.BytesIO(data), strict=False)
    return "\n".join(filter(None, (page.extract_text() for page in reader.pages)))


def _old_chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """rag_service.pdf.chunk_text as it was before v2."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


class TestPdfLoaderContract(DocumentLoaderContract):
    @pytest.fixture
    def loader(self) -> PdfLoader:
        return PdfLoader()

    @pytest.fixture
    def sample(self) -> bytes:
        return make_pdf(["Local-first means the data stays here.", "", "Page three text."])

    @pytest.fixture
    def expected_text(self) -> str:
        return "data stays here"

    @pytest.fixture
    def malformed(self) -> bytes:
        return b"%PDF-1.4\nthis is not really a pdf"


class TestFixedWindowChunkerContract(ChunkerContract):
    @pytest.fixture
    def chunker(self) -> FixedWindowChunker:
        return FixedWindowChunker()


def test_loader_text_matches_the_old_function() -> None:
    data = make_pdf(["First page.", "", "Third (bracketed) page."])
    assert PdfLoader().load(data).text == _old_load_pdf(data)


def test_loader_keeps_pages_and_filename() -> None:
    document = PdfLoader().load(make_pdf(["one", "", "three"]), filename="r.pdf")
    assert [(p.number, p.text) for p in document.pages] == [(1, "one"), (2, ""), (3, "three")]
    assert document.metadata == {"filename": "r.pdf"}


def test_loader_refuses_a_pdf_without_text() -> None:
    with pytest.raises(ServiceError) as info:
        PdfLoader().load(make_pdf(["", ""]))
    assert (info.value.code, info.value.message) == (
        ErrorCode.INVALID_REQUEST,
        "No readable text in PDF",
    )


@pytest.mark.parametrize("seed", range(20))
def test_chunks_are_identical_to_the_old_function(seed: int) -> None:
    rng = random.Random(seed)
    text = "".join(
        rng.choice(string.ascii_letters + "  \n\t.,") for _ in range(rng.randint(0, 3000))
    )
    size = rng.randint(1, 600)
    overlap = rng.randint(0, size - 1)
    expected = _old_chunk_text(text, size, overlap)
    assert split_text(text, size, overlap) == expected
    document = LoadedDocument(pages=[Page(1, text)])
    assert [c.text for c in FixedWindowChunker(size, overlap).chunk(document)] == expected


def test_chunks_are_attributed_to_the_page_they_start_on() -> None:
    document = LoadedDocument(pages=[Page(1, "a" * 30), Page(2, ""), Page(3, "b" * 30)])
    chunks = FixedWindowChunker(size=20, overlap=0).chunk(document)
    # text = 30 a's + "\n" + 30 b's: windows start at 0, 20, 40, 60
    assert [(c.text[:3], c.page) for c in chunks] == [
        ("aaa", 1),
        ("aaa", 1),
        ("bbb", 3),
        ("b", 3),
    ]


def test_invalid_window_settings_are_rejected() -> None:
    with pytest.raises(ValueError, match="overlap"):
        FixedWindowChunker(size=10, overlap=10)
    with pytest.raises(ValueError, match="positive"):
        split_text("abc", 0, 0)


def test_deprecated_shims_still_work() -> None:
    assert chunk_text("abcdefghij", chunk_size=4, overlap=1) == ["abcd", "defg", "ghij", "j"]
    assert load_pdf(io.BytesIO(make_pdf(["hello there"]))) == "hello there"
    with pytest.raises(ValueError, match="No readable text"):
        load_pdf(io.BytesIO(make_pdf([""])))
