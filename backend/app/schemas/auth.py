"""Request / response bodies for the ``/api/v1/auth`` endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class TokenRequest(BaseModel):
    """Credentials for ``POST /auth/token``."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Body for ``POST /auth/refresh``."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Access + refresh token pair issued by ``POST /auth/token``."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    """Single access token issued by ``POST /auth/refresh``."""

    access_token: str
    token_type: str = "bearer"
