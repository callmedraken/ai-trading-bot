"""D8-A parser, sanitized output, and isolated source-checkout launcher."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from trading_bot.cli import pd4_read_only_settlement_qualification as cli
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_startup_qualification as startup_module,
)
from trading_bot.runtime import (
    personal_desktop_unattended_settlement_qualification as d8a,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexState,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification as Storage,
)

Diagnostic = startup_module.PersonalDesktopUnattendedPaperStartupDiagnostic
Startup = startup_module.PersonalDesktopUnattendedPaperStartupStatus


@pytest.mark.parametrize(
    "args",
    [
        ["--account", "secret"],
        ["--session", "2026-08-25"],
        ["--decision-id", "secret"],
        ["--effect"],
        ["--root", "secret"],
        ["secret"],
    ],
)
def test_semantic_arguments_rejected_before_production(monkeypatch, capsys, args):
    monkeypatch.setattr(
        cli,
        "qualify_personal_desktop_unattended_settlement",
        lambda: pytest.fail("production invoked"),
    )
    assert cli.main(args) == 2
    record = json.loads(capsys.readouterr().err)
    assert record["reason"] == "INVALID_ARGUMENTS"
    assert "secret" not in json.dumps(record)
    assert record["real_effect_performed"] is False


@pytest.mark.parametrize("populated", [False, True])
def test_bounded_record_and_blocked_exit(monkeypatch, capsys, populated):
    evidence = {
        "startup_diagnostic": Diagnostic.QUALIFICATION_BLOCKED,
        "startup_storage_classification": Storage.FINALIZED_IDENTICAL,
        "startup_operation_classification": PaperOperationClassification.BLOCKED,
        "startup_operation_diagnostic": PaperOperationInspectionCode.INVALID_RECEIPT,
        "startup_mutex_acquisition_state": PaperAccountMutexState.OWNED,
    }
    result = d8a.SettlementQualificationResult(
        d8a.Status.BLOCKED,
        startup_status=Startup.BLOCKED,
        all_eight_gates_closed=True,
        **(evidence if populated else {}),
    )
    monkeypatch.setattr(
        cli, "qualify_personal_desktop_unattended_settlement", lambda: result
    )
    assert cli.main([]) == 6
    output = capsys.readouterr().out
    record = json.loads(output)
    assert output == json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    for field, value in evidence.items():
        assert record[field] == (value.value if populated else None)
    assert record["classification"] == "BLOCKED"
    assert record["all_eight_gates_closed"] is True
    assert record["real_effect_performed"] is False
    assert not any(
        name in key
        for key in record
        for name in ("authority", "binding", "permit", "path", "handle", "credential")
    )


def test_forged_diagnostic_is_rejected_without_leaking_raw_data(monkeypatch, capsys):
    result = d8a.SettlementQualificationResult(d8a.Status.BLOCKED)
    object.__setattr__(result, "startup_diagnostic", "secret/raw/path/exception")
    monkeypatch.setattr(
        cli, "qualify_personal_desktop_unattended_settlement", lambda: result
    )
    assert cli.main([]) == 5
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err)["reason"] == "VALIDATION_BLOCKED"
    assert "secret" not in output.err


def test_launcher_isolated_from_cwd_and_ambient_package(tmp_path):
    launcher = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run_personal_desktop_read_only_settlement_qualification.py"
    )
    result = subprocess.run(
        [sys.executable, "-I", str(launcher), "--account", "secret"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stderr)["reason"] == "INVALID_ARGUMENTS"
    assert "secret" not in result.stderr
