# Product Requirements Document
## Alert Case Management & Deduplication System (Fraud / Financial Crime)

---

## 1. Document Control

| Field | Value |
|---|---|
| Document title | Alert Case Management & Deduplication System — Product Requirements Document |
| Version | 1.0 (Draft) |
| Status | For review |
| Date | 2026-08-30 |
| Owner | Product / Risk Advisory Delivery Lead |
| Contributors | Fraud Operations SME, Financial Crime Compliance, Engineering Lead, UX |
| Reviewers | Head of Fraud Operations, Internal Audit, Data Protection Officer, Engineering |
| Classification | Internal — engagement deliverable |
| Related documents | Synthetic Data Specification (Appendix D), API Reference (Appendix B), Threat Model (to follow) |

### 1.1 Purpose of this document

This PRD defines the product vision, scope, personas, functional and non-functional
requirements, recommended architecture, and delivery roadmap for a self-contained
**Alert Case Management & Deduplication System**. It is written as a consulting-style
client deliverable: it is precise enough to plan and build against, and structured so
that risk, compliance, and audit stakeholders can trace every requirement to a business
or regulatory need.

The system is delivered as a working reference implementation on **synthetic data**. It
is not a production financial-crime platform and does not file regulatory reports. Where
this document references regulatory regimes, it does so to explain design intent; it is
not legal advice.

### 1.2 Glossary

| Term | Definition |
|---|---|
| **Alert** | A single machine- or rule-generated signal that a transaction, account, or entity may warrant review. The atomic input to the system. |
| **Case** | The canonical unit of investigation. One case groups one or more alerts that refer to the same underlying event or pattern. |
| **Deduplication / grouping** | The process of deciding that two or more alerts belong to the same case. |
| **Blocking** | A cheap first-pass filter that narrows the set of alert pairs considered for similarity scoring (a standard entity-resolution technique). |
| **Canonical case** | The single case record that survives after alerts are grouped; other candidate cases are merged into it. |
| **Disposition** | The final analyst decision on a case (e.g. *No action*, *Escalate*, *Confirmed fraud*, *Confirmed AML concern*). |
| **Audit event** | An immutable record of one state-changing action, capturing actor, timestamp, action, reason, and before/after values. |
| **SLA timer** | A clock attached to a case or case state used to measure and enforce turnaround expectations. |
| **RBAC** | Role-based access control. |
| **TMS** | Transaction-monitoring system — an upstream AML rules engine. |
| **SAR / STR** | Suspicious Activity Report / Suspicious Transaction Report — the regulatory filing a confirmed concern may lead to. Out of scope for this system. |
| **Ground-truth group** | In synthetic data, the known-correct case grouping for an alert, used to measure deduplication accuracy. |

---

## 2. Executive Summary & Background

### 2.1 Problem statement

Financial institutions and their advisory partners generate large volumes of
transaction-monitoring and fraud alerts. A substantial share of these alerts are
near-duplicates referring to the same underlying event — the same disputed transaction
surfaced by three rules, or a burst of card-not-present attempts from one device within
minutes. Analysts spend significant time manually identifying these relationships,
grouping alerts, re-reviewing the same facts, and documenting decisions in inconsistent
ways. The result is wasted analyst capacity, inconsistent case handling, uneven quality,
and — most critically — weak or incomplete audit trails for investigation decisions.

### 2.2 Literature review

Public case studies from Deloitte and EY describe large-scale fraud and AML
transformation programmes that consistently emphasise three themes: **alert triage**,
**case management**, and **reduction of false-positive and duplicate work**. JP Morgan
and peer institutions operate high-volume transaction-monitoring operations that depend
on structured investigation workflows to remain defensible at scale. Industry reports and
bank technology RFPs repeatedly highlight two points relevant here: (1) the operational
cost of ungrouped, un-triaged alerts, and (2) the regulatory expectation of complete,
immutable audit logs covering every investigation decision — who reviewed what, when, and
why. FFIEC examination guidance and model-governance expectations (in the spirit of the
US Federal Reserve's SR 11-7) reinforce that alert-handling logic and its outcomes must
be transparent, tunable, and evidenced.

The entity-resolution and record-linkage literature (Fellegi–Sunter and its successors)
provides well-understood techniques — deterministic keys, blocking, and probabilistic or
similarity-based scoring — that map directly onto the alert-grouping problem.

### 2.3 Need / necessity

Regulators and internal audit functions demand clear lineage from the originating alert
to the final disposition. Manual grouping does not scale with rising digital-payment
volumes and real-time payment rails, and it introduces compliance risk when the audit
trail is thin. Automated, auditable case management is a core, recurring deliverable in
risk-advisory and bank-technology engagements.

### 2.4 Why / How / When / Where / Who

- **Why.** To reduce analyst workload, improve consistency of investigation and
  disposition, and create defensible, regulator-ready investigation records.
- **How.** API-driven ingestion → deterministic + similarity-based grouping → canonical
  case creation → case lifecycle management with assignment, notes, and attachments →
  immutable audit log → investigator UI. Everything containerised with seed data.
- **When.** Immediately relevant. Alert volumes continue to rise with digital and
  real-time payments; the audit expectation is already in force.
- **Where.** Deployable as an internal tool or demonstration system for fraud
  operations, financial-crime compliance, and risk-technology teams.
- **Who.** Risk-advisory consultants, bank fraud-operations teams, financial-crime units,
  and the technology teams that support them.

### 2.5 Solution overview

A single backend service ingests alerts (individually and in bulk), applies a
configurable grouping engine, and produces canonical **cases**. Analysts work cases
through a defined lifecycle in a lightweight investigator UI: they are assigned work,
review grouped alerts, add notes, attach supporting documents, request more information,
and record a disposition. Every state change is written to an append-only audit log with
full before/after detail. Admins configure grouping rules, manage users and roles, and
monitor system health. The whole system runs from a single `docker compose up` with
realistic synthetic data.

---

## 3. Goals & Non-Goals

### 3.1 Objectives and success measures

| # | Objective | Success measure (on synthetic benchmark) |
|---|---|---|
| O1 | Automatically group duplicate/related alerts into cases | ≥ 90% pairwise grouping F1 against ground-truth groups; false-merge rate ≤ 2% |
| O2 | Reduce manual grouping effort | ≥ 60% reduction in alerts an analyst must open individually vs. an ungrouped baseline |
| O3 | Produce a complete, immutable audit trail | 100% of state-changing actions produce an audit event; zero successful mutations or deletions of audit records in testing |
| O4 | Provide an efficient investigation workflow | A case can be triaged, investigated, and dispositioned end-to-end in the UI without leaving the app; median analyst clicks-to-disposition tracked |
| O5 | Be trivially deployable and reproducible | `docker compose up` yields a working system with seed data in under 5 minutes on a developer laptop |
| O6 | Make grouping logic transparent and tunable | Every grouping decision exposes the rule(s) and score that produced it; rules are changeable via config without code changes |

### 3.2 Non-goals (explicitly out of scope for v1)

- Ingesting real customer or transaction data; only synthetic data is used.
- Filing or drafting SARs/STRs or any regulatory report.
- Real-time streaming ingestion (Kafka/Kinesis). Ingestion is request/response and batch.
- Training machine-learning models or maintaining an ML pipeline. Similarity scoring uses
  deterministic, explainable features and configurable weights.
- Sanctions / watchlist screening, PEP screening, or KYC onboarding.
- Multi-tenancy, SSO/SAML/OIDC federation, and fine-grained attribute-based access
  control. v1 ships simple RBAC (Analyst / Admin) with a clean extension path.
- A configurable no-code workflow designer. The case lifecycle is fixed in v1.
- Native mobile applications.
- High-availability / multi-region deployment. v1 targets a single-node deployment.

---

## 4. Personas & Stakeholders

| Persona | Role in the system | Primary needs | v1 system role |
|---|---|---|---|
| **Fraud / AML Analyst ("Alex")** | Front-line investigator | A prioritised queue; grouped alerts so they review an event once; fast note-taking; clear next actions | Analyst |
| **Senior Investigator ("Sam")** | Handles complex/escalated cases; QA | Ability to merge/split cases the engine got wrong; visibility into grouping rationale; review other analysts' work | Analyst (with merge/split) |
| **Team Lead / Ops Manager ("Morgan")** | Runs the queue; assigns work; owns SLAs | Workload distribution; SLA/aging visibility; throughput and quality metrics | Analyst + reporting; assignment |
| **Financial Crime Compliance / Internal Audit ("Riley")** | Second line / assurance | Complete, immutable lineage from alert to disposition; exportable audit evidence; confidence that logic is documented and controlled | Read-only + audit export (Admin-granted) |
| **System Administrator ("Devin")** | Operates the deployment | Configure grouping rules; manage users/roles; monitor health and metrics; manage retention | Admin |
| **Data Protection Officer** | Governance stakeholder (not a daily user) | Assurance on PII handling, retention, and access logging | Consulted; requirements source |
| **Upstream system owners (TMS / fraud engine)** | Integrators | A stable, documented alert schema and idempotent ingestion | API consumer |

---

## 4a. Data Sources & Ingestion

### 4a.1 Real-world upstream sources (contextual — the system is designed to accept these)

| Source category | Examples | Signal contributed |
|---|---|---|
| Transaction-monitoring / AML rules engines | NICE Actimize, SAS AML, Oracle Mantas, Verafin, in-house rules | Typology alerts (structuring, rapid movement, unusual counterparty) |
| Fraud-scoring / real-time decisioning | Card-not-present scoring, account-takeover models, first-party fraud models | Scored fraud alerts with risk score and reason codes |
| Payment processor / card network notifications | Chargeback feeds, Visa TC40 / Mastercard SAFE fraud reports | Confirmed or reported fraud on specific transactions |
| Device & network intelligence | Device fingerprinting, IP reputation / geolocation | Device ID, IP, velocity signals used for grouping |
| Enrichment reference data (read-only, not an alert source) | Customer / KYC master, merchant registry, device registry | Attributes for search, filtering, and grouping context |

Each upstream system is expected to map its native alert format to the **canonical Alert
schema** (Appendix A). The system does not connect directly to any of the above in v1.

### 4a.2 In-scope data inputs (what the system actually ingests)

1. **Canonical Alert schema.** A documented JSON contract covering identity
   (`external_alert_id`, `source_system`), event data (`event_time`, `amount`,
   `currency`, `direction`), entities (`customer_id`, `account_id`, `counterparty`,
   `merchant`, `mcc`), technical context (`device_id`, `ip_address`,
   `session_id`), risk (`risk_score`, `rule_codes[]`, `typologies[]`), and a free-form
   `raw_payload` for provenance. Full field list in Appendix A.
2. **Push ingestion (API).** Single-alert and bulk (array / NDJSON) endpoints, protected
   by an idempotency key (Section 6.1).
3. **Batch ingestion (file drop).** CSV, JSON, or JSONL files submitted via an upload
   endpoint or a watched directory; processed by an async loader through the *same*
   validation and grouping path as API ingestion. Per-row outcomes are reported.
4. **Synthetic alert generator.** A CLI/module that produces realistic, tunable datasets:
   configurable number of true event clusters; controllable time jitter, amount jitter,
   and shared `device_id` / `ip_address` / `merchant`; injected noise/singletons; and a
   `ground_truth_group_id` on every alert for offline accuracy measurement. Used for seed
   data, demos, and the grouping benchmark.
5. **Synthetic enrichment datasets.** Customers, merchants, and devices, referenced by
   ID from alerts, to exercise search, filtering, and grouping context.

### 4a.3 Ingestion requirements summary

- All ingestion paths share one validation → normalisation → persistence → grouping
  pipeline. There is no path that bypasses validation or the audit log.
- Malformed alerts are rejected with a structured error (API) or quarantined with a
  reason (batch); they never partially apply.
- Ingestion is decoupled from grouping: an alert is persisted first, then grouped
  synchronously for single ingest or asynchronously (queued) for bulk/batch, so large
  loads do not block callers.
- Every ingested alert and every grouping decision is traceable back to its source and
  its idempotency key.

---

## 5. User Journeys

### 5.1 Primary journey — alert to disposition

1. **Ingest.** An upstream TMS posts a batch of 50 alerts with an idempotency key. The
   system validates and persists them, then enqueues grouping.
2. **Group.** The grouping engine blocks candidates by shared customer/account within a
   72-hour window, scores each candidate pair, and assigns alerts to cases. 50 alerts
   collapse into 11 cases; 3 cases carry ≥ 4 alerts each. Each grouping decision records
   the matched rule(s) and score.
3. **Triage.** Morgan (Team Lead) sees 11 new cases in the queue, sorted by aggregate
   risk score and oldest alert age. Morgan assigns the 3 high-risk cases to Alex.
4. **Investigate.** Alex opens a case, sees all 4 alerts, the shared device and merchant,
   a timeline, and the enrichment context. Alex moves the case to *In Progress*, adds a
   note, and attaches a PDF of the customer's dispute statement (its text is extracted
   and indexed).
5. **Request info.** Alex needs the merchant's response, moves the case to *Pending
   Info*, and records why. The SLA timer for active work pauses.
6. **Resolve.** Two days later the info arrives; Alex moves the case back to *In
   Progress*, then to *Closed* with disposition *Confirmed fraud* and a summary rationale.
7. **Audit.** Riley (Audit) later opens the case and exports its full audit trail: every
   state change, note, attachment, assignment, and the grouping rationale, each with
   actor, timestamp, reason, and before/after values.

### 5.2 Secondary journey — engine got the grouping wrong

- **False merge.** Sam notices a case contains alerts for two unrelated customers. Sam
  **splits** the case, choosing which alerts move to a new case and recording a reason.
  Both the original and new case get audit events; the grouping engine records that a
  human override now pins these alerts apart.
- **Missed link.** Alex finds two separate cases that are clearly the same event and
  **force-merges** them, selecting the surviving canonical case and recording a reason.
  Notes and attachments are carried over; the merge is fully audited and reversible via a
  subsequent split.

### 5.3 Administration journey

- Devin adjusts the amount-tolerance on the "same disputed transaction" rule from 0% to
  ±1% via the rules config, runs the grouping benchmark to confirm F1 did not regress,
  and re-runs grouping for the affected open cases. The config change is itself audited.

---

## 6. Functional Requirements

Requirements use MoSCoW priority (**M**ust / **S**hould / **C**ould / **W**on't-in-v1).
Each has acceptance criteria. IDs are stable references for the implementation plan and
test matrix.

### 6.1 Ingestion

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-ING-01 | M | Accept a single alert via `POST /api/v1/alerts` conforming to the canonical schema | Valid alert returns `201` with the created alert ID and its assigned case ID (or `202` if grouping is deferred); invalid alert returns `422` with per-field errors and creates nothing |
| FR-ING-02 | M | Accept bulk alerts via `POST /api/v1/alerts:batch` (JSON array or NDJSON) | Response reports per-item status (created / duplicate / rejected with reason); a single bad item does not fail the batch; batch grouping is enqueued, not synchronous |
| FR-ING-03 | M | Support an idempotency key on all ingestion requests (`Idempotency-Key` header and/or per-alert `external_alert_id` + `source_system`) | Re-submitting the same key within the retention window returns the original result and does not create a duplicate alert; keys are retained ≥ 7 days in Valkey with a Postgres backstop |
| FR-ING-04 | M | Validate and normalise every alert (currency codes, timestamps to UTC, amount precision, enum values) before persistence | Normalisation is deterministic and recorded; original values are preserved in `raw_payload` |
| FR-ING-05 | S | Accept batch file uploads (CSV / JSON / JSONL) via `POST /api/v1/imports` | Returns an import job ID; job status endpoint reports progress and a downloadable per-row outcome report; rows route through the same validation as FR-ING-04 |
| FR-ING-06 | S | Provide a synthetic alert generator with tunable duplication, jitter, noise, and ground-truth labels | Generator produces a dataset and a manifest; documented parameters; used by seed data and the grouping benchmark |
| FR-ING-07 | C | Watched-directory ingestion for batch files | Files dropped in a configured location are picked up, processed, and moved to `processed/` or `failed/` with a report |
| FR-ING-08 | M | Reject or quarantine malformed input without partial application | No alert is ever half-created; rejected API items return structured errors; quarantined batch rows are retrievable with reasons |

### 6.2 Grouping & Deduplication

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-GRP-01 | M | Assign every ingested alert to exactly one case (a new single-alert case if nothing matches) | No alert is ever caseless after grouping completes; a singleton alert yields a valid case |
| FR-GRP-02 | M | Apply configurable **deterministic** grouping rules: shared key(s) (customer, account, counterparty, device, IP, merchant+amount) within a configurable time window, with amount tolerance | Rules are defined in config (Section 10); changing a rule requires no code change; each rule has an ID, enabled flag, keys, window, tolerance, and weight |
| FR-GRP-03 | M | Apply a **configurable similarity score** to candidate pairs that share a blocking key but do not match a deterministic rule outright; group when the score ≥ a configurable threshold | Score is a weighted, explainable combination of feature similarities (time proximity, amount proximity, string similarity on merchant/counterparty, device/IP equality); the exact score and contributing features are stored on the grouping decision |
| FR-GRP-04 | M | Record, for every alert-to-case assignment, the rule ID(s) and/or similarity score that caused it, plus the engine version and config hash | The grouping rationale is visible in the API and UI for any alert; two runs with the same config and data produce the same grouping (determinism) |
| FR-GRP-05 | M | Create a **canonical case** when multiple candidate cases are found for an alert set: choose a deterministic survivor (e.g. earliest-created, then lowest ID) and merge the rest | Merge preserves all alerts, notes, attachments, and audit history; a merge produces audit events on all affected cases |
| FR-GRP-06 | S | Support re-running grouping for a set of open cases after a config change, without disturbing closed cases or human overrides | Re-group is an explicit, audited admin action; closed cases and pinned overrides (FR-OVR-03) are never altered |
| FR-GRP-07 | S | Compute and expose an aggregate case **risk score** derived from its alerts (configurable aggregation: max / sum-capped / weighted) | Risk score updates when alerts are added or removed; aggregation method is config-driven |
| FR-GRP-08 | C | Provide an offline **grouping benchmark** that scores the engine against `ground_truth_group_id` (precision, recall, F1, false-merge rate) | Runnable via CLI against any generated dataset; outputs a report; used in CI to catch regressions |
| FR-GRP-09 | W | Machine-learned matching model | Deferred; v1 uses explainable weighted features only |

### 6.3 Manual Override (Merge / Split / Re-group)

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-OVR-01 | M | Force-merge two or more cases into one chosen canonical case, with a mandatory reason | All alerts/notes/attachments move to the survivor; non-survivors become `Merged` and are read-only; audit events on all cases; only Analyst+ can do this |
| FR-OVR-02 | M | Split a case: move a selected subset of alerts to a new case, with a mandatory reason | Both cases remain valid and non-empty; notes/attachments stay with the original unless explicitly moved; audit events on both cases |
| FR-OVR-03 | M | A human merge or split **pins** the affected alerts (keeps-together / keeps-apart) so future automated re-grouping cannot undo it | Re-group (FR-GRP-06) respects pins; pins are visible and individually removable by an Analyst+ with a reason |
| FR-OVR-04 | S | Reverse a merge by splitting back out the previously merged alerts | The system retains enough lineage to reconstruct pre-merge case boundaries; reversal is audited |
| FR-OVR-05 | S | Move a single alert from one existing case to another | Guardrails prevent emptying a case without closing it; audited |

### 6.4 Case Lifecycle & Workflow

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-CASE-01 | M | Cases follow the fixed lifecycle: **Open → In Progress → Pending Info → Closed**, plus terminal `Merged` | Allowed transitions are enforced server-side; `Pending Info` can only be entered from `In Progress` and returns to `In Progress`; `Closed` requires a disposition; illegal transitions return `409` |
| FR-CASE-02 | M | Closing a case requires a disposition from a configurable set (e.g. *No action*, *Escalate*, *Confirmed fraud*, *Confirmed AML concern*, *Duplicate*) and a rationale note | Cannot close without both; disposition and rationale appear in the audit trail and case header |
| FR-CASE-03 | M | Re-open a closed case (Analyst+), with a reason, returning it to `In Progress` | Re-open is audited; re-open count is tracked and reportable (quality signal) |
| FR-CASE-04 | M | Assign / reassign a case to a user; support "assign to me" and bulk assign from the queue | Assignment is audited (from → to); unassigning is allowed; assignment does not change case state |
| FR-CASE-05 | S | SLA timers: track time-in-state and total case age; `Pending Info` pauses the "active work" timer; surface breached/at-risk cases | SLA thresholds are configurable; queue and case views show age and SLA status; no hard enforcement (advisory in v1) |
| FR-CASE-06 | S | Prevent conflicting concurrent edits (optimistic concurrency) | State-changing requests carry a version/ETag; a stale write returns `409` with the current state |
| FR-CASE-07 | C | Watchers / subscribers on a case receive an in-app activity feed | Users can follow a case they are not assigned to and see its activity |

### 6.5 Collaboration — Notes & Attachments

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-COL-01 | M | Add free-text notes/comments to a case; notes are immutable once saved (append-only), attributed, and timestamped | Notes cannot be edited or hard-deleted; a note may be marked `retracted` (still visible, struck through) with a reason; all captured in audit |
| FR-COL-02 | M | Attach supporting files to a case (PDF, PNG/JPG, CSV, TXT, EML), stored in object storage | File size and type limits enforced; stored with checksum; download is access-controlled and audited; original filename and uploader retained |
| FR-COL-03 | S | Extract text from PDF attachments and index it for case search | On upload, PDF text is extracted (PyMuPDF, pdfplumber fallback) and made searchable within the case; extraction failures are recorded, not fatal |
| FR-COL-04 | S | Virus/type sanity checks on upload (magic-byte check; optional ClamAV hook) | Files whose content does not match their declared type are rejected; hook point documented for AV in production |
| FR-COL-05 | C | Link related cases to each other with a typed relationship (`duplicate-of`, `related-to`) | Relationships are visible on both cases and audited |

### 6.6 Immutable Audit Log

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-AUD-01 | M | Every state-changing action writes an audit event capturing: actor (user ID + role), action type, target entity + ID, timestamp (UTC), request/correlation ID, human-readable reason (where the action requires one), and structured **before** and **after** values | 100% of mutating endpoints produce an audit event in tests; a mutation that fails to audit fails the transaction |
| FR-AUD-02 | M | Audit records are **append-only**: no update or delete path exists in the application, and the database role used by the app lacks `UPDATE`/`DELETE` on the audit table | Attempted update/delete via the app is impossible by construction; a DB-level test confirms the grant restriction |
| FR-AUD-03 | M | Audit events are **hash-chained**: each event stores the hash of the previous event for its stream, making silent tampering detectable | A verification job recomputes the chain and reports any break; documented as tamper-*evidence*, not tamper-proofing |
| FR-AUD-04 | M | Query the audit trail by case, by actor, by time range, and by action type | Results are paginated, ordered, and filterable; accessible to Audit/Admin roles |
| FR-AUD-05 | M | Export a case's complete audit trail (and its notes/attachment metadata) as a single human-readable file (PDF or HTML) and as JSON | Export is itself an audited action; the exported document is self-contained and includes the grouping rationale |
| FR-AUD-06 | S | Ingestion and grouping decisions are represented in the audit/lineage view for a case | From any case, a reviewer can trace each alert back to its source, idempotency key, and the rule/score that grouped it |
| FR-AUD-07 | S | Configuration changes (grouping rules, dispositions, SLA thresholds, roles) are audited with before/after | Changing any config value produces an audit event attributed to the admin |

### 6.7 Search & Filtering

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-SRCH-01 | M | List and filter cases by: status, disposition, assignee (incl. unassigned), created/updated/closed date range, risk-score range, source system, typology | Filters combine (AND); results paginated and sortable; response time meets NFR-PERF-02 |
| FR-SRCH-02 | M | Full-text search across case ID, alert external IDs, customer/account/merchant identifiers, note text, and extracted attachment text | Uses Postgres full-text search; ranked results; highlights matched fields |
| FR-SRCH-03 | S | Saved views / filters per user (e.g. "My open high-risk cases") | Users can save, name, and re-run filter sets |
| FR-SRCH-04 | S | Queue view with default prioritisation (risk score desc, then oldest alert age) and one-click claim | Team Lead and Analyst queue views; claiming assigns to the current user and is audited |

### 6.8 Investigator Dashboard (UI)

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-UI-01 | M | Case **list view**: filters (FR-SRCH-01), columns for status, assignee, risk, alert count, age/SLA; pagination; sort | Loads and filters without full-page reloads; reflects server state |
| FR-UI-02 | M | Case **detail view**: header (status, disposition, assignee, risk, SLA), grouped alerts with per-alert grouping rationale, event timeline, notes thread, attachments, audit tab | All v1 case actions (transition, assign, note, attach, merge, split, export) are reachable from this view |
| FR-UI-03 | M | Alert-level drill-down showing the canonical fields and the raw payload | Analyst can see exactly what the upstream system sent |
| FR-UI-04 | S | Admin screens: grouping-rule config editor (with validation and a "test against benchmark" action), user & role management, disposition/SLA settings | Admin-only; every save is audited; invalid config is rejected with a clear message |
| FR-UI-05 | S | Basic operational dashboard: open/closed counts, aging buckets, dedup ratio, re-open rate, throughput per analyst | Read-only; served from the metrics/reporting endpoints |
| FR-UI-06 | M | The UI enforces the same RBAC as the API (controls for actions a user cannot perform are hidden or disabled) | A read-only user sees no mutating controls; server still enforces regardless of UI |
| FR-UI-07 | C | Keyboard-first triage flow (next case, set state, add note, next) | Documented shortcuts; measured against O4 |

The primary UI is **React + TypeScript**. A **HTMX + Jinja2** alternative delivering
FR-UI-01/02/03/06 is documented for lean-team builds (Section 11.5).

### 6.9 Access Control (RBAC)

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-RBAC-01 | M | Two built-in roles: **Analyst** (triage, investigate, note, attach, merge/split, close/re-open, export) and **Admin** (all Analyst actions + user/role management + grouping config + retention) | Enforced server-side on every endpoint; documented permission matrix (Appendix C) |
| FR-RBAC-02 | M | A **read-only / audit** capability (assignable by Admin) that permits viewing everything and exporting audit trails but no mutations | A read-only principal receives `403` on every mutating endpoint |
| FR-RBAC-03 | M | Authentication via signed tokens (JWT) issued by a local auth endpoint; passwords hashed with a modern KDF (argon2/bcrypt) | Tokens expire; refresh flow defined; no plaintext secrets at rest |
| FR-RBAC-04 | S | Service-to-service ingestion uses API keys distinct from user credentials, scoped to ingestion endpoints only | An ingestion key cannot read cases or the audit log |
| FR-RBAC-05 | C | Pluggable auth: documented seam for swapping local auth for OIDC/SAML later | Interface boundary identified; no implementation in v1 |

### 6.10 Observability & Operations

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-OPS-01 | M | `GET /healthz` (liveness) and `GET /readyz` (readiness incl. DB and Valkey) | `readyz` returns `503` with component detail when a dependency is down |
| FR-OPS-02 | M | `GET /metrics` in Prometheus format: ingestion rate, grouping latency, cases by state, queue depth, audit-write failures (should be zero), HTTP latencies | Scrapeable; key business and technical metrics present |
| FR-OPS-03 | M | Structured JSON logs (structlog) with correlation IDs propagated from ingestion through grouping and case actions | A single request or alert can be traced across services by correlation ID |
| FR-OPS-04 | S | Seed-data command that loads a realistic synthetic dataset (alerts, resulting cases, a few worked examples, users) | `make seed` / documented command; idempotent; produces a demo-ready state |
| FR-OPS-05 | S | Data-retention job: archive/purge cases and audit records older than a configurable period, with a dry-run mode | Purge is itself audited (a retention manifest); dry-run lists what would be affected |
| FR-OPS-06 | C | OpenTelemetry traces exported to a local collector in the compose stack | Optional profile in docker-compose |

---

## 7. Non-Functional Requirements

### 7.1 Auditability & data integrity

| ID | Requirement |
|---|---|
| NFR-AUD-01 | The audit log is the system's integrity backbone: append-only at the application layer, `UPDATE`/`DELETE` revoked at the DB-grant layer for the app role, hash-chained per stream, and independently verifiable. |
| NFR-AUD-02 | Every mutation and its audit event commit in the **same database transaction**. If the audit write fails, the mutation rolls back. |
| NFR-AUD-03 | Notes are append-only; attachments are immutable (content-addressed by checksum); "deletion" is always a soft state with a retained reason. |
| NFR-AUD-04 | System clocks are UTC; all timestamps are stored with timezone; the app records both event time (from the alert) and system-received time. |
| NFR-AUD-05 | Grouping is deterministic and reproducible: identical input data + config hash + engine version ⇒ identical case grouping. |

### 7.2 Security & privacy

| ID | Requirement |
|---|---|
| NFR-SEC-01 | All traffic over TLS (terminated at a reverse proxy in the compose stack); no service exposes an unauthenticated mutating endpoint. |
| NFR-SEC-02 | RBAC enforced server-side on every endpoint; the UI never the sole gate. Default-deny. |
| NFR-SEC-03 | Secrets (DB, Valkey, JWT signing key; object-storage credentials arrive at Phase 2) come from environment/secret files, never source control; `.env.example` documents them. |
| NFR-SEC-04 | Synthetic data only. The data model treats customer/account identifiers as pseudonymous references; there is no name/address/DOB storage in v1. Field-level notes mark where real PII would land so production hardening is scoped. |
| NFR-SEC-05 | Every read of an attachment or an audit export is itself logged (access logging), attributed, and time-stamped. |
| NFR-SEC-06 | Dependency scanning (pip-audit) and container image scanning run in CI; copyleft components (PyMuPDF, pdfplumber, and Garage — all Phase 2) are documented with their obligations (Appendix E); none sit on the MVP critical path. |
| NFR-SEC-07 | Input is validated and size-limited on every endpoint; file uploads are type-checked by content, not extension. |
| NFR-SEC-08 | Rate limiting on ingestion and auth endpoints (Valkey-backed). |

### 7.3 Performance & scale (targets for a single-node reference deployment)

| ID | Requirement |
|---|---|
| NFR-PERF-01 | Sustained ingestion of **100,000 alerts/day** (~70/min average, bursts to 500/min) without backlog growth on a 4-vCPU / 8 GB host. |
| NFR-PERF-02 | Case list/filter queries return in **< 800 ms p95** at 250,000 cases / 1,000,000 alerts. |
| NFR-PERF-03 | Single-alert ingest (incl. synchronous grouping against a candidate set) responds in **< 500 ms p95**. |
| NFR-PERF-04 | Bulk ingest of 10,000 alerts is fully grouped within **10 minutes**; caller gets an immediate `202` with a job handle. |
| NFR-PERF-05 | Grouping cost is sub-quadratic in dataset size through blocking; the candidate set for any alert is bounded (configurable cap, default 500) with overflow logged. |

### 7.4 Reliability & availability

| ID | Requirement |
|---|---|
| NFR-REL-01 | Target single-node availability 99% (business-hours operation assumed); documented backup/restore for Postgres (the only stateful store in the MVP). |
| NFR-REL-02 | Ingestion is crash-safe: an alert accepted (`201`/`202`) is durably persisted before the response; grouping jobs are retried with idempotency on worker restart. |
| NFR-REL-03 | Graceful degradation: if the object store is down, case work continues; only attachment upload/download is blocked, and this is surfaced via `readyz`. |
| NFR-REL-04 | Migrations are versioned (Alembic), forward-only in normal operation, and run automatically on container start behind a lock. |

### 7.5 Maintainability, portability, and quality

| ID | Requirement |
|---|---|
| NFR-MNT-01 | `git clone` → `docker compose up` → working system with seed data in **< 5 minutes**, no manual steps beyond copying `.env.example`. |
| NFR-MNT-02 | The grouping engine is an isolated module with a documented interface (`group(alerts, config) -> decisions`), unit-testable without a database. |
| NFR-MNT-03 | Test coverage: ≥ 85% line coverage on the backend; every FR-* has at least one automated test; service-container integration tests for Postgres and Valkey. |
| NFR-MNT-04 | API is versioned under `/api/v1`; the canonical Alert schema is published as JSON Schema / OpenAPI and treated as a contract. |
| NFR-MNT-05 | Code style enforced (ruff, black, mypy for the backend; eslint, prettier, tsc for the frontend) in CI. |
| NFR-MNT-06 | All configuration (grouping rules, dispositions, SLA thresholds, limits) is externalised to files/env; no business thresholds hard-coded. |

### 7.6 Usability & accessibility

| ID | Requirement |
|---|---|
| NFR-UX-01 | Investigator UI targets WCAG 2.1 AA for the core triage and case-detail flows (contrast, keyboard navigation, focus order, form labels). |
| NFR-UX-02 | Every destructive or hard-to-reverse action (merge, split, close, retention purge) requires explicit confirmation and a reason. |
| NFR-UX-03 | UI copy is externalised for future i18n; dates/numbers/currency render locale-aware. |
| NFR-UX-04 | Empty, loading, and error states are designed for every primary view. |

---

## 8. Data Model (Recommended)

Persisted in **PostgreSQL 16** via **SQLAlchemy 2.0**, migrations via **Alembic**. Core
entities and key fields (not exhaustive):

| Entity | Key fields | Notes |
|---|---|---|
| **Alert** | `id` (uuid), `external_alert_id`, `source_system`, `idempotency_key`, `event_time`, `received_at`, `amount`, `currency`, `direction`, `customer_ref`, `account_ref`, `counterparty_ref`, `merchant_name`, `mcc`, `device_id`, `ip_address`, `session_id`, `risk_score`, `rule_codes` (jsonb), `typologies` (jsonb), `raw_payload` (jsonb), `ground_truth_group_id` (nullable, synthetic only), `case_id` (fk) | Unique on (`source_system`, `external_alert_id`); immutable after normalisation |
| **Case** | `id` (uuid), `human_ref` (short code), `status`, `disposition` (nullable), `assignee_id` (fk, nullable), `risk_score`, `alert_count`, `created_at`, `updated_at`, `closed_at` (nullable), `canonical_from_case_id` (nullable, for merged), `version` (int, optimistic lock) | `status` ∈ {Open, In Progress, Pending Info, Closed, Merged} |
| **CaseAlertLink** | `case_id` (fk), `alert_id` (fk), `linked_at`, `linked_by` (system/user), `grouping_decision_id` (fk) | Association with provenance |
| **GroupingDecision** | `id`, `alert_id` (fk), `case_id` (fk), `method` (deterministic/similarity/manual), `matched_rule_ids` (jsonb), `similarity_score` (nullable), `feature_contributions` (jsonb), `engine_version`, `config_hash`, `created_at` | The "why" behind every link |
| **GroupingRule** (config, versioned) | `id`, `name`, `enabled`, `blocking_keys` (jsonb), `time_window_seconds`, `amount_tolerance`, `match_predicate`, `weight`, `effective_from`, `created_by` | Stored so changes are auditable; loaded into the engine |
| **AlertPin** | `id`, `alert_id_a` (fk), `alert_id_b` (fk), `kind` (keep_together/keep_apart), `reason`, `created_by`, `created_at`, `active` | Human overrides that constrain re-grouping |
| **Note** | `id`, `case_id` (fk), `author_id` (fk), `body`, `created_at`, `retracted` (bool), `retraction_reason` (nullable) | Append-only; no update/delete |
| **Attachment** | `id`, `case_id` (fk), `uploader_id` (fk), `filename`, `content_type`, `size_bytes`, `sha256`, `object_key` (object store), `extracted_text` (nullable), `extraction_status`, `created_at` | Content in object storage; row is metadata |
| **AuditEvent** | `id` (bigserial), `stream` (e.g. `case:{id}`), `seq` (per stream), `prev_hash`, `hash`, `actor_id` (nullable for system), `actor_role`, `action`, `target_type`, `target_id`, `reason` (nullable), `before` (jsonb), `after` (jsonb), `correlation_id`, `created_at` | Append-only; app DB role has no UPDATE/DELETE; hash-chained per stream |
| **User** | `id`, `email`, `display_name`, `password_hash`, `is_active`, `created_at` | Local auth in v1 |
| **Role / UserRole** | `role` ∈ {analyst, admin, readonly}; `user_id` (fk), `role` | Simple RBAC; permission matrix in Appendix C |
| **ApiKey** | `id`, `label`, `hashed_key`, `scope` (`ingest`), `is_active`, `created_at` | Service ingestion credentials |
| **ImportJob** | `id`, `filename`, `format`, `status`, `total_rows`, `created_rows`, `duplicate_rows`, `failed_rows`, `report_object_key`, `created_by`, `created_at` | Batch ingestion tracking |
| **SavedView** | `id`, `user_id` (fk), `name`, `filter_json` | Per-user filters |

Indexing highlights: `alert(event_time)`, `alert(customer_ref, event_time)`,
`alert(device_id)`, `alert(ip_address)`, GIN on `alert.rule_codes` / full-text columns,
`case(status, risk_score)`, `case(assignee_id, status)`, `audit_event(stream, seq)`.

An ER diagram is included as `docs/diagrams/er-model.md` (to be produced with the design).

---

## 9. API Surface (Recommended)

**FastAPI**, JSON, versioned under `/api/v1`, OpenAPI published at `/api/v1/openapi.json`.
Auth: `Authorization: Bearer <jwt>` for users; `X-API-Key` for ingestion services.

### 9.1 Resource summary

| Method & path | Purpose | Roles |
|---|---|---|
| `POST /api/v1/auth/token` | Obtain a JWT | public (credentials) |
| `POST /api/v1/auth/refresh` | Refresh a JWT | authenticated |
| `POST /api/v1/alerts` | Ingest one alert | ingest key / admin |
| `POST /api/v1/alerts:batch` | Ingest many alerts (array / NDJSON) | ingest key / admin |
| `GET /api/v1/alerts/{id}` | Retrieve an alert incl. grouping rationale | analyst+ |
| `POST /api/v1/imports` | Upload a batch file (CSV/JSON/JSONL) | analyst+ |
| `GET /api/v1/imports/{id}` | Import job status + report link | analyst+ |
| `GET /api/v1/cases` | List/filter/search cases (query params per FR-SRCH-01/02) | analyst+ / readonly |
| `GET /api/v1/cases/{id}` | Case detail (alerts, notes, attachments, SLA, rationale) | analyst+ / readonly |
| `POST /api/v1/cases/{id}/transition` | Change status (`{to, reason, disposition?}`) | analyst+ |
| `POST /api/v1/cases/{id}/assign` | Assign/reassign/unassign (`{assignee_id | null}`) | analyst+ |
| `POST /api/v1/cases/{id}/notes` | Add a note | analyst+ |
| `POST /api/v1/cases/{id}/notes/{noteId}/retract` | Retract a note (`{reason}`) | author / admin |
| `POST /api/v1/cases/{id}/attachments` | Upload an attachment (multipart) | analyst+ |
| `GET /api/v1/cases/{id}/attachments/{attId}` | Download an attachment (audited) | analyst+ / readonly |
| `POST /api/v1/cases:merge` | Force-merge (`{case_ids[], canonical_case_id, reason}`) | analyst+ |
| `POST /api/v1/cases/{id}:split` | Split (`{alert_ids[], reason}`) → new case | analyst+ |
| `POST /api/v1/cases/{id}/pins` | Pin alerts keep-together / keep-apart | analyst+ |
| `GET /api/v1/cases/{id}/audit` | Case audit trail | readonly+ |
| `POST /api/v1/cases/{id}/audit:export` | Export audit trail (PDF/HTML/JSON), audited | readonly+ |
| `GET /api/v1/audit` | Cross-entity audit query (actor/time/action filters) | admin / readonly-audit |
| `POST /api/v1/audit:verify` | Recompute and verify hash chains | admin |
| `GET /api/v1/grouping/rules` / `PUT /api/v1/grouping/rules` | Read/update grouping config (audited) | admin |
| `POST /api/v1/grouping/regroup` | Re-run grouping for open cases (`{scope, reason}`) | admin |
| `POST /api/v1/grouping/benchmark` | Run the benchmark against a dataset | admin |
| `GET /api/v1/reports/overview` | Operational metrics for the dashboard | analyst+ |
| `GET /api/v1/users` / `POST` / `PATCH` | User & role management | admin |
| `GET /healthz` `GET /readyz` `GET /metrics` | Ops endpoints | infra |

### 9.2 Selected request/response examples

**Idempotent single ingest**

```
POST /api/v1/alerts
X-API-Key: <key>
Idempotency-Key: 9f1c-tms-batch-2026-08-30-000123

{
  "external_alert_id": "TMS-000123",
  "source_system": "aml-rules-engine",
  "event_time": "2026-08-30T09:14:22Z",
  "amount": 4980.00,
  "currency": "USD",
  "direction": "outbound",
  "customer_ref": "CUST-55021",
  "account_ref": "ACCT-99013",
  "counterparty_ref": "CP-13322",
  "merchant_name": "QuickCash LLC",
  "mcc": "6051",
  "device_id": "DEV-aa93f2",
  "ip_address": "203.0.113.44",
  "risk_score": 78,
  "rule_codes": ["STRUCTURING_02", "RAPID_MOVEMENT_04"],
  "typologies": ["structuring"],
  "raw_payload": { "...": "verbatim upstream message" }
}

201 Created
{
  "alert_id": "b1e...",
  "case_id": "7c2...",
  "grouping": {
    "method": "deterministic",
    "matched_rule_ids": ["same-customer-72h"],
    "similarity_score": null,
    "engine_version": "1.0.0",
    "config_hash": "sha256:abcd..."
  }
}
```

Re-sending the same `Idempotency-Key` returns `200` with the identical body and creates nothing.

**Split a mis-grouped case**

```
POST /api/v1/cases/7c2...:split
Authorization: Bearer <jwt>

{ "alert_ids": ["a12...", "a13..."], "reason": "Alerts belong to unrelated customer CUST-55022; engine over-matched on shared IP." }

201 Created
{ "original_case_id": "7c2...", "new_case_id": "9d4...", "audit_event_ids": ["...", "..."] }
```

---

## 10. Grouping & Deduplication Design (Recommended)

### 10.1 Pipeline

```
ingest → normalise → BLOCK (cheap candidate generation)
       → SCORE candidate pairs (deterministic rules, then similarity)
       → RESOLVE alert → case (union-find over matched pairs, respecting pins)
       → CANONICALISE (merge candidate cases; pick deterministic survivor)
       → PERSIST GroupingDecision + audit
```

### 10.2 Blocking (candidate generation)

For each new alert, generate candidate alerts that share **at least one** blocking key
within the rule's time window. Default blocking keys: `customer_ref`, `account_ref`,
`counterparty_ref`, `device_id`, `ip_address`, and `(merchant_name_normalised, amount
bucket)`. Candidate sets are capped (default 500, configurable); overflow is logged as a
tuning signal. Blocking keeps grouping cost sub-quadratic (NFR-PERF-05). Implemented with
indexed SQL plus in-process set operations (Polars/DuckDB over the candidate frame).

### 10.3 Deterministic rules

A rule is: `{id, enabled, blocking_keys, time_window_seconds, amount_tolerance,
match_predicate, weight}`. If a candidate pair satisfies a rule's predicate outright
(e.g. *same `account_ref`, same amount within ±0%, within 24h*), the pair is grouped with
`method = deterministic` and the rule ID recorded. Starter rule set:

| Rule ID | Intent | Keys | Window | Tolerance |
|---|---|---|---|---|
| `same-txn-dispute` | Same disputed transaction surfaced by multiple rules | account_ref + amount + counterparty_ref | 24h | ±0% (config to ±1%) |
| `same-customer-72h` | Same customer, connected activity | customer_ref | 72h | n/a |
| `card-testing-burst` | Rapid low-value attempts, one device | device_id + amount bucket | 30m | ±10% |
| `shared-ip-session` | Coordinated activity from one IP/session | ip_address + session_id | 2h | n/a |
| `same-counterparty-window` | Repeated payments to one counterparty | counterparty_ref | 7d | n/a |

### 10.4 Similarity scoring (for candidates not matched by a deterministic rule)

Score = weighted sum of feature similarities, each in [0, 1], normalised by weight:

| Feature | Similarity function | Default weight |
|---|---|---|
| Time proximity | `exp(-Δt / τ)`, τ configurable per rule context | 0.20 |
| Amount proximity | `1 - min(1, |a−b| / max(a,b))` | 0.20 |
| Merchant / counterparty name | token-set ratio (RapidFuzz) | 0.20 |
| Device match | 1 if equal else 0 | 0.15 |
| IP match | 1 if equal else 0 | 0.10 |
| MCC / typology overlap | Jaccard over sets | 0.15 |

Group the pair when `score ≥ threshold` (default 0.72, configurable). Store the score and
per-feature contributions on the `GroupingDecision` so the UI can explain it
("Grouped at 0.81: merchant name 0.95, amount 0.9, time 0.7, device 0"). No ML; every
weight and threshold is in config and covered by the benchmark.

### 10.5 Resolution & canonicalisation

Matched pairs form an undirected graph; connected components (union-find) define the
grouping. `keep_apart` pins remove edges; `keep_together` pins add edges. When a
component spans multiple existing cases, the **survivor** is chosen deterministically
(earliest `created_at`, then lowest `id`); other cases are merged into it and marked
`Merged`. Closed cases are never auto-merged — such collisions raise a review flag
instead.

### 10.6 Configuration format

Rules, weights, thresholds, blocking keys, candidate cap, risk-score aggregation, and
disposition list live in a single versioned config (YAML in the repo, editable via the
admin API which persists versions to `GroupingRule` / settings tables). The engine
records the `config_hash` it ran under on every decision.

### 10.7 Tuning & evaluation

The synthetic generator labels every alert with `ground_truth_group_id`. The benchmark
(`POST /api/v1/grouping/benchmark` or CLI) reports pairwise precision/recall/F1, the
false-merge rate, and a confusion summary, per dataset. CI runs the benchmark on a fixed
dataset and fails the build on regression beyond a tolerance. Config changes in the admin
UI offer a one-click "test against benchmark" before saving.

### 10.8 Edge cases

- **Backdated alerts** arriving after their case closed → new single-alert case + review
  flag linking to the closed case.
- **Very large clusters** (e.g. a merchant-wide event) → cap alerts-per-case (default
  200) and spawn linked continuation cases.
- **Conflicting pins** (A keep_together B, B keep_apart A) → most recent pin wins; the
  conflict is surfaced.
- **Amount in mixed currencies** → no cross-currency amount match unless a converted
  amount is supplied; documented limitation.
- **Missing keys** (null device/IP) → those blocking keys simply don't fire for that alert.

---

## 11. Architecture (Prescriptive)

### 11.1 Component overview

| Component | Technology | Responsibility |
|---|---|---|
| **API service** | Python 3.11+, FastAPI, Pydantic v2, Uvicorn | All HTTP endpoints, auth, RBAC, request validation, orchestration |
| **Grouping engine** | Python module (in-process), Polars / DuckDB, RapidFuzz | Blocking, scoring, resolution, canonicalisation; pure function over (alerts, config) |
| **Worker** | ARQ on Valkey (Redis protocol) | Bulk/batch ingestion, async grouping jobs, re-group, exports, retention, PDF text extraction |
| **Primary database** | PostgreSQL 16 | System of record; audit table with restricted grants; full-text search |
| **Cache / queue / rate-limit** | Valkey 8 (Redis-protocol) | Idempotency-key store, ARQ broker, rate limiting, hot query cache |
| **Object storage** | *(Phase 2)* Garage | Case attachments, import reports — not in the MVP |
| **Document processing** | PyMuPDF (fitz) + pdfplumber fallback | Extract text from PDF attachments for search |
| **Frontend** | React + TypeScript + Vite + Tailwind CSS | Investigator dashboard (list, detail, admin, reports) |
| **Reverse proxy** | Caddy or nginx | TLS termination, routing UI + API |
| **Migrations** | Alembic | Schema versioning, auto-run on start behind an advisory lock |
| **Observability** | structlog, Prometheus client, optional OTel collector | Logs, metrics, traces |

### 11.2 Docker Compose topology

Services: `proxy` (Caddy — the only published ports, 80/443), `api`, `worker`,
`frontend` (one-shot: builds the SPA and publishes it to a shared volume the
proxy serves), `postgres`, `valkey`. A `seed` one-shot service runs migrations
and loads synthetic data. Object storage (`garage`) joins in Phase 2. The
`pgdata` named volume is the only stateful one; `.env` (from `.env.example`)
drives all credentials and tunables.

### 11.3 Key data-flow decisions

- **Persist-then-group.** Ingestion always persists the alert (durable) before grouping.
  Single ingest groups synchronously within the request (bounded candidate set); bulk and
  batch enqueue grouping jobs and return `202`.
- **Transactional audit.** Every mutation + its `AuditEvent` share one DB transaction
  (NFR-AUD-02). Audit rows are written by an application service that computes the
  per-stream `seq` and `prev_hash` under a row lock on the stream head.
- **Restricted DB role.** The app connects as a role granted `SELECT`/`INSERT` on
  `audit_event` but not `UPDATE`/`DELETE`; migrations run as a separate role.
- **Idempotency.** `Idempotency-Key` (or `source_system`+`external_alert_id`) is checked
  in Valkey first, then enforced by a unique DB constraint; the stored response is
  replayed on repeat.
- **Config hashing.** The grouping engine loads config at startup and on admin update,
  computes a `config_hash`, and stamps it on every `GroupingDecision`.

### 11.4 Security architecture

TLS at the proxy; JWT for users (short-lived + refresh), argon2 password hashing;
scoped API keys for ingestion; server-side RBAC dependency on every route; Valkey-backed
rate limits on `/auth/*` and `/alerts*`; upload content-type verification and size caps;
pip-audit + image scan in CI. Secrets only via env/secret files.

### 11.5 The lean alternative (HTMX + Jinja2)

For a small team, the frontend may instead be server-rendered with **Jinja2 templates +
HTMX** served directly by FastAPI, delivering the case list, case detail, triage actions,
and RBAC-aware controls (FR-UI-01/02/03/06). Admin and reporting screens (FR-UI-04/05)
are simplified. This drops the Node build, Vite, and a separate frontend container. The
API contract is unchanged, so the React UI can be added later without backend changes.
The PRD treats React as the default and HTMX as a documented, supported downgrade.

### 11.6 Deployment (free, self-hostable)

The MVP is designed to run on a single node at zero infrastructure cost, with no
managed services. The reference deployment (`docker-compose.yml` + `DEPLOY.md`)
has two shapes:

- **Primary — self-host + Cloudflare Tunnel.** The stack runs on any Linux box
  the operator controls (≥ 2 vCPU / 4 GB). `cloudflared` dials out to Cloudflare,
  which terminates TLS at its edge and routes to the Caddy proxy on `:80`. **No
  inbound ports are opened.** Caddy runs HTTP-only.
- **Fallback — OCI Always Free Ampere A1** (4 OCPU / 24 GB, arm64). The same
  compose file; `SITE_ADDRESS` is set to a real domain and Caddy provisions a
  Let's Encrypt certificate automatically; the OCI security list opens only
  80/443. PostgreSQL runs as a self-hosted `postgres:16` container — Oracle
  Autonomous DB is **not** compatible with the async driver and migration SQL.

Every image (`postgres:16`, `valkey/valkey:8`, `caddy:2`, `node:22-alpine`,
`python:3.11-slim`) publishes a `linux/arm64` variant, so the Ampere A1 target
needs no changes. Migrations run explicitly (`docker compose run --rm api alembic
upgrade head`, or via the `seed` one-shot on first deploy) — there is no
auto-migrate on API start. The `pgdata` volume is the only stateful thing;
backup is a nightly `pg_dump` cron with 7-day retention. Valkey is cache/queue
only and safe to lose — because ingestion persists before grouping, a cold start
loses at most in-flight grouping jobs, recoverable by re-ingest or re-group.

---

## 12. Analytics & Success Metrics

| Metric | Definition | Target / use |
|---|---|---|
| **Deduplication ratio** | 1 − (cases created / alerts ingested), over a period | Higher is better; headline efficiency metric; shown on dashboard |
| **Grouping F1 (offline)** | Pairwise F1 vs. ground-truth on the benchmark dataset | ≥ 0.90; CI gate |
| **False-merge rate** | Fraction of grouped pairs that are wrong (offline) | ≤ 2%; CI gate |
| **Manual override rate** | Merges + splits per 100 cases | Tracked; a rising split rate signals over-grouping |
| **Case re-open rate** | Re-opened cases / closed cases | Quality signal; investigate if > 5% |
| **Median clicks-to-disposition** | UI interaction count from open to close | Proxy for workflow efficiency (O4) |
| **Time-in-state / case age** | Distribution per state; SLA breach count | Ops management |
| **Throughput per analyst** | Cases dispositioned per analyst per day | Capacity planning |
| **Audit completeness** | Mutations with a matching audit event / total mutations | Must be 100%; alert on any gap |
| **Audit-write failures** | Count of transactions rolled back due to audit-write failure | Must be 0; Prometheus alert |
| **Ingestion backlog** | Queue depth for grouping jobs | Should trend to 0; capacity signal |

---

## 13. Compliance & Audit Considerations

This system is designed to *support* an institution's obligations; it does not itself
discharge them. Design intent mapped to common expectations:

| Expectation (illustrative) | How the design responds |
|---|---|
| **Complete lineage from alert to disposition** (FFIEC BSA/AML exam expectations; internal audit) | Every alert links to a case via a `GroupingDecision` recording method, rule/score, engine version, and config hash; every case action is audited; a single export bundles the full trail (FR-AUD-05/06). |
| **Immutable, tamper-evident records** (SOX-style change control; evidentiary integrity) | Append-only audit table, DB-grant-enforced; per-stream hash chain with a verification endpoint (FR-AUD-02/03, NFR-AUD-01). |
| **Model / logic governance** (in the spirit of US Federal Reserve SR 11-7) | Grouping logic is fully explainable (no ML), version-controlled, config-hashed on every decision, and continuously benchmarked with a documented dataset; config changes are audited with before/after (FR-AUD-07). |
| **Segregation of duties & least privilege** | Server-side RBAC, default-deny; distinct ingestion API keys; separate DB roles for app vs. migrations (FR-RBAC-*, NFR-SEC-02). |
| **Access transparency** | Reads of attachments and audit exports are themselves logged and attributed (NFR-SEC-05). |
| **Data minimisation & retention** (GDPR principles; records-retention policy) | No name/address/DOB in v1; identifiers are pseudonymous references; configurable retention job with dry-run and an audited purge manifest (FR-OPS-05); field notes mark where real PII would live. |
| **Right to produce records on request** (regulator / auditor requests) | Cross-entity audit query by actor/time/action; per-case self-contained export (FR-AUD-04/05). |

A production deployment would additionally need: real PII handling and encryption-at-rest
classification, legal review of retention periods, an AV solution on uploads, SSO and
full audit-user provisioning, and DR beyond single-node — all noted as out of scope for
v1.

---

## 14. Rollout & Roadmap

Assumes a squad of ~3–4 engineers plus part-time UX; indicative phasing, not a committed
plan.

### Phase 0 — Foundations (≈ 1–2 weeks)
Repo, CI (lint/type/test), Docker Compose skeleton (Postgres, Valkey, API, worker),
Alembic baseline, auth + RBAC (FR-RBAC-01/02/03), canonical Alert schema + OpenAPI,
`healthz`/`readyz`/`metrics` (FR-OPS-01/02/03), structured logging.

### Phase 1 — MVP: ingest → group → case → audit (≈ 3–4 weeks)
- Single + bulk ingestion with idempotency (FR-ING-01/02/03/04/08)
- Deterministic grouping + canonical case creation (FR-GRP-01/02/04/05)
- Fixed case lifecycle, assignment, notes (FR-CASE-01/02/03/04, FR-COL-01)
- Immutable, transactional, hash-chained audit log + case audit query/export
  (FR-AUD-01/02/03/04/05)
- Case list + detail UI with grouping rationale (FR-UI-01/02/03/06)
- Search/filter core (FR-SRCH-01/02)
- Synthetic generator + seed data + benchmark harness (FR-ING-06, FR-GRP-08, FR-OPS-04)
**Exit:** a demo where a batch of synthetic alerts becomes a triaged, dispositioned,
fully-audited set of cases via the UI; benchmark F1 reported.

### Phase 2 — Investigator depth (≈ 3–4 weeks)
- Similarity scoring + explainable contributions + threshold config (FR-GRP-03/07)
- Manual merge/split + pins + re-group (FR-OVR-01/02/03, FR-GRP-06)
- Attachments + PDF text extraction + attachment search (FR-COL-02/03/04)
- SLA timers, optimistic concurrency, queue view (FR-CASE-05/06, FR-SRCH-04)
- Batch file import + import job UI (FR-ING-05)
- Admin: grouping-rule editor with benchmark test, disposition/SLA settings (FR-UI-04,
  FR-AUD-07)
**Exit:** analysts can correct the engine; grouping is tunable and evidenced; NFR-PERF
targets validated with a load test.

### Phase 3 — Operations & polish (≈ 2–3 weeks)
- Operational dashboard & reports (FR-UI-05, `/reports/overview`)
- Retention job with dry-run + audited purge (FR-OPS-05)
- Saved views, watchers, related-case links (FR-SRCH-03, FR-CASE-07, FR-COL-05)
- Audit hash-chain verification endpoint & job (FR-AUD-03 hardening)
- Accessibility pass (NFR-UX-01), empty/error states, keyboard triage (FR-UI-07)
- Observability profile (OTel), dependency/image scanning in CI (FR-OPS-06, NFR-SEC-06)

### Later / not in v1
Streaming ingestion, ML matching (FR-GRP-09), no-code workflow designer, multi-tenancy,
OIDC/SAML (FR-RBAC-05), HA/multi-region, native mobile.

---

## 15. Risks, Assumptions & Open Questions

### 15.1 Assumptions

| # | Assumption |
|---|---|
| A1 | Only synthetic data is used; no production or real PII data enters the system in v1. |
| A2 | Single-node deployment on a developer-class or small cloud host (≈ 4 vCPU / 8 GB). |
| A3 | Upstream systems can map their alerts to the canonical schema and call an HTTP endpoint or drop files. |
| A4 | Business-hours operation; 99% availability is acceptable for a reference/demo system. |
| A5 | A squad of ~3–4 engineers is available for roughly a quarter. |
| A6 | The fixed case lifecycle (Open → In Progress → Pending Info → Closed) is acceptable to stakeholders for v1. |
| A7 | Two roles (Analyst, Admin) plus a read-only capability cover v1 needs. |

### 15.2 Risks

| # | Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R1 | Grouping over-merges (false merges), eroding analyst trust and audit integrity | High | Medium | Conservative default thresholds; false-merge rate as a CI gate; easy split + pins; every merge audited and reversible |
| R2 | Grouping under-merges, so duplicates persist and the efficiency benefit is small | Medium | Medium | Benchmark-driven tuning; similarity layer on top of deterministic rules; override rate monitored |
| R3 | Audit-log design proves a bottleneck under load (per-stream lock for `seq`/hash) | Medium | Low-Medium | Stream granularity is per-case (naturally sharded); load test in Phase 2; batch grouping decisions where possible |
| R4 | Synthetic data is not realistic enough, so results don't transfer to a real engagement | Medium | Medium | Generator parameters modelled on documented fraud/AML typologies; SME review of generated samples |
| R5 | Copyleft components (PyMuPDF, pdfplumber, Garage) raise licensing concerns for some clients | Medium | Low | All are Phase 2, none on the MVP critical path (Appendix E); object storage is pluggable (any S3-compatible store); pdf extraction isolated behind an interface with an MIT-licensed fallback path |
| R6 | Scope creep toward a full production platform | High | Medium | Non-goals (Section 3.2) enforced; roadmap phased; changes go through re-scoping |
| R7 | RBAC too simplistic for a real client pilot | Low | Medium | Clean auth seam (FR-RBAC-05); documented extension to OIDC and finer roles |
| R8 | PDF text extraction fails on scanned/image PDFs, weakening attachment search | Low | High (for scanned docs) | Extraction failure is non-fatal and recorded; OCR noted as a future add-on |

### 15.3 Open questions

| # | Question | Owner | Needed by |
|---|---|---|---|
| Q1 | Final disposition taxonomy — confirm the closing-disposition list with Compliance | Compliance SME | Phase 1 start |
| Q2 | SLA thresholds per state and whether v1 should ever hard-block on breach (currently advisory) | Ops Manager | Phase 2 start |
| Q3 | Retention period defaults for cases vs. audit records (often audit is kept far longer) | DPO / Compliance | Phase 3 start |
| Q4 | Whether a read-only "auditor" login is provisioned per engagement or shared | Admin / Client | Phase 1 |
| Q5 | Target list of upstream `source_system` values and any source-specific field quirks to model in the generator | Fraud Ops SME | Phase 1 |
| Q6 | Is cross-currency amount matching (with a supplied FX rate) needed in v1, or deferred? | Product | Phase 2 start |
| Q7 | Confirm React vs. HTMX for the pilot given the actual team composition | Eng Lead | Phase 0 end |

---

## Appendices

### Appendix A — Canonical Alert schema (summary)

| Field | Type | Req. | Notes |
|---|---|---|---|
| `external_alert_id` | string | yes | Unique within `source_system` |
| `source_system` | string | yes | Upstream identifier |
| `event_time` | ISO-8601 datetime | yes | When the underlying event occurred; stored UTC |
| `amount` | decimal | yes | ≥ 0; 2–4 dp |
| `currency` | ISO-4217 | yes | |
| `direction` | enum(`inbound`,`outbound`,`internal`) | yes | |
| `customer_ref` | string | no | Pseudonymous |
| `account_ref` | string | no | Pseudonymous |
| `counterparty_ref` | string | no | |
| `merchant_name` | string | no | Free text; normalised for matching |
| `mcc` | string | no | Merchant category code |
| `device_id` | string | no | |
| `ip_address` | string (IPv4/IPv6) | no | |
| `session_id` | string | no | |
| `risk_score` | integer 0–100 | no | Upstream score |
| `rule_codes` | string[] | no | Upstream rule identifiers |
| `typologies` | string[] | no | e.g. `structuring`, `account-takeover` |
| `raw_payload` | object | no | Verbatim upstream message for provenance |
| `ground_truth_group_id` | string | no | **Synthetic data only**; ignored in scoring, used by the benchmark |

Full JSON Schema ships in the repo at `schemas/alert.schema.json`.

### Appendix B — API reference

Generated OpenAPI at `/api/v1/openapi.json`; a rendered reference is committed at
`docs/api/README.md`. Section 9 is the summary.

### Appendix C — RBAC permission matrix

| Capability | Analyst | Admin | Read-only |
|---|---|---|---|
| View cases / alerts / audit | ✓ | ✓ | ✓ |
| Ingest via API key | (key) | (key) | — |
| Transition case / assign / note | ✓ | ✓ | — |
| Upload / download attachment | ✓ / ✓ | ✓ / ✓ | — / ✓ |
| Merge / split / pin | ✓ | ✓ | — |
| Close / re-open case | ✓ | ✓ | — |
| Export audit trail | ✓ | ✓ | ✓ |
| Cross-entity audit query | — | ✓ | ✓ (audit variant) |
| Edit grouping rules / re-group / benchmark | — | ✓ | — |
| Manage users & roles | — | ✓ | — |
| Run retention job | — | ✓ | — |

### Appendix D — Synthetic Data Specification (outline)

To be delivered alongside the design. Covers: entity pools (customers, accounts,
merchants, devices, IPs); event templates per typology; cluster generation (size
distribution, intra-cluster time/amount jitter, shared-key selection); noise/singleton
injection; label assignment (`ground_truth_group_id`); dataset manifest format; the fixed
CI benchmark dataset and its expected metrics.

### Appendix E — Dependency & licence register

The full stack table (from the engagement brief) is reproduced in
`docs/licenses.md`.

**Critical-path components (MVP) — all permissive:**

| Component | Licence |
|---|---|
| PostgreSQL 16 | PostgreSQL Licence (BSD-style) |
| Valkey 8 | BSD-3-Clause |
| Caddy 2 | Apache-2.0 |
| FastAPI, SQLAlchemy, Alembic, ARQ, Pydantic, React, Vite, Tailwind | MIT / BSD |

No copyleft component is on the MVP critical path. MinIO (AGPLv3) was the
original object store; object storage is deferred to Phase 2 and MinIO is
**dropped** — the Phase 2 choice is **Garage (AGPL-3.0)**, run as an unmodified
standalone service (no code linked or modified), replaceable with any
S3-compatible store via the storage interface.

**Copyleft components (Phase 2 only) and their handling:**

| Component | Licence | Handling |
|---|---|---|
| Garage | AGPL-3.0 | Phase 2 object store. Unmodified standalone container; reached over the S3 API only; swappable for OCI Object Storage or any S3-compatible store |
| PyMuPDF (fitz) | AGPLv3 | Phase 2. Isolated behind the document-processing interface; pdfplumber (MIT) available as the fallback extractor; can be excluded from a build if a client requires it |
| pdfplumber | MIT | Fallback extractor |

All other components are MIT / BSD / Apache-2.0 / PSF — permissive, no distribution obligations for internal use.

### Appendix F — Traceability (core features → requirements)

| Engagement core feature | Requirement IDs |
|---|---|
| Alert ingestion API (single + bulk) | FR-ING-01, FR-ING-02 |
| Idempotency key support on ingest | FR-ING-03 |
| Configurable grouping rules (time, amount, merchant, device, IP) | FR-GRP-02, FR-GRP-03, §10 |
| Automatic canonical Case creation | FR-GRP-01, FR-GRP-05 |
| Manual force-merge / split | FR-OVR-01, FR-OVR-02, FR-OVR-03 |
| Case lifecycle Open→In Progress→Pending Info→Closed | FR-CASE-01, FR-CASE-02, FR-CASE-03 |
| Assign case to analyst | FR-CASE-04 |
| Notes / comments | FR-COL-01 |
| Attach supporting files | FR-COL-02, FR-COL-03, FR-COL-04 |
| Full immutable audit log (before/after) | FR-AUD-01–07, NFR-AUD-01–05 |
| Search & filter cases | FR-SRCH-01, FR-SRCH-02, FR-SRCH-03 |
| Investigator dashboard (list + detail) | FR-UI-01, FR-UI-02, FR-UI-03 |
| Role-based access (Analyst / Admin) | FR-RBAC-01–04, Appendix C |
| Health check & metrics endpoint | FR-OPS-01, FR-OPS-02 |
| Docker Compose + seed data | §11.2, FR-OPS-04, NFR-MNT-01 |

---

*End of document.*
