"""/api/v1/internal: calls only the web app may make, with its service token."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from core_api.api.deps import RequestIdDep
from core_api.domain.access import Role
from core_api.services.memberships import TeamMembershipService
from ldk_core.auth import bearer_token, unauthorized


async def web_service(request: Request) -> None:
    """Accept only the web app's service token; 401 otherwise, or when none is set."""
    expected = request.app.state.web_service_token
    token = bearer_token(request.headers.get("authorization"))
    if expected is None or token is None or not hmac.compare_digest(token, expected):
        raise unauthorized()


router = APIRouter(
    prefix="/api/v1/internal", tags=["internal"], dependencies=[Depends(web_service)]
)


class RoleIn(BaseModel):
    """The role to give; ``null`` removes the member."""

    role: Role | None


def _service(request: Request) -> TeamMembershipService:
    service: TeamMembershipService = request.app.state.team_members
    return service


@router.put("/team-members/{user_id}")
async def set_team_member(
    user_id: str, body: RoleIn, request: Request, rid: RequestIdDep
) -> dict[str, object]:
    """Set the web user's role in the shared team workspace."""
    workspace_id = await _service(request).set_role(user_id, body.role, request_id=rid)
    return {"data": {"workspace_id": str(workspace_id), "role": body.role}}
