"""Documents and their chunks, with full-text and vector search indexes.

Three ideas in this migration:

* ``chunks.workspace_id`` duplicates the document's workspace so retrieval can
  filter on it directly in the WHERE clause. A composite foreign key to
  ``documents (id, workspace_id)`` makes it impossible for the copy to drift.
* ``tsv`` is a *generated* column: Postgres keeps the full-text vector in step
  with ``text`` on every write, so the application can never forget to update
  it. A GIN index makes ``tsv @@ query`` fast.
* An HNSW index on ``embedding`` with ``vector_cosine_ops`` answers "nearest by
  cosine distance" (``<=>``) approximately, in roughly logarithmic time rather
  than scanning every row.

``UNIQUE (workspace_id, content_hash)`` is what makes re-ingesting the same
file a no-op instead of a duplicate.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE core.documents (
        id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
        source_type   text NOT NULL CHECK (source_type IN ('upload', 'github')),
        source_uri    text NOT NULL,
        title         text,
        content_hash  bytea NOT NULL CHECK (octet_length(content_hash) = 32),
        status        text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'indexing', 'ready', 'failed')),
        created_by    text NOT NULL,
        created_at    timestamptz NOT NULL DEFAULT now(),
        updated_at    timestamptz NOT NULL DEFAULT now(),
        UNIQUE (workspace_id, content_hash),
        -- Target of the composite foreign key from chunks.
        UNIQUE (id, workspace_id)
    );

    CREATE TABLE core.chunks (
        id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id   uuid NOT NULL,
        workspace_id  uuid NOT NULL,
        ord           integer NOT NULL CHECK (ord >= 0),
        text          text NOT NULL,
        tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
        embedding     vector(768) NOT NULL,
        embed_model   text NOT NULL,
        page          integer,
        metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
        FOREIGN KEY (document_id, workspace_id)
            REFERENCES core.documents (id, workspace_id) ON DELETE CASCADE,
        UNIQUE (document_id, ord)
    );
    CREATE INDEX chunks_workspace_id ON core.chunks (workspace_id);
    CREATE INDEX chunks_tsv ON core.chunks USING gin (tsv);
    CREATE INDEX chunks_embedding ON core.chunks USING hnsw (embedding vector_cosine_ops);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE core.chunks;
    DROP TABLE core.documents;
    """)
