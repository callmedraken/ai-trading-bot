"""Sanitized zero-argument D8-B CLI and isolated source launcher."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from trading_bot.cli import pd4_unattended_settlement_execution as cli
from trading_bot.runtime.personal_desktop_unattended_settlement_execution import (
    SettlementExecutionResult,
    Status,
)


@pytest.mark.parametrize(
    "argument",
    [
        "--account-id=x",
        "--decision-id=x",
        "--open-price=1",
        "--effects-enabled",
        "unexpected",
    ],
)
def test_semantic_arguments_rejected_before_production(monkeypatch, capsys, argument):
    monkeypatch.setattr(
        cli,
        "execute_personal_desktop_unattended_settlement",
        lambda: pytest.fail("D8-B production called for semantic argument"),
    )
    assert cli.main([argument]) == 2
    assert json.loads(capsys.readouterr().err)["reason"] == "INVALID_ARGUMENTS"


def test_cli_emits_only_bounded_diagnostic(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "execute_personal_desktop_unattended_settlement",
        lambda: SettlementExecutionResult(
            Status.SETTLEMENT_NOT_READY, all_eight_gates_closed=True
        ),
    )
    assert cli.main([]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["classification"] == "SETTLEMENT_NOT_READY"
    assert record["real_effect_performed"] is False
    assert "authority" not in record
    assert "plan" not in record
    assert "path" not in record


def test_source_launcher_accepts_python_isolated_mode_with_rejected_argument():
    launcher = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run_personal_desktop_unattended_settlement_execution.py"
    )
    result = subprocess.run(
        [sys.executable, "-I", str(launcher), "--account-id=x"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 2
    assert json.loads(result.stderr)["reason"] == "INVALID_ARGUMENTS"
