"""Tests for the deterministic synthetic alert generator."""

from __future__ import annotations

from app.schemas.alert import AlertIn
from scripts.generate_synthetic import generate


def test_generation_is_deterministic_for_a_seed() -> None:
    assert generate(10, (2, 4), 5, seed=1) == generate(10, (2, 4), 5, seed=1)


def test_every_row_validates_as_alert_in() -> None:
    for row in generate(20, (2, 5), 10, seed=7):
        AlertIn(**row)


def test_cluster_members_share_ground_truth_group() -> None:
    rows = generate(5, (3, 3), 0, seed=3)
    by_group: dict[str, list[dict[str, object]]] = {}
    for r in rows:
        by_group.setdefault(str(r["ground_truth_group_id"]), []).append(r)
    assert all(len(v) == 3 for v in by_group.values())
    assert len(by_group) == 5


def test_clusters_are_mostly_recoverable_by_shared_keys() -> None:
    rows = generate(5, (3, 3), 0, seed=3)
    by_group: dict[str, set[object]] = {}
    for r in rows:
        by_group.setdefault(str(r["ground_truth_group_id"]), set()).add(r["account_ref"])
    assert all(len(accts) == 1 for accts in by_group.values())


def test_singletons_are_globally_unique_on_blocking_keys() -> None:
    rows = generate(8, (2, 4), 20, seed=11)
    singletons = [r for r in rows if str(r["ground_truth_group_id"]).startswith("sng-")]
    assert len(singletons) == 20
    for key in ("customer_ref", "account_ref", "counterparty_ref", "device_id", "ip_address"):
        values = [r[key] for r in rows if r.get(key) is not None]
        singleton_values = [r[key] for r in singletons if r.get(key) is not None]
        # No singleton shares a blocking-key value with any other row.
        for value in singleton_values:
            assert values.count(value) == 1


def test_counts_match_requested_shape() -> None:
    rows = generate(6, (2, 2), 4, seed=5)
    groups = {str(r["ground_truth_group_id"]) for r in rows}
    assert len([g for g in groups if g.startswith("grp-")]) == 6
    assert len([g for g in groups if g.startswith("sng-")]) == 4
    assert len(rows) == 6 * 2 + 4
