"""Unit tests for the deterministic alert normalisation service.

Pure functions, no DB -- not ``infra``-marked. ``AlertIn`` already enforces an
uppercase ``^[A-Z]{3}$`` currency and a tz-aware ``event_time``, so the inputs
here are always schema-valid; the point of ``normalize_alert`` is to produce a
single canonical, immutable representation regardless of representation quirks
(offset timezones, trailing decimal zeros, messy merchant strings).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.ingestion.normalize import NormalizedAlert, amount_bucket, normalize_alert
from app.schemas.alert import AlertIn


def _alert(**overrides: object) -> AlertIn:
    data: dict[str, object] = {
        "external_alert_id": "A1",
        "source_system": "tms",
        "event_time": datetime(2026, 8, 30, 12, 0, tzinfo=timezone(timedelta(hours=2))),
        "amount": Decimal("100.1"),
        "currency": "USD",
        "direction": "outbound",
        "merchant_name": "  Quick-Cash,  LLC ",
    }
    data.update(overrides)
    return AlertIn(**data)  # type: ignore[arg-type]


def test_event_time_coerced_to_utc() -> None:
    n = normalize_alert(_alert())
    assert n.event_time.tzinfo == UTC
    assert n.event_time.hour == 10  # 12:00+02:00 -> 10:00Z
    assert n.event_time.utcoffset() == timedelta(0)


def test_event_time_already_utc_is_unchanged() -> None:
    ts = datetime(2026, 8, 30, 9, 30, tzinfo=UTC)
    n = normalize_alert(_alert(event_time=ts))
    assert n.event_time == ts


_NAIVE_DT = datetime(2026, 8, 30, 12, 0)  # noqa: DTZ001  -- deliberately tz-naive


def test_naive_event_time_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        _alert(event_time=_NAIVE_DT)


def test_normalize_alert_guards_against_naive_event_time() -> None:
    # model_copy() does not re-validate, so this smuggles a naive datetime past
    # the schema -- normalize_alert must still refuse it rather than silently
    # interpret it in the host's local timezone.
    smuggled = _alert().model_copy(update={"event_time": _NAIVE_DT})
    with pytest.raises(ValueError, match="event_time must be timezone-aware"):
        normalize_alert(smuggled)


def test_currency_uppercased_and_amount_quantised() -> None:
    n = normalize_alert(_alert(amount=Decimal("100.10000")))
    assert n.currency == "USD"
    assert str(n.amount) == "100.1000"
    assert n.amount == Decimal("100.1000")


def test_amount_quantised_pads_to_four_places() -> None:
    # AlertIn already rejects >4 decimal places, so quantise only ever pads.
    assert str(normalize_alert(_alert(amount=Decimal(2))).amount) == "2.0000"
    assert str(normalize_alert(_alert(amount=Decimal("1.5"))).amount) == "1.5000"


def test_merchant_normalisation_is_deterministic() -> None:
    a = normalize_alert(_alert()).merchant_name_normalised
    b = normalize_alert(_alert()).merchant_name_normalised
    assert a == b == "quick cash llc"


def test_merchant_normalisation_collapses_internal_whitespace_and_punctuation() -> None:
    n = normalize_alert(_alert(merchant_name="ACME   ***  Corp!!!  #42"))
    assert n.merchant_name_normalised == "acme corp 42"


def test_merchant_name_none_normalises_to_none() -> None:
    n = normalize_alert(_alert(merchant_name=None))
    assert n.merchant_name is None
    assert n.merchant_name_normalised is None


def test_merchant_name_all_punctuation_normalises_to_empty_string() -> None:
    n = normalize_alert(_alert(merchant_name="!!! --- ???"))
    assert n.merchant_name_normalised == ""


def test_ip_address_canonicalised_to_string() -> None:
    n = normalize_alert(_alert(ip_address="2001:0db8:0000:0000:0000:0000:0000:0001"))
    assert n.ip_address == "2001:db8::1"
    assert isinstance(n.ip_address, str)


def test_ip_address_none_stays_none() -> None:
    assert normalize_alert(_alert(ip_address=None)).ip_address is None


def test_result_is_a_frozen_dataclass() -> None:
    n = normalize_alert(_alert())
    assert dataclasses.is_dataclass(n)
    with pytest.raises(dataclasses.FrozenInstanceError):
        n.currency = "EUR"  # type: ignore[misc]


def test_passthrough_fields_preserved() -> None:
    n = normalize_alert(
        _alert(
            customer_ref="C7",
            rule_codes=["R1", "R2"],
            typologies=["structuring"],
            raw_payload={"k": "v"},
            risk_score=55,
            ground_truth_group_id="G1",
        )
    )
    assert n.customer_ref == "C7"
    assert n.rule_codes == ["R1", "R2"]
    assert n.typologies == ["structuring"]
    assert n.raw_payload == {"k": "v"}
    assert n.risk_score == 55
    assert n.ground_truth_group_id == "G1"
    assert isinstance(n, NormalizedAlert)


@pytest.mark.parametrize(
    ("amount", "bucket"),
    [
        (Decimal(0), "0-10"),
        (Decimal(5), "0-10"),
        (Decimal("9.9999"), "0-10"),
        (Decimal(10), "10-100"),
        (Decimal("99.99"), "10-100"),
        (Decimal(100), "100-1000"),
        (Decimal("999.99"), "100-1000"),
        (Decimal(1000), "1000-10000"),
        (Decimal(4980), "1000-10000"),
        (Decimal("9999.99"), "1000-10000"),
        (Decimal(10000), "10000+"),
        (Decimal(250000), "10000+"),
    ],
)
def test_amount_bucket_boundaries(amount: Decimal, bucket: str) -> None:
    assert amount_bucket(amount) == bucket


def test_amount_bucket_rejects_negative() -> None:
    with pytest.raises(ValueError, match="amount must be non-negative"):
        amount_bucket(Decimal("-0.01"))
