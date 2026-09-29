"""Architecture-127 pure D10 durable wake-evidence contracts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PureWindowsPath

from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as scheduler_contract,
)
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10ActivationLease,
    format_utc_instant,
    parse_utc_instant,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_PRODUCTION_PYTHON,
)
from trading_bot.runtime.personal_desktop_d10_python_substrate import VERSION
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    D10_WAKE_EVIDENCE_SCHEMA,
    MAX_D10_SUMMARY_WAKES,
    MAX_D10_WAKE_EVIDENCE_BYTES,
    D10WakeOutcome,
    D10WakeStopReason,
)

D10_WAKE_EVIDENCE_ROOT = PureWindowsPath(r"F:\AITradingBot\D10\evidence")
D10_GUARD_WAKE_START_EVIDENCE_SCHEMA = "personal-desktop-d10-guard-start/v1"
D10_GUARD_TERMINAL_EVIDENCE_SCHEMA = "personal-desktop-d10-guard-evidence/v1"
MAX_D10_GUARD_WAKE_START_EVIDENCE_BYTES = 2048
MAX_D10_GUARD_TERMINAL_EVIDENCE_BYTES = 2048
MAX_D10_EVIDENCE_LOG_RECORDS = MAX_D10_SUMMARY_WAKES
MAX_D10_EVIDENCE_LOG_BYTES = MAX_D10_EVIDENCE_LOG_RECORDS * (
    max(MAX_D10_WAKE_EVIDENCE_BYTES, MAX_D10_GUARD_TERMINAL_EVIDENCE_BYTES) + 1
)

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


class D10WakeEvidenceLogError(ValueError):
    """Durable D10 evidence bytes violate the frozen source contract."""


class D10GuardTerminalReason(StrEnum):
    CHILD_LAUNCH_FAILED = "CHILD_LAUNCH_FAILED"
    CHILD_OUTPUT_MISSING = "CHILD_OUTPUT_MISSING"
    CHILD_OUTPUT_INVALID = "CHILD_OUTPUT_INVALID"
    CHILD_EXIT_MISMATCH = "CHILD_EXIT_MISMATCH"


@dataclass(frozen=True, slots=True)
class D10GuardWakeStartEvidence:
    """Bounded guard-owned marker durably committed before source launch."""

    schema: str
    observed_at_utc: datetime
    deployment_id: str
    soak_id: str

    def __post_init__(self) -> None:
        if (
            self.schema != D10_GUARD_WAKE_START_EVIDENCE_SCHEMA
            or type(self.observed_at_utc) is not datetime
            or self.observed_at_utc.tzinfo is not UTC
            or type(self.deployment_id) is not str
            or _UUID.fullmatch(self.deployment_id) is None
            or type(self.soak_id) is not str
            or _UUID.fullmatch(self.soak_id) is None
        ):
            raise D10WakeEvidenceLogError("guard wake-start evidence is invalid")

    def canonical_bytes(self) -> bytes:
        payload = {
            "schema": self.schema,
            "observed_at_utc": format_utc_instant(self.observed_at_utc),
            "deployment_id": self.deployment_id,
            "soak_id": self.soak_id,
        }
        data = _canonical_json_bytes(payload)
        if len(data) > MAX_D10_GUARD_WAKE_START_EVIDENCE_BYTES:
            raise D10WakeEvidenceLogError("guard wake-start evidence exceeds bound")
        return data


@dataclass(frozen=True, slots=True)
class PersistedD10WakeRecord:
    """Validated canonical ordinary wake record."""

    canonical_bytes: bytes
    outcome: D10WakeOutcome
    stop_reason: D10WakeStopReason | None
    observed_at_utc: datetime

    def __post_init__(self) -> None:
        if (
            type(self.canonical_bytes) is not bytes
            or not self.canonical_bytes
            or len(self.canonical_bytes) > MAX_D10_WAKE_EVIDENCE_BYTES
            or type(self.outcome) is not D10WakeOutcome
            or (
                self.stop_reason is not None
                and type(self.stop_reason) is not D10WakeStopReason
            )
            or (self.outcome is D10WakeOutcome.STOPPED)
            != (self.stop_reason is not None)
            or type(self.observed_at_utc) is not datetime
            or self.observed_at_utc.tzinfo is not UTC
        ):
            raise D10WakeEvidenceLogError("persisted wake record is invalid")


@dataclass(frozen=True, slots=True)
class D10GuardTerminalEvidence:
    """Bounded sanitized terminal evidence emitted only by the sealed guard."""

    schema: str
    reason: D10GuardTerminalReason
    observed_at_utc: datetime
    deployment_id: str
    soak_id: str

    def __post_init__(self) -> None:
        if (
            self.schema != D10_GUARD_TERMINAL_EVIDENCE_SCHEMA
            or type(self.reason) is not D10GuardTerminalReason
            or type(self.observed_at_utc) is not datetime
            or self.observed_at_utc.tzinfo is not UTC
            or type(self.deployment_id) is not str
            or _UUID.fullmatch(self.deployment_id) is None
            or type(self.soak_id) is not str
            or _UUID.fullmatch(self.soak_id) is None
        ):
            raise D10WakeEvidenceLogError("guard terminal evidence is invalid")

    def canonical_bytes(self) -> bytes:
        payload = {
            "schema": self.schema,
            "reason": self.reason.value,
            "observed_at_utc": format_utc_instant(self.observed_at_utc),
            "deployment_id": self.deployment_id,
            "soak_id": self.soak_id,
            "terminal": True,
        }
        data = _canonical_json_bytes(payload)
        if len(data) > MAX_D10_GUARD_TERMINAL_EVIDENCE_BYTES:
            raise D10WakeEvidenceLogError("guard terminal evidence exceeds bound")
        return data


@dataclass(frozen=True, slots=True)
class D10WakeEvidenceLogSummary:
    """Sanitized complete-log observation; carries no authority or raw bytes."""

    record_count: int
    wake_count: int
    terminal: bool
    terminal_kind: str | None
    first_observed_at_utc: datetime | None
    last_observed_at_utc: datetime | None
    last_outcome: D10WakeOutcome | None
    last_stop_reason: D10WakeStopReason | None
    last_guard_reason: D10GuardTerminalReason | None

    def __post_init__(self) -> None:
        if (
            type(self.record_count) is not int
            or self.record_count < 0
            or type(self.wake_count) is not int
            or self.wake_count < 0
            or self.wake_count > self.record_count
            or type(self.terminal) is not bool
            or (self.terminal_kind is not None and type(self.terminal_kind) is not str)
            or (
                self.first_observed_at_utc is not None
                and (
                    type(self.first_observed_at_utc) is not datetime
                    or self.first_observed_at_utc.tzinfo is not UTC
                )
            )
            or (
                self.last_observed_at_utc is not None
                and (
                    type(self.last_observed_at_utc) is not datetime
                    or self.last_observed_at_utc.tzinfo is not UTC
                )
            )
            or (
                self.last_outcome is not None
                and type(self.last_outcome) is not D10WakeOutcome
            )
            or (
                self.last_stop_reason is not None
                and type(self.last_stop_reason) is not D10WakeStopReason
            )
            or (
                self.last_guard_reason is not None
                and type(self.last_guard_reason) is not D10GuardTerminalReason
            )
        ):
            raise D10WakeEvidenceLogError("wake evidence summary is invalid")


def d10_wake_evidence_path(lease: D10ActivationLease) -> PureWindowsPath:
    """Derive the only current-soak evidence path from a verified lease model."""

    if type(lease) is not D10ActivationLease:
        raise D10WakeEvidenceLogError("evidence path requires exact activation lease")
    if _UUID.fullmatch(lease.soak_id) is None:
        raise D10WakeEvidenceLogError("soak identity is not canonical")
    return D10_WAKE_EVIDENCE_ROOT / f"wake-{lease.soak_id}.jsonl"


def parse_persisted_d10_wake_record(
    data: bytes, lease: D10ActivationLease
) -> PersistedD10WakeRecord:
    """Validate one exact canonical ordinary D10 wake record against its lease."""

    if type(lease) is not D10ActivationLease:
        raise D10WakeEvidenceLogError("wake record requires exact activation lease")
    value = _parse_json(data)
    _require_keys(
        value,
        {
            "schema",
            "outcome",
            "stop_reason",
            "observed_at_utc",
            "deployment",
            "soak",
            "runtime",
            "session",
            "capture",
            "history",
            "settlement",
            "decision",
            "budgets",
            "effect_crossings",
            "final_gates",
        },
    )
    if value["schema"] != D10_WAKE_EVIDENCE_SCHEMA:
        raise D10WakeEvidenceLogError("wake evidence schema differs")
    try:
        outcome = D10WakeOutcome(value["outcome"])
        stop_reason = (
            None
            if value["stop_reason"] is None
            else D10WakeStopReason(value["stop_reason"])
        )
        observed_at = _parse_wake_utc(value["observed_at_utc"])
    except (TypeError, ValueError) as exc:
        raise D10WakeEvidenceLogError("wake outcome or time is invalid") from exc
    if (outcome is D10WakeOutcome.STOPPED) != (stop_reason is not None):
        raise D10WakeEvidenceLogError("wake stop fields disagree")

    deployment = _dict(value["deployment"], "deployment")
    _require_keys(
        deployment,
        {
            "id",
            "attestation_sha256",
            "source_head",
            "source_tree",
            "executable_file_count",
        },
    )
    if (
        deployment["id"] != lease.deployment_id
        or deployment["attestation_sha256"] != lease.attestation_sha256
        or deployment["source_head"] != lease.certified_source_head
        or deployment["source_tree"] != lease.certified_source_tree
        or type(deployment["executable_file_count"]) is not int
        or deployment["executable_file_count"] <= 0
    ):
        raise D10WakeEvidenceLogError("wake deployment identity differs")

    soak = _dict(value["soak"], "soak")
    _require_keys(soak, {"id", "activation_utc", "end_utc"})
    if (
        soak["id"] != lease.soak_id
        or _parse_wake_utc(soak["activation_utc"]) != lease.accepted_activation_utc
        or _parse_wake_utc(soak["end_utc"]) != lease.end_utc
    ):
        raise D10WakeEvidenceLogError("wake soak identity differs")

    runtime = _dict(value["runtime"], "runtime")
    _require_keys(
        runtime,
        {
            "scheduler_contract_schema",
            "scheduler_task_path",
            "trading_sid",
            "production_python",
            "production_python_version",
        },
    )
    if runtime != {
        "scheduler_contract_schema": scheduler_contract.D10_SCHEDULER_CONTRACT_SCHEMA,
        "scheduler_task_path": scheduler_contract.D10_SCHEDULER_CONTRACT.task_path,
        "trading_sid": lease.trading_sid,
        "production_python": D10_PRODUCTION_PYTHON,
        "production_python_version": VERSION,
    }:
        raise D10WakeEvidenceLogError("wake runtime identity differs")

    budgets = _dict(value["budgets"], "budgets")
    _require_keys(
        budgets,
        {
            "provider_attempts",
            "settlement_attempts",
            "publication_attempts",
            "receipt_recovery_attempts",
            "broker_live_calls",
        },
    )
    if (
        any(type(budgets[name]) is not int for name in budgets)
        or any(
            budgets[name] not in (0, 1)
            for name in (
                "provider_attempts",
                "settlement_attempts",
                "publication_attempts",
            )
        )
        or budgets["receipt_recovery_attempts"] != 0
        or budgets["broker_live_calls"] != 0
    ):
        raise D10WakeEvidenceLogError("wake effect budgets are invalid")

    crossings = _dict(value["effect_crossings"], "effect_crossings")
    _require_keys(crossings, {"provider", "settlement", "publication"})
    if any(type(item) is not bool for item in crossings.values()):
        raise D10WakeEvidenceLogError("wake effect crossings are invalid")
    if (
        (crossings["provider"] and budgets["provider_attempts"] != 1)
        or (crossings["settlement"] and budgets["settlement_attempts"] != 1)
        or (crossings["publication"] and budgets["publication_attempts"] != 1)
    ):
        raise D10WakeEvidenceLogError("wake crossings disagree with budgets")

    final_gates = _dict(value["final_gates"], "final_gates")
    if final_gates != {"all_closed": True, "closed_count": 8}:
        raise D10WakeEvidenceLogError("wake final gate proof differs")

    session = _dict(value["session"], "session")
    _require_keys(session, {"completed", "next_execution", "preopen_deadline_utc"})
    capture = _dict(value["capture"], "capture")
    _require_keys(
        capture,
        {
            "classification",
            "selection_id",
            "snapshot_id",
            "attempt_id",
            "terminal_state",
            "provider_call_disposition",
        },
    )
    history = _dict(value["history"], "history")
    _require_keys(
        history,
        {
            "classification",
            "reconciled_count",
            "current_decision_id",
            "unresolved_decision_id",
        },
    )
    settlement = _dict(value["settlement"], "settlement")
    _require_keys(
        settlement,
        {
            "decision_id",
            "classification",
            "reconciliation",
            "plan_id",
            "invocation_id",
            "operation_id",
            "application_id",
            "predecessor_checkpoint_id",
            "successor_checkpoint_id",
        },
    )
    decision = _dict(value["decision"], "decision")
    _require_keys(decision, {"id", "publication", "reconciliation", "finalized_id"})

    optional_strings = (
        session["completed"],
        session["next_execution"],
        capture["classification"],
        capture["selection_id"],
        capture["snapshot_id"],
        capture["attempt_id"],
        capture["terminal_state"],
        capture["provider_call_disposition"],
        history["classification"],
        history["current_decision_id"],
        history["unresolved_decision_id"],
        settlement["decision_id"],
        settlement["classification"],
        settlement["reconciliation"],
        settlement["plan_id"],
        settlement["invocation_id"],
        settlement["operation_id"],
        settlement["application_id"],
        settlement["predecessor_checkpoint_id"],
        settlement["successor_checkpoint_id"],
        decision["id"],
        decision["publication"],
        decision["reconciliation"],
        decision["finalized_id"],
    )
    if any(item is not None and type(item) is not str for item in optional_strings):
        raise D10WakeEvidenceLogError("wake optional evidence type differs")
    if type(history["reconciled_count"]) is not int or history["reconciled_count"] < 0:
        raise D10WakeEvidenceLogError("wake historical count differs")
    deadline = session["preopen_deadline_utc"]
    if deadline is not None:
        _parse_wake_utc(deadline)

    canonical = _canonical_json_bytes(value)
    if canonical != data or len(canonical) > MAX_D10_WAKE_EVIDENCE_BYTES:
        raise D10WakeEvidenceLogError("wake evidence bytes are not canonical")
    return PersistedD10WakeRecord(canonical, outcome, stop_reason, observed_at)


def parse_guard_wake_start_evidence(
    data: bytes, lease: D10ActivationLease
) -> D10GuardWakeStartEvidence:
    """Parse one exact guard-owned start marker bound to the active lease."""

    if type(lease) is not D10ActivationLease:
        raise D10WakeEvidenceLogError("guard start requires exact activation lease")
    value = _parse_json(data)
    _require_keys(
        value,
        {
            "schema",
            "observed_at_utc",
            "deployment_id",
            "soak_id",
        },
    )
    try:
        model = D10GuardWakeStartEvidence(
            schema=value["schema"],
            observed_at_utc=parse_utc_instant(value["observed_at_utc"]),
            deployment_id=value["deployment_id"],
            soak_id=value["soak_id"],
        )
    except (TypeError, ValueError) as exc:
        raise D10WakeEvidenceLogError("guard wake-start record is invalid") from exc
    if (
        model.deployment_id != lease.deployment_id
        or model.soak_id != lease.soak_id
        or model.canonical_bytes() != data
    ):
        raise D10WakeEvidenceLogError("guard wake-start identity or bytes differ")
    return model


def parse_guard_terminal_evidence(
    data: bytes, lease: D10ActivationLease
) -> D10GuardTerminalEvidence:
    """Parse one exact canonical guard-terminal record bound to the lease."""

    if type(lease) is not D10ActivationLease:
        raise D10WakeEvidenceLogError("guard record requires exact activation lease")
    value = _parse_json(data)
    _require_keys(
        value,
        {
            "schema",
            "reason",
            "observed_at_utc",
            "deployment_id",
            "soak_id",
            "terminal",
        },
    )
    if value["terminal"] is not True:
        raise D10WakeEvidenceLogError("guard terminal marker differs")
    try:
        model = D10GuardTerminalEvidence(
            schema=value["schema"],
            reason=D10GuardTerminalReason(value["reason"]),
            observed_at_utc=parse_utc_instant(value["observed_at_utc"]),
            deployment_id=value["deployment_id"],
            soak_id=value["soak_id"],
        )
    except (TypeError, ValueError) as exc:
        raise D10WakeEvidenceLogError("guard terminal record is invalid") from exc
    if (
        model.deployment_id != lease.deployment_id
        or model.soak_id != lease.soak_id
        or model.canonical_bytes() != data
    ):
        raise D10WakeEvidenceLogError("guard terminal identity or bytes differ")
    return model


def summarize_d10_wake_evidence_log(
    data: bytes, lease: D10ActivationLease
) -> D10WakeEvidenceLogSummary:
    """Validate the complete append-only log and return bounded sanitized facts."""

    if type(lease) is not D10ActivationLease:
        raise D10WakeEvidenceLogError("wake log requires exact activation lease")
    if type(data) is not bytes or len(data) > MAX_D10_EVIDENCE_LOG_BYTES:
        raise D10WakeEvidenceLogError("wake evidence log size is invalid")
    if not data:
        return D10WakeEvidenceLogSummary(
            0,
            0,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    if not data.endswith(b"\n"):
        raise D10WakeEvidenceLogError("wake evidence log has a partial final record")
    lines = data[:-1].split(b"\n")
    if (
        not lines
        or len(lines) > MAX_D10_EVIDENCE_LOG_RECORDS
        or any(not line for line in lines)
    ):
        raise D10WakeEvidenceLogError("wake evidence log record count is invalid")

    previous: datetime | None = None
    first: datetime | None = None
    last: datetime | None = None
    pending_start = False
    terminal = False
    terminal_kind: str | None = None
    wake_count = 0
    last_outcome: D10WakeOutcome | None = None
    last_stop_reason: D10WakeStopReason | None = None
    last_guard_reason: D10GuardTerminalReason | None = None

    for line in lines:
        if terminal:
            raise D10WakeEvidenceLogError("terminal wake evidence is not final")
        if len(line) > MAX_D10_WAKE_EVIDENCE_BYTES:
            raise D10WakeEvidenceLogError("wake evidence record exceeds its bound")
        value = _parse_json(line)
        schema = value.get("schema")

        if schema == D10_GUARD_WAKE_START_EVIDENCE_SCHEMA:
            if pending_start:
                raise D10WakeEvidenceLogError("wake-start evidence is unresolved")
            start = parse_guard_wake_start_evidence(line, lease)
            observed = start.observed_at_utc
            pending_start = True
            terminal_kind = "WAKE_STARTED_INCOMPLETE"
            last_outcome = None
            last_stop_reason = None
            last_guard_reason = None
        elif schema == D10_WAKE_EVIDENCE_SCHEMA:
            if not pending_start:
                raise D10WakeEvidenceLogError("ordinary wake lacks wake-start evidence")
            record = parse_persisted_d10_wake_record(line, lease)
            observed = record.observed_at_utc
            pending_start = False
            wake_count += 1
            last_outcome = record.outcome
            last_stop_reason = record.stop_reason
            last_guard_reason = None
            if record.outcome is D10WakeOutcome.STOPPED:
                terminal = True
                terminal_kind = "STOPPED"
            else:
                terminal_kind = None
        elif schema == D10_GUARD_TERMINAL_EVIDENCE_SCHEMA:
            if not pending_start:
                raise D10WakeEvidenceLogError(
                    "guard terminal lacks wake-start evidence"
                )
            record = parse_guard_terminal_evidence(line, lease)
            observed = record.observed_at_utc
            pending_start = False
            terminal = True
            terminal_kind = "GUARD_TERMINAL"
            last_outcome = None
            last_stop_reason = None
            last_guard_reason = record.reason
        else:
            raise D10WakeEvidenceLogError("wake evidence record schema differs")

        if previous is not None and observed < previous:
            raise D10WakeEvidenceLogError(
                "wake evidence observation time moved backward"
            )
        if first is None:
            first = observed
        previous = observed
        last = observed

    if pending_start:
        terminal = True
        terminal_kind = "WAKE_STARTED_INCOMPLETE"

    return D10WakeEvidenceLogSummary(
        record_count=len(lines),
        wake_count=wake_count,
        terminal=terminal,
        terminal_kind=terminal_kind,
        first_observed_at_utc=first,
        last_observed_at_utc=last,
        last_outcome=last_outcome,
        last_stop_reason=last_stop_reason,
        last_guard_reason=last_guard_reason,
    )


def _parse_wake_utc(value: object) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise D10WakeEvidenceLogError("wake timestamp is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00").astimezone(UTC)
    except ValueError as exc:
        raise D10WakeEvidenceLogError("wake timestamp is invalid") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise D10WakeEvidenceLogError("wake timestamp is not canonical UTC")
    return parsed


def _dict(value: object, name: str) -> dict[str, object]:
    if type(value) is not dict:
        raise D10WakeEvidenceLogError(f"{name} evidence must be an object")
    return value


def _require_keys(value: dict[str, object], expected: set[str]) -> None:
    if set(value) != expected:
        raise D10WakeEvidenceLogError("evidence field set differs")


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, UnicodeError, ValueError) as exc:
        raise D10WakeEvidenceLogError("evidence is not canonical JSON") from exc


def _parse_json(data: bytes) -> dict[str, object]:
    if type(data) is not bytes or not data or len(data) > MAX_D10_WAKE_EVIDENCE_BYTES:
        raise D10WakeEvidenceLogError("evidence record size is invalid")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in items:
            if key in value:
                raise D10WakeEvidenceLogError("duplicate evidence field")
            value[key] = item
        return value

    try:
        result = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                D10WakeEvidenceLogError("non-finite evidence value")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise D10WakeEvidenceLogError("evidence is not valid UTF-8 JSON") from exc
    if type(result) is not dict:
        raise D10WakeEvidenceLogError("evidence root must be an object")
    return result
