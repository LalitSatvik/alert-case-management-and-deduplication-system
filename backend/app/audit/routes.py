"""``/api/v1`` audit endpoints: query the log, read a case's history, verify chains.

* ``GET  /api/v1/audit``               -- filtered, keyset-paginated global log (admin, readonly)
* ``GET  /api/v1/cases/{case_id}/audit`` -- one case stream ordered by seq (analyst, admin, readonly)
* ``POST /api/v1/audit:verify``        -- recompute + anchor every stream (admin only)

Verification is deliberately stronger than :func:`verify_stream` alone. That
function walks a caller-supplied event list and can only catch tampering *within*
the list -- it cannot notice that the whole chain was truncated and rebuilt. So
``:verify`` additionally anchors each stream against its ``audit_streams`` tip
row: the last event's ``hash`` must equal ``last_hash`` and the event count must
equal ``last_seq`` (seqs are 1-based, so N events <=> ``last_seq == N``).

It also catches *orphan* streams: ``app_user`` has unrestricted INSERT on
``audit_events``, so a forger could append events under a ``stream`` value that
has no ``audit_streams`` tip row at all. Anchor-only checking would never look at
them, so ``:verify`` separately scans ``SELECT DISTINCT stream FROM
audit_events`` and flags any stream with events but no tip row
(``reason="orphan_stream"``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.export import build_case_audit_bundle, render_html
from app.audit.service import GENESIS_HASH, record_audit, verify_stream
from app.auth.deps import Principal, get_current_principal, require_role
from app.cases.service import CaseNotFound
from app.db import get_session
from app.models.audit import AuditEvent, AuditStream
from app.schemas.audit import (
    AuditEventOut,
    AuditPage,
    BrokenStream,
    VerifyResult,
)

router = APIRouter(tags=["audit"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/audit",
    response_model=AuditPage,
    dependencies=[Depends(require_role("admin", "readonly"))],
)
async def query_audit(
    session: SessionDep,
    actor_id: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query(alias="to")] = None,
    cursor: Annotated[int | None, Query(description="last id from the previous page")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditPage:
    """Filtered, keyset-paginated view of the global audit log (newest first)."""
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit + 1)
    if actor_id is not None:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if action is not None:
        stmt = stmt.where(AuditEvent.action == action)
    if target_type is not None:
        stmt = stmt.where(AuditEvent.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(AuditEvent.target_id == target_id)
    if from_ is not None:
        stmt = stmt.where(AuditEvent.created_at >= from_)
    if to is not None:
        stmt = stmt.where(AuditEvent.created_at <= to)
    if cursor is not None:
        stmt = stmt.where(AuditEvent.id < cursor)

    rows = list((await session.execute(stmt)).scalars().all())
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = page[-1].id if has_more and page else None
    return AuditPage(
        items=[AuditEventOut.model_validate(row) for row in page],
        next_cursor=next_cursor,
    )


@router.get(
    "/cases/{case_id}/audit",
    response_model=list[AuditEventOut],
    dependencies=[Depends(require_role("analyst", "admin", "readonly"))],
)
async def case_audit(session: SessionDep, case_id: str) -> list[AuditEventOut]:
    """The ``case:{case_id}`` audit stream, ordered by ``seq``."""
    rows = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.stream == f"case:{case_id}")
                .order_by(AuditEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    return [AuditEventOut.model_validate(row) for row in rows]


@router.post(
    "/cases/{case_id}/audit:export",
    dependencies=[Depends(require_role("analyst", "admin", "readonly"))],
)
async def export_case_audit(
    session: SessionDep,
    case_id: UUID,
    actor: Annotated[Principal, Depends(get_current_principal)],
    format: Annotated[Literal["json", "html"], Query()] = "json",
) -> Response:
    """Export a case's full audit trail as a JSON bundle or a self-contained HTML doc.

    The bundle carries the case header, its linked alerts (with grouping
    rationale), every note, and the whole ``case:{case_id}`` hash-chained event
    stream plus a ``chain_verified`` flag. The export is *itself* audited: a
    ``case.audit_exported`` event is appended to the stream and committed before
    the response is returned (so it is not part of the bundle just built).
    """
    try:
        bundle = await build_case_audit_bundle(session, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found") from exc

    await record_audit(
        session,
        stream=f"case:{case_id}",
        actor=actor,
        action="case.audit_exported",
        target_type="case",
        target_id=str(case_id),
        after={"format": format},
    )
    await session.commit()

    if format == "json":
        return JSONResponse(content=bundle)
    return HTMLResponse(content=render_html(bundle))


@router.post(
    "/audit:verify",
    response_model=VerifyResult,
    dependencies=[Depends(require_role("admin"))],
)
async def verify_audit(session: SessionDep) -> VerifyResult:
    """Recompute + tip-anchor every audit stream; report the broken ones."""
    streams = list((await session.execute(select(AuditStream))).scalars().all())
    broken: list[BrokenStream] = []

    anchored = {row.stream for row in streams}

    for stream_row in streams:
        events = list(
            (
                await session.execute(
                    select(AuditEvent)
                    .where(AuditEvent.stream == stream_row.stream)
                    .order_by(AuditEvent.seq)
                )
            )
            .scalars()
            .all()
        )

        # A bare genesis tip (no events yet) is a legitimate clean state.
        if not events and stream_row.last_seq == 0 and stream_row.last_hash == GENESIS_HASH:
            continue

        broken_seqs = verify_stream(events)
        if broken_seqs:
            broken.append(BrokenStream(stream=stream_row.stream, seqs=broken_seqs, reason="chain"))
            continue

        if not events or events[-1].hash != stream_row.last_hash:
            broken.append(
                BrokenStream(
                    stream=stream_row.stream,
                    seqs=[stream_row.last_seq],
                    reason="tip_mismatch",
                )
            )
            continue

        if len(events) != stream_row.last_seq:
            broken.append(
                BrokenStream(
                    stream=stream_row.stream,
                    seqs=[e.seq for e in events],
                    reason="count_mismatch",
                )
            )

    # Orphan streams: events exist under a stream key with no audit_streams tip
    # row, so the anchored loop above never inspected them.
    event_streams = set(
        (await session.execute(select(AuditEvent.stream).distinct())).scalars().all()
    )
    orphans = sorted(event_streams - anchored)
    for orphan in orphans:
        seqs = list(
            (
                await session.execute(
                    select(AuditEvent.seq)
                    .where(AuditEvent.stream == orphan)
                    .order_by(AuditEvent.seq)
                )
            )
            .scalars()
            .all()
        )
        broken.append(BrokenStream(stream=orphan, seqs=seqs, reason="orphan_stream"))

    return VerifyResult(streams_checked=len(streams) + len(orphans), broken=broken)


__all__ = ["router"]
