"""Exact, inert provenance binding for completed research; no SHADOW authority."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import copy, deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from decimal import Context, Decimal, localcontext
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.experiments.historical import (
    HistoricalExperimentRequest,
    HistoricalExperimentResult,
    HistoricalExperimentRun,
    HistoricalExperimentVariant,
)
from trading_bot.experiments.report import HistoricalExperimentReport
from trading_bot.experiments.research_candidate import (
    MAX_RESEARCH_CANDIDATE_NAME_LENGTH,
    MAX_RESEARCH_CANDIDATE_ORDINAL,
    MAX_RESEARCH_CANDIDATE_RANK,
    ResearchCandidateError,
    ResearchStrategyCandidate,
    verify_research_candidate_against_report,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardQualification,
    ResearchCandidateWalkForwardQualificationPolicy,
    ResearchCandidateWalkForwardQualificationStatus,
    WalkForwardPassedResearchStrategyCandidate,
    verify_research_candidate_walk_forward_qualification,
    verify_walk_forward_passed_research_candidate,
)
from trading_bot.experiments.walk_forward import HistoricalExperimentWalkForwardResult

RESEARCH_CANDIDATE_SHADOW_BINDING_SCHEMA = (
    "research-candidate-shadow-variant-binding/v1"
)
RESEARCH_CANDIDATE_SHADOW_BINDING_IDENTITY_VERSION = (
    "research-candidate-shadow-variant-binding-identity/v1"
)
RESEARCH_CANDIDATE_SHADOW_BINDING_NAMESPACE = UUID(
    "0521440a-535c-4ebc-baa4-b071db744593"
)
_SHA40 = re.compile(r"[0-9a-f]{40}")


class ResearchCandidateShadowBindingError(ResearchCandidateError):
    """Malformed binding or inconsistent completed external evidence."""


def _material(binding: ResearchCandidateShadowVariantBinding) -> str:
    if (
        type(binding.schema) is not str
        or binding.schema != RESEARCH_CANDIDATE_SHADOW_BINDING_SCHEMA
    ):
        raise ResearchCandidateShadowBindingError("invalid binding schema")
    values = [RESEARCH_CANDIDATE_SHADOW_BINDING_IDENTITY_VERSION, binding.schema]
    for item in fields(binding):
        if item.name in ("schema", "binding_id"):
            continue
        value = getattr(binding, item.name)
        if item.type == "UUID":
            if type(value) is not UUID:
                raise ResearchCandidateShadowBindingError(
                    f"exact UUID required: {item.name}"
                )
            text = str(value)
        elif item.name.endswith(("_head", "_tree")):
            if type(value) is not str or _SHA40.fullmatch(value) is None:
                raise ResearchCandidateShadowBindingError(
                    f"exact lowercase 40-hex required: {item.name}"
                )
            text = value
        elif item.name == "caller_ordinal":
            if (
                type(value) is not int
                or not 0 <= value <= MAX_RESEARCH_CANDIDATE_ORDINAL
            ):
                raise ResearchCandidateShadowBindingError("invalid caller ordinal")
            text = str(value)
        elif item.name == "rank":
            if value is not None and (
                type(value) is not int or not 1 <= value <= MAX_RESEARCH_CANDIDATE_RANK
            ):
                raise ResearchCandidateShadowBindingError("invalid rank")
            text = "none" if value is None else str(value)
        else:
            if (
                type(value) is not str
                or not value
                or value != value.strip()
                or len(value) > MAX_RESEARCH_CANDIDATE_NAME_LENGTH
            ):
                raise ResearchCandidateShadowBindingError("invalid variant name")
            text = value
        values.append(text)
    try:
        return "".join(f"{len(value.encode('utf-8'))}:{value}" for value in values)
    except UnicodeError:
        raise ResearchCandidateShadowBindingError("UTF-8 material required") from None


@dataclass(frozen=True, slots=True)
class ResearchCandidateShadowVariantBinding:
    """Self-consistent provenance only; full external verification is separate."""

    walk_forward_passed_candidate_id: UUID
    predecessor_candidate_id: UUID
    qualification_id: UUID
    candidate_source_head: str
    candidate_source_tree: str
    qualification_source_head: str
    qualification_source_tree: str
    binding_source_head: str
    binding_source_tree: str
    report_id: UUID
    experiment_request_id: UUID
    experiment_result_id: UUID
    historical_fingerprint: UUID
    schedule_fingerprint: UUID
    initial_state_fingerprint: UUID
    variant_id: UUID
    caller_ordinal: int
    variant_name: str
    rank: int | None
    experiment_run_id: UUID
    rolling_result_id: UUID
    schema: str = field(default=RESEARCH_CANDIDATE_SHADOW_BINDING_SCHEMA, init=False)
    binding_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "binding_id",
            uuid5(RESEARCH_CANDIDATE_SHADOW_BINDING_NAMESPACE, _material(self)),
        )

    def to_json(self) -> str:
        """Canonical self-consistency, without external-evidence acceptance."""
        _validate_binding(self)
        return json.dumps(
            {
                item.name: str(value)
                if type(value := getattr(self, item.name)) is UUID
                else value
                for item in fields(self)
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchCandidateShadowVariantBinding:
        """Parsing never proves report/result/walk-forward verification or SHADOW."""
        try:
            if (
                cls is not ResearchCandidateShadowVariantBinding
                or type(value) is not str
            ):
                raise ResearchCandidateShadowBindingError("exact binding JSON required")
            raw = json.loads(
                value, object_pairs_hook=_unique_object, parse_constant=_reject_constant
            )
            if type(raw) is not dict or set(raw) != {item.name for item in fields(cls)}:
                raise ResearchCandidateShadowBindingError(
                    "exact binding fields required"
                )
            arguments = {}
            for item in fields(cls):
                if not item.init:
                    continue
                scalar = raw[item.name]
                if item.type == "UUID":
                    if type(scalar) is not str:
                        raise ResearchCandidateShadowBindingError(
                            "canonical UUID string required"
                        )
                    parsed = UUID(scalar)
                    if str(parsed) != scalar:
                        raise ResearchCandidateShadowBindingError(
                            "canonical UUID string required"
                        )
                    scalar = parsed
                arguments[item.name] = scalar
            result = cls(**arguments)
            if result.to_json() != value:
                raise ResearchCandidateShadowBindingError(
                    "noncanonical or inconsistent binding"
                )
            return result
        except (TypeError, ValueError, UnicodeError):
            raise ResearchCandidateShadowBindingError(
                "invalid shadow variant binding JSON"
            ) from None


def _validate_binding(binding: ResearchCandidateShadowVariantBinding) -> None:
    if type(binding) is not ResearchCandidateShadowVariantBinding:
        raise ResearchCandidateShadowBindingError("exact binding required")
    expected = uuid5(RESEARCH_CANDIDATE_SHADOW_BINDING_NAMESPACE, _material(binding))
    if type(binding.binding_id) is not UUID or binding.binding_id != expected:
        raise ResearchCandidateShadowBindingError("inconsistent binding_id")


def _copy_retained(value: object, memo: dict[int, object] | None = None):
    """Copy immutable evidence including mapping proxies, preserving shared links.

    Object addresses are used only as a copy memo, never as identity material.
    Reconstructing dataclasses via constructors would erase relationship drift.
    """
    if memo is None:
        memo = {}
    key = id(value)
    if key in memo:
        return memo[key]
    if is_dataclass(value) and not isinstance(value, type):
        result = copy(value)
        memo[key] = result
        for item in fields(value):
            object.__setattr__(
                result, item.name, _copy_retained(getattr(value, item.name), memo)
            )
        return result
    if type(value) in (dict, MappingProxyType):
        storage = {}
        result = (
            MappingProxyType(storage) if type(value) is MappingProxyType else storage
        )
        memo[key] = result
        for name, item in value.items():
            storage[_copy_retained(name, memo)] = _copy_retained(item, memo)
        return result
    if type(value) in (tuple, list):
        result = (
            tuple(_copy_retained(item, memo) for item in value)
            if type(value) is tuple
            else [_copy_retained(item, memo) for item in value]
        )
        memo[key] = result
        return result
    return deepcopy(value, memo)


def _same_retained(left: object, right: object) -> bool:
    """Reject normalization and equal-but-differently-typed retained evidence."""
    if type(left) is not type(right) or left != right:
        return False
    if is_dataclass(left) and not isinstance(left, type):
        return all(
            _same_retained(getattr(left, item.name), getattr(right, item.name))
            for item in fields(left)
        )
    if isinstance(left, Mapping):
        return all(
            _same_retained(key, other_key) and _same_retained(value, other_value)
            for (key, value), (other_key, other_value) in zip(
                left.items(), right.items(), strict=True
            )
        )
    if isinstance(left, (tuple, list)):
        return all(
            _same_retained(item, other) for item, other in zip(left, right, strict=True)
        )
    return True


def _retained_precision(value: object) -> int:
    """Enough precision for inherited Decimal.normalize calls to remain exact."""
    if type(value) is Decimal:
        return len(value.as_tuple().digits)
    if is_dataclass(value) and not isinstance(value, type):
        return max(
            (_retained_precision(getattr(value, item.name)) for item in fields(value)),
            default=28,
        )
    if isinstance(value, Mapping):
        return max((_retained_precision(item) for item in value.values()), default=28)
    if isinstance(value, (tuple, list)):
        return max((_retained_precision(item) for item in value), default=28)
    return 28


def _validated_result(result: HistoricalExperimentResult) -> HistoricalExperimentResult:
    if (
        type(result) is not HistoricalExperimentResult
        or type(result.request) is not HistoricalExperimentRequest
    ):
        raise ResearchCandidateShadowBindingError(
            "exact completed historical result/request required"
        )
    if type(result.runs) is not tuple or type(result.request.variants) is not tuple:
        raise ResearchCandidateShadowBindingError("canonical retained tuples required")
    if any(type(run) is not HistoricalExperimentRun for run in result.runs) or any(
        type(variant) is not HistoricalExperimentVariant
        for variant in result.request.variants
    ):
        raise ResearchCandidateShadowBindingError(
            "exact retained run/variant models required"
        )
    validated = _copy_retained(result)
    # Revalidate the historical boundary and retained rolling relationships.
    # The result/run identities commit to complete variant semantics. Historical
    # validation does not re-execute or recertify unrelated legacy leaf adapters.
    with localcontext(Context(prec=_retained_precision(validated))):
        validated.request.__post_init__()
        for run in validated.runs:
            run.variant.__post_init__()
            run.metrics.__post_init__()
            run.rolling_result.request.__post_init__()
            run.rolling_result.__post_init__()
            run.__post_init__()
        validated.__post_init__()
    if not _same_retained(validated, result):
        raise ResearchCandidateShadowBindingError(
            "historical evidence must already be canonical"
        )
    return validated


def _bound_run(
    binding: ResearchCandidateShadowVariantBinding, result: HistoricalExperimentResult
) -> HistoricalExperimentRun:
    for name in (
        "experiment_result_id",
        "experiment_request_id",
        "historical_fingerprint",
        "schedule_fingerprint",
        "initial_state_fingerprint",
    ):
        actual = (
            result.result_id
            if name == "experiment_result_id"
            else result.request.request_id
            if name == "experiment_request_id"
            else getattr(result, name)
        )
        if getattr(binding, name) != actual:
            raise ResearchCandidateShadowBindingError(
                f"historical provenance mismatch: {name}"
            )
    runs = tuple(
        run
        for run in result.runs
        if run.ordinal == binding.caller_ordinal
        and run.variant.variant_id == binding.variant_id
    )
    if len(runs) != 1:
        raise ResearchCandidateShadowBindingError("exactly one bound run required")
    run = runs[0]
    if (
        run.variant.name != binding.variant_name
        or run.run_id != binding.experiment_run_id
        or run.rolling_result.result_id != binding.rolling_result_id
        or run.variant is not result.request.variants[binding.caller_ordinal]
    ):
        raise ResearchCandidateShadowBindingError(
            "bound run/variant provenance mismatch"
        )
    return run


def build_research_candidate_shadow_variant_binding(
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
) -> ResearchCandidateShadowVariantBinding:
    """Independently reconcile the complete chain without any execution."""
    verify_research_candidate_against_report(predecessor, report)
    verify_research_candidate_walk_forward_qualification(
        qualification,
        predecessor,
        report,
        walk_forward_result,
        qualification_policy,
        source_head=qualification_source_head,
        source_tree=qualification_source_tree,
    )
    verify_walk_forward_passed_research_candidate(
        walk_forward_passed, predecessor, qualification
    )
    if (
        qualification.status
        is not ResearchCandidateWalkForwardQualificationStatus.PASSED
    ):
        raise ResearchCandidateShadowBindingError("PASSED qualification required")
    result = _validated_result(historical_experiment_result)
    if (
        result.result_id != predecessor.experiment_result_id
        or result.result_id != report.experiment_result_id
    ):
        raise ResearchCandidateShadowBindingError("original experiment result required")
    rows = tuple(
        row for row in report.variants if row.variant_id == predecessor.variant_id
    )
    if len(rows) != 1:
        raise ResearchCandidateShadowBindingError(
            "exactly one original report row required"
        )
    row = rows[0]
    binding = ResearchCandidateShadowVariantBinding(
        walk_forward_passed.candidate_id,
        predecessor.candidate_id,
        qualification.qualification_id,
        predecessor.source_head,
        predecessor.source_tree,
        qualification_source_head,
        qualification_source_tree,
        binding_source_head,
        binding_source_tree,
        report.report_id,
        report.experiment_request_id,
        result.result_id,
        report.historical_fingerprint,
        report.schedule_fingerprint,
        report.initial_state_fingerprint,
        predecessor.variant_id,
        predecessor.caller_ordinal,
        predecessor.variant_name,
        predecessor.rank,
        row.experiment_run_id,
        row.rolling_result_id,
    )
    run = _bound_run(binding, result)
    if (
        row.caller_ordinal != run.ordinal
        or row.variant_name != run.variant.name
        or row.metrics != run.metrics
    ):
        raise ResearchCandidateShadowBindingError("report/run evidence mismatch")
    return binding


def resolve_bound_research_candidate_variant(
    binding: ResearchCandidateShadowVariantBinding,
    historical_experiment_result: HistoricalExperimentResult,
) -> HistoricalExperimentVariant:
    """Return only the original retained variant from an independently validated result.

    This reconciles the result bridge, not the absent lifecycle/report evidence.
    It grants no execution, compatibility, or SHADOW qualification authority.
    """
    _validate_binding(binding)
    result = _validated_result(historical_experiment_result)
    run = _bound_run(binding, result)
    return historical_experiment_result.request.variants[run.ordinal]


def verify_research_candidate_shadow_variant_binding(
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
) -> None:
    """Recompute the complete external chain; parsing alone cannot substitute."""
    _validate_binding(binding)
    expected = build_research_candidate_shadow_variant_binding(
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
    )
    if binding != expected:
        raise ResearchCandidateShadowBindingError(
            "binding does not reconcile with external evidence"
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResearchCandidateShadowBindingError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchCandidateShadowBindingError("non-JSON constant")


__all__ = [
    "RESEARCH_CANDIDATE_SHADOW_BINDING_SCHEMA",
    "RESEARCH_CANDIDATE_SHADOW_BINDING_IDENTITY_VERSION",
    "RESEARCH_CANDIDATE_SHADOW_BINDING_NAMESPACE",
    "ResearchCandidateShadowBindingError",
    "ResearchCandidateShadowVariantBinding",
    "build_research_candidate_shadow_variant_binding",
    "resolve_bound_research_candidate_variant",
    "verify_research_candidate_shadow_variant_binding",
]
