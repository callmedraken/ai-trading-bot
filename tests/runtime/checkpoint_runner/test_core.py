from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner

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
        "arch128-r5-substrate",
        "arch128-r5-trading",
        "arch128-r6",
        "arch128-r7",
        "arch128-r8",
        "arch128-r8-terminal-halt",
        "arch130-r8i-d1",
        "arch131-robinhood-review-paper",
        "arch131-robinhood-mcp-schema",
        "arch131-robinhood-paper-cycle",
        "arch131-robinhood-performance",
        "arch131-robinhood-direct-mcp",
        "arch131-robinhood-oauth-windows",
        "arch131-robinhood-agentic-account",
        "arch131-robinhood-paper-operator",
        "arch131-robinhood-paper-intent-bridge",
        "arch131-robinhood-deterministic-paper-pipeline",
        "arch131-robinhood-virtual-risk-context",
        "arch131-robinhood-forward-paper-cycle",
        "arch131-robinhood-live-qualification-verifier",
        "arch131-robinhood-session-admission",
        "arch131-robinhood-risk-price-snapshot",
        "arch131-robinhood-forward-paper-preview",
        "arch131-robinhood-risk-price-acquisition",
        "arch131-robinhood-supervised-forward-paper",
        "arch131-robinhood-supervised-prepare-qualification",
        "arch131-robinhood-supervised-prepare-verifier",
        "arch131-nyse-published-regular-session-authority",
        "arch131-robinhood-published-session-prepare",
        "arch131-robinhood-published-prepare-operator",
        "arch131-robinhood-supervised-qualification",
        "arch133-robinhood-unattended-activation-core",
        "arch133-robinhood-unattended-state-store",
        "arch133-robinhood-unattended-one-wake-composition",
        "arch133-robinhood-unattended-review-paper-execution",
        "arch133-robinhood-unattended-host-scheduler-surface",
        "arch133-robinhood-unattended-host-bootstrap",
        "arch133-robinhood-unattended-host-publication",
        "arch133-robinhood-scratch-root-acl-qualification",
        "arch133-robinhood-retained-root-diagnostic",
        "arch133-robinhood-retained-root-acl-recovery",
        "arch133-robinhood-post-publication-verifier",
        "arch133-robinhood-post-publication-stage-diagnostic",
        "arch133-robinhood-publication-state-paper-diagnostic",
        "arch133-robinhood-publication-state-paper-corrected",
        "arch133-robinhood-single-session-scheduler-installation",
        "arch133-robinhood-fresh-activation-reprovision",
        "arch133-robinhood-reprovision-admission-diagnostic",
        "arch133-robinhood-reprovision-parent-security-diagnostic",
    }
    for spec in specs.values():
        assert "tests/runtime/checkpoint_runner/test_core.py" in spec.tests
        assert "scripts/checkpoint_runner.py" in spec.ruff_paths
        assert "tests/runtime/checkpoint_runner/test_core.py" in spec.ruff_paths
        expected_branch = (
            "feature/robinhood-review-paper-side-foundation"
            if spec.name
            in {
                "arch131-robinhood-live-qualification-verifier",
                "arch131-robinhood-session-admission",
                "arch131-robinhood-risk-price-snapshot",
                "arch131-robinhood-forward-paper-preview",
                "arch131-robinhood-risk-price-acquisition",
                "arch131-robinhood-supervised-forward-paper",
                "arch131-robinhood-supervised-prepare-qualification",
                "arch131-robinhood-supervised-prepare-verifier",
                "arch131-nyse-published-regular-session-authority",
                "arch131-robinhood-published-session-prepare",
                "arch131-robinhood-published-prepare-operator",
                "arch131-robinhood-supervised-qualification",
            }
            else (
                "feature/robinhood-review-paper-mode"
                if spec.name
                in {
                    "arch131-robinhood-review-paper",
                    "arch131-robinhood-mcp-schema",
                    "arch131-robinhood-paper-cycle",
                    "arch131-robinhood-performance",
                    "arch131-robinhood-direct-mcp",
                    "arch131-robinhood-oauth-windows",
                    "arch131-robinhood-agentic-account",
                    "arch131-robinhood-paper-operator",
                    "arch131-robinhood-paper-intent-bridge",
                    "arch131-robinhood-deterministic-paper-pipeline",
                    "arch131-robinhood-virtual-risk-context",
                    "arch131-robinhood-forward-paper-cycle",
                }
                else (
                    "feature/d10c-r8-incident-reconciliation"
                    if spec.name == "arch130-r8i-d1"
                    else (
                        "feature/d10c-r8-terminal-halt"
                        if spec.name == "arch128-r8-terminal-halt"
                        else "feature/d10c-durable-wake-evidence"
                    )
                )
            )
        )
        if spec.name == "arch133-robinhood-unattended-activation-core":
            expected_branch = "feature/robinhood-unattended-review-paper-133a"
        if spec.name == "arch133-robinhood-unattended-state-store":
            expected_branch = "feature/robinhood-unattended-review-paper-133b"
        if spec.name == "arch133-robinhood-unattended-one-wake-composition":
            expected_branch = "feature/robinhood-unattended-review-paper-133c"
        if spec.name == "arch133-robinhood-unattended-review-paper-execution":
            expected_branch = "feature/robinhood-unattended-review-paper-133d"
        if spec.name == "arch133-robinhood-unattended-host-scheduler-surface":
            expected_branch = "feature/robinhood-unattended-review-paper-133e"
        if spec.name == "arch133-robinhood-unattended-host-bootstrap":
            expected_branch = "feature/robinhood-unattended-review-paper-133g"
        if spec.name == "arch133-robinhood-unattended-host-publication":
            expected_branch = "feature/robinhood-unattended-review-paper-133h"
        if spec.name == "arch133-robinhood-scratch-root-acl-qualification":
            expected_branch = "feature/robinhood-unattended-review-paper-133i"
        if spec.name == "arch133-robinhood-retained-root-diagnostic":
            expected_branch = "feature/robinhood-unattended-review-paper-133j"
        if spec.name == "arch133-robinhood-retained-root-acl-recovery":
            expected_branch = "feature/robinhood-unattended-review-paper-133k"
        if spec.name == "arch133-robinhood-post-publication-verifier":
            expected_branch = "feature/robinhood-unattended-review-paper-133l"
        if spec.name == "arch133-robinhood-post-publication-stage-diagnostic":
            expected_branch = "feature/robinhood-unattended-review-paper-133m"
        if spec.name == "arch133-robinhood-publication-state-paper-diagnostic":
            expected_branch = "feature/robinhood-unattended-review-paper-133n"
        if spec.name == "arch133-robinhood-publication-state-paper-corrected":
            expected_branch = "feature/robinhood-unattended-review-paper-133o"
        if spec.name == "arch133-robinhood-single-session-scheduler-installation":
            expected_branch = "feature/robinhood-unattended-review-paper-133p"
        if spec.name == "arch133-robinhood-fresh-activation-reprovision":
            expected_branch = "feature/robinhood-unattended-review-paper-133q"
        if spec.name == "arch133-robinhood-reprovision-admission-diagnostic":
            expected_branch = "feature/robinhood-unattended-review-paper-133r"
        if spec.name == "arch133-robinhood-reprovision-parent-security-diagnostic":
            expected_branch = "feature/robinhood-unattended-review-paper-133s"
        assert spec.remote_branch == expected_branch

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
    assert specs["arch131-robinhood-review-paper"].preflight is None
    assert specs["arch131-robinhood-review-paper"].execute is None
    assert specs["arch131-robinhood-mcp-schema"].preflight is None
    assert specs["arch131-robinhood-mcp-schema"].execute is None
    assert specs["arch131-robinhood-paper-cycle"].preflight is None
    assert specs["arch131-robinhood-paper-cycle"].execute is None
    assert specs["arch131-robinhood-performance"].preflight is None
    assert specs["arch131-robinhood-performance"].execute is None
    assert specs["arch131-robinhood-direct-mcp"].preflight is None
    assert specs["arch131-robinhood-direct-mcp"].execute is None
    assert specs["arch128-r5-substrate"].remote_head_env is None
    assert (
        specs["arch128-r5-trading"].remote_head_env == runner.R5_TRADING_REMOTE_HEAD_ENV
    )


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


@pytest.mark.parametrize(
    "failure", [None, "pytest", "ruff_check", "ruff_format", "git_diff_check"]
)
def test_batch_shares_commands_preserves_order_and_collects_authorities(
    tmp_path,
    monkeypatch,
    failure,
):
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
    assert [step.name for step, diagnostic in calls if not diagnostic] == [
        "pytest",
        "ruff_check",
        "ruff_format",
        "git_diff_check",
    ]
    assert [step.name for step, diagnostic in calls if diagnostic] == (
        [failure] if failure in {"ruff_check", "ruff_format"} else []
    )
    assert calls[0][0].argv[3:6] == (
        "tests/shared.py",
        "tests/first.py",
        "tests/second.py",
    )
    assert calls[1][0].argv[5:] == ("shared.py", "first.py", "second.py", "third.py")
    assert authorities == ["first", "second", "third"]
    report = json.loads(report_path.read_text())
    assert report["kind"] == "source_gate_batch"
    assert report["checkpoints"] == authorities
    assert report["source_before"] == report["source_after"] == _clean_source()
    assert report["identity_stable"] is True
    assert report["authority_failures"] == dict.fromkeys(authorities, [])
    for spec in specs:
        participant = report["participants"][spec.name]
        assert participant["checkpoint"] == spec.name
        assert participant["batch_report"] == str(report_path)
        assert participant["tests"] == list(spec.tests)
        assert participant["ruff_paths"] == list(spec.ruff_paths)
        assert participant["tests_covered"] and participant["ruff_paths_covered"]
        assert participant["authority_status"] == "PASS"
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
    assert report["participants"]["first"]["status"] == "PASS"
    assert report["participants"]["second"]["status"] == "FAIL"
    assert report["status"] == "FAIL"


@pytest.mark.parametrize(
    "drift", [{"head": "c" * 40}, {"tree": "d" * 40}, {"porcelain": " M changed.py"}]
)
def test_batch_source_drift_fails(tmp_path, monkeypatch, drift):
    states = iter([_clean_source(), {**_clean_source(), **drift}])
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
    assert calls[0].argv[3] == _spec().tests[0]
    assert [step.name for step in calls] == [
        "pytest",
        "ruff_check",
        "ruff_format",
        "git_diff_check",
    ]


@pytest.mark.parametrize("diagnostic", [False, True])
@pytest.mark.parametrize("elapsed", [0.0, 1234567890.25])
def test_r2a_command_elapsed_uses_monotonic_and_preserves_stdout(
    tmp_path, monkeypatch, diagnostic, elapsed
):
    ticks = iter([7.0, 7.0 + elapsed])
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks))
    step = runner.Step("pytest", ("python", "-m", "pytest"), ("diagnostic",))
    stdout = b"100 slowest durations\n12.00s call tests/example.py::test_example\n"
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
    assert calls == [
        (
            step.diagnostic_argv if diagnostic else step.argv,
            {"cwd": tmp_path, "capture_output": True, "check": False},
        )
    ]


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("elapsed", [0.0, 1234567890.25])
@pytest.mark.parametrize("exit_code", [0, 1])
def test_r2a_elapsed_is_additive_report_evidence_without_status_threshold(
    tmp_path, monkeypatch, batch, elapsed, exit_code
):
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
    argv = steps[0].argv
    assert tuple(arg for arg in argv if arg.startswith("--durations")) == (
        "--durations=100",
        "--durations-min=0.0",
    )
    assert steps[0].diagnostic_argv is None
    assert all(
        not any(arg.startswith("--durations") for arg in step.argv)
        for step in steps[1:]
    )


def test_r2b_common_and_family_requirements_are_independently_selectable():
    assert runner.COMMON_TESTS == (
        "tests/runtime/checkpoint_runner/test_core.py",
        "tests/runtime/checkpoint_runner/test_ci.py",
    )
    registry = runner._checkpoint_specs()
    for name, spec in registry.items():
        if name.startswith("arch131-"):
            module = "test_arch131.py"
        elif name.startswith("arch133-"):
            letter = spec.remote_branch[-1]
            module = (
                "test_arch133_a_g.py"
                if letter <= "g"
                else "test_arch133_h_k.py"
                if letter <= "k"
                else "test_arch133_l_m.py"
            )
        else:
            module = "test_retained_arch128_130.py"
        selected = tuple(
            path
            for path in spec.tests
            if path.startswith("tests/runtime/checkpoint_runner/")
        )
        assert selected == (
            *runner.COMMON_TESTS,
            "tests/runtime/checkpoint_runner/" + module,
        )
        assert set(selected) <= set(spec.ruff_paths)
        certification = tuple(
            path
            for path in spec.tests
            if path.startswith("tests/scripts/certification_runner/")
        )
        assert certification in [
            (),
            ("tests/scripts/certification_runner/test_profiles.py",),
        ]
    active, _ = runner.batch_requirements(
        [registry[name] for name in runner.ACTIVE_CI_CHECKPOINTS]
    )
    retained, _ = runner.batch_requirements(
        [registry[name] for name in runner.RETAINED_CHECKPOINTS]
    )
    assert "tests/runtime/checkpoint_runner/test_retained_arch128_130.py" not in active
    assert "tests/runtime/checkpoint_runner/test_retained_arch128_130.py" in retained
    assert not any(
        "test_arch" in path for path in retained if "/checkpoint_runner/" in path
    )


def test_source_junit_evidence_is_external_and_additive(tmp_path):
    basetemp = tmp_path / "pytest"
    step = runner.build_verification_steps(
        _spec(), python_executable="python", basetemp=basetemp
    )[0]
    assert f"--junitxml={tmp_path / 'pytest-results.xml'}" in step.argv
    assert "--durations=100" in step.argv
    assert "--durations-min=0.0" in step.argv
