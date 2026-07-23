"""Canonical identity material for immutable aligned historical data."""

from decimal import Decimal

from trading_bot.market_data.models import MultiSymbolHistoricalDataResult

_ZERO = Decimal("0")


def canonical_multi_symbol_historical_material(
    data: MultiSymbolHistoricalDataResult,
) -> tuple[str, ...]:
    """Return namespace-free canonical request/result and ordered OHLCV material."""
    if type(data) is not MultiSymbolHistoricalDataResult:
        raise TypeError("data must be exactly MultiSymbolHistoricalDataResult")
    request = data.request
    material = [
        request.start.isoformat(),
        request.end.isoformat(),
        request.timeframe.value,
        request.adjustment.value,
        request.missing_bar_policy.value,
        data.provider_name,
        *(str(symbol) for symbol in request.symbols),
    ]
    for frame in data.frames:
        material.extend(
            (
                frame.timestamp.isoformat(),
                *(str(symbol) for symbol in frame.missing_symbols),
            )
        )
        for symbol in frame.symbols:
            bar = frame.bars_by_symbol.get(symbol)
            material.extend(
                ("missing", str(symbol)) if bar is None else _bar_material(bar)
            )
    return tuple(material)


def _bar_material(bar) -> tuple[str, ...]:  # type: ignore[no-untyped-def]
    return (
        str(bar.symbol),
        bar.timestamp.isoformat(),
        _canonical_decimal(bar.open),
        _canonical_decimal(bar.high),
        _canonical_decimal(bar.low),
        _canonical_decimal(bar.close),
        str(bar.volume),
    )


def _canonical_decimal(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("historical identity Decimal values must be finite")
    if value == _ZERO:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
