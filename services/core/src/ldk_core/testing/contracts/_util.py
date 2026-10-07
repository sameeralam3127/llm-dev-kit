"""Small helpers shared by the contract suites."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Coroutine
from typing import Any, NoReturn

from ldk_core.errors import ErrorCode, ServiceError

REGISTRY_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")
"""Same rule as ``PluginManifest.name``."""


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run one coroutine to completion; suites stay free of async plugins."""
    return asyncio.run(coro)


async def collect[T](iterator: AsyncIterator[T]) -> list[T]:
    """Drain an async iterator into a list."""
    return [item async for item in iterator]


def unimplemented(fixture: str) -> NoReturn:
    """Fail clearly when a suite subclass forgot to provide a fixture."""
    raise NotImplementedError(f"Contract suite subclasses must override the `{fixture}` fixture")


def assert_service_error(error: BaseException, *codes: ErrorCode) -> ServiceError:
    """Assert ``error`` is a ServiceError, with one of ``codes`` if given."""
    assert isinstance(error, ServiceError), (
        f"expected ServiceError, got {type(error).__name__}: {error}"
    )
    if codes:
        assert error.code in codes, f"expected one of {[c.value for c in codes]}, got {error.code}"
    return error
