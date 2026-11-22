"""ALLOW_LEGACY_ANONYMOUS makes callers without a credential administrators.

The services refuse to start with it on unless the gateway listens on
loopback only, so the escape hatch can never face a network.
"""

import pytest

from devkit_common.auth import build_authenticator, check_legacy_anonymous
from devkit_common.config import Settings
from ldk_core.config import SettingsError, load_settings


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)


def _settings(monkeypatch: pytest.MonkeyPatch, *, anonymous: str, bind: str | None) -> Settings:
    monkeypatch.setenv("ALLOW_LEGACY_ANONYMOUS", anonymous)
    if bind is None:
        monkeypatch.delenv("GATEWAY_BIND", raising=False)
    else:
        monkeypatch.setenv("GATEWAY_BIND", bind)
    return load_settings(Settings)


@pytest.mark.parametrize("bind", ["0.0.0.0", "192.168.1.20", "::", "[::]"])
def test_refuses_anonymous_access_on_a_network_interface(
    monkeypatch: pytest.MonkeyPatch, bind: str
) -> None:
    settings = _settings(monkeypatch, anonymous="true", bind=bind)
    with pytest.raises(SettingsError, match=r"ALLOW_LEGACY_ANONYMOUS.*GATEWAY_BIND"):
        check_legacy_anonymous(settings)


@pytest.mark.parametrize("bind", [None, "127.0.0.1", "127.0.0.2", "localhost", "::1", "[::1]"])
def test_allows_anonymous_access_on_loopback(
    monkeypatch: pytest.MonkeyPatch, bind: str | None
) -> None:
    check_legacy_anonymous(_settings(monkeypatch, anonymous="true", bind=bind))


def test_any_bind_is_fine_with_anonymous_access_off(monkeypatch: pytest.MonkeyPatch) -> None:
    check_legacy_anonymous(_settings(monkeypatch, anonymous="false", bind="0.0.0.0"))


def test_startup_fails_before_any_plugin_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, anonymous="true", bind="0.0.0.0")

    class Untouched:
        def configure(self, *args: object) -> None:
            raise AssertionError("plugins configured despite the refusal")

    with pytest.raises(SettingsError):
        build_authenticator(Untouched(), settings)  # type: ignore[arg-type]
