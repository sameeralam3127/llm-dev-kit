"""The RAG pipeline, shared by /chat, /chat/stream and /v1/chat/completions.

``RagPipeline`` owns the steps every answer takes: the answer cache, the
question embedding, retrieval, the prompt and the model call. The routes only
translate their own request and response formats around it, so a change to
retrieval, prompting or caching is made once and reaches every endpoint.
"""

import json
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from devkit_common.models import ChatResponse
from ldk_core.errors import ServiceError
from rag_service.prompts import build_prompt


@dataclass(frozen=True)
class Prepared:
    """A question made ready to answer.

    Attributes:
        question: The question as the model sees it, conversation included; it
            is also the cache key, with the model and the revision.
        revision: The document-set revision read when the question started, or
            ``None`` when the cache is unavailable.
        cached: A cached answer, when there is one; nothing else was done then.
        sources: The retrieved passages (empty on a cache hit).
        prompt: The prompt to send; ``None`` on a cache hit.
    """

    question: str
    revision: int | None
    cached: str | None = None
    sources: list[str] = field(default_factory=list)
    prompt: str | None = None


@dataclass(frozen=True)
class Answer:
    text: str
    model: str
    provider: str | None
    sources: list[str]
    cached: bool


class RagPipeline:
    """Cache -> embed -> retrieve -> prompt -> generate, for every endpoint.

    The corpus revision is read once, up front, and used for the save, so an
    answer that spans an ingest is stored under the revision it started with.
    A retrieval failure raises ``ServiceError``; it never degrades to an
    ungrounded answer. Only complete, non-empty answers are cached: a failed or
    interrupted stream never is.
    """

    def __init__(self, *, llm: Any, cache: Any, retriever: Any) -> None:
        self.llm = llm
        self.cache = cache
        self.retriever = retriever

    async def prepare(
        self, query: str, model: str | None, *, history: str | None = None
    ) -> Prepared:
        """Look the question up in the cache, else retrieve and build the prompt.

        Retrieval uses the latest question alone; the prompt and the cache key
        use it with the conversation before it.
        """
        query = query.strip()
        question = query if not history else f"{history}\n\nCurrent question: {query}"
        revision = await self.cache.revision()
        cached = await self.cache.get(question, model, revision=revision)
        if cached:
            return Prepared(question=question, revision=revision, cached=cached)

        embedding = await self.llm.embed_one(query)
        docs = await self.retriever.retrieve(embedding) if embedding else []
        prompt = build_prompt(question, "\n\n".join(docs) if docs else None)
        return Prepared(question=question, revision=revision, sources=docs, prompt=prompt)

    async def answer(
        self,
        query: str,
        model: str | None,
        *,
        api_key: str | None = None,
        history: str | None = None,
    ) -> Answer:
        """The whole answer at once."""
        prepared = await self.prepare(query, model, history=history)
        if prepared.cached is not None:
            return Answer(prepared.cached, model or "", None, [], cached=True)

        result = await self.llm.generate(prepared.prompt, model=model, api_key=api_key)
        text = result.get("response", "")
        if text:
            await self.cache.set(prepared.question, model, text, revision=prepared.revision)
        return Answer(
            text,
            result.get("model", model or ""),
            result.get("provider"),
            prepared.sources,
            cached=False,
        )

    async def stream(
        self, prepared: Prepared, model: str | None, *, api_key: str | None = None
    ) -> AsyncGenerator[str, None]:
        """The answer's pieces as they arrive; a cache hit is one piece.

        The answer is cached only when the model's stream ends normally. An
        error propagates to the caller, and a caller that stops early (a
        disconnected client) closes the generator before the save.
        """
        if prepared.cached is not None:
            yield prepared.cached
            return
        parts: list[str] = []
        async for piece in self.llm.generate_stream(prepared.prompt, model=model, api_key=api_key):
            parts.append(piece)
            yield piece
        text = "".join(parts)
        if text:
            await self.cache.set(prepared.question, model, text, revision=prepared.revision)


async def answer_query(
    query: str,
    model: str | None,
    *,
    llm,
    cache,
    retriever,
    api_key: str | None = None,
) -> ChatResponse:
    """/chat: the pipeline's answer as a ``ChatResponse``."""
    pipeline = RagPipeline(llm=llm, cache=cache, retriever=retriever)
    answer = await pipeline.answer(query, model, api_key=api_key)
    if answer.cached:
        return ChatResponse(response=answer.text, model=model or "", cached=True)
    return ChatResponse(
        response=answer.text,
        model=answer.model,
        provider=answer.provider,
        sources=answer.sources,
    )


async def stream_answer(
    query: str,
    model: str | None,
    *,
    llm,
    cache,
    retriever,
    api_key: str | None = None,
) -> AsyncIterator[str]:
    """/chat/stream: the pipeline's answer as NDJSON lines.

    Line protocol: {"meta": {...}} first (sources + cache hit), then
    {"delta": "..."} per token, then {"done": true, "model": ...}. Errors are
    reported as {"error": "..."} and end the stream.
    """
    pipeline = RagPipeline(llm=llm, cache=cache, retriever=retriever)
    try:
        prepared = await pipeline.prepare(query, model)
    except ServiceError as exc:
        yield json.dumps({"error": exc.message}) + "\n"
        return

    yield (
        json.dumps({"meta": {"cached": prepared.cached is not None, "sources": prepared.sources}})
        + "\n"
    )
    try:
        async for delta in pipeline.stream(prepared, model, api_key=api_key):
            yield json.dumps({"delta": delta}) + "\n"
    except ServiceError as exc:
        yield json.dumps({"error": exc.message}) + "\n"
        return
    yield json.dumps({"done": True, "model": model or ""}) + "\n"
