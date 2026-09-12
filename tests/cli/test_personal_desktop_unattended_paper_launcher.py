"""Focused PD4-E no-argument launcher coverage."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest

import trading_bot.cli.personal_desktop_unattended_paper_launcher as launcher
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as receipt_recovery,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as unattended_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_storage_provisioning as storage_provisioning,
)

_ROOT = Path(__file__).resolve().parents[2]


def test_launcher_is_cwd_and_package_root_independent(tmp_path: Path) -> None:
    alternate_root = tmp_path / "alternate-package"
    alternate_cli = alternate_root / "trading_bot" / "cli"
    alternate_cli.mkdir(parents=True)
    (alternate_root / "trading_bot" / "__init__.py").write_text("")
    (alternate_cli / "__init__.py").write_text("")
    (alternate_cli / "personal_desktop_unattended_paper_launcher.py").write_text(
        "def main(argv=None):\n    print('alternate package selected')\n    return 73\n"
    )
    away = tmp_path / "away-from-repository"
    away.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(alternate_root)
    script = _ROOT / "scripts" / "run_personal_desktop_unattended_paper_operation.py"
    expected = "Validate the frozen PD4-E unattended launcher contract"

    for command in (
        [sys.executable, "-I", str(script), "--help"],
        [sys.executable, str(script), "--help"],
    ):
        completed = subprocess.run(
            command,
            cwd=away,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0
        assert expected in completed.stdout
        assert "alternate package selected" not in completed.stdout
        assert completed.stderr == ""


def test_parser_has_no_semantic_override_and_bad_arguments_are_sanitized(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert launcher.build_parser().parse_args([]).__dict__ == {}
    hostile = r"--paper-account=C:\secret\credential-material"
    with pytest.raises(launcher._CliUsageError):
        launcher.build_parser().parse_args([hostile])
    assert launcher.main([hostile]) == launcher._EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "secret" not in captured.err
    assert json.loads(captured.err) == {
        "reason": "INVALID_ARGUMENTS",
        "schema": launcher._SCHEMA,
    }


def test_source_only_main_emits_sanitized_non_authorizing_evidence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert launcher.main([]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "diagnostic": "SOURCE_ONLY_ZERO_ARGUMENT_BOUNDARY",
        "execution_performed": False,
        "invocation_published": False,
        "qualification_performed": False,
        "recovery_performed": False,
        "schema": launcher._SCHEMA,
        "scheduler_modified": False,
        "status": "EFFECTS_CLOSED",
    }
    forbidden = ("S-1-", "F:\\", "account", "snapshot", "credential")
    assert all(value not in captured.out for value in forbidden)


def test_any_open_gate_fails_closed() -> None:
    closed = launcher._EffectGateState(False, False, False, False, False, False)
    assert launcher._all_effect_gates_are_closed(closed)
    for field in fields(launcher._EffectGateState):
        values = {item.name: False for item in fields(launcher._EffectGateState)}
        values[field.name] = True
        assert not launcher._all_effect_gates_are_closed(
            launcher._EffectGateState(**values)
        )


def test_all_six_real_effect_gates_remain_false() -> None:
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        receipt_recovery.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert (
        unattended_execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        storage_provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED
        is False
    )


def test_pd4e_source_reaches_no_scheduler_or_trading_effect_callable() -> None:
    paths = (
        _ROOT
        / "src"
        / "trading_bot"
        / "cli"
        / "personal_desktop_unattended_paper_launcher.py",
        _ROOT / "scripts" / "run_personal_desktop_unattended_paper_operation.py",
    )
    forbidden = {
        "schtasks",
        "register_task",
        "create_task",
        "modify_task",
        "run_task",
        "provider_call",
        "recover_paper_operation_receipt_once",
        "execute_paper_operation_once",
        "execute_personal_desktop_unattended_paper_operation",
        "open_personal_desktop_unattended_invocation_output_capability",
        "broker_order",
        "live_order",
    }
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called = {
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
        }
        assert called.isdisjoint(forbidden)
