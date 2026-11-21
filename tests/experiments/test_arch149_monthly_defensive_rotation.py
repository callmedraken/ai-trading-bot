from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import ROUND_FLOOR, Context, Decimal, localcontext
from pathlib import Path

import pytest

import trading_bot.experiments.arch149_monthly_defensive_rotation as rotation
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.arch149_monthly_defensive_rotation import (
    CASH,
    EXPLORATION_END,
    EXPLORATION_START,
    STRATEGY_ID,
    TargetResolution,
    monthly_rotation_identity,
    replay_monthly_defensive_rotation,
    verify_rotation_replay_identity,
)
from trading_bot.experiments.filtered_trend_campaign import (
    ALLOCATION,
    BASE_COSTS,
    STARTING_CASH,
    STRESS_COSTS,
    Costs,
)
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    ProviderProvenance,
    SymbolDataset,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)
from trading_bot.ledger import PaperLedger

NY = __import__("zoneinfo").ZoneInfo("America/New_York")


@pytest.fixture(scope="module")
def sessions() -> tuple[date, ...]:
    return tuple(
        day
        for day in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= day < date(2024, 1, 1)
    )


def _month_end_dates(sessions: tuple[date, ...]) -> tuple[date, ...]:
    return tuple(
        day
        for index, day in enumerate(sessions)
        if index + 1 == len(sessions)
        or (sessions[index + 1].year, sessions[index + 1].month)
        != (day.year, day.month)
    )


def _dataset(
    sessions: tuple[date, ...],
    *,
    targets: dict[date, str | tuple[str, ...]] | None = None,
    direct_closes: dict[tuple[str, date], Decimal] | None = None,
    opens: dict[tuple[str, date], Decimal] | None = None,
) -> MultiAssetDataset:
    """Create an exact-calendar fixture containing synthetic prices only."""
    targets = targets or {}
    direct_closes = direct_closes or {}
    opens = opens or {}
    indices = {day: index for index, day in enumerate(sessions)}
    closes = {symbol: [Decimal(100)] * len(sessions) for symbol in UNIVERSE}
    for signal_date, target in targets.items():
        signal_index = indices[signal_date]
        endpoint = signal_index - 21
        if target == CASH:
            for symbol in UNIVERSE:
                closes[symbol][endpoint] = Decimal(90)
        else:
            chosen = (target,) if type(target) is str else target
            for symbol in chosen:
                closes[symbol][endpoint] = Decimal(120)
    for (symbol, day), value in direct_closes.items():
        closes[symbol][indices[day]] = value

    provenance = ProviderProvenance()
    symbol_datasets: list[SymbolDataset] = []
    for symbol in UNIVERSE:
        bars: list[Bar] = []
        for index, day in enumerate(sessions):
            close = closes[symbol][index]
            open_price = opens.get((symbol, day), close)
            high = max(open_price, close) + Decimal(1)
            low = min(open_price, close) - Decimal(1)
            timestamp = datetime.combine(day, time.min, NY).astimezone(UTC)
            bars.append(
                Bar(
                    Symbol(symbol),
                    timestamp,
                    open_price,
                    high,
                    low,
                    close,
                    1000,
                )
            )
        symbol_datasets.append(SymbolDataset(symbol, tuple(bars), provenance))
    return MultiAssetDataset(tuple(symbol_datasets))


def _target_by_date(replay):
    return {target.signal_date: target for target in replay.targets}


def _forged_dataset(
    dataset: MultiAssetDataset,
    *,
    omit_symbol: str | None = None,
    mutate_bar: tuple[str, date, str, object] | None = None,
) -> MultiAssetDataset:
    """Bypass value constructors to probe replay fail-closed guards."""
    datasets = []
    for item in dataset.datasets:
        if item.symbol == omit_symbol:
            continue
        bars = item.bars
        if mutate_bar is not None and item.symbol == mutate_bar[0]:
            _, target_date, field_name, value = mutate_bar
            mutable_bars = list(bars)
            index = next(
                i
                for i, bar in enumerate(bars)
                if bar.timestamp.astimezone(NY).date() == target_date
            )
            original = bars[index]
            altered = object.__new__(Bar)
            for name in (
                "symbol",
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ):
                object.__setattr__(altered, name, getattr(original, name))
            object.__setattr__(altered, field_name, value)
            mutable_bars[index] = altered
            bars = tuple(mutable_bars)
        altered_dataset = object.__new__(SymbolDataset)
        object.__setattr__(altered_dataset, "symbol", item.symbol)
        object.__setattr__(altered_dataset, "bars", bars)
        object.__setattr__(
            altered_dataset, "provider_provenance", item.provider_provenance
        )
        datasets.append(altered_dataset)
    forged = object.__new__(MultiAssetDataset)
    object.__setattr__(forged, "datasets", tuple(datasets))
    object.__setattr__(forged, "identity", dataset.identity)
    return forged


def test_month_end_rank_gate_ties_lookbacks_and_excluded_recent_window(sessions):
    month_ends = _month_end_dates(sessions)
    jan_2017 = next(day for day in month_ends if day == date(2017, 1, 31))
    index = sessions.index(jan_2017)
    baseline = _dataset(
        sessions,
        targets={jan_2017: ("SPY", "QQQ")},
        direct_closes={
            ("SPY", sessions[index - 252]): Decimal(110),
            ("QQQ", sessions[index - 252]): Decimal(110),
        },
    )
    recent_changed = _dataset(
        sessions,
        targets={jan_2017: ("SPY", "QQQ")},
        direct_closes={
            ("SPY", sessions[index - 252]): Decimal(110),
            ("QQQ", sessions[index - 252]): Decimal(110),
            **{
                (symbol, day): Decimal(500)
                for symbol in UNIVERSE
                for day in sessions[index - 20 : index + 1]
            },
        },
    )
    future_changed = _dataset(
        sessions,
        targets={jan_2017: ("SPY", "QQQ")},
        direct_closes={
            ("SPY", sessions[index - 252]): Decimal(110),
            ("QQQ", sessions[index - 252]): Decimal(110),
            **{
                (symbol, day): Decimal(500)
                for symbol in UNIVERSE
                for day in sessions[index + 1 :]
            },
        },
    )
    first = replay_monthly_defensive_rotation(baseline, costs=BASE_COSTS)
    changed = replay_monthly_defensive_rotation(recent_changed, costs=BASE_COSTS)
    future = replay_monthly_defensive_rotation(future_changed, costs=BASE_COSTS)
    first_signal = _target_by_date(first)[jan_2017]
    changed_signal = _target_by_date(changed)[jan_2017]
    future_signal = _target_by_date(future)[jan_2017]

    assert first.strategy_id == STRATEGY_ID
    assert baseline.symbols == UNIVERSE
    assert first_signal.target == "SPY"  # tied top scores use frozen universe order
    with localcontext(Context(prec=50)):
        expected_score = Decimal(120) / Decimal(110) - Decimal(1)
    assert first_signal.ranked_scores[0] == ("SPY", expected_score)
    assert first_signal.ranked_scores[0][1] == first_signal.ranked_scores[1][1]
    assert first_signal.identity == changed_signal.identity
    assert first_signal.identity == future_signal.identity
    assert len(first.targets) == 84
    assert tuple(target.signal_date for target in first.targets) == tuple(
        day for day in month_ends if day >= EXPLORATION_START
    )
    assert first_signal.next_session == sessions[index + 1]

    cash_dataset = _dataset(sessions, targets={jan_2017: CASH})
    cash_signal = _target_by_date(
        replay_monthly_defensive_rotation(cash_dataset, costs=BASE_COSTS)
    )[jan_2017]
    assert cash_signal.target == CASH
    assert cash_signal.ranked_scores[0][1] == Decimal("-0.1")
    zero_signal = _target_by_date(
        replay_monthly_defensive_rotation(_dataset(sessions), costs=BASE_COSTS)
    )[jan_2017]
    assert zero_signal.ranked_scores[0][1] == 0
    assert zero_signal.target == CASH


def test_next_open_whole_share_switch_cash_and_unchanged_resolution(sessions):
    month_ends = tuple(
        day for day in _month_end_dates(sessions) if day >= EXPLORATION_START
    )
    jan, feb, mar, apr = month_ends[:4]
    dataset = _dataset(
        sessions,
        targets={jan: "SPY", feb: "QQQ", mar: CASH, apr: CASH},
    )
    replay = replay_monthly_defensive_rotation(dataset, costs=BASE_COSTS)
    by_date = _target_by_date(replay)
    jan_action = sessions[sessions.index(jan) + 1]
    feb_action = sessions[sessions.index(feb) + 1]
    mar_action = sessions[sessions.index(mar) + 1]
    apr_action = sessions[sessions.index(apr) + 1]

    assert by_date[jan].next_session == jan_action
    assert by_date[jan].resolution is TargetResolution.REBALANCED
    assert by_date[feb].next_session == feb_action
    assert by_date[feb].resolution is TargetResolution.REBALANCED
    assert by_date[mar].next_session == mar_action
    assert by_date[mar].resolution is TargetResolution.REBALANCED
    assert by_date[apr].next_session == apr_action
    assert by_date[apr].resolution is TargetResolution.UNCHANGED_TARGET

    fills_by_signal = {}
    for fill in replay.fills:
        fills_by_signal.setdefault(fill.signal_date, []).append(fill)
    first_buy = fills_by_signal[jan][0]
    with localcontext(Context(prec=50)):
        expected_quantity = (
            (STARTING_CASH * ALLOCATION - BASE_COSTS.commission)
            / (Decimal(100) * (Decimal(1) + BASE_COSTS.slippage_bps / Decimal(10000)))
        ).to_integral_value(rounding=ROUND_FLOOR)
    assert first_buy.side == "BUY"
    assert first_buy.timestamp.astimezone(NY).date() == jan_action
    assert first_buy.execution_open == Decimal(100)
    assert first_buy.price == Decimal(100) * (
        Decimal(1) + BASE_COSTS.slippage_bps / Decimal(10000)
    )
    assert first_buy.quantity == expected_quantity
    assert first_buy.quantity == first_buy.quantity.to_integral_value()
    assert first_buy.cash_after >= Decimal(5000)

    switch_fills = fills_by_signal[feb]
    assert tuple(fill.side for fill in switch_fills) == ("SELL", "BUY")
    assert tuple(fill.symbol for fill in switch_fills) == ("SPY", "QQQ")
    assert switch_fills[0].timestamp == switch_fills[1].timestamp
    assert switch_fills[0].timestamp.astimezone(NY).date() == feb_action
    assert fills_by_signal[mar][0].side == "SELL"
    assert fills_by_signal[mar][0].symbol == "QQQ"
    assert apr not in fills_by_signal
    early_fills = tuple(fill for fill in replay.fills if fill.signal_date <= apr)
    assert sum(fill.side == "BUY" and fill.symbol == "SPY" for fill in early_fills) == 1
    assert sum(fill.side == "BUY" and fill.symbol == "QQQ" for fill in early_fills) == 1
    assert all(
        fill.timestamp.astimezone(NY).date() < date(2017, 5, 1)
        for fill in replay.fills
        if fill.signal_date <= apr
    )
    with localcontext(Context(prec=50)):
        expected_investment_fraction = Decimal(
            sum(mark.held_symbol is not None for mark in replay.daily_marks)
        ) / len(replay.daily_marks)
    assert replay.time_invested == expected_investment_fraction
    marks_by_date = {mark.session_date: mark for mark in replay.daily_marks}
    assert marks_by_date[feb].held_symbol == "SPY"
    assert marks_by_date[mar].held_symbol == "QQQ"
    assert marks_by_date[apr].held_symbol is None
    assert replay.months_held == tuple(
        (
            symbol,
            sum(
                marks_by_date[day].held_symbol == symbol
                for day in _month_end_dates(sessions)
                if day >= EXPLORATION_START
            ),
        )
        for symbol in UNIVERSE
    )


def test_terminal_december_no_2024_lookup_and_report_bounds(sessions):
    dataset = _dataset(sessions)
    replay = replay_monthly_defensive_rotation(dataset, costs=BASE_COSTS)
    terminal = replay.targets[-1]

    assert terminal.signal_date == date(2023, 12, 29)
    assert terminal.next_session is None
    assert terminal.resolution is TargetResolution.END_OF_EXPLORATION
    assert all(target.signal_date.year >= 2017 for target in replay.targets)
    assert all(
        EXPLORATION_START <= mark.session_date < EXPLORATION_END
        for mark in replay.daily_marks
    )
    assert replay.daily_marks[0].session_date >= EXPLORATION_START
    assert replay.daily_marks[-1].session_date < EXPLORATION_END
    assert all(
        fill.timestamp.astimezone(NY).date().year <= 2023 for fill in replay.fills
    )


def test_insufficient_whole_share_lot_is_explicit_without_fallback(sessions):
    jan = next(day for day in _month_end_dates(sessions) if day == date(2017, 1, 31))
    next_session = sessions[sessions.index(jan) + 1]
    dataset = _dataset(
        sessions,
        targets={jan: "SPY"},
        opens={("SPY", next_session): Decimal("1000000")},
    )
    replay = replay_monthly_defensive_rotation(dataset, costs=BASE_COSTS)
    target = _target_by_date(replay)[jan]

    assert target.target == "SPY"
    assert target.next_session == next_session
    assert target.resolution is TargetResolution.INSUFFICIENT_WHOLE_SHARES
    assert not any(fill.signal_date == jan for fill in replay.fills)
    first_action_mark = next(
        mark for mark in replay.daily_marks if mark.session_date == next_session
    )
    assert first_action_mark.held_symbol is None
    assert first_action_mark.cash == STARTING_CASH


def test_base_stress_economics_context_independent_identity_and_no_io(
    sessions, monkeypatch
):
    first_2017_month_end = next(
        day for day in _month_end_dates(sessions) if day >= EXPLORATION_START
    )
    dataset = _dataset(sessions, targets={first_2017_month_end: "SPY"})

    def reject_io(*_args, **_kwargs):
        raise AssertionError("replay attempted filesystem access")

    monkeypatch.setattr(Path, "open", reject_io)
    base = replay_monthly_defensive_rotation(dataset, costs=BASE_COSTS)
    with localcontext(Context(prec=3)):
        same = replay_monthly_defensive_rotation(dataset, costs=BASE_COSTS)
    stress = replay_monthly_defensive_rotation(dataset, costs=STRESS_COSTS)

    assert base == same
    assert base.identity == same.identity
    assert base.identity != stress.identity
    assert base.fills and stress.fills
    assert all(fill.commission == Decimal(1) for fill in base.fills)
    assert all(fill.commission == Decimal(2) for fill in stress.fills)
    assert all(
        fill.price == fill.execution_open * Decimal("1.0005")
        for fill in base.fills
        if fill.side == "BUY"
    )
    assert all(
        fill.price == fill.execution_open * Decimal("0.9995")
        for fill in base.fills
        if fill.side == "SELL"
    )
    assert all(
        fill.price == fill.execution_open * Decimal("1.001")
        for fill in stress.fills
        if fill.side == "BUY"
    )
    assert all(
        fill.price == fill.execution_open * Decimal("0.999")
        for fill in stress.fills
        if fill.side == "SELL"
    )
    assert tuple(fill.turnover_notional for fill in base.fills) == base.fill_turnovers
    assert verify_rotation_replay_identity(base)
    assert monthly_rotation_identity(
        "test", (date(2017, 1, 31), Decimal("1.0"))
    ) == monthly_rotation_identity("test", (date(2017, 1, 31), Decimal("1.00")))
    with pytest.raises(ValueError):
        replay_monthly_defensive_rotation(dataset, costs=Costs(Decimal(0), Decimal(5)))


def test_post_2023_dataset_is_physically_rejected(sessions):
    dataset = _dataset(sessions)
    mutated_series = []
    future_timestamp = datetime(2024, 1, 2, tzinfo=UTC)
    for item in dataset.datasets:
        malformed = object.__new__(SymbolDataset)
        future_bar = replace(item.bars[-1], timestamp=future_timestamp)
        object.__setattr__(malformed, "symbol", item.symbol)
        object.__setattr__(malformed, "bars", item.bars[:-1] + (future_bar,))
        object.__setattr__(malformed, "provider_provenance", item.provider_provenance)
        mutated_series.append(malformed)
    out_of_bounds = object.__new__(MultiAssetDataset)
    object.__setattr__(out_of_bounds, "datasets", tuple(mutated_series))
    object.__setattr__(out_of_bounds, "identity", dataset.identity)

    with pytest.raises(ValueError, match="outside"):
        replay_monthly_defensive_rotation(out_of_bounds, costs=BASE_COSTS)


def test_partial_universe_and_missing_lag_close_fail_closed(sessions):
    jan = next(day for day in _month_end_dates(sessions) if day == date(2017, 1, 31))
    dataset = _dataset(sessions, targets={jan: "SPY"})
    with pytest.raises(ValueError, match="all eight"):
        replay_monthly_defensive_rotation(
            _forged_dataset(dataset, omit_symbol="PDBC"), costs=BASE_COSTS
        )

    recent_required_date = sessions[sessions.index(jan) - 21]
    missing_lag = _forged_dataset(
        dataset,
        mutate_bar=("SPY", recent_required_date, "close", None),
    )
    replay = replay_monthly_defensive_rotation(missing_lag, costs=BASE_COSTS)
    signal = _target_by_date(replay)[jan]
    assert signal.resolution is TargetResolution.MISSING_INPUT
    assert signal.missing_symbols == ("SPY",)
    assert signal.ranked_scores == ()
    assert signal.target is None
    assert signal.next_session is None
    assert not any(fill.signal_date == jan for fill in replay.fills)


def test_missing_switch_open_fails_before_selling_existing_position(
    sessions, monkeypatch
):
    month_ends = tuple(
        day for day in _month_end_dates(sessions) if day >= EXPLORATION_START
    )
    jan, feb = month_ends[:2]
    feb_open_date = sessions[sessions.index(feb) + 1]
    dataset = _dataset(sessions, targets={jan: "SPY", feb: "QQQ"})
    missing_target_open = _forged_dataset(
        dataset,
        mutate_bar=("QQQ", feb_open_date, "open", None),
    )
    fills_before_failure = []
    original_apply_fill = PaperLedger.apply_fill

    def record_fill(ledger, fill):
        fills_before_failure.append((fill.symbol.value, fill.side))
        return original_apply_fill(ledger, fill)

    monkeypatch.setattr(PaperLedger, "apply_fill", record_fill)
    with pytest.raises(ValueError, match="OPEN is unavailable"):
        replay_monthly_defensive_rotation(missing_target_open, costs=BASE_COSTS)
    assert fills_before_failure == [("SPY", rotation.OrderSide.BUY)]


def test_one_portfolio_carries_equity_and_holding_across_calendar_years(sessions):
    month_ends = tuple(
        day for day in _month_end_dates(sessions) if day >= EXPLORATION_START
    )
    rising_spy = {
        ("SPY", day): Decimal(100) + Decimal(index) / Decimal(10)
        for index, day in enumerate(sessions)
    }
    replay = replay_monthly_defensive_rotation(
        _dataset(sessions, direct_closes=rising_spy), costs=BASE_COSTS
    )
    targets_by_date = _target_by_date(replay)
    marks_by_date = {mark.session_date: mark for mark in replay.daily_marks}
    december_2017 = date(2017, 12, 29)
    first_2018_session = sessions[sessions.index(december_2017) + 1]
    before = marks_by_date[december_2017]
    after = marks_by_date[first_2018_session]

    assert tuple(targets_by_date[day].target for day in month_ends) == ("SPY",) * 84
    assert replay.initial_equity == STARTING_CASH
    assert {mark.session_date.year for mark in replay.daily_marks} == set(
        range(2017, 2024)
    )
    assert before.held_symbol == after.held_symbol == "SPY"
    assert before.held_quantity == after.held_quantity
    assert before.cash == after.cash
    assert not any(
        fill.timestamp.astimezone(NY).date() == first_2018_session
        for fill in replay.fills
    )
    assert replay.final_equity == replay.daily_marks[-1].equity
