"""Immutable restart-safe paper-operation intent and receipt evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.ledger import CompactPaperLedgerPosition, CompactPaperLedgerState
from trading_bot.market_data import (
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    canonical_decimal,
    verify_daily_snapshot,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    CheckpointedPaperCycleReportSchemaError,
    CheckpointedPaperCycleReportSyntaxError,
    parse_checkpointed_paper_cycle_report,
    parse_checkpointed_verified_snapshot_paper_cycle_request,
    serialize_checkpointed_verified_snapshot_paper_cycle_request,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    CheckpointedVerifiedSnapshotPaperCycleStatus,
    derive_checkpointed_verified_snapshot_application_id,
    execute_checkpointed_verified_snapshot_paper_cycle,
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.exceptions import (
    CheckpointedVerifiedSnapshotPaperCycleApplicationError,
    CheckpointedVerifiedSnapshotPaperCycleInsufficientCashError,
    CheckpointedVerifiedSnapshotPaperCycleReconciliationError,
    CheckpointedVerifiedSnapshotPaperCycleRestorationError,
    CheckpointedVerifiedSnapshotPaperCycleRuntimeExecutionError,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageEvidence,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    PaperAccountCheckpointEdgeVerificationStatus,
    verify_checkpointed_paper_cycle_successor_edge,
)

PAPER_OPERATION_INTENT_SCHEMA_VERSION = 1
PAPER_OPERATION_RECEIPT_SCHEMA_VERSION = 1
PAPER_OPERATION_ID_MATERIAL_VERSION = "paper-operation-identity-v1"
PAPER_OPERATION_ID_NAMESPACE = UUID("f4cb58e5-bb4a-5dad-8a12-951679933b77")
MAX_PAPER_OPERATION_RECEIPT_BYTES = 32 * 1024 * 1024
MAX_PAPER_OPERATION_ARRAY_ITEMS = 20_000
MAX_PAPER_OPERATION_STRING_CHARACTERS = 16_384
MAX_PAPER_OPERATION_DECIMAL_CHARACTERS = 4096
MAX_PAPER_OPERATION_INTEGER = (1 << 63) - 1

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)


class PaperOperationError(Exception):
    """Base class for immutable paper-operation evidence failures."""


class PaperOperationReceiptSyntaxError(PaperOperationError, ValueError):
    """Raised when receipt bytes are not strict UTF-8 JSON."""


class PaperOperationReceiptSchemaError(PaperOperationError, ValueError):
    """Raised when receipt bytes violate the canonical schema."""


class PaperOperationStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PaperOperationOutcome(StrEnum):
    APPLIED = "APPLIED"
    NO_ACTION = "NO_ACTION"


class PaperOperationDiagnosticCode(StrEnum):
    NONE = "NONE"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    APPLICATION_FAILURE = "APPLICATION_FAILURE"
    RUNTIME_EXECUTION_FAILURE = "RUNTIME_EXECUTION_FAILURE"
    RESTORATION_FAILURE = "RESTORATION_FAILURE"
    RECONCILIATION_FAILURE = "RECONCILIATION_FAILURE"


class PaperOperationReceiptVerificationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class PaperOperationReceiptVerificationCode(StrEnum):
    RECEIPT_BYTE_LENGTH_MISMATCH = "RECEIPT_BYTE_LENGTH_MISMATCH"
    RECEIPT_SHA256_MISMATCH = "RECEIPT_SHA256_MISMATCH"
    RECEIPT_SYNTAX_FAILURE = "RECEIPT_SYNTAX_FAILURE"
    RECEIPT_SCHEMA_FAILURE = "RECEIPT_SCHEMA_FAILURE"
    CONFIGURATION_EVIDENCE_MISMATCH = "CONFIGURATION_EVIDENCE_MISMATCH"
    PRIOR_LINEAGE_FAILURE = "PRIOR_LINEAGE_FAILURE"
    PRIOR_LINEAGE_MISMATCH = "PRIOR_LINEAGE_MISMATCH"
    TERMINAL_CHECKPOINT_MISMATCH = "TERMINAL_CHECKPOINT_MISMATCH"
    SNAPSHOT_VERIFICATION_FAILURE = "SNAPSHOT_VERIFICATION_FAILURE"
    SNAPSHOT_EVIDENCE_MISMATCH = "SNAPSHOT_EVIDENCE_MISMATCH"
    APPLICATION_ID_MISMATCH = "APPLICATION_ID_MISMATCH"
    FAILED_REPLAY_MISMATCH = "FAILED_REPLAY_MISMATCH"
    TRANSITION_EVIDENCE_MISMATCH = "TRANSITION_EVIDENCE_MISMATCH"
    EDGE_VERIFICATION_FAILURE = "EDGE_VERIFICATION_FAILURE"
    OUTCOME_MISMATCH = "OUTCOME_MISMATCH"
    SUCCESSOR_LINEAGE_FAILURE = "SUCCESSOR_LINEAGE_FAILURE"
    SUCCESSOR_LINEAGE_MISMATCH = "SUCCESSOR_LINEAGE_MISMATCH"


@dataclass(frozen=True, slots=True)
class PaperOperationArtifactEvidence:
    """Canonical transport evidence for an artifact without a domain UUID."""

    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if (
            type(self.sha256) is not str
            or _SHA256.fullmatch(self.sha256) is None
            or type(self.byte_length) is not int
            or self.byte_length < 0
        ):
            raise PaperOperationError("operation artifact evidence is invalid")


@dataclass(frozen=True, slots=True)
class PaperOperationIntent:
    """Complete path-independent identity material for one paper operation."""

    schema_version: int
    operation_id: UUID
    caller_idempotency_key: UUID
    prior_lineage_evidence: PaperAccountLineageEvidence
    terminal_checkpoint_artifact: PaperAccountLineageArtifactEvidence
    completed_snapshot_artifact: PaperAccountLineageArtifactEvidence
    cycle_configuration_artifact: PaperOperationArtifactEvidence
    request: CheckpointedVerifiedSnapshotPaperCycleRequest

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != PAPER_OPERATION_INTENT_SCHEMA_VERSION
            or type(self.operation_id) is not UUID
            or type(self.caller_idempotency_key) is not UUID
            or type(self.prior_lineage_evidence) is not PaperAccountLineageEvidence
            or type(self.terminal_checkpoint_artifact)
            is not PaperAccountLineageArtifactEvidence
            or type(self.completed_snapshot_artifact)
            is not PaperAccountLineageArtifactEvidence
            or type(self.cycle_configuration_artifact)
            is not PaperOperationArtifactEvidence
            or type(self.request) is not CheckpointedVerifiedSnapshotPaperCycleRequest
        ):
            raise PaperOperationError("operation intent contains invalid values")
        if (
            self.terminal_checkpoint_artifact.kind
            not in (
                PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
                PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
            )
            or self.terminal_checkpoint_artifact
            != self.prior_lineage_evidence.checkpoint_artifacts[-1]
            or self.completed_snapshot_artifact.kind
            is not PaperAccountLineageArtifactKind.DAILY_SNAPSHOT
            or self.completed_snapshot_artifact.artifact_id
            != self.request.snapshot_reference.snapshot_id
            or self.completed_snapshot_artifact.sha256
            != self.request.snapshot_reference.artifact_sha256
            or self.completed_snapshot_artifact.byte_length
            != self.request.snapshot_reference.artifact_byte_length
        ):
            raise PaperOperationError("operation intent references do not reconcile")
        expected = derive_paper_operation_id(
            self.caller_idempotency_key,
            self.prior_lineage_evidence,
            self.terminal_checkpoint_artifact,
            self.completed_snapshot_artifact,
            self.cycle_configuration_artifact,
            self.request,
        )
        if self.operation_id != expected:
            raise PaperOperationError("operation ID does not reconcile")


@dataclass(frozen=True, slots=True)
class PaperOperationReceipt:
    """Immutable terminal evidence for one exact operation."""

    schema_version: int
    receipt_id: UUID
    intent: PaperOperationIntent
    status: PaperOperationStatus
    outcome: PaperOperationOutcome | None
    diagnostic_code: PaperOperationDiagnosticCode
    prior_lineage_evidence: PaperAccountLineageEvidence
    successor_lineage_evidence: PaperAccountLineageEvidence | None
    transition_report_artifact: PaperAccountLineageArtifactEvidence | None
    successor_checkpoint_artifact: PaperAccountLineageArtifactEvidence | None
    application_id: UUID
    cycle_result_id: UUID | None

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != PAPER_OPERATION_RECEIPT_SCHEMA_VERSION
            or type(self.receipt_id) is not UUID
            or type(self.intent) is not PaperOperationIntent
            or type(self.status) is not PaperOperationStatus
            or type(self.diagnostic_code) is not PaperOperationDiagnosticCode
            or type(self.prior_lineage_evidence) is not PaperAccountLineageEvidence
            or type(self.application_id) is not UUID
            or self.receipt_id != self.intent.operation_id
            or self.prior_lineage_evidence != self.intent.prior_lineage_evidence
        ):
            raise PaperOperationError("operation receipt contains invalid values")
        expected_application = derive_checkpointed_verified_snapshot_application_id(
            self.prior_lineage_evidence.terminal_checkpoint_id,
            self.intent.request.request_id,
        )
        if self.application_id != expected_application:
            raise PaperOperationError("receipt application ID does not reconcile")
        completed = (
            type(self.outcome) is PaperOperationOutcome
            and self.diagnostic_code is PaperOperationDiagnosticCode.NONE
            and type(self.successor_lineage_evidence) is PaperAccountLineageEvidence
            and type(self.transition_report_artifact)
            is PaperAccountLineageArtifactEvidence
            and self.transition_report_artifact.kind
            is PaperAccountLineageArtifactKind.CYCLE_REPORT
            and type(self.successor_checkpoint_artifact)
            is PaperAccountLineageArtifactEvidence
            and self.successor_checkpoint_artifact.kind
            is PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT
            and type(self.cycle_result_id) is UUID
        )
        failed = (
            self.outcome is None
            and self.diagnostic_code is not PaperOperationDiagnosticCode.NONE
            and self.successor_lineage_evidence is None
            and self.transition_report_artifact is None
            and self.successor_checkpoint_artifact is None
            and self.cycle_result_id is None
        )
        if self.status is PaperOperationStatus.COMPLETED:
            if not completed:
                raise PaperOperationError(
                    "COMPLETED receipt requires complete transition evidence"
                )
            successor = self.successor_lineage_evidence
            assert successor is not None
            if (
                successor.genesis_checkpoint_id
                != self.prior_lineage_evidence.genesis_checkpoint_id
                or successor.edge_count != self.prior_lineage_evidence.edge_count + 1
                or successor.checkpoint_ids[:-1]
                != self.prior_lineage_evidence.checkpoint_ids
                or successor.application_ids[:-1]
                != self.prior_lineage_evidence.application_ids
                or successor.application_ids[-1] != self.application_id
                or successor.cycle_result_ids[-1] != self.cycle_result_id
                or successor.checkpoint_artifacts[-1]
                != self.successor_checkpoint_artifact
                or successor.report_artifacts[-1] != self.transition_report_artifact
            ):
                raise PaperOperationError(
                    "successor lineage does not extend prior lineage exactly"
                )
        elif not failed:
            raise PaperOperationError(
                "FAILED receipt may retain only deterministic failure evidence"
            )


@dataclass(frozen=True, slots=True)
class PaperOperationReceiptVerificationDiagnostic:
    code: PaperOperationReceiptVerificationCode

    def __post_init__(self) -> None:
        if type(self.code) is not PaperOperationReceiptVerificationCode:
            raise PaperOperationError("receipt verification diagnostic is invalid")


@dataclass(frozen=True, slots=True)
class PaperOperationReceiptVerificationResult:
    status: PaperOperationReceiptVerificationStatus
    receipt_sha256: str
    receipt_byte_length: int
    receipt: PaperOperationReceipt | None
    diagnostics: tuple[PaperOperationReceiptVerificationDiagnostic, ...]

    def __post_init__(self) -> None:
        if (
            type(self.status) is not PaperOperationReceiptVerificationStatus
            or type(self.receipt_sha256) is not str
            or _SHA256.fullmatch(self.receipt_sha256) is None
            or type(self.receipt_byte_length) is not int
            or self.receipt_byte_length < 0
            or type(self.diagnostics) is not tuple
            or any(
                type(item) is not PaperOperationReceiptVerificationDiagnostic
                for item in self.diagnostics
            )
        ):
            raise PaperOperationError("receipt verification result is invalid")
        if self.status is PaperOperationReceiptVerificationStatus.PASS:
            if type(self.receipt) is not PaperOperationReceipt or self.diagnostics:
                raise PaperOperationError("PASS requires one verified receipt")
        elif self.receipt is not None or not self.diagnostics:
            raise PaperOperationError("FAIL must not expose a receipt")


def create_paper_operation_intent(
    caller_idempotency_key: UUID,
    prior_lineage_evidence: PaperAccountLineageEvidence,
    terminal_checkpoint_artifact: PaperAccountLineageArtifactEvidence,
    completed_snapshot_artifact: PaperAccountLineageArtifactEvidence,
    cycle_configuration_artifact: PaperOperationArtifactEvidence,
    request: CheckpointedVerifiedSnapshotPaperCycleRequest,
) -> PaperOperationIntent:
    """Create one validated intent and its deterministic operation ID."""
    operation_id = derive_paper_operation_id(
        caller_idempotency_key,
        prior_lineage_evidence,
        terminal_checkpoint_artifact,
        completed_snapshot_artifact,
        cycle_configuration_artifact,
        request,
    )
    return PaperOperationIntent(
        PAPER_OPERATION_INTENT_SCHEMA_VERSION,
        operation_id,
        caller_idempotency_key,
        prior_lineage_evidence,
        terminal_checkpoint_artifact,
        completed_snapshot_artifact,
        cycle_configuration_artifact,
        request,
    )


def derive_paper_operation_id(
    caller_idempotency_key: UUID,
    prior_lineage_evidence: PaperAccountLineageEvidence,
    terminal_checkpoint_artifact: PaperAccountLineageArtifactEvidence,
    completed_snapshot_artifact: PaperAccountLineageArtifactEvidence,
    cycle_configuration_artifact: PaperOperationArtifactEvidence,
    request: CheckpointedVerifiedSnapshotPaperCycleRequest,
) -> UUID:
    """Derive one path-independent UUID5 over framed canonical intent material."""
    if (
        type(caller_idempotency_key) is not UUID
        or type(prior_lineage_evidence) is not PaperAccountLineageEvidence
        or type(terminal_checkpoint_artifact) is not PaperAccountLineageArtifactEvidence
        or type(completed_snapshot_artifact) is not PaperAccountLineageArtifactEvidence
        or type(cycle_configuration_artifact) is not PaperOperationArtifactEvidence
        or type(request) is not CheckpointedVerifiedSnapshotPaperCycleRequest
    ):
        raise TypeError("paper-operation identity material is invalid")
    request_material = serialize_checkpointed_verified_snapshot_paper_cycle_request(
        request
    ).decode("ascii")
    return uuid5(
        PAPER_OPERATION_ID_NAMESPACE,
        _framed(
            (
                PAPER_OPERATION_ID_MATERIAL_VERSION,
                str(caller_idempotency_key),
                str(prior_lineage_evidence.evidence_id),
                *_artifact_identity_parts(terminal_checkpoint_artifact),
                *_artifact_identity_parts(completed_snapshot_artifact),
                request_material,
                cycle_configuration_artifact.sha256,
                str(cycle_configuration_artifact.byte_length),
            )
        ),
    )


def serialize_paper_operation_receipt(receipt: PaperOperationReceipt) -> bytes:
    """Serialize an immutable receipt as strict canonical schema-1 JSON."""
    if type(receipt) is not PaperOperationReceipt:
        raise PaperOperationReceiptSchemaError(
            "receipt must be an exact PaperOperationReceipt"
        )
    payload = _canonical_json_bytes(_receipt_tree(receipt))
    if len(payload) > MAX_PAPER_OPERATION_RECEIPT_BYTES:
        raise PaperOperationReceiptSchemaError("receipt exceeds byte bound")
    return payload


def parse_paper_operation_receipt(payload: bytes) -> PaperOperationReceipt:
    """Parse exact canonical receipt bytes with strict schema validation."""
    tree = _load_json(payload)
    root = _object(tree, {"schema_version", "receipt"}, "root")
    if _integer(root["schema_version"], "schema_version") != 1:
        raise PaperOperationReceiptSchemaError("unsupported receipt schema")
    receipt = _receipt(root["receipt"])
    if serialize_paper_operation_receipt(receipt) != payload:
        raise PaperOperationReceiptSchemaError("receipt bytes are not canonical")
    return receipt


def verify_paper_operation_receipt(
    receipt_payload: bytes,
    *,
    cycle_configuration_payload: bytes,
    prior_genesis_checkpoint: PaperAccountLineageArtifact,
    prior_successor_checkpoints: tuple[PaperAccountLineageArtifact, ...],
    prior_cycle_reports: tuple[PaperAccountLineageArtifact, ...],
    prior_snapshots: tuple[PaperAccountLineageArtifact, ...],
    completed_snapshot_payload: bytes,
    calendar: IdentifiedMarketCalendar,
    transition_report_payload: bytes | None = None,
    successor_checkpoint_payload: bytes | None = None,
    expected_receipt_sha256: str | None = None,
    expected_receipt_byte_length: int | None = None,
) -> PaperOperationReceiptVerificationResult:
    """Verify one terminal operation receipt using only explicit offline inputs."""
    length = len(receipt_payload) if type(receipt_payload) is bytes else 0
    digest = (
        sha256(receipt_payload).hexdigest()
        if type(receipt_payload) is bytes
        else "0" * 64
    )
    if expected_receipt_byte_length is not None and (
        type(expected_receipt_byte_length) is not int
        or expected_receipt_byte_length < 0
        or expected_receipt_byte_length != length
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.RECEIPT_BYTE_LENGTH_MISMATCH,
        )
    if expected_receipt_sha256 is not None and (
        type(expected_receipt_sha256) is not str
        or _SHA256.fullmatch(expected_receipt_sha256) is None
        or expected_receipt_sha256 != digest
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.RECEIPT_SHA256_MISMATCH,
        )
    try:
        receipt = parse_paper_operation_receipt(receipt_payload)
    except PaperOperationReceiptSyntaxError:
        return _failed(
            digest, length, PaperOperationReceiptVerificationCode.RECEIPT_SYNTAX_FAILURE
        )
    except (PaperOperationReceiptSchemaError, PaperOperationError):
        return _failed(
            digest, length, PaperOperationReceiptVerificationCode.RECEIPT_SCHEMA_FAILURE
        )
    intent = receipt.intent
    if (
        type(cycle_configuration_payload) is not bytes
        or sha256(cycle_configuration_payload).hexdigest()
        != intent.cycle_configuration_artifact.sha256
        or len(cycle_configuration_payload)
        != intent.cycle_configuration_artifact.byte_length
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.CONFIGURATION_EVIDENCE_MISMATCH,
        )
    try:
        prior = verify_paper_account_lineage(
            prior_genesis_checkpoint,
            intent.prior_lineage_evidence.terminal_checkpoint_id,
            prior_successor_checkpoints,
            prior_cycle_reports,
            prior_snapshots,
            calendar,
        )
    except Exception:
        return _failed(
            digest, length, PaperOperationReceiptVerificationCode.PRIOR_LINEAGE_FAILURE
        )
    if (
        prior.status is not PaperAccountLineageVerificationStatus.PASS
        or prior.evidence is None
    ):
        return _failed(
            digest, length, PaperOperationReceiptVerificationCode.PRIOR_LINEAGE_FAILURE
        )
    if prior.evidence != intent.prior_lineage_evidence:
        return _failed(
            digest, length, PaperOperationReceiptVerificationCode.PRIOR_LINEAGE_MISMATCH
        )
    if prior.evidence.checkpoint_artifacts[-1] != intent.terminal_checkpoint_artifact:
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.TERMINAL_CHECKPOINT_MISMATCH,
        )
    snapshot = verify_daily_snapshot(
        completed_snapshot_payload,
        calendar,
        expected_sha256=intent.completed_snapshot_artifact.sha256,
        expected_byte_length=intent.completed_snapshot_artifact.byte_length,
    )
    if (
        snapshot.status is not DailySnapshotVerificationStatus.PASS
        or snapshot.snapshot is None
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.SNAPSHOT_VERIFICATION_FAILURE,
        )
    if snapshot.snapshot.snapshot_id != intent.completed_snapshot_artifact.artifact_id:
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.SNAPSHOT_EVIDENCE_MISMATCH,
        )
    expected_application = derive_checkpointed_verified_snapshot_application_id(
        prior.evidence.terminal_checkpoint_id, intent.request.request_id
    )
    if receipt.application_id != expected_application:
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.APPLICATION_ID_MISMATCH,
        )
    prior_authority = verified_prior_from_full_lineage(prior)
    if receipt.status is PaperOperationStatus.FAILED:
        if (
            transition_report_payload is not None
            or successor_checkpoint_payload is not None
        ):
            return _failed(
                digest,
                length,
                PaperOperationReceiptVerificationCode.FAILED_REPLAY_MISMATCH,
            )
        try:
            execute_checkpointed_verified_snapshot_paper_cycle(
                intent.request, prior_authority, snapshot, calendar
            )
        except Exception as error:
            if _failure_code(error) is not receipt.diagnostic_code:
                return _failed(
                    digest,
                    length,
                    PaperOperationReceiptVerificationCode.FAILED_REPLAY_MISMATCH,
                )
        else:
            return _failed(
                digest,
                length,
                PaperOperationReceiptVerificationCode.FAILED_REPLAY_MISMATCH,
            )
        return PaperOperationReceiptVerificationResult(
            PaperOperationReceiptVerificationStatus.PASS,
            digest,
            length,
            receipt,
            (),
        )
    if (
        type(transition_report_payload) is not bytes
        or type(successor_checkpoint_payload) is not bytes
        or receipt.transition_report_artifact is None
        or receipt.successor_checkpoint_artifact is None
        or sha256(transition_report_payload).hexdigest()
        != receipt.transition_report_artifact.sha256
        or len(transition_report_payload)
        != receipt.transition_report_artifact.byte_length
        or sha256(successor_checkpoint_payload).hexdigest()
        != receipt.successor_checkpoint_artifact.sha256
        or len(successor_checkpoint_payload)
        != receipt.successor_checkpoint_artifact.byte_length
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.TRANSITION_EVIDENCE_MISMATCH,
        )
    prior_payload = _terminal_payload(
        intent.terminal_checkpoint_artifact.artifact_id,
        prior_genesis_checkpoint,
        prior_successor_checkpoints,
    )
    if prior_payload is None:
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.TERMINAL_CHECKPOINT_MISMATCH,
        )
    edge = verify_checkpointed_paper_cycle_successor_edge(
        transition_report_payload,
        prior_payload,
        completed_snapshot_payload,
        successor_checkpoint_payload,
        calendar,
        expected_successor_sha256=receipt.successor_checkpoint_artifact.sha256,
        expected_successor_byte_length=receipt.successor_checkpoint_artifact.byte_length,
        verified_prior=prior_authority,
    )
    if (
        edge.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
        or edge.cycle_result is None
        or edge.successor_checkpoint is None
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.EDGE_VERIFICATION_FAILURE,
        )
    try:
        report = parse_checkpointed_paper_cycle_report(transition_report_payload)
    except (
        CheckpointedPaperCycleReportSyntaxError,
        CheckpointedPaperCycleReportSchemaError,
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.EDGE_VERIFICATION_FAILURE,
        )
    if (
        report.report_id != receipt.transition_report_artifact.artifact_id
        or edge.successor_checkpoint.checkpoint_id
        != receipt.successor_checkpoint_artifact.artifact_id
        or edge.cycle_result.application_id != receipt.application_id
        or edge.cycle_result.result_id != receipt.cycle_result_id
        or report.evidence.request != intent.request
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.TRANSITION_EVIDENCE_MISMATCH,
        )
    expected_outcome = (
        PaperOperationOutcome.APPLIED
        if edge.cycle_result.status
        is CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED
        else PaperOperationOutcome.NO_ACTION
    )
    if receipt.outcome is not expected_outcome:
        return _failed(
            digest, length, PaperOperationReceiptVerificationCode.OUTCOME_MISMATCH
        )
    report_artifact = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.CYCLE_REPORT,
        report.report_id,
        transition_report_payload,
        receipt.transition_report_artifact.sha256,
        receipt.transition_report_artifact.byte_length,
    )
    successor_artifact = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        edge.successor_checkpoint.checkpoint_id,
        successor_checkpoint_payload,
        receipt.successor_checkpoint_artifact.sha256,
        receipt.successor_checkpoint_artifact.byte_length,
    )
    snapshot_artifact = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        snapshot.snapshot.snapshot_id,
        completed_snapshot_payload,
        intent.completed_snapshot_artifact.sha256,
        intent.completed_snapshot_artifact.byte_length,
    )
    successor_lineage = verify_paper_account_lineage(
        prior_genesis_checkpoint,
        edge.successor_checkpoint.checkpoint_id,
        (*prior_successor_checkpoints, successor_artifact),
        (*prior_cycle_reports, report_artifact),
        (*prior_snapshots, snapshot_artifact),
        calendar,
    )
    if (
        successor_lineage.status is not PaperAccountLineageVerificationStatus.PASS
        or successor_lineage.evidence is None
    ):
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.SUCCESSOR_LINEAGE_FAILURE,
        )
    if successor_lineage.evidence != receipt.successor_lineage_evidence:
        return _failed(
            digest,
            length,
            PaperOperationReceiptVerificationCode.SUCCESSOR_LINEAGE_MISMATCH,
        )
    return PaperOperationReceiptVerificationResult(
        PaperOperationReceiptVerificationStatus.PASS,
        digest,
        length,
        receipt,
        (),
    )


def _failure_code(error: Exception) -> PaperOperationDiagnosticCode | None:
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


def _artifact_identity_parts(
    evidence: PaperAccountLineageArtifactEvidence,
) -> tuple[str, ...]:
    return (
        evidence.kind.value,
        str(evidence.artifact_id),
        evidence.sha256,
        str(evidence.byte_length),
    )


def _receipt_tree(receipt: PaperOperationReceipt) -> dict[str, object]:
    return {
        "schema_version": PAPER_OPERATION_RECEIPT_SCHEMA_VERSION,
        "receipt": {
            "receipt_id": str(receipt.receipt_id),
            "intent": _intent_tree(receipt.intent),
            "status": receipt.status.value,
            "outcome": None if receipt.outcome is None else receipt.outcome.value,
            "diagnostic_code": receipt.diagnostic_code.value,
            "prior_lineage_evidence": _lineage_tree(receipt.prior_lineage_evidence),
            "successor_lineage_evidence": (
                None
                if receipt.successor_lineage_evidence is None
                else _lineage_tree(receipt.successor_lineage_evidence)
            ),
            "transition_report_artifact": _optional_artifact_tree(
                receipt.transition_report_artifact
            ),
            "successor_checkpoint_artifact": _optional_artifact_tree(
                receipt.successor_checkpoint_artifact
            ),
            "application_id": str(receipt.application_id),
            "cycle_result_id": (
                None
                if receipt.cycle_result_id is None
                else str(receipt.cycle_result_id)
            ),
        },
    }


def _intent_tree(intent: PaperOperationIntent) -> dict[str, object]:
    request = json.loads(
        serialize_checkpointed_verified_snapshot_paper_cycle_request(
            intent.request
        ).decode("ascii")
    )
    return {
        "schema_version": intent.schema_version,
        "operation_id": str(intent.operation_id),
        "caller_idempotency_key": str(intent.caller_idempotency_key),
        "prior_lineage_evidence": _lineage_tree(intent.prior_lineage_evidence),
        "terminal_checkpoint_artifact": _artifact_tree(
            intent.terminal_checkpoint_artifact
        ),
        "completed_snapshot_artifact": _artifact_tree(
            intent.completed_snapshot_artifact
        ),
        "cycle_configuration_artifact": {
            "sha256": intent.cycle_configuration_artifact.sha256,
            "byte_length": intent.cycle_configuration_artifact.byte_length,
        },
        "request": request,
    }


def _lineage_tree(evidence: PaperAccountLineageEvidence) -> dict[str, object]:
    return {
        "evidence_id": str(evidence.evidence_id),
        "genesis_checkpoint_id": str(evidence.genesis_checkpoint_id),
        "terminal_checkpoint_id": str(evidence.terminal_checkpoint_id),
        "lineage_id": str(evidence.lineage_id),
        "edge_count": evidence.edge_count,
        "checkpoint_ids": [str(item) for item in evidence.checkpoint_ids],
        "application_ids": [str(item) for item in evidence.application_ids],
        "cycle_result_ids": [str(item) for item in evidence.cycle_result_ids],
        "snapshot_ids": [str(item) for item in evidence.snapshot_ids],
        "checkpoint_artifacts": [
            _artifact_tree(item) for item in evidence.checkpoint_artifacts
        ],
        "report_artifacts": [
            _artifact_tree(item) for item in evidence.report_artifacts
        ],
        "snapshot_artifacts": [
            _artifact_tree(item) for item in evidence.snapshot_artifacts
        ],
        "terminal_compact_state": _compact_tree(evidence.terminal_compact_state),
    }


def _artifact_tree(
    evidence: PaperAccountLineageArtifactEvidence,
) -> dict[str, object]:
    return {
        "kind": evidence.kind.value,
        "artifact_id": str(evidence.artifact_id),
        "sha256": evidence.sha256,
        "byte_length": evidence.byte_length,
    }


def _optional_artifact_tree(
    evidence: PaperAccountLineageArtifactEvidence | None,
) -> dict[str, object] | None:
    return None if evidence is None else _artifact_tree(evidence)


def _compact_tree(state: CompactPaperLedgerState) -> dict[str, object]:
    return {
        "compact_state_id": str(state.compact_state_id),
        "as_of": canonical_timestamp(state.as_of),
        "cash": canonical_decimal(state.cash),
        "positions": [
            {
                "symbol": str(item.symbol),
                "quantity": canonical_decimal(item.quantity),
                "total_cost_basis": canonical_decimal(item.total_cost_basis),
                "average_cost": canonical_decimal(item.average_cost),
            }
            for item in state.positions
        ],
        "realized_profit_loss": canonical_decimal(state.realized_profit_loss),
    }


_RECEIPT_FIELDS = {
    "receipt_id",
    "intent",
    "status",
    "outcome",
    "diagnostic_code",
    "prior_lineage_evidence",
    "successor_lineage_evidence",
    "transition_report_artifact",
    "successor_checkpoint_artifact",
    "application_id",
    "cycle_result_id",
}
_INTENT_FIELDS = {
    "schema_version",
    "operation_id",
    "caller_idempotency_key",
    "prior_lineage_evidence",
    "terminal_checkpoint_artifact",
    "completed_snapshot_artifact",
    "cycle_configuration_artifact",
    "request",
}
_LINEAGE_FIELDS = {
    "evidence_id",
    "genesis_checkpoint_id",
    "terminal_checkpoint_id",
    "lineage_id",
    "edge_count",
    "checkpoint_ids",
    "application_ids",
    "cycle_result_ids",
    "snapshot_ids",
    "checkpoint_artifacts",
    "report_artifacts",
    "snapshot_artifacts",
    "terminal_compact_state",
}
_ARTIFACT_FIELDS = {"kind", "artifact_id", "sha256", "byte_length"}
_COMPACT_FIELDS = {
    "compact_state_id",
    "as_of",
    "cash",
    "positions",
    "realized_profit_loss",
}
_POSITION_FIELDS = {"symbol", "quantity", "total_cost_basis", "average_cost"}


def _receipt(value: object) -> PaperOperationReceipt:
    raw = _object(value, _RECEIPT_FIELDS, "receipt")
    outcome = (
        None
        if raw["outcome"] is None
        else _enum(raw["outcome"], PaperOperationOutcome, "receipt.outcome")
    )
    successor_lineage = (
        None
        if raw["successor_lineage_evidence"] is None
        else _lineage(raw["successor_lineage_evidence"], "successor_lineage")
    )
    report = _optional_artifact(raw["transition_report_artifact"], "report")
    successor = _optional_artifact(
        raw["successor_checkpoint_artifact"], "successor_checkpoint"
    )
    cycle_result = (
        None
        if raw["cycle_result_id"] is None
        else _uuid(raw["cycle_result_id"], "cycle_result_id")
    )
    try:
        return PaperOperationReceipt(
            PAPER_OPERATION_RECEIPT_SCHEMA_VERSION,
            _uuid(raw["receipt_id"], "receipt_id"),
            _intent(raw["intent"]),
            _enum(raw["status"], PaperOperationStatus, "status"),
            outcome,
            _enum(
                raw["diagnostic_code"],
                PaperOperationDiagnosticCode,
                "diagnostic_code",
            ),
            _lineage(raw["prior_lineage_evidence"], "prior_lineage"),
            successor_lineage,
            report,
            successor,
            _uuid(raw["application_id"], "application_id"),
            cycle_result,
        )
    except (TypeError, ValueError, PaperOperationError) as error:
        raise PaperOperationReceiptSchemaError("receipt does not reconcile") from error


def _intent(value: object) -> PaperOperationIntent:
    raw = _object(value, _INTENT_FIELDS, "intent")
    config = _object(
        raw["cycle_configuration_artifact"],
        {"sha256", "byte_length"},
        "cycle_configuration_artifact",
    )
    try:
        request_payload = _canonical_json_bytes(raw["request"])
        request = parse_checkpointed_verified_snapshot_paper_cycle_request(
            request_payload
        )
        return PaperOperationIntent(
            _integer(raw["schema_version"], "intent.schema_version"),
            _uuid(raw["operation_id"], "intent.operation_id"),
            _uuid(raw["caller_idempotency_key"], "caller_idempotency_key"),
            _lineage(raw["prior_lineage_evidence"], "intent.prior_lineage"),
            _artifact(
                raw["terminal_checkpoint_artifact"], "terminal_checkpoint_artifact"
            ),
            _artifact(raw["completed_snapshot_artifact"], "snapshot_artifact"),
            PaperOperationArtifactEvidence(
                _sha(config["sha256"], "configuration.sha256"),
                _nonnegative_integer(
                    config["byte_length"], "configuration.byte_length"
                ),
            ),
            request,
        )
    except (
        TypeError,
        ValueError,
        PaperOperationError,
        CheckpointedPaperCycleReportSyntaxError,
        CheckpointedPaperCycleReportSchemaError,
    ) as error:
        raise PaperOperationReceiptSchemaError("intent does not reconcile") from error


def _lineage(value: object, path: str) -> PaperAccountLineageEvidence:
    raw = _object(value, _LINEAGE_FIELDS, path)
    try:
        return PaperAccountLineageEvidence(
            _uuid(raw["evidence_id"], f"{path}.evidence_id"),
            _uuid(raw["genesis_checkpoint_id"], f"{path}.genesis_checkpoint_id"),
            _uuid(raw["terminal_checkpoint_id"], f"{path}.terminal_checkpoint_id"),
            _uuid(raw["lineage_id"], f"{path}.lineage_id"),
            _nonnegative_integer(raw["edge_count"], f"{path}.edge_count"),
            _uuid_array(raw["checkpoint_ids"], f"{path}.checkpoint_ids"),
            _uuid_array(raw["application_ids"], f"{path}.application_ids"),
            _uuid_array(raw["cycle_result_ids"], f"{path}.cycle_result_ids"),
            _uuid_array(raw["snapshot_ids"], f"{path}.snapshot_ids"),
            _artifact_array(raw["checkpoint_artifacts"], f"{path}.checkpoints"),
            _artifact_array(raw["report_artifacts"], f"{path}.reports"),
            _artifact_array(raw["snapshot_artifacts"], f"{path}.snapshots"),
            _compact(raw["terminal_compact_state"], f"{path}.terminal_compact_state"),
        )
    except (TypeError, ValueError, PaperOperationError) as error:
        raise PaperOperationReceiptSchemaError(
            f"{path}: lineage evidence does not reconcile"
        ) from error


def _artifact(value: object, path: str) -> PaperAccountLineageArtifactEvidence:
    raw = _object(value, _ARTIFACT_FIELDS, path)
    return PaperAccountLineageArtifactEvidence(
        _enum(raw["kind"], PaperAccountLineageArtifactKind, f"{path}.kind"),
        _uuid(raw["artifact_id"], f"{path}.artifact_id"),
        _sha(raw["sha256"], f"{path}.sha256"),
        _nonnegative_integer(raw["byte_length"], f"{path}.byte_length"),
    )


def _optional_artifact(
    value: object, path: str
) -> PaperAccountLineageArtifactEvidence | None:
    return None if value is None else _artifact(value, path)


def _artifact_array(
    value: object, path: str
) -> tuple[PaperAccountLineageArtifactEvidence, ...]:
    return tuple(
        _artifact(item, f"{path}[{index}]")
        for index, item in enumerate(_array(value, path))
    )


def _uuid_array(value: object, path: str) -> tuple[UUID, ...]:
    return tuple(
        _uuid(item, f"{path}[{index}]")
        for index, item in enumerate(_array(value, path))
    )


def _compact(value: object, path: str) -> CompactPaperLedgerState:
    raw = _object(value, _COMPACT_FIELDS, path)
    positions = tuple(
        _position(item, f"{path}.positions[{index}]")
        for index, item in enumerate(_array(raw["positions"], f"{path}.positions"))
    )
    try:
        return CompactPaperLedgerState(
            _uuid(raw["compact_state_id"], f"{path}.compact_state_id"),
            _timestamp(raw["as_of"], f"{path}.as_of"),
            _decimal(raw["cash"], f"{path}.cash"),
            positions,
            _decimal(raw["realized_profit_loss"], f"{path}.realized_profit_loss"),
        )
    except (TypeError, ValueError) as error:
        raise PaperOperationReceiptSchemaError(
            f"{path}: compact state does not reconcile"
        ) from error


def _position(value: object, path: str) -> CompactPaperLedgerPosition:
    raw = _object(value, _POSITION_FIELDS, path)
    try:
        return CompactPaperLedgerPosition(
            Symbol(_string(raw["symbol"], f"{path}.symbol")),
            _decimal(raw["quantity"], f"{path}.quantity"),
            _decimal(raw["total_cost_basis"], f"{path}.total_cost_basis"),
            _decimal(raw["average_cost"], f"{path}.average_cost"),
        )
    except (TypeError, ValueError) as error:
        raise PaperOperationReceiptSchemaError(
            f"{path}: position does not reconcile"
        ) from error


def _terminal_payload(
    terminal_id: UUID,
    genesis: PaperAccountLineageArtifact,
    successors: tuple[PaperAccountLineageArtifact, ...],
) -> bytes | None:
    for item in (genesis, *successors):
        if item.artifact_id == terminal_id:
            return item.payload
    return None


def _canonical_json_bytes(tree: object) -> bytes:
    try:
        return (
            json.dumps(
                tree,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise PaperOperationReceiptSchemaError(
            "cannot render canonical receipt"
        ) from error


def _load_json(payload: bytes) -> object:
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_PAPER_OPERATION_RECEIPT_BYTES
    ):
        raise PaperOperationReceiptSyntaxError(
            "receipt bytes are invalid or exceed bounds"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise PaperOperationReceiptSyntaxError("receipt has UTF-8 BOM")
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        PaperOperationReceiptSchemaError,
    ) as error:
        raise PaperOperationReceiptSyntaxError("receipt JSON is not strict") from error


def _object(value: object, fields: set[str], path: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise PaperOperationReceiptSchemaError(f"{path}: fields do not match schema")
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list or len(value) > MAX_PAPER_OPERATION_ARRAY_ITEMS:
        raise PaperOperationReceiptSchemaError(f"{path}: invalid bounded array")
    return value


def _string(value: object, path: str) -> str:
    if type(value) is not str or len(value) > MAX_PAPER_OPERATION_STRING_CHARACTERS:
        raise PaperOperationReceiptSchemaError(f"{path}: invalid bounded string")
    return value


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    if _UUID.fullmatch(text) is None:
        raise PaperOperationReceiptSchemaError(f"{path}: UUID is not canonical")
    parsed = UUID(text)
    if str(parsed) != text:
        raise PaperOperationReceiptSchemaError(f"{path}: UUID is not canonical")
    return parsed


def _sha(value: object, path: str) -> str:
    text = _string(value, path)
    if _SHA256.fullmatch(text) is None:
        raise PaperOperationReceiptSchemaError(f"{path}: SHA-256 is not canonical")
    return text


def _integer(value: object, path: str) -> int:
    if type(value) is not int or abs(value) > MAX_PAPER_OPERATION_INTEGER:
        raise PaperOperationReceiptSchemaError(f"{path}: invalid integer")
    return value


def _nonnegative_integer(value: object, path: str) -> int:
    retained = _integer(value, path)
    if retained < 0:
        raise PaperOperationReceiptSchemaError(f"{path}: integer must be nonnegative")
    return retained


def _decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    if len(text) > MAX_PAPER_OPERATION_DECIMAL_CHARACTERS:
        raise PaperOperationReceiptSchemaError(f"{path}: Decimal exceeds bound")
    try:
        retained = Decimal(text)
    except InvalidOperation as error:
        raise PaperOperationReceiptSchemaError(f"{path}: Decimal is invalid") from error
    if not retained.is_finite() or canonical_decimal(retained) != text:
        raise PaperOperationReceiptSchemaError(f"{path}: Decimal is not canonical")
    return retained


def _timestamp(value: object, path: str):
    from datetime import datetime

    text = _string(value, path)
    if _TIMESTAMP.fullmatch(text) is None:
        raise PaperOperationReceiptSchemaError(f"{path}: timestamp is invalid")
    try:
        retained = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise PaperOperationReceiptSchemaError(
            f"{path}: timestamp is invalid"
        ) from error
    if canonical_timestamp(retained) != text:
        raise PaperOperationReceiptSchemaError(f"{path}: timestamp is not canonical")
    return retained


def _enum(value: object, enum_type, path: str):  # type: ignore[no-untyped-def]
    text = _string(value, path)
    try:
        retained = enum_type(text)
    except ValueError as error:
        raise PaperOperationReceiptSchemaError(f"{path}: invalid enum") from error
    if retained.value != text:
        raise PaperOperationReceiptSchemaError(f"{path}: enum is not canonical")
    return retained


def _duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PaperOperationReceiptSchemaError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise PaperOperationReceiptSchemaError("JSON float is not permitted")


def _reject_constant(_: str) -> None:
    raise PaperOperationReceiptSchemaError("JSON constant is not permitted")


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def _failed(
    digest: str,
    length: int,
    code: PaperOperationReceiptVerificationCode,
) -> PaperOperationReceiptVerificationResult:
    return PaperOperationReceiptVerificationResult(
        PaperOperationReceiptVerificationStatus.FAIL,
        digest,
        length,
        None,
        (PaperOperationReceiptVerificationDiagnostic(code),),
    )
