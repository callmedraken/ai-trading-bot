from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from itertools import product
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    AbsoluteMomentumSpec,
    ConjunctiveOperation,
    ConjunctiveTrendSpec,
    DonchianBreakoutSpec,
    Generation1DiagnosticReference,
    InformationVisibility,
    MomentumGate,
    MovingAverageRule,
    MovingAverageTrendSpec,
    MultiHorizonTrendSpec,
    ProposalKind,
    ResearchProposal,
    TrendVote,
    VisibilityStage,
    VisibleEvidenceClassification,
    VisibleEvidenceReference,
    VisibleTimeframe,
    VisibleTimePartition,
)
from trading_bot.experiments.ai_strategy_discovery_generation2 import (
    CONFIRMATION_END_EXCLUSIVE,
    CONFIRMATION_START,
    ConfirmationView,
    Generation2ProgramResult,
    _combine_position_states,
    _parent_position_states,
    _validate_g2_proposal,
    evaluate_generation2_program,
)
from trading_bot.experiments.filtered_trend_campaign import CellEvidence
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

_PARENT_SPECS = {
    "6ff56e8f-ab41-50f3-aa3b-2474bfb37537": MovingAverageTrendSpec(
        35, 50, MovingAverageRule.MA_PERCENT_BAND_010
    ),
    "926f7b9f-d40f-5c4b-8e56-de498786e440": AbsoluteMomentumSpec(63, MomentumGate.NONE),
    "f6739ed9-f812-5f62-938c-6b0ea7407825": AbsoluteMomentumSpec(
        252, MomentumGate.ABOVE_SMA200
    ),
    "369a6806-1609-53b4-8972-b4d248505e2d": MultiHorizonTrendSpec(
        (63, 126, 252), TrendVote.THREE_OF_THREE
    ),
    "c5d6574d-a9dc-5b4f-8a68-b95b1cdd3e59": MovingAverageTrendSpec(
        35, 50, MovingAverageRule.BASE_MA
    ),
    "b4c598f0-688d-5c81-b924-219fabd90e2a": DonchianBreakoutSpec(35, 50, 20),
}
_ALLOWED_PAIRS = (
    ("6ff56e8f-ab41-50f3-aa3b-2474bfb37537", "926f7b9f-d40f-5c4b-8e56-de498786e440"),
    ("6ff56e8f-ab41-50f3-aa3b-2474bfb37537", "f6739ed9-f812-5f62-938c-6b0ea7407825"),
    ("6ff56e8f-ab41-50f3-aa3b-2474bfb37537", "369a6806-1609-53b4-8972-b4d248505e2d"),
    ("c5d6574d-a9dc-5b4f-8a68-b95b1cdd3e59", "926f7b9f-d40f-5c4b-8e56-de498786e440"),
    ("b4c598f0-688d-5c81-b924-219fabd90e2a", "926f7b9f-d40f-5c4b-8e56-de498786e440"),
    ("b4c598f0-688d-5c81-b924-219fabd90e2a", "369a6806-1609-53b4-8972-b4d248505e2d"),
)


def _g2_proposal(parent_ids: tuple[str, str]) -> ResearchProposal:
    parents = tuple(sorted(parent_ids))
    components = tuple(_PARENT_SPECS[parent_id] for parent_id in parents)
    visible = VisibleEvidenceReference(
        reference_label="G1_DISCOVERY_FIXTURE",
        dataset_label="A147_SYNTHETIC_DAILY",
        timeframe=VisibleTimeframe.DAILY,
        time_partition=VisibleTimePartition.DISCOVERY_2019_2021,
        classification=VisibleEvidenceClassification.GENERATION_1_DISCOVERY_RESULT,
    )
    diagnostics = tuple(
        Generation1DiagnosticReference(
            parent_proposal_id=parent_id,
            parent_trial_ordinal=index + 1,
            diagnostic_id=str(
                uuid5(NAMESPACE_URL, f"synthetic-g1-diagnostic:{parent_id}")
            ),
        )
        for index, parent_id in enumerate(parents)
    )
    return ResearchProposal(
        campaign_version=CAMPAIGN_VERSION,
        generation=2,
        proposal_kind=ProposalKind.RECOMBINATION,
        parent_proposal_ids=parents,
        strategy_spec=ConjunctiveTrendSpec(components),
        hypothesis="A second G1 state may gate noisy trend exposure.",
        expected_mechanism="Both long-only parents must agree before exposure.",
        falsification_condition="Confirmation robustness gates fail.",
        source_reference_labels=("G1_DISCOVERY_FIXTURE",),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
            visible_evidence=(visible,),
            visible_generation1_diagnostics=diagnostics,
        ),
        producer_label="synthetic-test-fixture",
    )


def _synthetic_dataset(*, post_2022_delta: Decimal = Decimal(0)) -> MultiAssetDataset:
    """Build only deterministic synthetic prices over the published session calendar."""
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
            close = Decimal(100 + symbol_index) + Decimal(trend)
            if session >= date(2023, 1, 1):
                close += post_2022_delta
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


def _short_bars(count: int) -> tuple[Bar, ...]:
    return tuple(
        Bar(
            Symbol("SPY"),
            (datetime(2020, 1, 1, tzinfo=NY) + timedelta(days=index)).astimezone(UTC),
            Decimal(100),
            Decimal(101),
            Decimal(99),
            Decimal(100),
            1000,
        )
        for index in range(count)
    )


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    (
        (left, right, "BUY" if left == right == "BUY" else "SELL")
        for left, right in product(("SELL", "BUY"), repeat=2)
    ),
)
def test_all_of_truth_table_requires_two_long_parent_states(
    first, second, expected
) -> None:
    assert _combine_position_states((first,), (second,)) == (expected,)


def test_hysteretic_parent_hold_carries_its_position_state(monkeypatch) -> None:
    signals = ("BUY", "HOLD", "HOLD", "SELL", "HOLD")
    monkeypatch.setattr(
        "trading_bot.experiments.ai_strategy_discovery_generation2.generation1_signal_series",
        lambda _spec, _bars: signals,
    )

    states = _parent_position_states(
        StrategyConfig("BASE_MA", 35, 50, "none"), _short_bars(len(signals))
    )

    assert states == ("BUY", "BUY", "BUY", "SELL", "SELL")


def test_only_the_six_frozen_component_pairs_are_representable() -> None:
    represented = tuple(
        _g2_proposal(pair).strategy_spec.components for pair in _ALLOWED_PAIRS
    )

    assert len(represented) == 6
    assert len(set(represented)) == 6
    assert all(
        components == ConjunctiveTrendSpec(components).components
        for components in represented
    )
    with pytest.raises(ValueError, match="outside the six frozen"):
        ConjunctiveTrendSpec(
            (
                MovingAverageTrendSpec(55, 100, MovingAverageRule.BASE_MA),
                AbsoluteMomentumSpec(63, MomentumGate.NONE),
            )
        )
    with pytest.raises(ValueError):
        ConjunctiveTrendSpec(
            (
                _PARENT_SPECS[_ALLOWED_PAIRS[0][0]],
                _PARENT_SPECS[_ALLOWED_PAIRS[0][1]],
            ),
            operation="OR",
        )
    assert ConjunctiveOperation.ALL_OF.value == "ALL_OF"


def test_parent_diagnostics_and_component_semantics_must_match() -> None:
    proposal = _g2_proposal(_ALLOWED_PAIRS[0])
    assert (
        tuple(
            item.parent_proposal_id
            for item in proposal.information_visibility.visible_generation1_diagnostics
        )
        == proposal.parent_proposal_ids
    )

    wrong_parent_ids = (
        "c5d6574d-a9dc-5b4f-8a68-b95b1cdd3e59",
        "f6739ed9-f812-5f62-938c-6b0ea7407825",
    )
    wrong = _g2_proposal(_ALLOWED_PAIRS[0])
    with pytest.raises(ValueError, match="do not match"):
        altered = ResearchProposal(
            campaign_version=wrong.campaign_version,
            generation=wrong.generation,
            proposal_kind=wrong.proposal_kind,
            parent_proposal_ids=tuple(sorted(wrong_parent_ids)),
            strategy_spec=wrong.strategy_spec,
            hypothesis=wrong.hypothesis,
            expected_mechanism=wrong.expected_mechanism,
            falsification_condition=wrong.falsification_condition,
            source_reference_labels=wrong.source_reference_labels,
            information_visibility=InformationVisibility(
                VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
                visible_evidence=wrong.information_visibility.visible_evidence,
                visible_generation1_diagnostics=tuple(
                    Generation1DiagnosticReference(
                        parent_id,
                        index + 1,
                        str(uuid5(NAMESPACE_URL, f"mismatched:{parent_id}")),
                    )
                    for index, parent_id in enumerate(sorted(wrong_parent_ids))
                ),
            ),
            producer_label=wrong.producer_label,
        )
        _validate_g2_proposal(altered)


def test_confirmation_view_exposes_only_2022_2023_report_slices() -> None:
    view = ConfirmationView.from_dataset(_synthetic_dataset())

    assert view.report_window == (date(2022, 1, 1), date(2024, 1, 1))
    assert tuple(regime.label for regime in view.regimes) == (
        "2022",
        "2023",
        "continuous",
    )
    for symbol in UNIVERSE:
        bars = view.bars_for(symbol)
        dates = tuple(bar.timestamp.astimezone(NY).date() for bar in bars)
        assert dates[0] < CONFIRMATION_START
        assert dates[-1] < CONFIRMATION_END_EXCLUSIVE
        assert any(session < CONFIRMATION_START for session in dates)
        assert any(
            CONFIRMATION_START <= session < date(2023, 1, 1) for session in dates
        )
        assert any(
            date(2023, 1, 1) <= session < CONFIRMATION_END_EXCLUSIVE
            for session in dates
        )


def test_view_rejects_any_2024_or_later_bar() -> None:
    dataset = _synthetic_dataset()
    source = dataset.datasets[0]
    future_bar = Bar(
        Symbol(source.symbol),
        datetime(2024, 1, 2, tzinfo=NY).astimezone(UTC),
        Decimal(100),
        Decimal(101),
        Decimal(99),
        Decimal(100),
        1000,
    )
    object.__setattr__(source, "bars", (*source.bars, future_bar))

    with pytest.raises(ValueError, match="2024 and later"):
        ConfirmationView.from_dataset(dataset)


def test_generation2_result_preserves_prefix_next_open_bounds_and_economics() -> None:
    proposal = _g2_proposal(_ALLOWED_PAIRS[0])
    view = ConfirmationView.from_dataset(_synthetic_dataset())
    changed_future_view = ConfirmationView.from_dataset(
        _synthetic_dataset(post_2022_delta=Decimal(500))
    )

    result = evaluate_generation2_program(proposal, view)
    changed_future_result = evaluate_generation2_program(proposal, changed_future_view)

    assert isinstance(result, Generation2ProgramResult)
    assert len(result.cells) == 24
    assert tuple(cell for cell in result.cells if cell.regime == "2022") == tuple(
        cell for cell in changed_future_result.cells if cell.regime == "2022"
    )
    assert result.dataset_identity == view.dataset_identity
    assert result.confirmation_view_identity == view.identity
    assert result.identity != changed_future_result.identity
    assert tuple((cell.symbol, cell.regime) for cell in result.cells) == tuple(
        (symbol, label)
        for symbol in UNIVERSE
        for label in ("2022", "2023", "continuous")
    )

    cells_with_fills = 0
    for cell in result.cells:
        bars = view.bars_for(cell.symbol)
        bar_index_by_timestamp = {
            bar.timestamp: index for index, bar in enumerate(bars)
        }
        regime_start, regime_end = {
            "2022": (date(2022, 1, 1), date(2023, 1, 1)),
            "2023": (date(2023, 1, 1), date(2024, 1, 1)),
            "continuous": (date(2022, 1, 1), date(2024, 1, 1)),
        }[cell.regime]
        assert date.fromisoformat(cell.first_session[:10]) >= regime_start
        assert date.fromisoformat(cell.last_session[:10]) < regime_end
        assert cell.candidate_id == proposal.proposal_id
        for metrics, commission, bps in (
            (cell.base, Decimal(1), Decimal(5)),
            (cell.stress, Decimal(2), Decimal(10)),
        ):
            cells_with_fills += bool(metrics.fills)
            assert metrics.fill_count == len(metrics.fills)
            for fill in metrics.fills:
                execution = datetime.fromisoformat(fill.session)
                assert fill.information_through is not None
                information = datetime.fromisoformat(fill.information_through)
                assert information < execution
                assert (
                    bar_index_by_timestamp[information] + 1
                    == bar_index_by_timestamp[execution]
                )
                assert (
                    bars[bar_index_by_timestamp[execution]].open == fill.execution_open
                )
                assert date.fromisoformat(fill.session[:10]) >= regime_start
                assert date.fromisoformat(fill.session[:10]) < regime_end
                assert fill.price == fill.execution_open * (
                    Decimal(1) + bps / Decimal(10000)
                    if fill.side == "BUY"
                    else Decimal(1) - bps / Decimal(10000)
                )
                assert fill.commission == commission
                assert fill.quantity == fill.quantity.to_integral_value()
    assert cells_with_fills > 0
    assert all(type(cell) is CellEvidence for cell in result.cells)
