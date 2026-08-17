"""Deterministic lease evidence for the Windows local launch guard."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5

from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence, ScheduledPhase

LAUNCH_LEASE_START_SCHEMA_VERSION = 1
LAUNCH_LEASE_RELEASE_SCHEMA_VERSION = 1
LAUNCH_LEASE_START_MATERIAL_VERSION = "launch-lease-start/v1"
LAUNCH_LEASE_RELEASE_MATERIAL_VERSION = "launch-lease-release/v1"
LAUNCH_LEASE_START_NAMESPACE = UUID("3785d749-91e1-5b48-995f-1e48708a209d")
LAUNCH_LEASE_RELEASE_NAMESPACE = UUID("7a154905-0644-5c08-8d04-d0a16c50d1cd")
MAX_LEASE_ARTIFACT_BYTES = 65_536
MAX_POLICY_LENGTH = 128
MAX_DIAGNOSTIC_LENGTH = 128
MAX_BOOT_EVIDENCE_LENGTH = 256
MAX_MONOTONIC_DURATION_NANOSECONDS = 31_536_000_000_000_000

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SID_RE = re.compile(r"S-(?:[0-9]+-)+[0-9]+")
_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9_]{0,127}")
_POLICY_RE = re.compile(r"[a-z][a-z0-9._-]{0,127}")
_BOOT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}")


class LaunchGuardAcquisitionClassification(StrEnum):
    """Complete externally observable native acquisition classification."""

    ACQUIRED = "ACQUIRED"
    ALREADY_HELD = "ALREADY_HELD"
    ABANDONED_ACQUIRED = "ABANDONED_ACQUIRED"
    ACCESS_DENIED = "ACCESS_DENIED"
    UNSUPPORTED = "UNSUPPORTED"
    ERROR = "ERROR"


class LaunchLeaseReleaseClassification(StrEnum):
    """Why an acquired launch lease is being released."""

    NORMAL = "NORMAL"
    START_PUBLICATION_FAILED = "START_PUBLICATION_FAILED"


class LaunchResultClassification(StrEnum):
    """Sanitized result categories allowed in release evidence."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"
    NOT_RUN = "NOT_RUN"


def windows_mutex_name(authority_epoch_id: UUID) -> str:
    """Return the architecture-approved global mutex name."""

    if not isinstance(authority_epoch_id, UUID):
        raise ValueError("authority_epoch_id must be a UUID")
    return f"Global\\AITradingBot.PaperAuthority.{authority_epoch_id}"


def _frame(*parts: str) -> str:
    return "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)


def _require_uuid(value: object, field: str) -> UUID:
    if not isinstance(value, UUID):
        raise ValueError(f"{field} must be a UUID")
    return value


def _require_exact_int(
    value: object,
    field: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{field} is outside the supported range")
    return value


def _require_token(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > MAX_DIAGNOSTIC_LENGTH
        or not _TOKEN_RE.fullmatch(value)
    ):
        raise ValueError(f"{field} must be a canonical diagnostic token")
    return value


def _require_policy(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > MAX_POLICY_LENGTH
        or not _POLICY_RE.fullmatch(value)
    ):
        raise ValueError(f"{field} must be a canonical policy identifier")
    return value


def _require_boot_evidence(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > MAX_BOOT_EVIDENCE_LENGTH
        or not _BOOT_RE.fullmatch(value)
    ):
        raise ValueError("boot_evidence must be bounded canonical text")
    return value


def _canonical_timestamp_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be canonical UTC timestamp text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be canonical UTC timestamp text") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    rendered = canonical_timestamp(parsed.astimezone(UTC))
    if rendered != value:
        raise ValueError(f"{field} must be canonical UTC timestamp text")
    return rendered


def _require_sid(value: object) -> str:
    if not isinstance(value, str) or len(value) > 184 or not _SID_RE.fullmatch(value):
        raise ValueError("user_sid must be a canonical Windows SID")
    return value


def _require_hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class LaunchLeaseArtifactReference:
    """Content-bound reference to an immutable lease artifact."""

    record_id: UUID
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        _require_uuid(self.record_id, "record_id")
        _require_hash(self.sha256, "sha256")
        _require_exact_int(
            self.byte_length,
            "byte_length",
            minimum=1,
            maximum=MAX_LEASE_ARTIFACT_BYTES,
        )


@dataclass(frozen=True, slots=True)
class LaunchLeaseStart:
    """Canonical evidence written while the named mutex is held."""

    schema_version: int
    record_id: UUID
    scheduled_launch_id: UUID
    authority_epoch_id: UUID
    scheduled_phase: ScheduledPhase
    mutex_name: str
    acquisition_classification: LaunchGuardAcquisitionClassification
    machine_authority_id: UUID
    boot_evidence: str
    process_id: int
    process_creation_timestamp_utc: str
    user_sid: str
    executable_release: ArtifactEvidence
    acquisition_timestamp_utc: str
    max_runtime_seconds: int
    launch_policy: str

    def __post_init__(self) -> None:
        _require_exact_int(
            self.schema_version,
            "schema_version",
            minimum=LAUNCH_LEASE_START_SCHEMA_VERSION,
            maximum=LAUNCH_LEASE_START_SCHEMA_VERSION,
        )
        _require_uuid(self.record_id, "record_id")
        _require_uuid(self.scheduled_launch_id, "scheduled_launch_id")
        _require_uuid(self.authority_epoch_id, "authority_epoch_id")
        if not isinstance(self.scheduled_phase, ScheduledPhase):
            raise ValueError("scheduled_phase must be a ScheduledPhase")
        if self.mutex_name != windows_mutex_name(self.authority_epoch_id):
            raise ValueError("mutex_name does not match authority_epoch_id")
        if self.acquisition_classification not in {
            LaunchGuardAcquisitionClassification.ACQUIRED,
            LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED,
        }:
            raise ValueError("start evidence requires an acquired classification")
        _require_uuid(self.machine_authority_id, "machine_authority_id")
        _require_boot_evidence(self.boot_evidence)
        _require_exact_int(
            self.process_id,
            "process_id",
            minimum=1,
            maximum=2_147_483_647,
        )
        _canonical_timestamp_text(
            self.process_creation_timestamp_utc,
            "process_creation_timestamp_utc",
        )
        _require_sid(self.user_sid)
        if not isinstance(self.executable_release, ArtifactEvidence):
            raise ValueError("executable_release must be ArtifactEvidence")
        _canonical_timestamp_text(
            self.acquisition_timestamp_utc,
            "acquisition_timestamp_utc",
        )
        _require_exact_int(
            self.max_runtime_seconds,
            "max_runtime_seconds",
            minimum=1,
            maximum=31_536_000,
        )
        _require_policy(self.launch_policy, "launch_policy")
        expected = derive_launch_lease_start_id(
            scheduled_launch_id=self.scheduled_launch_id,
            authority_epoch_id=self.authority_epoch_id,
            scheduled_phase=self.scheduled_phase,
            mutex_name=self.mutex_name,
            acquisition_classification=self.acquisition_classification,
            machine_authority_id=self.machine_authority_id,
            boot_evidence=self.boot_evidence,
            process_id=self.process_id,
            process_creation_timestamp_utc=self.process_creation_timestamp_utc,
            user_sid=self.user_sid,
            executable_release=self.executable_release,
            acquisition_timestamp_utc=self.acquisition_timestamp_utc,
            max_runtime_seconds=self.max_runtime_seconds,
            launch_policy=self.launch_policy,
        )
        if self.record_id != expected:
            raise ValueError("record_id does not match canonical lease-start material")


@dataclass(frozen=True, slots=True)
class LaunchLeaseRelease:
    """Canonical release intent published before the mutex is released."""

    schema_version: int
    release_id: UUID
    lease_start: LaunchLeaseArtifactReference
    scheduled_launch_id: UUID
    authority_epoch_id: UUID
    release_classification: LaunchLeaseReleaseClassification
    release_timestamp_utc: str
    monotonic_duration_nanoseconds: int
    result_classification: LaunchResultClassification
    result_diagnostic: str
    process_exit_code: int | None
    release_policy: str

    def __post_init__(self) -> None:
        _require_exact_int(
            self.schema_version,
            "schema_version",
            minimum=LAUNCH_LEASE_RELEASE_SCHEMA_VERSION,
            maximum=LAUNCH_LEASE_RELEASE_SCHEMA_VERSION,
        )
        _require_uuid(self.release_id, "release_id")
        if not isinstance(self.lease_start, LaunchLeaseArtifactReference):
            raise ValueError("lease_start must be LaunchLeaseArtifactReference")
        _require_uuid(self.scheduled_launch_id, "scheduled_launch_id")
        _require_uuid(self.authority_epoch_id, "authority_epoch_id")
        if not isinstance(
            self.release_classification,
            LaunchLeaseReleaseClassification,
        ):
            raise ValueError(
                "release_classification must be LaunchLeaseReleaseClassification"
            )
        _canonical_timestamp_text(
            self.release_timestamp_utc,
            "release_timestamp_utc",
        )
        _require_exact_int(
            self.monotonic_duration_nanoseconds,
            "monotonic_duration_nanoseconds",
            minimum=0,
            maximum=MAX_MONOTONIC_DURATION_NANOSECONDS,
        )
        if not isinstance(self.result_classification, LaunchResultClassification):
            raise ValueError("result_classification must be LaunchResultClassification")
        _require_token(self.result_diagnostic, "result_diagnostic")
        if self.process_exit_code is not None:
            _require_exact_int(
                self.process_exit_code,
                "process_exit_code",
                minimum=-2_147_483_648,
                maximum=2_147_483_647,
            )
        _require_policy(self.release_policy, "release_policy")
        expected = derive_launch_lease_release_id(
            lease_start=self.lease_start,
            scheduled_launch_id=self.scheduled_launch_id,
            authority_epoch_id=self.authority_epoch_id,
            release_classification=self.release_classification,
            release_timestamp_utc=self.release_timestamp_utc,
            monotonic_duration_nanoseconds=self.monotonic_duration_nanoseconds,
            result_classification=self.result_classification,
            result_diagnostic=self.result_diagnostic,
            process_exit_code=self.process_exit_code,
            release_policy=self.release_policy,
        )
        if self.release_id != expected:
            raise ValueError(
                "release_id does not match canonical lease-release material"
            )


@dataclass(frozen=True, slots=True)
class LaunchGuardDiagnostic:
    """Read-only, non-authoritative launch guard diagnostic."""

    mutex_name: str
    process_id: int
    process_creation_timestamp_utc: str
    boot_evidence: str
    user_sid: str
    lease_start: LaunchLeaseArtifactReference
    lease_release: LaunchLeaseArtifactReference | None
    released: bool

    def __post_init__(self) -> None:
        if not isinstance(self.mutex_name, str) or not self.mutex_name:
            raise ValueError("mutex_name must be non-empty")
        _require_exact_int(
            self.process_id,
            "process_id",
            minimum=1,
            maximum=2_147_483_647,
        )
        _canonical_timestamp_text(
            self.process_creation_timestamp_utc,
            "process_creation_timestamp_utc",
        )
        _require_boot_evidence(self.boot_evidence)
        _require_sid(self.user_sid)
        if not isinstance(self.lease_start, LaunchLeaseArtifactReference):
            raise ValueError("lease_start must be LaunchLeaseArtifactReference")
        if self.lease_release is not None and not isinstance(
            self.lease_release,
            LaunchLeaseArtifactReference,
        ):
            raise ValueError(
                "lease_release must be LaunchLeaseArtifactReference or None"
            )
        if not isinstance(self.released, bool):
            raise ValueError("released must be a bool")
        if not self.released and self.lease_release is not None:
            raise ValueError("an active diagnostic cannot contain release evidence")


def derive_launch_lease_start_id(
    *,
    scheduled_launch_id: UUID,
    authority_epoch_id: UUID,
    scheduled_phase: ScheduledPhase,
    mutex_name: str,
    acquisition_classification: LaunchGuardAcquisitionClassification,
    machine_authority_id: UUID,
    boot_evidence: str,
    process_id: int,
    process_creation_timestamp_utc: str,
    user_sid: str,
    executable_release: ArtifactEvidence,
    acquisition_timestamp_utc: str,
    max_runtime_seconds: int,
    launch_policy: str,
) -> UUID:
    """Derive the stable identity of launch-start evidence."""

    _require_uuid(scheduled_launch_id, "scheduled_launch_id")
    _require_uuid(authority_epoch_id, "authority_epoch_id")
    if not isinstance(scheduled_phase, ScheduledPhase):
        raise ValueError("scheduled_phase must be a ScheduledPhase")
    if mutex_name != windows_mutex_name(authority_epoch_id):
        raise ValueError("mutex_name does not match authority_epoch_id")
    if acquisition_classification not in {
        LaunchGuardAcquisitionClassification.ACQUIRED,
        LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED,
    }:
        raise ValueError("start identity requires an acquired classification")
    _require_uuid(machine_authority_id, "machine_authority_id")
    _require_exact_int(
        process_id,
        "process_id",
        minimum=1,
        maximum=2_147_483_647,
    )
    if not isinstance(executable_release, ArtifactEvidence):
        raise ValueError("executable_release must be ArtifactEvidence")
    _require_exact_int(
        max_runtime_seconds,
        "max_runtime_seconds",
        minimum=1,
        maximum=31_536_000,
    )
    process_creation_timestamp_utc = _canonical_timestamp_text(
        process_creation_timestamp_utc,
        "process_creation_timestamp_utc",
    )
    acquisition_timestamp_utc = _canonical_timestamp_text(
        acquisition_timestamp_utc,
        "acquisition_timestamp_utc",
    )
    material = _frame(
        LAUNCH_LEASE_START_MATERIAL_VERSION,
        str(scheduled_launch_id),
        str(authority_epoch_id),
        scheduled_phase.value,
        mutex_name,
        acquisition_classification.value,
        str(machine_authority_id),
        _require_boot_evidence(boot_evidence),
        str(process_id),
        process_creation_timestamp_utc,
        _require_sid(user_sid),
        str(executable_release.artifact_id),
        executable_release.sha256,
        str(executable_release.byte_length),
        acquisition_timestamp_utc,
        str(max_runtime_seconds),
        _require_policy(launch_policy, "launch_policy"),
    )
    return uuid5(LAUNCH_LEASE_START_NAMESPACE, material)


def create_launch_lease_start(
    *,
    scheduled_launch_id: UUID,
    authority_epoch_id: UUID,
    scheduled_phase: ScheduledPhase,
    acquisition_classification: LaunchGuardAcquisitionClassification,
    machine_authority_id: UUID,
    boot_evidence: str,
    process_id: int,
    process_creation_timestamp_utc: str,
    user_sid: str,
    executable_release: ArtifactEvidence,
    acquisition_timestamp_utc: str,
    max_runtime_seconds: int,
    launch_policy: str,
) -> LaunchLeaseStart:
    mutex_name = windows_mutex_name(authority_epoch_id)
    record_id = derive_launch_lease_start_id(
        scheduled_launch_id=scheduled_launch_id,
        authority_epoch_id=authority_epoch_id,
        scheduled_phase=scheduled_phase,
        mutex_name=mutex_name,
        acquisition_classification=acquisition_classification,
        machine_authority_id=machine_authority_id,
        boot_evidence=boot_evidence,
        process_id=process_id,
        process_creation_timestamp_utc=process_creation_timestamp_utc,
        user_sid=user_sid,
        executable_release=executable_release,
        acquisition_timestamp_utc=acquisition_timestamp_utc,
        max_runtime_seconds=max_runtime_seconds,
        launch_policy=launch_policy,
    )
    return LaunchLeaseStart(
        schema_version=LAUNCH_LEASE_START_SCHEMA_VERSION,
        record_id=record_id,
        scheduled_launch_id=scheduled_launch_id,
        authority_epoch_id=authority_epoch_id,
        scheduled_phase=scheduled_phase,
        mutex_name=mutex_name,
        acquisition_classification=acquisition_classification,
        machine_authority_id=machine_authority_id,
        boot_evidence=boot_evidence,
        process_id=process_id,
        process_creation_timestamp_utc=_canonical_timestamp_text(
            process_creation_timestamp_utc,
            "process_creation_timestamp_utc",
        ),
        user_sid=user_sid,
        executable_release=executable_release,
        acquisition_timestamp_utc=_canonical_timestamp_text(
            acquisition_timestamp_utc,
            "acquisition_timestamp_utc",
        ),
        max_runtime_seconds=max_runtime_seconds,
        launch_policy=launch_policy,
    )


def lease_start_artifact_reference(
    lease_start: LaunchLeaseStart,
) -> LaunchLeaseArtifactReference:
    payload = serialize_launch_lease_start(lease_start)
    return LaunchLeaseArtifactReference(
        record_id=lease_start.record_id,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
    )


def derive_launch_lease_release_id(
    *,
    lease_start: LaunchLeaseArtifactReference,
    scheduled_launch_id: UUID,
    authority_epoch_id: UUID,
    release_classification: LaunchLeaseReleaseClassification,
    release_timestamp_utc: str,
    monotonic_duration_nanoseconds: int,
    result_classification: LaunchResultClassification,
    result_diagnostic: str,
    process_exit_code: int | None,
    release_policy: str,
) -> UUID:
    if not isinstance(lease_start, LaunchLeaseArtifactReference):
        raise ValueError("lease_start must be LaunchLeaseArtifactReference")
    _require_uuid(scheduled_launch_id, "scheduled_launch_id")
    _require_uuid(authority_epoch_id, "authority_epoch_id")
    if not isinstance(
        release_classification,
        LaunchLeaseReleaseClassification,
    ):
        raise ValueError(
            "release_classification must be LaunchLeaseReleaseClassification"
        )
    _require_exact_int(
        monotonic_duration_nanoseconds,
        "monotonic_duration_nanoseconds",
        minimum=0,
        maximum=MAX_MONOTONIC_DURATION_NANOSECONDS,
    )
    if not isinstance(result_classification, LaunchResultClassification):
        raise ValueError("result_classification must be LaunchResultClassification")
    if process_exit_code is not None:
        _require_exact_int(
            process_exit_code,
            "process_exit_code",
            minimum=-2_147_483_648,
            maximum=2_147_483_647,
        )
    release_timestamp_utc = _canonical_timestamp_text(
        release_timestamp_utc,
        "release_timestamp_utc",
    )
    exit_material = "" if process_exit_code is None else str(process_exit_code)
    material = _frame(
        LAUNCH_LEASE_RELEASE_MATERIAL_VERSION,
        str(lease_start.record_id),
        lease_start.sha256,
        str(lease_start.byte_length),
        str(scheduled_launch_id),
        str(authority_epoch_id),
        release_classification.value,
        release_timestamp_utc,
        str(monotonic_duration_nanoseconds),
        result_classification.value,
        _require_token(result_diagnostic, "result_diagnostic"),
        exit_material,
        _require_policy(release_policy, "release_policy"),
    )
    return uuid5(LAUNCH_LEASE_RELEASE_NAMESPACE, material)


def create_launch_lease_release(
    *,
    lease_start: LaunchLeaseStart,
    lease_start_reference: LaunchLeaseArtifactReference,
    release_classification: LaunchLeaseReleaseClassification,
    release_timestamp_utc: str,
    monotonic_duration_nanoseconds: int,
    result_classification: LaunchResultClassification,
    result_diagnostic: str,
    process_exit_code: int | None,
    release_policy: str,
) -> LaunchLeaseRelease:
    if lease_start_reference != lease_start_artifact_reference(lease_start):
        raise ValueError("lease_start_reference does not match lease_start bytes")
    release_id = derive_launch_lease_release_id(
        lease_start=lease_start_reference,
        scheduled_launch_id=lease_start.scheduled_launch_id,
        authority_epoch_id=lease_start.authority_epoch_id,
        release_classification=release_classification,
        release_timestamp_utc=release_timestamp_utc,
        monotonic_duration_nanoseconds=monotonic_duration_nanoseconds,
        result_classification=result_classification,
        result_diagnostic=result_diagnostic,
        process_exit_code=process_exit_code,
        release_policy=release_policy,
    )
    return LaunchLeaseRelease(
        schema_version=LAUNCH_LEASE_RELEASE_SCHEMA_VERSION,
        release_id=release_id,
        lease_start=lease_start_reference,
        scheduled_launch_id=lease_start.scheduled_launch_id,
        authority_epoch_id=lease_start.authority_epoch_id,
        release_classification=release_classification,
        release_timestamp_utc=_canonical_timestamp_text(
            release_timestamp_utc,
            "release_timestamp_utc",
        ),
        monotonic_duration_nanoseconds=monotonic_duration_nanoseconds,
        result_classification=result_classification,
        result_diagnostic=result_diagnostic,
        process_exit_code=process_exit_code,
        release_policy=release_policy,
    )


def _artifact_evidence_to_dict(value: ArtifactEvidence) -> dict[str, object]:
    return {
        "artifact_id": str(value.artifact_id),
        "byte_length": value.byte_length,
        "sha256": value.sha256,
    }


def _lease_reference_to_dict(
    value: LaunchLeaseArtifactReference,
) -> dict[str, object]:
    return {
        "byte_length": value.byte_length,
        "record_id": str(value.record_id),
        "sha256": value.sha256,
    }


def launch_lease_start_to_dict(value: LaunchLeaseStart) -> dict[str, object]:
    return {
        "acquisition_classification": value.acquisition_classification.value,
        "acquisition_timestamp_utc": value.acquisition_timestamp_utc,
        "authority_epoch_id": str(value.authority_epoch_id),
        "boot_evidence": value.boot_evidence,
        "executable_release": _artifact_evidence_to_dict(value.executable_release),
        "launch_policy": value.launch_policy,
        "machine_authority_id": str(value.machine_authority_id),
        "max_runtime_seconds": value.max_runtime_seconds,
        "mutex_name": value.mutex_name,
        "process_creation_timestamp_utc": value.process_creation_timestamp_utc,
        "process_id": value.process_id,
        "record_id": str(value.record_id),
        "scheduled_launch_id": str(value.scheduled_launch_id),
        "scheduled_phase": value.scheduled_phase.value,
        "schema_version": value.schema_version,
        "user_sid": value.user_sid,
    }


def launch_lease_release_to_dict(value: LaunchLeaseRelease) -> dict[str, object]:
    return {
        "authority_epoch_id": str(value.authority_epoch_id),
        "lease_start": _lease_reference_to_dict(value.lease_start),
        "monotonic_duration_nanoseconds": value.monotonic_duration_nanoseconds,
        "process_exit_code": value.process_exit_code,
        "release_classification": value.release_classification.value,
        "release_id": str(value.release_id),
        "release_policy": value.release_policy,
        "release_timestamp_utc": value.release_timestamp_utc,
        "result_classification": value.result_classification.value,
        "result_diagnostic": value.result_diagnostic,
        "scheduled_launch_id": str(value.scheduled_launch_id),
        "schema_version": value.schema_version,
    }


def _serialize(payload: Mapping[str, object]) -> bytes:
    encoded = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")
    if len(encoded) > MAX_LEASE_ARTIFACT_BYTES:
        raise ValueError("lease artifact exceeds the supported byte bound")
    return encoded


def serialize_launch_lease_start(value: LaunchLeaseStart) -> bytes:
    return _serialize(launch_lease_start_to_dict(value))


def serialize_launch_lease_release(value: LaunchLeaseRelease) -> bytes:
    return _serialize(launch_lease_release_to_dict(value))


def _reject_duplicate_key(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON constant: {value}")


def _load_object(payload: bytes) -> dict[str, Any]:
    if not isinstance(payload, bytes):
        raise ValueError("lease artifact must be bytes")
    if not payload or len(payload) > MAX_LEASE_ARTIFACT_BYTES:
        raise ValueError("lease artifact byte length is invalid")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise ValueError("lease artifact must not contain a BOM")
    try:
        document = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=_reject_duplicate_key,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("lease artifact is not strict ASCII JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("lease artifact root must be an object")
    return document


def _require_keys(document: Mapping[str, Any], expected: set[str]) -> None:
    keys = set(document)
    if keys != expected:
        missing = sorted(expected - keys)
        unexpected = sorted(keys - expected)
        raise ValueError(
            f"lease artifact members differ; missing={missing}, unexpected={unexpected}"
        )


def _parse_uuid(value: object, field: str) -> UUID:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a canonical UUID string")
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError(f"{field} must be a canonical UUID string")
    return parsed


def _parse_artifact_evidence(value: object) -> ArtifactEvidence:
    if not isinstance(value, dict):
        raise ValueError("executable_release must be an object")
    _require_keys(value, {"artifact_id", "byte_length", "sha256"})
    return ArtifactEvidence(
        artifact_id=_parse_uuid(value["artifact_id"], "artifact_id"),
        sha256=_require_hash(value["sha256"], "sha256"),
        byte_length=_require_exact_int(
            value["byte_length"],
            "byte_length",
            minimum=1,
            maximum=(1 << 63) - 1,
        ),
    )


def _parse_lease_reference(value: object) -> LaunchLeaseArtifactReference:
    if not isinstance(value, dict):
        raise ValueError("lease_start must be an object")
    _require_keys(value, {"record_id", "byte_length", "sha256"})
    return LaunchLeaseArtifactReference(
        record_id=_parse_uuid(value["record_id"], "record_id"),
        sha256=_require_hash(value["sha256"], "sha256"),
        byte_length=_require_exact_int(
            value["byte_length"],
            "byte_length",
            minimum=1,
            maximum=MAX_LEASE_ARTIFACT_BYTES,
        ),
    )


def parse_launch_lease_start(payload: bytes) -> LaunchLeaseStart:
    document = _load_object(payload)
    _require_keys(
        document,
        {
            "acquisition_classification",
            "acquisition_timestamp_utc",
            "authority_epoch_id",
            "boot_evidence",
            "executable_release",
            "launch_policy",
            "machine_authority_id",
            "max_runtime_seconds",
            "mutex_name",
            "process_creation_timestamp_utc",
            "process_id",
            "record_id",
            "scheduled_launch_id",
            "scheduled_phase",
            "schema_version",
            "user_sid",
        },
    )
    try:
        result = LaunchLeaseStart(
            schema_version=document["schema_version"],
            record_id=_parse_uuid(document["record_id"], "record_id"),
            scheduled_launch_id=_parse_uuid(
                document["scheduled_launch_id"],
                "scheduled_launch_id",
            ),
            authority_epoch_id=_parse_uuid(
                document["authority_epoch_id"],
                "authority_epoch_id",
            ),
            scheduled_phase=ScheduledPhase(document["scheduled_phase"]),
            mutex_name=document["mutex_name"],
            acquisition_classification=LaunchGuardAcquisitionClassification(
                document["acquisition_classification"]
            ),
            machine_authority_id=_parse_uuid(
                document["machine_authority_id"],
                "machine_authority_id",
            ),
            boot_evidence=document["boot_evidence"],
            process_id=document["process_id"],
            process_creation_timestamp_utc=document["process_creation_timestamp_utc"],
            user_sid=document["user_sid"],
            executable_release=_parse_artifact_evidence(document["executable_release"]),
            acquisition_timestamp_utc=document["acquisition_timestamp_utc"],
            max_runtime_seconds=document["max_runtime_seconds"],
            launch_policy=document["launch_policy"],
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("lease-start member has an invalid type") from exc
    if serialize_launch_lease_start(result) != payload:
        raise ValueError("lease-start artifact is not canonical JSON")
    return result


def parse_launch_lease_release(payload: bytes) -> LaunchLeaseRelease:
    document = _load_object(payload)
    _require_keys(
        document,
        {
            "authority_epoch_id",
            "lease_start",
            "monotonic_duration_nanoseconds",
            "process_exit_code",
            "release_classification",
            "release_id",
            "release_policy",
            "release_timestamp_utc",
            "result_classification",
            "result_diagnostic",
            "scheduled_launch_id",
            "schema_version",
        },
    )
    try:
        result = LaunchLeaseRelease(
            schema_version=document["schema_version"],
            release_id=_parse_uuid(document["release_id"], "release_id"),
            lease_start=_parse_lease_reference(document["lease_start"]),
            scheduled_launch_id=_parse_uuid(
                document["scheduled_launch_id"],
                "scheduled_launch_id",
            ),
            authority_epoch_id=_parse_uuid(
                document["authority_epoch_id"],
                "authority_epoch_id",
            ),
            release_classification=LaunchLeaseReleaseClassification(
                document["release_classification"]
            ),
            release_timestamp_utc=document["release_timestamp_utc"],
            monotonic_duration_nanoseconds=document["monotonic_duration_nanoseconds"],
            result_classification=LaunchResultClassification(
                document["result_classification"]
            ),
            result_diagnostic=document["result_diagnostic"],
            process_exit_code=document["process_exit_code"],
            release_policy=document["release_policy"],
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("lease-release member has an invalid type") from exc
    if serialize_launch_lease_release(result) != payload:
        raise ValueError("lease-release artifact is not canonical JSON")
    return result
