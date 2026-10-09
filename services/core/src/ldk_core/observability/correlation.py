"""Request correlation ids.

Every request gets one id that follows it through every service and appears
on every log line written while handling it. The gateway or the web app may
send one in ``X-Request-ID``; otherwise the first service to see the request
mints it. The id is echoed back on the response so a user-visible error can be
matched to its logs.

:class:`CorrelationIdMiddleware` is plain ASGI, so ``ldk_core`` does not
depend on FastAPI or Starlette; any ASGI app can wrap it.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable, Iterator, MutableMapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

HEADER = "x-request-id"
"""Header carrying the id, lower-case as ASGI presents it."""

_SAFE_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_current: ContextVar[str | None] = ContextVar("ldk_correlation_id", default=None)

Message = MutableMapping[str, Any]
Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def new_correlation_id() -> str:
    """Mint a fresh id (32 hex characters)."""
    return uuid.uuid4().hex


def get_correlation_id() -> str | None:
    """Return the id bound to the current request, or ``None`` outside one."""
    return _current.get()


@contextmanager
def correlation_scope(correlation_id: str | None = None) -> Iterator[str]:
    """Bind an id for the duration of a block; mints one if none is given.

    Use it for work that does not arrive over HTTP, such as a queued ingest
    job, so its logs still carry an id.
    """
    cid = correlation_id or new_correlation_id()
    token = _current.set(cid)
    try:
        yield cid
    finally:
        _current.reset(token)


def accept_incoming(value: str | None) -> str | None:
    """Return ``value`` if it is safe to reuse as an id, else ``None``.

    Incoming ids are client-controlled and end up in logs, so anything outside
    a conservative character set or over 128 characters is replaced rather
    than trusted.
    """
    if value and _SAFE_ID.fullmatch(value):
        return value
    return None


class CorrelationIdMiddleware:
    """ASGI middleware that binds a correlation id to each HTTP request.

    Reuses a well-formed incoming ``X-Request-ID``, otherwise mints one, and
    sets the header on the response.

    Args:
        app: The ASGI application to wrap.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI connection; non-HTTP scopes pass straight through."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header(scope, HEADER)
        with correlation_scope(accept_incoming(incoming)) as cid:

            async def send_with_id(message: Message) -> None:
                if message["type"] == "http.response.start":
                    headers = [
                        (k, v)
                        for k, v in message.get("headers", [])
                        if k.lower() != b"x-request-id"
                    ]
                    headers.append((HEADER.encode(), cid.encode()))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_with_id)


def _header(scope: Scope, name: str) -> str | None:
    """Return the first value of header ``name`` from an ASGI scope."""
    wanted = name.encode()
    for key, value in scope.get("headers", []):
        if key.lower() == wanted:
            return bytes(value).decode("latin-1")
    return None
