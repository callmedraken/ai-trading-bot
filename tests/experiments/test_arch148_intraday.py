"""Synthetic/fake-only Architecture 148-B1 data and backtest coverage."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import trading_bot.experiments.arch148_intraday as subject
from trading_bot.domain import Bar, Symbol
from trading_bot.live_runtime.models import (
    MarketQuality,
    MarketRegime,
    SignalAnalysis,
    SignalPoint,
)


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
    assert (
        dataset.to_json()
        == subject.IntradayDataset.from_json(dataset.to_json()).to_json()
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
