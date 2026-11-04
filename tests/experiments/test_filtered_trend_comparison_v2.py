"""Focused coverage for the frozen comparison v2 signal primitives."""

from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext

import pytest

from trading_bot.domain.market import Bar, Symbol
from trading_bot.experiments.filtered_trend_comparison_v2 import (
    CANDIDATES,
    Candidate,
    required_closes,
    signal,
    signal_series,
)
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig
from trading_bot.experiments.filtered_trend_strategies import signal as v1_signal
from trading_bot.experiments.filtered_trend_strategies import (
    signal_series as v1_signal_series,
)


def _bars(closes: list[Decimal], *, symbol: str = "SPY") -> tuple[Bar, ...]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    instrument = Symbol(symbol)
    return tuple(
        Bar(
            symbol=instrument,
            timestamp=start + timedelta(days=index),
            open=close,
            high=close + Decimal("1"),
            low=close - Decimal("1"),
            close=close,
            volume=1,
        )
        for index, close in enumerate(closes)
    )


def _base_config() -> StrategyConfig:
    return StrategyConfig("BASE_MA", 35, 50, "none")


def test_candidate_order_and_exact_warmups() -> None:
    assert CANDIDATES == (
        Candidate.BASE_MA35_50_V1,
        Candidate.PRICE_SMA200_V1,
        Candidate.PRICE_MOM_252_V1,
    )
    assert tuple(required_closes(candidate) for candidate in CANDIDATES) == (
        50,
        200,
        253,
    )


@pytest.mark.parametrize(
    ("candidate", "warmup"),
    (
        (Candidate.BASE_MA35_50_V1, 50),
        (Candidate.PRICE_SMA200_V1, 200),
        (Candidate.PRICE_MOM_252_V1, 253),
    ),
)
def test_signal_series_is_hold_before_exact_first_valid_index(
    candidate: Candidate, warmup: int
) -> None:
    bars = _bars([Decimal("100")] * (warmup - 1))
    states = signal_series(candidate, bars)

    assert len(states) == warmup - 1
    assert states == ("HOLD",) * (warmup - 1)
    assert signal(candidate, bars, invested=False) == "HOLD"

    first_valid = signal_series(
        candidate, _bars([Decimal("100")] * (warmup - 1) + [Decimal("101")])
    )
    assert len(first_valid) == warmup
    assert first_valid[-1] in ("BUY", "SELL", "HOLD")


def test_sma200_uses_200_closes_and_holds_on_equality() -> None:
    equal = _bars([Decimal("100")] * 200)

    assert signal_series(Candidate.PRICE_SMA200_V1, equal)[198] == "HOLD"
    assert signal_series(Candidate.PRICE_SMA200_V1, equal)[199] == "HOLD"
    assert signal(Candidate.PRICE_SMA200_V1, equal, invested=True) == "HOLD"
    assert signal(Candidate.PRICE_SMA200_V1, equal, invested=False) == "HOLD"

    bullish = _bars([Decimal("100")] * 199 + [Decimal("101")])
    assert signal_series(Candidate.PRICE_SMA200_V1, bullish)[199] == "BUY"
    assert signal(Candidate.PRICE_SMA200_V1, bullish, invested=False) == "BUY"
    assert signal(Candidate.PRICE_SMA200_V1, bullish, invested=True) == "HOLD"


def test_momentum_compares_current_close_with_exact_252_session_lag() -> None:
    equal = _bars([Decimal("100")] * 253)

    assert signal_series(Candidate.PRICE_MOM_252_V1, equal)[251] == "HOLD"
    assert signal_series(Candidate.PRICE_MOM_252_V1, equal)[252] == "HOLD"
    assert signal(Candidate.PRICE_MOM_252_V1, equal, invested=True) == "HOLD"
    assert signal(Candidate.PRICE_MOM_252_V1, equal, invested=False) == "HOLD"

    bullish = _bars([Decimal("100")] * 252 + [Decimal("101")])
    assert signal_series(Candidate.PRICE_MOM_252_V1, bullish)[252] == "BUY"
    assert signal(Candidate.PRICE_MOM_252_V1, bullish, invested=False) == "BUY"
    assert signal(Candidate.PRICE_MOM_252_V1, bullish, invested=True) == "HOLD"


def test_signal_position_mapping_for_both_directional_candidates() -> None:
    for candidate, bullish in (
        (
            Candidate.PRICE_SMA200_V1,
            _bars([Decimal("100")] * 199 + [Decimal("101")]),
        ),
        (
            Candidate.PRICE_MOM_252_V1,
            _bars([Decimal("100")] * 252 + [Decimal("101")]),
        ),
    ):
        assert signal(candidate, bullish, invested=False) == "BUY"
        assert signal(candidate, bullish, invested=True) == "HOLD"

        bearish = _bars(
            [Decimal("100")] * (required_closes(candidate) - 1) + [Decimal("99")]
        )
        assert signal(candidate, bearish, invested=True) == "SELL"
        assert signal(candidate, bearish, invested=False) == "HOLD"


def test_base_candidate_matches_v1_signal_and_equality_semantics() -> None:
    config = _base_config()
    equal = _bars([Decimal("100")] * 50)
    equal_states = signal_series(Candidate.BASE_MA35_50_V1, equal)
    expected_equal = v1_signal_series(config, equal)

    assert equal_states[:49] == ("HOLD",) * 49
    assert equal_states[49:] == expected_equal[49:]
    assert equal_states[49] == "HOLD"
    assert (
        signal(Candidate.BASE_MA35_50_V1, equal, invested=True)
        == v1_signal(config, equal, True)
        == "HOLD"
    )

    rising = _bars([Decimal(100 + index) for index in range(80)])
    falling = _bars(
        [Decimal("100")] * 70 + [Decimal(169 - index) for index in range(1, 40)]
    )
    for bars in (rising, falling):
        assert (
            signal_series(Candidate.BASE_MA35_50_V1, bars)[49:]
            == (v1_signal_series(config, bars)[49:])
        )
        for invested in (False, True):
            assert signal(Candidate.BASE_MA35_50_V1, bars, invested=invested) == (
                v1_signal(config, bars, invested)
            )


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_signal_series_is_invariant_to_future_suffix(candidate: Candidate) -> None:
    closes = [Decimal(100 + index) for index in range(270)]
    prefix = _bars(closes[:260])
    complete = _bars(closes)

    assert signal_series(candidate, complete)[: len(prefix)] == signal_series(
        candidate, prefix
    )


def test_inputs_must_be_ordered_single_symbol_finite_immutable_bars() -> None:
    bars = _bars([Decimal("100")] * 50)

    with pytest.raises(TypeError, match="tuple"):
        signal_series(Candidate.BASE_MA35_50_V1, list(bars))  # type: ignore[arg-type]

    mixed = bars[:1] + _bars([Decimal("100")], symbol="QQQ")
    with pytest.raises(ValueError, match="one symbol"):
        signal_series(Candidate.BASE_MA35_50_V1, mixed)

    out_of_order = (bars[1], bars[0])
    with pytest.raises(ValueError, match="increasing"):
        signal_series(Candidate.BASE_MA35_50_V1, out_of_order)

    duplicate_time = (bars[0], bars[0])
    with pytest.raises(ValueError, match="increasing"):
        signal_series(Candidate.BASE_MA35_50_V1, duplicate_time)

    timestamp = datetime(2020, 1, 1, tzinfo=UTC)
    infinite = Bar(
        symbol=Symbol("SPY"),
        timestamp=timestamp,
        open=Decimal("Infinity"),
        high=Decimal("Infinity"),
        low=Decimal("Infinity"),
        close=Decimal("Infinity"),
        volume=1,
    )
    with pytest.raises(ValueError, match="finite"):
        signal_series(Candidate.PRICE_SMA200_V1, (infinite,))


def test_candidate_and_invested_arguments_are_strict() -> None:
    bars = _bars([Decimal("100")] * 50)

    with pytest.raises(TypeError, match="Candidate"):
        required_closes("BASE_MA35_50_V1")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="invested"):
        signal(Candidate.BASE_MA35_50_V1, bars, invested=1)  # type: ignore[arg-type]


def test_decimal_results_do_not_depend_on_ambient_context() -> None:
    close_to_mean = _bars([Decimal("123.4501")] * 199 + [Decimal("123.45")])
    momentum = _bars([Decimal("100")] * 252 + [Decimal("101")])
    candidates_bars = {
        Candidate.BASE_MA35_50_V1: _bars([Decimal(100 + index) for index in range(80)]),
        Candidate.PRICE_SMA200_V1: close_to_mean,
        Candidate.PRICE_MOM_252_V1: momentum,
    }

    with localcontext(Context(prec=2)):
        low_precision = {
            candidate: signal_series(candidate, bars)
            for candidate, bars in candidates_bars.items()
        }
    with localcontext(Context(prec=80)):
        high_precision = {
            candidate: signal_series(candidate, bars)
            for candidate, bars in candidates_bars.items()
        }

    assert low_precision == high_precision
    assert low_precision[Candidate.PRICE_SMA200_V1][-1] == "SELL"
