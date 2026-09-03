from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.grouping.blocking import EngineAlert, candidate_pairs
from app.grouping.config import load_config

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


def test_same_account_within_window_is_a_candidate():
    pairs = candidate_pairs([_a("1", account_ref="A"), _a("2", minutes=5, account_ref="A")], CFG)
    assert ("1", "2") in pairs


def test_same_account_outside_all_windows_is_not_a_candidate():
    pairs = candidate_pairs(
        [_a("1", account_ref="A"), _a("2", minutes=60 * 24 * 8, account_ref="A")], CFG
    )
    assert pairs == set()


def test_no_shared_blocking_key_no_candidate():
    pairs = candidate_pairs([_a("1", account_ref="A"), _a("2", account_ref="B")], CFG)
    assert pairs == set()


def test_candidate_cap_is_enforced_deterministically():
    alerts = [_a("0", device_id="D", amount=Decimal(100))] + [
        _a(str(i), minutes=1, device_id="D", amount=Decimal(100)) for i in range(1, 20)
    ]
    cfg = load_config("config/grouping.yaml")
    object.__setattr__(cfg, "candidate_cap", 5)
    pairs = candidate_pairs(alerts, cfg)
    for_zero = [p for p in pairs if "0" in p]
    assert len(for_zero) <= 5
