"""What every FastAPI service gets: logging, correlation ids, one error shape.

``install_service(app, ...)`` is the only call a service makes. Afterwards:

- every log line is structured and carries ``service`` and ``correlation_id``;
- every response has ``X-Request-ID``;
- every error, whether a ``ServiceError``, a framework ``HTTPException``, a
  request validation failure or an unhandled exception, is the envelope in
  ``ldk_core.errors``: ``{"error": {"code", "message", "details"?}}``.

Imports FastAPI, so only the HTTP services use it (not mcp-service).
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ldk_core.config import CoreSettings
from ldk_core.errors import ErrorCode, ServiceError, code_for_status
from ldk_core.observability import CorrelationIdMiddleware, configure_logging, get_logger
from ldk_core.observability.correlation import ASGIApp, Message, Receive, Scope, Send

_log = get_logger(__name__)


def install_service(app: FastAPI, *, service: str, settings: CoreSettings) -> None:
    """Configure logging and attach the middleware and error handlers to ``app``."""
    configure_logging(service=service, level=settings.log_level, fmt=settings.log_format)
    app.add_exception_handler(ServiceError, _service_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    # Added first, so it sits inside the correlation middleware and unhandled
    # errors are logged and answered while the request id is still bound.
    app.add_middleware(_UnhandledErrorMiddleware)
    app.add_middleware(CorrelationIdMiddleware)


def envelope(error: ServiceError, status: int | None = None) -> JSONResponse:
    """Render ``error`` as the standard JSON response."""
    return JSONResponse(
        error.to_body(), status_code=status or error.status, headers=dict(error.headers)
    )


async def _service_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ServiceError)
    if exc.status >= 500:
        _log.warning("request failed", code=exc.code.value, error=exc.message)
    return envelope(exc)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    error = ServiceError(
        code_for_status(exc.status_code),
        str(exc.detail),
        headers=exc.headers,
    )
    # Keep the framework's status (405 stays 405); the code says what kind.
    return envelope(error, exc.status_code)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        {"path": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return envelope(
        ServiceError(ErrorCode.INVALID_REQUEST, "Request validation failed", details=details)
    )


class _UnhandledErrorMiddleware:
    """Turn an unexpected exception into a logged, generic 500 envelope."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            _log.exception("unhandled error", path=scope.get("path"))
            if started:
                raise  # Too late to send a response; let the server close it.
            response = envelope(ServiceError(ErrorCode.INTERNAL, "Something went wrong on our end"))
            await response(scope, receive, send)


def error_detail(body: Any) -> str | None:
    """Pull a human-readable message out of an error body from any service.

    Understands the envelope and FastAPI's legacy ``{"detail": ...}``, so a
    client keeps working against a service that has not been upgraded.
    """
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    if isinstance(body.get("detail"), str):
        return body["detail"]
    return None
