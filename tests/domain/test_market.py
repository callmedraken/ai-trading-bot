from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Asset, AssetType, Bar, Symbol


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [("spy", "SPY"), (" BRK.B ", "BRK.B"), ("abc-1", "ABC-1")],
)
def test_symbol_normalizes_and_stringifies(raw: str, normalized: str) -> None:
    symbol = Symbol(raw)
    assert symbol.value == normalized
    assert str(symbol) == normalized


def test_normalized_symbols_are_equal_and_hashable() -> None:
    assert Symbol(" spy ") == Symbol("SPY")
    assert len({Symbol("spy"), Symbol("SPY")}) == 1


@pytest.mark.parametrize("value", ["", "   ", "bad symbol", "ABC_1", "ABCDEFGHIJK"])
def test_symbol_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        Symbol(value)


def test_asset_accepts_supported_type_and_optional_name() -> None:
    assert Asset(Symbol("SPY"), AssetType.ETF, "SPDR S&P 500 ETF").name
    assert Asset(Symbol("AAPL"), AssetType.STOCK).name is None


@pytest.mark.parametrize("name", ["", "  "])
def test_asset_rejects_blank_name(name: str) -> None:
    with pytest.raises(ValueError, match="blank"):
        Asset(Symbol("SPY"), AssetType.ETF, name)


def test_asset_rejects_unsupported_type() -> None:
    with pytest.raises(ValueError, match="STOCK or ETF"):
        Asset(Symbol("SPY"), "CRYPTO")  # type: ignore[arg-type]


def make_bar(**overrides: object) -> Bar:
    values: dict[str, object] = {
        "symbol": Symbol("SPY"),
        "timestamp": datetime(2026, 1, 2, 16, tzinfo=timezone(timedelta(hours=-8))),
        "open": Decimal("100"),
        "high": Decimal("105"),
        "low": Decimal("99"),
        "close": Decimal("103"),
        "volume": 1000,
    }
    values.update(overrides)
    return Bar(**values)  # type: ignore[arg-type]


def test_bar_normalizes_timestamp_to_utc() -> None:
    bar = make_bar()
    assert bar.timestamp == datetime(2026, 1, 3, 0, tzinfo=UTC)
    assert bar.timestamp.tzinfo is UTC


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_bar_rejects_nonpositive_prices(field: str, value: Decimal) -> None:
    with pytest.raises(ValueError, match=field):
        make_bar(**{field: value})


def test_bar_does_not_convert_missing_price_to_zero() -> None:
    with pytest.raises(TypeError, match="open must be a Decimal"):
        make_bar(open=None)


@pytest.mark.parametrize("volume", [-1, Decimal("1")])
def test_bar_rejects_invalid_volume(volume: object) -> None:
    with pytest.raises((TypeError, ValueError), match="volume"):
        make_bar(volume=volume)


def test_bar_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_bar(timestamp=datetime(2026, 1, 2))


def test_bar_rejects_inconsistent_high_or_low() -> None:
    with pytest.raises(ValueError, match="high"):
        make_bar(high=Decimal("102"))
    with pytest.raises(ValueError, match="low"):
        make_bar(low=Decimal("101"))


def test_market_models_are_immutable() -> None:
    symbol = Symbol("SPY")
    with pytest.raises(FrozenInstanceError):
        symbol.value = "QQQ"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        make_bar().close = Decimal("1")  # type: ignore[misc]
