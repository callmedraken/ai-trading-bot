from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_live.execution import (
    LIVE_ARM_VALUE,
    LiveStateStore,
    execute_plan,
)
from trading_bot.desktop_live.models import (
    LiveExecutionPlan,
    LivePlanState,
    TradabilityObservation,
    parse_order_review,
)


def _plan() -> LiveExecutionPlan:
    review = parse_order_review(
        {
            "data": {
                "result": {
                    "symbol": "SPY",
                    "side": "buy",
                    "type": "market",
                    "dollar_amount": "0.50",
                    "market_hours": "regular_hours",
                    "time_in_force": "gfd",
                    "warnings": [],
                }
            }
        }
    )
    return LiveExecutionPlan.create(
        source_head="a" * 40,
        source_tree="b" * 40,
        policy=TinyLivePolicy(),
        observation_basis="ROBINHOOD_RAW_DAILY_REGULAR_V1",
        target_session="2026-11-02",
        previous_completed_session="2026-10-30",
        signal_values_digest="c" * 64,
        decision="BUY",
        account_fingerprint="d" * 64,
        position_baseline_count=0,
        spy_position_quantity=Decimal("0"),
        order_baseline_count=0,
        current_quote=Decimal("500"),
        risk_outcome="APPROVED",
        approved_quantity=Decimal("0.001"),
        requested_dollars=Decimal("0.50"),
        trade_approval_enabled=False,
        tradability=TradabilityObservation("SPY", True, True, True),
        review=review,
        provider_warning_summary=(),
        state=LivePlanState.READY,
    )


class _FakeTransport:
    def __init__(self):
        self.placed = 0

    def get_accounts(self):
        return {
            "data": {
                "accounts": [{"account_number": "SYNTHETIC", "agentic_allowed": True}]
            }
        }

    def review_equity_order(self, arguments):
        del arguments
        return {
            "data": {
                "result": {
                    "symbol": "SPY",
                    "side": "buy",
                    "type": "market",
                    "dollar_amount": "0.50",
                    "market_hours": "regular_hours",
                    "time_in_force": "gfd",
                    "warnings": [],
                }
            }
        }

    def place_equity_order(self, arguments):
        del arguments
        self.placed += 1
        return {"data": {"id": "provider-order-1"}}


def test_disarmed_plan_stops_before_any_mutation(tmp_path, monkeypatch):
    transport = _FakeTransport()
    monkeypatch.setattr(
        "trading_bot.desktop_live.execution.observe_robinhood_baseline",
        lambda *args, **kwargs: SimpleNamespace(
            account_fingerprint="d" * 64,
            positions=(),
            orders=(),
        ),
    )
    result = execute_plan(
        _plan(),
        transport=transport,
        now=datetime(2026, 11, 2, 14, 31, tzinfo=UTC),
        state_store=LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl"),
        source_head="a" * 40,
        source_tree="b" * 40,
        arm_token=None,
        plan_digest=None,
    )
    assert result.reason == "LIVE_DISARMED"
    assert transport.placed == 0


@pytest.mark.parametrize(
    "provider_state",
    ["partially_filled", "partially-filled", "pending", "open"],
)
def test_nonterminal_post_trade_state_is_consumed_and_never_reconciled(
    tmp_path, monkeypatch, provider_state
):
    transport = _FakeTransport()
    observations = 0

    def observe(*args, **kwargs):
        nonlocal observations
        observations += 1
        if observations == 1:
            return SimpleNamespace(
                account_fingerprint="d" * 64,
                positions=(),
                orders=(),
            )
        return SimpleNamespace(
            account_fingerprint="d" * 64,
            positions=(SimpleNamespace(symbol="SPY", quantity=Decimal("0.001")),),
            orders=(
                SimpleNamespace(
                    order_id="provider-order-1",
                    cumulative_quantity=Decimal("0.001"),
                    state=provider_state,
                ),
            ),
        )

    monkeypatch.setattr(
        "trading_bot.desktop_live.execution.observe_robinhood_baseline", observe
    )
    store = LiveStateStore(tmp_path / "attempt.json", tmp_path / "life.jsonl")
    plan = _plan()
    result = execute_plan(
        plan,
        transport=transport,
        now=datetime(2026, 11, 2, 14, 31, tzinfo=UTC),
        state_store=store,
        source_head="a" * 40,
        source_tree="b" * 40,
        arm_token=LIVE_ARM_VALUE,
        plan_digest=plan.plan_sha256,
    )

    assert result.status == "STOPPED"
    assert result.receipt is None
    assert result.reason == "POST_TRADE_RECONCILIATION_BLOCKED"
    assert store.marker.is_file()
    assert transport.placed == 1

    retry = execute_plan(
        plan,
        transport=transport,
        now=datetime(2026, 11, 2, 14, 31, tzinfo=UTC),
        state_store=store,
        source_head="a" * 40,
        source_tree="b" * 40,
        arm_token=LIVE_ARM_VALUE,
        plan_digest=plan.plan_sha256,
    )

    assert retry.reason == "PRESERVE_CONSUMED_ATTEMPT_NO_RETRY"
    assert transport.placed == 1
