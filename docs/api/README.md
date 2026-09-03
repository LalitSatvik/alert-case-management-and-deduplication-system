# ACMS HTTP API

Alert Case Management & Deduplication System — API `1.0.0` (OpenAPI 3.1).

The live schema is served by the running stack at **`/api/v1/openapi.json`**, with
Swagger UI at `/api/v1/docs` and ReDoc at `/api/v1/redoc`. This file is a
committed snapshot of that schema; regenerate it after changing a route:

```bash
cd backend
python -c "import json, app.main; print(json.dumps(app.main.app.openapi(), indent=2))" > ../docs/api/openapi.json
```

`backend/tests/test_openapi.py` fails if any core path stops being registered.

## Conventions

- **Base path:** `/api/v1` for the application API. `/healthz`, `/readyz` and
  `/metrics` sit at the root (they are proxied straight through by Caddy).
- **Auth:** `Authorization: Bearer <access token>` from `POST /api/v1/auth/token`.
  Ingestion endpoints instead take `X-API-Key: <ingest key>`.
- **RBAC:** roles are `admin`, `analyst`, `readonly`. Each endpoint below notes
  the roles it accepts.
- **Optimistic concurrency:** `POST /cases/{case_id}/transition` accepts an
  `If-Match: <version>` header and returns `409` on a stale version.
- **Errors:** validation failures return `422` with a FastAPI error body;
  domain errors return a stable string in `detail` (e.g. `illegal_transition`,
  `stale_case_version`, `case_not_found`).

## Endpoints

### Ops (unauthenticated)

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness — always `200 {"status":"ok"}`. |
| GET | `/readyz` | Readiness — checks Postgres + Valkey; `503` with per-component detail when a dependency is down. |
| GET | `/metrics` | Prometheus exposition format. |

### Auth — `tag: auth`

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/v1/auth/token` | `{email, password}` | Returns `{access_token, refresh_token, token_type}`. |
| POST | `/api/v1/auth/refresh` | `{refresh_token}` | Returns a fresh `{access_token, token_type}`. |

### Ingestion — `tag: ingestion` (API key, scope `ingest`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/v1/alerts` | `X-API-Key` | Single alert. Optional `Idempotency-Key` header. Persists, groups synchronously, audits. `201`. |
| POST | `/api/v1/alerts:batch` | `X-API-Key` | JSON array of alerts. Persists all, enqueues one async grouping job, returns `202 {accepted, duplicates, rejected[], job_id, grouping_enqueued}`. |

### Cases — `tag: cases`

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/api/v1/cases` | analyst, admin, readonly | Filtered, keyset-paginated list. Filters: `status`, `disposition`, `assignee_id` (or `unassigned`), `created_from/to`, `closed_from/to`, `risk_min/max`, `source_system`, `typology`, `q`. `sort` ∈ `-risk_score`, `-created_at`, `oldest_alert`. `limit` ≤ 200, `cursor`. |
| GET | `/api/v1/cases/{case_id}` | analyst, admin, readonly | Case header + linked alerts (with grouping rationale) + all notes + audit timeline (newest first). |
| POST | `/api/v1/cases/{case_id}/transition` | analyst, admin | Body `{to, reason?, disposition?}`. `disposition` required to close; `reason` required to re-open. `If-Match` header for concurrency. `200`, `409` (illegal / stale), `422` (guard failed). |
| POST | `/api/v1/cases/{case_id}/assign` | analyst, admin | Body `{assignee_id}` — a user id, or `null` to unassign. |
| POST | `/api/v1/cases/{case_id}/notes` | analyst, admin | Body `{body}` (non-empty). Appends an immutable note. `201`. |
| POST | `/api/v1/cases/{case_id}/notes/{note_id}/retract` | analyst, admin | Body `{reason}`. Author-or-admin only. Marks retracted, keeps the row. |

### Audit — `tag: audit`

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/api/v1/audit` | admin, readonly | Filtered, keyset-paginated global log (newest first). Filters: `actor_id`, `action`, `target_type`, `target_id`, `from`, `to`, `cursor`, `limit`. |
| GET | `/api/v1/cases/{case_id}/audit` | analyst, admin, readonly | The `case:{id}` hash-chained stream, ordered by `seq`. |
| POST | `/api/v1/cases/{case_id}/audit:export` | analyst, admin, readonly | `?format=json\|html`. JSON bundle = case header + alerts (grouping rationale) + notes + full event stream + `chain_verified`. HTML = one self-contained, XSS-safe document. The export is itself audited (`case.audit_exported`). |
| POST | `/api/v1/audit:verify` | admin | Recomputes every stream, tip-anchors it against `audit_streams`, and flags orphan streams. Returns `{streams_checked, broken[]}`. |

## Audit actions

Events on a `case:{id}` stream use these `action` values: `case.alert_linked`,
`case.transitioned`, `case.assigned`, `case.note_added`, `case.note_retracted`,
`case.review_flagged`, `case.merged`, `case.audit_exported`. Alert ingestion
writes `alert.ingested` on the alert stream.
