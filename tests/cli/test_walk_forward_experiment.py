import json
from pathlib import Path

import pytest
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
