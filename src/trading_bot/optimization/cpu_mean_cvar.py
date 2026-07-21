"""Optional deterministic CPU Mean-CVaR adapter using SciPy HiGHS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, DecimalException
from importlib import import_module
from math import isfinite
from typing import Any
from uuid import UUID, uuid5

from trading_bot.optimization.exceptions import (
    CpuOptimizerUnavailableError,
    NumericalConversionError,
    PostSolveValidationError,
    SolverOutputError,
)
from trading_bot.portfolio import (
    AllocationSource,
    MeanCvarOptimizationRequest,
    MeanCvarOptimizationResult,
    OptimizationDiagnostic,
    OptimizationDiagnosticLevel,
    OptimizationStatus,
    PortfolioConstraintViolationError,
    PortfolioOptimizationResult,
    TargetAllocation,
    TargetPortfolio,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_NAMESPACE = UUID("397975fc-26af-535d-9bf5-759f16e18514")


@dataclass(frozen=True, slots=True)
class _LinearProblem:
    objective: tuple[Decimal, ...]
    a_ub: tuple[tuple[Decimal, ...], ...]
    b_ub: tuple[Decimal, ...]
    a_eq: tuple[tuple[Decimal, ...], ...]
    b_eq: tuple[Decimal, ...]
    bounds: tuple[tuple[Decimal | None, Decimal | None], ...]
    asset_count: int
    cash_index: int


class CpuMeanCvarOptimizer:
    """Solve the continuous long-only Mean-CVaR LP on a CPU."""

    def __init__(
        self,
        *,
        _solver: Callable[..., Any] | None = None,
        _solver_identity: str | None = None,
    ) -> None:
        self._solver = _solver
        self._solver_identity = _solver_identity

    def optimize(
        self, request: MeanCvarOptimizationRequest
    ) -> MeanCvarOptimizationResult:
        if not isinstance(request, MeanCvarOptimizationRequest):
            raise TypeError("request must be a MeanCvarOptimizationRequest")
        try:
            solver, identity = self._load_solver()
        except CpuOptimizerUnavailableError:
            return self._unsuccessful(
                request,
                OptimizationStatus.UNAVAILABLE,
                "scipy-highs-unavailable",
                ("SCIPY_UNAVAILABLE",),
            )

        preflight = self._zero_turnover_preflight(request, identity)
        if preflight is not None:
            return preflight
        problem = self._build_problem(request)
        options: dict[str, Any] = {
            "presolve": True,
            "disp": False,
            "primal_feasibility_tolerance": float(request.parameters.solver_tolerance),
            "dual_feasibility_tolerance": float(request.parameters.solver_tolerance),
        }
        if request.parameters.maximum_iterations is not None:
            options["maxiter"] = request.parameters.maximum_iterations
        try:
            raw = solver(
                [float(value) for value in problem.objective],
                A_ub=[[float(value) for value in row] for row in problem.a_ub] or None,
                b_ub=[float(value) for value in problem.b_ub] or None,
                A_eq=[[float(value) for value in row] for row in problem.a_eq],
                b_eq=[float(value) for value in problem.b_eq],
                bounds=[
                    (
                        None if lower is None else float(lower),
                        None if upper is None else float(upper),
                    )
                    for lower, upper in problem.bounds
                ],
                method="highs",
                options=options,
            )
        except Exception as error:  # third-party boundary
            return self._unsuccessful(
                request,
                OptimizationStatus.FAILED,
                identity,
                ("SOLVER_FAILED",),
                message=f"SciPy HiGHS raised {type(error).__name__}: {error}",
            )
        status = getattr(raw, "status", None)
        if status == 1:
            return self._unsuccessful(
                request,
                OptimizationStatus.FAILED,
                identity,
                ("SOLVER_STATUS", "SOLVER_LIMIT_REACHED"),
                message=str(getattr(raw, "message", "solver limit reached")),
            )
        if status == 2:
            return self._unsuccessful(
                request,
                OptimizationStatus.INFEASIBLE,
                identity,
                ("SOLVER_STATUS",),
                message=str(getattr(raw, "message", "problem is infeasible")),
            )
        if status == 3:
            return self._unsuccessful(
                request,
                OptimizationStatus.UNBOUNDED,
                identity,
                ("SOLVER_STATUS",),
                message=str(getattr(raw, "message", "problem is unbounded")),
            )
        if status != 0:
            return self._unsuccessful(
                request,
                OptimizationStatus.FAILED,
                identity,
                ("SOLVER_STATUS", "SOLVER_FAILED"),
                message=str(getattr(raw, "message", "solver failed")),
            )
        return self._clean_success(request, problem, raw, identity)

    def _load_solver(self) -> tuple[Callable[..., Any], str]:
        if self._solver is not None:
            return self._solver, self._solver_identity or "scipy-highs-test"
        try:
            scipy = import_module("scipy")
            optimize = import_module("scipy.optimize")
        except ImportError as error:
            raise CpuOptimizerUnavailableError("SciPy is not installed") from error
        version = str(getattr(scipy, "__version__", "unknown"))
        return optimize.linprog, f"scipy-highs-{version}"

    @staticmethod
    def _build_problem(request: MeanCvarOptimizationRequest) -> _LinearProblem:
        base = request.base_request
        scenarios = request.scenarios
        parameters = request.parameters
        n = len(base.state.positions)
        m = len(scenarios.scenarios)
        turnover = base.constraints.maximum_one_way_rebalance_turnover
        variable_count = n + 1 + 1 + m + (n + 1 if turnover is not None else 0)
        cash_index = n
        z_index = n + 1
        excess_start = n + 2
        turnover_start = excess_start + m

        objective = [_ZERO] * variable_count
        for index, expected in enumerate(base.expected_returns):
            objective[index] = -expected.value
        objective[cash_index] = -scenarios.cash_return
        objective[z_index] = base.risk_aversion
        scale = base.risk_aversion / (_ONE - parameters.confidence_level)
        for index, scenario in enumerate(scenarios.scenarios):
            objective[excess_start + index] = scale * scenario.probability

        a_eq = [[_ZERO] * variable_count]
        for index in range(n + 1):
            a_eq[0][index] = _ONE

        a_ub: list[list[Decimal]] = []
        b_ub: list[Decimal] = []
        for scenario_index, scenario in enumerate(scenarios.scenarios):
            row = [_ZERO] * variable_count
            for asset_index, value in enumerate(scenario.returns):
                row[asset_index] = -value
            row[cash_index] = -scenarios.cash_return
            row[z_index] = -_ONE
            row[excess_start + scenario_index] = -_ONE
            a_ub.append(row)
            b_ub.append(_ZERO)

        if parameters.minimum_expected_return is not None:
            row = [_ZERO] * variable_count
            for index, expected in enumerate(base.expected_returns):
                row[index] = -expected.value
            row[cash_index] = -scenarios.cash_return
            a_ub.append(row)
            b_ub.append(-parameters.minimum_expected_return)

        if turnover is not None:
            current = (*base.state.position_weights, base.state.cash_weight)
            for component, current_weight in enumerate(current):
                upper = [_ZERO] * variable_count
                upper[component] = _ONE
                upper[turnover_start + component] = -_ONE
                a_ub.append(upper)
                b_ub.append(current_weight)
                lower = [_ZERO] * variable_count
                lower[component] = -_ONE
                lower[turnover_start + component] = -_ONE
                a_ub.append(lower)
                b_ub.append(-current_weight)
            aggregate = [_ZERO] * variable_count
            for index in range(n + 1):
                aggregate[turnover_start + index] = _ONE
            a_ub.append(aggregate)
            b_ub.append(Decimal("2") * turnover)

        bounds: list[tuple[Decimal | None, Decimal | None]] = [
            (_ZERO, base.constraints.maximum_position_weight) for _ in range(n)
        ]
        bounds.append(
            (
                base.constraints.minimum_cash_weight,
                base.constraints.maximum_cash_weight,
            )
        )
        bounds.append((None, None))
        bounds.extend([(_ZERO, None)] * m)
        if turnover is not None:
            bounds.extend([(_ZERO, None)] * (n + 1))
        return _LinearProblem(
            tuple(objective),
            tuple(tuple(row) for row in a_ub),
            tuple(b_ub),
            tuple(tuple(row) for row in a_eq),
            (_ONE,),
            tuple(bounds),
            n,
            cash_index,
        )

    def _clean_success(
        self,
        request: MeanCvarOptimizationRequest,
        problem: _LinearProblem,
        raw: Any,
        identity: str,
    ) -> MeanCvarOptimizationResult:
        values = getattr(raw, "x", None)
        if values is None or len(values) < problem.asset_count + 1:
            return self._cleanup_failure(
                request, identity, "NONFINITE_SOLVER_OUTPUT", "missing solver output"
            )
        tolerance = request.parameters.solver_tolerance
        cleaned: list[Decimal] = []
        clamp_count = 0
        try:
            for index in range(problem.asset_count):
                raw_value = values[index]
                if not isfinite(float(raw_value)):
                    raise SolverOutputError("solver output is nonfinite")
                value = Decimal(str(raw_value))
                if -tolerance <= value <= _ZERO:
                    if value < _ZERO:
                        clamp_count += 1
                    value = _ZERO
                elif value < -tolerance:
                    raise NumericalConversionError("materially negative weight")
                maximum = request.base_request.constraints.maximum_position_weight
                if value > maximum + tolerance:
                    raise PostSolveValidationError("weight materially exceeds maximum")
                value = value.quantize(
                    request.parameters.output_quantum, rounding=ROUND_HALF_EVEN
                )
                cleaned.append(_ZERO if value == _ZERO else value)
        except NumericalConversionError as error:
            return self._cleanup_failure(
                request, identity, "MATERIAL_NEGATIVE_WEIGHT", str(error)
            )
        except PostSolveValidationError as error:
            return self._cleanup_failure(
                request,
                identity,
                "POST_CLEANUP_PORTFOLIO_CONSTRAINT_VIOLATION",
                str(error),
            )
        except (ValueError, TypeError, DecimalException, SolverOutputError) as error:
            return self._cleanup_failure(
                request, identity, "NONFINITE_SOLVER_OUTPUT", str(error)
            )

        cash = _ONE - sum(cleaned, start=_ZERO)
        constraints = request.base_request.constraints
        if cash < _ZERO or not (
            constraints.minimum_cash_weight <= cash <= constraints.maximum_cash_weight
        ):
            return self._cleanup_failure(
                request, identity, "INVALID_CASH_RESIDUAL", "invalid cash residual"
            )
        diagnostics_codes = ["SOLVER_STATUS"]
        if clamp_count:
            diagnostics_codes.append("CLEANUP_CLAMP_COUNT")
        request_fingerprint = self._request_fingerprint(request)
        weights_identity = ",".join(self._decimal_identity(item) for item in cleaned)
        target_id = uuid5(
            _NAMESPACE,
            f"target|{request_fingerprint}|{identity}|{weights_identity}|"
            f"{self._decimal_identity(cash)}",
        )
        try:
            target = TargetPortfolio(
                target_id,
                request.base_request.as_of,
                tuple(
                    TargetAllocation(position.symbol, weight)
                    for position, weight in zip(
                        request.base_request.state.positions, cleaned, strict=True
                    )
                ),
                cash,
                AllocationSource.OPTIMIZER,
                identity,
            )
            constraints.validate_target(request.base_request.state, target)
        except (ValueError, PortfolioConstraintViolationError) as error:
            return self._cleanup_failure(
                request,
                identity,
                "POST_CLEANUP_PORTFOLIO_CONSTRAINT_VIOLATION",
                str(error),
            )
        expected = self._expected_return(request, target)
        minimum = request.parameters.minimum_expected_return
        if minimum is not None and expected < minimum:
            return self._cleanup_failure(
                request,
                identity,
                "POST_CLEANUP_EXPECTED_RETURN_VIOLATION",
                "cleaned expected return is below the configured minimum",
            )
        cvar = self._exact_cvar(request, target)
        objective = request.base_request.risk_aversion * cvar - expected
        diagnostics_codes.extend(("OBJECTIVE_VALUE", "MAX_CONSTRAINT_VIOLATION"))
        diagnostics = self._diagnostics(
            diagnostics_codes,
            "optimization completed successfully",
            objective=objective,
            clamp_count=clamp_count,
        )
        result_id = self._result_id(
            request,
            OptimizationStatus.OPTIMAL,
            diagnostics_codes,
            target_id=target_id,
            expected=expected,
            cvar=cvar,
            objective=objective,
        )
        wrapped = PortfolioOptimizationResult(
            result_id,
            request.base_request,
            OptimizationStatus.OPTIMAL,
            identity,
            target,
            objective,
            diagnostics,
        )
        return MeanCvarOptimizationResult(request, wrapped, expected, cvar)

    @staticmethod
    def _expected_return(
        request: MeanCvarOptimizationRequest, target: TargetPortfolio
    ) -> Decimal:
        return (
            sum(
                (
                    allocation.weight * expected.value
                    for allocation, expected in zip(
                        target.allocations,
                        request.base_request.expected_returns,
                        strict=True,
                    )
                ),
                start=_ZERO,
            )
            + target.cash_weight * request.scenarios.cash_return
        )

    @staticmethod
    def _exact_cvar(
        request: MeanCvarOptimizationRequest, target: TargetPortfolio
    ) -> Decimal:
        losses = tuple(
            -(
                sum(
                    (
                        allocation.weight * value
                        for allocation, value in zip(
                            target.allocations, scenario.returns, strict=True
                        )
                    ),
                    start=_ZERO,
                )
                + target.cash_weight * request.scenarios.cash_return
            )
            for scenario in request.scenarios.scenarios
        )
        scale = _ONE / (_ONE - request.parameters.confidence_level)
        candidates = []
        for z in sorted(set(losses)):
            excess = sum(
                (
                    scenario.probability * max(loss - z, _ZERO)
                    for scenario, loss in zip(
                        request.scenarios.scenarios, losses, strict=True
                    )
                ),
                start=_ZERO,
            )
            candidates.append((z + scale * excess, z))
        return min(candidates, key=lambda item: (item[0], item[1]))[0]

    def _zero_turnover_preflight(
        self, request: MeanCvarOptimizationRequest, identity: str
    ) -> MeanCvarOptimizationResult | None:
        constraints = request.base_request.constraints
        if constraints.maximum_one_way_rebalance_turnover != _ZERO:
            return None
        state = request.base_request.state
        if not (
            constraints.minimum_cash_weight
            <= state.cash_weight
            <= constraints.maximum_cash_weight
        ) or any(
            weight > constraints.maximum_position_weight
            for weight in state.position_weights
        ):
            return self._unsuccessful(
                request,
                OptimizationStatus.INFEASIBLE,
                identity,
                ("SOLVER_STATUS",),
                message="unchanged allocation violates supported constraints",
            )
        expected = (
            sum(
                (
                    weight * forecast.value
                    for weight, forecast in zip(
                        state.position_weights,
                        request.base_request.expected_returns,
                        strict=True,
                    )
                ),
                start=_ZERO,
            )
            + state.cash_weight * request.scenarios.cash_return
        )
        minimum = request.parameters.minimum_expected_return
        if minimum is not None and expected < minimum:
            return self._unsuccessful(
                request,
                OptimizationStatus.INFEASIBLE,
                identity,
                ("SOLVER_STATUS",),
                message="unchanged allocation violates minimum expected return",
            )
        return None

    def _cleanup_failure(
        self,
        request: MeanCvarOptimizationRequest,
        identity: str,
        code: str,
        message: str,
    ) -> MeanCvarOptimizationResult:
        return self._unsuccessful(
            request, OptimizationStatus.FAILED, identity, (code,), message=message
        )

    def _unsuccessful(
        self,
        request: MeanCvarOptimizationRequest,
        status: OptimizationStatus,
        solver_name: str,
        codes: tuple[str, ...],
        *,
        message: str | None = None,
    ) -> MeanCvarOptimizationResult:
        diagnostics = self._diagnostics(codes, message or codes[0])
        result_id = self._result_id(request, status, codes)
        wrapped = PortfolioOptimizationResult(
            result_id,
            request.base_request,
            status,
            solver_name,
            diagnostics=diagnostics,
        )
        return MeanCvarOptimizationResult(request, wrapped)

    @staticmethod
    def _diagnostics(
        codes: list[str] | tuple[str, ...],
        message: str,
        *,
        objective: Decimal | None = None,
        clamp_count: int = 0,
    ) -> tuple[OptimizationDiagnostic, ...]:
        values = {
            "OBJECTIVE_VALUE": objective,
            "MAX_CONSTRAINT_VIOLATION": _ZERO,
            "CLEANUP_CLAMP_COUNT": Decimal(clamp_count),
        }
        return tuple(
            OptimizationDiagnostic(
                code,
                message if index == 0 else code.replace("_", " ").lower(),
                OptimizationDiagnosticLevel.INFO
                if code in {"OBJECTIVE_VALUE", "MAX_CONSTRAINT_VIOLATION"}
                else OptimizationDiagnosticLevel.WARNING,
                values.get(code),
            )
            for index, code in enumerate(codes)
        )

    def _request_fingerprint(self, request: MeanCvarOptimizationRequest) -> str:
        base = request.base_request
        parts = [
            str(base.request_id),
            base.as_of.isoformat(),
            str(base.forecast_horizon.periods),
            base.forecast_horizon.timeframe.value,
            str(request.scenarios.scenario_set_id),
            self._decimal_identity(base.risk_aversion),
            self._decimal_identity(request.parameters.confidence_level),
            "none"
            if request.parameters.minimum_expected_return is None
            else self._decimal_identity(request.parameters.minimum_expected_return),
            self._decimal_identity(request.parameters.solver_tolerance),
            str(request.parameters.maximum_iterations),
            self._decimal_identity(request.parameters.output_quantum),
            self._decimal_identity(base.constraints.minimum_cash_weight),
            self._decimal_identity(base.constraints.maximum_cash_weight),
            self._decimal_identity(base.constraints.maximum_position_weight),
            "none"
            if base.constraints.maximum_one_way_rebalance_turnover is None
            else self._decimal_identity(
                base.constraints.maximum_one_way_rebalance_turnover
            ),
            str(base.constraints.long_only),
            str(base.constraints.allow_leverage),
            self._decimal_identity(base.state.cash),
            self._decimal_identity(base.state.equity),
        ]
        for position in base.state.positions:
            parts.extend(
                (
                    str(position.symbol),
                    self._decimal_identity(position.quantity),
                    self._decimal_identity(position.average_cost),
                    self._decimal_identity(position.current_price),
                )
            )
        parts.extend(
            self._decimal_identity(item.value) for item in base.expected_returns
        )
        for scenario in request.scenarios.scenarios:
            parts.append(str(scenario.scenario_id))
            parts.append(self._decimal_identity(scenario.probability))
            parts.extend(self._decimal_identity(value) for value in scenario.returns)
        parts.append(self._decimal_identity(request.scenarios.cash_return))
        return "|".join(parts)

    def _result_id(
        self,
        request: MeanCvarOptimizationRequest,
        status: OptimizationStatus,
        codes: list[str] | tuple[str, ...],
        *,
        target_id: UUID | None = None,
        expected: Decimal | None = None,
        cvar: Decimal | None = None,
        objective: Decimal | None = None,
    ) -> UUID:
        values = [
            "result",
            self._request_fingerprint(request),
            status.value,
            "none" if target_id is None else str(target_id),
            "none" if expected is None else self._decimal_identity(expected),
            "none" if cvar is None else self._decimal_identity(cvar),
            "none" if objective is None else self._decimal_identity(objective),
            ",".join(codes),
        ]
        return uuid5(_NAMESPACE, "|".join(values))

    @staticmethod
    def _decimal_identity(value: Decimal) -> str:
        normalized = _ZERO if value == _ZERO else value.normalize()
        return str(normalized)
