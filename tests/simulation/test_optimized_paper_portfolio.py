from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.execution import OrderEngine, PaperFillPolicy
from trading_bot.ledger import PaperLedger
from trading_bot.market_data import Timeframe
from trading_bot.optimization import CpuMeanCvarOptimizer
from trading_bot.optimization.exceptions import NumericalConversionError
from trading_bot.portfolio import (
    ExpectedReturn,
    ForecastHorizon,
    IneligibleOptimizedTargetError,
    MeanCvarOptimizationParameters,
    MetadataEntry,
    OptimizationStatus,
    OptimizedTargetPortfolioFactory,
    PortfolioConstraints,
    ReturnScenario,
    ReturnScenarioSet,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import PaperPortfolioCyclePrice, PaperPortfolioRuntime
from trading_bot.simulation import (
    InvalidOptimizedPaperSimulationFrameError,
    InvalidOptimizedPaperSimulationRequestError,
    OptimizedPaperPortfolioSimulator,
    OptimizedPaperSimulationCertificationError,
    OptimizedPaperSimulationFrame,
    OptimizedPaperSimulationOptimizationError,
    OptimizedPaperSimulationRequest,
    PaperPortfolioSimulationCycleError,
    PaperPortfolioSimulationStateDerivationError,
    PaperPortfolioSimulationStatus,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
HORIZON = ForecastHorizon(1, Timeframe.DAY_1)


def _scenarios(offset: int, symbols: tuple[Symbol, ...]) -> ReturnScenarioSet:
    as_of = NOW + timedelta(days=offset)
    return ReturnScenarioSet(
        UUID(int=200 + offset),
        as_of,
        HORIZON,
        symbols,
        (
            ReturnScenario(
                UUID(int=300 + offset * 2),
                (Decimal("0.1"),) * len(symbols),
                Decimal("0.5"),
            ),
            ReturnScenario(
                UUID(int=301 + offset * 2),
                (Decimal("-0.1"),) * len(symbols),
                Decimal("0.5"),
            ),
        ),
    )


def _frame(
    offset: int,
    desired_weights: tuple[str, ...],
    *,
    symbols: tuple[Symbol, ...] = (SPY,),
    risk_prices: tuple[str, ...] | None = None,
    fill_prices: tuple[str, ...] | None = None,
    commission: str = "0",
    metadata: tuple[MetadataEntry, ...] = (),
) -> OptimizedPaperSimulationFrame:
    as_of = NOW + timedelta(days=offset)
    risk_prices = risk_prices or ("100",) * len(symbols)
    fill_prices = fill_prices or risk_prices
    fee = Decimal(commission)
    return OptimizedPaperSimulationFrame(
        as_of,
        tuple(
            PaperPortfolioCyclePrice(symbol, Decimal(risk_price), Decimal(fill_price))
            for symbol, risk_price, fill_price in zip(
                symbols, risk_prices, fill_prices, strict=True
            )
        ),
        tuple(
            ExpectedReturn(symbol, Decimal(weight))
            for symbol, weight in zip(symbols, desired_weights, strict=True)
        ),
        _scenarios(offset, symbols),
        MeanCvarOptimizationParameters(Decimal("0.75")),
        Decimal("1"),
        PortfolioConstraints(maximum_position_weight=Decimal("1")),
        RebalanceAssumptions(fixed_commission=fee),
        RebalanceProposalPolicy(allow_partial_plans=bool(fee)),
        None,
        RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            estimated_commission=fee,
        ),
        PortfolioRiskPolicy(),
        PaperFillPolicy(Decimal("0"), fee),
        True,
        as_of + timedelta(minutes=1),
        as_of + timedelta(minutes=2),
        metadata,
    )


def _request(*frames: OptimizedPaperSimulationFrame):
    return OptimizedPaperSimulationRequest(
        UUID(int=1), frames, (MetadataEntry("source", "test"),)
    )


class _WeightOptimizer:
    def optimize(self, request):  # noqa: ANN001, ANN201
        weights = [item.value for item in request.base_request.expected_returns]
        cash = Decimal("1") - sum(weights, start=Decimal("0"))
        raw = SimpleNamespace(
            status=0,
            x=[*(float(item) for item in weights), float(cash), 0, 0, 0],
            message="test",
        )

        def solve(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            return raw

        return CpuMeanCvarOptimizer(
            _solver=solve, _solver_identity="scipy-highs-test"
        ).optimize(request)


class _Simulator(OptimizedPaperPortfolioSimulator):
    _optimizer_type = _WeightOptimizer


def _simulator() -> OptimizedPaperPortfolioSimulator:
    return _Simulator(
        PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("1000")))
    )


def test_one_frame_optimized_buy_preserves_exact_handoffs() -> None:
    simulator = _simulator()
    result = simulator.run(_request(_frame(0, ("0.2",))))
    evaluation = result.evaluations[0]
    target = evaluation.optimization_result.optimization_result.target
    assert result.status is PaperPortfolioSimulationStatus.COMPLETED
    assert target is not None
    assert evaluation.optimized_target_result.target is target
    assert evaluation.cycle_result.request.inputs.target is target
    assert (
        evaluation.optimization_result.request.base_request.state
        is evaluation.derived_state
    )
    assert evaluation.optimized_target_result.request.state is evaluation.derived_state
    assert simulator.ledger.positions[SPY].quantity == Decimal("2")
    assert simulator.ledger.cash == Decimal("800")


def test_position_increase_partial_sale_and_liquidation_carry_state() -> None:
    simulator = _simulator()
    result = simulator.run(
        _request(
            _frame(0, ("0.2",)),
            _frame(1, ("0.4",)),
            _frame(2, ("0.2",)),
            _frame(3, ("0",), fill_prices=("110",)),
        )
    )
    assert [
        item.derived_state.positions[0].quantity for item in result.evaluations
    ] == [
        Decimal("0"),
        Decimal("2"),
        Decimal("4"),
        Decimal("2"),
    ]
    assert SPY not in simulator.ledger.positions
    assert simulator.ledger.cash == Decimal("1020")
    assert simulator.ledger.realized_profit_loss == Decimal("20")


def test_zero_weight_held_symbol_and_positive_flat_new_entry_are_retained() -> None:
    simulator = _simulator()
    result = simulator.run(
        _request(
            _frame(0, ("0.5", "0"), symbols=(SPY, QQQ)),
            _frame(1, ("0", "0.5"), symbols=(SPY, QQQ)),
        )
    )
    target = result.evaluations[1].optimized_target_result.target
    assert tuple(item.weight for item in target.allocations) == (
        Decimal("0"),
        Decimal("0.50000000"),
    )
    assert result.evaluations[0].derived_state.positions[1].quantity == Decimal("0")
    assert SPY not in simulator.ledger.positions
    assert simulator.ledger.positions[QQQ].quantity == Decimal("5")


def test_cash_commissions_and_realized_pnl_accumulate() -> None:
    simulator = _simulator()
    result = simulator.run(
        _request(
            _frame(0, ("0.2",), commission="2"),
            _frame(1, ("0",), fill_prices=("110",), commission="2"),
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


def test_all_no_action_and_applied_no_action_applied_statuses() -> None:
    no_action = _simulator().run(_request(_frame(0, ("0",)), _frame(1, ("0",))))
    assert no_action.status is PaperPortfolioSimulationStatus.NO_ACTION
    assert no_action.no_action_cycle_count == 2 and len(no_action.diagnostics) == 1
    mixed = _simulator().run(
        _request(_frame(0, ("0.2",)), _frame(1, ("0.2",)), _frame(2, ("0",)))
    )
    assert [item.cycle_result.status.value for item in mixed.evaluations] == [
        "APPLIED",
        "NO_ACTION",
        "APPLIED",
    ]


@pytest.mark.parametrize(
    "status",
    (
        OptimizationStatus.INFEASIBLE,
        OptimizationStatus.UNBOUNDED,
        OptimizationStatus.FAILED,
        OptimizationStatus.UNAVAILABLE,
    ),
)
def test_unsuccessful_optimization_stops_before_runtime(status) -> None:  # noqa: ANN001
    class FailedOptimizer:
        def optimize(self, request):  # noqa: ANN001, ANN201
            successful = _WeightOptimizer().optimize(request)
            portfolio = object.__new__(type(successful.optimization_result))
            for field in __import__("dataclasses").fields(
                successful.optimization_result
            ):
                value = getattr(successful.optimization_result, field.name)
                object.__setattr__(
                    portfolio,
                    field.name,
                    status
                    if field.name == "status"
                    else None
                    if field.name in {"target", "objective_value"}
                    else value,
                )
            specialized = object.__new__(type(successful))
            object.__setattr__(specialized, "request", successful.request)
            object.__setattr__(specialized, "optimization_result", portfolio)
            object.__setattr__(specialized, "expected_portfolio_return", None)
            object.__setattr__(specialized, "cvar", None)
            return specialized

    class FailedSimulator(OptimizedPaperPortfolioSimulator):
        _optimizer_type = FailedOptimizer

    simulator = FailedSimulator(
        PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("1000")))
    )
    with pytest.raises(OptimizedPaperSimulationOptimizationError) as caught:
        simulator.run(_request(_frame(0, ("0.2",))))
    assert caught.value.frame_ordinal == 0 and caught.value.status is status
    assert simulator.ledger.cash == Decimal("1000") and simulator.engine.orders == {}


def test_certification_failure_retains_ordinal_and_cause() -> None:
    class FailedFactory(OptimizedTargetPortfolioFactory):
        def create(self, request):  # noqa: ANN001, ANN201
            raise IneligibleOptimizedTargetError("test")

    class FailedSimulator(_Simulator):
        _target_factory_type = FailedFactory

    simulator = FailedSimulator(
        PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("1000")))
    )
    with pytest.raises(OptimizedPaperSimulationCertificationError) as caught:
        simulator.run(_request(_frame(0, ("0.2",))))
    assert caught.value.frame_ordinal == 0
    assert isinstance(caught.value.__cause__, IneligibleOptimizedTargetError)
    assert simulator.ledger.cash == Decimal("1000")


def test_known_optimizer_exception_retains_ordinal_and_cause() -> None:
    class RaisingOptimizer:
        def optimize(self, request):  # noqa: ANN001, ANN201
            raise NumericalConversionError("test")

    class RaisingSimulator(OptimizedPaperPortfolioSimulator):
        _optimizer_type = RaisingOptimizer

    simulator = RaisingSimulator(
        PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("1000")))
    )
    with pytest.raises(OptimizedPaperSimulationOptimizationError) as caught:
        simulator.run(_request(_frame(0, ("0.2",))))
    assert caught.value.frame_ordinal == 0 and caught.value.status is None
    assert isinstance(caught.value.__cause__, NumericalConversionError)
    assert simulator.ledger.cash == Decimal("1000")


def test_later_runtime_failure_preserves_prior_frame_commit() -> None:
    simulator = _simulator()
    with pytest.raises(PaperPortfolioSimulationCycleError) as caught:
        simulator.run(
            _request(
                _frame(0, ("0.2",)),
                _frame(1, ("1",), fill_prices=("1000",)),
            )
        )
    assert caught.value.frame_ordinal == 1 and caught.value.__cause__ is not None
    assert simulator.ledger.positions[SPY].quantity == Decimal("2")
    assert simulator.ledger.cash == Decimal("800")


def test_missing_held_symbol_fails_before_optimization_after_prior_commit() -> None:
    simulator = _simulator()
    with pytest.raises(PaperPortfolioSimulationStateDerivationError):
        simulator.run(
            _request(
                _frame(0, ("0.2",)),
                _frame(1, ("0.2",), symbols=(QQQ,)),
            )
        )
    assert simulator.ledger.positions[SPY].quantity == Decimal("2")


def test_deterministic_stage_and_result_identities_repeat() -> None:
    request = _request(_frame(0, ("0",)), _frame(1, ("0.2",)))
    first = _simulator().run(request)
    second = _simulator().run(request)
    assert first == second
    assert [item.optimization_request_id for item in first.evaluations] == [
        item.optimization_request_id for item in second.evaluations
    ]
    assert first.final_engine_state_id == first.evaluations[-1].post_engine_state_id
    assert first.final_ledger_state_id == first.evaluations[-1].post_ledger_state_id


def test_changed_returns_and_scenario_contents_change_identity() -> None:
    base = _frame(0, ("0.2",))
    baseline = _simulator().run(_request(base))
    changed_return = _simulator().run(_request(_frame(0, ("0.3",))))
    scenarios = base.scenarios
    changed_scenarios = ReturnScenarioSet(
        scenarios.scenario_set_id,
        scenarios.as_of,
        scenarios.forecast_horizon,
        scenarios.symbols,
        (
            ReturnScenario(
                scenarios.scenarios[0].scenario_id,
                (Decimal("0.2"),),
                scenarios.scenarios[0].probability,
            ),
            scenarios.scenarios[1],
        ),
        scenarios.cash_return,
        scenarios.source,
        scenarios.source_name,
        scenarios.metadata,
    )
    changed_scenario = _simulator().run(
        _request(replace(base, scenarios=changed_scenarios))
    )
    assert baseline.result_id != changed_return.result_id
    assert baseline.result_id != changed_scenario.result_id


def test_static_validation_and_metadata_copying() -> None:
    frame = _frame(0, ("0",))
    frames = [frame]
    metadata = [MetadataEntry("caller", "test")]
    request = OptimizedPaperSimulationRequest(UUID(int=2), frames, metadata)
    frames.clear()
    metadata.clear()
    assert request.frames == (frame,)
    assert request.metadata == (MetadataEntry("caller", "test"),)
    with pytest.raises(InvalidOptimizedPaperSimulationRequestError, match="at least"):
        OptimizedPaperSimulationRequest(UUID(int=1), ())
    with pytest.raises(InvalidOptimizedPaperSimulationRequestError, match="increase"):
        _request(frame, frame)
    with pytest.raises(InvalidOptimizedPaperSimulationFrameError, match="reserved"):
        _frame(
            0,
            ("0",),
            metadata=(MetadataEntry("optimized_simulation_bad", "x"),),
        )


def test_price_return_and_scenario_order_mismatch_is_rejected() -> None:
    base = _frame(0, ("0", "0"), symbols=(SPY, QQQ))
    with pytest.raises(InvalidOptimizedPaperSimulationFrameError, match="return"):
        OptimizedPaperSimulationFrame(
            base.as_of,
            base.prices,
            tuple(reversed(base.expected_returns)),
            base.scenarios,
            base.optimization_parameters,
            base.risk_aversion,
            base.portfolio_constraints,
            base.rebalance_assumptions,
            base.proposal_policy,
            None,
            base.risk_limits,
            base.risk_policy,
            base.fill_policy,
            True,
            base.submitted_at,
            base.filled_at,
        )
