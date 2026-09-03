from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.audit.routes import router as audit_router
from app.auth.routes import router as auth_router
from app.cases.routes import router as cases_router
from app.ingestion.routes import router as ingestion_router
from app.logging import CorrelationIdMiddleware, configure_logging
from app.metrics import http_request_duration_seconds
from app.ops.routes import router as ops_router

API_V1_PREFIX = "/api/v1"


async def _record_request_duration(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Observe ``http_request_duration_seconds`` for every request (FR-OPS-02).

    The ``route`` label is the matched route *template* (``/api/v1/cases/{case_id}``),
    never the raw path, so per-id URLs do not blow up the metric's cardinality.
    """
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    route = request.scope.get("route")
    template = getattr(route, "path", None) or "unmatched"
    http_request_duration_seconds.labels(
        method=request.method,
        route=template,
        status=str(response.status_code),
    ).observe(elapsed)
    return response


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Alert Case Management & Deduplication System",
        version="1.0.0",
        # Served same-origin behind the Caddy proxy, which routes /api/* to the
        # backend -- so the schema and docs live under the API prefix too.
        openapi_url=f"{API_V1_PREFIX}/openapi.json",
        docs_url=f"{API_V1_PREFIX}/docs",
        redoc_url=f"{API_V1_PREFIX}/redoc",
    )
    app.middleware("http")(_record_request_duration)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(ops_router)
    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(audit_router, prefix=API_V1_PREFIX)
    app.include_router(ingestion_router, prefix=API_V1_PREFIX)
    app.include_router(cases_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
