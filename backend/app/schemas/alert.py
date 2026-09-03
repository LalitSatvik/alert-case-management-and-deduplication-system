"""Canonical Alert schema with JSON Schema export."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, IPvAnyAddress

# Annotated types for reuse
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$", min_length=3, max_length=3)]
Direction = Literal["inbound", "outbound", "internal"]
RiskScore = Annotated[int, Field(ge=0, le=100)]


class GroupingInfo(BaseModel):
    """Grouping and deduplication metadata for an alert."""

    model_config = {"json_schema_extra": {}}

    method: Literal["deterministic", "similarity", "singleton", "manual"]
    matched_rule_ids: list[str]
    similarity_score: float | None = None
    feature_contributions: dict[str, float]
    engine_version: str
    config_hash: str


class AlertIn(BaseModel):
    """Canonical inbound alert schema."""

    model_config = {"json_schema_extra": {}}

    # Required fields
    external_alert_id: str
    source_system: str
    event_time: AwareDatetime
    amount: Amount
    currency: Currency
    direction: Direction

    # Optional fields with defaults
    customer_ref: str | None = None
    account_ref: str | None = None
    counterparty_ref: str | None = None
    merchant_name: str | None = None
    mcc: str | None = None
    device_id: str | None = None
    ip_address: IPvAnyAddress | None = None
    session_id: str | None = None
    risk_score: RiskScore | None = None
    rule_codes: list[str] = Field(default_factory=list)
    typologies: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    ground_truth_group_id: str | None = None


class AlertOut(BaseModel):
    """Outbound alert schema with system-generated fields."""

    model_config = {"json_schema_extra": {}}

    # System-generated fields
    id: UUID
    received_at: datetime
    case_id: UUID | None = None
    grouping: GroupingInfo | None = None

    # All AlertIn fields
    external_alert_id: str
    source_system: str
    event_time: AwareDatetime
    amount: Amount
    currency: Currency
    direction: Direction

    # Optional AlertIn fields
    customer_ref: str | None = None
    account_ref: str | None = None
    counterparty_ref: str | None = None
    merchant_name: str | None = None
    mcc: str | None = None
    device_id: str | None = None
    ip_address: IPvAnyAddress | None = None
    session_id: str | None = None
    risk_score: RiskScore | None = None
    rule_codes: list[str] = Field(default_factory=list)
    typologies: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    ground_truth_group_id: str | None = None


def export_alert_json_schema() -> dict[str, Any]:
    """Export the canonical AlertIn schema as a JSON Schema dict.

    Returns:
        dict: The JSON Schema representation of AlertIn.
    """
    return AlertIn.model_json_schema()
