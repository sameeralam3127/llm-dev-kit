"""loader.pdf refuses PDFs that cost far more to parse than their size says.

Every page of a PDF can point at one compressed content stream, so a file of a
few KB can take minutes of CPU and yield millions of characters. The loader
caps pages, characters and time, and parses in a child process it can kill.
"""

import time

import pytest
from pdfs import make_pdf, make_shared_stream_pdf

from ldk_core.errors import ErrorCode, ServiceError
from ldk_plugin_loader_pdf import PdfLoader, plugin, run_isolated


def _refused(loader: PdfLoader, data: bytes, match: str) -> float:
    started = time.monotonic()
    with pytest.raises(ServiceError, match=match) as caught:
        loader.load(data)
    assert caught.value.code is ErrorCode.INVALID_REQUEST
    return time.monotonic() - started


def test_a_small_file_with_shared_streams_is_cheap_to_refuse() -> None:
    bomb = make_shared_stream_pdf(pages=400)
    assert len(bomb) < 100_000
    elapsed = _refused(PdfLoader(max_chars=50_000), bomb, "characters")
    assert elapsed < 10


def test_too_many_pages_is_refused_before_any_text_is_extracted() -> None:
    elapsed = _refused(PdfLoader(max_pages=50), make_shared_stream_pdf(pages=51), "51 pages")
    assert elapsed < 10


def test_parsing_stops_at_the_time_limit() -> None:
    bomb = make_shared_stream_pdf(pages=2000, repeats=400)
    elapsed = _refused(PdfLoader(max_seconds=1, max_chars=10**9), bomb, "too long")
    assert elapsed < 10


def test_an_ordinary_pdf_still_loads() -> None:
    document = PdfLoader().load(make_pdf(["one", "", "three"]), filename="r.pdf")
    assert [page.text for page in document.pages] == ["one", "", "three"]


def test_a_stuck_parser_is_killed_at_the_deadline() -> None:
    started = time.monotonic()
    with pytest.raises(ServiceError, match="too long"):
        run_isolated(time.sleep, (30,), timeout=1)
    assert time.monotonic() - started < 5


def test_errors_in_the_child_keep_their_meaning() -> None:
    with pytest.raises(ServiceError, match="Could not read PDF") as caught:
        PdfLoader().load(b"%PDF-1.4\nnot a pdf at all")
    assert caught.value.code is ErrorCode.INVALID_REQUEST


def test_limits_are_plugin_configuration() -> None:
    loader = plugin.factory({"max_pages": 10, "max_chars": 1000, "max_seconds": 5})
    assert (loader.max_pages, loader.max_chars, loader.max_seconds) == (10, 1000, 5)
    defaults = plugin.factory({})
    assert (defaults.max_pages, defaults.max_chars, defaults.max_seconds) == (2000, 4_000_000, 60)
