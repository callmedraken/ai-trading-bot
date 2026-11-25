"""Synthetic contracts for the Architecture 151 source foundation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext
from functools import cache
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import pytest

from trading_bot.experiments import arch150_g1_discovery as arch150_d1r
from trading_bot.experiments import arch150_intraday_ai as arch150
from trading_bot.experiments import arch151_intraday_walkforward as arch151
from trading_bot.experiments.arch148_intraday import HistoricalIntradaySessionAuthority
from trading_bot.experiments.arch151_intraday_walkforward import (
    CANONICAL_MANIFEST,
    CANONICAL_PROGRAMS,
    CANONICAL_SLOTS,
    CAUSAL_EXECUTION_POLICY,
    FILL_COST_POLICIES,
    AggregateBar,
    AmbiguousIntraminuteRule,
    Arch151Error,
    Arch151Program,
    BarResolution,
    CausalExecutionPolicy,
    FamilyAMeasureScope,
    FillCostApplicationRule,
    FillCostCase,
    FinalObservedBarRule,
    MissingObservationRule,
    OneMinuteBar,
    ProgramKey,
    QualificationRejection,
    StopGapRule,
    StrategyFamily,
    TargetReferenceRule,
    TrailingActivationRule,
    TrailingMonotonicityRule,
    UnavailableIndicatorError,
    UnsupportedProgramError,
    VwapObservation,
    aggregate_session_vwap,
    aggregate_sparse_bars,
    average_true_range,
    calibrate_family_a,
    canonical_manifest,
    contiguous_aggregate_bars,
    efficiency_ratio,
    ema_series,
    exact_cross_etf_confirmation,
    family_a_breakout_level,
    family_a_entry_signal,
    family_a_historical_session_measure,
    family_a_initial_risk,
    family_a_session_measure,
    family_b_entry_signal,
    family_c_entry_signal,
    family_c_reversion_exit,
    family_d_entry_signal,
    normalized_vwap_deviation,
    program_fingerprint,
    program_from_bytes,
    program_id,
    program_to_bytes,
    sample_standard_deviation,
    structural_entry_opportunities,
    vwap_sigma_stop_distance,
)

_NY = ZoneInfo("America/New_York")
_AUTHORITY = HistoricalIntradaySessionAuthority()
_NORMAL_DAY = date(2023, 1, 3)


def _minute(
    symbol: str,
    session: date,
    offset: int,
    *,
    open_price: str = "100",
    high: str | None = None,
    low: str | None = None,
    close: str = "100",
    volume: int = 100,
) -> OneMinuteBar:
    schedule = _AUTHORITY.schedule_for(session)
    assert schedule is not None
    timestamp = schedule.opens_at + timedelta(minutes=offset)
    close_decimal = Decimal(close)
    open_decimal = Decimal(open_price)
    return OneMinuteBar(
        symbol,
        timestamp,
        open_decimal,
        Decimal(high) if high is not None else max(open_decimal, close_decimal),
        Decimal(low) if low is not None else min(open_decimal, close_decimal),
        close_decimal,
        volume,
    )


def _minutes_for_aggregates(
    aggregates: tuple[AggregateBar, ...], resolution: BarResolution
) -> tuple[OneMinuteBar, ...]:
    result: list[OneMinuteBar] = []
    for aggregate in aggregates:
        for offset in range(int(resolution)):
            result.append(
                OneMinuteBar(
                    aggregate.symbol,
                    aggregate.timestamp + timedelta(minutes=offset),
                    aggregate.open,
                    aggregate.high,
                    aggregate.low,
                    aggregate.close,
                    aggregate.volume // int(resolution),
                )
            )
    return tuple(result)


def _verified_test_session(aggregates):
    materialized = tuple(aggregates)
    minutes = _minutes_for_aggregates(materialized, materialized[0].resolution)
    return arch151._test_only_verified_sparse_session(materialized, minute_bars=minutes)


def _bar_at(
    session: date,
    resolution: BarResolution,
    index: int,
    close: Decimal,
    *,
    open_price: Decimal | None = None,
    high: Decimal | None = None,
    low: Decimal | None = None,
    symbol: str = "SPY",
) -> AggregateBar:
    schedule = _AUTHORITY.schedule_for(session)
    assert schedule is not None
    timestamp = schedule.opens_at + timedelta(minutes=index * int(resolution))
    opening = open_price if open_price is not None else close
    return AggregateBar(
        symbol,
        timestamp,
        opening,
        high if high is not None else max(opening, close),
        low if low is not None else min(opening, close),
        close,
        100 * int(resolution),
        resolution,
    )


def _flat_aggregate_session(
    session: date, resolution: BarResolution, close: Decimal = Decimal("100")
) -> list[AggregateBar]:
    schedule = _AUTHORITY.schedule_for(session)
    assert schedule is not None
    minutes = int((schedule.closes_at - schedule.opens_at).total_seconds() // 60)
    return [
        _bar_at(session, resolution, index, close)
        for index in range(minutes // int(resolution))
    ]


@cache
def _full_session_minutes(
    session: date,
    symbol: str = "SPY",
    *,
    first_30m_close: str = "100.1",
) -> tuple[OneMinuteBar, ...]:
    schedule = _AUTHORITY.schedule_for(session)
    assert schedule is not None
    session_minutes = int(
        (schedule.closes_at - schedule.opens_at).total_seconds() // 60
    )
    return tuple(
        _minute(
            symbol,
            session,
            offset,
            close=first_30m_close if offset == 29 else "100",
        )
        for offset in range(session_minutes)
    )


@cache
def _a_history_measures(scored_year: int = 2023, symbol: str = "SPY"):
    sessions = tuple(
        session
        for session in _AUTHORITY.published.sessions
        if date(2016, 1, 1) <= session < date(scored_year, 1, 1)
    )[-60:]
    records = []
    for session in sessions:
        records.append(
            family_a_historical_session_measure(_full_session_minutes(session, symbol))
        )
    return tuple(records)


def _synthetic_source_history(
    sessions: tuple[date, ...] = (_NORMAL_DAY,),
    *,
    symbols: tuple[str, ...] = ("SPY", "QQQ"),
    missing_offsets: tuple[tuple[str, date, int], ...] = (),
):
    missing = set(missing_offsets)
    bars = tuple(
        minute
        for symbol in symbols
        for session in sessions
        for minute in _full_session_minutes(session, symbol)
        if (
            symbol,
            session,
            int(
                (
                    minute.timestamp - _AUTHORITY.schedule_for(session).opens_at
                ).total_seconds()
                // 60
            ),
        )
        not in missing
    )
    return arch151._test_only_synthetic_source_history(bars)


def _feature_cutoff(session: date = _NORMAL_DAY) -> datetime:
    return datetime.combine(session, time(14, 0), _NY).astimezone(UTC)


def _a_reachable_inputs(program, symbol: str = "SPY"):
    schedule = _AUTHORITY.schedule_for(_NORMAL_DAY)
    assert schedule is not None
    start = program.entry_window.start
    start_local = datetime.combine(_NORMAL_DAY, start, _NY)
    delta = int((start_local - schedule.opens_at).total_seconds() // 60)
    first_index = delta // int(program.resolution)
    count = program.parameters.confirmation_bars
    values = _flat_aggregate_session(_NORMAL_DAY, program.resolution)
    for index in range(first_index, first_index + count):
        values[index] = _bar_at(
            _NORMAL_DAY,
            program.resolution,
            index,
            Decimal("101"),
            open_price=Decimal("100.9"),
            high=Decimal("101.1"),
            low=Decimal("100.8"),
            symbol=symbol,
        )
    confirmation = tuple(
        VwapObservation(
            values[index], Decimal("100.4") + Decimal(index) / Decimal(1000)
        )
        for index in range(first_index, first_index + count)
    )
    first_30 = tuple(_minute(symbol, _NORMAL_DAY, offset) for offset in range(30))
    measure = family_a_session_measure(first_30)
    calibration = calibrate_family_a(program, _a_history_measures(symbol=symbol), 2023)
    return calibration, measure, confirmation


def _b_reachable_session(program):
    parameters = program.parameters
    resolution = program.resolution
    bars = _flat_aggregate_session(_NORMAL_DAY, resolution)
    schedule = _AUTHORITY.schedule_for(_NORMAL_DAY)
    assert schedule is not None
    entry_start = datetime.combine(_NORMAL_DAY, program.entry_window.start, _NY)
    first_window_index = int(
        (entry_start - schedule.opens_at).total_seconds() // 60
    ) // int(resolution)
    opening_count = parameters.opening_range_minutes // int(resolution)
    min_final_index = (
        opening_count
        + parameters.breakout_confirmation_bars
        + 1
        + parameters.reclaim_confirmation_bars
        - 1
    )
    final_reclaim_index = max(first_window_index, min_final_index)
    first_breakout_index = (
        final_reclaim_index
        - parameters.reclaim_confirmation_bars
        - parameters.breakout_confirmation_bars
    )
    breakout_level = Decimal("100") * (
        Decimal(1) + parameters.breakout_buffer_bps / Decimal(10000)
    )
    for index in range(
        first_breakout_index,
        first_breakout_index + parameters.breakout_confirmation_bars,
    ):
        close = breakout_level + Decimal("0.10")
        bars[index] = _bar_at(
            _NORMAL_DAY,
            resolution,
            index,
            close,
            open_price=breakout_level + Decimal("0.02"),
            high=close + Decimal("0.03"),
            low=breakout_level + Decimal("0.01"),
        )
    retest_index = first_breakout_index + parameters.breakout_confirmation_bars
    bars[retest_index] = _bar_at(
        _NORMAL_DAY,
        resolution,
        retest_index,
        breakout_level + Decimal("0.02"),
        open_price=breakout_level + Decimal("0.03"),
        high=breakout_level + Decimal("0.06"),
        low=breakout_level,
    )
    previous_high = bars[retest_index].high
    reclaim_indexes = range(
        retest_index + 1,
        retest_index + 1 + parameters.reclaim_confirmation_bars,
    )
    for index in reclaim_indexes:
        close = previous_high + Decimal("0.10")
        bars[index] = _bar_at(
            _NORMAL_DAY,
            resolution,
            index,
            close,
            open_price=previous_high + Decimal("0.02"),
            high=close + Decimal("0.02"),
            low=previous_high + Decimal("0.01"),
        )
        previous_high = bars[index].high
    return bars[: final_reclaim_index + 1]


def _b_case(program_key: ProgramKey = ProgramKey.B5_01):
    program = next(item for item in CANONICAL_PROGRAMS if item.key is program_key)
    bars = _flat_aggregate_session(_NORMAL_DAY, program.resolution)
    opening_count = program.parameters.opening_range_minutes // int(program.resolution)
    level = max(bar.high for bar in bars[:opening_count]) * (
        Decimal(1) + program.parameters.breakout_buffer_bps / Decimal(10000)
    )
    return program, bars, level


def _set_b_case_bar(
    bars: list[AggregateBar],
    program: Arch151Program,
    index: int,
    *,
    close: Decimal,
    low: Decimal,
) -> None:
    bars[index] = _bar_at(
        _NORMAL_DAY,
        program.resolution,
        index,
        close,
        low=low,
    )


def _set_b_valid_setup(
    bars: list[AggregateBar],
    program: Arch151Program,
    level: Decimal,
    breakout_index: int,
    retest_index: int,
    reclaim_index: int,
) -> None:
    _set_b_case_bar(
        bars,
        program,
        breakout_index,
        close=level + Decimal("0.10"),
        low=level + Decimal("0.03"),
    )
    _set_b_case_bar(
        bars,
        program,
        retest_index,
        close=level + Decimal("0.02"),
        low=level,
    )
    _set_b_case_bar(
        bars,
        program,
        reclaim_index,
        close=level + Decimal("0.12"),
        low=level + Decimal("0.04"),
    )


def _c_reachable_inputs(program):
    bars = _flat_aggregate_session(_NORMAL_DAY, program.resolution)
    parameters = program.parameters
    schedule = _AUTHORITY.schedule_for(_NORMAL_DAY)
    assert schedule is not None
    entry_start = datetime.combine(_NORMAL_DAY, program.entry_window.start, _NY)
    required = max(
        parameters.deviation_lookback_bars, parameters.efficiency_ratio_lookback
    )
    signal_index = max(
        int((entry_start - schedule.opens_at).total_seconds() // 60)
        // int(program.resolution),
        required,
    )
    history_indexes = range(signal_index - required, signal_index)
    closes: list[Decimal] = []
    for position, index in enumerate(history_indexes):
        close = Decimal("100") if position % 2 == 0 else Decimal("101")
        bars[index] = _bar_at(
            _NORMAL_DAY,
            program.resolution,
            index,
            close,
            open_price=close,
            high=close + Decimal("0.01"),
            low=close - Decimal("0.01"),
        )
        closes.append(close)
    signal_bar = _bar_at(
        _NORMAL_DAY,
        program.resolution,
        signal_index,
        Decimal("97"),
        open_price=Decimal("97"),
        high=Decimal("97.01"),
        low=Decimal("96.99"),
    )
    bars[signal_index] = signal_bar
    history_bars = tuple(bars[index] for index in history_indexes)
    history = tuple(
        VwapObservation(
            bar,
            bar.close
            / (Decimal(1) + (Decimal("0.01") if offset % 2 == 0 else Decimal("-0.01"))),
        )
        for offset, bar in enumerate(history_bars)
    )
    signal = VwapObservation(signal_bar, Decimal("97") / Decimal("0.95"))
    return history, signal, bars


def _d_reachable_inputs(
    program,
    *,
    gap_symbol: str | None = None,
    gap_index: int | None = None,
):
    parameters = program.parameters
    resolution = program.resolution
    target = _flat_aggregate_session(_NORMAL_DAY, resolution)
    confirming = _flat_aggregate_session(_NORMAL_DAY, resolution, Decimal("100"))
    minimum_setup_index = (gap_index + 1 if gap_index is not None else 0) + max(
        parameters.ema_slow + 2,
        parameters.atr_lookback + 1,
        parameters.swing_peak_window_bars,
    )
    schedule = _AUTHORITY.schedule_for(_NORMAL_DAY)
    assert schedule is not None
    entry_start = datetime.combine(_NORMAL_DAY, program.entry_window.start, _NY)
    first_window_index = (
        int((entry_start - schedule.opens_at).total_seconds() // 60) // int(resolution)
        - 1
    )
    final_index = max(
        first_window_index, minimum_setup_index + parameters.reclaim_confirmation_bars
    )
    setup_index = final_index - parameters.reclaim_confirmation_bars

    for index in range(len(target)):
        close = Decimal("100") + Decimal(index) * Decimal("0.02")
        target[index] = _bar_at(
            _NORMAL_DAY,
            resolution,
            index,
            close,
            open_price=close - Decimal("0.005"),
            high=close + Decimal("0.005"),
            low=close - Decimal("0.005"),
        )
        other_close = Decimal("100") + Decimal(index) * Decimal("0.03")
        confirming[index] = _bar_at(
            _NORMAL_DAY,
            resolution,
            index,
            other_close,
            open_price=other_close - Decimal("0.005"),
            high=other_close + Decimal("0.005"),
            low=other_close - Decimal("0.005"),
            symbol="QQQ",
        )

    peak = max(
        bar.high
        for bar in target[setup_index - parameters.swing_peak_window_bars : setup_index]
    )
    atr = average_true_range(
        target[setup_index - parameters.atr_lookback - 1 : setup_index],
        parameters.atr_lookback,
    )
    setup_low = peak - atr * Decimal("0.5")
    setup_close = setup_low + atr * Decimal("0.2")
    target[setup_index] = _bar_at(
        _NORMAL_DAY,
        resolution,
        setup_index,
        setup_close,
        open_price=setup_close,
        high=peak,
        low=setup_low,
    )
    previous_high = target[setup_index].high
    for index in range(setup_index + 1, final_index + 1):
        close = previous_high + Decimal("0.02")
        target[index] = _bar_at(
            _NORMAL_DAY,
            resolution,
            index,
            close,
            open_price=previous_high + Decimal("0.01"),
            high=close + Decimal("0.005"),
            low=previous_high + Decimal("0.001"),
        )
        previous_high = target[index].high
    confirming_vwaps = [VwapObservation(bar, Decimal("90")) for bar in confirming]
    if gap_index is not None:
        if gap_symbol == "SPY":
            del target[gap_index]
        elif gap_symbol == "QQQ":
            del confirming[gap_index]
            del confirming_vwaps[gap_index]
        else:
            raise ValueError("gap_symbol must name the target or confirming ETF")
    elif gap_symbol is not None:
        raise ValueError("gap_index is required when a symbol gap is requested")
    final_timestamp = schedule.opens_at + timedelta(
        minutes=final_index * int(resolution)
    )
    target = [bar for bar in target if bar.timestamp <= final_timestamp]
    confirming = [bar for bar in confirming if bar.timestamp <= final_timestamp]
    confirming_vwaps = [
        observation
        for observation in confirming_vwaps
        if observation.bar.timestamp <= final_timestamp
    ]
    return (
        target,
        confirming,
        tuple(confirming_vwaps),
        _verified_test_session(target),
        _verified_test_session(confirming),
    )


def _install_d_setup(program, target, final_index):
    parameters = program.parameters
    setup_index = final_index - parameters.reclaim_confirmation_bars
    peak_start = setup_index - parameters.swing_peak_window_bars
    swing_peak = max(bar.high for bar in target[peak_start:setup_index])
    frozen_atr = average_true_range(
        target[setup_index - parameters.atr_lookback - 1 : setup_index],
        parameters.atr_lookback,
    )
    setup_low = swing_peak - frozen_atr * Decimal("0.5")
    setup_close = setup_low + frozen_atr * Decimal("0.2")
    target[setup_index] = _bar_at(
        _NORMAL_DAY,
        program.resolution,
        setup_index,
        setup_close,
        open_price=setup_close,
        high=swing_peak,
        low=setup_low,
    )
    previous_high = target[setup_index].high
    for index in range(setup_index + 1, final_index + 1):
        close = previous_high + Decimal("0.02")
        target[index] = _bar_at(
            _NORMAL_DAY,
            program.resolution,
            index,
            close,
            open_price=previous_high + Decimal("0.01"),
            high=close + Decimal("0.005"),
            low=previous_high + Decimal("0.001"),
        )
        previous_high = target[index].high
    return setup_index


def _d_two_setup_streams(program):
    first_target, first_other, _, _, _ = _d_reachable_inputs(program)
    first_final = len(first_target) - 1
    parameters = program.parameters
    fresh_segment_warmup = max(
        parameters.ema_slow + 2,
        parameters.atr_lookback + 1,
        parameters.swing_peak_window_bars,
    )
    second_setup = first_final + 2 + fresh_segment_warmup
    second_final = second_setup + parameters.reclaim_confirmation_bars
    full_target = list(_flat_aggregate_session(_NORMAL_DAY, program.resolution))
    full_other = list(
        _flat_aggregate_session(_NORMAL_DAY, program.resolution, Decimal("100"))
    )
    for index in range(len(full_target)):
        close = Decimal("100") + Decimal(index) * Decimal("0.02")
        full_target[index] = _bar_at(
            _NORMAL_DAY,
            program.resolution,
            index,
            close,
            open_price=close - Decimal("0.005"),
            high=close + Decimal("0.005"),
            low=close - Decimal("0.005"),
        )
        other_close = Decimal("100") + Decimal(index) * Decimal("0.03")
        full_other[index] = _bar_at(
            _NORMAL_DAY,
            program.resolution,
            index,
            other_close,
            open_price=other_close - Decimal("0.005"),
            high=other_close + Decimal("0.005"),
            low=other_close - Decimal("0.005"),
            symbol="QQQ",
        )
    full_target[: len(first_target)] = first_target
    full_other[: len(first_other)] = first_other
    for index in range(first_final + 1, second_final + 1):
        previous = full_target[index - 1]
        close = previous.close + Decimal("0.02")
        full_target[index] = _bar_at(
            _NORMAL_DAY,
            program.resolution,
            index,
            close,
            open_price=previous.close + Decimal("0.01"),
            high=close + Decimal("0.005"),
            low=previous.high + Decimal("0.001"),
        )
        other_previous = full_other[index - 1]
        other_close = other_previous.close + Decimal("0.03")
        full_other[index] = _bar_at(
            _NORMAL_DAY,
            program.resolution,
            index,
            other_close,
            open_price=other_previous.close + Decimal("0.02"),
            high=other_close + Decimal("0.005"),
            low=other_previous.high + Decimal("0.001"),
            symbol="QQQ",
        )
    assert _install_d_setup(program, full_target, second_final) == second_setup
    assert program.entry_window.contains(full_target[second_final].completed_at)
    confirming_vwaps = tuple(VwapObservation(bar, Decimal("90")) for bar in full_other)
    return (
        tuple(full_target[: second_final + 1]),
        tuple(full_other[: second_final + 1]),
        confirming_vwaps[: second_final + 1],
        _verified_test_session(full_target),
        _verified_test_session(full_other),
        first_final,
        second_setup,
        second_final,
        tuple(full_target),
    )


def _fold_metrics_for_year(year, profile=None):
    profile = profile or {}
    session_dates = arch151._published_sessions_for_year(year)
    session_count = len(session_dates)
    returns = [Decimal(0)] * session_count
    return_events = profile.get(
        "return_events",
        ((session_count - 1, profile.get("annual_return", Decimal("0.01"))),),
    )
    for index, value in return_events:
        returns[index] = value
    round_trips = [0] * session_count
    active_sessions = profile.get("active_sessions", 100)
    double_sessions = profile.get("double_sessions", 0)
    for index in range(active_sessions):
        round_trips[index] = 2 if index < double_sessions else 1
    gross_positive = profile.get("gross_positive", Decimal("2"))
    gross_negative = profile.get("gross_negative", Decimal("1"))
    return arch151.FoldMetrics(
        session_dates,
        tuple(returns),
        tuple(round_trips),
        gross_positive,
        gross_negative,
        profile.get("net_positive", gross_positive),
        profile.get("net_negative", gross_negative),
        profile.get("annual_turnover", Decimal("0.25")),
    )


def _evaluation_batch_for_slot(slot, year_profiles=None):
    year_profiles = year_profiles or {}
    records = []
    for fold in arch151.WALK_FORWARD_FOLDS:
        profile = year_profiles.get(fold.scored_year, {})
        for economics_case in arch151.EVALUATION_ECONOMICS_ORDER:
            case_profiles = profile.get("economics_cases", {})
            case_profile = case_profiles.get(economics_case, {})
            metrics = _fold_metrics_for_year(
                fold.scored_year,
                {
                    key: value
                    for key, value in profile.items()
                    if key != "economics_cases"
                }
                | case_profile,
            )
            records.append(
                arch151.FoldEvaluation(
                    slot.slot_id,
                    slot.program_id,
                    slot.symbol,
                    fold,
                    economics_case,
                    metrics,
                )
            )
    return arch151.DevelopmentEvaluationBatch(slot.slot_id, tuple(records))


def _dsr_evaluation_population():
    batches = []
    for slot_index, slot in enumerate(CANONICAL_SLOTS):
        records = []
        population_index = 0
        for fold in arch151.WALK_FORWARD_FOLDS:
            session_dates = arch151._published_sessions_for_year(fold.scored_year)
            returns = []
            round_trips = []
            for session_index, _session in enumerate(session_dates):
                if slot_index == 0:
                    value = (
                        Decimal("0.0011")
                        if population_index % 2 == 0
                        else Decimal("0.0009")
                    )
                elif slot_index == 1:
                    value = (
                        Decimal("-0.0011")
                        if population_index % 2 == 0
                        else Decimal("-0.0009")
                    )
                else:
                    value = (
                        Decimal("0.001")
                        if population_index % 2 == 0
                        else Decimal("-0.0008")
                    )
                returns.append(value)
                round_trips.append(1 if session_index < 100 else 0)
                population_index += 1
            metrics = arch151.FoldMetrics(
                session_dates,
                tuple(returns),
                tuple(round_trips),
                Decimal("0") if slot_index == 1 else Decimal("2"),
                Decimal("1"),
                Decimal("0") if slot_index == 1 else Decimal("2"),
                Decimal("1"),
                Decimal("0.25"),
            )
            for economics_case in arch151.EVALUATION_ECONOMICS_ORDER:
                records.append(
                    arch151.FoldEvaluation(
                        slot.slot_id,
                        slot.program_id,
                        slot.symbol,
                        fold,
                        economics_case,
                        metrics,
                    )
                )
        batches.append(arch151.DevelopmentEvaluationBatch(slot.slot_id, tuple(records)))
    return tuple(batches)


@cache
def _one_candidate_final_freeze():
    batches = _dsr_evaluation_population()
    calculation = arch151.compute_selection_bias_evidence(batches)
    freeze = arch151.freeze_final_candidate_set(
        batches, _selection_bias_calculation=calculation
    )
    assert freeze.status is arch151.FinalFreezeStatus.ONE_CANDIDATE_FROZEN
    assert freeze.candidate_slot_id == CANONICAL_SLOTS[0].slot_id
    return freeze


def _later_period_evidence(
    period: arch151.LaterPeriodKind,
    *,
    freeze=None,
    economics_case: arch151.FillCostCase = arch151.FillCostCase.STRESS,
    returns_by_session: dict[date, Decimal] | None = None,
    outcomes_by_session: dict[date, tuple[Decimal, ...]] | None = None,
):
    selected_freeze = freeze or _one_candidate_final_freeze()
    expected_sessions, _expected_months = arch151._later_period_calendar(period)
    return_values = returns_by_session or {}
    outcomes = outcomes_by_session or {}
    sessions = []
    trades = []
    for session in expected_sessions:
        session_outcomes = outcomes.get(session, (Decimal("1"),))
        session_pnl = sum(session_outcomes, Decimal(0))
        sessions.append(
            arch151.LaterPeriodSessionEvidence(
                session,
                return_values.get(session, Decimal("0.001")),
                session_pnl,
                len(session_outcomes),
            )
        )
        trades.extend(
            arch151.LaterPeriodTradeEvidence(session, value)
            for value in session_outcomes
        )
    return arch151.LaterPeriodEvaluationEvidence(
        period,
        selected_freeze.freeze_id,
        selected_freeze.fingerprint,
        selected_freeze.candidate_slot_id,
        economics_case,
        tuple(sessions),
        tuple(trades),
    )


def _synthetic_ranking_material(
    slot,
    probability=Decimal("0.95"),
    net_profit_factor=Decimal("1.5"),
    pre_cost_profit_factor=Decimal("1.5"),
):
    aggregate = arch151.DevelopmentAggregate(
        slot.slot_id,
        arch151.FillCostCase.STRESS,
        Decimal("0.10"),
        net_profit_factor,
        pre_cost_profit_factor,
        5,
        5,
        Decimal("-0.05"),
        Decimal("0.10"),
        Decimal(100),
        Decimal("0.40"),
        Decimal(1),
        Decimal("0.5"),
        Decimal("0.25"),
    )
    return arch151.SyntheticRankingMaterial(slot.slot_id, probability, aggregate)


def test_canonical_population_is_exact_ordered_immutable_and_typed() -> None:
    assert canonical_manifest() is CANONICAL_MANIFEST
    assert len(CANONICAL_PROGRAMS) == 16
    assert len(CANONICAL_SLOTS) == 32
    assert tuple(program.key for program in CANONICAL_PROGRAMS) == tuple(ProgramKey)
    assert tuple(slot.ordinal for slot in CANONICAL_SLOTS) == tuple(range(1, 33))
    assert tuple(slot.symbol for slot in CANONICAL_SLOTS) == ("SPY", "QQQ") * 16
    assert len({program_id(program) for program in CANONICAL_PROGRAMS}) == 16
    assert len({slot.slot_id for slot in CANONICAL_SLOTS}) == 32
    for family in StrategyFamily:
        family_programs = tuple(
            item for item in CANONICAL_PROGRAMS if item.family is family
        )
        assert len(family_programs) == 4
        assert (
            sum(
                item.resolution is BarResolution.FIVE_MINUTE for item in family_programs
            )
            == 2
        )
        assert (
            sum(
                item.resolution is BarResolution.FIFTEEN_MINUTE
                for item in family_programs
            )
            == 2
        )
    assert [program.parameters.atr_lookback for program in CANONICAL_PROGRAMS[-2:]] == [
        8,
        10,
    ]
    with pytest.raises(FrozenInstanceError):
        CANONICAL_SLOTS[0].symbol = "QQQ"  # type: ignore[misc]


def test_program_identities_bind_complete_canonical_semantics() -> None:
    program = CANONICAL_PROGRAMS[0]
    payload = program_to_bytes(program)
    assert program_from_bytes(payload) is program
    assert program_id(program).version == 5
    assert len(program_fingerprint(program)) == 64
    assert program_id(program) == program_id(program_from_bytes(payload))
    altered = payload.replace(b"0.75", b"0.76")
    with pytest.raises(UnsupportedProgramError):
        program_from_bytes(altered)
    with pytest.raises(UnsupportedProgramError):
        program_from_bytes(
            payload.replace(b'"key":"A5-01",', b'"key":"A5-01","unknown":1,')
        )
    with pytest.raises(UnsupportedProgramError):
        program_from_bytes(b" " + payload)
    replacement = replace(
        program,
        parameters=replace(program.parameters, breakout_multiplier=Decimal("0.76")),
    )
    with pytest.raises(UnsupportedProgramError):
        program_fingerprint(replacement)
    assert CANONICAL_MANIFEST.fingerprint == CANONICAL_MANIFEST.fingerprint
    assert CANONICAL_MANIFEST.manifest_id.version == 5


@pytest.mark.parametrize(
    "resolution", [BarResolution.FIVE_MINUTE, BarResolution.FIFTEEN_MINUTE]
)
def test_sparse_aggregation_omits_incomplete_bucket_and_preserves_complete_bar(
    resolution,
) -> None:
    session = _NORMAL_DAY
    span = int(resolution)
    minutes = tuple(
        _minute(
            "SPY",
            session,
            offset,
            open_price=str(100 + offset),
            high=str(101 + offset),
            low=str(99 + offset),
            close=str(100 + offset),
        )
        for offset in range(span * 2)
        if offset != 2
    )
    result = aggregate_sparse_bars(minutes, resolution)
    assert result.resolution is resolution
    assert len(result.bars) == 1
    assert result.bars[0].timestamp == _AUTHORITY.schedule_for(
        session
    ).opens_at.astimezone(result.bars[0].timestamp.tzinfo) + timedelta(minutes=span)
    assert result.bars[0].open == Decimal(100 + span)
    assert result.bars[0].close == Decimal(100 + 2 * span - 1)
    assert result.bars[0].volume == 100 * span
    assert (
        len(result.input_digest)
        == len(result.output_digest)
        == len(result.source_digest)
        == 64
    )


def test_aggregation_rejects_duplicate_unscheduled_and_off_grid_minutes() -> None:
    bars = tuple(_minute("SPY", _NORMAL_DAY, offset) for offset in range(10))
    with pytest.raises(Arch151Error, match="strictly chronological"):
        aggregate_sparse_bars((bars[0], bars[1], bars[1]), BarResolution.FIVE_MINUTE)
    holiday_time = datetime.combine(date(2023, 1, 2), time(9, 30), _NY)
    holiday = tuple(
        OneMinuteBar(
            "SPY",
            holiday_time + timedelta(minutes=offset),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            100,
        )
        for offset in range(5)
    )
    with pytest.raises(Arch151Error, match="published regular XNYS"):
        aggregate_sparse_bars(holiday, BarResolution.FIVE_MINUTE)
    with pytest.raises(ValueError, match="minute aligned"):
        replace(bars[0], timestamp=bars[0].timestamp + timedelta(seconds=30))


@pytest.mark.parametrize(
    "resolution,expected",
    [(BarResolution.FIVE_MINUTE, 42), (BarResolution.FIFTEEN_MINUTE, 14)],
)
def test_sparse_aggregation_respects_published_early_close(
    resolution, expected
) -> None:
    session = date(2023, 11, 24)
    minutes = tuple(_minute("SPY", session, offset) for offset in range(210))
    result = aggregate_sparse_bars(minutes, resolution)
    assert len(result.bars) == expected
    schedule = _AUTHORITY.schedule_for(session)
    assert schedule is not None
    assert result.bars[-1].completed_at == schedule.closes_at.astimezone(
        result.bars[-1].timestamp.tzinfo
    )
    assert all(
        bar.completed_at <= schedule.closes_at.astimezone(bar.timestamp.tzinfo)
        for bar in result.bars
    )


def test_five_minute_sparse_aggregation_matches_arch150_on_early_close_gaps() -> None:
    session = date(2023, 11, 24)
    missing_offsets = {2, 17}
    minutes = tuple(
        _minute(
            "SPY",
            session,
            offset,
            open_price=str(100 + offset),
            high=str(102 + offset),
            low=str(99 + offset),
            close=str(101 + offset),
            volume=offset + 1,
        )
        for offset in range(210)
        if offset not in missing_offsets
    )
    arch150_minutes = tuple(
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
        for minute in minutes
    )

    arch150_result = arch150.aggregate_sparse_five_minute_bars(arch150_minutes)
    arch151_result = aggregate_sparse_bars(minutes, BarResolution.FIVE_MINUTE)

    def ohlcv(bars):
        return tuple(
            (bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume)
            for bar in bars
        )

    assert ohlcv(arch151_result.bars) == ohlcv(arch150_result.bars)
    assert len(arch151_result.bars) == 40
    schedule = _AUTHORITY.schedule_for(session)
    assert schedule is not None
    assert arch151_result.bars[-1].completed_at == schedule.closes_at.astimezone(UTC)
    assert arch150_result.bars[-1].timestamp + timedelta(
        minutes=5
    ) == schedule.closes_at.astimezone(UTC)


def test_session_vwap_uses_observed_minute_hlc3_volume_and_resets_per_session() -> None:
    minutes = tuple(
        _minute(
            "SPY",
            session,
            offset,
            open_price=str(price),
            high=str(price),
            low=str(price),
            close=str(price),
            volume=volume,
        )
        for session, prices, volumes in (
            (_NORMAL_DAY, range(100, 110), range(1, 11)),
            (date(2023, 1, 4), range(200, 205), (10,) * 5),
        )
        for offset, (price, volume) in enumerate(zip(prices, volumes, strict=True))
    )
    stream = aggregate_sparse_bars(minutes, BarResolution.FIVE_MINUTE)

    observations = aggregate_session_vwap(minutes, stream)

    assert len(observations) == 3
    assert observations[0].vwap.quantize(Decimal("0.000001")) == Decimal("102.666667")
    assert observations[1].vwap == Decimal(5830) / Decimal(55)
    assert observations[2].vwap == Decimal(202)
    assert tuple(item.bar for item in observations) == stream.bars


def test_session_vwap_drops_missing_bucket_without_synthesis_or_carry() -> None:
    minutes = tuple(
        _minute(
            "SPY",
            _NORMAL_DAY,
            offset,
            open_price=str(100 + offset),
            high=str(100 + offset),
            low=str(100 + offset),
            close=str(100 + offset),
            volume=1,
        )
        for offset in (0, 1, 2, 3, 5, 6, 7, 8, 9)
    )
    stream = aggregate_sparse_bars(minutes, BarResolution.FIVE_MINUTE)

    observations = aggregate_session_vwap(minutes, stream)

    assert len(stream.bars) == len(observations) == 1
    assert observations[0].bar.timestamp == minutes[4].timestamp
    assert observations[0].vwap.quantize(Decimal("0.000001")) == Decimal("104.555556")
    with pytest.raises(Arch151Error, match="does not match exact minute sources"):
        aggregate_session_vwap(minutes[:4], stream)


def test_session_vwap_rejects_zero_observed_volume() -> None:
    minutes = tuple(
        _minute("SPY", _NORMAL_DAY, offset, volume=0) for offset in range(5)
    )
    stream = aggregate_sparse_bars(minutes, BarResolution.FIVE_MINUTE)

    with pytest.raises(UnavailableIndicatorError, match="zero observed-volume"):
        aggregate_session_vwap(minutes, stream)


def test_session_vwap_requires_exact_evidence_for_post_open_projection() -> None:
    second_session = date(2023, 1, 4)
    first_minutes = tuple(_minute("SPY", _NORMAL_DAY, offset) for offset in range(5))
    post_open_minutes = tuple(
        _minute(
            "SPY",
            second_session,
            offset,
            open_price=str(100 + offset),
            high=str(100 + offset),
            low=str(100 + offset),
            close=str(100 + offset),
            volume=offset + 1,
        )
        for offset in range(5, 10)
    )
    minutes = first_minutes + post_open_minutes
    stream = aggregate_sparse_bars(minutes, BarResolution.FIVE_MINUTE)

    with pytest.raises(
        UnavailableIndicatorError, match="begin at the published XNYS open"
    ):
        aggregate_session_vwap(minutes, stream)
    post_open_bars = tuple(
        bar for bar in stream.bars if bar.session_date == second_session
    )
    evidence = arch151._test_only_verified_sparse_session(
        post_open_bars, minute_bars=post_open_minutes
    )
    observations = aggregate_session_vwap(
        minutes, stream, verified_sessions=(evidence,)
    )
    expected = sum(
        Decimal(100 + offset) * Decimal(offset + 1) for offset in range(5, 10)
    ) / Decimal(sum(offset + 1 for offset in range(5, 10)))
    second_observation = next(
        observation
        for observation in observations
        if observation.bar.session_date == second_session
    )
    assert second_observation.vwap == expected

    tampered = (
        *first_minutes,
        *post_open_minutes[:-1],
        replace(post_open_minutes[-1], volume=99),
    )
    with pytest.raises(Arch151Error, match="exact minute sources"):
        aggregate_session_vwap(tampered, stream, verified_sessions=(evidence,))


def test_one_minute_bar_has_unambiguous_completion_time() -> None:
    bar = _minute("SPY", _NORMAL_DAY, 0)
    assert bar.completed_at == bar.timestamp + timedelta(minutes=1)


def test_family_a_entry_window_applies_to_final_confirmation_bar_only() -> None:
    program = CANONICAL_PROGRAMS[0]
    calibration, measure, _ = _a_reachable_inputs(program)
    earlier = tuple(
        VwapObservation(
            _bar_at(
                _NORMAL_DAY,
                program.resolution,
                index,
                Decimal("101"),
                open_price=Decimal("100.9"),
                high=Decimal("101.1"),
                low=Decimal("100.8"),
            ),
            Decimal("100.4") + Decimal(index) / Decimal(1000),
        )
        for index in (3, 4)
    )
    crosses_window = tuple(
        VwapObservation(
            _bar_at(
                _NORMAL_DAY,
                program.resolution,
                index,
                Decimal("101"),
                open_price=Decimal("100.9"),
                high=Decimal("101.1"),
                low=Decimal("100.8"),
            ),
            Decimal("100.4") + Decimal(index) / Decimal(1000),
        )
        for index in (4, 5)
    )

    assert family_a_entry_signal(program, calibration, measure, earlier) is None
    assert (
        family_a_entry_signal(program, calibration, measure, crosses_window) is not None
    )


def test_family_a_rejects_off_grid_and_mismatched_session_observations() -> None:
    program = CANONICAL_PROGRAMS[0]
    calibration, measure, confirmation = _a_reachable_inputs(program)
    off_grid = tuple(
        replace(
            observation,
            bar=replace(
                observation.bar,
                timestamp=observation.bar.timestamp + timedelta(minutes=1),
            ),
        )
        for observation in confirmation
    )
    with pytest.raises(Arch151Error, match="session aligned"):
        family_a_entry_signal(program, calibration, measure, off_grid)

    other_session = tuple(
        replace(
            observation,
            bar=replace(
                observation.bar,
                timestamp=observation.bar.timestamp + timedelta(days=1),
            ),
        )
        for observation in confirmation
    )
    with pytest.raises(Arch151Error, match="crossed the current session"):
        family_a_entry_signal(program, calibration, measure, other_session)


def test_family_a_calibrations_are_independent_and_bound_to_symbol() -> None:
    program = CANONICAL_PROGRAMS[0]
    spy = calibrate_family_a(program, _a_history_measures(symbol="SPY"), 2023)
    qqq = calibrate_family_a(program, _a_history_measures(symbol="QQQ"), 2023)

    assert spy.symbol == "SPY"
    assert qqq.symbol == "QQQ"
    assert spy.noise_return == qqq.noise_return
    assert spy.regime_median_return == qqq.regime_median_return
    assert spy.calibration_id != qqq.calibration_id
    assert spy.calibration_fingerprint != qqq.calibration_fingerprint


def test_family_a_calibration_rejects_mixed_symbol_history() -> None:
    program = CANONICAL_PROGRAMS[0]
    spy_history = _a_history_measures(symbol="SPY")
    qqq_same_date = family_a_historical_session_measure(
        _full_session_minutes(spy_history[0].session_date, "QQQ")
    )

    with pytest.raises(Arch151Error, match="mixes instruments"):
        calibrate_family_a(program, (qqq_same_date, *spy_history[1:]), 2023)


@pytest.mark.parametrize(
    ("calibration_symbol", "current_symbol"),
    [("SPY", "QQQ"), ("QQQ", "SPY")],
)
def test_family_a_rejects_both_calibration_to_current_symbol_mismatches(
    calibration_symbol: str,
    current_symbol: str,
) -> None:
    program = CANONICAL_PROGRAMS[0]
    calibration = calibrate_family_a(
        program, _a_history_measures(symbol=calibration_symbol), 2023
    )
    _, current, confirmation = _a_reachable_inputs(program, current_symbol)

    with pytest.raises(Arch151Error, match="source-bound"):
        family_a_entry_signal(program, calibration, current, confirmation)
    with pytest.raises(Arch151Error, match="binding"):
        arch151.family_a_regime_passes(program, calibration, current)
    with pytest.raises(Arch151Error, match="breakout inputs"):
        family_a_breakout_level(program, calibration, current)
    with pytest.raises(Arch151Error, match="risk inputs"):
        family_a_initial_risk(program, calibration, current, Decimal("100"))


def test_family_a_rejects_confirmation_symbol_mismatch() -> None:
    program = CANONICAL_PROGRAMS[0]
    calibration, current, _ = _a_reachable_inputs(program, "SPY")
    _, _, qqq_confirmation = _a_reachable_inputs(program, "QQQ")

    with pytest.raises(Arch151Error, match="confirmation instrument"):
        family_a_entry_signal(program, calibration, current, qqq_confirmation)


def test_family_a_historical_measure_requires_every_scheduled_session_minute() -> None:
    regular_session = _full_session_minutes(_NORMAL_DAY)
    assert len(regular_session) == 390
    measured = family_a_historical_session_measure(regular_session)
    assert measured.measure_scope is FamilyAMeasureScope.COMPLETE_HISTORICAL_SESSION
    assert measured.symbol == "SPY"

    with pytest.raises(UnavailableIndicatorError, match="complete published session"):
        family_a_historical_session_measure(regular_session[:-1])


def test_family_a_historical_measure_uses_published_early_close_length() -> None:
    early_close = date(2023, 11, 24)
    schedule = _AUTHORITY.schedule_for(early_close)
    assert schedule is not None
    assert schedule.closes_at.astimezone(_NY).time() == time(13, 0)
    bars = _full_session_minutes(early_close, "QQQ")
    assert len(bars) == 210

    measured = family_a_historical_session_measure(bars)
    assert measured.symbol == "QQQ"
    assert measured.measure_scope is FamilyAMeasureScope.COMPLETE_HISTORICAL_SESSION


def test_family_a_current_opening_measure_is_causal_without_future_bars() -> None:
    first_30 = _full_session_minutes(_NORMAL_DAY, "QQQ")[:30]
    current = family_a_session_measure(first_30)

    assert current.symbol == "QQQ"
    assert current.measure_scope is FamilyAMeasureScope.CURRENT_OPENING_WINDOW
    with pytest.raises(UnavailableIndicatorError, match="exactly 30"):
        family_a_session_measure((*first_30, _minute("QQQ", _NORMAL_DAY, 30)))
    with pytest.raises(UnavailableIndicatorError, match="complete published session"):
        family_a_historical_session_measure(first_30)
    with pytest.raises(Arch151Error, match="complete published historical"):
        calibrate_family_a(
            CANONICAL_PROGRAMS[0], (*_a_history_measures(), current), 2023
        )


def test_family_a_calibration_is_prior_only_dimensionless_and_frozen() -> None:
    program = CANONICAL_PROGRAMS[0]
    calibration = calibrate_family_a(program, _a_history_measures(), 2023)
    assert calibration.symbol == "SPY"
    assert calibration.noise_return == Decimal("0.001")
    assert calibration.regime_median_return == Decimal("0.001")
    current = family_a_session_measure(
        tuple(_minute("SPY", _NORMAL_DAY, i) for i in range(30))
    )
    assert current.measure_scope is FamilyAMeasureScope.CURRENT_OPENING_WINDOW
    _, measure, confirmation = _a_reachable_inputs(program)
    assert current.absolute_return == 0
    assert measure == current
    assert (
        family_a_entry_signal(program, calibration, measure, confirmation) is not None
    )
    current_year_complete = family_a_historical_session_measure(
        _full_session_minutes(_NORMAL_DAY)
    )
    with pytest.raises(Arch151Error, match="before scored year"):
        calibrate_family_a(
            program, (*_a_history_measures(), current_year_complete), 2023
        )
    with pytest.raises(FrozenInstanceError):
        calibration.noise_return = Decimal("99")
    altered_bar = replace(
        confirmation[1].bar,
        timestamp=confirmation[1].bar.timestamp + timedelta(minutes=5),
    )
    later = (confirmation[0], replace(confirmation[1], bar=altered_bar))
    with pytest.raises(UnavailableIndicatorError, match="gap"):
        family_a_entry_signal(program, calibration, measure, later)


def test_family_a_uses_price_times_dimensionless_noise_for_stop_risk() -> None:
    program = CANONICAL_PROGRAMS[0]
    calibration, current_session, _ = _a_reachable_inputs(program)
    level = family_a_breakout_level(program, calibration, current_session)
    assert level.symbol == "SPY"
    assert level.calibration_id == calibration.calibration_id
    assert level.level == Decimal("100.07500")
    risk = family_a_initial_risk(program, calibration, current_session, Decimal("100"))
    assert risk.symbol == "SPY"
    assert risk.calibration_id == calibration.calibration_id
    assert risk.stop_reference_price == Decimal("99.875000")
    assert risk.risk_distance == Decimal("0.125000")


def test_family_c_deviation_is_normalized_and_stop_converts_to_price_distance() -> None:
    assert normalized_vwap_deviation(Decimal("99"), Decimal("100")) == Decimal("-0.01")
    assert vwap_sigma_stop_distance(
        Decimal("100"), Decimal("0.01"), Decimal("2")
    ) == Decimal("2.00")


@pytest.mark.parametrize(
    "family",
    [
        StrategyFamily.NOISE_VWAP_BREAKOUT,
        StrategyFamily.OPENING_RANGE_RETEST,
        StrategyFamily.VWAP_MEAN_REVERSION,
        StrategyFamily.CROSS_ETF_TREND_PULLBACK,
    ],
)
def test_all_sixteen_programs_have_behaviorally_reachable_entry_predicates(
    family,
) -> None:
    programs = tuple(item for item in CANONICAL_PROGRAMS if item.family is family)
    assert len(programs) == 4
    for program in programs:
        if family is StrategyFamily.NOISE_VWAP_BREAKOUT:
            calibration, measure, confirmation = _a_reachable_inputs(program)
            signal = family_a_entry_signal(program, calibration, measure, confirmation)
            assert signal is not None, program.key
            assert signal.symbol == calibration.symbol == measure.symbol
            assert (
                len(signal.confirmation_timestamps)
                == program.parameters.confirmation_bars
            )
            assert signal.final_close > signal.breakout_level
        elif family is StrategyFamily.OPENING_RANGE_RETEST:
            bars = _b_reachable_session(program)
            minute_stream = _minutes_for_aggregates(tuple(bars), program.resolution)
            aggregate = aggregate_sparse_bars(minute_stream, program.resolution)
            signal = family_b_entry_signal(program, aggregate.bars)
            assert signal is not None, program.key
            assert signal.symbol == "SPY"
            assert (
                len(signal.breakout_confirmation_timestamps)
                == program.parameters.breakout_confirmation_bars
            )
            assert (
                len(signal.reclaim_timestamps)
                == program.parameters.reclaim_confirmation_bars
            )
            assert (
                signal.retest_timestamp not in signal.breakout_confirmation_timestamps
            )
            assert signal.retest_timestamp not in signal.reclaim_timestamps
        elif family is StrategyFamily.VWAP_MEAN_REVERSION:
            history, current, bars = _c_reachable_inputs(program)
            minute_stream = _minutes_for_aggregates(tuple(bars), program.resolution)
            assert len(
                aggregate_sparse_bars(minute_stream, program.resolution).bars
            ) == len(bars)
            sparse_session = _verified_test_session(bars)
            signal = family_c_entry_signal(
                program, history, current, verified_session=sparse_session
            )
            assert signal is not None, program.key
            assert signal.symbol == "SPY"
            assert signal.normalized_deviation < 0
            assert signal.efficiency_ratio <= program.parameters.efficiency_ratio_max
            signal_index = next(
                index for index, bar in enumerate(bars) if bar == current.bar
            )
            assert family_c_reversion_exit(
                program,
                signal,
                VwapObservation(bars[signal_index + 1], Decimal("90")),
                verified_session=sparse_session,
            )
        else:
            target, other, vwaps, target_session, other_session = _d_reachable_inputs(
                program
            )
            minute_stream = _minutes_for_aggregates(tuple(target), program.resolution)
            assert len(
                aggregate_sparse_bars(minute_stream, program.resolution).bars
            ) == len(target)
            signal = family_d_entry_signal(
                program,
                target,
                other,
                vwaps,
                target_session=target_session,
                confirming_session=other_session,
            )
            assert signal is not None, program.key
            assert signal.symbol == "SPY"
            assert signal.confirming_symbol == "QQQ"
            assert signal.stop_reference_price < signal.pullback_low < signal.swing_peak


@pytest.mark.parametrize("failure_stage", ["retest", "reclaim"])
def test_family_b_recovers_with_a_fresh_setup_after_failure(failure_stage: str) -> None:
    program, bars, level = _b_case()
    if failure_stage == "retest":
        _set_b_case_bar(
            bars,
            program,
            6,
            close=level + Decimal("0.10"),
            low=level + Decimal("0.03"),
        )
        _set_b_case_bar(
            bars,
            program,
            7,
            close=level + Decimal("0.02"),
            low=level * Decimal("0.997"),
        )
        valid_breakout, retest, reclaim = 8, 9, 10
    else:
        _set_b_valid_setup(bars, program, level, 6, 7, 8)
        _set_b_case_bar(bars, program, 8, close=level, low=level - Decimal("0.01"))
        valid_breakout, retest, reclaim = 9, 10, 11

    _set_b_valid_setup(bars, program, level, valid_breakout, retest, reclaim)
    signal = family_b_entry_signal(program, bars[: reclaim + 1])

    assert signal is not None
    assert signal.breakout_confirmation_timestamps == (bars[valid_breakout].timestamp,)
    assert signal.retest_timestamp == bars[retest].timestamp
    assert signal.reclaim_timestamps == (bars[reclaim].timestamp,)


def test_family_b_recovers_after_a_missing_post_opening_bucket() -> None:
    program, bars, level = _b_case()
    _set_b_case_bar(
        bars,
        program,
        6,
        close=level + Decimal("0.10"),
        low=level + Decimal("0.03"),
    )
    _set_b_valid_setup(bars, program, level, 8, 9, 10)
    sparse = (*bars[:7], *bars[8:11])

    signal = family_b_entry_signal(program, sparse)

    assert signal is not None
    assert signal.breakout_confirmation_timestamps == (bars[8].timestamp,)
    assert signal.retest_timestamp == bars[9].timestamp
    assert signal.reclaim_timestamps == (bars[10].timestamp,)


def test_family_b_missing_or_incomplete_opening_range_fails_closed() -> None:
    program, bars, _ = _b_case()
    missing_opening_bar = (*bars[:2], *bars[3:12])

    with pytest.raises(
        UnavailableIndicatorError,
        match="opening range must be complete and session aligned",
    ):
        family_b_entry_signal(program, missing_opening_bar)


def test_family_b_retest_deadline_includes_exact_final_subsequent_bar() -> None:
    program, bars, level = _b_case()
    final_breakout = 6
    deadline_retest = final_breakout + program.parameters.retest_deadline_bars
    upper = level * (
        Decimal(1) + program.parameters.retest_tolerance_bps / Decimal(10000)
    )
    _set_b_case_bar(
        bars,
        program,
        final_breakout,
        close=level + Decimal("0.10"),
        low=level + Decimal("0.03"),
    )
    for index in range(final_breakout + 1, deadline_retest):
        _set_b_case_bar(
            bars,
            program,
            index,
            close=upper + Decimal("0.10"),
            low=upper + Decimal("0.05"),
        )
    _set_b_case_bar(
        bars,
        program,
        deadline_retest,
        close=level + Decimal("0.02"),
        low=level,
    )
    _set_b_case_bar(
        bars,
        program,
        deadline_retest + 1,
        close=level + Decimal("0.12"),
        low=level + Decimal("0.04"),
    )

    signal = family_b_entry_signal(program, bars[: deadline_retest + 2])

    assert signal is not None
    assert signal.retest_timestamp == bars[deadline_retest].timestamp

    late_bars = list(bars)
    _set_b_case_bar(
        late_bars,
        program,
        deadline_retest,
        close=upper + Decimal("0.10"),
        low=upper + Decimal("0.05"),
    )
    _set_b_case_bar(
        late_bars,
        program,
        deadline_retest + 1,
        close=level,
        low=level,
    )
    _set_b_case_bar(
        late_bars,
        program,
        deadline_retest + 2,
        close=level + Decimal("0.12"),
        low=level + Decimal("0.04"),
    )
    assert family_b_entry_signal(program, late_bars[: deadline_retest + 3]) is None


def test_family_b_signal_is_bound_to_current_reclaim_completion() -> None:
    program, bars, level = _b_case()
    _set_b_valid_setup(bars, program, level, 6, 7, 8)

    signal = family_b_entry_signal(program, bars[:9])

    assert signal is not None
    assert signal.signal_timestamp == bars[8].completed_at
    assert signal.reclaim_timestamps == (bars[8].timestamp,)
    assert family_b_entry_signal(program, bars[:10]) is None


@pytest.mark.parametrize("symbol", ["SPY", "QQQ"])
def test_family_b_signal_binds_execution_symbol(symbol: str) -> None:
    program, bars, level = _b_case()
    _set_b_valid_setup(bars, program, level, 6, 7, 8)
    selected = tuple(replace(bar, symbol=symbol) for bar in bars[:9])

    signal = family_b_entry_signal(program, selected)

    assert signal is not None
    assert signal.symbol == symbol


def test_family_c_rejects_insufficient_warmup_and_zero_er_denominator() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C15_02)
    bars = _flat_aggregate_session(_NORMAL_DAY, program.resolution)
    sparse_session = _verified_test_session(bars)
    current = VwapObservation(bars[20], Decimal("100"))
    short = tuple(VwapObservation(bar, Decimal("100")) for bar in bars[20 - 11 : 20])
    with pytest.raises(UnavailableIndicatorError, match="warmup"):
        family_c_entry_signal(program, short, current, verified_session=sparse_session)
    with pytest.raises(UnavailableIndicatorError, match="zero"):
        efficiency_ratio([Decimal("100")] * 11, 10)
    with pytest.raises(UnavailableIndicatorError, match="two values"):
        sample_standard_deviation([Decimal("0.1")])


def test_family_c_rejects_off_grid_and_cross_session_history() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C5_01)
    history, current, bars = _c_reachable_inputs(program)
    sparse_session = _verified_test_session(bars)
    off_grid_history = tuple(
        replace(
            observation,
            bar=replace(
                observation.bar,
                timestamp=observation.bar.timestamp + timedelta(minutes=1),
            ),
        )
        for observation in history
    )
    off_grid_current = replace(
        current,
        bar=replace(
            current.bar, timestamp=current.bar.timestamp + timedelta(minutes=1)
        ),
    )
    with pytest.raises(Arch151Error, match="session aligned"):
        family_c_entry_signal(
            program,
            off_grid_history,
            off_grid_current,
            verified_session=sparse_session,
        )

    other_session_history = tuple(
        replace(
            observation,
            bar=replace(
                observation.bar,
                timestamp=observation.bar.timestamp + timedelta(days=1),
            ),
        )
        for observation in history
    )
    with pytest.raises(UnavailableIndicatorError, match="gap or session"):
        family_c_entry_signal(
            program,
            other_session_history,
            current,
            verified_session=sparse_session,
        )


def test_family_c_exit_rejects_earlier_or_different_session_bar() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C5_01)
    history, current, bars = _c_reachable_inputs(program)
    sparse_session = _verified_test_session(bars)
    signal = family_c_entry_signal(
        program, history, current, verified_session=sparse_session
    )
    assert signal is not None
    signal_index = next(index for index, bar in enumerate(bars) if bar == current.bar)
    earlier = VwapObservation(bars[signal_index - 1], Decimal("90"))
    with pytest.raises(Arch151Error, match="strictly later"):
        family_c_reversion_exit(
            program, signal, earlier, verified_session=sparse_session
        )

    other_session = VwapObservation(
        replace(
            current.bar,
            timestamp=current.bar.timestamp + timedelta(days=1),
        ),
        Decimal("90"),
    )
    with pytest.raises(Arch151Error, match="strictly later"):
        family_c_reversion_exit(
            program, signal, other_session, verified_session=sparse_session
        )


@pytest.mark.parametrize(
    ("entry_symbol", "exit_symbol"), [("SPY", "QQQ"), ("QQQ", "SPY")]
)
def test_family_c_entry_and_exit_are_bound_to_the_same_instrument(
    entry_symbol: str, exit_symbol: str
) -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C5_01)
    history, current, bars = _c_reachable_inputs(program)
    entry_bars = tuple(replace(bar, symbol=entry_symbol) for bar in bars)
    entry_by_time = {bar.timestamp: bar for bar in entry_bars}
    entry_history = tuple(
        replace(observation, bar=entry_by_time[observation.bar.timestamp])
        for observation in history
    )
    entry_current = replace(current, bar=entry_by_time[current.bar.timestamp])
    entry_evidence = _verified_test_session(entry_bars)
    signal = family_c_entry_signal(
        program, entry_history, entry_current, verified_session=entry_evidence
    )
    assert signal is not None
    exit_bar = next(
        bar for bar in entry_bars if bar.timestamp > entry_current.bar.timestamp
    )
    wrong_exit_bar = replace(exit_bar, symbol=exit_symbol)
    wrong_exit_evidence = _verified_test_session(
        tuple(replace(bar, symbol=exit_symbol) for bar in entry_bars)
    )
    with pytest.raises(Arch151Error, match="instrument or resolution"):
        family_c_reversion_exit(
            program,
            signal,
            VwapObservation(wrong_exit_bar, Decimal("90")),
            verified_session=wrong_exit_evidence,
        )


def test_family_c_requires_sealed_sparse_session_and_valid_frozen_sigma() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C5_01)
    history, current, bars = _c_reachable_inputs(program)
    with pytest.raises(arch151.AuthorizationUnavailableError, match="evaluator-owned"):
        family_c_entry_signal(program, history, current)
    sparse_session = _verified_test_session(bars)
    signal = family_c_entry_signal(
        program, history, current, verified_session=sparse_session
    )
    assert signal is not None
    later = next(bar for bar in bars if bar.timestamp > current.bar.timestamp)
    with pytest.raises(Arch151Error, match="positive and finite"):
        family_c_reversion_exit(
            program,
            replace(signal, frozen_entry_sigma=Decimal(0)),
            VwapObservation(later, Decimal("90")),
            verified_session=sparse_session,
        )
    with pytest.raises(Arch151Error, match="canonical entry signal"):
        family_c_reversion_exit(
            program,
            replace(signal, program_id=UUID(int=1)),
            VwapObservation(later, Decimal("90")),
            verified_session=sparse_session,
        )


def test_family_c_restarts_from_verified_sparse_projection_after_missing_open() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C5_02)
    bars = list(_flat_aggregate_session(_NORMAL_DAY, program.resolution))
    parameters = program.parameters
    required = max(
        parameters.deviation_lookback_bars, parameters.efficiency_ratio_lookback
    )
    signal_index = required + 1
    for index in range(signal_index):
        close = Decimal("100") if index % 2 == 0 else Decimal("101")
        bars[index] = _bar_at(
            _NORMAL_DAY,
            program.resolution,
            index,
            close,
            open_price=close,
            high=close + Decimal("0.01"),
            low=close - Decimal("0.01"),
        )
    bars[signal_index] = _bar_at(
        _NORMAL_DAY,
        program.resolution,
        signal_index,
        Decimal("97"),
        open_price=Decimal("97"),
        high=Decimal("97.01"),
        low=Decimal("96.99"),
    )
    assert program.entry_window.contains(bars[signal_index].completed_at)
    history_bars = tuple(bars[index] for index in range(1, signal_index))
    history = tuple(
        VwapObservation(
            bar,
            bar.close
            / (Decimal(1) + (Decimal("0.01") if offset % 2 == 0 else Decimal("-0.01"))),
        )
        for offset, bar in enumerate(history_bars)
    )
    current = VwapObservation(bars[signal_index], Decimal("97") / Decimal("0.95"))
    sparse_bars = tuple(bars[1:])
    sparse_evidence = _verified_test_session(sparse_bars)
    signal = family_c_entry_signal(
        program, history, current, verified_session=sparse_evidence
    )
    assert signal is not None
    with pytest.raises(arch151.AuthorizationUnavailableError, match="evaluator-owned"):
        family_c_entry_signal(program, history, current)
    forged_history = (
        replace(
            history[0],
            bar=replace(history[0].bar, volume=history[0].bar.volume + 1),
        ),
        *history[1:],
    )
    with pytest.raises(arch151.AuthorizationUnavailableError, match="source-bound"):
        family_c_entry_signal(
            program,
            forged_history,
            current,
            verified_session=sparse_evidence,
        )


def test_family_d_ema_atr_and_cross_confirmation_reset_at_gaps() -> None:
    up = tuple(
        _bar_at(
            _NORMAL_DAY,
            BarResolution.FIVE_MINUTE,
            index,
            Decimal("100") + Decimal(index) / Decimal(10),
            high=Decimal("101") + Decimal(index) / Decimal(10),
            low=Decimal("99") + Decimal(index) / Decimal(10),
        )
        for index in range(20)
    )
    ema = ema_series(up, 8)
    assert ema[:7] == (None,) * 7
    assert ema[7] == sum((bar.close for bar in up[:8]), Decimal(0)) / Decimal(8)
    assert ema_series(up[:7], 8) == (None,) * 7

    sparse_local = (*up[:5], *up[6:])
    local_ema = ema_series(sparse_local, 3)
    assert local_ema[5:7] == (None, None)
    assert local_ema[7] == sum((bar.close for bar in up[6:9]), Decimal(0)) / Decimal(3)
    sparse_confirming = tuple(replace(bar, symbol="QQQ") for bar in sparse_local)
    confirming_ema = ema_series(sparse_confirming, 3)
    assert confirming_ema[5:7] == (None, None)
    assert confirming_ema[7] == local_ema[7]

    atr = average_true_range(up[5:20], 14)
    assert atr > 0
    with pytest.raises(UnavailableIndicatorError, match="exactly 15"):
        average_true_range(up[5:19], 14)
    with pytest.raises(UnavailableIndicatorError, match="gap"):
        average_true_range((up[0], up[1], up[3]), 2)
    target = up[-2:]
    other = tuple(replace(bar, symbol="QQQ") for bar in target)
    assert len(exact_cross_etf_confirmation(target, other, 2)) == 2
    with pytest.raises(UnavailableIndicatorError, match="gap"):
        contiguous_aggregate_bars((up[0], up[2]))
    with pytest.raises(UnavailableIndicatorError, match="gap or session"):
        exact_cross_etf_confirmation(
            target,
            (
                other[0],
                replace(other[1], timestamp=other[1].timestamp + timedelta(minutes=5)),
            ),
            2,
        )


def test_family_d_vwap_observations_bind_exact_confirming_bars() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target, confirming, vwaps, target_session, confirming_session = _d_reachable_inputs(
        program
    )
    assert (
        family_d_entry_signal(
            program,
            target,
            confirming,
            vwaps,
            target_session=target_session,
            confirming_session=confirming_session,
        )
        is not None
    )

    reordered = tuple(reversed(vwaps))
    wrong_symbol = tuple(
        VwapObservation(bar, observation.vwap)
        for bar, observation in zip(target, vwaps, strict=True)
    )
    stale_first = replace(
        vwaps[0],
        bar=replace(
            confirming[0], timestamp=confirming[0].timestamp - timedelta(minutes=5)
        ),
    )
    stale = (stale_first, *vwaps[1:])
    for invalid in (reordered, wrong_symbol, stale):
        with pytest.raises(UnavailableIndicatorError, match="not exactly bar aligned"):
            family_d_entry_signal(
                program,
                target,
                confirming,
                invalid,
                target_session=target_session,
                confirming_session=confirming_session,
            )


@pytest.mark.parametrize("gap_symbol", ["SPY", "QQQ"])
def test_family_d_reseeds_and_finds_fresh_signal_after_either_symbol_gap(
    gap_symbol: str,
) -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target, confirming, vwaps, target_session, confirming_session = _d_reachable_inputs(
        program, gap_symbol=gap_symbol, gap_index=1
    )

    signal = family_d_entry_signal(
        program,
        target,
        confirming,
        vwaps,
        target_session=target_session,
        confirming_session=confirming_session,
    )

    assert signal is not None
    assert signal.setup_timestamp > target[0].timestamp
    assert signal.signal_timestamp >= signal.setup_timestamp
    assert signal.confirming_symbol == "QQQ"


def test_family_d_does_not_bridge_cross_confirmation_across_a_gap() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target, confirming, vwaps, target_session, confirming_session = _d_reachable_inputs(
        program
    )
    original = family_d_entry_signal(
        program,
        target,
        confirming,
        vwaps,
        target_session=target_session,
        confirming_session=confirming_session,
    )
    assert original is not None
    signal_index = next(
        index
        for index, bar in enumerate(target)
        if bar.timestamp == original.signal_timestamp
    )
    missing_confirmation_index = signal_index - 1
    gapped_confirming = tuple(
        bar
        for index, bar in enumerate(confirming)
        if index != missing_confirmation_index
    )
    gapped_vwaps = tuple(
        observation
        for index, observation in enumerate(vwaps)
        if index != missing_confirmation_index
    )

    assert (
        family_d_entry_signal(
            program,
            target,
            gapped_confirming,
            gapped_vwaps,
            target_session=target_session,
            confirming_session=_verified_test_session(gapped_confirming),
        )
        is None
    )


@pytest.mark.parametrize("gap_symbol", ["SPY", "QQQ"])
def test_family_d_discards_pre_gap_signal_when_final_segment_has_no_setup(
    gap_symbol: str,
) -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    (
        _target,
        confirming_all,
        _vwaps,
        _target_session,
        _confirming_session,
        first_final,
        second_setup,
        _second_final,
        full_target,
    ) = _d_two_setup_streams(program)
    full_confirming = tuple(confirming_all)
    cutoff = second_setup
    gap_index = first_final + 1
    target = tuple(
        bar
        for index, bar in enumerate(full_target[:cutoff])
        if gap_symbol != "SPY" or index != gap_index
    )
    confirming = tuple(
        bar
        for index, bar in enumerate(full_confirming[:cutoff])
        if gap_symbol != "QQQ" or index != gap_index
    )
    vwaps = tuple(VwapObservation(bar, Decimal("90")) for bar in confirming)
    target_session = _verified_test_session(target)
    confirming_session = _verified_test_session(confirming)

    result = family_d_entry_signal(
        program,
        target,
        confirming,
        vwaps,
        target_session=target_session,
        confirming_session=confirming_session,
    )

    assert target[-1].timestamp == confirming[-1].timestamp
    assert result is None


def test_family_d_gap_near_close_without_fresh_warmup_has_no_signal() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target = _flat_aggregate_session(_NORMAL_DAY, program.resolution)
    confirming = [
        replace(bar, symbol="QQQ")
        for bar in _flat_aggregate_session(
            _NORMAL_DAY, program.resolution, Decimal("100")
        )
    ]
    gap_index = len(target) - 3
    del target[gap_index]
    vwaps = tuple(VwapObservation(bar, Decimal("90")) for bar in confirming)

    assert (
        family_d_entry_signal(
            program,
            target,
            confirming,
            vwaps,
            target_session=_verified_test_session(target),
            confirming_session=_verified_test_session(confirming),
        )
        is None
    )


def test_family_d_emits_first_valid_signal_only_at_current_decision_bar() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target_prefix, confirming_prefix, _, _, _ = _d_reachable_inputs(program)
    full_target = list(_flat_aggregate_session(_NORMAL_DAY, program.resolution))
    full_confirming = list(
        tuple(
            replace(bar, symbol="QQQ")
            for bar in _flat_aggregate_session(
                _NORMAL_DAY, program.resolution, Decimal("100")
            )
        )
    )
    full_target[: len(target_prefix)] = target_prefix
    full_confirming[: len(confirming_prefix)] = confirming_prefix
    target_evidence = _verified_test_session(full_target)
    confirming_evidence = _verified_test_session(full_confirming)

    signal = family_d_entry_signal(
        program,
        target_prefix,
        confirming_prefix,
        tuple(VwapObservation(bar, Decimal("90")) for bar in confirming_prefix),
        target_session=target_evidence,
        confirming_session=confirming_evidence,
    )
    assert signal is not None
    assert signal.signal_timestamp == target_prefix[-1].timestamp
    assert signal.symbol == "SPY"
    assert signal.program_id == program_id(program)

    later_target = tuple(full_target[: len(target_prefix) + 1])
    later_confirming = tuple(full_confirming[: len(confirming_prefix) + 1])
    assert (
        family_d_entry_signal(
            program,
            later_target,
            later_confirming,
            tuple(VwapObservation(bar, Decimal("90")) for bar in later_confirming),
            target_session=target_evidence,
            confirming_session=confirming_evidence,
        )
        is None
    )


def test_family_d_later_independent_setup_signals_after_first_decision() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    (
        target,
        confirming,
        vwaps,
        target_session,
        confirming_session,
        first_final,
        second_setup,
        second_final,
        full_target,
    ) = _d_two_setup_streams(program)
    prefix_target = tuple(full_target[: first_final + 1])
    full_confirming = confirming_session.bars
    first_prefix_signal = family_d_entry_signal(
        program,
        prefix_target,
        full_confirming[: first_final + 1],
        tuple(
            VwapObservation(bar, Decimal("90"))
            for bar in full_confirming[: first_final + 1]
        ),
        target_session=target_session,
        confirming_session=confirming_session,
    )
    assert first_prefix_signal is not None
    assert first_prefix_signal.signal_timestamp == prefix_target[-1].timestamp

    second_signal = family_d_entry_signal(
        program,
        target,
        confirming,
        vwaps,
        target_session=target_session,
        confirming_session=confirming_session,
    )
    assert second_signal is not None
    assert second_signal.signal_timestamp == full_target[second_final].timestamp
    assert second_signal.setup_timestamp == full_target[second_setup].timestamp
    assert second_signal.setup_timestamp > first_prefix_signal.setup_timestamp


@pytest.mark.parametrize("gap_symbol", ["SPY", "QQQ"])
def test_family_d_later_independent_setup_signals_after_gap(gap_symbol: str) -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    (
        target_all,
        confirming_all,
        _vwaps,
        _target_session,
        _confirming_session,
        first_final,
        second_setup,
        second_final,
        full_target,
    ) = _d_two_setup_streams(program)
    gap_index = first_final + 1
    target = tuple(
        bar
        for index, bar in enumerate(target_all)
        if gap_symbol != "SPY" or index != gap_index
    )
    confirming = tuple(
        bar
        for index, bar in enumerate(confirming_all)
        if gap_symbol != "QQQ" or index != gap_index
    )
    vwaps = tuple(VwapObservation(bar, Decimal("90")) for bar in confirming)
    target_session = _verified_test_session(target)
    confirming_session = _verified_test_session(confirming)

    signal = family_d_entry_signal(
        program,
        target,
        confirming,
        vwaps,
        target_session=target_session,
        confirming_session=confirming_session,
    )

    assert signal is not None
    assert signal.setup_timestamp == full_target[second_setup].timestamp
    assert signal.signal_timestamp == full_target[second_final].timestamp
    assert signal.signal_timestamp == target[-1].timestamp == confirming[-1].timestamp


def test_family_d_expired_first_entry_does_not_block_later_signal() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    (
        target,
        confirming,
        vwaps,
        target_session,
        confirming_session,
        first_final,
        _second_setup,
        second_final,
        full_target,
    ) = _d_two_setup_streams(program)
    target_minutes = list(
        _minutes_for_aggregates(full_target[: second_final + 1], program.resolution)
    )
    confirming_minutes = list(_minutes_for_aggregates(confirming, program.resolution))
    first_signal_bar = full_target[first_final]
    second_signal_bar = full_target[second_final]
    next_entry_minute = second_signal_bar.completed_at
    schedule = _AUTHORITY.schedule_for(_NORMAL_DAY)
    assert schedule is not None
    next_entry_offset = int(
        (next_entry_minute - schedule.opens_at).total_seconds() // 60
    )
    next_bucket = full_target[second_final + 1]
    target_minutes.append(
        _minute(
            "SPY",
            _NORMAL_DAY,
            next_entry_offset,
            open_price=str(next_bucket.open),
            high=str(next_bucket.high),
            low=str(next_bucket.low),
            close=str(next_bucket.close),
            volume=next_bucket.volume // int(program.resolution),
        )
    )
    target_minutes = [
        minute
        for minute in target_minutes
        if minute.timestamp != first_signal_bar.completed_at
    ]
    minute_times = {minute.timestamp for minute in target_minutes}
    assert first_signal_bar.completed_at not in minute_times
    assert next_entry_minute in minute_times

    target = aggregate_sparse_bars(target_minutes, program.resolution).bars
    confirming = aggregate_sparse_bars(confirming_minutes, program.resolution).bars
    assert all(
        bar.timestamp != full_target[first_final + 1].timestamp for bar in target
    )
    target_session = arch151._test_only_verified_sparse_session(
        target, minute_bars=target_minutes
    )
    confirming_session = arch151._test_only_verified_sparse_session(
        confirming, minute_bars=confirming_minutes
    )
    vwaps = tuple(VwapObservation(bar, Decimal("90")) for bar in confirming)

    later_signal = family_d_entry_signal(
        program,
        target,
        confirming,
        vwaps,
        target_session=target_session,
        confirming_session=confirming_session,
    )
    assert later_signal is not None
    assert later_signal.signal_timestamp == second_signal_bar.timestamp
    assert (
        later_signal.signal_timestamp
        == target[-1].timestamp
        == confirming[-1].timestamp
    )


def test_family_d_gap_recovery_requires_fresh_warmup_and_verified_projection() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target, confirming, vwaps, target_session, confirming_session = _d_reachable_inputs(
        program, gap_symbol="SPY", gap_index=0
    )
    recovered = family_d_entry_signal(
        program,
        target,
        confirming,
        vwaps,
        target_session=target_session,
        confirming_session=confirming_session,
    )
    assert recovered is not None
    assert recovered.signal_timestamp == target[-1].timestamp
    with pytest.raises(arch151.AuthorizationUnavailableError, match="evaluator-owned"):
        family_d_entry_signal(program, target, confirming, vwaps)
    with pytest.raises(arch151.AuthorizationUnavailableError, match="source-bound"):
        family_d_entry_signal(
            program,
            target[1:],
            confirming[1:],
            vwaps[1:],
            target_session=target_session,
            confirming_session=confirming_session,
        )

    required = max(
        program.parameters.ema_slow + 2,
        program.parameters.atr_lookback + 1,
        program.parameters.swing_peak_window_bars,
    )
    short_target = target[: required - 1]
    short_confirming = confirming[: required - 1]
    assert (
        family_d_entry_signal(
            program,
            short_target,
            short_confirming,
            vwaps[: required - 1],
            target_session=target_session,
            confirming_session=confirming_session,
        )
        is None
    )


def test_family_d_each_prefix_matches_its_current_decision_result() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target, confirming, _, _, _ = _d_reachable_inputs(program)
    full_target = list(_flat_aggregate_session(_NORMAL_DAY, program.resolution))
    full_confirming = list(
        tuple(
            replace(bar, symbol="QQQ")
            for bar in _flat_aggregate_session(
                _NORMAL_DAY, program.resolution, Decimal("100")
            )
        )
    )
    full_target[: len(target)] = target
    full_confirming[: len(confirming)] = confirming
    target_evidence = _verified_test_session(full_target)
    confirming_evidence = _verified_test_session(full_confirming)

    observed = []
    for length in range(max(1, len(target) - 3), len(target) + 1):
        target_prefix = tuple(full_target[:length])
        confirming_prefix = tuple(full_confirming[:length])
        vwaps = tuple(VwapObservation(bar, Decimal("90")) for bar in confirming_prefix)
        result = family_d_entry_signal(
            program,
            target_prefix,
            confirming_prefix,
            vwaps,
            target_session=target_evidence,
            confirming_session=confirming_evidence,
        )
        assert result is None or result.signal_timestamp == target_prefix[-1].timestamp
        observed.append(result)
    assert observed[-1] is not None
    assert all(result is None for result in observed[:-1])


def test_family_d_prefixes_remain_causal_across_a_cross_symbol_gap() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    (
        target_all,
        confirming_all,
        _vwaps,
        _target_session,
        _confirming_session,
        first_final,
        _second_setup,
        _second_final,
        _full_target,
    ) = _d_two_setup_streams(program)
    gap_index = first_final + 1
    target = tuple(bar for index, bar in enumerate(target_all) if index != gap_index)
    confirming = tuple(confirming_all)
    target_session = _verified_test_session(target)
    confirming_session = _verified_test_session(confirming)

    for decision_timestamp in sorted(
        {bar.timestamp for bar in target} | {bar.timestamp for bar in confirming}
    ):
        target_prefix = tuple(
            bar for bar in target if bar.timestamp <= decision_timestamp
        )
        confirming_prefix = tuple(
            bar for bar in confirming if bar.timestamp <= decision_timestamp
        )
        if not target_prefix or not confirming_prefix:
            continue
        vwaps = tuple(VwapObservation(bar, Decimal("90")) for bar in confirming_prefix)
        signal = family_d_entry_signal(
            program,
            target_prefix,
            confirming_prefix,
            vwaps,
            target_session=target_session,
            confirming_session=confirming_session,
        )
        if signal is not None:
            assert signal.signal_timestamp == target_prefix[-1].timestamp
            assert signal.signal_timestamp == confirming_prefix[-1].timestamp


def test_family_d_same_bar_signal_tie_break_is_stable() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    timestamp = datetime(2023, 1, 3, 16, 0, tzinfo=ZoneInfo("UTC"))
    base = arch151.TrendPullbackSignal(
        program.key,
        program_id(program),
        "SPY",
        _NORMAL_DAY,
        timestamp,
        timestamp,
        Decimal("100"),
        Decimal("2"),
        Decimal("99"),
        Decimal("98"),
        Decimal("100"),
        Decimal("99"),
        "QQQ",
    )
    earlier_setup = replace(
        base,
        setup_timestamp=timestamp - timedelta(minutes=5),
        swing_peak=Decimal("99"),
    )
    later_setup = replace(base, swing_peak=Decimal("200"))
    assert arch151._family_d_same_bar_tie_key(earlier_setup) < (
        arch151._family_d_same_bar_tie_key(later_setup)
    )
    higher_peak = replace(base, swing_peak=Decimal("101"))
    assert arch151._family_d_same_bar_tie_key(higher_peak) < (
        arch151._family_d_same_bar_tie_key(base)
    )
    lower_pullback = replace(base, pullback_low=Decimal("98.5"))
    assert arch151._family_d_same_bar_tie_key(lower_pullback) < (
        arch151._family_d_same_bar_tie_key(base)
    )


def test_sparse_session_evidence_has_no_public_boolean_or_constructor_issuer() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    bars = _flat_aggregate_session(_NORMAL_DAY, program.resolution)
    with pytest.raises(arch151.AuthorizationUnavailableError, match="evaluator-owned"):
        arch151.VerifiedSparseSession(
            symbol="SPY",
            resolution=program.resolution,
            session_date=_NORMAL_DAY,
            bars=bars,
            source_digest="0" * 64,
        )
    with pytest.raises(TypeError):
        arch151.VerifiedSparseSession(
            symbol="SPY",
            resolution=program.resolution,
            session_date=_NORMAL_DAY,
            bars=bars,
            source_digest="0" * 64,
            authenticated=True,
        )
    with pytest.raises(UnavailableIndicatorError, match="published open"):
        ema_series(bars[1:], program.parameters.ema_fast)


def test_causal_execution_policy_and_cost_cases_are_closed_contracts() -> None:
    assert CAUSAL_EXECUTION_POLICY.decision_requires_completed_bar
    assert CAUSAL_EXECUTION_POLICY.entry_requires_immediately_following_minute_open
    assert CAUSAL_EXECUTION_POLICY.missing_entry_expires_without_chase
    assert (
        CAUSAL_EXECUTION_POLICY.ambiguous_bar_rule
        is AmbiguousIntraminuteRule.STOP_PRECEDES_TARGET
    )
    assert (
        CAUSAL_EXECUTION_POLICY.fill_cost_application_rule
        is FillCostApplicationRule.ONCE_PER_ACTUAL_FILL
    )
    assert (
        CAUSAL_EXECUTION_POLICY.target_reference_rule
        is TargetReferenceRule.TARGET_REFERENCE_BEFORE_ADVERSE_COSTS
    )
    assert (
        CAUSAL_EXECUTION_POLICY.final_observed_bar_rule
        is FinalObservedBarRule.NO_RETROSPECTIVE_FINAL_BAR_DESIGNATION
    )
    assert CAUSAL_EXECUTION_POLICY.stop_gap_rule is StopGapRule.OBSERVED_OPEN_IF_THROUGH
    assert (
        CAUSAL_EXECUTION_POLICY.non_gap_stop_touch_rule
        is StopGapRule.OTHERWISE_STOP_REFERENCE
    )
    assert (
        CAUSAL_EXECUTION_POLICY.trailing_rule
        is TrailingActivationRule.NEXT_OBSERVATION_ONLY
    )
    assert (
        CAUSAL_EXECUTION_POLICY.trailing_monotonicity_rule
        is TrailingMonotonicityRule.MONOTONIC_ONLY
    )
    assert CAUSAL_EXECUTION_POLICY.combined_multi_slot_allocation_allowed is False
    assert CAUSAL_EXECUTION_POLICY.maximum_completed_round_trips_per_session == 2
    assert CAUSAL_EXECUTION_POLICY.cooldown_uses_elapsed_wall_clock
    assert CAUSAL_EXECUTION_POLICY.max_hold_uses_elapsed_wall_clock
    assert CAUSAL_EXECUTION_POLICY.failed_liquidation_preserves_complete_evidence
    assert CAUSAL_EXECUTION_POLICY.missing_observation_rules == (
        MissingObservationRule.NO_SYNTHESIS_NO_CARRY_NO_SUBSTITUTION,
        MissingObservationRule.PENDING_EXIT_REMAINS_PENDING,
    )
    with pytest.raises(TypeError):
        CausalExecutionPolicy(maximum_completed_round_trips_per_session=1)
    assert CAUSAL_EXECUTION_POLICY.liquidation_minutes_before_close == 5
    assert CAUSAL_EXECUTION_POLICY.liquidation_uses_first_observed_open_before_close
    assert CAUSAL_EXECUTION_POLICY.no_entries_at_or_after_liquidation
    assert CAUSAL_EXECUTION_POLICY.missing_liquidation_observation_fails_closed
    assert tuple(policy.case for policy in FILL_COST_POLICIES) == (
        FillCostCase.ZERO,
        FillCostCase.BASE,
        FillCostCase.STRESS,
    )
    assert tuple(
        policy.adverse_slippage_bps_per_fill for policy in FILL_COST_POLICIES
    ) == (Decimal("0"), Decimal("2"), Decimal("5"))
    assert all(policy.commission_per_fill == 0 for policy in FILL_COST_POLICIES)


def test_signal_predicates_and_result_types_are_public_api() -> None:
    public_names = (
        "FamilyABreakoutLevel",
        "FamilyAInitialRisk",
        "FamilyAMeasureScope",
        "FamilyASessionMeasure",
        "NoiseBreakoutSignal",
        "OpeningRangeRetestSignal",
        "VwapMeanReversionSignal",
        "TrendPullbackSignal",
        "family_a_entry_signal",
        "family_a_historical_session_measure",
        "family_b_entry_signal",
        "family_c_entry_signal",
        "family_c_reversion_exit",
        "family_d_entry_signal",
        "aggregate_session_vwap",
        "MissingObservationRule",
        "StopGapRule",
        "TrailingActivationRule",
        "TrailingMonotonicityRule",
        "WalkForwardFold",
        "WALK_FORWARD_FOLDS",
        "FoldMetrics",
        "FoldEvaluation",
        "DevelopmentEvaluationBatch",
        "qualify_development",
        "PRIOR_INTRADAY_TRIAL_LEDGER",
        "SELECTION_BIAS_INPUT",
        "FinalCandidateFreeze",
        "freeze_final_candidate_set",
        "authorize_holdout",
        "authorize_extension",
        "SyntheticRankingMaterial",
        "rank_synthetic_candidate_population",
    )
    assert set(public_names) <= set(arch151.__all__)
    assert all(hasattr(arch151, name) for name in public_names)


def test_walk_forward_folds_are_exact_expanding_chronology() -> None:
    assert tuple(
        (
            fold.name,
            fold.calibration_start,
            fold.calibration_end_exclusive,
            fold.scored_start,
            fold.scored_end_exclusive,
            fold.scored_year,
        )
        for fold in arch151.WALK_FORWARD_FOLDS
    ) == tuple(
        (
            f"WF{index}",
            date(2016, 1, 1),
            date(year, 1, 1),
            date(year, 1, 1),
            date(year + 1, 1, 1),
            year,
        )
        for index, year in enumerate((2019, 2020, 2021, 2022, 2023), start=1)
    )
    assert len({fold.fold_id for fold in arch151.WALK_FORWARD_FOLDS}) == 5
    assert all(fold.fold_id.version == 5 for fold in arch151.WALK_FORWARD_FOLDS)
    with pytest.raises(FrozenInstanceError):
        arch151.WALK_FORWARD_FOLDS[0].scored_year = 2020  # type: ignore[misc]


def test_fold_evaluation_batch_is_complete_ordered_and_source_bound() -> None:
    slot = CANONICAL_SLOTS[0]
    batch = _evaluation_batch_for_slot(slot)
    assert batch.records == _evaluation_batch_for_slot(slot).records
    assert len(batch.records) == 15
    assert len({record.evaluation_id for record in batch.records}) == 15
    assert tuple(
        (record.fold, record.economics_case) for record in batch.records
    ) == tuple(
        (fold, economics)
        for fold in arch151.WALK_FORWARD_FOLDS
        for economics in arch151.EVALUATION_ECONOMICS_ORDER
    )
    stress = arch151.aggregate_development_economics(batch, arch151.FillCostCase.STRESS)
    published_sessions = sum(
        len(arch151._published_sessions_for_year(year)) for year in arch151.SCORED_YEARS
    )
    assert stress.average_round_trips_per_year == Decimal(100)
    assert stress.active_session_fraction.quantize(Decimal("0.000001")) == (
        Decimal(500) / Decimal(published_sessions)
    ).quantize(Decimal("0.000001"))
    assert stress.median_round_trips_per_active_session == Decimal(1)
    with pytest.raises(Arch151Error, match="each fold once"):
        arch151.DevelopmentEvaluationBatch(slot.slot_id, batch.records[:-1])
    duplicate = (*batch.records[:1], batch.records[0], *batch.records[2:])
    with pytest.raises(Arch151Error, match="each fold once"):
        arch151.DevelopmentEvaluationBatch(slot.slot_id, duplicate)
    mixed_case = (
        replace(batch.records[0], economics_case=arch151.FillCostCase.ZERO),
        *batch.records[1:],
    )
    with pytest.raises(Arch151Error, match="each fold once"):
        arch151.DevelopmentEvaluationBatch(slot.slot_id, mixed_case)


def test_fold_evaluation_identity_uses_v3_schema_and_namespace() -> None:
    slot = CANONICAL_SLOTS[0]
    batch = _evaluation_batch_for_slot(slot)
    repeated_batch = _evaluation_batch_for_slot(slot)
    record = batch.records[0]
    material = {
        "schema": "arch151-fold-evaluation/v3",
        "semantic_contract_version": arch151.SEMANTIC_CONTRACT_VERSION,
        "slot_id": str(record.slot_id),
        "program_id": str(record.program_id),
        "symbol": record.symbol,
        "fold_id": str(record.fold.fold_id),
        "economics_case": record.economics_case.value,
        "metrics": arch151._fold_metrics_material(record.metrics),
    }
    expected_namespace = uuid5(arch151._ROOT_NAMESPACE, "fold-evaluation/v3")
    expected_id = uuid5(
        expected_namespace,
        arch151._canonical_json(material).decode("utf-8"),
    )
    current_metrics = dict(arch151._fold_metrics_material(record.metrics))
    v2_metrics = dict(current_metrics)
    for key in (
        "net_positive_trade_pnl",
        "net_negative_trade_pnl",
        "pre_cost_profit_factor",
    ):
        v2_metrics.pop(key)
    v2_metrics["profit_factor"] = (
        record.metrics.pre_cost_profit_factor.canonical_material()
    )
    prior_v2_id = uuid5(
        uuid5(arch151._ROOT_NAMESPACE, "fold-evaluation/v2"),
        arch151._canonical_json(
            {
                **material,
                "schema": "arch151-fold-evaluation/v2",
                "metrics": v2_metrics,
            }
        ).decode("utf-8"),
    )
    v1_metrics = dict(v2_metrics)
    v1_metrics.pop("profit_factor")
    prior_v1_id = uuid5(
        uuid5(arch151._ROOT_NAMESPACE, "fold-evaluation/v1"),
        arch151._canonical_json(
            {
                **material,
                "schema": "arch151-fold-evaluation/v1",
                "metrics": v1_metrics,
            }
        ).decode("utf-8"),
    )

    assert arch151._FOLD_EVALUATION_SCHEMA == "arch151-fold-evaluation/v3"
    assert arch151._EVALUATION_NAMESPACE == expected_namespace
    assert record.evaluation_id == expected_id
    assert record.evaluation_id == repeated_batch.records[0].evaluation_id
    assert record.evaluation_id != prior_v2_id
    assert record.evaluation_id != prior_v1_id
    assert batch.batch_digest == repeated_batch.batch_digest
    qualification = arch151.qualify_development(batch)
    repeated_qualification = arch151.qualify_development(repeated_batch)
    assert qualification.qualification_id == repeated_qualification.qualification_id
    with pytest.raises(UnsupportedProgramError, match="canonical slot"):
        replace(batch.records[0], symbol="QQQ")
    with pytest.raises(Arch151Error, match="chronology"):
        replace(
            arch151.WALK_FORWARD_FOLDS[0],
            calibration_end_exclusive=date(2018, 1, 1),
        )
    altered_dates = replace(
        batch.records[0].metrics,
        session_dates=(
            date(2018, 12, 31),
            *batch.records[0].metrics.session_dates[1:],
        ),
    )
    with pytest.raises(Arch151Error, match="full published XNYS"):
        replace(batch.records[0], metrics=altered_dates)
    two_entry_slot = next(
        slot for slot in CANONICAL_SLOTS if slot.program_key is ProgramKey.C5_01
    )
    two_entry_record = _evaluation_batch_for_slot(two_entry_slot).records[0]
    over_cap_counts = (3, *two_entry_record.metrics.round_trips_by_session[1:])
    over_cap_metrics = replace(
        two_entry_record.metrics, round_trips_by_session=over_cap_counts
    )
    with pytest.raises(Arch151Error, match="per-session entry cap"):
        replace(two_entry_record, metrics=over_cap_metrics)


def test_qualification_identity_uses_v3_and_preserves_v2_predecessor_schema() -> None:
    batch = _evaluation_batch_for_slot(CANONICAL_SLOTS[0])
    qualification = arch151.qualify_development(batch)
    material = {
        "schema": "arch151-development-qualification/v3",
        "batch_digest": batch.batch_digest,
        "economics_case": arch151.FillCostCase.STRESS.value,
        "economic_rejections": [
            item.value for item in qualification.economic_rejection_reasons
        ],
        "selection_bias_status": qualification.selection_bias_status.value,
        "selection_bias_evidence_digest": None,
        "selection_bias_rejections": [
            item.value
            for item in qualification.rejection_reasons[
                len(qualification.economic_rejection_reasons) :
            ]
        ],
    }
    expected_namespace = uuid5(arch151._ROOT_NAMESPACE, "development-qualification/v3")
    expected_id = uuid5(
        expected_namespace,
        arch151._canonical_json(material).decode("utf-8"),
    )
    predecessor_id = uuid5(
        uuid5(arch151._ROOT_NAMESPACE, "development-qualification/v2"),
        arch151._canonical_json(
            {**material, "schema": "arch151-development-qualification/v2"}
        ).decode("utf-8"),
    )

    assert arch151._QUALIFICATION_SCHEMA == "arch151-development-qualification/v3"
    assert arch151._QUALIFICATION_NAMESPACE == expected_namespace
    assert qualification.qualification_id == expected_id
    assert qualification.qualification_id != predecessor_id


def test_fold_metrics_reject_invalid_and_preserve_zero_trade_undefined_pf() -> None:
    dates = arch151._published_sessions_for_year(2019)
    zeros = (Decimal(0),) * len(dates)
    trips = (0,) * len(dates)
    with pytest.raises(ValueError, match="finite"):
        arch151.FoldMetrics(
            dates,
            (Decimal("NaN"), *zeros[1:]),
            trips,
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal("0.25"),
        )
    zero_trade = arch151.FoldMetrics(
        dates, zeros, trips, Decimal(0), Decimal(0), Decimal(0), Decimal(0), Decimal(0)
    )
    assert zero_trade.profit_factor.state is arch151.ProfitFactorState.UNDEFINED
    with pytest.raises(Arch151Error, match="invalid gross or realized net"):
        arch151.FoldMetrics(
            dates,
            zeros,
            trips,
            Decimal(-1),
            Decimal(1),
            Decimal(0),
            Decimal(0),
            Decimal(0),
        )
    with pytest.raises(ValueError, match="finite"):
        arch151.FoldMetrics(
            dates,
            zeros,
            trips,
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal("NaN"),
        )
    with pytest.raises(ValueError, match="turnover cannot be negative"):
        arch151.FoldMetrics(
            dates,
            zeros,
            trips,
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal("-0.01"),
        )
    with pytest.raises(Arch151Error, match="aligned full-session"):
        arch151.FoldMetrics(
            dates,
            zeros[:-1],
            trips,
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal("0.25"),
        )


def test_invalid_fold_evidence_fails_before_undefined_pf_qualification() -> None:
    slot = CANONICAL_SLOTS[0]
    batch = _evaluation_batch_for_slot(slot)
    metrics = batch.records[0].metrics
    with pytest.raises(Arch151Error, match="invalid gross or realized net"):
        replace(metrics, gross_positive_trade_pnl=Decimal("-1"))

    zero_profiles = {
        year: {
            "return_events": (),
            "active_sessions": 0,
            "gross_positive": Decimal(0),
            "gross_negative": Decimal(0),
            "annual_turnover": Decimal(0),
        }
        for year in arch151.SCORED_YEARS
    }
    valid_undefined_batch = _evaluation_batch_for_slot(slot, zero_profiles)
    qualification = arch151.qualify_development(valid_undefined_batch)
    assert (
        QualificationRejection.STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE
        in qualification.economic_rejection_reasons
    )


def test_development_aggregate_uses_summed_pf_and_chained_drawdown() -> None:
    slot = CANONICAL_SLOTS[0]
    profiles = {
        2019: {
            "return_events": ((250, Decimal("0.20")), (251, Decimal("-0.15"))),
            "gross_positive": Decimal("2"),
            "gross_negative": Decimal("1"),
            "net_positive": Decimal("2"),
            "net_negative": Decimal(0),
            "annual_turnover": Decimal("0.10"),
        },
        2020: {
            "return_events": ((0, Decimal("-0.10")), (251, Decimal("0.20"))),
            "gross_positive": Decimal("0.1"),
            "gross_negative": Decimal("10"),
            "net_positive": Decimal(0),
            "net_negative": Decimal("1"),
            "annual_turnover": Decimal("0.20"),
        },
        2021: {"net_positive": Decimal(0), "net_negative": Decimal(0)},
        2022: {"net_positive": Decimal(0), "net_negative": Decimal(0)},
        2023: {"net_positive": Decimal(0), "net_negative": Decimal(0)},
    }
    batch = _evaluation_batch_for_slot(slot, profiles)
    aggregate = arch151.aggregate_development_economics(
        batch, arch151.FillCostCase.STRESS
    )
    assert aggregate.profit_factor.state is arch151.ProfitFactorState.FINITE
    assert aggregate.profit_factor.finite_value == Decimal(2)
    assert aggregate.pre_cost_profit_factor.state is arch151.ProfitFactorState.FINITE
    assert aggregate.pre_cost_profit_factor.finite_value.quantize(
        Decimal("0.000001")
    ) == Decimal("0.578571")
    assert aggregate.max_drawdown > Decimal("0.23")
    assert aggregate.max_drawdown > max(
        record.metrics.max_drawdown
        for record in batch.records
        if record.economics_case is arch151.FillCostCase.STRESS
    )
    assert aggregate.turnover == Decimal("0.21")


def test_cost_case_pf_uses_realized_net_totals_for_annual_and_aggregate_gates() -> None:
    slot = CANONICAL_SLOTS[0]
    profiles = {
        year: {
            "gross_positive": Decimal("0.04"),
            "gross_negative": Decimal("0.01"),
            "annual_turnover": Decimal("0.1"),
            "economics_cases": {
                arch151.FillCostCase.ZERO: {
                    "return_events": (
                        (
                            len(arch151._published_sessions_for_year(year)) - 1,
                            Decimal("0.02"),
                        ),
                    ),
                    "net_positive": Decimal("0.03"),
                    "net_negative": Decimal("0.01"),
                },
                arch151.FillCostCase.BASE: {
                    "return_events": (
                        (
                            len(arch151._published_sessions_for_year(year)) - 1,
                            Decimal("0.01"),
                        ),
                    ),
                    "net_positive": Decimal("0.02"),
                    "net_negative": Decimal("0.01"),
                },
                arch151.FillCostCase.STRESS: {
                    "return_events": (
                        (
                            len(arch151._published_sessions_for_year(year)) - 1,
                            Decimal("-0.001"),
                        ),
                    ),
                    "net_positive": Decimal("0.009"),
                    "net_negative": Decimal("0.01"),
                },
            },
        }
        for year in arch151.SCORED_YEARS
    }
    batch = _evaluation_batch_for_slot(slot, profiles)
    zero = arch151.aggregate_development_economics(batch, arch151.FillCostCase.ZERO)
    base = arch151.aggregate_development_economics(batch, arch151.FillCostCase.BASE)
    stress = arch151.aggregate_development_economics(batch, arch151.FillCostCase.STRESS)

    assert zero.profit_factor.finite_value == Decimal(3)
    assert base.profit_factor.finite_value == Decimal(2)
    assert stress.profit_factor.finite_value == Decimal("0.9")
    assert stress.pre_cost_profit_factor.finite_value == Decimal(4)
    assert stress.profitable_scored_years == 0
    rejected = arch151.qualify_development(batch)
    assert (
        arch151.QualificationRejection.STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE
        in rejected.economic_rejection_reasons
    )


def test_profit_factor_preserves_zero_trade_win_loss_and_mixed_states() -> None:
    dates = arch151._published_sessions_for_year(2019)
    zeros = (Decimal(0),) * len(dates)
    no_trades = (0,) * len(dates)
    zero_trade = arch151.FoldMetrics(
        dates,
        zeros,
        no_trades,
        Decimal(0),
        Decimal(0),
        Decimal(0),
        Decimal(0),
        Decimal(0),
    )
    all_wins = arch151.FoldMetrics(
        dates,
        (Decimal("0.01"), *zeros[1:]),
        (1, *no_trades[1:]),
        Decimal("2"),
        Decimal(0),
        Decimal("2"),
        Decimal(0),
        Decimal("0.1"),
    )
    all_losses = arch151.FoldMetrics(
        dates,
        (Decimal("-0.01"), *zeros[1:]),
        (1, *no_trades[1:]),
        Decimal(0),
        Decimal("2"),
        Decimal(0),
        Decimal("2"),
        Decimal("0.1"),
    )
    mixed = arch151.ProfitFactor.from_totals(Decimal("3"), Decimal("2"))

    assert zero_trade.profit_factor.state is arch151.ProfitFactorState.UNDEFINED
    assert zero_trade.profit_factor.arch150_report_value() is None
    zero_gross_trade = arch151.FoldMetrics(
        dates,
        (Decimal("-0.01"), *zeros[1:]),
        (1, *no_trades[1:]),
        Decimal(0),
        Decimal(0),
        Decimal(0),
        Decimal("0.01"),
        Decimal("0.1"),
    )
    assert zero_gross_trade.profit_factor.state is arch151.ProfitFactorState.FINITE
    assert zero_gross_trade.profit_factor.finite_value == Decimal(0)
    assert (
        zero_gross_trade.pre_cost_profit_factor.state
        is arch151.ProfitFactorState.UNDEFINED
    )
    assert zero_gross_trade.completed_round_trips == 1
    assert all_wins.profit_factor.state is arch151.ProfitFactorState.POSITIVE_INFINITY
    assert all_wins.profit_factor.arch150_report_value() == "Infinity"
    assert all_wins.profit_factor.exceeds_one
    assert all_losses.profit_factor.state is arch151.ProfitFactorState.FINITE
    assert all_losses.profit_factor.finite_value == Decimal(0)
    assert not all_losses.profit_factor.exceeds_one
    assert mixed.state is arch151.ProfitFactorState.FINITE
    assert mixed.finite_value == Decimal("1.5")
    with pytest.raises(Arch151Error, match="invalid trade P&L"):
        arch151.ProfitFactor.from_totals(Decimal("-1"), Decimal("0"))
    with pytest.raises(Arch151Error, match="zero-trade fold"):
        arch151.FoldMetrics(
            dates,
            zeros,
            no_trades,
            Decimal("1"),
            Decimal(0),
            Decimal("1"),
            Decimal(0),
            Decimal(0),
        )


def test_undefined_and_positive_infinity_aggregate_pf_are_explicit() -> None:
    slot = CANONICAL_SLOTS[0]
    zero_profiles = {
        year: {
            "return_events": (),
            "active_sessions": 0,
            "gross_positive": Decimal(0),
            "gross_negative": Decimal(0),
            "annual_turnover": Decimal(0),
        }
        for year in arch151.SCORED_YEARS
    }
    zero_batch = _evaluation_batch_for_slot(slot, zero_profiles)
    zero_aggregate = arch151.aggregate_development_economics(
        zero_batch, arch151.FillCostCase.STRESS
    )
    zero_qualification = arch151.qualify_development(zero_batch)
    assert zero_aggregate.profit_factor.state is arch151.ProfitFactorState.UNDEFINED
    assert (
        QualificationRejection.STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE
        in zero_qualification.economic_rejection_reasons
    )

    undefined_trade_profiles = {}
    for year in arch151.SCORED_YEARS:
        session_count = len(arch151._published_sessions_for_year(year))
        undefined_trade_profiles[year] = {
            "return_events": ((session_count - 1, Decimal("-0.01")),),
            "active_sessions": 1,
            "gross_positive": Decimal(0),
            "gross_negative": Decimal(0),
            "annual_turnover": Decimal("0.1"),
        }
    undefined_trade_batch = _evaluation_batch_for_slot(slot, undefined_trade_profiles)
    undefined_trade_aggregate = arch151.aggregate_development_economics(
        undefined_trade_batch, arch151.FillCostCase.STRESS
    )
    assert (
        undefined_trade_aggregate.profit_factor.state
        is arch151.ProfitFactorState.UNDEFINED
    )
    assert (
        QualificationRejection.STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE
        in arch151.qualify_development(undefined_trade_batch).economic_rejection_reasons
    )

    winner_profiles = {
        year: {
            "active_sessions": 1,
            "gross_positive": Decimal("2"),
            "gross_negative": Decimal(0),
        }
        for year in arch151.SCORED_YEARS
    }
    winner_batch = _evaluation_batch_for_slot(slot, winner_profiles)
    winner_aggregate = arch151.aggregate_development_economics(
        winner_batch, arch151.FillCostCase.STRESS
    )
    assert (
        winner_aggregate.profit_factor.state
        is arch151.ProfitFactorState.POSITIVE_INFINITY
    )
    assert winner_aggregate.profitable_scored_years == 5


def test_profit_factor_ranking_orders_infinity_finite_and_undefined() -> None:
    common = (
        Decimal("0.95"),
        Decimal("-0.1"),
    )
    suffix = (Decimal("0.5"), Decimal("0.1"), Decimal("0.25"), UUID(int=1))
    infinite = arch151._ranking_key(
        *common,
        arch151.ProfitFactor.from_totals(Decimal(1), Decimal(0)),
        *suffix,
    )
    finite = arch151._ranking_key(
        *common,
        arch151.ProfitFactor.from_totals(Decimal(1), Decimal(2)),
        *suffix,
    )
    undefined = arch151._ranking_key(
        *common,
        arch151.ProfitFactor.from_totals(Decimal(0), Decimal(0)),
        *suffix,
    )
    assert infinite < finite < undefined


def test_development_qualification_rejections_are_independently_testable() -> None:
    base = arch151.DevelopmentAggregate(
        CANONICAL_SLOTS[0].slot_id,
        arch151.FillCostCase.STRESS,
        Decimal("0.10"),
        Decimal("1.5"),
        Decimal("1.5"),
        5,
        5,
        Decimal("-0.05"),
        Decimal("0.10"),
        Decimal(100),
        Decimal("0.40"),
        Decimal(1),
        Decimal("0.5"),
        Decimal("0.25"),
    )
    cases = (
        (
            {"net_return": Decimal(0)},
            QualificationRejection.STRESS_NET_RETURN_NOT_POSITIVE,
        ),
        (
            {"profit_factor": Decimal(1)},
            QualificationRejection.STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE,
        ),
        (
            {"positive_scored_years": 3},
            QualificationRejection.FEWER_THAN_FOUR_POSITIVE_YEARS,
        ),
        (
            {"profitable_scored_years": 3},
            QualificationRejection.FEWER_THAN_FOUR_PROFITABLE_YEARS,
        ),
        (
            {"worst_scored_year_return": Decimal("-0.10")},
            QualificationRejection.WORST_YEAR_RETURN_AT_OR_BELOW_NEGATIVE_TEN_PERCENT,
        ),
        (
            {"max_drawdown": Decimal("0.200001")},
            QualificationRejection.MAXIMUM_DRAWDOWN_ABOVE_TWENTY_PERCENT,
        ),
        (
            {"average_round_trips_per_year": Decimal("99.99")},
            QualificationRejection.AVERAGE_ROUND_TRIPS_PER_YEAR_BELOW_100,
        ),
        (
            {"active_session_fraction": Decimal("0.349999")},
            QualificationRejection.ACTIVE_SESSION_FRACTION_BELOW_35_PERCENT,
        ),
        (
            {"median_round_trips_per_active_session": Decimal("2.000001")},
            QualificationRejection.MEDIAN_TRADES_PER_ACTIVE_SESSION_ABOVE_TWO,
        ),
    )
    for updates, expected_reason in cases:
        assert arch151._qualification_rejections(replace(base, **updates)) == (
            expected_reason,
        )
    assert arch151._qualification_rejections(replace(base, sharpe=None)) == ()


def test_qualification_uses_stress_and_fails_closed_without_dsr() -> None:
    batch = _evaluation_batch_for_slot(CANONICAL_SLOTS[0])
    aggregate = arch151.aggregate_development_economics(
        batch, arch151.FillCostCase.STRESS
    )
    qualification = arch151.qualify_development(batch)
    assert aggregate.economics_case is arch151.FillCostCase.STRESS
    assert qualification.economically_qualified
    assert not qualification.qualified
    assert qualification.rejection_reasons == (
        QualificationRejection.SELECTION_BIAS_EVIDENCE_UNAVAILABLE,
    )
    assert (
        qualification.selection_bias_status
        is arch151.SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    with pytest.raises(TypeError):
        arch151.qualify_development(batch, selection_bias_probability=Decimal("0.99"))


def test_zero_economics_are_diagnostic_and_never_replace_stress_qualification() -> None:
    original = _evaluation_batch_for_slot(CANONICAL_SLOTS[0])
    records = []
    for record in original.records:
        if record.economics_case is arch151.FillCostCase.STRESS:
            returns = (Decimal(0),) * (len(record.metrics.session_net_returns) - 1) + (
                Decimal("-0.02"),
            )
            record = replace(
                record,
                metrics=replace(record.metrics, session_net_returns=returns),
            )
        records.append(record)
    batch = arch151.DevelopmentEvaluationBatch(original.slot_id, tuple(records))
    zero = arch151.aggregate_development_economics(batch, arch151.FillCostCase.ZERO)
    stress = arch151.aggregate_development_economics(batch, arch151.FillCostCase.STRESS)
    qualification = arch151.qualify_development(batch)
    assert zero.net_return > 0
    assert stress.net_return < 0
    assert (
        QualificationRejection.STRESS_NET_RETURN_NOT_POSITIVE
        in qualification.economic_rejection_reasons
    )
    assert not qualification.economically_qualified


def test_prior_trial_ledger_is_exact_deduplicated_and_effective_count_is_64() -> None:
    ledger = arch151.PRIOR_INTRADAY_TRIAL_LEDGER
    assert ledger.documented_prior_intraday_trials == 29
    assert tuple(entry.distinct_trial_count for entry in ledger.entries) == (4, 1, 24)
    churn, late_drive, g1 = ledger.entries
    assert churn.campaign is arch151.PriorTrialCampaignKey.ARCH148_CHURN
    assert churn.report_id == UUID("19dcca18-7080-541d-9864-d730c68471e0")
    assert churn.report_sha256 == (
        "5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8"
    )
    assert churn.source_commit == "be30617594e197f372438dba19d325fd8737b850"
    assert "CONTROL" in churn.deduplication_rationale
    assert "repeated observations" in churn.deduplication_rationale
    assert churn.hypothesis_keys == (
        "CONTROL",
        "OPPOSITE_CONFIRMATION_EXIT",
        "OPPOSITE_EXIT_COOLDOWN_15M",
        "OPPOSITE_EXIT_COOLDOWN_30M",
    )
    assert (
        late_drive.campaign is arch151.PriorTrialCampaignKey.ARCH148_LATE_OPENING_DRIVE
    )
    assert late_drive.report_id == UUID("42355698-d57e-5f6b-8347-6a752e5b4572")
    assert late_drive.report_sha256 == (
        "e6349ea0c7f1e1b09f165bede8c93b68fb6bc6168940fda0ae2270bf9079f19b"
    )
    assert late_drive.source_commit == "370ebccf52a61e91979bc61efaac0001dd563be6"
    assert late_drive.hypothesis_keys == ("OPENING_DRIVE_LATE_CAPTURE_V1",)
    assert g1.campaign is arch151.PriorTrialCampaignKey.ARCH150_G1
    assert g1.report_id == UUID("22f752aa-5dc1-5e42-af29-1c7e2f921175")
    assert g1.report_sha256 == (
        "d3b637f410b9e8bf05d352e50efea95721151543ec6308fc270c804b5aa372c7"
    )
    assert g1.source_commit == "4df84db43833edc0d1b644e2116acdfdccc5897b"
    assert g1.manifest_id == UUID("7e179cbc-18cf-59ce-9116-899cc876ece0")
    assert tuple(str(value) for value in g1.slot_ids) == (
        "69e38e92-3748-53e4-a24f-a700c04386c3",
        "05b34c9f-4aa3-5b32-99ee-e76de7d30682",
        "612e820a-25c6-56eb-ac95-fbf943352842",
        "e771607a-3c78-5bb9-970a-7e0bb34da4bd",
        "fae4d0b5-348d-5ba4-a7ea-e2d75512a09d",
        "3e4b5053-b17e-582b-851e-c8c9927e524a",
        "4fdc7fe8-6845-5e1c-8aa8-a3d679f77aa3",
        "03532ff1-5c9a-5772-8d07-f905560c7800",
        "ad36a3fb-90ce-552a-81a6-a8791bba47d0",
        "5646b3cb-0bfb-54cf-8131-d3237cabfcd2",
        "59db62c4-3d17-5e73-9f94-20e516b25b5a",
        "11e66a27-c0a7-516e-b810-37ef5c4bcb78",
        "db72c3a0-3291-5eec-b6d3-0d8546b8cd75",
        "a5a4d9cb-c97f-5e71-b2b5-44137eb6e637",
        "30b0716b-4949-5bd6-8ab8-c582c8e5d3d6",
        "997cc95c-5e7c-5252-85bf-3a76d705ca4e",
        "5d19627f-25ec-5e76-961e-3d6ac86224df",
        "7aa841e8-0e9f-5eef-89e1-4f3f377a1fc6",
        "f55fc548-6597-5d23-a7f6-1152879f76d9",
        "63c665ab-8fc7-5feb-9b20-cdb25f702685",
        "1190874c-23af-503f-8b2f-4be6c8a1da85",
        "3d79db4f-f1a0-56da-a5fd-4438c6689fdc",
        "b80e9148-1620-5f47-9a8e-a2dc89468efd",
        "c0ea9f0b-8dc4-573b-932e-4777d1817dcb",
    )
    selection = arch151.SELECTION_BIAS_INPUT
    assert selection.documented_prior_intraday_trials == 29
    assert selection.current_search_slots == 32
    assert selection.minimum_effective_trial_count == 64
    assert selection.effective_trial_count == max(64, 32 + 29) == 64
    assert selection.required_probability == Decimal("0.95")
    assert selection.probability is None
    assert selection.status is arch151.SelectionBiasStatus.DSR_COMPUTATION_REQUIRED
    assert selection.input_id.version == 5
    assert len(selection.fingerprint) == 64
    with pytest.raises(Arch151Error, match="source-owned"):
        arch151.PriorTrialLedger()
    with pytest.raises(Arch151Error, match="source-owned"):
        arch151.SelectionBiasInputContract()
    with pytest.raises(Arch151Error, match="keys contain duplicates"):
        replace(churn, hypothesis_keys=("CONTROL",) * 4)


def test_selection_probability_threshold_is_diagnostic_and_decimal_only() -> None:
    assert arch151._selection_bias_probability_meets_threshold(Decimal("0.95"))
    assert not arch151._selection_bias_probability_meets_threshold(Decimal("0.949999"))
    with pytest.raises(TypeError, match="must be a Decimal"):
        arch151._selection_bias_probability_meets_threshold(0.99)  # type: ignore[arg-type]


def test_dsr_reference_values_and_complete_population_freeze_are_deterministic() -> (
    None
):
    assert arch151._normal_cdf(Decimal("1.96")) == Decimal(
        "0.975002104851779565863415730959162809977500220938116608914283"
    )
    assert arch151._normal_quantile(Decimal("0.984375")) == Decimal(
        "2.15387469406145621296370420514771444541699825530527270617670"
    )

    batches = _dsr_evaluation_population()
    calculation = arch151.compute_selection_bias_evidence(batches)
    assert calculation.status is arch151.SelectionBiasStatus.DSR_VERIFIED
    assert calculation.effective_trial_count == 64
    assert len(calculation.evidence) == len(CANONICAL_SLOTS) == 32
    assert len(calculation.trial_diagnostics) == 32
    assert calculation.affected_trial_slot_ids == ()
    assert (
        calculation.descriptive_economic_order
        == arch151.rank_descriptive_economic_population(batches)
    )
    assert set(calculation.descriptive_economic_order) == {
        slot.slot_id for slot in CANONICAL_SLOTS
    }
    assert all(
        item.status is arch151.DsrTrialStatus.SHARPE_AVAILABLE
        and item.unavailable_reason is None
        for item in calculation.trial_diagnostics
    )
    assert tuple(item.candidate_slot_id for item in calculation.evidence) == tuple(
        slot.slot_id for slot in CANONICAL_SLOTS
    )
    assert all(item.observation_count == 1_258 for item in calculation.evidence)
    assert all(
        item.population_digest == calculation.population_digest
        for item in calculation.evidence
    )
    assert calculation.evidence[0].probability >= Decimal("0.95")
    assert all(item.probability < Decimal("0.95") for item in calculation.evidence[1:])
    assert arch151._DSR_CALCULATION_NAMESPACE == uuid5(
        arch151._ROOT_NAMESPACE, "dsr-population-calculation/v2"
    )
    predecessor_material = {
        "schema": "arch151-dsr-population-calculation/v1",
        "population_digest": calculation.population_digest,
        "status": arch151.SelectionBiasStatus.DSR_VERIFIED.value,
        "evidence_ids": [str(item.evidence_id) for item in calculation.evidence],
    }
    predecessor_id = uuid5(
        uuid5(arch151._ROOT_NAMESPACE, "dsr-population-calculation/v1"),
        arch151._canonical_json(predecessor_material).decode("utf-8"),
    )
    assert calculation.calculation_id != predecessor_id
    with pytest.raises(Arch151Error, match="identity does not match canonical inputs"):
        replace(calculation, calculation_id=UUID(int=17))
    assert (
        arch151.compute_selection_bias_evidence(batches).calculation_id
        == calculation.calculation_id
    )

    ranked = arch151.rank_verified_candidate_population(batches, calculation)
    assert len(ranked) == len(set(ranked)) == 32
    assert set(ranked) == {slot.slot_id for slot in CANONICAL_SLOTS}
    assert ranked[0] == CANONICAL_SLOTS[0].slot_id
    qualification = arch151.qualify_development(batches[0], calculation.evidence[0])
    assert qualification.qualified
    rejected = arch151.qualify_development(batches[1], calculation.evidence[1])
    assert not rejected.economically_qualified
    assert (
        QualificationRejection.SELECTION_BIAS_PROBABILITY_BELOW_THRESHOLD
        in rejected.rejection_reasons
    )
    assert CANONICAL_SLOTS[1].slot_id in ranked

    freeze = arch151.freeze_final_candidate_set(
        batches, _selection_bias_calculation=calculation
    )
    assert freeze.status is arch151.FinalFreezeStatus.ONE_CANDIDATE_FROZEN
    assert freeze.candidate_slot_id == CANONICAL_SLOTS[0].slot_id
    assert CANONICAL_SLOTS[1].slot_id not in freeze.economically_qualified_slot_ids
    assert freeze.ranking_order == ranked
    assert freeze.selection_bias_calculation_id == calculation.calculation_id
    with pytest.raises(arch151.AuthorizationUnavailableError, match="authenticated"):
        arch151.authorize_holdout(freeze)


def test_bailey_lopez_de_prado_paper_example_matches_eq1_and_eq2() -> None:
    # Bailey & López de Prado (2014), The Deflated Sharpe Ratio, Eqs. 1–2:
    # https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
    with localcontext() as context:
        context.prec = 60
        sessions_per_year = Decimal(250)
        annualized_trial_variance = Decimal("0.5")
        trial_count = Decimal(100)
        expected_trial_sharpe = Decimal("2.5") / sessions_per_year.sqrt()
        expected_max_standard_normal = (
            Decimal(1) - Decimal("0.577215664901532860606512090082402431")
        ) * arch151._normal_quantile(Decimal(1) - Decimal(1) / trial_count) + Decimal(
            "0.577215664901532860606512090082402431"
        ) * arch151._normal_quantile(
            Decimal(1) - Decimal(1) / (trial_count * Decimal(1).exp())
        )
        expected_maximum = (
            annualized_trial_variance / sessions_per_year
        ).sqrt() * expected_max_standard_normal
        variance = (
            Decimal(1)
            - Decimal(-3) * expected_trial_sharpe
            + ((Decimal(10) - Decimal(1)) / Decimal(4)) * expected_trial_sharpe**2
        )
        dsr_probability = arch151._normal_cdf(
            (expected_trial_sharpe - expected_maximum)
            * Decimal(1249).sqrt()
            / variance.sqrt()
        )

    assert abs(expected_maximum - Decimal("0.1132")) < Decimal("0.0001")
    assert abs(dsr_probability - Decimal("0.9004")) < Decimal("0.0002")


def test_dsr_unavailable_keeps_all_slots_and_never_drops_undefined_trial() -> None:
    batches = list(_dsr_evaluation_population())
    first = batches[0]
    changed = tuple(
        replace(
            record,
            metrics=replace(
                record.metrics,
                session_net_returns=(Decimal(0),)
                * len(record.metrics.session_net_returns),
            ),
        )
        if record.economics_case is FillCostCase.STRESS
        else record
        for record in first.records
    )
    batches[0] = arch151.DevelopmentEvaluationBatch(first.slot_id, changed)
    calculation = arch151.compute_selection_bias_evidence(tuple(batches))
    assert (
        calculation.status
        is arch151.SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    assert (
        calculation.unavailable_reason
        is arch151.DsrUnavailableReason.UNDEFINED_TRIAL_SHARPE
    )
    assert calculation.evidence == ()
    assert calculation.effective_trial_count == max(64, 32 + 29) == 64
    assert tuple(
        item.candidate_slot_id for item in calculation.trial_diagnostics
    ) == tuple(slot.slot_id for slot in CANONICAL_SLOTS)
    assert calculation.affected_trial_slot_ids == (CANONICAL_SLOTS[0].slot_id,)
    assert calculation.trial_diagnostics[0].status is (
        arch151.DsrTrialStatus.SHARPE_UNAVAILABLE
    )
    assert (
        calculation.trial_diagnostics[0].unavailable_reason
        is arch151.DsrUnavailableReason.UNDEFINED_TRIAL_SHARPE
    )
    assert all(
        item.status is arch151.DsrTrialStatus.SHARPE_AVAILABLE
        for item in calculation.trial_diagnostics[1:]
    )
    assert len(calculation.descriptive_economic_order) == 32
    assert set(calculation.descriptive_economic_order) == {
        slot.slot_id for slot in CANONICAL_SLOTS
    }
    freeze = arch151.freeze_final_candidate_set(
        tuple(batches), _selection_bias_calculation=calculation
    )
    assert (
        freeze.status
        is arch151.FinalFreezeStatus.ZERO_CANDIDATES_STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    assert freeze.candidate_slot_id is None
    assert freeze.ranking_order == ()
    with pytest.raises(Arch151Error, match="identity does not match canonical inputs"):
        replace(calculation, calculation_id=UUID(int=18))
    with pytest.raises(Arch151Error, match="all 32 complete canonical"):
        arch151.compute_selection_bias_evidence(tuple(batches[1:]))


def test_dsr_invalid_moments_and_degenerate_formula_fail_closed(monkeypatch) -> None:
    batches = _dsr_evaluation_population()
    original_statistics = arch151._trial_return_statistics

    def one_invalid_trial(returns):
        if returns[0] == Decimal("0.0011"):
            return arch151.DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
        return original_statistics(returns)

    monkeypatch.setattr(arch151, "_trial_return_statistics", one_invalid_trial)
    invalid = arch151.compute_selection_bias_evidence(batches)
    assert (
        invalid.status is arch151.SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    assert (
        invalid.unavailable_reason
        is arch151.DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
    )
    assert invalid.evidence == ()
    assert invalid.affected_trial_slot_ids == (CANONICAL_SLOTS[0].slot_id,)
    assert invalid.trial_diagnostics[0].unavailable_reason is (
        arch151.DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
    )
    assert all(
        item.status is arch151.DsrTrialStatus.SHARPE_AVAILABLE
        for item in invalid.trial_diagnostics[1:]
    )

    def degenerate_statistics(returns):
        if returns[0] == Decimal("0.0011"):
            return Decimal(1), Decimal(10), Decimal(1), Decimal(1)
        return Decimal(2), Decimal(0), Decimal(3), Decimal(1)

    monkeypatch.setattr(arch151, "_trial_return_statistics", degenerate_statistics)
    degenerate = arch151.compute_selection_bias_evidence(batches)
    assert (
        degenerate.status
        is arch151.SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    assert (
        degenerate.unavailable_reason
        is arch151.DsrUnavailableReason.DEGENERATE_DSR_VARIANCE
    )
    assert degenerate.evidence == ()
    assert degenerate.affected_trial_slot_ids == (CANONICAL_SLOTS[0].slot_id,)
    assert degenerate.trial_diagnostics[0].daily_sharpe == Decimal(1)
    assert degenerate.trial_diagnostics[0].unavailable_reason is (
        arch151.DsrUnavailableReason.DEGENERATE_DSR_VARIANCE
    )


def test_dsr_mixed_inactive_and_invalid_candidates_preserve_all_slots(
    monkeypatch,
) -> None:
    batches = list(_dsr_evaluation_population())
    first = batches[0]
    zero_return_records = tuple(
        replace(
            record,
            metrics=replace(
                record.metrics,
                session_net_returns=(Decimal(0),)
                * len(record.metrics.session_net_returns),
                round_trips_by_session=(0,)
                * len(record.metrics.round_trips_by_session),
                gross_positive_trade_pnl=Decimal(0),
                gross_negative_trade_pnl=Decimal(0),
                net_positive_trade_pnl=Decimal(0),
                net_negative_trade_pnl=Decimal(0),
                annual_turnover=Decimal(0),
            ),
        )
        for record in first.records
    )
    batches[0] = arch151.DevelopmentEvaluationBatch(first.slot_id, zero_return_records)
    original_statistics = arch151._trial_return_statistics

    def invalidate_second_trial(returns):
        if returns[0] == Decimal("-0.0011"):
            return arch151.DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
        return original_statistics(returns)

    monkeypatch.setattr(arch151, "_trial_return_statistics", invalidate_second_trial)
    calculation = arch151.compute_selection_bias_evidence(tuple(batches))

    assert calculation.effective_trial_count == 64
    assert calculation.unavailable_reason is (
        arch151.DsrUnavailableReason.UNDEFINED_TRIAL_SHARPE
    )
    assert calculation.affected_trial_slot_ids == (
        CANONICAL_SLOTS[0].slot_id,
        CANONICAL_SLOTS[1].slot_id,
    )
    assert tuple(
        item.candidate_slot_id for item in calculation.trial_diagnostics
    ) == tuple(slot.slot_id for slot in CANONICAL_SLOTS)
    assert calculation.trial_diagnostics[0].unavailable_reason is (
        arch151.DsrUnavailableReason.UNDEFINED_TRIAL_SHARPE
    )
    assert calculation.trial_diagnostics[1].unavailable_reason is (
        arch151.DsrUnavailableReason.INVALID_CANDIDATE_MOMENTS
    )
    assert all(
        item.status is arch151.DsrTrialStatus.SHARPE_AVAILABLE
        for item in calculation.trial_diagnostics[2:]
    )
    assert len(calculation.descriptive_economic_order) == 32
    assert set(calculation.descriptive_economic_order) == {
        slot.slot_id for slot in CANONICAL_SLOTS
    }


def test_zero_dispersion_marks_all_32_slots_unavailable_and_preserves_order() -> None:
    batches = tuple(_evaluation_batch_for_slot(slot) for slot in CANONICAL_SLOTS)
    calculation = arch151.compute_selection_bias_evidence(batches)

    assert (
        calculation.unavailable_reason
        is arch151.DsrUnavailableReason.ZERO_TRIAL_SHARPE_VARIANCE
    )
    assert calculation.affected_trial_slot_ids == tuple(
        slot.slot_id for slot in CANONICAL_SLOTS
    )
    assert all(
        item.status is arch151.DsrTrialStatus.SHARPE_AVAILABLE
        and item.daily_sharpe is not None
        and item.unavailable_reason
        is arch151.DsrUnavailableReason.ZERO_TRIAL_SHARPE_VARIANCE
        for item in calculation.trial_diagnostics
    )
    assert len(calculation.descriptive_economic_order) == 32
    assert calculation.effective_trial_count == 64


def test_valid_dsr_with_no_economic_survivor_is_not_statistical_unavailability() -> (
    None
):
    batches = []
    for batch in _dsr_evaluation_population():
        records = tuple(
            replace(
                record,
                metrics=replace(
                    record.metrics,
                    round_trips_by_session=tuple(
                        1 if index < 20 else 0
                        for index, _ in enumerate(record.metrics.round_trips_by_session)
                    ),
                ),
            )
            for record in batch.records
        )
        batches.append(arch151.DevelopmentEvaluationBatch(batch.slot_id, records))

    calculation = arch151.compute_selection_bias_evidence(tuple(batches))
    freeze = arch151.freeze_final_candidate_set(
        tuple(batches), _selection_bias_calculation=calculation
    )

    assert calculation.status is arch151.SelectionBiasStatus.DSR_VERIFIED
    assert not calculation.affected_trial_slot_ids
    assert not freeze.economically_qualified_slot_ids
    assert freeze.candidate_slot_id is None
    assert (
        freeze.status is arch151.FinalFreezeStatus.ZERO_CANDIDATES_NO_QUALIFIED_SURVIVOR
    )


def test_ranking_uses_every_frozen_lexicographic_tie_break() -> None:
    base = [
        Decimal("0.95"),
        Decimal("-0.10"),
        Decimal("1.5"),
        Decimal("0.5"),
        Decimal("0.10"),
        Decimal("0.25"),
        UUID(int=2),
    ]
    improvements = (
        (0, Decimal("0.96")),
        (1, Decimal("-0.09")),
        (2, Decimal("1.6")),
        (3, Decimal("0.6")),
        (4, Decimal("0.09")),
        (5, Decimal("0.24")),
        (6, UUID(int=1)),
    )
    base_key = arch151._ranking_key(*base)
    for index, improved_value in improvements:
        improved = list(base)
        improved[index] = improved_value
        assert arch151._ranking_key(*improved) < base_key


def test_public_synthetic_ranking_preserves_all_canonical_slots() -> None:
    materials = tuple(_synthetic_ranking_material(slot) for slot in CANONICAL_SLOTS)
    preferred = _synthetic_ranking_material(CANONICAL_SLOTS[-1], Decimal("0.99"))
    materials = (*materials[:-1], preferred)
    ranked = arch151.rank_synthetic_candidate_population(materials)
    assert len(ranked) == len(set(ranked)) == 32
    assert set(ranked) == {slot.slot_id for slot in CANONICAL_SLOTS}
    assert ranked[0] == CANONICAL_SLOTS[-1].slot_id
    assert ranked[1:] == tuple(
        sorted(
            (slot.slot_id for slot in CANONICAL_SLOTS[:-1]), key=lambda value: value.int
        )
    )
    with pytest.raises(Arch151Error, match="complete 32-slot"):
        arch151.rank_synthetic_candidate_population(materials[:-1])
    with pytest.raises(Arch151Error, match="canonical input population"):
        arch151.rank_synthetic_candidate_population(
            (materials[1], materials[0], *materials[2:])
        )


def test_ranking_uses_stress_realized_net_pf_not_pre_cost_pf() -> None:
    materials = tuple(_synthetic_ranking_material(slot) for slot in CANONICAL_SLOTS)
    materials = list(materials)
    materials[0] = _synthetic_ranking_material(
        CANONICAL_SLOTS[0],
        net_profit_factor=Decimal("0.9"),
        pre_cost_profit_factor=Decimal("100"),
    )
    materials[1] = _synthetic_ranking_material(
        CANONICAL_SLOTS[1],
        net_profit_factor=Decimal("2"),
        pre_cost_profit_factor=Decimal("0.5"),
    )

    ranked = arch151.rank_synthetic_candidate_population(tuple(materials))

    assert ranked[0] == CANONICAL_SLOTS[1].slot_id
    assert ranked[-1] == CANONICAL_SLOTS[0].slot_id


def test_final_freeze_requires_full_population_and_fails_closed_on_degenerate_dsr() -> (
    None
):
    batches = tuple(_evaluation_batch_for_slot(slot) for slot in CANONICAL_SLOTS)
    selection = arch151.compute_selection_bias_evidence(batches)
    assert (
        selection.status is arch151.SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    assert (
        selection.unavailable_reason
        is arch151.DsrUnavailableReason.ZERO_TRIAL_SHARPE_VARIANCE
    )
    freeze = arch151.freeze_final_candidate_set(
        batches, _selection_bias_calculation=selection
    )
    assert freeze.source_manifest_id == CANONICAL_MANIFEST.manifest_id
    assert freeze.batch_digests == tuple(batch.batch_digest for batch in batches)
    assert freeze.economically_qualified_slot_ids == tuple(
        slot.slot_id for slot in CANONICAL_SLOTS
    )
    assert freeze.candidate_slot_id is None
    assert freeze.candidate_program_id is None
    assert (
        freeze.status
        is arch151.FinalFreezeStatus.ZERO_CANDIDATES_STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    assert (
        freeze.selection_bias_status
        is arch151.SelectionBiasStatus.STATISTICAL_EVIDENCE_UNAVAILABLE
    )
    assert len(freeze.fingerprint) == 64
    assert (
        arch151.freeze_final_candidate_set(
            batches, _selection_bias_calculation=selection
        ).freeze_id
        == freeze.freeze_id
    )
    with pytest.raises(Arch151Error, match="all 32 canonical"):
        arch151.freeze_final_candidate_set(batches[:-1])
    duplicated = (*batches[:-1], batches[0])
    with pytest.raises(Arch151Error, match="manifest order"):
        arch151.freeze_final_candidate_set(duplicated)
    with pytest.raises(TypeError):
        arch151.freeze_final_candidate_set(
            batches, candidate_slot_id=CANONICAL_SLOTS[0].slot_id
        )
    with pytest.raises(Arch151Error, match="all 32 canonical"):
        arch151.freeze_final_candidate_set(
            tuple(slot.slot_id for slot in CANONICAL_SLOTS)
        )
    with pytest.raises(TypeError):
        arch151.FinalCandidateFreeze(candidate_slot_id=CANONICAL_SLOTS[0].slot_id)
    with pytest.raises(arch151.AuthorizationUnavailableError, match="zero candidates"):
        arch151.authorize_holdout(freeze, object(), object())
    with pytest.raises(arch151.AuthorizationUnavailableError):
        arch151.authorize_holdout(UUID(int=1), True, Decimal("0.99"))
    with pytest.raises(arch151.AuthorizationUnavailableError):
        arch151.authorize_extension(freeze, UUID(int=1), True)
    with pytest.raises(
        arch151.AuthorizationUnavailableError, match="complete source population"
    ):
        arch151.VerifiedSelectionBiasEvidence(probability=Decimal("0.99"))


def test_canonical_entry_windows_are_structurally_reachable_from_session_grid() -> None:
    for program in CANONICAL_PROGRAMS:
        minutes = tuple(_minute("SPY", _NORMAL_DAY, offset) for offset in range(390))
        aggregated = aggregate_sparse_bars(minutes, program.resolution)
        opportunities = structural_entry_opportunities(
            program, aggregated.bars, minutes
        )
        assert opportunities, program.key
        assert all(
            program.entry_window.contains(item.completed_signal_bar.completed_at)
            for item in opportunities
        )


def test_later_period_calendar_population_and_non_authorizing() -> None:
    freeze = _one_candidate_final_freeze()
    holdout = arch151.qualify_later_period(
        freeze,
        _later_period_evidence(arch151.LaterPeriodKind.HOLDOUT_2024_2025),
    )
    assert holdout.status is arch151.LaterPeriodStatus.PASS
    assert holdout.passed
    assert holdout.expected_session_count == holdout.observed_session_count == 502
    assert holdout.expected_month_count == holdout.observed_month_count == 24
    assert holdout.calendar_partition_net_returns[0][0] == 2024
    assert holdout.calendar_partition_net_returns[1][0] == 2025
    assert holdout.aggregate_net_return is not None and holdout.aggregate_net_return > 0
    assert holdout.profit_factor is not None
    assert holdout.profit_factor.state is arch151.ProfitFactorState.POSITIVE_INFINITY
    assert holdout.active_session_fraction == 1
    assert holdout.average_completed_round_trips_per_year == Decimal("251")
    assert holdout.maximum_positive_month_pnl_share is not None
    assert holdout.maximum_positive_month_pnl_share <= Decimal("0.40")

    extension_sessions, extension_months = arch151._later_period_calendar(
        arch151.LaterPeriodKind.EXTENSION_2026_JAN_OCT
    )
    active_months = set(extension_months[:6])
    active_dates = set()
    for month in extension_months[:6]:
        active_dates.update(
            session
            for session in extension_sessions
            if (session.year, session.month) == month
        )
        if len(active_dates) >= 66:
            break
    active_dates = set(sorted(active_dates)[:62])
    outcomes = {
        session: ((Decimal("1"),) if session in active_dates else ())
        for session in extension_sessions
    }
    monthly_positive_returns = {
        session: (
            Decimal("0.001")
            if (session.year, session.month) in active_months
            else Decimal(0)
        )
        for session in extension_sessions
    }
    extension = arch151.qualify_later_period(
        freeze,
        _later_period_evidence(
            arch151.LaterPeriodKind.EXTENSION_2026_JAN_OCT,
            returns_by_session=monthly_positive_returns,
            outcomes_by_session=outcomes,
        ),
    )
    assert extension.status is arch151.LaterPeriodStatus.PASS
    assert extension.expected_session_count == extension.observed_session_count == 204
    assert extension.expected_month_count == extension.observed_month_count == 10
    assert extension.positive_month_count == 6
    assert extension.active_session_fraction is not None
    assert extension.active_session_fraction >= Decimal("0.30")
    assert extension.profit_factor is not None
    assert extension.profit_factor.state is arch151.ProfitFactorState.POSITIVE_INFINITY

    with pytest.raises(arch151.AuthorizationUnavailableError, match="authenticated"):
        arch151.authorize_holdout(freeze, holdout, object())
    with pytest.raises(arch151.AuthorizationUnavailableError, match="authenticated"):
        arch151.authorize_extension(freeze, object(), holdout)
    with pytest.raises(arch151.AuthorizationUnavailableError):
        arch151.AuthenticatedHoldoutPass()
    with pytest.raises(arch151.AuthorizationUnavailableError):
        arch151.AuthenticatedExtensionPass()
    with pytest.raises(arch151.AuthorizationUnavailableError):
        arch151.classify_research_survivor(
            freeze, object(), object(), object(), object()
        )


def test_holdout_boundaries_accept_inclusive_limits() -> None:
    freeze = _one_candidate_final_freeze()
    sessions, _months = arch151._later_period_calendar(
        arch151.LaterPeriodKind.HOLDOUT_2024_2025
    )
    active_dates = sessions[:151]
    active_date_set = set(active_dates)
    outcomes = {
        session: ((Decimal(0), Decimal(0)) if index < 9 else (Decimal(0),))
        if session in active_date_set
        else ()
        for index, session in enumerate(sessions)
    }
    for month, amount in (
        ((2024, 1), Decimal("4")),
        ((2024, 2), Decimal("3")),
        ((2024, 3), Decimal("3")),
    ):
        session = next(day for day in active_dates if (day.year, day.month) == month)
        values = list(outcomes[session])
        values[0] = amount
        outcomes[session] = tuple(values)
    returns = {session: Decimal("0.001") for session in sessions}
    returns[sessions[0]] = Decimal("-0.15")
    result = arch151.qualify_later_period(
        freeze,
        _later_period_evidence(
            arch151.LaterPeriodKind.HOLDOUT_2024_2025,
            returns_by_session=returns,
            outcomes_by_session=outcomes,
        ),
    )

    assert result.status is arch151.LaterPeriodStatus.PASS
    assert result.max_drawdown == Decimal("0.15")
    assert result.average_completed_round_trips_per_year == Decimal("80")
    with localcontext() as context:
        context.prec = 60
        assert result.active_session_fraction == Decimal(151) / Decimal(502)
    assert result.maximum_positive_month_pnl_share == Decimal("0.4")


def test_later_period_completeness_candidate_and_economics_bindings_fail_closed() -> (
    None
):
    freeze = _one_candidate_final_freeze()
    evidence = _later_period_evidence(arch151.LaterPeriodKind.HOLDOUT_2024_2025)

    missing_session = replace(evidence, sessions=evidence.sessions[1:])
    incomplete = arch151.qualify_later_period(freeze, missing_session)
    assert incomplete.status is arch151.LaterPeriodStatus.INCOMPLETE
    assert (
        arch151.LaterPeriodRejection.SESSION_POPULATION_INCOMPLETE
        in incomplete.rejection_reasons
    )

    one_month_removed = tuple(
        row
        for row in evidence.sessions
        if (row.session_date.year, row.session_date.month) != (2024, 1)
    )
    missing_month = arch151.qualify_later_period(
        freeze, replace(evidence, sessions=one_month_removed)
    )
    assert missing_month.status is arch151.LaterPeriodStatus.INCOMPLETE
    assert (
        arch151.LaterPeriodRejection.CALENDAR_MONTH_POPULATION_INCOMPLETE
        in missing_month.rejection_reasons
    )

    with pytest.raises(arch151.AuthorizationUnavailableError, match="frozen candidate"):
        arch151.qualify_later_period(
            freeze,
            replace(evidence, candidate_slot_id=CANONICAL_SLOTS[1].slot_id),
        )
    with pytest.raises(Arch151Error, match="STRESS"):
        arch151.qualify_later_period(
            freeze, replace(evidence, economics_case=arch151.FillCostCase.BASE)
        )

    altered_trade = replace(evidence.trades[0], net_pnl=Decimal("2"))
    invalid = arch151.qualify_later_period(
        freeze, replace(evidence, trades=(altered_trade, *evidence.trades[1:]))
    )
    assert invalid.status is arch151.LaterPeriodStatus.INVALID
    assert invalid.rejection_reasons == (
        arch151.LaterPeriodRejection.SESSION_TRADE_RECONCILIATION_INVALID,
    )
    assert invalid.aggregate_net_return is None


def _distributed_session_dates(
    sessions: tuple[date, ...], *, base_per_month: int, extra_count: int
) -> tuple[date, ...]:
    groups: dict[tuple[int, int], list[date]] = {}
    for session in sessions:
        groups.setdefault((session.year, session.month), []).append(session)
    selected = [
        session for values in groups.values() for session in values[:base_per_month]
    ]
    remaining = extra_count
    for values in groups.values():
        if not remaining:
            break
        if len(values) > base_per_month:
            selected.append(values[base_per_month])
            remaining -= 1
    assert remaining == 0
    return tuple(sorted(selected))


@pytest.mark.parametrize(
    ("case", "expected_rejection"),
    [
        (
            "net_return",
            arch151.LaterPeriodRejection.HOLDOUT_NET_RETURN_NOT_POSITIVE,
        ),
        (
            "calendar_year",
            arch151.LaterPeriodRejection.HOLDOUT_YEAR_RETURN_NOT_POSITIVE,
        ),
        (
            "profit_factor",
            arch151.LaterPeriodRejection.HOLDOUT_PROFIT_FACTOR_NOT_ABOVE_1_10,
        ),
        (
            "drawdown",
            arch151.LaterPeriodRejection.HOLDOUT_MAX_DRAWDOWN_ABOVE_15_PERCENT,
        ),
        (
            "active_fraction",
            arch151.LaterPeriodRejection.HOLDOUT_ACTIVE_SESSION_FRACTION_BELOW_30_PERCENT,
        ),
        (
            "annual_frequency",
            arch151.LaterPeriodRejection.HOLDOUT_AVERAGE_ROUND_TRIPS_BELOW_80,
        ),
        (
            "concentration",
            arch151.LaterPeriodRejection.HOLDOUT_POSITIVE_PNL_CONCENTRATION_ABOVE_40_PERCENT,
        ),
        (
            "positive_pnl_unavailable",
            arch151.LaterPeriodRejection.HOLDOUT_POSITIVE_PNL_UNAVAILABLE,
        ),
    ],
)
def test_holdout_stress_thresholds_produce_typed_rejections(
    case: str, expected_rejection: arch151.LaterPeriodRejection
) -> None:
    freeze = _one_candidate_final_freeze()
    sessions, _months = arch151._later_period_calendar(
        arch151.LaterPeriodKind.HOLDOUT_2024_2025
    )
    returns: dict[date, Decimal] = {}
    outcomes: dict[date, tuple[Decimal, ...]] = {}
    if case == "net_return":
        returns = {session: Decimal(0) for session in sessions}
    elif case == "calendar_year":
        returns = {
            session: Decimal("-0.0005") for session in sessions if session.year == 2025
        }
    elif case == "profit_factor":
        outcomes = {session: (Decimal("1.10"), Decimal("-1")) for session in sessions}
    elif case == "drawdown":
        returns[sessions[0]] = Decimal("-0.20")
    elif case == "active_fraction":
        selected = _distributed_session_dates(sessions, base_per_month=3, extra_count=8)
        outcomes = {
            session: ((Decimal("1"), Decimal("1")) if session in selected else ())
            for session in sessions
        }
    elif case == "annual_frequency":
        selected = _distributed_session_dates(
            sessions, base_per_month=6, extra_count=14
        )
        outcomes = {
            session: ((Decimal("1"),) if session in selected else ())
            for session in sessions
        }
    elif case == "concentration":
        outcomes = {
            session: ((Decimal("1000"),) if session == sessions[0] else (Decimal("1"),))
            for session in sessions
        }
    elif case == "positive_pnl_unavailable":
        outcomes = {session: (Decimal("-1"),) for session in sessions}
    else:
        raise AssertionError(case)

    qualified = arch151.qualify_later_period(
        freeze,
        _later_period_evidence(
            arch151.LaterPeriodKind.HOLDOUT_2024_2025,
            returns_by_session=returns,
            outcomes_by_session=outcomes,
        ),
    )
    assert qualified.status is arch151.LaterPeriodStatus.FAIL
    assert expected_rejection in qualified.rejection_reasons


@pytest.mark.parametrize(
    ("case", "expected_rejection"),
    [
        (
            "net_return",
            arch151.LaterPeriodRejection.EXTENSION_NET_RETURN_NOT_POSITIVE,
        ),
        (
            "profit_factor",
            arch151.LaterPeriodRejection.EXTENSION_PROFIT_FACTOR_NOT_ABOVE_1_05,
        ),
        (
            "drawdown",
            arch151.LaterPeriodRejection.EXTENSION_MAX_DRAWDOWN_ABOVE_15_PERCENT,
        ),
        (
            "positive_months",
            arch151.LaterPeriodRejection.EXTENSION_POSITIVE_MONTHS_BELOW_6,
        ),
        (
            "active_fraction",
            arch151.LaterPeriodRejection.EXTENSION_ACTIVE_SESSION_FRACTION_BELOW_30_PERCENT,
        ),
    ],
)
def test_extension_stress_thresholds_produce_typed_rejections(
    case: str, expected_rejection: arch151.LaterPeriodRejection
) -> None:
    freeze = _one_candidate_final_freeze()
    sessions, months = arch151._later_period_calendar(
        arch151.LaterPeriodKind.EXTENSION_2026_JAN_OCT
    )
    returns: dict[date, Decimal] = {}
    outcomes: dict[date, tuple[Decimal, ...]] = {}
    if case == "net_return":
        returns = {session: Decimal(0) for session in sessions}
    elif case == "profit_factor":
        outcomes = {session: (Decimal("1.05"), Decimal("-1")) for session in sessions}
    elif case == "drawdown":
        returns = {session: Decimal("0.005") for session in sessions}
        returns[sessions[0]] = Decimal("-0.20")
    elif case == "positive_months":
        positive_months = set(months[:5])
        returns = {
            session: (
                Decimal("0.001")
                if (session.year, session.month) in positive_months
                else Decimal(0)
            )
            for session in sessions
        }
    elif case == "active_fraction":
        selected = _distributed_session_dates(
            tuple(
                session
                for session in sessions
                if (session.year, session.month) in set(months[:6])
            ),
            base_per_month=10,
            extra_count=1,
        )
        outcomes = {
            session: ((Decimal("1"),) if session in selected else ())
            for session in sessions
        }
        returns = {
            session: (
                Decimal("0.001")
                if (session.year, session.month) in set(months[:6])
                else Decimal(0)
            )
            for session in sessions
        }
    else:
        raise AssertionError(case)

    qualified = arch151.qualify_later_period(
        freeze,
        _later_period_evidence(
            arch151.LaterPeriodKind.EXTENSION_2026_JAN_OCT,
            returns_by_session=returns,
            outcomes_by_session=outcomes,
        ),
    )
    assert qualified.status is arch151.LaterPeriodStatus.FAIL
    assert expected_rejection in qualified.rejection_reasons


def test_later_period_authorization_requires_real_source_owned_ordered_evidence() -> (
    None
):
    freeze = _one_candidate_final_freeze()
    synthetic = arch151.qualify_later_period(
        freeze,
        _later_period_evidence(arch151.LaterPeriodKind.HOLDOUT_2024_2025),
    )
    assert synthetic.passed
    with pytest.raises(arch151.AuthorizationUnavailableError, match="authenticated"):
        arch151.authorize_holdout(freeze, synthetic, synthetic)
    with pytest.raises(arch151.AuthorizationUnavailableError):
        arch151.authorize_extension(freeze, synthetic, synthetic)
    forged_development = object.__new__(arch151.AuthenticatedDevelopmentEvidence)
    object.__setattr__(forged_development, "_seal", object())
    with pytest.raises(arch151.AuthorizationUnavailableError, match="authenticated"):
        arch151.authorize_holdout(freeze, forged_development, synthetic)


def test_d1r_adapter_is_fixed_and_reuses_arch150_acceptance_without_reading_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (
        arch151.ARCH150_D1R_DATASET_ID
        == arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.dataset_id
    )
    assert arch151.ARCH150_D1R_DATASET_SHA256 == (
        arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.dataset_semantic_sha256
    )
    assert arch151.ARCH150_D1R_CUSTODY_ID == (
        arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.custody_id
    )
    assert arch151.ARCH150_D1R_CUSTODY_SHA256 == (
        arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.custody_semantic_sha256
    )
    assert arch151.ARCH150_D1R_EVIDENCE_ID == UUID(
        "c31bb29d-3d53-5e2f-a01f-55a42ec96295"
    )
    assert (
        arch151.ARCH150_D1R_EVIDENCE_SHA256
        == (arch150_d1r._SEMANTIC_PINS["evidence.json"][1])
    )
    assert arch151.ARCH150_D1R_SCHEDULED_SLOTS_PER_SYMBOL == (
        arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.scheduled_slots_per_symbol
    )
    assert arch151.ARCH150_D1R_OBSERVED_COUNTS == (
        arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.observed_counts_by_symbol
    )
    assert arch151.ARCH150_D1R_MISSING_COUNTS == (
        arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.missing_counts_by_symbol
    )
    assert arch151.ARCH150_D1R_COMMON_MISSING_COUNT == 64
    assert arch151.ARCH150_D1R_UNION_MISSING_COUNT == 155
    assert arch151.ARCH150_D1R_AFFECTED_SESSION_COUNT == 9
    assert arch151.ARCH150_D1R_FULLY_MISSING_SESSION_COUNTS == (
        ("SPY", 0),
        ("QQQ", 0),
    )

    one = _minute("SPY", _NORMAL_DAY, 0)
    incomplete_bars = (
        arch150.IntradayBar(
            one.symbol,
            one.timestamp,
            one.open,
            one.high,
            one.low,
            one.close,
            one.volume,
            arch150.BarResolution.ONE_MINUTE,
        ),
    )
    normalized_hashes = dict(arch150._ACCEPTED_NORMALIZED_CSV_SHA256)
    artifacts = tuple(
        arch150_d1r.ArtifactCommitment(
            name,
            length,
            normalized_hashes.get(
                name.removeprefix("normalized/").removesuffix(".csv"), "0" * 64
            ),
        )
        for name, length in arch150_d1r._ARTIFACT_LENGTHS.items()
    )
    snapshot = arch150_d1r.InputSnapshot(incomplete_bars, artifacts)
    roots = []

    def fake_pinned_reader(root):
        roots.append(root)
        return snapshot

    monkeypatch.setattr(arch151.arch150_d1r, "_read_pinned_input", fake_pinned_reader)
    with pytest.raises(arch150.Arch150Error):
        arch151.load_arch150_d1r_source_history()

    assert roots == [arch150_d1r.ACCEPTED_INPUT_ROOT]
    bad_artifacts = tuple(
        replace(item, sha256="0" * 64) if item.name == "normalized/SPY.csv" else item
        for item in artifacts
    )
    monkeypatch.setattr(
        arch151.arch150_d1r,
        "_read_pinned_input",
        lambda root: arch150_d1r.InputSnapshot(incomplete_bars, bad_artifacts),
    )
    with pytest.raises(arch151.AuthorizationUnavailableError, match="commitments"):
        arch151.load_arch150_d1r_source_history()
    with pytest.raises(TypeError):
        arch151._adapt_arch150_d1r_snapshot(snapshot)

    with pytest.raises(arch151.AuthorizationUnavailableError, match="accepted Arch150"):
        arch151._source_session_projections(
            (("SPY", (_minute("SPY", _NORMAL_DAY, 0),)),),
            "0" * 64,
            accepted_dataset=True,
        )
    with pytest.raises(TypeError):
        arch151._source_session_projections((), "0" * 64, production=True)


def test_synthetic_history_uses_separate_seal_and_feature_cache_is_source_bound() -> (
    None
):
    history = _synthetic_source_history()
    assert type(history) is arch151._SyntheticSourceHistory
    assert not isinstance(history, arch151.Arch150D1RSourceHistory)
    projection = history._projection_index[
        ("SPY", _NORMAL_DAY, BarResolution.FIVE_MINUTE)
    ]
    evidence = next(
        item
        for item in projection.verified_sessions
        if item.resolution is BarResolution.FIVE_MINUTE
    )
    assert type(evidence) is arch151._SyntheticSparseSessionEvidence
    assert not isinstance(evidence, arch151.VerifiedSparseSession)

    cutoff = _feature_cutoff()
    prepared = tuple(
        arch151.prepare_session_features(history, program, symbol, _NORMAL_DAY, cutoff)
        for program in CANONICAL_PROGRAMS
        for symbol in ("SPY", "QQQ")
    )
    assert len({item.key.cache_id for item in prepared}) == 32
    for item in prepared:
        assert item.key.source_digest == history.source_digest
        assert item.key.cutoff_completed_at == cutoff
        assert item.decision_bar is not None
        assert item.decision_bar.completed_at == cutoff
        assert all(bar.completed_at <= cutoff for bar in item.bars)
        assert all(
            observation.bar.completed_at <= cutoff
            for observation in item.vwap_observations
        )
        assert all(point.bar.completed_at <= cutoff for point in item.indicators)

    program = CANONICAL_PROGRAMS[0]
    earlier = arch151.prepare_session_features(
        history,
        program,
        "SPY",
        _NORMAL_DAY,
        cutoff - timedelta(minutes=int(program.resolution)),
    )
    other_symbol = arch151.prepare_session_features(
        history, program, "QQQ", _NORMAL_DAY, cutoff
    )
    source_minutes = tuple(
        _full_session_minutes(_NORMAL_DAY, symbol) for symbol in ("SPY", "QQQ")
    )
    first_minute = source_minutes[0][0]
    changed_first = replace(
        first_minute,
        low=Decimal("99.9"),
        close=Decimal("99.9"),
    )
    changed_history = arch151._test_only_synthetic_source_history(
        (changed_first,) + source_minutes[0][1:] + source_minutes[1]
    )
    other_source = arch151.prepare_session_features(
        changed_history, program, "SPY", _NORMAL_DAY, cutoff
    )
    assert earlier.key.cache_id != prepared[0].key.cache_id
    assert other_symbol.key.cache_id != prepared[0].key.cache_id
    assert other_source.key.cache_id != prepared[0].key.cache_id


def test_sparse_features_reset_after_open_and_in_session_gaps() -> None:
    missing_open = tuple(
        (symbol, _NORMAL_DAY, offset)
        for symbol in ("SPY", "QQQ")
        for offset in range(15)
    )
    history = _synthetic_source_history(missing_offsets=missing_open)
    a_program = next(
        item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.A5_01
    )
    b_program = next(
        item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.B5_01
    )
    c_program = next(
        item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C5_01
    )
    d_program = next(
        item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01
    )
    cutoff = _feature_cutoff()

    a = arch151.prepare_session_features(history, a_program, "SPY", _NORMAL_DAY, cutoff)
    b = arch151.prepare_session_features(history, b_program, "SPY", _NORMAL_DAY, cutoff)
    c = arch151.prepare_session_features(history, c_program, "SPY", _NORMAL_DAY, cutoff)
    d = arch151.prepare_session_features(history, d_program, "SPY", _NORMAL_DAY, cutoff)
    assert a.family_a_measure is None
    assert b.opening_range_high is None
    assert c.bars[0].timestamp > _AUTHORITY.schedule_for(_NORMAL_DAY).opens_at
    assert d.bars[0].timestamp > _AUTHORITY.schedule_for(_NORMAL_DAY).opens_at
    assert c.indicators[0].sigma is None
    assert c.indicators[0].efficiency_ratio is None
    assert d.indicators[0].ema_fast is None
    assert d.indicators[0].ema_slow is None
    assert d.indicators[0].preceding_atr is None

    gap_offsets = tuple(
        (symbol, _NORMAL_DAY, offset)
        for symbol in ("SPY", "QQQ")
        for offset in range(60, 65)
    )
    missing_gap = set(gap_offsets)
    gap_minutes = tuple(
        _minute(
            symbol,
            _NORMAL_DAY,
            offset,
            open_price=str(Decimal("100") + Decimal(offset) / Decimal("100")),
            high=str(Decimal("100") + Decimal(offset) / Decimal("100")),
            low=str(Decimal("100") + Decimal(offset) / Decimal("100")),
            close=str(Decimal("100") + Decimal(offset) / Decimal("100")),
        )
        for symbol in ("SPY", "QQQ")
        for offset in range(390)
        if (symbol, _NORMAL_DAY, offset) not in missing_gap
    )
    gap_history = arch151._test_only_synthetic_source_history(gap_minutes)
    c_gap = arch151.prepare_session_features(
        gap_history, c_program, "SPY", _NORMAL_DAY, cutoff
    )
    d_gap = arch151.prepare_session_features(
        gap_history, d_program, "SPY", _NORMAL_DAY, cutoff
    )
    c_gap_index = next(
        index
        for index, point in enumerate(c_gap.indicators)
        if point.bar.timestamp
        >= _AUTHORITY.schedule_for(_NORMAL_DAY).opens_at + timedelta(minutes=65)
    )
    d_gap_index = next(
        index
        for index, point in enumerate(d_gap.indicators)
        if point.bar.timestamp
        >= _AUTHORITY.schedule_for(_NORMAL_DAY).opens_at + timedelta(minutes=65)
    )
    assert c_gap.indicators[c_gap_index].sigma is None
    assert c_gap.indicators[c_gap_index].efficiency_ratio is None
    assert any(point.sigma is not None for point in c_gap.indicators[c_gap_index + 1 :])
    assert any(
        point.efficiency_ratio is not None
        for point in c_gap.indicators[c_gap_index + 1 :]
    )
    assert d_gap.indicators[d_gap_index].ema_slow is None
    assert d_gap.indicators[d_gap_index].preceding_atr is None
    assert any(
        point.ema_slow is not None for point in d_gap.indicators[d_gap_index + 1 :]
    )
    assert any(
        point.preceding_atr is not None for point in d_gap.indicators[d_gap_index + 1 :]
    )

    next_session = next(
        session
        for session in _AUTHORITY.published.sessions
        if session > _NORMAL_DAY and session.year == _NORMAL_DAY.year
    )
    two_sessions = _synthetic_source_history((_NORMAL_DAY, next_session))
    next_day = arch151.prepare_session_features(
        two_sessions, d_program, "SPY", next_session, _feature_cutoff(next_session)
    )
    assert next_day.indicators[0].ema_fast is None
    assert next_day.indicators[0].ema_slow is None
    assert next_day.indicators[0].preceding_atr is None


def test_observed_only_vwap_binds_the_exact_sparse_source_projection() -> None:
    schedule = _AUTHORITY.schedule_for(_NORMAL_DAY)
    assert schedule is not None
    minutes = tuple(
        _minute(
            "SPY",
            _NORMAL_DAY,
            offset,
            open_price="102",
            high="102",
            low="102",
            close="102",
        )
        for offset in range(15, 390)
    )
    history = arch151._test_only_synthetic_source_history(minutes)
    projection = history._projection_index[
        ("SPY", _NORMAL_DAY, BarResolution.FIVE_MINUTE)
    ]
    stream = next(
        item
        for item in projection.aggregate_streams
        if item.resolution is BarResolution.FIVE_MINUTE
    )
    evidence = next(
        item
        for item in projection.verified_sessions
        if item.resolution is BarResolution.FIVE_MINUTE
    )
    observations = dict(projection.vwap_by_resolution)[BarResolution.FIVE_MINUTE]
    assert stream.bars[0].timestamp == schedule.opens_at + timedelta(minutes=15)
    assert observations[0].bar == stream.bars[0]
    assert observations[0].vwap == Decimal("102")
    assert observations == aggregate_session_vwap(
        minutes, stream, verified_sessions=(evidence,)
    )

    changed_minute = replace(
        minutes[1],
        low=Decimal("101"),
        close=Decimal("101"),
    )
    changed_history = arch151._test_only_synthetic_source_history(
        minutes[:1] + (changed_minute,) + minutes[2:]
    )
    other_evidence = next(
        item
        for item in changed_history._projection_index[
            ("SPY", _NORMAL_DAY, BarResolution.FIVE_MINUTE)
        ].verified_sessions
        if item.resolution is BarResolution.FIVE_MINUTE
    )
    with pytest.raises(arch151.AuthorizationUnavailableError, match="not bound"):
        aggregate_session_vwap(minutes, stream, verified_sessions=(other_evidence,))


def test_family_a_source_calibration_uses_only_prior_complete_sessions() -> None:
    prior_sessions = tuple(
        session
        for session in _AUTHORITY.published.sessions
        if date(2022, 1, 1) <= session < date(2023, 1, 1)
    )[-61:]
    assert len(prior_sessions) == 61
    incomplete_session = prior_sessions[0]
    incomplete_offset = 100
    missing = (("SPY", incomplete_session, incomplete_offset),)
    prior_history = _synthetic_source_history(
        prior_sessions, symbols=("SPY",), missing_offsets=missing
    )
    scored_history = _synthetic_source_history(
        (*prior_sessions, date(2023, 1, 3)),
        symbols=("SPY",),
        missing_offsets=missing,
    )
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.A5_01)
    prior = arch151.calibrate_family_a_from_source_history(
        prior_history, program, "SPY", 2023
    )
    with_scored_year = arch151.calibrate_family_a_from_source_history(
        scored_history, program, "SPY", 2023
    )

    assert len(prior.calibration_session_dates) == 60
    assert incomplete_session not in prior.calibration_session_dates
    assert all(
        session < date(2023, 1, 1) for session in prior.calibration_session_dates
    )
    assert prior.calibration_id == with_scored_year.calibration_id
    assert prior.calibration_fingerprint == with_scored_year.calibration_fingerprint
