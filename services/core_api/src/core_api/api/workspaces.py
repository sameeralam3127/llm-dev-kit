"""/api/v1/me and /api/v1/workspaces."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from core_api.api.deps import CallerDep, RequestIdDep, authenticated
from core_api.ports.stores import Workspace
from core_api.services.workspaces import WorkspaceService

router = APIRouter(prefix="/api/v1", tags=["workspaces"], dependencies=[Depends(authenticated)])


class WorkspaceOut(BaseModel):
    """A workspace and the caller's role in it."""

    id: UUID
    slug: str
    name: str
    role: str
    created_at: datetime

    @classmethod
    def of(cls, w: Workspace) -> WorkspaceOut:
        """Serialise a workspace."""
        return cls(id=w.id, slug=w.slug, name=w.name, role=w.role, created_at=w.created_at)


class WorkspaceIn(BaseModel):
    """Request to create a workspace."""

    slug: str = Field(min_length=1, max_length=63)
    name: str = Field(min_length=1, max_length=200)


def _service(request: Request) -> WorkspaceService:
    service: WorkspaceService = request.app.state.workspaces
    return service


@router.get("/me")
async def me(caller: CallerDep, request: Request) -> dict[str, object]:
    """Who the server thinks you are, and your workspaces."""
    workspaces = await _service(request).mine(caller)
    return {
        "user_id": caller.user_id,
        "via": caller.via,
        "workspaces": [WorkspaceOut.of(w).model_dump(mode="json") for w in workspaces],
    }


@router.get("/workspaces")
async def list_workspaces(caller: CallerDep, request: Request) -> dict[str, list[WorkspaceOut]]:
    """Your workspaces."""
    return {"data": [WorkspaceOut.of(w) for w in await _service(request).mine(caller)]}


@router.post("/workspaces", status_code=201)
async def create_workspace(
    body: WorkspaceIn, caller: CallerDep, request: Request, rid: RequestIdDep
) -> dict[str, WorkspaceOut]:
    """Create a workspace; you become its owner."""
    workspace = await _service(request).create(
        caller, slug=body.slug, name=body.name, request_id=rid
    )
    return {"data": WorkspaceOut.of(workspace)}
