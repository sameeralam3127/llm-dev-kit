"""Create and list workspaces."""

from __future__ import annotations

import re

from core_api.domain.access import Caller
from core_api.ports.stores import AuditEvent, AuditSink, Workspace, WorkspaceStore
from ldk_core.errors import ErrorCode, ServiceError, bad_request

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class WorkspaceService:
    """Use cases for ``/api/v1/workspaces``."""

    def __init__(self, *, workspaces: WorkspaceStore, audit: AuditSink) -> None:
        self._workspaces = workspaces
        self._audit = audit

    async def create(
        self, caller: Caller, *, slug: str, name: str, request_id: str | None
    ) -> Workspace:
        """Create a workspace owned by the caller.

        Only a signed-in user can create one: an API key is bound to an
        existing workspace and cannot spawn others.
        """
        if caller.via != "session":
            raise ServiceError(ErrorCode.FORBIDDEN, "API keys cannot create workspaces")
        if not _SLUG.match(slug):
            raise bad_request("slug must be lower-case letters, digits and hyphens")
        try:
            workspace = await self._workspaces.create_workspace(
                slug=slug, name=name, owner_id=caller.user_id
            )
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":  # unique_violation
                raise ServiceError(ErrorCode.CONFLICT, "That slug is taken") from exc
            raise
        await self._audit.record(
            AuditEvent(
                actor=caller.user_id,
                workspace_id=workspace.id,
                action="workspace.create",
                resource=f"workspace:{workspace.id}",
                request_id=request_id,
            )
        )
        return workspace

    async def mine(self, caller: Caller) -> list[Workspace]:
        """The caller's workspaces; for an API key, only the one it belongs to."""
        all_ = await self._workspaces.workspaces_of(caller.user_id)
        if caller.key_workspace_id is not None:
            return [w for w in all_ if w.id == caller.key_workspace_id]
        return all_
