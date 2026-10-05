import os
import subprocess
import sys
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.domain import OrderFill, OrderSide, Symbol
from trading_bot.execution import OrderEngine, PaperFillPolicy
from trading_bot.ledger import PaperLedger
from trading_bot.market_data import Timeframe
from trading_bot.optimization import CpuMeanCvarOptimizer
from trading_bot.portfolio import (
    ExpectedReturn,
    ForecastHorizon,
    MeanCvarOptimizationParameters,
    MetadataEntry,
    PortfolioConstraints,
    ReturnScenario,
    ReturnScenarioSet,
)
from trading_bot.portfolio_analytics import (
    InconsistentOptimizedSimulationPerformanceResultError,
    InvalidOptimizedSimulationPerformanceRequestError,
    OptimizedSimulationEquityPhase,
    OptimizedSimulationPerformanceAnalyzer,
    OptimizedSimulationPerformanceDiagnosticCode,
    OptimizedSimulationPerformanceReconciliationError,
    OptimizedSimulationPerformanceRequest,
    OptimizedSimulationPerformanceResult,
    OptimizedSimulationValuationBasis,
    OptimizedSimulationValuationError,
    OptimizedSimulationValuationPolicy,
)
from trading_bot.portfolio_analytics.optimized_simulation import _execution_metrics
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import PaperPortfolioCyclePrice, PaperPortfolioRuntime
from trading_bot.simulation import (
    OptimizedPaperPortfolioSimulator,
    OptimizedPaperSimulationFrame,
    OptimizedPaperSimulationRequest,
)


@pytest.mark.parametrize(
    "module_order",
    [
        ("trading_bot.portfolio_analytics",),
        ("trading_bot.portfolio_analytics", "trading_bot.simulation"),
        ("trading_bot.simulation", "trading_bot.portfolio_analytics"),
    ],
)
def test_package_import_order_in_clean_interpreter(
    module_order: tuple[str, ...], tmp_path: Path
) -> None:
    source = Path(__file__).resolve().parents[2] / "src"
    code = "\n".join(
        [
            "from pathlib import Path",
            "import sys",
            "import trading_bot",
            "source = Path(sys.argv[1]).resolve()",
            "package_path = Path(trading_bot.__file__).resolve()",
            "assert package_path == source / 'trading_bot' / '__init__.py'",
            *(f"import {name}" for name in module_order),
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(source), *module_order],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(source)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


NOW = datetime(2026, 7, 22, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
HORIZON = ForecastHorizon(1, Timeframe.DAY_1)


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
            _solver=solve, _solver_identity="scipy-highs-analytics-test"
        ).optimize(request)


class _Simulator(OptimizedPaperPortfolioSimulator):
    _optimizer_type = _WeightOptimizer


def _scenarios(offset: int, symbols: tuple[Symbol, ...]) -> ReturnScenarioSet:
    return ReturnScenarioSet(
        UUID(int=100 + offset),
        NOW + timedelta(days=offset),
        HORIZON,
        symbols,
        (
            ReturnScenario(
                UUID(int=200 + offset * 2),
                (Decimal("0.1"),) * len(symbols),
                Decimal("0.5"),
            ),
            ReturnScenario(
                UUID(int=201 + offset * 2),
                (Decimal("-0.1"),) * len(symbols),
                Decimal("0.5"),
            ),
        ),
    )


def _frame(
    offset: int,
    weights: tuple[str, ...],
    *,
    symbols: tuple[Symbol, ...] = (SPY,),
    risk_prices: tuple[str, ...] | None = None,
    fill_prices: tuple[str, ...] | None = None,
    commission: str = "0",
    slippage_bps: str = "0",
    max_new_position: str | None = None,
) -> OptimizedPaperSimulationFrame:
    as_of = NOW + timedelta(days=offset)
    risk_prices = risk_prices or ("100",) * len(symbols)
    fill_prices = fill_prices or risk_prices
    fee = Decimal(commission)
    return OptimizedPaperSimulationFrame(
        as_of,
        tuple(
            PaperPortfolioCyclePrice(symbol, Decimal(risk), Decimal(fill))
            for symbol, risk, fill in zip(
                symbols, risk_prices, fill_prices, strict=True
            )
        ),
        tuple(
            ExpectedReturn(symbol, Decimal(weight))
            for symbol, weight in zip(symbols, weights, strict=True)
        ),
        _scenarios(offset, symbols),
        MeanCvarOptimizationParameters(Decimal("0.75")),
        Decimal("1"),
        PortfolioConstraints(maximum_position_weight=Decimal("1")),
        RebalanceAssumptions(fixed_commission=fee),
        RebalanceProposalPolicy(allow_partial_plans=True),
        None,
        RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            max_new_position_percent=(
                None if max_new_position is None else Decimal(max_new_position)
            ),
            minimum_cash_reserve_percent=Decimal("0"),
            estimated_commission=fee,
        ),
        PortfolioRiskPolicy(),
        PaperFillPolicy(Decimal(slippage_bps), fee),
        True,
        as_of + timedelta(minutes=1),
        as_of + timedelta(minutes=2),
    )


def _simulation(
    *frames_: OptimizedPaperSimulationFrame,
    ledger: PaperLedger | None = None,
):
    ledger = ledger or PaperLedger(Decimal("1000"))
    simulator = _Simulator(PaperPortfolioRuntime(OrderEngine(), ledger))
    return simulator.run(OptimizedPaperSimulationRequest(UUID(int=1), frames_))


def _analyze(result, *, request_id: int = 2, metadata=()):  # type: ignore[no-untyped-def]
    request = OptimizedSimulationPerformanceRequest(
        UUID(int=request_id), result, metadata=metadata
    )
    return OptimizedSimulationPerformanceAnalyzer().analyze(request)


def _seed_position(
    ledger: PaperLedger,
    symbol: Symbol,
    quantity: str,
    price: str,
) -> None:
    ledger.apply_fill(
        OrderFill(
            UUID(int=800),
            UUID(int=801),
            symbol,
            OrderSide.BUY,
            Decimal(quantity),
            Decimal(price),
            Decimal("0"),
            NOW - timedelta(days=1),
        )
    )


def _unsafe_replace(instance, **changes):  # type: ignore[no-untyped-def]
    replacement = object.__new__(type(instance))
    for field in fields(instance):
        object.__setattr__(
            replacement,
            field.name,
            changes.get(field.name, getattr(instance, field.name)),
        )
    return replacement


def test_one_frame_buy_at_reference_has_exact_execution_only_return() -> None:
    report = _analyze(_simulation(_frame(0, ("0.2",))))
    frame = report.frames[0]
    assert report.initial_equity == report.final_equity == Decimal("1000")
    assert report.absolute_simulation_profit_loss == Decimal("0")
    assert report.simulation_return == frame.period_return == Decimal("0")
    assert frame.forward_market_profit_loss is None
    assert frame.gross_buy_notional == Decimal("200")
    assert frame.one_way_turnover == frame.two_way_turnover == Decimal("0.2")
    assert frame.maximum_absolute_allocation_drift == Decimal("0")


def test_no_action_diagnostics_and_observation_order() -> None:
    report = _analyze(_simulation(_frame(0, ("0",))))
    assert [item.code for item in report.diagnostics] == [
        OptimizedSimulationPerformanceDiagnosticCode.NO_TRADING_ACTIVITY,
        OptimizedSimulationPerformanceDiagnosticCode.ALL_CYCLES_NO_ACTION,
    ]
    assert [item.phase for item in report.equity_observations] == [
        OptimizedSimulationEquityPhase.PRE_CYCLE,
        OptimizedSimulationEquityPhase.POST_CYCLE,
    ]
    assert report.total_gross_traded_notional == Decimal("0")


def test_commission_and_adverse_buy_slippage_reconcile_execution() -> None:
    report = _analyze(
        _simulation(_frame(0, ("0.2",), commission="2", slippage_bps="100"))
    )
    frame = report.frames[0]
    assert frame.commission_cost == Decimal("2")
    assert frame.signed_slippage_profit_loss == Decimal("-1.98")
    assert frame.adverse_slippage_cost == Decimal("1.98")
    assert frame.execution_profit_loss == Decimal("-3.98")
    assert frame.total_execution_cost == Decimal("3.98")
    assert report.absolute_simulation_profit_loss == Decimal("-3.98")


def test_risk_reference_and_fill_prices_remain_distinct() -> None:
    report = _analyze(
        _simulation(
            _frame(
                0,
                ("0.2",),
                risk_prices=("100",),
                fill_prices=("99",),
                slippage_bps="100",
            )
        )
    )
    frame = report.frames[0]
    assert frame.gross_buy_notional == Decimal("199.98")
    assert frame.signed_slippage_profit_loss == Decimal("-1.98")
    assert frame.execution_profit_loss == Decimal("0.02")


def test_favorable_slippage_is_signed_and_not_adverse() -> None:
    fill = OrderFill(
        UUID(int=900),
        UUID(int=901),
        SPY,
        OrderSide.BUY,
        Decimal("1"),
        Decimal("99"),
        Decimal("0"),
        NOW,
    )
    evaluation = SimpleNamespace(fill=fill, reference_price=Decimal("100"))
    source = SimpleNamespace(
        cycle_result=SimpleNamespace(
            fill_result=SimpleNamespace(evaluations=(evaluation,))
        )
    )
    _, _, _, signed, adverse, impact = _execution_metrics(source, {SPY: Decimal("100")})
    assert signed == Decimal("1")
    assert adverse == Decimal("0")
    assert impact == Decimal("1")


def test_preexisting_position_sale_reports_simulation_relative_pnl() -> None:
    ledger = PaperLedger(Decimal("1000"))
    _seed_position(ledger, SPY, "5", "80")
    report = _analyze(_simulation(_frame(0, ("0",), commission="2"), ledger=ledger))
    frame = report.frames[0]
    assert report.initial_equity == Decimal("1100")
    assert report.initial_unrealized_profit_loss == Decimal("100")
    assert frame.frame_simulation_realized_profit_loss == Decimal("98")
    assert report.final_unrealized_profit_loss == Decimal("0")
    assert report.absolute_simulation_profit_loss == Decimal("-2")
    assert report.absolute_simulation_profit_loss == (
        report.cumulative_simulation_realized_profit_loss
        + report.final_unrealized_profit_loss
        - report.initial_unrealized_profit_loss
    )


def test_partial_sale_then_liquidation_preserves_average_cost() -> None:
    ledger = PaperLedger(Decimal("1000"))
    _seed_position(ledger, SPY, "10", "80")
    report = _analyze(
        _simulation(
            _frame(0, ("0.5",), risk_prices=("100",)),
            _frame(1, ("0",), risk_prices=("110",)),
            ledger=ledger,
        )
    )
    assert [item.frame_simulation_realized_profit_loss for item in report.frames] == [
        Decimal("80"),
        Decimal("180"),
    ]
    assert report.cumulative_simulation_realized_profit_loss == Decimal("260")
    assert report.frames[0].post_cycle_position_count == 1
    assert report.frames[1].post_cycle_position_count == 0


def test_forward_market_gain_and_cumulative_return() -> None:
    report = _analyze(
        _simulation(
            _frame(0, ("0.2",), risk_prices=("100",)),
            _frame(1, ("0.2",), risk_prices=("110",)),
        )
    )
    assert report.frames[0].forward_market_profit_loss == Decimal("20")
    assert report.frames[0].period_profit_loss == Decimal("20")
    assert report.frames[0].period_return == Decimal("0.02")
    assert report.frames[-1].cumulative_return == report.simulation_return


def test_drawdown_captures_pre_and_post_cycle_and_recovery() -> None:
    report = _analyze(
        _simulation(
            _frame(0, ("0.5",), risk_prices=("100",)),
            _frame(1, ("0.5",), risk_prices=("80",)),
            _frame(2, ("0.5",), risk_prices=("120",)),
        )
    )
    observations = report.equity_observations
    assert observations[2].phase is OptimizedSimulationEquityPhase.PRE_CYCLE
    assert observations[2].drawdown_amount == Decimal("100")
    assert report.maximum_drawdown_amount >= Decimal("100")
    assert observations[-1].equity > observations[2].equity


def test_resized_risk_reports_reduced_notional() -> None:
    report = _analyze(_simulation(_frame(0, ("0.8",), max_new_position="0.1")))
    frame = report.frames[0]
    assert frame.resized_risk_count == 1
    assert frame.reduced_notional == Decimal("700")
    assert frame.gross_buy_notional == Decimal("100")


def test_mixed_sell_buy_notional_and_aggregate_turnover() -> None:
    ledger = PaperLedger(Decimal("1000"))
    _seed_position(ledger, SPY, "5", "100")
    report = _analyze(
        _simulation(
            _frame(
                0,
                ("0", "0.5"),
                symbols=(SPY, QQQ),
                risk_prices=("100", "100"),
            ),
            ledger=ledger,
        )
    )
    frame = report.frames[0]
    assert frame.gross_sell_notional == Decimal("500")
    assert frame.gross_buy_notional == Decimal("500")
    assert frame.net_buy_notional == Decimal("0")
    assert frame.one_way_turnover == Decimal("0.5")
    assert frame.two_way_turnover == Decimal("1")


def test_optimization_summary_and_allocation_drift_are_retained() -> None:
    report = _analyze(_simulation(_frame(0, ("0.2",)), _frame(1, ("0.4",))))
    assert report.optimization_summary.worst_cvar == max(
        item.cvar for item in report.frames
    )
    assert report.optimization_summary.mean_expected_portfolio_return == sum(
        (item.expected_portfolio_return for item in report.frames),
        start=Decimal("0"),
    ) / Decimal("2")
    assert all(item.optimization_status.value == "OPTIMAL" for item in report.frames)
    assert tuple(item.symbol for item in report.frames[0].allocation_drifts) == (SPY,)


def test_request_validation_and_defensive_metadata_copy() -> None:
    result = _simulation(_frame(0, ("0",)))
    metadata = [MetadataEntry("source", "test")]
    request = OptimizedSimulationPerformanceRequest(
        UUID(int=2), result, metadata=metadata
    )
    metadata.clear()
    assert request.metadata == (MetadataEntry("source", "test"),)
    with pytest.raises(InvalidOptimizedSimulationPerformanceRequestError):
        OptimizedSimulationPerformanceRequest(UUID(int=2), object())  # type: ignore[arg-type]
    with pytest.raises(InvalidOptimizedSimulationPerformanceRequestError):
        OptimizedSimulationPerformanceRequest("bad", result)  # type: ignore[arg-type]
    with pytest.raises(InvalidOptimizedSimulationPerformanceRequestError):
        OptimizedSimulationPerformanceRequest(
            UUID(int=2),
            result,
            metadata=(MetadataEntry("optimized_simulation_performance_x", "x"),),
        )


def test_corrupted_policy_is_rejected() -> None:
    policy = object.__new__(OptimizedSimulationValuationPolicy)
    object.__setattr__(policy, "valuation_basis", "OTHER")
    with pytest.raises(InvalidOptimizedSimulationPerformanceRequestError):
        OptimizedSimulationValuationPolicy.__post_init__(policy)
    assert (
        OptimizedSimulationValuationPolicy().valuation_basis
        is OptimizedSimulationValuationBasis.FRAME_RISK_PRICES
    )


def test_corrupted_state_chain_and_application_are_rejected() -> None:
    result = _simulation(_frame(0, ("0.2",)), _frame(1, ("0.2",)))
    second = _unsafe_replace(result.evaluations[1], pre_ledger_state_id=UUID(int=999))
    corrupted = _unsafe_replace(result, evaluations=(result.evaluations[0], second))
    with pytest.raises(OptimizedSimulationPerformanceReconciliationError):
        _analyze(corrupted)

    result = _simulation(_frame(0, ("0.2",)))
    cycle = result.evaluations[0].cycle_result
    application = cycle.application_result.evaluations[0]
    bad_application = _unsafe_replace(
        application, ledger_cash_after=application.ledger_cash_after + Decimal("1")
    )
    bad_batch = _unsafe_replace(
        cycle.application_result, evaluations=(bad_application,)
    )
    bad_cycle = _unsafe_replace(cycle, application_result=bad_batch)
    bad_evaluation = _unsafe_replace(result.evaluations[0], cycle_result=bad_cycle)
    with pytest.raises(OptimizedSimulationPerformanceReconciliationError):
        _analyze(_unsafe_replace(result, evaluations=(bad_evaluation,)))


def test_duplicate_lifecycle_id_is_rejected() -> None:
    result = _simulation(_frame(0, ("0.2",)), _frame(1, ("0.4",)))
    first_event = result.evaluations[0].cycle_result.order_result.created_events[0]
    second_evaluation = result.evaluations[1]
    second_cycle = second_evaluation.cycle_result
    second_event = second_cycle.order_result.created_events[0]
    duplicate = _unsafe_replace(second_event, event_id=first_event.event_id)
    order_result = _unsafe_replace(
        second_cycle.order_result, created_events=(duplicate,)
    )
    cycle = _unsafe_replace(second_cycle, order_result=order_result)
    evaluation = _unsafe_replace(second_evaluation, cycle_result=cycle)
    corrupted = _unsafe_replace(result, evaluations=(result.evaluations[0], evaluation))
    with pytest.raises(OptimizedSimulationPerformanceReconciliationError):
        _analyze(corrupted)


def test_zero_equity_corruption_raises_valuation_error() -> None:
    result = _simulation(_frame(0, ("0",)))
    state = _unsafe_replace(
        result.evaluations[0].derived_state,
        cash=Decimal("0"),
        equity=Decimal("0"),
    )
    evaluation = _unsafe_replace(result.evaluations[0], derived_state=state)
    with pytest.raises(OptimizedSimulationValuationError):
        _analyze(_unsafe_replace(result, evaluations=(evaluation,)))


def test_identity_is_deterministic_and_includes_request_metadata() -> None:
    result = _simulation(_frame(0, ("0.2",)))
    first = _analyze(result)
    second = _analyze(result)
    changed = _analyze(result, metadata=(MetadataEntry("variant", "changed"),))
    assert first == second
    assert first.result_id != changed.result_id
    assert first.frames[0].frame_id == second.frames[0].frame_id


def test_result_validation_rejects_changed_deterministic_identity() -> None:
    report = _analyze(_simulation(_frame(0, ("0.2",))))
    corrupted = _unsafe_replace(report, result_id=UUID(int=999))
    with pytest.raises(InconsistentOptimizedSimulationPerformanceResultError):
        OptimizedSimulationPerformanceResult.__post_init__(corrupted)


def test_analysis_does_not_invoke_operational_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _simulation(_frame(0, ("0.2",)))

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("operational component invoked")

    monkeypatch.setattr(CpuMeanCvarOptimizer, "optimize", forbidden)
    report = _analyze(result)
    assert report.total_fill_count == 1
