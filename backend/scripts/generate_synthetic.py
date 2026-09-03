"""Deterministic synthetic alert generator.

``generate`` builds a list of ``AlertIn``-valid dicts made of coherent *clusters*
(alerts that genuinely belong together) and *singletons* (alerts that belong to
nobody). Every value is drawn from a single ``random.Random(seed)`` in a fixed
order, so ``generate(...)`` called twice with the same arguments returns an
identical list -- same rows, same order.

Cluster coherence (what lets the default grouping config recover them):

* every member shares ``customer_ref``, ``account_ref``, ``counterparty_ref`` and
  ``merchant_name`` -- one namespace per cluster, never reused by another cluster
  or by a singleton;
* ``event_time`` is jittered inside a 6-12h window (well inside every rule's time
  window, so the ``same-customer-72h`` and ``same-txn-dispute`` rules block and
  match every intra-cluster pair);
* ``amount`` is exact-equal for ~80% of members (so ``same-txn-dispute``, which
  needs amount within +/-0, fires) with a ~1-3% jitter on the rest;
* ~40% of members share a ``device_id`` and ~30% share an ``ip_address`` +
  ``session_id``, adding secondary deterministic edges.

Singletons get globally unique everything and a unique ``ground_truth_group_id``,
so no rule ever blocks them against another alert.

``ambiguity`` (default ``0.0``, which reproduces the behaviour above *exactly* --
not one extra RNG draw is made) turns on hard cases that only the similarity
score can resolve:

* **similarity-only members** -- ``round(ambiguity * cluster_size)`` extra members
  per cluster that share only ``account_ref`` (so ``same-txn-dispute`` *blocks*
  them, within 24h) plus ``merchant_name`` / ``device_id`` / ``typologies``, but
  carry a unique ``customer_ref`` / ``counterparty_ref`` and an amount + time
  jitter that breaks every deterministic rule -- the engine can only pull them
  into their cluster via the weighted similarity score crossing
  ``similarity_threshold``. They keep their cluster's ``ground_truth_group_id``.
* **near-miss decoys** -- ``round(ambiguity * n_clusters)`` alerts that share
  exactly one blocking key (``account_ref``) with a cluster but have their own
  unique group id, merchant, counterparty and a very different amount -- a
  correct engine must *not* group them, an over-eager one false-merges.

CLI::

    python scripts/generate_synthetic.py --clusters 200 --min 2 --max 6 \\
        --singletons 300 --seed 42 --out scripts/data/benchmark.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

__all__ = ["generate"]

_BASE_TIME = datetime(2026, 1, 6, 9, 0, 0, tzinfo=UTC)
_SOURCE_SYSTEMS = ("acme-fraud", "txmon-core", "sanctions-screen")
_CURRENCIES = ("USD", "EUR", "GBP")
_DIRECTIONS = ("inbound", "outbound", "internal")
_MERCHANTS = (
    "Quick Cash LLC",
    "Blue Harbor Retail",
    "Nova Telecom",
    "Riverbank Supplies",
    "Apex Digital Goods",
    "Meridian Travel",
    "Coastline Foods",
    "Ironwood Hardware",
)
_MCCS = ("6011", "5411", "4829", "5999", "7995")
_TYPOLOGIES = ("structuring", "layering", "card-testing", "account-takeover", "mule-network")

_CLUSTER_TIME_WINDOW_HOURS = (6.0, 12.0)
_EXACT_AMOUNT_RATE = 0.8
_SHARE_DEVICE_RATE = 0.4
_SHARE_IP_SESSION_RATE = 0.3

# Hard-case tuning (ambiguity > 0 only). The time jitter stays inside
# ``same-txn-dispute``'s 24h blocking window (so the pair is a candidate) but well
# outside ``card-testing-burst`` (30m) and ``shared-ip-session`` (2h); the amount
# jitter breaks ``same-txn-dispute``'s +/-0 amount match. What remains is a
# similarity edge whose strength depends on how close in time / amount the hard
# member lands -- so a tunable fraction cross ``similarity_threshold`` and the
# rest are genuine misses.
_AMBIG_TIME_SECONDS = (7200.0, 36000.0)  # 2h .. 10h from the cluster start
_AMBIG_AMOUNT_DRIFT = (0.05, 0.22)  # 5% .. 22%
_DECOY_TIME_SECONDS = 72000.0  # decoy lands within 20h of its target cluster


def _ipv4(n: int) -> str:
    """Map a counter to a distinct RFC 1918 address (n < 2**24)."""
    return f"10.{(n >> 16) & 0xFF}.{(n >> 8) & 0xFF}.{n & 0xFF}"


def _amount_str(value: Decimal) -> str:
    """Quantise to 2 decimal places and render as a plain string."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _prune(row: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is ``None`` so the row is a tidy JSON object."""
    return {k: v for k, v in row.items() if v is not None}


def generate(
    n_clusters: int,
    cluster_size_range: tuple[int, int],
    singleton_count: int,
    seed: int,
    ambiguity: float = 0.0,
) -> list[dict[str, Any]]:
    """Return a deterministic list of ``AlertIn``-valid alert dicts.

    Args:
        n_clusters: number of coherent clusters to emit.
        cluster_size_range: inclusive ``(min, max)`` member count per cluster.
        singleton_count: number of lone alerts (each its own ground-truth group).
        seed: seeds the one ``random.Random`` that drives every choice.
        ambiguity: ``0.0`` (default) emits only clean clusters + singletons and is
            byte-for-byte identical to the pre-``ambiguity`` generator. ``> 0``
            additionally injects similarity-only cluster members and near-miss
            decoys (see the module docstring) at a rate scaled by this value.
    """
    rng = random.Random(seed)
    lo, hi = cluster_size_range
    rows: list[dict[str, Any]] = []
    ip_counter = 1
    cluster_starts: list[datetime] = []
    cluster_accounts: list[str] = []

    for i in range(n_clusters):
        gid = f"grp-{i}"
        size = rng.randint(lo, hi)
        start = _BASE_TIME + timedelta(
            days=rng.randint(0, 240),
            minutes=rng.randint(0, 600),
        )
        window_seconds = rng.uniform(*_CLUSTER_TIME_WINDOW_HOURS) * 3600.0

        account_ref = f"acct-c{i}"
        counterparty_ref = f"cp-c{i}"
        customer_ref = f"cust-c{i}"
        merchant_name = f"{rng.choice(_MERCHANTS)} #{i}"
        mcc = rng.choice(_MCCS)
        currency = rng.choice(_CURRENCIES)
        source_system = rng.choice(_SOURCE_SYSTEMS)
        typologies = [rng.choice(_TYPOLOGIES)]
        base_amount = Decimal(rng.randrange(1_000, 900_000)) / Decimal(100)

        cluster_device = f"dev-c{i}"
        cluster_session = f"sess-c{i}"
        cluster_ip = _ipv4(ip_counter)
        ip_counter += 1

        cluster_starts.append(start)
        cluster_accounts.append(account_ref)

        for k in range(size):
            offset = 0.0 if k == 0 else rng.uniform(0.0, window_seconds)
            event_time = start + timedelta(seconds=int(offset))

            if k == 0 or rng.random() >= (1.0 - _EXACT_AMOUNT_RATE):
                amount = base_amount
            else:
                drift = Decimal(str(rng.uniform(1.0, 3.0))) / Decimal(100)
                sign = Decimal(1) if rng.random() < 0.5 else Decimal(-1)
                amount = base_amount * (Decimal(1) + sign * drift)

            if rng.random() < _SHARE_DEVICE_RATE:
                device_id: str | None = cluster_device
            else:
                device_id = f"dev-c{i}-m{k}"

            if rng.random() < _SHARE_IP_SESSION_RATE:
                ip_address: str | None = cluster_ip
                session_id: str | None = cluster_session
            else:
                ip_address = _ipv4(ip_counter)
                ip_counter += 1
                session_id = f"sess-c{i}-m{k}"

            rows.append(
                _prune(
                    {
                        "external_alert_id": f"{gid}-a{k}",
                        "source_system": source_system,
                        "event_time": event_time.isoformat(),
                        "amount": _amount_str(amount),
                        "currency": currency,
                        "direction": rng.choice(_DIRECTIONS),
                        "customer_ref": customer_ref,
                        "account_ref": account_ref,
                        "counterparty_ref": counterparty_ref,
                        "merchant_name": merchant_name,
                        "mcc": mcc,
                        "device_id": device_id,
                        "ip_address": ip_address,
                        "session_id": session_id,
                        "risk_score": rng.randint(30, 95),
                        "typologies": typologies,
                        "ground_truth_group_id": gid,
                    }
                )
            )

        n_ambig = round(ambiguity * size) if ambiguity > 0 else 0
        if n_ambig:
            core_rows = rows[-size:]
            if not any(r.get("device_id") == cluster_device for r in core_rows):
                # Guarantee at least one deterministic member carries the shared
                # device so the similarity-only members have an edge to land on.
                core_rows[0]["device_id"] = cluster_device
            for m in range(n_ambig):
                dt_seconds = rng.uniform(*_AMBIG_TIME_SECONDS)
                hard_time = start + timedelta(seconds=int(dt_seconds))
                drift = Decimal(str(rng.uniform(*_AMBIG_AMOUNT_DRIFT)))
                sign = Decimal(1) if rng.random() < 0.5 else Decimal(-1)
                hard_amount = base_amount * (Decimal(1) + sign * drift)
                hard_ip = _ipv4(ip_counter)
                ip_counter += 1
                rows.append(
                    _prune(
                        {
                            "external_alert_id": f"{gid}-x{m}",
                            "source_system": source_system,
                            "event_time": hard_time.isoformat(),
                            "amount": _amount_str(hard_amount),
                            "currency": currency,
                            "direction": rng.choice(_DIRECTIONS),
                            "customer_ref": f"cust-c{i}-x{m}",
                            "account_ref": account_ref,
                            "counterparty_ref": f"cp-c{i}-x{m}",
                            "merchant_name": merchant_name,
                            "mcc": mcc,
                            "device_id": cluster_device,
                            "ip_address": hard_ip,
                            "session_id": f"sess-c{i}-x{m}",
                            "risk_score": rng.randint(30, 95),
                            "typologies": typologies,
                            "ground_truth_group_id": gid,
                        }
                    )
                )

    n_decoys = round(ambiguity * n_clusters) if ambiguity > 0 else 0
    for d in range(n_decoys):
        target = d % n_clusters
        decoy_time = cluster_starts[target] + timedelta(
            seconds=int(rng.uniform(0.0, _DECOY_TIME_SECONDS))
        )
        decoy_amount = Decimal(rng.randrange(500, 950_000)) / Decimal(100)
        decoy_ip = _ipv4(ip_counter)
        ip_counter += 1
        rows.append(
            _prune(
                {
                    "external_alert_id": f"dcy-{d}-a0",
                    "source_system": rng.choice(_SOURCE_SYSTEMS),
                    "event_time": decoy_time.isoformat(),
                    "amount": _amount_str(decoy_amount),
                    "currency": rng.choice(_CURRENCIES),
                    "direction": rng.choice(_DIRECTIONS),
                    "customer_ref": f"cust-dcy-{d}",
                    "account_ref": cluster_accounts[target],
                    "counterparty_ref": f"cp-dcy-{d}",
                    "merchant_name": f"{rng.choice(_MERCHANTS)} decoy {d}",
                    "mcc": rng.choice(_MCCS),
                    "device_id": f"dev-dcy-{d}",
                    "ip_address": decoy_ip,
                    "session_id": f"sess-dcy-{d}",
                    "risk_score": rng.randint(20, 85),
                    "typologies": [rng.choice(_TYPOLOGIES)],
                    "ground_truth_group_id": f"dcy-{d}",
                }
            )
        )

    for j in range(singleton_count):
        gid = f"sng-{j}"
        start = _BASE_TIME + timedelta(
            days=rng.randint(0, 240),
            minutes=rng.randint(0, 1440),
        )
        amount = Decimal(rng.randrange(500, 950_000)) / Decimal(100)
        ip_address = _ipv4(ip_counter)
        ip_counter += 1
        rows.append(
            _prune(
                {
                    "external_alert_id": f"{gid}-a0",
                    "source_system": rng.choice(_SOURCE_SYSTEMS),
                    "event_time": start.isoformat(),
                    "amount": _amount_str(amount),
                    "currency": rng.choice(_CURRENCIES),
                    "direction": rng.choice(_DIRECTIONS),
                    "customer_ref": f"cust-s{j}",
                    "account_ref": f"acct-s{j}",
                    "counterparty_ref": f"cp-s{j}",
                    "merchant_name": f"{rng.choice(_MERCHANTS)} solo {j}",
                    "mcc": rng.choice(_MCCS),
                    "device_id": f"dev-s{j}",
                    "ip_address": ip_address,
                    "session_id": f"sess-s{j}",
                    "risk_score": rng.randint(10, 80),
                    "typologies": [rng.choice(_TYPOLOGIES)],
                    "ground_truth_group_id": gid,
                }
            )
        )

    rng.shuffle(rows)
    return rows


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a synthetic alert dataset (JSONL).")
    parser.add_argument("--clusters", type=int, required=True, help="number of coherent clusters")
    parser.add_argument(
        "--min", type=int, required=True, help="min members per cluster (inclusive)"
    )
    parser.add_argument(
        "--max", type=int, required=True, help="max members per cluster (inclusive)"
    )
    parser.add_argument("--singletons", type=int, required=True, help="number of lone alerts")
    parser.add_argument("--seed", type=int, required=True, help="RNG seed (full determinism)")
    parser.add_argument(
        "--ambiguity",
        type=float,
        default=0.0,
        help="0.0 = clean clusters only; > 0 injects similarity-only + decoy hard cases",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="output path (one JSON object/line)"
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_arg_parser().parse_args(argv)
    rows = generate(args.clusters, (args.min, args.max), args.singletons, args.seed, args.ambiguity)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} alerts to {args.out}")


if __name__ == "__main__":
    main()
