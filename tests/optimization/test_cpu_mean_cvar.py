from decimal import Decimal
from importlib.util import find_spec

import pytest
from tests.optimization.helpers import fake_solver, mean_cvar_request, solver_result

from trading_bot.optimization import CpuMeanCvarOptimizer
from trading_bot.portfolio import (
    MeanCvarOptimizationParameters,
    OptimizationStatus,
    PortfolioConstraints,
)


def optimizer(result) -> CpuMeanCvarOptimizer:  # noqa: ANN001
    return CpuMeanCvarOptimizer(
        _solver=fake_solver(result), _solver_identity="scipy-highs-test"
    )


def test_matrix_has_exact_variable_row_order_and_scenario_signs() -> None:
    request = mean_cvar_request(
        constraints=PortfolioConstraints(
            maximum_one_way_rebalance_turnover=Decimal("0.2")
        ),
        parameters=MeanCvarOptimizationParameters(
            Decimal("0.75"), minimum_expected_return=Decimal("0.03")
        ),
    )
    problem = CpuMeanCvarOptimizer._build_problem(request)
    assert len(problem.objective) == 2 + 1 + 1 + 2 + 3
    assert problem.a_eq[0][:3] == (Decimal("1"),) * 3
    assert problem.a_ub[0][:6] == (
        Decimal("-0.10"),
        Decimal("-0.02"),
        Decimal("-0.01"),
        Decimal("-1"),
        Decimal("-1"),
        Decimal("0"),
    )
    # scenarios, expected-return floor, two rows per asset/cash, aggregate
    assert len(problem.a_ub) == 2 + 1 + 6 + 1
    assert problem.b_ub[-1] == Decimal("0.4")


def test_success_cleanup_recomputes_exact_reward_cvar_and_objective() -> None:
    # asset weights, cash, z, two excess variables
    result = optimizer(solver_result(0, [0.5, 0.25, 0.25, 0, 0, 0])).optimize(
        mean_cvar_request()
    )
    assert result.optimization_result.status is OptimizationStatus.OPTIMAL
    assert result.optimization_result.target is not None
    assert tuple(a.weight for a in result.optimization_result.target.allocations) == (
        Decimal("0.50000000"),
        Decimal("0.25000000"),
    )
    assert result.optimization_result.target.cash_weight == Decimal("0.25000000")
    assert result.expected_portfolio_return == Decimal("0.0625000000")
    assert result.cvar == Decimal("0.0950000000")
    assert result.optimization_result.objective_value == Decimal("0.1275000000")


def test_small_negative_is_clamped_and_material_negative_fails() -> None:
    request = mean_cvar_request()
    clamped = optimizer(solver_result(0, [-1e-9, 0.5, 0.5, 0, 0, 0])).optimize(request)
    assert clamped.optimization_result.status is OptimizationStatus.OPTIMAL
    assert "CLEANUP_CLAMP_COUNT" in {
        item.code for item in clamped.optimization_result.diagnostics
    }
    failed = optimizer(solver_result(0, [-0.01, 0.5, 0.51, 0, 0, 0])).optimize(request)
    assert failed.optimization_result.status is OptimizationStatus.FAILED
    assert failed.optimization_result.diagnostics[0].code == "MATERIAL_NEGATIVE_WEIGHT"


def test_invalid_residual_and_post_cleanup_expected_return_fail() -> None:
    request = mean_cvar_request()
    invalid = optimizer(solver_result(0, [0.8, 0.8, 0, 0, 0, 0])).optimize(request)
    assert invalid.optimization_result.diagnostics[0].code == "INVALID_CASH_RESIDUAL"
    floor = mean_cvar_request(
        parameters=MeanCvarOptimizationParameters(
            Decimal("0.75"), minimum_expected_return=Decimal("0.09")
        )
    )
    below = optimizer(solver_result(0, [0, 0, 1, 0, 0, 0])).optimize(floor)
    assert below.optimization_result.diagnostics[0].code == (
        "POST_CLEANUP_EXPECTED_RETURN_VIOLATION"
    )


@pytest.mark.parametrize(
    ("solver_status", "expected", "code"),
    (
        (1, OptimizationStatus.FAILED, "SOLVER_LIMIT_REACHED"),
        (2, OptimizationStatus.INFEASIBLE, "SOLVER_STATUS"),
        (3, OptimizationStatus.UNBOUNDED, "SOLVER_STATUS"),
        (4, OptimizationStatus.FAILED, "SOLVER_FAILED"),
        (99, OptimizationStatus.FAILED, "SOLVER_FAILED"),
    ),
)
def test_solver_status_mapping(
    solver_status: int, expected: OptimizationStatus, code: str
) -> None:
    result = optimizer(solver_result(solver_status)).optimize(mean_cvar_request())
    assert result.optimization_result.status is expected
    assert code in {item.code for item in result.optimization_result.diagnostics}
    assert result.expected_portfolio_return is None
    assert result.cvar is None


def test_missing_and_nonfinite_solver_outputs_fail_closed() -> None:
    missing = optimizer(solver_result(0)).optimize(mean_cvar_request())
    assert missing.optimization_result.diagnostics[0].code == "NONFINITE_SOLVER_OUTPUT"
    nonfinite = optimizer(solver_result(0, [float("nan"), 0, 1, 0, 0, 0])).optimize(
        mean_cvar_request()
    )
    assert nonfinite.optimization_result.diagnostics[0].code == (
        "NONFINITE_SOLVER_OUTPUT"
    )


def test_output_changes_ids_and_equal_output_repeats_ids() -> None:
    request = mean_cvar_request()
    first = optimizer(solver_result(0, [0.5, 0.25, 0.25, 0, 0, 0])).optimize(request)
    repeated = optimizer(solver_result(0, [0.5, 0.25, 0.25, 12, 9, 8])).optimize(
        request
    )
    changed = optimizer(solver_result(0, [0.4, 0.3, 0.3, 0, 0, 0])).optimize(request)
    assert first.optimization_result.result_id == repeated.optimization_result.result_id
    assert first.optimization_result.target == repeated.optimization_result.target
    assert first.optimization_result.result_id != changed.optimization_result.result_id


def test_zero_turnover_obvious_infeasibility_avoids_solver() -> None:
    request = mean_cvar_request(
        constraints=PortfolioConstraints(
            maximum_position_weight=Decimal("0.1"),
            maximum_one_way_rebalance_turnover=Decimal("0"),
        )
    )

    def must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("solver should not run")

    result = CpuMeanCvarOptimizer(
        _solver=must_not_run, _solver_identity="scipy-highs-test"
    ).optimize(request)
    assert result.optimization_result.status is OptimizationStatus.INFEASIBLE


def test_optional_real_scipy_or_explicit_unavailable_behavior() -> None:
    result = CpuMeanCvarOptimizer().optimize(mean_cvar_request())
    if result.optimization_result.status is OptimizationStatus.UNAVAILABLE:
        assert result.optimization_result.solver_name == "scipy-highs-unavailable"
        assert result.optimization_result.diagnostics[0].code == "SCIPY_UNAVAILABLE"
    else:
        assert result.optimization_result.status is OptimizationStatus.OPTIMAL


@pytest.mark.skipif(find_spec("scipy") is None, reason="optional SciPy is absent")
def test_real_scipy_representative_solve_repeats_and_reconciles() -> None:
    request = mean_cvar_request()
    first = CpuMeanCvarOptimizer().optimize(request)
    second = CpuMeanCvarOptimizer().optimize(request)
    assert first.optimization_result.status is OptimizationStatus.OPTIMAL
    assert first == second
    assert first.expected_portfolio_return is not None
    assert first.cvar is not None
    assert first.optimization_result.objective_value == (
        request.base_request.risk_aversion * first.cvar
        - first.expected_portfolio_return
    )


@pytest.mark.skipif(find_spec("scipy") is None, reason="optional SciPy is absent")
def test_real_scipy_maps_infeasible_problem() -> None:
    request = mean_cvar_request(
        constraints=PortfolioConstraints(
            maximum_cash_weight=Decimal("0.1"),
            maximum_position_weight=Decimal("0.1"),
        )
    )
    result = CpuMeanCvarOptimizer().optimize(request)
    assert result.optimization_result.status is OptimizationStatus.INFEASIBLE
