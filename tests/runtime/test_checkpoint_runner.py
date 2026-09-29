from __future__ import annotations

from pathlib import Path

from scripts import checkpoint_runner as runner


def _spec() -> runner.CheckpointSpec:
    return runner.CheckpointSpec(
        name="example",
        description="example",
        tests=("tests/runtime/test_checkpoint_runner.py",),
        ruff_paths=(
            "scripts/checkpoint_runner.py",
            "tests/runtime/test_checkpoint_runner.py",
        ),
        authority_check=lambda repo: (),
    )


def _outcome(name: str, exit_code: int) -> runner.CommandOutcome:
    return runner.CommandOutcome(
        name=name,
        argv=("tool", name),
        exit_code=exit_code,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_sha256="0" * 64,
        stderr_sha256="0" * 64,
        stdout_path="stdout",
        stderr_path="stderr",
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
        "pytest",
        "ruff_check",
        "ruff_format",
        "git_diff_check",
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
        ("pytest", False),
        ("ruff_check", False),
        ("ruff_check", True),
        ("ruff_format", False),
        ("git_diff_check", False),
    ]
    assert tuple(outcome.name for outcome in outcomes) == (
        "pytest",
        "ruff_check",
        "ruff_check_diagnostic",
        "ruff_format",
        "git_diff_check",
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
        ("pytest", False),
        ("ruff_check", False),
        ("ruff_check", True),
        ("ruff_format", False),
        ("ruff_format", True),
        ("git_diff_check", False),
    ]


def test_registered_profiles_include_current_arch128_gates() -> None:
    specs = runner._checkpoint_specs()

    assert set(specs) == {
        "arch128-parent-acl-repair",
        "arch128-r4",
    }
    for spec in specs.values():
        assert "tests/runtime/test_checkpoint_runner.py" in spec.tests
        assert "scripts/checkpoint_runner.py" in spec.ruff_paths
        assert "tests/runtime/test_checkpoint_runner.py" in spec.ruff_paths


def test_current_arch128_authority_profiles_pass() -> None:
    repo_root = Path(runner.__file__).resolve().parent.parent
    specs = runner._checkpoint_specs()

    assert specs["arch128-parent-acl-repair"].authority_check(repo_root) == ()
    assert specs["arch128-r4"].authority_check(repo_root) == ()


def test_default_evidence_root_is_outside_repo() -> None:
    repo_root = Path(runner.__file__).resolve().parent.parent
    evidence_root = runner._default_evidence_root(repo_root)

    assert evidence_root != repo_root
    assert repo_root not in evidence_root.parents
