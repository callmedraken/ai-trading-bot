"""Deterministic whole-panel analysis and in-memory G1 ledger orchestration.

This module has no provider, AI, credential, broker, filesystem, or operator
surface. Its public batch runner consumes only an already validated in-memory
discovery view and frozen proposal set.
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
from trading_bot.experiments.ai_strategy_discovery_generation1 import (
    DiscoveryView,
    Generation1ProgramResult,
    evaluate_generation1_program,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_plan import (
    Generation1ProposalSet,
)
from trading_bot.experiments.filtered_trend_campaign import (
    CONTEXT,
    UNIVERSE,
    CellEvidence,
    Metrics,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import PRICE_BASIS

_ANNUAL_LABELS = ("2019", "2020", "2021")
_CONTINUOUS_LABEL = "continuous"
_EXPECTED_CELL_ORDER = tuple(
    (symbol, label)
    for symbol in UNIVERSE
    for label in (*_ANNUAL_LABELS, _CONTINUOUS_LABEL)
)
_RESULT_FAILURE_CODE = "G1_DETERMINISTIC_EVALUATION_FAILED"
ZERO_EFFECT_COUNTER_NAMES = (
    "ai_service_calls",
    "credential_reads",
    "provider_network_calls",
    "robinhood_calls",
    "broker_calls",
    "order_effects",
    "production_state_reads",
    "production_state_writes",
    "final_holdout_accesses",
    "strategy_promotions",
)


class Generation1AnalysisError(ValueError):
    """Incomplete, inconsistent, or misbound G1 analysis input."""


class Generation1FailureCode(StrEnum):
    """Stable failure classifications that deliberately omit exception prose."""

    DETERMINISTIC_EVALUATION_VALUE_ERROR = _RESULT_FAILURE_CODE


@dataclass(frozen=True, slots=True)
class Generation1EvaluationFailure:
    """One deterministic evaluator ValueError bound to a single attempted trial."""

    proposal_id: str
    semantic_program_id: str
    dataset_identity: str
    attempt_id: str
    evaluation_id: str
    failure_code: Generation1FailureCode
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
        if type(self.failure_code) is not Generation1FailureCode:
            raise Generation1AnalysisError("failure code must be a declared value")
        object.__setattr__(
            self,
            "identity",
            semantic_identity(
                "generation1-evaluation-failure",
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


Generation1Outcome = Generation1ProgramResult | Generation1EvaluationFailure


@dataclass(frozen=True, slots=True)
class EconomicSummary:
    """Base or stress diagnostics for a complete 8-symbol G1 result panel."""

    continuous_symbol_returns: tuple[tuple[str, Decimal], ...]
    annual_asset_year_returns: tuple[tuple[str, str, Decimal], ...]
    median_continuous_return: Decimal
    minimum_continuous_return: Decimal
    positive_continuous_symbols: int
    positive_asset_year_cells: int
    worst_continuous_drawdown: Decimal
    annual_asset_year_turnovers: tuple[tuple[str, str, Decimal], ...]
    median_annual_turnover: Decimal
    discovery_cell_buy_entry_count: int
    discovery_cell_fill_count: int
    discovery_cell_closed_trade_count: int
    median_continuous_time_invested: Decimal
    median_continuous_buy_and_hold_return: Decimal
    largest_symbol_absolute_return_share: Decimal
    largest_year_absolute_return_share: Decimal

    def identity_material(self) -> tuple[object, ...]:
        return (
            self.continuous_symbol_returns,
            self.annual_asset_year_returns,
            self.median_continuous_return,
            self.minimum_continuous_return,
            self.positive_continuous_symbols,
            self.positive_asset_year_cells,
            self.worst_continuous_drawdown,
            self.annual_asset_year_turnovers,
            self.median_annual_turnover,
            self.discovery_cell_buy_entry_count,
            self.discovery_cell_fill_count,
            self.discovery_cell_closed_trade_count,
            self.median_continuous_time_invested,
            self.median_continuous_buy_and_hold_return,
            self.largest_symbol_absolute_return_share,
            self.largest_year_absolute_return_share,
        )


@dataclass(frozen=True, slots=True)
class ProgramAnalysis:
    """Descriptive decision for one ordered frozen proposal."""

    proposal_id: str
    semantic_program_id: str
    outcome_identity: str
    disposition: TrialDisposition
    base: EconomicSummary | None
    stress: EconomicSummary | None
    nondominated: bool
    failure_code: Generation1FailureCode | None = None

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
class Generation1BatchAnalysis:
    """Complete ordered analysis; it grants no lifecycle or promotion state."""

    proposal_set_identity: str
    dataset_identity: str
    programs: tuple[ProgramAnalysis, ...]
    pareto_front_proposal_ids: tuple[str, ...]
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        _require_uuid5(self.proposal_set_identity, "proposal-set identity")
        _require_uuid5(self.dataset_identity, "dataset identity")
        if type(self.programs) is not tuple or any(
            type(item) is not ProgramAnalysis for item in self.programs
        ):
            raise Generation1AnalysisError(
                "analysis requires ordered program summaries"
            )
        if type(self.pareto_front_proposal_ids) is not tuple or any(
            type(item) is not str for item in self.pareto_front_proposal_ids
        ):
            raise Generation1AnalysisError(
                "Pareto frontier requires ordered proposal ids"
            )
        if len(set(self.pareto_front_proposal_ids)) != len(
            self.pareto_front_proposal_ids
        ):
            raise Generation1AnalysisError(
                "Pareto frontier contains duplicate proposals"
            )
        if not set(self.pareto_front_proposal_ids) <= {
            item.proposal_id for item in self.programs if item.stress is not None
        }:
            raise Generation1AnalysisError(
                "Pareto frontier contains an ineligible proposal"
            )
        object.__setattr__(
            self,
            "identity",
            semantic_identity(
                "generation1-whole-panel-analysis",
                (
                    self.proposal_set_identity,
                    self.dataset_identity,
                    tuple(item.identity_material() for item in self.programs),
                    self.pareto_front_proposal_ids,
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class Generation1BatchRun:
    """In-memory run record, including the complete pre-evaluation ledger."""

    proposal_set_identity: str
    discovery_view_identity: str
    dataset_identity: str
    dataset_evidence_id: str
    pre_evaluation_ledger: TrialLedger
    terminal_ledger: TrialLedger
    outcomes: tuple[Generation1Outcome, ...]
    analysis: Generation1BatchAnalysis
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        _require_uuid5(self.proposal_set_identity, "proposal-set identity")
        _require_uuid5(self.discovery_view_identity, "discovery-view identity")
        _require_uuid5(self.dataset_identity, "dataset identity")
        _require_uuid5(self.dataset_evidence_id, "dataset evidence identity")
        if (
            type(self.pre_evaluation_ledger) is not TrialLedger
            or type(self.terminal_ledger) is not TrialLedger
        ):
            raise Generation1AnalysisError("batch run requires canonical ledgers")
        if type(self.outcomes) is not tuple or any(
            type(item) not in (Generation1ProgramResult, Generation1EvaluationFailure)
            for item in self.outcomes
        ):
            raise Generation1AnalysisError(
                "batch run outcomes must be closed typed values"
            )
        if type(self.analysis) is not Generation1BatchAnalysis:
            raise Generation1AnalysisError(
                "batch run requires exact canonical analysis"
            )
        if self.analysis.proposal_set_identity != self.proposal_set_identity:
            raise Generation1AnalysisError(
                "batch analysis proposal-set binding disagrees"
            )
        if self.analysis.dataset_identity != self.dataset_identity:
            raise Generation1AnalysisError("batch analysis dataset binding disagrees")
        if (
            len(self.outcomes) != len(self.analysis.programs)
            or tuple(item.proposal_id for item in self.outcomes)
            != tuple(item.proposal_id for item in self.analysis.programs)
            or tuple(item.identity for item in self.outcomes)
            != tuple(item.outcome_identity for item in self.analysis.programs)
        ):
            raise Generation1AnalysisError(
                "batch outcomes do not match the complete analysis"
            )
        if (
            len(self.terminal_ledger.records)
            != len(self.pre_evaluation_ledger.records) + len(self.outcomes)
            or self.terminal_ledger.records[: len(self.pre_evaluation_ledger.records)]
            != self.pre_evaluation_ledger.records
        ):
            raise Generation1AnalysisError(
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
                type(outcome) is Generation1EvaluationFailure
                and (
                    record.evaluation_attempt_id != outcome.attempt_id
                    or record.evaluation_id != outcome.evaluation_id
                )
            )
            or record.result_id
            != (outcome.identity if type(outcome) is Generation1ProgramResult else None)
            or record.terminal_diagnostic_code
            != (
                outcome.failure_code.value
                if type(outcome) is Generation1EvaluationFailure
                else _disposition_code(program.disposition)
            )
            or record.pnl_visible is not (type(outcome) is Generation1ProgramResult)
            or record.diagnostic_visible is not True
            for record, program, outcome in zip(
                terminal_records, self.analysis.programs, self.outcomes, strict=True
            )
        ):
            raise Generation1AnalysisError(
                "terminal ledger is incomplete or visibility disagrees "
                "with completed outcomes"
            )
        if (
            self.terminal_ledger.evaluated_trial_count
            - self.pre_evaluation_ledger.evaluated_trial_count
            != len(self.outcomes)
        ):
            raise Generation1AnalysisError(
                "each attempted program must count exactly once"
            )
        object.__setattr__(
            self,
            "identity",
            semantic_identity(
                "generation1-in-memory-batch-run",
                (
                    self.proposal_set_identity,
                    self.discovery_view_identity,
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
        """Canonical immutable zero counters for this pure in-memory result."""
        return tuple((name, 0) for name in ZERO_EFFECT_COUNTER_NAMES)

    @property
    def final_holdout_sealed(self) -> bool:
        """G1 analysis exposes no holdout input and retains the sealed boundary."""
        return True


def analyze_generation1_batch(
    proposal_set: Generation1ProposalSet,
    outcomes: tuple[Generation1Outcome, ...],
    *,
    expected_dataset_identity: str,
) -> Generation1BatchAnalysis:
    """Analyze every ordered proposal outcome, rejecting omitted or partial data."""
    if type(proposal_set) is not Generation1ProposalSet:
        raise Generation1AnalysisError("a frozen Generation-1 proposal set is required")
    _require_uuid5(expected_dataset_identity, "expected dataset identity")
    if type(outcomes) is not tuple or any(
        type(item) not in (Generation1ProgramResult, Generation1EvaluationFailure)
        for item in outcomes
    ):
        raise Generation1AnalysisError("outcome type is outside the closed G1 grammar")
    if len(outcomes) != len(proposal_set.proposals):
        raise Generation1AnalysisError(
            "one ordered outcome is required per frozen proposal"
        )
    expected_ids = proposal_set.proposal_identities
    if tuple(item.proposal_id for item in outcomes) != expected_ids:
        raise Generation1AnalysisError(
            "outcomes are missing, duplicated, foreign, or reordered"
        )

    programs: list[ProgramAnalysis] = []
    for proposal, outcome in zip(proposal_set.proposals, outcomes, strict=True):
        if type(outcome) not in (
            Generation1ProgramResult,
            Generation1EvaluationFailure,
        ):
            raise Generation1AnalysisError(
                "outcome type is outside the closed G1 grammar"
            )
        if (
            outcome.semantic_program_id != proposal.semantic_program_id
            or outcome.dataset_identity != expected_dataset_identity
        ):
            raise Generation1AnalysisError(
                "outcome semantic or dataset binding disagrees"
            )
        if type(outcome) is Generation1EvaluationFailure:
            programs.append(
                ProgramAnalysis(
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
        _validate_result(proposal, outcome, expected_dataset_identity)
        programs.append(_summarize_program(proposal, outcome))

    eligible = tuple(
        index for index, item in enumerate(programs) if item.stress is not None
    )
    frontier_indices = tuple(
        index
        for index in eligible
        if not any(
            _dominates(programs[other].stress, programs[index].stress)
            for other in eligible
            if other != index
        )
    )
    frontier = tuple(programs[index].proposal_id for index in frontier_indices)
    frontier_set = set(frontier)

    finalized: list[ProgramAnalysis] = []
    for item in programs:
        if item.stress is None or item.base is None:
            finalized.append(item)
            continue
        zero_trade = (
            item.base.discovery_cell_buy_entry_count == 0
            and item.stress.discovery_cell_buy_entry_count == 0
        )
        nondominated = item.proposal_id in frontier_set
        stress = item.stress
        shortlist_gates = (
            stress.median_continuous_return > 0
            and stress.positive_continuous_symbols >= 5
            and stress.positive_asset_year_cells >= 13
        )
        disposition = (
            TrialDisposition.ZERO_TRADE
            if zero_trade
            else TrialDisposition.SHORTLISTED
            if shortlist_gates and nondominated
            else TrialDisposition.ECONOMICALLY_REJECTED
        )
        finalized.append(
            ProgramAnalysis(
                item.proposal_id,
                item.semantic_program_id,
                item.outcome_identity,
                disposition,
                item.base,
                item.stress,
                nondominated,
            )
        )

    return Generation1BatchAnalysis(
        proposal_set.identity,
        expected_dataset_identity,
        tuple(finalized),
        frontier,
    )


def run_generation1_batch(
    proposal_set: Generation1ProposalSet,
    prior_ledger: TrialLedger,
    discovery_view: DiscoveryView,
    *,
    expected_source_head: str,
    expected_source_tree: str,
    expected_generation0_inventory_id: str,
    expected_foundation_id: str,
    expected_dataset_identity: str,
    dataset_evidence_id: str,
) -> Generation1BatchRun:
    """Evaluate a frozen in-memory batch and append its terminal ledger events.

    `dataset_evidence_id` identifies the accepted A147 source bundle/receipt;
    `expected_dataset_identity` independently binds the dataset carried by the
    bounded `DiscoveryView`. No evaluator callback or persistence/output path is
    accepted here.
    """
    if type(proposal_set) is not Generation1ProposalSet:
        raise Generation1AnalysisError("a frozen Generation-1 proposal set is required")
    if type(prior_ledger) is not TrialLedger:
        raise Generation1AnalysisError("a canonical prior trial ledger is required")
    if type(discovery_view) is not DiscoveryView:
        raise Generation1AnalysisError("a bounded in-memory discovery view is required")
    _validate_run_bindings(
        proposal_set,
        discovery_view,
        expected_source_head=expected_source_head,
        expected_source_tree=expected_source_tree,
        expected_generation0_inventory_id=expected_generation0_inventory_id,
        expected_foundation_id=expected_foundation_id,
        expected_dataset_identity=expected_dataset_identity,
        dataset_evidence_id=dataset_evidence_id,
    )

    pre_evaluation_ledger, trial_ordinals = _prepare_ledger(proposal_set, prior_ledger)
    attempts = {
        proposal.proposal_id: _attempt_binding(
            proposal_set,
            proposal,
            trial_ordinals[proposal.proposal_id],
            discovery_view,
            dataset_evidence_id,
        )
        for proposal in proposal_set.proposals
    }

    outcomes: list[Generation1Outcome] = []
    for proposal in proposal_set.proposals:
        attempt_id, evaluation_id = attempts[proposal.proposal_id]
        try:
            outcome = evaluate_generation1_program(proposal, discovery_view)
        except ValueError:
            outcome = Generation1EvaluationFailure(
                proposal.proposal_id,
                proposal.semantic_program_id,
                expected_dataset_identity,
                attempt_id,
                evaluation_id,
                Generation1FailureCode.DETERMINISTIC_EVALUATION_VALUE_ERROR,
            )
        outcomes.append(outcome)

    typed_outcomes = tuple(outcomes)
    analysis = analyze_generation1_batch(
        proposal_set,
        typed_outcomes,
        expected_dataset_identity=expected_dataset_identity,
    )
    terminal_ledger = pre_evaluation_ledger
    for proposal, program, outcome in zip(
        proposal_set.proposals, analysis.programs, typed_outcomes, strict=True
    ):
        accepted = _find_accepted_event(pre_evaluation_ledger, proposal.proposal_id)
        attempt_id, evaluation_id = attempts[proposal.proposal_id]
        if type(outcome) is Generation1EvaluationFailure:
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
                evaluation_source_head=expected_source_head,
                evaluation_source_tree=expected_source_tree,
                dataset_evidence_id=dataset_evidence_id,
                evaluation_id=evaluation_id,
                result_id=result_id,
                terminal_diagnostic_code=diagnostic_code,
                pnl_visible=type(outcome) is Generation1ProgramResult,
                diagnostic_visible=True,
            )
        )

    return Generation1BatchRun(
        proposal_set.identity,
        discovery_view.identity,
        expected_dataset_identity,
        dataset_evidence_id,
        pre_evaluation_ledger,
        terminal_ledger,
        typed_outcomes,
        analysis,
    )


def _validate_run_bindings(
    proposal_set: Generation1ProposalSet,
    discovery_view: DiscoveryView,
    *,
    expected_source_head: str,
    expected_source_tree: str,
    expected_generation0_inventory_id: str,
    expected_foundation_id: str,
    expected_dataset_identity: str,
    dataset_evidence_id: str,
) -> None:
    for value, label in (
        (expected_generation0_inventory_id, "expected Generation-0 inventory id"),
        (expected_foundation_id, "expected foundation id"),
        (expected_dataset_identity, "expected dataset identity"),
        (dataset_evidence_id, "dataset evidence identity"),
    ):
        _require_uuid5(value, label)
    for value, label in (
        (expected_source_head, "expected source HEAD"),
        (expected_source_tree, "expected source tree"),
    ):
        if (
            type(value) is not str
            or len(value) != 40
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise Generation1AnalysisError(f"{label} must be lowercase 40-hex")
    if (
        proposal_set.source_head != expected_source_head
        or proposal_set.source_tree != expected_source_tree
        or proposal_set.generation0_inventory_id != expected_generation0_inventory_id
        or proposal_set.foundation_id != expected_foundation_id
    ):
        raise Generation1AnalysisError("proposal-set authority binding disagrees")
    if discovery_view.dataset_identity != expected_dataset_identity:
        raise Generation1AnalysisError("discovery-view dataset identity disagrees")
    if (
        discovery_view.price_basis != PRICE_BASIS
        or tuple(item.symbol for item in discovery_view.symbol_bars) != UNIVERSE
    ):
        raise Generation1AnalysisError(
            "discovery view is outside the accepted A147 basis"
        )


def _prepare_ledger(
    proposal_set: Generation1ProposalSet, prior_ledger: TrialLedger
) -> tuple[TrialLedger, dict[str, int]]:
    if prior_ledger.evaluated_trial_count != 0:
        raise Generation1AnalysisError(
            "G1 replay is forbidden after any counted attempt"
        )
    plan_by_id = {proposal.proposal_id: proposal for proposal in proposal_set.proposals}
    plan_by_semantic = {
        proposal.semantic_program_id: proposal.proposal_id
        for proposal in proposal_set.proposals
    }
    pending: dict[str, TrialLedgerRecord] = {}
    pending_order: list[str] = []
    first_semantic_owner: dict[str, str] = {}
    for record in prior_ledger.records:
        if record.generation == 2:
            raise Generation1AnalysisError(
                "Generation-2 history is outside this G1 run"
            )
        if record.disposition is TrialDisposition.ACCEPTED_FOR_EVALUATION:
            proposal = plan_by_id.get(record.proposal_id)
            if proposal is None or record.proposal != proposal:
                raise Generation1AnalysisError(
                    "pending accepted proposals must belong to this frozen G1 set"
                )
            pending[record.proposal_id] = record
            pending_order.append(record.proposal_id)
            semantic_id = record.semantic_program_id
            if semantic_id is not None:
                first_semantic_owner.setdefault(semantic_id, record.proposal_id)
            continue
        if record.disposition is TrialDisposition.DUPLICATE_REJECTED:
            # The canonical ledger already validated this non-counted resend or
            # prose alias. Preserve it without making it a terminal event for a
            # separately accepted frozen proposal.
            continue
        if record.proposal_id in plan_by_id:
            raise Generation1AnalysisError(
                "a frozen proposal already has a terminal ledger event"
            )
        semantic_id = record.semantic_program_id
        if semantic_id is not None:
            first_semantic_owner.setdefault(semantic_id, record.proposal_id)
    for semantic_id, proposal_id in plan_by_semantic.items():
        prior_owner = first_semantic_owner.get(semantic_id)
        if prior_owner is not None and prior_owner != proposal_id:
            raise Generation1AnalysisError(
                "frozen proposal is a duplicate of an earlier semantic program"
            )
    expected_prefix = proposal_set.proposal_identities[: len(pending_order)]
    if tuple(pending_order) != expected_prefix:
        raise Generation1AnalysisError(
            "pending proposal events do not follow frozen set order"
        )

    prepared = prior_ledger
    trial_ordinals = {
        proposal_id: record.trial_ordinal for proposal_id, record in pending.items()
    }
    next_trial_ordinal = max(
        (record.trial_ordinal for record in prepared.records), default=0
    )
    for proposal in proposal_set.proposals[len(pending_order) :]:
        next_trial_ordinal += 1
        prepared = prepared.append(
            TrialLedgerRecord(
                event_ordinal=len(prepared.records) + 1,
                trial_ordinal=next_trial_ordinal,
                proposal=proposal,
                disposition=TrialDisposition.ACCEPTED_FOR_EVALUATION,
            )
        )
        trial_ordinals[proposal.proposal_id] = next_trial_ordinal
    if tuple(trial_ordinals) != proposal_set.proposal_identities:
        raise Generation1AnalysisError(
            "not every frozen proposal is pending for evaluation"
        )
    return prepared, trial_ordinals


def _attempt_binding(
    proposal_set: Generation1ProposalSet,
    proposal: ResearchProposal,
    trial_ordinal: int,
    discovery_view: DiscoveryView,
    dataset_evidence_id: str,
) -> tuple[str, str]:
    material = (
        proposal_set.identity,
        proposal.proposal_id,
        proposal.semantic_program_id,
        trial_ordinal,
        discovery_view.identity,
        discovery_view.dataset_identity,
        dataset_evidence_id,
        proposal_set.source_head,
        proposal_set.source_tree,
    )
    attempt_id = semantic_identity("generation1-evaluation-attempt", material)
    evaluation_id = semantic_identity(
        "generation1-evaluation", (attempt_id, proposal_set.identity)
    )
    return attempt_id, evaluation_id


def _find_accepted_event(ledger: TrialLedger, proposal_id: str) -> TrialLedgerRecord:
    for record in ledger.records:
        if (
            record.proposal_id == proposal_id
            and record.disposition is TrialDisposition.ACCEPTED_FOR_EVALUATION
        ):
            return record
    raise Generation1AnalysisError("missing pre-evaluation acceptance event")


def _validate_result(
    proposal: ResearchProposal,
    result: Generation1ProgramResult,
    expected_dataset_identity: str,
) -> None:
    if (
        result.proposal_id != proposal.proposal_id
        or result.semantic_program_id != proposal.semantic_program_id
        or result.dataset_identity != expected_dataset_identity
        or tuple((cell.symbol, cell.regime) for cell in result.cells)
        != _EXPECTED_CELL_ORDER
        or len(result.cells) != 32
        or any(type(cell) is not CellEvidence for cell in result.cells)
    ):
        raise Generation1AnalysisError(
            "completed result panel is incomplete or misbound"
        )
    for cell in result.cells:
        if cell.regime not in (*_ANNUAL_LABELS, _CONTINUOUS_LABEL):
            raise Generation1AnalysisError("result contains an unsupported G1 period")
        if type(cell.base) is not Metrics or type(cell.stress) is not Metrics:
            raise Generation1AnalysisError(
                "result cells require base and stress metrics"
            )


def _summarize_program(
    proposal: ResearchProposal, result: Generation1ProgramResult
) -> ProgramAnalysis:
    return ProgramAnalysis(
        proposal.proposal_id,
        proposal.semantic_program_id,
        result.identity,
        TrialDisposition.ECONOMICALLY_REJECTED,
        _summarize_economics(result.cells, stress=False),
        _summarize_economics(result.cells, stress=True),
        False,
    )


def _summarize_economics(
    cells: tuple[CellEvidence, ...], *, stress: bool
) -> EconomicSummary:
    def metrics(cell: CellEvidence) -> Metrics:
        return cell.stress if stress else cell.base

    continuous_cells = tuple(cell for cell in cells if cell.regime == _CONTINUOUS_LABEL)
    annual_cells = tuple(cell for cell in cells if cell.regime in _ANNUAL_LABELS)
    if (
        tuple(cell.symbol for cell in continuous_cells) != UNIVERSE
        or len(annual_cells) != 24
    ):
        raise Generation1AnalysisError(
            "summary requires all 8 continuous and 24 annual cells"
        )

    continuous_returns = tuple(
        (cell.symbol, metrics(cell).total_return) for cell in continuous_cells
    )
    annual_returns = tuple(
        (cell.symbol, cell.regime, metrics(cell).total_return) for cell in annual_cells
    )
    annual_turnovers = tuple(
        (cell.symbol, cell.regime, metrics(cell).turnover) for cell in annual_cells
    )
    with localcontext(CONTEXT):
        continuous_values = tuple(value for _, value in continuous_returns)
        annual_values = tuple(value for _, _, value in annual_returns)
        continuous_metrics = tuple(metrics(cell) for cell in continuous_cells)
        annual_metric_values = tuple(metrics(cell) for cell in annual_cells)
        panel_metric_values = tuple(metrics(cell) for cell in cells)
        by_year = tuple(
            sum(
                (abs(value) for symbol, year, value in annual_returns if year == label),
                Decimal(0),
            )
            for label in _ANNUAL_LABELS
        )
        total_absolute_year_return = sum(by_year, Decimal(0))
        max_year_share = (
            max(by_year) / total_absolute_year_return
            if total_absolute_year_return > 0
            else Decimal(0)
        )
        total_absolute_symbol_return = sum(
            (abs(value) for value in continuous_values), Decimal(0)
        )
        max_symbol_share = (
            max(abs(value) for value in continuous_values)
            / total_absolute_symbol_return
            if total_absolute_symbol_return > 0
            else Decimal(0)
        )
        return EconomicSummary(
            continuous_symbol_returns=continuous_returns,
            annual_asset_year_returns=annual_returns,
            median_continuous_return=median(continuous_values),
            minimum_continuous_return=min(continuous_values),
            positive_continuous_symbols=sum(value > 0 for value in continuous_values),
            positive_asset_year_cells=sum(value > 0 for value in annual_values),
            worst_continuous_drawdown=max(
                metric.maximum_drawdown for metric in continuous_metrics
            ),
            annual_asset_year_turnovers=annual_turnovers,
            median_annual_turnover=median(
                metric.turnover for metric in annual_metric_values
            ),
            discovery_cell_buy_entry_count=sum(
                fill.side == "BUY"
                for metric in panel_metric_values
                for fill in metric.fills
            ),
            discovery_cell_fill_count=sum(
                metric.fill_count for metric in panel_metric_values
            ),
            discovery_cell_closed_trade_count=sum(
                metric.closed_trades for metric in panel_metric_values
            ),
            median_continuous_time_invested=median(
                metric.time_invested for metric in continuous_metrics
            ),
            median_continuous_buy_and_hold_return=median(
                (
                    cell.buy_and_hold_stress.total_return
                    if stress
                    else cell.buy_and_hold.total_return
                )
                for cell in continuous_cells
            ),
            largest_symbol_absolute_return_share=max_symbol_share,
            largest_year_absolute_return_share=max_year_share,
        )


def _dominates(left: EconomicSummary | None, right: EconomicSummary | None) -> bool:
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


def _disposition_code(disposition: TrialDisposition) -> str:
    return {
        TrialDisposition.ZERO_TRADE: "G1_ZERO_TRADE",
        TrialDisposition.ECONOMICALLY_REJECTED: "G1_ECONOMICALLY_REJECTED",
        TrialDisposition.SHORTLISTED: "G1_SHORTLISTED_NONDOMINATED",
    }[disposition]


def _require_uuid5(value: object, label: str) -> None:
    try:
        if type(value) is not str:
            raise ValueError
        parsed = UUID(value)
        if str(parsed) != value or parsed.version != 5:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise Generation1AnalysisError(f"{label} must be a canonical UUID5") from None
