from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    build_activation_lease_model,
)
from trading_bot.runtime.personal_desktop_d10_wake_evidence_log import (
    D10_GUARD_TERMINAL_EVIDENCE_SCHEMA,
    D10_WAKE_EVIDENCE_ROOT,
    D10GuardTerminalEvidence,
    D10GuardTerminalReason,
    D10WakeEvidenceLogError,
    d10_wake_evidence_path,
    parse_guard_terminal_evidence,
    parse_persisted_d10_wake_record,
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
    assert str(d10_wake_evidence_path(lease)).endswith(
        f"wake-{lease.soak_id}.jsonl"
    )
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
