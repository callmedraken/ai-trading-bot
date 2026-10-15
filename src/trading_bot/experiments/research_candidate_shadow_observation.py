"""Canonical caller-supplied SHADOW evidence; no observation acquisition.

Zero counters describe supplied evidence. They cannot prove the truthfulness of
an external producer. Parsing proves self-consistency; use the external verifier.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields
from datetime import UTC, date, datetime
from uuid import UUID, uuid5

from trading_bot.experiments.historical import HistoricalExperimentResult
from trading_bot.experiments.report import HistoricalExperimentReport
from trading_bot.experiments.research_candidate import (
    ResearchCandidateError,
    ResearchStrategyCandidate,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    ResearchCandidateShadowVariantBinding,
    resolve_bound_research_candidate_variant,
    verify_research_candidate_shadow_variant_binding,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardQualification,
    ResearchCandidateWalkForwardQualificationPolicy,
    WalkForwardPassedResearchStrategyCandidate,
)
from trading_bot.experiments.walk_forward import HistoricalExperimentWalkForwardResult

RESEARCH_CANDIDATE_SHADOW_OBSERVATION_SCHEMA = (
    "research-candidate-shadow-observation/v1"
)
RESEARCH_CANDIDATE_SHADOW_BATCH_SCHEMA = (
    "research-candidate-shadow-observation-batch/v1"
)
# Literal UUID5 namespaces are frozen from NAMESPACE_URL and the schema strings.
OBSERVATION_NAMESPACE = UUID("ba1eef1a-c096-53bf-a440-545a66226149")
BATCH_NAMESPACE = UUID("3cc3c312-8a9c-5c29-9c6b-81eeeb49d5aa")
MAX_SHADOW_OBSERVATIONS = 100_000
MAX_SHADOW_OBSERVATION_ORDINAL = 1_000_000
SHADOW_ZERO_EFFECT_FIELDS = (
    "credential_reads",
    "provider_calls",
    "robinhood_reads",
    "broker_calls",
    "paper_mutations",
    "scheduler_calls",
    "acl_mutations",
    "production_sqlite_reads",
    "production_sqlite_writes",
)
_SHA40 = re.compile(r"[0-9a-f]{40}")


class ResearchCandidateShadowObservationError(ResearchCandidateError):
    """Malformed canonical observation or inconsistent external provenance."""


def _uuid(value: UUID) -> str:
    if type(value) is not UUID:
        raise ResearchCandidateShadowObservationError("exact UUID required")
    return str(value)


def _source(value: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchCandidateShadowObservationError(
            "lowercase 40-hex source required"
        )
    return value


def _timestamp(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is not UTC or value.fold != 0:
        raise ResearchCandidateShadowObservationError(
            "exact aware UTC datetime required"
        )
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identity(namespace: UUID, version: str, values: tuple[str, ...]) -> UUID:
    return uuid5(
        namespace, "".join(f"{len(v.encode('utf-8'))}:{v}" for v in (version, *values))
    )


def _zeros(value: object) -> tuple[str, ...]:
    for name in SHADOW_ZERO_EFFECT_FIELDS:
        counter = getattr(value, name)
        if type(counter) is not int or counter != 0:
            raise ResearchCandidateShadowObservationError(
                "exact zero effect counters required"
            )
    return ("0",) * len(SHADOW_ZERO_EFFECT_FIELDS)


@dataclass(frozen=True, slots=True)
class ResearchCandidateShadowObservation:
    binding_id: UUID
    session_date: date
    observed_at_utc: datetime
    observation_ordinal: int
    input_fingerprint: UUID
    decision_fingerprint: UUID
    credential_reads: int
    provider_calls: int
    robinhood_reads: int
    broker_calls: int
    paper_mutations: int
    scheduler_calls: int
    acl_mutations: int
    production_sqlite_reads: int
    production_sqlite_writes: int
    schema: str = field(
        default=RESEARCH_CANDIDATE_SHADOW_OBSERVATION_SCHEMA, init=False
    )
    observation_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        if type(self.session_date) is not date:
            raise ResearchCandidateShadowObservationError("exact session date required")
        if (
            type(self.observation_ordinal) is not int
            or not 0 <= self.observation_ordinal <= MAX_SHADOW_OBSERVATION_ORDINAL
        ):
            raise ResearchCandidateShadowObservationError(
                "bounded nonnegative ordinal required"
            )
        material = (
            self.schema,
            _uuid(self.binding_id),
            self.session_date.isoformat(),
            _timestamp(self.observed_at_utc),
            str(self.observation_ordinal),
            _uuid(self.input_fingerprint),
            _uuid(self.decision_fingerprint),
            *_zeros(self),
        )
        object.__setattr__(
            self,
            "observation_id",
            _identity(
                OBSERVATION_NAMESPACE,
                "research-candidate-shadow-observation-identity/v1",
                material,
            ),
        )

    def to_json(self) -> str:
        _validate(self, ResearchCandidateShadowObservation)
        return _json(_wire(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchCandidateShadowObservation:
        return _parse(cls, ResearchCandidateShadowObservation, value)


@dataclass(frozen=True, slots=True)
class ResearchCandidateShadowObservationBatch:
    binding_id: UUID
    observation_source_head: str
    observation_source_tree: str
    observations: tuple[ResearchCandidateShadowObservation, ...]
    schema: str = field(default=RESEARCH_CANDIDATE_SHADOW_BATCH_SCHEMA, init=False)
    observation_count: int = field(init=False)
    credential_reads: int = field(default=0, init=False)
    provider_calls: int = field(default=0, init=False)
    robinhood_reads: int = field(default=0, init=False)
    broker_calls: int = field(default=0, init=False)
    paper_mutations: int = field(default=0, init=False)
    scheduler_calls: int = field(default=0, init=False)
    acl_mutations: int = field(default=0, init=False)
    production_sqlite_reads: int = field(default=0, init=False)
    production_sqlite_writes: int = field(default=0, init=False)
    observation_batch_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _uuid(self.binding_id)
        _source(self.observation_source_head)
        _source(self.observation_source_tree)
        if (
            type(self.observations) is not tuple
            or not 1 <= len(self.observations) <= MAX_SHADOW_OBSERVATIONS
        ):
            raise ResearchCandidateShadowObservationError(
                "bounded nonempty observation tuple required"
            )
        previous = None
        seen = set()
        for observation in self.observations:
            _validate(observation, ResearchCandidateShadowObservation)
            key = (observation.session_date, observation.observation_ordinal)
            if (
                observation.binding_id != self.binding_id
                or observation.observation_id in seen
            ):
                raise ResearchCandidateShadowObservationError(
                    "binding mismatch or duplicate observation"
                )
            if previous is not None and (
                key <= (previous.session_date, previous.observation_ordinal)
                or observation.observed_at_utc < previous.observed_at_utc
            ):
                raise ResearchCandidateShadowObservationError(
                    "caller observation order is not canonical"
                )
            seen.add(observation.observation_id)
            previous = observation
        object.__setattr__(self, "observation_count", len(self.observations))
        material = (
            self.schema,
            str(self.binding_id),
            self.observation_source_head,
            self.observation_source_tree,
            str(self.observation_count),
            *(str(item.observation_id) for item in self.observations),
            *_zeros(self),
        )
        object.__setattr__(
            self,
            "observation_batch_id",
            _identity(
                BATCH_NAMESPACE,
                "research-candidate-shadow-observation-batch-identity/v1",
                material,
            ),
        )

    def to_json(self) -> str:
        _validate(self, ResearchCandidateShadowObservationBatch)
        return _json(_wire(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchCandidateShadowObservationBatch:
        return _parse(cls, ResearchCandidateShadowObservationBatch, value)


def _validate(value: object, model: type) -> None:
    if type(value) is not model:
        raise ResearchCandidateShadowObservationError(
            "exact observation model required"
        )
    expected = model(
        **{f.name: getattr(value, f.name) for f in fields(model) if f.init}
    )
    if value != expected or any(
        type(getattr(value, f.name)) is not type(getattr(expected, f.name))
        for f in fields(model)
    ):
        raise ResearchCandidateShadowObservationError(
            "inconsistent observation artifact"
        )


def _wire(value: object) -> dict[str, object]:
    result = {}
    for f in fields(value):
        scalar = getattr(value, f.name)
        if type(scalar) is UUID:
            scalar = str(scalar)
        elif type(scalar) is date:
            scalar = scalar.isoformat()
        elif type(scalar) is datetime:
            scalar = _timestamp(scalar)
        elif type(scalar) is tuple:
            scalar = [_wire(item) for item in scalar]
        result[f.name] = scalar
    return result


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResearchCandidateShadowObservationError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchCandidateShadowObservationError("non-JSON constant")


def _parse(cls: type, model: type, value: str):
    try:
        if cls is not model or type(value) is not str:
            raise ResearchCandidateShadowObservationError(
                "exact canonical JSON required"
            )
        raw = json.loads(
            value, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(raw) is not dict or set(raw) != {f.name for f in fields(model)}:
            raise ResearchCandidateShadowObservationError(
                "exact artifact fields required"
            )
        arguments = {}
        for f in fields(model):
            if not f.init:
                continue
            scalar = raw[f.name]
            if f.type == "UUID":
                if type(scalar) is not str or str(UUID(scalar)) != scalar:
                    raise ResearchCandidateShadowObservationError(
                        "canonical UUID required"
                    )
                scalar = UUID(scalar)
            elif f.name == "session_date":
                scalar = date.fromisoformat(scalar)
            elif f.name == "observed_at_utc":
                scalar = datetime.fromisoformat(scalar)
            elif f.name == "observations":
                if type(scalar) is not list:
                    raise ResearchCandidateShadowObservationError(
                        "observation array required"
                    )
                scalar = tuple(
                    ResearchCandidateShadowObservation.from_json(_json(item))
                    for item in scalar
                )
            arguments[f.name] = scalar
        artifact = model(**arguments)
        if artifact.to_json() != value:
            raise ResearchCandidateShadowObservationError(
                "noncanonical or forged artifact"
            )
        return artifact
    except (TypeError, ValueError, OverflowError, UnicodeError):
        raise ResearchCandidateShadowObservationError(
            "invalid shadow observation JSON"
        ) from None


def build_research_candidate_shadow_observation_batch(
    binding: ResearchCandidateShadowVariantBinding,
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
) -> ResearchCandidateShadowObservationBatch:
    """Reconcile supplied evidence without acquiring or evaluating observations."""
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
    return ResearchCandidateShadowObservationBatch(
        binding.binding_id,
        observation_source_head,
        observation_source_tree,
        observations,
    )


def verify_research_candidate_shadow_observation_batch(
    batch: ResearchCandidateShadowObservationBatch,
    binding: ResearchCandidateShadowVariantBinding,
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
) -> None:
    """Independently rebuild external provenance and exact caller evidence."""
    _validate(batch, ResearchCandidateShadowObservationBatch)
    expected = build_research_candidate_shadow_observation_batch(
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
    if batch != expected:
        raise ResearchCandidateShadowObservationError(
            "batch does not reconcile with external evidence"
        )


__all__ = [
    "RESEARCH_CANDIDATE_SHADOW_OBSERVATION_SCHEMA",
    "RESEARCH_CANDIDATE_SHADOW_BATCH_SCHEMA",
    "OBSERVATION_NAMESPACE",
    "BATCH_NAMESPACE",
    "SHADOW_ZERO_EFFECT_FIELDS",
    "MAX_SHADOW_OBSERVATIONS",
    "MAX_SHADOW_OBSERVATION_ORDINAL",
    "ResearchCandidateShadowObservation",
    "ResearchCandidateShadowObservationBatch",
    "ResearchCandidateShadowObservationError",
    "build_research_candidate_shadow_observation_batch",
    "verify_research_candidate_shadow_observation_batch",
]
