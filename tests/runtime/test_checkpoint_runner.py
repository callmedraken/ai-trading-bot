from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

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
    }
    for spec in specs.values():
        assert "tests/runtime/test_checkpoint_runner.py" in spec.tests
        assert "scripts/checkpoint_runner.py" in spec.ruff_paths
        assert "tests/runtime/test_checkpoint_runner.py" in spec.ruff_paths
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


def test_current_arch128_authority_profiles_pass() -> None:
    repo_root = Path(runner.__file__).resolve().parent.parent
    specs = runner._checkpoint_specs()

    assert specs["arch128-parent-acl-repair"].authority_check(repo_root) == ()
    assert specs["arch128-r4"].authority_check(repo_root) == ()
    assert specs["arch128-r5-substrate"].authority_check(repo_root) == ()
    assert specs["arch128-r5-trading"].authority_check(repo_root) == ()
    assert specs["arch128-r6"].authority_check(repo_root) == ()
    assert specs["arch128-r7"].authority_check(repo_root) == ()
    assert specs["arch128-r8"].authority_check(repo_root) == ()
    assert specs["arch130-r8i-d1"].authority_check(repo_root) == ()
    assert specs["arch131-robinhood-review-paper"].authority_check(repo_root) == ()
    assert specs["arch131-robinhood-mcp-schema"].authority_check(repo_root) == ()
    assert specs["arch131-robinhood-paper-cycle"].authority_check(repo_root) == ()
    assert specs["arch131-robinhood-performance"].authority_check(repo_root) == ()
    assert specs["arch131-robinhood-direct-mcp"].authority_check(repo_root) == ()


def test_default_evidence_root_is_outside_repo() -> None:
    repo_root = Path(runner.__file__).resolve().parent.parent
    evidence_root = runner._default_evidence_root(repo_root)

    assert evidence_root != repo_root
    assert repo_root not in evidence_root.parents


def _parent_preflight_result(status: str = "PASS") -> dict[str, object]:
    return {
        "status": status,
        "acl_mutation": "NOT_RUN",
        "recursive_acl_mutation": "NOT_RUN",
        "d10_child_mutation": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "activation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }


def _r4_preflight_result(
    *,
    status: str = "PASS",
    detail: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "production_filesystem_mutation": "NOT_RUN",
        "rename_1": "NOT_RUN",
        "rename_2": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "activation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }
    if detail is not None:
        result["detail"] = detail
    return result


def test_parent_preflight_uses_read_only_operator(
    monkeypatch,
) -> None:
    from scripts import d10_arch128_parent_acl_repair as repair

    monkeypatch.setattr(repair, "_read_only", lambda: _parent_preflight_result())

    result = runner._parent_acl_preflight()

    assert result["status"] == "PASS"
    assert result["primary"]["acl_mutation"] == "NOT_RUN"
    assert result["diagnostics"] == {}


def test_parent_execute_delegates_through_existing_interlock(
    monkeypatch,
) -> None:
    from scripts import d10_arch128_parent_acl_repair as repair

    monkeypatch.delenv(repair.AUTH_ENV, raising=False)
    monkeypatch.setattr(
        repair,
        "_repair_once",
        lambda: (_ for _ in ()).throw(AssertionError("repair called")),
    )

    result = runner._parent_acl_execute()

    assert result["status"] == "BLOCKED"
    assert result["primary"]["reason"] == "authorization_interlock_not_exact"
    assert result["effect_disposition"] == "NOT_STARTED"


def test_parent_execute_rejects_forbidden_side_effect_evidence(
    monkeypatch,
) -> None:
    from scripts import d10_arch128_parent_acl_repair as repair

    result = _parent_preflight_result()
    result["status"] = "PASS"
    result["acl_mutation"] = "EXACT_PARENT_POLICY_APPLIED_AND_VERIFIED"
    result["scheduler_mutation"] = "MUTATED"
    monkeypatch.setattr(repair, "_dispatch", lambda *args, **kwargs: result)

    try:
        runner._parent_acl_execute()
    except RuntimeError as exc:
        assert "scheduler_mutation" in str(exc)
    else:
        raise AssertionError("unexpected protected side effect was accepted")


def test_r4_execute_delegates_through_existing_interlock(
    monkeypatch,
) -> None:
    from scripts import d10_arch128_r4_operator as operator

    monkeypatch.delenv(operator.AUTH_ENV, raising=False)
    monkeypatch.setattr(
        operator,
        "_execute_once",
        lambda: (_ for _ in ()).throw(AssertionError("R4 execute called")),
    )

    result = runner._r4_execute()

    assert result["status"] == "BLOCKED"
    assert result["primary"]["reason"] == "authorization_interlock_not_exact"
    assert result["effect_disposition"] == "NOT_STARTED"


def test_r4_execute_accepts_exact_complete_result(
    monkeypatch,
) -> None:
    from scripts import d10_arch128_r4_operator as operator

    primary = _r4_preflight_result()
    primary.update(
        {
            "status": "PASS",
            "production_filesystem_mutation": "REPLACEMENT_COMPLETE_AND_VERIFIED",
            "rename_1": "SUCCESS",
            "rename_2": "SUCCESS",
        }
    )
    monkeypatch.setattr(operator, "_dispatch", lambda *args, **kwargs: primary)

    result = runner._r4_execute()

    assert result["status"] == "PASS"
    assert result["effect_disposition"] == "CONFIRMED"


def test_r4_execute_marks_indeterminate_effect_conservatively(
    monkeypatch,
) -> None:
    from scripts import d10_arch128_r4_operator as operator

    primary = _r4_preflight_result(status="STOPPED_INDETERMINATE")
    primary.update(
        {
            "production_filesystem_mutation": "STAGING_CREATED_AND_VERIFIED",
            "rename_1": "INDETERMINATE",
            "rename_2": "NOT_CALLED",
        }
    )
    monkeypatch.setattr(operator, "_dispatch", lambda *args, **kwargs: primary)

    result = runner._r4_execute()

    assert result["status"] == "STOPPED_INDETERMINATE"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"


def test_r4_execute_rejects_forbidden_side_effect_evidence(
    monkeypatch,
) -> None:
    from scripts import d10_arch128_r4_operator as operator

    primary = _r4_preflight_result()
    primary.update(
        {
            "status": "PASS",
            "production_filesystem_mutation": "REPLACEMENT_COMPLETE_AND_VERIFIED",
            "rename_1": "SUCCESS",
            "rename_2": "SUCCESS",
            "scheduler_mutation": "MUTATED",
        }
    )
    monkeypatch.setattr(operator, "_dispatch", lambda *args, **kwargs: primary)

    try:
        runner._r4_execute()
    except RuntimeError as exc:
        assert "scheduler_mutation" in str(exc)
    else:
        raise AssertionError("unexpected R4 side effect was accepted")


def test_r4_preflight_attaches_parent_acl_diagnostic(
    monkeypatch,
) -> None:
    from scripts import d10_arch128_parent_acl_repair as repair
    from scripts import d10_arch128_r4_operator as operator

    monkeypatch.setattr(
        operator,
        "_read_only_preflight",
        lambda: _r4_preflight_result(
            status="BLOCKED",
            detail="d10_parent_policy_mismatch",
        ),
    )
    monkeypatch.setattr(
        repair,
        "_read_only",
        lambda: {
            **_parent_preflight_result(),
            "drift_state": "EXACT_DIAGNOSED_THREE_ACE_STATE",
        },
    )

    result = runner._r4_preflight()

    assert result["status"] == "BLOCKED"
    assert result["diagnostics"]["parent_acl"]["status"] == "PASS"
    assert (
        result["diagnostics"]["parent_acl"]["drift_state"]
        == "EXACT_DIAGNOSED_THREE_ACE_STATE"
    )


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


def test_r5_substrate_preflight_requires_exact_pid_interlock(
    monkeypatch,
) -> None:
    monkeypatch.delenv(runner.R5_TRADING_PID_ENV, raising=False)

    result = runner._r5_substrate_preflight()

    assert result["status"] == "BLOCKED"
    assert result["primary"]["reason"] == "trading_pid_interlock_not_exact"
    assert result["primary"]["source_launch"] == "NOT_RUN"


def test_r5_trading_preflight_uses_fixed_production_command(
    monkeypatch,
) -> None:
    observed: dict[str, object] = {}
    payload = {
        "status": "PASS",
        "activation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "scheduler": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
        "second_stage_launch_trap": "NOT_CALLED",
    }

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(payload).encode("utf-8"),
            b"",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner._r5_trading_preflight()

    command = observed["command"]
    assert command[:6] == (
        str(runner.R5_PRODUCTION_PYTHON),
        "-I",
        "-S",
        "-B",
        "-X",
        f"pycache_prefix={runner.R5_PYCACHE_PREFIX}",
    )
    assert result["status"] == "PASS"
    assert result["primary"]["source_launch"] == "NOT_RUN"


def test_r7_preflight_delegates_to_read_only_admission(monkeypatch) -> None:
    from scripts import d10_arch128_r7_readonly as admission

    primary = admission._base()
    primary.update(
        status="PASS",
        canonical_deployment="NEW_EXACT_AND_VERIFIED",
        evidence_root="EXACT_EMPTY_AND_VERIFIED",
        activation_lease="FINAL_INSTALLING_TMP_ABSENT_AND_VERIFIED",
        scheduler="EXACT_DISABLED_NONRUNNING_AND_VERIFIED",
    )
    monkeypatch.setattr(admission, "preflight", lambda: primary)

    result = runner._r7_preflight()

    assert result["status"] == "PASS"
    assert result["primary"] is primary


def test_r7_preflight_rejects_effect_evidence(monkeypatch) -> None:
    from scripts import d10_arch128_r7_readonly as admission

    primary = admission._base()
    primary.update(status="PASS", scheduler_mutation="MUTATED")
    monkeypatch.setattr(admission, "preflight", lambda: primary)

    try:
        runner._r7_preflight()
    except RuntimeError as exc:
        assert "scheduler_mutation" in str(exc)
    else:
        raise AssertionError("R7 read-only gate accepted effect evidence")


def test_r7_registration_preserves_source_and_preflight_profiles() -> None:
    specs = runner._checkpoint_specs()

    assert specs["arch128-r7"].preflight is runner._r7_preflight
    assert specs["arch128-r7"].execute is runner._r7_execute

    assert specs["arch128-r7"].authority_check is runner._r7_authority_check
    assert specs["arch128-r7"].remote_branch == "feature/d10c-durable-wake-evidence"
    assert specs["arch128-r7"].remote_head_env is None
    assert specs["arch128-r7"].tests == (
        *runner.COMMON_TESTS,
        "tests/runtime/test_d10_arch128_r7_readonly.py",
        "tests/runtime/test_d10_arch128_r7_protected.py",
        "tests/runtime/test_d10_arch128_r7_windows.py",
        "tests/runtime/test_d10_python_substrate_windows.py",
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
        "tests/runtime/test_d10_activation_scheduler_operator.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r3_preflight.py",
    )
    parser = runner._parser(specs)
    for command in ("verify", "preflight", "execute"):
        assert parser.parse_args((command, "arch128-r7")).checkpoint == "arch128-r7"


def _r7_result(status: str = "PASS") -> dict[str, object]:
    from scripts import d10_arch128_r7_protected as protected

    result = protected._base()
    if status == "PASS":
        result.update(
            status="PASS",
            stage="COMPLETE",
            authorization="ACCEPTED",
            evidence_provision="CALL_RETURNED",
            scheduler_mutation="CALL_RETURNED",
            lease_publication="PUBLISHED_VERIFIED",
        )
    return result


@pytest.mark.parametrize(
    "authorization", (None, "", "wrong", "ARCH128_R7_PROTECTED_ACTIVATION_AUTHORIZED ")
)
def test_r7_execute_missing_exact_authorization_never_constructs_host(
    monkeypatch,
    authorization,
) -> None:
    from scripts import d10_arch128_r7_protected as protected
    from scripts import d10_arch128_r7_windows as windows

    monkeypatch.delenv(protected.AUTH_ENV, raising=False)
    if authorization is not None:
        monkeypatch.setenv(protected.AUTH_ENV, authorization)
    calls = []

    def forbidden_factory():
        calls.append("factory")
        raise AssertionError("R7C host must remain unconstructed")

    monkeypatch.setattr(windows, "host_factory", forbidden_factory)
    result = runner._r7_execute()
    assert result["status"] == "BLOCKED"
    assert result["effect_disposition"] == "NOT_STARTED"
    assert result["primary"]["authorization"] == "NOT_ACCEPTED"
    assert calls == []


def test_r7_execute_exact_dispatch_composition_and_pass(monkeypatch) -> None:
    from scripts import d10_arch128_r7_protected as protected
    from scripts import d10_arch128_r7_windows as windows

    primary = _r7_result()
    calls = []
    monkeypatch.setenv(protected.AUTH_ENV, protected.AUTH_VALUE)
    monkeypatch.setenv(windows.TRADING_PID_ENV, "unchanged-pid-hint")

    def dispatch(argv, environment, factory):
        calls.append((argv, environment, factory))
        return primary

    monkeypatch.setattr(protected, "_dispatch", dispatch)
    result = runner._r7_execute()
    assert len(calls) == 1
    argv, environment, factory = calls[0]
    assert argv == ("--execute-reviewed-r7-protected-activation",)
    assert environment[protected.AUTH_ENV] == protected.AUTH_VALUE
    assert environment[windows.TRADING_PID_ENV] == "unchanged-pid-hint"
    assert environment == dict(runner.os.environ)
    assert factory is windows.host_factory
    assert result == {
        "status": "PASS",
        "primary": primary,
        "effect_disposition": "CONFIRMED",
    }


@pytest.mark.parametrize(
    "field",
    (
        "evidence_provision",
        "scheduler_mutation",
        "lease_publication",
    ),
)
@pytest.mark.parametrize(
    "mutation",
    (
        "ATTEMPTED",
        "CALL_RETURNED",
        "INDETERMINATE",
        "PUBLISHED_VERIFIED",
        "UNKNOWN",
    ),
)
def test_r7_execute_possible_mutation_is_conservative(
    monkeypatch,
    field,
    mutation,
) -> None:
    from scripts import d10_arch128_r7_protected as protected

    primary = _r7_result("BLOCKED")
    primary[field] = mutation
    monkeypatch.setattr(protected, "_dispatch", lambda *args: primary)
    assert runner._r7_execute()["effect_disposition"] == "MAY_HAVE_OCCURRED"


@pytest.mark.parametrize(
    "changes",
    (
        {"status": "STOPPED"},
        {"status": "INDETERMINATE"},
        {"status": "UNKNOWN"},
        {"status": None},
        {"authorization": "ACCEPTED"},
        {"authorization": "UNKNOWN"},
        {"stage": "UNKNOWN"},
        {"reconciliation_required": True},
    ),
)
def test_r7_execute_unproven_pre_effect_result_is_conservative(
    monkeypatch,
    changes,
) -> None:
    from scripts import d10_arch128_r7_protected as protected

    primary = _r7_result("BLOCKED")
    primary.update(changes)
    monkeypatch.setattr(protected, "_dispatch", lambda *args: primary)
    assert runner._r7_execute()["effect_disposition"] == "MAY_HAVE_OCCURRED"


@pytest.mark.parametrize(
    "field",
    (
        "production_filesystem_mutation",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    ),
)
@pytest.mark.parametrize("status", ("PASS", "BLOCKED"))
def test_r7_execute_rejects_forbidden_effects(monkeypatch, field, status) -> None:
    from scripts import d10_arch128_r7_protected as protected

    primary = _r7_result(status)
    primary[field] = "ATTEMPTED"
    monkeypatch.setattr(protected, "_dispatch", lambda *args: primary)
    with pytest.raises(RuntimeError, match=field):
        runner._r7_execute()


@pytest.mark.parametrize(
    "field",
    (
        "automatic_retry",
        "automatic_rollback",
        "automatic_cleanup",
        "reconciliation_required",
    ),
)
@pytest.mark.parametrize("value", (None, 0, "False", True))
def test_r7_execute_rejects_malformed_pass_recovery_evidence(
    monkeypatch,
    field,
    value,
) -> None:
    from scripts import d10_arch128_r7_protected as protected

    primary = _r7_result()
    primary[field] = value
    monkeypatch.setattr(protected, "_dispatch", lambda *args: primary)
    with pytest.raises(RuntimeError):
        runner._r7_execute()


@pytest.mark.parametrize(
    "field",
    (
        "stage",
        "authorization",
        "evidence_provision",
        "scheduler_mutation",
        "lease_publication",
    ),
)
def test_r7_execute_rejects_incomplete_pass(monkeypatch, field) -> None:
    from scripts import d10_arch128_r7_protected as protected

    primary = _r7_result()
    primary.pop(field)
    monkeypatch.setattr(protected, "_dispatch", lambda *args: primary)
    with pytest.raises(RuntimeError, match="completion evidence"):
        runner._r7_execute()


@pytest.mark.parametrize("primary", (None, [], {}, {"status": "PASS"}))
def test_r7_execute_rejects_malformed_dispatch_result(monkeypatch, primary) -> None:
    from scripts import d10_arch128_r7_protected as protected

    monkeypatch.setattr(protected, "_dispatch", lambda *args: primary)
    with pytest.raises(RuntimeError, match="malformed evidence"):
        runner._r7_execute()


@pytest.mark.parametrize("failure", ("exception", "malformed_pass", "forbidden_effect"))
def test_r7_runner_records_dispatch_failures_as_possible_effect(
    monkeypatch,
    tmp_path,
    failure,
) -> None:
    from scripts import d10_arch128_r7_protected as protected

    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "feature/d10c-durable-wake-evidence",
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda root: state.copy())
    monkeypatch.setattr(runner, "_remote_branch_head", lambda *args: state["head"])
    calls = []

    def dispatch(*args):
        calls.append("dispatch")
        if failure == "exception":
            raise RuntimeError("test-only dispatch exception")
        primary = _r7_result()
        if failure == "malformed_pass":
            primary["lease_publication"] = "INDETERMINATE"
        else:
            primary["broker"] = "ATTEMPTED"
        return primary

    monkeypatch.setattr(protected, "_dispatch", dispatch)
    passed, report_path = runner.execute_checkpoint(
        runner._checkpoint_specs()["arch128-r7"],
        repo_root=tmp_path / "repo",
        evidence_root=tmp_path / "external",
    )
    report = json.loads(report_path.read_text())
    assert not passed
    assert calls == ["dispatch"]
    assert report["status"] == "STOPPED"
    assert report["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert report["automatic_retry"] == "NOT_AUTHORIZED"
    assert report_path.with_name("attempt.json").is_file()


@pytest.mark.parametrize(
    "addition",
    (
        "r7_windows.host_factory()",
        "r7_windows.WindowsR7EvidenceBackend()",
        "r7_windows.WindowsActivationLeaseBackend()",
        "r7_windows.WindowsR7Boundaries(1)",
        "r7_windows._interactive_credential()",
        "r7_windows._scheduler_update(None, None)",
        "CreateFileW()",
        "subprocess.run(['provider'])",
        "guard.main()",
        "retry()",
        "rollback()",
        "cleanup()",
    ),
)
def test_r7d_authority_rejects_direct_host_and_recovery_calls(
    tmp_path,
    addition,
) -> None:
    root = Path(__file__).resolve().parents[2]
    directory = tmp_path / "scripts"
    directory.mkdir()
    for filename in (
        "checkpoint_runner.py",
        "d10_arch128_r7_protected.py",
        "d10_arch128_r7_windows.py",
    ):
        source = (root / "scripts" / filename).read_text(encoding="utf-8")
        if filename == "checkpoint_runner.py":
            source = source.replace(
                "    primary = r7_protected._dispatch(",
                "    " + addition + "\n    primary = r7_protected._dispatch(",
                1,
            )
        (directory / filename).write_text(source, encoding="utf-8")
    assert any("R7D" in failure for failure in runner._r7d_authority_check(tmp_path))


@pytest.mark.parametrize(
    "before,after",
    (
        ("(r7_protected.EXECUTE_FLAG,)", "('--alternate-flag',)"),
        (
            "dict(os.environ),\n        r7_windows.host_factory",
            "{},\n        r7_windows.host_factory",
        ),
        ("execute=_r7_execute,", "execute=_r4_execute,"),
        ('"CALL_RETURNED"', '"ATTEMPTED"'),
        ('disposition = "MAY_HAVE_OCCURRED"', 'disposition = "CONFIRMED"'),
        ('disposition = "NOT_STARTED"', 'disposition = "CONFIRMED"'),
        (
            'primary.get("automatic_retry") is not False',
            'primary.get("automatic_retry") != False',
        ),
        ("ARCH128_R7_PROTECTED_ACTIVATION_AUTHORIZED", "ALTERNATE_AUTHORIZATION"),
        ("AI_TRADING_BOT_ARCH128_R7_TRADING_PID", "ALTERNATE_PID"),
    ),
)
def test_r7d_authority_rejects_composition_or_contract_drift(
    tmp_path,
    before,
    after,
) -> None:
    root = Path(__file__).resolve().parents[2]
    directory = tmp_path / "scripts"
    directory.mkdir()
    for filename in (
        "checkpoint_runner.py",
        "d10_arch128_r7_protected.py",
        "d10_arch128_r7_windows.py",
    ):
        source = (root / "scripts" / filename).read_text(encoding="utf-8")
        source = source.replace(before, after)
        (directory / filename).write_text(source, encoding="utf-8")
    assert runner._r7d_authority_check(tmp_path)


def test_r7d_wrapper_has_no_direct_host_authority() -> None:
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "scripts/checkpoint_runner.py").read_text())
    wrapper = runner._top_level_functions(tree)["_r7_execute"]
    dispatches = [
        node
        for node in ast.walk(wrapper)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "r7_protected._dispatch"
    ]
    assert len(dispatches) == 1
    assert runner._r7d_authority_check(root) == ()


def test_r8_registration_is_read_only() -> None:
    spec = runner._checkpoint_specs()["arch128-r8"]
    assert spec.preflight is runner._r8_preflight
    assert spec.execute is None
    assert spec.authority_check is runner._r8_authority_check
    assert spec.remote_branch == "feature/d10c-durable-wake-evidence"
    assert spec.remote_head_env is None
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/runtime/test_d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_durable_wake_evidence_observe.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_personal_desktop_d10_guard_evidence.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "scripts/d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_arch128_r8_readonly.py",
    )
    parser = runner._parser(runner._checkpoint_specs())
    for command in ("verify", "preflight"):
        assert parser.parse_args((command, "arch128-r8")).checkpoint == "arch128-r8"
    with pytest.raises(SystemExit):
        parser.parse_args(("execute", "arch128-r8"))


@pytest.mark.parametrize("status", ("PASS", "BLOCKED"))
def test_r8_preflight_delegates_once_and_preserves_runner_shape(
    monkeypatch, status
) -> None:
    from scripts import d10_arch128_r8_readonly as admission

    primary = admission._base()
    primary["status"] = status
    calls = []

    def preflight():
        calls.append(())
        return primary

    monkeypatch.setattr(admission, "preflight", preflight)
    assert runner._r8_preflight() == {"status": status, "primary": primary}
    assert calls == [()]


@pytest.mark.parametrize(
    "field",
    (
        "production_filesystem_mutation",
        "evidence_mutation",
        "scheduler_mutation",
        "lease_mutation",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    ),
)
@pytest.mark.parametrize("status", ("PASS", "BLOCKED"))
@pytest.mark.parametrize("drift", ("CALL_RETURNED", None))
def test_r8_runner_independently_rejects_effect_drift(
    monkeypatch, field, status, drift
) -> None:
    from scripts import d10_arch128_r8_readonly as admission

    primary = admission._base()
    primary["status"] = status
    if drift is None:
        del primary[field]
    else:
        primary[field] = drift
    monkeypatch.setattr(admission, "preflight", lambda: primary)
    with pytest.raises(RuntimeError, match=field):
        runner._r8_preflight()


@pytest.mark.parametrize("primary", (None, [], "PASS"))
def test_r8_runner_rejects_malformed_result(monkeypatch, primary) -> None:
    from scripts import d10_arch128_r8_readonly as admission

    monkeypatch.setattr(admission, "preflight", lambda: primary)
    with pytest.raises(RuntimeError, match="exact dictionary"):
        runner._r8_preflight()


def _r8_authority_copy(
    tmp_path: Path,
    *,
    addition: str = "",
    old: str = "",
    new: str = "",
    runner_old: str = "",
    runner_new: str = "",
) -> Path:
    root = Path(runner.__file__).resolve().parent.parent
    target = tmp_path / "scripts"
    target.mkdir()
    source = (root / "scripts/d10_arch128_r8_readonly.py").read_text(encoding="utf-8")
    if old:
        assert old in source
        source = source.replace(old, new, 1)
    if addition:
        source = source.replace(
            "    result = _base()", f"    {addition}\n    result = _base()", 1
        )
    (target / "d10_arch128_r8_readonly.py").write_text(source, encoding="utf-8")
    runner_source = (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    if runner_old:
        assert runner_old in runner_source
        runner_source = runner_source.replace(runner_old, runner_new, 1)
    (target / "checkpoint_runner.py").write_text(runner_source, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    (
        "guard.main()",
        "observer.guard.observe_fixed_d10_durable_wake_evidence()",
        "observer.guard.main()",
        "ctypes.WinDLL('kernel32')",
        "subprocess.run([])",
        "os.system('command')",
        "Popen([])",
        "r7_windows.host_factory()",
        "r7_windows.WindowsR7EvidenceBackend()",
        "r7_windows.WindowsR7Boundaries(1)",
        "r7_windows._interactive_credential()",
        "_update_scheduler()",
        "open('some-file', 'w')",
        "Path('some-file').write_text('data')",
        "Path('some-file').rename('another')",
        "Path('some-file').unlink()",
        "input('credential')",
        "task.Run(None)",
        "task.RegisterTaskDefinition()",
        "provider.capture()",
        "paper_v2.execute()",
        "broker.order()",
        "live.execute()",
    ),
)
def test_r8_authority_rejects_direct_host_or_effect_calls(tmp_path, addition) -> None:
    root = _r8_authority_copy(tmp_path, addition=addition)
    assert runner._r8_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ('"evidence_mutation": "NOT_RUN"', '"evidence_mutation": "CALL_RETURNED"'),
        ("def preflight()", "def preflight(path=None)"),
        ("observation = observer.observe()", "observation = observer.observe(None)"),
        (
            "observation = observer.observe()",
            "observation = observer.observe(); observer.observe()",
        ),
        (
            "from scripts import d10_durable_wake_evidence_observe as observer",
            "from scripts import run_personal_desktop_d10_launch_guard as observer",
        ),
        ("import re", "import re\nimport ctypes"),
        ("import re", "import re\nimport subprocess"),
        ("import re", "import re\nfrom scripts import d10_arch128_r7_windows"),
        (
            "d2071f25-5a7c-5293-a28f-5b722c9917a2",
            "11111111-1111-5111-8111-111111111111",
        ),
        ("3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71", "a" * 64),
        (
            "30e31396-9f51-57ca-a480-d2a3e9cae4a0",
            "22222222-2222-5222-8222-222222222222",
        ),
        ("2026-09-30T22:07:24.000000Z", "2026-09-30T22:07:25.000000Z"),
        ("2026-10-07T22:07:24.000000Z", "2026-10-07T22:07:25.000000Z"),
        (r"F:\AITradingBot\D10\evidence", r"F:\AITradingBot\D10\other"),
        ('observation["record_count"] != 3', 'observation["record_count"] < 3'),
        ('observation["wake_count"] != 1', 'observation["wake_count"] < 1'),
        ('observation["terminal"] is not False', 'observation["terminal"] == True'),
        (
            'observation["terminal_kind"] is not None',
            'observation["terminal_kind"] == "STOPPED"',
        ),
        ('("COMPLETED", "NO_ACTION")', '("COMPLETED", "NO_ACTION", "STOPPED")'),
        (
            'observation["last_stop_reason"] is not None',
            'observation["last_stop_reason"] == "STOPPED"',
        ),
        (
            'observation["last_guard_reason"] is not None',
            'observation["last_guard_reason"] == "STOPPED"',
        ),
    ),
)
def test_r8_authority_freezes_boundary_identity_and_first_wake_policy(
    tmp_path, old, new
) -> None:
    root = _r8_authority_copy(tmp_path, old=old, new=new)
    assert runner._r8_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("preflight=_r8_preflight,", "preflight=_r8_preflight, execute=_r7_execute,"),
        ("preflight=_r8_preflight,", "preflight=_r7_preflight,"),
        (
            "primary = admission.preflight()\n    if type(primary) is not dict:",
            "primary = admission.preflight()\n    guard.main()\n"
            "    if type(primary) is not dict:",
        ),
    ),
)
def test_r8_authority_rejects_execute_registration_and_wrapper_effects(
    tmp_path, old, new
) -> None:
    root = _r8_authority_copy(tmp_path, runner_old=old, runner_new=new)
    assert runner._r8_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1", "wrong-token-target"),
        (
            "AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1",
            "wrong-client-target",
        ),
        ("CRED_TYPE_GENERIC: Final = 1", "CRED_TYPE_GENERIC: Final = 2"),
        ('LOOPBACK_HOST: Final = "127.0.0.1"', 'LOOPBACK_HOST: Final = "0.0.0.0"'),
        ("host=LOOPBACK_HOST", 'host="192.168.1.2"'),
        ("self._api.CredReadW", "self._api.CredEnumerateW"),
        ("_require_target(target)", "pass"),
    ],
)
def test_131f_authority_detects_boundary_drift(tmp_path, before, after):
    repo = Path(runner.__file__).resolve().parent.parent
    relative = Path("src/trading_bot/robinhood_mcp/windows_oauth.py")
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    source = (repo / relative).read_text(encoding="utf-8")
    assert before in source
    destination.write_text(source.replace(before, after), encoding="utf-8")
    script = tmp_path / "scripts/checkpoint_runner.py"
    script.parent.mkdir()
    script.write_bytes((repo / "scripts/checkpoint_runner.py").read_bytes())
    assert runner._arch131_windows_oauth_authority_check(tmp_path)


@pytest.mark.parametrize(
    "addition",
    [
        "import keyring",
        "import os\nvalue = os.getenv('TOKEN')",
        "from pathlib import Path\nPath('tokens').write_text('secret')",
        "value = open('tokens', 'w')",
        "value = native.CredEnumerateW()",
        "def place_equity_order(): pass",
        "tool = 'cancel_equity_order'",
        "import socket\nsocket.socket().bind(('0.0.0.0', 1234))",
    ],
)
def test_131f_authority_rejects_new_effects(tmp_path, addition):
    repo = Path(runner.__file__).resolve().parent.parent
    relative = Path("src/trading_bot/robinhood_mcp/windows_oauth.py")
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    destination.write_text(
        (repo / relative).read_text(encoding="utf-8") + "\n" + addition,
        encoding="utf-8",
    )
    script = tmp_path / "scripts/checkpoint_runner.py"
    script.parent.mkdir()
    script.write_bytes((repo / "scripts/checkpoint_runner.py").read_bytes())
    assert runner._arch131_windows_oauth_authority_check(tmp_path)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131f_authority_rejects_host_registration(tmp_path, capability):
    repo = Path(runner.__file__).resolve().parent.parent
    relative = Path("src/trading_bot/robinhood_mcp/windows_oauth.py")
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    destination.write_bytes((repo / relative).read_bytes())
    script = tmp_path / "scripts/checkpoint_runner.py"
    script.parent.mkdir()
    source = (repo / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    script.write_text(
        source.replace(f"{capability}=None,", f"{capability}=dangerous_host,"),
        encoding="utf-8",
    )
    assert runner._arch131_windows_oauth_authority_check(tmp_path)


def test_131f_source_registration_and_workflow():
    specs = runner._checkpoint_specs()
    spec = specs["arch131-robinhood-oauth-windows"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.index("arch131-robinhood-oauth-windows") > workflow.index(
        "arch131-robinhood-direct-mcp"
    )


def test_131g_source_registration():
    spec = runner._checkpoint_specs()["arch131-robinhood-agentic-account"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert spec.authority_check is runner._arch131_agentic_account_authority_check
    assert {
        "tests/robinhood_mcp/test_account_resolution.py",
        "tests/robinhood_mcp/test_sdk_transport.py",
        "tests/test_robinhood_paper_cycle.py",
    } <= set(spec.tests)
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert "arch131-robinhood-agentic-account" in workflow
    assert workflow.index("arch131-robinhood-agentic-account") > workflow.index(
        "arch131-robinhood-oauth-windows"
    )


@pytest.mark.parametrize(
    "relative,before,after",
    [
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            '    "get_equity_orders",',
            '    "get_accounts",\n    "get_equity_orders",',
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    def _get_accounts(",
            "    def get_accounts(",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    def get_equity_orders(",
            "    def call_tool(",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "tool_name not in _ALLOWED_TOOL_NAMES",
            "False",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    return RobinhoodAgenticAccountResolver(transport._get_accounts)",
            "    return transport._get_accounts",
        ),
        (
            "src/trading_bot/robinhood_mcp/adapter.py",
            "    def get_equity_orders(",
            "    def get_accounts(",
        ),
        (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "class RobinhoodAgenticAccountResolver:",
            "def call_tool(): pass\n\nclass RobinhoodAgenticAccountResolver:",
        ),
        (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "        return eligible[0]",
            "        print(eligible[0])\n        return eligible[0]",
        ),
        (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "        return eligible[0]",
            '        return "rhs_account_number"',
        ),
        (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "        return eligible[0]",
            '        return "place_equity_order"',
        ),
        (
            "src/trading_bot/robinhood_mcp/__init__.py",
            "__all__ = [",
            "def get_accounts(): pass\n\n__all__ = [",
        ),
        (
            "scripts/checkpoint_runner.py",
            "preflight=None,",
            "preflight=dangerous_host,",
        ),
        ("scripts/checkpoint_runner.py", "execute=None,", "execute=dangerous_host,"),
    ],
)
def test_131g_authority_rejects_boundary_drift(tmp_path, relative, before, after):
    repo = Path(runner.__file__).resolve().parent.parent
    paths = (
        "src/trading_bot/robinhood_mcp/sdk_transport.py",
        "src/trading_bot/robinhood_mcp/adapter.py",
        "src/trading_bot/robinhood_mcp/account_resolution.py",
        "src/trading_bot/robinhood_mcp/__init__.py",
        "src/trading_bot/robinhood_paper_cycle.py",
        "scripts/checkpoint_runner.py",
    )
    for path in paths:
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = (repo / path).read_text(encoding="utf-8")
        if path == relative:
            assert before in source
            source = source.replace(before, after)
        destination.write_text(source, encoding="utf-8")
    assert runner._arch131_agentic_account_authority_check(tmp_path)


def test_131h_source_registration_and_workflow():
    spec = runner._checkpoint_specs()["arch131-robinhood-paper-operator"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert spec.authority_check is runner._arch131_paper_operator_authority_check
    assert {
        "tests/test_robinhood_paper_operator.py",
        "tests/test_robinhood_paper_cycle.py",
        "tests/robinhood_mcp/test_account_resolution.py",
        "tests/robinhood_mcp/test_sdk_transport.py",
        "tests/robinhood_mcp/test_windows_oauth.py",
    } <= set(spec.tests)
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.index("arch131-robinhood-paper-operator") > workflow.index(
        "arch131-robinhood-agentic-account"
    )


@pytest.mark.parametrize(
    "relative,before,after",
    [
        (
            "src/trading_bot/robinhood_paper_operator.py",
            '"--porcelain=v1", "--untracked-files=all"',
            '"--porcelain"',
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "with localcontext(_decimal_context()), _suppress_downstream_output():",
            "with localcontext(_decimal_context()):",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "logging.Logger.handle = _discard_log",
            "logging.Logger.handle = previous_handle",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            'open(os.devnull, "w", encoding="utf-8") as sink',
            'open("captured-output.txt", "w", encoding="utf-8") as sink',
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "isinstance(value, str) and bool(value.strip())",
            "bool(value)",
        ),
        (
            "src/trading_bot/robinhood_paper_cycle.py",
            "        post_review, post_review_pages = _collect_agentic_orders(",
            "        if review_failure is not None:\n"
            "            raise review_failure\n"
            "        post_review, post_review_pages = _collect_agentic_orders(",
        ),
        (
            "src/trading_bot/robinhood_paper_cycle.py",
            "except Exception as error:",
            "except BaseException as error:",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "browser_opener=observation.forbid_browser",
            "browser_opener=lambda url: True",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            'raise RobinhoodPaperOperatorError("interactive OAuth is forbidden")',
            "return True",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "json.dumps(asdict(evidence), sort_keys=True)",
            'json.dumps({"raw": store.history()}, default=str)',
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "    source_head: str",
            "    account_number: str\n    source_head: str",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "    placement_calls: int = 0",
            "    placement_calls: int = 1",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "if any(resolved == root or resolved.is_relative_to(root) "
            "for root in roots):",
            "if False:",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "    roots = _admit_source(expected_branch, expected_head, expected_tree)",
            "    roots = ()",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "    observation = _Observation()",
            "    place_equity_order()\n    observation = _Observation()",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            '    "get_equity_orders",',
            '    "get_accounts",\n    "get_equity_orders",',
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    def _get_accounts(",
            "    def get_accounts(",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    def get_equity_orders(",
            "    def call_tool(",
        ),
        ("scripts/checkpoint_runner.py", "preflight=None,", "preflight=host_effect,"),
        ("scripts/checkpoint_runner.py", "execute=None,", "execute=host_effect,"),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "arch131-robinhood-paper-operator",
            "missing-checkpoint",
        ),
    ],
)
def test_131h_authority_rejects_boundary_drift(tmp_path, relative, before, after):
    repo = Path(runner.__file__).resolve().parent.parent
    for path in (
        "src/trading_bot/robinhood_paper_operator.py",
        "src/trading_bot/robinhood_mcp/sdk_transport.py",
        "src/trading_bot/robinhood_mcp/windows_oauth.py",
        "src/trading_bot/robinhood_mcp/adapter.py",
        "src/trading_bot/robinhood_mcp/account_resolution.py",
        "src/trading_bot/robinhood_mcp/__init__.py",
        "src/trading_bot/robinhood_paper_cycle.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        source = (repo / path).read_text(encoding="utf-8")
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source, encoding="utf-8")
    assert runner._arch131_paper_operator_authority_check(tmp_path) == ()
    destination = tmp_path / relative
    source = destination.read_text(encoding="utf-8")
    assert before in source
    destination.write_text(source.replace(before, after), encoding="utf-8")
    failures = runner._arch131_paper_operator_authority_check(tmp_path)
    assert failures


def test_131i_source_registration_and_workflow() -> None:
    spec = runner._checkpoint_specs()["arch131-robinhood-paper-intent-bridge"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert spec.authority_check is runner._arch131_paper_intent_bridge_authority_check
    assert {
        "tests/review_paper/test_intent_bridge.py",
        "tests/review_paper/test_store.py",
        "tests/risk/test_risk_models.py",
        "tests/risk/test_manager.py",
        "tests/execution/test_execution_models.py",
        "tests/execution/test_order_engine.py",
    } <= set(spec.tests)
    assert {
        "src/trading_bot/review_paper/intent_bridge.py",
        "src/trading_bot/review_paper/__init__.py",
        "tests/review_paper/test_intent_bridge.py",
    } <= set(spec.ruff_paths)
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.index("arch131-robinhood-paper-intent-bridge") > (
        workflow.index("arch131-robinhood-paper-operator")
    )


def _131i_authority_copy(tmp_path: Path) -> Path:
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/intent_bridge.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_paper_intent_bridge_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "mapping",
    [
        "proposal_id=decision.proposal.proposal_id",
        "order_id=order_id",
        "symbol=decision.proposal.symbol",
        "side=decision.proposal.side",
        "desired_quantity=decision.proposal.desired_quantity",
        "approved_quantity=decision.approved_quantity",
        "risk_outcome=decision.outcome",
        "risk_reason_codes=tuple(reason.code.value for reason in decision.reasons)",
        "proposal_reason=decision.proposal.reason",
        "proposal_confidence=decision.proposal.confidence",
        "order_type=instruction.order_type",
        "time_in_force=instruction.time_in_force",
        "proposed_at=decision.proposal.created_at",
        "limit_price=instruction.limit_price",
    ],
)
def test_131i_authority_freezes_each_mapping(tmp_path, mapping) -> None:
    root = _131i_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/intent_bridge.py"
    source = path.read_text(encoding="utf-8")
    field = mapping.split("=", 1)[0]
    assert mapping in source
    path.write_text(source.replace(mapping, field + "=None"), encoding="utf-8")
    assert runner._arch131_paper_intent_bridge_authority_check(root)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("type(decision) is not RiskDecision", "False"),
        ("type(instruction) is not ExecutionInstruction", "False"),
        ("type(order_id) is not UUID", "False"),
        ("decision.outcome is RiskOutcome.REJECTED", "False"),
        ("decision.evaluated_at < decision.proposal.created_at", "False"),
        ("instruction.created_at < decision.evaluated_at", "False"),
        ("order_id: UUID,", "order_id: UUID = UUID(int=0),"),
        ("order_id=order_id", "order_id=uuid4()"),
        ("order_id=order_id", "order_id=UUID(int=0)"),
        (
            "reason.code.value for reason in decision.reasons",
            "reason.code.value for reason in reversed(decision.reasons)",
        ),
        (
            "tuple(reason.code.value for reason in decision.reasons)",
            "tuple(sorted({reason.code.value for reason in decision.reasons}))",
        ),
        ("limit_price=instruction.limit_price", "limit_price=None"),
        ("risk_outcome=decision.outcome", "risk_outcome=RiskOutcome.APPROVED"),
    ],
)
def test_131i_authority_freezes_validation_and_identity(tmp_path, before, after):
    root = _131i_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/intent_bridge.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert runner._arch131_paper_intent_bridge_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    [
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "from trading_bot.robinhood_paper_cycle import RobinhoodReviewPaperCycle",
        "from trading_bot.robinhood_mcp.sdk_transport import "
        "RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_mcp.windows_oauth import WindowsOAuthStorage",
        "from trading_bot.risk import RiskManager",
        "from trading_bot.execution import OrderEngine",
        "from uuid import uuid4",
        "import socket",
        "import subprocess",
        "import http.client",
        "import pathlib",
        "import os",
        "import logging",
        "run_robinhood_paper_operator()",
        "RobinhoodReviewPaperCycle()",
        "RiskManager().evaluate()",
        "OrderEngine().create_order()",
        "open('file')",
        "socket.socket()",
        "subprocess.run([])",
        "os.environ['SECRET']",
        "os.getenv('SECRET')",
        "print('proposal material')",
        "logging.info('proposal material')",
        "eval('effect()')",
        "__import__('socket')",
        "(",
    ],
)
def test_131i_authority_rejects_imports_calls_and_module_effects(tmp_path, addition):
    root = _131i_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/intent_bridge.py"
    path.write_text(
        path.read_text(encoding="utf-8") + addition + "\n", encoding="utf-8"
    )
    assert runner._arch131_paper_intent_bridge_authority_check(root)


@pytest.mark.parametrize(
    ("relative", "before", "after"),
    [
        ("scripts/checkpoint_runner.py", "preflight=None,", "preflight=host_effect,"),
        ("scripts/checkpoint_runner.py", "execute=None,", "execute=host_effect,"),
        (
            "scripts/checkpoint_runner.py",
            "authority_check=_arch131_paper_intent_bridge_authority_check,",
            "authority_check=_arch131_paper_operator_authority_check,",
        ),
        (
            "scripts/checkpoint_runner.py",
            'name="arch131-robinhood-paper-intent-bridge",',
            'name="missing-checkpoint",',
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "arch131-robinhood-paper-intent-bridge",
            "missing-checkpoint",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "verify-batch",
            "$Failures += 'wrong'",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "              arch131-robinhood-paper-intent-bridge",
            "              # arch131-robinhood-paper-intent-bridge",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "              arch131-robinhood-paper-operator",
            "              # arch131-robinhood-paper-operator",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            (
                "arch133-robinhood-post-publication-verifier\n"
                "          exit $LASTEXITCODE"
            ),
            ("arch133-robinhood-post-publication-verifier\n          exit 0"),
        ),
    ],
)
def test_131i_authority_freezes_source_only_registration_and_ci(
    tmp_path,
    relative,
    before,
    after,
) -> None:
    root = _131i_authority_copy(tmp_path)
    path = root / relative
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after, 1), encoding="utf-8")
    assert runner._arch131_paper_intent_bridge_authority_check(root)


def test_131i_authority_rejects_reversed_workflow_order(tmp_path) -> None:
    root = _131i_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text(encoding="utf-8")
    operator = "arch131-robinhood-paper-operator"
    bridge = "arch131-robinhood-paper-intent-bridge"
    source = source.replace(operator, "TEMP_CHECKPOINT")
    source = source.replace(bridge, operator).replace("TEMP_CHECKPOINT", bridge)
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_paper_intent_bridge_authority_check(root)


def test_131j_source_registration_and_workflow() -> None:
    spec = runner._checkpoint_specs()["arch131-robinhood-deterministic-paper-pipeline"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert (
        spec.authority_check
        is runner._arch131_deterministic_paper_pipeline_authority_check
    )
    assert set(spec.tests) == {
        "tests/runtime/test_checkpoint_runner.py",
        "tests/test_robinhood_paper_pipeline.py",
        "tests/review_paper/test_intent_bridge.py",
        "tests/test_robinhood_paper_operator.py",
        "tests/test_robinhood_paper_cycle.py",
        "tests/risk/test_risk_models.py",
        "tests/risk/test_manager.py",
    }
    assert "src/trading_bot/robinhood_paper_pipeline.py" in spec.ruff_paths
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.index("arch131-robinhood-deterministic-paper-pipeline") > (
        workflow.index("arch131-robinhood-paper-intent-bridge")
    )


def _131j_authority_copy(tmp_path: Path) -> Path:
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/robinhood_paper_pipeline.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_deterministic_paper_pipeline_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "argument",
    [
        "intent",
        "review_received_at",
        "expected_branch",
        "expected_head",
        "expected_tree",
        "paper_store_path",
        "evidence_path",
        "redirect_uri",
        "starting_cash",
        "slippage_basis_points",
        "commission",
    ],
)
def test_131j_authority_freezes_each_forwarded_argument(tmp_path, argument):
    root = _131j_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_paper_pipeline.py"
    source = path.read_text()
    before = f"{argument}={argument},"
    assert source.count(before) == 1
    path.write_text(source.replace(before, f"{argument}=None,"), encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("RiskManager(risk_limits)", "RiskManager(RiskLimits())"),
        (".evaluate(proposal, risk_context)", ".evaluate(proposal, other_context)"),
        (
            "decision = RiskManager",
            "decision = RiskManager(risk_limits).evaluate(proposal, risk_context)\n"
            "    decision = RiskManager",
        ),
        (
            "return RobinhoodDeterministicPaperPipelineResult(decision, None, None)",
            "pass",
        ),
        (
            "decision.outcome is RiskOutcome.REJECTED",
            "decision.outcome is RiskOutcome.APPROVED",
        ),
        (
            "build_review_paper_intent(decision, instruction, order_id=order_id)",
            "ReviewPaperIntent()",
        ),
        ("order_id=order_id)", "order_id=UUID(int=0))"),
        (
            "intent = build_review_paper_intent",
            "build_review_paper_intent(decision, instruction, order_id=order_id)\n"
            "    intent = build_review_paper_intent",
        ),
        (
            "evidence = run_robinhood_paper_operator(",
            "run_robinhood_paper_operator(intent=intent)\n"
            "    evidence = run_robinhood_paper_operator(",
        ),
        ("decision, intent, evidence)", "decision, intent, None)"),
        ("frozen=True, slots=True", "frozen=False, slots=True"),
        ("if type(order_id) is not UUID:", "if False:"),
        ("if type(self.intent) is not ReviewPaperIntent:", "if False:"),
        (
            "if type(self.operator_evidence) is not RobinhoodPaperOperatorEvidence:",
            "if False:",
        ),
        (
            "if self.intent is not None or self.operator_evidence is not None:",
            "if False:",
        ),
    ],
)
def test_131j_authority_freezes_composition_and_result(tmp_path, before, after):
    root = _131j_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_paper_pipeline.py"
    source = path.read_text()
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import random",
        "from uuid import uuid4",
        "from trading_bot.robinhood_mcp import RobinhoodReviewReadAdapter",
        "from trading_bot.robinhood_mcp.windows_oauth import "
        "create_windows_robinhood_oauth_factory",
        "from trading_bot.execution.engine import OrderEngine",
        "open('paper.sqlite', 'w')",
        "print('raw proposal/account')",
        "os.getenv('CONFIG')",
        "subprocess.run(['command'])",
        "transport.call_tool('place_equity_order')",
        "transport.call_tool('cancel_equity_order')",
        "transport.call_tool('place_option_order')",
        "transport.call_tool('place_crypto_order')",
        "create_windows_robinhood_oauth_factory()",
        "resolver.resolve()",
        "OrderEngine.create_order()",
        "OrderEngine.submit_order()",
        "uuid4()",
        "while True:\n    pass",
        "for cycle in range(2):\n    pass",
        "try:\n    run_robinhood_paper_operator()\n"
        "except Exception:\n    run_robinhood_paper_operator()",
    ],
)
def test_131j_authority_rejects_unreviewed_effects(tmp_path, addition):
    root = _131j_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_paper_pipeline.py"
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("preflight=None", "preflight=_r7_preflight"),
        ("execute=None", "execute=_r7_execute"),
        (
            "authority_check=_arch131_deterministic_paper_pipeline_authority_check",
            "authority_check=_arch131_paper_operator_authority_check",
        ),
        ('name="arch131-robinhood-deterministic-paper-pipeline"', 'name="other"'),
        ('"tests/test_robinhood_paper_pipeline.py",', '"tests/other.py",'),
        ("remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH", 'remote_branch="other"'),
    ],
)
def test_131j_authority_freezes_source_only_registration(tmp_path, before, after):
    root = _131j_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    prefix, rest = source.split(
        '        "arch131-robinhood-deterministic-paper-pipeline": CheckpointSpec(', 1
    )
    registration, suffix = rest.split(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', 1
    )
    assert before in registration
    source = (
        prefix
        + '        "arch131-robinhood-deterministic-paper-pipeline": CheckpointSpec('
        + registration.replace(before, after, 1)
        + '        "arch131-robinhood-paper-operator": CheckpointSpec('
        + suffix
    )
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        (
            "              arch131-robinhood-deterministic-paper-pipeline",
            "              # arch131-robinhood-deterministic-paper-pipeline",
        ),
        (
            "exit $LASTEXITCODE",
            "$Failures += 'other'",
        ),
        (
            "              arch131-robinhood-paper-intent-bridge",
            "              # arch131-robinhood-paper-intent-bridge",
        ),
    ],
)
def test_131j_authority_freezes_workflow_invocations(tmp_path, before, after):
    root = _131j_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


def test_131j_authority_rejects_reversed_workflow_order(tmp_path):
    root = _131j_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    pipeline_name = "arch131-robinhood-deterministic-paper-pipeline"
    bridge_name = "arch131-robinhood-paper-intent-bridge"
    source = source.replace(pipeline_name, "TEMP_CHECKPOINT")
    source = source.replace(bridge_name, pipeline_name).replace(
        "TEMP_CHECKPOINT", bridge_name
    )
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


# CI source-gate optimization regressions. Frozen independently of the runner
# registry to detect omissions/order changes in the workflow and its pins.
_EXPECTED_CI_CHECKPOINTS = (
    "arch128-parent-acl-repair",
    "arch128-r4",
    "arch128-r5-substrate",
    "arch128-r5-trading",
    "arch128-r6",
    "arch128-r7",
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
)


def _clean_source():
    return {"head": "a" * 40, "tree": "b" * 40, "branch": "example", "porcelain": ""}


def _batch_specs(calls, *, authority_failure=False, authority_exception=False):
    def forbidden():
        raise AssertionError("host/effect capability called")

    def authority(name):
        def check(repo):
            calls.append(name)
            if name == "second" and authority_exception:
                raise RuntimeError("authority unavailable")
            return ("boundary drift",) if name == "second" and authority_failure else ()

        return check

    return tuple(
        runner.CheckpointSpec(
            name=name,
            description=name,
            tests=tests,
            ruff_paths=ruff,
            authority_check=authority(name),
            preflight=forbidden,
            execute=forbidden,
        )
        for name, tests, ruff in (
            ("first", ("tests/shared.py", "tests/first.py"), ("shared.py", "first.py")),
            (
                "second",
                ("tests/second.py", "tests/shared.py"),
                ("second.py", "shared.py"),
            ),
            ("third", ("tests/first.py",), ("third.py", "first.py")),
        )
    )


def test_batch_first_seen_requirements_and_all_current_coverage():
    tests, ruff = runner.batch_requirements(_batch_specs([]))
    assert tests == ("tests/shared.py", "tests/first.py", "tests/second.py")
    assert ruff == ("shared.py", "first.py", "second.py", "third.py")
    specs = runner._checkpoint_specs()
    selected = [specs[name] for name in _EXPECTED_CI_CHECKPOINTS]
    tests, ruff = runner.batch_requirements(selected)
    assert len(tests) == len(set(tests))
    assert len(ruff) == len(set(ruff))
    assert tests[0] == runner.COMMON_TESTS[0]
    assert ruff[:2] == runner.COMMON_RUFF_PATHS
    for spec in selected:
        assert set(spec.tests) <= set(tests)
        assert set(spec.ruff_paths) <= set(ruff)
    assert runner.CI_CHECKPOINTS == _EXPECTED_CI_CHECKPOINTS


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


@pytest.mark.parametrize(
    "paths,expected",
    [
        (["docs/foo.md"], "DOCS_ONLY"),
        (["docs/foo.md", "docs/nested/bar.md"], "DOCS_ONLY"),
        (["docs/foo.md", "src/foo.py"], "FULL"),
        (["docs/foo.md", "tests/foo.py"], "FULL"),
        ([".github/workflows/checkpoint-source-gates.yml"], "FULL"),
        (["scripts/checkpoint_runner.py"], "FULL"),
        (["pyproject.toml"], "FULL"),
        (["unknown"], "FULL"),
        ([], "FULL"),
        ([""], "FULL"),
        (["docs/../src/foo.py"], "FULL"),
        (["docs/"], "FULL"),
        ([" docs/foo.md"], "FULL"),
        (["docs\\foo.md"], "FULL"),
    ],
)
def test_docs_changed_path_classification(paths, expected):
    assert runner.classify_changed_paths(paths) == expected


def _event(monkeypatch, tmp_path, base, name="push"):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {"before": base}
            if name == "push"
            else {"pull_request": {"base": {"sha": base}}}
        )
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_EVENT_NAME", name)
    return event


@pytest.mark.parametrize("name", ["push", "pull_request"])
def test_ci_classification_uses_exact_event_base_and_nul_paths(
    tmp_path, monkeypatch, name
):
    base, head = "a" * 40, "b" * 40
    _event(monkeypatch, tmp_path, base, name)
    calls = []

    def git(repo, *args):
        calls.append(args)
        return "commit" if args[0] == "cat-file" else ""

    monkeypatch.setattr(runner, "_git_output", git)

    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv, 0, b"docs/a file.md\x00docs/nested.md\x00", b""
        )

    monkeypatch.setattr(runner.subprocess, "run", run)
    result = runner._ci_changes(tmp_path, head)
    assert result["mode"] == "DOCS_ONLY"
    assert result["changed_paths"] == ["docs/a file.md", "docs/nested.md"]
    assert calls == [
        ("cat-file", "-t", base),
        ("merge-base", "--is-ancestor", base, head),
        ("git", "diff", "--name-only", "-z", "--no-renames", base, head, "--"),
    ]


@pytest.mark.parametrize(
    "base", [None, "", "0" * 40, "invalid", "g" * 40, "--malicious", 123]
)
def test_ci_invalid_base_falls_back_without_git(tmp_path, monkeypatch, base):
    _event(monkeypatch, tmp_path, base)
    monkeypatch.setattr(
        runner, "_git_output", lambda *a: pytest.fail("invalid base used")
    )
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


@pytest.mark.parametrize(
    "bad_event", ["[]", "null", "{}", "{", '{"pull_request": null}']
)
def test_ci_missing_or_malformed_event_falls_back(tmp_path, monkeypatch, bad_event):
    event = _event(monkeypatch, tmp_path, "a" * 40, "pull_request")
    event.write_text(bad_event)
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"
    monkeypatch.delenv("GITHUB_EVENT_PATH")
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


@pytest.mark.parametrize("stage", ["cat-file", "merge-base"])
def test_ci_unavailable_base_or_nonancestor_falls_back(tmp_path, monkeypatch, stage):
    _event(monkeypatch, tmp_path, "a" * 40)

    def git(repo, *args):
        if args[0] == stage:
            raise RuntimeError("unavailable")
        return "commit"

    monkeypatch.setattr(runner, "_git_output", git)
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"", 0),
        (b" docs/hidden.md\x00", 0),
        (b"docs/a.md", 0),
        (b"docs/a.md\x00", 1),
        (b"docs/a.md\x00src/old.py\x00", 0),
    ],
)
def test_ci_unknown_diff_and_moved_source_fall_back(tmp_path, monkeypatch, raw, code):
    _event(monkeypatch, tmp_path, "a" * 40)
    monkeypatch.setattr(runner, "_git_output", lambda *a: "commit")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, code, raw, b""),
    )
    assert runner._ci_changes(tmp_path, "b" * 40)["mode"] == "FULL"


@pytest.mark.parametrize(
    "docs_only,mode,exit_code,drift,expected",
    [
        (False, "DOCS_ONLY", 0, False, True),
        (False, "FULL", 0, False, True),
        (True, "DOCS_ONLY", 0, False, True),
        (True, "DOCS_ONLY", 1, False, False),
        (True, "FULL", 0, False, False),
        (True, "DOCS_ONLY", 0, True, False),
        (False, "DOCS_ONLY", 0, True, False),
    ],
)
def test_ci_docs_gate_evidence_range_check_and_output(
    tmp_path, monkeypatch, docs_only, mode, exit_code, drift, expected
):
    states = iter(
        [_clean_source(), {**_clean_source(), "porcelain": "?? drift" if drift else ""}]
    )
    monkeypatch.setattr(runner, "_git_state", lambda repo: next(states))
    monkeypatch.setattr(
        runner,
        "_ci_changes",
        lambda *a: {
            "mode": mode,
            "base": "c" * 40,
            "changed_paths": ["docs/a.md"],
            "reason": "test",
        },
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    calls = []

    def execute(step, **kwargs):
        calls.append(step.argv)
        return _outcome(step.name, exit_code)

    monkeypatch.setattr(runner, "_execute_step", execute)
    passed, path = runner.verify_ci_changes(
        repo_root=tmp_path, evidence_root=tmp_path / "evidence", docs_only=docs_only
    )
    assert passed == expected
    assert calls == (
        [("git", "diff", "--check", "c" * 40, "a" * 40, "--")]
        if docs_only and mode == "DOCS_ONLY"
        else []
    )
    report = json.loads(path.read_text())
    assert report["status"] == ("PASS" if expected else "FAIL")
    assert report["identity_stable"] == (not drift)
    assert report["production_effects"] == "NOT_RUN"
    if docs_only:
        assert not output.exists()
    else:
        assert output.read_text() == f"mode={mode if expected else 'FULL'}\n"


def test_docs_gate_rejects_dirty_source(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner,
        "_git_state",
        lambda repo: {**_clean_source(), "porcelain": " M docs/a.md"},
    )
    monkeypatch.setattr(
        runner, "_ci_changes", lambda *a: pytest.fail("classified dirty source")
    )
    with pytest.raises(RuntimeError, match="clean worktree"):
        runner.verify_ci_changes(
            repo_root=tmp_path, evidence_root=tmp_path / "evidence", docs_only=True
        )


def test_ci_workflow_batch_order_conditions_and_slim_artifacts():
    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    # runner context is allowed in step env, but unavailable in job env.
    job_settings = workflow.split("    steps:", 1)[0]
    assert "runner.temp" not in job_settings
    assert (
        workflow.count(
            "        env:\n"
            "          AI_TRADING_BOT_CHECKPOINT_EVIDENCE_ROOT: "
            "${{ runner.temp }}/ai-trading-bot-checkpoints"
        )
        == 3
    )
    assert runner._batch_workflow_is_reviewed(workflow)
    assert workflow.count("verify-batch") == 1
    assert "verify arch" not in workflow and "$Failures" not in workflow
    command = workflow.split("            verify-batch `\n", 1)[1].split(
        "          exit $LASTEXITCODE", 1
    )[0]
    assert (
        tuple(line.strip().removesuffix(" `") for line in command.splitlines())
        == _EXPECTED_CI_CHECKPOINTS
    )
    assert workflow.index("classify-ci") < workflow.index(
        "Install source-gate dependencies"
    )
    for name in (
        "Install source-gate dependencies",
        "Show checkpoint status",
        "Verify batch source checkpoints",
    ):
        assert (
            f"- name: {name}\n        if: steps.changes.outputs.mode != 'DOCS_ONLY'"
            in workflow
        )
    assert (
        "- name: Validate docs-only range\n"
        "        if: steps.changes.outputs.mode == 'DOCS_ONLY'" in workflow
    )
    assert "-File .\\ops.ps1 verify-docs" in workflow
    upload = workflow.split("- name: Upload checkpoint evidence", 1)[1]
    assert (
        "/**/report.json" in upload
        and "/**/commands/*.stdout.txt" in upload
        and "/**/commands/*.stderr.txt" in upload
    )
    assert "!${{ runner.temp }}/ai-trading-bot-checkpoints/**/pytest/**" in upload
    assert "path: ${{ runner.temp }}/ai-trading-bot-checkpoints\n" not in upload


@pytest.mark.parametrize(
    "mutation", ["duplicate", "comment", "exit", "rename", "reverse"]
)
def test_batch_workflow_authority_rejects_incomplete_or_ambiguous_invocation(mutation):
    repo = Path(runner.__file__).resolve().parent.parent
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    if mutation == "duplicate":
        workflow += "\nverify-batch arch128-r4\n"
    elif mutation == "comment":
        workflow = workflow.replace(
            "              arch128-r4", "              # arch128-r4"
        )
    elif mutation == "exit":
        workflow = workflow.replace("exit $LASTEXITCODE", "exit 0")
    elif mutation == "rename":
        workflow = workflow.replace("arch128-r4", "missing-checkpoint")
    else:
        workflow = (
            workflow.replace("arch128-r4", "TEMP")
            .replace("arch128-r6", "arch128-r4")
            .replace("TEMP", "arch128-r6")
        )
    assert not runner._batch_workflow_is_reviewed(workflow)


@pytest.mark.parametrize("event_name", ["push", "pull_request"])
@pytest.mark.parametrize(
    "scenario", ["docs", "whitespace", "moved_source", "unavailable"]
)
def test_ci_change_gate_against_real_git_range(
    tmp_path, monkeypatch, event_name, scenario
):
    repo = tmp_path / "repository"
    repo.mkdir()

    def git(*args):
        result = subprocess.run(
            ("git", *args), cwd=repo, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()

    git("init", "--quiet")
    git("config", "user.name", "CI test")
    git("config", "user.email", "ci-test@example.invalid")
    git("config", "core.autocrlf", "false")
    (repo / "docs").mkdir()
    (repo / "src").mkdir()
    (repo / "docs/a.md").write_text("before\n", encoding="utf-8", newline="\n")
    (repo / "src/source.py").write_text("source\n", encoding="utf-8", newline="\n")
    git("add", "docs/a.md", "src/source.py")
    git("commit", "--quiet", "-m", "base")
    base = git("rev-parse", "HEAD")
    if scenario == "moved_source":
        git("mv", "src/source.py", "docs/source.py")
    else:
        (repo / "docs/a.md").write_text(
            "after  \n" if scenario == "whitespace" else "after\n",
            encoding="utf-8",
            newline="\n",
        )
    git("add", "docs/a.md")
    git("commit", "--quiet", "-m", "change")
    _event(
        monkeypatch,
        tmp_path,
        "f" * 40 if scenario == "unavailable" else base,
        event_name,
    )
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    mode = runner._ci_changes(repo, git("rev-parse", "HEAD"))["mode"]
    assert mode == (
        "FULL" if scenario in {"moved_source", "unavailable"} else "DOCS_ONLY"
    )
    passed, path = runner.verify_ci_changes(
        repo_root=repo, evidence_root=tmp_path / "evidence", docs_only=True
    )
    assert passed == (scenario == "docs")
    report = json.loads(path.read_text())
    assert report["source_before"] == report["source_after"]
    assert report["identity_stable"] is True
    assert report["status"] == ("PASS" if passed else "FAIL")
    assert git("status", "--porcelain=v1", "--untracked-files=all") == ""


# 131-K pins every builder boundary and the source-only batch participant.
def test_131k_source_only_registration_and_batch():
    name = "arch131-robinhood-virtual-risk-context"
    specs = runner._checkpoint_specs()
    spec = specs[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_virtual_risk_context_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert set(spec.tests) == {
        *runner.COMMON_TESTS,
        "tests/review_paper/test_risk_context.py",
        "tests/review_paper/test_store.py",
        "tests/ledger/test_ledger.py",
        "tests/risk/test_risk_models.py",
    }
    assert set(spec.ruff_paths) == {
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/review_paper/risk_context.py",
        "src/trading_bot/review_paper/__init__.py",
        "tests/review_paper/test_risk_context.py",
    }
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert (
        runner.CI_CHECKPOINTS.index(name)
        == runner.CI_CHECKPOINTS.index("arch131-robinhood-deterministic-paper-pipeline")
        + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131k_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/risk_context.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_virtual_risk_context_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "before,after",
    [
        (
            "type(store) is not ReviewPaperStore",
            "not isinstance(store, ReviewPaperStore)",
        ),
        ("type(proposal) is not TradeProposal", "False"),
        ("isinstance(prices, Mapping)", "True"),
        ("type(new_trading_enabled) is not bool", "False"),
        ('normalize_utc(as_of, "as_of")', "as_of"),
        ("as_of < proposal.created_at", "False"),
        ("isinstance(symbol, Symbol)", "True"),
        ("isinstance(price, Decimal)", "True"),
        ("not price.is_finite()", "False"),
        ('price <= Decimal("0")', "False"),
        ("set(prices) != set(ledger.positions) | {proposal.symbol}", "False"),
        (
            "ledger = store.reconstruct_ledger()",
            "ledger = store.reconstruct_ledger()\n"
            "    ledger = store.reconstruct_ledger()",
        ),
        (
            "account = ledger.create_account_snapshot(prices, as_of)",
            "account = ledger.create_account_snapshot(prices, as_of)\n"
            "    account = ledger.create_account_snapshot(prices, as_of)",
        ),
        ("cash=account.cash", "cash=account.buying_power"),
        ("equity=account.equity", "equity=account.cash"),
        ("positions=ledger.positions", "positions={}"),
        ("current_price=prices[proposal.symbol]", "current_price=None"),
        (
            "total_market_exposure=account.positions_market_value",
            "total_market_exposure=account.equity",
        ),
        ("new_trading_enabled=new_trading_enabled", "new_trading_enabled=True"),
        ("as_of=as_of", "as_of=proposal.created_at"),
    ],
)
def test_131k_authority_freezes_builder(tmp_path, before, after):
    root = _131k_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_context.py"
    source = path.read_text()
    assert before in source
    path.write_text(source.replace(before, after, 1), encoding="utf-8")
    assert runner._arch131_virtual_risk_context_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    [
        "from trading_bot.risk import RiskManager",
        "RiskManager().evaluate()",
        "from trading_bot.review_paper.intent_bridge import build_review_paper_intent",
        "from trading_bot.robinhood_paper_pipeline "
        "import run_robinhood_deterministic_paper_pipeline",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "from trading_bot.robinhood_mcp import RobinhoodMCPAdapter",
        "from trading_bot.robinhood_oauth import RobinhoodOAuthClient",
        "store.record_market_review(intent, review)",
        "performance.record_valuation(quotes)",
        "from uuid import uuid4",
        "import random",
        "import socket",
        "import subprocess",
        "import os",
        "import logging",
        "open('paper', 'w')",
        "print('context')",
        "ReviewPaperStore('other', starting_cash=1)",
        "def hidden_effect():\n    pass",
    ],
)
def test_131k_authority_rejects_expanded_effect_surface(tmp_path, addition):
    root = _131k_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_context.py"
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert runner._arch131_virtual_risk_context_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("preflight=None", "preflight=_r7_preflight"),
        ("execute=None", "execute=_r7_execute"),
        (
            "authority_check=_arch131_virtual_risk_context_authority_check",
            "authority_check=_arch131_paper_operator_authority_check",
        ),
        ('name="arch131-robinhood-virtual-risk-context"', 'name="other"'),
        ('"tests/review_paper/test_risk_context.py"', '"tests/other.py"'),
        ('"src/trading_bot/review_paper/risk_context.py"', '"src/other.py"'),
        ("remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH", 'remote_branch="other"'),
    ],
)
def test_131k_authority_freezes_registration(tmp_path, before, after):
    root = _131k_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    prefix, rest = source.split(
        '        "arch131-robinhood-virtual-risk-context": CheckpointSpec(', 1
    )
    registration, suffix = rest.split(
        '        "arch131-robinhood-forward-paper-cycle": CheckpointSpec(', 1
    )
    assert before in registration
    path.write_text(
        prefix
        + '        "arch131-robinhood-virtual-risk-context": CheckpointSpec('
        + registration.replace(before, after, 1)
        + '        "arch131-robinhood-forward-paper-cycle": CheckpointSpec('
        + suffix,
        encoding="utf-8",
    )
    assert runner._arch131_virtual_risk_context_authority_check(root)


@pytest.mark.parametrize("change", ["missing", "duplicate", "reverse", "sequential"])
def test_131k_authority_freezes_batch_workflow(tmp_path, change):
    root = _131k_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    name = "arch131-robinhood-virtual-risk-context"
    if change == "missing":
        source = source.replace(name, "# " + name)
    elif change == "duplicate":
        source = source.replace(name, name + " " + name)
    elif change == "reverse":
        previous = "arch131-robinhood-deterministic-paper-pipeline"
        source = (
            source.replace(previous, "TEMP_CHECKPOINT")
            .replace(name, previous)
            .replace("TEMP_CHECKPOINT", name)
        )
    else:
        source = source.replace("verify-batch", "verify arch")
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_virtual_risk_context_authority_check(root)


# 131-L freezes the sole-account binder and effect-free source certification.
def test_131l_source_only_registration_and_batch():
    name = "arch131-robinhood-forward-paper-cycle"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_forward_paper_cycle_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/test_robinhood_forward_paper_cycle.py",
        "tests/review_paper/test_risk_context.py",
        "tests/test_robinhood_paper_pipeline.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/robinhood_forward_paper_cycle.py",
        "tests/test_robinhood_forward_paper_cycle.py",
    )
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CHECKPOINTS.index(name) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-virtual-risk-context") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131l_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/robinhood_forward_paper_cycle.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_forward_paper_cycle_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "before,after",
    [
        ("        store,", "        other_store,"),
        ("        proposal,", "        other_proposal,"),
        ("        prices,", "        {},"),
        ("as_of=as_of", "as_of=proposal.created_at"),
        ("new_trading_enabled=new_trading_enabled", "new_trading_enabled=True"),
        ("risk_context=risk_context", "risk_context=other_context"),
        ("paper_store_path=store.path", "paper_store_path=other_store.path"),
        (
            "starting_cash=store.starting_cash",
            "starting_cash=other_store.starting_cash",
        ),
        (
            "    store: ReviewPaperStore,",
            "    store: ReviewPaperStore,\n    paper_store_path: Path,",
        ),
        (
            "    store: ReviewPaperStore,",
            "    store: ReviewPaperStore,\n    starting_cash: Decimal,",
        ),
        (
            "    risk_context = build_review_paper_risk_context(",
            "    build_review_paper_risk_context(store, proposal, prices)\n"
            "    risk_context = build_review_paper_risk_context(",
        ),
        (
            "    return run_robinhood_deterministic_paper_pipeline(",
            "    run_robinhood_deterministic_paper_pipeline()\n"
            "    return run_robinhood_deterministic_paper_pipeline(",
        ),
        (
            "    return run_robinhood_deterministic_paper_pipeline(",
            "    return None\n    run_robinhood_deterministic_paper_pipeline(",
        ),
        (
            "    risk_context = build_review_paper_risk_context(",
            "    return run_robinhood_deterministic_paper_pipeline()\n"
            "    risk_context = build_review_paper_risk_context(",
        ),
        (
            "run_robinhood_deterministic_paper_pipeline,",
            "run_robinhood_deterministic_paper_pipeline as alternate,",
        ),
        *(
            (f"{key}={key}", f"{key}=None")
            for key in (
                "proposal",
                "risk_limits",
                "instruction",
                "order_id",
                "review_received_at",
                "expected_branch",
                "expected_head",
                "expected_tree",
                "evidence_path",
                "redirect_uri",
                "slippage_basis_points",
                "commission",
            )
        ),
    ],
)
def test_131l_authority_freezes_composition_and_every_input(tmp_path, before, after):
    root = _131l_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_forward_paper_cycle.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after, 1), encoding="utf-8")
    assert runner._arch131_forward_paper_cycle_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    [
        "from trading_bot.risk import RiskManager",
        "RiskManager().evaluate()",
        "from trading_bot.review_paper import build_review_paper_intent",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "from trading_bot.robinhood_mcp import RobinhoodMCPAdapter",
        "from trading_bot.robinhood_oauth import RobinhoodOAuthClient",
        "store.reconstruct_ledger()",
        "ReviewPaperStore('other', starting_cash=1)",
        "performance.record_valuation(quotes)",
        "account.get_buying_power()",
        "OrderEngine().submit_order(order)",
        "adapter.place_equity_order()",
        "adapter.cancel_equity_order()",
        "adapter.place_option_order()",
        "adapter.place_crypto_order()",
        "from uuid import uuid4",
        "import socket",
        "import subprocess",
        "import os",
        "import logging",
        "open('paper', 'w')",
        "while True:\n    pass",
        "for attempt in range(2):\n    pass",
        "try:\n    pass\nexcept Exception:\n    pass",
        "def hidden_effect():\n    pass",
        "@scheduler\ndef unattended():\n    pass",
    ],
)
def test_131l_authority_rejects_expanded_effect_or_retry_surface(tmp_path, addition):
    root = _131l_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_forward_paper_cycle.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n", encoding="utf-8"
    )
    assert runner._arch131_forward_paper_cycle_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("preflight=None", "preflight=_r7_preflight"),
        ("execute=None", "execute=_r7_execute"),
        (
            "authority_check=_arch131_forward_paper_cycle_authority_check",
            "authority_check=_arch131_paper_operator_authority_check",
        ),
        ('name="arch131-robinhood-forward-paper-cycle"', 'name="other"'),
        ('"tests/test_robinhood_forward_paper_cycle.py"', '"tests/other.py"'),
        ('"src/trading_bot/robinhood_forward_paper_cycle.py"', '"src/other.py"'),
        ("remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH", 'remote_branch="other"'),
    ],
)
def test_131l_authority_freezes_source_only_registration(tmp_path, before, after):
    root = _131l_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    prefix, rest = source.split(
        '        "arch131-robinhood-forward-paper-cycle": CheckpointSpec(', 1
    )
    registration, suffix = rest.split(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', 1
    )
    assert before in registration
    path.write_text(
        prefix
        + '        "arch131-robinhood-forward-paper-cycle": CheckpointSpec('
        + registration.replace(before, after, 1)
        + '        "arch131-robinhood-paper-operator": CheckpointSpec('
        + suffix,
        encoding="utf-8",
    )
    assert runner._arch131_forward_paper_cycle_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131l_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131l_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-forward-paper-cycle"
    from dataclasses import replace

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-L checkpoint has host/effect capability" in (
        runner._arch131_forward_paper_cycle_authority_check(root)
    )


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "reverse", "sequential", "exit"]
)
def test_131l_authority_freezes_batch_workflow(tmp_path, change):
    root = _131l_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text(encoding="utf-8")
    name = "arch131-robinhood-forward-paper-cycle"
    if change == "missing":
        source = source.replace(name, "# " + name)
    elif change == "duplicate":
        source = source.replace(name, name + " " + name)
    elif change == "reverse":
        previous = "arch131-robinhood-virtual-risk-context"
        source = (
            source.replace(previous, "TEMP_CHECKPOINT")
            .replace(name, previous)
            .replace("TEMP_CHECKPOINT", name)
        )
    elif change == "sequential":
        source = source.replace("verify-batch", "verify arch")
    else:
        source = source.replace("exit $LASTEXITCODE", "exit 0")
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_forward_paper_cycle_authority_check(root)


@pytest.mark.parametrize(
    "relative",
    [
        "src/trading_bot/robinhood_forward_paper_cycle.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ],
)
def test_131l_authority_fails_closed_when_source_is_unavailable(tmp_path, relative):
    root = _131l_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch131_forward_paper_cycle_authority_check(root)


# 131-LQ freezes read-only evidence reconciliation on the isolated side branch.
def test_131lq_source_only_registration_and_batch():
    name = "arch131-robinhood-live-qualification-verifier"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert (
        spec.authority_check
        is runner._arch131_live_qualification_verifier_authority_check
    )
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/test_robinhood_live_qualification_verifier.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/robinhood_live_qualification_verifier.py",
        "tests/test_robinhood_live_qualification_verifier.py",
    )
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CHECKPOINTS.index(name) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-cycle") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131lq_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/robinhood_live_qualification_verifier.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_live_qualification_verifier_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131lq_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131lq_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_live_qualification_verifier.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_live_qualification_verifier_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131lq_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131lq_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-live-qualification-verifier"
    from dataclasses import replace

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-LQ checkpoint has host/effect capability" in (
        runner._arch131_live_qualification_verifier_authority_check(root)
    )


# 131-M pins the entire pure module and its source-only side-branch registration.
def test_131m_source_only_registration_and_batch():
    name = "arch131-robinhood-session-admission"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_session_admission_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/review_paper/test_session_admission.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/review_paper/session_admission.py",
        "tests/review_paper/test_session_admission.py",
    )
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CHECKPOINTS.index(name) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-live-qualification-verifier") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131m_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/session_admission.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_session_admission_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131m_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131m_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/session_admission.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_session_admission_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131m_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131m_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-session-admission"
    from dataclasses import replace

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-M checkpoint has host/effect capability" in (
        runner._arch131_session_admission_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_session_admission.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_session_admission_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131m_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131m_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-session-admission": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-forward-paper-preview": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-M source-only checkpoint registration drift" in (
        runner._arch131_session_admission_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131m_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131m_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/session_admission.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-live-qualification-verifier",\n'
                '    "arch131-robinhood-session-admission",',
                '    "arch131-robinhood-session-admission",\n'
                '    "arch131-robinhood-live-qualification-verifier",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_session_admission_authority_check(root)


def test_131m_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):
    from dataclasses import replace

    root = _131m_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-session-admission"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-M checkpoint remote branch drift" in (
        runner._arch131_session_admission_authority_check(root)
    )


# 131-N pins the entire pure module and its source-only side-branch registration.
def test_131n_source_only_registration_and_batch():
    name = "arch131-robinhood-risk-price-snapshot"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_risk_price_snapshot_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/review_paper/test_risk_prices.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/review_paper/risk_prices.py",
        "tests/review_paper/test_risk_prices.py",
    )
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CHECKPOINTS.index(name) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-session-admission") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131n_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/risk_prices.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_risk_price_snapshot_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131n_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131n_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_prices.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_risk_price_snapshot_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131n_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131n_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-risk-price-snapshot"
    from dataclasses import replace

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-N checkpoint has host/effect capability" in (
        runner._arch131_risk_price_snapshot_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_risk_prices.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_risk_price_snapshot_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131n_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131n_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-risk-price-snapshot": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-forward-paper-preview": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-N source-only checkpoint registration drift" in (
        runner._arch131_risk_price_snapshot_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131n_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131n_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/risk_prices.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-session-admission",\n'
                '    "arch131-robinhood-risk-price-snapshot",',
                '    "arch131-robinhood-risk-price-snapshot",\n'
                '    "arch131-robinhood-session-admission",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_risk_price_snapshot_authority_check(root)


def test_131n_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):
    from dataclasses import replace

    root = _131n_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-risk-price-snapshot"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-N checkpoint remote branch drift" in (
        runner._arch131_risk_price_snapshot_authority_check(root)
    )


# 131-O pins the entire pure module and its source-only side-branch registration.
def test_131o_source_only_registration_and_batch():
    name = "arch131-robinhood-forward-paper-preview"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_forward_paper_preview_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/review_paper/test_forward_preview.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/review_paper/forward_preview.py",
        "tests/review_paper/test_forward_preview.py",
    )
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CHECKPOINTS.index(name) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-risk-price-snapshot") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131o_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/forward_preview.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_forward_paper_preview_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131o_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131o_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/forward_preview.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_forward_paper_preview_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131o_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131o_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-forward-paper-preview"
    from dataclasses import replace

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-O checkpoint has host/effect capability" in (
        runner._arch131_forward_paper_preview_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_forward_preview.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_forward_paper_preview_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131o_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131o_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-forward-paper-preview": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-O source-only checkpoint registration drift" in (
        runner._arch131_forward_paper_preview_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131o_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131o_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/forward_preview.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-risk-price-snapshot",\n'
                '    "arch131-robinhood-forward-paper-preview",',
                '    "arch131-robinhood-forward-paper-preview",\n'
                '    "arch131-robinhood-risk-price-snapshot",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_forward_paper_preview_authority_check(root)


def test_131o_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):
    from dataclasses import replace

    root = _131o_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-forward-paper-preview"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-O checkpoint remote branch drift" in (
        runner._arch131_forward_paper_preview_authority_check(root)
    )


@pytest.mark.parametrize(
    "before,after",
    [
        ("price_snapshot.prices,", "dict(price_snapshot.prices),"),
        ("as_of=price_snapshot.observed_at,", "as_of=proposal.created_at,"),
        ("risk_context=risk_context,", "risk_context=other_context,"),
        ("risk_decision=decision,", "risk_decision=other_decision,"),
        (
            "    decision = RiskManager(risk_limits).evaluate(proposal, risk_context)",
            "    RiskManager(risk_limits).evaluate(proposal, risk_context)\n"
            "    decision = RiskManager(risk_limits).evaluate(proposal, risk_context)",
        ),
        (
            "    risk_context = build_review_paper_risk_context(",
            "    store.reconstruct_ledger()\n"
            "    risk_context = build_review_paper_risk_context(",
        ),
        ("return context.subtract(current, approved)", "return Decimal('0')"),
        ('if self.projected_position_quantity < Decimal("0"):', "if False:"),
    ],
)
def test_131o_authority_pins_composition_validation_and_projection(
    tmp_path, before, after
):
    root = _131o_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/forward_preview.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert (
        "131-O forward-preview boundary drift"
        in runner._arch131_forward_paper_preview_authority_check(root)
    )


# 131-P pins the entire bounded module and its source-only side-branch registration.
def test_131p_source_only_registration_and_batch():
    name = "arch131-robinhood-risk-price-acquisition"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert (
        spec.authority_check is runner._arch131_risk_price_acquisition_authority_check
    )
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/review_paper/test_risk_price_acquisition.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/review_paper/risk_price_acquisition.py",
        "tests/review_paper/test_risk_price_acquisition.py",
    )
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CHECKPOINTS.index(name) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-preview") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131p_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/risk_price_acquisition.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_risk_price_acquisition_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131p_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131p_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_price_acquisition.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_risk_price_acquisition_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131p_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131p_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-risk-price-acquisition"
    from dataclasses import replace

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-P checkpoint has host/effect capability" in (
        runner._arch131_risk_price_acquisition_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_risk_price_acquisition.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_risk_price_acquisition_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131p_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131p_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-risk-price-acquisition": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-P source-only checkpoint registration drift" in (
        runner._arch131_risk_price_acquisition_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131p_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131p_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/risk_price_acquisition.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-forward-paper-preview",\n'
                '    "arch131-robinhood-risk-price-acquisition",',
                '    "arch131-robinhood-risk-price-acquisition",\n'
                '    "arch131-robinhood-forward-paper-preview",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_risk_price_acquisition_authority_check(root)


def test_131p_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):
    from dataclasses import replace

    root = _131p_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-risk-price-acquisition"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-P checkpoint remote branch drift" in (
        runner._arch131_risk_price_acquisition_authority_check(root)
    )


@pytest.mark.parametrize(
    "before,after",
    [
        ("store.reconstruct_ledger()", "store.create_account_snapshot({})"),
        (
            "response = adapter.equity_quotes(required_symbols)",
            "adapter.equity_quotes(required_symbols)\n"
            "    response = adapter.equity_quotes(required_symbols)",
        ),
        ("datetime.now(UTC)", "datetime.now()"),
        ("observed_at = datetime.now(UTC)", "observed_at = proposal.created_at"),
        ("max_quote_age=max_quote_age,", "max_quote_age=timedelta(days=1),"),
        ("return build_review_paper_risk_price_snapshot(", "return other_builder("),
        ("key=str", "key=repr"),
        ("len(required_symbols) > 20", "len(required_symbols) > 21"),
        (
            "type(store) is not ReviewPaperStore",
            "not isinstance(store, ReviewPaperStore)",
        ),
    ],
)
def test_131p_authority_pins_complete_acquisition(tmp_path, before, after):
    root = _131p_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_price_acquisition.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert "131-P risk-price acquisition boundary drift" in (
        runner._arch131_risk_price_acquisition_authority_check(root)
    )


# 131-Q pins the entire bounded module and its source-only side-branch registration.
def test_131q_source_only_registration_and_batch():
    name = "arch131-robinhood-supervised-forward-paper"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert (
        spec.authority_check is runner._arch131_supervised_forward_paper_authority_check
    )
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/review_paper/test_supervised_forward_paper.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/review_paper/supervised_forward_paper.py",
        "tests/review_paper/test_supervised_forward_paper.py",
    )
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CHECKPOINTS.index(name) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-risk-price-acquisition") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131q_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/supervised_forward_paper.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch131_supervised_forward_paper_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131q_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131q_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/supervised_forward_paper.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_supervised_forward_paper_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131q_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131q_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-supervised-forward-paper"
    from dataclasses import replace

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-Q checkpoint has host/effect capability" in (
        runner._arch131_supervised_forward_paper_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_supervised_forward_paper.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_supervised_forward_paper_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131q_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131q_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-supervised-forward-paper": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-Q source-only checkpoint registration drift" in (
        runner._arch131_supervised_forward_paper_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131q_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131q_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/supervised_forward_paper.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-risk-price-acquisition",\n'
                '    "arch131-robinhood-supervised-forward-paper",',
                '    "arch131-robinhood-supervised-forward-paper",\n'
                '    "arch131-robinhood-risk-price-acquisition",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_supervised_forward_paper_authority_check(root)


def test_131q_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):
    from dataclasses import replace

    root = _131q_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-supervised-forward-paper"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-Q checkpoint remote branch drift" in (
        runner._arch131_supervised_forward_paper_authority_check(root)
    )


@pytest.mark.parametrize(
    "before,after",
    [
        ("datetime.now(UTC)", "datetime.now()"),
        (
            "prepare_started_at = datetime.now(UTC)",
            "prepare_started_at = proposal.created_at",
        ),
        (
            "execute_at = datetime.now(UTC)",
            "execute_at = preparation.price_snapshot.observed_at",
        ),
        ("durable_history_before = store.history()", "durable_history_before = ()"),
        ("durable_history_after = store.history()", "durable_history_after = ()"),
        ("current_history = preparation.store.history()", "current_history = ()"),
        (
            "execute_at > preparation.quote_valid_until",
            "execute_at >= preparation.quote_valid_until",
        ),
        ("durable_history_before != durable_history_after", "False"),
        ("current_history != preparation.durable_history", "False"),
        (
            "revalidated_preview.risk_context != preparation.preview.risk_context",
            "False",
        ),
        (
            "revalidated_preview.risk_decision != preparation.preview.risk_decision",
            "False",
        ),
        (
            "instruction.created_at < preparation.preview.risk_decision.evaluated_at",
            "False",
        ),
        (
            "pipeline_result = run_robinhood_forward_paper_cycle(",
            "pipeline_result = other_pipeline(",
        ),
        (
            "durable_history_before = store.history()",
            "run_robinhood_forward_paper_cycle()\n"
            "    durable_history_before = store.history()",
        ),
        (
            "execute_at = datetime.now(UTC)",
            "run_robinhood_forward_paper_cycle()\n    execute_at = datetime.now(UTC)",
        ),
        (
            "durable_history_before = store.history()",
            "adapter.equity_quotes(())\n    durable_history_before = store.history()",
        ),
        (
            "type(adapter) is not RobinhoodReviewReadAdapter",
            "not isinstance(adapter, RobinhoodReviewReadAdapter)",
        ),
        ("mark.source_at + max_quote_age", "snapshot.observed_at + max_quote_age"),
    ],
)
def test_131q_authority_pins_complete_composition(tmp_path, before, after):
    root = _131q_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/supervised_forward_paper.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert "131-Q supervised forward-paper boundary drift" in (
        runner._arch131_supervised_forward_paper_authority_check(root)
    )


_R_PREPARE_BOUNDARIES = (
    (
        "arch131-robinhood-supervised-prepare-qualification",
        "Architecture 131-R supervised PREPARE qualification harness",
        "src/trading_bot/review_paper/prepare_qualification.py",
        "tests/review_paper/test_prepare_qualification.py",
        runner._arch131_prepare_qualification_authority_check,
        "arch131-robinhood-supervised-forward-paper",
    ),
    (
        "arch131-robinhood-supervised-prepare-verifier",
        "Architecture 131-R read-only PREPARE qualification verifier",
        "src/trading_bot/robinhood_prepare_qualification_verifier.py",
        "tests/test_robinhood_prepare_qualification_verifier.py",
        runner._arch131_prepare_verifier_authority_check,
        "arch131-robinhood-supervised-prepare-qualification",
    ),
)


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
def test_131r_source_only_registration_and_batch(boundary):
    name, description, source, test, authority, predecessor = boundary
    spec = runner._checkpoint_specs()[name]
    assert spec.description == description
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is authority
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (*runner.COMMON_TESTS, test)
    assert spec.ruff_paths == (*runner.COMMON_RUFF_PATHS, source, test)
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert (
        runner.CI_CHECKPOINTS.index(name)
        == runner.CI_CHECKPOINTS.index(predecessor) + 1
    )
    assert authority(Path(runner.__file__).resolve().parent.parent) == ()
    assert len(runner.CI_CHECKPOINTS) == 43
    assert runner.CI_CHECKPOINTS[-24:-10] == (
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
    )


def _131r_copy(tmp_path, boundary):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        boundary[2],
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert boundary[4](tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        "from trading_bot.risk.manager import RiskManager",
        "from trading_bot.execution.models import ExecutionInstruction",
        "from trading_bot.review_paper.supervised_forward_paper import "
        "execute_review_paper_supervised_cycle",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131r_complete_module_pinned(tmp_path, boundary, addition):
    root = _131r_copy(tmp_path, boundary)
    path = root / boundary[2]
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert boundary[4](root)


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_r7_execute"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        ("Architecture 131-R", "unreviewed"),
    ],
)
def test_131r_exact_registration_pinned(tmp_path, boundary, old, new):
    root = _131r_copy(tmp_path, boundary)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    start = source.index(f'        "{boundary[0]}": CheckpointSpec(')
    end = source.index("            execute=None,\n        ),", start) + len(
        "            execute=None,\n        ),"
    )
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new) + source[end:], encoding="utf-8"
    )
    assert boundary[4](root)


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
@pytest.mark.parametrize("target", ["source_missing", "branch", "batch", "workflow"])
def test_131r_source_authority_drift(tmp_path, boundary, target):
    root = _131r_copy(tmp_path, boundary)
    if target == "source_missing":
        (root / boundary[2]).unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(
            path.read_text().replace("exit $LASTEXITCODE", "exit 0"), encoding="utf-8"
        )
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"', '"feature/wrong"'
            )
        else:
            source = source.replace(
                f'    "{boundary[0]}",',
                f'    "{boundary[0]}",\n    "{boundary[0]}",',
                1,
            )
        path.write_text(source, encoding="utf-8")
    assert boundary[4](root)


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
@pytest.mark.parametrize(
    "field,value",
    [
        ("preflight", lambda: None),
        ("execute", lambda: None),
        ("remote_branch", "feature/wrong"),
    ],
)
def test_131r_runtime_registration_drift(tmp_path, monkeypatch, boundary, field, value):
    from dataclasses import replace

    root = _131r_copy(tmp_path, boundary)
    specs = runner._checkpoint_specs()
    specs[boundary[0]] = replace(specs[boundary[0]], **{field: value})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert boundary[4](root)


@pytest.mark.parametrize(
    "index,old,new",
    [
        (0, "prepare_review_paper_supervised_cycle(", "other_prepare("),
        (0, "after = _read_durable_snapshot(store.path)", "after = before"),
        (0, "if before != after:", "if False:"),
        (0, 'evidence_path.open("x"', 'evidence_path.open("w"'),
        (0, "return preparation", "return None"),
        (0, "SELECT * FROM review_fills", "SELECT paper_trade_id FROM review_fills"),
        (0, "?mode=ro", "?mode=rw"),
        (1, "?mode=ro", "?mode=rw"),
        (1, "SELECT * FROM review_fills", "SELECT paper_trade_id FROM review_fills"),
        (1, '"execute_invoked"] is False', '"execute_invoked"] == False'),
        (
            1,
            "expected_deadline = min(source + age for source in source_times)",
            "expected_deadline = observed + age",
        ),
    ],
)
def test_131r_critical_guards_pinned(tmp_path, index, old, new):
    boundary = _R_PREPARE_BOUNDARIES[index]
    root = _131r_copy(tmp_path, boundary)
    path = root / boundary[2]
    source = path.read_text()
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    assert boundary[4](root)


# 131-S pins the entire pure module and its source-only side-branch registration.
def test_131s_source_only_registration_and_batch():
    name = "arch131-nyse-published-regular-session-authority"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert (
        spec.authority_check
        is runner._arch131_nyse_published_regular_session_authority_check
    )
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/review_paper/test_nyse_published_regular_sessions.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "src/trading_bot/review_paper/nyse_published_regular_sessions.py",
        "tests/review_paper/test_nyse_published_regular_sessions.py",
    )
    assert runner.CI_CHECKPOINTS.count(name) == 1
    assert runner.CI_CHECKPOINTS.index(name) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-supervised-prepare-verifier") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


def _131s_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parent.parent
    for relative in (
        "src/trading_bot/review_paper/nyse_published_regular_sessions.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert (
        runner._arch131_nyse_published_regular_session_authority_check(tmp_path) == ()
    )
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131s_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131s_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/nyse_published_regular_sessions.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_nyse_published_regular_session_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131s_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131s_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-nyse-published-regular-session-authority"
    from dataclasses import replace

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-S checkpoint has host/effect capability" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_nyse_published_regular_sessions.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_nyse_published_regular_session_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131s_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131s_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-nyse-published-regular-session-authority": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-published-session-prepare": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-S source-only checkpoint registration drift" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131s_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131s_authority_copy(tmp_path)
    if target == "source_missing":
        (
            root / "src/trading_bot/review_paper/nyse_published_regular_sessions.py"
        ).unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-supervised-prepare-verifier",\n'
                '    "arch131-nyse-published-regular-session-authority",',
                '    "arch131-nyse-published-regular-session-authority",\n'
                '    "arch131-robinhood-supervised-prepare-verifier",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_nyse_published_regular_session_authority_check(root)


def test_131s_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):
    from dataclasses import replace

    root = _131s_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-nyse-published-regular-session-authority"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-S checkpoint remote branch drift" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("date(2028, 1, 17)", "date(2028, 1, 1)"),
        ("date(2028, 7, 3)", "date(2028, 7, 5)"),
        ("type(session_date) is not date", "not isinstance(session_date, date)"),
        ("if session_date.year not in self.supported_years:", "if False:"),
        ("session_date.weekday() >= 5", "session_date.weekday() > 5"),
        ("time(9, 30)", "time(9, 31)"),
        ("close_hour = 13 if session_date in _EARLY_CLOSES else 16", "close_hour = 16"),
        ('ZoneInfo("America/New_York")', 'ZoneInfo("UTC")'),
        ('default="NYSE"', 'default="other"'),
        ('default="NYSE core equity regular session"', 'default="other scope"'),
        (
            'default="nyse-published-regular-sessions-2026-2028/v1"',
            'default="unreviewed/v2"',
        ),
        ("default=(2026, 2027, 2028)", "default=(2026, 2027, 2028, 2029)"),
        ("default=date(2026, 10, 4)", "default=date(2026, 10, 5)"),
        ("frozen=True", "frozen=False"),
        ("init=False", "init=True"),
        ("frozenset(", "set("),
        ("return ReviewPaperSessionSchedule(", "return other_schedule("),
    ],
)
def test_131s_authority_pins_manifest_and_schedule(tmp_path, old, new):
    root = _131s_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/nyse_published_regular_sessions.py"
    source = path.read_text(encoding="utf-8")
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    assert "131-S published regular-session boundary drift" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "comment", "reordered"])
def test_131s_authority_rejects_ci_invocation_drift(tmp_path, mutation):
    root = _131s_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text(encoding="utf-8")
    name = "arch131-nyse-published-regular-session-authority"
    previous = "arch131-robinhood-supervised-prepare-verifier"
    line = f"              {name} `\n"
    assert source.count(line) == 1
    if mutation == "missing":
        source = source.replace(line, "")
    elif mutation == "duplicate":
        source = source.replace(line, f"              {name} `\n" + line)
    elif mutation == "comment":
        source = source.replace(line, f"              # {name}\n")
    else:
        source = source.replace(
            f"              {previous} `\n" + line,
            f"              {name} `\n              {previous} `\n",
        )
    path.write_text(source, encoding="utf-8")
    assert "131-S workflow invocation/order drift" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


_T_NAME = "arch131-robinhood-published-session-prepare"
_T_SOURCE = "src/trading_bot/review_paper/published_session_prepare.py"
_T_VERIFIER = "src/trading_bot/robinhood_prepare_qualification_verifier.py"
_T_AUTHORITY = runner._arch131_published_session_prepare_authority_check


def test_131t_source_only_registration_and_batch():
    spec = runner._checkpoint_specs()[_T_NAME]
    assert (
        spec.description
        == "Architecture 131-T explicit-date published-session PREPARE binding"
    )
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.authority_check is _T_AUTHORITY
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/review_paper/test_published_session_prepare.py",
        "tests/test_robinhood_prepare_qualification_verifier.py",
        "tests/scripts/test_run_test_certification.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        _T_SOURCE,
        "tests/review_paper/test_published_session_prepare.py",
        _T_VERIFIER,
        "tests/test_robinhood_prepare_qualification_verifier.py",
        "tests/scripts/test_run_test_certification.py",
    )
    assert len(runner.CI_CHECKPOINTS) == 43
    assert runner.CI_CHECKPOINTS.count(_T_NAME) == 1
    assert runner.CI_CHECKPOINTS.index(_T_NAME) == (
        runner.CI_CHECKPOINTS.index("arch131-nyse-published-regular-session-authority")
        + 1
    )
    assert _T_AUTHORITY(Path(runner.__file__).resolve().parents[1]) == ()


def _131t_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _T_SOURCE,
        _T_VERIFIER,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert _T_AUTHORITY(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize("relative", [_T_SOURCE, _T_VERIFIER])
@pytest.mark.parametrize(
    "addition",
    [
        "from datetime import datetime",
        "datetime.now()",
        "date.today()",
        "import socket",
        "import httpx",
        "import os",
        "import subprocess",
        "import time",
        "sleep(1)",
        "while True:\n    pass",
        "config.read()",
        "scheduler.run()",
        "adapter.acquire_quotes()",
        "store.read_records()",
        "execute_review_paper_supervised_cycle()",
        "retry()",
        "poll()",
        "open('evidence.json', 'w')",
    ],
)
def test_131t_complete_boundaries_pinned(tmp_path, relative, addition):
    root = _131t_copy(tmp_path)
    path = root / relative
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert _T_AUTHORITY(root)


@pytest.mark.parametrize(
    "relative,old,new",
    [
        (_T_SOURCE, "if schedule is None:", "if False:"),
        (_T_SOURCE, "return schedule", "return None"),
        (_T_SOURCE, "schedule=schedule,", "schedule=None,"),
        (_T_SOURCE, "store=store,", "store=None,"),
        (_T_SOURCE, "schedule_for(session_date)", "schedule_for(date(2026, 10, 2))"),
        (
            _T_SOURCE,
            "return prepare_review_paper_supervised_cycle(",
            "return execute_review_paper_supervised_cycle(",
        ),
        (
            _T_SOURCE,
            "return run_review_paper_prepare_qualification(",
            "return other_qualification(",
        ),
        (_T_VERIFIER, "canonical is not None", "True"),
        (_T_VERIFIER, "opens_at == canonical.opens_at", "True"),
        (_T_VERIFIER, "closes_at == canonical.closes_at", "True"),
        (_T_VERIFIER, "schedule_for(session_date)", "schedule_for(date(2026, 10, 2))"),
        (_T_VERIFIER, "?mode=ro", "?mode=rw"),
    ],
)
def test_131t_resolution_delegation_and_verifier_guards_pinned(
    tmp_path, relative, old, new
):
    root = _131t_copy(tmp_path)
    path = root / relative
    source = path.read_text()
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    assert _T_AUTHORITY(root)


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_r7_execute"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        ("tests/scripts/test_run_test_certification.py", "tests/missing.py"),
        (
            "_arch131_published_session_prepare_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131t_registration_drift(tmp_path, old, new):
    root = _131t_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    start = source.index(f'        "{_T_NAME}": CheckpointSpec(')
    end = source.index(
        '        "arch131-robinhood-published-prepare-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new) + source[end:], encoding="utf-8"
    )
    assert "131-T source-only checkpoint registration drift" in _T_AUTHORITY(root)


@pytest.mark.parametrize("field", ["preflight", "execute", "remote_branch"])
def test_131t_runtime_capability_drift(tmp_path, monkeypatch, field):
    from dataclasses import replace

    root = _131t_copy(tmp_path)
    specs = runner._checkpoint_specs()

    def forbidden():
        pytest.fail("source gate must never invoke host/effect capabilities")

    specs[_T_NAME] = replace(
        specs[_T_NAME], **{field: "wrong" if field == "remote_branch" else forbidden}
    )
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert _T_AUTHORITY(root)


@pytest.mark.parametrize(
    "target", ["branch", "batch", "source_missing", "verifier_missing"]
)
def test_131t_authority_drift(tmp_path, target):
    root = _131t_copy(tmp_path)
    if target.endswith("missing"):
        (root / (_T_SOURCE if target == "source_missing" else _T_VERIFIER)).unlink()
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"', '"feature/wrong"'
            )
        else:
            previous = "arch131-nyse-published-regular-session-authority"
            source = source.replace(
                f'    "{previous}",\n    "{_T_NAME}",',
                f'    "{_T_NAME}",\n    "{previous}",',
            )
        path.write_text(source, encoding="utf-8")
    assert _T_AUTHORITY(root)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "comment", "reordered"])
def test_131t_ci_invocation_drift(tmp_path, mutation):
    root = _131t_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    line = f"              {_T_NAME} `\n"
    previous = "arch131-nyse-published-regular-session-authority"
    assert source.count(line) == 1
    if mutation == "missing":
        source = source.replace(line, "")
    elif mutation == "duplicate":
        source = source.replace(line, f"              {_T_NAME} `\n" + line)
    elif mutation == "comment":
        source = source.replace(line, f"              # {_T_NAME}\n")
    else:
        source = source.replace(
            f"              {previous} `\n" + line,
            f"              {_T_NAME} `\n              {previous} `\n",
        )
    path.write_text(source, encoding="utf-8")
    assert "131-T workflow invocation/order drift" in _T_AUTHORITY(root)


_U_NAME = "arch131-robinhood-published-prepare-operator"
_U_SOURCE = "src/trading_bot/robinhood_prepare_operator.py"
_U_AUTHORITY = runner._arch131_published_prepare_operator_authority_check


def test_131u_source_only_registration_and_batch():
    spec = runner._checkpoint_specs()[_U_NAME]
    assert (
        spec.description
        == "Architecture 131-U source-owned PREPARE transport composition"
    )
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.authority_check is _U_AUTHORITY
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/test_robinhood_prepare_operator.py",
        "tests/review_paper/test_published_session_prepare.py",
        "tests/review_paper/test_prepare_qualification.py",
        "tests/scripts/test_run_test_certification.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        _U_SOURCE,
        "tests/test_robinhood_prepare_operator.py",
        "tests/scripts/test_run_test_certification.py",
    )
    assert len(runner.CI_CHECKPOINTS) == 43
    assert runner.CI_CHECKPOINTS.count(_U_NAME) == 1
    assert runner.CI_CHECKPOINTS.index(_U_NAME) == (
        runner.CI_CHECKPOINTS.index("arch131-robinhood-published-session-prepare") + 1
    )
    assert _U_AUTHORITY(Path(runner.__file__).resolve().parents[1]) == ()


def _131u_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _U_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert _U_AUTHORITY(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize("relative", [_U_SOURCE])
@pytest.mark.parametrize(
    "addition",
    [
        "from datetime import datetime",
        "datetime.now()",
        "date.today()",
        "import socket",
        "import httpx",
        "import os",
        "import subprocess",
        "import time",
        "sleep(1)",
        "while True:\n    pass",
        "config.read()",
        "scheduler.run()",
        "adapter.acquire_quotes()",
        "from trading_bot.execution.models import ExecutionInstruction",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "run_robinhood_deterministic_paper_pipeline()",
        "run_robinhood_forward_paper_cycle()",
        "build_review_paper_intent()",
        "transport.get_accounts()",
        "transport.get_equity_orders()",
        "transport.review_equity_order()",
        "place_order()",
        "cancel_order()",
        "options_mutation()",
        "crypto_mutation()",
        "storage.get_tokens()",
        "storage.get_client_info()",
        "api.read_generic()",
        "webbrowser.open('private')",
        "uuid4()",
        "store.read_records()",
        "execute_review_paper_supervised_cycle()",
        "retry()",
        "poll()",
        "open('evidence.json', 'w')",
    ],
)
def test_131u_complete_boundaries_pinned(tmp_path, relative, addition):
    root = _131u_copy(tmp_path)
    path = root / relative
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert _U_AUTHORITY(root)


@pytest.mark.parametrize(
    "old,new",
    [
        ("browser_opener=_block_interactive_authorization", "browser_opener=None"),
        (
            'raise LoopbackOAuthError("Interactive OAuth authorization is forbidden")',
            "return True",
        ),
        ("redirect_uri=redirect_uri", "redirect_uri='http://127.0.0.1:9999/callback'"),
        (
            "RobinhoodMcpStreamableHttpTransport(oauth_factory)",
            "RobinhoodMcpStreamableHttpTransport(None)",
        ),
        ("RobinhoodReviewReadAdapter(transport)", "RobinhoodReviewReadAdapter(None)"),
        ("adapter=adapter", "adapter=None"),
        ("session_date=session_date", "session_date=None"),
        ("store=store", "store=None"),
        ("evidence_path=evidence_path", "evidence_path=None"),
        (
            "return run_review_paper_published_session_prepare_qualification(",
            "return execute_review_paper_supervised_cycle(",
        ),
    ],
)
def test_131u_composition_and_blocker_pinned(tmp_path, old, new):
    root = _131u_copy(tmp_path)
    path = root / _U_SOURCE
    source = path.read_text()
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    assert _U_AUTHORITY(root)


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_r7_execute"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*COMMON_TESTS,", ""),
        ("*COMMON_RUFF_PATHS,", ""),
        ("tests/scripts/test_run_test_certification.py", "tests/missing.py"),
        (
            "_arch131_published_prepare_operator_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131u_registration_drift(tmp_path, old, new):
    root = _131u_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    start = source.index(f'        "{_U_NAME}": CheckpointSpec(')
    end = source.index(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new) + source[end:], encoding="utf-8"
    )
    assert "131-U source-only checkpoint registration drift" in _U_AUTHORITY(root)


@pytest.mark.parametrize("field", ["preflight", "execute", "remote_branch"])
def test_131u_runtime_capability_drift(tmp_path, monkeypatch, field):
    from dataclasses import replace

    root = _131u_copy(tmp_path)
    specs = runner._checkpoint_specs()

    def forbidden():
        pytest.fail("source gate must never invoke host/effect capabilities")

    specs[_U_NAME] = replace(
        specs[_U_NAME], **{field: "wrong" if field == "remote_branch" else forbidden}
    )
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert _U_AUTHORITY(root)


@pytest.mark.parametrize(
    "target", ["branch", "batch", "source_missing", "source_duplicate"]
)
def test_131u_authority_drift(tmp_path, target):
    root = _131u_copy(tmp_path)
    if target == "source_missing":
        (root / _U_SOURCE).unlink()
    elif target == "source_duplicate":
        path = root / _U_SOURCE
        path.write_text(
            path.read_text() + "\ndef helper(): return None\n", encoding="utf-8"
        )
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"', '"feature/wrong"'
            )
        else:
            previous = "arch131-robinhood-published-session-prepare"
            source = source.replace(
                f'    "{previous}",\n    "{_U_NAME}",',
                f'    "{_U_NAME}",\n    "{previous}",',
            )
        path.write_text(source, encoding="utf-8")
    assert _U_AUTHORITY(root)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "comment", "reordered"])
def test_131u_ci_invocation_drift(tmp_path, mutation):
    root = _131u_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    line = f"              {_U_NAME} `\n"
    previous = "arch131-robinhood-published-session-prepare"
    assert source.count(line) == 1
    if mutation == "missing":
        source = source.replace(line, "")
    elif mutation == "duplicate":
        source = source.replace(line, f"              {_U_NAME} `\n" + line)
    elif mutation == "comment":
        source = source.replace(line, f"              # {_U_NAME}\n")
    else:
        source = source.replace(
            f"              {previous} `\n" + line,
            f"              {_U_NAME} `\n              {previous}\n",
        )
    path.write_text(source, encoding="utf-8")
    assert "131-U workflow invocation/order drift" in _U_AUTHORITY(root)


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_131u_source_gate_participant_drift(tmp_path, mutation):
    root = _131u_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    line = f'    "{_U_NAME}",\n'
    assert source.count(line) == 1
    source = source.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(source, encoding="utf-8")
    assert "131-U checkpoint batch registration drift" in _U_AUTHORITY(root)


def test_131v_source_only_registration_and_boundaries(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    authority = runner._arch131_supervised_qualification_authority_check
    spec = runner._checkpoint_specs()["arch131-robinhood-supervised-qualification"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert authority(repo) == ()
    for relative in (
        "src/trading_bot/robinhood_supervised_qualification.py",
        "src/trading_bot/robinhood_execute_qualification_verifier.py",
        "scripts/robinhood_supervised_qualification.py",
        "src/trading_bot/review_paper/__init__.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert authority(tmp_path) == ()
    source = tmp_path / "src/trading_bot/robinhood_supervised_qualification.py"
    text_value = source.read_text(encoding="utf-8")
    for addition in (
        "callback()",
        "execute_review_paper_supervised_cycle()",
        "place_order()",
        "sleep(1)",
    ):
        source.write_text(text_value + "\n" + addition + "\n", encoding="utf-8")
        assert authority(tmp_path)


_A133_NAME = "arch133-robinhood-unattended-activation-core"
_A133_SOURCE = "src/trading_bot/review_paper/unattended_activation.py"
_A133_TEST = "tests/review_paper/test_unattended_activation.py"


def test_133a_source_only_registration_and_single_ordered_batch():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_A133_NAME]
    assert spec.name == _A133_NAME
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133a"
    assert spec.authority_check is runner._arch133_unattended_activation_authority_check
    assert spec.tests == (*runner.COMMON_TESTS, _A133_TEST)
    assert spec.ruff_paths == (*runner.COMMON_RUFF_PATHS, _A133_SOURCE, _A133_TEST)
    assert runner.CI_CHECKPOINTS.count(_A133_NAME) == 1
    index = runner.CI_CHECKPOINTS.index(_A133_NAME)
    assert runner.CI_CHECKPOINTS[index - 1 : index + 1] == (
        "arch131-robinhood-supervised-qualification",
        _A133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_A133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert spec.authority_check(repo) == ()


def _133a_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _A133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch133_unattended_activation_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import sqlite3",
        "import socket",
        "import subprocess",
        "from pathlib import Path",
        "from uuid import uuid4",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.risk.manager import RiskManager",
        "datetime.now(UTC)",
        "open('paper.sqlite', 'w')",
        "sleep(1)",
        "while True:\n    pass",
        "callback()",
    ],
)
def test_133a_authority_pins_every_import_and_call(tmp_path, addition):
    root = _133a_authority_copy(tmp_path)
    path = root / _A133_SOURCE
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert "133-A pure activation/wake boundary drift" in (
        runner._arch133_unattended_activation_authority_check(root)
    )


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("source", "missing"),
        ("source", "syntax"),
        ("runner", "missing"),
        ("runner", "registration"),
        ("runner", "batch_missing"),
        ("runner", "batch_duplicate"),
        ("workflow", "missing"),
        ("workflow", "batch_missing"),
        ("workflow", "batch_duplicate"),
    ],
)
def test_133a_authority_fails_closed_on_missing_or_drifting_material(
    tmp_path, target, mutation
):
    root = _133a_authority_copy(tmp_path)
    relative = {
        "source": _A133_SOURCE,
        "runner": "scripts/checkpoint_runner.py",
        "workflow": ".github/workflows/checkpoint-source-gates.yml",
    }[target]
    path = root / relative
    if mutation == "missing":
        path.unlink()
    elif mutation == "syntax":
        path.write_text("def broken(:", encoding="utf-8")
    else:
        text = path.read_text(encoding="utf-8")
        if mutation == "registration":
            start = text.index('        "' + _A133_NAME + '": CheckpointSpec(')
            end = text.index(
                '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
            )
            block = text[start:end].replace("preflight=None", "preflight=_r8_preflight")
            text = text[:start] + block + text[end:]
        else:
            line = (
                f'    "{_A133_NAME}",\n'
                if target == "runner"
                else f"              {_A133_NAME} `\n"
            )
            assert text.count(line) == 1
            text = text.replace(line, "" if mutation == "batch_missing" else line * 2)
        path.write_text(text, encoding="utf-8")
    assert runner._arch133_unattended_activation_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "feature/wrong"},
        {"tests": ()},
        {"ruff_paths": ()},
    ],
)
def test_133a_runtime_registration_drift_is_rejected(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133a_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_A133_NAME] = replace(specs[_A133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_unattended_activation_authority_check(root)


_B133_NAME = "arch133-robinhood-unattended-state-store"
_B133_SOURCES = (
    "src/trading_bot/review_paper/unattended_state_schema.py",
    "src/trading_bot/review_paper/unattended_state_store.py",
    "src/trading_bot/review_paper/unattended_state_verifier.py",
)
_B133_TEST = "tests/review_paper/test_unattended_state_store.py"


def test_133b_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_B133_NAME]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133b"
    assert spec.authority_check is runner._arch133_unattended_state_authority_check
    assert spec.tests == (*runner.COMMON_TESTS, _A133_TEST, _B133_TEST)
    assert spec.ruff_paths == (*runner.COMMON_RUFF_PATHS, *_B133_SOURCES, _B133_TEST)
    assert runner.CI_CHECKPOINTS.count(_B133_NAME) == 1
    index = runner.CI_CHECKPOINTS.index(_B133_NAME)
    assert runner.CI_CHECKPOINTS[index - 1 : index + 1] == (
        _A133_NAME,
        _B133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_B133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert spec.authority_check(repo) == ()


def _133b_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        *_B133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch133_unattended_state_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize("source", _B133_SOURCES)
@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import socket",
        "import subprocess",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        "from trading_bot.risk.manager import RiskManager",
        "datetime.now(UTC)",
        "open('paper.sqlite', 'w')",
        "callback()",
        "while True:\n    pass",
    ],
)
def test_133b_authority_pins_every_import_and_call(tmp_path, source, addition):
    root = _133b_authority_copy(tmp_path)
    path = root / source
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert f"133-B closed state boundary drift: {source}" in (
        runner._arch133_unattended_state_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    (
        *_B133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ),
)
def test_133b_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133b_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_unattended_state_authority_check(root)


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("runner", "registration"),
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133b_authority_registration_batch_and_workflow_drift(
    tmp_path, target, mutation
):
    root = _133b_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    if mutation == "registration":
        start = text.index('        "' + _B133_NAME + '": CheckpointSpec(')
        end = text.index(
            '        "arch133-robinhood-unattended-one-wake-composition": '
            "CheckpointSpec(",
            start,
        )
        text = (
            text[:start]
            + text[start:end].replace("execute=None", "execute=_r8_execute")
            + text[end:]
        )
    else:
        line = (
            f'    "{_B133_NAME}",\n'
            if target == "runner"
            else f"              {_B133_NAME} `\n"
        )
        assert text.count(line) == 1
        if mutation == "order":
            text = text.replace(
                f"              {_A133_NAME} `\n" + line,
                f"              {_B133_NAME} `\n              {_A133_NAME} `\n",
            )
        else:
            text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_unattended_state_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "feature/wrong"},
        {"remote_head_env": "UNSAFE"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda repo: ()},
    ],
)
def test_133b_runtime_registration_drift_fails_closed(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133b_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_B133_NAME] = replace(specs[_B133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_unattended_state_authority_check(root)


_C133_NAME = "arch133-robinhood-unattended-one-wake-composition"
_C133_SOURCE = "src/trading_bot/review_paper/unattended_one_wake.py"
_C133_TEST = "tests/review_paper/test_unattended_one_wake.py"


def test_133c_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_C133_NAME]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133c"
    assert spec.authority_check is runner._arch133_one_wake_authority_check
    assert spec.tests == (
        *runner.COMMON_TESTS,
        _A133_TEST,
        _B133_TEST,
        _C133_TEST,
        "tests/scripts/test_run_test_certification.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        _C133_SOURCE,
        _C133_TEST,
        "tests/scripts/test_run_test_certification.py",
    )
    assert runner.CI_CHECKPOINTS.count(_C133_NAME) == 1
    start = runner.CI_CHECKPOINTS.index(_A133_NAME)
    end = runner.CI_CHECKPOINTS.index(_C133_NAME)
    assert runner.CI_CHECKPOINTS[start : end + 1] == (
        _A133_NAME,
        _B133_NAME,
        _C133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_C133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert spec.authority_check(repo) == ()


def _133c_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _C133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch133_one_wake_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import subprocess",
        "import socket",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        (
            "from trading_bot.robinhood_paper_pipeline import "
            "run_robinhood_deterministic_paper_pipeline"
        ),
        (
            "from trading_bot.robinhood_forward_paper_cycle import "
            "run_robinhood_forward_paper_cycle"
        ),
        "datetime.now(UTC)",
        "callback()",
        "while True:\n    pass",
        "effect_seam.simulate_review_paper()",
        "quote_seam.prepare_quote()",
    ],
)
def test_133c_authority_pins_every_import_call_and_edge(tmp_path, addition):
    root = _133c_authority_copy(tmp_path)
    path = root / _C133_SOURCE
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert f"133-C closed composition boundary drift: {_C133_SOURCE}" in (
        runner._arch133_one_wake_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    [
        _C133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ],
)
def test_133c_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133c_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_one_wake_authority_check(root)


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("runner", "registration"),
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133c_authority_registration_batch_and_workflow_drift(
    tmp_path, target, mutation
):
    root = _133c_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    if mutation == "registration":
        start = text.index('        "' + _C133_NAME + '": CheckpointSpec(')
        end = text.index(
            '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
        )
        text = (
            text[:start]
            + text[start:end].replace("execute=None", "execute=_r8_execute")
            + text[end:]
        )
    else:
        line = (
            f'    "{_C133_NAME}",\n'
            if target == "runner"
            else f"              {_C133_NAME} `\n"
        )
        assert text.count(line) == 1
        if mutation == "order":
            text = text.replace(
                f"              {_B133_NAME} `\n" + line,
                f"              {_C133_NAME} `\n              {_B133_NAME} `\n",
            )
        else:
            text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_one_wake_authority_check(root)


_D133_NAME = "arch133-robinhood-unattended-review-paper-execution"
_D133_SOURCE = "src/trading_bot/review_paper/unattended_execution.py"
_D133_TEST = "tests/review_paper/test_unattended_execution.py"


def test_133d_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_D133_NAME]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133d"
    assert spec.authority_check is runner._arch133_execution_authority_check
    assert spec.tests == (
        *runner.COMMON_TESTS,
        _A133_TEST,
        _B133_TEST,
        _C133_TEST,
        _D133_TEST,
        "tests/test_robinhood_paper_operator.py",
        "tests/scripts/test_run_test_certification.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        _D133_SOURCE,
        _D133_TEST,
        "src/trading_bot/robinhood_paper_operator.py",
        "tests/scripts/test_run_test_certification.py",
    )
    assert runner.CI_CHECKPOINTS.count(_D133_NAME) == 1
    index = runner.CI_CHECKPOINTS.index(_D133_NAME)
    assert runner.CI_CHECKPOINTS[index - 1 : index + 1] == (
        _C133_NAME,
        _D133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_D133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert spec.authority_check(repo) == ()


def _133d_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        _D133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch133_execution_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import subprocess",
        "import socket",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        (
            "from trading_bot.robinhood_paper_pipeline import "
            "run_robinhood_deterministic_paper_pipeline"
        ),
        (
            "from trading_bot.robinhood_forward_paper_cycle import "
            "run_robinhood_forward_paper_cycle"
        ),
        "datetime.now(UTC)",
        "callback()",
        "while True:\n    pass",
        "effect_seam.simulate_review_paper()",
        "quote_seam.prepare_quote()",
    ],
)
def test_133d_authority_pins_every_import_call_and_edge(tmp_path, addition):
    root = _133d_authority_copy(tmp_path)
    path = root / _D133_SOURCE
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert f"133-D closed composition boundary drift: {_D133_SOURCE}" in (
        runner._arch133_execution_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    [
        _D133_SOURCE,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ],
)
def test_133d_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133d_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_execution_authority_check(root)


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("runner", "registration"),
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133d_authority_registration_batch_and_workflow_drift(
    tmp_path, target, mutation
):
    root = _133d_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    if mutation == "registration":
        start = text.index('        "' + _D133_NAME + '": CheckpointSpec(')
        end = text.index(
            '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
        )
        text = (
            text[:start]
            + text[start:end].replace("execute=None", "execute=_r8_execute")
            + text[end:]
        )
    else:
        line = (
            f'    "{_D133_NAME}",\n'
            if target == "runner"
            else f"              {_D133_NAME} `\n"
        )
        assert text.count(line) == 1
        if mutation == "order":
            text = text.replace(
                f"              {_C133_NAME} `\n" + line,
                f"              {_D133_NAME} `\n              {_C133_NAME} `\n",
            )
        else:
            text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_execution_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "feature/wrong"},
        {"remote_head_env": "UNSAFE"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda repo: ()},
    ],
)
def test_133d_runtime_registration_drift_fails_closed(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133d_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_D133_NAME] = replace(specs[_D133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_execution_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "feature/wrong"},
        {"remote_head_env": "UNSAFE"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda repo: ()},
    ],
)
def test_133c_runtime_registration_drift_fails_closed(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133c_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_C133_NAME] = replace(specs[_C133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_one_wake_authority_check(root)


_E133_NAME = "arch133-robinhood-unattended-host-scheduler-surface"
_E133_SOURCES = (
    "src/trading_bot/review_paper/unattended_host_identity.py",
    "src/trading_bot/review_paper/unattended_scheduler.py",
    "src/trading_bot/review_paper/unattended_host.py",
    "scripts/run_arch133_unattended_review_paper.py",
)
_E133_TEST = "tests/review_paper/test_unattended_host.py"


def test_133e_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_E133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133e"
    assert spec.authority_check is runner._arch133_host_scheduler_authority_check
    assert spec.tests == (
        *runner.COMMON_TESTS,
        _A133_TEST,
        _B133_TEST,
        _C133_TEST,
        _D133_TEST,
        _E133_TEST,
        "tests/scripts/test_run_test_certification.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        *_E133_SOURCES,
        _E133_TEST,
        "tests/scripts/test_run_test_certification.py",
    )
    assert runner.CI_CHECKPOINTS.count(_E133_NAME) == 1
    index = runner.CI_CHECKPOINTS.index(_E133_NAME)
    assert runner.CI_CHECKPOINTS[index - 1 : index + 1] == (
        _D133_NAME,
        _E133_NAME,
    )
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_E133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert runner._arch133_host_scheduler_authority_check(repo) == ()


def _133e_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        *_E133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((repo / relative).read_text(), encoding="utf-8")
    assert runner._arch133_host_scheduler_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize("source", _E133_SOURCES)
@pytest.mark.parametrize(
    "addition",
    [
        "import subprocess",
        "import socket",
        "datetime.now(UTC)",
        "callback()",
        "while True:\n    pass",
        "scheduler.mutate()",
    ],
)
def test_133e_authority_pins_all_host_runtime_scheduler_and_launcher_edges(
    tmp_path, source, addition
):
    root = _133e_authority_copy(tmp_path)
    path = root / source
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert (
        f"133-E closed composition boundary drift: {source}"
        in runner._arch133_host_scheduler_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    (
        *_E133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ),
)
def test_133e_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133e_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_host_scheduler_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "wrong"},
        {"remote_head_env": "UNREVIEWED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133e_runtime_registration_drift_rejected(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133e_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_E133_NAME] = replace(specs[_E133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_host_scheduler_authority_check(root)


@pytest.mark.parametrize(
    "target,mutation",
    [
        ("runner", "registration"),
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133e_registration_batch_and_workflow_fail_closed(tmp_path, target, mutation):
    root = _133e_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    if mutation == "registration":
        start = text.index('        "' + _E133_NAME + '": CheckpointSpec(')
        end = text.index(
            '        "arch133-robinhood-unattended-host-bootstrap": CheckpointSpec(',
            start,
        )
        text = (
            text[:start]
            + text[start:end].replace("execute=None", "execute=_r8_execute")
            + text[end:]
        )
    else:
        line = (
            f'    "{_E133_NAME}",\n'
            if target == "runner"
            else f"              {_E133_NAME} `\n"
        )
        assert text.count(line) == 1
        if mutation == "order":
            text = text.replace(
                f"              {_D133_NAME} `\n" + line,
                f"              {_E133_NAME} `\n              {_D133_NAME}\n",
            )
        else:
            text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_host_scheduler_authority_check(root)


_G133_NAME = "arch133-robinhood-unattended-host-bootstrap"
_H133_NAME = "arch133-robinhood-unattended-host-publication"


def test_133h_checkpoint_is_source_only_and_ci_registered():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_H133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133h"
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/review_paper/test_unattended_publication.py",
    )
    assert runner.CI_CHECKPOINTS[-6:-4] == (_G133_NAME, _H133_NAME)
    assert runner._arch133_host_publication_authority_check(repo) == ()


def _133h_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        *runner.ARCH133_PUBLICATION_PINS,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((repo / relative).read_text(), encoding="utf-8")
    assert runner._arch133_host_publication_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize("source", tuple(runner.ARCH133_PUBLICATION_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133h_complete_authority_pins_fail_closed(tmp_path, source, mutation):
    root = _133h_copy(tmp_path)
    path = root / source
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text() + "\nUNREVIEWED_EFFECT = True\n", encoding="utf-8"
        )
    assert runner._arch133_host_publication_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("preflight reached")},
        {"execute": lambda: pytest.fail("execute reached")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "UNREVIEWED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133h_runtime_capability_drift_rejected(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133h_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_H133_NAME] = replace(specs[_H133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_host_publication_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133h_batch_workflow_registration_drift(tmp_path, target, mutation):
    root = _133h_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    line = (
        f'    "{_H133_NAME}",\n'
        if target == "runner"
        else f"              {_H133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_G133_NAME}",\n'
            if target == "runner"
            else f"              {_G133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_host_publication_authority_check(root)


def test_133h_verify_preflight_execute_callbacks_unreachable(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_H133_NAME]
    monkeypatch.setattr(
        runner, "_git_state", lambda *args: pytest.fail("host accessed")
    )
    with pytest.raises(RuntimeError, match="no read-only preflight"):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


_G133_SOURCES = (
    "src/trading_bot/review_paper/unattended_host_identity.py",
    "src/trading_bot/review_paper/unattended_scheduler.py",
    "src/trading_bot/review_paper/unattended_host.py",
    "src/trading_bot/review_paper/unattended_host_bootstrap.py",
    "scripts/run_arch133_unattended_review_paper.py",
    "scripts/run_arch133_unattended_host_preflight.py",
)


def test_133g_source_only_registration_exact_order_and_coverage():
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[_G133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133g"
    assert spec.authority_check is runner._arch133_host_bootstrap_authority_check
    assert spec.tests == (
        *runner.COMMON_TESTS,
        _A133_TEST,
        _B133_TEST,
        _C133_TEST,
        _D133_TEST,
        _E133_TEST,
        "tests/scripts/test_run_test_certification.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        *_G133_SOURCES,
        _E133_TEST,
        "tests/scripts/test_run_test_certification.py",
    )
    assert runner.CI_CHECKPOINTS.count(_G133_NAME) == 1
    assert runner.CI_CHECKPOINTS[-7:-5] == (_E133_NAME, _G133_NAME)
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.count(_G133_NAME) == 1
    assert runner._batch_workflow_is_reviewed(workflow)
    assert runner._arch133_host_bootstrap_authority_check(repo) == ()


def _133g_authority_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        *_G133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((repo / relative).read_text(), encoding="utf-8")
    assert runner._arch133_host_bootstrap_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize("source", _G133_SOURCES)
def test_133g_authority_pins_bootstrap_runtime_and_launcher_edges(tmp_path, source):
    root = _133g_authority_copy(tmp_path)
    path = root / source
    path.write_text(path.read_text() + "\n# drift\n", encoding="utf-8")
    assert (
        f"133-G closed bootstrap boundary drift: {source}"
        in runner._arch133_host_bootstrap_authority_check(root)
    )


@pytest.mark.parametrize(
    "relative",
    (
        *_G133_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ),
)
def test_133g_authority_missing_files_fail_closed(tmp_path, relative):
    root = _133g_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch133_host_bootstrap_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: {}},
        {"execute": lambda: {}},
        {"remote_branch": "wrong"},
        {"remote_head_env": "UNREVIEWED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133g_runtime_registration_drift_rejected(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133g_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_G133_NAME] = replace(specs[_G133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_host_bootstrap_authority_check(root)


@pytest.mark.parametrize(
    ("target", "mutation"),
    [
        ("runner", "missing"),
        ("runner", "duplicate"),
        ("workflow", "missing"),
        ("workflow", "duplicate"),
        ("workflow", "order"),
    ],
)
def test_133g_registration_batch_and_workflow_fail_closed(tmp_path, target, mutation):
    root = _133g_authority_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text()
    line = (
        f'    "{_G133_NAME}",\n'
        if target == "runner"
        else f"              {_G133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        text = text.replace(
            f"              {_E133_NAME} `\n" + line,
            f"              {_G133_NAME} `\n              {_E133_NAME}\n",
        )
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_host_bootstrap_authority_check(root)


_I133_NAME = "arch133-robinhood-scratch-root-acl-qualification"


def test_133i_source_only_registration_and_inert_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_I133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133i"
    assert spec.authority_check is runner._arch133_scratch_root_acl_authority_check
    assert runner.CI_CHECKPOINTS[-5:-3] == (_H133_NAME, _I133_NAME)
    assert (
        runner._arch133_scratch_root_acl_authority_check(
            Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


def _133i_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in {
        *runner.ARCH133_SCRATCH_PINS,
        *runner.ARCH133_PUBLICATION_PINS,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    }:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch133_scratch_root_acl_authority_check(tmp_path) == ()
    return tmp_path


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_SCRATCH_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133i_source_import_closure_pins_fail_closed(tmp_path, relative, mutation):
    root = _133i_copy(tmp_path)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_scratch_root_acl_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("preflight reached")},
        {"execute": lambda: pytest.fail("execute reached")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133i_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133i_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_I133_NAME] = replace(specs[_I133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_scratch_root_acl_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133i_ci_registration_drift_fails_closed(tmp_path, target, mutation):
    root = _133i_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_I133_NAME}",\n'
        if target == "runner"
        else f"              {_I133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_H133_NAME}",\n'
            if target == "runner"
            else f"              {_H133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_scratch_root_acl_authority_check(root)


@pytest.mark.parametrize(
    "old,new",
    [
        (
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133IQualification-v1"',
            r'SCRATCH_PATH = r"F:\AI\temp\arch133i-root-acl-qualification-v1"',
        ),
        (
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133IQualification-v1"',
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133"',
        ),
        (
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133IQualification-v1"',
            r'SCRATCH_PATH = r"F:\AITradingBot\Arch133\qualification"',
        ),
        (
            r'PARENTS = ("F:\\", r"F:\AITradingBot")',
            r'PARENTS = ("F:\\", r"F:\AI", r"F:\AI\temp")',
        ),
    ],
)
def test_133i_relocated_namespace_pin_rejects_drift(tmp_path, old, new):
    root = _133i_copy(tmp_path)
    path = root / "src/trading_bot/arch133_acl/qualification.py"
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1
    path.write_text(text.replace(old, new), encoding="utf-8")
    assert runner._arch133_scratch_root_acl_authority_check(root)


_J133_NAME = "arch133-robinhood-retained-root-diagnostic"


def _133j_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in {
        *runner.ARCH133_RETAINED_PINS,
        *runner.ARCH133_SCRATCH_PINS,
        *runner.ARCH133_PUBLICATION_PINS,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    }:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch133_retained_root_authority_check(tmp_path) == ()
    return tmp_path


def test_133j_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_J133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133j"
    assert spec.authority_check is runner._arch133_retained_root_authority_check
    assert runner.CI_CHECKPOINTS[-4:-2] == (_I133_NAME, _J133_NAME)
    assert (
        runner._arch133_retained_root_authority_check(
            Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_RETAINED_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133j_read_only_import_closure_pins_fail_closed(tmp_path, relative, mutation):
    root = _133j_copy(tmp_path)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_retained_root_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("preflight reached")},
        {"execute": lambda: pytest.fail("execute reached")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133j_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133j_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_J133_NAME] = replace(specs[_J133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_retained_root_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133j_ci_registration_drift_fails_closed(tmp_path, target, mutation):
    root = _133j_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_J133_NAME}",\n'
        if target == "runner"
        else f"              {_J133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_I133_NAME}",\n'
            if target == "runner"
            else f"              {_I133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_retained_root_authority_check(root)


_K133_NAME = "arch133-robinhood-retained-root-acl-recovery"


def _133k_copy(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in {
        *runner.ARCH133_RECOVERY_PINS,
        *runner.ARCH133_RETAINED_PINS,
        *runner.ARCH133_SCRATCH_PINS,
        *runner.ARCH133_PUBLICATION_PINS,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    }:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch133_recovery_authority_check(tmp_path) == ()
    return tmp_path


def test_133k_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_K133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133k"
    assert spec.authority_check is runner._arch133_recovery_authority_check
    assert runner.CI_CHECKPOINTS[-3:-1] == (_J133_NAME, _K133_NAME)
    assert (
        runner._arch133_recovery_authority_check(
            Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_RECOVERY_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133k_read_only_import_closure_pins_fail_closed(tmp_path, relative, mutation):
    root = _133k_copy(tmp_path)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_recovery_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("preflight reached")},
        {"execute": lambda: pytest.fail("execute reached")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133k_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133k_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_K133_NAME] = replace(specs[_K133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_recovery_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133k_ci_registration_drift_fails_closed(tmp_path, target, mutation):
    root = _133k_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_K133_NAME}",\n'
        if target == "runner"
        else f"              {_K133_NAME} `\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_J133_NAME}",\n'
            if target == "runner"
            else f"              {_J133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_recovery_authority_check(root)


_L133_NAME = "arch133-robinhood-post-publication-verifier"


def _133l_copy(tmp_path):
    root = _133k_copy(tmp_path)
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in runner.ARCH133_VERIFIER_PINS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (repo / relative).read_text(encoding="utf-8"), encoding="utf-8"
        )
    assert runner._arch133_verifier_authority_check(root) == ()
    return root


def test_133l_source_only_registration_no_host_callbacks(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[_L133_NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-unattended-review-paper-133l"
    assert runner.CI_CHECKPOINTS[-2:] == (_K133_NAME, _L133_NAME)
    assert (
        runner._arch133_verifier_authority_check(
            Path(runner.__file__).resolve().parents[1]
        )
        == ()
    )
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host accessed"))
    with pytest.raises(RuntimeError):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )
    with pytest.raises(RuntimeError):
        runner.execute_checkpoint(
            spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


@pytest.mark.parametrize("relative", tuple(runner.ARCH133_VERIFIER_PINS))
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_133l_complete_import_closure_pins_fail_closed(tmp_path, relative, mutation):
    root = _133l_copy(tmp_path)
    path = root / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(
            path.read_text(encoding="utf-8") + "\nUNREVIEWED = True\n", encoding="utf-8"
        )
    assert runner._arch133_verifier_authority_check(root)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: pytest.fail("host accessed")},
        {"execute": lambda: pytest.fail("host accessed")},
        {"remote_branch": "wrong"},
        {"remote_head_env": "INJECTED"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_133l_runtime_callback_injection_fails_closed(tmp_path, monkeypatch, change):
    from dataclasses import replace

    root = _133l_copy(tmp_path)
    specs = runner._checkpoint_specs()
    specs[_L133_NAME] = replace(specs[_L133_NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_verifier_authority_check(root)


@pytest.mark.parametrize("target", ["runner", "workflow"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "order"])
def test_133l_ci_registration_drift_fails_closed(tmp_path, target, mutation):
    root = _133l_copy(tmp_path)
    path = root / (
        "scripts/checkpoint_runner.py"
        if target == "runner"
        else ".github/workflows/checkpoint-source-gates.yml"
    )
    text = path.read_text(encoding="utf-8")
    line = (
        f'    "{_L133_NAME}",\n'
        if target == "runner"
        else f"              {_L133_NAME}\n"
    )
    assert text.count(line) == 1
    if mutation == "order":
        prior = (
            f'    "{_K133_NAME}",\n'
            if target == "runner"
            else f"              {_K133_NAME} `\n"
        )
        text = text.replace(prior + line, line + prior)
    else:
        text = text.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_verifier_authority_check(root)
