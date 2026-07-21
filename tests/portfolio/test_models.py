from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_data import Timeframe
from trading_bot.portfolio import (
    AllocationSource,
    ExpectedReturn,
    ForecastHorizon,
    InvalidOptimizationRequestError,
    InvalidOptimizationResultError,
    InvalidPortfolioConstraintsError,
    InvalidPortfolioStateError,
    InvalidTargetPortfolioError,
    MetadataEntry,
    OptimizationDiagnostic,
    OptimizationDiagnosticLevel,
    OptimizationStatus,
    PortfolioConstraints,
    PortfolioConstraintViolationError,
    PortfolioOptimizationRequest,
    PortfolioOptimizationResult,
    PortfolioPositionState,
    PortfolioState,
    PortfolioUniverseMismatchError,
    TargetAllocation,
    TargetPortfolio,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def state() -> PortfolioState:
    return PortfolioState(
        NOW,
        (
            PortfolioPositionState(SPY, Decimal("2.5"), Decimal("80"), Decimal("100")),
            PortfolioPositionState(QQQ, Decimal("0"), Decimal("0"), Decimal("50")),
        ),
        Decimal("750"),
        Decimal("1000"),
    )


def target(
    spy: str = "0.4",
    qqq: str = "0.3",
    cash: str = "0.3",
    *,
    as_of: datetime = NOW,
    source: AllocationSource = AllocationSource.MANUAL,
    source_name: str | None = None,
) -> TargetPortfolio:
    return TargetPortfolio(
        UUID(int=2),
        as_of,
        (
            TargetAllocation(SPY, Decimal(spy)),
            TargetAllocation(QQQ, Decimal(qqq)),
        ),
        Decimal(cash),
        source,
        source_name,
    )


def request(
    *, constraints: PortfolioConstraints | None = None
) -> PortfolioOptimizationRequest:
    return PortfolioOptimizationRequest(
        UUID(int=1),
        state(),
        constraints or PortfolioConstraints(),
        (ExpectedReturn(SPY, Decimal("0.03")), ExpectedReturn(QQQ, Decimal("-0.01"))),
        ForecastHorizon(5, Timeframe.DAY_1),
        Decimal("2"),
        (MetadataEntry("forecast", "fixture"),),
    )


def test_portfolio_state_derives_market_values_and_weights_exactly() -> None:
    item = state()
    assert item.symbols == (SPY, QQQ)
    assert tuple(position.market_value for position in item.positions) == (
        Decimal("250.0"),
        Decimal("0"),
    )
    assert item.position_weights == (Decimal("0.25"), Decimal("0"))
    assert item.cash_weight == Decimal("0.75")
    with pytest.raises(FrozenInstanceError):
        item.cash = Decimal("1")  # type: ignore[misc]


def test_cash_only_state_preserves_ordered_flat_symbols_and_negative_zero() -> None:
    item = PortfolioState(
        NOW,
        (
            PortfolioPositionState(SPY, Decimal("-0"), Decimal("-0"), Decimal("1")),
            PortfolioPositionState(QQQ, Decimal("0"), Decimal("0"), Decimal("1")),
        ),
        Decimal("100"),
        Decimal("100"),
    )
    assert item.positions[0].quantity == Decimal("0")
    assert not item.positions[0].quantity.is_signed()
    assert item.position_weights == (Decimal("0"), Decimal("0"))
    assert item.cash_weight == Decimal("1")


@pytest.mark.parametrize(
    ("quantity", "average_cost", "price", "message"),
    (
        ("-1", "1", "1", "quantity"),
        ("0", "1", "1", "flat"),
        ("1", "0", "1", "open"),
        ("0", "0", "0", "current_price"),
        ("0", "0", "NaN", "finite"),
    ),
)
def test_position_state_rejects_invalid_values(
    quantity: str, average_cost: str, price: str, message: str
) -> None:
    with pytest.raises(InvalidPortfolioStateError, match=message):
        PortfolioPositionState(
            SPY, Decimal(quantity), Decimal(average_cost), Decimal(price)
        )


def test_state_rejects_empty_duplicates_bad_equity_and_naive_time() -> None:
    with pytest.raises(InvalidPortfolioStateError, match="empty"):
        PortfolioState(NOW, (), Decimal("1"), Decimal("1"))
    position = PortfolioPositionState(SPY, Decimal("0"), Decimal("0"), Decimal("1"))
    with pytest.raises(InvalidPortfolioStateError, match="unique"):
        PortfolioState(NOW, (position, position), Decimal("1"), Decimal("1"))
    with pytest.raises(InvalidPortfolioStateError, match="equity"):
        PortfolioState(NOW, (position,), Decimal("1"), Decimal("2"))
    with pytest.raises(InvalidPortfolioStateError, match="aware"):
        PortfolioState(
            NOW.replace(tzinfo=None), (position,), Decimal("1"), Decimal("1")
        )


def test_target_requires_exact_weight_sum_and_preserves_zero_allocations() -> None:
    item = target("0.7", "0", "0.3")
    assert item.symbols == (SPY, QQQ)
    assert item.allocations[1].weight == Decimal("0")
    with pytest.raises(InvalidTargetPortfolioError, match="exactly one"):
        target("0.7", "0", "0.299999")


def test_target_validates_duplicates_provenance_metadata_and_timestamp() -> None:
    with pytest.raises(InvalidTargetPortfolioError, match="unique"):
        TargetPortfolio(
            UUID(int=2),
            NOW,
            (TargetAllocation(SPY, Decimal("0.5")),) * 2,
            Decimal("0"),
            AllocationSource.MANUAL,
        )
    with pytest.raises(InvalidTargetPortfolioError, match="source_name"):
        target(source=AllocationSource.OPTIMIZER)
    with pytest.raises(InvalidTargetPortfolioError, match="source_name"):
        target(source_name=" ")
    with pytest.raises(InvalidTargetPortfolioError, match="unique"):
        TargetPortfolio(
            UUID(int=2),
            NOW,
            (TargetAllocation(SPY, Decimal("1")),),
            Decimal("0"),
            AllocationSource.MANUAL,
            metadata=(MetadataEntry("a", "1"), MetadataEntry("a", "2")),
        )
    with pytest.raises(InvalidTargetPortfolioError, match="aware"):
        target(as_of=NOW.replace(tzinfo=None))


def test_turnover_uses_full_vector_and_does_not_require_equal_timestamps() -> None:
    item = target(as_of=NOW + timedelta(days=1))
    current = state()
    assert item.total_weight_change(current) == Decimal("0.90")
    assert item.one_way_rebalance_turnover(current) == Decimal("0.45")
    reversed_target = TargetPortfolio(
        UUID(int=2),
        NOW,
        tuple(reversed(item.allocations)),
        item.cash_weight,
        AllocationSource.MANUAL,
    )
    with pytest.raises(PortfolioUniverseMismatchError):
        reversed_target.total_weight_change(current)


def test_constraints_validate_model_and_target_separately() -> None:
    with pytest.raises(InvalidPortfolioConstraintsError, match="cannot exceed"):
        PortfolioConstraints(Decimal("0.6"), Decimal("0.5"))
    with pytest.raises(InvalidPortfolioConstraintsError, match="long_only"):
        PortfolioConstraints(long_only=False)
    with pytest.raises(InvalidPortfolioConstraintsError, match="allow_leverage"):
        PortfolioConstraints(allow_leverage=True)

    constraints = PortfolioConstraints(
        minimum_cash_weight=Decimal("0.2"),
        maximum_cash_weight=Decimal("0.4"),
        maximum_position_weight=Decimal("0.6"),
        maximum_one_way_rebalance_turnover=Decimal("0.5"),
        minimum_position_weight=Decimal("0.1"),
    )
    constraints.validate_target(state(), target())
    with pytest.raises(PortfolioConstraintViolationError, match="cash"):
        constraints.validate_target(state(), target("0.7", "0.2", "0.1"))
    with pytest.raises(PortfolioConstraintViolationError, match="exceeds maximum"):
        constraints.validate_target(state(), target("0.7", "0", "0.3"))
    with pytest.raises(PortfolioConstraintViolationError, match="below minimum"):
        constraints.validate_target(state(), target("0.55", "0.05", "0.4"))


def test_zero_weight_is_exempt_from_minimum_and_turnover_boundary_is_exact() -> None:
    item = target("0.25", "0", "0.75")
    constraints = PortfolioConstraints(
        minimum_position_weight=Decimal("0.2"),
        maximum_one_way_rebalance_turnover=Decimal("0"),
    )
    constraints.validate_target(state(), item)
    with pytest.raises(PortfolioConstraintViolationError, match="turnover"):
        PortfolioConstraints(
            maximum_one_way_rebalance_turnover=Decimal("0.449")
        ).validate_target(state(), target())


def test_forecast_horizon_and_expected_returns_are_explicit_and_ordered() -> None:
    item = request()
    assert item.forecast_horizon == ForecastHorizon(5, Timeframe.DAY_1)
    assert tuple(value.symbol for value in item.expected_returns) == (SPY, QQQ)
    assert item.expected_returns[1].value == Decimal("-0.01")
    with pytest.raises(InvalidOptimizationRequestError, match="positive"):
        ForecastHorizon(0, Timeframe.DAY_1)
    with pytest.raises(InvalidOptimizationRequestError, match="risk_aversion"):
        PortfolioOptimizationRequest(
            UUID(int=1),
            state(),
            PortfolioConstraints(),
            (ExpectedReturn(SPY, Decimal("0")), ExpectedReturn(QQQ, Decimal("0"))),
            ForecastHorizon(1, Timeframe.DAY_1),
            Decimal("Infinity"),
        )


def test_request_rejects_expected_return_order_mismatch() -> None:
    with pytest.raises(InvalidOptimizationRequestError, match="universe order"):
        PortfolioOptimizationRequest(
            UUID(int=1),
            state(),
            PortfolioConstraints(),
            (ExpectedReturn(QQQ, Decimal("0")), ExpectedReturn(SPY, Decimal("0"))),
            ForecastHorizon(1, Timeframe.DAY_1),
            Decimal("0"),
        )


def test_successful_result_validates_provenance_time_and_constraints() -> None:
    optimization_request = request()
    optimized = target(
        source=AllocationSource.OPTIMIZER,
        source_name="cpu-reference",
    )
    result = PortfolioOptimizationResult(
        UUID(int=1),
        optimization_request,
        OptimizationStatus.OPTIMAL,
        "cpu-reference",
        optimized,
    )
    assert result.objective_value is None
    assert result.request_id == optimization_request.request_id
    with pytest.raises(InvalidOptimizationResultError, match="as_of"):
        PortfolioOptimizationResult(
            UUID(int=3),
            optimization_request,
            OptimizationStatus.FEASIBLE,
            "cpu-reference",
            target(
                as_of=NOW + timedelta(days=1),
                source=AllocationSource.OPTIMIZER,
                source_name="cpu-reference",
            ),
        )
    with pytest.raises(InvalidOptimizationResultError, match="source_name"):
        PortfolioOptimizationResult(
            UUID(int=3),
            optimization_request,
            OptimizationStatus.FEASIBLE,
            "other-solver",
            optimized,
        )


def test_unsuccessful_result_requires_diagnostic_and_prohibits_outputs() -> None:
    diagnostic = OptimizationDiagnostic(
        "NO_SOLVER", "solver is unavailable", OptimizationDiagnosticLevel.ERROR
    )
    result = PortfolioOptimizationResult(
        UUID(int=1),
        request(),
        OptimizationStatus.UNAVAILABLE,
        "cpu-reference",
        diagnostics=(diagnostic,),
    )
    assert result.diagnostics == (diagnostic,)
    with pytest.raises(InvalidOptimizationResultError, match="diagnostic"):
        PortfolioOptimizationResult(
            UUID(int=3), request(), OptimizationStatus.FAILED, "cpu-reference"
        )
    with pytest.raises(InvalidOptimizationResultError, match="prohibit"):
        PortfolioOptimizationResult(
            UUID(int=3),
            request(),
            OptimizationStatus.INFEASIBLE,
            "cpu-reference",
            objective_value=Decimal("0"),
            diagnostics=(diagnostic,),
        )


def test_models_require_caller_supplied_uuid_values_but_allow_equal_ids() -> None:
    optimized = target(
        source=AllocationSource.OPTIMIZER,
        source_name="cpu-reference",
    )
    result = PortfolioOptimizationResult(
        UUID(int=1),
        request(),
        OptimizationStatus.FEASIBLE,
        "cpu-reference",
        optimized,
        Decimal("0"),
    )
    assert result.result_id == result.request_id
    with pytest.raises(InvalidTargetPortfolioError, match="UUID"):
        TargetPortfolio(  # type: ignore[arg-type]
            "bad",
            NOW,
            (TargetAllocation(SPY, Decimal("1")),),
            Decimal("0"),
            AllocationSource.MANUAL,
        )
