"""Frozen deterministic trend candidates for the v2 research comparison."""

from __future__ import annotations

from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum

from trading_bot.domain.market import Bar
from trading_bot.experiments.filtered_trend_strategies import (
    StrategyConfig as _StrategyConfig,
)
from trading_bot.experiments.filtered_trend_strategies import (
    signal as _base_signal,
)
from trading_bot.experiments.filtered_trend_strategies import (
    signal_series as _base_signal_series,
)


class Candidate(StrEnum):
    """One of the three candidates frozen for comparison v2."""

    BASE_MA35_50_V1 = "BASE_MA35_50_V1"
    PRICE_SMA200_V1 = "PRICE_SMA200_V1"
    PRICE_MOM_252_V1 = "PRICE_MOM_252_V1"


CANDIDATES = (
    Candidate.BASE_MA35_50_V1,
    Candidate.PRICE_SMA200_V1,
    Candidate.PRICE_MOM_252_V1,
)

_BASE_CONFIG = _StrategyConfig("BASE_MA", 35, 50, "none")
_REQUIRED_CLOSES = {
    Candidate.BASE_MA35_50_V1: 50,
    Candidate.PRICE_SMA200_V1: 200,
    Candidate.PRICE_MOM_252_V1: 253,
}
_SMA_WINDOW = 200
_MOMENTUM_LAG = 252
_ZERO = Decimal("0")
_ONE = Decimal("1")
_ARITHMETIC_CONTEXT = Context(
    prec=50,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)


def required_closes(candidate: Candidate) -> int:
    """Return the minimum completed-close count needed for a first signal."""

    _require_candidate(candidate)
    return _REQUIRED_CLOSES[candidate]


def signal(
    candidate: Candidate,
    bars: tuple[Bar, ...],
    *,
    invested: bool,
) -> str:
    """Return BUY, SELL, or HOLD for one completed-bar prefix.

    The caller supplies only completed bars through the information session.
    A resulting order is for a later session; this function never reads future
    bars or constructs execution data.
    """

    _require_candidate(candidate)
    _validate_bars(bars)
    if type(invested) is not bool:
        raise TypeError("invested must be a bool")
    if len(bars) < required_closes(candidate):
        raise ValueError("insufficient completed bars for candidate warmup")

    if candidate is Candidate.BASE_MA35_50_V1:
        return _base_signal(_BASE_CONFIG, bars, invested)
    state = _signal_series_validated(candidate, bars)[-1]
    if state is None:
        raise ValueError("candidate signal is unavailable")
    if state == "HOLD":
        return "HOLD"
    if state == "BUY":
        return "HOLD" if invested else "BUY"
    return "SELL" if invested else "HOLD"


def signal_series(
    candidate: Candidate,
    bars: tuple[Bar, ...],
) -> tuple[str | None, ...]:
    """Return raw candidate intentions aligned to each completed-bar prefix.

    Entries before the candidate's exact warmup window are None. Later entries
    are BUY or SELL for the independent price rules; the accepted BASE_MA rule
    retains its existing HOLD-at-equality behavior.
    """

    _require_candidate(candidate)
    _validate_bars(bars)
    return _signal_series_validated(candidate, bars)


def _signal_series_validated(
    candidate: Candidate,
    bars: tuple[Bar, ...],
) -> tuple[str | None, ...]:
    warmup = required_closes(candidate)
    if candidate is Candidate.BASE_MA35_50_V1:
        states = _base_signal_series(_BASE_CONFIG, bars)
        return tuple(
            None if index < warmup - 1 else state for index, state in enumerate(states)
        )

    result: list[str | None] = [None] * len(bars)
    if candidate is Candidate.PRICE_SMA200_V1:
        with localcontext(_ARITHMETIC_CONTEXT):
            rolling_total = _ZERO
            for index, bar in enumerate(bars):
                rolling_total += bar.close
                if index >= _SMA_WINDOW:
                    rolling_total -= bars[index - _SMA_WINDOW].close
                if index >= _SMA_WINDOW - 1:
                    average = rolling_total / Decimal(_SMA_WINDOW)
                    result[index] = "BUY" if bar.close > average else "SELL"
        return tuple(result)

    if candidate is Candidate.PRICE_MOM_252_V1:
        for index in range(_MOMENTUM_LAG, len(bars)):
            result[index] = (
                "BUY"
                if bars[index].close > bars[index - _MOMENTUM_LAG].close
                else "SELL"
            )
        return tuple(result)

    raise ValueError("unsupported candidate")


def _require_candidate(candidate: Candidate) -> None:
    if not isinstance(candidate, Candidate):
        raise TypeError("candidate must be a Candidate")


def _validate_bars(bars: tuple[Bar, ...]) -> None:
    if not isinstance(bars, tuple):
        raise TypeError("bars must be an immutable tuple of Bar values")

    previous: Bar | None = None
    for bar in bars:
        if type(bar) is not Bar:
            raise TypeError("bars must contain only immutable Bar values")
        if previous is not None:
            if bar.symbol != previous.symbol:
                raise ValueError("bars must contain one symbol")
            if bar.timestamp <= previous.timestamp:
                raise ValueError("bars must be strictly increasing in time")
        for value in (bar.open, bar.high, bar.low, bar.close):
            if (
                not isinstance(value, Decimal)
                or not value.is_finite()
                or value <= _ZERO
            ):
                raise ValueError("bars must contain finite positive prices")
        previous = bar
