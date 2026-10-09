import asyncio
from typing import Any

import pytest

from ldk_core.observability.correlation import (
    CorrelationIdMiddleware,
    accept_incoming,
    correlation_scope,
    get_correlation_id,
)


def _run(app: Any, scope: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str | None]]:
    """Drive the middleware once; return sent messages and ids seen by the app."""
    sent: list[dict[str, Any]] = []
    seen: list[str | None] = []

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        seen.append(get_correlation_id())
        if scope["type"] == "http":
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"x-request-id", b"stale"), (b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"ok"})

    async def receive() -> dict[str, Any]:
        return {"type": "http.request"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(app(inner)(scope, receive, send))
    return sent, seen


def _http(headers: list[tuple[bytes, bytes]] | None = None) -> dict[str, Any]:
    return {"type": "http", "headers": headers or []}


def _response_ids(sent: list[dict[str, Any]]) -> list[bytes]:
    start = next(m for m in sent if m["type"] == "http.response.start")
    return [v for k, v in start["headers"] if k == b"x-request-id"]


def test_mints_an_id_and_echoes_it_once() -> None:
    sent, seen = _run(CorrelationIdMiddleware, _http())
    (cid,) = seen
    assert cid and len(cid) == 32
    assert _response_ids(sent) == [cid.encode()]


def test_reuses_a_well_formed_incoming_id() -> None:
    sent, seen = _run(CorrelationIdMiddleware, _http([(b"X-Request-ID", b"gw-123.abc:9")]))
    assert seen == ["gw-123.abc:9"]
    assert _response_ids(sent) == [b"gw-123.abc:9"]


@pytest.mark.parametrize(
    "value",
    [b"has space", b"newline\ninjected", b"x" * 129, b"", "é".encode("latin-1")],
)
def test_replaces_an_unsafe_incoming_id(value: bytes) -> None:
    _, seen = _run(CorrelationIdMiddleware, _http([(b"x-request-id", value)]))
    (cid,) = seen
    assert cid is not None
    assert cid.encode() != value
    assert len(cid) == 32


def test_each_request_gets_its_own_id_and_none_leaks_after() -> None:
    _, first = _run(CorrelationIdMiddleware, _http())
    _, second = _run(CorrelationIdMiddleware, _http())
    assert first != second
    assert get_correlation_id() is None


def test_non_http_scopes_pass_through_untouched() -> None:
    _, seen = _run(CorrelationIdMiddleware, {"type": "lifespan"})
    assert seen == [None]


def test_correlation_scope_binds_and_restores() -> None:
    assert get_correlation_id() is None
    with correlation_scope("job-7") as outer:
        assert outer == "job-7"
        with correlation_scope() as inner:
            assert get_correlation_id() == inner != "job-7"
        assert get_correlation_id() == "job-7"
    assert get_correlation_id() is None


def test_accept_incoming() -> None:
    assert accept_incoming("abc-123") == "abc-123"
    assert accept_incoming(None) is None
    assert accept_incoming("a b") is None


def test_works_inside_a_real_fastapi_app() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/whoami")
    async def whoami() -> dict[str, str | None]:
        return {"correlation_id": get_correlation_id()}

    app.add_middleware(CorrelationIdMiddleware)
    client = TestClient(app)

    res = client.get("/whoami", headers={"X-Request-ID": "web-42"})
    assert res.json() == {"correlation_id": "web-42"}
    assert res.headers["x-request-id"] == "web-42"

    minted = client.get("/whoami")
    assert minted.headers["x-request-id"] == minted.json()["correlation_id"]
