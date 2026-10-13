"""Pure research evidence for one explicitly selected completed report variant.

Canonical parsing proves self-consistency only. External report evidence requires
verify_research_candidate_against_report; neither operation grants promotion or
production authority.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.experiments.exceptions import HistoricalExperimentError
from trading_bot.experiments.report import HistoricalExperimentReport

RESEARCH_CANDIDATE_SCHEMA = "research-strategy-candidate/v1"
RESEARCH_CANDIDATE_IDENTITY_VERSION = "research-strategy-candidate-identity/v1"
MAX_RESEARCH_CANDIDATE_ORDINAL = 1_000_000
MAX_RESEARCH_CANDIDATE_RANK = 1_000_000
MAX_RESEARCH_CANDIDATE_NAME_LENGTH = 256
_NAMESPACE = UUID("c914e214-9553-56ce-978a-ddd33bf6210f")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_FIELDS = frozenset(
    {
        "schema",
        "candidate_id",
        "stage",
        "source_head",
        "source_tree",
        "report_id",
        "experiment_result_id",
        "variant_id",
        "caller_ordinal",
        "variant_name",
        "rank",
    }
)


class ResearchCandidateStage(StrEnum):
    """Conceptual ordering only; reserved stages grant no transition authority."""

    EXPERIMENTAL = "EXPERIMENTAL"
    BACKTESTED = "BACKTESTED"
    WALK_FORWARD_PASSED = "WALK_FORWARD_PASSED"
    SHADOW = "SHADOW"
    PAPER_CANDIDATE = "PAPER_CANDIDATE"
    AWAITING_HUMAN_PROMOTION = "AWAITING_HUMAN_PROMOTION"


class ResearchCandidateError(HistoricalExperimentError, ValueError):
    """Malformed candidate or inconsistent external report evidence."""


def _semantic_material(candidate: ResearchStrategyCandidate) -> str:
    if (
        type(candidate.schema) is not str
        or candidate.schema != RESEARCH_CANDIDATE_SCHEMA
    ):
        raise ResearchCandidateError("invalid candidate schema")
    if (
        type(candidate.stage) is not ResearchCandidateStage
        or candidate.stage is not ResearchCandidateStage.BACKTESTED
    ):
        raise ResearchCandidateError("only BACKTESTED may be materialized")
    for name in ("source_head", "source_tree"):
        value = getattr(candidate, name)
        if type(value) is not str or _SHA40.fullmatch(value) is None:
            raise ResearchCandidateError(f"{name} must be exact lowercase 40-hex")
    for name in ("report_id", "experiment_result_id", "variant_id"):
        if type(getattr(candidate, name)) is not UUID:
            raise ResearchCandidateError(f"{name} must be exactly UUID")
    if (
        type(candidate.caller_ordinal) is not int
        or not 0 <= candidate.caller_ordinal <= MAX_RESEARCH_CANDIDATE_ORDINAL
    ):
        raise ResearchCandidateError("caller_ordinal must be a bounded nonnegative int")
    name = candidate.variant_name
    if (
        type(name) is not str
        or not name
        or name != name.strip()
        or len(name) > MAX_RESEARCH_CANDIDATE_NAME_LENGTH
    ):
        raise ResearchCandidateError(
            "variant_name must be bounded canonical nonblank text"
        )
    if candidate.rank is not None and (
        type(candidate.rank) is not int
        or not 1 <= candidate.rank <= MAX_RESEARCH_CANDIDATE_RANK
    ):
        raise ResearchCandidateError("rank must be a bounded positive int or None")
    values = (
        RESEARCH_CANDIDATE_IDENTITY_VERSION,
        candidate.schema,
        candidate.stage.value,
        candidate.source_head,
        candidate.source_tree,
        str(candidate.report_id),
        str(candidate.experiment_result_id),
        str(candidate.variant_id),
        str(candidate.caller_ordinal),
        candidate.variant_name,
        "none" if candidate.rank is None else str(candidate.rank),
    )
    try:
        return "".join(f"{len(value.encode('utf-8'))}:{value}" for value in values)
    except UnicodeError:
        raise ResearchCandidateError("variant_name must be UTF-8 text") from None


@dataclass(frozen=True, slots=True)
class ResearchStrategyCandidate:
    """An inert BACKTESTED declaration, without external-evidence verification."""

    source_head: str
    source_tree: str
    report_id: UUID
    experiment_result_id: UUID
    variant_id: UUID
    caller_ordinal: int
    variant_name: str
    rank: int | None
    schema: str = field(default=RESEARCH_CANDIDATE_SCHEMA, init=False)
    stage: ResearchCandidateStage = field(
        default=ResearchCandidateStage.BACKTESTED, init=False
    )
    candidate_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_id", uuid5(_NAMESPACE, _semantic_material(self))
        )

    def to_json(self) -> str:
        """Return compact, sorted, canonical JSON after revalidating identity."""
        _validate_candidate(self)
        return json.dumps(
            {
                "schema": self.schema,
                "candidate_id": str(self.candidate_id),
                "stage": self.stage.value,
                "source_head": self.source_head,
                "source_tree": self.source_tree,
                "report_id": str(self.report_id),
                "experiment_result_id": str(self.experiment_result_id),
                "variant_id": str(self.variant_id),
                "caller_ordinal": self.caller_ordinal,
                "variant_name": self.variant_name,
                "rank": self.rank,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, value: str) -> ResearchStrategyCandidate:
        """Parse self-consistent canonical bytes; does not verify an external report."""
        try:
            if cls is not ResearchStrategyCandidate or type(value) is not str:
                raise ResearchCandidateError("exact candidate JSON required")
            raw = json.loads(
                value, object_pairs_hook=_unique_object, parse_constant=_reject_constant
            )
            if type(raw) is not dict or set(raw) != _FIELDS:
                raise ResearchCandidateError("exact candidate fields required")
            if (
                raw["schema"] != RESEARCH_CANDIDATE_SCHEMA
                or raw["stage"] != ResearchCandidateStage.BACKTESTED.value
            ):
                raise ResearchCandidateError("invalid schema or stage")
            result = cls(
                source_head=raw["source_head"],
                source_tree=raw["source_tree"],
                report_id=_parse_uuid(raw["report_id"]),
                experiment_result_id=_parse_uuid(raw["experiment_result_id"]),
                variant_id=_parse_uuid(raw["variant_id"]),
                caller_ordinal=raw["caller_ordinal"],
                variant_name=raw["variant_name"],
                rank=raw["rank"],
            )
            if (
                _parse_uuid(raw["candidate_id"]) != result.candidate_id
                or result.to_json() != value
            ):
                raise ResearchCandidateError("noncanonical or inconsistent candidate")
            return result
        except (TypeError, ValueError, UnicodeError):
            raise ResearchCandidateError("invalid research candidate JSON") from None


def _validate_candidate(candidate: ResearchStrategyCandidate) -> None:
    if type(candidate) is not ResearchStrategyCandidate:
        raise ResearchCandidateError(
            "candidate must be exactly ResearchStrategyCandidate"
        )
    expected = uuid5(_NAMESPACE, _semantic_material(candidate))
    if type(candidate.candidate_id) is not UUID or candidate.candidate_id != expected:
        raise ResearchCandidateError("candidate_id is inconsistent")


def _validated_report(report: HistoricalExperimentReport) -> HistoricalExperimentReport:
    if type(report) is not HistoricalExperimentReport:
        raise ResearchCandidateError(
            "report must be exactly HistoricalExperimentReport"
        )
    # Report revalidation normalizes nested rows. Work on a copy so even invalid
    # input cannot alter caller evidence; reject any normalized/noncanonical input.
    validated = deepcopy(report)
    validated.__post_init__()
    if validated != report:
        raise ResearchCandidateError("report fields must already be canonical")
    return validated


def build_backtested_research_candidate(
    report: HistoricalExperimentReport,
    *,
    selected_variant_id: UUID,
    source_head: str,
    source_tree: str,
) -> ResearchStrategyCandidate:
    """Declare only the exact variant explicitly selected by the caller."""
    report = _validated_report(report)
    if type(selected_variant_id) is not UUID:
        raise ResearchCandidateError("selected_variant_id must be exactly UUID")
    rows = tuple(
        row for row in report.variants if row.variant_id == selected_variant_id
    )
    if len(rows) != 1:
        raise ResearchCandidateError("exactly one matching report variant required")
    row = rows[0]
    return ResearchStrategyCandidate(
        source_head=source_head,
        source_tree=source_tree,
        report_id=report.report_id,
        experiment_result_id=report.experiment_result_id,
        variant_id=row.variant_id,
        caller_ordinal=row.caller_ordinal,
        variant_name=row.variant_name,
        rank=row.rank,
    )


def verify_research_candidate_against_report(
    candidate: ResearchStrategyCandidate, report: HistoricalExperimentReport
) -> None:
    """Require independent exact agreement with the supplied canonical report."""
    _validate_candidate(candidate)
    expected = build_backtested_research_candidate(
        report,
        selected_variant_id=candidate.variant_id,
        source_head=candidate.source_head,
        source_tree=candidate.source_tree,
    )
    if candidate != expected:
        raise ResearchCandidateError(
            "candidate does not reconcile with report evidence"
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ResearchCandidateError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchCandidateError("non-JSON constant")


def _parse_uuid(value: object) -> UUID:
    if type(value) is not str:
        raise ResearchCandidateError("canonical UUID string required")
    parsed = UUID(value)
    if str(parsed) != value:
        raise ResearchCandidateError("canonical UUID string required")
    return parsed


__all__ = [
    "MAX_RESEARCH_CANDIDATE_NAME_LENGTH",
    "MAX_RESEARCH_CANDIDATE_ORDINAL",
    "MAX_RESEARCH_CANDIDATE_RANK",
    "RESEARCH_CANDIDATE_IDENTITY_VERSION",
    "RESEARCH_CANDIDATE_SCHEMA",
    "ResearchCandidateError",
    "ResearchCandidateStage",
    "ResearchStrategyCandidate",
    "build_backtested_research_candidate",
    "verify_research_candidate_against_report",
]
