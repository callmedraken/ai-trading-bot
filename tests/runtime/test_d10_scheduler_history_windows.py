"""Mocked helper output only: S2C1B source acceptance does not authorize observe()."""

import inspect
import io
import json
import subprocess
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

import pytest

from scripts import d10_scheduler_history_windows as collector
from scripts import d10_scheduler_slot_review_policy as policy


def _timestamp(value):
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _payload():
    events = [
        {
            "event_id": policy.EVENT_IDS[kind],
            "record_id": index * 3 + offset + 1,
            "observed_at_utc": _timestamp(slot + timedelta(seconds=offset)),
            "task_name": policy.TASK_PATH,
            "instance_id": f"00000000-0000-0000-0000-{index + 1:012x}",
        }
        for index, slot in enumerate(policy.expected_slots_utc())
        for offset, kind in enumerate(
            (
                policy.D10SchedulerHistoryEventKind.SCHEDULED_TRIGGER,
                policy.D10SchedulerHistoryEventKind.TASK_STARTED,
                policy.D10SchedulerHistoryEventKind.TASK_COMPLETED,
            )
        )
    ]
    return {
        "schema": collector.HELPER_SCHEMA,
        "status": "OBSERVED",
        "channel": collector.CHANNEL,
        "provider": collector.PROVIDER,
        "channel_enabled": True,
        "oldest_retained_event_utc": _timestamp(policy.ACTIVATION_UTC),
        "collected_at_utc": _timestamp(policy.END_UTC),
        "events": events,
    }


@pytest.fixture(autouse=True)
def prohibit_real_helper(monkeypatch):
    # Every test starts with a fail-fast subprocess prohibition.
    monkeypatch.setattr(
        collector.subprocess,
        "Popen",
        Mock(side_effect=AssertionError("unmocked helper forbidden")),
    )


def _mock_helper(
    monkeypatch, payload=None, *, stdout=None, stderr=b"", code=0, error=None
):
    if stdout is None:
        stdout = json.dumps(_payload() if payload is None else payload).encode("utf-8")
    process = Mock()
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.stdout = io.BytesIO(stdout)
    process.stderr = io.BytesIO(stderr)
    process.wait = Mock(side_effect=[error, code] if error else None, return_value=code)
    launch = Mock(return_value=process)
    monkeypatch.setattr(collector.subprocess, "Popen", launch)
    return launch, process


def _blocked(result, reason=None):
    assert result["schema"] == collector.SCHEMA
    assert result["status"] == "BLOCKED"
    if reason is not None:
        assert result["reason"] == reason
    assert set(result) <= {"schema", "status", "reason", "policy_reason"} | set(
        collector.NOT_RUN
    )
    for field in collector.NOT_RUN:
        assert result[field] == "NOT_RUN"
    serialized = json.dumps(result)
    assert len(serialized) < 1024
    assert "private exception" not in serialized


def test_valid_projection_exact_observation_and_single_policy_call(monkeypatch):
    payload = _payload()
    launch, process = _mock_helper(monkeypatch, payload)
    analyze = Mock(wraps=policy.analyze)
    monkeypatch.setattr(policy, "analyze", analyze)
    result = collector.observe()
    assert result["status"] == "PASS"
    assert result["category"] == "SCHEDULER_SLOT_COVERAGE"
    launch.assert_called_once_with(
        (
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(collector.HELPER),
        ),
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process.wait.assert_called_once_with(timeout=60)
    process.kill.assert_not_called()
    analyze.assert_called_once()
    observation = analyze.call_args.args[0]
    assert type(observation) is policy.D10SchedulerHistoryObservation
    assert observation.deployment_id == policy.DEPLOYMENT_ID
    assert observation.soak_id == policy.SOAK_ID
    assert observation.activation_utc == policy.ACTIVATION_UTC
    assert observation.end_utc == policy.END_UTC
    assert observation.collected_at_utc == policy.END_UTC
    assert observation.oldest_retained_event_utc == policy.ACTIVATION_UTC
    assert observation.channel_enabled is True
    assert type(observation.events) is tuple
    for event, raw in zip(observation.events, payload["events"], strict=True):
        assert type(event) is policy.D10SchedulerHistoryEvent
        assert type(event.kind) is policy.D10SchedulerHistoryEventKind
        assert policy.EVENT_IDS[event.kind] == event.event_id == raw["event_id"]
        assert event.record_id == raw["record_id"]
        assert event.task_name == raw["task_name"]
        assert event.instance_id == raw["instance_id"]
        assert _timestamp(event.observed_at_utc) == raw["observed_at_utc"]
    assert result["policy"]["slot_count"] == 7
    for field in collector.NOT_RUN:
        assert result[field] == "NOT_RUN"
    serialized = json.dumps(result)
    for forbidden in (
        "UserContext",
        "Computer",
        "UserID",
        "process_id",
        "message",
        "<Event",
        "raw_xml",
    ):
        assert forbidden not in serialized


def test_source_acceptance_is_not_operational_authority():
    assert "S2C1B source acceptance does not authorize observe()." in collector.__doc__
    assert tuple(inspect.signature(collector.observe).parameters) == ()
    assert collector.HELPER.name == "d10_scheduler_history_observe.ps1"
    assert collector.MAX_STDOUT == 256 * 1024
    assert collector.MAX_STDERR == 256
    assert collector.MAX_TARGET_EVENTS == 256


@pytest.mark.parametrize(
    "changes",
    (
        {"code": 1},
        {"stderr": b"private exception"},
        {"stdout": b""},
        {"stdout": b"x" * (collector.MAX_STDOUT + 1)},
        {"stderr": b"x" * (collector.MAX_STDERR + 1)},
    ),
)
def test_transport_rejects_invalid_output_without_policy(monkeypatch, changes):
    launch, _ = _mock_helper(monkeypatch, **changes)
    analyze = Mock()
    monkeypatch.setattr(policy, "analyze", analyze)
    _blocked(collector.observe(), "helper_transport_invalid")
    launch.assert_called_once()
    analyze.assert_not_called()


@pytest.mark.parametrize(
    "error",
    (
        subprocess.TimeoutExpired("private exception", 60),
        RuntimeError("private exception"),
    ),
)
def test_wait_failure_kills_once_no_retry(monkeypatch, error):
    launch, process = _mock_helper(monkeypatch, error=error)
    _blocked(collector.observe(), "helper_transport_failed")
    launch.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_args_list[0].kwargs == {"timeout": 60}
    assert len(process.wait.call_args_list) == 2
    assert process.wait.call_args_list[1].kwargs == {"timeout": 60}


def test_launch_exception_bounded_no_retry(monkeypatch):
    launch = Mock(side_effect=OSError("private exception"))
    monkeypatch.setattr(collector.subprocess, "Popen", launch)
    _blocked(collector.observe(), "helper_transport_failed")
    launch.assert_called_once()


@pytest.mark.parametrize(
    "stdout",
    (
        b'{"schema":"first","schema":"second"}',
        b'{"events":[{"event_id":100,"event_id":107}]}',
        b"\xff",
        b"not JSON",
        b"null",
        b"[]",
        b"{}",
    ),
)
def test_invalid_json(monkeypatch, stdout):
    _mock_helper(monkeypatch, stdout=stdout)
    _blocked(collector.observe(), "helper_observation_invalid")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema", "foreign"),
        ("schema", 1),
        ("status", "PASS"),
        ("status", False),
        ("channel", "foreign"),
        ("provider", "foreign"),
        ("channel_enabled", 1),
        ("collected_at_utc", None),
        ("collected_at_utc", "2026-10-07T22:07:24Z"),
        ("collected_at_utc", "2026-02-30T22:07:24.000000Z"),
        ("collected_at_utc", "2026-10-07T22:07:24.0000000Z"),
        ("oldest_retained_event_utc", "2026-09-30T22:07:24.000000+00:00"),
        ("oldest_retained_event_utc", 123),
        ("events", {}),
        ("events", None),
        ("events", "[]"),
    ),
)
def test_invalid_top_scalars(monkeypatch, field, value):
    payload = _payload()
    payload[field] = value
    _mock_helper(monkeypatch, payload)
    _blocked(collector.observe(), "helper_observation_invalid")


@pytest.mark.parametrize("field", tuple(_payload()))
def test_missing_top_field(monkeypatch, field):
    payload = _payload()
    del payload[field]
    _mock_helper(monkeypatch, payload)
    _blocked(collector.observe(), "helper_observation_invalid")


def test_extra_top_field(monkeypatch):
    payload = _payload()
    payload["raw_xml"] = "private exception"
    _mock_helper(monkeypatch, payload)
    _blocked(collector.observe(), "helper_observation_invalid")


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("channel_enabled", False, "history_channel_not_enabled"),
        ("oldest_retained_event_utc", None, "history_retention_unavailable"),
    ),
)
def test_missing_history_fails_without_policy_or_other_subprocess(
    monkeypatch, field, value, reason
):
    payload = _payload()
    payload[field] = value
    launch, _ = _mock_helper(monkeypatch, payload)
    analyze = Mock()
    monkeypatch.setattr(policy, "analyze", analyze)
    _blocked(collector.observe(), reason)
    launch.assert_called_once()
    analyze.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("event_id", 999),
        ("event_id", True),
        ("event_id", 107.0),
        ("event_id", "107"),
        ("record_id", 0),
        ("record_id", -1),
        ("record_id", True),
        ("record_id", 1.0),
        ("record_id", "1"),
        ("record_id", 2**64),
        ("task_name", r"\OtherTask"),
        ("task_name", None),
        ("instance_id", "00000000-0000-0000-0000-00000000000A"),
        ("instance_id", "{00000000-0000-0000-0000-000000000001}"),
        ("instance_id", "00000000000000000000000000000001"),
        ("instance_id", "not-a-uuid"),
        ("instance_id", 1),
        ("observed_at_utc", "2026-10-01T08:30:00.0000001Z"),
        ("observed_at_utc", "2026-10-01T08:30:00.000000+00:00"),
        ("observed_at_utc", False),
    ),
)
def test_invalid_event_scalar(monkeypatch, field, value):
    payload = _payload()
    payload["events"][0][field] = value
    _mock_helper(monkeypatch, payload)
    _blocked(collector.observe(), "helper_observation_invalid")


@pytest.mark.parametrize("field", tuple(_payload()["events"][0]))
def test_missing_event_field(monkeypatch, field):
    payload = _payload()
    del payload["events"][0][field]
    _mock_helper(monkeypatch, payload)
    _blocked(collector.observe(), "helper_observation_invalid")


@pytest.mark.parametrize("event", (None, [], "event"))
def test_nonexact_event_object(monkeypatch, event):
    payload = _payload()
    payload["events"][0] = event
    _mock_helper(monkeypatch, payload)
    _blocked(collector.observe(), "helper_observation_invalid")


def test_extra_event_field_and_target_overflow(monkeypatch):
    for extra in (True, False):
        payload = _payload()
        if extra:
            payload["events"][0]["UserContext"] = "private exception"
        else:
            payload["events"] = payload["events"] * 13
        _mock_helper(monkeypatch, payload)
        _blocked(collector.observe(), "helper_observation_invalid")


def test_nonexact_event_list(monkeypatch):
    payload = _payload()
    payload["events"] = tuple(payload["events"])
    # This cannot occur via JSON, but the projection boundary must stay exact.
    with pytest.raises(ValueError):
        collector._observation(payload)


@pytest.mark.parametrize(
    ("change", "reason"),
    (
        ("manual", "manual_task_trigger_observed"),
        ("retention", "history_retention_insufficient"),
        ("missing", "scheduled_trigger_count_invalid"),
        ("duplicate", "scheduled_slot_duplicate"),
        ("unmatched", "unmatched_task_execution"),
        ("order", "event_order_invalid"),
    ),
)
def test_real_policy_rejection_is_preserved_once(monkeypatch, change, reason):
    payload = _payload()
    events = payload["events"]
    if change == "manual":
        events[0]["event_id"] = 110
    elif change == "retention":
        payload["oldest_retained_event_utc"] = _timestamp(
            policy.ACTIVATION_UTC + timedelta(microseconds=1)
        )
    elif change == "missing":
        del events[:3]
    elif change == "duplicate":
        for offset in range(3):
            events[3 + offset]["observed_at_utc"] = events[offset]["observed_at_utc"]
        events.sort(key=lambda event: event["observed_at_utc"])
        for index, event in enumerate(events, 1):
            event["record_id"] = index
    elif change == "unmatched":
        events[1]["instance_id"] = "00000000-0000-0000-0000-000000000099"
    else:
        events[1]["record_id"] = events[0]["record_id"]
    _mock_helper(monkeypatch, payload)
    analyze = Mock(wraps=policy.analyze)
    monkeypatch.setattr(policy, "analyze", analyze)
    result = collector.observe()
    _blocked(result, "scheduler_slot_policy_blocked")
    assert result["policy_reason"] == reason
    analyze.assert_called_once()


@pytest.mark.parametrize(
    "change",
    (
        "extra",
        "missing",
        "status",
        "authority",
        "bool_count",
        "identity",
        "instances",
        "instance_extra",
        "instance_uuid",
        "timestamp",
        "slots",
        "blocked_reason",
        "blocked_extra",
        "not_dict",
        "exception",
    ),
)
def test_policy_result_shape_fails_closed(monkeypatch, change):
    value = deepcopy(policy.analyze(collector._observation(_payload())))
    if change == "extra":
        value["raw_xml"] = "private exception"
    elif change == "missing":
        del value["slot_count"]
    elif change == "status":
        value["status"] = "ACCEPTED"
    elif change == "authority":
        value["d10_accepted"] = True
    elif change == "bool_count":
        value["manual_trigger_count"] = False
    elif change == "identity":
        value["soak_id"] = "foreign"
    elif change == "instances":
        value["instances"] = list(value["instances"])
    elif change == "instance_extra":
        value["instances"][0]["UserContext"] = "private exception"
    elif change == "instance_uuid":
        value["instances"][0]["instance_id"] = "foreign"
    elif change == "timestamp":
        value["collected_at_utc"] = "foreign"
    elif change == "slots":
        value["expected_slots_utc"] = ("foreign",) * 7
    elif change.startswith("blocked"):
        value = {
            "schema": policy.SCHEMA,
            "status": "BLOCKED",
            "category": "SCHEDULER_SLOT_COVERAGE",
            "reason": "private exception"
            if change == "blocked_reason"
            else "event_input_invalid",
            "d10_accepted": False,
            "broker_paper_authorized": False,
            "operator_decision_required": True,
        }
        if change == "blocked_extra":
            value["raw_xml"] = "private exception"
    elif change == "not_dict":
        value = []
    _mock_helper(monkeypatch)
    analyze = Mock(return_value=value)
    if change == "exception":
        analyze.side_effect = RuntimeError("private exception")
    monkeypatch.setattr(policy, "analyze", analyze)
    _blocked(collector.observe(), "scheduler_slot_policy_invalid")
    analyze.assert_called_once()


def test_bounded_stream_reads(monkeypatch):
    _, process = _mock_helper(monkeypatch)
    process.stdout = Mock(wraps=process.stdout)
    process.stderr = Mock(wraps=process.stderr)
    assert collector.observe()["status"] == "PASS"
    process.stdout.read.assert_called_once_with(256 * 1024 + 1)
    process.stderr.read.assert_called_once_with(257)


@pytest.mark.parametrize("nested", (False, True))
def test_duplicate_keys_in_otherwise_valid_observation(monkeypatch, nested):
    stdout = json.dumps(_payload())
    if nested:
        stdout = stdout.replace(
            '"event_id": 107', '"event_id": 107, "event_id": 107', 1
        )
    else:
        stdout = stdout.replace(
            '"status": "OBSERVED"', '"status": "OBSERVED", "status": "OBSERVED"', 1
        )
    _mock_helper(monkeypatch, stdout=stdout.encode("utf-8"))
    analyze = Mock()
    monkeypatch.setattr(policy, "analyze", analyze)
    _blocked(collector.observe(), "helper_observation_invalid")
    analyze.assert_not_called()


def test_missing_slot_with_seven_triggers_reaches_policy(monkeypatch):
    payload = _payload()
    for offset in range(3):
        payload["events"][offset]["observed_at_utc"] = _timestamp(
            policy.expected_slots_utc()[1] + timedelta(seconds=offset)
        )
    payload["events"].sort(key=lambda event: event["observed_at_utc"])
    for index, event in enumerate(payload["events"], 1):
        event["record_id"] = index
    _mock_helper(monkeypatch, payload)
    result = collector.observe()
    _blocked(result, "scheduler_slot_policy_blocked")
    assert result["policy_reason"] == "scheduled_slot_missing"


def test_stream_exception_is_bounded_without_retry(monkeypatch):
    launch, process = _mock_helper(monkeypatch)
    process.stdout = Mock()
    process.stdout.read.side_effect = OSError("private exception")
    _blocked(collector.observe(), "helper_transport_failed")
    launch.assert_called_once()
    process.kill.assert_called_once()


def test_reader_resource_failure_launches_nothing(monkeypatch):
    launch, _ = _mock_helper(monkeypatch)
    monkeypatch.setattr(
        collector,
        "ThreadPoolExecutor",
        Mock(side_effect=RuntimeError("private exception")),
    )
    _blocked(collector.observe(), "helper_transport_failed")
    launch.assert_not_called()
