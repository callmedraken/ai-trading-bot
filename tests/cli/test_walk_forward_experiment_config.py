import json
from copy import deepcopy
from pathlib import Path

import pytest

from trading_bot.cli.exceptions import ConfigValidationError
from trading_bot.cli.walk_forward_experiment_config import (
    parse_walk_forward_experiment_config,
)

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_EXAMPLE = ROOT / "examples" / "historical-experiment.example.json"


def raw_walk_forward() -> dict:
    historical = json.loads(HISTORICAL_EXAMPLE.read_text(encoding="utf-8"))
    first = deepcopy(historical["variant_grid"]["base_variant"])
    second = deepcopy(first)
    first["variant_id"] = "00000000-0000-0000-0000-000000000501"
    first["name"] = "Candidate One"
    second["variant_id"] = "00000000-0000-0000-0000-000000000502"
    second["name"] = "Candidate Two"
    second["optimization"]["risk_aversion"] = "2"
    return {
        "schema_version": 1,
        "request_id": "00000000-0000-0000-0000-000000000500",
        "historical_data": historical["historical_data"],
        "initial_state": historical["initial_state"],
        "variants": [first, second],
        "folds": [
            {
                "fold_id": "00000000-0000-0000-0000-000000000510",
                "training_start": "2026-01-05T20:00:00+00:00",
                "training_end": "2026-01-08T20:00:00+00:00",
                "test_start": "2026-01-08T20:00:00+00:00",
                "test_end": "2026-01-11T20:00:00+00:00",
                "training_rebalance_timestamps": ["2026-01-07T20:00:00+00:00"],
                "test_rebalance_timestamps": ["2026-01-10T20:00:00+00:00"],
                "metadata": [],
            }
        ],
        "selection_policy": {
            "policy_id": "00000000-0000-0000-0000-000000000520",
            "ranking_policy": {
                "policy_id": "00000000-0000-0000-0000-000000000521",
                "criteria": [{"metric": "FINAL_EQUITY", "direction": "DESCENDING"}],
                "tie_breaker": "CALLER_ORDER",
                "metadata": [],
            },
            "metadata": [],
        },
        "metadata": [],
    }


def test_schema_one_parses_explicit_folds_variants_and_policy() -> None:
    loaded = parse_walk_forward_experiment_config(raw_walk_forward(), ROOT / "examples")
    assert loaded.schema_version == 1
    assert len(loaded.variants) == 2
    assert len(loaded.folds) == 1
    assert loaded.selection_policy.ranking_policy.criteria[0].metric.value == (
        "FINAL_EQUITY"
    )


@pytest.mark.parametrize("version", (2, True, "1"))
def test_schema_version_is_strict(version) -> None:
    raw = raw_walk_forward()
    raw["schema_version"] = version
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(raw, ROOT / "examples")


def test_unknown_root_key_and_grid_are_rejected() -> None:
    raw = raw_walk_forward()
    raw["variant_grid"] = None
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(raw, ROOT / "examples")


def test_invalid_fold_and_reserved_metadata_are_rejected() -> None:
    raw = raw_walk_forward()
    raw["folds"][0]["test_start"] = "2026-01-09T20:00:00+00:00"
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(raw, ROOT / "examples")
    raw = raw_walk_forward()
    raw["metadata"] = [{"key": "historical_experiment_walk_forward_bad", "value": "x"}]
    with pytest.raises(ConfigValidationError):
        parse_walk_forward_experiment_config(raw, ROOT / "examples")
