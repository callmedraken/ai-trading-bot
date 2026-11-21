"""Synthetic contract tests for the Architecture 150 foundation."""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

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
    CostCase,
    FrequencyDiagnostics,
    InformationFirewallError,
    IntradayBar,
    NoiseAreaVwapMomentumProgram,
    OpeningRangeBreakoutReversalProgram,
    OpeningRangeDirection,
    ResearchStage,
    StrategyFamily,
    TrialDisposition,
    TrialLedger,
    UnsupportedProgramError,
    VwapTrendReversalProgram,
    aggregate_five_minute_bars,
    compute_frequency_diagnostics,
    foundation_help,
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
    validate_universe_minute_bars,
)


def _bar(
    symbol: str,
    day: date,
    minute: int,
    close: str = "100",
    *,
    volume: int = 100,
) -> IntradayBar:
    local = datetime(day.year, day.month, day.day, 9, 30) + timedelta(minutes=minute)
    from zoneinfo import ZoneInfo

    timestamp = local.replace(tzinfo=ZoneInfo("America/New_York"))
    price = Decimal(close)
    return IntradayBar(symbol, timestamp, price, price, price, price, volume)


def _session_bars(day: date, symbol: str = "SPY") -> list[IntradayBar]:
    closes = ["100", "99", "101", "101.5", "102", "103", "104"]
    return [_bar(symbol, day, index, close) for index, close in enumerate(closes)]


def _universe_bars(day: date) -> list[IntradayBar]:
    return [_bar(symbol, day, 0) for symbol in INITIAL_UNIVERSE]


def test_closed_typed_program_families_have_stable_semantic_identities() -> None:
    programs = (
        NoiseAreaVwapMomentumProgram(noise_band_bps=Decimal("10.0")),
        VwapTrendReversalProgram(displacement_bps=Decimal("25.00")),
        OpeningRangeBreakoutReversalProgram(direction=OpeningRangeDirection.REVERSAL),
    )
    assert tuple(program.family for program in programs) == tuple(StrategyFamily)
    assert program_fingerprint(programs[0]) == program_fingerprint(
        NoiseAreaVwapMomentumProgram(noise_band_bps=Decimal("10"))
    )
    assert program_id(programs[1]) == program_id(
        VwapTrendReversalProgram(displacement_bps=Decimal("25"))
    )
    assert all(
        program_from_bytes(program_to_bytes(program)) == program for program in programs
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
        OpeningRangeBreakoutReversalProgram(max_hold_bars=61)
    with pytest.raises(UnsupportedProgramError):
        program_from_bytes(
            b'{"schema":"arch150-typed-intraday-program/v1",'
            b'"family":"OPENING_RANGE_BREAKOUT_REVERSAL",'
            b'"opening_range_minutes":30,"direction":"CONTINUATION",'
            b'"entry_delay_bars":1,"max_hold_bars":30,'
            b'"exit_window":"LAST_HALF_HOUR"}'
        )


def test_universe_order_and_minute_validation_reject_malformed_input() -> None:
    assert INITIAL_UNIVERSE == ("SPY", "QQQ")
    validated = validate_universe_minute_bars(_universe_bars(date(2020, 1, 2)))
    assert tuple(validated.by_symbol) == INITIAL_UNIVERSE
    bars = _session_bars(date(2020, 1, 2))
    with pytest.raises(ValueError, match="strictly chronological"):
        validate_1_minute_bars([bars[0], bars[2], bars[1]])
    with pytest.raises(ValueError, match="strictly chronological"):
        validate_1_minute_bars([bars[0], bars[0]])
    with pytest.raises(ValueError, match="regular XNYS"):
        validate_1_minute_bars([_bar("SPY", date(2020, 1, 2), -1)])


def test_five_minute_aggregation_is_deterministic_and_session_bounded() -> None:
    bars = [
        _bar("SPY", date(2020, 1, 2), index, str(100 + index)) for index in range(10)
    ]
    aggregated = aggregate_five_minute_bars(validate_1_minute_bars(bars))
    assert len(aggregated) == 2
    assert aggregated[0].open == Decimal("100")
    assert aggregated[0].close == Decimal("104")
    assert aggregated[0].volume == 500
    assert aggregated == aggregate_five_minute_bars(validate_1_minute_bars(bars))


def test_information_firewall_allows_only_discovery_and_validation_windows() -> None:
    discovery = open_discovery_dataset(_universe_bars(date(2020, 1, 2)))
    assert discovery.stage is ResearchStage.DISCOVERY
    assert (discovery.start, discovery.end_exclusive) == (
        DISCOVERY_START,
        DISCOVERY_END,
    )
    validation = open_validation_dataset(_universe_bars(date(2022, 1, 3)))
    assert validation.stage is ResearchStage.VALIDATION
    assert validation.start == date(2021, 1, 1)
    with pytest.raises(InformationFirewallError):
        open_discovery_dataset(_universe_bars(date(2021, 1, 4)))
    with pytest.raises(InformationFirewallError):
        open_holdout_dataset(_universe_bars(HOLDOUT_START))
    with pytest.raises(InformationFirewallError):
        open_recent_extension_dataset(_universe_bars(RECENT_EXTENSION_START))
    with pytest.raises(InformationFirewallError):
        open_validation_dataset(_universe_bars(date(2026, 11, 2)))


def test_cost_cases_and_session_flat_replay_are_deterministic() -> None:
    program = NoiseAreaVwapMomentumProgram(max_hold_bars=60)
    bars = validate_1_minute_bars(_session_bars(date(2022, 1, 3)))
    zero = replay_program(program, bars, cost_case=CostCase.ZERO)
    base = replay_program(program, bars, cost_case=BASE_COST.case)
    stress = replay_program(program, bars, cost_case=STRESS_COST.case)
    assert BASE_COST.adverse_slippage_bps == Decimal("2")
    assert STRESS_COST.adverse_slippage_bps == Decimal("5")
    assert zero.cost_case.value == "ZERO"
    assert not zero.zero_friction_can_qualify
    assert all(trade.entry.side.value == "BUY" for trade in stress.trades)
    assert all(trade.exit.side.value == "SELL" for trade in stress.trades)
    assert all(
        trade.entry.timestamp.date() == trade.exit.timestamp.date()
        for trade in stress.trades
    )
    assert stress.maximum_gross_exposure <= Decimal("1")
    assert stress == replay_program(program, bars, cost_case=STRESS_COST.case)
    assert stress.net_pnl <= base.net_pnl


def test_trial_budget_counts_invalid_duplicate_zero_trade_and_failure_trials() -> None:
    ledger = TrialLedger()
    family_programs = (
        NoiseAreaVwapMomentumProgram(),
        VwapTrendReversalProgram(),
        OpeningRangeBreakoutReversalProgram(),
    )
    dispositions = (
        TrialDisposition.INVALID,
        TrialDisposition.DUPLICATE,
        TrialDisposition.ZERO_TRADE,
        TrialDisposition.FAILED,
        TrialDisposition.ECONOMICALLY_REJECTED,
        TrialDisposition.SHORTLISTED,
    )
    for family_index, program in enumerate(family_programs):
        for ordinal in range(G1_FAMILY_TRIAL_LIMIT):
            ledger = ledger.consume(
                program,
                dispositions[(ordinal + family_index) % len(dispositions)],
                diagnostic_code="SYNTHETIC",
            )
    assert ledger.consumed_trial_count == G1_TOTAL_TRIAL_LIMIT
    assert all(
        value == G1_FAMILY_TRIAL_LIMIT for value in ledger.family_counts.values()
    )
    assert ledger.records[1].disposition is TrialDisposition.DUPLICATE
    with pytest.raises(ValueError):
        ledger.consume(family_programs[0], TrialDisposition.FAILED)


def test_selection_bias_input_retains_the_complete_consumed_ledger() -> None:
    ledger = TrialLedger().consume(
        NoiseAreaVwapMomentumProgram(), TrialDisposition.ZERO_TRADE
    )
    bias = selection_bias_input(ledger)
    assert bias.consumed_trial_count == 1
    assert bias.trial_ids == (ledger.records[0].trial_id,)
    assert bias.ledger_id == ledger.ledger_id
    assert b"arch150-selection-bias-input/v1" in bias.to_bytes()


def test_frequency_boundaries_and_later_stage_policies_are_separate() -> None:
    replay = replay_program(
        NoiseAreaVwapMomentumProgram(),
        validate_1_minute_bars(_session_bars(date(2022, 1, 3))),
        cost_case=CostCase.STRESS,
    )
    calculated = compute_frequency_diagnostics(
        replay.trades,
        validation_years=(2022,),
        regular_sessions=2,
        cost_case=CostCase.STRESS,
    )
    assert calculated.annual_completed_round_trips[0][1] == len(replay.trades)
    assert calculated.active_session_fraction == Decimal("0.5")
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
    assert passes_frequency_gate(exact, VALIDATION_FREQUENCY_POLICY)
    assert not passes_frequency_gate(
        FrequencyDiagnostics(
            exact.cost_case,
            exact.validation_years,
            exact.annual_completed_round_trips,
            exact.regular_sessions,
            exact.active_sessions,
            exact.trades_per_active_session_values,
            Decimal("99.99"),
            exact.active_session_fraction,
            exact.trades_per_active_session,
            exact.median_trades_per_active_session,
        ),
        VALIDATION_FREQUENCY_POLICY,
    )
    assert not passes_frequency_gate(
        FrequencyDiagnostics(
            CostCase.ZERO,
            exact.validation_years,
            exact.annual_completed_round_trips,
            exact.regular_sessions,
            exact.active_sessions,
            exact.trades_per_active_session_values,
            exact.average_completed_round_trips_per_validation_year,
            exact.active_session_fraction,
            exact.trades_per_active_session,
            exact.median_trades_per_active_session,
        ),
        VALIDATION_FREQUENCY_POLICY,
    )
    assert HOLDOUT_FREQUENCY_POLICY.minimum_active_session_fraction == Decimal("0.30")
    assert EXTENSION_FREQUENCY_POLICY.minimum_active_session_fraction == Decimal("0.30")


def test_effect_free_surface_and_arch149_source_remain_outside_this_module() -> None:
    assert FOUNDATION_EFFECT_COUNTERS.provider_calls == 0
    assert foundation_help().startswith("Architecture 150 foundation")
    source = ast.parse(
        Path(__file__)
        .parents[2]
        .joinpath("src/trading_bot/experiments/arch150_intraday_ai.py")
        .read_text(encoding="utf-8")
    )
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
        name.startswith(("alpaca", "robinhood", "requests", "openai"))
        for name in imports
    )
