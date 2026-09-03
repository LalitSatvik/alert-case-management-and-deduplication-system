"""Audit-log service: hash-chained, per-stream sequenced, transaction-borrowing.

The first three tests use the standard ``db_session`` (savepoint rollback). The
concurrency test needs two sessions that *really* commit to different physical
transactions so the ``SELECT ... FOR UPDATE`` on the ``audit_streams`` row is the
only thing that can serialise them -- it uses ``db_session_factory`` and is
marked ``infra`` (it also TRUNCATEs the audit tables, which savepoint isolation
cannot undo).
"""

from __future__ import annotations

import asyncio

import pytest

from app.audit.service import GENESIS_HASH, record_audit, verify_stream


async def test_first_event_chains_from_genesis(db_session):
    ev = await record_audit(
        db_session,
        stream="case:1",
        actor=None,
        action="case.created",
        target_type="case",
        target_id="1",
        after={"status": "Open"},
    )
    await db_session.commit()
    assert ev.seq == 1
    assert ev.prev_hash == GENESIS_HASH
    assert len(ev.hash) == 64


async def test_sequential_events_chain(db_session):
    e1 = await record_audit(
        db_session, stream="case:2", actor=None, action="a", target_type="case", target_id="2"
    )
    e2 = await record_audit(
        db_session, stream="case:2", actor=None, action="b", target_type="case", target_id="2"
    )
    await db_session.commit()
    assert e2.seq == 2
    assert e2.prev_hash == e1.hash
    assert verify_stream([e1, e2]) == []


async def test_verify_detects_tampering(db_session):
    e1 = await record_audit(
        db_session, stream="case:3", actor=None, action="a", target_type="case", target_id="3"
    )
    e2 = await record_audit(
        db_session, stream="case:3", actor=None, action="b", target_type="case", target_id="3"
    )
    await db_session.commit()
    e1.after = {"tampered": True}  # mutate in memory
    assert verify_stream([e1, e2]) != []


async def test_verify_detects_dropped_event_via_broken_linkage(db_session):
    # Three chained events; hand the verifier only the 1st and 3rd. Each event's
    # own hash still recomputes fine -- only the prev_hash linkage is broken
    # (e3.prev_hash == e2.hash, but e2 is missing), exercising verify_stream's
    # linkage branch rather than its self-hash branch.
    e1 = await record_audit(
        db_session, stream="case:link", actor=None, action="a", target_type="case", target_id="link"
    )
    _e2 = await record_audit(
        db_session, stream="case:link", actor=None, action="b", target_type="case", target_id="link"
    )
    e3 = await record_audit(
        db_session, stream="case:link", actor=None, action="c", target_type="case", target_id="link"
    )
    await db_session.commit()
    assert verify_stream([e1, e3]) == [e3.seq]


@pytest.mark.infra
async def test_concurrent_writes_to_same_stream_serialise(db_session_factory):
    # two sessions, same stream; the FOR UPDATE lock must force distinct seq values
    async def write(action: str) -> None:
        async with db_session_factory() as s:
            await record_audit(
                s, stream="case:9", actor=None, action=action, target_type="case", target_id="9"
            )
            await s.commit()

    await asyncio.gather(write("a"), write("b"))

    async with db_session_factory() as s:
        from sqlalchemy import select

        from app.models.audit import AuditEvent

        rows = (
            (
                await s.execute(
                    select(AuditEvent).where(AuditEvent.stream == "case:9").order_by(AuditEvent.seq)
                )
            )
            .scalars()
            .all()
        )
    assert [r.seq for r in rows] == [1, 2]
    assert verify_stream(list(rows)) == []
