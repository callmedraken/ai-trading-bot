"""Explicit local publication and read-only verification of one lineage head."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import (
    MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_BYTES,
    PaperAccountLineageManifest,
    load_paper_account_lineage_manifest,
    read_safe_regular_file,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.runtime import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    MAX_PAPER_OPERATION_RECEIPT_BYTES,
    LineageHeadAdvancementCauseEvidence,
    LineageHeadAdvancementCauseKind,
    LineageHeadRecordReference,
    LineageHeadTerminalCheckpointEvidence,
    LineageManifestEvidence,
    LocalLineageHeadReference,
    LocalLineageHeadSchemaError,
    LocalLineageHeadSyntaxError,
    PaperAccountCheckpointEdgeVerificationStatus,
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageEvidence,
    PaperAccountLineageHeadRecord,
    PaperAccountLineageVerificationResult,
    PaperAccountLineageVerificationStatus,
    PaperOperationReceiptVerificationStatus,
    PaperOperationStatus,
    VerifiedPriorCheckpoint,
    create_paper_account_lineage_head_record,
    parse_local_lineage_head_reference,
    parse_paper_account_lineage_head_record,
    parse_paper_operation_receipt,
    serialize_local_lineage_head_reference,
    serialize_paper_account_lineage_head_record,
    verified_prior_from_full_lineage,
    verify_checkpointed_paper_cycle_successor_edge,
    verify_paper_account_lineage,
    verify_paper_operation_receipt,
)

CURRENT_HEAD_FILENAME = "current-lineage-head.json"
LINEAGE_MANIFEST_DIRECTORY = "lineage-manifests"
LINEAGE_HEAD_RECORD_DIRECTORY = "lineage-head-records"
MAX_AUTHORITY_DIRECTORY_ENTRIES = 10_000


class LocalLineageHeadClassification(StrEnum):
    PASS = "PASS"
    INITIALIZED = "INITIALIZED"
    ADVANCED = "ADVANCED"
    STALE_EXPECTED_HEAD = "STALE_EXPECTED_HEAD"
    BLOCKED = "BLOCKED"
    CONFLICTING = "CONFLICTING"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class LocalLineageHeadDiagnosticCode(StrEnum):
    NONE = "NONE"
    POINTER_MISSING = "POINTER_MISSING"
    POINTER_SYNTAX_FAILURE = "POINTER_SYNTAX_FAILURE"
    POINTER_SCHEMA_FAILURE = "POINTER_SCHEMA_FAILURE"
    POINTER_ALREADY_EXISTS = "POINTER_ALREADY_EXISTS"
    UNSAFE_POINTER = "UNSAFE_POINTER"
    UNSAFE_AUTHORITY_ROOT = "UNSAFE_AUTHORITY_ROOT"
    CASEFOLD_COLLISION = "CASEFOLD_COLLISION"
    HEAD_RECORD_EVIDENCE_MISMATCH = "HEAD_RECORD_EVIDENCE_MISMATCH"
    BROKEN_PREDECESSOR_CHAIN = "BROKEN_PREDECESSOR_CHAIN"
    GENERATION_DISCONTINUITY = "GENERATION_DISCONTINUITY"
    EPOCH_MISMATCH = "EPOCH_MISMATCH"
    MANIFEST_EVIDENCE_MISMATCH = "MANIFEST_EVIDENCE_MISMATCH"
    MANIFEST_VERIFICATION_FAILURE = "MANIFEST_VERIFICATION_FAILURE"
    TERMINAL_EVIDENCE_MISMATCH = "TERMINAL_EVIDENCE_MISMATCH"
    NON_EXTENSION = "NON_EXTENSION"
    FORK = "FORK"
    ROLLBACK = "ROLLBACK"
    ADVANCEMENT_CAUSE_MISMATCH = "ADVANCEMENT_CAUSE_MISMATCH"
    RECEIPT_MISMATCH = "RECEIPT_MISMATCH"
    FAILED_RECEIPT_CANNOT_ADVANCE = "FAILED_RECEIPT_CANNOT_ADVANCE"
    EDGE_VERIFICATION_FAILURE = "EDGE_VERIFICATION_FAILURE"
    EXPLICIT_ARTIFACT_MISMATCH = "EXPLICIT_ARTIFACT_MISMATCH"
    STALE_EXPECTED_HEAD = "STALE_EXPECTED_HEAD"
    IMMUTABLE_ARTIFACT_CONFLICT = "IMMUTABLE_ARTIFACT_CONFLICT"
    ATOMIC_REPLACEMENT_UNAVAILABLE = "ATOMIC_REPLACEMENT_UNAVAILABLE"
    ATOMIC_REPLACEMENT_FAILURE = "ATOMIC_REPLACEMENT_FAILURE"


@dataclass(frozen=True, slots=True)
class VerifiedAuthoritativeLineageHead:
    authority_root: Path
    pointer: LocalLineageHeadReference
    pointer_payload: bytes
    records: tuple[PaperAccountLineageHeadRecord, ...]
    record_payloads: tuple[bytes, ...]
    manifests: tuple[PaperAccountLineageManifest, ...]
    lineage_verifications: tuple[PaperAccountLineageVerificationResult, ...]
    verified_prior: VerifiedPriorCheckpoint

    @property
    def current_record(self) -> PaperAccountLineageHeadRecord:
        return self.records[-1]

    @property
    def current_lineage(self) -> PaperAccountLineageVerificationResult:
        return self.lineage_verifications[-1]


@dataclass(frozen=True, slots=True)
class LocalLineageHeadResult:
    classification: LocalLineageHeadClassification
    diagnostic: LocalLineageHeadDiagnosticCode
    authority: VerifiedAuthoritativeLineageHead | None = None


@dataclass(frozen=True, slots=True)
class _AuthorityRoot:
    path: Path
    identity: tuple[int, int]


@dataclass(frozen=True, slots=True)
class _ManifestVerification:
    path: Path
    payload: bytes
    manifest: PaperAccountLineageManifest
    verification: PaperAccountLineageVerificationResult


class AtomicPointerReplacer(Protocol):
    """Narrow compare-and-swap boundary for the mutable pointer."""

    def replace(
        self,
        pointer_path: Path,
        *,
        expected_payload: bytes,
        replacement_payload: bytes,
        parent_identity: tuple[int, int],
    ) -> None: ...


class AtomicPointerReplacementError(Exception):
    pass


class AtomicPointerReplacementUnavailable(AtomicPointerReplacementError):
    pass


class WindowsAtomicPointerReplacer:
    """Use same-directory MoveFileExW replace-existing with write-through."""

    def replace(
        self,
        pointer_path: Path,
        *,
        expected_payload: bytes,
        replacement_payload: bytes,
        parent_identity: tuple[int, int],
    ) -> None:
        if os.name != "nt":
            raise AtomicPointerReplacementUnavailable(
                "Windows atomic pointer replacement is unavailable"
            )
        parent = pointer_path.parent
        _require_directory_identity(parent, parent_identity)
        if _safe_read(pointer_path, len(expected_payload)) != expected_payload:
            raise AtomicPointerReplacementError(
                "installed pointer changed before compare-and-swap"
            )
        staging_path = parent / f".{CURRENT_HEAD_FILENAME}.staging"
        _reject_casefold_entries(parent, {staging_path.name}, allow={pointer_path.name})
        _write_exclusive_file(staging_path, replacement_payload)
        try:
            staged = _safe_read(staging_path, len(replacement_payload))
            if staged != replacement_payload:
                raise AtomicPointerReplacementError(
                    "pointer staging bytes do not reconcile"
                )
            parse_local_lineage_head_reference(staged)
            _require_directory_identity(parent, parent_identity)
            if _safe_read(pointer_path, len(expected_payload)) != expected_payload:
                raise AtomicPointerReplacementError(
                    "installed pointer changed before atomic replacement"
                )
            _move_file_ex_replace_write_through(staging_path, pointer_path)
            installed = _safe_read(pointer_path, len(replacement_payload))
            if installed != replacement_payload:
                raise AtomicPointerReplacementError(
                    "installed replacement pointer does not reconcile"
                )
            _require_directory_identity(parent, parent_identity)
        except Exception:
            # Staging is intentionally retained after replacement-path failure.
            raise


class _HeadFailure(Exception):
    def __init__(
        self,
        classification: LocalLineageHeadClassification,
        code: LocalLineageHeadDiagnosticCode,
    ) -> None:
        self.classification = classification
        self.code = code
        super().__init__(code.value)


def verify_local_lineage_head(
    authority_root: Path,
    calendar=None,
) -> LocalLineageHeadResult:
    """Verify only the pointer-selected explicit predecessor chain read-only."""
    retained_calendar = _calendar() if calendar is None else calendar
    try:
        authority = _verify_local_lineage_head(authority_root, retained_calendar)
        return LocalLineageHeadResult(
            LocalLineageHeadClassification.PASS,
            LocalLineageHeadDiagnosticCode.NONE,
            authority,
        )
    except _HeadFailure as error:
        return LocalLineageHeadResult(error.classification, error.code)


def initialize_local_lineage_head(
    authority_root: Path,
    authority_epoch_id: UUID,
    lineage_manifest_path: Path,
    calendar=None,
) -> LocalLineageHeadResult:
    """Publish one generation-zero head without overwriting any pointer."""
    retained_calendar = _calendar() if calendar is None else calendar
    try:
        root = _validate_authority_root(authority_root)
        if type(authority_epoch_id) is not UUID:
            raise _blocked(LocalLineageHeadDiagnosticCode.EPOCH_MISMATCH)
        source = _verify_source_manifest(lineage_manifest_path, retained_calendar)
        evidence = source.verification.evidence
        terminal = source.verification.terminal_checkpoint
        if (
            evidence is None
            or terminal is None
            or evidence.edge_count != 0
            or terminal.sequence != 0
        ):
            raise _blocked(LocalLineageHeadDiagnosticCode.NON_EXTENSION)
        _require_absolute_manifest_paths(source.payload)
        manifest_directory, record_directory = _ensure_authority_directories(root)
        pointer_path = root.path / CURRENT_HEAD_FILENAME
        if _entry_exists(pointer_path):
            raise _blocked(LocalLineageHeadDiagnosticCode.POINTER_ALREADY_EXISTS)
        manifest_digest = sha256(source.payload).hexdigest()
        manifest_name = _manifest_filename(evidence.evidence_id, manifest_digest)
        _ensure_immutable_file(
            manifest_directory / manifest_name,
            source.payload,
        )
        terminal_artifact = evidence.checkpoint_artifacts[-1]
        terminal_evidence = _terminal_evidence(terminal_artifact, terminal.sequence)
        record = create_paper_account_lineage_head_record(
            authority_epoch_id,
            0,
            None,
            LineageManifestEvidence(
                evidence.evidence_id,
                manifest_digest,
                len(source.payload),
            ),
            evidence.evidence_id,
            terminal_evidence,
            LineageHeadAdvancementCauseKind.GENESIS,
            LineageHeadAdvancementCauseEvidence(
                terminal_artifact.artifact_id,
                terminal_artifact.sha256,
                terminal_artifact.byte_length,
            ),
        )
        record_payload = serialize_paper_account_lineage_head_record(record)
        record_path = record_directory / _record_filename(record.record_id)
        _ensure_immutable_file(record_path, record_payload)
        pointer = LocalLineageHeadReference(
            1,
            authority_epoch_id,
            0,
            record.record_id,
            sha256(record_payload).hexdigest(),
            len(record_payload),
        )
        _install_initial_pointer(
            root,
            serialize_local_lineage_head_reference(pointer),
        )
        verified = _verify_local_lineage_head(root.path, retained_calendar)
        if verified.pointer != pointer:
            raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_POINTER)
        return LocalLineageHeadResult(
            LocalLineageHeadClassification.INITIALIZED,
            LocalLineageHeadDiagnosticCode.NONE,
            verified,
        )
    except _HeadFailure as error:
        return LocalLineageHeadResult(error.classification, error.code)
    except Exception:
        return LocalLineageHeadResult(
            LocalLineageHeadClassification.BLOCKED,
            LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT,
        )


def advance_local_lineage_head(
    authority_root: Path,
    *,
    expected_head_reference_path: Path,
    lineage_manifest_path: Path,
    prior_checkpoint_path: Path,
    cycle_report_path: Path,
    snapshot_path: Path,
    successor_checkpoint_path: Path,
    completed_receipt_path: Path,
    cycle_configuration_path: Path,
    replacer: AtomicPointerReplacer | None = None,
    calendar=None,
) -> LocalLineageHeadResult:
    """Advance exactly one edge from explicit completed-operation evidence."""
    retained_calendar = _calendar() if calendar is None else calendar
    try:
        current = _verify_local_lineage_head(authority_root, retained_calendar)
        root = _validate_authority_root(authority_root)
        installed_pointer = _safe_read(
            root.path / CURRENT_HEAD_FILENAME,
            16 * 1024,
        )
        expected_pointer = _safe_read(expected_head_reference_path, 16 * 1024)
        try:
            expected = parse_local_lineage_head_reference(expected_pointer)
        except (
            LocalLineageHeadSyntaxError,
            LocalLineageHeadSchemaError,
        ) as error:
            raise _blocked(
                LocalLineageHeadDiagnosticCode.POINTER_SCHEMA_FAILURE
            ) from error
        if expected_pointer != installed_pointer or expected != current.pointer:
            if _is_divergent_stale_proposal(
                current,
                expected,
                lineage_manifest_path,
                retained_calendar,
            ):
                raise _conflicting(LocalLineageHeadDiagnosticCode.FORK)
            classification = (
                LocalLineageHeadClassification.STALE_EXPECTED_HEAD
                if expected.generation <= current.pointer.generation
                else LocalLineageHeadClassification.CONFLICTING
            )
            code = (
                LocalLineageHeadDiagnosticCode.STALE_EXPECTED_HEAD
                if classification is LocalLineageHeadClassification.STALE_EXPECTED_HEAD
                else LocalLineageHeadDiagnosticCode.ROLLBACK
            )
            raise _HeadFailure(classification, code)
        source = _verify_source_manifest(lineage_manifest_path, retained_calendar)
        _require_absolute_manifest_paths(source.payload)
        new_evidence = source.verification.evidence
        new_terminal = source.verification.terminal_checkpoint
        old_evidence = current.current_lineage.evidence
        if old_evidence is None or new_evidence is None or new_terminal is None:
            raise _blocked(LocalLineageHeadDiagnosticCode.MANIFEST_VERIFICATION_FAILURE)
        _require_exact_extension(old_evidence, new_evidence)
        if (
            new_terminal.sequence
            != current.current_record.terminal_checkpoint.sequence + 1
        ):
            raise _blocked(LocalLineageHeadDiagnosticCode.GENERATION_DISCONTINUITY)

        prior_payload = _safe_read(
            prior_checkpoint_path,
            MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
        )
        report_payload = _safe_read(
            cycle_report_path,
            MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
        )
        snapshot_payload = _safe_read(snapshot_path, 4 * 1024 * 1024)
        successor_payload = _safe_read(
            successor_checkpoint_path,
            MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
        )
        receipt_payload = _safe_read(
            completed_receipt_path,
            MAX_PAPER_OPERATION_RECEIPT_BYTES,
        )
        cycle_payload = _safe_read(cycle_configuration_path, 256 * 1024)

        old_manifest = current.manifests[-1]
        old_terminal_artifact = _terminal_artifact(old_manifest, old_evidence)
        if prior_payload != old_terminal_artifact.payload:
            raise _blocked(LocalLineageHeadDiagnosticCode.EXPLICIT_ARTIFACT_MISMATCH)
        new_terminal_artifact = new_evidence.checkpoint_artifacts[-1]
        if (
            sha256(successor_payload).hexdigest() != new_terminal_artifact.sha256
            or len(successor_payload) != new_terminal_artifact.byte_length
        ):
            raise _blocked(LocalLineageHeadDiagnosticCode.EXPLICIT_ARTIFACT_MISMATCH)

        edge = verify_checkpointed_paper_cycle_successor_edge(
            report_payload,
            prior_payload,
            snapshot_payload,
            successor_payload,
            retained_calendar,
            expected_successor_sha256=new_terminal_artifact.sha256,
            expected_successor_byte_length=new_terminal_artifact.byte_length,
            verified_prior=current.verified_prior,
        )
        if (
            edge.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
            or edge.successor_checkpoint is None
            or edge.successor_checkpoint.checkpoint_id
            != new_evidence.terminal_checkpoint_id
        ):
            raise _blocked(LocalLineageHeadDiagnosticCode.EDGE_VERIFICATION_FAILURE)

        try:
            parsed_receipt = parse_paper_operation_receipt(receipt_payload)
        except Exception as error:
            raise _blocked(LocalLineageHeadDiagnosticCode.RECEIPT_MISMATCH) from error
        if parsed_receipt.status is PaperOperationStatus.FAILED:
            raise _HeadFailure(
                LocalLineageHeadClassification.MANUAL_REVIEW_REQUIRED,
                LocalLineageHeadDiagnosticCode.FAILED_RECEIPT_CANNOT_ADVANCE,
            )
        receipt = verify_paper_operation_receipt(
            receipt_payload,
            cycle_configuration_payload=cycle_payload,
            prior_genesis_checkpoint=old_manifest.genesis_checkpoint,
            prior_successor_checkpoints=old_manifest.successor_checkpoints,
            prior_cycle_reports=old_manifest.cycle_reports,
            prior_snapshots=old_manifest.snapshots,
            completed_snapshot_payload=snapshot_payload,
            calendar=retained_calendar,
            transition_report_payload=report_payload,
            successor_checkpoint_payload=successor_payload,
            expected_receipt_sha256=sha256(receipt_payload).hexdigest(),
            expected_receipt_byte_length=len(receipt_payload),
        )
        if (
            receipt.status is not PaperOperationReceiptVerificationStatus.PASS
            or receipt.receipt is None
            or receipt.receipt.status is not PaperOperationStatus.COMPLETED
            or receipt.receipt.prior_lineage_evidence != old_evidence
            or receipt.receipt.successor_lineage_evidence != new_evidence
            or receipt.receipt.successor_checkpoint_artifact
            != new_evidence.checkpoint_artifacts[-1]
            or receipt.receipt.transition_report_artifact
            != new_evidence.report_artifacts[-1]
            or receipt.receipt.intent.completed_snapshot_artifact
            != new_evidence.snapshot_artifacts[-1]
        ):
            raise _blocked(LocalLineageHeadDiagnosticCode.RECEIPT_MISMATCH)

        manifest_directory, record_directory = _ensure_authority_directories(root)
        manifest_digest = sha256(source.payload).hexdigest()
        _ensure_immutable_file(
            manifest_directory
            / _manifest_filename(new_evidence.evidence_id, manifest_digest),
            source.payload,
        )
        previous_payload = current.record_payloads[-1]
        previous = LineageHeadRecordReference(
            current.current_record.record_id,
            sha256(previous_payload).hexdigest(),
            len(previous_payload),
        )
        new_record = create_paper_account_lineage_head_record(
            current.pointer.authority_epoch_id,
            current.pointer.generation + 1,
            previous,
            LineageManifestEvidence(
                new_evidence.evidence_id,
                manifest_digest,
                len(source.payload),
            ),
            new_evidence.evidence_id,
            _terminal_evidence(
                new_evidence.checkpoint_artifacts[-1],
                new_terminal.sequence,
            ),
            LineageHeadAdvancementCauseKind.COMPLETED_OPERATION,
            LineageHeadAdvancementCauseEvidence(
                receipt.receipt.receipt_id,
                sha256(receipt_payload).hexdigest(),
                len(receipt_payload),
            ),
        )
        new_record_payload = serialize_paper_account_lineage_head_record(new_record)
        _ensure_immutable_file(
            record_directory / _record_filename(new_record.record_id),
            new_record_payload,
        )
        new_pointer = LocalLineageHeadReference(
            1,
            current.pointer.authority_epoch_id,
            current.pointer.generation + 1,
            new_record.record_id,
            sha256(new_record_payload).hexdigest(),
            len(new_record_payload),
        )
        retained_replacer = (
            WindowsAtomicPointerReplacer() if replacer is None else replacer
        )
        try:
            retained_replacer.replace(
                root.path / CURRENT_HEAD_FILENAME,
                expected_payload=installed_pointer,
                replacement_payload=serialize_local_lineage_head_reference(new_pointer),
                parent_identity=root.identity,
            )
        except AtomicPointerReplacementUnavailable as error:
            raise _HeadFailure(
                LocalLineageHeadClassification.MANUAL_REVIEW_REQUIRED,
                LocalLineageHeadDiagnosticCode.ATOMIC_REPLACEMENT_UNAVAILABLE,
            ) from error
        except Exception as error:
            raise _HeadFailure(
                LocalLineageHeadClassification.MANUAL_REVIEW_REQUIRED,
                LocalLineageHeadDiagnosticCode.ATOMIC_REPLACEMENT_FAILURE,
            ) from error
        verified = _verify_local_lineage_head(root.path, retained_calendar)
        if verified.pointer != new_pointer:
            raise _HeadFailure(
                LocalLineageHeadClassification.MANUAL_REVIEW_REQUIRED,
                LocalLineageHeadDiagnosticCode.ATOMIC_REPLACEMENT_FAILURE,
            )
        return LocalLineageHeadResult(
            LocalLineageHeadClassification.ADVANCED,
            LocalLineageHeadDiagnosticCode.NONE,
            verified,
        )
    except _HeadFailure as error:
        return LocalLineageHeadResult(error.classification, error.code)
    except Exception:
        return LocalLineageHeadResult(
            LocalLineageHeadClassification.BLOCKED,
            LocalLineageHeadDiagnosticCode.EXPLICIT_ARTIFACT_MISMATCH,
        )


def _verify_local_lineage_head(
    authority_root: Path,
    calendar,
) -> VerifiedAuthoritativeLineageHead:
    root = _validate_authority_root(authority_root)
    pointer_path = root.path / CURRENT_HEAD_FILENAME
    if not _entry_exists(pointer_path):
        raise _blocked(LocalLineageHeadDiagnosticCode.POINTER_MISSING)
    manifest_directory = _require_child_directory(root, LINEAGE_MANIFEST_DIRECTORY)
    record_directory = _require_child_directory(root, LINEAGE_HEAD_RECORD_DIRECTORY)
    try:
        pointer_payload = _safe_read(pointer_path, 16 * 1024)
    except Exception as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_POINTER) from error
    try:
        pointer = parse_local_lineage_head_reference(pointer_payload)
    except LocalLineageHeadSyntaxError as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.POINTER_SYNTAX_FAILURE) from error
    except LocalLineageHeadSchemaError as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.POINTER_SCHEMA_FAILURE) from error

    records_reverse: list[PaperAccountLineageHeadRecord] = []
    payloads_reverse: list[bytes] = []
    manifests_reverse: list[PaperAccountLineageManifest] = []
    verifications_reverse: list[PaperAccountLineageVerificationResult] = []
    expected_id = pointer.head_record_id
    expected_sha = pointer.head_record_sha256
    expected_length = pointer.head_record_byte_length
    seen: set[UUID] = set()
    while True:
        if expected_id in seen:
            raise _conflicting(LocalLineageHeadDiagnosticCode.BROKEN_PREDECESSOR_CHAIN)
        seen.add(expected_id)
        record_path = record_directory / _record_filename(expected_id)
        try:
            record_payload = _safe_read(record_path, 64 * 1024)
        except Exception as error:
            raise _blocked(
                LocalLineageHeadDiagnosticCode.BROKEN_PREDECESSOR_CHAIN
            ) from error
        if (
            len(record_payload) != expected_length
            or sha256(record_payload).hexdigest() != expected_sha
        ):
            raise _blocked(LocalLineageHeadDiagnosticCode.HEAD_RECORD_EVIDENCE_MISMATCH)
        try:
            record = parse_paper_account_lineage_head_record(record_payload)
        except Exception as error:
            raise _blocked(
                LocalLineageHeadDiagnosticCode.HEAD_RECORD_EVIDENCE_MISMATCH
            ) from error
        if record.record_id != expected_id:
            raise _blocked(LocalLineageHeadDiagnosticCode.HEAD_RECORD_EVIDENCE_MISMATCH)
        if record.authority_epoch_id != pointer.authority_epoch_id:
            raise _conflicting(LocalLineageHeadDiagnosticCode.EPOCH_MISMATCH)
        manifest_path = manifest_directory / _manifest_filename(
            record.lineage_manifest.artifact_id,
            record.lineage_manifest.sha256,
        )
        manifest = _verify_published_manifest(
            manifest_path,
            record.lineage_manifest,
            calendar,
        )
        _require_record_matches_manifest(record, manifest.verification)
        records_reverse.append(record)
        payloads_reverse.append(record_payload)
        manifests_reverse.append(manifest.manifest)
        verifications_reverse.append(manifest.verification)
        previous = record.previous_head_record
        if previous is None:
            break
        expected_id = previous.head_record_id
        expected_sha = previous.sha256
        expected_length = previous.byte_length

    records = tuple(reversed(records_reverse))
    payloads = tuple(reversed(payloads_reverse))
    manifests = tuple(reversed(manifests_reverse))
    verifications = tuple(reversed(verifications_reverse))
    if (
        records[-1].record_id != pointer.head_record_id
        or records[-1].generation != pointer.generation
    ):
        raise _blocked(LocalLineageHeadDiagnosticCode.GENERATION_DISCONTINUITY)
    for index, record in enumerate(records):
        if record.generation != index:
            code = (
                LocalLineageHeadDiagnosticCode.ROLLBACK
                if record.generation < index
                else LocalLineageHeadDiagnosticCode.GENERATION_DISCONTINUITY
            )
            raise _conflicting(code)
        if record.authority_epoch_id != pointer.authority_epoch_id:
            raise _conflicting(LocalLineageHeadDiagnosticCode.EPOCH_MISMATCH)
        if index:
            _require_exact_extension(
                verifications[index - 1].evidence,
                verifications[index].evidence,
            )
            if record.advancement_cause_kind not in (
                LineageHeadAdvancementCauseKind.COMPLETED_OPERATION,
                LineageHeadAdvancementCauseKind.APPROVED_MANUAL_RECOVERY,
            ):
                raise _blocked(
                    LocalLineageHeadDiagnosticCode.ADVANCEMENT_CAUSE_MISMATCH
                )
    try:
        verified_prior = verified_prior_from_full_lineage(verifications[-1])
    except Exception as error:
        raise _blocked(
            LocalLineageHeadDiagnosticCode.MANIFEST_VERIFICATION_FAILURE
        ) from error
    try:
        _require_directory_identity(root.path, root.identity)
        if _safe_read(pointer_path, 16 * 1024) != pointer_payload:
            raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_POINTER)
    except _HeadFailure:
        raise
    except Exception as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT) from error
    return VerifiedAuthoritativeLineageHead(
        root.path,
        pointer,
        pointer_payload,
        records,
        payloads,
        manifests,
        verifications,
        verified_prior,
    )


def _verify_source_manifest(path: Path, calendar) -> _ManifestVerification:
    try:
        payload = read_safe_regular_file(
            path,
            MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_BYTES,
            "lineage manifest",
        )
        manifest = load_paper_account_lineage_manifest(path)
        verification = verify_paper_account_lineage(
            manifest.genesis_checkpoint,
            manifest.terminal_checkpoint_id,
            manifest.successor_checkpoints,
            manifest.cycle_reports,
            manifest.snapshots,
            calendar,
        )
    except Exception as error:
        raise _blocked(
            LocalLineageHeadDiagnosticCode.MANIFEST_VERIFICATION_FAILURE
        ) from error
    if (
        verification.status is not PaperAccountLineageVerificationStatus.PASS
        or verification.evidence is None
        or verification.terminal_checkpoint is None
    ):
        raise _blocked(LocalLineageHeadDiagnosticCode.MANIFEST_VERIFICATION_FAILURE)
    return _ManifestVerification(path, payload, manifest, verification)


def _verify_published_manifest(
    path: Path,
    expected: LineageManifestEvidence,
    calendar,
) -> _ManifestVerification:
    try:
        payload = _safe_read(path, MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_BYTES)
    except Exception as error:
        raise _blocked(
            LocalLineageHeadDiagnosticCode.MANIFEST_EVIDENCE_MISMATCH
        ) from error
    if (
        len(payload) != expected.byte_length
        or sha256(payload).hexdigest() != expected.sha256
    ):
        raise _blocked(LocalLineageHeadDiagnosticCode.MANIFEST_EVIDENCE_MISMATCH)
    result = _verify_source_manifest(path, calendar)
    evidence = result.verification.evidence
    if evidence is None or evidence.evidence_id != expected.artifact_id:
        raise _blocked(LocalLineageHeadDiagnosticCode.MANIFEST_VERIFICATION_FAILURE)
    return result


def _require_record_matches_manifest(
    record: PaperAccountLineageHeadRecord,
    verification: PaperAccountLineageVerificationResult,
) -> None:
    evidence = verification.evidence
    terminal = verification.terminal_checkpoint
    if evidence is None or terminal is None:
        raise _blocked(LocalLineageHeadDiagnosticCode.MANIFEST_VERIFICATION_FAILURE)
    artifact = evidence.checkpoint_artifacts[-1]
    if (
        evidence.evidence_id != record.verified_lineage_evidence_id
        or artifact.artifact_id != record.terminal_checkpoint.checkpoint_id
        or artifact.sha256 != record.terminal_checkpoint.sha256
        or artifact.byte_length != record.terminal_checkpoint.byte_length
        or terminal.sequence != record.terminal_checkpoint.sequence
        or record.generation != terminal.sequence
    ):
        raise _blocked(LocalLineageHeadDiagnosticCode.TERMINAL_EVIDENCE_MISMATCH)


def _require_exact_extension(
    prior: PaperAccountLineageEvidence | None,
    successor: PaperAccountLineageEvidence | None,
) -> None:
    if prior is None or successor is None:
        raise _blocked(LocalLineageHeadDiagnosticCode.NON_EXTENSION)
    if successor.edge_count <= prior.edge_count:
        raise _conflicting(LocalLineageHeadDiagnosticCode.ROLLBACK)
    if successor.edge_count != prior.edge_count + 1:
        raise _blocked(LocalLineageHeadDiagnosticCode.NON_EXTENSION)
    if (
        successor.genesis_checkpoint_id != prior.genesis_checkpoint_id
        or successor.checkpoint_ids[:-1] != prior.checkpoint_ids
        or successor.application_ids[:-1] != prior.application_ids
        or successor.cycle_result_ids[:-1] != prior.cycle_result_ids
        or successor.snapshot_ids[:-1] != prior.snapshot_ids
        or successor.checkpoint_artifacts[:-1] != prior.checkpoint_artifacts
        or successor.report_artifacts[:-1] != prior.report_artifacts
        or successor.snapshot_artifacts[:-1] != prior.snapshot_artifacts
    ):
        raise _conflicting(LocalLineageHeadDiagnosticCode.FORK)


def _is_divergent_stale_proposal(
    current: VerifiedAuthoritativeLineageHead,
    expected: LocalLineageHeadReference,
    lineage_manifest_path: Path,
    calendar,
) -> bool:
    if (
        expected.generation >= current.pointer.generation
        or expected.generation >= len(current.records)
        or current.records[expected.generation].record_id != expected.head_record_id
        or expected.generation + 1 >= len(current.lineage_verifications)
    ):
        return False
    try:
        proposed = _verify_source_manifest(lineage_manifest_path, calendar)
        base = current.lineage_verifications[expected.generation].evidence
        _require_exact_extension(base, proposed.verification.evidence)
    except _HeadFailure:
        return False
    installed = current.lineage_verifications[expected.generation + 1].evidence
    return proposed.verification.evidence != installed


def _terminal_evidence(
    artifact: PaperAccountLineageArtifactEvidence,
    sequence: int,
) -> LineageHeadTerminalCheckpointEvidence:
    return LineageHeadTerminalCheckpointEvidence(
        artifact.artifact_id,
        artifact.sha256,
        artifact.byte_length,
        sequence,
    )


def _terminal_artifact(
    manifest: PaperAccountLineageManifest,
    evidence: PaperAccountLineageEvidence,
) -> PaperAccountLineageArtifact:
    for artifact in (
        manifest.genesis_checkpoint,
        *manifest.successor_checkpoints,
    ):
        if artifact.artifact_id == evidence.terminal_checkpoint_id:
            return artifact
    raise _blocked(LocalLineageHeadDiagnosticCode.TERMINAL_EVIDENCE_MISMATCH)


def _validate_authority_root(path: Path) -> _AuthorityRoot:
    if not isinstance(path, Path):
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT)
    absolute = Path(os.path.abspath(path))
    _require_safe_chain(absolute)
    try:
        retained = os.lstat(absolute)
    except OSError as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT) from error
    if not _real_directory(retained):
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT)
    _reject_casefold_entries(
        absolute,
        {
            CURRENT_HEAD_FILENAME,
            LINEAGE_MANIFEST_DIRECTORY,
            LINEAGE_HEAD_RECORD_DIRECTORY,
        },
        allow={
            CURRENT_HEAD_FILENAME,
            LINEAGE_MANIFEST_DIRECTORY,
            LINEAGE_HEAD_RECORD_DIRECTORY,
        },
    )
    return _AuthorityRoot(absolute, (retained.st_dev, retained.st_ino))


def _ensure_authority_directories(
    root: _AuthorityRoot,
) -> tuple[Path, Path]:
    paths = []
    for name in (LINEAGE_MANIFEST_DIRECTORY, LINEAGE_HEAD_RECORD_DIRECTORY):
        path = root.path / name
        if not _entry_exists(path):
            try:
                path.mkdir()
            except OSError as error:
                raise _blocked(
                    LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT
                ) from error
        paths.append(_require_child_directory(root, name))
    _require_directory_identity(root.path, root.identity)
    return paths[0], paths[1]


def _require_child_directory(root: _AuthorityRoot, name: str) -> Path:
    path = root.path / name
    try:
        retained = os.lstat(path)
    except OSError as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT) from error
    if not _real_directory(retained):
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT)
    try:
        _require_directory_identity(root.path, root.identity)
    except AtomicPointerReplacementError as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT) from error
    return path


def _ensure_immutable_file(path: Path, payload: bytes) -> None:
    if _entry_exists(path):
        try:
            if _safe_read(path, len(payload)) == payload:
                return
        except Exception:
            pass
        raise _conflicting(LocalLineageHeadDiagnosticCode.IMMUTABLE_ARTIFACT_CONFLICT)
    _reject_casefold_entries(path.parent, {path.name}, allow=set())
    staging = path.parent / f".{path.name}.staging"
    _reject_casefold_entries(path.parent, {staging.name}, allow=set())
    staging_identity = _write_exclusive_file(staging, payload)
    try:
        if _safe_read(staging, len(payload)) != payload:
            raise _blocked(LocalLineageHeadDiagnosticCode.IMMUTABLE_ARTIFACT_CONFLICT)
        try:
            os.link(staging, path, follow_symlinks=False)
        except OSError as error:
            raise _blocked(
                LocalLineageHeadDiagnosticCode.IMMUTABLE_ARTIFACT_CONFLICT
            ) from error
        if _safe_read(path, len(payload)) != payload:
            raise _blocked(LocalLineageHeadDiagnosticCode.IMMUTABLE_ARTIFACT_CONFLICT)
        try:
            staging.unlink()
        except OSError:
            # The immutable final is authoritative; leftover staging requires review.
            pass
    except Exception:
        if not _entry_exists(path):
            _remove_owned_regular_file(staging, staging_identity)
        raise


def _install_initial_pointer(root: _AuthorityRoot, payload: bytes) -> None:
    pointer = root.path / CURRENT_HEAD_FILENAME
    if _entry_exists(pointer):
        raise _blocked(LocalLineageHeadDiagnosticCode.POINTER_ALREADY_EXISTS)
    staging = root.path / f".{CURRENT_HEAD_FILENAME}.initializing"
    _reject_casefold_entries(root.path, {staging.name, pointer.name}, allow=set())
    staging_identity = _write_exclusive_file(staging, payload)
    try:
        if _safe_read(staging, len(payload)) != payload:
            raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_POINTER)
        parse_local_lineage_head_reference(payload)
        _require_directory_identity(root.path, root.identity)
        try:
            os.link(staging, pointer, follow_symlinks=False)
        except OSError as error:
            raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_POINTER) from error
        if _safe_read(pointer, len(payload)) != payload:
            raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_POINTER)
        try:
            staging.unlink()
        except OSError:
            pass
    except Exception:
        if not _entry_exists(pointer):
            _remove_owned_regular_file(staging, staging_identity)
        raise


def _write_exclusive_file(path: Path, payload: bytes) -> tuple[int, int]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags, 0o600)
    opened = os.fstat(descriptor)
    identity = (opened.st_dev, opened.st_ino)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            written = stream.write(payload)
            if written != len(payload):
                raise OSError("incomplete staging write")
            stream.flush()
            os.fsync(stream.fileno())
        return identity
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        _remove_owned_regular_file(path, identity)
        raise


def _safe_read(path: Path, maximum: int) -> bytes:
    return read_safe_regular_file(path, maximum, "local lineage-head artifact")


def _require_absolute_manifest_paths(payload: bytes) -> None:
    try:
        root = json.loads(payload.decode("utf-8"))
        entries = [
            root["genesis_checkpoint"],
            *root["successor_checkpoints"],
            *root["cycle_reports"],
            *root["snapshots"],
        ]
        if any(not Path(item["path"]).is_absolute() for item in entries):
            raise ValueError
    except Exception as error:
        raise _blocked(
            LocalLineageHeadDiagnosticCode.MANIFEST_VERIFICATION_FAILURE
        ) from error


def _reject_casefold_entries(
    directory: Path,
    names: set[str],
    *,
    allow: set[str],
) -> None:
    try:
        entries = list(os.scandir(directory))
    except OSError as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT) from error
    if len(entries) > MAX_AUTHORITY_DIRECTORY_ENTRIES:
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT)
    requested = {name.casefold(): name for name in names}
    allowed = {name.casefold(): name for name in allow}
    seen: set[str] = set()
    for entry in entries:
        folded = entry.name.casefold()
        if folded in seen:
            raise _conflicting(LocalLineageHeadDiagnosticCode.CASEFOLD_COLLISION)
        seen.add(folded)
        if folded in requested and (
            folded not in allowed or entry.name != allowed[folded]
        ):
            raise _conflicting(LocalLineageHeadDiagnosticCode.CASEFOLD_COLLISION)


def _require_safe_chain(path: Path) -> None:
    for item in (path, *path.parents):
        try:
            retained = os.lstat(item)
        except OSError as error:
            raise _blocked(
                LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT
            ) from error
        if stat.S_ISLNK(retained.st_mode) or _reparse(retained):
            raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT)


def _require_directory_identity(path: Path, expected: tuple[int, int]) -> None:
    try:
        retained = os.lstat(path)
    except OSError as error:
        raise AtomicPointerReplacementError("authority root is unavailable") from error
    if not _real_directory(retained) or (retained.st_dev, retained.st_ino) != expected:
        raise AtomicPointerReplacementError("authority root identity changed")


def _real_directory(value: os.stat_result) -> bool:
    return (
        stat.S_ISDIR(value.st_mode)
        and not stat.S_ISLNK(value.st_mode)
        and not _reparse(value)
    )


def _reparse(value: os.stat_result) -> bool:
    return bool(
        getattr(value, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _entry_exists(path: Path) -> bool:
    try:
        os.lstat(path)
        return True
    except FileNotFoundError:
        return False
    except OSError as error:
        raise _blocked(LocalLineageHeadDiagnosticCode.UNSAFE_AUTHORITY_ROOT) from error


def _remove_owned_regular_file(
    path: Path,
    expected_identity: tuple[int, int],
) -> None:
    try:
        retained = os.lstat(path)
        if (
            stat.S_ISREG(retained.st_mode)
            and not _reparse(retained)
            and (retained.st_dev, retained.st_ino) == expected_identity
        ):
            path.unlink()
    except OSError:
        pass


def _manifest_filename(evidence_id: UUID, digest: str) -> str:
    return f"paper-account-lineage-manifest-{evidence_id}-{digest}.json"


def _record_filename(record_id: UUID) -> str:
    return f"paper-account-lineage-head-record-{record_id}.json"


def _move_file_ex_replace_write_through(source: Path, destination: Path) -> None:
    try:
        import ctypes
        from ctypes import wintypes

        move = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        move.restype = wintypes.BOOL
        flags = 0x1 | 0x8  # MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
        if not move(str(source), str(destination), flags):
            error = ctypes.get_last_error()
            raise OSError(error, "MoveFileExW failed")
    except OSError:
        raise
    except Exception as error:
        raise AtomicPointerReplacementUnavailable(
            "Windows atomic replacement primitive is unavailable"
        ) from error


def _calendar():
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _blocked(code: LocalLineageHeadDiagnosticCode) -> _HeadFailure:
    return _HeadFailure(LocalLineageHeadClassification.BLOCKED, code)


def _conflicting(code: LocalLineageHeadDiagnosticCode) -> _HeadFailure:
    return _HeadFailure(LocalLineageHeadClassification.CONFLICTING, code)


def _print_result(result: LocalLineageHeadResult) -> None:
    print(f"classification: {result.classification.value}")
    print(f"diagnostic: {result.diagnostic.value}")
    if result.authority is not None:
        print(f"authority epoch ID: {result.authority.pointer.authority_epoch_id}")
        print(f"generation: {result.authority.pointer.generation}")
        print(f"head record ID: {result.authority.pointer.head_record_id}")
        evidence = result.authority.current_lineage.evidence
        if evidence is not None:
            print(f"lineage evidence ID: {evidence.evidence_id}")
            print(f"terminal checkpoint ID: {evidence.terminal_checkpoint_id}")


def _exit_code(result: LocalLineageHeadResult) -> int:
    if result.classification in (
        LocalLineageHeadClassification.PASS,
        LocalLineageHeadClassification.INITIALIZED,
        LocalLineageHeadClassification.ADVANCED,
    ):
        return 0
    if result.classification in (
        LocalLineageHeadClassification.STALE_EXPECTED_HEAD,
        LocalLineageHeadClassification.CONFLICTING,
    ):
        return 5
    if result.classification is LocalLineageHeadClassification.MANUAL_REVIEW_REQUIRED:
        return 8
    return 4


def verify_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify one explicitly referenced authoritative local lineage head."
    )
    parser.add_argument("--authority-root", required=True, type=Path)
    args = parser.parse_args(argv)
    result = verify_local_lineage_head(args.authority_root)
    _print_result(result)
    return _exit_code(result)


def initialize_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Initialize one authoritative local lineage head at genesis."
    )
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--authority-epoch-id", required=True, type=UUID)
    parser.add_argument("--lineage-manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    result = initialize_local_lineage_head(
        args.authority_root,
        args.authority_epoch_id,
        args.lineage_manifest,
    )
    _print_result(result)
    return _exit_code(result)


def advance_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Advance one authoritative local lineage head by one explicit edge."
    )
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--expected-head-reference", required=True, type=Path)
    parser.add_argument("--lineage-manifest", required=True, type=Path)
    parser.add_argument("--prior-checkpoint", required=True, type=Path)
    parser.add_argument("--cycle-report", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--successor-checkpoint", required=True, type=Path)
    parser.add_argument("--completed-receipt", required=True, type=Path)
    parser.add_argument("--cycle-configuration", required=True, type=Path)
    args = parser.parse_args(argv)
    result = advance_local_lineage_head(
        args.authority_root,
        expected_head_reference_path=args.expected_head_reference,
        lineage_manifest_path=args.lineage_manifest,
        prior_checkpoint_path=args.prior_checkpoint,
        cycle_report_path=args.cycle_report,
        snapshot_path=args.snapshot,
        successor_checkpoint_path=args.successor_checkpoint,
        completed_receipt_path=args.completed_receipt,
        cycle_configuration_path=args.cycle_configuration,
    )
    _print_result(result)
    return _exit_code(result)


if __name__ == "__main__":
    print(
        "invoke one of the dedicated local lineage-head scripts",
        file=sys.stderr,
    )
    raise SystemExit(2)
