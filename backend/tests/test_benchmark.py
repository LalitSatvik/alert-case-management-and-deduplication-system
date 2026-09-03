"""Tests for the grouping-accuracy benchmark harness."""

from __future__ import annotations

import dataclasses
import json
import pathlib

from app.grouping.config import load_config
from scripts.benchmark import evaluate

_DATA_DIR = pathlib.Path(__file__).parent.parent / "scripts/data"


def _load(name: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (_DATA_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


DATA = _load("benchmark.jsonl")
HARD_DATA = _load("benchmark_hard.jsonl")


def test_benchmark_meets_targets_on_committed_dataset() -> None:
    r = evaluate(DATA, load_config("config/grouping.yaml"))
    assert r["f1"] >= 0.90, r
    assert r["false_merge_rate"] <= 0.02, r


def test_perfect_prediction_scores_one() -> None:
    rows = [
        {
            "external_alert_id": "a",
            "source_system": "s",
            "event_time": "2026-08-30T12:00:00Z",
            "amount": "500",
            "currency": "USD",
            "direction": "outbound",
            "account_ref": "A",
            "counterparty_ref": "C",
            "ground_truth_group_id": "g1",
        },
        {
            "external_alert_id": "b",
            "source_system": "s",
            "event_time": "2026-08-30T12:05:00Z",
            "amount": "500",
            "currency": "USD",
            "direction": "outbound",
            "account_ref": "A",
            "counterparty_ref": "C",
            "ground_truth_group_id": "g1",
        },
    ]
    r = evaluate(rows, load_config("config/grouping.yaml"))
    assert r["f1"] == 1.0


def test_hard_benchmark_is_discriminating() -> None:
    """The hard set exercises similarity scoring: the default config passes the
    0.90 floor but is *not* trivially perfect (bounded above at 0.99), and it
    does not false-merge the decoys."""
    r = evaluate(HARD_DATA, load_config("config/grouping.yaml"))
    assert 0.90 <= r["f1"] <= 0.99, r
    assert r["false_merge_rate"] <= 0.05, r


def test_hard_benchmark_needs_the_similarity_path() -> None:
    """Proof the gate discriminates: with the weighted similarity score disabled
    (threshold pushed above its maximum), the same config drops below the 0.90
    floor on the hard set -- the similarity-only members can no longer be
    recovered."""
    config = load_config("config/grouping.yaml")
    no_similarity = dataclasses.replace(config, similarity_threshold=2.0)
    r = evaluate(HARD_DATA, no_similarity)
    assert r["f1"] < 0.90, r
