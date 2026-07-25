import csv
import io
import json
from decimal import Decimal

import pytest
from tests.experiments.test_walk_forward_analytics import _metric, _policy, _source

from trading_bot.cli.exceptions import WalkForwardExperimentOutputError
from trading_bot.cli.walk_forward_aggregate_serialization import (
    WALK_FORWARD_AGGREGATE_CSV_HEADER,
    serialize_walk_forward_aggregate_csv,
    serialize_walk_forward_aggregate_json,
)
from trading_bot.experiments import (
    HistoricalExperimentWalkForwardAggregateAnalyzer,
    HistoricalExperimentWalkForwardAggregateMetric,
    HistoricalExperimentWalkForwardAggregateOperation,
)


@pytest.fixture
def aggregate_result():
    operation = HistoricalExperimentWalkForwardAggregateOperation
    return HistoricalExperimentWalkForwardAggregateAnalyzer().analyze(
        _source(),
        _policy(
            _metric(
                HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_RETURN,
                operation.MINIMUM,
                operation.MAXIMUM,
                operation.MEDIAN,
                operation.EQUAL_FOLD_ARITHMETIC_MEAN,
                operation.SIGN_COUNTS,
            ),
            _metric(HistoricalExperimentWalkForwardAggregateMetric.TOTAL_COMMISSIONS),
        ),
    )


def test_json_is_exact_projection_with_rational_terms(aggregate_result) -> None:
    rendered = serialize_walk_forward_aggregate_json(aggregate_result)
    tree = json.loads(rendered)["walk_forward_aggregate_result"]
    assert rendered.endswith("\n") and not rendered.endswith("\n\n")
    assert tree["result_id"] == str(aggregate_result.result_id)
    mean = tree["metric_summaries"][0]["arithmetic_mean"]
    source_mean = aggregate_result.metric_summaries[0].arithmetic_mean
    assert mean == {
        "numerator": source_mean.numerator,
        "denominator": source_mean.denominator,
    }
    assert tree["metric_summaries"][1]["minimum"] is None
    assert all(
        not isinstance(item["value"], float)
        for item in tree["metric_summaries"][0]["observations"]
    )


def test_csv_is_fold_then_policy_ordered_and_preserves_scalar_types(
    aggregate_result,
) -> None:
    rendered = serialize_walk_forward_aggregate_csv(aggregate_result)
    rows = list(csv.DictReader(io.StringIO(rendered)))
    assert tuple(rows[0]) == WALK_FORWARD_AGGREGATE_CSV_HEADER
    assert [(row["fold_ordinal"], row["metric_ordinal"]) for row in rows] == [
        ("0", "0"),
        ("0", "1"),
        ("1", "0"),
        ("1", "1"),
    ]
    assert rows[0]["observation_scalar_type"] == "DECIMAL"
    assert rows[1]["minimum"] == ""
    assert rows[0]["arithmetic_mean_denominator"]
    assert Decimal(rows[0]["observation_value"]).is_finite()


def test_serializers_require_exact_immutable_aggregate_result() -> None:
    with pytest.raises(WalkForwardExperimentOutputError):
        serialize_walk_forward_aggregate_json(object())  # type: ignore[arg-type]
    with pytest.raises(WalkForwardExperimentOutputError):
        serialize_walk_forward_aggregate_csv(object())  # type: ignore[arg-type]
