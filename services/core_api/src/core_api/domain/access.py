"""Who may do what in a workspace.

Every request resolves to an :class:`Access`: a user, a workspace, and the
scopes they hold there. Scopes come from the membership role, or for an API key
from the scopes it was issued with, which can never exceed its owner's role.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

Role = Literal["owner", "editor", "reader"]
Scope = Literal["chat", "ingest", "manage"]
Via = Literal["session", "api_key"]

ROLES: tuple[Role, ...] = ("reader", "editor", "owner")

SCOPES_BY_ROLE: dict[Role, frozenset[Scope]] = {
    "reader": frozenset({"chat"}),
    "editor": frozenset({"chat", "ingest"}),
    "owner": frozenset({"chat", "ingest", "manage"}),
}
ALL_SCOPES: frozenset[Scope] = SCOPES_BY_ROLE["owner"]


@dataclass(frozen=True, slots=True)
class Caller:
    """An authenticated caller before a workspace is chosen."""

    user_id: str
    via: Via
    #: Set when the caller used an API key: keys are bound to one workspace.
    key_workspace_id: UUID | None = None
    key_scopes: frozenset[Scope] | None = None
    key_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Access:
    """A caller resolved against one workspace."""

    user_id: str
    workspace_id: UUID
    role: Role
    scopes: frozenset[Scope]
    via: Via
    key_id: UUID | None = None

    def allows(self, scope: Scope) -> bool:
        """Return whether this access grants ``scope``."""
        return scope in self.scopes


def resolve(caller: Caller, workspace_id: UUID, role: Role | None) -> Access | None:
    """Combine a caller, a workspace and their membership role.

    Returns ``None`` when the caller has no access at all: no membership, or an
    API key used outside the workspace it was issued for. An API key's scopes
    are intersected with its owner's *current* role, so demoting someone
    narrows their keys immediately.
    """
    if role is None:
        return None
    if caller.key_workspace_id is not None and caller.key_workspace_id != workspace_id:
        return None
    granted = SCOPES_BY_ROLE[role]
    if caller.key_scopes is not None:
        granted = granted & caller.key_scopes
    return Access(
        user_id=caller.user_id,
        workspace_id=workspace_id,
        role=role,
        scopes=granted,
        via=caller.via,
        key_id=caller.key_id,
    )
