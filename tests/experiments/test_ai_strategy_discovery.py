from __future__ import annotations

import ast
from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    COUNT_PROVENANCE,
    GENERATION_1_MAX_EVALUATED,
    GENERATION_1_MAX_PER_FAMILY,
    GENERATION_2_MAX_EVALUATED,
    DeferredStrategySpec,
    DiscoveryError,
    DonchianBreakoutSpec,
    Generation1DiagnosticReference,
    InformationVisibility,
    InvalidProposalReference,
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
    compile_strategy_config,
)

_HEAD = "a" * 40
_TREE = "b" * 40


def _identity(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _visible_evidence() -> tuple[VisibleEvidenceReference, ...]:
    return (
        VisibleEvidenceReference(
            reference_label="A147_FILTERED_TREND",
            dataset_label="A147_DAILY_MULTI_ASSET",
            timeframe=VisibleTimeframe.DAILY,
            time_partition=VisibleTimePartition.PRIOR_RESEARCH_2022_2023,
            classification=VisibleEvidenceClassification.PRIOR_CANONICAL,
        ),
    )


def _visibility(
    stage: VisibilityStage,
    *,
    diagnostics: tuple[Generation1DiagnosticReference, ...] = (),
) -> InformationVisibility:
    return InformationVisibility(
        stage,
        visible_evidence=_visible_evidence(),
        visible_generation1_diagnostics=diagnostics,
    )


def _g1_proposal(
    *,
    spec: MovingAverageTrendSpec
    | DonchianBreakoutSpec
    | DeferredStrategySpec
    | None = None,
    hypothesis: str = "The frozen trend filter may persist across assets.",
    producer: str = "offline-fixture",
    kind: ProposalKind = ProposalKind.ORIGINAL,
) -> ResearchProposal:
    return ResearchProposal(
        campaign_version="v1",
        generation=1,
        proposal_kind=kind,
        parent_proposal_ids=(),
        strategy_spec=spec or MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA),
        hypothesis=hypothesis,
        expected_mechanism="Participation in persistent directional regimes.",
        falsification_condition="Stress returns fail across assets and years.",
        source_reference_labels=("A147_FILTERED_TREND",),
        information_visibility=_visibility(VisibilityStage.GENERATION_1_PRE_RESULTS),
        producer_label=producer,
    )


def _attempt_fields(label: str) -> dict[str, str]:
    return {
        "evaluation_attempt_id": _identity(f"attempt:{label}"),
        "evaluation_source_head": _HEAD,
        "evaluation_source_tree": _TREE,
        "dataset_evidence_id": _identity("accepted-open-dataset"),
        "evaluation_id": _identity(f"evaluation:{label}"),
    }


def _result_record(
    proposal: ResearchProposal,
    *,
    event: int,
    trial: int,
    disposition: TrialDisposition,
    label: str,
    code: str,
    pnl_visible: bool = False,
    diagnostic_visible: bool = False,
) -> TrialLedgerRecord:
    return TrialLedgerRecord(
        event_ordinal=event,
        trial_ordinal=trial,
        proposal=proposal,
        disposition=disposition,
        **_attempt_fields(label),
        result_id=_identity(f"result:{label}")
        if disposition is not TrialDisposition.DETERMINISTIC_EVALUATION_FAILED
        else None,
        terminal_diagnostic_code=code,
        pnl_visible=pnl_visible,
        diagnostic_visible=diagnostic_visible,
    )


def test_proposal_canonical_identity_and_producer_provenance() -> None:
    proposal = _g1_proposal()
    same_semantics = _g1_proposal(producer="another-producer")
    different_hypothesis = _g1_proposal(
        hypothesis="A different falsifiable hypothesis."
    )

    assert proposal.proposal_id == _g1_proposal().proposal_id
    assert proposal.proposal_id == same_semantics.proposal_id
    assert proposal.semantic_program_id == same_semantics.semantic_program_id
    assert proposal.proposal_id != different_hypothesis.proposal_id
    assert proposal.semantic_program_id == different_hypothesis.semantic_program_id
    assert proposal.to_bytes() == _g1_proposal().to_bytes()
    assert ResearchProposal.from_bytes(proposal.to_bytes()) == proposal
    assert proposal.to_dict()["producer_label"] == "offline-fixture"
    assert proposal.semantic_status.value == "SUPPORTED"
    assert (
        CAMPAIGN_VERSION,
        GENERATION_1_MAX_EVALUATED,
        GENERATION_2_MAX_EVALUATED,
        GENERATION_1_MAX_PER_FAMILY,
    ) == ("v1", 32, 16, 8)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (
            MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA),
            ("BASE_MA", 35, 50, "none"),
        ),
        (
            MovingAverageTrendSpec(55, 100, MovingAverageRule.MA_PERCENT_BAND_010),
            ("MA_PERCENT_BAND", 55, 100, "0.010"),
        ),
        (
            DonchianBreakoutSpec(50, 200, 55),
            ("MA_DONCHIAN", 50, 200, "55"),
        ),
    ],
)
def test_supported_specs_map_to_exact_a147_configs(spec, expected) -> None:
    config = compile_strategy_config(spec)
    assert (config.family, config.fast, config.slow, config.parameter) == expected


def test_finite_strategy_grammar_rejects_values_code_and_unknown_fields() -> None:
    with pytest.raises(DiscoveryError):
        MovingAverageTrendSpec(True, 50, MovingAverageRule.BASE_MA)
    with pytest.raises(DiscoveryError):
        MovingAverageTrendSpec(34, 50, MovingAverageRule.BASE_MA)
    with pytest.raises(DiscoveryError):
        DonchianBreakoutSpec(35, 50, 21)
    with pytest.raises(DiscoveryError):
        DeferredStrategySpec(StrategyFamily.MOVING_AVERAGE_TREND)
    with pytest.raises(DiscoveryError):
        compile_strategy_config(DeferredStrategySpec(StrategyFamily.ABSOLUTE_MOMENTUM))

    raw = _g1_proposal().to_dict()
    raw["strategy_spec"]["expression"] = "__import__('os').system('whoami')"
    with pytest.raises(DiscoveryError):
        ResearchProposal.from_dict(raw)


def test_deferred_family_vocabulary_is_explicit_but_not_compilable() -> None:
    deferred = (
        StrategyFamily.ABSOLUTE_MOMENTUM,
        StrategyFamily.MULTI_HORIZON_TREND,
        StrategyFamily.VOLATILITY_ADJUSTED_TREND,
        StrategyFamily.BOUNDED_MEAN_REVERSION,
        StrategyFamily.CROSS_SECTIONAL_RELATIVE_STRENGTH,
        StrategyFamily.DEFENSIVE_ROTATION,
        StrategyFamily.CROSS_ASSET_REGIME_GATE,
        StrategyFamily.FIXED_ENSEMBLE,
    )
    for family in deferred:
        proposal = _g1_proposal(spec=DeferredStrategySpec(family))
        assert proposal.semantic_status.value == "UNSUPPORTED"
        assert proposal.family is family
        with pytest.raises(DiscoveryError):
            compile_strategy_config(proposal.strategy_spec)


def test_g2_requires_prior_g1_parent_diagnostics_and_visibility() -> None:
    parent = _g1_proposal()
    prior = _result_record(
        parent,
        event=1,
        trial=1,
        disposition=TrialDisposition.SHORTLISTED,
        label="parent",
        code="G1_DIAGNOSTIC_READY",
        pnl_visible=True,
        diagnostic_visible=True,
    )
    reference = Generation1DiagnosticReference(
        parent.proposal_id, 1, prior.diagnostic_id
    )
    child = ResearchProposal(
        campaign_version="v1",
        generation=2,
        proposal_kind=ProposalKind.MUTATION,
        parent_proposal_ids=(parent.proposal_id,),
        strategy_spec=DonchianBreakoutSpec(35, 50, 20),
        hypothesis="Remove the band filter after its low breadth diagnostic.",
        expected_mechanism="A prior channel breakout may preserve participation.",
        falsification_condition="Stress returns remain weak after removing the band.",
        source_reference_labels=("A147_FILTERED_TREND",),
        information_visibility=_visibility(
            VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
            diagnostics=(reference,),
        ),
        producer_label="offline-fixture",
    )
    child_record = _result_record(
        child,
        event=2,
        trial=2,
        disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
        label="child-failure",
        code="SYNTHETIC_EVALUATOR_FAILURE",
    )
    ledger = TrialLedger((prior, child_record))
    assert ledger.evaluated_trial_counts_by_generation == (1, 1)

    with pytest.raises(DiscoveryError):
        InformationVisibility(
            VisibilityStage.GENERATION_1_PRE_RESULTS,
            visible_evidence=_visible_evidence(),
            final_holdout_accessed=True,
        )
    with pytest.raises(DiscoveryError):
        InformationVisibility(
            VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
            visible_evidence=_visible_evidence(),
            visible_generation1_diagnostics=(reference,),
            confirmation_results_visible=True,
        )
    with pytest.raises(DiscoveryError):
        ResearchProposal(
            campaign_version="v1",
            generation=2,
            proposal_kind=ProposalKind.MUTATION,
            parent_proposal_ids=(parent.proposal_id,),
            strategy_spec=DonchianBreakoutSpec(35, 50, 20),
            hypothesis="A chronological proposal with a missing diagnostic.",
            expected_mechanism="A channel may retain directional exposure.",
            falsification_condition="The channel loses breadth under stress.",
            source_reference_labels=("A147_FILTERED_TREND",),
            information_visibility=_visibility(
                VisibilityStage.GENERATION_2_PRE_CONFIRMATION
            ),
            producer_label="offline-fixture",
        )


def test_ledger_retains_duplicate_invalid_unsupported_and_failed_trials() -> None:
    baseline = _g1_proposal()
    same_program = _g1_proposal(
        hypothesis="The same program with a different explanation.",
        producer="second-producer",
    )
    invalid = _g1_proposal(
        spec=MovingAverageTrendSpec(55, 100, MovingAverageRule.BASE_MA),
        hypothesis="This proposal is well-formed but policy-invalid.",
    )
    deferred = _g1_proposal(
        spec=DeferredStrategySpec(StrategyFamily.ABSOLUTE_MOMENTUM),
        hypothesis="Absolute momentum remains deferred in this checkpoint.",
    )
    failed = _g1_proposal(
        spec=DonchianBreakoutSpec(35, 50, 20),
        hypothesis="The MA-gated prior channel high may capture breakouts.",
    )
    zero = _g1_proposal(
        spec=MovingAverageTrendSpec(50, 200, MovingAverageRule.MA_PERCENT_BAND_010),
        hypothesis="A slower band may reduce turnover.",
    )
    economic = _g1_proposal(
        spec=DonchianBreakoutSpec(55, 100, 55),
        hypothesis="A longer prior channel may reduce false entries.",
    )

    records = (
        TrialLedgerRecord(
            1,
            1,
            baseline,
            TrialDisposition.ACCEPTED_FOR_EVALUATION,
        ),
        _result_record(
            baseline,
            event=2,
            trial=1,
            disposition=TrialDisposition.SHORTLISTED,
            label="baseline",
            code="SHORTLISTED",
        ),
        TrialLedgerRecord(
            3,
            2,
            same_program,
            TrialDisposition.DUPLICATE_REJECTED,
            terminal_diagnostic_code="DUPLICATE_SEMANTIC_PROGRAM",
        ),
        TrialLedgerRecord(
            4,
            3,
            baseline,
            TrialDisposition.DUPLICATE_REJECTED,
            terminal_diagnostic_code="DUPLICATE_SEMANTIC_PROGRAM",
        ),
        TrialLedgerRecord(
            5,
            4,
            invalid,
            TrialDisposition.INVALID,
            terminal_diagnostic_code="INVALID_POLICY_FIXTURE",
        ),
        TrialLedgerRecord(
            6,
            5,
            deferred,
            TrialDisposition.UNSUPPORTED,
            terminal_diagnostic_code="NO_ACCEPTED_STANDALONE_EVALUATOR",
        ),
        TrialLedgerRecord(
            7,
            6,
            deferred,
            TrialDisposition.DUPLICATE_REJECTED,
            terminal_diagnostic_code="DUPLICATE_SEMANTIC_PROGRAM",
        ),
        _result_record(
            failed,
            event=8,
            trial=7,
            disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
            label="failed",
            code="SYNTHETIC_DETERMINISTIC_FAILURE",
        ),
        _result_record(
            zero,
            event=9,
            trial=8,
            disposition=TrialDisposition.ZERO_TRADE,
            label="zero-trade",
            code="ZERO_TRADES",
        ),
        _result_record(
            economic,
            event=10,
            trial=9,
            disposition=TrialDisposition.ECONOMICALLY_REJECTED,
            label="economic",
            code="ECONOMICALLY_REJECTED",
        ),
    )
    ledger = TrialLedger(records)

    assert len(ledger.records) == 10
    assert ledger.records[2].disposition is TrialDisposition.DUPLICATE_REJECTED
    assert ledger.records[3].disposition is TrialDisposition.DUPLICATE_REJECTED
    assert ledger.records[4].disposition is TrialDisposition.INVALID
    assert ledger.records[5].disposition is TrialDisposition.UNSUPPORTED
    assert ledger.records[6].disposition is TrialDisposition.DUPLICATE_REJECTED
    assert ledger.records[7].result_id is None
    assert ledger.records[7].pnl_visible is False
    assert ledger.evaluated_trial_count == 4
    assert ledger.evaluated_trial_counts_by_generation == (4, 0)
    assert ledger.evaluated_trial_count_provenance == COUNT_PROVENANCE
    assert ledger.to_dict()["evaluated_trial_count"] == 4


def test_ledger_canonical_roundtrip_and_aggregate_binds_ordered_history() -> None:
    proposal = _g1_proposal()
    record = _result_record(
        proposal,
        event=1,
        trial=1,
        disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
        label="failure",
        code="SYNTHETIC_FAILURE",
    )
    ledger = TrialLedger((record,))
    decoded = TrialLedger.from_bytes(ledger.to_bytes())

    assert decoded == ledger
    assert decoded.ledger_id == ledger.ledger_id
    assert decoded.evaluated_trial_count == 1
    assert (
        decoded.records[0].search_trial_count_provenance
        == "COUNTED_ONCE_BY_TRIAL_ORDINAL"
    )

    other_producer = _g1_proposal(producer="different-producer")
    other_record = _result_record(
        other_producer,
        event=1,
        trial=1,
        disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
        label="failure",
        code="SYNTHETIC_FAILURE",
    )
    assert other_producer.proposal_id == proposal.proposal_id
    assert TrialLedger((other_record,)).ledger_id != ledger.ledger_id

    appended = ledger.append(
        TrialLedgerRecord(
            event_ordinal=2,
            trial_ordinal=2,
            proposal=_g1_proposal(
                spec=DeferredStrategySpec(StrategyFamily.FIXED_ENSEMBLE),
                hypothesis="A deferred family is retained without evaluation.",
            ),
            disposition=TrialDisposition.UNSUPPORTED,
            terminal_diagnostic_code="UNSUPPORTED_FIXTURE",
        )
    )
    assert len(ledger.records) == 1
    assert len(appended.records) == 2
    assert appended.ledger_id != ledger.ledger_id


def test_ledger_rejects_duplicate_order_gap_double_count_and_bad_bindings() -> None:
    proposal = _g1_proposal()
    accepted = TrialLedgerRecord(
        1, 1, proposal, TrialDisposition.ACCEPTED_FOR_EVALUATION
    )
    terminal = _result_record(
        proposal,
        event=2,
        trial=1,
        disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
        label="single-attempt",
        code="SYNTHETIC_FAILURE",
    )
    ledger = TrialLedger((accepted, terminal))
    assert ledger.evaluated_trial_count == 1

    duplicate_attempt = _result_record(
        proposal,
        event=3,
        trial=1,
        disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
        label="second-attempt",
        code="SECOND_FAILURE",
    )
    with pytest.raises(DiscoveryError):
        TrialLedger((accepted, terminal, duplicate_attempt))
    other_proposal = _g1_proposal(
        spec=DonchianBreakoutSpec(35, 50, 20),
        hypothesis="A second trial that cannot reuse the first attempt identity.",
    )
    reused_attempt = _result_record(
        other_proposal,
        event=3,
        trial=2,
        disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
        label="different-trial",
        code="SYNTHETIC_FAILURE",
    )
    reused_attempt = replace(
        reused_attempt,
        evaluation_attempt_id=terminal.evaluation_attempt_id,
    )
    with pytest.raises(DiscoveryError):
        TrialLedger((accepted, terminal, reused_attempt))
    with pytest.raises(DiscoveryError):
        TrialLedger(
            (
                TrialLedgerRecord(
                    2,
                    1,
                    proposal,
                    TrialDisposition.INVALID,
                    terminal_diagnostic_code="INVALID",
                ),
            )
        )
    with pytest.raises(DiscoveryError):
        TrialLedgerRecord(
            1,
            1,
            proposal,
            TrialDisposition.SHORTLISTED,
            terminal_diagnostic_code="SHORTLISTED",
            pnl_visible=True,
        )


def test_closed_parsers_reject_duplicate_unknown_missing_and_noncanonical_fields() -> (
    None
):
    proposal = _g1_proposal()
    raw = proposal.to_dict()
    unknown = dict(raw)
    unknown["arbitrary_expression"] = "lambda x: x"
    with pytest.raises(DiscoveryError):
        ResearchProposal.from_dict(unknown)
    missing = dict(raw)
    del missing["falsification_condition"]
    with pytest.raises(DiscoveryError):
        ResearchProposal.from_dict(missing)
    duplicate_key_body = proposal.to_bytes().replace(
        b'"schema":"ai-strategy-discovery-proposal/v1",',
        b'"schema":"ai-strategy-discovery-proposal/v1","schema":"ai-strategy-discovery-proposal/v1",',
        1,
    )
    with pytest.raises(DiscoveryError):
        ResearchProposal.from_bytes(duplicate_key_body)
    with pytest.raises(DiscoveryError):
        ResearchProposal.from_bytes(proposal.to_bytes() + b"\n")

    ledger = TrialLedger(())
    ledger_raw = ledger.to_dict()
    ledger_raw["evaluated_trial_count"] = 1
    with pytest.raises(DiscoveryError):
        TrialLedger.from_dict(ledger_raw)
    attempted = TrialLedger(
        (
            _result_record(
                _g1_proposal(),
                event=1,
                trial=1,
                disposition=TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
                label="bool-count",
                code="SYNTHETIC_FAILURE",
            ),
        )
    )
    bool_count = attempted.to_dict()
    bool_count["evaluated_trial_count"] = True
    with pytest.raises(DiscoveryError):
        TrialLedger.from_dict(bool_count)
    bool_generation = attempted.to_dict()
    record_with_bool_generation = bool_generation["records"][0]
    record_with_bool_generation["generation"] = True
    with pytest.raises(DiscoveryError):
        TrialLedger.from_dict(bool_generation)
    bool_generation_count = attempted.to_dict()
    bool_generation_count["evaluated_trial_count_by_generation"] = [True, 0]
    with pytest.raises(DiscoveryError):
        TrialLedger.from_dict(bool_generation_count)
    with pytest.raises(DiscoveryError):
        TrialLedger.from_bytes(
            b'{"schema":"ai-strategy-discovery-trial-ledger/v1","schema":"duplicate"}'
        )


def test_invalid_submission_reference_keeps_safe_fingerprint() -> None:
    invalid = InvalidProposalReference(
        generation=1,
        caller_semantic_fingerprint="c" * 64,
        diagnostic_code="UNKNOWN_SPEC_FIELD",
        source_reference_labels=("UNPARSED_MODEL_INPUT",),
        information_visibility=_visibility(VisibilityStage.GENERATION_1_PRE_RESULTS),
        producer_label="offline-fixture",
    )
    assert "raw" not in invalid.to_dict()
    assert "payload" not in invalid.to_dict()
    assert "UNKNOWN_SPEC_FIELD" == invalid.to_dict()["diagnostic_code"]

    first = TrialLedgerRecord(
        1,
        1,
        invalid,
        TrialDisposition.INVALID,
        terminal_diagnostic_code="UNKNOWN_SPEC_FIELD",
    )
    duplicate = TrialLedgerRecord(
        2,
        2,
        invalid,
        TrialDisposition.DUPLICATE_REJECTED,
        terminal_diagnostic_code="DUPLICATE_SEMANTIC_PROGRAM",
    )
    ledger = TrialLedger((first, duplicate))
    decoded = TrialLedger.from_bytes(ledger.to_bytes())
    assert decoded == ledger
    assert decoded.evaluated_trial_count == 0
    assert decoded.records[0].proposal_id == decoded.records[1].proposal_id

    malformed_g2 = InvalidProposalReference(
        generation=2,
        caller_semantic_fingerprint="d" * 64,
        diagnostic_code="INVALID_PARENT_LINKAGE",
        source_reference_labels=("UNPARSED_MODEL_INPUT",),
        information_visibility=_visibility(
            VisibilityStage.GENERATION_2_PRE_CONFIRMATION
        ),
        producer_label="offline-fixture",
    )
    assert malformed_g2.parent_proposal_ids == ()
    g1_rejected = TrialLedgerRecord(
        1,
        1,
        _g1_proposal(),
        TrialDisposition.INVALID,
        terminal_diagnostic_code="INVALID_POLICY_FIXTURE",
    )
    g2_invalid = TrialLedgerRecord(
        2,
        2,
        malformed_g2,
        TrialDisposition.INVALID,
        terminal_diagnostic_code="INVALID_PARENT_LINKAGE",
    )
    assert TrialLedger((g1_rejected, g2_invalid)).evaluated_trial_count == 0


def test_visibility_blocks_late_g1_and_early_g2() -> None:
    with pytest.raises(DiscoveryError):
        VisibleEvidenceReference(
            reference_label="FORBIDDEN_CONFIRMATION",
            dataset_label="CAMPAIGN_DATASET",
            timeframe=VisibleTimeframe.DAILY,
            time_partition=VisibleTimePartition.CAMPAIGN_CONFIRMATION_2022_2023,
            classification=VisibleEvidenceClassification.GENERATION_2_CONFIRMATION_RESULT,
        )

    visible_parent = _g1_proposal(
        spec=MovingAverageTrendSpec(35, 50, MovingAverageRule.BASE_MA),
        hypothesis="An evaluated parent diagnostic.",
    )
    parent_record = _result_record(
        visible_parent,
        event=1,
        trial=1,
        disposition=TrialDisposition.SHORTLISTED,
        label="visible-parent",
        code="VISIBLE_DIAGNOSTIC",
        diagnostic_visible=True,
    )
    late_g1 = _g1_proposal(
        spec=MovingAverageTrendSpec(55, 100, MovingAverageRule.BASE_MA),
        hypothesis="A late proposal after diagnostic exposure.",
    )
    with pytest.raises(DiscoveryError):
        TrialLedger(
            (
                parent_record,
                TrialLedgerRecord(
                    2,
                    2,
                    late_g1,
                    TrialDisposition.INVALID,
                    terminal_diagnostic_code="INVALID_POLICY_FIXTURE",
                ),
            )
        )

    pending_parent = TrialLedgerRecord(
        1,
        1,
        visible_parent,
        TrialDisposition.ACCEPTED_FOR_EVALUATION,
    )
    pending_other = TrialLedgerRecord(
        2,
        2,
        _g1_proposal(
            spec=MovingAverageTrendSpec(55, 100, MovingAverageRule.BASE_MA),
            hypothesis="Another first-wave proposal.",
        ),
        TrialDisposition.ACCEPTED_FOR_EVALUATION,
    )
    diagnostic_ref = Generation1DiagnosticReference(
        visible_parent.proposal_id, 1, parent_record.diagnostic_id
    )
    child = ResearchProposal(
        campaign_version="v1",
        generation=2,
        proposal_kind=ProposalKind.MUTATION,
        parent_proposal_ids=(visible_parent.proposal_id,),
        strategy_spec=DonchianBreakoutSpec(35, 50, 20),
        hypothesis="A G2 child after G1 completion.",
        expected_mechanism="A channel entry may improve exposure.",
        falsification_condition="The channel loses stress robustness.",
        source_reference_labels=("A147_FILTERED_TREND",),
        information_visibility=_visibility(
            VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
            diagnostics=(diagnostic_ref,),
        ),
        producer_label="offline-fixture",
    )
    g2_record = TrialLedgerRecord(
        4,
        3,
        child,
        TrialDisposition.INVALID,
        terminal_diagnostic_code="INVALID_POLICY_FIXTURE",
    )
    with pytest.raises(DiscoveryError):
        TrialLedger(
            (
                pending_parent,
                pending_other,
                _result_record(
                    visible_parent,
                    event=3,
                    trial=1,
                    disposition=TrialDisposition.SHORTLISTED,
                    label="pending-parent-result",
                    code="VISIBLE_DIAGNOSTIC",
                    diagnostic_visible=True,
                ),
                g2_record,
            )
        )


def test_g2_proposal_set_freezes_before_confirmation_output() -> None:
    parent = _g1_proposal()
    g1_result = _result_record(
        parent,
        event=1,
        trial=1,
        disposition=TrialDisposition.SHORTLISTED,
        label="g1-complete",
        code="G1_DIAGNOSTIC_READY",
        diagnostic_visible=True,
    )
    reference = Generation1DiagnosticReference(
        parent.proposal_id, 1, g1_result.diagnostic_id
    )

    def g2_proposal(spec, hypothesis: str) -> ResearchProposal:
        return ResearchProposal(
            campaign_version="v1",
            generation=2,
            proposal_kind=ProposalKind.MUTATION,
            parent_proposal_ids=(parent.proposal_id,),
            strategy_spec=spec,
            hypothesis=hypothesis,
            expected_mechanism=(
                "The G1 diagnostic motivates a bounded structural change."
            ),
            falsification_condition=(
                "Confirmation evidence rejects the proposed mechanism."
            ),
            source_reference_labels=("A147_FILTERED_TREND",),
            information_visibility=_visibility(
                VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
                diagnostics=(reference,),
            ),
            producer_label="offline-fixture",
        )

    first = g2_proposal(
        DonchianBreakoutSpec(35, 50, 20), "A short channel may improve entry timing."
    )
    second = g2_proposal(
        MovingAverageTrendSpec(55, 100, MovingAverageRule.MA_PERCENT_BAND_010),
        "A slower band may reduce confirmation turnover.",
    )
    late = g2_proposal(
        DonchianBreakoutSpec(55, 100, 55),
        "A late proposal after confirmation became visible.",
    )
    records = (
        g1_result,
        TrialLedgerRecord(2, 2, first, TrialDisposition.ACCEPTED_FOR_EVALUATION),
        TrialLedgerRecord(3, 3, second, TrialDisposition.ACCEPTED_FOR_EVALUATION),
        _result_record(
            first,
            event=4,
            trial=2,
            disposition=TrialDisposition.SHORTLISTED,
            label="g2-first",
            code="CONFIRMATION_RESULT",
            pnl_visible=True,
        ),
        _result_record(
            second,
            event=5,
            trial=3,
            disposition=TrialDisposition.ECONOMICALLY_REJECTED,
            label="g2-second",
            code="CONFIRMATION_REJECTED",
        ),
        TrialLedgerRecord(
            6,
            4,
            late,
            TrialDisposition.INVALID,
            terminal_diagnostic_code="LATE_G2_PROPOSAL",
        ),
    )
    with pytest.raises(DiscoveryError):
        TrialLedger(records)


def test_import_surface_has_no_external_effect_dependencies() -> None:
    from pathlib import Path

    source = (
        Path(__file__).parents[2]
        / "src/trading_bot/experiments/ai_strategy_discovery.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    forbidden = {
        "alpaca",
        "boto3",
        "openai",
        "requests",
        "robinhood",
        "trading_bot.broker",
        "trading_bot.runtime",
        "trading_bot.production",
    }
    assert not any(
        imported == blocked or imported.startswith(f"{blocked}.")
        for imported in imports
        for blocked in forbidden
    )
    assert "trading_bot.experiments.filtered_trend_strategies" in {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
