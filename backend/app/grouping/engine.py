"""Grouping resolution: candidate pairs -> kept edges -> connected components.

Pure and deterministic. No database, no I/O, no wall-clock reads, no randomness:
:func:`group` is a byte-for-byte function of ``(alerts, config, pinned_apart,
pinned_together)`` and its output does not depend on the order of the ``alerts``
list. This is what lets a grouping run be replayed and audited.

Pipeline:

1. :func:`app.grouping.blocking.candidate_pairs` proposes ``(min_id, max_id)``
   candidate pairs.
2. Each candidate is judged by :func:`app.grouping.scoring.pair_decision`; the
   edge is *kept* when the pair deterministically matches a rule **or** its
   similarity score is ``>= config.similarity_threshold``.
3. ``pinned_apart`` edges are dropped; ``pinned_together`` edges are force-added
   (with their own ``pair_decision`` metadata).
4. Union-find over the kept edges yields connected components. Each component's
   ``group_key`` is the lexicographically smallest alert id in it -- the same id
   ordering :mod:`app.grouping.blocking` uses for its ``(min_id, max_id)`` tuples.
5. One :class:`Decision` per input alert. A grouped alert reports the
   ``method`` / ``matched_rule_ids`` / ``similarity_score`` / ``contributions`` of
   its *strongest* incident kept edge: deterministic beats similarity; among
   similarity edges the higher score wins; ties break on the counterpart id. A
   lone alert reports ``method="singleton"``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.grouping import GroupingConfig
from app.grouping.blocking import EngineAlert, candidate_pairs
from app.grouping.scoring import pair_decision

__all__ = ["Decision", "group"]


@dataclass(frozen=True)
class Decision:
    """The engine's verdict for a single alert.

    Attributes:
        alert_id: The alert this decision is about.
        group_key: Stable synthetic id shared by every alert the engine puts in
            the same component -- the lexicographically smallest alert id in it.
        method: ``"deterministic"``, ``"similarity"`` or ``"singleton"``.
        matched_rule_ids: Rule ids of the strongest incident edge (empty unless
            ``method == "deterministic"``).
        similarity_score: Score of the strongest incident edge, or ``None`` for a
            deterministic / singleton decision.
        contributions: Per-feature similarity breakdown of the strongest incident
            edge (``{}`` for a singleton).
    """

    alert_id: str
    group_key: str
    method: str
    matched_rule_ids: tuple[str, ...]
    similarity_score: float | None
    contributions: dict[str, float]


@dataclass
class _Edge:
    method: str
    matched_rule_ids: tuple[str, ...]
    score: float | None
    contributions: dict[str, float]


class _UnionFind:
    """Union-find whose set representative is always the set's minimum element."""

    def __init__(self, items: Iterable[str]) -> None:
        self._parent: dict[str, str] = {x: x for x in items}

    def find(self, x: str) -> str:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        lo, hi = (ra, rb) if ra < rb else (rb, ra)
        self._parent[hi] = lo


def _norm(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _edge_sort_key(counterpart: str, edge: _Edge) -> tuple[int, float, str]:
    """Lower is stronger: deterministic first, then higher score, then lower id."""
    if edge.method == "deterministic":
        return (0, 0.0, counterpart)
    return (1, -(edge.score or 0.0), counterpart)


def group(
    alerts: list[EngineAlert],
    config: GroupingConfig,
    pinned_apart: Iterable[tuple[str, str]] = frozenset(),
    pinned_together: Iterable[tuple[str, str]] = frozenset(),
) -> list[Decision]:
    """Resolve ``alerts`` into grouping :class:`Decision`s. Pure; order-independent."""
    by_id = {a.id: a for a in alerts}
    ids = sorted(by_id)

    apart = {_norm(a, b) for a, b in pinned_apart}
    together = {_norm(a, b) for a, b in pinned_together}

    kept: dict[tuple[str, str], _Edge] = {}
    for low, high in sorted(candidate_pairs(alerts, config)):
        pair = _norm(low, high)
        if pair in apart:
            continue
        method, rule_ids, score, contribs = pair_decision(by_id[low], by_id[high], config)
        if rule_ids or (score is not None and score >= config.similarity_threshold):
            kept[pair] = _Edge(method, tuple(rule_ids), score, contribs)

    for low, high in sorted(together):
        if low not in by_id or high not in by_id:
            continue
        pair = _norm(low, high)
        if pair in apart or pair in kept:
            continue
        method, rule_ids, score, contribs = pair_decision(by_id[low], by_id[high], config)
        kept[pair] = _Edge(method, tuple(rule_ids), score, contribs)

    uf = _UnionFind(ids)
    for low, high in sorted(kept):
        uf.union(low, high)

    incident: dict[str, list[tuple[str, _Edge]]] = {x: [] for x in ids}
    for (low, high), edge in kept.items():
        incident[low].append((high, edge))
        incident[high].append((low, edge))

    decisions: list[Decision] = []
    for alert_id in ids:
        group_key = uf.find(alert_id)
        edges = incident[alert_id]
        if not edges:
            decisions.append(Decision(alert_id, group_key, "singleton", (), None, {}))
            continue
        _, edge = min(edges, key=lambda ce: _edge_sort_key(ce[0], ce[1]))
        decisions.append(
            Decision(
                alert_id=alert_id,
                group_key=group_key,
                method=edge.method,
                matched_rule_ids=edge.matched_rule_ids,
                similarity_score=edge.score,
                contributions=dict(edge.contributions),
            )
        )
    return decisions
