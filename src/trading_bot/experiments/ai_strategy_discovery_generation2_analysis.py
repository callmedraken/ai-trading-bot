"""Whole-panel G2 confirmation analysis and in-memory ledger orchestration.

This module accepts only a frozen six-proposal set, its accepted G1 ledger
binding, and an immutable in-memory confirmation view. It has no provider, AI,
credential, broker, filesystem, or operator surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from enum import StrEnum
from statistics import median
from uuid import UUID

from trading_bot.experiments.ai_strategy_discovery import (
    ResearchProposal,
    TrialDisposition,
    TrialLedger,
    TrialLedgerRecord,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_analysis import (
    ZERO_EFFECT_COUNTER_NAMES,
)
from trading_bot.experiments.ai_strategy_discovery_generation2 import (
    ConfirmationView,
    Generation2ProgramResult,
    evaluate_generation2_program,
)
from trading_bot.experiments.ai_strategy_discovery_generation2_plan import (
    Generation2ProposalSet,
)
from trading_bot.experiments.filtered_trend_campaign import (
    CONTEXT,
    UNIVERSE,
    CellEvidence,
    Metrics,
    semantic_identity,
)

_ANNUAL_LABELS = ("2022", "2023")
_CONTINUOUS_LABEL = "continuous"
_RESULT_FAILURE_CODE = "G2_DETERMINISTIC_EVALUATION_FAILED"


class Generation2AnalysisError(ValueError):
    """Incomplete, inconsistent, or misbound G2 analysis input."""


class Generation2FailureCode(StrEnum):
    """Stable failure classifications that do not expose exception prose."""

    DETERMINISTIC_EVALUATION_VALUE_ERROR = _RESULT_FAILURE_CODE


@dataclass(frozen=True, slots=True)
class Generation2EvaluationFailure:
    """One deterministic evaluator failure bound to one attempted G2 trial."""

    proposal_id: str
    semantic_program_id: str
    dataset_identity: str
    attempt_id: str
    evaluation_id: str
    failure_code: Generation2FailureCode
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        for value, label in (
            (self.proposal_id, "proposal identity"),
            (self.semantic_program_id, "semantic program identity"),
            (self.dataset_identity, "dataset identity"),
            (self.attempt_id, "attempt identity"),
            (self.evaluation_id, "evaluation identity"),
        ):
            _require_uuid5(value, label)
        if type(self.failure_code) is not Generation2FailureCode:
            raise Generation2AnalysisError("failure code must be a declared value")
        object.__setattr__(
            self,
            "identity",
            semantic_identity(
                "generation2-evaluation-failure",
                (
                    self.proposal_id,
                    self.semantic_program_id,
                    self.dataset_identity,
                    self.attempt_id,
                    self.evaluation_id,
                    self.failure_code.value,
                ),
            ),
        )


Generation2Outcome = Generation2ProgramResult | Generation2EvaluationFailure


@dataclass(frozen=True, slots=True)
class ConfirmationSummary:
    """Base or stress diagnostics for one complete G2 confirmation panel."""

    continuous_symbol_returns: tuple[tuple[str, Decimal], ...]
    annual_asset_year_returns: tuple[tuple[str, str, Decimal], ...]
    median_2022_return: Decimal
    median_2023_return: Decimal
    median_continuous_return: Decimal
    minimum_continuous_return: Decimal
    positive_continuous_symbols: int
    positive_asset_year_cells: int
    worst_continuous_drawdown: Decimal
    annual_asset_year_turnovers: tuple[tuple[str, str, Decimal], ...]
    median_annual_turnover: Decimal

    def identity_material(self) -> tuple[object, ...]:
        return (
            self.continuous_symbol_returns,
            self.annual_asset_year_returns,
            self.median_2022_return,
            self.median_2023_return,
            self.median_continuous_return,
            self.minimum_continuous_return,
            self.positive_continuous_symbols,
            self.positive_asset_year_cells,
            self.worst_continuous_drawdown,
            self.annual_asset_year_turnovers,
            self.median_annual_turnover,
        )


@dataclass(frozen=True, slots=True)
class Generation2ProgramAnalysis:
    """Descriptive confirmation decision for one ordered frozen proposal."""

    proposal_id: str
    semantic_program_id: str
    outcome_identity: str
    disposition: TrialDisposition
    base: ConfirmationSummary | None
    stress: ConfirmationSummary | None
    nondominated: bool
    failure_code: Generation2FailureCode | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.proposal_id, "proposal identity"),
            (self.semantic_program_id, "semantic program identity"),
            (self.outcome_identity, "outcome identity"),
        ):
            _require_uuid5(value, label)
        if type(self.disposition) is not TrialDisposition:
            raise Generation2AnalysisError("G2 disposition must be a declared value")
        if type(self.nondominated) is not bool:
            raise Generation2AnalysisError("nondominated flag must be boolean")
        if self.disposition is TrialDisposition.DETERMINISTIC_EVALUATION_FAILED:
            if (
                self.base is not None
                or self.stress is not None
                or self.nondominated
                or type(self.failure_code) is not Generation2FailureCode
            ):
                raise Generation2AnalysisError(
                    "deterministic failure exposes diagnostics only"
                )
        elif self.disposition in (
            TrialDisposition.CONFIRMATION_PASSED,
            TrialDisposition.CONFIRMATION_REJECTED,
        ):
            if (
                type(self.base) is not ConfirmationSummary
                or type(self.stress) is not ConfirmationSummary
                or self.failure_code is not None
            ):
                raise Generation2AnalysisError(
                    "completed confirmation requires base and stress summaries"
                )
            gates = _confirmation_gates(self.stress)
            if (self.disposition is TrialDisposition.CONFIRMATION_PASSED) != (
                gates and self.nondominated
            ):
                raise Generation2AnalysisError(
                    "confirmation disposition disagrees with fixed gates/frontier"
                )
        else:
            raise Generation2AnalysisError(
                "G2 analysis disposition is outside the confirmation grammar"
            )

    def identity_material(self) -> tuple[object, ...]:
        return (
            self.proposal_id,
            self.semantic_program_id,
            self.outcome_identity,
            self.disposition.value,
            None if self.base is None else self.base.identity_material(),
            None if self.stress is None else self.stress.identity_material(),
            self.nondominated,
            None if self.failure_code is None else self.failure_code.value,
        )


@dataclass(frozen=True, slots=True)
class Generation2BatchAnalysis:
    """Complete ordered G2 analysis with no lifecycle promotion authority."""

    proposal_set_identity: str
    confirmation_view_identity: str
    dataset_identity: str
    programs: tuple[Generation2ProgramAnalysis, ...]
    pareto_front_proposal_ids: tuple[str, ...]
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        _require_uuid5(self.proposal_set_identity, "proposal-set identity")
        _require_uuid5(self.confirmation_view_identity, "confirmation-view identity")
        _require_uuid5(self.dataset_identity, "dataset identity")
        if type(self.programs) is not tuple or any(
            type(item) is not Generation2ProgramAnalysis for item in self.programs
        ):
            raise Generation2AnalysisError(
                "analysis requires ordered G2 program summaries"
            )
        if (
            len(self.programs) != 6
            or len({item.proposal_id for item in self.programs}) != 6
            or len({item.semantic_program_id for item in self.programs}) != 6
        ):
            raise Generation2AnalysisError(
                "analysis requires six distinct ordered G2 programs"
            )
        if type(self.pareto_front_proposal_ids) is not tuple or any(
            type(item) is not str for item in self.pareto_front_proposal_ids
        ):
            raise Generation2AnalysisError(
                "Pareto frontier requires ordered proposal IDs"
            )
        if len(set(self.pareto_front_proposal_ids)) != len(
            self.pareto_front_proposal_ids
        ):
            raise Generation2AnalysisError(
                "Pareto frontier contains duplicate proposals"
            )
        if not set(self.pareto_front_proposal_ids) <= {
            item.proposal_id for item in self.programs if item.stress is not None
        }:
            raise Generation2AnalysisError(
                "Pareto frontier contains an ineligible proposal"
            )
        if self.pareto_front_proposal_ids != tuple(
            item.proposal_id for item in self.programs if item.nondominated
        ):
            raise Generation2AnalysisError(
                "Pareto frontier order disagrees with program summaries"
            )
        object.__setattr__(
            self,
            "identity",
            semantic_identity(
                "generation2-whole-panel-analysis",
                (
                    self.proposal_set_identity,
                    self.confirmation_view_identity,
                    self.dataset_identity,
                    tuple(item.identity_material() for item in self.programs),
                    self.pareto_front_proposal_ids,
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class Generation2BatchRun:
    """In-memory G2 run containing the complete pre-evaluation ledger."""

    proposal_set_identity: str
    confirmation_view_identity: str
    dataset_identity: str
    dataset_evidence_id: str
    pre_evaluation_ledger: TrialLedger
    terminal_ledger: TrialLedger
    outcomes: tuple[Generation2Outcome, ...]
    analysis: Generation2BatchAnalysis
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        for value, label in (
            (self.proposal_set_identity, "proposal-set identity"),
            (self.confirmation_view_identity, "confirmation-view identity"),
            (self.dataset_identity, "dataset identity"),
            (self.dataset_evidence_id, "dataset evidence identity"),
        ):
            _require_uuid5(value, label)
        if (
            type(self.pre_evaluation_ledger) is not TrialLedger
            or type(self.terminal_ledger) is not TrialLedger
        ):
            raise Generation2AnalysisError("batch run requires canonical ledgers")
        if type(self.outcomes) is not tuple or any(
            type(item) not in (Generation2ProgramResult, Generation2EvaluationFailure)
            for item in self.outcomes
        ):
            raise Generation2AnalysisError("G2 outcomes must be closed typed values")
        if (
            len(self.outcomes) != 6
            or len({item.proposal_id for item in self.outcomes}) != 6
            or len({item.semantic_program_id for item in self.outcomes}) != 6
        ):
            raise Generation2AnalysisError(
                "batch run requires six distinct ordered G2 outcomes"
            )
        if type(self.analysis) is not Generation2BatchAnalysis:
            raise Generation2AnalysisError(
                "batch run requires exact canonical G2 analysis"
            )
        if (
            self.analysis.proposal_set_identity != self.proposal_set_identity
            or self.analysis.confirmation_view_identity
            != self.confirmation_view_identity
            or self.analysis.dataset_identity != self.dataset_identity
        ):
            raise Generation2AnalysisError("G2 batch analysis bindings disagree")
        if (
            len(self.outcomes) != len(self.analysis.programs)
            or tuple(item.proposal_id for item in self.outcomes)
            != tuple(item.proposal_id for item in self.analysis.programs)
            or tuple(item.identity for item in self.outcomes)
            != tuple(item.outcome_identity for item in self.analysis.programs)
        ):
            raise Generation2AnalysisError(
                "G2 outcomes do not match the complete analysis"
            )
        if (
            len(self.terminal_ledger.records)
            != len(self.pre_evaluation_ledger.records) + len(self.outcomes)
            or self.terminal_ledger.records[: len(self.pre_evaluation_ledger.records)]
            != self.pre_evaluation_ledger.records
        ):
            raise Generation2AnalysisError(
                "terminal ledger does not preserve its exact prefix"
            )
        terminal_records = self.terminal_ledger.records[
            len(self.pre_evaluation_ledger.records) :
        ]
        if any(
            record.proposal_id != program.proposal_id
            or record.disposition is not program.disposition
            or record.evaluation_attempt_id is None
            or record.dataset_evidence_id != self.dataset_evidence_id
            or (
                type(outcome) is Generation2EvaluationFailure
                and (
                    record.evaluation_attempt_id != outcome.attempt_id
                    or record.evaluation_id != outcome.evaluation_id
                )
            )
            or record.result_id
            != (outcome.identity if type(outcome) is Generation2ProgramResult else None)
            or record.terminal_diagnostic_code
            != (
                outcome.failure_code.value
                if type(outcome) is Generation2EvaluationFailure
                else _disposition_code(program.disposition)
            )
            or record.pnl_visible is not (type(outcome) is Generation2ProgramResult)
            or record.diagnostic_visible is not True
            for record, program, outcome in zip(
                terminal_records, self.analysis.programs, self.outcomes, strict=True
            )
        ):
            raise Generation2AnalysisError(
                "terminal visibility disagrees with complete G2 outcomes"
            )
        if self.pre_evaluation_ledger.evaluated_trial_counts_by_generation[
            0
        ] != self.terminal_ledger.evaluated_trial_counts_by_generation[
            0
        ] or self.terminal_ledger.evaluated_trial_counts_by_generation[
            1
        ] - self.pre_evaluation_ledger.evaluated_trial_counts_by_generation[1] != len(
            self.outcomes
        ):
            raise Generation2AnalysisError(
                "G2 attempts must count once without changing G1 history"
            )
        object.__setattr__(
            self,
            "identity",
            semantic_identity(
                "generation2-in-memory-batch-run",
                (
                    self.proposal_set_identity,
                    self.confirmation_view_identity,
                    self.dataset_identity,
                    self.dataset_evidence_id,
                    self.pre_evaluation_ledger.ledger_id,
                    self.terminal_ledger.ledger_id,
                    tuple(item.identity for item in self.outcomes),
                    self.analysis.identity,
                ),
            ),
        )

    @property
    def zero_effects(self) -> tuple[tuple[str, int], ...]:
        """Canonical immutable zero counters for this in-memory result."""
        return tuple((name, 0) for name in ZERO_EFFECT_COUNTER_NAMES)

    @property
    def final_holdout_sealed(self) -> bool:
        """The G2 analyzer has no holdout input and keeps it sealed."""
        return True


def analyze_generation2_batch(
    proposal_set: Generation2ProposalSet,
    outcomes: tuple[Generation2Outcome, ...],
    *,
    expected_dataset_identity: str,
    confirmation_view_identity: str,
) -> Generation2BatchAnalysis:
    """Analyze all six ordered outcomes and reject omissions or partial panels."""
    _validate_complete_proposal_set(proposal_set)
    _require_uuid5(expected_dataset_identity, "expected dataset identity")
    _require_uuid5(confirmation_view_identity, "confirmation-view identity")
    if expected_dataset_identity != proposal_set.accepted_generation1_dataset_identity:
        raise Generation2AnalysisError(
            "analysis dataset must match the accepted G1 dataset binding"
        )
    if type(outcomes) is not tuple or any(
        type(item) not in (Generation2ProgramResult, Generation2EvaluationFailure)
        for item in outcomes
    ):
        raise Generation2AnalysisError("outcome type is outside the closed G2 grammar")
    if len(outcomes) != len(proposal_set.proposals):
        raise Generation2AnalysisError(
            "one ordered outcome is required per frozen G2 proposal"
        )
    if tuple(item.proposal_id for item in outcomes) != tuple(
        proposal.proposal_id for proposal in proposal_set.proposals
    ):
        raise Generation2AnalysisError(
            "G2 outcomes are missing, duplicated, foreign, or reordered"
        )

    programs: list[Generation2ProgramAnalysis] = []
    for proposal, outcome in zip(proposal_set.proposals, outcomes, strict=True):
        if (
            outcome.semantic_program_id != proposal.semantic_program_id
            or outcome.dataset_identity != expected_dataset_identity
        ):
            raise Generation2AnalysisError(
                "G2 outcome semantic or dataset binding disagrees"
            )
        if type(outcome) is Generation2EvaluationFailure:
            programs.append(
                Generation2ProgramAnalysis(
                    proposal.proposal_id,
                    proposal.semantic_program_id,
                    outcome.identity,
                    TrialDisposition.DETERMINISTIC_EVALUATION_FAILED,
                    None,
                    None,
                    False,
                    outcome.failure_code,
                )
            )
            continue
        _validate_result(
            proposal,
            outcome,
            expected_dataset_identity,
            confirmation_view_identity,
        )
        programs.append(_summarize_program(proposal, outcome))

    completed = tuple(
        index for index, item in enumerate(programs) if item.stress is not None
    )
    frontier_indices = tuple(
        index
        for index in completed
        if not any(
            _dominates(programs[other].stress, programs[index].stress)
            for other in completed
            if other != index
        )
    )
    frontier_ids = tuple(programs[index].proposal_id for index in frontier_indices)
    frontier_set = set(frontier_ids)

    finalized: list[Generation2ProgramAnalysis] = []
    for item in programs:
        if item.stress is None:
            finalized.append(item)
            continue
        stress = item.stress
        nondominated = item.proposal_id in frontier_set
        gates = _confirmation_gates(stress)
        disposition = (
            TrialDisposition.CONFIRMATION_PASSED
            if gates and nondominated
            else TrialDisposition.CONFIRMATION_REJECTED
        )
        finalized.append(
            Generation2ProgramAnalysis(
                item.proposal_id,
                item.semantic_program_id,
                item.outcome_identity,
                disposition,
                item.base,
                item.stress,
                nondominated,
            )
        )

    return Generation2BatchAnalysis(
        proposal_set.identity,
        confirmation_view_identity,
        expected_dataset_identity,
        tuple(finalized),
        frontier_ids,
    )


def run_generation2_batch(
    proposal_set: Generation2ProposalSet,
    accepted_generation1_terminal_ledger: TrialLedger,
    confirmation_view: ConfirmationView,
    *,
    expected_source_head: str,
    expected_source_tree: str,
) -> Generation2BatchRun:
    """Evaluate the frozen six as one in-memory batch over a bounded view.

    The proposal set carries the accepted G1 dataset and evidence identities.
    Every G2 acceptance event is appended to a private immutable ledger copy
    before the fixed evaluator is invoked for the first time.
    """
    _validate_complete_proposal_set(proposal_set)
    if type(accepted_generation1_terminal_ledger) is not TrialLedger:
        raise Generation2AnalysisError(
            "an exact accepted G1 terminal ledger is required"
        )
    if type(confirmation_view) is not ConfirmationView:
        raise Generation2AnalysisError("a bounded confirmation view is required")
    _validate_run_bindings(
        proposal_set,
        accepted_generation1_terminal_ledger,
        confirmation_view,
        expected_source_head=expected_source_head,
        expected_source_tree=expected_source_tree,
    )

    pre_evaluation_ledger, ordinals = _prepare_ledger(
        proposal_set, accepted_generation1_terminal_ledger
    )
    attempts = {
        proposal.proposal_id: _attempt_binding(
            proposal_set,
            proposal,
            ordinals[proposal.proposal_id],
            confirmation_view,
        )
        for proposal in proposal_set.proposals
    }

    pending_outcomes: list[Generation2Outcome] = []
    for proposal in proposal_set.proposals:
        attempt_id, evaluation_id = attempts[proposal.proposal_id]
        try:
            outcome = evaluate_generation2_program(proposal, confirmation_view)
        except ValueError:
            outcome = Generation2EvaluationFailure(
                proposal.proposal_id,
                proposal.semantic_program_id,
                confirmation_view.dataset_identity,
                attempt_id,
                evaluation_id,
                Generation2FailureCode.DETERMINISTIC_EVALUATION_VALUE_ERROR,
            )
        pending_outcomes.append(outcome)

    outcomes = tuple(pending_outcomes)
    analysis = analyze_generation2_batch(
        proposal_set,
        outcomes,
        expected_dataset_identity=proposal_set.accepted_generation1_dataset_identity,
        confirmation_view_identity=confirmation_view.identity,
    )

    terminal_ledger = pre_evaluation_ledger
    for proposal, program, outcome in zip(
        proposal_set.proposals, analysis.programs, outcomes, strict=True
    ):
        accepted = _find_accepted_event(pre_evaluation_ledger, proposal.proposal_id)
        attempt_id, evaluation_id = attempts[proposal.proposal_id]
        if type(outcome) is Generation2EvaluationFailure:
            disposition = TrialDisposition.DETERMINISTIC_EVALUATION_FAILED
            result_id = None
            diagnostic_code = outcome.failure_code.value
        else:
            disposition = program.disposition
            result_id = outcome.identity
            diagnostic_code = _disposition_code(disposition)
        terminal_ledger = terminal_ledger.append(
            TrialLedgerRecord(
                event_ordinal=len(terminal_ledger.records) + 1,
                trial_ordinal=accepted.trial_ordinal,
                proposal=proposal,
                disposition=disposition,
                evaluation_attempt_id=attempt_id,
                evaluation_source_head=proposal_set.source_head,
                evaluation_source_tree=proposal_set.source_tree,
                dataset_evidence_id=(
                    proposal_set.accepted_generation1_dataset_evidence_id
                ),
                evaluation_id=evaluation_id,
                result_id=result_id,
                terminal_diagnostic_code=diagnostic_code,
                pnl_visible=type(outcome) is Generation2ProgramResult,
                diagnostic_visible=True,
            )
        )

    return Generation2BatchRun(
        proposal_set.identity,
        confirmation_view.identity,
        confirmation_view.dataset_identity,
        proposal_set.accepted_generation1_dataset_evidence_id,
        pre_evaluation_ledger,
        terminal_ledger,
        outcomes,
        analysis,
    )


def _validate_run_bindings(
    proposal_set: Generation2ProposalSet,
    terminal_ledger: TrialLedger,
    confirmation_view: ConfirmationView,
    *,
    expected_source_head: str,
    expected_source_tree: str,
) -> None:
    for value, label in (
        (expected_source_head, "expected source HEAD"),
        (expected_source_tree, "expected source tree"),
    ):
        if (
            type(value) is not str
            or len(value) != 40
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise Generation2AnalysisError(f"{label} must be lowercase 40-hex")
    if (
        proposal_set.source_head != expected_source_head
        or proposal_set.source_tree != expected_source_tree
    ):
        raise Generation2AnalysisError("G2 proposal-set source binding disagrees")
    if any(record.generation == 2 for record in terminal_ledger.records):
        raise Generation2AnalysisError("G2 replay is forbidden after any G2 event")
    if terminal_ledger.evaluated_trial_counts_by_generation[1] != 0:
        raise Generation2AnalysisError(
            "G2 replay is forbidden after any counted attempt"
        )
    if (
        terminal_ledger.ledger_id
        != proposal_set.accepted_generation1_terminal_ledger_id
    ):
        raise Generation2AnalysisError("accepted G1 terminal-ledger binding disagrees")
    if confirmation_view.dataset_identity != (
        proposal_set.accepted_generation1_dataset_identity
    ):
        raise Generation2AnalysisError(
            "confirmation view is not bound to the accepted G1 dataset"
        )
    _require_uuid5(
        proposal_set.accepted_generation1_dataset_evidence_id,
        "accepted G1 dataset evidence identity",
    )


def _prepare_ledger(
    proposal_set: Generation2ProposalSet,
    prior_ledger: TrialLedger,
) -> tuple[TrialLedger, dict[str, int]]:
    next_ordinal = max(
        (record.trial_ordinal for record in prior_ledger.records), default=0
    )
    prepared = prior_ledger
    ordinals: dict[str, int] = {}
    for proposal in proposal_set.proposals:
        next_ordinal += 1
        prepared = prepared.append(
            TrialLedgerRecord(
                event_ordinal=len(prepared.records) + 1,
                trial_ordinal=next_ordinal,
                proposal=proposal,
                disposition=TrialDisposition.ACCEPTED_FOR_EVALUATION,
            )
        )
        ordinals[proposal.proposal_id] = next_ordinal
    return prepared, ordinals


def _attempt_binding(
    proposal_set: Generation2ProposalSet,
    proposal: ResearchProposal,
    trial_ordinal: int,
    confirmation_view: ConfirmationView,
) -> tuple[str, str]:
    material = (
        proposal_set.identity,
        proposal.proposal_id,
        proposal.semantic_program_id,
        trial_ordinal,
        confirmation_view.identity,
        confirmation_view.dataset_identity,
        proposal_set.accepted_generation1_dataset_evidence_id,
        proposal_set.source_head,
        proposal_set.source_tree,
    )
    attempt_id = semantic_identity("generation2-evaluation-attempt", material)
    evaluation_id = semantic_identity(
        "generation2-evaluation", (attempt_id, proposal_set.identity)
    )
    return attempt_id, evaluation_id


def _find_accepted_event(ledger: TrialLedger, proposal_id: str) -> TrialLedgerRecord:
    for record in ledger.records:
        if (
            record.proposal_id == proposal_id
            and record.disposition is TrialDisposition.ACCEPTED_FOR_EVALUATION
        ):
            return record
    raise Generation2AnalysisError("missing pre-evaluation acceptance event")


def _validate_complete_proposal_set(proposal_set: Generation2ProposalSet) -> None:
    if type(proposal_set) is not Generation2ProposalSet:
        raise Generation2AnalysisError("a frozen Generation-2 proposal set is required")
    if (
        type(proposal_set.proposals) is not tuple
        or len(proposal_set.proposals) != 6
        or any(
            type(proposal) is not ResearchProposal
            for proposal in proposal_set.proposals
        )
        or len({proposal.proposal_id for proposal in proposal_set.proposals}) != 6
        or len({proposal.semantic_program_id for proposal in proposal_set.proposals})
        != 6
        or any(proposal.generation != 2 for proposal in proposal_set.proposals)
    ):
        raise Generation2AnalysisError(
            "proposal set must contain the exact ordered six-program G2 population"
        )
    for value, label in (
        (proposal_set.identity, "proposal-set identity"),
        (
            proposal_set.accepted_generation1_terminal_ledger_id,
            "accepted G1 terminal-ledger identity",
        ),
        (
            proposal_set.accepted_generation1_dataset_identity,
            "accepted G1 dataset identity",
        ),
        (
            proposal_set.accepted_generation1_proposal_set_id,
            "accepted G1 proposal-set identity",
        ),
        (
            proposal_set.accepted_generation1_analysis_id,
            "accepted G1 analysis identity",
        ),
        (
            proposal_set.accepted_generation1_dataset_evidence_id,
            "accepted G1 dataset evidence identity",
        ),
    ):
        _require_uuid5(value, label)
    if (
        proposal_set.max_evaluated != 16
        or proposal_set.evaluated_candidate_count != 6
        or proposal_set.confirmation_results_visible is not False
        or proposal_set.final_holdout_sealed is not True
    ):
        raise Generation2AnalysisError("G2 proposal-set freeze bindings disagree")


def _validate_result(
    proposal: ResearchProposal,
    result: Generation2ProgramResult,
    expected_dataset_identity: str,
    expected_confirmation_view_identity: str,
) -> None:
    if (
        result.proposal_id != proposal.proposal_id
        or result.semantic_program_id != proposal.semantic_program_id
        or result.dataset_identity != expected_dataset_identity
        or result.confirmation_view_identity != expected_confirmation_view_identity
    ):
        raise Generation2AnalysisError(
            "completed G2 result panel is incomplete or misbound"
        )


def _summarize_program(
    proposal: ResearchProposal,
    result: Generation2ProgramResult,
) -> Generation2ProgramAnalysis:
    return Generation2ProgramAnalysis(
        proposal.proposal_id,
        proposal.semantic_program_id,
        result.identity,
        TrialDisposition.CONFIRMATION_REJECTED,
        _summarize_economics(result.cells, stress=False),
        _summarize_economics(result.cells, stress=True),
        False,
    )


def _summarize_economics(
    cells: tuple[CellEvidence, ...], *, stress: bool
) -> ConfirmationSummary:
    def metrics(cell: CellEvidence) -> Metrics:
        return cell.stress if stress else cell.base

    continuous_cells = tuple(cell for cell in cells if cell.regime == _CONTINUOUS_LABEL)
    year_cells = tuple(cell for cell in cells if cell.regime in _ANNUAL_LABELS)
    if tuple(cell.symbol for cell in continuous_cells) != UNIVERSE or tuple(
        (cell.symbol, cell.regime) for cell in year_cells
    ) != tuple((symbol, year) for symbol in UNIVERSE for year in _ANNUAL_LABELS):
        raise Generation2AnalysisError(
            "summary requires all 8 continuous and 16 asset/year cells"
        )

    continuous_returns = tuple(
        (cell.symbol, metrics(cell).total_return) for cell in continuous_cells
    )
    year_returns = tuple(
        (cell.symbol, cell.regime, metrics(cell).total_return) for cell in year_cells
    )
    turnovers = tuple(
        (cell.symbol, cell.regime, metrics(cell).turnover) for cell in year_cells
    )
    with localcontext(CONTEXT):
        continuous_values = tuple(value for _, value in continuous_returns)
        return_2022 = tuple(
            metrics(cell).total_return for cell in year_cells if cell.regime == "2022"
        )
        return_2023 = tuple(
            metrics(cell).total_return for cell in year_cells if cell.regime == "2023"
        )
        return ConfirmationSummary(
            continuous_symbol_returns=continuous_returns,
            annual_asset_year_returns=year_returns,
            median_2022_return=median(return_2022),
            median_2023_return=median(return_2023),
            median_continuous_return=median(continuous_values),
            minimum_continuous_return=min(continuous_values),
            positive_continuous_symbols=sum(value > 0 for value in continuous_values),
            positive_asset_year_cells=sum(value > 0 for _, _, value in year_returns),
            worst_continuous_drawdown=max(
                metrics(cell).maximum_drawdown for cell in continuous_cells
            ),
            annual_asset_year_turnovers=turnovers,
            median_annual_turnover=median(
                metrics(cell).turnover for cell in year_cells
            ),
        )


def _dominates(
    left: ConfirmationSummary | None,
    right: ConfirmationSummary | None,
) -> bool:
    if left is None or right is None:
        return False
    left_maximize = (
        left.median_continuous_return,
        left.minimum_continuous_return,
        left.positive_continuous_symbols,
        left.positive_asset_year_cells,
    )
    right_maximize = (
        right.median_continuous_return,
        right.minimum_continuous_return,
        right.positive_continuous_symbols,
        right.positive_asset_year_cells,
    )
    left_minimize = (
        left.worst_continuous_drawdown,
        left.median_annual_turnover,
    )
    right_minimize = (
        right.worst_continuous_drawdown,
        right.median_annual_turnover,
    )
    no_worse = all(a >= b for a, b in zip(left_maximize, right_maximize, strict=True))
    no_worse = no_worse and all(
        a <= b for a, b in zip(left_minimize, right_minimize, strict=True)
    )
    strictly_better = any(
        a > b for a, b in zip(left_maximize, right_maximize, strict=True)
    ) or any(a < b for a, b in zip(left_minimize, right_minimize, strict=True))
    return no_worse and strictly_better


def _confirmation_gates(summary: ConfirmationSummary) -> bool:
    return (
        summary.median_2022_return > 0
        and summary.median_2023_return > 0
        and summary.median_continuous_return > 0
        and summary.positive_continuous_symbols >= 5
        and summary.positive_asset_year_cells >= 9
        and summary.minimum_continuous_return > Decimal("-0.10")
    )


def _disposition_code(disposition: TrialDisposition) -> str:
    return {
        TrialDisposition.CONFIRMATION_PASSED: "G2_CONFIRMATION_PASSED",
        TrialDisposition.CONFIRMATION_REJECTED: "G2_CONFIRMATION_REJECTED",
    }[disposition]


def _require_uuid5(value: object, label: str) -> None:
    try:
        if type(value) is not str:
            raise ValueError
        parsed = UUID(value)
        if str(parsed) != value or parsed.version != 5:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise Generation2AnalysisError(f"{label} must be a canonical UUID5") from None
