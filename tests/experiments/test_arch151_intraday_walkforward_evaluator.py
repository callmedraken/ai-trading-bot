"""Synthetic execution contracts for the Arch151 evaluator."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from functools import cache
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID

import pytest

from trading_bot.experiments import arch151_intraday_walkforward as arch151
from trading_bot.experiments import arch151_intraday_walkforward_evaluator as evaluator

SESSION = date(2023, 1, 3)


def _flat_bars(
    symbol: str, session: date, resolution: arch151.BarResolution
) -> list[arch151.AggregateBar]:
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    assert schedule is not None
    count = int((schedule.closes_at - schedule.opens_at).total_seconds() // 60)
    count //= int(resolution)
    return [
        arch151.AggregateBar(
            symbol,
            schedule.opens_at + timedelta(minutes=index * int(resolution)),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            100 * int(resolution),
            resolution,
        )
        for index in range(count)
    ]


def _minute_from_bar(bar: arch151.AggregateBar, offset: int) -> arch151.OneMinuteBar:
    return arch151.OneMinuteBar(
        bar.symbol,
        bar.timestamp + timedelta(minutes=offset),
        bar.open,
        bar.high,
        bar.low,
        bar.close,
        bar.volume // int(bar.resolution),
    )


def _b_history(
    *,
    session: date = SESSION,
    entry_observed: bool = True,
    ambiguous_entry_range: bool = False,
    exit_mode: str = "target_open",
    exit_delay_minutes: int = 1,
    second_setup: bool = False,
    second_open_observed: bool = False,
):
    program = next(
        item
        for item in arch151.CANONICAL_PROGRAMS
        if item.key is arch151.ProgramKey.B5_01
    )
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    assert schedule is not None
    bars = _flat_bars("SPY", session, program.resolution)
    parameters = program.parameters
    level = Decimal("100") * (
        Decimal(1) + parameters.breakout_buffer_bps / Decimal(10000)
    )
    bars[6] = arch151.AggregateBar(
        "SPY",
        bars[6].timestamp,
        level + Decimal("0.03"),
        level + Decimal("0.11"),
        level + Decimal("0.02"),
        level + Decimal("0.10"),
        500,
        program.resolution,
    )
    bars[7] = arch151.AggregateBar(
        "SPY",
        bars[7].timestamp,
        level + Decimal("0.04"),
        level + Decimal("0.06"),
        level,
        level + Decimal("0.02"),
        500,
        program.resolution,
    )
    bars[8] = arch151.AggregateBar(
        "SPY",
        bars[8].timestamp,
        level + Decimal("0.03"),
        level + Decimal("0.15"),
        level + Decimal("0.02"),
        level + Decimal("0.12"),
        500,
        program.resolution,
    )
    if second_setup:
        bars[11] = arch151.AggregateBar(
            "SPY",
            bars[11].timestamp,
            level + Decimal("0.03"),
            level + Decimal("0.11"),
            level + Decimal("0.02"),
            level + Decimal("0.10"),
            500,
            program.resolution,
        )
        bars[12] = arch151.AggregateBar(
            "SPY",
            bars[12].timestamp,
            level + Decimal("0.04"),
            level + Decimal("0.06"),
            level,
            level + Decimal("0.02"),
            500,
            program.resolution,
        )
        bars[13] = arch151.AggregateBar(
            "SPY",
            bars[13].timestamp,
            level + Decimal("0.03"),
            level + Decimal("0.15"),
            level + Decimal("0.02"),
            level + Decimal("0.12"),
            500,
            program.resolution,
        )
    minutes = [
        _minute_from_bar(bar, offset)
        for bar in bars[:9]
        for offset in range(int(program.resolution))
    ]
    entry_time = bars[8].completed_at
    stop = level * (Decimal(1) - parameters.stop_buffer_bps / Decimal(10000))
    risk = Decimal("100.2") - stop
    target = Decimal("100.2") + parameters.target_r * risk
    if entry_observed:
        entry_low = (
            stop - Decimal("0.01") if ambiguous_entry_range else Decimal("100.19")
        )
        entry_high = (
            target + Decimal("0.01") if ambiguous_entry_range else Decimal("100.3")
        )
        minutes.append(
            arch151.OneMinuteBar(
                "SPY",
                entry_time,
                Decimal("100.2"),
                entry_high,
                entry_low,
                Decimal("100.25"),
                100,
            )
        )
        if exit_mode != "none":
            exit_time = entry_time + timedelta(minutes=exit_delay_minutes)
            if exit_mode == "target_open":
                exit_open, exit_high, exit_low = (
                    target + Decimal("0.2"),
                    target + Decimal("0.3"),
                    target + Decimal("0.1"),
                )
            elif exit_mode == "stop_gap":
                exit_open, exit_high, exit_low = (
                    stop - Decimal("0.1"),
                    stop,
                    stop - Decimal("0.2"),
                )
            elif exit_mode == "ambiguous_touch":
                exit_open, exit_high, exit_low = (
                    Decimal("100.2"),
                    target + Decimal("0.1"),
                    stop - Decimal("0.1"),
                )
            elif exit_mode in ("hold_open", "liquidation"):
                exit_open, exit_high, exit_low = (
                    Decimal("100.3"),
                    Decimal("100.35"),
                    Decimal("100.25"),
                )
            else:
                raise ValueError(f"unsupported exit mode: {exit_mode}")
            minutes.append(
                arch151.OneMinuteBar(
                    "SPY", exit_time, exit_open, exit_high, exit_low, exit_open, 100
                )
            )
    else:
        minutes.append(
            arch151.OneMinuteBar(
                "SPY",
                entry_time + timedelta(minutes=1),
                Decimal("100.2"),
                Decimal("100.3"),
                Decimal("100.1"),
                Decimal("100.25"),
                100,
            )
        )
    if second_setup:
        special_timestamps = (
            {entry_time} if entry_observed else {entry_time + timedelta(minutes=1)}
        )
        if entry_observed and exit_mode != "none":
            special_timestamps.add(entry_time + timedelta(minutes=exit_delay_minutes))
        minutes.extend(
            minute
            for bar in bars[9:14]
            for minute in _bar_minutes(bar)
            if minute.timestamp not in special_timestamps
        )
        if second_open_observed:
            minutes.append(
                arch151.OneMinuteBar(
                    "SPY",
                    bars[13].completed_at,
                    Decimal("100"),
                    Decimal("100.01"),
                    Decimal("99.99"),
                    Decimal("100"),
                    100,
                )
            )
    return (
        program,
        arch151._test_only_synthetic_source_history(minutes),
        entry_time,
        target,
        stop,
        schedule.closes_at - timedelta(minutes=5),
    )


def _slot_for(program: arch151.Arch151Program, symbol: str = "SPY"):
    return next(
        slot
        for slot in arch151.CANONICAL_SLOTS
        if slot.program_key is program.key and slot.symbol == symbol
    )


def _bar_minutes(bar: arch151.AggregateBar) -> tuple[arch151.OneMinuteBar, ...]:
    return tuple(_minute_from_bar(bar, offset) for offset in range(int(bar.resolution)))


def _timestamp_for_index(
    session: date, resolution: arch151.BarResolution, index: int
) -> datetime:
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    assert schedule is not None
    return schedule.opens_at + timedelta(minutes=index * int(resolution))


def _programs_for_family(family: arch151.StrategyFamily):
    return tuple(item for item in arch151.CANONICAL_PROGRAMS if item.family is family)


@cache
def _a_prior_minutes(symbol: str) -> tuple[arch151.OneMinuteBar, ...]:
    prior_sessions = tuple(
        session
        for session in arch151._SESSION_AUTHORITY.published.sessions
        if date(2016, 1, 1) <= session < date(2019, 1, 1)
    )[-60:]
    result: list[arch151.OneMinuteBar] = []
    for session in prior_sessions:
        schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
        assert schedule is not None
        count = int((schedule.closes_at - schedule.opens_at).total_seconds() // 60)
        for offset in range(count):
            close = Decimal("100.1") if offset == 29 else Decimal("100")
            result.append(
                arch151.OneMinuteBar(
                    symbol,
                    schedule.opens_at + timedelta(minutes=offset),
                    Decimal("100"),
                    max(Decimal("100"), close),
                    min(Decimal("100"), close),
                    close,
                    100,
                )
            )
    return tuple(result)


def _a_history(program: arch151.Arch151Program, symbol: str):
    session = SESSION
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    assert schedule is not None
    current: list[arch151.OneMinuteBar] = []
    for offset in range(
        int((schedule.closes_at - schedule.opens_at).total_seconds() // 60)
    ):
        if offset < 30:
            opening = close = Decimal("100")
            high, low = Decimal("100.001"), Decimal("99.999")
        else:
            close = Decimal("100.1") + Decimal(offset - 30) * Decimal("0.005")
            opening = close - Decimal("0.002")
            high, low = close + Decimal("0.003"), close - Decimal("0.004")
        current.append(
            arch151.OneMinuteBar(
                symbol,
                schedule.opens_at + timedelta(minutes=offset),
                opening,
                high,
                low,
                close,
                100,
            )
        )
    history = arch151._test_only_synthetic_source_history(
        (*_a_prior_minutes(symbol), *current)
    )
    return history, session


def _b_all_program_history(program: arch151.Arch151Program, symbol: str):
    resolution = program.resolution
    bars = _flat_bars(symbol, SESSION, resolution)
    parameters = program.parameters
    schedule = arch151._SESSION_AUTHORITY.schedule_for(SESSION)
    assert schedule is not None
    start_local = datetime.combine(
        SESSION, program.entry_window.start, arch151.NEW_YORK
    ).astimezone(UTC)
    first_window_index = int(
        (start_local - schedule.opens_at).total_seconds() // 60
    ) // int(resolution)
    opening_count = parameters.opening_range_minutes // int(resolution)
    minimum_final = (
        opening_count
        + parameters.breakout_confirmation_bars
        + 1
        + parameters.reclaim_confirmation_bars
        - 1
    )
    final_index = max(first_window_index, minimum_final)
    breakout_start = (
        final_index
        - parameters.reclaim_confirmation_bars
        - parameters.breakout_confirmation_bars
    )
    level = Decimal("100") * (
        Decimal(1) + parameters.breakout_buffer_bps / Decimal(10000)
    )
    for index in range(
        breakout_start,
        breakout_start + parameters.breakout_confirmation_bars,
    ):
        bars[index] = arch151.AggregateBar(
            symbol,
            bars[index].timestamp,
            level + Decimal("0.03"),
            level + Decimal("0.12"),
            level + Decimal("0.02"),
            level + Decimal("0.10"),
            500 * int(resolution),
            resolution,
        )
    retest_index = breakout_start + parameters.breakout_confirmation_bars
    bars[retest_index] = arch151.AggregateBar(
        symbol,
        bars[retest_index].timestamp,
        level + Decimal("0.04"),
        level + Decimal("0.07"),
        level,
        level + Decimal("0.02"),
        500 * int(resolution),
        resolution,
    )
    previous_high = bars[retest_index].high
    reclaim_start = retest_index + 1
    for index in range(reclaim_start, final_index + 1):
        close = previous_high + Decimal("0.10")
        bars[index] = arch151.AggregateBar(
            symbol,
            bars[index].timestamp,
            previous_high + Decimal("0.02"),
            close + Decimal("0.02"),
            previous_high + Decimal("0.01"),
            close,
            500 * int(resolution),
            resolution,
        )
        previous_high = bars[index].high
    selected = bars[: final_index + 1]
    minutes = [minute for bar in selected for minute in _bar_minutes(bar)]
    signal_time = selected[-1].completed_at
    retest_low = min(item.low for item in selected[retest_index : final_index + 1])
    with localcontext(arch151._DECIMAL_CONTEXT):
        stop = retest_low * (Decimal(1) - parameters.stop_buffer_bps / Decimal(10000))
        entry_reference = selected[-1].close + Decimal("0.05")
        target = entry_reference + parameters.target_r * (entry_reference - stop)
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            signal_time,
            entry_reference,
            entry_reference + Decimal("0.02"),
            entry_reference - Decimal("0.02"),
            entry_reference,
            100,
        )
    )
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            signal_time + timedelta(minutes=1),
            target + Decimal("0.1"),
            target + Decimal("0.2"),
            target + Decimal("0.05"),
            target + Decimal("0.1"),
            100,
        )
    )
    return arch151._test_only_synthetic_source_history(minutes), signal_time


def _c_history(program: arch151.Arch151Program, symbol: str):
    resolution = program.resolution
    parameters = program.parameters
    bars = _flat_bars(symbol, SESSION, resolution)
    required = max(
        parameters.deviation_lookback_bars,
        parameters.efficiency_ratio_lookback,
    )
    schedule = arch151._SESSION_AUTHORITY.schedule_for(SESSION)
    assert schedule is not None
    start_local = datetime.combine(
        SESSION, program.entry_window.start, arch151.NEW_YORK
    ).astimezone(UTC)
    start_index = int((start_local - schedule.opens_at).total_seconds() // 60) // int(
        resolution
    )
    signal_index = max(required, start_index)
    history_start = signal_index - required
    for offset, index in enumerate(range(history_start, signal_index)):
        close = Decimal("100") if offset % 2 == 0 else Decimal("101")
        if offset % 2 == 0:
            high, low = close, close - Decimal("1.5")
        else:
            high, low = close + Decimal("1.5"), close
        bars[index] = arch151.AggregateBar(
            symbol,
            bars[index].timestamp,
            close,
            high,
            low,
            close,
            100 * int(resolution),
            resolution,
        )
    bars[signal_index] = arch151.AggregateBar(
        symbol,
        bars[signal_index].timestamp,
        Decimal("98"),
        Decimal("104"),
        Decimal("98"),
        Decimal("98"),
        100 * int(resolution),
        resolution,
    )
    minutes = [
        minute for bar in bars[: signal_index + 1] for minute in _bar_minutes(bar)
    ]
    signal_time = bars[signal_index].completed_at
    # The first minute after the signal is the entry open. Later constituents
    # create a causal VWAP reclaim for the completed next aggregate.
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            signal_time,
            Decimal("98.1"),
            Decimal("98.3"),
            Decimal("98.0"),
            Decimal("98.2"),
            100,
        )
    )
    for offset in range(1, int(resolution)):
        minutes.append(
            arch151.OneMinuteBar(
                symbol,
                signal_time + timedelta(minutes=offset),
                Decimal("104"),
                Decimal("104"),
                Decimal("102.5"),
                Decimal("104"),
                100,
            )
        )
    exit_time = signal_time + timedelta(minutes=int(resolution))
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            exit_time,
            Decimal("104"),
            Decimal("104.1"),
            Decimal("103.9"),
            Decimal("104"),
            100,
        )
    )
    return arch151._test_only_synthetic_source_history(minutes), signal_time, exit_time


def _c_two_entry_history(program: arch151.Arch151Program, symbol: str):
    if program.resolution is not arch151.BarResolution.FIVE_MINUTE:
        raise ValueError("two-entry cooldown fixture is a bounded C5-01 case")
    bars = _flat_bars(symbol, SESSION, program.resolution)
    for index in range(24):
        close = Decimal("100") if index % 2 == 0 else Decimal("101")
        high, low = (
            (close, close - Decimal("1.5"))
            if index % 2 == 0
            else (close + Decimal("1.5"), close)
        )
        bars[index] = arch151.AggregateBar(
            symbol,
            bars[index].timestamp,
            close,
            high,
            low,
            close,
            500,
            program.resolution,
        )
    bars[24] = arch151.AggregateBar(
        symbol,
        bars[24].timestamp,
        Decimal("98"),
        Decimal("104"),
        Decimal("98"),
        Decimal("98"),
        500,
        program.resolution,
    )
    for index in range(27, 51):
        close = Decimal("100") if (index - 27) % 2 == 0 else Decimal("101")
        high, low = (
            (close, close - Decimal("1.5"))
            if (index - 27) % 2 == 0
            else (close + Decimal("1.5"), close)
        )
        bars[index] = arch151.AggregateBar(
            symbol,
            bars[index].timestamp,
            close,
            high,
            low,
            close,
            500,
            program.resolution,
        )
    bars[51] = arch151.AggregateBar(
        symbol,
        bars[51].timestamp,
        Decimal("98"),
        Decimal("104"),
        Decimal("98"),
        Decimal("98"),
        500,
        program.resolution,
    )
    minutes = [
        minute for bar in (*bars[:25], *bars[27:52]) for minute in _bar_minutes(bar)
    ]
    first_signal_time = bars[24].completed_at
    for offset in range(1, int(program.resolution)):
        minutes.append(
            arch151.OneMinuteBar(
                symbol,
                first_signal_time + timedelta(minutes=offset),
                Decimal("104"),
                Decimal("104"),
                Decimal("102.5"),
                Decimal("104"),
                100,
            )
        )
    # The entry open is observed at the signal boundary; the VWAP exit is
    # completed one bucket later, but that exact eligible open is absent.
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            first_signal_time,
            Decimal("98.1"),
            Decimal("98.3"),
            Decimal("98.0"),
            Decimal("98.2"),
            100,
        )
    )
    # Remove all constituents of aggregate index 26. The position's pending
    # reversion exit fills at the first observed open in the fresh segment.
    minutes = [
        item
        for item in minutes
        if not (
            bars[26].timestamp
            <= item.timestamp
            < bars[26].timestamp + timedelta(minutes=int(program.resolution))
        )
    ]
    second_signal_time = bars[51].completed_at
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            second_signal_time,
            Decimal("98.1"),
            Decimal("98.2"),
            Decimal("98.0"),
            Decimal("98.1"),
            100,
        )
    )
    second_exit_time = second_signal_time + timedelta(
        minutes=program.parameters.max_hold_minutes
    )
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            second_exit_time,
            Decimal("98.1"),
            Decimal("98.2"),
            Decimal("98.0"),
            Decimal("98.1"),
            100,
        )
    )
    return (
        arch151._test_only_synthetic_source_history(minutes),
        first_signal_time,
        second_signal_time,
        second_exit_time,
    )


def _d_history(program: arch151.Arch151Program, symbol: str):
    resolution = program.resolution
    parameters = program.parameters
    other_symbol = next(item for item in arch151.INITIAL_UNIVERSE if item != symbol)
    local = _flat_bars(symbol, SESSION, resolution)
    other = _flat_bars(other_symbol, SESSION, resolution)
    schedule = arch151._SESSION_AUTHORITY.schedule_for(SESSION)
    assert schedule is not None
    start_local = datetime.combine(
        SESSION, program.entry_window.start, arch151.NEW_YORK
    ).astimezone(UTC)
    first_window_index = (
        int((start_local - schedule.opens_at).total_seconds() // 60) // int(resolution)
        - 1
    )
    minimum_setup = max(
        parameters.ema_slow + 2,
        parameters.atr_lookback + 1,
        parameters.swing_peak_window_bars,
    )
    final_index = max(
        first_window_index,
        minimum_setup + parameters.reclaim_confirmation_bars,
    )
    setup_index = final_index - parameters.reclaim_confirmation_bars
    for index in range(final_index + 1):
        local_close = Decimal("100") + Decimal(index) * Decimal("0.02")
        local[index] = arch151.AggregateBar(
            symbol,
            local[index].timestamp,
            local_close - Decimal("0.005"),
            local_close + Decimal("0.005"),
            local_close - Decimal("0.005"),
            local_close,
            100 * int(resolution),
            resolution,
        )
        other_close = Decimal("100") + Decimal(index) * Decimal("0.03")
        other[index] = arch151.AggregateBar(
            other_symbol,
            other[index].timestamp,
            other_close - Decimal("0.005"),
            other_close,
            other_close - Decimal("0.03"),
            other_close,
            100 * int(resolution),
            resolution,
        )
    peak_start = setup_index - parameters.swing_peak_window_bars
    peak = max(item.high for item in local[peak_start:setup_index])
    atr = arch151.average_true_range(
        local[setup_index - parameters.atr_lookback - 1 : setup_index],
        parameters.atr_lookback,
    )
    setup_low = peak - atr * Decimal("0.5")
    setup_close = setup_low + atr * Decimal("0.2")
    local[setup_index] = arch151.AggregateBar(
        symbol,
        local[setup_index].timestamp,
        setup_close,
        peak,
        setup_low,
        setup_close,
        100 * int(resolution),
        resolution,
    )
    previous_high = local[setup_index].high
    for index in range(setup_index + 1, final_index + 1):
        close = previous_high + Decimal("0.02")
        local[index] = arch151.AggregateBar(
            symbol,
            local[index].timestamp,
            previous_high + Decimal("0.01"),
            close + Decimal("0.005"),
            previous_high + Decimal("0.001"),
            close,
            100 * int(resolution),
            resolution,
        )
        previous_high = local[index].high
    minutes = [
        minute
        for bar in (*local[: final_index + 1], *other[: final_index + 1])
        for minute in _bar_minutes(bar)
    ]
    signal_time = local[final_index].completed_at
    entry_price = local[final_index].close + Decimal("0.01")
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            signal_time,
            entry_price,
            entry_price + Decimal("0.01"),
            entry_price - Decimal("0.001"),
            entry_price,
            100,
        )
    )
    boundary = schedule.closes_at - timedelta(minutes=5)
    minutes.append(
        arch151.OneMinuteBar(
            symbol,
            boundary,
            entry_price,
            entry_price + Decimal("0.01"),
            entry_price - Decimal("0.001"),
            entry_price,
            100,
        )
    )
    return arch151._test_only_synthetic_source_history(minutes), signal_time, boundary


def _source_for_program(program: arch151.Arch151Program, symbol: str):
    if program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT:
        history, session = _a_history(program, symbol)
        return history, session, None, evaluator.ExitReason.MAXIMUM_HOLD
    if program.family is arch151.StrategyFamily.OPENING_RANGE_RETEST:
        history, signal_time = _b_all_program_history(program, symbol)
        return history, SESSION, signal_time, evaluator.ExitReason.TARGET_OPEN
    if program.family is arch151.StrategyFamily.VWAP_MEAN_REVERSION:
        history, signal_time, exit_time = _c_history(program, symbol)
        return (
            history,
            SESSION,
            signal_time,
            (evaluator.ExitReason.VWAP_REVERSION, exit_time),
        )
    history, signal_time, exit_time = _d_history(program, symbol)
    return (
        history,
        SESSION,
        signal_time,
        (evaluator.ExitReason.SESSION_LIQUIDATION, exit_time),
    )


def test_b_simulator_fills_next_open_then_target_open_with_cost_reconciliation() -> (
    None
):
    program, history, entry_time, target, _stop, _boundary = _b_history()
    record = evaluator._simulate_session(
        history,
        _slot_for(program),
        SESSION,
        arch151.FillCostCase.STRESS,
    )

    assert len(record.trades) == 1
    trade = record.trades[0]
    assert trade.entry.timestamp == entry_time
    assert trade.exit.timestamp == entry_time + timedelta(minutes=1)
    assert trade.exit_reason is evaluator.ExitReason.TARGET_OPEN
    assert trade.exit.reference_price == target
    assert trade.exit.execution_price < target
    assert trade.entry.cash_before == Decimal(1)
    assert trade.entry.cash_after >= 0
    assert record.closing_equity == trade.exit.cash_after
    assert record.generated_signal_count == 1
    assert record.eligible_signal_count == 1
    assert record.executed_signal_count == 1
    assert record.expired_signal_count == 0
    assert record.blocked_signal_count == 0
    assert record.signal_lifecycle_reconciled
    outcome = record.signal_outcomes[0]
    assert outcome.disposition is evaluator.SignalDisposition.EXECUTED
    assert outcome.signal_timestamp == trade.signal_timestamp
    assert outcome.decision_timestamp == entry_time
    assert outcome.scheduled_next_open == entry_time
    assert outcome.entry_fill_id == trade.entry.fill_id
    with localcontext(arch151._DECIMAL_CONTEXT):
        assert trade.gross_pnl == trade.entry.quantity * (
            target - trade.entry.reference_price
        )
        assert abs(
            trade.net_pnl - (trade.gross_pnl - trade.total_adverse_cost)
        ) <= Decimal("1e-55")
        assert record.session_return == record.closing_equity - Decimal(1)
    assert len(record.fills) == 2


def test_b_simulator_expires_an_absent_next_open_without_chasing() -> None:
    program, history, entry_time, _target, _stop, _boundary = _b_history(
        entry_observed=False
    )
    record = evaluator._simulate_session(
        history,
        _slot_for(program),
        SESSION,
        arch151.FillCostCase.ZERO,
    )

    assert record.trades == ()
    assert record.fills == ()
    assert record.expired_entry_timestamps == (entry_time,)
    assert record.generated_signal_count == 1
    assert record.eligible_signal_count == 1
    assert record.executed_signal_count == 0
    assert record.expired_signal_count == 1
    assert record.blocked_signal_count == 0
    assert record.signal_lifecycle_reconciled
    outcome = record.signal_outcomes[0]
    assert outcome.disposition is evaluator.SignalDisposition.EXPIRED
    assert outcome.entry_fill_id is None
    assert record.closing_equity == Decimal(1)
    assert record.session_return == Decimal(0)


@pytest.mark.parametrize(
    ("exit_mode", "second_open_observed", "expected_reason"),
    [
        ("none", False, evaluator.RejectionReason.POSITION_ALREADY_OPEN),
        ("target_open", True, evaluator.RejectionReason.SESSION_ENTRY_LIMIT),
    ],
)
def test_generated_signal_is_blocked_with_reconciled_terminal_diagnostics(
    exit_mode: str,
    second_open_observed: bool,
    expected_reason: evaluator.RejectionReason,
) -> None:
    program, history, first_entry, *_ = _b_history(
        exit_mode=exit_mode,
        second_setup=True,
        second_open_observed=second_open_observed,
    )
    second_signal = _timestamp_for_index(SESSION, program.resolution, 13) + timedelta(
        minutes=int(program.resolution)
    )
    record = evaluator._simulate_session(
        history, _slot_for(program), SESSION, arch151.FillCostCase.ZERO
    )

    assert record.generated_signal_count == 2
    assert record.eligible_signal_count == 2
    assert record.executed_signal_count == 1
    assert record.expired_signal_count == 0
    assert record.blocked_signal_count == 1
    assert record.signal_lifecycle_reconciled
    first, second = record.signal_outcomes
    assert first.scheduled_next_open == first_entry
    assert first.disposition is evaluator.SignalDisposition.EXECUTED
    assert second.scheduled_next_open == second_signal
    assert second.disposition is evaluator.SignalDisposition.BLOCKED
    assert second.blocked_reason is expected_reason
    assert second.entry_fill_id is None
    assert all(fill.timestamp != second_signal for fill in record.fills)


def test_signal_inside_window_is_blocked_when_scheduled_open_is_after_cutoff() -> None:
    program, history, *_ = _b_history()
    slot = _slot_for(program)
    cache = evaluator._PreparationCache(history)
    tape = evaluator._session_tape(history, cache, program, slot.symbol, SESSION, None)
    assert tape is not None and tape.entry_intents
    source_intent = next(iter(tape.entry_intents.values()))
    decision = _timestamp_for_index(SESSION, program.resolution, 30)
    scheduled_open = decision + timedelta(minutes=1)
    assert program.entry_window.contains(decision)
    assert not program.entry_window.contains(scheduled_open)
    intent = replace(
        source_intent,
        signal_timestamp=decision - timedelta(minutes=int(program.resolution)),
        completed_at=decision,
    )
    shifted_tape = replace(
        tape, entry_intents=MappingProxyType({scheduled_open: intent})
    )
    minutes = history._projection_index[
        (slot.symbol, SESSION, program.resolution)
    ].minutes

    record = evaluator._simulate_session_from_tape(
        history_digest=evaluator._history_digest(history),
        slot=slot,
        program=program,
        session=SESSION,
        tape=shifted_tape,
        minutes=minutes,
        starting_equity=Decimal(1),
        case=arch151.FillCostCase.ZERO,
    )

    assert record.fills == ()
    assert record.generated_signal_count == 1
    assert record.eligible_signal_count == 0
    assert record.executed_signal_count == 0
    assert record.expired_signal_count == 0
    assert record.blocked_signal_count == 1
    assert record.signal_lifecycle_reconciled
    outcome = record.signal_outcomes[0]
    assert outcome.decision_timestamp == decision
    assert outcome.scheduled_next_open == scheduled_open
    assert outcome.disposition is evaluator.SignalDisposition.BLOCKED
    assert outcome.blocked_reason is evaluator.RejectionReason.ENTRY_WINDOW_CLOSED


def test_entry_minute_ambiguous_stop_and_target_resolves_to_stop() -> None:
    program, history, entry_time, _target, stop, _boundary = _b_history(
        ambiguous_entry_range=True
    )
    record = evaluator._simulate_session(
        history,
        _slot_for(program),
        SESSION,
        arch151.FillCostCase.ZERO,
    )

    assert len(record.trades) == 1
    assert record.trades[0].entry.timestamp == entry_time
    assert record.trades[0].exit_reason is evaluator.ExitReason.STOP_TOUCH
    assert record.trades[0].exit.reference_price == stop


@pytest.mark.parametrize("symbol", arch151.INITIAL_UNIVERSE)
def test_slot_lookup_preserves_canonical_symbol_identity(symbol: str) -> None:
    program, _history, *_ = _b_history()
    slot = _slot_for(program, symbol)
    assert arch151.validate_slot(slot)
    assert slot.symbol == symbol


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("stop_gap", evaluator.ExitReason.STOP_GAP),
        ("ambiguous_touch", evaluator.ExitReason.STOP_TOUCH),
    ],
)
def test_existing_position_exit_priority_uses_stop_gap_then_stop_touch(
    mode: str, expected: evaluator.ExitReason
) -> None:
    program, history, _entry_time, _target, _stop, _boundary = _b_history(
        exit_mode=mode
    )
    record = evaluator._simulate_session(
        history, _slot_for(program), SESSION, arch151.FillCostCase.ZERO
    )

    assert len(record.trades) == 1
    assert record.trades[0].exit_reason is expected
    if expected is evaluator.ExitReason.STOP_GAP:
        assert (
            record.trades[0].exit.reference_price
            < record.trades[0].final_stop_reference
        )
    else:
        assert (
            record.trades[0].exit.reference_price
            == record.trades[0].final_stop_reference
        )


def test_target_open_precedes_pending_maximum_hold_at_the_same_open() -> None:
    program, history, _entry_time, target, _stop, _boundary = _b_history(
        exit_mode="target_open", exit_delay_minutes=90
    )
    record = evaluator._simulate_session(
        history, _slot_for(program), SESSION, arch151.FillCostCase.ZERO
    )

    trade = record.trades[0]
    assert trade.exit_reason is evaluator.ExitReason.TARGET_OPEN
    assert trade.exit.reference_price == target


def test_elapsed_maximum_hold_exit_remains_pending_across_missing_minutes() -> None:
    program, history, entry_time, _target, _stop, _boundary = _b_history(
        exit_mode="hold_open", exit_delay_minutes=91
    )
    record = evaluator._simulate_session(
        history, _slot_for(program), SESSION, arch151.FillCostCase.ZERO
    )

    trade = record.trades[0]
    assert trade.exit.timestamp == entry_time + timedelta(minutes=91)
    assert trade.exit_reason is evaluator.ExitReason.MAXIMUM_HOLD


@pytest.mark.parametrize(
    ("session", "expected_boundary"),
    [(SESSION, SESSION), (date(2023, 11, 24), date(2023, 11, 24))],
)
def test_mandatory_liquidation_uses_published_normal_or_early_close(
    session: date, expected_boundary: date
) -> None:
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    assert schedule is not None
    boundary_local = schedule.closes_at - timedelta(minutes=5)
    entry_local = schedule.opens_at + timedelta(minutes=45)
    program, history, *_ = _b_history(
        session=session,
        exit_mode="liquidation",
        exit_delay_minutes=int((boundary_local - entry_local).total_seconds() // 60),
    )
    record = evaluator._simulate_session(
        history, _slot_for(program), session, arch151.FillCostCase.ZERO
    )

    trade = record.trades[0]
    assert trade.exit_reason is evaluator.ExitReason.SESSION_LIQUIDATION
    assert trade.exit.timestamp.astimezone(arch151.NEW_YORK).date() == expected_boundary
    assert trade.exit.timestamp == boundary_local.astimezone(arch151.UTC)
    assert trade.exit.reference_price == Decimal("100.3")
    assert trade.exit_reason is evaluator.ExitReason.SESSION_LIQUIDATION


def test_missing_mandatory_liquidation_fails_with_position_evidence() -> None:
    program, history, _entry_time, _target, _stop, _boundary = _b_history(
        exit_mode="none"
    )
    record = evaluator._simulate_session(
        history, _slot_for(program), SESSION, arch151.FillCostCase.STRESS
    )

    assert record.failure is not None
    assert (
        record.failure.kind
        is evaluator.ReplayFailureKind.MANDATORY_LIQUIDATION_UNOBSERVED
    )
    assert (
        record.failure.pending_exit_reason is evaluator.ExitReason.SESSION_LIQUIDATION
    )
    assert record.failure.entry_fill is not None
    assert record.failure.quantity is not None
    assert len(record.fills) == 1
    assert record.closing_equity is None
    assert record.session_return is None


def test_family_c_positive_risk_survives_finite_decimal_stop_subtraction() -> None:
    program = next(
        item
        for item in arch151.CANONICAL_PROGRAMS
        if item.key is arch151.ProgramKey.C5_01
    )
    history, _signal_time, _exit_time = _c_history(program, "SPY")
    record = evaluator._simulate_session(
        history, _slot_for(program), SESSION, arch151.FillCostCase.BASE
    )

    assert len(record.trades) == 1
    trade = record.trades[0]
    assert trade.initial_risk.is_finite()
    assert trade.initial_risk > 0
    assert trade.initial_stop_reference > 0


def test_a_trailing_stop_from_a_completed_bar_is_prospective_and_monotonic() -> None:
    program = next(
        item
        for item in arch151.CANONICAL_PROGRAMS
        if item.key is arch151.ProgramKey.A5_01
    )
    history, _ = _a_history(program, "SPY")
    baseline = evaluator._simulate_session(
        history, _slot_for(program), SESSION, arch151.FillCostCase.ZERO
    )
    baseline_trade = baseline.trades[0]
    entry_time = baseline_trade.entry.timestamp
    entry_price = baseline_trade.entry.reference_price
    risk = baseline_trade.initial_risk
    projection = history._projection_index[("SPY", SESSION, program.resolution)]
    revised_minutes = []
    for minute in projection.minutes:
        offset = int((minute.timestamp - entry_time).total_seconds() // 60)
        if offset == 0:
            opening = entry_price
            high = entry_price + risk * Decimal("0.05")
            low = entry_price - risk * Decimal("0.1")
            close = entry_price
        elif 1 <= offset < int(program.resolution):
            opening = entry_price + risk * Decimal("0.05")
            high = entry_price + risk * Decimal("1.2")
            low = entry_price - risk * Decimal("0.3")
            close = opening
        elif offset == int(program.resolution):
            opening = entry_price + risk * Decimal("0.1")
            high = opening + risk * Decimal("0.02")
            low = opening - risk * Decimal("0.02")
            close = opening
        else:
            revised_minutes.append(minute)
            continue
        revised_minutes.append(
            arch151.OneMinuteBar(
                minute.symbol,
                minute.timestamp,
                opening,
                high,
                low,
                close,
                minute.volume,
            )
        )
    revised = arch151._test_only_synthetic_source_history(
        (*_a_prior_minutes("SPY"), *revised_minutes)
    )
    record = evaluator._simulate_session(
        revised, _slot_for(program), SESSION, arch151.FillCostCase.ZERO
    )

    trade = record.trades[0]
    assert trade.exit.timestamp == entry_time + timedelta(
        minutes=int(program.resolution)
    )
    assert trade.exit_reason is evaluator.ExitReason.STOP_GAP
    assert trade.final_stop_reference > trade.initial_stop_reference
    assert trade.exit.reference_price > trade.initial_stop_reference
    assert trade.exit.reference_price <= trade.final_stop_reference


@pytest.mark.parametrize(
    ("case", "expected_bps"),
    [
        (arch151.FillCostCase.ZERO, Decimal(0)),
        (arch151.FillCostCase.BASE, Decimal(2)),
        (arch151.FillCostCase.STRESS, Decimal(5)),
    ],
)
def test_each_cost_case_applies_adverse_cost_once_per_actual_fill(
    case: arch151.FillCostCase, expected_bps: Decimal
) -> None:
    program, history, *_ = _b_history()
    record = evaluator._simulate_session(history, _slot_for(program), SESSION, case)

    assert len(record.fills) == 2
    with localcontext(arch151._DECIMAL_CONTEXT):
        for fill in record.fills:
            assert fill.adverse_cost == fill.quantity * abs(
                fill.execution_price - fill.reference_price
            )
            expected = fill.reference_price * expected_bps / Decimal(10000)
            assert abs(
                abs(fill.execution_price - fill.reference_price) - expected
            ) < Decimal("1e-55")
    assert record.trades[0].gross_exposure_fraction <= Decimal(1)


def test_canonical_year_batch_keeps_all_slots_costs_and_full_session_denominators() -> (
    None
):
    program, history, *_ = _b_history()
    batch = evaluator.simulate_canonical_year(history, 2023)

    assert batch.batch_id == evaluator._canonical_year_batch_id(
        batch.source_binding, batch.scored_year, batch.evaluations
    )
    assert len(batch.evaluations) == len(arch151.CANONICAL_SLOTS) * 3
    assert tuple(item.slot.slot_id for item in batch.evaluations) == tuple(
        slot.slot_id
        for slot in arch151.CANONICAL_SLOTS
        for _case in arch151.EVALUATION_ECONOMICS_ORDER
    )
    assert tuple(item.cost_case for item in batch.evaluations[:3]) == (
        arch151.FillCostCase.BASE,
        arch151.FillCostCase.STRESS,
        arch151.FillCostCase.ZERO,
    )
    slot = _slot_for(program)
    selected = tuple(item for item in batch.evaluations if item.slot == slot)
    assert len(selected) == 3
    assert all(item.complete and item.initial_equity == Decimal(1) for item in selected)
    assert all(
        len(item.sessions) == len(arch151._published_sessions_for_year(2023))
        for item in selected
    )
    missing_date = next(
        session
        for session in arch151._published_sessions_for_year(2023)
        if session != SESSION
    )
    assert all(
        next(
            item for item in yearly.sessions if item.session_date == missing_date
        ).session_return
        == Decimal(0)
        for yearly in selected
    )
    assert not batch.complete
    assert len(batch.evaluations) == len(arch151.CANONICAL_SLOTS) * 3


@pytest.mark.parametrize(
    "program", arch151.CANONICAL_PROGRAMS, ids=lambda item: item.key.value
)
@pytest.mark.parametrize("symbol", arch151.INITIAL_UNIVERSE)
def test_all_canonical_signals_enter_and_exit_through_unmocked_predicates(
    program: arch151.Arch151Program, symbol: str
) -> None:
    history, session, expected_entry, expected_exit = _source_for_program(
        program, symbol
    )
    record = evaluator._simulate_session(
        history, _slot_for(program, symbol), session, arch151.FillCostCase.BASE
    )

    assert record.failure is None, program.key
    assert len(record.trades) == 1, (program.key, symbol, record.signal_rejections)
    trade = record.trades[0]
    assert trade.symbol == symbol
    assert trade.program_id == _slot_for(program, symbol).program_id
    assert trade.entry.timestamp == expected_entry or (
        expected_entry is None and trade.entry.timestamp < trade.exit.timestamp
    )
    if isinstance(expected_exit, tuple):
        expected_reason, expected_timestamp = expected_exit
        assert trade.exit_reason is expected_reason
        assert trade.exit.timestamp == expected_timestamp
    else:
        assert trade.exit_reason is expected_exit
    assert len(record.fills) == 2
    assert trade.entry.cash_after >= 0
    assert trade.gross_exposure_fraction <= Decimal(1)
    with localcontext(arch151._DECIMAL_CONTEXT):
        assert trade.net_pnl == record.closing_equity - record.starting_equity


def test_family_c_cooldown_and_reversion_exit_survive_a_missing_next_open() -> None:
    program = next(
        item
        for item in arch151.CANONICAL_PROGRAMS
        if item.key is arch151.ProgramKey.C5_01
    )
    history, first_signal, second_signal, second_exit = _c_two_entry_history(
        program, "SPY"
    )
    sparse = history._projection_index[("SPY", SESSION, program.resolution)]
    stream = next(
        item
        for item in sparse.aggregate_streams
        if item.resolution is program.resolution
    )
    missing_bucket_start = first_signal + timedelta(minutes=program.resolution)
    assert all(
        not (
            missing_bucket_start
            <= bar.timestamp
            < missing_bucket_start + timedelta(minutes=program.resolution)
        )
        for bar in stream.bars
    )

    record = evaluator._simulate_session(
        history,
        _slot_for(program, "SPY"),
        SESSION,
        arch151.FillCostCase.BASE,
    )

    assert record.failure is None
    assert len(record.trades) == 2
    first, second = record.trades
    assert first.exit_reason is evaluator.ExitReason.VWAP_REVERSION
    assert first.exit.timestamp > first_signal + timedelta(minutes=program.resolution)
    assert second.entry.timestamp == second_signal
    assert second.entry.timestamp >= first.exit.timestamp + timedelta(
        minutes=program.parameters.cooldown_minutes
    )
    assert second.exit_reason is evaluator.ExitReason.MAXIMUM_HOLD
    assert second.exit.timestamp == second_exit


@cache
def _idle_session_records_for_year(
    year: int,
) -> tuple[evaluator.SessionReplayRecord, ...]:
    return tuple(
        evaluator.SessionReplayRecord(
            UUID(int=year * 10_000 + index + 1),
            session_date,
            Decimal(1),
            Decimal(1),
            Decimal(0),
            (),
            (),
            (),
            (),
            Decimal(0),
            None,
        )
        for index, session_date in enumerate(arch151._published_sessions_for_year(year))
    )


def _complete_idle_year_batch(year: int) -> evaluator.CanonicalYearBatch:
    source_digest = "a" * 64
    cost_index = {
        case: index for index, case in enumerate(arch151.EVALUATION_ECONOMICS_ORDER)
    }
    evaluations = tuple(
        evaluator.SlotYearReplay(
            UUID(int=year * 1_000_000 + slot.ordinal * 10 + cost_index[cost] + 1),
            slot,
            year,
            cost,
            source_digest,
            _idle_session_records_for_year(year),
            (),
            True,
            Decimal(1),
            Decimal(1),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            None,
        )
        for slot in arch151.CANONICAL_SLOTS
        for cost in arch151.EVALUATION_ECONOMICS_ORDER
    )
    source_binding = evaluator._synthetic_source_binding_for_test(source_digest)
    return evaluator.CanonicalYearBatch(
        evaluator._canonical_year_batch_id(source_binding, year, evaluations),
        year,
        arch151.CANONICAL_MANIFEST.manifest_id,
        arch151.CANONICAL_MANIFEST.fingerprint,
        source_digest,
        evaluations,
        source_binding,
        evaluator._CANONICAL_YEAR_BATCH_SEAL,
    )


def test_development_composition_preserves_all_480_fold_slot_cost_records() -> None:
    year_batches = tuple(
        _complete_idle_year_batch(year) for year in arch151.SCORED_YEARS
    )
    run = evaluator.compose_development_evaluation(year_batches)

    assert len(run.year_batches) == 5
    assert (
        tuple(batch.scored_year for batch in run.year_batches) == arch151.SCORED_YEARS
    )
    assert run.fold_evaluation_count == 480
    assert tuple(batch.slot_id for batch in run.slot_batches) == tuple(
        slot.slot_id for slot in arch151.CANONICAL_SLOTS
    )
    assert all(len(batch.records) == 15 for batch in run.slot_batches)
    assert (
        run.selection_bias.status
        is arch151.SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    assert (
        run.selection_bias.unavailable_reason
        is arch151.DsrUnavailableReason.UNDEFINED_TRIAL_SHARPE
    )
    assert run.final_freeze.candidate_slot_id is None
    assert run.ranking_order == ()
    assert len(run.qualifications) == 32

    changed_binding = evaluator._synthetic_source_binding_for_test("b" * 64)
    changed_last = replace(
        year_batches[-1],
        batch_id=evaluator._canonical_year_batch_id(
            changed_binding, year_batches[-1].scored_year, year_batches[-1].evaluations
        ),
        source_digest="b" * 64,
        source_binding=changed_binding,
    )
    with pytest.raises(evaluator.EvaluationIntegrityError, match="share exact source"):
        evaluator.compose_development_evaluation((*year_batches[:-1], changed_last))


def test_source_owned_report_binds_all_records_provenance_dsr_and_freeze() -> None:
    run = evaluator.compose_development_evaluation(
        tuple(_complete_idle_year_batch(year) for year in arch151.SCORED_YEARS)
    )

    report = evaluator.serialize_development_evaluation(run)
    repeated = evaluator.serialize_development_evaluation(run)
    payload = json.loads(report.canonical_json_bytes)

    assert report == repeated
    assert report.run_id == run.run_id
    assert report.source_binding_id == run.source_binding.binding_id
    assert report.manifest_id == arch151.CANONICAL_MANIFEST.manifest_id
    assert report.manifest_fingerprint == arch151.CANONICAL_MANIFEST.fingerprint
    assert report.record_count == 480
    assert report.sha256 == sha256(report.canonical_json_bytes).hexdigest()
    assert payload["schema"] == "arch151-development-evaluation-report/v1"
    assert payload["run"]["run_id"] == str(run.run_id)
    assert payload["run"]["source_digest"] == run.source_digest
    assert (
        payload["run"]["source_binding"]["kind"]
        == evaluator.DevelopmentSourceKind.SYNTHETIC_TEST_ONLY.value
    )
    assert payload["run"]["source_binding"]["dataset_id"] is None
    assert payload["record_count"] == len(payload["fold_records"]) == 480
    assert len(payload["year_batches"]) == 5
    assert len(payload["slot_year_replays"]) == 480
    assert len(payload["slot_batches"]) == len(arch151.CANONICAL_SLOTS)
    assert len(payload["qualifications"]) == len(arch151.CANONICAL_SLOTS)
    assert payload["selection_bias"]["calculation_id"] == str(
        run.selection_bias.calculation_id
    )
    assert payload["selection_bias"]["evidence"] == []
    assert payload["final_freeze"]["freeze_id"] == str(run.final_freeze.freeze_id)
    assert payload["final_freeze"]["candidate_slot_id"] is None
    assert all(
        replay["signal_counts"]
        == {"generated": 0, "eligible": 0, "executed": 0, "expired": 0, "blocked": 0}
        for replay in payload["slot_year_replays"]
    )


def test_unissued_development_batch_run_and_report_constructors_fail_closed() -> None:
    with pytest.raises(arch151.AuthorizationUnavailableError, match="source adapter"):
        evaluator.DevelopmentSourceBinding(
            kind=evaluator.DevelopmentSourceKind.SYNTHETIC_TEST_ONLY,
            source_digest="a" * 64,
        )

    batch = _complete_idle_year_batch(arch151.SCORED_YEARS[0])
    with pytest.raises(arch151.AuthorizationUnavailableError, match="evaluator"):
        evaluator.CanonicalYearBatch(
            batch.batch_id,
            batch.scored_year,
            batch.manifest_id,
            batch.manifest_fingerprint,
            batch.source_digest,
            batch.evaluations,
            batch.source_binding,
            None,
        )

    run = evaluator.compose_development_evaluation(
        tuple(_complete_idle_year_batch(year) for year in arch151.SCORED_YEARS)
    )
    with pytest.raises(arch151.AuthorizationUnavailableError, match="composed"):
        evaluator.serialize_development_evaluation(replace(run, _seal=None))

    with pytest.raises(arch151.AuthorizationUnavailableError, match="composed"):
        evaluator.DevelopmentEvaluationReport(
            report_id=run.run_id,
            run_id=run.run_id,
            source_binding_id=run.source_binding.binding_id,
            manifest_id=arch151.CANONICAL_MANIFEST.manifest_id,
            manifest_fingerprint=arch151.CANONICAL_MANIFEST.fingerprint,
            record_count=480,
            canonical_json_bytes=b"{}",
            sha256_digest=sha256(b"{}").hexdigest(),
        )


def test_year_batch_identity_binds_complete_replay_outputs() -> None:
    year_batches = tuple(
        _complete_idle_year_batch(year) for year in arch151.SCORED_YEARS
    )
    first = year_batches[0]
    replay = first.evaluations[0]
    changed_replay = replace(replay, turnover=Decimal("1"))
    assert replay.replay_digest != changed_replay.replay_digest
    changed_first = replace(
        first,
        evaluations=(changed_replay, *first.evaluations[1:]),
    )

    with pytest.raises(evaluator.EvaluationIntegrityError, match="batch IDs"):
        evaluator.compose_development_evaluation((changed_first, *year_batches[1:]))
