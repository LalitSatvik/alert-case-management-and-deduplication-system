"""Integration tests for ``GET /api/v1/users`` -- the assignee-picker directory."""

from __future__ import annotations

import pytest


@pytest.fixture
async def analyst_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("analyst",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


async def test_lists_active_users_ordered_by_email(app_client, analyst_headers, make_user) -> None:
    await make_user(email="zoe@example.com")  # type: ignore[operator]
    await make_user(email="amy@example.com")  # type: ignore[operator]

    r = await app_client.get("/api/v1/users", headers=analyst_headers)
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()]
    # the seeded principal is a user too; assert ordering + our two are present
    assert emails == sorted(emails)
    assert {"amy@example.com", "zoe@example.com"} <= set(emails)
    assert all({"id", "email", "display_name"} == u.keys() for u in r.json())


async def test_excludes_inactive_users(app_client, analyst_headers, make_user) -> None:
    await make_user(email="ghost@example.com", is_active=False)  # type: ignore[operator]

    r = await app_client.get("/api/v1/users", headers=analyst_headers)
    assert "ghost@example.com" not in [u["email"] for u in r.json()]


async def test_users_requires_auth(app_client) -> None:
    r = await app_client.get("/api/v1/users")
    assert r.status_code == 401
