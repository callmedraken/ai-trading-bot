"""Pure S2A policy over supplied sanitized wakes; never operational authority.

Seven wakes are a minimum only, never proof of scheduler-slot coverage.
Duplicate/restart and read-only wakes remain legitimate operator-review evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    D10OneWeekWakeEvidence,
    D10OneWeekWakeSummary,
    D10WakeOutcome,
    build_d10_one_week_wake_summary,
)

SCHEMA: Final = "d10-end-of-soak-operator-review/v1"
DEPLOYMENT_ID: Final = "d2071f25-5a7c-5293-a28f-5b722c9917a2"
ATTESTATION_SHA256: Final = (
    "3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71"
)
SOAK_ID: Final = "30e31396-9f51-57ca-a480-d2a3e9cae4a0"
ACTIVATION_UTC: Final = datetime(2026, 9, 30, 22, 7, 24, tzinfo=UTC)
END_UTC: Final = datetime(2026, 10, 7, 22, 7, 24, tzinfo=UTC)
MINIMUM_DAILY_WAKE_COUNT: Final = 7
EXTERNAL_REVIEW_REQUIRED: Final = (
    "SCHEDULER_SLOT_COVERAGE",
    "ELIGIBLE_XNYS_SESSION_COVERAGE",
    "SLEEP_REBOOT_DUPLICATE_CONTEXT",
    "PAPER_V2_ACCOUNT_TRADES_POSITIONS_PERFORMANCE",
    "AUDIT_COMPLETENESS",
)


def _blocked(reason: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "internal_wake_evidence": "BLOCKED",
        "reason": reason,
        "detail": "Supplied internal wake evidence is not ready for operator review.",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
        "external_review_required": EXTERNAL_REVIEW_REQUIRED,
    }


def _utc(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is UTC


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def analyze(
    wakes: tuple[D10OneWeekWakeEvidence, ...],
    *,
    reviewed_at_utc: datetime,
) -> dict[str, object]:
    """Assess internal evidence only; external review and operator decision remain."""
    if type(wakes) is not tuple or any(
        type(item) is not D10OneWeekWakeEvidence for item in wakes
    ):
        return _blocked("wake_input_type_invalid")
    try:
        summary: D10OneWeekWakeSummary = build_d10_one_week_wake_summary(wakes)
    except Exception:
        return _blocked("wake_summary_invalid")

    if not _utc(reviewed_at_utc):
        return _blocked("reviewed_at_utc_invalid")
    if reviewed_at_utc < END_UTC:
        return _blocked("review_window_not_complete")

    first = wakes[0]
    for wake in wakes:
        if wake.deployment_id != DEPLOYMENT_ID:
            return _blocked("deployment_mismatch")
        if wake.attestation_sha256 != ATTESTATION_SHA256:
            return _blocked("attestation_mismatch")
        if wake.soak_id != SOAK_ID:
            return _blocked("soak_mismatch")
        if not _utc(wake.activation_utc) or wake.activation_utc != ACTIVATION_UTC:
            return _blocked("activation_mismatch")
        if not _utc(wake.end_utc) or wake.end_utc != END_UTC:
            return _blocked("end_mismatch")
        if (
            type(wake.certified_source_head) is not str
            or not wake.certified_source_head
        ):
            return _blocked("source_head_invalid")
        if (
            type(wake.certified_source_tree) is not str
            or not wake.certified_source_tree
        ):
            return _blocked("source_tree_invalid")
        if (
            type(wake.executable_file_count) is not int
            or wake.executable_file_count <= 0
        ):
            return _blocked("executable_count_invalid")
        if wake.certified_source_head != first.certified_source_head:
            return _blocked("source_head_mismatch")
        if wake.certified_source_tree != first.certified_source_tree:
            return _blocked("source_tree_mismatch")
        if wake.executable_file_count != first.executable_file_count:
            return _blocked("executable_count_mismatch")
        if not _utc(wake.observed_at_utc):
            return _blocked("wake_observation_invalid")
        if not ACTIVATION_UTC <= wake.observed_at_utc < END_UTC:
            return _blocked("wake_outside_window")
        if type(wake.outcome) is not D10WakeOutcome or wake.outcome not in (
            D10WakeOutcome.COMPLETED,
            D10WakeOutcome.NO_ACTION,
        ):
            return _blocked("wake_outcome_invalid")
        if wake.stop_reason is not None:
            return _blocked("wake_stop_reason_present")
        if wake.historical_unresolved_decision_id is not None:
            return _blocked("historical_unresolved_decision_present")
        if wake.all_effect_gates_closed is not True:
            return _blocked("final_gates_not_closed")
        if type(wake.closed_effect_gate_count) is not int or (
            wake.closed_effect_gate_count != 8
        ):
            return _blocked("closed_gate_count_invalid")
        if type(wake.receipt_recovery_attempts) is not int or (
            wake.receipt_recovery_attempts != 0
        ):
            return _blocked("receipt_recovery_present")
        if type(wake.broker_live_calls) is not int or wake.broker_live_calls != 0:
            return _blocked("broker_live_calls_present")
        if any(
            type(count) is not int or count not in (0, 1)
            for count in (
                wake.provider_attempts,
                wake.settlement_attempts,
                wake.publication_attempts,
            )
        ):
            return _blocked("attempt_count_invalid")

    if summary.wake_count < MINIMUM_DAILY_WAKE_COUNT:
        return _blocked("minimum_daily_wake_count_not_met")
    if (
        summary.completed_count + summary.no_action_count != summary.wake_count
        or summary.stopped_count != 0
        or summary.stop_counts != ()
        or summary.all_effect_gates_closed is not True
    ):
        return _blocked("wake_summary_unhealthy")

    return {
        "schema": SCHEMA,
        "status": "READY_FOR_OPERATOR_REVIEW",
        "internal_wake_evidence": "PASS",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
        "wake_count": summary.wake_count,
        "completed_count": summary.completed_count,
        "no_action_count": summary.no_action_count,
        "stopped_count": summary.stopped_count,
        "provider_attempts": summary.provider_attempts,
        "settlement_attempts": summary.settlement_attempts,
        "publication_attempts": summary.publication_attempts,
        "first_observed_at_utc": _timestamp(summary.first_observed_at_utc),
        "last_observed_at_utc": _timestamp(summary.last_observed_at_utc),
        "reviewed_at_utc": _timestamp(reviewed_at_utc),
        "minimum_daily_wake_count_met": True,
        "extra_wake_count": summary.wake_count - MINIMUM_DAILY_WAKE_COUNT,
        "deployment_id": DEPLOYMENT_ID,
        "soak_id": SOAK_ID,
        "attestation_sha256": ATTESTATION_SHA256,
        "certified_source_head": first.certified_source_head,
        "certified_source_tree": first.certified_source_tree,
        "executable_file_count": first.executable_file_count,
        "external_review_required": EXTERNAL_REVIEW_REQUIRED,
    }
