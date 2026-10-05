"""Architecture-122 bounded one-wake D10 simulated-paper composition."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import (
    personal_desktop_paper_account_security as account,
)
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as recovery,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised,
)
from trading_bot.runtime import (
    personal_desktop_unattended_market_data_capture as c3,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_publication as decision_gate,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as paper_exec,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_storage_provisioning as provisioning,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_PRODUCTION_PYTHON,
)
from trading_bot.runtime.personal_desktop_d10_deployment_verifier import (
    ActivationLeaseVerificationBlocked,
    DeploymentVerificationBlocked,
    VerifiedD10ActivationLease,
    VerifiedD10Deployment,
    require_verified_d10_activation_lease,
    require_verified_d10_deployment,
    verify_d10_activation_lease,
    verify_d10_deployment,
)
from trading_bot.runtime.personal_desktop_d10_python_substrate import (
    VERSION as D10_PYTHON_VERSION,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification as Cycle,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleResult,
    personal_desktop_unattended_effect_gate_state,
    run_personal_desktop_unattended_daily_cycle,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    next_xnys_execution_session,
    xnys_regular_open,
)
from trading_bot.runtime.personal_desktop_unattended_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationClassification as Publication,
)
from trading_bot.runtime.personal_desktop_unattended_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationResult,
    run_personal_desktop_unattended_decision_publication,
)
from trading_bot.runtime.personal_desktop_unattended_decision_reconciliation import (
    UnattendedDecisionReconciliationClassification as DecisionRecon,
)
from trading_bot.runtime.personal_desktop_unattended_decision_reconciliation import (
    UnattendedDecisionReconciliationResult,
    reconcile_personal_desktop_unattended_decision,
)
from trading_bot.runtime.personal_desktop_unattended_historical_settlement_audit import (  # noqa: E501
    HistoricalSettlementAuditClassification as HistoricalAudit,
)
from trading_bot.runtime.personal_desktop_unattended_historical_settlement_audit import (  # noqa: E501
    HistoricalSettlementAuditResult,
    audit_personal_desktop_historical_settlements,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification as Capture,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureResult,
    run_personal_desktop_unattended_market_data_capture,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract import (  # noqa: E501
    D10_SCHEDULER_CONTRACT,
    D10_SCHEDULER_CONTRACT_SCHEMA,
    is_frozen_one_week_soak_scheduler_contract,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak_window import (
    OneWeekSoakState,
    build_one_week_soak_window,
)
from trading_bot.runtime.personal_desktop_unattended_settlement_execution import (
    SettlementExecutionClassification as Settlement,
)
from trading_bot.runtime.personal_desktop_unattended_settlement_execution import (
    SettlementExecutionResult,
    execute_personal_desktop_unattended_settlement,
)
from trading_bot.runtime.personal_desktop_unattended_settlement_reconciliation import (
    SettlementReconciliationClassification as SettlementRecon,
)
from trading_bot.runtime.personal_desktop_unattended_settlement_reconciliation import (
    SettlementReconciliationResult,
    reconcile_personal_desktop_unattended_settlement,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)

D10_WAKE_EVIDENCE_SCHEMA = "personal-desktop-d10-wake-evidence/v1"
D10_WAKE_SUMMARY_SCHEMA = "personal-desktop-d10-wake-summary/v1"
MAX_D10_WAKE_EVIDENCE_BYTES = 16_384
MAX_D10_SUMMARY_WAKES = 512
_CLOSED = (False,) * 8
_CAPTURE_OPEN = (True, False, False, False, False, False, False, False)


class D10WakeOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    NO_ACTION = "NO_ACTION"
    STOPPED = "STOPPED"


class D10WakeStopReason(StrEnum):
    BLOCKED = "BLOCKED"
    SESSION_GAP = "SESSION_GAP"
    MISSED_DECISION_DEADLINE = "MISSED_DECISION_DEADLINE"
    STALE_UNRESOLVED_DECISION = "STALE_UNRESOLVED_DECISION"
    PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS = "PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    AUTHORITY_DRIFT = "AUTHORITY_DRIFT"
    DEPLOYMENT_IDENTITY_DRIFT = "DEPLOYMENT_IDENTITY_DRIFT"
    LEASE_NOT_ACTIVE_OR_EXPIRED = "LEASE_NOT_ACTIVE_OR_EXPIRED"
    EFFECT_GATE_DRIFT = "EFFECT_GATE_DRIFT"
    AMBIGUOUS_EFFECT_RESULT = "AMBIGUOUS_EFFECT_RESULT"


@dataclass(frozen=True, slots=True)
class D10OneWeekWakeEvidence:
    """Bounded sanitized per-wake facts; contains no authority or capability."""

    outcome: D10WakeOutcome
    stop_reason: D10WakeStopReason | None
    observed_at_utc: datetime
    deployment_id: str | None = None
    attestation_sha256: str | None = None
    certified_source_head: str | None = None
    certified_source_tree: str | None = None
    executable_file_count: int | None = None
    soak_id: str | None = None
    activation_utc: datetime | None = None
    end_utc: datetime | None = None
    completed_session: str | None = None
    next_execution_session: str | None = None
    preopen_deadline_utc: datetime | None = None
    capture_classification: str | None = None
    capture_selection_id: str | None = None
    capture_snapshot_id: str | None = None
    provider_attempt_id: str | None = None
    provider_terminal_state: str | None = None
    provider_call_disposition: str | None = None
    historical_audit_classification: str | None = None
    historical_reconciled_count: int = 0
    historical_current_decision_id: str | None = None
    historical_unresolved_decision_id: str | None = None
    settlement_decision_id: str | None = None
    settlement_classification: str | None = None
    settlement_reconciliation: str | None = None
    final_plan_id: str | None = None
    invocation_id: str | None = None
    operation_id: str | None = None
    application_id: str | None = None
    predecessor_checkpoint_id: str | None = None
    successor_checkpoint_id: str | None = None
    next_decision_id: str | None = None
    publication_classification: str | None = None
    decision_reconciliation: str | None = None
    finalized_decision_id: str | None = None
    provider_attempts: int = 0
    settlement_attempts: int = 0
    publication_attempts: int = 0
    receipt_recovery_attempts: int = 0
    broker_live_calls: int = 0
    provider_effect_crossed: bool = False
    settlement_effect_crossed: bool = False
    publication_effect_crossed: bool = False
    all_effect_gates_closed: bool = True
    closed_effect_gate_count: int = 8

    def __post_init__(self) -> None:
        optional_strings = (
            self.deployment_id,
            self.attestation_sha256,
            self.certified_source_head,
            self.certified_source_tree,
            self.soak_id,
            self.completed_session,
            self.next_execution_session,
            self.capture_classification,
            self.capture_selection_id,
            self.capture_snapshot_id,
            self.provider_attempt_id,
            self.provider_terminal_state,
            self.provider_call_disposition,
            self.historical_audit_classification,
            self.historical_current_decision_id,
            self.historical_unresolved_decision_id,
            self.settlement_decision_id,
            self.settlement_classification,
            self.settlement_reconciliation,
            self.final_plan_id,
            self.invocation_id,
            self.operation_id,
            self.application_id,
            self.predecessor_checkpoint_id,
            self.successor_checkpoint_id,
            self.next_decision_id,
            self.publication_classification,
            self.decision_reconciliation,
            self.finalized_decision_id,
        )
        counts = (
            self.provider_attempts,
            self.settlement_attempts,
            self.publication_attempts,
            self.receipt_recovery_attempts,
            self.broker_live_calls,
            self.historical_reconciled_count,
            self.closed_effect_gate_count,
        )
        if (
            type(self.outcome) is not D10WakeOutcome
            or (
                self.stop_reason is not None
                and type(self.stop_reason) is not D10WakeStopReason
            )
            or (self.outcome is D10WakeOutcome.STOPPED)
            != (self.stop_reason is not None)
            or not _is_utc(self.observed_at_utc)
            or any(v is not None and type(v) is not str for v in optional_strings)
            or any(
                v is not None and not _is_utc(v)
                for v in (self.activation_utc, self.end_utc, self.preopen_deadline_utc)
            )
            or (self.activation_utc is None) != (self.end_utc is None)
            or any(type(v) is not int or v < 0 for v in counts)
            or self.provider_attempts > 1
            or self.settlement_attempts > 1
            or self.publication_attempts > 1
            or self.receipt_recovery_attempts != 0
            or self.broker_live_calls != 0
            or type(self.provider_effect_crossed) is not bool
            or type(self.settlement_effect_crossed) is not bool
            or type(self.publication_effect_crossed) is not bool
            or self.all_effect_gates_closed is not True
            or self.closed_effect_gate_count != 8
            or (self.provider_effect_crossed and self.provider_attempts != 1)
            or (self.settlement_effect_crossed and self.settlement_attempts != 1)
            or (self.publication_effect_crossed and self.publication_attempts != 1)
        ):
            raise ValueError("D10 wake evidence is invalid")


@dataclass(frozen=True, slots=True)
class D10OneWeekWakeSummary:
    """Pure cumulative view over a bounded sequence of sanitized wake records."""

    soak_id: str
    deployment_id: str
    wake_count: int
    completed_count: int
    no_action_count: int
    stopped_count: int
    provider_attempts: int
    settlement_attempts: int
    publication_attempts: int
    stop_counts: tuple[tuple[str, int], ...]
    first_observed_at_utc: datetime
    last_observed_at_utc: datetime
    all_effect_gates_closed: bool


@dataclass(frozen=True, slots=True)
class DisposableD10OneWeekSoakDependencies:
    """Disposable controller seams; production never accepts this object."""

    now: Callable[[], datetime]
    validate_admission: Callable[[object, object], None]
    revalidate_before_effect: Callable[[object, object], None]
    gate_state: Callable[[], tuple[bool, ...]]
    set_market_data_gate: Callable[[bool], None]
    close_all_gates: Callable[[], None]
    capture: Callable[[], PersonalDesktopUnattendedMarketDataCaptureResult]
    daily_cycle: Callable[[], PersonalDesktopUnattendedDailyCycleResult]
    historical_audit: Callable[[], HistoricalSettlementAuditResult]
    settle: Callable[[], SettlementExecutionResult]
    reconcile_settlement: Callable[[], SettlementReconciliationResult]
    publish_decision: Callable[[], PersonalDesktopUnattendedDecisionPublicationResult]
    reconcile_decision: Callable[[], UnattendedDecisionReconciliationResult]


class _StopWake(Exception):
    def __init__(self, reason: D10WakeStopReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class D10GateClosureFailure(RuntimeError):
    """The controller could not prove every effect gate was closed at exit."""


@dataclass(slots=True)
class _Facts:
    observed_at_utc: datetime
    deployment_id: str | None = None
    attestation_sha256: str | None = None
    certified_source_head: str | None = None
    certified_source_tree: str | None = None
    executable_file_count: int | None = None
    soak_id: str | None = None
    activation_utc: datetime | None = None
    end_utc: datetime | None = None
    completed_session: str | None = None
    next_execution_session: str | None = None
    preopen_deadline_utc: datetime | None = None
    capture_classification: str | None = None
    capture_selection_id: str | None = None
    capture_snapshot_id: str | None = None
    provider_attempt_id: str | None = None
    provider_terminal_state: str | None = None
    provider_call_disposition: str | None = None
    historical_audit_classification: str | None = None
    historical_reconciled_count: int = 0
    historical_current_decision_id: str | None = None
    historical_unresolved_decision_id: str | None = None
    settlement_decision_id: str | None = None
    settlement_classification: str | None = None
    settlement_reconciliation: str | None = None
    final_plan_id: str | None = None
    invocation_id: str | None = None
    operation_id: str | None = None
    application_id: str | None = None
    predecessor_checkpoint_id: str | None = None
    successor_checkpoint_id: str | None = None
    next_decision_id: str | None = None
    publication_classification: str | None = None
    decision_reconciliation: str | None = None
    finalized_decision_id: str | None = None
    provider_attempts: int = 0
    settlement_attempts: int = 0
    publication_attempts: int = 0
    provider_effect_crossed: bool = False
    settlement_effect_crossed: bool = False
    publication_effect_crossed: bool = False


def run_personal_desktop_unattended_one_week_soak(
    deployment: VerifiedD10Deployment,
    lease: VerifiedD10ActivationLease,
) -> D10OneWeekWakeEvidence:
    """Run one wake with genuine same-process Architecture-123/124 provenance."""

    return _run_one_wake(deployment, lease, _production_dependencies())


def run_personal_desktop_unattended_one_week_soak_for_test(
    deployment: object,
    lease: object,
    dependencies: DisposableD10OneWeekSoakDependencies,
) -> D10OneWeekWakeEvidence:
    """Exercise ordering through disposable test boundaries."""

    if type(dependencies) is not DisposableD10OneWeekSoakDependencies:
        raise TypeError("disposable D10 dependencies are invalid")
    return _run_one_wake(deployment, lease, dependencies)


def _run_one_wake(
    deployment: object,
    lease: object,
    dependencies: DisposableD10OneWeekSoakDependencies,
) -> D10OneWeekWakeEvidence:
    facts = _Facts(datetime.now(UTC))
    outcome = D10WakeOutcome.STOPPED
    stop_reason: D10WakeStopReason | None = D10WakeStopReason.BLOCKED
    try:
        facts.observed_at_utc = _read_utc(dependencies.now)
        _require_gates_closed(dependencies)
        try:
            dependencies.validate_admission(deployment, lease)
            _copy_provenance(facts, deployment, lease)
            if facts.activation_utc is None:
                raise _StopWake(D10WakeStopReason.BLOCKED)
            window = build_one_week_soak_window(facts.activation_utc)
        except _StopWake:
            raise
        except DeploymentVerificationBlocked as exc:
            raise _StopWake(D10WakeStopReason.DEPLOYMENT_IDENTITY_DRIFT) from exc
        except ActivationLeaseVerificationBlocked as exc:
            raise _StopWake(D10WakeStopReason.LEASE_NOT_ACTIVE_OR_EXPIRED) from exc
        except Exception as exc:
            raise _StopWake(D10WakeStopReason.BLOCKED) from exc
        if (
            window.end_utc != facts.end_utc
            or window.state_at(facts.observed_at_utc) is not OneWeekSoakState.ACTIVE
        ):
            raise _StopWake(D10WakeStopReason.LEASE_NOT_ACTIVE_OR_EXPIRED)

        capture = _capture_once_if_required(dependencies, facts, deployment, lease)
        if capture is not None:
            facts.capture_classification = capture.classification.value
            _copy_capture(facts, capture)
            if capture.classification is Capture.SESSION_GAP:
                raise _StopWake(D10WakeStopReason.SESSION_GAP)
            if capture.classification is Capture.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS:
                raise _StopWake(
                    D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
                )
            if capture.classification is Capture.BLOCKED:
                raise _StopWake(D10WakeStopReason.BLOCKED)
            if capture.classification is Capture.CAPTURE_REQUIRED:
                raise _StopWake(
                    D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
                )

        first_cycle = _read_cycle(dependencies, facts)
        reason = _cycle_stop_reason(first_cycle.classification)
        if reason is not None:
            raise _StopWake(reason)
        _audit_history(dependencies, facts, first_cycle.completed_session)

        if first_cycle.classification in {Cycle.EXECUTION_READY, Cycle.ALREADY_APPLIED}:
            _reconcile_current_settlement(
                dependencies,
                facts,
                first_cycle,
                deployment,
                lease,
                attempt=first_cycle.classification is Cycle.EXECUTION_READY,
            )

        # Reconstruct next-decision truth from durable state after settlement.
        second_cycle = _read_cycle(dependencies, facts)
        reason = _cycle_stop_reason(second_cycle.classification)
        if reason is not None:
            raise _StopWake(reason)
        if second_cycle.completed_session != first_cycle.completed_session:
            raise _StopWake(D10WakeStopReason.BLOCKED)
        facts.next_decision_id = _uuid_text(second_cycle.next_decision_id)
        if second_cycle.completed_session is not None:
            execution_session = next_xnys_execution_session(
                second_cycle.completed_session
            )
            facts.next_execution_session = execution_session.session_date.isoformat()
            facts.preopen_deadline_utc = xnys_regular_open(execution_session)

        # Reprove older finalized decisions before any publication effect.
        _audit_history(dependencies, facts, second_cycle.completed_session)
        _publish_or_reconcile_decision(
            dependencies, facts, second_cycle, deployment, lease
        )
        outcome = (
            D10WakeOutcome.NO_ACTION
            if facts.provider_attempts == 0
            and facts.settlement_attempts == 0
            and facts.publication_attempts == 0
            else D10WakeOutcome.COMPLETED
        )
        stop_reason = None
    except _StopWake as stop:
        stop_reason = stop.reason
    except BaseException:
        stop_reason = D10WakeStopReason.BLOCKED
    finally:
        try:
            dependencies.close_all_gates()
        except BaseException as exc:
            raise D10GateClosureFailure(
                "D10 could not restore all effect gates closed"
            ) from exc
        if not _gates_are_closed(dependencies.gate_state()):
            raise D10GateClosureFailure(
                "D10 final effect-gate closure could not be proven"
            )

    if stop_reason is not None:
        outcome = D10WakeOutcome.STOPPED
    return _build_evidence(facts, outcome, stop_reason)


def _capture_once_if_required(
    dependencies: DisposableD10OneWeekSoakDependencies,
    facts: _Facts,
    deployment: object,
    lease: object,
) -> PersonalDesktopUnattendedMarketDataCaptureResult | None:
    _require_gates_closed(dependencies)
    try:
        preflight = dependencies.capture()
    except BaseException as exc:
        raise _StopWake(D10WakeStopReason.BLOCKED) from exc
    _require_capture_result(preflight)
    if preflight.classification is not Capture.CAPTURE_REQUIRED:
        return preflight

    _validate_before_effect(dependencies, deployment, lease)
    try:
        dependencies.set_market_data_gate(True)
        _require_gate_state(dependencies, _CAPTURE_OPEN)
        facts.provider_attempts = 1
        facts.provider_effect_crossed = True
        captured = dependencies.capture()
    except _StopWake:
        raise
    except BaseException as exc:
        reason = (
            D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
            if facts.provider_attempts
            else D10WakeStopReason.EFFECT_GATE_DRIFT
        )
        raise _StopWake(reason) from exc
    finally:
        dependencies.set_market_data_gate(False)
    _require_gates_closed(dependencies)
    _require_capture_result(captured)
    if captured.invocation is not None:
        invocation = captured.invocation
        facts.provider_attempt_id = invocation.attempt_id
        facts.provider_terminal_state = invocation.terminal_state
        facts.provider_call_disposition = invocation.provider_call_disposition
        if (
            invocation.terminal_state != "SUCCEEDED"
            or invocation.provider_call_disposition != "CONFIRMED"
        ):
            raise _StopWake(D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS)
    elif captured.classification is Capture.NO_NEW_COMPLETED_SESSION:
        facts.provider_attempts = 0
        facts.provider_effect_crossed = False
    else:
        raise _StopWake(D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS)

    # Only a fresh closed-gate read, not the invocation result, can continue.
    try:
        current = dependencies.capture()
    except BaseException as exc:
        raise _StopWake(D10WakeStopReason.BLOCKED) from exc
    _require_capture_result(current)
    _require_gates_closed(dependencies)
    return current


def _read_cycle(
    dependencies: DisposableD10OneWeekSoakDependencies,
    facts: _Facts,
) -> PersonalDesktopUnattendedDailyCycleResult:
    _require_gates_closed(dependencies)
    try:
        result = dependencies.daily_cycle()
    except BaseException as exc:
        raise _StopWake(D10WakeStopReason.BLOCKED) from exc
    if type(result) is not PersonalDesktopUnattendedDailyCycleResult:
        raise _StopWake(D10WakeStopReason.BLOCKED)
    _require_gates_closed(dependencies)
    if result.completed_session is not None:
        current = result.completed_session.session_date.isoformat()
        if facts.completed_session is not None and facts.completed_session != current:
            raise _StopWake(D10WakeStopReason.BLOCKED)
        facts.completed_session = current
        execution_session = next_xnys_execution_session(result.completed_session)
        facts.next_execution_session = execution_session.session_date.isoformat()
        facts.preopen_deadline_utc = xnys_regular_open(execution_session)
    if result.next_decision_id is not None:
        facts.next_decision_id = str(result.next_decision_id)
    return result


def _audit_history(
    dependencies: DisposableD10OneWeekSoakDependencies,
    facts: _Facts,
    expected_session: TradingSession | None,
) -> HistoricalSettlementAuditResult:
    _require_gates_closed(dependencies)
    try:
        result = dependencies.historical_audit()
    except BaseException as exc:
        raise _StopWake(D10WakeStopReason.BLOCKED) from exc
    _require_gates_closed(dependencies)
    if type(result) is not HistoricalSettlementAuditResult:
        raise _StopWake(D10WakeStopReason.BLOCKED)
    facts.historical_audit_classification = result.classification.value
    facts.historical_reconciled_count = len(result.reconciled_decision_ids)
    facts.historical_current_decision_id = _uuid_text(result.current_decision_id)
    facts.historical_unresolved_decision_id = _uuid_text(result.unresolved_decision_id)
    if result.classification is HistoricalAudit.STALE_UNRESOLVED_DECISION:
        raise _StopWake(D10WakeStopReason.STALE_UNRESOLVED_DECISION)
    if (
        result.classification is not HistoricalAudit.RECONCILED_HISTORY
        or not result.all_eight_gates_closed
        or result.completed_session != expected_session
    ):
        raise _StopWake(D10WakeStopReason.BLOCKED)
    return result


def _reconcile_current_settlement(
    dependencies: DisposableD10OneWeekSoakDependencies,
    facts: _Facts,
    cycle: PersonalDesktopUnattendedDailyCycleResult,
    deployment: object,
    lease: object,
    *,
    attempt: bool,
) -> None:
    if cycle.pending_decision_id is None or cycle.completed_session is None:
        raise _StopWake(D10WakeStopReason.BLOCKED)
    facts.settlement_decision_id = str(cycle.pending_decision_id)
    if not attempt:
        facts.settlement_classification = "ALREADY_APPLIED"
    effect: SettlementExecutionResult | None = None
    effect_error = False
    if attempt:
        _validate_before_effect(dependencies, deployment, lease)
        facts.settlement_attempts = 1
        try:
            effect = dependencies.settle()
            if type(effect) is not SettlementExecutionResult:
                effect_error = True
            else:
                facts.settlement_classification = effect.classification.value
                facts.settlement_effect_crossed = effect.real_effect_performed
                effect_error = (
                    not effect.all_eight_gates_closed
                    or effect.completed_execution_session != cycle.completed_session
                    or effect.decision_id != cycle.pending_decision_id
                )
        except BaseException:
            effect_error = True
    _require_gates_closed(dependencies)

    try:
        reconciled = dependencies.reconcile_settlement()
    except BaseException as exc:
        facts.settlement_reconciliation = SettlementRecon.BLOCKED.value
        raise _StopWake(D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT) from exc
    _require_gates_closed(dependencies)
    if type(reconciled) is not SettlementReconciliationResult:
        raise _StopWake(D10WakeStopReason.BLOCKED)
    facts.settlement_reconciliation = reconciled.classification.value
    if reconciled.classification is SettlementRecon.RECEIPT_RECOVERY_REQUIRED:
        raise _StopWake(D10WakeStopReason.RECEIPT_RECOVERY_REQUIRED)
    if reconciled.classification is not SettlementRecon.RECONCILED:
        raise _StopWake(
            D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT
            if attempt
            else D10WakeStopReason.BLOCKED
        )
    if (
        not reconciled.all_eight_gates_closed
        or reconciled.completed_execution_session != cycle.completed_session
        or reconciled.decision_id != cycle.pending_decision_id
    ):
        raise _StopWake(D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT)

    if attempt and effect is not None:
        effect_error = effect_error or any(
            actual != expected
            for actual, expected in (
                (effect.final_plan_id, reconciled.final_plan_id),
                (effect.invocation_id, reconciled.invocation_id),
                (effect.operation_id, reconciled.operation_id),
                (effect.application_id, reconciled.application_id),
                (
                    effect.account_predecessor_checkpoint_id,
                    reconciled.predecessor_checkpoint_id,
                ),
                (effect.final_checkpoint_id, reconciled.successor_checkpoint_id),
            )
        )
    facts.final_plan_id = _uuid_text(reconciled.final_plan_id)
    facts.invocation_id = _uuid_text(reconciled.invocation_id)
    facts.operation_id = _uuid_text(reconciled.operation_id)
    facts.application_id = _uuid_text(reconciled.application_id)
    facts.predecessor_checkpoint_id = _uuid_text(reconciled.predecessor_checkpoint_id)
    facts.successor_checkpoint_id = _uuid_text(reconciled.successor_checkpoint_id)
    if attempt and (
        effect_error
        or effect is None
        or effect.classification
        not in {
            Settlement.SETTLEMENT_COMPLETED,
            Settlement.SETTLEMENT_ALREADY_APPLIED,
        }
    ):
        if (
            effect is not None
            and effect.classification is Settlement.RECEIPT_RECOVERY_REQUIRED
        ):
            raise _StopWake(D10WakeStopReason.RECEIPT_RECOVERY_REQUIRED)
        raise _StopWake(D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT)


def _publish_or_reconcile_decision(
    dependencies: DisposableD10OneWeekSoakDependencies,
    facts: _Facts,
    cycle: PersonalDesktopUnattendedDailyCycleResult,
    deployment: object,
    lease: object,
) -> None:
    pub_status = cycle.decision_publication_status
    ready = cycle.classification is Cycle.DECISION_READY or (
        cycle.classification is Cycle.ALREADY_APPLIED
        and getattr(pub_status, "value", None)
        in {"DECISION_READY", "DECISION_READY_EFFECTS_DISABLED"}
    )
    finalized = cycle.classification is Cycle.DECISION_ALREADY_FINALIZED or (
        cycle.classification is Cycle.ALREADY_APPLIED
        and getattr(pub_status, "value", None) == "DECISION_ALREADY_FINALIZED"
    )
    benign_without_decision = cycle.classification in {
        Cycle.WARMING_UP,
        Cycle.NO_NEW_COMPLETED_SESSION,
    }
    if not (ready or finalized or benign_without_decision):
        raise _StopWake(D10WakeStopReason.BLOCKED)

    facts.next_decision_id = _uuid_text(cycle.next_decision_id)
    publication: PersonalDesktopUnattendedDecisionPublicationResult | None = None
    publication_error = False
    deadline_missed = False
    if ready:
        if cycle.completed_session is None or cycle.next_decision_id is None:
            raise _StopWake(D10WakeStopReason.BLOCKED)
        execution_session = next_xnys_execution_session(cycle.completed_session)
        deadline = xnys_regular_open(execution_session)
        facts.preopen_deadline_utc = deadline
        if _read_utc(dependencies.now) >= deadline:
            deadline_missed = True
            facts.publication_classification = (
                Publication.MISSED_DECISION_DEADLINE.value
            )
        else:
            _validate_before_effect(dependencies, deployment, lease)
            facts.publication_attempts = 1
            try:
                publication = dependencies.publish_decision()
                if (
                    type(publication)
                    is not PersonalDesktopUnattendedDecisionPublicationResult
                ):
                    publication_error = True
                else:
                    facts.publication_classification = publication.classification.value
                    facts.publication_effect_crossed = publication.real_effect_performed
                    if publication.real_effect_performed is not (
                        publication.classification is Publication.DECISION_PUBLISHED
                    ):
                        publication_error = True
                    if (
                        publication.decision_id != cycle.next_decision_id
                        or publication.selected_session != cycle.completed_session
                        or publication.intended_execution_session != execution_session
                    ):
                        publication_error = True
            except BaseException:
                publication_error = True
            _require_gates_closed(dependencies)

    # Reconciliation is independent of the publication return value.
    try:
        reconciliation = dependencies.reconcile_decision()
    except BaseException as exc:
        facts.decision_reconciliation = DecisionRecon.BLOCKED.value
        raise _StopWake(
            D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT
            if ready
            else D10WakeStopReason.BLOCKED
        ) from exc
    _require_gates_closed(dependencies)
    if type(reconciliation) is not UnattendedDecisionReconciliationResult:
        raise _StopWake(D10WakeStopReason.BLOCKED)
    facts.decision_reconciliation = reconciliation.classification.value
    facts.finalized_decision_id = _uuid_text(reconciliation.finalized_decision_id)
    if reconciliation.classification is DecisionRecon.SESSION_GAP:
        raise _StopWake(D10WakeStopReason.SESSION_GAP)
    if (
        reconciliation.classification is DecisionRecon.BLOCKED
        or not reconciliation.all_eight_gates_closed
    ):
        raise _StopWake(D10WakeStopReason.BLOCKED)

    if ready:
        if deadline_missed or (
            publication is not None
            and publication.classification is Publication.MISSED_DECISION_DEADLINE
        ):
            if reconciliation.classification is DecisionRecon.RECONCILED:
                _require_exact_decision_reconciliation(reconciliation, cycle)
                return
            raise _StopWake(D10WakeStopReason.MISSED_DECISION_DEADLINE)
        if publication_error or publication is None:
            raise _StopWake(D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT)
        if publication.classification is Publication.PUBLICATION_OUTCOME_AMBIGUOUS:
            raise _StopWake(D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT)
        if publication.classification is Publication.SESSION_GAP:
            raise _StopWake(D10WakeStopReason.SESSION_GAP)
        if publication.classification is Publication.MISSED_DECISION_DEADLINE:
            raise _StopWake(D10WakeStopReason.MISSED_DECISION_DEADLINE)
        if publication.classification not in {
            Publication.DECISION_PUBLISHED,
            Publication.DECISION_ALREADY_FINALIZED,
        }:
            raise _StopWake(D10WakeStopReason.BLOCKED)
        _require_exact_decision_reconciliation(reconciliation, cycle)
    elif finalized:
        _require_exact_decision_reconciliation(reconciliation, cycle)
    elif reconciliation.classification not in {
        DecisionRecon.WARMING_UP,
        DecisionRecon.NOT_FINALIZED,
    }:
        raise _StopWake(D10WakeStopReason.BLOCKED)


def _require_exact_decision_reconciliation(
    result: UnattendedDecisionReconciliationResult,
    cycle: PersonalDesktopUnattendedDailyCycleResult,
) -> None:
    if (
        result.classification is not DecisionRecon.RECONCILED
        or result.expected_decision_id != cycle.next_decision_id
        or result.finalized_decision_id != cycle.next_decision_id
        or result.completed_session != cycle.completed_session
    ):
        raise _StopWake(D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT)


def _cycle_stop_reason(classification: Cycle) -> D10WakeStopReason | None:
    return {
        Cycle.SESSION_GAP: D10WakeStopReason.SESSION_GAP,
        Cycle.MISSED_DECISION_DEADLINE: D10WakeStopReason.MISSED_DECISION_DEADLINE,
        Cycle.RECEIPT_RECOVERY_REQUIRED: D10WakeStopReason.RECEIPT_RECOVERY_REQUIRED,
        Cycle.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS: (
            D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
        ),
        Cycle.BLOCKED: D10WakeStopReason.BLOCKED,
        Cycle.CAPTURE_REQUIRED: (
            D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
        ),
    }.get(classification)


def _validate_before_effect(
    dependencies: DisposableD10OneWeekSoakDependencies,
    deployment: object,
    lease: object,
) -> None:
    _require_gates_closed(dependencies)
    try:
        dependencies.revalidate_before_effect(deployment, lease)
    except _StopWake:
        raise
    except DeploymentVerificationBlocked as exc:
        raise _StopWake(D10WakeStopReason.DEPLOYMENT_IDENTITY_DRIFT) from exc
    except ActivationLeaseVerificationBlocked as exc:
        raise _StopWake(D10WakeStopReason.LEASE_NOT_ACTIVE_OR_EXPIRED) from exc
    except Exception as exc:
        raise _StopWake(D10WakeStopReason.AUTHORITY_DRIFT) from exc
    _require_gates_closed(dependencies)


def _require_gates_closed(
    dependencies: DisposableD10OneWeekSoakDependencies,
) -> None:
    try:
        state = dependencies.gate_state()
    except BaseException as exc:
        raise _StopWake(D10WakeStopReason.EFFECT_GATE_DRIFT) from exc
    if not _gates_are_closed(state):
        raise _StopWake(D10WakeStopReason.EFFECT_GATE_DRIFT)


def _require_gate_state(
    dependencies: DisposableD10OneWeekSoakDependencies,
    expected: tuple[bool, ...],
) -> None:
    try:
        state = dependencies.gate_state()
    except BaseException as exc:
        raise _StopWake(D10WakeStopReason.EFFECT_GATE_DRIFT) from exc
    if type(state) is not tuple or len(state) != 8 or state != expected:
        raise _StopWake(D10WakeStopReason.EFFECT_GATE_DRIFT)


def _gates_are_closed(state: object) -> bool:
    return (
        type(state) is tuple
        and len(state) == 8
        and all(type(value) is bool and value is False for value in state)
    )


def _copy_provenance(facts: _Facts, deployment: object, lease: object) -> None:
    if (
        type(deployment) is not VerifiedD10Deployment
        or type(lease) is not VerifiedD10ActivationLease
    ):
        raise _StopWake(D10WakeStopReason.DEPLOYMENT_IDENTITY_DRIFT)
    facts.deployment_id = deployment.deployment_id
    facts.attestation_sha256 = deployment.attestation_sha256
    facts.certified_source_head = deployment.certified_source_head
    facts.certified_source_tree = deployment.certified_source_tree
    facts.executable_file_count = deployment.executable_file_count
    facts.soak_id = lease.soak_id
    facts.activation_utc = lease.accepted_activation_utc
    facts.end_utc = lease.end_utc


def _copy_capture(
    facts: _Facts, result: PersonalDesktopUnattendedMarketDataCaptureResult
) -> None:
    if result.selected_c3 is not None:
        facts.capture_selection_id = str(result.selected_c3.selection_id)
        facts.capture_snapshot_id = str(result.selected_c3.snapshot_id)
    if result.invocation is not None:
        facts.provider_attempt_id = result.invocation.attempt_id
        facts.provider_terminal_state = result.invocation.terminal_state
        facts.provider_call_disposition = result.invocation.provider_call_disposition


def _require_capture_result(result: object) -> None:
    if type(result) is not PersonalDesktopUnattendedMarketDataCaptureResult:
        raise _StopWake(D10WakeStopReason.BLOCKED)


def _uuid_text(value: object) -> str | None:
    return None if value is None else str(value)


def _read_utc(now: Callable[[], datetime]) -> datetime:
    value = now()
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("D10 clock must provide an aware timestamp")
    return value.astimezone(UTC)


def _is_utc(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is UTC


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def _build_evidence(
    f: _Facts,
    outcome: D10WakeOutcome,
    stop_reason: D10WakeStopReason | None,
) -> D10OneWeekWakeEvidence:
    return D10OneWeekWakeEvidence(
        outcome=outcome,
        stop_reason=stop_reason,
        observed_at_utc=f.observed_at_utc,
        deployment_id=f.deployment_id,
        attestation_sha256=f.attestation_sha256,
        certified_source_head=f.certified_source_head,
        certified_source_tree=f.certified_source_tree,
        executable_file_count=f.executable_file_count,
        soak_id=f.soak_id,
        activation_utc=f.activation_utc,
        end_utc=f.end_utc,
        completed_session=f.completed_session,
        next_execution_session=f.next_execution_session,
        preopen_deadline_utc=f.preopen_deadline_utc,
        capture_classification=f.capture_classification,
        capture_selection_id=f.capture_selection_id,
        capture_snapshot_id=f.capture_snapshot_id,
        provider_attempt_id=f.provider_attempt_id,
        provider_terminal_state=f.provider_terminal_state,
        provider_call_disposition=f.provider_call_disposition,
        historical_audit_classification=f.historical_audit_classification,
        historical_reconciled_count=f.historical_reconciled_count,
        historical_current_decision_id=f.historical_current_decision_id,
        historical_unresolved_decision_id=f.historical_unresolved_decision_id,
        settlement_decision_id=f.settlement_decision_id,
        settlement_classification=f.settlement_classification,
        settlement_reconciliation=f.settlement_reconciliation,
        final_plan_id=f.final_plan_id,
        invocation_id=f.invocation_id,
        operation_id=f.operation_id,
        application_id=f.application_id,
        predecessor_checkpoint_id=f.predecessor_checkpoint_id,
        successor_checkpoint_id=f.successor_checkpoint_id,
        next_decision_id=f.next_decision_id,
        publication_classification=f.publication_classification,
        decision_reconciliation=f.decision_reconciliation,
        finalized_decision_id=f.finalized_decision_id,
        provider_attempts=f.provider_attempts,
        settlement_attempts=f.settlement_attempts,
        publication_attempts=f.publication_attempts,
        provider_effect_crossed=f.provider_effect_crossed,
        settlement_effect_crossed=f.settlement_effect_crossed,
        publication_effect_crossed=f.publication_effect_crossed,
    )


def serialize_d10_wake_evidence(evidence: D10OneWeekWakeEvidence) -> str:
    """Serialize the fixed operator evidence shape as bounded canonical JSON."""

    if type(evidence) is not D10OneWeekWakeEvidence:
        raise TypeError("D10 wake evidence is invalid")
    payload = {
        "schema": D10_WAKE_EVIDENCE_SCHEMA,
        "outcome": evidence.outcome.value,
        "stop_reason": None
        if evidence.stop_reason is None
        else evidence.stop_reason.value,
        "observed_at_utc": _iso(evidence.observed_at_utc),
        "deployment": {
            "id": evidence.deployment_id,
            "attestation_sha256": evidence.attestation_sha256,
            "source_head": evidence.certified_source_head,
            "source_tree": evidence.certified_source_tree,
            "executable_file_count": evidence.executable_file_count,
        },
        "soak": {
            "id": evidence.soak_id,
            "activation_utc": _iso(evidence.activation_utc),
            "end_utc": _iso(evidence.end_utc),
        },
        "runtime": {
            "scheduler_contract_schema": D10_SCHEDULER_CONTRACT_SCHEMA,
            "scheduler_task_path": D10_SCHEDULER_CONTRACT.task_path,
            "trading_sid": D10_SCHEDULER_CONTRACT.principal_sid,
            "production_python": D10_PRODUCTION_PYTHON,
            "production_python_version": D10_PYTHON_VERSION,
        },
        "session": {
            "completed": evidence.completed_session,
            "next_execution": evidence.next_execution_session,
            "preopen_deadline_utc": _iso(evidence.preopen_deadline_utc),
        },
        "capture": {
            "classification": evidence.capture_classification,
            "selection_id": evidence.capture_selection_id,
            "snapshot_id": evidence.capture_snapshot_id,
            "attempt_id": evidence.provider_attempt_id,
            "terminal_state": evidence.provider_terminal_state,
            "provider_call_disposition": evidence.provider_call_disposition,
        },
        "history": {
            "classification": evidence.historical_audit_classification,
            "reconciled_count": evidence.historical_reconciled_count,
            "current_decision_id": evidence.historical_current_decision_id,
            "unresolved_decision_id": evidence.historical_unresolved_decision_id,
        },
        "settlement": {
            "decision_id": evidence.settlement_decision_id,
            "classification": evidence.settlement_classification,
            "reconciliation": evidence.settlement_reconciliation,
            "plan_id": evidence.final_plan_id,
            "invocation_id": evidence.invocation_id,
            "operation_id": evidence.operation_id,
            "application_id": evidence.application_id,
            "predecessor_checkpoint_id": evidence.predecessor_checkpoint_id,
            "successor_checkpoint_id": evidence.successor_checkpoint_id,
        },
        "decision": {
            "id": evidence.next_decision_id,
            "publication": evidence.publication_classification,
            "reconciliation": evidence.decision_reconciliation,
            "finalized_id": evidence.finalized_decision_id,
        },
        "budgets": {
            "provider_attempts": evidence.provider_attempts,
            "settlement_attempts": evidence.settlement_attempts,
            "publication_attempts": evidence.publication_attempts,
            "receipt_recovery_attempts": evidence.receipt_recovery_attempts,
            "broker_live_calls": evidence.broker_live_calls,
        },
        "effect_crossings": {
            "provider": evidence.provider_effect_crossed,
            "settlement": evidence.settlement_effect_crossed,
            "publication": evidence.publication_effect_crossed,
        },
        "final_gates": {
            "all_closed": evidence.all_effect_gates_closed,
            "closed_count": evidence.closed_effect_gate_count,
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_D10_WAKE_EVIDENCE_BYTES:
        raise ValueError("D10 wake evidence exceeds its fixed bound")
    return encoded


def build_d10_one_week_wake_summary(
    evidence: tuple[D10OneWeekWakeEvidence, ...],
) -> D10OneWeekWakeSummary:
    """Build a read-only rollup from at most 512 sanitized wake records."""

    if (
        type(evidence) is not tuple
        or not 1 <= len(evidence) <= MAX_D10_SUMMARY_WAKES
        or any(type(item) is not D10OneWeekWakeEvidence for item in evidence)
        or len(set(evidence)) != len(evidence)
    ):
        raise ValueError("D10 summary requires a bounded evidence tuple")
    first = evidence[0]
    times = tuple(item.observed_at_utc for item in evidence)
    if (
        first.soak_id is None
        or first.deployment_id is None
        or tuple(sorted(times)) != times
        or any(
            item.soak_id != first.soak_id
            or item.deployment_id != first.deployment_id
            or not item.all_effect_gates_closed
            for item in evidence
        )
    ):
        raise ValueError("D10 summary evidence identity/order differs")
    stops = Counter(
        item.stop_reason.value for item in evidence if item.stop_reason is not None
    )
    return D10OneWeekWakeSummary(
        soak_id=first.soak_id,
        deployment_id=first.deployment_id,
        wake_count=len(evidence),
        completed_count=sum(
            item.outcome is D10WakeOutcome.COMPLETED for item in evidence
        ),
        no_action_count=sum(
            item.outcome is D10WakeOutcome.NO_ACTION for item in evidence
        ),
        stopped_count=sum(item.outcome is D10WakeOutcome.STOPPED for item in evidence),
        provider_attempts=sum(item.provider_attempts for item in evidence),
        settlement_attempts=sum(item.settlement_attempts for item in evidence),
        publication_attempts=sum(item.publication_attempts for item in evidence),
        stop_counts=tuple(sorted(stops.items())),
        first_observed_at_utc=times[0],
        last_observed_at_utc=times[-1],
        all_effect_gates_closed=True,
    )


def _production_dependencies() -> DisposableD10OneWeekSoakDependencies:
    admission: dict[str, object] = {}

    def validate(deployment: object, lease: object) -> None:
        if (
            type(deployment) is not VerifiedD10Deployment
            or type(lease) is not VerifiedD10ActivationLease
        ):
            raise DeploymentVerificationBlocked("D10 provenance type differs")
        require_verified_d10_deployment(deployment)
        require_verified_d10_activation_lease(lease, deployment)
        if not is_frozen_one_week_soak_scheduler_contract(D10_SCHEDULER_CONTRACT):
            raise DeploymentVerificationBlocked("D10 scheduler identity differs")

        try:
            current_c1 = require_validated_production_authority(
                acquire_validated_production_authority()
            )
            current_token = WindowsTradingTokenObserver().observe()
            require_trading_token(D10_SCHEDULER_CONTRACT.principal_sid, current_token)
        except Exception as exc:
            raise _StopWake(D10WakeStopReason.AUTHORITY_DRIFT) from exc
        if "c1" in admission and (
            admission["c1"] != current_c1 or admission["token"] != current_token
        ):
            raise _StopWake(D10WakeStopReason.AUTHORITY_DRIFT)

        current_deployment = verify_d10_deployment()
        require_verified_d10_deployment(current_deployment)
        if _deployment_facts(current_deployment) != _deployment_facts(deployment):
            raise DeploymentVerificationBlocked("D10 deployment identity drifted")
        current_lease = verify_d10_activation_lease(current_deployment)
        require_verified_d10_activation_lease(current_lease, current_deployment)
        if _lease_facts(current_lease) != _lease_facts(lease):
            raise ActivationLeaseVerificationBlocked("D10 lease identity drifted")

        if "c1" not in admission:
            admission["c1"] = current_c1
            admission["token"] = current_token

    return DisposableD10OneWeekSoakDependencies(
        now=lambda: datetime.now(UTC),
        validate_admission=validate,
        revalidate_before_effect=validate,
        gate_state=personal_desktop_unattended_effect_gate_state,
        set_market_data_gate=_set_market_data_gate,
        close_all_gates=_close_all_effect_gates,
        capture=run_personal_desktop_unattended_market_data_capture,
        daily_cycle=run_personal_desktop_unattended_daily_cycle,
        historical_audit=audit_personal_desktop_historical_settlements,
        settle=execute_personal_desktop_unattended_settlement,
        reconcile_settlement=reconcile_personal_desktop_unattended_settlement,
        publish_decision=run_personal_desktop_unattended_decision_publication,
        reconcile_decision=reconcile_personal_desktop_unattended_decision,
    )


def _set_market_data_gate(opened: bool) -> None:
    if type(opened) is not bool:
        raise TypeError("D10 market-data gate state must be boolean")
    if opened and not _gates_are_closed(
        personal_desktop_unattended_effect_gate_state()
    ):
        raise RuntimeError("D10 market-data gate requires all other gates closed")
    c3.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED = opened


def _close_all_effect_gates() -> None:
    c3.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED = False
    decision_gate.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED = (
        False
    )
    account.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
    account.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
    supervised.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
    recovery.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False
    paper_exec.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = False
    provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED = False  # noqa: E501


def _deployment_facts(value: VerifiedD10Deployment) -> tuple[object, ...]:
    return (
        value.deployment_id,
        value.attestation_sha256,
        value.certified_source_head,
        value.certified_source_tree,
        value.executable_file_count,
    )


def _lease_facts(value: VerifiedD10ActivationLease) -> tuple[object, ...]:
    return (
        value.state,
        value.soak_id,
        value.accepted_activation_utc,
        value.end_utc,
        value.deployment_id,
        value.attestation_sha256,
    )
