"""``POST /api/v1/alerts`` -- single-alert ingestion with idempotency.

Flow:

1. FastAPI validates the body against :class:`AlertIn` (a schema violation is a
   ``422`` before this handler runs -- nothing is persisted).
2. ``require_ingest_key`` authenticates the ``X-API-Key`` header.
3. Compute the idempotency key (``Idempotency-Key`` header namespaced by the
   authenticated ``ApiKey.id``, else the alert's natural identity) and ``check``
   Redis -- a hit with a matching request fingerprint replays the stored body
   with ``200``; a hit whose fingerprint differs (same key, different body) is a
   ``409`` ``idempotency_key_reuse``.
4. Otherwise :func:`app.ingestion.service.ingest_one` persists the alert + audit
   event in one transaction. On a fresh create we ``store`` the response body in
   Redis and return ``201``; if the alert already existed (DB unique constraint)
   we return ``200``.
"""

from __future__ import annotations

import json
from typing import Annotated

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_ingest_key
from app.config import get_settings
from app.db import get_session
from app.ingestion import idempotency
from app.ingestion.service import ingest_one, persist_alert_only
from app.models.user import ApiKey
from app.ratelimit import rate_limit
from app.redis import get_redis
from app.schemas.alert import AlertIn, AlertOut

router = APIRouter(tags=["ingestion"])
_log = structlog.get_logger("ingestion.routes")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
IngestKeyDep = Annotated[ApiKey, Depends(require_ingest_key)]

# Chunk size for the batch route's periodic commits -- see ingest_alerts_batch.
_BATCH_COMMIT_CHUNK = 500


async def _ingest_rate_limit(redis: RedisDep, api_key: IngestKeyDep) -> None:
    """NFR-SEC-08: per-ingest-key fixed-window ceiling on the write endpoints."""
    settings = get_settings()
    await rate_limit(
        redis,
        f"ingest:{api_key.id}",
        settings.ingest_rate_limit_per_minute,
        60,
    )


@router.post(
    "/alerts",
    response_model=AlertOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_ingest_rate_limit)],
)
async def ingest_alert(
    payload: AlertIn,
    session: SessionDep,
    redis: RedisDep,
    api_key: IngestKeyDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AlertOut:
    """Ingest one alert. ``201`` when created, ``200`` on an idempotent replay.

    A repeat of the same ``Idempotency-Key`` with a *different* body is rejected
    ``409`` (``idempotency_key_reuse``) rather than silently returning the first
    alert and dropping the second.
    """
    key = idempotency.compute_key(idempotency_key, payload, api_key.id)
    fingerprint = idempotency.request_fingerprint(payload)

    cached = await idempotency.check(redis, key)
    if cached is not None:
        stored_body, stored_fingerprint = cached
        if stored_fingerprint is not None and stored_fingerprint != fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="idempotency_key_reuse"
            )
        response.status_code = status.HTTP_200_OK
        return AlertOut.model_validate(stored_body)

    result, created = await ingest_one(
        session, payload, idem_key=key, actor_label=api_key.label, api_key_id=api_key.id
    )
    body = result.model_dump(mode="json")

    if created:
        await idempotency.store(
            redis, key, body, fingerprint, get_settings().idempotency_ttl_seconds
        )
        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return result


def _simplify_errors(exc: ValidationError) -> list[dict[str, object]]:
    """Trim ``ValidationError.errors()`` to JSON-safe ``{loc, msg, type}`` dicts."""
    return [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]


async def _parse_batch_items(request: Request) -> list[object]:
    """Read the request body as a list of raw items.

    Accepts a JSON array (any ``Content-Type``) or, when ``Content-Type`` is
    ``application/x-ndjson``, one JSON object per newline. A malformed body is a
    ``422``.
    """
    body = await request.body()
    content_type = request.headers.get("content-type", "").lower()
    try:
        if "x-ndjson" in content_type or "ndjson" in content_type:
            items: list[object] = []
            for line in body.splitlines():
                text = line.strip()
                if text:
                    items.append(json.loads(text))
            return items
        parsed = json.loads(body) if body.strip() else None
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"malformed JSON body: {exc}"
        ) from exc
    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="body must be a JSON array or application/x-ndjson",
        )
    return parsed


@router.post(
    "/alerts:batch",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_ingest_rate_limit)],
)
async def ingest_alerts_batch(
    request: Request,
    session: SessionDep,
    api_key: IngestKeyDep,
) -> dict[str, object]:
    """Bulk-ingest alerts; grouping is deferred to one async ``group_alerts_job``.

    Each item is validated independently (rejects are reported, not fatal), each
    valid item is persisted with per-item dedup, and a single ARQ job is enqueued
    with the ids of the newly-created alerts. ``202``.

    Size limits (NFR-SEC-07): more than ``settings.batch_max_items`` items is a
    ``413`` (``batch_too_large``) before any work.

    Transaction shape: the batch is *not* one unbounded transaction. Every
    ``_BATCH_COMMIT_CHUNK`` (500) successfully-persisted items are committed, then
    a final commit flushes the tail. A mid-batch failure can therefore leave
    earlier chunks durably persisted -- an acceptable trade for not holding a
    write transaction (and its locks) open across an arbitrarily large body. The
    per-item SAVEPOINT dedup still means one bad item never poisons its chunk.

    The enqueue is best-effort: if Redis is unreachable (or declines the job) the
    alerts are still durably persisted and the route still returns ``202`` with
    ``grouping_enqueued: false`` / ``job_id: null``. Un-grouped alerts
    (``case_id IS NULL``) can be re-grouped later by re-enqueuing
    ``group_alerts_job`` with their ids; a periodic sweep is a Phase-2 item.
    """
    raw_items = await _parse_batch_items(request)
    if len(raw_items) > get_settings().batch_max_items:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="batch_too_large")

    rejected: list[dict[str, object]] = []
    valid: list[AlertIn] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            rejected.append(
                {
                    "index": index,
                    "errors": [{"loc": [], "msg": "item must be a JSON object", "type": "type"}],
                }
            )
            continue
        try:
            valid.append(AlertIn(**item))
        except ValidationError as exc:
            rejected.append({"index": index, "errors": _simplify_errors(exc)})

    new_alert_ids: list[str] = []
    duplicates = 0
    for processed, alert_in in enumerate(valid, start=1):
        alert_id, created = await persist_alert_only(
            session,
            alert_in,
            idem_key=idempotency.compute_key(None, alert_in, api_key.id),
            actor_label=api_key.label,
            api_key_id=api_key.id,
        )
        if created:
            new_alert_ids.append(str(alert_id))
        else:
            duplicates += 1
        if processed % _BATCH_COMMIT_CHUNK == 0:
            await session.commit()

    await session.commit()

    # TODO(phase-2): periodic sweep job for alerts where case_id IS NULL
    job_id: str | None = None
    grouping_enqueued = False
    try:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        try:
            job = await pool.enqueue_job("group_alerts_job", new_alert_ids)
        finally:
            await pool.aclose()
        if job is not None:
            job_id = job.job_id
            grouping_enqueued = True
    except (RedisError, OSError) as exc:
        # The alerts are committed; a lost enqueue must not 500 the caller.
        _log.warning(
            "batch.grouping_enqueue_failed",
            alert_ids=len(new_alert_ids),
            error=str(exc),
        )

    return {
        "accepted": len(new_alert_ids),
        "duplicates": duplicates,
        "rejected": rejected,
        "job_id": job_id,
        "grouping_enqueued": grouping_enqueued,
    }


__all__ = ["router"]
