import json
from collections.abc import AsyncIterator

from fastapi import HTTPException

from devkit_common.models import ChatResponse
from rag_service.prompts import build_prompt


async def answer_query(
    query: str,
    model: str | None,
    *,
    llm,
    cache,
    retriever,
    api_key: str | None = None,
) -> ChatResponse:
    """Cache -> embed -> retrieve -> generate. Only successful responses are cached."""
    query = query.strip()

    cached = await cache.get(query, model)
    if cached:
        return ChatResponse(response=cached, model=model or "", cached=True)

    embedding = await llm.embed_one(query)
    docs = await retriever.retrieve(embedding) if embedding else []

    prompt = build_prompt(query, "\n\n".join(docs) if docs else None)
    result = await llm.generate(prompt, model=model, api_key=api_key)

    response = result.get("response", "")
    if response:
        await cache.set(query, model, response)

    return ChatResponse(
        response=response,
        model=result.get("model", model or ""),
        provider=result.get("provider"),
        sources=docs,
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
    """Same pipeline as answer_query but yields NDJSON lines as tokens arrive.

    Line protocol: {"meta": {...}} first (sources + cache hit), then
    {"delta": "..."} per token, then {"done": true, "model": ...}. Errors are
    reported as {"error": "..."} and end the stream.
    """
    query = query.strip()

    cached = await cache.get(query, model)
    if cached:
        yield json.dumps({"meta": {"cached": True, "sources": []}}) + "\n"
        yield json.dumps({"delta": cached}) + "\n"
        yield json.dumps({"done": True, "model": model or ""}) + "\n"
        return

    try:
        embedding = await llm.embed_one(query)
        docs = await retriever.retrieve(embedding) if embedding else []
    except HTTPException as exc:
        yield json.dumps({"error": exc.detail}) + "\n"
        return

    yield json.dumps({"meta": {"cached": False, "sources": docs}}) + "\n"

    prompt = build_prompt(query, "\n\n".join(docs) if docs else None)
    parts: list[str] = []
    try:
        async for delta in llm.generate_stream(prompt, model=model, api_key=api_key):
            parts.append(delta)
            yield json.dumps({"delta": delta}) + "\n"
    except (HTTPException, RuntimeError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        yield json.dumps({"error": detail}) + "\n"
        return

    response = "".join(parts)
    if response:
        await cache.set(query, model, response)
    yield json.dumps({"done": True, "model": model or ""}) + "\n"
