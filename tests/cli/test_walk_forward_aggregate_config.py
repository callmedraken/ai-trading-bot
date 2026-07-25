from copy import deepcopy
from pathlib import Path

import pytest
from tests.cli.test_walk_forward_experiment_config import raw_walk_forward

from trading_bot.cli.exceptions import ConfigValidationError
from trading_bot.cli.walk_forward_experiment_config import (
    parse_walk_forward_experiment_config,
)

ROOT = Path(__file__).resolve().parents[2]


def raw_schema_two() -> dict:
    raw = deepcopy(raw_walk_forward())
    raw["schema_version"] = 2
    raw["aggregate_policy"] = {
        "policy_id": "00000000-0000-0000-0000-000000000530",
        "metrics": [
            {
                "metric": "SIMULATION_RETURN",
                "operations": [
                    "SIGN_COUNTS",
                    "EQUAL_FOLD_ARITHMETIC_MEAN",
                    "MINIMUM",
                ],
            },
            {"metric": "TOTAL_COMMISSIONS", "operations": []},
        ],
        "metadata": [],
    }
    return raw


def test_schema_two_requires_and_parses_explicit_aggregate_policy() -> None:
    loaded = parse_walk_forward_experiment_config(raw_schema_two(), ROOT / "examples")
    assert loaded.schema_version == 2
    assert loaded.aggregate_policy is not None
    assert [item.value for item in loaded.aggregate_policy.metrics[0].operations] == [
        "MINIMUM",
        "EQUAL_FOLD_ARITHMETIC_MEAN",
        "SIGN_COUNTS",
    ]
    assert loaded.aggregate_policy.metrics[1].operations == ()


def test_schema_one_shape_is_unchanged_and_schema_two_is_strict() -> None:
    schema_one = raw_walk_forward()
    schema_one["aggregate_policy"] = raw_schema_two()["aggregate_policy"]
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(schema_one, ROOT / "examples")
    schema_two = raw_schema_two()
    del schema_two["aggregate_policy"]
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(schema_two, ROOT / "examples")


@pytest.mark.parametrize(
    "metric,operations",
    [
        ("TOTAL_COMMISSIONS", ["MINIMUM"]),
        ("SIMULATION_RETURN", ["MINIMUM", "MINIMUM"]),
    ],
)
def test_invalid_aggregate_operations_fail_configuration(
    metric: str, operations: list[str]
) -> None:
    raw = raw_schema_two()
    raw["aggregate_policy"]["metrics"] = [{"metric": metric, "operations": operations}]
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(raw, ROOT / "examples")
