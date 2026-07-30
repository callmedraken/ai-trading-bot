"""Safe immutable publication for guarded capture-readiness decisions."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from trading_bot.cli.checkpoint_transition_output import (
    OutputParent,
    validate_output_parent,
)
from trading_bot.runtime import (
    MAX_GUARDED_CAPTURE_READINESS_ARTIFACT_BYTES,
    ArtifactEvidence,
    ScheduledCaptureReadinessDecision,
    parse_scheduled_capture_readiness_decision,
    serialize_scheduled_capture_readiness_decision,
)

READINESS_DECISIONS_DIRECTORY = "readiness-decisions"
_MAX_AUDIT_ENTRIES = 10_000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_FINAL_NAME = re.compile(
    r"scheduled-capture-readiness-decision-[0-9a-f]{8}-"
    r"[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
    r"[0-9a-f]{12}\.json"
)


class DecisionEvidencePublicationError(RuntimeError):
    """Raised when immutable decision evidence cannot be safely published."""


class DecisionEvidencePublicationClassification(StrEnum):
    PUBLISHED = "PUBLISHED"
    IDEMPOTENT = "IDEMPOTENT"


@dataclass(frozen=True, slots=True)
class DecisionEvidencePublicationResult:
    classification: DecisionEvidencePublicationClassification
    path: Path
    artifact_reference: ArtifactEvidence


def publish_scheduled_capture_readiness_decision(
    audit_root: Path,
    decision: ScheduledCaptureReadinessDecision,
) -> DecisionEvidencePublicationResult:
    """Publish one canonical decision with same-parent no-clobber semantics."""
    if type(decision) is not ScheduledCaptureReadinessDecision:
        raise TypeError("decision must be ScheduledCaptureReadinessDecision")
    payload = serialize_scheduled_capture_readiness_decision(decision)
    decision_dir, parent_state = _validate_decision_directory(audit_root)
    _validate_existing_entries(decision_dir)
    final_name = f"scheduled-capture-readiness-decision-{decision.decision_id}.json"
    final_path = decision_dir / final_name
    evidence = ArtifactEvidence(
        decision.decision_id,
        hashlib.sha256(payload).hexdigest(),
        len(payload),
    )
    if final_path.exists():
        existing = _bounded_read(final_path)
        if existing != payload:
            raise DecisionEvidencePublicationError(
                "existing decision conflicts with requested bytes"
            )
        parsed = parse_scheduled_capture_readiness_decision(existing)
        if parsed != decision:
            raise DecisionEvidencePublicationError(
                "existing decision does not reconcile"
            )
        return DecisionEvidencePublicationResult(
            DecisionEvidencePublicationClassification.IDEMPOTENT,
            final_path,
            evidence,
        )
    staging_path = decision_dir / f".{final_name}.staging"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(staging_path, flags, 0o600)
    except FileExistsError as exc:
        raise DecisionEvidencePublicationError(
            "crash-left decision staging requires manual review"
        ) from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Invocation-owned staging is evidence and is intentionally preserved.
        raise
    staged = _bounded_read(staging_path)
    if staged != payload:
        raise DecisionEvidencePublicationError(
            "decision staging reread differs from intended bytes"
        )
    if parse_scheduled_capture_readiness_decision(staged) != decision:
        raise DecisionEvidencePublicationError("decision staging does not reconcile")
    if validate_output_parent(decision_dir) != parent_state:
        raise DecisionEvidencePublicationError(
            "decision parent identity changed before finalization"
        )
    try:
        os.link(staging_path, final_path)
    except FileExistsError as exc:
        existing = _bounded_read(final_path)
        if existing != payload:
            raise DecisionEvidencePublicationError(
                "no-clobber decision finalization found a conflict"
            ) from exc
    final_payload = _bounded_read(final_path)
    if final_payload != payload:
        raise DecisionEvidencePublicationError(
            "finalized decision differs from intended bytes"
        )
    if parse_scheduled_capture_readiness_decision(final_payload) != decision:
        raise DecisionEvidencePublicationError("finalized decision does not reconcile")
    if validate_output_parent(decision_dir) != parent_state:
        raise DecisionEvidencePublicationError(
            "decision parent identity changed after finalization"
        )
    try:
        staging = _assert_regular(staging_path)
        final = _assert_regular(final_path)
        if (staging.st_dev, staging.st_ino) != (final.st_dev, final.st_ino):
            raise DecisionEvidencePublicationError(
                "decision staging identity differs from final artifact"
            )
        staging_path.unlink()
    except FileNotFoundError as exc:
        raise DecisionEvidencePublicationError(
            "decision staging disappeared before verified finalization"
        ) from exc
    return DecisionEvidencePublicationResult(
        DecisionEvidencePublicationClassification.PUBLISHED,
        final_path,
        evidence,
    )


def _validate_decision_directory(root: Path) -> tuple[Path, OutputParent]:
    if not root.is_absolute():
        raise DecisionEvidencePublicationError("audit root must be absolute")
    root_state = validate_output_parent(root)
    entries = list(root.iterdir())
    if len(entries) > _MAX_AUDIT_ENTRIES:
        raise DecisionEvidencePublicationError("audit root has too many entries")
    folded = [entry.name.casefold() for entry in entries]
    if len(folded) != len(set(folded)):
        raise DecisionEvidencePublicationError(
            "audit root contains case-fold collisions"
        )
    collisions = [
        entry.name
        for entry in entries
        if entry.name.casefold() == READINESS_DECISIONS_DIRECTORY
        and entry.name != READINESS_DECISIONS_DIRECTORY
    ]
    if collisions:
        raise DecisionEvidencePublicationError(
            "audit root contains a readiness-decisions case collision"
        )
    decision_dir = root / READINESS_DECISIONS_DIRECTORY
    if decision_dir.exists():
        decision_state = validate_output_parent(decision_dir)
    else:
        try:
            os.mkdir(decision_dir)
        except FileExistsError:
            pass
        decision_state = validate_output_parent(decision_dir)
    if validate_output_parent(root) != root_state:
        raise DecisionEvidencePublicationError("audit root identity changed")
    return decision_dir, decision_state


def _validate_existing_entries(decision_dir: Path) -> None:
    entries = list(decision_dir.iterdir())
    if len(entries) > _MAX_AUDIT_ENTRIES:
        raise DecisionEvidencePublicationError(
            "readiness-decisions has too many entries"
        )
    folded = [entry.name.casefold() for entry in entries]
    if len(folded) != len(set(folded)):
        raise DecisionEvidencePublicationError(
            "readiness-decisions contains case-fold collisions"
        )
    for entry in entries:
        if _FINAL_NAME.fullmatch(entry.name) is None:
            raise DecisionEvidencePublicationError(
                f"readiness-decisions contains unexpected entry: {entry.name}"
            )
        try:
            decision = parse_scheduled_capture_readiness_decision(_bounded_read(entry))
        except ValueError as exc:
            raise DecisionEvidencePublicationError(
                f"existing decision is not canonical: {entry.name}"
            ) from exc
        expected = f"scheduled-capture-readiness-decision-{decision.decision_id}.json"
        if entry.name != expected:
            raise DecisionEvidencePublicationError(
                "existing decision filename does not match its canonical ID"
            )


def _bounded_read(path: Path) -> bytes:
    before = _assert_regular(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        held = os.fstat(stream.fileno())
        if _is_reparse(held) or not stat.S_ISREG(held.st_mode):
            raise DecisionEvidencePublicationError(
                "opened decision artifact is not a regular file"
            )
        if (before.st_dev, before.st_ino) != (held.st_dev, held.st_ino):
            raise DecisionEvidencePublicationError(
                "decision identity changed before bounded reread"
            )
        payload = stream.read(MAX_GUARDED_CAPTURE_READINESS_ARTIFACT_BYTES + 1)
    after = _assert_regular(path)
    if (held.st_dev, held.st_ino, held.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        raise DecisionEvidencePublicationError(
            "decision identity changed during reread"
        )
    if len(payload) > MAX_GUARDED_CAPTURE_READINESS_ARTIFACT_BYTES:
        raise DecisionEvidencePublicationError(
            "decision exceeds the bounded reread limit"
        )
    return payload


def _assert_regular(path: Path) -> os.stat_result:
    info = path.lstat()
    if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
        raise DecisionEvidencePublicationError(
            f"unsafe non-regular decision entry: {path}"
        )
    return info


def _is_reparse(value: os.stat_result) -> bool:
    return bool(getattr(value, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)
