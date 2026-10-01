"""Fixed S2C1B read-only Windows scheduler-history collector source.

S2C1B source acceptance does not authorize observe().
Operational invocation remains a later separately reviewed checkpoint. Importing
this module and the verify-only runner never collect Windows event history.
"""

from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from scripts import d10_scheduler_slot_review_policy as policy

SCHEMA = "d10-scheduler-history-collector/v1"
HELPER_SCHEMA = "d10-scheduler-history-windows-observation/v1"
CHANNEL = "Microsoft-Windows-TaskScheduler/Operational"
PROVIDER = "Microsoft-Windows-TaskScheduler"
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
HELPER = Path(__file__).resolve().with_name("d10_scheduler_history_observe.ps1")
MAX_STDOUT = 256 * 1024
MAX_STDERR = 256
MAX_TARGET_EVENTS = 256
TIMEOUT_SECONDS = 60
NOT_RUN = {
    "production_filesystem_mutation": "NOT_RUN",
    "event_log_mutation": "NOT_RUN",
    "scheduler_mutation": "NOT_RUN",
    "manual_task_start": "NOT_RUN",
    "source_launch": "NOT_RUN",
    "provider": "NOT_RUN",
    "Paper-v2": "NOT_RUN",
    "broker": "NOT_RUN",
    "live": "NOT_RUN",
}
POLICY_REASONS = frozenset(
    {
        "observation_type_invalid",
        "observation_identity_mismatch",
        "collection_time_invalid",
        "collection_window_not_complete",
        "history_channel_not_enabled",
        "history_retention_insufficient",
        "event_input_invalid",
        "foreign_task_event",
        "event_outside_window",
        "event_order_invalid",
        "manual_task_trigger_observed",
        "expected_slot_derivation_invalid",
        "scheduled_trigger_count_invalid",
        "instance_id_duplicate",
        "scheduled_trigger_outside_slots",
        "scheduled_slot_missing",
        "scheduled_slot_duplicate",
        "unmatched_task_execution",
        "instance_start_missing",
        "instance_start_duplicate",
        "instance_completion_missing",
        "instance_completion_duplicate",
        "instance_time_order_invalid",
    }
)


def _blocked(reason: str, policy_reason: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "reason": reason,
        **NOT_RUN,
    }
    if policy_reason is not None:
        result["policy_reason"] = policy_reason
    return result


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _timestamp(value: object) -> datetime:
    if (
        type(value) is not str
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", value
        )
        is None
    ):
        raise ValueError
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def _uuid(value: object) -> str:
    if type(value) is not str or len(value) != 36 or str(UUID(value)) != value:
        raise ValueError
    return value


def _observation(value: object) -> policy.D10SchedulerHistoryObservation:
    if type(value) is not dict or set(value) != {
        "schema",
        "status",
        "channel",
        "provider",
        "channel_enabled",
        "oldest_retained_event_utc",
        "collected_at_utc",
        "events",
    }:
        raise ValueError
    for field, expected in (
        ("schema", HELPER_SCHEMA),
        ("status", "OBSERVED"),
        ("channel", CHANNEL),
        ("provider", PROVIDER),
    ):
        if type(value[field]) is not str or value[field] != expected:
            raise ValueError
    if type(value["channel_enabled"]) is not bool:
        raise ValueError
    collected = _timestamp(value["collected_at_utc"])
    oldest = value["oldest_retained_event_utc"]
    retained = None if oldest is None else _timestamp(oldest)
    if type(value["events"]) is not list or len(value["events"]) > MAX_TARGET_EVENTS:
        raise ValueError
    kinds = {event_id: kind for kind, event_id in policy.EVENT_IDS.items()}
    events: list[policy.D10SchedulerHistoryEvent] = []
    for event in value["events"]:
        if type(event) is not dict or set(event) != {
            "event_id",
            "record_id",
            "observed_at_utc",
            "task_name",
            "instance_id",
        }:
            raise ValueError
        if (
            type(event["event_id"]) is not int
            or event["event_id"] not in kinds
            or type(event["record_id"]) is not int
            or not 0 < event["record_id"] <= 2**64 - 1
            or type(event["task_name"]) is not str
            or event["task_name"] != policy.TASK_PATH
        ):
            raise ValueError
        events.append(
            policy.D10SchedulerHistoryEvent(
                kind=kinds[event["event_id"]],
                event_id=event["event_id"],
                record_id=event["record_id"],
                observed_at_utc=_timestamp(event["observed_at_utc"]),
                task_name=event["task_name"],
                instance_id=_uuid(event["instance_id"]),
            )
        )
    if value["channel_enabled"] is False:
        raise _ChannelDisabled
    if retained is None:
        raise _RetentionUnavailable
    return policy.D10SchedulerHistoryObservation(
        deployment_id=policy.DEPLOYMENT_ID,
        soak_id=policy.SOAK_ID,
        activation_utc=policy.ACTIVATION_UTC,
        end_utc=policy.END_UTC,
        collected_at_utc=collected,
        channel_enabled=True,
        oldest_retained_event_utc=retained,
        events=tuple(events),
    )


class _ChannelDisabled(ValueError):
    pass


class _RetentionUnavailable(ValueError):
    pass


def _policy_result(value: object) -> dict[str, object]:
    # Validate the exact sanitized result envelope, without reimplementing policy.
    base = {
        "schema": policy.SCHEMA,
        "category": "SCHEDULER_SLOT_COVERAGE",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }
    if type(value) is not dict:
        raise ValueError
    for field, expected in base.items():
        if type(value.get(field)) is not type(expected) or value[field] != expected:
            raise ValueError
    if value.get("status") == "BLOCKED":
        if (
            set(value) != set(base) | {"status", "reason"}
            or type(value["status"]) is not str
            or type(value["reason"]) is not str
            or value["reason"] not in POLICY_REASONS
        ):
            raise ValueError
        return value
    fixed = {
        **base,
        "status": "READY_FOR_EXTERNAL_REVIEW_ARTIFACT",
        "deployment_id": policy.DEPLOYMENT_ID,
        "soak_id": policy.SOAK_ID,
        "activation_utc": "2026-09-30T22:07:24.000000Z",
        "end_utc": "2026-10-07T22:07:24.000000Z",
        "slot_count": policy.SLOT_COUNT,
        "scheduled_trigger_count": policy.SLOT_COUNT,
        "manual_trigger_count": 0,
        "started_count": policy.SLOT_COUNT,
        "completed_count": policy.SLOT_COUNT,
        "channel_enabled": True,
        "history_retained_from_before_activation": True,
    }
    if set(value) != set(fixed) | {
        "collected_at_utc",
        "expected_slots_utc",
        "instances",
    }:
        raise ValueError
    for field, expected in fixed.items():
        if type(value[field]) is not type(expected) or value[field] != expected:
            raise ValueError
    _timestamp(value["collected_at_utc"])
    slots, instances = value["expected_slots_utc"], value["instances"]
    if (
        type(slots) is not tuple
        or len(slots) != policy.SLOT_COUNT
        or type(instances) is not tuple
        or len(instances) != policy.SLOT_COUNT
    ):
        raise ValueError
    for slot in slots:
        _timestamp(slot)
    for instance in instances:
        if type(instance) is not dict or set(instance) != {
            "slot_utc",
            "instance_id",
            "triggered_at_utc",
            "started_at_utc",
            "completed_at_utc",
        }:
            raise ValueError
        _uuid(instance["instance_id"])
        for field in (
            "slot_utc",
            "triggered_at_utc",
            "started_at_utc",
            "completed_at_utc",
        ):
            _timestamp(instance[field])
    return value


def observe() -> dict[str, object]:
    """Source only: S2C1B source acceptance does not authorize observe()."""
    try:
        # Readers allocate at most limit+1 bytes per stream. If a larger producer
        # stalls after that read, the fixed process timeout still fails closed.
        # Construct the readers before launching: allocation failures launch nothing.
        with ThreadPoolExecutor(max_workers=2) as readers:
            with subprocess.Popen(
                (
                    POWERSHELL,
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(HELPER),
                ),
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                try:
                    out = readers.submit(process.stdout.read, MAX_STDOUT + 1)
                    err = readers.submit(process.stderr.read, MAX_STDERR + 1)
                    code = process.wait(timeout=TIMEOUT_SECONDS)
                    stdout, stderr = out.result(), err.result()
                except BaseException:
                    process.kill()
                    process.wait(timeout=TIMEOUT_SECONDS)
                    raise
    except Exception:
        return _blocked("helper_transport_failed")
    if (
        type(stdout) is not bytes
        or type(stderr) is not bytes
        or len(stdout) > MAX_STDOUT
        or len(stderr) > MAX_STDERR
        or code != 0
        or stderr
        or not stdout
    ):
        return _blocked("helper_transport_invalid")
    try:
        observation = _observation(
            json.loads(stdout.decode("utf-8"), object_pairs_hook=_unique_pairs)
        )
    except _ChannelDisabled:
        return _blocked("history_channel_not_enabled")
    except _RetentionUnavailable:
        return _blocked("history_retention_unavailable")
    except Exception:
        return _blocked("helper_observation_invalid")
    try:
        result = _policy_result(policy.analyze(observation))
    except Exception:
        return _blocked("scheduler_slot_policy_invalid")
    if result["status"] == "BLOCKED":
        return _blocked("scheduler_slot_policy_blocked", result["reason"])
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "category": "SCHEDULER_SLOT_COVERAGE",
        "policy": result,
        **NOT_RUN,
    }
