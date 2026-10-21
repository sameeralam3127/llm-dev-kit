"""Conversations and messages as answer provenance.

The chat history people see stays in the web app's ``app`` schema (decision
1). These tables record what core-api did for each answer: which chunks it
retrieved, which model answered, and how many tokens it used, so every answer
can be cited and audited.

``parent_id`` lets a regenerated answer point at the message it replaces.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE core.conversations (
        id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
        user_id       text NOT NULL,
        -- The web app's chat id, when the conversation came from the chat UI.
        external_id   text,
        created_at    timestamptz NOT NULL DEFAULT now(),
        UNIQUE (workspace_id, external_id)
    );
    CREATE INDEX conversations_user ON core.conversations (workspace_id, user_id);

    CREATE TABLE core.messages (
        id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id      uuid NOT NULL REFERENCES core.conversations(id) ON DELETE CASCADE,
        parent_id            uuid REFERENCES core.messages(id) ON DELETE SET NULL,
        role                 text NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
        content              text NOT NULL,
        model                text,
        retrieved_chunk_ids  uuid[] NOT NULL DEFAULT '{}',
        tokens_in            integer CHECK (tokens_in >= 0),
        tokens_out           integer CHECK (tokens_out >= 0),
        request_id           text,
        created_at           timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX messages_conversation ON core.messages (conversation_id, created_at);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE core.messages;
    DROP TABLE core.conversations;
    """)
