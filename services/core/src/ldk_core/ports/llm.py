"""``LLMProvider``: anything that turns messages into tokens.

The Python twin of ``ChatProvider`` in ``web/src/lib/llm/types.ts``. Ollama
and LiteLLM implement it first (#11); a provider is chosen by the registry
from the model id, never imported by a consumer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One turn of a conversation."""

    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """Everything a provider needs to answer.

    Attributes:
        model: The provider-local model id, with any ``provider/`` routing
            prefix already removed by the registry.
        messages: The conversation, oldest first.
        temperature: Sampling temperature; ``None`` keeps the provider default.
        max_tokens: Upper bound on generated tokens; ``None`` keeps the default.
        api_key: A per-request cloud key. Sovereign mode rejects requests
            that carry one before they reach a provider (Phase 3).
        extra: Provider-specific options passed through untouched, e.g.
            Ollama's ``num_ctx``.
    """

    model: str
    messages: Sequence[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    api_key: str | None = field(default=None, repr=False)
    extra: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Generates text from a conversation, whole or streamed.

    Failures raise :class:`ldk_core.errors.ServiceError`:
    ``upstream_unavailable`` when the backend cannot be reached,
    ``upstream_error`` when it answers with an error, ``unauthorized`` when a
    required key is missing.
    """

    @property
    def name(self) -> str:
        """Registry name and model-id prefix, e.g. ``"ollama"``, ``"openai"``."""
        ...

    async def list_models(self) -> list[str]:
        """Return the model ids this provider can serve right now."""
        ...

    async def complete(self, request: CompletionRequest) -> str:
        """Return the full answer once generation finishes."""
        ...

    def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Yield text deltas as they are generated.

        Implemented as an async generator, so it is a plain ``def`` here.
        Errors before the first delta raise immediately. Errors after it raise
        from the iterator, so the caller can keep the partial answer.
        """
        ...
