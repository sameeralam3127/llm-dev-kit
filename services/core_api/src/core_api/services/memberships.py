"""Keep the instance's shared team workspace in step with the web app's users.

In the lite profile every web user works in one workspace, as in v1, where
documents are shared. The web app owns who its users are and what role each
has; core-api mirrors that here. Only the web app's service token may call
this (``api/internal.py``): a user session never can, or any member could
promote themselves.
"""

from __future__ import annotations

from uuid import UUID

from core_api.domain.access import Role
from core_api.ports.stores import AuditEvent, AuditSink, WorkspaceStore

TEAM_SLUG = "team"
TEAM_NAME = "Team"
ACTOR = "web"


class TeamMembershipService:
    """Use cases for ``/api/v1/internal/team-members``."""

    def __init__(self, *, workspaces: WorkspaceStore, audit: AuditSink) -> None:
        self._workspaces = workspaces
        self._audit = audit

    async def set_role(self, user_id: str, role: Role | None, *, request_id: str | None) -> UUID:
        """Give ``user_id`` ``role`` in the team workspace; ``None`` removes them.

        Creates the workspace on first use. Audited only when the role changes,
        since the web app calls this whenever it is unsure.
        """
        workspace_id = await self._workspaces.ensure_workspace(slug=TEAM_SLUG, name=TEAM_NAME)
        previous = await self._workspaces.set_role(workspace_id, user_id, role)
        if previous != role:
            await self._audit.record(
                AuditEvent(
                    actor=ACTOR,
                    workspace_id=workspace_id,
                    action="membership.set",
                    resource=f"user:{user_id}",
                    request_id=request_id,
                    detail={"from": previous, "to": role},
                )
            )
        return workspace_id
