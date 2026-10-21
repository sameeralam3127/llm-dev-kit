"""Workspaces and memberships, plus the pgvector extension.

Users themselves live in the web app's ``app`` schema (Prisma owns identity,
decision 1), so ``memberships.user_id`` holds the web app's user id. There is
deliberately no foreign key into ``app``: each migration tool owns its own
schema, and neither has to run before the other.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    -- pgvector adds the `vector` column type and its distance operators.
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE core.workspaces (
        id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        slug        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{0,62}$'),
        name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
        created_at  timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE core.memberships (
        workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
        user_id       text NOT NULL,
        role          text NOT NULL CHECK (role IN ('owner', 'editor', 'reader')),
        created_at    timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (workspace_id, user_id)
    );
    -- "Which workspaces can this user see?" is asked on every request.
    CREATE INDEX memberships_user_id ON core.memberships (user_id);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE core.memberships;
    DROP TABLE core.workspaces;
    -- The extension is left installed: other schemas may use it.
    """)
