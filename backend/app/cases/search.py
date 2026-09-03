"""Case list: filter set, query builder, and keyset-paginated fetch.

``CaseFilters`` is the parsed query string; :func:`build_case_query` turns it into
a single ``Select`` over ``cases`` (all filters AND-ed, every predicate
parameterised); :func:`paginate` adds the sort and a keyset cursor and returns
:class:`~app.schemas.case.CaseListItem` rows plus the next cursor.

Design notes
------------
* **assignee** -- ``"unassigned"`` -> ``assignee_id IS NULL``; a UUID -> equality;
  ``None`` -> no filter.
* **source_system / typology** -- a correlated ``EXISTS`` over the case's linked
  alerts (``case_alert_links`` JOIN ``alerts``). ``typology`` uses the JSONB
  containment operator (``Alert.typologies.contains([value])`` -> ``@>``), which
  matches an element of the stored string array.
* **q** -- a UNION of case ids whose ``human_ref`` (``to_tsvector('simple', ...)``),
  linked alert ``external_alert_id`` / ``merchant_name_normalised`` /
  ``customer_ref`` / ``account_ref`` (FR-SRCH-02), or note ``body`` matches
  ``plainto_tsquery('simple', q)``; the outer query then filters
  ``Case.id IN (<that UNION>)``. GIN indexes in the ``case_fts`` and
  ``case_fts_refs`` migrations back these ``to_tsvector`` expressions verbatim.
  The text-search config is passed as a SQL literal (``'simple'``), not a bind
  parameter, so Postgres resolves the two-argument (``regconfig``) form.
* **oldest_alert** -- the case's earliest linked ``alert.event_time``, as a
  correlated scalar subquery (also the ``oldest_alert`` sort key). NULLs (a case
  with no alerts) sort last.
* **keyset cursor** -- base64(JSON) of ``{"v": <sort value>, "id": <last id>}``.
  For the two descending sorts the next page is ``(col, id) < (v, id)``; for the
  ascending ``oldest_alert`` sort it is ``(col, id) > (v, id)`` with NULLs kept
  last. ``next_cursor`` is returned only when a full page was produced.
"""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import CompoundSelect, Row, Select, and_, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.alert import Alert
from app.models.case import Case, CaseAlertLink, Note
from app.models.user import User
from app.schemas.case import CaseListItem, CaseStatsOut

__all__ = ["CaseFilters", "InvalidCursor", "build_case_query", "case_stats", "paginate"]

MAX_LIMIT = 200
DEFAULT_LIMIT = 50

# A case is "high risk" for the summary strip at or above this score.
HIGH_RISK_THRESHOLD = 90

Sort = Literal["-risk_score", "-created_at", "oldest_alert"]
AssigneeFilter = uuid.UUID | Literal["unassigned"] | None

# The text-search config as a SQL literal -- a bound parameter would be typed
# ``text`` and Postgres has no ``to_tsvector(text, text)`` / implicit
# ``text -> regconfig`` cast, so it must be inlined.
_SIMPLE: ColumnElement[str] = literal_column("'simple'")


class InvalidCursor(Exception):
    """The ``cursor`` query parameter is not a cursor this endpoint issued."""


@dataclass
class CaseFilters:
    """Parsed, validated ``GET /cases`` query string."""

    status: list[str] = field(default_factory=list)
    disposition: list[str] = field(default_factory=list)
    assignee_id: AssigneeFilter = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    closed_from: datetime | None = None
    closed_to: datetime | None = None
    risk_min: int | None = None
    risk_max: int | None = None
    source_system: str | None = None
    typology: str | None = None
    q: str | None = None
    sort: Sort = "-risk_score"
    limit: int = DEFAULT_LIMIT
    cursor: str | None = None


# --- shared SQL fragments -------------------------------------------------


def _tsvector(expr: Any) -> ColumnElement[Any]:
    return func.to_tsvector(_SIMPLE, expr)


def _tsquery(q: str) -> ColumnElement[Any]:
    return func.plainto_tsquery(_SIMPLE, q)


def _alert_exists(predicate: ColumnElement[bool]) -> ColumnElement[bool]:
    """``EXISTS`` over the outer case's linked alerts matching ``predicate``."""
    return (
        select(literal_column("1"))
        .select_from(CaseAlertLink)
        .join(Alert, Alert.id == CaseAlertLink.alert_id)
        .where(CaseAlertLink.case_id == Case.id, predicate)
        .exists()
    )


def _oldest_alert_expr() -> ColumnElement[Any]:
    """Correlated scalar subquery: the case's earliest linked ``alert.event_time``."""
    return (
        select(func.min(Alert.event_time))
        .select_from(CaseAlertLink)
        .join(Alert, Alert.id == CaseAlertLink.alert_id)
        .where(CaseAlertLink.case_id == Case.id)
        .correlate(Case)
        .scalar_subquery()
    )


def _fts_case_ids(q: str) -> CompoundSelect[Any]:
    """UNION of case ids matching ``q`` across human_ref / alert fields / note body."""
    tsq = _tsquery(q)
    from_cases = select(Case.id).where(_tsvector(Case.human_ref).bool_op("@@")(tsq))
    from_alerts = (
        select(CaseAlertLink.case_id)
        .join(Alert, Alert.id == CaseAlertLink.alert_id)
        .where(
            or_(
                _tsvector(func.coalesce(Alert.external_alert_id, "")).bool_op("@@")(tsq),
                _tsvector(func.coalesce(Alert.merchant_name_normalised, "")).bool_op("@@")(tsq),
                _tsvector(func.coalesce(Alert.customer_ref, "")).bool_op("@@")(tsq),
                _tsvector(func.coalesce(Alert.account_ref, "")).bool_op("@@")(tsq),
            )
        )
    )
    from_notes = select(Note.case_id).where(_tsvector(Note.body).bool_op("@@")(tsq))
    return from_cases.union(from_alerts, from_notes)


def _conditions(f: CaseFilters) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = []
    if f.status:
        conds.append(Case.status.in_(f.status))
    if f.disposition:
        conds.append(Case.disposition.in_(f.disposition))
    if f.assignee_id == "unassigned":
        conds.append(Case.assignee_id.is_(None))
    elif isinstance(f.assignee_id, uuid.UUID):
        conds.append(Case.assignee_id == f.assignee_id)
    if f.created_from is not None:
        conds.append(Case.created_at >= f.created_from)
    if f.created_to is not None:
        conds.append(Case.created_at <= f.created_to)
    if f.closed_from is not None:
        conds.append(Case.closed_at >= f.closed_from)
    if f.closed_to is not None:
        conds.append(Case.closed_at <= f.closed_to)
    if f.risk_min is not None:
        conds.append(Case.risk_score >= f.risk_min)
    if f.risk_max is not None:
        conds.append(Case.risk_score <= f.risk_max)
    if f.source_system is not None:
        conds.append(_alert_exists(Alert.source_system == f.source_system))
    if f.typology is not None:
        conds.append(_alert_exists(Alert.typologies.contains([f.typology])))
    if f.q is not None and f.q.strip():
        conds.append(Case.id.in_(_fts_case_ids(f.q)))
    return conds


# --- query builder + pagination ---------------------------------------


def build_case_query(filters: CaseFilters) -> Select[Any]:
    """A ``Select`` of the columns a :class:`CaseListItem` needs, all filters AND-ed."""
    stmt = (
        select(
            Case.id,
            Case.human_ref,
            Case.status,
            Case.disposition,
            Case.assignee_id,
            Case.risk_score,
            Case.alert_count,
            Case.created_at,
            Case.updated_at,
            User.email.label("assignee_email"),
            _oldest_alert_expr().label("oldest_alert_event_time"),
        )
        .select_from(Case)
        .outerjoin(User, User.id == Case.assignee_id)
    )
    conds = _conditions(filters)
    if conds:
        stmt = stmt.where(*conds)
    return stmt


def _order_by(sort: Sort) -> list[ColumnElement[Any]]:
    if sort == "-created_at":
        return [Case.created_at.desc(), Case.id.desc()]
    if sort == "oldest_alert":
        return [_oldest_alert_expr().asc(), Case.id.asc()]
    return [Case.risk_score.desc(), Case.id.desc()]


def _keyset(sort: Sort, value: Any, last_id: uuid.UUID) -> ColumnElement[bool]:
    if sort == "-created_at":
        return or_(
            Case.created_at < value,
            and_(Case.created_at == value, Case.id < last_id),
        )
    if sort == "oldest_alert":
        expr = _oldest_alert_expr()
        if value is None:
            return and_(expr.is_(None), Case.id > last_id)
        return or_(expr > value, expr.is_(None), and_(expr == value, Case.id > last_id))
    return or_(
        Case.risk_score < value,
        and_(Case.risk_score == value, Case.id < last_id),
    )


def _encode_cursor(sort: Sort, row: Row[Any]) -> str:
    if sort == "-created_at":
        value: Any = row.created_at.isoformat()
    elif sort == "oldest_alert":
        oldest = row.oldest_alert_event_time
        value = oldest.isoformat() if oldest is not None else None
    else:
        value = row.risk_score
    payload = json.dumps({"v": value, "id": str(row.id)})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def _decode_cursor(sort: Sort, cursor: str) -> tuple[Any, uuid.UUID]:
    """Decode a keyset cursor, or raise :class:`InvalidCursor`.

    ANY failure -- bad base64/JSON, missing ``id``/``v``, or a ``v`` whose type
    does not match the active ``sort`` -- is a clean :class:`InvalidCursor` (400),
    so a stale cursor reused after the sort control changes never 500s. ``v`` must
    be a non-bool int for ``-risk_score``; a parseable ISO datetime string for
    ``-created_at``; and either of those or ``None`` (the no-linked-alert tail
    sentinel) for ``oldest_alert``.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        last_id = uuid.UUID(str(payload["id"]))
        raw = payload["v"]
        if sort == "-risk_score":
            if not isinstance(raw, int) or isinstance(raw, bool):
                raise ValueError("risk_score cursor must be an int")
            value: Any = raw
        elif sort == "-created_at":
            if not isinstance(raw, str):
                raise ValueError("created_at cursor must be an ISO datetime string")
            value = datetime.fromisoformat(raw)
        else:  # "oldest_alert"
            if raw is not None and not isinstance(raw, str):
                raise ValueError("oldest_alert cursor must be an ISO string or null")
            value = None if raw is None else datetime.fromisoformat(raw)
    except (
        ValueError,
        KeyError,
        TypeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise InvalidCursor(cursor) from exc
    return value, last_id


async def case_stats(session: AsyncSession, filters: CaseFilters) -> CaseStatsOut:
    """Aggregate counts over the same filtered set as :func:`paginate`.

    Sort / limit / cursor on ``filters`` are ignored -- only the predicates from
    :func:`_conditions` apply, so the numbers describe the whole filtered result,
    not one page of it.
    """
    conds = _conditions(filters)

    agg_stmt = select(
        func.count().label("total"),
        func.count().filter(Case.assignee_id.is_(None)).label("unassigned"),
        func.count().filter(Case.risk_score >= HIGH_RISK_THRESHOLD).label("high_risk"),
        func.coalesce(func.avg(Case.risk_score), 0).label("avg_risk"),
    ).select_from(Case)
    if conds:
        agg_stmt = agg_stmt.where(*conds)
    agg = (await session.execute(agg_stmt)).one()

    status_stmt = select(Case.status, func.count()).select_from(Case)
    if conds:
        status_stmt = status_stmt.where(*conds)
    status_stmt = status_stmt.group_by(Case.status)
    by_status = {status: count for status, count in (await session.execute(status_stmt)).all()}

    return CaseStatsOut(
        total=agg.total,
        by_status=by_status,
        unassigned=agg.unassigned,
        high_risk=agg.high_risk,
        high_risk_threshold=HIGH_RISK_THRESHOLD,
        avg_risk=round(float(agg.avg_risk), 1),
    )


async def paginate(
    session: AsyncSession, filters: CaseFilters
) -> tuple[list[CaseListItem], str | None]:
    """Run the filtered query with sort + keyset cursor; return ``(items, next_cursor)``."""
    limit = max(1, min(filters.limit, MAX_LIMIT))
    stmt = build_case_query(filters).order_by(*_order_by(filters.sort))
    if filters.cursor is not None:
        value, last_id = _decode_cursor(filters.sort, filters.cursor)
        stmt = stmt.where(_keyset(filters.sort, value, last_id))

    rows = list((await session.execute(stmt.limit(limit + 1))).all())
    has_more = len(rows) > limit
    page = rows[:limit]

    items = [
        CaseListItem(
            id=row.id,
            human_ref=row.human_ref,
            status=row.status,
            disposition=row.disposition,
            assignee_email=row.assignee_email,
            risk_score=row.risk_score,
            alert_count=row.alert_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
            oldest_alert_event_time=row.oldest_alert_event_time,
        )
        for row in page
    ]
    next_cursor = _encode_cursor(filters.sort, page[-1]) if has_more and page else None
    return items, next_cursor
