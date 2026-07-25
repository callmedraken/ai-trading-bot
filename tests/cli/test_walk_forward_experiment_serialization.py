import csv
import hashlib
import json
from decimal import getcontext
from io import StringIO
from pathlib import Path

import pytest
from tests.experiments.test_historical import _Factory
from tests.experiments.test_walk_forward import _request

from trading_bot.cli.exceptions import WalkForwardExperimentOutputError
from trading_bot.cli.walk_forward_experiment_serialization import (
    WALK_FORWARD_CSV_HEADER,
    serialize_walk_forward_csv,
    serialize_walk_forward_json,
)
from trading_bot.experiments import HistoricalExperimentWalkForwardRunner

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "cli"
    / "walk-forward-v1-fixtures.json"
)


@pytest.fixture(scope="module")
def result():
    return HistoricalExperimentWalkForwardRunner(_Factory()).run(_request())


def test_json_retains_complete_independent_fold_provenance(result) -> None:
    rendered = serialize_walk_forward_json(result)
    tree = json.loads(rendered)
    root = tree["walk_forward_result"]
    assert tree["schema_version"] == 1
    assert root["result_id"] == str(result.result_id)
    assert len(root["folds"]) == 2
    for source, serialized in zip(result.folds, root["folds"], strict=True):
        assert serialized["training"]["report"]["ranking"] is not None
        assert serialized["test"]["report"]["ranking"] is None
        assert len(serialized["test"]["report"]["variants"]) == 1
        assert (
            serialized["selection"]["selected_variant_id"]
            == serialized["test"]["report"]["variants"][0]["variant_id"]
        )
        assert "aggregate_metrics" not in serialized
        assert serialized["test"]["run_id"] == str(source.test_run_id)
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")


def test_csv_is_fold_ordered_training_then_test_and_has_no_aggregate(result) -> None:
    rendered = serialize_walk_forward_csv(result)
    rows = list(csv.DictReader(StringIO(rendered)))
    assert tuple(rows[0]) == WALK_FORWARD_CSV_HEADER
    assert [row["row_kind"] for row in rows] == [
        "TRAINING_VARIANT",
        "TRAINING_VARIANT",
        "TEST_VARIANT",
        "TRAINING_VARIANT",
        "TRAINING_VARIANT",
        "TEST_VARIANT",
    ]
    assert all(row["rank"] for row in rows if row["row_kind"] == "TRAINING_VARIANT")
    assert all(not row["rank"] for row in rows if row["row_kind"] == "TEST_VARIANT")
    assert not any(
        "aggregate_out_of_sample" in name for name in WALK_FORWARD_CSV_HEADER
    )
    assert rendered.endswith("\n")


def test_json_and_csv_are_decimal_context_independent(result) -> None:
    baseline = (
        serialize_walk_forward_json(result),
        serialize_walk_forward_csv(result),
    )
    context = getcontext()
    prior = (context.prec, context.Emax, context.Emin)
    try:
        context.prec = 2
        context.Emax = 9
        context.Emin = -9
        assert (
            serialize_walk_forward_json(result),
            serialize_walk_forward_csv(result),
        ) == baseline
    finally:
        context.prec, context.Emax, context.Emin = prior


def test_serializers_require_exact_immutable_result() -> None:
    with pytest.raises(WalkForwardExperimentOutputError):
        serialize_walk_forward_json(object())  # type: ignore[arg-type]
    with pytest.raises(WalkForwardExperimentOutputError):
        serialize_walk_forward_csv(object())  # type: ignore[arg-type]


def test_version_one_fixture_bytes_and_digests(result) -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    outputs = {
        "compact_json": serialize_walk_forward_json(result),
        "pretty_json": serialize_walk_forward_json(result, pretty=True),
        "csv": serialize_walk_forward_csv(result),
    }
    for name, rendered in outputs.items():
        encoded = rendered.encode("utf-8")
        assert len(encoded) == expected[name]["bytes"]
        assert hashlib.sha256(encoded).hexdigest() == expected[name]["sha256"]
