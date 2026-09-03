"""The generated OpenAPI schema lists every core route.

A cheap contract check: if a router stops being registered (or a path changes
shape), ``GET /api/v1/openapi.json`` drops the entry and this fails. Runs against
the real ASGI app via ``app_client``; needs no auth (the schema is public).
"""

from __future__ import annotations

_CORE_PATHS = [
    "/api/v1/alerts",
    "/api/v1/alerts:batch",
    "/api/v1/cases",
    "/api/v1/cases/stats",
    "/api/v1/cases/{case_id}",
    "/api/v1/cases/{case_id}/transition",
    "/api/v1/cases/{case_id}/audit",
    "/api/v1/cases/{case_id}/audit:export",
    "/api/v1/audit",
    "/api/v1/audit:verify",
    "/api/v1/users",
    "/api/v1/auth/token",
    "/healthz",
    "/readyz",
    "/metrics",
]


async def test_openapi_lists_core_routes(app_client) -> None:
    paths = (await app_client.get("/api/v1/openapi.json")).json()["paths"]
    missing = [p for p in _CORE_PATHS if p not in paths]
    assert not missing, f"missing from openapi.json: {missing}"
