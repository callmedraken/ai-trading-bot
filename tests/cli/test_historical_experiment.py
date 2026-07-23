import json
from pathlib import Path

import pytest

from trading_bot.cli import historical_experiment
from trading_bot.cli._simulation_bootstrap import initialize_ledger
from trading_bot.cli.config import _initial_ledger
from trading_bot.cli.exceptions import ConfigValidationError
from trading_bot.cli.historical_experiment_config import (
    load_historical_experiment_config,
    parse_historical_experiment_config,
)
from trading_bot.cli.historical_experiment_serialization import (
    build_historical_experiment_audit,
)
from trading_bot.cli.serialization import serialize_audit
from trading_bot.experiments import HistoricalExperimentRunner
from trading_bot.market_data import CoordinatingHistoricalDataProvider

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment.example.json"


def _raw() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _write_config(tmp_path: Path, raw: dict) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    for symbol in ("SPY", "QQQ"):
        source = ROOT / "examples" / "data" / "rolling-historical" / f"{symbol}.csv"
        (data / f"{symbol}.csv").write_bytes(source.read_bytes())
    for source in raw["historical_data"]["sources"]:
        source["path"] = f"data/{source['symbol']}.csv"
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_checked_in_example_parses_exact_ordered_domain_models() -> None:
    config = load_historical_experiment_config(EXAMPLE)
    assert config.schema_version == 1
    assert tuple(str(item) for item in config.historical_data.symbols) == (
        "SPY",
        "QQQ",
    )
    assert tuple(item.name for item in config.variants) == (
        "Shorter Window",
        "Longer Window",
    )
    assert tuple(item.window_policy.observation_count for item in config.variants) == (
        3,
        4,
    )


@pytest.mark.parametrize(
    ("mutate", "path"),
    (
        (lambda raw: raw.update(schema_version=2), "$.schema_version"),
        (lambda raw: raw.update(extra=True), "$.extra"),
        (lambda raw: raw.pop("initial_state"), "$.initial_state"),
        (
            lambda raw: raw["variants"][0].update(trading_enabled=1),
            "$.variants[0].trading_enabled",
        ),
        (
            lambda raw: raw["variants"][0]["optimization"].update(risk_aversion=1),
            "$.variants[0].optimization.risk_aversion",
        ),
        (
            lambda raw: raw["variants"][0]["metadata"].append(
                {"key": "historical_experiment_bad", "value": "x"}
            ),
            "$.variants[0].metadata",
        ),
    ),
)
def test_strict_schema_reports_json_paths(mutate, path: str) -> None:  # type: ignore[no-untyped-def]
    raw = _raw()
    mutate(raw)
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == path


def test_schedule_and_variant_uniqueness_are_rejected() -> None:
    raw = _raw()
    raw["rebalance_schedule"].append(raw["rebalance_schedule"][0])
    with pytest.raises(ConfigValidationError, match="strictly increasing"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _raw()
    raw["variants"][1]["variant_id"] = raw["variants"][0]["variant_id"]
    with pytest.raises(ConfigValidationError, match="variant IDs"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _raw()
    raw["variants"][1]["name"] = " shorter window "
    with pytest.raises(ConfigValidationError, match="variant names"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)


def test_initial_state_and_commission_compatibility_are_strict() -> None:
    raw = _raw()
    raw["initial_state"]["bootstrap_commission"] = "1"
    with pytest.raises(ConfigValidationError, match="exactly zero"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _raw()
    raw["variants"][0]["fills"]["fixed_commission"] = "1"
    with pytest.raises(ConfigValidationError, match="commissions must match"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)


def test_config_relative_paths_and_provider_are_used_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _write_config(tmp_path, _raw())
    events: list[str] = []

    class RecordingCoordinator:
        def __init__(self, provider):  # type: ignore[no-untyped-def]
            self.delegate = CoordinatingHistoricalDataProvider(provider)

        def get_bars(self, request):  # type: ignore[no-untyped-def]
            events.append("provider")
            return self.delegate.get_bars(request)

    monkeypatch.setattr(
        historical_experiment, "_coordinator_type", RecordingCoordinator
    )
    monkeypatch.chdir(ROOT / "tests")
    run = historical_experiment.run_cli(path)
    assert events == ["provider"]
    assert run.result.request.historical_data is run.historical_data
    assert run.historical_data.symbols == run.config.historical_data.symbols


def test_runner_is_constructed_and_called_once_with_exact_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []

    class RecordingRunner:
        def __init__(self, factory):  # type: ignore[no-untyped-def]
            events.append("constructed")
            self.delegate = HistoricalExperimentRunner(factory)

        def run(self, request):  # type: ignore[no-untyped-def]
            events.append(request)
            return self.delegate.run(request)

    monkeypatch.setattr(historical_experiment, "_runner_type", RecordingRunner)
    run = historical_experiment.run_cli(EXAMPLE)
    assert events[0] == "constructed"
    assert events[1] is run.result.request
    assert len(events) == 2
    assert run.result.request.variants == run.config.variants
    assert run.result.request.rebalance_timestamps == run.config.rebalance_schedule


def test_factory_creates_fresh_stacks_and_variant_bootstrap_ids(
    tmp_path: Path,
) -> None:
    raw = _raw()
    raw["initial_state"] = {
        "mode": "BOOTSTRAP_FILLS",
        "as_of": "2026-01-05T19:00:00+00:00",
        "available_cash": "1000",
        "bootstrap_commission": "0",
        "bootstrap_positions": [{"symbol": "SPY", "quantity": "2", "unit_cost": "100"}],
    }
    run = historical_experiment.run_cli(_write_config(tmp_path, raw))
    records = run.factory.records
    assert len(records) == 2
    assert records[0].simulator is not records[1].simulator
    assert records[0].simulator.runtime is not records[1].simulator.runtime
    assert (
        records[0].bootstrap_fills[0].fill_id != records[1].bootstrap_fills[0].fill_id
    )
    assert (
        run.result.runs[0].initial_state_content_fingerprint
        == run.result.runs[1].initial_state_content_fingerprint
    )


def test_existing_bootstrap_wrapper_identity_is_unchanged() -> None:
    config = _initial_ledger(
        {
            "initialization_mode": "BOOTSTRAP_FILLS",
            "as_of": "2026-01-05T19:00:00+00:00",
            "available_cash": "1000",
            "positions": [{"symbol": "SPY", "quantity": "2", "average_cost": "100"}],
        },
        "$.initial_ledger",
    )
    _, fills = initialize_ledger(
        historical_experiment.UUID("00000000-0000-0000-0000-000000000001"),
        config,
    )
    assert str(fills[0].fill_id) == "ae7a1847-84ef-5f10-9f12-57a451a15574"
    assert str(fills[0].order_id) == "f26b6bfe-3cc6-574b-aff8-49009ed96c1d"


def test_summary_is_ordered_complete_and_neutral() -> None:
    summary = historical_experiment.run_cli(EXAMPLE).summary
    assert summary.index("variant 0 | Shorter Window") < summary.index(
        "variant 1 | Longer Window"
    )
    assert "simulation realized P&L:" in summary
    assert "maximum target cash weight:" in summary
    lowered = summary.casefold()
    assert "winner" not in lowered
    assert "best" not in lowered
    assert "recommended" not in lowered


def test_no_output_never_builds_audit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factories = []
    original = historical_experiment._ExperimentSimulatorFactory

    class RecordingFactory(original):
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            super().__init__(**kwargs)
            factories.append(self)

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("audit builder must not run")

    monkeypatch.setattr(
        historical_experiment, "_ExperimentSimulatorFactory", RecordingFactory
    )
    monkeypatch.setattr(historical_experiment, "_audit_builder", forbidden)
    assert historical_experiment.main(["--config", str(EXAMPLE)]) == 0
    assert "experiment result ID:" in capsys.readouterr().out
    assert factories[0].records == ()


def test_quiet_writes_complete_audit_without_history_duplication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "audit.json"
    assert (
        historical_experiment.main(
            ["--config", str(EXAMPLE), "--output", str(output), "--quiet"]
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
        "experiment",
    }
    assert audit["schema_version"] == 1
    assert len(audit["historical_data"]["frames"]) == 5
    runs = audit["experiment"]["result"]["runs"]
    assert [item["ordinal"] for item in runs] == [0, 1]
    assert "historical_data" not in json.dumps(runs)
    assert "configuration" not in runs[0]["rolling"]
    assert "schema_version" not in runs[0]["rolling"]
    assert len(runs[0]["metrics"]) == 26
    assert runs[0]["metrics"]["simulation_realized_profit_loss"] == "0"


def test_compact_and_pretty_audits_are_byte_deterministic() -> None:
    runs = [historical_experiment.run_cli(EXAMPLE) for _ in range(2)]
    audits = [
        build_historical_experiment_audit(
            run.config,
            run.historical_data,
            run.result,
            run.factory.records,
        )
        for run in runs
    ]
    for pretty in (False, True):
        assert serialize_audit(audits[0], pretty=pretty) == serialize_audit(
            audits[1], pretty=pretty
        )


def test_output_collision_preserves_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("keep", encoding="utf-8")
    assert (
        historical_experiment.main(
            ["--config", str(EXAMPLE), "--output", str(output), "--quiet"]
        )
        == 7
    )
    assert output.read_text(encoding="utf-8") == "keep"
    assert "already exists" in capsys.readouterr().err
