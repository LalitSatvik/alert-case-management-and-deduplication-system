"""Integration tests for ``POST /api/v1/cases/{case_id}/transition``.

These drive the real ASGI app through ``app_client`` (so ``require_role`` +
``get_current_principal`` run for real). ``get_current_principal`` loads the user
by the token's ``sub``, so tokens must come from a *seeded* principal via
``seed_principal`` + ``token_for`` -- the bare ``analyst_token`` / ``readonly_token``
fixtures mint a random ``sub`` with no DB row and would 401.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.audit import AuditEvent


@pytest.fixture
async def analyst_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("analyst",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


@pytest.fixture
async def readonly_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("readonly",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


async def test_full_lifecycle_path(app_client, analyst_headers, seeded_case) -> None:
    h = analyst_headers
    cid = seeded_case.id
    assert (
        await app_client.post(
            f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=h
        )
    ).status_code == 200
    assert (
        await app_client.post(
            f"/api/v1/cases/{cid}/transition",
            json={"to": "Pending Info", "reason": "await merchant"},
            headers=h,
        )
    ).status_code == 200
    assert (
        await app_client.post(
            f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=h
        )
    ).status_code == 200
    r = await app_client.post(
        f"/api/v1/cases/{cid}/transition",
        json={"to": "Closed", "disposition": "Confirmed fraud", "reason": "card compromised"},
        headers=h,
    )
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "Closed"
    assert body["disposition"] == "Confirmed fraud"
    assert body["closed_at"] is not None
    assert body["version"] == 5


async def test_reopen_clears_closed_state(app_client, analyst_headers, seeded_case) -> None:
    h = analyst_headers
    cid = seeded_case.id
    await app_client.post(f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=h)
    await app_client.post(
        f"/api/v1/cases/{cid}/transition",
        json={"to": "Closed", "disposition": "No action"},
        headers=h,
    )
    r = await app_client.post(
        f"/api/v1/cases/{cid}/transition",
        json={"to": "In Progress", "reason": "new evidence"},
        headers=h,
    )
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "In Progress"
    assert body["disposition"] is None
    assert body["closed_at"] is None


async def test_reopen_without_reason_is_422(app_client, analyst_headers, seeded_case) -> None:
    h = analyst_headers
    cid = seeded_case.id
    await app_client.post(f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=h)
    await app_client.post(
        f"/api/v1/cases/{cid}/transition",
        json={"to": "Closed", "disposition": "No action"},
        headers=h,
    )
    r = await app_client.post(
        f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=h
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "reopen_requires_reason"


async def test_illegal_transition_returns_409(app_client, analyst_headers, seeded_case) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{seeded_case.id}/transition",
        json={"to": "Closed", "disposition": "Confirmed fraud"},
        headers=analyst_headers,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "illegal_transition"


async def test_close_without_disposition_returns_422(
    app_client, analyst_headers, seeded_case
) -> None:
    h = analyst_headers
    cid = seeded_case.id
    await app_client.post(f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=h)
    r = await app_client.post(f"/api/v1/cases/{cid}/transition", json={"to": "Closed"}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"] == "disposition_required"


async def test_close_with_unknown_disposition_returns_422(
    app_client, analyst_headers, seeded_case
) -> None:
    h = analyst_headers
    cid = seeded_case.id
    await app_client.post(f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=h)
    r = await app_client.post(
        f"/api/v1/cases/{cid}/transition",
        json={"to": "Closed", "disposition": "Totally made up"},
        headers=h,
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "unknown_disposition"


async def test_unknown_case_returns_404(app_client, analyst_headers) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{uuid.uuid4()}/transition",
        json={"to": "In Progress"},
        headers=analyst_headers,
    )
    assert r.status_code == 404


async def test_stale_if_match_returns_409(app_client, analyst_headers, seeded_case) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{seeded_case.id}/transition",
        json={"to": "In Progress"},
        headers={**analyst_headers, "If-Match": "99"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "stale_case_version"


async def test_matching_if_match_succeeds(app_client, analyst_headers, seeded_case) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{seeded_case.id}/transition",
        json={"to": "In Progress"},
        headers={**analyst_headers, "If-Match": "1"},
    )
    assert r.status_code == 200
    assert r.json()["version"] == 2


async def test_readonly_cannot_transition(app_client, readonly_headers, seeded_case) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{seeded_case.id}/transition",
        json={"to": "In Progress"},
        headers=readonly_headers,
    )
    assert r.status_code == 403


async def test_unauthenticated_is_401(app_client, seeded_case) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{seeded_case.id}/transition", json={"to": "In Progress"}
    )
    assert r.status_code == 401


async def test_transition_writes_audit_event(
    app_client, analyst_headers, seeded_case, db_session
) -> None:
    cid = seeded_case.id
    await app_client.post(
        f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=analyst_headers
    )
    events = (
        (
            await db_session.execute(
                select(AuditEvent)
                .where(AuditEvent.stream == f"case:{cid}")
                .order_by(AuditEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    event = events[0]
    assert event.action == "case.transitioned"
    assert event.target_type == "case"
    assert event.target_id == str(cid)
    assert event.before == {"status": "Open", "disposition": None}
    assert event.after == {"status": "In Progress", "disposition": None}
    assert event.actor_id is not None
