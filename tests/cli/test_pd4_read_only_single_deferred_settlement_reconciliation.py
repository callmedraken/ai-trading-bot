"""D9-R1 CLI accepts no semantic arguments and emits bounded diagnostics."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.cli import (
    pd4_read_only_single_deferred_settlement_reconciliation as cli,
)
from trading_bot.cli.paper_operation_inspection import PaperOperationClassification
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.paper_operation import PaperOperationStatus
from trading_bot.runtime.personal_desktop_single_deferred_settlement_reconciliation import (  # noqa: E501
    DeferredSettlementReconciliationResult,
    Status,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification,
)


def _reconciled() -> DeferredSettlementReconciliationResult:
    return DeferredSettlementReconciliationResult(
        Status.RECONCILED,
        TradingSession(date(2026, 8, 27)),
        TradingSession(date(2026, 8, 25)),
        TradingSession(date(2026, 8, 24)),
        *(UUID(int=value) for value in range(1, 10)),
        PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL,
        PaperOperationClassification.ALREADY_APPLIED,
        PaperOperationStatus.COMPLETED,
        True,
        False,
    )


@pytest.mark.parametrize(
    "argument", ["--session", "2026-08-25", "--execute", "--path=x"]
)
def test_semantic_arguments_rejected_before_reconciliation(
    monkeypatch, capsys, argument
):
    monkeypatch.setattr(
        cli,
        "reconcile_personal_desktop_single_deferred_settlement",
        lambda: pytest.fail("D9-R1 entered after invalid CLI arguments"),
    )
    assert cli.main([argument]) == 2
    record = json.loads(capsys.readouterr().err)
    assert record["reason"] == "INVALID_ARGUMENTS"
    assert record["real_effect_performed"] is False


def test_only_reconciled_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "reconcile_personal_desktop_single_deferred_settlement", _reconciled
    )
    assert cli.main([]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["classification"] == "RECONCILED"
    assert record["current_completed_session"] == "2026-08-27"
    assert record["deferred_execution_session"] == "2026-08-25"
    assert record["successor_checkpoint_id"] == str(UUID(int=9))
    assert record["real_effect_performed"] is False
    monkeypatch.setattr(
        cli,
        "reconcile_personal_desktop_single_deferred_settlement",
        lambda: DeferredSettlementReconciliationResult(Status.NOT_APPLIED),
    )
    assert cli.main([]) == 6


def test_invalid_result_returns_five(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "reconcile_personal_desktop_single_deferred_settlement", lambda: object()
    )
    assert cli.main([]) == 5
    assert json.loads(capsys.readouterr().err)["reason"] == "VALIDATION_BLOCKED"


def test_source_checkout_launcher_rejects_semantic_argument():
    launcher_name = (
        "run_personal_desktop_read_only_single_deferred_settlement_reconciliation.py"
    )
    launcher = Path(__file__).resolve().parents[2] / "scripts" / launcher_name
    completed = subprocess.run(
        [sys.executable, "-I", str(launcher), "--session=2026-08-25"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stderr)["reason"] == "INVALID_ARGUMENTS"
