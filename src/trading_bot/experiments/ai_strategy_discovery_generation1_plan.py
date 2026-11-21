"""Closed, canonical proposal-set contract for the daily Generation-1 search.

The plan stores typed proposals only. It does not acquire data, evaluate a
strategy, or expose a result. A proposal set can represent the complete frozen
22-program vocabulary or a smaller fixture subset, but every included program
must be one of those closed semantics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from uuid import UUID, uuid5

from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    GENERATION_1_MAX_EVALUATED,
    GENERATION_1_MAX_PER_FAMILY,
    AbsoluteMomentumSpec,
    DiscoveryError,
    DonchianBreakoutSpec,
    MomentumGate,
    MovingAverageRule,
    MovingAverageTrendSpec,
    MultiHorizonTrendSpec,
    ProposalKind,
    ProposalSemanticStatus,
    ResearchProposal,
    StrategyFamily,
    StrategySpec,
    TrendVote,
    VisibilityStage,
    VisibleEvidenceClassification,
    VisibleTimePartition,
    compile_generation1_program,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

SCHEMA = "ai-strategy-discovery-generation1-proposal-set/v1"
IDENTITY_VERSION = "ai-strategy-discovery-generation1-proposal-set-identity/v1"
MAX_PROPOSAL_SET_BYTES = 4 * 1024 * 1024

_IDENTITY_NAMESPACE = UUID("45a50f1e-19b9-55f2-9a6c-33045ffebeb0")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_SUPPORTED_FAMILIES = (
    StrategyFamily.MOVING_AVERAGE_TREND,
    StrategyFamily.DONCHIAN_BREAKOUT,
    StrategyFamily.ABSOLUTE_MOMENTUM,
    StrategyFamily.MULTI_HORIZON_TREND,
)
_SUPPORTED_SPEC_TYPES = (
    MovingAverageTrendSpec,
    DonchianBreakoutSpec,
    AbsoluteMomentumSpec,
    MultiHorizonTrendSpec,
)


class Generation1PlanError(ValueError):
    """Malformed, unsupported, or inconsistent Generation-1 proposal plan."""


def frozen_generation1_specs() -> tuple[StrategySpec, ...]:
    """Return the exact ordered 6+6+6+4 closed program vocabulary.

    This pure helper creates no proposals or artifacts and performs no
    evaluation. The returned specifications are the only supported G1
    semantics; remaining campaign budget is intentionally unused.
    """
    pairs = ((35, 50), (55, 100), (50, 200))
    return (
        tuple(
            MovingAverageTrendSpec(fast, slow, MovingAverageRule.BASE_MA)
            for fast, slow in pairs
        )
        + tuple(
            MovingAverageTrendSpec(fast, slow, MovingAverageRule.MA_PERCENT_BAND_010)
            for fast, slow in pairs
        )
        + tuple(
            DonchianBreakoutSpec(fast, slow, channel)
            for fast, slow in pairs
            for channel in (20, 55)
        )
        + tuple(
            AbsoluteMomentumSpec(lookback, gate)
            for lookback in (63, 126, 252)
            for gate in (MomentumGate.NONE, MomentumGate.ABOVE_SMA200)
        )
        + tuple(
            MultiHorizonTrendSpec(horizons, vote)
            for horizons in ((21, 63, 126), (63, 126, 252))
            for vote in (TrendVote.TWO_OF_THREE, TrendVote.THREE_OF_THREE)
        )
    )


@dataclass(frozen=True, slots=True)
class Generation1ProposalSet:
    """Immutable G1 proposal population frozen before any G1 evaluation."""

    campaign_version: str
    generation0_inventory_id: str
    foundation_id: str
    source_head: str
    source_tree: str
    proposals: tuple[ResearchProposal, ...]
    identity: str = field(init=False)
    schema: str = field(default=SCHEMA, init=False)

    def __post_init__(self) -> None:
        if type(self.campaign_version) is not str or (
            self.campaign_version != CAMPAIGN_VERSION
        ):
            raise Generation1PlanError("campaign version is outside the frozen plan")
        _require_uuid5(self.generation0_inventory_id, "Generation-0 inventory id")
        _require_uuid5(self.foundation_id, "campaign foundation id")
        _require_git_id(self.source_head, "source HEAD")
        _require_git_id(self.source_tree, "source tree")
        if type(self.proposals) is not tuple or not self.proposals:
            raise Generation1PlanError(
                "proposal set must be a nonempty immutable tuple"
            )
        if len(self.proposals) > GENERATION_1_MAX_EVALUATED:
            raise Generation1PlanError("Generation-1 budget exceeded")

        seen_programs: set[str] = set()
        seen_proposals: set[str] = set()
        counts = {family: 0 for family in _SUPPORTED_FAMILIES}
        for proposal in self.proposals:
            if type(proposal) is not ResearchProposal:
                raise Generation1PlanError("proposal set requires typed proposals")
            if proposal.generation != 1 or proposal.parent_proposal_ids:
                raise Generation1PlanError("G1 proposal set cannot contain G2 lineage")
            if proposal.semantic_status is not ProposalSemanticStatus.SUPPORTED:
                raise Generation1PlanError(
                    "proposal set accepts supported programs only"
                )
            if type(proposal.strategy_spec) not in _SUPPORTED_SPEC_TYPES:
                raise Generation1PlanError(
                    "proposal spec is outside the frozen G1 grammar"
                )
            if (
                proposal.information_visibility.stage
                is not VisibilityStage.GENERATION_1_PRE_RESULTS
            ):
                raise Generation1PlanError("G1 proposals must be frozen before results")
            if (
                proposal.information_visibility.visible_generation1_diagnostics
                or proposal.information_visibility.confirmation_results_visible
                or proposal.information_visibility.final_holdout_accessed
            ):
                raise Generation1PlanError(
                    "G1 result and holdout visibility must be zero"
                )
            for evidence in proposal.information_visibility.visible_evidence:
                if evidence.classification in (
                    VisibleEvidenceClassification.GENERATION_1_DISCOVERY_RESULT,
                    VisibleEvidenceClassification.GENERATION_2_CONFIRMATION_RESULT,
                    VisibleEvidenceClassification.FINAL_HOLDOUT,
                ) or evidence.time_partition in (
                    VisibleTimePartition.CAMPAIGN_CONFIRMATION_2022_2023,
                    VisibleTimePartition.FINAL_HOLDOUT,
                ):
                    raise Generation1PlanError(
                        "G1 proposal set cannot expose campaign confirmation or holdout"
                    )
            expected_kind = (
                ProposalKind.RETAINED_BASELINE
                if proposal.family
                in (
                    StrategyFamily.MOVING_AVERAGE_TREND,
                    StrategyFamily.DONCHIAN_BREAKOUT,
                )
                else ProposalKind.ORIGINAL
            )
            if proposal.proposal_kind is not expected_kind:
                raise Generation1PlanError(
                    "retained A147 baselines and new G1 programs require "
                    "their frozen kind"
                )
            try:
                compile_generation1_program(proposal.strategy_spec)
            except DiscoveryError as error:
                raise Generation1PlanError(
                    "proposal has no G1 program mapping"
                ) from error
            if proposal.proposal_id in seen_proposals:
                raise Generation1PlanError("duplicate proposal identity")
            if proposal.semantic_program_id in seen_programs:
                raise Generation1PlanError("duplicate semantic program identity")
            seen_proposals.add(proposal.proposal_id)
            seen_programs.add(proposal.semantic_program_id)
            counts[proposal.family] += 1
            if counts[proposal.family] > GENERATION_1_MAX_PER_FAMILY:
                raise Generation1PlanError("Generation-1 per-family budget exceeded")

        object.__setattr__(
            self, "identity", _identity(self.to_dict(include_identity=False))
        )

    @property
    def proposal_identities(self) -> tuple[str, ...]:
        return tuple(proposal.proposal_id for proposal in self.proposals)

    @property
    def semantic_program_ids(self) -> tuple[str, ...]:
        return tuple(proposal.semantic_program_id for proposal in self.proposals)

    @property
    def supported_evaluated_count(self) -> int:
        return len(self.proposals)

    @property
    def family_counts(self) -> tuple[tuple[StrategyFamily, int], ...]:
        return tuple(
            (family, sum(proposal.family is family for proposal in self.proposals))
            for family in _SUPPORTED_FAMILIES
        )

    @property
    def max_evaluated(self) -> int:
        return GENERATION_1_MAX_EVALUATED

    @property
    def max_per_family(self) -> int:
        return GENERATION_1_MAX_PER_FAMILY

    @property
    def generation1_results_visible(self) -> bool:
        return False

    @property
    def confirmation_evidence_visible(self) -> bool:
        return False

    @property
    def final_holdout_sealed(self) -> bool:
        return True

    @property
    def is_complete_population(self) -> bool:
        """Whether this subset contains all 22 and only frozen G1 semantics."""
        return self.supported_evaluated_count == len(frozen_generation1_specs())

    def to_dict(self, *, include_identity: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "schema": SCHEMA,
            "campaign_version": self.campaign_version,
            "generation0_inventory_id": self.generation0_inventory_id,
            "foundation_id": self.foundation_id,
            "source": {"head": self.source_head, "tree": self.source_tree},
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "ordered_proposal_identities": list(self.proposal_identities),
            "ordered_semantic_program_ids": list(self.semantic_program_ids),
            "supported_evaluated_count": self.supported_evaluated_count,
            "complete_frozen_population": self.is_complete_population,
            "family_counts": {
                family.value: count for family, count in self.family_counts
            },
            "budgets": {
                "max_evaluated": self.max_evaluated,
                "max_per_family": self.max_per_family,
            },
            "information_visibility": {
                "stage": VisibilityStage.GENERATION_1_PRE_RESULTS.value,
                "generation1_results_visible": self.generation1_results_visible,
                "confirmation_evidence_visible": self.confirmation_evidence_visible,
                "final_holdout_sealed": self.final_holdout_sealed,
            },
        }
        if include_identity:
            value["identity"] = self.identity
        return value

    def to_bytes(self) -> bytes:
        body = canonical_json_bytes(self.to_dict())
        if len(body) > MAX_PROPOSAL_SET_BYTES:
            raise Generation1PlanError("proposal set exceeds the byte limit")
        return body

    @classmethod
    def from_dict(cls, raw: object) -> Generation1ProposalSet:
        row = _exact_object(
            raw,
            {
                "schema",
                "identity",
                "campaign_version",
                "generation0_inventory_id",
                "foundation_id",
                "source",
                "proposals",
                "ordered_proposal_identities",
                "ordered_semantic_program_ids",
                "supported_evaluated_count",
                "complete_frozen_population",
                "family_counts",
                "budgets",
                "information_visibility",
            },
        )
        if row["schema"] != SCHEMA or type(row["proposals"]) is not list:
            raise Generation1PlanError("unsupported Generation-1 proposal-set schema")
        source = _exact_object(row["source"], {"head", "tree"})
        if (
            type(row["campaign_version"]) is not str
            or type(row["generation0_inventory_id"]) is not str
            or type(row["foundation_id"]) is not str
        ):
            raise Generation1PlanError("proposal-set bindings have invalid types")
        if type(row["proposals"]) is not list or any(
            type(proposal) is not dict for proposal in row["proposals"]
        ):
            raise Generation1PlanError("proposal-set entries must be objects")
        for key in ("ordered_proposal_identities", "ordered_semantic_program_ids"):
            if type(row[key]) is not list or any(
                type(value) is not str for value in row[key]
            ):
                raise Generation1PlanError("ordered identities must be string arrays")
        if type(row["supported_evaluated_count"]) is not int:
            raise Generation1PlanError("supported evaluated count must be an integer")
        if type(row["complete_frozen_population"]) is not bool:
            raise Generation1PlanError("population completeness must be a boolean")
        family_counts = _exact_object(
            row["family_counts"], {f.value for f in _SUPPORTED_FAMILIES}
        )
        if any(type(count) is not int or count < 0 for count in family_counts.values()):
            raise Generation1PlanError("family counts must be nonnegative integers")
        budgets = _exact_object(row["budgets"], {"max_evaluated", "max_per_family"})
        if any(type(value) is not int for value in budgets.values()):
            raise Generation1PlanError("proposal-set budgets must be integers")
        visibility = _exact_object(
            row["information_visibility"],
            {
                "stage",
                "generation1_results_visible",
                "confirmation_evidence_visible",
                "final_holdout_sealed",
            },
        )
        if type(visibility["stage"]) is not str or any(
            type(visibility[name]) is not bool
            for name in (
                "generation1_results_visible",
                "confirmation_evidence_visible",
                "final_holdout_sealed",
            )
        ):
            raise Generation1PlanError(
                "information visibility fields have invalid types"
            )
        plan = cls(
            campaign_version=row["campaign_version"],
            generation0_inventory_id=row["generation0_inventory_id"],
            foundation_id=row["foundation_id"],
            source_head=source["head"],
            source_tree=source["tree"],
            proposals=tuple(
                ResearchProposal.from_dict(item) for item in row["proposals"]
            ),
        )
        if (
            row["identity"] != plan.identity
            or row["ordered_proposal_identities"] != list(plan.proposal_identities)
            or row["ordered_semantic_program_ids"] != list(plan.semantic_program_ids)
            or row["supported_evaluated_count"] != plan.supported_evaluated_count
            or row["complete_frozen_population"] is not plan.is_complete_population
            or row["family_counts"]
            != {family.value: count for family, count in plan.family_counts}
            or row["budgets"]
            != {
                "max_evaluated": plan.max_evaluated,
                "max_per_family": plan.max_per_family,
            }
            or row["information_visibility"]
            != {
                "stage": VisibilityStage.GENERATION_1_PRE_RESULTS.value,
                "generation1_results_visible": False,
                "confirmation_evidence_visible": False,
                "final_holdout_sealed": True,
            }
            or canonical_json_bytes(plan.to_dict()) != canonical_json_bytes(row)
        ):
            raise Generation1PlanError(
                "proposal-set identity or derived fields disagree"
            )
        return plan

    @classmethod
    def from_bytes(cls, body: bytes) -> Generation1ProposalSet:
        if type(body) is not bytes or not body or len(body) > MAX_PROPOSAL_SET_BYTES:
            raise Generation1PlanError("proposal-set JSON size is invalid")
        try:
            raw = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            plan = cls.from_dict(raw)
            if plan.to_bytes() != body:
                raise Generation1PlanError("proposal-set JSON is not canonical")
            return plan
        except (json.JSONDecodeError, UnicodeError, RecursionError, TypeError) as error:
            if isinstance(error, Generation1PlanError):
                raise
            raise Generation1PlanError(
                "invalid canonical Generation-1 proposal set"
            ) from None


def _identity(material: dict[str, object]) -> str:
    return str(
        uuid5(
            _IDENTITY_NAMESPACE,
            canonical_json_bytes(
                {"identity_version": IDENTITY_VERSION, **material}
            ).decode("utf-8"),
        )
    )


def _exact_object(raw: object, expected: set[str]) -> dict[str, object]:
    if type(raw) is not dict or set(raw) != expected:
        raise Generation1PlanError("object fields do not match the closed schema")
    return raw


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Generation1PlanError("duplicate JSON object field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise Generation1PlanError(f"non-finite JSON value rejected: {value}")


def _require_uuid5(value: object, label: str) -> None:
    if type(value) is not str or _UUID.fullmatch(value) is None:
        raise Generation1PlanError(f"{label} must be a canonical UUID5")
    try:
        if str(UUID(value)) != value or UUID(value).version != 5:
            raise ValueError
    except ValueError:
        raise Generation1PlanError(f"{label} must be a canonical UUID5") from None


def _require_git_id(value: object, label: str) -> None:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise Generation1PlanError(f"{label} must be lowercase 40-hex")
