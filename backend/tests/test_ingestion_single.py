"""Single-alert ingestion endpoint + idempotency.

Infra-marked: drives the real ``create_app()`` through ``ingest_client`` (which
shares the test's ``db_session`` and a Redis client on logical DB 15), and
``require_ingest_key`` loads a real ``ApiKey`` row.

The grouping engine is wired into ``ingest_one``, so a created alert
comes back with a ``case_id`` and a populated ``grouping`` block, and the cached
idempotent-replay body carries them too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select

from app.models.alert import Alert

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.infra


def _key(client: AsyncClient) -> dict[str, str]:
    return {"X-API-Key": client.api_key}  # type: ignore[attr-defined]


async def test_ingest_creates_alert(ingest_client: AsyncClient, valid_alert_payload: dict) -> None:
    r = await ingest_client.post(
        "/api/v1/alerts", json=valid_alert_payload, headers=_key(ingest_client)
    )
    assert r.status_code == 201
    body = r.json()
    assert body["external_alert_id"] == valid_alert_payload["external_alert_id"]
    assert body["case_id"] is not None
    assert body["grouping"]["engine_version"] == "1.0.0"
    assert body["grouping"]["method"] in {"singleton", "deterministic", "similarity"}


async def test_idempotent_replay_returns_same_result_no_duplicate(
    ingest_client: AsyncClient, valid_alert_payload: dict, db_session: AsyncSession
) -> None:
    h = {**_key(ingest_client), "Idempotency-Key": "abc-123"}
    r1 = await ingest_client.post("/api/v1/alerts", json=valid_alert_payload, headers=h)
    r2 = await ingest_client.post("/api/v1/alerts", json=valid_alert_payload, headers=h)
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    # The cached replay body carries the grouping fields set on the first pass.
    assert r2.json()["case_id"] == r1.json()["case_id"]
    assert r2.json()["case_id"] is not None

    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 1


async def test_same_source_external_id_is_deduped(
    ingest_client: AsyncClient, valid_alert_payload: dict
) -> None:
    r1 = await ingest_client.post(
        "/api/v1/alerts", json=valid_alert_payload, headers=_key(ingest_client)
    )
    r2 = await ingest_client.post(
        "/api/v1/alerts", json=valid_alert_payload, headers=_key(ingest_client)
    )
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


async def test_db_unique_constraint_dedupes_across_idempotency_keys(
    ingest_client: AsyncClient, valid_alert_payload: dict, db_session: AsyncSession
) -> None:
    # Distinct Idempotency-Key headers => the Redis layer misses on the replay,
    # so dedup can only come from the (source_system, external_alert_id) unique
    # constraint at the DB layer.
    r1 = await ingest_client.post(
        "/api/v1/alerts",
        json=valid_alert_payload,
        headers={**_key(ingest_client), "Idempotency-Key": "key-one"},
    )
    r2 = await ingest_client.post(
        "/api/v1/alerts",
        json=valid_alert_payload,
        headers={**_key(ingest_client), "Idempotency-Key": "key-two"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]

    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 1


async def test_ingest_survives_redis_outage(
    ingest_client: AsyncClient,
    valid_alert_payload: dict,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Every Redis GET/SET raises a connection error: ingestion must degrade to
    # the DB layer, not 500. First request still creates (201); the identical
    # replay still dedupes (200) via uq_alerts_source_external.
    from redis.asyncio import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError

    async def _boom(*args: object, **kwargs: object) -> object:
        raise RedisConnectionError("simulated redis outage")

    monkeypatch.setattr(Redis, "get", _boom)
    monkeypatch.setattr(Redis, "set", _boom)

    r1 = await ingest_client.post(
        "/api/v1/alerts", json=valid_alert_payload, headers=_key(ingest_client)
    )
    r2 = await ingest_client.post(
        "/api/v1/alerts", json=valid_alert_payload, headers=_key(ingest_client)
    )
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]

    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 1


async def test_invalid_payload_persists_nothing(
    ingest_client: AsyncClient, db_session: AsyncSession
) -> None:
    r = await ingest_client.post(
        "/api/v1/alerts", json={"external_alert_id": "x"}, headers=_key(ingest_client)
    )
    assert r.status_code == 422
    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 0


async def test_ingest_requires_api_key(
    ingest_client: AsyncClient, valid_alert_payload: dict
) -> None:
    r = await ingest_client.post("/api/v1/alerts", json=valid_alert_payload)
    assert r.status_code == 401


async def test_ingest_writes_audit_event(
    ingest_client: AsyncClient,
    valid_alert_payload: dict,
    seed_principal: object,
    token_for: object,
) -> None:
    # ``admin_token`` mints a JWT with a random ``sub`` and no DB row, which
    # ``get_current_principal`` 401s on -- so the audit read needs a
    # real seeded admin principal, exactly like the audit-route tests.
    admin = await seed_principal(roles=["admin"])  # type: ignore[operator]
    r = await ingest_client.post(
        "/api/v1/alerts", json=valid_alert_payload, headers=_key(ingest_client)
    )
    assert r.status_code == 201
    aid = r.json()["id"]
    a = await ingest_client.get(
        "/api/v1/audit",
        params={"target_id": aid},
        headers={"Authorization": f"Bearer {token_for(admin)}"},  # type: ignore[operator]
    )
    assert a.status_code == 200
    actions = [e["action"] for e in a.json()["items"]]
    assert "alert.ingested" in actions


async def test_ingest_audit_event_is_queryable_by_api_key_identity(
    ingest_client: AsyncClient,
    valid_alert_payload: dict,
    seed_principal: object,
    token_for: object,
    db_session: AsyncSession,
) -> None:
    """Fix L1: the ingest audit event's ``actor_id`` is the authenticated ApiKey.id,
    so ``GET /api/v1/audit?actor_id=`` can attribute it."""
    from app.models.user import ApiKey

    admin = await seed_principal(roles=["admin"])  # type: ignore[operator]
    r = await ingest_client.post(
        "/api/v1/alerts", json=valid_alert_payload, headers=_key(ingest_client)
    )
    assert r.status_code == 201

    api_key = (await db_session.execute(select(ApiKey))).scalars().first()
    assert api_key is not None

    a = await ingest_client.get(
        "/api/v1/audit",
        params={"actor_id": str(api_key.id), "action": "alert.ingested"},
        headers={"Authorization": f"Bearer {token_for(admin)}"},  # type: ignore[operator]
    )
    assert a.status_code == 200
    items = a.json()["items"]
    assert items
    assert all(e["actor_id"] == str(api_key.id) for e in items)
    assert r.json()["id"] in {e["target_id"] for e in items}
