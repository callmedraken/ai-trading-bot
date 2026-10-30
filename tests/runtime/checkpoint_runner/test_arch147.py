"""Architecture 147 checkpoint and current source-authority coverage."""

from pathlib import Path

from scripts import checkpoint_runner as runner
from scripts import current_source_authority as current

ROOT = Path(runner.__file__).resolve().parents[1]


def test_arch147_is_current_source_only_full_without_effect_dispatch():
    spec = runner._checkpoint_specs()[runner.ARCH147_NAME]
    assert spec.name == runner.ARCH147_NAME
    assert spec.remote_branch == runner.ARCH147_BRANCH
    assert spec.preflight is None
    assert spec.execute is None
    assert runner.CI_CERTIFICATION_PROFILES[runner.ARCH147_NAME] == "full"
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS[0] == runner.ARCH147_NAME
    assert (
        spec.tests.count("tests/experiments/test_historical_research_partial_state.py")
        == 1
    )


def test_consumed_architecture_146_observer_is_not_current_route():
    assert runner.ARCH146_PARTIAL_STATE_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH146_PRE_B2_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH146B1_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert current.current_preflight_dispatch_failures(ROOT) == ()


def test_arch147_authority_is_static_and_does_not_dispatch_host_work(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Architecture 147 authority dispatched an effect")

    monkeypatch.setattr(runner, "preflight_checkpoint", forbidden)
    monkeypatch.setattr(runner, "execute_checkpoint", forbidden)
    assert runner._arch147_authority_check(ROOT) == ()


def test_arch147_resolves_for_feature_branch():
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), runner.ARCH147_BRANCH, "push"
        )
        == runner.ARCH147_NAME
    )
