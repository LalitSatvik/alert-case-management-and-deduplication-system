"""Deterministic, pure normalisation of inbound alerts.

No I/O, no clock reads, no randomness: given the same :class:`AlertIn` the
returned :class:`NormalizedAlert` is byte-for-byte identical every call. The
ingestion endpoint calls :func:`normalize_alert` before persisting an
:class:`~app.models.alert.Alert`; :func:`amount_bucket` is consumed later by the
blocking / deduplication stage to build candidate keys.

Normalisation rules (all idempotent):

* ``event_time`` -> converted to UTC via :meth:`datetime.astimezone`.
* ``currency`` -> upper-cased (``AlertIn`` already enforces ``^[A-Z]{3}$``; the
  call is kept as a defensive, cost-free guard).
* ``amount`` -> quantised to 4 decimal places (``ROUND_HALF_EVEN``).
* ``merchant_name_normalised`` -> ``merchant_name`` lower-cased with every run of
  non-alphanumeric characters collapsed to a single space and the ends trimmed;
  ``None`` when ``merchant_name`` is ``None``.
* ``ip_address`` -> canonical string form (e.g. ``2001:db8::1``) or ``None``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.schemas.alert import AlertIn

__all__ = ["NormalizedAlert", "amount_bucket", "normalize_alert", "normalize_merchant_name"]

_AMOUNT_QUANTUM = Decimal("0.0001")
_MERCHANT_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class NormalizedAlert:
    """Immutable canonical form of an inbound alert, ready to persist.

    Every field is either a normalised value or a straight pass-through from the
    validated :class:`AlertIn`. Frozen so downstream stages cannot mutate it.
    """

    external_alert_id: str
    source_system: str
    event_time: datetime
    amount: Decimal
    currency: str
    direction: str
    customer_ref: str | None
    account_ref: str | None
    counterparty_ref: str | None
    merchant_name: str | None
    merchant_name_normalised: str | None
    mcc: str | None
    device_id: str | None
    session_id: str | None
    ip_address: str | None
    risk_score: int | None
    rule_codes: list[str]
    typologies: list[str]
    raw_payload: dict[str, Any]
    ground_truth_group_id: str | None


def normalize_merchant_name(name: str | None) -> str | None:
    """Lower-case, strip punctuation, collapse whitespace. ``None`` -> ``None``.

    ``"  Quick-Cash,  LLC "`` -> ``"quick cash llc"``. A name made up entirely of
    punctuation normalises to the empty string (not ``None``).
    """
    if name is None:
        return None
    return _MERCHANT_NON_ALNUM.sub(" ", name.lower()).strip()


def normalize_alert(payload: AlertIn) -> NormalizedAlert:
    """Produce the deterministic :class:`NormalizedAlert` for a validated payload.

    ``AlertIn.event_time`` is an :class:`~pydantic.AwareDatetime`, so a naive value
    is already rejected with a 422 at the API boundary. The guard below keeps
    :func:`normalize_alert` deterministic even if it is ever called with a
    hand-built payload: without a fixed offset ``astimezone`` would fall back to
    the host's local timezone (a hidden wall-clock read).
    """
    if payload.event_time.tzinfo is None or payload.event_time.utcoffset() is None:
        raise ValueError("event_time must be timezone-aware")
    return NormalizedAlert(
        external_alert_id=payload.external_alert_id,
        source_system=payload.source_system,
        event_time=payload.event_time.astimezone(UTC),
        amount=payload.amount.quantize(_AMOUNT_QUANTUM),
        currency=payload.currency.upper(),
        direction=payload.direction,
        customer_ref=payload.customer_ref,
        account_ref=payload.account_ref,
        counterparty_ref=payload.counterparty_ref,
        merchant_name=payload.merchant_name,
        merchant_name_normalised=normalize_merchant_name(payload.merchant_name),
        mcc=payload.mcc,
        device_id=payload.device_id,
        session_id=payload.session_id,
        ip_address=None if payload.ip_address is None else str(payload.ip_address),
        risk_score=payload.risk_score,
        rule_codes=list(payload.rule_codes),
        typologies=list(payload.typologies),
        raw_payload=dict(payload.raw_payload),
        ground_truth_group_id=payload.ground_truth_group_id,
    )


def amount_bucket(amount: Decimal) -> str:
    """Map an amount to a coarse magnitude bucket (lower-inclusive, upper-exclusive).

    ``Decimal("10")`` -> ``"10-100"``; ``Decimal("4980")`` -> ``"1000-10000"``.
    """
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if amount < 10:
        return "0-10"
    if amount < 100:
        return "10-100"
    if amount < 1000:
        return "100-1000"
    if amount < 10000:
        return "1000-10000"
    return "10000+"
