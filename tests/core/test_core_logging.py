import json
import logging

import pytest
import structlog

from ldk_core.observability import configure_logging, correlation_scope, get_logger


@pytest.fixture(autouse=True)
def _restore_root_logger():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    structlog.reset_defaults()
    root.handlers[:] = handlers
    root.setLevel(level)


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().err.splitlines() if line]


def test_structlog_lines_are_json_with_service_and_correlation_id(capsys) -> None:
    configure_logging(service="rag-service", level="INFO", fmt="json")
    with correlation_scope("req-1"):
        get_logger("rag_service.chat").info("retrieved", chunks=3)

    (line,) = _lines(capsys)
    assert line["event"] == "retrieved"
    assert line["chunks"] == 3
    assert line["service"] == "rag-service"
    assert line["correlation_id"] == "req-1"
    assert line["level"] == "info"
    assert line["logger"] == "rag_service.chat"
    assert line["timestamp"].endswith("Z")


def test_stdlib_loggers_share_the_format(capsys) -> None:
    configure_logging(service="llm-service", fmt="json")
    with correlation_scope("req-2"):
        logging.getLogger("uvicorn.error").warning("upstream slow")

    (line,) = _lines(capsys)
    assert line["event"] == "upstream slow"
    assert line["service"] == "llm-service"
    assert line["correlation_id"] == "req-2"
    assert line["level"] == "warning"


def test_level_filters_both_kinds(capsys) -> None:
    configure_logging(service="s", level="WARNING", fmt="json")
    get_logger("a").info("hidden")
    logging.getLogger("b").info("hidden")
    get_logger("a").warning("shown")

    assert [line["event"] for line in _lines(capsys)] == ["shown"]


def test_no_correlation_id_outside_a_request(capsys) -> None:
    configure_logging(service="s", fmt="json")
    get_logger().info("startup")
    (line,) = _lines(capsys)
    assert "correlation_id" not in line


def test_exceptions_are_rendered(capsys) -> None:
    configure_logging(service="s", fmt="json")
    try:
        raise ValueError("boom")
    except ValueError:
        get_logger().exception("failed")
    (line,) = _lines(capsys)
    assert "ValueError: boom" in line["exception"]


def test_console_format_is_human_readable(capsys) -> None:
    configure_logging(service="s", fmt="console")
    get_logger().info("hello", user="u1")
    err = capsys.readouterr().err
    assert "hello" in err
    assert "user=u1" in err
    with pytest.raises(json.JSONDecodeError):
        json.loads(err.splitlines()[0])
