"""139-A consumes synthetic completed evidence; operations never execute research."""

import ast
import inspect
import json
from copy import deepcopy as standard_deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Context, Decimal, localcontext
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID, uuid5

import pytest
from tests.experiments.test_research_candidate_walk_forward import (
    HEAD,
    TREE,
    _reidentify_report,
)
from tests.experiments.test_walk_forward_analytics import _source

from trading_bot.experiments import historical as historical_module
from trading_bot.experiments import research_candidate_shadow_binding as module
from trading_bot.experiments import walk_forward as walk_module
from trading_bot.experiments.exceptions import HistoricalExperimentError
from trading_bot.experiments.research_candidate import (
    ResearchCandidateStage,
    build_backtested_research_candidate,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    ResearchCandidateShadowBindingError as Error,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    ResearchCandidateShadowVariantBinding as Binding,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    build_research_candidate_shadow_variant_binding as build,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    resolve_bound_research_candidate_variant as resolve,
)
from trading_bot.experiments.research_candidate_shadow_binding import (
    verify_research_candidate_shadow_variant_binding as verify,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardQualificationPolicy as Policy,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    build_walk_forward_passed_research_candidate,
    qualify_research_candidate_walk_forward,
)


def deepcopy(value):
    # Independent test copy: register only mapping proxies in standard deepcopy's
    # memo, preserving the alias topology of the rest of the evidence graph.
    memo = {}

    def seed(item):
        if id(item) in memo:
            return
        if type(item) is MappingProxyType:
            storage = {}
            memo[id(item)] = MappingProxyType(storage)
            for key, child in item.items():
                seed(key)
                seed(child)
                storage[standard_deepcopy(key, memo)] = standard_deepcopy(child, memo)
        elif hasattr(item, "__dataclass_fields__"):
            for field in fields(item):
                seed(getattr(item, field.name))
        elif isinstance(item, (tuple, list)):
            for child in item:
                seed(child)
        elif isinstance(item, dict):
            for child in item.values():
                seed(child)

    seed(value)
    return standard_deepcopy(value, memo)


SOURCES = dict(
    qualification_source_head=HEAD,
    qualification_source_tree=TREE,
    binding_source_head="1af8150c9985f5dc7ad1e143a16d90dcdc86be1a",
    binding_source_tree="f0adb7a370c5ab1d41c4a6d62e2b9db012096952",
)


@pytest.fixture(scope="module")
def completed():
    # Retain original results from the accepted small in-memory fixture. These
    # synthetic fixture runs are setup only, never binding/resolution operations.
    results = []
    original = historical_module.HistoricalExperimentRunner.run

    def retain(self, request):
        result = original(self, request)
        results.append(result)
        return result

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(historical_module.HistoricalExperimentRunner, "run", retain)
        source = _source()
    return source, results[0]


def _chain(source, result, report=None):
    report = report if report is not None else source.folds[0].training_report
    selected = source.folds[0].selection.selected_variant_id
    candidate = build_backtested_research_candidate(
        report, selected_variant_id=selected, source_head=HEAD, source_tree=TREE
    )
    policy = Policy(2, Decimal("-100"), Decimal("-100"), Decimal("100"))
    qualification = qualify_research_candidate_walk_forward(
        candidate, report, source, policy, source_head=HEAD, source_tree=TREE
    )
    successor = build_walk_forward_passed_research_candidate(candidate, qualification)
    return dict(
        predecessor=candidate,
        walk_forward_passed=successor,
        qualification=qualification,
        report=report,
        historical_experiment_result=result,
        walk_forward_result=source,
        qualification_policy=policy,
        **SOURCES,
    )


@pytest.fixture
def chain(completed):
    source, result = deepcopy(completed)
    return _chain(source, result)


@pytest.fixture
def binding(chain):
    return build(**chain)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@pytest.mark.parametrize("rank", [1, 2, None])
def test_exact_binding_rank_determinism_and_resolver(completed, rank):
    source, result = deepcopy(completed)
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
    chain = _chain(source, result, report)
    before = deepcopy((source, result, report))
    binding = build(**chain)
    assert binding == build(**chain) == Binding.from_json(binding.to_json())
    assert binding.rank == rank == chain["predecessor"].rank
    verify(binding, **chain)
    assert resolve(binding, result) is result.request.variants[binding.caller_ordinal]
    assert (source, result, report) == before
    assert chain["predecessor"].stage is ResearchCandidateStage.BACKTESTED
    assert (
        chain["walk_forward_passed"].stage is ResearchCandidateStage.WALK_FORWARD_PASSED
    )
    with pytest.raises(FrozenInstanceError):
        binding.rank = 1


def test_exact_ordered_utf8_identity(binding):
    ordered = (
        "walk_forward_passed_candidate_id",
        "predecessor_candidate_id",
        "qualification_id",
        "candidate_source_head",
        "candidate_source_tree",
        "qualification_source_head",
        "qualification_source_tree",
        "binding_source_head",
        "binding_source_tree",
        "report_id",
        "experiment_request_id",
        "experiment_result_id",
        "historical_fingerprint",
        "schedule_fingerprint",
        "initial_state_fingerprint",
        "variant_id",
        "caller_ordinal",
        "variant_name",
        "rank",
        "experiment_run_id",
        "rolling_result_id",
    )
    assert tuple(item.name for item in fields(binding) if item.init) == ordered
    renamed = replace(binding, variant_name="caf\u00e9:variant")
    values = (
        "research-candidate-shadow-variant-binding-identity/v1",
        renamed.schema,
        *(
            "none" if getattr(renamed, name) is None else str(getattr(renamed, name))
            for name in ordered
        ),
    )
    assert renamed.binding_id == uuid5(
        UUID("0521440a-535c-4ebc-baa4-b071db744593"),
        "".join(f"{len(value.encode('utf-8'))}:{value}" for value in values),
    )


@pytest.mark.parametrize("name", [item.name for item in fields(Binding) if item.init])
def test_every_semantic_field_identity_sensitive(binding, name):
    value = getattr(binding, name)
    changed = (
        UUID(int=999)
        if type(value) is UUID
        else 7
        if type(value) is int
        else "different"
        if name == "variant_name"
        else "a" * 40
    )
    assert replace(binding, **{name: changed}).binding_id != binding.binding_id


@pytest.mark.parametrize("name", list(SOURCES))
def test_independent_source_authority(binding, chain, name):
    other = dict(chain, **{name: "a" * 40})
    with pytest.raises(HistoricalExperimentError):
        verify(binding, **other)
    if name.startswith("binding_"):
        # A different well-formed source can make a different binding, but cannot
        # independently verify an artifact bound to the original exact source.
        assert build(**other).binding_id != binding.binding_id


@pytest.mark.parametrize("name", list(SOURCES))
@pytest.mark.parametrize("value", ["A" * 40, "a" * 39, "g" * 40, "a" * 41, None, True])
def test_noncanonical_sources_rejected(chain, name, value):
    with pytest.raises(HistoricalExperimentError):
        build(**dict(chain, **{name: value}))


@pytest.mark.parametrize(
    "name",
    [
        "predecessor",
        "walk_forward_passed",
        "qualification",
        "report",
        "historical_experiment_result",
        "walk_forward_result",
        "qualification_policy",
    ],
)
def test_external_types_and_subclasses_fail_closed(chain, name):
    with pytest.raises(HistoricalExperimentError):
        build(**dict(chain, **{name: None}))
    original = chain[name]
    subclass = type("Foreign", (type(original),), {})
    forged = object.__new__(subclass)
    for item in fields(original):
        object.__setattr__(forged, item.name, getattr(original, item.name))
    with pytest.raises(HistoricalExperimentError):
        build(**dict(chain, **{name: forged}))


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("predecessor", "report_id", UUID(int=999)),
        ("walk_forward_passed", "qualification_id", UUID(int=999)),
        ("qualification", "walk_forward_result_id", UUID(int=999)),
        ("walk_forward_result", "result_id", UUID(int=999)),
        ("qualification_policy", "minimum_fold_count", 3),
    ],
)
def test_wrong_external_chain_rejected(chain, name, field, value):
    original = chain[name]
    if name == "walk_forward_result":
        other = deepcopy(original)
        object.__setattr__(other, field, value)
    else:
        other = replace(original, **{field: value})
    with pytest.raises(HistoricalExperimentError):
        build(**dict(chain, **{name: other}))


def test_failed_qualification_rejected(chain):
    policy = replace(chain["qualification_policy"], minimum_fold_count=3)
    qualification = qualify_research_candidate_walk_forward(
        chain["predecessor"],
        chain["report"],
        chain["walk_forward_result"],
        policy,
        source_head=HEAD,
        source_tree=TREE,
    )
    assert qualification.status.value == "FAILED"
    with pytest.raises(HistoricalExperimentError):
        build(**dict(chain, qualification=qualification, qualification_policy=policy))


@pytest.mark.parametrize(
    "name",
    [
        "report_id",
        "experiment_result_id",
        "experiment_request_id",
        "historical_fingerprint",
        "schedule_fingerprint",
        "initial_state_fingerprint",
    ],
)
def test_canonical_wrong_report_provenance_rejected(chain, name):
    report = deepcopy(chain["report"])
    if name == "report_id":
        object.__setattr__(report, name, UUID(int=999))
        with pytest.raises(HistoricalExperimentError):
            build(**dict(chain, report=report))
    else:
        object.__setattr__(report, name, UUID(int=999))
        _reidentify_report(report)
        altered = _chain(
            chain["walk_forward_result"], chain["historical_experiment_result"], report
        )
        with pytest.raises(HistoricalExperimentError):
            build(**altered)


@pytest.mark.parametrize(
    "name,value",
    [
        ("experiment_run_id", UUID(int=999)),
        ("rolling_result_id", UUID(int=999)),
        ("metrics", None),
        ("caller_ordinal", 2),
        ("variant_name", "different"),
    ],
)
def test_report_row_disagreement_rejected(chain, name, value):
    report = deepcopy(chain["report"])
    row = next(
        row
        for row in report.variants
        if row.variant_id == chain["predecessor"].variant_id
    )
    if name == "metrics":
        value = replace(row.metrics, total_orders=row.metrics.total_orders + 1)
    object.__setattr__(row, name, value)
    try:
        _reidentify_report(report)
        altered = _chain(
            chain["walk_forward_result"], chain["historical_experiment_result"], report
        )
    except HistoricalExperimentError:
        return
    with pytest.raises(HistoricalExperimentError):
        build(**altered)


@pytest.mark.parametrize(
    "drift",
    [
        "result_id",
        "request_id",
        "historical_fingerprint",
        "schedule_fingerprint",
        "initial_state_fingerprint",
        "missing_variant",
        "duplicate_variant",
        "variant_id",
        "variant_name",
        "variant_config",
        "ordinal",
        "run_id",
        "rolling_id",
        "metrics",
        "retained_variant",
        "retained_history",
        "runs_list",
        "variants_list",
        "schedule_list",
        "metadata_list",
        "policy_normalization",
        "initial_normalization",
        "run_subclass",
        "variant_subclass",
    ],
)
def test_historical_drift_rejected_without_mutating_evidence(chain, binding, drift):
    result = chain["historical_experiment_result"]
    run = result.runs[binding.caller_ordinal]
    variant = run.variant
    if drift in (
        "result_id",
        "historical_fingerprint",
        "schedule_fingerprint",
        "initial_state_fingerprint",
    ):
        object.__setattr__(result, drift, UUID(int=999))
    elif drift == "request_id":
        object.__setattr__(result.request, "request_id", UUID(int=999))
    elif drift in ("missing_variant", "duplicate_variant", "variants_list"):
        variants = (
            ()
            if drift == "missing_variant"
            else (variant, variant)
            if drift == "duplicate_variant"
            else list(result.request.variants)
        )
        object.__setattr__(result.request, "variants", variants)
    elif drift in ("variant_id", "variant_name", "variant_config"):
        name = (
            "variant_id"
            if drift == "variant_id"
            else "name"
            if drift == "variant_name"
            else "risk_aversion"
        )
        object.__setattr__(
            variant,
            name,
            UUID(int=999)
            if drift == "variant_id"
            else "different"
            if drift == "variant_name"
            else Decimal("9"),
        )
    elif drift in (
        "ordinal",
        "run_id",
        "rolling_id",
        "metrics",
        "retained_variant",
        "retained_history",
    ):
        if drift == "rolling_id":
            object.__setattr__(run.rolling_result, "result_id", UUID(int=999))
        elif drift == "retained_history":
            object.__setattr__(
                run.rolling_result.request,
                "historical_data",
                deepcopy(result.request.historical_data),
            )
        else:
            name = "variant" if drift == "retained_variant" else drift
            value = (
                deepcopy(variant)
                if drift == "retained_variant"
                else replace(run.metrics, total_orders=999)
                if drift == "metrics"
                else 9
                if drift == "ordinal"
                else UUID(int=999)
            )
            object.__setattr__(run, name, value)
    elif drift == "runs_list":
        object.__setattr__(result, "runs", list(result.runs))
    elif drift == "schedule_list":
        object.__setattr__(
            result.request,
            "rebalance_timestamps",
            list(result.request.rebalance_timestamps),
        )
    elif drift == "metadata_list":
        object.__setattr__(variant, "metadata", list(variant.metadata))
    elif drift == "policy_normalization":
        object.__setattr__(
            variant.scenario_policy,
            "price_field",
            variant.scenario_policy.price_field.value,
        )
    elif drift == "initial_normalization":
        object.__setattr__(result.request.initial_state, "bootstrap_positions", [])
    else:
        original = run if drift == "run_subclass" else variant
        subclass = type("Foreign", (type(original),), {})
        other = object.__new__(subclass)
        for item in fields(original):
            object.__setattr__(other, item.name, getattr(original, item.name))
        if drift == "run_subclass":
            object.__setattr__(
                result,
                "runs",
                tuple(other if item is run else item for item in result.runs),
            )
        else:
            object.__setattr__(
                result.request,
                "variants",
                tuple(
                    other if item is variant else item
                    for item in result.request.variants
                ),
            )
    before = deepcopy(result)
    with pytest.raises((HistoricalExperimentError, ValueError, TypeError)):
        build(**chain)
    with pytest.raises((HistoricalExperimentError, ValueError, TypeError)):
        resolve(binding, result)
    assert result == before
    # Equal list/tuple normalization would be detectable even if equality of a
    # nested value model were permissive; all retained field types stay intact.
    assert module._same_retained(result, before)


@pytest.mark.parametrize(
    "name",
    [
        "experiment_result_id",
        "experiment_request_id",
        "historical_fingerprint",
        "schedule_fingerprint",
        "initial_state_fingerprint",
        "variant_id",
        "caller_ordinal",
        "variant_name",
        "experiment_run_id",
        "rolling_result_id",
    ],
)
def test_self_consistent_wrong_result_bridge_rejected(binding, chain, name):
    value = getattr(binding, name)
    altered = replace(
        binding,
        **{
            name: UUID(int=999)
            if type(value) is UUID
            else 9
            if type(value) is int
            else "different"
        },
    )
    parsed = Binding.from_json(altered.to_json())
    with pytest.raises(Error):
        resolve(parsed, chain["historical_experiment_result"])
    with pytest.raises(Error):
        verify(parsed, **chain)


def test_same_variant_uuid_in_different_valid_result_rejected(completed, binding):
    source, result = deepcopy(completed)
    # A genuinely different completed fixture result keeps identical variant IDs.
    from tests.experiments.test_historical import _Factory

    altered_request = replace(result.request, request_id=UUID(int=999))
    different = historical_module.HistoricalExperimentRunner(_Factory()).run(
        altered_request
    )
    assert (
        different.request.variants[0].variant_id
        == result.request.variants[0].variant_id
    )
    with pytest.raises(Error):
        resolve(binding, different)


@pytest.mark.parametrize("precision", [2, 28, 80])
def test_binding_decimal_context_independent(chain, binding, precision):
    with localcontext(Context(prec=precision)):
        assert build(**chain) == binding
        assert (
            resolve(binding, chain["historical_experiment_result"]).variant_id
            == binding.variant_id
        )
        verify(binding, **chain)


def test_lossy_legacy_decimal_identity_cannot_hide_variant_config_drift(chain, binding):
    result = chain["historical_experiment_result"]
    variant = result.runs[binding.caller_ordinal].variant
    # Historical canonical_decimal uses normalize: low significance changes can
    # alias at precision 28. The bridge must validate without that loss.
    object.__setattr__(variant, "risk_aversion", Decimal("1." + "0" * 30 + "1"))
    with localcontext(Context(prec=28)):
        result.runs[binding.caller_ordinal].__post_init__()
        result.__post_init__()
    before = deepcopy(result)
    with pytest.raises(HistoricalExperimentError):
        resolve(binding, result)
    with pytest.raises(HistoricalExperimentError):
        build(**chain)
    assert module._same_retained(result, before)


def test_unconsumed_noncanonical_iterable_fails_without_changing_caller(chain, binding):
    result = chain["historical_experiment_result"]
    timestamps = result.request.rebalance_timestamps
    iterator = iter(timestamps)
    object.__setattr__(result.request, "rebalance_timestamps", iterator)
    with pytest.raises((HistoricalExperimentError, TypeError, ValueError)):
        resolve(binding, result)
    assert result.request.rebalance_timestamps is iterator
    assert tuple(iterator) == timestamps


def test_copy_preserves_mapping_types_and_aliases(chain):
    original = chain["historical_experiment_result"]
    defensive = module._copy_retained(original)
    assert module._same_retained(original, defensive)
    assert defensive is not original
    for run, variant in zip(defensive.runs, defensive.request.variants, strict=True):
        assert run.variant is variant
        assert (
            run.rolling_result.request.historical_data
            is defensive.request.historical_data
        )
        assert (
            run.rolling_result.optimized_result.request
            is run.rolling_result.optimized_request
        )
    # Drift must remain drift in the defensive copy rather than being repaired.
    original_run = original.runs[0]
    object.__setattr__(original_run, "variant", deepcopy(original_run.variant))
    drifted = module._copy_retained(original)
    assert drifted.runs[0].variant is not drifted.request.variants[0]
    with pytest.raises(HistoricalExperimentError):
        resolve(build(**_chain(chain["walk_forward_result"], defensive)), original)


def test_binding_operations_do_not_run_or_construct_simulator(
    chain, binding, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("no execution/evaluation capability")

    monkeypatch.setattr(historical_module.HistoricalExperimentRunner, "run", forbidden)
    monkeypatch.setattr(
        walk_module.HistoricalExperimentWalkForwardRunner, "run", forbidden
    )
    monkeypatch.setattr(
        historical_module.OptimizedPaperPortfolioSimulator, "__init__", forbidden
    )
    assert build(**chain) == binding
    verify(binding, **chain)
    assert (
        resolve(binding, chain["historical_experiment_result"]).variant_id
        == binding.variant_id
    )


@pytest.mark.parametrize("name", [item.name for item in fields(Binding)])
def test_json_missing_unknown_duplicate_fields(binding, name):
    raw = json.loads(binding.to_json())
    raw.pop(name)
    with pytest.raises(Error):
        Binding.from_json(_json(raw))
    raw = json.loads(binding.to_json())
    with pytest.raises(Error):
        Binding.from_json(
            binding.to_json()[:-1] + "," + _json(name) + ":" + _json(raw[name]) + "}"
        )
    raw["unknown"] = None
    with pytest.raises(Error):
        Binding.from_json(_json(raw))


@pytest.mark.parametrize(
    "name", [item.name for item in fields(Binding) if item.type == "UUID"]
)
@pytest.mark.parametrize("form", ["upper", "hex", "braces", "int"])
def test_json_uuid_canonicality(binding, name, form):
    raw = json.loads(binding.to_json())
    value = UUID(raw[name])
    raw[name] = (
        str(value).upper()
        if form == "upper"
        else value.hex
        if form == "hex"
        else "{" + str(value) + "}"
        if form == "braces"
        else value.int
    )
    # UUIDs made entirely of digits would have no uppercase drift.
    if raw[name] == str(value):
        raw[name] = str(UUID("aaaaaaaa-aaaa-5aaa-aaaa-aaaaaaaaaaaa")).upper()
    with pytest.raises(Error):
        Binding.from_json(_json(raw))


@pytest.mark.parametrize(
    "name",
    [item.name for item in fields(Binding) if item.name.endswith(("_head", "_tree"))],
)
def test_json_source_canonicality(binding, name):
    raw = json.loads(binding.to_json())
    raw[name] = "A" * 40
    with pytest.raises(Error):
        Binding.from_json(_json(raw))


@pytest.mark.parametrize("name", ["caller_ordinal", "rank"])
@pytest.mark.parametrize("value", [True, False, 1.0, "1", -1, 1_000_001])
def test_exact_integer_typing(binding, name, value):
    with pytest.raises(Error):
        replace(binding, **{name: value})
    raw = json.loads(binding.to_json())
    raw[name] = value
    with pytest.raises(Error):
        Binding.from_json(_json(raw))


@pytest.mark.parametrize("value", ["", " spaced ", "x" * 257, "\ud800", True, None])
def test_variant_name_rejected(binding, value):
    with pytest.raises(Error):
        replace(binding, variant_name=value)


def test_json_alternate_representations_and_forged_identity(binding, chain):
    raw = json.loads(binding.to_json())
    variants = [
        json.dumps(raw),
        _json(dict(reversed(tuple(raw.items())))),
        binding.to_json() + "\n",
        "[]",
        "null",
        '{"rank":NaN}',
    ]
    # _json sorts keys; explicitly serialize reversed insertion order here.
    variants[1] = json.dumps(dict(reversed(tuple(raw.items()))), separators=(",", ":"))
    raw["binding_id"] = str(UUID(int=999))
    variants.append(_json(raw))
    for value in variants:
        with pytest.raises(Error):
            Binding.from_json(value)
    forged = deepcopy(binding)
    object.__setattr__(forged, "binding_id", UUID(int=999))
    with pytest.raises(Error):
        resolve(forged, chain["historical_experiment_result"])
    with pytest.raises(Error):
        forged.to_json()
    with pytest.raises(Error):
        verify(forged, **chain)


def test_parser_self_consistency_does_not_prove_external_verification(binding, chain):
    unrelated = replace(
        binding, report_id=UUID(int=999), qualification_id=UUID(int=998)
    )
    parsed = Binding.from_json(unrelated.to_json())
    # Resolver verifies only the result bridge; complete lifecycle/report evidence
    # remains mandatory in the independent verifier used by later observation.
    assert resolve(parsed, chain["historical_experiment_result"])
    with pytest.raises(Error):
        verify(parsed, **chain)


def test_prior_artifacts_unchanged_and_no_new_stage(chain):
    artifacts = (
        chain["predecessor"],
        chain["qualification_policy"],
        chain["qualification"],
        chain["walk_forward_passed"],
    )
    for artifact in artifacts:
        assert type(artifact).from_json(artifact.to_json()) == artifact
    for artifact in (artifacts[0], artifacts[3]):
        raw = json.loads(artifact.to_json())
        for stage in ("SHADOW", "PAPER_CANDIDATE", "AWAITING_HUMAN_PROMOTION"):
            raw["stage"] = stage
            with pytest.raises(HistoricalExperimentError):
                type(artifact).from_json(_json(raw))
    # Frozen golden bytes are added after comparing against the exact base modules.
    assert all(
        sha256(artifact.to_json().encode()).hexdigest() for artifact in artifacts
    )


def test_exact_capability_allowlist_and_no_lifecycle_promotion():
    tree = ast.parse(inspect.getsource(module))
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imports == {
        "__future__",
        "json",
        "re",
        "collections.abc",
        "copy",
        "dataclasses",
        "decimal",
        "types",
        "uuid",
        "trading_bot.experiments.historical",
        "trading_bot.experiments.report",
        "trading_bot.experiments.research_candidate",
        "trading_bot.experiments.research_candidate_walk_forward",
        "trading_bot.experiments.walk_forward",
    }
    historical_imports = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "trading_bot.experiments.historical"
    )
    assert {alias.name for alias in historical_imports.names} == {
        "HistoricalExperimentRequest",
        "HistoricalExperimentResult",
        "HistoricalExperimentRun",
        "HistoricalExperimentVariant",
    }
    walk_imports = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "trading_bot.experiments.walk_forward"
    )
    assert [alias.name for alias in walk_imports.names] == [
        "HistoricalExperimentWalkForwardResult"
    ]
    forbidden = {
        "run",
        "evaluate",
        "advance",
        "promote",
        "set_stage",
        "build_shadow_candidate",
        "ShadowResearchStrategyCandidate",
        "ProductionStrategyContract",
        "HistoricalExperimentRunner",
        "HistoricalExperimentWalkForwardRunner",
        "OptimizedPaperPortfolioSimulator",
        "uuid4",
        "now",
        "utcnow",
        "time",
        "open",
        "exec",
        "eval",
        "__import__",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in forbidden
        elif isinstance(node, ast.Name):
            assert node.id not in forbidden - {"run"}
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            assert node.name not in forbidden
    assert all(not hasattr(module, name) for name in forbidden)
    from trading_bot import experiments

    for name in module.__all__:
        assert getattr(experiments, name) is getattr(module, name)
