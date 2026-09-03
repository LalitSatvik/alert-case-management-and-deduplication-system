"""Pure grouping engine: config model, blocking, and scoring.

No database and no I/O beyond reading the YAML config file; no wall-clock reads
and no randomness. Given the same inputs every function here returns a
byte-for-byte identical result, which is what makes engine runs reproducible and
auditable.

This package module owns the frozen config dataclasses (:class:`Rule`,
:class:`FeatureWeights`, :class:`GroupingConfig`) and the pinned
:data:`ENGINE_VERSION`; :mod:`app.grouping.config` loads/hashes them,
:mod:`app.grouping.blocking` generates candidate pairs, and
:mod:`app.grouping.scoring` decides each pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["ENGINE_VERSION", "FeatureWeights", "GroupingConfig", "Rule"]

ENGINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class Rule:
    """A single grouping rule: how to block on it and how to match it exactly.

    Attributes:
        id: Stable identifier (e.g. ``"same-txn-dispute"``).
        enabled: Disabled rules are skipped by both blocking and matching.
        blocking_keys: Alert fields (plus the pseudo-field ``"amount_bucket"``)
            whose values, combined, form one blocking bucket.
        time_window_seconds: Max ``|event_time|`` gap for a candidate / match.
        amount_tolerance: Allowed ``|a-b| / max(a, b, 1)`` fraction for the
            ``"amount"`` match key (``0.0`` = exact).
        match_keys: Fields that must all agree for a deterministic match.
        weight: Rule confidence weight (consumed by engine resolution).
    """

    id: str
    enabled: bool
    blocking_keys: tuple[str, ...]
    time_window_seconds: int
    amount_tolerance: float
    match_keys: tuple[str, ...]
    weight: float


@dataclass(frozen=True)
class FeatureWeights:
    """Similarity-feature weights; expected to sum to ~1.0 (not enforced)."""

    time: float
    amount: float
    name: float
    device: float
    ip: float
    typology: float


@dataclass(frozen=True)
class GroupingConfig:
    """The full, immutable grouping-engine configuration."""

    rules: tuple[Rule, ...]
    weights: FeatureWeights
    similarity_threshold: float
    candidate_cap: int
    time_tau_seconds: int
    dispositions: tuple[str, ...]
    risk_aggregation: Literal["max", "sum_capped", "weighted"]
