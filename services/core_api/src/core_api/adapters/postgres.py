"""The Postgres adapter: every port, in plain SQL over one async pool."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from core_api.domain.access import Role, Scope
from core_api.ports.stores import ApiKeyRecord, AuditEvent, Workspace

_KEY_COLUMNS = """id, workspace_id, user_id, name, prefix, hash, scopes,
                  created_at, last_used_at, expires_at, revoked_at"""


def _key(row: dict[str, Any]) -> ApiKeyRecord:
    return ApiKeyRecord(
        id=row["id"],
        workspace_id=row["workspace_id"],
        user_id=row["user_id"],
        name=row["name"],
        prefix=row["prefix"],
        digest=bytes(row["hash"]),
        scopes=frozenset(row["scopes"]),
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
    )


class PostgresStore:
    """Implements :class:`WorkspaceStore`, :class:`ApiKeyStore` and :class:`AuditSink`."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    # ------------------------------------------------------------ workspaces

    async def create_workspace(self, *, slug: str, name: str, owner_id: str) -> Workspace:
        """Insert the workspace and its owner's membership in one transaction."""
        async with self._pool.connection() as conn, conn.transaction():
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                "INSERT INTO core.workspaces (slug, name) VALUES (%s, %s)"
                " RETURNING id, slug, name, created_at",
                (slug, name),
            )
            row = await cur.fetchone()
            assert row is not None
            await cur.execute(
                "INSERT INTO core.memberships (workspace_id, user_id, role)"
                " VALUES (%s, %s, 'owner')",
                (row["id"], owner_id),
            )
        return Workspace(role="owner", **row)

    async def workspaces_of(self, user_id: str) -> list[Workspace]:
        """Every workspace the user belongs to, oldest first."""
        async with self._pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                """SELECT w.id, w.slug, w.name, w.created_at, m.role
                   FROM core.workspaces w JOIN core.memberships m ON m.workspace_id = w.id
                   WHERE m.user_id = %s ORDER BY w.created_at""",
                (user_id,),
            )
            return [Workspace(**row) for row in await cur.fetchall()]

    async def role_of(self, workspace_id: UUID, user_id: str) -> Role | None:
        """The member's role, or ``None``."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT role FROM core.memberships WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            row = await cur.fetchone()
            return row[0] if row else None

    # --------------------------------------------------------------- api keys

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
        """Store a key's digest; the plaintext never reaches this layer."""
        async with self._pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                f"""INSERT INTO core.api_keys
                        (workspace_id, user_id, name, prefix, hash, scopes, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {_KEY_COLUMNS}""",  # noqa: S608
                (workspace_id, user_id, name, prefix, digest, sorted(scopes), expires_at),
            )
            row = await cur.fetchone()
            assert row is not None
            return _key(row)

    async def key_by_prefix(self, prefix: str) -> ApiKeyRecord | None:
        """The key with this prefix, revoked or not."""
        async with self._pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                f"SELECT {_KEY_COLUMNS} FROM core.api_keys WHERE prefix = %s",  # noqa: S608
                (prefix,),
            )
            row = await cur.fetchone()
            return _key(row) if row else None

    async def keys_of_workspace(self, workspace_id: UUID) -> list[ApiKeyRecord]:
        """Unrevoked keys, newest first."""
        async with self._pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                f"""SELECT {_KEY_COLUMNS} FROM core.api_keys
                    WHERE workspace_id = %s AND revoked_at IS NULL
                    ORDER BY created_at DESC""",  # noqa: S608
                (workspace_id,),
            )
            return [_key(row) for row in await cur.fetchall()]

    async def revoke_key(self, workspace_id: UUID, key_id: UUID) -> bool:
        """Revoke; the workspace condition stops one workspace revoking another's key."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """UPDATE core.api_keys SET revoked_at = now()
                   WHERE id = %s AND workspace_id = %s AND revoked_at IS NULL""",
                (key_id, workspace_id),
            )
            return cur.rowcount == 1

    async def touch_key(self, key_id: UUID) -> None:
        """Set ``last_used_at``, at most once a minute per key."""
        async with self._pool.connection() as conn:
            await conn.execute(
                """UPDATE core.api_keys SET last_used_at = now()
                   WHERE id = %s
                     AND (last_used_at IS NULL OR last_used_at < now() - interval '1 minute')""",
                (key_id,),
            )

    # ------------------------------------------------------------------ audit

    async def record(self, event: AuditEvent) -> None:
        """Append one audit event."""
        async with self._pool.connection() as conn:
            await conn.execute(
                """INSERT INTO core.audit_events
                       (actor, workspace_id, action, resource, model, egress, request_id, detail)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    event.actor,
                    event.workspace_id,
                    event.action,
                    event.resource,
                    event.model,
                    event.egress,
                    event.request_id,
                    Jsonb(event.detail),
                ),
            )
