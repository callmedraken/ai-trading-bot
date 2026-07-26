from datetime import timedelta
from decimal import Decimal, localcontext
from hashlib import sha256

from tests.market_data.daily_snapshot_test_support import (
    QQQ,
    SPY,
    accepted_result,
    accepted_snapshot,
    candidate,
)

from trading_bot.market_data import (
    ProviderDescriptor,
    SourcePayloadEvidence,
    canonical_bar_material,
    canonical_decimal,
    canonical_scalar,
    daily_snapshot_audit_hash,
    daily_snapshot_id,
    snapshot_audit_material,
    snapshot_identity_material,
)

EXPECTED_BAR_MATERIAL = (
    "29:daily-market-snapshot-bars-v1"
    "1:0"
    "3:SPY"
    "10:2025-01-06"
    "20:2025-01-06T05:00:00Z"
    "3:100"
    "5:103.5"
    "5:99.25"
    "6:102.75"
    "4:1000"
    "1:1"
    "3:QQQ"
    "10:2025-01-06"
    "20:2025-01-06T05:00:00Z"
    "3:200"
    "3:205"
    "3:198"
    "3:203"
    "4:2000"
)
EXPECTED_IDENTITY_MATERIAL = (
    "33:daily-market-snapshot-identity-v1"
    "36:98dbdaca-e14b-5f10-8ca9-3650e18aa1d8"
    "4:XNYS"
    "34:nyse-regular-sessions-1998-2100-v1"
    "16:America/New_York"
    "10:2025-01-06"
    "2:1D"
    "3:RAW"
    "13:test-provider"
    "1:1"
    "10:daily-bars"
    "9:test-feed"
    "1:2"
    "3:SPY"
    "3:QQQ"
    "179:" + EXPECTED_BAR_MATERIAL
)
EXPECTED_AUDIT_MATERIAL = (
    "30:daily-market-snapshot-audit-v1"
    "36:c9d2e055-80fe-52b7-ae3f-56c26b76f736"
    "20:2025-01-07T18:00:00Z"
    "20:2025-01-07T18:00:01Z"
    "6:<none>"
    "17:remote-request-17"
    "64:2c6c212d290a0774fb147d4df27c860e47bf4c6c420638362202963cf588aaed"
    "2:36"
    "16:application/json"
    "1:2"
    "1:0"
    "3:QQQ"
    "1:1"
    "3:SPY"
)


def test_canonical_scalar_and_decimal_golden_vectors() -> None:
    assert canonical_scalar("SPY") == "3:SPY"
    values = (
        Decimal("0"),
        Decimal("-0.000"),
        Decimal("1.2300"),
        Decimal("1E+3"),
        Decimal("0.00100"),
    )
    expected = ("0", "0", "1.23", "1000", "0.001")

    with localcontext() as context:
        context.prec = 3
        context.Emax = 3
        assert tuple(canonical_decimal(value) for value in values) == expected


def test_canonical_material_hash_and_uuid5_golden_vectors() -> None:
    snapshot = accepted_snapshot()

    assert canonical_bar_material(snapshot.bars) == EXPECTED_BAR_MATERIAL
    assert snapshot.canonical_bars.byte_length == 179
    assert (
        snapshot.canonical_bars.sha256
        == "d4d223567d47cb9f3962864d79589c471901834f1a706c8752ce549feb60c4b3"
    )
    assert (
        snapshot_identity_material(
            snapshot.request,
            snapshot.target_session,
            snapshot.provider,
            snapshot.bars,
        )
        == EXPECTED_IDENTITY_MATERIAL
    )
    assert (
        daily_snapshot_id(
            snapshot.request,
            snapshot.target_session,
            snapshot.provider,
            snapshot.bars,
        )
        == snapshot.snapshot_id
    )
    assert str(snapshot.snapshot_id) == "c9d2e055-80fe-52b7-ae3f-56c26b76f736"


def test_audit_material_and_hash_golden_vectors() -> None:
    snapshot = accepted_snapshot()
    arguments = {
        "snapshot_id": snapshot.snapshot_id,
        "requested_at": snapshot.request.requested_at,
        "captured_at": snapshot.audit.captured_at,
        "provider_as_of": snapshot.audit.provider_as_of,
        "provider_request_id": snapshot.audit.provider_request_id,
        "provider_response_symbols": snapshot.audit.provider_response_symbols,
        "source_payload": snapshot.audit.source_payload,
    }

    assert snapshot_audit_material(**arguments) == EXPECTED_AUDIT_MATERIAL
    assert (
        daily_snapshot_audit_hash(**arguments)
        == "7b3159a939ac43d0b8756d29da98df974fb4bb313782072671c329ef48ee8506"
    )


def test_identity_excludes_clocks_remote_id_and_source_payload_evidence() -> None:
    original = accepted_snapshot()
    changed_payload = b"changed deterministic fake evidence"
    changed_result = accepted_result(
        captured_at=original.audit.captured_at + timedelta(seconds=17),
        provider_request_id="different-remote-id",
        source_payload=SourcePayloadEvidence(
            sha256=sha256(changed_payload).hexdigest(),
            byte_length=len(changed_payload),
            media_type="application/json",
        ),
    )
    assert changed_result.snapshot is not None
    changed = changed_result.snapshot

    assert changed.snapshot_id == original.snapshot_id
    assert changed.canonical_bars == original.canonical_bars
    assert changed.audit.audit_sha256 != original.audit.audit_sha256


def test_provider_response_order_changes_only_audit_evidence() -> None:
    original = accepted_snapshot()
    reordered_result = accepted_result(
        candidates=(
            candidate(SPY, 0),
            candidate(
                QQQ,
                1,
                open_price=Decimal("200"),
                high=Decimal("205"),
                low=Decimal("198"),
                close=Decimal("203"),
                volume=2_000,
            ),
        )
    )
    assert reordered_result.snapshot is not None
    reordered = reordered_result.snapshot

    assert reordered.snapshot_id == original.snapshot_id
    assert reordered.bars == original.bars
    assert reordered.audit.provider_response_symbols == (SPY, QQQ)
    assert reordered.audit.audit_sha256 != original.audit.audit_sha256


def test_provider_feed_is_bound_into_snapshot_identity() -> None:
    snapshot = accepted_snapshot()
    changed_provider = ProviderDescriptor(
        snapshot.provider.provider_id,
        snapshot.provider.adapter_version,
        snapshot.provider.operation,
        "different-feed",
    )

    assert daily_snapshot_id(
        snapshot.request,
        snapshot.target_session,
        changed_provider,
        snapshot.bars,
    ) != daily_snapshot_id(
        snapshot.request,
        snapshot.target_session,
        snapshot.provider,
        snapshot.bars,
    )
