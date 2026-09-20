from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.gui.operator_observability_models import (
    OperatorEffectGateState,
    OperatorOperationsPageStatus,
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
    OperatorPaperPositionView,
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
    selected = tuple(
        SelectedC3WarmupSessionView(
            session_date=session,
            symbol="SPY",
            close=Decimal("760") + Decimal(index),
            snapshot_id=UUID(int=index),
            selection_id=UUID(int=100 + index),
        )
        for index, session in enumerate(required, start=1)
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
            positions=(
                OperatorPaperPositionView(
                    symbol="SPY",
                    quantity=Decimal("2"),
                    total_cost_basis=Decimal("1500"),
                    average_cost=Decimal("750"),
                ),
            ),
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
    assert state.account.positions[0].symbol == "SPY"


def test_snapshot_adapter_rejects_wrong_type() -> None:
    with pytest.raises(OperatorObservabilitySnapshotAdapterError):
        adapt_operator_observability_snapshot(object())  # type: ignore[arg-type]
