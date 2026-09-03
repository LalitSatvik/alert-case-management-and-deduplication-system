"""``/api/v1/auth`` endpoints: password login and refresh-token exchange."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password_or_dummy,
)
from app.config import get_settings
from app.db import get_session
from app.models.user import User, UserRole
from app.ratelimit import rate_limit
from app.redis import get_redis
from app.schemas.auth import (
    AccessTokenResponse,
    RefreshRequest,
    TokenRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _auth_rate_limit(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
) -> None:
    """NFR-SEC-08: per-client-IP fixed-window ceiling on the credential endpoints."""
    client_ip = request.client.host if request.client is not None else "unknown"
    await rate_limit(
        redis,
        f"auth:{client_ip}",
        get_settings().auth_rate_limit_per_minute,
        60,
    )


_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
)


async def _roles_for(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await session.execute(
        select(UserRole.role).where(UserRole.user_id == user_id).order_by(UserRole.role)
    )
    return list(result.scalars().all())


@router.post(
    "/token",
    response_model=TokenResponse,
    dependencies=[Depends(_auth_rate_limit)],
)
async def issue_token(body: TokenRequest, session: SessionDep) -> TokenResponse:
    """Verify email + password and return an access/refresh token pair."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    hashed = user.password_hash if (user is not None and user.is_active) else None
    # Always run the verify (decoy hash when hashed is None) so a missing/inactive
    # account costs the same time as a wrong password.
    password_ok = verify_password_or_dummy(body.password, hashed)
    if user is None or not password_ok:
        raise _INVALID_CREDENTIALS
    roles = await _roles_for(session, user.id)
    return TokenResponse(
        access_token=create_access_token(sub=str(user.id), roles=roles),
        refresh_token=create_refresh_token(sub=str(user.id)),
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    dependencies=[Depends(_auth_rate_limit)],
)
async def refresh(body: RefreshRequest, session: SessionDep) -> AccessTokenResponse:
    """Exchange a valid refresh token for a fresh access token."""
    try:
        claims = decode_token(body.refresh_token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        ) from exc
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not a refresh token")
    try:
        user_id = uuid.UUID(str(claims.get("sub")))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid subject"
        ) from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown or inactive user"
        )
    roles = await _roles_for(session, user.id)
    return AccessTokenResponse(access_token=create_access_token(sub=str(user.id), roles=roles))
