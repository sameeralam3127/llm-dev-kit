"""/api/v1/workspaces/{workspace_id}/api-keys."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from core_api.api.deps import AccessDep, RequestIdDep, authenticated
from core_api.ports.stores import ApiKeyRecord
from core_api.services.api_keys import ApiKeyService

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/api-keys",
    tags=["api-keys"],
    dependencies=[Depends(authenticated)],
)


class ApiKeyOut(BaseModel):
    """A key as listed: never the key itself."""

    id: UUID
    name: str
    prefix: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None

    @classmethod
    def of(cls, k: ApiKeyRecord) -> ApiKeyOut:
        """Serialise a stored key."""
        return cls(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            scopes=sorted(k.scopes),
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
        )


class CreatedApiKeyOut(ApiKeyOut):
    """A new key, the one response that includes it."""

    #: The only time the full key is ever returned.
    key: str


class ApiKeyIn(BaseModel):
    """Request to issue a key."""

    name: str = Field(min_length=1, max_length=100)
    scopes: list[Literal["chat", "ingest", "manage"]] = Field(default=["chat"], min_length=1)
    expires_at: datetime | None = None


def _service(request: Request) -> ApiKeyService:
    service: ApiKeyService = request.app.state.api_keys
    return service


@router.post("", status_code=201)
async def create_key(
    body: ApiKeyIn, access: AccessDep, request: Request, response: Response, rid: RequestIdDep
) -> dict[str, CreatedApiKeyOut]:
    """Issue a key. The response is the only time the key is shown."""
    record, plaintext = await _service(request).create(
        access,
        name=body.name,
        scopes=frozenset(body.scopes),
        expires_at=body.expires_at,
        request_id=rid,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"data": CreatedApiKeyOut(**ApiKeyOut.of(record).model_dump(), key=plaintext)}


@router.get("")
async def list_keys(access: AccessDep, request: Request) -> dict[str, list[ApiKeyOut]]:
    """List the workspace's active keys."""
    return {"data": [ApiKeyOut.of(k) for k in await _service(request).list(access)]}


@router.delete("/{key_id}", status_code=204)
async def revoke_key(
    key_id: UUID, access: AccessDep, request: Request, rid: RequestIdDep
) -> Response:
    """Revoke a key; it stops working at once."""
    await _service(request).revoke(access, key_id, request_id=rid)
    return Response(status_code=204)
