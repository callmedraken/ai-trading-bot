import csv
import io
import json
from decimal import Context, localcontext
from hashlib import sha256
from pathlib import Path

import pytest

from trading_bot.cli import historical_experiment
from trading_bot.cli.exceptions import HistoricalExperimentPairwiseOutputError
from trading_bot.cli.historical_experiment_pairwise_serialization import (
    PAIRWISE_CSV_HEADER,
    PAIRWISE_EXPERIMENT_SCHEMA_VERSION,
    build_pairwise_json,
    serialize_pairwise_csv,
    serialize_pairwise_json,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment.example.json"
POLICY = ROOT / "examples" / "historical-experiment-pairwise-policy.example.json"
FIXTURES = ROOT / "tests" / "fixtures" / "cli"


@pytest.fixture(scope="module")
def result():
    run = historical_experiment.run_cli(
        EXAMPLE,
        collect_audit_records=False,
        pairwise_policy_path=POLICY,
    )
    assert run.pairwise_result is not None
    return run.pairwise_result


def test_json_has_exact_versioned_pairwise_boundary(result) -> None:
    tree = build_pairwise_json(result)
    assert tree["schema_version"] == PAIRWISE_EXPERIMENT_SCHEMA_VERSION == 1
    section = tree["pairwise_result"]
    assert section["result_id"] == str(result.result_id)
    assert section["source_report_id"] == str(result.source_report_id)
    assert len(section["records"]) == 3
    assert [item["metric"] for item in section["records"][0]["differences"]] == [
        metric.value for metric in result.policy.metrics
    ]
    assert "report" not in tree
    assert "variants" not in section


def test_json_and_csv_match_exact_fixtures_and_hashes(result) -> None:
    outputs = {
        "historical-experiment-pairwise-v1-compact.json": serialize_pairwise_json(
            result
        ),
        "historical-experiment-pairwise-v1-pretty.json": serialize_pairwise_json(
            result, pretty=True
        ),
        "historical-experiment-pairwise-v1.csv": serialize_pairwise_csv(result),
    }
    expected_hashes = {
        "historical-experiment-pairwise-v1-compact.json": (
            "7fad19ad71d7375b8dbde5b7f3207375a47bf404b35a7681100e3764204dbcb2"
        ),
        "historical-experiment-pairwise-v1-pretty.json": (
            "9150071cc298f22ecc4e817cfb2743144ba00acfdab28ea6f817ee464ef51c35"
        ),
        "historical-experiment-pairwise-v1.csv": (
            "0a811617e5e7b2825aa6dd179383ce4a0a7d6ea13e3bba6b93ffad50095f16f0"
        ),
    }
    for name, content in outputs.items():
        expected = (FIXTURES / name).read_text(encoding="utf-8")
        assert content == expected
        assert content.endswith("\n") and not content.endswith("\n\n")
        assert sha256(content.encode()).hexdigest() == expected_hashes[name]


def test_csv_is_long_format_in_record_then_metric_order(result) -> None:
    rows = list(csv.reader(io.StringIO(serialize_pairwise_csv(result))))
    assert tuple(rows[0]) == PAIRWISE_CSV_HEADER
    assert len(PAIRWISE_CSV_HEADER) == len(set(PAIRWISE_CSV_HEADER)) == 16
    assert len(rows) == 1 + len(result.records) * len(result.policy.metrics)
    assert [(row[7], row[12]) for row in rows[1:]] == [
        (str(record.ordinal), metric.value)
        for record in result.records
        for metric in result.policy.metrics
    ]
    assert json.loads(rows[1][6]) == [
        {"key": "example", "value": "neutral-pairwise-comparison"}
    ]


def test_serialization_is_independent_of_decimal_context(result) -> None:
    expected = (
        serialize_pairwise_json(result),
        serialize_pairwise_csv(result),
    )
    with localcontext(Context(prec=2)):
        assert (
            serialize_pairwise_json(result),
            serialize_pairwise_csv(result),
        ) == expected


def test_exact_result_and_pretty_types_are_required(result) -> None:
    with pytest.raises(HistoricalExperimentPairwiseOutputError):
        build_pairwise_json(object())  # type: ignore[arg-type]
    with pytest.raises(HistoricalExperimentPairwiseOutputError):
        serialize_pairwise_json(result, pretty=1)  # type: ignore[arg-type]
    assert isinstance(
        build_pairwise_json(result)["pairwise_result"]["records"][0]["ordinal"],
        int,
    )
    assert isinstance(
        build_pairwise_json(result)["pairwise_result"]["records"][0]["differences"][0][
            "left_value"
        ],
        str,
    )
