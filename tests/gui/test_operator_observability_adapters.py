from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Symbol
from trading_bot.gui.operator_observability_adapters import (
    OperatorObservabilityAdapterError,
    adapt_effect_gate_state,
    adapt_operator_observability_state,
    adapt_selected_c3_history_window,
)
from trading_bot.gui.operator_observability_models import OperatorWarmupClassification
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailyBarCandidate,
    DailyProviderResponse,
    DailySnapshotCaptureRequest,
    SourcePayloadEvidence,
    accept_daily_provider_response,
    build_daily_provider_request,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotAuditEvidence,
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadResult,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SelectedC3StrategyHistoryWindowClassification,
    SelectedC3StrategyHistoryWindowResult,
    SessionIndexedSelectedC3SnapshotReadResult,
    personal_desktop_unattended_capture_request,
)
from trading_bot.runtime.personal_desktop_unattended_capture_warmup import (
    PersonalDesktopUnattendedCaptureWarmupGateState,
)

_NAMESPACE = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_NEW_YORK = ZoneInfo("America/New_York")


def _session_read(
    session_date: date,
    *,
    price: Decimal,
) -> SessionIndexedSelectedC3SnapshotReadResult:
    session = TradingSession(session_date)
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    next_session = NYSEMarketCalendar().next_session(
        datetime.combine(session.session_date, time(12), tzinfo=_NEW_YORK)
    )
    requested_at = datetime.combine(
        next_session.session_date,
        time(12),
        tzinfo=_NEW_YORK,
    ).astimezone(UTC)
    symbol = Symbol("SPY")
    request = DailySnapshotCaptureRequest(
        request_id=uuid5(_NAMESPACE, f"request:{session_date}"),
        symbols=(symbol,),
        requested_at=requested_at,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
    )
    provider_request = build_daily_provider_request(
        request,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        calendar,
    )
    source = f"operator-fixture:{session_date}".encode()
    response = DailyProviderResponse(
        request=provider_request,
        candidates=(
            DailyBarCandidate(
                response_ordinal=0,
                symbol=symbol,
                session=session,
                timestamp=datetime.combine(session_date, time(20), tzinfo=UTC),
                open=price,
                high=price + Decimal("2"),
                low=price - Decimal("1"),
                close=price + Decimal("1"),
                volume=1000,
            ),
        ),
        captured_at=requested_at + timedelta(seconds=1),
        provider_as_of=requested_at,
        provider_request_id=f"operator-fixture-{session_date}",
        source_payload=SourcePayloadEvidence(
            sha256=hashlib.sha256(source).hexdigest(),
            byte_length=len(source),
            media_type="application/json",
        ),
        pagination_complete=True,
    )
    accepted = accept_daily_provider_response(provider_request, response, calendar)
    assert accepted.snapshot is not None
    payload = serialize_daily_snapshot(accepted.snapshot)
    verification = verify_daily_snapshot(payload, calendar)
    assert verification.passed
    assert verification.snapshot is not None

    audit = SelectedC3SnapshotAuditEvidence(
        selection_id=uuid5(_NAMESPACE, f"selection:{session_date}"),
        session_id=uuid5(_NAMESPACE, f"session:{session_date}"),
        attempt_id=uuid5(_NAMESPACE, f"attempt:{session_date}"),
        terminal_id=uuid5(_NAMESPACE, f"terminal:{session_date}"),
        snapshot_id=verification.snapshot.snapshot_id,
        artifact_sha256=hashlib.sha256(payload).hexdigest(),
        artifact_byte_length=len(payload),
        artifact_identity_sha256="2" * 64,
        terminal_state="SUCCEEDED",
        provider_call_disposition="CONFIRMED",
        canonical_artifact_path=f"fixture/{verification.snapshot.snapshot_id}.json",
    )
    selected = SelectedC3SnapshotReadResult(
        audit,
        object.__new__(SelectedC3SnapshotPermit),
        payload,
        verification,
    )
    capture_request = personal_desktop_unattended_capture_request(session)
    return SessionIndexedSelectedC3SnapshotReadResult(
        session,
        capture_request,
        capture_request.canonical_c2_request_json(),
        selected,
    )


def _required_dates() -> tuple[date, ...]:
    return (
        date(2026, 9, 8),
        date(2026, 9, 9),
        date(2026, 9, 10),
        date(2026, 9, 11),
        date(2026, 9, 14),
        date(2026, 9, 15),
    )


def _window(
    classification: SelectedC3StrategyHistoryWindowClassification,
    selected_dates: tuple[date, ...],
) -> SelectedC3StrategyHistoryWindowResult:
    selected = tuple(
        _session_read(session_date, price=Decimal(700 + index))
        for index, session_date in enumerate(selected_dates, start=1)
    )
    return SelectedC3StrategyHistoryWindowResult(
        classification=classification,
        required_sessions=tuple(TradingSession(value) for value in _required_dates()),
        selected=selected,
    )


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


def test_adapt_warming_up_history_uses_verified_selected_c3_close_and_ids() -> None:
    window = _window(
        SelectedC3StrategyHistoryWindowClassification.WARMING_UP,
        (date(2026, 9, 11), date(2026, 9, 14), date(2026, 9, 15)),
    )

    view = adapt_selected_c3_history_window(window)

    assert view.classification is OperatorWarmupClassification.WARMING_UP
    assert view.selected_count == 3
    assert tuple(item.session_date for item in view.selected_sessions) == (
        date(2026, 9, 11),
        date(2026, 9, 14),
        date(2026, 9, 15),
    )
    assert tuple(item.symbol for item in view.selected_sessions) == ("SPY",) * 3
    assert tuple(item.close for item in view.selected_sessions) == (
        Decimal("701") + Decimal("1"),
        Decimal("702") + Decimal("1"),
        Decimal("703") + Decimal("1"),
    )
    assert tuple(item.snapshot_id for item in view.selected_sessions) == tuple(
        item.selected.audit.snapshot_id for item in window.selected
    )
    assert tuple(item.selection_id for item in view.selected_sessions) == tuple(
        item.selected.audit.selection_id for item in window.selected
    )


def test_adapt_ready_history_requires_and_exposes_exact_six_session_window() -> None:
    window = _window(
        SelectedC3StrategyHistoryWindowClassification.READY,
        _required_dates(),
    )

    view = adapt_selected_c3_history_window(window)

    assert view.classification is OperatorWarmupClassification.READY
    assert view.selected_count == 6
    assert view.missing_sessions == ()


def test_adapt_gate_state_preserves_exact_order_and_closed_status() -> None:
    view = adapt_effect_gate_state(_closed_gates())

    assert view.as_tuple() == (False,) * 8
    assert view.all_closed is True


def test_adapt_operator_state_combines_independent_verified_inputs() -> None:
    window = _window(
        SelectedC3StrategyHistoryWindowClassification.WARMING_UP,
        (date(2026, 9, 14), date(2026, 9, 15)),
    )

    state = adapt_operator_observability_state(window, _closed_gates())

    assert state.warmup.selected_count == 2
    assert state.gates.all_closed is True


def test_adapter_rejects_wrong_runtime_evidence_types() -> None:
    with pytest.raises(OperatorObservabilityAdapterError):
        adapt_selected_c3_history_window(object())  # type: ignore[arg-type]
    with pytest.raises(OperatorObservabilityAdapterError):
        adapt_effect_gate_state(object())  # type: ignore[arg-type]


def test_adapter_rejects_non_frozen_history_window_size() -> None:
    selected = _session_read(date(2026, 9, 15), price=Decimal("700"))
    window = SelectedC3StrategyHistoryWindowResult(
        classification=SelectedC3StrategyHistoryWindowClassification.WARMING_UP,
        required_sessions=(
            TradingSession(date(2026, 9, 9)),
            TradingSession(date(2026, 9, 10)),
            TradingSession(date(2026, 9, 11)),
            TradingSession(date(2026, 9, 14)),
            TradingSession(date(2026, 9, 15)),
        ),
        selected=(selected,),
    )

    with pytest.raises(OperatorObservabilityAdapterError, match="six-session"):
        adapt_selected_c3_history_window(window)
