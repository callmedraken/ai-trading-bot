"""Read-only Architecture-122 audit of retained historical settlement decisions."""

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
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
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
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    CompleteDecisionNamespaceClassification,
    CompleteDecisionNamespaceResult,
    FinalizedDecisionIdentity,
    read_complete_personal_desktop_unattended_decision_namespace,
    require_complete_personal_desktop_unattended_decision_namespace,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
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
    build_c3_verified_daily_bar_open_binding,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)


class HistoricalSettlementAuditClassification(StrEnum):
    RECONCILED_HISTORY = "RECONCILED_HISTORY"
    STALE_UNRESOLVED_DECISION = "STALE_UNRESOLVED_DECISION"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class HistoricalSettlementAuditResult:
    """Bounded identifiers only; never exposes durable artifacts or authority."""

    classification: HistoricalSettlementAuditClassification
    completed_session: TradingSession | None = None
    reconciled_decision_ids: tuple[UUID, ...] = ()
    current_decision_id: UUID | None = None
    unresolved_decision_id: UUID | None = None
    all_eight_gates_closed: bool = False
    real_effect_performed: bool = False

    def __post_init__(self) -> None:
        status = HistoricalSettlementAuditClassification
        if (
            type(self.classification) is not status
            or (
                self.completed_session is not None
                and type(self.completed_session) is not TradingSession
            )
            or type(self.reconciled_decision_ids) is not tuple
            or any(type(item) is not UUID for item in self.reconciled_decision_ids)
            or len(set(self.reconciled_decision_ids))
            != len(self.reconciled_decision_ids)
            or any(
                item is not None and type(item) is not UUID
                for item in (self.current_decision_id, self.unresolved_decision_id)
            )
            or type(self.all_eight_gates_closed) is not bool
            or self.real_effect_performed is not False
            or (
                self.classification is status.RECONCILED_HISTORY
                and (
                    self.completed_session is None
                    or not self.all_eight_gates_closed
                    or self.unresolved_decision_id is not None
                )
            )
            or (
                self.classification is status.STALE_UNRESOLVED_DECISION
                and (
                    self.completed_session is None
                    or self.unresolved_decision_id is None
                )
            )
            or (
                self.classification is status.BLOCKED
                and (
                    self.reconciled_decision_ids
                    or self.current_decision_id
                    or self.unresolved_decision_id
                )
            )
        ):
            raise ValueError("historical settlement audit result is invalid")


@dataclass(frozen=True, slots=True)
class DisposableHistoricalSettlementAuditDependencies:
    """Disposable read-only seams; production entry point takes no arguments."""

    gate_state: Callable[[], tuple[bool, ...]]
    acquire_c1: Callable[[], Any]
    validate_c1: Callable[[Any], Any]
    observe_token: Callable[[], TradingTokenObservation]
    now: Callable[[], datetime]
    discover: Callable[[Any], CompleteDecisionNamespaceResult]
    require_discovery: Callable[[CompleteDecisionNamespaceResult, Any], tuple[Any, ...]]
    read_selected: Callable[
        [Any, TradingSession], SessionIndexedSelectedC3SnapshotReadResult
    ]
    require_selected: Callable[[Any, SessionIndexedSelectedC3SnapshotReadResult], None]
    build_open: Callable[..., Any]
    complete_plan: Callable[..., Any]
    verify_plan: Callable[..., Any]
    historical_configurations: Callable[[Any], tuple[bytes, ...]]
    read_account: Callable[[Any, tuple[bytes, ...]], Any]
    require_account: Callable[[Any], PersonalDesktopPaperAccountReadEvidence]
    build_material: Callable[..., preparation.PreparedPaperOperationMaterial]
    read_storage: Callable[..., Any]
    require_storage: Callable[[Any], Any]
    inspect_operation: Callable[..., PaperOperationInspectionResult]


def audit_personal_desktop_historical_settlements() -> HistoricalSettlementAuditResult:
    """Independently classify all prior finalized decisions without effects."""

    return _audit(_production_dependencies())


def audit_personal_desktop_historical_settlements_for_test(
    dependencies: DisposableHistoricalSettlementAuditDependencies,
) -> HistoricalSettlementAuditResult:
    if type(dependencies) is not DisposableHistoricalSettlementAuditDependencies:
        raise TypeError("D10 disposable dependencies are invalid")
    return _audit(dependencies)


def _closed(d: DisposableHistoricalSettlementAuditDependencies) -> None:
    state = d.gate_state()
    if (
        type(state) is not tuple
        or state != (False,) * 8
        or any(type(item) is not bool for item in state)
    ):
        raise ValueError("D10 audit requires eight exact-boolean closed gates")


def _authority(
    d: DisposableHistoricalSettlementAuditDependencies,
    c1: Any,
    token: TradingTokenObservation,
) -> None:
    _closed(d)
    if d.validate_c1(d.acquire_c1()) != c1 or d.observe_token() != token:
        raise ValueError("C1 or Trading token changed")
    _closed(d)


def _selected(
    d: DisposableHistoricalSettlementAuditDependencies, c1: Any, session: TradingSession
) -> SessionIndexedSelectedC3SnapshotReadResult:
    result = d.read_selected(c1, session)
    if (
        type(result) is not SessionIndexedSelectedC3SnapshotReadResult
        or result.session != session
    ):
        raise ValueError("selected C3 session differs")
    d.require_selected(c1, result)
    return result


def _match_c3(
    expected: Any, result: SessionIndexedSelectedC3SnapshotReadResult
) -> None:
    audit = result.selected.audit
    if (
        result.session != expected.selected_session
        or result.selected.snapshot_bytes != expected.snapshot_artifact
        or audit.selection_id != expected.selection_id
        or audit.session_id != expected.session_id
        or audit.terminal_id != expected.terminal_id
        or audit.snapshot_id != expected.snapshot_id
        or audit.artifact_sha256 != expected.artifact_sha256
        or audit.artifact_byte_length != expected.artifact_byte_length
    ):
        raise ValueError("decision C3 differs from current authority")


def _inventory(
    d: DisposableHistoricalSettlementAuditDependencies, c1: Any
) -> tuple[
    CompleteDecisionNamespaceResult,
    tuple[PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding, ...],
]:
    result = d.discover(c1)
    if (
        type(result) is not CompleteDecisionNamespaceResult
        or result.classification is not CompleteDecisionNamespaceClassification.VALID
    ):
        raise ValueError("complete decision namespace is blocked")
    result.__post_init__()
    bindings = d.require_discovery(result, c1)
    if (
        type(bindings) is not tuple
        or any(
            type(item)
            is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
            for item in bindings
        )
        or result.decisions
        != tuple(
            FinalizedDecisionIdentity(
                item.decision.intended_execution_session, item.decision.decision_id
            )
            for item in bindings
        )
    ):
        raise ValueError("complete decision inventory lacks provenance")
    return result, bindings


def _reconcile_one(
    d: DisposableHistoricalSettlementAuditDependencies,
    c1: Any,
    binding: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    account: PersonalDesktopPaperAccountReadEvidence,
) -> None:
    calendar = personal_desktop_unattended_decision_calendar()
    decision = binding.decision
    replayed = verify_personal_desktop_unattended_paper_decision_intent(
        binding.artifact_bytes,
        calendar,
        expected_decision_id=decision.decision_id,
        expected_artifact_sha256=binding.artifact_sha256,
        expected_artifact_byte_length=binding.artifact_byte_length,
    )
    if replayed != binding or not decision.history_c3:
        raise ValueError("finalized decision replay differs")
    cursor = decision.history_c3[0].selected_session
    for item in decision.history_c3:
        if item.selected_session != cursor:
            raise ValueError("decision C3 history gap")
        _match_c3(item, _selected(d, c1, cursor))
        cursor = next_xnys_execution_session(cursor)
    if cursor != decision.selected_session:
        raise ValueError("decision history does not end at selected session")
    original = _selected(d, c1, decision.selected_session)
    _match_c3(decision.current_c3, original)
    execution = _selected(d, c1, decision.intended_execution_session)
    opened = d.build_open(execution.selected, c1)
    plan = d.complete_plan(decision.prepared_decision, opened, calendar)
    if (
        d.verify_plan(
            plan.artifact_bytes,
            calendar,
            expected_sha256=plan.artifact_sha256,
            expected_byte_length=plan.artifact_byte_length,
            expected_checkpointed_request=plan.checkpointed_request,
        )
        != plan
    ):
        raise ValueError("completed plan does not reverify")
    prepared = decision.prepared_decision
    model = plan.plan
    references = model.request_core.open_references
    if (
        model.paper_account_id != decision.paper_account_id
        or model.paper_account_id != account.anchor.paper_account_id
        or model.paper_account_id
        != PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.paper_account_id
        or model.prior_checkpoint != prepared.prior_checkpoint
        or model.prior_checkpoint.checkpoint_id != decision.predecessor_checkpoint_id
        or model.selected_snapshot_artifact != decision.current_c3.snapshot_artifact
        or model.selected_c3_assertion != prepared.selected_c3_assertion
        or model.history_seed_artifact != prepared.history_seed_artifact
        or model.strategy_config != prepared.strategy_config
        or model.caller_idempotency_key != prepared.caller_idempotency_key
        or model.strategy_run_id != prepared.strategy_run_id
        or model.strategy_step_index != prepared.strategy_step_index
        or model.signal_status != prepared.signal_status
        or model.strategy_proposal != prepared.strategy_proposal
        or model.target != prepared.target
        or len(references) != 1
        or references[0].symbol != opened.symbol
        or references[0].session != opened.session
        or references[0].caller_asserted_open_reference_price != opened.open_price
        or opened.session != decision.intended_execution_session
    ):
        raise ValueError("historical final plan differs")
    invocation_model = create_personal_desktop_unattended_paper_invocation(
        plan, calendar
    )
    invocation = verify_personal_desktop_unattended_paper_invocation(
        serialize_personal_desktop_unattended_paper_invocation(invocation_model),
        calendar,
        expected_invocation_id=invocation_model.invocation_id,
    )
    if (
        invocation.invocation != invocation_model
        or invocation.replayed_plan != plan
        or invocation.invocation.predecessor_checkpoint_id
        != decision.predecessor_checkpoint_id
        or invocation.invocation.execution_session
        != decision.intended_execution_session
        or invocation.invocation.selected_snapshot_id != decision.current_c3.snapshot_id
    ):
        raise ValueError("historical invocation differs")
    material = d.build_material(account, original.selected, plan, calendar)
    if (
        type(material) is not preparation.PreparedPaperOperationMaterial
        or material.plan_binding != plan
    ):
        raise ValueError("historical operation material differs")
    inputs = material.execution_inputs
    application = derive_checkpointed_verified_snapshot_application_id(
        decision.predecessor_checkpoint_id, plan.checkpointed_request.request_id
    )
    if (
        inputs.intent.prior_lineage_evidence.terminal_checkpoint_id
        != decision.predecessor_checkpoint_id
        or inputs.application_id != application
    ):
        raise ValueError("historical operation identity differs")
    storage = d.read_storage(c1, invocation)
    if (
        type(storage) is not PersonalDesktopUnattendedInvocationStorageReadResult
        or storage.classification is not Storage.FINALIZED_IDENTICAL
    ):
        raise ValueError("historical invocation is not finalized-identical")
    storage.__post_init__()
    proof = d.require_storage(storage)
    if (
        proof.authority is not c1
        or proof.expected != invocation
        or proof.classification is not Storage.FINALIZED_IDENTICAL
        or storage.expected_invocation_id != invocation_model.invocation_id
        or storage.matching_invocation_id != invocation_model.invocation_id
        or storage.finalized_invocation_count != len(proof.finalized)
        or sum(item == invocation for item in proof.finalized) != 1
        or any(
            item != invocation
            and item.invocation.execution_session == decision.intended_execution_session
            for item in proof.finalized
        )
    ):
        raise ValueError("historical invocation storage lacks exact provenance")
    inspection = d.inspect_operation(Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME), inputs)
    _require_applied_inspection(
        inspection,
        inputs.intent.operation_id,
        application,
        decision.predecessor_checkpoint_id,
    )
    _verify_historical_receipt(account, inputs)
    final_storage = d.read_storage(c1, invocation)
    final_storage_proof = d.require_storage(final_storage)
    if (
        type(final_storage) is not PersonalDesktopUnattendedInvocationStorageReadResult
        or _storage_signature(final_storage) != _storage_signature(storage)
        or final_storage_proof.authority is not c1
        or final_storage_proof.expected != invocation
        or final_storage_proof.classification is not Storage.FINALIZED_IDENTICAL
        or final_storage_proof.finalized != proof.finalized
        or d.inspect_operation(Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME), inputs)
        != inspection
    ):
        raise ValueError("historical operation or invocation changed during audit")


def _storage_signature(
    result: PersonalDesktopUnattendedInvocationStorageReadResult,
) -> tuple[object, ...]:
    result.__post_init__()
    return (
        result.classification,
        result.expected_invocation_id,
        result.finalized_invocation_count,
        result.matching_invocation_id,
        result.diagnostic,
    )


def _require_applied_inspection(
    inspection: PaperOperationInspectionResult,
    operation_id: UUID,
    application_id: UUID,
    predecessor_checkpoint_id: UUID,
) -> None:
    if (
        type(inspection) is not PaperOperationInspectionResult
        or inspection.classification is not PaperOperationClassification.ALREADY_APPLIED
        or inspection.diagnostics != (PaperOperationInspectionCode.ALREADY_APPLIED,)
        or inspection.receipt_path is None
        or inspection.operation_id != operation_id
        or inspection.application_id != application_id
        or inspection.terminal_checkpoint_id != predecessor_checkpoint_id
    ):
        raise ValueError("historical operation is not already applied")


def _verify_historical_receipt(
    account: PersonalDesktopPaperAccountReadEvidence, inputs: Any
) -> None:
    application = inputs.application_id
    prior = inputs.intent.prior_lineage_evidence
    index = prior.edge_count
    full = account.lineage
    matches = tuple(
        receipt
        for receipt in account.receipts
        if receipt.receipt_id == inputs.intent.operation_id
        or receipt.application_id == application
    )
    if (
        len(matches) != 1
        or index >= full.edge_count
        or full.checkpoint_ids[: index + 1] != prior.checkpoint_ids
        or full.application_ids[index] != application
    ):
        raise ValueError("historical lineage edge or receipt is missing")
    receipt = matches[0]
    successor = full.checkpoint_ids[index + 1]
    if (
        receipt.status is not PaperOperationStatus.COMPLETED
        or receipt.receipt_id != inputs.intent.operation_id
        or receipt.intent != inputs.intent
        or receipt.application_id != application
        or receipt.prior_lineage_evidence != prior
        or receipt.successor_lineage_evidence.checkpoint_ids
        != full.checkpoint_ids[: index + 2]
        or receipt.successor_lineage_evidence.application_ids
        != full.application_ids[: index + 1]
        or receipt.successor_lineage_evidence.terminal_checkpoint_id != successor
        or receipt.successor_checkpoint_artifact != full.checkpoint_artifacts[index + 1]
        or receipt.transition_report_artifact != full.report_artifacts[index]
        or account.successors[index].artifact_id != successor
    ):
        raise ValueError("historical receipt or deterministic successor differs")
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
    ):
        raise ValueError("historical completed receipt does not reverify")


def _audit(
    d: DisposableHistoricalSettlementAuditDependencies,
) -> HistoricalSettlementAuditResult:
    try:
        _closed(d)
        token = d.observe_token()
        require_trading_token(
            PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid, token
        )
        c1 = d.validate_c1(d.acquire_c1())
        completed = completed_xnys_session_at(d.now())
        inventory, bindings = _inventory(d, c1)
        if any(item.execution_session > completed for item in inventory.decisions):
            raise ValueError("future finalized decision blocks D10")
        configurations = d.historical_configurations(c1)
        if type(configurations) is not tuple or any(
            type(item) is not bytes for item in configurations
        ):
            raise ValueError("historical configurations are invalid")
        account = d.require_account(d.read_account(c1, configurations))
        if type(account) is not PersonalDesktopPaperAccountReadEvidence:
            raise ValueError("verified account evidence is invalid")
        reconciled: list[UUID] = []
        current = next(
            (
                item.decision_id
                for item in inventory.decisions
                if item.execution_session == completed
            ),
            None,
        )
        for binding in bindings:
            decision = binding.decision
            if decision.intended_execution_session == completed:
                current = decision.decision_id
                continue
            try:
                _reconcile_one(d, c1, binding, account)
            except Exception:
                _authority(d, c1, token)
                return HistoricalSettlementAuditResult(
                    HistoricalSettlementAuditClassification.STALE_UNRESOLVED_DECISION,
                    completed,
                    tuple(reconciled),
                    current,
                    decision.decision_id,
                    True,
                    False,
                )
            reconciled.append(decision.decision_id)
        final_inventory, final_bindings = _inventory(d, c1)
        if (
            final_inventory.decisions != inventory.decisions
            or final_bindings != bindings
        ):
            raise ValueError("decision namespace changed during audit")
        if d.require_account(d.read_account(c1, configurations)) != account:
            raise ValueError("account changed during audit")
        if completed_xnys_session_at(d.now()) != completed:
            raise ValueError("completed session changed during audit")
        _authority(d, c1, token)
        return HistoricalSettlementAuditResult(
            HistoricalSettlementAuditClassification.RECONCILED_HISTORY,
            completed,
            tuple(reconciled),
            current,
            None,
            True,
            False,
        )
    except Exception:
        try:
            _closed(d)
            closed = True
        except Exception:
            closed = False
        return HistoricalSettlementAuditResult(
            HistoricalSettlementAuditClassification.BLOCKED,
            all_eight_gates_closed=closed,
        )


def _production_dependencies() -> DisposableHistoricalSettlementAuditDependencies:
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

    def read_account(c1: Any, configurations: tuple[bytes, ...]) -> Any:
        return read_personal_desktop_paper_account(
            c1, historical_cycle_configuration_payloads=configurations
        )

    return DisposableHistoricalSettlementAuditDependencies(
        gate_state=personal_desktop_unattended_effect_gate_state,
        acquire_c1=acquire_validated_production_authority,
        validate_c1=require_validated_production_authority,
        observe_token=observer.observe,
        now=lambda: datetime.now(UTC),
        discover=read_complete_personal_desktop_unattended_decision_namespace,
        require_discovery=require_complete_personal_desktop_unattended_decision_namespace,
        read_selected=read_selected,
        require_selected=require_selected,
        build_open=build_c3_verified_daily_bar_open_binding,
        complete_plan=complete_manual_paper_strategy_plan,
        verify_plan=verify_manual_paper_strategy_plan,
        historical_configurations=resolve_personal_desktop_historical_cycle_configurations,
        read_account=read_account,
        require_account=require_validated_personal_desktop_paper_account,
        build_material=preparation.reconstruct_verified_paper_operation_from_predecessor_prefix,
        read_storage=read_personal_desktop_unattended_invocation_storage,
        require_storage=require_validated_personal_desktop_unattended_invocation_storage_read,
        inspect_operation=inspect_paper_operation_root,
    )
