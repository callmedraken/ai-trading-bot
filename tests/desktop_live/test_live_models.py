from decimal import Decimal

import pytest

from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_live.execution import plan_from_sanitized
from trading_bot.desktop_live.models import (
    LiveExecutionPlan,
    LivePlanState,
    TradabilityObservation,
)


def _no_action() -> LiveExecutionPlan:
    return LiveExecutionPlan.create(
        source_head="a" * 40,
        source_tree="b" * 40,
        policy=TinyLivePolicy(),
        observation_basis="ROBINHOOD_RAW_DAILY_REGULAR_V1",
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
