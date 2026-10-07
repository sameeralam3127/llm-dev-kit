"""Fail-fast service configuration.

The Python counterpart of ``web/src/lib/env.ts``: every service declares its
settings as a subclass of :class:`CoreSettings` and loads them once at startup
with :func:`load_settings`. A bad or missing value stops the process with one
message that names every offending variable, instead of surfacing later as a
500 halfway through a stream.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "console"]


class CoreSettings(BaseSettings):
    """Settings every service shares. Subclass to add service-specific ones.

    Values come from the environment, then ``.env``. Each field reads the
    upper-case variable of the same name (``LOG_LEVEL`` for ``log_level``).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    service_name: str = Field(
        default="llm-dev-kit",
        min_length=1,
        description="Name stamped on every log line and, later, every trace.",
    )
    log_level: LogLevel = Field(default="INFO", description="Minimum level that is emitted.")
    log_format: LogFormat = Field(
        default="json",
        description="'json' for machines (the default in containers), 'console' for humans.",
    )


class SettingsError(RuntimeError):
    """Raised by :func:`load_settings` when the environment is invalid.

    The message lists every problem at once, one per line, so an operator
    fixes them in a single pass.
    """


def load_settings[S: CoreSettings](cls: type[S]) -> S:
    """Instantiate ``cls`` from the environment or fail with a readable error.

    Args:
        cls: The settings class to load, usually a :class:`CoreSettings`
            subclass owned by the service.

    Returns:
        The validated, frozen settings.

    Raises:
        SettingsError: One or more variables are missing or malformed.
    """
    try:
        return cls()
    except ValidationError as exc:
        lines = [
            f"  - {_env_name(err['loc'])}: {err['msg']}" for err in exc.errors(include_url=False)
        ]
        raise SettingsError("Invalid environment configuration:\n" + "\n".join(lines)) from None


def _env_name(loc: tuple[int | str, ...]) -> str:
    """Render a validation location as the environment variable an operator sets."""
    return "__".join(str(part) for part in loc).upper() or "<settings>"
