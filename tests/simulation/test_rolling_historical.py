from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.execution import OrderEngine, PaperFillPolicy
from trading_bot.execution.state_fingerprints import ledger_snapshot, ledger_state_id
from trading_bot.ledger import PaperLedger
from trading_bot.market_data import (
    AlignedMarketFrame,
    MissingBarPolicy,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
)
from trading_bot.portfolio import (
    HistoricalScenarioGenerationPolicy,
    MeanCvarOptimizationParameters,
    MetadataEntry,
    PortfolioConstraints,
)
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime import PaperPortfolioRuntime
from trading_bot.simulation import (
    InvalidRollingHistoricalSimulationRequestError,
    OptimizedPaperPortfolioSimulator,
    RollingHistoricalCycleTimingPolicy,
    RollingHistoricalExecutionPricePolicy,
    RollingHistoricalOptimizedSimulationRunner,
    RollingHistoricalScheduleError,
    RollingHistoricalSimulationReconciliationError,
    RollingHistoricalSimulationRequest,
    RollingHistoricalWindowError,
    RollingHistoricalWindowPolicy,
)

SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
SYMBOLS = (SPY, QQQ)
START = datetime(2026, 1, 5, 20, tzinfo=UTC)


def _historical(
    rows: tuple[tuple[str, str], ...] = (
        ("100", "100"),
        ("102", "99"),
        ("104", "98"),
        ("106", "97"),
        ("108", "96"),
    ),
    *,
    policy: MissingBarPolicy = MissingBarPolicy.INTERSECTION,
) -> MultiSymbolHistoricalDataResult:
    timestamps = tuple(START + timedelta(days=index) for index in range(len(rows)))
    request = MultiSymbolHistoricalDataRequest(
        SYMBOLS,
        timestamps[0] - timedelta(days=1),
        timestamps[-1] + timedelta(days=1),
        missing_bar_policy=policy,
    )
    frames = tuple(
        AlignedMarketFrame(
            timestamp,
            SYMBOLS,
            {
                symbol: Bar(
                    symbol,
                    timestamp,
                    Decimal(close),
                    Decimal(close),
                    Decimal(close),
                    Decimal(close),
                    100,
                )
                for symbol, close in zip(SYMBOLS, values, strict=True)
            },
        )
        for timestamp, values in zip(timestamps, rows, strict=True)
    )
    return MultiSymbolHistoricalDataResult(request, frames, "fixture")


def _request(
    *,
    data: MultiSymbolHistoricalDataResult | None = None,
    schedule: tuple[datetime, ...] | None = None,
    count: int = 3,
    timing: RollingHistoricalCycleTimingPolicy | None = None,
    metadata: tuple[MetadataEntry, ...] = (),
    trading_enabled: bool = True,
) -> RollingHistoricalSimulationRequest:
    history = data or _historical()
    fee = Decimal("0")
    return RollingHistoricalSimulationRequest(
        UUID(int=100),
        history,
        schedule if schedule is not None else (history.frames[2].timestamp,),
        RollingHistoricalWindowPolicy(count),
        HistoricalScenarioGenerationPolicy(),
        RollingHistoricalExecutionPricePolicy(),
        timing or RollingHistoricalCycleTimingPolicy(),
        Decimal("0"),
        "fixture",
        MeanCvarOptimizationParameters(Decimal("0.75")),
        Decimal("1"),
        PortfolioConstraints(maximum_position_weight=Decimal("1")),
        RebalanceAssumptions(fixed_commission=fee),
        RebalanceProposalPolicy(allow_partial_plans=True),
        None,
        RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            estimated_commission=fee,
        ),
        PortfolioRiskPolicy(),
        PaperFillPolicy(Decimal("0"), fee),
        trading_enabled,
        metadata,
    )


def _runner() -> RollingHistoricalOptimizedSimulationRunner:
    simulator = OptimizedPaperPortfolioSimulator(
        PaperPortfolioRuntime(OrderEngine(), PaperLedger(Decimal("1000")))
    )
    return RollingHistoricalOptimizedSimulationRunner(simulator)


def test_request_copies_and_normalizes_schedule_and_metadata() -> None:
    local = timezone(timedelta(hours=-5))
    schedule = [START.astimezone(local) + timedelta(days=2)]
    metadata = [MetadataEntry("caller", "test")]
    request = _request(schedule=schedule, metadata=metadata)
    schedule.clear()
    metadata.clear()
    assert request.rebalance_timestamps == (START + timedelta(days=2),)
    assert request.metadata == (MetadataEntry("caller", "test"),)


@pytest.mark.parametrize(
    "changes",
    (
        {"request_id": "bad"},
        {"trading_enabled": 1},
        {"metadata": (MetadataEntry("rolling_historical_simulation_forbidden", "x"),)},
    ),
)
def test_request_rejects_invalid_public_values(changes: dict) -> None:
    request = _request()
    with pytest.raises(InvalidRollingHistoricalSimulationRequestError):
        replace(request, **changes)


@pytest.mark.parametrize("count", (True, 1, 2.0))
def test_window_policy_requires_exact_integer_at_least_two(count: object) -> None:
    with pytest.raises(InvalidRollingHistoricalSimulationRequestError):
        RollingHistoricalWindowPolicy(count)  # type: ignore[arg-type]


def test_timing_policy_validates_offsets() -> None:
    with pytest.raises(InvalidRollingHistoricalSimulationRequestError):
        RollingHistoricalCycleTimingPolicy(timedelta(seconds=2), timedelta(seconds=1))
    with pytest.raises(InvalidRollingHistoricalSimulationRequestError):
        RollingHistoricalCycleTimingPolicy(timedelta(seconds=-1), timedelta(0))


@pytest.mark.parametrize(
    "schedule",
    (
        (),
        (START + timedelta(days=2), START + timedelta(days=2)),
        (START + timedelta(days=3), START + timedelta(days=2)),
        (START + timedelta(days=20),),
    ),
)
def test_schedule_rejects_empty_duplicate_decreasing_or_absent(
    schedule: tuple[datetime, ...],
) -> None:
    with pytest.raises(RollingHistoricalScheduleError):
        _runner().run(_request(schedule=schedule))


def test_normalized_duplicate_schedule_is_rejected() -> None:
    local = timezone(timedelta(hours=-5))
    timestamp = START + timedelta(days=2)
    with pytest.raises(RollingHistoricalScheduleError):
        _runner().run(_request(schedule=(timestamp, timestamp.astimezone(local))))


def test_insufficient_history_and_fill_conflict_are_rejected() -> None:
    with pytest.raises(RollingHistoricalWindowError):
        _runner().run(_request(schedule=(START + timedelta(days=1),), count=3))
    timing = RollingHistoricalCycleTimingPolicy(fill_offset=timedelta(days=2))
    with pytest.raises(RollingHistoricalScheduleError):
        _runner().run(
            _request(
                schedule=(
                    START + timedelta(days=2),
                    START + timedelta(days=3),
                ),
                timing=timing,
            )
        )


def test_one_frame_run_preserves_exact_window_objects_and_handoffs() -> None:
    history = _historical()
    result = _runner().run(_request(data=history))
    generation = result.frame_generations[0]
    child = generation.scenario_result.request.historical_data
    assert child.frames == history.frames[:3]
    assert all(
        actual is expected
        for actual, expected in zip(child.frames, history.frames[:3], strict=True)
    )
    assert child.request.start == history.frames[0].timestamp
    assert child.request.end == history.frames[3].timestamp
    assert generation.window_end_index_inclusive == 2
    assert (
        generation.optimized_frame.scenarios is generation.scenario_result.scenario_set
    )
    assert (
        generation.optimized_frame.expected_returns
        is generation.scenario_result.expected_returns
    )
    assert result.optimized_result.request is result.optimized_request
    assert result.performance_request.simulation_result is result.optimized_result
    assert result.performance_result.request is result.performance_request


def test_overlapping_and_final_windows_use_contractual_bounds() -> None:
    history = _historical((("100", "100"),) * 5)
    result = _runner().run(
        _request(
            data=history,
            schedule=(history.frames[2].timestamp, history.frames[4].timestamp),
        )
    )
    first, final = (
        item.scenario_result.request.historical_data
        for item in result.frame_generations
    )
    assert first.frames == history.frames[0:3]
    assert first.request.end == history.frames[3].timestamp
    assert final.frames == history.frames[2:5]
    assert final.request.end == history.request.end


def test_frames_use_ordered_close_prices_offsets_and_separate_metadata() -> None:
    history = _historical()
    timing = RollingHistoricalCycleTimingPolicy(
        timedelta(minutes=1), timedelta(minutes=2)
    )
    result = _runner().run(_request(data=history, timing=timing))
    generation = result.frame_generations[0]
    frame = generation.optimized_frame
    source = history.frames[2]
    assert tuple(item.symbol for item in frame.prices) == SYMBOLS
    assert tuple(item.risk_price for item in frame.prices) == (
        source.bars_by_symbol[SPY].close,
        source.bars_by_symbol[QQQ].close,
    )
    assert frame.submitted_at == frame.as_of + timedelta(minutes=1)
    assert frame.filled_at == frame.as_of + timedelta(minutes=2)
    assert not (
        {item.key for item in result.optimized_request.metadata}
        & {item.key for item in frame.metadata}
    )


def test_multi_frame_run_carries_state_and_is_deterministic() -> None:
    history = _historical((("100", "100"),) * 5)
    request = _request(
        data=history,
        schedule=(history.frames[2].timestamp, history.frames[4].timestamp),
    )
    first = _runner().run(request)
    second = _runner().run(request)
    assert first.result_id == second.result_id
    assert first.optimized_request.request_id == second.optimized_request.request_id
    assert tuple(
        item.optimized_frame_fingerprint for item in first.frame_generations
    ) == tuple(item.optimized_frame_fingerprint for item in second.frame_generations)
    assert len(first.optimized_result.evaluations) == 2
    assert first.final_engine_state_id == first.optimized_result.final_engine_state_id
    assert first.final_ledger_state_id == first.optimized_result.final_ledger_state_id


def test_history_change_changes_deterministic_identities() -> None:
    first = _runner().run(_request())
    changed = _historical(
        (
            ("100", "100"),
            ("102", "99"),
            ("105", "98"),
            ("106", "97"),
            ("108", "96"),
        )
    )
    second = _runner().run(_request(data=changed))
    assert first.frame_generations[0].scenario_request_id != (
        second.frame_generations[0].scenario_request_id
    )
    assert first.result_id != second.result_id


def test_complete_union_history_is_accepted() -> None:
    result = _runner().run(_request(data=_historical(policy=MissingBarPolicy.UNION)))
    assert len(result.frame_generations) == 1


def test_corrupted_history_fails_before_simulation() -> None:
    history = _historical()
    object.__setattr__(history, "frames", tuple(reversed(history.frames)))
    runner = _runner()
    before = ledger_state_id(ledger_snapshot(runner.simulator.ledger))
    with pytest.raises(RollingHistoricalSimulationReconciliationError):
        runner.run(_request(data=history))
    assert ledger_state_id(ledger_snapshot(runner.simulator.ledger)) == before


def test_runner_exposes_only_supplied_simulator_as_read_only_property() -> None:
    runner = _runner()
    assert runner.simulator is runner._simulator
    with pytest.raises(AttributeError):
        runner.simulator = _runner().simulator  # type: ignore[misc]
