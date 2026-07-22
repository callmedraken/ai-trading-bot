from dataclasses import fields
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from tests.optimization.helpers import mean_cvar_request, solver_result

from trading_bot.optimization import CpuMeanCvarOptimizer
from trading_bot.portfolio import (
    AllocationSource,
    InconsistentOptimizedTargetResultError,
    IneligibleOptimizedTargetError,
    InvalidMeanCvarOptimizationResultError,
    InvalidOptimizedTargetOutputError,
    InvalidOptimizedTargetRequestError,
    MeanCvarOptimizationResult,
    MetadataEntry,
    OptimizationStatus,
    OptimizedTargetPortfolioFactory,
    OptimizedTargetRequest,
    OptimizedTargetResult,
    OptimizedTargetStateMismatchError,
    PortfolioPositionState,
    PortfolioState,
)

REQUEST_ID = UUID(int=100)


def _optimization(
    weights: tuple[float, float, float] = (0.5, 0.25, 0.25),
) -> MeanCvarOptimizationResult:
    raw = solver_result(0, [*weights, 0, 0, 0])

    def solve(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return raw

    return CpuMeanCvarOptimizer(
        _solver=solve, _solver_identity="scipy-highs-test"
    ).optimize(mean_cvar_request())


def _request(
    result: MeanCvarOptimizationResult | None = None,
    *,
    request_id: UUID = REQUEST_ID,
    state: PortfolioState | None = None,
    metadata=(),  # noqa: ANN001, ANN202
) -> OptimizedTargetRequest:
    result = result or _optimization()
    return OptimizedTargetRequest(
        request_id,
        result,
        state or result.request.base_request.state,
        metadata,
    )


def _corrupt(item, **changes):  # noqa: ANN001, ANN003, ANN202
    copy = object.__new__(type(item))
    for field in fields(item):
        object.__setattr__(
            copy, field.name, changes.get(field.name, getattr(item, field.name))
        )
    return copy


def test_optimal_target_is_certified_without_reconstruction() -> None:
    optimization = _optimization()
    request = _request(optimization)
    result = OptimizedTargetPortfolioFactory().create(request)
    source_target = optimization.optimization_result.target
    assert source_target is not None
    assert result.target is source_target
    assert result.target.target_id == source_target.target_id
    assert result.target.allocations == source_target.allocations
    assert result.target.cash_weight == source_target.cash_weight
    assert result.target.source is AllocationSource.OPTIMIZER
    assert result.target.source_name == optimization.optimization_result.solver_name


def test_multiple_symbols_weights_cash_and_order_are_preserved_exactly() -> None:
    result = OptimizedTargetPortfolioFactory().create(_request())
    state = result.request.state
    assert result.target.symbols == state.symbols
    assert tuple(item.weight for item in result.target.allocations) == (
        Decimal("0.50000000"),
        Decimal("0.25000000"),
    )
    assert result.target.cash_weight == Decimal("0.25000000")
    assert sum(
        (item.weight for item in result.target.allocations),
        start=result.target.cash_weight,
    ) == Decimal("1")


def test_zero_weight_held_symbol_and_flat_new_entry_are_retained() -> None:
    optimization = _optimization((0, 0.75, 0.25))
    target = OptimizedTargetPortfolioFactory().create(_request(optimization)).target
    assert target.allocations[0].weight == Decimal("0")
    assert target.symbols == optimization.request.base_request.state.symbols

    base_state = optimization.request.base_request.state
    flat_state = PortfolioState(
        base_state.as_of,
        (
            base_state.positions[0],
            PortfolioPositionState(
                base_state.positions[1].symbol,
                Decimal("0"),
                Decimal("0"),
                base_state.positions[1].current_price,
            ),
        ),
        Decimal("800"),
        Decimal("1000"),
    )
    assert flat_state.positions[1].quantity == Decimal("0")


@pytest.mark.parametrize(
    "status",
    (
        OptimizationStatus.INFEASIBLE,
        OptimizationStatus.UNBOUNDED,
        OptimizationStatus.FAILED,
        OptimizationStatus.UNAVAILABLE,
    ),
)
def test_unsuccessful_optimizer_statuses_are_ineligible(status) -> None:  # noqa: ANN001
    successful = _optimization()
    portfolio_result = _corrupt(
        successful.optimization_result,
        status=status,
        target=None,
        objective_value=None,
    )
    specialized = _corrupt(
        successful,
        optimization_result=portfolio_result,
        expected_portfolio_return=None,
        cvar=None,
    )
    with pytest.raises(IneligibleOptimizedTargetError, match="OPTIMAL"):
        OptimizedTargetPortfolioFactory().create(_request(specialized))


def test_corrupted_optimal_without_target_is_ineligible() -> None:
    successful = _optimization()
    specialized = _corrupt(
        successful,
        optimization_result=_corrupt(successful.optimization_result, target=None),
    )
    with pytest.raises(IneligibleOptimizedTargetError):
        OptimizedTargetPortfolioFactory().create(_request(specialized))


def test_specialized_contract_rejects_generic_feasible_status() -> None:
    successful = _optimization()
    feasible = _corrupt(
        successful.optimization_result, status=OptimizationStatus.FEASIBLE
    )
    with pytest.raises(InvalidMeanCvarOptimizationResultError, match="FEASIBLE"):
        MeanCvarOptimizationResult(
            successful.request,
            feasible,
            successful.expected_portfolio_return,
            successful.cvar,
        )


def test_request_validation_and_metadata_defensive_copy() -> None:
    optimization = _optimization()
    values = [MetadataEntry("caller", "test")]
    request = _request(optimization, metadata=values)
    values.clear()
    assert request.metadata == (MetadataEntry("caller", "test"),)
    with pytest.raises(InvalidOptimizedTargetRequestError, match="UUID"):
        _request(optimization, request_id="bad")  # type: ignore[arg-type]
    with pytest.raises(InvalidOptimizedTargetRequestError, match="unique"):
        _request(
            optimization,
            metadata=(MetadataEntry("x", "1"), MetadataEntry("x", "2")),
        )
    with pytest.raises(InvalidOptimizedTargetRequestError, match="reserved"):
        _request(
            optimization,
            metadata=(MetadataEntry("optimized_target_internal", "x"),),
        )


@pytest.mark.parametrize("change", ("timestamp", "cash", "quantity", "cost", "price"))
def test_any_intended_state_change_is_rejected(change: str) -> None:
    optimization = _optimization()
    state = optimization.request.base_request.state
    positions = list(state.positions)
    as_of, cash, equity = state.as_of, state.cash, state.equity
    if change == "timestamp":
        as_of += timedelta(seconds=1)
    elif change == "cash":
        cash += Decimal("1")
        equity += Decimal("1")
    else:
        first = positions[0]
        quantity = first.quantity
        average_cost = first.average_cost
        price = first.current_price
        if change == "quantity":
            quantity += Decimal("1")
            equity += price
        elif change == "cost":
            average_cost += Decimal("1")
        else:
            price += Decimal("1")
            equity += first.quantity
        positions[0] = PortfolioPositionState(
            first.symbol, quantity, average_cost, price
        )
    changed = PortfolioState(as_of, tuple(positions), cash, equity)
    with pytest.raises(OptimizedTargetStateMismatchError, match="exactly equal"):
        OptimizedTargetPortfolioFactory().create(_request(optimization, state=changed))


def test_reordered_or_missing_state_universe_is_rejected() -> None:
    optimization = _optimization()
    state = optimization.request.base_request.state
    reordered = PortfolioState(
        state.as_of, tuple(reversed(state.positions)), state.cash, state.equity
    )
    with pytest.raises(OptimizedTargetStateMismatchError):
        OptimizedTargetPortfolioFactory().create(
            _request(optimization, state=reordered)
        )


@pytest.mark.parametrize(
    "corruption", ("order", "weight", "cash", "timestamp", "source")
)
def test_defensive_target_corruption_is_rejected(corruption: str) -> None:
    optimization = _optimization()
    target = optimization.optimization_result.target
    assert target is not None
    changes = {}
    if corruption == "order":
        changes["allocations"] = tuple(reversed(target.allocations))
    elif corruption == "weight":
        changes["allocations"] = (
            _corrupt(target.allocations[0], weight=Decimal("NaN")),
            target.allocations[1],
        )
    elif corruption == "cash":
        changes["cash_weight"] = Decimal("0.3")
    elif corruption == "timestamp":
        changes["as_of"] = target.as_of + timedelta(seconds=1)
    else:
        changes["source"] = AllocationSource.MANUAL
    bad_target = _corrupt(target, **changes)
    specialized = _corrupt(
        optimization,
        optimization_result=_corrupt(
            optimization.optimization_result, target=bad_target
        ),
    )
    expected = (
        OptimizedTargetStateMismatchError
        if corruption == "timestamp"
        else InvalidOptimizedTargetOutputError
    )
    with pytest.raises(expected):
        OptimizedTargetPortfolioFactory().create(_request(specialized))


def test_result_identity_is_deterministic_and_metadata_sensitive() -> None:
    optimization = _optimization()
    factory = OptimizedTargetPortfolioFactory()
    first = factory.create(_request(optimization))
    repeated = factory.create(_request(optimization))
    changed_id = factory.create(_request(optimization, request_id=UUID(int=101)))
    changed_metadata = factory.create(
        _request(optimization, metadata=(MetadataEntry("purpose", "audit"),))
    )
    assert first == repeated
    assert first.result_id != changed_id.result_id
    assert first.result_id != changed_metadata.result_id
    with pytest.raises(InconsistentOptimizedTargetResultError, match="result_id"):
        OptimizedTargetResult(UUID(int=999), first.request, first.target)


def test_factory_does_not_mutate_inputs_or_invoke_an_optimizer() -> None:
    optimization = _optimization()
    before = (optimization, optimization.optimization_result.target)
    result = OptimizedTargetPortfolioFactory().create(_request(optimization))
    assert (optimization, optimization.optimization_result.target) == before
    assert result.target is before[1]
