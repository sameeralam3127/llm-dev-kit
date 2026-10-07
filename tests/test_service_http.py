import json

import pytest
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from devkit_common.http import error_detail, install_service
from ldk_core.config import CoreSettings
from ldk_core.errors import ErrorCode, ServiceError


class Item(BaseModel):
    name: str
    count: int


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    app = FastAPI()
    install_service(app, service="test-service", settings=CoreSettings())

    @app.get("/missing")
    async def missing() -> None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Document not found")

    @app.get("/slow-down")
    async def slow_down() -> None:
        raise ServiceError(ErrorCode.RATE_LIMITED, "Slow down", headers={"Retry-After": "2"})

    @app.get("/legacy")
    async def legacy() -> None:
        raise HTTPException(status_code=409, detail="Already exists")

    @app.post("/items")
    async def create(item: Item) -> Item:
        return item

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    yield TestClient(app, raise_server_exceptions=False)
    structlog.reset_defaults()


def _error(res) -> dict:
    return res.json()["error"]


def test_service_error_becomes_the_envelope(client) -> None:
    res = client.get("/missing")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "not_found", "message": "Document not found"}}


def test_service_error_headers_are_sent(client) -> None:
    res = client.get("/slow-down")
    assert res.status_code == 429
    assert res.headers["retry-after"] == "2"


def test_http_exceptions_keep_their_status(client) -> None:
    res = client.get("/legacy")
    assert res.status_code == 409
    assert _error(res) == {"code": "conflict", "message": "Already exists"}

    unknown = client.get("/no-such-route")
    assert unknown.status_code == 404
    assert _error(unknown)["code"] == "not_found"

    wrong_method = client.delete("/missing")
    assert wrong_method.status_code == 405
    assert _error(wrong_method)["code"] == "invalid_request"


def test_validation_errors_list_each_field(client) -> None:
    res = client.post("/items", json={"name": "x", "count": "many"})
    assert res.status_code == 400
    error = _error(res)
    assert error["code"] == "invalid_request"
    assert error["details"] == [
        {
            "path": "body.count",
            "message": "Input should be a valid integer, unable to parse string as an integer",
        }
    ]


def test_unhandled_errors_are_generic_and_logged_with_the_request_id(client, capsys) -> None:
    res = client.get("/boom", headers={"X-Request-ID": "req-500"})
    assert res.status_code == 500
    assert res.json() == {
        "error": {"code": "internal", "message": "Something went wrong on our end"}
    }
    assert "hunter2" not in res.text
    assert res.headers["x-request-id"] == "req-500"

    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line]
    (logged,) = [line for line in lines if line["event"] == "unhandled error"]
    assert logged["correlation_id"] == "req-500"
    assert logged["service"] == "test-service"
    assert "hunter2" in logged["exception"]  # the log keeps what the client must not see


def test_every_response_has_a_request_id(client) -> None:
    assert client.post("/items", json={"name": "x", "count": 1}).headers["x-request-id"]
    assert client.get("/missing").headers["x-request-id"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"error": {"code": "x", "message": "envelope"}}, "envelope"),
        ({"detail": "legacy"}, "legacy"),
        ({"detail": [{"msg": "list"}]}, None),
        (["not", "a", "dict"], None),
    ],
)
def test_error_detail_reads_both_shapes(body, expected) -> None:
    assert error_detail(body) == expected
