"""Narrow adapters from verified local CLI results to pure readiness inputs."""

from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from trading_bot.cli.local_lineage_head import VerifiedAuthoritativeLineageHead
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionResult,
)
from trading_bot.runtime import (
    ArtifactEvidence,
    CoordinatorInspectionInput,
    HeadRecordEvidence,
    TerminalCheckpointEvidence,
    VerifiedAuthoritativeHeadInput,
)


def scheduled_head_input_from_verified_authority(
    authority: VerifiedAuthoritativeLineageHead,
) -> VerifiedAuthoritativeHeadInput:
    """Normalize only a complete verified local authority into readiness evidence."""
    if type(authority) is not VerifiedAuthoritativeLineageHead:
        raise TypeError("authority must be VerifiedAuthoritativeLineageHead")
    record = authority.current_record
    pointer = authority.pointer
    if (
        pointer.authority_epoch_id != record.authority_epoch_id
        or pointer.generation != record.generation
        or pointer.head_record_id != record.record_id
        or pointer.head_record_sha256
        != sha256(authority.record_payloads[-1]).hexdigest()
        or pointer.head_record_byte_length != len(authority.record_payloads[-1])
        or authority.verified_prior.checkpoint_id
        != record.terminal_checkpoint.checkpoint_id
        or authority.verified_prior.sequence != record.terminal_checkpoint.sequence
        or authority.verified_prior.checkpoint_sha256
        != record.terminal_checkpoint.sha256
        or authority.verified_prior.checkpoint_byte_length
        != record.terminal_checkpoint.byte_length
    ):
        raise ValueError("verified authority does not reconcile for readiness")
    return VerifiedAuthoritativeHeadInput(
        HeadRecordEvidence(
            record.authority_epoch_id,
            ArtifactEvidence(
                record.record_id,
                pointer.head_record_sha256,
                pointer.head_record_byte_length,
            ),
            record.generation,
        ),
        record.verified_lineage_evidence_id,
        TerminalCheckpointEvidence(
            ArtifactEvidence(
                record.terminal_checkpoint.checkpoint_id,
                record.terminal_checkpoint.sha256,
                record.terminal_checkpoint.byte_length,
            ),
            record.terminal_checkpoint.sequence,
            authority.verified_prior.compact_state.as_of,
        ),
        True,
    )


def scheduled_coordinator_input_from_inspection(
    inspection: PaperOperationInspectionResult,
    *,
    head_advanced_to_successor: bool = False,
    successor_checkpoint_id: UUID | None = None,
) -> CoordinatorInspectionInput:
    """Normalize one existing read-only coordinator inspection result."""
    if type(inspection) is not PaperOperationInspectionResult:
        raise TypeError("inspection must be PaperOperationInspectionResult")
    if type(head_advanced_to_successor) is not bool:
        raise TypeError("head_advanced_to_successor must be a bool")
    if (
        successor_checkpoint_id is not None
        and type(successor_checkpoint_id) is not UUID
    ):
        raise TypeError("successor_checkpoint_id must be a UUID or None")
    already_applied = (
        inspection.classification is PaperOperationClassification.ALREADY_APPLIED
    )
    return CoordinatorInspectionInput(
        inspection.classification.value,
        inspection.terminal_checkpoint_id,
        inspection.diagnostics[0].value,
        successor_checkpoint_id=successor_checkpoint_id,
        completed_receipt_verified=already_applied,
        transition_verified=already_applied,
        head_advanced_to_successor=head_advanced_to_successor,
    )
