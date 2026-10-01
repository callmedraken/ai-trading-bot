"""Pure S2C2A review of supplied sanitized XNYS session/timing coverage.

READY proves only complete source-owned XNYS session/timing coverage of the
supplied sanitized wakes. It does not prove durable-file collector truth,
scheduler-origin truth, Paper-v2 correctness, profitability, audit completeness,
sleep/reboot correctness, D10 acceptance, or broker-paper readiness.
No historical catch-up, retry, repair, or operational authority is granted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Final

from scripts import d10_end_of_soak_review as internal_review_policy
from scripts import d10_scheduler_slot_review_policy as slot_policy
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import personal_desktop_unattended_daily_cycle_timing as timing
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    MAX_D10_SUMMARY_WAKES,
    D10OneWeekWakeEvidence,
    D10WakeOutcome,
)

SCHEMA: Final = "d10-xnys-session-coverage-review/v1"
DEPLOYMENT_ID: Final = internal_review_policy.DEPLOYMENT_ID
ATTESTATION_SHA256: Final = internal_review_policy.ATTESTATION_SHA256
SOAK_ID: Final = internal_review_policy.SOAK_ID
ACTIVATION_UTC: Final = internal_review_policy.ACTIVATION_UTC
END_UTC: Final = internal_review_policy.END_UTC


def _blocked(reason: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "reason": reason,
        "category": "ELIGIBLE_XNYS_SESSION_COVERAGE",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }


def _utc(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is UTC


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _session(value: object) -> TradingSession | None:
    if type(value) is not str or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            return None
        return TradingSession(parsed)
    except ValueError:
        return None


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    # Preserve first appearance, including the legitimate repeated weekend session.
    return tuple(dict.fromkeys(values))


def _coverage_reason(
    covered: tuple[str, ...], expected: tuple[str, ...], prefix: str
) -> str | None:
    if set(covered) != set(expected):
        return prefix + "_coverage_incomplete"
    if covered != expected:
        return prefix + "_order_invalid"
    return None


def _expected_coverage() -> (
    tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[datetime, ...]]
    | None
):
    try:
        slots = slot_policy.expected_slots_utc()
        if (
            type(slots) is not tuple
            or len(slots) != 7
            or any(not _utc(slot) for slot in slots)
            or any(not ACTIVATION_UTC <= slot < END_UTC for slot in slots)
            or any(a >= b for a, b in zip(slots, slots[1:], strict=False))
        ):
            return None
        completed = tuple(timing.completed_xnys_session_at(slot) for slot in slots)
        if any(type(session) is not TradingSession for session in completed):
            return None
        slot_completed = tuple(
            session.session_date.isoformat() for session in completed
        )
        unique_completed = _unique(slot_completed)
        executions: list[str] = []
        deadlines: list[datetime] = []
        for text in unique_completed:
            session = _session(text)
            if session is None:
                return None
            execution = timing.next_xnys_execution_session(session)
            if type(execution) is not TradingSession:
                return None
            deadline = timing.xnys_regular_open(execution)
            if not _utc(deadline):
                return None
            executions.append(execution.session_date.isoformat())
            deadlines.append(deadline)
        return slot_completed, unique_completed, tuple(executions), tuple(deadlines)
    except Exception:
        return None


def analyze(
    wakes: tuple[D10OneWeekWakeEvidence, ...],
    *,
    reviewed_at_utc: datetime,
) -> dict[str, object]:
    """Review supplied facts only; collection and operator acceptance are separate."""
    if (
        type(wakes) is not tuple
        or not 7 <= len(wakes) <= MAX_D10_SUMMARY_WAKES
        or any(type(wake) is not D10OneWeekWakeEvidence for wake in wakes)
    ):
        return _blocked("wake_input_invalid")
    if not _utc(reviewed_at_utc):
        return _blocked("review_time_invalid")
    if reviewed_at_utc < END_UTC:
        return _blocked("review_window_not_complete")
    expected = _expected_coverage()
    if expected is None:
        return _blocked("expected_slot_derivation_invalid")
    slot_completed, expected_completed, expected_execution, deadlines = expected
    completed_texts: list[str] = []
    execution_texts: list[str] = []
    first = wakes[0]
    previous_time: datetime | None = None
    for wake in wakes:
        if (
            type(wake.deployment_id) is not str
            or wake.deployment_id != DEPLOYMENT_ID
            or type(wake.attestation_sha256) is not str
            or wake.attestation_sha256 != ATTESTATION_SHA256
            or type(wake.soak_id) is not str
            or wake.soak_id != SOAK_ID
            or not _utc(wake.activation_utc)
            or wake.activation_utc != ACTIVATION_UTC
            or not _utc(wake.end_utc)
            or wake.end_utc != END_UTC
        ):
            return _blocked("wake_identity_mismatch")
        if (
            type(wake.certified_source_head) is not str
            or not wake.certified_source_head
            or type(wake.certified_source_tree) is not str
            or not wake.certified_source_tree
            or type(wake.executable_file_count) is not int
            or wake.executable_file_count <= 0
        ):
            return _blocked("wake_source_identity_invalid")
        if (
            wake.certified_source_head != first.certified_source_head
            or wake.certified_source_tree != first.certified_source_tree
            or wake.executable_file_count != first.executable_file_count
        ):
            return _blocked("wake_source_identity_mismatch")
        if not _utc(wake.observed_at_utc) or not (
            ACTIVATION_UTC <= wake.observed_at_utc < END_UTC
        ):
            return _blocked("wake_time_invalid")
        if previous_time is not None and wake.observed_at_utc < previous_time:
            return _blocked("wake_order_invalid")
        previous_time = wake.observed_at_utc
        if (
            type(wake.outcome) is not D10WakeOutcome
            or wake.outcome not in (D10WakeOutcome.COMPLETED, D10WakeOutcome.NO_ACTION)
            or wake.stop_reason is not None
            or wake.all_effect_gates_closed is not True
            or type(wake.closed_effect_gate_count) is not int
            or wake.closed_effect_gate_count != 8
            or type(wake.receipt_recovery_attempts) is not int
            or wake.receipt_recovery_attempts != 0
            or type(wake.broker_live_calls) is not int
            or wake.broker_live_calls != 0
            or any(
                type(count) is not int or count not in (0, 1)
                for count in (
                    wake.provider_attempts,
                    wake.settlement_attempts,
                    wake.publication_attempts,
                )
            )
        ):
            return _blocked("wake_not_healthy")
        completed_session = _session(wake.completed_session)
        execution_session = _session(wake.next_execution_session)
        if completed_session is None or execution_session is None:
            return _blocked("session_field_invalid")
        try:
            expected_session = timing.completed_xnys_session_at(wake.observed_at_utc)
            if type(expected_session) is not TradingSession or (
                completed_session != expected_session
            ):
                return _blocked("completed_session_mismatch")
        except Exception:
            return _blocked("completed_session_mismatch")
        try:
            expected_next = timing.next_xnys_execution_session(expected_session)
            if type(expected_next) is not TradingSession or (
                execution_session != expected_next
            ):
                return _blocked("next_execution_session_mismatch")
        except Exception:
            return _blocked("next_execution_session_mismatch")
        try:
            expected_deadline = timing.xnys_regular_open(expected_next)
            if (
                not _utc(expected_deadline)
                or not _utc(wake.preopen_deadline_utc)
                or wake.preopen_deadline_utc != expected_deadline
            ):
                return _blocked("preopen_deadline_mismatch")
        except Exception:
            return _blocked("preopen_deadline_mismatch")
        # Revalidate bounded sanitized model invariants even after unsafe mutation.
        try:
            wake.__post_init__()
        except Exception:
            return _blocked("wake_input_invalid")
        if wake.completed_session not in expected_completed:
            return _blocked("unexpected_completed_session")
        completed_texts.append(wake.completed_session)
        execution_texts.append(wake.next_execution_session)
    covered_completed = _unique(tuple(completed_texts))
    covered_execution = _unique(tuple(execution_texts))
    reason = _coverage_reason(
        covered_completed, expected_completed, "completed_session"
    )
    if reason is not None:
        return _blocked(reason)
    reason = _coverage_reason(
        covered_execution, expected_execution, "execution_session"
    )
    if reason is not None:
        return _blocked(reason)
    rows: list[dict[str, object]] = []
    for completed, execution, deadline in zip(
        expected_completed, expected_execution, deadlines, strict=True
    ):
        matching = tuple(wake for wake in wakes if wake.completed_session == completed)
        rows.append(
            {
                "completed_session": completed,
                "next_execution_session": execution,
                "preopen_deadline_utc": _timestamp(deadline),
                "wake_count": len(matching),
                "provider_attempts": sum(wake.provider_attempts for wake in matching),
                "settlement_attempts": sum(
                    wake.settlement_attempts for wake in matching
                ),
                "publication_attempts": sum(
                    wake.publication_attempts for wake in matching
                ),
            }
        )
    return {
        "schema": SCHEMA,
        "status": "READY_FOR_EXTERNAL_REVIEW_ARTIFACT",
        "category": "ELIGIBLE_XNYS_SESSION_COVERAGE",
        "deployment_id": DEPLOYMENT_ID,
        "soak_id": SOAK_ID,
        "attestation_sha256": ATTESTATION_SHA256,
        "certified_source_head": first.certified_source_head,
        "certified_source_tree": first.certified_source_tree,
        "executable_file_count": first.executable_file_count,
        "activation_utc": _timestamp(ACTIVATION_UTC),
        "end_utc": _timestamp(END_UTC),
        "reviewed_at_utc": _timestamp(reviewed_at_utc),
        "wake_count": len(wakes),
        "expected_slot_completed_sessions": slot_completed,
        "expected_completed_sessions": expected_completed,
        "covered_completed_sessions": covered_completed,
        "expected_execution_sessions": expected_execution,
        "covered_execution_sessions": covered_execution,
        "session_rows": tuple(rows),
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }
