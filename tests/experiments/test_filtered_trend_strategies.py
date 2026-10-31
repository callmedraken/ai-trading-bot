"""Coverage for deterministic filtered trend signal primitives."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext

import pytest

import trading_bot.experiments.filtered_trend_strategies as strategies
from trading_bot.domain.market import Bar, Symbol
from trading_bot.experiments.filtered_trend_strategies import (
    StrategyConfig,
    signal,
    signal_series,
    strategy_grid,
    wilder_adx,
    wilder_atr,
)


def _bars(
    closes: list[Decimal],
    *,
    high_pad: Decimal = Decimal("0.1"),
    low_pad: Decimal = Decimal("0.1"),
) -> tuple[Bar, ...]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    symbol = Symbol("SPY")
    return tuple(
        Bar(
            symbol=symbol,
            timestamp=start + timedelta(days=index),
            open=close,
            high=close + high_pad,
            low=close - low_pad,
            close=close,
            volume=1,
        )
        for index, close in enumerate(closes)
    )


def _config(family: str, parameter: str, fast: int = 35, slow: int = 50):
    return StrategyConfig(family, fast, slow, parameter)


def test_grid_has_exact_frozen_30_configurations() -> None:
    grid = strategy_grid()
    pairs = ((35, 50), (55, 100), (50, 200))
    assert len(grid) == 30
    assert len(set(grid)) == 30
    expected = tuple(
        StrategyConfig(family, fast, slow, parameter)
        for family, parameters in (
            ("BASE_MA", ("none",)),
            ("MA_PERCENT_BAND", ("0.005", "0.010", "0.015")),
            ("MA_ADX", ("20", "25")),
            ("MA_DONCHIAN", ("20", "55")),
            (
                "MA_LONG_MOMENTUM",
                ("return252_positive", "close_at_least_90pct_prior252_high"),
            ),
        )
        for fast, slow in pairs
        for parameter in parameters
    )
    assert grid == expected
    with pytest.raises(FrozenInstanceError):
        grid[0].fast = 1  # type: ignore[misc]


def test_signal_suppresses_redundant_position_actions() -> None:
    rising = _bars([Decimal(100) + Decimal(index) / 10 for index in range(260)])
    bullish = _config("BASE_MA", "none")
    assert signal(bullish, rising, invested=False) == "BUY"
    assert signal(bullish, rising, invested=True) == "HOLD"

    falling_closes = [Decimal("100")] * 100 + [
        Decimal(200 - index) for index in range(1, 121)
    ]
    falling = _bars(falling_closes)
    assert signal(bullish, falling, invested=True) == "SELL"
    assert signal(bullish, falling, invested=False) == "HOLD"


def test_percent_band_uses_fast_average_gap_over_slow_average() -> None:
    bars = _bars([Decimal("100")] * 50 + [Decimal("102")] * 35)
    assert signal(_config("MA_PERCENT_BAND", "0.005"), bars, False) == "BUY"
    assert signal(_config("MA_PERCENT_BAND", "0.010"), bars, False) == "HOLD"
    assert signal(_config("MA_PERCENT_BAND", "0.015"), bars, False) == "HOLD"


def test_percent_band_holds_inside_hysteresis_and_exits_beyond_it() -> None:
    inside_band = _bars([Decimal("100")] * 50 + [Decimal("99.9")] * 35)
    outside_band = _bars([Decimal("100")] * 50 + [Decimal("90")] * 35)
    config = _config("MA_PERCENT_BAND", "0.005")

    assert signal(config, inside_band, invested=True) == "HOLD"
    assert signal(config, outside_band, invested=True) == "SELL"


def test_ma_warmup_and_equality_are_hold_states() -> None:
    config = _config("BASE_MA", "none")
    insufficient = _bars([Decimal("100")] * 49)
    equality = _bars([Decimal("100")] * 50)

    assert signal(config, insufficient, invested=True) == "HOLD"
    assert signal(config, equality, invested=True) == "HOLD"
    assert signal(config, equality, invested=False) == "HOLD"


def test_non_band_families_exit_on_strictly_bearish_ma_without_confirmation() -> None:
    bars = _bars([Decimal("100")] * 253 + [Decimal("99.9")] * 35)
    for config in strategy_grid():
        if config.family != "MA_PERCENT_BAND":
            assert signal(config, bars, invested=True) == "SELL"


@pytest.mark.parametrize(
    ("current", "previous", "expected_20", "expected_25"),
    [
        ("20", "20", "BUY", "HOLD"),
        ("20", "21", "BUY", "HOLD"),
        ("25", "26", "BUY", "HOLD"),
        ("25", "24", "BUY", "BUY"),
        ("19", "18", "HOLD", "HOLD"),
        ("24", "23", "BUY", "HOLD"),
    ],
)
def test_adx_variants_have_distinct_threshold_and_rising_policies(
    monkeypatch: pytest.MonkeyPatch,
    current: str,
    previous: str,
    expected_20: str,
    expected_25: str,
) -> None:
    bars = _bars([Decimal("100")] * 50 + [Decimal("101")])

    def fake_adx_values(
        fake_bars: tuple[Bar, ...], period: int
    ) -> tuple[Decimal | None, ...]:
        assert fake_bars is bars
        assert period == 14
        values: list[Decimal | None] = [None] * len(fake_bars)
        values[-2] = Decimal(previous)
        values[-1] = Decimal(current)
        return tuple(values)

    monkeypatch.setattr(strategies, "_wilder_adx_values", fake_adx_values)

    assert signal(_config("MA_ADX", "20"), bars, False) == expected_20
    assert signal(_config("MA_ADX", "25"), bars, False) == expected_25


def test_adx_variants_exit_on_bearish_ma_without_adx_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = _bars([Decimal("101")] * 50 + [Decimal("99")])
    monkeypatch.setattr(
        strategies,
        "_wilder_adx_values",
        lambda fake_bars, period: (None,) * len(fake_bars),
    )

    for threshold in ("20", "25"):
        assert signal(_config("MA_ADX", threshold), bars, True) == "SELL"


def test_donchian_breakout_compares_latest_close_to_prior_highs_only() -> None:
    no_breakout = _bars([Decimal("100")] * 260)
    breakout = _bars([Decimal("100")] * 259 + [Decimal("100.5")])
    for window in ("20", "55"):
        config = _config("MA_DONCHIAN", window)
        assert signal(config, no_breakout, False) == "HOLD"
        assert signal(config, breakout, False) == "BUY"


def test_long_momentum_filters_use_prior_252_bars() -> None:
    rising = _bars([Decimal("100") + Decimal(index) / 10 for index in range(260)])
    assert (
        signal(_config("MA_LONG_MOMENTUM", "return252_positive"), rising, False)
        == "BUY"
    )

    closes = [Decimal("120")] + [Decimal("100")] * 251
    closes[200] = Decimal("130")
    closes.append(Decimal("117.1"))
    near_prior_high = _bars(closes)
    assert (
        signal(
            _config("MA_LONG_MOMENTUM", "return252_positive"),
            near_prior_high,
            False,
        )
        == "HOLD"
    )
    assert (
        signal(
            _config("MA_LONG_MOMENTUM", "close_at_least_90pct_prior252_high"),
            near_prior_high,
            False,
        )
        == "BUY"
    )


def test_bearish_ma_exit_is_not_blocked_by_any_entry_filter() -> None:
    closes = [Decimal("100") + Decimal(index) / 10 for index in range(300)]
    closes.extend(Decimal("130") - Decimal(index) / 2 for index in range(1, 251))
    bars = _bars(closes)
    for config in strategy_grid():
        assert signal(config, bars, invested=True) == "SELL", config


def test_wilder_atr_and_adx_have_canonical_warmup_and_values() -> None:
    bars = _bars([Decimal("100") + Decimal(index) / 10 for index in range(50)])
    atr = wilder_atr(bars)
    adx = wilder_adx(bars)

    assert len(atr) == len(bars)
    assert len(adx) == len(bars)
    assert atr[:14] == (None,) * 14
    assert atr[14:] == (Decimal("0.2"),) * (len(bars) - 14)
    assert adx[:27] == (None,) * 27
    assert adx[27:] == (Decimal("100"),) * (len(bars) - 27)


@pytest.mark.parametrize(
    "config",
    [
        _config("BASE_MA", "none"),
        _config("MA_PERCENT_BAND", "0.005"),
        _config("MA_ADX", "20"),
        _config("MA_DONCHIAN", "20"),
        _config("MA_LONG_MOMENTUM", "return252_positive"),
    ],
)
def test_future_execution_bar_cannot_change_completed_prefix_signals(
    config: StrategyConfig,
) -> None:
    prefix = _bars([Decimal("100") + Decimal(index) / 10 for index in range(300)])
    execution_timestamp = prefix[-1].timestamp + timedelta(days=1)
    execution_bar = Bar(
        symbol=prefix[-1].symbol,
        timestamp=execution_timestamp,
        open=Decimal("100"),
        high=Decimal("100.1"),
        low=Decimal("99.9"),
        close=Decimal("100"),
        volume=1,
    )
    changed_execution_bar = Bar(
        symbol=prefix[-1].symbol,
        timestamp=execution_timestamp,
        open=Decimal("100000"),
        high=Decimal("100001"),
        low=Decimal("99999"),
        close=Decimal("100000"),
        volume=1,
    )
    full = prefix + (execution_bar,)
    changed_full = prefix + (changed_execution_bar,)

    prefix_states = signal_series(config, prefix)
    assert signal_series(config, full)[:-1] == prefix_states
    assert signal_series(config, changed_full)[:-1] == prefix_states


def test_decimal_results_ignore_ambient_context() -> None:
    bars = _bars([Decimal("100") + Decimal(index) / 10 for index in range(300)])
    config = _config("MA_PERCENT_BAND", "0.005")
    expected_signals = signal_series(config, bars)
    expected_atr = wilder_atr(bars)
    with localcontext(Context(prec=3)):
        assert signal_series(config, bars) == expected_signals
        assert wilder_atr(bars) == expected_atr


def test_input_validation_rejects_unsupported_configs_and_bar_order() -> None:
    with pytest.raises(ValueError):
        StrategyConfig("MA_ADX", 35, 50, "30")
    bars = _bars([Decimal("100"), Decimal("101")])
    with pytest.raises(ValueError, match="strictly increasing"):
        signal_series(_config("BASE_MA", "none"), (bars[1], bars[0]))
