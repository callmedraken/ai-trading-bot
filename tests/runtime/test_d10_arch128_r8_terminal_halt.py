from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from scripts.d10_protected_deployment import CheckedFile, NativeObject, expected_policy

from scripts import checkpoint_runner as runner
from scripts import d10_arch128_r8_halt_diagnostic as diagnostic
from scripts import d10_arch128_r8_halt_windows as windows
from scripts import d10_arch128_r8_terminal_halt as halt

ROOT = Path(__file__).resolve().parents[2]


def snapshot(enabled: bool = True) -> halt.Snapshot:
    return halt.Snapshot(
        copy.deepcopy(halt.EXPECTED_EVIDENCE),
        {"sha256": halt.LEASE_SHA256, "native_identity_sha256": "a" * 64},
        {
            **halt.expected_scheduler(enabled),
            "xml_byte_length": 4000,
            "xml_sha256": ("b" if enabled else "c") * 64,
        },
    )


def host() -> Mock:
    before, after = snapshot(), snapshot(False)
    return Mock(
        observe=Mock(side_effect=[before, after]),
        disable=Mock(
            return_value={
                "schema": "arch128-r8-terminal-halt-com/v1",
                "call_attempted": True,
                "disposition": "CALL_RETURNED",
                "before": before.scheduler,
                "after": after.scheduler,
                "xml_unchanged": True,
            }
        ),
    )


def diagnostic_ready() -> dict[str, object]:
    return {
        "schema": diagnostic.SCHEMA,
        "status": diagnostic.READY,
        "reason": None,
        "call_attempted": False,
        "scheduler_mutation": "NOT_RUN",
        "scheduler": snapshot().scheduler,
    }


def execute(boundary: Mock) -> dict[str, object]:
    return halt.execute(
        (halt.EXECUTE_FLAG,),
        {halt.AUTHORIZATION_ENV: halt.AUTHORIZATION_VALUE},
        lambda: boundary,
    )


def assert_closed(result: dict[str, object]) -> None:
    assert all(result[field] == "NOT_RUN" for field in halt.CLOSED_EFFECTS)
    assert result["failed_child_effects"] == "UNKNOWN_REQUIRES_READ_ONLY_RECONCILIATION"
    assert result["automatic_retry"] is False
    assert result["automatic_rollback"] is False
    assert result["automatic_cleanup"] is False


def test_exact_incident_read_only_preflight_passes() -> None:
    boundary = host()
    result = halt.preflight(boundary)
    assert result["status"] == "PASS"
    assert result["scheduler_mutation"] == "NOT_RUN"
    assert result["call_attempted"] is False
    boundary.observe.assert_called_once_with()
    boundary.disable.assert_not_called()
    assert_closed(result)


@pytest.mark.parametrize("field", tuple(halt.EXPECTED_EVIDENCE))
def test_every_incident_evidence_field_is_exact(field: str) -> None:
    before = snapshot()
    before.evidence[field] = "DRIFT"
    boundary = Mock(observe=Mock(return_value=before))
    assert halt.preflight(boundary)["status"] == "BLOCKED"
    assert execute(boundary)["disposition"] == "NOT_CALLED"
    boundary.disable.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    (
        ("record_count", True),
        ("wake_count", False),
        ("evidence_byte_length", 453.0),
        ("terminal", 1),
    ),
)
def test_incident_types_cannot_alias_values(field: str, value: object) -> None:
    before = snapshot()
    before.evidence[field] = value
    assert (
        halt.preflight(Mock(observe=Mock(return_value=before)))["status"] == "BLOCKED"
    )


@pytest.mark.parametrize("field", tuple(halt.expected_scheduler(True)))
def test_every_scheduler_semantic_is_required_before_call(field: str) -> None:
    before = snapshot()
    before.scheduler[field] = "DRIFT"
    boundary = Mock(observe=Mock(return_value=before))
    assert execute(boundary)["disposition"] == "NOT_CALLED"
    boundary.disable.assert_not_called()


def test_running_task_blocks() -> None:
    before = snapshot()
    before.scheduler["task_state"] = 4
    boundary = Mock(observe=Mock(return_value=before))
    assert execute(boundary)["disposition"] == "NOT_CALLED"
    boundary.disable.assert_not_called()


def test_already_disabled_is_distinct_and_never_mutates() -> None:
    boundary = Mock(observe=Mock(return_value=snapshot(False)))
    for result in (halt.preflight(boundary), execute(boundary)):
        assert result["status"] == "BLOCKED"
        assert result["reason"] == "already_disabled_no_mutation_authority"
        assert result["call_attempted"] is False
    boundary.disable.assert_not_called()


@pytest.mark.parametrize("argv", ((), (halt.EXECUTE_FLAG, "extra"), ("--old-halt",)))
def test_exact_execute_flag_required(argv) -> None:
    factory = Mock()
    result = halt.execute(
        argv, {halt.AUTHORIZATION_ENV: halt.AUTHORIZATION_VALUE}, factory
    )
    assert result["disposition"] == "NOT_CALLED"
    factory.assert_not_called()


@pytest.mark.parametrize("value", (None, "", "wrong", halt.AUTHORIZATION_VALUE + " "))
def test_exact_human_authorization_required_before_factory(value) -> None:
    factory = Mock()
    environment = {} if value is None else {halt.AUTHORIZATION_ENV: value}
    result = halt.execute((halt.EXECUTE_FLAG,), environment, factory)
    assert result["disposition"] == "NOT_CALLED"
    factory.assert_not_called()
    assert_closed(result)


def test_exact_authorization_and_admission_disable_once() -> None:
    boundary = host()
    result = execute(boundary)
    assert result["status"] == "PASS"
    assert result["disposition"] == "CALL_RETURNED"
    assert result["scheduler_mutation"] == "DISABLED_VERIFIED"
    assert result["evidence_before_after"] == "IDENTICAL"
    assert result["lease_before_after"] == "IDENTICAL"
    assert boundary.observe.call_count == 2
    boundary.disable.assert_called_once_with()
    assert_closed(result)


@pytest.mark.parametrize(
    "section,field,value",
    (
        ("scheduler", "enabled", True),
        ("scheduler", "task_state", 4),
        ("scheduler", "restart_count", 1),
        ("scheduler", "trigger_end_boundary", "old"),
        ("evidence", "evidence_sha256", "d" * 64),
        ("evidence", "evidence_byte_length", 454),
        ("lease", "sha256", "d" * 64),
        ("lease", "native_identity_sha256", "d" * 64),
    ),
)
def test_post_halt_drift_is_nonpass_and_never_retries(section, field, value) -> None:
    boundary = host()
    after = snapshot(False)
    getattr(after, section)[field] = value
    boundary.observe.side_effect = [snapshot(), after]
    result = execute(boundary)
    assert result["status"] == "STOPPED"
    assert result["disposition"] == "INDETERMINATE"
    boundary.disable.assert_called_once_with()
    assert_closed(result)


@pytest.mark.parametrize("phase", ("factory", "observation"))
def test_exception_before_protected_dispatch_is_not_called(phase) -> None:
    factory = (
        Mock(side_effect=RuntimeError("sensitive"))
        if phase == "factory"
        else Mock(
            return_value=Mock(observe=Mock(side_effect=RuntimeError("sensitive")))
        )
    )
    result = halt.execute(
        (halt.EXECUTE_FLAG,),
        {halt.AUTHORIZATION_ENV: halt.AUTHORIZATION_VALUE},
        factory,
    )
    assert result["disposition"] == "NOT_CALLED"
    assert result["call_attempted"] is False
    assert "sensitive" not in str(result)


def test_native_proven_pre_call_exception_is_not_called() -> None:
    boundary = host()
    boundary.disable.return_value = {
        "schema": "arch128-r8-terminal-halt-com/v1",
        "call_attempted": False,
        "disposition": "NOT_CALLED",
        "before": None,
        "after": None,
        "xml_unchanged": False,
    }
    result = execute(boundary)
    assert result["disposition"] == "NOT_CALLED"
    assert result["call_attempted"] is False
    boundary.disable.assert_called_once_with()
    assert boundary.observe.call_count == 1


@pytest.mark.parametrize("phase", ("dispatch", "post_read"))
def test_exception_after_possible_attempt_is_indeterminate(phase) -> None:
    boundary = host()
    if phase == "dispatch":
        boundary.disable.side_effect = RuntimeError("sensitive")
    else:
        boundary.observe.side_effect = [snapshot(), RuntimeError("sensitive")]
    result = execute(boundary)
    assert result["disposition"] == "INDETERMINATE"
    assert result["call_attempted"] is True
    assert "sensitive" not in str(result)
    boundary.disable.assert_called_once_with()
    assert_closed(result)


@pytest.mark.parametrize(
    "change",
    (
        {"schema": "old/v1"},
        {"call_attempted": 1},
        {"disposition": "INDETERMINATE"},
        {"xml_unchanged": False},
        {"after": snapshot().scheduler},
        {"extra": True},
    ),
)
def test_malformed_native_result_never_passes(change) -> None:
    boundary = host()
    boundary.disable.return_value.update(change)
    assert execute(boundary)["status"] != "PASS"
    boundary.disable.assert_called_once_with()


def test_current_interval_and_lease_are_derived() -> None:
    expected = halt.expected_scheduler(True)
    assert expected["trigger_start_boundary"] == "2026-10-01T01:30:00-07:00"
    assert expected["trigger_end_boundary"] == "2026-10-07T15:07:24-07:00"
    assert expected["start_when_available"] is True
    assert expected["restart_count"] == 0
    assert halt.EXECUTE_FLAG == "--execute-reviewed-r8-terminal-halt"
    assert halt.AUTHORIZATION_ENV == "AI_TRADING_BOT_ARCH128_R8_HALT_AUTHORIZATION"
    assert halt.AUTHORIZATION_VALUE == "ARCH128_R8_TERMINAL_HALT_AUTHORIZED"


def test_registration_does_not_execute_and_preflight_has_only_reader(
    monkeypatch,
) -> None:
    protected = Mock(side_effect=AssertionError("writer constructed"))
    monkeypatch.setattr(windows, "ProtectedWindowsHost", protected)
    monkeypatch.setattr(windows, "ReadOnlyWindowsHost", lambda: host())
    monkeypatch.setattr(diagnostic, "observe", diagnostic_ready)
    spec = runner._checkpoint_specs()["arch128-r8-terminal-halt"]
    assert spec.preflight is runner._r8_halt_preflight
    assert spec.execute is runner._r8_halt_execute
    assert spec.remote_branch == "feature/d10c-r8-terminal-halt"
    assert spec.remote_head_env is None
    assert spec.preflight()["status"] == "PASS"
    protected.assert_not_called()


def test_generic_runner_admits_source_and_writes_attempt_before_dispatch(
    tmp_path, monkeypatch
) -> None:
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "feature/d10c-r8-terminal-halt",
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda repo: state)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda repo, branch: "a" * 40)
    monkeypatch.setattr(windows, "ProtectedWindowsHost", host)
    monkeypatch.setenv(halt.AUTHORIZATION_ENV, halt.AUTHORIZATION_VALUE)
    original = halt.execute

    def checked(*args):
        attempt = list(tmp_path.rglob("attempt.json"))
        assert len(attempt) == 1
        assert json.loads(attempt[0].read_text())["source"]["remote_head"] == "a" * 40
        return original(*args)

    monkeypatch.setattr(halt, "execute", checked)
    passed, path = runner.execute_checkpoint(
        runner._checkpoint_specs()["arch128-r8-terminal-halt"],
        repo_root=ROOT,
        evidence_root=tmp_path,
    )
    assert passed
    record = json.loads(path.read_text())
    assert record["effect_disposition"] == "CONFIRMED"
    assert record["automatic_retry"] == "NOT_AUTHORIZED"


def test_generic_source_mismatch_never_dispatches(tmp_path, monkeypatch) -> None:
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "feature/d10c-r8-terminal-halt",
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda repo: state)
    monkeypatch.setattr(runner, "_remote_branch_head", lambda repo, branch: "c" * 40)
    dispatch = Mock()
    monkeypatch.setattr(halt, "execute", dispatch)
    with pytest.raises(RuntimeError, match="not the live remote"):
        runner.execute_checkpoint(
            runner._checkpoint_specs()["arch128-r8-terminal-halt"],
            repo_root=ROOT,
            evidence_root=tmp_path,
        )
    dispatch.assert_not_called()


@pytest.mark.parametrize(
    "field", (*halt.CLOSED_EFFECTS, "lease_before_after", "call_attempted")
)
def test_runner_independently_rejects_forged_pass(monkeypatch, field) -> None:
    primary = execute(host())
    primary[field] = "DRIFT"
    monkeypatch.setattr(halt, "execute", lambda *args: primary)
    result = runner._r8_halt_execute()
    assert result["status"] == "STOPPED"
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"


@pytest.mark.parametrize("field", (*halt.CLOSED_EFFECTS, "scheduler_mutation"))
def test_runner_preflight_rejects_effect_drift(monkeypatch, field) -> None:
    primary = halt.preflight(host())
    primary[field] = "DRIFT"
    monkeypatch.setattr(halt, "preflight", lambda boundary: primary)
    assert runner._r8_halt_preflight()["status"] == "BLOCKED"


def test_runner_preflight_requires_native_pre_call_ready(monkeypatch) -> None:
    monkeypatch.setattr(windows, "ReadOnlyWindowsHost", lambda: host())
    monkeypatch.setattr(diagnostic, "observe", diagnostic_ready)
    result = runner._r8_halt_preflight()
    assert result["status"] == "PASS"
    assert result["diagnostics"]["native_pre_call"] == diagnostic_ready()


@pytest.mark.parametrize("reason", sorted(diagnostic.REASONS))
def test_runner_preflight_blocks_native_pre_call_reason(monkeypatch, reason) -> None:
    monkeypatch.setattr(windows, "ReadOnlyWindowsHost", lambda: host())
    blocked = diagnostic_ready()
    blocked["status"] = diagnostic.BLOCKED
    blocked["reason"] = reason
    monkeypatch.setattr(diagnostic, "observe", lambda: blocked)
    result = runner._r8_halt_preflight()
    assert result["status"] == "BLOCKED"
    assert result["primary"]["status"] == "PASS"
    assert result["diagnostics"]["native_pre_call"]["reason"] == reason
    assert result["diagnostics"]["native_pre_call"]["call_attempted"] is False


def test_native_pre_call_diagnostic_transport_is_fixed_read_only(monkeypatch) -> None:
    payload = json.dumps(diagnostic_ready(), separators=(",", ":")).encode("utf-8")
    run = Mock(return_value=subprocess.CompletedProcess((), 0, payload, b""))
    monkeypatch.setattr(diagnostic.subprocess, "run", run)
    assert diagnostic.observe() == diagnostic_ready()
    command = run.call_args.args[0]
    assert command[-1] == str(diagnostic.HELPER)
    assert halt.EXECUTE_FLAG not in command
    assert str(windows.HALT_HELPER) not in command


def test_native_pre_call_diagnostic_source_is_read_only() -> None:
    source = (ROOT / "scripts/d10_arch128_r8_terminal_halt_diagnose.ps1").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "$task.Enabled = $false",
        ".Run(",
        ".Stop(",
        ".DeleteTask(",
        ".RegisterTask",
        "Start-ScheduledTask",
        "Stop-ScheduledTask",
        "Set-ScheduledTask",
    ):
        assert forbidden not in source
    for reason in diagnostic.REASONS:
        assert f"'{reason}'" in source

    for state in ("COUNT_DRIFT", "VALUE_NOT_TRUE"):
        assert f"'xml_enabled_node_state'] = '{state}'" in source
    assert "'xml_enabled_node_state'] = 'MISSING'" not in source


def test_scheduler_helper_is_reused_and_two_reads_must_match(monkeypatch) -> None:
    monkeypatch.setattr(windows, "transport", Mock())
    tree = ast.parse((ROOT / "scripts/d10_arch128_r8_halt_windows.py").read_text())
    read_class = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "ReadOnlyWindowsHost"
    )
    calls = [
        ast.unparse(n.func) for n in ast.walk(read_class) if isinstance(n, ast.Call)
    ]
    assert calls.count("observer.observe") == 1
    assert "transport" in calls
    assert "disable" not in str(calls)
    assert windows.OBSERVE_HELPER.name == "d10_arch128_r3_scheduler_observe.ps1"


def test_transport_never_accepts_arbitrary_helper(monkeypatch) -> None:
    run = Mock()
    monkeypatch.setattr(windows.subprocess, "run", run)
    with pytest.raises(halt.HaltBlocked):
        windows.transport(Path("arbitrary.ps1"))
    run.assert_not_called()


def test_read_only_transport_has_no_execute_flag(monkeypatch) -> None:
    run = Mock(
        return_value=subprocess.CompletedProcess((), 0, b'{"status":"OBSERVED"}', b"")
    )
    monkeypatch.setattr(windows.subprocess, "run", run)
    windows.transport(windows.OBSERVE_HELPER)
    command = run.call_args.args[0]
    assert halt.EXECUTE_FLAG not in command
    assert str(windows.HALT_HELPER) not in command


@pytest.mark.parametrize(
    "stdout",
    (b'{"a":1,"a":2}', b"[]", b"x" * (32 * 1024 + 1)),
    ids=("duplicate", "array", "oversized"),
)
def test_transport_malformed_or_oversized_result_blocks(monkeypatch, stdout) -> None:
    monkeypatch.setattr(
        windows.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess((), 0, stdout, b""),
    )
    with pytest.raises((halt.HaltBlocked, ValueError)):
        windows.transport(windows.HALT_HELPER)


def test_authority_gate_freezes_source() -> None:
    assert runner._r8_halt_authority_check(ROOT) == ()


@pytest.mark.parametrize(
    "path,old,new",
    (
        (
            "scripts/d10_arch128_r8_terminal_halt.ps1",
            "$task.Enabled = $false",
            "$task.Enabled = $false; $task.Run($null)",
        ),
        (
            "scripts/d10_arch128_r8_terminal_halt.ps1",
            "2026-10-01T01:30:00-07:00",
            "2026-09-29T01:30:00-07:00",
        ),
        (
            "scripts/d10_arch128_r8_terminal_halt_diagnose.ps1",
            "    exit 0",
            "    $task.Enabled = $false\n    exit 0",
        ),
        (
            "scripts/d10_arch128_r8_terminal_halt.py",
            '"record_count": 2',
            '"record_count": 3',
        ),
        (
            "scripts/d10_arch128_r8_halt_windows.py",
            "observer.observe()",
            "observer.main()",
        ),
        (
            "scripts/d10_arch128_r8_terminal_halt.py",
            "        mutation = host.disable()",
            "        mutation = host.disable()\n        publish_decision()",
        ),
        (
            "scripts/checkpoint_runner.py",
            "preflight=_r8_halt_preflight",
            "preflight=_r7_preflight",
        ),
        (
            "scripts/checkpoint_runner.py",
            "execute=_r8_halt_execute",
            "execute=_r7_execute",
        ),
        (
            "scripts/checkpoint_runner.py",
            'if remote_head != state_before["head"]:',
            "if False:",
        ),
        (
            "scripts/checkpoint_runner.py",
            'attempt_path = evidence_dir / "attempt.json"',
            'attempt_path = evidence_dir / "missing-attempt.json"',
        ),
    ),
)
def test_authority_rejects_widening_and_stale_interval(
    tmp_path, path, old, new
) -> None:
    for name in runner.R8_HALT_SOURCE_PINS:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
    target = tmp_path / "scripts/checkpoint_runner.py"
    target.write_text(
        (ROOT / "scripts/checkpoint_runner.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    target = tmp_path / path
    source = target.read_text(encoding="utf-8")
    assert old in source
    target.write_text(source.replace(old, new, 1), encoding="utf-8")
    assert runner._r8_halt_authority_check(tmp_path)


@pytest.mark.parametrize(
    "filename",
    (
        "d10_arch128_r8_terminal_halt.ps1",
        "d10_arch128_r8_terminal_halt_diagnose.ps1",
    ),
)
def test_powershell_source_parses_without_host_execution(filename) -> None:
    if __import__("os").name != "nt":
        pytest.skip("PowerShell AST syntax gate on Windows only")
    helper = ROOT / "scripts" / filename
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile('"
        + str(helper).replace("'", "''")
        + "',[ref]$tokens,[ref]$errors) | Out-Null; "
        "if ($errors.Count) { $errors | ForEach-Object { $_.Message }; exit 1 }"
    )
    completed = subprocess.run(
        ("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command),
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout.decode(errors="replace")


def test_native_source_has_single_fixed_mutation_and_ordering() -> None:
    source = (ROOT / "scripts/d10_arch128_r8_terminal_halt.ps1").read_text()
    assert source.count("    $task.Enabled = $false") == 1
    attempted = source.index("    $callAttempted = $true")
    mutation = source.index("    $task.Enabled = $false")
    returned = source.index("    $disposition = 'CALL_RETURNED'")
    assert attempted < mutation < returned
    for forbidden in (
        ".Run(",
        ".Stop(",
        ".DeleteTask(",
        ".RegisterTask",
        "Start-ScheduledTask",
        "Stop-ScheduledTask",
        "Set-ScheduledTask",
        "Remove-Item",
        "Set-Content",
        "2026-09-29T01:30:00",
        "2026-10-05T17:45:22",
    ):
        assert forbidden not in source
    assert "Normalize-EnabledXml" in source
    assert "$first | ConvertTo-Json" in source and "$fourth | ConvertTo-Json" in source
    assert "Task Scheduler schema permits omission" in source
    assert "$nodes.Count -gt 1" in source
    assert "$nodes.Count -ne 1 -or $nodes[0].InnerText -cne 'false'" in source


@pytest.mark.parametrize(
    "scenario,disposition,calls",
    (
        ("success", "CALL_RETURNED", 1),
        ("pre_enabled_omitted", "CALL_RETURNED", 1),
        ("post_enabled_omitted", "INDETERMINATE", 1),
        ("before_exception", "NOT_CALLED", 0),
        ("pre_running", "NOT_CALLED", 0),
        ("pre_disabled", "NOT_CALLED", 0),
        ("pre_semantics", "NOT_CALLED", 0),
        ("pre_two_read_drift", "NOT_CALLED", 0),
        ("setter_throw_before_change", "INDETERMINATE", 1),
        ("setter_throw_after_change", "INDETERMINATE", 1),
        ("post_enabled", "INDETERMINATE", 1),
        ("post_running", "INDETERMINATE", 1),
        ("post_xml_drift", "INDETERMINATE", 1),
        ("post_two_read_drift", "INDETERMINATE", 1),
    ),
)
def test_native_halt_logic_over_fake_com_only(
    tmp_path, scenario, disposition, calls
) -> None:
    if os.name != "nt":
        pytest.skip("PowerShell native-logic simulation on Windows only")
    source = (ROOT / "scripts/d10_arch128_r8_terminal_halt.ps1").read_text()
    # Replace native acquisition in a test copy; preserve exact mutation logic.
    begin = source.index("    $identity =")
    end = source.index("    function Require-ExactSemantics")
    source = source[:begin] + source[end:]
    native = "$service = New-Object -ComObject 'Schedule.Service'"
    assert source.count(native) == 1
    source = source.replace(native, "$service = $global:MockService")
    assert "New-Object -ComObject" not in source
    assert "Join-Path $PSScriptRoot" not in source
    source = source.replace(
        "    schema = 'arch128-r8-terminal-halt-com/v1'",
        "    mock_calls = $global:MockCalls\n"
        "    schema = 'arch128-r8-terminal-halt-com/v1'",
    )
    projection = halt.expected_scheduler(True)
    del projection["enabled"]
    del projection["task_state"]
    mock = r"""
$global:MockCalls = 0
$global:MockReads = 0
$global:ModelEnabled = $true
$global:Case = '__SCENARIO__'
$global:Projection = '__PROJECTION__' | ConvertFrom-Json
if ($global:Case -eq 'pre_disabled') { $global:ModelEnabled = $false }
$global:MockTask = [pscustomobject]@{ Path = '\AITradingBot-PD4-UnattendedPaper-v1' }
$global:MockTask | Add-Member ScriptProperty Enabled {
    return $global:ModelEnabled
} {
    param($Value)
    $global:MockCalls++
    if ($global:Case -eq 'setter_throw_before_change') { throw 'setter exception' }
    if ($global:Case -ne 'post_enabled') { $global:ModelEnabled = [bool]$Value }
    if ($global:Case -eq 'setter_throw_after_change') { throw 'setter exception' }
}
$global:MockTask | Add-Member ScriptProperty State {
    if ($global:Case -eq 'pre_running' -or
        ($global:MockCalls -gt 0 -and $global:Case -eq 'post_running')) { return 4 }
    if ($global:ModelEnabled) { return 3 }
    return 1
}
$global:MockTask | Add-Member ScriptProperty Xml {
    $enabledText = if ($global:ModelEnabled) { 'true' } else { 'false' }
    $other = if ($global:MockCalls -gt 0 -and $global:Case -eq 'post_xml_drift') {
        9
    } else { 7 }
    $omitEnabled = (
        ($global:Case -eq 'pre_enabled_omitted' -and $global:MockCalls -eq 0) -or
        ($global:Case -eq 'post_enabled_omitted' -and $global:MockCalls -gt 0)
    )
    $enabledXml = if ($omitEnabled) {
        ''
    } else {
        '<Enabled>' + $enabledText + '</Enabled>'
    }
    return '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">' +
           '<Settings>' + $enabledXml + '<Priority>' + $other +
           '</Priority></Settings></Task>'
}
$global:MockFolder = [pscustomobject]@{}
$global:MockFolder | Add-Member ScriptMethod GetTask {
    param($Name)
    if ($Name -cne 'AITradingBot-PD4-UnattendedPaper-v1') { throw 'unreviewed task' }
    return $global:MockTask
}
$global:MockService = [pscustomobject]@{}
$global:MockService | Add-Member ScriptMethod Connect {
    if ($global:Case -eq 'before_exception') { throw 'connect exception' }
}
$global:MockService | Add-Member ScriptMethod GetFolder {
    param($Name)
    if ($Name -cne '\') { throw 'unreviewed folder' }
    return $global:MockFolder
}
function Read-FixedTask {
    param($FixedFolder)
    $global:MockReads++
    $result = [ordered]@{}
    foreach ($item in $global:Projection.PSObject.Properties) {
        $result[$item.Name] = $item.Value
    }
    $result['enabled'] = $global:ModelEnabled
    if ($global:Case -eq 'pre_semantics' -or
        ($global:MockReads -eq 2 -and $global:Case -eq 'pre_two_read_drift') -or
        ($global:MockReads -eq 4 -and $global:Case -eq 'post_two_read_drift')) {
        $result['restart_count'] = 1
    }
    $encoding = [System.Text.UTF8Encoding]::new($false)
    $bytes = $encoding.GetBytes([string]$global:MockTask.Xml)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hex = [BitConverter]::ToString($sha.ComputeHash($bytes))
        $digest = $hex.Replace('-', '').ToLowerInvariant()
    }
    finally { $sha.Dispose() }
    $result['xml_byte_length'] = [int]$bytes.Length
    $result['xml_sha256'] = $digest
    return $result
}
"""
    mock = mock.replace("__SCENARIO__", scenario).replace(
        "__PROJECTION__", json.dumps(projection)
    )
    simulation = tmp_path / "fake-com-only.ps1"
    simulation.write_text(mock + source, encoding="utf-8")
    environment = dict(os.environ)
    environment[halt.AUTHORIZATION_ENV] = halt.AUTHORIZATION_VALUE
    completed = subprocess.run(
        (
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(simulation),
            halt.EXECUTE_FLAG,
        ),
        capture_output=True,
        check=False,
        timeout=30,
        env=environment,
    )
    assert not completed.stderr
    result = json.loads(completed.stdout)
    assert result["disposition"] == disposition
    assert result["mock_calls"] == calls
    assert result["call_attempted"] is (calls == 1)
    assert result["xml_unchanged"] is (scenario in ("success", "pre_enabled_omitted"))


@pytest.mark.parametrize(
    "drift", (None, "lease_bytes", "lease_native", "lease_acl", "scheduler")
)
def test_fixed_native_reader_and_accepted_observers_are_composed(
    monkeypatch, drift
) -> None:
    data = windows.r6.derive_reactivation_plan(halt.ACTIVATION).lease.canonical_bytes()
    owner, protected, aces = expected_policy(False)
    path = windows.D10_ACTIVATION_LEASE_PATH
    identity = NativeObject(
        path,
        path,
        False,
        owner,
        protected,
        aces,
        False,
        3,
        "F:" + chr(92),
        "NTFS",
        1,
        22,
        1,
        len(data),
    )
    first = CheckedFile(identity, data, True)
    second = first
    if drift == "lease_bytes":
        second = replace(first, data=data.replace(b"22:07:24", b"22:07:25"))
    if drift == "lease_native":
        second = replace(first, identity=replace(identity, file_index=23))
    if drift == "lease_acl":
        first = replace(first, identity=replace(identity, dacl_protected=False))
    reader = Mock(spec_set=("read_file",), read_file=Mock(side_effect=[first, second]))
    reader_factory = Mock(return_value=reader)
    monkeypatch.setattr(windows, "WindowsArch128ReadOnlyReader", reader_factory)
    evidence = Mock(return_value=copy.deepcopy(halt.EXPECTED_EVIDENCE))
    monkeypatch.setattr(windows.observer, "observe", evidence)
    scheduler = snapshot().scheduler
    other = dict(scheduler)
    if drift == "scheduler":
        other["restart_count"] = 1
    transport = Mock(
        return_value={
            "schema": "arch128-r3-scheduler-observation/v1",
            "status": "OBSERVED",
            "first": scheduler,
            "second": other,
        }
    )
    monkeypatch.setattr(windows, "transport", transport)
    result = halt.preflight(windows.ReadOnlyWindowsHost())
    assert result["status"] == ("PASS" if drift is None else "BLOCKED")
    assert result["call_attempted"] is False
    reader_factory.assert_called_once_with()
    for call in reader.read_file.call_args_list:
        assert call.args == (path, 64 * 1024)
    if drift is None:
        evidence.assert_called_once_with()
        transport.assert_called_once_with(windows.OBSERVE_HELPER)
        assert reader.read_file.call_count == 2


def test_decision_publication_is_explicitly_closed_in_halt_evidence() -> None:
    assert "decision_publication" in halt.CLOSED_EFFECTS
    assert halt.preflight(host())["decision_publication"] == "NOT_RUN"
    assert execute(host())["decision_publication"] == "NOT_RUN"


@pytest.mark.parametrize("operation", ("preflight", "execute"))
def test_runner_rejects_missing_decision_publication_evidence(
    monkeypatch, operation
) -> None:
    primary = halt.preflight(host()) if operation == "preflight" else execute(host())
    del primary["decision_publication"]
    monkeypatch.setattr(halt, operation, lambda *args: primary)
    result = (
        runner._r8_halt_preflight()
        if operation == "preflight"
        else runner._r8_halt_execute()
    )
    assert result["status"] != "PASS"
    if operation == "execute":
        assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"


def test_halt_sources_have_no_decision_publication_boundary() -> None:
    for name in ("d10_arch128_r8_terminal_halt.py", "d10_arch128_r8_halt_windows.py"):
        tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = ast.unparse(node.func).casefold()
                assert "publish" not in target
                assert "decision_publication" not in target
    helper = (ROOT / "scripts/d10_arch128_r8_terminal_halt.ps1").read_text()
    assert "publish" not in helper.casefold()
