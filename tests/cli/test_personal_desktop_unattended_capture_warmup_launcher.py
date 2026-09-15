"""Focused Architecture-112 D5 capture-only launcher coverage."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

import trading_bot.cli.personal_desktop_unattended_capture_warmup_launcher as launcher
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_capture_warmup import (
    PersonalDesktopUnattendedCaptureWarmupGateState,
    PersonalDesktopUnattendedCaptureWarmupResult,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification as CycleStatus,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification as CaptureStatus,
)

_ROOT = Path(__file__).resolve().parents[2]
_SESSION = TradingSession(date(2026, 9, 11))


def _closed() -> PersonalDesktopUnattendedCaptureWarmupGateState:
    return PersonalDesktopUnattendedCaptureWarmupGateState(*((False,) * 8))


def _result(
    classification: CycleStatus,
    *,
    market_data: CaptureStatus = CaptureStatus.NO_NEW_COMPLETED_SESSION,
    capture_performed: bool = False,
    provider_attempt_may_have_occurred: bool = False,
    real_effect_performed: bool = False,
) -> PersonalDesktopUnattendedCaptureWarmupResult:
    return PersonalDesktopUnattendedCaptureWarmupResult(
        classification,
        completed_session=_SESSION,
        market_data_classification=market_data,
        cycle_classification=classification,
        capture_performed=capture_performed,
        provider_attempt_may_have_occurred=provider_attempt_may_have_occurred,
        real_effect_performed=real_effect_performed,
    )


def test_launcher_is_cwd_and_package_root_independent(tmp_path: Path) -> None:
    alternate_root = tmp_path / "alternate-package"
    alternate_cli = alternate_root / "trading_bot" / "cli"
    alternate_cli.mkdir(parents=True)
    (alternate_root / "trading_bot" / "__init__.py").write_text("")
    (alternate_cli / "__init__.py").write_text("")
    alternate_module = (
        alternate_cli / "personal_desktop_unattended_capture_warmup_launcher.py"
    )
    alternate_module.write_text(
        "def main(argv=None):\n    print('alternate package selected')\n    return 73\n"
    )
    away = tmp_path / "away-from-repository"
    away.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(alternate_root)
    script = _ROOT / "scripts" / "run_personal_desktop_unattended_capture_warmup.py"
    expected = "Run the frozen PD4-D5 zero-argument capture-only warm-up launcher."

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
    hostile = r"--session=2026-09-11&credential=C:\secret"
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


def test_contract_mismatch_fails_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        launcher,
        "personal_desktop_unattended_capture_warmup_scheduler_contract",
        object,
    )
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_capture_warmup",
        lambda: calls.append("runtime"),
    )
    assert launcher.main([]) == launcher._EXIT_CONTRACT
    assert calls == []
    assert json.loads(capsys.readouterr().err)["reason"] == (
        "SCHEDULER_CONTRACT_INVALID"
    )


def test_open_gate_fails_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        launcher,
        "personal_desktop_unattended_capture_warmup_gate_state",
        lambda: PersonalDesktopUnattendedCaptureWarmupGateState(
            True, False, False, False, False, False, False, False
        ),
    )
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_capture_warmup",
        lambda: calls.append("runtime"),
    )
    assert launcher.main([]) == launcher._EXIT_GATE
    assert calls == []
    assert json.loads(capsys.readouterr().err)["reason"] == (
        "EFFECT_GATE_STATE_INVALID"
    )


def test_warming_up_emits_bounded_success_record(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        launcher,
        "personal_desktop_unattended_capture_warmup_gate_state",
        _closed,
    )
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_capture_warmup",
        lambda: _result(CycleStatus.WARMING_UP),
    )
    assert launcher.main([]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "capture_performed": False,
        "classification": "WARMING_UP",
        "completed_session": "2026-09-11",
        "cycle_classification": "WARMING_UP",
        "market_data_classification": "NO_NEW_COMPLETED_SESSION",
        "provider_attempt_may_have_occurred": False,
        "real_effect_performed": False,
        "scheduler_modified": False,
        "schema": "personal-desktop-unattended-capture-warmup-launcher/v1",
        "status": "CAPTURE_WARMUP",
    }


def test_successful_capture_warming_up_is_normal_zero_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        launcher,
        "personal_desktop_unattended_capture_warmup_gate_state",
        _closed,
    )
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_capture_warmup",
        lambda: _result(
            CycleStatus.WARMING_UP,
            market_data=CaptureStatus.CAPTURE_REQUIRED,
            capture_performed=True,
            provider_attempt_may_have_occurred=True,
            real_effect_performed=True,
        ),
    )
    assert launcher.main([]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["capture_performed"] is True
    assert record["real_effect_performed"] is True
    assert record["classification"] == "WARMING_UP"


def test_decision_ready_is_safe_handoff_without_publication(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        launcher,
        "personal_desktop_unattended_capture_warmup_gate_state",
        _closed,
    )
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_capture_warmup",
        lambda: _result(CycleStatus.DECISION_READY),
    )
    assert launcher.main([]) == 0
    assert json.loads(capsys.readouterr().out)["classification"] == "DECISION_READY"


@pytest.mark.parametrize(
    "classification",
    (
        CycleStatus.BLOCKED,
        CycleStatus.SESSION_GAP,
        CycleStatus.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
        CycleStatus.RECEIPT_RECOVERY_REQUIRED,
        CycleStatus.MISSED_DECISION_DEADLINE,
        CycleStatus.CAPTURE_REQUIRED,
        CycleStatus.EXECUTION_READY,
        CycleStatus.ALREADY_APPLIED,
        CycleStatus.DECISION_ALREADY_FINALIZED,
    ),
)
def test_unsafe_or_unexpected_classification_is_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    classification: CycleStatus,
) -> None:
    monkeypatch.setattr(
        launcher,
        "personal_desktop_unattended_capture_warmup_gate_state",
        _closed,
    )
    monkeypatch.setattr(
        launcher,
        "run_personal_desktop_unattended_capture_warmup",
        lambda: _result(classification),
    )
    assert launcher.main([]) == launcher._EXIT_UNSAFE_CLASSIFICATION
    assert json.loads(capsys.readouterr().out)["classification"] == classification.value


def test_launcher_does_not_directly_open_gates_or_reach_effect_roots() -> None:
    paths = (
        _ROOT
        / "src"
        / "trading_bot"
        / "cli"
        / "personal_desktop_unattended_capture_warmup_launcher.py",
        _ROOT / "scripts" / "run_personal_desktop_unattended_capture_warmup.py",
    )
    forbidden_calls = {
        "schtasks",
        "register_task",
        "create_task",
        "modify_task",
        "run_task",
        "run_personal_desktop_unattended_market_data_capture",
        "WindowsEffectfulDailySnapshotCapture",
        "qualify_personal_desktop_unattended_decision_publication",
        "execute_personal_desktop_unattended_paper_operation",
        "recover_personal_desktop_paper_operation_receipt_once",
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
    assert "run_personal_desktop_unattended_capture_warmup" in called
    assert called.isdisjoint(forbidden_calls)
    assert not any(name.endswith("EFFECTS_ENABLED") for name in assigned)
