import hashlib
import json
from pathlib import Path

import pytest
from tests.cli.test_walk_forward_aggregate_config import raw_schema_two
from tests.cli.test_walk_forward_experiment_config import raw_walk_forward

from trading_bot.cli import coordinated_output, walk_forward_experiment
from trading_bot.cli.walk_forward_experiment_config import (
    load_walk_forward_experiment_config,
)
from trading_bot.experiments import HistoricalExperimentWalkForwardRunner
from trading_bot.market_data import CoordinatingHistoricalDataProvider


def write_config(tmp_path: Path) -> Path:
    raw = raw_walk_forward()
    raw["historical_data"]["end"] = "2026-01-11T20:00:00+00:00"
    data = tmp_path / "data"
    data.mkdir()
    closes = {
        "SPY": ("100", "102", "104", "106", "108", "110"),
        "QQQ": ("90", "91", "92", "93", "94", "95"),
    }
    for symbol, values in closes.items():
        lines = ["timestamp,symbol,open,high,low,close,volume"]
        for day, close in enumerate(values, start=5):
            lines.append(
                f"2026-01-{day:02d}T20:00:00+00:00,{symbol},"
                f"{close},{close},{close},{close},1000"
            )
        (data / f"{symbol}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for source in raw["historical_data"]["sources"]:
        source["path"] = f"data/{source['symbol']}.csv"
    path = tmp_path / "walk-forward.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_cli_loads_once_and_calls_one_walk_forward_runner_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider_calls = 0
    runner_constructions = 0
    runner_calls = 0
    original_coordinator = CoordinatingHistoricalDataProvider
    original_runner = HistoricalExperimentWalkForwardRunner

    class CountingCoordinator(original_coordinator):
        def get_bars(self, request):  # type: ignore[no-untyped-def]
            nonlocal provider_calls
            provider_calls += 1
            return super().get_bars(request)

    class CountingRunner:
        def __init__(self, factory):  # type: ignore[no-untyped-def]
            nonlocal runner_constructions
            runner_constructions += 1
            self._runner = original_runner(factory)

        def run(self, request):  # type: ignore[no-untyped-def]
            nonlocal runner_calls
            runner_calls += 1
            return self._runner.run(request)

    monkeypatch.setattr(
        walk_forward_experiment, "_coordinator_type", CountingCoordinator
    )
    monkeypatch.setattr(walk_forward_experiment, "_runner_type", CountingRunner)
    run = walk_forward_experiment.run_cli(write_config(tmp_path))
    assert provider_calls == 1
    assert runner_constructions == 1
    assert runner_calls == 1
    assert len(run.result.folds) == 1


def test_summary_only_and_exact_result_handoff_to_both_serializers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = write_config(tmp_path)
    seen = []
    json_serializer = walk_forward_experiment._json_serializer
    csv_serializer = walk_forward_experiment._csv_serializer

    def json_recording(result, *, pretty):  # type: ignore[no-untyped-def]
        seen.append(result)
        return json_serializer(result, pretty=pretty)

    def csv_recording(result):  # type: ignore[no-untyped-def]
        seen.append(result)
        return csv_serializer(result)

    monkeypatch.setattr(walk_forward_experiment, "_json_serializer", json_recording)
    monkeypatch.setattr(walk_forward_experiment, "_csv_serializer", csv_recording)
    assert walk_forward_experiment.main(["--config", str(config), "--quiet"]) == 0
    assert seen == []
    assert (
        walk_forward_experiment.main(
            [
                "--config",
                str(config),
                "--json",
                str(tmp_path / "result.json"),
                "--csv",
                str(tmp_path / "result.csv"),
                "--quiet",
            ]
        )
        == 0
    )
    assert len(seen) == 2
    assert seen[0] is seen[1]


def test_manifest_uses_exact_once_rendered_bytes_and_is_rejected_if_existing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = write_config(tmp_path)
    json_path = tmp_path / "result.json"
    csv_path = tmp_path / "result.csv"
    manifest_path = tmp_path / "manifest.json"
    json_calls = 0
    csv_calls = 0
    json_serializer = walk_forward_experiment._json_serializer
    csv_serializer = walk_forward_experiment._csv_serializer

    def json_recording(result, *, pretty):  # type: ignore[no-untyped-def]
        nonlocal json_calls
        json_calls += 1
        return json_serializer(result, pretty=pretty)

    def csv_recording(result):  # type: ignore[no-untyped-def]
        nonlocal csv_calls
        csv_calls += 1
        return csv_serializer(result)

    monkeypatch.setattr(walk_forward_experiment, "_json_serializer", json_recording)
    monkeypatch.setattr(walk_forward_experiment, "_csv_serializer", csv_recording)
    arguments = [
        "--config",
        str(config),
        "--json",
        str(json_path),
        "--csv",
        str(csv_path),
        "--manifest",
        str(manifest_path),
        "--session-label",
        "local",
        "--session-metadata",
        "purpose=audit",
        "--quiet",
    ]
    assert walk_forward_experiment.main(arguments) == 0
    assert json_calls == csv_calls == 1
    payload = json.loads(manifest_path.read_bytes())[
        "walk_forward_research_session_manifest"
    ]
    records = payload["artifacts"]
    assert [item["kind"] for item in records] == [
        "WALK_FORWARD_JSON",
        "WALK_FORWARD_CSV",
    ]
    for record, path in zip(records, (json_path, csv_path), strict=True):
        content = path.read_bytes()
        assert record["byte_length"] == len(content)
        assert record["hash"]["value"] == hashlib.sha256(content).hexdigest()

    assert walk_forward_experiment.main([*arguments, "--overwrite"]) == 7
    assert (
        "cannot be overwritten in manifest schema version 1" in capsys.readouterr().err
    )
    assert json_calls == csv_calls == 1


def test_factory_key_includes_child_request_variant_and_ordinal(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    loaded = load_walk_forward_experiment_config(config)
    factory = walk_forward_experiment._WalkForwardSimulatorFactory()
    variant = loaded.variants[0]
    first = factory(
        loaded.initial_state,
        experiment_request_id=loaded.request_id,
        variant_id=variant.variant_id,
        variant_ordinal=0,
    )
    second = factory(
        loaded.initial_state,
        experiment_request_id=loaded.folds[0].fold_id,
        variant_id=variant.variant_id,
        variant_ordinal=0,
    )
    assert first is not second
    with pytest.raises(ValueError, match="duplicate"):
        factory(
            loaded.initial_state,
            experiment_request_id=loaded.request_id,
            variant_id=variant.variant_id,
            variant_ordinal=0,
        )


def test_collision_preflight_and_staging_failure_preserve_destinations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = write_config(tmp_path)
    destination = tmp_path / "result.json"
    destination.write_text("keep", encoding="utf-8")
    assert (
        walk_forward_experiment.main(
            ["--config", str(config), "--json", str(destination), "--quiet"]
        )
        == 7
    )
    assert destination.read_text(encoding="utf-8") == "keep"
    assert "already exists" in capsys.readouterr().err

    def failing_fsync(descriptor):  # type: ignore[no-untyped-def]
        raise OSError("deliberate staging failure")

    monkeypatch.setattr(coordinated_output.os, "fsync", failing_fsync)
    assert (
        walk_forward_experiment.main(
            [
                "--config",
                str(config),
                "--json",
                str(destination),
                "--overwrite",
                "--quiet",
            ]
        )
        == 7
    )
    assert destination.read_text(encoding="utf-8") == "keep"
    assert not tuple(tmp_path.glob("*.tmp"))


def test_summary_explicitly_disclaims_aggregate_equity_curve(tmp_path: Path) -> None:
    summary = walk_forward_experiment.run_cli(write_config(tmp_path)).summary
    assert "Fold 0:" in summary
    assert "selected rank: 1" in summary
    assert "no aggregate out-of-sample metrics" in summary
    assert "continuous equity curve" in summary


def test_schema_two_runs_one_runner_and_one_analyzer_with_exact_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = write_config(tmp_path)
    raw = json.loads(config.read_text(encoding="utf-8"))
    aggregate = raw_schema_two()
    raw["schema_version"] = 2
    raw["aggregate_policy"] = aggregate["aggregate_policy"]
    config.write_text(json.dumps(raw), encoding="utf-8")
    runner_type = walk_forward_experiment._runner_type
    analyzer_type = walk_forward_experiment._aggregate_analyzer_type
    seen = []

    class CountingRunner:
        calls = 0

        def __init__(self, factory):
            self._runner = runner_type(factory)

        def run(self, request):
            type(self).calls += 1
            result = self._runner.run(request)
            seen.append(result)
            return result

    class CountingAnalyzer:
        calls = 0

        def analyze(self, result, policy):
            type(self).calls += 1
            assert result is seen[0]
            return analyzer_type().analyze(result, policy)

    monkeypatch.setattr(walk_forward_experiment, "_runner_type", CountingRunner)
    monkeypatch.setattr(
        walk_forward_experiment, "_aggregate_analyzer_type", CountingAnalyzer
    )
    run = walk_forward_experiment.run_cli(config)
    assert CountingRunner.calls == CountingAnalyzer.calls == 1
    assert run.aggregate_result is not None
    assert "independent simulation" in run.summary
    assert "distribution of fold observations" in run.summary


def test_schema_one_aggregate_destination_fails_before_historical_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = write_config(tmp_path)

    class ForbiddenCoordinator:
        def __init__(self, provider):
            raise AssertionError("historical loading must not begin")

    monkeypatch.setattr(
        walk_forward_experiment, "_coordinator_type", ForbiddenCoordinator
    )
    assert (
        walk_forward_experiment.main(
            [
                "--config",
                str(config),
                "--aggregate-json",
                str(tmp_path / "aggregate.json"),
                "--quiet",
            ]
        )
        == 4
    )


def test_schema_three_runs_exact_analyzers_and_writes_stability_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = write_config(tmp_path)
    raw = json.loads(config.read_text(encoding="utf-8"))
    raw["schema_version"] = 3
    raw["aggregate_policy"] = None
    raw["stability_policy"] = {
        "policy_id": "00000000-0000-0000-0000-000000000540",
        "metrics": [
            {
                "metric": "SIMULATION_RETURN",
                "operations": [],
                "comparability_rule": "NONE",
            }
        ],
        "metadata": [],
    }
    config.write_text(json.dumps(raw), encoding="utf-8")
    runner_type = walk_forward_experiment._runner_type
    stability_type = walk_forward_experiment._stability_analyzer_type
    seen = []

    class CountingRunner:
        calls = 0

        def __init__(self, factory):
            self._runner = runner_type(factory)

        def run(self, request):
            type(self).calls += 1
            result = self._runner.run(request)
            seen.append(result)
            return result

    class CountingStability:
        calls = 0

        def analyze(self, result, policy, aggregate):
            type(self).calls += 1
            assert result is seen[0]
            assert aggregate is None
            return stability_type().analyze(result, policy, aggregate)

    monkeypatch.setattr(walk_forward_experiment, "_runner_type", CountingRunner)
    monkeypatch.setattr(
        walk_forward_experiment, "_stability_analyzer_type", CountingStability
    )
    json_path = tmp_path / "stability.json"
    csv_path = tmp_path / "stability.csv"
    assert (
        walk_forward_experiment.main(
            [
                "--config",
                str(config),
                "--stability-json",
                str(json_path),
                "--stability-csv",
                str(csv_path),
                "--quiet",
            ]
        )
        == 0
    )
    assert CountingRunner.calls == CountingStability.calls == 1
    assert json_path.is_file() and csv_path.is_file()


def test_schema_three_passes_exact_aggregate_to_stability_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = write_config(tmp_path)
    raw = json.loads(config.read_text(encoding="utf-8"))
    raw["schema_version"] = 3
    raw["aggregate_policy"] = raw_schema_two()["aggregate_policy"]
    raw["stability_policy"] = {
        "policy_id": "00000000-0000-0000-0000-000000000541",
        "metrics": [
            {
                "metric": "SIMULATION_RETURN",
                "operations": [],
                "comparability_rule": "NONE",
            }
        ],
        "metadata": [],
    }
    config.write_text(json.dumps(raw), encoding="utf-8")
    aggregate_type = walk_forward_experiment._aggregate_analyzer_type
    stability_type = walk_forward_experiment._stability_analyzer_type
    seen = []

    class CountingAggregate:
        calls = 0

        def analyze(self, result, policy):
            type(self).calls += 1
            aggregate = aggregate_type().analyze(result, policy)
            seen.append((result, aggregate))
            return aggregate

    class CountingStability:
        calls = 0

        def analyze(self, result, policy, aggregate):
            type(self).calls += 1
            assert result is seen[0][0]
            assert aggregate is seen[0][1]
            return stability_type().analyze(result, policy, aggregate)

    monkeypatch.setattr(
        walk_forward_experiment, "_aggregate_analyzer_type", CountingAggregate
    )
    monkeypatch.setattr(
        walk_forward_experiment, "_stability_analyzer_type", CountingStability
    )
    run = walk_forward_experiment.run_cli(config)
    assert CountingAggregate.calls == CountingStability.calls == 1
    assert run.aggregate_result is seen[0][1]
    assert run.stability_result is not None
    assert (
        run.stability_result.source_aggregate_result_id
        == run.aggregate_result.result_id
    )


def test_stability_destination_compatibility_fails_before_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = write_config(tmp_path)

    class ForbiddenCoordinator:
        def __init__(self, provider):
            raise AssertionError("historical loading must not begin")

    monkeypatch.setattr(
        walk_forward_experiment, "_coordinator_type", ForbiddenCoordinator
    )
    assert (
        walk_forward_experiment.main(
            [
                "--config",
                str(config),
                "--stability-json",
                str(tmp_path / "stability.json"),
                "--quiet",
            ]
        )
        == 4
    )
