"""D9-R1 independent, read-only proof of one deferred Paper-v2 settlement."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
    inspect_paper_operation_root,
)
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_preparation as preparation,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    derive_checkpointed_verified_snapshot_application_id,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperStrategyPlanArtifactBinding,
    complete_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)
from trading_bot.runtime.paper_operation import (
    PaperOperationReceiptVerificationStatus,
    PaperOperationStatus,
    serialize_paper_operation_receipt,
    verify_paper_operation_receipt,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_historical_cycle_configurations import (
    resolve_personal_desktop_historical_cycle_configurations,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexState,
    paper_receipt_recovery_admission,
    supervised_paper_cycle_admission,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountReadEvidence,
    read_personal_desktop_paper_account,
    require_validated_personal_desktop_paper_account,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationResult,
    PaperReceiptRecoveryQualificationStatus,
    qualify_personal_desktop_paper_receipt_recovery,
    require_validated_paper_receipt_recovery_qualification,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SessionIndexedSelectedC3SnapshotReadResult,
    WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    personal_desktop_unattended_effect_gate_state,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    completed_xnys_session_at,
    next_xnys_execution_session,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PersonalDesktopUnattendedPaperDecisionC3Evidence,
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    SingleDeferredDecisionClassification as Discovery,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    SingleDeferredDecisionResult,
    find_single_deferred_unattended_decision,
    require_single_deferred_unattended_decision,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    create_personal_desktop_unattended_paper_invocation,
    serialize_personal_desktop_unattended_paper_invocation,
    verify_personal_desktop_unattended_paper_invocation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification as Storage,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageReadResult,
    read_personal_desktop_unattended_invocation_storage,
    require_validated_personal_desktop_unattended_invocation_storage_read,
)
from trading_bot.runtime.verified_c3_daily_bar_open import (
    C3VerifiedDailyBarOpenBinding,
    build_c3_verified_daily_bar_open_binding,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)


class DeferredSettlementReconciliationClassification(StrEnum):
    RECONCILED = "RECONCILED"
    NOT_APPLIED = "NOT_APPLIED"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


Status = DeferredSettlementReconciliationClassification
_CLOSED = (False,) * 8


@dataclass(frozen=True, slots=True)
class DeferredSettlementReconciliationResult:
    """Bounded diagnostic evidence; only RECONCILED is acceptance proof."""

    classification: DeferredSettlementReconciliationClassification
    current_completed_session: TradingSession | None = None
    deferred_execution_session: TradingSession | None = None
    decision_selected_session: TradingSession | None = None
    decision_id: UUID | None = None
    decision_selected_snapshot_id: UUID | None = None
    execution_selected_snapshot_id: UUID | None = None
    final_plan_id: UUID | None = None
    invocation_id: UUID | None = None
    operation_id: UUID | None = None
    application_id: UUID | None = None
    predecessor_checkpoint_id: UUID | None = None
    successor_checkpoint_id: UUID | None = None
    invocation_storage_classification: Storage | None = None
    operation_classification: PaperOperationClassification | None = None
    receipt_status: PaperOperationStatus | None = None
    all_eight_gates_closed: bool = False
    real_effect_performed: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not Status
            or any(
                value is not None and type(value) is not TradingSession
                for value in (
                    self.current_completed_session,
                    self.deferred_execution_session,
                    self.decision_selected_session,
                )
            )
            or any(
                value is not None and type(value) is not UUID
                for value in (
                    self.decision_id,
                    self.decision_selected_snapshot_id,
                    self.execution_selected_snapshot_id,
                    self.final_plan_id,
                    self.invocation_id,
                    self.operation_id,
                    self.application_id,
                    self.predecessor_checkpoint_id,
                    self.successor_checkpoint_id,
                )
            )
            or (
                self.invocation_storage_classification is not None
                and type(self.invocation_storage_classification) is not Storage
            )
            or (
                self.operation_classification is not None
                and type(self.operation_classification)
                is not PaperOperationClassification
            )
            or (
                self.receipt_status is not None
                and type(self.receipt_status) is not PaperOperationStatus
            )
            or type(self.all_eight_gates_closed) is not bool
            or self.real_effect_performed is not False
            or (
                self.classification is Status.RECONCILED
                and (
                    not self.all_eight_gates_closed
                    or self.current_completed_session is None
                    or self.deferred_execution_session is None
                    or self.deferred_execution_session >= self.current_completed_session
                    or self.decision_selected_session is None
                    or self.decision_id is None
                    or self.decision_selected_snapshot_id is None
                    or self.execution_selected_snapshot_id is None
                    or self.final_plan_id is None
                    or self.invocation_id is None
                    or self.operation_id is None
                    or self.application_id is None
                    or self.predecessor_checkpoint_id is None
                    or self.successor_checkpoint_id is None
                    or self.invocation_storage_classification
                    is not Storage.FINALIZED_IDENTICAL
                    or self.operation_classification
                    is not PaperOperationClassification.ALREADY_APPLIED
                    or self.receipt_status is not PaperOperationStatus.COMPLETED
                )
            )
        ):
            raise ValueError("D9-R1 reconciliation result is invalid")


@dataclass(frozen=True, slots=True)
class DisposableDeferredSettlementReconciliationDependencies:
    """Read-only disposable seams; the production function takes no arguments."""

    gate_state: Callable[[], tuple[bool, ...]]
    acquire_c1: Callable[[], Any]
    validate_c1: Callable[[Any], Any]
    observe_token: Callable[[], TradingTokenObservation]
    now: Callable[[], datetime]
    discover: Callable[..., SingleDeferredDecisionResult]
    require_discovery: Callable[..., Any]
    read_selected: Callable[..., SessionIndexedSelectedC3SnapshotReadResult]
    require_selected: Callable[..., None]
    build_open: Callable[..., C3VerifiedDailyBarOpenBinding]
    complete_plan: Callable[..., ManualPaperStrategyPlanArtifactBinding]
    verify_plan: Callable[..., ManualPaperStrategyPlanArtifactBinding]
    historical_configurations: Callable[[Any], tuple[bytes, ...]]
    qualify_recovery: Callable[
        [Any, tuple[bytes, ...]], PaperReceiptRecoveryQualificationResult
    ]
    require_recovery: Callable[[PaperReceiptRecoveryQualificationResult], Any]
    read_account: Callable[[Any, tuple[bytes, ...]], Any]
    require_account: Callable[[Any], PersonalDesktopPaperAccountReadEvidence]
    admit_healthy: Callable[[Any], Any]
    admit_recovery: Callable[[PaperReceiptRecoveryQualificationResult], Any]
    build_material: Callable[..., preparation.PreparedPaperOperationMaterial]
    read_storage: Callable[..., PersonalDesktopUnattendedInvocationStorageReadResult]
    require_storage: Callable[
        [PersonalDesktopUnattendedInvocationStorageReadResult], Any
    ]
    inspect_operation: Callable[..., PaperOperationInspectionResult]


@dataclass(frozen=True, slots=True)
class _Expected:
    c1: Any
    token: TradingTokenObservation
    completed: TradingSession
    deferred: TradingSession
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    original: SelectedC3SnapshotReadResult
    execution: SessionIndexedSelectedC3SnapshotReadResult
    plan: ManualPaperStrategyPlanArtifactBinding
    invocation: PersonalDesktopUnattendedPaperInvocationArtifactBinding
    configurations: tuple[bytes, ...]


def reconcile_personal_desktop_single_deferred_settlement() -> (
    DeferredSettlementReconciliationResult
):
    """Reconcile the sole deferred settlement from durable source-owned truth."""

    try:
        return _run(_production_dependencies())
    except Exception:
        return DeferredSettlementReconciliationResult(Status.BLOCKED)


def reconcile_personal_desktop_single_deferred_settlement_for_test(
    dependencies: DisposableDeferredSettlementReconciliationDependencies,
) -> DeferredSettlementReconciliationResult:
    """Exercise the boundary with disposable read-only evidence."""

    if type(dependencies) is not DisposableDeferredSettlementReconciliationDependencies:
        raise TypeError("D9-R1 disposable dependencies are invalid")
    return _run(dependencies)


def _require_gates(d: DisposableDeferredSettlementReconciliationDependencies) -> None:
    gates = d.gate_state()
    if (
        type(gates) is not tuple
        or gates != _CLOSED
        or any(type(value) is not bool for value in gates)
    ):
        raise ValueError("D9-R1 requires all eight exact-boolean gates closed")


def _token(
    d: DisposableDeferredSettlementReconciliationDependencies,
) -> TradingTokenObservation:
    observation = d.observe_token()
    require_trading_token(
        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
        observation,
    )
    return observation


def _final_authority(
    d: DisposableDeferredSettlementReconciliationDependencies, expected: _Expected
) -> None:
    _require_gates(d)
    if d.validate_c1(d.acquire_c1()) != expected.c1 or _token(d) != expected.token:
        raise ValueError("D9-R1 C1 or Trading token changed")
    _require_gates(d)


def _selected(
    d: DisposableDeferredSettlementReconciliationDependencies,
    c1: Any,
    session: TradingSession,
) -> SessionIndexedSelectedC3SnapshotReadResult:
    result = d.read_selected(c1, session)
    if (
        type(result) is not SessionIndexedSelectedC3SnapshotReadResult
        or result.session != session
    ):
        raise ValueError("D9-R1 selected C3 session is invalid")
    d.require_selected(c1, result)
    return result


def _require_c3(
    expected: PersonalDesktopUnattendedPaperDecisionC3Evidence,
    actual: SessionIndexedSelectedC3SnapshotReadResult,
) -> None:
    audit = actual.selected.audit
    if (
        actual.session != expected.selected_session
        or actual.selected.snapshot_bytes != expected.snapshot_artifact
        or audit.selection_id != expected.selection_id
        or audit.session_id != expected.session_id
        or audit.terminal_id != expected.terminal_id
        or audit.snapshot_id != expected.snapshot_id
        or audit.artifact_sha256 != expected.artifact_sha256
        or audit.artifact_byte_length != expected.artifact_byte_length
    ):
        raise ValueError("D9-R1 selected C3 differs from finalized decision")


def _require_plan(
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    execution: SessionIndexedSelectedC3SnapshotReadResult,
    opened: C3VerifiedDailyBarOpenBinding,
    plan_binding: ManualPaperStrategyPlanArtifactBinding,
    d: DisposableDeferredSettlementReconciliationDependencies,
) -> None:
    if type(plan_binding) is not ManualPaperStrategyPlanArtifactBinding:
        raise TypeError("D9-R1 plan binding is invalid")
    replayed = d.verify_plan(
        plan_binding.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_sha256=plan_binding.artifact_sha256,
        expected_byte_length=plan_binding.artifact_byte_length,
        expected_checkpointed_request=plan_binding.checkpointed_request,
    )
    decision = binding.decision
    prepared = decision.prepared_decision
    plan = plan_binding.plan
    references = plan.request_core.open_references
    if (
        replayed != plan_binding
        or plan.paper_account_id != decision.paper_account_id
        or plan.paper_account_id
        != PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.paper_account_id
        or plan.prior_checkpoint != prepared.prior_checkpoint
        or plan.prior_checkpoint.checkpoint_id != decision.predecessor_checkpoint_id
        or plan.selected_snapshot_artifact != decision.current_c3.snapshot_artifact
        or plan.selected_c3_assertion != prepared.selected_c3_assertion
        or plan.history_seed_artifact != prepared.history_seed_artifact
        or plan.strategy_config != prepared.strategy_config
        or plan.caller_idempotency_key != prepared.caller_idempotency_key
        or plan.strategy_run_id != prepared.strategy_run_id
        or plan.strategy_step_index != prepared.strategy_step_index
        or plan.signal_status != prepared.signal_status
        or plan.strategy_proposal != prepared.strategy_proposal
        or plan.target != prepared.target
        or len(references) != 1
        or references[0].symbol != opened.symbol
        or references[0].session != opened.session
        or references[0].caller_asserted_open_reference_price != opened.open_price
        or opened.session != decision.intended_execution_session
        or execution.session != opened.session
    ):
        raise ValueError("D9-R1 final plan differs from verified decision/open")


def _reconstruct(
    d: DisposableDeferredSettlementReconciliationDependencies,
) -> _Expected:
    # No durable read precedes these four source-owned admission facts.
    _require_gates(d)
    token = _token(d)
    c1 = d.validate_c1(d.acquire_c1())
    completed = completed_xnys_session_at(d.now())
    discovery = d.discover(c1)
    if (
        type(discovery) is not SingleDeferredDecisionResult
        or discovery.current_completed_session != completed
        or discovery.execution_session is None
        or discovery.execution_session >= completed
        or discovery.classification is not Discovery.FINALIZED
    ):
        raise ValueError("D9-R1 lacks one exact finalized decision")
    binding = d.require_discovery(c1, discovery)
    if (
        binding is not discovery.binding
        or type(binding)
        is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    ):
        raise ValueError("D9-R1 lacks current-C1 decision discovery provenance")
    replayed = verify_personal_desktop_unattended_paper_decision_intent(
        binding.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_decision_id=discovery.decision_id,
        expected_artifact_sha256=binding.artifact_sha256,
        expected_artifact_byte_length=binding.artifact_byte_length,
    )
    if (
        replayed != binding
        or binding.decision.intended_execution_session != discovery.execution_session
    ):
        raise ValueError("D9-R1 finalized decision is inconsistent")
    decision = binding.decision
    execution = _selected(d, c1, discovery.execution_session)
    original = _selected(d, c1, decision.selected_session)
    _require_c3(decision.current_c3, original)
    if not decision.history_c3:
        raise ValueError("D9-R1 selected C3 history is empty")
    cursor = decision.history_c3[0].selected_session
    for item in decision.history_c3:
        if item.selected_session != cursor:
            raise ValueError("D9-R1 selected C3 history order has a gap")
        _require_c3(item, _selected(d, c1, cursor))
        cursor = next_xnys_execution_session(cursor)
    if cursor != decision.selected_session:
        raise ValueError("D9-R1 selected C3 history does not end at decision session")
    opened = d.build_open(execution.selected, c1)
    if type(opened) is not C3VerifiedDailyBarOpenBinding:
        raise TypeError("D9-R1 verified C3 open binding is invalid")
    plan = d.complete_plan(
        decision.prepared_decision,
        opened,
        personal_desktop_unattended_decision_calendar(),
    )
    _require_plan(binding, execution, opened, plan, d)
    invocation_model = create_personal_desktop_unattended_paper_invocation(
        plan, personal_desktop_unattended_decision_calendar()
    )
    invocation = verify_personal_desktop_unattended_paper_invocation(
        serialize_personal_desktop_unattended_paper_invocation(invocation_model),
        personal_desktop_unattended_decision_calendar(),
        expected_invocation_id=invocation_model.invocation_id,
    )
    if (
        type(invocation) is not PersonalDesktopUnattendedPaperInvocationArtifactBinding
        or invocation.invocation != invocation_model
        or invocation.replayed_plan != plan
        or invocation.invocation.plan_artifact != plan.artifact_bytes
        or invocation.invocation.predecessor_checkpoint_id
        != decision.predecessor_checkpoint_id
        or invocation.invocation.execution_session != discovery.execution_session
        or invocation.invocation.selected_snapshot_id != decision.current_c3.snapshot_id
    ):
        raise ValueError(
            "D9-R1 invocation differs from independently reconstructed plan"
        )
    historical = d.historical_configurations(c1)
    if type(historical) is not tuple or any(
        type(item) is not bytes for item in historical
    ):
        raise TypeError("D9-R1 historical configuration payloads are invalid")
    expected = _Expected(
        c1,
        token,
        completed,
        discovery.execution_session,
        binding,
        original.selected,
        execution,
        plan,
        invocation,
        historical,
    )
    _final_authority(d, expected)
    return expected


def _recovery_signature(
    result: PaperReceiptRecoveryQualificationResult,
) -> tuple[object, ...]:
    if type(result) is not PaperReceiptRecoveryQualificationResult:
        raise TypeError("D9-R1 recovery qualification result is invalid")
    result.__post_init__()
    return (
        result.status,
        result.paper_account_id,
        result.terminal_checkpoint_id,
        result.missing_application_id,
        result.predecessor_checkpoint_id,
    )


def _account(
    d: DisposableDeferredSettlementReconciliationDependencies,
    expected: _Expected,
    recovery: PaperReceiptRecoveryQualificationResult,
) -> tuple[Any, PersonalDesktopPaperAccountReadEvidence]:
    if (
        recovery.status
        is PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
    ):
        registered = d.require_recovery(recovery)
        account = registered.account
        if (
            registered.missing_application_id != recovery.missing_application_id
            or registered.missing_predecessor_checkpoint_id
            != recovery.predecessor_checkpoint_id
        ):
            raise ValueError("D9-R1 recovery provenance differs")
        return recovery, account
    if (
        recovery.status
        is not PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
    ):
        raise ValueError("D9-R1 account recovery qualification is blocked")
    authority = d.read_account(expected.c1, expected.configurations)
    account = d.require_account(authority)
    return authority, account


def _storage(
    d: DisposableDeferredSettlementReconciliationDependencies, expected: _Expected
) -> PersonalDesktopUnattendedInvocationStorageReadResult:
    result = d.read_storage(expected.c1, expected.invocation)
    if type(result) is not PersonalDesktopUnattendedInvocationStorageReadResult:
        raise TypeError("D9-R1 invocation storage result is invalid")
    result.__post_init__()
    if result.classification not in {Storage.ABSENT, Storage.FINALIZED_IDENTICAL}:
        raise ValueError("D9-R1 invocation storage is ambiguous")
    proof = d.require_storage(result)
    if (
        proof.authority is not expected.c1
        or proof.expected != expected.invocation
        or proof.classification is not result.classification
        or result.finalized_invocation_count != len(proof.finalized)
        or result.expected_invocation_id != expected.invocation.invocation.invocation_id
        or any(
            item != expected.invocation
            and item.invocation.execution_session == expected.deferred
            for item in proof.finalized
        )
        or (
            result.classification is Storage.FINALIZED_IDENTICAL
            and (
                result.matching_invocation_id != result.expected_invocation_id
                or sum(item == expected.invocation for item in proof.finalized) != 1
            )
        )
    ):
        raise ValueError("D9-R1 invocation storage lacks exact current-C1 provenance")
    return result


def _storage_signature(
    result: PersonalDesktopUnattendedInvocationStorageReadResult,
) -> tuple[object, ...]:
    return (
        result.classification,
        result.expected_invocation_id,
        result.finalized_invocation_count,
        result.matching_invocation_id,
        result.diagnostic,
    )


def _inspection(
    d: DisposableDeferredSettlementReconciliationDependencies,
    material: preparation.PreparedPaperOperationMaterial,
) -> PaperOperationInspectionResult:
    result = d.inspect_operation(
        Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME), material.execution_inputs
    )
    intent = material.execution_inputs.intent
    if (
        type(result) is not PaperOperationInspectionResult
        or result.operation_id != intent.operation_id
        or result.application_id != material.execution_inputs.application_id
        or result.terminal_checkpoint_id
        != intent.prior_lineage_evidence.terminal_checkpoint_id
    ):
        raise ValueError("D9-R1 inspection differs from expected A67 inputs")
    result.__post_init__()
    return result


def _completed_receipt(
    account: PersonalDesktopPaperAccountReadEvidence,
    material: preparation.PreparedPaperOperationMaterial,
) -> tuple[PaperOperationStatus, UUID]:
    inputs = material.execution_inputs
    intent = inputs.intent
    matches = tuple(
        receipt
        for receipt in account.receipts
        if receipt.receipt_id == intent.operation_id
        or receipt.application_id == inputs.application_id
    )
    if len(matches) != 1:
        raise ValueError("D9-R1 expected receipt is absent or ambiguous")
    receipt = matches[0]
    prior = intent.prior_lineage_evidence
    full = account.lineage
    index = prior.edge_count
    if (
        receipt.status is not PaperOperationStatus.COMPLETED
        or receipt.receipt_id != intent.operation_id
        or receipt.intent != intent
        or receipt.application_id != inputs.application_id
        or receipt.prior_lineage_evidence != prior
        or receipt.successor_lineage_evidence != full
        or full.edge_count != index + 1
        or full.checkpoint_ids[: index + 1] != prior.checkpoint_ids
        or full.application_ids[index] != inputs.application_id
        or receipt.successor_checkpoint_artifact != full.checkpoint_artifacts[index + 1]
        or receipt.transition_report_artifact != full.report_artifacts[index]
        or account.prior_checkpoint.checkpoint_id != full.terminal_checkpoint_id
    ):
        raise ValueError("D9-R1 receipt or current account successor differs")
    verified = verify_paper_operation_receipt(
        serialize_paper_operation_receipt(receipt),
        cycle_configuration_payload=inputs.cycle_configuration_payload,
        prior_genesis_checkpoint=inputs.prior_genesis_checkpoint,
        prior_successor_checkpoints=inputs.prior_successor_checkpoints,
        prior_cycle_reports=inputs.prior_cycle_reports,
        prior_snapshots=inputs.prior_snapshots,
        completed_snapshot_payload=inputs.completed_snapshot_payload,
        calendar=inputs.calendar,
        transition_report_payload=account.reports[index].payload,
        successor_checkpoint_payload=account.successors[index].payload,
    )
    if (
        verified.status is not PaperOperationReceiptVerificationStatus.PASS
        or verified.diagnostics
        or verified.receipt != receipt
        or receipt.successor_lineage_evidence.terminal_checkpoint_id
        != account.lineage.terminal_checkpoint_id
    ):
        raise ValueError("D9-R1 exact completed receipt does not reverify")
    return receipt.status, full.terminal_checkpoint_id


def _result(
    status: Status,
    expected: _Expected,
    storage: PersonalDesktopUnattendedInvocationStorageReadResult,
    inspection: PaperOperationInspectionResult,
    *,
    successor: UUID | None = None,
    receipt: PaperOperationStatus | None = None,
) -> DeferredSettlementReconciliationResult:
    decision = expected.binding.decision
    inputs_id = inspection.operation_id
    return DeferredSettlementReconciliationResult(
        status,
        expected.completed,
        expected.deferred,
        decision.selected_session,
        decision.decision_id,
        decision.current_c3.snapshot_id,
        expected.execution.selected.audit.snapshot_id,
        expected.plan.plan.plan_id,
        expected.invocation.invocation.invocation_id,
        inputs_id,
        inspection.application_id,
        decision.predecessor_checkpoint_id,
        successor,
        storage.classification,
        inspection.classification,
        receipt,
        True,
        False,
    )


def _run(
    d: DisposableDeferredSettlementReconciliationDependencies,
) -> DeferredSettlementReconciliationResult:
    try:
        expected = _reconstruct(d)
        decision = expected.binding.decision
        predecessor = decision.predecessor_checkpoint_id
        application = derive_checkpointed_verified_snapshot_application_id(
            predecessor, expected.plan.checkpointed_request.request_id
        )
        pre_recovery = d.qualify_recovery(expected.c1, expected.configurations)
        _recovery_signature(pre_recovery)
        pre_authority, pre_account = _account(d, expected, pre_recovery)
        if (
            pre_account.anchor.paper_account_id != decision.paper_account_id
            or pre_recovery.paper_account_id != decision.paper_account_id
        ):
            raise ValueError("D9-R1 prelock account identity differs from decision")
        recovering = (
            pre_recovery.status
            is PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
        )
        admission = (
            d.admit_recovery(pre_recovery)
            if recovering
            else d.admit_healthy(pre_authority)
        )
        with admission as held:
            acquisition = held.acquisition
            if (
                acquisition is None
                or acquisition.state is not PaperAccountMutexState.OWNED
                or acquisition.paper_account_id != decision.paper_account_id
            ):
                raise ValueError("D9-R1 PD2A mutex admission is not exact")
            _final_authority(d, expected)
            post_recovery = d.qualify_recovery(expected.c1, expected.configurations)
            if _recovery_signature(post_recovery) != _recovery_signature(pre_recovery):
                raise ValueError("D9-R1 account recovery state drifted under mutex")
            _, post_account = _account(d, expected, post_recovery)
            if post_account != pre_account:
                raise ValueError(
                    "D9-R1 account lineage or identity drifted before mutex"
                )
            if recovering and (
                post_recovery.predecessor_checkpoint_id != predecessor
                or post_recovery.missing_application_id != application
                or post_account.lineage.checkpoint_ids[-2:]
                != (predecessor, post_account.lineage.terminal_checkpoint_id)
                or post_account.lineage.application_ids[-1] != application
            ):
                raise ValueError("D9-R1 recovery is unrelated to exact settlement")
            material = d.build_material(
                post_account,
                expected.original,
                expected.plan,
                personal_desktop_unattended_decision_calendar(),
            )
            if (
                type(material) is not preparation.PreparedPaperOperationMaterial
                or material.plan_binding != expected.plan
                or (
                    material.execution_inputs.intent.prior_lineage_evidence.terminal_checkpoint_id
                    != predecessor
                )
                or material.execution_inputs.application_id != application
            ):
                raise ValueError("D9-R1 predecessor material differs from exact plan")
            storage = _storage(d, expected)
            inspection = _inspection(d, material)
            status: Status
            successor: UUID | None = None
            receipt_status: PaperOperationStatus | None = None
            if recovering:
                if (
                    storage.classification is not Storage.FINALIZED_IDENTICAL
                    or inspection.classification
                    is not PaperOperationClassification.BLOCKED
                    or inspection.diagnostics
                    != (
                        PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT,
                    )
                    or inspection.receipt_path is not None
                ):
                    raise ValueError("D9-R1 exact missing receipt is not proven")
                status = Status.RECEIPT_RECOVERY_REQUIRED
                successor = post_account.lineage.terminal_checkpoint_id
            elif inspection.classification is PaperOperationClassification.PENDING:
                if (
                    inspection.diagnostics != (PaperOperationInspectionCode.PENDING,)
                    or inspection.receipt_path is not None
                    or post_account.lineage.terminal_checkpoint_id != predecessor
                    or any(
                        receipt.application_id == application
                        for receipt in post_account.receipts
                    )
                ):
                    raise ValueError("D9-R1 pending operation contradicts account")
                status = Status.NOT_APPLIED
            elif (
                inspection.classification
                is PaperOperationClassification.ALREADY_APPLIED
            ):
                if (
                    storage.classification is not Storage.FINALIZED_IDENTICAL
                    or inspection.diagnostics
                    != (PaperOperationInspectionCode.ALREADY_APPLIED,)
                    or inspection.receipt_path is None
                ):
                    raise ValueError(
                        "D9-R1 applied operation lacks exact invocation or receipt"
                    )
                receipt_status, successor = _completed_receipt(post_account, material)
                status = Status.RECONCILED
            else:
                raise ValueError("D9-R1 operation is conflicting or blocked")
            final_recovery = d.qualify_recovery(expected.c1, expected.configurations)
            if _recovery_signature(final_recovery) != _recovery_signature(
                post_recovery
            ):
                raise ValueError("D9-R1 final recovery state drifted")
            _, final_account = _account(d, expected, final_recovery)
            if final_account != post_account:
                raise ValueError("D9-R1 final account lineage or tip drifted")
            if (
                _storage_signature(_storage(d, expected)) != _storage_signature(storage)
                or _inspection(d, material) != inspection
            ):
                raise ValueError("D9-R1 final invocation or operation drifted")
            _final_authority(d, expected)
            return _result(
                status,
                expected,
                storage,
                inspection,
                successor=successor,
                receipt=receipt_status,
            )
    except Exception:
        try:
            _require_gates(d)
            closed = True
        except Exception:
            closed = False
        return DeferredSettlementReconciliationResult(
            Status.BLOCKED, all_eight_gates_closed=closed
        )


def _production_dependencies() -> (
    DisposableDeferredSettlementReconciliationDependencies
):
    retained_readers: list[WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority] = []
    observer = WindowsTradingTokenObserver()

    def read_selected(
        c1: Any, session: TradingSession
    ) -> SessionIndexedSelectedC3SnapshotReadResult:
        reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(c1)
        retained_readers.append(reader)
        return reader.read_selected_snapshot_for_session(session)

    def require_selected(
        c1: Any, selected: SessionIndexedSelectedC3SnapshotReadResult
    ) -> None:
        require_selected_c3_snapshot_matches_authority(
            selected.selected.permit,
            selected.selected.audit,
            require_validated_production_authority(c1),
        )

    def discover(c1: Any) -> SingleDeferredDecisionResult:
        return find_single_deferred_unattended_decision(c1)

    def require_discovery(c1: Any, result: SingleDeferredDecisionResult) -> Any:
        binding = require_single_deferred_unattended_decision(result, c1)
        if binding is not result.binding:
            raise ValueError("D9-R1 discovery lacks current-C1 provenance")
        return binding

    def qualify_recovery(
        c1: Any, configurations: tuple[bytes, ...]
    ) -> PaperReceiptRecoveryQualificationResult:
        return qualify_personal_desktop_paper_receipt_recovery(
            c1, historical_cycle_configuration_payloads=configurations
        )

    def read_account(c1: Any, configurations: tuple[bytes, ...]) -> Any:
        return read_personal_desktop_paper_account(
            c1, historical_cycle_configuration_payloads=configurations
        )

    return DisposableDeferredSettlementReconciliationDependencies(
        gate_state=personal_desktop_unattended_effect_gate_state,
        acquire_c1=acquire_validated_production_authority,
        validate_c1=require_validated_production_authority,
        observe_token=observer.observe,
        now=lambda: datetime.now(UTC),
        discover=discover,
        require_discovery=require_discovery,
        read_selected=read_selected,
        require_selected=require_selected,
        build_open=build_c3_verified_daily_bar_open_binding,
        complete_plan=complete_manual_paper_strategy_plan,
        verify_plan=verify_manual_paper_strategy_plan,
        historical_configurations=resolve_personal_desktop_historical_cycle_configurations,
        qualify_recovery=qualify_recovery,
        require_recovery=require_validated_paper_receipt_recovery_qualification,
        read_account=read_account,
        require_account=require_validated_personal_desktop_paper_account,
        admit_healthy=supervised_paper_cycle_admission,
        admit_recovery=paper_receipt_recovery_admission,
        build_material=preparation.reconstruct_verified_paper_operation_from_predecessor_prefix,
        read_storage=read_personal_desktop_unattended_invocation_storage,
        require_storage=require_validated_personal_desktop_unattended_invocation_storage_read,
        inspect_operation=inspect_paper_operation_root,
    )
