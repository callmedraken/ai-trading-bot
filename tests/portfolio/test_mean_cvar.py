from dataclasses import FrozenInstanceError
from decimal import Decimal
from uuid import UUID

import pytest
from tests.optimization.helpers import mean_cvar_request

from trading_bot.portfolio import (
    InvalidMeanCvarOptimizationRequestError,
    InvalidMeanCvarOptimizationResultError,
    MeanCvarOptimizationParameters,
    MeanCvarOptimizationRequest,
    MeanCvarOptimizationResult,
    OptimizationDiagnostic,
    OptimizationDiagnosticLevel,
    OptimizationStatus,
    PortfolioConstraints,
    PortfolioOptimizationResult,
)


@pytest.mark.parametrize("value", ("0", "1", "-0.1", "NaN", "Infinity"))
def test_confidence_level_is_finite_and_strictly_inside_unit_interval(
    value: str,
) -> None:
    with pytest.raises(InvalidMeanCvarOptimizationRequestError):
        MeanCvarOptimizationParameters(Decimal(value))


def test_parameter_validation_and_optional_expected_return() -> None:
    item = MeanCvarOptimizationParameters(
        Decimal("0.95"),
        Decimal("0.01"),
        Decimal("1e-7"),
        100,
        Decimal("1e-6"),
    )
    assert item.minimum_expected_return == Decimal("0.01")
    for kwargs in (
        {"solver_tolerance": Decimal("0")},
        {"output_quantum": Decimal("NaN")},
        {"maximum_iterations": True},
        {"maximum_iterations": 0},
    ):
        with pytest.raises(InvalidMeanCvarOptimizationRequestError):
            MeanCvarOptimizationParameters(Decimal("0.9"), **kwargs)


def test_request_uses_base_risk_aversion_and_is_immutable() -> None:
    request = mean_cvar_request()
    assert request.base_request.risk_aversion == Decimal("2")
    assert not hasattr(request.parameters, "risk_aversion")
    with pytest.raises(FrozenInstanceError):
        request.scenarios = request.scenarios  # type: ignore[misc]


def test_request_rejects_minimum_position_weight() -> None:
    with pytest.raises(
        InvalidMeanCvarOptimizationRequestError, match="minimum_position_weight"
    ):
        mean_cvar_request(
            constraints=PortfolioConstraints(minimum_position_weight=Decimal("0.05"))
        )


def test_specialized_result_enforces_status_invariants_and_base_request() -> None:
    request = mean_cvar_request()
    diagnostic = OptimizationDiagnostic(
        "FAILED", "failed", OptimizationDiagnosticLevel.ERROR
    )
    wrapped = PortfolioOptimizationResult(
        UUID(int=99),
        request.base_request,
        OptimizationStatus.FAILED,
        "test",
        diagnostics=(diagnostic,),
    )
    assert MeanCvarOptimizationResult(request, wrapped).cvar is None
    with pytest.raises(InvalidMeanCvarOptimizationResultError):
        MeanCvarOptimizationResult(request, wrapped, Decimal("1"), Decimal("1"))
    other = mean_cvar_request(expected=("0.11", "0.04"))
    with pytest.raises(InvalidMeanCvarOptimizationResultError, match="base request"):
        MeanCvarOptimizationResult(other, wrapped)


def test_request_requires_specialized_member_types() -> None:
    request = mean_cvar_request()
    with pytest.raises(InvalidMeanCvarOptimizationRequestError, match="base_request"):
        MeanCvarOptimizationRequest(  # type: ignore[arg-type]
            object(), request.scenarios, request.parameters
        )
