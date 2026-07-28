"""Safe read-only inspection and classification of one local operation root."""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.cli.checkpoint_transition_output import (
    CheckpointTransitionConflictError,
    CheckpointTransitionOutputError,
    OutputParent,
    inspect_transition_directory,
    validate_output_parent,
)
from trading_bot.cli.paper_operation_config import VerifiedPaperOperationInputs
from trading_bot.runtime import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    MAX_PAPER_OPERATION_RECEIPT_BYTES,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
    PaperOperationReceipt,
    PaperOperationReceiptVerificationStatus,
    PaperOperationStatus,
    parse_checkpointed_paper_cycle_report,
    parse_paper_operation_receipt,
    parse_successor_paper_account_checkpoint,
    verify_paper_operation_receipt,
)

MAX_PAPER_OPERATION_ROOT_ENTRIES = 10_000
MAX_PAPER_OPERATION_DIRECTORY_ENTRIES = 4

_UUID_TEXT = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}"
)
_TRANSITION = re.compile(rf"^paper-account-transition-({_UUID_TEXT})$")
_TRANSITION_STAGING = re.compile(
    rf"^\.paper-account-transition-({_UUID_TEXT})\.staging$"
)
_OPERATION = re.compile(rf"^paper-operation-({_UUID_TEXT})$")
_OPERATION_STAGING = re.compile(rf"^\.paper-operation-({_UUID_TEXT})\.staging$")
_REPORT = re.compile(rf"^checkpointed-paper-cycle-report-({_UUID_TEXT})\.json$")
_CHECKPOINT = re.compile(rf"^paper-account-checkpoint-({_UUID_TEXT})\.json$")


class PaperOperationClassification(StrEnum):
    PENDING = "PENDING"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    CONFLICTING = "CONFLICTING"
    BLOCKED = "BLOCKED"


class PaperOperationInspectionCode(StrEnum):
    PENDING = "PENDING"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    CALLER_IDEMPOTENCY_CONFLICT = "CALLER_IDEMPOTENCY_CONFLICT"
    LINEAGE_CONFLICT = "LINEAGE_CONFLICT"
    STALE_TERMINAL_CHECKPOINT = "STALE_TERMINAL_CHECKPOINT"
    VALID_FAILED_RECEIPT = "VALID_FAILED_RECEIPT"
    FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE = (
        "FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE"
    )
    FOREIGN_TRANSITION_DEPENDENCIES_UNAVAILABLE = (
        "FOREIGN_TRANSITION_DEPENDENCIES_UNAVAILABLE"
    )
    INVALID_RECEIPT = "INVALID_RECEIPT"
    INVALID_FOREIGN_RECEIPT = "INVALID_FOREIGN_RECEIPT"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    FINALIZED_TRANSITION_WITHOUT_RECEIPT = "FINALIZED_TRANSITION_WITHOUT_RECEIPT"
    OPERATION_STAGING_EXISTS = "OPERATION_STAGING_EXISTS"
    TRANSITION_STAGING_EXISTS = "TRANSITION_STAGING_EXISTS"
    UNSAFE_OPERATION_ROOT = "UNSAFE_OPERATION_ROOT"
    ENUMERATION_LIMIT_EXCEEDED = "ENUMERATION_LIMIT_EXCEEDED"
    CASEFOLD_COLLISION = "CASEFOLD_COLLISION"
    MALFORMED_OPERATION_LAYOUT = "MALFORMED_OPERATION_LAYOUT"
    MALFORMED_TRANSITION_LAYOUT = "MALFORMED_TRANSITION_LAYOUT"
    AMBIGUOUS_OPERATION_STATE = "AMBIGUOUS_OPERATION_STATE"


@dataclass(frozen=True, slots=True)
class PaperOperationInspectionResult:
    classification: PaperOperationClassification
    operation_id: UUID
    terminal_checkpoint_id: UUID
    application_id: UUID
    receipt_path: Path | None
    diagnostics: tuple[PaperOperationInspectionCode, ...]

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not PaperOperationClassification
            or type(self.operation_id) is not UUID
            or type(self.terminal_checkpoint_id) is not UUID
            or type(self.application_id) is not UUID
            or (
                self.receipt_path is not None
                and not isinstance(self.receipt_path, Path)
            )
            or type(self.diagnostics) is not tuple
            or len(self.diagnostics) != 1
            or type(self.diagnostics[0]) is not PaperOperationInspectionCode
        ):
            raise ValueError("paper-operation inspection result is invalid")


@dataclass(frozen=True, slots=True)
class _Transition:
    application_id: UUID
    directory: Path
    report_path: Path
    checkpoint_path: Path
    report_payload: bytes
    checkpoint_payload: bytes
    request: object
    prior_checkpoint_id: UUID
    snapshot_artifact: PaperAccountLineageArtifactEvidence


@dataclass(frozen=True, slots=True)
class _Receipt:
    directory_id: UUID
    path: Path
    payload: bytes
    receipt: PaperOperationReceipt


def inspect_paper_operation_root(
    operation_root: Path,
    inputs: VerifiedPaperOperationInputs,
) -> PaperOperationInspectionResult:
    """Classify one exact operation without writing or executing a paper cycle."""
    if (
        not isinstance(operation_root, Path)
        or type(inputs) is not VerifiedPaperOperationInputs
    ):
        raise TypeError("paper-operation inspection arguments are invalid")
    try:
        parent = validate_output_parent(operation_root)
        root_entries = _enumerate(parent.path, MAX_PAPER_OPERATION_ROOT_ENTRIES)
        _require_parent_identity(parent)
    except _EnumerationLimit:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.ENUMERATION_LIMIT_EXCEEDED,
        )
    except Exception:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.UNSAFE_OPERATION_ROOT,
        )
    collision = _casefold_collision(root_entries)
    if collision:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.CASEFOLD_COLLISION,
        )
    transition_directories: dict[UUID, Path] = {}
    operations_path: Path | None = None
    for name in root_entries:
        path = parent.path / name
        if name.casefold() == "paper-operations":
            if (
                name != "paper-operations"
                or operations_path is not None
                or not _real_directory(path)
            ):
                return _result(
                    inputs,
                    PaperOperationClassification.BLOCKED,
                    None,
                    PaperOperationInspectionCode.UNSAFE_OPERATION_ROOT,
                )
            operations_path = path
            continue
        if name.casefold().startswith(".paper-account-transition-"):
            if _TRANSITION_STAGING.fullmatch(name) is None:
                return _result(
                    inputs,
                    PaperOperationClassification.BLOCKED,
                    None,
                    PaperOperationInspectionCode.MALFORMED_TRANSITION_LAYOUT,
                )
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.TRANSITION_STAGING_EXISTS,
            )
        if name.casefold().startswith("paper-account-transition-"):
            matched = _TRANSITION.fullmatch(name)
            if matched is None or not _real_directory(path):
                return _result(
                    inputs,
                    PaperOperationClassification.BLOCKED,
                    None,
                    PaperOperationInspectionCode.MALFORMED_TRANSITION_LAYOUT,
                )
            retained_id = UUID(matched.group(1))
            if retained_id in transition_directories:
                return _result(
                    inputs,
                    PaperOperationClassification.BLOCKED,
                    None,
                    PaperOperationInspectionCode.CASEFOLD_COLLISION,
                )
            transition_directories[retained_id] = path
    try:
        transitions = {
            application_id: _read_transition(path, application_id)
            for application_id, path in transition_directories.items()
        }
    except _InvalidTransition:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.INVALID_TRANSITION,
        )
    except Exception:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.MALFORMED_TRANSITION_LAYOUT,
        )
    try:
        receipts = _read_receipts(operations_path)
    except _EnumerationLimit:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.ENUMERATION_LIMIT_EXCEEDED,
        )
    except _Staging:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.OPERATION_STAGING_EXISTS,
        )
    except _Collision:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.CASEFOLD_COLLISION,
        )
    except _InvalidReceipt:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.INVALID_RECEIPT,
        )
    except Exception:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.MALFORMED_OPERATION_LAYOUT,
        )
    try:
        _require_parent_identity(parent)
    except Exception:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.UNSAFE_OPERATION_ROOT,
        )
    exact = next(
        (item for item in receipts if item.directory_id == inputs.intent.operation_id),
        None,
    )
    foreign_same_key = tuple(
        item
        for item in receipts
        if item.directory_id != inputs.intent.operation_id
        and item.receipt.intent.caller_idempotency_key
        == inputs.intent.caller_idempotency_key
    )
    for item in foreign_same_key:
        if not _foreign_dependencies_available(item.receipt, inputs):
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE,
            )
        candidate_transition = transitions.get(item.receipt.application_id)
        report_payload = None
        checkpoint_payload = None
        if item.receipt.status is PaperOperationStatus.COMPLETED:
            if candidate_transition is None:
                return _result(
                    inputs,
                    PaperOperationClassification.BLOCKED,
                    None,
                    PaperOperationInspectionCode.FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE,
                )
            report_payload = candidate_transition.report_payload
            checkpoint_payload = candidate_transition.checkpoint_payload
        verified = _verify_receipt(
            item,
            inputs,
            report_payload=report_payload,
            checkpoint_payload=checkpoint_payload,
        )
        if not verified:
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.INVALID_FOREIGN_RECEIPT,
            )
        return _result(
            inputs,
            PaperOperationClassification.CONFLICTING,
            item.path,
            PaperOperationInspectionCode.CALLER_IDEMPOTENCY_CONFLICT,
        )
    same_prior_foreign: list[_Transition] = []
    unavailable_foreign = False
    for application_id, transition in transitions.items():
        if application_id == inputs.application_id:
            continue
        if (
            transition.prior_checkpoint_id
            != inputs.intent.prior_lineage_evidence.terminal_checkpoint_id
        ):
            continue
        if transition.snapshot_artifact != inputs.intent.completed_snapshot_artifact:
            unavailable_foreign = True
            continue
        try:
            verified_transition = inspect_transition_directory(
                parent,
                application_id=str(application_id),
                prior_payload=inputs.terminal_checkpoint_payload,
                snapshot_payload=inputs.completed_snapshot_payload,
                calendar=_calendar_from_snapshot(inputs),
                expected_request=transition.request,
                verified_prior=inputs.verified_prior,
            )
        except (CheckpointTransitionOutputError, CheckpointTransitionConflictError):
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.INVALID_TRANSITION,
            )
        if verified_transition is None:
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.INVALID_TRANSITION,
            )
        same_prior_foreign.append(transition)
    if unavailable_foreign:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.FOREIGN_TRANSITION_DEPENDENCIES_UNAVAILABLE,
        )
    if len(same_prior_foreign) > 1:
        return _result(
            inputs,
            PaperOperationClassification.CONFLICTING,
            None,
            PaperOperationInspectionCode.LINEAGE_CONFLICT,
        )
    if exact is not None:
        if exact.receipt.receipt_id != exact.directory_id:
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.INVALID_RECEIPT,
            )
        candidate_transition = transitions.get(inputs.application_id)
        if exact.receipt.status is PaperOperationStatus.COMPLETED:
            if candidate_transition is None:
                return _result(
                    inputs,
                    PaperOperationClassification.BLOCKED,
                    None,
                    PaperOperationInspectionCode.INVALID_RECEIPT,
                )
            verified = _verify_receipt(
                exact,
                inputs,
                report_payload=candidate_transition.report_payload,
                checkpoint_payload=candidate_transition.checkpoint_payload,
            )
            if not verified:
                return _result(
                    inputs,
                    PaperOperationClassification.BLOCKED,
                    None,
                    PaperOperationInspectionCode.INVALID_RECEIPT,
                )
            if same_prior_foreign:
                return _result(
                    inputs,
                    PaperOperationClassification.CONFLICTING,
                    exact.path,
                    PaperOperationInspectionCode.LINEAGE_CONFLICT,
                )
            return _result(
                inputs,
                PaperOperationClassification.ALREADY_APPLIED,
                exact.path,
                PaperOperationInspectionCode.ALREADY_APPLIED,
            )
        if transitions.get(inputs.application_id) is not None:
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.AMBIGUOUS_OPERATION_STATE,
            )
        if not _verify_receipt(exact, inputs):
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.INVALID_RECEIPT,
            )
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            exact.path,
            PaperOperationInspectionCode.VALID_FAILED_RECEIPT,
        )
    requested_transition = transitions.get(inputs.application_id)
    if requested_transition is not None:
        try:
            verified_transition = inspect_transition_directory(
                parent,
                application_id=str(inputs.application_id),
                prior_payload=inputs.terminal_checkpoint_payload,
                snapshot_payload=inputs.completed_snapshot_payload,
                calendar=_calendar_from_snapshot(inputs),
                expected_request=inputs.request,
                verified_prior=inputs.verified_prior,
            )
        except (CheckpointTransitionOutputError, CheckpointTransitionConflictError):
            verified_transition = None
        if verified_transition is None:
            return _result(
                inputs,
                PaperOperationClassification.BLOCKED,
                None,
                PaperOperationInspectionCode.INVALID_TRANSITION,
            )
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT,
        )
    if same_prior_foreign:
        return _result(
            inputs,
            PaperOperationClassification.BLOCKED,
            None,
            PaperOperationInspectionCode.STALE_TERMINAL_CHECKPOINT,
        )
    return _result(
        inputs,
        PaperOperationClassification.PENDING,
        None,
        PaperOperationInspectionCode.PENDING,
    )


def _verify_receipt(
    retained: _Receipt,
    inputs: VerifiedPaperOperationInputs,
    *,
    report_payload: bytes | None = None,
    checkpoint_payload: bytes | None = None,
) -> bool:
    result = verify_paper_operation_receipt(
        retained.payload,
        cycle_configuration_payload=inputs.cycle_configuration_payload,
        prior_genesis_checkpoint=inputs.lineage_manifest.genesis_checkpoint,
        prior_successor_checkpoints=inputs.lineage_manifest.successor_checkpoints,
        prior_cycle_reports=inputs.lineage_manifest.cycle_reports,
        prior_snapshots=inputs.lineage_manifest.snapshots,
        completed_snapshot_payload=inputs.completed_snapshot_payload,
        calendar=_calendar_from_snapshot(inputs),
        transition_report_payload=report_payload,
        successor_checkpoint_payload=checkpoint_payload,
    )
    return result.status is PaperOperationReceiptVerificationStatus.PASS


def _foreign_dependencies_available(
    receipt: PaperOperationReceipt,
    inputs: VerifiedPaperOperationInputs,
) -> bool:
    return (
        receipt.intent.prior_lineage_evidence == inputs.intent.prior_lineage_evidence
        and receipt.intent.terminal_checkpoint_artifact
        == inputs.intent.terminal_checkpoint_artifact
        and receipt.intent.completed_snapshot_artifact
        == inputs.intent.completed_snapshot_artifact
        and receipt.intent.cycle_configuration_artifact
        == inputs.intent.cycle_configuration_artifact
    )


def _read_transition(path: Path, application_id: UUID) -> _Transition:
    names = _enumerate(path, MAX_PAPER_OPERATION_DIRECTORY_ENTRIES)
    if len(names) != 2 or _casefold_collision(names):
        raise ValueError("transition layout is invalid")
    report_names = tuple(name for name in names if _REPORT.fullmatch(name))
    checkpoint_names = tuple(name for name in names if _CHECKPOINT.fullmatch(name))
    if len(report_names) != 1 or len(checkpoint_names) != 1:
        raise ValueError("transition layout is invalid")
    report_path = path / report_names[0]
    checkpoint_path = path / checkpoint_names[0]
    report_payload = read_safe_regular_file(
        report_path,
        MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
        "transition report",
    )
    checkpoint_payload = read_safe_regular_file(
        checkpoint_path,
        MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
        "successor checkpoint",
    )
    try:
        report = parse_checkpointed_paper_cycle_report(report_payload)
        checkpoint = parse_successor_paper_account_checkpoint(checkpoint_payload)
    except ValueError as error:
        raise _InvalidTransition from error
    snapshot = report.evidence.request.snapshot_reference
    if (
        report_names[0]
        != (f"checkpointed-paper-cycle-report-{report.evidence.cycle_result_id}.json")
        or checkpoint_names[0]
        != f"paper-account-checkpoint-{checkpoint.checkpoint_id}.json"
        or report.evidence.application_id != application_id
        or checkpoint.application_id != application_id
    ):
        raise _InvalidTransition
    return _Transition(
        application_id,
        path,
        report_path,
        checkpoint_path,
        report_payload,
        checkpoint_payload,
        report.evidence.request,
        checkpoint.prior_checkpoint.checkpoint_id,
        PaperAccountLineageArtifactEvidence(
            PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
            snapshot.snapshot_id,
            snapshot.artifact_sha256,
            snapshot.artifact_byte_length,
        ),
    )


def _read_receipts(operations_path: Path | None) -> tuple[_Receipt, ...]:
    if operations_path is None:
        return ()
    names = _enumerate(operations_path, MAX_PAPER_OPERATION_ROOT_ENTRIES)
    if _casefold_collision(names):
        raise _Collision
    receipts: list[_Receipt] = []
    for name in names:
        path = operations_path / name
        if name.casefold().startswith(".paper-operation-"):
            if _OPERATION_STAGING.fullmatch(name) is None:
                raise ValueError("operation staging name is malformed")
            raise _Staging
        if not name.casefold().startswith("paper-operation-"):
            raise ValueError("unexpected paper-operations entry")
        matched = _OPERATION.fullmatch(name)
        if matched is None or not _real_directory(path):
            raise ValueError("operation directory is malformed")
        directory_id = UUID(matched.group(1))
        contents = _enumerate(path, MAX_PAPER_OPERATION_DIRECTORY_ENTRIES)
        expected_name = f"paper-operation-receipt-{directory_id}.json"
        if contents != (expected_name,):
            raise ValueError("operation directory contents are invalid")
        receipt_path = path / expected_name
        try:
            payload = read_safe_regular_file(
                receipt_path,
                MAX_PAPER_OPERATION_RECEIPT_BYTES,
                "paper-operation receipt",
            )
            receipt = parse_paper_operation_receipt(payload)
        except Exception as error:
            raise _InvalidReceipt from error
        if receipt.receipt_id != directory_id:
            raise ValueError("receipt directory identity is invalid")
        receipts.append(_Receipt(directory_id, receipt_path, payload, receipt))
    return tuple(receipts)


def _enumerate(path: Path, maximum: int) -> tuple[str, ...]:
    before = os.lstat(path)
    if not _real_directory_stat(before):
        raise ValueError("directory is unsafe")
    names: list[str] = []
    with os.scandir(path) as entries:
        for entry in entries:
            names.append(entry.name)
            if len(names) > maximum:
                raise _EnumerationLimit
    after = os.lstat(path)
    if not _real_directory_stat(after) or (before.st_dev, before.st_ino) != (
        after.st_dev,
        after.st_ino,
    ):
        raise ValueError("directory changed during enumeration")
    return tuple(sorted(names))


def _casefold_collision(names: tuple[str, ...]) -> bool:
    folded = tuple(name.casefold() for name in names)
    return len(set(folded)) != len(folded)


def _real_directory(path: Path) -> bool:
    try:
        return _real_directory_stat(os.lstat(path))
    except OSError:
        return False


def _real_directory_stat(value: os.stat_result) -> bool:
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


def _require_parent_identity(parent: OutputParent) -> None:
    retained = os.lstat(parent.path)
    if not _real_directory_stat(retained) or (retained.st_dev, retained.st_ino) != (
        parent.device,
        parent.inode,
    ):
        raise ValueError("operation root identity changed")


def _calendar_from_snapshot(inputs: VerifiedPaperOperationInputs):
    return inputs.calendar


def _result(
    inputs: VerifiedPaperOperationInputs,
    classification: PaperOperationClassification,
    receipt_path: Path | None,
    code: PaperOperationInspectionCode,
) -> PaperOperationInspectionResult:
    return PaperOperationInspectionResult(
        classification,
        inputs.intent.operation_id,
        inputs.intent.prior_lineage_evidence.terminal_checkpoint_id,
        inputs.application_id,
        receipt_path,
        (code,),
    )


class _EnumerationLimit(Exception):
    pass


class _Staging(Exception):
    pass


class _Collision(Exception):
    pass


class _InvalidReceipt(Exception):
    pass


class _InvalidTransition(Exception):
    pass
