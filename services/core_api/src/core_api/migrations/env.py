"""Alembic environment: run every migration inside the ``core`` schema.

Prisma (the web app) owns the ``app`` schema in the same database; this file
never touches it. The version table lives in ``core`` too, so the two tools'
bookkeeping cannot collide.
"""

import os

from alembic import context
from sqlalchemy import create_engine, text

SCHEMA = "core"


def _url() -> str:
    url = context.config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"]
    # SQLAlchemy needs the driver named; plain postgresql:// would pick psycopg2.
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        connection.commit()
        context.configure(
            connection=connection,
            version_table_schema=SCHEMA,
            # One transaction per migration: a failure leaves no half-applied step.
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL script) mode is not used; run against a database.")
run_migrations_online()
