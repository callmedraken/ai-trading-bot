from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from trading_bot.domain import OrderSide, Position, Symbol, TradeProposal
from trading_bot.risk import (
    RiskContext,
    RiskDecision,
    RiskLimits,
    RiskOutcome,
    RiskReason,
    RiskReasonCode,
)

NOW = datetime(2026, 1, 2, 12, tzinfo=UTC)
SPY = Symbol("SPY")


def proposal() -> TradeProposal:
    return TradeProposal.create(
        symbol=SPY,
        side=OrderSide.BUY,
        desired_quantity=Decimal("2"),
        created_at=NOW,
        reason="test",
    )


def test_context_validates_and_defensively_copies_positions() -> None:
    source = {SPY: Position(SPY, Decimal("2"), Decimal("100"))}
    local = datetime(2026, 1, 2, 4, tzinfo=timezone(timedelta(hours=-8)))
    context = RiskContext(
        cash=Decimal("0"),
        equity=Decimal("200"),
        positions=source,
        current_price=Decimal("100"),
        total_market_exposure=Decimal("200"),
        new_trading_enabled=True,
        as_of=local,
    )
    source.clear()
    assert SPY in context.positions
    assert isinstance(context.positions, MappingProxyType)
    assert context.as_of == NOW


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cash", Decimal("-1")),
        ("equity", Decimal("0")),
        ("total_market_exposure", Decimal("-1")),
        ("current_price", Decimal("0")),
    ],
)
def test_context_rejects_invalid_financial_values(field: str, value: Decimal) -> None:
    values = {
        "cash": Decimal("100"),
        "equity": Decimal("100"),
        "positions": {},
        "current_price": Decimal("1"),
        "total_market_exposure": Decimal("0"),
        "new_trading_enabled": True,
        "as_of": NOW,
    }
    values[field] = value
    with pytest.raises(ValueError, match=field):
        RiskContext(**values)  # type: ignore[arg-type]


def test_context_does_not_require_exact_reconciliation() -> None:
    context = RiskContext(
        cash=Decimal("100"),
        equity=Decimal("999"),
        positions={},
        current_price=None,
        total_market_exposure=Decimal("12"),
        new_trading_enabled=True,
        as_of=NOW,
    )
    assert context.equity == Decimal("999")


def test_risk_limits_optional_rules_and_commission_defaults() -> None:
    limits = RiskLimits()
    assert limits.max_order_notional is None
    assert limits.max_new_position_percent is None
    assert limits.estimated_commission == Decimal("0")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_position_percent", Decimal("0")),
        ("max_total_exposure_percent", Decimal("1.1")),
        ("max_order_notional", Decimal("0")),
        ("max_new_position_percent", Decimal("1.1")),
        ("minimum_cash_reserve_percent", Decimal("-0.1")),
        ("fractional_increment", Decimal("0")),
        ("estimated_commission", Decimal("-0.01")),
    ],
)
def test_risk_limits_reject_invalid_values(field: str, value: Decimal) -> None:
    with pytest.raises(ValueError, match=field):
        RiskLimits(**{field: value})


def test_decision_enforces_outcome_quantity_invariants() -> None:
    item = proposal()
    reason = RiskReason(RiskReasonCode.CASH_CAPACITY, "cash constrained")
    approved = RiskDecision(item, RiskOutcome.APPROVED, Decimal("2"), (), NOW)
    assert approved.approved_quantity == item.desired_quantity
    with pytest.raises(ValueError, match="smaller positive"):
        RiskDecision(item, RiskOutcome.RESIZED, Decimal("2"), (reason,), NOW)
    with pytest.raises(ValueError, match="zero quantity"):
        RiskDecision(item, RiskOutcome.REJECTED, Decimal("1"), (reason,), NOW)


def test_risk_models_are_immutable() -> None:
    limits = RiskLimits()
    with pytest.raises(FrozenInstanceError):
        limits.allow_buying = False  # type: ignore[misc]
