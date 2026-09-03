"""RBAC dependency + ingest API-key auth tests.

``require_role`` is exercised as a pure dependency: a tiny in-test FastAPI app
exposes probe routes guarded by the dependency, and ``get_current_principal`` is
replaced with a ``dependency_overrides`` stub so no DB is touched.

``get_current_principal`` and ``require_ingest_key`` need real rows, so their
tests build an equally tiny probe app, override its ``get_session`` to yield the
test's ``db_session``, and seed ``User`` / ``ApiKey`` rows through that session.
Those tests are ``infra``-marked (they need the local Postgres from conftest).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.deps import (
    Principal,
    get_current_principal,
    require_ingest_key,
    require_role,
)
from app.auth.security import create_access_token, generate_api_key, hash_api_key
from app.db import get_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


# --- require_role: principal injected via dependency_overrides ----------------


def _role_app() -> FastAPI:
    app = FastAPI()

    @app.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    async def admin_only() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/analyst-or-admin",
        dependencies=[Depends(require_role("analyst", "admin"))],
    )
    async def analyst_or_admin() -> dict[str, bool]:
        return {"ok": True}

    return app


async def test_require_role_forbids_wrong_role() -> None:
    app = _role_app()
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id="u", email="e", roles=["analyst"]
    )
    async with _client(app) as c:
        r = await c.get("/admin-only")
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient_role"


async def test_require_role_allows_correct_role() -> None:
    app = _role_app()
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id="u", email="e", roles=["admin"]
    )
    async with _client(app) as c:
        r = await c.get("/admin-only")
    assert r.status_code == 200


async def test_require_role_allows_any_of_the_allowed_set() -> None:
    app = _role_app()
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id="u", email="e", roles=["analyst"]
    )
    async with _client(app) as c:
        r = await c.get("/analyst-or-admin")
    assert r.status_code == 200


async def test_require_role_forbids_when_no_roles() -> None:
    app = _role_app()
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id="u", email="e", roles=[]
    )
    async with _client(app) as c:
        r = await c.get("/analyst-or-admin")
    assert r.status_code == 403


# --- hash_api_key / generate_api_key -----------------------------------------


def test_hash_api_key_is_sha256_hex() -> None:
    assert hash_api_key("abc") == hashlib.sha256(b"abc").hexdigest()


def test_generate_api_key_returns_raw_and_matching_hash() -> None:
    raw, hashed = generate_api_key()
    assert raw
    assert hash_api_key(raw) == hashed
    other_raw, _ = generate_api_key()
    assert other_raw != raw


# --- get_current_principal: real user rows -----------------------------------


def _principal_app(db_session: AsyncSession) -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    async def me(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        return principal

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    return app


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.infra
async def test_get_current_principal_returns_user_and_roles(
    db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(roles=["analyst", "admin"])
    async with _client(_principal_app(db_session)) as c:
        r = await c.get("/me", headers=_bearer(token_for(user)))
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == str(user.id)
    assert body["email"] == user.email
    assert sorted(body["roles"]) == ["admin", "analyst"]


@pytest.mark.infra
async def test_get_current_principal_missing_header_is_401(db_session: AsyncSession) -> None:
    async with _client(_principal_app(db_session)) as c:
        r = await c.get("/me")
    assert r.status_code == 401


@pytest.mark.infra
async def test_get_current_principal_garbage_token_is_401(db_session: AsyncSession) -> None:
    async with _client(_principal_app(db_session)) as c:
        r = await c.get("/me", headers=_bearer("not-a-jwt"))
    assert r.status_code == 401


@pytest.mark.infra
async def test_get_current_principal_unknown_user_is_401(db_session: AsyncSession) -> None:
    token = create_access_token(sub=str(uuid.uuid4()), roles=["analyst"])
    async with _client(_principal_app(db_session)) as c:
        r = await c.get("/me", headers=_bearer(token))
    assert r.status_code == 401


@pytest.mark.infra
async def test_get_current_principal_non_uuid_sub_is_401(db_session: AsyncSession) -> None:
    token = create_access_token(sub="not-a-uuid", roles=["analyst"])
    async with _client(_principal_app(db_session)) as c:
        r = await c.get("/me", headers=_bearer(token))
    assert r.status_code == 401


@pytest.mark.infra
async def test_get_current_principal_refresh_token_is_401(
    db_session: AsyncSession, seed_principal
) -> None:
    from app.auth.security import create_refresh_token

    user = await seed_principal()
    async with _client(_principal_app(db_session)) as c:
        r = await c.get("/me", headers=_bearer(create_refresh_token(sub=str(user.id))))
    assert r.status_code == 401


@pytest.mark.infra
async def test_get_current_principal_inactive_user_is_403(
    db_session: AsyncSession, seed_principal, token_for
) -> None:
    user = await seed_principal(is_active=False)
    async with _client(_principal_app(db_session)) as c:
        r = await c.get("/me", headers=_bearer(token_for(user)))
    assert r.status_code == 403


# --- require_ingest_key: probe route + real ApiKey rows ---------------------


def _ingest_app(db_session: AsyncSession) -> FastAPI:
    app = FastAPI()

    @app.get("/probe", dependencies=[Depends(require_ingest_key)])
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    return app


@pytest.mark.infra
async def test_ingest_key_accepts_active_ingest_key(db_session: AsyncSession, make_api_key) -> None:
    raw = await make_api_key(active=True)
    async with _client(_ingest_app(db_session)) as c:
        r = await c.get("/probe", headers={"X-API-Key": raw})
    assert r.status_code == 200


@pytest.mark.infra
async def test_ingest_key_rejected_when_inactive(db_session: AsyncSession, make_api_key) -> None:
    raw = await make_api_key(active=False)
    async with _client(_ingest_app(db_session)) as c:
        r = await c.get("/probe", headers={"X-API-Key": raw})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_api_key"


@pytest.mark.infra
async def test_ingest_key_rejected_when_unknown(db_session: AsyncSession) -> None:
    async with _client(_ingest_app(db_session)) as c:
        r = await c.get("/probe", headers={"X-API-Key": "totally-unknown"})
    assert r.status_code == 401


@pytest.mark.infra
async def test_ingest_key_rejected_when_header_missing(db_session: AsyncSession) -> None:
    async with _client(_ingest_app(db_session)) as c:
        r = await c.get("/probe")
    assert r.status_code == 401


@pytest.mark.infra
async def test_ingest_key_rejected_for_wrong_scope(db_session: AsyncSession, make_api_key) -> None:
    raw = await make_api_key(active=True, scope="admin")
    async with _client(_ingest_app(db_session)) as c:
        r = await c.get("/probe", headers={"X-API-Key": raw})
    assert r.status_code == 401


@pytest.mark.infra
async def test_ingest_key_stores_only_the_hash(db_session: AsyncSession, make_api_key) -> None:
    from sqlalchemy import select

    from app.models.user import ApiKey

    raw = await make_api_key(active=True)
    rows = (await db_session.execute(select(ApiKey.hashed_key))).scalars().all()
    assert raw not in rows
    assert hash_api_key(raw) in rows
