import json
from copy import deepcopy
from hashlib import sha256
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
    _build_raw_experiment_sections,
    build_historical_experiment_audit,
)
from trading_bot.cli.serialization import serialize_audit
from trading_bot.experiments import (
    HistoricalExperimentComparator,
    HistoricalExperimentRankingError,
    HistoricalExperimentRunner,
)
from trading_bot.market_data import CoordinatingHistoricalDataProvider

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment.example.json"
FIXTURES = ROOT / "tests" / "fixtures" / "cli"


def _raw() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _write_config(tmp_path: Path, raw: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
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
    assert config.schema_version == 2
    assert config.ranking_policy is not None
    assert len(config.ranking_policy.criteria) == 2
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
        (lambda raw: raw.update(schema_version=1), "$.schema_version"),
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


def test_schema_one_rejection_has_migration_guidance() -> None:
    raw = _raw()
    raw["schema_version"] = 1
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == "$.schema_version"
    assert "requires version 2" in str(caught.value)


def test_missing_and_null_ranking_canonicalize_to_none() -> None:
    missing = _raw()
    missing.pop("ranking")
    explicit_null = _raw()
    explicit_null["ranking"] = None
    first = parse_historical_experiment_config(missing, EXAMPLE.parent)
    second = parse_historical_experiment_config(explicit_null, EXAMPLE.parent)
    assert first.ranking_policy is None
    assert second.ranking_policy is None
    assert first == second


@pytest.mark.parametrize(
    ("mutate", "path"),
    (
        (lambda raw: raw["ranking"].update(extra=True), "$.ranking.extra"),
        (lambda raw: raw["ranking"].update(policy_id="bad"), "$.ranking.policy_id"),
        (
            lambda raw: raw["ranking"].update(criteria=[]),
            "$.ranking.criteria",
        ),
        (
            lambda raw: raw["ranking"]["criteria"][0].update(metric="UNKNOWN"),
            "$.ranking.criteria[0].metric",
        ),
        (
            lambda raw: raw["ranking"]["criteria"][0].update(direction="MAXIMIZE"),
            "$.ranking.criteria[0].direction",
        ),
        (
            lambda raw: raw["ranking"].update(tie_breaker="RUN_ID"),
            "$.ranking.tie_breaker",
        ),
    ),
)
def test_ranking_schema_rejects_invalid_values(mutate, path: str) -> None:  # type: ignore[no-untyped-def]
    raw = _raw()
    mutate(raw)
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == path


def test_ranking_rejects_duplicate_criteria_and_metadata() -> None:
    raw = _raw()
    raw["ranking"]["criteria"].append(deepcopy(raw["ranking"]["criteria"][0]))
    with pytest.raises(ConfigValidationError, match="unique"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _raw()
    raw["ranking"]["metadata"] = [
        {"key": "same", "value": "1"},
        {"key": "same", "value": "2"},
    ]
    with pytest.raises(ConfigValidationError, match="unique"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _raw()
    raw["ranking"]["metadata"] = [
        {"key": "historical_experiment_comparison_bad", "value": "x"}
    ]
    with pytest.raises(ConfigValidationError, match="reserved"):
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
    run = historical_experiment.run_cli(EXAMPLE)
    summary = run.summary
    raw_summary = historical_experiment._format_summary(run.result)
    assert summary.startswith(raw_summary)
    assert "Ranking policy:" in summary
    assert "SIMULATION_RETURN: " in summary
    assert summary.index("SIMULATION_RETURN: ") < summary.index(
        "MAXIMUM_DRAWDOWN_PERCENTAGE: "
    )
    assert summary.index("variant 0 | Shorter Window") < summary.index(
        "variant 1 | Longer Window"
    )
    assert "simulation realized P&L:" in summary
    assert "maximum target cash weight:" in summary
    lowered = summary.casefold()
    assert "winner" not in lowered
    assert "best" not in lowered
    assert "recommended" not in lowered
    assert "superior" not in lowered
    assert "optimal" not in lowered
    assert "selected" not in lowered
    assert "live candidate" not in lowered


def test_comparator_is_optional_single_use_and_receives_exact_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[tuple[str, object | None]] = []

    class RecordingRunner:
        def __init__(self, factory):  # type: ignore[no-untyped-def]
            self.delegate = HistoricalExperimentRunner(factory)

        def run(self, request):  # type: ignore[no-untyped-def]
            result = self.delegate.run(request)
            events.append(("runner", result))
            return result

    class RecordingComparator:
        def __init__(self) -> None:
            events.append(("comparator constructed", None))
            self.delegate = HistoricalExperimentComparator()

        def compare(self, result, policy):  # type: ignore[no-untyped-def]
            events.append(("compare", result))
            return self.delegate.compare(result, policy)

    monkeypatch.setattr(historical_experiment, "_runner_type", RecordingRunner)
    monkeypatch.setattr(historical_experiment, "_comparator_type", RecordingComparator)
    ranked = historical_experiment.run_cli(EXAMPLE)
    assert events == [
        ("runner", ranked.result),
        ("comparator constructed", None),
        ("compare", ranked.result),
    ]

    events.clear()
    raw = _raw()
    raw["ranking"] = None
    unranked = historical_experiment.run_cli(_write_config(tmp_path, raw))
    assert events == [("runner", unranked.result)]
    assert unranked.comparison is None
    assert "Ranking policy:" not in unranked.summary


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
        "comparison",
    }
    assert audit["schema_version"] == 2
    assert audit["configuration"]["ranking"] == audit["comparison"]["policy"]
    assert (
        audit["comparison"]["source_experiment_result_id"]
        == audit["experiment"]["result"]["result_id"]
    )
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
            run.comparison,
            run.factory.records,
        )
        for run in runs
    ]
    for pretty in (False, True):
        assert serialize_audit(audits[0], pretty=pretty) == serialize_audit(
            audits[1], pretty=pretty
        )


@pytest.mark.parametrize(
    ("pretty", "fixture_name"),
    (
        (False, "historical-experiment-audit-v2-compact.json"),
        (True, "historical-experiment-audit-v2-pretty.json"),
    ),
)
def test_schema_two_audit_matches_exact_fixture(
    pretty: bool, fixture_name: str
) -> None:
    run = historical_experiment.run_cli(EXAMPLE)
    audit = build_historical_experiment_audit(
        run.config,
        run.historical_data,
        run.result,
        run.comparison,
        run.factory.records,
    )
    assert serialize_audit(audit, pretty=pretty) == (FIXTURES / fixture_name).read_text(
        encoding="utf-8"
    )


def test_missing_ranking_audit_is_canonical_null(tmp_path: Path) -> None:
    raw = _raw()
    raw.pop("ranking")
    run = historical_experiment.run_cli(_write_config(tmp_path, raw))
    audit = build_historical_experiment_audit(
        run.config,
        run.historical_data,
        run.result,
        run.comparison,
        run.factory.records,
    )
    assert audit["configuration"]["ranking"] is None
    assert audit["comparison"] is None


def test_schema_one_raw_section_digest_sentinels() -> None:
    run = historical_experiment.run_cli(EXAMPLE)
    raw = _build_raw_experiment_sections(
        run.config, run.historical_data, run.result, run.factory.records
    )
    legacy = {"schema_version": 1, **raw}
    legacy["configuration"] = dict(legacy["configuration"])
    legacy["configuration"]["schema_version"] = 1
    legacy["configuration"].pop("ranking")
    expected = {
        False: "9821bc983bec97939c8395251bee57dddb349072c317afb7898f4093a218138e",
        True: "29dfd1c13189e65f579979e0721cc60b0e06e52d02d1ae72b7d81bafeabb5fff",
    }
    for pretty, digest in expected.items():
        assert (
            sha256(serialize_audit(legacy, pretty=pretty).encode()).hexdigest()
            == digest
        )


def test_raw_identities_do_not_depend_on_ranking_policy(tmp_path: Path) -> None:
    raws = []
    for ordinal in range(3):
        raw = _raw()
        if ordinal == 0:
            raw["ranking"] = None
        else:
            raw["ranking"]["policy_id"] = (
                f"00000000-0000-0000-0000-00000000042{ordinal}"
            )
            if ordinal == 2:
                raw["ranking"]["tie_breaker"] = "VARIANT_ID"
        raws.append(raw)
    runs = [
        historical_experiment.run_cli(_write_config(tmp_path / f"case-{ordinal}", raw))
        for ordinal, raw in enumerate(raws)
    ]

    def identities(run):  # type: ignore[no-untyped-def]
        return (
            run.result.result_id,
            tuple(
                (
                    item.run_id,
                    item.rolling_result.result_id,
                    item.rolling_result.optimized_result.result_id,
                    item.rolling_result.performance_result.result_id,
                )
                for item in run.result.runs
            ),
        )

    assert identities(runs[0]) == identities(runs[1]) == identities(runs[2])
    assert runs[1].comparison is not None
    assert runs[2].comparison is not None
    assert runs[1].comparison.result_id != runs[2].comparison.result_id


def test_known_comparison_failure_is_exit_six_and_preserves_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "audit.json"
    output.write_text("keep", encoding="utf-8")
    calls = 0

    class FailingComparator:
        def compare(self, result, policy):  # type: ignore[no-untyped-def]
            nonlocal calls
            calls += 1
            raise HistoricalExperimentRankingError("deliberate failure")

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("audit builder must not run")

    monkeypatch.setattr(historical_experiment, "_comparator_type", FailingComparator)
    monkeypatch.setattr(historical_experiment, "_audit_builder", forbidden)
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--output",
                str(output),
                "--overwrite",
            ]
        )
        == 6
    )
    captured = capsys.readouterr()
    assert calls == 1
    assert captured.out == ""
    assert "comparison failed" in captured.err
    assert output.read_text(encoding="utf-8") == "keep"
    assert not tuple(tmp_path.glob("*.tmp"))


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
