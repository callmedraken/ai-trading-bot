from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Context, Decimal, localcontext
from functools import cache
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    AbsoluteMomentumSpec,
    DonchianBreakoutSpec,
    Generation1DiagnosticReference,
    InformationVisibility,
    MomentumGate,
    MovingAverageRule,
    MovingAverageTrendSpec,
    MultiHorizonTrendSpec,
    ProposalKind,
    ResearchProposal,
    StrategyFamily,
    TrendVote,
    VisibilityStage,
    VisibleEvidenceClassification,
    VisibleEvidenceReference,
    VisibleTimeframe,
    VisibleTimePartition,
    compile_generation1_program,
)
from trading_bot.experiments.ai_strategy_discovery_generation1 import (
    DISCOVERY_END_EXCLUSIVE,
    DiscoveryView,
    Generation1ProgramResult,
    _new_program_states,
    evaluate_generation1_program,
)
from trading_bot.experiments.filtered_trend_campaign import (
    evaluate_cell,
    regime_plan,
)
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    ProviderProvenance,
    SymbolDataset,
)
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

NY = ZoneInfo("America/New_York")


def _proposal(spec) -> ResearchProposal:
    retained = spec.family in (
        StrategyFamily.MOVING_AVERAGE_TREND,
        StrategyFamily.DONCHIAN_BREAKOUT,
    )
    evidence = VisibleEvidenceReference(
        reference_label="PRIOR_A147",
        dataset_label="A147_DAILY",
        timeframe=VisibleTimeframe.DAILY,
        time_partition=VisibleTimePartition.PRIOR_RESEARCH_2022_2023,
        classification=VisibleEvidenceClassification.PRIOR_CANONICAL,
    )
    return ResearchProposal(
        campaign_version=CAMPAIGN_VERSION,
        generation=1,
        proposal_kind=(
            ProposalKind.RETAINED_BASELINE if retained else ProposalKind.ORIGINAL
        ),
        parent_proposal_ids=(),
        strategy_spec=spec,
        hypothesis="A closed daily rule may persist across symbols.",
        expected_mechanism="The frozen signal may capture persistent trends.",
        falsification_condition="Stress breadth gates fail.",
        source_reference_labels=("PRIOR_A147",),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_1_PRE_RESULTS,
            visible_evidence=(evidence,),
        ),
        producer_label="offline-fixture",
    )


def _daily_bars(symbol: str, closes: tuple[Decimal, ...]) -> tuple[Bar, ...]:
    values = []
    for index, close in enumerate(closes):
        # Synthetic signal fixtures use consecutive aware timestamps; they do not
        # stand in for accepted market sessions or enter the dataset evaluator.
        timestamp = datetime(2016, 1, 1, tzinfo=NY) + timedelta(days=index)
        values.append(
            Bar(
                Symbol(symbol),
                timestamp.astimezone(UTC),
                close,
                close + 1,
                close - 1,
                close,
                1000,
            )
        )
    return tuple(values)


@cache
def _accepted_synthetic_dataset(
    *, future_delta: Decimal = Decimal(0)
) -> MultiAssetDataset:
    sessions = tuple(
        session
        for session in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= session < date(2024, 1, 1)
    )
    provenance = ProviderProvenance()
    datasets = []
    for symbol_index, symbol in enumerate(UNIVERSE):
        bars = []
        for index, session in enumerate(sessions):
            cycle = index % 400
            trend = cycle if cycle < 200 else 400 - cycle
            close = Decimal(100 + symbol_index) + Decimal(trend) / Decimal(10)
            if session >= date(2022, 1, 1):
                close += future_delta
            stamp = datetime.combine(session, time.min, NY).astimezone(UTC)
            bars.append(
                Bar(
                    Symbol(symbol),
                    stamp,
                    close,
                    close + 1,
                    close - 1,
                    close,
                    1000,
                )
            )
        datasets.append(SymbolDataset(symbol, tuple(bars), provenance))
    return MultiAssetDataset(tuple(datasets))


def test_view_clips_at_new_york_2022_cutoff_and_cannot_store_later_bars() -> None:
    original = DiscoveryView.from_dataset(_accepted_synthetic_dataset())
    changed_confirmation = DiscoveryView.from_dataset(
        _accepted_synthetic_dataset(future_delta=Decimal(500))
    )

    assert tuple(item.symbol for item in original.symbol_bars) == UNIVERSE
    assert original.price_basis == "ALPACA_ALL_ADJUSTED_PRICE_V1"
    assert original.provider_provenance == ProviderProvenance()
    assert original.symbol_bars == changed_confirmation.symbol_bars
    for item in original.symbol_bars:
        assert all(
            bar.timestamp.astimezone(NY).date() < DISCOVERY_END_EXCLUSIVE
            for bar in item.bars
        )
        assert item.bars[0].timestamp.astimezone(NY).date() == date(2016, 1, 4)
        assert item.bars[-1].timestamp.astimezone(NY).date() < date(2022, 1, 1)
    with pytest.raises((AttributeError, TypeError)):
        original.symbol_bars = ()


def test_absolute_momentum_uses_strict_lookback_and_sma200_equality() -> None:
    flat = _daily_bars("SPY", (Decimal(100),) * 64)
    ungated = _new_program_states(AbsoluteMomentumSpec(63, MomentumGate.NONE), flat)
    assert ungated[62] == "SELL"
    assert ungated[63] == "SELL"  # equality to close[t-63] is non-positive

    rising = _daily_bars("SPY", (Decimal(100),) * 63 + (Decimal(101),))
    gated_before_sma_warmup = _new_program_states(
        AbsoluteMomentumSpec(63, MomentumGate.ABOVE_SMA200), rising
    )
    assert gated_before_sma_warmup[-1] == "SELL"

    closes = [Decimal(100)] * 200
    closes[136] = Decimal(99)
    closes[137] = Decimal(101)
    sma_equality_bars = _daily_bars("SPY", tuple(closes))
    ungated = _new_program_states(
        AbsoluteMomentumSpec(63, MomentumGate.NONE), sma_equality_bars
    )
    gated = _new_program_states(
        AbsoluteMomentumSpec(63, MomentumGate.ABOVE_SMA200), sma_equality_bars
    )
    assert ungated[199] == "BUY"
    assert gated[199] == "SELL"  # close equals inclusive SMA200

    near_equal_closes = [Decimal(100)] * 200
    near_equal_closes[136] = Decimal(99)
    near_equal_closes[137] = Decimal("100." + "9" * 80)
    near_equal_bars = _daily_bars("SPY", tuple(near_equal_closes))
    with localcontext(Context(prec=2)):
        exact_gate = _new_program_states(
            AbsoluteMomentumSpec(63, MomentumGate.ABOVE_SMA200), near_equal_bars
        )
    assert exact_gate[199] == "BUY"


@pytest.mark.parametrize(
    ("horizons", "vote", "expected"),
    [
        ((21, 63, 126), TrendVote.TWO_OF_THREE, "BUY"),
        ((21, 63, 126), TrendVote.THREE_OF_THREE, "SELL"),
        ((63, 126, 252), TrendVote.TWO_OF_THREE, "BUY"),
        ((63, 126, 252), TrendVote.THREE_OF_THREE, "SELL"),
    ],
)
def test_multi_horizon_voting_is_strict_and_closed(horizons, vote, expected) -> None:
    closes = [Decimal(100)] * (max(horizons) + 1)
    closes[-1 - horizons[1]] = Decimal(99)
    closes[-1 - horizons[2]] = Decimal(99)
    bars = _daily_bars("SPY", tuple(closes))
    states = _new_program_states(MultiHorizonTrendSpec(horizons, vote), bars)
    assert states[-1] == expected


def test_g1_result_is_bounded_deterministic_next_open_and_uses_a147_costs() -> None:
    proposal = _proposal(AbsoluteMomentumSpec(63, MomentumGate.NONE))
    first_view = DiscoveryView.from_dataset(_accepted_synthetic_dataset())
    second_view = DiscoveryView.from_dataset(
        _accepted_synthetic_dataset(future_delta=Decimal(500))
    )

    first = evaluate_generation1_program(proposal, first_view)
    repeated = evaluate_generation1_program(proposal, first_view)
    confirmation_changed = evaluate_generation1_program(proposal, second_view)

    assert first == repeated
    assert first.cells == confirmation_changed.cells
    assert first.identity == repeated.identity
    assert first.identity != confirmation_changed.identity
    assert isinstance(first, Generation1ProgramResult)
    assert len(first.cells) == 32
    assert tuple((cell.symbol, cell.regime) for cell in first.cells) == tuple(
        (symbol, label)
        for symbol in UNIVERSE
        for label in ("2019", "2020", "2021", "continuous")
    )
    for cell in first.cells:
        assert datetime.fromisoformat(cell.first_session).astimezone(NY).date() >= date(
            2019, 1, 1
        )
        assert datetime.fromisoformat(cell.last_session).astimezone(NY).date() < date(
            2022, 1, 1
        )
        assert cell.base.fill_count == len(cell.base.fills)
        assert cell.stress.fill_count == len(cell.stress.fills)
        assert cell.buy_and_hold.fill_count <= 1
        assert cell.buy_and_hold_stress.fill_count <= 1
        assert cell.base.time_invested >= 0
        assert cell.stress.time_invested >= 0
        for metrics, commission, bps in (
            (cell.base, Decimal(1), Decimal(5)),
            (cell.stress, Decimal(2), Decimal(10)),
        ):
            for fill in metrics.fills:
                assert fill.commission == commission
                assert fill.price == fill.execution_open * (
                    Decimal(1) + bps / Decimal(10000)
                    if fill.side == "BUY"
                    else Decimal(1) - bps / Decimal(10000)
                )
                assert fill.information_through is not None
                assert fill.information_through < fill.session
        assert cell.base.equity_trace_identity
        assert cell.stress.equity_trace_identity
        assert cell.result_id

    changed_metrics = replace(
        first.cells[0].base,
        total_return=first.cells[0].base.total_return + Decimal("0.0001"),
    )
    changed_cell = replace(first.cells[0], base=changed_metrics)
    altered = replace(first, cells=(changed_cell, *first.cells[1:]))
    assert altered.identity != first.identity


@pytest.mark.parametrize(
    "spec",
    (
        MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA),
        MovingAverageTrendSpec(55, 100, MovingAverageRule.MA_PERCENT_BAND_010),
        DonchianBreakoutSpec(50, 200, 55),
    ),
)
def test_retained_baselines_match_existing_a147_cells_exactly(spec) -> None:
    proposal = _proposal(spec)
    view = DiscoveryView.from_dataset(_accepted_synthetic_dataset())
    program = compile_generation1_program(spec)
    assert isinstance(program, StrategyConfig)
    result = evaluate_generation1_program(proposal, view)

    expected = tuple(
        evaluate_cell(
            view.bars_for(symbol),
            program,
            next(item for item in regime_plan() if item.label == label),
            proposal.proposal_id,
        )
        for symbol in UNIVERSE
        for label in ("2019", "2020", "2021", "continuous")
    )
    assert result.cells == expected


def test_multi_horizon_program_evaluates_a_complete_synthetic_g1_panel() -> None:
    proposal = _proposal(MultiHorizonTrendSpec((63, 126, 252), TrendVote.TWO_OF_THREE))
    view = DiscoveryView.from_dataset(_accepted_synthetic_dataset())
    result = evaluate_generation1_program(proposal, view)

    assert len(result.cells) == 32
    assert {cell.candidate_id for cell in result.cells} == {proposal.proposal_id}
    assert {cell.regime for cell in result.cells} == {
        "2019",
        "2020",
        "2021",
        "continuous",
    }
    assert all(
        fill.information_through is not None and fill.information_through < fill.session
        for cell in result.cells
        for fill in cell.base.fills + cell.stress.fills
    )


def test_evaluator_rejects_non_g1_or_untyped_inputs_before_replay() -> None:
    proposal = _proposal(MultiHorizonTrendSpec((21, 63, 126), TrendVote.TWO_OF_THREE))
    view = DiscoveryView.from_dataset(_accepted_synthetic_dataset())
    with pytest.raises(ValueError, match="ResearchProposal"):
        evaluate_generation1_program(object(), view)
    with pytest.raises(ValueError, match="DiscoveryView"):
        evaluate_generation1_program(proposal, object())
    with pytest.raises(ValueError, match="complete and canonically ordered"):
        Generation1ProgramResult(
            proposal.proposal_id,
            proposal.semantic_program_id,
            view.dataset_identity,
            (object(),),
        )
    evidence = proposal.information_visibility.visible_evidence
    parent = str(uuid5(NAMESPACE_URL, "g1-parent"))
    diagnostic = Generation1DiagnosticReference(
        parent, 1, str(uuid5(NAMESPACE_URL, "g1-diagnostic"))
    )
    generation_two = ResearchProposal(
        campaign_version=CAMPAIGN_VERSION,
        generation=2,
        proposal_kind=ProposalKind.MUTATION,
        parent_proposal_ids=(parent,),
        strategy_spec=proposal.strategy_spec,
        hypothesis="A bounded diagnostic mutation.",
        expected_mechanism="A parent diagnostic motivates the variant.",
        falsification_condition="Breadth gates fail.",
        source_reference_labels=("PRIOR_A147",),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
            visible_evidence=evidence,
            visible_generation1_diagnostics=(diagnostic,),
        ),
        producer_label="offline-fixture",
    )
    with pytest.raises(ValueError, match="supported Generation-1"):
        evaluate_generation1_program(generation_two, view)
