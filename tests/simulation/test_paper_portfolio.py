from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.execution import OrderEngine, PaperFillPolicy
from trading_bot.ledger import PaperLedger
from trading_bot.portfolio import (
    AllocationSource,
    MetadataEntry,
    TargetAllocation,
    TargetPortfolio,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits, RiskOutcome
from trading_bot.runtime import PaperPortfolioCyclePrice, PaperPortfolioRuntime
from trading_bot.simulation import (
    InvalidPaperPortfolioSimulationFrameError,
    InvalidPaperPortfolioSimulationRequestError,
    PaperPortfolioSimulationCycleError,
    PaperPortfolioSimulationFrame,
    PaperPortfolioSimulationRequest,
    PaperPortfolioSimulationStateDerivationError,
    PaperPortfolioSimulationStatus,
    PaperPortfolioSimulator,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _frame(
    offset: int,
    weights: tuple[str, ...],
    *,
    symbols: tuple[Symbol, ...] = (SPY,),
    risk_prices: tuple[str, ...] | None = None,
    fill_prices: tuple[str, ...] | None = None,
    trading_enabled: bool = True,
    allow_partial_plans: bool = False,
    commission: str = "0",
    limits: RiskLimits | None = None,
    metadata: tuple[MetadataEntry, ...] = (),
) -> PaperPortfolioSimulationFrame:
    as_of = NOW + timedelta(days=offset)
    risk_prices = risk_prices or ("100",) * len(symbols)
    fill_prices = fill_prices or risk_prices
    target = TargetPortfolio(
        UUID(int=100 + offset),
        as_of,
        tuple(
            TargetAllocation(symbol, Decimal(weight))
            for symbol, weight in zip(symbols, weights, strict=True)
        ),
        Decimal("1") - sum((Decimal(item) for item in weights), start=Decimal("0")),
        AllocationSource.MANUAL,
    )
    fee = Decimal(commission)
    return PaperPortfolioSimulationFrame(
        as_of,
        target,
        tuple(
            PaperPortfolioCyclePrice(symbol, Decimal(risk_price), Decimal(fill_price))
            for symbol, risk_price, fill_price in zip(
                symbols, risk_prices, fill_prices, strict=True
            )
        ),
        RebalanceAssumptions(fixed_commission=fee),
        None,
        RebalanceProposalPolicy(allow_partial_plans),
        None,
        limits
        or RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            estimated_commission=fee,
        ),
        PortfolioRiskPolicy(),
        PaperFillPolicy(Decimal("0"), fee),
        trading_enabled,
        as_of + timedelta(minutes=1),
        as_of + timedelta(minutes=2),
        metadata,
    )


def _request(*frames: PaperPortfolioSimulationFrame):
    return PaperPortfolioSimulationRequest(
        UUID(int=1), frames, (MetadataEntry("source", "test"),)
    )


def _simulator(cash: str = "1000") -> PaperPortfolioSimulator:
    return PaperPortfolioSimulator(
        PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal(cash)))
    )


def test_one_frame_buy_derives_state_and_returns_completed_result() -> None:
    simulator = _simulator()
    result = simulator.run(_request(_frame(0, ("0.2",))))
    evaluation = result.evaluations[0]
    assert result.status is PaperPortfolioSimulationStatus.COMPLETED
    assert result.applied_cycle_count == 1 and result.no_action_cycle_count == 0
    assert evaluation.derived_state.cash == Decimal("1000")
    assert evaluation.derived_state.equity == Decimal("1000")
    assert evaluation.derived_state.positions[0].quantity == Decimal("0")
    assert simulator.ledger.cash == Decimal("800")
    assert simulator.ledger.positions[SPY].quantity == Decimal("2")
    assert result.final_engine_state_id == evaluation.post_engine_state_id
    assert result.final_ledger_state_id == evaluation.post_ledger_state_id


def test_two_frames_carry_state_forward_and_increase_position() -> None:
    simulator = _simulator()
    result = simulator.run(_request(_frame(0, ("0.2",)), _frame(1, ("0.4",))))
    first, second = result.evaluations
    assert second.derived_state.cash == Decimal("800")
    assert second.derived_state.positions[0].quantity == Decimal("2")
    assert second.derived_state.positions[0].average_cost == Decimal("100")
    assert second.derived_state.equity == Decimal("1000")
    assert first.post_engine_state_id == second.pre_engine_state_id
    assert first.post_ledger_state_id == second.pre_ledger_state_id
    assert simulator.ledger.positions[SPY].quantity == Decimal("4")


def test_buy_no_action_then_liquidation_tracks_realized_pnl() -> None:
    simulator = _simulator()
    result = simulator.run(
        _request(
            _frame(0, ("0.2",)),
            _frame(1, ("0.2",)),
            _frame(2, ("0",), risk_prices=("110",), fill_prices=("115",)),
        )
    )
    assert [item.cycle_result.status.value for item in result.evaluations] == [
        "APPLIED",
        "NO_ACTION",
        "APPLIED",
    ]
    assert result.applied_cycle_count == 2 and result.no_action_cycle_count == 1
    assert SPY not in simulator.ledger.positions
    assert simulator.ledger.cash == Decimal("1030")
    assert simulator.ledger.realized_profit_loss == Decimal("30")


def test_buy_then_partial_sell_retains_cost_basis_and_state_carry_forward() -> None:
    simulator = _simulator()
    result = simulator.run(_request(_frame(0, ("0.4",)), _frame(1, ("0.2",))))
    assert result.evaluations[1].derived_state.positions[0].quantity == Decimal("4")
    assert simulator.ledger.positions[SPY].quantity == Decimal("2")
    assert simulator.ledger.positions[SPY].average_cost == Decimal("100")
    assert simulator.ledger.cash == Decimal("800")


def test_liquidation_proceeds_are_available_to_a_later_symbol_frame() -> None:
    simulator = _simulator()
    result = simulator.run(
        _request(
            _frame(0, ("0.8",)),
            _frame(1, ("0",)),
            _frame(2, ("0", "0.8"), symbols=(SPY, QQQ)),
        )
    )
    assert result.applied_cycle_count == 3
    assert SPY not in simulator.ledger.positions
    assert simulator.ledger.positions[QQQ].quantity == Decimal("8")
    assert simulator.ledger.cash == Decimal("200")


def test_commissions_accumulate_across_buy_and_liquidation() -> None:
    simulator = _simulator()
    result = simulator.run(
        _request(
            _frame(0, ("0.2",), commission="2", allow_partial_plans=True),
            _frame(
                1,
                ("0",),
                risk_prices=("110",),
                fill_prices=("110",),
                commission="2",
                allow_partial_plans=True,
            ),
        )
    )
    fills = tuple(
        fill
        for evaluation in result.evaluations
        for fill in evaluation.cycle_result.fill_result.fills
    )
    assert tuple(item.commission for item in fills) == (Decimal("2"), Decimal("2"))
    assert simulator.ledger.cash == Decimal("1015.8")
    assert simulator.ledger.realized_profit_loss == Decimal("15.8")


def test_all_no_action_and_rejected_then_later_action_statuses() -> None:
    no_action = _simulator().run(_request(_frame(0, ("0",)), _frame(1, ("0",))))
    assert no_action.status is PaperPortfolioSimulationStatus.NO_ACTION
    assert no_action.applied_cycle_count == 0 and no_action.no_action_cycle_count == 2
    assert len(no_action.diagnostics) == 1

    simulator = _simulator()
    mixed = simulator.run(
        _request(
            _frame(0, ("0.2",), trading_enabled=False),
            _frame(1, ("0.2",)),
        )
    )
    assert mixed.evaluations[0].cycle_result.risk_result.rejected_count == 1
    assert mixed.status is PaperPortfolioSimulationStatus.COMPLETED
    assert simulator.ledger.positions[SPY].quantity == Decimal("2")


def test_risk_resize_is_retained_across_frames() -> None:
    limits = RiskLimits(
        max_position_percent=Decimal("0.3"),
        max_total_exposure_percent=Decimal("1"),
        minimum_cash_reserve_percent=Decimal("0"),
    )
    simulator = _simulator()
    result = simulator.run(_request(_frame(0, ("0.8",), limits=limits)))
    decision = result.evaluations[0].cycle_result.risk_result.evaluations[0].decision
    assert decision.outcome is RiskOutcome.RESIZED
    assert decision.approved_quantity == Decimal("3")
    assert simulator.ledger.positions[SPY].quantity == Decimal("3")


def test_risk_prices_value_state_and_fill_prices_only_execute() -> None:
    simulator = _simulator()
    result = simulator.run(
        _request(
            _frame(0, ("0.2",)),
            _frame(
                1,
                ("0.3",),
                risk_prices=("120",),
                fill_prices=("999",),
                trading_enabled=False,
                allow_partial_plans=True,
            ),
        )
    )
    state = result.evaluations[1].derived_state
    assert state.positions[0].current_price == Decimal("120")
    assert state.equity == Decimal("1040")
    assert result.evaluations[1].cycle_result.status.value == "NO_ACTION"


def test_request_and_frames_defensively_copy_and_validate_metadata() -> None:
    frame = _frame(0, ("0",))
    values = [frame]
    metadata = [MetadataEntry("caller", "value")]
    request = PaperPortfolioSimulationRequest(UUID(int=2), values, metadata)
    values.clear()
    metadata.clear()
    assert request.frames == (frame,)
    assert request.metadata == (MetadataEntry("caller", "value"),)
    with pytest.raises(InvalidPaperPortfolioSimulationFrameError, match="reserved"):
        _frame(0, ("0",), metadata=(MetadataEntry("simulation_bad", "x"),))
    with pytest.raises(InvalidPaperPortfolioSimulationRequestError, match="overlap"):
        PaperPortfolioSimulationRequest(
            UUID(int=2),
            (_frame(0, ("0",), metadata=(MetadataEntry("same", "x"),)),),
            (MetadataEntry("same", "y"),),
        )


def test_static_validation_rejects_empty_and_bad_frame_chronology() -> None:
    with pytest.raises(InvalidPaperPortfolioSimulationRequestError, match="at least"):
        PaperPortfolioSimulationRequest(UUID(int=1), ())
    first = _frame(0, ("0",))
    with pytest.raises(InvalidPaperPortfolioSimulationRequestError, match="increase"):
        _request(first, first)
    with pytest.raises(InvalidPaperPortfolioSimulationFrameError, match="aware"):
        PaperPortfolioSimulationFrame(
            datetime(2026, 7, 21),
            first.target,
            first.prices,
            first.rebalance_assumptions,
            None,
            first.proposal_policy,
            None,
            first.risk_limits,
            first.risk_policy,
            first.fill_policy,
            True,
            first.submitted_at,
            first.filled_at,
        )


def test_target_price_order_and_commissions_are_statically_validated() -> None:
    base = _frame(0, ("0", "0"), symbols=(SPY, QQQ))
    with pytest.raises(InvalidPaperPortfolioSimulationFrameError, match="symbol order"):
        PaperPortfolioSimulationFrame(
            base.as_of,
            base.target,
            tuple(reversed(base.prices)),
            base.rebalance_assumptions,
            None,
            base.proposal_policy,
            None,
            base.risk_limits,
            base.risk_policy,
            base.fill_policy,
            True,
            base.submitted_at,
            base.filled_at,
        )
    with pytest.raises(InvalidPaperPortfolioSimulationFrameError, match="commissions"):
        PaperPortfolioSimulationFrame(
            base.as_of,
            base.target,
            base.prices,
            RebalanceAssumptions(fixed_commission=Decimal("1")),
            None,
            base.proposal_policy,
            None,
            base.risk_limits,
            base.risk_policy,
            base.fill_policy,
            True,
            base.submitted_at,
            base.filled_at,
        )


def test_missing_held_symbol_fails_after_prior_frame_remains_committed() -> None:
    simulator = _simulator()
    request = _request(
        _frame(0, ("0.2",)),
        _frame(1, ("0",), symbols=(QQQ,)),
    )
    with pytest.raises(PaperPortfolioSimulationStateDerivationError, match="SPY"):
        simulator.run(request)
    assert simulator.ledger.positions[SPY].quantity == Decimal("2")
    assert simulator.ledger.cash == Decimal("800")


def test_later_cycle_failure_preserves_prior_commit_and_exposes_ordinal() -> None:
    simulator = _simulator()
    request = _request(
        _frame(0, ("0.2",)),
        _frame(1, ("1",), risk_prices=("100",), fill_prices=("1000",)),
    )
    with pytest.raises(PaperPortfolioSimulationCycleError) as caught:
        simulator.run(request)
    assert caught.value.frame_ordinal == 1
    assert caught.value.__cause__ is not None
    assert simulator.ledger.positions[SPY].quantity == Decimal("2")
    assert simulator.ledger.cash == Decimal("800")
    assert len(simulator.engine.orders) == 1


def test_cycle_and_result_identities_are_deterministic_and_chain_no_action() -> None:
    request = _request(
        _frame(0, ("0",)),
        _frame(1, ("0.2",)),
    )
    first = _simulator().run(request)
    second = _simulator().run(request)
    assert first.result_id == second.result_id
    assert [item.cycle_request_id for item in first.evaluations] == [
        item.cycle_request_id for item in second.evaluations
    ]
    assert (
        first.evaluations[0].cycle_result.result_id
        != first.evaluations[1].cycle_request_id
    )
    assert first.final_engine_state_id == first.evaluations[-1].post_engine_state_id
    assert first.final_ledger_state_id == first.evaluations[-1].post_ledger_state_id


def test_runtime_properties_always_delegate_to_current_runtime_components() -> None:
    runtime = PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("1000")))
    simulator = PaperPortfolioSimulator(runtime)
    old_engine, old_ledger = simulator.engine, simulator.ledger
    simulator.run(_request(_frame(0, ("0.2",))))
    assert simulator.runtime is runtime
    assert simulator.engine is runtime.engine and simulator.ledger is runtime.ledger
    assert simulator.engine is not old_engine and simulator.ledger is not old_ledger
