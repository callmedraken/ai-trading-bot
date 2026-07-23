import csv
import io
import json
from dataclasses import fields, replace
from hashlib import sha256
from pathlib import Path

import pytest
from tests.experiments.test_historical import _Factory, _request, _variant

from trading_bot.cli import historical_experiment
from trading_bot.cli.exceptions import HistoricalExperimentReportOutputError
from trading_bot.cli.historical_experiment_report_serialization import (
    _METRIC_FIELDS,
    COMPACT_EXPERIMENT_REPORT_CSV_HEADER,
    COMPACT_EXPERIMENT_REPORT_SCHEMA_VERSION,
    build_compact_report_json,
    serialize_compact_report_csv,
    serialize_compact_report_json,
)
from trading_bot.experiments import (
    HistoricalExperimentMetrics,
    HistoricalExperimentReportBuilder,
    HistoricalExperimentRunner,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment.example.json"
FIXTURES = ROOT / "tests" / "fixtures" / "cli"


@pytest.fixture(scope="module")
def report():
    run = historical_experiment.run_cli(
        EXAMPLE,
        collect_audit_records=False,
        build_compact_report=True,
    )
    assert run.compact_report is not None
    return run.compact_report


def test_metric_mapping_and_csv_header_are_explicit_complete_and_stable() -> None:
    model_fields = tuple(item.name for item in fields(HistoricalExperimentMetrics))
    assert len(_METRIC_FIELDS) == 26
    assert len(set(_METRIC_FIELDS)) == 26
    assert set(_METRIC_FIELDS) == set(model_fields)
    assert len(COMPACT_EXPERIMENT_REPORT_CSV_HEADER) == 81
    assert len(set(COMPACT_EXPERIMENT_REPORT_CSV_HEADER)) == 81
    assert COMPACT_EXPERIMENT_REPORT_CSV_HEADER[:9] == (
        "report_id",
        "experiment_request_id",
        "experiment_result_id",
        "historical_fingerprint",
        "schedule_fingerprint",
        "initial_state_fingerprint",
        "variant_source",
        "grid_specification_id",
        "grid_result_id",
    )
    assert COMPACT_EXPERIMENT_REPORT_CSV_HEADER[-26:] == _METRIC_FIELDS


def test_json_schema_contains_compact_identity_provenance_and_metrics(report) -> None:
    tree = build_compact_report_json(report)
    assert tree["schema_version"] == COMPACT_EXPERIMENT_REPORT_SCHEMA_VERSION == 1
    section = tree["report"]
    assert section["report_id"] == str(report.report_id)
    assert section["experiment_result_id"] == str(report.experiment_result_id)
    assert section["variant_source"] == "GRID"
    assert section["grid_specification_id"] == str(report.grid_specification_id)
    assert section["grid_result_id"] == str(report.grid_result_id)
    assert section["metadata"] == []
    assert section["ranking"]["comparison_result_id"] == str(
        report.ranking.comparison_result_id
    )
    assert [item["caller_ordinal"] for item in section["variants"]] == [0, 1, 2, 3]
    first = section["variants"][0]
    assert first["rolling_result_id"] == str(report.variants[0].rolling_result_id)
    assert len(first["metrics"]) == 26
    assert [item["metric"] for item in first["comparison_values"]] == [
        item.metric.value for item in report.ranking.criteria
    ]
    assert "historical_data" not in section
    for row in section["variants"]:
        assert set(row) == {
            "caller_ordinal",
            "experiment_run_id",
            "rolling_result_id",
            "variant_id",
            "variant_name",
            "grid_ordinal",
            "grid_assignments",
            "rank",
            "comparison_values",
            "metrics",
        }


def test_json_is_deterministic_and_has_one_trailing_newline(report) -> None:
    for pretty in (False, True):
        first = serialize_compact_report_json(report, pretty=pretty)
        second = serialize_compact_report_json(report, pretty=pretty)
        assert first == second
        assert first.endswith("\n")
        assert not first.endswith("\n\n")
    with pytest.raises(HistoricalExperimentReportOutputError):
        serialize_compact_report_json(report, pretty=1)  # type: ignore[arg-type]
    with pytest.raises(HistoricalExperimentReportOutputError):
        build_compact_report_json(object())  # type: ignore[arg-type]


def test_csv_has_exact_header_caller_order_and_typed_values(report) -> None:
    rendered = serialize_compact_report_csv(report)
    rows = list(csv.DictReader(io.StringIO(rendered)))
    assert tuple(rows[0]) == COMPACT_EXPERIMENT_REPORT_CSV_HEADER
    assert len(rows) == 4
    assert [row["caller_ordinal"] for row in rows] == ["0", "1", "2", "3"]
    assert [row["grid_window_observation_count"] for row in rows] == [
        "3",
        "3",
        "4",
        "4",
    ]
    assert [row["grid_risk_aversion"] for row in rows] == ["1", "2", "1", "2"]
    assert rows[0]["grid_trading_enabled"] == ""
    assert rows[0]["rank_value_simulation_return"] != ""
    assert rows[0]["rank_value_total_orders"] == ""
    assert rows[0]["total_orders"].isdigit()
    assert json.loads(rows[0]["grid_assignments"])[0] == {
        "parameter": "WINDOW_OBSERVATION_COUNT",
        "value": 3,
    }
    assert json.loads(rows[0]["ranking_criteria"])[0]["metric"] == ("SIMULATION_RETURN")
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")


@pytest.mark.parametrize(
    ("pretty", "fixture_name", "digest"),
    (
        (
            False,
            "historical-experiment-compact-report-v1-compact.json",
            "9e9db4d8285db39f49762e45bda05e5eb1bb5676c5a784fc9dd28be51c1be1ef",
        ),
        (
            True,
            "historical-experiment-compact-report-v1-pretty.json",
            "68fcb877fdfc6109adba7ccd066e9c784f306d1edd449592249f0d795d4c638f",
        ),
    ),
)
def test_json_matches_exact_fixture(
    report, pretty: bool, fixture_name: str, digest: str
) -> None:
    expected = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    actual = serialize_compact_report_json(report, pretty=pretty)
    assert actual == expected
    assert sha256(expected.encode("utf-8")).hexdigest() == digest


def test_csv_matches_exact_fixture(report) -> None:
    expected = (FIXTURES / "historical-experiment-compact-report-v1.csv").read_text(
        encoding="utf-8"
    )
    actual = serialize_compact_report_csv(report)
    assert actual == expected
    assert sha256(expected.encode("utf-8")).hexdigest() == (
        "2898a17d2fd64b943cfb629fe9d1fa34dc123655fcdd17e46f2ebbbad909ba01"
    )


def test_csv_standard_dialect_round_trips_special_variant_text() -> None:
    name = 'Comma, "Quote"\nUnicode Ω'
    variant = replace(_variant(10), name=name)
    result = HistoricalExperimentRunner(_Factory()).run(_request(variants=(variant,)))
    report = HistoricalExperimentReportBuilder().build(result)
    rows = list(csv.DictReader(io.StringIO(serialize_compact_report_csv(report))))
    assert rows[0]["variant_name"] == name
