"""Solver-independent immutable Mean-CVaR optimization contracts."""

from dataclasses import dataclass
from decimal import Decimal

from trading_bot.portfolio.exceptions import (
    InvalidMeanCvarOptimizationRequestError,
    InvalidMeanCvarOptimizationResultError,
)
from trading_bot.portfolio.models import (
    OptimizationStatus,
    PortfolioOptimizationRequest,
    PortfolioOptimizationResult,
)
from trading_bot.portfolio.scenarios import ReturnScenarioSet

_ZERO = Decimal("0")
_ONE = Decimal("1")


def _finite_decimal(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise InvalidMeanCvarOptimizationRequestError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise InvalidMeanCvarOptimizationRequestError(f"{name} must be finite")
    return _ZERO if value == _ZERO else value


@dataclass(frozen=True, slots=True)
class MeanCvarOptimizationParameters:
    """Numerical and objective parameters for one Mean-CVaR solve."""

    confidence_level: Decimal
    minimum_expected_return: Decimal | None = None
    solver_tolerance: Decimal = Decimal("0.00000001")
    maximum_iterations: int | None = None
    output_quantum: Decimal = Decimal("0.00000001")

    def __post_init__(self) -> None:
        confidence = _finite_decimal(self.confidence_level, "confidence_level")
        if not _ZERO < confidence < _ONE:
            raise InvalidMeanCvarOptimizationRequestError(
                "confidence_level must be strictly between zero and one"
            )
        minimum = self.minimum_expected_return
        if minimum is not None:
            minimum = _finite_decimal(minimum, "minimum_expected_return")
        tolerance = _finite_decimal(self.solver_tolerance, "solver_tolerance")
        if tolerance <= _ZERO:
            raise InvalidMeanCvarOptimizationRequestError(
                "solver_tolerance must be positive"
            )
        iterations = self.maximum_iterations
        if iterations is not None and (
            not isinstance(iterations, int)
            or isinstance(iterations, bool)
            or iterations <= 0
        ):
            raise InvalidMeanCvarOptimizationRequestError(
                "maximum_iterations must be a positive non-boolean integer"
            )
        quantum = _finite_decimal(self.output_quantum, "output_quantum")
        if quantum <= _ZERO:
            raise InvalidMeanCvarOptimizationRequestError(
                "output_quantum must be positive"
            )
        object.__setattr__(self, "confidence_level", confidence)
        object.__setattr__(self, "minimum_expected_return", minimum)
        object.__setattr__(self, "solver_tolerance", tolerance)
        object.__setattr__(self, "output_quantum", quantum)


@dataclass(frozen=True, slots=True)
class MeanCvarOptimizationRequest:
    """A compatible forecast, scenario distribution, and Mean-CVaR policy."""

    base_request: PortfolioOptimizationRequest
    scenarios: ReturnScenarioSet
    parameters: MeanCvarOptimizationParameters

    def __post_init__(self) -> None:
        if not isinstance(self.base_request, PortfolioOptimizationRequest):
            raise InvalidMeanCvarOptimizationRequestError(
                "base_request must be a PortfolioOptimizationRequest"
            )
        if not isinstance(self.scenarios, ReturnScenarioSet):
            raise InvalidMeanCvarOptimizationRequestError(
                "scenarios must be a ReturnScenarioSet"
            )
        if not isinstance(self.parameters, MeanCvarOptimizationParameters):
            raise InvalidMeanCvarOptimizationRequestError(
                "parameters must be MeanCvarOptimizationParameters"
            )
        self.scenarios.validate_compatibility(
            as_of=self.base_request.as_of,
            forecast_horizon=self.base_request.forecast_horizon,
            symbols=self.base_request.state.symbols,
        )
        constraints = self.base_request.constraints
        if constraints.long_only is not True or constraints.allow_leverage is not False:
            raise InvalidMeanCvarOptimizationRequestError(
                "Mean-CVaR requires long-only allocations without leverage"
            )
        if constraints.minimum_position_weight is not None:
            raise InvalidMeanCvarOptimizationRequestError(
                "minimum_position_weight is unsupported by the continuous LP"
            )


@dataclass(frozen=True, slots=True)
class MeanCvarOptimizationResult:
    """Specialized result retaining scenario inputs and exact risk measures."""

    request: MeanCvarOptimizationRequest
    optimization_result: PortfolioOptimizationResult
    expected_portfolio_return: Decimal | None = None
    cvar: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, MeanCvarOptimizationRequest):
            raise InvalidMeanCvarOptimizationResultError(
                "request must be a MeanCvarOptimizationRequest"
            )
        if not isinstance(self.optimization_result, PortfolioOptimizationResult):
            raise InvalidMeanCvarOptimizationResultError(
                "optimization_result must be a PortfolioOptimizationResult"
            )
        if self.optimization_result.request != self.request.base_request:
            raise InvalidMeanCvarOptimizationResultError(
                "wrapped result must refer to the specialized base request"
            )
        successful = self.optimization_result.status is OptimizationStatus.OPTIMAL
        if successful:
            if self.optimization_result.target is None:
                raise InvalidMeanCvarOptimizationResultError(
                    "OPTIMAL results require a target"
                )
            for name in ("expected_portfolio_return", "cvar"):
                value = getattr(self, name)
                if not isinstance(value, Decimal) or not value.is_finite():
                    raise InvalidMeanCvarOptimizationResultError(
                        f"OPTIMAL results require finite {name}"
                    )
        elif self.optimization_result.status in {
            OptimizationStatus.INFEASIBLE,
            OptimizationStatus.UNBOUNDED,
            OptimizationStatus.FAILED,
            OptimizationStatus.UNAVAILABLE,
        }:
            if self.optimization_result.target is not None:
                raise InvalidMeanCvarOptimizationResultError(
                    "unsuccessful results must not contain a target"
                )
            if self.expected_portfolio_return is not None or self.cvar is not None:
                raise InvalidMeanCvarOptimizationResultError(
                    "unsuccessful results must not contain risk measures"
                )
        else:
            raise InvalidMeanCvarOptimizationResultError(
                "FEASIBLE is unsupported for Mean-CVaR results"
            )
