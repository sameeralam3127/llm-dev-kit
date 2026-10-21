"""The ingestion job queue, claimed with ``FOR UPDATE SKIP LOCKED``.

A worker claims the next job with::

    SELECT ... FROM core.ingestion_jobs
    WHERE state = 'queued' AND run_after <= now()
    ORDER BY run_after
    FOR UPDATE SKIP LOCKED
    LIMIT 1

``SKIP LOCKED`` makes concurrent workers step over rows another transaction has
already locked, so each job goes to exactly one worker without a broker. The
partial index below covers exactly that query, and stays small because
finished jobs fall out of it.

At most one live job per document: re-uploading while a job is still queued or
running cannot enqueue a second one.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE core.ingestion_jobs (
        id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        document_id   uuid NOT NULL REFERENCES core.documents(id) ON DELETE CASCADE,
        workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
        state         text NOT NULL DEFAULT 'queued'
                      CHECK (state IN ('queued', 'running', 'succeeded', 'failed')),
        attempts      integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        max_attempts  integer NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
        run_after     timestamptz NOT NULL DEFAULT now(),
        locked_by     text,
        locked_at     timestamptz,
        last_error    text,
        created_at    timestamptz NOT NULL DEFAULT now(),
        updated_at    timestamptz NOT NULL DEFAULT now(),
        CHECK (state <> 'failed' OR last_error IS NOT NULL)
    );
    CREATE INDEX ingestion_jobs_claimable ON core.ingestion_jobs (run_after)
        WHERE state = 'queued';
    CREATE UNIQUE INDEX ingestion_jobs_one_live_per_document ON core.ingestion_jobs (document_id)
        WHERE state IN ('queued', 'running');
    """)


def downgrade() -> None:
    op.execute("DROP TABLE core.ingestion_jobs;")
