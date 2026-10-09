"""Contract suites for the auth, rate-limit, tool and storage ports."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import jsonschema
import pytest

from ldk_core.errors import ErrorCode
from ldk_core.ports import AuthProvider, Principal, RateLimiter, StorageBackend, Tool
from ldk_core.testing.contracts._util import (
    REGISTRY_NAME,
    assert_service_error,
    run,
    unimplemented,
)


class AuthProviderContract:
    """Every :class:`AuthProvider` must pass this.

    Fixtures to provide:
        auth: The implementation under test.
        valid_credential: A credential it must accept.
        expected_subject: The ``subject`` that credential belongs to.
        invalid_credentials: Credentials it claims (``accepts`` is true) but
            must refuse: expired, wrong signature, revoked, and so on.
    """

    @pytest.fixture
    def auth(self) -> AuthProvider:
        """The implementation under test."""
        unimplemented("auth")

    @pytest.fixture
    def valid_credential(self) -> str:
        """A credential that authenticates."""
        unimplemented("valid_credential")

    @pytest.fixture
    def expected_subject(self) -> str:
        """Who ``valid_credential`` belongs to."""
        unimplemented("expected_subject")

    @pytest.fixture
    def invalid_credentials(self) -> list[str]:
        """Credentials that must be refused."""
        unimplemented("invalid_credentials")

    def test_satisfies_the_protocol(self, auth: AuthProvider) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(auth, AuthProvider)
        assert REGISTRY_NAME.fullmatch(auth.name)

    def test_authenticates_a_valid_credential(
        self, auth: AuthProvider, valid_credential: str, expected_subject: str
    ) -> None:
        """A good credential yields the right principal."""
        assert auth.accepts(valid_credential)
        principal = run(auth.authenticate(valid_credential))
        assert isinstance(principal, Principal)
        assert principal.subject == expected_subject

    def test_refuses_invalid_credentials_without_detail(
        self, auth: AuthProvider, invalid_credentials: list[str]
    ) -> None:
        """Every refusal is ``unauthorized`` and never echoes the credential."""
        assert invalid_credentials, "provide at least one invalid credential"
        for credential in invalid_credentials:
            with pytest.raises(Exception) as info:
                run(auth.authenticate(credential))
            error = assert_service_error(info.value, ErrorCode.UNAUTHORIZED)
            assert credential not in error.message

    def test_does_not_claim_garbage(self, auth: AuthProvider) -> None:
        """``accepts`` leaves obviously foreign input to other providers."""
        assert not auth.accepts("")


class RateLimiterContract:
    """Every :class:`RateLimiter` must pass this.

    Fixtures to provide:
        limiter: The implementation under test.
        bucket: A bucket name it is configured for.
        capacity: That bucket's capacity. Refill must be slow enough that no
            token returns during the test (a minute or more per token).
    """

    @pytest.fixture
    def limiter(self) -> RateLimiter:
        """The implementation under test."""
        unimplemented("limiter")

    @pytest.fixture
    def bucket(self) -> str:
        """A configured bucket."""
        unimplemented("bucket")

    @pytest.fixture
    def capacity(self) -> int:
        """Capacity of ``bucket``; at least 2."""
        unimplemented("capacity")

    def test_satisfies_the_protocol(self, limiter: RateLimiter) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(limiter, RateLimiter)
        assert REGISTRY_NAME.fullmatch(limiter.name)

    def test_allows_up_to_capacity_then_refuses(
        self, limiter: RateLimiter, bucket: str, capacity: int
    ) -> None:
        """``remaining`` counts down; the next hit is refused with a retry hint."""
        for expected_remaining in range(capacity - 1, -1, -1):
            decision = run(limiter.hit(bucket, "user:a"))
            assert decision.allowed
            assert decision.limit == capacity
            assert decision.remaining == expected_remaining
        refused = run(limiter.hit(bucket, "user:a"))
        assert not refused.allowed
        assert refused.remaining == 0
        assert refused.retry_after is not None and refused.retry_after > 0

    def test_keys_are_independent(self, limiter: RateLimiter, bucket: str, capacity: int) -> None:
        """Exhausting one caller leaves another untouched."""
        for _ in range(capacity):
            run(limiter.hit(bucket, "user:a"))
        assert run(limiter.hit(bucket, "user:b")).allowed

    def test_a_refused_hit_costs_nothing(
        self, limiter: RateLimiter, bucket: str, capacity: int
    ) -> None:
        """Asking for more than is left is refused without spending what is left."""
        for _ in range(capacity - 1):
            run(limiter.hit(bucket, "user:a"))
        assert not run(limiter.hit(bucket, "user:a", cost=2)).allowed
        assert run(limiter.hit(bucket, "user:a", cost=1)).allowed


class ToolContract:
    """Every :class:`Tool` must pass this.

    Fixtures to provide:
        tool: The implementation under test.
        valid_arguments: Arguments that satisfy its schema and succeed.
        principal: Caller to invoke it as (defaults to an ordinary user).
    """

    @pytest.fixture
    def tool(self) -> Tool:
        """The implementation under test."""
        unimplemented("tool")

    @pytest.fixture
    def valid_arguments(self) -> Mapping[str, Any]:
        """Arguments for a successful call."""
        unimplemented("valid_arguments")

    @pytest.fixture
    def principal(self) -> Principal | None:
        """The caller; override for tools that need particular roles."""
        return Principal(subject="contract-user", kind="user", roles=frozenset({"user"}))

    def test_satisfies_the_protocol(self, tool: Tool) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(tool, Tool)

    def test_is_describable_to_a_model(self, tool: Tool) -> None:
        """Name, description and a valid object schema are what MCP clients see."""
        assert REGISTRY_NAME.fullmatch(tool.name)
        assert tool.description.strip()
        jsonschema.Draft202012Validator.check_schema(dict(tool.input_schema))
        assert tool.input_schema.get("type") == "object"

    def test_valid_arguments_match_the_schema(
        self, tool: Tool, valid_arguments: Mapping[str, Any]
    ) -> None:
        """The suite's own fixture is honest about the schema."""
        jsonschema.validate(dict(valid_arguments), dict(tool.input_schema))

    def test_result_is_json_serialisable(
        self, tool: Tool, valid_arguments: Mapping[str, Any], principal: Principal | None
    ) -> None:
        """Whatever comes back must cross the MCP wire as JSON."""
        result = run(tool.invoke(valid_arguments, principal=principal))
        json.dumps(result)


class StorageBackendContract:
    """Every :class:`StorageBackend` must pass this.

    Fixtures to provide:
        storage: A fresh, empty backend.
    """

    @pytest.fixture
    def storage(self) -> StorageBackend:
        """The implementation under test, empty."""
        unimplemented("storage")

    def test_satisfies_the_protocol(self, storage: StorageBackend) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(storage, StorageBackend)
        assert REGISTRY_NAME.fullmatch(storage.name)

    def test_round_trip_with_metadata(self, storage: StorageBackend) -> None:
        """What goes in comes out, with size and digest describing it."""
        data = b"%PDF-1.7 pretend"
        stored = run(storage.put("users/u1/doc.pdf", data, content_type="application/pdf"))
        assert stored.key == "users/u1/doc.pdf"
        assert stored.size == len(data)
        assert stored.content_type == "application/pdf"
        assert stored.sha256 == hashlib.sha256(data).hexdigest()
        assert run(storage.get("users/u1/doc.pdf")) == data
        assert run(storage.exists("users/u1/doc.pdf"))

    def test_put_replaces(self, storage: StorageBackend) -> None:
        """Writing a key twice keeps the second content."""
        run(storage.put("k", b"one", content_type="text/plain"))
        run(storage.put("k", b"two", content_type="text/plain"))
        assert run(storage.get("k")) == b"two"

    def test_missing_key_is_not_found(self, storage: StorageBackend) -> None:
        """Absent content is ``not_found``, not ``None`` or a raw OSError."""
        assert not run(storage.exists("nope"))
        with pytest.raises(Exception) as info:
            run(storage.get("nope"))
        assert_service_error(info.value, ErrorCode.NOT_FOUND)

    def test_delete_reports_whether_it_existed(self, storage: StorageBackend) -> None:
        """True the first time, False after."""
        run(storage.put("k", b"x", content_type="text/plain"))
        assert run(storage.delete("k")) is True
        assert run(storage.delete("k")) is False
        assert not run(storage.exists("k"))

    @pytest.mark.parametrize("key", ["/etc/passwd", "../escape", "a/../../b", "", "a//b"])
    def test_rejects_unsafe_keys(self, storage: StorageBackend, key: str) -> None:
        """Keys that are absolute, empty or escape the root are refused."""
        with pytest.raises(Exception) as info:
            run(storage.put(key, b"x", content_type="text/plain"))
        assert_service_error(info.value, ErrorCode.INVALID_REQUEST)
