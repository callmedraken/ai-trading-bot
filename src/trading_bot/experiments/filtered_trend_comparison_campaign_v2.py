"""Frozen, in-memory replay and selection for filtered-trend comparison v2."""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from trading_bot.domain.market import Bar
from trading_bot.experiments.filtered_trend_campaign import (
    AggregateSummary,
    CellEvidence,
    Regime,
    _evaluate_cell,
    regime_plan,
)
from trading_bot.experiments.filtered_trend_campaign import (
    campaign_context as _v1_campaign_context,
)
from trading_bot.experiments.filtered_trend_campaign import (
    frozen_context as _v1_frozen_context,
)
from trading_bot.experiments.filtered_trend_campaign import (
    semantic_identity as _v1_semantic_identity,
)
from trading_bot.experiments.filtered_trend_campaign import (
    summarize as _v1_summarize,
)
from trading_bot.experiments.filtered_trend_comparison_v2 import (
    CANDIDATES,
    Candidate,
    signal_series,
)
from trading_bot.experiments.filtered_trend_data import (
    MultiAssetDataset,
)
from trading_bot.experiments.filtered_trend_strategies import StrategyConfig

QUALIFICATION_POLICY = "comparison-v2/qualification-v1"
_SHORTLIST_POLICY = "qualified-fixed-order-sma200-mom252/v1"
_PRIOR_CAMPAIGN_ID = "48ae05d5-ede1-5461-9da9-b5d7744cefad"
_BASE_CONFIG = StrategyConfig("BASE_MA", 35, 50, "none")
_NEW_YORK = ZoneInfo("America/New_York")

_HIGHER_IS_BETTER = (
    "positive_regime_cells",
    "minimum_regime_return",
    "median_regime_return",
    "positive_continuous_symbols",
    "minimum_continuous_return",
    "median_continuous_return",
)
_LOWER_IS_BETTER = (
    "negative_regime_cells",
    "worst_regime_drawdown",
    "median_regime_drawdown",
    "median_turnover",
    "worst_continuous_drawdown",
)
_COUNT_FIELDS = frozenset(
    {
        "positive_regime_cells",
        "negative_regime_cells",
        "positive_continuous_symbols",
    }
)
_NONNEGATIVE_DECIMAL_FIELDS = frozenset(
    {
        "worst_regime_drawdown",
        "median_regime_drawdown",
        "median_turnover",
        "worst_continuous_drawdown",
    }
)
if set(_HIGHER_IS_BETTER) | set(_LOWER_IS_BETTER) != {
    item.name for item in fields(AggregateSummary)
}:
    raise RuntimeError("comparison v2 qualification policy must cover every metric")


@dataclass(frozen=True, slots=True)
class ComparisonSummary:
    """One frozen candidate's base and stress aggregate evidence."""

    candidate: Candidate
    candidate_id: str
    base: AggregateSummary
    stress: AggregateSummary


def semantic_identity(kind: str, value: object) -> str:
    """Create a stable UUID5 using v1 typed framing and the v2 kind namespace."""

    if type(kind) is not str or not kind:
        raise TypeError("identity kind must be a nonempty string")
    return _v1_semantic_identity("comparison-v2/" + kind, value)


def candidate_identity(campaign_id: str, candidate: Candidate) -> str:
    """Return the stable candidate UUID5 bound to a v2 campaign identity."""

    if not isinstance(candidate, Candidate):
        raise TypeError("candidate must be a Candidate")
    if type(campaign_id) is not str:
        raise ValueError("campaign_id must be a canonical UUID5 identity")
    try:
        campaign_uuid = UUID(campaign_id)
    except (AttributeError, TypeError, ValueError):
        raise ValueError("campaign_id must be a UUID5 identity") from None
    if campaign_uuid.version != 5 or str(campaign_uuid) != campaign_id:
        raise ValueError("campaign_id must be a canonical UUID5 identity")
    return semantic_identity("candidate", (campaign_id, candidate.value))


def frozen_context(
    source_head: str,
    source_tree: str,
    dataset_id: str,
    price_basis: str,
    dataset_provenance: list[dict],
) -> dict:
    """Return the canonical v2 research context without inspecting results."""

    context = _v1_frozen_context(
        source_head,
        source_tree,
        dataset_id,
        price_basis,
        dataset_provenance,
    )
    context = dict(context)
    context.update(
        {
            "schema": "filtered-trend-comparison-campaign/v2",
            "grid": [candidate.value for candidate in CANDIDATES],
            "qualification_policy": QUALIFICATION_POLICY,
            "shortlist_policy": _SHORTLIST_POLICY,
            "neighbor_policy": None,
            "prior_configurations": 30,
            "comparison_configurations": 3,
            "prior_campaign_id": _PRIOR_CAMPAIGN_ID,
            "reused_history": True,
        }
    )
    return context


def campaign_identity(context: dict) -> str:
    """Return the stable UUID5 identity for a v2 semantic context."""

    if type(context) is not dict:
        raise TypeError("campaign context must be a dict")
    return semantic_identity("campaign", context)


def select_candidate(summaries: tuple[ComparisonSummary, ...]) -> str:
    """Apply the frozen all-metrics base/stress qualification policy."""

    if type(summaries) is not tuple or len(summaries) != len(CANDIDATES):
        raise ValueError("all three ordered comparison summaries are required")
    if any(type(item) is not ComparisonSummary for item in summaries):
        raise TypeError("summaries must contain ComparisonSummary values")
    if any(type(item.candidate) is not Candidate for item in summaries):
        raise TypeError("summary candidates must be Candidate values")
    if tuple(item.candidate for item in summaries) != CANDIDATES:
        raise ValueError("summaries must use the frozen candidate order")
    if len({item.candidate_id for item in summaries}) != len(CANDIDATES):
        raise ValueError("candidate identities must be distinct")
    for item in summaries:
        _require_canonical_uuid5(item.candidate_id, "candidate_id")
        _validate_aggregate(item.base)
        _validate_aggregate(item.stress)

    control = summaries[0]
    for candidate in summaries[1:]:
        if qualifies_candidate(candidate, control):
            return candidate.candidate.value
    return "NONE_QUALIFIES"


def qualifies_candidate(
    challenger: ComparisonSummary,
    control: ComparisonSummary,
) -> bool:
    """Return whether one challenger meets the frozen base/stress gate."""

    if (
        type(challenger) is not ComparisonSummary
        or type(control) is not ComparisonSummary
    ):
        raise TypeError("candidate and control must be ComparisonSummary values")
    if control.candidate is not Candidate.BASE_MA35_50_V1:
        raise ValueError("qualification control must be BASE_MA35_50_V1")
    if (
        type(challenger.candidate) is not Candidate
        or challenger.candidate not in CANDIDATES[1:]
    ):
        raise ValueError("qualification challenger is not a frozen comparison arm")
    _require_canonical_uuid5(challenger.candidate_id, "candidate_id")
    _require_canonical_uuid5(control.candidate_id, "candidate_id")
    if challenger.candidate_id == control.candidate_id:
        raise ValueError("candidate identities must be distinct")
    _validate_aggregate(challenger.base)
    _validate_aggregate(challenger.stress)
    _validate_aggregate(control.base)
    _validate_aggregate(control.stress)
    return (
        _no_worse(challenger.base, control.base)
        and _no_worse(challenger.stress, control.stress)
        and _strictly_better(challenger.stress, control.stress)
    )


def run_campaign(
    dataset: MultiAssetDataset,
    source_head: str,
    source_tree: str,
) -> tuple[dict, tuple[CellEvidence, ...], tuple[ComparisonSummary, ...]]:
    """Run only the fixed v2 comparison in memory against an admitted dataset."""

    if type(dataset) is not MultiAssetDataset:
        raise TypeError("exact validated MultiAssetDataset required")
    prior_context = _v1_campaign_context(dataset, source_head, source_tree)
    context = frozen_context(
        source_head,
        source_tree,
        str(dataset.identity),
        dataset.price_basis,
        prior_context["dataset_provenance"],
    )
    campaign_id = campaign_identity(context)

    all_cells: list[CellEvidence] = []
    summaries: list[ComparisonSummary] = []
    regimes = regime_plan()
    for candidate in CANDIDATES:
        candidate_id = candidate_identity(campaign_id, candidate)
        candidate_cells: list[CellEvidence] = []
        for item in dataset.datasets:
            states = signal_series(candidate, item.bars)
            if type(states) is not tuple or len(states) != len(item.bars):
                raise ValueError("candidate signal series is incomplete")
            if any(state not in (None, "BUY", "SELL", "HOLD") for state in states):
                raise ValueError("candidate signal series contains an invalid state")
            for regime in regimes:
                execution_indices = _regime_indices(item.bars, regime)
                if not execution_indices:
                    raise ValueError("candidate regime contains no sessions")
                if execution_indices[0] == 0 or any(
                    states[index - 1] is None for index in execution_indices
                ):
                    raise ValueError(
                        "candidate warmup does not cover every prior-close signal"
                    )
                candidate_cells.append(
                    _evaluate_cell(
                        item.bars,
                        _BASE_CONFIG,
                        regime,
                        candidate_id,
                        prepared_states=cast(tuple[str, ...], states),
                    )
                )
        owned_cells = tuple(candidate_cells)
        all_cells.extend(owned_cells)
        summaries.append(
            ComparisonSummary(
                candidate,
                candidate_id,
                _v1_summarize(owned_cells),
                _v1_summarize(owned_cells, stress=True),
            )
        )
    return context, tuple(all_cells), tuple(summaries)


def _regime_indices(bars: tuple[Bar, ...], regime: Regime) -> tuple[int, ...]:
    return tuple(
        index
        for index, bar in enumerate(bars)
        if regime.start <= bar.timestamp.astimezone(_NEW_YORK).date() < regime.end
    )


def _validate_aggregate(summary: AggregateSummary) -> None:
    if type(summary) is not AggregateSummary:
        raise TypeError("aggregate evidence must be an AggregateSummary")
    for item in fields(AggregateSummary):
        value = getattr(summary, item.name)
        if item.name in _COUNT_FIELDS:
            maximum = 8 if item.name == "positive_continuous_symbols" else 40
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError("aggregate counts must be nonnegative integers")
        elif type(value) is not Decimal or not value.is_finite():
            raise ValueError("aggregate metrics must be finite Decimals")
        elif item.name in _NONNEGATIVE_DECIMAL_FIELDS and value < 0:
            raise ValueError("drawdown and turnover metrics must be nonnegative")
        elif (
            item.name in _NONNEGATIVE_DECIMAL_FIELDS - {"median_turnover"} and value > 1
        ):
            raise ValueError("aggregate drawdowns must not exceed one")
        elif (
            item.name
            in {
                "minimum_regime_return",
                "median_regime_return",
                "minimum_continuous_return",
                "median_continuous_return",
            }
            and value < -1
        ):
            raise ValueError("long-only aggregate returns cannot be below negative one")
    if summary.positive_regime_cells + summary.negative_regime_cells > 40:
        raise ValueError("annual regime result counts cannot exceed forty")


def _require_canonical_uuid5(value: str, label: str) -> None:
    if type(value) is not str:
        raise ValueError(f"{label} must be a canonical UUID5 identity")
    try:
        parsed = UUID(value)
    except ValueError:
        raise ValueError(f"{label} must be a canonical UUID5 identity") from None
    if parsed.version != 5 or str(parsed) != value:
        raise ValueError(f"{label} must be a canonical UUID5 identity")


def _no_worse(candidate: AggregateSummary, control: AggregateSummary) -> bool:
    return all(
        getattr(candidate, name) >= getattr(control, name) for name in _HIGHER_IS_BETTER
    ) and all(
        getattr(candidate, name) <= getattr(control, name) for name in _LOWER_IS_BETTER
    )


def _strictly_better(candidate: AggregateSummary, control: AggregateSummary) -> bool:
    return any(
        getattr(candidate, name) > getattr(control, name) for name in _HIGHER_IS_BETTER
    ) or any(
        getattr(candidate, name) < getattr(control, name) for name in _LOWER_IS_BETTER
    )
