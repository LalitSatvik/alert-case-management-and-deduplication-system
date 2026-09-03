"""ARQ worker: asynchronous grouping for bulk-ingested alerts.

``POST /api/v1/alerts:batch`` persists alerts *without* grouping them (grouping
touches many rows and can merge cases -- too slow to do inline for a large batch)
and enqueues one :func:`group_alerts_job` carrying the new alert ids. This module
is the consumer.

``group_alerts_job`` groups the alerts **one at a time, each in its own
transaction**:

* it opens a fresh session per alert, so a poison alert's exception is caught,
  recorded in the result's ``failed`` list, and does not roll back or block the
  alerts around it;
* it ``commit``s after each alert, so batch-mates that should group see each
  other -- alert A creates a case, then alert B's candidate query finds A (now
  cased) and attaches to A's case. Sequential passes collapse a batch to the
  right set of cases;
* it is idempotent: an alert already linked to a case (``case_id is not None``)
  is skipped, so a retried job (``max_tries = 3``) never double-groups.

:class:`WorkerSettings` is what ``arq worker app.worker.WorkerSettings`` runs in
the deployment. ``on_startup`` builds one async engine + sessionmaker into the
context (``ACMS_WORKER_DATABASE_URL`` overrides the app's ``DATABASE_URL`` when
set -- e.g. to point the worker at a different pool); ``on_shutdown`` disposes it.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.grouping.config import get_grouping_config
from app.grouping.persistence import apply_grouping_for_alert
from app.models.alert import Alert

__all__ = ["WorkerSettings", "group_alerts_job"]

_WORKER_DB_URL_ENV = "ACMS_WORKER_DATABASE_URL"


async def group_alerts_job(ctx: dict[str, Any], alert_ids: list[str]) -> dict[str, Any]:
    """Group each alert in ``alert_ids``, one transaction per alert.

    Returns ``{"grouped": <int>, "failed": [{"alert_id": ..., "error": ...}]}``.
    An alert that is already linked to a case is skipped (idempotent); an alert
    that raises is recorded in ``failed`` and does not block the rest.
    """
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    config = get_grouping_config()

    grouped = 0
    failed: list[dict[str, str]] = []

    for raw_id in alert_ids:
        try:
            alert_id = uuid.UUID(str(raw_id))
            async with session_factory() as session:
                alert = (
                    await session.execute(select(Alert).where(Alert.id == alert_id))
                ).scalar_one_or_none()
                if alert is None:
                    raise LookupError(f"alert {raw_id} not found")
                if alert.case_id is not None:
                    continue  # already grouped -- idempotent skip
                await apply_grouping_for_alert(session, alert, config, "worker")
                await session.commit()
            grouped += 1
        except Exception as exc:  # noqa: BLE001 -- one poison alert must not abort the batch
            failed.append({"alert_id": str(raw_id), "error": f"{type(exc).__name__}: {exc}"})

    return {"grouped": grouped, "failed": failed}


async def on_startup(ctx: dict[str, Any]) -> None:
    """Build the worker's async engine + sessionmaker into ``ctx``."""
    url = os.environ.get(_WORKER_DB_URL_ENV) or get_settings().database_url
    engine = create_async_engine(url, pool_pre_ping=True, future=True)
    ctx["db_engine"] = engine
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    """Dispose the worker's async engine."""
    engine = ctx.get("db_engine")
    if engine is not None:
        await engine.dispose()


class WorkerSettings:
    """ARQ entrypoint: ``arq app.worker.WorkerSettings``."""

    functions: ClassVar[list[Callable[..., Awaitable[Any]]]] = [group_alerts_job]
    redis_settings: ClassVar[RedisSettings] = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries: ClassVar[int] = 3
    on_startup: ClassVar[Callable[[dict[str, Any]], Awaitable[None]]] = staticmethod(on_startup)
    on_shutdown: ClassVar[Callable[[dict[str, Any]], Awaitable[None]]] = staticmethod(on_shutdown)
