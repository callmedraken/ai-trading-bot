from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.portfolio import (
    AllocationSource,
    PortfolioConstraints,
    PortfolioPositionState,
    PortfolioState,
    TargetAllocation,
    TargetPortfolio,
)
from trading_bot.rebalancing import (
    PlannedTradeSide,
    RebalanceAssumptions,
    RebalanceDiagnosticCode,
    RebalancePlanner,
    RebalancePlanRequest,
    RebalanceStatus,
    UnplannedAllocationReason,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
IWM = Symbol("IWM")


def state(
    quantities: tuple[str, ...] = ("25", "0"),
    cash: str = "750",
    prices: tuple[str, ...] = ("10", "10"),
) -> PortfolioState:
    symbols = (SPY, QQQ, IWM)[: len(quantities)]
    positions = tuple(
        PortfolioPositionState(
            symbol,
            Decimal(quantity),
            Decimal("8") if Decimal(quantity) else Decimal("0"),
            Decimal(price),
        )
        for symbol, quantity, price in zip(symbols, quantities, prices, strict=True)
    )
    equity = Decimal(cash) + sum(
        (item.market_value for item in positions), start=Decimal("0")
    )
    return PortfolioState(NOW, positions, Decimal(cash), equity)


def target(weights: tuple[str, ...], cash_weight: str) -> TargetPortfolio:
    symbols = (SPY, QQQ, IWM)[: len(weights)]
    return TargetPortfolio(
        UUID(int=2),
        NOW,
        tuple(
            TargetAllocation(symbol, Decimal(weight))
            for symbol, weight in zip(symbols, weights, strict=True)
        ),
        Decimal(cash_weight),
        AllocationSource.MANUAL,
    )


def request(
    current: PortfolioState,
    desired: TargetPortfolio,
    assumptions: RebalanceAssumptions | None = None,
    constraints: PortfolioConstraints | None = None,
) -> RebalancePlanRequest:
    return RebalancePlanRequest(
        UUID(int=1),
        current,
        desired,
        assumptions or RebalanceAssumptions(),
        constraints,
    )


def test_no_action_plan_is_exact_and_immutable_inputs_are_preserved() -> None:
    current = state()
    desired = target(("0.25", "0"), "0.75")
    before = (current, desired)
    plan = RebalancePlanner().plan(request(current, desired))
    assert plan.status is RebalanceStatus.NO_ACTION
    assert plan.trades == ()
    assert all(item.absolute_weight_deviation == 0 for item in plan.deviations)
    assert (current, desired) == before


def test_fractional_mixed_plan_sells_then_buys_and_reconciles() -> None:
    current = state()
    desired = target(("0.2", "0.2"), "0.6")
    plan = RebalancePlanner().plan(request(current, desired))
    assert plan.status is RebalanceStatus.COMPLETE
    assert [item.side for item in plan.trades] == [
        PlannedTradeSide.SELL,
        PlannedTradeSide.BUY,
    ]
    assert [item.planned_quantity for item in plan.trades] == [
        Decimal("5"),
        Decimal("20"),
    ]
    assert plan.estimated_ending_cash == Decimal("600")
    assert plan.estimated_ending_equity == Decimal("1000")
    assert plan.cash_value_deviation == Decimal("0")


def test_whole_share_rounding_produces_partial_plan() -> None:
    current = state(quantities=("3", "0"), cash="70", prices=("10", "10"))
    desired = target(("0.155", "0.345"), "0.5")
    assumptions = RebalanceAssumptions(
        allow_fractional_quantities=False,
        quantity_increment=Decimal("1"),
    )
    plan = RebalancePlanner().plan(request(current, desired, assumptions))
    assert plan.status is RebalanceStatus.PARTIAL
    assert any(
        item.limiting_reason is UnplannedAllocationReason.QUANTITY_ROUNDING
        for item in plan.deviations
    )


def test_target_zero_full_exit_is_exact_and_increment_exempt() -> None:
    current = state(quantities=("1.234", "0"), cash="10")
    desired = target(("0", "0"), "1")
    assumptions = RebalanceAssumptions(quantity_increment=Decimal("0.1"))
    plan = RebalancePlanner().plan(request(current, desired, assumptions))
    assert plan.planned_sells[0].planned_quantity == Decimal("1.234")
    assert plan.planned_sells[0].planned_quantity == current.positions[0].quantity


def test_sell_proceeds_policy_and_commissions_are_not_double_counted() -> None:
    current = state()
    desired = target(("0.2", "0.2"), "0.6")
    enabled = RebalanceAssumptions(fixed_commission=Decimal("1"))
    disabled = RebalanceAssumptions(
        fixed_commission=Decimal("1"), use_planned_sell_proceeds=False
    )
    enabled_plan = RebalancePlanner().plan(request(current, desired, enabled))
    disabled_plan = RebalancePlanner().plan(request(current, desired, disabled))
    assert enabled_plan.estimated_commissions == Decimal("2")
    assert enabled_plan.estimated_ending_cash == (
        Decimal("750")
        + enabled_plan.estimated_gross_sell_proceeds
        - enabled_plan.estimated_gross_buy_cost
        - Decimal("2")
    )
    assert (
        disabled_plan.estimated_gross_buy_cost < enabled_plan.estimated_gross_buy_cost
    )
    assert disabled_plan.estimated_ending_cash > enabled_plan.estimated_ending_cash


def test_minimum_thresholds_and_commission_exceeding_proceeds_skip_trades() -> None:
    current = state(quantities=("1", "0"), cash="100", prices=("1", "1"))
    desired = target(("0", "0"), "1")
    commission_plan = RebalancePlanner().plan(
        request(
            current,
            desired,
            RebalanceAssumptions(fixed_commission=Decimal("1")),
        )
    )
    assert commission_plan.trades == ()
    assert commission_plan.deviations[0].limiting_reason is (
        UnplannedAllocationReason.COMMISSION_EXCEEDS_SELL_PROCEEDS
    )
    threshold_plan = RebalancePlanner().plan(
        request(
            state(),
            target(("0.249", "0.001"), "0.75"),
            RebalanceAssumptions(minimum_trade_quantity=Decimal("1")),
        )
    )
    assert any(
        item.limiting_reason is UnplannedAllocationReason.BELOW_MINIMUM_QUANTITY
        for item in threshold_plan.deviations
    )
    notional_plan = RebalancePlanner().plan(
        request(
            state(),
            target(("0.249", "0.001"), "0.75"),
            RebalanceAssumptions(minimum_trade_notional=Decimal("2")),
        )
    )
    assert any(
        item.limiting_reason is UnplannedAllocationReason.BELOW_MINIMUM_NOTIONAL
        for item in notional_plan.deviations
    )


def test_limiting_reason_precedence_is_deterministic() -> None:
    current = state(quantities=("1", "0"), cash="100", prices=("1", "1"))
    desired = target(("0", "0"), "1")
    plan = RebalancePlanner().plan(
        request(
            current,
            desired,
            RebalanceAssumptions(
                fixed_commission=Decimal("1"),
                minimum_trade_quantity=Decimal("2"),
                minimum_trade_notional=Decimal("2"),
            ),
        )
    )
    assert plan.deviations[0].limiting_reason is (
        UnplannedAllocationReason.COMMISSION_EXCEEDS_SELL_PROCEEDS
    )


def test_additive_buffer_can_make_exact_target_partial_or_infeasible() -> None:
    partial = RebalancePlanner().plan(
        request(
            state(),
            target(("0.2", "0.1"), "0.7"),
            RebalanceAssumptions(additional_execution_cash_buffer=Decimal("25")),
        )
    )
    assert partial.status is RebalanceStatus.PARTIAL
    infeasible = RebalancePlanner().plan(
        request(
            state(),
            target(("0.1", "0"), "0.9"),
            RebalanceAssumptions(additional_execution_cash_buffer=Decimal("1")),
        )
    )
    assert infeasible.status is RebalanceStatus.INFEASIBLE
    assert infeasible.trades == ()
    assert infeasible.estimated_ending_cash == infeasible.estimated_starting_cash


def test_canonical_funding_reduces_later_buy_and_emits_diagnostic() -> None:
    current = state(quantities=("0", "0", "0"), cash="100", prices=("10", "10", "10"))
    desired = target(("0.5", "0.5", "0"), "0")
    plan = RebalancePlanner().plan(
        request(
            current,
            desired,
            RebalanceAssumptions(fixed_commission=Decimal("1")),
        )
    )
    assert plan.planned_buys[0].symbol == SPY
    assert plan.deviations[1].limiting_reason is (
        UnplannedAllocationReason.INSUFFICIENT_BUY_CASH
    )
    assert plan.diagnostics[0].code is (
        RebalanceDiagnosticCode.CANONICAL_FUNDING_PRIORITY_APPLIED
    )
    assert plan.status is RebalanceStatus.PARTIAL


def test_achieved_constraint_failure_is_partial_without_fabricated_target() -> None:
    current = state()
    desired = target(("0.2", "0.2"), "0.6")
    constraints = PortfolioConstraints(
        maximum_position_weight=Decimal("0.2"),
        maximum_cash_weight=Decimal("0.7"),
        minimum_cash_weight=Decimal("0.5"),
    )
    plan = RebalancePlanner().plan(
        request(
            current,
            desired,
            RebalanceAssumptions(fixed_commission=Decimal("10")),
            constraints,
        )
    )
    assert not plan.estimated_constraints_satisfied
    assert plan.status is RebalanceStatus.PARTIAL


def test_ids_order_and_repeated_planning_are_deterministic() -> None:
    item = request(state(), target(("0.2", "0.2"), "0.6"))
    planner = RebalancePlanner()
    first = planner.plan(item)
    second = planner.plan(item)
    assert first == second
    assert first.plan_id.version == 5
    assert all(trade.planned_trade_id.version == 5 for trade in first.trades)
    assert len({trade.planned_trade_id for trade in first.trades}) == len(first.trades)
    assert [trade.symbol_ordinal for trade in first.trades] == [0, 1]


def test_nonpositive_ending_equity_infeasible_shape_is_cash_safe() -> None:
    item = request(state(), target(("0.2", "0.2"), "0.6"))
    plan = RebalancePlanner._infeasible(
        item,
        RebalanceDiagnosticCode.NONPOSITIVE_ENDING_EQUITY,
        "defensive test",
    )
    assert plan.status is RebalanceStatus.INFEASIBLE
    assert plan.trades == ()
    assert plan.estimated_ending_equity == item.state.equity
    assert tuple(item.estimated_achieved_quantity for item in plan.deviations) == (
        Decimal("25"),
        Decimal("0"),
    )
