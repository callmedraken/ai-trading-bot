from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

import trading_bot.cli.pd4_operator_observability_snapshot as cli_module
from trading_bot.cli.pd4_operator_observability_snapshot import (
    build_parser,
    diagnostic_record,
    main,
)
from trading_bot.gui.operator_observability_models import (
    OperatorEffectGateState,
)
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.operator_observability_snapshot import (
    OperatorObservabilitySnapshotResult,
    OperatorPaperAccountView,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification,
)


def _result(
    classification: PersonalDesktopUnattendedDailyCycleClassification = (
        PersonalDesktopUnattendedDailyCycleClassification.CAPTURE_REQUIRED
    ),
) -> OperatorObservabilitySnapshotResult:
    return OperatorObservabilitySnapshotResult(
        cycle_classification=classification,
        completed_session=TradingSession(date(2026, 9, 18)),
        market_data_classification=(
            PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED
        ),
        selected_snapshot_id=None,
        warmup=None,
        account=OperatorPaperAccountView(
            paper_account_id="paper-account",
            checkpoint_id=UUID("11111111-1111-4111-8111-111111111111"),
            sequence=1,
            as_of=datetime(2026, 9, 18, 20, tzinfo=UTC),
            cash=Decimal("25000"),
            realized_profit_loss=Decimal("0"),
            positions=(),
            lineage_edge_count=1,
            receipt_count=1,
        ),
        gates=OperatorEffectGateState(
            market_data_capture=False,
            decision_publication=False,
            production=False,
            recovery=False,
            supervised_execution=False,
            receipt_recovery=False,
            unattended_execution=False,
            unattended_storage_provisioning=False,
        ),
    )


def test_parser_accepts_no_semantic_arguments() -> None:
    assert build_parser().parse_args([]) is not None
    with pytest.raises(Exception):
        build_parser().parse_args(["--session", "2026-09-18"])


def test_diagnostic_record_is_sanitized_and_json_serializable() -> None:
    record = diagnostic_record(_result())

    assert record["cycle_classification"] == "CAPTURE_REQUIRED"
    assert record["completed_session"] == "2026-09-18"
    assert record["selected_snapshot_id"] is None
    assert record["warmup"] is None
    assert record["account"]["cash"] == "25000"  # type: ignore[index]
    assert record["gates"]["all_closed"] is True  # type: ignore[index]
    assert record["real_effect_performed"] is False
    json.dumps(record)


def test_main_prints_valid_snapshot_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "read_personal_desktop_operator_observability_snapshot",
        lambda: _result(),
    )

    assert main([]) == 0
    record = json.loads(capsys.readouterr().out)

    assert record["schema"] == "personal-desktop-operator-observability-snapshot/v1"
    assert record["cycle_classification"] == "CAPTURE_REQUIRED"
    assert record["real_effect_performed"] is False


def test_main_attention_classification_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "read_personal_desktop_operator_observability_snapshot",
        lambda: _result(
            PersonalDesktopUnattendedDailyCycleClassification.SESSION_GAP
        ),
    )

    assert main([]) == 6
    record = json.loads(capsys.readouterr().out)
    assert record["cycle_classification"] == "SESSION_GAP"


def test_main_blocks_on_validation_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def blocked() -> OperatorObservabilitySnapshotResult:
        raise ValueError("secret detail must not escape")

    monkeypatch.setattr(
        cli_module,
        "read_personal_desktop_operator_observability_snapshot",
        blocked,
    )

    assert main([]) == 5
    error = json.loads(capsys.readouterr().err)
    assert error == {
        "real_effect_performed": False,
        "reason": "VALIDATION_BLOCKED",
        "schema": "personal-desktop-operator-observability-snapshot/v1",
    }
