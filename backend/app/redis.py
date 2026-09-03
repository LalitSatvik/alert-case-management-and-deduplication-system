"""Redis connection helper exposed as a FastAPI dependency.

``get_redis`` yields a short-lived ``redis.asyncio.Redis`` built from
``Settings.redis_url`` with ``decode_responses=True`` (so callers get ``str``
back, not ``bytes``) and closes it when the request finishes. Tests override this
dependency to point at the throwaway logical DB 15.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from redis.asyncio import Redis, from_url

from app.config import get_settings

__all__ = ["get_redis"]


async def get_redis() -> AsyncIterator[Redis]:
    """Yield a decode-responses Redis client for one request, then close it."""
    client: Redis = from_url(  # type: ignore[no-untyped-call]
        get_settings().redis_url, decode_responses=True
    )
    try:
        yield client
    finally:
        await client.aclose()
