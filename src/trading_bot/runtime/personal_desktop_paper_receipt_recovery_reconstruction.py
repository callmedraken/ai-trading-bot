"""Read-only reconstruction of one qualified Paper-v2 recovery operation.

The public boundary consumes genuine C1, P2, and PD3-B provenance plus the
explicit semantic inputs of the original operation.  Raw Architecture-67
inputs remain in a private binding for the future same-mutex PD3-D
composition; callers receive only immutable audit facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    inspect_paper_operation_root,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    IdentifiedMarketCalendar,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    parse_checkpointed_paper_cycle_report,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    VerifiedPriorCheckpoint,
    derive_checkpointed_verified_snapshot_application_id,
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperPriorCheckpointEvidence,
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyPlanArtifactBinding,
    ManualPaperStrategyPlanRequest,
    build_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageEvidence,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    PaperAccountCheckpointEdgeVerificationStatus,
    parse_successor_paper_account_checkpoint,
    verify_checkpointed_paper_cycle_successor_edge,
)
from trading_bot.runtime.paper_operation import (
    PaperOperationArtifactEvidence,
    create_paper_operation_intent,
)
from trading_bot.runtime.paper_operation_execution_inputs import (
    VerifiedPaperOperationExecutionInputs,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountRecoveryReadEvidence,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
)
from trading_bot.runtime.personal_desktop_paper_receipt_recovery_qualification import (
    PaperReceiptRecoveryQualificationResult,
    PaperReceiptRecoveryQualificationStatus,
    require_validated_paper_receipt_recovery_qualification,
)
from trading_bot.runtime.strategy_history_seed import VerifiedStrategyHistorySeed
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig


class PaperReceiptRecoveryReconstructionError(PersonalDesktopPaperAccountError):
    """The supplied original-operation facts did not reconstruct the target."""


@dataclass(frozen=True, slots=True)
class PaperReceiptRecoveryReconstructionResult:
    """Sanitized immutable audit evidence; never reusable recovery authority."""

    paper_account_id: str
    operation_id: UUID
    application_id: UUID
    predecessor_checkpoint_id: UUID
    installed_terminal_checkpoint_id: UUID
    selected_snapshot_id: UUID
    plan_id: UUID
    plan_sha256: str
    plan_byte_length: int
    inspection_classification: PaperOperationClassification
    inspection_diagnostic: PaperOperationInspectionCode

    def __post_init__(self) -> None:
        if (
            type(self.paper_account_id) is not str
            or not self.paper_account_id
            or any(
                type(getattr(self, name)) is not UUID
                for name in (
                    "operation_id",
                    "application_id",
                    "predecessor_checkpoint_id",
                    "installed_terminal_checkpoint_id",
                    "selected_snapshot_id",
                    "plan_id",
                )
            )
            or type(self.plan_sha256) is not str
            or len(self.plan_sha256) != 64
            or any(
                character not in "0123456789abcdef" for character in self.plan_sha256
            )
            or type(self.plan_byte_length) is not int
            or self.plan_byte_length <= 0
            or self.inspection_classification
            is not PaperOperationClassification.BLOCKED
            or self.inspection_diagnostic
            is not PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT
        ):
            raise ValueError("receipt-recovery reconstruction result is invalid")


@dataclass(frozen=True, slots=True)
class _PaperReceiptRecoveryReconstructionBinding:
    """Private immediate-use PD3-D material, never returned by the public API."""

    result: PaperReceiptRecoveryReconstructionResult
    execution_inputs: VerifiedPaperOperationExecutionInputs


def reconstruct_personal_desktop_paper_receipt_recovery_operation(
    authority: ValidatedProductionAuthority,
    qualification: PaperReceiptRecoveryQualificationResult,
    selected_snapshot: SelectedC3SnapshotReadResult,
    *,
    history_seed: VerifiedStrategyHistorySeed,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: UUID,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...] = (),
) -> PaperReceiptRecoveryReconstructionResult:
    """Reconstruct and inspect one exact qualified operation without effects."""

    binding = _reconstruct_personal_desktop_paper_receipt_recovery_operation(
        authority,
        qualification,
        selected_snapshot,
        history_seed=history_seed,
        strategy_config=strategy_config,
        caller_idempotency_key=caller_idempotency_key,
        open_reference=open_reference,
        policies=policies,
        planning_at=planning_at,
        submitted_at=submitted_at,
        filled_at=filled_at,
        metadata=metadata,
        operation_root=Path(PERSONAL_DESKTOP_PAPER_V2_RUNTIME),
        calendar=BoundMarketCalendar(
            XNYS_CALENDAR_DESCRIPTOR,
            NYSEMarketCalendar(),
        ),
    )
    return binding.result


def _reconstruct_personal_desktop_paper_receipt_recovery_operation(
    authority: ValidatedProductionAuthority,
    qualification: PaperReceiptRecoveryQualificationResult,
    selected_snapshot: SelectedC3SnapshotReadResult,
    *,
    history_seed: VerifiedStrategyHistorySeed,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: UUID,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...],
    operation_root: Path,
    calendar: IdentifiedMarketCalendar,
) -> _PaperReceiptRecoveryReconstructionBinding:
    """Private reconstruction core for immediate future same-mutex composition."""

    try:
        c1 = require_validated_production_authority(authority)
        if type(qualification) is not PaperReceiptRecoveryQualificationResult:
            raise PaperReceiptRecoveryReconstructionError(
                "receipt-recovery qualification type is invalid"
            )
        if type(selected_snapshot) is not SelectedC3SnapshotReadResult:
            raise PaperReceiptRecoveryReconstructionError(
                "selected snapshot must be an exact P2 read result"
            )
        if type(caller_idempotency_key) is not UUID:
            raise PaperReceiptRecoveryReconstructionError(
                "caller idempotency key must be an exact UUID"
            )
        require_selected_c3_snapshot_matches_authority(
            selected_snapshot.permit,
            selected_snapshot.audit,
            c1,
        )
        recovery_read = require_validated_paper_receipt_recovery_qualification(
            qualification
        )
        _require_qualification_agreement(c1, qualification, recovery_read)
        binding = _reconstruct_from_verified_evidence(
            qualification,
            recovery_read,
            selected_snapshot,
            history_seed=history_seed,
            strategy_config=strategy_config,
            caller_idempotency_key=caller_idempotency_key,
            open_reference=open_reference,
            policies=policies,
            planning_at=planning_at,
            submitted_at=submitted_at,
            filled_at=filled_at,
            metadata=metadata,
            operation_root=operation_root,
            calendar=calendar,
        )
        require_validated_production_authority(c1)
        require_selected_c3_snapshot_matches_authority(
            selected_snapshot.permit,
            selected_snapshot.audit,
            c1,
        )
        if (
            require_validated_paper_receipt_recovery_qualification(qualification)
            is not recovery_read
        ):
            raise PaperReceiptRecoveryReconstructionError(
                "receipt-recovery qualification provenance drifted"
            )
        _require_qualification_agreement(c1, qualification, recovery_read)
        return binding
    except PaperReceiptRecoveryReconstructionError:
        raise
    except Exception as error:
        raise PaperReceiptRecoveryReconstructionError(
            "receipt-recovery reconstruction failed closed"
        ) from error


def _require_qualification_agreement(
    authority: ValidatedProductionAuthority,
    qualification: PaperReceiptRecoveryQualificationResult,
    recovery_read: PersonalDesktopPaperAccountRecoveryReadEvidence,
) -> None:
    account = recovery_read.account
    lineage = account.lineage
    if (
        qualification.status
        is not PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
        or recovery_read.missing_application_id is None
        or recovery_read.missing_predecessor_checkpoint_id is None
        or qualification.paper_account_id != account.anchor.paper_account_id
        or qualification.terminal_checkpoint_id != lineage.terminal_checkpoint_id
        or qualification.missing_application_id != recovery_read.missing_application_id
        or qualification.predecessor_checkpoint_id
        != recovery_read.missing_predecessor_checkpoint_id
        or account.anchor.machine_authority_id != authority.machine_authority_id
        or account.anchor.approved_trading_sid != authority.approved_account_sid
        or not lineage.application_ids
        or lineage.application_ids[-1] != recovery_read.missing_application_id
        or len(lineage.checkpoint_ids) < 2
        or lineage.checkpoint_ids[-2] != recovery_read.missing_predecessor_checkpoint_id
    ):
        raise PaperReceiptRecoveryReconstructionError(
            "qualification, C1, and registered account evidence do not agree"
        )


def _reconstruct_from_verified_evidence(
    qualification: PaperReceiptRecoveryQualificationResult,
    recovery_read: PersonalDesktopPaperAccountRecoveryReadEvidence,
    selected_snapshot: SelectedC3SnapshotReadResult,
    *,
    history_seed: VerifiedStrategyHistorySeed,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: UUID,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...],
    operation_root: Path,
    calendar: IdentifiedMarketCalendar,
) -> _PaperReceiptRecoveryReconstructionBinding:
    account = recovery_read.account
    full = account.lineage
    missing_application_id = recovery_read.missing_application_id
    predecessor_checkpoint_id = recovery_read.missing_predecessor_checkpoint_id
    assert missing_application_id is not None
    assert predecessor_checkpoint_id is not None

    matching_edges = tuple(
        index
        for index, application_id in enumerate(full.application_ids)
        if application_id == missing_application_id
    )
    if matching_edges != (full.edge_count - 1,):
        raise PaperReceiptRecoveryReconstructionError(
            "qualification does not identify one exact terminal transition"
        )
    edge_index = matching_edges[0]
    if (
        len(account.successors) != full.edge_count
        or len(account.reports) != full.edge_count
        or full.checkpoint_ids[edge_index] != predecessor_checkpoint_id
        or full.checkpoint_ids[edge_index + 1] != full.terminal_checkpoint_id
    ):
        raise PaperReceiptRecoveryReconstructionError(
            "registered transition inventory does not match qualification"
        )

    prefix_successors = account.successors[:edge_index]
    prefix_reports = account.reports[:edge_index]
    prefix_snapshots = _prefix_snapshot_artifacts(account.snapshots, full, edge_index)
    prefix = verify_paper_account_lineage(
        account.genesis,
        predecessor_checkpoint_id,
        prefix_successors,
        prefix_reports,
        prefix_snapshots,
        calendar,
    )
    if (
        prefix.status is not PaperAccountLineageVerificationStatus.PASS
        or prefix.evidence is None
        or prefix.terminal_checkpoint is None
        or prefix.diagnostics
        or prefix.evidence.terminal_checkpoint_id != predecessor_checkpoint_id
        or prefix.terminal_checkpoint.checkpoint_id != predecessor_checkpoint_id
        or prefix.evidence.checkpoint_ids != full.checkpoint_ids[: edge_index + 1]
        or prefix.evidence.application_ids != full.application_ids[:edge_index]
        or prefix.evidence.cycle_result_ids != full.cycle_result_ids[:edge_index]
        or prefix.evidence.snapshot_ids != full.snapshot_ids[:edge_index]
        or prefix.evidence.checkpoint_artifacts
        != full.checkpoint_artifacts[: edge_index + 1]
        or prefix.evidence.report_artifacts != full.report_artifacts[:edge_index]
        or prefix.evidence.snapshot_artifacts != full.snapshot_artifacts[:edge_index]
    ):
        raise PaperReceiptRecoveryReconstructionError(
            "predecessor prefix failed independent A66 reverification"
        )
    verified_prior = verified_prior_from_full_lineage(prefix)
    terminal_artifact = _terminal_artifact(
        account.genesis,
        prefix_successors,
        prefix.evidence.checkpoint_artifacts[-1],
    )

    successor_artifact = account.successors[edge_index]
    report_artifact = account.reports[edge_index]
    snapshot_artifact = _exact_snapshot_artifact(
        account.snapshots,
        full.snapshot_artifacts[edge_index],
    )
    if (
        _artifact_evidence(successor_artifact)
        != full.checkpoint_artifacts[edge_index + 1]
        or _artifact_evidence(report_artifact) != full.report_artifacts[edge_index]
        or snapshot_artifact.payload != selected_snapshot.snapshot_bytes
        or snapshot_artifact.artifact_id != selected_snapshot.audit.snapshot_id
        or snapshot_artifact.sha256 != selected_snapshot.audit.artifact_sha256
        or snapshot_artifact.byte_length != selected_snapshot.audit.artifact_byte_length
        or selected_snapshot.verification.snapshot is None
        or selected_snapshot.verification.snapshot.snapshot_id
        != snapshot_artifact.artifact_id
    ):
        raise PaperReceiptRecoveryReconstructionError(
            "selected P2 snapshot does not match registered transition evidence"
        )

    assertion = ManualPaperSelectedC3Assertion(
        selected_snapshot.audit.selection_id,
        selected_snapshot.audit.session_id,
        selected_snapshot.audit.terminal_id,
        selected_snapshot.audit.snapshot_id,
        selected_snapshot.audit.artifact_sha256,
        selected_snapshot.audit.artifact_byte_length,
    )
    plan_request = ManualPaperStrategyPlanRequest(
        selected_snapshot.verification,
        account.anchor.paper_account_id,
        assertion,
        verified_prior,
        history_seed,
        strategy_config,
        str(caller_idempotency_key),
        open_reference,
        policies,
        planning_at,
        submitted_at,
        filled_at,
        metadata,
    )
    built_plan = build_manual_paper_strategy_plan(plan_request, calendar)
    replayed_plan = verify_manual_paper_strategy_plan(
        built_plan.artifact_bytes,
        calendar,
        expected_sha256=built_plan.artifact_sha256,
        expected_byte_length=built_plan.artifact_byte_length,
        expected_checkpointed_request=built_plan.checkpointed_request,
    )
    if _rebuilt_plan_drifted(
        built_plan,
        replayed_plan,
        selected_snapshot,
        verified_prior,
        assertion,
        caller_idempotency_key,
    ):
        raise PaperReceiptRecoveryReconstructionError(
            "rebuilt strategy plan failed detached reconciliation"
        )

    report = parse_checkpointed_paper_cycle_report(report_artifact.payload)
    successor = parse_successor_paper_account_checkpoint(successor_artifact.payload)
    request = built_plan.checkpointed_request
    reference = request.snapshot_reference
    if (
        report.report_id != report_artifact.artifact_id
        or report.evidence.application_id != missing_application_id
        or report.evidence.request != request
        or report.evidence.prior_checkpoint.checkpoint_id != predecessor_checkpoint_id
        or report.evidence.cycle_result_id != full.cycle_result_ids[edge_index]
        or reference.snapshot_id != selected_snapshot.audit.snapshot_id
        or reference.artifact_sha256 != selected_snapshot.audit.artifact_sha256
        or reference.artifact_byte_length
        != selected_snapshot.audit.artifact_byte_length
        or successor.application_id != missing_application_id
        or successor.prior_checkpoint.checkpoint_id != predecessor_checkpoint_id
        or successor.checkpoint_id != qualification.terminal_checkpoint_id
        or successor.checkpoint_id != full.terminal_checkpoint_id
        or successor.producing_cycle.report_id != report.report_id
        or successor.producing_cycle.cycle_result_id != report.evidence.cycle_result_id
        or successor.snapshot_reference != reference
    ):
        raise PaperReceiptRecoveryReconstructionError(
            "rebuilt request does not match the verified terminal transition"
        )
    edge = verify_checkpointed_paper_cycle_successor_edge(
        report_artifact.payload,
        terminal_artifact.payload,
        selected_snapshot.snapshot_bytes,
        successor_artifact.payload,
        calendar,
        expected_successor_sha256=successor_artifact.sha256,
        expected_successor_byte_length=successor_artifact.byte_length,
        verified_prior=verified_prior,
    )
    if (
        edge.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
        or edge.diagnostics
        or edge.successor_checkpoint != successor
        or edge.cycle_result is None
        or edge.cycle_result.result_id != report.evidence.cycle_result_id
        or edge.cycle_result.application_id != missing_application_id
    ):
        raise PaperReceiptRecoveryReconstructionError(
            "terminal successor edge failed exact A62/A63 reverification"
        )

    intent = create_paper_operation_intent(
        caller_idempotency_key,
        prefix.evidence,
        _artifact_evidence(terminal_artifact),
        _artifact_evidence(snapshot_artifact),
        PaperOperationArtifactEvidence(
            built_plan.artifact_sha256,
            built_plan.artifact_byte_length,
        ),
        request,
    )
    application_id = derive_checkpointed_verified_snapshot_application_id(
        predecessor_checkpoint_id,
        request.request_id,
    )
    if application_id != missing_application_id:
        raise PaperReceiptRecoveryReconstructionError(
            "reconstructed application ID does not match qualification"
        )
    execution_inputs = VerifiedPaperOperationExecutionInputs(
        intent,
        application_id,
        account.genesis,
        prefix_successors,
        prefix_reports,
        prefix_snapshots,
        verified_prior,
        terminal_artifact.payload,
        selected_snapshot.snapshot_bytes,
        selected_snapshot.verification,
        built_plan.artifact_bytes,
        request,
        calendar,
    )
    inspection = inspect_paper_operation_root(operation_root, execution_inputs)
    if (
        inspection.classification is not PaperOperationClassification.BLOCKED
        or inspection.diagnostics
        != (PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT,)
        or inspection.application_id != missing_application_id
        or inspection.operation_id != intent.operation_id
        or inspection.terminal_checkpoint_id != predecessor_checkpoint_id
        or inspection.receipt_path is not None
    ):
        raise PaperReceiptRecoveryReconstructionError(
            "A67 inspection did not prove the exact missing-receipt state"
        )
    result = PaperReceiptRecoveryReconstructionResult(
        account.anchor.paper_account_id,
        intent.operation_id,
        application_id,
        predecessor_checkpoint_id,
        full.terminal_checkpoint_id,
        selected_snapshot.audit.snapshot_id,
        built_plan.plan.plan_id,
        built_plan.artifact_sha256,
        built_plan.artifact_byte_length,
        inspection.classification,
        inspection.diagnostics[0],
    )
    return _PaperReceiptRecoveryReconstructionBinding(result, execution_inputs)


def _rebuilt_plan_drifted(
    built_plan: ManualPaperStrategyPlanArtifactBinding,
    replayed_plan: ManualPaperStrategyPlanArtifactBinding,
    selected_snapshot: SelectedC3SnapshotReadResult,
    verified_prior: VerifiedPriorCheckpoint,
    assertion: ManualPaperSelectedC3Assertion,
    caller_idempotency_key: UUID,
) -> bool:
    """Return whether detached plan facts differ from explicit inputs."""

    try:
        return bool(
            replayed_plan != built_plan
            or built_plan.plan.prior_checkpoint
            != ManualPaperPriorCheckpointEvidence.from_verified(verified_prior)
            or built_plan.plan.selected_c3_assertion != assertion
            or built_plan.plan.selected_snapshot_artifact
            != selected_snapshot.snapshot_bytes
            or built_plan.plan.caller_idempotency_key != str(caller_idempotency_key)
        )
    except (AttributeError, TypeError):
        return True


def _prefix_snapshot_artifacts(
    snapshots: tuple[PaperAccountLineageArtifact, ...],
    full: PaperAccountLineageEvidence,
    edge_index: int,
) -> tuple[PaperAccountLineageArtifact, ...]:
    required = full.snapshot_artifacts[:edge_index]
    retained: list[PaperAccountLineageArtifact] = []
    seen: set[UUID] = set()
    for evidence in required:
        artifact = _exact_snapshot_artifact(snapshots, evidence)
        if artifact.artifact_id not in seen:
            retained.append(artifact)
            seen.add(artifact.artifact_id)
    return tuple(retained)


def _exact_snapshot_artifact(
    snapshots: tuple[PaperAccountLineageArtifact, ...],
    evidence: PaperAccountLineageArtifactEvidence,
) -> PaperAccountLineageArtifact:
    matching = tuple(
        artifact
        for artifact in snapshots
        if artifact.artifact_id == evidence.artifact_id
        and _artifact_evidence(artifact) == evidence
    )
    if len(matching) != 1:
        raise PaperReceiptRecoveryReconstructionError(
            "registered snapshot inventory is incomplete or conflicting"
        )
    return matching[0]


def _terminal_artifact(
    genesis: PaperAccountLineageArtifact,
    successors: tuple[PaperAccountLineageArtifact, ...],
    evidence: PaperAccountLineageArtifactEvidence,
) -> PaperAccountLineageArtifact:
    matching = tuple(
        artifact
        for artifact in (genesis, *successors)
        if artifact.artifact_id == evidence.artifact_id
        and _artifact_evidence(artifact) == evidence
    )
    if len(matching) != 1:
        raise PaperReceiptRecoveryReconstructionError(
            "reverified predecessor terminal artifact is ambiguous"
        )
    return matching[0]


def _artifact_evidence(
    artifact: PaperAccountLineageArtifact,
) -> PaperAccountLineageArtifactEvidence:
    if type(artifact) is not PaperAccountLineageArtifact:
        raise PaperReceiptRecoveryReconstructionError(
            "registered lineage artifact type is invalid"
        )
    return PaperAccountLineageArtifactEvidence(
        artifact.kind,
        artifact.artifact_id,
        artifact.sha256,
        artifact.byte_length,
    )
