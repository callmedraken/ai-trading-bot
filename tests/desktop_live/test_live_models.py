import json
from decimal import Decimal

import pytest

from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_live.execution import plan_from_sanitized
from trading_bot.desktop_live.models import (
    LiveExecutionPlan,
    LivePlanState,
    TradabilityObservation,
    parse_order_review,
)
from trading_bot.desktop_live.preflight import review_order_arguments


def _no_action() -> LiveExecutionPlan:
    return LiveExecutionPlan.create(
        source_head="a" * 40,
        source_tree="b" * 40,
        policy=TinyLivePolicy(),
        observation_basis="ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1",
        target_session="2026-11-02",
        previous_completed_session="2026-10-30",
        signal_values_digest="c" * 64,
        decision="NO_ACTION",
        account_fingerprint="d" * 64,
        position_baseline_count=0,
        spy_position_quantity=Decimal("0"),
        order_baseline_count=0,
        current_quote=Decimal("500"),
        risk_outcome="NOT_EVALUATED",
        approved_quantity=Decimal("0"),
        requested_dollars=Decimal("0"),
        trade_approval_enabled=False,
        tradability=TradabilityObservation("SPY", False, False, False),
        review=None,
        provider_warning_summary=(),
        state=LivePlanState.NO_ACTION,
    )


def test_plan_is_sanitized_and_digest_bound():
    plan = _no_action()
    raw = plan.sanitized()
    assert "account_number" not in raw
    assert raw["plan_sha256"] == plan.plan_sha256
    assert plan_from_sanitized(raw) == plan


def test_plan_rejects_tampered_digest():
    raw = _no_action().sanitized()
    raw["plan_sha256"] = "e" * 64
    with pytest.raises(RuntimeError, match="PLAN_DIGEST"):
        plan_from_sanitized(raw)


def _review(**changes):
    return {
        "data": {
            "symbol": "SPY",
            "side": "buy",
            "type": "market",
            "dollar_amount": "0.50",
            "order_checks": {},
            **changes,
        }
    }


def test_current_review_binds_explicit_request_without_unadvertised_echoes():
    expected = review_order_arguments(Decimal("0.50"), "SYNTHETIC_ACCOUNT")
    review = parse_order_review(_review(), expected=expected)
    assert review.clean
    assert (
        review.symbol,
        review.side,
        review.order_type,
        review.dollar_amount,
        review.market_hours,
        review.time_in_force,
    ) == ("SPY", "buy", "market", Decimal("0.50"), "regular_hours", "gfd")
    assert (
        parse_order_review(_review(), expected={**expected, "account_number": "OTHER"})
        == review
    )
    with_reason = _review(customer_approval_required_reason="SECRET_RAW_REASON")
    assert parse_order_review(with_reason, expected=expected) == review


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol", "QQQ"),
        ("side", "sell"),
        ("type", "limit"),
        ("dollar_amount", "0.51"),
        ("symbol", None),
        ("type", None),
        ("dollar_amount", None),
        ("market_hours", "extended_hours"),
        ("time_in_force", "gtc"),
        ("order_checks", None),
        ("order_checks", []),
        ("order_checks", ""),
        ("customer_approval_required", None),
        ("customer_approval_required", 1),
        ("customer_approval_required", "false"),
    ],
)
def test_review_drift_and_invalid_conditions_fail_closed(field, value):
    with pytest.raises(ValueError):
        parse_order_review(
            _review(**{field: value}),
            expected=review_order_arguments(Decimal("0.50"), "SYNTHETIC"),
        )


@pytest.mark.parametrize(
    "missing", ["symbol", "side", "type", "dollar_amount", "order_checks"]
)
def test_review_requires_current_echoes_and_order_checks(missing):
    payload = _review()
    del payload["data"][missing]
    with pytest.raises(ValueError):
        parse_order_review(
            payload, expected=review_order_arguments(Decimal("0.50"), "SYNTHETIC")
        )


def test_review_digest_binds_only_contract_and_sanitized_alert_approval_state():
    expected = review_order_arguments(Decimal("0.50"), "SYNTHETIC")
    clean = parse_order_review(_review(), expected=expected)
    alerts = [
        parse_order_review(_review(order_checks={"alert": raw}), expected=expected)
        for raw in ("SECRET_ONE", "SECRET_TWO")
    ]
    assert alerts[0] == alerts[1]
    assert alerts[0].warnings == ("ROBINHOOD_ORDER_CHECKS_PRESENT",)
    assert alerts[0].digest != clean.digest
    approval = parse_order_review(
        _review(customer_approval_required=True), expected=expected
    )
    false_approval = parse_order_review(
        _review(customer_approval_required=False), expected=expected
    )
    assert approval.warnings == ("ROBINHOOD_CUSTOMER_APPROVAL_REQUIRED",)
    assert not approval.clean
    assert false_approval.clean
    assert (
        len({clean.digest, alerts[0].digest, approval.digest, false_approval.digest})
        == 4
    )
    larger = parse_order_review(
        _review(dollar_amount="1.00"), expected={**expected, "dollar_amount": "1.00"}
    )
    assert larger.digest != clean.digest
    assert "SECRET" not in repr(alerts)
    assert "SYNTHETIC" not in repr(alerts)
    assert "alert" not in json.dumps(alerts[0].warnings)


@pytest.mark.parametrize(
    "changes",
    [
        {"market_hours": "extended_hours"},
        {"time_in_force": "gtc"},
        {"dollar_amount": "10.01"},
        {"dollar_amount": "0"},
        {"quantity": "1"},
        {"ref_id": "unexpected"},
    ],
)
def test_parser_requires_explicit_bounded_request_contract(changes):
    with pytest.raises(ValueError):
        parse_order_review(
            _review(),
            expected={
                **review_order_arguments(Decimal("0.50"), "SYNTHETIC"),
                **changes,
            },
        )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"data": None},
        {"data": []},
        {
            "data": {
                "result": {
                    "symbol": "SPY",
                    "side": "buy",
                    "type": "market",
                    "dollar_amount": "0.50",
                    "order_checks": {},
                }
            }
        },
    ],
)
def test_current_review_requires_direct_data_object(payload):
    with pytest.raises(ValueError):
        parse_order_review(
            payload, expected=review_order_arguments(Decimal("0.50"), "SYNTHETIC")
        )


def test_history_only_plan_basis_cannot_be_reused_for_completed_close_plan():
    from dataclasses import replace

    with pytest.raises(ValueError, match="observation basis"):
        replace(_no_action(), observation_basis="ROBINHOOD_RAW_DAILY_REGULAR_V1")
