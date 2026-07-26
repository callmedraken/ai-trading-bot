import csv
import hashlib
import io
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
    manifest: bool = False,
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
    if manifest:
        arguments.extend(
            [
                "--manifest",
                str(destination / "manifest.json"),
                "--session-label",
                "schema-3-e2e",
                "--session-metadata",
                "purpose=cross-artifact-reconciliation",
            ]
        )
    subprocess.run(arguments, cwd=ROOT, check=True)


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _keys(child)}
    return set()


def _median(values: list[Fraction]) -> Fraction:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _first_appearance_counts(values: list[object]) -> list[tuple[object, int]]:
    order = []
    counts = {}
    for value in values:
        if value not in counts:
            order.append(value)
            counts[value] = 0
        counts[value] += 1
    return [(value, counts[value]) for value in order]


def _selection_runs(values: list[str]) -> list[tuple[int, int, str, int]]:
    runs = []
    start = 0
    for index in range(1, len(values) + 1):
        if index == len(values) or values[index] != values[start]:
            runs.append((start, index - 1, values[start], index - start))
            start = index
    return runs


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
    first = tmp_path / "schema-three-first"
    second = tmp_path / "schema-three-second"
    without_stability_destinations = tmp_path / "without-stability-destinations"

    _run_cli(first, config=config, stability=True, manifest=True)
    _run_cli(second, config=config, stability=True, manifest=True)
    _run_cli(without_stability_destinations, config=config)

    all_artifacts = (
        *ARTIFACT_NAMES,
        "stability.json",
        "stability.csv",
        "manifest.json",
    )
    assert {item.name for item in first.iterdir()} == set(all_artifacts)
    for name in all_artifacts:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    for name in ARTIFACT_NAMES:
        assert (first / name).read_bytes() == (
            without_stability_destinations / name
        ).read_bytes()

    stability = json.loads((first / "stability.json").read_bytes())[
        "walk_forward_stability_result"
    ]
    repeated_stability = json.loads((second / "stability.json").read_bytes())[
        "walk_forward_stability_result"
    ]
    walk = json.loads((first / "walk.json").read_bytes())["walk_forward_result"]
    aggregate = json.loads((first / "aggregate.json").read_bytes())[
        "walk_forward_aggregate_result"
    ]
    manifest = json.loads((first / "manifest.json").read_bytes())[
        "walk_forward_research_session_manifest"
    ]
    assert stability["result_id"] == repeated_stability["result_id"]
    assert stability["source_walk_forward_result_id"] == walk["result_id"]
    assert stability["source_aggregate_result_id"] == aggregate["result_id"]
    assert aggregate["source_walk_forward_result_id"] == walk["result_id"]
    assert manifest["walk_forward_config_schema_version"] == 3
    assert manifest["result_ids"] == {
        "walk_forward": walk["result_id"],
        "aggregate": aggregate["result_id"],
        "stability": stability["result_id"],
    }
    assert manifest["session_label"] == "schema-3-e2e"
    assert manifest["metadata"] == [
        {"key": "purpose", "value": "cross-artifact-reconciliation"}
    ]
    primary_names = (
        "walk.json",
        "walk.csv",
        "aggregate.json",
        "aggregate.csv",
        "stability.json",
        "stability.csv",
    )
    assert [item["path"] for item in manifest["artifacts"]] == list(primary_names)
    assert [item["ordinal"] for item in manifest["artifacts"]] == list(range(1, 7))
    for record, name in zip(manifest["artifacts"], primary_names, strict=True):
        exact_bytes = (first / name).read_bytes()
        assert record["path_base"] == "MANIFEST_PARENT"
        assert record["byte_length"] == len(exact_bytes)
        assert record["hash"] == {
            "algorithm": "SHA256",
            "value": hashlib.sha256(exact_bytes).hexdigest(),
        }

    stability_csv_rows = list(
        csv.DictReader(io.StringIO((first / "stability.csv").read_text("utf-8")))
    )
    assert stability_csv_rows
    assert {row["stability_result_id"] for row in stability_csv_rows} == {
        stability["result_id"]
    }
    assert {row["source_walk_forward_result_id"] for row in stability_csv_rows} == {
        walk["result_id"]
    }
    assert {row["source_aggregate_result_id"] for row in stability_csv_rows} == {
        aggregate["result_id"]
    }

    folds = walk["folds"]
    selections = [fold["selection"]["selected_variant_id"] for fold in walk["folds"]]
    fold_ids = [fold["fold"]["fold_id"] for fold in folds]
    selection = stability["selection_stability"]
    observations = selection["observations"]
    assert [
        (item["fold_ordinal"], item["fold_id"], item["selected_variant_id"])
        for item in observations
    ] == [
        (ordinal, fold_id, variant_id)
        for ordinal, (fold_id, variant_id) in enumerate(
            zip(fold_ids, selections, strict=True)
        )
    ]

    transitions = selection["transitions"]
    expected_pairs = list(zip(selections, selections[1:], strict=False))
    assert [
        (item["from_variant_id"], item["to_variant_id"]) for item in transitions
    ] == expected_pairs
    assert [item["changed"] for item in transitions] == [
        previous != current for previous, current in expected_pairs
    ]
    assert any(item["from_variant_id"] == item["to_variant_id"] for item in transitions)

    persistent = sum(previous == current for previous, current in expected_pairs)
    changed = len(expected_pairs) - persistent
    assert selection["persistence_adjacency_count"] == persistent
    assert selection["changed_adjacency_count"] == changed
    persistence = Fraction(persistent, len(expected_pairs))
    assert selection["persistence_ratio"] == {
        "numerator": persistence.numerator,
        "denominator": persistence.denominator,
    }

    expected_runs = _selection_runs(selections)
    assert [
        (
            item["start_fold_ordinal"],
            item["end_fold_ordinal"],
            item["variant_id"],
            item["consecutive_fold_count"],
        )
        for item in selection["runs"]
    ] == expected_runs
    assert selection["longest_consecutive_selection_run"] == max(
        item[3] for item in expected_runs
    )

    expected_transition_frequencies = _first_appearance_counts(expected_pairs)
    assert [
        (
            (item["from_variant_id"], item["to_variant_id"]),
            item["occurrence_count"],
        )
        for item in selection["transition_frequencies"]
    ] == expected_transition_frequencies
    expected_variant_frequencies = _first_appearance_counts(selections)
    assert [
        (item["variant_id"], item["selected_fold_count"])
        for item in selection["variant_frequencies"]
    ] == expected_variant_frequencies
    assert [
        item["first_selected_fold_ordinal"] for item in selection["variant_frequencies"]
    ] == [selections.index(item[0]) for item in expected_variant_frequencies]

    metric_fields = {
        "SIMULATION_RETURN": "simulation_return",
        "TOTAL_ORDERS": "total_orders",
    }
    aggregate_observations = {
        item["metric"]: [observation["value"] for observation in item["observations"]]
        for item in aggregate["metric_summaries"]
    }
    for summary in stability["metric_stability"]:
        metric = summary["metric"]
        source_values = [
            fold["test"]["report"]["variants"][0]["metrics"][metric_fields[metric]]
            for fold in folds
        ]
        serialized_values = [
            observation["value"] for observation in summary["observations"]
        ]
        assert serialized_values == source_values
        if metric in aggregate_observations:
            assert serialized_values == aggregate_observations[metric]

        exact_values = [Fraction(str(value)) for value in serialized_values]
        assert [
            Fraction(str(item["absolute_change"]))
            for item in summary["adjacent_changes"]
        ] == [
            abs(current - previous)
            for previous, current in zip(exact_values, exact_values[1:], strict=False)
        ]
        assert Fraction(str(summary["value_range"])) == (
            max(exact_values) - min(exact_values)
        )
        exact_median = _median(exact_values)
        assert Fraction(str(summary["median"])) == exact_median
        exact_mad = _median([abs(value - exact_median) for value in exact_values])
        assert Fraction(str(summary["median_absolute_deviation"])) == exact_mad
        if summary["sign_change_count"] is not None:
            expected_sign_changes = sum(
                previous != 0
                and current != 0
                and ((previous < 0 < current) or (current < 0 < previous))
                for previous, current in zip(
                    exact_values, exact_values[1:], strict=False
                )
            )
            assert summary["sign_change_count"] == expected_sign_changes

    assert all(type(item["test_duration_microseconds"]) is int for item in observations)
    prohibited = {
        "aggregate_total",
        "annualization",
        "annualized_return",
        "causal",
        "compounded_return",
        "continuous_equity_curve",
        "quality",
        "ranking",
        "recommendation",
        "score",
        "total",
        "winner",
    }
    assert _keys(stability).isdisjoint(prohibited)
    assert set(stability_csv_rows[0]).isdisjoint(prohibited)
    assert not any(ROOT.glob("stability.json"))
    assert not any(ROOT.glob("stability.csv"))
