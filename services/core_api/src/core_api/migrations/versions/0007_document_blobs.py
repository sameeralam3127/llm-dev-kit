"""Original uploads, kept in Postgres until object storage arrives.

Postgres is the single system of record in Milestone 1 (object storage is
Milestone 2), so an upload's bytes live here, written in the same transaction
as its document row and ingestion job. Either all three exist or none do.

Large ``bytea`` values are stored out of line by Postgres's TOAST mechanism,
compressed and chunked, so wide rows do not slow down queries on
``documents``. Keeping the original also means a document can be re-indexed
later without asking for the file again.

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE core.document_blobs (
        document_id   uuid PRIMARY KEY REFERENCES core.documents(id) ON DELETE CASCADE,
        media_type    text NOT NULL,
        size_bytes    bigint NOT NULL CHECK (size_bytes > 0),
        data          bytea NOT NULL,
        CHECK (octet_length(data) = size_bytes)
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE core.document_blobs;")
