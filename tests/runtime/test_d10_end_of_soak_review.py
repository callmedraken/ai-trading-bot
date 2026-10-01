"""Synthetic-only S2A policy tests; never read production evidence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from scripts import d10_end_of_soak_review as review
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    D10OneWeekWakeEvidence,
    D10WakeOutcome,
    D10WakeStopReason,
)

EXTERNAL_REVIEW = (
    "SCHEDULER_SLOT_COVERAGE",
    "ELIGIBLE_XNYS_SESSION_COVERAGE",
    "SLEEP_REBOOT_DUPLICATE_CONTEXT",
    "PAPER_V2_ACCOUNT_TRADES_POSITIONS_PERFORMANCE",
    "AUDIT_COMPLETENESS",
)


def _wakes(count: int = 7) -> tuple[D10OneWeekWakeEvidence, ...]:
    return tuple(
        D10OneWeekWakeEvidence(
            outcome=D10WakeOutcome.COMPLETED,
            stop_reason=None,
            observed_at_utc=review.ACTIVATION_UTC + timedelta(hours=index),
            deployment_id=review.DEPLOYMENT_ID,
            attestation_sha256=review.ATTESTATION_SHA256,
            soak_id=review.SOAK_ID,
            activation_utc=review.ACTIVATION_UTC,
            end_utc=review.END_UTC,
            certified_source_head="synthetic-source-head",
            certified_source_tree="synthetic-source-tree",
            executable_file_count=100,
            provider_attempts=index % 2,
            settlement_attempts=0,
            publication_attempts=0,
        )
        for index in range(count)
    )


def _assert_no_authority(result: dict[str, object]) -> None:
    assert result["schema"] == "d10-end-of-soak-operator-review/v1"
    assert result["d10_accepted"] is False
    assert result["broker_paper_authorized"] is False
    assert result["operator_decision_required"] is True
    assert result["external_review_required"] == EXTERNAL_REVIEW
    assert all(
        value is None or type(value) in (str, int, bool, tuple)
        for value in result.values()
    )


@pytest.mark.parametrize("count", (7, 8, 12))
@pytest.mark.parametrize("mixed", (False, True))
def test_healthy_wakes_are_only_ready_for_operator_review(count, mixed) -> None:
    wakes = _wakes(count)
    if mixed:
        wakes = tuple(
            replace(wake, outcome=D10WakeOutcome.NO_ACTION) if index % 2 else wake
            for index, wake in enumerate(wakes)
        )
    result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["status"] == "READY_FOR_OPERATOR_REVIEW"
    assert result["internal_wake_evidence"] == "PASS"
    assert result["wake_count"] == count
    assert result["completed_count"] + result["no_action_count"] == count
    assert result["no_action_count"] == (count // 2 if mixed else 0)
    assert result["stopped_count"] == 0
    assert result["minimum_daily_wake_count_met"] is True
    assert result["extra_wake_count"] == count - 7
    assert result["provider_attempts"] == count // 2
    assert result["settlement_attempts"] == result["publication_attempts"] == 0
    assert result["first_observed_at_utc"] == "2026-09-30T22:07:24.000000Z"
    assert result["last_observed_at_utc"] == (
        wakes[-1]
        .observed_at_utc.isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    assert result["reviewed_at_utc"] == "2026-10-07T22:07:24.000000Z"
    assert result["deployment_id"] == review.DEPLOYMENT_ID
    assert result["soak_id"] == review.SOAK_ID
    assert result["attestation_sha256"] == review.ATTESTATION_SHA256
    assert result["certified_source_head"] == "synthetic-source-head"
    assert result["certified_source_tree"] == "synthetic-source-tree"
    assert result["executable_file_count"] == 100
    assert "scheduler_slot_coverage" not in result


@pytest.mark.parametrize("count", (0, 1, 6))
def test_insufficient_wakes_block(count) -> None:
    result = review.analyze(_wakes(count), reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["status"] == "BLOCKED"


@pytest.mark.parametrize("wakes", (None, [], {}, (object(),)))
def test_exact_input_types_required(wakes, monkeypatch) -> None:
    def unexpected_summary(_):
        pytest.fail("wrong input type must not enter summary builder")

    monkeypatch.setattr(review, "build_d10_one_week_wake_summary", unexpected_summary)
    result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["reason"] == "wake_input_type_invalid"


def test_subclasses_are_not_sanitized_exact_inputs() -> None:
    class TupleSubclass(tuple):
        pass

    class WakeSubclass(D10OneWeekWakeEvidence):
        pass

    subclass = WakeSubclass(
        outcome=D10WakeOutcome.COMPLETED,
        stop_reason=None,
        observed_at_utc=review.ACTIVATION_UTC,
    )
    for wakes in (TupleSubclass(_wakes()), (subclass,)):
        result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
        _assert_no_authority(result)
        assert result["reason"] == "wake_input_type_invalid"


@pytest.mark.parametrize(
    "reviewed_at",
    (
        None,
        "2026-10-07T22:07:24Z",
        review.END_UTC.replace(tzinfo=None),
        review.END_UTC.astimezone(timezone(timedelta(hours=1))),
        review.END_UTC.replace(tzinfo=timezone(timedelta(0), "alternate UTC")),
    ),
)
def test_review_time_requires_exact_aware_utc(reviewed_at) -> None:
    result = review.analyze(_wakes(), reviewed_at_utc=reviewed_at)
    _assert_no_authority(result)
    assert result["reason"] == "reviewed_at_utc_invalid"


def test_datetime_subclass_review_time_blocks() -> None:
    class DateTimeSubclass(datetime):
        pass

    value = DateTimeSubclass(2026, 10, 7, 22, 7, 24, tzinfo=UTC)
    assert review.analyze(_wakes(), reviewed_at_utc=value)["status"] == "BLOCKED"


@pytest.mark.parametrize("delta", (-1, 0, 1))
def test_review_end_boundary(delta) -> None:
    result = review.analyze(
        _wakes(), reviewed_at_utc=review.END_UTC + timedelta(microseconds=delta)
    )
    _assert_no_authority(result)
    assert result["status"] == ("BLOCKED" if delta < 0 else "READY_FOR_OPERATOR_REVIEW")
    if delta < 0:
        assert result["reason"] == "review_window_not_complete"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("deployment_id", "foreign", "wake_summary_invalid"),
        ("attestation_sha256", "foreign", "attestation_mismatch"),
        ("soak_id", "foreign", "wake_summary_invalid"),
        (
            "activation_utc",
            review.ACTIVATION_UTC + timedelta(seconds=1),
            "activation_mismatch",
        ),
        ("end_utc", review.END_UTC + timedelta(seconds=1), "end_mismatch"),
        ("certified_source_head", "foreign", "source_head_mismatch"),
        ("certified_source_tree", "foreign", "source_tree_mismatch"),
        ("certified_source_head", None, "source_head_invalid"),
        ("certified_source_head", "", "source_head_invalid"),
        ("certified_source_tree", None, "source_tree_invalid"),
        ("certified_source_tree", "", "source_tree_invalid"),
        ("executable_file_count", 101, "executable_count_mismatch"),
        ("executable_file_count", None, "executable_count_invalid"),
        ("executable_file_count", 0, "executable_count_invalid"),
        ("executable_file_count", -1, "executable_count_invalid"),
        ("executable_file_count", True, "executable_count_invalid"),
        (
            "observed_at_utc",
            review.ACTIVATION_UTC - timedelta(microseconds=1),
            "wake_outside_window",
        ),
        (
            "historical_unresolved_decision_id",
            "synthetic-unresolved",
            "historical_unresolved_decision_present",
        ),
    ),
)
def test_provenance_and_window_block(field, value, reason) -> None:
    wakes = _wakes()
    wakes = (replace(wakes[0], **{field: value}), *wakes[1:])
    result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == reason


@pytest.mark.parametrize("field", ("deployment_id", "soak_id"))
def test_consistently_foreign_provenance_blocks(field) -> None:
    wakes = tuple(replace(wake, **{field: "foreign"}) for wake in _wakes())
    result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["reason"] == (
        "deployment_mismatch" if field == "deployment_id" else "soak_mismatch"
    )


@pytest.mark.parametrize("delta", (0, 1))
def test_observation_at_or_after_end_blocks(delta) -> None:
    wakes = _wakes()
    last = replace(
        wakes[-1], observed_at_utc=review.END_UTC + timedelta(microseconds=delta)
    )
    result = review.analyze((*wakes[:-1], last), reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["reason"] == "wake_outside_window"


def test_stopped_wake_blocks() -> None:
    wakes = _wakes()
    stopped = replace(
        wakes[-1], outcome=D10WakeOutcome.STOPPED, stop_reason=D10WakeStopReason.BLOCKED
    )
    result = review.analyze((*wakes[:-1], stopped), reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["status"] == "BLOCKED"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("stop_reason", D10WakeStopReason.BLOCKED, "wake_stop_reason_present"),
        ("outcome", "COMPLETED", "wake_outcome_invalid"),
        ("outcome", "UNKNOWN", "wake_outcome_invalid"),
        ("all_effect_gates_closed", False, "final_gates_not_closed"),
        ("all_effect_gates_closed", 1, "final_gates_not_closed"),
        ("closed_effect_gate_count", 7, "closed_gate_count_invalid"),
        ("closed_effect_gate_count", 8.0, "closed_gate_count_invalid"),
        ("receipt_recovery_attempts", 1, "receipt_recovery_present"),
        ("receipt_recovery_attempts", False, "receipt_recovery_present"),
        ("broker_live_calls", 1, "broker_live_calls_present"),
        ("broker_live_calls", False, "broker_live_calls_present"),
        ("provider_attempts", 2, "attempt_count_invalid"),
        ("settlement_attempts", -1, "attempt_count_invalid"),
        ("publication_attempts", True, "attempt_count_invalid"),
        (
            "observed_at_utc",
            review.ACTIVATION_UTC.replace(tzinfo=None),
            "wake_observation_invalid",
        ),
    ),
)
def test_independent_final_review_invariants(monkeypatch, field, value, reason) -> None:
    wakes = _wakes()
    summary = review.build_d10_one_week_wake_summary(wakes)
    # Deliberately bypass the frozen dataclass constructor in synthetic tests
    # to prove S2A checks remain independent of upstream constructor enforcement.
    object.__setattr__(wakes[0], field, value)
    monkeypatch.setattr(review, "build_d10_one_week_wake_summary", lambda _: summary)
    result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["reason"] == reason


@pytest.mark.parametrize(
    "changes",
    (
        {"completed_count": 6},
        {"stopped_count": 1},
        {"stop_counts": (("BLOCKED", 1),)},
        {"all_effect_gates_closed": False},
    ),
)
def test_unhealthy_summary_blocks(monkeypatch, changes) -> None:
    wakes = _wakes()
    summary = replace(review.build_d10_one_week_wake_summary(wakes), **changes)
    monkeypatch.setattr(review, "build_d10_one_week_wake_summary", lambda _: summary)
    result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["reason"] == "wake_summary_unhealthy"


@pytest.mark.parametrize("count", (0, 6, 7, 8, 12))
def test_existing_summary_called_exactly_once(monkeypatch, count) -> None:
    builder = review.build_d10_one_week_wake_summary
    wakes = _wakes(count)
    calls = []

    def summarize(supplied):
        calls.append(supplied)
        return builder(supplied)

    monkeypatch.setattr(review, "build_d10_one_week_wake_summary", summarize)
    result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert len(calls) == 1
    assert calls[0] is wakes


def test_summary_exception_is_bounded_without_content_leakage(monkeypatch) -> None:
    def fail(_):
        raise RuntimeError("sensitive exception content must never be copied")

    monkeypatch.setattr(review, "build_d10_one_week_wake_summary", fail)
    result = review.analyze(_wakes(), reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "wake_summary_invalid"
    assert "sensitive" not in repr(result)


@pytest.mark.parametrize("kind", ("duplicate", "unordered", "oversized"))
def test_summary_rejections_are_not_repaired(kind) -> None:
    wakes = _wakes(513) if kind == "oversized" else _wakes()
    if kind == "duplicate":
        wakes = (*wakes, wakes[-1])
    elif kind == "unordered":
        wakes = tuple(reversed(wakes))
    result = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    _assert_no_authority(result)
    assert result["reason"] == "wake_summary_invalid"


def test_analysis_is_deterministic_and_preserves_inputs() -> None:
    wakes = _wakes()
    before = repr(wakes)
    first = review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    assert first == review.analyze(wakes, reviewed_at_utc=review.END_UTC)
    assert repr(wakes) == before
