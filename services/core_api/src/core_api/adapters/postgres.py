"""The Postgres adapter: every port, in plain SQL over one async pool."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from core_api.domain.access import Role, Scope
from core_api.domain.ingestion import IndexedChunk
from core_api.domain.retrieval import Hit
from core_api.ports.jobs import Blob, Job
from core_api.ports.stores import ApiKeyRecord, AuditEvent, DocumentRecord, Workspace

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


_DOCUMENT_COLUMNS = """d.id, d.workspace_id, d.source_type, d.source_uri, d.title, d.status,
                       d.created_by, d.created_at, d.updated_at,
                       (SELECT count(*) FROM core.chunks c
                        WHERE c.document_id = d.id) AS chunk_count,
                       (SELECT j.last_error FROM core.ingestion_jobs j WHERE j.document_id = d.id
                        ORDER BY j.id DESC LIMIT 1) AS last_error"""

_JOB_COLUMNS = "id, document_id, workspace_id, attempts, max_attempts, locked_by"


def _vector(values: list[float]) -> str:
    """The text form pgvector parses, ``[0.1,0.2,…]``. No client library needed."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


class PostgresStore:
    """Implements every core-api port: workspaces, keys, audit, documents and jobs."""

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

    # -------------------------------------------------------------- documents

    async def create_upload(
        self,
        *,
        workspace_id: UUID,
        user_id: str,
        filename: str,
        media_type: str,
        data: bytes,
        content_hash: bytes,
    ) -> tuple[DocumentRecord, bool]:
        """Document, blob and job in one transaction; a duplicate creates nothing."""
        async with self._pool.connection() as conn, conn.transaction():
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                """INSERT INTO core.documents
                       (workspace_id, source_type, source_uri, title, content_hash, created_by)
                   VALUES (%s, 'upload', %s, %s, %s, %s)
                   ON CONFLICT (workspace_id, content_hash) DO NOTHING
                   RETURNING id""",
                (workspace_id, f"upload:{filename}", filename, content_hash, user_id),
            )
            inserted = await cur.fetchone()
            if inserted is None:
                await cur.execute(
                    f"""SELECT {_DOCUMENT_COLUMNS} FROM core.documents d
                        WHERE d.workspace_id = %s AND d.content_hash = %s""",  # noqa: S608
                    (workspace_id, content_hash),
                )
                existing = await cur.fetchone()
                assert existing is not None
                return DocumentRecord(**existing), False

            await cur.execute(
                """INSERT INTO core.document_blobs (document_id, media_type, size_bytes, data)
                   VALUES (%s, %s, %s, %s)""",
                (inserted["id"], media_type, len(data), data),
            )
            await cur.execute(
                "INSERT INTO core.ingestion_jobs (document_id, workspace_id) VALUES (%s, %s)",
                (inserted["id"], workspace_id),
            )
            await cur.execute(
                f"SELECT {_DOCUMENT_COLUMNS} FROM core.documents d WHERE d.id = %s",  # noqa: S608
                (inserted["id"],),
            )
            row = await cur.fetchone()
            assert row is not None
            return DocumentRecord(**row), True

    async def documents_of(self, workspace_id: UUID) -> list[DocumentRecord]:
        """Newest first; the WHERE clause is the tenant boundary."""
        async with self._pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                f"""SELECT {_DOCUMENT_COLUMNS} FROM core.documents d
                    WHERE d.workspace_id = %s ORDER BY d.created_at DESC""",  # noqa: S608
                (workspace_id,),
            )
            return [DocumentRecord(**row) for row in await cur.fetchall()]

    # ------------------------------------------------------------- job queue

    async def claim(self, worker_id: str) -> Job | None:
        """Take one due job with ``FOR UPDATE SKIP LOCKED``, then commit at once.

        The inner SELECT locks one queued row; ``SKIP LOCKED`` makes a second
        worker running the same query step over it instead of waiting, so each
        job goes to exactly one worker. The claim commits immediately, and the
        slow work happens outside any open transaction, protected by the
        lease (``locked_by``, ``locked_at``) instead of a held lock.
        """
        async with self._pool.connection() as conn, conn.transaction():
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                f"""WITH next AS (
                        SELECT id FROM core.ingestion_jobs
                        WHERE state = 'queued' AND run_after <= now()
                        ORDER BY run_after, id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE core.ingestion_jobs j
                    SET state = 'running', attempts = j.attempts + 1,
                        locked_by = %s, locked_at = now(), updated_at = now()
                    FROM next WHERE j.id = next.id
                    RETURNING {", ".join("j." + c for c in _JOB_COLUMNS.split(", "))}""",  # noqa: S608
                (worker_id,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            await cur.execute(
                "UPDATE core.documents SET status = 'indexing', updated_at = now() WHERE id = %s",
                (row["document_id"],),
            )
            return Job(**row)

    async def reclaim_expired(self, lease_seconds: float) -> int:
        """Requeue jobs whose lease ran out (the worker crashed or hung).

        The crashed attempt still counts, so a job that kills its worker every
        time ends up ``failed`` instead of looping forever.
        """
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                """UPDATE core.ingestion_jobs
                   SET state = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
                       last_error = 'worker stopped before finishing (lease expired)',
                       locked_by = NULL, locked_at = NULL, updated_at = now()
                   WHERE state = 'running'
                     AND locked_at < now() - make_interval(secs => %s)
                   RETURNING document_id, state""",
                (lease_seconds,),
            )
            rows = await cur.fetchall()
            for document_id, state in rows:
                await conn.execute(
                    "UPDATE core.documents SET status = %s, updated_at = now() WHERE id = %s",
                    ("failed" if state == "failed" else "pending", document_id),
                )
            return len(rows)

    async def retry_later(self, job: Job, error: str, run_after: datetime) -> bool:
        """Requeue with a delay, only if this worker still holds the lease."""
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                """UPDATE core.ingestion_jobs
                   SET state = 'queued', run_after = %s, last_error = %s,
                       locked_by = NULL, locked_at = NULL, updated_at = now()
                   WHERE id = %s AND state = 'running' AND locked_by = %s""",
                (run_after, error, job.id, job.locked_by),
            )
            if cur.rowcount != 1:
                return False
            await conn.execute(
                "UPDATE core.documents SET status = 'pending', updated_at = now() WHERE id = %s",
                (job.document_id,),
            )
            return True

    async def fail(self, job: Job, error: str) -> bool:
        """Mark the job and its document failed, only if the lease is still ours."""
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                """UPDATE core.ingestion_jobs
                   SET state = 'failed', last_error = %s,
                       locked_by = NULL, locked_at = NULL, updated_at = now()
                   WHERE id = %s AND state = 'running' AND locked_by = %s""",
                (error, job.id, job.locked_by),
            )
            if cur.rowcount != 1:
                return False
            await conn.execute(
                "UPDATE core.documents SET status = 'failed', updated_at = now() WHERE id = %s",
                (job.document_id,),
            )
            return True

    # -------------------------------------------------------------- ingestion

    async def blob_of(self, document_id: UUID) -> Blob | None:
        """The original bytes and the name they were uploaded under."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """SELECT b.data, b.media_type, d.title
                   FROM core.document_blobs b JOIN core.documents d ON d.id = b.document_id
                   WHERE b.document_id = %s""",
                (document_id,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            return Blob(data=bytes(row[0]), media_type=row[1], filename=row[2] or "document")

    async def replace_chunks(self, job: Job, chunks: list[IndexedChunk], embed_model: str) -> bool:
        """Delete the old chunks, insert the new ones and finish the job, atomically.

        ``SELECT … FOR UPDATE`` on the job first is the *fence*: if this
        worker's lease expired and another worker took the job over, it finds
        no row it owns, and writes nothing. Because everything happens in one
        transaction, a reader sees the complete old set of chunks until the
        commit, then the complete new set.
        """
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                """SELECT 1 FROM core.ingestion_jobs
                   WHERE id = %s AND state = 'running' AND locked_by = %s
                   FOR UPDATE""",
                (job.id, job.locked_by),
            )
            if await cur.fetchone() is None:
                return False
            await conn.execute("DELETE FROM core.chunks WHERE document_id = %s", (job.document_id,))
            async with conn.cursor() as insert:
                await insert.executemany(
                    """INSERT INTO core.chunks
                           (document_id, workspace_id, ord, text, page, embedding, embed_model)
                       VALUES (%s, %s, %s, %s, %s, %s::vector, %s)""",
                    [
                        (
                            job.document_id,
                            job.workspace_id,
                            chunk.ord,
                            chunk.text,
                            chunk.page,
                            _vector(chunk.embedding),
                            embed_model,
                        )
                        for chunk in chunks
                    ],
                )
            await conn.execute(
                "UPDATE core.documents SET status = 'ready', updated_at = now() WHERE id = %s",
                (job.document_id,),
            )
            await conn.execute(
                """UPDATE core.ingestion_jobs
                   SET state = 'succeeded', last_error = NULL,
                       locked_by = NULL, locked_at = NULL, updated_at = now()
                   WHERE id = %s""",
                (job.id,),
            )
            return True

    # -------------------------------------------------------------- retrieval

    async def search(
        self, workspace_id: UUID, *, text: str, vector: Sequence[float], k: int
    ) -> tuple[list[Hit], list[Hit]]:
        """Top-``k`` by cosine distance and top-``k`` by full-text rank, in one workspace.

        **Tenancy is in the SQL.** Both queries filter ``workspace_id`` in their
        WHERE clause, so another workspace's chunks are never read, let alone
        returned; nothing is filtered afterwards in Python.

        **Filtered vector search.** An HNSW index walks the graph for its best
        ``ef_search`` candidates and only then applies the WHERE clause, so a
        small workspace among many could get back fewer than ``k`` rows.
        ``hnsw.iterative_scan`` (pgvector 0.8) makes the index keep searching
        until enough rows pass the filter. ``relaxed_order`` allows slightly
        out-of-order results, which is fine because RRF re-ranks them anyway.

        **Full-text terms are OR-ed.** ``plainto_tsquery`` stems the question and
        drops stop words, but joins the terms with AND, so a chunk would need
        every word of the question. A question nearly always has words its
        answer lacks ("date" in "BLUEFIN-42 ship date"), so the terms are joined
        with OR instead, and ``ts_rank_cd`` ranks chunks matching more of them
        higher.
        """
        hit_columns = "c.id, c.document_id, d.title, c.page, c.text"
        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
            semantic = await conn.execute(
                f"""SELECT {hit_columns}
                    FROM core.chunks c JOIN core.documents d ON d.id = c.document_id
                    WHERE c.workspace_id = %s
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s""",  # noqa: S608
                (workspace_id, _vector(list(vector)), k),
            )
            semantic_rows = await semantic.fetchall()
            lexical = await conn.execute(
                f"""SELECT {hit_columns}
                    FROM core.chunks c JOIN core.documents d ON d.id = c.document_id,
                         to_tsquery('english', replace(
                             plainto_tsquery('english', %s)::text, ' & ', ' | ')) AS q
                    WHERE c.workspace_id = %s AND c.tsv @@ q
                    ORDER BY ts_rank_cd(c.tsv, q) DESC
                    LIMIT %s""",  # noqa: S608
                (text, workspace_id, k),
            )
            lexical_rows = await lexical.fetchall()
        return [Hit(*row) for row in semantic_rows], [Hit(*row) for row in lexical_rows]

    async def record_exchange(
        self,
        *,
        workspace_id: UUID,
        user_id: str,
        external_id: str | None,
        question: str,
        answer: str,
        model: str,
        chunk_ids: Sequence[UUID],
        tokens_in: int | None,
        tokens_out: int | None,
        request_id: str | None,
    ) -> None:
        """One conversation per external chat id (or per exchange without one)."""
        async with self._pool.connection() as conn, conn.transaction():
            if external_id is not None:
                cur = await conn.execute(
                    """INSERT INTO core.conversations (workspace_id, user_id, external_id)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (workspace_id, external_id)
                       DO UPDATE SET external_id = EXCLUDED.external_id
                       RETURNING id""",
                    (workspace_id, user_id, external_id),
                )
            else:
                cur = await conn.execute(
                    "INSERT INTO core.conversations (workspace_id, user_id)"
                    " VALUES (%s, %s) RETURNING id",
                    (workspace_id, user_id),
                )
            row = await cur.fetchone()
            assert row is not None
            conversation_id = row[0]
            cur = await conn.execute(
                """INSERT INTO core.messages (conversation_id, role, content, request_id)
                   VALUES (%s, 'user', %s, %s) RETURNING id""",
                (conversation_id, question, request_id),
            )
            asked = await cur.fetchone()
            assert asked is not None
            await conn.execute(
                """INSERT INTO core.messages
                       (conversation_id, parent_id, role, content, model,
                        retrieved_chunk_ids, tokens_in, tokens_out, request_id)
                   VALUES (%s, %s, 'assistant', %s, %s, %s, %s, %s, %s)""",
                (
                    conversation_id,
                    asked[0],
                    answer,
                    model,
                    list(chunk_ids),
                    tokens_in,
                    tokens_out,
                    request_id,
                ),
            )
