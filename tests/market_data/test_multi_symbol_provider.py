from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.market_data import (
    CoordinatingHistoricalDataProvider,
    CSVHistoricalDataProvider,
    CSVRowError,
    EmptyAlignedHistoricalDataError,
    HistoricalDataNotFoundError,
    HistoricalDataRequest,
    HistoricalDataResult,
    InconsistentProviderResultError,
    MissingBarPolicy,
    MultiSymbolHistoricalDataProvider,
    MultiSymbolHistoricalDataRequest,
)

SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 4, tzinfo=UTC)
FIXTURES = Path(__file__).parents[1] / "fixtures" / "historical_data"


def bar(symbol: Symbol, day: int) -> Bar:
    timestamp = START + timedelta(days=day)
    return Bar(
        symbol,
        timestamp,
        Decimal("100"),
        Decimal("102"),
        Decimal("99"),
        Decimal("101"),
        1000,
    )


class InMemoryProvider:
    def __init__(self, data: dict[Symbol, tuple[Bar, ...]]) -> None:
        self.data = data
        self.calls = []

    def get_bars(self, request: HistoricalDataRequest) -> HistoricalDataResult:
        self.calls.append(request.symbol)
        return HistoricalDataResult(request, self.data[request.symbol], "ignored")


def request(
    policy: MissingBarPolicy = MissingBarPolicy.UNION,
) -> MultiSymbolHistoricalDataRequest:
    return MultiSymbolHistoricalDataRequest(
        (QQQ, SPY), START, END, missing_bar_policy=policy
    )


def test_union_alignment_preserves_all_timestamps_and_missing_symbols() -> None:
    source = InMemoryProvider({QQQ: (bar(QQQ, 1),), SPY: (bar(SPY, 0), bar(SPY, 1))})
    provider: MultiSymbolHistoricalDataProvider = CoordinatingHistoricalDataProvider(
        source
    )
    result = provider.get_bars(request())
    assert source.calls == [QQQ, SPY]
    assert result.timestamps == (START, START + timedelta(days=1))
    assert result.frames[0].missing_symbols == (QQQ,)
    assert tuple(result.frames[1].bars_by_symbol) == (QQQ, SPY)
    assert not result.is_complete


def test_intersection_retains_only_complete_exact_timestamp_frames() -> None:
    source = InMemoryProvider({QQQ: (bar(QQQ, 1),), SPY: (bar(SPY, 0), bar(SPY, 1))})
    result = CoordinatingHistoricalDataProvider(source).get_bars(
        request(MissingBarPolicy.INTERSECTION)
    )
    assert result.timestamps == (START + timedelta(days=1),)
    assert result.frames[0].is_complete
    assert tuple(result.frames[0].bars_by_symbol) == (QQQ, SPY)


def test_empty_constituent_is_retained_by_union_but_empties_intersection() -> None:
    source = InMemoryProvider({QQQ: (), SPY: (bar(SPY, 0),)})
    provider = CoordinatingHistoricalDataProvider(source)
    union = provider.get_bars(request())
    assert union.bars_for(QQQ).bars == ()
    assert union.frames[0].missing_symbols == (QQQ,)
    with pytest.raises(EmptyAlignedHistoricalDataError):
        provider.get_bars(request(MissingBarPolicy.INTERSECTION))


def test_all_empty_constituents_fail_for_both_policies() -> None:
    provider = CoordinatingHistoricalDataProvider(InMemoryProvider({QQQ: (), SPY: ()}))
    for policy in MissingBarPolicy:
        with pytest.raises(EmptyAlignedHistoricalDataError):
            provider.get_bars(request(policy))


def test_repeated_loads_are_value_equal_and_provider_name_is_coordinator_owned() -> (
    None
):
    source = InMemoryProvider({QQQ: (bar(QQQ, 0),), SPY: (bar(SPY, 0),)})
    provider = CoordinatingHistoricalDataProvider(source)
    first = provider.get_bars(request())
    second = provider.get_bars(request())
    assert first == second
    assert first.provider_name.endswith(".InMemoryProvider")


def test_inconsistent_constituent_request_fails_at_provider_boundary() -> None:
    class BadProvider:
        def get_bars(self, child: HistoricalDataRequest) -> HistoricalDataResult:
            wrong = HistoricalDataRequest(SPY, child.start, child.end)
            return HistoricalDataResult(wrong, (), "bad")

    with pytest.raises(InconsistentProviderResultError, match="request"):
        CoordinatingHistoricalDataProvider(BadProvider()).get_bars(request())


def test_constituent_errors_propagate_without_translation() -> None:
    class FailingProvider:
        def get_bars(self, child: HistoricalDataRequest) -> HistoricalDataResult:
            raise CSVRowError(f"malformed {child.symbol}")

    with pytest.raises(CSVRowError, match="QQQ"):
        CoordinatingHistoricalDataProvider(FailingProvider()).get_bars(request())


def test_real_csv_provider_composes_without_changing_single_symbol_provider() -> None:
    provider = CoordinatingHistoricalDataProvider(CSVHistoricalDataProvider(FIXTURES))
    result = provider.get_bars(request())
    assert result.provider_name == (
        "coordinating:trading_bot.market_data.csv_provider.CSVHistoricalDataProvider"
    )
    assert result.symbols == (QQQ, SPY)
    assert result.timestamps == tuple(sorted(result.timestamps))
    assert result.bars_for(QQQ).bars
    assert result.bars_for(SPY).bars


def test_real_csv_missing_file_and_malformed_row_errors_propagate(
    tmp_path: Path,
) -> None:
    coordinator = CoordinatingHistoricalDataProvider(
        CSVHistoricalDataProvider(tmp_path)
    )
    with pytest.raises(HistoricalDataNotFoundError, match="QQQ"):
        coordinator.get_bars(request())

    (tmp_path / "QQQ.csv").write_text(
        "timestamp,symbol,open,high,low,close,volume\n"
        "2026-01-01T00:00:00Z,QQQ,bad,102,99,101,1000\n",
        encoding="utf-8",
    )
    with pytest.raises(CSVRowError, match="QQQ.csv"):
        coordinator.get_bars(request())
