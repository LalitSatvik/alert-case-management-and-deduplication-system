"""Persist a grouping verdict: create / attach / merge canonical cases.

:func:`apply_grouping_for_alert` is the DB-facing bridge over the pure
:func:`app.grouping.engine.group`. For one freshly-persisted alert it:

1. loads a bounded set of already-cased candidate alerts that share a blocking
   key and fall inside the widest rule time window;
2. runs the pure engine over ``[new] + candidates`` and reads the new alert's
   connected component;
3. resolves the component to existing cases and decides:

   * **closed case(s) matched** -- never merged; a ``case.review_flagged`` audit
     is written on each and they drop out of the create/attach decision;
   * **0 open cases** -- create a fresh ``Case`` (``human_ref`` from the
     ``case_human_ref_seq`` sequence);
   * **1 open case** -- attach to it;
   * **>=2 open cases** -- pick the survivor (earliest ``created_at``, then lowest
     id), reassign the others' alerts + links to it, mark them ``Merged`` with
     ``canonical_from_case_id``, and write a ``case.merged`` audit on each.

4. writes the :class:`~app.models.grouping.GroupingDecision` and the
   :class:`~app.models.case.CaseAlertLink`, recomputes the case's ``risk_score``
   (per ``config.risk_aggregation``) and ``alert_count``, bumps ``version`` on an
   existing (mutated) case, and writes a ``case.alert_linked`` audit.

Never commits -- the caller owns the transaction so the alert, the decision, the
link and every audit event land atomically. ``datetime.now`` is used only for
``linked_at`` / ``created_at`` wall-clock stamps, never for anything the engine
hashes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit
from app.grouping import ENGINE_VERSION, GroupingConfig
from app.grouping.blocking import EngineAlert
from app.grouping.config import config_hash
from app.grouping.engine import Decision
from app.grouping.engine import group as engine_group
from app.metrics import grouping_decisions_total, grouping_duration_seconds
from app.models.alert import Alert
from app.models.case import Case, CaseAlertLink, Note
from app.models.grouping import GroupingDecision

__all__ = ["apply_grouping_for_alert"]

_BLOCKING_FIELDS = (
    "customer_ref",
    "account_ref",
    "counterparty_ref",
    "device_id",
    "ip_address",
    "session_id",
    "merchant_name_normalised",
)

_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _base36(n: int) -> str:
    """Render a non-negative int in base 36 (``0`` -> ``"0"``, ``36`` -> ``"10"``)."""
    if n == 0:
        return "0"
    out: list[str] = []
    while n:
        n, r = divmod(n, 36)
        out.append(_B36[r])
    return "".join(reversed(out))


def _engine_alert(a: Alert) -> EngineAlert:
    return EngineAlert(
        id=str(a.id),
        event_time=a.event_time,
        amount=a.amount,
        currency=a.currency,
        customer_ref=a.customer_ref,
        account_ref=a.account_ref,
        counterparty_ref=a.counterparty_ref,
        merchant_name_normalised=a.merchant_name_normalised,
        mcc=a.mcc,
        device_id=a.device_id,
        ip_address=a.ip_address,
        session_id=a.session_id,
        typologies=frozenset(a.typologies or []),
    )


def _aggregate_risk(scores: list[int], mode: str) -> int:
    if not scores:
        return 0
    dominant = max(scores)
    total = sum(scores)
    if mode == "sum_capped":
        return min(100, total)
    if mode == "weighted":
        # Dominant alert plus a 10% contribution from every other alert.
        return min(100, round(dominant + 0.1 * (total - dominant)))
    return dominant  # "max"


def _candidate_query(alert: Alert, config: GroupingConfig) -> Select[tuple[Alert]] | None:
    """Bounded already-cased candidates sharing a blocking key within the widest window."""
    key_filters = [
        getattr(Alert, name) == getattr(alert, name)
        for name in _BLOCKING_FIELDS
        if getattr(alert, name) is not None
    ]
    if not key_filters:
        return None

    windows = [r.time_window_seconds for r in config.rules if r.enabled]
    span = timedelta(seconds=max(windows) if windows else 0)
    return (
        select(Alert)
        .where(
            Alert.case_id.is_not(None),
            Alert.id != alert.id,
            Alert.event_time >= alert.event_time - span,
            Alert.event_time <= alert.event_time + span,
            or_(*key_filters),
        )
        .order_by(Alert.event_time.desc())
        .limit(config.candidate_cap)
    )


async def _create_case(session: AsyncSession, alert: Alert) -> Case:
    seq = int((await session.execute(select(func.nextval("case_human_ref_seq")))).scalar_one())
    case = Case(
        human_ref=f"CASE-{_base36(seq)}",
        status="Open",
        risk_score=alert.risk_score or 0,
        alert_count=0,
    )
    session.add(case)
    await session.flush()
    return case


async def apply_grouping_for_alert(
    session: AsyncSession,
    alert: Alert,
    config: GroupingConfig,
    actor_label: str,
) -> tuple[Case, GroupingDecision]:
    """Group ``alert`` into a canonical case. Returns ``(case, grouping_decision)``."""
    with grouping_duration_seconds.time():
        return await _apply_grouping_for_alert(session, alert, config, actor_label)


async def _apply_grouping_for_alert(
    session: AsyncSession,
    alert: Alert,
    config: GroupingConfig,
    actor_label: str,
) -> tuple[Case, GroupingDecision]:
    now = datetime.now(UTC)

    stmt = _candidate_query(alert, config)
    candidates: list[Alert] = (
        [] if stmt is None else list((await session.execute(stmt)).scalars().all())
    )

    engine_alerts = [_engine_alert(alert), *(_engine_alert(c) for c in candidates)]
    by_alert: dict[str, Decision] = {d.alert_id: d for d in engine_group(engine_alerts, config)}
    dec = by_alert[str(alert.id)]
    grouping_decisions_total.labels(method=dec.method).inc()

    matched_case_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for cand in candidates:
        if cand.case_id is None or cand.case_id in seen:
            continue
        if by_alert[str(cand.id)].group_key == dec.group_key:
            seen.add(cand.case_id)
            matched_case_ids.append(cand.case_id)

    cases: list[Case] = []
    if matched_case_ids:
        cases = list(
            (await session.execute(select(Case).where(Case.id.in_(matched_case_ids))))
            .scalars()
            .all()
        )

    for closed in (c for c in cases if c.status == "Closed"):
        await record_audit(
            session,
            stream=f"case:{closed.id}",
            actor=None,
            action="case.review_flagged",
            target_type="case",
            target_id=str(closed.id),
            reason=f"new alert {alert.id} matched a closed case",
        )

    open_cases = [c for c in cases if c.status not in ("Merged", "Closed")]

    created_new = False
    if not open_cases:
        target = await _create_case(session, alert)
        created_new = True
    elif len(open_cases) == 1:
        target = open_cases[0]
    else:
        survivor = min(open_cases, key=lambda c: (c.created_at, str(c.id)))
        for loser in open_cases:
            if loser.id == survivor.id:
                continue
            old_status = loser.status
            # FR-GRP-05: a merge preserves *all* of the non-survivor's history --
            # its alerts, alert links, notes and grouping decisions all move to
            # the survivor, in this same transaction (no commit here).
            await session.execute(
                update(Alert).where(Alert.case_id == loser.id).values(case_id=survivor.id)
            )
            await session.execute(
                update(CaseAlertLink)
                .where(CaseAlertLink.case_id == loser.id)
                .values(case_id=survivor.id)
            )
            await session.execute(
                update(Note).where(Note.case_id == loser.id).values(case_id=survivor.id)
            )
            await session.execute(
                update(GroupingDecision)
                .where(GroupingDecision.case_id == loser.id)
                .values(case_id=survivor.id)
            )
            loser.status = "Merged"
            loser.canonical_from_case_id = survivor.id
            merge_before: dict[str, object] = {"status": old_status}
            merge_after: dict[str, object] = {
                "status": "Merged",
                "canonical_from_case_id": str(survivor.id),
            }
            await record_audit(
                session,
                stream=f"case:{loser.id}",
                actor=None,
                action="case.merged",
                target_type="case",
                target_id=str(loser.id),
                before=merge_before,
                after=merge_after,
            )
        target = survivor

    alert.case_id = target.id
    grouping_decision = GroupingDecision(
        alert_id=alert.id,
        case_id=target.id,
        method=dec.method,
        matched_rule_ids=list(dec.matched_rule_ids),
        similarity_score=dec.similarity_score,
        feature_contributions=dict(dec.contributions),
        engine_version=ENGINE_VERSION,
        config_hash=config_hash(config),
        created_at=now,
    )
    session.add(grouping_decision)
    await session.flush()

    session.add(
        CaseAlertLink(
            case_id=target.id,
            alert_id=alert.id,
            grouping_decision_id=grouping_decision.id,
            linked_at=now,
            linked_by=actor_label,
        )
    )
    await session.flush()

    member_scores = [
        (s or 0)
        for s in (await session.execute(select(Alert.risk_score).where(Alert.case_id == target.id)))
        .scalars()
        .all()
    ]
    target.risk_score = _aggregate_risk(member_scores, config.risk_aggregation)
    target.alert_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CaseAlertLink)
                .where(CaseAlertLink.case_id == target.id)
            )
        ).scalar_one()
    )
    if not created_new:
        target.version += 1

    linked_after: dict[str, object] = {"alert_id": str(alert.id), "method": dec.method}
    await record_audit(
        session,
        stream=f"case:{target.id}",
        actor=None,
        action="case.alert_linked",
        target_type="case",
        target_id=str(target.id),
        after=linked_after,
    )

    await session.flush()
    return target, grouping_decision
