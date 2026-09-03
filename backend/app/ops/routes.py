from __future__ import annotations

import structlog
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import engine
from app.metrics import cases_open
from app.models.case import Case

router = APIRouter(tags=["ops"])
_log = structlog.get_logger("ops")

_TERMINAL_STATUSES = ("Closed", "Merged")


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}
    ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        _log.warning("readyz.database_check_failed", error=str(exc), exc_type=type(exc).__name__)
        checks["database"] = f"error: {type(exc).__name__}"
        ok = False
    try:
        r = redis_from_url(get_settings().redis_url)  # type: ignore[no-untyped-call]
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        _log.warning("readyz.redis_check_failed", error=str(exc), exc_type=type(exc).__name__)
        checks["redis"] = f"error: {type(exc).__name__}"
        ok = False
    response.status_code = 200 if ok else 503
    return {"status": "ready" if ok else "not_ready", "checks": checks}


async def _refresh_cases_open() -> None:
    """Set the ``cases_open`` gauge from a single ``COUNT`` at scrape time.

    Best-effort: a DB error leaves the previous value in place and is logged, not
    raised -- a scrape must never fail because the database blipped.
    """
    try:
        async with AsyncSession(engine) as session:
            value = await session.scalar(
                select(func.count()).select_from(Case).where(Case.status.not_in(_TERMINAL_STATUSES))
            )
        cases_open.set(int(value or 0))
    except Exception as exc:  # noqa: BLE001
        _log.warning("metrics.cases_open_refresh_failed", error=str(exc))


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus exposition (FR-OPS-02).

    Left unauthenticated in Phase 1; putting the endpoint behind auth (or binding
    it to an internal interface only) is a documented Phase-2 hardening item.
    """
    await _refresh_cases_open()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
