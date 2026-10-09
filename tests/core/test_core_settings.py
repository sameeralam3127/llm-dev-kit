import pydantic
import pytest
from pydantic import Field

from ldk_core.config import CoreSettings, SettingsError, load_settings


class _ServiceSettings(CoreSettings):
    port: int = Field(default=8000, gt=0)
    upstream_url: str


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Keep a developer's real .env and shell from leaking into the tests.
    monkeypatch.chdir(tmp_path)
    for var in ("SERVICE_NAME", "LOG_LEVEL", "LOG_FORMAT", "PORT", "UPSTREAM_URL"):
        monkeypatch.delenv(var, raising=False)


def test_defaults() -> None:
    settings = load_settings(CoreSettings)
    assert (settings.service_name, settings.log_level, settings.log_format) == (
        "llm-dev-kit",
        "INFO",
        "json",
    )


def test_reads_upper_case_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("UPSTREAM_URL", "http://llm:8010")
    monkeypatch.setenv("PORT", "9000")
    settings = load_settings(_ServiceSettings)
    assert settings.log_level == "DEBUG"
    assert settings.port == 9000
    assert settings.upstream_url == "http://llm:8010"


def test_reads_dotenv(tmp_path) -> None:
    (tmp_path / ".env").write_text("UPSTREAM_URL=http://from-dotenv\n")
    assert load_settings(_ServiceSettings).upstream_url == "http://from-dotenv"


def test_reports_every_problem_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    monkeypatch.setenv("PORT", "-1")
    with pytest.raises(SettingsError) as info:
        load_settings(_ServiceSettings)
    message = str(info.value)
    assert message.startswith("Invalid environment configuration:")
    for var in ("LOG_LEVEL", "PORT", "UPSTREAM_URL"):
        assert f"  - {var}:" in message
    # The pydantic error is replaced, not chained, so startup output stays short.
    assert info.value.__cause__ is None


def test_settings_are_frozen() -> None:
    settings = load_settings(CoreSettings)
    with pytest.raises(pydantic.ValidationError):
        settings.log_level = "DEBUG"  # type: ignore[misc]
