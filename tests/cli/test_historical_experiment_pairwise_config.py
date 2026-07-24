import json
from copy import deepcopy
from pathlib import Path

import pytest

from trading_bot.cli.exceptions import (
    ConfigJsonError,
    ConfigReadError,
    ConfigValidationError,
)
from trading_bot.cli.historical_experiment_pairwise_config import (
    load_historical_experiment_pairwise_policy,
    parse_historical_experiment_pairwise_policy,
)
from trading_bot.experiments import (
    HistoricalExperimentPairwiseOrientation,
    HistoricalExperimentPairwisePairing,
    HistoricalExperimentRankingMetric,
)
from trading_bot.portfolio import MetadataEntry

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment-pairwise-policy.example.json"


def _raw() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_loads_exact_ordered_policy() -> None:
    loaded = load_historical_experiment_pairwise_policy(EXAMPLE)
    assert loaded.schema_version == 1
    assert loaded.policy.metrics == (
        HistoricalExperimentRankingMetric.SIMULATION_RETURN,
        HistoricalExperimentRankingMetric.MAXIMUM_DRAWDOWN_PERCENTAGE,
    )
    assert (
        loaded.policy.pairing is HistoricalExperimentPairwisePairing.BASELINE_VERSUS_ALL
    )
    assert (
        loaded.policy.orientation
        is HistoricalExperimentPairwiseOrientation.CALLER_ORDER
    )
    assert str(loaded.policy.baseline_variant_id) == (
        "2760ea8a-84b9-5619-a2df-4755e460cb20"
    )
    assert loaded.policy.metadata == (
        MetadataEntry("example", "neutral-pairwise-comparison"),
    )


def test_all_pairs_policy_is_supported() -> None:
    raw = _raw()
    raw["policy"]["pairing"] = "ALL_UNORDERED_PAIRS"
    raw["policy"]["orientation"] = "VARIANT_ID"
    raw["policy"]["baseline_variant_id"] = None
    loaded = parse_historical_experiment_pairwise_policy(raw)
    assert loaded.policy.baseline_variant_id is None


@pytest.mark.parametrize(
    ("mutation", "path"),
    (
        (lambda raw: raw.update(schema_version=2), "$.schema_version"),
        (lambda raw: raw.update(extra=True), "$.extra"),
        (lambda raw: raw["policy"].pop("orientation"), "$.policy.orientation"),
        (
            lambda raw: raw["policy"].update(policy_id="NOT-A-UUID"),
            "$.policy.policy_id",
        ),
        (
            lambda raw: raw["policy"]["metrics"].__setitem__(1, "UNKNOWN"),
            "$.policy.metrics[1]",
        ),
        (
            lambda raw: raw["policy"].update(orientation="UNKNOWN"),
            "$.policy.orientation",
        ),
        (
            lambda raw: raw["policy"].update(baseline_variant_id="BAD"),
            "$.policy.baseline_variant_id",
        ),
        (
            lambda raw: raw["policy"].update(metadata="bad"),
            "$.policy.metadata",
        ),
    ),
)
def test_structure_errors_retain_precise_paths(mutation, path: str) -> None:  # type: ignore[no-untyped-def]
    raw = _raw()
    mutation(raw)
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_pairwise_policy(raw)
    assert caught.value.field_path == path


@pytest.mark.parametrize(
    "mutation",
    (
        lambda raw: raw["policy"].update(metrics=[]),
        lambda raw: raw["policy"].update(
            metrics=["SIMULATION_RETURN", "SIMULATION_RETURN"]
        ),
        lambda raw: raw["policy"].update(baseline_variant_id=None),
        lambda raw: raw["policy"].update(pairing="ALL_UNORDERED_PAIRS"),
        lambda raw: raw["policy"].update(orientation="VARIANT_ID"),
    ),
)
def test_domain_policy_rules_are_mapped_to_validation(mutation) -> None:  # type: ignore[no-untyped-def]
    raw = deepcopy(_raw())
    mutation(raw)
    with pytest.raises(ConfigValidationError):
        parse_historical_experiment_pairwise_policy(raw)


def test_read_utf8_and_json_failures_are_distinct(tmp_path: Path) -> None:
    with pytest.raises(ConfigReadError):
        load_historical_experiment_pairwise_policy(tmp_path / "missing.json")
    invalid_utf8 = tmp_path / "utf8.json"
    invalid_utf8.write_bytes(b"\xff")
    with pytest.raises(ConfigReadError):
        load_historical_experiment_pairwise_policy(invalid_utf8)
    malformed = tmp_path / "json.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ConfigJsonError):
        load_historical_experiment_pairwise_policy(malformed)
