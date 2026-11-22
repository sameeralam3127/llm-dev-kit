"""llm-dev-kit plugin: PDF loader (``loader.pdf``)."""

from __future__ import annotations

import io
import multiprocessing
import time
from collections.abc import Callable, Mapping
from typing import Any

from pypdf import PdfReader

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.plugins import Plugin, load_manifest
from ldk_core.ports import LoadedDocument, Page

DEFAULT_MAX_PAGES = 2000
DEFAULT_MAX_CHARS = 4_000_000
DEFAULT_MAX_SECONDS = 60.0
KILL_GRACE_SECONDS = 10.0
"""Extra time the child gets beyond ``max_seconds``, for starting up."""


class PdfLoader:
    """Extracts text with pypdf, one :class:`Page` per PDF page.

    Image-only pages give empty text; a file with no text at all is refused,
    since there would be nothing to index.

    File size says little about parsing cost: every page can point at one
    compressed content stream. So pages, extracted characters and time are
    capped, and parsing runs in a child process that is killed at the
    deadline, because a thread cannot be stopped.

    Args:
        max_pages: More pages than this is refused before any text is read.
        max_chars: Extraction stops once the text passes this many characters.
        max_seconds: Extraction stops after this long; the child process is
            killed a little later if it is stuck inside one page.
        isolate: Parse in a child process. Off only to debug the parser.
    """

    name = "pdf"
    media_types = frozenset({"application/pdf"})

    def __init__(
        self,
        *,
        max_pages: int = DEFAULT_MAX_PAGES,
        max_chars: int = DEFAULT_MAX_CHARS,
        max_seconds: float = DEFAULT_MAX_SECONDS,
        isolate: bool = True,
    ) -> None:
        self.max_pages = max_pages
        self.max_chars = max_chars
        self.max_seconds = max_seconds
        self.isolate = isolate

    def load(self, data: bytes, *, filename: str | None = None) -> LoadedDocument:
        """Parse PDF bytes.

        Raises:
            ServiceError: ``invalid_request`` for an unreadable file, one
                without extractable text, or one over a limit.
        """
        args = (data, self.max_pages, self.max_chars, self.max_seconds)
        if self.isolate:
            texts = run_isolated(_extract, args, timeout=self.max_seconds + KILL_GRACE_SECONDS)
        else:
            texts = _extract(*args)
        pages = [Page(number, text) for number, text in enumerate(texts, start=1)]
        document = LoadedDocument(pages=pages, metadata={"filename": filename} if filename else {})
        if not document.text.strip():
            raise ServiceError(ErrorCode.INVALID_REQUEST, "No readable text in PDF")
        return document


def _extract(data: bytes, max_pages: int, max_chars: int, max_seconds: float) -> list[str]:
    """Each page's text, stopping at the first limit passed."""
    deadline = time.monotonic() + max_seconds
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        count = len(reader.pages)
    except Exception as exc:  # pypdf raises many types on malformed input
        raise _unreadable(exc) from exc
    if count > max_pages:
        raise ServiceError(
            ErrorCode.INVALID_REQUEST,
            f"PDF has {count} pages; the limit is {max_pages}",
        )

    texts: list[str] = []
    total = 0
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise _unreadable(exc) from exc
        total += len(text)
        if total > max_chars:
            raise ServiceError(
                ErrorCode.INVALID_REQUEST,
                f"PDF has more than {max_chars:,} characters of text",
            )
        if time.monotonic() > deadline:
            raise _too_slow(max_seconds)
        texts.append(text)
    return texts


def _unreadable(exc: Exception) -> ServiceError:
    return ServiceError(ErrorCode.INVALID_REQUEST, f"Could not read PDF: {str(exc)[:200]}")


def _too_slow(seconds: float) -> ServiceError:
    return ServiceError(
        ErrorCode.INVALID_REQUEST, f"PDF took too long to read (limit {seconds:g} s)"
    )


def _child(conn: Any, target: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        conn.send(("ok", target(*args)))
    except ServiceError as exc:
        conn.send(("error", exc.code.value, exc.message))
    except Exception as exc:  # noqa: BLE001 - reported to the parent, not raised here
        conn.send(("error", ErrorCode.INVALID_REQUEST.value, _unreadable(exc).message))
    finally:
        conn.close()


def run_isolated(target: Callable[..., Any], args: tuple[Any, ...], *, timeout: float) -> Any:
    """Run ``target(*args)`` in a fresh process, killed after ``timeout`` seconds.

    ``ServiceError`` raised in the child is raised here with the same code and
    message. ``target`` must be importable by name (a module-level function).
    """
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(sender, target, args), daemon=True)
    process.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            raise _too_slow(
                timeout - KILL_GRACE_SECONDS if timeout > KILL_GRACE_SECONDS else timeout
            )
        status, *payload = receiver.recv()
    except EOFError as exc:
        raise ServiceError(
            ErrorCode.INVALID_REQUEST, "Could not read PDF: the parser stopped unexpectedly"
        ) from exc
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
        process.join(timeout=5)
    if status == "error":
        code, message = payload
        raise ServiceError(ErrorCode(code), message)
    return payload[0]


def _factory(config: Mapping[str, Any]) -> PdfLoader:
    return PdfLoader(
        max_pages=config.get("max_pages", DEFAULT_MAX_PAGES),
        max_chars=config.get("max_chars", DEFAULT_MAX_CHARS),
        max_seconds=config.get("max_seconds", DEFAULT_MAX_SECONDS),
    )


plugin = Plugin(load_manifest(__name__, "manifests/loader.pdf.json"), _factory)

__all__ = ["PdfLoader", "plugin", "run_isolated"]
