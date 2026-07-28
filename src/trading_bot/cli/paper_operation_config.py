"""Strict explicit input loading for read-only paper-operation inspection."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import (
    MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_BYTES,
    PaperAccountLineageManifest,
    load_paper_account_lineage_manifest,
    read_safe_regular_file,
)
from trading_bot.cli.checkpoint_transition_config import (
    MAX_CHECKPOINT_TRANSITION_CONFIG_BYTES,
    CheckpointTransitionConfigValidationError,
    parse_checkpoint_transition_config,
)
from trading_bot.market_data import (
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    DailySnapshotVerificationResult,
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    verify_daily_snapshot,
)
from trading_bot.runtime import (
    MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationResult,
    PaperAccountLineageVerificationStatus,
    PaperOperationArtifactEvidence,
    PaperOperationIntent,
    VerifiedPriorCheckpoint,
    create_paper_operation_intent,
    derive_checkpointed_verified_snapshot_application_id,
    verified_prior_from_full_lineage,
    verify_paper_account_lineage,
)

PAPER_OPERATION_CONFIG_SCHEMA_VERSION = 1
MAX_PAPER_OPERATION_CONFIG_BYTES = 256 * 1024
MAX_PAPER_OPERATION_PATH_CHARACTERS = 4096

_ROOT_FIELDS = {
    "schema_version",
    "caller_idempotency_key",
    "prior_lineage_manifest",
    "terminal_checkpoint",
    "completed_snapshot",
    "cycle_configuration",
}
_ARTIFACT_FIELDS = {"artifact_id", "path", "sha256", "byte_length"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PaperOperationConfigReadError(Exception):
    """Raised when configuration or an explicit dependency cannot be read safely."""


class PaperOperationConfigSyntaxError(Exception):
    """Raised when operation configuration is not bounded strict JSON."""


class PaperOperationConfigValidationError(ValueError):
    """Raised when the exact operation configuration schema is invalid."""


class PaperOperationInputVerificationCode(StrEnum):
    MANIFEST_EVIDENCE_MISMATCH = "MANIFEST_EVIDENCE_MISMATCH"
    PRIOR_LINEAGE_VERIFICATION_FAILED = "PRIOR_LINEAGE_VERIFICATION_FAILED"
    PRIOR_LINEAGE_ID_MISMATCH = "PRIOR_LINEAGE_ID_MISMATCH"
    TERMINAL_CHECKPOINT_MISMATCH = "TERMINAL_CHECKPOINT_MISMATCH"
    SNAPSHOT_EVIDENCE_MISMATCH = "SNAPSHOT_EVIDENCE_MISMATCH"
    SNAPSHOT_VERIFICATION_FAILED = "SNAPSHOT_VERIFICATION_FAILED"
    CYCLE_CONFIGURATION_EVIDENCE_MISMATCH = "CYCLE_CONFIGURATION_EVIDENCE_MISMATCH"
    CYCLE_CONFIGURATION_INVALID = "CYCLE_CONFIGURATION_INVALID"
    CYCLE_CONFIGURATION_ID_MISMATCH = "CYCLE_CONFIGURATION_ID_MISMATCH"
    CYCLE_SNAPSHOT_REFERENCE_MISMATCH = "CYCLE_SNAPSHOT_REFERENCE_MISMATCH"


class PaperOperationInputVerificationError(Exception):
    """Raised with one stable code when explicit dependencies do not verify."""

    def __init__(self, code: PaperOperationInputVerificationCode) -> None:
        if type(code) is not PaperOperationInputVerificationCode:
            raise TypeError("input verification code is invalid")
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class PaperOperationArtifactReference:
    """One exact explicit artifact reference with a transport-only path."""

    artifact_id: UUID
    path: Path
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if (
            type(self.artifact_id) is not UUID
            or not isinstance(self.path, Path)
            or not self.path.is_absolute()
            or type(self.sha256) is not str
            or _SHA256.fullmatch(self.sha256) is None
            or type(self.byte_length) is not int
            or self.byte_length <= 0
        ):
            raise PaperOperationConfigValidationError("artifact reference is invalid")


@dataclass(frozen=True, slots=True)
class PaperOperationConfig:
    schema_version: int
    caller_idempotency_key: UUID
    prior_lineage_manifest: PaperOperationArtifactReference
    terminal_checkpoint: PaperOperationArtifactReference
    completed_snapshot: PaperOperationArtifactReference
    cycle_configuration: PaperOperationArtifactReference

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != PAPER_OPERATION_CONFIG_SCHEMA_VERSION
            or type(self.caller_idempotency_key) is not UUID
            or any(
                type(value) is not PaperOperationArtifactReference
                for value in (
                    self.prior_lineage_manifest,
                    self.terminal_checkpoint,
                    self.completed_snapshot,
                    self.cycle_configuration,
                )
            )
        ):
            raise PaperOperationConfigValidationError(
                "paper-operation configuration is invalid"
            )


@dataclass(frozen=True, slots=True)
class VerifiedPaperOperationInputs:
    config: PaperOperationConfig
    intent: PaperOperationIntent
    application_id: UUID
    lineage_manifest: PaperAccountLineageManifest
    prior_lineage_verification: PaperAccountLineageVerificationResult
    verified_prior: VerifiedPriorCheckpoint
    terminal_checkpoint_payload: bytes
    completed_snapshot_payload: bytes
    snapshot_verification: DailySnapshotVerificationResult
    cycle_configuration_payload: bytes
    request: CheckpointedVerifiedSnapshotPaperCycleRequest
    calendar: IdentifiedMarketCalendar


def load_paper_operation_config(path: Path) -> PaperOperationConfig:
    """Safely read and strictly parse one operation configuration."""
    try:
        payload = read_safe_regular_file(
            path, MAX_PAPER_OPERATION_CONFIG_BYTES, "operation configuration"
        )
    except Exception as error:
        raise PaperOperationConfigReadError(
            "operation configuration cannot be read safely"
        ) from error
    return parse_paper_operation_config(payload, base_directory=_absolute(path).parent)


def parse_paper_operation_config(
    payload: bytes,
    *,
    base_directory: Path,
) -> PaperOperationConfig:
    """Parse strict schema-1 bytes and resolve transport paths against one base."""
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_PAPER_OPERATION_CONFIG_BYTES
    ):
        raise PaperOperationConfigReadError(
            "operation configuration bytes are invalid or exceed bounds"
        )
    if not isinstance(base_directory, Path):
        raise PaperOperationConfigValidationError("base directory is invalid")
    root = _object(_json(payload), _ROOT_FIELDS, "root")
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != PAPER_OPERATION_CONFIG_SCHEMA_VERSION
    ):
        raise PaperOperationConfigValidationError("schema_version must be 1")
    base = _absolute(base_directory)
    return PaperOperationConfig(
        PAPER_OPERATION_CONFIG_SCHEMA_VERSION,
        _uuid(root["caller_idempotency_key"], "caller_idempotency_key"),
        _artifact(root["prior_lineage_manifest"], "prior_lineage_manifest", base),
        _artifact(root["terminal_checkpoint"], "terminal_checkpoint", base),
        _artifact(root["completed_snapshot"], "completed_snapshot", base),
        _artifact(root["cycle_configuration"], "cycle_configuration", base),
    )


def load_verified_paper_operation_inputs(
    config_path: Path,
    calendar: IdentifiedMarketCalendar,
) -> VerifiedPaperOperationInputs:
    """Load and verify every explicit dependency without executing a paper cycle."""
    config = load_paper_operation_config(config_path)
    manifest_payload = _read_reference(
        config.prior_lineage_manifest,
        MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_BYTES,
        PaperOperationInputVerificationCode.MANIFEST_EVIDENCE_MISMATCH,
    )
    try:
        manifest = load_paper_account_lineage_manifest(
            config.prior_lineage_manifest.path
        )
    except Exception as error:
        raise PaperOperationConfigReadError(
            "prior-lineage manifest cannot be loaded safely"
        ) from error
    repeated_manifest = _read_reference(
        config.prior_lineage_manifest,
        MAX_PAPER_ACCOUNT_LINEAGE_MANIFEST_BYTES,
        PaperOperationInputVerificationCode.MANIFEST_EVIDENCE_MISMATCH,
    )
    if repeated_manifest != manifest_payload:
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.MANIFEST_EVIDENCE_MISMATCH
        )
    lineage = verify_paper_account_lineage(
        manifest.genesis_checkpoint,
        manifest.terminal_checkpoint_id,
        manifest.successor_checkpoints,
        manifest.cycle_reports,
        manifest.snapshots,
        calendar,
    )
    if (
        lineage.status is not PaperAccountLineageVerificationStatus.PASS
        or lineage.evidence is None
    ):
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.PRIOR_LINEAGE_VERIFICATION_FAILED
        )
    if lineage.evidence.evidence_id != config.prior_lineage_manifest.artifact_id:
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.PRIOR_LINEAGE_ID_MISMATCH
        )
    terminal_evidence = lineage.evidence.checkpoint_artifacts[-1]
    terminal_maximum = (
        MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES
        if terminal_evidence.kind is PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT
        else MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES
    )
    terminal_payload = _read_reference(
        config.terminal_checkpoint,
        terminal_maximum,
        PaperOperationInputVerificationCode.TERMINAL_CHECKPOINT_MISMATCH,
    )
    terminal_artifact = _terminal_artifact(manifest)
    if (
        config.terminal_checkpoint.artifact_id != terminal_evidence.artifact_id
        or config.terminal_checkpoint.sha256 != terminal_evidence.sha256
        or config.terminal_checkpoint.byte_length != terminal_evidence.byte_length
        or terminal_artifact is None
        or terminal_artifact.payload != terminal_payload
    ):
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.TERMINAL_CHECKPOINT_MISMATCH
        )
    snapshot_payload = _read_reference(
        config.completed_snapshot,
        MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
        PaperOperationInputVerificationCode.SNAPSHOT_EVIDENCE_MISMATCH,
    )
    snapshot = verify_daily_snapshot(
        snapshot_payload,
        calendar,
        expected_sha256=config.completed_snapshot.sha256,
        expected_byte_length=config.completed_snapshot.byte_length,
    )
    if (
        snapshot.status is not DailySnapshotVerificationStatus.PASS
        or snapshot.snapshot is None
    ):
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.SNAPSHOT_VERIFICATION_FAILED
        )
    if snapshot.snapshot.snapshot_id != config.completed_snapshot.artifact_id:
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.SNAPSHOT_EVIDENCE_MISMATCH
        )
    cycle_payload = _read_reference(
        config.cycle_configuration,
        MAX_CHECKPOINT_TRANSITION_CONFIG_BYTES,
        PaperOperationInputVerificationCode.CYCLE_CONFIGURATION_EVIDENCE_MISMATCH,
    )
    try:
        request = parse_checkpoint_transition_config(cycle_payload).request
    except (CheckpointTransitionConfigValidationError, ValueError) as error:
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.CYCLE_CONFIGURATION_INVALID
        ) from error
    if request.request_id != config.cycle_configuration.artifact_id:
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.CYCLE_CONFIGURATION_ID_MISMATCH
        )
    configured_snapshot_evidence = PaperAccountLineageArtifactEvidence(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        config.completed_snapshot.artifact_id,
        config.completed_snapshot.sha256,
        config.completed_snapshot.byte_length,
    )
    if (
        request.snapshot_reference.snapshot_id
        != configured_snapshot_evidence.artifact_id
        or request.snapshot_reference.artifact_sha256
        != configured_snapshot_evidence.sha256
        or request.snapshot_reference.artifact_byte_length
        != configured_snapshot_evidence.byte_length
    ):
        raise PaperOperationInputVerificationError(
            PaperOperationInputVerificationCode.CYCLE_SNAPSHOT_REFERENCE_MISMATCH
        )
    intent = create_paper_operation_intent(
        config.caller_idempotency_key,
        lineage.evidence,
        terminal_evidence,
        configured_snapshot_evidence,
        PaperOperationArtifactEvidence(
            config.cycle_configuration.sha256,
            config.cycle_configuration.byte_length,
        ),
        request,
    )
    verified_prior = verified_prior_from_full_lineage(lineage)
    return VerifiedPaperOperationInputs(
        config,
        intent,
        derive_checkpointed_verified_snapshot_application_id(
            lineage.evidence.terminal_checkpoint_id,
            request.request_id,
        ),
        manifest,
        lineage,
        verified_prior,
        terminal_payload,
        snapshot_payload,
        snapshot,
        cycle_payload,
        request,
        calendar,
    )


def _read_reference(
    reference: PaperOperationArtifactReference,
    maximum: int,
    code: PaperOperationInputVerificationCode,
) -> bytes:
    try:
        payload = read_safe_regular_file(reference.path, maximum, "operation artifact")
    except Exception as error:
        raise PaperOperationConfigReadError(
            "explicit operation artifact cannot be read safely"
        ) from error
    if (
        len(payload) != reference.byte_length
        or sha256(payload).hexdigest() != reference.sha256
    ):
        raise PaperOperationInputVerificationError(code)
    return payload


def _terminal_artifact(manifest: PaperAccountLineageManifest):
    for artifact in (manifest.genesis_checkpoint, *manifest.successor_checkpoints):
        if artifact.artifact_id == manifest.terminal_checkpoint_id:
            return artifact
    return None


def _artifact(
    value: object,
    label: str,
    base: Path,
) -> PaperOperationArtifactReference:
    raw = _object(value, _ARTIFACT_FIELDS, label)
    path_text = _path(raw["path"], f"{label}.path")
    path = Path(path_text)
    if not path.is_absolute():
        path = base / path
    length = raw["byte_length"]
    if type(length) is not int or length <= 0:
        raise PaperOperationConfigValidationError(
            f"{label}.byte_length must be a positive integer"
        )
    digest = _string(raw["sha256"], f"{label}.sha256")
    if _SHA256.fullmatch(digest) is None:
        raise PaperOperationConfigValidationError(
            f"{label}.sha256 must be lowercase SHA-256 text"
        )
    return PaperOperationArtifactReference(
        _uuid(raw["artifact_id"], f"{label}.artifact_id"),
        _absolute(path),
        digest,
        length,
    )


def _json(payload: bytes) -> object:
    if payload.startswith(b"\xef\xbb\xbf"):
        raise PaperOperationConfigSyntaxError("configuration BOM is not permitted")
    try:
        return json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicates,
            parse_float=_float,
            parse_constant=_constant,
        )
    except PaperOperationConfigSyntaxError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PaperOperationConfigSyntaxError(
            "configuration is not strict UTF-8 JSON"
        ) from error


def _duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PaperOperationConfigSyntaxError("duplicate configuration key")
        result[key] = value
    return result


def _float(_: str) -> None:
    raise PaperOperationConfigSyntaxError("JSON floats are not permitted")


def _constant(_: str) -> None:
    raise PaperOperationConfigSyntaxError("JSON constants are not permitted")


def _object(value: object, fields: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise PaperOperationConfigValidationError(f"{label} fields are invalid")
    return value


def _string(value: object, label: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > MAX_PAPER_OPERATION_PATH_CHARACTERS
    ):
        raise PaperOperationConfigValidationError(f"{label} is invalid")
    return value


def _path(value: object, label: str) -> str:
    text = _string(value, label)
    if (
        text != text.strip()
        or "\x00" in text
        or any(ord(character) < 32 for character in text)
    ):
        raise PaperOperationConfigValidationError(f"{label} is unsafe")
    return text


def _uuid(value: object, label: str) -> UUID:
    text = _string(value, label)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise PaperOperationConfigValidationError(
            f"{label} must be canonical UUID text"
        ) from error
    if str(parsed) != text:
        raise PaperOperationConfigValidationError(
            f"{label} must be canonical UUID text"
        )
    return parsed


def _absolute(path: Path) -> Path:
    try:
        return Path(os.path.abspath(path))
    except (OSError, ValueError) as error:
        raise PaperOperationConfigValidationError("path is invalid") from error
