import pytest

from app.auth.security import (
    TokenError,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_access_token_carries_roles():
    tok = create_access_token(sub="user-1", roles=["analyst"])
    claims = decode_token(tok)
    assert claims["sub"] == "user-1"
    assert claims["roles"] == ["analyst"]
    assert claims["type"] == "access"


def test_decode_rejects_garbage():
    with pytest.raises(TokenError):
        decode_token("not-a-jwt")


@pytest.mark.infra
async def test_token_endpoint_issues_jwt(app_client, seed_user):
    # seed_user fixture (in conftest) inserts a user with password "pw" and role "analyst"
    r = await app_client.post(
        "/api/v1/auth/token", json={"email": seed_user.email, "password": "pw"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert decode_token(body["access_token"])["roles"] == ["analyst"]


@pytest.mark.infra
async def test_token_endpoint_rejects_bad_password(app_client, seed_user):
    r = await app_client.post(
        "/api/v1/auth/token", json={"email": seed_user.email, "password": "nope"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


@pytest.mark.infra
async def test_token_endpoint_unknown_email_is_401(app_client):
    # No user row -> decoy-hash verify still runs, same single 401.
    r = await app_client.post(
        "/api/v1/auth/token", json={"email": "nobody@example.com", "password": "pw"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


@pytest.mark.infra
async def test_token_endpoint_inactive_user_is_401(app_client, db_session, seed_user):
    seed_user.is_active = False
    await db_session.commit()
    r = await app_client.post(
        "/api/v1/auth/token", json={"email": seed_user.email, "password": "pw"}
    )
    assert r.status_code == 401


@pytest.mark.infra
async def test_refresh_endpoint_issues_new_access_token(app_client, seed_user):
    r = await app_client.post(
        "/api/v1/auth/token", json={"email": seed_user.email, "password": "pw"}
    )
    refresh = r.json()["refresh_token"]
    r2 = await app_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    body = r2.json()
    assert body["token_type"] == "bearer"
    claims = decode_token(body["access_token"])
    assert claims["type"] == "access"
    assert claims["roles"] == ["analyst"]


@pytest.mark.infra
async def test_refresh_endpoint_rejects_access_token(app_client, seed_user):
    r = await app_client.post(
        "/api/v1/auth/token", json={"email": seed_user.email, "password": "pw"}
    )
    access = r.json()["access_token"]
    r2 = await app_client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert r2.status_code == 401
