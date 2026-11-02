from pathlib import Path

from scripts.arch147_p6_tiny_live_source import authority_failures

from scripts import checkpoint_runner as runner
from scripts import current_source_authority as current

ROOT = Path(runner.__file__).resolve().parents[1]


def test_p6_is_registered_first_with_bounded_live_dispatch():
    spec = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    assert spec.remote_branch == runner.ARCH147_P6_BRANCH
    assert spec.preflight is runner._arch147_p6_preflight
    assert spec.execute is runner._arch147_p6_execute
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS[:2] == (
        runner.ARCH147_P6_NAME,
        runner.ARCH147_P5B_NAME,
    )
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "full"
    assert authority_failures(ROOT) == ()
    assert current.current_preflight_dispatch_failures(ROOT) == ()


def test_p6_preflight_and_execute_are_not_p5b_facade_methods():
    p5b = runner._checkpoint_specs()[runner.ARCH147_P5B_NAME]
    p6 = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    assert p5b.execute is None
    assert p6.execute is runner._arch147_p6_execute
    assert p6.preflight is not p5b.preflight
