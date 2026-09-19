import ast
import inspect
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.gui import (
    operator_observability_snapshot_adapter as snapshot_adapter_module,
)
from trading_bot.gui.operator_observability_models import (
    OperatorEffectGateState,
    OperatorOperationsPageStatus,
    OperatorStrategyExplanationStatus,
    OperatorWarmupClassification,
    OperatorWarmupView,
    SelectedC3WarmupSessionView,
)
from trading_bot.gui.operator_observability_snapshot_adapter import (
    OperatorObservabilitySnapshotAdapterError,
    adapt_operator_observability_snapshot,
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


def _gates() -> OperatorEffectGateState:
    return OperatorEffectGateState(
        market_data_capture=False,
        decision_publication=False,
        production=False,
        recovery=False,
        supervised_execution=False,
        receipt_recovery=False,
        unattended_execution=False,
        unattended_storage_provisioning=False,
    )


def _warmup() -> OperatorWarmupView:
    required = (
        date(2026, 9, 11),
        date(2026, 9, 14),
        date(2026, 9, 15),
        date(2026, 9, 16),
        date(2026, 9, 17),
        date(2026, 9, 18),
    )
    closes = (
        Decimal("764.29"),
        Decimal("760.88"),
        Decimal("757.39"),
        Decimal("754.05"),
        Decimal("762.6"),
        Decimal("761.69"),
    )
    selected = tuple(
        SelectedC3WarmupSessionView(
            session_date=session,
            symbol="SPY",
            close=close,
            snapshot_id=UUID(int=index),
            selection_id=UUID(int=100 + index),
        )
        for index, (session, close) in enumerate(
            zip(required, closes, strict=True),
            start=1,
        )
    )
    return OperatorWarmupView(
        classification=OperatorWarmupClassification.READY,
        required_sessions=required,
        selected_sessions=selected,
    )


def _result() -> OperatorObservabilitySnapshotResult:
    return OperatorObservabilitySnapshotResult(
        cycle_classification=PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
        completed_session=TradingSession(date(2026, 9, 18)),
        market_data_classification=(
            PersonalDesktopUnattendedMarketDataCaptureClassification.NO_NEW_COMPLETED_SESSION
        ),
        selected_snapshot_id=UUID(int=6),
        warmup=_warmup(),
        account=OperatorPaperAccountView(
            paper_account_id="paper-account",
            checkpoint_id=UUID(int=500),
            sequence=1,
            as_of=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
            cash=Decimal("25000"),
            realized_profit_loss=Decimal("0"),
            positions=(),
            lineage_edge_count=1,
            receipt_count=1,
        ),
        gates=_gates(),
    )


def test_snapshot_adapter_copies_only_bounded_display_facts() -> None:
    state = adapt_operator_observability_snapshot(_result())

    assert state.status is OperatorOperationsPageStatus.AVAILABLE
    assert state.cycle_classification == "BLOCKED"
    assert state.completed_session == date(2026, 9, 18)
    assert state.market_data_classification == "NO_NEW_COMPLETED_SESSION"
    assert state.selected_snapshot_id == UUID(int=6)
    assert state.warmup is not None
    assert state.warmup.selected_count == 6
    assert state.strategy_ready is True
    assert state.gates is not None and state.gates.all_closed is True
    assert state.account is not None
    assert state.account.cash == Decimal("25000")
    assert state.account.positions == ()

    explanation = state.strategy_explanation
    assert explanation is not None
    assert explanation.status is OperatorStrategyExplanationStatus.BUY
    assert explanation.short_window == 3
    assert explanation.long_window == 5
    assert explanation.desired_quantity == Decimal("1")
    assert explanation.symbol == "SPY"
    assert explanation.sessions == (
        date(2026, 9, 11),
        date(2026, 9, 14),
        date(2026, 9, 15),
        date(2026, 9, 16),
        date(2026, 9, 17),
        date(2026, 9, 18),
    )
    assert explanation.closes == (
        Decimal("764.29"),
        Decimal("760.88"),
        Decimal("757.39"),
        Decimal("754.05"),
        Decimal("762.6"),
        Decimal("761.69"),
    )
    assert explanation.previous_short == Decimal("758.0133333333333333333333333")
    assert explanation.previous_long == Decimal("759.842")
    assert explanation.current_short == Decimal("759.4466666666666666666666667")
    assert explanation.current_long == Decimal("759.322")
    assert explanation.crossover_side == "BUY"
    assert explanation.actionable_side == "BUY"
    assert explanation.invested is False


def test_snapshot_adapter_rejects_wrong_type() -> None:
    with pytest.raises(OperatorObservabilitySnapshotAdapterError):
        adapt_operator_observability_snapshot(object())  # type: ignore[arg-type]


def test_o4_adapter_uses_read_only_source_owned_strategy_seam() -> None:
    source = inspect.getsource(snapshot_adapter_module)
    tree = ast.parse(source)
    called_names = {
        (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }

    assert "personal_desktop_unattended_strategy_config" in called_names
    assert "evaluate_moving_average_crossover_closes" in called_names
    assert {
        "publish",
        "provision",
        "execute",
        "run_personal_desktop_unattended_daily_cycle",
    }.isdisjoint(called_names)
