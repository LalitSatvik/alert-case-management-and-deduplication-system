"""Pure grouping-engine resolution tests.

No database, no fixtures -- :func:`app.grouping.engine.group` is a pure function of
its arguments, so these run fast and are order-independent by contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.grouping.blocking import EngineAlert
from app.grouping.config import load_config
from app.grouping.engine import group

CFG = load_config("config/grouping.yaml")

_BASE = datetime(2026, 8, 30, 12, tzinfo=UTC)


def _a(alert_id: str, minutes: int = 0, **o: object) -> EngineAlert:
    base: dict[str, object] = {
        "event_time": _BASE + timedelta(minutes=minutes),
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
    return EngineAlert(id=alert_id, **base)  # type: ignore[arg-type]


def test_three_alerts_same_dispute_form_one_group() -> None:
    alerts = [
        _a("1", account_ref="A", counterparty_ref="C", amount=Decimal(500)),
        _a("2", minutes=10, account_ref="A", counterparty_ref="C", amount=Decimal(500)),
        _a("3", minutes=20, account_ref="A", counterparty_ref="C", amount=Decimal(500)),
    ]
    decisions = group(alerts, CFG)
    assert {d.group_key for d in decisions} == {"1"}
    assert all(d.method == "deterministic" for d in decisions)


def test_unrelated_alert_is_its_own_group() -> None:
    alerts = [
        _a("1", account_ref="A", counterparty_ref="C", amount=Decimal(500)),
        _a("2", minutes=10, account_ref="A", counterparty_ref="C", amount=Decimal(500)),
        _a("9", minutes=5, account_ref="Z", counterparty_ref="Q", amount=Decimal(3)),
    ]
    decisions = {d.alert_id: d for d in group(alerts, CFG)}
    assert decisions["9"].group_key != decisions["1"].group_key
    assert decisions["1"].group_key == decisions["2"].group_key
    assert decisions["9"].method == "singleton"
    assert decisions["9"].similarity_score is None
    assert decisions["9"].contributions == {}


def test_pinned_apart_splits_a_group() -> None:
    alerts = [
        _a("1", account_ref="A", counterparty_ref="C", amount=Decimal(500)),
        _a("2", minutes=10, account_ref="A", counterparty_ref="C", amount=Decimal(500)),
    ]
    decisions = {d.alert_id: d.group_key for d in group(alerts, CFG, pinned_apart={("1", "2")})}
    assert decisions["1"] != decisions["2"]


def test_pinned_together_joins_unrelated_alerts() -> None:
    alerts = [
        _a("1", account_ref="A", counterparty_ref="C"),
        _a("9", minutes=5, account_ref="Z", counterparty_ref="Q", amount=Decimal(3)),
    ]
    decisions = {d.alert_id: d.group_key for d in group(alerts, CFG, pinned_together={("9", "1")})}
    assert decisions["1"] == decisions["9"] == "1"


def test_group_is_deterministic_across_input_order() -> None:
    a1 = _a("1", account_ref="A", counterparty_ref="C", amount=Decimal(500))
    a2 = _a("2", minutes=10, account_ref="A", counterparty_ref="C", amount=Decimal(500))
    a3 = _a("3", minutes=20, account_ref="A", counterparty_ref="C", amount=Decimal(500))
    forward = {d.alert_id: d.group_key for d in group([a1, a2, a3], CFG)}
    reverse = {d.alert_id: d.group_key for d in group([a3, a2, a1], CFG)}
    assert forward == reverse == {"1": "1", "2": "1", "3": "1"}
