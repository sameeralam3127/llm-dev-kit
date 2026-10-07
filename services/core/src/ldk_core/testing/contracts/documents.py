"""Contract suites for :class:`DocumentLoader` and :class:`Chunker`."""

from __future__ import annotations

import pytest

from ldk_core.errors import ErrorCode
from ldk_core.ports import Chunker, DocumentLoader, LoadedDocument, Page
from ldk_core.testing.contracts._util import REGISTRY_NAME, assert_service_error, unimplemented


class DocumentLoaderContract:
    """Every :class:`DocumentLoader` must pass this.

    Fixtures to provide:
        loader: The implementation under test.
        sample: Bytes of a valid file in the loader's format.
        expected_text: A phrase that must appear in the extracted text.
        malformed: Bytes the loader must reject.
    """

    @pytest.fixture
    def loader(self) -> DocumentLoader:
        """The implementation under test."""
        unimplemented("loader")

    @pytest.fixture
    def sample(self) -> bytes:
        """A valid file."""
        unimplemented("sample")

    @pytest.fixture
    def expected_text(self) -> str:
        """A phrase present in ``sample``."""
        unimplemented("expected_text")

    @pytest.fixture
    def malformed(self) -> bytes:
        """A file that cannot be parsed."""
        unimplemented("malformed")

    def test_satisfies_the_protocol(self, loader: DocumentLoader) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(loader, DocumentLoader)

    def test_identifies_itself(self, loader: DocumentLoader) -> None:
        """A registry-safe name and at least one well-formed MIME type."""
        assert REGISTRY_NAME.fullmatch(loader.name)
        assert loader.media_types
        assert all("/" in t and t == t.lower() for t in loader.media_types)

    def test_extracts_text(self, loader: DocumentLoader, sample: bytes, expected_text: str) -> None:
        """The known phrase survives extraction."""
        document = loader.load(sample, filename="sample")
        assert isinstance(document, LoadedDocument)
        assert expected_text in document.text

    def test_pages_are_numbered_from_one_without_gaps(
        self, loader: DocumentLoader, sample: bytes
    ) -> None:
        """Citations rely on page numbers matching the source."""
        pages = loader.load(sample).pages
        assert [p.number for p in pages] == list(range(1, len(pages) + 1))

    def test_rejects_malformed_input(self, loader: DocumentLoader, malformed: bytes) -> None:
        """Bad uploads are the caller's fault: ``invalid_request``, not a crash."""
        with pytest.raises(Exception) as info:
            loader.load(malformed, filename="broken")
        assert_service_error(info.value, ErrorCode.INVALID_REQUEST)


_PROSE = (
    "Local-first software keeps the primary copy of data on the user's own "
    "machine. Sync is an optimisation, not a dependency. "
)
DOCUMENTS: dict[str, LoadedDocument] = {
    "single_page": LoadedDocument(pages=[Page(1, _PROSE * 12)]),
    "multi_page": LoadedDocument(
        pages=[Page(1, _PROSE * 6), Page(2, ""), Page(3, "Page three stands alone. " * 30)]
    ),
    "tiny": LoadedDocument(pages=[Page(1, "Just one short sentence.")]),
    # Every word distinct, so dropping any span of text is detectable.
    "unique_words": LoadedDocument(
        pages=[Page(n, " ".join(f"p{n}w{i}" for i in range(150))) for n in (1, 2)]
    ),
}
"""Documents every chunker is exercised on."""


class ChunkerContract:
    """Every :class:`Chunker` must pass this.

    Fixtures to provide:
        chunker: The implementation under test, configured as it would be in
            production.
    """

    @pytest.fixture
    def chunker(self) -> Chunker:
        """The implementation under test."""
        unimplemented("chunker")

    @pytest.fixture(params=sorted(DOCUMENTS))
    def document(self, request: pytest.FixtureRequest) -> LoadedDocument:
        """Each of :data:`DOCUMENTS` in turn."""
        return DOCUMENTS[request.param]

    def test_satisfies_the_protocol(self, chunker: Chunker) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(chunker, Chunker)
        assert REGISTRY_NAME.fullmatch(chunker.name)

    def test_no_empty_chunks_and_contiguous_indexes(
        self, chunker: Chunker, document: LoadedDocument
    ) -> None:
        """Indexes run 0..n-1 in order and every chunk has text."""
        chunks = chunker.chunk(document)
        assert chunks
        assert [c.index for c in chunks] == list(range(len(chunks)))
        assert all(c.text.strip() for c in chunks)

    def test_is_deterministic(self, chunker: Chunker, document: LoadedDocument) -> None:
        """Re-indexing the same document yields the same chunks (stable ids)."""
        assert chunker.chunk(document) == chunker.chunk(document)

    def test_drops_no_words(self, chunker: Chunker, document: LoadedDocument) -> None:
        """Every word of the source appears in some chunk."""
        covered = {w for c in chunker.chunk(document) for w in c.text.split()}
        assert set(document.text.split()) <= covered

    def test_pages_point_at_real_pages(self, chunker: Chunker, document: LoadedDocument) -> None:
        """A chunk's page, when set, is a page of the document that has text."""
        pages_with_text = {p.number for p in document.pages if p.text.strip()}
        for chunk in chunker.chunk(document):
            assert chunk.page is None or chunk.page in pages_with_text

    def test_empty_document_has_no_chunks(self, chunker: Chunker) -> None:
        """Nothing to index means nothing returned, not an empty chunk."""
        assert chunker.chunk(LoadedDocument(pages=[Page(1, "   ")])) == []
        assert chunker.chunk(LoadedDocument(pages=[])) == []
