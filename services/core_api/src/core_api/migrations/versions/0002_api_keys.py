"""Workspace-scoped API keys, stored as a lookup prefix and an HMAC.

A key looks like ``sk-ldk-<prefix>_<secret>``. The prefix finds the row; the
stored ``hash`` is HMAC-SHA-256(pepper, key), where the pepper is a server
secret that never touches the database (decision 2). A stolen database dump
therefore cannot be used to check guesses offline.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE core.api_keys (
        id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
        user_id       text NOT NULL,
        name          text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
        prefix        text NOT NULL UNIQUE CHECK (prefix ~ '^[A-Za-z0-9]{8,16}$'),
        hash          bytea NOT NULL CHECK (octet_length(hash) = 32),
        scopes        text[] NOT NULL CHECK (cardinality(scopes) > 0),
        created_at    timestamptz NOT NULL DEFAULT now(),
        last_used_at  timestamptz,
        expires_at    timestamptz,
        revoked_at    timestamptz,
        CHECK (expires_at IS NULL OR expires_at > created_at)
    );
    CREATE INDEX api_keys_workspace_id ON core.api_keys (workspace_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE core.api_keys;")
