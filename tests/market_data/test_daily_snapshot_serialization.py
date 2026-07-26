import json
from hashlib import sha256

import pytest
from tests.market_data.daily_snapshot_test_support import accepted_snapshot

from trading_bot.market_data import (
    DailySnapshotSerializationError,
    parse_daily_snapshot,
    serialize_daily_snapshot,
)


def test_canonical_serialization_has_golden_length_sha256_and_round_trip() -> None:
    snapshot = accepted_snapshot()
    payload = serialize_daily_snapshot(snapshot)

    assert len(payload) == 1375
    assert (
        sha256(payload).hexdigest()
        == "e877b28f29cc4355efdd6e32f1183faf5c64970ffc7eec898caced75de077b2d"
    )
    assert payload.endswith(b"\n")
    assert not payload.endswith(b"\n\n")
    assert parse_daily_snapshot(payload) == snapshot
    assert serialize_daily_snapshot(parse_daily_snapshot(payload)) == payload


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: b"\xef\xbb\xbf" + payload,
        lambda payload: payload[:-1] + b"\xff\n",
        lambda payload: payload + b"\n",
        lambda payload: payload[:-1] + b" trailing\n",
        lambda payload: payload.replace(
            b'"provider_as_of":null', b'"provider_as_of":NaN'
        ),
        lambda payload: payload.replace(
            b'"request_id":"98dbdaca-e14b-5f10-8ca9-3650e18aa1d8"',
            b'"request_id":"98DBDACA-E14B-5F10-8CA9-3650E18AA1D8"',
        ),
        lambda payload: payload.replace(
            b'"requested_at":"2025-01-07T18:00:00Z"',
            b'"requested_at":"2025-01-07T18:00:00+00:00"',
        ),
        lambda payload: payload.replace(b'"volume":1000', b'"volume":true'),
        lambda payload: payload.replace(b'"open":"100"', b'"open":"100.00"'),
    ],
)
def test_strict_parser_rejects_invalid_bytes_and_noncanonical_scalars(
    mutator,
) -> None:
    with pytest.raises(DailySnapshotSerializationError):
        parse_daily_snapshot(mutator(serialize_daily_snapshot(accepted_snapshot())))


def test_strict_parser_rejects_duplicate_unknown_and_missing_fields() -> None:
    payload = serialize_daily_snapshot(accepted_snapshot())
    duplicate = payload.replace(
        b'{"adjustment":"RAW",',
        b'{"adjustment":"RAW","adjustment":"RAW",',
        1,
    )
    unknown_tree = json.loads(payload)
    unknown_tree["unknown"] = 1
    unknown = (
        json.dumps(
            unknown_tree,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    missing_tree = json.loads(payload)
    del missing_tree["timeframe"]
    missing = (
        json.dumps(
            missing_tree,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )

    for invalid in (duplicate, unknown, missing):
        with pytest.raises(DailySnapshotSerializationError):
            parse_daily_snapshot(invalid)


def test_strict_parser_rejects_comments() -> None:
    payload = serialize_daily_snapshot(accepted_snapshot())
    commented = payload.replace(b"{", b"{/*comment*/", 1)

    with pytest.raises(DailySnapshotSerializationError):
        parse_daily_snapshot(commented)
