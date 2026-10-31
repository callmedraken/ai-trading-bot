"""P5A current authority is separate from immutable historical reconstruction."""

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner
from scripts import current_source_authority as current
from scripts import run_test_certification as certification

ROOT = Path(runner.__file__).resolve().parents[1]


def test_p5a_source_only_current_route_and_explicit_full_ownership():
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH147_P5A_NAME]
    assert spec.remote_branch == runner.ARCH147_P5A_BRANCH
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS[:3] == (
        runner.ARCH147_P5A_NAME,
        runner.ARCH147_P4_NAME,
        runner.ARCH147_NAME,
    )
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert runner.resolve_ci_checkpoint(specs, spec.remote_branch, "push") == spec.name
    assert current.current_preflight_dispatch_failures(ROOT) == ()
    assert runner._arch147_p5a_authority_check(ROOT) == ()
    assert runner._arch147_p4_authority_check(ROOT) == ()
    new_tests = {
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in (ROOT / "tests/desktop_paper").glob("test_*.py")
    }
    assert new_tests <= set(certification.FULL_EXACT_MODULES)
    assert new_tests <= set(spec.tests)


def test_p5a_inventory_carries_current_route_regression_exactly_once():
    spec = runner._checkpoint_specs()[runner.ARCH147_P5A_NAME]
    route_test = "tests/experiments/test_historical_research_partial_state.py"

    assert spec.tests.count(route_test) == 1
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS[:3] == (
        runner.ARCH147_P5A_NAME,
        runner.ARCH147_P4_NAME,
        runner.ARCH147_NAME,
    )


@pytest.mark.parametrize(
    "name", [runner.ARCH147_P5A_NAME, runner.ARCH147_P4_NAME, runner.ARCH147_NAME]
)
def test_each_current_route_rejects_host_dispatch(monkeypatch, name):
    specs = runner._checkpoint_specs()
    specs[name] = replace(specs[name], execute=lambda **kwargs: None)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert current.current_preflight_dispatch_failures(ROOT)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "malformed", "reordered"])
def test_p5a_current_workflow_projection_is_fail_closed(mutation):
    workflow = (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text()
    row = "              " + runner.ARCH147_P5A_NAME + " `\n"
    p4 = "              " + runner.ARCH147_P4_NAME + " `\n"
    altered = {
        "missing": workflow.replace(row, "", 1),
        "duplicate": workflow.replace(row, row + row, 1),
        "malformed": workflow.replace(row, row.replace(" `", ""), 1),
        "reordered": workflow.replace(row + p4, p4 + row, 1),
    }[mutation]
    for predicate in (
        runner._arch134_current_batch_workflow_is_reviewed,
        runner._arch134_readonly_diagnostic_batch_workflow_successor,
    ):
        assert predicate(workflow)
        assert not predicate(altered)


def test_p5a_authority_never_dispatches_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("effect dispatched")

    monkeypatch.setattr(runner, "preflight_checkpoint", forbidden)
    monkeypatch.setattr(runner, "execute_checkpoint", forbidden)
    assert runner._arch147_p5a_authority_check(ROOT) == ()


def test_p5a_authority_rejects_missing_required_package_module(monkeypatch):
    original = Path.is_file

    def is_file(path):
        if path == ROOT / "src/trading_bot/desktop_paper/configuration.py":
            return False
        return original(path)

    monkeypatch.setattr(Path, "is_file", is_file)
    assert "147 P5A source missing: configuration.py" in (
        runner._arch147_p5a_authority_check(ROOT)
    )


@pytest.mark.parametrize(
    "claim, diagnostic",
    [
        ("import trading_bot.robinhood_mcp", "147 P5A forbidden import: worker.py"),
        (
            "import trading_bot.experiments.desktop_research_campaign",
            "147 P5A worker imports research authority",
        ),
    ],
)
def test_p5a_authority_rejects_worker_effect_or_selection_imports(
    monkeypatch, claim, diagnostic
):
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        source = original(path, *args, **kwargs)
        if path == ROOT / "src/trading_bot/desktop_paper/worker.py":
            return source + "\n" + claim + "\n"
        return source

    monkeypatch.setattr(Path, "read_text", read_text)
    assert diagnostic in runner._arch147_p5a_authority_check(ROOT)
