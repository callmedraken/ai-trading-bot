"""Synthetic local evidence; parser/linkage scope never proves external history."""

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from trading_bot.experiments.research_candidate import ResearchStrategyCandidate
from trading_bot.experiments.research_candidate_shadow_binding import (
    ResearchCandidateShadowVariantBinding,
)
from trading_bot.experiments.research_candidate_shadow_observation import (
    SHADOW_ZERO_EFFECT_FIELDS,
    ResearchCandidateShadowObservation,
    ResearchCandidateShadowObservationBatch,
)
from trading_bot.experiments.research_candidate_shadow_qualification import (
    ResearchCandidateShadowQualification,
    ResearchCandidateShadowQualificationPolicy,
    build_shadow_research_candidate,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    WalkForwardPassedResearchStrategyCandidate,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    LOCAL_VERIFICATION_SCOPE,
    LifecycleQualificationStatus,
    LifecycleQualificationView,
    LifecycleSourceView,
    LifecycleZeroEffectsView,
    ResearchCandidateLifecycleView,
    unavailable_research_candidate_lifecycle_state,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecycleDiagnostic as Diagnostic,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageState as State,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageStatus as Status,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecycleStage as Stage,
)
from trading_bot.gui.research_candidate_lifecycle_service import (
    ResearchCandidateLifecycleInspectionService,
)

CONFIG_FIELDS = (
    "research_walk_forward_candidate",
    "research_shadow_binding",
    "research_shadow_observation_batch",
    "research_shadow_qualification",
    "research_shadow_candidate",
)


def local_artifacts(seed=0, rank=2):
    """Canonical, linked synthetic objects without external research execution."""
    facts = dict(
        source_head="a" * 40,
        source_tree="b" * 40,
        report_id=UUID(int=1 + seed),
        experiment_result_id=UUID(int=2 + seed),
        variant_id=UUID(int=3 + seed),
        caller_ordinal=1,
        variant_name="Synthetic variant <read-only>",
        rank=rank,
    )
    backtested = ResearchStrategyCandidate(**facts)
    walk = WalkForwardPassedResearchStrategyCandidate(
        backtested.candidate_id, UUID(int=4 + seed), **facts
    )
    binding = ResearchCandidateShadowVariantBinding(
        walk.candidate_id,
        backtested.candidate_id,
        walk.qualification_id,
        facts["source_head"],
        facts["source_tree"],
        "c" * 40,
        "d" * 40,
        "e" * 40,
        "f" * 40,
        facts["report_id"],
        UUID(int=5 + seed),
        facts["experiment_result_id"],
        UUID(int=6 + seed),
        UUID(int=7 + seed),
        UUID(int=8 + seed),
        facts["variant_id"],
        facts["caller_ordinal"],
        facts["variant_name"],
        rank,
        UUID(int=9 + seed),
        UUID(int=10 + seed),
    )
    observations = tuple(
        ResearchCandidateShadowObservation(
            binding.binding_id,
            date(2026, 1, 2) + timedelta(days=session),
            datetime(2026, 1, 2, 15, 0, 0, 123456, tzinfo=UTC)
            + timedelta(days=session, minutes=ordinal),
            ordinal,
            UUID(int=11 + seed),
            UUID(int=12 + seed),
            **dict.fromkeys(SHADOW_ZERO_EFFECT_FIELDS, 0),
        )
        for session, count in enumerate((2, 3))
        for ordinal in range(count)
    )
    batch = ResearchCandidateShadowObservationBatch(
        binding.binding_id, "1" * 40, "2" * 40, observations
    )
    qualification = ResearchCandidateShadowQualification(
        binding.binding_id,
        batch.observation_batch_id,
        ResearchCandidateShadowQualificationPolicy(2, 4, 2),
        "3" * 40,
        "4" * 40,
        5,
        2,
        2,
    )
    shadow = build_shadow_research_candidate(walk, binding, batch, qualification)
    return walk, binding, batch, qualification, shadow


def write_artifacts(tmp_path, artifacts=None):
    artifacts = local_artifacts() if artifacts is None else artifacts
    paths = tuple(tmp_path / f"selected-{index}.json" for index in range(5))
    for path, artifact in zip(paths, artifacts, strict=True):
        path.write_text(artifact.to_json(), encoding="utf-8")
    return paths


def available_state(tmp_path):
    return ResearchCandidateLifecycleInspectionService(
        *write_artifacts(tmp_path)
    ).get_research_candidate_lifecycle_state()


def test_closed_status_and_scope_vocabulary():
    assert [s.value for s in Status] == ["UNAVAILABLE", "AVAILABLE", "ATTENTION"]
    assert list(Stage) == [Stage.SHADOW]
    assert list(LifecycleQualificationStatus) == [LifecycleQualificationStatus.PASSED]
    assert LOCAL_VERIFICATION_SCOPE == (
        "Canonical local artifacts and SHADOW successor linkage verified. "
        "Full historical external-chain qualification was not re-run by this GUI."
    )


def test_complete_frozen_slotted_values_and_fixed_governance(tmp_path):
    state = available_state(tmp_path)
    assert state.status is Status.AVAILABLE
    e = state.evidence
    assert type(e) is ResearchCandidateLifecycleView
    for value in (
        state,
        e,
        e.candidate_source,
        e.observations,
        e.qualification,
        e.observations.zero_effects,
    ):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)
    for name, value in (
        ("automatic_promotion_enabled", False),
        ("human_promotion_required", True),
        ("promotion_authority_connected", False),
        ("can_research_replace_production", False),
        ("full_external_research_chain_verified_by_gui", False),
    ):
        assert getattr(state, name) is value
        with pytest.raises(TypeError):
            State(Status.AVAILABLE, Diagnostic.LOCAL_LINKAGE, e, **{name: not value})
    with pytest.raises(TypeError):
        replace(e, stage="PAPER_CANDIDATE")


@pytest.mark.parametrize(
    "status,diagnostic",
    [
        (Status.UNAVAILABLE, Diagnostic.NOT_CONFIGURED),
        (Status.ATTENTION, Diagnostic.INVALID),
    ],
)
def test_empty_states_have_only_fixed_bounded_diagnostics(tmp_path, status, diagnostic):
    state = State(status, diagnostic)
    assert state.evidence is None and len(state.message) < 512
    with pytest.raises(ValueError):
        State(status, diagnostic, available_state(tmp_path).evidence)
    with pytest.raises(TypeError):
        State(status, "C:\\private\\raw.json traceback")
    assert unavailable_research_candidate_lifecycle_state() == State(
        Status.UNAVAILABLE, Diagnostic.NOT_CONFIGURED
    )


@pytest.mark.parametrize(
    "status,diagnostic",
    [
        ("AVAILABLE", Diagnostic.LOCAL_LINKAGE),
        (Status.AVAILABLE, "LOCAL_LINKAGE"),
        (Status.AVAILABLE, Diagnostic.INVALID),
        (Status.AVAILABLE, Diagnostic.LOCAL_LINKAGE),
    ],
)
def test_exact_status_and_available_requires_complete_evidence(status, diagnostic):
    with pytest.raises((TypeError, ValueError)):
        State(status, diagnostic)


@pytest.mark.parametrize("digest", ["A" * 40, "a" * 39, "g" * 40, "a" * 41, True, None])
def test_exact_source_digests(digest):
    with pytest.raises(ValueError):
        LifecycleSourceView(digest, "b" * 40)
    with pytest.raises(ValueError):
        LifecycleSourceView("a" * 40, digest)


@pytest.mark.parametrize(
    "field",
    [f.name for f in fields(ResearchCandidateLifecycleView) if f.name.endswith("_id")],
)
def test_exact_uuid_fields(tmp_path, field):
    e = available_state(tmp_path).evidence
    with pytest.raises(TypeError):
        replace(e, **{field: str(getattr(e, field))})


@pytest.mark.parametrize("value", [True, False, -1, 1_000_001, 1.0, "1", None])
def test_exact_ordinal(tmp_path, value):
    with pytest.raises(ValueError):
        replace(available_state(tmp_path).evidence, caller_ordinal=value)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1_000_001, 1.0, "1"])
def test_invalid_rank(tmp_path, value):
    with pytest.raises(ValueError):
        replace(available_state(tmp_path).evidence, rank=value)


@pytest.mark.parametrize("value", [None, 1, 1_000_000])
def test_retained_rank_is_only_evidence(tmp_path, value):
    e = available_state(tmp_path).evidence
    assert replace(e, rank=value).rank == value


@pytest.mark.parametrize(
    "value", ["", " ", " untrimmed", "x" * 257, "bad\nname", "bad\x7fname", "\ud800", 1]
)
def test_bounded_variant_text(tmp_path, value):
    with pytest.raises((ValueError, UnicodeError)):
        replace(available_state(tmp_path).evidence, variant_name=value)


@pytest.mark.parametrize("name", SHADOW_ZERO_EFFECT_FIELDS)
@pytest.mark.parametrize("value", [True, False, 1, -1, 0.0, "0"])
def test_exact_zero_effect_counters(name, value):
    with pytest.raises(ValueError):
        LifecycleZeroEffectsView(
            **(dict.fromkeys(SHADOW_ZERO_EFFECT_FIELDS, 0) | {name: value})
        )


def test_exact_b1_b2_presentation_and_sources(tmp_path):
    walk, binding, batch, q, shadow = local_artifacts()
    e = available_state(tmp_path).evidence
    assert (
        e.shadow_candidate_id,
        e.walk_forward_passed_candidate_id,
        e.backtested_candidate_id,
    ) == (shadow.candidate_id, walk.candidate_id, walk.predecessor_candidate_id)
    assert (
        e.walk_forward_qualification_id,
        e.binding_id,
        e.observation_batch_id,
        e.qualification_id,
    ) == (
        walk.qualification_id,
        binding.binding_id,
        batch.observation_batch_id,
        q.qualification_id,
    )
    assert (
        e.report_id,
        e.experiment_result_id,
        e.variant_id,
        e.caller_ordinal,
        e.variant_name,
        e.rank,
    ) == (
        shadow.report_id,
        shadow.experiment_result_id,
        shadow.variant_id,
        1,
        shadow.variant_name,
        2,
    )
    for name, head, tree in (
        ("candidate_source", "a", "b"),
        ("walk_forward_qualification_source", "c", "d"),
        ("binding_source", "e", "f"),
        ("observation_source", "1", "2"),
        ("qualification_source", "3", "4"),
    ):
        assert getattr(e, name) == LifecycleSourceView(head * 40, tree * 40)
    o = e.observations
    assert (o.observation_count, o.distinct_session_count) == (5, 2)
    assert (o.first_session_date, o.last_session_date) == (
        date(2026, 1, 2),
        date(2026, 1, 3),
    )
    assert (o.first_observed_at_utc, o.last_observed_at_utc) == (
        batch.observations[0].observed_at_utc,
        batch.observations[-1].observed_at_utc,
    )
    assert all(
        type(getattr(o.zero_effects, name)) is int
        and getattr(o.zero_effects, name) == 0
        for name in SHADOW_ZERO_EFFECT_FIELDS
    )
    assert e.qualification == LifecycleQualificationView(
        2, 4, 2, 5, 2, 2, LifecycleQualificationStatus.PASSED, ()
    )


@pytest.mark.parametrize(
    "field",
    [
        "minimum_session_count",
        "minimum_total_observation_count",
        "minimum_observations_per_session",
        "observation_count",
        "distinct_session_count",
        "minimum_observations_in_any_session",
    ],
)
@pytest.mark.parametrize("value", [True, 0, 100001, "2"])
def test_exact_qualification_counts(tmp_path, field, value):
    with pytest.raises(ValueError):
        replace(available_state(tmp_path).evidence.qualification, **{field: value})


def test_summary_rejects_wrong_types_ranges_and_conflicts(tmp_path):
    e = available_state(tmp_path).evidence
    for changes in (
        {"first_session_date": datetime.now(UTC)},
        {"last_observed_at_utc": datetime(2026, 1, 2)},
        {"observation_count": True},
        {"distinct_session_count": 6},
        {"first_session_date": date(2026, 1, 4)},
        {"zero_effects": None},
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(e.observations, **changes)
    for changes in (
        {"status": "PASSED"},
        {"failure_reasons": []},
        {"failure_reasons": ("failure",)},
        {"minimum_session_count": 3},
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(e.qualification, **changes)
    for changes in (
        {"candidate_source": None},
        {"observations": None},
        {"qualification": None},
        {"observations": replace(e.observations, observation_count=6)},
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(e, **changes)
