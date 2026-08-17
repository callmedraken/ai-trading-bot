"""Strict nonsecret configuration for the manual guarded capture runner."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.cli.guarded_capture_readiness_config import (
    CaptureOnlyHealthConfig,
    ExplicitArtifactReference,
)
from trading_bot.cli.windows_launch_guard import LaunchGuardAclPolicy
from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.runtime import (
    ArtifactEvidence,
    ScheduledPhase,
    derive_scheduled_launch_id,
    derive_scheduled_paper_session_id,
)

GUARDED_CAPTURE_RUNNER_CONFIG_SCHEMA_VERSION = 1
MAX_GUARDED_CAPTURE_RUNNER_CONFIG_BYTES = 256 * 1024
MAX_GUARDED_CAPTURE_RUNNER_PATH_CHARACTERS = 4096
MAX_GUARDED_CAPTURE_RUNNER_REFERENCES = 100
_MAX_INTEGER = (1 << 63) - 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_POLICY = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_SID = re.compile(r"^S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$")


class ProductionXnysHoursAuthorityStatus(StrEnum):
    """Whether official production XNYS-hours provenance is available."""

    UNRESOLVED = "UNRESOLVED"
    VERIFIED = "VERIFIED"


@dataclass(frozen=True, slots=True)
class ProductionXnysHoursAuthority:
    status: ProductionXnysHoursAuthorityStatus
    provenance: str | None
    schedule_evidence: ArtifactEvidence | None

    def __post_init__(self) -> None:
        if type(self.status) is not ProductionXnysHoursAuthorityStatus:
            raise GuardedCaptureRunnerConfigError("production hours status is invalid")
        if self.status is ProductionXnysHoursAuthorityStatus.UNRESOLVED:
            if self.provenance is not None or self.schedule_evidence is not None:
                raise GuardedCaptureRunnerConfigError(
                    "unresolved hours authority cannot carry verification evidence"
                )
            return
        if (
            self.provenance != "official-xnys-hours-v1"
            or type(self.schedule_evidence) is not ArtifactEvidence
        ):
            raise GuardedCaptureRunnerConfigError(
                "verified hours authority requires official provenance and evidence"
            )


class GuardedCaptureRunnerConfigError(ValueError):
    """Raised when the manual runner configuration is not accepted."""


@dataclass(frozen=True, slots=True)
class GuardedCaptureRunnerConfig:
    authority_root: Path
    scheduler_audit_root: Path
    capture_attempt_root: Path
    authority_epoch_id: UUID
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
    terminal_completed_at_utc: datetime
    request_timestamp_utc: datetime
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
    capture_configuration_artifact: ExplicitArtifactReference
    credential_reference_artifact: ExplicitArtifactReference
    snapshot_destination: ExplicitArtifactReference
    software_release_evidence: ArtifactEvidence
    credential_reference_version: str
    snapshot_capture_request_id: UUID
    allocation_history_policy_version: str
    allocation_policy_version: str
    terminal_policy_version: str
    runner_policy_version: str
    approved_python_executable: Path
    approved_python_executable_evidence: ArtifactEvidence
    approved_child_script: Path
    approved_child_script_evidence: ArtifactEvidence
    process_evidence_directory: Path
    controlled_temp_directory: Path
    termination_grace_seconds: int
    wall_timeout_seconds: int
    manual_disable_active: bool
    capture_health: CaptureOnlyHealthConfig
    production_xnys_hours_authority: ProductionXnysHoursAuthority

    def __post_init__(self) -> None:
        for value, label in (
            (self.authority_root, "authority_root"),
            (self.scheduler_audit_root, "scheduler_audit_root"),
            (self.capture_attempt_root, "capture_attempt_root"),
            (self.approved_python_executable, "approved_python_executable"),
            (self.approved_child_script, "approved_child_script"),
            (self.process_evidence_directory, "process_evidence_directory"),
            (self.controlled_temp_directory, "controlled_temp_directory"),
        ):
            if not isinstance(value, Path) or not value.is_absolute():
                raise GuardedCaptureRunnerConfigError(f"{label} must be absolute")
        if self.scheduled_phase is not ScheduledPhase.CAPTURE:
            raise GuardedCaptureRunnerConfigError("scheduled_phase must be CAPTURE")
        if (
            type(self.target_session) is not TradingSession
            or type(self.execution_session) is not TradingSession
            or self.execution_session.session_date <= self.target_session.session_date
        ):
            raise GuardedCaptureRunnerConfigError(
                "target and execution sessions invalid"
            )
        symbols = tuple(self.symbols)
        if symbols != (Symbol("SPY"), Symbol("QQQ")):
            raise GuardedCaptureRunnerConfigError("symbols must be exactly SPY,QQQ")
        for value, label in (
            (self.universe_policy_version, "universe_policy_version"),
            (self.readiness_policy_version, "readiness_policy_version"),
            (self.selection_policy_version, "selection_policy_version"),
            (self.launch_guard_policy_version, "launch_guard_policy_version"),
            (
                self.allocation_history_policy_version,
                "allocation_history_policy_version",
            ),
            (self.allocation_policy_version, "allocation_policy_version"),
            (self.terminal_policy_version, "terminal_policy_version"),
            (self.runner_policy_version, "runner_policy_version"),
            (self.credential_reference_version, "credential_reference_version"),
        ):
            _policy(value, label)
        _utc(self.nominal_scheduled_slot, "nominal_scheduled_slot")
        observed = _utc(
            self.observed_current_utc_timestamp,
            "observed_current_utc_timestamp",
        )
        request_at = _utc(self.request_timestamp_utc, "request_timestamp_utc")
        completed_at = _utc(
            self.terminal_completed_at_utc,
            "terminal_completed_at_utc",
        )
        if completed_at < request_at or observed < request_at:
            raise GuardedCaptureRunnerConfigError(
                "explicit capture timestamps are not chronological"
            )
        _nonnegative(self.launch_retry_ordinal, "launch_retry_ordinal")
        _nonnegative(
            self.monotonic_duration_nanoseconds,
            "monotonic_duration_nanoseconds",
        )
        if type(self.acl_mode) is not LaunchGuardAclPolicy:
            raise GuardedCaptureRunnerConfigError("acl_mode is invalid")
        for value, label in (
            (self.market_hours_schedule_artifact, "market_hours_schedule_artifact"),
            (self.capture_policy_artifact, "capture_policy_artifact"),
            (self.capture_configuration_artifact, "capture_configuration_artifact"),
            (self.credential_reference_artifact, "credential_reference_artifact"),
            (self.snapshot_destination, "snapshot_destination"),
        ):
            if type(value) is not ExplicitArtifactReference:
                raise GuardedCaptureRunnerConfigError(f"{label} is invalid")
        for value, label in (
            (self.executable_release_evidence, "executable_release_evidence"),
            (self.software_release_evidence, "software_release_evidence"),
            (
                self.approved_python_executable_evidence,
                "approved_python_executable_evidence",
            ),
            (self.approved_child_script_evidence, "approved_child_script_evidence"),
        ):
            if type(value) is not ArtifactEvidence:
                raise GuardedCaptureRunnerConfigError(f"{label} is invalid")
        if type(self.manual_disable_active) is not bool:
            raise GuardedCaptureRunnerConfigError("manual_disable_active must be bool")
        if type(self.capture_health) is not CaptureOnlyHealthConfig:
            raise GuardedCaptureRunnerConfigError("capture_health is invalid")
        if (
            type(self.production_xnys_hours_authority)
            is not ProductionXnysHoursAuthority
        ):
            raise GuardedCaptureRunnerConfigError(
                "production hours authority is invalid"
            )
        for value, label, maximum in (
            (self.process_id, "process_id", (1 << 31) - 1),
            (self.maximum_runtime_seconds, "maximum_runtime_seconds", 31_536_000),
            (self.wall_timeout_seconds, "wall_timeout_seconds", 300),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise GuardedCaptureRunnerConfigError(f"{label} is outside its bound")
        if (
            type(self.mutex_timeout_seconds) is not int
            or not 0 <= self.mutex_timeout_seconds <= 4_294_967
        ):
            raise GuardedCaptureRunnerConfigError("mutex_timeout_seconds is invalid")
        if (
            type(self.termination_grace_seconds) is not int
            or not 1 <= self.termination_grace_seconds <= 30
        ):
            raise GuardedCaptureRunnerConfigError(
                "termination_grace_seconds is invalid"
            )
        if not _SID.fullmatch(self.account_sid):
            raise GuardedCaptureRunnerConfigError("account_sid is invalid")
        for value, label in (
            (self.acquisition_timestamp_utc, "acquisition_timestamp_utc"),
            (self.release_timestamp_utc, "release_timestamp_utc"),
            (self.process_creation_timestamp_utc, "process_creation_timestamp_utc"),
        ):
            _timestamp_text(value, label)
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(
            self,
            "nominal_scheduled_slot",
            _utc(self.nominal_scheduled_slot, "nominal_scheduled_slot"),
        )
        object.__setattr__(self, "observed_current_utc_timestamp", observed)
        object.__setattr__(self, "request_timestamp_utc", request_at)
        object.__setattr__(self, "terminal_completed_at_utc", completed_at)

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


_ROOT_FIELDS = {
    "schema_version",
    "authority_root",
    "scheduler_audit_root",
    "capture_attempt_root",
    "authority_epoch_id",
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
    "terminal_completed_at_utc",
    "request_timestamp_utc",
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
    "capture_configuration_artifact",
    "credential_reference_artifact",
    "snapshot_destination",
    "software_release_evidence",
    "credential_reference_version",
    "snapshot_capture_request_id",
    "allocation_history_policy_version",
    "allocation_policy_version",
    "terminal_policy_version",
    "runner_policy_version",
    "approved_python_executable",
    "approved_python_executable_evidence",
    "approved_child_script",
    "approved_child_script_evidence",
    "process_evidence_directory",
    "controlled_temp_directory",
    "termination_grace_seconds",
    "wall_timeout_seconds",
    "manual_disable_active",
    "capture_health",
    "production_xnys_hours_authority",
}
_FILE_REFERENCE_FIELDS = {"artifact_id", "path", "sha256", "byte_length"}
_EVIDENCE_FIELDS = {"artifact_id", "sha256", "byte_length"}
_HEALTH_FIELDS = {"audit_ok", "disk_watermark_ok", "backup_ok", "notification_ok"}
_HOURS_AUTHORITY_FIELDS = {"status", "provenance", "schedule_evidence"}


def load_guarded_capture_runner_config(path: Path) -> GuardedCaptureRunnerConfig:
    """Load only the runner config; referenced artifacts remain unopened."""
    payload = read_safe_regular_file(
        path,
        MAX_GUARDED_CAPTURE_RUNNER_CONFIG_BYTES,
        "guarded capture runner config",
    )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise GuardedCaptureRunnerConfigError("config BOM is not permitted")
    try:
        root_value = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except GuardedCaptureRunnerConfigError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardedCaptureRunnerConfigError(
            "config must be strict UTF-8 JSON"
        ) from exc
    root = _object(root_value, _ROOT_FIELDS, "config")
    if _integer(root["schema_version"], "schema_version") != 1:
        raise GuardedCaptureRunnerConfigError("config schema_version must be 1")
    base = Path(os.path.abspath(path)).parent
    phase = _enum(ScheduledPhase, root["scheduled_phase"], "scheduled_phase")
    if phase is not ScheduledPhase.CAPTURE:
        raise GuardedCaptureRunnerConfigError("scheduled_phase must be CAPTURE")
    return GuardedCaptureRunnerConfig(
        authority_root=_absolute_path(root["authority_root"], base, "authority_root"),
        scheduler_audit_root=_absolute_path(
            root["scheduler_audit_root"], base, "scheduler_audit_root"
        ),
        capture_attempt_root=_absolute_path(
            root["capture_attempt_root"], base, "capture_attempt_root"
        ),
        authority_epoch_id=_uuid(root["authority_epoch_id"], "authority_epoch_id"),
        scheduled_phase=phase,
        target_session=TradingSession(_date(root["target_session"], "target_session")),
        execution_session=TradingSession(
            _date(root["execution_session"], "execution_session")
        ),
        symbols=tuple(
            Symbol(_string(item, "symbols"))
            for item in _array(root["symbols"], "symbols")
        ),
        universe_policy_version=_policy(
            root["universe_policy_version"], "universe_policy_version"
        ),
        readiness_policy_version=_policy(
            root["readiness_policy_version"], "readiness_policy_version"
        ),
        selection_policy_version=_policy(
            root["selection_policy_version"], "selection_policy_version"
        ),
        nominal_scheduled_slot=_timestamp(
            root["nominal_scheduled_slot"], "nominal_scheduled_slot"
        ),
        launch_retry_ordinal=_nonnegative(
            root["launch_retry_ordinal"], "launch_retry_ordinal"
        ),
        observed_current_utc_timestamp=_timestamp(
            root["observed_current_utc_timestamp"], "observed_current_utc_timestamp"
        ),
        acquisition_timestamp_utc=_timestamp_text(
            root["acquisition_timestamp_utc"], "acquisition_timestamp_utc"
        ),
        release_timestamp_utc=_timestamp_text(
            root["release_timestamp_utc"], "release_timestamp_utc"
        ),
        terminal_completed_at_utc=_timestamp(
            root["terminal_completed_at_utc"], "terminal_completed_at_utc"
        ),
        request_timestamp_utc=_timestamp(
            root["request_timestamp_utc"], "request_timestamp_utc"
        ),
        monotonic_duration_nanoseconds=_nonnegative(
            root["monotonic_duration_nanoseconds"], "monotonic_duration_nanoseconds"
        ),
        machine_authority_id=_uuid(
            root["machine_authority_id"], "machine_authority_id"
        ),
        boot_session_evidence=_string(
            root["boot_session_evidence"], "boot_session_evidence"
        ),
        process_id=_positive(root["process_id"], "process_id"),
        process_creation_timestamp_utc=_timestamp_text(
            root["process_creation_timestamp_utc"], "process_creation_timestamp_utc"
        ),
        account_sid=_string(root["account_sid"], "account_sid"),
        executable_release_evidence=_evidence(
            root["executable_release_evidence"], "executable_release_evidence"
        ),
        maximum_runtime_seconds=_positive(
            root["maximum_runtime_seconds"], "maximum_runtime_seconds"
        ),
        mutex_timeout_seconds=_nonnegative(
            root["mutex_timeout_seconds"], "mutex_timeout_seconds"
        ),
        launch_guard_policy_version=_policy(
            root["launch_guard_policy_version"], "launch_guard_policy_version"
        ),
        acl_mode=_enum(LaunchGuardAclPolicy, root["acl_mode"], "acl_mode"),
        market_hours_schedule_artifact=_file_reference(
            root["market_hours_schedule_artifact"],
            base,
            "market_hours_schedule_artifact",
        ),
        capture_policy_artifact=_file_reference(
            root["capture_policy_artifact"], base, "capture_policy_artifact"
        ),
        capture_configuration_artifact=_file_reference(
            root["capture_configuration_artifact"],
            base,
            "capture_configuration_artifact",
        ),
        credential_reference_artifact=_file_reference(
            root["credential_reference_artifact"], base, "credential_reference_artifact"
        ),
        snapshot_destination=_file_reference(
            root["snapshot_destination"], base, "snapshot_destination"
        ),
        software_release_evidence=_evidence(
            root["software_release_evidence"], "software_release_evidence"
        ),
        credential_reference_version=_policy(
            root["credential_reference_version"], "credential_reference_version"
        ),
        snapshot_capture_request_id=_uuid(
            root["snapshot_capture_request_id"], "snapshot_capture_request_id"
        ),
        allocation_history_policy_version=_policy(
            root["allocation_history_policy_version"],
            "allocation_history_policy_version",
        ),
        allocation_policy_version=_policy(
            root["allocation_policy_version"], "allocation_policy_version"
        ),
        terminal_policy_version=_policy(
            root["terminal_policy_version"], "terminal_policy_version"
        ),
        runner_policy_version=_policy(
            root["runner_policy_version"], "runner_policy_version"
        ),
        approved_python_executable=_absolute_path(
            root["approved_python_executable"], base, "approved_python_executable"
        ),
        approved_python_executable_evidence=_evidence(
            root["approved_python_executable_evidence"],
            "approved_python_executable_evidence",
        ),
        approved_child_script=_absolute_path(
            root["approved_child_script"], base, "approved_child_script"
        ),
        approved_child_script_evidence=_evidence(
            root["approved_child_script_evidence"], "approved_child_script_evidence"
        ),
        process_evidence_directory=_absolute_path(
            root["process_evidence_directory"], base, "process_evidence_directory"
        ),
        controlled_temp_directory=_absolute_path(
            root["controlled_temp_directory"], base, "controlled_temp_directory"
        ),
        termination_grace_seconds=_positive(
            root["termination_grace_seconds"], "termination_grace_seconds"
        ),
        wall_timeout_seconds=_positive(
            root["wall_timeout_seconds"], "wall_timeout_seconds"
        ),
        manual_disable_active=_boolean(
            root["manual_disable_active"], "manual_disable_active"
        ),
        capture_health=_health(root["capture_health"]),
        production_xnys_hours_authority=_hours_authority(
            root["production_xnys_hours_authority"]
        ),
    )


def _hours_authority(value: object) -> ProductionXnysHoursAuthority:
    root = _object(value, _HOURS_AUTHORITY_FIELDS, "production_xnys_hours_authority")
    status = _enum(ProductionXnysHoursAuthorityStatus, root["status"], "hours status")
    provenance = (
        None
        if root["provenance"] is None
        else _string(root["provenance"], "hours provenance")
    )
    evidence = (
        None
        if root["schedule_evidence"] is None
        else _evidence(root["schedule_evidence"], "hours schedule evidence")
    )
    return ProductionXnysHoursAuthority(status, provenance, evidence)


def _health(value: object) -> CaptureOnlyHealthConfig:
    root = _object(value, _HEALTH_FIELDS, "capture_health")
    return CaptureOnlyHealthConfig(
        audit_ok=_boolean(root["audit_ok"], "capture_health.audit_ok"),
        disk_watermark_ok=_boolean(
            root["disk_watermark_ok"], "capture_health.disk_watermark_ok"
        ),
        backup_ok=_boolean(root["backup_ok"], "capture_health.backup_ok"),
        notification_ok=_boolean(
            root["notification_ok"], "capture_health.notification_ok"
        ),
    )


def _file_reference(value: object, base: Path, label: str) -> ExplicitArtifactReference:
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
    if len(text) > MAX_GUARDED_CAPTURE_RUNNER_PATH_CHARACTERS or "\x00" in text:
        raise GuardedCaptureRunnerConfigError(f"{label} is invalid")
    path = Path(text)
    if not path.is_absolute():
        path = base / path
    try:
        return Path(os.path.abspath(path))
    except (OSError, ValueError) as exc:
        raise GuardedCaptureRunnerConfigError(f"{label} is invalid") from exc


def _duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GuardedCaptureRunnerConfigError(f"duplicate config member: {key}")
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise GuardedCaptureRunnerConfigError("floats are not permitted")


def _reject_constant(_: str) -> None:
    raise GuardedCaptureRunnerConfigError("constants are not permitted")


def _object(value: object, fields: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise GuardedCaptureRunnerConfigError(f"{label} members are not exact")
    return value


def _array(value: object, label: str) -> list[object]:
    if type(value) is not list or len(value) > MAX_GUARDED_CAPTURE_RUNNER_REFERENCES:
        raise GuardedCaptureRunnerConfigError(f"{label} must be bounded array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value or len(value) > 4096:
        raise GuardedCaptureRunnerConfigError(f"{label} must be bounded nonempty text")
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise GuardedCaptureRunnerConfigError(f"{label} must be bool")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int or not -_MAX_INTEGER <= value <= _MAX_INTEGER:
        raise GuardedCaptureRunnerConfigError(f"{label} must be bounded integer")
    return value


def _nonnegative(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed < 0:
        raise GuardedCaptureRunnerConfigError(f"{label} must be nonnegative")
    return parsed


def _positive(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed <= 0:
        raise GuardedCaptureRunnerConfigError(f"{label} must be positive")
    return parsed


def _uuid(value: object, label: str) -> UUID:
    text = _string(value, label)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise GuardedCaptureRunnerConfigError(f"{label} must be UUID") from exc
    if str(parsed) != text or parsed.int == 0:
        raise GuardedCaptureRunnerConfigError(f"{label} must be canonical nonzero UUID")
    return parsed


def _sha(value: object, label: str) -> str:
    text = _string(value, label)
    if _SHA256.fullmatch(text) is None:
        raise GuardedCaptureRunnerConfigError(f"{label} must be lowercase SHA-256")
    return text


def _timestamp(value: object, label: str) -> datetime:
    return datetime.fromisoformat(
        _timestamp_text(value, label).replace("Z", "+00:00")
    ).astimezone(UTC)


def _timestamp_text(value: object, label: str) -> str:
    text = _string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GuardedCaptureRunnerConfigError(f"{label} must be timestamp") from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or canonical_timestamp(parsed.astimezone(UTC)) != text
    ):
        raise GuardedCaptureRunnerConfigError(f"{label} must be canonical UTC")
    return text


def _utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise GuardedCaptureRunnerConfigError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise GuardedCaptureRunnerConfigError(f"{label} must be ISO date") from exc
    if parsed.isoformat() != text:
        raise GuardedCaptureRunnerConfigError(f"{label} must be canonical ISO date")
    return parsed


def _enum(enum_type: type[StrEnum], value: object, label: str) -> StrEnum:
    text = _string(value, label)
    try:
        return enum_type(text)
    except ValueError as exc:
        raise GuardedCaptureRunnerConfigError(f"{label} is unsupported") from exc


def _policy(value: object, label: str) -> str:
    if type(value) is not str or _POLICY.fullmatch(value) is None:
        raise GuardedCaptureRunnerConfigError(f"{label} must be a canonical policy")
    return value
