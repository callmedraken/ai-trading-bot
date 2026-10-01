"""Pure S2C2B projection of supplied Architecture-127 durable evidence bytes.

S2C2B source acceptance does not prove that supplied log_bytes came from
the production evidence file. It proves only accepted durable grammar,
lossless sanitized wake reconstruction, and accepted S2C2A XNYS coverage.
It does not prove filesystem provenance, scheduler origin, sleep/reboot
behavior, Paper-v2 state/performance, audit completeness, D10 acceptance,
or broker-paper authorization. Operator review remains required.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Final

from scripts import d10_xnys_session_coverage_policy as session_policy
from trading_bot.runtime import personal_desktop_d10_wake_evidence_log as wake_log
from trading_bot.runtime.personal_desktop_d10_activation_lease import D10ActivationLease
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    MAX_D10_WAKE_EVIDENCE_BYTES,
    D10OneWeekWakeEvidence,
)

SCHEMA: Final = "d10-xnys-session-evidence-projector/v1"
DEPLOYMENT_ID: Final = session_policy.DEPLOYMENT_ID
ATTESTATION_SHA256: Final = session_policy.ATTESTATION_SHA256
SOAK_ID: Final = session_policy.SOAK_ID
ACTIVATION_UTC: Final = session_policy.ACTIVATION_UTC
END_UTC: Final = session_policy.END_UTC

EFFECT_FIELDS: Final = (
    "production_filesystem_mutation",
    "evidence_mutation",
    "scheduler_mutation",
    "source_launch",
    "provider",
    "Paper-v2",
    "broker",
    "live",
)
_POLICY_BASE_FIELDS: Final = (
    "schema",
    "status",
    "category",
    "d10_accepted",
    "broker_paper_authorized",
    "operator_decision_required",
)
_POLICY_READY_FIELDS: Final = (
    *_POLICY_BASE_FIELDS,
    "deployment_id",
    "soak_id",
    "attestation_sha256",
    "certified_source_head",
    "certified_source_tree",
    "executable_file_count",
    "activation_utc",
    "end_utc",
    "reviewed_at_utc",
    "wake_count",
    "expected_slot_completed_sessions",
    "expected_completed_sessions",
    "covered_completed_sessions",
    "expected_execution_sessions",
    "covered_execution_sessions",
    "session_rows",
)
_POLICY_REASONS: Final = (
    "wake_input_invalid",
    "review_time_invalid",
    "review_window_not_complete",
    "expected_slot_derivation_invalid",
    "wake_identity_mismatch",
    "wake_source_identity_invalid",
    "wake_source_identity_mismatch",
    "wake_time_invalid",
    "wake_order_invalid",
    "wake_not_healthy",
    "session_field_invalid",
    "completed_session_mismatch",
    "next_execution_session_mismatch",
    "preopen_deadline_mismatch",
    "unexpected_completed_session",
    "completed_session_coverage_incomplete",
    "completed_session_order_invalid",
    "execution_session_coverage_incomplete",
    "execution_session_order_invalid",
)
_ROW_FIELDS: Final = (
    "completed_session",
    "next_execution_session",
    "preopen_deadline_utc",
    "wake_count",
    "provider_attempts",
    "settlement_attempts",
    "publication_attempts",
)


def _base(status: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": status,
        "category": "ELIGIBLE_XNYS_SESSION_COVERAGE",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
        **{field: "NOT_RUN" for field in EFFECT_FIELDS},
    }


def _blocked(reason: str) -> dict[str, object]:
    return {**_base("BLOCKED"), "reason": reason}


def _wake_deadline(value: object) -> datetime | None:
    # Projection of an already parser-accepted optional wake timestamp only.
    if value is None:
        return None
    if type(value) is not str or not value.endswith("Z"):
        raise ValueError
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if (
        type(parsed) is not datetime
        or parsed.tzinfo is not UTC
        or parsed.isoformat().replace("+00:00", "Z") != value
    ):
        raise ValueError
    return parsed


def _reconstruct(
    record: wake_log.PersistedD10WakeRecord, lease: D10ActivationLease
) -> D10OneWeekWakeEvidence:
    # Architecture 127 is the validation authority. Only accepted canonical
    # bytes are decoded here; its ordinary-record byte bound also bounds JSON.
    if type(record) is not wake_log.PersistedD10WakeRecord:
        raise ValueError
    record.__post_init__()
    if len(record.canonical_bytes) > MAX_D10_WAKE_EVIDENCE_BYTES:
        raise ValueError
    value = json.loads(record.canonical_bytes)
    return D10OneWeekWakeEvidence(
        outcome=record.outcome,
        stop_reason=record.stop_reason,
        observed_at_utc=record.observed_at_utc,
        deployment_id=lease.deployment_id,
        attestation_sha256=lease.attestation_sha256,
        certified_source_head=lease.certified_source_head,
        certified_source_tree=lease.certified_source_tree,
        executable_file_count=value["deployment"]["executable_file_count"],
        soak_id=lease.soak_id,
        activation_utc=lease.accepted_activation_utc,
        end_utc=lease.end_utc,
        completed_session=value["session"]["completed"],
        next_execution_session=value["session"]["next_execution"],
        preopen_deadline_utc=_wake_deadline(value["session"]["preopen_deadline_utc"]),
        capture_classification=value["capture"]["classification"],
        capture_selection_id=value["capture"]["selection_id"],
        capture_snapshot_id=value["capture"]["snapshot_id"],
        provider_attempt_id=value["capture"]["attempt_id"],
        provider_terminal_state=value["capture"]["terminal_state"],
        provider_call_disposition=value["capture"]["provider_call_disposition"],
        historical_audit_classification=value["history"]["classification"],
        historical_reconciled_count=value["history"]["reconciled_count"],
        historical_current_decision_id=value["history"]["current_decision_id"],
        historical_unresolved_decision_id=value["history"]["unresolved_decision_id"],
        settlement_decision_id=value["settlement"]["decision_id"],
        settlement_classification=value["settlement"]["classification"],
        settlement_reconciliation=value["settlement"]["reconciliation"],
        final_plan_id=value["settlement"]["plan_id"],
        invocation_id=value["settlement"]["invocation_id"],
        operation_id=value["settlement"]["operation_id"],
        application_id=value["settlement"]["application_id"],
        predecessor_checkpoint_id=value["settlement"]["predecessor_checkpoint_id"],
        successor_checkpoint_id=value["settlement"]["successor_checkpoint_id"],
        next_decision_id=value["decision"]["id"],
        publication_classification=value["decision"]["publication"],
        decision_reconciliation=value["decision"]["reconciliation"],
        finalized_decision_id=value["decision"]["finalized_id"],
        provider_attempts=value["budgets"]["provider_attempts"],
        settlement_attempts=value["budgets"]["settlement_attempts"],
        publication_attempts=value["budgets"]["publication_attempts"],
        receipt_recovery_attempts=value["budgets"]["receipt_recovery_attempts"],
        broker_live_calls=value["budgets"]["broker_live_calls"],
        provider_effect_crossed=value["effect_crossings"]["provider"],
        settlement_effect_crossed=value["effect_crossings"]["settlement"],
        publication_effect_crossed=value["effect_crossings"]["publication"],
        all_effect_gates_closed=value["final_gates"]["all_closed"],
        closed_effect_gate_count=value["final_gates"]["closed_count"],
    )


def _policy_timestamp(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise ValueError
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _session_text(value: object) -> bool:
    # Canonical envelope syntax only; no independent XNYS/session derivation.
    return (
        type(value) is str
        and len(value) == 10
        and date.fromisoformat(value).isoformat() == value
    )


def _policy_valid(
    value: object,
    lease: D10ActivationLease,
    wakes: tuple[D10OneWeekWakeEvidence, ...],
    reviewed_at_utc: datetime,
) -> bool:
    """Check the exact sanitized S2C2A envelope, without rerunning its policy."""
    if type(value) is not dict or any(
        type(value.get(field)) is not str for field in ("schema", "status", "category")
    ):
        return False
    if (
        value["schema"] != session_policy.SCHEMA
        or value["category"] != "ELIGIBLE_XNYS_SESSION_COVERAGE"
        or value.get("d10_accepted") is not False
        or value.get("broker_paper_authorized") is not False
        or value.get("operator_decision_required") is not True
    ):
        return False
    if value["status"] == "BLOCKED":
        return (
            set(value) == {*_POLICY_BASE_FIELDS, "reason"}
            and type(value["reason"]) is str
            and value["reason"] in _POLICY_REASONS
        )
    if value["status"] != "READY_FOR_EXTERNAL_REVIEW_ARTIFACT" or set(value) != set(
        _POLICY_READY_FIELDS
    ):
        return False
    facts = {
        "deployment_id": lease.deployment_id,
        "soak_id": lease.soak_id,
        "attestation_sha256": lease.attestation_sha256,
        "certified_source_head": lease.certified_source_head,
        "certified_source_tree": lease.certified_source_tree,
        "executable_file_count": wakes[0].executable_file_count,
        "activation_utc": _policy_timestamp(lease.accepted_activation_utc),
        "end_utc": _policy_timestamp(lease.end_utc),
        "reviewed_at_utc": _policy_timestamp(reviewed_at_utc),
        "wake_count": len(wakes),
    }
    if any(
        type(value[key]) is not type(fact) or value[key] != fact
        for key, fact in facts.items()
    ):
        return False
    for field in (
        "expected_slot_completed_sessions",
        "expected_completed_sessions",
        "covered_completed_sessions",
        "expected_execution_sessions",
        "covered_execution_sessions",
    ):
        texts = value[field]
        if (
            type(texts) is not tuple
            or not 1 <= len(texts) <= 7
            or any(not _session_text(text) for text in texts)
        ):
            return False
    if (
        len(value["expected_slot_completed_sessions"]) != 7
        or value["expected_completed_sessions"] != value["covered_completed_sessions"]
        or value["expected_execution_sessions"] != value["covered_execution_sessions"]
    ):
        return False
    rows = value["session_rows"]
    if (
        type(rows) is not tuple
        or len(rows) != len(value["expected_completed_sessions"])
        or len(rows) != len(value["expected_execution_sessions"])
    ):
        return False
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != set(_ROW_FIELDS):
            return False
        if (
            not _session_text(row["completed_session"])
            or not _session_text(row["next_execution_session"])
            or row["completed_session"] != value["expected_completed_sessions"][index]
            or row["next_execution_session"]
            != value["expected_execution_sessions"][index]
            or type(row["wake_count"]) is not int
            or not 1 <= row["wake_count"] <= len(wakes)
            or any(
                type(row[field]) is not int or not 0 <= row[field] <= row["wake_count"]
                for field in (
                    "provider_attempts",
                    "settlement_attempts",
                    "publication_attempts",
                )
            )
        ):
            return False
        timestamp = datetime.fromisoformat(row["preopen_deadline_utc"])
        if _policy_timestamp(timestamp) != row["preopen_deadline_utc"]:
            return False
    return sum(row["wake_count"] for row in rows) == len(wakes)


def project(
    log_bytes: bytes,
    lease: D10ActivationLease,
    *,
    reviewed_at_utc: datetime,
) -> dict[str, object]:
    """Project supplied bytes only; no host collection or acceptance authority."""
    if type(log_bytes) is not bytes:
        return _blocked("input_invalid")
    if type(lease) is not D10ActivationLease:
        return _blocked("lease_invalid")
    try:
        lease.__post_init__()
    except Exception:
        return _blocked("lease_invalid")
    if (
        lease.deployment_id != DEPLOYMENT_ID
        or lease.attestation_sha256 != ATTESTATION_SHA256
        or lease.soak_id != SOAK_ID
        or lease.accepted_activation_utc != ACTIVATION_UTC
        or lease.end_utc != END_UTC
    ):
        return _blocked("lease_identity_mismatch")
    # Whole-log validation precedes all extraction, once, with no fallback.
    try:
        summary = wake_log.summarize_d10_wake_evidence_log(log_bytes, lease)
    except Exception:
        return _blocked("durable_log_invalid")
    try:
        if type(summary) is not wake_log.D10WakeEvidenceLogSummary:
            raise ValueError
        summary.__post_init__()
    except Exception:
        return _blocked("durable_log_shape_invalid")
    if (
        summary.terminal is not False
        or summary.terminal_kind is not None
        or summary.last_stop_reason is not None
        or summary.last_guard_reason is not None
    ):
        return _blocked("durable_log_terminal")
    if summary.wake_count < 7:
        return _blocked("durable_log_incomplete")
    if (
        summary.record_count != summary.wake_count * 3
        or summary.record_count > wake_log.MAX_D10_EVIDENCE_LOG_RECORDS
    ):
        return _blocked("durable_log_shape_invalid")
    lines = log_bytes[:-1].split(b"\n")
    if len(lines) != summary.record_count or len(lines) != summary.wake_count * 3:
        return _blocked("durable_log_shape_invalid")
    reconstructed_wakes: list[D10OneWeekWakeEvidence] = []
    previous_time: datetime | None = None
    for offset in range(0, len(lines), 3):
        ordinary_bytes = lines[offset + 1]
        try:
            record = wake_log.parse_persisted_d10_wake_record(ordinary_bytes, lease)
        except Exception:
            return _blocked("ordinary_record_invalid")
        try:
            wake = _reconstruct(record, lease)
        except Exception:
            return _blocked("wake_projection_invalid")
        if previous_time is not None and wake.observed_at_utc < previous_time:
            return _blocked("wake_projection_order_invalid")
        previous_time = wake.observed_at_utc
        reconstructed_wakes.append(wake)
    if len(reconstructed_wakes) != summary.wake_count:
        return _blocked("wake_projection_invalid")
    try:
        policy = session_policy.analyze(
            tuple(reconstructed_wakes), reviewed_at_utc=reviewed_at_utc
        )
        if not _policy_valid(
            policy, lease, tuple(reconstructed_wakes), reviewed_at_utc
        ):
            return _blocked("xnys_session_policy_invalid")
    except Exception:
        return _blocked("xnys_session_policy_invalid")
    if policy["status"] == "BLOCKED":
        return {
            **_blocked("xnys_session_policy_blocked"),
            "policy_reason": policy["reason"],
        }
    return {
        **_base("PASS"),
        "wake_count": summary.wake_count,
        "record_count": summary.record_count,
        "input_log_byte_length": len(log_bytes),
        "input_log_sha256": hashlib.sha256(log_bytes).hexdigest(),
        "policy": policy,
    }
