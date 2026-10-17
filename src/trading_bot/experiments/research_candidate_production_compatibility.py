"""Pure SHADOW-to-production compatibility assessment.

This module records that the current research model has no reviewed semantic
mapping to the production moving-average strategy.  It verifies the complete
caller-supplied 139-B evidence chain, but it never constructs or evaluates a
production strategy and never advances the research lifecycle.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.experiments.historical import (
    HistoricalExperimentResult,
    HistoricalExperimentVariant,
)
from trading_bot.experiments.report import HistoricalExperimentReport
from trading_bot.experiments.research_candidate import (
    ResearchCandidateError,
    ResearchCandidateStage,
    ResearchStrategyCandidate,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    ResearchCandidateShadowVariantBinding,
    resolve_bound_research_candidate_variant,
)
from trading_bot.experiments.research_candidate_shadow_observation import (
    ResearchCandidateShadowObservation,
    ResearchCandidateShadowObservationBatch,
)
from trading_bot.experiments.research_candidate_shadow_qualification import (
    ResearchCandidateShadowQualification,
    ResearchCandidateShadowQualificationPolicy,
    ShadowResearchStrategyCandidate,
    verify_research_candidate_shadow_qualification,
    verify_shadow_research_candidate,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardQualification,
    ResearchCandidateWalkForwardQualificationPolicy,
    WalkForwardPassedResearchStrategyCandidate,
)
from trading_bot.experiments.walk_forward import HistoricalExperimentWalkForwardResult
from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
)

RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_SCHEMA = (
    "research-candidate-production-compatibility/v1"
)
RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_IDENTITY_VERSION = (
    "research-candidate-production-compatibility-identity/v1"
)
RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_NAMESPACE = UUID(
    "3a2c0a57-e61a-5b19-bdc2-00e96e732e96"
)
_SHA40 = re.compile(r"[0-9a-f]{40}")
_FIELDS = frozenset(
    {
        "schema",
        "assessment_id",
        "stage",
        "shadow_candidate_id",
        "binding_id",
        "shadow_qualification_id",
        "historical_experiment_result_id",
        "variant_id",
        "candidate_source_head",
        "candidate_source_tree",
        "assessment_source_head",
        "assessment_source_tree",
        "production_schema",
        "production_strategy_id",
        "production_strategy_version",
        "status",
        "blockers",
    }
)


class ResearchCandidateProductionCompatibilityError(ResearchCandidateError):
    """Malformed assessment or inconsistent complete external evidence."""


class ResearchCandidateProductionCompatibilityStatus(StrEnum):
    """The only status materialized by the frozen v1 contract."""

    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class ResearchCandidateProductionCompatibilityBlocker(StrEnum):
    """Ordered reasons that v1 cannot establish positive compatibility."""

    RESEARCH_STRATEGY_FAMILY_UNBOUND = "RESEARCH_STRATEGY_FAMILY_UNBOUND"
    PRODUCTION_SYMBOL_MAPPING_UNBOUND = "PRODUCTION_SYMBOL_MAPPING_UNBOUND"
    PRODUCTION_CONFIG_MAPPING_UNBOUND = "PRODUCTION_CONFIG_MAPPING_UNBOUND"


_BLOCKERS = (
    ResearchCandidateProductionCompatibilityBlocker.RESEARCH_STRATEGY_FAMILY_UNBOUND,
    ResearchCandidateProductionCompatibilityBlocker.PRODUCTION_SYMBOL_MAPPING_UNBOUND,
    ResearchCandidateProductionCompatibilityBlocker.PRODUCTION_CONFIG_MAPPING_UNBOUND,
)


def _uuid(value: object, name: str) -> UUID:
    if type(value) is not UUID:
        raise ResearchCandidateProductionCompatibilityError(
            f"{name} must be exactly UUID"
        )
    return value


def _source(value: object, name: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchCandidateProductionCompatibilityError(
            f"{name} must be exact lowercase 40-hex"
        )
    return value


def _frame(values: tuple[str, ...]) -> str:
    try:
        return "".join(f"{len(value.encode('utf-8'))}:{value}" for value in values)
    except UnicodeError:
        raise ResearchCandidateProductionCompatibilityError(
            "identity material must be UTF-8"
        ) from None


def _identity_material(
    assessment: ResearchCandidateProductionCompatibilityAssessment,
) -> str:
    values = (
        RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_IDENTITY_VERSION,
        assessment.schema,
        assessment.stage.value,
        str(assessment.shadow_candidate_id),
        str(assessment.binding_id),
        str(assessment.shadow_qualification_id),
        str(assessment.historical_experiment_result_id),
        str(assessment.variant_id),
        assessment.candidate_source_head,
        assessment.candidate_source_tree,
        assessment.assessment_source_head,
        assessment.assessment_source_tree,
        assessment.production_schema,
        assessment.production_strategy_id,
        assessment.production_strategy_version,
        assessment.status.value,
        str(len(assessment.blockers)),
        *(blocker.value for blocker in assessment.blockers),
    )
    return _frame(values)


@dataclass(frozen=True, slots=True)
class ResearchCandidateProductionCompatibilityAssessment:
    """Immutable, negative compatibility evidence for one verified SHADOW chain."""

    shadow_candidate_id: UUID
    binding_id: UUID
    shadow_qualification_id: UUID
    historical_experiment_result_id: UUID
    variant_id: UUID
    candidate_source_head: str
    candidate_source_tree: str
    assessment_source_head: str
    assessment_source_tree: str
    schema: str = field(
        default=RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_SCHEMA, init=False
    )
    assessment_id: UUID = field(init=False)
    stage: ResearchCandidateStage = field(
        default=ResearchCandidateStage.SHADOW, init=False
    )
    production_schema: str = field(default=PRODUCTION_STRATEGY_SCHEMA, init=False)
    production_strategy_id: str = field(default=MOVING_AVERAGE_STRATEGY_ID, init=False)
    production_strategy_version: str = field(
        default=MOVING_AVERAGE_STRATEGY_VERSION, init=False
    )
    status: ResearchCandidateProductionCompatibilityStatus = field(init=False)
    blockers: tuple[ResearchCandidateProductionCompatibilityBlocker, ...] = field(
        init=False
    )

    def __post_init__(self) -> None:
        for name in (
            "shadow_candidate_id",
            "binding_id",
            "shadow_qualification_id",
            "historical_experiment_result_id",
            "variant_id",
        ):
            _uuid(getattr(self, name), name)
        for name in (
            "candidate_source_head",
            "candidate_source_tree",
            "assessment_source_head",
            "assessment_source_tree",
        ):
            _source(getattr(self, name), name)
        if self.schema != RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_SCHEMA:
            raise ResearchCandidateProductionCompatibilityError("invalid schema")
        if self.stage is not ResearchCandidateStage.SHADOW:
            raise ResearchCandidateProductionCompatibilityError(
                "assessment stage must be SHADOW"
            )
        if self.production_schema != PRODUCTION_STRATEGY_SCHEMA:
            raise ResearchCandidateProductionCompatibilityError(
                "invalid production schema"
            )
        if self.production_strategy_id != MOVING_AVERAGE_STRATEGY_ID:
            raise ResearchCandidateProductionCompatibilityError(
                "invalid production strategy id"
            )
        if self.production_strategy_version != MOVING_AVERAGE_STRATEGY_VERSION:
            raise ResearchCandidateProductionCompatibilityError(
                "invalid production strategy version"
            )
        object.__setattr__(
            self,
            "status",
            ResearchCandidateProductionCompatibilityStatus.NOT_ESTABLISHED,
        )
        object.__setattr__(self, "blockers", _BLOCKERS)
        object.__setattr__(
            self,
            "assessment_id",
            uuid5(
                RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_NAMESPACE,
                _identity_material(self),
            ),
        )

    def to_json(self) -> str:
        """Return compact sorted canonical JSON proving self-consistency only."""
        _validate_assessment(self)
        return json.dumps(
            {
                "schema": self.schema,
                "assessment_id": str(self.assessment_id),
                "stage": self.stage.value,
                "shadow_candidate_id": str(self.shadow_candidate_id),
                "binding_id": str(self.binding_id),
                "shadow_qualification_id": str(self.shadow_qualification_id),
                "historical_experiment_result_id": str(
                    self.historical_experiment_result_id
                ),
                "variant_id": str(self.variant_id),
                "candidate_source_head": self.candidate_source_head,
                "candidate_source_tree": self.candidate_source_tree,
                "assessment_source_head": self.assessment_source_head,
                "assessment_source_tree": self.assessment_source_tree,
                "production_schema": self.production_schema,
                "production_strategy_id": self.production_strategy_id,
                "production_strategy_version": self.production_strategy_version,
                "status": self.status.value,
                "blockers": [blocker.value for blocker in self.blockers],
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_json(
        cls, value: str
    ) -> ResearchCandidateProductionCompatibilityAssessment:
        """Parse canonical self-consistent bytes without external verification."""
        try:
            if (
                cls is not ResearchCandidateProductionCompatibilityAssessment
                or type(value) is not str
            ):
                raise ResearchCandidateProductionCompatibilityError(
                    "exact assessment JSON required"
                )
            raw = json.loads(
                value, object_pairs_hook=_unique_object, parse_constant=_reject_constant
            )
            if type(raw) is not dict or set(raw) != _FIELDS:
                raise ResearchCandidateProductionCompatibilityError(
                    "exact assessment fields required"
                )
            if (
                raw["schema"] != RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_SCHEMA
                or raw["stage"] != ResearchCandidateStage.SHADOW.value
                or raw["production_schema"] != PRODUCTION_STRATEGY_SCHEMA
                or raw["production_strategy_id"] != MOVING_AVERAGE_STRATEGY_ID
                or raw["production_strategy_version"] != MOVING_AVERAGE_STRATEGY_VERSION
                or raw["status"]
                != ResearchCandidateProductionCompatibilityStatus.NOT_ESTABLISHED.value
            ):
                raise ResearchCandidateProductionCompatibilityError(
                    "invalid assessment constants"
                )
            if raw["blockers"] != [blocker.value for blocker in _BLOCKERS]:
                raise ResearchCandidateProductionCompatibilityError(
                    "invalid ordered blockers"
                )
            result = cls(
                shadow_candidate_id=_parse_uuid(raw["shadow_candidate_id"]),
                binding_id=_parse_uuid(raw["binding_id"]),
                shadow_qualification_id=_parse_uuid(raw["shadow_qualification_id"]),
                historical_experiment_result_id=_parse_uuid(
                    raw["historical_experiment_result_id"]
                ),
                variant_id=_parse_uuid(raw["variant_id"]),
                candidate_source_head=raw["candidate_source_head"],
                candidate_source_tree=raw["candidate_source_tree"],
                assessment_source_head=raw["assessment_source_head"],
                assessment_source_tree=raw["assessment_source_tree"],
            )
            if (
                _parse_uuid(raw["assessment_id"]) != result.assessment_id
                or result.to_json() != value
            ):
                raise ResearchCandidateProductionCompatibilityError(
                    "noncanonical or inconsistent assessment"
                )
            return result
        except (TypeError, ValueError, OverflowError, UnicodeError):
            raise ResearchCandidateProductionCompatibilityError(
                "invalid production compatibility assessment JSON"
            ) from None


def _validate_assessment(
    assessment: ResearchCandidateProductionCompatibilityAssessment,
) -> None:
    if type(assessment) is not ResearchCandidateProductionCompatibilityAssessment:
        raise ResearchCandidateProductionCompatibilityError("exact assessment required")
    if assessment.schema != RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_SCHEMA:
        raise ResearchCandidateProductionCompatibilityError("invalid assessment schema")
    if (
        assessment.production_schema != PRODUCTION_STRATEGY_SCHEMA
        or assessment.production_strategy_id != MOVING_AVERAGE_STRATEGY_ID
        or assessment.production_strategy_version != MOVING_AVERAGE_STRATEGY_VERSION
    ):
        raise ResearchCandidateProductionCompatibilityError(
            "assessment production constants are inconsistent"
        )
    for name in (
        "shadow_candidate_id",
        "binding_id",
        "shadow_qualification_id",
        "historical_experiment_result_id",
        "variant_id",
    ):
        _uuid(getattr(assessment, name), name)
    for name in (
        "candidate_source_head",
        "candidate_source_tree",
        "assessment_source_head",
        "assessment_source_tree",
    ):
        _source(getattr(assessment, name), name)
    if (
        type(assessment.stage) is not ResearchCandidateStage
        or assessment.stage is not ResearchCandidateStage.SHADOW
        or type(assessment.status) is not ResearchCandidateProductionCompatibilityStatus
        or assessment.status
        is not ResearchCandidateProductionCompatibilityStatus.NOT_ESTABLISHED
        or type(assessment.blockers) is not tuple
        or assessment.blockers != _BLOCKERS
        or any(
            type(item) is not ResearchCandidateProductionCompatibilityBlocker
            for item in assessment.blockers
        )
    ):
        raise ResearchCandidateProductionCompatibilityError(
            "assessment constants are inconsistent"
        )
    expected = uuid5(
        RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_NAMESPACE,
        _identity_material(assessment),
    )
    if (
        type(assessment.assessment_id) is not UUID
        or assessment.assessment_id != expected
    ):
        raise ResearchCandidateProductionCompatibilityError(
            "assessment_id is inconsistent"
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ResearchCandidateProductionCompatibilityError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchCandidateProductionCompatibilityError("non-JSON constant")


def _parse_uuid(value: object) -> UUID:
    if type(value) is not str:
        raise ResearchCandidateProductionCompatibilityError(
            "canonical UUID string required"
        )
    parsed = UUID(value)
    if str(parsed) != value:
        raise ResearchCandidateProductionCompatibilityError(
            "canonical UUID string required"
        )
    return parsed


def _decimal_precision(value: object) -> int:
    if type(value) is Decimal:
        return max(28, len(value.as_tuple().digits))
    if is_dataclass(value) and not isinstance(value, type):
        return max(
            (_decimal_precision(getattr(value, item.name)) for item in fields(value)),
            default=28,
        )
    if isinstance(value, Mapping):
        return max((_decimal_precision(item) for item in value.values()), default=28)
    if isinstance(value, (tuple, list)):
        return max((_decimal_precision(item) for item in value), default=28)
    return 28


def _revalidate_variant(variant: HistoricalExperimentVariant) -> None:
    if type(variant) is not HistoricalExperimentVariant:
        raise ResearchCandidateProductionCompatibilityError(
            "exact retained historical variant required"
        )
    retained = deepcopy(variant)
    with localcontext(Context(prec=_decimal_precision(retained))):
        retained.__post_init__()
    if retained != variant:
        raise ResearchCandidateProductionCompatibilityError(
            "retained historical variant is not canonical"
        )


def _verify_lineage(
    shadow_candidate: ShadowResearchStrategyCandidate,
    binding: ResearchCandidateShadowVariantBinding,
    shadow_qualification: ResearchCandidateShadowQualification,
    batch: ResearchCandidateShadowObservationBatch,
    predecessor: ResearchStrategyCandidate,
    walk_forward_passed: WalkForwardPassedResearchStrategyCandidate,
    qualification: ResearchCandidateWalkForwardQualification,
    report: HistoricalExperimentReport,
    historical_experiment_result: HistoricalExperimentResult,
    walk_forward_result: HistoricalExperimentWalkForwardResult,
    variant: HistoricalExperimentVariant,
) -> None:
    pairs = (
        (shadow_candidate.binding_id, binding.binding_id),
        (shadow_candidate.observation_batch_id, batch.observation_batch_id),
        (shadow_candidate.qualification_id, shadow_qualification.qualification_id),
        (shadow_candidate.predecessor_candidate_id, walk_forward_passed.candidate_id),
        (shadow_candidate.backtested_candidate_id, predecessor.candidate_id),
        (
            shadow_candidate.walk_forward_qualification_id,
            qualification.qualification_id,
        ),
        (shadow_candidate.report_id, report.report_id),
        (shadow_candidate.experiment_result_id, historical_experiment_result.result_id),
        (shadow_candidate.variant_id, variant.variant_id),
        (binding.experiment_result_id, historical_experiment_result.result_id),
        (binding.variant_id, variant.variant_id),
        (binding.report_id, report.report_id),
        (binding.walk_forward_passed_candidate_id, walk_forward_passed.candidate_id),
        (binding.predecessor_candidate_id, predecessor.candidate_id),
        (binding.qualification_id, qualification.qualification_id),
        (qualification.candidate_id, predecessor.candidate_id),
        (qualification.walk_forward_result_id, walk_forward_result.result_id),
    )
    if any(left != right for left, right in pairs):
        raise ResearchCandidateProductionCompatibilityError(
            "candidate/result/variant lineage mismatch"
        )
    source_pairs = (
        (shadow_candidate.source_head, binding.candidate_source_head),
        (shadow_candidate.source_tree, binding.candidate_source_tree),
        (shadow_candidate.source_head, predecessor.source_head),
        (shadow_candidate.source_tree, predecessor.source_tree),
        (shadow_candidate.source_head, walk_forward_passed.source_head),
        (shadow_candidate.source_tree, walk_forward_passed.source_tree),
    )
    if any(left != right for left, right in source_pairs):
        raise ResearchCandidateProductionCompatibilityError(
            "candidate source lineage mismatch"
        )
    report_rows = tuple(
        row for row in report.variants if row.variant_id == binding.variant_id
    )
    if (
        binding.caller_ordinal >= len(historical_experiment_result.request.variants)
        or historical_experiment_result.request.variants[binding.caller_ordinal]
        is not variant
        or len(report_rows) != 1
        or report_rows[0].caller_ordinal != binding.caller_ordinal
        or report_rows[0].variant_id != variant.variant_id
    ):
        raise ResearchCandidateProductionCompatibilityError(
            "resolved variant lineage mismatch"
        )


def build_research_candidate_production_compatibility_assessment(
    shadow_candidate: ShadowResearchStrategyCandidate,
    binding: ResearchCandidateShadowVariantBinding,
    shadow_qualification: ResearchCandidateShadowQualification,
    batch: ResearchCandidateShadowObservationBatch,
    shadow_qualification_policy: ResearchCandidateShadowQualificationPolicy,
    predecessor: ResearchStrategyCandidate,
    walk_forward_passed: WalkForwardPassedResearchStrategyCandidate,
    qualification: ResearchCandidateWalkForwardQualification,
    report: HistoricalExperimentReport,
    historical_experiment_result: HistoricalExperimentResult,
    walk_forward_result: HistoricalExperimentWalkForwardResult,
    qualification_policy: ResearchCandidateWalkForwardQualificationPolicy,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    binding_source_head: str,
    binding_source_tree: str,
    observations: tuple[ResearchCandidateShadowObservation, ...],
    observation_source_head: str,
    observation_source_tree: str,
    shadow_qualification_source_head: str,
    shadow_qualification_source_tree: str,
    assessment_source_head: str,
    assessment_source_tree: str,
) -> ResearchCandidateProductionCompatibilityAssessment:
    """Verify complete SHADOW evidence and return only NOT_ESTABLISHED v1."""
    verify_research_candidate_shadow_qualification(
        shadow_qualification,
        binding,
        batch=batch,
        policy=shadow_qualification_policy,
        predecessor=predecessor,
        walk_forward_passed=walk_forward_passed,
        qualification=qualification,
        report=report,
        historical_experiment_result=historical_experiment_result,
        walk_forward_result=walk_forward_result,
        qualification_policy=qualification_policy,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
        binding_source_head=binding_source_head,
        binding_source_tree=binding_source_tree,
        observations=observations,
        observation_source_head=observation_source_head,
        observation_source_tree=observation_source_tree,
        shadow_qualification_source_head=shadow_qualification_source_head,
        shadow_qualification_source_tree=shadow_qualification_source_tree,
    )
    verify_shadow_research_candidate(
        shadow_candidate,
        walk_forward_passed,
        binding,
        batch=batch,
        qualification=shadow_qualification,
    )
    variant = resolve_bound_research_candidate_variant(
        binding, historical_experiment_result
    )
    _verify_lineage(
        shadow_candidate,
        binding,
        shadow_qualification,
        batch,
        predecessor,
        walk_forward_passed,
        qualification,
        report,
        historical_experiment_result,
        walk_forward_result,
        variant,
    )
    _revalidate_variant(variant)
    return ResearchCandidateProductionCompatibilityAssessment(
        shadow_candidate.candidate_id,
        binding.binding_id,
        shadow_qualification.qualification_id,
        historical_experiment_result.result_id,
        variant.variant_id,
        shadow_candidate.source_head,
        shadow_candidate.source_tree,
        assessment_source_head,
        assessment_source_tree,
    )


def verify_research_candidate_production_compatibility_assessment(
    assessment: ResearchCandidateProductionCompatibilityAssessment,
    shadow_candidate: ShadowResearchStrategyCandidate,
    binding: ResearchCandidateShadowVariantBinding,
    shadow_qualification: ResearchCandidateShadowQualification,
    batch: ResearchCandidateShadowObservationBatch,
    shadow_qualification_policy: ResearchCandidateShadowQualificationPolicy,
    predecessor: ResearchStrategyCandidate,
    walk_forward_passed: WalkForwardPassedResearchStrategyCandidate,
    qualification: ResearchCandidateWalkForwardQualification,
    report: HistoricalExperimentReport,
    historical_experiment_result: HistoricalExperimentResult,
    walk_forward_result: HistoricalExperimentWalkForwardResult,
    qualification_policy: ResearchCandidateWalkForwardQualificationPolicy,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    binding_source_head: str,
    binding_source_tree: str,
    observations: tuple[ResearchCandidateShadowObservation, ...],
    observation_source_head: str,
    observation_source_tree: str,
    shadow_qualification_source_head: str,
    shadow_qualification_source_tree: str,
    assessment_source_head: str,
    assessment_source_tree: str,
) -> None:
    """Reconstruct complete external evidence and require exact assessment equality."""
    _validate_assessment(assessment)
    expected = build_research_candidate_production_compatibility_assessment(
        shadow_candidate,
        binding,
        shadow_qualification,
        batch,
        shadow_qualification_policy,
        predecessor,
        walk_forward_passed,
        qualification,
        report,
        historical_experiment_result,
        walk_forward_result,
        qualification_policy,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
        binding_source_head=binding_source_head,
        binding_source_tree=binding_source_tree,
        observations=observations,
        observation_source_head=observation_source_head,
        observation_source_tree=observation_source_tree,
        shadow_qualification_source_head=shadow_qualification_source_head,
        shadow_qualification_source_tree=shadow_qualification_source_tree,
        assessment_source_head=assessment_source_head,
        assessment_source_tree=assessment_source_tree,
    )
    if assessment != expected:
        raise ResearchCandidateProductionCompatibilityError(
            "assessment does not reconcile with complete external evidence"
        )


__all__ = [
    "RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_SCHEMA",
    "RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_IDENTITY_VERSION",
    "RESEARCH_CANDIDATE_PRODUCTION_COMPATIBILITY_NAMESPACE",
    "ResearchCandidateProductionCompatibilityError",
    "ResearchCandidateProductionCompatibilityStatus",
    "ResearchCandidateProductionCompatibilityBlocker",
    "ResearchCandidateProductionCompatibilityAssessment",
    "build_research_candidate_production_compatibility_assessment",
    "verify_research_candidate_production_compatibility_assessment",
]
