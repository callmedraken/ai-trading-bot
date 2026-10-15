"""Synthetic deterministic SHADOW coverage and lineage, without acquisition."""

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from tests.experiments.test_research_candidate_shadow_binding import (
    _chain,
    _reidentify_report,
    deepcopy,
)
from tests.experiments.test_research_candidate_shadow_binding import binding as binding
from tests.experiments.test_research_candidate_shadow_binding import chain as chain
from tests.experiments.test_research_candidate_shadow_binding import (
    completed as completed,
)
from tests.experiments.test_research_candidate_shadow_observation import (
    SOURCE,
    observation,
)

from trading_bot import experiments
from trading_bot.experiments import research_candidate_shadow_observation as b1
from trading_bot.experiments import research_candidate_shadow_qualification as m
from trading_bot.experiments.research_candidate import (
    ResearchCandidateStage,
    ResearchStrategyCandidate,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    build_research_candidate_shadow_variant_binding,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    WalkForwardPassedResearchStrategyCandidate,
)

Policy = m.ResearchCandidateShadowQualificationPolicy
Qualification = m.ResearchCandidateShadowQualification
Shadow = m.ShadowResearchStrategyCandidate
Status = m.ResearchCandidateShadowQualificationStatus
Reason = m.ResearchCandidateShadowFailureReason
Error = m.ResearchCandidateShadowQualificationError
Q_SOURCE = dict(
    shadow_qualification_source_head="c" * 40, shadow_qualification_source_tree="d" * 40
)


def observations(binding_id, counts=(2, 2)):
    return tuple(
        observation(
            binding_id,
            ordinal=ordinal,
            day=date(2026, 1, 2) + timedelta(days=session),
            observed_at_utc=datetime(2026, 1, 2, 15, tzinfo=UTC)
            + timedelta(days=session, minutes=ordinal),
        )
        for session, count in enumerate(counts)
        for ordinal in range(count)
    )


def evidence(binding, chain, counts=(2, 2), policy=None):
    items = observations(binding.binding_id, counts)
    batch = b1.build_research_candidate_shadow_observation_batch(
        binding, **chain, observations=items, **SOURCE
    )
    policy = Policy(2, 4, 2) if policy is None else policy
    qualification = m.qualify_research_candidate_shadow(
        binding, batch, policy, **chain, observations=items, **SOURCE, **Q_SOURCE
    )
    return items, batch, qualification


def local_qualification(**changes):
    values = dict(
        binding_id=UUID(int=1),
        observation_batch_id=UUID(int=2),
        policy=Policy(1, 1, 1),
        qualification_source_head="a" * 40,
        qualification_source_tree="b" * 40,
        observation_count=8,
        distinct_session_count=2,
        minimum_observations_in_any_session=2,
    )
    values.update(changes)
    return Qualification(**values)


def local_shadow(**changes):
    values = dict(
        source_head="a" * 40,
        source_tree="b" * 40,
        report_id=UUID(int=1),
        experiment_result_id=UUID(int=2),
        variant_id=UUID(int=3),
        caller_ordinal=0,
        variant_name="Strategy Ã©",
        rank=2,
    )
    for key in tuple(values):
        if key in changes:
            values[key] = changes.pop(key)
    candidate = ResearchStrategyCandidate(**values)
    prior_qualification_id = changes.pop("walk_forward_qualification_id", UUID(int=4))
    predecessor = WalkForwardPassedResearchStrategyCandidate(
        candidate.candidate_id, prior_qualification_id, **values
    )
    more = dict(
        predecessor_candidate_id=predecessor.candidate_id,
        backtested_candidate_id=candidate.candidate_id,
        walk_forward_qualification_id=prior_qualification_id,
        binding_id=UUID(int=5),
        observation_batch_id=UUID(int=6),
        qualification_id=UUID(int=7),
        walk_forward_qualification_source_head="c" * 40,
        walk_forward_qualification_source_tree="d" * 40,
        binding_source_head="e" * 40,
        binding_source_tree="f" * 40,
        observation_source_head="1" * 40,
        observation_source_tree="2" * 40,
        qualification_source_head="3" * 40,
        qualification_source_tree="4" * 40,
    )
    more.update(changes)
    return Shadow(**more, **values)


@pytest.mark.parametrize(
    "field",
    [
        "minimum_session_count",
        "minimum_total_observation_count",
        "minimum_observations_per_session",
    ],
)
@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, "1", None, 100001])
def test_policy_exact_required_bounded_types(field, value):
    with pytest.raises(Error):
        replace(Policy(1, 4, 1), **{field: value})


def test_policy_consistency_no_defaults_or_weakening_switches():
    with pytest.raises(TypeError):
        Policy()
    with pytest.raises(Error):
        Policy(2, 3, 2)
    with pytest.raises(TypeError):
        Policy(1, 1, 1, zero_effects_required=False)
    assert Policy(1, 100000, 100000).minimum_total_observation_count == 100000
    assert [f.name for f in fields(Policy) if f.init] == [
        "minimum_session_count",
        "minimum_total_observation_count",
        "minimum_observations_per_session",
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("minimum_session_count", 2),
        ("minimum_total_observation_count", 5),
        ("minimum_observations_per_session", 2),
    ],
)
def test_policy_identity_every_semantic_field(field, value):
    original = Policy(1, 4, 1)
    assert replace(original, **{field: value}).policy_id != original.policy_id


@pytest.mark.parametrize(
    "policy,counts,reasons",
    [
        (Policy(2, 4, 2), (2, 2), ()),
        (Policy(3, 3, 1), (1, 2), (Reason.INSUFFICIENT_SESSIONS,)),
        (Policy(2, 5, 1), (2, 2), (Reason.INSUFFICIENT_TOTAL_OBSERVATIONS,)),
        (Policy(2, 4, 2), (1, 3), (Reason.INSUFFICIENT_OBSERVATIONS_PER_SESSION,)),
        (
            Policy(3, 5, 1),
            (2, 2),
            (Reason.INSUFFICIENT_SESSIONS, Reason.INSUFFICIENT_TOTAL_OBSERVATIONS),
        ),
        (
            Policy(3, 6, 2),
            (1, 5),
            (
                Reason.INSUFFICIENT_SESSIONS,
                Reason.INSUFFICIENT_OBSERVATIONS_PER_SESSION,
            ),
        ),
        (
            Policy(2, 6, 2),
            (1, 3),
            (
                Reason.INSUFFICIENT_TOTAL_OBSERVATIONS,
                Reason.INSUFFICIENT_OBSERVATIONS_PER_SESSION,
            ),
        ),
        (Policy(3, 9, 3), (1, 3), tuple(Reason)),
    ],
)
def test_real_entry_point_coverage_inclusive_bounds_and_order(
    binding, chain, policy, counts, reasons
):
    before = deepcopy(chain)
    items, batch, result = evidence(binding, chain, counts, policy)
    assert result.status is (Status.FAILED if reasons else Status.PASSED)
    assert result.failure_reasons == reasons
    assert result.observation_count == sum(counts)
    assert result.distinct_session_count == len(counts)
    assert result.minimum_observations_in_any_session == min(counts)
    m.verify_research_candidate_shadow_qualification(
        result,
        binding,
        batch,
        policy,
        **chain,
        observations=items,
        **SOURCE,
        **Q_SOURCE,
    )
    assert chain == before
    if reasons:
        with pytest.raises(Error):
            m.build_shadow_research_candidate(
                chain["walk_forward_passed"], binding, batch, result
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("binding_id", UUID(int=8)),
        ("observation_batch_id", UUID(int=9)),
        ("policy", Policy(2, 4, 2)),
        ("qualification_source_head", "c" * 40),
        ("qualification_source_tree", "d" * 40),
        ("observation_count", 9),
        ("distinct_session_count", 3),
        ("minimum_observations_in_any_session", 3),
    ],
)
def test_qualification_identity_every_semantic_field(field, value):
    assert (
        replace(local_qualification(), **{field: value}).qualification_id
        != local_qualification().qualification_id
    )


@pytest.mark.parametrize(
    "field",
    [
        "observation_count",
        "distinct_session_count",
        "minimum_observations_in_any_session",
    ],
)
@pytest.mark.parametrize("value", [True, 0, -1, 100001, 1.0])
def test_qualification_exact_bounded_counts(field, value):
    with pytest.raises(Error):
        replace(local_qualification(), **{field: value})


@pytest.mark.parametrize("counts", [(2, 3, 1), (8, 1, 2), (5, 2, 3)])
def test_impossible_coverage_facts_raise(counts):
    with pytest.raises(Error):
        local_qualification(
            observation_count=counts[0],
            distinct_session_count=counts[1],
            minimum_observations_in_any_session=counts[2],
        )


@pytest.mark.parametrize("field", b1.SHADOW_ZERO_EFFECT_FIELDS)
@pytest.mark.parametrize("target", ["observation", "batch"])
def test_malformed_effect_evidence_raises_never_failed(binding, chain, field, target):
    items, batch, _ = evidence(binding, chain)
    object.__setattr__(items[0] if target == "observation" else batch, field, 1)
    with pytest.raises(ValueError):
        m.qualify_research_candidate_shadow(
            binding,
            batch,
            Policy(2, 4, 2),
            **chain,
            observations=items,
            **SOURCE,
            **Q_SOURCE,
        )
    assert getattr(items[0] if target == "observation" else batch, field) == 1


def test_independent_qualification_verifier_rejects_external_drift(binding, chain):
    items, batch, result = evidence(binding, chain)
    before = deepcopy(chain)
    for name in Q_SOURCE:
        with pytest.raises(Error):
            m.verify_research_candidate_shadow_qualification(
                result,
                binding,
                batch,
                result.policy,
                **chain,
                observations=items,
                **SOURCE,
                **{**Q_SOURCE, name: "f" * 40},
            )
    with pytest.raises(Error):
        m.verify_research_candidate_shadow_qualification(
            result,
            binding,
            batch,
            Policy(1, 1, 1),
            **chain,
            observations=items,
            **SOURCE,
            **Q_SOURCE,
        )
    for name in ("binding_source_head", "qualification_source_head"):
        with pytest.raises(ValueError):
            m.qualify_research_candidate_shadow(
                binding,
                batch,
                result.policy,
                **{**chain, name: "f" * 40},
                observations=items,
                **SOURCE,
                **Q_SOURCE,
            )
    forged = replace(result, observation_count=5)
    assert Qualification.from_json(forged.to_json()) == forged
    with pytest.raises(Error):
        m.verify_research_candidate_shadow_qualification(
            forged,
            binding,
            batch,
            result.policy,
            **chain,
            observations=items,
            **SOURCE,
            **Q_SOURCE,
        )
    assert chain == before


def test_exact_caller_observations_and_sources_are_required(binding, chain):
    items, batch, result = evidence(binding, chain)
    changed = (replace(items[0], input_fingerprint=UUID(int=99)), *items[1:])
    with pytest.raises(ValueError):
        m.qualify_research_candidate_shadow(
            binding,
            batch,
            result.policy,
            **chain,
            observations=changed,
            **SOURCE,
            **Q_SOURCE,
        )
    with pytest.raises(ValueError):
        m.qualify_research_candidate_shadow(
            binding,
            batch,
            result.policy,
            **chain,
            observations=items,
            **{**SOURCE, "observation_source_tree": "f" * 40},
            **Q_SOURCE,
        )


@pytest.mark.parametrize("rank", [1, 2, None])
def test_passed_shadow_preserves_rank_and_complete_lineage(completed, rank):
    source, historical = deepcopy(completed)
    report = deepcopy(source.folds[0].training_report)
    selected = source.folds[0].selection.selected_variant_id
    if rank is None:
        object.__setattr__(report, "ranking", None)
        for row in report.variants:
            object.__setattr__(row, "rank", None)
            object.__setattr__(row, "comparison_values", ())
    else:
        for row in report.variants:
            object.__setattr__(
                row, "rank", rank if row.variant_id == selected else 3 - rank
            )
    _reidentify_report(report)
    chain = _chain(source, historical, report)
    binding = build_research_candidate_shadow_variant_binding(**chain)
    items, batch, qualification = evidence(binding, chain)
    predecessor = chain["walk_forward_passed"]
    successor = m.build_shadow_research_candidate(
        predecessor, binding, batch, qualification
    )
    assert (
        successor
        == m.build_shadow_research_candidate(predecessor, binding, batch, qualification)
        == Shadow.from_json(successor.to_json())
    )
    m.verify_shadow_research_candidate(
        successor, predecessor, binding, batch, qualification
    )
    assert successor.stage is ResearchCandidateStage.SHADOW
    assert successor.rank == rank == predecessor.rank
    assert successor.predecessor_candidate_id == predecessor.candidate_id
    assert successor.backtested_candidate_id == predecessor.predecessor_candidate_id
    assert successor.walk_forward_qualification_id == predecessor.qualification_id
    for name in (
        "source_head",
        "source_tree",
        "report_id",
        "experiment_result_id",
        "variant_id",
        "caller_ordinal",
        "variant_name",
    ):
        assert getattr(successor, name) == getattr(predecessor, name)
    assert successor.binding_id == binding.binding_id
    assert successor.observation_batch_id == batch.observation_batch_id
    assert successor.qualification_id == qualification.qualification_id
    assert (
        successor.walk_forward_qualification_source_head
        == binding.qualification_source_head
    )
    assert successor.binding_source_head == binding.binding_source_head
    assert successor.observation_source_head == batch.observation_source_head
    assert (
        successor.qualification_source_head == qualification.qualification_source_head
    )
    for model, previous in (
        (ResearchStrategyCandidate, chain["predecessor"]),
        (WalkForwardPassedResearchStrategyCandidate, predecessor),
    ):
        raw = json.loads(previous.to_json())
        raw["stage"] = "SHADOW"
        with pytest.raises(ValueError):
            model.from_json(json.dumps(raw, sort_keys=True, separators=(",", ":")))
        with pytest.raises(ValueError):
            model.from_json(successor.to_json())
    assert len(items) == 4


@pytest.mark.parametrize("part", ["predecessor", "binding", "batch", "qualification"])
def test_shadow_rejects_wrong_linkage(binding, chain, part):
    _, batch, qualification = evidence(binding, chain)
    predecessor = chain["walk_forward_passed"]
    if part == "predecessor":
        predecessor = replace(predecessor, qualification_id=UUID(int=99))
    elif part == "binding":
        binding = replace(binding, binding_source_head="f" * 40)
    elif part == "batch":
        batch = replace(batch, observation_source_head="f" * 40)
    else:
        qualification = replace(qualification, binding_id=UUID(int=99))
    with pytest.raises(Error):
        m.build_shadow_research_candidate(predecessor, binding, batch, qualification)


@pytest.mark.parametrize(
    "field",
    [
        f.name
        for f in fields(Shadow)
        if f.init
        and f.name not in ("predecessor_candidate_id", "backtested_candidate_id")
    ],
)
def test_shadow_identity_every_independently_variable_semantic(field):
    original = local_shadow()
    value = getattr(original, field)
    changed = (
        UUID(int=99)
        if type(value) is UUID
        else "9" * 40
        if field.endswith(("_head", "_tree"))
        else 3
        if field in ("rank", "caller_ordinal")
        else "Other Ã©"
    )
    assert local_shadow(**{field: changed}).candidate_id != original.candidate_id


@pytest.mark.parametrize(
    "field", ["predecessor_candidate_id", "backtested_candidate_id"]
)
def test_shadow_rejects_forged_derived_predecessor_ids(field):
    with pytest.raises(ValueError):
        local_shadow(**{field: UUID(int=99)})


@pytest.mark.parametrize(
    "make,model,id_field",
    [
        (lambda: Policy(2, 4, 2), Policy, "policy_id"),
        (local_qualification, Qualification, "qualification_id"),
        (local_shadow, Shadow, "candidate_id"),
    ],
)
@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "missing",
        "extra",
        "whitespace",
        "newline",
        "id",
        "schema",
        "uuid",
        "bool",
        "constant",
    ],
)
def test_strict_parsers(make, model, id_field, mutation):
    value = make().to_json()
    raw = json.loads(value)
    if mutation == "duplicate":
        value = '{"schema":"duplicate",' + value[1:]
    elif mutation == "whitespace":
        value = json.dumps(raw)
    elif mutation == "newline":
        value += "\n"
    else:
        if mutation == "missing":
            raw.pop("schema")
        elif mutation == "extra":
            raw["verified"] = True
        elif mutation == "id":
            raw[id_field] = str(UUID(int=99))
        elif mutation == "schema":
            raw["schema"] = "wrong/v1"
        elif mutation == "uuid":
            raw[id_field] = UUID(raw[id_field]).hex
        elif mutation == "bool":
            raw[
                "minimum_session_count"
                if model is Policy
                else "observation_count"
                if model is Qualification
                else "caller_ordinal"
            ] = True
        elif mutation == "constant":
            raw[
                "minimum_session_count"
                if model is Policy
                else "observation_count"
                if model is Qualification
                else "caller_ordinal"
            ] = float("inf")
        value = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    with pytest.raises(Error):
        model.from_json(value)


def test_nested_duplicate_and_derived_status_reasons_and_stage_rejected():
    value = local_qualification().to_json()
    with pytest.raises(Error):
        Qualification.from_json(
            value.replace(
                '"minimum_session_count":',
                '"schema":"duplicate","minimum_session_count":',
            )
        )
    for field, bad in (
        ("status", "FAILED"),
        ("failure_reasons", [Reason.INSUFFICIENT_SESSIONS.value]),
        ("qualification_id", str(UUID(int=99))),
    ):
        raw = json.loads(value)
        raw[field] = bad
        with pytest.raises(Error):
            Qualification.from_json(
                json.dumps(raw, sort_keys=True, separators=(",", ":"))
            )
    for field in ("stage", "schema"):
        raw = json.loads(local_shadow().to_json())
        raw[field] = "PAPER_CANDIDATE"
        with pytest.raises(Error):
            Shadow.from_json(json.dumps(raw, sort_keys=True, separators=(",", ":")))
    q = local_qualification()
    object.__setattr__(q, "status", "PASSED")
    with pytest.raises(Error):
        q.to_json()


def test_frozen_exports_namespaces_and_semantic_framing():
    for module in (b1, m):
        for name in module.__all__:
            assert getattr(experiments, name) is getattr(module, name)
    for value, model, namespace in (
        (Policy(1, 4, 1), Policy, m.SHADOW_POLICY_NAMESPACE),
        (local_qualification(), Qualification, m.SHADOW_QUALIFICATION_NAMESPACE),
        (local_shadow(), Shadow, m.SHADOW_CANDIDATE_NAMESPACE),
    ):
        assert model.from_json(value.to_json()) == value
        assert namespace == uuid5(NAMESPACE_URL, value.schema)
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            value.schema = "other"
    p = Policy(1, 4, 1)
    values = (
        "research-candidate-shadow-qualification-policy-identity/v1",
        p.schema,
        "1",
        "4",
        "1",
    )
    assert p.policy_id == uuid5(
        m.SHADOW_POLICY_NAMESPACE,
        "".join(f"{len(v.encode('utf-8'))}:{v}" for v in values),
    )


def test_closed_capability_ast_and_exact_imports():
    tree = ast.parse(inspect.getsource(m))
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert imports == {
        "__future__",
        "json",
        "re",
        "dataclasses",
        "enum",
        "uuid",
        "trading_bot.experiments.historical",
        "trading_bot.experiments.report",
        "trading_bot.experiments.research_candidate",
        "trading_bot.experiments.research_candidate_shadow_binding",
        "trading_bot.experiments.research_candidate_shadow_observation",
        "trading_bot.experiments.research_candidate_walk_forward",
        "trading_bot.experiments.walk_forward",
    }
    assert all(
        not a.name.startswith("_")
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        for a in n.names
    )
    forbidden = {
        "open",
        "Path",
        "eval",
        "exec",
        "__import__",
        "now",
        "utcnow",
        "today",
        "sleep",
        "uuid4",
        "hash",
        "id",
        "run",
        "evaluate",
        "simulate",
        "Popen",
        "connect",
        "request",
        "execute",
        "place_order",
        "review_equity_order",
        "promote",
        "advance",
        "set_stage",
        "ProductionStrategyContract",
        "PaperCandidate",
        "AwaitingHumanPromotion",
    }
    calls = {
        n.func.id if isinstance(n.func, ast.Name) else n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
    }
    assert not calls & forbidden
    assert all(not hasattr(m, name) for name in forbidden)
