"""Focused Architecture-122 one-wake controller composition tests."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from trading_bot.cli.paper_operation_inspection import PaperOperationClassification
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak as soak_controller,
)
from trading_bot.runtime.paper_operation import PaperOperationStatus
from trading_bot.runtime.personal_desktop_d10_deployment_verifier import (
    ActivationLeaseVerificationBlocked,
    DeploymentVerificationBlocked,
    VerifiedD10ActivationLease,
    VerifiedD10Deployment,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    personal_desktop_unattended_capture_request,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification as Cycle,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleResult,
)
from trading_bot.runtime.personal_desktop_unattended_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationClassification as Publication,
)
from trading_bot.runtime.personal_desktop_unattended_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationResult,
)
from trading_bot.runtime.personal_desktop_unattended_decision_reconciliation import (
    UnattendedDecisionReconciliationClassification as DecisionRecon,
)
from trading_bot.runtime.personal_desktop_unattended_decision_reconciliation import (
    UnattendedDecisionReconciliationResult,
)
from trading_bot.runtime.personal_desktop_unattended_historical_settlement_audit import (  # noqa: E501
    HistoricalSettlementAuditClassification as History,
)
from trading_bot.runtime.personal_desktop_unattended_historical_settlement_audit import (  # noqa: E501
    HistoricalSettlementAuditResult,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification as Capture,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureResult,
    PersonalDesktopUnattendedSelectedC3Evidence,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    D10WakeOutcome,
    D10WakeStopReason,
    DisposableD10OneWeekSoakDependencies,
    build_d10_one_week_wake_summary,
    run_personal_desktop_unattended_one_week_soak_for_test,
    serialize_d10_wake_evidence,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationStatus as PubStatus,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification as InvocationStorage,
)
from trading_bot.runtime.personal_desktop_unattended_settlement_execution import (
    SettlementExecutionClassification as Settlement,
)
from trading_bot.runtime.personal_desktop_unattended_settlement_execution import (
    SettlementExecutionResult,
)
from trading_bot.runtime.personal_desktop_unattended_settlement_reconciliation import (
    SettlementReconciliationClassification as SettlementRecon,
)
from trading_bot.runtime.personal_desktop_unattended_settlement_reconciliation import (
    SettlementReconciliationResult,
)
from trading_bot.runtime.windows_effectful_capture import (
    prepare_production_capture_plan,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    ProductionCaptureInvocationResult,
)

SESSION = TradingSession(date(2026, 9, 21))
NEXT_SESSION = TradingSession(date(2026, 9, 22))
OBSERVED = datetime(2026, 9, 22, 12, tzinfo=UTC)
ACTIVATION = datetime(2026, 9, 20, tzinfo=UTC)
END = ACTIVATION + timedelta(days=7)
DECISION_ID = UUID(int=101)
NEXT_DECISION_ID = UUID(int=102)
DEPLOYMENT = VerifiedD10Deployment("deployment", "a" * 64, "b" * 40, "c" * 40, 2)
LEASE = VerifiedD10ActivationLease(
    "ACTIVE", "soak", ACTIVATION, END, "deployment", "a" * 64
)


def _uuid(number: int) -> UUID:
    return UUID(int=number)


def _capture(
    classification: Capture = Capture.NO_NEW_COMPLETED_SESSION,
    *,
    invocation: ProductionCaptureInvocationResult | None = None,
) -> PersonalDesktopUnattendedMarketDataCaptureResult:
    request = personal_desktop_unattended_capture_request(SESSION)
    prepare_production_capture_plan(request, OBSERVED)
    selected = (
        PersonalDesktopUnattendedSelectedC3Evidence(
            _uuid(1), _uuid(2), _uuid(3), _uuid(4), _uuid(5), "d" * 64, 100
        )
        if classification is Capture.NO_NEW_COMPLETED_SESSION
        else None
    )
    return PersonalDesktopUnattendedMarketDataCaptureResult(
        classification,
        SESSION,
        request,
        hashlib.sha256(request.canonical_c2_request_json()).hexdigest(),
        selected_c3=selected,
        invocation=invocation,
    )


def _invocation(state: str, disposition: str) -> ProductionCaptureInvocationResult:
    successful = state == "SUCCEEDED"
    return ProductionCaptureInvocationResult(
        session_id=str(_uuid(10)),
        attempt_id=str(_uuid(11)),
        claim_id=str(_uuid(12)),
        reservation_id=str(_uuid(13)),
        execution_id=str(_uuid(14)) if successful else None,
        terminal_id=str(_uuid(15)),
        selection_id=str(_uuid(16)) if successful else None,
        terminal_state=state,
        provider_call_disposition=disposition,
        snapshot_id=_uuid(17) if successful else None,
        artifact_sha256="e" * 64 if successful else None,
        artifact_byte_length=100 if successful else None,
    )


def _cycle(
    classification: Cycle,
    *,
    pending: UUID | None = None,
    next_decision: UUID | None = None,
    publication_status: PubStatus | None = None,
    session: TradingSession = SESSION,
) -> PersonalDesktopUnattendedDailyCycleResult:
    return PersonalDesktopUnattendedDailyCycleResult(
        classification,
        completed_session=session,
        selected_snapshot_id=_uuid(20),
        pending_decision_id=pending,
        next_decision_id=next_decision,
        decision_publication_status=publication_status,
    )


def _history(
    classification: History = History.RECONCILED_HISTORY,
    *,
    unresolved: UUID | None = None,
    reconciled: tuple[UUID, ...] = (),
) -> HistoricalSettlementAuditResult:
    return HistoricalSettlementAuditResult(
        classification,
        completed_session=SESSION,
        reconciled_decision_ids=reconciled,
        unresolved_decision_id=unresolved,
        all_eight_gates_closed=classification is History.RECONCILED_HISTORY,
    )


def _settlement_result() -> SettlementExecutionResult:
    return SettlementExecutionResult(
        Settlement.SETTLEMENT_COMPLETED,
        completed_execution_session=SESSION,
        decision_id=DECISION_ID,
        final_plan_id=_uuid(42),
        invocation_id=_uuid(43),
        operation_id=_uuid(44),
        application_id=_uuid(45),
        account_predecessor_checkpoint_id=_uuid(46),
        final_checkpoint_id=_uuid(47),
        all_eight_gates_closed=True,
        real_effect_performed=True,
    )


def _settlement_reconciliation() -> SettlementReconciliationResult:
    return SettlementReconciliationResult(
        SettlementRecon.RECONCILED,
        completed_execution_session=SESSION,
        decision_selected_session=TradingSession(date(2026, 9, 18)),
        decision_id=DECISION_ID,
        decision_selected_snapshot_id=_uuid(40),
        execution_selected_snapshot_id=_uuid(41),
        final_plan_id=_uuid(42),
        invocation_id=_uuid(43),
        operation_id=_uuid(44),
        application_id=_uuid(45),
        predecessor_checkpoint_id=_uuid(46),
        successor_checkpoint_id=_uuid(47),
        invocation_storage_classification=InvocationStorage.FINALIZED_IDENTICAL,
        operation_classification=PaperOperationClassification.ALREADY_APPLIED,
        receipt_status=PaperOperationStatus.COMPLETED,
        all_eight_gates_closed=True,
    )


def _decision_reconciliation(
    classification: DecisionRecon = DecisionRecon.RECONCILED,
    *,
    finalized: UUID | None = NEXT_DECISION_ID,
) -> UnattendedDecisionReconciliationResult:
    return UnattendedDecisionReconciliationResult(
        classification,
        completed_session=SESSION,
        expected_decision_id=NEXT_DECISION_ID,
        finalized_decision_id=finalized,
        intended_execution_session=NEXT_SESSION,
        all_eight_gates_closed=True,
    )


def _publication_result(
    classification: Publication = Publication.DECISION_PUBLISHED,
) -> PersonalDesktopUnattendedDecisionPublicationResult:
    return PersonalDesktopUnattendedDecisionPublicationResult(
        classification,
        decision_id=NEXT_DECISION_ID,
        selected_session=SESSION,
        intended_execution_session=NEXT_SESSION,
        real_effect_performed=classification is Publication.DECISION_PUBLISHED,
    )


class _Harness:
    def __init__(
        self,
        *,
        captures: tuple[PersonalDesktopUnattendedMarketDataCaptureResult, ...] = (),
        cycles: tuple[PersonalDesktopUnattendedDailyCycleResult, ...] = (),
        histories: tuple[HistoricalSettlementAuditResult, ...] = (),
        settlement: SettlementExecutionResult | None = None,
        settlement_reconciliation: SettlementReconciliationResult | None = None,
        publication: PersonalDesktopUnattendedDecisionPublicationResult | None = None,
        decision_reconciliation: UnattendedDecisionReconciliationResult | None = None,
        now: datetime = OBSERVED,
        initially_open_gate: int | None = None,
        fail_after_open: str | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.gates = [False] * 8
        if initially_open_gate is not None:
            self.gates[initially_open_gate] = True
        self.captures = deque(captures or (_capture(),))
        self.cycles = deque(
            cycles
            or (
                _cycle(
                    Cycle.DECISION_ALREADY_FINALIZED,
                    next_decision=NEXT_DECISION_ID,
                    publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
                ),
                _cycle(
                    Cycle.DECISION_ALREADY_FINALIZED,
                    next_decision=NEXT_DECISION_ID,
                    publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
                ),
            )
        )
        self.histories = deque(histories or (_history(), _history()))
        self.settlement_result = settlement or _settlement_result()
        self.settlement_reconciliation = (
            settlement_reconciliation or _settlement_reconciliation()
        )
        self.publication_result = publication or _publication_result()
        self.decision_reconciliation = (
            decision_reconciliation or _decision_reconciliation()
        )
        self.now_value = now
        self.capture_calls = 0
        self.settlement_calls = 0
        self.publication_calls = 0
        self.admission_error: Exception | None = None
        self.revalidation_error: Exception | None = None
        self.fail_call: str | None = None
        self.fail_after_open = fail_after_open

    def _raise_if(self, name: str) -> None:
        if self.fail_call == name:
            raise RuntimeError(f"failed {name}")

    def _assert_closed(self) -> None:
        assert tuple(self.gates) == (False,) * 8

    def dependencies(self) -> DisposableD10OneWeekSoakDependencies:
        return DisposableD10OneWeekSoakDependencies(
            now=lambda: self.now_value,
            validate_admission=self.validate_admission,
            revalidate_before_effect=self.revalidate,
            gate_state=lambda: tuple(self.gates),
            set_market_data_gate=self.set_capture_gate,
            close_all_gates=self.close_all_gates,
            capture=self.capture,
            daily_cycle=self.daily_cycle,
            historical_audit=self.audit,
            settle=self.settle,
            reconcile_settlement=self.reconcile_settlement_call,
            publish_decision=self.publish,
            reconcile_decision=self.reconcile_decision_call,
        )

    def validate_admission(self, deployment: object, lease: object) -> None:
        self.calls.append("admission")
        self._raise_if("admission")
        if self.admission_error is not None:
            raise self.admission_error
        assert deployment is DEPLOYMENT
        assert lease is LEASE

    def revalidate(self, deployment: object, lease: object) -> None:
        self.calls.append("revalidate")
        self._raise_if("revalidate")
        if self.revalidation_error is not None:
            raise self.revalidation_error
        assert deployment is DEPLOYMENT
        assert lease is LEASE

    def set_capture_gate(self, opened: bool) -> None:
        self.calls.append("capture_gate_open" if opened else "capture_gate_close")
        if opened:
            assert tuple(self.gates) == (False,) * 8
        self.gates[0] = opened

    def close_all_gates(self) -> None:
        self.calls.append("final_close")
        self.gates[:] = [False] * 8

    def capture(self) -> PersonalDesktopUnattendedMarketDataCaptureResult:
        self.calls.append("capture")
        self._raise_if("capture")
        self.capture_calls += 1
        if self.fail_after_open == "capture" and self.capture_calls == 2:
            raise RuntimeError("failed after provider gate opened")
        return self.captures.popleft()

    def daily_cycle(self) -> PersonalDesktopUnattendedDailyCycleResult:
        self.calls.append("daily_cycle")
        self._assert_closed()
        self._raise_if("daily_cycle")
        return self.cycles.popleft()

    def audit(self) -> HistoricalSettlementAuditResult:
        self.calls.append("historical_audit")
        self._assert_closed()
        self._raise_if("historical_audit")
        return self.histories.popleft()

    def settle(self) -> SettlementExecutionResult:
        self.calls.append("settle")
        self._assert_closed()
        self._raise_if("settle")
        self.settlement_calls += 1
        self.gates[6] = True
        try:
            assert sum(self.gates) == 1
            if self.fail_after_open == "settlement":
                raise RuntimeError("failed after settlement gate opened")
            return self.settlement_result
        finally:
            self.gates[6] = False

    def reconcile_settlement_call(self) -> SettlementReconciliationResult:
        self.calls.append("settlement_reconciliation")
        self._assert_closed()
        self._raise_if("settlement_reconciliation")
        return self.settlement_reconciliation

    def publish(self) -> PersonalDesktopUnattendedDecisionPublicationResult:
        self.calls.append("publish")
        self._assert_closed()
        self._raise_if("publish")
        self.publication_calls += 1
        self.gates[1] = True
        try:
            assert sum(self.gates) == 1
            if self.fail_after_open == "publication":
                raise RuntimeError("failed after publication gate opened")
            return self.publication_result
        finally:
            self.gates[1] = False

    def reconcile_decision_call(self) -> UnattendedDecisionReconciliationResult:
        self.calls.append("decision_reconciliation")
        self._assert_closed()
        self._raise_if("decision_reconciliation")
        return self.decision_reconciliation


def _run(harness: _Harness):
    return run_personal_desktop_unattended_one_week_soak_for_test(
        DEPLOYMENT, LEASE, harness.dependencies()
    )


def test_positive_idempotent_wake_and_reconciled_history_are_no_effect() -> None:
    prior = _uuid(60)
    harness = _Harness(
        cycles=(
            _cycle(
                Cycle.DECISION_ALREADY_FINALIZED,
                next_decision=NEXT_DECISION_ID,
                publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
            ),
            _cycle(
                Cycle.DECISION_ALREADY_FINALIZED,
                next_decision=NEXT_DECISION_ID,
                publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
            ),
        ),
        histories=(_history(reconciled=(prior,)), _history(reconciled=(prior,))),
    )

    evidence = _run(harness)

    assert evidence.outcome is D10WakeOutcome.NO_ACTION
    assert evidence.stop_reason is None
    assert evidence.historical_reconciled_count == 1
    assert evidence.decision_reconciliation == DecisionRecon.RECONCILED.value
    assert harness.capture_calls == 1
    assert harness.settlement_calls == harness.publication_calls == 0
    assert evidence.provider_attempts == evidence.settlement_attempts == 0
    assert evidence.publication_attempts == evidence.receipt_recovery_attempts == 0
    assert evidence.broker_live_calls == 0
    assert evidence.all_effect_gates_closed
    assert harness.calls[-1] == "final_close"


def test_capture_required_uses_one_provider_attempt_and_closed_gate_reread() -> None:
    provider = _invocation("SUCCEEDED", "CONFIRMED")
    harness = _Harness(
        captures=(
            _capture(Capture.CAPTURE_REQUIRED),
            _capture(Capture.CAPTURE_REQUIRED, invocation=provider),
            _capture(),
        ),
        cycles=(
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
        ),
        histories=(_history(), _history()),
    )

    evidence = _run(harness)

    assert evidence.outcome is D10WakeOutcome.COMPLETED
    assert evidence.provider_attempts == 1
    assert evidence.provider_effect_crossed is True
    assert evidence.provider_attempt_id == provider.attempt_id
    assert evidence.capture_classification == Capture.NO_NEW_COMPLETED_SESSION.value
    assert harness.capture_calls == 3
    assert harness.publication_calls == 1
    assert harness.calls.count("capture_gate_open") == 1
    assert harness.calls.count("capture_gate_close") == 1
    assert harness.calls.index("capture_gate_close") < harness.calls.index(
        "daily_cycle"
    )
    assert evidence.publication_attempts == 1
    assert evidence.publication_effect_crossed
    assert evidence.decision_reconciliation == DecisionRecon.RECONCILED.value
    assert tuple(harness.gates) == (False,) * 8


def test_capture_not_required_never_opens_market_data_gate() -> None:
    harness = _Harness(
        captures=(_capture(),),
        cycles=(
            _cycle(
                Cycle.DECISION_ALREADY_FINALIZED,
                next_decision=NEXT_DECISION_ID,
                publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
            ),
            _cycle(
                Cycle.DECISION_ALREADY_FINALIZED,
                next_decision=NEXT_DECISION_ID,
                publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
            ),
        ),
    )

    evidence = _run(harness)

    assert evidence.capture_classification == Capture.NO_NEW_COMPLETED_SESSION.value
    assert evidence.provider_attempts == 0
    assert "capture_gate_open" not in harness.calls
    assert evidence.outcome is D10WakeOutcome.NO_ACTION


def test_settlement_attempted_once_then_reconciled_before_fresh_cycle() -> None:
    harness = _Harness(
        cycles=(
            _cycle(Cycle.EXECUTION_READY, pending=DECISION_ID),
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
        ),
        histories=(_history(), _history()),
        settlement=_settlement_result(),
        settlement_reconciliation=_settlement_reconciliation(),
    )

    evidence = _run(harness)

    assert harness.settlement_calls == 1
    assert evidence.settlement_attempts == 1
    assert evidence.settlement_effect_crossed
    assert evidence.settlement_decision_id == str(DECISION_ID)
    assert evidence.settlement_reconciliation == SettlementRecon.RECONCILED.value
    assert evidence.final_plan_id == str(_uuid(42))
    assert evidence.invocation_id == str(_uuid(43))
    assert evidence.operation_id == str(_uuid(44))
    assert evidence.application_id == str(_uuid(45))
    assert evidence.predecessor_checkpoint_id == str(_uuid(46))
    assert evidence.successor_checkpoint_id == str(_uuid(47))
    assert (
        harness.calls.index("settle")
        < harness.calls.index("settlement_reconciliation")
        < harness.calls.index("daily_cycle", harness.calls.index("daily_cycle") + 1)
    )
    assert harness.publication_calls == 1
    assert tuple(harness.gates) == (False,) * 8

    ordered = (
        "admission",
        "capture",
        "daily_cycle",
        "historical_audit",
        "revalidate",
        "settle",
        "settlement_reconciliation",
        "daily_cycle",
        "historical_audit",
        "revalidate",
        "publish",
        "decision_reconciliation",
        "final_close",
    )
    positions = []
    next_position = 0
    for name in ordered:
        position = harness.calls.index(name, next_position)
        positions.append(position)
        next_position = position + 1
    assert positions == sorted(positions)


def test_already_applied_duplicate_wake_reconciles_without_reexecution() -> None:
    harness = _Harness(
        cycles=(
            _cycle(Cycle.ALREADY_APPLIED, pending=DECISION_ID),
            _cycle(
                Cycle.DECISION_ALREADY_FINALIZED,
                next_decision=NEXT_DECISION_ID,
                publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
            ),
        ),
        histories=(_history(), _history()),
    )

    evidence = _run(harness)

    assert evidence.outcome is D10WakeOutcome.NO_ACTION
    assert harness.settlement_calls == 0
    assert harness.calls.count("settlement_reconciliation") == 1
    assert evidence.settlement_attempts == 0
    assert evidence.settlement_reconciliation == SettlementRecon.RECONCILED.value
    assert evidence.decision_reconciliation == DecisionRecon.RECONCILED.value


def test_restarted_wake_converges_on_durable_already_applied_state() -> None:
    first_harness = _Harness(
        cycles=(
            _cycle(Cycle.EXECUTION_READY, pending=DECISION_ID),
            _cycle(
                Cycle.DECISION_ALREADY_FINALIZED,
                next_decision=NEXT_DECISION_ID,
                publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
            ),
        ),
        histories=(_history(), _history()),
    )
    first = _run(first_harness)
    second_harness = _Harness(
        cycles=(
            _cycle(Cycle.ALREADY_APPLIED, pending=DECISION_ID),
            _cycle(
                Cycle.DECISION_ALREADY_FINALIZED,
                next_decision=NEXT_DECISION_ID,
                publication_status=PubStatus.DECISION_ALREADY_FINALIZED,
            ),
        ),
        histories=(_history(), _history()),
        now=OBSERVED + timedelta(minutes=1),
    )

    second = _run(second_harness)

    assert first.outcome is D10WakeOutcome.COMPLETED
    assert first.settlement_attempts == 1
    assert second.outcome is D10WakeOutcome.NO_ACTION
    assert second.settlement_attempts == 0
    assert second_harness.settlement_calls == 0
    assert second.settlement_reconciliation == SettlementRecon.RECONCILED.value
    assert first.operation_id == second.operation_id
    assert first.successor_checkpoint_id == second.successor_checkpoint_id


def test_stale_historical_decision_blocks_before_settlement_or_publication() -> None:
    harness = _Harness(
        cycles=(_cycle(Cycle.EXECUTION_READY, pending=DECISION_ID),),
        histories=(_history(History.STALE_UNRESOLVED_DECISION, unresolved=_uuid(70)),),
    )

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.STALE_UNRESOLVED_DECISION
    assert evidence.historical_unresolved_decision_id == str(_uuid(70))
    assert harness.settlement_calls == harness.publication_calls == 0
    assert evidence.receipt_recovery_attempts == 0
    assert evidence.all_effect_gates_closed


@pytest.mark.parametrize(
    ("classification", "reason"),
    [
        (Cycle.MISSED_DECISION_DEADLINE, D10WakeStopReason.MISSED_DECISION_DEADLINE),
        (Cycle.SESSION_GAP, D10WakeStopReason.SESSION_GAP),
        (
            Cycle.RECEIPT_RECOVERY_REQUIRED,
            D10WakeStopReason.RECEIPT_RECOVERY_REQUIRED,
        ),
    ],
)
def test_cycle_stop_conditions_fail_closed_without_followup_effects(
    classification: Cycle, reason: D10WakeStopReason
) -> None:
    harness = _Harness(cycles=(_cycle(classification),))

    evidence = _run(harness)

    assert evidence.stop_reason is reason
    assert harness.settlement_calls == harness.publication_calls == 0
    assert evidence.receipt_recovery_attempts == 0
    assert tuple(harness.gates) == (False,) * 8


def test_provider_ambiguity_stops_without_retry() -> None:
    harness = _Harness(
        captures=(_capture(Capture.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS),),
    )

    evidence = _run(harness)

    assert (
        evidence.stop_reason is D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
    )
    assert harness.capture_calls == 1
    assert harness.settlement_calls == harness.publication_calls == 0
    assert evidence.provider_attempts == 0
    assert evidence.receipt_recovery_attempts == 0


def test_ambiguous_provider_result_is_not_retried() -> None:
    ambiguous = _invocation("AMBIGUOUS", "MAY_HAVE_OCCURRED")
    harness = _Harness(
        captures=(
            _capture(Capture.CAPTURE_REQUIRED),
            _capture(Capture.CAPTURE_REQUIRED, invocation=ambiguous),
        ),
    )

    evidence = _run(harness)

    assert (
        evidence.stop_reason is D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
    )
    assert evidence.provider_attempts == 1
    assert evidence.provider_terminal_state == "AMBIGUOUS"
    assert harness.capture_calls == 2
    assert "daily_cycle" not in harness.calls


def test_deployment_and_lease_provenance_fail_before_any_effect() -> None:
    deployment_drift = _Harness()
    deployment_drift.admission_error = DeploymentVerificationBlocked("copied proof")
    rejected = _run(deployment_drift)
    assert rejected.stop_reason is D10WakeStopReason.DEPLOYMENT_IDENTITY_DRIFT
    assert deployment_drift.capture_calls == 0

    lease_drift = _Harness()
    lease_drift.admission_error = ActivationLeaseVerificationBlocked("expired")
    rejected_lease = _run(lease_drift)
    assert rejected_lease.stop_reason is D10WakeStopReason.LEASE_NOT_ACTIVE_OR_EXPIRED
    assert lease_drift.capture_calls == 0


def test_production_admission_classifies_c1_drift_before_any_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        soak_controller,
        "require_verified_d10_deployment",
        lambda _deployment: DEPLOYMENT,
    )
    monkeypatch.setattr(
        soak_controller,
        "require_verified_d10_activation_lease",
        lambda _lease, _deployment: LEASE,
    )
    monkeypatch.setattr(
        soak_controller,
        "is_frozen_one_week_soak_scheduler_contract",
        lambda _contract: True,
    )
    monkeypatch.setattr(
        soak_controller, "acquire_validated_production_authority", object
    )

    def reject_c1(_authority: object) -> object:
        raise RuntimeError("C1 drift")

    monkeypatch.setattr(
        soak_controller, "require_validated_production_authority", reject_c1
    )

    evidence = soak_controller.run_personal_desktop_unattended_one_week_soak(
        DEPLOYMENT, LEASE
    )

    assert evidence.stop_reason is D10WakeStopReason.AUTHORITY_DRIFT
    assert evidence.provider_attempts == evidence.settlement_attempts == 0
    assert evidence.publication_attempts == 0
    assert evidence.all_effect_gates_closed
    assert (
        soak_controller.personal_desktop_unattended_effect_gate_state() == (False,) * 8
    )


def test_expired_lease_blocks_before_capture_or_effect() -> None:
    harness = _Harness(now=END)

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.LEASE_NOT_ACTIVE_OR_EXPIRED
    assert harness.capture_calls == 0
    assert harness.settlement_calls == harness.publication_calls == 0


def test_revalidation_detects_lease_or_principal_drift_before_effect_gate_opens() -> (
    None
):
    lease_harness = _Harness(captures=(_capture(Capture.CAPTURE_REQUIRED),))
    lease_harness.revalidation_error = ActivationLeaseVerificationBlocked("expired")
    lease_evidence = _run(lease_harness)
    assert lease_evidence.stop_reason is D10WakeStopReason.LEASE_NOT_ACTIVE_OR_EXPIRED
    assert "capture_gate_open" not in lease_harness.calls

    authority_harness = _Harness(captures=(_capture(Capture.CAPTURE_REQUIRED),))
    authority_harness.revalidation_error = RuntimeError("C1/token changed")
    authority_evidence = _run(authority_harness)
    assert authority_evidence.stop_reason is D10WakeStopReason.AUTHORITY_DRIFT
    assert "capture_gate_open" not in authority_harness.calls


@pytest.mark.parametrize("phase", ["settlement", "publication"])
def test_authority_drift_blocks_before_each_later_effect(phase: str) -> None:
    if phase == "settlement":
        cycles = (_cycle(Cycle.EXECUTION_READY, pending=DECISION_ID),)
        histories = (_history(),)
    else:
        cycles = (
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
        )
        histories = (_history(), _history())
    harness = _Harness(cycles=cycles, histories=histories)
    harness.revalidation_error = RuntimeError("C1 or Trading principal drift")

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.AUTHORITY_DRIFT
    assert harness.settlement_calls == harness.publication_calls == 0
    assert tuple(harness.gates) == (False,) * 8


def test_gate_drift_blocks_before_effect_and_finally_closes_every_gate() -> None:
    harness = _Harness(initially_open_gate=4)

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.EFFECT_GATE_DRIFT
    assert harness.capture_calls == harness.settlement_calls == 0
    assert tuple(harness.gates) == (False,) * 8
    assert evidence.all_effect_gates_closed


@pytest.mark.parametrize(
    ("phase", "expected_reason"),
    [
        ("capture", D10WakeStopReason.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS),
        ("settlement", D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT),
        ("publication", D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT),
    ],
)
def test_exception_after_gate_open_restores_all_gates(
    phase: str, expected_reason: D10WakeStopReason
) -> None:
    capture_results = (
        (
            _capture(Capture.CAPTURE_REQUIRED),
            _capture(
                Capture.CAPTURE_REQUIRED,
                invocation=_invocation("SUCCEEDED", "CONFIRMED"),
            ),
        )
        if phase == "capture"
        else (_capture(),)
    )
    cycles = (
        (
            _cycle(Cycle.EXECUTION_READY, pending=DECISION_ID),
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
        )
        if phase == "settlement"
        else (
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
        )
    )
    harness = _Harness(
        captures=capture_results,
        cycles=cycles,
        histories=(_history(), _history()),
        fail_after_open=phase,
    )

    evidence = _run(harness)

    assert evidence.stop_reason is expected_reason
    assert tuple(harness.gates) == (False,) * 8
    assert evidence.all_effect_gates_closed
    assert harness.calls[-1] == "final_close"
    if phase == "settlement":
        assert "settlement_reconciliation" in harness.calls
    if phase == "publication":
        assert "decision_reconciliation" in harness.calls


def test_settlement_effect_summary_must_match_independent_reconciliation() -> None:
    wrong_effect = replace(_settlement_result(), operation_id=_uuid(99))
    harness = _Harness(
        cycles=(_cycle(Cycle.EXECUTION_READY, pending=DECISION_ID),),
        histories=(_history(),),
        settlement=wrong_effect,
    )

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT
    assert harness.calls.count("settlement_reconciliation") == 1
    assert harness.publication_calls == 0
    assert evidence.all_effect_gates_closed


def test_recovery_required_reconciliation_stops_without_recovery() -> None:
    required = SettlementReconciliationResult(
        SettlementRecon.RECEIPT_RECOVERY_REQUIRED,
        completed_execution_session=SESSION,
        decision_id=DECISION_ID,
        all_eight_gates_closed=True,
    )
    harness = _Harness(
        cycles=(_cycle(Cycle.EXECUTION_READY, pending=DECISION_ID),),
        histories=(_history(),),
        settlement_reconciliation=required,
    )

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.RECEIPT_RECOVERY_REQUIRED
    assert harness.settlement_calls == 1
    assert harness.calls.count("settlement_reconciliation") == 1
    assert evidence.receipt_recovery_attempts == 0
    assert "publish" not in harness.calls
    assert evidence.all_effect_gates_closed


def test_missed_preopen_deadline_skips_publication_and_reconciles_durable_state() -> (
    None
):
    late = datetime(2026, 9, 22, 14, tzinfo=UTC)
    harness = _Harness(
        cycles=(
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
        ),
        histories=(_history(), _history()),
        now=late,
        decision_reconciliation=_decision_reconciliation(
            DecisionRecon.NOT_FINALIZED, finalized=None
        ),
    )

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.MISSED_DECISION_DEADLINE
    assert evidence.preopen_deadline_utc is not None
    assert evidence.publication_attempts == 0
    assert harness.publication_calls == 0
    assert harness.calls.count("decision_reconciliation") == 1


def test_second_cycle_session_gap_stops_without_historical_catch_up() -> None:
    harness = _Harness(
        cycles=(
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
            _cycle(Cycle.SESSION_GAP),
        ),
        histories=(_history(),),
    )

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.SESSION_GAP
    assert harness.calls.count("daily_cycle") == 2
    assert harness.calls.count("historical_audit") == 1
    assert harness.settlement_calls == harness.publication_calls == 0


def test_ambiguous_publication_is_reconciled_once_then_stops() -> None:
    harness = _Harness(
        cycles=(
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
        ),
        histories=(_history(), _history()),
        publication=_publication_result(Publication.PUBLICATION_OUTCOME_AMBIGUOUS),
    )

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.AMBIGUOUS_EFFECT_RESULT
    assert harness.publication_calls == 1
    assert harness.calls.count("decision_reconciliation") == 1
    assert evidence.publication_attempts == 1


def test_decision_reconciliation_session_gap_stops_after_closed_publication_gate() -> (
    None
):
    harness = _Harness(
        cycles=(
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
            _cycle(Cycle.DECISION_READY, next_decision=NEXT_DECISION_ID),
        ),
        histories=(_history(), _history()),
        decision_reconciliation=_decision_reconciliation(
            DecisionRecon.SESSION_GAP, finalized=None
        ),
    )

    evidence = _run(harness)

    assert evidence.stop_reason is D10WakeStopReason.SESSION_GAP
    assert harness.publication_calls == 1
    assert tuple(harness.gates) == (False,) * 8


def test_evidence_is_bounded_sanitized_and_records_zero_recovery_and_live_calls() -> (
    None
):
    harness = _Harness()
    evidence = _run(harness)

    encoded = serialize_d10_wake_evidence(evidence)
    parsed = json.loads(encoded)
    assert len(encoded.encode("utf-8")) <= 16_384
    assert parsed["final_gates"] == {"all_closed": True, "closed_count": 8}
    assert parsed["budgets"]["receipt_recovery_attempts"] == 0
    assert parsed["budgets"]["broker_live_calls"] == 0
    assert parsed["deployment"]["id"] == DEPLOYMENT.deployment_id
    assert parsed["soak"]["id"] == LEASE.soak_id
    assert "credential" not in encoded.lower()
    assert "native_handle" not in encoded.lower()
    assert "authority_object" not in encoded.lower()
    assert "capability" not in encoded.lower()


def test_cumulative_summary_is_read_only_bounded_and_soak_scoped() -> None:
    first = _run(_Harness())
    second_harness = _Harness(now=OBSERVED + timedelta(hours=1))
    second = _run(second_harness)

    summary = build_d10_one_week_wake_summary((first, second))

    assert summary.wake_count == 2
    assert summary.no_action_count == 2
    assert summary.stopped_count == 0
    assert summary.all_effect_gates_closed
    with pytest.raises(ValueError):
        build_d10_one_week_wake_summary((first, first))


def test_gate_drift_and_lease_state_are_not_exposed_in_evidence() -> None:
    harness = _Harness(initially_open_gate=2)
    evidence = _run(harness)
    encoded = serialize_d10_wake_evidence(evidence)

    assert evidence.stop_reason is D10WakeStopReason.EFFECT_GATE_DRIFT
    assert evidence.outcome is D10WakeOutcome.STOPPED
    assert "VerifiedD10ActivationLease" not in encoded
    assert "TradingTokenObservation" not in encoded
