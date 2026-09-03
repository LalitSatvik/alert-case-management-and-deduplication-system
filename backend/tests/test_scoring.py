from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.grouping.blocking import EngineAlert
from app.grouping.config import load_config
from app.grouping.scoring import deterministic_match, feature_contributions, score_pair

CFG = load_config("config/grouping.yaml")


def _a(id, minutes=0, **o):
    base = {
        "event_time": datetime(2026, 8, 30, 12, tzinfo=UTC) + timedelta(minutes=minutes),
        "amount": Decimal(100),
        "currency": "USD",
        "customer_ref": None,
        "account_ref": None,
        "counterparty_ref": None,
        "merchant_name_normalised": None,
        "mcc": None,
        "device_id": None,
        "ip_address": None,
        "session_id": None,
        "typologies": frozenset(),
    }
    base.update(o)
    return EngineAlert(id=id, **base)


def test_same_txn_dispute_is_deterministic():
    a = _a("1", account_ref="A", counterparty_ref="C", amount=Decimal(500))
    b = _a("2", minutes=30, account_ref="A", counterparty_ref="C", amount=Decimal(500))
    assert "same-txn-dispute" in deterministic_match(a, b, CFG)


def test_amount_outside_tolerance_breaks_deterministic_match():
    a = _a("1", account_ref="A", counterparty_ref="C", amount=Decimal(500))
    b = _a("2", minutes=30, account_ref="A", counterparty_ref="C", amount=Decimal(600))
    assert "same-txn-dispute" not in deterministic_match(a, b, CFG)


def test_similarity_high_for_close_merchant_amount_time():
    a = _a("1", merchant_name_normalised="quick cash llc", amount=Decimal(100), device_id="D")
    b = _a(
        "2", minutes=10, merchant_name_normalised="quick cash", amount=Decimal(101), device_id="D"
    )
    assert score_pair(a, b, CFG) >= CFG.similarity_threshold


def test_contributions_are_bounded():
    a, b = _a("1"), _a("2", minutes=5)
    c = feature_contributions(a, b, CFG)
    assert set(c) == {"time", "amount", "name", "device", "ip", "typology"}
    assert all(0.0 <= v <= 1.0 for v in c.values())
