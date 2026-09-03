"""Persistence tests for the ``Alert`` model.

``infra``-marked: needs the local Postgres bootstrapped by ``conftest.py`` and the
full Alembic chain (``migrated_db`` via ``db_session``). Exercises the round-trip
of every column plus the ``(source_system, external_alert_id)`` unique constraint.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.alert import Alert

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.infra

_EVENT_TIME = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)


def _alert(**overrides: object) -> Alert:
    kwargs: dict[str, object] = {
        "external_alert_id": "X1",
        "source_system": "tms",
        "event_time": _EVENT_TIME,
        "received_at": _EVENT_TIME + timedelta(seconds=5),
        "amount": Decimal("100.1234"),
        "currency": "USD",
        "direction": "outbound",
    }
    kwargs.update(overrides)
    return Alert(**kwargs)


async def test_alert_round_trips_all_columns(db_session: AsyncSession) -> None:
    from app.models.case import Case

    case = Case(human_ref="CASE-ROUNDTRIP", status="Open")
    db_session.add(case)
    await db_session.flush()
    a = _alert(
        idempotency_key="idem-1",
        customer_ref="C1",
        account_ref="ACC1",
        counterparty_ref="CP1",
        merchant_name="Quick Cash LLC",
        merchant_name_normalised="quick cash llc",
        mcc="6011",
        device_id="dev-1",
        session_id="sess-1",
        ip_address="2001:db8::1",
        risk_score=42,
        rule_codes=["R1", "R2"],
        typologies=["structuring"],
        raw_payload={"nested": {"a": 1}},
        ground_truth_group_id="G1",
        case_id=case.id,
    )
    db_session.add(a)
    await db_session.commit()

    got = (await db_session.execute(sa.select(Alert).where(Alert.id == a.id))).scalar_one()
    assert isinstance(got.id, uuid.UUID)
    assert got.amount == Decimal("100.1234")
    assert got.event_time == _EVENT_TIME
    assert got.event_time.tzinfo is not None
    assert got.received_at.tzinfo is not None
    assert got.rule_codes == ["R1", "R2"]
    assert got.typologies == ["structuring"]
    assert got.raw_payload == {"nested": {"a": 1}}
    assert got.risk_score == 42
    assert got.ip_address == "2001:db8::1"
    assert isinstance(got.case_id, uuid.UUID)
    assert got.created_at is not None and got.updated_at is not None


async def test_json_columns_default_to_empty(db_session: AsyncSession) -> None:
    a = _alert(external_alert_id="X-defaults")
    db_session.add(a)
    await db_session.commit()
    got = (await db_session.execute(sa.select(Alert).where(Alert.id == a.id))).scalar_one()
    assert got.rule_codes == []
    assert got.typologies == []
    assert got.raw_payload == {}


async def test_received_at_server_default_populates(db_session: AsyncSession) -> None:
    a = Alert(
        external_alert_id="X-recv",
        source_system="tms",
        event_time=_EVENT_TIME,
        amount=Decimal(1),
        currency="USD",
        direction="inbound",
    )
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)
    assert a.received_at is not None
    assert a.received_at.tzinfo is not None


async def test_unique_source_external_rejects_duplicate(db_session: AsyncSession) -> None:
    db_session.add(_alert(external_alert_id="DUP", source_system="tms"))
    await db_session.commit()

    db_session.add(_alert(external_alert_id="DUP", source_system="tms"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_same_external_id_different_source_is_allowed(db_session: AsyncSession) -> None:
    db_session.add(_alert(external_alert_id="SHARED", source_system="tms"))
    db_session.add(_alert(external_alert_id="SHARED", source_system="cams"))
    await db_session.commit()
    count = (
        await db_session.execute(
            sa.select(sa.func.count()).select_from(Alert).where(Alert.external_alert_id == "SHARED")
        )
    ).scalar_one()
    assert count == 2


async def test_case_id_has_foreign_key_to_cases(db_session: AsyncSession) -> None:
    """The deferred FK rejects an unknown ``case_id`` is rejected by the DB."""
    a = _alert(external_alert_id="X-badfk", case_id=uuid.uuid4())
    db_session.add(a)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    fks = Alert.__table__.c.case_id.foreign_keys
    assert {fk.column.table.name for fk in fks} == {"cases"}
