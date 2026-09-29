from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    build_activation_lease_model,
)
from trading_bot.runtime.personal_desktop_d10_wake_evidence_log import (
    D10_GUARD_RESULT_ACCEPT_EVIDENCE_SCHEMA,
    D10_GUARD_TERMINAL_EVIDENCE_SCHEMA,
    D10_GUARD_WAKE_START_EVIDENCE_SCHEMA,
    D10_WAKE_EVIDENCE_ROOT,
    D10GuardResultAcceptanceEvidence,
    D10GuardTerminalEvidence,
    D10GuardTerminalReason,
    D10GuardWakeStartEvidence,
    D10WakeEvidenceLogError,
    d10_wake_evidence_path,
    parse_guard_result_acceptance_evidence,
    parse_guard_terminal_evidence,
    parse_guard_wake_start_evidence,
    parse_persisted_d10_wake_record,
    summarize_d10_wake_evidence_log,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    D10OneWeekWakeEvidence,
    D10WakeOutcome,
    D10WakeStopReason,
    serialize_d10_wake_evidence,
)

NOW = datetime(2026, 9, 29, 8, 30, tzinfo=UTC)


def _lease():
    return build_activation_lease_model(
        deployment_id="11111111-1111-5111-8111-111111111111",
        attestation_sha256="a" * 64,
        accepted_activation_utc=NOW - timedelta(hours=8),
        certified_source_head="b" * 40,
        certified_source_tree="c" * 40,
    )


def _wake(lease, *, stopped=False):
    return D10OneWeekWakeEvidence(
        outcome=D10WakeOutcome.STOPPED if stopped else D10WakeOutcome.NO_ACTION,
        stop_reason=D10WakeStopReason.BLOCKED if stopped else None,
        observed_at_utc=NOW,
        deployment_id=lease.deployment_id,
        attestation_sha256=lease.attestation_sha256,
        certified_source_head=lease.certified_source_head,
        certified_source_tree=lease.certified_source_tree,
        executable_file_count=306,
        soak_id=lease.soak_id,
        activation_utc=lease.accepted_activation_utc,
        end_utc=lease.end_utc,
    )


def test_path_and_ordinary_record_round_trip():
    lease = _lease()
    assert str(D10_WAKE_EVIDENCE_ROOT) == r"F:\AITradingBot\D10\evidence"
    assert str(d10_wake_evidence_path(lease)).endswith(f"wake-{lease.soak_id}.jsonl")
    data = serialize_d10_wake_evidence(_wake(lease)).encode()
    parsed = parse_persisted_d10_wake_record(data, lease)
    assert parsed.canonical_bytes == data
    assert parsed.outcome is D10WakeOutcome.NO_ACTION


def test_stopped_and_guard_terminal_round_trip():
    lease = _lease()
    data = serialize_d10_wake_evidence(_wake(lease, stopped=True)).encode()
    parsed = parse_persisted_d10_wake_record(data, lease)
    assert parsed.outcome is D10WakeOutcome.STOPPED
    assert parsed.stop_reason is D10WakeStopReason.BLOCKED

    guard = D10GuardTerminalEvidence(
        D10_GUARD_TERMINAL_EVIDENCE_SCHEMA,
        D10GuardTerminalReason.CHILD_OUTPUT_INVALID,
        NOW,
        lease.deployment_id,
        lease.soak_id,
    )
    assert parse_guard_terminal_evidence(guard.canonical_bytes(), lease) == guard


def test_noncanonical_bytes_fail_closed():
    lease = _lease()
    data = serialize_d10_wake_evidence(_wake(lease)).encode()
    with pytest.raises(D10WakeEvidenceLogError):
        parse_persisted_d10_wake_record(data + b" ", lease)


def test_nested_wake_value_types_fail_closed():
    lease = _lease()
    data = json.loads(serialize_d10_wake_evidence(_wake(lease)))
    data["session"]["completed"] = 1
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(D10WakeEvidenceLogError, match="optional evidence type"):
        parse_persisted_d10_wake_record(payload, lease)


def _start(lease, observed=NOW - timedelta(minutes=1)):
    return D10GuardWakeStartEvidence(
        D10_GUARD_WAKE_START_EVIDENCE_SCHEMA,
        observed,
        lease.deployment_id,
        lease.soak_id,
    )


def _accept(lease, result, observed=NOW + timedelta(seconds=1)):
    return D10GuardResultAcceptanceEvidence(
        D10_GUARD_RESULT_ACCEPT_EVIDENCE_SCHEMA,
        observed,
        lease.deployment_id,
        lease.soak_id,
        hashlib.sha256(result).hexdigest(),
    )


def test_accepted_log_summary_and_incomplete_states_are_terminal():
    lease = _lease()
    start = _start(lease).canonical_bytes()
    ordinary = serialize_d10_wake_evidence(_wake(lease)).encode()

    incomplete = summarize_d10_wake_evidence_log(start + b"\n", lease)
    assert incomplete.record_count == 1
    assert incomplete.wake_count == 0
    assert incomplete.terminal is True
    assert incomplete.terminal_kind == "WAKE_STARTED_INCOMPLETE"

    unaccepted = summarize_d10_wake_evidence_log(
        start + b"\n" + ordinary + b"\n",
        lease,
    )
    assert unaccepted.record_count == 2
    assert unaccepted.wake_count == 1
    assert unaccepted.terminal is True
    assert unaccepted.terminal_kind == "WAKE_RESULT_UNACCEPTED"
    assert unaccepted.last_outcome is D10WakeOutcome.NO_ACTION

    acceptance = _accept(lease, ordinary).canonical_bytes()
    complete = summarize_d10_wake_evidence_log(
        start + b"\n" + ordinary + b"\n" + acceptance + b"\n",
        lease,
    )
    assert complete.record_count == 3
    assert complete.wake_count == 1
    assert complete.terminal is False
    assert complete.terminal_kind is None
    assert complete.last_outcome is D10WakeOutcome.NO_ACTION
    assert complete.last_observed_at_utc == NOW + timedelta(seconds=1)


def test_result_acceptance_round_trip_binds_exact_result_hash():
    lease = _lease()
    ordinary = serialize_d10_wake_evidence(_wake(lease)).encode()
    acceptance = _accept(lease, ordinary)
    data = acceptance.canonical_bytes()

    assert parse_guard_result_acceptance_evidence(data, lease, ordinary) == acceptance

    different = serialize_d10_wake_evidence(
        D10OneWeekWakeEvidence(
            outcome=D10WakeOutcome.COMPLETED,
            stop_reason=None,
            observed_at_utc=NOW,
            deployment_id=lease.deployment_id,
            attestation_sha256=lease.attestation_sha256,
            certified_source_head=lease.certified_source_head,
            certified_source_tree=lease.certified_source_tree,
            executable_file_count=306,
            soak_id=lease.soak_id,
            activation_utc=lease.accepted_activation_utc,
            end_utc=lease.end_utc,
        )
    ).encode()
    with pytest.raises(D10WakeEvidenceLogError, match="hash"):
        parse_guard_result_acceptance_evidence(data, lease, different)


def test_acceptance_cannot_appear_without_matching_nonterminal_result():
    lease = _lease()
    ordinary = serialize_d10_wake_evidence(_wake(lease)).encode()
    acceptance = _accept(lease, ordinary).canonical_bytes()

    with pytest.raises(D10WakeEvidenceLogError, match="acceptance"):
        summarize_d10_wake_evidence_log(acceptance + b"\n", lease)

    start = _start(lease).canonical_bytes()
    stopped = serialize_d10_wake_evidence(_wake(lease, stopped=True)).encode()
    with pytest.raises(D10WakeEvidenceLogError, match="terminal"):
        summarize_d10_wake_evidence_log(
            start + b"\n" + stopped + b"\n" + acceptance + b"\n",
            lease,
        )


def test_stopped_and_guard_failure_log_pairs_are_terminal():
    lease = _lease()
    start = _start(lease).canonical_bytes()
    stopped = serialize_d10_wake_evidence(_wake(lease, stopped=True)).encode()
    stopped_summary = summarize_d10_wake_evidence_log(
        start + b"\n" + stopped + b"\n", lease
    )
    assert stopped_summary.terminal is True
    assert stopped_summary.terminal_kind == "STOPPED"
    assert stopped_summary.last_stop_reason is D10WakeStopReason.BLOCKED

    terminal = D10GuardTerminalEvidence(
        D10_GUARD_TERMINAL_EVIDENCE_SCHEMA,
        D10GuardTerminalReason.CHILD_OUTPUT_INVALID,
        NOW,
        lease.deployment_id,
        lease.soak_id,
    ).canonical_bytes()
    failure_summary = summarize_d10_wake_evidence_log(
        start + b"\n" + terminal + b"\n", lease
    )
    assert failure_summary.terminal is True
    assert failure_summary.terminal_kind == "GUARD_TERMINAL"
    assert (
        failure_summary.last_guard_reason is D10GuardTerminalReason.CHILD_OUTPUT_INVALID
    )


def test_log_pairing_partial_blank_and_time_order_fail_closed():
    lease = _lease()
    start = _start(lease).canonical_bytes()
    ordinary = serialize_d10_wake_evidence(_wake(lease)).encode()

    with pytest.raises(D10WakeEvidenceLogError, match="wake-start"):
        summarize_d10_wake_evidence_log(ordinary + b"\n", lease)
    with pytest.raises(D10WakeEvidenceLogError, match="partial"):
        summarize_d10_wake_evidence_log(start, lease)
    with pytest.raises(D10WakeEvidenceLogError, match="record count"):
        summarize_d10_wake_evidence_log(start + b"\n\n", lease)

    late_start = _start(lease, NOW + timedelta(minutes=1)).canonical_bytes()
    with pytest.raises(D10WakeEvidenceLogError, match="moved backward"):
        summarize_d10_wake_evidence_log(late_start + b"\n" + ordinary + b"\n", lease)


def test_guard_start_round_trip_and_foreign_identity_rejected():
    lease = _lease()
    start = _start(lease)
    data = start.canonical_bytes()
    assert parse_guard_wake_start_evidence(data, lease) == start

    value = json.loads(data)
    value["soak_id"] = "22222222-2222-5222-8222-222222222222"
    foreign = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(D10WakeEvidenceLogError, match="identity"):
        parse_guard_wake_start_evidence(foreign, lease)
