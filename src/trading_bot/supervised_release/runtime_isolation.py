"""Pure Architecture 134-F1R1-A runtime-isolation contracts.

This module describes an already-installed immutable release.  It deliberately
does not discover a checkout, invoke Git, inspect the host, read credentials,
contact a provider, mutate a scheduler/store, or execute an order.  Those
capabilities belong to separately reviewed installation and runtime adapters.

The records here contain only fixed identities, closed enums, sequence numbers,
and hashes.  No wall-clock value, path selected by a caller, provider payload,
exception text, or secret is accepted into an identity or diagnostic record.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from trading_bot.supervised_release.model import (
    PRODUCTION_PYTHON,
    ReleaseManifest,
    release_root,
)

RUNTIME_ISOLATION_SCHEMA = "arch134-f1r1-a-runtime-isolation/v1"
DIAGNOSTIC_SCHEMA = "arch134-f1r1-a-diagnostic/v1"
EFFECT_SCHEMA = "arch134-f1r1-a-effect/v1"
LIFECYCLE_SCHEMA = "arch134-f1r1-a-lifecycle/v1"
SUCCESSOR_OVERLAY_SCHEMA = "arch134-f1r1-a-successor-overlay/v1"
MAX_DIAGNOSTIC_BYTES = 4096
MAX_EFFECT_RECORDS = 8
MAX_LIFECYCLE_RECORDS = 32


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object, *, name: str, length: int = 64) -> None:
    if type(value) is not str or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError(f"{name} must be a lowercase hexadecimal digest")


def _runtime_id(value: object) -> None:
    if type(value) is not str or re.fullmatch(r"runtime-[0-9a-f]{64}", value) is None:
        raise ValueError("canonical immutable runtime identity required")


def _exact_fields(value: object, expected: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ValueError("exact closed fields required")
    return value


class RuntimeAdmissionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"


class RuntimeAdmissionReason(StrEnum):
    ADMITTED = "ADMITTED"
    INVALID_MATERIAL = "INVALID_MATERIAL"
    RELEASE_IDENTITY_DRIFT = "RELEASE_IDENTITY_DRIFT"
    RUNTIME_IDENTITY_DRIFT = "RUNTIME_IDENTITY_DRIFT"
    STATE_IDENTITY_DRIFT = "STATE_IDENTITY_DRIFT"


class DiagnosticReason(StrEnum):
    SOURCE_RELEASE_ADMISSION_FAILED = "SOURCE_RELEASE_ADMISSION_FAILED"
    RUNTIME_IDENTITY_DRIFT = "RUNTIME_IDENTITY_DRIFT"
    STATE_IDENTITY_DRIFT = "STATE_IDENTITY_DRIFT"
    CLOCK_WINDOW_REJECTED = "CLOCK_WINDOW_REJECTED"
    CREDENTIAL_ADMISSION_FAILED = "CREDENTIAL_ADMISSION_FAILED"
    PRE_EFFECT_GUARD_FAILED = "PRE_EFFECT_GUARD_FAILED"
    PROVIDER_ENTRY_FAILED = "PROVIDER_ENTRY_FAILED"
    QUOTE_TRANSPORT_FAILED = "QUOTE_TRANSPORT_FAILED"
    QUOTE_SCHEMA_REJECTED = "QUOTE_SCHEMA_REJECTED"
    PAPER_EFFECT_AMBIGUOUS = "PAPER_EFFECT_AMBIGUOUS"


class EffectOperation(StrEnum):
    QUOTE_REQUEST = "QUOTE_REQUEST"
    PAPER_MUTATION = "PAPER_MUTATION"
    BROKER_OPERATION = "BROKER_OPERATION"


class EffectStage(StrEnum):
    INTENT = "INTENT"
    PRE_ENTRY_REJECTED = "PRE_ENTRY_REJECTED"
    ENTRY_ADMITTED = "ENTRY_ADMITTED"
    ACK = "ACK"
    DIAGNOSTIC = "DIAGNOSTIC"


class EffectStatus(StrEnum):
    PRE_ENTRY_REJECTED = "PRE_ENTRY_REJECTED"
    AMBIGUOUS = "AMBIGUOUS"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class EffectConsumedError(RuntimeError):
    """A durable effect lineage is consumed and cannot be retried."""


@dataclass(frozen=True, slots=True)
class DurableStoreIdentity:
    """Logical durable-state identity, intentionally independent of a path."""

    name: str
    sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.name) is not str
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", self.name) is None
        ):
            raise ValueError("closed durable-store name required")
        _digest(self.sha256, name="durable store identity")

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class InstalledRuntimeMaterial:
    """Immutable local material sufficient for repeated runtime admission."""

    manifest: ReleaseManifest
    binding_sha256: str
    durable_store_identities: tuple[DurableStoreIdentity, ...] = ()

    def __post_init__(self) -> None:
        if type(self.manifest) is not ReleaseManifest:
            raise TypeError("exact release manifest required")
        _digest(self.binding_sha256, name="runtime binding")
        if type(self.durable_store_identities) is not tuple or any(
            type(value) is not DurableStoreIdentity
            for value in self.durable_store_identities
        ):
            raise TypeError("exact durable store identities required")
        names = [value.name.casefold() for value in self.durable_store_identities]
        if len(names) != len(set(names)):
            raise ValueError("duplicate durable store identity")

    @classmethod
    def from_manifest(
        cls,
        manifest: ReleaseManifest,
        *,
        binding_sha256: str,
        durable_store_identities: tuple[DurableStoreIdentity, ...] = (),
    ) -> InstalledRuntimeMaterial:
        return cls(manifest, binding_sha256, durable_store_identities)

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.manifest.to_json().encode("utf-8")).hexdigest()

    def _identity_material(self) -> dict[str, object]:
        return {
            "schema": RUNTIME_ISOLATION_SCHEMA,
            "release_id": self.manifest.release_id,
            "manifest_sha256": self.manifest_sha256,
            "binding_sha256": self.binding_sha256,
            "source_inventory": [
                entry.to_dict() for entry in self.manifest.source_inventory
            ],
            "source_inventory_sha256": self.manifest.source_inventory_sha256,
            "launcher_relative_path": self.manifest.launcher_relative_path,
            "launcher_sha256": self.manifest.launcher_sha256,
            "production_python_version": self.manifest.production_python_version,
            "production_python_sha256": self.manifest.production_python_sha256,
            "strategy_id": self.manifest.strategy_id,
            "strategy_version": self.manifest.strategy_version,
            "strategy_config_sha256": self.manifest.strategy_config_sha256,
            "risk_policy_id": self.manifest.risk_policy_id,
            "risk_policy_version": self.manifest.risk_policy_version,
            "risk_policy_sha256": self.manifest.risk_policy_sha256,
            "durable_store_identities": [
                value.to_dict() for value in self.durable_store_identities
            ],
        }

    @property
    def runtime_id(self) -> str:
        material = _canonical(self._identity_material()).encode("utf-8")
        return "runtime-" + hashlib.sha256(material).hexdigest()

    def to_json(self) -> str:
        return _canonical(self._identity_material() | {"runtime_id": self.runtime_id})


@dataclass(frozen=True, slots=True)
class RuntimeAdmissionProof:
    runtime_id: str
    release_id: str
    manifest_sha256: str
    binding_sha256: str
    release_root: str
    source_root: str
    launcher: str
    python_executable: str
    durable_store_identities: tuple[DurableStoreIdentity, ...]


@dataclass(frozen=True, slots=True)
class RuntimeAdmissionResult:
    status: RuntimeAdmissionStatus
    reason: RuntimeAdmissionReason
    proof: RuntimeAdmissionProof | None = None


def admit_installed_runtime(
    material: InstalledRuntimeMaterial,
    *,
    expected_runtime_id: str | None = None,
    expected_state_identities: tuple[DurableStoreIdentity, ...] | None = None,
) -> RuntimeAdmissionResult:
    """Admit immutable local material without consulting any development source."""
    try:
        if type(material) is not InstalledRuntimeMaterial:
            raise TypeError("exact installed runtime material required")
        runtime_id = material.runtime_id
        if expected_runtime_id is not None:
            _runtime_id(expected_runtime_id)
            if expected_runtime_id != runtime_id:
                return RuntimeAdmissionResult(
                    RuntimeAdmissionStatus.BLOCKED,
                    RuntimeAdmissionReason.RUNTIME_IDENTITY_DRIFT,
                )
        if expected_state_identities is not None:
            if type(expected_state_identities) is not tuple or any(
                type(value) is not DurableStoreIdentity
                for value in expected_state_identities
            ):
                raise TypeError("exact expected state identities required")
            if expected_state_identities != material.durable_store_identities:
                return RuntimeAdmissionResult(
                    RuntimeAdmissionStatus.BLOCKED,
                    RuntimeAdmissionReason.STATE_IDENTITY_DRIFT,
                )
        root = release_root(material.manifest.release_id)
        proof = RuntimeAdmissionProof(
            runtime_id,
            material.manifest.release_id,
            material.manifest_sha256,
            material.binding_sha256,
            root,
            root + r"\src",
            root + "\\" + material.manifest.launcher_relative_path.replace("/", "\\"),
            PRODUCTION_PYTHON,
            material.durable_store_identities,
        )
        return RuntimeAdmissionResult(
            RuntimeAdmissionStatus.ADMITTED, RuntimeAdmissionReason.ADMITTED, proof
        )
    except (TypeError, ValueError, KeyError, ArithmeticError):
        return RuntimeAdmissionResult(
            RuntimeAdmissionStatus.BLOCKED, RuntimeAdmissionReason.INVALID_MATERIAL
        )


@dataclass(frozen=True, slots=True)
class DiagnosticEvidence:
    runtime_id: str
    sequence: int
    reason: DiagnosticReason
    operation: EffectOperation | None = None

    def __post_init__(self) -> None:
        _runtime_id(self.runtime_id)
        if type(self.sequence) is not int or not 1 <= self.sequence <= 2**31 - 1:
            raise ValueError("bounded diagnostic sequence required")
        if type(self.reason) is not DiagnosticReason:
            raise ValueError("closed diagnostic reason required")
        if self.operation is not None and type(self.operation) is not EffectOperation:
            raise ValueError("closed diagnostic operation required")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": DIAGNOSTIC_SCHEMA,
            "runtime_id": self.runtime_id,
            "sequence": self.sequence,
            "reason": self.reason.value,
            "operation": None if self.operation is None else self.operation.value,
        }

    def to_json(self) -> str:
        result = _canonical(self.to_dict())
        if len(result.encode("utf-8")) > MAX_DIAGNOSTIC_BYTES:
            raise ValueError("diagnostic evidence exceeds bounded size")
        return result

    @classmethod
    def from_json(cls, text: str) -> DiagnosticEvidence:
        if type(text) is not str or len(text.encode("utf-8")) > MAX_DIAGNOSTIC_BYTES:
            raise ValueError("bounded diagnostic JSON required")
        raw = _exact_fields(
            json.loads(text),
            {"schema", "runtime_id", "sequence", "reason", "operation"},
        )
        if raw["schema"] != DIAGNOSTIC_SCHEMA:
            raise ValueError("diagnostic schema mismatch")
        operation = (
            None if raw["operation"] is None else EffectOperation(raw["operation"])
        )
        result = cls(
            raw["runtime_id"],
            raw["sequence"],
            DiagnosticReason(raw["reason"]),
            operation,
        )
        if result.to_json() != text:
            raise ValueError("noncanonical diagnostic evidence")
        return result


@dataclass(frozen=True, slots=True)
class EffectRecord:
    sequence: int
    operation: EffectOperation
    stage: EffectStage
    reason: DiagnosticReason | None = None

    def __post_init__(self) -> None:
        if (
            type(self.sequence) is not int
            or not 1 <= self.sequence <= MAX_EFFECT_RECORDS
        ):
            raise ValueError("bounded effect sequence required")
        if (
            type(self.operation) is not EffectOperation
            or type(self.stage) is not EffectStage
        ):
            raise ValueError("closed effect record required")
        if self.stage is EffectStage.DIAGNOSTIC:
            if type(self.reason) is not DiagnosticReason:
                raise ValueError("diagnostic effect reason required")
        elif self.reason is not None:
            raise ValueError("effect transition cannot contain a diagnostic reason")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": EFFECT_SCHEMA,
            "sequence": self.sequence,
            "operation": self.operation.value,
            "stage": self.stage.value,
            "reason": None if self.reason is None else self.reason.value,
        }


class DurableEffectJournal(Protocol):
    def records(self) -> tuple[EffectRecord, ...]: ...

    def append(self, record: EffectRecord) -> None: ...


def validate_effect_records(
    records: tuple[EffectRecord, ...],
) -> tuple[EffectRecord, ...]:
    """Replay the closed transition order and reject ambiguous reuse attempts."""
    if type(records) is not tuple or len(records) > MAX_EFFECT_RECORDS:
        raise ValueError("bounded effect history required")
    if not records:
        return records
    if any(type(record) is not EffectRecord for record in records):
        raise ValueError("exact effect records required")
    operation = records[0].operation
    if records[0].sequence != 1 or records[0].stage is not EffectStage.INTENT:
        raise ValueError("effect history must begin with INTENT")
    state = EffectStage.INTENT
    for expected_sequence, record in enumerate(records, 1):
        if record.sequence != expected_sequence or record.operation is not operation:
            raise ValueError("effect sequence or operation drift")
        if record is records[0]:
            continue
        if (
            state is EffectStage.INTENT
            and record.stage is EffectStage.PRE_ENTRY_REJECTED
        ):
            state = record.stage
        elif state is EffectStage.INTENT and record.stage is EffectStage.ENTRY_ADMITTED:
            state = record.stage
        elif state is EffectStage.ENTRY_ADMITTED and record.stage is EffectStage.ACK:
            state = record.stage
        elif (
            state is EffectStage.ENTRY_ADMITTED
            and record.stage is EffectStage.DIAGNOSTIC
        ):
            state = record.stage
        else:
            raise ValueError("invalid effect transition")
    if state is EffectStage.DIAGNOSTIC and records[-1].reason is None:
        raise ValueError("diagnostic reason required")
    return records


@dataclass(frozen=True, slots=True)
class EffectResult:
    status: EffectStatus
    reason: DiagnosticReason | None
    records: tuple[EffectRecord, ...]


def run_durable_effect(
    *,
    journal: DurableEffectJournal,
    operation: EffectOperation,
    pre_entry_guard: Callable[[], bool],
    external_operation: Callable[[], None],
) -> EffectResult:
    """Persist INTENT and ENTRY_ADMITTED before crossing an external seam."""
    existing = validate_effect_records(tuple(journal.records()))
    if existing:
        raise EffectConsumedError("durable effect lineage is already consumed")
    if type(operation) is not EffectOperation:
        raise ValueError("closed effect operation required")
    journal.append(EffectRecord(1, operation, EffectStage.INTENT))
    try:
        if pre_entry_guard() is not True:
            raise ValueError("pre-entry guard rejected")
    except Exception:
        journal.append(
            EffectRecord(
                2,
                operation,
                EffectStage.PRE_ENTRY_REJECTED,
            )
        )
        records = validate_effect_records(tuple(journal.records()))
        return EffectResult(
            EffectStatus.PRE_ENTRY_REJECTED,
            DiagnosticReason.PRE_EFFECT_GUARD_FAILED,
            records,
        )
    # This append is the durable external-entry boundary.  The seam is below it.
    journal.append(EffectRecord(2, operation, EffectStage.ENTRY_ADMITTED))
    try:
        external_operation()
    except Exception:
        journal.append(
            EffectRecord(
                3,
                operation,
                EffectStage.DIAGNOSTIC,
                DiagnosticReason.PROVIDER_ENTRY_FAILED,
            )
        )
        records = validate_effect_records(tuple(journal.records()))
        return EffectResult(
            EffectStatus.AMBIGUOUS,
            DiagnosticReason.PROVIDER_ENTRY_FAILED,
            records,
        )
    journal.append(EffectRecord(3, operation, EffectStage.ACK))
    records = validate_effect_records(tuple(journal.records()))
    return EffectResult(EffectStatus.ACKNOWLEDGED, None, records)


class LifecycleEvent(StrEnum):
    HOST_ENTERED = "HOST_ENTERED"
    SUPERVISOR_LOCK_ACQUIRED = "SUPERVISOR_LOCK_ACQUIRED"
    SUPERVISOR_LOOP_ENTERED = "SUPERVISOR_LOOP_ENTERED"
    SAFE_WAITING = "SAFE_WAITING"
    NORMAL_RETURN = "NORMAL_RETURN"
    CAUGHT_INTERNAL_FAILURE = "CAUGHT_INTERNAL_FAILURE"


class LifecycleStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    ABRUPT_PROCESS_DISAPPEARANCE = "ABRUPT_PROCESS_DISAPPEARANCE"
    NORMAL_RETURN = "NORMAL_RETURN"
    CAUGHT_INTERNAL_FAILURE = "CAUGHT_INTERNAL_FAILURE"


@dataclass(frozen=True, slots=True)
class LifecycleRecord:
    sequence: int
    event: LifecycleEvent

    def __post_init__(self) -> None:
        if (
            type(self.sequence) is not int
            or not 1 <= self.sequence <= MAX_LIFECYCLE_RECORDS
        ):
            raise ValueError("bounded lifecycle sequence required")
        if type(self.event) is not LifecycleEvent:
            raise ValueError("closed lifecycle event required")


def _validate_lifecycle_records(records: tuple[LifecycleRecord, ...]) -> None:
    if type(records) is not tuple or len(records) > MAX_LIFECYCLE_RECORDS:
        raise ValueError("bounded lifecycle evidence required")
    if any(type(record) is not LifecycleRecord for record in records):
        raise ValueError("exact lifecycle records required")
    state = None
    for expected, record in enumerate(records, 1):
        if record.sequence != expected:
            raise ValueError("lifecycle sequence drift")
        event = record.event
        if state is None and event is LifecycleEvent.HOST_ENTERED:
            state = event
        elif (
            state is LifecycleEvent.HOST_ENTERED
            and event is LifecycleEvent.SUPERVISOR_LOCK_ACQUIRED
        ):
            state = event
        elif (
            state is LifecycleEvent.SUPERVISOR_LOCK_ACQUIRED
            and event is LifecycleEvent.SUPERVISOR_LOOP_ENTERED
        ):
            state = event
        elif (
            state
            in {
                LifecycleEvent.SUPERVISOR_LOOP_ENTERED,
                LifecycleEvent.SAFE_WAITING,
            }
            and event is LifecycleEvent.SAFE_WAITING
        ):
            state = event
        elif state in {
            LifecycleEvent.SUPERVISOR_LOOP_ENTERED,
            LifecycleEvent.SAFE_WAITING,
        } and event in {
            LifecycleEvent.NORMAL_RETURN,
            LifecycleEvent.CAUGHT_INTERNAL_FAILURE,
        }:
            state = event
        else:
            raise ValueError("invalid lifecycle transition")
        if state in {
            LifecycleEvent.NORMAL_RETURN,
            LifecycleEvent.CAUGHT_INTERNAL_FAILURE,
        } and expected != len(records):
            raise ValueError("lifecycle terminal evidence is not final")


@dataclass(frozen=True, slots=True)
class LifecycleEvidence:
    runtime_id: str
    records: tuple[LifecycleRecord, ...]

    def __post_init__(self) -> None:
        _runtime_id(self.runtime_id)
        _validate_lifecycle_records(self.records)

    @property
    def status(self) -> LifecycleStatus:
        if not self.records:
            return LifecycleStatus.NOT_STARTED
        terminal = self.records[-1].event
        if terminal is LifecycleEvent.NORMAL_RETURN:
            return LifecycleStatus.NORMAL_RETURN
        if terminal is LifecycleEvent.CAUGHT_INTERNAL_FAILURE:
            return LifecycleStatus.CAUGHT_INTERNAL_FAILURE
        return LifecycleStatus.ABRUPT_PROCESS_DISAPPEARANCE

    def to_json(self) -> str:
        return _canonical(
            {
                "schema": LIFECYCLE_SCHEMA,
                "runtime_id": self.runtime_id,
                "records": [
                    {"sequence": record.sequence, "event": record.event.value}
                    for record in self.records
                ],
            }
        )

    @classmethod
    def from_json(cls, text: str) -> LifecycleEvidence:
        raw = _exact_fields(json.loads(text), {"schema", "runtime_id", "records"})
        if raw["schema"] != LIFECYCLE_SCHEMA or type(raw["records"]) is not list:
            raise ValueError("lifecycle schema mismatch")
        records = []
        for item in raw["records"]:
            row = _exact_fields(item, {"sequence", "event"})
            records.append(
                LifecycleRecord(row["sequence"], LifecycleEvent(row["event"]))
            )
        result = cls(raw["runtime_id"], tuple(records))
        if result.to_json() != text:
            raise ValueError("noncanonical lifecycle evidence")
        return result


class LifecycleRecorder:
    """Bounded source-level lifecycle recorder with no clock or effect access."""

    def __init__(self, runtime_id: str) -> None:
        _runtime_id(runtime_id)
        self._runtime_id = runtime_id
        self._records: tuple[LifecycleRecord, ...] = ()

    def append(self, event: LifecycleEvent) -> None:
        if type(event) is not LifecycleEvent:
            raise ValueError("closed lifecycle event required")
        if len(self._records) >= MAX_LIFECYCLE_RECORDS:
            raise ValueError("lifecycle evidence budget exhausted")
        candidate = self._records + (LifecycleRecord(len(self._records) + 1, event),)
        _validate_lifecycle_records(candidate)
        self._records = candidate

    def snapshot(self) -> LifecycleEvidence:
        return LifecycleEvidence(self._runtime_id, self._records)


@dataclass(frozen=True, slots=True)
class PinSuccessorOverlay:
    """Exact path-preserving successor overlay for frozen source consumers."""

    predecessor_pins: tuple[tuple[str, str], ...]
    successor_pins: tuple[tuple[str, str], ...]
    predecessor_sha256: str
    successor_sha256: str

    def __post_init__(self) -> None:
        _validate_pins(self.predecessor_pins)
        _validate_pins(self.successor_pins)
        if tuple(path for path, _ in self.predecessor_pins) != tuple(
            path for path, _ in self.successor_pins
        ):
            raise ValueError("successor path set must equal predecessor path set")
        if _pin_digest(self.predecessor_pins) != self.predecessor_sha256:
            raise ValueError("predecessor pin digest mismatch")
        if _pin_digest(self.successor_pins) != self.successor_sha256:
            raise ValueError("successor pin digest mismatch")


def _validate_pins(pins: tuple[tuple[str, str], ...]) -> None:
    if type(pins) is not tuple or not pins:
        raise ValueError("nonempty exact pin set required")
    paths = tuple(path for path, _ in pins)
    if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
        raise ValueError("sorted unique successor paths required")
    for path, pin in pins:
        if type(path) is not str or not path or "\\" in path:
            raise ValueError("canonical successor path required")
        _digest(pin, name="source pin", length=40)


def _pin_digest(pins: tuple[tuple[str, str], ...]) -> str:
    return hashlib.sha256(_canonical(pins).encode("utf-8")).hexdigest()


def build_pin_successor_overlay(
    predecessor_pins: tuple[tuple[str, str], ...],
    successor_pins: tuple[tuple[str, str], ...],
) -> PinSuccessorOverlay:
    return PinSuccessorOverlay(
        predecessor_pins,
        successor_pins,
        _pin_digest(predecessor_pins),
        _pin_digest(successor_pins),
    )


def resolve_pin_successor(
    path: str,
    predecessor_pins: tuple[tuple[str, str], ...],
    overlay: PinSuccessorOverlay | None,
    successor_pins: tuple[tuple[str, str], ...] | None,
) -> str:
    """Resolve an exact successor, or restore the predecessor when removed."""
    _validate_pins(predecessor_pins)
    predecessor = dict(predecessor_pins)
    if path not in predecessor:
        raise ValueError("path is outside predecessor pin set")
    if overlay is None or successor_pins is None:
        return predecessor[path]
    if overlay.predecessor_pins != predecessor_pins:
        raise ValueError("wrong predecessor pin set")
    if successor_pins != overlay.successor_pins:
        raise ValueError("wrong successor pin set or blob")
    return dict(successor_pins)[path]


class ProductionOperatorState(StrEnum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"


def production_state_after_boot_or_login(
    _previous: ProductionOperatorState,
) -> ProductionOperatorState:
    """Production reboot contract: boot/login never resumes trading."""
    if type(_previous) is not ProductionOperatorState:
        raise ValueError("closed production operator state required")
    return ProductionOperatorState.STOPPED


def production_manual_start(
    state: ProductionOperatorState,
    admission: RuntimeAdmissionResult,
) -> ProductionOperatorState:
    """Only an explicit fresh admitted start may transition STOPPED to RUNNING."""
    if (
        type(state) is not ProductionOperatorState
        or type(admission) is not RuntimeAdmissionResult
    ):
        raise ValueError("explicit production start inputs required")
    if state is not ProductionOperatorState.STOPPED:
        raise ValueError("manual start requires stopped production state")
    if admission.status is not RuntimeAdmissionStatus.ADMITTED:
        raise ValueError("manual start requires fresh runtime admission")
    return ProductionOperatorState.RUNNING
