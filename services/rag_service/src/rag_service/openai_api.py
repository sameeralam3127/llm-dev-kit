"""OpenAI-compatible endpoints so any OpenAI client (SDKs, LangChain, curl)
can use the RAG pipeline as a model backend.

This module only translates: OpenAI's request in, OpenAI's response or SSE
stream out. Retrieval, the prompt, the answer cache and the model call are
``rag_service.chat.RagPipeline``, shared with /chat and /chat/stream, so a
repeated question is answered from the cache here too, and a streamed answer
is cached once it completes. A cached answer streams as one content chunk.

Every model exposed here answers with retrieval-augmented context. The Bearer
token says who is calling: a personal API key (``sk-ldk-...``) or an access
token from the web app. Calls without one get 401.

Under ``ALLOW_LEGACY_ANONYMOUS`` the pre-v2 meaning survives for one release:
a Bearer that is not an identity is a cloud provider key, forwarded to
llm-service for cloud models, and placeholder keys (``sk-local*``) are ignored.
"""

import json
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from devkit_common.auth import require
from ldk_core.auth import CHAT
from ldk_core.errors import ErrorCode, ServiceError, bad_request
from ldk_core.observability import get_logger
from ldk_core.ports import Principal
from rag_service.chat import RagPipeline

_log = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat"], dependencies=[Depends(require(CHAT))])

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
        "data": [{"id": model, "object": "model", "owned_by": "llm-dev-kit"} for model in models],
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
    principal: Principal = request.state.principal
    # Only an anonymous legacy caller's Bearer can be a provider key; anyone
    # else's Bearer is their identity.
    api_key = _bearer_api_key(authorization) if principal.kind == "anonymous" else None

    query, history = _extract_query(messages)
    if not query.strip():
        raise bad_request("No user message provided")

    pipeline = RagPipeline(
        llm=request.app.state.llm,
        cache=request.app.state.cache,
        retriever=request.app.state.retriever,
    )

    if not stream:
        answer = await pipeline.answer(query, model, api_key=api_key, history=history)
        return _completion_body(answer.model or model, answer.text)

    # Retrieval happens here, before any response: an outage is an HTTP error.
    prepared = await pipeline.prepare(query, model, history=history)

    # Not part of OpenAI's format: the passages retrieved for this answer, in
    # the shape core-api sends, so the web app can show where it came from.
    citations = [
        {"index": i, "title": None, "page": None, "snippet": text[:600]}
        for i, text in enumerate(prepared.sources, start=1)
    ]
    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(time.time())

    def chunk(delta: dict, finish_reason: str | None = None, **extra: object) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
            **extra,
        }
        return f"data: {json.dumps(payload)}\n\n"

    def error_event(code: ErrorCode, message: str) -> str:
        # The shape OpenAI sends; its SDKs raise on it instead of returning text.
        payload = {"error": {"message": message, "type": code.value, "code": code.value}}
        return f"data: {json.dumps(payload)}\n\n"

    # Wait for the first piece before answering: a failure that early (an
    # unknown model, llm-service down) becomes an ordinary error response,
    # not a 200 stream an SDK would read as a finished answer.
    pieces = pipeline.stream(prepared, model, api_key=api_key)
    try:
        first: str | None = await anext(pieces)
    except StopAsyncIteration:
        first = None

    async def sse():
        try:
            yield chunk({"role": "assistant", "content": ""})
            if first is None:
                yield chunk({}, "stop", citations=citations)
                yield "data: [DONE]\n\n"
                return
            yield chunk({"content": first})
            async for piece in pieces:
                yield chunk({"content": piece})
        except ServiceError as exc:
            # Headers are sent: report the failure in the stream, and never
            # follow it with finish_reason "stop" or [DONE].
            yield error_event(exc.code, exc.message)
            return
        except Exception:  # noqa: BLE001 - any failure must end the stream as failed
            _log.exception("stream failed after it started")
            yield error_event(ErrorCode.INTERNAL, "The answer stopped unexpectedly")
            return
        finally:
            await pieces.aclose()
        yield chunk({}, "stop", citations=citations)
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
