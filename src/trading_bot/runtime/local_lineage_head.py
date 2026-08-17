"""Deterministic immutable records for one authoritative local lineage head."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

PAPER_ACCOUNT_LINEAGE_HEAD_RECORD_SCHEMA_VERSION = 1
LOCAL_LINEAGE_HEAD_REFERENCE_SCHEMA_VERSION = 1
PAPER_ACCOUNT_LINEAGE_HEAD_RECORD_MATERIAL_VERSION = (
    "paper-account-lineage-head-record-v1"
)
PAPER_ACCOUNT_LINEAGE_HEAD_RECORD_NAMESPACE = UUID(
    "2be0b50b-d4d7-587f-bd3e-69a4970dd0f4"
)
MAX_LOCAL_LINEAGE_HEAD_RECORD_BYTES = 64 * 1024
MAX_LOCAL_LINEAGE_HEAD_REFERENCE_BYTES = 16 * 1024
MAX_LOCAL_LINEAGE_HEAD_INTEGER = (1 << 63) - 1

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECORD_FIELDS = {
    "schema_version",
    "record_id",
    "authority_epoch_id",
    "generation",
    "previous_head_record",
    "lineage_manifest",
    "verified_lineage_evidence_id",
    "terminal_checkpoint",
    "advancement_cause",
}
_POINTER_FIELDS = {
    "schema_version",
    "authority_epoch_id",
    "generation",
    "head_record_id",
    "head_record_sha256",
    "head_record_byte_length",
}


class LocalLineageHeadError(Exception):
    """Base error for immutable local lineage-head values."""


class LocalLineageHeadSyntaxError(LocalLineageHeadError, ValueError):
    """Raised when bounded UTF-8 JSON cannot be decoded."""


class LocalLineageHeadSchemaError(LocalLineageHeadError, ValueError):
    """Raised when decoded values violate the strict canonical schema."""


class LineageHeadAdvancementCauseKind(StrEnum):
    GENESIS = "GENESIS"
    COMPLETED_OPERATION = "COMPLETED_OPERATION"
    APPROVED_MANUAL_RECOVERY = "APPROVED_MANUAL_RECOVERY"


@dataclass(frozen=True, slots=True)
class LineageHeadRecordReference:
    head_record_id: UUID
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        _require_uuid(self.head_record_id, "head_record_id")
        _require_evidence(self.sha256, self.byte_length, "head-record")


@dataclass(frozen=True, slots=True)
class LineageManifestEvidence:
    artifact_id: UUID
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        _require_uuid(self.artifact_id, "lineage manifest artifact_id")
        _require_evidence(self.sha256, self.byte_length, "lineage manifest")


@dataclass(frozen=True, slots=True)
class LineageHeadTerminalCheckpointEvidence:
    checkpoint_id: UUID
    sha256: str
    byte_length: int
    sequence: int

    def __post_init__(self) -> None:
        _require_uuid(self.checkpoint_id, "terminal checkpoint_id")
        _require_evidence(self.sha256, self.byte_length, "terminal checkpoint")
        _require_nonnegative_integer(self.sequence, "terminal sequence")


@dataclass(frozen=True, slots=True)
class LineageHeadAdvancementCauseEvidence:
    artifact_id: UUID
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        _require_uuid(self.artifact_id, "advancement-cause artifact_id")
        _require_evidence(self.sha256, self.byte_length, "advancement cause")


@dataclass(frozen=True, slots=True)
class PaperAccountLineageHeadRecord:
    schema_version: int
    record_id: UUID
    authority_epoch_id: UUID
    generation: int
    previous_head_record: LineageHeadRecordReference | None
    lineage_manifest: LineageManifestEvidence
    verified_lineage_evidence_id: UUID
    terminal_checkpoint: LineageHeadTerminalCheckpointEvidence
    advancement_cause_kind: LineageHeadAdvancementCauseKind
    advancement_cause: LineageHeadAdvancementCauseEvidence

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != PAPER_ACCOUNT_LINEAGE_HEAD_RECORD_SCHEMA_VERSION
        ):
            raise LocalLineageHeadSchemaError("head-record schema_version must be 1")
        _require_uuid(self.record_id, "record_id")
        _require_uuid(self.authority_epoch_id, "authority_epoch_id")
        _require_nonnegative_integer(self.generation, "generation")
        if self.previous_head_record is not None and (
            type(self.previous_head_record) is not LineageHeadRecordReference
        ):
            raise LocalLineageHeadSchemaError(
                "previous_head_record must be exact evidence or genesis"
            )
        if type(self.lineage_manifest) is not LineageManifestEvidence:
            raise LocalLineageHeadSchemaError("lineage_manifest evidence is invalid")
        _require_uuid(
            self.verified_lineage_evidence_id,
            "verified_lineage_evidence_id",
        )
        if type(self.terminal_checkpoint) is not LineageHeadTerminalCheckpointEvidence:
            raise LocalLineageHeadSchemaError("terminal_checkpoint evidence is invalid")
        if type(self.advancement_cause_kind) is not LineageHeadAdvancementCauseKind:
            raise LocalLineageHeadSchemaError("advancement cause kind is invalid")
        if type(self.advancement_cause) is not LineageHeadAdvancementCauseEvidence:
            raise LocalLineageHeadSchemaError("advancement cause evidence is invalid")
        if self.lineage_manifest.artifact_id != self.verified_lineage_evidence_id:
            raise LocalLineageHeadSchemaError(
                "manifest artifact ID must equal verified lineage evidence ID"
            )
        if self.generation == 0:
            if (
                self.previous_head_record is not None
                or self.advancement_cause_kind
                is not LineageHeadAdvancementCauseKind.GENESIS
                or self.terminal_checkpoint.sequence != 0
                or self.advancement_cause.artifact_id
                != self.terminal_checkpoint.checkpoint_id
                or self.advancement_cause.sha256 != self.terminal_checkpoint.sha256
                or self.advancement_cause.byte_length
                != self.terminal_checkpoint.byte_length
            ):
                raise LocalLineageHeadSchemaError(
                    "generation zero must be rooted in the exact genesis checkpoint"
                )
        elif (
            self.previous_head_record is None
            or self.advancement_cause_kind is LineageHeadAdvancementCauseKind.GENESIS
        ):
            raise LocalLineageHeadSchemaError(
                "later generations require a predecessor and non-genesis cause"
            )
        expected = derive_paper_account_lineage_head_record_id(
            self.authority_epoch_id,
            self.generation,
            self.previous_head_record,
            self.lineage_manifest,
            self.verified_lineage_evidence_id,
            self.terminal_checkpoint,
            self.advancement_cause_kind,
            self.advancement_cause,
        )
        if self.record_id != expected:
            raise LocalLineageHeadSchemaError(
                "record_id does not match canonical head-record material"
            )


@dataclass(frozen=True, slots=True)
class LocalLineageHeadReference:
    schema_version: int
    authority_epoch_id: UUID
    generation: int
    head_record_id: UUID
    head_record_sha256: str
    head_record_byte_length: int

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != LOCAL_LINEAGE_HEAD_REFERENCE_SCHEMA_VERSION
        ):
            raise LocalLineageHeadSchemaError("current-head schema_version must be 1")
        _require_uuid(self.authority_epoch_id, "authority_epoch_id")
        _require_nonnegative_integer(self.generation, "generation")
        _require_uuid(self.head_record_id, "head_record_id")
        _require_evidence(
            self.head_record_sha256,
            self.head_record_byte_length,
            "head record",
        )


def create_paper_account_lineage_head_record(
    authority_epoch_id: UUID,
    generation: int,
    previous_head_record: LineageHeadRecordReference | None,
    lineage_manifest: LineageManifestEvidence,
    verified_lineage_evidence_id: UUID,
    terminal_checkpoint: LineageHeadTerminalCheckpointEvidence,
    advancement_cause_kind: LineageHeadAdvancementCauseKind,
    advancement_cause: LineageHeadAdvancementCauseEvidence,
) -> PaperAccountLineageHeadRecord:
    """Create one immutable record from complete explicit canonical material."""
    record_id = derive_paper_account_lineage_head_record_id(
        authority_epoch_id,
        generation,
        previous_head_record,
        lineage_manifest,
        verified_lineage_evidence_id,
        terminal_checkpoint,
        advancement_cause_kind,
        advancement_cause,
    )
    return PaperAccountLineageHeadRecord(
        PAPER_ACCOUNT_LINEAGE_HEAD_RECORD_SCHEMA_VERSION,
        record_id,
        authority_epoch_id,
        generation,
        previous_head_record,
        lineage_manifest,
        verified_lineage_evidence_id,
        terminal_checkpoint,
        advancement_cause_kind,
        advancement_cause,
    )


def derive_paper_account_lineage_head_record_id(
    authority_epoch_id: UUID,
    generation: int,
    previous_head_record: LineageHeadRecordReference | None,
    lineage_manifest: LineageManifestEvidence,
    verified_lineage_evidence_id: UUID,
    terminal_checkpoint: LineageHeadTerminalCheckpointEvidence,
    advancement_cause_kind: LineageHeadAdvancementCauseKind,
    advancement_cause: LineageHeadAdvancementCauseEvidence,
) -> UUID:
    """Derive the schema-1 UUID5 from path-free length-framed material."""
    _require_uuid(authority_epoch_id, "authority_epoch_id")
    _require_nonnegative_integer(generation, "generation")
    if previous_head_record is not None and (
        type(previous_head_record) is not LineageHeadRecordReference
    ):
        raise LocalLineageHeadSchemaError("previous head-record evidence is invalid")
    if type(lineage_manifest) is not LineageManifestEvidence:
        raise LocalLineageHeadSchemaError("lineage manifest evidence is invalid")
    _require_uuid(verified_lineage_evidence_id, "verified lineage evidence ID")
    if type(terminal_checkpoint) is not LineageHeadTerminalCheckpointEvidence:
        raise LocalLineageHeadSchemaError("terminal checkpoint evidence is invalid")
    if type(advancement_cause_kind) is not LineageHeadAdvancementCauseKind:
        raise LocalLineageHeadSchemaError("advancement cause kind is invalid")
    if type(advancement_cause) is not LineageHeadAdvancementCauseEvidence:
        raise LocalLineageHeadSchemaError("advancement cause evidence is invalid")
    predecessor_parts = (
        ("GENESIS",)
        if previous_head_record is None
        else (
            "HEAD_RECORD",
            str(previous_head_record.head_record_id),
            previous_head_record.sha256,
            str(previous_head_record.byte_length),
        )
    )
    parts = (
        PAPER_ACCOUNT_LINEAGE_HEAD_RECORD_MATERIAL_VERSION,
        str(authority_epoch_id),
        str(generation),
        *predecessor_parts,
        str(lineage_manifest.artifact_id),
        lineage_manifest.sha256,
        str(lineage_manifest.byte_length),
        str(verified_lineage_evidence_id),
        str(terminal_checkpoint.checkpoint_id),
        terminal_checkpoint.sha256,
        str(terminal_checkpoint.byte_length),
        str(terminal_checkpoint.sequence),
        advancement_cause_kind.value,
        str(advancement_cause.artifact_id),
        advancement_cause.sha256,
        str(advancement_cause.byte_length),
    )
    return uuid5(PAPER_ACCOUNT_LINEAGE_HEAD_RECORD_NAMESPACE, _framed(parts))


def serialize_paper_account_lineage_head_record(
    record: PaperAccountLineageHeadRecord,
) -> bytes:
    if type(record) is not PaperAccountLineageHeadRecord:
        raise TypeError("record must be an exact PaperAccountLineageHeadRecord")
    return _canonical_json_bytes(_record_tree(record))


def parse_paper_account_lineage_head_record(
    payload: bytes,
) -> PaperAccountLineageHeadRecord:
    root = _object(
        _load_json(payload, MAX_LOCAL_LINEAGE_HEAD_RECORD_BYTES),
        _RECORD_FIELDS,
        "root",
    )
    if _integer(root["schema_version"], "schema_version") != 1:
        raise LocalLineageHeadSchemaError("unsupported head-record schema")
    previous_value = _object(
        root["previous_head_record"],
        (
            {"kind"}
            if isinstance(root["previous_head_record"], dict)
            and root["previous_head_record"].get("kind") == "GENESIS"
            else {"kind", "head_record_id", "sha256", "byte_length"}
        ),
        "previous_head_record",
    )
    kind = _string(previous_value["kind"], "previous_head_record.kind")
    if kind == "GENESIS":
        previous = None
    elif kind == "HEAD_RECORD":
        previous = LineageHeadRecordReference(
            _uuid(
                previous_value["head_record_id"],
                "previous_head_record.head_record_id",
            ),
            _sha(previous_value["sha256"], "previous_head_record.sha256"),
            _nonnegative_integer(
                previous_value["byte_length"],
                "previous_head_record.byte_length",
            ),
        )
    else:
        raise LocalLineageHeadSchemaError("previous_head_record.kind is unsupported")
    manifest = _object(
        root["lineage_manifest"],
        {"artifact_id", "sha256", "byte_length"},
        "lineage_manifest",
    )
    terminal = _object(
        root["terminal_checkpoint"],
        {"checkpoint_id", "sha256", "byte_length", "sequence"},
        "terminal_checkpoint",
    )
    cause = _object(
        root["advancement_cause"],
        {"kind", "artifact_id", "sha256", "byte_length"},
        "advancement_cause",
    )
    try:
        cause_kind = LineageHeadAdvancementCauseKind(
            _string(cause["kind"], "advancement_cause.kind")
        )
    except ValueError as error:
        raise LocalLineageHeadSchemaError(
            "advancement_cause.kind is unsupported"
        ) from error
    record = PaperAccountLineageHeadRecord(
        PAPER_ACCOUNT_LINEAGE_HEAD_RECORD_SCHEMA_VERSION,
        _uuid(root["record_id"], "record_id"),
        _uuid(root["authority_epoch_id"], "authority_epoch_id"),
        _nonnegative_integer(root["generation"], "generation"),
        previous,
        LineageManifestEvidence(
            _uuid(manifest["artifact_id"], "lineage_manifest.artifact_id"),
            _sha(manifest["sha256"], "lineage_manifest.sha256"),
            _nonnegative_integer(
                manifest["byte_length"], "lineage_manifest.byte_length"
            ),
        ),
        _uuid(
            root["verified_lineage_evidence_id"],
            "verified_lineage_evidence_id",
        ),
        LineageHeadTerminalCheckpointEvidence(
            _uuid(terminal["checkpoint_id"], "terminal_checkpoint.checkpoint_id"),
            _sha(terminal["sha256"], "terminal_checkpoint.sha256"),
            _nonnegative_integer(
                terminal["byte_length"], "terminal_checkpoint.byte_length"
            ),
            _nonnegative_integer(terminal["sequence"], "terminal_checkpoint.sequence"),
        ),
        cause_kind,
        LineageHeadAdvancementCauseEvidence(
            _uuid(cause["artifact_id"], "advancement_cause.artifact_id"),
            _sha(cause["sha256"], "advancement_cause.sha256"),
            _nonnegative_integer(cause["byte_length"], "advancement_cause.byte_length"),
        ),
    )
    if serialize_paper_account_lineage_head_record(record) != payload:
        raise LocalLineageHeadSchemaError("head-record bytes are not canonical")
    return record


def serialize_local_lineage_head_reference(
    reference: LocalLineageHeadReference,
) -> bytes:
    if type(reference) is not LocalLineageHeadReference:
        raise TypeError("reference must be an exact LocalLineageHeadReference")
    return _canonical_json_bytes(
        {
            "schema_version": reference.schema_version,
            "authority_epoch_id": str(reference.authority_epoch_id),
            "generation": reference.generation,
            "head_record_id": str(reference.head_record_id),
            "head_record_sha256": reference.head_record_sha256,
            "head_record_byte_length": reference.head_record_byte_length,
        }
    )


def parse_local_lineage_head_reference(payload: bytes) -> LocalLineageHeadReference:
    root = _object(
        _load_json(payload, MAX_LOCAL_LINEAGE_HEAD_REFERENCE_BYTES),
        _POINTER_FIELDS,
        "root",
    )
    reference = LocalLineageHeadReference(
        _integer(root["schema_version"], "schema_version"),
        _uuid(root["authority_epoch_id"], "authority_epoch_id"),
        _nonnegative_integer(root["generation"], "generation"),
        _uuid(root["head_record_id"], "head_record_id"),
        _sha(root["head_record_sha256"], "head_record_sha256"),
        _nonnegative_integer(
            root["head_record_byte_length"], "head_record_byte_length"
        ),
    )
    if serialize_local_lineage_head_reference(reference) != payload:
        raise LocalLineageHeadSchemaError("current-head bytes are not canonical")
    return reference


def _record_tree(record: PaperAccountLineageHeadRecord) -> dict[str, object]:
    previous: dict[str, object] = (
        {"kind": "GENESIS"}
        if record.previous_head_record is None
        else {
            "kind": "HEAD_RECORD",
            "head_record_id": str(record.previous_head_record.head_record_id),
            "sha256": record.previous_head_record.sha256,
            "byte_length": record.previous_head_record.byte_length,
        }
    )
    return {
        "schema_version": record.schema_version,
        "record_id": str(record.record_id),
        "authority_epoch_id": str(record.authority_epoch_id),
        "generation": record.generation,
        "previous_head_record": previous,
        "lineage_manifest": {
            "artifact_id": str(record.lineage_manifest.artifact_id),
            "sha256": record.lineage_manifest.sha256,
            "byte_length": record.lineage_manifest.byte_length,
        },
        "verified_lineage_evidence_id": str(record.verified_lineage_evidence_id),
        "terminal_checkpoint": {
            "checkpoint_id": str(record.terminal_checkpoint.checkpoint_id),
            "sha256": record.terminal_checkpoint.sha256,
            "byte_length": record.terminal_checkpoint.byte_length,
            "sequence": record.terminal_checkpoint.sequence,
        },
        "advancement_cause": {
            "kind": record.advancement_cause_kind.value,
            "artifact_id": str(record.advancement_cause.artifact_id),
            "sha256": record.advancement_cause.sha256,
            "byte_length": record.advancement_cause.byte_length,
        },
    }


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _load_json(payload: bytes, maximum: int) -> object:
    if type(payload) is not bytes or not payload or len(payload) > maximum:
        raise LocalLineageHeadSyntaxError("JSON payload is invalid or exceeds bounds")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise LocalLineageHeadSyntaxError("UTF-8 BOM is not permitted")
    try:
        text = payload.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except LocalLineageHeadSchemaError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalLineageHeadSyntaxError("payload is not strict UTF-8 JSON") from error


def _duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LocalLineageHeadSchemaError(f"duplicate field: {key}")
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise LocalLineageHeadSchemaError("JSON floats are not permitted")


def _reject_constant(_: str) -> None:
    raise LocalLineageHeadSchemaError("JSON constants are not permitted")


def _object(value: object, fields: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise LocalLineageHeadSchemaError(f"{label} fields are invalid")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        raise LocalLineageHeadSchemaError(f"{label} must be a string")
    return value


def _uuid(value: object, label: str) -> UUID:
    text = _string(value, label)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise LocalLineageHeadSchemaError(f"{label} must be a UUID") from error
    if str(parsed) != text:
        raise LocalLineageHeadSchemaError(f"{label} must be canonical UUID text")
    return parsed


def _sha(value: object, label: str) -> str:
    text = _string(value, label)
    if _SHA256.fullmatch(text) is None:
        raise LocalLineageHeadSchemaError(f"{label} must be lowercase SHA-256 text")
    return text


def _integer(value: object, label: str) -> int:
    if type(value) is not int or abs(value) > MAX_LOCAL_LINEAGE_HEAD_INTEGER:
        raise LocalLineageHeadSchemaError(f"{label} must be a bounded integer")
    return value


def _nonnegative_integer(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed < 0:
        raise LocalLineageHeadSchemaError(f"{label} must be nonnegative")
    return parsed


def _require_uuid(value: object, label: str) -> None:
    if type(value) is not UUID:
        raise LocalLineageHeadSchemaError(f"{label} must be an exact UUID")


def _require_evidence(sha256: object, byte_length: object, label: str) -> None:
    if (
        type(sha256) is not str
        or _SHA256.fullmatch(sha256) is None
        or type(byte_length) is not int
        or byte_length < 0
        or byte_length > MAX_LOCAL_LINEAGE_HEAD_INTEGER
    ):
        raise LocalLineageHeadSchemaError(f"{label} evidence is invalid")


def _require_nonnegative_integer(value: object, label: str) -> None:
    if type(value) is not int or value < 0 or value > MAX_LOCAL_LINEAGE_HEAD_INTEGER:
        raise LocalLineageHeadSchemaError(f"{label} must be a bounded integer")


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)
