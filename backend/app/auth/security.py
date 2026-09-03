"""Password hashing (argon2) and JWT token minting / verification.

``hash_password`` / ``verify_password`` wrap :class:`argon2.PasswordHasher` with
its library defaults (no weakened time/memory/parallelism cost). Tokens are HS256
JWTs signed with ``Settings.jwt_secret``; ``decode_token`` raises
:class:`TokenError` for anything invalid, malformed, or expired.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError, VerifyMismatchError

from app.config import get_settings

_ph = PasswordHasher()

# A fixed argon2 hash to verify against when there is no real user, so an unknown
# / inactive email costs the same wall-clock time as a real failed login (no
# account-existence timing side-channel).
_DECOY_HASH = _ph.hash("acms-login-decoy-not-a-real-password")


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, badly signed, or expired."""


def hash_password(pw: str) -> str:
    """Return an argon2id hash (with embedded params + salt) for ``pw``."""
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    """Return ``True`` iff ``pw`` matches the argon2 hash ``hashed``."""
    try:
        return _ph.verify(hashed, pw)
    except (VerifyMismatchError, InvalidHashError, Argon2Error):
        # InvalidHashError subclasses ValueError (not Argon2Error): a malformed
        # stored hash must be a failed verification, never a 500.
        return False


def verify_password_or_dummy(pw: str, hashed: str | None) -> bool:
    """Verify ``pw`` against ``hashed``; if ``hashed`` is ``None`` still run an
    argon2 verification against a decoy hash and return ``False``.

    Callers use this on the login path so a missing user takes the same time as a
    wrong password, closing the account-enumeration timing side-channel.
    """
    if hashed is None:
        verify_password(pw, _DECOY_HASH)
        return False
    return verify_password(pw, hashed)


def _encode(payload: dict[str, Any], ttl: int) -> str:
    s = get_settings()
    now = int(time.time())
    return jwt.encode(
        {**payload, "iat": now, "exp": now + ttl},
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )


def create_access_token(sub: str, roles: list[str]) -> str:
    """Mint a short-lived access token carrying ``sub`` and ``roles``."""
    return _encode(
        {"sub": sub, "roles": roles, "type": "access"},
        get_settings().access_token_ttl_seconds,
    )


def create_refresh_token(sub: str) -> str:
    """Mint a long-lived refresh token for subject ``sub``."""
    return _encode({"sub": sub, "type": "refresh"}, get_settings().refresh_token_ttl_seconds)


def decode_token(token: str) -> dict[str, Any]:
    """Decode + verify ``token``; raise :class:`TokenError` if it is not valid."""
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc


def hash_api_key(raw: str) -> str:
    """Return the SHA-256 hex digest of ``raw``.

    API keys are high-entropy random strings, so a plain (fast) SHA-256 is the
    right primitive: no salt/stretching needed, and lookups stay a single indexed
    equality on the stored digest. Only the digest is ever persisted.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Mint a new ingest API key: return ``(raw, hashed)``.

    ``raw`` is shown to the caller exactly once; only ``hashed`` (see
    :func:`hash_api_key`) is stored on the ``api_keys`` row.
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_api_key(raw)
