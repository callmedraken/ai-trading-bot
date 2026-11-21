from __future__ import annotations

import os
import socket
import subprocess
import urllib.request
from datetime import UTC, date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    ConjunctiveTrendSpec,
    Generation1DiagnosticReference,
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
    frozen_generation2_parent_pairs,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_analysis import (
    ZERO_EFFECT_COUNTER_NAMES,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_plan import (
    Generation1ProposalSet,
)
from trading_bot.experiments.ai_strategy_discovery_generation2 import (
    ConfirmationView,
    Generation2ProgramResult,
)
from trading_bot.experiments.ai_strategy_discovery_generation2_analysis import (
    Generation2AnalysisError,
    Generation2EvaluationFailure,
    Generation2FailureCode,
    analyze_generation2_batch,
    run_generation2_batch,
)
from trading_bot.experiments.ai_strategy_discovery_generation2_plan import (
    Generation2ProposalSet,
)
from trading_bot.experiments.filtered_trend_campaign import (
    UNIVERSE,
    AtrDescription,
    CellEvidence,
    Metrics,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import (
    MultiAssetDataset,
    ProviderProvenance,
    SymbolDataset,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

NY = ZoneInfo("America/New_York")
_HEAD = "a" * 40
_TREE = "b" * 40
_G1_HEAD = "c" * 40
_G1_TREE = "d" * 40
_DATA_EVIDENCE_ID = str(uuid5(NAMESPACE_URL, "generation2-synthetic-evidence"))
_G1_INVENTORY_ID = str(uuid5(NAMESPACE_URL, "generation2-synthetic-inventory"))
_FOUNDATION_ID = str(uuid5(NAMESPACE_URL, "generation2-synthetic-foundation"))


def _uuid(label: object) -> str:
    return semantic_identity("g2-analysis-test", label)


def _spec_key(spec: object) -> str:
    return repr(spec.to_dict())


def _synthetic_g1_parent_proposals() -> tuple[ResearchProposal, ...]:
    by_key: dict[str, ResearchProposal] = {}
    for pair in frozen_generation2_parent_pairs():
        for _, spec in pair:
            key = _spec_key(spec)
            if key in by_key:
                continue
            family = spec.family
            retained = family in (
                StrategyFamily.MOVING_AVERAGE_TREND,
                StrategyFamily.DONCHIAN_BREAKOUT,
            )
            label = f"SYNTHETIC_G1_{len(by_key)}"
            evidence = VisibleEvidenceReference(
                reference_label=label,
                dataset_label="A147_SYNTHETIC_DAILY",
                timeframe=VisibleTimeframe.DAILY,
                time_partition=VisibleTimePartition.PRIOR_RESEARCH_2022_2023,
                classification=VisibleEvidenceClassification.PRIOR_CANONICAL,
            )
            by_key[key] = ResearchProposal(
                campaign_version=CAMPAIGN_VERSION,
                generation=1,
                proposal_kind=(
                    ProposalKind.RETAINED_BASELINE
                    if retained
                    else ProposalKind.ORIGINAL
                ),
                parent_proposal_ids=(),
                strategy_spec=spec,
                hypothesis="Synthetic parent proposal for isolated G2 runner tests.",
                expected_mechanism="Preserve its typed G1 signal semantics.",
                falsification_condition="The synthetic source fixture is bounded.",
                source_reference_labels=(label,),
                information_visibility=InformationVisibility(
                    VisibilityStage.GENERATION_1_PRE_RESULTS,
                    visible_evidence=(evidence,),
                ),
                producer_label="g2-analysis-synthetic-fixture",
            )
    return tuple(by_key.values())


def _synthetic_g1_terminal_ledger(
    parents: tuple[ResearchProposal, ...],
) -> TrialLedger:
    ledger = TrialLedger(())
    for trial_ordinal, proposal in enumerate(parents, start=1):
        ledger = ledger.append(
            TrialLedgerRecord(
                event_ordinal=len(ledger.records) + 1,
                trial_ordinal=trial_ordinal,
                proposal=proposal,
                disposition=TrialDisposition.ACCEPTED_FOR_EVALUATION,
            )
        )
    for trial_ordinal, proposal in enumerate(parents, start=1):
        ledger = ledger.append(
            TrialLedgerRecord(
                event_ordinal=len(ledger.records) + 1,
                trial_ordinal=trial_ordinal,
                proposal=proposal,
                disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
                evaluation_attempt_id=_uuid(("g1-attempt", proposal.proposal_id)),
                evaluation_source_head=_G1_HEAD,
                evaluation_source_tree=_G1_TREE,
                dataset_evidence_id=_DATA_EVIDENCE_ID,
                evaluation_id=_uuid(("g1-evaluation", proposal.proposal_id)),
                terminal_diagnostic_code="G1_SYNTHETIC_FIXTURE_FAILURE",
                pnl_visible=False,
                diagnostic_visible=True,
            )
        )
    return ledger


def _synthetic_g2_proposals(
    parents: tuple[ResearchProposal, ...], ledger: TrialLedger
) -> tuple[ResearchProposal, ...]:
    parent_by_spec = {_spec_key(item.strategy_spec): item for item in parents}
    terminal_by_id = {
        record.proposal_id: record
        for record in ledger.records
        if record.generation == 1 and record.evaluation_attempt_id is not None
    }
    proposals = []
    for pair in frozen_generation2_parent_pairs():
        selected = tuple(parent_by_spec[_spec_key(spec)] for _, spec in pair)
        ordered_parents = tuple(sorted(selected, key=lambda item: item.proposal_id))
        diagnostic_refs = tuple(
            Generation1DiagnosticReference(
                parent_proposal_id=parent.proposal_id,
                parent_trial_ordinal=terminal_by_id[parent.proposal_id].trial_ordinal,
                diagnostic_id=terminal_by_id[parent.proposal_id].diagnostic_id,
            )
            for parent in ordered_parents
        )
        evidence_refs = tuple(
            VisibleEvidenceReference(
                reference_label=f"G1_PARENT_{index}_{parent.proposal_id[:8]}",
                dataset_label="A147_SYNTHETIC_DAILY",
                timeframe=VisibleTimeframe.DAILY,
                time_partition=VisibleTimePartition.DISCOVERY_2019_2021,
                classification=(
                    VisibleEvidenceClassification.GENERATION_1_DISCOVERY_RESULT
                ),
            )
            for index, parent in enumerate(ordered_parents)
        )
        proposals.append(
            ResearchProposal(
                campaign_version=CAMPAIGN_VERSION,
                generation=2,
                proposal_kind=ProposalKind.RECOMBINATION,
                parent_proposal_ids=tuple(item.proposal_id for item in ordered_parents),
                strategy_spec=ConjunctiveTrendSpec(
                    components=tuple(spec for _, spec in pair)
                ),
                hypothesis="A fixed conjunctive gate may improve robustness.",
                expected_mechanism="Both typed parent signals must be LONG.",
                falsification_condition="A frozen confirmation gate fails.",
                source_reference_labels=tuple(
                    item.reference_label for item in evidence_refs
                ),
                information_visibility=InformationVisibility(
                    VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
                    visible_evidence=evidence_refs,
                    visible_generation1_diagnostics=diagnostic_refs,
                ),
                producer_label="g2-analysis-synthetic-fixture",
            )
        )
    return tuple(proposals)


def _synthetic_dataset() -> MultiAssetDataset:
    """Build deterministic fake prices and use only the published date calendar."""
    sessions = tuple(
        session
        for session in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= session < date(2024, 1, 1)
    )
    datasets = []
    provenance = ProviderProvenance()
    for symbol_index, symbol in enumerate(UNIVERSE):
        bars = []
        for index, session in enumerate(sessions):
            phase = index % 400
            trend = phase if phase < 200 else 400 - phase
            close = Decimal(100 + symbol_index) + Decimal(trend) / Decimal(10)
            stamp = datetime.combine(session, time.min, NY).astimezone(UTC)
            bars.append(
                Bar(
                    Symbol(symbol),
                    stamp,
                    close,
                    close + Decimal(1),
                    close - Decimal(1),
                    close,
                    1000,
                )
            )
        datasets.append(SymbolDataset(symbol, tuple(bars), provenance))
    return MultiAssetDataset(tuple(datasets))


def _fixture(
    monkeypatch: pytest.MonkeyPatch,
    view: ConfirmationView,
) -> tuple[Generation2ProposalSet, TrialLedger]:
    import trading_bot.experiments.ai_strategy_discovery_generation2_plan as plan_module

    parents = _synthetic_g1_parent_proposals()
    ledger = _synthetic_g1_terminal_ledger(parents)
    g1_set = Generation1ProposalSet(
        campaign_version=CAMPAIGN_VERSION,
        generation0_inventory_id=_G1_INVENTORY_ID,
        foundation_id=_FOUNDATION_ID,
        source_head=_G1_HEAD,
        source_tree=_G1_TREE,
        proposals=parents,
    )
    g1_analysis = SimpleNamespace(
        identity=_uuid("synthetic-g1-analysis"),
        dataset_identity=view.dataset_identity,
    )
    g2_proposals = _synthetic_g2_proposals(parents, ledger)
    monkeypatch.setattr(
        plan_module,
        "_validate_accepted_generation1_inputs",
        lambda *_args: _DATA_EVIDENCE_ID,
    )
    monkeypatch.setattr(
        plan_module,
        "_frozen_proposals",
        lambda *_args: g2_proposals,
    )
    proposal_set = Generation2ProposalSet(
        g1_set,
        g1_analysis,
        ledger,
        _HEAD,
        _TREE,
    )
    return proposal_set, ledger


def _metrics(
    total_return: Decimal,
    *,
    drawdown: Decimal,
    turnover: Decimal,
    identity: object,
) -> Metrics:
    return Metrics(
        total_return=total_return,
        maximum_drawdown=drawdown,
        final_equity=Decimal("100000") * (Decimal(1) + total_return),
        realized_profit_loss=Decimal(0),
        fill_count=0,
        closed_trades=0,
        turnover=turnover,
        time_invested=Decimal(0),
        equity_trace_identity=_uuid(("trace", identity)),
        fills=(),
    )


def _result(
    proposal: ResearchProposal,
    view: ConfirmationView,
    *,
    continuous: tuple[Decimal, ...] | None = None,
    returns_2022: tuple[Decimal, ...] | None = None,
    returns_2023: tuple[Decimal, ...] | None = None,
    stress_continuous: tuple[Decimal, ...] | None = None,
    stress_returns_2022: tuple[Decimal, ...] | None = None,
    stress_returns_2023: tuple[Decimal, ...] | None = None,
    drawdown: Decimal = Decimal("0.10"),
    turnover: Decimal = Decimal("0.20"),
) -> Generation2ProgramResult:
    continuous_values = continuous or (Decimal("0.20"),) * len(UNIVERSE)
    annual_values = {
        "2022": returns_2022 or (Decimal("0.10"),) * len(UNIVERSE),
        "2023": returns_2023 or (Decimal("0.10"),) * len(UNIVERSE),
    }
    stress_continuous_values = stress_continuous or continuous_values
    stress_annual_values = {
        "2022": stress_returns_2022 or annual_values["2022"],
        "2023": stress_returns_2023 or annual_values["2023"],
    }
    assert len(continuous_values) == len(UNIVERSE)
    assert len(stress_continuous_values) == len(UNIVERSE)
    assert all(
        len(values) == len(UNIVERSE)
        for values in (*annual_values.values(), *stress_annual_values.values())
    )
    cells = []
    for symbol_index, symbol in enumerate(UNIVERSE):
        for label in ("2022", "2023", "continuous"):
            if label == "continuous":
                value = continuous_values[symbol_index]
                stress_value = stress_continuous_values[symbol_index]
                first = date(2022, 1, 3)
                last = date(2023, 12, 29)
            else:
                value = annual_values[label][symbol_index]
                stress_value = stress_annual_values[label][symbol_index]
                year = int(label)
                first = date(year, 1, 3)
                last = date(year, 12, 29)
            row_key = (proposal.proposal_id, symbol, label)
            base = _metrics(
                value,
                drawdown=drawdown,
                turnover=turnover,
                identity=("base", row_key),
            )
            stress = _metrics(
                stress_value,
                drawdown=drawdown,
                turnover=turnover,
                identity=("stress", row_key),
            )
            buy_hold = _metrics(
                Decimal("0.01"),
                drawdown=Decimal("0.20"),
                turnover=Decimal(0),
                identity=("buy-hold", row_key),
            )
            buy_hold_stress = _metrics(
                Decimal("0.01"),
                drawdown=Decimal("0.25"),
                turnover=Decimal(0),
                identity=("buy-hold-stress", row_key),
            )
            cells.append(
                CellEvidence(
                    candidate_id=proposal.proposal_id,
                    symbol=symbol,
                    regime=label,
                    result_id=_uuid(("cell", row_key)),
                    base=base,
                    stress=stress,
                    buy_and_hold=buy_hold,
                    buy_and_hold_stress=buy_hold_stress,
                    atr=AtrDescription(
                        1,
                        Decimal(1),
                        Decimal(1),
                        Decimal(1),
                        Decimal("0.01"),
                    ),
                    session_count=20,
                    first_session=datetime.combine(first, time.min, NY).isoformat(),
                    last_session=datetime.combine(last, time.min, NY).isoformat(),
                )
            )
    return Generation2ProgramResult(
        proposal_id=proposal.proposal_id,
        semantic_program_id=proposal.semantic_program_id,
        dataset_identity=view.dataset_identity,
        confirmation_view_identity=view.identity,
        cells=tuple(cells),
    )


def _failure(
    proposal: ResearchProposal,
    view: ConfirmationView,
) -> Generation2EvaluationFailure:
    return Generation2EvaluationFailure(
        proposal_id=proposal.proposal_id,
        semantic_program_id=proposal.semantic_program_id,
        dataset_identity=view.dataset_identity,
        attempt_id=_uuid(("failure-attempt", proposal.proposal_id)),
        evaluation_id=_uuid(("failure-evaluation", proposal.proposal_id)),
        failure_code=Generation2FailureCode.DETERMINISTIC_EVALUATION_VALUE_ERROR,
    )


@pytest.fixture
def view() -> ConfirmationView:
    return ConfirmationView.from_dataset(_synthetic_dataset())


def test_analyzer_uses_complete_completed_population_and_preserves_ties(
    monkeypatch: pytest.MonkeyPatch,
    view: ConfirmationView,
) -> None:
    proposal_set, _ = _fixture(monkeypatch, view)
    proposals = proposal_set.proposals
    negative_half = (Decimal("-0.20"),) * 4 + (Decimal("0.01"),) * 4
    outcomes = (
        _result(proposals[0], view, drawdown=Decimal("0.10"), turnover=Decimal("0.40")),
        _result(proposals[1], view, drawdown=Decimal("0.10"), turnover=Decimal("0.40")),
        _result(
            proposals[2],
            view,
            returns_2022=negative_half,
            drawdown=Decimal("0.01"),
            turnover=Decimal("0.05"),
        ),
        _result(
            proposals[3],
            view,
            continuous=(Decimal("0.05"),) * len(UNIVERSE),
            drawdown=Decimal("0.20"),
            turnover=Decimal("0.50"),
        ),
        _result(
            proposals[4],
            view,
            continuous=(Decimal("0.15"),) * len(UNIVERSE),
            drawdown=Decimal("0.05"),
            turnover=Decimal("0.40"),
        ),
        _failure(proposals[5], view),
    )

    analysis = analyze_generation2_batch(
        proposal_set,
        outcomes,
        expected_dataset_identity=proposal_set.accepted_generation1_dataset_identity,
        confirmation_view_identity=view.identity,
    )

    assert tuple(item.disposition for item in analysis.programs) == (
        TrialDisposition.CONFIRMATION_PASSED,
        TrialDisposition.CONFIRMATION_PASSED,
        TrialDisposition.CONFIRMATION_REJECTED,
        TrialDisposition.CONFIRMATION_REJECTED,
        TrialDisposition.CONFIRMATION_PASSED,
        TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
    )
    assert analysis.pareto_front_proposal_ids == (
        proposals[0].proposal_id,
        proposals[1].proposal_id,
        proposals[2].proposal_id,
        proposals[4].proposal_id,
    )
    assert analysis.programs[0].nondominated is True
    assert analysis.programs[1].nondominated is True
    assert analysis.programs[2].stress is not None
    assert analysis.programs[2].stress.median_2022_return < 0
    assert analysis.programs[2].nondominated is True
    assert analysis.programs[3].nondominated is False
    assert analysis.programs[5].stress is None


@pytest.mark.parametrize(
    ("case", "continuous", "returns_2022", "returns_2023", "expected_annual_positive"),
    (
        (
            "zero_2022_median",
            (Decimal("0.20"),) * 8,
            (Decimal("-0.10"),) * 4 + (Decimal("0.10"),) * 4,
            (Decimal("0.10"),) * 8,
            12,
        ),
        (
            "zero_2023_median",
            (Decimal("0.20"),) * 8,
            (Decimal("0.10"),) * 8,
            (Decimal("-0.10"),) * 4 + (Decimal("0.10"),) * 4,
            12,
        ),
        (
            "zero_continuous_median",
            (Decimal("-0.10"),) * 4 + (Decimal("0.10"),) * 4,
            (Decimal("0.10"),) * 8,
            (Decimal("0.10"),) * 8,
            16,
        ),
        (
            "four_positive_continuous_symbols",
            (Decimal("-0.01"),) * 4 + (Decimal("0.10"),) * 4,
            (Decimal("0.10"),) * 8,
            (Decimal("0.10"),) * 8,
            16,
        ),
        (
            "eight_positive_year_cells",
            (Decimal("0.20"),) * 8,
            (Decimal("-0.01"),) * 4 + (Decimal("0.10"),) * 4,
            (Decimal("-0.01"),) * 4 + (Decimal("0.10"),) * 4,
            8,
        ),
        (
            "minimum_return_boundary",
            (Decimal("-0.10"),) + (Decimal("0.20"),) * 7,
            (Decimal("0.10"),) * 8,
            (Decimal("0.10"),) * 8,
            16,
        ),
    ),
)
def test_confirmation_gates_use_strict_frozen_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    view: ConfirmationView,
    case: str,
    continuous: tuple[Decimal, ...],
    returns_2022: tuple[Decimal, ...],
    returns_2023: tuple[Decimal, ...],
    expected_annual_positive: int,
) -> None:
    proposal_set, _ = _fixture(monkeypatch, view)
    proposal = proposal_set.proposals[0]
    outcomes = (
        _result(
            proposal,
            view,
            continuous=continuous,
            returns_2022=returns_2022,
            returns_2023=returns_2023,
        ),
    ) + tuple(_failure(item, view) for item in proposal_set.proposals[1:])

    analysis = analyze_generation2_batch(
        proposal_set,
        outcomes,
        expected_dataset_identity=proposal_set.accepted_generation1_dataset_identity,
        confirmation_view_identity=view.identity,
    )

    summary = analysis.programs[0].stress
    assert summary is not None
    assert summary.positive_asset_year_cells == expected_annual_positive
    assert analysis.programs[0].disposition is TrialDisposition.CONFIRMATION_REJECTED
    assert analysis.pareto_front_proposal_ids == (proposal.proposal_id,)


def test_analyzer_binds_dataset_to_accepted_g1_identity(
    monkeypatch: pytest.MonkeyPatch,
    view: ConfirmationView,
) -> None:
    proposal_set, _ = _fixture(monkeypatch, view)
    outcomes = tuple(_failure(proposal, view) for proposal in proposal_set.proposals)

    with pytest.raises(Generation2AnalysisError, match="accepted G1 dataset"):
        analyze_generation2_batch(
            proposal_set,
            outcomes,
            expected_dataset_identity=_uuid("another-dataset"),
            confirmation_view_identity=view.identity,
        )


def test_analyzer_requires_six_ordered_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    view: ConfirmationView,
) -> None:
    proposal_set, _ = _fixture(monkeypatch, view)
    outcomes = tuple(_failure(proposal, view) for proposal in proposal_set.proposals)
    kwargs = {
        "expected_dataset_identity": proposal_set.accepted_generation1_dataset_identity,
        "confirmation_view_identity": view.identity,
    }

    with pytest.raises(Generation2AnalysisError, match="one ordered outcome"):
        analyze_generation2_batch(proposal_set, outcomes[:-1], **kwargs)
    with pytest.raises(Generation2AnalysisError, match="missing, duplicated, foreign"):
        analyze_generation2_batch(proposal_set, tuple(reversed(outcomes)), **kwargs)


def test_confirmation_selection_uses_stress_metrics_not_base_metrics(
    monkeypatch: pytest.MonkeyPatch,
    view: ConfirmationView,
) -> None:
    proposal_set, _ = _fixture(monkeypatch, view)
    proposal = proposal_set.proposals[0]
    stress_zero = (Decimal("-0.10"),) * 4 + (Decimal("0.10"),) * 4
    outcomes = (_result(proposal, view, stress_returns_2022=stress_zero),) + tuple(
        _failure(item, view) for item in proposal_set.proposals[1:]
    )

    analysis = analyze_generation2_batch(
        proposal_set,
        outcomes,
        expected_dataset_identity=proposal_set.accepted_generation1_dataset_identity,
        confirmation_view_identity=view.identity,
    )

    summary = analysis.programs[0]
    assert summary.base is not None and summary.base.median_2022_return > 0
    assert summary.stress is not None and summary.stress.median_2022_return == 0
    assert summary.disposition is TrialDisposition.CONFIRMATION_REJECTED


def test_runner_freezes_all_acceptances_and_exposes_only_complete_results(
    monkeypatch: pytest.MonkeyPatch,
    view: ConfirmationView,
) -> None:
    proposal_set, prior = _fixture(monkeypatch, view)
    import trading_bot.experiments.ai_strategy_discovery_generation2_analysis as module

    def forbidden_effect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the in-memory G2 runner attempted an external effect")

    monkeypatch.setattr(socket, "create_connection", forbidden_effect)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden_effect)
    monkeypatch.setattr(subprocess, "run", forbidden_effect)
    monkeypatch.setattr(os, "system", forbidden_effect)

    original_append = TrialLedger.append
    original_analyze = module.analyze_generation2_batch
    accepted_ids: list[str] = []
    evaluated_ids: list[str] = []
    analysis_complete = False

    def append_spy(ledger: TrialLedger, record: TrialLedgerRecord) -> TrialLedger:
        nonlocal analysis_complete
        if record.generation == 2:
            if record.disposition is TrialDisposition.ACCEPTED_FOR_EVALUATION:
                assert evaluated_ids == []
                accepted_ids.append(record.proposal_id)
            else:
                assert evaluated_ids == list(proposal_set.proposal_ids)
                assert analysis_complete
        return original_append(ledger, record)

    monkeypatch.setattr(TrialLedger, "append", append_spy)

    def evaluator(proposal: ResearchProposal, bounded_view: ConfirmationView):
        assert bounded_view is view
        assert accepted_ids == list(proposal_set.proposal_ids)
        assert evaluated_ids == list(proposal_set.proposal_ids[: len(evaluated_ids)])
        evaluated_ids.append(proposal.proposal_id)
        if proposal is proposal_set.proposals[0]:
            raise ValueError("synthetic deterministic evaluation failure")
        return _result(proposal, view)

    monkeypatch.setattr(module, "evaluate_generation2_program", evaluator)

    def analyze_spy(*args: object, **kwargs: object):
        nonlocal analysis_complete
        assert evaluated_ids == list(proposal_set.proposal_ids)
        analysis = original_analyze(*args, **kwargs)
        analysis_complete = True
        return analysis

    monkeypatch.setattr(module, "analyze_generation2_batch", analyze_spy)

    run = run_generation2_batch(
        proposal_set,
        prior,
        view,
        expected_source_head=_HEAD,
        expected_source_tree=_TREE,
    )

    assert accepted_ids == list(proposal_set.proposal_ids)
    assert evaluated_ids == list(proposal_set.proposal_ids)
    assert run.pre_evaluation_ledger.records[: len(prior.records)] == prior.records
    assert run.terminal_ledger.records[: len(prior.records)] == prior.records
    assert run.pre_evaluation_ledger.evaluated_trial_counts_by_generation == (6, 0)
    assert run.terminal_ledger.evaluated_trial_counts_by_generation == (6, 6)
    assert len(run.outcomes) == 6
    assert type(run.outcomes[0]) is Generation2EvaluationFailure
    assert run.outcomes[0].failure_code is (
        Generation2FailureCode.DETERMINISTIC_EVALUATION_VALUE_ERROR
    )
    failed_record = run.terminal_ledger.records[-6]
    assert failed_record.evaluation_attempt_id == run.outcomes[0].attempt_id
    assert failed_record.evaluation_id == run.outcomes[0].evaluation_id
    assert failed_record.result_id is None
    assert failed_record.pnl_visible is False
    assert failed_record.diagnostic_visible is True
    assert all(
        record.pnl_visible is True and record.diagnostic_visible is True
        for record in run.terminal_ledger.records[-5:]
    )
    assert run.zero_effects == tuple((name, 0) for name in ZERO_EFFECT_COUNTER_NAMES)
    assert run.final_holdout_sealed is True
    assert proposal_set.final_holdout_sealed is True

    calls_before_replay = list(evaluated_ids)
    with pytest.raises(Generation2AnalysisError, match="replay is forbidden"):
        run_generation2_batch(
            proposal_set,
            run.terminal_ledger,
            view,
            expected_source_head=_HEAD,
            expected_source_tree=_TREE,
        )
    assert evaluated_ids == calls_before_replay


def test_run_generation2_batch_composes_all_six_on_synthetic_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = ConfirmationView.from_dataset(_synthetic_dataset())
    proposal_set, prior = _fixture(monkeypatch, view)
    import trading_bot.experiments.ai_strategy_discovery_generation2 as evaluator_module

    synthetic_parents = _synthetic_g1_parent_proposals()
    monkeypatch.setattr(
        evaluator_module,
        "_PARENT_ID_BY_SPEC",
        {parent.strategy_spec: parent.proposal_id for parent in synthetic_parents},
    )
    monkeypatch.setattr(
        evaluator_module,
        "_ALLOWED_PARENT_PAIRS",
        frozenset(
            frozenset(proposal.parent_proposal_ids)
            for proposal in proposal_set.proposals
        ),
    )

    run = run_generation2_batch(
        proposal_set,
        prior,
        view,
        expected_source_head=_HEAD,
        expected_source_tree=_TREE,
    )

    assert len(run.outcomes) == 6
    assert all(type(result) is Generation2ProgramResult for result in run.outcomes)
    assert all(
        result.dataset_identity == view.dataset_identity for result in run.outcomes
    )
    assert all(
        result.confirmation_view_identity == view.identity for result in run.outcomes
    )
    assert all(len(result.cells) == 24 for result in run.outcomes)
    assert run.terminal_ledger.evaluated_trial_counts_by_generation == (6, 6)
    assert run.terminal_ledger.records[: len(prior.records)] == prior.records
