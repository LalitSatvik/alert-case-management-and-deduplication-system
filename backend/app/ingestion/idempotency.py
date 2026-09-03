"""Redis-backed idempotency for the ingestion endpoint.

Two layers protect against duplicate submissions; this module is the first:

* **Redis key** -- ``compute_key`` derives a stable key. With no
  ``Idempotency-Key`` header it is the alert's natural identity,
  ``"{source_system}:{external_alert_id}"`` (already collision-safe). With a
  header it is ``"{api_key_id}:{header_key}"`` -- namespaced by the authenticated
  ``ApiKey.id`` so two ingest clients that happen to pick the same header value
  never touch each other's entry.
* Alongside the cached response body we store a **request fingerprint** -- the
  SHA-256 of the canonical JSON of the validated :class:`AlertIn`. ``check``
  returns it so the route can tell a genuine retry (same key, same body -> replay
  the ``200``) from key reuse (same key, *different* body -> ``409``
  ``idempotency_key_reuse``, rather than silently returning the first alert and
  dropping the second).
* **DB unique constraint** -- ``uq_alerts_source_external`` (handled in
  :mod:`app.ingestion.service`) catches duplicates that slip past Redis (expired
  key, Redis unavailable, distinct headers on the same natural id).

Redis is a best-effort cache here, not a correctness dependency: any
``redis.exceptions.RedisError`` (connection refused, timeout, ...) is logged
(``idempotency.redis_unavailable``) and swallowed -- ``check`` falls through to a
normal ingest and the DB unique constraint still dedupes; ``store`` simply loses
the cache entry (the alert is already persisted).

Stored values are JSON objects; keys are namespaced with ``idem:``.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.schemas.alert import AlertIn

__all__ = ["check", "compute_key", "request_fingerprint", "store"]

_PREFIX = "idem:"
_log = structlog.get_logger("ingestion.idempotency")


def compute_key(header_key: str | None, payload: AlertIn, api_key_id: uuid.UUID | None) -> str:
    """The idempotency key for this request.

    A truthy client-supplied ``Idempotency-Key`` header wins, namespaced by the
    authenticated ``ApiKey.id`` (``"{api_key_id}:{header_key}"``) so the same
    header value from two different keys cannot collide. Otherwise fall back to
    the alert's natural identity, ``source_system:external_alert_id``, which is
    already naturally namespaced.
    """
    if header_key:
        return f"{api_key_id}:{header_key}"
    return f"{payload.source_system}:{payload.external_alert_id}"


def request_fingerprint(payload: AlertIn) -> str:
    """SHA-256 hex digest of a canonical serialisation of the validated payload.

    ``model_dump_json`` emits fields in model-declaration order, so the same
    ``AlertIn`` always hashes to the same value regardless of inbound key order.
    """
    return hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()


async def check(redis: Redis, key: str) -> tuple[dict[str, object], str | None] | None:
    """Return ``(stored_response_body, stored_request_sha256)`` for ``key``, or ``None``.

    ``None`` on a miss. A Redis outage is treated as a miss (logged, not raised):
    the caller then ingests normally and the DB unique constraint provides
    deduplication. Entries written before request fingerprinting existed come
    back with a ``None`` fingerprint.
    """
    try:
        raw = await redis.get(_PREFIX + key)
    except RedisError as exc:
        _log.warning("idempotency.redis_unavailable", op="check", key=key, error=str(exc))
        return None
    if raw is None:
        return None
    stored: dict[str, object] = json.loads(raw)
    if "response" in stored:
        body = stored["response"]
        fingerprint = stored.get("request_sha256")
        return (
            body if isinstance(body, dict) else {},
            fingerprint if isinstance(fingerprint, str) else None,
        )
    # Legacy entry: the bare response body with no fingerprint envelope.
    return stored, None


async def store(
    redis: Redis,
    key: str,
    response_body: dict[str, object],
    request_sha256: str,
    ttl: int,
) -> None:
    """SET a ``{"response": ..., "request_sha256": ...}`` envelope under ``key``.

    A Redis outage is logged and swallowed -- the alert is already persisted, so a
    lost cache entry only means the next identical request dedupes via the DB.
    """
    envelope = {"response": response_body, "request_sha256": request_sha256}
    try:
        await redis.set(_PREFIX + key, json.dumps(envelope), ex=ttl)
    except RedisError as exc:
        _log.warning("idempotency.redis_unavailable", op="store", key=key, error=str(exc))
