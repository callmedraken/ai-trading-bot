"""Synthetic execution contracts for the Arch151 evaluator."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from functools import cache
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID, uuid5

import pytest

from trading_bot.experiments import arch150_g1_discovery as arch150_d1r
from trading_bot.experiments import arch150_intraday_ai as arch150
from trading_bot.experiments import arch151_intraday_walkforward as arch151
from trading_bot.experiments import arch151_intraday_walkforward_evaluator as evaluator
from trading_bot.experiments import arch151_intraday_walkforward_operator as operator

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
    entry_reference: Decimal = Decimal("100.2"),
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
    risk = entry_reference - stop
    target = entry_reference + parameters.target_r * risk
    if entry_observed:
        entry_low = (
            stop - Decimal("0.01")
            if ambiguous_entry_range
            else max(stop + Decimal("0.01"), entry_reference - Decimal("0.01"))
        )
        entry_high = (
            target + Decimal("0.01")
            if ambiguous_entry_range
            else min(target - Decimal("0.01"), entry_reference + Decimal("0.1"))
        )
        minutes.append(
            arch151.OneMinuteBar(
                "SPY",
                entry_time,
                entry_reference,
                entry_high,
                entry_low,
                min(entry_high, entry_reference + Decimal("0.05")),
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
                    entry_reference,
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
                entry_reference,
                entry_reference + Decimal("0.1"),
                entry_reference - Decimal("0.1"),
                entry_reference + Decimal("0.05"),
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


def _synthetic_benchmark_history(
    year: int = 2019, *, missing_start: bool = False, missing_end: bool = False
):
    sessions = arch151._published_sessions_for_year(year)
    first_date, last_date = sessions[0], sessions[-1]
    minutes: list[arch151.OneMinuteBar] = []
    for session, role in ((first_date, "first"), (last_date, "last")):
        schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
        assert schedule is not None
        scheduled_minutes = int(
            (schedule.closes_at - schedule.opens_at).total_seconds() // 60
        )
        if role == "first":
            offsets = range(15, 30) if missing_start else range(0, 15)
        else:
            offsets = (
                range(scheduled_minutes - 30, scheduled_minutes - 15)
                if missing_end
                else range(scheduled_minutes - 15, scheduled_minutes)
            )
        for offset in offsets:
            opening = Decimal("100")
            closing = (
                Decimal("110")
                if role == "last" and offset == scheduled_minutes - 1
                else opening
            )
            high = max(opening, closing) + Decimal("0.01")
            low = min(opening, closing) - Decimal("0.01")
            minutes.append(
                arch151.OneMinuteBar(
                    "SPY",
                    schedule.opens_at + timedelta(minutes=offset),
                    opening,
                    high,
                    low,
                    closing,
                    100,
                )
            )
    return arch151._test_only_synthetic_source_history(minutes)


def _synthetic_campaign_measures(
    _history, symbol: str, scored_year: int
) -> tuple[arch151.FamilyASessionMeasure, ...]:
    """Create deterministic test-only prior measures for full composition."""

    prior_dates = tuple(
        session
        for session in arch151._SESSION_AUTHORITY.published.sessions
        if date(2016, 1, 1) <= session < date(scored_year, 1, 1)
    )[-60:]
    return tuple(
        arch151.FamilyASessionMeasure(
            symbol,
            arch151.FamilyAMeasureScope.COMPLETE_HISTORICAL_SESSION,
            session,
            Decimal("100"),
            Decimal("110"),
            Decimal("0.1"),
            sha256(
                f"synthetic-prior:{symbol}:{session.isoformat()}".encode()
            ).hexdigest(),
            _seal=arch151._FAMILY_A_MEASURE_SEAL,
        )
        for session in prior_dates
    )


def _synthetic_five_year_campaign_history():
    """Generate a complete campaign with representative 2023 family signals."""
    minutes_by_key = {}

    def retain(items) -> None:
        for minute in items:
            minutes_by_key[minute.symbol, minute.timestamp] = minute

    def shift_fractional_price_level(items):
        offset = Decimal("0.03125")
        for minute in items:
            with localcontext(arch151._DECIMAL_CONTEXT):
                yield replace(
                    minute,
                    open=minute.open + offset,
                    high=minute.high + offset,
                    low=minute.low + offset,
                    close=minute.close + offset,
                )

    for year in arch151.SCORED_YEARS:
        signal_session = arch151._published_sessions_for_year(year)[1]
        retain(_campaign_signal_session_minutes(signal_session))
        benchmark = _synthetic_benchmark_history(year)
        retain(
            minute
            for projection in benchmark._session_projections
            for minute in projection.minutes
        )

    for symbol in arch151.INITIAL_UNIVERSE:
        retain(shift_fractional_price_level(_a_prior_minutes(symbol)))

    selected_keys = (
        arch151.ProgramKey.A5_01,
        arch151.ProgramKey.A15_01,
        arch151.ProgramKey.B5_01,
        arch151.ProgramKey.B15_01,
        arch151.ProgramKey.C5_01,
        arch151.ProgramKey.C15_01,
        arch151.ProgramKey.D5_01,
        arch151.ProgramKey.D15_01,
    )
    target_dates = arch151._published_sessions_for_year(2023)[10:20]
    assert len(target_dates) == 10
    representative_sessions: dict[tuple[arch151.ProgramKey, str], date] = {}
    flat_target_dates: set[date] = set()
    target_index = 0
    for key in selected_keys:
        program = next(item for item in arch151.CANONICAL_PROGRAMS if item.key is key)
        if program.family is arch151.StrategyFamily.CROSS_ETF_TREND_PULLBACK:
            selected_targets = {
                symbol: target_dates[target_index + offset]
                for offset, symbol in enumerate(arch151.INITIAL_UNIVERSE)
            }
            target_index += len(arch151.INITIAL_UNIVERSE)
        else:
            target = target_dates[target_index]
            target_index += 1
            selected_targets = {symbol: target for symbol in arch151.INITIAL_UNIVERSE}
        for symbol, target in selected_targets.items():
            representative_sessions[key, symbol] = target
            if target not in flat_target_dates:
                schedule = arch151._SESSION_AUTHORITY.schedule_for(target)
                assert schedule is not None
                count = int(
                    (schedule.closes_at - schedule.opens_at).total_seconds() // 60
                )
                retain(
                    arch151.OneMinuteBar(
                        item,
                        schedule.opens_at + timedelta(minutes=offset),
                        Decimal("100"),
                        Decimal("100.01"),
                        Decimal("99.99"),
                        Decimal("100"),
                        100,
                    )
                    for item in arch151.INITIAL_UNIVERSE
                    for offset in range(count)
                )
                flat_target_dates.add(target)
            source_history, source_session, *_ = _source_for_program(program, symbol)
            assert source_session == SESSION
            source_symbols = (
                arch151.INITIAL_UNIVERSE
                if program.family is arch151.StrategyFamily.CROSS_ETF_TREND_PULLBACK
                else (symbol,)
            )
            shift = target - source_session
            for source_symbol in source_symbols:
                projection = source_history._projection_index[
                    (source_symbol, source_session, program.resolution)
                ]
                pattern_minutes = projection.minutes
                if program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT:
                    pattern_minutes = tuple(
                        shift_fractional_price_level(pattern_minutes)
                    )
                retain(
                    replace(
                        minute,
                        timestamp=minute.timestamp + timedelta(days=shift.days),
                    )
                    for minute in pattern_minutes
                )

    history = arch151._test_only_synthetic_source_history(
        tuple(
            sorted(
                minutes_by_key.values(),
                key=lambda minute: (minute.symbol, minute.timestamp),
            )
        )
    )
    return history, representative_sessions


def _campaign_signal_session_minutes(session: date) -> tuple[arch151.OneMinuteBar, ...]:
    """Generate one complete SPY/QQQ session containing a B5 trade setup."""
    program, b_history, *_ = _b_history(session=session)
    assert program.key is arch151.ProgramKey.B5_01
    projection = next(
        item
        for item in b_history._session_projections
        if item.symbol == "SPY" and item.session_date == session
    )
    supplied_minutes = {item.timestamp: item for item in projection.minutes}
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    assert schedule is not None
    count = int((schedule.closes_at - schedule.opens_at).total_seconds() // 60)
    minutes = tuple(
        (supplied_minutes.get(timestamp) if symbol == "SPY" else None)
        or arch151.OneMinuteBar(
            symbol,
            timestamp,
            Decimal("100"),
            Decimal("100.01"),
            Decimal("99.99"),
            Decimal("100"),
            100,
        )
        for symbol in arch151.INITIAL_UNIVERSE
        for offset in range(count)
        for timestamp in (schedule.opens_at + timedelta(minutes=offset),)
    )
    return minutes


def _flat_arch150_session_bars(
    session: date, symbol: str
) -> tuple[arch150.IntradayBar, ...]:
    schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
    assert schedule is not None
    count = int((schedule.closes_at - schedule.opens_at).total_seconds() // 60)
    base = Decimal("100") + Decimal(session.toordinal() % 31) / Decimal(100)
    return tuple(
        arch150.IntradayBar(
            symbol,
            schedule.opens_at + timedelta(minutes=offset),
            opening,
            opening + Decimal("0.02"),
            opening - Decimal("0.02"),
            opening + Decimal("0.001"),
            100,
            arch150.BarResolution.ONE_MINUTE,
        )
        for offset in range(count)
        for opening in (base + Decimal(offset) / Decimal(10000),)
    )


def _arch150_adapter_fixture():
    scored_sessions = arch151._published_sessions_for_year(2021)
    prior_sessions = tuple(
        session
        for session in arch151._SESSION_AUTHORITY.published.sessions
        if session < date(2021, 1, 1)
    )[-60:]
    signal_session = scored_sessions[1]
    published_sessions = arch151._SESSION_AUTHORITY.published.sessions
    source_sessions = tuple(
        sorted(
            {
                next(item for item in published_sessions if item.year == 2016),
                *prior_sessions,
                scored_sessions[0],
                signal_session,
                scored_sessions[-1],
                next(item for item in published_sessions if item.year == 2023),
            }
        )
    )
    signal_minutes = _campaign_signal_session_minutes(signal_session)
    minutes_by_symbol: dict[str, list[arch151.OneMinuteBar]] = {
        symbol: [] for symbol in arch151.INITIAL_UNIVERSE
    }
    for session in source_sessions:
        session_minutes = (
            tuple(item for item in signal_minutes if item.session_date == session)
            if session == signal_session
            else tuple(
                arch151.OneMinuteBar(
                    bar.symbol,
                    bar.timestamp,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                )
                for symbol in arch151.INITIAL_UNIVERSE
                for bar in _flat_arch150_session_bars(session, symbol)
            )
        )
        for minute in session_minutes:
            minutes_by_symbol[minute.symbol].append(minute)
    source_bars = tuple(
        arch150.IntradayBar(
            minute.symbol,
            minute.timestamp,
            minute.open,
            minute.high,
            minute.low,
            minute.close,
            minute.volume,
            arch150.BarResolution.ONE_MINUTE,
        )
        for symbol in arch151.INITIAL_UNIVERSE
        for minute in minutes_by_symbol[symbol]
    )
    validated_bars = arch150.validate_universe_minute_bars(source_bars)
    accepted_csv_hashes = dict(arch150._ACCEPTED_NORMALIZED_CSV_SHA256)
    artifacts = tuple(
        arch150_d1r.ArtifactCommitment(
            name,
            byte_length,
            accepted_csv_hashes.get(
                name.removeprefix("normalized/").removesuffix(".csv"),
                "a" * 64,
            ),
        )
        for name, byte_length in arch150_d1r._ARTIFACT_LENGTHS.items()
    )
    snapshot = arch150_d1r.InputSnapshot(source_bars, artifacts)
    return snapshot, validated_bars, source_sessions, signal_session


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
    )[-61:]
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


@cache
def _a_history(symbol: str):
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
        history, session = _a_history(symbol)
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
    assert trade.excursion_minute_count == 1
    assert trade.mfe_return is not None and trade.mfe_return > 0
    assert trade.mae_return is not None and trade.mae_return < 0
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
    assert record.trades[0].mfe_return is None
    assert record.trades[0].mae_return is None
    assert record.trades[0].excursion_minute_count == 0


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
    history, _ = _a_history("SPY")
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


def test_stress_pf_uses_net_winning_and_losing_trade_outcomes() -> None:
    program, history, _entry_time, _target, _stop, _boundary = _b_history(
        entry_reference=Decimal("100.04")
    )
    slot = _slot_for(program)
    source_digest = evaluator._history_digest(history)

    def make_complete_year(case: arch151.FillCostCase):
        trade_session = evaluator._simulate_session(history, slot, SESSION, case)
        assert len(trade_session.trades) == 1
        trade = trade_session.trades[0]
        assert trade.gross_pnl > 0
        if case is arch151.FillCostCase.STRESS:
            assert trade.net_pnl < 0
        else:
            assert trade.net_pnl > 0
        equity = Decimal(1)
        sessions = []
        for session in arch151._published_sessions_for_year(2023):
            if session == SESSION:
                record = trade_session
            else:
                record = evaluator._idle_session(
                    history_digest=source_digest,
                    slot=slot,
                    case=case,
                    session=session,
                    starting_equity=equity,
                )
            sessions.append(record)
            assert record.closing_equity is not None
            equity = record.closing_equity
        replay = evaluator._finish_slot_year(
            history_digest=source_digest,
            slot=slot,
            year=2023,
            case=case,
            sessions=tuple(sessions),
        )
        return trade, replay, evaluator._fold_metrics_from_slot_year(replay)

    stress_trade, stress_replay, stress_metrics = make_complete_year(
        arch151.FillCostCase.STRESS
    )
    base_trade, _base_replay, base_metrics = make_complete_year(
        arch151.FillCostCase.BASE
    )

    assert stress_trade.gross_pnl > 0 > stress_trade.net_pnl
    assert stress_metrics.pre_cost_profit_factor.state is (
        arch151.ProfitFactorState.POSITIVE_INFINITY
    )
    assert stress_metrics.profit_factor.state is arch151.ProfitFactorState.FINITE
    assert stress_metrics.profit_factor.finite_value == Decimal(0)
    assert stress_metrics.net_positive_trade_pnl == 0
    assert stress_metrics.net_negative_trade_pnl > 0
    assert base_trade.net_pnl > 0
    assert (
        base_metrics.profit_factor.state is arch151.ProfitFactorState.POSITIVE_INFINITY
    )
    with pytest.raises(
        evaluator.EvaluationIntegrityError,
        match="realized P&L totals do not reconcile",
    ):
        evaluator._fold_metrics_from_slot_year(
            replace(
                stress_replay,
                positive_net_pnl=stress_replay.positive_net_pnl + Decimal("0.01"),
            )
        )


@pytest.fixture(scope="module")
def multi_trade_slot_year() -> evaluator.SlotYearReplay:
    program, winning_history, *_ = _b_history()
    _, losing_history, *_ = _b_history(exit_mode="stop_gap")
    templates = []
    for history, price in (
        (winning_history, Decimal("102.2")),
        (losing_history, Decimal("98.2")),
    ):
        bars = history._session_projections[0].minutes
        exit_bar = replace(bars[-1], open=price, high=price, low=price, close=price)
        templates.append((*bars[:-1], exit_bar))
    template_schedule = arch151._SESSION_AUTHORITY.schedule_for(SESSION)
    assert template_schedule is not None
    template_open = template_schedule.opens_at.astimezone(UTC)
    minutes = []
    for index, session in enumerate(arch151._published_sessions_for_year(2023)[:210]):
        schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
        assert schedule is not None
        offset = schedule.opens_at.astimezone(UTC) - template_open
        minutes.extend(
            replace(bar, timestamp=bar.timestamp + offset)
            for bar in templates[index % len(templates)]
        )
    history = arch151._test_only_synthetic_source_history(minutes)
    return next(
        replay
        for replay in evaluator._simulate_slot_year_cases(
            history, _slot_for(program), 2023
        )
        if replay.cost_case is arch151.FillCostCase.BASE
    )


def test_fold_cash_reconciliation_accepts_finite_precision_trade_accumulation(
    multi_trade_slot_year: evaluator.SlotYearReplay,
) -> None:
    replay = multi_trade_slot_year
    assert replay.complete and len(replay.trades) == 210
    assert replay.positive_net_pnl > 0 and replay.negative_net_pnl > 0
    with localcontext(arch151._DECIMAL_CONTEXT):
        grouped_net = replay.positive_net_pnl - replay.negative_net_pnl
        assert replay.net_return - grouped_net == Decimal("-5E-60")

    with localcontext() as ambient:
        ambient.prec = 8
        metrics = evaluator._fold_metrics_from_slot_year(replay)

    assert sum(metrics.round_trips_by_session) == 210
    assert metrics.net_positive_trade_pnl == replay.positive_net_pnl
    assert metrics.net_negative_trade_pnl == replay.negative_net_pnl
    assert metrics.profit_factor == arch151.ProfitFactor.from_totals(
        replay.positive_net_pnl, replay.negative_net_pnl
    )


def test_fold_cash_reconciliation_rejects_materially_incorrect_trade_pnl(
    multi_trade_slot_year: evaluator.SlotYearReplay,
) -> None:
    replay = multi_trade_slot_year
    first, *remaining = replay.sessions
    (trade,) = first.trades
    with localcontext(arch151._DECIMAL_CONTEXT):
        changed_trade = replace(trade, net_pnl=trade.net_pnl + Decimal("0.01"))
    changed_session = replace(first, trades=(changed_trade,))
    tampered = evaluator._finish_slot_year(
        history_digest=replay.source_digest,
        slot=replay.slot,
        year=replay.scored_year,
        case=replay.cost_case,
        sessions=(changed_session, *remaining),
    )

    with pytest.raises(
        evaluator.EvaluationIntegrityError,
        match="trade net P&L does not reconcile to fill cash",
    ):
        evaluator._fold_metrics_from_slot_year(tampered)


def test_canonical_year_batch_keeps_all_slots_costs_and_full_session_denominators() -> (
    None
):
    program, history, *_ = _b_history()
    batch = evaluator.simulate_canonical_year(history, 2023)

    assert batch.batch_id == evaluator._canonical_year_batch_id(
        batch.source_binding,
        batch.scored_year,
        batch.evaluations,
        batch.passive_spy_benchmark,
    )
    assert evaluator._BATCH_NAMESPACE == uuid5(
        evaluator._NAMESPACE, "canonical-year-batch/v3"
    )
    assert batch.passive_spy_benchmark.scored_year == 2023
    assert batch.passive_spy_benchmark.source_digest == batch.source_digest
    assert (
        batch.passive_spy_benchmark.price_basis
        == "ALPACA_ALL_ADJUSTED_1MINUTE_PRICE_V1"
    )
    predecessor_batch_namespace = uuid5(evaluator._NAMESPACE, "canonical-year-batch/v2")
    predecessor_batch_material = {
        "schema": "arch151-canonical-year-batch/v2",
        "source_binding_id": str(batch.source_binding.binding_id),
        "source_digest": batch.source_digest,
        "manifest_id": str(batch.manifest_id),
        "manifest_fingerprint": batch.manifest_fingerprint,
        "scored_year": batch.scored_year,
        "replay_outputs": [
            {"replay_id": str(item.replay_id), "replay_digest": item.replay_digest}
            for item in batch.evaluations
        ],
    }
    predecessor_batch_id = evaluator._canonical_id(
        predecessor_batch_namespace,
        "arch151-canonical-year-batch/v2",
        predecessor_batch_material,
    )
    assert batch.batch_id != predecessor_batch_id
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


def test_family_d_program_pair_cache_matches_independent_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = next(
        item
        for item in arch151.CANONICAL_PROGRAMS
        if item.key is arch151.ProgramKey.D5_01
    )
    history, _signal_time, _boundary = _d_history(program, "SPY")
    slots = tuple(
        slot for slot in arch151.CANONICAL_SLOTS if slot.program_key is program.key
    )
    assert tuple(slot.symbol for slot in slots) == arch151.INITIAL_UNIVERSE
    original_prepare = arch151.prepare_session_features
    prepared_program_symbols: list[str] = []

    def counted_prepare(history, selected_program, symbol, session, cutoff):
        if selected_program.key is program.key:
            prepared_program_symbols.append(symbol)
        return original_prepare(history, selected_program, symbol, session, cutoff)

    monkeypatch.setattr(arch151, "prepare_session_features", counted_prepare)
    optimized_batch = evaluator.simulate_canonical_year(history, 2023)
    optimized_results = tuple(
        tuple(
            item
            for item in optimized_batch.evaluations
            if item.slot.slot_id == slot.slot_id
        )
        for slot in slots
    )
    optimized_preparations = tuple(prepared_program_symbols)

    prepared_program_symbols.clear()
    reference_results = tuple(
        evaluator._simulate_slot_year_cases(history, slot, 2023) for slot in slots
    )
    reference_preparations = tuple(prepared_program_symbols)

    assert optimized_results == reference_results
    assert optimized_preparations == ("SPY", "QQQ")
    assert reference_preparations == ("SPY", "QQQ", "QQQ", "SPY")


def test_family_a_calibration_cache_matches_per_program_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eligible_prior = tuple(
        session
        for session in arch151._SESSION_AUTHORITY.published.sessions
        if date(2016, 1, 1) <= session < date(2019, 1, 1)
    )
    history, _session = _a_history("SPY")
    programs = _programs_for_family(arch151.StrategyFamily.NOISE_VWAP_BREAKOUT)
    original_measure_source = arch151._family_a_historical_measures_from_source_history
    measured_sources: list[tuple[str, int]] = []

    def counted_measure_source(history, symbol, scored_year):
        measured_sources.append((symbol, scored_year))
        return original_measure_source(history, symbol, scored_year)

    monkeypatch.setattr(
        arch151,
        "_family_a_historical_measures_from_source_history",
        counted_measure_source,
    )
    cache = evaluator._FamilyACalibrationCache(history)
    optimized = tuple(cache.calibration(item, "SPY", 2023) for item in programs)
    assert measured_sources == [("SPY", 2023)]
    assert len(cache._measures[(history.source_digest, "SPY", 2023)]) == 60
    expected_calibration_dates = eligible_prior[-60:]
    assert all(
        item.calibration_session_dates == expected_calibration_dates
        for item in optimized
    )

    reference = tuple(
        arch151.calibrate_family_a_from_source_history(history, item, "SPY", 2023)
        for item in programs
    )
    assert optimized == reference
    assert measured_sources == [("SPY", 2023)] * 5


def test_generated_five_year_simulation_composes_non_idle_480_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_measure_function = arch151._family_a_historical_measures_from_source_history

    def campaign_measures(history, symbol: str, scored_year: int):
        if scored_year == 2023:
            return source_measure_function(history, symbol, scored_year)
        return _synthetic_campaign_measures(history, symbol, scored_year)

    monkeypatch.setattr(
        arch151, "_family_a_historical_measures_from_source_history", campaign_measures
    )
    history, representative_sessions = _synthetic_five_year_campaign_history()
    expected_binding = evaluator._synthetic_source_binding_for_test(
        history.source_digest
    )
    expected_rows = tuple(
        (slot, case)
        for slot in arch151.CANONICAL_SLOTS
        for case in arch151.EVALUATION_ECONOMICS_ORDER
    )
    year_batches = []
    for year in arch151.SCORED_YEARS:
        if year == 2023:
            with localcontext() as ambient:
                ambient.prec = 8
                year_batches.append(evaluator.simulate_canonical_year(history, year))
        else:
            year_batches.append(evaluator.simulate_canonical_year(history, year))
    year_batches = tuple(year_batches)
    for batch in year_batches:
        assert batch.complete
        assert batch.source_binding == expected_binding
        assert batch.source_digest == history.source_digest
        assert (
            tuple((item.slot, item.cost_case) for item in batch.evaluations)
            == expected_rows
        )
        assert all(
            item.source_digest == history.source_digest for item in batch.evaluations
        )
        assert {item.cost_case for item in batch.evaluations if item.trades} == set(
            arch151.EVALUATION_ECONOMICS_ORDER
        )
        assert batch.passive_spy_benchmark.status is evaluator.BenchmarkStatus.AVAILABLE

    run = evaluator.compose_development_evaluation(year_batches)
    report = evaluator.serialize_development_evaluation(run)
    assert sha256(report.canonical_json_bytes).hexdigest() == report.sha256

    revision = operator.SourceRevision(
        operator.EXPECTED_BRANCH,
        operator.EXPECTED_ORIGIN,
        "b" * 40,
        "c" * 40,
        _seal=operator._SOURCE_REVISION_SEAL,
    )
    representative_batch = next(
        item for item in year_batches if item.scored_year == 2023
    )
    year_evidence = operator._year_batch_material(
        representative_batch,
        revision=revision,
        attempt_id=UUID(int=9101),
        invocation_id=UUID(int=9102),
    )
    year_evidence_bytes = operator._canonical_bytes(year_evidence)
    serialized_year_evidence = json.loads(year_evidence_bytes)
    assert serialized_year_evidence["expected_replay_count"] == 96
    assert serialized_year_evidence["observed_replay_count"] == 96
    assert serialized_year_evidence["complete"] is True

    representative_programs = {
        key: next(item for item in arch151.CANONICAL_PROGRAMS if item.key is key)
        for key in (
            arch151.ProgramKey.A5_01,
            arch151.ProgramKey.A15_01,
            arch151.ProgramKey.B5_01,
            arch151.ProgramKey.B15_01,
            arch151.ProgramKey.C5_01,
            arch151.ProgramKey.C15_01,
            arch151.ProgramKey.D5_01,
            arch151.ProgramKey.D15_01,
        )
    }
    preparation_cache = evaluator._PreparationCache(history)
    calibration_cache = evaluator._FamilyACalibrationCache(history)
    with localcontext(arch151._DECIMAL_CONTEXT):
        expected_fractional_noise = abs(
            Decimal("100.13125") / Decimal("100.03125") - Decimal(1)
        )
    for symbol in arch151.INITIAL_UNIVERSE:
        source_calibration = calibration_cache.calibration(
            representative_programs[arch151.ProgramKey.A5_01], symbol, 2023
        )
        assert source_calibration.noise_return == expected_fractional_noise
    cross_context_representatives = {
        (arch151.ProgramKey.B5_01, "SPY"),
        (arch151.ProgramKey.B15_01, "QQQ"),
        (arch151.ProgramKey.C5_01, "SPY"),
        (arch151.ProgramKey.D5_01, "SPY"),
        (arch151.ProgramKey.D15_01, "QQQ"),
    }
    for (program_key, symbol), session_date in representative_sessions.items():
        program = representative_programs[program_key]
        slot = _slot_for(program, symbol)
        reference_tape = None
        if (
            program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT
            or (program_key, symbol) in cross_context_representatives
        ):
            calibration = (
                calibration_cache.calibration(program, symbol, 2023)
                if program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT
                else None
            )
            with localcontext(arch151._DECIMAL_CONTEXT):
                reference_tape = evaluator._session_tape(
                    history,
                    preparation_cache,
                    program,
                    symbol,
                    session_date,
                    calibration,
                )
        for case in arch151.EVALUATION_ECONOMICS_ORDER:
            annual_replay = next(
                item
                for item in representative_batch.evaluations
                if item.slot == slot and item.cost_case is case
            )
            annual_session = next(
                item
                for item in annual_replay.sessions
                if item.session_date == session_date
            )
            assert annual_session.trades, (program_key, symbol, case)
            if (
                program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT
                or (program_key, symbol) in cross_context_representatives
            ):
                projection = history._projection_index.get(
                    (symbol, session_date, program.resolution)
                )
                with localcontext(arch151._DECIMAL_CONTEXT):
                    normal_context_session = evaluator._simulate_session_from_tape(
                        history_digest=evaluator._history_digest(history),
                        slot=slot,
                        program=program,
                        session=session_date,
                        tape=reference_tape,
                        minutes=projection.minutes if projection is not None else (),
                        starting_equity=annual_session.starting_equity,
                        case=case,
                    )
                assert normal_context_session == annual_session, (
                    program_key,
                    symbol,
                    case,
                )

    assert len(representative_sessions) == 16
    assert len(set(representative_sessions.values())) == 10
    b5_spy = next(
        item
        for item in representative_batch.evaluations
        if item.slot
        == _slot_for(representative_programs[arch151.ProgramKey.B5_01], "SPY")
        and item.cost_case is arch151.FillCostCase.BASE
    )
    assert len({trade.entry.timestamp.date() for trade in b5_spy.trades}) >= 2

    assert run.fold_evaluation_count == 480
    assert tuple(item.scored_year for item in run.year_batches) == arch151.SCORED_YEARS
    assert len(run.slot_batches) == 32
    assert run.year_batches == year_batches
    assert run.source_binding == expected_binding
    assert run.source_digest == history.source_digest


def test_arch150_full_input_adapter_preserves_development_history_and_replays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, validated_bars, source_sessions, signal_session = (
        _arch150_adapter_fixture()
    )
    monkeypatch.setattr(
        arch151.arch150_d1r,
        "_read_pinned_input",
        lambda _root: snapshot,
    )
    monkeypatch.setattr(
        arch151.arch150,
        "_validate_accepted_sparse_custody",
        lambda _bars: validated_bars,
    )

    discovery = arch150.open_sparse_discovery_dataset(snapshot.bars)
    assert discovery.end_exclusive == date(2021, 1, 1)
    assert all(
        bar.session_date < date(2021, 1, 1)
        for symbol in arch150.INITIAL_UNIVERSE
        for bar in discovery.bars.by_symbol[symbol].bars
    )
    assert arch151.DEVELOPMENT_END == date(2024, 1, 1)

    synthetic_boundary = arch151._synthetic_arch150_d1r_custody_boundary_for_test(
        validated_bars
    )
    monkeypatch.setattr(
        arch151.arch150,
        "_validate_accepted_sparse_custody",
        lambda _bars: synthetic_boundary,
    )
    history = arch151._adapt_arch150_d1r_snapshot()

    assert type(history) is arch151._SyntheticSourceHistory
    assert not isinstance(history, arch151.Arch150D1RSourceHistory)
    assert history.source_digest != validated_bars.input_digest
    sessions_by_symbol = {
        symbol: tuple(
            item.session_date
            for item in history._session_projections
            if item.symbol == symbol
        )
        for symbol in arch151.INITIAL_UNIVERSE
    }
    for symbol in arch151.INITIAL_UNIVERSE:
        assert sessions_by_symbol[symbol] == source_sessions
        assert any(item < date(2021, 1, 1) for item in sessions_by_symbol[symbol])
        assert any(item >= date(2021, 1, 1) for item in sessions_by_symbol[symbol])
    assert all(
        type(item) is arch151._SyntheticSparseSessionEvidence
        for projection in history._session_projections
        for item in projection.verified_sessions
    )

    program = next(
        item
        for item in arch151.CANONICAL_PROGRAMS
        if item.key is arch151.ProgramKey.B5_01
    )
    schedule = arch151._SESSION_AUTHORITY.schedule_for(signal_session)
    assert schedule is not None
    prepared = arch151.prepare_session_features(
        history,
        program,
        "SPY",
        signal_session,
        schedule.opens_at + timedelta(minutes=45),
    )
    assert prepared.decision_bar is not None
    slot = next(
        item
        for item in arch151.CANONICAL_SLOTS
        if item.program_key is arch151.ProgramKey.B5_01 and item.symbol == "SPY"
    )
    replay = evaluator._simulate_slot_year(
        history,
        slot,
        2021,
        arch151.EVALUATION_ECONOMICS_ORDER[0],
    )
    assert replay.complete
    assert replay.trades
    binding = evaluator._development_source_binding(history)
    assert binding.kind is evaluator.DevelopmentSourceKind.SYNTHETIC_TEST_ONLY
    with pytest.raises(arch151.AuthorizationUnavailableError, match="accepted"):
        evaluator.evaluate_full_development_history(history)


@pytest.mark.parametrize(
    "mutation",
    (
        "reordered_symbols",
        "interleaved_symbols",
        "reordered_observations",
        "2024_input",
    ),
)
def test_arch150_adapter_rejects_invalid_population_before_custody_scan(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    snapshot, _validated_bars, _sessions, _signal_session = _arch150_adapter_fixture()
    bars = snapshot.bars
    if mutation == "reordered_symbols":
        bars = tuple(
            bar
            for symbol in ("QQQ", "SPY")
            for bar in snapshot.bars
            if bar.symbol == symbol
        )
    elif mutation == "interleaved_symbols":
        first_qqq = next(bar for bar in snapshot.bars if bar.symbol == "QQQ")
        bars = (snapshot.bars[0], first_qqq, *snapshot.bars[1:])
    elif mutation == "reordered_observations":
        bars = (snapshot.bars[1], snapshot.bars[0], *snapshot.bars[2:])
    else:
        bars = (
            replace(
                snapshot.bars[0],
                timestamp=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
            ),
            *snapshot.bars[1:],
        )
    invalid_snapshot = arch150_d1r.InputSnapshot(bars, snapshot.artifacts)
    monkeypatch.setattr(
        arch151.arch150_d1r, "_read_pinned_input", lambda _root: invalid_snapshot
    )
    monkeypatch.setattr(
        arch151.arch150,
        "_validate_accepted_sparse_custody",
        lambda _bars: pytest.fail("invalid populations fail before custody scan"),
    )

    with pytest.raises(arch151.AuthorizationUnavailableError) as error:
        arch151._adapt_arch150_d1r_snapshot()
    assert (
        error.value.source_load_reason
        is arch151.SourceLoadFailureReason.INVALID_DEVELOPMENT_POPULATION
    )


def test_arch150_adapter_rejects_truncated_population_at_custody_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, _validated_bars, _sessions, _signal_session = _arch150_adapter_fixture()
    truncated = arch150_d1r.InputSnapshot(snapshot.bars[:-1], snapshot.artifacts)
    monkeypatch.setattr(
        arch151.arch150_d1r, "_read_pinned_input", lambda _root: truncated
    )

    with pytest.raises(arch151.AuthorizationUnavailableError) as error:
        arch151._adapt_arch150_d1r_snapshot()
    assert (
        error.value.source_load_reason
        is arch151.SourceLoadFailureReason.CUSTODY_AUTHORITY_MISMATCH
    )


def test_arch150_adapter_rejects_mismatched_authority_and_projection_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, validated_bars, _sessions, _signal_session = _arch150_adapter_fixture()
    monkeypatch.setattr(
        arch151.arch150_d1r, "_read_pinned_input", lambda _root: snapshot
    )
    monkeypatch.setattr(
        arch151.arch150,
        "_validate_accepted_sparse_custody",
        lambda _bars: object(),
    )
    with pytest.raises(arch151.AuthorizationUnavailableError) as error:
        arch151._adapt_arch150_d1r_snapshot()
    assert (
        error.value.source_load_reason
        is arch151.SourceLoadFailureReason.CUSTODY_AUTHORITY_MISMATCH
    )

    custody = arch151._Arch150D1RDevelopmentCustody(
        validated_bars=validated_bars,
        authority=arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY,
        _seal=arch151._D1R_DEVELOPMENT_CUSTODY_SEAL,
    )
    spy_minutes = tuple(
        arch151.OneMinuteBar(
            bar.symbol,
            bar.timestamp,
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
        )
        for bar in validated_bars.by_symbol["SPY"].bars
    )
    qqq_minutes = tuple(
        arch151.OneMinuteBar(
            bar.symbol,
            bar.timestamp,
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
        )
        for bar in validated_bars.by_symbol["QQQ"].bars
    )
    changed_spy = (
        replace(spy_minutes[0], close=spy_minutes[0].close + Decimal("0.01")),
        *spy_minutes[1:],
    )
    with pytest.raises(arch151.AuthorizationUnavailableError) as error:
        arch151._source_session_projections(
            (("SPY", changed_spy), ("QQQ", qqq_minutes)),
            "b" * 64,
            accepted_custody=custody,
        )
    assert (
        error.value.source_load_reason
        is arch151.SourceLoadFailureReason.CUSTODY_AUTHORITY_MISMATCH
    )


def test_arch150_adapter_sanitizes_projection_construction_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, validated_bars, _sessions, _signal_session = _arch150_adapter_fixture()
    synthetic_boundary = arch151._synthetic_arch150_d1r_custody_boundary_for_test(
        validated_bars
    )
    monkeypatch.setattr(
        arch151.arch150_d1r, "_read_pinned_input", lambda _root: snapshot
    )
    monkeypatch.setattr(
        arch151.arch150,
        "_validate_accepted_sparse_custody",
        lambda _bars: synthetic_boundary,
    )

    def fail_projection(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("unrestricted fixture detail")

    monkeypatch.setattr(arch151, "_source_session_projections", fail_projection)
    with pytest.raises(arch151.AuthorizationUnavailableError) as error:
        arch151._adapt_arch150_d1r_snapshot()
    assert (
        error.value.source_load_reason
        is arch151.SourceLoadFailureReason.SOURCE_PROJECTION_CONSTRUCTION_FAILED
    )
    assert "unrestricted fixture detail" not in str(error.value)


def test_passive_spy_benchmark_binds_exact_adjusted_price_endpoints() -> None:
    history = _synthetic_benchmark_history()
    benchmark = evaluator._passive_benchmark_year(history, 2019)

    first_session, last_session = (
        arch151._published_sessions_for_year(2019)[0],
        arch151._published_sessions_for_year(2019)[-1],
    )
    first_schedule = arch151._SESSION_AUTHORITY.schedule_for(first_session)
    last_schedule = arch151._SESSION_AUTHORITY.schedule_for(last_session)
    assert first_schedule is not None and last_schedule is not None
    assert benchmark.status is evaluator.BenchmarkStatus.AVAILABLE
    assert benchmark.start_timestamp == first_schedule.opens_at
    assert benchmark.start_price == Decimal("100")
    assert benchmark.end_timestamp == last_schedule.closes_at
    assert benchmark.end_price == Decimal("110")
    assert benchmark.adjusted_price_return == Decimal("0.1")
    assert benchmark.adjustment == "all"
    assert (
        benchmark.adjustment_semantics
        == "SPLIT_PRICE_VOLUME|CASH_DIVIDEND_PRICE|SPIN_OFF_PRICE"
    )
    assert benchmark.price_basis == "ALPACA_ALL_ADJUSTED_1MINUTE_PRICE_V1"
    assert benchmark.benchmark_id == evaluator._passive_benchmark_year_id(benchmark)

    annual = tuple(
        evaluator._synthetic_passive_benchmark_for_test(
            "a" * 64,
            year,
            start_price=Decimal(100 + index * 5),
            end_price=Decimal(105 + index * 10),
        )
        for index, year in enumerate(arch151.SCORED_YEARS)
    )
    campaign = evaluator._passive_benchmark_campaign(annual)
    assert campaign.status is evaluator.BenchmarkStatus.AVAILABLE
    assert campaign.start_price == Decimal(100)
    assert campaign.end_price == Decimal(145)
    assert campaign.adjusted_price_return == Decimal("0.45")


@pytest.mark.parametrize(
    ("missing_start", "missing_end", "expected_reason"),
    [
        (
            True,
            False,
            evaluator.BenchmarkUnavailableReason.FIRST_SESSION_OPEN_UNOBSERVED,
        ),
        (
            False,
            True,
            evaluator.BenchmarkUnavailableReason.LAST_SESSION_CLOSE_UNOBSERVED,
        ),
    ],
)
def test_passive_spy_benchmark_missing_endpoints_are_unavailable_not_zero(
    missing_start: bool,
    missing_end: bool,
    expected_reason: evaluator.BenchmarkUnavailableReason,
) -> None:
    history = _synthetic_benchmark_history(
        missing_start=missing_start, missing_end=missing_end
    )

    benchmark = evaluator._passive_benchmark_year(history, 2019)

    assert benchmark.status is evaluator.BenchmarkStatus.UNAVAILABLE
    assert benchmark.unavailable_reason is expected_reason
    assert benchmark.adjusted_price_return is None


@pytest.fixture(scope="module")
def family_a_replays() -> MappingProxyType[
    tuple[arch151.ProgramKey, str], evaluator.SessionReplayRecord
]:
    results = {}
    for symbol in arch151.INITIAL_UNIVERSE:
        history, _ = _a_history(symbol)
        calibration_cache = evaluator._FamilyACalibrationCache(history)
        for program in _programs_for_family(arch151.StrategyFamily.NOISE_VWAP_BREAKOUT):
            replays = evaluator._simulate_slot_year_cases(
                history,
                _slot_for(program, symbol),
                SESSION.year,
                calibration_cache=calibration_cache,
            )
            base = next(
                item for item in replays if item.cost_case is arch151.FillCostCase.BASE
            )
            results[program.key, symbol] = next(
                item for item in base.sessions if item.session_date == SESSION
            )
    return MappingProxyType(results)


@pytest.mark.parametrize(
    "program", arch151.CANONICAL_PROGRAMS, ids=lambda item: item.key.value
)
@pytest.mark.parametrize("symbol", arch151.INITIAL_UNIVERSE)
def test_all_canonical_signals_enter_and_exit_through_unmocked_predicates(
    program: arch151.Arch151Program, symbol: str, request: pytest.FixtureRequest
) -> None:
    history, session, expected_entry, expected_exit = _source_for_program(
        program, symbol
    )
    if program.family is arch151.StrategyFamily.NOISE_VWAP_BREAKOUT:
        record = request.getfixturevalue("family_a_replays")[program.key, symbol]
    else:
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
    evaluator._validate_session_trade_cash(record)


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


def _complete_idle_year_batch(
    year: int, *, missing_benchmark_open: bool
) -> evaluator.CanonicalYearBatch:
    source_digest = "a" * 64
    cost_index = {
        case: index for index, case in enumerate(arch151.EVALUATION_ECONOMICS_ORDER)
    }
    sessions = _idle_session_records_for_year(year)
    evaluations = tuple(
        evaluator.SlotYearReplay(
            UUID(int=year * 1_000_000 + slot.ordinal * 10 + cost_index[cost] + 1),
            slot,
            year,
            cost,
            source_digest,
            sessions,
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
    benchmark = evaluator._synthetic_passive_benchmark_for_test(
        source_digest,
        year,
        start_price=None if missing_benchmark_open else Decimal("100"),
        end_price=Decimal("110"),
        unavailable_reason=(
            evaluator.BenchmarkUnavailableReason.FIRST_SESSION_OPEN_UNOBSERVED
            if missing_benchmark_open
            else None
        ),
    )
    return evaluator.CanonicalYearBatch(
        evaluator._canonical_year_batch_id(
            source_binding, year, evaluations, benchmark
        ),
        year,
        arch151.CANONICAL_MANIFEST.manifest_id,
        arch151.CANONICAL_MANIFEST.fingerprint,
        source_digest,
        evaluations,
        benchmark,
        source_binding,
        evaluator._CANONICAL_YEAR_BATCH_SEAL,
    )


@pytest.fixture(scope="module")
def idle_year_batches() -> tuple[evaluator.CanonicalYearBatch, ...]:
    return tuple(
        _complete_idle_year_batch(
            year, missing_benchmark_open=year == arch151.SCORED_YEARS[1]
        )
        for year in arch151.SCORED_YEARS
    )


@pytest.fixture(scope="module")
def idle_run(
    idle_year_batches: tuple[evaluator.CanonicalYearBatch, ...],
) -> evaluator.DevelopmentEvaluationRun:
    return evaluator.compose_development_evaluation(idle_year_batches)


@pytest.fixture(scope="module")
def idle_report(
    idle_run: evaluator.DevelopmentEvaluationRun,
) -> evaluator.DevelopmentEvaluationReport:
    return evaluator.serialize_development_evaluation(idle_run)


def _one_trade_full_year_replay(
    case: arch151.FillCostCase,
    *,
    exit_mode: str = "target_open",
) -> evaluator.SlotYearReplay:
    program, history, *_ = _b_history(exit_mode=exit_mode)
    slot = _slot_for(program)
    first_session = evaluator._simulate_session(history, slot, SESSION, case)
    assert first_session.closing_equity is not None
    equity = first_session.closing_equity
    sessions: list[evaluator.SessionReplayRecord] = []
    for idle in _idle_session_records_for_year(2023):
        if idle.session_date == SESSION:
            sessions.append(first_session)
        else:
            sessions.append(
                replace(
                    idle,
                    starting_equity=equity,
                    closing_equity=equity,
                    session_return=Decimal(0),
                )
            )
    return evaluator._finish_slot_year(
        history_digest=evaluator._history_digest(history),
        slot=slot,
        year=2023,
        case=case,
        sessions=tuple(sessions),
    )


def test_economic_diagnostics_reconcile_costs_months_time_and_excursions() -> None:
    replays = {
        case: _one_trade_full_year_replay(case)
        for case in arch151.EVALUATION_ECONOMICS_ORDER
    }
    zero = replays[arch151.FillCostCase.ZERO]
    base = replays[arch151.FillCostCase.BASE]
    stress = replays[arch151.FillCostCase.STRESS]
    zero_diag = evaluator._economic_diagnostic(
        (zero,), evaluator.DiagnosticScope.SCORED_YEAR
    )
    base_diag = evaluator._economic_diagnostic(
        (base,), evaluator.DiagnosticScope.SCORED_YEAR
    )
    stress_diag = evaluator._economic_diagnostic(
        (stress,), evaluator.DiagnosticScope.SCORED_YEAR
    )
    base_drag = evaluator._cost_drag_diagnostic(
        base,
        zero,
        evaluator.DiagnosticScope.SCORED_YEAR,
        (base,),
        (zero,),
    )

    trade = base.trades[0]
    assert base_diag.complete
    assert base_diag.trade_count == 1
    assert base_diag.gross_trade_pnl == trade.gross_pnl
    assert base_diag.net_trade_pnl == trade.net_pnl
    assert base_diag.total_adverse_cost == trade.total_adverse_cost > 0
    assert base_diag.gross_trade_expectancy == trade.gross_pnl
    assert base_diag.net_trade_expectancy == trade.net_pnl
    assert base_diag.net_win_rate == Decimal(1)
    assert base_diag.average_net_win == trade.net_pnl
    assert base_diag.average_net_loss is None
    assert base_diag.net_payoff_ratio is None
    assert base_diag.monthly_returns[0].month == 1
    assert base_diag.monthly_returns[0].net_return == base.sessions[0].session_return
    assert base_diag.positive_month_count == 1
    assert base_diag.available_month_count == 12
    assert base_diag.holding_minutes.mean == Decimal(1)
    assert base_diag.time_in_market_minutes == Decimal(1)
    with localcontext(arch151._DECIMAL_CONTEXT):
        expected_time_fraction = Decimal(1) / Decimal(
            base_diag.published_session_minutes
        )
    assert base_diag.time_in_market_fraction == expected_time_fraction
    target_open = next(
        item
        for item in base_diag.exits_by_reason
        if item.reason is evaluator.ExitReason.TARGET_OPEN
    )
    assert target_open.trade_count == 1
    assert target_open.net_pnl == trade.net_pnl
    assert base_diag.generated_signals == 1
    assert base_diag.executed_signals == 1
    assert base_diag.expired_signals == base_diag.blocked_signals == 0
    assert base_diag.mfe_returns.count == base_diag.mae_returns.count == 1
    assert base_diag.trades[0].excursion_minute_count == 1
    assert zero_diag.total_adverse_cost == 0
    assert stress_diag.total_adverse_cost > base_diag.total_adverse_cost
    assert (
        base_drag.path_relationship
        is evaluator.CostPathRelationship.IDENTICAL_ENTRY_EXIT_PATH
    )
    with localcontext(arch151._DECIMAL_CONTEXT):
        expected_return_delta = (
            base_diag.compounded_net_return - zero_diag.compounded_net_return
        )
    assert base_drag.net_return_delta == expected_return_delta
    assert base_drag.net_return_delta < 0
    with localcontext(arch151._DECIMAL_CONTEXT):
        expected_cost_delta = base.total_adverse_cost - zero.total_adverse_cost
    assert base_drag.adverse_cost_delta == expected_cost_delta


def test_economic_diagnostic_negates_fractional_losses_exactly() -> None:
    replay = _one_trade_full_year_replay(
        arch151.FillCostCase.STRESS, exit_mode="stop_gap"
    )
    trade = replay.trades[0]
    assert trade.net_pnl < 0
    with localcontext() as ambient:
        ambient.prec = 8
        diagnostic = evaluator._economic_diagnostic(
            (replay,), evaluator.DiagnosticScope.SCORED_YEAR
        )
        rounded_negation = -trade.net_pnl
    assert diagnostic.average_net_loss == trade.net_pnl.copy_negate()
    assert rounded_negation != diagnostic.average_net_loss


def test_annual_replay_failure_has_slot_and_operation_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program, history, *_ = _b_history()
    slot = _slot_for(program)

    def fail_tape(*_args, **_kwargs):
        raise ValueError("private tape detail")

    monkeypatch.setattr(evaluator, "_session_tape", fail_tape)
    with pytest.raises(evaluator.AnnualReplayFailure) as error:
        evaluator._simulate_slot_year_cases(history, slot, 2023)

    context = error.value.context
    assert context.scored_year == 2023
    assert context.program_id == slot.program_id
    assert context.slot_id == slot.slot_id
    assert context.symbol == slot.symbol
    assert context.cost_case is None
    assert context.session_date == arch151._published_sessions_for_year(2023)[0]
    assert (
        context.operation_stage
        is evaluator.AnnualReplayOperationStage.SESSION_TAPE_PREPARATION
    )
    assert isinstance(error.value.__cause__, ValueError)


def test_diagnostic_quartiles_use_nearest_rank_without_interpolation() -> None:
    odd = evaluator._distribution_summary(
        tuple(Decimal(item) for item in (1, 2, 3, 4, 5))
    )
    even = evaluator._distribution_summary(
        tuple(Decimal(item) for item in (1, 2, 3, 4, 5, 6))
    )

    assert odd.first_quartile == Decimal(2)
    assert odd.median == Decimal(3)
    assert odd.third_quartile == Decimal(4)
    assert even.first_quartile == Decimal(2)
    assert even.median == Decimal("3.5")
    assert even.third_quartile == Decimal(5)


def test_economic_diagnostics_retain_expired_and_blocked_signal_counts() -> None:
    program, expired_history, *_ = _b_history(entry_observed=False)
    slot = _slot_for(program)
    expired_session = evaluator._simulate_session(
        expired_history, slot, SESSION, arch151.FillCostCase.ZERO
    )
    _program, blocked_history, *_ = _b_history(
        exit_mode="target_open",
        second_setup=True,
        second_open_observed=True,
    )
    blocked_session = evaluator._simulate_session(
        blocked_history, slot, SESSION, arch151.FillCostCase.ZERO
    )

    def partial_replay(
        record: evaluator.SessionReplayRecord,
        source_digest: str,
        replay_id: int,
    ) -> evaluator.SlotYearReplay:
        return evaluator.SlotYearReplay(
            replay_id=UUID(int=replay_id),
            slot=slot,
            scored_year=2023,
            cost_case=arch151.FillCostCase.ZERO,
            source_digest=source_digest,
            sessions=(record,),
            trades=record.trades,
            complete=False,
            initial_equity=Decimal(1),
            final_equity=None,
            net_return=None,
            positive_net_pnl=None,
            negative_net_pnl=None,
            gross_trade_pnl=None,
            total_adverse_cost=None,
            fill_notional=None,
            turnover=None,
            maximum_drawdown=None,
            failure=record.failure,
        )

    expired = evaluator._economic_diagnostic(
        (
            partial_replay(
                expired_session,
                evaluator._history_digest(expired_history),
                9001,
            ),
        ),
        evaluator.DiagnosticScope.SCORED_YEAR,
    )
    blocked = evaluator._economic_diagnostic(
        (
            partial_replay(
                blocked_session,
                evaluator._history_digest(blocked_history),
                9002,
            ),
        ),
        evaluator.DiagnosticScope.SCORED_YEAR,
    )

    assert not expired.complete and expired.generated_signals == 1
    assert expired.expired_signals == 1
    assert expired.executed_signals == expired.blocked_signals == 0
    assert not blocked.complete and blocked.generated_signals == 2
    assert blocked.executed_signals == 1
    assert blocked.expired_signals == 0
    assert blocked.blocked_signals == 1
    assert (
        next(
            item
            for item in blocked.rejections_by_reason
            if item.reason is evaluator.RejectionReason.SESSION_ENTRY_LIMIT
        ).count
        == 1
    )


def test_unavailable_annual_benchmark_is_retained_without_zero_fill_or_dropout(
    idle_run: evaluator.DevelopmentEvaluationRun,
    idle_report: evaluator.DevelopmentEvaluationReport,
) -> None:
    run = idle_run
    payload = json.loads(idle_report.canonical_json_bytes)
    benchmark = payload["research_diagnostics"]["passive_spy_benchmark"]

    assert len(benchmark["annual"]) == len(arch151.SCORED_YEARS) == 5
    assert benchmark["annual"][1]["status"] == evaluator.BenchmarkStatus.UNAVAILABLE
    assert benchmark["annual"][1]["adjusted_price_return"] is None
    assert benchmark["annual"][1]["unavailable_reason"] == (
        evaluator.BenchmarkUnavailableReason.FIRST_SESSION_OPEN_UNOBSERVED
    )
    assert benchmark["five_year"]["status"] == evaluator.BenchmarkStatus.AVAILABLE
    assert run.fold_evaluation_count == 480
    assert len(run.qualifications) == len(arch151.CANONICAL_SLOTS) == 32


def test_development_composition_preserves_all_480_fold_slot_cost_records(
    idle_run: evaluator.DevelopmentEvaluationRun,
) -> None:
    run = idle_run
    year_batches = run.year_batches

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
    changed_benchmark = evaluator._synthetic_passive_benchmark_for_test(
        "b" * 64, year_batches[-1].scored_year
    )
    changed_last = replace(
        year_batches[-1],
        batch_id=evaluator._canonical_year_batch_id(
            changed_binding,
            year_batches[-1].scored_year,
            year_batches[-1].evaluations,
            changed_benchmark,
        ),
        source_digest="b" * 64,
        passive_spy_benchmark=changed_benchmark,
        source_binding=changed_binding,
    )
    with pytest.raises(evaluator.EvaluationIntegrityError, match="share exact source"):
        evaluator.compose_development_evaluation((*year_batches[:-1], changed_last))


def test_source_owned_report_binds_all_records_provenance_dsr_and_freeze(
    idle_run: evaluator.DevelopmentEvaluationRun,
    idle_report: evaluator.DevelopmentEvaluationReport,
) -> None:
    run = idle_run

    report = idle_report
    payload = json.loads(report.canonical_json_bytes)

    assert report.run_id == run.run_id
    assert report.source_binding_id == run.source_binding.binding_id
    assert report.manifest_id == arch151.CANONICAL_MANIFEST.manifest_id
    assert report.manifest_fingerprint == arch151.CANONICAL_MANIFEST.fingerprint
    assert report.record_count == 480
    assert report.sha256 == sha256(report.canonical_json_bytes).hexdigest()
    assert payload["schema"] == "arch151-development-evaluation-report/v3"
    run_material = {
        "schema": evaluator._DEVELOPMENT_RUN_SCHEMA,
        "source_binding_id": str(run.source_binding.binding_id),
        "source_digest": run.source_digest,
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "year_batch_ids": [str(item.batch_id) for item in run.year_batches],
        "slot_batch_digests": [item.batch_digest for item in run.slot_batches],
        "selection_bias_calculation_id": str(run.selection_bias.calculation_id),
        "qualification_ids": [
            str(item.qualification_id) for item in run.qualifications
        ],
        "passive_spy_benchmark_id": str(run.passive_spy_benchmark.benchmark_id),
        "ranking_order": [str(item) for item in run.ranking_order],
        "freeze_id": str(run.final_freeze.freeze_id),
    }
    expected_run_namespace = uuid5(
        evaluator._NAMESPACE, "development-evaluation-run/v4"
    )
    expected_run_id = evaluator._canonical_id(
        expected_run_namespace,
        "arch151-development-evaluation-run/v4",
        run_material,
    )
    predecessor_run_v3_namespace = uuid5(
        evaluator._NAMESPACE, "development-evaluation-run/v3"
    )
    predecessor_v3_material = {
        key: value
        for key, value in run_material.items()
        if key != "passive_spy_benchmark_id"
    }
    predecessor_v3_material["schema"] = "arch151-development-evaluation-run/v3"
    predecessor_run_v3_id = evaluator._canonical_id(
        predecessor_run_v3_namespace,
        "arch151-development-evaluation-run/v3",
        predecessor_v3_material,
    )
    predecessor_run_v2_namespace = uuid5(
        evaluator._NAMESPACE, "development-evaluation-run/v2"
    )
    predecessor_v2_material = dict(predecessor_v3_material)
    predecessor_v2_material["schema"] = "arch151-development-evaluation-run/v2"
    predecessor_run_v2_id = evaluator._canonical_id(
        predecessor_run_v2_namespace,
        "arch151-development-evaluation-run/v2",
        predecessor_v2_material,
    )
    expected_report_id = evaluator._canonical_id(
        evaluator._DEVELOPMENT_REPORT_NAMESPACE,
        "arch151-development-evaluation-report/v3",
        {"run_id": str(run.run_id), "sha256": report.sha256},
    )
    predecessor_report_v2_namespace = uuid5(
        predecessor_run_v3_namespace, "canonical-report/v2"
    )
    predecessor_report_v2_id = evaluator._canonical_id(
        predecessor_report_v2_namespace,
        "arch151-development-evaluation-report/v2",
        {"run_id": str(run.run_id), "sha256": report.sha256},
    )
    predecessor_report_v1_namespace = uuid5(
        predecessor_run_v2_namespace, "canonical-report/v1"
    )
    predecessor_report_v1_id = evaluator._canonical_id(
        predecessor_report_v1_namespace,
        "arch151-development-evaluation-report/v1",
        {"run_id": str(run.run_id), "sha256": report.sha256},
    )
    assert evaluator._DEVELOPMENT_RUN_SCHEMA == "arch151-development-evaluation-run/v4"
    assert evaluator._DEVELOPMENT_RUN_NAMESPACE == expected_run_namespace
    assert run.run_id == expected_run_id
    assert run.run_id != predecessor_run_v3_id
    assert run.run_id != predecessor_run_v2_id
    assert (
        evaluator._DEVELOPMENT_REPORT_SCHEMA
        == "arch151-development-evaluation-report/v3"
    )
    assert evaluator._DEVELOPMENT_REPORT_NAMESPACE == uuid5(
        expected_run_namespace, "canonical-report/v3"
    )
    assert report.report_id == expected_report_id
    assert report.report_id != predecessor_report_v2_id
    assert report.report_id != predecessor_report_v1_id
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
    diagnostics = payload["research_diagnostics"]
    assert diagnostics["qualification_or_ranking_input"] is False
    assert len(diagnostics["annual_slot_economics"]) == 480
    assert len(diagnostics["five_year_slot_economics"]) == 96
    assert len(diagnostics["cost_drag_vs_zero"]) == 384
    assert {
        (item["slot_id"], item["scored_year"], item["cost_case"])
        for item in diagnostics["annual_slot_economics"]
    } == {
        (str(slot.slot_id), year, case.value)
        for slot in arch151.CANONICAL_SLOTS
        for year in arch151.SCORED_YEARS
        for case in arch151.EVALUATION_ECONOMICS_ORDER
    }
    assert {
        (item["slot_id"], item["cost_case"])
        for item in diagnostics["five_year_slot_economics"]
    } == {
        (str(slot.slot_id), case.value)
        for slot in arch151.CANONICAL_SLOTS
        for case in arch151.EVALUATION_ECONOMICS_ORDER
    }
    assert all(
        item["trade_count"] == 0 for item in diagnostics["annual_slot_economics"]
    )
    assert all(
        item["net_trade_expectancy"] is None
        and item["net_win_rate"] is None
        and item["net_payoff_ratio"] is None
        for item in diagnostics["annual_slot_economics"]
    )
    assert all(
        item["path_relationship"]
        == evaluator.CostPathRelationship.IDENTICAL_ENTRY_EXIT_PATH
        and item["net_return_delta"] == "0"
        and item["adverse_cost_delta"] == "0"
        for item in diagnostics["cost_drag_vs_zero"]
    )
    assert len(diagnostics["passive_spy_benchmark"]["annual"]) == 5
    assert diagnostics["passive_spy_benchmark"]["metric"] == "ADJUSTED_PRICE_RETURN"
    assert (
        diagnostics["passive_spy_benchmark"]["price_basis"]
        == "ALPACA_ALL_ADJUSTED_1MINUTE_PRICE_V1"
    )
    assert (
        diagnostics["passive_spy_benchmark"][
            "dividend_cashflow_total_return_reconstructed"
        ]
        is False
    )
    assert (
        diagnostics["passive_spy_benchmark"]["five_year"]["adjusted_price_return"]
        == "0.1"
    )
    assert len(payload["slot_batches"]) == len(arch151.CANONICAL_SLOTS)
    assert len(payload["qualifications"]) == len(arch151.CANONICAL_SLOTS)
    assert payload["selection_bias"]["calculation_id"] == str(
        run.selection_bias.calculation_id
    )
    assert payload["selection_bias"]["evidence"] == []
    assert len(payload["selection_bias"]["trial_diagnostics"]) == 32
    assert payload["selection_bias"]["affected_trial_slot_ids"] == [
        str(slot.slot_id) for slot in arch151.CANONICAL_SLOTS
    ]
    assert payload["selection_bias"]["descriptive_economic_order"] == [
        str(item) for item in run.selection_bias.descriptive_economic_order
    ]
    assert len(payload["selection_bias"]["descriptive_economic_order"]) == 32
    assert payload["final_freeze"]["freeze_id"] == str(run.final_freeze.freeze_id)
    assert payload["final_freeze"]["candidate_slot_id"] is None
    assert "pre_cost_profit_factor" in payload["fold_records"][0]["metrics"]
    assert "net_positive_trade_pnl" in payload["fold_records"][0]["metrics"]
    assert "pre_cost_profit_factor" in payload["qualifications"][0]["aggregate"]
    assert all(
        replay["signal_counts"]
        == {"generated": 0, "eligible": 0, "executed": 0, "expired": 0, "blocked": 0}
        for replay in payload["slot_year_replays"]
    )


def test_unissued_development_batch_run_and_report_constructors_fail_closed(
    idle_run: evaluator.DevelopmentEvaluationRun,
) -> None:
    with pytest.raises(arch151.AuthorizationUnavailableError, match="source adapter"):
        evaluator.DevelopmentSourceBinding(
            kind=evaluator.DevelopmentSourceKind.SYNTHETIC_TEST_ONLY,
            source_digest="a" * 64,
        )

    batch = idle_run.year_batches[0]
    with pytest.raises(arch151.AuthorizationUnavailableError, match="evaluator"):
        evaluator.CanonicalYearBatch(
            batch.batch_id,
            batch.scored_year,
            batch.manifest_id,
            batch.manifest_fingerprint,
            batch.source_digest,
            batch.evaluations,
            batch.passive_spy_benchmark,
            batch.source_binding,
            None,
        )

    run = idle_run
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


def test_synthetic_development_report_cannot_issue_authenticated_evidence(
    monkeypatch: pytest.MonkeyPatch,
    idle_run: evaluator.DevelopmentEvaluationRun,
    idle_report: evaluator.DevelopmentEvaluationReport,
) -> None:
    source_revision_calls = []

    def reject_source_revision():
        source_revision_calls.append(True)
        raise AssertionError("synthetic authentication must not inspect Git source")

    monkeypatch.setattr(operator, "_read_source_revision", reject_source_revision)
    with pytest.raises(
        arch151.AuthorizationUnavailableError,
        match="synthetic development runs cannot issue",
    ):
        evaluator.authenticate_development_evidence(idle_run, idle_report, object())
    assert source_revision_calls == []


def test_operator_attestation_binds_exact_run_report_and_captured_revision(
    monkeypatch: pytest.MonkeyPatch,
    idle_run: evaluator.DevelopmentEvaluationRun,
    idle_report: evaluator.DevelopmentEvaluationReport,
) -> None:
    run = idle_run
    report = idle_report
    revision = operator.SourceRevision(
        operator.EXPECTED_BRANCH,
        operator.EXPECTED_ORIGIN,
        "b" * 40,
        "c" * 40,
        _seal=operator._SOURCE_REVISION_SEAL,
    )
    invocation_id = operator._invocation_id(revision)
    context = operator._ActiveDevelopmentInvocation(
        _seal=operator._ACTIVE_INVOCATION_SEAL,
        attempt_id=UUID(int=9101),
        invocation_id=invocation_id,
        source_revision=revision,
    )
    context.bind_run(run)
    context.bind_report(report)
    attestation = operator._issue_development_source_attestation(
        context,
        run,
        report,
        _synthetic_test_only=True,
    )

    assert attestation.run_id == run.run_id
    assert attestation.report_id == report.report_id
    assert attestation.report_sha256 == report.sha256
    assert attestation.record_count == 480
    assert attestation.invocation_id == invocation_id
    assert attestation.source_revision == revision
    assert len(attestation.year_batch_ids) == 5
    assert len(attestation.slot_batch_digests) == 32
    assert (
        operator._validate_development_source_attestation(
            run, report, attestation, expected_revision=revision
        )
        == attestation
    )

    changed_revision = operator.SourceRevision(
        operator.EXPECTED_BRANCH,
        operator.EXPECTED_ORIGIN,
        "d" * 40,
        "e" * 40,
        _seal=operator._SOURCE_REVISION_SEAL,
    )
    with pytest.raises(operator.OperatorError):
        operator._ActiveDevelopmentInvocation(
            _seal=operator._ACTIVE_INVOCATION_SEAL,
            attempt_id=UUID(int=9101),
            invocation_id=operator._invocation_id(changed_revision),
            source_revision=revision,
        )
    with pytest.raises(
        arch151.AuthorizationUnavailableError, match="does not bind this run"
    ):
        operator._validate_development_source_attestation(
            run, report, attestation, expected_revision=changed_revision
        )

    altered_bytes = report.canonical_json_bytes + b" "
    altered_digest = sha256(altered_bytes).hexdigest()
    forged_report = evaluator.DevelopmentEvaluationReport(
        _seal=evaluator._DEVELOPMENT_REPORT_SEAL,
        report_id=evaluator._canonical_id(
            evaluator._DEVELOPMENT_REPORT_NAMESPACE,
            evaluator._DEVELOPMENT_REPORT_SCHEMA,
            {"run_id": str(run.run_id), "sha256": altered_digest},
        ),
        run_id=run.run_id,
        source_binding_id=report.source_binding_id,
        manifest_id=report.manifest_id,
        manifest_fingerprint=report.manifest_fingerprint,
        record_count=report.record_count,
        canonical_json_bytes=altered_bytes,
        sha256_digest=altered_digest,
    )
    with pytest.raises(
        arch151.AuthorizationUnavailableError, match="does not bind this run"
    ):
        operator._validate_development_source_attestation(
            run, forged_report, attestation
        )

    outcome = operator.OperatorOutcome(
        operator.OperatorStatus.COMPLETED,
        UUID(int=9102),
        invocation_id,
        None,
        report.report_id,
        report.sha256,
        None,
    )
    for untrusted in (UUID(int=9103), outcome, revision):
        with pytest.raises(arch151.AuthorizationUnavailableError):
            operator._validate_development_source_attestation(run, report, untrusted)

    source_revision_calls: list[None] = []

    def reject_synthetic_authentication():
        source_revision_calls.append(None)
        pytest.fail("synthetic receipts must fail before current-source inspection")

    monkeypatch.setattr(
        operator, "_read_source_revision", reject_synthetic_authentication
    )
    with pytest.raises(
        arch151.AuthorizationUnavailableError,
        match="synthetic development runs cannot issue",
    ):
        evaluator.authenticate_development_evidence(run, report, attestation)
    assert source_revision_calls == []


def test_year_batch_identity_binds_complete_replay_outputs(
    idle_year_batches: tuple[evaluator.CanonicalYearBatch, ...],
) -> None:
    year_batches = idle_year_batches
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
