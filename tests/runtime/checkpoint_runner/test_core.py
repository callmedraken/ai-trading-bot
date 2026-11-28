from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner
from scripts import current_source_authority

from .helpers import (
    _EXPECTED_ACTIVE_CI_CHECKPOINTS,
    _batch_specs,
    _clean_source,
    _outcome,
    _parent_preflight_result,
    _spec,
)


def test_build_verification_steps_runs_both_nonmutating_ruff_gates(
    tmp_path: Path,
) -> None:
    steps = runner.build_verification_steps(
        _spec(),
        python_executable="python",
        basetemp=tmp_path / "pytest",
    )

    assert tuple(step.name for step in steps) == (
        "git_diff_check",
        "ruff_check",
        "ruff_format",
        "pytest",
    )

    lint = steps[1]
    formatting = steps[2]

    assert lint.argv[:5] == ("python", "-m", "ruff", "check", "--no-cache")
    assert lint.diagnostic_argv is not None
    assert "--diff" in lint.diagnostic_argv
    assert "--fix" not in lint.argv
    assert "--fix" not in lint.diagnostic_argv

    assert formatting.argv[:5] == (
        "python",
        "-m",
        "ruff",
        "format",
        "--check",
    )
    assert "--no-cache" in formatting.argv
    assert formatting.diagnostic_argv is not None
    assert "--diff" in formatting.diagnostic_argv


def test_run_verification_steps_continues_after_lint_failure(
    tmp_path: Path,
) -> None:
    steps = runner.build_verification_steps(
        _spec(),
        python_executable="python",
        basetemp=tmp_path / "pytest",
    )
    calls: list[tuple[str, bool]] = []

    def execute(
        step: runner.Step,
        diagnostic: bool,
    ) -> runner.CommandOutcome:
        calls.append((step.name, diagnostic))
        if step.name == "ruff_check" and not diagnostic:
            return _outcome(step.name, 1)
        suffix = "_diagnostic" if diagnostic else ""
        return _outcome(step.name + suffix, 0)

    outcomes = runner.run_verification_steps(steps, execute)

    assert calls == [
        ("git_diff_check", False),
        ("ruff_check", False),
        ("ruff_check", True),
        ("ruff_format", False),
        ("pytest", False),
    ]
    assert tuple(outcome.name for outcome in outcomes) == (
        "git_diff_check",
        "ruff_check",
        "ruff_check_diagnostic",
        "ruff_format",
        "pytest",
    )


def test_run_verification_steps_collects_both_ruff_diagnostics(
    tmp_path: Path,
) -> None:
    steps = runner.build_verification_steps(
        _spec(),
        python_executable="python",
        basetemp=tmp_path / "pytest",
    )
    calls: list[tuple[str, bool]] = []

    def execute(
        step: runner.Step,
        diagnostic: bool,
    ) -> runner.CommandOutcome:
        calls.append((step.name, diagnostic))
        if step.name in {"ruff_check", "ruff_format"} and not diagnostic:
            return _outcome(step.name, 1)
        suffix = "_diagnostic" if diagnostic else ""
        return _outcome(step.name + suffix, 0)

    runner.run_verification_steps(steps, execute)

    assert calls == [
        ("git_diff_check", False),
        ("ruff_check", False),
        ("ruff_check", True),
        ("ruff_format", False),
        ("ruff_format", True),
        ("pytest", False),
    ]


def _current_registry_invariant_failures(
    specs: dict[str, runner.CheckpointSpec],
    *,
    active_names: tuple[str, ...] | None = None,
    current_active_names: tuple[str, ...] | None = None,
    retained_names: tuple[str, ...] | None = None,
    certification_profiles: dict[str, str] | None = None,
) -> tuple[str, ...]:
    """Validate current registry closure and ownership without a name snapshot."""
    active = runner.ACTIVE_CI_CHECKPOINTS if active_names is None else active_names
    current_active = (
        runner.CURRENT_ACTIVE_CI_CHECKPOINTS
        if current_active_names is None
        else current_active_names
    )
    retained = runner.RETAINED_CHECKPOINTS if retained_names is None else retained_names
    profiles = (
        runner.CI_CERTIFICATION_PROFILES
        if certification_profiles is None
        else certification_profiles
    )
    failures: list[str] = []
    if not specs:
        failures.append("checkpoint registry is empty")

    for key, spec in specs.items():
        if key != spec.name:
            failures.append(f"registry key does not match spec name: {key}")
        if not spec.tests:
            failures.append(f"checkpoint has no tests: {key}")
        if not spec.ruff_paths:
            failures.append(f"checkpoint has no Ruff paths: {key}")
        runner_tests = tuple(
            path
            for path in spec.tests
            if path.startswith("tests/runtime/checkpoint_runner/")
        )
        uncovered = tuple(
            path
            for path in runner_tests
            if not any(
                ruff_path == "."
                or path == ruff_path
                or path.startswith(ruff_path.rstrip("/") + "/")
                for ruff_path in spec.ruff_paths
            )
        )
        if uncovered:
            failures.append(f"runner tests lack Ruff ownership in {key}: {uncovered}")

    route_groups = (
        ("active", active),
        ("current active", current_active),
        ("retained", retained),
    )
    for label, references in route_groups:
        if len(references) != len(set(references)):
            failures.append(f"duplicate {label} route references")
        for name in references:
            if name not in specs:
                failures.append(
                    f"{label} route references unregistered checkpoint: {name}"
                )

    for name, profile in profiles.items():
        if name not in specs:
            failures.append(
                f"certification profile references unregistered checkpoint: {name}"
            )
        if profile not in runner.CI_CERTIFICATION_PROFILE_VALUES:
            failures.append(f"unsupported certification profile for {name}: {profile}")

    current_route_valid = len(current_active) == len(set(current_active)) and all(
        name in specs and specs[name].name == name for name in current_active
    )
    current_specs = tuple(specs[name] for name in current_active if name in specs)
    if current_specs and current_route_valid:
        selected_tests, selected_ruff = runner.batch_requirements(current_specs)
        if not set(runner.COMMON_TESTS).issubset(selected_tests):
            failures.append("current active route omits common runner tests")
        if not set(runner.COMMON_RUFF_PATHS).issubset(selected_ruff):
            failures.append("current active route omits common runner Ruff ownership")
    elif current_active and not current_specs:
        failures.append("current active route has no registered checkpoints")

    return tuple(failures)


def test_current_checkpoint_registry_invariants_allow_growth():
    specs = runner._checkpoint_specs()

    assert _current_registry_invariant_failures(specs) == ()


def test_arch148_churn_checkpoint_is_source_only_and_mapped():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH148_CHURN_NAME]

    assert runner.ARCH148_CHURN_NAME == "arch148-churn-research"
    assert runner.ARCH148_CHURN_BRANCH == "feature/research-arch148-churn"
    assert spec.remote_branch == runner.ARCH148_CHURN_BRANCH
    assert spec.authority_check is runner._arch148_churn_authority_check
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner.ARCH148_CHURN_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH148_CHURN_NAME in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(runner.ARCH148_CHURN_NAME) == 1
    assert runner.CI_CERTIFICATION_PROFILES[runner.ARCH148_CHURN_NAME] == "full"
    assert (
        runner.resolve_ci_checkpoint(specs, runner.ARCH148_CHURN_BRANCH, "push")
        == runner.ARCH148_CHURN_NAME
    )
    assert runner._arch148_churn_authority_check(repo) == ()


def test_arch148_intraday_momentum_checkpoint_is_source_only_and_mapped():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH148_INTRADAY_MOMENTUM_NAME]

    assert runner.ARCH148_INTRADAY_MOMENTUM_NAME == (
        "arch148-intraday-momentum-research"
    )
    assert runner.ARCH148_INTRADAY_MOMENTUM_BRANCH == (
        "feature/research-arch148-intraday-momentum-current"
    )
    assert spec.remote_branch == runner.ARCH148_INTRADAY_MOMENTUM_BRANCH
    assert spec.authority_check is runner._arch148_intraday_momentum_authority_check
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner.ARCH148_INTRADAY_MOMENTUM_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH148_INTRADAY_MOMENTUM_NAME in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert (
        runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(
            runner.ARCH148_INTRADAY_MOMENTUM_NAME
        )
        == 1
    )
    assert (
        runner.CI_CERTIFICATION_PROFILES[runner.ARCH148_INTRADAY_MOMENTUM_NAME]
        == "full"
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs, runner.ARCH148_INTRADAY_MOMENTUM_BRANCH, "push"
        )
        == runner.ARCH148_INTRADAY_MOMENTUM_NAME
    )
    assert runner._arch148_intraday_momentum_authority_check(repo) == ()


def test_arch148_intraday_momentum_route_help_is_effect_free(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("route help dispatched a protected runner effect")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    monkeypatch.setattr(runner, "_git_state", forbidden)
    monkeypatch.setattr(runner, "_default_evidence_root", forbidden)
    monkeypatch.setattr(runner, "verify_checkpoint", forbidden)
    monkeypatch.setattr(runner, "verify_batch", forbidden)

    with pytest.raises(SystemExit) as exit_info:
        runner.main(["verify", runner.ARCH148_INTRADAY_MOMENTUM_NAME, "--help"])

    assert exit_info.value.code == 0
    assert runner.ARCH148_INTRADAY_MOMENTUM_NAME in capsys.readouterr().out


def test_arch149_monthly_defensive_rotation_checkpoint_is_source_only_and_mapped():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_NAME]

    assert runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_NAME == (
        "arch149-monthly-defensive-rotation-research"
    )
    assert runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_BRANCH == (
        "feature/research-arch149-monthly-defensive-rotation-current"
    )
    assert spec.remote_branch == runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_BRANCH
    assert (
        spec.authority_check
        is runner._arch149_monthly_defensive_rotation_authority_check
    )
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_NAME
        not in runner.ACTIVE_CI_CHECKPOINTS
    )
    assert (
        runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(
            runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_NAME
        )
        == 1
    )
    assert (
        runner.CI_CERTIFICATION_PROFILES[runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_NAME]
        == "full"
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs, runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_BRANCH, "push"
        )
        == runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_NAME
    )
    assert runner._arch149_monthly_defensive_rotation_authority_check(repo) == ()


def test_arch149_monthly_defensive_rotation_route_help_is_effect_free(
    monkeypatch, capsys
):
    def forbidden(*args, **kwargs):
        pytest.fail("route help dispatched a protected runner effect")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    monkeypatch.setattr(runner, "_git_state", forbidden)
    monkeypatch.setattr(runner, "_default_evidence_root", forbidden)
    monkeypatch.setattr(runner, "verify_checkpoint", forbidden)
    monkeypatch.setattr(runner, "verify_batch", forbidden)

    with pytest.raises(SystemExit) as exit_info:
        runner.main(
            ["verify", runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_NAME, "--help"]
        )

    assert exit_info.value.code == 0
    assert runner.ARCH149_MONTHLY_DEFENSIVE_ROTATION_NAME in capsys.readouterr().out


def test_arch150_intraday_ai_checkpoint_is_source_only_and_mapped():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH150_INTRADAY_AI_NAME]

    assert runner.ARCH150_INTRADAY_AI_NAME == (
        "arch150-intraday-ai-research-foundation"
    )
    assert runner.ARCH150_INTRADAY_AI_BRANCH == (
        "feature/research-arch150-intraday-ai-current"
    )
    assert spec.tests == runner.ARCH150_INTRADAY_AI_TESTS
    assert spec.ruff_paths == runner.ARCH150_INTRADAY_AI_RUFF
    assert {
        "src/trading_bot/experiments/arch150_g1_discovery.py",
        "tests/experiments/test_arch150_g1_discovery.py",
    } <= set(runner.ARCH150_INTRADAY_AI_PATHS)
    assert "tests/experiments/test_arch150_g1_discovery.py" in spec.tests
    assert "src/trading_bot/experiments/arch150_g1_discovery.py" in spec.ruff_paths
    assert "tests/experiments/test_arch150_g1_discovery.py" in spec.ruff_paths
    assert "tests/experiments/test_arch150_g1_validation.py" in spec.tests
    assert "src/trading_bot/experiments/arch150_g1_validation.py" in spec.ruff_paths
    assert "tests/experiments/test_arch150_g1_validation.py" in spec.ruff_paths
    assert spec.authority_check is runner._arch150_intraday_ai_authority_check
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner.ARCH150_INTRADAY_AI_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    assert (
        runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(runner.ARCH150_INTRADAY_AI_NAME) == 1
    )
    assert runner.CI_CERTIFICATION_PROFILES[runner.ARCH150_INTRADAY_AI_NAME] == "full"
    assert (
        runner.resolve_ci_checkpoint(specs, runner.ARCH150_INTRADAY_AI_BRANCH, "push")
        == runner.ARCH150_INTRADAY_AI_NAME
    )
    assert runner._arch150_intraday_ai_authority_check(repo) == ()


def test_arch151_intraday_walkforward_checkpoint_is_source_only_and_mapped():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    name = runner.ARCH151_INTRADAY_WALKFORWARD_NAME
    spec = specs[name]

    assert name == "arch151-intraday-walkforward-foundation"
    assert runner.ARCH151_INTRADAY_WALKFORWARD_BRANCH == (
        "feature/research-arch151-intraday-walkforward-current"
    )
    assert spec.tests == runner.ARCH151_INTRADAY_WALKFORWARD_TESTS
    assert spec.ruff_paths == runner.ARCH151_INTRADAY_WALKFORWARD_RUFF
    assert "tests/runtime/checkpoint_runner/test_core.py" in spec.tests
    assert "tests/runtime/checkpoint_runner/test_ci.py" in spec.tests
    assert "tests/runtime/checkpoint_runner/test_source_authority.py" in spec.tests
    assert "tests/experiments/test_arch151_intraday_walkforward.py" in spec.tests
    assert (
        "src/trading_bot/experiments/arch151_intraday_walkforward.py" in spec.ruff_paths
    )
    assert spec.authority_check is runner._arch151_intraday_walkforward_authority_check
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert name not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CERTIFICATION_PROFILES[name] == "full"
    assert (
        runner.resolve_ci_checkpoint(
            specs, runner.ARCH151_INTRADAY_WALKFORWARD_BRANCH, "push"
        )
        == name
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs, runner.ARCH151_INTRADAY_WALKFORWARD_BRANCH, "pull_request"
        )
        is None
    )
    assert runner._arch151_intraday_walkforward_authority_check(repo) == ()


def test_arch151_evaluator_successor_is_source_only_and_diff_selected():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    name = runner.ARCH151_INTRADAY_WALKFORWARD_EVALUATOR_NAME
    spec = specs[name]

    assert name == "arch151-intraday-walkforward-evaluator"
    assert spec.remote_branch == runner.ARCH151_INTRADAY_WALKFORWARD_BRANCH
    assert spec.tests == runner.ARCH151_INTRADAY_WALKFORWARD_EVALUATOR_TESTS
    assert spec.ruff_paths == runner.ARCH151_INTRADAY_WALKFORWARD_EVALUATOR_RUFF
    assert "scripts/source_authority.py" in spec.ruff_paths
    assert "tests/experiments/test_arch151_intraday_walkforward.py" in spec.tests
    assert (
        "tests/experiments/test_arch151_intraday_walkforward_evaluator.py" in spec.tests
    )
    assert (
        "src/trading_bot/experiments/arch151_intraday_walkforward_evaluator.py"
        in spec.ruff_paths
    )
    assert (
        "src/trading_bot/experiments/arch151_intraday_walkforward_operator.py"
        in spec.ruff_paths
    )
    assert (
        "tests/experiments/test_arch151_intraday_walkforward_operator.py" in spec.tests
    )
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert name not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CERTIFICATION_PROFILES[name] == "full"
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH151_INTRADAY_WALKFORWARD_BRANCH,
            "push",
        )
        == runner.ARCH151_INTRADAY_WALKFORWARD_NAME
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH151_INTRADAY_WALKFORWARD_BRANCH,
            "push",
            changed_paths=runner.ARCH151_INTRADAY_WALKFORWARD_PATHS,
        )
        == runner.ARCH151_INTRADAY_WALKFORWARD_NAME
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH151_INTRADAY_WALKFORWARD_BRANCH,
            "push",
            changed_paths=(
                *runner.ARCH151_INTRADAY_WALKFORWARD_EVALUATOR_PATHS[:2],
                *runner.ARCH151_INTRADAY_WALKFORWARD_PATHS,
                "scripts/checkpoint_runner.py",
                ".github/workflows/checkpoint-source-gates.yml",
                "docs/architecture/151-intraday-walk-forward-campaign.md",
            ),
        )
        == name
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH151_INTRADAY_WALKFORWARD_BRANCH,
            "pull_request",
            changed_paths=runner.ARCH151_INTRADAY_WALKFORWARD_EVALUATOR_PATHS,
        )
        is None
    )
    assert runner._arch151_intraday_walkforward_evaluator_authority_check(repo) == ()


def test_arch152_pm1_is_source_only_and_mapped_to_full():
    from scripts import run_test_certification as certification

    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    name = runner.ARCH152_PM1_NAME
    spec = specs[name]

    assert name == "arch152-portfolio-manager-foundation"
    assert runner.ARCH152_PM1_BRANCH == "feature/robinhood-portfolio-manager-current"
    assert spec.tests == runner.ARCH152_PM1_TESTS
    assert spec.ruff_paths == runner.ARCH152_PM1_RUFF
    assert set(runner.ARCH152_PM1_SOURCE_PATHS) <= set(spec.ruff_paths)
    assert set(runner.ARCH152_PM1_TEST_PATHS) <= set(spec.tests)
    assert set(runner.ARCH152_PM1_TEST_SUPPORT_PATHS) <= set(spec.ruff_paths)
    assert "tests/portfolio_manager" in certification.FULL_DIRECTORIES
    assert spec.authority_check is runner._arch152_pm1_authority_check
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert name not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CERTIFICATION_PROFILES[name] == "full"
    assert (
        runner.resolve_ci_checkpoint(specs, runner.ARCH152_PM1_BRANCH, "push") == name
    )
    assert (
        runner.resolve_ci_checkpoint(specs, runner.ARCH152_PM1_BRANCH, "pull_request")
        is None
    )
    assert runner._arch152_pm1_authority_check(repo) == ()


def test_arch152_pm2d_b1_is_source_only_and_diff_selected_on_pm_branch():
    from scripts import run_test_certification as certification

    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    name = runner.ARCH152_PM2D_B1_NAME
    spec = specs[name]

    assert name == "arch152-pm2d-b1-sec-sharadar-bounded-qualification-source"
    assert runner.ARCH152_PM2D_B1_BRANCH == runner.ARCH152_PM1_BRANCH
    assert spec.tests == runner.ARCH152_PM2D_B1_TESTS
    assert spec.ruff_paths == runner.ARCH152_PM2D_B1_RUFF
    assert "scripts/current_source_authority.py" in spec.ruff_paths
    assert set(runner.ARCH152_PM2D_B1_SOURCE_PATHS) <= set(spec.ruff_paths)
    assert set(runner.ARCH152_PM2D_B1_TEST_PATHS) <= set(spec.tests)
    assert (
        "src/trading_bot/portfolio_manager/sec_native_observation.py"
        in runner.ARCH152_PM2D_B1_SOURCE_PATHS
    )
    assert (
        "src/trading_bot/portfolio_manager/sec_" + "real_observation.py"
        in runner.ARCH152_PM2D_B1_SOURCE_PATHS
    )
    assert (
        "tests/portfolio_manager/test_sec_native_observation.py"
        in runner.ARCH152_PM2D_B1_TEST_PATHS
    )
    assert (
        "docs/architecture/152-pm2d-b1-r-real-fundamental-observation-readiness.md"
        in runner.ARCH152_PM2D_B1_PATHS
    )
    assert (
        "docs/architecture/152-pm2d-b1-n-reusable-sec-financial-statement-ingestion.md"
        in runner.ARCH152_PM2D_B1_PATHS
    )
    assert (
        "docs/validation/arch152-pm2d-b1-n-reusable-sec-financial-statement-ingestion.md"
        in runner.ARCH152_PM2D_B1_PATHS
    )
    assert "tests/portfolio_manager" in certification.FULL_DIRECTORIES
    assert spec.authority_check is runner._arch152_pm2d_b1_authority_check
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert name in current_source_authority.develop_static_checkpoints(repo)
    assert name not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CERTIFICATION_PROFILES[name] == "full"
    assert (
        runner.resolve_ci_checkpoint(specs, runner.ARCH152_PM2D_B1_BRANCH, "push")
        == runner.ARCH152_PM1_NAME
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH152_PM2D_B1_BRANCH,
            "push",
            changed_paths=runner.ARCH152_PM2D_B1_SOURCE_PATHS,
        )
        == name
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH152_PM2D_B1_BRANCH,
            "push",
            changed_paths=runner.ARCH152_PM2D_B1_TEST_PATHS,
        )
        == name
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH152_PM2D_B1_BRANCH,
            "push",
            changed_paths=runner.ARCH152_PM1_SOURCE_PATHS,
        )
        == runner.ARCH152_PM1_NAME
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH152_PM2D_B1_BRANCH,
            "push",
            changed_paths=("README.md",),
        )
        == runner.ARCH152_PM1_NAME
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH152_PM2D_B1_BRANCH,
            "push",
            changed_paths=("src/trading_bot/portfolio_manager/research_snapshot.py",),
        )
        == runner.ARCH152_PM1_NAME
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH152_PM2D_B1_BRANCH,
            "push",
            changed_paths=(
                runner.ARCH152_PM1_SOURCE_PATHS[0],
                runner.ARCH152_PM2D_B1_SOURCE_PATHS[0],
            ),
        )
        == name
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs, runner.ARCH152_PM2D_B1_BRANCH, "pull_request"
        )
        is None
    )
    assert runner._arch152_pm2d_b1_authority_check(repo) == ()


def test_current_commit_changed_paths_uses_nul_delimited_no_rename_diff(
    monkeypatch,
):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return runner.subprocess.CompletedProcess(
            argv,
            0,
            stdout=b"space name.py\0line\nbreak.py\0",
            stderr=b"",
        )

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner._current_commit_changed_paths(Path("repo")) == (
        "space name.py",
        "line\nbreak.py",
    )
    assert calls[0][0] == (
        "git",
        "diff",
        "--name-only",
        "--no-renames",
        "-z",
        "HEAD^",
        "HEAD",
        "--",
    )
    assert calls[0][1]["env"]["GIT_OPTIONAL_LOCKS"] == "0"


@pytest.mark.parametrize(
    "completed",
    [
        (1, b"path.py\0"),
        (0, b"path.py"),
        (0, b"path.py\0\0"),
        (0, b"\xff\0"),
    ],
)
def test_current_commit_changed_paths_fails_closed_on_invalid_git_output(
    monkeypatch, completed
):
    def run(argv, **kwargs):
        return runner.subprocess.CompletedProcess(
            argv, completed[0], stdout=completed[1], stderr=b"secret diagnostic"
        )

    monkeypatch.setattr(runner.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="current commit path diff"):
        runner._current_commit_changed_paths(Path("repo"))


def test_arch150_d1_data_custody_route_is_source_only_and_diff_selected():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_NAME]

    assert runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE == (
        "arch150-intraday-data-custody-source"
    )
    assert spec.remote_branch == runner.ARCH150_INTRADAY_AI_BRANCH
    assert spec.tests == runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_TESTS
    assert spec.ruff_paths == runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_RUFF
    assert "tests/experiments/test_arch150_d1_requalify.py" in spec.tests
    assert "src/trading_bot/experiments/arch150_d1_requalify.py" in spec.ruff_paths
    assert "tests/experiments/test_arch150_d1_requalify.py" in spec.ruff_paths
    assert {
        "src/trading_bot/experiments/arch150_d1_requalify.py",
        "tests/experiments/test_arch150_d1_requalify.py",
    } <= set(runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_PATHS)
    assert (
        spec.authority_check is runner._arch150_d1_intraday_data_custody_authority_check
    )
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(
            runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_NAME
        )
        == 1
    )
    assert (
        runner.CI_CERTIFICATION_PROFILES[
            runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_NAME
        ]
        == "full"
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH150_INTRADAY_AI_BRANCH,
            "push",
            changed_paths=runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_PATHS,
        )
        == runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_NAME
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs,
            runner.ARCH150_INTRADAY_AI_BRANCH,
            "push",
            changed_paths=("src/trading_bot/experiments/arch150_d1_requalify.py",),
        )
        == runner.ARCH150_D1_INTRADAY_DATA_CUSTODY_SOURCE_NAME
    )
    assert (
        runner.resolve_ci_checkpoint(specs, runner.ARCH150_INTRADAY_AI_BRANCH, "push")
        == runner.ARCH150_INTRADAY_AI_NAME
    )
    assert runner._arch150_d1_intraday_data_custody_authority_check(repo) == ()


def test_arch150_intraday_ai_help_is_effect_free(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("source-only help dispatched an external effect")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    monkeypatch.setattr(runner, "_git_state", forbidden)
    monkeypatch.setattr(runner, "_default_evidence_root", forbidden)
    monkeypatch.setattr(runner, "verify_checkpoint", forbidden)
    monkeypatch.setattr(runner, "verify_batch", forbidden)

    with pytest.raises(SystemExit) as exit_info:
        runner.main(["verify", runner.ARCH150_INTRADAY_AI_NAME, "--help"])

    assert exit_info.value.code == 0
    assert runner.ARCH150_INTRADAY_AI_NAME in capsys.readouterr().out


def test_ai_strategy_discovery_checkpoint_is_source_only_and_mapped():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.AI_STRATEGY_DISCOVERY_FOUNDATION_NAME]

    assert (
        runner.AI_STRATEGY_DISCOVERY_FOUNDATION_NAME
        == "arch-ai-strategy-discovery-foundation"
    )
    assert (
        runner.AI_STRATEGY_DISCOVERY_FOUNDATION_BRANCH
        == "feature/research-ai-strategy-discovery-current"
    )
    assert spec.remote_branch == runner.AI_STRATEGY_DISCOVERY_FOUNDATION_BRANCH
    assert (
        spec.authority_check is runner._ai_strategy_discovery_foundation_authority_check
    )
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        runner.AI_STRATEGY_DISCOVERY_FOUNDATION_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    )
    assert (
        runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(
            runner.AI_STRATEGY_DISCOVERY_FOUNDATION_NAME
        )
        == 1
    )
    assert (
        runner.CI_CERTIFICATION_PROFILES[runner.AI_STRATEGY_DISCOVERY_FOUNDATION_NAME]
        == "full"
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs, runner.AI_STRATEGY_DISCOVERY_FOUNDATION_BRANCH, "push"
        )
        == runner.AI_STRATEGY_DISCOVERY_FOUNDATION_NAME
    )
    assert (
        runner.AI_STRATEGY_DISCOVERY_FOUNDATION_NAME
        in current_source_authority.develop_static_checkpoints(repo)
    )
    assert runner._ai_strategy_discovery_foundation_authority_check(repo) == ()


def test_ai_strategy_discovery_g1_engine_is_source_only_full_and_mapped():
    repo = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    spec = specs[runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_NAME]

    assert runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_NAME == (
        "arch-ai-strategy-discovery-g1-engine"
    )
    assert runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_BRANCH == (
        "feature/research-ai-strategy-discovery-g1-engine-current"
    )
    assert spec.remote_branch == runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_BRANCH
    assert (
        spec.authority_check is runner._ai_strategy_discovery_g1_engine_authority_check
    )
    assert spec.tests == runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_TESTS
    assert spec.ruff_paths == runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_RUFF
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    )
    assert (
        runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(
            runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_NAME
        )
        == 1
    )
    assert (
        runner.CI_CERTIFICATION_PROFILES[runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_NAME]
        == "full"
    )
    assert (
        runner.resolve_ci_checkpoint(
            specs, runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_BRANCH, "push"
        )
        == runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_NAME
    )
    assert (
        runner.AI_STRATEGY_DISCOVERY_G1_ENGINE_NAME
        in current_source_authority.develop_static_checkpoints(repo)
    )
    assert runner._ai_strategy_discovery_g1_engine_authority_check(repo) == ()


def test_registry_invariants_accept_additions_and_reject_missing_references():
    specs = runner._checkpoint_specs()
    synthetic_name = "synthetic-future-checkpoint"
    synthetic = runner.CheckpointSpec(
        name=synthetic_name,
        description="test-only additive checkpoint",
        tests=(
            *runner.COMMON_TESTS,
            "tests/runtime/checkpoint_runner/test_synthetic_future.py",
        ),
        ruff_paths=(
            *runner.COMMON_RUFF_PATHS,
            "tests/runtime/checkpoint_runner/test_synthetic_future.py",
        ),
        authority_check=lambda _repo: (),
    )
    expanded = {**specs, synthetic_name: synthetic}
    assert _current_registry_invariant_failures(expanded) == ()

    active_with_synthetic = (*runner.ACTIVE_CI_CHECKPOINTS, synthetic_name)
    current_with_synthetic = (
        *runner.CURRENT_ACTIVE_CI_CHECKPOINTS,
        synthetic_name,
    )
    assert (
        _current_registry_invariant_failures(
            expanded,
            active_names=active_with_synthetic,
            current_active_names=current_with_synthetic,
        )
        == ()
    )

    missing_route = (
        *runner.CURRENT_ACTIVE_CI_CHECKPOINTS,
        "synthetic-missing-current-route",
    )
    failures = _current_registry_invariant_failures(
        expanded,
        current_active_names=missing_route,
    )
    assert (
        "current active route references unregistered checkpoint: "
        "synthetic-missing-current-route"
    ) in failures

    missing_profile = {
        **runner.CI_CERTIFICATION_PROFILES,
        "synthetic-missing-profile-checkpoint": "full",
    }
    failures = _current_registry_invariant_failures(
        expanded,
        certification_profiles=missing_profile,
    )
    assert (
        "certification profile references unregistered checkpoint: "
        "synthetic-missing-profile-checkpoint"
    ) in failures

    malformed = dict(expanded)
    malformed[synthetic_name] = replace(synthetic, name="different-spec-name")
    assert any(
        failure.startswith("registry key does not match spec name:")
        for failure in _current_registry_invariant_failures(malformed)
    )

    empty_inventory = replace(synthetic, tests=(), ruff_paths=())
    failures = _current_registry_invariant_failures(
        {synthetic_name: empty_inventory},
        active_names=(),
        current_active_names=(),
        retained_names=(),
        certification_profiles={},
    )
    assert f"checkpoint has no tests: {synthetic_name}" in failures
    assert f"checkpoint has no Ruff paths: {synthetic_name}" in failures

    duplicate_current_route = (
        *runner.CURRENT_ACTIVE_CI_CHECKPOINTS,
        runner.CURRENT_ACTIVE_CI_CHECKPOINTS[0],
    )
    failures = _current_registry_invariant_failures(
        specs,
        current_active_names=duplicate_current_route,
    )
    assert "duplicate current active route references" in failures


def test_arch128_arch130_arch131_dispatch_contracts_remain_exact():
    specs = runner._checkpoint_specs()

    assert specs["arch128-parent-acl-repair"].execute is not None
    assert specs["arch128-r4"].execute is not None
    assert specs["arch128-r5-substrate"].execute is None
    assert specs["arch128-r5-trading"].execute is None
    assert specs["arch128-r6"].preflight is None
    assert specs["arch128-r6"].execute is None
    assert specs["arch128-r7"].preflight is not None
    assert specs["arch128-r7"].execute is runner._r7_execute
    assert specs["arch130-r8i-d1"].preflight is runner._arch130_r8i_d1_preflight
    assert specs["arch130-r8i-d1"].execute is None
    for name in (
        "arch131-robinhood-review-paper",
        "arch131-robinhood-mcp-schema",
        "arch131-robinhood-paper-cycle",
        "arch131-robinhood-performance",
        "arch131-robinhood-direct-mcp",
    ):
        assert specs[name].preflight is None
        assert specs[name].execute is None
    assert specs["arch128-r5-substrate"].remote_head_env is None
    assert (
        specs["arch128-r5-trading"].remote_head_env == runner.R5_TRADING_REMOTE_HEAD_ENV
    )


def test_rhc2_registration_is_manual_and_unmapped() -> None:
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH147_RHC2_NAME]

    assert spec.name == "arch147-rhc2-robinhood-order-scope-successor-observation"
    assert spec.preflight is runner._arch147_rhc2_preflight
    assert spec.execute is None
    assert spec.remote_branch is None
    assert spec.remote_head_env is None
    assert runner.ARCH147_RHC2_NAME not in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH147_RHC2_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH147_RHC2_NAME not in runner.CI_CERTIFICATION_PROFILES
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), runner.ARCH147_PROTOTYPE_BRANCH, "push"
        )
        == runner.ARCH147_PROTOTYPE_NAME
    )
    assert runner._arch147_rhc2_authority_check(root) == ()


def test_default_evidence_root_is_outside_repo() -> None:
    repo_root = Path(runner.__file__).resolve().parent.parent
    evidence_root = runner._default_evidence_root(repo_root)

    assert evidence_root != repo_root
    assert repo_root not in evidence_root.parents


def test_read_only_effect_guard_rejects_unexpected_mutation() -> None:
    result = _parent_preflight_result()
    result["acl_mutation"] = "MUTATED"

    try:
        runner._require_not_run(result, ("acl_mutation",))
    except RuntimeError as exc:
        assert "acl_mutation" in str(exc)
    else:
        raise AssertionError("unexpected mutation was accepted")


def test_remote_branch_head_is_bounded_and_noninteractive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return subprocess.CompletedProcess(
            argv,
            0,
            "a" * 40 + "\trefs/heads/feature/example\n",
            "",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    head = runner._remote_branch_head(tmp_path, "feature/example")

    assert head == "a" * 40
    assert observed["timeout"] == runner.REMOTE_LOOKUP_TIMEOUT_SECONDS
    environment = observed["env"]
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["GCM_INTERACTIVE"] == "Never"
    assert environment["GIT_OPTIONAL_LOCKS"] == "0"


def test_remote_branch_head_timeout_fails_closed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    try:
        runner._remote_branch_head(tmp_path, "feature/example")
    except RuntimeError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("timed-out remote lookup was accepted")


def test_trusted_remote_head_handoff_requires_exact_lower_hex(
    monkeypatch,
) -> None:
    variable = "TEST_REMOTE_HEAD"

    for value in ("", "a" * 39, "A" * 40, "g" * 40):
        monkeypatch.setenv(variable, value)
        try:
            runner._trusted_remote_head_from_env(variable)
        except RuntimeError as exc:
            assert variable in str(exc)
        else:
            raise AssertionError("malformed trusted remote-head handoff was accepted")

    monkeypatch.setenv(variable, "a" * 40)
    assert runner._trusted_remote_head_from_env(variable) == "a" * 40


def test_preflight_checkpoint_accepts_bound_trusted_remote_head(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "HEAD",
        "porcelain": "",
    }
    variable = "TEST_TRUSTED_REMOTE_HEAD"
    monkeypatch.setenv(variable, state["head"])
    monkeypatch.setattr(runner, "_git_state", lambda repo: dict(state))
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("live remote lookup should not run")
        ),
    )

    spec = runner.CheckpointSpec(
        name="example",
        description="example",
        tests=(),
        ruff_paths=(),
        authority_check=lambda repo: (),
        preflight=lambda: {
            "status": "PASS",
            "primary": {"status": "PASS"},
        },
        remote_branch="feature/pinned",
        remote_head_env=variable,
    )

    passed, report_path = runner.preflight_checkpoint(
        spec,
        repo_root=tmp_path,
        evidence_root=tmp_path / "external-handoff",
    )

    assert passed is True
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["source"]["remote_head"] == state["head"]
    assert report["source"]["remote_head_source"] == f"TRUSTED_ENV:{variable}"


def test_preflight_checkpoint_rejects_mismatched_trusted_remote_head(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = 0
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "HEAD",
        "porcelain": "",
    }
    variable = "TEST_TRUSTED_REMOTE_HEAD"
    monkeypatch.setenv(variable, "c" * 40)
    monkeypatch.setattr(runner, "_git_state", lambda repo: dict(state))

    def preflight() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"status": "PASS", "primary": {"status": "PASS"}}

    spec = runner.CheckpointSpec(
        name="example",
        description="example",
        tests=(),
        ruff_paths=(),
        authority_check=lambda repo: (),
        preflight=preflight,
        remote_branch="feature/pinned",
        remote_head_env=variable,
    )

    try:
        runner.preflight_checkpoint(
            spec,
            repo_root=tmp_path,
            evidence_root=tmp_path / "external-handoff-mismatch",
        )
    except RuntimeError as exc:
        assert "not the live remote branch head" in str(exc)
    else:
        raise AssertionError("mismatched trusted remote-head handoff was accepted")

    assert calls == 0


def test_preflight_checkpoint_requires_live_remote_head(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = 0
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "feature/example",
        "porcelain": "",
    }

    monkeypatch.setattr(runner, "_git_state", lambda repo: dict(state))
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda repo, branch: "c" * 40,
    )

    def preflight() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "status": "PASS",
            "primary": {"status": "PASS"},
            "diagnostics": {},
        }

    spec = runner.CheckpointSpec(
        name="example",
        description="example",
        tests=(),
        ruff_paths=(),
        authority_check=lambda repo: (),
        preflight=preflight,
    )

    try:
        runner.preflight_checkpoint(
            spec,
            repo_root=tmp_path,
            evidence_root=tmp_path / "evidence",
        )
    except RuntimeError as exc:
        assert "live remote branch head" in str(exc)
    else:
        raise AssertionError("stale source was accepted")

    assert calls == 0


def test_preflight_checkpoint_writes_external_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "feature/example",
        "porcelain": "",
    }

    monkeypatch.setattr(runner, "_git_state", lambda repo: dict(state))
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda repo, branch: state["head"],
    )

    spec = runner.CheckpointSpec(
        name="example",
        description="example",
        tests=(),
        ruff_paths=(),
        authority_check=lambda repo: (),
        preflight=lambda: {
            "status": "PASS",
            "primary": {"status": "PASS"},
            "diagnostics": {},
        },
    )

    passed, report = runner.preflight_checkpoint(
        spec,
        repo_root=tmp_path,
        evidence_root=tmp_path / "external",
    )

    assert passed is True
    assert report.is_file()
    payload = report.read_text(encoding="utf-8")
    assert '"kind": "read_only_preflight"' in payload
    assert '"protected_execution": "NOT_AUTHORIZED"' in payload


def test_preflight_checkpoint_allows_detached_with_pinned_remote(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "HEAD",
        "porcelain": "",
    }
    observed_branches: list[str] = []

    monkeypatch.setattr(runner, "_git_state", lambda repo: dict(state))

    def remote_head(repo: Path, branch: str) -> str:
        observed_branches.append(branch)
        return state["head"]

    monkeypatch.setattr(runner, "_remote_branch_head", remote_head)

    spec = runner.CheckpointSpec(
        name="example",
        description="example",
        tests=(),
        ruff_paths=(),
        authority_check=lambda repo: (),
        preflight=lambda: {
            "status": "PASS",
            "primary": {"status": "PASS"},
            "diagnostics": {},
        },
        remote_branch="feature/pinned",
    )

    passed, report = runner.preflight_checkpoint(
        spec,
        repo_root=tmp_path,
        evidence_root=tmp_path / "external-detached",
    )

    assert passed is True
    assert report.is_file()
    assert observed_branches == ["feature/pinned"]


def test_execute_checkpoint_requires_live_remote_head(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = 0
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "HEAD",
        "porcelain": "",
    }

    monkeypatch.setattr(runner, "_git_state", lambda repo: dict(state))
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda repo, branch: "c" * 40,
    )

    def execute() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "status": "PASS",
            "primary": {"status": "PASS"},
            "effect_disposition": "CONFIRMED",
        }

    spec = runner.CheckpointSpec(
        name="example",
        description="example",
        tests=(),
        ruff_paths=(),
        authority_check=lambda repo: (),
        execute=execute,
        remote_branch="feature/pinned",
    )

    try:
        runner.execute_checkpoint(
            spec,
            repo_root=tmp_path,
            evidence_root=tmp_path / "external",
        )
    except RuntimeError as exc:
        assert "live remote branch head" in str(exc)
    else:
        raise AssertionError("stale source was accepted")

    assert calls == 0


def test_execute_checkpoint_writes_attempt_and_final_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "HEAD",
        "porcelain": "",
    }

    monkeypatch.setattr(runner, "_git_state", lambda repo: dict(state))
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda repo, branch: state["head"],
    )

    spec = runner.CheckpointSpec(
        name="example",
        description="example",
        tests=(),
        ruff_paths=(),
        authority_check=lambda repo: (),
        execute=lambda: {
            "status": "PASS",
            "primary": {"status": "PASS"},
            "effect_disposition": "CONFIRMED",
        },
        remote_branch="feature/pinned",
    )

    passed, report = runner.execute_checkpoint(
        spec,
        repo_root=tmp_path,
        evidence_root=tmp_path / "external",
    )

    assert passed is True
    assert report.is_file()
    attempt = report.with_name("attempt.json")
    assert attempt.is_file()
    payload = report.read_text(encoding="utf-8")
    assert '"kind": "protected_execution"' in payload
    assert '"protected_execution": "ATTEMPTED"' in payload
    assert '"automatic_retry": "NOT_AUTHORIZED"' in payload
    assert '"effect_disposition": "CONFIRMED"' in payload


def test_execute_checkpoint_preserves_attempt_on_runner_exception(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "HEAD",
        "porcelain": "",
    }

    monkeypatch.setattr(runner, "_git_state", lambda repo: dict(state))
    monkeypatch.setattr(
        runner,
        "_remote_branch_head",
        lambda repo, branch: state["head"],
    )

    def execute() -> dict[str, object]:
        raise RuntimeError("ambiguous protected failure")

    spec = runner.CheckpointSpec(
        name="example",
        description="example",
        tests=(),
        ruff_paths=(),
        authority_check=lambda repo: (),
        execute=execute,
        remote_branch="feature/pinned",
    )

    passed, report = runner.execute_checkpoint(
        spec,
        repo_root=tmp_path,
        evidence_root=tmp_path / "external-stop",
    )

    assert passed is False
    assert report.is_file()
    assert report.with_name("attempt.json").is_file()
    payload = report.read_text(encoding="utf-8")
    assert '"status": "STOPPED"' in payload
    assert '"effect_disposition": "MAY_HAVE_OCCURRED"' in payload
    assert '"automatic_retry": "NOT_AUTHORIZED"' in payload


def test_batch_first_seen_requirements_and_all_current_coverage():
    tests, ruff = runner.batch_requirements(_batch_specs([]))
    assert tests == ("tests/shared.py", "tests/first.py", "tests/second.py")
    assert ruff == ("shared.py", "first.py", "second.py", "third.py")
    specs = runner._checkpoint_specs()
    selected = [specs[name] for name in _EXPECTED_ACTIVE_CI_CHECKPOINTS]
    tests, ruff = runner.batch_requirements(selected)
    assert len(tests) == len(set(tests))
    assert len(ruff) == len(set(ruff))
    assert tests[0] == runner.COMMON_TESTS[0]
    assert ruff[: len(runner.COMMON_RUFF_PATHS)] == runner.COMMON_RUFF_PATHS
    for spec in selected:
        assert set(spec.tests) <= set(tests)
        assert set(spec.ruff_paths) <= set(ruff)
    assert runner.ACTIVE_CI_CHECKPOINTS == _EXPECTED_ACTIVE_CI_CHECKPOINTS
    # Reconstruct the exact GUI-A14 parent tuple, excluding later checkpoints.
    active = tuple(
        name
        for name in runner.ACTIVE_CI_CHECKPOINTS
        if name
        not in {
            runner.READONLY_ADMISSION_NAME,
            runner.ARCH146A_NAME,
            runner.ARCH134_AUTH_NAME,
            runner.ARCH134_D1R5_NAME,
            runner.ARCH134_D1R6_NAME,
            runner.ARCH134_D1R7_NAME,
            runner.ARCH134_D1R8_NAME,
            runner.ARCH134_F1_NAME,
            runner.ARCH144C_NAME,
            runner.ARCH145A_NAME,
            runner.ARCH134_F1R1_B_NAME,
            runner.ARCH134_R5_NAME,
            runner.ARCH134_FRESH_NAME,
            runner.ARCH134_ACL_NAME,
            runner.ARCH134_D1S4_NAME,
            runner.ARCH134_D1S3_NAME,
            runner.ARCH134_D1S2_NAME,
            runner.ARCH134_D1S1_NAME,
            runner.ARCH134_F1R1_C1_NAME,
        }
    )
    parent = (*active[:7], runner.SUPERVISED_PUBLICATION_RECOVERY_NAME, *active[7:])
    assert len(parent) == 63 and len(active) == 62
    parent_value = ast.parse(repr(parent), mode="eval").body
    assert (
        hashlib.sha256(
            ast.dump(parent_value, include_attributes=False).encode("utf-8")
        ).hexdigest()
        == "9be10678e014f0a7db34338409f89f82be1ec9b05933120e24f3f2d8b25289ff"
    )


def test_ci_checkpoint_resolution_is_exact_and_fails_broad():
    specs = runner._checkpoint_specs()
    name = "arch133-robinhood-supervised-release-installation-operator"
    branch = specs[name].remote_branch
    assert runner.resolve_ci_checkpoint(specs, branch, "push") == name
    assert runner.resolve_ci_checkpoint(specs, branch, "pull_request") is None
    assert runner.resolve_ci_checkpoint(specs, "feature/unknown", "push") is None

    duplicate = dict(specs)
    duplicate["duplicate"] = replace(specs[name], name="duplicate")
    assert runner.resolve_ci_checkpoint(duplicate, branch, "push") is None

    inactive = {"inactive": replace(specs[name], name="inactive")}
    assert runner.resolve_ci_checkpoint(inactive, branch, "push") is None


def test_duration_balanced_shards_are_deterministic_disjoint_and_complete():
    tests = tuple(runner.CI_TEST_DURATION_WEIGHTS)
    first = runner.duration_balanced_test_shards(tests, 4)
    second = runner.duration_balanced_test_shards(tests, 4)
    assert first == second
    assert sorted(path for shard in first for path in shard) == sorted(tests)
    assert sum(len(shard) for shard in first) == len(tests)
    assert len({path for shard in first for path in shard}) == len(tests)

    loads = [
        sum(runner.CI_TEST_DURATION_WEIGHTS[path] for path in shard) for shard in first
    ]
    assert max(loads) - min(loads) < 0.1
    with pytest.raises(ValueError, match="test shard count rejected"):
        runner.duration_balanced_test_shards(("tests/one.py",), 2)


@pytest.mark.parametrize(
    ("phase", "expected_steps", "authority_calls"),
    [
        ("static", ["git_diff_check", "ruff_check", "ruff_format"], 1),
        ("tests", ["pytest"], 0),
    ],
)
def test_single_source_gate_phase_separates_static_authority_and_tests(
    tmp_path,
    monkeypatch,
    phase,
    expected_steps,
    authority_calls,
):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    calls = []
    authorities = []

    def authority(repo):
        authorities.append(repo)
        return ()

    spec = replace(_spec(), authority_check=authority)
    monkeypatch.setattr(runner, "_git_state", lambda repo: _clean_source())
    monkeypatch.setenv(runner.SOURCE_GATE_PHASE_ENV, phase)
    monkeypatch.setattr(
        runner,
        "_execute_step",
        lambda step, **kw: calls.append(step) or _outcome(step.name, 0),
    )

    passed, path = runner.verify_checkpoint(
        spec,
        repo_root=tmp_path,
        evidence_root=tmp_path / "evidence",
    )

    assert passed
    assert [step.name for step in calls] == expected_steps
    assert len(authorities) == authority_calls
    report = json.loads(path.read_text())
    assert report["phase"] == phase
    assert report["authority_checked"] is (phase == "static")
    assert bool(report["executed_tests"]) is (phase == "tests")


def test_batch_tests_phase_shards_and_skips_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    authorities = []
    specs = _batch_specs(authorities)
    monkeypatch.setattr(runner, "_git_state", lambda repo: _clean_source())
    monkeypatch.setenv(runner.SOURCE_GATE_PHASE_ENV, "tests")
    monkeypatch.setenv(runner.SOURCE_GATE_SHARD_INDEX_ENV, "0")
    monkeypatch.setenv(runner.SOURCE_GATE_SHARD_COUNT_ENV, "2")
    calls = []
    monkeypatch.setattr(
        runner,
        "_execute_step",
        lambda step, **kw: calls.append(step) or _outcome(step.name, 0),
    )

    passed, path = runner.verify_batch(
        specs, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
    )

    assert passed
    assert authorities == []
    assert [step.name for step in calls] == ["pytest"]
    report = json.loads(path.read_text())
    assert report["phase"] == "tests"
    assert report["authority_checked"] is False
    assert report["test_shard"] == {"index": 0, "count": 2}
    assert report["executed_tests"]


@pytest.mark.parametrize(
    "failure", [None, "pytest", "ruff_check", "ruff_format", "git_diff_check"]
)
def test_batch_shares_commands_preserves_order_and_collects_authorities(
    tmp_path,
    monkeypatch,
    failure,
):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    authorities = []
    specs = _batch_specs(authorities)
    monkeypatch.setattr(runner, "_git_state", lambda repo: _clean_source())
    calls = []

    def execute(step, **kwargs):
        diagnostic = kwargs["diagnostic"]
        calls.append((step, diagnostic))
        return _outcome(
            step.name + ("_diagnostic" if diagnostic else ""),
            1 if step.name == failure and not diagnostic else 0,
        )

    monkeypatch.setattr(runner, "_execute_step", execute)
    passed, report_path = runner.verify_batch(
        specs, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
    )
    assert passed == (failure is None)
    primary = [step.name for step, diagnostic in calls if not diagnostic]
    expected = ["git_diff_check", "ruff_check", "ruff_format"]
    if failure not in {"git_diff_check", "ruff_check", "ruff_format"}:
        expected.append("pytest")
    assert primary == expected
    assert [step.name for step, diagnostic in calls if diagnostic] == (
        [failure] if failure in {"ruff_check", "ruff_format"} else []
    )
    pytest_call = next(
        (step for step, diagnostic in calls if step.name == "pytest"),
        None,
    )
    if "pytest" in expected:
        assert pytest_call is not None
        assert pytest_call.argv[3:6] == (
            "tests/shared.py",
            "tests/first.py",
            "tests/second.py",
        )
    ruff_call = next(step for step, diagnostic in calls if step.name == "ruff_check")
    assert ruff_call.argv[5:] == ("shared.py", "first.py", "second.py", "third.py")
    names = ["first", "second", "third"]
    static_failed = failure in {"git_diff_check", "ruff_check", "ruff_format"}
    assert authorities == ([] if static_failed else names)
    report = json.loads(report_path.read_text())
    assert report["kind"] == "source_gate_batch"
    assert report["checkpoints"] == names
    assert report["phase"] == "all"
    assert report["source_before"] == report["source_after"] == _clean_source()
    assert report["identity_stable"] is True
    assert report["authority_failures"] == dict.fromkeys(names, [])
    for spec in specs:
        participant = report["participants"][spec.name]
        assert participant["checkpoint"] == spec.name
        assert participant["batch_report"] == str(report_path)
        assert participant["tests"] == list(spec.tests)
        assert participant["ruff_paths"] == list(spec.ruff_paths)
        assert participant["tests_covered"] and participant["ruff_paths_covered"]
        assert participant["authority_status"] == (
            "NOT_RUN" if static_failed else "PASS"
        )
        assert participant["status"] == ("PASS" if passed else "FAIL")
    for field in (
        "production_effects",
        "scheduler_mutation",
        "provider_effects",
        "broker_live_effects",
    ):
        assert report[field] == "NOT_RUN"
    assert not list(report_path.parent.glob("*/pytest"))


@pytest.mark.parametrize("exception", [False, True])
def test_batch_authority_failure_attribution_and_continuation(
    tmp_path, monkeypatch, exception
):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    calls = []
    specs = _batch_specs(calls, authority_failure=True, authority_exception=exception)
    monkeypatch.setattr(runner, "_git_state", lambda repo: _clean_source())
    monkeypatch.setattr(
        runner, "_execute_step", lambda step, **kw: _outcome(step.name, 0)
    )
    passed, path = runner.verify_batch(
        specs, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
    )
    assert not passed
    assert calls == ["first", "second", "third"]
    report = json.loads(path.read_text())
    assert report["authority_failures"]["first"] == []
    assert report["authority_failures"]["second"]
    assert report["authority_failures"]["third"] == []
    assert all(command["name"] != "pytest" for command in report["commands"])
    assert report["participants"]["first"]["status"] == "PASS"
    assert report["participants"]["second"]["status"] == "FAIL"
    assert report["status"] == "FAIL"


@pytest.mark.parametrize(
    "drift", [{"head": "c" * 40}, {"tree": "d" * 40}, {"porcelain": " M changed.py"}]
)
def test_batch_source_drift_fails(tmp_path, monkeypatch, drift):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    states = iter(
        [
            _clean_source(),
            _clean_source(),
            _clean_source(),
            {**_clean_source(), **drift},
        ]
    )
    monkeypatch.setattr(runner, "_git_state", lambda repo: next(states))
    monkeypatch.setattr(
        runner, "_execute_step", lambda step, **kw: _outcome(step.name, 0)
    )
    passed, path = runner.verify_batch(
        _batch_specs([]), repo_root=tmp_path, evidence_root=tmp_path / "evidence"
    )
    assert not passed
    report = json.loads(path.read_text())
    assert not report["identity_stable"]
    assert all(p["status"] == "FAIL" for p in report["participants"].values())


def test_batch_dirty_source_rejected_before_commands_or_authority(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    calls = []
    monkeypatch.setattr(
        runner,
        "_git_state",
        lambda repo: {**_clean_source(), "porcelain": "?? unknown"},
    )
    monkeypatch.setattr(
        runner, "_execute_step", lambda *a, **kw: pytest.fail("command ran")
    )
    with pytest.raises(RuntimeError, match="clean worktree"):
        runner.verify_batch(
            _batch_specs(calls), repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    assert calls == []
    assert not (tmp_path / "evidence").exists()


@pytest.mark.parametrize(
    "arguments",
    [[], ["unknown"], ["arch128-r4", "arch128-r4"], ["arch128-r4", "--execute"]],
)
def test_batch_cli_rejects_invalid_selection(monkeypatch, arguments):
    monkeypatch.setattr(
        runner, "verify_batch", lambda *a, **kw: pytest.fail("batch ran")
    )
    with pytest.raises(SystemExit) as error:
        runner.main(["verify-batch", *arguments])
    assert error.value.code == 2


def test_batch_cli_preserves_order_and_single_verify_dispatch(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(
        runner,
        "verify_batch",
        lambda specs, **kw: (seen.extend(s.name for s in specs) or True, tmp_path),
    )
    assert runner.main(["verify-batch", "arch128-r6", "arch128-r4"]) == 0
    assert seen == ["arch128-r6", "arch128-r4"]
    monkeypatch.setattr(
        runner,
        "verify_checkpoint",
        lambda spec, **kw: (seen.append(spec.name) or True, tmp_path),
    )
    assert runner.main(["verify", "arch128-r4"]) == 0
    assert seen[-1] == "arch128-r4"


def test_single_verify_report_and_command_selection_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda repo: _clean_source())
    calls = []

    def execute(step, **kw):
        calls.append(step)
        return _outcome(step.name, 0)

    monkeypatch.setattr(runner, "_execute_step", execute)
    passed, path = runner.verify_checkpoint(
        _spec(), repo_root=tmp_path, evidence_root=tmp_path / "evidence"
    )
    assert passed
    report = json.loads(path.read_text())
    assert report["kind"] == "source_gate" and report["checkpoint"] == "example"
    assert report["started_from"] == report["finished_at"] == _clean_source()
    assert "participants" not in report
    pytest_call = next(step for step in calls if step.name == "pytest")
    assert pytest_call.argv[3] == _spec().tests[0]
    assert [step.name for step in calls] == [
        "git_diff_check",
        "ruff_check",
        "ruff_format",
        "pytest",
    ]


@pytest.mark.parametrize("options", [("check", "--no-cache"), ("format", "--diff")])
def test_oversized_windows_ruff_command_preserves_every_path(options):
    prefix = (r"C:\Program Files\Python314\python.exe", "-m", "ruff", *options)
    paths = tuple(
        f"tests/{index}/{'😀' * 15} a checkpoint module.py" for index in range(600)
    )
    commands = runner._windows_ruff_commands((*prefix, *paths))
    assert len(commands) > 1
    assert all(command[: len(prefix)] == prefix for command in commands)
    assert (
        tuple(path for command in commands for path in command[len(prefix) :]) == paths
    )
    assert all(
        len(subprocess.list2cmdline(command).encode("utf-16-le")) // 2 < 32_767
        for command in commands
    )
    short = (*prefix, paths[0])
    assert runner._windows_ruff_commands(short) == (short,)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows subprocess batching")
def test_execute_step_preserves_ruff_batch_failure_and_output(tmp_path, monkeypatch):
    prefix = ("python", "-m", "ruff", "check", "--no-cache")
    paths = tuple(f"tests/{index:03d}.py" for index in range(20))
    monkeypatch.setattr(runner, "_WINDOWS_RUFF_COMMAND_BUDGET", 100)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, int(len(calls) == 2), b"out\n", b"")

    monkeypatch.setattr(runner.subprocess, "run", run)
    step = runner.Step("ruff_check", (*prefix, *paths))
    outcome = runner._execute_step(
        step, repo_root=tmp_path, command_dir=tmp_path, index=1
    )
    assert len(calls) > 2
    assert tuple(path for call in calls for path in call[len(prefix) :]) == paths
    assert outcome.exit_code == 1
    assert Path(outcome.stdout_path).read_bytes() == b"out\n" * len(calls)


@pytest.mark.parametrize("diagnostic", [False, True])
@pytest.mark.parametrize("elapsed", [0.0, 1234567890.25])
def test_r2a_command_elapsed_uses_monotonic_and_preserves_stdout(
    tmp_path, monkeypatch, diagnostic, elapsed
):
    ticks = iter([7.0, 7.0 + elapsed])
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks))
    step = runner.Step("pytest", ("python", "-m", "pytest"), ("diagnostic",))
    stdout = b"100 slowest durations\n12.00s call tests/example.py::test_example\n"
    monkeypatch.setenv(runner.SOURCE_GATE_PHASE_ENV, "tests")
    monkeypatch.setenv(runner.SOURCE_GATE_SHARD_INDEX_ENV, "2")
    monkeypatch.setenv(runner.SOURCE_GATE_SHARD_COUNT_ENV, "4")
    monkeypatch.setenv("CHECKPOINT_RUNNER_KEEP_ME", "present")
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout, b"")

    monkeypatch.setattr(runner.subprocess, "run", run)
    outcome = runner._execute_step(
        step,
        repo_root=tmp_path,
        command_dir=tmp_path,
        index=1,
        diagnostic=diagnostic,
    )
    assert outcome.elapsed_seconds == elapsed
    assert outcome.elapsed_seconds >= 0
    assert outcome.exit_code == 0
    assert Path(outcome.stdout_path).read_bytes() == stdout
    assert len(calls) == 1
    call_argv, kwargs = calls[0]
    assert call_argv == (step.diagnostic_argv if diagnostic else step.argv)
    assert kwargs["cwd"] == tmp_path
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    environment = kwargs["env"]
    assert environment["CHECKPOINT_RUNNER_KEEP_ME"] == "present"
    assert runner.SOURCE_GATE_PHASE_ENV not in environment
    assert runner.SOURCE_GATE_SHARD_INDEX_ENV not in environment
    assert runner.SOURCE_GATE_SHARD_COUNT_ENV not in environment


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("elapsed", [0.0, 1234567890.25])
@pytest.mark.parametrize("exit_code", [0, 1])
def test_r2a_elapsed_is_additive_report_evidence_without_status_threshold(
    tmp_path, monkeypatch, batch, elapsed, exit_code
):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda repo: _clean_source())
    monkeypatch.setattr(
        runner,
        "_execute_step",
        lambda step, **kw: replace(
            _outcome(step.name, exit_code), elapsed_seconds=elapsed
        ),
    )
    if batch:
        passed, path = runner.verify_batch(
            [_spec()], repo_root=tmp_path, evidence_root=tmp_path
        )
    else:
        passed, path = runner.verify_checkpoint(
            _spec(), repo_root=tmp_path, evidence_root=tmp_path
        )
    assert passed == (exit_code == 0)
    report = json.loads(path.read_text())
    assert report["schema"] == runner.SCHEMA
    assert report["identity_stable"] is True
    assert report["status"] == ("PASS" if exit_code == 0 else "FAIL")
    assert all(command["elapsed_seconds"] == elapsed for command in report["commands"])


def test_r2a_pytest_top_100_duration_flags_are_exact_and_diagnostic_only(tmp_path):
    steps = runner.build_verification_steps(
        _spec(), python_executable="python", basetemp=tmp_path
    )
    pytest_step = next(step for step in steps if step.name == "pytest")
    argv = pytest_step.argv
    assert tuple(arg for arg in argv if arg.startswith("--durations")) == (
        "--durations=100",
        "--durations-min=0.0",
    )
    assert pytest_step.diagnostic_argv is None
    assert all(
        not any(arg.startswith("--durations") for arg in step.argv)
        for step in steps
        if step.name != "pytest"
    )


def test_r2b_common_and_family_requirements_are_independently_selectable():
    required_common = {
        "tests/runtime/checkpoint_runner/test_core.py",
        "tests/runtime/checkpoint_runner/test_ci.py",
    }
    assert required_common.issubset(runner.COMMON_TESTS)
    assert len(runner.COMMON_TESTS) == len(set(runner.COMMON_TESTS))
    assert set(runner.COMMON_TESTS).issubset(runner.COMMON_RUFF_PATHS)

    shared_test = "tests/runtime/checkpoint_runner/test_synthetic_shared.py"
    alpha_test = "tests/synthetic_alpha/test_duplicate.py"
    beta_test = "tests/synthetic_beta/test_duplicate.py"
    future_test = "tests/runtime/checkpoint_runner/test_synthetic_future_family.py"
    shared_source = "scripts/synthetic_shared.py"
    alpha_source = "scripts/synthetic_alpha.py"
    beta_source = "scripts/synthetic_beta.py"
    future_source = "scripts/synthetic_future_family.py"

    def family_spec(name, family_tests, family_sources):
        return runner.CheckpointSpec(
            name=name,
            description="synthetic test family",
            tests=(*runner.COMMON_TESTS, *family_tests),
            ruff_paths=(*runner.COMMON_RUFF_PATHS, *family_sources),
            authority_check=lambda _repo: (),
        )

    alpha = family_spec(
        "synthetic-family-alpha",
        (shared_test, alpha_test),
        (shared_source, alpha_source),
    )
    beta = family_spec(
        "synthetic-family-beta",
        (shared_test, beta_test),
        (shared_source, beta_source),
    )
    future = family_spec(
        "synthetic-future-family",
        (future_test,),
        (future_source,),
    )

    requirements = runner.batch_requirements((alpha, beta))
    expected = (
        tuple(
            dict.fromkeys((*runner.COMMON_TESTS, shared_test, alpha_test, beta_test))
        ),
        tuple(
            dict.fromkeys(
                (*runner.COMMON_RUFF_PATHS, shared_source, alpha_source, beta_source)
            )
        ),
    )
    assert requirements == expected
    assert len(requirements[0]) == len(set(requirements[0]))
    assert len(requirements[1]) == len(set(requirements[1]))
    assert requirements[0].index(alpha_test) < requirements[0].index(beta_test)
    assert runner.batch_requirements((alpha, beta)) == requirements
    assert runner.batch_requirements((beta, alpha)) == (
        tuple(
            dict.fromkeys((*runner.COMMON_TESTS, shared_test, beta_test, alpha_test))
        ),
        tuple(
            dict.fromkeys(
                (*runner.COMMON_RUFF_PATHS, shared_source, beta_source, alpha_source)
            )
        ),
    )

    expanded = runner.batch_requirements((alpha, beta, future))
    assert future_test in expanded[0]
    assert future_source in expanded[1]
    assert beta_test in expanded[0]
    assert alpha_test in expanded[0]

    independent = runner.batch_requirements((alpha, future))
    assert future_test in independent[0]
    assert alpha_test in independent[0]
    assert beta_test not in independent[0]
    with pytest.raises(ValueError, match="distinct registered checkpoints"):
        runner.batch_requirements((alpha, replace(beta, name=alpha.name)))


def test_active_and_retained_checkpoint_tests_remain_partitioned():
    registry = runner._checkpoint_specs()
    active, _ = runner.batch_requirements(
        tuple(registry[name] for name in runner.ACTIVE_CI_CHECKPOINTS)
    )
    retained, _ = runner.batch_requirements(
        tuple(registry[name] for name in runner.RETAINED_CHECKPOINTS)
    )
    retained_owner = "tests/runtime/checkpoint_runner/test_retained_arch128_130.py"

    assert retained_owner not in active
    assert retained_owner in retained


def test_source_junit_evidence_is_external_and_additive(tmp_path):
    basetemp = tmp_path / "pytest"
    step = next(
        step
        for step in runner.build_verification_steps(
            _spec(), python_executable="python", basetemp=basetemp
        )
        if step.name == "pytest"
    )
    assert f"--junitxml={tmp_path / 'pytest-results.xml'}" in step.argv
    assert "--durations=100" in step.argv
    assert "--durations-min=0.0" in step.argv


def test_arch144c_source_only_route_authority_and_frozen_v1(
    monkeypatch: pytest.MonkeyPatch,
):
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH144C_NAME]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == runner.ARCH144C_BRANCH
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), spec.remote_branch, "push"
        )
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) is None
    assert runner._batch_workflow_is_reviewed(
        (root / ".github/workflows/checkpoint-source-gates.yml").read_text()
    )
    assert runner._arch144c_authority_check(root) == ()
    for relative, pin in {
        (
            "src/trading_bot/experiments/"
            "research_strategy_paper_candidate_eligibility.py"
        ): ("fd6b0ad650fb3fb97f587deb7cffc7286e685813"),
        (
            "src/trading_bot/experiments/"
            "research_strategy_paper_evidence_verification.py"
        ): ("915bdd84bee3ad0b57efcafb0a78da01fce94e66"),
    }.items():
        assert runner._git_blob_sha1(root / relative) == pin


def test_arch144c_pin_successor_rejects_wrong_predecessor_and_drift(monkeypatch):
    path = "tests/runtime/checkpoint_runner/test_core.py"
    before = runner.ARCH144C_PREDECESSOR_TEST_PINS[path]
    successor = runner._arch134_d1s3_shared_successor_pin(path)
    assert runner._arch144c_current_inventory_test_pin(path, before) == successor
    with pytest.raises(ValueError):
        runner._arch144c_current_inventory_test_pin(path, "a" * 40)
    pins = dict(runner.ARCH144C_TEST_PIN_OVERRIDES)
    pins[path] = "a" * 40
    monkeypatch.setattr(runner, "ARCH144C_TEST_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError):
        runner._arch144c_current_inventory_test_pin(path, before)
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch144c_authority_check(root)


def test_arch145a_source_only_route_is_registered_and_inert(
    monkeypatch: pytest.MonkeyPatch,
):
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH145A_NAME]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == runner.ARCH145A_BRANCH
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), spec.remote_branch, "push"
        )
        is None
    )
    assert runner.ARCH145A_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.resolve_ci_certification_profile(spec.name) is None
    assert runner._arch145a_authority_check(root) == ()
    assert runner.ARCH145A_SOURCE_PINS.keys() == set(runner.ARCH145A_PATHS)


def test_arch134_f1r1_a_source_only_route_is_registered_and_inert(
    monkeypatch: pytest.MonkeyPatch,
):
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH134_F1R1_A_NAME]

    assert runner._arch134_f1r1_a_authority_check(root) == ()
    assert spec.remote_branch == runner.ARCH134_F1R1_A_BRANCH
    assert spec.tests == runner.ARCH134_F1R1_A_TESTS
    assert spec.ruff_paths == runner.ARCH134_F1R1_A_RUFF_PATHS
    assert spec.preflight is None
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert runner.ARCH134_F1R1_A_NAME not in runner.ACTIVE_CI_CHECKPOINTS
    assert runner.ARCH134_F1R1_A_NAME not in runner.CI_CERTIFICATION_PROFILES
    assert set(runner.ARCH134_F1R1_A_SOURCE_PINS) == set(runner.ARCH134_F1R1_A_PATHS)


def test_arch134_f1r1_a_overlays_fail_closed_and_restore_predecessor(
    monkeypatch: pytest.MonkeyPatch,
):
    source_path = "scripts/run_test_certification.py"
    source_predecessor = runner.ARCH134_F1R1_A_PREDECESSOR_SOURCE_PINS[source_path]
    assert (
        runner._arch134_f1r1_a_current_source_pin(source_path, source_predecessor)
        == runner.ARCH134_F1R1_A_SOURCE_PIN_OVERRIDES[source_path]
    )
    assert (
        runner._arch134_f1r1_a_current_source_pin("unrelated.py", "a" * 40) == "a" * 40
    )
    with pytest.raises(ValueError, match="134-F1R1-A"):
        runner._arch134_f1r1_a_current_source_pin(source_path, "a" * 40)

    for mutation in ("missing", "extra", "wrong"):
        pins = dict(runner.ARCH134_F1R1_A_SOURCE_PIN_OVERRIDES)
        if mutation == "missing":
            pins.pop(source_path)
        elif mutation == "extra":
            pins["extra.py"] = "b" * 40
        else:
            pins[source_path] = "b" * 40
        monkeypatch.setattr(runner, "ARCH134_F1R1_A_SOURCE_PIN_OVERRIDES", pins)
        with pytest.raises(ValueError, match="134-F1R1-A"):
            runner._arch134_f1r1_a_current_source_pin(source_path, source_predecessor)
        monkeypatch.undo()

    test_path = "tests/scripts/certification_runner/test_profiles.py"
    test_predecessor = runner.ARCH134_F1R1_A_PREDECESSOR_TEST_PINS[test_path]
    for mutation in ("missing", "extra", "wrong"):
        pins = dict(runner.ARCH134_F1R1_A_TEST_PIN_OVERRIDES)
        if mutation == "missing":
            pins.pop(test_path)
        elif mutation == "extra":
            pins["tests/extra.py"] = "b" * 40
        else:
            pins[test_path] = "b" * 40
        monkeypatch.setattr(runner, "ARCH134_F1R1_A_TEST_PIN_OVERRIDES", pins)
        with pytest.raises(ValueError, match="134-F1R1-A"):
            runner._arch134_f1r1_a_current_inventory_test_pin(
                test_path, test_predecessor
            )
        monkeypatch.undo()


def test_arch145a_d1r6_workflow_successor_is_exact_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
):
    root = Path(runner.__file__).resolve().parents[1]
    path = root / runner.ARCH145A_D1R6_WORKFLOW_PATH
    # Retain the historical 145 proof against its exact accepted C2 successor.
    # R3M's current workflow is independently pinned and verified below.
    accepted = subprocess.run(
        [
            "git",
            "show",
            "6906ba01bfb6a353029d695e584b2097587b81b9:"
            + runner.ARCH145A_D1R6_WORKFLOW_PATH,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    data = accepted.encode("utf-8")
    assert (
        hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        == runner.ARCH132_R3M_BLOB_PREDECESSORS[runner.ARCH145A_D1R6_WORKFLOW_PATH]
    )
    current = accepted.replace(
        "              arch146-a-historical-research-dataset-enforcement \x60\n", ""
    )
    # C1's independently pinned dependency step is additive to this old proof.
    marker = "      - name: Install FULL optimizer dependency\n"
    added = current.partition(marker)[2].partition(
        "      - name: Run canonical certification profile\n"
    )[0]
    current = current.replace(marker + added, "", 1)
    predecessor = subprocess.run(
        [
            "git",
            "show",
            "c9b9fe92997f015c3b392fdcbb15d4ff1d1db63b:.github/workflows/"
            "checkpoint-source-gates.yml",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert current == predecessor.replace(
        '      - "feature/robinhood-*"\n',
        '      - "feature/robinhood-*"\n      - "feature/research-*"\n',
    ).replace(
        "              arch134-d1r5-pre-market-wake-qualification `\n",
        "              arch134-f1r1-b-host-qualification `\n"
        "              arch134-d1r5-pre-market-wake-qualification `\n",
    ).replace(
        "              arch134-f1r1-b-host-qualification `\n",
        "              arch134-f1r1-c1-qualification-operator `\n"
        "              arch134-f1r1-b-host-qualification `\n",
    ).replace(
        "              arch134-f1r1-c1-qualification-operator `\n",
        "              arch134-f1r1-d1s1-successor-soak-source `\n"
        "              arch134-f1r1-c1-qualification-operator `\n",
    ).replace(
        "              arch134-f1r1-d1s1-successor-soak-source `\n",
        "              arch134-f1r1-d1s2-successor-installed-readiness `\n"
        "              arch134-f1r1-d1s1-successor-soak-source `\n",
    ).replace(
        "              arch133-robinhood-supervised-release-installation-operator `\n",
        "              arch134-f1r1-d1s3-successor-release-installation-operator `\n"
        "              arch133-robinhood-supervised-release-installation-operator `\n",
    ).replace(
        "              arch134-f1r1-d1s2-successor-installed-readiness `\n",
        "              arch134-f1r1-d1s3-r5-successor-release-publication-recovery `\n"
        "              arch134-f1r1-d1s2-successor-installed-readiness `\n",
    ).replace(
        "              arch134-f1r1-d1s3-r5-successor-release-publication-recovery `\n",
        "              arch134-f1r1-d1s4-fresh-successor-source `\n"
        "              arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery `\n"
        "              arch134-f1r1-d1s4-rename-free-direct-installation `\n"
        "              arch134-f1r1-d1s3-r5-successor-release-publication-recovery `\n",
    )
    # Current authority includes the independently tested additive registration.
    current = path.read_text(encoding="utf-8")
    assert runner._arch134_current_batch_workflow_is_reviewed(current)
    assert "pull_request:" in current
    assert "workflow_dispatch:" in current
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in current
    assert "cancel-in-progress: true" in current
    assert "shard: [0, 1, 2, 3]" in current
    assert current.count("  source-gates:\n") == 1
    assert "feature/robinhood-*" in current
    assert "feature/test-suite-*" in current
    from scripts import source_authority

    candidate = runner._arch134_d1s3_shared_successor_pin(
        runner.ARCH145A_D1R6_WORKFLOW_PATH
    )
    assert source_authority.blob_matches(root, path, candidate)
    assert (
        runner._arch145a_d1r6_workflow_successor(
            runner.ARCH145A_D1R6_WORKFLOW_PREDECESSOR_BLOB_SHA1,
            candidate,
        )
        == candidate
    )
    with pytest.raises(ValueError, match="145-A D1R6"):
        runner._arch145a_d1r6_workflow_successor("a" * 40, candidate)
    with pytest.raises(ValueError, match="145-A D1R6"):
        runner._arch145a_d1r6_workflow_successor(
            runner.ARCH145A_D1R6_WORKFLOW_PREDECESSOR_BLOB_SHA1,
            "a" * 40,
        )
    without_research = current.replace('      - "feature/research-*"\n', "")
    extra_branch = current.replace(
        '      - "feature/research-*"\n',
        '      - "feature/research-*"\n      - "feature/unreviewed-*"\n',
    )
    for mutated in (without_research, extra_branch):
        raw = mutated.encode("utf-8")
        mutated_blob = hashlib.sha1(
            b"blob " + str(len(raw)).encode("ascii") + bytes((0,)) + raw
        ).hexdigest()
        with pytest.raises(ValueError, match="145-A D1R6"):
            runner._arch145a_d1r6_workflow_successor(
                runner.ARCH145A_D1R6_WORKFLOW_PREDECESSOR_BLOB_SHA1,
                mutated_blob,
            )
    assert runner._arch134_d1r6_authority_check(root) == ()
    assert runner._arch145a_authority_check(root) == ()


def test_arch145a_successors_preserve_predecessors_and_resolve_all_consumers(
    monkeypatch: pytest.MonkeyPatch,
):
    root = Path(runner.__file__).resolve().parents[1]
    digest = lambda value: hashlib.sha256(  # noqa: E731
        json.dumps(value, sort_keys=True).encode()
    ).hexdigest()

    assert (
        digest(
            [
                runner.ARCH144C_PREDECESSOR_TEST_PINS,
                runner.ARCH144C_TEST_PIN_OVERRIDES,
            ]
        )
        == runner.ARCH144C_TEST_PINS_SHA256
    )
    assert (
        runner._arch145a_predecessor_active_checkpoint_inventory()
        == (runner.ACTIVE_CI_CHECKPOINTS[2:])
    )
    assert runner._arch144c_authority_check(root) == ()
    assert runner._arch134_f1_authority_check(root) == ()
    for check in (
        runner._arch134_armed_paper_authority_check,
        runner._arch134_production_paper_runtime_authority_check,
        runner._arch134_runtime_acl_authority_check,
    ):
        assert check(root) == ()


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "wrong_blob",
        "malformed_blob",
        "digest",
        "predecessor",
        "predecessor_material",
    ],
)
def test_arch145a_test_successor_overlay_fails_closed(
    monkeypatch: pytest.MonkeyPatch, mutation: str
):
    path = "tests/runtime/checkpoint_runner/test_core.py"
    predecessor = runner.ARCH145A_PREDECESSOR_TEST_PINS[path]
    pins = dict(runner.ARCH145A_TEST_PIN_OVERRIDES)
    if mutation == "missing":
        pins.pop(path)
    elif mutation == "extra":
        pins["tests/domain/test_market.py"] = "a" * 40
    elif mutation == "wrong_blob":
        pins[path] = "a" * 40
    elif mutation == "malformed_blob":
        pins[path] = None
    elif mutation == "digest":
        monkeypatch.setattr(runner, "ARCH145A_TEST_PIN_OVERRIDES_SHA256", "a" * 64)
    elif mutation == "predecessor":
        predecessor = "a" * 40
    else:
        prior = dict(runner.ARCH144C_TEST_PIN_OVERRIDES)
        prior[path] = "a" * 40
        monkeypatch.setattr(runner, "ARCH144C_TEST_PIN_OVERRIDES", prior)
    monkeypatch.setattr(runner, "ARCH145A_TEST_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError, match="145-A"):
        runner._arch145a_current_inventory_test_pin(path, predecessor)


def test_arch145a_source_successor_rejects_missing_or_extra_paths(
    monkeypatch: pytest.MonkeyPatch,
):
    path = "scripts/run_test_certification.py"
    predecessor = runner.ARCH145A_PREDECESSOR_SOURCE_PINS[path]
    for mutation in ("missing", "extra"):
        pins = dict(runner.ARCH145A_SOURCE_PIN_OVERRIDES)
        if mutation == "missing":
            pins.pop(path)
        else:
            pins["tests/domain/test_market.py"] = "a" * 40
        monkeypatch.setattr(runner, "ARCH145A_SOURCE_PIN_OVERRIDES", pins)
        with pytest.raises(ValueError, match="145-A"):
            runner._arch145a_current_source_pin(path, predecessor)
        monkeypatch.undo()


def test_arch145a_successor_removal_restores_predecessor_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    root = Path(runner.__file__).resolve().parents[1]
    monkeypatch.setattr(runner, "ARCH145A_TEST_PIN_OVERRIDES", {})
    assert runner._arch144c_authority_check(root)


def test_arch134_f1r1_b_registration_and_active_successor_are_source_only(
    monkeypatch: pytest.MonkeyPatch,
):
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH134_F1R1_B_NAME]

    assert runner._arch134_f1r1_b_authority_check(root) == ()
    assert spec.remote_branch == runner.ARCH134_F1R1_B_BRANCH
    assert spec.tests == runner.ARCH134_F1R1_B_TESTS
    assert spec.ruff_paths == runner.ARCH134_F1R1_B_RUFF_PATHS
    assert spec.preflight is None
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert runner.CI_CERTIFICATION_PROFILES[runner.ARCH134_F1R1_B_NAME] == ("robinhood")
    assert (
        runner._arch145a_predecessor_active_checkpoint_inventory()
        == (runner.ACTIVE_CI_CHECKPOINTS[2:])
    )


@pytest.mark.parametrize("kind", ["source", "test"])
def test_arch134_f1r1_b_overlay_rejects_wrong_predecessor_or_shape(
    monkeypatch: pytest.MonkeyPatch, kind: str
):
    if kind == "source":
        path = "scripts/run_test_certification.py"
        before_name = "ARCH134_F1R1_B_PREDECESSOR_SOURCE_PINS"
        after_name = "ARCH134_F1R1_B_SOURCE_PIN_OVERRIDES"
        resolver = runner._arch134_f1r1_b_current_source_pin
    else:
        path = "tests/runtime/checkpoint_runner/test_core.py"
        before_name = "ARCH134_F1R1_B_PREDECESSOR_TEST_PINS"
        after_name = "ARCH134_F1R1_B_TEST_PIN_OVERRIDES"
        resolver = runner._arch134_f1r1_b_current_inventory_test_pin

    before = getattr(runner, before_name)
    after = dict(getattr(runner, after_name))
    with pytest.raises(ValueError, match="134-F1R1-B"):
        resolver(path, "a" * 40)

    after.pop(path)
    monkeypatch.setattr(runner, after_name, after)
    with pytest.raises(ValueError, match="134-F1R1-B"):
        resolver(path, before[path])


def test_h_p_compact_fixtures_preserve_exact_source_ast_and_tuple_anchors(tmp_path):
    from .helpers import _copy_local_authority

    root = Path(runner.__file__).resolve().parents[1]
    original = (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    fixture_root = _copy_local_authority(tmp_path, {})
    compact = (fixture_root / "scripts/checkpoint_runner.py").read_text(
        encoding="utf-8"
    )
    old_tree, new_tree = ast.parse(original), ast.parse(compact)
    expected = {
        "ACTIVE_CI_CHECKPOINTS",
        "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH",
        "ARCH145A_PREDECESSOR_ACTIVE_CI_CHECKPOINTS",
    }
    for name in expected:
        before = next(
            n
            for n in old_tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == name
        )
        after = next(
            n
            for n in new_tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == name
        )
        assert ast.dump(before) == ast.dump(after)
    before = next(
        n
        for n in old_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_checkpoint_specs"
    )
    after = next(
        n
        for n in new_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_checkpoint_specs"
    )
    assert ast.dump(before) == ast.dump(after)
    assert compact.count('    "arch133-robinhood-unattended-host-publication",\n') == 2
    assert len(compact) < len(original) // 3


def test_source_pytest_scratch_is_short_unique_and_external(tmp_path):
    first = runner._source_pytest_basetemp(tmp_path / "short")
    second = runner._source_pytest_basetemp(tmp_path / "short")
    assert first != second
    assert first.parent == second.parent == tmp_path / "short"
    assert first.name.startswith("source-") and len(first.name) == 39
    assert not first.exists() and not second.exists()
    with pytest.raises(RuntimeError, match="external"):
        runner._source_pytest_basetemp(Path(runner.__file__).resolve().parents[1])


def test_source_junit_evidence_is_separate_from_short_scratch(tmp_path):
    scratch = runner._source_pytest_basetemp(tmp_path / "short")
    evidence = tmp_path / ("evidence-" + "x" * 100) / "pytest-results.xml"
    step = next(
        s
        for s in runner.build_verification_steps(
            _spec(), python_executable="python", basetemp=scratch, junitxml=evidence
        )
        if s.name == "pytest"
    )
    assert f"--basetemp={scratch}" in step.argv
    assert f"--junitxml={evidence}" in step.argv
    assert scratch.parent != evidence.parent


@pytest.mark.parametrize("batch", [False, True])
def test_both_source_gate_paths_use_short_scratch_with_deep_evidence(
    tmp_path, monkeypatch, batch
):
    monkeypatch.setattr(
        current_source_authority, "current_authority_check", lambda _: ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda _: _clean_source())
    monkeypatch.setenv(runner.SOURCE_GATE_PHASE_ENV, "tests")
    scratch = tmp_path / "short" / "fresh-guid"
    monkeypatch.setattr(runner, "_source_pytest_basetemp", lambda: scratch)
    steps = []
    monkeypatch.setattr(
        runner,
        "_execute_step",
        lambda step, **kw: steps.append(step) or _outcome(step.name, 0),
    )
    root = tmp_path / ("evidence-" + "x" * 100)
    if batch:
        passed, report = runner.verify_batch(
            [_spec()], repo_root=tmp_path, evidence_root=root
        )
    else:
        passed, report = runner.verify_checkpoint(
            _spec(), repo_root=tmp_path, evidence_root=root
        )
    assert passed
    step = next(s for s in steps if s.name == "pytest")
    assert f"--basetemp={scratch}" in step.argv
    assert f"--junitxml={report.parent / 'pytest-results.xml'}" in step.argv


def test_source_scratch_collision_preserves_existing_directory(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(runner, "uuid4", lambda: SimpleNamespace(hex="0" * 32))
    existing = tmp_path / ("source-" + "0" * 32)
    existing.mkdir()
    marker = existing / "preserved.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(RuntimeError, match="already exists"):
        runner._source_pytest_basetemp(tmp_path)
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_r3_dispatch_preserves_r2_fresh_evidence_gate_structurally():
    tree = ast.parse(runner.Path(runner.__file__).read_text())
    nodes = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    old = ast.dump(nodes["_arch134_readonly_diagnostic_r2_preflight_checkpoint"])
    new = ast.dump(nodes["_arch134_readonly_diagnostic_r3_preflight_checkpoint"])
    expected = (
        old.replace("diagnostic_r2", "diagnostic_r3")
        .replace("DIAGNOSTIC_R2", "DIAGNOSTIC_R3")
        .replace(
            "Name(id='_readonly_preflight_checkpoint'",
            "Name(id='_arch134_readonly_diagnostic_r2_preflight_checkpoint'",
        )
    )
    assert new == expected


def test_b1_is_exact_source_only_full_mapping():
    root = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[runner.ARCH146B1_NAME]
    assert spec.preflight is None and spec.execute is None
    assert (
        runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), runner.ARCH146B1_BRANCH, "push"
        )
        is None
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "full"
    # B1 remains a strict historical source contract, but is no longer a
    # current route or current-product success prerequisite.
    assert spec.name not in current_source_authority.develop_static_checkpoints(root)
    workflow = (root / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert runner._arch134_current_batch_workflow_is_reviewed(workflow)
    assert spec.name not in workflow


def test_b1_rejects_protected_dispatch_or_mapping_drift(monkeypatch):
    root = Path(runner.__file__).resolve().parents[1]
    specs = runner._checkpoint_specs()
    specs[runner.ARCH146B1_NAME] = replace(
        specs[runner.ARCH146B1_NAME], execute=lambda: {}
    )
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "146-B1 source-only registration drift" in runner._arch146b1_authority_check(
        root
    )


def test_no_b2_operator_dispatch_is_registered():
    assert not any(name.startswith("arch146-b2") for name in runner._checkpoint_specs())
