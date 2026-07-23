import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from trading_bot.cli import rolling_historical
from trading_bot.cli.exceptions import ConfigValidationError
from trading_bot.cli.rolling_historical_config import (
    load_rolling_config,
    parse_rolling_config,
)
from trading_bot.cli.rolling_historical_serialization import (
    build_rolling_audit,
    historical_content_fingerprint,
)
from trading_bot.cli.serialization import serialize_audit
from trading_bot.market_data import CoordinatingHistoricalDataProvider
from trading_bot.simulation import RollingHistoricalOptimizedSimulationRunner

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "rolling-historical-simulation.example.json"


def _raw() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_checked_in_config_parses_strict_domain_policies() -> None:
    config = load_rolling_config(EXAMPLE)
    assert config.schema_version == 1
    assert tuple(str(item) for item in config.historical_data.symbols) == (
        "SPY",
        "QQQ",
    )
    assert config.window_policy.observation_count == 3
    assert config.historical_data.sources[0].configured_path == (
        "data/rolling-historical/SPY.csv"
    )


@pytest.mark.parametrize(
    ("mutate", "path"),
    (
        (lambda raw: raw.update(schema_version=2), "$.schema_version"),
        (lambda raw: raw.update(extra=True), "$.extra"),
        (lambda raw: raw.pop("timing"), "$.timing"),
        (lambda raw: raw.update(trading_enabled=1), "$.trading_enabled"),
        (
            lambda raw: raw["optimization"].update(risk_aversion=1),
            "$.optimization.risk_aversion",
        ),
        (
            lambda raw: raw["historical_data"].update(timeframe="1H"),
            "$.historical_data.timeframe",
        ),
        (
            lambda raw: raw["scenario"].update(price_field="OPEN"),
            "$.scenario.price_field",
        ),
        (
            lambda raw: raw["metadata"].append(
                {"key": "rolling_historical_simulation_bad", "value": "x"}
            ),
            "$.metadata",
        ),
    ),
)
def test_strict_schema_rejects_invalid_values(mutate, path: str) -> None:  # type: ignore[no-untyped-def]
    raw = _raw()
    mutate(raw)
    with pytest.raises(ConfigValidationError) as caught:
        parse_rolling_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == path


def test_source_order_common_parent_and_exact_filename_are_enforced(
    tmp_path: Path,
) -> None:
    raw = _raw()
    raw["historical_data"]["sources"].reverse()
    with pytest.raises(ConfigValidationError, match="same ordered index"):
        parse_rolling_config(raw, EXAMPLE.parent)

    raw = _raw()
    raw["historical_data"]["sources"][1]["path"] = raw["historical_data"]["sources"][0][
        "path"
    ]
    with pytest.raises(ConfigValidationError, match="same ordered index|unique"):
        parse_rolling_config(raw, EXAMPLE.parent)

    raw = _raw()
    wrong = tmp_path / "wrong.csv"
    wrong.write_text("x", encoding="utf-8")
    raw["historical_data"]["sources"][0]["path"] = str(wrong)
    with pytest.raises(ConfigValidationError, match="relative"):
        parse_rolling_config(raw, EXAMPLE.parent)


def test_config_relative_resolution_is_independent_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_rolling_config(EXAMPLE)
    assert all(item.resolved_path.is_file() for item in config.historical_data.sources)


def test_coordinator_and_runner_are_each_called_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class RecordingCoordinator:
        def __init__(self, provider):  # type: ignore[no-untyped-def]
            self.delegate = CoordinatingHistoricalDataProvider(provider)

        def get_bars(self, request):  # type: ignore[no-untyped-def]
            events.append("provider")
            return self.delegate.get_bars(request)

    class RecordingRunner:
        def __init__(self, simulator):  # type: ignore[no-untyped-def]
            self.delegate = RollingHistoricalOptimizedSimulationRunner(simulator)

        def run(self, request):  # type: ignore[no-untyped-def]
            events.append("runner")
            return self.delegate.run(request)

    monkeypatch.setattr(rolling_historical, "_coordinator_type", RecordingCoordinator)
    monkeypatch.setattr(rolling_historical, "_runner_type", RecordingRunner)
    run = rolling_historical.run_cli(EXAMPLE)
    assert events == ["provider", "runner"]
    assert run.result.request.historical_data is run.historical_data
    assert run.result.request.rebalance_timestamps == run.config.rebalance_schedule


def test_summary_contains_aggregate_sections_and_every_frame() -> None:
    summary = rolling_historical.run_cli(EXAMPLE).summary
    assert "Run:" in summary
    assert "Trading:" in summary
    assert "Optimization:" in summary
    assert "Frames:" in summary
    assert "absolute simulation P&L:" in summary
    assert "final ledger realized P&L:" in summary
    assert "frame 0 | 2026-01-07T20:00:00+00:00 | window 0..2" in summary
    assert "frame 1 | 2026-01-09T20:00:00+00:00 | window 2..4" in summary


def test_no_output_never_builds_audit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("audit builder must not run")

    monkeypatch.setattr(rolling_historical, "_audit_builder", forbidden)
    assert rolling_historical.main(["--config", str(EXAMPLE)]) == 0
    assert "rolling result ID:" in capsys.readouterr().out


def test_quiet_writes_complete_schema_one_audit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "audit.json"
    assert (
        rolling_historical.main(
            [
                "--config",
                str(EXAMPLE),
                "--output",
                str(output),
                "--quiet",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == ""
    audit = json.loads(output.read_text(encoding="utf-8"))
    assert set(audit) == {
        "schema_version",
        "configuration",
        "historical_data",
        "initial_state",
        "rolling",
    }
    assert audit["schema_version"] == 1
    assert len(audit["historical_data"]["frames"]) == 5
    generations = audit["rolling"]["result"]["frame_generations"]
    assert len(generations) == 2
    assert (
        "frames"
        not in generations[0]["scenario_result"]["request"]["historical_request"]
    )
    assert "configuration" not in audit["rolling"]["result"]["optimized_simulation"]


def test_audit_paths_are_relative_and_fingerprint_uses_loaded_content() -> None:
    run = rolling_historical.run_cli(EXAMPLE)
    audit = build_rolling_audit(
        run.config,
        run.historical_data,
        run.result,
        run.ledger,
        run.bootstrap_fills,
    )
    sources = audit["configuration"]["historical_data"]["sources"]
    assert sources[0]["path"] == "data/rolling-historical/SPY.csv"
    rendered = serialize_audit(audit, pretty=False)
    assert str(ROOT.resolve()) not in rendered
    assert audit["historical_data"]["content_fingerprint"] == str(
        historical_content_fingerprint(run.historical_data)
    )


def test_compact_and_pretty_reports_are_byte_deterministic() -> None:
    first = rolling_historical.run_cli(EXAMPLE)
    second = rolling_historical.run_cli(EXAMPLE)
    audits = [
        build_rolling_audit(
            run.config,
            run.historical_data,
            run.result,
            run.ledger,
            run.bootstrap_fills,
        )
        for run in (first, second)
    ]
    assert serialize_audit(audits[0], pretty=False) == serialize_audit(
        audits[1], pretty=False
    )
    assert serialize_audit(audits[0], pretty=True) == serialize_audit(
        audits[1], pretty=True
    )


def test_representative_audit_bytes_retain_compatibility_digests() -> None:
    run = rolling_historical.run_cli(EXAMPLE)
    audit = build_rolling_audit(
        run.config,
        run.historical_data,
        run.result,
        run.ledger,
        run.bootstrap_fills,
    )
    expected = {
        False: "d77a1b4c52df2d7bd927dd15ff69680ed7f83fecfd304c2df4a45247000e45d7",
        True: "b6c95c75a2fe0d1ee434d9a2e43d5bef2d81662f5cb20f2bc02a256dd27449dd",
    }
    for pretty, digest in expected.items():
        rendered = serialize_audit(audit, pretty=pretty)
        assert rendered.endswith("\n")
        assert sha256(rendered.encode("utf-8")).hexdigest() == digest


def test_schedule_window_and_metadata_change_report_bytes() -> None:
    raw = _raw()
    baseline = rolling_historical.run_cli(EXAMPLE)
    baseline_text = serialize_audit(
        build_rolling_audit(
            baseline.config,
            baseline.historical_data,
            baseline.result,
            baseline.ledger,
            baseline.bootstrap_fills,
        ),
        pretty=False,
    )
    changed = deepcopy(raw)
    changed["metadata"][0]["value"] = "changed"
    path = EXAMPLE.parent / "rolling-historical-simulation.changed.tmp.json"
    try:
        path.write_text(json.dumps(changed), encoding="utf-8")
        run = rolling_historical.run_cli(path)
    finally:
        path.unlink(missing_ok=True)
    changed_text = serialize_audit(
        build_rolling_audit(
            run.config,
            run.historical_data,
            run.result,
            run.ledger,
            run.bootstrap_fills,
        ),
        pretty=False,
    )
    assert baseline_text != changed_text


def test_output_collision_preserves_existing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("keep", encoding="utf-8")
    assert (
        rolling_historical.main(
            ["--config", str(EXAMPLE), "--output", str(output), "--quiet"]
        )
        == 7
    )
    assert output.read_text(encoding="utf-8") == "keep"
    assert "already exists" in capsys.readouterr().err
