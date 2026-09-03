"""Bulk ingestion endpoint + ARQ worker + async grouping.

``infra``-marked: drives the real ``create_app()`` and needs the bootstrapped
local Postgres, the full Alembic chain, and a local Redis (logical DB 15 for the
ARQ queue).

Two isolation modes are exercised here:

* ``test_batch_accepts_*`` only assert the ``202`` body, so they ride the
  savepoint-isolated ``ingest_client``.
* ``test_batch_grouping_runs_via_worker`` needs the ARQ worker -- a *separate* DB
  connection -- to see the alerts the batch route persisted, so it uses the
  real-committing ``committing_client`` + ``committing_session_factory`` and the
  ``run_worker_once`` drainer. Both clean up with a ``TRUNCATE``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.models.alert import Alert

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from contextlib import AbstractAsyncContextManager

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.infra

_REDIS_TEST_URL = "redis://localhost:6379/15"


@pytest.fixture(autouse=True)
async def _flush_arq_queue() -> AsyncIterator[None]:
    """Flush test Redis DB 15 before and after each test.

    The savepoint-isolated batch tests hit the real route -> real ``enqueue_job``
    for alert ids that then roll back; without this the queue accretes orphan
    jobs across tests.
    """
    import redis.asyncio as _redis

    client = _redis.from_url(_REDIS_TEST_URL)
    await client.flushdb()
    try:
        yield
    finally:
        await client.flushdb()
        await client.aclose()


def _key(client: AsyncClient) -> dict[str, str]:
    return {"X-API-Key": client.api_key}  # type: ignore[attr-defined]


async def test_batch_accepts_valid_and_reports_rejects(
    ingest_client: AsyncClient, valid_alert_payload: dict
) -> None:
    items = [
        valid_alert_payload,
        {"external_alert_id": "bad"},
        {**valid_alert_payload, "external_alert_id": "A2"},
    ]
    r = await ingest_client.post("/api/v1/alerts:batch", json=items, headers=_key(ingest_client))
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 2
    assert body["duplicates"] == 0
    assert body["rejected"][0]["index"] == 1
    assert body["rejected"][0]["errors"]
    assert body["job_id"]
    assert body["grouping_enqueued"] is True


async def test_batch_accepts_ndjson(ingest_client: AsyncClient, valid_alert_payload: dict) -> None:
    import json

    lines = "\n".join(
        json.dumps({**valid_alert_payload, "external_alert_id": f"ND{i}"}) for i in range(3)
    )
    r = await ingest_client.post(
        "/api/v1/alerts:batch",
        content=lines,
        headers={**_key(ingest_client), "Content-Type": "application/x-ndjson"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 3
    assert body["rejected"] == []
    assert body["grouping_enqueued"] is True


async def test_batch_duplicate_in_batch_does_not_poison(
    ingest_client: AsyncClient, valid_alert_payload: dict
) -> None:
    # Two identical items (collide on source_system+external_alert_id) plus a
    # distinct one. The savepoint around each insert means the dup rolls back
    # only itself -- the other two still land.
    items = [
        valid_alert_payload,
        valid_alert_payload,
        {**valid_alert_payload, "external_alert_id": "DISTINCT"},
    ]
    r = await ingest_client.post("/api/v1/alerts:batch", json=items, headers=_key(ingest_client))
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 2
    assert body["duplicates"] == 1


async def test_batch_reports_no_job_when_enqueue_declined(
    ingest_client: AsyncClient, valid_alert_payload: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fix L3: ARQ ``enqueue_job`` returns ``None`` for an already-queued job id --
    the route must report ``job_id: null`` / ``grouping_enqueued: false``, not
    fabricate a uuid and claim success."""

    class _FakePool:
        async def enqueue_job(self, *args: object, **kwargs: object) -> None:
            return None

        async def aclose(self) -> None:
            return None

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return _FakePool()

    monkeypatch.setattr("app.ingestion.routes.create_pool", _fake_create_pool)

    items = [{**valid_alert_payload, "external_alert_id": f"NJ{i}"} for i in range(2)]
    r = await ingest_client.post("/api/v1/alerts:batch", json=items, headers=_key(ingest_client))
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 2
    assert body["job_id"] is None
    assert body["grouping_enqueued"] is False


async def test_batch_survives_grouping_enqueue_failure(
    committing_client: AsyncClient,
    valid_alert_payload: dict,
    committing_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Redis unreachable at enqueue time: alerts are already committed, so the
    # route must still 202 (grouping_enqueued=False, job_id=None) and the alerts
    # persist un-grouped (case_id NULL) for a later re-enqueue / sweep.
    from redis.exceptions import ConnectionError as RedisConnectionError

    async def _boom(*args: object, **kwargs: object) -> object:
        raise RedisConnectionError("simulated redis outage")

    monkeypatch.setattr("app.ingestion.routes.create_pool", _boom)

    items = [{**valid_alert_payload, "external_alert_id": f"EF{i}"} for i in range(2)]
    r = await committing_client.post(
        "/api/v1/alerts:batch", json=items, headers={"X-API-Key": "unused"}
    )
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 2
    assert body["grouping_enqueued"] is False
    assert body["job_id"] is None

    async with committing_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Alert).where(Alert.external_alert_id.in_(["EF0", "EF1"]))
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 2
    assert all(a.case_id is None for a in rows)


async def test_batch_grouping_runs_via_worker(
    committing_client: AsyncClient,
    valid_alert_payload: dict,
    run_worker_once: Callable[[], Awaitable[None]],
    committing_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    items = [
        {
            **valid_alert_payload,
            "external_alert_id": f"B{i}",
            "account_ref": "SHARED",
            "counterparty_ref": "CP",
            "amount": "500",
        }
        for i in range(3)
    ]
    r = await committing_client.post(
        "/api/v1/alerts:batch", json=items, headers={"X-API-Key": "unused"}
    )
    assert r.status_code == 202
    assert r.json()["accepted"] == 3
    assert r.json()["grouping_enqueued"] is True

    await run_worker_once()  # drains the ARQ queue against the test redis

    async with committing_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Alert).where(Alert.external_alert_id.in_(["B0", "B1", "B2"]))
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 3
    case_ids = {a.case_id for a in rows}
    assert None not in case_ids
    assert len(case_ids) == 1


async def test_group_alerts_job_isolates_poison_and_skips_cased(
    committing_client: AsyncClient,
    valid_alert_payload: dict,
    committing_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    from app.grouping.config import get_grouping_config
    from app.grouping.persistence import apply_grouping_for_alert
    from app.worker import group_alerts_job

    items = [{**valid_alert_payload, "external_alert_id": f"P{i}"} for i in range(2)]
    r = await committing_client.post(
        "/api/v1/alerts:batch", json=items, headers={"X-API-Key": "unused"}
    )
    assert r.json()["accepted"] == 2
    async with committing_session_factory() as session:
        good_ids = [
            str(a_id)
            for a_id in (
                await session.execute(
                    select(Alert.id)
                    .where(Alert.external_alert_id.in_(["P0", "P1"]))
                    .order_by(Alert.external_alert_id)
                )
            )
            .scalars()
            .all()
        ]
    assert len(good_ids) == 2

    # Pre-group the first alert so the job must SKIP it (idempotent path).
    async with committing_session_factory() as session:
        alert = await session.get(Alert, uuid.UUID(good_ids[0]))
        assert alert is not None
        await apply_grouping_for_alert(session, alert, get_grouping_config(), "test")
        await session.commit()
        pre_case_id = alert.case_id

    ctx = {"session_factory": committing_session_factory}
    missing_id = str(uuid.uuid4())
    result = await group_alerts_job(ctx, [good_ids[0], missing_id, good_ids[1]])

    assert result["grouped"] == 1  # only good_ids[1] newly grouped
    assert [f["alert_id"] for f in result["failed"]] == [missing_id]

    async with committing_session_factory() as session:
        rows = {
            str(a.id): a
            for a in (
                (
                    await session.execute(
                        select(Alert).where(
                            Alert.id.in_([uuid.UUID(good_ids[0]), uuid.UUID(good_ids[1])])
                        )
                    )
                )
                .scalars()
                .all()
            )
        }
    assert rows[good_ids[0]].case_id == pre_case_id  # untouched
    assert rows[good_ids[1]].case_id is not None


def test_worker_settings_is_production_correct() -> None:
    from app.worker import WorkerSettings, group_alerts_job

    assert group_alerts_job in WorkerSettings.functions
    assert WorkerSettings.max_tries == 3
    assert WorkerSettings.redis_settings is not None
    assert callable(WorkerSettings.on_startup)
    assert callable(WorkerSettings.on_shutdown)
