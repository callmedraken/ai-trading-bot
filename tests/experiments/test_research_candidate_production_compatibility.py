"""Architecture-141 pure compatibility evidence and closed-boundary tests."""

import ast
import json
from dataclasses import replace
from decimal import Context, localcontext
from pathlib import Path
from uuid import UUID

import pytest
from tests.experiments.test_research_candidate_shadow_binding import (
    binding as binding,
)
from tests.experiments.test_research_candidate_shadow_binding import chain as chain
from tests.experiments.test_research_candidate_shadow_binding import (
    completed as completed,
)
from tests.experiments.test_research_candidate_shadow_binding import (
    deepcopy as copy_evidence,
)
from tests.experiments.test_research_candidate_shadow_observation import SOURCE
from tests.experiments.test_research_candidate_shadow_qualification import (
    Q_SOURCE,
    evidence,
)

from scripts import checkpoint_runner, run_test_certification
from trading_bot.experiments import (
    research_candidate_production_compatibility as module,
)
from trading_bot.experiments.research_candidate_shadow_qualification import (
    ResearchCandidateShadowQualificationPolicy,
    build_shadow_research_candidate,
)

Assessment = module.ResearchCandidateProductionCompatibilityAssessment
Blocker = module.ResearchCandidateProductionCompatibilityBlocker
Error = module.ResearchCandidateProductionCompatibilityError
Status = module.ResearchCandidateProductionCompatibilityStatus

ASSESSMENT_SOURCE = {
    "assessment_source_head": "e" * 40,
    "assessment_source_tree": "f" * 40,
}


@pytest.fixture
def artifacts(binding, chain):
    observations, batch, shadow_qualification = evidence(binding, chain)
    successor = build_shadow_research_candidate(
        chain["walk_forward_passed"], binding, batch, shadow_qualification
    )
    return dict(
        shadow_candidate=successor,
        binding=binding,
        shadow_qualification=shadow_qualification,
        batch=batch,
        shadow_qualification_policy=shadow_qualification.policy,
        **chain,
        observations=observations,
        **SOURCE,
        **Q_SOURCE,
        **ASSESSMENT_SOURCE,
    )


def build(artifacts):
    return module.build_research_candidate_production_compatibility_assessment(
        **artifacts
    )


def test_exact_construction_and_canonical_round_trip(artifacts):
    assessment = build(artifacts)
    assert assessment.stage.value == "SHADOW"
    assert assessment.status is Status.NOT_ESTABLISHED
    assert assessment.blockers == (
        Blocker.RESEARCH_STRATEGY_FAMILY_UNBOUND,
        Blocker.PRODUCTION_SYMBOL_MAPPING_UNBOUND,
        Blocker.PRODUCTION_CONFIG_MAPPING_UNBOUND,
    )
    assert assessment.to_json() == Assessment.from_json(assessment.to_json()).to_json()
    assert set(json.loads(assessment.to_json())) == {
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("shadow_candidate_id", UUID(int=901)),
        ("binding_id", UUID(int=902)),
        ("shadow_qualification_id", UUID(int=903)),
        ("historical_experiment_result_id", UUID(int=904)),
        ("variant_id", UUID(int=905)),
        ("candidate_source_head", "1" * 40),
        ("candidate_source_tree", "2" * 40),
        ("assessment_source_head", "3" * 40),
        ("assessment_source_tree", "4" * 40),
    ],
)
def test_uuid5_identity_is_deterministic_and_semantic(artifacts, field, value):
    original = build(artifacts)
    changed = replace(original, **{field: value})
    assert build(artifacts) == original
    assert changed.assessment_id != original.assessment_id


def test_full_external_verification_precedes_assessment(artifacts, monkeypatch):
    calls = []
    original = module.verify_research_candidate_shadow_qualification

    def checking(*args, **kwargs):
        calls.append("qualification")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        module, "verify_research_candidate_shadow_qualification", checking
    )
    build(artifacts)
    assert calls == ["qualification"]


@pytest.mark.parametrize(
    "name,mutation",
    [
        ("predecessor", lambda a: replace(a["predecessor"], source_head="0" * 40)),
        (
            "walk-forward",
            lambda a: replace(a["walk_forward_result"], result_id=UUID(int=906)),
        ),
        ("binding", lambda a: replace(a["binding"], binding_source_head="0" * 40)),
        (
            "observation",
            lambda a: replace(a["batch"], observation_source_head="0" * 40),
        ),
        (
            "qualification",
            lambda a: replace(a["shadow_qualification"], binding_id=UUID(int=907)),
        ),
        (
            "successor",
            lambda a: replace(a["shadow_candidate"], binding_id=UUID(int=908)),
        ),
        (
            "historical result",
            lambda a: _forge_result_id(a["historical_experiment_result"]),
        ),
    ],
)
def test_tampered_external_evidence_fails_closed(artifacts, name, mutation):
    changed = dict(artifacts)
    key = {
        "predecessor": "predecessor",
        "walk-forward": "walk_forward_result",
        "binding": "binding",
        "observation": "batch",
        "qualification": "shadow_qualification",
        "successor": "shadow_candidate",
        "historical result": "historical_experiment_result",
    }[name]
    with pytest.raises((Error, ValueError)):
        changed[key] = mutation(artifacts)
        build(changed)


def _forge_result_id(result):
    forged = copy_evidence(result)
    object.__setattr__(forged, "result_id", UUID(int=909))
    return forged


def test_resolved_variant_mismatch_fails_closed(artifacts, monkeypatch):
    variant = copy_evidence(
        artifacts["historical_experiment_result"].request.variants[0]
    )
    object.__setattr__(variant, "variant_id", UUID(int=910))
    monkeypatch.setattr(
        module, "resolve_bound_research_candidate_variant", lambda *_: variant
    )
    with pytest.raises(Error, match="variant lineage"):
        build(artifacts)


def test_independent_verifier_reconstructs_exact_assessment(artifacts):
    assessment = build(artifacts)
    module.verify_research_candidate_production_compatibility_assessment(
        assessment, **artifacts
    )
    with pytest.raises(Error):
        module.verify_research_candidate_production_compatibility_assessment(
            replace(assessment, assessment_source_head="0" * 40), **artifacts
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: raw.update({"unknown": 1}),
        lambda raw: raw.pop("variant_id"),
        lambda raw: raw.update({"assessment_id": str(UUID(int=999))}),
        lambda raw: raw.update({"stage": "PAPER_CANDIDATE"}),
        lambda raw: raw.update({"status": "COMPATIBLE"}),
        lambda raw: raw.update({"blockers": []}),
        lambda raw: raw.update({"candidate_source_head": "A" * 40}),
        lambda raw: raw.update({"shadow_candidate_id": 1}),
    ],
)
def test_parser_rejects_forged_wrong_or_noncanonical_fields(artifacts, mutation):
    raw = json.loads(build(artifacts).to_json())
    mutation(raw)
    with pytest.raises(Error):
        Assessment.from_json(json.dumps(raw, sort_keys=True, separators=(",", ":")))


def test_parser_rejects_duplicate_fields(artifacts):
    payload = build(artifacts).to_json()
    with pytest.raises(Error):
        Assessment.from_json(payload[:-1] + ',"schema":"other"}')


def test_parser_is_not_external_verification(artifacts, monkeypatch):
    assessment = build(artifacts)

    def forbidden(*args, **kwargs):
        raise AssertionError("parser attempted external verification")

    monkeypatch.setattr(
        module, "verify_research_candidate_shadow_qualification", forbidden
    )
    assert Assessment.from_json(assessment.to_json()) == assessment


def test_decimal_and_object_identity_independence(artifacts):
    first = build(artifacts)
    with localcontext(Context(prec=7)):
        low = build(copy_evidence(artifacts))
    with localcontext(Context(prec=80)):
        high = build(copy_evidence(artifacts))
    assert low == high == first


def test_inputs_remain_unchanged_on_success_and_failure(artifacts):
    before = copy_evidence(artifacts)
    build(artifacts)
    assert artifacts == before
    changed = dict(artifacts)
    changed["batch"] = replace(artifacts["batch"], observation_source_tree="0" * 40)
    with pytest.raises((Error, ValueError)):
        build(changed)
    assert artifacts == before


def test_no_heuristic_compatibility_or_production_authority():
    source_path = Path(module.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    assert "MovingAverageCrossoverConfig" not in source
    assert "MovingAverageCrossoverStrategy" not in source
    assert "ProductionStrategyContract" not in source
    assert "PAPER_CANDIDATE" not in source
    assert "AWAITING_HUMAN_PROMOTION" not in source
    for forbidden_mapping_token in (
        "variant_name",
        "rank",
        "metadata",
        "SPY",
        "short_window",
        "long_window",
        "desired_quantity",
    ):
        assert forbidden_mapping_token not in source
    forbidden_calls = {
        "evaluate",
        "promote",
        "advance",
        "set_stage",
        "uuid4",
        "now",
        "utcnow",
        "today",
        "run",
        "simulate",
        "id",
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not calls & forbidden_calls
    assert "PRODUCTION_SQLITE_READS" not in source
    assert "PROVIDER_CALLS" not in source
    assert "D1R9_OPERATIONS" not in source


def test_stage_vocabulary_remains_unchanged():
    from trading_bot.experiments.research_candidate import ResearchCandidateStage

    assert tuple(stage.value for stage in ResearchCandidateStage) == (
        "EXPERIMENTAL",
        "BACKTESTED",
        "WALK_FORWARD_PASSED",
        "SHADOW",
        "PAPER_CANDIDATE",
        "AWAITING_HUMAN_PROMOTION",
    )


def test_public_exports_are_additive():
    import trading_bot.experiments as experiments

    for name in module.__all__:
        assert name in experiments.__all__
        assert getattr(experiments, name) is getattr(module, name)


def test_policy_type_is_exact():
    with pytest.raises(TypeError):
        ResearchCandidateShadowQualificationPolicy(1, 1, 1, extra=True)


def test_arch141_overlay_inventory_and_workflow_preservation():
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    inventory = run_test_certification.discover_inventory(root)
    assert {
        name: len(run_test_certification.select_inventory(inventory, name))
        for name in ("full", "robinhood", "legacy", "exhaustive")
    } == {"full": 183, "robinhood": 101, "legacy": 222, "exhaustive": 405}
    assert len([path for path in inventory if path.startswith("tests/gui/")]) == 51
    assert "arch141-research-candidate-production-compatibility" not in (
        checkpoint_runner.ACTIVE_CI_CHECKPOINTS
    )
    profile = "tests/scripts/certification_runner/test_profiles.py"
    assert (
        checkpoint_runner._git_blob_sha1(root / profile)
        == (checkpoint_runner.ARCH141_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[profile])
    )
    assert (
        checkpoint_runner._git_blob_sha1(
            root / ".github/workflows/checkpoint-source-gates.yml"
        )
        == "fe6aceac62721338eba4fcb40e2e7fde0d976e18"
    )
    assert checkpoint_runner._arch134_d1r5_authority_check(root) == ()


@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong"])
def test_arch141_overlay_fails_closed(monkeypatch, mutation):
    pins = dict(checkpoint_runner.ARCH141_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    if mutation == "missing":
        pins.clear()
    elif mutation == "extra":
        pins["tests/experiments/test_research_candidate.py"] = "a" * 40
    else:
        pins["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH141_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    root = Path(checkpoint_runner.__file__).resolve().parents[1]
    assert checkpoint_runner._arch134_d1r5_authority_check(root)


def test_arch141_overlay_rejects_predecessor_dictionary_drift(monkeypatch):
    predecessor = dict(
        checkpoint_runner.ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    )
    predecessor["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner,
        "ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        predecessor,
    )
    with pytest.raises(ValueError, match="frozen 140-A18 predecessor"):
        checkpoint_runner._arch141_current_inventory_test_pin(
            "tests/scripts/certification_runner/test_profiles.py",
            "51f4404eacc526d8108921642b670f93290bcd33",
        )
