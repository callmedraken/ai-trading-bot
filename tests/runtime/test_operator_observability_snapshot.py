from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

import trading_bot.runtime.operator_observability_snapshot as snapshot_module
from trading_bot.gui.operator_observability_models import (
    OperatorWarmupClassification,
    OperatorWarmupView,
)
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.operator_observability_snapshot import (
    DisposableOperatorObservabilitySnapshotDependencies,
    OperatorObservabilitySnapshotError,
    OperatorPaperAccountView,
    read_personal_desktop_operator_observability_snapshot_for_test,
)
from trading_bot.runtime.personal_desktop_unattended_capture_warmup import (
    PersonalDesktopUnattendedCaptureWarmupGateState,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification,
    PersonalDesktopUnattendedDailyCycleResult,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification,
)

_Capture = PersonalDesktopUnattendedMarketDataCaptureClassification


class _FakeAuthority:
    pass


def _closed_gates() -> PersonalDesktopUnattendedCaptureWarmupGateState:
    return PersonalDesktopUnattendedCaptureWarmupGateState(
        market_data_capture=False,
        decision_publication=False,
        production=False,
        recovery=False,
        supervised_execution=False,
        receipt_recovery=False,
        unattended_execution=False,
        unattended_storage_provisioning=False,
    )


def _account() -> OperatorPaperAccountView:
    return OperatorPaperAccountView(
        paper_account_id="paper-account",
        checkpoint_id=UUID("11111111-1111-4111-8111-111111111111"),
        sequence=1,
        as_of=datetime(2026, 9, 18, 20, tzinfo=UTC),
        cash=Decimal("25000"),
        realized_profit_loss=Decimal("0"),
        positions=(),
        lineage_edge_count=1,
        receipt_count=1,
    )


def _cycle(
    classification: PersonalDesktopUnattendedDailyCycleClassification,
    *,
    selected: bool,
) -> PersonalDesktopUnattendedDailyCycleResult:
    return PersonalDesktopUnattendedDailyCycleResult(
        classification=classification,
        completed_session=TradingSession(date(2026, 9, 18)),
        selected_snapshot_id=(
            UUID("22222222-2222-4222-8222-222222222222")
            if selected
            else None
        ),
        market_data_classification=(
            _Capture.NO_NEW_COMPLETED_SESSION
            if selected
            else _Capture.CAPTURE_REQUIRED
        ),
    )


def _dependencies(
    cycle: PersonalDesktopUnattendedDailyCycleResult,
    *,
    gates: list[PersonalDesktopUnattendedCaptureWarmupGateState] | None = None,
    window: object | None = None,
) -> DisposableOperatorObservabilitySnapshotDependencies:
    values = [_closed_gates(), _closed_gates()] if gates is None else gates

    def gate_state() -> PersonalDesktopUnattendedCaptureWarmupGateState:
        return values.pop(0)

    authority = _FakeAuthority()
    return DisposableOperatorObservabilitySnapshotDependencies(
        gate_state=gate_state,
        run_cycle=lambda: cycle,
        acquire_c1=lambda: authority,  # type: ignore[return-value]
        validate_c1=lambda value: value,  # type: ignore[return-value]
        read_window=lambda _authority, _cycle: window,  # type: ignore[return-value]
        read_account=lambda _authority: _account(),
    )


def test_capture_required_snapshot_is_valid_without_selected_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        snapshot_module,
        "ValidatedProductionAuthority",
        _FakeAuthority,
    )
    cycle = _cycle(
        PersonalDesktopUnattendedDailyCycleClassification.CAPTURE_REQUIRED,
        selected=False,
    )

    result = read_personal_desktop_operator_observability_snapshot_for_test(
        _dependencies(cycle)
    )

    assert result.cycle_classification is (
        PersonalDesktopUnattendedDailyCycleClassification.CAPTURE_REQUIRED
    )
    assert result.selected_snapshot_id is None
    assert result.warmup is None
    assert result.account.cash == Decimal("25000")
    assert result.gates.all_closed is True
    assert result.real_effect_performed is False


def test_selected_cycle_includes_adapted_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        snapshot_module,
        "ValidatedProductionAuthority",
        _FakeAuthority,
    )
    warmup = OperatorWarmupView(
        classification=OperatorWarmupClassification.WARMING_UP,
        required_sessions=tuple(
            date(2026, 9, day) for day in (11, 14, 15, 16, 17, 18)
        ),
        selected_sessions=(),
    )
    sentinel = object()
    monkeypatch.setattr(
        snapshot_module,
        "adapt_selected_c3_history_window",
        lambda value: warmup if value is sentinel else None,
    )
    cycle = _cycle(
        PersonalDesktopUnattendedDailyCycleClassification.WARMING_UP,
        selected=True,
    )

    result = read_personal_desktop_operator_observability_snapshot_for_test(
        _dependencies(cycle, window=sentinel)
    )

    assert result.selected_snapshot_id == UUID(
        "22222222-2222-4222-8222-222222222222"
    )
    assert result.warmup is warmup
    assert result.gates.all_closed is True


def test_open_gate_blocks_before_g6(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        snapshot_module,
        "ValidatedProductionAuthority",
        _FakeAuthority,
    )
    opened = PersonalDesktopUnattendedCaptureWarmupGateState(
        market_data_capture=True,
        decision_publication=False,
        production=False,
        recovery=False,
        supervised_execution=False,
        receipt_recovery=False,
        unattended_execution=False,
        unattended_storage_provisioning=False,
    )
    called = False

    def run_cycle() -> PersonalDesktopUnattendedDailyCycleResult:
        nonlocal called
        called = True
        return _cycle(
            PersonalDesktopUnattendedDailyCycleClassification.WARMING_UP,
            selected=True,
        )

    dependencies = _dependencies(
        _cycle(
            PersonalDesktopUnattendedDailyCycleClassification.WARMING_UP,
            selected=True,
        ),
        gates=[opened],
    )
    dependencies = DisposableOperatorObservabilitySnapshotDependencies(
        gate_state=dependencies.gate_state,
        run_cycle=run_cycle,
        acquire_c1=dependencies.acquire_c1,
        validate_c1=dependencies.validate_c1,
        read_window=dependencies.read_window,
        read_account=dependencies.read_account,
    )

    with pytest.raises(OperatorObservabilitySnapshotError, match="closed before"):
        read_personal_desktop_operator_observability_snapshot_for_test(dependencies)

    assert called is False


def test_gate_drift_blocks_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        snapshot_module,
        "ValidatedProductionAuthority",
        _FakeAuthority,
    )
    after = PersonalDesktopUnattendedCaptureWarmupGateState(
        market_data_capture=False,
        decision_publication=True,
        production=False,
        recovery=False,
        supervised_execution=False,
        receipt_recovery=False,
        unattended_execution=False,
        unattended_storage_provisioning=False,
    )

    with pytest.raises(OperatorObservabilitySnapshotError, match="changed"):
        read_personal_desktop_operator_observability_snapshot_for_test(
            _dependencies(
                _cycle(
                    PersonalDesktopUnattendedDailyCycleClassification.CAPTURE_REQUIRED,
                    selected=False,
                ),
                gates=[_closed_gates(), after],
            )
        )


def test_wrong_account_result_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        snapshot_module,
        "ValidatedProductionAuthority",
        _FakeAuthority,
    )
    base = _dependencies(
        _cycle(
            PersonalDesktopUnattendedDailyCycleClassification.CAPTURE_REQUIRED,
            selected=False,
        )
    )
    dependencies = DisposableOperatorObservabilitySnapshotDependencies(
        gate_state=base.gate_state,
        run_cycle=base.run_cycle,
        acquire_c1=base.acquire_c1,
        validate_c1=base.validate_c1,
        read_window=base.read_window,
        read_account=lambda _authority: object(),  # type: ignore[return-value]
    )

    with pytest.raises(OperatorObservabilitySnapshotError, match="account read"):
        read_personal_desktop_operator_observability_snapshot_for_test(dependencies)
