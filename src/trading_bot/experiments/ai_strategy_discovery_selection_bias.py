"""Pure source-owned selection-bias analysis for accepted Generation 1 evidence.

This module consumes only the frozen G1 proposal population, its G1-only
terminal ledger, the complete typed G1 result panel, its whole-panel analysis,
and an already bounded in-memory A147 discovery view. It does not replay
signals, read artifacts, acquire data, or expose an operator command.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from trading_bot.domain import Bar
from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    TrialDisposition,
    TrialLedger,
)
from trading_bot.experiments.ai_strategy_discovery_generation1 import (
    DISCOVERY_END_EXCLUSIVE,
    DISCOVERY_START,
    NY,
    DiscoveryView,
    Generation1ProgramResult,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_analysis import (
    ZERO_EFFECT_COUNTER_NAMES,
    Generation1BatchAnalysis,
)
from trading_bot.experiments.ai_strategy_discovery_generation1_plan import (
    Generation1ProposalSet,
)
from trading_bot.experiments.ai_strategy_discovery_selection_equity import (
    BasketReturns,
    aggregate_g1_basket,
    reconstruct_stress_equity,
)
from trading_bot.experiments.ai_strategy_discovery_selection_statistics import (
    CAMPAIGN_EVALUATED_TRIAL_COUNT,
    CAMPAIGN_FAMILYWISE_ALPHA,
    DSR_PASS_THRESHOLD,
    G1_SEARCH_TRIAL_COUNT,
    SearchBenchmark,
    SelectionInference,
    SelectionStatisticsError,
    SharpeStatistics,
    assess_selection_bias,
    g1_search_benchmark,
    summarize_daily_returns,
)
from trading_bot.experiments.filtered_trend_campaign import (
    CellEvidence,
    decimal_text,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import (
    PRICE_BASIS,
    UNIVERSE,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

SELECTION_BIAS_SCHEMA = "ai-strategy-discovery-selection-bias/v1"
SELECTION_BIAS_IDENTITY_VERSION = "ai-strategy-discovery-selection-bias-identity/v1"

# These values identify the already accepted inputs. Tests replace them only
# while assembling fully synthetic typed evidence.
_ACCEPTED_G1_PROPOSAL_SET_ID = "b2b3cadc-c11d-5a7a-be0b-5a2e16b9b39b"
_ACCEPTED_G1_PROPOSAL_SET_SHA256 = (
    "f5998be087f7c70d64300f1ab4f76efd6b3e627c60ebb0dfa145e7605953239e"
)
_ACCEPTED_G1_ANALYSIS_ID = "d5ca081e-7490-5590-921d-10cee373d012"
_ACCEPTED_G1_TERMINAL_LEDGER_ID = "68418f44-7db0-5080-a6bd-a956a928bd4a"

_EXPECTED_G1_DISPOSITION_CODES = {
    TrialDisposition.SHORTLISTED: "G1_SHORTLISTED_NONDOMINATED",
    TrialDisposition.ECONOMICALLY_REJECTED: "G1_ECONOMICALLY_REJECTED",
}


class SelectionBiasError(ValueError):
    """Rejected, incomplete, or source-mismatched selection-bias evidence."""


class SelectionBiasDisposition(StrEnum):
    PASSED = "SELECTION_BIAS_PASSED"
    REJECTED = "SELECTION_BIAS_REJECTED"


@dataclass(frozen=True, slots=True)
class ProgramSelectionBias:
    """Search statistic for one G1 trial and optional shortlisted-candidate gate."""

    proposal_id: str
    semantic_program_id: str
    g1_disposition: TrialDisposition
    result_id: str
    reconstructed_trace_identities: tuple[tuple[str, str], ...]
    basket_return_series_identity: str
    daily_returns: tuple[Decimal, ...]
    statistics: SharpeStatistics
    inference: SelectionInference | None
    selection_bias_disposition: SelectionBiasDisposition | None
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.proposal_id) is not str
            or type(self.semantic_program_id) is not str
        ):
            raise SelectionBiasError("G1 program identities are invalid")
        if type(self.g1_disposition) is not TrialDisposition:
            raise SelectionBiasError("G1 terminal disposition is invalid")
        if self.g1_disposition not in _EXPECTED_G1_DISPOSITION_CODES:
            raise SelectionBiasError(
                "selection result contains a nonterminal G1 disposition"
            )
        if (
            type(self.result_id) is not str
            or type(self.basket_return_series_identity) is not str
        ):
            raise SelectionBiasError("G1 result or basket identity is invalid")
        if (
            type(self.reconstructed_trace_identities) is not tuple
            or tuple(symbol for symbol, _ in self.reconstructed_trace_identities)
            != UNIVERSE
            or any(
                type(identity) is not str or not identity
                for _, identity in self.reconstructed_trace_identities
            )
        ):
            raise SelectionBiasError("G1 reconstructed trace evidence is incomplete")
        if type(self.statistics) is not SharpeStatistics:
            raise SelectionBiasError("G1 Sharpe statistics are invalid")
        if (
            type(self.daily_returns) is not tuple
            or len(self.daily_returns) != self.statistics.observation_count
            or any(
                type(value) is not Decimal or not value.is_finite()
                for value in self.daily_returns
            )
        ):
            raise SelectionBiasError("G1 Sharpe input series is incomplete")
        try:
            input_statistics = summarize_daily_returns(self.daily_returns)
        except (SelectionStatisticsError, ValueError, TypeError):
            raise SelectionBiasError("G1 Sharpe input series is invalid") from None
        if input_statistics.identity != self.statistics.identity:
            raise SelectionBiasError(
                "serialized returns do not match Sharpe input identity"
            )
        shortlisted = self.g1_disposition is TrialDisposition.SHORTLISTED
        if shortlisted != (type(self.inference) is SelectionInference):
            raise SelectionBiasError("selection inference eligibility disagrees")
        if shortlisted != (
            type(self.selection_bias_disposition) is SelectionBiasDisposition
        ):
            raise SelectionBiasError("selection disposition eligibility disagrees")
        if shortlisted and (
            self.inference.statistics_identity != self.statistics.identity
            or self.selection_bias_disposition
            is not (
                SelectionBiasDisposition.PASSED
                if self.inference.passed
                else SelectionBiasDisposition.REJECTED
            )
        ):
            raise SelectionBiasError(
                "selection disposition does not bind candidate inference"
            )
        object.__setattr__(
            self,
            "identity",
            semantic_identity(
                "selection-bias-program",
                self.to_dict(include_identity=False),
            ),
        )

    def to_dict(self, *, include_identity: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "basket_return_series_identity": self.basket_return_series_identity,
            "daily_returns": [decimal_text(value) for value in self.daily_returns],
            "g1_disposition": self.g1_disposition.value,
            "inference": None if self.inference is None else self.inference.to_dict(),
            "proposal_id": self.proposal_id,
            "reconstructed_trace_identities": [
                {"symbol": symbol, "trace_identity": trace_identity}
                for symbol, trace_identity in self.reconstructed_trace_identities
            ],
            "result_id": self.result_id,
            "selection_bias_disposition": (
                None
                if self.selection_bias_disposition is None
                else self.selection_bias_disposition.value
            ),
            "semantic_program_id": self.semantic_program_id,
            "statistics": self.statistics.to_dict(),
        }
        if include_identity:
            value["identity"] = self.identity
        return value


@dataclass(frozen=True, slots=True)
class SelectionBiasReport:
    """Canonical in-memory result for the exact accepted G1 search population."""

    source_head: str
    source_tree: str
    accepted_g1_source_head: str
    accepted_g1_source_tree: str
    proposal_set_identity: str
    proposal_set_sha256: str
    analysis_identity: str
    terminal_ledger_identity: str
    dataset_identity: str
    dataset_evidence_identity: str
    eligible_shortlisted_proposal_ids: tuple[str, ...]
    programs: tuple[ProgramSelectionBias, ...]
    search_benchmark: SearchBenchmark
    identity: str = field(init=False)

    schema: ClassVar[str] = SELECTION_BIAS_SCHEMA

    def __post_init__(self) -> None:
        for value in (
            self.source_head,
            self.source_tree,
            self.accepted_g1_source_head,
            self.accepted_g1_source_tree,
        ):
            _require_git_identity(value)
        for value in (
            self.proposal_set_identity,
            self.analysis_identity,
            self.terminal_ledger_identity,
            self.dataset_identity,
            self.dataset_evidence_identity,
        ):
            _require_identity_text(value)
        _require_sha256(self.proposal_set_sha256)
        if (
            type(self.eligible_shortlisted_proposal_ids) is not tuple
            or len(self.eligible_shortlisted_proposal_ids) != 12
            or any(
                type(item) is not str for item in self.eligible_shortlisted_proposal_ids
            )
        ):
            raise SelectionBiasError(
                "eligible G1 shortlist is not the exact 12-program set"
            )
        if (
            type(self.programs) is not tuple
            or len(self.programs) != G1_SEARCH_TRIAL_COUNT
            or any(type(item) is not ProgramSelectionBias for item in self.programs)
        ):
            raise SelectionBiasError(
                "selection-bias result requires the complete G1 population"
            )
        if (
            len({item.proposal_id for item in self.programs}) != G1_SEARCH_TRIAL_COUNT
            or len({item.semantic_program_id for item in self.programs})
            != G1_SEARCH_TRIAL_COUNT
        ):
            raise SelectionBiasError("G1 search population contains duplicate programs")
        if (
            tuple(
                item.proposal_id
                for item in self.programs
                if item.g1_disposition is TrialDisposition.SHORTLISTED
            )
            != self.eligible_shortlisted_proposal_ids
        ):
            raise SelectionBiasError(
                "eligible shortlist does not match ordered G1 analysis"
            )
        if type(self.search_benchmark) is not SearchBenchmark:
            raise SelectionBiasError("complete G1 Sharpe search benchmark is required")
        if self.search_benchmark.trial_count != G1_SEARCH_TRIAL_COUNT:
            raise SelectionBiasError(
                "primary DSR benchmark must retain all 22 G1 trials"
            )
        if self.search_benchmark.population_statistics_identities != tuple(
            item.statistics.identity for item in self.programs
        ):
            raise SelectionBiasError(
                "search benchmark population does not match report programs"
            )
        if any(
            item.inference is not None
            and item.inference.benchmark_identity != self.search_benchmark.identity
            for item in self.programs
        ):
            raise SelectionBiasError(
                "candidate inference is not bound to the report benchmark"
            )
        object.__setattr__(
            self,
            "identity",
            semantic_identity(
                "selection-bias-report",
                self.to_dict(include_identity=False),
            ),
        )

    def to_dict(self, *, include_identity: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "accepted_g1_source": {
                "head": self.accepted_g1_source_head,
                "tree": self.accepted_g1_source_tree,
            },
            "analysis_identity": self.analysis_identity,
            "campaign_trial_count": CAMPAIGN_EVALUATED_TRIAL_COUNT,
            "campaign_version": CAMPAIGN_VERSION,
            "dataset_evidence_identity": self.dataset_evidence_identity,
            "dataset_identity": self.dataset_identity,
            "dsr_threshold": decimal_text(DSR_PASS_THRESHOLD),
            "eligible_shortlisted_proposal_ids": list(
                self.eligible_shortlisted_proposal_ids
            ),
            "effects": {name: 0 for name in ZERO_EFFECT_COUNTER_NAMES},
            "final_holdout_sealed": True,
            "identity_version": SELECTION_BIAS_IDENTITY_VERSION,
            "programs": [item.to_dict() for item in self.programs],
            "proposal_set_identity": self.proposal_set_identity,
            "proposal_set_sha256": self.proposal_set_sha256,
            "schema": self.schema,
            "search_benchmark": self.search_benchmark.to_dict(),
            "source": {"head": self.source_head, "tree": self.source_tree},
            "terminal_ledger_identity": self.terminal_ledger_identity,
            "campaign_alpha": decimal_text(CAMPAIGN_FAMILYWISE_ALPHA),
        }
        if include_identity:
            value["identity"] = self.identity
        return value

    def to_bytes(self) -> bytes:
        """Return canonical bytes without writing or publishing an artifact."""
        return canonical_json_bytes(self.to_dict())

    @property
    def zero_effects(self) -> tuple[tuple[str, int], ...]:
        return tuple((name, 0) for name in ZERO_EFFECT_COUNTER_NAMES)

    @property
    def final_holdout_sealed(self) -> bool:
        return True


def evaluate_generation1_selection_bias(
    proposal_set: Generation1ProposalSet,
    terminal_ledger: TrialLedger,
    analysis: Generation1BatchAnalysis,
    results: tuple[Generation1ProgramResult, ...],
    discovery_view: DiscoveryView,
    *,
    source_head: str,
    source_tree: str,
) -> SelectionBiasReport:
    """Analyze accepted G1 evidence without replaying or reading research artifacts.

    The caller supplies the selection-bias source identity explicitly. This
    callable performs no Git, filesystem, network, provider, broker, or AI work.
    Any accepted-source, chronology, trace, or result-panel mismatch aborts the
    whole call before a report is returned.
    """
    _require_git_identity(source_head)
    _require_git_identity(source_tree)
    _validate_accepted_inputs(
        proposal_set, terminal_ledger, analysis, results, discovery_view
    )

    proposals = proposal_set.proposals
    terminal_records = _g1_terminal_records(
        terminal_ledger,
        proposal_set,
        analysis,
        results,
    )
    evidence_ids = {record.dataset_evidence_id for record in terminal_records}
    if len(evidence_ids) != 1 or None in evidence_ids:
        raise SelectionBiasError("G1 terminal ledger has inconsistent dataset evidence")
    dataset_evidence_identity = next(iter(evidence_ids))
    if type(dataset_evidence_identity) is not str:
        raise SelectionBiasError("G1 dataset evidence identity is invalid")

    scoring_bars = {
        symbol: _scoring_bars(discovery_view.bars_for(symbol)) for symbol in UNIVERSE
    }
    search_programs: list[ProgramSelectionBias] = []
    statistics_population: list[SharpeStatistics] = []
    eligible_ids: list[str] = []
    reconstructed: list[tuple[tuple[str, str], ...]] = []
    baskets: list[BasketReturns] = []

    for proposal, result in zip(proposals, results, strict=True):
        continuous_cells = tuple(
            cell for cell in result.cells if cell.regime == "continuous"
        )
        if (
            len(continuous_cells) != len(UNIVERSE)
            or tuple(cell.symbol for cell in continuous_cells) != UNIVERSE
            or any(type(cell) is not CellEvidence for cell in continuous_cells)
        ):
            raise SelectionBiasError(
                "continuous G1 stress panel is incomplete or misordered"
            )
        sleeves = tuple(
            reconstruct_stress_equity(cell, scoring_bars[cell.symbol])
            for cell in continuous_cells
        )
        if any(sleeve.candidate_id != proposal.proposal_id for sleeve in sleeves):
            raise SelectionBiasError(
                "G1 basket contains an equity sleeve from another program"
            )
        trace_pairs = tuple(
            (sleeve.symbol, sleeve.trace_identity) for sleeve in sleeves
        )
        expected_trace_pairs = tuple(
            (cell.symbol, cell.stress.equity_trace_identity)
            for cell in continuous_cells
        )
        if trace_pairs != expected_trace_pairs:
            raise SelectionBiasError("reconstructed stress equity identity mismatch")
        basket = aggregate_g1_basket(sleeves)
        if (
            type(basket) is not BasketReturns
            or basket.trace_identities != trace_pairs
            or type(basket.daily_returns) is not tuple
            or any(
                type(value) is not Decimal or not value.is_finite()
                for value in basket.daily_returns
            )
        ):
            raise SelectionBiasError("G1 basket return series is inconsistent")
        try:
            statistics = summarize_daily_returns(basket.daily_returns)
        except (SelectionStatisticsError, ValueError, TypeError):
            raise SelectionBiasError(
                "G1 basket Sharpe statistics are invalid"
            ) from None
        if statistics.observation_count != len(basket.daily_returns):
            raise SelectionBiasError(
                "G1 Sharpe observation count disagrees with basket input"
            )
        statistics_population.append(statistics)
        reconstructed.append(trace_pairs)
        baskets.append(basket)

    try:
        benchmark = g1_search_benchmark(tuple(statistics_population))
    except (SelectionStatisticsError, ValueError, TypeError):
        raise SelectionBiasError(
            "complete 22-program G1 search benchmark is invalid"
        ) from None
    if (
        benchmark.trial_count != G1_SEARCH_TRIAL_COUNT
        or benchmark.population_statistics_identities
        != tuple(item.identity for item in statistics_population)
    ):
        raise SelectionBiasError(
            "DSR benchmark did not bind the complete ordered G1 search"
        )

    for index, (proposal, result, program) in enumerate(
        zip(proposals, results, analysis.programs, strict=True)
    ):
        if program.disposition is TrialDisposition.SHORTLISTED:
            eligible_ids.append(proposal.proposal_id)
            try:
                inference = assess_selection_bias(
                    statistics_population[index], benchmark
                )
            except (SelectionStatisticsError, ValueError, TypeError):
                raise SelectionBiasError(
                    "shortlisted G1 candidate inference is invalid"
                ) from None
            if (
                inference.statistics_identity != statistics_population[index].identity
                or inference.benchmark_identity != benchmark.identity
                or inference.campaign_alpha != CAMPAIGN_FAMILYWISE_ALPHA
                or inference.dsr_probability < 0
                or inference.dsr_probability > 1
                or inference.campaign_psr_p_value < 0
                or inference.campaign_psr_p_value > 1
            ):
                raise SelectionBiasError(
                    "selection inference does not bind frozen thresholds"
                )
            passed_by_contract = (
                inference.dsr_probability >= DSR_PASS_THRESHOLD
                and inference.campaign_psr_p_value <= CAMPAIGN_FAMILYWISE_ALPHA
            )
            if inference.passed is not passed_by_contract:
                raise SelectionBiasError(
                    "selection inference disposition disagrees with frozen gate"
                )
            selection_disposition = (
                SelectionBiasDisposition.PASSED
                if passed_by_contract
                else SelectionBiasDisposition.REJECTED
            )
        else:
            inference = None
            selection_disposition = None
        trace_pairs = reconstructed[index]
        basket = baskets[index]
        search_programs.append(
            ProgramSelectionBias(
                proposal_id=proposal.proposal_id,
                semantic_program_id=proposal.semantic_program_id,
                g1_disposition=program.disposition,
                result_id=result.identity,
                reconstructed_trace_identities=trace_pairs,
                basket_return_series_identity=basket.identity,
                daily_returns=basket.daily_returns,
                statistics=statistics_population[index],
                inference=inference,
                selection_bias_disposition=selection_disposition,
            )
        )

    if len(eligible_ids) != 12:
        raise SelectionBiasError(
            "accepted G1 analysis does not contain exactly 12 eligible programs"
        )
    return SelectionBiasReport(
        source_head=source_head,
        source_tree=source_tree,
        accepted_g1_source_head=proposal_set.source_head,
        accepted_g1_source_tree=proposal_set.source_tree,
        proposal_set_identity=proposal_set.identity,
        proposal_set_sha256=hashlib.sha256(proposal_set.to_bytes()).hexdigest(),
        analysis_identity=analysis.identity,
        terminal_ledger_identity=terminal_ledger.ledger_id,
        dataset_identity=discovery_view.dataset_identity,
        dataset_evidence_identity=dataset_evidence_identity,
        eligible_shortlisted_proposal_ids=tuple(eligible_ids),
        programs=tuple(search_programs),
        search_benchmark=benchmark,
    )


def _validate_accepted_inputs(
    proposal_set: Generation1ProposalSet,
    terminal_ledger: TrialLedger,
    analysis: Generation1BatchAnalysis,
    results: tuple[Generation1ProgramResult, ...],
    discovery_view: DiscoveryView,
) -> None:
    if type(proposal_set) is not Generation1ProposalSet:
        raise SelectionBiasError("exact typed accepted G1 proposal set is required")
    if type(terminal_ledger) is not TrialLedger:
        raise SelectionBiasError("exact typed G1 terminal ledger is required")
    if type(analysis) is not Generation1BatchAnalysis:
        raise SelectionBiasError("exact typed G1 analysis is required")
    if type(results) is not tuple or any(
        type(result) is not Generation1ProgramResult for result in results
    ):
        raise SelectionBiasError("only the complete typed G1 result tuple is accepted")
    if type(discovery_view) is not DiscoveryView:
        raise SelectionBiasError("bounded in-memory G1 DiscoveryView is required")

    proposal_sha256 = hashlib.sha256(proposal_set.to_bytes()).hexdigest()
    if (
        proposal_set.identity != _ACCEPTED_G1_PROPOSAL_SET_ID
        or proposal_sha256 != _ACCEPTED_G1_PROPOSAL_SET_SHA256
        or len(proposal_set.proposals) != G1_SEARCH_TRIAL_COUNT
        or not proposal_set.is_complete_population
    ):
        raise SelectionBiasError(
            "proposal set is not the exact accepted 22-program G1 set"
        )
    if (
        analysis.identity != _ACCEPTED_G1_ANALYSIS_ID
        or analysis.proposal_set_identity != proposal_set.identity
        or len(analysis.programs) != G1_SEARCH_TRIAL_COUNT
    ):
        raise SelectionBiasError(
            "analysis is not the exact accepted complete G1 analysis"
        )
    if (
        terminal_ledger.ledger_id != _ACCEPTED_G1_TERMINAL_LEDGER_ID
        or terminal_ledger.evaluated_trial_count != G1_SEARCH_TRIAL_COUNT
        or terminal_ledger.evaluated_trial_counts_by_generation
        != (G1_SEARCH_TRIAL_COUNT, 0)
        or any(record.generation != 1 for record in terminal_ledger.records)
    ):
        raise SelectionBiasError("terminal ledger is not the accepted G1-only ledger")
    if (
        analysis.dataset_identity != discovery_view.dataset_identity
        or discovery_view.price_basis != PRICE_BASIS
        or tuple(item.symbol for item in discovery_view.symbol_bars) != UNIVERSE
    ):
        raise SelectionBiasError(
            "DiscoveryView is outside the accepted A147 G1 dataset"
        )
    if len(results) != G1_SEARCH_TRIAL_COUNT:
        raise SelectionBiasError("all 22 ordered completed G1 results are required")

    proposal_ids = proposal_set.proposal_identities
    semantic_ids = proposal_set.semantic_program_ids
    if (
        tuple(result.proposal_id for result in results) != proposal_ids
        or tuple(result.semantic_program_id for result in results) != semantic_ids
        or tuple(result.dataset_identity for result in results)
        != (discovery_view.dataset_identity,) * G1_SEARCH_TRIAL_COUNT
        or tuple(program.proposal_id for program in analysis.programs) != proposal_ids
        or tuple(program.semantic_program_id for program in analysis.programs)
        != semantic_ids
        or tuple(program.outcome_identity for program in analysis.programs)
        != tuple(result.identity for result in results)
    ):
        raise SelectionBiasError(
            "G1 results and analysis are incomplete, reordered, or mismatched"
        )
    dispositions = tuple(program.disposition for program in analysis.programs)
    if (
        dispositions.count(TrialDisposition.SHORTLISTED) != 12
        or dispositions.count(TrialDisposition.ECONOMICALLY_REJECTED) != 10
        or any(item not in _EXPECTED_G1_DISPOSITION_CODES for item in dispositions)
    ):
        raise SelectionBiasError("accepted G1 terminal dispositions changed")
    if any(
        program.base is None
        or program.stress is None
        or program.failure_code is not None
        for program in analysis.programs
    ):
        raise SelectionBiasError("selection bias requires 22 completed G1 analyses")
    for symbol_data in discovery_view.symbol_bars:
        if any(
            bar.timestamp.astimezone(NY).date() >= DISCOVERY_END_EXCLUSIVE
            for bar in symbol_data.bars
        ):
            raise SelectionBiasError("post-2021 bars are outside the G1 selection view")


def _g1_terminal_records(
    ledger: TrialLedger,
    proposal_set: Generation1ProposalSet,
    analysis: Generation1BatchAnalysis,
    results: tuple[Generation1ProgramResult, ...],
) -> tuple[object, ...]:
    proposals = proposal_set.proposals
    accepted = tuple(
        record
        for record in ledger.records
        if record.disposition is TrialDisposition.ACCEPTED_FOR_EVALUATION
    )
    terminal = tuple(
        record for record in ledger.records if record.evaluation_attempt_id is not None
    )
    if (
        len(accepted) != G1_SEARCH_TRIAL_COUNT
        or tuple(record.proposal_id for record in accepted)
        != tuple(proposal.proposal_id for proposal in proposals)
        or tuple(record.proposal_id for record in terminal)
        != tuple(proposal.proposal_id for proposal in proposals)
    ):
        raise SelectionBiasError(
            "G1 terminal ledger does not bind the complete ordered proposal set"
        )
    for accepted_record, terminal_record, proposal, program, result in zip(
        accepted, terminal, proposals, analysis.programs, results, strict=True
    ):
        if (
            accepted_record.proposal != proposal
            or accepted_record.trial_ordinal != terminal_record.trial_ordinal
            or terminal_record.proposal != proposal
            or terminal_record.disposition is not program.disposition
            or terminal_record.result_id != result.identity
            or terminal_record.dataset_evidence_id is None
            or terminal_record.evaluation_source_head != proposal_set.source_head
            or terminal_record.evaluation_source_tree != proposal_set.source_tree
            or terminal_record.terminal_diagnostic_code
            != _EXPECTED_G1_DISPOSITION_CODES[program.disposition]
            or not terminal_record.pnl_visible
            or not terminal_record.diagnostic_visible
        ):
            raise SelectionBiasError("G1 terminal ledger result bindings disagree")
    return terminal


def _scoring_bars(bars: tuple[Bar, ...]) -> tuple[Bar, ...]:
    scoring = tuple(
        bar
        for bar in bars
        if DISCOVERY_START
        <= bar.timestamp.astimezone(NY).date()
        < DISCOVERY_END_EXCLUSIVE
    )
    if not scoring:
        raise SelectionBiasError("G1 scoring bars must be confined to 2019-2021")
    return scoring


def _require_git_identity(value: object) -> None:
    if (
        type(value) is not str
        or len(value) != 40
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise SelectionBiasError("source HEAD and tree must be lowercase 40-hex")


def _require_identity_text(value: object) -> None:
    if type(value) is not str or not value:
        raise SelectionBiasError("bound identities must be nonempty strings")


def _require_sha256(value: object) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise SelectionBiasError("proposal-set digest must be lowercase SHA-256")
