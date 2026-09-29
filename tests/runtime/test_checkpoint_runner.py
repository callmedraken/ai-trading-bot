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
        assert spec.remote_branch == "feature/d10c-durable-wake-evidence"


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
