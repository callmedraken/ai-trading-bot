import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from tests.market_data.daily_snapshot_test_support import (
    accepted_snapshot,
    calendar,
)

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    BoundMarketCalendar,
    CalendarDescriptor,
    DailySnapshotReplayError,
    DailySnapshotVerificationCode,
    DailySnapshotVerificationError,
    DailySnapshotVerificationStatus,
    SnapshotAuditEvidence,
    daily_snapshot_audit_hash,
    replay_verified_daily_snapshot,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)


def _canonical_json(tree: object) -> bytes:
    return (
        json.dumps(
            tree,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )


def test_complete_verification_passes_and_replay_preserves_exact_bars() -> None:
    snapshot = accepted_snapshot()
    payload = serialize_daily_snapshot(snapshot)
    result = verify_daily_snapshot(
        payload,
        calendar(),
        expected_sha256=__import__("hashlib").sha256(payload).hexdigest(),
        expected_byte_length=len(payload),
    )

    assert result.status is DailySnapshotVerificationStatus.PASS
    assert result.passed
    assert result.snapshot == snapshot
    replay = replay_verified_daily_snapshot(result)
    assert replay.snapshot_id == snapshot.snapshot_id
    assert replay.symbols == snapshot.request.symbols
    assert replay.bars == snapshot.bars


def test_outer_evidence_mismatches_are_distinct_and_block_replay() -> None:
    payload = serialize_daily_snapshot(accepted_snapshot())
    result = verify_daily_snapshot(
        payload,
        calendar(),
        expected_sha256="0" * 64,
        expected_byte_length=len(payload) + 1,
    )

    assert tuple(item.code for item in result.diagnostics[:2]) == (
        DailySnapshotVerificationCode.BYTE_LENGTH_MISMATCH,
        DailySnapshotVerificationCode.SHA256_MISMATCH,
    )
    with pytest.raises(DailySnapshotReplayError):
        replay_verified_daily_snapshot(result)


@pytest.mark.parametrize(
    ("field_path", "replacement", "expected_code"),
    [
        (
            ("canonical_bars", "sha256"),
            "0" * 64,
            DailySnapshotVerificationCode.CANONICAL_BARS_MISMATCH,
        ),
        (
            ("audit", "audit_sha256"),
            "0" * 64,
            DailySnapshotVerificationCode.AUDIT_HASH_MISMATCH,
        ),
        (
            ("snapshot_id",),
            "00000000-0000-5000-8000-000000000000",
            DailySnapshotVerificationCode.IDENTITY_MISMATCH,
        ),
    ],
)
def test_verifier_recomputes_hashes_and_identity(
    field_path: tuple[str, ...],
    replacement: str,
    expected_code: DailySnapshotVerificationCode,
) -> None:
    tree = json.loads(serialize_daily_snapshot(accepted_snapshot()))
    target = tree
    for part in field_path[:-1]:
        target = target[part]
    target[field_path[-1]] = replacement

    result = verify_daily_snapshot(_canonical_json(tree), calendar())

    assert result.status is DailySnapshotVerificationStatus.FAIL
    assert expected_code in {item.code for item in result.diagnostics}


def test_verifier_rejects_noncanonical_json_formatting() -> None:
    tree = json.loads(serialize_daily_snapshot(accepted_snapshot()))
    pretty = (
        json.dumps(tree, ensure_ascii=True, sort_keys=True, indent=2).encode() + b"\n"
    )

    result = verify_daily_snapshot(pretty, calendar())

    assert DailySnapshotVerificationCode.NONCANONICAL_SERIALIZATION in {
        item.code for item in result.diagnostics
    }


def test_verifier_requires_exact_calendar_descriptor() -> None:
    wrong_calendar = BoundMarketCalendar(
        CalendarDescriptor("XNYS", "other-v1", "America/New_York"),
        NYSEMarketCalendar(),
    )
    result = verify_daily_snapshot(
        serialize_daily_snapshot(accepted_snapshot()), wrong_calendar
    )

    assert tuple(item.code for item in result.diagnostics) == (
        DailySnapshotVerificationCode.CALENDAR_MISMATCH,
    )


def test_verifier_rejects_provider_as_of_before_target() -> None:
    snapshot = accepted_snapshot()
    provider_as_of = datetime(2025, 1, 3, 22, tzinfo=UTC)
    audit_hash = daily_snapshot_audit_hash(
        snapshot_id=snapshot.snapshot_id,
        requested_at=snapshot.request.requested_at,
        captured_at=snapshot.audit.captured_at,
        provider_as_of=provider_as_of,
        provider_request_id=snapshot.audit.provider_request_id,
        provider_response_symbols=snapshot.audit.provider_response_symbols,
        source_payload=snapshot.audit.source_payload,
    )
    stale_audit = SnapshotAuditEvidence(
        captured_at=snapshot.audit.captured_at,
        provider_as_of=provider_as_of,
        provider_request_id=snapshot.audit.provider_request_id,
        provider_response_symbols=snapshot.audit.provider_response_symbols,
        source_payload=snapshot.audit.source_payload,
        audit_sha256=audit_hash,
    )
    stale_snapshot = replace(snapshot, audit=stale_audit)

    result = verify_daily_snapshot(serialize_daily_snapshot(stale_snapshot), calendar())

    assert DailySnapshotVerificationCode.PROVIDER_AS_OF_MISMATCH in {
        item.code for item in result.diagnostics
    }


@pytest.mark.parametrize(
    ("sha_value", "length_value"),
    [("ABC", None), (None, True), (None, -1)],
)
def test_expected_outer_arguments_are_validated_before_verification(
    sha_value, length_value
) -> None:
    with pytest.raises(DailySnapshotVerificationError):
        verify_daily_snapshot(
            b"not opened or parsed",
            calendar(),
            expected_sha256=sha_value,
            expected_byte_length=length_value,
        )
