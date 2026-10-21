"""The audit log: append-only, enforced by the database.

Triggers reject every UPDATE, DELETE and TRUNCATE, so not even a bug in a
service (or a compromised one) can rewrite history through normal SQL.
Retention, when it arrives, is a separate privileged job.

``workspace_id`` has no foreign key on purpose: deleting a workspace must not
delete the record of what happened in it.

``egress`` says whether the action sent data off the network, e.g. a call to a
cloud model. Sovereign mode is proven by there being no ``egress = true`` rows.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE core.audit_events (
        id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        occurred_at   timestamptz NOT NULL DEFAULT now(),
        actor         text NOT NULL,
        workspace_id  uuid,
        action        text NOT NULL,
        resource      text,
        model         text,
        egress        boolean NOT NULL DEFAULT false,
        request_id    text,
        detail        jsonb NOT NULL DEFAULT '{}'::jsonb
    );
    CREATE INDEX audit_events_workspace ON core.audit_events (workspace_id, occurred_at);
    CREATE INDEX audit_events_egress ON core.audit_events (occurred_at) WHERE egress;

    CREATE FUNCTION core.audit_events_append_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'core.audit_events is append-only (% refused)', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END;
    $$;

    CREATE TRIGGER audit_events_no_update_delete
        BEFORE UPDATE OR DELETE ON core.audit_events
        FOR EACH ROW EXECUTE FUNCTION core.audit_events_append_only();
    CREATE TRIGGER audit_events_no_truncate
        BEFORE TRUNCATE ON core.audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION core.audit_events_append_only();
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE core.audit_events;
    DROP FUNCTION core.audit_events_append_only();
    """)
