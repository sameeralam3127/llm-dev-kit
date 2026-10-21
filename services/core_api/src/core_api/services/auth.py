"""Turn a request's credential into a :class:`Caller`, then into :class:`Access`.

Two kinds of credential are accepted:

* a **session token**: the short-lived RS256 token the web app signs for the
  signed-in user, verified against the web app's JWKS by an ``AuthProvider``
  (the v2 ``auth.local`` plugin). The web app stays the identity issuer.
* a **workspace API key** (``ldk_…``), checked against its stored HMAC.

Anything else, including no credential, is a 401 that says nothing about why.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from core_api.domain import api_keys
from core_api.domain.access import Access, Caller, resolve
from core_api.ports.stores import ApiKeyStore, WorkspaceStore
from ldk_core.auth import bearer_token, unauthorized
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import AuthProvider


class AccessResolver:
    """Authenticates callers and resolves their access to workspaces."""

    def __init__(
        self,
        *,
        sessions: AuthProvider,
        keys: ApiKeyStore,
        workspaces: WorkspaceStore,
        pepper: bytes,
    ) -> None:
        self._sessions = sessions
        self._keys = keys
        self._workspaces = workspaces
        self._pepper = pepper

    async def caller(self, authorization: str | None) -> Caller:
        """Who is calling. Raises a 401 for a missing or invalid credential."""
        token = bearer_token(authorization)
        if token is None:
            raise unauthorized()
        if token.startswith(api_keys.KEY_PREFIX):
            return await self._from_api_key(token)
        if self._sessions.accepts(token):
            principal = await self._sessions.authenticate(token)
            return Caller(user_id=principal.subject, via="session")
        raise unauthorized()

    async def access(self, caller: Caller, workspace_id: UUID) -> Access:
        """The caller's access to one workspace, or a 403.

        A non-member gets the same 403 as a member lacking a scope would get
        elsewhere: it does not reveal whether the workspace exists.
        """
        role = await self._workspaces.role_of(workspace_id, caller.user_id)
        access = resolve(caller, workspace_id, role)
        if access is None:
            raise ServiceError(ErrorCode.FORBIDDEN, "You do not have access to this workspace")
        return access

    async def _from_api_key(self, key: str) -> Caller:
        prefix = api_keys.parse_prefix(key)
        record = await self._keys.key_by_prefix(prefix) if prefix else None
        # Compute the HMAC even when there is no row, so a missing prefix and a
        # wrong secret take the same time.
        stored = record.digest if record else b"\0" * 32
        if not api_keys.matches(key, stored, self._pepper) or record is None:
            raise unauthorized()
        now = datetime.now(UTC)
        if record.revoked_at is not None or (record.expires_at and record.expires_at <= now):
            raise unauthorized()
        await self._keys.touch_key(record.id)
        return Caller(
            user_id=record.user_id,
            via="api_key",
            key_workspace_id=record.workspace_id,
            key_scopes=record.scopes,
            key_id=record.id,
        )
