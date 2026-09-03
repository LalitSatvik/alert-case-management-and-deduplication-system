"""Valkey-backed rate limiting + batch size cap (fix H3, NFR-SEC-08 / NFR-SEC-07).

``app_client`` / ``ingest_client`` point ``get_redis`` at the throwaway logical DB
15, which the ``redis_url`` fixture flushes on teardown -- so each test starts
with empty rate-limit counters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import get_settings

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.infra


async def test_auth_token_is_rate_limited(app_client: AsyncClient) -> None:
    limit = get_settings().auth_rate_limit_per_minute
    body = {"email": "nobody@example.com", "password": "wrong"}

    for _ in range(limit):
        r = await app_client.post("/api/v1/auth/token", json=body)
        assert r.status_code == 401

    blocked = await app_client.post("/api/v1/auth/token", json=body)
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "rate_limited"
    assert "Retry-After" in blocked.headers


async def test_batch_over_max_items_is_413(
    ingest_client: AsyncClient, valid_alert_payload: dict
) -> None:
    oversized = [{} for _ in range(get_settings().batch_max_items + 1)]
    r = await ingest_client.post(
        "/api/v1/alerts:batch",
        json=oversized,
        headers={"X-API-Key": ingest_client.api_key},  # type: ignore[attr-defined]
    )
    assert r.status_code == 413
    assert r.json()["detail"] == "batch_too_large"


async def test_rate_limiter_fails_open_when_redis_errors(
    app_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from redis.asyncio import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError

    async def _boom(*args: object, **kwargs: object) -> object:
        raise RedisConnectionError("simulated redis outage")

    monkeypatch.setattr(Redis, "incr", _boom)

    body = {"email": "nobody@example.com", "password": "wrong"}
    # Well past the limit -- every call should still reach the handler (401), not 429.
    for _ in range(get_settings().auth_rate_limit_per_minute + 3):
        r = await app_client.post("/api/v1/auth/token", json=body)
        assert r.status_code == 401
