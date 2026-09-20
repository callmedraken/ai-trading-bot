"""D8-A parser, sanitized output, and isolated source-checkout launcher."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from trading_bot.cli import pd4_read_only_settlement_qualification as cli
from trading_bot.runtime import (
    personal_desktop_unattended_settlement_qualification as d8a,
)


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


def test_bounded_record_and_blocked_exit(monkeypatch, capsys):
    result = d8a.SettlementQualificationResult(d8a.Status.BLOCKED)
    monkeypatch.setattr(
        cli, "qualify_personal_desktop_unattended_settlement", lambda: result
    )
    assert cli.main([]) == 6
    record = json.loads(capsys.readouterr().out)
    assert record["classification"] == "BLOCKED"
    assert record["real_effect_performed"] is False
    assert not any(
        name in key
        for key in record
        for name in ("authority", "binding", "permit", "path", "handle", "credential")
    )


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
