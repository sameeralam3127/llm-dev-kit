import re
from pathlib import Path

import pytest

from ldk_core.errors import (
    STATUS_BY_CODE,
    ErrorCode,
    ServiceError,
    bad_request,
    code_for_status,
    not_found,
    to_service_error,
)

HTTP_TS = Path(__file__).resolve().parents[2] / "web/src/server/http.ts"


def _ts_status_map() -> dict[str, int]:
    source = HTTP_TS.read_text()
    block = re.search(r"STATUS_BY_CODE[^{]*\{(.*?)\}", source, re.S)
    assert block, "STATUS_BY_CODE not found in http.ts"
    return {k: int(v) for k, v in re.findall(r"(\w+):\s*(\d{3})", block.group(1))}


def test_status_map_matches_the_web_app() -> None:
    # The envelope is a cross-language contract: a code must mean the same
    # status whichever service answered.
    assert {c.value: s for c, s in STATUS_BY_CODE.items()} == _ts_status_map()


def test_every_code_has_a_status() -> None:
    assert set(STATUS_BY_CODE) == set(ErrorCode)


def test_status_map_is_read_only() -> None:
    with pytest.raises(TypeError):
        STATUS_BY_CODE[ErrorCode.INTERNAL] = 200  # type: ignore[index]


def test_body_matches_web_envelope_and_omits_unset_details() -> None:
    assert not_found("Document").to_body() == {
        "error": {"code": "not_found", "message": "Document not found"}
    }
    err = bad_request("Request validation failed", [{"path": "name", "message": "Required"}])
    assert err.status == 400
    assert err.to_body()["error"]["details"] == [{"path": "name", "message": "Required"}]


def test_falsy_details_are_kept() -> None:
    assert ServiceError(ErrorCode.CONFLICT, "x", details=[]).to_body()["error"]["details"] == []


def test_headers_are_carried_for_the_handler() -> None:
    err = ServiceError(ErrorCode.RATE_LIMITED, "Slow down", headers={"Retry-After": "3"})
    assert err.status == 429
    assert err.headers == {"Retry-After": "3"}


def test_unknown_exceptions_become_generic_internal_errors() -> None:
    err = to_service_error(RuntimeError("password=hunter2 leaked in a traceback"))
    assert err.code is ErrorCode.INTERNAL
    assert err.status == 500
    assert "hunter2" not in err.message


def test_service_errors_pass_through_unchanged() -> None:
    original = not_found()
    assert to_service_error(original) is original


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, ErrorCode.INVALID_REQUEST),
        (401, ErrorCode.UNAUTHORIZED),
        (404, ErrorCode.NOT_FOUND),
        (408, ErrorCode.TIMEOUT),
        (422, ErrorCode.INVALID_REQUEST),
        (429, ErrorCode.RATE_LIMITED),
        (418, ErrorCode.INVALID_REQUEST),
        (500, ErrorCode.UPSTREAM_ERROR),
        (502, ErrorCode.UPSTREAM_ERROR),
        (503, ErrorCode.UPSTREAM_UNAVAILABLE),
        (504, ErrorCode.TIMEOUT),
        (529, ErrorCode.UPSTREAM_ERROR),
    ],
)
def test_code_for_status(status: int, code: ErrorCode) -> None:
    assert code_for_status(status) is code
