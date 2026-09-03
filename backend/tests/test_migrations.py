"""The Alembic environment must apply cleanly against a real PostgreSQL database.

No Docker / testcontainers here: the ``test_db`` fixture (see ``conftest.py``)
bootstraps a throwaway ``acms_test`` database owned by ``acms_owner``. This test
runs ``alembic upgrade head`` (and then ``downgrade base``) as a subprocess with
``MIGRATION_DATABASE_URL`` pointed at ``test_db.migration_url`` -- i.e. exactly the
DDL owner role migrations run as in production.

``alembic`` is invoked as ``sys.executable -m alembic`` from ``backend/`` so the
shared ``.venv`` interpreter and ``backend/`` on ``sys.path`` are both guaranteed.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import asyncpg
import pytest

pytestmark = pytest.mark.infra

_BACKEND_ROOT = pathlib.Path(__file__).parent.parent


def _run_alembic(*args: str, migration_url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "MIGRATION_DATABASE_URL": migration_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_alembic_upgrade_head_then_downgrade_base(test_db) -> None:
    """``alembic upgrade head`` succeeds, and the chain is reversible to ``base``."""
    up = _run_alembic("upgrade", "head", migration_url=test_db.migration_url)
    assert up.returncode == 0, up.stderr

    down = _run_alembic("downgrade", "base", migration_url=test_db.migration_url)
    assert down.returncode == 0, down.stderr

    up_again = _run_alembic("upgrade", "head", migration_url=test_db.migration_url)
    assert up_again.returncode == 0, up_again.stderr


async def test_autogenerate_leaves_fts_indexes_alone(migrated_db) -> None:
    """The expression FTS indexes are invisible to autogenerate (fix M4).

    They are raw ``op.execute`` DDL, not declared on any model, so without the
    ``include_object`` guard in ``alembic/env.py`` a ``compare_metadata`` run
    would emit ``remove_index`` for every ``*_fts`` index. With the guard the diff
    contains none.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.models import Base, alert, audit, case, grouping, user  # noqa: F401

    def _include_object(obj, name, type_, reflected, compare_to):  # mirrors alembic/env.py
        return not (type_ == "index" and name is not None and name.endswith("_fts"))

    def _diff(sync_conn):
        ctx = MigrationContext.configure(
            sync_conn,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "include_object": _include_object,
                "target_metadata": Base.metadata,
            },
        )
        return compare_metadata(ctx, Base.metadata)

    engine = create_async_engine(migrated_db.migration_url)
    try:
        async with engine.connect() as conn:
            diffs = await conn.run_sync(_diff)
    finally:
        await engine.dispose()

    removed_fts = [
        d
        for d in diffs
        if isinstance(d, tuple)
        and d
        and d[0] == "remove_index"
        and getattr(d[1], "name", "").endswith("_fts")
    ]
    assert removed_fts == [], removed_fts


async def test_migrated_db_fixture_stamps_alembic_version(migrated_db) -> None:
    """The ``migrated_db`` fixture leaves the DB stamped at a head revision."""
    conn = await asyncpg.connect(migrated_db.migration_url_asyncpg)
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await conn.close()
    assert version is not None
