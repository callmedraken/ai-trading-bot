"""Architecture-112 capture-only unattended warm-up boundary.

This module is the only D5 composition that temporarily opens the unattended
market-data gate. It never opens any companion gate and runs G6 only after all
eight gates have been restored to their closed state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification,
    PersonalDesktopUnattendedDailyCycleResult,
    run_personal_desktop_unattended_daily_cycle,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification,
    PersonalDesktopUnattendedMarketDataCaptureResult,
    run_personal_desktop_unattended_market_data_capture,
)

_Cycle = PersonalDesktopUnattendedDailyCycleClassification
_Capture = PersonalDesktopUnattendedMarketDataCaptureClassification


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedCaptureWarmupGateState:
    """Exact process-local state of the eight reviewed production gates."""

    market_data_capture: bool
    decision_publication: bool
    production: bool
    recovery: bool
    supervised_execution: bool
    receipt_recovery: bool
    unattended_execution: bool
    unattended_storage_provisioning: bool


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedCaptureWarmupResult:
    """Sanitized D5 evidence carrying no reusable provider authority."""

    classification: PersonalDesktopUnattendedDailyCycleClassification
    completed_session: TradingSession | None = None
    market_data_classification: (
        PersonalDesktopUnattendedMarketDataCaptureClassification | None
    ) = None
    cycle_classification: PersonalDesktopUnattendedDailyCycleClassification | None = None
    capture_performed: bool = False
    provider_attempt_may_have_occurred: bool = False
    real_effect_performed: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.classification)
            is not PersonalDesktopUnattendedDailyCycleClassification
            or (
                self.completed_session is not None
                and type(self.completed_session) is not TradingSession
            )
            or (
                self.market_data_classification is not None
                and type(self.market_data_classification)
                is not PersonalDesktopUnattendedMarketDataCaptureClassification
            )
            or (
                self.cycle_classification is not None
                and type(self.cycle_classification)
                is not PersonalDesktopUnattendedDailyCycleClassification
            )
            or any(
                type(value) is not bool
                for value in (
                    self.capture_performed,
                    self.provider_attempt_may_have_occurred,
                    self.real_effect_performed,
                )
            )
            or self.capture_performed
            and (
                not self.real_effect_performed
                or not self.provider_attempt_may_have_occurred
                or self.market_data_classification is not _Capture.CAPTURE_REQUIRED
            )
            or self.real_effect_performed and not self.provider_attempt_may_have_occurred
            or (
                self.cycle_classification is not None
                and self.classification is not self.cycle_classification
            )
        ):
            raise ValueError("capture warm-up result is invalid")


@dataclass(frozen=True, slots=True)
class DisposablePersonalDesktopUnattendedCaptureWarmupDependencies:
    """Explicit D5 seams for deterministic no-provider source tests."""

    gate_state: Callable[[], PersonalDesktopUnattendedCaptureWarmupGateState]
    set_market_data_gate: Callable[[bool], None]
    run_market_data: Callable[[], PersonalDesktopUnattendedMarketDataCaptureResult]
    run_daily_cycle: Callable[[], PersonalDesktopUnattendedDailyCycleResult]


def personal_desktop_unattended_capture_warmup_gate_state() -> (
    PersonalDesktopUnattendedCaptureWarmupGateState
):
    """Return the current process-local eight-gate state without mutation."""

    return PersonalDesktopUnattendedCaptureWarmupGateState(
        market_data_capture.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED,
        decision_publication.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        receipt_recovery.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        unattended_execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        storage_provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )


def run_personal_desktop_unattended_capture_warmup() -> (
    PersonalDesktopUnattendedCaptureWarmupResult
):
    """Run one source-owned capture-only wake with no caller semantic inputs."""

    return _run_capture_warmup(_production_dependencies())


def run_personal_desktop_unattended_capture_warmup_for_test(
    dependencies: DisposablePersonalDesktopUnattendedCaptureWarmupDependencies,
) -> PersonalDesktopUnattendedCaptureWarmupResult:
    """Exercise D5 through explicit disposable boundaries."""

    if (
        type(dependencies)
        is not DisposablePersonalDesktopUnattendedCaptureWarmupDependencies
    ):
        raise TypeError("capture warm-up dependencies are invalid")
    return _run_capture_warmup(dependencies)


def _production_dependencies() -> (
    DisposablePersonalDesktopUnattendedCaptureWarmupDependencies
):
    def set_market_data_gate(value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("market-data gate value must be bool")
        market_data_capture.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED = (
            value
        )

    return DisposablePersonalDesktopUnattendedCaptureWarmupDependencies(
        gate_state=personal_desktop_unattended_capture_warmup_gate_state,
        set_market_data_gate=set_market_data_gate,
        run_market_data=run_personal_desktop_unattended_market_data_capture,
        run_daily_cycle=run_personal_desktop_unattended_daily_cycle,
    )


def _run_capture_warmup(
    dependencies: DisposablePersonalDesktopUnattendedCaptureWarmupDependencies,
) -> PersonalDesktopUnattendedCaptureWarmupResult:
    try:
        initial = dependencies.gate_state()
    except BaseException:
        return _result(_Cycle.BLOCKED)
    if not _all_closed(initial):
        return _result(_Cycle.BLOCKED)

    market_data: PersonalDesktopUnattendedMarketDataCaptureResult | None = None
    provider_attempt_may_have_occurred = False
    admission_blocked = False
    g5_started = False
    close_failed = False
    try:
        dependencies.set_market_data_gate(True)
        try:
            opened = dependencies.gate_state()
        except BaseException:
            admission_blocked = True
        else:
            if not _capture_only_open(opened):
                admission_blocked = True
            else:
                g5_started = True
                try:
                    market_data = dependencies.run_market_data()
                except BaseException:
                    provider_attempt_may_have_occurred = True
    except BaseException:
        admission_blocked = True
    finally:
        try:
            dependencies.set_market_data_gate(False)
        except BaseException:
            close_failed = True

    try:
        final_gates = dependencies.gate_state()
    except BaseException:
        final_gates = None
    if close_failed or not _all_closed(final_gates):
        return _result(
            _Cycle.BLOCKED,
            provider_attempt_may_have_occurred=(
                provider_attempt_may_have_occurred or g5_started
            ),
        )
    if provider_attempt_may_have_occurred:
        return _result(
            _Cycle.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
            provider_attempt_may_have_occurred=True,
        )
    if admission_blocked or not g5_started:
        return _result(_Cycle.BLOCKED)
    if type(market_data) is not PersonalDesktopUnattendedMarketDataCaptureResult:
        return _result(_Cycle.BLOCKED)

    classification = market_data.classification
    if classification in {
        _Capture.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
        _Capture.SESSION_GAP,
        _Capture.BLOCKED,
    }:
        return _result(
            _map_market_data(classification),
            market_data=market_data,
            provider_attempt_may_have_occurred=(
                classification is _Capture.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
            ),
        )

    capture_performed = False
    real_effect_performed = False
    if classification is _Capture.NO_NEW_COMPLETED_SESSION:
        if market_data.invocation is not None:
            return _result(_Cycle.BLOCKED, market_data=market_data)
    elif classification is _Capture.CAPTURE_REQUIRED:
        invocation = market_data.invocation
        if invocation is None:
            return _result(_Cycle.BLOCKED, market_data=market_data)
        provider_may_have_occurred = invocation.provider_call_disposition != "NOT_STARTED"
        provider_confirmed = invocation.provider_call_disposition == "CONFIRMED"
        capture_performed = invocation.terminal_state == "SUCCEEDED" and provider_confirmed
        real_effect_performed = provider_confirmed
        if not capture_performed:
            return _result(
                _Cycle.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS,
                market_data=market_data,
                provider_attempt_may_have_occurred=provider_may_have_occurred,
                real_effect_performed=real_effect_performed,
            )
    else:
        return _result(_Cycle.BLOCKED, market_data=market_data)

    try:
        before_g6 = dependencies.gate_state()
    except BaseException:
        return _result(
            _Cycle.BLOCKED,
            market_data=market_data,
            capture_performed=capture_performed,
            provider_attempt_may_have_occurred=capture_performed,
            real_effect_performed=real_effect_performed,
        )
    if not _all_closed(before_g6):
        return _result(
            _Cycle.BLOCKED,
            market_data=market_data,
            capture_performed=capture_performed,
            provider_attempt_may_have_occurred=capture_performed,
            real_effect_performed=real_effect_performed,
        )

    try:
        cycle = dependencies.run_daily_cycle()
    except BaseException:
        return _result(
            _Cycle.BLOCKED,
            market_data=market_data,
            capture_performed=capture_performed,
            provider_attempt_may_have_occurred=capture_performed,
            real_effect_performed=real_effect_performed,
        )
    if (
        type(cycle) is not PersonalDesktopUnattendedDailyCycleResult
        or cycle.real_effect_performed is not False
        or cycle.completed_session != market_data.eligible_completed_session
    ):
        return _result(
            _Cycle.BLOCKED,
            market_data=market_data,
            capture_performed=capture_performed,
            provider_attempt_may_have_occurred=capture_performed,
            real_effect_performed=real_effect_performed,
        )

    return _result(
        cycle.classification,
        market_data=market_data,
        cycle=cycle,
        capture_performed=capture_performed,
        provider_attempt_may_have_occurred=capture_performed,
        real_effect_performed=real_effect_performed,
    )


def _all_closed(state: object) -> bool:
    return type(state) is PersonalDesktopUnattendedCaptureWarmupGateState and all(
        type(value) is bool and value is False
        for value in (
            state.market_data_capture,
            state.decision_publication,
            state.production,
            state.recovery,
            state.supervised_execution,
            state.receipt_recovery,
            state.unattended_execution,
            state.unattended_storage_provisioning,
        )
    )


def _capture_only_open(state: object) -> bool:
    return (
        type(state) is PersonalDesktopUnattendedCaptureWarmupGateState
        and state.market_data_capture is True
        and all(
            type(value) is bool and value is False
            for value in (
                state.decision_publication,
                state.production,
                state.recovery,
                state.supervised_execution,
                state.receipt_recovery,
                state.unattended_execution,
                state.unattended_storage_provisioning,
            )
        )
    )


def _map_market_data(
    classification: PersonalDesktopUnattendedMarketDataCaptureClassification,
) -> PersonalDesktopUnattendedDailyCycleClassification:
    mapping = {
        _Capture.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS: (
            _Cycle.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
        ),
        _Capture.SESSION_GAP: _Cycle.SESSION_GAP,
        _Capture.BLOCKED: _Cycle.BLOCKED,
    }
    return mapping.get(classification, _Cycle.BLOCKED)


def _result(
    classification: PersonalDesktopUnattendedDailyCycleClassification,
    *,
    market_data: PersonalDesktopUnattendedMarketDataCaptureResult | None = None,
    cycle: PersonalDesktopUnattendedDailyCycleResult | None = None,
    capture_performed: bool = False,
    provider_attempt_may_have_occurred: bool = False,
    real_effect_performed: bool = False,
) -> PersonalDesktopUnattendedCaptureWarmupResult:
    return PersonalDesktopUnattendedCaptureWarmupResult(
        classification,
        completed_session=(
            cycle.completed_session
            if cycle is not None
            else (
                market_data.eligible_completed_session
                if market_data is not None
                else None
            )
        ),
        market_data_classification=(
            market_data.classification if market_data is not None else None
        ),
        cycle_classification=(cycle.classification if cycle is not None else None),
        capture_performed=capture_performed,
        provider_attempt_may_have_occurred=provider_attempt_may_have_occurred,
        real_effect_performed=real_effect_performed,
    )
