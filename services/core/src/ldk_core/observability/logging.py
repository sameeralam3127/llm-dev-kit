"""Structured logging for every Python service.

One call to :func:`configure_logging` at startup makes both ``structlog``
loggers and the standard library (uvicorn, httpx, third-party code) emit the
same format: JSON in containers, coloured key/value lines on a terminal.
Every line carries the service name and, inside a request, its correlation
id.

Prompts and document text must never be logged as values. That rule is
enforced by review now and by ``DEBUG_LOG_PROMPTS`` in Phase 6.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from ldk_core.config.settings import LogFormat, LogLevel
from ldk_core.observability.correlation import get_correlation_id


def configure_logging(*, service: str, level: LogLevel = "INFO", fmt: LogFormat = "json") -> None:
    """Configure structlog and the stdlib root logger. Safe to call again.

    Args:
        service: Stamped on every line as ``service``.
        level: Minimum level emitted, for both structlog and stdlib loggers.
        fmt: ``"json"`` (one object per line) or ``"console"`` (human-readable).
    """
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _ServiceStamp(service),
        _add_correlation_id,
    ]
    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.processors.StackInfoRenderer(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ],
    )
    handler = _StderrHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # uvicorn installs its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structured logger; pass ``__name__`` to record the module."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


class _StderrHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Write to whatever ``sys.stderr`` is at emit time.

    A plain ``StreamHandler(sys.stderr)`` keeps the stream object it was given,
    so output is lost once something swaps ``sys.stderr`` (test capture,
    reconfigured stdio).
    """

    def __init__(self) -> None:
        super().__init__(sys.stderr)

    @property
    def stream(self) -> Any:
        """The current ``sys.stderr``."""
        return sys.stderr

    @stream.setter
    def stream(self, _: Any) -> None:
        """Ignore assignments; the stream is always looked up live."""


class _ServiceStamp:
    """Processor that adds ``service`` to every event."""

    def __init__(self, service: str) -> None:
        self.service = service

    def __call__(self, _: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", self.service)
        return event_dict


def _add_correlation_id(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """Processor that adds the current request's ``correlation_id``, if any."""
    cid = get_correlation_id()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict
