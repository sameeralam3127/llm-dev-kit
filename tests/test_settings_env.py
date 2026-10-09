"""devkit_common.Settings as docker compose feeds it."""

import pytest

from devkit_common.config import Settings
from ldk_core.config import SettingsError, load_settings


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)


def test_empty_optionals_from_compose_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # compose renders `${EMBEDDING_DIMENSION:-}` as an empty string.
    monkeypatch.setenv("EMBEDDING_DIMENSION", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    settings = load_settings(Settings)
    assert settings.embedding_dimension is None
    assert settings.openai_api_key is None


def test_set_values_are_still_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1024")
    assert load_settings(Settings).embedding_dimension == 1024
    monkeypatch.setenv("EMBEDDING_DIMENSION", "-3")
    with pytest.raises(SettingsError, match="EMBEDDING_DIMENSION"):
        load_settings(Settings)


def test_api_keys_stay_out_of_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    assert "sk-secret-value" not in repr(load_settings(Settings))
