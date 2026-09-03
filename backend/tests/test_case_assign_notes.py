"""Integration tests for case assignment + append-only notes.

These drive the real ASGI app through ``app_client`` so ``require_role`` +
``get_current_principal`` run for real. Tokens therefore come from a *seeded*
principal (``seed_principal`` + ``token_for``); the bare ``analyst_token``
fixture mints a random ``sub`` with no DB row and would 401.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.audit import AuditEvent
from app.models.case import Note


@pytest.fixture
async def analyst(seed_principal: object, token_for: object) -> tuple[object, dict[str, str]]:
    user = await seed_principal(roles=("analyst",))  # type: ignore[operator]
    return user, {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


@pytest.fixture
async def admin(seed_principal: object, token_for: object) -> tuple[object, dict[str, str]]:
    user = await seed_principal(roles=("admin",))  # type: ignore[operator]
    return user, {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


@pytest.fixture
async def readonly_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("readonly",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


# --- assignment --------------------------------------------------------------


async def test_assign_and_reassign_are_audited(
    app_client, analyst, admin_user, make_user, make_case
) -> None:
    _, h = analyst
    case = await make_case()
    other = await make_user(roles=("analyst",))

    r = await app_client.post(
        f"/api/v1/cases/{case.id}/assign", json={"assignee_id": str(admin_user.id)}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["assignee_id"] == str(admin_user.id)
    assert r.json()["version"] == 2

    r = await app_client.post(
        f"/api/v1/cases/{case.id}/assign", json={"assignee_id": str(other.id)}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["assignee_id"] == str(other.id)
    assert r.json()["version"] == 3

    audit = await app_client.get(f"/api/v1/cases/{case.id}/audit", headers=h)
    assigned = [e for e in audit.json() if e["action"] == "case.assigned"]
    assert len(assigned) == 2
    assert assigned[0]["before"] == {"assignee_id": None}
    assert assigned[0]["after"] == {"assignee_id": str(admin_user.id)}
    assert assigned[1]["before"] == {"assignee_id": str(admin_user.id)}
    assert assigned[1]["after"] == {"assignee_id": str(other.id)}


async def test_unassign_sets_null(app_client, analyst, admin_user, make_case) -> None:
    _, h = analyst
    case = await make_case()
    await app_client.post(
        f"/api/v1/cases/{case.id}/assign", json={"assignee_id": str(admin_user.id)}, headers=h
    )
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/assign", json={"assignee_id": None}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["assignee_id"] is None


async def test_assign_to_inactive_user_rejected(
    app_client, analyst, inactive_user, make_case
) -> None:
    _, h = analyst
    case = await make_case()
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/assign", json={"assignee_id": str(inactive_user.id)}, headers=h
    )
    assert r.status_code == 422


async def test_assign_to_unknown_user_rejected(app_client, analyst, make_case) -> None:
    _, h = analyst
    case = await make_case()
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/assign", json={"assignee_id": str(uuid.uuid4())}, headers=h
    )
    assert r.status_code == 422


async def test_assign_unknown_case_is_404(app_client, analyst, admin_user) -> None:
    _, h = analyst
    r = await app_client.post(
        f"/api/v1/cases/{uuid.uuid4()}/assign", json={"assignee_id": str(admin_user.id)}, headers=h
    )
    assert r.status_code == 404


async def test_readonly_cannot_assign(app_client, readonly_headers, admin_user, make_case) -> None:
    case = await make_case()
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/assign",
        json={"assignee_id": str(admin_user.id)},
        headers=readonly_headers,
    )
    assert r.status_code == 403


# --- notes ------------------------------------------------------------------


async def test_note_added_is_audited_with_excerpt_only(
    app_client, analyst, make_case, db_session
) -> None:
    user, h = analyst
    case = await make_case()
    body = "x" * 400
    r = await app_client.post(f"/api/v1/cases/{case.id}/notes", json={"body": body}, headers=h)
    assert r.status_code == 201
    out = r.json()
    assert out["body"] == body
    assert out["retracted"] is False
    assert out["author_id"] == str(user.id)

    note = (
        await db_session.execute(select(Note).where(Note.id == uuid.UUID(out["id"])))
    ).scalar_one()
    assert note.body == body  # full body persisted in ``notes``

    events = (
        (
            await db_session.execute(
                select(AuditEvent)
                .where(AuditEvent.stream == f"case:{case.id}")
                .order_by(AuditEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    added = [e for e in events if e.action == "case.note_added"]
    assert len(added) == 1
    assert added[0].target_type == "note"
    assert added[0].after == {"note_id": out["id"], "excerpt": body[:120]}
    assert len(added[0].after["excerpt"]) == 120


async def test_note_is_immutable_but_retractable(app_client, analyst, make_case) -> None:
    _, h = analyst
    case = await make_case()
    n = await app_client.post(
        f"/api/v1/cases/{case.id}/notes", json={"body": "checked device history"}, headers=h
    )
    nid = n.json()["id"]

    # No PATCH/PUT/DELETE route exists for a note.
    for method in ("DELETE", "PUT", "PATCH"):
        resp = await app_client.request(method, f"/api/v1/cases/{case.id}/notes/{nid}", headers=h)
        assert resp.status_code in (404, 405)

    r = await app_client.post(
        f"/api/v1/cases/{case.id}/notes/{nid}/retract",
        json={"reason": "posted on wrong case"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["retracted"] is True
    assert r.json()["retraction_reason"] == "posted on wrong case"


async def test_retract_is_idempotent(app_client, analyst, make_case, db_session) -> None:
    _, h = analyst
    case = await make_case()
    nid = (
        await app_client.post(f"/api/v1/cases/{case.id}/notes", json={"body": "note"}, headers=h)
    ).json()["id"]

    first = await app_client.post(
        f"/api/v1/cases/{case.id}/notes/{nid}/retract", json={"reason": "one"}, headers=h
    )
    second = await app_client.post(
        f"/api/v1/cases/{case.id}/notes/{nid}/retract", json={"reason": "two"}, headers=h
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["retraction_reason"] == "one"  # unchanged

    events = (
        (await db_session.execute(select(AuditEvent).where(AuditEvent.stream == f"case:{case.id}")))
        .scalars()
        .all()
    )
    assert len([e for e in events if e.action == "case.note_retracted"]) == 1


async def test_retract_by_other_analyst_is_forbidden(
    app_client, analyst, seed_principal, token_for, make_case
) -> None:
    _, h = analyst
    case = await make_case()
    nid = (
        await app_client.post(f"/api/v1/cases/{case.id}/notes", json={"body": "mine"}, headers=h)
    ).json()["id"]

    other = await seed_principal(roles=("analyst",))
    other_h = {"Authorization": f"Bearer {token_for(other)}"}
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/notes/{nid}/retract", json={"reason": "nope"}, headers=other_h
    )
    assert r.status_code == 403


async def test_retract_by_admin_is_allowed(
    app_client, analyst, seed_principal, token_for, make_case
) -> None:
    _, h = analyst
    case = await make_case()
    nid = (
        await app_client.post(f"/api/v1/cases/{case.id}/notes", json={"body": "mine"}, headers=h)
    ).json()["id"]

    admin = await seed_principal(roles=("admin",))
    admin_h = {"Authorization": f"Bearer {token_for(admin)}"}
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/notes/{nid}/retract",
        json={"reason": "supervisor override"},
        headers=admin_h,
    )
    assert r.status_code == 200
    assert r.json()["retracted"] is True


async def test_retract_note_not_on_case_is_404(app_client, analyst, make_case) -> None:
    _, h = analyst
    case_a = await make_case()
    case_b = await make_case()
    nid = (
        await app_client.post(f"/api/v1/cases/{case_a.id}/notes", json={"body": "on a"}, headers=h)
    ).json()["id"]

    r = await app_client.post(
        f"/api/v1/cases/{case_b.id}/notes/{nid}/retract", json={"reason": "x"}, headers=h
    )
    assert r.status_code == 404


async def test_retract_unknown_note_is_404(app_client, analyst, make_case) -> None:
    _, h = analyst
    case = await make_case()
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/notes/{uuid.uuid4()}/retract",
        json={"reason": "x"},
        headers=h,
    )
    assert r.status_code == 404


async def test_empty_note_body_is_422(app_client, analyst, make_case) -> None:
    _, h = analyst
    case = await make_case()
    r = await app_client.post(f"/api/v1/cases/{case.id}/notes", json={"body": ""}, headers=h)
    assert r.status_code == 422


async def test_empty_retract_reason_is_422(app_client, analyst, make_case) -> None:
    _, h = analyst
    case = await make_case()
    nid = (
        await app_client.post(f"/api/v1/cases/{case.id}/notes", json={"body": "n"}, headers=h)
    ).json()["id"]
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/notes/{nid}/retract", json={"reason": ""}, headers=h
    )
    assert r.status_code == 422


async def test_add_note_unknown_case_is_404(app_client, analyst) -> None:
    _, h = analyst
    r = await app_client.post(f"/api/v1/cases/{uuid.uuid4()}/notes", json={"body": "x"}, headers=h)
    assert r.status_code == 404


async def test_readonly_cannot_add_note(app_client, readonly_headers, make_case) -> None:
    case = await make_case()
    r = await app_client.post(
        f"/api/v1/cases/{case.id}/notes", json={"body": "x"}, headers=readonly_headers
    )
    assert r.status_code == 403


async def test_note_endpoints_require_auth(app_client, make_case) -> None:
    case = await make_case()
    assert (
        await app_client.post(f"/api/v1/cases/{case.id}/notes", json={"body": "x"})
    ).status_code == 401
    assert (
        await app_client.post(f"/api/v1/cases/{case.id}/assign", json={"assignee_id": None})
    ).status_code == 401
