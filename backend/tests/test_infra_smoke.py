"""Smoke test: the local test-database bootstrap creates both roles + the owned DB.

In a Docker deployment these roles/DB come from ``docker/postgres/init/01-roles.sql``.
In this repo's test suite they are created by the ``test_db`` fixture in ``conftest.py``
against a locally running PostgreSQL 16 (superuser access required).
"""

from __future__ import annotations

import asyncpg
import pytest

pytestmark = pytest.mark.infra


async def test_roles_exist(test_db) -> None:
    """Both ``acms_owner`` and ``app_user`` login roles must exist."""
    conn = await asyncpg.connect(test_db.migration_url_asyncpg)
    try:
        rows = await conn.fetch(
            "SELECT rolname FROM pg_roles "
            "WHERE rolname IN ('acms_owner', 'app_user') ORDER BY rolname"
        )
    finally:
        await conn.close()
    assert [r["rolname"] for r in rows] == ["acms_owner", "app_user"]


async def test_database_exists_and_owned_by_acms_owner(test_db) -> None:
    """``acms_test`` must exist and be owned by ``acms_owner``."""
    conn = await asyncpg.connect(test_db.migration_url_asyncpg)
    try:
        owner = await conn.fetchval(
            "SELECT pg_catalog.pg_get_userbyid(d.datdba) "
            "FROM pg_catalog.pg_database d WHERE d.datname = 'acms_test'"
        )
    finally:
        await conn.close()
    assert owner == "acms_owner"
