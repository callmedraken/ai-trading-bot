"""Focused D6 sanitized, zero-argument source-checkout launcher tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from trading_bot.cli import (
    personal_desktop_unattended_decision_publication_launcher as cli,
)
from trading_bot.runtime.personal_desktop_unattended_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationClassification as Status,
)
from trading_bot.runtime.personal_desktop_unattended_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationResult as Result,
)


def test_parser_accepts_no_semantic_arguments_and_sanitizes_errors(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        cli,
        "run_personal_desktop_unattended_decision_publication",
        lambda: calls.append(True),
    )
    assert cli.build_parser().parse_args([]).__dict__ == {}
    assert cli.main([r"--session=2026-09-15&credential=C:\secret"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "secret" not in captured.err
    assert json.loads(captured.err)["reason"] == "INVALID_ARGUMENTS"
    assert calls == []


@pytest.mark.parametrize("status", list(Status))
def test_one_call_bounded_record_and_conservative_exit(monkeypatch, capsys, status):
    calls = []

    def run():
        calls.append(True)
        return Result(status)

    monkeypatch.setattr(
        cli, "run_personal_desktop_unattended_decision_publication", run
    )
    expected = (
        0
        if status
        in (
            Status.DECISION_NOT_READY,
            Status.DECISION_PUBLISHED,
            Status.DECISION_ALREADY_FINALIZED,
        )
        else 6
    )
    assert cli.main([]) == expected
    assert calls == [True]
    record = json.loads(capsys.readouterr().out)
    assert record == {
        "schema": cli._SCHEMA,
        "classification": status.value,
        "decision_id": None,
        "selected_session": None,
        "intended_execution_session": None,
        "real_effect_performed": False,
    }


@pytest.mark.parametrize("invalid", [None, object(), "private credential"])
def test_invalid_result_sanitized(monkeypatch, capsys, invalid):
    monkeypatch.setattr(
        cli, "run_personal_desktop_unattended_decision_publication", lambda: invalid
    )
    assert cli.main([]) == 5
    captured = capsys.readouterr()
    assert captured.out == "" and "credential" not in captured.err
    assert json.loads(captured.err)["reason"] == "RESULT_INVALID"


def test_runtime_exception_sanitized_and_not_retried(monkeypatch, capsys):
    calls = []

    def fail():
        calls.append(True)
        raise RuntimeError("private credential")

    monkeypatch.setattr(
        cli, "run_personal_desktop_unattended_decision_publication", fail
    )
    assert cli.main([]) == 5
    assert calls == [True] and "credential" not in capsys.readouterr().err


def test_launcher_is_isolated_source_checkout_and_cwd_independent(tmp_path):
    alternate = tmp_path / "alternate"
    package = alternate / "trading_bot" / "cli"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    (
        package / "personal_desktop_unattended_decision_publication_launcher.py"
    ).write_text(
        "def main():\n    print('alternate package selected')\n    return 73\n"
    )
    away = tmp_path / "away"
    away.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(alternate)
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run_personal_desktop_unattended_decision_publication.py"
    )
    for flags in (["-I"], []):
        completed = subprocess.run(
            [sys.executable, *flags, str(script), "--help"],
            cwd=away,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0
        assert "PD4-D6 zero-argument decision-only launcher" in completed.stdout
        assert "alternate package selected" not in completed.stdout
        assert completed.stderr == ""
