"""The `core` schema's guarantees, checked against a real Postgres."""

import hashlib

import psycopg
import pytest
from alembic import command
from conftest import alembic_config

ZERO_VECTOR = "[" + ",".join(["0"] * 768) + "]"


def one(conn, sql, *params):
    return conn.execute(sql, params).fetchone()


def workspace(conn, slug="acme"):
    return one(
        conn, "INSERT INTO core.workspaces (slug, name) VALUES (%s, %s) RETURNING id", slug, slug
    )[0]


def document(conn, ws, content=b"hello"):
    return one(
        conn,
        """INSERT INTO core.documents
               (workspace_id, source_type, source_uri, content_hash, created_by)
           VALUES (%s, 'upload', 'a.pdf', %s, 'user-1') RETURNING id""",
        ws,
        hashlib.sha256(content).digest(),
    )[0]


def chunk(conn, doc, ws, ord_=0, text="sovereign mode keeps data local", vector=ZERO_VECTOR):
    return one(
        conn,
        """INSERT INTO core.chunks (document_id, workspace_id, ord, text, embedding, embed_model)
           VALUES (%s, %s, %s, %s, %s::vector, 'nomic-embed-text') RETURNING id""",
        doc,
        ws,
        ord_,
        text,
        vector,
    )[0]


def test_head_creates_every_table(conn) -> None:
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'core'"
        )
    }
    assert tables >= {
        "workspaces",
        "memberships",
        "api_keys",
        "documents",
        "chunks",
        "ingestion_jobs",
        "conversations",
        "messages",
        "audit_events",
        "alembic_version",
    }


def test_every_migration_reverses(empty_db) -> None:
    config = alembic_config(empty_db)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    with psycopg.connect(empty_db) as conn:
        left = conn.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'core' AND table_name <> 'alembic_version'"
        ).fetchone()[0]
    assert left == 0
    command.upgrade(config, "head")


def test_the_same_content_cannot_be_ingested_twice_in_a_workspace(conn) -> None:
    ws = workspace(conn)
    document(conn, ws, b"same bytes")
    with pytest.raises(psycopg.errors.UniqueViolation):
        document(conn, ws, b"same bytes")
    # ...but another workspace may hold the same file.
    document(conn, workspace(conn, "other"), b"same bytes")


def test_a_chunk_cannot_claim_another_workspace(conn) -> None:
    a, b = workspace(conn, "a"), workspace(conn, "b")
    doc = document(conn, a)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        chunk(conn, doc, b)


def test_full_text_vector_is_generated(conn) -> None:
    ws = workspace(conn)
    chunk(conn, document(conn, ws), ws, text="Priya Raman leads the Halcyon team")
    hits = one(
        conn,
        "SELECT count(*) FROM core.chunks WHERE tsv @@ plainto_tsquery('english', 'halcyon teams')",
    )[0]
    assert hits == 1


def test_embedding_must_have_768_dimensions(conn) -> None:
    ws = workspace(conn)
    with pytest.raises(psycopg.errors.DataException):
        chunk(conn, document(conn, ws), ws, vector="[1,2,3]")


def test_nearest_neighbour_search_uses_the_hnsw_index(conn) -> None:
    ws = workspace(conn)
    chunk(conn, document(conn, ws), ws)
    conn.execute("SET enable_seqscan = off")
    plan = "\n".join(
        row[0]
        for row in conn.execute(
            "EXPLAIN SELECT id FROM core.chunks ORDER BY embedding <=> %s::vector LIMIT 5",
            (ZERO_VECTOR,),
        )
    )
    assert "chunks_embedding" in plan


def test_a_document_has_at_most_one_live_job(conn) -> None:
    ws = workspace(conn)
    doc = document(conn, ws)
    conn.execute(
        "INSERT INTO core.ingestion_jobs (document_id, workspace_id) VALUES (%s, %s)", (doc, ws)
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO core.ingestion_jobs (document_id, workspace_id) VALUES (%s, %s)", (doc, ws)
        )
    conn.execute(
        "UPDATE core.ingestion_jobs SET state = 'succeeded' WHERE document_id = %s", (doc,)
    )
    conn.execute(
        "INSERT INTO core.ingestion_jobs (document_id, workspace_id) VALUES (%s, %s)", (doc, ws)
    )


def test_a_failed_job_must_say_why(conn) -> None:
    ws = workspace(conn)
    doc = document(conn, ws)
    conn.execute(
        "INSERT INTO core.ingestion_jobs (document_id, workspace_id) VALUES (%s, %s)", (doc, ws)
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "UPDATE core.ingestion_jobs SET state = 'failed' WHERE document_id = %s", (doc,)
        )


def test_api_keys_need_a_32_byte_hash_and_a_scope(conn) -> None:
    ws = workspace(conn)
    insert = """INSERT INTO core.api_keys (workspace_id, user_id, name, prefix, hash, scopes)
                VALUES (%s, 'user-1', 'laptop', %s, %s, %s)"""
    conn.execute(insert, (ws, "abcd1234", b"x" * 32, ["chat"]))
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(insert, (ws, "efgh5678", b"short", ["chat"]))
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(insert, (ws, "ijkl9012", b"y" * 32, []))


def test_the_audit_log_is_append_only(conn) -> None:
    conn.execute(
        "INSERT INTO core.audit_events (actor, action, model, egress) "
        "VALUES ('user-1', 'model.call', 'llama3.1', false)"
    )
    for statement in (
        "UPDATE core.audit_events SET egress = true",
        "DELETE FROM core.audit_events",
        "TRUNCATE core.audit_events",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(statement)
    assert one(conn, "SELECT count(*) FROM core.audit_events")[0] == 1


def test_audit_survives_workspace_deletion(conn) -> None:
    ws = workspace(conn)
    conn.execute(
        "INSERT INTO core.audit_events (actor, workspace_id, action) VALUES ('u', %s, 'x')", (ws,)
    )
    conn.execute("DELETE FROM core.workspaces WHERE id = %s", (ws,))
    assert one(conn, "SELECT count(*) FROM core.audit_events WHERE workspace_id = %s", ws)[0] == 1
