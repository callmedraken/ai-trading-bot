"""Five explicit bounded local reads, canonical parsers and exact local linkage."""

from dataclasses import fields
from pathlib import Path, PureWindowsPath

from trading_bot.experiments.research_candidate_shadow_binding import (
    ResearchCandidateShadowVariantBinding,
)
from trading_bot.experiments.research_candidate_shadow_observation import (
    ResearchCandidateShadowObservationBatch,
)
from trading_bot.experiments.research_candidate_shadow_qualification import (
    ResearchCandidateShadowQualification,
    ShadowResearchStrategyCandidate,
    verify_shadow_research_candidate,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    WalkForwardPassedResearchStrategyCandidate,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    LifecycleObservationView,
    LifecycleQualificationStatus,
    LifecycleQualificationView,
    LifecycleSourceView,
    LifecycleZeroEffectsView,
    ResearchCandidateLifecycleDiagnostic,
    ResearchCandidateLifecyclePageState,
    ResearchCandidateLifecyclePageStatus,
    ResearchCandidateLifecycleView,
)

MAX_LIFECYCLE_ARTIFACT_BYTES = 8 * 1024 * 1024


class ResearchCandidateLifecycleInspectionService:
    """Cache success or failure; never retain raw payloads or domain artifacts."""

    def __init__(
        self,
        walk_forward_candidate: Path,
        shadow_binding: Path,
        shadow_observation_batch: Path,
        shadow_qualification: Path,
        shadow_candidate: Path,
    ) -> None:
        self._paths = (
            walk_forward_candidate,
            shadow_binding,
            shadow_observation_batch,
            shadow_qualification,
            shadow_candidate,
        )
        if any(not isinstance(path, Path) for path in self._paths):
            raise TypeError("Five explicit Paths required")
        self._cached: ResearchCandidateLifecyclePageState | None = None

    def get_research_candidate_lifecycle_state(
        self,
    ) -> ResearchCandidateLifecyclePageState:
        if self._cached is None:
            self._cached = self._acquire()
        return self._cached

    def _acquire(self) -> ResearchCandidateLifecyclePageState:
        try:
            for path in self._paths:
                _validate_local_path(path)
            # Exact text goes straight to accepted parsers, without normalization.
            walk_forward = WalkForwardPassedResearchStrategyCandidate.from_json(
                _read_text(self._paths[0])
            )
            binding = ResearchCandidateShadowVariantBinding.from_json(
                _read_text(self._paths[1])
            )
            batch = ResearchCandidateShadowObservationBatch.from_json(
                _read_text(self._paths[2])
            )
            qualification = ResearchCandidateShadowQualification.from_json(
                _read_text(self._paths[3])
            )
            shadow = ShadowResearchStrategyCandidate.from_json(
                _read_text(self._paths[4])
            )
            verify_shadow_research_candidate(
                shadow, walk_forward, binding, batch, qualification
            )
            return ResearchCandidateLifecyclePageState(
                ResearchCandidateLifecyclePageStatus.AVAILABLE,
                ResearchCandidateLifecycleDiagnostic.LOCAL_LINKAGE,
                _adapt(shadow, batch, qualification),
            )
        except Exception:
            # An inspection boundary must never leak payloads, paths or parser
            # exceptions into presentation state, including unexpected failures.
            return ResearchCandidateLifecyclePageState(
                ResearchCandidateLifecyclePageStatus.ATTENTION,
                ResearchCandidateLifecycleDiagnostic.INVALID,
            )


def _validate_local_path(path: Path) -> None:
    text = str(path)
    windows = PureWindowsPath(text)
    if (
        path.suffix.casefold() != ".json"
        or text.startswith(("\\\\", "//"))
        or any(ord(char) < 32 or ord(char) == 127 for char in text)
        or ":" in text[len(windows.drive) :]
        or (windows.drive and (len(windows.drive) != 2 or not windows.root))
    ):
        raise ValueError("Unsupported explicit local JSON path")


def _read_text(path: Path) -> str:
    with path.open("rb") as stream:
        payload = stream.read(MAX_LIFECYCLE_ARTIFACT_BYTES + 1)
    if len(payload) > MAX_LIFECYCLE_ARTIFACT_BYTES:
        raise ValueError("Lifecycle artifact exceeds GUI inspection bound")
    return payload.decode("utf-8", errors="strict")


def _adapt(
    shadow: ShadowResearchStrategyCandidate,
    batch: ResearchCandidateShadowObservationBatch,
    qualification: ResearchCandidateShadowQualification,
) -> ResearchCandidateLifecycleView:
    observations = batch.observations
    policy = qualification.policy
    return ResearchCandidateLifecycleView(
        shadow_candidate_id=shadow.candidate_id,
        walk_forward_passed_candidate_id=shadow.predecessor_candidate_id,
        backtested_candidate_id=shadow.backtested_candidate_id,
        walk_forward_qualification_id=shadow.walk_forward_qualification_id,
        binding_id=shadow.binding_id,
        observation_batch_id=shadow.observation_batch_id,
        qualification_id=shadow.qualification_id,
        report_id=shadow.report_id,
        experiment_result_id=shadow.experiment_result_id,
        variant_id=shadow.variant_id,
        caller_ordinal=shadow.caller_ordinal,
        variant_name=shadow.variant_name,
        rank=shadow.rank,
        candidate_source=LifecycleSourceView(shadow.source_head, shadow.source_tree),
        walk_forward_qualification_source=LifecycleSourceView(
            shadow.walk_forward_qualification_source_head,
            shadow.walk_forward_qualification_source_tree,
        ),
        binding_source=LifecycleSourceView(
            shadow.binding_source_head, shadow.binding_source_tree
        ),
        observation_source=LifecycleSourceView(
            shadow.observation_source_head, shadow.observation_source_tree
        ),
        qualification_source=LifecycleSourceView(
            shadow.qualification_source_head, shadow.qualification_source_tree
        ),
        observations=LifecycleObservationView(
            batch.observation_count,
            len({item.session_date for item in observations}),
            observations[0].session_date,
            observations[-1].session_date,
            observations[0].observed_at_utc,
            observations[-1].observed_at_utc,
            LifecycleZeroEffectsView(
                **{
                    item.name: getattr(batch, item.name)
                    for item in fields(LifecycleZeroEffectsView)
                }
            ),
        ),
        qualification=LifecycleQualificationView(
            policy.minimum_session_count,
            policy.minimum_total_observation_count,
            policy.minimum_observations_per_session,
            qualification.observation_count,
            qualification.distinct_session_count,
            qualification.minimum_observations_in_any_session,
            LifecycleQualificationStatus(qualification.status.value),
            tuple(reason.value for reason in qualification.failure_reasons),
        ),
    )
