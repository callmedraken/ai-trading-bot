"""Synthetic/fake-only Architecture 148-B1 data and backtest coverage."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import trading_bot.experiments.arch148_intraday as subject
import trading_bot.experiments.arch148_sparse_backtest as sparse_backtest
from trading_bot.domain import Bar, Symbol
from trading_bot.live_runtime.models import (
    MarketQuality,
    MarketRegime,
    SignalAnalysis,
    SignalPoint,
)
from trading_bot.live_runtime.strategy import SessionReason


def _bars_for(symbol: str, day: date, *, opens: dict[datetime, Decimal] | None = None):
    opens = opens or {}
    return tuple(
        Bar(
            Symbol(symbol),
            stamp,
            opens.get(stamp, Decimal("100")),
            opens.get(stamp, Decimal("100")) + Decimal("1"),
            opens.get(stamp, Decimal("100")) - Decimal("1"),
            opens.get(stamp, Decimal("100")),
            100,
        )
        for stamp in subject.session_slots(day)
    )


def _dataset(day: date = date(2023, 11, 24), *, tqqq_opens=None):
    start = datetime.combine(day, datetime.min.time(), UTC)
    end = start + timedelta(days=1)
    return subject.IntradayDataset(
        start,
        end,
        tuple(
            subject.IntradaySymbolDataset(
                symbol,
                _bars_for(symbol, day, opens=tqqq_opens if symbol == "TQQQ" else None),
            )
            for symbol in subject.INTRADAY_SYMBOLS
        ),
    )


def _with_tqqq_bar(dataset, index: int, **changes):
    bars = list(dataset.bars_by_symbol["TQQQ"])
    bars[index] = replace(bars[index], **changes)
    return subject.IntradayDataset(
        dataset.start,
        dataset.end_exclusive,
        (
            dataset.datasets[0],
            subject.IntradaySymbolDataset("TQQQ", tuple(bars)),
            dataset.datasets[2],
        ),
    )


def _signal(
    regime: MarketRegime,
    *,
    confirmed: MarketRegime | None = None,
    paired: bool = False,
) -> SignalAnalysis:
    point = None
    previous = None
    if paired:
        point = SignalPoint(
            datetime(2023, 11, 24, 14, 30, tzinfo=UTC),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("99"),
            Decimal("55"),
            regime,
        )
        previous = SignalPoint(
            datetime(2023, 11, 24, 14, 25, tzinfo=UTC),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("99"),
            Decimal("55"),
            regime,
        )
    return SignalAnalysis(
        MarketQuality.READY,
        regime,
        confirmed,
        point,
        previous,
        "SYNTHETIC_B1_SIGNAL",
    )


def test_fixed_open_request_price_basis_and_holdout_rejection() -> None:
    request = subject.HistoricalIntradayRequest("QQQ")
    assert subject.INTRADAY_SYMBOLS == ("QQQ", "TQQQ", "SQQQ")
    assert request.timeframe == "5Min"
    assert request.adjustment == "all"
    assert request.feed == "sip"
    assert request.currency == "USD"
    assert request.sort == "asc"
    assert request.limit == 10_000
    assert subject.PRICE_BASIS == "ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1"
    with pytest.raises(subject.Arch148IntradayError, match="OPEN bounds"):
        subject.HistoricalIntradayRequest(
            "QQQ", end_exclusive=datetime(2024, 1, 2, tzinfo=UTC)
        )


def test_alpaca_request_and_page_parser_are_exact_and_auth_free() -> None:
    request = subject.HistoricalIntradayRequest("QQQ")
    provider_request = subject.build_alpaca_intraday_request(request)
    assert provider_request.method == "GET"
    assert "timeframe=5Min" in provider_request.target
    assert "adjustment=all" in provider_request.target
    assert "limit=10000" in provider_request.target
    assert not {name.casefold() for name, _ in provider_request.public_headers} & {
        "authorization",
        "apca-api-key-id",
        "apca-api-secret-key",
    }
    payload = json.dumps(
        {
            "bars": {
                "QQQ": [
                    {
                        "t": "2016-01-04T14:30:00Z",
                        "o": 100,
                        "h": 101,
                        "l": 99,
                        "c": 100,
                        "v": 1,
                    }
                ]
            },
            "next_page_token": "next",
        },
        separators=(",", ":"),
    ).encode()
    page = subject.parse_alpaca_intraday_page(payload, request)
    assert page.bars[0].symbol == Symbol("QQQ")
    assert page.next_page_token == "next"
    assert page.raw_page_sha256


@pytest.mark.parametrize(
    "payload,match",
    [
        (b'{"bars":{"TQQQ":[]},"next_page_token":null}', "unexpected symbol"),
        (
            b'{"bars":{"QQQ":[{"t":"2016-01-04T14:30:00Z","o":NaN,"h":101,"l":99,"c":100,"v":1}]},"next_page_token":null}',
            "nonfinite",
        ),
        (
            b'{"bars":{"QQQ":[{"t":"2016-01-04T14:30:00Z","o":100,"h":101,"l":99,"c":100,"v":1}]},"next_page_token":null,"x":1}',
            "fields",
        ),
    ],
)
def test_page_parser_rejects_malformed_pages(payload: bytes, match: str) -> None:
    with pytest.raises(subject.Arch148IntradayError, match=match):
        subject.parse_alpaca_intraday_page(
            payload, subject.HistoricalIntradayRequest("QQQ")
        )


def test_pagination_exhaustion_records_ordered_raw_page_digests() -> None:
    first = Bar(
        Symbol("QQQ"),
        datetime(2016, 1, 4, 14, 30, tzinfo=UTC),
        Decimal("100"),
        Decimal("101"),
        Decimal("99"),
        Decimal("100"),
        1,
    )

    class FakeTransport:
        def __init__(self):
            self.tokens = []

        def fetch_page(self, request):
            self.tokens.append(request.page_token)
            if request.page_token is None:
                return subject.HistoricalIntradayPage((first,), "next", "a" * 64, 10)
            return subject.HistoricalIntradayPage((), None, "b" * 64, 11)

    transport = FakeTransport()
    collected = subject.collect_intraday_pages(transport, "QQQ")
    assert transport.tokens == [None, "next"]
    assert collected.raw_page_sha256 == ("a" * 64, "b" * 64)
    assert collected.raw_page_byte_size == (10, 11)


def test_repeated_token_unexpected_symbol_and_bad_order_fail_closed() -> None:
    first = Bar(
        Symbol("QQQ"),
        datetime(2016, 1, 4, 14, 30, tzinfo=UTC),
        Decimal("100"),
        Decimal("101"),
        Decimal("99"),
        Decimal("100"),
        1,
    )

    class Repeating:
        def fetch_page(self, request):
            if request.page_token is None:
                return subject.HistoricalIntradayPage((first,), "loop", "a" * 64, 10)
            return subject.HistoricalIntradayPage((), "loop", "b" * 64, 10)

    with pytest.raises(subject.Arch148IntradayError, match="repeated"):
        subject.collect_intraday_pages(Repeating(), "QQQ")

    class Unexpected:
        def fetch_page(self, request):
            wrong = Bar(
                Symbol("TQQQ"),
                first.timestamp,
                first.open,
                first.high,
                first.low,
                first.close,
                first.volume,
            )
            return subject.HistoricalIntradayPage((wrong,), None, "a" * 64, 10)

    with pytest.raises(subject.Arch148IntradayError, match="unexpected symbol"):
        subject.collect_intraday_pages(Unexpected(), "QQQ")

    class OutOfOrder:
        def __init__(self):
            self.second = first.timestamp + timedelta(minutes=5)

        def fetch_page(self, request):
            if request.page_token is None:
                return subject.HistoricalIntradayPage(
                    (
                        Bar(
                            Symbol("QQQ"),
                            self.second,
                            first.open,
                            first.high,
                            first.low,
                            first.close,
                            1,
                        ),
                    ),
                    "next",
                    "a" * 64,
                    10,
                )
            return subject.HistoricalIntradayPage((first,), None, "b" * 64, 10)

    with pytest.raises(subject.Arch148IntradayError, match="chronological"):
        subject.collect_intraday_pages(OutOfOrder(), "QQQ")


@pytest.mark.parametrize("which", ["first", "middle", "final"])
def test_normal_and_early_close_slot_coverage_rejects_missing_slots(which: str) -> None:
    day = date(2023, 11, 24)
    slots = list(subject.session_slots(day))
    if which == "first":
        slots.pop(0)
    elif which == "middle":
        slots.pop(len(slots) // 2)
    else:
        slots.pop()
    bars = tuple(
        Bar(
            Symbol("QQQ"),
            stamp,
            Decimal("100"),
            Decimal("101"),
            Decimal("99"),
            Decimal("100"),
            1,
        )
        for stamp in slots
    )
    with pytest.raises(subject.IntradaySessionCoverageError):
        subject.IntradayDataset(
            datetime(2023, 11, 24, tzinfo=UTC),
            datetime(2023, 11, 25, tzinfo=UTC),
            (
                subject.IntradaySymbolDataset("QQQ", bars),
                subject.IntradaySymbolDataset("TQQQ", _bars_for("TQQQ", day)),
                subject.IntradaySymbolDataset("SQQQ", _bars_for("SQQQ", day)),
            ),
        )


def test_frozen_early_close_dates_and_dst_schedule_instants() -> None:
    expected_early_close_dates = frozenset(
        {
            date(2016, 11, 25),
            date(2017, 7, 3),
            date(2017, 11, 24),
            date(2018, 7, 3),
            date(2018, 11, 23),
            date(2018, 12, 24),
            date(2019, 7, 3),
            date(2019, 11, 29),
            date(2019, 12, 24),
            date(2020, 11, 27),
            date(2020, 12, 24),
            date(2021, 11, 26),
            date(2022, 11, 25),
            date(2023, 7, 3),
            date(2023, 11, 24),
        }
    )
    assert subject.EARLY_CLOSE_DATES == expected_early_close_dates
    assert len(subject.session_slots(date(2016, 7, 1))) == 78
    assert len(subject.session_slots(date(2016, 12, 23))) == 78
    assert len(subject.session_slots(date(2016, 11, 25))) == 42

    authority = subject.HistoricalIntradaySessionAuthority()
    new_york = ZoneInfo("America/New_York")
    normal_dst = authority.schedule_for(date(2016, 7, 1))
    assert normal_dst is not None
    assert normal_dst.opens_at == datetime(2016, 7, 1, 9, 30, tzinfo=new_york)
    assert normal_dst.closes_at == datetime(2016, 7, 1, 16, 0, tzinfo=new_york)
    assert normal_dst.opens_at.astimezone(UTC) == datetime(
        2016, 7, 1, 13, 30, tzinfo=UTC
    )
    assert normal_dst.closes_at.astimezone(UTC) == datetime(
        2016, 7, 1, 20, 0, tzinfo=UTC
    )

    early_dst = authority.schedule_for(date(2017, 7, 3))
    assert early_dst is not None
    assert early_dst.opens_at == datetime(2017, 7, 3, 9, 30, tzinfo=new_york)
    assert early_dst.closes_at == datetime(2017, 7, 3, 13, 0, tzinfo=new_york)
    assert early_dst.opens_at.astimezone(UTC) == datetime(
        2017, 7, 3, 13, 30, tzinfo=UTC
    )
    assert early_dst.closes_at.astimezone(UTC) == datetime(
        2017, 7, 3, 17, 0, tzinfo=UTC
    )

    normal_standard = authority.schedule_for(date(2016, 12, 23))
    assert normal_standard is not None
    assert normal_standard.opens_at == datetime(2016, 12, 23, 9, 30, tzinfo=new_york)
    assert normal_standard.closes_at == datetime(2016, 12, 23, 16, 0, tzinfo=new_york)
    assert normal_standard.opens_at.astimezone(UTC) == datetime(
        2016, 12, 23, 14, 30, tzinfo=UTC
    )
    assert normal_standard.closes_at.astimezone(UTC) == datetime(
        2016, 12, 23, 21, 0, tzinfo=UTC
    )

    early_standard = authority.schedule_for(date(2018, 12, 24))
    assert early_standard is not None
    assert early_standard.opens_at == datetime(2018, 12, 24, 9, 30, tzinfo=new_york)
    assert early_standard.closes_at == datetime(2018, 12, 24, 13, 0, tzinfo=new_york)
    assert early_standard.opens_at.astimezone(UTC) == datetime(
        2018, 12, 24, 14, 30, tzinfo=UTC
    )
    assert early_standard.closes_at.astimezone(UTC) == datetime(
        2018, 12, 24, 18, 0, tzinfo=UTC
    )

    for non_session in (date(2016, 12, 26), date(2018, 12, 5)):
        assert authority.schedule_for(non_session) is None
        assert subject.session_slots(non_session, authority) == ()


def test_session_slot_counts_and_out_of_session_bar_are_frozen() -> None:
    assert len(subject.session_slots(date(2023, 11, 22))) == 78
    assert len(subject.session_slots(date(2023, 11, 24))) == 42
    slots = list(subject.session_slots(date(2023, 11, 24)))
    slots[0] -= timedelta(minutes=5)
    bad = tuple(
        Bar(
            Symbol("QQQ"),
            stamp,
            Decimal("100"),
            Decimal("101"),
            Decimal("99"),
            Decimal("100"),
            1,
        )
        for stamp in slots
    )
    with pytest.raises(subject.IntradaySessionCoverageError):
        subject.IntradayDataset(
            datetime(2023, 11, 24, tzinfo=UTC),
            datetime(2023, 11, 25, tzinfo=UTC),
            (
                subject.IntradaySymbolDataset("QQQ", bad),
                subject.IntradaySymbolDataset(
                    "TQQQ", _bars_for("TQQQ", date(2023, 11, 24))
                ),
                subject.IntradaySymbolDataset(
                    "SQQQ", _bars_for("SQQQ", date(2023, 11, 24))
                ),
            ),
        )


def test_deterministic_dataset_and_custody_serialization() -> None:
    dataset = _dataset()
    collected = tuple(
        subject.CollectedIntradayPages(
            symbol, dataset.bars_by_symbol[symbol], ("a" * 64,), (123,)
        )
        for symbol in subject.INTRADAY_SYMBOLS
    )
    evidence = subject.build_intraday_custody_evidence(dataset, collected)
    subject.verify_intraday_custody_evidence(dataset, evidence)
    assert dataset.to_dict()["schema"] == "arch148-intraday-dataset/v2"
    assert evidence.to_dict()["schema"] == "arch148-intraday-custody-evidence/v2"
    mismatched = list(collected)
    mismatched[0] = subject.CollectedIntradayPages(
        "QQQ", dataset.bars_by_symbol["QQQ"][1:], ("b" * 64,), (123,)
    )
    with pytest.raises(subject.Arch148IntradayError, match="do not match"):
        subject.build_intraday_custody_evidence(dataset, tuple(mismatched))
    assert (
        subject.IntradayDataset.from_json(dataset.to_json()).identity
        == dataset.identity
    )
    assert (
        subject.IntradayCustodyEvidence.from_json(evidence.to_json()).evidence_id
        == evidence.evidence_id
    )
    restored_dataset = subject.IntradayDataset.from_json(dataset.to_json())
    restored_evidence = subject.IntradayCustodyEvidence.from_json(evidence.to_json())
    assert (
        restored_dataset.schedule_identity == subject.ARCH148_INTRADAY_SCHEDULE_IDENTITY
    )
    assert restored_dataset.schedule_digest == subject.ARCH148_INTRADAY_SCHEDULE_DIGEST
    assert (
        restored_evidence.schedule_identity
        == subject.ARCH148_INTRADAY_SCHEDULE_IDENTITY
    )
    assert restored_evidence.schedule_digest == subject.ARCH148_INTRADAY_SCHEDULE_DIGEST
    assert (
        dataset.to_json()
        == subject.IntradayDataset.from_json(dataset.to_json()).to_json()
    )


def _sparse_dataset(day: date = date(2023, 11, 22)):
    slots = subject.session_slots(day)
    missing_by_symbol = {
        "QQQ": {slots[1]},
        "TQQQ": {slots[1]},
        "SQQQ": {slots[1], slots[2]},
    }
    datasets = tuple(
        subject.IntradaySymbolDataset(
            symbol,
            tuple(
                bar
                for bar in _bars_for(symbol, day)
                if bar.timestamp not in missing_by_symbol[symbol]
            ),
        )
        for symbol in subject.INTRADAY_SYMBOLS
    )
    start = datetime.combine(day, datetime.min.time(), UTC)
    return subject.SparseIntradayDataset(start, start + timedelta(days=1), datasets)


def test_v3_sparse_dataset_binds_real_observations_and_gap_evidence() -> None:
    dataset = _sparse_dataset()
    assert dataset.to_dict()["schema"] == "arch148-intraday-dataset/v3"
    assert tuple(item.scheduled_slot_count for item in dataset.sparse_evidence) == (
        78,
        78,
        78,
    )
    assert tuple(
        item.observed_regular_session_count for item in dataset.sparse_evidence
    ) == (77, 77, 76)
    assert tuple(item.missing_count for item in dataset.sparse_evidence) == (1, 1, 2)
    assert dataset.common_missing_slot_count == 1
    assert dataset.union_missing_slot_count == 2
    assert tuple(
        item.complete_missing_session_count for item in dataset.sparse_evidence
    ) == (
        0,
        0,
        0,
    )
    assert all(
        item.first_observed_timestamp == subject.session_slots(date(2023, 11, 22))[0]
        and item.last_observed_timestamp
        == subject.session_slots(date(2023, 11, 22))[-1]
        for item in dataset.sparse_evidence
    )
    restored = subject.SparseIntradayDataset.from_json(dataset.to_json())
    assert restored.identity == dataset.identity
    assert restored.to_json() == dataset.to_json()
    assert restored.bars_by_symbol["QQQ"] == dataset.bars_by_symbol["QQQ"]
    changed = subject.SparseIntradayDataset(
        dataset.start,
        dataset.end_exclusive,
        (
            subject.IntradaySymbolDataset("QQQ", dataset.bars_by_symbol["QQQ"][:-1]),
            dataset.datasets[1],
            dataset.datasets[2],
        ),
    )
    assert changed.identity != dataset.identity


def test_v3_sparse_dataset_rejects_a_fully_missing_expected_session() -> None:
    first_day = date(2023, 11, 22)
    second_day = date(2023, 11, 24)
    qqq = _bars_for("QQQ", first_day)
    two_day_bars = {
        symbol: _bars_for(symbol, first_day) + _bars_for(symbol, second_day)
        for symbol in subject.INTRADAY_SYMBOLS
    }
    two_day_bars["QQQ"] = qqq
    with pytest.raises(subject.SparseIntradayCoverageError) as caught:
        subject.SparseIntradayDataset(
            datetime(2023, 11, 22, tzinfo=UTC),
            datetime(2023, 11, 25, tzinfo=UTC),
            tuple(
                subject.IntradaySymbolDataset(symbol, two_day_bars[symbol])
                for symbol in subject.INTRADAY_SYMBOLS
            ),
        )
    assert caught.value.symbol == "QQQ"
    assert caught.value.missing_session_count == 1
    assert len(caught.value.missing_session_sha256) == 64


def test_v3_sparse_custody_roundtrip_binds_page_and_normalized_bytes() -> None:
    dataset = _sparse_dataset()
    pages = tuple(
        subject.IntradayPageEvidence(symbol, (str(index) * 64,), (123,))
        for index, symbol in enumerate(subject.INTRADAY_SYMBOLS, start=1)
    )
    evidence = subject.build_sparse_intraday_custody_evidence(dataset, pages)
    subject.verify_sparse_intraday_custody_evidence(dataset, evidence)
    restored = subject.SparseIntradayCustodyEvidence.from_json(evidence.to_json())
    assert restored.evidence_id == evidence.evidence_id
    assert restored.to_dict()["schema"] == "arch148-intraday-custody-evidence/v3"
    assert restored.to_json() == evidence.to_json()


def test_run_backtest_dispatches_sparse_v3_through_the_sparse_entrypoint(
    monkeypatch,
) -> None:
    dataset = _sparse_dataset()
    marker = object()
    observed = {}

    def fake_sparse_backtest(value, **kwargs):
        observed["dataset"] = value
        observed["kwargs"] = kwargs
        return marker

    monkeypatch.setattr(sparse_backtest, "run_sparse_backtest", fake_sparse_backtest)
    assert subject.run_backtest(dataset) is marker
    assert observed["dataset"] is dataset
    assert observed["kwargs"]["cost_model"] is subject.ZERO_COST


def test_schedule_commitment_changes_with_early_close_semantics() -> None:
    changed_dates = subject.EARLY_CLOSE_DATES | {date(2016, 7, 1)}
    changed_identity, changed_digest = subject.arch148_intraday_schedule_commitment(
        changed_dates
    )
    assert changed_identity != subject.ARCH148_INTRADAY_SCHEDULE_IDENTITY
    assert changed_digest != subject.ARCH148_INTRADAY_SCHEDULE_DIGEST


@pytest.mark.parametrize(
    "field,wrong_value",
    [
        ("schedule_identity", "wrong-schedule-identity"),
        ("schedule_digest", "0" * 64),
    ],
)
def test_dataset_and_custody_reject_wrong_schedule_commitment(
    field: str, wrong_value: str
) -> None:
    dataset = _dataset()
    collected = tuple(
        subject.CollectedIntradayPages(
            symbol, dataset.bars_by_symbol[symbol], ("a" * 64,), (123,)
        )
        for symbol in subject.INTRADAY_SYMBOLS
    )
    evidence = subject.build_intraday_custody_evidence(dataset, collected)
    with pytest.raises(subject.Arch148IntradayError, match="provenance is frozen"):
        replace(dataset, **{field: wrong_value})
    with pytest.raises(subject.Arch148IntradayError, match="provenance is frozen"):
        replace(evidence, **{field: wrong_value})

    bad_dataset = dataset.to_dict()
    bad_dataset[field] = wrong_value
    with pytest.raises(subject.Arch148IntradayError, match="provenance is frozen"):
        subject.IntradayDataset.from_json(
            json.dumps(bad_dataset, sort_keys=True, separators=(",", ":"))
        )

    bad_evidence = evidence.to_dict()
    bad_evidence[field] = wrong_value
    with pytest.raises(subject.Arch148IntradayError, match="provenance is frozen"):
        subject.IntradayCustodyEvidence.from_json(
            json.dumps(bad_evidence, sort_keys=True, separators=(",", ":"))
        )


def test_arch146_date_authority_cannot_stand_in_for_arch148_schedule() -> None:
    dataset = _dataset()
    collected = tuple(
        subject.CollectedIntradayPages(
            symbol, dataset.bars_by_symbol[symbol], ("a" * 64,), (123,)
        )
        for symbol in subject.INTRADAY_SYMBOLS
    )
    evidence = subject.build_intraday_custody_evidence(dataset, collected)
    with pytest.raises(subject.Arch148IntradayError, match="provenance is frozen"):
        replace(
            dataset,
            schedule_identity=subject.AUTHORITY_IDENTITY,
            schedule_digest=subject.AUTHORITY_DIGEST,
        )
    with pytest.raises(subject.Arch148IntradayError, match="provenance is frozen"):
        replace(
            evidence,
            schedule_identity=subject.AUTHORITY_IDENTITY,
            schedule_digest=subject.AUTHORITY_DIGEST,
        )


def test_next_bar_entry_costs_controls_and_deterministic_replay() -> None:
    day = date(2023, 11, 24)
    slots = subject.session_slots(day)
    opens = dict.fromkeys(slots, Decimal("110"))
    dataset = _dataset(day, tqqq_opens=opens)

    def bullish(market, *, authority):
        assert market.completed_bars[-1].timestamp < market.as_of
        assert not market.execution_prices
        return _signal(MarketRegime.BULLISH, confirmed=MarketRegime.BULLISH)

    result = subject.run_backtest(
        dataset, analyzer=bullish, cost_model=subject.ZERO_COST
    )
    replay = subject.run_backtest(
        dataset, analyzer=bullish, cost_model=subject.ZERO_COST
    )
    assert result == replay
    assert result.trade_count == 1
    assert result.trades[0].symbol == "TQQQ"
    assert result.trades[0].entry_at == slots[3]
    assert result.trades[0].entry_price == Decimal("110")
    assert result.cash_control_return == Decimal("0")
    assert result.qqq_buy_and_hold_return == Decimal("0")

    conservative = subject.run_backtest(
        dataset, analyzer=bullish, cost_model=subject.CONSERVATIVE_COSTS
    )
    assert (
        conservative.cost_adjusted_strategy_return < conservative.gross_strategy_return
    )
    assert conservative.turnover > 0


def test_entry_bar_low_can_trigger_the_new_hard_stop() -> None:
    day = date(2023, 11, 24)
    slots = subject.session_slots(day)
    dataset = _with_tqqq_bar(
        _dataset(day),
        3,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("96"),
        close=Decimal("100"),
    )

    def bullish(market, *, authority):
        return (
            _signal(MarketRegime.BULLISH, confirmed=MarketRegime.BULLISH)
            if market.as_of == slots[3]
            else _signal(MarketRegime.NEUTRAL)
        )

    result = subject.run_backtest(dataset, analyzer=bullish)
    assert result.stop_hit_count == 1
    assert result.trade_count == 1
    assert result.trades[0].entry_at == slots[3]
    assert result.trades[0].exit_at == slots[3]
    assert result.trades[0].exit_reason == "STOP"
    assert result.trades[0].exit_price == Decimal("97.00")
    assert result.trades[0].holding_duration == timedelta()


def test_entry_bar_gap_uses_open_and_sell_slippage() -> None:
    day = date(2023, 11, 24)
    slots = subject.session_slots(day)
    dataset = _with_tqqq_bar(
        _dataset(day),
        3,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
    )
    cost_model = subject.BacktestCostModel(
        "SYNTHETIC_1000_BPS", Decimal("1000"), Decimal("0")
    )

    def bullish(market, *, authority):
        return (
            _signal(MarketRegime.BULLISH, confirmed=MarketRegime.BULLISH)
            if market.as_of == slots[3]
            else _signal(MarketRegime.NEUTRAL)
        )

    result = subject.run_backtest(dataset, analyzer=bullish, cost_model=cost_model)
    trade = result.trades[0]
    assert trade.entry_at == trade.exit_at == slots[3]
    assert trade.exit_reason == "STOP"
    assert trade.exit_price == Decimal("100")
    assert trade.gross_pnl == Decimal("0")
    assert trade.cost_adjusted_pnl == trade.quantity * Decimal(
        "90"
    ) - trade.quantity * Decimal("110")


def test_entry_bar_low_above_stop_carries_position_to_next_bar() -> None:
    day = date(2023, 11, 24)
    slots = subject.session_slots(day)
    dataset = _with_tqqq_bar(
        _dataset(day),
        4,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("96"),
        close=Decimal("100"),
    )

    def bullish(market, *, authority):
        return (
            _signal(MarketRegime.BULLISH, confirmed=MarketRegime.BULLISH)
            if market.as_of == slots[3]
            else _signal(MarketRegime.NEUTRAL)
        )

    result = subject.run_backtest(dataset, analyzer=bullish)
    assert result.stop_hit_count == 1
    assert result.trade_count == 1
    assert result.trades[0].entry_at == slots[3]
    assert result.trades[0].exit_at == slots[4]
    assert result.trades[0].exit_price == Decimal("97.00")


def test_entry_bar_stop_does_not_reenter_in_the_same_cycle() -> None:
    day = date(2023, 11, 24)
    slots = subject.session_slots(day)
    dataset = _with_tqqq_bar(
        _dataset(day),
        3,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("96"),
        close=Decimal("100"),
    )
    calls_at_entry_bar = 0

    def changing_signal(market, *, authority):
        nonlocal calls_at_entry_bar
        if market.as_of == slots[3]:
            calls_at_entry_bar += 1
            regime = (
                MarketRegime.BULLISH
                if calls_at_entry_bar == 1
                else MarketRegime.BEARISH
            )
            return _signal(regime, confirmed=regime)
        return _signal(MarketRegime.NEUTRAL)

    result = subject.run_backtest(dataset, analyzer=changing_signal)
    assert calls_at_entry_bar == 1
    assert result.trade_count == 1
    assert result.trades[0].symbol == "TQQQ"
    assert result.trades[0].entry_at == result.trades[0].exit_at == slots[3]


def test_stop_keeps_priority_over_regime_and_forced_flat() -> None:
    day = date(2023, 11, 24)
    slots = subject.session_slots(day)
    dataset = _with_tqqq_bar(
        _dataset(day),
        4,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("96"),
        close=Decimal("100"),
    )

    def conflicting_signal(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(MarketRegime.BULLISH, confirmed=MarketRegime.BULLISH)
        if market.as_of == slots[4]:
            return _signal(
                MarketRegime.BEARISH,
                confirmed=MarketRegime.BEARISH,
                paired=True,
            )
        return _signal(MarketRegime.NEUTRAL)

    def force_flat_on_stop_bar(as_of):
        if as_of == slots[4]:
            return subject.SessionDecision(None, False, True, SessionReason.FORCED_FLAT)
        return subject.session_decision(
            as_of, authority=subject.HistoricalIntradaySessionAuthority()
        )

    result = subject.run_backtest(
        dataset,
        analyzer=conflicting_signal,
        session_policy=force_flat_on_stop_bar,
    )
    assert result.trades[0].exit_reason == "STOP"
    assert result.trades[0].exit_at == slots[4]
    assert result.stop_hit_count == 1
    assert result.reversal_exits == 0
    assert result.forced_flat_count == 0


def test_stop_priority_gap_and_intrabar_threshold_conventions() -> None:
    day = date(2023, 11, 24)
    slots = subject.session_slots(day)
    opens = {
        slots[3]: Decimal("110"),
        slots[4]: Decimal("107"),
    }
    dataset = _dataset(day, tqqq_opens=opens)
    source = dataset.bars_by_symbol["TQQQ"]
    changed = list(source)
    changed[4] = Bar(
        Symbol("TQQQ"),
        changed[4].timestamp,
        Decimal("107"),
        Decimal("108"),
        Decimal("106"),
        Decimal("107"),
        100,
    )
    dataset = subject.IntradayDataset(
        dataset.start,
        dataset.end_exclusive,
        (
            dataset.datasets[0],
            subject.IntradaySymbolDataset("TQQQ", tuple(changed)),
            dataset.datasets[2],
        ),
    )

    def bullish(market, *, authority):
        return _signal(MarketRegime.BULLISH, confirmed=MarketRegime.BULLISH)

    result = subject.run_backtest(dataset, analyzer=bullish)
    assert result.stop_hit_count == 1
    assert result.trades[0].exit_reason == "STOP"
    assert result.trades[0].exit_price == Decimal("106.7")


def test_reversal_exits_first_and_inverse_enters_on_a_later_cycle() -> None:
    day = date(2023, 11, 24)
    dataset = _dataset(day)
    calls = 0

    def sequence(market, *, authority):
        nonlocal calls
        calls += 1
        if calls >= 5:
            return _signal(
                MarketRegime.BEARISH,
                confirmed=MarketRegime.BEARISH,
                paired=True,
            )
        return _signal(MarketRegime.BULLISH, confirmed=MarketRegime.BULLISH)

    result = subject.run_backtest(dataset, analyzer=sequence)
    assert result.trade_count >= 2
    assert result.trades[0].symbol == "TQQQ"
    assert result.trades[0].exit_reason == "REGIME_EXIT"
    assert result.trades[1].symbol == "SQQQ"
    assert result.trades[1].entry_at > result.trades[0].exit_at


def test_import_and_construction_have_no_provider_or_credential_effect() -> None:
    assert (
        subject.HistoricalIntradaySessionAuthority().published.identity
        == subject.AUTHORITY_IDENTITY
    )
    assert not hasattr(subject, "credentials")
    assert not hasattr(subject, "robinhood")
    assert Path(subject.__file__).exists()
