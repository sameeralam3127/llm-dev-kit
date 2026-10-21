"""Hybrid retrieval and grounded prompts, as pure functions.

**Reciprocal Rank Fusion.** Semantic search (embeddings) is good at meaning and
paraphrase; full-text search is good at exact terms such as product codes and
names. Their scores are on unrelated scales, so instead of combining scores
RRF combines *ranks*: every list a result appears in contributes
``1 / (k + rank)``. A chunk near the top of both lists beats one at the top of
only one. ``k`` (60 by convention) damps the influence of the very first
places, so one list cannot dominate.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

RRF_K = 60


def rrf[T: Hashable](rankings: Sequence[Sequence[T]], k: int = RRF_K) -> list[tuple[T, float]]:
    """Fuse ranked lists into one, best first. Ties keep first-seen order."""
    scores: dict[T, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


@dataclass(frozen=True, slots=True)
class Hit:
    """A chunk found by search."""

    chunk_id: UUID
    document_id: UUID
    title: str | None
    page: int | None
    text: str


@dataclass(frozen=True, slots=True)
class Citation:
    """A source as returned to the caller; ``index`` matches ``[n]`` in the answer."""

    index: int
    chunk_id: UUID
    document_id: UUID
    title: str | None
    page: int | None
    snippet: str


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One turn of a conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


def fuse(semantic: Sequence[Hit], lexical: Sequence[Hit], limit: int) -> list[Hit]:
    """The ``limit`` best chunks across both searches, by RRF."""
    by_id = {hit.chunk_id: hit for hit in [*semantic, *lexical]}
    fused = rrf([[h.chunk_id for h in semantic], [h.chunk_id for h in lexical]])
    return [by_id[chunk_id] for chunk_id, _ in fused[:limit]]


def citations_for(hits: Sequence[Hit], snippet_chars: int = 240) -> list[Citation]:
    """Number the sources 1..n in the order they are given to the model."""
    return [
        Citation(
            index=i,
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            title=h.title,
            page=h.page,
            snippet=h.text[:snippet_chars],
        )
        for i, h in enumerate(hits, start=1)
    ]


_GROUNDED = """You answer questions using only the numbered sources below.
- Cite every claim with the source number in square brackets, like [1] or [2][3].
- If the sources do not contain the answer, say that plainly instead of guessing.
- Be concise.

Sources:
{sources}"""


def build_messages(
    history: Sequence[ChatMessage], question: str, citations: Sequence[Citation]
) -> list[ChatMessage]:
    """The messages sent to the model: grounding instructions, history, question.

    With no sources (an empty workspace, or nothing relevant), the model
    answers as a general assistant, which is how v2 behaves too.
    """
    messages: list[ChatMessage] = []
    if citations:
        sources = "\n\n".join(
            f"[{c.index}] {c.title or 'Untitled'}"
            + (f", page {c.page}" if c.page else "")
            + f"\n{c.snippet}"
            for c in citations
        )
        messages.append(ChatMessage("system", _GROUNDED.format(sources=sources)))
    messages.extend(m for m in history if m.role != "system")
    messages.append(ChatMessage("user", question))
    return messages
