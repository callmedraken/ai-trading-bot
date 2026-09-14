"""Focused PD4-D2 zero-argument daily-cycle launcher coverage."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from dataclasses import fields
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import trading_bot.cli.personal_desktop_unattended_paper_launcher as launcher
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as receipt_recovery,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_market_data_capture as market_data_capture,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_publication as decision_publication,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as unattended_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_startup_qualification as startup_qualification,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_storage_provisioning as storage_provisioning,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification as Classification,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleResult,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification as MarketDataStatus,
)

SettlementStatus = startup_qualification.PersonalDesktopUnattendedPaperStartupStatus

_ROOT = Path(__file__).resolve().parents[2]


def _result(
    classification: Classification,
    *,
    completed: date | None = None,
    market_data: MarketDataStatus | None = None,
    settlement: SettlementStatus | None = None,
) -> PersonalDesktopUnattendedDailyCycleResult:
    return PersonalDesktopUnattendedDailyCycleResult(
        classification,
        completed_session=(
            TradingSession(completed) if completed is not None else None
        ),
        market_data_classification=market_data,
        settlement_status=settlement,
    )


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
    expected = "Run the frozen PD4-D2 zero-argument daily-cycle launcher"

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


def test_contract_mismatch_fails_before_g6(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        launcher, "personal_desktop_unattended_scheduler_contract", object
    )
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_daily_cycle",
        lambda: calls.append("g6"),
    )
    assert launcher.main([]) == launcher._EXIT_CONTRACT
    assert calls == []
    assert json.loads(capsys.readouterr().err)["reason"] == (
        "SCHEDULER_CONTRACT_INVALID"
    )


@pytest.mark.parametrize("invalid", (True, 1, None, "False"))
def test_each_individual_open_or_non_bool_gate_fails_before_g6(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    invalid: object,
) -> None:
    for changed_field in fields(launcher._EffectGateState):
        calls: list[str] = []
        values = {item.name: False for item in fields(launcher._EffectGateState)}
        values[changed_field.name] = invalid
        state = launcher._EffectGateState(**values)
        monkeypatch.setattr(launcher, "_effect_gate_state", lambda value=state: value)
        monkeypatch.setattr(
            launcher,
            "run_personal_desktop_unattended_daily_cycle",
            lambda calls=calls: calls.append("g6"),
        )
        assert launcher.main([]) == launcher._EXIT_GATE
        assert calls == []
        assert json.loads(capsys.readouterr().err)["reason"] == (
            "EFFECT_GATE_STATE_INVALID"
        )


def test_exact_all_closed_gate_set_calls_g6_once_and_emits_capture_required(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []
    result = _result(
        Classification.CAPTURE_REQUIRED,
        completed=date(2026, 9, 11),
        market_data=MarketDataStatus.CAPTURE_REQUIRED,
    )

    def run() -> PersonalDesktopUnattendedDailyCycleResult:
        calls.append("g6")
        return result

    monkeypatch.setattr(
        launcher,
        "_effect_gate_state",
        lambda: launcher._EffectGateState(*((False,) * 8)),
    )
    monkeypatch.setattr(launcher, "run_personal_desktop_unattended_daily_cycle", run)
    assert launcher.main([]) == 0
    assert calls == ["g6"]
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "classification": "CAPTURE_REQUIRED",
        "completed_session": "2026-09-11",
        "decision_publication_status": None,
        "market_data_classification": "CAPTURE_REQUIRED",
        "real_effect_performed": False,
        "scheduler_modified": False,
        "schema": "personal-desktop-unattended-paper-launcher/v2",
        "settlement_status": None,
        "status": "EFFECTS_CLOSED",
    }
    forbidden = (
        "S-1-",
        "F:\\",
        "credential",
        "permit",
        "capability",
        "handle",
        "security_descriptor",
        "authority",
    )
    assert all(value not in captured.out.casefold() for value in forbidden)


def test_warming_up_is_a_successful_sanitized_classification(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_daily_cycle",
        lambda: _result(Classification.WARMING_UP),
    )
    assert launcher.main([]) == 0
    assert json.loads(capsys.readouterr().out)["classification"] == "WARMING_UP"


def test_blocked_is_surfaced_with_conservative_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_daily_cycle",
        lambda: _result(Classification.BLOCKED),
    )
    assert launcher.main([]) == launcher._EXIT_UNSAFE_CLASSIFICATION
    record = json.loads(capsys.readouterr().out)
    assert record["classification"] == "BLOCKED"
    assert record["real_effect_performed"] is False


def test_real_effect_result_is_rejected_even_when_injected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = SimpleNamespace(
        classification=Classification.CAPTURE_REQUIRED,
        real_effect_performed=True,
    )
    monkeypatch.setattr(
        launcher, "run_personal_desktop_unattended_daily_cycle", lambda: fake
    )
    assert launcher.main([]) == launcher._EXIT_RESULT
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["reason"] == "DAILY_CYCLE_RESULT_INVALID"


def test_all_eight_real_effect_gates_remain_committed_false() -> None:
    assert (
        market_data_capture.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED
        is False
    )
    assert (
        decision_publication.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED
        is False
    )
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


def test_launcher_reaches_only_g6_and_never_mutates_scheduler_or_opens_gates() -> None:
    paths = (
        _ROOT
        / "src"
        / "trading_bot"
        / "cli"
        / "personal_desktop_unattended_paper_launcher.py",
        _ROOT / "scripts" / "run_personal_desktop_unattended_paper_operation.py",
    )
    forbidden_calls = {
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
    called: set[str] = set()
    assigned: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called.update(
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
        )
        assigned.update(
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        )
    assert "run_personal_desktop_unattended_daily_cycle" in called
    assert called.isdisjoint(forbidden_calls)
    assert not any(name.endswith("EFFECTS_ENABLED") for name in assigned)
