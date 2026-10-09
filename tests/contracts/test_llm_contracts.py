"""Reference LLM provider and embedder, proving the suites run and pass."""

import hashlib
from collections.abc import AsyncIterator, Sequence

import pytest

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import CompletionRequest
from ldk_core.testing.contracts import EmbedderContract, LLMProviderContract


class EchoProvider:
    name = "echo"
    _models = ("echo-1",)

    async def list_models(self) -> list[str]:
        return list(self._models)

    def _check(self, request: CompletionRequest) -> None:
        if request.model not in self._models:
            raise ServiceError(ErrorCode.UPSTREAM_ERROR, f"model '{request.model}' not found")

    async def complete(self, request: CompletionRequest) -> str:
        self._check(request)
        return f"echo: {request.messages[-1].content}"

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        self._check(request)
        for word in f"echo: {request.messages[-1].content}".split(" "):
            yield word + " "


class HashEmbedder:
    name = "hash"
    model = "sha256-8"
    dimension = 8

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [b / 255 for b in hashlib.sha256(text.encode()).digest()[: self.dimension]]
            for text in texts
        ]


class TestEchoProvider(LLMProviderContract):
    @pytest.fixture
    def provider(self) -> EchoProvider:
        return EchoProvider()

    @pytest.fixture
    def model(self) -> str:
        return "echo-1"


class TestHashEmbedder(EmbedderContract):
    @pytest.fixture
    def embedder(self) -> HashEmbedder:
        return HashEmbedder()
