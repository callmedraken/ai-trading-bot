from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from decimal import ROUND_FLOOR, Decimal, localcontext
from types import SimpleNamespace
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Bar, OrderFill, OrderSide, Symbol
from trading_bot.experiments import ai_strategy_discovery_generation1 as generation1
from trading_bot.experiments import (
    ai_strategy_discovery_selection_bias as selection_bias,
)
from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    InformationVisibility,
    ProposalKind,
    ResearchProposal,
    StrategyFamily,
    TrialDisposition,
    TrialLedger,
    TrialLedgerRecord,
    VisibilityStage,
    VisibleEvidenceClassification,
    VisibleEvidenceReference,
    VisibleTimeframe,
    VisibleTimePartition,
)
from trading_bot.experiments.ai_strategy_discovery_generation1 import (
    DiscoveryView,
    Generation1ProgramResult,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_analysis import (
    EconomicSummary,
    Generation1BatchAnalysis,
    ProgramAnalysis,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_plan import (
    Generation1ProposalSet,
    frozen_generation1_specs,
)
from trading_bot.experiments.ai_strategy_discovery_generation2 import (
    Generation2ProgramResult,
)
from trading_bot.experiments.ai_strategy_discovery_selection_equity import (
    STARTING_CASH,
    STRESS_COSTS,
)
from trading_bot.experiments.ai_strategy_discovery_selection_statistics import (
    CAMPAIGN_FAMILYWISE_ALPHA,
)
from trading_bot.experiments.filtered_trend_campaign import (
    ALLOCATION,
    CONTEXT,
    AtrDescription,
    CellEvidence,
    FillEvidence,
    Metrics,
    decimal_text,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    ProviderProvenance,
    SymbolDataset,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)
from trading_bot.ledger import PaperLedger

_NY = ZoneInfo("America/New_York")
_G0_ID = "08395fd5-43a4-5a81-9992-877560757a9f"
_FOUNDATION_ID = "00a845be-228a-56c6-9fd1-9b76c2176cf8"
_G1_HEAD = "a" * 40
_G1_TREE = "b" * 40
_SELECTION_HEAD = "c" * 40
_SELECTION_TREE = "d" * 40


@dataclass(frozen=True, slots=True)
class _SyntheticEvidence:
    proposal_set: Generation1ProposalSet
    terminal_ledger: TrialLedger
    analysis: Generation1BatchAnalysis
    results: tuple[Generation1ProgramResult, ...]
    discovery_view: DiscoveryView
    dataset_evidence_id: str


def _uuid(value: object) -> str:
    return semantic_identity("selection-bias-test", value)


def _proposal(spec: object) -> ResearchProposal:
    retained = spec.family in (
        StrategyFamily.MOVING_AVERAGE_TREND,
        StrategyFamily.DONCHIAN_BREAKOUT,
    )
    return ResearchProposal(
        campaign_version=CAMPAIGN_VERSION,
        generation=1,
        proposal_kind=(
            ProposalKind.RETAINED_BASELINE if retained else ProposalKind.ORIGINAL
        ),
        parent_proposal_ids=(),
        strategy_spec=spec,
        hypothesis="Synthetic closed rule fixture.",
        expected_mechanism="Synthetic trend variation tests the selection binding.",
        falsification_condition="The fixed synthetic return series has no variation.",
        source_reference_labels=("SYNTHETIC",),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_1_PRE_RESULTS,
            visible_evidence=(
                VisibleEvidenceReference(
                    reference_label="SYNTHETIC_A147",
                    dataset_label="SYNTHETIC_A147_DAILY",
                    timeframe=VisibleTimeframe.DAILY,
                    time_partition=VisibleTimePartition.PRIOR_RESEARCH_2022_2023,
                    classification=VisibleEvidenceClassification.PRIOR_CANONICAL,
                ),
            ),
        ),
        producer_label="selection-bias-test",
    )


def _build_view() -> DiscoveryView:
    sessions = tuple(
        session
        for session in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= session < date(2024, 1, 1)
    )
    datasets = []
    for symbol_index, symbol in enumerate(UNIVERSE):
        bars = []
        for index, session in enumerate(sessions):
            wave = Decimal((index * 7 + symbol_index * 5) % 29) / Decimal("50")
            trend = Decimal(index) / Decimal("1000")
            close = Decimal(90 + symbol_index) + wave + trend
            open_price = close + Decimal((index % 5) - 2) / Decimal("100")
            stamp = datetime.combine(session, time.min, _NY)
            bars.append(
                Bar(
                    Symbol(symbol),
                    stamp,
                    open_price,
                    max(open_price, close) + Decimal("0.5"),
                    min(open_price, close) - Decimal("0.5"),
                    close,
                    1000,
                )
            )
        datasets.append(SymbolDataset(symbol, tuple(bars), ProviderProvenance()))
    return DiscoveryView.from_dataset(MultiAssetDataset(tuple(datasets)))


def _make_continuous_cell(
    proposal_id: str,
    symbol: str,
    symbol_index: int,
    candidate_index: int,
    full_bars: tuple[Bar, ...],
) -> CellEvidence:
    scoring_bars = tuple(
        bar
        for bar in full_bars
        if date(2019, 1, 1) <= bar.timestamp.astimezone(_NY).date() < date(2022, 1, 1)
    )
    fill_index = (candidate_index * 7 + symbol_index * 3) % 80
    fill_bar = scoring_bars[fill_index]
    if fill_index == 0:
        information_through = full_bars[
            next(
                index
                for index, bar in enumerate(full_bars)
                if bar.timestamp == scoring_bars[0].timestamp
            )
            - 1
        ].timestamp
    else:
        information_through = scoring_bars[fill_index - 1].timestamp

    ledger = PaperLedger(STARTING_CASH)
    with localcontext(CONTEXT):
        slipped = fill_bar.open * (
            Decimal("1") + STRESS_COSTS.slippage_bps / Decimal("10000")
        )
        quantity = (
            (ledger.cash * ALLOCATION - STRESS_COSTS.commission) / slipped
        ).to_integral_value(rounding=ROUND_FLOOR)
        fill_id = UUID(_uuid(("fill", proposal_id, symbol)))
        fill = OrderFill(
            fill_id=fill_id,
            order_id=fill_id,
            symbol=fill_bar.symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            price=slipped,
            commission=STRESS_COSTS.commission,
            filled_at=fill_bar.timestamp,
        )
        cash_after = ledger.cash - quantity * slipped - STRESS_COSTS.commission
        fill_evidence = FillEvidence(
            identity=str(fill_id),
            session=fill_bar.timestamp.isoformat(),
            information_through=information_through.isoformat(),
            side="BUY",
            quantity=quantity,
            execution_open=fill_bar.open,
            price=slipped,
            commission=STRESS_COSTS.commission,
            cash_after=cash_after,
            risk_outcome="APPROVED",
        )
        equity_values = [STARTING_CASH]
        for index, bar in enumerate(scoring_bars):
            if index == fill_index:
                ledger.apply_fill(fill)
            equity_values.append(
                ledger.create_account_snapshot(
                    {bar.symbol: bar.close}, bar.timestamp
                ).equity
            )
        final_equity = equity_values[-1]
        total_return = final_equity / STARTING_CASH - Decimal("1")

    stress = Metrics(
        total_return=total_return,
        maximum_drawdown=Decimal("0"),
        final_equity=final_equity,
        realized_profit_loss=ledger.realized_profit_loss,
        fill_count=1,
        closed_trades=0,
        turnover=Decimal("0"),
        time_invested=Decimal("1"),
        equity_trace_identity=semantic_identity("equity-trace", tuple(equity_values)),
        fills=(fill_evidence,),
    )
    return CellEvidence(
        candidate_id=proposal_id,
        symbol=symbol,
        regime="continuous",
        result_id=_uuid((proposal_id, symbol, "continuous")),
        base=stress,
        stress=stress,
        buy_and_hold=stress,
        buy_and_hold_stress=stress,
        atr=AtrDescription(
            count=1,
            minimum=Decimal("1"),
            median=Decimal("1"),
            maximum=Decimal("1"),
            median_close_fraction=Decimal("0.01"),
        ),
        session_count=len(scoring_bars),
        first_session=scoring_bars[0].timestamp.isoformat(),
        last_session=scoring_bars[-1].timestamp.isoformat(),
    )


def _year_cell(cell: CellEvidence, year: int) -> CellEvidence:
    return replace(
        cell,
        regime=str(year),
        result_id=_uuid((cell.candidate_id, cell.symbol, year)),
        first_session=datetime.combine(date(year, 1, 2), time.min, _NY).isoformat(),
        last_session=datetime.combine(date(year, 12, 31), time.min, _NY).isoformat(),
    )


def _economic_summary() -> EconomicSummary:
    return EconomicSummary(
        continuous_symbol_returns=tuple(
            (symbol, Decimal("0.1")) for symbol in UNIVERSE
        ),
        annual_asset_year_returns=tuple(
            (symbol, str(year), Decimal("0.1"))
            for symbol in UNIVERSE
            for year in (2019, 2020, 2021)
        ),
        median_continuous_return=Decimal("0.1"),
        minimum_continuous_return=Decimal("0.1"),
        positive_continuous_symbols=8,
        positive_asset_year_cells=24,
        worst_continuous_drawdown=Decimal("0"),
        annual_asset_year_turnovers=tuple(
            (symbol, str(year), Decimal("0.1"))
            for symbol in UNIVERSE
            for year in (2019, 2020, 2021)
        ),
        median_annual_turnover=Decimal("0.1"),
        discovery_cell_buy_entry_count=8,
        discovery_cell_fill_count=8,
        discovery_cell_closed_trade_count=0,
        median_continuous_time_invested=Decimal("1"),
        median_continuous_buy_and_hold_return=Decimal("0.1"),
        largest_symbol_absolute_return_share=Decimal("0.125"),
        largest_year_absolute_return_share=Decimal("0.34"),
    )


def _build_evidence() -> _SyntheticEvidence:
    view = _build_view()
    proposal_set = Generation1ProposalSet(
        campaign_version=CAMPAIGN_VERSION,
        generation0_inventory_id=_G0_ID,
        foundation_id=_FOUNDATION_ID,
        source_head=_G1_HEAD,
        source_tree=_G1_TREE,
        proposals=tuple(_proposal(spec) for spec in frozen_generation1_specs()),
    )
    result_rows = []
    for candidate_index, proposal in enumerate(proposal_set.proposals):
        cells = []
        for symbol_index, symbol in enumerate(UNIVERSE):
            continuous = _make_continuous_cell(
                proposal.proposal_id,
                symbol,
                symbol_index,
                candidate_index,
                view.bars_for(symbol),
            )
            cells.extend(_year_cell(continuous, year) for year in (2019, 2020, 2021))
            cells.append(continuous)
        result_rows.append(
            Generation1ProgramResult(
                proposal.proposal_id,
                proposal.semantic_program_id,
                view.dataset_identity,
                tuple(cells),
            )
        )
    results = tuple(result_rows)
    economic_summary = _economic_summary()
    analysis_programs = tuple(
        ProgramAnalysis(
            proposal_id=proposal.proposal_id,
            semantic_program_id=proposal.semantic_program_id,
            outcome_identity=result.identity,
            disposition=(
                TrialDisposition.SHORTLISTED
                if index < 12
                else TrialDisposition.ECONOMICALLY_REJECTED
            ),
            base=economic_summary,
            stress=economic_summary,
            nondominated=index < 12,
        )
        for index, (proposal, result) in enumerate(
            zip(proposal_set.proposals, results, strict=True)
        )
    )
    analysis = Generation1BatchAnalysis(
        proposal_set_identity=proposal_set.identity,
        dataset_identity=view.dataset_identity,
        programs=analysis_programs,
        pareto_front_proposal_ids=tuple(
            proposal.proposal_id for proposal in proposal_set.proposals[:12]
        ),
    )

    dataset_evidence_id = _uuid("accepted-a147-evidence")
    records = [
        TrialLedgerRecord(
            event_ordinal=index + 1,
            trial_ordinal=index + 1,
            proposal=proposal,
            disposition=TrialDisposition.ACCEPTED_FOR_EVALUATION,
        )
        for index, proposal in enumerate(proposal_set.proposals)
    ]
    for index, (proposal, result, program) in enumerate(
        zip(proposal_set.proposals, results, analysis.programs, strict=True)
    ):
        records.append(
            TrialLedgerRecord(
                event_ordinal=len(records) + 1,
                trial_ordinal=index + 1,
                proposal=proposal,
                disposition=program.disposition,
                evaluation_attempt_id=_uuid(("attempt", proposal.proposal_id)),
                evaluation_source_head=_G1_HEAD,
                evaluation_source_tree=_G1_TREE,
                dataset_evidence_id=dataset_evidence_id,
                evaluation_id=_uuid(("evaluation", proposal.proposal_id)),
                result_id=result.identity,
                terminal_diagnostic_code=(
                    "G1_SHORTLISTED_NONDOMINATED"
                    if program.disposition is TrialDisposition.SHORTLISTED
                    else "G1_ECONOMICALLY_REJECTED"
                ),
                pnl_visible=True,
                diagnostic_visible=True,
            )
        )
    terminal_ledger = TrialLedger(tuple(records))
    return _SyntheticEvidence(
        proposal_set=proposal_set,
        terminal_ledger=terminal_ledger,
        analysis=analysis,
        results=results,
        discovery_view=view,
        dataset_evidence_id=dataset_evidence_id,
    )


@pytest.fixture(scope="module")
def synthetic_evidence() -> _SyntheticEvidence:
    return _build_evidence()


def _bind_synthetic_acceptance(
    monkeypatch: pytest.MonkeyPatch, evidence: _SyntheticEvidence
) -> None:
    monkeypatch.setattr(
        selection_bias,
        "_ACCEPTED_G1_PROPOSAL_SET_ID",
        evidence.proposal_set.identity,
    )
    monkeypatch.setattr(
        selection_bias,
        "_ACCEPTED_G1_PROPOSAL_SET_SHA256",
        hashlib.sha256(evidence.proposal_set.to_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        selection_bias, "_ACCEPTED_G1_ANALYSIS_ID", evidence.analysis.identity
    )
    monkeypatch.setattr(
        selection_bias,
        "_ACCEPTED_G1_TERMINAL_LEDGER_ID",
        evidence.terminal_ledger.ledger_id,
    )


def _evaluate(evidence: _SyntheticEvidence) -> selection_bias.SelectionBiasReport:
    return selection_bias.evaluate_generation1_selection_bias(
        evidence.proposal_set,
        evidence.terminal_ledger,
        evidence.analysis,
        evidence.results,
        evidence.discovery_view,
        source_head=_SELECTION_HEAD,
        source_tree=_SELECTION_TREE,
    )


def test_selection_bias_binds_all_22_programs_and_only_12_shortlisted(
    synthetic_evidence: _SyntheticEvidence,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_synthetic_acceptance(monkeypatch, synthetic_evidence)
    seen_bounds: list[tuple[date, date]] = []
    original_reconstruction = selection_bias.reconstruct_stress_equity

    def tracked_reconstruction(cell: CellEvidence, bars: tuple[Bar, ...]):
        sessions = tuple(bar.timestamp.astimezone(_NY).date() for bar in bars)
        assert min(sessions) >= date(2019, 1, 1)
        assert max(sessions) < date(2022, 1, 1)
        seen_bounds.append((min(sessions), max(sessions)))
        return original_reconstruction(cell, bars)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("selection-bias analysis must not replay a G1 strategy")

    monkeypatch.setattr(
        selection_bias, "reconstruct_stress_equity", tracked_reconstruction
    )
    monkeypatch.setattr(generation1, "generation1_signal_series", forbidden)
    monkeypatch.setattr(generation1, "evaluate_generation1_program", forbidden)

    report = _evaluate(synthetic_evidence)

    assert len(seen_bounds) == 22 * 8
    assert len(report.programs) == 22
    assert report.search_benchmark.trial_count == 22
    assert report.search_benchmark.population_statistics_identities == tuple(
        item.statistics.identity for item in report.programs
    )
    assert len(report.eligible_shortlisted_proposal_ids) == 12
    assert report.eligible_shortlisted_proposal_ids == tuple(
        proposal.proposal_id
        for proposal in synthetic_evidence.proposal_set.proposals[:12]
    )
    assert all(item.inference is not None for item in report.programs[:12])
    assert all(item.inference is None for item in report.programs[12:])
    assert all(
        item.statistics.observation_count == len(item.daily_returns)
        for item in report.programs
    )
    assert all(item.daily_returns for item in report.programs)
    assert report.to_dict()["campaign_trial_count"] == 28
    assert report.to_dict()["campaign_alpha"] == decimal_text(CAMPAIGN_FAMILYWISE_ALPHA)
    assert report.zero_effects
    assert all(value == 0 for _, value in report.zero_effects)
    assert report.final_holdout_sealed is True
    encoded = report.to_bytes()
    assert canonical_json_bytes(json.loads(encoded)) == encoded


def test_selection_bias_rejects_reordered_results_and_trace_mismatch(
    synthetic_evidence: _SyntheticEvidence,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_synthetic_acceptance(monkeypatch, synthetic_evidence)
    with pytest.raises(
        selection_bias.SelectionBiasError, match="incomplete, reordered"
    ):
        selection_bias.evaluate_generation1_selection_bias(
            synthetic_evidence.proposal_set,
            synthetic_evidence.terminal_ledger,
            synthetic_evidence.analysis,
            tuple(reversed(synthetic_evidence.results)),
            synthetic_evidence.discovery_view,
            source_head=_SELECTION_HEAD,
            source_tree=_SELECTION_TREE,
        )

    original_reconstruction = selection_bias.reconstruct_stress_equity
    original_aggregation = selection_bias.aggregate_g1_basket
    aggregate_calls = 0

    def wrong_trace(cell: CellEvidence, bars: tuple[Bar, ...]):
        sleeve = original_reconstruction(cell, bars)
        return SimpleNamespace(
            symbol=sleeve.symbol,
            candidate_id=sleeve.candidate_id,
            trace_identity=_uuid((sleeve.trace_identity, "wrong")),
        )

    def tracked_aggregation(sleeves: tuple[object, ...]):
        nonlocal aggregate_calls
        aggregate_calls += 1
        return original_aggregation(sleeves)  # pragma: no cover

    monkeypatch.setattr(selection_bias, "reconstruct_stress_equity", wrong_trace)
    monkeypatch.setattr(selection_bias, "aggregate_g1_basket", tracked_aggregation)
    with pytest.raises(
        selection_bias.SelectionBiasError, match="equity identity mismatch"
    ):
        _evaluate(synthetic_evidence)
    assert aggregate_calls == 0


def test_shortlist_only_population_cannot_define_the_g1_search_benchmark(
    synthetic_evidence: _SyntheticEvidence,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_synthetic_acceptance(monkeypatch, synthetic_evidence)
    shortlist_only = Generation1ProposalSet(
        campaign_version=synthetic_evidence.proposal_set.campaign_version,
        generation0_inventory_id=synthetic_evidence.proposal_set.generation0_inventory_id,
        foundation_id=synthetic_evidence.proposal_set.foundation_id,
        source_head=synthetic_evidence.proposal_set.source_head,
        source_tree=synthetic_evidence.proposal_set.source_tree,
        proposals=synthetic_evidence.proposal_set.proposals[:12],
    )
    monkeypatch.setattr(
        selection_bias, "_ACCEPTED_G1_PROPOSAL_SET_ID", shortlist_only.identity
    )
    monkeypatch.setattr(
        selection_bias,
        "_ACCEPTED_G1_PROPOSAL_SET_SHA256",
        hashlib.sha256(shortlist_only.to_bytes()).hexdigest(),
    )
    with pytest.raises(
        selection_bias.SelectionBiasError,
        match="exact accepted 22-program G1 set",
    ):
        selection_bias.evaluate_generation1_selection_bias(
            shortlist_only,
            synthetic_evidence.terminal_ledger,
            synthetic_evidence.analysis,
            synthetic_evidence.results,
            synthetic_evidence.discovery_view,
            source_head=_SELECTION_HEAD,
            source_tree=_SELECTION_TREE,
        )


def test_selection_bias_rejects_g2_results_post_2021_bars_and_holdout_input(
    synthetic_evidence: _SyntheticEvidence,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_synthetic_acceptance(monkeypatch, synthetic_evidence)
    forged_g2_result = object.__new__(Generation2ProgramResult)
    with pytest.raises(
        selection_bias.SelectionBiasError, match="complete typed G1 result"
    ):
        selection_bias.evaluate_generation1_selection_bias(
            synthetic_evidence.proposal_set,
            synthetic_evidence.terminal_ledger,
            synthetic_evidence.analysis,
            (forged_g2_result, *synthetic_evidence.results[1:]),
            synthetic_evidence.discovery_view,
            source_head=_SELECTION_HEAD,
            source_tree=_SELECTION_TREE,
        )

    view = synthetic_evidence.discovery_view
    bad_view = object.__new__(DiscoveryView)
    for name in (
        "dataset_identity",
        "price_basis",
        "provider_provenance",
        "symbol_bars",
        "identity",
    ):
        object.__setattr__(bad_view, name, getattr(view, name))
    first = view.symbol_bars[0]
    future_bar = Bar(
        Symbol(first.symbol),
        datetime(2022, 1, 3, tzinfo=_NY),
        Decimal("100"),
        Decimal("101"),
        Decimal("99"),
        Decimal("100"),
        1000,
    )
    forged_symbol_bars = object.__new__(type(first))
    object.__setattr__(forged_symbol_bars, "symbol", first.symbol)
    object.__setattr__(forged_symbol_bars, "bars", (*first.bars, future_bar))
    object.__setattr__(
        bad_view, "symbol_bars", (forged_symbol_bars, *view.symbol_bars[1:])
    )
    with pytest.raises(selection_bias.SelectionBiasError, match="post-2021 bars"):
        selection_bias.evaluate_generation1_selection_bias(
            synthetic_evidence.proposal_set,
            synthetic_evidence.terminal_ledger,
            synthetic_evidence.analysis,
            synthetic_evidence.results,
            bad_view,
            source_head=_SELECTION_HEAD,
            source_tree=_SELECTION_TREE,
        )

    with pytest.raises(TypeError):
        selection_bias.evaluate_generation1_selection_bias(
            synthetic_evidence.proposal_set,
            synthetic_evidence.terminal_ledger,
            synthetic_evidence.analysis,
            synthetic_evidence.results,
            synthetic_evidence.discovery_view,
            source_head=_SELECTION_HEAD,
            source_tree=_SELECTION_TREE,
            final_holdout=object(),  # type: ignore[call-arg]
        )
