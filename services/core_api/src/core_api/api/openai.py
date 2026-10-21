"""The OpenAI-compatible API: ``/v1/models`` and ``/v1/chat/completions``.

Request and response shapes follow OpenAI's, so any OpenAI SDK works by
pointing it at this server with a workspace API key. Two additions, both
ignored by SDKs that do not know them:

* every answer carries ``citations``, numbered to match the ``[n]`` markers in
  its text, in the final chunk when streaming;
* ``X-Conversation-Id`` groups exchanges into one conversation for provenance.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core_api.api.deps import CurrentWorkspaceDep, RequestIdDep, authenticated
from core_api.domain.retrieval import ChatMessage, Citation
from core_api.ports.models import Delta
from core_api.services.chat import Answered, ChatService, PreparedChat
from ldk_core.errors import ServiceError, bad_request, to_service_error

router = APIRouter(prefix="/v1", tags=["openai-compatible"], dependencies=[Depends(authenticated)])


class MessageIn(BaseModel):
    """An OpenAI chat message. ``content`` may be a string or a list of text parts."""

    role: Literal["system", "user", "assistant"]
    content: str | list[dict[str, Any]]

    def text(self) -> str:
        """The message's text, joining text parts."""
        if isinstance(self.content, str):
            return self.content
        return " ".join(str(p.get("text", "")) for p in self.content if p.get("type") == "text")


class ChatCompletionIn(BaseModel):
    """The subset of OpenAI's request that core-api uses; other fields are ignored."""

    model: str | None = None
    messages: list[MessageIn] = Field(min_length=1)
    stream: bool = False


def _service(request: Request) -> ChatService:
    service: ChatService = request.app.state.chat
    return service


def _citation(c: Citation) -> dict[str, Any]:
    return {
        "index": c.index,
        "chunk_id": str(c.chunk_id),
        "document_id": str(c.document_id),
        "title": c.title,
        "page": c.page,
        "snippet": c.snippet,
    }


@router.get("/models")
async def list_models(access: CurrentWorkspaceDep, request: Request) -> dict[str, Any]:
    """Models, in OpenAI's list format."""
    names = await _service(request).models(access)
    return {
        "object": "list",
        "data": [{"id": n, "object": "model", "owned_by": "llm-dev-kit"} for n in names],
    }


@router.post("/chat/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionIn, access: CurrentWorkspaceDep, request: Request, rid: RequestIdDep
) -> dict[str, Any] | StreamingResponse:
    """Answer from the workspace's documents, with citations."""
    *history, last = body.messages
    if last.role != "user":
        raise bad_request("The last message must be from the user")
    prepared = await _service(request).prepare(
        access,
        history=[ChatMessage(m.role, m.text()) for m in history],
        question=last.text(),
        model=body.model,
        external_id=request.headers.get("x-conversation-id"),
        request_id=rid,
    )
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    if body.stream:
        return StreamingResponse(
            _sse(_service(request), prepared, completion_id, created),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    answered: Answered | None = None
    async for event in _service(request).stream(prepared):
        if isinstance(event, Answered):
            answered = event
    assert answered is not None
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": answered.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answered.text},
                "finish_reason": "stop",
            }
        ],
        "usage": _usage(answered),
        "citations": [_citation(c) for c in answered.citations],
    }


def _usage(a: Answered) -> dict[str, int | None]:
    total = (a.tokens_in or 0) + (a.tokens_out or 0) if a.tokens_in is not None else None
    return {"prompt_tokens": a.tokens_in, "completion_tokens": a.tokens_out, "total_tokens": total}


async def _sse(
    service: ChatService, prepared: PreparedChat, completion_id: str, created: int
) -> AsyncIterator[str]:
    def chunk(delta: dict[str, Any], **extra: Any) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": prepared.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": extra.pop("finish", None)}],
            **extra,
        }
        return f"data: {json.dumps(payload)}\n\n"

    yield chunk({"role": "assistant", "content": ""})
    try:
        async for event in service.stream(prepared):
            if isinstance(event, Delta):
                yield chunk({"content": event.text})
            else:
                yield chunk(
                    {},
                    finish="stop",
                    usage=_usage(event),
                    citations=[_citation(c) for c in event.citations],
                )
    except Exception as exc:  # noqa: BLE001 - a stream that has started can only report in-band
        error: ServiceError = to_service_error(exc)
        yield f"data: {json.dumps(error.to_body())}\n\n"
    yield "data: [DONE]\n\n"
