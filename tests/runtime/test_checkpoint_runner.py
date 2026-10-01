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
        "d10-soak-status",
        "d10-soak-review",
    }
    for spec in specs.values():
        assert "tests/runtime/test_checkpoint_runner.py" in spec.tests
        assert "scripts/checkpoint_runner.py" in spec.ruff_paths
        assert "tests/runtime/test_checkpoint_runner.py" in spec.ruff_paths
        expected_branch = (
            "feature/post-d10-observability"
            if spec.name in ("d10-soak-status", "d10-soak-review")
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
