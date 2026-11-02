"""Current authority for the Architecture 147 filtered-trend route."""

from pathlib import Path

from scripts.source_authority import current_owner

from scripts import checkpoint_runner as runner
from scripts import current_source_authority as current
from scripts import run_test_certification as certification

from .helpers import _historical_workflow_view

ROOT = Path(runner.__file__).resolve().parents[1]


def test_filtered_trend_checkpoint_is_source_only_full_and_precedes_p5a():
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH147_FILTERED_TREND_NAME]
    assert spec.remote_branch == runner.ARCH147_FILTERED_TREND_BRANCH
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS[:6] == (
        runner.ARCH147_P6_NAME,
        runner.ARCH147_P5B_NAME,
        runner.ARCH147_FILTERED_TREND_NAME,
        runner.ARCH147_P5A_NAME,
        runner.ARCH147_P4_NAME,
        runner.ARCH147_NAME,
    )
    assert (
        runner.resolve_ci_checkpoint(specs, spec.remote_branch, "push")
        == runner.ARCH147_FILTERED_TREND_NAME
    )
    assert runner._arch147_filtered_trend_authority_check(ROOT) == ()
    assert current.current_preflight_dispatch_failures(ROOT) == ()


def test_filtered_trend_modules_and_route_regression_are_full_owned():
    modules = {
        "tests/experiments/test_filtered_trend_data.py",
        "tests/experiments/test_filtered_trend_strategies.py",
        "tests/experiments/test_filtered_trend_campaign.py",
        "tests/experiments/test_filtered_trend_bundle.py",
    }
    spec = runner._checkpoint_specs()[runner.ARCH147_FILTERED_TREND_NAME]
    inventory = set(
        certification.select_inventory(certification.discover_inventory(ROOT), "full")
    )
    assert modules <= set(spec.tests)
    assert modules <= inventory
    assert "tests/runtime/checkpoint_runner/test_arch147_filtered_trend.py" in (
        certification.FULL_EXACT_MODULES
    )
    assert current_owner("_arch147_current_batch_workflow_is_reviewed") == (
        "checkpoint_runner"
    )
    assert current_owner("_arch147_filtered_trend_authority_check") == (
        "checkpoint_runner"
    )


def test_filtered_trend_route_is_removed_before_frozen_historical_predicate():
    workflow = (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    assert runner._arch147_current_batch_workflow_is_reviewed(workflow)
    reconstructed = _historical_workflow_view(workflow)
    assert runner._ARCH132_R3M_PREDECESSOR_BATCH_WORKFLOW_IS_REVIEWED(reconstructed)


def test_current_and_historical_workflow_routes_are_distinct_and_fail_closed():
    workflow = (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    historical = _historical_workflow_view(workflow)
    current_row = f"              {runner.ARCH147_FILTERED_TREND_NAME} {chr(96)}\n"
    historical_row = f"              {runner.ACTIVE_CI_CHECKPOINTS[0]} {chr(96)}\n"

    assert runner._arch147_current_batch_workflow_is_reviewed(workflow)
    assert runner._arch147_batch_workflow_is_reviewed(workflow)
    assert not runner._arch147_current_batch_workflow_is_reviewed(historical)
    assert runner._arch147_batch_workflow_is_reviewed(historical)

    invalid_views = (
        workflow.replace(current_row, "", 1),
        historical.replace(historical_row, historical_row + current_row, 1),
        historical.replace(historical_row, historical_row + historical_row, 1),
        historical + "  certification-full:\n",
    )
    for invalid in invalid_views:
        assert not runner._arch147_current_batch_workflow_is_reviewed(invalid)
        assert not runner._arch147_batch_workflow_is_reviewed(invalid)
