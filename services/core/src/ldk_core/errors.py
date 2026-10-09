"""The error envelope every Python service returns.

Mirrors ``web/src/server/http.ts`` so a client sees the same shape whichever
service answered::

    {"error": {"code": "not_found", "message": "Chat not found", "details": ...}}

Codes, not status numbers, are the contract: a handler raises
``ServiceError(ErrorCode.NOT_FOUND, ...)`` and the status follows from the
code. Keep ``ErrorCode`` and ``STATUS_BY_CODE`` in step with ``ApiErrorCode``
in the web app.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class ErrorCode(StrEnum):
    """Machine-readable failure categories shared with the web app."""

    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    UPSTREAM_ERROR = "upstream_error"
    TIMEOUT = "timeout"
    INTERNAL = "internal"


STATUS_BY_CODE: Mapping[ErrorCode, int] = MappingProxyType(
    {
        ErrorCode.UNAUTHORIZED: 401,
        ErrorCode.FORBIDDEN: 403,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.INVALID_REQUEST: 400,
        ErrorCode.CONFLICT: 409,
        ErrorCode.RATE_LIMITED: 429,
        ErrorCode.UPSTREAM_UNAVAILABLE: 503,
        ErrorCode.UPSTREAM_ERROR: 502,
        ErrorCode.TIMEOUT: 504,
        ErrorCode.INTERNAL: 500,
    }
)
"""HTTP status for each code. Read-only so no caller can remap a code."""


class ServiceError(Exception):
    """An expected failure that maps to a typed HTTP response.

    Raise it anywhere below a route; the service's exception handler turns it
    into the envelope. Anything else that escapes becomes ``internal`` with a
    generic message, so internals never leak to the client.

    Args:
        code: The failure category; determines the HTTP status.
        message: Human-readable and safe to show to the caller.
        details: Optional JSON-serialisable context, e.g. per-field
            validation errors.
        headers: Extra response headers, e.g. ``Retry-After`` for
            ``rate_limited``.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.headers: Mapping[str, str] = dict(headers or {})

    @property
    def status(self) -> int:
        """The HTTP status implied by :attr:`code`."""
        return STATUS_BY_CODE[self.code]

    def to_body(self) -> dict[str, Any]:
        """Return the JSON response body, omitting ``details`` when unset."""
        error: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}

    def __repr__(self) -> str:
        """Show code and message, which is what matters in logs and tests."""
        return f"ServiceError({self.code.value!r}, {self.message!r})"


def not_found(what: str = "Resource") -> ServiceError:
    """Build a ``not_found`` error, e.g. ``not_found("Document")``."""
    return ServiceError(ErrorCode.NOT_FOUND, f"{what} not found")


def bad_request(message: str, details: Any = None) -> ServiceError:
    """Build an ``invalid_request`` error with optional per-field details."""
    return ServiceError(ErrorCode.INVALID_REQUEST, message, details=details)


_CODE_BY_STATUS: Mapping[int, ErrorCode] = MappingProxyType(
    {
        # A 500 from elsewhere is their failure, not ours: upstream_error.
        **{s: c for c, s in STATUS_BY_CODE.items() if c is not ErrorCode.INTERNAL},
        408: ErrorCode.TIMEOUT,
        422: ErrorCode.INVALID_REQUEST,
    }
)


def code_for_status(status: int) -> ErrorCode:
    """Pick the error code for an HTTP status from an upstream or a framework.

    Exact matches use :data:`STATUS_BY_CODE` in reverse (plus 408 and 422).
    Any other 4xx is ``invalid_request`` and any other 5xx, 500 included, is
    ``upstream_error``: the failure happened on the other side.
    """
    if status in _CODE_BY_STATUS:
        return _CODE_BY_STATUS[status]
    return ErrorCode.INVALID_REQUEST if 400 <= status < 500 else ErrorCode.UPSTREAM_ERROR


def to_service_error(error: BaseException) -> ServiceError:
    """Map any exception to a ``ServiceError`` without leaking internals.

    A ``ServiceError`` passes through unchanged. Anything else becomes a
    generic ``internal`` error; the caller is responsible for logging the
    original before responding.
    """
    if isinstance(error, ServiceError):
        return error
    return ServiceError(ErrorCode.INTERNAL, "Something went wrong on our end")
