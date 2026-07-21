from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.market_data import (
    AlignedMarketFrame,
    DuplicateRequestedSymbolError,
    EmptyAlignedHistoricalDataError,
    InvalidMultiSymbolHistoricalDataRequestError,
    InvalidMultiSymbolHistoricalDataResultError,
    MissingBarPolicy,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
)

SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 4, tzinfo=UTC)


def bar(symbol: Symbol, timestamp: datetime) -> Bar:
    return Bar(
        symbol,
        timestamp,
        Decimal("100"),
        Decimal("102"),
        Decimal("99"),
        Decimal("101"),
        1000,
    )


def request(**overrides: object) -> MultiSymbolHistoricalDataRequest:
    values: dict[str, object] = {
        "symbols": (QQQ, SPY),
        "start": START,
        "end": END,
    }
    values.update(overrides)
    return MultiSymbolHistoricalDataRequest(**values)  # type: ignore[arg-type]


def test_request_preserves_and_defensively_copies_symbol_order() -> None:
    source = [QQQ, SPY]
    item = request(symbols=source)
    source.reverse()
    assert item.symbols == (QQQ, SPY)
    assert item.missing_bar_policy is MissingBarPolicy.UNION
    with pytest.raises(FrozenInstanceError):
        item.start = END  # type: ignore[misc]


def test_request_rejects_empty_duplicate_and_invalid_symbols() -> None:
    with pytest.raises(InvalidMultiSymbolHistoricalDataRequestError, match="empty"):
        request(symbols=())
    with pytest.raises(DuplicateRequestedSymbolError):
        request(symbols=(SPY, Symbol("spy")))
    with pytest.raises(InvalidMultiSymbolHistoricalDataRequestError, match="Symbol"):
        request(symbols=(SPY, "QQQ"))


def test_request_normalizes_aware_bounds_and_rejects_invalid_ranges() -> None:
    eastern = timezone(timedelta(hours=-5))
    item = request(
        start=datetime(2025, 12, 31, 19, tzinfo=eastern),
        end=datetime(2026, 1, 3, 19, tzinfo=eastern),
    )
    assert item.start == START
    assert item.end == END
    with pytest.raises(InvalidMultiSymbolHistoricalDataRequestError):
        request(start=datetime(2026, 1, 1))
    with pytest.raises(InvalidMultiSymbolHistoricalDataRequestError):
        request(start=END, end=START)


def test_frame_copies_reorders_and_explicitly_records_missing_symbols() -> None:
    source = {SPY: bar(SPY, START), QQQ: bar(QQQ, START)}
    frame = AlignedMarketFrame(START, (QQQ, SPY), source)
    source.clear()
    assert tuple(frame.bars_by_symbol) == (QQQ, SPY)
    assert frame.missing_symbols == ()
    assert frame.is_complete

    partial = AlignedMarketFrame(START, (QQQ, SPY), {SPY: bar(SPY, START)})
    assert tuple(partial.bars_by_symbol) == (SPY,)
    assert partial.missing_symbols == (QQQ,)
    assert not partial.is_complete
    with pytest.raises(TypeError):
        partial.bars_by_symbol[QQQ] = bar(QQQ, START)  # type: ignore[index]


def test_equal_frame_content_has_value_equality_independent_of_mapping_identity() -> (
    None
):
    first = AlignedMarketFrame(START, (SPY, QQQ), {SPY: bar(SPY, START)})
    second = AlignedMarketFrame(START, (SPY, QQQ), {SPY: bar(SPY, START)})
    assert first == second


def test_frame_rejects_unknown_mismatched_and_mistimed_bars() -> None:
    with pytest.raises(InvalidMultiSymbolHistoricalDataResultError, match="outside"):
        AlignedMarketFrame(START, (SPY,), {QQQ: bar(QQQ, START)})
    with pytest.raises(InvalidMultiSymbolHistoricalDataResultError, match="keys"):
        AlignedMarketFrame(START, (SPY,), {SPY: bar(QQQ, START)})
    with pytest.raises(InvalidMultiSymbolHistoricalDataResultError, match="timestamp"):
        AlignedMarketFrame(START, (SPY,), {SPY: bar(SPY, START + timedelta(days=1))})


def test_result_accessors_are_exact_ordered_and_do_not_revalidate() -> None:
    frames = (
        AlignedMarketFrame(START, (QQQ, SPY), {SPY: bar(SPY, START)}),
        AlignedMarketFrame(
            START + timedelta(days=1),
            (QQQ, SPY),
            {
                QQQ: bar(QQQ, START + timedelta(days=1)),
                SPY: bar(SPY, START + timedelta(days=1)),
            },
        ),
    )
    result = MultiSymbolHistoricalDataResult(request(), frames, "coordinator")
    assert result.symbols == (QQQ, SPY)
    assert result.timestamps == tuple(frame.timestamp for frame in frames)
    assert result.bars_for(SPY).bars == (
        frames[0].bars_by_symbol[SPY],
        frames[1].bars_by_symbol[SPY],
    )
    offset_timestamp = datetime(2025, 12, 31, 19, tzinfo=timezone(timedelta(hours=-5)))
    assert result.frame_at(offset_timestamp) == frames[0]
    assert result.frame_at(START + timedelta(hours=1)) is None
    with pytest.raises(ValueError, match="timezone-aware"):
        result.frame_at(datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="outside"):
        result.bars_for(Symbol("DIA"))


def test_result_rejects_empty_unordered_outside_and_incomplete_intersection() -> None:
    with pytest.raises(EmptyAlignedHistoricalDataError):
        MultiSymbolHistoricalDataResult(request(), (), "test")
    later = AlignedMarketFrame(
        START + timedelta(days=1),
        (QQQ, SPY),
        {QQQ: bar(QQQ, START + timedelta(days=1))},
    )
    earlier = AlignedMarketFrame(START, (QQQ, SPY), {QQQ: bar(QQQ, START)})
    with pytest.raises(InvalidMultiSymbolHistoricalDataResultError, match="increasing"):
        MultiSymbolHistoricalDataResult(request(), (later, earlier), "test")
    outside = AlignedMarketFrame(END, (QQQ, SPY), {QQQ: bar(QQQ, END)})
    with pytest.raises(InvalidMultiSymbolHistoricalDataResultError, match="outside"):
        MultiSymbolHistoricalDataResult(request(), (outside,), "test")
    intersection = request(missing_bar_policy=MissingBarPolicy.INTERSECTION)
    with pytest.raises(
        InvalidMultiSymbolHistoricalDataResultError, match="intersection"
    ):
        MultiSymbolHistoricalDataResult(intersection, (earlier,), "test")
