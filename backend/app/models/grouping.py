"""Grouping-engine persistence model: one row per engine verdict for an alert.

:class:`GroupingDecision` is the durable, auditable record of *why* an alert was
attached to a case: the ``method`` (``deterministic`` / ``similarity`` /
``singleton``), the ``matched_rule_ids``, the ``similarity_score`` and the full
``feature_contributions`` breakdown, stamped with the ``engine_version`` and
``config_hash`` in force at the time. Written by
:func:`app.grouping.persistence.apply_grouping_for_alert`; referenced by the
:class:`~app.models.case.CaseAlertLink` it produced.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class GroupingDecision(Base):
    """An immutable record of one grouping-engine verdict for one alert."""

    __tablename__ = "grouping_decisions"
    __table_args__ = (Index("ix_grouping_decisions_alert_id", "alert_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alerts.id", name="fk_grouping_decisions_alert_id_alerts"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", name="fk_grouping_decisions_case_id_cases"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    matched_rule_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feature_contributions: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ["Base", "GroupingDecision"]
