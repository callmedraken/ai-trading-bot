import csv
import io
import json
from decimal import Context, Decimal, localcontext

import pytest
from tests.experiments.test_walk_forward_analytics import _source
from tests.experiments.test_walk_forward_stability import (
    OPERATION,
    C,
    M,
    _metric,
    _policy,
)

from trading_bot.cli.exceptions import WalkForwardExperimentOutputError
from trading_bot.cli.walk_forward_stability_serialization import (
    WALK_FORWARD_STABILITY_CSV_HEADER,
    serialize_walk_forward_stability_csv,
    serialize_walk_forward_stability_json,
)
from trading_bot.experiments import HistoricalExperimentWalkForwardStabilityAnalyzer


@pytest.fixture
def stability_result():
    return HistoricalExperimentWalkForwardStabilityAnalyzer().analyze(
        _source(),
        _policy(
            _metric(
                M.SIMULATION_RETURN,
                (
                    OPERATION.ADJACENT_ABSOLUTE_CHANGE,
                    OPERATION.RANGE,
                    OPERATION.MEDIAN_ABSOLUTE_DEVIATION,
                    OPERATION.SIGN_CHANGE_COUNT,
                ),
                C.EQUAL_TEST_DURATION,
            )
        ),
    )


def test_json_is_an_exact_ordered_projection(stability_result) -> None:
    compact = serialize_walk_forward_stability_json(stability_result)
    pretty = serialize_walk_forward_stability_json(stability_result, pretty=True)
    tree = json.loads(compact)["walk_forward_stability_result"]
    selection = tree["selection_stability"]
    assert compact.endswith("\n") and not compact.endswith("\n\n")
    assert pretty.endswith("\n") and json.loads(pretty) == json.loads(compact)
    assert tree["result_id"] == str(stability_result.result_id)
    assert selection["transitions"][0]["changed"] is False
    assert (
        selection["transitions"][0]["from_variant_id"]
        == selection["transitions"][0]["to_variant_id"]
    )
    summary = tree["metric_stability"][0]
    assert type(summary["observations"][0]["value"]) is str
    assert summary["observations"][0]["value_scalar_type"] == "DECIMAL"
    assert summary["median"] is not None
    assert not any(
        isinstance(value, float)
        for value in (
            summary["value_range"],
            summary["median"],
            summary["median_absolute_deviation"],
        )
    )


def test_csv_has_fixed_header_and_explicit_record_order(stability_result) -> None:
    rendered = serialize_walk_forward_stability_csv(stability_result)
    rows = list(csv.DictReader(io.StringIO(rendered)))
    assert tuple(rows[0]) == WALK_FORWARD_STABILITY_CSV_HEADER
    assert [row["record_type"] for row in rows] == [
        "SELECTION_OBSERVATION",
        "SELECTION_OBSERVATION",
        "SELECTION_RUN",
        "SELECTION_TRANSITION",
        "TRANSITION_FREQUENCY",
        "VARIANT_FREQUENCY",
        "METRIC_OBSERVATION",
        "METRIC_OBSERVATION",
        "ADJACENT_METRIC_CHANGE",
        "METRIC_SUMMARY",
    ]
    transition = rows[3]
    assert transition["from_variant_id"] == transition["to_variant_id"]
    assert transition["transition_changed"] == "false"
    assert rows[-1]["median_absolute_deviation"] != ""
    assert Decimal(rows[-1]["value_range"]).is_finite()


def test_serialization_is_decimal_context_independent(stability_result) -> None:
    expected_json = serialize_walk_forward_stability_json(stability_result)
    expected_csv = serialize_walk_forward_stability_csv(stability_result)
    with localcontext(Context(prec=1)):
        assert serialize_walk_forward_stability_json(stability_result) == expected_json
        assert serialize_walk_forward_stability_csv(stability_result) == expected_csv


def test_serializers_reject_nonexact_results_and_bool_scalars() -> None:
    with pytest.raises(WalkForwardExperimentOutputError):
        serialize_walk_forward_stability_json(object())  # type: ignore[arg-type]
    with pytest.raises(WalkForwardExperimentOutputError):
        serialize_walk_forward_stability_csv(object())  # type: ignore[arg-type]
    from trading_bot.cli.walk_forward_stability_serialization import _json_scalar

    with pytest.raises(WalkForwardExperimentOutputError):
        _json_scalar(True)
