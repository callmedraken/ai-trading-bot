from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import OrderFill, OrderSide, OrderStatus, Symbol
from trading_bot.execution import OrderEngine, PaperFillPolicy
from trading_bot.ledger import PaperLedger
from trading_bot.portfolio import (
    AllocationSource,
    MetadataEntry,
    PortfolioPositionState,
    PortfolioState,
    TargetAllocation,
    TargetPortfolio,
)
from trading_bot.rebalancing import (
    PlannedTradeSide,
    RebalanceAssumptions,
    RebalanceProposalPolicy,
)
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits, RiskOutcome
from trading_bot.runtime import (
    InconsistentPaperPortfolioRuntimeStateError,
    InvalidPaperPortfolioCycleRequestError,
    PaperPortfolioCycleInputs,
    PaperPortfolioCyclePrice,
    PaperPortfolioCycleRequest,
    PaperPortfolioCycleStatus,
    PaperPortfolioRuntime,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _request(*, weight: str = "0.2", trading_enabled: bool = True):  # type: ignore[no-untyped-def]
    state = PortfolioState(
        NOW,
        (PortfolioPositionState(SPY, Decimal("0"), Decimal("0"), Decimal("100")),),
        Decimal("1000"),
        Decimal("1000"),
    )
    target_weight = Decimal(weight)
    target = TargetPortfolio(
        UUID(int=2),
        NOW,
        (TargetAllocation(SPY, target_weight),),
        Decimal("1") - target_weight,
        AllocationSource.MANUAL,
    )
    limits = RiskLimits(
        max_position_percent=Decimal("1"),
        max_total_exposure_percent=Decimal("1"),
        minimum_cash_reserve_percent=Decimal("0"),
    )
    inputs = PaperPortfolioCycleInputs(
        state,
        target,
        RebalanceAssumptions(),
        None,
        RebalanceProposalPolicy(),
        None,
        limits,
        PortfolioRiskPolicy(),
        (PaperPortfolioCyclePrice(SPY, Decimal("100"), Decimal("101")),),
        PaperFillPolicy(),
        trading_enabled,
        NOW + timedelta(minutes=1),
        NOW + timedelta(minutes=2),
    )
    return PaperPortfolioCycleRequest(
        UUID(int=1), inputs, (MetadataEntry("caller", "test"),)
    )


def test_buy_cycle_runs_complete_audit_chain_and_commits_once() -> None:
    runtime = PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("1000")))
    original_engine, original_ledger = runtime.engine, runtime.ledger
    result = runtime.run_cycle(_request())
    assert result.status is PaperPortfolioCycleStatus.APPLIED
    assert result.risk_result.approved_count == 1
    assert len(result.order_result.orders) == len(result.submission_result.orders) == 1
    assert (
        len(result.fill_result.fills) == len(result.application_result.evaluations) == 1
    )
    assert result.fill_result.fills[0].price == Decimal("101")
    assert (
        runtime.engine is not original_engine and runtime.ledger is not original_ledger
    )
    assert runtime.ledger.cash == Decimal("798")
    assert runtime.ledger.positions[SPY].quantity == Decimal("2")
    assert result.post_engine_state_id == result.application_result.post_engine_state_id
    assert result.post_ledger_state_id == result.application_result.post_ledger_state_id


def test_no_action_preserves_exact_runtime_objects_and_builds_empty_chain() -> None:
    class UncopyableEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise AssertionError("NO_ACTION must not copy")

    class UncopyableLedger(PaperLedger):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise AssertionError("NO_ACTION must not copy")

    engine = UncopyableEngine()
    ledger = UncopyableLedger(Decimal("1000"))
    runtime = PaperPortfolioRuntime(engine, ledger)
    result = runtime.run_cycle(_request(weight="0"))
    assert result.status is PaperPortfolioCycleStatus.NO_ACTION
    assert runtime.engine is engine and runtime.ledger is ledger
    assert result.order_result.orders == result.submission_result.orders == ()
    assert result.fill_result.fills == result.application_result.evaluations == ()
    assert result.pre_engine_state_id == result.post_engine_state_id
    assert result.pre_ledger_state_id == result.post_ledger_state_id


def test_all_risk_rejected_is_no_action_without_copying() -> None:
    engine = OrderEngine()
    ledger = PaperLedger(Decimal("1000"))
    runtime = PaperPortfolioRuntime(engine, ledger)
    result = runtime.run_cycle(_request(trading_enabled=False))
    assert result.status is PaperPortfolioCycleStatus.NO_ACTION
    assert result.risk_result.rejected_count == 1
    assert runtime.engine is engine and runtime.ledger is ledger


def test_equal_inputs_and_prestate_produce_deterministic_identifiers() -> None:
    first = PaperPortfolioRuntime(
        OrderEngine(), PaperLedger(Decimal("1000"))
    ).run_cycle(_request())
    second = PaperPortfolioRuntime(
        OrderEngine(), PaperLedger(Decimal("1000"))
    ).run_cycle(_request())
    assert first.result_id == second.result_id
    assert first.plan.request.request_id == second.plan.request.request_id
    assert (
        first.application_result.request.request_id
        == second.application_result.request.request_id
    )
    assert all(
        MetadataEntry("paper_portfolio_cycle_id", str(UUID(int=1)))
        in stage.request.metadata
        for stage in (
            first.plan,
            first.proposal_result,
            first.risk_result,
            first.order_result,
            first.submission_result,
            first.fill_result,
            first.application_result,
        )
    )


def test_request_defensively_copies_metadata_and_rejects_reserved_keys() -> None:
    request = _request()
    values = [MetadataEntry("source", "manual")]
    copied = PaperPortfolioCycleRequest(request.request_id, request.inputs, values)
    values.clear()
    assert copied.metadata == (MetadataEntry("source", "manual"),)
    with pytest.raises(InvalidPaperPortfolioCycleRequestError, match="reserved"):
        PaperPortfolioCycleRequest(
            request.request_id,
            request.inputs,
            (MetadataEntry("paper_portfolio_internal", "bad"),),
        )


def test_input_validation_rejects_commission_and_timestamp_mismatches() -> None:
    request = _request()
    values = request.inputs
    with pytest.raises(InvalidPaperPortfolioCycleRequestError, match="commissions"):
        PaperPortfolioCycleInputs(
            values.state,
            values.target,
            values.rebalance_assumptions,
            values.portfolio_constraints,
            values.proposal_policy,
            values.proposal_confidence,
            RiskLimits(estimated_commission=Decimal("1")),
            values.risk_policy,
            values.prices,
            values.fill_policy,
            values.trading_enabled,
            values.submitted_at,
            values.filled_at,
        )
    with pytest.raises(InvalidPaperPortfolioCycleRequestError, match="timestamps"):
        PaperPortfolioCycleInputs(
            values.state,
            values.target,
            values.rebalance_assumptions,
            values.portfolio_constraints,
            values.proposal_policy,
            values.proposal_confidence,
            values.risk_limits,
            values.risk_policy,
            values.prices,
            values.fill_policy,
            values.trading_enabled,
            NOW - timedelta(seconds=1),
            values.filled_at,
        )


def test_runtime_rejects_state_that_disagrees_with_ledger() -> None:
    runtime = PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("999")))
    with pytest.raises(InconsistentPaperPortfolioRuntimeStateError, match="cash"):
        runtime.run_cycle(_request())


def test_cycle_prices_are_strict_and_independent() -> None:
    with pytest.raises(InvalidPaperPortfolioCycleRequestError, match="positive"):
        PaperPortfolioCyclePrice(SPY, Decimal("NaN"), Decimal("100"))
    result = PaperPortfolioRuntime(
        OrderEngine(), PaperLedger(Decimal("1000"))
    ).run_cycle(_request())
    assert result.risk_result.request.prices[0].price == Decimal("100")
    assert result.fill_result.request.prices[0].reference_price == Decimal("101")


def _seed_position(
    ledger: PaperLedger,
    symbol: Symbol,
    *,
    quantity: str,
    price: str,
) -> None:
    ledger.apply_fill(
        OrderFill(
            UUID(int=900),
            UUID(int=901),
            symbol,
            OrderSide.BUY,
            Decimal(quantity),
            Decimal(price),
            Decimal("0"),
            NOW - timedelta(days=1),
        )
    )


def _custom_request(
    state: PortfolioState,
    target: TargetPortfolio,
    prices: tuple[PaperPortfolioCyclePrice, ...],
    *,
    limits: RiskLimits,
    commission: str = "0",
    allow_sell_proceeds: bool = False,
) -> PaperPortfolioCycleRequest:
    fee = Decimal(commission)
    return PaperPortfolioCycleRequest(
        UUID(int=700),
        PaperPortfolioCycleInputs(
            state,
            target,
            RebalanceAssumptions(fixed_commission=fee),
            None,
            RebalanceProposalPolicy(),
            None,
            limits,
            PortfolioRiskPolicy(allow_sell_proceeds),
            prices,
            PaperFillPolicy(Decimal("0"), fee),
            True,
            NOW + timedelta(minutes=1),
            NOW + timedelta(minutes=2),
        ),
    )


def test_mixed_sell_then_buy_cycle_preserves_order_through_every_stage() -> None:
    ledger = PaperLedger(Decimal("1000"))
    _seed_position(ledger, SPY, quantity="10", price="50")
    state = PortfolioState(
        NOW,
        (
            PortfolioPositionState(SPY, Decimal("10"), Decimal("50"), Decimal("50")),
            PortfolioPositionState(QQQ, Decimal("0"), Decimal("0"), Decimal("50")),
        ),
        Decimal("500"),
        Decimal("1000"),
    )
    target = TargetPortfolio(
        UUID(int=701),
        NOW,
        (
            TargetAllocation(SPY, Decimal("0.25")),
            TargetAllocation(QQQ, Decimal("0.25")),
        ),
        Decimal("0.50"),
        AllocationSource.MANUAL,
    )
    request = _custom_request(
        state,
        target,
        (
            PaperPortfolioCyclePrice(SPY, Decimal("50"), Decimal("55")),
            PaperPortfolioCyclePrice(QQQ, Decimal("50"), Decimal("45")),
        ),
        limits=RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
        ),
        allow_sell_proceeds=True,
    )
    runtime = PaperPortfolioRuntime(OrderEngine(), ledger)
    result = runtime.run_cycle(request)

    assert [trade.side for trade in result.plan.trades] == [
        PlannedTradeSide.SELL,
        PlannedTradeSide.BUY,
    ]
    expected_sides = [OrderSide.SELL, OrderSide.BUY]
    assert [item.side for item in result.proposal_result.proposals] == expected_sides
    assert [
        item.decision.proposal.side for item in result.risk_result.evaluations
    ] == expected_sides
    created_ids = [item.request.order_id for item in result.order_result.orders]
    assert [
        item.request.order_id for item in result.submission_result.orders
    ] == created_ids
    assert [item.order_id for item in result.fill_result.fills] == created_ids
    assert [
        item.fill.order_id for item in result.application_result.evaluations
    ] == created_ids
    assert all(
        order.status is OrderStatus.FILLED for order in runtime.engine.orders.values()
    )
    assert runtime.ledger.cash == Decimal("550")
    assert runtime.ledger.positions[SPY].quantity == Decimal("5")
    assert runtime.ledger.positions[QQQ].quantity == Decimal("5")
    assert result.status is PaperPortfolioCycleStatus.APPLIED


def test_risk_resized_buy_quantity_is_preserved_through_application() -> None:
    state = PortfolioState(
        NOW,
        (PortfolioPositionState(SPY, Decimal("0"), Decimal("0"), Decimal("100")),),
        Decimal("1000"),
        Decimal("1000"),
    )
    target = TargetPortfolio(
        UUID(int=702),
        NOW,
        (TargetAllocation(SPY, Decimal("0.8")),),
        Decimal("0.2"),
        AllocationSource.MANUAL,
    )
    request = _custom_request(
        state,
        target,
        (PaperPortfolioCyclePrice(SPY, Decimal("100"), Decimal("100")),),
        limits=RiskLimits(
            max_position_percent=Decimal("0.3"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
        ),
    )
    runtime = PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("1000")))
    result = runtime.run_cycle(request)
    decision = result.risk_result.evaluations[0].decision

    assert decision.outcome is RiskOutcome.RESIZED
    assert (
        Decimal("0") < decision.approved_quantity < decision.proposal.desired_quantity
    )
    quantities = (
        result.order_result.orders[0].request.quantity,
        result.submission_result.orders[0].request.quantity,
        result.fill_result.fills[0].quantity,
        result.application_result.evaluations[0].fill.quantity,
        runtime.ledger.positions[SPY].quantity,
    )
    assert quantities == (decision.approved_quantity,) * 5
    assert result.status is PaperPortfolioCycleStatus.APPLIED


def test_sell_cycle_reconciles_commission_cash_position_and_realized_pnl() -> None:
    ledger = PaperLedger(Decimal("1000"))
    _seed_position(ledger, SPY, quantity="10", price="50")
    state = PortfolioState(
        NOW,
        (PortfolioPositionState(SPY, Decimal("10"), Decimal("50"), Decimal("60")),),
        Decimal("500"),
        Decimal("1100"),
    )
    target = TargetPortfolio(
        UUID(int=703),
        NOW,
        (TargetAllocation(SPY, Decimal("0")),),
        Decimal("1"),
        AllocationSource.MANUAL,
    )
    request = _custom_request(
        state,
        target,
        (PaperPortfolioCyclePrice(SPY, Decimal("60"), Decimal("65")),),
        limits=RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            estimated_commission=Decimal("2"),
        ),
        commission="2",
    )
    runtime = PaperPortfolioRuntime(OrderEngine(), ledger)
    result = runtime.run_cycle(request)
    fill = result.fill_result.fills[0]
    audit = result.application_result.evaluations[0]
    order = tuple(runtime.engine.orders.values())[0]

    assert fill.quantity == Decimal("10")
    assert fill.price == Decimal("65") and fill.commission == Decimal("2")
    assert runtime.ledger.cash == Decimal("1148")
    assert SPY not in runtime.ledger.positions
    assert runtime.ledger.realized_profit_loss == Decimal("148")
    assert order.status is OrderStatus.FILLED
    assert runtime.engine.get_fills(order.request.order_id) == (fill,)
    assert runtime.ledger.fills[-1] == fill
    assert audit.ledger_cash_after == runtime.ledger.cash
    assert audit.ledger_position_after is None
    assert (
        audit.ledger_realized_profit_loss_after == runtime.ledger.realized_profit_loss
    )
    assert result.post_ledger_state_id == result.application_result.post_ledger_state_id
