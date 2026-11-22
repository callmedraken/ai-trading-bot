"""Synthetic contract tests for the Architecture 150 foundation."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from decimal import Context, Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from trading_bot.experiments.arch150_intraday_ai import (
    BASE_COST,
    DISCOVERY_END,
    DISCOVERY_START,
    EXTENSION_FREQUENCY_POLICY,
    FOUNDATION_EFFECT_COUNTERS,
    G1_FAMILY_TRIAL_LIMIT,
    G1_TOTAL_TRIAL_LIMIT,
    HOLDOUT_FREQUENCY_POLICY,
    HOLDOUT_START,
    INITIAL_UNIVERSE,
    RECENT_EXTENSION_START,
    STRESS_COST,
    VALIDATION_FREQUENCY_POLICY,
    BarResolution,
    CandidateFreeze,
    CostCase,
    DiscoveryResultFreeze,
    FrequencyDiagnostics,
    G1PopulationManifest,
    IncompleteFiveMinuteAggregation,
    InformationFirewallError,
    IntradayBar,
    InvalidTrialReference,
    NoiseAreaVwapMomentumProgram,
    OpeningRangeBreakoutReversalProgram,
    OpeningRangeDirection,
    ResearchDataset,
    ResearchStage,
    StrategyFamily,
    TradeDirection,
    TrialBudgetExceeded,
    TrialDisposition,
    TrialLedger,
    UnsupportedProgramError,
    VwapReferenceSide,
    VwapStrategyMode,
    VwapTrendReversalProgram,
    aggregate_five_minute_bars,
    evaluate_frozen_trial,
    finalize_discovery_population,
    foundation_help,
    freeze_candidate_population,
    freeze_g1_population,
    open_discovery_dataset,
    open_holdout_dataset,
    open_recent_extension_dataset,
    open_validation_dataset,
    passes_frequency_gate,
    program_fingerprint,
    program_from_bytes,
    program_id,
    program_to_bytes,
    replay_program,
    selection_bias_input,
    validate_1_minute_bars,
)

_NY = ZoneInfo("America/New_York")


def _bar(
    symbol: str,
    day: date,
    offset_minutes: int,
    close: str = "100",
    *,
    volume: int = 100,
    high: str | None = None,
    low: str | None = None,
    seconds: int = 0,
    resolution: BarResolution = BarResolution.ONE_MINUTE,
) -> IntradayBar:
    local = datetime.combine(day, time(9, 30), _NY) + timedelta(
        minutes=offset_minutes, seconds=seconds
    )
    price = Decimal(close)
    return IntradayBar(
        symbol,
        local,
        price,
        Decimal(high) if high is not None else price,
        Decimal(low) if low is not None else price,
        price,
        volume,
        resolution,
    )


def _prices(day: date, values: list[str], symbol: str = "SPY") -> list[IntradayBar]:
    return [_bar(symbol, day, index, value) for index, value in enumerate(values)]


def _flat(day: date, count: int = 12, price: str = "100") -> list[IntradayBar]:
    return _prices(day, [price] * count)


def _universe_bars(day: date) -> list[IntradayBar]:
    return [_bar(symbol, day, 0) for symbol in INITIAL_UNIVERSE]


def _discovery_dataset(spy_bars: list[IntradayBar] | None = None) -> ResearchDataset:
    if spy_bars is None:
        spy_bars = [_bar("SPY", date(2020, 1, 2), 0)]
    day = spy_bars[0].session_date
    return open_discovery_dataset((*spy_bars, _bar("QQQ", day, 0)))


def _frozen_candidates(
    *, start_noise_band_bps: int = 1
) -> tuple[TrialLedger, G1PopulationManifest, DiscoveryResultFreeze, CandidateFreeze]:
    programs = (
        NoiseAreaVwapMomentumProgram(
            lookback_sessions=1,
            noise_band_bps=Decimal(start_noise_band_bps),
            confirmation_bars=1,
        ),
        VwapTrendReversalProgram(
            displacement_bps=Decimal(5),
            confirmation_bars=1,
            max_hold_minutes=1,
            cooldown_bars=0,
        ),
        OpeningRangeBreakoutReversalProgram(
            opening_range_minutes=5,
            direction=OpeningRangeDirection.CONTINUATION,
            entry_delay_bars=0,
            max_hold_minutes=5,
        ),
    )
    spy_bars = _prices(date(2020, 1, 2), ["100", "110", "110", "90", "90"])
    discovery = _discovery_dataset(spy_bars)
    manifest = freeze_g1_population(programs)
    ledger = TrialLedger(manifest)
    for slot in manifest.slots:
        evaluation = evaluate_frozen_trial(ledger, slot, discovery)
        disposition = (
            TrialDisposition.SHORTLISTED
            if evaluation.replay_result is not None and evaluation.replay_result.trades
            else None
        )
        ledger = ledger.consume(evaluation, disposition)
    finalized = finalize_discovery_population(discovery, ledger)
    frozen_candidates = freeze_candidate_population(finalized, ledger, (programs[1],))
    return ledger, manifest, finalized, frozen_candidates


def test_closed_program_serialization_and_semantic_parameters() -> None:
    programs = (
        NoiseAreaVwapMomentumProgram(noise_band_bps=Decimal("10.0")),
        VwapTrendReversalProgram(
            displacement_bps=Decimal("25.00"),
            mode=VwapStrategyMode.BOUNDED_REVERSAL,
            reference_side=VwapReferenceSide.BELOW,
        ),
        OpeningRangeBreakoutReversalProgram(direction=OpeningRangeDirection.REVERSAL),
    )
    assert tuple(program.family for program in programs) == tuple(StrategyFamily)
    assert program_fingerprint(programs[0]) == program_fingerprint(
        NoiseAreaVwapMomentumProgram(noise_band_bps=Decimal("10"))
    )
    assert program_id(programs[1]) == program_id(
        VwapTrendReversalProgram(
            displacement_bps=Decimal("25"),
            mode=VwapStrategyMode.BOUNDED_REVERSAL,
            reference_side=VwapReferenceSide.BELOW,
        )
    )
    assert all(
        program_from_bytes(program_to_bytes(program)) == program for program in programs
    )
    assert (
        len(
            {
                program_fingerprint(
                    VwapTrendReversalProgram(
                        mode=mode,
                        reference_side=side,
                    )
                )
                for mode in VwapStrategyMode
                for side in VwapReferenceSide
            }
        )
        == 4
    )


def test_arbitrary_and_arch148_opening_drive_programs_are_not_representable() -> None:
    with pytest.raises(UnsupportedProgramError):
        program_fingerprint(lambda _: True)  # type: ignore[arg-type]
    with pytest.raises(UnsupportedProgramError):
        program_from_bytes(
            b'{"schema":"arch150-typed-intraday-program/v1",'
            b'"family":"CUSTOM","source":"open("}'
        )
    with pytest.raises(ValueError):
        OpeningRangeBreakoutReversalProgram(max_hold_minutes=61)
    with pytest.raises(UnsupportedProgramError):
        program_from_bytes(
            b'{"schema":"arch150-typed-intraday-program/v1",'
            b'"family":"OPENING_RANGE_BREAKOUT_REVERSAL",'
            b'"opening_range_minutes":30,"direction":"CONTINUATION",'
            b'"entry_delay_bars":1,"max_hold_minutes":30,'
            b'"exit_window":"LAST_HALF_HOUR"}'
        )


def test_one_minute_validation_uses_published_xnys_boundaries() -> None:
    normal = date(2022, 1, 3)
    holiday = date(2022, 1, 17)
    weekend = date(2022, 1, 8)
    early_close = date(2023, 11, 24)
    assert validate_1_minute_bars([_bar("SPY", normal, 0)]).bars
    assert validate_1_minute_bars([_bar("SPY", early_close, 209)]).bars
    for invalid in (
        _bar("SPY", holiday, 0),
        _bar("SPY", weekend, 0),
        _bar("SPY", normal, -1),
        _bar("SPY", normal, 390),
        _bar("SPY", early_close, 210),
        _bar("SPY", normal, 0, seconds=30),
    ):
        with pytest.raises(ValueError):
            validate_1_minute_bars([invalid])
    with pytest.raises(ValueError, match="strictly chronological"):
        validate_1_minute_bars(
            [_bar("SPY", normal, 0), _bar("SPY", normal, 2), _bar("SPY", normal, 1)]
        )
    with pytest.raises(ValueError, match="resolution"):
        validate_1_minute_bars(
            [_bar("SPY", normal, 0, resolution=BarResolution.FIVE_MINUTE)]
        )


def test_aggregation_uses_elapsed_session_minutes_across_ten_oclock() -> None:
    day = date(2022, 1, 3)
    source = [_bar("SPY", day, offset, str(100 + offset)) for offset in range(25, 40)]
    aggregated = aggregate_five_minute_bars(validate_1_minute_bars(source))
    assert len(aggregated) == 3
    assert [bar.local_timestamp.time() for bar in aggregated] == [
        time(9, 55),
        time(10, 0),
        time(10, 5),
    ]
    assert aggregated[0].open == Decimal("125")
    assert aggregated[0].close == Decimal("129")
    assert aggregated[0].volume == 500
    assert all(bar.resolution is BarResolution.FIVE_MINUTE for bar in aggregated)
    assert aggregate_five_minute_bars(validate_1_minute_bars(source)) == aggregated
    with pytest.raises(ValueError, match="resolution"):
        validate_1_minute_bars(aggregated)


def test_aggregation_fails_closed_for_partial_or_nonconsecutive_minutes() -> None:
    day = date(2022, 1, 3)
    missing = [_bar("SPY", day, offset) for offset in range(25, 40) if offset != 27]
    partial = [_bar("SPY", day, offset) for offset in (25, 26, 27, 28)]
    for source in (missing, partial):
        with pytest.raises(IncompleteFiveMinuteAggregation):
            aggregate_five_minute_bars(validate_1_minute_bars(source))


def test_aggregation_stays_inside_an_early_close_session() -> None:
    early_close = date(2023, 11, 24)
    source = [_bar("SPY", early_close, offset) for offset in range(210)]
    aggregated = aggregate_five_minute_bars(validate_1_minute_bars(source))
    assert len(aggregated) == 42
    assert aggregated.sessions == (early_close,)
    assert aggregated[0].local_timestamp.time() == time(9, 30)
    assert aggregated[-1].local_timestamp.time() == time(12, 55)
    assert aggregated[-1].timestamp + timedelta(minutes=5) == datetime.combine(
        early_close, time(13, 0), _NY
    ).astimezone(aggregated[-1].timestamp.tzinfo)


def test_validation_requires_an_immutable_candidate_freeze_after_full_population() -> (
    None
):
    bars = _universe_bars(date(2022, 1, 3))
    with pytest.raises(InformationFirewallError, match="candidate-freeze"):
        open_validation_dataset(bars)
    ledger, manifest, finalized, candidates = _frozen_candidates()
    assert len(manifest.slots) == 3
    assert ledger.is_complete
    assert ledger.consumed_trial_count == len(manifest.slots)
    assert tuple(ledger.family_counts.values()) == (1, 1, 1)
    assert candidates.population_manifest_id == manifest.manifest_id
    assert candidates.discovery_result_freeze_id == finalized.freeze_id
    assert candidates.discovery_dataset_id == finalized.discovery_dataset_id
    assert candidates.ledger_id == ledger.ledger_id
    with pytest.raises(InformationFirewallError, match="frozen G1 manifest"):
        TrialLedger(ledger.records)  # type: ignore[call-arg]
    with pytest.raises(InformationFirewallError, match="frozen-slot consumption"):
        TrialLedger(manifest, ledger.records)
    with pytest.raises(AttributeError, match="immutable"):
        ledger._records = ()
    validation = open_validation_dataset(bars, candidates)
    assert validation.stage is ResearchStage.VALIDATION
    assert validation.candidate_freeze == candidates
    assert validation.candidate_program_ids == (
        program_id(
            VwapTrendReversalProgram(
                displacement_bps=Decimal(5),
                confirmation_bars=1,
                max_hold_minutes=1,
                cooldown_bars=0,
            )
        ),
    )
    with pytest.raises(InformationFirewallError):
        CandidateFreeze(
            candidates.freeze_id,
            manifest.manifest_id,
            finalized.freeze_id,
            finalized.discovery_dataset_id,
            ledger.ledger_id,
            candidates.candidate_program_ids,
            candidates.candidate_fingerprints,
        )


def test_freeze_artifact_cannot_be_rebound_to_another_trial_population() -> None:
    ledger, manifest, population, _ = _frozen_candidates()
    other_ledger, other_manifest, other_population, _ = _frozen_candidates(
        start_noise_band_bps=30
    )
    other_program = NoiseAreaVwapMomentumProgram(
        lookback_sessions=1,
        noise_band_bps=Decimal("30"),
        confirmation_bars=1,
    )
    assert population.ledger_id == ledger.ledger_id
    assert manifest.manifest_id != other_manifest.manifest_id
    assert other_population.freeze_id != population.freeze_id
    with pytest.raises(
        InformationFirewallError, match="completed exact G1 result ledger"
    ):
        freeze_candidate_population(population, other_ledger, (other_program,))


def test_public_dataset_construction_and_later_stages_cannot_bypass_firewall() -> None:
    discovery = open_discovery_dataset(_universe_bars(date(2020, 1, 2)))
    assert discovery.stage is ResearchStage.DISCOVERY
    assert (discovery.start, discovery.end_exclusive) == (
        DISCOVERY_START,
        DISCOVERY_END,
    )
    with pytest.raises(TypeError):
        discovery.bars.by_symbol["SPY"] = discovery.bars.by_symbol["QQQ"]
    with pytest.raises(InformationFirewallError, match="stage authority"):
        ResearchDataset(
            ResearchStage.VALIDATION,
            discovery.bars,
            date(2021, 1, 1),
            date(2024, 1, 1),
        )
    with pytest.raises(InformationFirewallError):
        open_discovery_dataset(_universe_bars(date(2021, 1, 4)))
    with pytest.raises(InformationFirewallError):
        open_holdout_dataset(_universe_bars(HOLDOUT_START))
    with pytest.raises(InformationFirewallError):
        open_recent_extension_dataset(_universe_bars(RECENT_EXTENSION_START))
    _, _, _, freeze = _frozen_candidates()
    for opener in (
        open_discovery_dataset,
        lambda bars: open_validation_dataset(bars, freeze),
    ):
        with pytest.raises(InformationFirewallError):
            opener(_universe_bars(date(2026, 11, 2)))
    with pytest.raises(InformationFirewallError):
        ResearchDataset(
            ResearchStage.HOLDOUT,
            discovery.bars,
            HOLDOUT_START,
            date(2026, 1, 1),
        )


def test_family_a_uses_prior_session_noise_vwap_confirmation_and_elapsed_hold() -> None:
    day_one = date(2022, 1, 3)
    day_two = date(2022, 1, 4)
    current = date(2022, 1, 5)
    noisy_prior = _prices(day_one, ["100", "120", "100", "100"] + ["100"] * 8)
    quiet_prior = _flat(day_two)
    current_bars = _prices(current, ["100", "100", "100", "102.5"] + ["102.5"] * 8)
    input_bars = noisy_prior + quiet_prior + current_bars
    lookback_one = NoiseAreaVwapMomentumProgram(
        lookback_sessions=1,
        noise_band_bps=Decimal("5"),
        confirmation_bars=1,
        max_hold_minutes=1,
    )
    lookback_two = replace(lookback_one, lookback_sessions=2)
    low_floor = replay_program(lookback_one, input_bars)
    wide_floor = replay_program(
        replace(lookback_one, noise_band_bps=Decimal("250")), input_bars
    )
    two_confirmations = replay_program(
        replace(lookback_one, confirmation_bars=2), input_bars
    )
    current_trades = tuple(
        trade for trade in low_floor.trades if trade.session == current
    )
    assert current_trades and current_trades[0].direction is TradeDirection.LONG
    assert not any(
        trade.session == current
        for trade in replay_program(lookback_two, input_bars).trades
    )
    assert not any(trade.session == current for trade in wide_floor.trades)
    confirmed = tuple(
        trade for trade in two_confirmations.trades if trade.session == current
    )
    assert confirmed and confirmed[0].entry.timestamp - current_trades[
        0
    ].entry.timestamp == timedelta(minutes=1)
    longer_hold = replay_program(replace(lookback_one, max_hold_minutes=3), input_bars)
    longer = next(trade for trade in longer_hold.trades if trade.session == current)
    assert longer.exit.timestamp - longer.entry.timestamp == timedelta(minutes=3)


def test_family_a_noise_is_lagged_and_supports_downside_momentum() -> None:
    first = date(2022, 1, 3)
    second = date(2022, 1, 4)
    signal_day = date(2022, 1, 5)
    future = date(2022, 1, 6)
    previous = _flat(first) + _flat(second)
    down = _prices(signal_day, ["100", "100", "100", "97.5"] + ["97.5"] * 8)
    program = NoiseAreaVwapMomentumProgram(
        lookback_sessions=2,
        noise_band_bps=Decimal("5"),
        confirmation_bars=1,
        max_hold_minutes=2,
    )
    before = replay_program(program, previous + down)
    with_future = replay_program(
        program,
        previous + down + _prices(future, ["100", "100", "100", "200"] + ["200"] * 8),
    )
    first_day_trades = tuple(
        trade for trade in before.trades if trade.session == signal_day
    )
    future_day_trades = tuple(
        trade for trade in with_future.trades if trade.session == signal_day
    )
    assert first_day_trades and first_day_trades[0].direction is TradeDirection.SHORT
    assert first_day_trades == future_day_trades


def test_family_b_modes_sides_threshold_confirmation_and_hold_have_behavior() -> None:
    up_day = date(2022, 1, 3)
    down_day = date(2022, 1, 4)
    up = _prices(
        up_day,
        [str(Decimal("100") + Decimal(index) / Decimal("100")) for index in range(20)],
    )
    down = _prices(
        down_day,
        [str(Decimal("120") - Decimal(index) / Decimal("100")) for index in range(20)],
    )
    base = VwapTrendReversalProgram(
        displacement_bps=Decimal("5"),
        mode=VwapStrategyMode.CONTINUATION,
        reference_side=VwapReferenceSide.ABOVE,
        confirmation_bars=1,
        max_hold_minutes=1,
        cooldown_bars=0,
    )
    long_trades = replay_program(base, up).trades
    assert long_trades and long_trades[0].direction is TradeDirection.LONG
    assert not replay_program(replace(base, displacement_bps=Decimal("500")), up).trades
    confirmed = replay_program(replace(base, confirmation_bars=2), up).trades
    assert confirmed and confirmed[0].entry.timestamp > long_trades[0].entry.timestamp
    longer = replay_program(replace(base, max_hold_minutes=3), up).trades
    assert longer[0].exit.timestamp - longer[0].entry.timestamp == timedelta(minutes=3)
    reversal = replay_program(
        replace(base, mode=VwapStrategyMode.BOUNDED_REVERSAL), up
    ).trades
    assert reversal and reversal[0].direction is TradeDirection.SHORT
    below_short = replay_program(
        replace(base, reference_side=VwapReferenceSide.BELOW), down
    ).trades
    assert below_short and below_short[0].direction is TradeDirection.SHORT
    below_reversal = replay_program(
        replace(
            base,
            mode=VwapStrategyMode.BOUNDED_REVERSAL,
            reference_side=VwapReferenceSide.BELOW,
        ),
        down,
    ).trades
    assert below_reversal and below_reversal[0].direction is TradeDirection.LONG


def test_family_b_cooldown_enforces_sequential_nonoverlapping_reentry() -> None:
    day = date(2022, 1, 3)
    bars = _prices(day, [str(100 + index) for index in range(30)])
    base = VwapTrendReversalProgram(
        displacement_bps=Decimal("5"),
        confirmation_bars=1,
        max_hold_minutes=1,
        cooldown_bars=0,
    )
    no_cooldown = replay_program(base, bars).trades
    cooldown = replay_program(replace(base, cooldown_bars=2), bars).trades
    assert len(no_cooldown) >= 4
    assert len(cooldown) < len(no_cooldown)
    assert cooldown[1].entry.timestamp - cooldown[0].entry.timestamp == (
        no_cooldown[1].entry.timestamp
        - no_cooldown[0].entry.timestamp
        + timedelta(minutes=2)
    )
    assert all(
        left.exit.timestamp <= right.entry.timestamp
        for left, right in zip(no_cooldown, no_cooldown[1:], strict=False)
    )
    assert all(trade.session == day for trade in no_cooldown)


def test_family_c_range_delay_direction_and_hold_are_behavioral() -> None:
    day = date(2022, 1, 3)
    bars = [_bar("SPY", day, offset, "100") for offset in range(45)]
    bars[5:] = [_bar("SPY", day, offset, "103") for offset in range(5, 45)]
    bars[10] = _bar("SPY", day, 10, "100", high="104")
    bars[15] = _bar("SPY", day, 15, "100")
    short_range = OpeningRangeBreakoutReversalProgram(
        opening_range_minutes=5,
        direction=OpeningRangeDirection.CONTINUATION,
        entry_delay_bars=0,
        max_hold_minutes=1,
    )
    long_range = replace(short_range, opening_range_minutes=15)
    short_range_trades = replay_program(short_range, bars).trades
    assert short_range_trades and short_range_trades[0].direction is TradeDirection.LONG
    assert not replay_program(long_range, bars).trades
    delayed = replay_program(replace(short_range, entry_delay_bars=2), bars).trades
    assert delayed and delayed[0].entry.timestamp - short_range_trades[
        0
    ].entry.timestamp == timedelta(minutes=2)
    reversal = replay_program(
        replace(short_range, direction=OpeningRangeDirection.REVERSAL), bars
    ).trades
    assert reversal and reversal[0].direction is TradeDirection.SHORT
    longer = replay_program(replace(short_range, max_hold_minutes=3), bars).trades
    assert longer[0].exit.timestamp - longer[0].entry.timestamp == timedelta(minutes=3)


def test_five_minute_view_preserves_opening_range_and_hold_minutes() -> None:
    day = date(2022, 1, 3)
    source = [
        _bar("SPY", day, offset, "100" if offset < 30 else "102")
        for offset in range(70)
    ]
    minute_stream = validate_1_minute_bars(source)
    five_minute_stream = aggregate_five_minute_bars(minute_stream)
    program = OpeningRangeBreakoutReversalProgram(
        opening_range_minutes=30,
        direction=OpeningRangeDirection.CONTINUATION,
        entry_delay_bars=0,
        max_hold_minutes=10,
    )
    one_minute_trade = replay_program(program, minute_stream).trades[0]
    five_minute_trade = replay_program(program, five_minute_stream).trades[0]
    assert one_minute_trade.entry.timestamp - _bar(
        "SPY", day, 0
    ).timestamp >= timedelta(minutes=30)
    assert five_minute_trade.entry.timestamp - _bar(
        "SPY", day, 0
    ).timestamp >= timedelta(minutes=30)
    assert (
        one_minute_trade.exit.timestamp - one_minute_trade.entry.timestamp
        == timedelta(minutes=10)
    )
    assert (
        five_minute_trade.exit.timestamp - five_minute_trade.entry.timestamp
        == timedelta(minutes=10)
    )


def test_long_and_short_fills_use_adverse_stress_slippage() -> None:
    up = _prices(date(2022, 1, 3), [str(100 + index) for index in range(8)])
    down = _prices(date(2022, 1, 4), [str(108 - index) for index in range(8)])
    long_program = VwapTrendReversalProgram(
        displacement_bps=Decimal("5"),
        confirmation_bars=1,
        max_hold_minutes=1,
        cooldown_bars=0,
    )
    short_program = replace(
        long_program,
        reference_side=VwapReferenceSide.BELOW,
    )
    long_trade = replay_program(long_program, up, cost_case=CostCase.STRESS).trades[0]
    short_trade = replay_program(short_program, down, cost_case=CostCase.STRESS).trades[
        0
    ]
    assert long_trade.entry.side.value == "BUY" and long_trade.exit.side.value == "SELL"
    assert (
        short_trade.entry.side.value == "SELL" and short_trade.exit.side.value == "BUY"
    )
    assert long_trade.entry.execution_price > long_trade.entry.reference_price
    assert long_trade.exit.execution_price < long_trade.exit.reference_price
    assert short_trade.entry.execution_price < short_trade.entry.reference_price
    assert short_trade.exit.execution_price > short_trade.exit.reference_price
    assert (
        long_trade.entry.slippage_bps == short_trade.entry.slippage_bps == Decimal("5")
    )
    assert BASE_COST.adverse_slippage_bps == Decimal("2")
    assert STRESS_COST.adverse_slippage_bps == Decimal("5")


def test_running_equity_limits_next_session_gross_exposure() -> None:
    loss_day = date(2022, 1, 3)
    next_day = date(2022, 1, 4)
    bars = _prices(loss_day, ["100", "110", "110", "90", "90"])
    bars += _prices(next_day, ["100", "110", "110", "110"])
    program = VwapTrendReversalProgram(
        displacement_bps=Decimal("5"),
        confirmation_bars=1,
        max_hold_minutes=1,
        cooldown_bars=0,
    )
    result = replay_program(program, bars, initial_equity=Decimal("100"))
    first = next(trade for trade in result.trades if trade.session == loss_day)
    second = next(trade for trade in result.trades if trade.session == next_day)
    assert first.net_pnl < 0
    assert second.equity_before == first.equity_after < first.equity_before
    assert second.gross_exposure_fraction <= Decimal("1")
    with localcontext(Context(prec=80)):
        assert (
            second.entry.execution_price * second.entry.quantity <= second.equity_before
        )
    with localcontext(Context(prec=80)):
        assert result.final_equity == result.initial_equity + result.net_pnl
    assert result.maximum_gross_exposure <= Decimal("1")


def test_frequency_advancement_is_stress_only_for_all_promotion_policies() -> None:
    exact = FrequencyDiagnostics(
        CostCase.STRESS,
        (2021, 2022, 2023),
        ((2021, 100), (2022, 100), (2023, 100)),
        100,
        35,
        (1, 2, 3),
        Decimal("100"),
        Decimal("0.35"),
        Decimal("3"),
        Decimal("3"),
    )
    for policy in (
        VALIDATION_FREQUENCY_POLICY,
        HOLDOUT_FREQUENCY_POLICY,
        EXTENSION_FREQUENCY_POLICY,
    ):
        assert passes_frequency_gate(exact, policy)
        assert not passes_frequency_gate(
            replace(exact, cost_case=CostCase.BASE), policy
        )
        assert not passes_frequency_gate(
            replace(exact, cost_case=CostCase.ZERO), policy
        )


def test_g1_manifest_freezes_ordered_proposals_before_any_result() -> None:
    first = NoiseAreaVwapMomentumProgram()
    second = VwapTrendReversalProgram()
    proposals = (first, second, first)
    manifest = freeze_g1_population(proposals)
    same_manifest = freeze_g1_population(proposals)
    reordered = freeze_g1_population((second, first, first))
    ledger = TrialLedger(manifest)

    assert isinstance(manifest, G1PopulationManifest)
    assert len(manifest.slots) == 3 < G1_TOTAL_TRIAL_LIMIT
    assert manifest.manifest_id == same_manifest.manifest_id
    assert manifest.manifest_id != reordered.manifest_id
    assert tuple(slot.ordinal for slot in manifest.slots) == (1, 2, 3)
    assert manifest.slots[0].slot_id != manifest.slots[2].slot_id
    assert manifest.slots[0].program_id == manifest.slots[2].program_id
    assert b'"disposition"' not in manifest.to_bytes()
    assert ledger.records == ()
    assert ledger.manifest.manifest_id == manifest.manifest_id
    assert not hasattr(manifest.slots[0], "disposition")
    with pytest.raises(AttributeError):
        manifest.slots[0].program_id = program_id(second)  # type: ignore[misc]
    with pytest.raises(TrialBudgetExceeded, match="at least one"):
        freeze_g1_population(())


def test_g1_manifest_enforces_total_and_family_ceilings() -> None:
    family_a = tuple(
        NoiseAreaVwapMomentumProgram(noise_band_bps=Decimal(index + 1))
        for index in range(G1_FAMILY_TRIAL_LIMIT + 1)
    )
    with pytest.raises(TrialBudgetExceeded, match="family trial budget"):
        freeze_g1_population(family_a)
    over_total = (
        tuple(
            NoiseAreaVwapMomentumProgram(noise_band_bps=Decimal(index + 1))
            for index in range(G1_FAMILY_TRIAL_LIMIT)
        )
        + tuple(
            VwapTrendReversalProgram(displacement_bps=Decimal(index + 1))
            for index in range(G1_FAMILY_TRIAL_LIMIT)
        )
        + tuple(
            OpeningRangeBreakoutReversalProgram(
                opening_range_minutes=5,
                entry_delay_bars=index,
            )
            for index in range(G1_FAMILY_TRIAL_LIMIT)
        )
        + (VwapTrendReversalProgram(displacement_bps=Decimal(99)),)
    )
    with pytest.raises(TrialBudgetExceeded, match="total trial budget"):
        freeze_g1_population(over_total)


def test_g1_evaluation_requires_exact_next_slot_and_cannot_be_consumed_twice() -> None:
    first_program = VwapTrendReversalProgram(
        displacement_bps=Decimal(5),
        confirmation_bars=1,
        max_hold_minutes=1,
        cooldown_bars=0,
    )
    second_program = OpeningRangeBreakoutReversalProgram(
        opening_range_minutes=5, entry_delay_bars=0, max_hold_minutes=5
    )
    manifest = freeze_g1_population((first_program, second_program))
    ledger = TrialLedger(manifest)
    trend_bars = _prices(date(2020, 1, 2), ["100", "110", "110", "90", "90"])
    discovery = _discovery_dataset(trend_bars)

    with pytest.raises(InformationFirewallError, match="exact next frozen"):
        evaluate_frozen_trial(ledger, manifest.slots[1], discovery)
    with pytest.raises(InformationFirewallError, match="opened discovery dataset"):
        evaluate_frozen_trial(ledger, manifest.slots[0], trend_bars)  # type: ignore[arg-type]
    first_result = evaluate_frozen_trial(ledger, manifest.slots[0], discovery)
    assert first_result.replay_result is not None
    assert first_result.replay_result.trades
    with pytest.raises(InformationFirewallError, match="not authorized"):
        ledger.consume(first_program, TrialDisposition.SHORTLISTED)  # type: ignore[arg-type]

    ledger_after_first = ledger.consume(
        first_result, TrialDisposition.ECONOMICALLY_REJECTED
    )
    with pytest.raises(InformationFirewallError, match="exact next frozen"):
        evaluate_frozen_trial(ledger_after_first, manifest.slots[0], discovery)
    with pytest.raises(InformationFirewallError, match="next frozen population slot"):
        ledger_after_first.consume(first_result)
    second_result = evaluate_frozen_trial(
        ledger_after_first,
        manifest.slots[1],
        discovery,
    )
    completed = ledger_after_first.consume(second_result)
    assert completed.is_complete
    assert len(completed.records) == len(manifest.slots)
    with pytest.raises(TrialBudgetExceeded, match="all frozen"):
        evaluate_frozen_trial(completed, manifest.slots[1], discovery)


def test_invalid_and_duplicate_proposals_consume_their_frozen_slots() -> None:
    program = VwapTrendReversalProgram()
    invalid = InvalidTrialReference(
        StrategyFamily.OPENING_RANGE_BREAKOUT_REVERSAL,
        "caller-invalid-hypothesis-v1",
        "PROGRAM_PARSE_REJECTED",
    )
    manifest = freeze_g1_population((program, program, invalid))
    assert manifest.slots[0].slot_id != manifest.slots[1].slot_id
    assert manifest.slots[0].program_id == manifest.slots[1].program_id
    ledger = TrialLedger(manifest)
    bars = _prices(date(2020, 1, 2), ["100", "110", "110", "90", "90"])
    discovery = _discovery_dataset(bars)
    first = evaluate_frozen_trial(ledger, manifest.slots[0], discovery)
    ledger = ledger.consume(first, TrialDisposition.SHORTLISTED)
    duplicate = evaluate_frozen_trial(ledger, manifest.slots[1], discovery)
    assert duplicate.fixed_disposition is TrialDisposition.DUPLICATE
    ledger = ledger.consume(duplicate)
    invalid_result = evaluate_frozen_trial(ledger, manifest.slots[2], discovery)
    assert invalid_result.fixed_disposition is TrialDisposition.INVALID
    ledger = ledger.consume(invalid_result)
    assert tuple(record.disposition for record in ledger.records) == (
        TrialDisposition.SHORTLISTED,
        TrialDisposition.DUPLICATE,
        TrialDisposition.INVALID,
    )
    assert ledger.records[1].slot_id == manifest.slots[1].slot_id
    assert ledger.records[2].slot_id == manifest.slots[2].slot_id


def test_frozen_slot_and_ledger_cannot_be_rebound_or_accept_absent_programs() -> None:
    program = VwapTrendReversalProgram()
    manifest = freeze_g1_population((program,))
    other_manifest = freeze_g1_population(
        (replace(program, displacement_bps=Decimal(30)),)
    )
    ledger = TrialLedger(manifest)
    discovery = _discovery_dataset(_flat(date(2020, 1, 2)))
    with pytest.raises(InformationFirewallError, match="exact next frozen"):
        evaluate_frozen_trial(ledger, other_manifest.slots[0], discovery)
    with pytest.raises(InformationFirewallError, match="not authorized"):
        ledger.consume(
            VwapTrendReversalProgram(displacement_bps=Decimal(31)),
            TrialDisposition.FAILED,
        )  # type: ignore[arg-type]


def test_completed_discovery_freeze_gates_candidates_and_validation() -> None:
    manifest = freeze_g1_population(
        (
            VwapTrendReversalProgram(
                displacement_bps=Decimal(5),
                confirmation_bars=1,
                max_hold_minutes=1,
                cooldown_bars=0,
            ),
            NoiseAreaVwapMomentumProgram(),
        )
    )
    ledger = TrialLedger(manifest)
    trend_bars = _prices(date(2020, 1, 2), ["100", "110", "110", "90", "90"])
    discovery = _discovery_dataset(trend_bars)
    with pytest.raises(InformationFirewallError, match="every frozen G1 proposal"):
        finalize_discovery_population(discovery, ledger)
    with pytest.raises(
        InformationFirewallError, match="completed exact G1 result ledger"
    ):
        freeze_candidate_population(None, ledger, ())  # type: ignore[arg-type]

    candidate = manifest.slots[0]._program
    assert candidate is not None
    first = evaluate_frozen_trial(ledger, manifest.slots[0], discovery)
    ledger = ledger.consume(first, TrialDisposition.SHORTLISTED)
    second = evaluate_frozen_trial(ledger, manifest.slots[1], discovery)
    ledger = ledger.consume(second)
    with pytest.raises(InformationFirewallError, match="different discovery dataset"):
        finalize_discovery_population(
            _discovery_dataset(_flat(date(2020, 1, 2))), ledger
        )
    finalized = finalize_discovery_population(discovery, ledger)
    freeze = freeze_candidate_population(finalized, ledger, (candidate,))
    assert freeze.population_manifest_id == manifest.manifest_id
    assert freeze.ledger_id == ledger.ledger_id
    with pytest.raises(InformationFirewallError, match="not shortlisted"):
        freeze_candidate_population(
            finalized,
            ledger,
            (NoiseAreaVwapMomentumProgram(),),
        )
    with pytest.raises(InformationFirewallError, match="candidate-freeze"):
        open_validation_dataset(_universe_bars(date(2022, 1, 3)))
    validation = open_validation_dataset(_universe_bars(date(2022, 1, 3)), freeze)
    assert validation
    with pytest.raises(InformationFirewallError, match="opened discovery dataset"):
        evaluate_frozen_trial(ledger, manifest.slots[0], validation)


def test_selection_bias_binds_every_completed_frozen_attempt() -> None:
    duplicate = VwapTrendReversalProgram(
        displacement_bps=Decimal(5),
        confirmation_bars=1,
        max_hold_minutes=1,
        cooldown_bars=0,
    )
    invalid = InvalidTrialReference(
        StrategyFamily.NOISE_AREA_VWAP_MOMENTUM,
        "invalid-attempt-v1",
        "INVALID_TYPED_PROPOSAL",
    )
    failed = OpeningRangeBreakoutReversalProgram(
        opening_range_minutes=5, entry_delay_bars=0, max_hold_minutes=5
    )
    zero_trade = NoiseAreaVwapMomentumProgram()
    proposals = (duplicate, duplicate, invalid, failed, zero_trade)
    manifest = freeze_g1_population(proposals)
    ledger = TrialLedger(manifest)
    discovery = _discovery_dataset(
        _prices(date(2020, 1, 2), ["100", "110", "110", "90", "90"])
    )
    for slot in manifest.slots:
        evaluation = evaluate_frozen_trial(
            ledger,
            slot,
            discovery,
            initial_equity=Decimal("-1") if slot.ordinal == 4 else Decimal("1"),
        )
        disposition = (
            TrialDisposition.ECONOMICALLY_REJECTED if slot.ordinal == 1 else None
        )
        ledger = ledger.consume(evaluation, disposition)
    assert tuple(record.disposition for record in ledger.records) == (
        TrialDisposition.ECONOMICALLY_REJECTED,
        TrialDisposition.DUPLICATE,
        TrialDisposition.INVALID,
        TrialDisposition.FAILED,
        TrialDisposition.ZERO_TRADE,
    )
    finalized = finalize_discovery_population(discovery, ledger)
    bias = selection_bias_input(finalized, ledger)
    assert bias.consumed_trial_count == len(manifest.slots) == 5
    assert bias.population_manifest_id == manifest.manifest_id
    assert bias.discovery_result_freeze_id == finalized.freeze_id
    assert bias.slot_ids == tuple(slot.slot_id for slot in manifest.slots)
    assert bias.trial_ids == tuple(record.trial_id for record in ledger.records)
    assert bias.result_ids == tuple(record.result_id for record in ledger.records)
    assert bias.program_ids[0] == bias.program_ids[1]
    assert bias.program_ids[2] is None
    assert TrialDisposition.FAILED in bias.dispositions
    assert TrialDisposition.DUPLICATE in bias.dispositions
    assert TrialDisposition.INVALID in bias.dispositions
    assert TrialDisposition.ZERO_TRADE in bias.dispositions
    assert b"population_manifest_id" in bias.to_bytes()


def test_selection_bias_and_effect_free_arch150_surface_leave_arch149_untouched() -> (
    None
):
    manifest = freeze_g1_population((NoiseAreaVwapMomentumProgram(),))
    ledger = TrialLedger(manifest)
    discovery = _discovery_dataset(_flat(date(2020, 1, 2)))
    zero_trade = evaluate_frozen_trial(
        ledger,
        manifest.slots[0],
        discovery,
    )
    ledger = ledger.consume(zero_trade)
    finalized = finalize_discovery_population(discovery, ledger)
    bias = selection_bias_input(finalized, ledger)
    assert bias.consumed_trial_count == 1
    assert bias.trial_ids == (ledger.records[0].trial_id,)
    assert bias.ledger_id == ledger.ledger_id
    assert b"arch150-selection-bias-input/v2" in bias.to_bytes()
    assert foundation_help().startswith("Architecture 150 foundation")
    assert (
        FOUNDATION_EFFECT_COUNTERS.provider_calls,
        FOUNDATION_EFFECT_COUNTERS.credential_reads,
        FOUNDATION_EFFECT_COUNTERS.robinhood_calls,
        FOUNDATION_EFFECT_COUNTERS.broker_effects,
        FOUNDATION_EFFECT_COUNTERS.order_effects,
        FOUNDATION_EFFECT_COUNTERS.production_mutations,
        FOUNDATION_EFFECT_COUNTERS.final_holdout_opens,
    ) == (0, 0, 0, 0, 0, 0, 0)

    source_path = (
        Path(__file__)
        .parents[2]
        .joinpath("src/trading_bot/experiments/arch150_intraday_ai.py")
    )
    source = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = {
        node.module or alias.name
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    } | {
        alias.name
        for node in ast.walk(source)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any(
        name.startswith(("alpaca", "robinhood", "requests", "openai", "arch149"))
        for name in imports
    )
