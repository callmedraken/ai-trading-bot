import csv
import io
import json
from hashlib import sha256
from pathlib import Path

import pytest

from trading_bot.cli import historical_experiment
from trading_bot.cli.exceptions import HistoricalExperimentParetoOutputError
from trading_bot.cli.historical_experiment_pareto_serialization import (
    PARETO_CSV_HEADER,
    build_pareto_json,
    serialize_pareto_csv,
    serialize_pareto_json,
)

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "examples" / "historical-experiment.example.json"
POLICY = ROOT / "examples" / "historical-experiment-pareto-policy.example.json"
FIXTURES = ROOT / "tests" / "fixtures" / "cli"


@pytest.fixture(scope="module")
def result():
    run = historical_experiment.run_cli(
        EXPERIMENT, collect_audit_records=False, pareto_policy_path=POLICY
    )
    assert run.pareto_result is not None
    return run.pareto_result


def test_json_is_exact_pareto_boundary(result) -> None:
    tree = build_pareto_json(result)
    assert tree["schema_version"] == 1
    section = tree["pareto_result"]
    assert section["result_id"] == str(result.result_id)
    assert len(section["variants"]) == 4
    assert len(section["frontier_variant_ids"]) == 4
    assert section["dominance_records"] == []
    assert "report" not in tree


def test_json_modes_are_deterministic_and_typed(result) -> None:
    compact = serialize_pareto_json(result)
    pretty = serialize_pareto_json(result, pretty=True)
    assert compact == serialize_pareto_json(result)
    assert pretty == serialize_pareto_json(result, pretty=True)
    assert compact.endswith("\n") and pretty.endswith("\n")
    assert isinstance(
        json.loads(compact)["pareto_result"]["variants"][0]["is_nondominated"], bool
    )


def test_csv_has_exact_header_and_variant_rows(result) -> None:
    rows = list(csv.reader(io.StringIO(serialize_pareto_csv(result))))
    assert tuple(rows[0]) == PARETO_CSV_HEADER
    assert len(PARETO_CSV_HEADER) == len(set(PARETO_CSV_HEADER)) == 21
    assert [row[0] for row in rows[1:]] == ["VARIANT"] * 4
    assert json.loads(rows[1][4])[0] == {
        "direction": "DESCENDING",
        "metric": "SIMULATION_RETURN",
    }
    assert rows[1][9] == "true"


def test_serializers_require_exact_result(result) -> None:
    with pytest.raises(HistoricalExperimentParetoOutputError):
        build_pareto_json(object())  # type: ignore[arg-type]
    with pytest.raises(HistoricalExperimentParetoOutputError):
        serialize_pareto_json(result, pretty=1)  # type: ignore[arg-type]


def test_serializers_match_exact_hashed_fixtures(result) -> None:
    outputs = {
        "historical-experiment-pareto-v1-compact.json": serialize_pareto_json(result),
        "historical-experiment-pareto-v1-pretty.json": serialize_pareto_json(
            result, pretty=True
        ),
        "historical-experiment-pareto-v1.csv": serialize_pareto_csv(result),
    }
    hashes = {
        "historical-experiment-pareto-v1-compact.json": (
            "6796eef423529b3e3b0be12457bcf9732e8bb1b8ecc70a595d2c95bd9f5e3050"
        ),
        "historical-experiment-pareto-v1-pretty.json": (
            "550b7c4a9238c25a7466288d9aff5919c9d2981fb9bd484dcf8055aaa4dbc3c8"
        ),
        "historical-experiment-pareto-v1.csv": (
            "abec2c7b5b7148a4a5706bece3ebba980865b5c2382ad72ba7926d18da7c572d"
        ),
    }
    for name, output in outputs.items():
        fixture = (FIXTURES / name).read_text(encoding="utf-8").rstrip("\n") + "\n"
        assert output == fixture
        assert sha256(output.encode()).hexdigest() == hashes[name]
        assert output.endswith("\n") and not output.endswith("\n\n")
