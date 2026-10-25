"""The gateway's rules, independent of HTTP.

Order matters on every call: route, refuse egress in sovereign mode, write the
audit event, and only then call the model. If the audit write fails, the call
does not happen (fail closed): a model call that left no record is exactly
what an audit log exists to rule out.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from core_api.ports.stores import AuditEvent, AuditSink
from ldk_core.errors import ErrorCode, ServiceError, bad_request
from ldk_core.observability import get_logger
from ldk_core.ports import ChatMessage, CompletionRequest, Embedder, LLMProvider
from model_gateway.domain.callers import Service
from model_gateway.domain.egress import LOCAL_PROVIDER, Route, is_ollama_cloud, route

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CallContext:
    """Who is calling, and on whose behalf.

    Attributes:
        service: The authenticated calling service.
        user_id: The user core-api acts for (``X-On-Behalf-Of``), if any.
        workspace_id: The workspace the call is for (``X-Workspace-Id``), if any.
        request_id: Correlation id, shared with the caller's own audit events.
    """

    service: Service
    user_id: str | None = None
    workspace_id: UUID | None = None
    request_id: str | None = None

    @property
    def actor(self) -> str:
        """The user when there is one, otherwise the service itself."""
        return self.user_id or f"service:{self.service.name}"


@dataclass(frozen=True, slots=True)
class Admitted:
    """A chat call that passed policy and has its audit event written."""

    route: Route
    provider: LLMProvider


class ModelGateway:
    """Routes, polices and audits model calls.

    Args:
        llms: Chat providers by registry name. Sovereign mode passes only the
            local one, but refuses egress even if others are present.
        embedder: The embedding model.
        audit: Where audit events go; a write failure stops the call.
        sovereign: Refuse every call that would leave the network.
        embed_max_texts: Most texts one embed call may carry.
    """

    def __init__(
        self,
        *,
        llms: Mapping[str, LLMProvider],
        embedder: Embedder,
        audit: AuditSink,
        sovereign: bool,
        embed_max_texts: int = 256,
    ) -> None:
        self._llms = dict(llms)
        self._embedder = embedder
        self._audit = audit
        self.sovereign = sovereign
        self._embed_max_texts = embed_max_texts

    @property
    def embed_model(self) -> str:
        """The embedding model every vector comes from."""
        return self._embedder.model

    def _cloud(self) -> list[str]:
        return [name for name in self._llms if name != LOCAL_PROVIDER]

    async def models(self) -> list[str]:
        """Every model a caller may use here: never one sovereign mode would refuse."""
        found: list[str] = []
        local = self._llms.get(LOCAL_PROVIDER)
        if local is not None:
            try:
                found.extend(await local.list_models())
            except ServiceError as exc:
                _log.warning("local models unavailable", error=exc.message)
        for name in self._cloud():
            found.extend(f"{name}/{m}" for m in await self._llms[name].list_models())
        return [m for m in found if not (self.sovereign and route(m, self._cloud()).egress)]

    async def admit_chat(self, model: str, ctx: CallContext) -> Admitted:
        """Check ``model`` against policy and write the audit event, before any model call.

        Raises:
            ServiceError: ``forbidden`` when sovereign mode refuses it,
                ``invalid_request`` for an unknown provider, and
                ``upstream_unavailable`` when the audit log cannot be written.
        """
        target = route(model, self._cloud())
        if target.egress and self.sovereign:
            await self._deny(model, target, ctx)
            raise ServiceError(
                ErrorCode.FORBIDDEN,
                f"Sovereign mode is on: '{model}' would send data off the network",
            )
        provider = self._llms.get(target.provider)
        if provider is None:
            raise bad_request(f"Provider '{target.provider}' is not configured")
        await self._record(
            AuditEvent(
                actor=ctx.actor,
                action="model.chat",
                workspace_id=ctx.workspace_id,
                model=model,
                egress=target.egress,
                request_id=ctx.request_id,
                detail={"service": ctx.service.name, "provider": target.provider},
            )
        )
        return Admitted(target, provider)

    async def stream(
        self, admitted: Admitted, messages: Sequence[ChatMessage]
    ) -> AsyncIterator[str]:
        """Stream the answer to an admitted call."""
        request = CompletionRequest(model=admitted.route.model, messages=list(messages))
        async for text in admitted.provider.stream(request):
            yield text

    async def embed(
        self, texts: Sequence[str], *, model: str | None, ctx: CallContext
    ) -> list[list[float]]:
        """Embed ``texts`` after writing the audit event (counts only, never the text)."""
        if model and model != self._embedder.model:
            # Vectors from another model would not be comparable with the index.
            raise bad_request(f"This gateway embeds with '{self._embedder.model}', not '{model}'")
        if not texts or len(texts) > self._embed_max_texts:
            raise bad_request(f"Send between 1 and {self._embed_max_texts} texts")
        await self._record(
            AuditEvent(
                actor=ctx.actor,
                action="model.embed",
                workspace_id=ctx.workspace_id,
                model=self._embedder.model,
                egress=is_ollama_cloud(self._embedder.model),
                request_id=ctx.request_id,
                detail={"service": ctx.service.name, "texts": len(texts)},
            )
        )
        return await self._embedder.embed(texts)

    async def _deny(self, model: str, target: Route, ctx: CallContext) -> None:
        """Record a refusal. Nothing was sent, so ``egress`` is false."""
        try:
            await self._audit.record(
                AuditEvent(
                    actor=ctx.actor,
                    action="model.denied",
                    workspace_id=ctx.workspace_id,
                    model=model,
                    egress=False,
                    request_id=ctx.request_id,
                    detail={
                        "service": ctx.service.name,
                        "provider": target.provider,
                        "reason": "sovereign_mode",
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001 - the refusal stands either way
            _log.error("could not audit a refused model call", model=model, error=str(exc))

    async def _record(self, event: AuditEvent) -> None:
        try:
            await self._audit.record(event)
        except Exception as exc:
            _log.error(
                "audit write failed; model call refused", action=event.action, error=str(exc)
            )
            raise ServiceError(
                ErrorCode.UPSTREAM_UNAVAILABLE,
                "The audit log is unavailable, so no model call was made",
            ) from exc
