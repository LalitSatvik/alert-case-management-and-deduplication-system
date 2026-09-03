# backend scripts

All commands run from `backend/`, with the dev dependencies installed (`pip install -e ".[dev]"`).

## `generate_synthetic.py` — deterministic synthetic alert generator

`generate(n_clusters, cluster_size_range, singleton_count, seed)` returns a list
of `AlertIn`-valid dicts. It is driven by a single `random.Random(seed)`, so the
same arguments always produce the identical list (same rows, same order).

- **Clusters** — each shares one `ground_truth_group_id` and a coherent core:
  the same `customer_ref`, `account_ref`, `counterparty_ref` and `merchant_name`
  (a namespace unique to that cluster), a base `amount` that ~80% of members
  match exactly (the rest drift 1–3%), `event_time` jittered inside a 6–12h
  window, ~40% of members sharing a `device_id` and ~30% sharing an
  `ip_address` + `session_id`.
- **Singletons** — globally unique on every blocking key, each its own
  `ground_truth_group_id` (`sng-<n>`). No rule can block them against anything.

`ambiguity` (default `0.0`) is a fifth parameter. At `0.0` the output is
byte-for-byte identical to the description above. Above `0.0` it also injects, at
a rate scaled by the value:

- **similarity-only members** (`grp-<i>-x<m>`) — extra members that share only
  `account_ref` (so `same-txn-dispute` *blocks* them, within 24h) plus
  `merchant_name` / `device_id` / `typologies`, but carry a unique
  `customer_ref` / `counterparty_ref` and an amount + time jitter that breaks
  every deterministic rule. The engine can only pull them into their cluster via
  the weighted similarity score crossing `similarity_threshold` — how many it
  recovers depends entirely on the similarity path.
- **near-miss decoys** (`dcy-<d>`) — alerts sharing exactly one blocking key
  (`account_ref`) with a cluster but with their own group id, merchant,
  counterparty and a very different amount. A correct engine must not group them.

CLI:

```
python scripts/generate_synthetic.py \
    --clusters 200 --min 2 --max 6 --singletons 300 --seed 42 \
    --out scripts/data/benchmark.jsonl
```

writes one JSON object per line.

## Two committed datasets

| file | command | what it is |
|---|---|---|
| `scripts/data/benchmark.jsonl` | `--clusters 200 --min 2 --max 6 --singletons 300 --seed 42` | **structural smoke test** — clean clusters + singletons only. Verifies the engine's deterministic path isn't fundamentally broken. It does *not* exercise similarity scoring. |
| `scripts/data/benchmark_hard.jsonl` | `--clusters 120 --min 3 --max 6 --singletons 150 --seed 43 --ambiguity 0.25` | **discriminating accuracy gate** — 149 similarity-only members + 30 decoys mixed in. Recovering the clusters genuinely requires the weighted similarity score; disabling it drops F1 below the 0.90 floor. |

## `benchmark.py` — grouping-accuracy gate

`evaluate(rows, config)` builds an `EngineAlert` per row, runs
`app.grouping.engine.group`, and scores the predicted grouping against
`ground_truth_group_id` over **every unordered pair** of alerts:

| pair state | meaning |
|---|---|
| TP | predicted together **and** truly together |
| FP | predicted together **and** truly apart |
| FN | predicted apart **and** truly together |

```
precision        = TP / (TP + FP)
recall           = TP / (TP + FN)
f1               = 2·precision·recall / (precision + recall)
false_merge_rate = FP / (TP + FP)      # share of predicted-together pairs that are wrong
```

Zero-denominator handling: `precision` / `recall` are `1.0` when their
denominator is 0 (nothing predicted together / nothing truly together is
vacuously perfect); `f1` is `0.0` only when `precision + recall == 0`;
`false_merge_rate` is `0.0` when nothing was predicted together. The result also
carries `pairs_total`, `predicted_groups`, `true_groups`, `tp`, `fp`, `fn`.

CLI:

```
python scripts/benchmark.py \
    --dataset scripts/data/benchmark_hard.jsonl --min-f1 0.90 --max-false-merge 0.05
```

Exits non-zero if `f1 < --min-f1` or `false_merge_rate > --max-false-merge`.

### Numbers on the committed datasets (default `config/grouping.yaml`)

| metric | `benchmark.jsonl` (smoke) | `benchmark_hard.jsonl` (gate) |
|---|---|---|
| alerts | 1077 | 866 |
| pairs_total | 579426 | 374545 |
| true_groups / predicted_groups | 500 / 500 | 300 / 330 |
| TP / FP / FN | 1323 / 0 / 0 | 1615 / 0 / 137 |
| precision | 1.0000 | 1.0000 |
| recall | 1.0000 | 0.9218 |
| **f1** | **1.0000** | **0.9593** |
| **false_merge_rate** | **0.0000** | **0.0000** |
| CI gate | f1 ≥ 0.90, fmr ≤ 0.02 | f1 ≥ 0.90, fmr ≤ 0.05 |

`benchmark.jsonl` scores 1.0 by construction — the deterministic
`same-customer-72h` rule (matches on `customer_ref` alone, 72h) plus unique
per-cluster namespaces mean there is nothing for the similarity score to do. It
is a smoke test, not an accuracy measurement.

`benchmark_hard.jsonl` is the real accuracy gate. Its 149 similarity-only members
can only be joined to their clusters by the weighted similarity score crossing
`similarity_threshold`; the default config recovers ~92 % of the true pairs
(F1 0.9593) with no false merges, and disabling the similarity path
(`similarity_threshold` above its maximum) drops F1 to ~0.79 — below the 0.90
floor. `pytest` additionally bounds it *above* at 0.99 so it can never silently
become perfect-by-construction; CI only enforces the 0.90 floor.

## `seed.py` — reset the database to a worked demo state

```
DATABASE_URL=postgresql+asyncpg://app_user:app_pw@localhost:5432/acms_test \
MIGRATION_DATABASE_URL=postgresql+asyncpg://acms_owner:owner_pw@localhost:5432/acms_test \
python scripts/seed.py
```

(`make seed` runs the same script inside the compose stack.)

Steps, all idempotent:

1. `alembic upgrade head` (creates the schema on a fresh DB, no-op otherwise).
2. `TRUNCATE` every application table as `acms_owner` and restart
   `case_human_ref_seq` — the cluster, roles and schema are untouched, only data
   is wiped, so a second run lands on the same end state.
3. Create `admin@acms.example.com` / `analyst@acms.example.com` / `auditor@acms.example.com`
   (password `demo-pw`; roles `admin` / `analyst` / `readonly`) and one active
   ingest API key — its raw value is printed once.
4. `generate(150, (2, 6), 200, seed=1)` → ingest every row through
   `ingest_one` (persist + synchronous grouping + audit).
5. Walk 5 resulting cases Open → In Progress and add an analyst note to each.
6. Print a summary (users, api key, alerts, cases).

The database and its roles must already exist (same prerequisite as migrations).

## `export_schema.py`

Regenerates `backend/schemas/alert.schema.json` from `app.schemas.alert.AlertIn`.
