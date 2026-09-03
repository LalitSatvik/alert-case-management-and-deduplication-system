"""Integration tests for ``GET /api/v1/cases`` -- list / search / filter / paginate.

These drive the real ASGI app through ``app_client`` so ``require_role`` +
``get_current_principal`` run for real; tokens come from a *seeded* principal
(``seed_principal`` + ``token_for``), not the bare ``analyst_token`` fixture
(random ``sub``, no DB row -> 401).
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def analyst_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("analyst",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


@pytest.fixture
async def readonly_headers(seed_principal: object, token_for: object) -> dict[str, str]:
    user = await seed_principal(roles=("readonly",))  # type: ignore[operator]
    return {"Authorization": f"Bearer {token_for(user)}"}  # type: ignore[operator]


# --- filters ---------------------------------------------------------------


async def test_filter_by_status_and_assignee(app_client, analyst_headers, cases_fixture) -> None:
    r = await app_client.get(
        "/api/v1/cases",
        params={"status": "Open", "assignee_id": "unassigned"},
        headers=analyst_headers,
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


async def test_filter_by_assignee_uuid(app_client, analyst_headers, cases_fixture) -> None:
    analyst = cases_fixture["analyst"]
    r = await app_client.get(
        "/api/v1/cases", params={"assignee_id": str(analyst.id)}, headers=analyst_headers
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "In Progress"
    assert items[0]["assignee_email"] == analyst.email


async def test_invalid_assignee_id_is_422(app_client, analyst_headers) -> None:
    r = await app_client.get(
        "/api/v1/cases", params={"assignee_id": "not-a-uuid"}, headers=analyst_headers
    )
    assert r.status_code == 422


async def test_filter_by_risk_range(app_client, analyst_headers, make_case) -> None:
    await make_case(status="Open", risk_score=10)
    await make_case(status="Open", risk_score=55)
    await make_case(status="Open", risk_score=95)
    r = await app_client.get(
        "/api/v1/cases", params={"risk_min": 50, "risk_max": 90}, headers=analyst_headers
    )
    scores = [i["risk_score"] for i in r.json()["items"]]
    assert scores == [55]


async def test_filter_by_source_system(app_client, analyst_headers, case_with_merchant) -> None:
    r = await app_client.get(
        "/api/v1/cases", params={"source_system": "grouping-test"}, headers=analyst_headers
    )
    assert any(i["id"] == str(case_with_merchant.id) for i in r.json()["items"])
    r2 = await app_client.get(
        "/api/v1/cases", params={"source_system": "no-such-system"}, headers=analyst_headers
    )
    assert all(i["id"] != str(case_with_merchant.id) for i in r2.json()["items"])


async def test_filter_by_typology(app_client, analyst_headers, case_with_merchant) -> None:
    r = await app_client.get(
        "/api/v1/cases", params={"typology": "structuring"}, headers=analyst_headers
    )
    assert any(i["id"] == str(case_with_merchant.id) for i in r.json()["items"])


# --- full-text search -----------------------------------------------------


async def test_full_text_search_matches_merchant(
    app_client, analyst_headers, case_with_merchant
) -> None:
    r = await app_client.get("/api/v1/cases", params={"q": "quickcash"}, headers=analyst_headers)
    assert r.status_code == 200
    assert any(i["id"] == str(case_with_merchant.id) for i in r.json()["items"])


async def test_full_text_search_matches_note_body(app_client, analyst_headers, make_case) -> None:
    case = await make_case(status="Open")
    await app_client.post(
        f"/api/v1/cases/{case.id}/notes",
        json={"body": "suspected zelophehad laundering ring"},
        headers=analyst_headers,
    )
    r = await app_client.get("/api/v1/cases", params={"q": "zelophehad"}, headers=analyst_headers)
    assert any(i["id"] == str(case.id) for i in r.json()["items"])


async def test_full_text_search_matches_customer_and_account_ref(
    app_client, analyst_headers, make_case, make_alert, db_session
) -> None:
    """FR-SRCH-02 (fix M5): ``q`` also searches a linked alert's customer/account ref."""
    from datetime import UTC, datetime

    from app.models.case import CaseAlertLink
    from app.models.grouping import GroupingDecision

    case = await make_case(status="Open")
    alert = await make_alert(customer_ref="CUSTZEBRA9", account_ref="ACCTGIRAFFE7")
    now = datetime.now(UTC)
    decision = GroupingDecision(
        alert_id=alert.id,
        case_id=case.id,
        method="deterministic",
        matched_rule_ids=[],
        similarity_score=None,
        feature_contributions={},
        engine_version="t",
        config_hash="t",
        created_at=now,
    )
    db_session.add(decision)
    await db_session.flush()
    alert.case_id = case.id
    db_session.add(
        CaseAlertLink(
            case_id=case.id,
            alert_id=alert.id,
            grouping_decision_id=decision.id,
            linked_at=now,
            linked_by="t",
        )
    )
    await db_session.flush()

    for term in ("CUSTZEBRA9", "ACCTGIRAFFE7"):
        r = await app_client.get("/api/v1/cases", params={"q": term}, headers=analyst_headers)
        assert r.status_code == 200
        assert any(i["id"] == str(case.id) for i in r.json()["items"]), term


async def test_full_text_search_matches_human_ref(app_client, analyst_headers, make_case) -> None:
    case = await make_case(status="Open", human_ref="CASE-ZEBRA1")
    r = await app_client.get("/api/v1/cases", params={"q": "CASE-ZEBRA1"}, headers=analyst_headers)
    assert any(i["id"] == str(case.id) for i in r.json()["items"])


async def test_full_text_search_excludes_non_matches(
    app_client, analyst_headers, case_with_merchant, make_case
) -> None:
    other = await make_case(status="Open")
    r = await app_client.get("/api/v1/cases", params={"q": "quickcash"}, headers=analyst_headers)
    ids = {i["id"] for i in r.json()["items"]}
    assert str(case_with_merchant.id) in ids
    assert str(other.id) not in ids


# --- sort + pagination --------------------------------------------------


async def test_sort_by_risk_desc_is_default(app_client, analyst_headers, make_case) -> None:
    await make_case(status="Open", risk_score=10)
    await make_case(status="Open", risk_score=90)
    await make_case(status="Open", risk_score=50)
    r = await app_client.get("/api/v1/cases", headers=analyst_headers)
    scores = [i["risk_score"] for i in r.json()["items"]]
    assert scores == sorted(scores, reverse=True)


async def test_pagination_is_stable(app_client, analyst_headers, many_cases) -> None:
    h = analyst_headers
    p1 = (await app_client.get("/api/v1/cases", params={"limit": 10}, headers=h)).json()
    assert len(p1["items"]) == 10
    assert p1["next_cursor"]
    p2 = (
        await app_client.get(
            "/api/v1/cases", params={"limit": 10, "cursor": p1["next_cursor"]}, headers=h
        )
    ).json()
    ids1 = {i["id"] for i in p1["items"]}
    ids2 = {i["id"] for i in p2["items"]}
    assert ids1.isdisjoint(ids2)
    assert len(ids2) == 10


async def test_pagination_walks_every_row_once(app_client, analyst_headers, many_cases) -> None:
    h = analyst_headers
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(20):
        params: dict[str, object] = {"limit": 7}
        if cursor is not None:
            params["cursor"] = cursor
        page = (await app_client.get("/api/v1/cases", params=params, headers=h)).json()
        seen.extend(i["id"] for i in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(many_cases)
    assert len(set(seen)) == len(many_cases)


async def test_pagination_sorted_by_oldest_alert(
    app_client, analyst_headers, case_with_merchant, make_case
) -> None:
    await make_case(status="Open")
    r = await app_client.get(
        "/api/v1/cases", params={"sort": "oldest_alert", "limit": 50}, headers=analyst_headers
    )
    assert r.status_code == 200
    times = [i["oldest_alert_event_time"] for i in r.json()["items"]]
    non_null = [t for t in times if t is not None]
    assert non_null == sorted(non_null)


async def test_bad_cursor_is_400(app_client, analyst_headers) -> None:
    r = await app_client.get(
        "/api/v1/cases", params={"cursor": "!!!not-base64!!!"}, headers=analyst_headers
    )
    assert r.status_code == 400


def _make_cursor(value: object, case_id: str = "00000000-0000-0000-0000-000000000001") -> str:
    import base64
    import json

    return base64.urlsafe_b64encode(json.dumps({"v": value, "id": case_id}).encode("utf-8")).decode(
        "ascii"
    )


async def test_cursor_from_other_sort_is_400(app_client, analyst_headers, many_cases) -> None:
    """A page-1 cursor issued under ``-risk_score`` (v=int) must not 500 a
    ``-created_at`` request -- it is a clean 400."""
    h = analyst_headers
    p1 = (await app_client.get("/api/v1/cases", params={"limit": 5}, headers=h)).json()
    assert p1["next_cursor"]
    r = await app_client.get(
        "/api/v1/cases",
        params={"limit": 5, "cursor": p1["next_cursor"], "sort": "-created_at"},
        headers=h,
    )
    assert r.status_code == 400


async def test_cursor_bad_datetime_value_is_400(app_client, analyst_headers) -> None:
    r = await app_client.get(
        "/api/v1/cases",
        params={"cursor": _make_cursor("notadate"), "sort": "oldest_alert"},
        headers=analyst_headers,
    )
    assert r.status_code == 400


async def test_oldest_alert_null_cursor_under_risk_sort_is_400(app_client, analyst_headers) -> None:
    r = await app_client.get(
        "/api/v1/cases",
        params={"cursor": _make_cursor(None), "sort": "-risk_score"},
        headers=analyst_headers,
    )
    assert r.status_code == 400


# --- authz --------------------------------------------------------------


async def test_readonly_can_list(app_client, readonly_headers, cases_fixture) -> None:
    r = await app_client.get("/api/v1/cases", headers=readonly_headers)
    assert r.status_code == 200


async def test_list_requires_auth(app_client) -> None:
    assert (await app_client.get("/api/v1/cases")).status_code == 401
