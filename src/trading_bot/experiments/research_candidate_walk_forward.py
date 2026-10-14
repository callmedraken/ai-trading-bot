"""Pure Architecture-138 evidence; parsing never verifies external research.

Only completed immutable evidence is consumed. The successor grants no shadow,
paper, production compatibility, approval, promotion or execution authority.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field, fields
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.experiments.report import HistoricalExperimentReport
from trading_bot.experiments.research_candidate import (
    ResearchCandidateError,
    ResearchCandidateStage,
    ResearchStrategyCandidate,
    verify_research_candidate_against_report,
)
from trading_bot.experiments.walk_forward import HistoricalExperimentWalkForwardResult
from trading_bot.experiments.walk_forward_analytics import (
    HistoricalExperimentWalkForwardAggregateAnalyzer,
    HistoricalExperimentWalkForwardAggregateMetric,
    HistoricalExperimentWalkForwardAggregateOperation,
    HistoricalExperimentWalkForwardAggregatePolicy,
    HistoricalExperimentWalkForwardMetricPolicy,
)

RESEARCH_CANDIDATE_WALK_FORWARD_POLICY_SCHEMA = (
    "research-candidate-walk-forward-qualification-policy/v1"
)
RESEARCH_CANDIDATE_WALK_FORWARD_QUALIFICATION_SCHEMA = (
    "research-candidate-walk-forward-qualification/v1"
)
WALK_FORWARD_PASSED_RESEARCH_CANDIDATE_SCHEMA = (
    "research-strategy-candidate-walk-forward-passed/v1"
)
_POLICY_NAMESPACE = UUID("e07d29da-3084-5572-9a47-46f9e81dc0f8")
_QUALIFICATION_NAMESPACE = UUID("3c206910-6ced-5f74-b515-52901f6bdbbb")
_SUCCESSOR_NAMESPACE = UUID("e9f8a60f-7b82-57d6-868a-040cb79bb81a")
_AGGREGATE_NAME = "research-candidate-walk-forward-aggregate-evidence/v1"
_SHA40 = re.compile(r"[0-9a-f]{40}")


class ResearchCandidateWalkForwardError(ResearchCandidateError):
    """Malformed qualification material or inconsistent external evidence."""


class ResearchCandidateWalkForwardQualificationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class ResearchCandidateWalkForwardFailureReason(StrEnum):
    INSUFFICIENT_FOLDS = "INSUFFICIENT_FOLDS"
    NONCOMPARABLE_TEST_WINDOWS = "NONCOMPARABLE_TEST_WINDOWS"
    CANDIDATE_NOT_SELECTED_EVERY_FOLD = "CANDIDATE_NOT_SELECTED_EVERY_FOLD"
    MINIMUM_SIMULATION_RETURN_BELOW_THRESHOLD = (
        "MINIMUM_SIMULATION_RETURN_BELOW_THRESHOLD"
    )
    MEDIAN_SIMULATION_RETURN_BELOW_THRESHOLD = (
        "MEDIAN_SIMULATION_RETURN_BELOW_THRESHOLD"
    )
    MAXIMUM_DRAWDOWN_PERCENTAGE_ABOVE_THRESHOLD = (
        "MAXIMUM_DRAWDOWN_PERCENTAGE_ABOVE_THRESHOLD"
    )


def _identity(namespace: UUID, version: str, *values: str) -> UUID:
    try:
        material = "".join(
            f"{len(value.encode('utf-8'))}:{value}" for value in (version, *values)
        )
    except UnicodeError:
        raise ResearchCandidateWalkForwardError("UTF-8 material required") from None
    return uuid5(namespace, material)


def _decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise ResearchCandidateWalkForwardError("exact finite Decimal required")
    # Tuple arithmetic avoids normalize(), rounding and ambient Decimal context.
    if value.is_zero():
        return "0"
    sign, digits, exponent = value.as_tuple()
    coefficient = "".join(str(digit) for digit in digits).rstrip("0")
    exponent += len(digits) - len(coefficient)
    if exponent >= 0:
        text = coefficient + "0" * exponent
    else:
        point = len(coefficient) + exponent
        text = (
            coefficient[:point] + "." + coefficient[point:]
            if point > 0
            else "0." + "0" * (-point) + coefficient
        )
    return "-" + text if sign else text


def _source(value: str) -> None:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchCandidateWalkForwardError(
            "exact lowercase 40-hex source required"
        )


def _uuid(value: UUID) -> None:
    if type(value) is not UUID:
        raise ResearchCandidateWalkForwardError("exact UUID required")


@dataclass(frozen=True, slots=True)
class ResearchCandidateWalkForwardQualificationPolicy:
    minimum_fold_count: int
    minimum_fold_simulation_return: Decimal
    minimum_median_simulation_return: Decimal
    maximum_fold_drawdown_percentage: Decimal
    schema: str = field(
        default=RESEARCH_CANDIDATE_WALK_FORWARD_POLICY_SCHEMA, init=False
    )
    policy_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        if type(self.minimum_fold_count) is not int or not (
            2 <= self.minimum_fold_count <= 1_000_000
        ):
            raise ResearchCandidateWalkForwardError(
                "minimum_fold_count must be 2..1000000"
            )
        decimals = tuple(
            _decimal(value)
            for value in (
                self.minimum_fold_simulation_return,
                self.minimum_median_simulation_return,
                self.maximum_fold_drawdown_percentage,
            )
        )
        if self.maximum_fold_drawdown_percentage < 0:
            raise ResearchCandidateWalkForwardError(
                "drawdown threshold must be nonnegative"
            )
        if self.minimum_median_simulation_return < self.minimum_fold_simulation_return:
            raise ResearchCandidateWalkForwardError(
                "median threshold is below fold threshold"
            )
        object.__setattr__(
            self,
            "policy_id",
            _identity(
                _POLICY_NAMESPACE,
                "research-candidate-walk-forward-qualification-policy-identity/v1",
                self.schema,
                str(self.minimum_fold_count),
                *decimals,
            ),
        )

    def to_json(self) -> str:
        _validate(self, ResearchCandidateWalkForwardQualificationPolicy)
        return _json(_wire(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchCandidateWalkForwardQualificationPolicy:
        return _parse(cls, ResearchCandidateWalkForwardQualificationPolicy, value)


@dataclass(frozen=True, slots=True)
class ResearchCandidateWalkForwardQualification:
    candidate_id: UUID
    policy: ResearchCandidateWalkForwardQualificationPolicy
    qualification_source_head: str
    qualification_source_tree: str
    walk_forward_result_id: UUID
    walk_forward_request_id: UUID
    source_historical_fingerprint: UUID
    aggregate_result_id: UUID
    fold_count: int
    candidate_selected_fold_count: int
    test_windows_comparable: bool
    minimum_observed_simulation_return: Decimal
    median_simulation_return: Decimal
    maximum_observed_drawdown_percentage: Decimal
    schema: str = field(
        default=RESEARCH_CANDIDATE_WALK_FORWARD_QUALIFICATION_SCHEMA, init=False
    )
    policy_id: UUID = field(init=False)
    status: ResearchCandidateWalkForwardQualificationStatus = field(init=False)
    failure_reasons: tuple[ResearchCandidateWalkForwardFailureReason, ...] = field(
        init=False
    )
    qualification_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate(self.policy, ResearchCandidateWalkForwardQualificationPolicy)
        for name in (
            "candidate_id",
            "walk_forward_result_id",
            "walk_forward_request_id",
            "source_historical_fingerprint",
            "aggregate_result_id",
        ):
            _uuid(getattr(self, name))
        _source(self.qualification_source_head)
        _source(self.qualification_source_tree)
        if type(self.fold_count) is not int or self.fold_count < 1:
            raise ResearchCandidateWalkForwardError(
                "positive exact fold_count required"
            )
        if type(self.candidate_selected_fold_count) is not int or not (
            0 <= self.candidate_selected_fold_count <= self.fold_count
        ):
            raise ResearchCandidateWalkForwardError(
                "invalid candidate selected fold count"
            )
        if type(self.test_windows_comparable) is not bool:
            raise ResearchCandidateWalkForwardError("exact comparability bool required")
        decimals = tuple(
            _decimal(value)
            for value in (
                self.minimum_observed_simulation_return,
                self.median_simulation_return,
                self.maximum_observed_drawdown_percentage,
            )
        )
        if self.minimum_observed_simulation_return > self.median_simulation_return:
            raise ResearchCandidateWalkForwardError(
                "minimum exceeds median observation"
            )
        if self.maximum_observed_drawdown_percentage < 0:
            raise ResearchCandidateWalkForwardError("negative drawdown observation")
        policy = self.policy
        conditions = (
            self.fold_count < policy.minimum_fold_count,
            not self.test_windows_comparable,
            self.candidate_selected_fold_count != self.fold_count,
            self.minimum_observed_simulation_return
            < policy.minimum_fold_simulation_return,
            self.median_simulation_return < policy.minimum_median_simulation_return,
            self.maximum_observed_drawdown_percentage
            > policy.maximum_fold_drawdown_percentage,
        )
        reasons = tuple(
            reason
            for reason, failed in zip(
                ResearchCandidateWalkForwardFailureReason, conditions, strict=True
            )
            if failed
        )
        status = (
            ResearchCandidateWalkForwardQualificationStatus.FAILED
            if reasons
            else ResearchCandidateWalkForwardQualificationStatus.PASSED
        )
        object.__setattr__(self, "policy_id", policy.policy_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "failure_reasons", reasons)
        object.__setattr__(
            self,
            "qualification_id",
            _identity(
                _QUALIFICATION_NAMESPACE,
                "research-candidate-walk-forward-qualification-identity/v1",
                self.schema,
                str(self.candidate_id),
                str(policy.policy_id),
                policy.schema,
                str(policy.minimum_fold_count),
                _decimal(policy.minimum_fold_simulation_return),
                _decimal(policy.minimum_median_simulation_return),
                _decimal(policy.maximum_fold_drawdown_percentage),
                self.qualification_source_head,
                self.qualification_source_tree,
                str(self.walk_forward_result_id),
                str(self.walk_forward_request_id),
                str(self.source_historical_fingerprint),
                str(self.aggregate_result_id),
                str(self.fold_count),
                str(self.candidate_selected_fold_count),
                "true" if self.test_windows_comparable else "false",
                *decimals,
                status.value,
                str(len(reasons)),
                *(reason.value for reason in reasons),
            ),
        )

    def to_json(self) -> str:
        """Self-consistent evidence only; external verification is separate."""
        _validate(self, ResearchCandidateWalkForwardQualification)
        return _json(_wire(self))

    @classmethod
    def from_json(cls, value: str) -> ResearchCandidateWalkForwardQualification:
        return _parse(cls, ResearchCandidateWalkForwardQualification, value)


@dataclass(frozen=True, slots=True)
class WalkForwardPassedResearchStrategyCandidate:
    predecessor_candidate_id: UUID
    qualification_id: UUID
    source_head: str
    source_tree: str
    report_id: UUID
    experiment_result_id: UUID
    variant_id: UUID
    caller_ordinal: int
    variant_name: str
    rank: int | None
    schema: str = field(
        default=WALK_FORWARD_PASSED_RESEARCH_CANDIDATE_SCHEMA, init=False
    )
    stage: ResearchCandidateStage = field(
        default=ResearchCandidateStage.WALK_FORWARD_PASSED, init=False
    )
    candidate_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _uuid(self.predecessor_candidate_id)
        _uuid(self.qualification_id)
        predecessor = ResearchStrategyCandidate(
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
            raise ResearchCandidateWalkForwardError(
                "inconsistent predecessor semantic material"
            )
        object.__setattr__(
            self,
            "candidate_id",
            _identity(
                _SUCCESSOR_NAMESPACE,
                "research-strategy-candidate-walk-forward-passed-identity/v1",
                self.schema,
                self.stage.value,
                str(self.predecessor_candidate_id),
                str(self.qualification_id),
                self.source_head,
                self.source_tree,
                str(self.report_id),
                str(self.experiment_result_id),
                str(self.variant_id),
                str(self.caller_ordinal),
                self.variant_name,
                "none" if self.rank is None else str(self.rank),
            ),
        )

    def to_json(self) -> str:
        _validate(self, WalkForwardPassedResearchStrategyCandidate)
        return _json(_wire(self))

    @classmethod
    def from_json(cls, value: str) -> WalkForwardPassedResearchStrategyCandidate:
        return _parse(cls, WalkForwardPassedResearchStrategyCandidate, value)


def _validate(value: object, model: type) -> None:
    if type(value) is not model:
        raise ResearchCandidateWalkForwardError(f"exact {model.__name__} required")
    expected = model(
        **{item.name: getattr(value, item.name) for item in fields(model) if item.init}
    )
    # Equality alone admits bool-as-int, enum-as-str and UUID subclasses in fixed
    # fields; fixed derived fields must have the exact recomputed type as well.
    if value != expected or any(
        type(getattr(value, item.name)) is not type(getattr(expected, item.name))
        for item in fields(model)
    ):
        raise ResearchCandidateWalkForwardError("inconsistent artifact")
    if model is ResearchCandidateWalkForwardQualification and any(
        type(reason) is not ResearchCandidateWalkForwardFailureReason
        for reason in value.failure_reasons
    ):
        raise ResearchCandidateWalkForwardError("exact failure reasons required")


def _validated_walk_forward(
    result: HistoricalExperimentWalkForwardResult,
) -> HistoricalExperimentWalkForwardResult:
    if type(result) is not HistoricalExperimentWalkForwardResult:
        raise ResearchCandidateWalkForwardError(
            "exact completed walk-forward result required"
        )
    validated = deepcopy(result)
    # Existing validators can normalize nested models: never run them on caller
    # evidence, including when validation subsequently fails.
    validated.__post_init__()
    validated.selection_policy.__post_init__()
    for item in validated.folds:
        item.__post_init__()
        item.fold.__post_init__()
        item.training_report.__post_init__()
        item.test_report.__post_init__()
        item.__post_init__()
        if (
            type(item.selection.selected_rank) is not int
            or item.selection.selected_rank != 1
        ):
            raise ResearchCandidateWalkForwardError("exact selected_rank one required")
    validated.__post_init__()
    if validated != result:
        raise ResearchCandidateWalkForwardError(
            "walk-forward evidence must already be canonical"
        )
    return validated


def qualify_research_candidate_walk_forward(
    candidate: ResearchStrategyCandidate,
    report: HistoricalExperimentReport,
    walk_forward_result: HistoricalExperimentWalkForwardResult,
    policy: ResearchCandidateWalkForwardQualificationPolicy,
    *,
    source_head: str,
    source_tree: str,
) -> ResearchCandidateWalkForwardQualification:
    """Evaluate a fixed policy over completed evidence, without executing research."""
    verify_research_candidate_against_report(candidate, report)
    _validate(policy, ResearchCandidateWalkForwardQualificationPolicy)
    _source(source_head)
    _source(source_tree)
    source = _validated_walk_forward(walk_forward_result)
    for fold in source.folds:
        rows = tuple(
            row
            for row in fold.training_report.variants
            if row.variant_id == candidate.variant_id
        )
        if len(rows) != 1 or (
            rows[0].caller_ordinal != candidate.caller_ordinal
            or rows[0].variant_name != candidate.variant_name
        ):
            raise ResearchCandidateWalkForwardError(
                "candidate training provenance disagreement"
            )
    metric = HistoricalExperimentWalkForwardAggregateMetric
    operation = HistoricalExperimentWalkForwardAggregateOperation
    aggregate_policy = HistoricalExperimentWalkForwardAggregatePolicy(
        uuid5(policy.policy_id, _AGGREGATE_NAME),
        (
            HistoricalExperimentWalkForwardMetricPolicy(
                metric.SIMULATION_RETURN, (operation.MINIMUM, operation.MEDIAN)
            ),
            HistoricalExperimentWalkForwardMetricPolicy(
                metric.MAXIMUM_DRAWDOWN_PERCENTAGE, (operation.MAXIMUM,)
            ),
        ),
        (),
    )
    aggregate = HistoricalExperimentWalkForwardAggregateAnalyzer().analyze(
        source, aggregate_policy
    )
    returns, drawdowns = aggregate.metric_summaries
    windows = tuple(
        (
            fold.fold.test_end - fold.fold.test_start,
            len(fold.fold.test_rebalance_timestamps),
        )
        for fold in source.folds
    )
    return ResearchCandidateWalkForwardQualification(
        candidate.candidate_id,
        policy,
        source_head,
        source_tree,
        source.result_id,
        source.request_id,
        source.source_historical_fingerprint,
        aggregate.result_id,
        len(source.folds),
        sum(
            fold.selection.selected_variant_id == candidate.variant_id
            for fold in source.folds
        ),
        all(window == windows[0] for window in windows),
        returns.minimum,
        returns.median,
        drawdowns.maximum,
    )


def verify_research_candidate_walk_forward_qualification(
    qualification: ResearchCandidateWalkForwardQualification,
    candidate: ResearchStrategyCandidate,
    report: HistoricalExperimentReport,
    walk_forward_result: HistoricalExperimentWalkForwardResult,
    policy: ResearchCandidateWalkForwardQualificationPolicy,
    *,
    source_head: str,
    source_tree: str,
) -> None:
    """Independently recompute all external evidence and require exact agreement."""
    _validate(qualification, ResearchCandidateWalkForwardQualification)
    expected = qualify_research_candidate_walk_forward(
        candidate,
        report,
        walk_forward_result,
        policy,
        source_head=source_head,
        source_tree=source_tree,
    )
    if qualification != expected:
        raise ResearchCandidateWalkForwardError(
            "qualification does not reconcile with evidence"
        )


def build_walk_forward_passed_research_candidate(
    candidate: ResearchStrategyCandidate,
    qualification: ResearchCandidateWalkForwardQualification,
) -> WalkForwardPassedResearchStrategyCandidate:
    """Create an inert successor from self-consistent PASSED evidence only.

    Call the independent qualification verifier to establish external evidence;
    this builder and canonical parsing do not assert that it was supplied.
    """
    if type(candidate) is not ResearchStrategyCandidate:
        raise ResearchCandidateWalkForwardError("exact BACKTESTED candidate required")
    candidate.to_json()
    _validate(qualification, ResearchCandidateWalkForwardQualification)
    if (
        qualification.candidate_id != candidate.candidate_id
        or qualification.status
        is not ResearchCandidateWalkForwardQualificationStatus.PASSED
        or qualification.failure_reasons
    ):
        raise ResearchCandidateWalkForwardError(
            "matching PASSED qualification required"
        )
    return WalkForwardPassedResearchStrategyCandidate(
        candidate.candidate_id,
        qualification.qualification_id,
        candidate.source_head,
        candidate.source_tree,
        candidate.report_id,
        candidate.experiment_result_id,
        candidate.variant_id,
        candidate.caller_ordinal,
        candidate.variant_name,
        candidate.rank,
    )


def verify_walk_forward_passed_research_candidate(
    successor: WalkForwardPassedResearchStrategyCandidate,
    candidate: ResearchStrategyCandidate,
    qualification: ResearchCandidateWalkForwardQualification,
) -> None:
    _validate(successor, WalkForwardPassedResearchStrategyCandidate)
    if successor != build_walk_forward_passed_research_candidate(
        candidate, qualification
    ):
        raise ResearchCandidateWalkForwardError(
            "successor does not reconcile with evidence"
        )


def _wire(value: object) -> dict[str, object]:
    result = {}
    for item in fields(value):
        scalar = getattr(value, item.name)
        if type(scalar) is ResearchCandidateWalkForwardQualificationPolicy:
            scalar = _wire(scalar)
        elif type(scalar) is Decimal:
            scalar = _decimal(scalar)
        elif type(scalar) is UUID:
            scalar = str(scalar)
        elif isinstance(scalar, StrEnum):
            scalar = scalar.value
        elif type(scalar) is tuple:
            scalar = [reason.value for reason in scalar]
        result[item.name] = scalar
    return result


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResearchCandidateWalkForwardError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchCandidateWalkForwardError("non-JSON constant")


def _parse(cls: type, model: type, value: str):
    """Canonical bytes prove local consistency, never external reconciliation."""
    try:
        if cls is not model or type(value) is not str:
            raise ResearchCandidateWalkForwardError("exact artifact JSON required")
        raw = json.loads(
            value, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(raw) is not dict or set(raw) != {item.name for item in fields(model)}:
            raise ResearchCandidateWalkForwardError("exact artifact fields required")
        arguments = {}
        for item in fields(model):
            if not item.init:
                continue
            scalar = raw[item.name]
            if item.name == "policy":
                scalar = ResearchCandidateWalkForwardQualificationPolicy.from_json(
                    _json(scalar)
                )
            elif item.type == "UUID":
                if type(scalar) is not str:
                    raise ResearchCandidateWalkForwardError(
                        "canonical UUID string required"
                    )
                parsed = UUID(scalar)
                if str(parsed) != scalar:
                    raise ResearchCandidateWalkForwardError(
                        "canonical UUID string required"
                    )
                scalar = parsed
            elif item.type == "Decimal":
                if type(scalar) is not str:
                    raise ResearchCandidateWalkForwardError(
                        "canonical Decimal string required"
                    )
                scalar = Decimal(scalar)
            arguments[item.name] = scalar
        result = model(**arguments)
        if result.to_json() != value:
            raise ResearchCandidateWalkForwardError(
                "noncanonical or inconsistent artifact"
            )
        return result
    except (TypeError, ValueError, ArithmeticError, UnicodeError):
        raise ResearchCandidateWalkForwardError(
            "invalid research walk-forward JSON"
        ) from None


__all__ = [
    "RESEARCH_CANDIDATE_WALK_FORWARD_POLICY_SCHEMA",
    "RESEARCH_CANDIDATE_WALK_FORWARD_QUALIFICATION_SCHEMA",
    "WALK_FORWARD_PASSED_RESEARCH_CANDIDATE_SCHEMA",
    "ResearchCandidateWalkForwardError",
    "ResearchCandidateWalkForwardQualificationPolicy",
    "ResearchCandidateWalkForwardQualification",
    "ResearchCandidateWalkForwardQualificationStatus",
    "ResearchCandidateWalkForwardFailureReason",
    "WalkForwardPassedResearchStrategyCandidate",
    "qualify_research_candidate_walk_forward",
    "verify_research_candidate_walk_forward_qualification",
    "build_walk_forward_passed_research_candidate",
    "verify_walk_forward_passed_research_candidate",
]
