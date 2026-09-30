from __future__ import annotations

import inspect
from unittest.mock import Mock

import pytest

from scripts import d10_arch128_r8_readonly as r8


def _observation(outcome: str = "COMPLETED") -> dict[str, object]:
    return {
        **r8.EXPECTED_IDENTITY,
        "evidence_byte_length": 4096,
        "evidence_sha256": "a" * 64,
        "record_count": 3,
        "wake_count": 1,
        "terminal": False,
        "terminal_kind": None,
        "first_observed_at_utc": "2026-10-01T00:00:00Z",
        "last_observed_at_utc": "2026-10-01T00:00:01.123456Z",
        "last_outcome": outcome,
        "last_stop_reason": None,
        "last_guard_reason": None,
        **dict.fromkeys(r8.OBSERVER_EFFECT_FIELDS, "NOT_RUN"),
    }


def _assert_closed(result: dict[str, object]) -> None:
    for field in (
        "production_filesystem_mutation",
        "evidence_mutation",
        "scheduler_mutation",
        "lease_mutation",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    ):
        assert result[field] == "NOT_RUN"


@pytest.mark.parametrize("outcome", ("COMPLETED", "NO_ACTION"))
def test_exact_first_accepted_wake_passes_once(monkeypatch, outcome) -> None:
    observation = _observation(outcome)
    observe = Mock(return_value=observation)
    monkeypatch.setattr(r8.observer, "observe", observe)
    result = r8.preflight()
    assert result["status"] == "PASS"
    assert result["first_wake_durable_sequence"] == "ACCEPTED"
    assert result["observation"] == observation
    assert result["observation"] is not observation
    assert result["schema"] == "architecture-128-r8-readonly-first-wake/v1"
    observe.assert_called_once_with()
    _assert_closed(result)
    assert not inspect.signature(r8.preflight).parameters


@pytest.mark.parametrize(
    "changes",
    (
        {"record_count": 0, "wake_count": 0, "evidence_byte_length": 0},
        {
            "record_count": 1,
            "wake_count": 0,
            "terminal": True,
            "terminal_kind": "WAKE_STARTED_INCOMPLETE",
            "last_outcome": None,
        },
        {
            "record_count": 2,
            "terminal": True,
            "terminal_kind": "WAKE_RESULT_UNACCEPTED",
        },
        {
            "record_count": 2,
            "last_outcome": "STOPPED",
            "terminal": True,
            "terminal_kind": "STOPPED",
            "last_stop_reason": "BLOCKED",
        },
        {
            "record_count": 2,
            "wake_count": 0,
            "terminal": True,
            "terminal_kind": "GUARD_TERMINAL",
            "last_guard_reason": "BLOCKED",
        },
        {"record_count": 6, "wake_count": 2},
        {"record_count": 4},
        {"record_count": 2},
        {"record_count": 3.0},
        {"record_count": True},
        {"wake_count": 2},
        {"wake_count": True},
        {"wake_count": 1.0},
        {"terminal": 0},
        {"terminal": True},
        {"terminal_kind": "STOPPED"},
        {"last_outcome": "UNKNOWN"},
        {"last_outcome": None},
        {"last_outcome": []},
        {"last_stop_reason": "BLOCKED"},
        {"last_guard_reason": "BLOCKED"},
        {"schema": "other/v1"},
        {"status": "PASS"},
        {"deployment_id": "11111111-1111-5111-8111-111111111111"},
        {"attestation_sha256": "b" * 64},
        {"soak_id": "22222222-2222-5222-8222-222222222222"},
        {"activation_utc": "2026-09-30T22:07:25.000000Z"},
        {"end_utc": "2026-10-07T22:07:25.000000Z"},
        {"evidence_path": r"F:\AITradingBot\D10\evidence\other.jsonl"},
        {"evidence_sha256": "A" * 64},
        {"evidence_sha256": "g" * 64},
        {"evidence_sha256": "a" * 63},
        {"evidence_sha256": None},
        {"evidence_sha256": "a" * 64 + "\n"},
        {"evidence_byte_length": 0},
        {"evidence_byte_length": -1},
        {"evidence_byte_length": True},
        {"evidence_byte_length": 1.0},
        {"evidence_byte_length": r8.MAX_D10_EVIDENCE_LOG_BYTES + 1},
        {"extra_authority": "CALL_RETURNED"},
    ),
)
def test_invalid_first_wake_blocks(monkeypatch, changes) -> None:
    observation = _observation()
    observation.update(changes)
    observe = Mock(return_value=observation)
    monkeypatch.setattr(r8.observer, "observe", observe)
    result = r8.preflight()
    assert result["status"] == "BLOCKED"
    assert "observation" not in result
    assert "first_wake_durable_sequence" not in result
    assert len(result["reason"]) < 64
    assert len(result["detail"]) < 128
    observe.assert_called_once_with()
    _assert_closed(result)


@pytest.mark.parametrize("field", ("first_observed_at_utc", "last_observed_at_utc"))
@pytest.mark.parametrize(
    "value",
    (
        None,
        "",
        123,
        "2026-10-01",
        "2026-10-01T00:00:00+00:00",
        "2026-10-01T00:00:00.000000Z",
        "2026-10-01T00:00:00.1Z",
        "2026-02-30T00:00:00Z",
        "2026-10-01T00:00:00Z\n",
        "x" * 10000,
    ),
)
def test_missing_or_noncanonical_timestamp_blocks(monkeypatch, field, value) -> None:
    observation = _observation()
    observation[field] = value
    monkeypatch.setattr(r8.observer, "observe", lambda: observation)
    assert r8.preflight()["status"] == "BLOCKED"


def test_timestamp_order_blocks(monkeypatch) -> None:
    observation = _observation()
    observation["first_observed_at_utc"] = "2026-10-02T00:00:00Z"
    monkeypatch.setattr(r8.observer, "observe", lambda: observation)
    assert r8.preflight()["status"] == "BLOCKED"


@pytest.mark.parametrize("field", tuple(_observation()))
def test_missing_observation_field_blocks(monkeypatch, field) -> None:
    observation = _observation()
    del observation[field]
    monkeypatch.setattr(r8.observer, "observe", lambda: observation)
    assert r8.preflight()["status"] == "BLOCKED"


class _DictionarySubclass(dict):
    pass


@pytest.mark.parametrize(
    "value", (None, [], "OBSERVED", _DictionarySubclass(_observation()))
)
def test_nonexact_dictionary_blocks(monkeypatch, value) -> None:
    monkeypatch.setattr(r8.observer, "observe", lambda: value)
    result = r8.preflight()
    assert result["status"] == "BLOCKED"
    _assert_closed(result)


@pytest.mark.parametrize("field", r8.OBSERVER_EFFECT_FIELDS)
def test_observer_effect_drift_blocks(monkeypatch, field) -> None:
    observation = _observation()
    observation[field] = "CALL_RETURNED"
    monkeypatch.setattr(r8.observer, "observe", lambda: observation)
    result = r8.preflight()
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "observer_effect_drift"
    _assert_closed(result)


def test_observer_exception_is_bounded_and_not_retried(monkeypatch) -> None:
    observe = Mock(side_effect=RuntimeError("sensitive internal data" * 1000))
    monkeypatch.setattr(r8.observer, "observe", observe)
    result = r8.preflight()
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "observer_blocked"
    assert "sensitive" not in str(result)
    observe.assert_called_once_with()
    _assert_closed(result)
