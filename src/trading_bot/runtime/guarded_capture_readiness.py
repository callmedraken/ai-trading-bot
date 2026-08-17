"""Canonical evidence for the guarded capture-readiness dry-run milestone."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    AdjustmentType,
    CalendarDescriptor,
    ProviderDescriptor,
    Timeframe,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.runtime.scheduled_readiness import (
    MAX_SCHEDULED_ARTIFACT_BYTES,
    ArtifactEvidence,
    CapturePolicy,
    HeadRecordEvidence,
    MarketSessionHours,
    MarketSessionHoursKind,
    MarketSessionHoursSchedule,
    ScheduledReadinessClassification,
    ScheduledReadinessCode,
    TerminalCheckpointEvidence,
    derive_scheduled_capture_attempt_id,
)

MARKET_SESSION_HOURS_SCHEDULE_SCHEMA_VERSION = 1
CAPTURE_POLICY_ARTIFACT_SCHEMA_VERSION = 1
SCHEDULED_CAPTURE_READINESS_DECISION_SCHEMA_VERSION = 1
SCHEDULED_CAPTURE_READINESS_DECISION_MATERIAL_VERSION = (
    "scheduled-capture-readiness-decision-v1"
)
SCHEDULED_CAPTURE_READINESS_DECISION_NAMESPACE = UUID(
    "8dc35263-331b-55c9-946d-1f3747fd43b5"
)
MAX_GUARDED_CAPTURE_READINESS_ARTIFACT_BYTES = MAX_SCHEDULED_ARTIFACT_BYTES

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_POLICY = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_MAX_INTEGER = (1 << 63) - 1
_MAX_ITEMS = 100


class GuardedCaptureReadinessArtifactError(ValueError):
    """Raised when a dry-run input or decision artifact is invalid."""


class NextEligibleAction(StrEnum):
    NONE = "NONE"
    WAIT = "WAIT"
    CAPTURE_ATTEMPT_ALLOWED = "CAPTURE_ATTEMPT_ALLOWED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True, slots=True)
class ScheduledCaptureReadinessDecision:
    schema_version: int
    decision_id: UUID
    scheduled_session_id: UUID
    scheduled_launch_id: UUID
    authority_epoch_id: UUID
    lease_start: ArtifactEvidence
    head_record: HeadRecordEvidence
    terminal_checkpoint: TerminalCheckpointEvidence
    market_hours_schedule: ArtifactEvidence
    capture_policy: ArtifactEvidence
    capture_attempts: tuple[ArtifactEvidence, ...]
    snapshot_selection: ArtifactEvidence | None
    observed_at: datetime
    readiness_classification: ScheduledReadinessClassification
    diagnostics: tuple[ScheduledReadinessCode, ...]
    provider_invocation_permitted: bool
    next_eligible_action: NextEligibleAction
    capture_attempt_ordinal: int | None
    capture_attempt_id: UUID | None
    runner_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEDULED_CAPTURE_READINESS_DECISION_SCHEMA_VERSION:
            raise GuardedCaptureReadinessArtifactError(
                "decision schema_version must be 1"
            )
        for value, label in (
            (self.decision_id, "decision_id"),
            (self.scheduled_session_id, "scheduled_session_id"),
            (self.scheduled_launch_id, "scheduled_launch_id"),
            (self.authority_epoch_id, "authority_epoch_id"),
        ):
            _require_uuid(value, label)
        if any(
            type(value) is not ArtifactEvidence
            for value in (
                self.lease_start,
                self.market_hours_schedule,
                self.capture_policy,
            )
        ):
            raise GuardedCaptureReadinessArtifactError(
                "decision artifact evidence is invalid"
            )
        if (
            type(self.head_record) is not HeadRecordEvidence
            or type(self.terminal_checkpoint) is not TerminalCheckpointEvidence
            or self.head_record.authority_epoch_id != self.authority_epoch_id
            or self.head_record.generation != self.terminal_checkpoint.sequence
        ):
            raise GuardedCaptureReadinessArtifactError(
                "decision authority evidence does not reconcile"
            )
        attempts = tuple(self.capture_attempts)
        if len(attempts) > _MAX_ITEMS or any(
            type(value) is not ArtifactEvidence for value in attempts
        ):
            raise GuardedCaptureReadinessArtifactError(
                "decision capture-attempt evidence is invalid"
            )
        if (
            self.snapshot_selection is not None
            and type(self.snapshot_selection) is not ArtifactEvidence
        ):
            raise GuardedCaptureReadinessArtifactError(
                "decision selection evidence is invalid"
            )
        observed = _utc(self.observed_at, "observed_at")
        if type(self.readiness_classification) is not ScheduledReadinessClassification:
            raise GuardedCaptureReadinessArtifactError(
                "decision readiness classification is invalid"
            )
        diagnostics = tuple(self.diagnostics)
        if (
            len(set(diagnostics)) != len(diagnostics)
            or any(type(item) is not ScheduledReadinessCode for item in diagnostics)
            or diagnostics
            != tuple(item for item in ScheduledReadinessCode if item in diagnostics)
        ):
            raise GuardedCaptureReadinessArtifactError(
                "decision diagnostics are not canonical"
            )
        if (
            type(self.provider_invocation_permitted) is not bool
            or type(self.next_eligible_action) is not NextEligibleAction
        ):
            raise GuardedCaptureReadinessArtifactError(
                "decision action evidence is invalid"
            )
        has_attempt = (
            self.capture_attempt_ordinal is not None
            and self.capture_attempt_id is not None
        )
        if (self.capture_attempt_ordinal is None) != (self.capture_attempt_id is None):
            raise GuardedCaptureReadinessArtifactError(
                "decision proposed attempt evidence must be all-or-none"
            )
        if has_attempt:
            _nonnegative(self.capture_attempt_ordinal, "capture_attempt_ordinal")
            _require_uuid(self.capture_attempt_id, "capture_attempt_id")
        permitted = (
            self.readiness_classification is ScheduledReadinessClassification.READY
            and self.next_eligible_action is NextEligibleAction.CAPTURE_ATTEMPT_ALLOWED
            and has_attempt
        )
        if self.provider_invocation_permitted != permitted:
            raise GuardedCaptureReadinessArtifactError(
                "provider permission does not match the dry-run decision"
            )
        expected_action = {
            ScheduledReadinessClassification.READY: (
                NextEligibleAction.CAPTURE_ATTEMPT_ALLOWED
            ),
            ScheduledReadinessClassification.NOT_READY: NextEligibleAction.WAIT,
            ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED: (
                NextEligibleAction.MANUAL_REVIEW
            ),
        }.get(self.readiness_classification, NextEligibleAction.NONE)
        if self.next_eligible_action is not expected_action:
            raise GuardedCaptureReadinessArtifactError(
                "next eligible action does not match readiness"
            )
        _policy(self.runner_policy_version, "runner_policy_version")
        expected_id = derive_scheduled_capture_readiness_decision_id(
            scheduled_session_id=self.scheduled_session_id,
            scheduled_launch_id=self.scheduled_launch_id,
            authority_epoch_id=self.authority_epoch_id,
            lease_start=self.lease_start,
            head_record=self.head_record,
            terminal_checkpoint=self.terminal_checkpoint,
            market_hours_schedule=self.market_hours_schedule,
            capture_policy=self.capture_policy,
            capture_attempts=attempts,
            snapshot_selection=self.snapshot_selection,
            observed_at=observed,
            readiness_classification=self.readiness_classification,
            diagnostics=diagnostics,
            provider_invocation_permitted=self.provider_invocation_permitted,
            next_eligible_action=self.next_eligible_action,
            capture_attempt_ordinal=self.capture_attempt_ordinal,
            capture_attempt_id=self.capture_attempt_id,
            runner_policy_version=self.runner_policy_version,
        )
        if self.decision_id != expected_id:
            raise GuardedCaptureReadinessArtifactError(
                "decision_id does not match canonical material"
            )
        object.__setattr__(self, "capture_attempts", attempts)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "observed_at", observed)


def derive_scheduled_capture_readiness_decision_id(
    *,
    scheduled_session_id: UUID,
    scheduled_launch_id: UUID,
    authority_epoch_id: UUID,
    lease_start: ArtifactEvidence,
    head_record: HeadRecordEvidence,
    terminal_checkpoint: TerminalCheckpointEvidence,
    market_hours_schedule: ArtifactEvidence,
    capture_policy: ArtifactEvidence,
    capture_attempts: tuple[ArtifactEvidence, ...],
    snapshot_selection: ArtifactEvidence | None,
    observed_at: datetime,
    readiness_classification: ScheduledReadinessClassification,
    diagnostics: tuple[ScheduledReadinessCode, ...],
    provider_invocation_permitted: bool,
    next_eligible_action: NextEligibleAction,
    capture_attempt_ordinal: int | None,
    capture_attempt_id: UUID | None,
    runner_policy_version: str,
) -> UUID:
    for value, label in (
        (scheduled_session_id, "scheduled_session_id"),
        (scheduled_launch_id, "scheduled_launch_id"),
        (authority_epoch_id, "authority_epoch_id"),
    ):
        _require_uuid(value, label)
    if any(
        type(value) is not ArtifactEvidence
        for value in (lease_start, market_hours_schedule, capture_policy)
    ):
        raise GuardedCaptureReadinessArtifactError("decision evidence is invalid")
    if (
        type(head_record) is not HeadRecordEvidence
        or type(terminal_checkpoint) is not TerminalCheckpointEvidence
    ):
        raise GuardedCaptureReadinessArtifactError(
            "decision authority material is invalid"
        )
    attempts = tuple(capture_attempts)
    if len(attempts) > _MAX_ITEMS or any(
        type(item) is not ArtifactEvidence for item in attempts
    ):
        raise GuardedCaptureReadinessArtifactError(
            "decision attempt material is invalid"
        )
    if (
        snapshot_selection is not None
        and type(snapshot_selection) is not ArtifactEvidence
    ):
        raise GuardedCaptureReadinessArtifactError(
            "decision selection material is invalid"
        )
    observed = _utc(observed_at, "observed_at")
    if type(readiness_classification) is not ScheduledReadinessClassification:
        raise GuardedCaptureReadinessArtifactError("decision classification is invalid")
    ordered_diagnostics = tuple(diagnostics)
    if any(type(item) is not ScheduledReadinessCode for item in ordered_diagnostics):
        raise GuardedCaptureReadinessArtifactError(
            "decision diagnostic material is invalid"
        )
    if (
        type(provider_invocation_permitted) is not bool
        or type(next_eligible_action) is not NextEligibleAction
    ):
        raise GuardedCaptureReadinessArtifactError(
            "decision action material is invalid"
        )
    if (capture_attempt_ordinal is None) != (capture_attempt_id is None):
        raise GuardedCaptureReadinessArtifactError(
            "decision attempt material must be all-or-none"
        )
    if capture_attempt_ordinal is not None:
        _nonnegative(capture_attempt_ordinal, "capture_attempt_ordinal")
        _require_uuid(capture_attempt_id, "capture_attempt_id")
    parts = [
        SCHEDULED_CAPTURE_READINESS_DECISION_MATERIAL_VERSION,
        str(scheduled_session_id),
        str(scheduled_launch_id),
        str(authority_epoch_id),
        *_evidence_parts(lease_start),
        str(head_record.authority_epoch_id),
        *_evidence_parts(head_record.record),
        str(head_record.generation),
        *_evidence_parts(terminal_checkpoint.checkpoint),
        str(terminal_checkpoint.sequence),
        canonical_timestamp(terminal_checkpoint.as_of),
        *_evidence_parts(market_hours_schedule),
        *_evidence_parts(capture_policy),
        str(len(attempts)),
    ]
    for ordinal, attempt in enumerate(attempts):
        parts.extend((str(ordinal), *_evidence_parts(attempt)))
    parts.extend(
        (
            "NONE" if snapshot_selection is None else "PRESENT",
            *(
                ()
                if snapshot_selection is None
                else _evidence_parts(snapshot_selection)
            ),
            canonical_timestamp(observed),
            readiness_classification.value,
            str(len(ordered_diagnostics)),
            *(item.value for item in ordered_diagnostics),
            "true" if provider_invocation_permitted else "false",
            next_eligible_action.value,
            (
                "NONE"
                if capture_attempt_ordinal is None
                else str(capture_attempt_ordinal)
            ),
            "NONE" if capture_attempt_id is None else str(capture_attempt_id),
            _policy(runner_policy_version, "runner_policy_version"),
        )
    )
    return uuid5(
        SCHEDULED_CAPTURE_READINESS_DECISION_NAMESPACE,
        _framed(tuple(parts)),
    )


def create_scheduled_capture_readiness_decision(
    *,
    scheduled_session_id: UUID,
    scheduled_launch_id: UUID,
    authority_epoch_id: UUID,
    lease_start: ArtifactEvidence,
    head_record: HeadRecordEvidence,
    terminal_checkpoint: TerminalCheckpointEvidence,
    market_hours_schedule: ArtifactEvidence,
    capture_policy: ArtifactEvidence,
    capture_attempts: tuple[ArtifactEvidence, ...],
    snapshot_selection: ArtifactEvidence | None,
    observed_at: datetime,
    readiness_classification: ScheduledReadinessClassification,
    diagnostics: tuple[ScheduledReadinessCode, ...],
    provider_invocation_permitted: bool,
    next_eligible_action: NextEligibleAction,
    capture_attempt_ordinal: int | None,
    capture_attempt_id: UUID | None,
    runner_policy_version: str,
) -> ScheduledCaptureReadinessDecision:
    decision_id = derive_scheduled_capture_readiness_decision_id(
        scheduled_session_id=scheduled_session_id,
        scheduled_launch_id=scheduled_launch_id,
        authority_epoch_id=authority_epoch_id,
        lease_start=lease_start,
        head_record=head_record,
        terminal_checkpoint=terminal_checkpoint,
        market_hours_schedule=market_hours_schedule,
        capture_policy=capture_policy,
        capture_attempts=capture_attempts,
        snapshot_selection=snapshot_selection,
        observed_at=observed_at,
        readiness_classification=readiness_classification,
        diagnostics=diagnostics,
        provider_invocation_permitted=provider_invocation_permitted,
        next_eligible_action=next_eligible_action,
        capture_attempt_ordinal=capture_attempt_ordinal,
        capture_attempt_id=capture_attempt_id,
        runner_policy_version=runner_policy_version,
    )
    return ScheduledCaptureReadinessDecision(
        SCHEDULED_CAPTURE_READINESS_DECISION_SCHEMA_VERSION,
        decision_id,
        scheduled_session_id,
        scheduled_launch_id,
        authority_epoch_id,
        lease_start,
        head_record,
        terminal_checkpoint,
        market_hours_schedule,
        capture_policy,
        capture_attempts,
        snapshot_selection,
        observed_at,
        readiness_classification,
        diagnostics,
        provider_invocation_permitted,
        next_eligible_action,
        capture_attempt_ordinal,
        capture_attempt_id,
        runner_policy_version,
    )


def proposed_capture_attempt_id(
    scheduled_session_id: UUID,
    capture_attempt_ordinal: int,
    policy: CapturePolicy,
) -> UUID:
    """Derive, but never allocate, the next capture-attempt identity."""
    if type(policy) is not CapturePolicy:
        raise TypeError("policy must be CapturePolicy")
    return derive_scheduled_capture_attempt_id(
        scheduled_session_id,
        capture_attempt_ordinal,
        policy.symbols,
        policy.timeframe,
        policy.adjustment,
        policy.provider,
        policy.feed,
        policy.currency,
        policy.policy_version,
        policy.configuration_evidence,
    )


def serialize_market_session_hours_schedule(
    schedule: MarketSessionHoursSchedule,
) -> bytes:
    if type(schedule) is not MarketSessionHoursSchedule:
        raise TypeError("schedule must be MarketSessionHoursSchedule")
    return _json_bytes(_schedule_tree(schedule))


def parse_market_session_hours_schedule(
    payload: bytes,
) -> MarketSessionHoursSchedule:
    root = _object(
        _load_json(payload),
        {
            "schema_version",
            "calendar",
            "schedule_version",
            "coverage_start",
            "coverage_end",
            "entries",
            "exceptional_closures",
            "authority_evidence",
        },
        "schedule",
    )
    if _integer(root["schema_version"], "schema_version") != 1:
        raise GuardedCaptureReadinessArtifactError("schedule schema_version must be 1")
    calendar = _calendar(root["calendar"])
    entries = tuple(
        _hours(item, index)
        for index, item in enumerate(_array(root["entries"], "entries"))
    )
    closures = tuple(
        _date(item, f"exceptional_closures[{index}]")
        for index, item in enumerate(
            _array(root["exceptional_closures"], "exceptional_closures")
        )
    )
    schedule = MarketSessionHoursSchedule(
        calendar,
        _string(root["schedule_version"], "schedule_version"),
        _date(root["coverage_start"], "coverage_start"),
        _date(root["coverage_end"], "coverage_end"),
        entries,
        closures,
        _artifact(root["authority_evidence"], "authority_evidence"),
    )
    if serialize_market_session_hours_schedule(schedule) != payload:
        raise GuardedCaptureReadinessArtifactError("schedule bytes are not canonical")
    return schedule


def serialize_capture_policy_artifact(policy: CapturePolicy) -> bytes:
    if type(policy) is not CapturePolicy:
        raise TypeError("policy must be CapturePolicy")
    return _json_bytes(_policy_tree(policy))


def parse_capture_policy_artifact(payload: bytes) -> CapturePolicy:
    root = _object(
        _load_json(payload),
        {
            "schema_version",
            "policy_version",
            "publication_delay_seconds",
            "capture_cutoff_guard_seconds",
            "maximum_attempts",
            "fixed_backoffs_seconds",
            "maximum_clock_skew_seconds",
            "maximum_acceptable_lateness_seconds",
            "symbols",
            "timeframe",
            "adjustment",
            "provider",
            "feed",
            "currency",
            "configuration_evidence",
        },
        "capture_policy",
    )
    if _integer(root["schema_version"], "schema_version") != 1:
        raise GuardedCaptureReadinessArtifactError(
            "capture-policy schema_version must be 1"
        )
    policy = CapturePolicy(
        _string(root["policy_version"], "policy_version"),
        _nonnegative(root["publication_delay_seconds"], "publication_delay_seconds"),
        _nonnegative(
            root["capture_cutoff_guard_seconds"],
            "capture_cutoff_guard_seconds",
        ),
        _integer(root["maximum_attempts"], "maximum_attempts"),
        tuple(
            _nonnegative(item, f"fixed_backoffs_seconds[{index}]")
            for index, item in enumerate(
                _array(root["fixed_backoffs_seconds"], "fixed_backoffs_seconds")
            )
        ),
        _nonnegative(
            root["maximum_clock_skew_seconds"],
            "maximum_clock_skew_seconds",
        ),
        _nonnegative(
            root["maximum_acceptable_lateness_seconds"],
            "maximum_acceptable_lateness_seconds",
        ),
        tuple(
            Symbol(_string(item, f"symbols[{index}]"))
            for index, item in enumerate(_array(root["symbols"], "symbols"))
        ),
        _enum(Timeframe, root["timeframe"], "timeframe"),
        _enum(AdjustmentType, root["adjustment"], "adjustment"),
        _provider(root["provider"]),
        _string(root["feed"], "feed"),
        _string(root["currency"], "currency"),
        _artifact(root["configuration_evidence"], "configuration_evidence"),
    )
    if serialize_capture_policy_artifact(policy) != payload:
        raise GuardedCaptureReadinessArtifactError(
            "capture-policy bytes are not canonical"
        )
    return policy


def serialize_scheduled_capture_readiness_decision(
    decision: ScheduledCaptureReadinessDecision,
) -> bytes:
    if type(decision) is not ScheduledCaptureReadinessDecision:
        raise TypeError("decision must be ScheduledCaptureReadinessDecision")
    return _json_bytes(_decision_tree(decision))


def parse_scheduled_capture_readiness_decision(
    payload: bytes,
) -> ScheduledCaptureReadinessDecision:
    root = _object(
        _load_json(payload),
        {
            "schema_version",
            "decision_id",
            "scheduled_session_id",
            "scheduled_launch_id",
            "authority_epoch_id",
            "lease_start",
            "head_record",
            "terminal_checkpoint",
            "market_hours_schedule",
            "capture_policy",
            "capture_attempts",
            "snapshot_selection",
            "observed_at",
            "readiness_classification",
            "diagnostics",
            "provider_invocation_permitted",
            "next_eligible_action",
            "capture_attempt_ordinal",
            "capture_attempt_id",
            "runner_policy_version",
        },
        "decision",
    )
    head = _object(
        root["head_record"],
        {"authority_epoch_id", "record", "generation"},
        "head_record",
    )
    terminal = _object(
        root["terminal_checkpoint"],
        {"checkpoint", "sequence", "as_of"},
        "terminal_checkpoint",
    )
    selection_value = root["snapshot_selection"]
    ordinal_value = root["capture_attempt_ordinal"]
    attempt_id_value = root["capture_attempt_id"]
    decision = ScheduledCaptureReadinessDecision(
        _integer(root["schema_version"], "schema_version"),
        _uuid(root["decision_id"], "decision_id"),
        _uuid(root["scheduled_session_id"], "scheduled_session_id"),
        _uuid(root["scheduled_launch_id"], "scheduled_launch_id"),
        _uuid(root["authority_epoch_id"], "authority_epoch_id"),
        _artifact(root["lease_start"], "lease_start"),
        HeadRecordEvidence(
            _uuid(head["authority_epoch_id"], "head_record.authority_epoch_id"),
            _artifact(head["record"], "head_record.record"),
            _nonnegative(head["generation"], "head_record.generation"),
        ),
        TerminalCheckpointEvidence(
            _artifact(terminal["checkpoint"], "terminal_checkpoint.checkpoint"),
            _nonnegative(terminal["sequence"], "terminal_checkpoint.sequence"),
            _timestamp(terminal["as_of"], "terminal_checkpoint.as_of"),
        ),
        _artifact(root["market_hours_schedule"], "market_hours_schedule"),
        _artifact(root["capture_policy"], "capture_policy"),
        tuple(
            _artifact(item, f"capture_attempts[{index}]")
            for index, item in enumerate(
                _array(root["capture_attempts"], "capture_attempts")
            )
        ),
        (
            None
            if selection_value is None
            else _artifact(selection_value, "snapshot_selection")
        ),
        _timestamp(root["observed_at"], "observed_at"),
        _enum(
            ScheduledReadinessClassification,
            root["readiness_classification"],
            "readiness_classification",
        ),
        tuple(
            _enum(ScheduledReadinessCode, item, f"diagnostics[{index}]")
            for index, item in enumerate(_array(root["diagnostics"], "diagnostics"))
        ),
        _boolean(
            root["provider_invocation_permitted"],
            "provider_invocation_permitted",
        ),
        _enum(NextEligibleAction, root["next_eligible_action"], "next_eligible_action"),
        (
            None
            if ordinal_value is None
            else _nonnegative(ordinal_value, "capture_attempt_ordinal")
        ),
        (
            None
            if attempt_id_value is None
            else _uuid(attempt_id_value, "capture_attempt_id")
        ),
        _string(root["runner_policy_version"], "runner_policy_version"),
    )
    if serialize_scheduled_capture_readiness_decision(decision) != payload:
        raise GuardedCaptureReadinessArtifactError("decision bytes are not canonical")
    return decision


def _schedule_tree(schedule: MarketSessionHoursSchedule) -> dict[str, object]:
    return {
        "schema_version": MARKET_SESSION_HOURS_SCHEDULE_SCHEMA_VERSION,
        "calendar": {
            "calendar_id": schedule.calendar.calendar_id,
            "version": schedule.calendar.version,
            "exchange_timezone": schedule.calendar.exchange_timezone,
        },
        "schedule_version": schedule.schedule_version,
        "coverage_start": schedule.coverage_start.isoformat(),
        "coverage_end": schedule.coverage_end.isoformat(),
        "entries": [
            {
                "session": item.session.session_date.isoformat(),
                "opens_at": canonical_timestamp(item.opens_at),
                "closes_at": canonical_timestamp(item.closes_at),
                "kind": item.kind.value,
            }
            for item in schedule.entries
        ],
        "exceptional_closures": [
            item.isoformat() for item in schedule.exceptional_closures
        ],
        "authority_evidence": _artifact_tree(schedule.authority_evidence),
    }


def _policy_tree(policy: CapturePolicy) -> dict[str, object]:
    return {
        "schema_version": CAPTURE_POLICY_ARTIFACT_SCHEMA_VERSION,
        "policy_version": policy.policy_version,
        "publication_delay_seconds": policy.publication_delay_seconds,
        "capture_cutoff_guard_seconds": policy.capture_cutoff_guard_seconds,
        "maximum_attempts": policy.maximum_attempts,
        "fixed_backoffs_seconds": list(policy.fixed_backoffs_seconds),
        "maximum_clock_skew_seconds": policy.maximum_clock_skew_seconds,
        "maximum_acceptable_lateness_seconds": (
            policy.maximum_acceptable_lateness_seconds
        ),
        "symbols": [str(item) for item in policy.symbols],
        "timeframe": policy.timeframe.value,
        "adjustment": policy.adjustment.value,
        "provider": {
            "provider_id": policy.provider.provider_id,
            "adapter_version": policy.provider.adapter_version,
            "operation": policy.provider.operation,
            "feed": policy.provider.feed,
        },
        "feed": policy.feed,
        "currency": policy.currency,
        "configuration_evidence": _artifact_tree(policy.configuration_evidence),
    }


def _decision_tree(
    decision: ScheduledCaptureReadinessDecision,
) -> dict[str, object]:
    return {
        "schema_version": decision.schema_version,
        "decision_id": str(decision.decision_id),
        "scheduled_session_id": str(decision.scheduled_session_id),
        "scheduled_launch_id": str(decision.scheduled_launch_id),
        "authority_epoch_id": str(decision.authority_epoch_id),
        "lease_start": _artifact_tree(decision.lease_start),
        "head_record": {
            "authority_epoch_id": str(decision.head_record.authority_epoch_id),
            "record": _artifact_tree(decision.head_record.record),
            "generation": decision.head_record.generation,
        },
        "terminal_checkpoint": {
            "checkpoint": _artifact_tree(decision.terminal_checkpoint.checkpoint),
            "sequence": decision.terminal_checkpoint.sequence,
            "as_of": canonical_timestamp(decision.terminal_checkpoint.as_of),
        },
        "market_hours_schedule": _artifact_tree(decision.market_hours_schedule),
        "capture_policy": _artifact_tree(decision.capture_policy),
        "capture_attempts": [
            _artifact_tree(item) for item in decision.capture_attempts
        ],
        "snapshot_selection": (
            None
            if decision.snapshot_selection is None
            else _artifact_tree(decision.snapshot_selection)
        ),
        "observed_at": canonical_timestamp(decision.observed_at),
        "readiness_classification": decision.readiness_classification.value,
        "diagnostics": [item.value for item in decision.diagnostics],
        "provider_invocation_permitted": (decision.provider_invocation_permitted),
        "next_eligible_action": decision.next_eligible_action.value,
        "capture_attempt_ordinal": decision.capture_attempt_ordinal,
        "capture_attempt_id": (
            None
            if decision.capture_attempt_id is None
            else str(decision.capture_attempt_id)
        ),
        "runner_policy_version": decision.runner_policy_version,
    }


def _hours(value: object, index: int) -> MarketSessionHours:
    root = _object(
        value,
        {"session", "opens_at", "closes_at", "kind"},
        f"entries[{index}]",
    )
    return MarketSessionHours(
        TradingSession(_date(root["session"], f"entries[{index}].session")),
        _timestamp(root["opens_at"], f"entries[{index}].opens_at"),
        _timestamp(root["closes_at"], f"entries[{index}].closes_at"),
        _enum(MarketSessionHoursKind, root["kind"], f"entries[{index}].kind"),
    )


def _calendar(value: object) -> CalendarDescriptor:
    root = _object(
        value,
        {"calendar_id", "version", "exchange_timezone"},
        "calendar",
    )
    calendar = CalendarDescriptor(
        _string(root["calendar_id"], "calendar.calendar_id"),
        _string(root["version"], "calendar.version"),
        _string(root["exchange_timezone"], "calendar.exchange_timezone"),
    )
    if calendar != XNYS_CALENDAR_DESCRIPTOR:
        raise GuardedCaptureReadinessArtifactError(
            "calendar must be the supported XNYS descriptor"
        )
    return calendar


def _provider(value: object) -> ProviderDescriptor:
    root = _object(
        value,
        {"provider_id", "adapter_version", "operation", "feed"},
        "provider",
    )
    return ProviderDescriptor(
        _string(root["provider_id"], "provider.provider_id"),
        _integer(root["adapter_version"], "provider.adapter_version"),
        _string(root["operation"], "provider.operation"),
        _string(root["feed"], "provider.feed"),
    )


def _artifact_tree(value: ArtifactEvidence) -> dict[str, object]:
    return {
        "artifact_id": str(value.artifact_id),
        "sha256": value.sha256,
        "byte_length": value.byte_length,
    }


def _artifact(value: object, label: str) -> ArtifactEvidence:
    root = _object(value, {"artifact_id", "sha256", "byte_length"}, label)
    return ArtifactEvidence(
        _uuid(root["artifact_id"], f"{label}.artifact_id"),
        _sha(root["sha256"], f"{label}.sha256"),
        _nonnegative(root["byte_length"], f"{label}.byte_length"),
    )


def _evidence_parts(value: ArtifactEvidence) -> tuple[str, ...]:
    return str(value.artifact_id), value.sha256, str(value.byte_length)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _load_json(payload: bytes) -> object:
    if type(payload) is not bytes:
        raise TypeError("artifact payload must be bytes")
    if len(payload) > MAX_GUARDED_CAPTURE_READINESS_ARTIFACT_BYTES:
        raise GuardedCaptureReadinessArtifactError("artifact exceeds its byte bound")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise GuardedCaptureReadinessArtifactError("UTF-8 BOM is not permitted")
    try:
        return json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except GuardedCaptureReadinessArtifactError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardedCaptureReadinessArtifactError(
            "artifact is not strict UTF-8 JSON"
        ) from exc


def _duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GuardedCaptureReadinessArtifactError(
                f"duplicate object member: {key}"
            )
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise GuardedCaptureReadinessArtifactError("floats are not permitted")


def _reject_constant(_: str) -> None:
    raise GuardedCaptureReadinessArtifactError("constants are not permitted")


def _object(
    value: object,
    fields: set[str],
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise GuardedCaptureReadinessArtifactError(f"{label} members are not exact")
    return value


def _array(value: object, label: str) -> list[object]:
    if type(value) is not list or len(value) > _MAX_ITEMS:
        raise GuardedCaptureReadinessArtifactError(f"{label} is not a bounded array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value or len(value) > 256:
        raise GuardedCaptureReadinessArtifactError(
            f"{label} must be bounded nonempty text"
        )
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be a bool")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int or not -_MAX_INTEGER <= value <= _MAX_INTEGER:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be a bounded integer")
    return value


def _nonnegative(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed < 0:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be nonnegative")
    return parsed


def _require_uuid(value: object, label: str) -> UUID:
    if type(value) is not UUID:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be a UUID")
    return value


def _uuid(value: object, label: str) -> UUID:
    text = _string(value, label)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be a UUID") from exc
    if str(parsed) != text:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be a canonical UUID")
    return parsed


def _sha(value: object, label: str) -> str:
    text = _string(value, label)
    if _SHA256.fullmatch(text) is None:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be lowercase SHA-256")
    return text


def _timestamp(value: object, label: str) -> datetime:
    text = _string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GuardedCaptureReadinessArtifactError(
            f"{label} must be a timestamp"
        ) from exc
    normalized = _utc(parsed, label)
    if canonical_timestamp(normalized) != text:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be canonical UTC")
    return normalized


def _utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise GuardedCaptureReadinessArtifactError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise GuardedCaptureReadinessArtifactError(
            f"{label} must be an ISO date"
        ) from exc
    if parsed.isoformat() != text:
        raise GuardedCaptureReadinessArtifactError(
            f"{label} must be a canonical ISO date"
        )
    return parsed


def _enum(enum_type, value: object, label: str):  # type: ignore[no-untyped-def]
    text = _string(value, label)
    try:
        return enum_type(text)
    except ValueError as exc:
        raise GuardedCaptureReadinessArtifactError(
            f"{label} has an unsupported value"
        ) from exc


def _policy(value: object, label: str) -> str:
    if type(value) is not str or _POLICY.fullmatch(value) is None:
        raise GuardedCaptureReadinessArtifactError(
            f"{label} must be a canonical policy identifier"
        )
    return value


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)
