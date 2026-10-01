from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from scripts import d10_xnys_session_coverage_policy as policy
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    MAX_D10_SUMMARY_WAKES,
    D10OneWeekWakeEvidence,
    D10WakeOutcome,
    D10WakeStopReason,
)

SLOT_COMPLETED = (
    "2026-09-30",
    "2026-10-01",
    "2026-10-02",
    "2026-10-02",
    "2026-10-02",
    "2026-10-05",
    "2026-10-06",
)
COMPLETED = ("2026-09-30", "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06")
EXECUTION = ("2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07")


def _wake(instant: datetime) -> D10OneWeekWakeEvidence:
    completed = policy.timing.completed_xnys_session_at(instant)
    execution = policy.timing.next_xnys_execution_session(completed)
    return D10OneWeekWakeEvidence(
        outcome=D10WakeOutcome.NO_ACTION,
        stop_reason=None,
        observed_at_utc=instant,
        deployment_id=policy.DEPLOYMENT_ID,
        attestation_sha256=policy.ATTESTATION_SHA256,
        soak_id=policy.SOAK_ID,
        activation_utc=policy.ACTIVATION_UTC,
        end_utc=policy.END_UTC,
        certified_source_head="synthetic-head",
        certified_source_tree="synthetic-tree",
        executable_file_count=300,
        completed_session=completed.session_date.isoformat(),
        next_execution_session=execution.session_date.isoformat(),
        preopen_deadline_utc=policy.timing.xnys_regular_open(execution),
    )


def _wakes() -> tuple[D10OneWeekWakeEvidence, ...]:
    return tuple(_wake(slot) for slot in policy.slot_policy.expected_slots_utc())


def _changed(wakes=None, *, index=0, **fields):
    # Invalid fixtures deliberately bypass the accepted frozen model constructor.
    values = list(_wakes() if wakes is None else wakes)
    wake = replace(values[index])
    for name, value in fields.items():
        object.__setattr__(wake, name, value)
    values[index] = wake
    return tuple(values)


def _analyze(wakes=None, reviewed=policy.END_UTC):
    return policy.analyze(
        _wakes() if wakes is None else wakes, reviewed_at_utc=reviewed
    )


def _blocked(wakes, reason, *, reviewed=policy.END_UTC):
    result = _analyze(wakes, reviewed)
    assert result == {
        "schema": "d10-xnys-session-coverage-review/v1",
        "status": "BLOCKED",
        "reason": reason,
        "category": "ELIGIBLE_XNYS_SESSION_COVERAGE",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }


def test_canonical_seven_wakes_complete_derived_coverage():
    result = _analyze()
    assert result["status"] == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"
    assert result["expected_slot_completed_sessions"] == SLOT_COMPLETED
    assert result["expected_completed_sessions"] == COMPLETED
    assert result["covered_completed_sessions"] == COMPLETED
    assert result["expected_execution_sessions"] == EXECUTION
    assert result["covered_execution_sessions"] == EXECUTION
    assert result["wake_count"] == 7
    assert result["deployment_id"] == policy.DEPLOYMENT_ID
    assert result["soak_id"] == policy.SOAK_ID
    assert result["attestation_sha256"] == policy.ATTESTATION_SHA256
    assert result["certified_source_head"] == "synthetic-head"
    assert result["certified_source_tree"] == "synthetic-tree"
    assert result["executable_file_count"] == 300
    assert result["activation_utc"] == "2026-09-30T22:07:24.000000Z"
    assert result["end_utc"] == "2026-10-07T22:07:24.000000Z"
    assert result["reviewed_at_utc"] == result["end_utc"]
    rows = result["session_rows"]
    assert tuple(row["wake_count"] for row in rows) == (1, 1, 3, 1, 1)
    assert rows[-1]["next_execution_session"] == "2026-10-07"
    assert rows[-1]["preopen_deadline_utc"] == "2026-10-07T13:30:00.000000Z"
    assert all(
        set(row)
        == {
            "completed_session",
            "next_execution_session",
            "preopen_deadline_utc",
            "wake_count",
            "provider_attempts",
            "settlement_attempts",
            "publication_attempts",
        }
        for row in rows
    )
    assert result["d10_accepted"] is False
    assert result["broker_paper_authorized"] is False
    assert result["operator_decision_required"] is True
    assert not {
        "profitability",
        "profitable",
        "winner",
        "score",
        "recommendation",
    } & set(result)
    assert _analyze() == result


def test_uses_accepted_slots_and_timing_functions(monkeypatch):
    wakes = _wakes()
    calls = []
    slots = policy.slot_policy.expected_slots_utc
    monkeypatch.setattr(
        policy.slot_policy,
        "expected_slots_utc",
        lambda: (calls.append("slots"), slots())[1],
    )
    for name in (
        "completed_xnys_session_at",
        "next_xnys_execution_session",
        "xnys_regular_open",
    ):
        original = getattr(policy.timing, name)

        def wrapped(value, name=name, original=original):
            calls.append((name, value))
            return original(value)

        monkeypatch.setattr(policy.timing, name, wrapped)
    assert _analyze(wakes)["status"] == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"
    assert calls.count("slots") == 1
    assert (
        sum(
            isinstance(call, tuple) and call[0] == "completed_xnys_session_at"
            for call in calls
        )
        == 14
    )
    assert (
        sum(
            isinstance(call, tuple) and call[0] == "next_xnys_execution_session"
            for call in calls
        )
        == 12
    )
    assert (
        sum(
            isinstance(call, tuple) and call[0] == "xnys_regular_open" for call in calls
        )
        == 12
    )


@pytest.mark.parametrize("count", (8, 12, MAX_D10_SUMMARY_WAKES))
def test_additional_duplicate_restart_wakes_allowed(count):
    wakes = _wakes()
    expanded = (*wakes[:3], *((wakes[2],) * (count - 7)), *wakes[3:])
    result = _analyze(expanded)
    assert result["status"] == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"
    assert result["wake_count"] == count
    assert result["session_rows"][2]["wake_count"] == count - 4


@pytest.mark.parametrize(
    "value", ((), _wakes()[:6], list(_wakes()), (None,) * 7, ({},) * 7, _wakes() * 74)
)
def test_input_shape_and_bound(value):
    _blocked(value, "wake_input_invalid")


def test_subclass_wake_rejected():
    class SubWake(D10OneWeekWakeEvidence):
        pass

    wake = _wakes()[0]
    subclass = SubWake(
        **{field: getattr(wake, field) for field in wake.__dataclass_fields__}
    )
    _blocked((subclass, *_wakes()[1:]), "wake_input_invalid")


@pytest.mark.parametrize(
    "reviewed",
    (
        None,
        "2026-10-08",
        policy.END_UTC.replace(tzinfo=None),
        policy.END_UTC.replace(tzinfo=timezone(timedelta(0), "OtherUTC")),
    ),
)
def test_invalid_review_time(reviewed):
    _blocked(_wakes(), "review_time_invalid", reviewed=reviewed)


def test_exact_datetime_review_time():
    class SubDatetime(datetime):
        pass

    _blocked(
        _wakes(), "review_time_invalid", reviewed=SubDatetime(2026, 10, 8, tzinfo=UTC)
    )


def test_review_window_not_complete():
    _blocked(
        _wakes(),
        "review_window_not_complete",
        reviewed=policy.END_UTC - timedelta(microseconds=1),
    )


@pytest.mark.parametrize(
    "reviewed", (policy.END_UTC, policy.END_UTC + timedelta(days=3))
)
def test_review_at_or_after_end_allowed(reviewed):
    assert _analyze(reviewed=reviewed)["status"] == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("outcome", D10WakeOutcome.STOPPED),
        ("outcome", "NO_ACTION"),
        ("stop_reason", D10WakeStopReason.BLOCKED),
        ("all_effect_gates_closed", False),
        ("all_effect_gates_closed", 1),
        ("closed_effect_gate_count", 7),
        ("closed_effect_gate_count", 8.0),
        ("receipt_recovery_attempts", 1),
        ("receipt_recovery_attempts", False),
        ("broker_live_calls", 1),
        ("broker_live_calls", False),
        ("provider_attempts", 2),
        ("settlement_attempts", -1),
        ("publication_attempts", True),
    ),
)
def test_healthy_wake_required(field, value):
    _blocked(_changed(**{field: value}), "wake_not_healthy")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("deployment_id", "foreign"),
        ("attestation_sha256", "foreign"),
        ("soak_id", "foreign"),
        ("activation_utc", policy.ACTIVATION_UTC - timedelta(seconds=1)),
        ("end_utc", policy.END_UTC + timedelta(seconds=1)),
        ("activation_utc", policy.ACTIVATION_UTC.replace(tzinfo=None)),
        ("end_utc", None),
    ),
)
def test_exact_identity_required(field, value):
    _blocked(_changed(**{field: value}), "wake_identity_mismatch")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("certified_source_head", None),
        ("certified_source_head", ""),
        ("certified_source_head", 123),
        ("certified_source_tree", None),
        ("certified_source_tree", ""),
        ("executable_file_count", None),
        ("executable_file_count", 0),
        ("executable_file_count", -1),
        ("executable_file_count", True),
        ("executable_file_count", 300.0),
    ),
)
def test_invalid_source_facts(field, value):
    _blocked(_changed(**{field: value}), "wake_source_identity_invalid")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("certified_source_head", "other-head"),
        ("certified_source_tree", "other-tree"),
        ("executable_file_count", 301),
    ),
)
def test_source_facts_must_agree(field, value):
    _blocked(_changed(index=1, **{field: value}), "wake_source_identity_mismatch")


@pytest.mark.parametrize(
    "instant",
    (
        None,
        policy.ACTIVATION_UTC - timedelta(microseconds=1),
        policy.END_UTC,
        policy.END_UTC + timedelta(seconds=1),
        policy.ACTIVATION_UTC.replace(tzinfo=None),
        policy.ACTIVATION_UTC.replace(tzinfo=timezone(timedelta(hours=1))),
    ),
)
def test_observation_time_required_and_half_open(instant):
    _blocked(_changed(observed_at_utc=instant), "wake_time_invalid")


def test_input_order_preserved():
    wakes = _wakes()
    _blocked((wakes[1], wakes[0], *wakes[2:]), "wake_order_invalid")


@pytest.mark.parametrize("field", ("completed_session", "next_execution_session"))
@pytest.mark.parametrize(
    "value",
    (
        None,
        "",
        "2026-9-30",
        "2026-09-3",
        "20260930",
        "2026-W40-3",
        "2026-09-30T00:00:00",
        "2026-09-30Z",
        "2026-09-30+00:00",
        "2026-02-30",
        "label",
        "２０２６-０９-３０",
        123,
    ),
)
def test_strict_canonical_session_parser(field, value):
    _blocked(_changed(**{field: value}), "session_field_invalid")


def test_session_parser_returns_exact_model_and_rejects_subclass_text():
    class SubString(str):
        pass

    session = policy._session("2026-09-30")
    assert type(session) is TradingSession
    assert session.session_date == date(2026, 9, 30)
    assert policy._session(SubString("2026-09-30")) is None


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("completed_session", "2026-09-29", "completed_session_mismatch"),
        ("next_execution_session", "2026-10-02", "next_execution_session_mismatch"),
        ("next_execution_session", "2026-10-03", "next_execution_session_mismatch"),
        ("preopen_deadline_utc", None, "preopen_deadline_mismatch"),
        (
            "preopen_deadline_utc",
            datetime(2026, 10, 1, 13, 30),
            "preopen_deadline_mismatch",
        ),
        (
            "preopen_deadline_utc",
            datetime(2026, 10, 1, 13, 30, tzinfo=timezone(timedelta(0), "OtherUTC")),
            "preopen_deadline_mismatch",
        ),
        (
            "preopen_deadline_utc",
            datetime(2026, 10, 1, 13, 30, 0, 1, tzinfo=UTC),
            "preopen_deadline_mismatch",
        ),
    ),
)
def test_exact_session_chain_required(field, value, reason):
    _blocked(_changed(**{field: value}), reason)


def test_one_expected_completed_session_missing():
    wakes = _wakes()
    # Seven valid wakes; skip Oct. 1 completed session and add a weekend duplicate.
    _blocked(
        (wakes[0], *wakes[2:5], wakes[4], *wakes[5:]),
        "completed_session_coverage_incomplete",
    )


def test_unexpected_source_correct_completed_session_not_ignored():
    # A wake at activation precedes the first scheduler slot. Its accepted
    # completed-session derivation is outside the slot-implied expected set.
    foreign = _wake(policy.ACTIVATION_UTC)
    assert foreign.completed_session == "2026-09-29"
    _blocked((foreign, *_wakes()), "unexpected_completed_session")


@pytest.mark.parametrize("prefix", ("completed_session", "execution_session"))
def test_coverage_defenses_distinguish_missing_and_first_seen_order(prefix):
    # Real monotone timing and the per-wake chain also reject these conditions
    # earlier; isolate the final coverage defense without inventing calendar rules.
    assert policy._coverage_reason(("a", "b"), ("a", "b"), prefix) is None
    assert (
        policy._coverage_reason(("a",), ("a", "b"), prefix)
        == prefix + "_coverage_incomplete"
    )
    assert (
        policy._coverage_reason(("b", "a"), ("a", "b"), prefix)
        == prefix + "_order_invalid"
    )


@pytest.mark.parametrize(
    ("position", "replacement", "reason"),
    (
        (1, tuple(reversed(COMPLETED)), "completed_session_order_invalid"),
        (2, EXECUTION[:-1], "execution_session_coverage_incomplete"),
        (2, tuple(reversed(EXECUTION)), "execution_session_order_invalid"),
    ),
)
def test_analysis_final_coverage_defenses(monkeypatch, position, replacement, reason):
    wakes = _wakes()
    expected = list(policy._expected_coverage())
    expected[position] = replacement
    monkeypatch.setattr(policy, "_expected_coverage", lambda: tuple(expected))
    _blocked(wakes, reason)


@pytest.mark.parametrize(
    "zero_field", ("provider_attempts", "settlement_attempts", "publication_attempts")
)
def test_zero_attempts_are_facts_never_thresholds(zero_field):
    wakes = _wakes()
    fields = {
        name: int(name != zero_field)
        for name in ("provider_attempts", "settlement_attempts", "publication_attempts")
    }
    wakes = tuple(replace(wake, **fields) for wake in wakes)
    result = _analyze(wakes)
    assert result["status"] == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"
    for row in result["session_rows"]:
        assert row[zero_field] == 0
        for field in fields:
            assert row[field] == fields[field] * row["wake_count"]


@pytest.mark.parametrize(
    "outcome", (D10WakeOutcome.COMPLETED, D10WakeOutcome.NO_ACTION)
)
def test_both_healthy_outcomes_allowed(outcome):
    result = _analyze(tuple(replace(wake, outcome=outcome) for wake in _wakes()))
    assert result["status"] == "READY_FOR_EXTERNAL_REVIEW_ARTIFACT"


@pytest.mark.parametrize(
    "slots",
    (
        None,
        [],
        (),
        policy.slot_policy.expected_slots_utc()[:6],
        (*policy.slot_policy.expected_slots_utc(), policy.END_UTC),
        tuple(reversed(policy.slot_policy.expected_slots_utc())),
        (policy.ACTIVATION_UTC.replace(tzinfo=None),) * 7,
        (policy.END_UTC,) * 7,
    ),
)
def test_invalid_seven_slot_derivation_blocks(monkeypatch, slots):
    wakes = _wakes()
    monkeypatch.setattr(policy.slot_policy, "expected_slots_utc", lambda: slots)
    _blocked(wakes, "expected_slot_derivation_invalid")


@pytest.mark.parametrize(
    "function",
    ("completed_xnys_session_at", "next_xnys_execution_session", "xnys_regular_open"),
)
@pytest.mark.parametrize("failure", ("exception", "wrong_type"))
def test_expected_timing_derivation_fails_closed(monkeypatch, function, failure):
    wakes = _wakes()

    def invalid(_):
        if failure == "exception":
            raise ValueError("unbounded private exception detail")
        return None

    monkeypatch.setattr(policy.timing, function, invalid)
    _blocked(wakes, "expected_slot_derivation_invalid")


@pytest.mark.parametrize(
    ("function", "reason"),
    (
        ("completed_xnys_session_at", "completed_session_mismatch"),
        ("next_xnys_execution_session", "next_execution_session_mismatch"),
        ("xnys_regular_open", "preopen_deadline_mismatch"),
    ),
)
@pytest.mark.parametrize("failure", ("exception", "wrong_type"))
def test_per_wake_timing_derivation_fails_closed(
    monkeypatch, function, reason, failure
):
    wakes = _wakes()
    expected = policy._expected_coverage()
    monkeypatch.setattr(policy, "_expected_coverage", lambda: expected)

    def invalid(_):
        if failure == "exception":
            raise ValueError("private exception text")
        return None

    monkeypatch.setattr(policy.timing, function, invalid)
    _blocked(wakes, reason)


def test_revalidates_other_bounded_model_fields():
    _blocked(_changed(provider_effect_crossed=True), "wake_input_invalid")


def test_slot_derivation_exception_has_bounded_reason(monkeypatch):
    wakes = _wakes()

    def invalid():
        raise RuntimeError("private transport detail")

    monkeypatch.setattr(policy.slot_policy, "expected_slots_utc", invalid)
    _blocked(wakes, "expected_slot_derivation_invalid")
