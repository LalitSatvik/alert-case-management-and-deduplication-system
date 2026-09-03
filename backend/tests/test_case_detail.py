"""Integration tests for ``GET /api/v1/cases/{case_id}`` -- the detail view.

Drives the real ASGI app through ``app_client``; tokens come from a *seeded*
principal (``seed_principal`` + ``token_for``).
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
async def analyst_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("analyst",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


async def test_detail_includes_grouped_alerts_with_rationale(
    app_client, analyst_headers, grouped_case
) -> None:
    r = await app_client.get(f"/api/v1/cases/{grouped_case.id}", headers=analyst_headers)
    assert r.status_code == 200
    body = r.json()

    assert body["alert_count"] == len(body["alerts"])
    assert len(body["alerts"]) >= 2

    # Every linked alert carries its grouping rationale ...
    assert all(a["grouping"] is not None for a in body["alerts"])
    for a in body["alerts"]:
        assert a["grouping"]["method"] in ("deterministic", "similarity", "singleton", "manual")
        assert a["grouping"]["engine_version"]
        assert a["grouping"]["config_hash"]
    # ... and at least one is a real multi-alert match, not a singleton.
    methods = {a["grouping"]["method"] for a in body["alerts"]}
    assert methods & {"deterministic", "similarity"}

    # Newest audit entry present, and the timeline is newest-first.
    assert body["timeline"][0]["action"]
    seqs = [e["seq"] for e in body["timeline"]]
    assert seqs == sorted(seqs, reverse=True)


async def test_detail_notes_include_retracted_and_timeline_newest_first(
    app_client, analyst_headers, make_case
) -> None:
    case = await make_case(status="Open")
    cid = case.id
    await app_client.post(
        f"/api/v1/cases/{cid}/notes", json={"body": "first note"}, headers=analyst_headers
    )
    n2 = (
        await app_client.post(
            f"/api/v1/cases/{cid}/notes", json={"body": "second note"}, headers=analyst_headers
        )
    ).json()
    await app_client.post(
        f"/api/v1/cases/{cid}/notes/{n2['id']}/retract",
        json={"reason": "posted on wrong case"},
        headers=analyst_headers,
    )
    await app_client.post(
        f"/api/v1/cases/{cid}/transition", json={"to": "In Progress"}, headers=analyst_headers
    )

    body = (await app_client.get(f"/api/v1/cases/{cid}", headers=analyst_headers)).json()

    # notes: all of them (retracted included).
    assert {n["body"] for n in body["notes"]} == {"first note", "second note"}
    retracted = [n for n in body["notes"] if n["retracted"]]
    assert len(retracted) == 1
    assert retracted[0]["body"] == "second note"
    assert retracted[0]["retraction_reason"] == "posted on wrong case"

    # timeline: newest-first, and covers every recorded action.
    seqs = [e["seq"] for e in body["timeline"]]
    assert seqs == sorted(seqs, reverse=True)
    actions = {e["action"] for e in body["timeline"]}
    assert {"case.note_added", "case.note_retracted", "case.transitioned"} <= actions


async def test_detail_unknown_case_is_404(app_client, analyst_headers) -> None:
    r = await app_client.get(f"/api/v1/cases/{uuid.uuid4()}", headers=analyst_headers)
    assert r.status_code == 404


async def test_detail_non_uuid_is_422(app_client, analyst_headers) -> None:
    r = await app_client.get("/api/v1/cases/not-a-uuid", headers=analyst_headers)
    assert r.status_code == 422


async def test_detail_readonly_allowed(app_client, seed_principal, token_for, make_case) -> None:
    user = await seed_principal(roles=("readonly",))
    headers = {"Authorization": f"Bearer {token_for(user)}"}
    case = await make_case(status="Open")
    r = await app_client.get(f"/api/v1/cases/{case.id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["alerts"] == []
    assert r.json()["notes"] == []


async def test_detail_requires_auth(app_client, make_case) -> None:
    case = await make_case(status="Open")
    assert (await app_client.get(f"/api/v1/cases/{case.id}")).status_code == 401
