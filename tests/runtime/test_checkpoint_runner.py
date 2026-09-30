from __future__ import annotations

import json
import subprocess
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
        "arch128-r5-substrate",
        "arch128-r5-trading",
    }
    for spec in specs.values():
        assert "tests/runtime/test_checkpoint_runner.py" in spec.tests
        assert "scripts/checkpoint_runner.py" in spec.ruff_paths
        assert "tests/runtime/test_checkpoint_runner.py" in spec.ruff_paths
        assert spec.remote_branch == "feature/d10c-durable-wake-evidence"

    assert specs["arch128-parent-acl-repair"].execute is not None
    assert specs["arch128-r4"].execute is not None
    assert specs["arch128-r5-substrate"].execute is None
    assert specs["arch128-r5-trading"].execute is None
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
