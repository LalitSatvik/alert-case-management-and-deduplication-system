"""A merge non-survivor (``status == "Merged"``) is read-only (fix M1, FR-OVR-01).

``add_note`` / ``assign_case`` now load the case ``FOR UPDATE`` and raise
``CaseReadOnly`` -> ``409`` when it is Merged; non-Merged cases are unaffected.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.infra


@pytest.fixture
async def analyst_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("analyst",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


async def test_note_on_merged_case_is_409(app_client, analyst_headers, make_case) -> None:
    merged = await make_case(status="Merged")
    r = await app_client.post(
        f"/api/v1/cases/{merged.id}/notes",
        json={"body": "should be blocked"},
        headers=analyst_headers,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "case_read_only"


async def test_assign_on_merged_case_is_409(
    app_client, analyst_headers, make_case, admin_user
) -> None:
    merged = await make_case(status="Merged")
    r = await app_client.post(
        f"/api/v1/cases/{merged.id}/assign",
        json={"assignee_id": str(admin_user.id)},
        headers=analyst_headers,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "case_read_only"


async def test_note_and_assign_on_open_case_unaffected(
    app_client, analyst_headers, make_case, admin_user
) -> None:
    case = await make_case(status="Open")
    note = await app_client.post(
        f"/api/v1/cases/{case.id}/notes", json={"body": "ok"}, headers=analyst_headers
    )
    assert note.status_code == 201
    assign = await app_client.post(
        f"/api/v1/cases/{case.id}/assign",
        json={"assignee_id": str(admin_user.id)},
        headers=analyst_headers,
    )
    assert assign.status_code == 200


async def test_note_on_missing_case_still_404(app_client, analyst_headers) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{uuid.uuid4()}/notes", json={"body": "x"}, headers=analyst_headers
    )
    assert r.status_code == 404
