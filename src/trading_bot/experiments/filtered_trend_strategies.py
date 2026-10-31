"""Deterministic, strategy-neutral filtered trend signals for research."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)

from trading_bot.domain.market import Bar

_PAIRS = ((35, 50), (55, 100), (50, 200))
_FAMILIES = (
    "BASE_MA",
    "MA_PERCENT_BAND",
    "MA_ADX",
    "MA_DONCHIAN",
    "MA_LONG_MOMENTUM",
)
_PARAMETERS = {
    "BASE_MA": ("none",),
    "MA_PERCENT_BAND": ("0.005", "0.010", "0.015"),
    "MA_ADX": ("20", "25"),
    "MA_DONCHIAN": ("20", "55"),
    "MA_LONG_MOMENTUM": (
        "return252_positive",
        "close_at_least_90pct_prior252_high",
    ),
}
_ARITHMETIC_CONTEXT = Context(
    prec=50,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)
_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")
_ADX_PERIOD = 14
_ATR_PERIOD = 14


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """One immutable, predeclared filtered trend configuration."""

    family: str
    fast: int
    slow: int
    parameter: str

    def __post_init__(self) -> None:
        if not isinstance(self.family, str) or self.family not in _FAMILIES:
            raise ValueError("family must be a supported filtered trend family")
        if (
            not isinstance(self.fast, int)
            or isinstance(self.fast, bool)
            or not isinstance(self.slow, int)
            or isinstance(self.slow, bool)
            or (self.fast, self.slow) not in _PAIRS
        ):
            raise ValueError("fast and slow must be one of the frozen MA pairs")
        if (
            not isinstance(self.parameter, str)
            or self.parameter not in _PARAMETERS[self.family]
        ):
            raise ValueError("parameter must be declared for the selected family")


_STRATEGY_GRID = tuple(
    StrategyConfig(family, fast, slow, parameter)
    for family in _FAMILIES
    for fast, slow in _PAIRS
    for parameter in _PARAMETERS[family]
)


def strategy_grid() -> tuple[StrategyConfig, ...]:
    """Return the fixed grid in family, MA-pair, then parameter order."""

    return _STRATEGY_GRID


def signal(
    config: StrategyConfig,
    completed_bars: tuple[Bar, ...],
    invested: bool,
) -> str:
    """Return the point-in-time BUY, SELL, or HOLD action for a bar prefix."""

    _require_config(config)
    if not isinstance(invested, bool):
        raise TypeError("invested must be a bool")
    state = signal_series(config, completed_bars)
    if not state:
        return "HOLD"
    latest = state[-1]
    if latest == "BUY" and invested:
        return "HOLD"
    if latest == "SELL" and not invested:
        return "HOLD"
    return latest


def signal_series(
    config: StrategyConfig,
    bars: tuple[Bar, ...],
) -> tuple[str, ...]:
    """Return raw signal states aligned to each completed-bar prefix.

    Result index ``i`` is computed from ``bars[:i + 1]`` only. A caller that
    simulates positions applies BUY/SELL state transitions separately.
    """

    _require_config(config)
    _validate_bars(bars)
    if not bars:
        return ()

    with localcontext(_ARITHMETIC_CONTEXT):
        closes = tuple(bar.close for bar in bars)
        fast_averages = _rolling_averages(closes, config.fast)
        slow_averages = _rolling_averages(closes, config.slow)
        adx_values: tuple[Decimal | None, ...] | None = None
        if config.family == "MA_ADX":
            adx_values = _wilder_adx_values(bars, _ADX_PERIOD)
        donchian_values: tuple[Decimal | None, ...] | None = None
        if config.family == "MA_DONCHIAN":
            donchian_values = _prior_rolling_highs(
                tuple(bar.high for bar in bars), int(config.parameter)
            )
        prior_252_highs: tuple[Decimal | None, ...] | None = None
        if (
            config.family == "MA_LONG_MOMENTUM"
            and config.parameter == "close_at_least_90pct_prior252_high"
        ):
            prior_252_highs = _prior_rolling_highs(tuple(bar.high for bar in bars), 252)

        result: list[str] = []
        for index, (fast_average, slow_average) in enumerate(
            zip(fast_averages, slow_averages, strict=True)
        ):
            if fast_average is None or slow_average is None:
                result.append("HOLD")
                continue
            if _ma_exit_triggered(config, fast_average, slow_average):
                # Entry filters never defer the family's configured MA exit.
                result.append("SELL")
                continue
            if fast_average <= slow_average:
                # Equality is neutral and cannot open or retain an entry signal.
                result.append("HOLD")
                continue
            if _entry_filter_passes(
                config,
                index,
                bars,
                fast_average,
                slow_average,
                adx_values,
                donchian_values,
                prior_252_highs,
            ):
                result.append("BUY")
            else:
                result.append("HOLD")
        return tuple(result)


def wilder_atr(
    bars: tuple[Bar, ...], period: int = _ATR_PERIOD
) -> tuple[Decimal | None, ...]:
    """Return Wilder ATR values aligned to bars, with warmup as ``None``.

    The initial ATR is the arithmetic mean of the first ``period`` true ranges;
    subsequent values use Wilder's recursive smoothing.
    """

    _validate_bars(bars)
    _validate_period(period)
    with localcontext(_ARITHMETIC_CONTEXT):
        true_ranges, _, _ = _directional_components(bars)
        result: list[Decimal | None] = [None] * len(bars)
        if len(bars) <= period:
            return tuple(result)
        smoothed_true_range = sum(
            (value for value in true_ranges[1 : period + 1] if value is not None),
            start=_ZERO,
        )
        result[period] = smoothed_true_range / Decimal(period)
        for index in range(period + 1, len(bars)):
            current = true_ranges[index]
            assert current is not None
            smoothed_true_range = (
                smoothed_true_range - smoothed_true_range / Decimal(period) + current
            )
            result[index] = smoothed_true_range / Decimal(period)
        return tuple(result)


def wilder_adx(
    bars: tuple[Bar, ...], period: int = _ADX_PERIOD
) -> tuple[Decimal | None, ...]:
    """Return Wilder ADX values aligned to bars, with warmup as ``None``."""

    _validate_bars(bars)
    _validate_period(period)
    with localcontext(_ARITHMETIC_CONTEXT):
        return _wilder_adx_values(bars, period)


def _entry_filter_passes(
    config: StrategyConfig,
    index: int,
    bars: tuple[Bar, ...],
    fast_average: Decimal,
    slow_average: Decimal,
    adx_values: tuple[Decimal | None, ...] | None,
    donchian_values: tuple[Decimal | None, ...] | None,
    prior_252_highs: tuple[Decimal | None, ...] | None,
) -> bool:
    family = config.family
    if family == "BASE_MA":
        return True
    if family == "MA_PERCENT_BAND":
        band = Decimal(config.parameter)
        return fast_average > slow_average * (_ONE + band)
    if family == "MA_ADX":
        assert adx_values is not None
        current_adx = adx_values[index]
        previous_adx = adx_values[index - 1] if index else None
        if config.parameter == "20":
            return current_adx is not None and current_adx >= Decimal("20")
        assert config.parameter == "25"
        return (
            current_adx is not None
            and previous_adx is not None
            and current_adx >= Decimal("25")
            and current_adx > previous_adx
        )
    if family == "MA_DONCHIAN":
        assert donchian_values is not None
        prior_high = donchian_values[index]
        return prior_high is not None and bars[index].close > prior_high
    if config.parameter == "return252_positive":
        return index >= 252 and bars[index].close > bars[index - 252].close
    assert prior_252_highs is not None
    prior_high = prior_252_highs[index]
    return prior_high is not None and bars[index].close >= prior_high * Decimal("0.9")


def _ma_exit_triggered(
    config: StrategyConfig, fast_average: Decimal, slow_average: Decimal
) -> bool:
    if config.family == "MA_PERCENT_BAND":
        band = Decimal(config.parameter)
        return fast_average < slow_average * (_ONE - band)
    return fast_average < slow_average


def _rolling_averages(
    values: tuple[Decimal, ...], window: int
) -> tuple[Decimal | None, ...]:
    running_total = _ZERO
    result: list[Decimal | None] = []
    for index, value in enumerate(values):
        running_total += value
        if index >= window:
            running_total -= values[index - window]
        if index + 1 < window:
            result.append(None)
        else:
            result.append(running_total / Decimal(window))
    return tuple(result)


def _prior_rolling_highs(
    highs: tuple[Decimal, ...], window: int
) -> tuple[Decimal | None, ...]:
    """Return prior-window highs; the current bar is inserted after lookup."""

    candidates: deque[int] = deque()
    result: list[Decimal | None] = []
    for index, high in enumerate(highs):
        first_in_window = index - window
        while candidates and candidates[0] < first_in_window:
            candidates.popleft()
        result.append(highs[candidates[0]] if index >= window else None)
        while candidates and highs[candidates[-1]] <= high:
            candidates.pop()
        candidates.append(index)
    return tuple(result)


def _directional_components(
    bars: tuple[Bar, ...],
) -> tuple[
    tuple[Decimal | None, ...],
    tuple[Decimal | None, ...],
    tuple[Decimal | None, ...],
]:
    true_ranges: list[Decimal | None] = [None] * len(bars)
    positive_dm: list[Decimal | None] = [None] * len(bars)
    negative_dm: list[Decimal | None] = [None] * len(bars)
    for index in range(1, len(bars)):
        current = bars[index]
        previous = bars[index - 1]
        upward_move = current.high - previous.high
        downward_move = previous.low - current.low
        true_ranges[index] = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        positive_dm[index] = (
            upward_move
            if upward_move > downward_move and upward_move > _ZERO
            else _ZERO
        )
        negative_dm[index] = (
            downward_move
            if downward_move > upward_move and downward_move > _ZERO
            else _ZERO
        )
    return tuple(true_ranges), tuple(positive_dm), tuple(negative_dm)


def _wilder_adx_values(
    bars: tuple[Bar, ...], period: int
) -> tuple[Decimal | None, ...]:
    true_ranges, positive_dm, negative_dm = _directional_components(bars)
    result: list[Decimal | None] = [None] * len(bars)
    if len(bars) <= period:
        return tuple(result)

    divisor = Decimal(period)
    smoothed_true_range = sum(
        (value for value in true_ranges[1 : period + 1] if value is not None),
        start=_ZERO,
    )
    smoothed_positive_dm = sum(
        (value for value in positive_dm[1 : period + 1] if value is not None),
        start=_ZERO,
    )
    smoothed_negative_dm = sum(
        (value for value in negative_dm[1 : period + 1] if value is not None),
        start=_ZERO,
    )
    dx_values: list[Decimal] = []
    previous_adx: Decimal | None = None

    for index in range(period, len(bars)):
        if index > period:
            current_tr = true_ranges[index]
            current_positive = positive_dm[index]
            current_negative = negative_dm[index]
            assert current_tr is not None
            assert current_positive is not None
            assert current_negative is not None
            smoothed_true_range = (
                smoothed_true_range - smoothed_true_range / divisor + current_tr
            )
            smoothed_positive_dm = (
                smoothed_positive_dm - smoothed_positive_dm / divisor + current_positive
            )
            smoothed_negative_dm = (
                smoothed_negative_dm - smoothed_negative_dm / divisor + current_negative
            )

        if smoothed_true_range == _ZERO:
            current_dx = _ZERO
        else:
            positive_di = _HUNDRED * smoothed_positive_dm / smoothed_true_range
            negative_di = _HUNDRED * smoothed_negative_dm / smoothed_true_range
            directional_sum = positive_di + negative_di
            current_dx = (
                _ZERO
                if directional_sum == _ZERO
                else _HUNDRED * abs(positive_di - negative_di) / directional_sum
            )
        dx_values.append(current_dx)

        if len(dx_values) == period:
            previous_adx = sum(dx_values, start=_ZERO) / divisor
            result[index] = previous_adx
        elif len(dx_values) > period:
            assert previous_adx is not None
            previous_adx = (previous_adx * (divisor - _ONE) + current_dx) / divisor
            result[index] = previous_adx
    return tuple(result)


def _validate_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError("period must be a positive integer")


def _require_config(config: StrategyConfig) -> None:
    if not isinstance(config, StrategyConfig):
        raise TypeError("config must be a StrategyConfig")


def _validate_bars(bars: tuple[Bar, ...]) -> None:
    if not isinstance(bars, tuple):
        raise TypeError("bars must be a tuple of Bar values")
    previous: Bar | None = None
    for bar in bars:
        if not isinstance(bar, Bar):
            raise TypeError("bars must contain only Bar values")
        if previous is not None:
            if bar.symbol != previous.symbol:
                raise ValueError("bars must contain one symbol")
            if bar.timestamp <= previous.timestamp:
                raise ValueError("bars must be in strictly increasing time order")
        previous = bar
