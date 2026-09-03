"""End-to-end smoke test against a running ACMS stack.

Exercises the whole spine through the Caddy proxy: log in as the seeded analyst,
batch-ingest a 3-alert cluster with an ingest API key, wait for the async worker
to group them into one case, walk that case Open -> In Progress -> Closed with a
note, then export the audit trail and assert the hash chain verifies and every
expected action is on the stream.

Requires the full `docker compose` stack plus a seeded database:

    docker compose up --build -d
    docker compose run --rm seed          # prints the ingest API key
    ACMS_E2E=1 \
    ACMS_BASE_URL=http://localhost \
    ACMS_INGEST_API_KEY=<key from the seed output> \
    python -m pytest tests/e2e/test_smoke.py -v

`ACMS_ANALYST_EMAIL` / `ACMS_ANALYST_PASSWORD` default to the seeded demo login.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("ACMS_E2E") != "1",
        reason="requires the full docker compose stack; set ACMS_E2E=1",
    ),
]

BASE_URL = os.environ.get("ACMS_BASE_URL", "http://localhost").rstrip("/")
API = f"{BASE_URL}/api/v1"
ANALYST_EMAIL = os.environ.get("ACMS_ANALYST_EMAIL", "analyst@acms.example.com")
ANALYST_PASSWORD = os.environ.get("ACMS_ANALYST_PASSWORD", "demo-pw")
INGEST_API_KEY = os.environ.get("ACMS_INGEST_API_KEY", "")


def _cluster_payload() -> list[dict]:
    """Three alerts that the deterministic `same-txn-dispute` rule groups as one.

    Shared account_ref + amount + counterparty_ref, all inside 24h.
    """
    tag = uuid.uuid4().hex[:12]
    base_time = datetime.now(UTC) - timedelta(hours=1)
    common = {
        "source_system": "e2e-smoke",
        "amount": "125.50",
        "currency": "USD",
        "direction": "outbound",
        "account_ref": f"acct-{tag}",
        "counterparty_ref": f"cp-{tag}",
        "customer_ref": f"cust-{tag}",
    }
    return [
        {
            **common,
            "external_alert_id": f"e2e-{tag}-{i}",
            "event_time": (base_time + timedelta(minutes=5 * i)).isoformat(),
        }
        for i in range(3)
    ]


def test_end_to_end_ingest_to_audited_close() -> None:
    assert (
        INGEST_API_KEY
    ), "set ACMS_INGEST_API_KEY to the key printed by `docker compose run --rm seed`"

    with httpx.Client(base_url=API, timeout=30.0) as client:
        # --- log in as the analyst -----------------------------------------
        r = client.post(
            "/auth/token",
            json={"email": ANALYST_EMAIL, "password": ANALYST_PASSWORD},
        )
        r.raise_for_status()
        auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # --- batch-ingest a 3-alert cluster ------------------------------------
        alerts = _cluster_payload()
        external_ids = {a["external_alert_id"] for a in alerts}
        r = client.post(
            "/alerts:batch",
            json=alerts,
            headers={"X-API-Key": INGEST_API_KEY},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["accepted"] == 3
        assert body["grouping_enqueued"] is True

        # --- wait for the worker to collapse them into one case --------------
        case_id: str | None = None
        deadline = time.time() + 60
        while time.time() < deadline:
            r = client.get("/cases", params={"limit": 200}, headers=auth)
            r.raise_for_status()
            for item in r.json()["items"]:
                detail = client.get(f"/cases/{item['id']}", headers=auth)
                detail.raise_for_status()
                got = {a["external_alert_id"] for a in detail.json()["alerts"]}
                if external_ids <= got:
                    assert external_ids == got, "cluster split across cases"
                    case_id = item["id"]
                    break
            if case_id:
                break
            time.sleep(2)
        assert (
            case_id
        ), "worker did not produce a single case for the cluster within 60s"

        # --- work the case Open -> In Progress -> Closed --------------------
        r = client.post(
            f"/cases/{case_id}/transition",
            json={"to": "In Progress", "reason": "e2e smoke pickup"},
            headers=auth,
        )
        assert r.status_code == 200, r.text

        r = client.post(
            f"/cases/{case_id}/notes",
            json={
                "body": "e2e smoke: reviewed the three linked alerts, no further action."
            },
            headers=auth,
        )
        assert r.status_code == 201, r.text

        r = client.post(
            f"/cases/{case_id}/transition",
            json={
                "to": "Closed",
                "disposition": "No action",
                "reason": "e2e smoke close",
            },
            headers=auth,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "Closed"

        # --- export the audit trail and verify the chain -------------------
        # The export records its own `case.audit_exported` event *after*
        # building the bundle, so that action only shows up on a subsequent
        # export. Do it twice and assert on the second bundle.
        for _ in range(2):
            r = client.post(
                f"/cases/{case_id}/audit:export",
                params={"format": "json"},
                headers=auth,
            )
            assert r.status_code == 200, r.text
            bundle = r.json()

        assert bundle["chain_verified"] is True
        actions = {e["action"] for e in bundle["audit_events"]}
        assert {
            "case.alert_linked",
            "case.transitioned",
            "case.note_added",
            "case.audit_exported",
        } <= actions, actions
