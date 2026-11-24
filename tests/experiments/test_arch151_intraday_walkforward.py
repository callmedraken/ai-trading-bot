"""Synthetic contracts for the Architecture 151 source foundation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from functools import cache
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

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
    return target, confirming, tuple(confirming_vwaps)


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
    return arch151.FoldMetrics(
        session_dates,
        tuple(returns),
        tuple(round_trips),
        profile.get("gross_positive", Decimal("2")),
        profile.get("gross_negative", Decimal("1")),
        profile.get("annual_turnover", Decimal("0.25")),
    )


def _evaluation_batch_for_slot(slot, year_profiles=None):
    year_profiles = year_profiles or {}
    records = []
    for fold in arch151.WALK_FORWARD_FOLDS:
        metrics = _fold_metrics_for_year(
            fold.scored_year, year_profiles.get(fold.scored_year)
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
    return arch151.DevelopmentEvaluationBatch(slot.slot_id, tuple(records))


def _synthetic_ranking_material(slot, probability=Decimal("0.95")):
    aggregate = arch151.DevelopmentAggregate(
        slot.slot_id,
        arch151.FillCostCase.STRESS,
        Decimal("0.10"),
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


def test_session_vwap_rejects_any_source_session_that_starts_after_open() -> None:
    second_session = date(2023, 1, 4)
    minutes = tuple(_minute("SPY", _NORMAL_DAY, offset) for offset in range(5)) + tuple(
        _minute("SPY", second_session, offset) for offset in range(1, 10)
    )
    stream = aggregate_sparse_bars(minutes, BarResolution.FIVE_MINUTE)

    with pytest.raises(
        UnavailableIndicatorError, match="begin at the published XNYS open"
    ):
        aggregate_session_vwap(minutes, stream)


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
            signal = family_c_entry_signal(program, history, current)
            assert signal is not None, program.key
            assert signal.normalized_deviation < 0
            assert signal.efficiency_ratio <= program.parameters.efficiency_ratio_max
            signal_index = next(
                index for index, bar in enumerate(bars) if bar == current.bar
            )
            assert family_c_reversion_exit(
                program,
                signal,
                VwapObservation(bars[signal_index + 1], Decimal("90")),
            )
        else:
            target, other, vwaps = _d_reachable_inputs(program)
            minute_stream = _minutes_for_aggregates(tuple(target), program.resolution)
            assert len(
                aggregate_sparse_bars(minute_stream, program.resolution).bars
            ) == len(target)
            signal = family_d_entry_signal(program, target, other, vwaps)
            assert signal is not None, program.key
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


def test_family_c_rejects_insufficient_warmup_and_zero_er_denominator() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C15_02)
    bars = _flat_aggregate_session(_NORMAL_DAY, program.resolution)
    current = VwapObservation(bars[20], Decimal("100"))
    short = tuple(VwapObservation(bar, Decimal("100")) for bar in bars[20 - 11 : 20])
    with pytest.raises(UnavailableIndicatorError, match="warmup"):
        family_c_entry_signal(program, short, current)
    with pytest.raises(UnavailableIndicatorError, match="zero"):
        efficiency_ratio([Decimal("100")] * 11, 10)
    with pytest.raises(UnavailableIndicatorError, match="two values"):
        sample_standard_deviation([Decimal("0.1")])


def test_family_c_rejects_off_grid_and_cross_session_history() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C5_01)
    history, current, _ = _c_reachable_inputs(program)
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
        family_c_entry_signal(program, off_grid_history, off_grid_current)

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
        family_c_entry_signal(program, other_session_history, current)


def test_family_c_exit_rejects_earlier_or_different_session_bar() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.C5_01)
    history, current, bars = _c_reachable_inputs(program)
    signal = family_c_entry_signal(program, history, current)
    assert signal is not None
    signal_index = next(index for index, bar in enumerate(bars) if bar == current.bar)
    earlier = VwapObservation(bars[signal_index - 1], Decimal("90"))
    with pytest.raises(Arch151Error, match="strictly later"):
        family_c_reversion_exit(program, signal, earlier)

    other_session = VwapObservation(
        replace(
            current.bar,
            timestamp=current.bar.timestamp + timedelta(days=1),
        ),
        Decimal("90"),
    )
    with pytest.raises(Arch151Error, match="strictly later"):
        family_c_reversion_exit(program, signal, other_session)


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
    target, confirming, vwaps = _d_reachable_inputs(program)
    assert family_d_entry_signal(program, target, confirming, vwaps) is not None

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
            family_d_entry_signal(program, target, confirming, invalid)


@pytest.mark.parametrize("gap_symbol", ["SPY", "QQQ"])
def test_family_d_reseeds_and_finds_fresh_signal_after_either_symbol_gap(
    gap_symbol: str,
) -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target, confirming, vwaps = _d_reachable_inputs(
        program, gap_symbol=gap_symbol, gap_index=1
    )

    signal = family_d_entry_signal(program, target, confirming, vwaps)

    assert signal is not None
    assert signal.setup_timestamp > target[0].timestamp
    assert signal.signal_timestamp >= signal.setup_timestamp
    assert signal.confirming_symbol == "QQQ"


def test_family_d_does_not_bridge_cross_confirmation_across_a_gap() -> None:
    program = next(item for item in CANONICAL_PROGRAMS if item.key is ProgramKey.D5_01)
    target, confirming, vwaps = _d_reachable_inputs(program)
    original = family_d_entry_signal(program, target, confirming, vwaps)
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
        family_d_entry_signal(program, target, gapped_confirming, gapped_vwaps) is None
    )


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

    assert family_d_entry_signal(program, target, confirming, vwaps) is None


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


def test_fold_metrics_reject_nonfinite_or_undefined_economics() -> None:
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
            Decimal("0.25"),
        )
    with pytest.raises(UnavailableIndicatorError, match="loss denominator"):
        arch151.FoldMetrics(
            dates, zeros, trips, Decimal(1), Decimal(0), Decimal("0.25")
        )
    with pytest.raises(ValueError, match="finite"):
        arch151.FoldMetrics(dates, zeros, trips, Decimal(1), Decimal(1), Decimal("NaN"))
    with pytest.raises(ValueError, match="turnover cannot be negative"):
        arch151.FoldMetrics(
            dates, zeros, trips, Decimal(1), Decimal(1), Decimal("-0.01")
        )
    with pytest.raises(Arch151Error, match="aligned full-session"):
        arch151.FoldMetrics(
            dates, zeros[:-1], trips, Decimal(1), Decimal(1), Decimal("0.25")
        )


def test_development_aggregate_uses_summed_pf_and_chained_drawdown() -> None:
    slot = CANONICAL_SLOTS[0]
    profiles = {
        2019: {
            "return_events": ((250, Decimal("0.20")), (251, Decimal("-0.15"))),
            "gross_positive": Decimal("2"),
            "gross_negative": Decimal("1"),
            "annual_turnover": Decimal("0.10"),
        },
        2020: {
            "return_events": ((0, Decimal("-0.10")), (251, Decimal("0.20"))),
            "gross_positive": Decimal("0.1"),
            "gross_negative": Decimal("10"),
            "annual_turnover": Decimal("0.20"),
        },
    }
    batch = _evaluation_batch_for_slot(slot, profiles)
    aggregate = arch151.aggregate_development_economics(
        batch, arch151.FillCostCase.STRESS
    )
    assert aggregate.profit_factor.quantize(Decimal("0.000001")) == Decimal("0.578571")
    assert aggregate.max_drawdown > Decimal("0.23")
    assert aggregate.max_drawdown > max(
        record.metrics.max_drawdown
        for record in batch.records
        if record.economics_case is arch151.FillCostCase.STRESS
    )
    assert aggregate.turnover == Decimal("0.21")


def test_development_qualification_rejections_are_independently_testable() -> None:
    base = arch151.DevelopmentAggregate(
        CANONICAL_SLOTS[0].slot_id,
        arch151.FillCostCase.STRESS,
        Decimal("0.10"),
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
        is arch151.SelectionBiasStatus.DSR_COMPUTATION_DEFERRED
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
    assert selection.status is arch151.SelectionBiasStatus.DSR_COMPUTATION_DEFERRED
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


def test_final_freeze_requires_full_population_and_remains_zero_until_dsr_exists() -> (
    None
):
    batches = tuple(_evaluation_batch_for_slot(slot) for slot in CANONICAL_SLOTS)
    freeze = arch151.freeze_final_candidate_set(batches)
    assert freeze.source_manifest_id == CANONICAL_MANIFEST.manifest_id
    assert freeze.batch_digests == tuple(batch.batch_digest for batch in batches)
    assert freeze.economically_qualified_slot_ids == tuple(
        slot.slot_id for slot in CANONICAL_SLOTS
    )
    assert freeze.candidate_slot_id is None
    assert freeze.candidate_program_id is None
    assert (
        freeze.status
        is arch151.FinalFreezeStatus.ZERO_CANDIDATES_DSR_AUTHORITY_DEFERRED
    )
    assert (
        freeze.selection_bias_status
        is arch151.SelectionBiasStatus.DSR_COMPUTATION_DEFERRED
    )
    assert len(freeze.fingerprint) == 64
    assert arch151.freeze_final_candidate_set(batches).freeze_id == freeze.freeze_id
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
    with pytest.raises(arch151.AuthorizationUnavailableError, match="unavailable"):
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
