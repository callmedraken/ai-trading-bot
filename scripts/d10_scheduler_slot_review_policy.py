"""Pure S2C1A review of supplied sanitized scheduler history.

READY proves only compliance with this fixed supplied-history contract. It does
not prove collector truth, continuous channel enablement, accepted durable bot
wakes, Paper-v2 correctness, D10 acceptance, or broker-paper readiness. Those
remain separate collector, evidence, and operator-review boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

from scripts import d10_end_of_soak_review as internal_review_policy
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as scheduler_contract,
)

SCHEMA: Final = "d10-scheduler-slot-review/v1"
DEPLOYMENT_ID: Final = internal_review_policy.DEPLOYMENT_ID
SOAK_ID: Final = internal_review_policy.SOAK_ID
ACTIVATION_UTC: Final = internal_review_policy.ACTIVATION_UTC
END_UTC: Final = internal_review_policy.END_UTC
TASK_PATH: Final = r"\AITradingBot-PD4-UnattendedPaper-v1"
SLOT_COUNT: Final = 7


class D10SchedulerHistoryEventKind(StrEnum):
    SCHEDULED_TRIGGER = "SCHEDULED_TRIGGER"
    MANUAL_TRIGGER = "MANUAL_TRIGGER"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"


EVENT_IDS: Final = {
    D10SchedulerHistoryEventKind.SCHEDULED_TRIGGER: 107,
    D10SchedulerHistoryEventKind.MANUAL_TRIGGER: 110,
    D10SchedulerHistoryEventKind.TASK_STARTED: 100,
    D10SchedulerHistoryEventKind.TASK_COMPLETED: 102,
}


@dataclass(frozen=True, slots=True)
class D10SchedulerHistoryEvent:
    kind: D10SchedulerHistoryEventKind
    event_id: int
    record_id: int
    observed_at_utc: datetime
    task_name: str
    instance_id: str


@dataclass(frozen=True, slots=True)
class D10SchedulerHistoryObservation:
    deployment_id: str
    soak_id: str
    activation_utc: datetime
    end_utc: datetime
    collected_at_utc: datetime
    channel_enabled: bool
    oldest_retained_event_utc: datetime
    events: tuple[D10SchedulerHistoryEvent, ...]


def _blocked(reason: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "reason": reason,
        "category": "SCHEDULER_SLOT_COVERAGE",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }


def _utc(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is UTC


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _instance_id(value: object) -> bool:
    # One representation only: lowercase, unbraced 8-4-4-4-12 UUID text.
    return (
        type(value) is str
        and len(value) == 36
        and all(value[index] == "-" for index in (8, 13, 18, 23))
        and all(
            character in "0123456789abcdef"
            for index, character in enumerate(value)
            if index not in (8, 13, 18, 23)
        )
    )


def expected_slots_utc() -> tuple[datetime, ...]:
    """Derive slots only from the accepted fixed-activation scheduler spec.

    Revalidate the complete frozen deployment spec before using its daily local
    wall-clock boundary. No caller-supplied slot set or host state is consulted.
    Invalid derivation returns an empty tuple and cannot satisfy the policy.
    """
    try:
        spec = scheduler_contract.build_one_week_soak_scheduler_deployment_spec(
            ACTIVATION_UTC
        )
        if type(spec) is not scheduler_contract.OneWeekSoakSchedulerDeploymentSpec:
            return ()
        spec.__post_init__()
        if (
            not scheduler_contract.is_frozen_one_week_soak_scheduler_contract(
                scheduler_contract.one_week_soak_scheduler_contract()
            )
            or spec.schema != scheduler_contract.D10_SCHEDULER_DEPLOYMENT_SPEC_SCHEMA
            or spec.window.activation_utc != ACTIVATION_UTC
            or spec.window.end_utc != END_UTC
            or spec.end_boundary.astimezone(UTC) != END_UTC
            or spec.task.task_path != TASK_PATH
            or type(spec.task.days_interval) is not int
            or spec.task.days_interval != 1
        ):
            return ()
        slots: list[datetime] = []
        boundary = spec.task.start_boundary
        # Bounded derivation also rejects a spec that would supply extra slots.
        for _ in range(SLOT_COUNT + 1):
            slot = boundary.astimezone(UTC)
            if slot >= spec.end_boundary.astimezone(UTC):
                break
            if not ACTIVATION_UTC <= slot < END_UTC:
                return ()
            slots.append(slot)
            boundary += timedelta(days=spec.task.days_interval)
        if len(slots) != SLOT_COUNT or any(
            earlier >= later for earlier, later in zip(slots, slots[1:], strict=False)
        ):
            return ()
        return tuple(slots)
    except Exception:
        return ()


def analyze(observation: D10SchedulerHistoryObservation) -> dict[str, object]:
    """Validate supplied history without collection, sorting, repair, or authority."""
    if type(observation) is not D10SchedulerHistoryObservation:
        return _blocked("observation_type_invalid")
    if (
        type(observation.deployment_id) is not str
        or observation.deployment_id != DEPLOYMENT_ID
        or type(observation.soak_id) is not str
        or observation.soak_id != SOAK_ID
        or not _utc(observation.activation_utc)
        or observation.activation_utc != ACTIVATION_UTC
        or not _utc(observation.end_utc)
        or observation.end_utc != END_UTC
    ):
        return _blocked("observation_identity_mismatch")
    if not _utc(observation.collected_at_utc):
        return _blocked("collection_time_invalid")
    if observation.collected_at_utc < END_UTC:
        return _blocked("collection_window_not_complete")
    if observation.channel_enabled is not True:
        return _blocked("history_channel_not_enabled")
    if (
        not _utc(observation.oldest_retained_event_utc)
        or observation.oldest_retained_event_utc > ACTIVATION_UTC
    ):
        return _blocked("history_retention_insufficient")
    if type(observation.events) is not tuple:
        return _blocked("event_input_invalid")
    previous_record = 0
    previous_time = ACTIVATION_UTC
    for event in observation.events:
        if (
            type(event) is not D10SchedulerHistoryEvent
            or type(event.kind) is not D10SchedulerHistoryEventKind
            or type(event.event_id) is not int
            or event.event_id != EVENT_IDS[event.kind]
            or type(event.record_id) is not int
            or event.record_id <= 0
            or not _utc(event.observed_at_utc)
            or not _instance_id(event.instance_id)
        ):
            return _blocked("event_input_invalid")
        if type(event.task_name) is not str or event.task_name != TASK_PATH:
            return _blocked("foreign_task_event")
        if not ACTIVATION_UTC <= event.observed_at_utc < END_UTC:
            return _blocked("event_outside_window")
        if event.record_id <= previous_record or event.observed_at_utc < previous_time:
            return _blocked("event_order_invalid")
        previous_record = event.record_id
        previous_time = event.observed_at_utc
    if any(
        event.kind is D10SchedulerHistoryEventKind.MANUAL_TRIGGER
        for event in observation.events
    ):
        return _blocked("manual_task_trigger_observed")
    slots = expected_slots_utc()
    if len(slots) != SLOT_COUNT:
        return _blocked("expected_slot_derivation_invalid")
    triggers = tuple(
        event
        for event in observation.events
        if event.kind is D10SchedulerHistoryEventKind.SCHEDULED_TRIGGER
    )
    if len(triggers) != SLOT_COUNT:
        return _blocked("scheduled_trigger_count_invalid")
    if len({event.instance_id for event in triggers}) != SLOT_COUNT:
        return _blocked("instance_id_duplicate")
    if any(event.observed_at_utc < slots[0] for event in triggers):
        return _blocked("scheduled_trigger_outside_slots")
    ordered_triggers: list[D10SchedulerHistoryEvent] = []
    for index, slot in enumerate(slots):
        interval_end = slots[index + 1] if index + 1 < SLOT_COUNT else END_UTC
        matched = tuple(
            event for event in triggers if slot <= event.observed_at_utc < interval_end
        )
        if not matched:
            return _blocked("scheduled_slot_missing")
        if len(matched) != 1:
            return _blocked("scheduled_slot_duplicate")
        ordered_triggers.append(matched[0])
    scheduled_ids = {event.instance_id for event in triggers}
    if any(
        event.kind
        in (
            D10SchedulerHistoryEventKind.TASK_STARTED,
            D10SchedulerHistoryEventKind.TASK_COMPLETED,
        )
        and event.instance_id not in scheduled_ids
        for event in observation.events
    ):
        return _blocked("unmatched_task_execution")
    instances: list[dict[str, object]] = []
    for slot, trigger in zip(slots, ordered_triggers, strict=True):
        starts = tuple(
            event
            for event in observation.events
            if event.kind is D10SchedulerHistoryEventKind.TASK_STARTED
            and event.instance_id == trigger.instance_id
        )
        completions = tuple(
            event
            for event in observation.events
            if event.kind is D10SchedulerHistoryEventKind.TASK_COMPLETED
            and event.instance_id == trigger.instance_id
        )
        if not starts:
            return _blocked("instance_start_missing")
        if len(starts) != 1:
            return _blocked("instance_start_duplicate")
        if not completions:
            return _blocked("instance_completion_missing")
        if len(completions) != 1:
            return _blocked("instance_completion_duplicate")
        start, completion = starts[0], completions[0]
        if (
            not trigger.observed_at_utc
            <= start.observed_at_utc
            <= (completion.observed_at_utc)
        ):
            return _blocked("instance_time_order_invalid")
        instances.append(
            {
                "slot_utc": _timestamp(slot),
                "instance_id": trigger.instance_id,
                "triggered_at_utc": _timestamp(trigger.observed_at_utc),
                "started_at_utc": _timestamp(start.observed_at_utc),
                "completed_at_utc": _timestamp(completion.observed_at_utc),
            }
        )
    return {
        "schema": SCHEMA,
        "status": "READY_FOR_EXTERNAL_REVIEW_ARTIFACT",
        "category": "SCHEDULER_SLOT_COVERAGE",
        "deployment_id": DEPLOYMENT_ID,
        "soak_id": SOAK_ID,
        "activation_utc": _timestamp(ACTIVATION_UTC),
        "end_utc": _timestamp(END_UTC),
        "slot_count": SLOT_COUNT,
        "scheduled_trigger_count": SLOT_COUNT,
        "manual_trigger_count": 0,
        "started_count": SLOT_COUNT,
        "completed_count": SLOT_COUNT,
        "channel_enabled": True,
        "history_retained_from_before_activation": True,
        "collected_at_utc": _timestamp(observation.collected_at_utc),
        "expected_slots_utc": tuple(_timestamp(slot) for slot in slots),
        "instances": tuple(instances),
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }
