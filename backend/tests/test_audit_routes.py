"""``/api/v1`` audit endpoint tests.

All infra-marked: they drive the real ``create_app()`` through ``app_client``
(which shares the test's ``db_session``), and ``require_role`` ->
``get_current_principal`` loads a real ``User`` row, so every request needs a
seeded principal + matching token.

Tampering is injected the way the least-privilege ``app_user`` role actually
permits: ``audit_events`` is INSERT-only (append a bogus event to break the
chain) and ``audit_streams`` is UPDATE-able (corrupt the tip anchor). Neither
table can be UPDATE/DELETE-d / DELETE-d respectively -- that is the whole point
of the grants migration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from app.audit.service import GENESIS_HASH, record_audit

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.infra


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _record(session: AsyncSession, stream: str, n: int) -> None:
    for i in range(n):
        await record_audit(
            session,
            stream=stream,
            actor=None,
            action=f"a{i}",
            target_type="case",
            target_id=stream.split(":", 1)[1],
        )
    await session.commit()


# --- GET /api/v1/audit -------------------------------------------------------


async def test_readonly_can_query_audit(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["readonly"])
    r = await app_client.get("/api/v1/audit", headers=_bearer(token_for(user)))
    assert r.status_code == 200
    assert r.json() == {"items": [], "next_cursor": None}


async def test_admin_can_query_audit(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["admin"])
    await _record(db_session, "case:q1", 2)
    r = await app_client.get("/api/v1/audit", headers=_bearer(token_for(user)))
    assert r.status_code == 200
    body = r.json()
    assert [e["action"] for e in body["items"]] == ["a1", "a0"]  # newest first


async def test_analyst_forbidden_from_query_audit(
    app_client: AsyncClient, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["analyst"])
    r = await app_client.get("/api/v1/audit", headers=_bearer(token_for(user)))
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient_role"


async def test_query_audit_requires_auth(app_client: AsyncClient) -> None:
    assert (await app_client.get("/api/v1/audit")).status_code == 401


async def test_query_audit_filters_and_paginates(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["admin"])
    await _record(db_session, "case:p1", 3)
    await _record(db_session, "case:p2", 1)
    hdr = _bearer(token_for(user))

    r = await app_client.get("/api/v1/audit", params={"target_type": "case"}, headers=hdr)
    assert len(r.json()["items"]) == 4

    r1 = await app_client.get("/api/v1/audit", params={"limit": 2}, headers=hdr)
    body1 = r1.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None

    r2 = await app_client.get(
        "/api/v1/audit", params={"limit": 2, "cursor": body1["next_cursor"]}, headers=hdr
    )
    body2 = r2.json()
    assert len(body2["items"]) == 2
    first_ids = {e["id"] for e in body1["items"]}
    assert first_ids.isdisjoint({e["id"] for e in body2["items"]})


# --- GET /api/v1/cases/{case_id}/audit --------------------------------------


async def test_case_audit_returns_stream_ordered_by_seq(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["analyst"])
    await _record(db_session, "case:abc", 3)
    r = await app_client.get("/api/v1/cases/abc/audit", headers=_bearer(token_for(user)))
    assert r.status_code == 200
    assert [e["seq"] for e in r.json()] == [1, 2, 3]


async def test_case_audit_empty_for_unknown_case(
    app_client: AsyncClient, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["readonly"])
    r = await app_client.get("/api/v1/cases/nope/audit", headers=_bearer(token_for(user)))
    assert r.status_code == 200
    assert r.json() == []


# --- POST /api/v1/audit:verify --------------------------------------------


async def test_verify_clean_db_reports_nothing_broken(
    app_client: AsyncClient, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["admin"])
    r = await app_client.post("/api/v1/audit:verify", headers=_bearer(token_for(user)))
    assert r.status_code == 200
    assert r.json() == {"streams_checked": 0, "broken": []}


async def test_verify_intact_streams_are_clean(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["admin"])
    await _record(db_session, "case:v1", 3)
    await _record(db_session, "case:v2", 1)
    r = await app_client.post("/api/v1/audit:verify", headers=_bearer(token_for(user)))
    body = r.json()
    assert body["streams_checked"] == 2
    assert body["broken"] == []


async def test_verify_detects_broken_chain(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["admin"])
    await _record(db_session, "case:v3", 2)
    # app_user can INSERT into audit_events -> append a bogus seq 3 with garbage links.
    await db_session.execute(
        text(
            "INSERT INTO audit_events "
            "(stream, seq, prev_hash, hash, action, target_type, target_id, created_at) "
            "VALUES ('case:v3', 3, :g, 'deadbeef', 'x', 'case', 'v3', now())"
        ),
        {"g": GENESIS_HASH},
    )
    await db_session.commit()
    r = await app_client.post("/api/v1/audit:verify", headers=_bearer(token_for(user)))
    broken = r.json()["broken"]
    assert len(broken) == 1
    assert broken[0]["stream"] == "case:v3"
    assert broken[0]["reason"] == "chain"
    assert 3 in broken[0]["seqs"]


async def test_verify_detects_tip_hash_rewrite(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["admin"])
    await _record(db_session, "case:v4", 2)
    # app_user can UPDATE audit_streams -> corrupt only the tip anchor.
    await db_session.execute(
        text("UPDATE audit_streams SET last_hash = :h WHERE stream = 'case:v4'"),
        {"h": "f" * 64},
    )
    await db_session.commit()
    r = await app_client.post("/api/v1/audit:verify", headers=_bearer(token_for(user)))
    broken = r.json()["broken"]
    assert len(broken) == 1
    assert broken[0]["reason"] == "tip_mismatch"


async def test_verify_detects_count_mismatch(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["admin"])
    await _record(db_session, "case:v5", 2)
    await db_session.execute(text("UPDATE audit_streams SET last_seq = 5 WHERE stream = 'case:v5'"))
    await db_session.commit()
    r = await app_client.post("/api/v1/audit:verify", headers=_bearer(token_for(user)))
    broken = r.json()["broken"]
    assert len(broken) == 1
    assert broken[0]["reason"] == "count_mismatch"


async def test_verify_detects_orphan_stream_with_no_tip_row(
    app_client: AsyncClient, db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["admin"])
    # app_user has unrestricted INSERT on audit_events: forge events under a
    # stream key that has NO audit_streams tip row.
    await db_session.execute(
        text(
            "INSERT INTO audit_events "
            "(stream, seq, prev_hash, hash, action, target_type, target_id, created_at) "
            "VALUES ('forged:1', 1, :g, 'h1', 'x', 'case', '1', now())"
        ),
        {"g": GENESIS_HASH},
    )
    await db_session.commit()
    r = await app_client.post("/api/v1/audit:verify", headers=_bearer(token_for(user)))
    body = r.json()
    assert body["streams_checked"] == 1
    assert len(body["broken"]) == 1
    assert body["broken"][0]["stream"] == "forged:1"
    assert body["broken"][0]["reason"] == "orphan_stream"
    assert body["broken"][0]["seqs"] == [1]


async def test_analyst_forbidden_from_verify(
    app_client: AsyncClient, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["analyst"])
    r = await app_client.post("/api/v1/audit:verify", headers=_bearer(token_for(user)))
    assert r.status_code == 403


async def test_readonly_forbidden_from_verify(
    app_client: AsyncClient, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["readonly"])
    r = await app_client.post("/api/v1/audit:verify", headers=_bearer(token_for(user)))
    assert r.status_code == 403
