from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.market_data import (
    AdjustmentType,
    DuplicateBarTimestampError,
    HistoricalDataRequest,
    HistoricalDataResult,
    InvalidHistoricalDataRequestError,
    InvalidHistoricalDataResultError,
    Timeframe,
)

SPY = Symbol("SPY")
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 4, tzinfo=UTC)


def request(**overrides: object) -> HistoricalDataRequest:
    values: dict[str, object] = {
        "symbol": SPY,
        "start": START,
        "end": END,
        "timeframe": Timeframe.DAY_1,
        "adjustment": AdjustmentType.RAW,
    }
    values.update(overrides)
    return HistoricalDataRequest(**values)  # type: ignore[arg-type]


def bar(timestamp: datetime, symbol: Symbol = SPY) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=1000,
    )


def test_request_normalizes_utc_and_uses_expected_enums() -> None:
    local = timezone(timedelta(hours=-8))
    item = request(
        start=datetime(2025, 12, 31, 16, tzinfo=local),
        end=datetime(2026, 1, 3, 16, tzinfo=local),
    )
    assert item.start == START
    assert item.end == END
    assert Timeframe.DAY_1.value == "1D"
    assert AdjustmentType.SPLIT_ADJUSTED.value == "SPLIT_ADJUSTED"
    assert AdjustmentType.TOTAL_RETURN.value == "TOTAL_RETURN"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 1, 1), END),
        (START, datetime(2026, 1, 4)),
        (END, END),
        (END, START),
    ],
)
def test_request_rejects_naive_or_invalid_interval(
    start: datetime, end: datetime
) -> None:
    with pytest.raises(InvalidHistoricalDataRequestError):
        request(start=start, end=end)


def test_request_is_immutable() -> None:
    item = request()
    with pytest.raises(FrozenInstanceError):
        item.start = END  # type: ignore[misc]


def test_result_defensively_copies_bars_and_accepts_empty() -> None:
    source = [bar(START)]
    result = HistoricalDataResult(request(), source, "test")  # type: ignore[arg-type]
    source.clear()
    assert result.bars == (bar(START),)
    assert HistoricalDataResult(request(), (), "test").bars == ()


def test_result_enforces_half_open_interval() -> None:
    HistoricalDataResult(request(), (bar(START),), "test")
    with pytest.raises(InvalidHistoricalDataResultError, match="outside"):
        HistoricalDataResult(request(), (bar(END),), "test")
    with pytest.raises(InvalidHistoricalDataResultError, match="outside"):
        HistoricalDataResult(request(), (bar(START - timedelta(seconds=1)),), "test")


def test_result_rejects_wrong_symbol_order_and_duplicates() -> None:
    with pytest.raises(InvalidHistoricalDataResultError, match="does not match"):
        HistoricalDataResult(request(), (bar(START, Symbol("QQQ")),), "test")
    with pytest.raises(InvalidHistoricalDataResultError, match="chronologically"):
        HistoricalDataResult(
            request(), (bar(START + timedelta(days=1)), bar(START)), "test"
        )
    with pytest.raises(DuplicateBarTimestampError):
        HistoricalDataResult(request(), (bar(START), bar(START)), "test")


def test_result_requires_nonblank_provider_name() -> None:
    with pytest.raises(InvalidHistoricalDataResultError, match="provider_name"):
        HistoricalDataResult(request(), (), " ")
