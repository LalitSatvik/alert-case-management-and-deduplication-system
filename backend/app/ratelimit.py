"""Minimal Valkey/Redis fixed-window rate limiter (NFR-SEC-08).

One counter per ``(bucket_key, current window)``: ``INCR`` the counter and, on the
first hit (``== 1``), set its TTL to the window length. When the counter exceeds
``limit`` the request is rejected with ``429`` and a ``Retry-After`` header.

Fail-open, matching the idempotency layer's posture: any
``redis.exceptions.RedisError`` is logged (``ratelimit.redis_unavailable``) and
the request is allowed through. A rate limiter that hard-fails closed would turn
a Redis blip into a full outage of login and ingestion.
"""

from __future__ import annotations

import structlog
from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

__all__ = ["rate_limit"]

_PREFIX = "ratelimit:"
_log = structlog.get_logger("ratelimit")


async def rate_limit(redis: Redis, bucket_key: str, limit: int, window_seconds: int) -> None:
    """Count one hit against ``bucket_key``; raise ``429`` when the window is over ``limit``.

    Fail-open on any :class:`RedisError`.
    """
    key = _PREFIX + bucket_key
    try:
        count = int(await redis.incr(key))
        if count == 1:
            await redis.expire(key, window_seconds)
        ttl = int(await redis.ttl(key)) if count > limit else window_seconds
    except RedisError as exc:
        _log.warning("ratelimit.redis_unavailable", bucket=bucket_key, error=str(exc))
        return

    if count > limit:
        retry_after = ttl if ttl and ttl > 0 else window_seconds
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
            headers={"Retry-After": str(retry_after)},
        )
