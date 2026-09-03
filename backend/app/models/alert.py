"""Alert domain model: one row per inbound alert, stored post-normalisation.

Columns mirror :class:`app.schemas.alert.AlertIn` plus system-generated fields
(``id``, ``received_at``), the derived ``merchant_name_normalised``, an optional
``idempotency_key`` for de-duplicating retried submissions, and ``case_id`` (FK to
``cases.id``, nullable until the grouping engine assigns the alert to a case).

``rule_codes`` / ``typologies`` / ``raw_payload`` are ``JSONB``. Timestamps are
``TIMESTAMP WITH TIME ZONE`` per the project-wide UTC constraint. ``amount`` is
``NUMERIC(18, 4)`` to match the canonical schema's ``max_digits`` / ``decimal_places``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, TimestampMixin


class Alert(TimestampMixin, Base):
    """A single fraud/AML alert ingested from an upstream detection system."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("source_system", "external_alert_id", name="uq_alerts_source_external"),
        Index("ix_alerts_event_time", "event_time"),
        Index("ix_alerts_customer_ref_event_time", "customer_ref", "event_time"),
        Index("ix_alerts_device_id", "device_id"),
        Index("ix_alerts_ip_address", "ip_address"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)

    # --- source identity ---------------------------------------------------
    external_alert_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- timing (all tz-aware UTC) --------------------------------------------
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # --- transaction core --------------------------------------------------
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)

    # --- optional references / context -----------------------------------
    customer_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    counterparty_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_name_normalised: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mcc: Mapped[str | None] = mapped_column(String(8), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- detection metadata (JSONB) --------------------------------------
    rule_codes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    typologies: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    raw_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # --- evaluation / linkage -------------------------------------------
    ground_truth_group_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", name="fk_alerts_case_id_cases"), nullable=True
    )


__all__ = ["Alert", "Base"]
