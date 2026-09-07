"""Path-independent verified inputs for Architecture-67 execution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from trading_bot.market_data import (
    CalendarDescriptor,
    DailySnapshotVerificationResult,
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    verify_daily_snapshot,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    VerifiedPriorCheckpoint,
    derive_checkpointed_verified_snapshot_application_id,
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)
from trading_bot.runtime.paper_operation import PaperOperationIntent


class PaperOperationExecutionInputsError(ValueError):
    """The supplied path-independent execution evidence does not reconcile."""


@dataclass(frozen=True, slots=True)
class VerifiedPaperOperationExecutionInputs:
    """Exact verified semantic and artifact inputs consumed by Architecture 67."""

    intent: PaperOperationIntent
    application_id: UUID
    prior_genesis_checkpoint: PaperAccountLineageArtifact
    prior_successor_checkpoints: tuple[PaperAccountLineageArtifact, ...]
    prior_cycle_reports: tuple[PaperAccountLineageArtifact, ...]
    prior_snapshots: tuple[PaperAccountLineageArtifact, ...]
    verified_prior: VerifiedPriorCheckpoint
    terminal_checkpoint_payload: bytes
    completed_snapshot_payload: bytes
    snapshot_verification: DailySnapshotVerificationResult
    cycle_configuration_payload: bytes
    request: CheckpointedVerifiedSnapshotPaperCycleRequest
    calendar: IdentifiedMarketCalendar

    def __post_init__(self) -> None:
        if (
            type(self.intent) is not PaperOperationIntent
            or type(self.application_id) is not UUID
            or type(self.prior_genesis_checkpoint) is not PaperAccountLineageArtifact
            or type(self.verified_prior) is not VerifiedPriorCheckpoint
            or type(self.terminal_checkpoint_payload) is not bytes
            or type(self.completed_snapshot_payload) is not bytes
            or type(self.snapshot_verification) is not DailySnapshotVerificationResult
            or type(self.cycle_configuration_payload) is not bytes
            or type(self.request) is not CheckpointedVerifiedSnapshotPaperCycleRequest
            or type(getattr(self.calendar, "descriptor", None))
            is not CalendarDescriptor
        ):
            raise PaperOperationExecutionInputsError(
                "paper-operation execution input types are invalid"
            )
        successors = _exact_artifacts(
            self.prior_successor_checkpoints,
            "prior successor checkpoints",
        )
        reports = _exact_artifacts(self.prior_cycle_reports, "prior cycle reports")
        snapshots = _exact_artifacts(self.prior_snapshots, "prior snapshots")
        if self.request != self.intent.request:
            raise PaperOperationExecutionInputsError(
                "cycle request does not match immutable operation intent"
            )
        expected_application_id = derive_checkpointed_verified_snapshot_application_id(
            self.intent.prior_lineage_evidence.terminal_checkpoint_id,
            self.request.request_id,
        )
        if self.application_id != expected_application_id:
            raise PaperOperationExecutionInputsError(
                "application ID does not match operation intent"
            )
        try:
            lineage = verify_paper_account_lineage(
                self.prior_genesis_checkpoint,
                self.intent.prior_lineage_evidence.terminal_checkpoint_id,
                successors,
                reports,
                snapshots,
                self.calendar,
            )
        except Exception as error:
            raise PaperOperationExecutionInputsError(
                "prior lineage inputs could not be verified"
            ) from error
        if (
            lineage.status is not PaperAccountLineageVerificationStatus.PASS
            or lineage.evidence != self.intent.prior_lineage_evidence
        ):
            raise PaperOperationExecutionInputsError(
                "prior lineage inputs do not match operation intent"
            )
        try:
            derived_prior = verified_prior_from_full_lineage(lineage)
        except Exception as error:
            raise PaperOperationExecutionInputsError(
                "verified prior checkpoint could not be derived"
            ) from error
        if self.verified_prior != derived_prior:
            raise PaperOperationExecutionInputsError(
                "verified prior checkpoint does not match prior lineage"
            )
        terminal_evidence = self.intent.terminal_checkpoint_artifact
        terminal_artifact = next(
            (
                artifact
                for artifact in (self.prior_genesis_checkpoint, *successors)
                if artifact.artifact_id == terminal_evidence.artifact_id
            ),
            None,
        )
        if (
            terminal_artifact is None
            or terminal_artifact.kind is not terminal_evidence.kind
            or terminal_artifact.payload != self.terminal_checkpoint_payload
            or terminal_artifact.sha256 != terminal_evidence.sha256
            or terminal_artifact.byte_length != terminal_evidence.byte_length
            or sha256(self.terminal_checkpoint_payload).hexdigest()
            != terminal_evidence.sha256
            or len(self.terminal_checkpoint_payload) != terminal_evidence.byte_length
        ):
            raise PaperOperationExecutionInputsError(
                "terminal checkpoint payload does not match operation intent"
            )
        snapshot_evidence = self.intent.completed_snapshot_artifact
        if (
            snapshot_evidence.kind is not PaperAccountLineageArtifactKind.DAILY_SNAPSHOT
            or sha256(self.completed_snapshot_payload).hexdigest()
            != snapshot_evidence.sha256
            or len(self.completed_snapshot_payload) != snapshot_evidence.byte_length
            or self.snapshot_verification.status
            is not DailySnapshotVerificationStatus.PASS
            or self.snapshot_verification.snapshot is None
            or self.snapshot_verification.snapshot.snapshot_id
            != snapshot_evidence.artifact_id
            or self.snapshot_verification.sha256 != snapshot_evidence.sha256
            or self.snapshot_verification.byte_length != snapshot_evidence.byte_length
        ):
            raise PaperOperationExecutionInputsError(
                "completed snapshot evidence does not match operation intent"
            )
        try:
            repeated_snapshot = verify_daily_snapshot(
                self.completed_snapshot_payload,
                self.calendar,
                expected_sha256=snapshot_evidence.sha256,
                expected_byte_length=snapshot_evidence.byte_length,
            )
        except Exception as error:
            raise PaperOperationExecutionInputsError(
                "completed snapshot could not be verified"
            ) from error
        if repeated_snapshot != self.snapshot_verification:
            raise PaperOperationExecutionInputsError(
                "completed snapshot verification does not reconcile"
            )
        configuration_evidence = self.intent.cycle_configuration_artifact
        if (
            sha256(self.cycle_configuration_payload).hexdigest()
            != configuration_evidence.sha256
            or len(self.cycle_configuration_payload)
            != configuration_evidence.byte_length
        ):
            raise PaperOperationExecutionInputsError(
                "cycle configuration payload does not match operation intent"
            )


def _exact_artifacts(
    values: tuple[PaperAccountLineageArtifact, ...],
    label: str,
) -> tuple[PaperAccountLineageArtifact, ...]:
    if type(values) is not tuple or any(
        type(value) is not PaperAccountLineageArtifact for value in values
    ):
        raise PaperOperationExecutionInputsError(f"{label} are invalid")
    return values
