"""Integration tests for ``GET /api/v1/cases/stats``.

Same auth path as the list endpoint (seeded principal + ``token_for``). Savepoint
isolation means each test only sees the cases it creates, so the counts are exact.
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def analyst_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("analyst",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


async def test_stats_totals_bands_and_average(
    app_client, analyst_headers, make_case, make_user
) -> None:
    owner = await make_user(roles=("analyst",))  # type: ignore[operator]
    await make_case(status="In Progress", risk_score=95, assignee_id=owner.id)
    await make_case(status="Open", risk_score=90)
    await make_case(status="Open", risk_score=40)
    await make_case(status="Closed", risk_score=10)

    r = await app_client.get("/api/v1/cases/stats", headers=analyst_headers)
    assert r.status_code == 200
    body = r.json()

    assert body["total"] == 4
    assert body["by_status"] == {"Open": 2, "In Progress": 1, "Closed": 1}
    assert body["unassigned"] == 3
    assert body["high_risk"] == 2  # 95 and 90, threshold 90
    assert body["high_risk_threshold"] == 90
    assert body["avg_risk"] == pytest.approx(58.8, abs=0.05)  # (95+90+40+10)/4


async def test_stats_honours_the_same_filters_as_the_list(
    app_client, analyst_headers, make_case
) -> None:
    await make_case(status="Open", risk_score=20)
    await make_case(status="Open", risk_score=80)
    await make_case(status="Closed", risk_score=85)

    r = await app_client.get(
        "/api/v1/cases/stats",
        params={"status": "Open", "risk_min": 50},
        headers=analyst_headers,
    )
    body = r.json()
    assert body["total"] == 1
    assert body["by_status"] == {"Open": 1}
    assert body["high_risk"] == 0


async def test_stats_empty_result_is_zeroed(app_client, analyst_headers, make_case) -> None:
    await make_case(status="Open", risk_score=20)

    r = await app_client.get(
        "/api/v1/cases/stats", params={"status": "Merged"}, headers=analyst_headers
    )
    body = r.json()
    assert body["total"] == 0
    assert body["by_status"] == {}
    assert body["avg_risk"] == 0


async def test_stats_requires_auth(app_client) -> None:
    r = await app_client.get("/api/v1/cases/stats")
    assert r.status_code == 401
