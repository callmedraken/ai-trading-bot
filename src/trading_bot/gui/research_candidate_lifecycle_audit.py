"""Pure presentation of the already acquired local lifecycle evidence."""

from dataclasses import dataclass, fields

from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageState,
)

COVERAGE_NOTICE = (
    "Margins are coverage headroom only; they do not represent profitability, "
    "alpha, strategy quality, trading quality, confidence, or production readiness."
)
ZERO_EFFECT_NOTICE = (
    "Recorded observation effect invariant: all nine counters are zero. "
    "This recorded evidence grants no operational authority or external "
    "observation-origin claim."
)


@dataclass(frozen=True, slots=True)
class LifecycleAuditRow:
    label: str
    value: str

    def __post_init__(self) -> None:
        if type(self.label) is not str or type(self.value) is not str:
            raise TypeError("Exact presentation text required")


@dataclass(frozen=True, slots=True)
class LifecycleProvenanceRow:
    label: str
    head: str
    tree: str

    def __post_init__(self) -> None:
        if any(type(value) is not str for value in (self.label, self.head, self.tree)):
            raise TypeError("Exact retained provenance text required")


@dataclass(frozen=True, slots=True)
class LifecycleCoverageRow:
    metric: str
    required: int
    recorded: int

    def __post_init__(self) -> None:
        if type(self.metric) is not str:
            raise TypeError("Exact metric text required")
        if (
            type(self.required) is not int
            or type(self.recorded) is not int
            or self.required < 1
            or self.recorded < self.required
        ):
            raise ValueError("Exact positive counts and nonnegative headroom required")

    @property
    def margin(self) -> int:
        return self.recorded - self.required


@dataclass(frozen=True, slots=True)
class LifecycleAuditPresentation:
    artifacts: tuple[LifecycleAuditRow, ...] = ()
    supporting: tuple[LifecycleAuditRow, ...] = ()
    provenance: tuple[LifecycleProvenanceRow, ...] = ()
    coverage: tuple[LifecycleCoverageRow, ...] = ()
    effects: tuple[LifecycleAuditRow, ...] = ()
    governance: tuple[LifecycleAuditRow, ...] = ()

    def __post_init__(self) -> None:
        for name, row_type in (
            ("artifacts", LifecycleAuditRow),
            ("supporting", LifecycleAuditRow),
            ("provenance", LifecycleProvenanceRow),
            ("coverage", LifecycleCoverageRow),
            ("effects", LifecycleAuditRow),
            ("governance", LifecycleAuditRow),
        ):
            rows = getattr(self, name)
            if type(rows) is not tuple or any(
                type(row) is not row_type for row in rows
            ):
                raise TypeError("Exact immutable presentation rows required")


def compose_lifecycle_audit(
    state: ResearchCandidateLifecyclePageState,
) -> LifecycleAuditPresentation:
    """Compose retained facts only, without acquiring or verifying artifacts."""
    if type(state) is not ResearchCandidateLifecyclePageState:
        raise TypeError("Exact lifecycle page state required")
    evidence = state.evidence
    if evidence is None:
        return LifecycleAuditPresentation()
    qualification = evidence.qualification
    return LifecycleAuditPresentation(
        artifacts=tuple(
            LifecycleAuditRow(label, str(value))
            for label, value in evidence.artifact_identifiers
        ),
        supporting=tuple(
            LifecycleAuditRow(label, str(value))
            for label, value in (
                ("BACKTESTED ancestor candidate ID", evidence.backtested_candidate_id),
                (
                    "Walk-forward qualification ID",
                    evidence.walk_forward_qualification_id,
                ),
                ("Report ID", evidence.report_id),
                ("Experiment result ID", evidence.experiment_result_id),
                ("Variant ID", evidence.variant_id),
                ("Caller ordinal", evidence.caller_ordinal),
                ("Variant name", evidence.variant_name),
                (
                    "Original rank",
                    "Unranked" if evidence.rank is None else evidence.rank,
                ),
            )
        ),
        provenance=tuple(
            LifecycleProvenanceRow(label, source.head, source.tree)
            for label, source in (
                ("Candidate", evidence.candidate_source),
                (
                    "Walk-forward qualification",
                    evidence.walk_forward_qualification_source,
                ),
                ("139-A binding", evidence.binding_source),
                ("B1 observation", evidence.observation_source),
                ("B2 qualification", evidence.qualification_source),
            )
        ),
        coverage=(
            LifecycleCoverageRow(
                "Sessions",
                qualification.minimum_session_count,
                qualification.distinct_session_count,
            ),
            LifecycleCoverageRow(
                "Total observations",
                qualification.minimum_total_observation_count,
                qualification.observation_count,
            ),
            LifecycleCoverageRow(
                "Minimum per session",
                qualification.minimum_observations_per_session,
                qualification.minimum_observations_in_any_session,
            ),
        ),
        effects=tuple(
            LifecycleAuditRow(
                item.name.upper(),
                str(getattr(evidence.observations.zero_effects, item.name)),
            )
            for item in fields(evidence.observations.zero_effects)
        ),
        governance=tuple(
            LifecycleAuditRow(label, value)
            for label, value in (
                ("Stage", evidence.stage.value),
                ("Local canonical artifacts", "Verified"),
                ("Local SHADOW linkage", "Verified"),
                ("Full historical chain", "Not re-run by this GUI"),
                ("Real observation acquisition", "Not connected"),
                ("Automatic promotion", "Disabled"),
                ("Promotion authority", "Not connected"),
                ("Production compatibility", "Not established"),
                ("PAPER_CANDIDATE", "Not materialized"),
                ("AWAITING_HUMAN_PROMOTION", "Not materialized"),
                ("Trading authority", "None"),
            )
        ),
    )
