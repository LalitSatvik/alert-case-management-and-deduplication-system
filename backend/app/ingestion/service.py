"""Persist one normalised alert, atomically with its audit event.

``ingest_one`` is the single write path behind ``POST /api/v1/alerts``.
``persist_alert_only`` is the bulk write path behind ``POST /api/v1/alerts:batch``
-- same insert + audit, but grouping is deferred to the ARQ worker. Both share
``_insert_alert_or_existing`` (build + SAVEPOINT-wrapped INSERT + per-item dedup).

``ingest_one``:

1. normalises the validated :class:`AlertIn` (:func:`app.ingestion.normalize.normalize_alert`),
2. INSERTs the :class:`~app.models.alert.Alert` (carrying the idempotency key),
3. writes the ``alert.ingested`` audit event on stream ``alert:{id}``,
4. ``commit``s -- the INSERT and the audit event share one transaction, so a
   failure in the audit write rolls the alert back too.

If the INSERT trips ``uq_alerts_source_external`` (same
``source_system`` + ``external_alert_id`` already ingested), the failed INSERT is
rolled back to its SAVEPOINT (leaving the rest of the transaction intact), the
existing row is loaded, and it is returned with ``created=False`` so the route can
answer ``200`` instead of ``201``. This is the DB-layer half of idempotency; the
Redis-key half lives in :mod:`app.ingestion.idempotency`.

On a fresh create, :func:`app.grouping.persistence.apply_grouping_for_alert` runs
inside the same transaction (before the ``alert.ingested`` audit): it assigns the
alert to a canonical :class:`~app.models.case.Case` and records a
:class:`~app.models.grouping.GroupingDecision`, so the alert, its case link, the
grouping decision and every audit event commit atomically.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit
from app.auth.deps import Principal
from app.grouping.config import get_grouping_config
from app.grouping.persistence import apply_grouping_for_alert
from app.ingestion.normalize import normalize_alert
from app.metrics import alerts_ingested_total
from app.models.alert import Alert
from app.models.grouping import GroupingDecision
from app.schemas.alert import AlertIn, AlertOut, GroupingInfo

__all__ = ["ingest_one", "persist_alert_only"]


def _ingest_actor(api_key_id: uuid.UUID | None, actor_label: str) -> Principal | None:
    """Synthetic principal for an ingestion audit event.

    The authenticated ``ApiKey.id`` becomes ``actor_id`` so
    ``GET /api/v1/audit?actor_id=<api_key_id>`` finds every alert that key
    ingested. Chosen over a dedicated ``actor_label`` column because it reuses the
    existing ``actor_id`` filter and index with no schema change; the human label
    is still carried in ``reason`` (``api_key:<label>``) and in ``CaseAlertLink.linked_by``.
    Roles are empty -- an ingest key is not a user and holds none.
    """
    if api_key_id is None:
        return None
    return Principal(user_id=str(api_key_id), email=f"api_key:{actor_label}", roles=[])


def _to_alert_out(alert: Alert) -> AlertOut:
    """Build the response model from a persisted row (``grouping`` set by the caller)."""
    return AlertOut.model_validate(alert, from_attributes=True)


def _grouping_info(decision: GroupingDecision) -> GroupingInfo:
    """Project a persisted :class:`GroupingDecision` into the API's ``GroupingInfo``."""
    return GroupingInfo(
        method=decision.method,
        matched_rule_ids=list(decision.matched_rule_ids),
        similarity_score=decision.similarity_score,
        feature_contributions=dict(decision.feature_contributions),
        engine_version=decision.engine_version,
        config_hash=decision.config_hash,
    )


def _audit_after(alert: Alert) -> dict[str, object]:
    """JSON-only snapshot of the ingested alert for the audit event's ``after``."""
    return {
        "id": str(alert.id),
        "external_alert_id": alert.external_alert_id,
        "source_system": alert.source_system,
        "event_time": alert.event_time.isoformat(),
        "received_at": alert.received_at.isoformat(),
        "amount": str(alert.amount),
        "currency": alert.currency,
        "direction": alert.direction,
        "case_id": str(alert.case_id) if alert.case_id is not None else None,
    }


async def _insert_alert_or_existing(
    session: AsyncSession,
    payload: AlertIn,
    *,
    idem_key: str,
) -> tuple[Alert, bool]:
    """Build + INSERT the alert, or return the row that already owns its identity.

    The ``session.add`` + INSERT ``flush()`` run inside a SAVEPOINT
    (``session.begin_nested``): a ``uq_alerts_source_external`` collision rolls
    back *only* that savepoint -- never the enclosing transaction -- so a
    duplicate in a bulk batch does not poison the rows around it. On a collision
    the existing alert is SELECTed and returned with ``created=False``.

    The ``add`` must happen *inside* the ``begin_nested`` block: an object made
    pending before the savepoint belongs to the outer snapshot, and a flush
    failure would then deactivate the outer transaction instead of just the
    savepoint.

    Never commits. Shared by :func:`ingest_one` and :func:`persist_alert_only`.
    """
    normalized = normalize_alert(payload)
    alert = Alert(
        external_alert_id=normalized.external_alert_id,
        source_system=normalized.source_system,
        idempotency_key=idem_key,
        event_time=normalized.event_time,
        amount=normalized.amount,
        currency=normalized.currency,
        direction=normalized.direction,
        customer_ref=normalized.customer_ref,
        account_ref=normalized.account_ref,
        counterparty_ref=normalized.counterparty_ref,
        merchant_name=normalized.merchant_name,
        merchant_name_normalised=normalized.merchant_name_normalised,
        mcc=normalized.mcc,
        device_id=normalized.device_id,
        session_id=normalized.session_id,
        ip_address=normalized.ip_address,
        risk_score=normalized.risk_score,
        rule_codes=normalized.rule_codes,
        typologies=normalized.typologies,
        raw_payload=normalized.raw_payload,
        ground_truth_group_id=normalized.ground_truth_group_id,
    )
    try:
        async with session.begin_nested():
            session.add(alert)
            await session.flush()
    except IntegrityError:
        # The SAVEPOINT rollback already detached the doomed instance (a later
        # flush won't retry it); expunge defensively if it somehow lingers.
        if alert in session:
            session.expunge(alert)
        existing = (
            await session.execute(
                select(Alert).where(
                    Alert.source_system == normalized.source_system,
                    Alert.external_alert_id == normalized.external_alert_id,
                )
            )
        ).scalar_one()
        return existing, False

    await session.refresh(alert)
    return alert, True


async def ingest_one(
    session: AsyncSession,
    payload: AlertIn,
    *,
    idem_key: str,
    actor_label: str,
    api_key_id: uuid.UUID | None = None,
) -> tuple[AlertOut, bool]:
    """Persist ``payload`` and its audit event atomically. Returns ``(result, created)``.

    ``created`` is ``False`` when an alert with the same
    ``(source_system, external_alert_id)`` already existed.
    """
    alert, created = await _insert_alert_or_existing(session, payload, idem_key=idem_key)
    if not created:
        alerts_ingested_total.labels(result="duplicate").inc()
        return _to_alert_out(alert), False

    _case, decision = await apply_grouping_for_alert(
        session, alert, get_grouping_config(), actor_label
    )

    await record_audit(
        session,
        stream=f"alert:{alert.id}",
        actor=_ingest_actor(api_key_id, actor_label),
        action="alert.ingested",
        target_type="alert",
        target_id=str(alert.id),
        reason=f"api_key:{actor_label}",
        after=_audit_after(alert),
    )
    await session.commit()
    alerts_ingested_total.labels(result="created").inc()

    result = _to_alert_out(alert)
    result.case_id = _case.id
    result.grouping = _grouping_info(decision)
    return result, True


async def persist_alert_only(
    session: AsyncSession,
    payload: AlertIn,
    *,
    idem_key: str,
    actor_label: str,
    api_key_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, bool]:
    """Persist ``payload`` + its ``alert.ingested`` audit event -- **no grouping**.

    The bulk write path: the batch route persists every valid item this way (one
    SAVEPOINT per item, so a duplicate does not poison the batch), commits once,
    then hands the new alert ids to the ARQ ``group_alerts_job`` which groups them
    asynchronously. Returns ``(alert_id, created)``; ``created`` is ``False`` when
    an alert with the same ``(source_system, external_alert_id)`` already existed
    (its id is still returned). Never commits -- the caller owns the transaction.
    """
    alert, created = await _insert_alert_or_existing(session, payload, idem_key=idem_key)
    if not created:
        alerts_ingested_total.labels(result="duplicate").inc()
        return alert.id, False

    await record_audit(
        session,
        stream=f"alert:{alert.id}",
        actor=_ingest_actor(api_key_id, actor_label),
        action="alert.ingested",
        target_type="alert",
        target_id=str(alert.id),
        reason=f"api_key:{actor_label}",
        after=_audit_after(alert),
    )
    alerts_ingested_total.labels(result="created").inc()
    return alert.id, True
