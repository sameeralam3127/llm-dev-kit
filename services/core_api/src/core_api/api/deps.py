"""FastAPI dependencies: every route but /health starts here."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from core_api.domain.access import Access, Caller
from core_api.services.auth import AccessResolver
from ldk_core.observability import get_correlation_id


async def authenticated(request: Request) -> Caller:
    """Authenticate the caller, or answer 401 before any other work."""
    resolver: AccessResolver = request.app.state.resolver
    caller = await resolver.caller(request.headers.get("authorization"))
    request.state.caller = caller
    return caller


async def workspace_access(
    workspace_id: UUID, caller: Annotated[Caller, Depends(authenticated)], request: Request
) -> Access:
    """Resolve the caller against the workspace in the path, or answer 403."""
    resolver: AccessResolver = request.app.state.resolver
    return await resolver.access(caller, workspace_id)


def request_id() -> str | None:
    """The current request id, recorded on audit events."""
    return get_correlation_id()


CallerDep = Annotated[Caller, Depends(authenticated)]
AccessDep = Annotated[Access, Depends(workspace_access)]
RequestIdDep = Annotated[str | None, Depends(request_id)]
