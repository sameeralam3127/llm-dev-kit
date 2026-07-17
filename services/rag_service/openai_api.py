"""OpenAI-compatible endpoints so Open WebUI (or any OpenAI client) can use the
RAG pipeline as a model backend.

Every model exposed here answers with retrieval-augmented context. A real cloud
API key supplied as the Bearer token is forwarded to the llm-service for cloud
models; placeholder keys (sk-local*) are ignored, keeping the default fully
offline.
"""

import json
import time
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from rag_service.prompts import build_prompt

router = APIRouter(prefix="/v1", tags=["openai-compat"])

PLACEHOLDER_KEY_PREFIX = "sk-local"


def _bearer_api_key(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    if not token or token.startswith(PLACEHOLDER_KEY_PREFIX):
        return None
    return token


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _extract_query(messages: list[dict]) -> tuple[str, str | None]:
    """Return (latest user message, conversation transcript before it)."""
    query = ""
    last_user_index = -1
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            query = _content_to_text(messages[index].get("content"))
            last_user_index = index
            break

    history_lines = [
        f"{message['role'].capitalize()}: {_content_to_text(message.get('content'))}"
        for message in messages[:last_user_index]
        if message.get("role") in {"user", "assistant"}
        and _content_to_text(message.get("content")).strip()
    ]
    return query, "\n".join(history_lines) or None


def _completion_body(model: str, text: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@router.get("/models")
async def list_models(request: Request) -> dict:
    models = await request.app.state.llm.models()
    return {
        "object": "list",
        "data": [
            {"id": model, "object": "model", "owned_by": "llm-dev-kit"}
            for model in models
        ],
    }


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
):
    body = await request.json()
    settings = request.app.state.settings
    model = body.get("model") or settings.default_chat_model
    messages = body.get("messages") or []
    stream = bool(body.get("stream"))
    api_key = _bearer_api_key(authorization)

    query, history = _extract_query(messages)
    if not query.strip():
        raise HTTPException(status_code=400, detail="No user message provided")

    llm = request.app.state.llm
    retriever = request.app.state.retriever

    embedding = await llm.embed_one(query)
    docs = await retriever.retrieve(embedding) if embedding else []

    question = query if not history else f"{history}\n\nCurrent question: {query}"
    prompt = build_prompt(question, "\n\n".join(docs) if docs else None)

    if not stream:
        result = await llm.generate(prompt, model=model, api_key=api_key)
        return _completion_body(result.get("model", model), result.get("response", ""))

    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(time.time())

    def chunk(delta: dict, finish_reason: str | None = None) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {"index": 0, "delta": delta, "finish_reason": finish_reason}
            ],
        }
        return f"data: {json.dumps(payload)}\n\n"

    async def sse():
        yield chunk({"role": "assistant", "content": ""})
        try:
            async for piece in llm.generate_stream(prompt, model=model, api_key=api_key):
                yield chunk({"content": piece})
        except RuntimeError as exc:
            yield chunk({"content": f"\n[error] {exc}"})
        yield chunk({}, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
