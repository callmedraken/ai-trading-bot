from copy import deepcopy
from pathlib import Path

import pytest
from tests.cli.test_walk_forward_aggregate_config import raw_schema_two

from trading_bot.cli.exceptions import ConfigValidationError
from trading_bot.cli.walk_forward_experiment_config import (
    parse_walk_forward_experiment_config,
)

ROOT = Path(__file__).resolve().parents[2]


def raw_schema_three(*, aggregate: bool = True) -> dict:
    raw = deepcopy(raw_schema_two())
    raw["schema_version"] = 3
    if not aggregate:
        raw["aggregate_policy"] = None
    raw["stability_policy"] = {
        "policy_id": "00000000-0000-0000-0000-000000000540",
        "metrics": [
            {
                "metric": "SIMULATION_RETURN",
                "operations": [
                    "SIGN_CHANGE_COUNT",
                    "MEDIAN_ABSOLUTE_DEVIATION",
                    "RANGE",
                    "ADJACENT_ABSOLUTE_CHANGE",
                ],
                "comparability_rule": "EQUAL_TEST_DURATION",
            },
            {
                "metric": "TOTAL_COMMISSIONS",
                "operations": [],
                "comparability_rule": "NONE",
            },
        ],
        "metadata": [],
    }
    return raw


def test_schema_three_parses_required_policies_and_nullable_aggregate() -> None:
    loaded = parse_walk_forward_experiment_config(raw_schema_three(), ROOT / "examples")
    assert loaded.schema_version == 3
    assert loaded.aggregate_policy is not None
    assert loaded.stability_policy is not None
    assert [item.value for item in loaded.stability_policy.metrics[0].operations] == [
        "ADJACENT_ABSOLUTE_CHANGE",
        "RANGE",
        "MEDIAN_ABSOLUTE_DEVIATION",
        "SIGN_CHANGE_COUNT",
    ]
    without_aggregate = parse_walk_forward_experiment_config(
        raw_schema_three(aggregate=False), ROOT / "examples"
    )
    assert without_aggregate.aggregate_policy is None
    assert without_aggregate.stability_policy is not None


def test_schemas_one_and_two_remain_strict() -> None:
    schema_two = raw_schema_two()
    schema_two["stability_policy"] = raw_schema_three()["stability_policy"]
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(schema_two, ROOT / "examples")
    schema_three = raw_schema_three()
    del schema_three["stability_policy"]
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(schema_three, ROOT / "examples")
    schema_three = raw_schema_three()
    del schema_three["aggregate_policy"]
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(schema_three, ROOT / "examples")


@pytest.mark.parametrize(
    "mutation",
    (
        lambda raw: raw["stability_policy"]["metrics"][0].update(extra=None),
        lambda raw: raw["stability_policy"]["metrics"][0].update(
            comparability_rule="NONE"
        ),
        lambda raw: raw["stability_policy"]["metrics"][1].update(operations=["RANGE"]),
        lambda raw: raw["stability_policy"]["metrics"].append(
            deepcopy(raw["stability_policy"]["metrics"][0])
        ),
    ),
)
def test_schema_three_delegates_strict_policy_validation(mutation) -> None:
    raw = raw_schema_three()
    mutation(raw)
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(raw, ROOT / "examples")
