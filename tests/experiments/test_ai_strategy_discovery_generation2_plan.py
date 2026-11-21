from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.experiments import ai_strategy_discovery_generation2_plan as g2_plan
from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    GENERATION_2_MAX_EVALUATED,
    AbsoluteMomentumSpec,
    ConjunctiveOperation,
    ConjunctiveTrendSpec,
    DiscoveryError,
    Generation1DiagnosticReference,
    InformationVisibility,
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
    frozen_generation2_parent_pairs,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_analysis import (
    Generation1BatchAnalysis,
    ProgramAnalysis,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_plan import (
    Generation1ProposalSet,
    frozen_generation1_specs,
)

_HEAD = "a" * 40
_TREE = "b" * 40
_G1_HEAD = "c" * 40
_G1_TREE = "d" * 40
_GENERATION0_ID = "08395fd5-43a4-5a81-9992-877560757a9f"
_FOUNDATION_ID = "00a845be-228a-56c6-9fd1-9b76c2176cf8"


def _uuid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _g1_proposal(spec) -> ResearchProposal:
    evidence = VisibleEvidenceReference(
        reference_label="PRIOR_A147",
        dataset_label="A147_DAILY",
        timeframe=VisibleTimeframe.DAILY,
        time_partition=VisibleTimePartition.PRIOR_RESEARCH_2022_2023,
        classification=VisibleEvidenceClassification.PRIOR_CANONICAL,
    )
    kind = (
        ProposalKind.RETAINED_BASELINE
        if spec.family
        in (StrategyFamily.MOVING_AVERAGE_TREND, StrategyFamily.DONCHIAN_BREAKOUT)
        else ProposalKind.ORIGINAL
    )
    return ResearchProposal(
        campaign_version=CAMPAIGN_VERSION,
        generation=1,
        proposal_kind=kind,
        parent_proposal_ids=(),
        strategy_spec=spec,
        hypothesis="Frozen fixture hypothesis.",
        expected_mechanism="A typed daily rule may persist across symbols.",
        falsification_condition="Stress breadth gates fail.",
        source_reference_labels=("PRIOR_A147",),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_1_PRE_RESULTS,
            visible_evidence=(evidence,),
        ),
        producer_label="g2-plan-test-fixture",
    )


def _g2_proposal(
    spec: ConjunctiveTrendSpec,
    *,
    parent_ids: tuple[str, str] | None = None,
) -> ResearchProposal:
    ids = tuple(sorted(parent_ids or (_uuid("parent-a"), _uuid("parent-b"))))
    diagnostics = tuple(
        Generation1DiagnosticReference(
            parent_proposal_id=parent_id,
            parent_trial_ordinal=ordinal,
            diagnostic_id=_uuid(f"diagnostic-{parent_id}"),
        )
        for ordinal, parent_id in enumerate(ids, start=1)
    )
    evidence = tuple(
        VisibleEvidenceReference(
            reference_label=f"g1-diagnostic-{parent_id}",
            dataset_label="A147_DAILY_ACCEPTED",
            timeframe=VisibleTimeframe.DAILY,
            time_partition=VisibleTimePartition.DISCOVERY_2019_2021,
            classification=VisibleEvidenceClassification.GENERATION_1_DISCOVERY_RESULT,
        )
        for parent_id in ids
    )
    return ResearchProposal(
        campaign_version=CAMPAIGN_VERSION,
        generation=2,
        proposal_kind=ProposalKind.RECOMBINATION,
        parent_proposal_ids=ids,
        strategy_spec=spec,
        hypothesis="A momentum gate may reduce trend drawdown.",
        expected_mechanism="Both parents must be LONG at the completed close.",
        falsification_condition="A frozen confirmation gate fails.",
        source_reference_labels=tuple(item.reference_label for item in evidence),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
            visible_evidence=evidence,
            visible_generation1_diagnostics=diagnostics,
        ),
        producer_label="g2-plan-test-fixture",
    )


@pytest.fixture
def accepted_inputs(monkeypatch):
    proposals = tuple(_g1_proposal(spec) for spec in frozen_generation1_specs())
    proposal_set = Generation1ProposalSet(
        campaign_version=CAMPAIGN_VERSION,
        generation0_inventory_id=_GENERATION0_ID,
        foundation_id=_FOUNDATION_ID,
        source_head=_G1_HEAD,
        source_tree=_G1_TREE,
        proposals=proposals,
    )
    programs = tuple(
        ProgramAnalysis(
            proposal_id=proposal.proposal_id,
            semantic_program_id=proposal.semantic_program_id,
            outcome_identity=_uuid(f"analysis-outcome-{index}"),
            disposition=TrialDisposition.SHORTLISTED,
            base=None,
            stress=None,
            nondominated=False,
        )
        for index, proposal in enumerate(proposals)
    )
    analysis = Generation1BatchAnalysis(
        proposal_set_identity=proposal_set.identity,
        dataset_identity=_uuid("accepted-g1-dataset"),
        programs=programs,
        pareto_front_proposal_ids=(),
    )
    dataset_evidence_id = _uuid("accepted-g1-dataset-evidence")
    acceptance_records = tuple(
        TrialLedgerRecord(
            event_ordinal=index,
            trial_ordinal=index,
            proposal=proposal,
            disposition=TrialDisposition.ACCEPTED_FOR_EVALUATION,
        )
        for index, proposal in enumerate(proposals, start=1)
    )
    terminal_records = tuple(
        TrialLedgerRecord(
            event_ordinal=len(proposals) + index,
            trial_ordinal=index,
            proposal=proposal,
            disposition=TrialDisposition.SHORTLISTED,
            evaluation_attempt_id=_uuid(f"attempt-{index}"),
            evaluation_source_head=_G1_HEAD,
            evaluation_source_tree=_G1_TREE,
            dataset_evidence_id=dataset_evidence_id,
            evaluation_id=_uuid(f"evaluation-{index}"),
            result_id=_uuid(f"result-{index}"),
            terminal_diagnostic_code="G1_TEST_RESULT",
            pnl_visible=True,
            diagnostic_visible=True,
        )
        for index, proposal in enumerate(proposals, start=1)
    )
    ledger = TrialLedger(acceptance_records + terminal_records)

    proposal_id_by_spec = {
        proposal.strategy_spec: proposal.proposal_id for proposal in proposals
    }
    parent_pairs = tuple(
        tuple(proposal_id_by_spec[spec] for _, spec in pair)
        for pair in frozen_generation2_parent_pairs()
    )
    parent_specifications = {
        proposal_id_by_spec[spec]: spec
        for pair in frozen_generation2_parent_pairs()
        for _, spec in pair
    }
    monkeypatch.setattr(
        g2_plan, "ACCEPTED_GENERATION1_PROPOSAL_SET_ID", proposal_set.identity
    )
    monkeypatch.setattr(g2_plan, "ACCEPTED_GENERATION1_ANALYSIS_ID", analysis.identity)
    monkeypatch.setattr(
        g2_plan, "ACCEPTED_GENERATION1_TERMINAL_LEDGER_ID", ledger.ledger_id
    )
    monkeypatch.setattr(g2_plan, "_PARENT_SPECIFICATIONS", parent_specifications)
    monkeypatch.setattr(g2_plan, "_FROZEN_PARENT_PAIRS", parent_pairs)
    return proposal_set, analysis, ledger


def test_shared_grammar_exposes_exact_six_ordered_parent_spec_pairs() -> None:
    pairs = frozen_generation2_parent_pairs()
    assert len(pairs) == 6
    assert tuple(tuple(parent_id for parent_id, _ in pair) for pair in pairs) == (
        (
            "6ff56e8f-ab41-50f3-aa3b-2474bfb37537",
            "926f7b9f-d40f-5c4b-8e56-de498786e440",
        ),
        (
            "6ff56e8f-ab41-50f3-aa3b-2474bfb37537",
            "f6739ed9-f812-5f62-938c-6b0ea7407825",
        ),
        (
            "6ff56e8f-ab41-50f3-aa3b-2474bfb37537",
            "369a6806-1609-53b4-8972-b4d248505e2d",
        ),
        (
            "c5d6574d-a9dc-5b4f-8a68-b95b1cdd3e59",
            "926f7b9f-d40f-5c4b-8e56-de498786e440",
        ),
        (
            "b4c598f0-688d-5c81-b924-219fabd90e2a",
            "926f7b9f-d40f-5c4b-8e56-de498786e440",
        ),
        (
            "b4c598f0-688d-5c81-b924-219fabd90e2a",
            "369a6806-1609-53b4-8972-b4d248505e2d",
        ),
    )
    specs = tuple(
        ConjunctiveTrendSpec(components=(left[1], right[1])) for left, right in pairs
    )
    assert len(set(specs)) == 6
    assert all(spec.operation is ConjunctiveOperation.ALL_OF for spec in specs)


def test_conjunctive_identity_is_order_independent() -> None:
    left, right = frozen_generation2_parent_pairs()[0]
    forward = ConjunctiveTrendSpec(components=(left[1], right[1]))
    reversed_order = ConjunctiveTrendSpec(components=(right[1], left[1]))
    assert forward == reversed_order
    assert forward.to_dict() == reversed_order.to_dict()
    assert (
        _g2_proposal(forward).semantic_program_id
        == _g2_proposal(reversed_order).semantic_program_id
    )


def test_conjunctive_grammar_rejects_duplicates_unsupported_pairs_and_expressions() -> (
    None
):
    band = MovingAverageTrendSpec(35, 50, MovingAverageRule.MA_PERCENT_BAND_010)
    with pytest.raises(DiscoveryError, match="cannot duplicate itself"):
        ConjunctiveTrendSpec(components=(band, band))
    with pytest.raises(DiscoveryError, match="frozen G2 programs"):
        ConjunctiveTrendSpec(
            components=(
                MovingAverageTrendSpec(55, 100, MovingAverageRule.BASE_MA),
                AbsoluteMomentumSpec(63, MomentumGate.NONE),
            )
        )
    with pytest.raises(DiscoveryError, match="exactly two"):
        ConjunctiveTrendSpec(components=(band,))
    with pytest.raises(DiscoveryError, match="exactly two"):
        ConjunctiveTrendSpec(
            components=(band, AbsoluteMomentumSpec(63, MomentumGate.NONE), band)
        )
    with pytest.raises(DiscoveryError, match="ALL_OF"):
        ConjunctiveTrendSpec(
            components=(band, AbsoluteMomentumSpec(63, MomentumGate.NONE)),
            operation="OR",
        )
    with pytest.raises(DiscoveryError, match="typed G1 programs"):
        ConjunctiveTrendSpec(components=({"python": "arbitrary"}, band))


def test_conjunctive_spec_round_trips_and_rejects_nested_expressions() -> None:
    pair = frozen_generation2_parent_pairs()[0]
    proposal = _g2_proposal(ConjunctiveTrendSpec(components=(pair[0][1], pair[1][1])))
    assert ResearchProposal.from_bytes(proposal.to_bytes()) == proposal
    raw = proposal.to_dict()
    raw["strategy_spec"]["components"][0] = proposal.strategy_spec.to_dict()
    with pytest.raises(DiscoveryError):
        ResearchProposal.from_dict(raw)


def test_conjunctive_lineage_requires_two_distinct_canonical_parents() -> None:
    pair = frozen_generation2_parent_pairs()[0]
    spec = ConjunctiveTrendSpec(components=(pair[0][1], pair[1][1]))
    parent = _uuid("self-parent")
    evidence = VisibleEvidenceReference(
        reference_label="g1-diagnostic-self-parent",
        dataset_label="A147_DAILY_ACCEPTED",
        timeframe=VisibleTimeframe.DAILY,
        time_partition=VisibleTimePartition.DISCOVERY_2019_2021,
        classification=VisibleEvidenceClassification.GENERATION_1_DISCOVERY_RESULT,
    )
    visibility = InformationVisibility(
        VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
        visible_evidence=(evidence,),
        visible_generation1_diagnostics=(
            Generation1DiagnosticReference(parent, 1, _uuid("self-parent-diagnostic")),
        ),
    )
    with pytest.raises(DiscoveryError, match="duplicate parent proposal id"):
        ResearchProposal(
            campaign_version=CAMPAIGN_VERSION,
            generation=2,
            proposal_kind=ProposalKind.RECOMBINATION,
            parent_proposal_ids=(parent, parent),
            strategy_spec=spec,
            hypothesis="A momentum gate may reduce trend drawdown.",
            expected_mechanism="Both parents must be LONG at close.",
            falsification_condition="A frozen confirmation gate fails.",
            source_reference_labels=(evidence.reference_label,),
            information_visibility=visibility,
            producer_label="g2-plan-test-fixture",
        )


def test_g2_plan_binds_the_complete_six_and_exact_visible_g1_diagnostics(
    accepted_inputs,
) -> None:
    proposal_set, analysis, ledger = accepted_inputs
    plan = g2_plan.Generation2ProposalSet(proposal_set, analysis, ledger, _HEAD, _TREE)
    assert plan.accepted_generation1_proposal_set_id == proposal_set.identity
    assert plan.accepted_generation1_terminal_ledger_id == ledger.ledger_id
    assert plan.accepted_generation1_analysis_id == analysis.identity
    assert plan.accepted_generation1_dataset_identity == analysis.dataset_identity
    assert (
        plan.accepted_generation1_dataset_evidence_id
        == ledger.records[-1].dataset_evidence_id
    )
    assert len(plan.proposals) == plan.evaluated_candidate_count == 6
    assert len(set(plan.semantic_program_ids)) == 6
    assert plan.max_evaluated == GENERATION_2_MAX_EVALUATED == 16
    assert plan.confirmation_results_visible is False
    assert plan.final_holdout_sealed is True
    assert plan.parent_proposal_pairs == tuple(
        tuple(sorted(pair)) for pair in g2_plan._FROZEN_PARENT_PAIRS
    )
    for proposal, references in zip(
        plan.proposals, plan.parent_diagnostic_references, strict=True
    ):
        assert proposal.proposal_kind is ProposalKind.RECOMBINATION
        assert len(proposal.parent_proposal_ids) == len(references) == 2
        assert (
            tuple(ref.parent_proposal_id for ref in references)
            == proposal.parent_proposal_ids
        )
        for reference in references:
            parent = next(
                record
                for record in ledger.records
                if record.proposal_id == reference.parent_proposal_id
                and record.evaluation_attempt_id is not None
            )
            assert reference.parent_trial_ordinal == parent.trial_ordinal
            assert reference.diagnostic_id == parent.diagnostic_id
            assert parent.diagnostic_visible is True
    serialized = plan.to_bytes()
    restored = g2_plan.Generation2ProposalSet.from_bytes(
        serialized,
        generation1_proposal_set=proposal_set,
        generation1_analysis=analysis,
        terminal_ledger=ledger,
    )
    assert restored == plan
    changed = plan.to_dict()
    changed["budget"]["max_evaluated"] = 15
    with pytest.raises(g2_plan.Generation2PlanError, match="derived fields"):
        g2_plan.Generation2ProposalSet.from_dict(
            changed,
            generation1_proposal_set=proposal_set,
            generation1_analysis=analysis,
            terminal_ledger=ledger,
        )


def test_g2_plan_rejects_nonaccepted_or_misbound_typed_inputs(accepted_inputs) -> None:
    proposal_set, analysis, ledger = accepted_inputs
    with pytest.raises(g2_plan.Generation2PlanError, match="typed accepted G1"):
        g2_plan.Generation2ProposalSet(object(), analysis, ledger, _HEAD, _TREE)
    with pytest.raises(g2_plan.Generation2PlanError, match="source HEAD"):
        g2_plan.Generation2ProposalSet(
            proposal_set, analysis, ledger, "not-a-git-id", _TREE
        )


@pytest.mark.parametrize(
    "disposition",
    (TrialDisposition.CONFIRMATION_PASSED, TrialDisposition.CONFIRMATION_REJECTED),
)
def test_g2_confirmation_dispositions_require_result_and_visible_diagnostics(
    accepted_inputs, disposition
) -> None:
    proposal_set, analysis, ledger = accepted_inputs
    plan = g2_plan.Generation2ProposalSet(proposal_set, analysis, ledger, _HEAD, _TREE)
    proposal = plan.proposals[0]
    good = TrialLedgerRecord(
        event_ordinal=1,
        trial_ordinal=1,
        proposal=proposal,
        disposition=disposition,
        evaluation_attempt_id=_uuid("g2-attempt"),
        evaluation_source_head=_HEAD,
        evaluation_source_tree=_TREE,
        dataset_evidence_id=plan.accepted_generation1_dataset_evidence_id,
        evaluation_id=_uuid("g2-evaluation"),
        result_id=_uuid("g2-result"),
        terminal_diagnostic_code="G2_CONFIRMATION_RESULT",
        pnl_visible=True,
        diagnostic_visible=True,
    )
    assert good.disposition is disposition
    with pytest.raises(DiscoveryError, match="visible bound result"):
        TrialLedgerRecord(
            event_ordinal=1,
            trial_ordinal=1,
            proposal=proposal,
            disposition=disposition,
            evaluation_attempt_id=_uuid("g2-attempt-no-result"),
            evaluation_source_head=_HEAD,
            evaluation_source_tree=_TREE,
            dataset_evidence_id=plan.accepted_generation1_dataset_evidence_id,
            evaluation_id=_uuid("g2-evaluation-no-result"),
            terminal_diagnostic_code="G2_CONFIRMATION_RESULT",
            pnl_visible=False,
            diagnostic_visible=True,
        )


def test_g1_cannot_use_g2_confirmation_disposition(accepted_inputs) -> None:
    proposal_set, _, _ = accepted_inputs
    with pytest.raises(DiscoveryError, match="visible bound result"):
        TrialLedgerRecord(
            event_ordinal=1,
            trial_ordinal=1,
            proposal=proposal_set.proposals[0],
            disposition=TrialDisposition.CONFIRMATION_PASSED,
            evaluation_attempt_id=_uuid("invalid-g1-confirmation-attempt"),
            evaluation_source_head=_HEAD,
            evaluation_source_tree=_TREE,
            dataset_evidence_id=_uuid("invalid-g1-evidence"),
            evaluation_id=_uuid("invalid-g1-evaluation"),
            result_id=_uuid("invalid-g1-result"),
            terminal_diagnostic_code="G1_BAD_CONFIRMATION_RESULT",
            pnl_visible=True,
            diagnostic_visible=True,
        )
