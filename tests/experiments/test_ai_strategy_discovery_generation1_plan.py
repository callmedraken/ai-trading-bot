from __future__ import annotations

from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    AbsoluteMomentumSpec,
    DeferredStrategySpec,
    DiscoveryError,
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
from trading_bot.experiments.ai_strategy_discovery_generation1_plan import (
    SCHEMA,
    Generation1PlanError,
    Generation1ProposalSet,
    frozen_generation1_specs,
)
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig

_GENERATION0_ID = "08395fd5-43a4-5a81-9992-877560757a9f"
_FOUNDATION_ID = "00a845be-228a-56c6-9fd1-9b76c2176cf8"
_HEAD = "a" * 40
_TREE = "b" * 40


def _identity(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _proposal(spec, *, hypothesis: str = "Frozen test hypothesis.") -> ResearchProposal:
    kind = (
        ProposalKind.RETAINED_BASELINE
        if spec.family
        in (StrategyFamily.MOVING_AVERAGE_TREND, StrategyFamily.DONCHIAN_BREAKOUT)
        else ProposalKind.ORIGINAL
    )
    evidence = VisibleEvidenceReference(
        reference_label="PRIOR_A147",
        dataset_label="A147_DAILY",
        timeframe=VisibleTimeframe.DAILY,
        time_partition=VisibleTimePartition.PRIOR_RESEARCH_2022_2023,
        classification=VisibleEvidenceClassification.PRIOR_CANONICAL,
    )
    visibility = InformationVisibility(
        VisibilityStage.GENERATION_1_PRE_RESULTS,
        visible_evidence=(evidence,),
    )
    return ResearchProposal(
        campaign_version=CAMPAIGN_VERSION,
        generation=1,
        proposal_kind=kind,
        parent_proposal_ids=(),
        strategy_spec=spec,
        hypothesis=hypothesis,
        expected_mechanism="A closed daily rule may persist across symbols.",
        falsification_condition="Stress breadth gates fail.",
        source_reference_labels=("PRIOR_A147",),
        information_visibility=visibility,
        producer_label="offline-fixture",
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


def test_frozen_program_vocabulary_is_exactly_the_reviewed_22_semantics() -> None:
    specs = frozen_generation1_specs()
    compiled = tuple(compile_generation1_program(spec) for spec in specs)
    assert len(specs) == 22
    assert (
        sum(spec.family is StrategyFamily.MOVING_AVERAGE_TREND for spec in specs) == 6
    )
    assert sum(spec.family is StrategyFamily.DONCHIAN_BREAKOUT for spec in specs) == 6
    assert sum(spec.family is StrategyFamily.ABSOLUTE_MOMENTUM for spec in specs) == 6
    assert sum(spec.family is StrategyFamily.MULTI_HORIZON_TREND for spec in specs) == 4
    assert tuple(spec.family for spec in specs[:12]) == (
        (StrategyFamily.MOVING_AVERAGE_TREND,) * 6
        + (StrategyFamily.DONCHIAN_BREAKOUT,) * 6
    )
    assert sum(type(program) is StrategyConfig for program in compiled) == 12
    assert (
        sum(
            type(program) in (AbsoluteMomentumSpec, MultiHorizonTrendSpec)
            for program in compiled
        )
        == 10
    )
    assert tuple(
        (spec.fast_window, spec.slow_window, spec.rule)
        for spec in specs[:6]
        if spec.rule is MovingAverageRule.BASE_MA
    ) == tuple(
        (fast, slow, MovingAverageRule.BASE_MA)
        for fast, slow in ((35, 50), (55, 100), (50, 200))
    )
    assert tuple(
        (spec.fast_window, spec.slow_window, spec.rule)
        for spec in specs[:6]
        if spec.rule is MovingAverageRule.MA_PERCENT_BAND_010
    ) == tuple(
        (fast, slow, MovingAverageRule.MA_PERCENT_BAND_010)
        for fast, slow in ((35, 50), (55, 100), (50, 200))
    )
    assert tuple(
        (spec.lookback_sessions, spec.gate)
        for spec in specs
        if type(spec) is AbsoluteMomentumSpec
    ) == tuple(
        (lookback, gate)
        for lookback in (63, 126, 252)
        for gate in (MomentumGate.NONE, MomentumGate.ABOVE_SMA200)
    )
    assert tuple(
        (spec.horizons, spec.vote)
        for spec in specs
        if type(spec) is MultiHorizonTrendSpec
    ) == tuple(
        (horizons, vote)
        for horizons in ((21, 63, 126), (63, 126, 252))
        for vote in (TrendVote.TWO_OF_THREE, TrendVote.THREE_OF_THREE)
    )


def test_proposal_set_roundtrips_and_binds_ordered_ids_and_authority() -> None:
    first = _proposal(MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA))
    second = _proposal(AbsoluteMomentumSpec(63, MomentumGate.NONE))
    plan = _plan((first, second))
    decoded = Generation1ProposalSet.from_bytes(plan.to_bytes())

    assert decoded == plan
    assert decoded.identity == plan.identity
    assert decoded.schema == SCHEMA
    assert decoded.proposal_identities == (first.proposal_id, second.proposal_id)
    assert decoded.semantic_program_ids == (
        first.semantic_program_id,
        second.semantic_program_id,
    )
    assert decoded.supported_evaluated_count == 2
    assert decoded.family_counts == (
        (StrategyFamily.MOVING_AVERAGE_TREND, 1),
        (StrategyFamily.DONCHIAN_BREAKOUT, 0),
        (StrategyFamily.ABSOLUTE_MOMENTUM, 1),
        (StrategyFamily.MULTI_HORIZON_TREND, 0),
    )
    assert (decoded.max_evaluated, decoded.max_per_family) == (32, 8)
    assert not decoded.generation1_results_visible
    assert not decoded.confirmation_evidence_visible
    assert decoded.final_holdout_sealed
    assert not decoded.is_complete_population

    reversed_plan = _plan((second, first))
    assert reversed_plan.identity != plan.identity
    assert reversed_plan.proposal_identities == tuple(
        reversed(plan.proposal_identities)
    )
    complete_plan = _plan(tuple(_proposal(spec) for spec in frozen_generation1_specs()))
    assert complete_plan.is_complete_population
    assert complete_plan.family_counts == (
        (StrategyFamily.MOVING_AVERAGE_TREND, 6),
        (StrategyFamily.DONCHIAN_BREAKOUT, 6),
        (StrategyFamily.ABSOLUTE_MOMENTUM, 6),
        (StrategyFamily.MULTI_HORIZON_TREND, 4),
    )


def test_proposal_set_rejects_semantic_duplicates_even_when_prose_differs() -> None:
    spec = AbsoluteMomentumSpec(126, MomentumGate.ABOVE_SMA200)
    first = _proposal(spec, hypothesis="First explanation.")
    second = _proposal(spec, hypothesis="Different explanation.")
    assert first.proposal_id != second.proposal_id
    assert first.semantic_program_id == second.semantic_program_id
    with pytest.raises(Generation1PlanError, match="duplicate semantic"):
        _plan((first, second))


def test_proposal_set_rejects_unsupported_or_wrong_lineage_and_kind() -> None:
    with pytest.raises(Generation1PlanError, match="supported programs only"):
        _plan((_proposal(DeferredStrategySpec(StrategyFamily.FIXED_ENSEMBLE)),))

    baseline = _proposal(MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA))
    with pytest.raises(Generation1PlanError, match="frozen kind"):
        _plan((replace(baseline, proposal_kind=ProposalKind.ORIGINAL),))

    parent_id = _identity("g1-parent")
    diagnostic = Generation1DiagnosticReference(
        parent_id, 1, _identity("g1-diagnostic")
    )
    evidence = VisibleEvidenceReference(
        reference_label="PRIOR_A147",
        dataset_label="A147_DAILY",
        timeframe=VisibleTimeframe.DAILY,
        time_partition=VisibleTimePartition.PRIOR_RESEARCH_2022_2023,
        classification=VisibleEvidenceClassification.PRIOR_CANONICAL,
    )
    g2 = ResearchProposal(
        campaign_version=CAMPAIGN_VERSION,
        generation=2,
        proposal_kind=ProposalKind.MUTATION,
        parent_proposal_ids=(parent_id,),
        strategy_spec=AbsoluteMomentumSpec(63, MomentumGate.NONE),
        hypothesis="G2 fixture.",
        expected_mechanism="Fixture only.",
        falsification_condition="Fixture only.",
        source_reference_labels=("PRIOR_A147",),
        information_visibility=InformationVisibility(
            VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
            visible_evidence=(evidence,),
            visible_generation1_diagnostics=(diagnostic,),
        ),
        producer_label="offline-fixture",
    )
    with pytest.raises(Generation1PlanError, match="G2 lineage"):
        _plan((g2,))


def test_prior_confirmation_history_is_distinguished_from_new_confirmation() -> None:
    prior = _proposal(AbsoluteMomentumSpec(63, MomentumGate.NONE))
    prior_evidence = (
        _plan((prior,)).proposals[0].information_visibility.visible_evidence[0]
    )
    assert (
        prior_evidence.time_partition is VisibleTimePartition.PRIOR_RESEARCH_2022_2023
    )

    with pytest.raises(DiscoveryError, match="confirmation results"):
        VisibleEvidenceReference(
            reference_label="NEW_CONFIRMATION",
            dataset_label="OPEN_DAILY",
            timeframe=VisibleTimeframe.DAILY,
            time_partition=VisibleTimePartition.CAMPAIGN_CONFIRMATION_2022_2023,
            classification=VisibleEvidenceClassification.PRIOR_CANONICAL,
        )
    with pytest.raises(DiscoveryError, match="confirmation results"):
        VisibleEvidenceReference(
            reference_label="SEALED_FINAL",
            dataset_label="FINAL_HOLDOUT",
            timeframe=VisibleTimeframe.DAILY,
            time_partition=VisibleTimePartition.FINAL_HOLDOUT,
            classification=VisibleEvidenceClassification.FINAL_HOLDOUT,
        )


def test_proposal_set_parser_recomputes_every_identity_and_checks_exact_types() -> None:
    plan = _plan(
        (
            _proposal(MultiHorizonTrendSpec((21, 63, 126), TrendVote.TWO_OF_THREE)),
            _proposal(MultiHorizonTrendSpec((63, 126, 252), TrendVote.THREE_OF_THREE)),
        )
    )

    for mutate in (
        lambda raw: raw.__setitem__("identity", _identity("wrong-set")),
        lambda raw: raw.__setitem__("supported_evaluated_count", True),
        lambda raw: raw["family_counts"].__setitem__(
            StrategyFamily.MULTI_HORIZON_TREND.value, True
        ),
        lambda raw: raw["budgets"].__setitem__("max_evaluated", True),
        lambda raw: raw["information_visibility"].__setitem__(
            "final_holdout_sealed", False
        ),
        lambda raw: raw["ordered_semantic_program_ids"].reverse(),
    ):
        raw = plan.to_dict()
        mutate(raw)
        with pytest.raises(Generation1PlanError):
            Generation1ProposalSet.from_dict(raw)

    duplicate_key = plan.to_bytes().replace(
        b'"schema":', b'"schema":"duplicate","schema":', 1
    )
    with pytest.raises(Generation1PlanError, match="duplicate JSON"):
        Generation1ProposalSet.from_bytes(duplicate_key)


def test_proposal_set_binds_closed_budget_and_rejects_unknown_fields() -> None:
    plan = _plan((_proposal(AbsoluteMomentumSpec(252, MomentumGate.NONE)),))
    assert plan.to_dict()["budgets"] == {"max_evaluated": 32, "max_per_family": 8}
    raw = plan.to_dict()
    raw["arbitrary_program"] = "lambda bars: bars"
    with pytest.raises(Generation1PlanError):
        Generation1ProposalSet.from_dict(raw)
