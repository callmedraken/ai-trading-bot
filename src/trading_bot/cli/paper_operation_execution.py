"""One-shot verified paper-operation execution and transition commit."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.cli.checkpoint_transition_output import (
    CheckpointTransitionOutputError,
    OutputParent,
    TransitionCommitVerificationPhase,
    commit_transition_directory,
    inspect_transition_directory,
    preflight_transition_directory,
    validate_output_parent,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
    inspect_paper_operation_root,
)
from trading_bot.cli.paper_operation_receipt_output import (
    PaperOperationReceiptOutputError,
    ReceiptCommitVerificationPhase,
    commit_paper_operation_receipt,
)
from trading_bot.runtime import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    MAX_PAPER_OPERATION_RECEIPT_BYTES,
    PAPER_OPERATION_RECEIPT_SCHEMA_VERSION,
    CheckpointedVerifiedSnapshotPaperCycleApplicationError,
    CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    CheckpointedVerifiedSnapshotPaperCycleReconciliationError,
    CheckpointedVerifiedSnapshotPaperCycleRestorationError,
    CheckpointedVerifiedSnapshotPaperCycleResult,
    CheckpointedVerifiedSnapshotPaperCycleRuntimeExecutionError,
    CheckpointedVerifiedSnapshotPaperCycleStatus,
    PaperAccountCheckpointEdgeVerificationStatus,
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageEvidence,
    PaperAccountLineageVerificationStatus,
    PaperOperationDiagnosticCode,
    PaperOperationOutcome,
    PaperOperationReceipt,
    PaperOperationReceiptVerificationStatus,
    PaperOperationStatus,
    VerifiedPaperOperationExecutionInputs,
    checkpointed_paper_cycle_report_from_result,
    checkpointed_paper_cycle_report_reference,
    create_successor_paper_account_checkpoint,
    execute_checkpointed_verified_snapshot_paper_cycle,
    serialize_checkpointed_paper_cycle_report,
    serialize_paper_operation_receipt,
    serialize_successor_paper_account_checkpoint,
    verify_checkpointed_paper_cycle_successor_edge,
    verify_paper_account_lineage,
    verify_paper_operation_receipt,
)

ELIGIBLE_FAILED_RECEIPT_DIAGNOSTICS: frozenset[PaperOperationDiagnosticCode] = (
    frozenset(
        {
            PaperOperationDiagnosticCode.INSUFFICIENT_CASH,
            PaperOperationDiagnosticCode.APPLICATION_FAILURE,
            PaperOperationDiagnosticCode.RESTORATION_FAILURE,
            PaperOperationDiagnosticCode.RECONCILIATION_FAILURE,
            PaperOperationDiagnosticCode.RUNTIME_EXECUTION_FAILURE,
        }
    )
)


class PaperOperationExecutionClassification(StrEnum):
    COMPLETED = "COMPLETED"
    TRANSITION_COMMITTED = "COMPLETED"
    RECEIPT_RECOVERED = "RECEIPT_RECOVERED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    BLOCKED = "BLOCKED"
    CONFLICTING = "CONFLICTING"
    ALREADY_APPLIED = "ALREADY_APPLIED"


class PaperOperationExecutionDiagnosticCode(StrEnum):
    COMPLETED = "COMPLETED"
    TRANSITION_COMMITTED = "COMPLETED"
    RECEIPT_RECOVERED = "RECEIPT_RECOVERED"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    APPLICATION_FAILURE = "APPLICATION_FAILURE"
    RESTORATION_FAILURE = "RESTORATION_FAILURE"
    RECONCILIATION_FAILURE = "RECONCILIATION_FAILURE"
    RUNTIME_EXECUTION_FAILURE = "RUNTIME_EXECUTION_FAILURE"
    RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"
    SERIALIZATION_FAILURE = "SERIALIZATION_FAILURE"
    PROSPECTIVE_EDGE_VERIFICATION_FAILED = "PROSPECTIVE_EDGE_VERIFICATION_FAILED"
    PROSPECTIVE_LINEAGE_VERIFICATION_FAILED = "PROSPECTIVE_LINEAGE_VERIFICATION_FAILED"
    PROSPECTIVE_VERIFICATION_EXCEPTION = "PROSPECTIVE_VERIFICATION_EXCEPTION"
    STAGED_EDGE_VERIFICATION_FAILED = "STAGED_EDGE_VERIFICATION_FAILED"
    STAGED_LINEAGE_VERIFICATION_FAILED = "STAGED_LINEAGE_VERIFICATION_FAILED"
    STAGED_VERIFICATION_EXCEPTION = "STAGED_VERIFICATION_EXCEPTION"
    FINALIZED_EDGE_VERIFICATION_FAILED = "FINALIZED_EDGE_VERIFICATION_FAILED"
    FINALIZED_LINEAGE_VERIFICATION_FAILED = "FINALIZED_LINEAGE_VERIFICATION_FAILED"
    FINALIZED_VERIFICATION_EXCEPTION = "FINALIZED_VERIFICATION_EXCEPTION"
    RECOVERY_EDGE_VERIFICATION_FAILED = "RECOVERY_EDGE_VERIFICATION_FAILED"
    RECOVERY_LINEAGE_VERIFICATION_FAILED = "RECOVERY_LINEAGE_VERIFICATION_FAILED"
    RECOVERY_VERIFICATION_EXCEPTION = "RECOVERY_VERIFICATION_EXCEPTION"
    RECEIPT_SERIALIZATION_FAILURE = "RECEIPT_SERIALIZATION_FAILURE"
    STAGED_RECEIPT_VERIFICATION_FAILED = "STAGED_RECEIPT_VERIFICATION_FAILED"
    FINALIZED_RECEIPT_VERIFICATION_FAILED = "FINALIZED_RECEIPT_VERIFICATION_FAILED"
    FAILED_RECEIPT_REPLAY_VERIFICATION_FAILED = (
        "FAILED_RECEIPT_REPLAY_VERIFICATION_FAILED"
    )
    RECEIPT_OUTPUT_SAFETY_FAILURE = "RECEIPT_OUTPUT_SAFETY_FAILURE"
    OUTPUT_SAFETY_FAILURE = "OUTPUT_SAFETY_FAILURE"
    OPERATION_ROOT_CHANGED = "OPERATION_ROOT_CHANGED"


class _VerificationPhase(StrEnum):
    PROSPECTIVE = "PROSPECTIVE"
    STAGED = "STAGED"
    FINALIZED = "FINALIZED"
    RECOVERY = "RECOVERY"


@dataclass(frozen=True, slots=True)
class PaperOperationExecutionResult:
    classification: PaperOperationExecutionClassification
    operation_id: UUID
    pre_execution_classification: PaperOperationClassification
    terminal_checkpoint_id: UUID
    application_id: UUID
    cycle_result_id: UUID | None
    successor_checkpoint_id: UUID | None
    transition_path: Path | None
    receipt_path: Path | None
    outcome: CheckpointedVerifiedSnapshotPaperCycleStatus | None
    diagnostic_code: str

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not PaperOperationExecutionClassification
            or type(self.operation_id) is not UUID
            or type(self.pre_execution_classification)
            is not PaperOperationClassification
            or type(self.terminal_checkpoint_id) is not UUID
            or type(self.application_id) is not UUID
            or (
                self.cycle_result_id is not None
                and type(self.cycle_result_id) is not UUID
            )
            or (
                self.successor_checkpoint_id is not None
                and type(self.successor_checkpoint_id) is not UUID
            )
            or (
                self.transition_path is not None
                and not isinstance(self.transition_path, Path)
            )
            or (
                self.receipt_path is not None
                and not isinstance(self.receipt_path, Path)
            )
            or (
                self.outcome is not None
                and type(self.outcome)
                is not CheckpointedVerifiedSnapshotPaperCycleStatus
            )
            or type(self.diagnostic_code) is not str
            or not self.diagnostic_code
        ):
            raise ValueError("paper-operation execution result is invalid")
        committed = self.classification in (
            PaperOperationExecutionClassification.COMPLETED,
            PaperOperationExecutionClassification.RECEIPT_RECOVERED,
        )
        if committed != all(
            value is not None
            for value in (
                self.cycle_result_id,
                self.successor_checkpoint_id,
                self.transition_path,
                self.receipt_path,
                self.outcome,
            )
        ):
            raise ValueError("paper-operation execution result does not reconcile")
        if self.classification in (
            PaperOperationExecutionClassification.ALREADY_APPLIED,
            PaperOperationExecutionClassification.CONFLICTING,
        ) and self.pre_execution_classification not in (
            PaperOperationClassification.ALREADY_APPLIED,
            PaperOperationClassification.CONFLICTING,
        ):
            raise ValueError("paper-operation execution state does not reconcile")


class _VerificationFailure(Exception):
    def __init__(self, code: PaperOperationExecutionDiagnosticCode) -> None:
        self.code = code
        super().__init__(code.value)


def execute_paper_operation_once(
    operation_root: Path,
    inputs: VerifiedPaperOperationExecutionInputs,
) -> PaperOperationExecutionResult:
    """Complete or recover one exact operation without retrying its runtime."""
    if (
        not isinstance(operation_root, Path)
        or type(inputs) is not VerifiedPaperOperationExecutionInputs
    ):
        raise TypeError("paper-operation execution arguments are invalid")
    try:
        retained_parent = validate_output_parent(operation_root)
    except CheckpointTransitionOutputError:
        inspection = _unavailable_inspection(inputs)
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.OUTPUT_SAFETY_FAILURE.value,
        )
    inspection = inspect_paper_operation_root(operation_root, inputs)
    if inspection.classification is not PaperOperationClassification.PENDING:
        if (
            inspection.classification is PaperOperationClassification.BLOCKED
            and inspection.diagnostics[0]
            is PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT
        ):
            return _recover_receipt(
                retained_parent,
                inspection,
                inputs,
            )
        if (
            inspection.classification is PaperOperationClassification.BLOCKED
            and inspection.diagnostics[0]
            is PaperOperationInspectionCode.VALID_FAILED_RECEIPT
        ):
            return _recorded_failed_receipt(inspection, inputs)
        classification = (
            PaperOperationExecutionClassification.ALREADY_APPLIED
            if inspection.classification is PaperOperationClassification.ALREADY_APPLIED
            else PaperOperationExecutionClassification.CONFLICTING
            if inspection.classification is PaperOperationClassification.CONFLICTING
            else PaperOperationExecutionClassification.BLOCKED
        )
        return _from_inspection(
            inspection,
            classification,
            inspection.diagnostics[0].value,
            receipt_path=inspection.receipt_path,
            transition_path=(
                retained_parent.path
                / f"paper-account-transition-{inputs.application_id}"
                if classification
                is PaperOperationExecutionClassification.ALREADY_APPLIED
                else None
            ),
        )
    try:
        current_parent = validate_output_parent(operation_root)
        if current_parent != retained_parent:
            return _from_inspection(
                inspection,
                PaperOperationExecutionClassification.BLOCKED,
                PaperOperationExecutionDiagnosticCode.OPERATION_ROOT_CHANGED.value,
            )
        preflight_transition_directory(
            current_parent,
            application_id=str(inputs.application_id),
        )
    except CheckpointTransitionOutputError:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.OUTPUT_SAFETY_FAILURE.value,
        )
    try:
        cycle_result = execute_checkpointed_verified_snapshot_paper_cycle(
            inputs.request,
            inputs.verified_prior,
            inputs.snapshot_verification,
            inputs.calendar,
        )
    except Exception as error:
        diagnostic = _eligible_failed_receipt_diagnostic(error)
        if diagnostic is not None:
            return _finalize_failed_receipt(
                current_parent,
                inspection,
                inputs,
                diagnostic,
            )
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.RUNTIME_EXCEPTION.value,
        )
    try:
        report = checkpointed_paper_cycle_report_from_result(cycle_result)
        report_payload = serialize_checkpointed_paper_cycle_report(report)
        successor = create_successor_paper_account_checkpoint(
            report.evidence.prior_checkpoint,
            report.evidence.prior_lineage_id,
            cycle_result,
            checkpointed_paper_cycle_report_reference(report_payload),
        )
        successor_payload = serialize_successor_paper_account_checkpoint(successor)
    except Exception:
        return _produced_failure(
            inspection,
            cycle_result.result_id,
            None,
            cycle_result.status,
            PaperOperationExecutionDiagnosticCode.SERIALIZATION_FAILURE,
        )
    try:
        prospective_lineage = _verify_successor(
            inputs,
            cycle_result,
            report.report_id,
            successor.checkpoint_id,
            report_payload,
            successor_payload,
            _VerificationPhase.PROSPECTIVE,
            expected_lineage=None,
        )
    except _VerificationFailure as error:
        return _produced_failure(
            inspection,
            cycle_result.result_id,
            successor.checkpoint_id,
            cycle_result.status,
            error.code,
        )
    except Exception:
        return _produced_failure(
            inspection,
            cycle_result.result_id,
            successor.checkpoint_id,
            cycle_result.status,
            PaperOperationExecutionDiagnosticCode.PROSPECTIVE_VERIFICATION_EXCEPTION,
        )

    def verify_reread(
        reread_report: bytes,
        reread_checkpoint: bytes,
        phase: TransitionCommitVerificationPhase,
    ) -> None:
        execution_phase = (
            _VerificationPhase.STAGED
            if phase is TransitionCommitVerificationPhase.STAGED_REREAD
            else _VerificationPhase.FINALIZED
        )
        try:
            _verify_successor(
                inputs,
                cycle_result,
                report.report_id,
                successor.checkpoint_id,
                reread_report,
                reread_checkpoint,
                execution_phase,
                expected_lineage=prospective_lineage,
            )
        except _VerificationFailure:
            raise
        except Exception as error:
            diagnostic = (
                PaperOperationExecutionDiagnosticCode.STAGED_VERIFICATION_EXCEPTION
                if execution_phase is _VerificationPhase.STAGED
                else (
                    PaperOperationExecutionDiagnosticCode.FINALIZED_VERIFICATION_EXCEPTION
                )
            )
            raise _VerificationFailure(diagnostic) from error

    try:
        transition = commit_transition_directory(
            current_parent,
            result=cycle_result,
            report=report,
            report_payload=report_payload,
            successor=successor,
            successor_payload=successor_payload,
            verifier=verify_reread,
        )
    except _VerificationFailure as error:
        return _produced_failure(
            inspection,
            cycle_result.result_id,
            successor.checkpoint_id,
            cycle_result.status,
            error.code,
        )
    except CheckpointTransitionOutputError:
        return _produced_failure(
            inspection,
            cycle_result.result_id,
            successor.checkpoint_id,
            cycle_result.status,
            PaperOperationExecutionDiagnosticCode.OUTPUT_SAFETY_FAILURE,
        )
    except Exception:
        return _produced_failure(
            inspection,
            cycle_result.result_id,
            successor.checkpoint_id,
            cycle_result.status,
            PaperOperationExecutionDiagnosticCode.OUTPUT_SAFETY_FAILURE,
        )
    return _finalize_completed_receipt(
        current_parent,
        inspection,
        inputs,
        cycle_result,
        report_payload,
        successor_payload,
        prospective_lineage,
        transition.directory,
        PaperOperationExecutionClassification.COMPLETED,
        PaperOperationExecutionDiagnosticCode.COMPLETED,
    )


def _recover_receipt(
    parent: OutputParent,
    inspection: PaperOperationInspectionResult,
    inputs: VerifiedPaperOperationExecutionInputs,
) -> PaperOperationExecutionResult:
    try:
        current_parent = validate_output_parent(parent.path)
        if current_parent != parent:
            return _from_inspection(
                inspection,
                PaperOperationExecutionClassification.BLOCKED,
                PaperOperationExecutionDiagnosticCode.OPERATION_ROOT_CHANGED.value,
            )
        transition = inspect_transition_directory(
            current_parent,
            application_id=str(inputs.application_id),
            prior_payload=inputs.terminal_checkpoint_payload,
            snapshot_payload=inputs.completed_snapshot_payload,
            calendar=inputs.calendar,
            expected_request=inputs.request,
            verified_prior=inputs.verified_prior,
        )
        if transition is None:
            return _from_inspection(
                inspection,
                PaperOperationExecutionClassification.BLOCKED,
                PaperOperationInspectionCode.INVALID_TRANSITION.value,
            )
        report_payload = read_safe_regular_file(
            transition.report_path,
            MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
            "recovery cycle report",
        )
        successor_payload = read_safe_regular_file(
            transition.checkpoint_path,
            MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
            "recovery successor checkpoint",
        )
        if (
            sha256(report_payload).hexdigest() != transition.report_sha256
            or len(report_payload) != transition.report_byte_length
            or sha256(successor_payload).hexdigest() != transition.checkpoint_sha256
            or len(successor_payload) != transition.checkpoint_byte_length
        ):
            raise _VerificationFailure(
                PaperOperationExecutionDiagnosticCode.RECOVERY_EDGE_VERIFICATION_FAILED
            )
        successor_lineage = _verify_successor(
            inputs,
            transition.result,
            transition.report.report_id,
            transition.successor.checkpoint_id,
            report_payload,
            successor_payload,
            _VerificationPhase.RECOVERY,
            expected_lineage=None,
        )
    except _VerificationFailure as error:
        return _from_transition_failure(
            inspection,
            error.code,
            transition.directory if "transition" in locals() else None,
        )
    except CheckpointTransitionOutputError:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationInspectionCode.INVALID_TRANSITION.value,
        )
    except Exception:
        return _from_transition_failure(
            inspection,
            PaperOperationExecutionDiagnosticCode.RECOVERY_VERIFICATION_EXCEPTION,
            transition.directory if "transition" in locals() else None,
        )
    return _finalize_completed_receipt(
        current_parent,
        inspection,
        inputs,
        transition.result,
        report_payload,
        successor_payload,
        successor_lineage,
        transition.directory,
        PaperOperationExecutionClassification.RECEIPT_RECOVERED,
        PaperOperationExecutionDiagnosticCode.RECEIPT_RECOVERED,
    )


def _recorded_failed_receipt(
    inspection: PaperOperationInspectionResult,
    inputs: VerifiedPaperOperationExecutionInputs,
) -> PaperOperationExecutionResult:
    if inspection.receipt_path is None:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationInspectionCode.INVALID_RECEIPT.value,
        )
    try:
        payload = read_safe_regular_file(
            inspection.receipt_path,
            MAX_PAPER_OPERATION_RECEIPT_BYTES,
            "recorded failed receipt",
        )
        receipt = _verify_failed_receipt(payload, inputs)
    except Exception:
        receipt = None
    if (
        receipt is None
        or receipt.status is not PaperOperationStatus.FAILED
        or receipt.diagnostic_code not in ELIGIBLE_FAILED_RECEIPT_DIAGNOSTICS
    ):
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationInspectionCode.INVALID_RECEIPT.value,
        )
    return _from_inspection(
        inspection,
        PaperOperationExecutionClassification.EXECUTION_FAILED,
        receipt.diagnostic_code.value,
        receipt_path=inspection.receipt_path,
    )


def _finalize_failed_receipt(
    parent: OutputParent,
    inspection: PaperOperationInspectionResult,
    inputs: VerifiedPaperOperationExecutionInputs,
    diagnostic: PaperOperationDiagnosticCode,
) -> PaperOperationExecutionResult:
    if diagnostic not in ELIGIBLE_FAILED_RECEIPT_DIAGNOSTICS:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.RUNTIME_EXCEPTION.value,
        )
    try:
        current_parent = validate_output_parent(parent.path)
        if current_parent != parent:
            return _from_inspection(
                inspection,
                PaperOperationExecutionClassification.BLOCKED,
                PaperOperationExecutionDiagnosticCode.OPERATION_ROOT_CHANGED.value,
            )
        preflight_transition_directory(
            current_parent,
            application_id=str(inputs.application_id),
        )
    except CheckpointTransitionOutputError:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.OUTPUT_SAFETY_FAILURE.value,
        )
    try:
        receipt = PaperOperationReceipt(
            PAPER_OPERATION_RECEIPT_SCHEMA_VERSION,
            inputs.intent.operation_id,
            inputs.intent,
            PaperOperationStatus.FAILED,
            None,
            diagnostic,
            inputs.intent.prior_lineage_evidence,
            None,
            None,
            None,
            inputs.application_id,
            None,
        )
        receipt_payload = serialize_paper_operation_receipt(receipt)
    except Exception:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.RECEIPT_SERIALIZATION_FAILURE.value,
        )
    if _verify_failed_receipt(receipt_payload, inputs) != receipt:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.FAILED_RECEIPT_REPLAY_VERIFICATION_FAILED.value,
        )

    def verify_receipt_reread(
        reread_payload: bytes,
        phase: ReceiptCommitVerificationPhase,
    ) -> None:
        if _verify_failed_receipt(reread_payload, inputs) != receipt:
            code = (
                PaperOperationExecutionDiagnosticCode.STAGED_RECEIPT_VERIFICATION_FAILED
                if phase is ReceiptCommitVerificationPhase.STAGED_REREAD
                else (
                    PaperOperationExecutionDiagnosticCode.FINALIZED_RECEIPT_VERIFICATION_FAILED
                )
            )
            raise _VerificationFailure(code)

    try:
        committed = commit_paper_operation_receipt(
            current_parent,
            operation_id=inputs.intent.operation_id,
            receipt_payload=receipt_payload,
            verifier=verify_receipt_reread,
        )
    except _VerificationFailure as error:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            error.code.value,
        )
    except PaperOperationReceiptOutputError:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.RECEIPT_OUTPUT_SAFETY_FAILURE.value,
        )
    except Exception:
        return _from_inspection(
            inspection,
            PaperOperationExecutionClassification.BLOCKED,
            PaperOperationExecutionDiagnosticCode.RECEIPT_OUTPUT_SAFETY_FAILURE.value,
        )
    return _from_inspection(
        inspection,
        PaperOperationExecutionClassification.EXECUTION_FAILED,
        diagnostic.value,
        receipt_path=committed.receipt_path,
    )


def _verify_failed_receipt(
    payload: bytes,
    inputs: VerifiedPaperOperationExecutionInputs,
) -> PaperOperationReceipt | None:
    verification = verify_paper_operation_receipt(
        payload,
        cycle_configuration_payload=inputs.cycle_configuration_payload,
        prior_genesis_checkpoint=inputs.prior_genesis_checkpoint,
        prior_successor_checkpoints=inputs.prior_successor_checkpoints,
        prior_cycle_reports=inputs.prior_cycle_reports,
        prior_snapshots=inputs.prior_snapshots,
        completed_snapshot_payload=inputs.completed_snapshot_payload,
        calendar=inputs.calendar,
    )
    if (
        verification.status is not PaperOperationReceiptVerificationStatus.PASS
        or verification.receipt is None
        or verification.receipt.status is not PaperOperationStatus.FAILED
    ):
        return None
    return verification.receipt


def _finalize_completed_receipt(
    parent: OutputParent,
    inspection: PaperOperationInspectionResult,
    inputs: VerifiedPaperOperationExecutionInputs,
    cycle_result: CheckpointedVerifiedSnapshotPaperCycleResult,
    report_payload: bytes,
    successor_payload: bytes,
    successor_lineage: PaperAccountLineageEvidence,
    transition_path: Path,
    classification: PaperOperationExecutionClassification,
    success_diagnostic: PaperOperationExecutionDiagnosticCode,
) -> PaperOperationExecutionResult:
    try:
        receipt = PaperOperationReceipt(
            PAPER_OPERATION_RECEIPT_SCHEMA_VERSION,
            inputs.intent.operation_id,
            inputs.intent,
            PaperOperationStatus.COMPLETED,
            PaperOperationOutcome(cycle_result.status.value),
            PaperOperationDiagnosticCode.NONE,
            inputs.intent.prior_lineage_evidence,
            successor_lineage,
            successor_lineage.report_artifacts[-1],
            successor_lineage.checkpoint_artifacts[-1],
            inputs.application_id,
            cycle_result.result_id,
        )
        receipt_payload = serialize_paper_operation_receipt(receipt)
    except Exception:
        return _receipt_failure(
            inspection,
            cycle_result,
            successor_lineage.terminal_checkpoint_id,
            transition_path,
            PaperOperationExecutionDiagnosticCode.RECEIPT_SERIALIZATION_FAILURE,
        )

    def verify_receipt_reread(
        reread_payload: bytes,
        phase: ReceiptCommitVerificationPhase,
    ) -> None:
        verified = _verify_completed_receipt(
            reread_payload,
            inputs,
            report_payload,
            successor_payload,
        )
        if verified != receipt:
            diagnostic = (
                PaperOperationExecutionDiagnosticCode.STAGED_RECEIPT_VERIFICATION_FAILED
                if phase is ReceiptCommitVerificationPhase.STAGED_REREAD
                else (
                    PaperOperationExecutionDiagnosticCode.FINALIZED_RECEIPT_VERIFICATION_FAILED
                )
            )
            raise _VerificationFailure(diagnostic)

    try:
        if (
            _verify_completed_receipt(
                receipt_payload,
                inputs,
                report_payload,
                successor_payload,
            )
            != receipt
        ):
            raise _VerificationFailure(
                PaperOperationExecutionDiagnosticCode.STAGED_RECEIPT_VERIFICATION_FAILED
            )
        committed = commit_paper_operation_receipt(
            parent,
            operation_id=inputs.intent.operation_id,
            receipt_payload=receipt_payload,
            verifier=verify_receipt_reread,
        )
    except _VerificationFailure as error:
        return _receipt_failure(
            inspection,
            cycle_result,
            successor_lineage.terminal_checkpoint_id,
            transition_path,
            error.code,
        )
    except PaperOperationReceiptOutputError:
        return _receipt_failure(
            inspection,
            cycle_result,
            successor_lineage.terminal_checkpoint_id,
            transition_path,
            PaperOperationExecutionDiagnosticCode.RECEIPT_OUTPUT_SAFETY_FAILURE,
        )
    except Exception:
        return _receipt_failure(
            inspection,
            cycle_result,
            successor_lineage.terminal_checkpoint_id,
            transition_path,
            PaperOperationExecutionDiagnosticCode.RECEIPT_OUTPUT_SAFETY_FAILURE,
        )
    return PaperOperationExecutionResult(
        classification,
        inspection.operation_id,
        inspection.classification,
        inspection.terminal_checkpoint_id,
        inspection.application_id,
        cycle_result.result_id,
        successor_lineage.terminal_checkpoint_id,
        transition_path,
        committed.receipt_path,
        cycle_result.status,
        success_diagnostic.value,
    )


def _verify_completed_receipt(
    payload: bytes,
    inputs: VerifiedPaperOperationExecutionInputs,
    report_payload: bytes,
    successor_payload: bytes,
) -> PaperOperationReceipt | None:
    verification = verify_paper_operation_receipt(
        payload,
        cycle_configuration_payload=inputs.cycle_configuration_payload,
        prior_genesis_checkpoint=inputs.prior_genesis_checkpoint,
        prior_successor_checkpoints=inputs.prior_successor_checkpoints,
        prior_cycle_reports=inputs.prior_cycle_reports,
        prior_snapshots=inputs.prior_snapshots,
        completed_snapshot_payload=inputs.completed_snapshot_payload,
        calendar=inputs.calendar,
        transition_report_payload=report_payload,
        successor_checkpoint_payload=successor_payload,
    )
    if (
        verification.status is not PaperOperationReceiptVerificationStatus.PASS
        or verification.receipt is None
    ):
        return None
    return verification.receipt


def _verify_successor(
    inputs: VerifiedPaperOperationExecutionInputs,
    cycle_result: CheckpointedVerifiedSnapshotPaperCycleResult,
    report_id: UUID,
    successor_id: UUID,
    report_payload: bytes,
    successor_payload: bytes,
    phase: _VerificationPhase,
    *,
    expected_lineage: PaperAccountLineageEvidence | None,
) -> PaperAccountLineageEvidence:
    edge = verify_checkpointed_paper_cycle_successor_edge(
        report_payload,
        inputs.terminal_checkpoint_payload,
        inputs.completed_snapshot_payload,
        successor_payload,
        inputs.calendar,
        expected_successor_sha256=sha256(successor_payload).hexdigest(),
        expected_successor_byte_length=len(successor_payload),
        verified_prior=inputs.verified_prior,
    )
    if (
        edge.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
        or edge.cycle_result != cycle_result
    ):
        raise _VerificationFailure(_edge_failure_code(phase))
    report_artifact = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.CYCLE_REPORT,
        report_id,
        report_payload,
        sha256(report_payload).hexdigest(),
        len(report_payload),
    )
    successor_artifact = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        successor_id,
        successor_payload,
        sha256(successor_payload).hexdigest(),
        len(successor_payload),
    )
    snapshot = inputs.intent.completed_snapshot_artifact
    snapshot_artifact = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        snapshot.artifact_id,
        inputs.completed_snapshot_payload,
        snapshot.sha256,
        snapshot.byte_length,
    )
    lineage = verify_paper_account_lineage(
        inputs.prior_genesis_checkpoint,
        successor_id,
        (*inputs.prior_successor_checkpoints, successor_artifact),
        (*inputs.prior_cycle_reports, report_artifact),
        (*inputs.prior_snapshots, snapshot_artifact),
        inputs.calendar,
    )
    if (
        lineage.status is not PaperAccountLineageVerificationStatus.PASS
        or lineage.evidence is None
        or (expected_lineage is not None and lineage.evidence != expected_lineage)
    ):
        raise _VerificationFailure(_lineage_failure_code(phase))
    return lineage.evidence


def _edge_failure_code(
    phase: _VerificationPhase,
) -> PaperOperationExecutionDiagnosticCode:
    return {
        _VerificationPhase.PROSPECTIVE: (
            PaperOperationExecutionDiagnosticCode.PROSPECTIVE_EDGE_VERIFICATION_FAILED
        ),
        _VerificationPhase.STAGED: (
            PaperOperationExecutionDiagnosticCode.STAGED_EDGE_VERIFICATION_FAILED
        ),
        _VerificationPhase.FINALIZED: (
            PaperOperationExecutionDiagnosticCode.FINALIZED_EDGE_VERIFICATION_FAILED
        ),
        _VerificationPhase.RECOVERY: (
            PaperOperationExecutionDiagnosticCode.RECOVERY_EDGE_VERIFICATION_FAILED
        ),
    }[phase]


def _lineage_failure_code(
    phase: _VerificationPhase,
) -> PaperOperationExecutionDiagnosticCode:
    return {
        _VerificationPhase.PROSPECTIVE: (
            PaperOperationExecutionDiagnosticCode.PROSPECTIVE_LINEAGE_VERIFICATION_FAILED
        ),
        _VerificationPhase.STAGED: (
            PaperOperationExecutionDiagnosticCode.STAGED_LINEAGE_VERIFICATION_FAILED
        ),
        _VerificationPhase.FINALIZED: (
            PaperOperationExecutionDiagnosticCode.FINALIZED_LINEAGE_VERIFICATION_FAILED
        ),
        _VerificationPhase.RECOVERY: (
            PaperOperationExecutionDiagnosticCode.RECOVERY_LINEAGE_VERIFICATION_FAILED
        ),
    }[phase]


def _eligible_failed_receipt_diagnostic(
    error: Exception,
) -> PaperOperationDiagnosticCode | None:
    if isinstance(error, CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError):
        return PaperOperationDiagnosticCode.INSUFFICIENT_CASH
    if isinstance(error, CheckpointedVerifiedSnapshotPaperCycleApplicationError):
        return PaperOperationDiagnosticCode.APPLICATION_FAILURE
    if isinstance(error, CheckpointedVerifiedSnapshotPaperCycleRestorationError):
        return PaperOperationDiagnosticCode.RESTORATION_FAILURE
    if isinstance(error, CheckpointedVerifiedSnapshotPaperCycleReconciliationError):
        return PaperOperationDiagnosticCode.RECONCILIATION_FAILURE
    if isinstance(error, CheckpointedVerifiedSnapshotPaperCycleRuntimeExecutionError):
        return PaperOperationDiagnosticCode.RUNTIME_EXECUTION_FAILURE
    return None


def _from_inspection(
    inspection: PaperOperationInspectionResult,
    classification: PaperOperationExecutionClassification,
    diagnostic_code: str,
    *,
    transition_path: Path | None = None,
    receipt_path: Path | None = None,
) -> PaperOperationExecutionResult:
    return PaperOperationExecutionResult(
        classification,
        inspection.operation_id,
        inspection.classification,
        inspection.terminal_checkpoint_id,
        inspection.application_id,
        None,
        None,
        transition_path,
        receipt_path,
        None,
        diagnostic_code,
    )


def _produced_failure(
    inspection: PaperOperationInspectionResult,
    cycle_result_id: UUID,
    successor_checkpoint_id: UUID | None,
    outcome: CheckpointedVerifiedSnapshotPaperCycleStatus,
    diagnostic: PaperOperationExecutionDiagnosticCode,
) -> PaperOperationExecutionResult:
    return PaperOperationExecutionResult(
        PaperOperationExecutionClassification.BLOCKED,
        inspection.operation_id,
        inspection.classification,
        inspection.terminal_checkpoint_id,
        inspection.application_id,
        cycle_result_id,
        successor_checkpoint_id,
        None,
        None,
        outcome,
        diagnostic.value,
    )


def _from_transition_failure(
    inspection: PaperOperationInspectionResult,
    diagnostic: PaperOperationExecutionDiagnosticCode,
    transition_path: Path | None,
) -> PaperOperationExecutionResult:
    return PaperOperationExecutionResult(
        PaperOperationExecutionClassification.BLOCKED,
        inspection.operation_id,
        inspection.classification,
        inspection.terminal_checkpoint_id,
        inspection.application_id,
        None,
        None,
        transition_path,
        None,
        None,
        diagnostic.value,
    )


def _receipt_failure(
    inspection: PaperOperationInspectionResult,
    cycle_result: CheckpointedVerifiedSnapshotPaperCycleResult,
    successor_checkpoint_id: UUID,
    transition_path: Path,
    diagnostic: PaperOperationExecutionDiagnosticCode,
) -> PaperOperationExecutionResult:
    return PaperOperationExecutionResult(
        PaperOperationExecutionClassification.BLOCKED,
        inspection.operation_id,
        inspection.classification,
        inspection.terminal_checkpoint_id,
        inspection.application_id,
        cycle_result.result_id,
        successor_checkpoint_id,
        transition_path,
        None,
        cycle_result.status,
        diagnostic.value,
    )


def _unavailable_inspection(
    inputs: VerifiedPaperOperationExecutionInputs,
) -> PaperOperationInspectionResult:
    return PaperOperationInspectionResult(
        PaperOperationClassification.BLOCKED,
        inputs.intent.operation_id,
        inputs.intent.prior_lineage_evidence.terminal_checkpoint_id,
        inputs.application_id,
        None,
        (PaperOperationInspectionCode.UNSAFE_OPERATION_ROOT,),
    )
