"""Deterministic rule matching and explainable similarity scoring.

Two independent verdicts on a candidate pair:

* :func:`deterministic_match` -- the ids of enabled rules whose every match key
  agrees exactly (within the rule's amount tolerance) inside the time window.
* :func:`feature_contributions` / :func:`score_pair` -- a bounded per-feature
  breakdown and its weighted mean, for pairs no rule matched.

:func:`pair_decision` combines them into the tuple engine resolution
consumes. Every function is pure and deterministic.
"""

from __future__ import annotations

import math
from decimal import Decimal

from rapidfuzz import fuzz

from app.grouping import FeatureWeights, GroupingConfig, Rule
from app.grouping.blocking import EngineAlert
from app.ingestion.normalize import amount_bucket

__all__ = [
    "deterministic_match",
    "feature_contributions",
    "pair_decision",
    "score_pair",
]

_FEATURE_KEYS = ("time", "amount", "name", "device", "ip", "typology")


def _delta_seconds(a: EngineAlert, b: EngineAlert) -> float:
    return abs((a.event_time - b.event_time).total_seconds())


def _match_key_agrees(key: str, a: EngineAlert, b: EngineAlert, rule: Rule) -> bool:
    """Whether a single ``match_key`` agrees for this pair under ``rule``."""
    if key == "amount":
        denom = max(a.amount, b.amount, Decimal(1))
        return abs(a.amount - b.amount) / denom <= Decimal(str(rule.amount_tolerance))
    if key == "amount_bucket":
        return amount_bucket(a.amount) == amount_bucket(b.amount)
    left = getattr(a, key)
    right = getattr(b, key)
    return left is not None and right is not None and bool(left == right)


def deterministic_match(a: EngineAlert, b: EngineAlert, config: GroupingConfig) -> list[str]:
    """Ids of enabled rules that deterministically match this pair.

    A rule matches when ``|event_time| <= rule.time_window_seconds`` and every
    ``rule.match_keys`` entry agrees: equality for refs / ids / session /
    ``amount_bucket`` (both sides non-``None``), and ``amount`` within
    ``rule.amount_tolerance`` (as a fraction of ``max(a, b, 1)``). Empty list
    means no deterministic match -- fall back to similarity.
    """
    matched: list[str] = []
    for rule in config.rules:
        if not rule.enabled:
            continue
        if _delta_seconds(a, b) > rule.time_window_seconds:
            continue
        if all(_match_key_agrees(key, a, b, rule) for key in rule.match_keys):
            matched.append(rule.id)
    return matched


def feature_contributions(
    a: EngineAlert, b: EngineAlert, config: GroupingConfig
) -> dict[str, float]:
    """Per-feature similarity in ``[0, 1]``: ``time, amount, name, device, ip, typology``.

    * ``time``: ``exp(-dt_seconds / config.time_tau_seconds)``
    * ``amount``: ``1 - min(1, |a-b| / max(a, b, 1))``
    * ``name``: ``rapidfuzz.fuzz.token_set_ratio / 100`` (``0`` if either name is ``None``)
    * ``device`` / ``ip``: ``1`` iff equal and not ``None``, else ``0``
    * ``typology``: Jaccard of the two typology sets (``0`` if both are empty)
    """
    time_c = math.exp(-_delta_seconds(a, b) / config.time_tau_seconds)

    left_amount = float(a.amount)
    right_amount = float(b.amount)
    amount_c = 1.0 - min(1.0, abs(left_amount - right_amount) / max(left_amount, right_amount, 1.0))

    if a.merchant_name_normalised is None or b.merchant_name_normalised is None:
        name_c = 0.0
    else:
        name_c = (
            fuzz.token_set_ratio(a.merchant_name_normalised, b.merchant_name_normalised) / 100.0
        )

    device_c = 1.0 if a.device_id is not None and a.device_id == b.device_id else 0.0
    ip_c = 1.0 if a.ip_address is not None and a.ip_address == b.ip_address else 0.0

    if not a.typologies and not b.typologies:
        typology_c = 0.0
    else:
        union = a.typologies | b.typologies
        typology_c = len(a.typologies & b.typologies) / len(union) if union else 0.0

    return {
        "time": time_c,
        "amount": amount_c,
        "name": name_c,
        "device": device_c,
        "ip": ip_c,
        "typology": typology_c,
    }


def _weighted_score(contributions: dict[str, float], weights: FeatureWeights) -> float:
    by_key = {
        "time": weights.time,
        "amount": weights.amount,
        "name": weights.name,
        "device": weights.device,
        "ip": weights.ip,
        "typology": weights.typology,
    }
    total = sum(by_key.values())
    return sum(by_key[key] * contributions[key] for key in _FEATURE_KEYS) / total


def score_pair(a: EngineAlert, b: EngineAlert, config: GroupingConfig) -> float:
    """Weighted mean of :func:`feature_contributions` (``sum(w*c) / sum(w)``)."""
    return _weighted_score(feature_contributions(a, b, config), config.weights)


def pair_decision(
    a: EngineAlert, b: EngineAlert, config: GroupingConfig
) -> tuple[str, list[str], float | None, dict[str, float]]:
    """``(method, matched_rule_ids, similarity_score, contributions)`` for a pair.

    ``method`` is ``"deterministic"`` (score ``None``) when
    :func:`deterministic_match` is non-empty, else ``"similarity"`` with the
    computed score. The caller compares the score to
    ``config.similarity_threshold`` to decide grouping.
    """
    contributions = feature_contributions(a, b, config)
    matched = deterministic_match(a, b, config)
    if matched:
        return ("deterministic", matched, None, contributions)
    return ("similarity", [], _weighted_score(contributions, config.weights), contributions)
