"""Application Prometheus collectors (FR-OPS-02).

Module-level singletons registered on the default registry. Importing this module
is enough to register them; the ingestion, grouping, audit and HTTP paths import
the names they need and increment/observe them inline.

``cases_open`` is refreshed at scrape time by the ``/metrics`` route handler
(:func:`app.ops.routes.metrics`) with a single ``GROUP BY status`` query rather
than being incremented/decremented in the lifecycle service -- a counter kept in
process memory would drift on every restart, redeploy or multi-instance rollout,
whereas a scrape-time read is always exactly the database's truth. The read is
best-effort: a DB error leaves the last value in place and never fails the scrape.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "alerts_ingested_total",
    "audit_write_failures_total",
    "cases_open",
    "grouping_decisions_total",
    "grouping_duration_seconds",
    "http_request_duration_seconds",
]

alerts_ingested_total = Counter(
    "alerts_ingested_total",
    "Alerts accepted by the ingestion endpoint, by outcome.",
    ["result"],
)

grouping_duration_seconds = Histogram(
    "grouping_duration_seconds",
    "Wall-clock time to group one alert into a canonical case.",
)

grouping_decisions_total = Counter(
    "grouping_decisions_total",
    "Grouping decisions written, by engine method.",
    ["method"],
)

cases_open = Gauge(
    "cases_open",
    "Cases not in a terminal state (status not Closed/Merged), refreshed on scrape.",
)

audit_write_failures_total = Counter(
    "audit_write_failures_total",
    "Audit-log append attempts that raised before commit.",
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration, by method, matched route template and status.",
    ["method", "route", "status"],
)
