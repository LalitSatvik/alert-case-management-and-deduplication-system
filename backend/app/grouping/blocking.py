"""Blocking / candidate-pair generation for the grouping engine.

Pure and deterministic: :func:`candidate_pairs` depends only on its arguments --
never on wall-clock time, randomness, or set-iteration order. Given the same
alerts and config it returns the same set of ``(min_id, max_id)`` tuples every
call. The blocking stage is a cheap recall filter; :mod:`app.grouping.scoring`
decides each surviving pair.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import structlog

from app.grouping import GroupingConfig, Rule
from app.ingestion.normalize import amount_bucket

__all__ = ["EngineAlert", "blocking_key_values", "candidate_pairs"]

_log = structlog.get_logger("grouping.blocking")


@dataclass(frozen=True)
class EngineAlert:
    """Immutable projection of an alert with only the fields the engine needs.

    Deliberately decoupled from the ``Alert`` ORM model: engine callers build
    these from persisted rows (or from test fixtures) so the engine never touches
    a database session.
    """

    id: str
    event_time: datetime
    amount: Decimal
    currency: str
    customer_ref: str | None
    account_ref: str | None
    counterparty_ref: str | None
    merchant_name_normalised: str | None
    mcc: str | None
    device_id: str | None
    ip_address: str | None
    session_id: str | None
    typologies: frozenset[str]


def blocking_key_values(alert: EngineAlert, rule: Rule) -> list[str]:
    """Return the ``field=value`` components of ``rule``'s blocking key for ``alert``.

    A single-key rule yields one component (``["account_ref=ACCT-1"]``); a
    composite rule yields one per key (``["device_id=DEV-9", "amount_bucket=100-1000"]``)
    which the caller treats as a single combined bucket. ``"amount_bucket"`` is a
    pseudo-field resolved via :func:`app.ingestion.normalize.amount_bucket`.

    Returns ``[]`` when any component resolves to ``None`` -- the alert cannot be
    blocked by this rule and is dropped from its buckets entirely.
    """
    parts: list[str] = []
    for key in rule.blocking_keys:
        value = amount_bucket(alert.amount) if key == "amount_bucket" else getattr(alert, key)
        if value is None:
            return []
        parts.append(f"{key}={value}")
    return parts


def candidate_pairs(alerts: list[EngineAlert], config: GroupingConfig) -> set[tuple[str, str]]:
    """Generate candidate alert-id pairs via per-rule blocking.

    For every enabled rule the alerts are bucketed by that rule's (possibly
    composite) blocking key; each intra-bucket pair whose ``|event_time|`` gap is
    ``<= rule.time_window_seconds`` becomes a candidate. Each alert keeps at most
    ``config.candidate_cap`` counterparts -- overflow is logged and dropped
    deterministically, keeping the lexicographically smallest counterpart ids. A
    pair is emitted only if *both* endpoints kept each other, so no alert appears
    in more than ``candidate_cap`` pairs. Tuples are ordered ``(min_id, max_id)``.
    """
    counterparts: defaultdict[str, set[str]] = defaultdict(set)
    for rule in config.rules:
        if not rule.enabled:
            continue
        buckets: defaultdict[tuple[str, ...], list[EngineAlert]] = defaultdict(list)
        for alert in alerts:
            parts = blocking_key_values(alert, rule)
            if parts:
                buckets[tuple(parts)].append(alert)
        window = rule.time_window_seconds
        for bucket in buckets.values():
            for i in range(len(bucket)):
                for j in range(i + 1, len(bucket)):
                    left, right = bucket[i], bucket[j]
                    delta = abs((left.event_time - right.event_time).total_seconds())
                    if delta <= window:
                        counterparts[left.id].add(right.id)
                        counterparts[right.id].add(left.id)

    cap = config.candidate_cap
    allowed: dict[str, set[str]] = {}
    for alert_id in sorted(counterparts):
        cps = counterparts[alert_id]
        if len(cps) > cap:
            _log.debug(
                "candidate_cap_exceeded",
                alert_id=alert_id,
                kept=cap,
                dropped=len(cps) - cap,
            )
            allowed[alert_id] = set(sorted(cps)[:cap])
        else:
            allowed[alert_id] = set(cps)

    pairs: set[tuple[str, str]] = set()
    for alert_id, cps in allowed.items():
        for counterpart in cps:
            if alert_id in allowed.get(counterpart, set()):
                low, high = sorted((alert_id, counterpart))
                pairs.add((low, high))
    return pairs
