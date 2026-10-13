"""Architecture 138: qualification of completed in-memory research evidence."""

import ast
import inspect
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from decimal import Context, Decimal, localcontext
from uuid import UUID, uuid5

import pytest
from tests.experiments.test_walk_forward_analytics import _source

from trading_bot.experiments import report as report_module
from trading_bot.experiments import research_candidate_walk_forward as module
from trading_bot.experiments import walk_forward as walk_module
from trading_bot.experiments.exceptions import HistoricalExperimentError
from trading_bot.experiments.research_candidate import (
    ResearchCandidateStage,
    build_backtested_research_candidate,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardError,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardFailureReason as Reason,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardQualification as Qualification,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardQualificationPolicy as Policy,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    ResearchCandidateWalkForwardQualificationStatus as Status,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    build_walk_forward_passed_research_candidate as build,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    qualify_research_candidate_walk_forward as qualify,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    verify_research_candidate_walk_forward_qualification as verify,
)
from trading_bot.experiments.research_candidate_walk_forward import (
    verify_walk_forward_passed_research_candidate as verify_successor,
)

HEAD = "6e2081a1278f579ca0cee5a00e2bd83632bc2856"
TREE = "5858cc644d78eab9bbe58d1332f02c1b56aa5c65"


@pytest.fixture(scope="module")
def completed():
    # Accepted fake simulator creates immutable in-memory evidence only. No real
    # historical/provider execution occurs. Qualification never calls the runner.
    return _source()


@pytest.fixture
def source(completed):
    return deepcopy(completed)


@pytest.fixture
def report(source):
    return source.folds[0].training_report


@pytest.fixture
def candidate(report):
    row = next(row for row in report.variants if row.rank == 1)
    return _candidate(report, row.variant_id)


def _candidate(report, variant_id):
    return build_backtested_research_candidate(
        report, selected_variant_id=variant_id, source_head=HEAD, source_tree=TREE
    )


@pytest.fixture
def policy():
    return Policy(2, Decimal("-100"), Decimal("-100"), Decimal("100"))


def _qualify(candidate, report, source, policy):
    return qualify(
        candidate, report, source, policy, source_head=HEAD, source_tree=TREE
    )


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _reidentify_report(report):
    # Test-only projections of completed evidence use the existing identity engine.
    args = [
        getattr(report, item.name)
        for item in fields(report)
        if item.name != "report_id"
    ]
    object.__setattr__(report, "report_id", report_module._report_id_from_fields(*args))
    report.__post_init__()
    return report


def _reidentify_source(source):
    for fold in source.folds:
        _reidentify_report(fold.training_report)
        _reidentify_report(fold.test_report)
        object.__setattr__(
            fold.selection, "training_report_id", fold.training_report.report_id
        )
        fold.__post_init__()
    object.__setattr__(
        source,
        "result_id",
        walk_module._result_id(
            source.request_id,
            source.source_historical_fingerprint,
            source.selection_policy,
            source.folds,
            source.metadata,
        ),
    )
    source.__post_init__()
    return source


def _winner(source, index, ordinal):
    fold = source.folds[index]
    selected = fold.training_report.variants[ordinal]
    previous_rank = selected.rank
    for row in fold.training_report.variants:
        object.__setattr__(row, "rank", 1 if row is selected else previous_rank)
    object.__setattr__(
        fold.selection, "selected_caller_ordinal", selected.caller_ordinal
    )
    object.__setattr__(fold.selection, "selected_variant_id", selected.variant_id)
    object.__setattr__(
        fold.selection, "selected_training_run_id", selected.experiment_run_id
    )
    object.__setattr__(fold.test_report.variants[0], "variant_id", selected.variant_id)
    object.__setattr__(
        fold.test_report.variants[0], "variant_name", selected.variant_name
    )
    return _reidentify_source(source)


def test_policy_identity_framing_and_immutability(policy):
    material = (
        "research-candidate-walk-forward-qualification-policy-identity/v1",
        policy.schema,
        "2",
        "-100",
        "-100",
        "100",
    )
    assert policy.policy_id == uuid5(
        UUID("e07d29da-3084-5572-9a47-46f9e81dc0f8"),
        "".join(f"{len(value.encode('utf-8'))}:{value}" for value in material),
    )
    assert policy == Policy.from_json(policy.to_json())
    with pytest.raises(FrozenInstanceError):
        policy.minimum_fold_count = 3
    assert all(
        item.default is item.default_factory for item in fields(policy) if item.init
    )


@pytest.mark.parametrize(
    "name,value",
    [
        ("minimum_fold_count", 3),
        ("minimum_fold_simulation_return", Decimal("-101")),
        ("minimum_median_simulation_return", Decimal("-99")),
        ("maximum_fold_drawdown_percentage", Decimal("99")),
    ],
)
def test_policy_every_semantic_identity_sensitive(policy, name, value):
    assert replace(policy, **{name: value}).policy_id != policy.policy_id


@pytest.mark.parametrize("value", [True, False, 1, 1_000_001, 2.0, "2", None])
def test_policy_fold_count_rejected(policy, value):
    with pytest.raises(ResearchCandidateWalkForwardError):
        replace(policy, minimum_fold_count=value)


@pytest.mark.parametrize(
    "name",
    [
        "minimum_fold_simulation_return",
        "minimum_median_simulation_return",
        "maximum_fold_drawdown_percentage",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        0,
        0.0,
        "0",
        None,
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_policy_exact_finite_decimals(policy, name, value):
    with pytest.raises(ResearchCandidateWalkForwardError):
        replace(policy, **{name: value})


def test_policy_bounds_and_relations():
    assert Policy(1_000_000, Decimal("0"), Decimal("0"), Decimal("0"))
    with pytest.raises(ResearchCandidateWalkForwardError):
        Policy(2, Decimal("1"), Decimal("0"), Decimal("0"))
    with pytest.raises(ResearchCandidateWalkForwardError):
        Policy(2, Decimal("0"), Decimal("0"), Decimal("-0.0001"))


@pytest.mark.parametrize("rank", [1, 2, None])
def test_original_rank_is_evidence_only_and_preserved(source, candidate, policy, rank):
    original = deepcopy(source.folds[0].training_report)
    if rank == 2:
        for row in original.variants:
            object.__setattr__(
                row, "rank", 2 if row.variant_id == candidate.variant_id else 1
            )
    elif rank is None:
        object.__setattr__(original, "ranking", None)
        for row in original.variants:
            object.__setattr__(row, "rank", None)
            object.__setattr__(row, "comparison_values", ())
    _reidentify_report(original)
    candidate = _candidate(original, candidate.variant_id)
    qualification = _qualify(candidate, original, source, policy)
    assert qualification.status is Status.PASSED
    successor = build(candidate, qualification)
    assert successor.rank == rank
    assert successor.stage is ResearchCandidateStage.WALK_FORWARD_PASSED
    assert candidate.stage is ResearchCandidateStage.BACKTESTED
    for name in (
        "source_head",
        "source_tree",
        "report_id",
        "experiment_result_id",
        "variant_id",
        "caller_ordinal",
        "variant_name",
        "rank",
    ):
        assert getattr(successor, name) == getattr(candidate, name)
    verify_successor(successor, candidate, qualification)


def test_no_runner_and_exact_aggregate_called_once(
    candidate, report, source, policy, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("qualification must consume completed evidence only")

    monkeypatch.setattr(
        walk_module.HistoricalExperimentWalkForwardRunner, "run", forbidden
    )
    analyzer = module.HistoricalExperimentWalkForwardAggregateAnalyzer
    original = analyzer.analyze
    calls = []

    def tracked(self, retained, derived):
        result = original(self, retained, derived)
        calls.append((retained, derived, result))
        return result

    monkeypatch.setattr(analyzer, "analyze", tracked)
    before = deepcopy(source)
    qualification = _qualify(candidate, report, source, policy)
    assert len(calls) == 1
    retained, derived, result = calls[0]
    assert retained == source and retained is not source
    assert derived.policy_id == uuid5(
        policy.policy_id, "research-candidate-walk-forward-aggregate-evidence/v1"
    )
    assert derived.metadata == ()
    assert [
        (item.metric.value, tuple(op.value for op in item.operations))
        for item in derived.metrics
    ] == [
        ("SIMULATION_RETURN", ("MINIMUM", "MEDIAN")),
        ("MAXIMUM_DRAWDOWN_PERCENTAGE", ("MAXIMUM",)),
    ]
    assert qualification.aggregate_result_id == result.result_id
    assert source == before
    assert "aggregate" not in inspect.signature(qualify).parameters


@pytest.mark.parametrize("name", ["duration", "schedule"])
def test_noncomparable_windows_are_valid_failure(
    source, candidate, report, policy, name
):
    fold = source.folds[1].fold
    if name == "duration":
        object.__setattr__(fold, "test_end", fold.test_end + timedelta(days=1))
    else:
        object.__setattr__(
            fold,
            "test_rebalance_timestamps",
            (fold.test_start + timedelta(days=1), *fold.test_rebalance_timestamps),
        )
    _reidentify_source(source)
    result = _qualify(candidate, report, source, policy)
    assert result.failure_reasons == (Reason.NONCOMPARABLE_TEST_WINDOWS,)


@pytest.mark.parametrize("indices", [(1,), (0, 1)])
def test_losing_fold_and_different_winners_are_failed(
    source, candidate, report, policy, indices
):
    report = deepcopy(report)
    for index in indices:
        _winner(source, index, 1)
    result = _qualify(candidate, report, source, policy)
    assert result.candidate_selected_fold_count == 2 - len(indices)
    assert result.status is Status.FAILED
    assert result.failure_reasons == (Reason.CANDIDATE_NOT_SELECTED_EVERY_FOLD,)
    with pytest.raises(ResearchCandidateWalkForwardError):
        build(candidate, result)


@pytest.mark.parametrize("name", ["missing", "name", "ordinal"])
def test_candidate_training_provenance_malformed(
    source, candidate, report, policy, name
):
    report = deepcopy(report)
    fold = source.folds[1]
    row = next(
        row
        for row in fold.training_report.variants
        if row.variant_id == candidate.variant_id
    )
    if name == "missing":
        object.__setattr__(row, "variant_id", UUID(int=900))
        object.__setattr__(fold.selection, "selected_variant_id", row.variant_id)
        object.__setattr__(fold.test_report.variants[0], "variant_id", row.variant_id)
    elif name == "name":
        object.__setattr__(row, "variant_name", "Different")
    else:
        # Preserve the report's sequential ordinal invariant while changing the
        # candidate's ordinal: exchange identities and reselect its new row.
        other = fold.training_report.variants[1]
        object.__setattr__(other, "variant_id", row.variant_id)
        object.__setattr__(row, "variant_id", UUID(int=901))
        object.__setattr__(fold.selection, "selected_variant_id", row.variant_id)
        object.__setattr__(fold.test_report.variants[0], "variant_id", row.variant_id)
    _reidentify_source(source)
    before = deepcopy(source)
    with pytest.raises(ResearchCandidateWalkForwardError):
        _qualify(candidate, report, source, policy)
    assert source == before


@pytest.mark.parametrize(
    "name", ["result_id", "report_id", "metrics", "selection", "schedule"]
)
def test_complete_defensive_revalidation(source, candidate, report, policy, name):
    report = deepcopy(report)
    if name == "result_id":
        object.__setattr__(source, "result_id", UUID(int=300))
    elif name == "report_id":
        object.__setattr__(source.folds[1].training_report, "report_id", UUID(int=301))
    elif name == "metrics":
        object.__setattr__(
            source.folds[1].test_report.variants[0].metrics,
            "simulation_return",
            Decimal("NaN"),
        )
    elif name == "selection":
        object.__setattr__(source.folds[1].selection, "selected_rank", True)
    else:
        object.__setattr__(source.folds[1].fold, "test_rebalance_timestamps", [])
    before = repr(source)
    with pytest.raises((HistoricalExperimentError, ValueError)):
        _qualify(candidate, report, source, policy)
    assert repr(source) == before


@pytest.mark.parametrize("name", ["minimum", "median", "drawdown", "folds"])
@pytest.mark.parametrize("fail", [False, True])
def test_exact_thresholds(candidate, report, source, policy, name, fail):
    baseline = _qualify(candidate, report, source, policy)
    minimum = baseline.minimum_observed_simulation_return
    median = baseline.median_simulation_return
    drawdown = baseline.maximum_observed_drawdown_percentage
    if name == "minimum":
        value = minimum + Decimal("0.00000001") if fail else minimum
        policy = Policy(2, value, max(value, median), drawdown)
        reason = Reason.MINIMUM_SIMULATION_RETURN_BELOW_THRESHOLD
    elif name == "median":
        policy = Policy(
            2, minimum, median + Decimal("0.00000001") if fail else median, drawdown
        )
        reason = Reason.MEDIAN_SIMULATION_RETURN_BELOW_THRESHOLD
    elif name == "drawdown":
        # Positive retained test observation exercises the actual analyzer gate.
        for fold in source.folds:
            object.__setattr__(
                fold.test_report.variants[0].metrics,
                "maximum_drawdown_percentage",
                Decimal("2.5"),
            )
        _reidentify_source(source)
        policy = Policy(
            2, minimum, median, Decimal("2.4999") if fail else Decimal("2.5")
        )
        reason = Reason.MAXIMUM_DRAWDOWN_PERCENTAGE_ABOVE_THRESHOLD
    else:
        policy = replace(policy, minimum_fold_count=3 if fail else 2)
        reason = Reason.INSUFFICIENT_FOLDS
    result = _qualify(candidate, report, source, policy)
    assert (reason in result.failure_reasons) is fail
    assert (result.status is Status.FAILED) is fail


def test_all_failures_canonical_order_and_verifiable(candidate, report, source, policy):
    report = deepcopy(report)
    _winner(source, 1, 1)
    object.__setattr__(
        source.folds[1].fold,
        "test_end",
        source.folds[1].fold.test_end + timedelta(days=1),
    )
    # Existing metrics model accepts retained finite observations; no execution.
    for fold in source.folds:
        object.__setattr__(
            fold.test_report.variants[0].metrics, "simulation_return", Decimal("-1")
        )
        object.__setattr__(
            fold.test_report.variants[0].metrics,
            "maximum_drawdown_percentage",
            Decimal("2"),
        )
    _reidentify_source(source)
    policy = Policy(3, Decimal("0"), Decimal("0"), Decimal("1"))
    result = _qualify(candidate, report, source, policy)
    assert result.failure_reasons == tuple(Reason)
    assert result.status is Status.FAILED
    assert Qualification.from_json(result.to_json()) == result
    verify(
        result, candidate, report, source, policy, source_head=HEAD, source_tree=TREE
    )


def test_repeatable_context_independent_exact_median(candidate, report, source, policy):
    for fold, value in zip(
        source.folds, ("0.123456789123456789", "0.987654321987654321"), strict=True
    ):
        object.__setattr__(
            fold.test_report.variants[0].metrics, "simulation_return", Decimal(value)
        )
    _reidentify_source(source)
    baseline = _qualify(candidate, report, source, policy)
    assert baseline.median_simulation_return == Decimal("0.555555555555555555")
    for precision in (1, 2, 50):
        with localcontext(Context(prec=precision, Emin=-2, Emax=2)):
            assert replace(policy).to_json() == policy.to_json()
            result = _qualify(candidate, report, source, policy)
            assert result == baseline
            assert result.to_json() == baseline.to_json()
            assert (
                build(candidate, result).to_json()
                == build(candidate, baseline).to_json()
            )


@pytest.mark.parametrize(
    "name,value",
    [
        ("candidate_id", UUID(int=99)),
        ("walk_forward_result_id", UUID(int=99)),
        ("walk_forward_request_id", UUID(int=99)),
        ("source_historical_fingerprint", UUID(int=99)),
        ("aggregate_result_id", UUID(int=99)),
        ("qualification_source_head", "a" * 40),
        ("qualification_source_tree", "b" * 40),
        ("fold_count", 3),
        ("candidate_selected_fold_count", 0),
        ("test_windows_comparable", False),
        ("minimum_observed_simulation_return", Decimal("-1000")),
        ("median_simulation_return", Decimal("1000")),
        ("maximum_observed_drawdown_percentage", Decimal("1000")),
    ],
)
def test_qualification_semantic_identity(
    candidate, report, source, policy, name, value
):
    result = _qualify(candidate, report, source, policy)
    assert replace(result, **{name: value}).qualification_id != result.qualification_id


@pytest.mark.parametrize(
    "name", ["candidate", "report", "walk", "policy", "head", "tree"]
)
def test_independent_verifier_rejects_external_drift(
    candidate, report, source, policy, name
):
    result = _qualify(candidate, report, source, policy)
    head, tree = HEAD, TREE
    if name == "candidate":
        candidate = replace(candidate, variant_name="Other")
    elif name == "report":
        report = deepcopy(report)
        object.__setattr__(report.variants[0], "variant_name", "Other")
        _reidentify_report(report)
    elif name == "walk":
        object.__setattr__(source, "request_id", UUID(int=555))
        _reidentify_source(source)
    elif name == "policy":
        policy = replace(policy, minimum_fold_count=3)
    elif name == "head":
        head = "a" * 40
    else:
        tree = "b" * 40
    with pytest.raises(HistoricalExperimentError):
        verify(
            result,
            candidate,
            report,
            source,
            policy,
            source_head=head,
            source_tree=tree,
        )


@pytest.mark.parametrize("name", ["candidate", "report", "walk", "policy"])
def test_exact_input_types(candidate, report, source, policy, name):
    values = [candidate, report, source, policy]
    values[["candidate", "report", "walk", "policy"].index(name)] = None
    with pytest.raises(HistoricalExperimentError):
        _qualify(*values)


@pytest.mark.parametrize("source_id", [True, "A" * 40, "a" * 39, "a" * 41, "g" * 40])
def test_exact_qualification_source(candidate, report, source, policy, source_id):
    with pytest.raises(ResearchCandidateWalkForwardError):
        qualify(
            candidate, report, source, policy, source_head=source_id, source_tree=TREE
        )


@pytest.fixture
def artifacts(candidate, report, source, policy):
    qualification = _qualify(candidate, report, source, policy)
    return policy, qualification, build(candidate, qualification)


@pytest.mark.parametrize("index", range(3))
def test_strict_roundtrip_and_forged_fields(artifacts, index):
    artifact = artifacts[index]
    payload = artifact.to_json()
    assert type(artifact).from_json(payload) == artifact
    for name in json.loads(payload):
        raw = json.loads(payload)
        del raw[name]
        with pytest.raises(ResearchCandidateWalkForwardError):
            type(artifact).from_json(_json(raw))
    bad = [
        payload + "\n",
        json.dumps(json.loads(payload), indent=2),
        payload.replace("{", '{"schema":"forged",', 1),
        _json({**json.loads(payload), "unknown": 0}),
    ]
    for name in ("schema", "policy_id", "qualification_id", "candidate_id", "stage"):
        raw = json.loads(payload)
        if name in raw:
            raw[name] = "SHADOW" if name == "stage" else "forged"
            bad.append(_json(raw))
    for value in bad:
        with pytest.raises(ResearchCandidateWalkForwardError):
            type(artifact).from_json(value)


@pytest.mark.parametrize(
    "text", ["-100.0", "-1E+2", "-0100", "NaN", "Infinity", " -100"]
)
def test_policy_noncanonical_decimal_json(policy, text):
    raw = json.loads(policy.to_json())
    raw["minimum_fold_simulation_return"] = text
    with pytest.raises(ResearchCandidateWalkForwardError):
        Policy.from_json(_json(raw))


@pytest.mark.parametrize("value", [True, 2.0, "2"])
def test_json_bool_and_number_confusion(policy, value):
    raw = json.loads(policy.to_json())
    raw["minimum_fold_count"] = value
    with pytest.raises(ResearchCandidateWalkForwardError):
        Policy.from_json(_json(raw))


def test_parsing_is_self_consistency_only(candidate, report, source, policy):
    result = _qualify(candidate, report, source, policy)
    other = replace(result, aggregate_result_id=UUID(int=400))
    parsed = Qualification.from_json(other.to_json())
    assert parsed == other
    with pytest.raises(ResearchCandidateWalkForwardError):
        verify(
            parsed,
            candidate,
            report,
            source,
            policy,
            source_head=HEAD,
            source_tree=TREE,
        )


def test_successor_wrong_predecessor_and_qualification(
    candidate, report, source, policy
):
    qualification = _qualify(candidate, report, source, policy)
    successor = build(candidate, qualification)
    assert successor == build(candidate, qualification)
    with pytest.raises(ResearchCandidateWalkForwardError):
        build(replace(candidate, rank=None), qualification)
    different = replace(qualification, qualification_source_head="c" * 40)
    assert build(candidate, different).candidate_id != successor.candidate_id
    with pytest.raises(ResearchCandidateWalkForwardError):
        verify_successor(successor, candidate, different)
    with pytest.raises(ResearchCandidateWalkForwardError):
        replace(successor, predecessor_candidate_id=UUID(int=4))
    with pytest.raises((TypeError, ValueError)):
        replace(successor, stage=ResearchCandidateStage.SHADOW)
    with pytest.raises(FrozenInstanceError):
        successor.rank = 1
    for artifact, name, value in (
        (qualification, "status", Status.FAILED),
        (qualification, "qualification_id", UUID(int=4)),
        (qualification, "failure_reasons", (Reason.INSUFFICIENT_FOLDS,)),
        (successor, "stage", ResearchCandidateStage.SHADOW),
        (successor, "candidate_id", UUID(int=4)),
    ):
        forged = deepcopy(artifact)
        object.__setattr__(forged, name, value)
        with pytest.raises(ResearchCandidateWalkForwardError):
            forged.to_json()


def test_public_exports_and_closed_capability_ast():
    import trading_bot.experiments as package

    for name in module.__all__:
        assert getattr(package, name) is getattr(module, name)
    tree = ast.parse(inspect.getsource(module))
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports == {
        "__future__",
        "json",
        "re",
        "copy",
        "dataclasses",
        "decimal",
        "enum",
        "uuid",
        "trading_bot.experiments.research_candidate",
        "trading_bot.experiments.report",
        "trading_bot.experiments.walk_forward",
        "trading_bot.experiments.walk_forward_analytics",
    }
    allowed_names = {
        "trading_bot.experiments.walk_forward": {
            "HistoricalExperimentWalkForwardResult"
        },
        "trading_bot.experiments.research_candidate": {
            "ResearchCandidateError",
            "ResearchCandidateStage",
            "ResearchStrategyCandidate",
            "verify_research_candidate_against_report",
        },
        "trading_bot.experiments.report": {"HistoricalExperimentReport"},
        "trading_bot.experiments.walk_forward_analytics": {
            "HistoricalExperimentWalkForwardAggregateAnalyzer",
            "HistoricalExperimentWalkForwardAggregateMetric",
            "HistoricalExperimentWalkForwardAggregateOperation",
            "HistoricalExperimentWalkForwardAggregatePolicy",
            "HistoricalExperimentWalkForwardMetricPolicy",
        },
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in allowed_names:
            assert {alias.name for alias in node.names} == allowed_names[node.module]
    forbidden = {
        "open",
        "exec",
        "eval",
        "__import__",
        "hash",
        "id",
        "float",
        "uuid4",
        "now",
        "utcnow",
        "today",
        "time",
        "run",
        "read_text",
        "write_text",
        "connect",
        "request",
        "send",
        "promote",
        "advance",
        "set_stage",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else getattr(node.func, "attr", "")
            )
            assert name not in forbidden
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.name not in {"promote", "advance", "set_stage"}
    assert "ProductionStrategyContract" not in inspect.getsource(module)
    assert "HistoricalExperimentWalkForwardRunner" not in inspect.getsource(module)


@pytest.mark.parametrize("index", range(3))
def test_json_order_constants_and_exact_representations(artifacts, index):
    artifact = artifacts[index]
    payload = artifact.to_json()
    raw = json.loads(payload)
    alternate_order = json.dumps(
        dict(reversed(tuple(raw.items()))), separators=(",", ":")
    )
    for value in (
        alternate_order,
        payload.replace('"schema":', '"schema":NaN,"extra":', 1),
    ):
        with pytest.raises(ResearchCandidateWalkForwardError):
            type(artifact).from_json(value)
    for name, scalar in raw.items():
        if type(scalar) is int:
            malformed = {**raw, name: True}
            with pytest.raises(ResearchCandidateWalkForwardError):
                type(artifact).from_json(_json(malformed))
        if name.endswith("_id"):
            malformed = {**raw, name: scalar.replace("-", "")}
            with pytest.raises(ResearchCandidateWalkForwardError):
                type(artifact).from_json(_json(malformed))


def test_qualification_reasons_and_nested_policy_not_caller_authority(artifacts):
    _, qualification, _ = artifacts
    raw = json.loads(qualification.to_json())
    for name, value in (
        ("status", "FAILED"),
        ("failure_reasons", [Reason.INSUFFICIENT_FOLDS.value]),
        ("policy_id", str(UUID(int=1))),
        ("test_windows_comparable", 1),
        ("minimum_observed_simulation_return", "0.0000"),
    ):
        with pytest.raises(ResearchCandidateWalkForwardError):
            Qualification.from_json(_json({**raw, name: value}))
    raw["policy"]["metadata"] = []
    with pytest.raises(ResearchCandidateWalkForwardError):
        Qualification.from_json(_json(raw))
    policy = replace(qualification.policy, minimum_fold_count=3)
    different = replace(qualification, policy=policy)
    assert different.qualification_id != qualification.qualification_id
    assert different.policy_id == policy.policy_id


@pytest.mark.parametrize(
    "name,value",
    [
        ("fold_count", True),
        ("fold_count", 0),
        ("candidate_selected_fold_count", True),
        ("candidate_selected_fold_count", -1),
        ("candidate_selected_fold_count", 3),
        ("test_windows_comparable", 1),
        ("candidate_id", "bad"),
        ("aggregate_result_id", None),
        ("minimum_observed_simulation_return", 0.0),
        ("median_simulation_return", Decimal("NaN")),
        ("maximum_observed_drawdown_percentage", Decimal("-1")),
    ],
)
def test_qualification_exact_immutable_fields(artifacts, name, value):
    with pytest.raises(ResearchCandidateWalkForwardError):
        replace(artifacts[1], **{name: value})


def test_remaining_fold_count_failure_consumes_valid_one_fold(
    candidate, report, source, policy
):
    object.__setattr__(source, "folds", (source.folds[0],))
    _reidentify_source(source)
    result = _qualify(candidate, report, source, policy)
    assert result.fold_count == 1
    assert result.failure_reasons == (Reason.INSUFFICIENT_FOLDS,)


def test_result_and_successor_identity_framing(artifacts):
    policy, q, successor = artifacts
    material = (
        "research-candidate-walk-forward-qualification-identity/v1",
        q.schema,
        str(q.candidate_id),
        str(policy.policy_id),
        policy.schema,
        "2",
        "-100",
        "-100",
        "100",
        HEAD,
        TREE,
        str(q.walk_forward_result_id),
        str(q.walk_forward_request_id),
        str(q.source_historical_fingerprint),
        str(q.aggregate_result_id),
        "2",
        "2",
        "true",
        str(q.minimum_observed_simulation_return),
        str(q.median_simulation_return),
        str(q.maximum_observed_drawdown_percentage),
        "PASSED",
        "0",
    )
    # Canonical Decimal material is independently extracted from canonical JSON;
    # the UUID is over framed semantic scalars, never over serialized bytes.
    raw = json.loads(q.to_json())
    material = (
        *material[:18],
        raw["minimum_observed_simulation_return"],
        raw["median_simulation_return"],
        raw["maximum_observed_drawdown_percentage"],
        *material[21:],
    )
    assert q.qualification_id == uuid5(
        UUID("3c206910-6ced-5f74-b515-52901f6bdbbb"),
        "".join(f"{len(v.encode('utf-8'))}:{v}" for v in material),
    )
    material = (
        "research-strategy-candidate-walk-forward-passed-identity/v1",
        successor.schema,
        "WALK_FORWARD_PASSED",
        str(successor.predecessor_candidate_id),
        str(successor.qualification_id),
        HEAD,
        TREE,
        str(successor.report_id),
        str(successor.experiment_result_id),
        str(successor.variant_id),
        str(successor.caller_ordinal),
        successor.variant_name,
        str(successor.rank),
    )
    assert successor.candidate_id == uuid5(
        UUID("e9f8a60f-7b82-57d6-868a-040cb79bb81a"),
        "".join(f"{len(v.encode('utf-8'))}:{v}" for v in material),
    )


def test_selected_rank_bool_rejected_even_with_recomputed_source_identity(
    source, candidate, report, policy
):
    object.__setattr__(source.folds[1].selection, "selected_rank", True)
    _reidentify_source(source)
    before = deepcopy(source)
    with pytest.raises(ResearchCandidateWalkForwardError):
        _qualify(candidate, report, source, policy)
    assert source == before


def test_rejects_noncanonical_normalized_source_without_touching_caller(
    source, candidate, report, policy
):
    object.__setattr__(source, "folds", list(source.folds))
    before = deepcopy(source)
    with pytest.raises(ResearchCandidateWalkForwardError):
        _qualify(candidate, report, source, policy)
    assert source == before
    assert type(source.folds) is list
