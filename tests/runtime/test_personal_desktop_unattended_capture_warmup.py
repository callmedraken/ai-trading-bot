"""Focused Architecture-112 capture-only warm-up boundary coverage."""

from __future__ import annotations

import hashlib
import inspect
from datetime import date
from uuid import UUID

import pytest

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
    personal_desktop_unattended_paper_storage_provisioning as storage_provisioning,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    personal_desktop_unattended_capture_request,
)
from trading_bot.runtime.personal_desktop_unattended_capture_warmup import (
    DisposablePersonalDesktopUnattendedCaptureWarmupDependencies,
    PersonalDesktopUnattendedCaptureWarmupGateState,
    run_personal_desktop_unattended_capture_warmup,
    run_personal_desktop_unattended_capture_warmup_for_test,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification as CycleStatus,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleResult,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification as CaptureStatus,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureResult,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    ProductionCaptureInvocationResult,
)

_SESSION = TradingSession(date(2026, 9, 11))


def _closed() -> PersonalDesktopUnattendedCaptureWarmupGateState:
    return PersonalDesktopUnattendedCaptureWarmupGateState(*((False,) * 8))


def _request_result(
    classification: CaptureStatus,
    *,
    invocation: ProductionCaptureInvocationResult | None = None,
) -> PersonalDesktopUnattendedMarketDataCaptureResult:
    request = personal_desktop_unattended_capture_request(_SESSION)
    return PersonalDesktopUnattendedMarketDataCaptureResult(
        classification,
        _SESSION,
        request,
        hashlib.sha256(request.canonical_c2_request_json()).hexdigest(),
        invocation=invocation,
    )


def _invocation(
    *,
    terminal_state: str = "SUCCEEDED",
    provider_call_disposition: str = "CONFIRMED",
) -> ProductionCaptureInvocationResult:
    success = terminal_state == "SUCCEEDED"
    return ProductionCaptureInvocationResult(
        session_id="11111111-1111-4111-8111-111111111111",
        attempt_id="22222222-2222-4222-8222-222222222222",
        claim_id="33333333-3333-4333-8333-333333333333",
        reservation_id="44444444-4444-4444-8444-444444444444",
        execution_id=(
            "55555555-5555-4555-8555-555555555555"
            if provider_call_disposition != "NOT_STARTED"
            else None
        ),
        terminal_id="66666666-6666-4666-8666-666666666666",
        selection_id=(
            "77777777-7777-4777-8777-777777777777" if success else None
        ),
        terminal_state=terminal_state,
        provider_call_disposition=provider_call_disposition,
        snapshot_id=(
            UUID("88888888-8888-4888-8888-888888888888") if success else None
        ),
        artifact_sha256=("a" * 64 if success else None),
        artifact_byte_length=(1289 if success else None),
    )


def _cycle(classification: CycleStatus) -> PersonalDesktopUnattendedDailyCycleResult:
    return PersonalDesktopUnattendedDailyCycleResult(
        classification,
        completed_session=_SESSION,
        market_data_classification=CaptureStatus.NO_NEW_COMPLETED_SESSION,
    )


def _dependencies(
    *,
    market_data: PersonalDesktopUnattendedMarketDataCaptureResult | None = None,
    cycle: PersonalDesktopUnattendedDailyCycleResult | None = None,
    market_error: BaseException | None = None,
    initial: PersonalDesktopUnattendedCaptureWarmupGateState | None = None,
    calls: list[str] | None = None,
) -> DisposablePersonalDesktopUnattendedCaptureWarmupDependencies:
    calls = [] if calls is None else calls
    state = {"value": _closed() if initial is None else initial}

    def gate_state() -> PersonalDesktopUnattendedCaptureWarmupGateState:
        return state["value"]

    def set_gate(value: bool) -> None:
        calls.append(f"gate:{value}")
        current = state["value"]
        state["value"] = PersonalDesktopUnattendedCaptureWarmupGateState(
            value,
            current.decision_publication,
            current.production,
            current.recovery,
            current.supervised_execution,
            current.receipt_recovery,
            current.unattended_execution,
            current.unattended_storage_provisioning,
        )

    def run_market_data() -> PersonalDesktopUnattendedMarketDataCaptureResult:
        calls.append("g5")
        opened = state["value"]
        assert opened.market_data_capture is True
        assert all(
            value is False
            for value in (
                opened.decision_publication,
                opened.production,
                opened.recovery,
                opened.supervised_execution,
                opened.receipt_recovery,
                opened.unattended_execution,
                opened.unattended_storage_provisioning,
            )
        )
        if market_error is not None:
            raise market_error
        assert market_data is not None
        return market_data

    def run_daily_cycle() -> PersonalDesktopUnattendedDailyCycleResult:
        calls.append("g6")
        assert state["value"] == _closed()
        assert cycle is not None
        return cycle

    return DisposablePersonalDesktopUnattendedCaptureWarmupDependencies(
        gate_state,
        set_gate,
        run_market_data,
        run_daily_cycle,
    )


def test_production_api_accepts_no_semantic_arguments() -> None:
    assert (
        tuple(inspect.signature(run_personal_desktop_unattended_capture_warmup).parameters)
        == ()
    )


@pytest.mark.parametrize(
    "initial",
    (
        PersonalDesktopUnattendedCaptureWarmupGateState(
            True, False, False, False, False, False, False, False
        ),
        PersonalDesktopUnattendedCaptureWarmupGateState(
            False, True, False, False, False, False, False, False
        ),
        PersonalDesktopUnattendedCaptureWarmupGateState(
            False, False, True, False, False, False, False, False
        ),
        PersonalDesktopUnattendedCaptureWarmupGateState(
            False, False, False, False, False, False, False, True
        ),
    ),
)
def test_any_initially_open_gate_blocks_before_g5(
    initial: PersonalDesktopUnattendedCaptureWarmupGateState,
) -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_capture_warmup_for_test(
        _dependencies(initial=initial, calls=calls)
    )
    assert result.classification is CycleStatus.BLOCKED
    assert calls == []
    assert result.real_effect_performed is False


def test_no_new_completed_session_calls_g5_once_then_g6_all_closed() -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_capture_warmup_for_test(
        _dependencies(
            market_data=_request_result(CaptureStatus.NO_NEW_COMPLETED_SESSION),
            cycle=_cycle(CycleStatus.WARMING_UP),
            calls=calls,
        )
    )
    assert calls == ["gate:True", "g5", "gate:False", "g6"]
    assert result.classification is CycleStatus.WARMING_UP
    assert result.market_data_classification is CaptureStatus.NO_NEW_COMPLETED_SESSION
    assert result.capture_performed is False
    assert result.provider_attempt_may_have_occurred is False
    assert result.real_effect_performed is False


def test_successful_capture_calls_g5_once_then_g6_all_closed() -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_capture_warmup_for_test(
        _dependencies(
            market_data=_request_result(
                CaptureStatus.CAPTURE_REQUIRED,
                invocation=_invocation(),
            ),
            cycle=_cycle(CycleStatus.WARMING_UP),
            calls=calls,
        )
    )
    assert calls == ["gate:True", "g5", "gate:False", "g6"]
    assert result.classification is CycleStatus.WARMING_UP
    assert result.capture_performed is True
    assert result.provider_attempt_may_have_occurred is True
    assert result.real_effect_performed is True


def test_history_ready_handoff_is_decision_ready_without_publication_effect() -> None:
    result = run_personal_desktop_unattended_capture_warmup_for_test(
        _dependencies(
            market_data=_request_result(CaptureStatus.NO_NEW_COMPLETED_SESSION),
            cycle=_cycle(CycleStatus.DECISION_READY),
        )
    )
    assert result.classification is CycleStatus.DECISION_READY
    assert result.cycle_classification is CycleStatus.DECISION_READY
    assert result.real_effect_performed is False


def test_g5_exception_is_ambiguous_and_never_retried_or_sent_to_g6() -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_capture_warmup_for_test(
        _dependencies(
            market_error=RuntimeError("uncertain provider state"),
            calls=calls,
        )
    )
    assert calls == ["gate:True", "g5", "gate:False"]
    assert result.classification is CycleStatus.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
    assert result.provider_attempt_may_have_occurred is True
    assert result.capture_performed is False
    assert result.real_effect_performed is False


@pytest.mark.parametrize(
    ("capture_status", "cycle_status"),
    (
        (CaptureStatus.SESSION_GAP, CycleStatus.SESSION_GAP),
        (
            CaptureStatus.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
            CycleStatus.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
        ),
        (CaptureStatus.BLOCKED, CycleStatus.BLOCKED),
    ),
)
def test_unsafe_g5_classification_stops_before_g6(
    capture_status: CaptureStatus,
    cycle_status: CycleStatus,
) -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_capture_warmup_for_test(
        _dependencies(market_data=_request_result(capture_status), calls=calls)
    )
    assert calls == ["gate:True", "g5", "gate:False"]
    assert result.classification is cycle_status
    assert "g6" not in calls


def test_failed_confirmed_provider_invocation_is_consumed_not_retried() -> None:
    calls: list[str] = []
    result = run_personal_desktop_unattended_capture_warmup_for_test(
        _dependencies(
            market_data=_request_result(
                CaptureStatus.CAPTURE_REQUIRED,
                invocation=_invocation(
                    terminal_state="FAILED",
                    provider_call_disposition="CONFIRMED",
                ),
            ),
            calls=calls,
        )
    )
    assert calls == ["gate:True", "g5", "gate:False"]
    assert result.classification is CycleStatus.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
    assert result.capture_performed is False
    assert result.provider_attempt_may_have_occurred is True
    assert result.real_effect_performed is True


def test_g6_exception_occurs_only_after_gate_is_closed_and_is_blocked() -> None:
    calls: list[str] = []
    dependencies = _dependencies(
        market_data=_request_result(CaptureStatus.NO_NEW_COMPLETED_SESSION),
        cycle=_cycle(CycleStatus.WARMING_UP),
        calls=calls,
    )

    def fail_g6() -> PersonalDesktopUnattendedDailyCycleResult:
        calls.append("g6")
        raise RuntimeError("read-only reconciliation failed")

    dependencies = DisposablePersonalDesktopUnattendedCaptureWarmupDependencies(
        dependencies.gate_state,
        dependencies.set_market_data_gate,
        dependencies.run_market_data,
        fail_g6,
    )
    result = run_personal_desktop_unattended_capture_warmup_for_test(dependencies)
    assert calls == ["gate:True", "g5", "gate:False", "g6"]
    assert result.classification is CycleStatus.BLOCKED
    assert result.real_effect_performed is False


def test_all_production_gate_constants_remain_committed_false() -> None:
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
