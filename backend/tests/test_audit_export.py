"""Integration tests for ``POST /api/v1/cases/{case_id}/audit:export``.

Drives the real ASGI app through ``app_client``; tokens come from a *seeded*
principal (``seed_principal`` + ``token_for``). Exercises both the JSON bundle
and the self-contained HTML render, plus the XSS-safety guarantee on the HTML.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
async def analyst_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(  # type: ignore[operator]
        roles=("analyst",), email="export-analyst@example.com"
    )
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


async def test_json_export_contains_full_before_after(
    app_client, analyst_headers, worked_case
) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{worked_case.id}/audit:export",
        params={"format": "json"},
        headers=analyst_headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    bundle = r.json()

    assert bundle["chain_verified"] is True
    assert bundle["case"]["id"] == str(worked_case.id)
    assert bundle["case"]["status"] == "In Progress"
    assert bundle["generated_at"]

    assert any("before" in e and "after" in e for e in bundle["audit_events"])
    transitioned = [e for e in bundle["audit_events"] if e["action"] == "case.transitioned"]
    assert transitioned
    assert transitioned[0]["before"]["status"] == "Open"
    assert transitioned[0]["after"]["status"] == "In Progress"


async def test_json_export_has_alerts_with_grouping_and_all_notes(
    app_client, analyst_headers, worked_case
) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{worked_case.id}/audit:export",
        params={"format": "json"},
        headers=analyst_headers,
    )
    bundle = r.json()

    assert len(bundle["alerts"]) >= 2
    for alert in bundle["alerts"]:
        assert alert["grouping"] is not None
        assert alert["grouping"]["method"] in (
            "deterministic",
            "similarity",
            "singleton",
            "manual",
        )
        assert alert["grouping"]["engine_version"]
        assert alert["grouping"]["config_hash"]

    assert len(bundle["notes"]) >= 1
    assert all(
        {"id", "author_id", "body", "retracted", "created_at"} <= n.keys() for n in bundle["notes"]
    )


async def test_export_is_itself_audited(app_client, analyst_headers, worked_case) -> None:
    await app_client.post(
        f"/api/v1/cases/{worked_case.id}/audit:export",
        params={"format": "html"},
        headers=analyst_headers,
    )
    audit = await app_client.get(f"/api/v1/cases/{worked_case.id}/audit", headers=analyst_headers)
    events = audit.json()
    exported = [e for e in events if e["action"] == "case.audit_exported"]
    assert exported
    assert exported[-1]["after"] == {"format": "html"}
    assert exported[-1]["actor_id"] is not None


async def test_html_export_is_self_contained(app_client, analyst_headers, worked_case) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{worked_case.id}/audit:export",
        params={"format": "html"},
        headers=analyst_headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<link" not in r.text
    assert "http://" not in r.text
    assert "https://" not in r.text
    assert "<script src" not in r.text
    assert "<!DOCTYPE html>" in r.text
    assert "chain verified" in r.text.lower()


async def test_html_export_escapes_note_body(app_client, analyst_headers, worked_case) -> None:
    payload = {"body": "<script>alert(1)</script> and <b>bold</b>"}
    posted = await app_client.post(
        f"/api/v1/cases/{worked_case.id}/notes", json=payload, headers=analyst_headers
    )
    assert posted.status_code == 201

    r = await app_client.post(
        f"/api/v1/cases/{worked_case.id}/audit:export",
        params={"format": "html"},
        headers=analyst_headers,
    )
    assert "&lt;script&gt;" in r.text
    assert "<script>alert" not in r.text


async def test_export_unknown_case_is_404(app_client, analyst_headers) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{uuid.uuid4()}/audit:export",
        params={"format": "json"},
        headers=analyst_headers,
    )
    assert r.status_code == 404


async def test_export_requires_a_role(app_client, worked_case) -> None:
    r = await app_client.post(
        f"/api/v1/cases/{worked_case.id}/audit:export", params={"format": "json"}
    )
    assert r.status_code == 401
