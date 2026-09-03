import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_correlation_id_generated_when_absent(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    cid = r.headers.get("X-Correlation-ID")
    assert cid is not None
    # A valid UUID string was generated.
    assert str(uuid.UUID(cid)) == cid


async def test_correlation_id_preserved_when_supplied(client):
    supplied = "test-correlation-1234"
    r = await client.get("/healthz", headers={"X-Correlation-ID": supplied})
    assert r.status_code == 200
    assert r.headers.get("X-Correlation-ID") == supplied
