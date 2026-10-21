"""Ingestion rules that need no I/O: retry timing and failure classification."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

from ldk_core.errors import ErrorCode, ServiceError

BACKOFF_BASE_SECONDS = 10.0
BACKOFF_CAP_SECONDS = 600.0


def backoff_seconds(attempt: int, rand: Callable[[], float] = random.random) -> float:
    """How long to wait before retry number ``attempt`` (1-based).

    Exponential (10 s, 20 s, 40 s … capped at 10 minutes) with jitter: each
    delay is scaled by a random factor in [0.5, 1.0), so a batch of jobs that
    failed together, say while the model was down, does not retry in lockstep
    and knock it over again.
    """
    exponential = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * 2 ** max(0, attempt - 1))
    return exponential * (0.5 + rand() / 2)


def is_permanent(error: BaseException) -> bool:
    """Whether retrying cannot help.

    A file the parser rejects (corrupt, encrypted, no text) fails the same way
    every time, so it fails at once. Anything else, such as the model gateway
    being unreachable or slow, may pass on a later attempt.
    """
    return isinstance(error, ServiceError) and error.code is ErrorCode.INVALID_REQUEST


def batched[T](items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    """Consecutive slices of at most ``size`` items."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    """A chunk ready to store: its text, where it came from, and its embedding."""

    ord: int
    text: str
    page: int | None
    embedding: list[float]
