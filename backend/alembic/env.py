"""Alembic environment -- async engine, driven by ``app.config``.

The URL comes from ``get_settings().migration_database_url`` (the ``acms_owner``
DDL role), never from ``alembic.ini``. Every model module is imported so that all
tables are registered on ``Base.metadata`` before autogenerate compares.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import get_settings

# Every model module must be imported so its tables register on
# ``Base.metadata`` before Alembic diffs it against the database.
from app.models import Base, alert, audit, case, grouping, user  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(
    obj: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object,
) -> bool:
    """Hide the hand-written GIN full-text indexes from autogenerate.

    The four ``to_tsvector('simple', ...)`` expression indexes created by
    ``e3f1a2b7c8d9_case_fts`` (and the customer/account-ref ones added later) are
    raw ``op.execute`` DDL -- they are not declared on any model, so
    ``--autogenerate`` sees them only in the database and would emit ``drop_index``
    for every one. Their names all end in ``_fts``; skip those so autogenerate
    leaves them untouched.
    """
    return not (type_ == "index" and name is not None and name.endswith("_fts"))


def _configure_and_run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Emit SQL without a live DB connection (``alembic upgrade --sql``)."""
    context.configure(
        url=get_settings().migration_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Open an async connection and run migrations within it."""
    engine = create_async_engine(get_settings().migration_database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_configure_and_run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
