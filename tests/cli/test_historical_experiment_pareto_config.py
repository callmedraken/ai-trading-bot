import json
from pathlib import Path

import pytest

from trading_bot.cli.exceptions import ConfigValidationError
from trading_bot.cli.historical_experiment_pareto_config import (
    load_historical_experiment_pareto_policy,
    parse_historical_experiment_pareto_policy,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment-pareto-policy.example.json"


def _raw() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_loads_ordered_policy() -> None:
    loaded = load_historical_experiment_pareto_policy(EXAMPLE)
    assert loaded.schema_version == 1
    assert [item.metric.value for item in loaded.policy.objectives] == [
        "SIMULATION_RETURN",
        "MAXIMUM_DRAWDOWN_PERCENTAGE",
    ]


@pytest.mark.parametrize(
    ("mutation", "path"),
    (
        (lambda raw: raw.update(schema_version=2), "$.schema_version"),
        (lambda raw: raw.update(extra=True), "$.extra"),
        (
            lambda raw: raw["policy"]["objectives"][0].update(metric="BAD"),
            "$.policy.objectives[0].metric",
        ),
        (
            lambda raw: raw["policy"]["objectives"][0].update(direction="BAD"),
            "$.policy.objectives[0].direction",
        ),
        (lambda raw: raw["policy"].update(objectives=[]), "$.policy.objectives"),
    ),
)
def test_strict_errors_retain_paths(mutation, path: str) -> None:  # type: ignore[no-untyped-def]
    raw = _raw()
    mutation(raw)
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_pareto_policy(raw)
    assert caught.value.field_path == path


def test_duplicate_objectives_are_domain_validation() -> None:
    raw = _raw()
    raw["policy"]["objectives"].append(raw["policy"]["objectives"][0])
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_pareto_policy(raw)
    assert caught.value.field_path == "$.policy.objectives"
