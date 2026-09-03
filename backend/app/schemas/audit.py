"""Response bodies for the ``/api/v1/audit`` read + verify endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

BrokenReason = Literal["chain", "tip_mismatch", "count_mismatch", "orphan_stream"]


class AuditEventOut(BaseModel):
    """One audit event, as returned by the query and case-history endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stream: str
    seq: int
    prev_hash: str
    hash: str
    actor_id: str | None
    actor_role: str | None
    action: str
    target_type: str
    target_id: str
    reason: str | None
    before: dict[str, object] | None
    after: dict[str, object] | None
    correlation_id: str | None
    created_at: datetime


class AuditPage(BaseModel):
    """A keyset-paginated slice of the global audit log."""

    items: list[AuditEventOut]
    next_cursor: int | None = None


class BrokenStream(BaseModel):
    """A stream whose hash chain or tip anchor failed verification."""

    stream: str
    seqs: list[int]
    reason: BrokenReason


class VerifyResult(BaseModel):
    """Outcome of ``POST /api/v1/audit:verify`` over every stream."""

    streams_checked: int
    broken: list[BrokenStream]


__all__ = [
    "AuditEventOut",
    "AuditPage",
    "BrokenReason",
    "BrokenStream",
    "VerifyResult",
]
