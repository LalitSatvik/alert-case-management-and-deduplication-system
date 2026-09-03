"""Idempotency-Key semantics for ``POST /api/v1/alerts`` (fix H1).

Before the fix, ``compute_key`` returned the raw header and ``check`` never
compared payloads: a second POST with the same ``Idempotency-Key`` but a
*different* body silently returned the first alert with ``200`` and dropped the
second. Now the stored entry carries a SHA-256 fingerprint of the validated
payload; a mismatch is a ``409`` and the key is namespaced by the authenticated
``ApiKey.id`` so two clients cannot collide on the same header value.
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


def _key(raw: str) -> dict[str, str]:
    return {"X-API-Key": raw}


async def test_same_key_same_body_replays_200(
    ingest_client: AsyncClient, valid_alert_payload: dict
) -> None:
    h = {**_key(ingest_client.api_key), "Idempotency-Key": "k-replay"}  # type: ignore[attr-defined]
    r1 = await ingest_client.post("/api/v1/alerts", json=valid_alert_payload, headers=h)
    r2 = await ingest_client.post("/api/v1/alerts", json=valid_alert_payload, headers=h)
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


async def test_same_key_different_body_is_409(
    ingest_client: AsyncClient, valid_alert_payload: dict, db_session: AsyncSession
) -> None:
    h = {**_key(ingest_client.api_key), "Idempotency-Key": "k-reuse"}  # type: ignore[attr-defined]
    first = await ingest_client.post("/api/v1/alerts", json=valid_alert_payload, headers=h)
    assert first.status_code == 201

    other_body = {**valid_alert_payload, "external_alert_id": "different-alert", "amount": "9.99"}
    clash = await ingest_client.post("/api/v1/alerts", json=other_body, headers=h)
    assert clash.status_code == 409
    assert clash.json()["detail"] == "idempotency_key_reuse"

    # The second alert was never persisted.
    count = await db_session.scalar(select(func.count()).select_from(Alert))
    assert count == 1


async def test_distinct_natural_keys_are_independent(
    ingest_client: AsyncClient, valid_alert_payload: dict
) -> None:
    a = await ingest_client.post(
        "/api/v1/alerts",
        json={**valid_alert_payload, "external_alert_id": "nat-a"},
        headers=_key(ingest_client.api_key),  # type: ignore[attr-defined]
    )
    b = await ingest_client.post(
        "/api/v1/alerts",
        json={**valid_alert_payload, "external_alert_id": "nat-b"},
        headers=_key(ingest_client.api_key),  # type: ignore[attr-defined]
    )
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["id"] != b.json()["id"]


async def test_same_header_value_two_api_keys_do_not_collide(
    ingest_client: AsyncClient, valid_alert_payload: dict, make_api_key: object
) -> None:
    second_raw = await make_api_key(scope="ingest", active=True)  # type: ignore[operator]
    header = "shared-idem-value"

    r1 = await ingest_client.post(
        "/api/v1/alerts",
        json={**valid_alert_payload, "external_alert_id": "client-one"},
        headers={**_key(ingest_client.api_key), "Idempotency-Key": header},  # type: ignore[attr-defined]
    )
    # A *different* body from a *different* key with the *same* header value must
    # not 409 and must not replay the first client's alert.
    r2 = await ingest_client.post(
        "/api/v1/alerts",
        json={**valid_alert_payload, "external_alert_id": "client-two"},
        headers={**_key(second_raw), "Idempotency-Key": header},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
