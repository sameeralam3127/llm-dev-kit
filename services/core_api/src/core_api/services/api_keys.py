"""Issue, list and revoke workspace API keys."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from core_api.domain import api_keys
from core_api.domain.access import Access, Scope
from core_api.ports.stores import ApiKeyRecord, ApiKeyStore, AuditEvent, AuditSink
from ldk_core.auth import forbidden
from ldk_core.errors import ErrorCode, ServiceError, not_found

MAX_KEYS_PER_WORKSPACE = 50


class ApiKeyService:
    """Use cases for the ``/api/v1/workspaces/{id}/api-keys`` endpoints."""

    def __init__(self, *, keys: ApiKeyStore, audit: AuditSink, pepper: bytes) -> None:
        self._keys = keys
        self._audit = audit
        self._pepper = pepper

    async def create(
        self,
        access: Access,
        *,
        name: str,
        scopes: frozenset[Scope],
        expires_at: datetime | None,
        request_id: str | None,
    ) -> tuple[ApiKeyRecord, str]:
        """Issue a key; returns the record and the plaintext, shown once.

        A key can never hold a scope its creator lacks, and only owners
        (``manage``) issue keys at all.
        """
        _require(access, "manage")
        if not scopes <= access.scopes:
            raise forbidden(",".join(sorted(scopes - access.scopes)))
        if len(await self._keys.keys_of_workspace(access.workspace_id)) >= MAX_KEYS_PER_WORKSPACE:
            raise ServiceError(
                ErrorCode.CONFLICT, "This workspace already has the maximum number of keys"
            )

        new = api_keys.generate(self._pepper)
        record = await self._keys.insert_key(
            workspace_id=access.workspace_id,
            user_id=access.user_id,
            name=name,
            prefix=new.prefix,
            digest=new.digest,
            scopes=scopes,
            expires_at=expires_at,
        )
        await self._audit.record(
            AuditEvent(
                actor=access.user_id,
                workspace_id=access.workspace_id,
                action="api_key.create",
                resource=f"api_key:{record.id}",
                request_id=request_id,
                detail={"scopes": sorted(scopes), "via": access.via},
            )
        )
        return record, new.plaintext

    async def list(self, access: Access) -> list[ApiKeyRecord]:
        """Unrevoked keys in the workspace."""
        _require(access, "manage")
        return await self._keys.keys_of_workspace(access.workspace_id)

    async def revoke(self, access: Access, key_id: UUID, *, request_id: str | None) -> None:
        """Revoke a key in this workspace."""
        _require(access, "manage")
        if not await self._keys.revoke_key(access.workspace_id, key_id):
            raise not_found("API key")
        await self._audit.record(
            AuditEvent(
                actor=access.user_id,
                workspace_id=access.workspace_id,
                action="api_key.revoke",
                resource=f"api_key:{key_id}",
                request_id=request_id,
                detail={"via": access.via},
            )
        )


def _require(access: Access, scope: Scope) -> None:
    if not access.allows(scope):
        raise forbidden(scope)
