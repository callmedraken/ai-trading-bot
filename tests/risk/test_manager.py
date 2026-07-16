from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trading_bot.domain import OrderSide, Position, Symbol, TradeProposal
from trading_bot.risk import (
    RiskContext,
    RiskLimits,
    RiskManager,
    RiskOutcome,
    RiskReasonCode,
)

NOW = datetime(2026, 1, 2, 12, tzinfo=UTC)
SPY = Symbol("SPY")


def proposal(quantity: str = "10", side: OrderSide = OrderSide.BUY) -> TradeProposal:
    return TradeProposal.create(
        symbol=SPY,
        side=side,
        desired_quantity=Decimal(quantity),
        created_at=NOW,
        reason="test signal",
    )


def context(
    *,
    cash: str = "10000",
    equity: str = "10000",
    price: str | None = "100",
    exposure: str = "0",
    position: str | None = None,
    enabled: bool = True,
) -> RiskContext:
    positions = (
        {SPY: Position(SPY, Decimal(position), Decimal("100"))}
        if position is not None
        else {}
    )
    return RiskContext(
        cash=Decimal(cash),
        equity=Decimal(equity),
        positions=positions,
        current_price=Decimal(price) if price is not None else None,
        total_market_exposure=Decimal(exposure),
        new_trading_enabled=enabled,
        as_of=NOW,
    )


def liberal_limits(**overrides: object) -> RiskLimits:
    values: dict[str, object] = {
        "max_position_percent": Decimal("1"),
        "max_total_exposure_percent": Decimal("1"),
        "minimum_cash_reserve_percent": Decimal("0"),
        "max_order_notional": None,
        "max_new_position_percent": None,
        "allow_fractional_shares": True,
        "fractional_increment": Decimal("0.001"),
    }
    values.update(overrides)
    return RiskLimits(**values)  # type: ignore[arg-type]


def codes(decision: object) -> set[RiskReasonCode]:
    return {reason.code for reason in decision.reasons}  # type: ignore[attr-defined]


def test_valid_buy_is_approved_without_irrelevant_reasons() -> None:
    decision = RiskManager(liberal_limits()).evaluate(proposal(), context())
    assert decision.outcome is RiskOutcome.APPROVED
    assert decision.approved_quantity == Decimal("10")
    assert decision.reasons == ()


@pytest.mark.parametrize(
    ("limits", "account", "code"),
    [
        (liberal_limits(), context(enabled=False), RiskReasonCode.TRADING_DISABLED),
        (
            liberal_limits(allow_buying=False),
            context(),
            RiskReasonCode.BUYING_DISABLED,
        ),
        (
            liberal_limits(),
            context(price=None),
            RiskReasonCode.PRICE_NOT_AVAILABLE,
        ),
    ],
)
def test_buy_rejection_conditions(
    limits: RiskLimits, account: RiskContext, code: RiskReasonCode
) -> None:
    decision = RiskManager(limits).evaluate(proposal(), account)
    assert decision.outcome is RiskOutcome.REJECTED
    assert decision.approved_quantity == Decimal("0")
    assert codes(decision) == {code}


@pytest.mark.parametrize(
    ("limits", "account", "expected", "code"),
    [
        (
            liberal_limits(),
            context(cash="250"),
            Decimal("2.5"),
            RiskReasonCode.CASH_CAPACITY,
        ),
        (
            liberal_limits(minimum_cash_reserve_percent=Decimal("0.20")),
            context(cash="1000", equity="1000"),
            Decimal("8"),
            RiskReasonCode.MINIMUM_CASH_RESERVE,
        ),
        (
            liberal_limits(max_order_notional=Decimal("250")),
            context(),
            Decimal("2.5"),
            RiskReasonCode.MAX_ORDER_NOTIONAL,
        ),
        (
            liberal_limits(max_position_percent=Decimal("0.60")),
            context(cash="1000", equity="1000", position="5", exposure="500"),
            Decimal("1"),
            RiskReasonCode.MAX_POSITION_PERCENT,
        ),
        (
            liberal_limits(max_total_exposure_percent=Decimal("1")),
            context(cash="1000", equity="1000", exposure="900"),
            Decimal("1"),
            RiskReasonCode.MAX_TOTAL_EXPOSURE_PERCENT,
        ),
        (
            liberal_limits(max_new_position_percent=Decimal("0.15")),
            context(cash="1000", equity="1000"),
            Decimal("1.5"),
            RiskReasonCode.MAX_NEW_POSITION_PERCENT,
        ),
    ],
)
def test_each_buy_constraint_can_resize(
    limits: RiskLimits,
    account: RiskContext,
    expected: Decimal,
    code: RiskReasonCode,
) -> None:
    decision = RiskManager(limits).evaluate(proposal(), account)
    assert decision.outcome is RiskOutcome.RESIZED
    assert decision.approved_quantity == expected
    assert codes(decision) == {code}


def test_estimated_commission_reduces_cash_and_reserve_capacity() -> None:
    cash_limited = RiskManager(
        liberal_limits(estimated_commission=Decimal("1"))
    ).evaluate(proposal("11"), context(cash="1001"))
    assert cash_limited.approved_quantity == Decimal("10")
    assert RiskReasonCode.CASH_CAPACITY in codes(cash_limited)

    reserve_limited = RiskManager(
        liberal_limits(
            minimum_cash_reserve_percent=Decimal("0.20"),
            estimated_commission=Decimal("1"),
        )
    ).evaluate(proposal(), context(cash="1001", equity="1000"))
    assert reserve_limited.approved_quantity == Decimal("8")
    assert RiskReasonCode.MINIMUM_CASH_RESERVE in codes(reserve_limited)


def test_optional_limits_are_skipped() -> None:
    decision = RiskManager(liberal_limits()).evaluate(
        proposal("50"), context(cash="10000", equity="10000")
    )
    assert decision.outcome is RiskOutcome.APPROVED


def test_smallest_of_simultaneous_constraints_wins() -> None:
    limits = liberal_limits(
        max_order_notional=Decimal("250"),
        max_new_position_percent=Decimal("0.15"),
    )
    decision = RiskManager(limits).evaluate(
        proposal(), context(cash="1000", equity="1000")
    )
    assert decision.approved_quantity == Decimal("1.5")
    assert codes(decision) == {RiskReasonCode.MAX_NEW_POSITION_PERCENT}


def test_exact_boundary_is_approved_with_binding_reason() -> None:
    limits = liberal_limits(max_order_notional=Decimal("250"))
    decision = RiskManager(limits).evaluate(proposal("2.5"), context())
    assert decision.outcome is RiskOutcome.APPROVED
    assert codes(decision) == {RiskReasonCode.MAX_ORDER_NOTIONAL}


def test_fractional_and_whole_share_rounding_is_downward() -> None:
    fractional = RiskManager(
        liberal_limits(fractional_increment=Decimal("0.01"))
    ).evaluate(proposal("1.239"), context())
    assert fractional.approved_quantity == Decimal("1.23")
    assert RiskReasonCode.QUANTITY_INCREMENT in codes(fractional)

    whole = RiskManager(liberal_limits(allow_fractional_shares=False)).evaluate(
        proposal("2.9"), context()
    )
    assert whole.approved_quantity == Decimal("2")


def test_quantity_below_increment_is_rejected() -> None:
    decision = RiskManager(
        liberal_limits(fractional_increment=Decimal("0.01"))
    ).evaluate(proposal("0.009"), context())
    assert decision.outcome is RiskOutcome.REJECTED
    assert RiskReasonCode.QUANTITY_TOO_SMALL in codes(decision)


def test_sell_missing_position_or_disabled_is_rejected() -> None:
    missing = RiskManager(liberal_limits()).evaluate(
        proposal("1", OrderSide.SELL), context(price=None)
    )
    disabled = RiskManager(liberal_limits(allow_selling=False)).evaluate(
        proposal("1", OrderSide.SELL), context(position="2", enabled=False)
    )
    assert codes(missing) == {RiskReasonCode.POSITION_NOT_FOUND}
    assert codes(disabled) == {RiskReasonCode.SELLING_DISABLED}


def test_oversized_sell_is_resized_to_owned_quantity() -> None:
    decision = RiskManager(liberal_limits()).evaluate(
        proposal("5", OrderSide.SELL), context(position="2", price=None)
    )
    assert decision.outcome is RiskOutcome.RESIZED
    assert decision.approved_quantity == Decimal("2")
    assert codes(decision) == {RiskReasonCode.SELL_QUANTITY_REDUCED}


def test_sell_ignores_buy_limits_and_trading_disabled_flag() -> None:
    restrictive = RiskLimits(
        max_position_percent=Decimal("0.01"),
        max_total_exposure_percent=Decimal("0.01"),
        max_order_notional=Decimal("1"),
        max_new_position_percent=Decimal("0.01"),
        minimum_cash_reserve_percent=Decimal("1"),
        estimated_commission=Decimal("999"),
    )
    decision = RiskManager(restrictive).evaluate(
        proposal("1", OrderSide.SELL),
        context(cash="0", position="2", price=None, enabled=False),
    )
    assert decision.outcome is RiskOutcome.APPROVED
    assert decision.approved_quantity == Decimal("1")


def test_exact_fractional_liquidation_is_allowed_when_fractional_disabled() -> None:
    manager = RiskManager(liberal_limits(allow_fractional_shares=False))
    exact = manager.evaluate(
        proposal("0.75", OrderSide.SELL), context(position="0.75", price=None)
    )
    oversized = manager.evaluate(
        proposal("1", OrderSide.SELL), context(position="0.75", price=None)
    )
    assert exact.outcome is RiskOutcome.APPROVED
    assert exact.approved_quantity == Decimal("0.75")
    assert oversized.outcome is RiskOutcome.RESIZED
    assert oversized.approved_quantity == Decimal("0.75")


def test_evaluation_is_repeatable_and_does_not_mutate_inputs() -> None:
    item = proposal("3.1415")
    account = context(position="1")
    limits = liberal_limits(fractional_increment=Decimal("0.01"))
    item_before = deepcopy(item)
    positions_before = dict(account.positions)
    manager = RiskManager(limits)
    first = manager.evaluate(item, account)
    second = manager.evaluate(item, account)
    assert first == second
    assert item == item_before
    assert dict(account.positions) == positions_before
    assert manager.limits == limits
