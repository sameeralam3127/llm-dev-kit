"""Ports for the model gateway, the hybrid index and answer provenance."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from core_api.domain.retrieval import ChatMessage, Hit


@dataclass(frozen=True, slots=True)
class Delta:
    """A piece of streamed answer text."""

    text: str


@dataclass(frozen=True, slots=True)
class Done:
    """The end of a stream, with what the model reports about itself."""

    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None


StreamEvent = Delta | Done


@dataclass(frozen=True, slots=True)
class OnBehalfOf:
    """Who a model call is for, so model-gateway can audit it."""

    user_id: str
    workspace_id: UUID


class ModelClient(Protocol):
    """model-gateway: the only path to a model (architecture decision 3)."""

    async def models(self) -> list[str]:
        """Models the gateway will serve."""
        ...

    def stream_chat(
        self, messages: Sequence[ChatMessage], *, model: str, caller: OnBehalfOf
    ) -> AsyncIterator[StreamEvent]:
        """Stream an answer: :class:`Delta` events, then one :class:`Done`."""
        ...


class HybridIndex(Protocol):
    """Search one workspace's chunks two ways."""

    async def search(
        self, workspace_id: UUID, *, text: str, vector: Sequence[float], k: int
    ) -> tuple[list[Hit], list[Hit]]:
        """``(semantic, lexical)`` top-``k`` lists, each filtered by workspace in SQL."""
        ...


class ProvenanceStore(Protocol):
    """What each answer was built from."""

    async def record_exchange(
        self,
        *,
        workspace_id: UUID,
        user_id: str,
        external_id: str | None,
        question: str,
        answer: str,
        model: str,
        chunk_ids: Sequence[UUID],
        tokens_in: int | None,
        tokens_out: int | None,
        request_id: str | None,
    ) -> None:
        """Store the question and the answer, with the chunks the answer used."""
        ...
