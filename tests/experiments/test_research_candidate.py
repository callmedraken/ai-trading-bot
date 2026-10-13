"""Architecture 137: inert canonical evidence, explicit selection and closed stages."""

import ast
import inspect
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from decimal import localcontext
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from trading_bot.cli.historical_experiment_report_serialization import (
    deserialize_compact_report_json,
)
from trading_bot.experiments import research_candidate as module
from trading_bot.experiments.report import HistoricalExperimentReport
from trading_bot.experiments.research_candidate import (
    MAX_RESEARCH_CANDIDATE_NAME_LENGTH,
    MAX_RESEARCH_CANDIDATE_ORDINAL,
    MAX_RESEARCH_CANDIDATE_RANK,
    RESEARCH_CANDIDATE_IDENTITY_VERSION,
    RESEARCH_CANDIDATE_SCHEMA,
    ResearchCandidateError,
    ResearchCandidateStage,
    ResearchStrategyCandidate,
    build_backtested_research_candidate,
    verify_research_candidate_against_report,
)

HEAD = "778151fe8f91632a1af66384a3ab0a85d8d65069"
TREE = "03c50482427b04ebfc6ed061d048bb95e86edeae"


@pytest.fixture
def report() -> HistoricalExperimentReport:
    path = (
        Path(__file__).parents[1]
        / "fixtures/cli/historical-experiment-compact-report-v1-compact.json"
    )
    return deserialize_compact_report_json(path.read_text(encoding="utf-8"))


@pytest.fixture
def candidate(report: HistoricalExperimentReport) -> ResearchStrategyCandidate:
    return _build(report, report.variants[1].variant_id)


def _build(
    report: HistoricalExperimentReport, variant_id: UUID
) -> ResearchStrategyCandidate:
    return build_backtested_research_candidate(
        report, selected_variant_id=variant_id, source_head=HEAD, source_tree=TREE
    )


def _json(raw: object) -> str:
    return json.dumps(raw, sort_keys=True, separators=(",", ":"))


def test_exact_ordered_lifecycle_and_package_exports() -> None:
    import trading_bot.experiments as package

    assert tuple(stage.value for stage in ResearchCandidateStage) == (
        "EXPERIMENTAL",
        "BACKTESTED",
        "WALK_FORWARD_PASSED",
        "SHADOW",
        "PAPER_CANDIDATE",
        "AWAITING_HUMAN_PROMOTION",
    )
    for name in module.__all__:
        assert getattr(package, name) is getattr(module, name)


def test_stage_schema_and_identity_are_not_constructor_arguments(candidate) -> None:
    assert candidate.schema == RESEARCH_CANDIDATE_SCHEMA
    assert candidate.stage is ResearchCandidateStage.BACKTESTED
    assert not {"stage", "schema", "candidate_id"} & {
        item.name for item in fields(candidate) if item.init
    }
    with pytest.raises(FrozenInstanceError):
        candidate.stage = ResearchCandidateStage.SHADOW
    with pytest.raises((TypeError, ValueError)):
        replace(candidate, stage=ResearchCandidateStage.SHADOW)
    for stage in ResearchCandidateStage:
        if stage is ResearchCandidateStage.BACKTESTED:
            continue
        forged = deepcopy(candidate)
        object.__setattr__(forged, "stage", stage)
        with pytest.raises(ResearchCandidateError):
            forged.to_json()


def test_uuid5_identity_includes_all_retained_semantics(candidate) -> None:
    values = (
        RESEARCH_CANDIDATE_IDENTITY_VERSION,
        candidate.schema,
        candidate.stage.value,
        HEAD,
        TREE,
        str(candidate.report_id),
        str(candidate.experiment_result_id),
        str(candidate.variant_id),
        str(candidate.caller_ordinal),
        candidate.variant_name,
        str(candidate.rank),
    )
    material = "".join(f"{len(value.encode('utf-8'))}:{value}" for value in values)
    assert candidate.candidate_id == uuid5(
        UUID("c914e214-9553-56ce-978a-ddd33bf6210f"), material
    )
    assert candidate.candidate_id.version == 5
    assert replace(candidate).candidate_id == candidate.candidate_id
    with localcontext() as context:
        context.prec = 2
        assert replace(candidate).to_json() == candidate.to_json()


@pytest.mark.parametrize(
    "name,value",
    [
        ("source_head", "a" * 40),
        ("source_tree", "b" * 40),
        ("report_id", UUID(int=1)),
        ("experiment_result_id", UUID(int=2)),
        ("variant_id", UUID(int=3)),
        ("caller_ordinal", 0),
        ("variant_name", "Other | 2:é"),
        ("rank", 1),
        ("rank", None),
    ],
)
def test_every_mutable_semantic_changes_identity(candidate, name, value) -> None:
    assert replace(candidate, **{name: value}).candidate_id != candidate.candidate_id


@pytest.mark.parametrize("name", ["source_head", "source_tree"])
@pytest.mark.parametrize(
    "value",
    [None, 1, True, "", "a" * 39, "a" * 41, "A" * 40, "g" * 40, "a" * 40 + "\n"],
)
def test_invalid_source(candidate, name, value) -> None:
    with pytest.raises(ResearchCandidateError):
        replace(candidate, **{name: value})


@pytest.mark.parametrize("name", ["report_id", "experiment_result_id", "variant_id"])
@pytest.mark.parametrize(
    "value", [None, True, 1, "00000000-0000-0000-0000-000000000001"]
)
def test_exact_uuid_fields(candidate, name, value) -> None:
    with pytest.raises(ResearchCandidateError):
        replace(candidate, **{name: value})


@pytest.mark.parametrize(
    "value", [True, False, 1.0, "1", None, -1, MAX_RESEARCH_CANDIDATE_ORDINAL + 1]
)
def test_invalid_ordinal(candidate, value) -> None:
    with pytest.raises(ResearchCandidateError):
        replace(candidate, caller_ordinal=value)


@pytest.mark.parametrize(
    "value", [True, False, 1.0, "1", 0, -1, MAX_RESEARCH_CANDIDATE_RANK + 1]
)
def test_invalid_rank(candidate, value) -> None:
    with pytest.raises(ResearchCandidateError):
        replace(candidate, rank=value)


@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        "",
        " ",
        " name",
        "name ",
        "\nname",
        "x" * (MAX_RESEARCH_CANDIDATE_NAME_LENGTH + 1),
        "\ud800",
    ],
)
def test_invalid_name(candidate, value) -> None:
    with pytest.raises(ResearchCandidateError):
        replace(candidate, variant_name=value)


def test_bounds_and_unicode_roundtrip(candidate) -> None:
    bounded = replace(
        candidate,
        caller_ordinal=MAX_RESEARCH_CANDIDATE_ORDINAL,
        rank=MAX_RESEARCH_CANDIDATE_RANK,
        variant_name="é" * MAX_RESEARCH_CANDIDATE_NAME_LENGTH,
    )
    assert ResearchStrategyCandidate.from_json(bounded.to_json()) == bounded


@pytest.mark.parametrize("ordinal", [0, 1, 2, 3])
def test_explicit_selection_retains_exact_report_evidence(report, ordinal) -> None:
    before = deepcopy(report)
    row = report.variants[ordinal]
    result = _build(report, row.variant_id)
    assert result.report_id == report.report_id
    assert result.experiment_result_id == report.experiment_result_id
    for name in ("variant_id", "caller_ordinal", "variant_name", "rank"):
        assert getattr(result, name) == getattr(row, name)
    verify_research_candidate_against_report(result, report)
    assert report == before


def test_unranked_selection_uses_completed_evidence_only(report, monkeypatch) -> None:
    # Fixed identity of the existing fixture with ranking/comparison fields removed.
    unranked = deepcopy(report)
    object.__setattr__(unranked, "ranking", None)
    for row in unranked.variants:
        object.__setattr__(row, "rank", None)
        object.__setattr__(row, "comparison_values", ())
    object.__setattr__(unranked, "report_id", UNRANKED_REPORT_ID)
    unranked.__post_init__()
    from trading_bot.experiments import HistoricalExperimentRunner

    def forbidden(*args, **kwargs):
        raise AssertionError("candidate must not execute research")

    monkeypatch.setattr(HistoricalExperimentRunner, "run", forbidden)
    result = _build(unranked, unranked.variants[1].variant_id)
    assert result.rank is None
    assert (
        result.candidate_id
        != _build(report, report.variants[1].variant_id).candidate_id
    )
    verify_research_candidate_against_report(result, unranked)


def test_no_auto_selection(report) -> None:
    with pytest.raises(TypeError):
        build_backtested_research_candidate(report, source_head=HEAD, source_tree=TREE)
    with pytest.raises(ResearchCandidateError):
        _build(report, UUID(int=1))
    with pytest.raises(ResearchCandidateError):
        _build(report, str(report.variants[0].variant_id))


@pytest.mark.parametrize(
    "name,value",
    [
        ("report_id", UUID(int=1)),
        ("experiment_result_id", UUID(int=2)),
        ("variant_id", UUID(int=3)),
        ("variant_id", None),
        ("caller_ordinal", True),
        ("variant_name", " bad "),
        ("rank", 0),
        ("metrics", None),
    ],
)
def test_revalidates_report_without_mutating_it(report, candidate, name, value) -> None:
    if name in {"report_id", "experiment_result_id"}:
        object.__setattr__(report, name, value)
    else:
        object.__setattr__(report.variants[1], name, value)
    before = deepcopy(report)
    with pytest.raises((ValueError, TypeError)):
        _build(report, candidate.variant_id)
    with pytest.raises((ValueError, TypeError)):
        verify_research_candidate_against_report(candidate, report)
    assert report == before


def test_duplicate_report_variant_fails(report) -> None:
    object.__setattr__(report.variants[1], "variant_id", report.variants[0].variant_id)
    with pytest.raises(ValueError):
        _build(report, report.variants[0].variant_id)


@pytest.mark.parametrize(
    "name,value",
    [
        ("report_id", UUID(int=1)),
        ("experiment_result_id", UUID(int=2)),
        ("variant_id", UUID(int=3)),
        ("caller_ordinal", 0),
        ("variant_name", "different"),
        ("rank", 1),
        ("rank", None),
    ],
)
def test_self_consistency_is_not_external_reconciliation(
    report, candidate, name, value
) -> None:
    altered = replace(candidate, **{name: value})
    parsed = ResearchStrategyCandidate.from_json(altered.to_json())
    with pytest.raises(ResearchCandidateError):
        verify_research_candidate_against_report(parsed, report)


@pytest.mark.parametrize(
    "name,value",
    [
        ("candidate_id", UUID(int=1)),
        ("candidate_id", "bad"),
        ("schema", "other"),
        ("stage", "BACKTESTED"),
        ("caller_ordinal", True),
        ("variant_name", " name "),
        ("rank", 0),
    ],
)
def test_revalidates_forged_candidate(report, candidate, name, value) -> None:
    object.__setattr__(candidate, name, value)
    with pytest.raises(ResearchCandidateError):
        verify_research_candidate_against_report(candidate, report)
    with pytest.raises(ResearchCandidateError):
        candidate.to_json()


def test_exact_model_types(report, candidate) -> None:
    class ReportSubclass(HistoricalExperimentReport):
        pass

    class CandidateSubclass(ResearchStrategyCandidate):
        pass

    subclass_report = ReportSubclass(
        **{f.name: getattr(report, f.name) for f in fields(report)}
    )
    subclass_candidate = CandidateSubclass(
        **{f.name: getattr(candidate, f.name) for f in fields(candidate) if f.init}
    )
    for bad in (None, object(), subclass_report):
        with pytest.raises(ResearchCandidateError):
            _build(bad, candidate.variant_id)
    for bad in (None, object(), subclass_candidate):
        with pytest.raises(ResearchCandidateError):
            verify_research_candidate_against_report(bad, report)


def test_strict_canonical_roundtrip(candidate) -> None:
    encoded = candidate.to_json()
    assert encoded == _json(json.loads(encoded))
    assert ResearchStrategyCandidate.from_json(encoded).to_json() == encoded
    assert set(json.loads(encoded)) == {f.name for f in fields(candidate)}


@pytest.mark.parametrize("name", [f.name for f in fields(ResearchStrategyCandidate)])
def test_missing_and_duplicate_fields(candidate, name) -> None:
    raw = json.loads(candidate.to_json())
    value = raw.pop(name)
    with pytest.raises(ResearchCandidateError):
        ResearchStrategyCandidate.from_json(_json(raw))
    encoded = candidate.to_json()
    duplicated = encoded[:-1] + "," + _json(name) + ":" + _json(value) + "}"
    with pytest.raises(ResearchCandidateError):
        ResearchStrategyCandidate.from_json(duplicated)


@pytest.mark.parametrize(
    "name,value",
    [
        ("unknown", 1),
        ("schema", "research-strategy-candidate/v2"),
        ("candidate_id", "00000000-0000-0000-0000-000000000001"),
        ("source_head", HEAD.upper()),
        ("source_tree", TREE + "\n"),
        ("caller_ordinal", True),
        ("caller_ordinal", 1.0),
        ("rank", True),
        ("rank", 0),
        ("rank", float("nan")),
        ("rank", float("inf")),
        ("variant_name", " trimmed "),
        ("report_id", 1),
        *(
            ("stage", stage.value)
            for stage in ResearchCandidateStage
            if stage is not ResearchCandidateStage.BACKTESTED
        ),
        ("stage", "backtested"),
    ],
)
def test_invalid_json_fields(candidate, name, value) -> None:
    raw = json.loads(candidate.to_json())
    raw[name] = value
    with pytest.raises(ResearchCandidateError):
        ResearchStrategyCandidate.from_json(_json(raw))


@pytest.mark.parametrize(
    "name", ["candidate_id", "report_id", "experiment_result_id", "variant_id"]
)
@pytest.mark.parametrize("form", ["upper", "hex", "braces"])
def test_noncanonical_uuids(candidate, name, form) -> None:
    raw = json.loads(candidate.to_json())
    original = raw[name]
    raw[name] = {
        "upper": original.upper(),
        "hex": original.replace("-", ""),
        "braces": "{" + original + "}",
    }[form]
    with pytest.raises(ResearchCandidateError):
        ResearchStrategyCandidate.from_json(_json(raw))


def test_noncanonical_whitespace_order_and_number_forms(candidate) -> None:
    encoded = candidate.to_json()
    raw = json.loads(encoded)
    invalid = [
        encoded + "\n",
        " " + encoded,
        json.dumps(raw, indent=2),
        json.dumps(dict(reversed(list(raw.items()))), separators=(",", ":")),
        encoded.replace('"caller_ordinal":1', '"caller_ordinal":1e0'),
        "null",
        "[]",
        "{}",
        "{",
        encoded.encode(),
    ]
    for value in invalid:
        with pytest.raises(ResearchCandidateError):
            ResearchStrategyCandidate.from_json(value)


def test_static_capability_boundary() -> None:
    tree = ast.parse(inspect.getsource(module))
    allowed_imports = {
        "__future__",
        "json",
        "re",
        "copy",
        "dataclasses",
        "enum",
        "uuid",
        "trading_bot.experiments.exceptions",
        "trading_bot.experiments.report",
    }
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imports == allowed_imports
    forbidden = {
        "Path",
        "open",
        "environ",
        "getenv",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "httpx2",
        "urlopen",
        "sqlite3",
        "eval",
        "exec",
        "__import__",
        "import_module",
        "uuid4",
        "hash",
        "set_stage",
        "advance",
        "promote",
        "ProductionStrategyContract",
        "MovingAverageCrossoverConfig",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names.update(
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    )
    assert not names & forbidden
    assert {name for name in module.__all__ if callable(getattr(module, name))} == {
        "ResearchCandidateError",
        "ResearchCandidateStage",
        "ResearchStrategyCandidate",
        "build_backtested_research_candidate",
        "verify_research_candidate_against_report",
    }


UNRANKED_REPORT_ID = UUID("6bfe0a85-5d57-5b77-a6b3-f04796faf006")
