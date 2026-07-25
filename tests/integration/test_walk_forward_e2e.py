import json
import subprocess
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "tests" / "fixtures" / "cli" / "walk-forward-schema-2-e2e.json"
SCRIPT = ROOT / "scripts" / "run_walk_forward_experiment.py"
ARTIFACT_NAMES = ("walk.json", "walk.csv", "aggregate.json", "aggregate.csv")


def _run_cli(
    destination: Path,
    *,
    aggregates: bool = True,
    config: Path = CONFIG,
    stability: bool = False,
) -> None:
    destination.mkdir()
    arguments = [
        sys.executable,
        str(SCRIPT),
        "--config",
        str(config),
        "--json",
        str(destination / "walk.json"),
        "--csv",
        str(destination / "walk.csv"),
        "--quiet",
    ]
    if aggregates:
        arguments.extend(
            [
                "--aggregate-json",
                str(destination / "aggregate.json"),
                "--aggregate-csv",
                str(destination / "aggregate.csv"),
            ]
        )
    if stability:
        arguments.extend(
            [
                "--stability-json",
                str(destination / "stability.json"),
                "--stability-csv",
                str(destination / "stability.csv"),
            ]
        )
    subprocess.run(arguments, cwd=ROOT, check=True)


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _keys(child)}
    return set()


def test_schema_two_walk_forward_end_to_end_reconciles_exactly(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    without_aggregates = tmp_path / "without-aggregates"

    _run_cli(first)
    _run_cli(second)
    _run_cli(without_aggregates, aggregates=False)

    assert {item.name for item in first.iterdir()} == set(ARTIFACT_NAMES)
    for name in ARTIFACT_NAMES:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    for name in ("walk.json", "walk.csv"):
        assert (first / name).read_bytes() == (without_aggregates / name).read_bytes()

    walk = json.loads((first / "walk.json").read_bytes())["walk_forward_result"]
    aggregate = json.loads((first / "aggregate.json").read_bytes())[
        "walk_forward_aggregate_result"
    ]
    assert walk["result_id"] == aggregate["source_walk_forward_result_id"]
    assert (
        aggregate["result_id"]
        == json.loads((second / "aggregate.json").read_bytes())[
            "walk_forward_aggregate_result"
        ]["result_id"]
    )

    metric_names = {
        "SIMULATION_RETURN": "simulation_return",
        "TOTAL_ORDERS": "total_orders",
    }
    test_values = {
        metric: [
            fold["test"]["report"]["variants"][0]["metrics"][serialized_name]
            for fold in walk["folds"]
        ]
        for metric, serialized_name in metric_names.items()
    }
    for summary in aggregate["metric_summaries"]:
        observations = [item["value"] for item in summary["observations"]]
        assert observations == test_values[summary["metric"]]
        exact_mean = sum((Fraction(str(value)) for value in observations), Fraction())
        exact_mean /= len(observations)
        assert summary["arithmetic_mean"] == {
            "numerator": exact_mean.numerator,
            "denominator": exact_mean.denominator,
        }

    selected = [fold["selection"]["selected_variant_id"] for fold in walk["folds"]]
    expected_frequencies = Counter(selected)
    assert {
        item["variant_id"]: (
            item["selected_fold_count"],
            item["rank_one_selected_fold_count"],
        )
        for item in aggregate["variant_frequencies"]
    } == {
        variant_id: (count, count) for variant_id, count in expected_frequencies.items()
    }

    prohibited = {
        "aggregate_total",
        "annualization",
        "annualized_return",
        "compounded_return",
        "continuous_equity_curve",
        "ranking",
        "recommendation",
        "score",
        "total",
    }
    assert _keys(aggregate).isdisjoint(prohibited)
    assert not any(ROOT.glob("walk.json"))
    assert not any(ROOT.glob("aggregate.json"))


def test_schema_three_stability_artifacts_preserve_upstream_bytes(
    tmp_path: Path,
) -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    source_path = (
        CONFIG.parent / raw["historical_data"]["sources"][0]["path"]
    ).resolve()
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    (data_directory / "SPY.csv").write_bytes(source_path.read_bytes())
    raw["historical_data"]["sources"][0]["path"] = "data/SPY.csv"
    raw["schema_version"] = 3
    raw["stability_policy"] = {
        "policy_id": "00000000-0000-0000-0000-000000000640",
        "metrics": [
            {
                "metric": "SIMULATION_RETURN",
                "operations": [
                    "ADJACENT_ABSOLUTE_CHANGE",
                    "RANGE",
                    "MEDIAN_ABSOLUTE_DEVIATION",
                    "SIGN_CHANGE_COUNT",
                ],
                "comparability_rule": "EQUAL_TEST_DURATION",
            },
            {
                "metric": "TOTAL_ORDERS",
                "operations": [
                    "ADJACENT_ABSOLUTE_CHANGE",
                    "RANGE",
                    "MEDIAN_ABSOLUTE_DEVIATION",
                ],
                "comparability_rule": ("EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT"),
            },
        ],
        "metadata": [{"key": "purpose", "value": "stability-e2e"}],
    }
    config = tmp_path / "schema-three.json"
    config.write_text(json.dumps(raw), encoding="utf-8")
    schema_two = tmp_path / "schema-two"
    schema_three = tmp_path / "schema-three"

    _run_cli(schema_two)
    _run_cli(schema_three, config=config, stability=True)

    for name in ARTIFACT_NAMES:
        assert (schema_two / name).read_bytes() == (schema_three / name).read_bytes()
    stability_json = schema_three / "stability.json"
    stability_csv = schema_three / "stability.csv"
    assert stability_json.is_file() and stability_csv.is_file()
    stability = json.loads(stability_json.read_bytes())["walk_forward_stability_result"]
    walk = json.loads((schema_three / "walk.json").read_bytes())["walk_forward_result"]
    aggregate = json.loads((schema_three / "aggregate.json").read_bytes())[
        "walk_forward_aggregate_result"
    ]
    assert stability["source_walk_forward_result_id"] == walk["result_id"]
    assert stability["source_aggregate_result_id"] == aggregate["result_id"]
    selections = [fold["selection"]["selected_variant_id"] for fold in walk["folds"]]
    transitions = stability["selection_stability"]["transitions"]
    assert [
        (item["from_variant_id"], item["to_variant_id"]) for item in transitions
    ] == list(zip(selections, selections[1:], strict=False))
    assert all(
        type(item["test_duration_microseconds"]) is int
        for item in stability["selection_stability"]["observations"]
    )
    assert not any(ROOT.glob("stability.json"))
