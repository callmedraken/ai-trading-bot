from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

from trading_bot.experiments import arch150_intraday_data as data
from trading_bot.experiments.arch148_intraday import EARLY_CLOSE_DATES
from trading_bot.experiments.arch150_intraday_ai import BarResolution, IntradayBar


def _wire(
    symbol: str,
    rows: list[dict[str, object]] | None = None,
    token: str | None = None,
) -> bytes:
    return json.dumps(
        {"bars": {symbol: rows or []}, "next_page_token": token},
        separators=(",", ":"),
    ).encode("utf-8")


def _provider_row(stamp: datetime) -> dict[str, object]:
    return {
        "t": stamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "o": 100,
        "h": 102,
        "l": 99,
        "c": 101,
        "v": 42,
    }


def _bar(symbol: str, stamp: datetime) -> IntradayBar:
    return IntradayBar(
        symbol,
        stamp,
        Decimal("100"),
        Decimal("102"),
        Decimal("99"),
        Decimal("101"),
        42,
        BarResolution.ONE_MINUTE,
    )


def _collection(
    symbol: str,
    bars: tuple[IntradayBar, ...],
    *,
    token: str | None = None,
) -> data.SymbolPageCollection:
    payload = _wire(symbol, [_provider_row(bar.timestamp) for bar in bars], token)
    persisted: list[tuple[str, int, bytes]] = []
    result = data.collect_symbol_pages(
        symbol,
        lambda _: payload,
        lambda sym, ordinal, body: persisted.append((sym, ordinal, body)),
    )
    assert persisted == [(symbol, 1, payload)]
    return result


def test_request_is_exact_single_symbol_adjusted_pre_2024_and_deterministic():
    request = data.Arch150HistoricalRequest("SPY")
    assert data.INITIAL_UNIVERSE == ("SPY", "QQQ")
    assert data.TIMEFRAME == "1Min"
    assert data.MAX_PAGES_PER_SYMBOL == 4096
    assert data.MAX_PROVIDER_REQUEST_ATTEMPTS == 8192
    assert request.identity == data.Arch150HistoricalRequest("SPY").identity
    assert request.digest == data.Arch150HistoricalRequest("SPY").digest
    assert request.identity != data.Arch150HistoricalRequest("QQQ").identity

    alpaca_request = data.build_alpaca_request(request)
    query = parse_qs(urlsplit(alpaca_request.target).query)
    assert query == {
        "symbols": ["SPY"],
        "timeframe": ["1Min"],
        "start": ["2016-01-01T00:00:00Z"],
        "end": ["2023-12-31T23:59:59.999999Z"],
        "limit": ["10000"],
        "adjustment": ["all"],
        "asof": ["-"],
        "feed": ["sip"],
        "currency": ["USD"],
        "sort": ["asc"],
    }
    assert "2024" not in query["end"][0]


@pytest.mark.parametrize("symbol", ["TQQQ", "SQQQ", "AAPL", "spy", ""])
def test_request_rejects_non_universe_symbols(symbol: str):
    with pytest.raises(data.Arch150DataError, match="UNSUPPORTED_SYMBOL"):
        data.Arch150HistoricalRequest(symbol)


def test_parser_rejects_wrong_symbol_bad_body_and_out_of_range_timestamps():
    request = data.Arch150HistoricalRequest("SPY")
    with pytest.raises(data.Arch150DataError, match="UNEXPECTED_PROVIDER_SYMBOL"):
        data.parse_alpaca_page(_wire("QQQ"), request)
    with pytest.raises(data.Arch150DataError, match="MALFORMED_PROVIDER_BODY"):
        data.parse_alpaca_page(b"", request)
    for stamp in (
        datetime(2015, 12, 31, 23, 59, tzinfo=UTC),
        datetime(2024, 1, 1, tzinfo=UTC),
    ):
        with pytest.raises(data.Arch150DataError, match="OUT_OF_RANGE"):
            data.parse_alpaca_page(_wire("SPY", [_provider_row(stamp)]), request)


def test_short_pages_continue_until_null_token_and_raw_bytes_precede_parsing():
    first = _wire("SPY", [], "cursor-2")
    second = _wire("SPY", [], "cursor-3")
    third = _wire("SPY", [], None)
    pages = iter((first, second, third))
    events: list[tuple[str, object]] = []

    def fetch(request: data.Arch150HistoricalRequest) -> bytes:
        events.append(("fetch", request.page_token))
        return next(pages)

    def persist(symbol: str, ordinal: int, payload: bytes) -> None:
        events.append(("persist", (symbol, ordinal, payload)))

    collected = data.collect_symbol_pages("SPY", fetch, persist)
    assert collected.pagination_complete
    assert collected.parsed_page_count == 3
    assert [item.page_sha256 for item in collected.pages] == [
        hashlib.sha256(body).hexdigest() for body in (first, second, third)
    ]
    assert [item.byte_length for item in collected.pages] == list(
        map(len, (first, second, third))
    )
    assert [item.ordinal for item in collected.pages] == [1, 2, 3]
    assert [item.terminal_state for item in collected.pages] == [
        "CONTINUE",
        "CONTINUE",
        "NULL_TOKEN_EXHAUSTED",
    ]
    assert events == [
        ("fetch", None),
        ("persist", ("SPY", 1, first)),
        ("fetch", "cursor-2"),
        ("persist", ("SPY", 2, second)),
        ("fetch", "cursor-3"),
        ("persist", ("SPY", 3, third)),
    ]
    assert [page.next_token_sha256 for page in collected.pages] == [
        hashlib.sha256(b"cursor-2").hexdigest(),
        hashlib.sha256(b"cursor-3").hexdigest(),
        None,
    ]


def test_repeated_token_page_ceiling_and_empty_malformed_page_are_preserved():
    payloads = iter((_wire("SPY", [], "loop"), _wire("SPY", [], "loop")))
    persisted: list[bytes] = []
    repeated = data.collect_symbol_pages(
        "SPY", lambda _: next(payloads), lambda _s, _o, body: persisted.append(body)
    )
    assert repeated.terminal_state == "REPEATED_TOKEN"
    assert repeated.failure_code == "PAGINATION_TOKEN_LOOP"
    assert len(repeated.pages) == 2
    assert repeated.pages[-1].terminal_state == "REPEATED_TOKEN"
    assert persisted == [_wire("SPY", [], "loop")] * 2

    ceiling = data.collect_symbol_pages(
        "SPY",
        lambda _: _wire("SPY", [], "still-more"),
        lambda *_: None,
        max_pages=1,
    )
    assert ceiling.terminal_state == "PAGE_CEILING_REACHED"
    assert len(ceiling.pages) == 1

    empty_persisted: list[bytes] = []
    malformed = data.collect_symbol_pages(
        "SPY", lambda _: b"", lambda _s, _o, body: empty_persisted.append(body)
    )
    assert empty_persisted == [b""]
    assert malformed.terminal_state == "MALFORMED_PAGE"
    assert malformed.pages[0].byte_length == 0
    assert malformed.pages[0].page_sha256 == hashlib.sha256(b"").hexdigest()
    assert malformed.pages[0].terminal_state == "UNPARSED_RESPONSE_PRESERVED"

    oversized = b" " * (data.MAX_PROVIDER_PAGE_BYTES + 1)
    oversized_persisted: list[bytes] = []
    oversized_result = data.collect_symbol_pages(
        "SPY",
        lambda _: oversized,
        lambda _s, _o, body: oversized_persisted.append(body),
    )
    assert oversized_persisted == [oversized]
    assert oversized_result.terminal_state == "MALFORMED_PAGE"
    assert oversized_result.pages[0].byte_length == len(oversized)


def test_early_close_projection_and_off_session_filter_use_published_xnys():
    authority = data.published_session_authority()
    early_close = next(
        day for day in EARLY_CLOSE_DATES if date(2016, 1, 1) <= day < date(2024, 1, 1)
    )
    slots = tuple(
        data.expected_regular_minute_slots(
            early_close, early_close + timedelta(days=1), authority
        )
    )
    assert len(slots) == 210
    assert (
        tuple(
            data.expected_regular_minute_slots(
                date(2023, 12, 25), date(2023, 12, 26), authority
            )
        )
        == ()
    )

    schedule = authority.schedule_for(early_close)
    assert schedule is not None
    premarket = schedule.opens_at - timedelta(minutes=30)
    collection = _collection(
        "SPY", (_bar("SPY", premarket), *(_bar("SPY", stamp) for stamp in slots))
    )
    assert collection.raw_bar_count == 211
    assert (
        collection.pages[0].page_sha256
        == hashlib.sha256(
            _wire("SPY", [_provider_row(premarket), *map(_provider_row, slots)])
        ).hexdigest()
    )
    normalized, diagnostics = data._qualify_symbol(
        "SPY",
        collection.bars,
        authority=authority,
        expected_start=early_close,
        expected_end=early_close + timedelta(days=1),
    )
    assert len(normalized) == 210
    assert normalized[0].timestamp == slots[0]
    assert diagnostics.off_session_excluded_count == 1
    assert diagnostics.missing_expected_slot_count == 0


def test_duplicate_missing_and_misaligned_slots_block_without_filling():
    authority = data.published_session_authority()
    early_close = next(
        day for day in EARLY_CLOSE_DATES if date(2016, 1, 1) <= day < date(2024, 1, 1)
    )
    slots = tuple(
        data.expected_regular_minute_slots(
            early_close, early_close + timedelta(days=1), authority
        )
    )
    full = tuple(_bar("SPY", stamp) for stamp in slots)

    duplicate, duplicate_diagnostics = data._qualify_symbol(
        "SPY",
        (*full, full[-1]),
        authority=authority,
        expected_start=early_close,
        expected_end=early_close + timedelta(days=1),
    )
    assert len(duplicate) == len(slots)
    assert duplicate_diagnostics.duplicate_expected_slot_count == 1

    missing, missing_diagnostics = data._qualify_symbol(
        "SPY",
        full[:-1],
        authority=authority,
        expected_start=early_close,
        expected_end=early_close + timedelta(days=1),
    )
    assert len(missing) == len(slots) - 1
    assert missing_diagnostics.missing_expected_slot_count == 1

    misaligned = _bar("SPY", slots[0] + timedelta(seconds=30))
    _, malformed_diagnostics = data._qualify_symbol(
        "SPY",
        (*full[:1], misaligned, *full[2:]),
        authority=authority,
        expected_start=early_close,
        expected_end=early_close + timedelta(days=1),
    )
    assert malformed_diagnostics.malformed_bar_count == 1


def test_dataset_and_partition_identities_bind_one_immutable_2016_2023_dataset(
    monkeypatch: pytest.MonkeyPatch,
):
    authority = data.published_session_authority()
    stamps = (
        datetime(2020, 1, 2, 14, 30, tzinfo=UTC),
        datetime(2021, 1, 4, 14, 30, tzinfo=UTC),
        datetime(2023, 1, 3, 14, 30, tzinfo=UTC),
    )
    monkeypatch.setattr(
        data,
        "expected_regular_minute_slots",
        lambda _start, _end, _authority: iter(stamps),
    )
    collections = tuple(
        _collection(symbol, tuple(_bar(symbol, stamp) for stamp in stamps))
        for symbol in data.INITIAL_UNIVERSE
    )

    dataset = data.qualify_arch150_dataset(collections, authority=authority)
    again = data.qualify_arch150_dataset(collections, authority=authority)
    assert dataset.classification is data.DatasetClassification.READY
    assert dataset.identity == again.identity
    assert dataset.sha256 == again.sha256
    assert dataset.normalized_bytes == again.normalized_bytes
    assert dataset.discovery.start == date(2016, 1, 1)
    assert dataset.discovery.end_exclusive == date(2021, 1, 1)
    assert dataset.discovery.row_count == 2
    assert dataset.validation.start == date(2021, 1, 1)
    assert dataset.validation.end_exclusive == date(2024, 1, 1)
    assert dataset.validation.row_count == 4
    assert dataset.discovery.identity == again.discovery.identity
    assert dataset.validation.identity == again.validation.identity
    assert dataset.first_timestamp == stamps[0].strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    assert dataset.last_timestamp == stamps[-1].strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    assert all(bar.timestamp.year < 2024 for bar in dataset.bars)
    assert len(dataset.raw_page_commitments) == 2
    assert dataset.raw_page_commitments[0].symbol == "SPY"
    assert dataset.raw_page_commitments[1].symbol == "QQQ"

    evidence = data.build_custody_evidence(
        dataset,
        source_head="a" * 40,
        source_tree="b" * 40,
        credential_read_attempt_count=0,
        provider_request_attempt_count=0,
    )
    evidence_dict = evidence.to_dict()
    assert evidence_dict["raw_page_commitments"][0]["ordinal"] == 1
    assert evidence_dict["raw_page_commitments"][0]["byte_length"] > 0
    assert evidence_dict["effects"] == {
        "credential_read_attempt_count": 0,
        "provider_request_attempt_count": 0,
        "robinhood_calls": 0,
        "broker_calls": 0,
        "order_mutations": 0,
        "production_state_mutations": 0,
        "strategy_pnl_evaluations": 0,
        "holdout_accesses": 0,
        "extension_accesses": 0,
    }
    assert b"open" not in evidence.to_bytes()
    assert b"close" not in evidence.to_bytes()
    assert not hasattr(data, "HOLDOUT_START")
    assert not hasattr(data, "RECENT_EXTENSION_START")
    assert "replay_program" not in data.__dict__
    assert "evaluate_frozen_trial" not in data.__dict__


def test_incomplete_stream_is_blocked_and_deterministic(
    monkeypatch: pytest.MonkeyPatch,
):
    stamps = (datetime(2020, 1, 2, 14, 30, tzinfo=UTC),)
    monkeypatch.setattr(
        data,
        "expected_regular_minute_slots",
        lambda _start, _end, _authority: iter(stamps),
    )
    partial = tuple(_collection(symbol, ()) for symbol in data.INITIAL_UNIVERSE)
    first = data.qualify_arch150_dataset(partial)
    second = data.qualify_arch150_dataset(partial)
    assert first.classification is data.DatasetClassification.BLOCKED
    assert "MISSING_EXPECTED_SLOT" in first.failure_codes
    assert first.identity == second.identity
    assert first.bars == ()
    assert all(
        item.missing_expected_slot_count == 1 for item in first.diagnostics_by_symbol
    )


def test_duplicate_slot_blocks_complete_dataset_without_silent_deduplication(
    monkeypatch: pytest.MonkeyPatch,
):
    stamps = (
        datetime(2020, 1, 2, 14, 30, tzinfo=UTC),
        datetime(2020, 1, 2, 14, 31, tzinfo=UTC),
    )
    monkeypatch.setattr(
        data,
        "expected_regular_minute_slots",
        lambda _start, _end, _authority: iter(stamps),
    )
    collections = (
        _collection(
            "SPY",
            (
                _bar("SPY", stamps[0]),
                _bar("SPY", stamps[0]),
                _bar("SPY", stamps[1]),
            ),
        ),
        _collection("QQQ", tuple(_bar("QQQ", stamp) for stamp in stamps)),
    )
    dataset = data.qualify_arch150_dataset(collections)
    assert dataset.classification is data.DatasetClassification.BLOCKED
    assert "DUPLICATE_EXPECTED_SLOT" in dataset.failure_codes
    assert dataset.diagnostics_by_symbol[0].duplicate_expected_slot_count == 1
    assert dataset.bars == ()
