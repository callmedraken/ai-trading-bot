"""Pure SHADOW coverage qualification; no acquisition or execution authority.

Parsers/builders establish self-consistency. Full external evidence is verified
by the qualification entry point and its independent verifier. Rank remains
descriptive and no later lifecycle transition is implemented.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.experiments.historical import HistoricalExperimentResult
from trading_bot.experiments.report import HistoricalExperimentReport
from trading_bot.experiments.research_candidate import (
    ResearchCandidateError,
    ResearchCandidateStage,
    ResearchStrategyCandidate,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    ResearchCandidateShadowVariantBinding,
    resolve_bound_research_candidate_variant,
    verify_research_candidate_shadow_variant_binding,
)
from trading_bot.experiments.research_candidate_shadow_observation import (
    MAX_SHADOW_OBSERVATIONS,
    SHADOW_ZERO_EFFECT_FIELDS,
    ResearchCandidateShadowObservation,
    ResearchCandidateShadowObservationBatch,
    verify_research_candidate_shadow_observation_batch,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardQualification,
    ResearchCandidateWalkForwardQualificationPolicy,
    WalkForwardPassedResearchStrategyCandidate,
)
from trading_bot.experiments.walk_forward import HistoricalExperimentWalkForwardResult

RESEARCH_CANDIDATE_SHADOW_POLICY_SCHEMA = (
    "research-candidate-shadow-qualification-policy/v1"
)
RESEARCH_CANDIDATE_SHADOW_QUALIFICATION_SCHEMA = (
    "research-candidate-shadow-qualification/v1"
)
SHADOW_RESEARCH_CANDIDATE_SCHEMA = "research-strategy-candidate-shadow/v1"
SHADOW_POLICY_NAMESPACE = UUID("e89daadf-93fb-53e9-ae24-ff364c022d31")
SHADOW_QUALIFICATION_NAMESPACE = UUID("c93b2415-1b57-5794-811d-c84dfadf53e6")
SHADOW_CANDIDATE_NAMESPACE = UUID("82dd4ec8-46f3-5f7c-af78-042b0f89bf69")
_SHA40 = re.compile(r"[0-9a-f]{40}")


class ResearchCandidateShadowQualificationError(ResearchCandidateError):
    """Malformed qualification, policy or inconsistent predecessor evidence."""


class ResearchCandidateShadowQualificationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class ResearchCandidateShadowFailureReason(StrEnum):
    INSUFFICIENT_SESSIONS = "INSUFFICIENT_SESSIONS"
    INSUFFICIENT_TOTAL_OBSERVATIONS = "INSUFFICIENT_TOTAL_OBSERVATIONS"
    INSUFFICIENT_OBSERVATIONS_PER_SESSION = "INSUFFICIENT_OBSERVATIONS_PER_SESSION"


def _positive(value: int) -> str:
    if type(value) is not int or not 1 <= value <= MAX_SHADOW_OBSERVATIONS:
        raise ResearchCandidateShadowQualificationError(
            "bounded positive exact integer required"
        )
    return str(value)


def _uuid(value: UUID) -> str:
    if type(value) is not UUID:
        raise ResearchCandidateShadowQualificationError("exact UUID required")
    return str(value)


def _source(value: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchCandidateShadowQualificationError(
            "lowercase 40-hex source required"
        )
    return value


def _identity(namespace: UUID, version: str, *values: str) -> UUID:
    return uuid5(
        namespace, "".join(f"{len(v.encode('utf-8'))}:{v}" for v in (version, *values))
    )


@dataclass(frozen=True, slots=True)
class ResearchCandidateShadowQualificationPolicy:
    minimum_session_count: int
    minimum_total_observation_count: int
    minimum_observations_per_session: int
    schema: str = field(default=RESEARCH_CANDIDATE_SHADOW_POLICY_SCHEMA, init=False)
    policy_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        values = tuple(
            _positive(getattr(self, name))
            for name in (
                "minimum_session_count",
                "minimum_total_observation_count",
                "minimum_observations_per_session",
            )
        )
        if (
            self.minimum_total_observation_count
            < self.minimum_session_count * self.minimum_observations_per_session
        ):
            raise ResearchCandidateShadowQualificationError(
                "inconsistent minimum coverage policy"
            )
        object.__setattr__(
            self,
            "policy_id",
            _identity(
                SHADOW_POLICY_NAMESPACE,
                "research-candidate-shadow-qualification-policy-identity/v1",
                self.schema,
                *values,
            ),
        )

    def to_json(self) -> str:
        _validate(self, ResearchCandidateShadowQualificationPolicy)
        return _json(_wire(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchCandidateShadowQualificationPolicy:
        return _parse(cls, ResearchCandidateShadowQualificationPolicy, value)


@dataclass(frozen=True, slots=True)
class ResearchCandidateShadowQualification:
    binding_id: UUID
    observation_batch_id: UUID
    policy: ResearchCandidateShadowQualificationPolicy
    qualification_source_head: str
    qualification_source_tree: str
    observation_count: int
    distinct_session_count: int
    minimum_observations_in_any_session: int
    schema: str = field(
        default=RESEARCH_CANDIDATE_SHADOW_QUALIFICATION_SCHEMA, init=False
    )
    status: ResearchCandidateShadowQualificationStatus = field(init=False)
    failure_reasons: tuple[ResearchCandidateShadowFailureReason, ...] = field(
        init=False
    )
    qualification_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate(self.policy, ResearchCandidateShadowQualificationPolicy)
        _uuid(self.binding_id)
        _uuid(self.observation_batch_id)
        _source(self.qualification_source_head)
        _source(self.qualification_source_tree)
        counts = tuple(
            _positive(getattr(self, name))
            for name in (
                "observation_count",
                "distinct_session_count",
                "minimum_observations_in_any_session",
            )
        )
        if (
            self.observation_count
            < self.distinct_session_count * self.minimum_observations_in_any_session
            or (
                self.distinct_session_count == 1
                and self.minimum_observations_in_any_session != self.observation_count
            )
        ):
            raise ResearchCandidateShadowQualificationError("incoherent coverage facts")
        conditions = (
            self.distinct_session_count < self.policy.minimum_session_count,
            self.observation_count < self.policy.minimum_total_observation_count,
            self.minimum_observations_in_any_session
            < self.policy.minimum_observations_per_session,
        )
        reasons = tuple(
            reason
            for reason, failed in zip(
                ResearchCandidateShadowFailureReason, conditions, strict=True
            )
            if failed
        )
        status = (
            ResearchCandidateShadowQualificationStatus.FAILED
            if reasons
            else ResearchCandidateShadowQualificationStatus.PASSED
        )
        object.__setattr__(self, "failure_reasons", reasons)
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "qualification_id",
            _identity(
                SHADOW_QUALIFICATION_NAMESPACE,
                "research-candidate-shadow-qualification-identity/v1",
                self.schema,
                str(self.binding_id),
                str(self.observation_batch_id),
                str(self.policy.policy_id),
                self.policy.schema,
                str(self.policy.minimum_session_count),
                str(self.policy.minimum_total_observation_count),
                str(self.policy.minimum_observations_per_session),
                self.qualification_source_head,
                self.qualification_source_tree,
                *counts,
                status.value,
                str(len(reasons)),
                *(reason.value for reason in reasons),
            ),
        )

    def to_json(self) -> str:
        _validate(self, ResearchCandidateShadowQualification)
        return _json(_wire(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchCandidateShadowQualification:
        return _parse(cls, ResearchCandidateShadowQualification, value)


@dataclass(frozen=True, slots=True)
class ShadowResearchStrategyCandidate:
    predecessor_candidate_id: UUID
    backtested_candidate_id: UUID
    walk_forward_qualification_id: UUID
    binding_id: UUID
    observation_batch_id: UUID
    qualification_id: UUID
    source_head: str
    source_tree: str
    walk_forward_qualification_source_head: str
    walk_forward_qualification_source_tree: str
    binding_source_head: str
    binding_source_tree: str
    observation_source_head: str
    observation_source_tree: str
    qualification_source_head: str
    qualification_source_tree: str
    report_id: UUID
    experiment_result_id: UUID
    variant_id: UUID
    caller_ordinal: int
    variant_name: str
    rank: int | None
    schema: str = field(default=SHADOW_RESEARCH_CANDIDATE_SCHEMA, init=False)
    stage: ResearchCandidateStage = field(
        default=ResearchCandidateStage.SHADOW, init=False
    )
    candidate_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        predecessor = WalkForwardPassedResearchStrategyCandidate(
            self.backtested_candidate_id,
            self.walk_forward_qualification_id,
            self.source_head,
            self.source_tree,
            self.report_id,
            self.experiment_result_id,
            self.variant_id,
            self.caller_ordinal,
            self.variant_name,
            self.rank,
        )
        if predecessor.candidate_id != self.predecessor_candidate_id:
            raise ResearchCandidateShadowQualificationError(
                "predecessor semantic material mismatch"
            )
        material = [self.schema, self.stage.value]
        for f in fields(self):
            if f.name in ("schema", "stage", "candidate_id"):
                continue
            value = getattr(self, f.name)
            if f.type == "UUID":
                scalar = _uuid(value)
            elif f.name.endswith(("_head", "_tree")):
                scalar = _source(value)
            elif f.name == "rank":
                scalar = "none" if value is None else str(value)
            else:
                scalar = str(value)
            material.append(scalar)
        object.__setattr__(
            self,
            "candidate_id",
            _identity(
                SHADOW_CANDIDATE_NAMESPACE,
                "research-strategy-candidate-shadow-identity/v1",
                *material,
            ),
        )

    def to_json(self) -> str:
        _validate(self, ShadowResearchStrategyCandidate)
        return _json(_wire(self))

    @classmethod
    def from_json(cls, value: str) -> ShadowResearchStrategyCandidate:
        return _parse(cls, ShadowResearchStrategyCandidate, value)


def _validate(value: object, model: type) -> None:
    if type(value) is not model:
        raise ResearchCandidateShadowQualificationError("exact shadow model required")
    expected = model(
        **{f.name: getattr(value, f.name) for f in fields(model) if f.init}
    )
    if value != expected or any(
        type(getattr(value, f.name)) is not type(getattr(expected, f.name))
        for f in fields(model)
    ):
        raise ResearchCandidateShadowQualificationError("inconsistent shadow artifact")
    if model is ResearchCandidateShadowQualification and any(
        type(reason) is not ResearchCandidateShadowFailureReason
        for reason in value.failure_reasons
    ):
        raise ResearchCandidateShadowQualificationError(
            "exact ordered failure reasons required"
        )


def _coverage(batch: ResearchCandidateShadowObservationBatch) -> tuple[int, int, int]:
    if type(batch) is not ResearchCandidateShadowObservationBatch:
        raise ResearchCandidateShadowQualificationError(
            "exact observation batch required"
        )
    batch.to_json()
    sessions = {}
    for observation in batch.observations:
        for name in SHADOW_ZERO_EFFECT_FIELDS:
            if (
                type(getattr(observation, name)) is not int
                or getattr(observation, name) != 0
            ):
                raise ResearchCandidateShadowQualificationError("zero effects required")
        sessions[observation.session_date] = (
            sessions.get(observation.session_date, 0) + 1
        )
    for name in SHADOW_ZERO_EFFECT_FIELDS:
        if type(getattr(batch, name)) is not int or getattr(batch, name) != 0:
            raise ResearchCandidateShadowQualificationError(
                "zero batch effects required"
            )
    return len(batch.observations), len(sessions), min(sessions.values())


def qualify_research_candidate_shadow(
    binding: ResearchCandidateShadowVariantBinding,
    batch: ResearchCandidateShadowObservationBatch,
    policy: ResearchCandidateShadowQualificationPolicy,
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
) -> ResearchCandidateShadowQualification:
    """Verify exact external provenance and qualify only caller-supplied coverage."""
    _validate(policy, ResearchCandidateShadowQualificationPolicy)
    verify_research_candidate_shadow_variant_binding(
        binding,
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
    )
    resolve_bound_research_candidate_variant(binding, historical_experiment_result)
    verify_research_candidate_shadow_observation_batch(
        batch,
        binding,
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
    )
    return ResearchCandidateShadowQualification(
        binding.binding_id,
        batch.observation_batch_id,
        policy,
        shadow_qualification_source_head,
        shadow_qualification_source_tree,
        *_coverage(batch),
    )


def verify_research_candidate_shadow_qualification(
    shadow_qualification: ResearchCandidateShadowQualification,
    binding: ResearchCandidateShadowVariantBinding,
    batch: ResearchCandidateShadowObservationBatch,
    policy: ResearchCandidateShadowQualificationPolicy,
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
) -> None:
    """Independently rebuild qualification from the complete external chain."""
    _validate(shadow_qualification, ResearchCandidateShadowQualification)
    expected = qualify_research_candidate_shadow(
        binding,
        batch,
        policy,
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
    if shadow_qualification != expected:
        raise ResearchCandidateShadowQualificationError(
            "qualification external evidence mismatch"
        )


def build_shadow_research_candidate(
    predecessor: WalkForwardPassedResearchStrategyCandidate,
    binding: ResearchCandidateShadowVariantBinding,
    batch: ResearchCandidateShadowObservationBatch,
    qualification: ResearchCandidateShadowQualification,
) -> ShadowResearchStrategyCandidate:
    """Build a self-consistent SHADOW successor; external qualification is separate."""
    if (
        type(predecessor) is not WalkForwardPassedResearchStrategyCandidate
        or type(binding) is not ResearchCandidateShadowVariantBinding
    ):
        raise ResearchCandidateShadowQualificationError(
            "exact predecessor and binding required"
        )
    predecessor.to_json()
    binding.to_json()
    _validate(qualification, ResearchCandidateShadowQualification)
    counts = _coverage(batch)
    if (
        qualification.status is not ResearchCandidateShadowQualificationStatus.PASSED
        or qualification.failure_reasons
    ):
        raise ResearchCandidateShadowQualificationError("PASSED qualification required")
    if (
        binding.walk_forward_passed_candidate_id != predecessor.candidate_id
        or binding.predecessor_candidate_id != predecessor.predecessor_candidate_id
        or binding.qualification_id != predecessor.qualification_id
    ):
        raise ResearchCandidateShadowQualificationError(
            "predecessor binding lineage mismatch"
        )
    for name, binding_name in (
        ("source_head", "candidate_source_head"),
        ("source_tree", "candidate_source_tree"),
        ("report_id", "report_id"),
        ("experiment_result_id", "experiment_result_id"),
        ("variant_id", "variant_id"),
        ("caller_ordinal", "caller_ordinal"),
        ("variant_name", "variant_name"),
        ("rank", "rank"),
    ):
        if getattr(predecessor, name) != getattr(binding, binding_name):
            raise ResearchCandidateShadowQualificationError(
                "predecessor binding facts mismatch"
            )
    expected = ResearchCandidateShadowQualification(
        binding.binding_id,
        batch.observation_batch_id,
        qualification.policy,
        qualification.qualification_source_head,
        qualification.qualification_source_tree,
        *counts,
    )
    if batch.binding_id != binding.binding_id or qualification != expected:
        raise ResearchCandidateShadowQualificationError(
            "batch or qualification linkage mismatch"
        )
    return ShadowResearchStrategyCandidate(
        predecessor.candidate_id,
        predecessor.predecessor_candidate_id,
        predecessor.qualification_id,
        binding.binding_id,
        batch.observation_batch_id,
        qualification.qualification_id,
        predecessor.source_head,
        predecessor.source_tree,
        binding.qualification_source_head,
        binding.qualification_source_tree,
        binding.binding_source_head,
        binding.binding_source_tree,
        batch.observation_source_head,
        batch.observation_source_tree,
        qualification.qualification_source_head,
        qualification.qualification_source_tree,
        predecessor.report_id,
        predecessor.experiment_result_id,
        predecessor.variant_id,
        predecessor.caller_ordinal,
        predecessor.variant_name,
        predecessor.rank,
    )


def verify_shadow_research_candidate(
    successor: ShadowResearchStrategyCandidate,
    predecessor: WalkForwardPassedResearchStrategyCandidate,
    binding: ResearchCandidateShadowVariantBinding,
    batch: ResearchCandidateShadowObservationBatch,
    qualification: ResearchCandidateShadowQualification,
) -> None:
    """Independently rebuild exact linkage; not external evidence acceptance."""
    _validate(successor, ShadowResearchStrategyCandidate)
    if successor != build_shadow_research_candidate(
        predecessor, binding, batch, qualification
    ):
        raise ResearchCandidateShadowQualificationError(
            "shadow successor linkage mismatch"
        )


def _wire(value: object) -> dict[str, object]:
    result = {}
    for f in fields(value):
        scalar = getattr(value, f.name)
        if type(scalar) is ResearchCandidateShadowQualificationPolicy:
            scalar = _wire(scalar)
        elif type(scalar) is UUID:
            scalar = str(scalar)
        elif isinstance(scalar, StrEnum):
            scalar = scalar.value
        elif type(scalar) is tuple:
            scalar = [reason.value for reason in scalar]
        result[f.name] = scalar
    return result


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResearchCandidateShadowQualificationError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchCandidateShadowQualificationError("non-JSON constant")


def _parse(cls: type, model: type, value: str):
    try:
        if cls is not model or type(value) is not str:
            raise ResearchCandidateShadowQualificationError(
                "exact canonical JSON required"
            )
        raw = json.loads(
            value, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(raw) is not dict or set(raw) != {f.name for f in fields(model)}:
            raise ResearchCandidateShadowQualificationError(
                "exact artifact fields required"
            )
        arguments = {}
        for f in fields(model):
            if not f.init:
                continue
            scalar = raw[f.name]
            if f.type == "UUID":
                if type(scalar) is not str or str(UUID(scalar)) != scalar:
                    raise ResearchCandidateShadowQualificationError(
                        "canonical UUID required"
                    )
                scalar = UUID(scalar)
            elif f.name == "policy":
                scalar = ResearchCandidateShadowQualificationPolicy.from_json(
                    _json(scalar)
                )
            arguments[f.name] = scalar
        artifact = model(**arguments)
        if artifact.to_json() != value:
            raise ResearchCandidateShadowQualificationError(
                "noncanonical or forged artifact"
            )
        return artifact
    except (TypeError, ValueError, OverflowError, UnicodeError):
        raise ResearchCandidateShadowQualificationError(
            "invalid shadow qualification JSON"
        ) from None


__all__ = [
    "RESEARCH_CANDIDATE_SHADOW_POLICY_SCHEMA",
    "RESEARCH_CANDIDATE_SHADOW_QUALIFICATION_SCHEMA",
    "SHADOW_RESEARCH_CANDIDATE_SCHEMA",
    "SHADOW_POLICY_NAMESPACE",
    "SHADOW_QUALIFICATION_NAMESPACE",
    "SHADOW_CANDIDATE_NAMESPACE",
    "ResearchCandidateShadowQualificationError",
    "ResearchCandidateShadowQualificationPolicy",
    "ResearchCandidateShadowQualification",
    "ResearchCandidateShadowQualificationStatus",
    "ResearchCandidateShadowFailureReason",
    "ShadowResearchStrategyCandidate",
    "qualify_research_candidate_shadow",
    "verify_research_candidate_shadow_qualification",
    "build_shadow_research_candidate",
    "verify_shadow_research_candidate",
]
