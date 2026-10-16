from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner

from .helpers import (
    _EXPECTED_ACTIVE_CI_CHECKPOINTS,
    _EXPECTED_RETAINED_CHECKPOINTS,
    _clean_source,
    _outcome,
    _parent_preflight_result,
    _r4_preflight_result,
    _r7_result,
    _r8_authority_copy,
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
        *runner.RETAINED_TESTS,
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
    root = Path(runner.__file__).resolve().parents[1]
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
    root = Path(runner.__file__).resolve().parents[1]
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
    root = Path(runner.__file__).resolve().parents[1]
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
        *runner.RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_durable_wake_evidence_observe.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_personal_desktop_d10_guard_evidence.py",
    )
    assert spec.ruff_paths == (
        *runner.RETAINED_RUFF_PATHS,
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


def test_r2a_active_retained_partition_and_retained_authorities():
    assert runner.ACTIVE_CI_CHECKPOINTS == _EXPECTED_ACTIVE_CI_CHECKPOINTS
    assert runner.RETAINED_CHECKPOINTS == _EXPECTED_RETAINED_CHECKPOINTS
    assert not set(runner.ACTIVE_CI_CHECKPOINTS) & set(runner.RETAINED_CHECKPOINTS)
    assert not hasattr(runner, "CI_CHECKPOINTS")
    specs = runner._checkpoint_specs()
    repo = Path(runner.__file__).resolve().parent.parent
    for name in (*_EXPECTED_ACTIVE_CI_CHECKPOINTS, *_EXPECTED_RETAINED_CHECKPOINTS):
        assert name in specs
    for name in _EXPECTED_RETAINED_CHECKPOINTS:
        spec = specs[name]
        assert spec.tests and spec.ruff_paths
        assert spec.authority_check(repo) == ()


@pytest.mark.parametrize(
    "names",
    [
        _EXPECTED_RETAINED_CHECKPOINTS,
        tuple(reversed(_EXPECTED_RETAINED_CHECKPOINTS)),
        (
            _EXPECTED_ACTIVE_CI_CHECKPOINTS[-1],
            _EXPECTED_RETAINED_CHECKPOINTS[0],
            _EXPECTED_ACTIVE_CI_CHECKPOINTS[0],
            _EXPECTED_RETAINED_CHECKPOINTS[-1],
        ),
    ],
)
def test_r2a_explicit_retained_and_mixed_batches_preserve_all_requirements(
    names, monkeypatch, tmp_path
):
    registry = runner._checkpoint_specs()
    specs = [registry[name] for name in names]
    expected_tests, expected_ruff = [], []
    for spec in specs:
        for path in spec.tests:
            if path not in expected_tests:
                expected_tests.append(path)
        for path in spec.ruff_paths:
            if path not in expected_ruff:
                expected_ruff.append(path)
    assert runner.batch_requirements(specs) == (
        tuple(expected_tests),
        tuple(expected_ruff),
    )
    monkeypatch.setattr(runner, "_git_state", lambda repo: _clean_source())
    monkeypatch.setattr(
        runner, "_execute_step", lambda step, **kw: _outcome(step.name, 0)
    )
    # Exercise real registered requirements/authorities, mocking only child commands
    # and source admission; host capabilities must never be called by verify-batch.
    repo = Path(runner.__file__).resolve().parent.parent
    passed, path = runner.verify_batch(specs, repo_root=repo, evidence_root=tmp_path)
    assert passed
    report = json.loads(path.read_text())
    assert report["checkpoints"] == list(names)
    assert report["tests"] == expected_tests
    assert report["ruff_paths"] == expected_ruff
    assert report["authority_failures"] == dict.fromkeys(names, [])
    for field in (
        "production_effects",
        "scheduler_mutation",
        "provider_effects",
        "broker_live_effects",
    ):
        assert report[field] == "NOT_RUN"


@pytest.mark.parametrize("name", _EXPECTED_RETAINED_CHECKPOINTS)
def test_r2a_retained_individual_cli_dispatch(name, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(
        runner,
        "verify_checkpoint",
        lambda spec, **kw: (seen.append(spec) or True, tmp_path),
    )
    assert runner.main(["verify", name]) == 0
    assert seen == [runner._checkpoint_specs()[name]]


def test_retained_individual_verification_exercises_registered_source_contract(
    tmp_path, monkeypatch
):
    repo = Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()["arch128-r4"]
    calls = []
    monkeypatch.setattr(runner, "_git_state", lambda root: _clean_source())

    def execute(step, **kwargs):
        calls.append(step)
        return _outcome(step.name, 0)

    monkeypatch.setattr(runner, "_execute_step", execute)
    passed, path = runner.verify_checkpoint(
        spec, repo_root=repo, evidence_root=tmp_path
    )
    assert passed
    report = json.loads(path.read_text())
    assert all(path in calls[0].argv for path in spec.tests)
    assert all(path in calls[1].argv for path in spec.ruff_paths)
    assert report["authority_failures"] == []
    assert (
        "tests/runtime/checkpoint_runner/test_retained_arch128_130.py" in calls[0].argv
    )
    assert report["production_effects"] == "NOT_RUN"
