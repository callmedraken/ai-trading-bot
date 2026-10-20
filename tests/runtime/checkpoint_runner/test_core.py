from __future__ import annotations

import ast
import hashlib
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


def test_registered_profiles_include_current_arch128_gates() -> None:
    specs = runner._checkpoint_specs()

    assert set(specs) == {
        "arch133-robinhood-supervised-release-installation-operator",
        "arch133-robinhood-supervised-release-publication-recovery",
        "arch133-robinhood-supervised-release-installation-reconciliation",
        "arch133-robinhood-supervised-deployment-qualification",
        "arch133-robinhood-supervised-runtime-host-admission",
        "arch133-robinhood-supervised-maintenance-rebind",
        "arch133-robinhood-supervised-release-installation",
        "arch133-robinhood-supervised-release-build-verification",
        "arch133-robinhood-supervised-release-foundation",
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
        "arch133-robinhood-reprovision-parent-policy-diagnostic",
        "arch133-robinhood-fresh-activation-reprovision-corrected",
        "arch133-robinhood-reprovision-indeterminate-reconciliation",
        "arch133-robinhood-reprovision-sealed-predecessor-recovery",
        "arch133-robinhood-reprovision-recovery-reconciliation",
        "arch133-robinhood-windows-rename-qualification",
        "arch133-robinhood-closed-descendant-rename-qualification",
        "arch134-production-strategy-contract",
        "arch134-production-strategy-decision",
        "arch134-production-strategy-live-paper",
        "arch134-armed-paper-mvp",
        "arch134-production-paper-runtime",
        "arch134-production-paper-runtime-acl",
        "arch144-c-f1-paper-evidence-admission",
        "arch134-f2-five-session-soak-readiness",
        "arch134-f1-five-session-soak",
        "arch134-d1r8-d1-session-execution-consumer",
        "arch134-d1r7-d1-session-authorization",
        "arch134-d1r6-overnight-wake-arming",
        "arch134-d1r5-pre-market-wake-qualification",
        "arch134-alpaca-authentication-qualification",
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
        if spec.name == "arch133-robinhood-reprovision-parent-policy-diagnostic":
            expected_branch = "feature/robinhood-unattended-review-paper-133t"
        if spec.name == "arch133-robinhood-fresh-activation-reprovision-corrected":
            expected_branch = "feature/robinhood-unattended-review-paper-133u"
        if spec.name == "arch133-robinhood-reprovision-indeterminate-reconciliation":
            expected_branch = "feature/robinhood-unattended-review-paper-133v"
        if spec.name == "arch133-robinhood-reprovision-sealed-predecessor-recovery":
            expected_branch = "feature/robinhood-unattended-review-paper-133w"
        if spec.name == "arch133-robinhood-reprovision-recovery-reconciliation":
            expected_branch = "feature/robinhood-unattended-review-paper-133x"
        if spec.name == "arch133-robinhood-windows-rename-qualification":
            expected_branch = "feature/robinhood-unattended-review-paper-133y"
        if spec.name == "arch133-robinhood-closed-descendant-rename-qualification":
            expected_branch = "feature/robinhood-unattended-review-paper-133z"
        if spec.name == "arch133-robinhood-supervised-release-foundation":
            expected_branch = "feature/robinhood-supervised-release-foundation"
        if spec.name == "arch133-robinhood-supervised-release-build-verification":
            expected_branch = "feature/robinhood-supervised-release-build-verification"
        if spec.name == "arch133-robinhood-supervised-release-installation":
            expected_branch = "feature/robinhood-supervised-release-installation"
        if spec.name == "arch133-robinhood-supervised-runtime-host-admission":
            expected_branch = "feature/robinhood-supervised-runtime-host-admission"
        if spec.name == "arch133-robinhood-supervised-deployment-qualification":
            expected_branch = "feature/robinhood-supervised-deployment-qualification"
        if spec.name == "arch133-robinhood-supervised-maintenance-rebind":
            expected_branch = "feature/robinhood-supervised-maintenance-rebind"
        if spec.name == "arch133-robinhood-supervised-release-publication-recovery":
            expected_branch = (
                "feature/robinhood-supervised-release-publication-recovery"
            )
        if spec.name == "arch133-robinhood-supervised-release-installation-operator":
            expected_branch = (
                "feature/robinhood-supervised-release-installation-operator"
            )
        if (
            spec.name
            == "arch133-robinhood-supervised-release-installation-reconciliation"
        ):
            expected_branch = (
                "feature/robinhood-supervised-release-installation-reconciliation"
            )
        if spec.name == "arch134-production-strategy-contract":
            expected_branch = "feature/robinhood-production-strategy-contract"
        if spec.name == "arch134-production-strategy-decision":
            expected_branch = "feature/robinhood-production-strategy-decision"
        if spec.name == "arch134-production-strategy-live-paper":
            expected_branch = "feature/robinhood-production-strategy-live-paper"
        if spec.name == "arch134-armed-paper-mvp":
            expected_branch = "feature/robinhood-production-paper-mvp"
        if spec.name == "arch134-production-paper-runtime":
            expected_branch = "feature/robinhood-production-paper-history-recovery"
        if spec.name == "arch134-production-paper-runtime-acl":
            expected_branch = "feature/robinhood-production-paper-runtime-acl"
        if spec.name == "arch134-alpaca-authentication-qualification":
            expected_branch = (
                "feature/robinhood-production-paper-alpaca-auth-qualification"
            )
        if spec.name == "arch144-c-f1-paper-evidence-admission":
            expected_branch = runner.ARCH144C_BRANCH
        if spec.name == "arch134-f2-five-session-soak-readiness":
            expected_branch = runner.ARCH134_F2_BRANCH
        if spec.name == "arch134-f1-five-session-soak":
            expected_branch = runner.ARCH134_F1_BRANCH
        if spec.name == "arch134-d1r8-d1-session-execution-consumer":
            expected_branch = "feature/robinhood-production-paper-d1-session-execution"
        if spec.name == "arch134-d1r7-d1-session-authorization":
            expected_branch = (
                "feature/robinhood-production-paper-d1-session-authorization"
            )
        if spec.name == "arch134-d1r6-overnight-wake-arming":
            expected_branch = "feature/robinhood-production-paper-overnight-wake-arming"
        if spec.name == "arch134-d1r5-pre-market-wake-qualification":
            expected_branch = (
                "feature/robinhood-production-paper-premarket-wake-qualification"
            )
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
    # Reconstruct the exact GUI-A14 parent tuple: only historical AJ is retired.
    active = tuple(
        name
        for name in runner.ACTIVE_CI_CHECKPOINTS
        if name
        not in {
            runner.ARCH134_AUTH_NAME,
            runner.ARCH134_D1R5_NAME,
            runner.ARCH134_D1R6_NAME,
            runner.ARCH134_D1R7_NAME,
            runner.ARCH134_D1R8_NAME,
            runner.ARCH134_F1_NAME,
            runner.ARCH144C_NAME,
            runner.ARCH134_F2_NAME,
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
    pytest_call = next(step for step in calls if step.name == "pytest")
    assert pytest_call.argv[3] == _spec().tests[0]
    assert [step.name for step in calls] == [
        "git_diff_check",
        "ruff_check",
        "ruff_format",
        "pytest",
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
        expected = (
            runner.COMMON_TESTS
            if name
            in {
                "arch133-robinhood-supervised-release-installation-operator",
                "arch133-robinhood-supervised-release-publication-recovery",
                "arch133-robinhood-supervised-release-installation-reconciliation",
                "arch133-robinhood-supervised-deployment-qualification",
                "arch133-robinhood-supervised-release-foundation",
                "arch133-robinhood-supervised-runtime-host-admission",
                "arch133-robinhood-supervised-maintenance-rebind",
                "arch133-robinhood-supervised-release-installation",
                "arch133-robinhood-supervised-release-build-verification",
                "arch134-production-strategy-contract",
                "arch134-production-strategy-decision",
                "arch134-production-strategy-live-paper",
                "arch134-armed-paper-mvp",
                "arch134-production-paper-runtime",
                "arch134-production-paper-runtime-acl",
                "arch144-c-f1-paper-evidence-admission",
                "arch134-f2-five-session-soak-readiness",
                "arch134-f1-five-session-soak",
                "arch134-d1r8-d1-session-execution-consumer",
                "arch134-d1r7-d1-session-authorization",
                "arch134-d1r6-overnight-wake-arming",
                "arch134-d1r5-pre-market-wake-qualification",
                "arch134-alpaca-authentication-qualification",
            }
            else (
                *runner.COMMON_TESTS,
                "tests/runtime/checkpoint_runner/" + module,
            )
        )
        assert selected == expected
        assert set(selected) <= set(spec.ruff_paths)
        certification = tuple(
            path
            for path in spec.tests
            if path.startswith("tests/scripts/certification_runner/")
        )
        assert certification in [
            (),
            ("tests/scripts/certification_runner/test_profiles.py",),
            (
                "tests/scripts/certification_runner/test_profiles.py",
                "tests/scripts/certification_runner/test_lanes.py",
            ),
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


def test_arch144c_source_only_route_authority_and_frozen_v1():
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
    after = runner.ARCH144C_TEST_PIN_OVERRIDES[path]
    assert runner._arch144c_current_inventory_test_pin(
        path, before
    ) == runner.ARCH134_F2_PIN_OVERRIDES.get(path, after)
    with pytest.raises(ValueError):
        runner._arch144c_current_inventory_test_pin(path, "a" * 40)
    pins = dict(runner.ARCH144C_TEST_PIN_OVERRIDES)
    pins[path] = "a" * 40
    monkeypatch.setattr(runner, "ARCH144C_TEST_PIN_OVERRIDES", pins)
    with pytest.raises(ValueError):
        runner._arch144c_current_inventory_test_pin(path, before)
    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch144c_authority_check(root)
