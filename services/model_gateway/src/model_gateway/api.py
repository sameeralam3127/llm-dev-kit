"""HTTP routes. The wire protocol is documented in ``core_api.adapters.gateway``.

* ``GET /models`` → ``{"models": [...]}``
* ``POST /chat`` → SSE: ``{"delta": ...}`` events, then ``{"done": true, ...}``,
  or ``{"error": {...}}`` if the model fails mid-answer
* ``POST /embed`` → ``{"embeddings": [...], "model": ..., "dimension": n}``

A refused or unauditable call fails with an ordinary HTTP status before the
stream starts, so the caller never mistakes it for a model error.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ldk_core.auth import bearer_token, forbidden, unauthorized
from ldk_core.errors import bad_request, to_service_error
from ldk_core.observability import get_correlation_id, get_logger
from ldk_core.ports import ChatMessage
from model_gateway.domain.callers import Permission, Service, identify
from model_gateway.gateway import CallContext, ModelGateway

_log = get_logger(__name__)

router = APIRouter()

#: Longest ``X-On-Behalf-Of`` accepted; user ids are much shorter.
MAX_USER_ID = 256


def caller(permission: Permission) -> Callable[[Request], Coroutine[Any, Any, CallContext]]:
    """A dependency that authenticates the calling service and checks ``permission``."""

    async def dependency(request: Request) -> CallContext:
        services: list[Service] = request.app.state.services
        service = identify(bearer_token(request.headers.get("authorization")), services)
        if service is None:
            raise unauthorized("A service token is required")
        if permission not in service.permissions:
            raise forbidden(permission)
        user_id = request.headers.get("x-on-behalf-of") or None
        if user_id is not None and len(user_id) > MAX_USER_ID:
            raise bad_request("X-On-Behalf-Of is too long")
        workspace = request.headers.get("x-workspace-id")
        try:
            workspace_id = UUID(workspace) if workspace else None
        except ValueError as exc:
            raise bad_request("X-Workspace-Id must be a UUID") from exc
        return CallContext(service, user_id, workspace_id, get_correlation_id())

    return dependency


def _gateway(request: Request) -> ModelGateway:
    gateway: ModelGateway = request.app.state.gateway
    return gateway


class MessageIn(BaseModel):
    """One chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatIn(BaseModel):
    """``POST /chat``. Only streaming exists; ``stream`` is there to say so."""

    model: str = Field(min_length=1, max_length=200)
    messages: list[MessageIn] = Field(min_length=1)
    stream: Literal[True] = True


class EmbedIn(BaseModel):
    """``POST /embed``. The text count is capped by ``EMBED_MAX_TEXTS``."""

    texts: list[str]
    model: str | None = None


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.get("/models")
async def models(
    request: Request, _: Annotated[CallContext, Depends(caller("models"))]
) -> dict[str, list[str]]:
    """Models a caller may use; sovereign mode hides any it would refuse."""
    return {"models": await _gateway(request).models()}


@router.post("/chat")
async def chat(
    body: ChatIn, request: Request, ctx: Annotated[CallContext, Depends(caller("chat"))]
) -> StreamingResponse:
    """Stream one answer. Every chat is on behalf of a user in a workspace."""
    if ctx.user_id is None or ctx.workspace_id is None:
        raise bad_request("Chat calls need X-On-Behalf-Of and X-Workspace-Id")
    gateway = _gateway(request)
    admitted = await gateway.admit_chat(body.model, ctx)
    messages = [ChatMessage(m.role, m.content) for m in body.messages]

    async def events() -> AsyncIterator[str]:
        try:
            async for text in gateway.stream(admitted, messages):
                yield _sse({"delta": text})
        except Exception as exc:  # noqa: BLE001 - reported in-band; the status is already sent
            error = to_service_error(exc)
            if error is not exc:
                _log.exception("chat stream failed", model=body.model)
            yield _sse({"error": {"code": error.code.value, "message": error.message}})
            return
        # Providers stream text only; token counts are not known here yet.
        usage = {"tokens_in": None, "tokens_out": None}
        yield _sse({"done": True, "model": body.model, "usage": usage})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/embed")
async def embed(
    body: EmbedIn, request: Request, ctx: Annotated[CallContext, Depends(caller("embed"))]
) -> dict[str, Any]:
    """One vector per text, in order."""
    gateway = _gateway(request)
    vectors = await gateway.embed(body.texts, model=body.model, ctx=ctx)
    return {"embeddings": vectors, "model": gateway.embed_model, "dimension": len(vectors[0])}
