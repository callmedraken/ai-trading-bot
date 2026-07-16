from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_data import (
    AdjustmentType,
    CSVHistoricalDataProvider,
    CSVRowError,
    CSVSchemaError,
    DuplicateBarTimestampError,
    HistoricalDataNotFoundError,
    HistoricalDataProvider,
    HistoricalDataRequest,
    Timeframe,
    UnsupportedAdjustmentError,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "historical_data"
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 4, tzinfo=UTC)


def request(
    symbol: str = "SPY",
    *,
    start: datetime = START,
    end: datetime = END,
    adjustment: AdjustmentType = AdjustmentType.RAW,
) -> HistoricalDataRequest:
    return HistoricalDataRequest(
        Symbol(symbol), start, end, Timeframe.DAY_1, adjustment
    )


def write_csv(root: Path, text: str, symbol: str = "SPY") -> Path:
    path = root / f"{symbol}.csv"
    path.write_text(text, encoding="utf-8", newline="")
    return path


def test_provider_satisfies_protocol_and_loads_sorted_fixture() -> None:
    provider: HistoricalDataProvider = CSVHistoricalDataProvider(FIXTURES)
    result = provider.get_bars(request())
    assert result.provider_name == "local_csv"
    assert [bar.timestamp for bar in result.bars] == sorted(
        bar.timestamp for bar in result.bars
    )
    assert [bar.close for bar in result.bars] == [
        Decimal("100.50"),
        Decimal("102.00"),
        Decimal("103.25"),
    ]
    assert all(bar.timestamp.tzinfo is UTC for bar in result.bars)


def test_provider_filters_with_half_open_interval() -> None:
    provider = CSVHistoricalDataProvider(FIXTURES)
    result = provider.get_bars(
        request(
            start=datetime(2026, 1, 2, tzinfo=UTC),
            end=datetime(2026, 1, 3, tzinfo=UTC),
        )
    )
    assert len(result.bars) == 1
    assert result.bars[0].timestamp == datetime(2026, 1, 2, 5, tzinfo=UTC)


def test_empty_matching_interval_is_valid() -> None:
    provider = CSVHistoricalDataProvider(FIXTURES)
    result = provider.get_bars(
        request(
            start=datetime(2026, 2, 1, tzinfo=UTC),
            end=datetime(2026, 2, 2, tzinfo=UTC),
        )
    )
    assert result.bars == ()


@pytest.mark.parametrize(
    "adjustment", [AdjustmentType.SPLIT_ADJUSTED, AdjustmentType.TOTAL_RETURN]
)
def test_provider_rejects_adjusted_data(adjustment: AdjustmentType) -> None:
    provider = CSVHistoricalDataProvider(FIXTURES)
    with pytest.raises(UnsupportedAdjustmentError, match="RAW"):
        provider.get_bars(request(adjustment=adjustment))


def test_provider_rejects_missing_symbol_file(tmp_path: Path) -> None:
    with pytest.raises(HistoricalDataNotFoundError, match="QQQ"):
        CSVHistoricalDataProvider(tmp_path).get_bars(request("QQQ"))


@pytest.mark.parametrize(
    "header",
    [
        "timestamp,open,high,low,close,volume",
        "timestamp,symbol,open,high,low,close,volume,extra",
        "timestamp,symbol,symbol,high,low,close,volume",
    ],
)
def test_provider_rejects_invalid_schema(tmp_path: Path, header: str) -> None:
    write_csv(tmp_path, header + "\n")
    with pytest.raises(CSVSchemaError, match="headers"):
        CSVHistoricalDataProvider(tmp_path).get_bars(request())


def test_provider_accepts_headers_in_any_order(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "volume,close,low,high,open,symbol,timestamp\n"
        "1000,101,99,102,100,SPY,2026-01-01T00:00:00Z\n",
    )
    result = CSVHistoricalDataProvider(tmp_path).get_bars(request())
    assert result.bars[0].volume == 1000


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("2026-01-01T00:00:00,SPY,100,102,99,101,1000", "timezone"),
        ("not-a-date,SPY,100,102,99,101,1000", "Invalid isoformat"),
        ("2026-01-01T00:00:00Z,QQQ,100,102,99,101,1000", "does not match"),
        ("2026-01-01T00:00:00Z,SPY,NaN,102,99,101,1000", "finite"),
        ("2026-01-01T00:00:00Z,SPY,Infinity,102,99,101,1000", "finite"),
        ("2026-01-01T00:00:00Z,SPY,-Infinity,102,99,101,1000", "finite"),
        ("2026-01-01T00:00:00Z,SPY,100,102,99,101,1.5", "integer"),
        ("2026-01-01T00:00:00Z,SPY,100,102,99,101,-1", "integer"),
        ("2026-01-01T00:00:00Z,SPY,100,98,99,101,1", "high"),
        ("2026-01-01T00:00:00Z,SPY, 100,102,99,101,1", "padding"),
    ],
)
def test_provider_rejects_malformed_rows(
    tmp_path: Path, row: str, message: str
) -> None:
    write_csv(
        tmp_path,
        "timestamp,symbol,open,high,low,close,volume\n" + row + "\n",
    )
    with pytest.raises(CSVRowError, match=message) as captured:
        CSVHistoricalDataProvider(tmp_path).get_bars(request())
    assert ":2:" in str(captured.value)


def test_malformed_out_of_range_row_still_fails(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "timestamp,symbol,open,high,low,close,volume\n"
        "2025-01-01T00:00:00Z,SPY,bad,102,99,101,1000\n",
    )
    with pytest.raises(CSVRowError):
        CSVHistoricalDataProvider(tmp_path).get_bars(request())


def test_blank_or_wrong_length_row_fails(tmp_path: Path) -> None:
    header = "timestamp,symbol,open,high,low,close,volume\n"
    write_csv(tmp_path, header + "\n")
    with pytest.raises(CSVRowError, match="expected"):
        CSVHistoricalDataProvider(tmp_path).get_bars(request())
    write_csv(tmp_path, header + "2026-01-01T00:00:00Z,SPY,100\n")
    with pytest.raises(CSVRowError, match="expected"):
        CSVHistoricalDataProvider(tmp_path).get_bars(request())


def test_duplicate_detection_occurs_after_sorting(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "timestamp,symbol,open,high,low,close,volume\n"
        "2026-01-02T00:00:00Z,SPY,100,102,99,101,1\n"
        "2026-01-01T00:00:00Z,SPY,100,102,99,101,1\n"
        "2026-01-02T00:00:00+00:00,SPY,100,102,99,101,1\n",
    )
    with pytest.raises(DuplicateBarTimestampError, match="duplicate timestamp"):
        CSVHistoricalDataProvider(tmp_path).get_bars(request())


def test_repeated_calls_are_deterministic() -> None:
    provider = CSVHistoricalDataProvider(FIXTURES)
    assert provider.get_bars(request()) == provider.get_bars(request())
