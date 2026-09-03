"""The audit-log write path and verifier.

``record_audit`` appends one event to a per-stream hash chain:

1. ``INSERT ... ON CONFLICT DO NOTHING`` a genesis ``audit_streams`` row so the
   tip row always exists, then ``SELECT ... FOR UPDATE`` it. Two writers racing
   on the same stream serialise here: the second blocks on the first's row lock
   and only reads ``last_seq`` once the first has committed.
2. ``seq = last_seq + 1``; ``prev_hash`` is the stream's ``last_hash`` (or
   :data:`GENESIS_HASH` for the first event).
3. ``created_at`` is wall-clock UTC -- the audit trail legitimately records real
   time (it is not the grouping engine's logical clock).
4. ``hash = sha256(canonical_json(payload))`` where ``payload`` is the fixed
   list built by :func:`_event_hash` -- the *same* helper the verifier uses, so
   the two can never drift.
5. INSERT the ``AuditEvent`` and UPDATE the stream tip (``last_seq`` /
   ``last_hash``).

Everything runs on the **passed-in session**. ``record_audit`` never calls
``commit()`` -- the caller owns the transaction, so an audit write is atomic with
the change it describes. ``flush()`` is used to assign the event's ``id``.

``actor_role`` encoding: a comma-joined, sorted list of the principal's role
names (e.g. ``"admin,analyst"``), or ``None`` when there is no actor / no roles.
The full set is kept (rather than a single "primary" role) because a principal's
authority at the moment of the action is exactly ``set(roles)``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal
from app.metrics import audit_write_failures_total
from app.models.audit import AuditEvent, AuditStream

GENESIS_HASH = "0" * 64

__all__ = ["GENESIS_HASH", "record_audit", "verify_stream"]


def _canonical_json(obj: object) -> str:
    """Deterministic JSON: sorted keys, no whitespace, non-JSON values via ``str``."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _event_hash(
    *,
    stream: str,
    seq: int,
    actor_id: str | None,
    actor_role: str | None,
    action: str,
    target_type: str,
    target_id: str,
    reason: str | None,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
    created_at: datetime,
    prev_hash: str,
) -> str:
    """SHA-256 over the canonical JSON of an event's chained fields.

    Shared by :func:`record_audit` (at write time) and :func:`verify_stream` (at
    check time); the payload layout below is the single definition of "what an
    event's hash covers".
    """
    payload: list[object] = [
        stream,
        seq,
        actor_id,
        actor_role,
        action,
        target_type,
        target_id,
        reason,
        before,
        after,
        created_at.isoformat(),
        prev_hash,
    ]
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _current_correlation_id() -> str | None:
    """Best-effort correlation id from structlog's contextvars (None outside a request)."""
    cid = structlog.contextvars.get_contextvars().get("correlation_id")
    return str(cid) if cid is not None else None


async def record_audit(
    session: AsyncSession,
    *,
    stream: str,
    actor: Principal | None,
    action: str,
    target_type: str,
    target_id: str,
    reason: str | None = None,
    before: dict[str, object] | None = None,
    after: dict[str, object] | None = None,
) -> AuditEvent:
    """Append one hash-chained event to ``stream`` on the caller's session.

    Never commits. The returned :class:`AuditEvent` has been flushed (its ``id``
    is populated) but the enclosing transaction is still the caller's to commit
    or roll back. Any exception before the flush completes increments
    ``audit_write_failures_total`` (FR-OPS-02) and re-raises unchanged.
    """
    try:
        return await _append_event(
            session,
            stream=stream,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            before=before,
            after=after,
        )
    except Exception:
        audit_write_failures_total.inc()
        raise


async def _append_event(
    session: AsyncSession,
    *,
    stream: str,
    actor: Principal | None,
    action: str,
    target_type: str,
    target_id: str,
    reason: str | None,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> AuditEvent:
    # Ensure the stream tip row exists so the FOR UPDATE below has something to
    # lock even for a brand-new stream (a plain SELECT ... FOR UPDATE cannot lock
    # a row that does not exist yet, which would let two writers both pick seq 1).
    await session.execute(
        pg_insert(AuditStream)
        .values(stream=stream, last_seq=0, last_hash=GENESIS_HASH)
        .on_conflict_do_nothing(index_elements=["stream"])
    )

    stream_row = (
        await session.execute(
            select(AuditStream).where(AuditStream.stream == stream).with_for_update()
        )
    ).scalar_one()

    seq = stream_row.last_seq + 1
    prev_hash = stream_row.last_hash
    created_at = datetime.now(UTC)

    actor_id = actor.user_id if actor is not None else None
    actor_role = ",".join(sorted(actor.roles)) if actor is not None and actor.roles else None

    event_hash = _event_hash(
        stream=stream,
        seq=seq,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        before=before,
        after=after,
        created_at=created_at,
        prev_hash=prev_hash,
    )

    event = AuditEvent(
        stream=stream,
        seq=seq,
        prev_hash=prev_hash,
        hash=event_hash,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        before=before,
        after=after,
        correlation_id=_current_correlation_id(),
        created_at=created_at,
    )
    session.add(event)

    stream_row.last_seq = seq
    stream_row.last_hash = event_hash

    await session.flush()
    return event


def verify_stream(events: list[AuditEvent]) -> list[int]:
    """Re-derive the chain for ``events`` (assumed ordered by ``seq``).

    Returns the ``seq`` values where the chain is broken -- either the recomputed
    hash does not match the stored one (a hashed field was tampered with) or the
    stored ``prev_hash`` does not match the previous event's hash (an event was
    reordered, dropped, or its link edited). An empty list means the chain is
    intact.
    """
    broken: list[int] = []
    expected_prev = GENESIS_HASH
    for event in events:
        flagged = False
        if event.prev_hash != expected_prev:
            flagged = True
        recomputed = _event_hash(
            stream=event.stream,
            seq=event.seq,
            actor_id=event.actor_id,
            actor_role=event.actor_role,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            reason=event.reason,
            before=event.before,
            after=event.after,
            created_at=event.created_at,
            prev_hash=event.prev_hash,
        )
        if recomputed != event.hash:
            flagged = True
        if flagged:
            broken.append(event.seq)
        expected_prev = event.hash
    return broken
