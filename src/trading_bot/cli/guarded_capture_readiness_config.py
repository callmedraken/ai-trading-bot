"""Strict schema-1 configuration for guarded capture-readiness dry runs."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.cli.windows_launch_guard import LaunchGuardAclPolicy
from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.runtime import (
    ArtifactEvidence,
    LaunchGuardAcquisitionClassification,
    LaunchLeaseArtifactReference,
    LaunchLeaseReleaseClassification,
    LaunchResultClassification,
    ScheduledPhase,
    derive_launch_lease_release_id,
    derive_launch_lease_start_id,
    derive_scheduled_launch_id,
    derive_scheduled_paper_session_id,
    windows_mutex_name,
)

GUARDED_CAPTURE_READINESS_CONFIG_SCHEMA_VERSION = 1
MAX_GUARDED_CAPTURE_READINESS_CONFIG_BYTES = 256 * 1024
MAX_GUARDED_CAPTURE_READINESS_PATH_CHARACTERS = 4096
MAX_GUARDED_CAPTURE_READINESS_REFERENCES = 100

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_POLICY = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_MAX_INTEGER = (1 << 63) - 1
_ROOT_FIELDS = {
    "schema_version",
    "authority_root",
    "authority_epoch_id",
    "scheduler_audit_root",
    "scheduled_phase",
    "target_session",
    "execution_session",
    "symbols",
    "universe_policy_version",
    "readiness_policy_version",
    "selection_policy_version",
    "nominal_scheduled_slot",
    "launch_retry_ordinal",
    "observed_current_utc_timestamp",
    "acquisition_timestamp_utc",
    "release_timestamp_utc",
    "monotonic_duration_nanoseconds",
    "machine_authority_id",
    "boot_session_evidence",
    "process_id",
    "process_creation_timestamp_utc",
    "account_sid",
    "executable_release_evidence",
    "maximum_runtime_seconds",
    "mutex_timeout_seconds",
    "launch_guard_policy_version",
    "acl_mode",
    "market_hours_schedule_artifact",
    "capture_policy_artifact",
    "capture_attempt_artifacts",
    "snapshot_selection_artifact",
    "manual_disable_active",
    "capture_health",
    "runner_policy_version",
}
_FILE_REFERENCE_FIELDS = {"artifact_id", "path", "sha256", "byte_length"}
_EVIDENCE_FIELDS = {"artifact_id", "sha256", "byte_length"}
_HEALTH_FIELDS = {
    "audit_ok",
    "disk_watermark_ok",
    "backup_ok",
    "notification_ok",
}


class GuardedCaptureReadinessConfigError(ValueError):
    """Raised when the strict dry-run configuration cannot be accepted."""


@dataclass(frozen=True, slots=True)
class ExplicitArtifactReference:
    evidence: ArtifactEvidence
    path: Path

    def __post_init__(self) -> None:
        if type(self.evidence) is not ArtifactEvidence or not isinstance(
            self.path, Path
        ):
            raise GuardedCaptureReadinessConfigError("artifact reference is invalid")
        if not self.path.is_absolute():
            raise GuardedCaptureReadinessConfigError(
                "artifact reference path must resolve absolutely"
            )


@dataclass(frozen=True, slots=True)
class CaptureOnlyHealthConfig:
    audit_ok: bool
    disk_watermark_ok: bool
    backup_ok: bool
    notification_ok: bool

    def __post_init__(self) -> None:
        if any(
            type(getattr(self, name)) is not bool
            for name in (
                "audit_ok",
                "disk_watermark_ok",
                "backup_ok",
                "notification_ok",
            )
        ):
            raise GuardedCaptureReadinessConfigError(
                "capture health inputs must be explicit bools"
            )


@dataclass(frozen=True, slots=True)
class GuardedCaptureReadinessConfig:
    authority_root: Path
    authority_epoch_id: UUID
    scheduler_audit_root: Path
    scheduled_phase: ScheduledPhase
    target_session: TradingSession
    execution_session: TradingSession
    symbols: tuple[Symbol, ...]
    universe_policy_version: str
    readiness_policy_version: str
    selection_policy_version: str
    nominal_scheduled_slot: datetime
    launch_retry_ordinal: int
    observed_current_utc_timestamp: datetime
    acquisition_timestamp_utc: str
    release_timestamp_utc: str
    monotonic_duration_nanoseconds: int
    machine_authority_id: UUID
    boot_session_evidence: str
    process_id: int
    process_creation_timestamp_utc: str
    account_sid: str
    executable_release_evidence: ArtifactEvidence
    maximum_runtime_seconds: int
    mutex_timeout_seconds: int
    launch_guard_policy_version: str
    acl_mode: LaunchGuardAclPolicy
    market_hours_schedule_artifact: ExplicitArtifactReference
    capture_policy_artifact: ExplicitArtifactReference
    capture_attempt_artifacts: tuple[ExplicitArtifactReference, ...]
    snapshot_selection_artifact: ExplicitArtifactReference | None
    manual_disable_active: bool
    capture_health: CaptureOnlyHealthConfig
    runner_policy_version: str

    def __post_init__(self) -> None:
        if (
            not self.authority_root.is_absolute()
            or not self.scheduler_audit_root.is_absolute()
        ):
            raise GuardedCaptureReadinessConfigError(
                "authority and audit roots must be absolute"
            )
        if self.scheduled_phase is not ScheduledPhase.CAPTURE_READINESS_DRY_RUN:
            raise GuardedCaptureReadinessConfigError(
                "scheduled_phase must be CAPTURE_READINESS_DRY_RUN"
            )
        if (
            type(self.target_session) is not TradingSession
            or type(self.execution_session) is not TradingSession
            or self.execution_session.session_date <= self.target_session.session_date
        ):
            raise GuardedCaptureReadinessConfigError(
                "target and execution sessions are invalid"
            )
        symbols = tuple(self.symbols)
        if (
            not symbols
            or len(symbols) > MAX_GUARDED_CAPTURE_READINESS_REFERENCES
            or any(type(item) is not Symbol for item in symbols)
            or len(set(symbols)) != len(symbols)
        ):
            raise GuardedCaptureReadinessConfigError(
                "ordered symbol universe is invalid"
            )
        for value, label in (
            (self.universe_policy_version, "universe_policy_version"),
            (self.readiness_policy_version, "readiness_policy_version"),
            (self.selection_policy_version, "selection_policy_version"),
            (self.runner_policy_version, "runner_policy_version"),
            (self.launch_guard_policy_version, "launch_guard_policy_version"),
        ):
            _policy(value, label)
        nominal = _utc(self.nominal_scheduled_slot, "nominal_scheduled_slot")
        observed = _utc(
            self.observed_current_utc_timestamp,
            "observed_current_utc_timestamp",
        )
        _nonnegative(self.launch_retry_ordinal, "launch_retry_ordinal")
        if type(self.acl_mode) is not LaunchGuardAclPolicy:
            raise GuardedCaptureReadinessConfigError("acl_mode is invalid")
        if (
            type(self.market_hours_schedule_artifact) is not ExplicitArtifactReference
            or type(self.capture_policy_artifact) is not ExplicitArtifactReference
            or (
                self.snapshot_selection_artifact is not None
                and type(self.snapshot_selection_artifact)
                is not ExplicitArtifactReference
            )
        ):
            raise GuardedCaptureReadinessConfigError(
                "explicit input artifact reference is invalid"
            )
        attempts = tuple(self.capture_attempt_artifacts)
        if len(attempts) > MAX_GUARDED_CAPTURE_READINESS_REFERENCES or any(
            type(item) is not ExplicitArtifactReference for item in attempts
        ):
            raise GuardedCaptureReadinessConfigError(
                "capture-attempt references are invalid"
            )
        if (
            type(self.manual_disable_active) is not bool
            or type(self.capture_health) is not CaptureOnlyHealthConfig
        ):
            raise GuardedCaptureReadinessConfigError(
                "explicit dry-run gate inputs are invalid"
            )
        session_id = derive_scheduled_paper_session_id(
            self.authority_epoch_id,
            XNYS_CALENDAR_DESCRIPTOR,
            self.target_session,
            self.execution_session,
            symbols,
            self.universe_policy_version,
            self.readiness_policy_version,
        )
        launch_id = derive_scheduled_launch_id(
            self.authority_epoch_id,
            self.scheduled_phase,
            session_id,
            nominal,
            self.launch_retry_ordinal,
            self.runner_policy_version,
        )
        derive_launch_lease_start_id(
            scheduled_launch_id=launch_id,
            authority_epoch_id=self.authority_epoch_id,
            scheduled_phase=self.scheduled_phase,
            mutex_name=windows_mutex_name(self.authority_epoch_id),
            acquisition_classification=LaunchGuardAcquisitionClassification.ACQUIRED,
            machine_authority_id=self.machine_authority_id,
            boot_evidence=self.boot_session_evidence,
            process_id=self.process_id,
            process_creation_timestamp_utc=self.process_creation_timestamp_utc,
            user_sid=self.account_sid,
            executable_release=self.executable_release_evidence,
            acquisition_timestamp_utc=self.acquisition_timestamp_utc,
            max_runtime_seconds=self.maximum_runtime_seconds,
            launch_policy=self.launch_guard_policy_version,
        )
        derive_launch_lease_release_id(
            lease_start=LaunchLeaseArtifactReference(
                UUID("00000000-0000-5000-8000-000000000001"),
                "0" * 64,
                1,
            ),
            scheduled_launch_id=launch_id,
            authority_epoch_id=self.authority_epoch_id,
            release_classification=LaunchLeaseReleaseClassification.NORMAL,
            release_timestamp_utc=self.release_timestamp_utc,
            monotonic_duration_nanoseconds=self.monotonic_duration_nanoseconds,
            result_classification=LaunchResultClassification.NOT_RUN,
            result_diagnostic="NOT_RUN",
            process_exit_code=None,
            release_policy=self.launch_guard_policy_version,
        )
        if (
            type(self.mutex_timeout_seconds) is not int
            or isinstance(self.mutex_timeout_seconds, bool)
            or not 0 <= self.mutex_timeout_seconds <= 4_294_967
        ):
            raise GuardedCaptureReadinessConfigError(
                "mutex_timeout_seconds is outside the bounded Win32 range"
            )
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "capture_attempt_artifacts", attempts)
        object.__setattr__(self, "nominal_scheduled_slot", nominal)
        object.__setattr__(
            self,
            "observed_current_utc_timestamp",
            observed,
        )

    @property
    def scheduled_session_id(self) -> UUID:
        return derive_scheduled_paper_session_id(
            self.authority_epoch_id,
            XNYS_CALENDAR_DESCRIPTOR,
            self.target_session,
            self.execution_session,
            self.symbols,
            self.universe_policy_version,
            self.readiness_policy_version,
        )

    @property
    def scheduled_launch_id(self) -> UUID:
        return derive_scheduled_launch_id(
            self.authority_epoch_id,
            self.scheduled_phase,
            self.scheduled_session_id,
            self.nominal_scheduled_slot,
            self.launch_retry_ordinal,
            self.runner_policy_version,
        )


def load_guarded_capture_readiness_config(
    path: Path,
) -> GuardedCaptureReadinessConfig:
    """Load only the strict config; referenced artifacts remain unopened."""
    payload = read_safe_regular_file(
        path,
        MAX_GUARDED_CAPTURE_READINESS_CONFIG_BYTES,
        "guarded capture-readiness config",
    )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise GuardedCaptureReadinessConfigError("config BOM is not permitted")
    try:
        root_value = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except GuardedCaptureReadinessConfigError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardedCaptureReadinessConfigError(
            "config must be strict UTF-8 JSON"
        ) from exc
    root = _object(root_value, _ROOT_FIELDS, "config")
    if _integer(root["schema_version"], "schema_version") != 1:
        raise GuardedCaptureReadinessConfigError("config schema_version must be 1")
    config_path = Path(os.path.abspath(path))
    base = config_path.parent
    phase_text = _string(root["scheduled_phase"], "scheduled_phase")
    if phase_text != ScheduledPhase.CAPTURE_READINESS_DRY_RUN.value:
        raise GuardedCaptureReadinessConfigError(
            "scheduled_phase must be CAPTURE_READINESS_DRY_RUN"
        )
    return GuardedCaptureReadinessConfig(
        authority_root=_absolute_path(root["authority_root"], base, "authority_root"),
        authority_epoch_id=_uuid(root["authority_epoch_id"], "authority_epoch_id"),
        scheduler_audit_root=_absolute_path(
            root["scheduler_audit_root"],
            base,
            "scheduler_audit_root",
        ),
        scheduled_phase=ScheduledPhase(phase_text),
        target_session=TradingSession(_date(root["target_session"], "target_session")),
        execution_session=TradingSession(
            _date(root["execution_session"], "execution_session")
        ),
        symbols=tuple(
            Symbol(_string(item, f"symbols[{index}]"))
            for index, item in enumerate(_array(root["symbols"], "symbols"))
        ),
        universe_policy_version=_policy(
            root["universe_policy_version"],
            "universe_policy_version",
        ),
        readiness_policy_version=_policy(
            root["readiness_policy_version"],
            "readiness_policy_version",
        ),
        selection_policy_version=_policy(
            root["selection_policy_version"],
            "selection_policy_version",
        ),
        nominal_scheduled_slot=_timestamp(
            root["nominal_scheduled_slot"],
            "nominal_scheduled_slot",
        ),
        launch_retry_ordinal=_nonnegative(
            root["launch_retry_ordinal"],
            "launch_retry_ordinal",
        ),
        observed_current_utc_timestamp=_timestamp(
            root["observed_current_utc_timestamp"],
            "observed_current_utc_timestamp",
        ),
        acquisition_timestamp_utc=_timestamp_text(
            root["acquisition_timestamp_utc"],
            "acquisition_timestamp_utc",
        ),
        release_timestamp_utc=_timestamp_text(
            root["release_timestamp_utc"],
            "release_timestamp_utc",
        ),
        monotonic_duration_nanoseconds=_nonnegative(
            root["monotonic_duration_nanoseconds"],
            "monotonic_duration_nanoseconds",
        ),
        machine_authority_id=_uuid(
            root["machine_authority_id"],
            "machine_authority_id",
        ),
        boot_session_evidence=_string(
            root["boot_session_evidence"],
            "boot_session_evidence",
        ),
        process_id=_positive(root["process_id"], "process_id"),
        process_creation_timestamp_utc=_timestamp_text(
            root["process_creation_timestamp_utc"],
            "process_creation_timestamp_utc",
        ),
        account_sid=_string(root["account_sid"], "account_sid"),
        executable_release_evidence=_evidence(
            root["executable_release_evidence"],
            "executable_release_evidence",
        ),
        maximum_runtime_seconds=_positive(
            root["maximum_runtime_seconds"],
            "maximum_runtime_seconds",
        ),
        mutex_timeout_seconds=_nonnegative(
            root["mutex_timeout_seconds"],
            "mutex_timeout_seconds",
        ),
        launch_guard_policy_version=_policy(
            root["launch_guard_policy_version"],
            "launch_guard_policy_version",
        ),
        acl_mode=_enum(LaunchGuardAclPolicy, root["acl_mode"], "acl_mode"),
        market_hours_schedule_artifact=_file_reference(
            root["market_hours_schedule_artifact"],
            base,
            "market_hours_schedule_artifact",
        ),
        capture_policy_artifact=_file_reference(
            root["capture_policy_artifact"],
            base,
            "capture_policy_artifact",
        ),
        capture_attempt_artifacts=tuple(
            _file_reference(item, base, f"capture_attempt_artifacts[{index}]")
            for index, item in enumerate(
                _array(
                    root["capture_attempt_artifacts"],
                    "capture_attempt_artifacts",
                )
            )
        ),
        snapshot_selection_artifact=(
            None
            if root["snapshot_selection_artifact"] is None
            else _file_reference(
                root["snapshot_selection_artifact"],
                base,
                "snapshot_selection_artifact",
            )
        ),
        manual_disable_active=_boolean(
            root["manual_disable_active"],
            "manual_disable_active",
        ),
        capture_health=_health(root["capture_health"]),
        runner_policy_version=_policy(
            root["runner_policy_version"],
            "runner_policy_version",
        ),
    )


def _health(value: object) -> CaptureOnlyHealthConfig:
    root = _object(value, _HEALTH_FIELDS, "capture_health")
    return CaptureOnlyHealthConfig(
        audit_ok=_boolean(root["audit_ok"], "capture_health.audit_ok"),
        disk_watermark_ok=_boolean(
            root["disk_watermark_ok"],
            "capture_health.disk_watermark_ok",
        ),
        backup_ok=_boolean(root["backup_ok"], "capture_health.backup_ok"),
        notification_ok=_boolean(
            root["notification_ok"],
            "capture_health.notification_ok",
        ),
    )


def _file_reference(
    value: object,
    base: Path,
    label: str,
) -> ExplicitArtifactReference:
    root = _object(value, _FILE_REFERENCE_FIELDS, label)
    return ExplicitArtifactReference(
        ArtifactEvidence(
            _uuid(root["artifact_id"], f"{label}.artifact_id"),
            _sha(root["sha256"], f"{label}.sha256"),
            _nonnegative(root["byte_length"], f"{label}.byte_length"),
        ),
        _absolute_path(root["path"], base, f"{label}.path"),
    )


def _evidence(value: object, label: str) -> ArtifactEvidence:
    root = _object(value, _EVIDENCE_FIELDS, label)
    return ArtifactEvidence(
        _uuid(root["artifact_id"], f"{label}.artifact_id"),
        _sha(root["sha256"], f"{label}.sha256"),
        _nonnegative(root["byte_length"], f"{label}.byte_length"),
    )


def _absolute_path(value: object, base: Path, label: str) -> Path:
    text = _string(value, label)
    if len(text) > MAX_GUARDED_CAPTURE_READINESS_PATH_CHARACTERS or "\x00" in text:
        raise GuardedCaptureReadinessConfigError(f"{label} is invalid")
    path = Path(text)
    if not path.is_absolute():
        path = base / path
    try:
        return Path(os.path.abspath(path))
    except (OSError, ValueError) as exc:
        raise GuardedCaptureReadinessConfigError(f"{label} is invalid") from exc


def _duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GuardedCaptureReadinessConfigError(f"duplicate config member: {key}")
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise GuardedCaptureReadinessConfigError("floats are not permitted")


def _reject_constant(_: str) -> None:
    raise GuardedCaptureReadinessConfigError("constants are not permitted")


def _object(
    value: object,
    fields: set[str],
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise GuardedCaptureReadinessConfigError(f"{label} members are not exact")
    return value


def _array(value: object, label: str) -> list[object]:
    if type(value) is not list or len(value) > MAX_GUARDED_CAPTURE_READINESS_REFERENCES:
        raise GuardedCaptureReadinessConfigError(f"{label} must be a bounded array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value or len(value) > 4096:
        raise GuardedCaptureReadinessConfigError(
            f"{label} must be bounded nonempty text"
        )
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise GuardedCaptureReadinessConfigError(f"{label} must be a bool")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int or not -_MAX_INTEGER <= value <= _MAX_INTEGER:
        raise GuardedCaptureReadinessConfigError(f"{label} must be a bounded integer")
    return value


def _nonnegative(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed < 0:
        raise GuardedCaptureReadinessConfigError(f"{label} must be nonnegative")
    return parsed


def _positive(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed <= 0:
        raise GuardedCaptureReadinessConfigError(f"{label} must be positive")
    return parsed


def _uuid(value: object, label: str) -> UUID:
    text = _string(value, label)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise GuardedCaptureReadinessConfigError(f"{label} must be a UUID") from exc
    if str(parsed) != text:
        raise GuardedCaptureReadinessConfigError(f"{label} must be a canonical UUID")
    return parsed


def _sha(value: object, label: str) -> str:
    text = _string(value, label)
    if _SHA256.fullmatch(text) is None:
        raise GuardedCaptureReadinessConfigError(f"{label} must be lowercase SHA-256")
    return text


def _timestamp(value: object, label: str) -> datetime:
    text = _timestamp_text(value, label)
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def _timestamp_text(value: object, label: str) -> str:
    text = _string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GuardedCaptureReadinessConfigError(
            f"{label} must be a timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GuardedCaptureReadinessConfigError(f"{label} must be timezone-aware")
    if canonical_timestamp(parsed.astimezone(UTC)) != text:
        raise GuardedCaptureReadinessConfigError(f"{label} must be canonical UTC")
    return text


def _utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise GuardedCaptureReadinessConfigError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _date(value: object, label: str):
    from datetime import date

    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise GuardedCaptureReadinessConfigError(
            f"{label} must be an ISO date"
        ) from exc
    if parsed.isoformat() != text:
        raise GuardedCaptureReadinessConfigError(
            f"{label} must be a canonical ISO date"
        )
    return parsed


def _enum(enum_type, value: object, label: str):  # type: ignore[no-untyped-def]
    text = _string(value, label)
    try:
        return enum_type(text)
    except ValueError as exc:
        raise GuardedCaptureReadinessConfigError(
            f"{label} has an unsupported value"
        ) from exc


def _policy(value: object, label: str) -> str:
    if type(value) is not str or _POLICY.fullmatch(value) is None:
        raise GuardedCaptureReadinessConfigError(
            f"{label} must be a canonical policy identifier"
        )
    return value
