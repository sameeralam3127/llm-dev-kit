"""Grounded chat: retrieve from the caller's workspace, then stream the model's answer."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field

from core_api.domain.access import Access
from core_api.domain.retrieval import ChatMessage, Citation, build_messages, citations_for, fuse
from core_api.ports.models import Delta, Done, HybridIndex, ModelClient, OnBehalfOf, ProvenanceStore
from ldk_core.auth import forbidden
from ldk_core.errors import bad_request
from ldk_core.observability import get_logger
from ldk_core.ports import Embedder

_log = get_logger(__name__)

MAX_QUESTION_CHARS = 8_000


@dataclass(frozen=True, slots=True)
class PreparedChat:
    """Everything decided before the first token: the prompt and its sources."""

    access: Access
    model: str
    question: str
    messages: list[ChatMessage]
    citations: list[Citation]
    external_id: str | None
    request_id: str | None


@dataclass(slots=True)
class Answered:
    """The end of an answer: which model gave it and from which sources."""

    model: str
    citations: list[Citation]
    tokens_in: int | None = None
    tokens_out: int | None = None
    text: str = field(default="", repr=False)


class ChatService:
    """Use cases behind ``/v1/models`` and ``/v1/chat/completions``.

    Args:
        top_k: Candidates taken from *each* search before fusion.
        context_chunks: How many fused chunks go into the prompt.
    """

    def __init__(
        self,
        *,
        index: HybridIndex,
        embedder: Embedder,
        models: ModelClient,
        provenance: ProvenanceStore,
        default_model: str,
        top_k: int = 20,
        context_chunks: int = 5,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._models = models
        self._provenance = provenance
        self._default_model = default_model
        self._top_k = top_k
        self._context_chunks = context_chunks

    async def models(self, access: Access) -> list[str]:
        """Models available to this caller."""
        _require_chat(access)
        return await self._models.models()

    async def prepare(
        self,
        access: Access,
        *,
        history: Sequence[ChatMessage],
        question: str,
        model: str | None,
        external_id: str | None,
        request_id: str | None,
    ) -> PreparedChat:
        """Retrieve and build the prompt. Failures here are ordinary HTTP errors."""
        _require_chat(access)
        question = question.strip()
        if not question:
            raise bad_request("The last message must be a non-empty user message")
        if len(question) > MAX_QUESTION_CHARS:
            raise bad_request(f"The question is longer than {MAX_QUESTION_CHARS} characters")

        (vector,) = await self._embedder.embed([question])
        semantic, lexical = await self._index.search(
            access.workspace_id, text=question, vector=vector, k=self._top_k
        )
        hits = fuse(semantic, lexical, self._context_chunks)
        citations = citations_for(hits)
        return PreparedChat(
            access=access,
            model=model or self._default_model,
            question=question,
            messages=build_messages(history, question, citations),
            citations=citations,
            external_id=external_id,
            request_id=request_id,
        )

    async def stream(self, chat: PreparedChat) -> AsyncIterator[Delta | Answered]:
        """Relay the model's answer, then record what it was built from."""
        caller = OnBehalfOf(user_id=chat.access.user_id, workspace_id=chat.access.workspace_id)
        parts: list[str] = []
        done = Done(model=chat.model)
        async for event in self._models.stream_chat(chat.messages, model=chat.model, caller=caller):
            if isinstance(event, Delta):
                parts.append(event.text)
                yield event
            else:
                done = event
        answer = "".join(parts)
        await self._provenance.record_exchange(
            workspace_id=chat.access.workspace_id,
            user_id=chat.access.user_id,
            external_id=chat.external_id,
            question=chat.question,
            answer=answer,
            model=done.model,
            chunk_ids=[c.chunk_id for c in chat.citations],
            tokens_in=done.tokens_in,
            tokens_out=done.tokens_out,
            request_id=chat.request_id,
        )
        yield Answered(
            model=done.model,
            citations=chat.citations,
            tokens_in=done.tokens_in,
            tokens_out=done.tokens_out,
            text=answer,
        )


def _require_chat(access: Access) -> None:
    if not access.allows("chat"):
        raise forbidden("chat")
