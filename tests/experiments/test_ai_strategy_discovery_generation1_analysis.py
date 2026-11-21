from __future__ import annotations

import os
import socket
import subprocess
import urllib.request
from datetime import date, datetime, time
from decimal import Decimal
from functools import cache
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    AbsoluteMomentumSpec,
    DeferredStrategySpec,
    InformationVisibility,
    InvalidProposalReference,
    MomentumGate,
    MovingAverageRule,
    MovingAverageTrendSpec,
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
    ZERO_EFFECT_COUNTER_NAMES,
    Generation1AnalysisError,
    Generation1FailureCode,
    analyze_generation1_batch,
    run_generation1_batch,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_plan import (
    Generation1ProposalSet,
)
from trading_bot.experiments.filtered_trend_campaign import (
    AtrDescription,
    CellEvidence,
    FillEvidence,
    Metrics,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    ProviderProvenance,
    SymbolDataset,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

_GENERATION0_ID = "08395fd5-43a4-5a81-9992-877560757a9f"
_FOUNDATION_ID = "00a845be-228a-56c6-9fd1-9b76c2176cf8"
_DATA_EVIDENCE_ID = "d8c6e9d2-e6a6-5a1d-8f14-90b3d729d1d5"
_HEAD = "a" * 40
_TREE = "b" * 40
_NY = ZoneInfo("America/New_York")
_YEARS = ("2019", "2020", "2021")
_EXPECTED_CELLS = tuple(
    (symbol, label) for symbol in UNIVERSE for label in (*_YEARS, "continuous")
)
_ANNUAL = tuple((symbol, year) for symbol in UNIVERSE for year in _YEARS)


def _uuid(label: str) -> str:
    return semantic_identity("g1-analysis-test", label)


def _proposal(
    spec: object,
    *,
    hypothesis: str = "A closed daily rule may persist across symbols.",
    producer: str = "analysis-fixture",
) -> ResearchProposal:
    family = spec.family
    retained = family in (
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
        hypothesis=hypothesis,
        expected_mechanism="The frozen rule captures persistent trends.",
        falsification_condition="Stress breadth gates fail.",
        source_reference_labels=("PRIOR_A147",),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_1_PRE_RESULTS,
            visible_evidence=(evidence,),
        ),
        producer_label=producer,
    )


def _plan(proposals: tuple[ResearchProposal, ...]) -> Generation1ProposalSet:
    return Generation1ProposalSet(
        campaign_version=CAMPAIGN_VERSION,
        generation0_inventory_id=_GENERATION0_ID,
        foundation_id=_FOUNDATION_ID,
        source_head=_HEAD,
        source_tree=_TREE,
        proposals=proposals,
    )


def _metric(
    total_return: Decimal,
    *,
    drawdown: Decimal,
    turnover: Decimal,
    buy: bool = False,
) -> Metrics:
    fills = (
        (
            FillEvidence(
                identity=_uuid(("fill", total_return, turnover)),
                session="2019-01-02",
                information_through="2019-01-01",
                side="BUY",
                quantity=Decimal("1"),
                execution_open=Decimal("100"),
                price=Decimal("100"),
                commission=Decimal("1"),
                cash_after=Decimal("899"),
                risk_outcome="ACCEPTED",
            ),
        )
        if buy
        else ()
    )
    return Metrics(
        total_return=total_return,
        maximum_drawdown=drawdown,
        final_equity=Decimal("100000") * (Decimal(1) + total_return),
        realized_profit_loss=Decimal(0),
        fill_count=len(fills),
        closed_trades=0,
        turnover=turnover,
        time_invested=Decimal("0.5") if buy else Decimal(0),
        equity_trace_identity=_uuid(("trace", total_return, turnover)),
        fills=fills,
    )


def _cell_stamp(label: str, *, end: bool) -> str:
    if label == "continuous":
        day = date(2021, 12, 31) if end else date(2019, 1, 2)
    else:
        year = int(label)
        day = date(year, 12, 31) if end else date(year, 1, 2)
    return datetime.combine(day, time.min, _NY).isoformat()


def _result(
    proposal: ResearchProposal,
    dataset_identity: str,
    *,
    continuous: tuple[Decimal, ...] | None = None,
    positive_annual_cells: int = 24,
    annual_return: Decimal = Decimal("0.1"),
    drawdown: Decimal = Decimal("0.1"),
    turnover: Decimal = Decimal("0.2"),
    buy_in_cell: int | None = None,
) -> Generation1ProgramResult:
    continuous_values = continuous or (annual_return,) * len(UNIVERSE)
    assert len(continuous_values) == len(UNIVERSE)
    cells = []
    for index, (symbol, label) in enumerate(_EXPECTED_CELLS):
        if label == "continuous":
            value = continuous_values[UNIVERSE.index(symbol)]
        else:
            annual_index = _ANNUAL.index((symbol, label))
            value = (
                annual_return
                if annual_index < positive_annual_cells
                else -abs(annual_return)
            )
        buy = index == buy_in_cell
        base = _metric(value, drawdown=drawdown, turnover=turnover, buy=buy)
        stress = _metric(value, drawdown=drawdown, turnover=turnover, buy=buy)
        buy_hold = _metric(
            value / Decimal(2), drawdown=Decimal("0.2"), turnover=Decimal(0)
        )
        buy_hold_stress = _metric(
            value / Decimal(3), drawdown=Decimal("0.3"), turnover=Decimal(0)
        )
        cells.append(
            CellEvidence(
                candidate_id=proposal.proposal_id,
                symbol=symbol,
                regime=label,
                result_id=_uuid((proposal.proposal_id, symbol, label)),
                base=base,
                stress=stress,
                buy_and_hold=buy_hold,
                buy_and_hold_stress=buy_hold_stress,
                atr=AtrDescription(
                    1, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("0.01")
                ),
                session_count=20,
                first_session=_cell_stamp(label, end=False),
                last_session=_cell_stamp(label, end=True),
            )
        )
    return Generation1ProgramResult(
        proposal.proposal_id,
        proposal.semantic_program_id,
        dataset_identity,
        tuple(cells),
    )


@cache
def _synthetic_view() -> DiscoveryView:
    """A small purpose-built synthetic dataset, never sourced from a provider."""
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
            close = Decimal(100 + symbol_index) + Decimal(index) / Decimal(1000)
            stamp = datetime.combine(session, time.min, _NY)
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
    return DiscoveryView.from_dataset(MultiAssetDataset(tuple(datasets)))


def _view_without_replay_identity() -> DiscoveryView:
    """Build a bounded exact-type view for tests that stub the fixed evaluator."""
    return _synthetic_view()


def test_analyzer_requires_exact_complete_ordered_outcomes() -> None:
    proposals = (
        _proposal(MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA)),
        _proposal(AbsoluteMomentumSpec(63, MomentumGate.NONE)),
    )
    plan = _plan(proposals)
    dataset_id = _uuid("dataset")
    outcomes = tuple(_result(item, dataset_id) for item in proposals)

    analysis = analyze_generation1_batch(
        plan, outcomes, expected_dataset_identity=dataset_id
    )
    assert (
        tuple(item.proposal_id for item in analysis.programs)
        == plan.proposal_identities
    )
    for malformed in (
        outcomes[:1],
        (outcomes[0], outcomes[0]),
        (
            outcomes[0],
            _result(
                _proposal(AbsoluteMomentumSpec(126, MomentumGate.NONE)), dataset_id
            ),
        ),
        tuple(reversed(outcomes)),
    ):
        with pytest.raises(Generation1AnalysisError):
            analyze_generation1_batch(
                plan, malformed, expected_dataset_identity=dataset_id
            )


def test_dispositions_use_stress_gates_and_complete_pareto_frontier() -> None:
    top = _proposal(MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA))
    tie = _proposal(AbsoluteMomentumSpec(63, MomentumGate.NONE))
    dominated = _proposal(AbsoluteMomentumSpec(126, MomentumGate.NONE))
    edge = _proposal(
        MovingAverageTrendSpec(35, 50, MovingAverageRule.MA_PERCENT_BAND_010)
    )
    zero = _proposal(AbsoluteMomentumSpec(252, MomentumGate.NONE))
    proposals = (top, tie, dominated, edge, zero)
    plan = _plan(proposals)
    dataset_id = _uuid("dataset-pareto")
    edge_returns = (
        Decimal("-0.1"),
        Decimal("-0.1"),
        Decimal("-0.1"),
        Decimal("0.01"),
        Decimal("0.02"),
        Decimal("0.03"),
        Decimal("0.04"),
        Decimal("0.05"),
    )
    outcomes = (
        _result(
            top,
            dataset_id,
            annual_return=Decimal("0.1"),
            drawdown=Decimal("0.1"),
            turnover=Decimal("0.2"),
            buy_in_cell=0,
        ),
        _result(
            tie,
            dataset_id,
            annual_return=Decimal("0.1"),
            drawdown=Decimal("0.1"),
            turnover=Decimal("0.2"),
            buy_in_cell=0,
        ),
        _result(
            dominated,
            dataset_id,
            annual_return=Decimal("0.03"),
            positive_annual_cells=24,
            drawdown=Decimal("0.2"),
            turnover=Decimal("0.3"),
            buy_in_cell=0,
        ),
        _result(
            edge,
            dataset_id,
            continuous=edge_returns,
            positive_annual_cells=13,
            annual_return=Decimal("0.01"),
            drawdown=Decimal("0.05"),
            turnover=Decimal("0.1"),
            buy_in_cell=0,
        ),
        _result(
            zero,
            dataset_id,
            continuous=(Decimal(0),) * 8,
            positive_annual_cells=0,
            annual_return=Decimal(0),
            drawdown=Decimal("0.5"),
            turnover=Decimal("0.5"),
        ),
    )

    analysis = analyze_generation1_batch(
        plan, outcomes, expected_dataset_identity=dataset_id
    )
    by_id = {item.proposal_id: item for item in analysis.programs}
    assert by_id[top.proposal_id].disposition is TrialDisposition.SHORTLISTED
    assert by_id[tie.proposal_id].disposition is TrialDisposition.SHORTLISTED
    assert by_id[edge.proposal_id].disposition is TrialDisposition.SHORTLISTED
    assert (
        by_id[dominated.proposal_id].disposition
        is TrialDisposition.ECONOMICALLY_REJECTED
    )
    assert by_id[zero.proposal_id].disposition is TrialDisposition.ZERO_TRADE
    assert set(analysis.pareto_front_proposal_ids) == {
        top.proposal_id,
        tie.proposal_id,
        edge.proposal_id,
    }
    assert by_id[top.proposal_id].stress is not None
    assert by_id[top.proposal_id].stress.median_continuous_return == Decimal("0.1")
    assert by_id[top.proposal_id].stress.positive_continuous_symbols == 8
    assert by_id[edge.proposal_id].stress is not None
    assert by_id[edge.proposal_id].stress.positive_continuous_symbols == 5
    assert by_id[edge.proposal_id].stress.positive_asset_year_cells == 13
    assert by_id[edge.proposal_id].stress.median_annual_turnover == Decimal("0.1")


def test_zero_trade_counts_buy_entries_over_all_32_cells_and_both_economics() -> None:
    proposal = _proposal(MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA))
    plan = _plan((proposal,))
    dataset_id = _uuid("dataset-buy-count")
    result = _result(
        proposal,
        dataset_id,
        continuous=(Decimal(0),) * 8,
        positive_annual_cells=0,
        annual_return=Decimal(0),
        buy_in_cell=0,
    )

    analysis = analyze_generation1_batch(
        plan, (result,), expected_dataset_identity=dataset_id
    )
    item = analysis.programs[0]
    assert item.disposition is TrialDisposition.ECONOMICALLY_REJECTED
    assert item.base is not None and item.base.discovery_cell_buy_entry_count == 1
    assert item.stress is not None and item.stress.discovery_cell_buy_entry_count == 1


def test_runner_preserves_prior_history_and_reports_zero_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _proposal(MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA))
    second = _proposal(AbsoluteMomentumSpec(63, MomentumGate.NONE))
    plan = _plan((first, second))
    alias = _proposal(
        first.strategy_spec,
        hypothesis="A prose alias for the same immutable semantic program.",
        producer="another-reviewer",
    )
    exact_resend = first
    invalid = InvalidProposalReference(
        generation=1,
        caller_semantic_fingerprint="0" * 64,
        diagnostic_code="MALFORMED_FIXTURE",
        source_reference_labels=("LOCAL_FIXTURE",),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_1_PRE_RESULTS,
            visible_evidence=(),
        ),
        producer_label="analysis-fixture",
    )
    unsupported = _proposal(
        DeferredStrategySpec(StrategyFamily.FIXED_ENSEMBLE),
        hypothesis="A retained but unsupported proposal.",
    )
    prior = TrialLedger(
        (
            TrialLedgerRecord(1, 1, first, TrialDisposition.ACCEPTED_FOR_EVALUATION),
            TrialLedgerRecord(
                2,
                2,
                alias,
                TrialDisposition.DUPLICATE_REJECTED,
                terminal_diagnostic_code="DUPLICATE_SEMANTIC_PROGRAM",
            ),
            TrialLedgerRecord(
                3,
                3,
                exact_resend,
                TrialDisposition.DUPLICATE_REJECTED,
                terminal_diagnostic_code="DUPLICATE_SEMANTIC_PROGRAM",
            ),
            TrialLedgerRecord(
                4,
                4,
                invalid,
                TrialDisposition.INVALID,
                terminal_diagnostic_code="MALFORMED_FIXTURE",
            ),
            TrialLedgerRecord(
                5,
                5,
                unsupported,
                TrialDisposition.UNSUPPORTED,
                terminal_diagnostic_code="NO_ACCEPTED_STANDALONE_EVALUATOR",
            ),
        )
    )
    view = _view_without_replay_identity()
    results = {
        proposal.proposal_id: _result(proposal, view.dataset_identity)
        for proposal in plan.proposals
    }

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the G1 batch runner attempted an external effect")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    import trading_bot.experiments.ai_strategy_discovery_generation1_analysis as module

    calls: list[str] = []

    def evaluator(proposal: ResearchProposal, bounded_view: DiscoveryView):
        assert bounded_view is view
        calls.append(proposal.proposal_id)
        if proposal is first:
            raise ValueError("synthetic deterministic replay rejection")
        return results[proposal.proposal_id]

    monkeypatch.setattr(module, "evaluate_generation1_program", evaluator)
    run = run_generation1_batch(
        plan,
        prior,
        view,
        expected_source_head=_HEAD,
        expected_source_tree=_TREE,
        expected_generation0_inventory_id=_GENERATION0_ID,
        expected_foundation_id=_FOUNDATION_ID,
        expected_dataset_identity=view.dataset_identity,
        dataset_evidence_id=_DATA_EVIDENCE_ID,
    )

    assert calls == list(plan.proposal_identities)
    assert run.pre_evaluation_ledger.records[: len(prior.records)] == prior.records
    assert tuple(
        record.disposition
        for record in run.pre_evaluation_ledger.records[len(prior.records) :]
    ) == (TrialDisposition.ACCEPTED_FOR_EVALUATION,)
    assert run.pre_evaluation_ledger.evaluated_trial_count == 0
    assert run.terminal_ledger.evaluated_trial_count == 2
    assert run.terminal_ledger.records[1:3] == prior.records[1:3]
    assert (
        run.outcomes[0].failure_code
        is Generation1FailureCode.DETERMINISTIC_EVALUATION_VALUE_ERROR
    )
    assert (
        run.outcomes[0].attempt_id
        == run.terminal_ledger.records[-2].evaluation_attempt_id
    )
    assert (
        run.outcomes[0].evaluation_id == run.terminal_ledger.records[-2].evaluation_id
    )
    assert all(
        record.dataset_evidence_id == _DATA_EVIDENCE_ID
        and not record.pnl_visible
        and not record.diagnostic_visible
        for record in run.terminal_ledger.records[-2:]
    )
    assert tuple(name for name, _ in run.zero_effects) == ZERO_EFFECT_COUNTER_NAMES
    assert all(value == 0 for _, value in run.zero_effects)
    assert run.final_holdout_sealed is True
    assert plan.final_holdout_sealed is True


def test_runner_refuses_replay_and_propagates_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal = _proposal(MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA))
    plan = _plan((proposal,))
    view = _view_without_replay_identity()
    counted = TrialLedger(
        (
            TrialLedgerRecord(1, 1, proposal, TrialDisposition.ACCEPTED_FOR_EVALUATION),
            TrialLedgerRecord(
                2,
                1,
                proposal,
                TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
                evaluation_attempt_id=_uuid("prior-attempt"),
                evaluation_source_head=_HEAD,
                evaluation_source_tree=_TREE,
                dataset_evidence_id=_DATA_EVIDENCE_ID,
                evaluation_id=_uuid("prior-evaluation"),
                terminal_diagnostic_code="PRIOR_FAILURE",
            ),
        )
    )
    import trading_bot.experiments.ai_strategy_discovery_generation1_analysis as module

    calls = 0

    def forbidden_replay(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        raise AssertionError("counted history must be rejected before evaluator call")

    monkeypatch.setattr(module, "evaluate_generation1_program", forbidden_replay)
    kwargs = dict(
        expected_source_head=_HEAD,
        expected_source_tree=_TREE,
        expected_generation0_inventory_id=_GENERATION0_ID,
        expected_foundation_id=_FOUNDATION_ID,
        expected_dataset_identity=view.dataset_identity,
        dataset_evidence_id=_DATA_EVIDENCE_ID,
    )
    with pytest.raises(Generation1AnalysisError, match="replay is forbidden"):
        run_generation1_batch(plan, counted, view, **kwargs)
    assert calls == 0

    prior = TrialLedger(())

    def unexpected(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        raise RuntimeError("unexpected fixture failure")

    monkeypatch.setattr(module, "evaluate_generation1_program", unexpected)
    with pytest.raises(RuntimeError, match="unexpected fixture failure"):
        run_generation1_batch(plan, prior, view, **kwargs)
    assert calls == 1
