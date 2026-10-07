"""The suites must fail broken implementations, or they prove nothing.

Each test takes a reference implementation, breaks one promise, and checks
that the matching suite test fails.
"""

from collections.abc import AsyncIterator, Sequence

import pytest
from memory_store import MemoryVectorStore
from test_document_contracts import WordWindowChunker
from test_llm_contracts import EchoProvider
from test_platform_contracts import MemoryStorage, MemoryTokenBucket, StaticTokenAuth

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import (
    CompletionRequest,
    LoadedDocument,
    Principal,
    RateLimitDecision,
    SearchResult,
    SearchScope,
    StoredObject,
    TextChunk,
)
from ldk_core.testing.contracts import (
    DOCUMENTS,
    AuthProviderContract,
    ChunkerContract,
    LLMProviderContract,
    RateLimiterContract,
    StorageBackendContract,
    VectorStoreContract,
)


class ScopeLeakingStore(MemoryVectorStore):
    """Ignores the scope: the cross-user leak Phase 5 exists to prevent."""

    async def search(
        self, embedding: Sequence[float], *, scope: SearchScope, top_k: int
    ) -> list[SearchResult]:
        everything = SearchScope(frozenset(self._collections), scope.user_id)
        return await super().search(embedding, scope=everything, top_k=top_k)


class WordDroppingChunker(WordWindowChunker):
    def chunk(self, document: LoadedDocument) -> list[TextChunk]:
        return super().chunk(document)[:1]


class TraversingStorage(MemoryStorage):
    @staticmethod
    def _check(key: str) -> str:
        return key

    async def put(self, key: str, data: bytes, *, content_type: str) -> StoredObject:
        return await super().put(key or "_", data, content_type=content_type)


class LeakyAuth(StaticTokenAuth):
    async def authenticate(self, credential: str) -> Principal:
        if credential not in self._tokens:
            raise ServiceError(ErrorCode.UNAUTHORIZED, f"Unknown token {credential}")
        return await super().authenticate(credential)


class GreedyLimiter(MemoryTokenBucket):
    """Charges for refused hits."""

    async def hit(self, bucket: str, key: str, *, cost: int = 1) -> RateLimitDecision:
        decision = await super().hit(bucket, key, cost=cost)
        if not decision.allowed:
            _, last = self._state[(bucket, key)]
            self._state[(bucket, key)] = (0.0, last)
        return decision


class RawErrorProvider(EchoProvider):
    async def complete(self, request: CompletionRequest) -> str:
        if request.model not in self._models:
            raise KeyError(request.model)
        return await super().complete(request)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        raise KeyError(request.model)
        yield ""  # pragma: no cover


# pytest.raises reports "did not raise" with its own Failed exception.
SUITE_FAILURE = (AssertionError, pytest.fail.Exception)


def test_vector_store_scope_leak_is_caught() -> None:
    with pytest.raises(SUITE_FAILURE):
        VectorStoreContract().test_scope_excludes_other_collections(ScopeLeakingStore())


def test_chunker_dropping_words_is_caught() -> None:
    with pytest.raises(SUITE_FAILURE):
        ChunkerContract().test_drops_no_words(WordDroppingChunker(), DOCUMENTS["unique_words"])


def test_storage_path_traversal_is_caught() -> None:
    with pytest.raises(SUITE_FAILURE):
        StorageBackendContract().test_rejects_unsafe_keys(TraversingStorage(), "../escape")


def test_auth_echoing_the_credential_is_caught() -> None:
    with pytest.raises(SUITE_FAILURE):
        AuthProviderContract().test_refuses_invalid_credentials_without_detail(
            LeakyAuth({"tok-good": "u"}), ["tok-bad"]
        )


def test_limiter_charging_refusals_is_caught() -> None:
    with pytest.raises(SUITE_FAILURE):
        RateLimiterContract().test_a_refused_hit_costs_nothing(
            GreedyLimiter({"chat": (3, 1 / 60)}), "chat", 3
        )


def test_provider_leaking_raw_exceptions_is_caught() -> None:
    with pytest.raises(SUITE_FAILURE):
        LLMProviderContract().test_unknown_model_raises_service_error(RawErrorProvider())
