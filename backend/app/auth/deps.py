"""FastAPI auth dependencies: JWT principal, role guards, ingest API-key guard.

Three primitives, used as ``Depends(...)`` on protected routes:

* :func:`get_current_principal` -- resolve ``Authorization: Bearer <jwt>`` to a
  :class:`Principal` (user id + email + role names loaded from the DB).
* :func:`require_role` -- dependency *factory*; guards a route so only principals
  holding at least one of ``allowed`` roles may enter. Never pass ``"readonly"``
  to a mutating endpoint's allowed set.
* :func:`require_ingest_key` -- validate an ``X-API-Key`` header against an active
  ``scope="ingest"`` row in ``api_keys`` (compared by SHA-256 digest, never
  plaintext).

Status contract: **401** for an absent / malformed / expired / non-access token,
a non-UUID ``sub``, or a ``sub`` with no user row; **403** only once a real user
is identified but is inactive (``is_active is False``) or lacks the required role.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import TokenError, decode_token, hash_api_key
from app.db import get_session
from app.models.user import ApiKey, User, UserRole

_SessionDep = Annotated[AsyncSession, Depends(get_session)]

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid_token",
    headers={"WWW-Authenticate": "Bearer"},
)


class Principal(BaseModel):
    """The authenticated caller behind a request: a user and their role names."""

    user_id: str
    email: str
    roles: list[str]


async def get_current_principal(
    session: _SessionDep,
    authorization: str | None = Header(default=None),
) -> Principal:
    """Resolve the bearer token on the request to a :class:`Principal`.

    Raises 401 for a missing/malformed header, an invalid/expired token, a
    non-access token, a non-UUID ``sub``, or a ``sub`` that matches no user.
    Raises 403 when the user exists but ``is_active`` is False.
    """
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise _UNAUTHENTICATED
    token = authorization[len("bearer ") :].strip()
    try:
        claims = decode_token(token)
    except TokenError as exc:
        raise _UNAUTHENTICATED from exc
    if claims.get("type") != "access":
        raise _UNAUTHENTICATED
    try:
        user_id = uuid.UUID(str(claims.get("sub")))
    except (ValueError, TypeError) as exc:
        raise _UNAUTHENTICATED from exc

    user = await session.get(User, user_id)
    if user is None:
        raise _UNAUTHENTICATED
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="inactive_user")

    roles = (
        (
            await session.execute(
                select(UserRole.role).where(UserRole.user_id == user.id).order_by(UserRole.role)
            )
        )
        .scalars()
        .all()
    )
    return Principal(user_id=str(user.id), email=user.email, roles=list(roles))


def require_role(*allowed: str) -> Callable[[Principal], Awaitable[Principal]]:
    """Build a dependency that admits only principals holding one of ``allowed``.

    403 (``"insufficient_role"``) when ``set(principal.roles).isdisjoint(allowed)``.
    """
    allowed_set = frozenset(allowed)

    async def _guard(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if allowed_set.isdisjoint(principal.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_role")
        return principal

    return _guard


async def require_ingest_key(
    session: _SessionDep,
    x_api_key: str | None = Header(default=None),
) -> ApiKey:
    """Validate the ``X-API-Key`` header against an active ingest key.

    401 (``"invalid_api_key"``) for a missing header or when no active
    ``scope="ingest"`` row matches the SHA-256 digest of the presented key.
    """
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")
    if not x_api_key:
        raise invalid
    api_key = (
        await session.execute(
            select(ApiKey).where(
                ApiKey.hashed_key == hash_api_key(x_api_key),
                ApiKey.scope == "ingest",
                ApiKey.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if api_key is None:
        raise invalid
    return api_key


__all__ = [
    "Principal",
    "get_current_principal",
    "require_ingest_key",
    "require_role",
]
