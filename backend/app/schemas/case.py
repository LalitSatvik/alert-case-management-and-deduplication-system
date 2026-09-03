"""Request/response bodies for the ``/api/v1/cases`` endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.alert import AlertOut

__all__ = [
    "AssignRequest",
    "CaseDetailOut",
    "CaseListItem",
    "CaseListPage",
    "CaseOut",
    "CaseStatsOut",
    "NoteCreate",
    "NoteOut",
    "NoteRetract",
    "TimelineEntry",
    "TransitionRequest",
]


class TransitionRequest(BaseModel):
    """Body for ``POST /api/v1/cases/{case_id}/transition``.

    ``to`` is the target status; ``reason`` is required (route-enforced) only for
    a ``Closed`` -> ``In Progress`` re-open; ``disposition`` is required for a
    close and must be one of the configured dispositions.
    """

    to: str
    reason: str | None = None
    disposition: str | None = None


class CaseOut(BaseModel):
    """A ``cases`` row as returned by the case endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    human_ref: str
    status: str
    disposition: str | None
    assignee_id: UUID | None
    risk_score: int
    alert_count: int
    closed_at: datetime | None
    canonical_from_case_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class AssignRequest(BaseModel):
    """Body for ``POST /api/v1/cases/{case_id}/assign``.

    ``assignee_id`` is required but nullable: pass a user id to assign, or an
    explicit ``null`` to unassign. The user must exist and be active.
    """

    assignee_id: UUID | None


class NoteCreate(BaseModel):
    """Body for ``POST /api/v1/cases/{case_id}/notes`` -- a non-empty note body."""

    body: str = Field(min_length=1)


class NoteRetract(BaseModel):
    """Body for ``POST /api/v1/cases/{case_id}/notes/{note_id}/retract``."""

    reason: str = Field(min_length=1)


class NoteOut(BaseModel):
    """A ``notes`` row as returned by the note endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    author_id: UUID
    body: str
    retracted: bool
    retraction_reason: str | None
    created_at: datetime


class CaseListItem(BaseModel):
    """One row of ``GET /api/v1/cases`` -- a case header plus two joined fields.

    ``assignee_email`` is a LEFT JOIN onto ``users``; ``oldest_alert_event_time``
    is the case's earliest linked ``alert.event_time`` (``None`` when no alert is
    linked yet).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    human_ref: str
    status: str
    disposition: str | None
    assignee_email: str | None
    risk_score: int
    alert_count: int
    created_at: datetime
    updated_at: datetime
    oldest_alert_event_time: datetime | None


class CaseListPage(BaseModel):
    """A keyset-paginated slice of the case list."""

    items: list[CaseListItem]
    next_cursor: str | None = None


class CaseStatsOut(BaseModel):
    """Aggregate counts for ``GET /api/v1/cases/stats``.

    Every count honours the same filter query string as ``GET /cases`` so a
    summary strip stays consistent with the list it sits above. ``by_status`` maps
    each status present in the filtered set to its count; ``high_risk`` counts
    cases at or above ``high_risk_threshold``; ``avg_risk`` is rounded to one
    decimal and is ``0`` for an empty result.
    """

    total: int
    by_status: dict[str, int]
    unassigned: int
    high_risk: int
    high_risk_threshold: int
    avg_risk: float


class TimelineEntry(BaseModel):
    """One audit event on the ``case:{id}`` stream, projected for the detail view."""

    seq: int
    action: str
    actor_id: str | None
    actor_role: str | None
    reason: str | None
    created_at: datetime
    before: dict[str, Any] | None
    after: dict[str, Any] | None


class CaseDetailOut(CaseOut):
    """``GET /api/v1/cases/{case_id}`` -- the case header plus its collections.

    ``alerts`` are the linked alerts (oldest event first), each with its
    ``grouping`` rationale from the ``GroupingDecision`` that linked it. ``notes``
    are every note on the case (retracted included), oldest first. ``timeline`` is
    the case's audit stream, newest first.
    """

    alerts: list[AlertOut]
    notes: list[NoteOut]
    timeline: list[TimelineEntry]
