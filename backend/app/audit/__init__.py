"""Append-only, hash-chained audit log.

:func:`app.audit.service.record_audit` is the single write path: callers pass it
their *own* :class:`~sqlalchemy.ext.asyncio.AsyncSession` and it appends one
sequenced, hash-linked event to a per-target stream without ever committing --
the audit write lives or dies with the business transaction that triggered it.
:func:`app.audit.service.verify_stream` re-derives the chain to detect tampering.
"""

from __future__ import annotations

from app.audit.service import GENESIS_HASH, record_audit, verify_stream

__all__ = ["GENESIS_HASH", "record_audit", "verify_stream"]
