"""Grouping-accuracy benchmark: run the pure engine over a labelled dataset.

``evaluate`` builds an :class:`~app.grouping.blocking.EngineAlert` from every row,
runs :func:`app.grouping.engine.group`, then compares the predicted grouping
against each row's ``ground_truth_group_id`` at the **pair** level over all
unordered alert pairs:

* ``TP`` -- predicted together AND truly together
* ``FP`` -- predicted together AND truly apart
* ``FN`` -- predicted apart AND truly together

from which ``precision = TP/(TP+FP)``, ``recall = TP/(TP+FN)``,
``f1 = 2PR/(P+R)`` and ``false_merge_rate = FP/(TP+FP)`` (the share of
predicted-together pairs that are wrong).

Zero-denominator handling:

* ``precision`` / ``recall`` -> ``1.0`` when their denominator is 0 (no predicted
  pairs / no true pairs is vacuously perfect);
* ``f1`` -> ``0.0`` only when ``precision + recall == 0``;
* ``false_merge_rate`` -> ``0.0`` when nothing was predicted together.

CLI::

    python scripts/benchmark.py --dataset scripts/data/benchmark.jsonl \\
        --min-f1 0.90 --max-false-merge 0.02

Exits non-zero when ``f1 < --min-f1`` or ``false_merge_rate > --max-false-merge``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from typing import Any

from app.grouping import GroupingConfig
from app.grouping.blocking import EngineAlert
from app.grouping.config import load_config
from app.grouping.engine import group as engine_group
from app.ingestion.normalize import normalize_merchant_name

__all__ = ["evaluate", "load_rows"]


def load_rows(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL dataset into a list of dicts (blank lines skipped)."""
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _engine_alert(row: dict[str, Any]) -> EngineAlert:
    return EngineAlert(
        id=str(row["external_alert_id"]),
        event_time=datetime.fromisoformat(str(row["event_time"])),
        amount=Decimal(str(row["amount"])),
        currency=str(row["currency"]),
        customer_ref=row.get("customer_ref"),
        account_ref=row.get("account_ref"),
        counterparty_ref=row.get("counterparty_ref"),
        merchant_name_normalised=normalize_merchant_name(row.get("merchant_name")),
        mcc=row.get("mcc"),
        device_id=row.get("device_id"),
        ip_address=row.get("ip_address"),
        session_id=row.get("session_id"),
        typologies=frozenset(row.get("typologies") or []),
    )


def evaluate(rows: list[dict[str, Any]], config: GroupingConfig) -> dict[str, Any]:
    """Return pair-level accuracy metrics for the engine on ``rows``."""
    engine_alerts = [_engine_alert(row) for row in rows]
    decisions = engine_group(engine_alerts, config)
    predicted = {d.alert_id: d.group_key for d in decisions}
    truth = {str(row["external_alert_id"]): row.get("ground_truth_group_id") for row in rows}

    ids = sorted(truth)
    tp = fp = fn = 0
    for a, b in combinations(ids, 2):
        pred_together = predicted[a] == predicted[b]
        true_together = truth[a] is not None and truth[a] == truth[b]
        if pred_together and true_together:
            tp += 1
        elif pred_together:
            fp += 1
        elif true_together:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    false_merge_rate = fp / (tp + fp) if (tp + fp) else 0.0

    return {
        "pairs_total": len(ids) * (len(ids) - 1) // 2,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_merge_rate": false_merge_rate,
        "predicted_groups": len(set(predicted.values())),
        "true_groups": len(set(truth.values())),
        "alerts": len(ids),
    }


def _format_report(result: dict[str, Any], min_f1: float, max_false_merge: float) -> str:
    ok_f1 = result["f1"] >= min_f1
    ok_fm = result["false_merge_rate"] <= max_false_merge
    lines = [
        "grouping benchmark",
        "==================",
        f"alerts            {result['alerts']}",
        f"pairs_total       {result['pairs_total']}",
        f"true_groups       {result['true_groups']}",
        f"predicted_groups  {result['predicted_groups']}",
        f"TP / FP / FN      {result['tp']} / {result['fp']} / {result['fn']}",
        f"precision         {result['precision']:.4f}",
        f"recall            {result['recall']:.4f}",
        f"f1                {result['f1']:.4f}   (>= {min_f1}: {'PASS' if ok_f1 else 'FAIL'})",
        (
            f"false_merge_rate  {result['false_merge_rate']:.4f}   "
            f"(<= {max_false_merge}: {'PASS' if ok_fm else 'FAIL'})"
        ),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark the grouping engine on a labelled set.")
    parser.add_argument("--dataset", type=Path, required=True, help="path to the JSONL dataset")
    parser.add_argument("--config", type=Path, default=Path("config/grouping.yaml"))
    parser.add_argument("--min-f1", type=float, default=0.90)
    parser.add_argument("--max-false-merge", type=float, default=0.02)
    args = parser.parse_args(argv)

    rows = load_rows(args.dataset)
    result = evaluate(rows, load_config(str(args.config)))
    print(_format_report(result, args.min_f1, args.max_false_merge))

    if result["f1"] < args.min_f1 or result["false_merge_rate"] > args.max_false_merge:
        print("\nbenchmark gate: FAIL")
        return 1
    print("\nbenchmark gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
