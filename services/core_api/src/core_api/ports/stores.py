"""Storage ports for workspaces, API keys and the audit log."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from core_api.domain.access import Role, Scope


@dataclass(frozen=True, slots=True)
class Workspace:
    """A workspace as seen by one member."""

    id: UUID
    slug: str
    name: str
    role: Role
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ApiKeyRecord:
    """A stored key. The digest is here for verification and never leaves the service."""

    id: UUID
    workspace_id: UUID
    user_id: str
    name: str
    prefix: str
    digest: bytes
    scopes: frozenset[Scope]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One line of the append-only audit log."""

    actor: str
    action: str
    workspace_id: UUID | None = None
    resource: str | None = None
    model: str | None = None
    egress: bool = False
    request_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class WorkspaceStore(Protocol):
    """Workspaces and memberships."""

    async def create_workspace(self, *, slug: str, name: str, owner_id: str) -> Workspace:
        """Create a workspace with ``owner_id`` as its owner, atomically."""
        ...

    async def workspaces_of(self, user_id: str) -> list[Workspace]:
        """Every workspace ``user_id`` belongs to."""
        ...

    async def role_of(self, workspace_id: UUID, user_id: str) -> Role | None:
        """``user_id``'s role in the workspace, or ``None`` if not a member."""
        ...


class ApiKeyStore(Protocol):
    """Workspace API keys."""

    async def insert_key(
        self,
        *,
        workspace_id: UUID,
        user_id: str,
        name: str,
        prefix: str,
        digest: bytes,
        scopes: frozenset[Scope],
        expires_at: datetime | None,
    ) -> ApiKeyRecord:
        """Store a new key."""
        ...

    async def key_by_prefix(self, prefix: str) -> ApiKeyRecord | None:
        """Find a key by its lookup prefix."""
        ...

    async def keys_of_workspace(self, workspace_id: UUID) -> list[ApiKeyRecord]:
        """Unrevoked keys in a workspace, newest first."""
        ...

    async def revoke_key(self, workspace_id: UUID, key_id: UUID) -> bool:
        """Revoke a key in this workspace; ``False`` if there was none to revoke."""
        ...

    async def touch_key(self, key_id: UUID) -> None:
        """Record that a key was used (throttled by the adapter)."""
        ...


class AuditSink(Protocol):
    """Where audit events go."""

    async def record(self, event: AuditEvent) -> None:
        """Append ``event``. Never updates or deletes."""
        ...
