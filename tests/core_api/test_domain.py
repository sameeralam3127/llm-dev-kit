"""Pure domain rules: no database, no HTTP."""

import uuid

from core_api.domain import api_keys
from core_api.domain.access import Caller, resolve

PEPPER = b"p" * 32


def test_a_key_is_shown_once_and_stored_as_an_hmac() -> None:
    new = api_keys.generate(PEPPER)
    assert new.plaintext.startswith("ldk_")
    assert api_keys.parse_prefix(new.plaintext) == new.prefix
    assert len(new.digest) == 32
    assert new.plaintext.encode() not in new.digest
    assert api_keys.matches(new.plaintext, new.digest, PEPPER)


def test_the_pepper_matters() -> None:
    new = api_keys.generate(PEPPER)
    assert not api_keys.matches(new.plaintext, new.digest, b"q" * 32)


def test_malformed_keys_have_no_prefix() -> None:
    for candidate in ("ldk_short_abc", "sk-ldk-abc", "ldk_ABCDEFGHIJKL_" + "Z" * 64, ""):
        assert api_keys.parse_prefix(candidate) is None


def test_members_get_their_roles_scopes() -> None:
    ws = uuid.uuid4()
    caller = Caller(user_id="u", via="session")
    assert resolve(caller, ws, "reader").scopes == {"chat"}
    assert resolve(caller, ws, "editor").scopes == {"chat", "ingest"}
    assert resolve(caller, ws, "owner").scopes == {"chat", "ingest", "manage"}


def test_non_members_get_nothing() -> None:
    assert resolve(Caller(user_id="u", via="session"), uuid.uuid4(), None) is None


def test_a_key_only_works_in_its_own_workspace() -> None:
    home, other = uuid.uuid4(), uuid.uuid4()
    key = Caller(user_id="u", via="api_key", key_workspace_id=home, key_scopes=frozenset({"chat"}))
    assert resolve(key, home, "owner") is not None
    assert resolve(key, other, "owner") is None


def test_demoting_the_owner_narrows_their_keys() -> None:
    ws = uuid.uuid4()
    key = Caller(
        user_id="u", via="api_key", key_workspace_id=ws, key_scopes=frozenset({"chat", "ingest"})
    )
    assert resolve(key, ws, "owner").scopes == {"chat", "ingest"}
    assert resolve(key, ws, "reader").scopes == {"chat"}


def test_backoff_doubles_up_to_a_cap_with_jitter() -> None:
    from core_api.domain.ingestion import backoff_seconds

    assert [backoff_seconds(n, rand=lambda: 0.0) for n in (1, 2, 3)] == [5.0, 10.0, 20.0]
    assert backoff_seconds(1, rand=lambda: 0.999) < 10.0
    assert backoff_seconds(30, rand=lambda: 0.0) == 300.0  # capped at 600 s, halved by jitter


def test_only_parser_rejections_are_permanent() -> None:
    from core_api.domain.ingestion import is_permanent
    from ldk_core.errors import ErrorCode, ServiceError

    assert is_permanent(ServiceError(ErrorCode.INVALID_REQUEST, "no text"))
    assert not is_permanent(ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "down"))
    assert not is_permanent(TimeoutError())
