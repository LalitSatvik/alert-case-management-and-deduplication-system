"""Tests for the canonical Alert schema (AlertIn, AlertOut, GroupingInfo)."""

import json
import pathlib
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.alert import AlertIn, AlertOut, GroupingInfo, export_alert_json_schema


def _base(**over):
    """Construct a minimal valid AlertIn dict for testing."""
    d = {
        "external_alert_id": "A1",
        "source_system": "tms",
        "event_time": datetime(2026, 8, 30, tzinfo=UTC),
        "amount": Decimal("100.00"),
        "currency": "USD",
        "direction": "outbound",
    }
    d.update(over)
    return d


def test_minimal_valid_alert():
    """Test that a minimal AlertIn is valid with empty defaults for list fields."""
    a = AlertIn(**_base())
    assert a.rule_codes == []
    assert a.typologies == []
    assert a.raw_payload == {}


def test_negative_amount_rejected():
    """Test that negative amounts are rejected."""
    with pytest.raises(ValidationError):
        AlertIn(**_base(amount=Decimal(-1)))


def test_bad_currency_rejected():
    """Test that non-ISO-4217 currency codes are rejected (not exactly 3 uppercase letters)."""
    with pytest.raises(ValidationError):
        AlertIn(**_base(currency="US"))


def test_bad_direction_rejected():
    """Test that invalid direction values are rejected."""
    with pytest.raises(ValidationError):
        AlertIn(**_base(direction="sideways"))


def test_risk_score_range():
    """Test that risk scores must be between 0 and 100."""
    with pytest.raises(ValidationError):
        AlertIn(**_base(risk_score=101))
    with pytest.raises(ValidationError):
        AlertIn(**_base(risk_score=-1))


def test_valid_risk_score_boundaries():
    """Test that risk scores of 0 and 100 are valid."""
    a = AlertIn(**_base(risk_score=0))
    assert a.risk_score == 0
    b = AlertIn(**_base(risk_score=100))
    assert b.risk_score == 100


def test_alert_out_has_all_in_fields_plus_output_fields():
    """Test that AlertOut contains all AlertIn fields plus id, received_at, case_id, grouping."""
    a_in = AlertIn(**_base())
    alert_id = UUID("12345678-1234-5678-1234-567812345678")
    received_at = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

    a_out = AlertOut(
        **a_in.model_dump(),
        id=alert_id,
        received_at=received_at,
    )

    assert a_out.id == alert_id
    assert a_out.received_at == received_at
    assert a_out.case_id is None
    assert a_out.grouping is None
    assert a_out.external_alert_id == "A1"
    assert a_out.direction == "outbound"


def test_alert_out_with_grouping_info():
    """Test that AlertOut can contain GroupingInfo."""
    a_in = AlertIn(**_base())
    alert_id = UUID("12345678-1234-5678-1234-567812345678")
    received_at = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    case_id = UUID("87654321-4321-8765-4321-876543218765")

    grouping = GroupingInfo(
        method="deterministic",
        matched_rule_ids=["rule1", "rule2"],
        similarity_score=0.95,
        feature_contributions={"amount": 0.5, "customer": 0.3},
        engine_version="1.0.0",
        config_hash="abc123",
    )

    a_out = AlertOut(
        **a_in.model_dump(),
        id=alert_id,
        received_at=received_at,
        case_id=case_id,
        grouping=grouping,
    )

    assert a_out.case_id == case_id
    assert a_out.grouping == grouping
    assert a_out.grouping.method == "deterministic"


def test_committed_json_schema_is_current():
    """Test that the committed JSON schema file matches the current AlertIn schema."""
    schema_path = pathlib.Path(__file__).parent.parent / "schemas" / "alert.schema.json"
    assert schema_path.exists(), f"Schema file not found at {schema_path}"

    committed_schema = json.loads(schema_path.read_text())
    current_schema = export_alert_json_schema()

    assert committed_schema == current_schema, "Committed schema is out of sync with AlertIn schema"
