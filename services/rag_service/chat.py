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
