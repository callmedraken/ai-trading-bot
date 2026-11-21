"""Closed, accepted-lineage plan for six Generation-2 recombinations.

The plan consumes typed in-memory Generation-1 evidence only. It does not read
artifacts or market data, run an evaluator, or perform provider, AI, broker, or
lifecycle effects.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from uuid import UUID, uuid5

from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    GENERATION_2_MAX_EVALUATED,
    ConjunctiveTrendSpec,
    Generation1DiagnosticReference,
    InformationVisibility,
    ProposalKind,
    ResearchProposal,
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
)
from trading_bot.experiments.ai_strategy_discovery_generation1_plan import (
    Generation1ProposalSet,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

SCHEMA = "ai-strategy-discovery-generation2-proposal-set/v1"
IDENTITY_VERSION = "ai-strategy-discovery-generation2-proposal-set-identity/v1"
FROZEN_CANDIDATE_COUNT = 6
MAX_PROPOSAL_SET_BYTES = 4 * 1024 * 1024

ACCEPTED_GENERATION1_PROPOSAL_SET_ID = "b2b3cadc-c11d-5a7a-be0b-5a2e16b9b39b"
ACCEPTED_GENERATION1_ANALYSIS_ID = "d5ca081e-7490-5590-921d-10cee373d012"
ACCEPTED_GENERATION1_TERMINAL_LEDGER_ID = "68418f44-7db0-5080-a6bd-a956a928bd4a"
_ACCEPTED_GENERATION1_PROPOSAL_COUNT = 22
_ACCEPTED_GENERATION1_EVALUATED_COUNT = 22

_IDENTITY_NAMESPACE = UUID("8270b75a-3ac2-5f63-9c21-784d0857bdbb")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_PARENT_SPECIFICATIONS = {
    proposal_id: spec
    for pair in frozen_generation2_parent_pairs()
    for proposal_id, spec in pair
}
_FROZEN_PARENT_PAIRS = tuple(
    tuple(parent_id for parent_id, _ in pair)
    for pair in frozen_generation2_parent_pairs()
)


class Generation2PlanError(ValueError):
    """Malformed or misbound Generation-2 proposal plan."""


@dataclass(frozen=True, slots=True, init=False)
class Generation2ProposalSet:
    """Exactly six G2 proposals bound to accepted typed G1 records.

    Construction requires the accepted typed G1 proposal set, whole-panel
    analysis, and terminal ledger. There is no constructor accepting arbitrary
    G2 proposals or caller-selected accepted identities.
    """

    campaign_version: str
    accepted_generation1_proposal_set_id: str
    accepted_generation1_terminal_ledger_id: str
    accepted_generation1_analysis_id: str
    accepted_generation1_dataset_identity: str
    accepted_generation1_dataset_evidence_id: str
    source_head: str
    source_tree: str
    proposals: tuple[ResearchProposal, ...]
    identity: str
    schema: str = field(default=SCHEMA, init=False)

    def __init__(
        self,
        generation1_proposal_set: Generation1ProposalSet,
        generation1_analysis: Generation1BatchAnalysis,
        terminal_ledger: TrialLedger,
        source_head: str,
        source_tree: str,
    ) -> None:
        dataset_evidence_id = _validate_accepted_generation1_inputs(
            generation1_proposal_set, generation1_analysis, terminal_ledger
        )
        _require_git_id(source_head, "source HEAD")
        _require_git_id(source_tree, "source tree")
        proposals = _frozen_proposals(generation1_proposal_set, terminal_ledger)

        object.__setattr__(self, "campaign_version", CAMPAIGN_VERSION)
        object.__setattr__(
            self,
            "accepted_generation1_proposal_set_id",
            generation1_proposal_set.identity,
        )
        object.__setattr__(
            self,
            "accepted_generation1_terminal_ledger_id",
            terminal_ledger.ledger_id,
        )
        object.__setattr__(
            self, "accepted_generation1_analysis_id", generation1_analysis.identity
        )
        object.__setattr__(
            self,
            "accepted_generation1_dataset_identity",
            generation1_analysis.dataset_identity,
        )
        object.__setattr__(
            self, "accepted_generation1_dataset_evidence_id", dataset_evidence_id
        )
        object.__setattr__(self, "source_head", source_head)
        object.__setattr__(self, "source_tree", source_tree)
        object.__setattr__(self, "proposals", proposals)
        object.__setattr__(self, "schema", SCHEMA)
        object.__setattr__(
            self, "identity", _identity(self.to_dict(include_identity=False))
        )

    @property
    def proposal_ids(self) -> tuple[str, ...]:
        return tuple(proposal.proposal_id for proposal in self.proposals)

    @property
    def semantic_program_ids(self) -> tuple[str, ...]:
        return tuple(proposal.semantic_program_id for proposal in self.proposals)

    @property
    def parent_proposal_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            tuple(sorted(proposal.parent_proposal_ids)) for proposal in self.proposals
        )  # type: ignore[return-value]

    @property
    def parent_diagnostic_references(
        self,
    ) -> tuple[tuple[Generation1DiagnosticReference, ...], ...]:
        return tuple(
            proposal.information_visibility.visible_generation1_diagnostics
            for proposal in self.proposals
        )

    @property
    def max_evaluated(self) -> int:
        return GENERATION_2_MAX_EVALUATED

    @property
    def evaluated_candidate_count(self) -> int:
        return FROZEN_CANDIDATE_COUNT

    @property
    def confirmation_results_visible(self) -> bool:
        return False

    @property
    def final_holdout_sealed(self) -> bool:
        return True

    def to_dict(self, *, include_identity: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "schema": self.schema,
            "campaign_version": self.campaign_version,
            "accepted_generation1_proposal_set_id": (
                self.accepted_generation1_proposal_set_id
            ),
            "accepted_generation1_terminal_ledger_id": (
                self.accepted_generation1_terminal_ledger_id
            ),
            "accepted_generation1_analysis_id": self.accepted_generation1_analysis_id,
            "accepted_generation1_dataset_identity": (
                self.accepted_generation1_dataset_identity
            ),
            "accepted_generation1_dataset_evidence_id": (
                self.accepted_generation1_dataset_evidence_id
            ),
            "source": {"head": self.source_head, "tree": self.source_tree},
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "ordered_proposal_ids": list(self.proposal_ids),
            "ordered_semantic_program_ids": list(self.semantic_program_ids),
            "ordered_parent_proposal_pairs": [
                list(pair) for pair in self.parent_proposal_pairs
            ],
            "ordered_parent_diagnostic_references": [
                [reference.to_dict() for reference in references]
                for references in self.parent_diagnostic_references
            ],
            "complete_frozen_population": True,
            "budget": {
                "max_evaluated": GENERATION_2_MAX_EVALUATED,
                "evaluated_candidate_count": FROZEN_CANDIDATE_COUNT,
            },
            "information_visibility": {
                "stage": VisibilityStage.GENERATION_2_PRE_CONFIRMATION.value,
                "confirmation_results_visible": False,
                "final_holdout_sealed": True,
            },
        }
        if include_identity:
            result["identity"] = self.identity
        return result

    def to_bytes(self) -> bytes:
        body = canonical_json_bytes(self.to_dict())
        if len(body) > MAX_PROPOSAL_SET_BYTES:
            raise Generation2PlanError("proposal set exceeds the byte limit")
        return body

    @classmethod
    def from_dict(
        cls,
        raw: object,
        *,
        generation1_proposal_set: Generation1ProposalSet,
        generation1_analysis: Generation1BatchAnalysis,
        terminal_ledger: TrialLedger,
    ) -> Generation2ProposalSet:
        _exact_object(raw)
        source = raw.get("source") if type(raw) is dict else None
        if type(source) is not dict or set(source) != {"head", "tree"}:
            raise Generation2PlanError("source identity must use the closed schema")
        expected = cls(
            generation1_proposal_set,
            generation1_analysis,
            terminal_ledger,
            source["head"],
            source["tree"],
        )
        if canonical_json_bytes(expected.to_dict()) != canonical_json_bytes(raw):
            raise Generation2PlanError(
                "proposal-set identity or derived fields disagree"
            )
        return expected

    @classmethod
    def from_bytes(
        cls,
        body: bytes,
        *,
        generation1_proposal_set: Generation1ProposalSet,
        generation1_analysis: Generation1BatchAnalysis,
        terminal_ledger: TrialLedger,
    ) -> Generation2ProposalSet:
        if type(body) is not bytes or not body or len(body) > MAX_PROPOSAL_SET_BYTES:
            raise Generation2PlanError("proposal-set JSON size is invalid")
        try:
            raw = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            plan = cls.from_dict(
                raw,
                generation1_proposal_set=generation1_proposal_set,
                generation1_analysis=generation1_analysis,
                terminal_ledger=terminal_ledger,
            )
            if plan.to_bytes() != body:
                raise Generation2PlanError("proposal-set JSON is not canonical")
            return plan
        except (json.JSONDecodeError, UnicodeError, RecursionError, TypeError):
            raise Generation2PlanError(
                "invalid canonical Generation-2 proposal set"
            ) from None


def _validate_accepted_generation1_inputs(
    proposal_set: Generation1ProposalSet,
    analysis: Generation1BatchAnalysis,
    ledger: TrialLedger,
) -> str:
    if type(proposal_set) is not Generation1ProposalSet:
        raise Generation2PlanError("typed accepted G1 proposal set is required")
    if type(analysis) is not Generation1BatchAnalysis:
        raise Generation2PlanError("typed accepted G1 analysis is required")
    if type(ledger) is not TrialLedger:
        raise Generation2PlanError("typed accepted G1 terminal ledger is required")
    if proposal_set.identity != ACCEPTED_GENERATION1_PROPOSAL_SET_ID:
        raise Generation2PlanError("G1 proposal set is not the accepted campaign set")
    if analysis.identity != ACCEPTED_GENERATION1_ANALYSIS_ID:
        raise Generation2PlanError(
            "G1 analysis is not the accepted whole-panel analysis"
        )
    if ledger.ledger_id != ACCEPTED_GENERATION1_TERMINAL_LEDGER_ID:
        raise Generation2PlanError("G1 ledger is not the accepted terminal ledger")
    if (
        proposal_set.campaign_version != CAMPAIGN_VERSION
        or not proposal_set.is_complete_population
        or proposal_set.supported_evaluated_count
        != _ACCEPTED_GENERATION1_PROPOSAL_COUNT
        or analysis.proposal_set_identity != proposal_set.identity
        or len(analysis.programs) != _ACCEPTED_GENERATION1_PROPOSAL_COUNT
        or tuple(program.proposal_id for program in analysis.programs)
        != proposal_set.proposal_identities
        or tuple(program.semantic_program_id for program in analysis.programs)
        != proposal_set.semantic_program_ids
        or ledger.evaluated_trial_counts_by_generation
        != (_ACCEPTED_GENERATION1_EVALUATED_COUNT, 0)
        or ledger.evaluated_trial_count != _ACCEPTED_GENERATION1_EVALUATED_COUNT
        or any(record.generation != 1 for record in ledger.records)
    ):
        raise Generation2PlanError(
            "accepted G1 typed inputs are internally inconsistent"
        )

    evaluated_proposal_ids = {
        record.proposal_id
        for record in ledger.records
        if record.generation == 1 and record.evaluation_attempt_id is not None
    }
    if evaluated_proposal_ids != set(proposal_set.proposal_identities):
        raise Generation2PlanError("terminal ledger does not cover the complete G1 set")
    evidence_ids = {
        record.dataset_evidence_id
        for record in ledger.records
        if record.generation == 1 and record.evaluation_attempt_id is not None
    }
    if len(evidence_ids) != 1 or None in evidence_ids:
        raise Generation2PlanError(
            "G1 terminal ledger has inconsistent dataset evidence"
        )
    return next(iter(evidence_ids))  # type: ignore[return-value]


def _frozen_proposals(
    proposal_set: Generation1ProposalSet, ledger: TrialLedger
) -> tuple[ResearchProposal, ...]:
    g1_by_id = {proposal.proposal_id: proposal for proposal in proposal_set.proposals}
    for proposal_id, expected_spec in _PARENT_SPECIFICATIONS.items():
        parent = g1_by_id.get(proposal_id)
        if parent is None or parent.strategy_spec != expected_spec:
            raise Generation2PlanError(
                "a frozen G2 parent is absent or has different G1 semantics"
            )

    latest_terminal: dict[str, TrialLedgerRecord] = {}
    for record in ledger.records:
        if record.generation == 1 and record.evaluation_attempt_id is not None:
            latest_terminal[record.proposal_id] = record

    proposals: list[ResearchProposal] = []
    for pair in _FROZEN_PARENT_PAIRS:
        ordered_parent_ids = tuple(sorted(pair))
        diagnostic_refs: list[Generation1DiagnosticReference] = []
        evidence_refs: list[VisibleEvidenceReference] = []
        source_labels: list[str] = []
        for parent_id in ordered_parent_ids:
            record = latest_terminal.get(parent_id)
            if (
                record is None
                or record.diagnostic_visible is not True
                or record.diagnostic_id is None
                or record.disposition is TrialDisposition.ACCEPTED_FOR_EVALUATION
            ):
                raise Generation2PlanError(
                    "frozen G2 parent lacks its exact visible terminal diagnostic"
                )
            diagnostic_refs.append(
                Generation1DiagnosticReference(
                    parent_proposal_id=parent_id,
                    parent_trial_ordinal=record.trial_ordinal,
                    diagnostic_id=record.diagnostic_id,
                )
            )
            label = f"g1-diagnostic-{parent_id}"
            source_labels.append(label)
            evidence_refs.append(
                VisibleEvidenceReference(
                    reference_label=label,
                    dataset_label="A147_DAILY_ACCEPTED",
                    timeframe=VisibleTimeframe.DAILY,
                    time_partition=VisibleTimePartition.DISCOVERY_2019_2021,
                    classification=(
                        VisibleEvidenceClassification.GENERATION_1_DISCOVERY_RESULT
                    ),
                )
            )

        visibility = InformationVisibility(
            stage=VisibilityStage.GENERATION_2_PRE_CONFIRMATION,
            visible_evidence=tuple(evidence_refs),
            visible_generation1_diagnostics=tuple(diagnostic_refs),
        )
        proposals.append(
            ResearchProposal(
                campaign_version=CAMPAIGN_VERSION,
                generation=2,
                proposal_kind=ProposalKind.RECOMBINATION,
                parent_proposal_ids=ordered_parent_ids,
                strategy_spec=ConjunctiveTrendSpec(
                    components=tuple(_PARENT_SPECIFICATIONS[item] for item in pair)
                ),
                hypothesis=(
                    "A strict momentum admission gate may reduce drawdown in an "
                    "otherwise strong accepted trend program."
                ),
                expected_mechanism=(
                    "The recombination is LONG only when both accepted G1 parent "
                    "programs are LONG at the completed session close."
                ),
                falsification_condition=(
                    "The candidate fails any frozen stress-confirmation gate or "
                    "is dominated on the frozen confirmation Pareto frontier."
                ),
                source_reference_labels=tuple(source_labels),
                information_visibility=visibility,
                producer_label="generation2-frozen-structural-plan-v1",
            )
        )
    if (
        len(proposals) != FROZEN_CANDIDATE_COUNT
        or len({proposal.semantic_program_id for proposal in proposals})
        != FROZEN_CANDIDATE_COUNT
    ):
        raise Generation2PlanError(
            "frozen G2 proposal population is not six unique programs"
        )
    return tuple(proposals)


def _identity(material: dict[str, object]) -> str:
    return str(
        uuid5(
            _IDENTITY_NAMESPACE,
            canonical_json_bytes(
                {"identity_version": IDENTITY_VERSION, **material}
            ).decode("utf-8"),
        )
    )


def _require_git_id(value: object, label: str) -> None:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise Generation2PlanError(f"{label} must be lowercase 40-hex")


def _exact_object(raw: object) -> dict[str, object]:
    expected = {
        "schema",
        "identity",
        "campaign_version",
        "accepted_generation1_proposal_set_id",
        "accepted_generation1_terminal_ledger_id",
        "accepted_generation1_analysis_id",
        "accepted_generation1_dataset_identity",
        "accepted_generation1_dataset_evidence_id",
        "source",
        "proposals",
        "ordered_proposal_ids",
        "ordered_semantic_program_ids",
        "ordered_parent_proposal_pairs",
        "ordered_parent_diagnostic_references",
        "complete_frozen_population",
        "budget",
        "information_visibility",
    }
    if type(raw) is not dict or set(raw) != expected:
        raise Generation2PlanError("proposal-set fields do not match the closed schema")
    return raw


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Generation2PlanError("duplicate JSON object field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise Generation2PlanError(f"non-finite JSON value rejected: {value}")
