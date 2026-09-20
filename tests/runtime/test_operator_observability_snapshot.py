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
from trading_bot.runtime import (
    personal_desktop_unattended_paper_startup_qualification as startup_qualification,
)
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
from trading_bot.runtime.personal_desktop_unattended_paper_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationStatus,
)

PersonalDesktopUnattendedPaperStartupStatus = (
    startup_qualification.PersonalDesktopUnattendedPaperStartupStatus
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
    current_fields: bool = False,
) -> PersonalDesktopUnattendedDailyCycleResult:
    return PersonalDesktopUnattendedDailyCycleResult(
        classification=classification,
        completed_session=TradingSession(date(2026, 9, 18)),
        selected_snapshot_id=(
            UUID("22222222-2222-4222-8222-222222222222") if selected else None
        ),
        pending_decision_id=(
            UUID("33333333-3333-4333-8333-333333333333") if current_fields else None
        ),
        next_decision_id=(
            UUID("44444444-4444-4444-8444-444444444444") if current_fields else None
        ),
        invocation_id=(
            UUID("55555555-5555-4555-8555-555555555555") if current_fields else None
        ),
        operation_id=(
            UUID("66666666-6666-4666-8666-666666666666") if current_fields else None
        ),
        account_predecessor_checkpoint_id=(
            UUID("77777777-7777-4777-8777-777777777777") if current_fields else None
        ),
        final_checkpoint_id=(
            UUID("88888888-8888-4888-8888-888888888888") if current_fields else None
        ),
        market_data_classification=(
            _Capture.NO_NEW_COMPLETED_SESSION if selected else _Capture.CAPTURE_REQUIRED
        ),
        decision_publication_status=(
            PersonalDesktopUnattendedDecisionPublicationStatus.DECISION_READY
            if current_fields
            else None
        ),
        settlement_status=(
            PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED
            if current_fields
            else None
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
    monkeypatch.setattr(snapshot_module, "ValidatedProductionAuthority", _FakeAuthority)
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


def test_current_g6_settlement_fields_are_carried_as_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snapshot_module, "ValidatedProductionAuthority", _FakeAuthority)
    cycle = _cycle(
        PersonalDesktopUnattendedDailyCycleClassification.DECISION_READY,
        selected=False,
        current_fields=True,
    )

    result = read_personal_desktop_operator_observability_snapshot_for_test(
        _dependencies(cycle)
    )

    assert result.pending_decision_id == cycle.pending_decision_id
    assert result.next_decision_id == cycle.next_decision_id
    assert result.invocation_id == cycle.invocation_id
    assert result.operation_id == cycle.operation_id
    assert result.account_predecessor_checkpoint_id == (
        cycle.account_predecessor_checkpoint_id
    )
    assert result.final_checkpoint_id == cycle.final_checkpoint_id
    assert result.decision_publication_status is cycle.decision_publication_status
    assert result.settlement_status is cycle.settlement_status


def test_selected_cycle_includes_adapted_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(snapshot_module, "ValidatedProductionAuthority", _FakeAuthority)
    warmup = OperatorWarmupView(
        classification=OperatorWarmupClassification.WARMING_UP,
        required_sessions=tuple(date(2026, 9, day) for day in (11, 14, 15, 16, 17, 18)),
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

    assert result.selected_snapshot_id == UUID("22222222-2222-4222-8222-222222222222")
    assert result.warmup is warmup
    assert result.gates.all_closed is True


def test_open_gate_blocks_before_g6(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snapshot_module, "ValidatedProductionAuthority", _FakeAuthority)
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
    monkeypatch.setattr(snapshot_module, "ValidatedProductionAuthority", _FakeAuthority)
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
    monkeypatch.setattr(snapshot_module, "ValidatedProductionAuthority", _FakeAuthority)
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


def test_production_window_read_skips_p2_without_selected_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = object()
    calls: list[str] = []
    monkeypatch.setattr(
        snapshot_module,
        "require_validated_production_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        snapshot_module,
        "WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority",
        lambda value: calls.append("reader"),
    )
    cycle = _cycle(
        PersonalDesktopUnattendedDailyCycleClassification.CAPTURE_REQUIRED,
        selected=False,
    )

    assert snapshot_module._read_window_production(authority, cycle) is None
    assert calls == []


def test_production_window_read_requires_g6_snapshot_to_match_p2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = object()
    cycle = _cycle(
        PersonalDesktopUnattendedDailyCycleClassification.WARMING_UP,
        selected=True,
    )

    class _Audit:
        snapshot_id = UUID("33333333-3333-4333-8333-333333333333")

    class _Selected:
        audit = _Audit()

    class _Current:
        selected = _Selected()

    class _Reader:
        def read_selected_snapshot_for_session(
            self,
            session: TradingSession,
        ) -> object:
            assert session == cycle.completed_session
            return _Current()

    monkeypatch.setattr(
        snapshot_module,
        "require_validated_production_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        snapshot_module,
        "WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority",
        lambda value: _Reader(),
    )

    with pytest.raises(OperatorObservabilitySnapshotError, match="does not match P2"):
        snapshot_module._read_window_production(authority, cycle)


def test_production_window_read_retains_reader_for_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = object()
    cycle = _cycle(
        PersonalDesktopUnattendedDailyCycleClassification.WARMING_UP,
        selected=True,
    )
    sentinel_window = object()
    sentinel_config = object()

    class _Audit:
        snapshot_id = cycle.selected_snapshot_id

    class _Selected:
        audit = _Audit()

    class _Current:
        selected = _Selected()

    class _Reader:
        def read_selected_snapshot_for_session(
            self,
            session: TradingSession,
        ) -> object:
            assert session == cycle.completed_session
            return _Current()

        def inspect_strategy_history_window(
            self,
            current: object,
            config: object,
        ) -> object:
            assert type(current) is _Current
            assert config is sentinel_config
            return sentinel_window

    retained: list[object] = []
    monkeypatch.setattr(
        snapshot_module,
        "require_validated_production_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        snapshot_module,
        "WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority",
        lambda value: _Reader(),
    )
    monkeypatch.setattr(
        snapshot_module,
        "personal_desktop_unattended_strategy_config",
        lambda: sentinel_config,
    )

    assert (
        snapshot_module._read_window_production(
            authority,
            cycle,
            retained_readers=retained,  # type: ignore[arg-type]
        )
        is sentinel_window
    )
    assert len(retained) == 1


def test_production_account_read_uses_resolved_historical_configurations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = object()
    registered = object()
    evidence = object()
    expected = _account()
    configurations = (b"configuration-one", b"configuration-two")
    observed: list[object] = []

    monkeypatch.setattr(
        snapshot_module,
        "require_validated_production_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        snapshot_module,
        "resolve_personal_desktop_historical_cycle_configurations",
        lambda value: configurations,
    )

    def read_account(
        value: object,
        *,
        historical_cycle_configuration_payloads: tuple[bytes, ...],
    ) -> object:
        observed.extend((value, historical_cycle_configuration_payloads))
        return registered

    monkeypatch.setattr(
        snapshot_module,
        "read_personal_desktop_paper_account",
        read_account,
    )
    monkeypatch.setattr(
        snapshot_module,
        "require_validated_personal_desktop_paper_account",
        lambda value: evidence if value is registered else None,
    )
    monkeypatch.setattr(
        snapshot_module,
        "_adapt_account",
        lambda value: expected if value is evidence else None,
    )

    assert snapshot_module._read_account_production(authority) is expected
    assert observed == [authority, configurations]
