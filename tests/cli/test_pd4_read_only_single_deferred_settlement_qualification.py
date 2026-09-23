"""D8-R1 zero-semantic-argument CLI and sanitized result tests."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from trading_bot.cli import (
    pd4_read_only_single_deferred_settlement_qualification as cli,
)
from trading_bot.runtime import (
    personal_desktop_single_deferred_settlement_qualification as d8r,
)


@pytest.mark.parametrize(
    "args",
    [
        ["--session", "2026-08-25"],
        ["--decision-id", "secret"],
        ["--path", "secret"],
        ["--effect"],
        ["secret"],
    ],
)
def test_semantic_arguments_rejected_before_production(monkeypatch, capsys, args):
    monkeypatch.setattr(
        cli,
        "qualify_personal_desktop_single_deferred_settlement",
        lambda: pytest.fail("production invoked"),
    )
    assert cli.main(args) == 2
    record = json.loads(capsys.readouterr().err)
    assert record["reason"] == "INVALID_ARGUMENTS"
    assert record["real_effect_performed"] is False
    assert "secret" not in json.dumps(record)


@pytest.mark.parametrize(
    "status,exit_code",
    [
        (d8r.Status.BLOCKED, 6),
        (d8r.Status.EXECUTION_READY, 0),
    ],
)
def test_bounded_result_and_exit_never_authorizes(
    monkeypatch, capsys, status, exit_code
):
    if status is d8r.Status.BLOCKED:
        result = d8r.DeferredSettlementQualificationResult(status)
    else:
        from datetime import date

        from trading_bot.market_calendar import TradingSession

        result = d8r.DeferredSettlementQualificationResult(
            status,
            current_completed_session=TradingSession(date(2026, 8, 26)),
            deferred_execution_session=TradingSession(date(2026, 8, 25)),
        )
    monkeypatch.setattr(
        cli, "qualify_personal_desktop_single_deferred_settlement", lambda: result
    )
    assert cli.main([]) == exit_code
    output = capsys.readouterr().out
    record = json.loads(output)
    assert output == json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    assert record["classification"] == status.value
    assert record["real_effect_performed"] is False
    assert not any(
        word in key
        for key in record
        for word in ("authority", "binding", "permit", "path", "handle", "credential")
    )


def test_forged_result_is_rejected_without_leaking_raw_data(monkeypatch, capsys):
    result = d8r.DeferredSettlementQualificationResult(d8r.Status.BLOCKED)
    object.__setattr__(result, "startup_diagnostic", "secret/raw/path")
    monkeypatch.setattr(
        cli, "qualify_personal_desktop_single_deferred_settlement", lambda: result
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
        / "run_personal_desktop_read_only_single_deferred_settlement_qualification.py"
    )
    result = subprocess.run(
        [sys.executable, "-I", str(launcher), "--session", "secret"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stderr)["reason"] == "INVALID_ARGUMENTS"
