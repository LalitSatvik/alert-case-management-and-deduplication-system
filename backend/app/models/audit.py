"""Audit-log domain models: an append-only, per-stream, hash-chained event log.

Two tables:

* ``audit_streams`` -- one row per logical stream (e.g. ``"case:<uuid>"``). Holds
  the tip of the chain: ``last_seq`` (monotonic per stream) and ``last_hash``
  (the hash of the most recent event). :func:`app.audit.service.record_audit`
  ``SELECT ... FOR UPDATE`` locks this row to serialise concurrent writers.
* ``audit_events`` -- the immutable events themselves. ``id`` is a Postgres
  ``bigserial`` surrogate key; ``(stream, seq)`` is unique and provides the
  lookup index for a stream's ordered history. ``prev_hash`` links each event to
  its predecessor (the first event's ``prev_hash`` is ``GENESIS_HASH``); ``hash``
  is ``sha256`` over the canonical JSON of the event's own fields plus
  ``prev_hash`` (see :func:`app.audit.service._event_hash`).

Events are never updated or deleted by the application -- ``created_at`` is a
legitimate wall-clock timestamp (this is the audit trail, not the grouping
engine's logical clock). Extra indexes on ``actor_id`` / ``action`` /
``created_at`` back the audit-query endpoint.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AuditStream(Base):
    """The tip of one hash chain: the last sequence number and hash for a stream."""

    __tablename__ = "audit_streams"

    stream: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    last_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditEvent(Base):
    """A single immutable audit record, chained to its predecessor by hash."""

    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("stream", "seq", name="uq_audit_events_stream_seq"),
        Index("ix_audit_events_actor_id", "actor_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    stream: Mapped[str] = mapped_column(String(255), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    before: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ["AuditEvent", "AuditStream", "Base"]
