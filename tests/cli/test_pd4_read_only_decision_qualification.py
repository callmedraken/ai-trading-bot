"""D7-A zero-argument parser and bounded JSON, without production invocation."""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from tests.runtime.test_personal_desktop_unattended_decision_qualification import (
    Harness,
)

from trading_bot.cli import pd4_read_only_decision_qualification as cli
from trading_bot.runtime import personal_desktop_unattended_decision_qualification as d7


@pytest.mark.parametrize(
    "args",
    [
        ["--account", "secret"],
        ["--session", "2026-09-14"],
        ["--effect"],
        ["--storage-root", "secret"],
        ["secret"],
    ],
)
def test_semantic_args_rejected_before_boundary(monkeypatch, capsys, args):
    def forbidden():
        pytest.fail("semantic arguments entered D7-A production")

    monkeypatch.setattr(cli, "qualify_personal_desktop_unattended_decision", forbidden)
    assert cli.main(args) == 2
    captured = capsys.readouterr()
    assert "secret" not in captured.err
    assert json.loads(captured.err)["real_effect_performed"] is False


@pytest.mark.parametrize(
    "status,exit_code",
    [
        (d7.Status.READY, 0),
        (d7.Status.ALREADY_FINALIZED, 0),
        (d7.Status.WARMING_UP, 0),
        (d7.Status.NAMESPACE_MISSING, 6),
        (d7.Status.BLOCKED, 6),
        (d7.Status.MISSED_DECISION_DEADLINE, 6),
        (d7.Status.SESSION_GAP, 6),
    ],
)
def test_sanitized_deterministic_evidence(monkeypatch, capsys, status, exit_code):
    result = Harness(monkeypatch).run()
    result = replace(result, classification=status)
    monkeypatch.setattr(
        cli, "qualify_personal_desktop_unattended_decision", lambda: result
    )
    assert cli.main([]) == exit_code
    first = capsys.readouterr().out
    assert cli.main([]) == exit_code
    assert capsys.readouterr().out == first
    record = json.loads(first)
    assert record["real_effect_performed"] is False
    assert record["candidate_decision_id"] == str(result.candidate_decision_id)
    assert record["completed_session"] == "2026-08-24"
    assert record["regular_open"] == "2026-08-25T13:30:00+00:00"
    for forbidden in ("permit", "handle", "credential", "path", "acl", "authority"):
        assert not any(forbidden in key for key in record)


def test_invalid_result_is_sanitized(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "qualify_personal_desktop_unattended_decision", lambda: object()
    )
    assert cli.main([]) == 5
    assert json.loads(capsys.readouterr().err)["reason"] == "VALIDATION_BLOCKED"


def test_source_checkout_launcher_independent_of_cwd(tmp_path):
    launcher = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run_personal_desktop_read_only_decision_qualification.py"
    )
    result = subprocess.run(
        [sys.executable, "-I", str(launcher), "--account", "secret"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "secret" not in result.stderr
    assert json.loads(result.stderr)["reason"] == "INVALID_ARGUMENTS"
