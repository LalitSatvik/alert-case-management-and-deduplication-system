"""The ``app_user`` DB role must be append-only on the audit tables.

These tests connect as the least-privilege *runtime* role (``migrated_db.app_url``
-> ``app_user``), not the DDL owner, and assert the privilege boundary the
``de0fe5693ed3_audit_grants`` migration establishes:

* ``audit_events``  -- INSERT yes (the audit write path needs it), UPDATE/DELETE no.
* ``audit_streams`` -- UPDATE yes (``record_audit`` bumps the tip), DELETE no.

They really commit, so a ``_clean_audit`` fixture TRUNCATEs both tables as the
owner afterwards (``app_user`` deliberately cannot).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.audit.service import GENESIS_HASH

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from tests.conftest import BootstrappedDb

pytestmark = pytest.mark.infra

_INSERT_EVENT = text(
    "INSERT INTO audit_events "
    "(stream, seq, prev_hash, hash, action, target_type, target_id, created_at) "
    "VALUES ('s', 1, :genesis, 'h', 'a', 't', 'i', now())"
)


@pytest.fixture
async def app_engine(migrated_db: BootstrappedDb) -> AsyncIterator[AsyncEngine]:
    """Async engine authenticated as the least-privilege ``app_user`` role."""
    engine = create_async_engine(migrated_db.app_url, poolclass=NullPool, future=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def _clean_audit(migrated_db: BootstrappedDb) -> AsyncIterator[None]:
    """TRUNCATE the audit tables as the owner after the test (app_user cannot)."""
    yield
    owner = create_async_engine(migrated_db.migration_url, poolclass=NullPool, future=True)
    try:
        async with owner.begin() as conn:
            await conn.execute(text("TRUNCATE audit_events, audit_streams"))
    finally:
        await owner.dispose()


async def test_app_user_can_insert_audit_events(
    app_engine: AsyncEngine, _clean_audit: None
) -> None:
    async with app_engine.begin() as conn:
        await conn.execute(_INSERT_EVENT, {"genesis": GENESIS_HASH})
        count = await conn.scalar(text("SELECT count(*) FROM audit_events WHERE stream = 's'"))
    assert count == 1


async def test_app_user_cannot_update_audit_events(
    app_engine: AsyncEngine, _clean_audit: None
) -> None:
    async with app_engine.begin() as conn:
        await conn.execute(_INSERT_EVENT, {"genesis": GENESIS_HASH})
    async with app_engine.connect() as conn:
        with pytest.raises(ProgrammingError):
            await conn.execute(text("UPDATE audit_events SET reason = 'x' WHERE stream = 's'"))


async def test_app_user_cannot_delete_audit_events(
    app_engine: AsyncEngine, _clean_audit: None
) -> None:
    async with app_engine.begin() as conn:
        await conn.execute(_INSERT_EVENT, {"genesis": GENESIS_HASH})
    async with app_engine.connect() as conn:
        with pytest.raises(ProgrammingError):
            await conn.execute(text("DELETE FROM audit_events WHERE stream = 's'"))


async def test_app_user_can_update_but_not_delete_audit_streams(
    app_engine: AsyncEngine, _clean_audit: None
) -> None:
    async with app_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO audit_streams (stream, last_seq, last_hash) "
                "VALUES ('s', 0, :genesis)"
            ),
            {"genesis": GENESIS_HASH},
        )
    # UPDATE is allowed (record_audit bumps last_seq / last_hash).
    async with app_engine.begin() as conn:
        await conn.execute(text("UPDATE audit_streams SET last_seq = 1 WHERE stream = 's'"))
    # DELETE is not.
    async with app_engine.connect() as conn:
        with pytest.raises(ProgrammingError):
            await conn.execute(text("DELETE FROM audit_streams WHERE stream = 's'"))
