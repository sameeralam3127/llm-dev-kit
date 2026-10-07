"""Reference auth, rate limiter, tool and storage, proving the suites run and pass."""

import hashlib
import time
from collections.abc import Mapping
from typing import Any

import pytest

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import Principal, RateLimitDecision, StoredObject
from ldk_core.testing.contracts import (
    AuthProviderContract,
    RateLimiterContract,
    StorageBackendContract,
    ToolContract,
)


class StaticTokenAuth:
    name = "static"

    def __init__(self, tokens: Mapping[str, str]) -> None:
        self._tokens = dict(tokens)

    def accepts(self, credential: str) -> bool:
        return credential.startswith("tok-")

    async def authenticate(self, credential: str) -> Principal:
        subject = self._tokens.get(credential)
        if subject is None:
            raise ServiceError(ErrorCode.UNAUTHORIZED, "Invalid credential")
        return Principal(subject=subject, kind="api_key", roles=frozenset({"user"}))


class MemoryTokenBucket:
    name = "memory"

    def __init__(self, policies: Mapping[str, tuple[int, float]]) -> None:
        """``policies`` maps bucket -> (capacity, tokens refilled per second)."""
        self._policies = dict(policies)
        self._state: dict[tuple[str, str], tuple[float, float]] = {}

    async def hit(self, bucket: str, key: str, *, cost: int = 1) -> RateLimitDecision:
        capacity, rate = self._policies[bucket]
        now = time.monotonic()
        tokens, last = self._state.get((bucket, key), (float(capacity), now))
        tokens = min(capacity, tokens + (now - last) * rate)
        if tokens < cost:
            self._state[(bucket, key)] = (tokens, now)
            return RateLimitDecision(False, capacity, int(tokens), (cost - tokens) / rate)
        self._state[(bucket, key)] = (tokens - cost, now)
        return RateLimitDecision(True, capacity, int(tokens - cost))


class UpperTool:
    name = "upper"
    description = "Return the given text in upper case."
    input_schema: Mapping[str, Any] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def invoke(self, arguments: Mapping[str, Any], *, principal: Principal | None) -> Any:
        return {"text": str(arguments["text"]).upper()}


class MemoryStorage:
    name = "memory"

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, StoredObject]] = {}

    @staticmethod
    def _check(key: str) -> str:
        parts = key.split("/")
        if not key or key.startswith("/") or any(p in ("", ".", "..") for p in parts):
            raise ServiceError(ErrorCode.INVALID_REQUEST, "Invalid storage key")
        return key

    async def put(self, key: str, data: bytes, *, content_type: str) -> StoredObject:
        meta = StoredObject(
            self._check(key), len(data), content_type, hashlib.sha256(data).hexdigest()
        )
        self._objects[key] = (data, meta)
        return meta

    async def get(self, key: str) -> bytes:
        try:
            return self._objects[self._check(key)][0]
        except KeyError:
            raise ServiceError(ErrorCode.NOT_FOUND, "File not found") from None

    async def delete(self, key: str) -> bool:
        return self._objects.pop(self._check(key), None) is not None

    async def exists(self, key: str) -> bool:
        return self._check(key) in self._objects


class TestStaticTokenAuth(AuthProviderContract):
    @pytest.fixture
    def auth(self) -> StaticTokenAuth:
        return StaticTokenAuth({"tok-good": "user-1"})

    @pytest.fixture
    def valid_credential(self) -> str:
        return "tok-good"

    @pytest.fixture
    def expected_subject(self) -> str:
        return "user-1"

    @pytest.fixture
    def invalid_credentials(self) -> list[str]:
        return ["tok-bad", "tok-revoked"]


class TestMemoryTokenBucket(RateLimiterContract):
    @pytest.fixture
    def limiter(self) -> MemoryTokenBucket:
        return MemoryTokenBucket({"chat": (3, 1 / 60)})

    @pytest.fixture
    def bucket(self) -> str:
        return "chat"

    @pytest.fixture
    def capacity(self) -> int:
        return 3


class TestUpperTool(ToolContract):
    @pytest.fixture
    def tool(self) -> UpperTool:
        return UpperTool()

    @pytest.fixture
    def valid_arguments(self) -> Mapping[str, Any]:
        return {"text": "hello"}


class TestMemoryStorage(StorageBackendContract):
    @pytest.fixture
    def storage(self) -> MemoryStorage:
        return MemoryStorage()
