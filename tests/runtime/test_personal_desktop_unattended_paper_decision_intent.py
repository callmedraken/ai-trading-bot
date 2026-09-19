"""Focused PD4-G4 canonical durable decision-intent tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import pytest
from tests.runtime.test_manual_paper_strategy_plan import _policies, _prior

import trading_bot.runtime.personal_desktop_unattended_c3_history as history_module
from trading_bot.domain import Symbol
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
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_intent as intent_module,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotAuditEvidence,
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadResult,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyDecisionRequest,
    build_manual_paper_strategy_decision,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
    SessionIndexedSelectedC3SnapshotReadResult,
    build_selected_c3_strategy_history_binding,
    personal_desktop_unattended_capture_request,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    xnys_regular_open,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PersonalDesktopUnattendedPaperDecisionIntentError,
    bind_personal_desktop_unattended_paper_decision_intent,
    create_personal_desktop_unattended_paper_decision_intent,
    parse_personal_desktop_unattended_paper_decision_intent,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_NAMESPACE = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
_NEW_YORK = ZoneInfo("America/New_York")
_CONFIG = MovingAverageCrossoverConfig(3, 5, Decimal("1"))
_HISTORY_DATES = (
    date(2026, 8, 17),
    date(2026, 8, 18),
    date(2026, 8, 19),
    date(2026, 8, 20),
    date(2026, 8, 21),
)
_CURRENT_DATE = date(2026, 8, 24)


def _calendar():
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _selected_result(
    session: TradingSession,
    *,
    price: Decimal,
    symbol: Symbol = PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
) -> SelectedC3SnapshotReadResult:
    next_session = NYSEMarketCalendar().next_session(
        datetime.combine(session.session_date, time(12), tzinfo=_NEW_YORK)
    )
    requested_at = datetime.combine(next_session.session_date, time(8), tzinfo=UTC)
    request = DailySnapshotCaptureRequest(
        uuid5(_NAMESPACE, f"request:{session.session_date}:{symbol}"),
        (symbol,),
        requested_at,
        XNYS_CALENDAR_DESCRIPTOR,
    )
    provider_request = build_daily_provider_request(
        request, ALPACA_DAILY_SNAPSHOT_DESCRIPTOR, _calendar()
    )
    source = f"fixture:{session.session_date}:{symbol}".encode()
    response = DailyProviderResponse(
        provider_request,
        (
            DailyBarCandidate(
                0,
                symbol,
                session,
                datetime.combine(session.session_date, time(20), tzinfo=UTC),
                price,
                price + Decimal("2"),
                price - Decimal("1"),
                price + Decimal("1"),
                1000,
            ),
        ),
        requested_at + timedelta(seconds=1),
        requested_at,
        f"fixture-{session.session_date}",
        SourcePayloadEvidence(
            hashlib.sha256(source).hexdigest(), len(source), "application/json"
        ),
        True,
    )
    accepted = accept_daily_provider_response(provider_request, response, _calendar())
    assert accepted.snapshot is not None
    payload = serialize_daily_snapshot(accepted.snapshot)
    verification = verify_daily_snapshot(payload, _calendar())
    assert verification.snapshot is not None
    audit = SelectedC3SnapshotAuditEvidence(
        uuid5(_NAMESPACE, f"selection:{session.session_date}"),
        uuid5(_NAMESPACE, f"session:{session.session_date}"),
        uuid5(_NAMESPACE, f"attempt:{session.session_date}"),
        uuid5(_NAMESPACE, f"terminal:{session.session_date}"),
        verification.snapshot.snapshot_id,
        verification.sha256,
        verification.byte_length,
        "1" * 64,
        "SUCCEEDED",
        "CONFIRMED",
        f"fixture/{verification.snapshot.snapshot_id}.json",
    )
    return SelectedC3SnapshotReadResult(
        audit, object.__new__(SelectedC3SnapshotPermit), payload, verification
    )


def _session_read(day: date, price: int) -> SessionIndexedSelectedC3SnapshotReadResult:
    session = TradingSession(day)
    request = personal_desktop_unattended_capture_request(session)
    return SessionIndexedSelectedC3SnapshotReadResult(
        session,
        request,
        request.canonical_c2_request_json(),
        _selected_result(session, price=Decimal(price)),
    )


def _decision_binding(
    monkeypatch: pytest.MonkeyPatch, *, caller_key: str = "g4-decision-1"
):
    history = tuple(
        _session_read(day, 100 + index) for index, day in enumerate(_HISTORY_DATES)
    )
    current = _session_read(_CURRENT_DATE, 105)
    authority = object()
    monkeypatch.setattr(
        history_module, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        history_module,
        "require_selected_c3_snapshot_matches_authority",
        lambda permit, audit, current_authority: None,
    )
    history_binding = build_selected_c3_strategy_history_binding(
        authority,
        history,
        current,
        _CONFIG,  # type: ignore[arg-type]
    )
    audit = current.selected.audit
    assertion = ManualPaperSelectedC3Assertion(
        audit.selection_id,
        audit.session_id,
        audit.terminal_id,
        audit.snapshot_id,
        audit.artifact_sha256,
        audit.artifact_byte_length,
    )
    predecessor = _prior()
    execution_session = TradingSession(date(2026, 8, 25))
    modeled_open = xnys_regular_open(execution_session)
    snapshot = current.selected.verification.snapshot
    assert snapshot is not None
    prepared = build_manual_paper_strategy_decision(
        ManualPaperStrategyDecisionRequest(
            current.selected.verification,
            "paper.account-g4",
            assertion,
            predecessor,
            history_binding.verified_seed,
            _CONFIG,
            caller_key,
            _policies(),
            snapshot.audit.captured_at,
            modeled_open,
            modeled_open,
            (),
        ),
        _calendar(),
    )
    monkeypatch.setattr(
        intent_module, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        intent_module,
        "require_selected_c3_strategy_history_binding",
        lambda value, current_authority: value,
    )
    decision = create_personal_desktop_unattended_paper_decision_intent(
        prepared,
        history_binding,
        authority,  # type: ignore[arg-type]
        expected_paper_account_id=prepared.paper_account_id,
        expected_predecessor_checkpoint_id=prepared.prior_checkpoint.checkpoint_id,
    )
    return bind_personal_desktop_unattended_paper_decision_intent(decision)


def test_decision_intent_is_deterministic_and_round_trips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _decision_binding(monkeypatch)
    second = _decision_binding(monkeypatch)

    assert first.decision.decision_id == second.decision.decision_id
    assert first.artifact_bytes == second.artifact_bytes
    assert (
        parse_personal_desktop_unattended_paper_decision_intent(
            first.artifact_bytes, _calendar()
        )
        == first.decision
    )
    assert (
        verify_personal_desktop_unattended_paper_decision_intent(
            first.artifact_bytes,
            _calendar(),
            expected_decision_id=first.decision.decision_id,
            expected_artifact_sha256=first.artifact_sha256,
            expected_artifact_byte_length=first.artifact_byte_length,
        )
        == first
    )


def test_meaningful_semantic_change_changes_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _decision_binding(monkeypatch, caller_key="g4-a")
    second = _decision_binding(monkeypatch, caller_key="g4-b")
    assert first.decision.decision_id != second.decision.decision_id
    assert first.artifact_bytes != second.artifact_bytes


def test_artifact_has_no_execution_open_or_publication_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    tree = json.loads(binding.artifact_bytes)
    text = binding.artifact_bytes.decode()
    assert "open_reference" not in text
    assert "open_price" not in text
    assert "observed_at" not in text
    assert (
        tree["prepared_decision"]["submitted_at"]
        == tree["prepared_decision"]["filled_at"]
    )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.replace(b'"schema":', b'"unknown":0,"schema":', 1),
        lambda payload: payload.replace(
            b'"schema":', b'"schema":"duplicate","schema":', 1
        ),
        lambda payload: payload[:-1],
        lambda payload: b"\xef\xbb\xbf" + payload,
        lambda payload: payload.replace(b'"paper.account-g4"', b'"paper.account-x"'),
    ],
)
def test_malformed_noncanonical_or_tampered_bytes_fail_closed(
    monkeypatch: pytest.MonkeyPatch, mutator
) -> None:
    binding = _decision_binding(monkeypatch)
    with pytest.raises(PersonalDesktopUnattendedPaperDecisionIntentError):
        verify_personal_desktop_unattended_paper_decision_intent(
            mutator(binding.artifact_bytes), _calendar()
        )


def test_modeled_timestamps_are_exact_public_g1_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = _decision_binding(monkeypatch).decision
    expected = xnys_regular_open(decision.intended_execution_session)
    assert decision.prepared_decision.submitted_at == expected
    assert decision.prepared_decision.filled_at == expected


def test_wrong_account_or_predecessor_binding_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    with pytest.raises(PersonalDesktopUnattendedPaperDecisionIntentError):
        replace(binding.decision, paper_account_id="paper.account-wrong")
    with pytest.raises(PersonalDesktopUnattendedPaperDecisionIntentError):
        replace(binding.decision, predecessor_checkpoint_id=UUID(int=1))


def test_selected_current_c3_or_history_substitution_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    different = _decision_binding(monkeypatch, caller_key="different")
    with pytest.raises(PersonalDesktopUnattendedPaperDecisionIntentError):
        replace(binding.decision, current_c3=different.decision.history_c3[0])
    with pytest.raises(PersonalDesktopUnattendedPaperDecisionIntentError):
        replace(
            binding.decision,
            history_c3=tuple(reversed(binding.decision.history_c3)),
        )
