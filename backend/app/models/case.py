"""Case domain models: the canonical investigation case and its alert links.

* :class:`Case` -- one canonical case. ``human_ref`` (``CASE-<base36>``) is the
  analyst-facing id; ``status`` moves through ``Open`` -> ``Closed`` and a
  non-survivor of a merge becomes ``Merged`` with ``canonical_from_case_id``
  pointing at the survivor. ``risk_score`` / ``alert_count`` are denormalised
  aggregates recomputed by :func:`app.grouping.persistence.apply_grouping_for_alert`.
* :class:`CaseAlertLink` -- the many-to-one link from an alert to its case
  (``alert_id`` is unique: an alert belongs to exactly one case), carrying the
  :class:`~app.models.grouping.GroupingDecision` that produced the link.

``human_ref`` values are drawn from the Postgres sequence ``case_human_ref_seq``
(created by the ``cases`` migration), not a column default.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, TimestampMixin


class Case(TimestampMixin, Base):
    """A canonical investigation case grouping one or more related alerts."""

    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_status", "status"),
        Index("ix_cases_assignee_id", "assignee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    human_ref: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Open", server_default=text("'Open'")
    )
    disposition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", name="fk_cases_assignee_id_users"), nullable=True
    )
    risk_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    alert_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canonical_from_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", name="fk_cases_canonical_from_case_id_cases"), nullable=True
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class CaseAlertLink(Base):
    """Links one alert to exactly one case, with the decision that made the link."""

    __tablename__ = "case_alert_links"
    __table_args__ = (Index("ix_case_alert_links_case_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", name="fk_case_alert_links_case_id_cases"), nullable=False
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alerts.id", name="fk_case_alert_links_alert_id_alerts"),
        nullable=False,
        unique=True,
    )
    grouping_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "grouping_decisions.id",
            name="fk_case_alert_links_grouping_decision_id_grouping_decisions",
        ),
        nullable=False,
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    linked_by: Mapped[str] = mapped_column(String(255), nullable=False)


class Note(Base):
    """An append-only investigation note attached to a case.

    A note is immutable once written. The **only** permitted mutation anywhere in
    the application is :func:`app.cases.service.retract_note` flipping
    ``retracted`` / ``retraction_reason`` -- there is no update or delete path,
    and no PATCH/PUT/DELETE route. The full ``body`` lives here; the audit log
    only ever records a 120-character excerpt.
    """

    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_case_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", name="fk_notes_case_id_cases"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="fk_notes_author_id_users"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    retracted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    retraction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["Base", "Case", "CaseAlertLink", "Note"]
