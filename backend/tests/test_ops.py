import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_healthz_always_ok(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_metrics_is_prometheus_text(client):
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]


@pytest.mark.infra
async def test_metrics_exposes_application_series(
    ingest_client: AsyncClient, valid_alert_payload: dict
) -> None:
    """After an ingest + any request, FR-OPS-02 metric families are present."""
    r = await ingest_client.post(
        "/api/v1/alerts",
        json=valid_alert_payload,
        headers={"X-API-Key": ingest_client.api_key},  # type: ignore[attr-defined]
    )
    assert r.status_code == 201

    m = await ingest_client.get("/metrics")
    assert m.status_code == 200
    text = m.text
    assert "alerts_ingested_total" in text
    assert "http_request_duration_seconds" in text
    assert "grouping_duration_seconds" in text
    assert "cases_open" in text
