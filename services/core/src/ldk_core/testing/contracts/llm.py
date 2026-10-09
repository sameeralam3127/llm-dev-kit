"""Contract suites for :class:`LLMProvider` and :class:`Embedder`."""

from __future__ import annotations

import math
from collections.abc import AsyncIterator

import pytest

from ldk_core.ports import ChatMessage, CompletionRequest, Embedder, LLMProvider
from ldk_core.testing.contracts._util import (
    REGISTRY_NAME,
    assert_service_error,
    collect,
    run,
    unimplemented,
)

UNKNOWN_MODEL = "ldk-contract-no-such-model"


class LLMProviderContract:
    """Every :class:`LLMProvider` must pass this.

    Fixtures to provide:
        provider: The implementation under test.
        model: A model id it can serve, without any routing prefix.
    """

    @pytest.fixture
    def provider(self) -> LLMProvider:
        """The implementation under test."""
        unimplemented("provider")

    @pytest.fixture
    def model(self) -> str:
        """A model id the provider serves."""
        unimplemented("model")

    def _request(self, model: str, text: str = "Say hello.") -> CompletionRequest:
        return CompletionRequest(model=model, messages=[ChatMessage("user", text)], max_tokens=32)

    def test_satisfies_the_protocol(self, provider: LLMProvider) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(provider, LLMProvider)

    def test_name_is_a_valid_registry_name(self, provider: LLMProvider) -> None:
        """``name`` doubles as the model-id prefix, so it must be URL- and id-safe."""
        assert REGISTRY_NAME.fullmatch(provider.name)

    def test_lists_the_model(self, provider: LLMProvider, model: str) -> None:
        """The model under test is among the listed ones."""
        assert model in run(provider.list_models())

    def test_complete_returns_text(self, provider: LLMProvider, model: str) -> None:
        """A completion is non-empty text."""
        text = run(provider.complete(self._request(model)))
        assert isinstance(text, str)
        assert text.strip()

    def test_stream_yields_text_deltas(self, provider: LLMProvider, model: str) -> None:
        """Streaming returns an async iterator of strings that join to an answer."""
        stream = provider.stream(self._request(model))
        assert isinstance(stream, AsyncIterator)
        deltas = run(collect(stream))
        assert deltas
        assert all(isinstance(d, str) for d in deltas)
        assert "".join(deltas).strip()

    def test_unknown_model_raises_service_error(self, provider: LLMProvider) -> None:
        """Backend failures surface as ServiceError, never a raw client exception."""
        with pytest.raises(Exception) as info:
            run(provider.complete(self._request(UNKNOWN_MODEL)))
        assert_service_error(info.value)

    def test_unknown_model_raises_from_stream(self, provider: LLMProvider) -> None:
        """The same holds when streaming, before any delta arrives."""
        with pytest.raises(Exception) as info:
            run(collect(provider.stream(self._request(UNKNOWN_MODEL))))
        assert_service_error(info.value)


class EmbedderContract:
    """Every :class:`Embedder` must pass this.

    Fixtures to provide:
        embedder: The implementation under test.
    """

    @pytest.fixture
    def embedder(self) -> Embedder:
        """The implementation under test."""
        unimplemented("embedder")

    def test_satisfies_the_protocol(self, embedder: Embedder) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(embedder, Embedder)

    def test_identifies_itself(self, embedder: Embedder) -> None:
        """Name, model and a positive dimension are recorded on every chunk."""
        assert REGISTRY_NAME.fullmatch(embedder.name)
        assert embedder.model
        assert embedder.dimension > 0

    def test_one_vector_per_text_of_the_declared_dimension(self, embedder: Embedder) -> None:
        """Output length matches input, and every vector has ``dimension`` floats."""
        vectors = run(embedder.embed(["alpha", "beta", "gamma"]))
        assert len(vectors) == 3
        for vector in vectors:
            assert len(vector) == embedder.dimension
            assert all(isinstance(x, float) and math.isfinite(x) for x in vector)

    def test_order_is_preserved(self, embedder: Embedder) -> None:
        """Vector *i* belongs to text *i*, whatever batching happens inside."""
        batch = run(embedder.embed(["first text", "second text"]))
        alone = run(embedder.embed(["second text"]))
        assert _close(batch[1], alone[0])
        assert not _close(batch[0], alone[0])

    def test_empty_input_returns_empty(self, embedder: Embedder) -> None:
        """No texts, no vectors, and no backend call needed."""
        assert run(embedder.embed([])) == []


def _close(a: list[float], b: list[float], tol: float = 1e-4) -> bool:
    """Whether two vectors are equal within ``tol`` per component."""
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))
