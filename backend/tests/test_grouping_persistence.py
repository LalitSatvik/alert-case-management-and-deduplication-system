"""Integration tests for :func:`app.grouping.persistence.apply_grouping_for_alert`.

``infra``-marked: needs the bootstrapped local Postgres + the full Alembic chain
(via ``db_session``). Each test drives the real create / attach / merge / closed
branches and commits inside the surrounding rollback net.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select

from app.models.alert import Alert
from app.models.case import Case, CaseAlertLink
from app.models.grouping import GroupingDecision

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.infra


async def test_first_alert_creates_a_singleton_case(
    db_session: AsyncSession, make_alert, grouping_config
) -> None:
    from app.grouping.persistence import apply_grouping_for_alert

    a1 = await make_alert(account_ref="A", counterparty_ref="C", amount="500", risk_score=40)
    case, decision = await apply_grouping_for_alert(db_session, a1, grouping_config, "tms")
    await db_session.commit()

    assert case.human_ref.startswith("CASE-")
    assert case.status == "Open"
    assert case.alert_count == 1
    assert case.risk_score == 40
    assert case.version == 1  # fresh case: not bumped
    assert decision.method == "singleton"
    assert decision.engine_version == "1.0.0"
    assert a1.case_id == case.id

    link = (
        await db_session.execute(select(CaseAlertLink).where(CaseAlertLink.alert_id == a1.id))
    ).scalar_one()
    assert link.case_id == case.id
    assert link.grouping_decision_id == decision.id
    assert link.linked_by == "tms"


async def test_second_alert_joins_first_alerts_case(
    db_session: AsyncSession, make_alert, grouping_config
) -> None:
    from app.grouping.persistence import apply_grouping_for_alert

    a1 = await make_alert(account_ref="A", counterparty_ref="C", amount="500", risk_score=30)
    case1, _ = await apply_grouping_for_alert(db_session, a1, grouping_config, "tms")
    a2 = await make_alert(
        account_ref="A", counterparty_ref="C", amount="500", minutes=10, risk_score=70
    )
    case2, decision = await apply_grouping_for_alert(db_session, a2, grouping_config, "tms")
    await db_session.commit()

    assert case2.id == case1.id
    assert decision.method == "deterministic"
    assert decision.engine_version == "1.0.0"
    assert case2.alert_count == 2
    assert case2.risk_score == 70  # risk_aggregation: max
    assert case2.version == 2  # existing case mutated -> bumped once

    n_cases = await db_session.scalar(select(func.count()).select_from(Case))
    assert n_cases == 1


async def test_unrelated_alert_gets_its_own_case(
    db_session: AsyncSession, make_alert, grouping_config
) -> None:
    from app.grouping.persistence import apply_grouping_for_alert

    a1 = await make_alert(account_ref="A", counterparty_ref="C", amount="500")
    case1, _ = await apply_grouping_for_alert(db_session, a1, grouping_config, "tms")
    a2 = await make_alert(account_ref="Z", counterparty_ref="Q", amount="3", minutes=5)
    case2, _ = await apply_grouping_for_alert(db_session, a2, grouping_config, "tms")
    await db_session.commit()

    assert case1.id != case2.id
    n_cases = await db_session.scalar(select(func.count()).select_from(Case))
    assert n_cases == 2


async def test_merge_picks_earliest_case_as_survivor(
    db_session: AsyncSession, make_alert, grouping_config
) -> None:
    from app.grouping.persistence import apply_grouping_for_alert

    # Two separate cases: a1 keyed on counterparty_ref, a2 keyed on customer_ref.
    a1 = await make_alert(counterparty_ref="C", amount="500", minutes=0)
    case1, _ = await apply_grouping_for_alert(db_session, a1, grouping_config, "tms")
    a2 = await make_alert(customer_ref="CUST", account_ref="B", amount="700", minutes=1)
    case2, _ = await apply_grouping_for_alert(db_session, a2, grouping_config, "tms")
    assert case1.id != case2.id

    # a3 deterministically matches BOTH (counterparty_ref C -> a1, customer_ref CUST -> a2).
    a3 = await make_alert(customer_ref="CUST", counterparty_ref="C", amount="900", minutes=2)
    target, _ = await apply_grouping_for_alert(db_session, a3, grouping_config, "tms")
    await db_session.commit()

    all_cases = {c.id: c for c in (await db_session.execute(select(Case))).scalars().all()}
    assert len(all_cases) == 2
    survivor = all_cases[target.id]
    (other,) = [c for cid, c in all_cases.items() if cid != target.id]

    assert target.id in (case1.id, case2.id)
    assert survivor.status == "Open"
    assert other.status == "Merged"
    assert other.canonical_from_case_id == survivor.id
    assert survivor.alert_count == 3

    # Every alert (and its link) now points at the survivor.
    alert_cases = set((await db_session.execute(select(Alert.case_id))).scalars().all())
    assert alert_cases == {survivor.id}
    link_cases = set((await db_session.execute(select(CaseAlertLink.case_id))).scalars().all())
    assert link_cases == {survivor.id}

    # One GroupingDecision row written per apply_grouping_for_alert call.
    n_decisions = await db_session.scalar(select(func.count()).select_from(GroupingDecision))
    assert n_decisions == 3


async def test_merge_moves_notes_and_decisions_to_survivor(
    db_session: AsyncSession, make_alert, grouping_config, seed_principal
) -> None:
    """FR-GRP-05: a merge preserves the non-survivor's notes + grouping decisions."""
    from app.audit.export import build_case_audit_bundle
    from app.auth.deps import Principal
    from app.cases.service import add_note, get_case_detail
    from app.grouping.persistence import apply_grouping_for_alert
    from app.models.audit import AuditEvent
    from app.models.grouping import GroupingDecision

    author = await seed_principal(roles=("analyst",), email="merge-notes@example.com")
    actor = Principal(user_id=str(author.id), email=author.email, roles=["analyst"])

    # Two independent cases; a3 will deterministically match both and merge them.
    a1 = await make_alert(counterparty_ref="C", amount="500", minutes=0)
    c1, _ = await apply_grouping_for_alert(db_session, a1, grouping_config, "tms")
    a2 = await make_alert(customer_ref="CUST", account_ref="B", amount="700", minutes=1)
    c2, _ = await apply_grouping_for_alert(db_session, a2, grouping_config, "tms")
    assert c1.id != c2.id

    n1 = await add_note(db_session, c1.id, "note on c1, must survive a merge", actor)
    n2 = await add_note(db_session, c2.id, "note on c2, must survive a merge", actor)

    a3 = await make_alert(customer_ref="CUST", counterparty_ref="C", amount="900", minutes=2)
    survivor, _ = await apply_grouping_for_alert(db_session, a3, grouping_config, "tms")
    await db_session.commit()

    loser_id = c2.id if survivor.id == c1.id else c1.id
    reloaded_loser = (
        await db_session.execute(select(Case).where(Case.id == loser_id))
    ).scalar_one()
    assert reloaded_loser.status == "Merged"

    # Both notes now belong to (and are visible on) the survivor.
    detail = await get_case_detail(db_session, survivor.id)
    note_ids = {str(n.id) for n in detail.notes}
    assert {str(n1.id), str(n2.id)} <= note_ids

    bundle = await build_case_audit_bundle(db_session, survivor.id)
    assert {str(n1.id), str(n2.id)} <= {n["id"] for n in bundle["notes"]}

    # Every grouping decision points at the survivor; none is orphaned on the loser.
    decision_case_ids = set(
        (await db_session.execute(select(GroupingDecision.case_id))).scalars().all()
    )
    assert decision_case_ids == {survivor.id}

    # The per-loser merge audit event still fired.
    merged_events = (
        (
            await db_session.execute(
                select(AuditEvent).where(
                    AuditEvent.stream == f"case:{loser_id}",
                    AuditEvent.action == "case.merged",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(merged_events) == 1


async def test_closed_case_is_flagged_not_merged(
    db_session: AsyncSession, make_alert, grouping_config
) -> None:
    from app.grouping.persistence import apply_grouping_for_alert
    from app.models.audit import AuditEvent

    a1 = await make_alert(account_ref="A", counterparty_ref="C", amount="500")
    case1, _ = await apply_grouping_for_alert(db_session, a1, grouping_config, "tms")
    case1.status = "Closed"
    await db_session.flush()

    a2 = await make_alert(account_ref="A", counterparty_ref="C", amount="500", minutes=10)
    case2, decision = await apply_grouping_for_alert(db_session, a2, grouping_config, "tms")
    await db_session.commit()

    # A brand-new case for a2; the closed case is untouched aside from the flag.
    assert case2.id != case1.id
    assert case2.status == "Open"

    reloaded_closed = (
        await db_session.execute(select(Case).where(Case.id == case1.id))
    ).scalar_one()
    assert reloaded_closed.status == "Closed"

    flagged = (
        (
            await db_session.execute(
                select(AuditEvent).where(
                    AuditEvent.stream == f"case:{case1.id}",
                    AuditEvent.action == "case.review_flagged",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(flagged) == 1
    # The engine still groups a2 with a1 (deterministic match); persistence just
    # refuses to reuse the *closed* case and opens a fresh one instead.
    assert decision.method == "deterministic"
    assert decision.case_id == case2.id


async def test_weighted_risk_aggregation(
    db_session: AsyncSession, make_alert, grouping_config
) -> None:
    import dataclasses

    from app.grouping.persistence import apply_grouping_for_alert

    weighted_cfg = dataclasses.replace(grouping_config, risk_aggregation="weighted")

    a1 = await make_alert(account_ref="A", counterparty_ref="C", amount="500", risk_score=80)
    case, _ = await apply_grouping_for_alert(db_session, a1, weighted_cfg, "tms")
    a2 = await make_alert(
        account_ref="A", counterparty_ref="C", amount="500", minutes=5, risk_score=40
    )
    case, _ = await apply_grouping_for_alert(db_session, a2, weighted_cfg, "tms")
    a3 = await make_alert(
        account_ref="A", counterparty_ref="C", amount="500", minutes=8, risk_score=40
    )
    case, _ = await apply_grouping_for_alert(db_session, a3, weighted_cfg, "tms")
    await db_session.commit()

    # dominant 80 + 0.1 * ((80+40+40) - 80) = 80 + 8 = 88
    assert case.risk_score == 88
