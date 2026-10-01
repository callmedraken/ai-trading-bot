"""Synthetic history only; no Windows or production evidence access."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from scripts import d10_scheduler_slot_review_policy as policy

Kind = policy.D10SchedulerHistoryEventKind
Event = policy.D10SchedulerHistoryEvent
Observation = policy.D10SchedulerHistoryObservation


def _event(kind=Kind.SCHEDULED_TRIGGER, *, instant=None, instance=1, record=1):
    return Event(
        kind,
        policy.EVENT_IDS[kind],
        record,
        instant if instant is not None else policy.expected_slots_utc()[0],
        policy.TASK_PATH,
        f"00000000-0000-0000-0000-{instance:012x}",
    )


def _canonical(events):
    # Fixture assembly only. The production policy must never sort its input.
    return tuple(
        replace(event, record_id=index)
        for index, event in enumerate(
            sorted(events, key=lambda event: event.observed_at_utc), 1
        )
    )


def _history(*, delay=timedelta(0)):
    return _canonical(
        [
            _event(
                kind, instant=slot + delay + timedelta(seconds=offset), instance=index
            )
            for index, slot in enumerate(policy.expected_slots_utc(), 1)
            for offset, kind in enumerate(
                (Kind.SCHEDULED_TRIGGER, Kind.TASK_STARTED, Kind.TASK_COMPLETED)
            )
        ]
    )


def _observation(events=None, **changes):
    return replace(
        Observation(
            policy.DEPLOYMENT_ID,
            policy.SOAK_ID,
            policy.ACTIVATION_UTC,
            policy.END_UTC,
            policy.END_UTC,
            True,
            policy.ACTIVATION_UTC,
            _history() if events is None else events,
        ),
        **changes,
    )


def _blocked(observation, reason):
    result = policy.analyze(observation)
    assert result == {
        "schema": policy.SCHEMA,
        "status": "BLOCKED",
        "reason": reason,
        "category": "SCHEDULER_SLOT_COVERAGE",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }


@pytest.mark.parametrize("delay", (timedelta(0), timedelta(hours=4)))
def test_exact_or_delayed_seven_lifecycles_ready(delay):
    observation = _observation(_history(delay=delay))
    result = policy.analyze(observation)
    assert result == policy.analyze(observation)
    assert result["status"] == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"
    assert result["schema"] == "d10-scheduler-slot-review/v1"
    assert result["category"] == "SCHEDULER_SLOT_COVERAGE"
    assert result["deployment_id"] == policy.DEPLOYMENT_ID
    assert result["soak_id"] == policy.SOAK_ID
    assert result["activation_utc"] == "2026-09-30T22:07:24.000000Z"
    assert (
        result["end_utc"]
        == result["collected_at_utc"]
        == ("2026-10-07T22:07:24.000000Z")
    )
    for field in (
        "slot_count",
        "scheduled_trigger_count",
        "started_count",
        "completed_count",
    ):
        assert result[field] == 7
    assert result["manual_trigger_count"] == 0
    assert result["channel_enabled"] is True
    assert result["history_retained_from_before_activation"] is True
    assert result["d10_accepted"] is False
    assert result["broker_paper_authorized"] is False
    assert result["operator_decision_required"] is True
    assert len(result["instances"]) == 7
    for index, instance in enumerate(result["instances"]):
        assert set(instance) == {
            "slot_utc",
            "instance_id",
            "triggered_at_utc",
            "started_at_utc",
            "completed_at_utc",
        }
        assert instance["slot_utc"] == result["expected_slots_utc"][index]
        assert instance["instance_id"] == observation.events[index * 3].instance_id
    assert set(result) == {
        "schema",
        "status",
        "category",
        "deployment_id",
        "soak_id",
        "activation_utc",
        "end_utc",
        "slot_count",
        "scheduled_trigger_count",
        "manual_trigger_count",
        "started_count",
        "completed_count",
        "channel_enabled",
        "history_retained_from_before_activation",
        "collected_at_utc",
        "expected_slots_utc",
        "instances",
        "d10_accepted",
        "broker_paper_authorized",
        "operator_decision_required",
    }


def test_derived_slots_and_frozen_spec(monkeypatch):
    original = policy.scheduler_contract.build_one_week_soak_scheduler_deployment_spec
    calls = []

    def observed(activation):
        calls.append(activation)
        return original(activation)

    monkeypatch.setattr(
        policy.scheduler_contract,
        "build_one_week_soak_scheduler_deployment_spec",
        observed,
    )
    slots = policy.expected_slots_utc()
    assert calls == [policy.ACTIVATION_UTC]
    assert slots == tuple(
        datetime(2026, 10, day, 8, 30, tzinfo=UTC) for day in range(1, 8)
    )
    assert tuple(policy.analyze(_observation())["expected_slots_utc"]) == tuple(
        slot.isoformat(timespec="microseconds").replace("+00:00", "Z") for slot in slots
    )


@pytest.mark.parametrize("position", range(7))
def test_trigger_at_boundary_belongs_to_that_slot(position):
    result = policy.analyze(_observation())
    instance = result["instances"][position]
    assert instance["triggered_at_utc"] == instance["slot_utc"]


@pytest.mark.parametrize("position", range(6))
def test_trigger_immediately_before_next_slot_belongs_to_prior_slot(position):
    slots = policy.expected_slots_utc()
    instant = slots[position + 1] - timedelta(microseconds=1)
    events = list(_history())
    for offset in range(3):
        events[position * 3 + offset] = replace(
            events[position * 3 + offset], observed_at_utc=instant
        )
    result = policy.analyze(_observation(_canonical(events)))
    assert result["status"] == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"
    assert (
        result["instances"][position]["slot_utc"]
        == result["expected_slots_utc"][position]
    )


@pytest.mark.parametrize(
    "instant",
    (
        policy.ACTIVATION_UTC,
        policy.expected_slots_utc()[0],
        policy.END_UTC - timedelta(microseconds=1),
    ),
)
def test_manual_trigger_anywhere_blocks(instant):
    _blocked(
        _observation(
            _canonical(
                (*_history(), _event(Kind.MANUAL_TRIGGER, instant=instant, instance=99))
            )
        ),
        "manual_task_trigger_observed",
    )


@pytest.mark.parametrize("count", (0, 6, 8))
def test_total_scheduled_count_invalid(count):
    events = _history()
    if count == 0:
        events = tuple(
            event for event in events if event.kind is not Kind.SCHEDULED_TRIGGER
        )
    elif count == 6:
        events = events[:-3]
    else:
        events = _canonical((*events, _event(instance=99)))
    _blocked(_observation(events), "scheduled_trigger_count_invalid")


@pytest.mark.parametrize(
    ("slot_from", "slot_to", "reason"),
    (
        (1, 0, "scheduled_slot_duplicate"),
        (0, 1, "scheduled_slot_missing"),
    ),
)
def test_duplicate_or_empty_interval(slot_from, slot_to, reason):
    events = list(_history())
    slot = policy.expected_slots_utc()[slot_to] + timedelta(hours=2)
    for offset in range(3):
        index = slot_from * 3 + offset
        events[index] = replace(events[index], observed_at_utc=slot)
    _blocked(_observation(_canonical(events)), reason)


def test_trigger_before_first_slot_blocks():
    events = list(_history())
    events[0] = replace(events[0], observed_at_utc=policy.ACTIVATION_UTC)
    _blocked(_observation(tuple(events)), "scheduled_trigger_outside_slots")


@pytest.mark.parametrize(
    "instant",
    (
        policy.ACTIVATION_UTC - timedelta(microseconds=1),
        policy.END_UTC,
        policy.END_UTC + timedelta(microseconds=1),
    ),
)
@pytest.mark.parametrize("kind", tuple(Kind))
def test_all_events_must_be_inside_half_open_window(instant, kind):
    _blocked(
        _observation(_canonical((*_history(), _event(kind, instant=instant)))),
        "event_outside_window",
    )


@pytest.mark.parametrize(
    ("kind", "duplicate", "reason"),
    (
        (Kind.TASK_STARTED, False, "instance_start_missing"),
        (Kind.TASK_STARTED, True, "instance_start_duplicate"),
        (Kind.TASK_COMPLETED, False, "instance_completion_missing"),
        (Kind.TASK_COMPLETED, True, "instance_completion_duplicate"),
    ),
)
def test_lifecycle_cardinality(kind, duplicate, reason):
    events = list(_history())
    event = next(event for event in events if event.kind is kind)
    if duplicate:
        events.append(event)
    else:
        events.remove(event)
    _blocked(_observation(_canonical(events)), reason)


@pytest.mark.parametrize(
    ("index", "instant"),
    (
        (1, policy.expected_slots_utc()[0] - timedelta(microseconds=1)),
        (2, policy.expected_slots_utc()[0]),
    ),
)
def test_lifecycle_time_order(index, instant):
    events = list(_history())
    events[index] = replace(events[index], observed_at_utc=instant)
    _blocked(_observation(_canonical(events)), "instance_time_order_invalid")


def test_reused_instance_blocks():
    events = list(_history())
    for index in (3, 4, 5):
        events[index] = replace(events[index], instance_id=events[0].instance_id)
    _blocked(_observation(tuple(events)), "instance_id_duplicate")


@pytest.mark.parametrize("kind", (Kind.TASK_STARTED, Kind.TASK_COMPLETED))
def test_unmatched_execution_blocks(kind):
    _blocked(
        _observation(_canonical((*_history(), _event(kind, instance=99)))),
        "unmatched_task_execution",
    )


def test_seven_generic_starts_do_not_prove_scheduled_origin():
    events = tuple(
        event for event in _history() if event.kind is not Kind.SCHEDULED_TRIGGER
    )
    _blocked(_observation(events), "scheduled_trigger_count_invalid")


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("deployment_id", "foreign", "observation_identity_mismatch"),
        ("soak_id", "foreign", "observation_identity_mismatch"),
        (
            "activation_utc",
            policy.ACTIVATION_UTC + timedelta(seconds=1),
            "observation_identity_mismatch",
        ),
        (
            "end_utc",
            policy.END_UTC + timedelta(seconds=1),
            "observation_identity_mismatch",
        ),
        (
            "activation_utc",
            policy.ACTIVATION_UTC.replace(tzinfo=None),
            "observation_identity_mismatch",
        ),
        ("end_utc", None, "observation_identity_mismatch"),
        ("collected_at_utc", None, "collection_time_invalid"),
        (
            "collected_at_utc",
            policy.END_UTC.replace(tzinfo=None),
            "collection_time_invalid",
        ),
        (
            "collected_at_utc",
            policy.END_UTC - timedelta(microseconds=1),
            "collection_window_not_complete",
        ),
        ("channel_enabled", False, "history_channel_not_enabled"),
        ("channel_enabled", 1, "history_channel_not_enabled"),
        (
            "oldest_retained_event_utc",
            policy.ACTIVATION_UTC + timedelta(microseconds=1),
            "history_retention_insufficient",
        ),
        ("oldest_retained_event_utc", None, "history_retention_insufficient"),
        ("events", [], "event_input_invalid"),
        ("events", (None,), "event_input_invalid"),
    ),
)
def test_invalid_observation_fields(field, value, reason):
    _blocked(_observation(**{field: value}), reason)


@pytest.mark.parametrize("value", (None, {}, SimpleNamespace()))
def test_observation_exact_type(value):
    _blocked(value, "observation_type_invalid")


@pytest.mark.parametrize(
    "retention",
    (
        policy.ACTIVATION_UTC,
        policy.ACTIVATION_UTC - timedelta(days=2),
    ),
)
def test_retained_history_at_or_before_activation_allowed(retention):
    assert (
        policy.analyze(_observation(oldest_retained_event_utc=retention))["status"]
        == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("kind", "SCHEDULED_TRIGGER", "event_input_invalid"),
        ("event_id", 100, "event_input_invalid"),
        ("event_id", True, "event_input_invalid"),
        ("event_id", 107.0, "event_input_invalid"),
        ("record_id", True, "event_input_invalid"),
        ("record_id", 0, "event_input_invalid"),
        ("record_id", -1, "event_input_invalid"),
        ("record_id", 1.0, "event_input_invalid"),
        ("observed_at_utc", None, "event_input_invalid"),
        (
            "observed_at_utc",
            policy.ACTIVATION_UTC.replace(tzinfo=None),
            "event_input_invalid",
        ),
        (
            "observed_at_utc",
            policy.ACTIVATION_UTC.replace(tzinfo=timezone(timedelta(hours=1))),
            "event_input_invalid",
        ),
        ("task_name", "foreign", "foreign_task_event"),
        ("task_name", None, "foreign_task_event"),
        ("instance_id", "malformed", "event_input_invalid"),
        (
            "instance_id",
            "{00000000-0000-0000-0000-000000000001}",
            "event_input_invalid",
        ),
        ("instance_id", "AAAAAAAA-0000-0000-0000-000000000001", "event_input_invalid"),
        ("instance_id", "00000000_0000-0000-0000-000000000001", "event_input_invalid"),
        ("instance_id", "00000000-0000-0000-0000-00000000000g", "event_input_invalid"),
        ("instance_id", None, "event_input_invalid"),
    ),
)
def test_invalid_event_fields(field, value, reason):
    events = list(_history())
    events[0] = replace(events[0], **{field: value})
    _blocked(_observation(tuple(events)), reason)


@pytest.mark.parametrize("kind", tuple(Kind))
def test_exact_id_mapping_for_every_kind(kind):
    events = list(_history())
    events[0] = replace(events[0], kind=kind, event_id=999)
    _blocked(_observation(tuple(events)), "event_input_invalid")
    assert policy.EVENT_IDS == {
        Kind.SCHEDULED_TRIGGER: 107,
        Kind.MANUAL_TRIGGER: 110,
        Kind.TASK_STARTED: 100,
        Kind.TASK_COMPLETED: 102,
    }


@pytest.mark.parametrize("correction", ("reversed", "duplicate", "time"))
def test_noncanonical_order_blocks(correction):
    events = list(_history())
    if correction == "reversed":
        events[1] = replace(events[1], record_id=3)
        events[2] = replace(events[2], record_id=2)
    elif correction == "duplicate":
        events[1] = replace(events[1], record_id=1)
    else:
        events[2] = replace(events[2], observed_at_utc=events[0].observed_at_utc)
    _blocked(_observation(tuple(events)), "event_order_invalid")


def test_models_are_frozen_and_slotted():
    for value in (_event(), _observation()):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, "kind" if type(value) is Event else "soak_id", "not allowed")


@pytest.mark.parametrize(
    "drift", ("type", "exception", "start", "interval", "end", "task", "contract")
)
def test_derivation_fails_closed(monkeypatch, drift):
    observation = _observation()
    original = policy.scheduler_contract.build_one_week_soak_scheduler_deployment_spec
    spec = original(policy.ACTIVATION_UTC)
    if drift == "contract":
        monkeypatch.setattr(
            policy.scheduler_contract,
            "is_frozen_one_week_soak_scheduler_contract",
            lambda _: False,
        )
    else:
        if drift == "start":
            object.__setattr__(
                spec.task,
                "start_boundary",
                spec.task.start_boundary + timedelta(days=1),
            )
        elif drift == "interval":
            object.__setattr__(spec.task, "days_interval", 2)
        elif drift == "end":
            object.__setattr__(
                spec, "end_boundary", spec.end_boundary + timedelta(days=1)
            )
        elif drift == "task":
            object.__setattr__(spec.task, "task_path", "foreign")

        def builder(_):
            if drift == "exception":
                raise ValueError("arbitrary exception text must never escape")
            return None if drift == "type" else spec

        monkeypatch.setattr(
            policy.scheduler_contract,
            "build_one_week_soak_scheduler_deployment_spec",
            builder,
        )
    _blocked(observation, "expected_slot_derivation_invalid")
