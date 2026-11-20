"""Focused fake-only sparse execution tests for Architecture 148."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import arch148_intraday as intraday
from trading_bot.experiments.arch148_churn_policy import ChurnPolicy
from trading_bot.experiments.arch148_sparse_backtest import run_sparse_backtest
from trading_bot.live_runtime.models import (
    MarketQuality,
    MarketRegime,
    SignalAnalysis,
    SignalPoint,
)


def _dataset(
    day: date,
    *,
    missing: dict[str, set[int]] | None = None,
    overrides: dict[str, dict[int, tuple[str, str, str, str]]] | None = None,
) -> intraday.SparseIntradayDataset:
    missing = missing or {}
    overrides = overrides or {}
    slots = intraday.session_slots(day)
    datasets = []
    for symbol in intraday.INTRADAY_SYMBOLS:
        bars = []
        for index, timestamp in enumerate(slots):
            if index in missing.get(symbol, set()):
                continue
            values = overrides.get(symbol, {}).get(index, ("100", "101", "99", "100"))
            bars.append(
                Bar(
                    Symbol(symbol),
                    timestamp,
                    Decimal(values[0]),
                    Decimal(values[1]),
                    Decimal(values[2]),
                    Decimal(values[3]),
                    100,
                )
            )
        datasets.append(intraday.IntradaySymbolDataset(symbol, tuple(bars)))
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return intraday.SparseIntradayDataset(start, end, tuple(datasets))


def _dataset_for_days(days: tuple[date, ...]) -> intraday.SparseIntradayDataset:
    datasets = []
    for symbol in intraday.INTRADAY_SYMBOLS:
        bars = tuple(
            Bar(
                Symbol(symbol),
                timestamp,
                Decimal("100"),
                Decimal("101"),
                Decimal("99"),
                Decimal("100"),
                100,
            )
            for day in days
            for timestamp in intraday.session_slots(day)
        )
        datasets.append(intraday.IntradaySymbolDataset(symbol, bars))
    start = datetime(days[0].year, days[0].month, days[0].day, tzinfo=UTC)
    end_day = days[-1] + timedelta(days=1)
    end = datetime(end_day.year, end_day.month, end_day.day, tzinfo=UTC)
    return intraday.SparseIntradayDataset(start, end, tuple(datasets))


def _signal(
    *,
    quality: MarketQuality = MarketQuality.READY,
    regime: MarketRegime = MarketRegime.NEUTRAL,
    confirmation: MarketRegime | None = None,
) -> SignalAnalysis:
    return SignalAnalysis(
        quality,
        regime if quality is MarketQuality.READY else None,
        confirmation if quality is MarketQuality.READY else None,
        None,
        None,
        "SYNTHETIC_SPARSE_BACKTEST_SIGNAL",
    )


def _candidate_signal(
    as_of: datetime,
    previous: MarketRegime,
    latest: MarketRegime,
    *,
    confirmation: MarketRegime | None = None,
    quality: MarketQuality = MarketQuality.READY,
    previous_end: datetime | None = None,
) -> SignalAnalysis:
    latest_point = SignalPoint(
        as_of,
        Decimal("100"),
        Decimal("100"),
        Decimal("100"),
        Decimal("100"),
        Decimal("50"),
        latest,
    )
    previous_point = SignalPoint(
        previous_end or as_of - timedelta(minutes=5),
        Decimal("100"),
        Decimal("100"),
        Decimal("100"),
        Decimal("100"),
        Decimal("50"),
        previous,
    )
    return SignalAnalysis(
        quality,
        latest if quality is MarketQuality.READY else None,
        confirmation if quality is MarketQuality.READY else None,
        latest_point,
        previous_point,
        "SYNTHETIC_COMPLETED_CHURN_SIGNAL",
    )


def test_missing_entry_bar_skips_that_signal_without_delayed_fill() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day, missing={"TQQQ": {3}})
    seen_last_qqq_bar: list[datetime] = []

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            seen_last_qqq_bar.append(market.completed_bars[-1].timestamp)
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        return _signal()

    result = run_sparse_backtest(dataset, analyzer=analyzer)
    assert seen_last_qqq_bar == [slots[2]]
    assert result.trade_count == 0
    assert result.trades == ()


def test_default_sparse_backtest_replays_with_real_completed_bars() -> None:
    day = date(2023, 11, 27)
    slots = intraday.session_slots(day)
    dataset = _dataset(day)

    result = intraday.run_backtest(dataset)
    direct = run_sparse_backtest(dataset)

    assert result == direct
    assert result.dataset_identity == dataset.identity
    assert result.trade_count == 0
    assert result.equity_curve == (Decimal("10000"),) * len(slots)


def test_control_default_matches_prechange_neutral_exit_fixture() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day)

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of == slots[4]:
            return _candidate_signal(
                market.as_of, MarketRegime.NEUTRAL, MarketRegime.NEUTRAL
            )
        return _signal()

    default = run_sparse_backtest(dataset, analyzer=analyzer)
    explicit_control = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=ChurnPolicy.CONTROL,
    )
    routed = intraday.run_backtest(dataset, analyzer=analyzer)
    expected_trade = intraday.BacktestTrade(
        "TQQQ",
        slots[3],
        Decimal("100"),
        slots[4],
        Decimal("100"),
        Decimal("100"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        "REGIME_EXIT",
        timedelta(minutes=5),
    )
    expected = intraday.BacktestResult(
        dataset.identity,
        intraday.ZERO_COST.name,
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        1,
        0,
        0,
        0,
        Decimal("20000"),
        timedelta(minutes=5),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        (expected_trade,),
        (Decimal("10000"),) * len(slots),
    )

    assert default == explicit_control == routed == expected


def test_entry_bar_hard_stop_still_has_priority() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(
        day,
        overrides={"TQQQ": {3: ("100", "101", "96", "100")}},
    )

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        return _signal()

    result = run_sparse_backtest(dataset, analyzer=analyzer)

    assert result.trade_count == 1
    assert result.stop_hit_count == 1
    assert result.trades[0].entry_at == slots[3]
    assert result.trades[0].exit_at == slots[3]
    assert result.trades[0].exit_reason == "STOP"
    assert result.trades[0].exit_price == Decimal("97.00")


def test_opposite_confirmation_exit_ignores_neutral_candidates() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day)

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of >= slots[4]:
            return _candidate_signal(
                market.as_of, MarketRegime.NEUTRAL, MarketRegime.NEUTRAL
            )
        return _signal()

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=ChurnPolicy.OPPOSITE_CONFIRMATION_EXIT,
    )

    assert result.trade_count == 1
    assert result.reversal_exits == 0
    assert result.forced_flat_count == 1
    assert result.trades[0].exit_reason == "FORCED_FLAT"
    assert result.trades[0].exit_at == slots[-1]


def test_opposite_confirmation_exit_requires_two_adjacent_opposite_bars() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day)

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of == slots[4]:
            return _candidate_signal(
                market.as_of,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
            )
        return _signal()

    settled_trades = []

    def record_closed_trade(trade, trade_turnover, reversal_source):
        settled_trades.append((trade, trade_turnover, reversal_source))

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=ChurnPolicy.OPPOSITE_CONFIRMATION_EXIT,
        on_trade_close=record_closed_trade,
    )

    assert result.trade_count == 1
    assert result.reversal_exits == 1
    assert result.trades[0].exit_reason == "REGIME_EXIT"
    assert result.trades[0].exit_at == slots[4]
    assert settled_trades == [(result.trades[0], result.turnover, MarketRegime.BEARISH)]


def test_nonadjacent_opposite_candidates_do_not_exit_a_sparse_position() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day)

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of >= slots[4]:
            return _candidate_signal(
                market.as_of,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
                previous_end=market.as_of - timedelta(minutes=10),
            )
        return _signal()

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=ChurnPolicy.OPPOSITE_CONFIRMATION_EXIT,
    )

    assert result.trade_count == 1
    assert result.reversal_exits == 0
    assert result.trades[0].exit_reason == "FORCED_FLAT"
    assert result.trades[0].exit_at == slots[-1]


@pytest.mark.parametrize(
    ("policy", "release_index"),
    [
        (ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_15M, 7),
        (ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_30M, 10),
    ],
)
def test_cooldown_blocks_until_inclusive_elapsed_minute_boundary(
    policy: ChurnPolicy, release_index: int
) -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day)

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of >= slots[4]:
            return _candidate_signal(
                market.as_of,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
            )
        return _signal()

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=policy,
    )

    assert result.trade_count == 2
    assert result.trades[0].exit_reason == "REGIME_EXIT"
    assert result.trades[0].exit_at == slots[4]
    assert result.trades[1].symbol == "SQQQ"
    assert result.trades[1].entry_at == slots[release_index]
    assert result.reversal_exits == 1


def test_safety_exit_does_not_start_regime_cooldown() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day, missing={"TQQQ": {4}})

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of == slots[4]:
            return _signal(quality=MarketQuality.GAP)
        if market.as_of >= slots[5]:
            return _candidate_signal(
                market.as_of,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
            )
        return _signal()

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_30M,
    )

    assert result.trades[0].exit_reason == "SAFETY"
    assert result.trades[0].exit_at == slots[5]
    assert result.trades[1].symbol == "SQQQ"
    assert result.trades[1].entry_at == slots[6]


def test_cooldown_starts_when_a_delayed_regime_exit_fills() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day, missing={"TQQQ": {4}})

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of == slots[4]:
            return _candidate_signal(
                market.as_of,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
            )
        if market.as_of >= slots[5]:
            return _candidate_signal(
                market.as_of,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
            )
        return _signal()

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_15M,
    )

    assert result.trades[0].exit_reason == "REGIME_EXIT"
    assert result.trades[0].exit_at == slots[5]
    assert result.trades[1].symbol == "SQQQ"
    assert result.trades[1].entry_at == slots[8]


def test_regime_cooldown_resets_at_the_next_session_boundary() -> None:
    friday = date(2023, 11, 24)
    monday = date(2023, 11, 27)
    friday_slots = intraday.session_slots(friday)
    monday_slots = intraday.session_slots(monday)
    dataset = _dataset_for_days((friday, monday))

    def analyzer(market, *, authority):
        if market.as_of == friday_slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of == friday_slots[-3]:
            return _candidate_signal(
                market.as_of, MarketRegime.NEUTRAL, MarketRegime.BEARISH
            )
        if market.as_of == friday_slots[-2]:
            return _candidate_signal(
                market.as_of,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
            )
        if market.as_of == monday_slots[3]:
            return _signal(
                regime=MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
            )
        return _signal()

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_30M,
    )

    assert result.trades[0].exit_reason == "REGIME_EXIT"
    assert result.trades[0].exit_at == friday_slots[-2]
    assert result.trades[1].symbol == "SQQQ"
    assert result.trades[1].entry_at == monday_slots[3]


def test_stop_precedes_opposite_signal_and_does_not_start_cooldown() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(
        day,
        overrides={"TQQQ": {4: ("100", "101", "96", "100")}},
    )

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of >= slots[4]:
            return _candidate_signal(
                market.as_of,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                confirmation=MarketRegime.BEARISH,
            )
        return _signal()

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        churn_policy=ChurnPolicy.OPPOSITE_EXIT_COOLDOWN_30M,
    )

    assert result.stop_hit_count == 1
    assert result.reversal_exits == 0
    assert result.trades[0].exit_reason == "STOP"
    assert result.trades[0].exit_at == slots[4]
    assert result.trades[1].symbol == "SQQQ"
    assert result.trades[1].entry_at == slots[5]


@pytest.mark.parametrize(
    ("entry_bar", "expected_reason", "expected_price", "expected_stop_count"),
    [
        (("98", "99", "98", "98"), "SAFETY", Decimal("98"), 0),
        (("98", "99", "96", "98"), "STOP", Decimal("97.09700"), 1),
        (("95", "96", "94", "95"), "STOP", Decimal("95"), 1),
    ],
)
def test_pending_exit_uses_first_later_real_bar_with_stop_priority(
    entry_bar, expected_reason, expected_price, expected_stop_count
) -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(
        day,
        missing={"TQQQ": {4}},
        overrides={"TQQQ": {5: entry_bar}},
    )

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of == slots[4]:
            return _signal(quality=MarketQuality.GAP)
        return _signal()

    expected = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        cost_model=intraday.CONSERVATIVE_COSTS,
    )
    with localcontext() as context:
        context.prec = 3
        result = run_sparse_backtest(
            dataset,
            analyzer=analyzer,
            cost_model=intraday.CONSERVATIVE_COSTS,
        )

    assert result == expected
    assert result.trade_count == 1
    assert result.stop_hit_count == expected_stop_count
    assert result.trades[0].entry_at == slots[3]
    assert result.trades[0].exit_at == slots[5]
    assert result.trades[0].exit_reason == expected_reason
    assert result.trades[0].exit_price == expected_price


def test_regime_exit_waits_for_first_later_real_etf_bar() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day, missing={"TQQQ": {4}})

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        if market.as_of == slots[4]:
            previous = SignalPoint(
                slots[3],
                Decimal("100"),
                Decimal("100"),
                Decimal("101"),
                Decimal("100"),
                Decimal("40"),
                MarketRegime.BEARISH,
            )
            latest = SignalPoint(
                slots[4],
                Decimal("99"),
                Decimal("100"),
                Decimal("99"),
                Decimal("100"),
                Decimal("40"),
                MarketRegime.BEARISH,
            )
            return SignalAnalysis(
                MarketQuality.READY,
                MarketRegime.BEARISH,
                MarketRegime.BEARISH,
                latest,
                previous,
                "SYNTHETIC_REGIME_EXIT",
            )
        return _signal()

    result = run_sparse_backtest(dataset, analyzer=analyzer)

    assert result.trade_count == 1
    assert result.reversal_exits == 1
    assert result.trades[0].exit_at == slots[5]
    assert result.trades[0].exit_reason == "REGIME_EXIT"
    assert result.trades[0].exit_price == Decimal("100")


def test_sparse_valuation_skips_missing_held_etf_marks() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day, missing={"TQQQ": {4}})

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        return _signal()

    equity_marks = []
    settled_trades = []

    def record_closed_trade(trade, trade_turnover, reversal_source):
        settled_trades.append((trade, trade_turnover, reversal_source))

    result = run_sparse_backtest(
        dataset,
        analyzer=analyzer,
        on_equity_mark=lambda at, value: equity_marks.append((at, value)),
        on_trade_close=record_closed_trade,
    )

    assert result.trade_count == 1
    assert result.trades[0].exit_reason == "FORCED_FLAT"
    assert len(result.equity_curve) == len(slots) - 1
    assert [at for at, _ in equity_marks] == [
        slot for slot in slots if slot != slots[4]
    ]
    assert tuple(value for _, value in equity_marks) == result.equity_curve
    assert settled_trades == [(result.trades[0], result.turnover, None)]


def test_unexecutable_forced_flat_fails_the_sparse_session() -> None:
    day = date(2023, 11, 24)
    slots = intraday.session_slots(day)
    dataset = _dataset(day, missing={"TQQQ": {len(slots) - 1}})

    def analyzer(market, *, authority):
        if market.as_of == slots[3]:
            return _signal(
                regime=MarketRegime.BULLISH,
                confirmation=MarketRegime.BULLISH,
            )
        return _signal()

    with pytest.raises(
        intraday.Arch148IntradayError,
        match="forced-flat requirement was unexecutable",
    ):
        run_sparse_backtest(dataset, analyzer=analyzer)
