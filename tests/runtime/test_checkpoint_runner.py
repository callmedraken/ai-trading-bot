from __future__ import annotations

import ast
import hashlib
import json
import re
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
        "d10-soak-status",
        "d10-soak-review",
        "d10-external-review-package",
        "d10-scheduler-slot-policy",
        "d10-scheduler-history-collector",
        "d10-xnys-session-coverage-policy",
        "d10-xnys-session-evidence-projector",
    }
    for spec in specs.values():
        assert "tests/runtime/test_checkpoint_runner.py" in spec.tests
        assert "scripts/checkpoint_runner.py" in spec.ruff_paths
        assert "tests/runtime/test_checkpoint_runner.py" in spec.ruff_paths
        expected_branch = (
            "feature/post-d10-observability"
            if spec.name
            in (
                "d10-soak-status",
                "d10-soak-review",
                "d10-external-review-package",
                "d10-scheduler-slot-policy",
                "d10-scheduler-history-collector",
                "d10-xnys-session-coverage-policy",
                "d10-xnys-session-evidence-projector",
            )
            else "feature/d10c-durable-wake-evidence"
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
    assert specs["d10-soak-status"].authority_check(repo_root) == ()
    assert specs["d10-soak-review"].authority_check(repo_root) == ()
    assert specs["d10-external-review-package"].authority_check(repo_root) == ()


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


def test_soak_status_registration_is_read_only() -> None:
    spec = runner._checkpoint_specs()["d10-soak-status"]
    assert spec.preflight is runner._d10_soak_status_preflight
    assert spec.execute is None
    assert spec.authority_check is runner._d10_soak_status_authority_check
    assert spec.remote_branch == "feature/post-d10-observability"
    assert spec.remote_head_env is None
    assert spec.tests == (
        *runner.COMMON_TESTS,
        "tests/runtime/test_d10_soak_status_readonly.py",
        "tests/runtime/test_d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_durable_wake_evidence_observe.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "scripts/d10_soak_status_readonly.py",
        "tests/runtime/test_d10_soak_status_readonly.py",
    )
    parser = runner._parser(runner._checkpoint_specs())
    for command in ("verify", "preflight"):
        assert (
            parser.parse_args((command, "d10-soak-status")).checkpoint
            == "d10-soak-status"
        )
    with pytest.raises(SystemExit):
        parser.parse_args(("execute", "d10-soak-status"))


@pytest.mark.parametrize("status", ("PASS", "BLOCKED"))
def test_soak_status_preflight_delegates_once_and_preserves_runner_shape(
    monkeypatch, status
) -> None:
    from scripts import d10_soak_status_readonly as admission

    primary = admission._base()
    primary["status"] = status
    calls = []

    def preflight():
        calls.append(())
        return primary

    monkeypatch.setattr(admission, "preflight", preflight)
    assert runner._d10_soak_status_preflight() == {"status": status, "primary": primary}
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
def test_soak_status_runner_independently_rejects_effect_drift(
    monkeypatch, field, status, drift
) -> None:
    from scripts import d10_soak_status_readonly as admission

    primary = admission._base()
    primary["status"] = status
    if drift is None:
        del primary[field]
    else:
        primary[field] = drift
    monkeypatch.setattr(admission, "preflight", lambda: primary)
    with pytest.raises(RuntimeError, match=field):
        runner._d10_soak_status_preflight()


@pytest.mark.parametrize("primary", (None, [], "PASS"))
def test_soak_status_runner_rejects_malformed_result(monkeypatch, primary) -> None:
    from scripts import d10_soak_status_readonly as admission

    monkeypatch.setattr(admission, "preflight", lambda: primary)
    with pytest.raises(RuntimeError, match="exact dictionary"):
        runner._d10_soak_status_preflight()


def _soak_status_authority_copy(
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
    source = (root / "scripts/d10_soak_status_readonly.py").read_text(encoding="utf-8")
    if old:
        assert old in source
        source = source.replace(old, new, 1)
    if addition:
        source = source.replace(
            "    result = _base()", f"    {addition}\n    result = _base()", 1
        )
    (target / "d10_soak_status_readonly.py").write_text(source, encoding="utf-8")
    runner_source = (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    if runner_old:
        # Generic wrapper snippets also occur in R8; mutate only S1's wrapper.
        if runner_old.startswith("primary = admission.preflight()"):
            start = runner_source.index("\ndef _d10_soak_status_preflight(")
            end = runner_source.index("def _r7_execute(", start)
            wrapper = runner_source[start:end]
            assert runner_old in wrapper
            runner_source = (
                runner_source[:start]
                + wrapper.replace(runner_old, runner_new, 1)
                + runner_source[end:]
            )
        else:
            # Scope S1 mutations to S1; S2A also names the same side branch.
            start = runner_source.index('        "d10-soak-status": CheckpointSpec(')
            end = runner_source.index(
                '        "d10-soak-review": CheckpointSpec(', start
            )
            registration = runner_source[start:end]
            assert runner_old in registration
            runner_source = (
                runner_source[:start]
                + registration.replace(runner_old, runner_new, 1)
                + runner_source[end:]
            )
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
        "Path('some-file').read_text()",
        "Path('some-file').read_bytes()",
        "Path('some-file').mkdir()",
        "Path('some-file').touch()",
        "Path('some-file').replace('another')",
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
def test_soak_status_authority_rejects_direct_host_or_effect_calls(
    tmp_path, addition
) -> None:
    root = _soak_status_authority_copy(tmp_path, addition=addition)
    assert runner._d10_soak_status_authority_check(root)


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
        (
            'observation["record_count"] != 3 * observation["wake_count"]',
            'observation["record_count"] < 3 * observation["wake_count"]',
        ),
        ('observation["wake_count"] < 1', 'observation["wake_count"] < 0'),
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
def test_soak_status_authority_freezes_boundary_identity_and_healthy_policy(
    tmp_path, old, new
) -> None:
    root = _soak_status_authority_copy(tmp_path, old=old, new=new)
    assert runner._d10_soak_status_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            "preflight=_d10_soak_status_preflight,",
            "preflight=_d10_soak_status_preflight, execute=_r7_execute,",
        ),
        ("preflight=_d10_soak_status_preflight,", "preflight=_r7_preflight,"),
        (
            "primary = admission.preflight()\n    if type(primary) is not dict:",
            "primary = admission.preflight()\n    guard.main()\n"
            "    if type(primary) is not dict:",
        ),
    ),
)
def test_soak_status_authority_rejects_execute_registration_and_wrapper_effects(
    tmp_path, old, new
) -> None:
    root = _soak_status_authority_copy(tmp_path, runner_old=old, runner_new=new)
    assert runner._d10_soak_status_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ('"feature/post-d10-observability"', '"feature/d10c-durable-wake-evidence"'),
        (
            "preflight=_d10_soak_status_preflight,",
            "preflight=_d10_soak_status_preflight, remote_head_env='HEAD',",
        ),
    ),
)
def test_soak_status_authority_freezes_side_branch_and_no_handoff(
    tmp_path, old, new
) -> None:
    root = _soak_status_authority_copy(tmp_path, runner_old=old, runner_new=new)
    assert runner._d10_soak_status_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("*EXPECTED_IDENTITY,", "*EXPECTED_IDENTITY, 'extra',"),
        (
            "observation = observer.observe()",
            "observation = observer.observe()\n        observer.observe = fake",
        ),
        ('or observation["wake_count"] < 1', 'and observation["wake_count"] < 1'),
        (
            'raise ValueError\n        reason = "evidence_summary_invalid"',
            'pass\n        reason = "evidence_summary_invalid"',
        ),
        (
            'or observation["wake_count"] < 1',
            'or observation["wake_count"] < 1 or False',
        ),
    ),
)
def test_soak_status_authority_rejects_shape_binding_and_predicate_drift(
    tmp_path, old, new
) -> None:
    root = _soak_status_authority_copy(tmp_path, old=old, new=new)
    assert runner._d10_soak_status_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ('status="PASS",', 'status="PASS", provider="CALL_RETURNED",'),
        ('accepted_wake_count=observation["wake_count"]', "accepted_wake_count=1"),
        ("return result\n\n    result.update(", "pass\n\n    result.update("),
    ),
)
def test_soak_status_authority_freezes_sanitized_rollup_and_blocked_exit(
    tmp_path, old, new
) -> None:
    root = _soak_status_authority_copy(tmp_path, old=old, new=new)
    assert runner._d10_soak_status_authority_check(root)


def test_soak_status_runner_rejects_dictionary_subclass(monkeypatch) -> None:
    from scripts import d10_soak_status_readonly as admission

    class DictionarySubclass(dict):
        pass

    monkeypatch.setattr(
        admission, "preflight", lambda: DictionarySubclass(admission._base())
    )
    with pytest.raises(RuntimeError, match="exact dictionary"):
        runner._d10_soak_status_preflight()


def test_soak_review_registration_is_verify_only() -> None:
    spec = runner._checkpoint_specs()["d10-soak-review"]
    assert spec.preflight is None
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/post-d10-observability"
    assert spec.authority_check is runner._d10_soak_review_authority_check
    assert spec.tests == (
        "tests/runtime/test_checkpoint_runner.py",
        "tests/runtime/test_d10_soak_status_readonly.py",
        "tests/runtime/test_d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_durable_wake_evidence_observe.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_d10_end_of_soak_review.py",
        "tests/runtime/test_personal_desktop_unattended_one_week_soak_source.py",
        "tests/runtime/test_personal_desktop_unattended_one_week_soak_controller.py",
    )
    assert spec.ruff_paths == (
        *runner.COMMON_RUFF_PATHS,
        "scripts/d10_end_of_soak_review.py",
        "tests/runtime/test_d10_end_of_soak_review.py",
    )
    parser = runner._parser(runner._checkpoint_specs())
    assert parser.parse_args(("verify", "d10-soak-review")).checkpoint == (
        "d10-soak-review"
    )
    for command in ("preflight", "execute"):
        with pytest.raises(SystemExit):
            parser.parse_args((command, "d10-soak-review"))


def _soak_review_authority_copy(
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
    source = (root / "scripts/d10_end_of_soak_review.py").read_text(encoding="utf-8")
    if old:
        assert old in source
        source = source.replace(old, new, 1)
    if addition:
        source += "\n" + addition + "\n"
    (target / "d10_end_of_soak_review.py").write_text(source, encoding="utf-8")
    runner_source = (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    if runner_old:
        start = runner_source.index('        "d10-soak-review": CheckpointSpec(')
        end = runner_source.index('        "arch128-r8": CheckpointSpec(', start)
        registration = runner_source[start:end]
        assert runner_old in registration
        runner_source = (
            runner_source[:start]
            + registration.replace(runner_old, runner_new, 1)
            + runner_source[end:]
        )
    (target / "checkpoint_runner.py").write_text(runner_source, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    (
        "import os",
        "import subprocess",
        "import ctypes",
        "from pathlib import Path",
        "open('evidence')",
        "Path('evidence').read_bytes()",
        "Path('evidence').write_text('data')",
        "os.environ['TOKEN']",
        "subprocess.run([])",
        "ctypes.WinDLL('kernel32')",
        "datetime.now(UTC)",
        "datetime.today()",
        "observer.observe()",
        "guard.main()",
        "scheduler.Run(None)",
        "scheduler.RegisterTaskDefinition()",
        "credential.read()",
        "provider.capture()",
        "paper_v2.execute()",
        "broker.order()",
        "live.execute()",
        "__import__('os')",
        "eval('effect()')",
        "build_d10_one_week_wake_summary(())",
        "def preflight(): pass",
        "def execute(): pass",
    ),
)
def test_soak_review_authority_rejects_io_and_effect_additions(tmp_path, addition):
    root = _soak_review_authority_copy(tmp_path, addition=addition)
    assert runner._d10_soak_review_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            'SCHEMA: Final = "d10-end-of-soak-operator-review/v1"',
            'SCHEMA: Final = "other"',
        ),
        ('"d2071f25-5a7c-5293-a28f-5b722c9917a2"', '"foreign"'),
        (
            '"3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71"',
            '"foreign"',
        ),
        ('"30e31396-9f51-57ca-a480-d2a3e9cae4a0"', '"foreign"'),
        (
            "datetime(2026, 9, 30, 22, 7, 24, tzinfo=UTC)",
            "datetime(2026, 9, 30, 22, 7, 25, tzinfo=UTC)",
        ),
        (
            "datetime(2026, 10, 7, 22, 7, 24, tzinfo=UTC)",
            "datetime(2026, 10, 7, 22, 7, 25, tzinfo=UTC)",
        ),
        ("MINIMUM_DAILY_WAKE_COUNT: Final = 7", "MINIMUM_DAILY_WAKE_COUNT: Final = 6"),
        ("summary.wake_count < MINIMUM_DAILY_WAKE_COUNT", "summary.wake_count != 7"),
        ("reviewed_at_utc < END_UTC", "reviewed_at_utc <= END_UTC"),
        ("value.tzinfo is UTC", "value.tzinfo is not None"),
        ("type(item) is not D10OneWeekWakeEvidence", "False"),
        ("build_d10_one_week_wake_summary(wakes)", "None"),
        ("wake.certified_source_head != first.certified_source_head", "False"),
        ("wake.certified_source_tree != first.certified_source_tree", "False"),
        ("wake.executable_file_count != first.executable_file_count", "False"),
        (
            "ACTIVATION_UTC <= wake.observed_at_utc < END_UTC",
            "ACTIVATION_UTC <= wake.observed_at_utc <= END_UTC",
        ),
        ("D10WakeOutcome.NO_ACTION,", "D10WakeOutcome.STOPPED,"),
        ("wake.stop_reason is not None", "False"),
        ("wake.historical_unresolved_decision_id is not None", "False"),
        ("wake.all_effect_gates_closed is not True", "False"),
        ("wake.closed_effect_gate_count != 8", "wake.closed_effect_gate_count != 7"),
        ("wake.receipt_recovery_attempts != 0", "wake.receipt_recovery_attempts > 1"),
        ("wake.broker_live_calls != 0", "wake.broker_live_calls > 1"),
        ("count not in (0, 1)", "count not in (0, 1, 2)"),
        ("summary.stopped_count != 0", "False"),
        ("summary.stop_counts != ()", "False"),
        ("summary.all_effect_gates_closed is not True", "False"),
        ('"SCHEDULER_SLOT_COVERAGE",', '"AUTOMATIC_COVERAGE",'),
        ('"ELIGIBLE_XNYS_SESSION_COVERAGE",', '"AUTOMATIC_COVERAGE",'),
        ('"SLEEP_REBOOT_DUPLICATE_CONTEXT",', '"AUTOMATIC_COVERAGE",'),
        ('"PAPER_V2_ACCOUNT_TRADES_POSITIONS_PERFORMANCE",', '"AUTOMATIC_COVERAGE",'),
        ('"AUDIT_COMPLETENESS",', '"AUTOMATIC_COVERAGE",'),
        ('"d10_accepted": False', '"d10_accepted": True'),
        ('"broker_paper_authorized": False', '"broker_paper_authorized": True'),
        ('"operator_decision_required": True', '"operator_decision_required": False'),
    ),
)
def test_soak_review_authority_freezes_every_policy(tmp_path, old, new):
    root = _soak_review_authority_copy(tmp_path, old=old, new=new)
    assert runner._d10_soak_review_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            "authority_check=_d10_soak_review_authority_check,",
            "authority_check=_d10_soak_review_authority_check, "
            "preflight=_r8_preflight,",
        ),
        (
            "authority_check=_d10_soak_review_authority_check,",
            "authority_check=_d10_soak_review_authority_check, execute=_r7_execute,",
        ),
        (
            "authority_check=_d10_soak_review_authority_check,",
            "authority_check=_r8_authority_check,",
        ),
        (
            'remote_branch="feature/post-d10-observability",',
            'remote_branch="feature/d10c-durable-wake-evidence",',
        ),
        (
            'remote_branch="feature/post-d10-observability",',
            'remote_branch="feature/post-d10-observability", remote_head_env="HEAD",',
        ),
    ),
)
def test_soak_review_authority_freezes_verify_only_registration(tmp_path, old, new):
    root = _soak_review_authority_copy(tmp_path, runner_old=old, runner_new=new)
    assert runner._d10_soak_review_authority_check(root)


def test_soak_review_authority_blocks_missing_or_invalid_source(tmp_path):
    assert runner._d10_soak_review_authority_check(tmp_path)
    root = _soak_review_authority_copy(tmp_path, addition="def invalid(")
    assert runner._d10_soak_review_authority_check(root)


def test_external_review_package_registration_is_verify_only() -> None:
    specs = runner._checkpoint_specs()
    spec = specs["d10-external-review-package"]
    assert spec.preflight is None
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/post-d10-observability"
    assert spec.authority_check is runner._d10_external_review_package_authority_check
    assert spec.tests == (
        *specs["d10-soak-review"].tests,
        "tests/runtime/test_d10_external_review_package.py",
    )
    assert spec.ruff_paths == (
        *specs["d10-soak-review"].ruff_paths,
        "scripts/d10_external_review_package.py",
        "tests/runtime/test_d10_external_review_package.py",
    )
    parser = runner._parser(specs)
    assert parser.parse_args(("verify", spec.name)).checkpoint == spec.name
    for command in ("preflight", "execute"):
        with pytest.raises(SystemExit):
            parser.parse_args((command, spec.name))
    # Independently retained operational registrations and authority profiles.
    assert specs["d10-soak-status"].preflight is runner._d10_soak_status_preflight
    assert specs["d10-soak-status"].execute is None
    assert specs["d10-soak-review"].preflight is None
    assert specs["d10-soak-review"].execute is None
    assert specs["arch128-r8"].preflight is runner._r8_preflight
    assert specs["arch128-r8"].execute is None
    assert specs["arch128-r8"].remote_branch == "feature/d10c-durable-wake-evidence"


def _external_review_authority_copy(
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
    source = (root / "scripts/d10_external_review_package.py").read_text(
        encoding="utf-8"
    )
    if old:
        assert old in source
        source = source.replace(old, new, 1)
    if addition:
        source += "\n" + addition + "\n"
    (target / "d10_external_review_package.py").write_text(source, encoding="utf-8")
    # The S2B authority gate also preserves S2A's accepted source contract.
    (target / "d10_end_of_soak_review.py").write_text(
        (root / "scripts/d10_end_of_soak_review.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    runner_source = (root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    if runner_old:
        start = runner_source.index(
            '        "d10-external-review-package": CheckpointSpec('
        )
        end = runner_source.index('        "arch128-r8": CheckpointSpec(', start)
        registration = runner_source[start:end]
        assert runner_old in registration
        runner_source = (
            runner_source[:start]
            + registration.replace(runner_old, runner_new, 1)
            + runner_source[end:]
        )
    (target / "checkpoint_runner.py").write_text(runner_source, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    (
        "import os",
        "import subprocess",
        "import ctypes",
        "from pathlib import Path",
        "import socket",
        "from scripts import d10_soak_status_readonly as observer",
        "open('evidence')",
        "Path('evidence').read_bytes()",
        "Path('evidence').write_text('data')",
        "os.environ['TOKEN']",
        "subprocess.run([])",
        "ctypes.WinDLL('kernel32')",
        "datetime.now(UTC)",
        "datetime.today()",
        "observer.observe()",
        "internal_review_policy.analyze(())",
        "scheduler.Run(None)",
        "scheduler.RegisterTaskDefinition()",
        "credential.read()",
        "provider.capture()",
        "paper_v2.execute()",
        "broker.order()",
        "live.execute()",
        "__import__('os')",
        "eval('effect()')",
        "def preflight(): pass",
        "def execute(): pass",
        "production_observer = internal_review_policy",
    ),
)
def test_external_review_authority_rejects_io_or_effect_additions(tmp_path, addition):
    root = _external_review_authority_copy(tmp_path, addition=addition)
    assert runner._d10_external_review_package_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ('SCHEMA: Final = "d10-external-review-package/v1"', 'SCHEMA: Final = "other"'),
        (
            "DEPLOYMENT_ID: Final = internal_review_policy.DEPLOYMENT_ID",
            'DEPLOYMENT_ID: Final = "foreign"',
        ),
        (
            "SOAK_ID: Final = internal_review_policy.SOAK_ID",
            'SOAK_ID: Final = "foreign"',
        ),
        (
            "ATTESTATION_SHA256: Final = internal_review_policy.ATTESTATION_SHA256",
            'ATTESTATION_SHA256: Final = "foreign"',
        ),
        (
            "ACTIVATION_UTC: Final = internal_review_policy.ACTIVATION_UTC",
            "ACTIVATION_UTC: Final = END_UTC",
        ),
        (
            "END_UTC: Final = internal_review_policy.END_UTC",
            "END_UTC: Final = ACTIVATION_UTC",
        ),
        ('AUDIT_COMPLETENESS = "AUDIT_COMPLETENESS"', 'AUDIT_COMPLETENESS = "OTHER"'),
        (
            'AUDIT_COMPLETENESS = "AUDIT_COMPLETENESS"',
            'AUDIT_COMPLETENESS = "AUDIT_COMPLETENESS"\n    EXTRA = "EXTRA"',
        ),
        ("@dataclass(frozen=True, slots=True)", "@dataclass(frozen=False, slots=True)"),
        ("type(review) is not dict", "False"),
        ("set(review) != set(INTERNAL_REVIEW_FIELDS)", "False"),
        ('review["schema"] != internal_review_policy.SCHEMA', "False"),
        ('review["status"] != "READY_FOR_OPERATOR_REVIEW"', "False"),
        ('review["internal_wake_evidence"] != "PASS"', "False"),
        ('review["d10_accepted"] is not False', "False"),
        ('review["broker_paper_authorized"] is not False', "False"),
        ('review["operator_decision_required"] is not True', "False"),
        ('review["minimum_daily_wake_count_met"] is not True', "False"),
        ("required != internal_review_policy.EXTERNAL_REVIEW_REQUIRED", "False"),
        ('review["wake_count"] < 7', "False"),
        (
            'review["completed_count"] + review["no_action_count"] '
            '!= review["wake_count"]',
            "False",
        ),
        ('review["stopped_count"] != 0', "False"),
        ('review["extra_wake_count"] != review["wake_count"] - 7', "False"),
        ('review["executable_file_count"] <= 0', "False"),
        ("type(review[field]) is not str or not review[field]", "False"),
        ("value.tzinfo is UTC", "value.tzinfo is not None"),
        ("_timestamp(parsed) != value", "False"),
        ("ACTIVATION_UTC <= first <= last < END_UTC", "first <= last"),
        ("END_UTC <= reviewed <= packaged_at_utc", "True"),
        ("packaged_at_utc < END_UTC", "packaged_at_utc <= END_UTC"),
        ("type(external_reviews) is not tuple", "False"),
        ("type(item) is not D10ExternalReviewEvidence", "False"),
        ("len(external_reviews) != 5", "len(external_reviews) < 5"),
        ("type(item.category) is not D10ExternalReviewCategory", "False"),
        ("len(by_category) != 5", "False"),
        ("set(by_category) != set(CATEGORY_ORDER)", "False"),
        (
            "tuple(by_category[category] for category in CATEGORY_ORDER)",
            "external_reviews",
        ),
        ("item.deployment_id != DEPLOYMENT_ID", "False"),
        ("item.soak_id != SOAK_ID", "False"),
        ("item.activation_utc != ACTIVATION_UTC", "False"),
        ("item.end_utc != END_UTC", "False"),
        ("END_UTC <= item.reviewed_at_utc <= packaged_at_utc", "True"),
        ('re.fullmatch(r"[0-9a-f]{64}", item.artifact_sha256) is None', "False"),
        ("item.artifact_byte_length <= 0", "False"),
        ("item.complete is not True", "False"),
        ("item.unresolved_findings != 0", "False"),
        ('"d10_accepted": False', '"d10_accepted": True'),
        ('"broker_paper_authorized": False', '"broker_paper_authorized": True'),
        ('"operator_decision_required": True', '"operator_decision_required": False'),
        ('"status": "READY_FOR_OPERATOR_DECISION"', '"status": "ACCEPTED"'),
        ('"status": "READY_FOR_OPERATOR_DECISION"', '"status": "GRADUATED"'),
        ('"status": "READY_FOR_OPERATOR_DECISION"', '"status": "BROKER_READY"'),
        ('"status": "READY_FOR_OPERATOR_DECISION"', '"status": "GO_LIVE"'),
        ('"status": "READY_FOR_OPERATOR_DECISION"', '"status": "APPROVED"'),
        ('"category": item.category.value', '"category": item'),
    ),
)
def test_external_review_authority_freezes_every_policy(tmp_path, old, new):
    root = _external_review_authority_copy(tmp_path, old=old, new=new)
    assert runner._d10_external_review_package_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            "authority_check=_d10_external_review_package_authority_check,",
            "authority_check=_d10_external_review_package_authority_check, "
            "preflight=_r8_preflight,",
        ),
        (
            "authority_check=_d10_external_review_package_authority_check,",
            "authority_check=_d10_external_review_package_authority_check, "
            "execute=_r7_execute,",
        ),
        (
            "authority_check=_d10_external_review_package_authority_check,",
            "authority_check=_r8_authority_check,",
        ),
        (
            'remote_branch="feature/post-d10-observability",',
            'remote_branch="feature/d10c-durable-wake-evidence",',
        ),
        (
            'remote_branch="feature/post-d10-observability",',
            'remote_branch="feature/post-d10-observability", remote_head_env="HEAD",',
        ),
    ),
)
def test_external_review_authority_freezes_verify_only_registration(tmp_path, old, new):
    root = _external_review_authority_copy(tmp_path, runner_old=old, runner_new=new)
    assert runner._d10_external_review_package_authority_check(root)


def test_external_review_authority_blocks_missing_or_invalid_source(tmp_path):
    assert runner._d10_external_review_package_authority_check(tmp_path)
    root = _external_review_authority_copy(tmp_path, addition="def invalid(")
    assert runner._d10_external_review_package_authority_check(root)


def test_external_review_authority_preserves_upstream_frozen_identity(tmp_path):
    root = _external_review_authority_copy(tmp_path)
    path = root / "scripts/d10_end_of_soak_review.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace('"d2071f25-5a7c-5293-a28f-5b722c9917a2"', '"foreign"', 1)
    path.write_text(source, encoding="utf-8")
    assert runner._d10_external_review_package_authority_check(root)


def test_scheduler_slot_registration_is_verify_only() -> None:
    specs = runner._checkpoint_specs()
    spec = specs["d10-scheduler-slot-policy"]
    assert spec.preflight is None
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/post-d10-observability"
    assert spec.authority_check is runner._d10_scheduler_slot_policy_authority_check
    assert spec.tests == (
        *specs["d10-external-review-package"].tests,
        "tests/runtime/test_d10_scheduler_slot_review_policy.py",
    )
    assert spec.ruff_paths == (
        *specs["d10-external-review-package"].ruff_paths,
        "scripts/d10_scheduler_slot_review_policy.py",
        "tests/runtime/test_d10_scheduler_slot_review_policy.py",
    )
    parser = runner._parser(specs)
    assert parser.parse_args(("verify", spec.name)).checkpoint == spec.name
    for command in ("preflight", "execute"):
        with pytest.raises(SystemExit):
            parser.parse_args((command, spec.name))
    assert specs["arch128-r8"].preflight is runner._r8_preflight
    assert specs["arch128-r8"].execute is None
    assert specs["arch128-r8"].remote_branch == "feature/d10c-durable-wake-evidence"
    assert specs["d10-soak-status"].preflight is runner._d10_soak_status_preflight
    assert specs["d10-soak-status"].execute is None
    assert specs["d10-soak-review"].preflight is None
    assert specs["d10-soak-review"].execute is None
    assert specs["d10-external-review-package"].preflight is None
    assert specs["d10-external-review-package"].execute is None


def _scheduler_slot_authority_copy(
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
    for filename in (
        "d10_end_of_soak_review.py",
        "d10_external_review_package.py",
        "d10_scheduler_slot_review_policy.py",
        "checkpoint_runner.py",
    ):
        source = (root / "scripts" / filename).read_text(encoding="utf-8")
        if filename == "d10_scheduler_slot_review_policy.py":
            if old:
                assert old in source
                source = source.replace(old, new, 1)
            source += "\n" + addition + "\n"
        if filename == "checkpoint_runner.py" and runner_old:
            start = source.index('        "d10-scheduler-slot-policy": CheckpointSpec(')
            end = source.index('        "arch128-r8": CheckpointSpec(', start)
            registration = source[start:end]
            assert runner_old in registration
            source = (
                source[:start]
                + registration.replace(runner_old, runner_new, 1)
                + source[end:]
            )
        (target / filename).write_text(source, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "addition",
    (
        "import os",
        "import subprocess",
        "import ctypes",
        "from pathlib import Path",
        "import socket",
        "from win32com.client import Dispatch",
        "import win32evtlog",
        "from scripts import d10_soak_status_readonly as observer",
        "open('evidence')",
        "Path('evidence').read_bytes()",
        "os.environ['TOKEN']",
        "subprocess.run([])",
        "ctypes.WinDLL('kernel32')",
        "datetime.now(UTC)",
        "EventLogReader()",
        "Get_WinEvent()",
        "powershell()",
        "scheduler.Run(None)",
        "scheduler.RegisterTaskDefinition()",
        "observer.observe()",
        "provider.capture()",
        "paper_v2.execute()",
        "broker.order()",
        "live.execute()",
        "__import__('os')",
        "eval('effect()')",
        "def preflight(): pass",
        "def execute(): pass",
        "production_observer = internal_review_policy",
    ),
)
def test_scheduler_slot_authority_rejects_io_or_effect_additions(tmp_path, addition):
    root = _scheduler_slot_authority_copy(tmp_path, addition=addition)
    assert runner._d10_scheduler_slot_policy_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ('SCHEMA: Final = "d10-scheduler-slot-review/v1"', 'SCHEMA: Final = "other"'),
        (
            "DEPLOYMENT_ID: Final = internal_review_policy.DEPLOYMENT_ID",
            'DEPLOYMENT_ID: Final = "foreign"',
        ),
        (
            "SOAK_ID: Final = internal_review_policy.SOAK_ID",
            'SOAK_ID: Final = "foreign"',
        ),
        (
            "ACTIVATION_UTC: Final = internal_review_policy.ACTIVATION_UTC",
            "ACTIVATION_UTC: Final = END_UTC",
        ),
        (
            "END_UTC: Final = internal_review_policy.END_UTC",
            "END_UTC: Final = ACTIVATION_UTC",
        ),
        (
            'TASK_PATH: Final = r"\\AITradingBot-PD4-UnattendedPaper-v1"',
            'TASK_PATH: Final = "foreign"',
        ),
        ("SLOT_COUNT: Final = 7", "SLOT_COUNT: Final = 6"),
        (
            "D10SchedulerHistoryEventKind.SCHEDULED_TRIGGER: 107",
            "D10SchedulerHistoryEventKind.SCHEDULED_TRIGGER: 100",
        ),
        (
            "D10SchedulerHistoryEventKind.MANUAL_TRIGGER: 110",
            "D10SchedulerHistoryEventKind.MANUAL_TRIGGER: 111",
        ),
        (
            "D10SchedulerHistoryEventKind.TASK_STARTED: 100",
            "D10SchedulerHistoryEventKind.TASK_STARTED: 107",
        ),
        (
            "D10SchedulerHistoryEventKind.TASK_COMPLETED: 102",
            "D10SchedulerHistoryEventKind.TASK_COMPLETED: 101",
        ),
        ('TASK_COMPLETED = "TASK_COMPLETED"', 'TASK_COMPLETED = "OTHER"'),
        ("@dataclass(frozen=True, slots=True)", "@dataclass(frozen=False, slots=True)"),
        ("type(observation) is not D10SchedulerHistoryObservation", "False"),
        ("type(observation.events) is not tuple", "False"),
        ("type(event) is not D10SchedulerHistoryEvent", "False"),
        ("type(event.kind) is not D10SchedulerHistoryEventKind", "False"),
        ("event.event_id != EVENT_IDS[event.kind]", "False"),
        ("event.record_id <= 0", "False"),
        ("event.task_name != TASK_PATH", "False"),
        ("value.tzinfo is UTC", "value.tzinfo is not None"),
        ("len(value) == 36", "len(value) >= 36"),
        ("not _instance_id(event.instance_id)", "False"),
        ("observation.collected_at_utc < END_UTC", "False"),
        ("observation.channel_enabled is not True", "False"),
        ("observation.oldest_retained_event_utc > ACTIVATION_UTC", "False"),
        ("ACTIVATION_UTC <= event.observed_at_utc < END_UTC", "True"),
        ("event.record_id <= previous_record", "False"),
        ("event.observed_at_utc < previous_time", "False"),
        ("event.kind is D10SchedulerHistoryEventKind.MANUAL_TRIGGER", "False"),
        ('return _blocked("manual_task_trigger_observed")', "pass"),
        ("spec.__post_init__()", "pass"),
        ("spec.task.days_interval != 1", "False"),
        ("spec.window.activation_utc != ACTIVATION_UTC", "False"),
        ("spec.window.end_utc != END_UTC", "False"),
        ("spec.end_boundary.astimezone(UTC) != END_UTC", "False"),
        ("boundary = spec.task.start_boundary", "boundary = ACTIVATION_UTC"),
        ("timedelta(days=spec.task.days_interval)", "timedelta(days=2)"),
        ("len(slots) != SLOT_COUNT", "False"),
        ("slots = expected_slots_utc()", "slots = observation.expected_slots"),
        ("len(triggers) != SLOT_COUNT", "False"),
        ("len({event.instance_id for event in triggers}) != SLOT_COUNT", "False"),
        ("event.observed_at_utc < slots[0]", "False"),
        ("slot <= event.observed_at_utc < interval_end", "True"),
        ("if not matched:", "if False:"),
        ("len(matched) != 1", "False"),
        ("event.instance_id not in scheduled_ids", "False"),
        ("event.instance_id == trigger.instance_id", "True"),
        ("if not starts:", "if False:"),
        ("len(starts) != 1", "False"),
        ("if not completions:", "if False:"),
        ("len(completions) != 1", "False"),
        (
            "<= start.observed_at_utc",
            ">= start.observed_at_utc",
        ),
        ('"d10_accepted": False', '"d10_accepted": True'),
        ('"broker_paper_authorized": False', '"broker_paper_authorized": True'),
        ('"operator_decision_required": True', '"operator_decision_required": False'),
        ('"status": "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"', '"status": "ACCEPTED"'),
    ),
)
def test_scheduler_slot_authority_freezes_every_policy(tmp_path, old, new):
    root = _scheduler_slot_authority_copy(tmp_path, old=old, new=new)
    assert runner._d10_scheduler_slot_policy_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            "authority_check=_d10_scheduler_slot_policy_authority_check,",
            "authority_check=_d10_scheduler_slot_policy_authority_check, "
            "preflight=_r8_preflight,",
        ),
        (
            "authority_check=_d10_scheduler_slot_policy_authority_check,",
            "authority_check=_d10_scheduler_slot_policy_authority_check, "
            "execute=_r7_execute,",
        ),
        (
            "authority_check=_d10_scheduler_slot_policy_authority_check,",
            "authority_check=_r8_authority_check,",
        ),
        (
            'remote_branch="feature/post-d10-observability",',
            'remote_branch="feature/d10c-durable-wake-evidence",',
        ),
        (
            'remote_branch="feature/post-d10-observability",',
            'remote_branch="feature/post-d10-observability", remote_head_env="HEAD",',
        ),
    ),
)
def test_scheduler_slot_authority_freezes_registration(tmp_path, old, new):
    root = _scheduler_slot_authority_copy(tmp_path, runner_old=old, runner_new=new)
    assert runner._d10_scheduler_slot_policy_authority_check(root)


def test_scheduler_slot_authority_accepts_exact_source():
    root = Path(runner.__file__).resolve().parent.parent
    assert runner._d10_scheduler_slot_policy_authority_check(root) == ()


def test_scheduler_slot_authority_blocks_missing_or_invalid_source(tmp_path):
    assert runner._d10_scheduler_slot_policy_authority_check(tmp_path)
    root = _scheduler_slot_authority_copy(tmp_path, addition="def invalid(")
    assert runner._d10_scheduler_slot_policy_authority_check(root)


@pytest.mark.parametrize(
    "filename", ("d10_end_of_soak_review.py", "d10_external_review_package.py")
)
def test_scheduler_slot_authority_preserves_upstream_contracts(tmp_path, filename):
    root = _scheduler_slot_authority_copy(tmp_path)
    path = root / "scripts" / filename
    source = path.read_text(encoding="utf-8")
    source = source.replace('"d10_accepted": False', '"d10_accepted": True', 1)
    path.write_text(source, encoding="utf-8")
    assert runner._d10_scheduler_slot_policy_authority_check(root)


def test_scheduler_history_registration_is_verify_only():
    specs = runner._checkpoint_specs()
    spec = specs["d10-scheduler-history-collector"]
    upstream = specs["d10-scheduler-slot-policy"]
    assert spec.preflight is None
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/post-d10-observability"
    assert (
        spec.authority_check is runner._d10_scheduler_history_collector_authority_check
    )
    assert spec.tests == (
        *upstream.tests,
        "tests/runtime/test_d10_scheduler_history_windows.py",
    )
    assert spec.ruff_paths == (
        *upstream.ruff_paths,
        "scripts/d10_scheduler_history_windows.py",
        "tests/runtime/test_d10_scheduler_history_windows.py",
    )
    parser = runner._parser(specs)
    assert parser.parse_args(("verify", spec.name)).checkpoint == spec.name
    for command in ("preflight", "execute"):
        with pytest.raises(SystemExit):
            parser.parse_args((command, spec.name))
    # The accepted hierarchy retains its original operational boundaries.
    assert upstream.preflight is None and upstream.execute is None
    assert specs["d10-soak-status"].preflight is runner._d10_soak_status_preflight
    assert specs["d10-soak-status"].execute is None
    for name in ("d10-soak-review", "d10-external-review-package"):
        assert specs[name].preflight is None and specs[name].execute is None
    assert specs["arch128-r8"].preflight is runner._r8_preflight
    assert specs["arch128-r8"].execute is None
    assert specs["arch128-r8"].remote_branch == "feature/d10c-durable-wake-evidence"


def _scheduler_history_authority_copy(tmp_path):
    root = _scheduler_slot_authority_copy(tmp_path)
    source_root = Path(runner.__file__).resolve().parent.parent
    for name in (
        "d10_scheduler_history_windows.py",
        "d10_scheduler_history_observe.ps1",
    ):
        (root / "scripts" / name).write_bytes(
            (source_root / "scripts" / name).read_bytes()
        )
    return root


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("shell=False", "shell=True"),
        ("stdin=subprocess.DEVNULL", "stdin=subprocess.PIPE"),
        ("TIMEOUT_SECONDS = 60", "TIMEOUT_SECONDS = 600"),
        ("MAX_STDOUT = 256 * 1024", "MAX_STDOUT = 1024 * 1024"),
        ("MAX_STDERR = 256", "MAX_STDERR = 1024"),
        ("MAX_TARGET_EVENTS = 256", "MAX_TARGET_EVENTS = 512"),
        (
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "powershell.exe",
        ),
        ("d10_scheduler_history_observe.ps1", "alternate.ps1"),
        ('"-NonInteractive"', '"-Command"'),
        ("str(HELPER)", "os.environ['HELPER']"),
        ("def observe()", "def observe(arguments)"),
        (
            "policy.analyze(observation)",
            "policy.analyze(observation); policy.analyze(observation)",
        ),
        (
            "code = process.wait(timeout=TIMEOUT_SECONDS)",
            "while True: code = process.wait(timeout=TIMEOUT_SECONDS)",
        ),
        ('"event_log_mutation": "NOT_RUN"', '"event_log_mutation": "RUN"'),
        ("policy.EVENT_IDS.items()", "{'OTHER': 999}.items()"),
        ("str(UUID(value)) != value", "False"),
        (
            r'r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z"',
            'r".*"',
        ),
    ),
)
def test_scheduler_history_authority_rejects_transport_or_projection_drift(
    tmp_path, old, new
):
    root = _scheduler_history_authority_copy(tmp_path)
    path = root / "scripts/d10_scheduler_history_windows.py"
    source = path.read_text(encoding="utf-8")
    assert old in source
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    assert runner._d10_scheduler_history_collector_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    (
        "import os",
        "import ctypes",
        "from win32com.client import Dispatch",
        "raw_xml = '<Event />'",
        "message = event.Message",
        "provider.capture()",
        "paper_v2.execute()",
        "broker.order()",
        "live.execute()",
        "scheduler.Run(None)",
        "scheduler.RegisterTaskDefinition()",
        "observe()",
        "subprocess.run([])",
        "def preflight(): pass",
        "def execute(): pass",
    ),
)
def test_scheduler_history_authority_rejects_new_python_surfaces(tmp_path, addition):
    root = _scheduler_history_authority_copy(tmp_path)
    path = root / "scripts/d10_scheduler_history_windows.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n", encoding="utf-8"
    )
    assert runner._d10_scheduler_history_collector_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    (
        "# changed helper",
        "wevtutil sl channel /e:true",
        "Clear-EventLog channel",
        "Limit-EventLog channel",
        "Write-EventLog channel",
        "New-EventLog channel",
        "Remove-EventLog channel",
        "Set-WinEvent channel",
        "Enable-ScheduledTask task",
        "Disable-ScheduledTask task",
        "Start-ScheduledTask task",
        "Stop-ScheduledTask task",
        "Register-ScheduledTask task",
        "Unregister-ScheduledTask task",
        "schtasks /run",
        "New-Object -ComObject Schedule.Service",
        "$task.Run($null)",
        "$task.RegisterTaskDefinition()",
        "$events.Add($_.Message)",
        "$events.Add($_.ToXml())",
    ),
)
def test_scheduler_history_authority_rejects_any_helper_mutation(tmp_path, addition):
    root = _scheduler_history_authority_copy(tmp_path)
    path = root / "scripts/d10_scheduler_history_observe.ps1"
    path.write_bytes(path.read_bytes() + addition.encode("ascii") + b"\r\n")
    assert runner._d10_scheduler_history_collector_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("100000", "100001"),
        ("256", "512"),
        ("@(100, 102, 107, 110)", "@(100, 102)"),
        ("2026-09-30T22:07:24.000000Z", "2026-09-29T22:07:24.000000Z"),
        ("2026-10-07T22:07:24.000000Z", "2026-10-08T22:07:24.000000Z"),
        ("Microsoft-Windows-TaskScheduler/Operational", "System"),
        (r"\AITradingBot-PD4-UnattendedPaper-v1", r"\Foreign"),
        ("$instant.Ticks % 10", "$instant.Ticks % 1"),
        (".ToString('D').ToLowerInvariant()", ".ToString('B')"),
        ("if ($args.Count -ne 0)", "if ($false)"),
    ),
)
def test_scheduler_history_authority_freezes_helper_bounds_and_identity(
    tmp_path, old, new
):
    root = _scheduler_history_authority_copy(tmp_path)
    path = root / "scripts/d10_scheduler_history_observe.ps1"
    data = path.read_bytes()
    assert old.encode("ascii") in data
    path.write_bytes(data.replace(old.encode("ascii"), new.encode("ascii"), 1))
    assert runner._d10_scheduler_history_collector_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            "authority_check=_d10_scheduler_history_collector_authority_check,",
            "authority_check=_d10_scheduler_history_collector_authority_check, "
            "preflight=_r8_preflight,",
        ),
        (
            "authority_check=_d10_scheduler_history_collector_authority_check,",
            "authority_check=_d10_scheduler_history_collector_authority_check, "
            "execute=_r7_execute,",
        ),
        (
            'remote_branch="feature/post-d10-observability",',
            'remote_branch="feature/d10c-durable-wake-evidence",',
        ),
        (
            'remote_branch="feature/post-d10-observability",',
            'remote_branch="feature/post-d10-observability", remote_head_env="HEAD",',
        ),
        ("tests=scheduler_history_tests,", "tests=scheduler_slot_tests,"),
        ("ruff_paths=scheduler_history_ruff,", "ruff_paths=scheduler_slot_ruff,"),
    ),
)
def test_scheduler_history_authority_freezes_registration(tmp_path, old, new):
    root = _scheduler_history_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index('        "d10-scheduler-history-collector": CheckpointSpec(')
    end = source.index('        "arch128-r8": CheckpointSpec(', start)
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new, 1) + source[end:],
        encoding="utf-8",
    )
    assert runner._d10_scheduler_history_collector_authority_check(root)


@pytest.mark.parametrize(
    "filename",
    (
        "d10_scheduler_slot_review_policy.py",
        "d10_external_review_package.py",
        "d10_end_of_soak_review.py",
    ),
)
def test_scheduler_history_authority_composes_upstream(tmp_path, filename):
    root = _scheduler_history_authority_copy(tmp_path)
    path = root / "scripts" / filename
    source = path.read_text(encoding="utf-8")
    path.write_text(
        source.replace('"d10_accepted": False', '"d10_accepted": True', 1),
        encoding="utf-8",
    )
    assert runner._d10_scheduler_history_collector_authority_check(root)


def test_scheduler_history_authority_accepts_source_without_observation(monkeypatch):
    from scripts import d10_scheduler_history_windows as collector

    monkeypatch.setattr(
        collector, "observe", lambda: pytest.fail("source gate must not collect")
    )
    monkeypatch.setattr(
        collector.subprocess, "Popen", lambda *a, **k: pytest.fail("no helper")
    )
    root = Path(runner.__file__).resolve().parent.parent
    assert runner._d10_scheduler_history_collector_authority_check(root) == ()


def test_scheduler_history_authority_missing_source_blocks(tmp_path):
    assert runner._d10_scheduler_history_collector_authority_check(tmp_path)
    root = _scheduler_history_authority_copy(tmp_path)
    (root / "scripts/d10_scheduler_history_windows.py").write_text(
        "def invalid(", encoding="utf-8"
    )
    assert runner._d10_scheduler_history_collector_authority_check(root)


def test_xnys_session_registration_is_verify_only():
    specs = runner._checkpoint_specs()
    spec = specs["d10-xnys-session-coverage-policy"]
    upstream = specs["d10-scheduler-history-collector"]
    assert spec.preflight is None
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/post-d10-observability"
    assert (
        spec.authority_check is runner._d10_xnys_session_coverage_policy_authority_check
    )
    assert spec.tests == (
        *upstream.tests,
        "tests/runtime/test_d10_xnys_session_coverage_policy.py",
        "tests/runtime/test_personal_desktop_unattended_daily_cycle_timing.py",
        "tests/market_calendar/test_nyse_calendar.py",
    )
    assert spec.ruff_paths == (
        *upstream.ruff_paths,
        "scripts/d10_xnys_session_coverage_policy.py",
        "tests/runtime/test_d10_xnys_session_coverage_policy.py",
    )
    parser = runner._parser(specs)
    assert parser.parse_args(("verify", spec.name)).checkpoint == spec.name
    for command in ("preflight", "execute"):
        with pytest.raises(SystemExit):
            parser.parse_args((command, spec.name))


def _xnys_session_authority_copy(tmp_path, *, old="", new="", addition=""):
    root = _scheduler_history_authority_copy(tmp_path)
    path = Path(runner.__file__).parent / "d10_xnys_session_coverage_policy.py"
    source = path.read_text(encoding="utf-8")
    if old:
        assert old in source
        source = source.replace(old, new, 1)
    (root / "scripts/d10_xnys_session_coverage_policy.py").write_text(
        source + "\n" + addition + "\n", encoding="utf-8"
    )
    return root


@pytest.mark.parametrize(
    "addition",
    (
        "import os",
        "import subprocess",
        "import ctypes",
        "from pathlib import Path",
        "from trading_bot.market_calendar import NYSEMarketCalendar",
        "from scripts import d10_soak_status_readonly as observer",
        "from scripts import d10_scheduler_history_windows as collector",
        "open('evidence')",
        "Path('evidence').read_bytes()",
        "os.environ['TOKEN']",
        "subprocess.run([])",
        "ctypes.WinDLL('kernel32')",
        "datetime.now(UTC)",
        "datetime.today()",
        "observer.observe()",
        "collector.observe()",
        "provider.capture()",
        "paper_v2.execute()",
        "broker.order()",
        "live.execute()",
        "NYSEMarketCalendar().previous_session(None)",
        "def independent_calendar(value): return value.weekday() < 5",
        "def preflight(): pass",
        "def execute(): pass",
        "__import__('os')",
        "eval('effect()')",
    ),
)
def test_xnys_session_authority_rejects_io_effect_clock_calendar(tmp_path, addition):
    root = _xnys_session_authority_copy(tmp_path, addition=addition)
    assert runner._d10_xnys_session_coverage_policy_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            'SCHEMA: Final = "d10-xnys-session-coverage-review/v1"',
            'SCHEMA: Final = "other"',
        ),
        ("internal_review_policy.DEPLOYMENT_ID", "'foreign'"),
        ("internal_review_policy.ATTESTATION_SHA256", "'foreign'"),
        ("internal_review_policy.SOAK_ID", "'foreign'"),
        ("internal_review_policy.ACTIVATION_UTC", "END_UTC"),
        ("internal_review_policy.END_UTC", "ACTIVATION_UTC"),
        ("type(wakes) is not tuple", "False"),
        ("not 7 <= len(wakes) <= MAX_D10_SUMMARY_WAKES", "False"),
        ("type(wake) is not D10OneWeekWakeEvidence", "False"),
        ("value.tzinfo is UTC", "value.tzinfo is not None"),
        ("reviewed_at_utc < END_UTC", "False"),
        ("type(value) is not str", "False"),
        ("len(value) != 10", "False"),
        ("parsed.isoformat() != value", "False"),
        ("slot_policy.expected_slots_utc()", "caller_slots()"),
        ("len(slots) != 7", "len(slots) != 6"),
        ("timing.completed_xnys_session_at(slot)", "TradingSession(date(2026, 9, 30))"),
        ("dict.fromkeys(values)", "sorted(set(values))"),
        ("wake.deployment_id != DEPLOYMENT_ID", "False"),
        ("wake.attestation_sha256 != ATTESTATION_SHA256", "False"),
        ("wake.soak_id != SOAK_ID", "False"),
        ("wake.activation_utc != ACTIVATION_UTC", "False"),
        ("wake.end_utc != END_UTC", "False"),
        ("not wake.certified_source_head", "False"),
        ("not wake.certified_source_tree", "False"),
        ("wake.executable_file_count <= 0", "False"),
        ("wake.certified_source_head != first.certified_source_head", "False"),
        ("wake.certified_source_tree != first.certified_source_tree", "False"),
        ("wake.executable_file_count != first.executable_file_count", "False"),
        ("ACTIVATION_UTC <= wake.observed_at_utc < END_UTC", "True"),
        ("wake.observed_at_utc < previous_time", "False"),
        ("type(wake.outcome) is not D10WakeOutcome", "False"),
        ("D10WakeOutcome.NO_ACTION)", "D10WakeOutcome.STOPPED)"),
        ("wake.stop_reason is not None", "False"),
        ("wake.all_effect_gates_closed is not True", "False"),
        ("wake.closed_effect_gate_count != 8", "False"),
        ("wake.receipt_recovery_attempts != 0", "False"),
        ("wake.broker_live_calls != 0", "False"),
        ("count not in (0, 1)", "count not in (1,)"),
        ("timing.completed_xnys_session_at(wake.observed_at_utc)", "completed_session"),
        ("completed_session != expected_session", "False"),
        ("timing.next_xnys_execution_session(expected_session)", "execution_session"),
        ("execution_session != expected_next", "False"),
        ("timing.xnys_regular_open(expected_next)", "wake.preopen_deadline_utc"),
        ("wake.preopen_deadline_utc != expected_deadline", "False"),
        ("wake.__post_init__()", "pass"),
        ("wake.completed_session not in expected_completed", "False"),
        ("set(covered) != set(expected)", "False"),
        ("covered != expected", "False"),
        ('"d10_accepted": False', '"d10_accepted": True'),
        ('"broker_paper_authorized": False', '"broker_paper_authorized": True'),
        ('"operator_decision_required": True', '"operator_decision_required": False'),
        ('"READY_FOR_EXTERNAL_REVIEW_ARTIFACT"', '"ACCEPTED"'),
        (
            '"provider_attempts": sum(wake.provider_attempts for wake in matching)',
            '"provider_attempts": 1',
        ),
    ),
)
def test_xnys_session_authority_rejects_semantic_weakening(tmp_path, old, new):
    root = _xnys_session_authority_copy(tmp_path, old=old, new=new)
    assert runner._d10_xnys_session_coverage_policy_authority_check(root)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            "authority_check=_d10_xnys_session_coverage_policy_authority_check,",
            (
                "authority_check=_d10_xnys_session_coverage_policy_autho"
                "rity_check, preflight=_r8_preflight,"
            ),
        ),
        (
            "authority_check=_d10_xnys_session_coverage_policy_authority_check,",
            (
                "authority_check=_d10_xnys_session_coverage_policy_autho"
                "rity_check, execute=_r7_execute,"
            ),
        ),
        ('remote_branch="feature/post-d10-observability",', 'remote_branch="develop",'),
        ("tests=xnys_session_tests,", "tests=scheduler_history_tests,"),
        ("ruff_paths=xnys_session_ruff,", "ruff_paths=scheduler_history_ruff,"),
        (
            "ruff_paths=xnys_session_ruff,",
            'ruff_paths=xnys_session_ruff, remote_head_env="AUTHORITY",',
        ),
    ),
)
def test_xnys_session_authority_rejects_registration_drift(tmp_path, old, new):
    root = _xnys_session_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index('        "d10-xnys-session-coverage-policy": CheckpointSpec(')
    end = source.index('        "arch128-r8": CheckpointSpec(', start)
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new, 1) + source[end:],
        encoding="utf-8",
    )
    assert runner._d10_xnys_session_coverage_policy_authority_check(root)


@pytest.mark.parametrize("name", ("xnys_session_tests", "xnys_session_ruff"))
def test_xnys_session_authority_freezes_source_test_hierarchy(tmp_path, name):
    root = _xnys_session_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace(name + " = (", name + " = (*(),", 1)
    path.write_text(source, encoding="utf-8")
    assert runner._d10_xnys_session_coverage_policy_authority_check(root)


@pytest.mark.parametrize(
    "filename",
    (
        "d10_end_of_soak_review.py",
        "d10_external_review_package.py",
        "d10_scheduler_slot_review_policy.py",
        "d10_scheduler_history_windows.py",
    ),
)
def test_xnys_session_authority_composes_upstream_semantics(tmp_path, filename):
    root = _xnys_session_authority_copy(tmp_path)
    path = root / "scripts" / filename
    path.write_text(
        path.read_text(encoding="utf-8") + "\nforeign_effect()\n", encoding="utf-8"
    )
    assert runner._d10_xnys_session_coverage_policy_authority_check(root)


def test_xnys_session_authority_accepts_frozen_source_and_whitespace(tmp_path):
    source_root = Path(runner.__file__).resolve().parent.parent
    assert runner._d10_xnys_session_coverage_policy_authority_check(source_root) == ()
    root = _xnys_session_authority_copy(tmp_path, addition="# comment only")
    assert runner._d10_xnys_session_coverage_policy_authority_check(root) == ()


def test_xnys_session_authority_missing_invalid_source_blocks(tmp_path):
    assert runner._d10_xnys_session_coverage_policy_authority_check(tmp_path)
    root = _xnys_session_authority_copy(tmp_path)
    (root / "scripts/d10_xnys_session_coverage_policy.py").write_text(
        "def invalid(", encoding="utf-8"
    )
    assert runner._d10_xnys_session_coverage_policy_authority_check(root)


def test_xnys_session_preserves_exact_upstream_registration_asts():
    tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    expected = {
        "d10-soak-status": (
            "c931432dc1c416fba25c6d12c3c63dc81961b7dbf37dada871e57f6e8cd89b73"
        ),
        "d10-soak-review": (
            "4d4bf1a361f1e4184da9d727e2fd3d8903233b08fc721aa8f646e3f4b6143b41"
        ),
        "d10-external-review-package": (
            "749a6974c8f39eaaf7f4fd633773b29b312d69a4a7ba13e12298380db4083004"
        ),
        "d10-scheduler-slot-policy": (
            "39d11ed9fe65215ea80cd10e9375f81f775ed92bb61e50573bc2ef1c2cc85768"
        ),
        "d10-scheduler-history-collector": (
            "97f0c544281b10c41b0445d895fe28c882e5230a1e0782667fcade5dc7af247a"
        ),
        "arch128-r8": (
            "6da83416d48314b92e0ac4a158b3fefbbd4193a52d6c35913799ec53202c5b07"
        ),
    }
    actual = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "CheckpointSpec":
            for keyword in node.keywords:
                if (
                    keyword.arg == "name"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value in expected
                ):
                    actual[keyword.value.value] = hashlib.sha256(
                        ast.dump(node).encode("utf-8")
                    ).hexdigest()
    assert actual == expected


def test_xnys_projector_registration_is_verify_only():
    specs = runner._checkpoint_specs()
    spec = specs["d10-xnys-session-evidence-projector"]
    upstream = specs["d10-xnys-session-coverage-policy"]
    assert spec.preflight is None
    assert spec.execute is None
    assert spec.remote_head_env is None
    assert spec.remote_branch == "feature/post-d10-observability"
    assert (
        spec.authority_check
        is runner._d10_xnys_session_evidence_projector_authority_check
    )
    assert spec.tests == (
        *upstream.tests,
        "tests/runtime/test_d10_xnys_session_evidence_projector.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
    )
    assert spec.ruff_paths == (
        *upstream.ruff_paths,
        "scripts/d10_xnys_session_evidence_projector.py",
        "tests/runtime/test_d10_xnys_session_evidence_projector.py",
    )
    parser = runner._parser(specs)
    assert parser.parse_args(("verify", spec.name)).checkpoint == spec.name
    for command in ("preflight", "execute"):
        with pytest.raises(SystemExit):
            parser.parse_args((command, spec.name))


def _xnys_projector_authority_copy(tmp_path, *, old="", new="", addition=""):
    root = _xnys_session_authority_copy(tmp_path)
    path = Path(runner.__file__).parent / "d10_xnys_session_evidence_projector.py"
    source = path.read_text(encoding="utf-8")
    if old:
        assert old in source
        source = source.replace(old, new, 1)
    (root / "scripts/d10_xnys_session_evidence_projector.py").write_text(
        source + "\n" + addition + "\n", encoding="utf-8"
    )
    return root


@pytest.mark.parametrize(
    "addition",
    (
        "import os",
        "import subprocess",
        "import ctypes",
        "from pathlib import Path",
        "open('evidence')",
        "Path('evidence').read_bytes()",
        "os.environ['TOKEN']",
        "subprocess.run([])",
        "ctypes.WinDLL('kernel32')",
        "datetime.now(UTC)",
        "from scripts import d10_soak_status_readonly as observer",
        "observer.observe()",
        "collector.observe()",
        "provider.capture()",
        "paper_v2.execute()",
        "broker.order()",
        "live.execute()",
        "def observe(): pass",
        "def preflight(): pass",
        "def execute(): pass",
        "json.loads(log_bytes)",
        "def independent_grammar(data): return data.splitlines()",
        "sorted(reconstructed_wakes)",
        "set(reconstructed_wakes)",
        "dict.fromkeys(reconstructed_wakes)",
        "__import__('os')",
        "eval('effect()')",
    ),
)
def test_xnys_projector_authority_rejects_io_observer_grammar_sort_dedup(
    tmp_path, addition
):
    root = _xnys_projector_authority_copy(tmp_path, addition=addition)
    assert runner._d10_xnys_session_evidence_projector_authority_check(root)


@pytest.mark.parametrize(
    "old,new",
    (
        (
            'SCHEMA: Final = "d10-xnys-session-evidence-projector/v1"',
            'SCHEMA: Final = "other"',
        ),
        ("session_policy.DEPLOYMENT_ID", "'foreign'"),
        ("session_policy.ATTESTATION_SHA256", "'foreign'"),
        ("session_policy.SOAK_ID", "'foreign'"),
        ("session_policy.ACTIVATION_UTC", "END_UTC"),
        ("session_policy.END_UTC", "ACTIVATION_UTC"),
        ("type(log_bytes) is not bytes", "False"),
        ("type(lease) is not D10ActivationLease", "False"),
        ("lease.__post_init__()", "pass"),
        ("lease.deployment_id != DEPLOYMENT_ID", "False"),
        ("lease.attestation_sha256 != ATTESTATION_SHA256", "False"),
        ("lease.soak_id != SOAK_ID", "False"),
        ("lease.accepted_activation_utc != ACTIVATION_UTC", "False"),
        ("lease.end_utc != END_UTC", "False"),
        (
            "wake_log.summarize_d10_wake_evidence_log(log_bytes, lease)",
            "caller_summary()",
        ),
        ("summary.terminal is not False", "False"),
        ("summary.terminal_kind is not None", "False"),
        ("summary.last_stop_reason is not None", "False"),
        ("summary.last_guard_reason is not None", "False"),
        ("summary.wake_count < 7", "False"),
        ("summary.record_count != summary.wake_count * 3", "False"),
        ('log_bytes[:-1].split(b"\\n")', "log_bytes.splitlines()"),
        ("len(lines) != summary.record_count", "False"),
        ("range(0, len(lines), 3)", "range(0, len(lines), 2)"),
        ("lines[offset + 1]", "lines[offset]"),
        (
            "wake_log.parse_persisted_d10_wake_record(ordinary_bytes, lease)",
            "caller_record()",
        ),
        ("json.loads(record.canonical_bytes)", "json.loads(ordinary_bytes)"),
        ("observed_at_utc=record.observed_at_utc", "observed_at_utc=ACTIVATION_UTC"),
        (
            "certified_source_head=lease.certified_source_head",
            "certified_source_head='new'",
        ),
        (
            'executable_file_count=value["deployment"]["executable_file_count"]',
            "executable_file_count=307",
        ),
        (
            'provider_attempt_id=value["capture"]["attempt_id"]',
            "provider_attempt_id=None",
        ),
        ('final_plan_id=value["settlement"]["plan_id"]', "final_plan_id=None"),
        (
            'historical_reconciled_count=value["history"]["reconciled_count"]',
            "historical_reconciled_count=0",
        ),
        (
            'receipt_recovery_attempts=value["budgets"]["receipt_recovery_attempts"]',
            "receipt_recovery_attempts=0",
        ),
        (
            'closed_effect_gate_count=value["final_gates"]["closed_count"]',
            "closed_effect_gate_count=8",
        ),
        ("wake.observed_at_utc < previous_time", "False"),
        (
            "tuple(reconstructed_wakes), reviewed_at_utc=reviewed_at_utc",
            "tuple(sorted(reconstructed_wakes)), reviewed_at_utc=reviewed_at_utc",
        ),
        ("session_policy.analyze(", "independent_policy("),
        ("hashlib.sha256(log_bytes).hexdigest()", "'synthetic'"),
        ('"input_log_byte_length": len(log_bytes)', '"input_log_byte_length": 0'),
        ('"policy": policy', '"policy": log_bytes'),
        ('"d10_accepted": False', '"d10_accepted": True'),
        ('"broker_paper_authorized": False', '"broker_paper_authorized": True'),
        ('"operator_decision_required": True', '"operator_decision_required": False'),
        ('field: "NOT_RUN"', 'field: "RUN"'),
    ),
)
def test_xnys_projector_authority_rejects_semantic_drift(tmp_path, old, new):
    root = _xnys_projector_authority_copy(tmp_path, old=old, new=new)
    assert runner._d10_xnys_session_evidence_projector_authority_check(root)


@pytest.mark.parametrize(
    "old,new",
    (
        (
            "authority_check=_d10_xnys_session_evidence_projector_authority_check,",
            (
                "authority_check=_d10_xnys_session_evidence_projector_authority_check, "
                "preflight=_r8_preflight,"
            ),
        ),
        (
            "authority_check=_d10_xnys_session_evidence_projector_authority_check,",
            (
                "authority_check=_d10_xnys_session_evidence_projector_authority_check, "
                "execute=_r7_execute,"
            ),
        ),
        ('remote_branch="feature/post-d10-observability",', 'remote_branch="develop",'),
        ("tests=xnys_projector_tests,", "tests=xnys_session_tests,"),
        ("ruff_paths=xnys_projector_ruff,", "ruff_paths=xnys_session_ruff,"),
        (
            "ruff_paths=xnys_projector_ruff,",
            'ruff_paths=xnys_projector_ruff, remote_head_env="AUTHORITY",',
        ),
    ),
)
def test_xnys_projector_authority_rejects_registration_drift(tmp_path, old, new):
    root = _xnys_projector_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "d10-xnys-session-evidence-projector": CheckpointSpec('
    )
    end = source.index('        "arch128-r8": CheckpointSpec(', start)
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new, 1) + source[end:],
        encoding="utf-8",
    )
    assert runner._d10_xnys_session_evidence_projector_authority_check(root)


@pytest.mark.parametrize("name", ("xnys_projector_tests", "xnys_projector_ruff"))
def test_xnys_projector_authority_freezes_hierarchy(tmp_path, name):
    root = _xnys_projector_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    path.write_text(
        source.replace(name + " = (", name + " = (*(),", 1), encoding="utf-8"
    )
    assert runner._d10_xnys_session_evidence_projector_authority_check(root)


@pytest.mark.parametrize(
    "filename",
    (
        "d10_end_of_soak_review.py",
        "d10_external_review_package.py",
        "d10_scheduler_slot_review_policy.py",
        "d10_scheduler_history_windows.py",
        "d10_xnys_session_coverage_policy.py",
    ),
)
def test_xnys_projector_authority_composes_upstream(tmp_path, filename):
    root = _xnys_projector_authority_copy(tmp_path)
    path = root / "scripts" / filename
    path.write_text(
        path.read_text(encoding="utf-8") + "\nforeign_effect()\n", encoding="utf-8"
    )
    assert runner._d10_xnys_session_evidence_projector_authority_check(root)


def test_xnys_projector_authority_accepts_source_and_comments(tmp_path):
    source_root = Path(runner.__file__).resolve().parent.parent
    assert (
        runner._d10_xnys_session_evidence_projector_authority_check(source_root) == ()
    )
    root = _xnys_projector_authority_copy(tmp_path, addition="# comment only")
    assert runner._d10_xnys_session_evidence_projector_authority_check(root) == ()


def test_xnys_projector_authority_missing_or_invalid_blocks(tmp_path):
    assert runner._d10_xnys_session_evidence_projector_authority_check(tmp_path)
    root = _xnys_projector_authority_copy(tmp_path)
    path = root / "scripts/d10_xnys_session_evidence_projector.py"
    path.write_text("def invalid(", encoding="utf-8")
    assert runner._d10_xnys_session_evidence_projector_authority_check(root)
    path.unlink()
    assert runner._d10_xnys_session_evidence_projector_authority_check(root)


def test_xnys_projector_preserves_s2c2a_registration():
    tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    registrations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "CheckpointSpec"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "d10-xnys-session-coverage-policy"
            for keyword in node.keywords
        )
    ]
    assert len(registrations) == 1
    assert (
        hashlib.sha256(ast.dump(registrations[0]).encode()).hexdigest()
        == "d0d4700af714aeb5d780f2af4ccdcb646349617131bb8eb3ec0c2823a3ce4043"
    )


def test_xnys_projector_ci_preserves_historical_jobs_and_verify_only():
    root = Path(runner.__file__).resolve().parent.parent
    source = (root / ".github/workflows/side-checkpoint-certification.yml").read_text(
        encoding="utf-8"
    )
    historical, side = source.split("  side-head-source-gates:", 1)
    assert (
        hashlib.sha256(historical.encode()).hexdigest()
        == "bac12b74c9a6a97a916e57e7633fd4d9768d2f70561454e90f2014f75679bc5d"
    )
    commands = re.findall(r"^          [.]\\ops[.]ps1 (.+)$", side, re.MULTILINE)
    assert commands == [
        "verify d10-soak-status",
        "verify d10-soak-review",
        "verify d10-external-review-package",
        "verify d10-scheduler-slot-policy",
        "verify d10-scheduler-history-collector",
        "verify d10-xnys-session-coverage-policy",
        "verify d10-xnys-session-evidence-projector",
    ]
    assert "name: side-head-source-gate-evidence" in side
