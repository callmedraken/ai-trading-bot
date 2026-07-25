import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from trading_bot.cli import coordinated_output, historical_experiment
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
from trading_bot.experiments import (
    HistoricalExperimentComparator,
    HistoricalExperimentGridGenerator,
    HistoricalExperimentGridSizeError,
    HistoricalExperimentRankingError,
    HistoricalExperimentReportBuilder,
    HistoricalExperimentReportError,
    HistoricalExperimentRunner,
)
from trading_bot.market_data import CoordinatingHistoricalDataProvider

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment.example.json"
PAIRWISE_POLICY = (
    ROOT / "examples" / "historical-experiment-pairwise-policy.example.json"
)
FIXTURES = ROOT / "tests" / "fixtures" / "cli"


def _raw() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _explicit_raw() -> dict:
    raw = _raw()
    first = deepcopy(raw["variant_grid"]["base_variant"])
    first["variant_id"] = "00000000-0000-0000-0000-000000000411"
    first["name"] = "Shorter Window"
    second = deepcopy(first)
    second["variant_id"] = "00000000-0000-0000-0000-000000000412"
    second["name"] = "Longer Window"
    second["rolling_window"]["observation_count"] = 4
    second["optimization"]["risk_aversion"] = "2"
    raw["variants"] = [first, second]
    raw["variant_grid"] = None
    return raw


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


def test_pairwise_policy_builds_one_private_report_and_retains_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_calls = 0
    comparison_calls = 0
    report_type = historical_experiment._report_builder_type
    comparator_type = historical_experiment._pairwise_comparator_type

    class CountingReportBuilder:
        def build(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal report_calls
            report_calls += 1
            return report_type().build(*args, **kwargs)

    class CountingPairwiseComparator:
        def compare(self, report, policy):  # type: ignore[no-untyped-def]
            nonlocal comparison_calls
            comparison_calls += 1
            return comparator_type().compare(report, policy)

    monkeypatch.setattr(
        historical_experiment, "_report_builder_type", CountingReportBuilder
    )
    monkeypatch.setattr(
        historical_experiment,
        "_pairwise_comparator_type",
        CountingPairwiseComparator,
    )
    run = historical_experiment.run_cli(
        EXAMPLE,
        collect_audit_records=False,
        pairwise_policy_path=PAIRWISE_POLICY,
    )
    assert report_calls == comparison_calls == 1
    assert run.compact_report is not None
    assert run.pairwise_result is not None
    assert run.pairwise_result.source_report_id == run.compact_report.report_id
    assert "Pairwise comparison:" in run.summary
    assert "record count: 3" in run.summary


def test_no_pairwise_behavior_preserves_lazy_report_path() -> None:
    run = historical_experiment.run_cli(EXAMPLE, collect_audit_records=False)
    assert run.compact_report is None
    assert run.pairwise_result is None
    assert "Pairwise comparison:" not in run.summary


def test_policy_only_mode_prints_summary_without_artifact_blocks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--pairwise-policy",
                str(PAIRWISE_POLICY),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Pairwise comparison:" in output
    assert "Compact report:" not in output
    assert "Pairwise artifacts:" not in output


def test_pairwise_destinations_join_normalized_collision_check(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "same.json"
    with pytest.raises(SystemExit) as caught:
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--pairwise-policy",
                str(PAIRWISE_POLICY),
                "--output",
                str(destination),
                "--pairwise-json",
                str(tmp_path / "." / "same.json"),
            ]
        )
    assert caught.value.code == 2
    assert "pairwise distinct" in capsys.readouterr().err


def test_checked_in_example_parses_exact_ordered_domain_models() -> None:
    config = load_historical_experiment_config(EXAMPLE)
    assert config.schema_version == 3
    assert config.ranking_policy is not None
    assert len(config.ranking_policy.criteria) == 2
    assert tuple(str(item) for item in config.historical_data.symbols) == (
        "SPY",
        "QQQ",
    )
    assert config.explicit_variants is None
    assert config.grid_specification is not None
    assert tuple(item.parameter.value for item in config.grid_specification.axes) == (
        "WINDOW_OBSERVATION_COUNT",
        "RISK_AVERSION",
    )


@pytest.mark.parametrize(
    ("mutate", "path"),
    (
        (lambda raw: raw.update(schema_version=2), "$.schema_version"),
        (lambda raw: raw.update(extra=True), "$.extra"),
        (lambda raw: raw.pop("initial_state"), "$.initial_state"),
        (
            lambda raw: raw["variant_grid"]["base_variant"].update(trading_enabled=1),
            "$.variant_grid.base_variant.trading_enabled",
        ),
        (
            lambda raw: raw["variant_grid"]["base_variant"]["optimization"].update(
                risk_aversion=1
            ),
            "$.variant_grid.base_variant.optimization.risk_aversion",
        ),
        (
            lambda raw: raw["variant_grid"]["base_variant"]["metadata"].append(
                {"key": "historical_experiment_bad", "value": "x"}
            ),
            "$.variant_grid.base_variant.metadata",
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
    raw = _explicit_raw()
    raw["rebalance_schedule"].append(raw["rebalance_schedule"][0])
    with pytest.raises(ConfigValidationError, match="strictly increasing"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _explicit_raw()
    raw["variants"][1]["variant_id"] = raw["variants"][0]["variant_id"]
    with pytest.raises(ConfigValidationError, match="variant IDs"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _explicit_raw()
    raw["variants"][1]["name"] = " shorter window "
    with pytest.raises(ConfigValidationError, match="variant names"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)


def test_initial_state_and_commission_compatibility_are_strict() -> None:
    raw = _raw()
    raw["initial_state"]["bootstrap_commission"] = "1"
    with pytest.raises(ConfigValidationError, match="exactly zero"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _explicit_raw()
    raw["variants"][0]["fills"]["fixed_commission"] = "1"
    with pytest.raises(ConfigValidationError, match="commissions must match"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)


def test_schema_two_rejection_has_migration_guidance() -> None:
    raw = _raw()
    raw["schema_version"] = 2
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == "$.schema_version"
    assert "version 3" in str(caught.value)


def test_ranking_is_required_and_null_is_supported() -> None:
    missing = _raw()
    missing.pop("ranking")
    explicit_null = _raw()
    explicit_null["ranking"] = None
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(missing, EXAMPLE.parent)
    assert caught.value.field_path == "$.ranking"
    second = parse_historical_experiment_config(explicit_null, EXAMPLE.parent)
    assert second.ranking_policy is None


def test_schema_three_explicit_and_grid_modes_are_mutually_exclusive() -> None:
    explicit = parse_historical_experiment_config(_explicit_raw(), EXAMPLE.parent)
    assert explicit.explicit_variants is not None
    assert explicit.grid_specification is None

    grid = parse_historical_experiment_config(_raw(), EXAMPLE.parent)
    assert grid.explicit_variants is None
    assert grid.grid_specification is not None

    raw = _raw()
    raw["variants"] = []
    with pytest.raises(ConfigValidationError, match="cannot be active"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _raw()
    raw["variants"] = None
    raw["variant_grid"] = None
    with pytest.raises(ConfigValidationError, match="exactly one"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    for field in ("variants", "variant_grid"):
        raw = _raw()
        raw.pop(field)
        with pytest.raises(ConfigValidationError) as caught:
            parse_historical_experiment_config(raw, EXAMPLE.parent)
        assert caught.value.field_path == f"$.{field}"

    raw = _explicit_raw()
    raw["variants"] = []
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == "$.variants"


@pytest.mark.parametrize(
    ("parameter", "value", "path"),
    (
        ("WINDOW_OBSERVATION_COUNT", True, "$.variant_grid.axes[0].values[0]"),
        ("WINDOW_OBSERVATION_COUNT", "3", "$.variant_grid.axes[0].values[0]"),
        ("SCENARIO_CASH_RETURN", 0, "$.variant_grid.axes[0].values[0]"),
        ("RISK_AVERSION", 1.0, "$.variant_grid.axes[0].values[0]"),
        ("PROPOSAL_CONFIDENCE", 1, "$.variant_grid.axes[0].values[0]"),
        ("TRADING_ENABLED", 1, "$.variant_grid.axes[0].values[0]"),
    ),
)
def test_grid_axis_values_use_parameter_specific_json_types(
    parameter: str, value: object, path: str
) -> None:
    raw = _raw()
    raw["variant_grid"]["axes"] = [{"parameter": parameter, "values": [value]}]
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == path


def test_grid_schema_rejects_unknown_search_fields_and_domain_errors() -> None:
    raw = _raw()
    raw["variant_grid"]["axes"][0]["start"] = 2
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == "$.variant_grid.axes[0].start"

    raw = _raw()
    raw["variant_grid"]["axes"][0]["values"] = [3, 3]
    with pytest.raises(ConfigValidationError, match="duplicate"):
        parse_historical_experiment_config(raw, EXAMPLE.parent)

    raw = _raw()
    raw["variant_grid"]["maximum_variant_count"] = True
    with pytest.raises(ConfigValidationError) as caught:
        parse_historical_experiment_config(raw, EXAMPLE.parent)
    assert caught.value.field_path == "$.variant_grid.maximum_variant_count"


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


def test_grid_generator_runs_once_before_provider_with_exact_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, object]] = []

    class RecordingGenerator:
        def __init__(self) -> None:
            events.append(("generator constructed", self))
            self.delegate = HistoricalExperimentGridGenerator()

        def generate(self, specification):  # type: ignore[no-untyped-def]
            events.append(("generate", specification))
            return self.delegate.generate(specification)

    class RecordingCoordinator:
        def __init__(self, provider):  # type: ignore[no-untyped-def]
            self.delegate = CoordinatingHistoricalDataProvider(provider)

        def get_bars(self, request):  # type: ignore[no-untyped-def]
            events.append(("provider", request))
            return self.delegate.get_bars(request)

    monkeypatch.setattr(
        historical_experiment, "_grid_generator_type", RecordingGenerator
    )
    monkeypatch.setattr(
        historical_experiment, "_coordinator_type", RecordingCoordinator
    )
    run = historical_experiment.run_cli(EXAMPLE)
    assert [item[0] for item in events] == [
        "generator constructed",
        "generate",
        "provider",
    ]
    assert events[1][1] is run.config.grid_specification
    assert run.grid_result is not None
    assert all(
        requested is generated.variant
        for requested, generated in zip(
            run.result.request.variants,
            run.grid_result.generated_variants,
            strict=True,
        )
    )


def test_explicit_mode_never_constructs_grid_generator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ForbiddenGenerator:
        def __init__(self) -> None:
            raise AssertionError("explicit mode must not construct a grid generator")

    monkeypatch.setattr(
        historical_experiment, "_grid_generator_type", ForbiddenGenerator
    )
    run = historical_experiment.run_cli(_write_config(tmp_path, _explicit_raw()))
    assert run.grid_result is None
    assert run.result.request.variants is run.config.explicit_variants
    assert run.comparison is not None
    assert run.summary == historical_experiment._format_summary(run.result) + (
        historical_experiment._format_ranked_summary(run.comparison)
    )


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
    assert run.grid_result is not None
    assert all(
        requested is generated.variant
        for requested, generated in zip(
            run.result.request.variants,
            run.grid_result.generated_variants,
            strict=True,
        )
    )
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
    assert len(records) == 4
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
    assert run.grid_result is not None
    grid_summary = historical_experiment._format_grid_summary(run.grid_result)
    assert summary.startswith(grid_summary + raw_summary)
    assert "generated variant count: 4" in grid_summary
    assert "1. WINDOW_OBSERVATION_COUNT: 3, 4" in grid_summary
    assert "2. RISK_AVERSION: 1, 2" in grid_summary
    assert "Ranking policy:" in summary
    assert "SIMULATION_RETURN: " in summary
    assert summary.index("SIMULATION_RETURN: ") < summary.index(
        "MAXIMUM_DRAWDOWN_PERCENTAGE: "
    )
    assert summary.index("variant 0 | Grid Base | WINDOW_OBSERVATION_COUNT=3") < (
        summary.index("variant 1 | Grid Base | WINDOW_OBSERVATION_COUNT=3")
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
        "variant_generation",
        "experiment",
        "comparison",
    }
    assert audit["schema_version"] == 3
    assert audit["configuration"]["ranking"] == audit["comparison"]["policy"]
    assert (
        audit["comparison"]["source_experiment_result_id"]
        == audit["experiment"]["result"]["result_id"]
    )
    assert len(audit["historical_data"]["frames"]) == 5
    runs = audit["experiment"]["result"]["runs"]
    assert [item["ordinal"] for item in runs] == [0, 1, 2, 3]
    assert len(audit["variant_generation"]["generated_variants"]) == 4
    assert "rolling_window" not in audit["variant_generation"]["generated_variants"][0]
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
            run.grid_result,
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
        (False, "historical-experiment-audit-v3-compact.json"),
        (True, "historical-experiment-audit-v3-pretty.json"),
    ),
)
def test_schema_three_audit_matches_exact_fixture(
    pretty: bool, fixture_name: str
) -> None:
    run = historical_experiment.run_cli(EXAMPLE)
    audit = build_historical_experiment_audit(
        run.config,
        run.grid_result,
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
    raw["ranking"] = None
    run = historical_experiment.run_cli(_write_config(tmp_path, raw))
    audit = build_historical_experiment_audit(
        run.config,
        run.grid_result,
        run.historical_data,
        run.result,
        run.comparison,
        run.factory.records,
    )
    assert audit["configuration"]["ranking"] is None
    assert audit["comparison"] is None


def test_explicit_audit_has_canonical_inactive_grid_source(tmp_path: Path) -> None:
    run = historical_experiment.run_cli(_write_config(tmp_path, _explicit_raw()))
    audit = build_historical_experiment_audit(
        run.config,
        run.grid_result,
        run.historical_data,
        run.result,
        run.comparison,
        run.factory.records,
    )
    assert audit["configuration"]["variants"] is not None
    assert audit["configuration"]["variant_grid"] is None
    assert audit["variant_generation"] is None


def test_schema_two_fixture_digest_sentinels() -> None:
    expected = {
        "historical-experiment-audit-v2-compact.json": (
            "81184169a75fc51914f4b6dd71b7f16daeb685d676371c28c3164e0ae199e92f"
        ),
        "historical-experiment-audit-v2-pretty.json": (
            "dd4b9d6e5a90918eb4af71b11ba50d1f340ace952b96e1b12c79cec16543f7b1"
        ),
    }
    for name, digest in expected.items():
        content = (FIXTURES / name).read_bytes()
        assert content.endswith(b"\n")
        assert sha256(content).hexdigest() == digest


def test_schema_three_preserves_raw_nested_section_shapes() -> None:
    legacy = json.loads(
        (FIXTURES / "historical-experiment-audit-v2-compact.json").read_text(
            encoding="utf-8"
        )
    )
    current = json.loads(
        (FIXTURES / "historical-experiment-audit-v3-compact.json").read_text(
            encoding="utf-8"
        )
    )
    assert current["historical_data"] == legacy["historical_data"]
    assert current["initial_state"] == legacy["initial_state"]
    assert set(current["experiment"]["request"]) == set(legacy["experiment"]["request"])
    assert set(current["experiment"]["result"]) == set(legacy["experiment"]["result"])
    assert set(current["experiment"]["result"]["runs"][0]) == set(
        legacy["experiment"]["result"]["runs"][0]
    )
    assert set(current["comparison"]) == set(legacy["comparison"])


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


def test_grid_identity_effects_are_isolated_from_raw_experiment(
    tmp_path: Path,
) -> None:
    raws = [_raw() for _ in range(8)]
    raws[1]["variant_grid"]["maximum_variant_count"] = 5
    raws[2]["variant_grid"]["metadata"] = [{"key": "purpose", "value": "changed"}]
    raws[3]["variant_grid"]["specification_id"] = "00000000-0000-0000-0000-000000000431"
    raws[4]["variant_grid"]["axes"].reverse()
    raws[5]["variant_grid"]["base_variant"]["scenario"]["source_name"] = (
        "changed-grid-base"
    )
    raws[6]["variant_grid"]["axes"][1]["values"] = ["1", "3"]
    raws[7]["variant_grid"]["axes"][1]["parameter"] = "SCENARIO_CASH_RETURN"
    runs = [
        historical_experiment.run_cli(
            _write_config(tmp_path / f"identity-{index}", raw)
        )
        for index, raw in enumerate(raws)
    ]
    assert all(run.grid_result is not None for run in runs)

    def generated_ids(run):  # type: ignore[no-untyped-def]
        return tuple(
            item.variant.variant_id for item in run.grid_result.generated_variants
        )

    baseline = runs[0]
    for changed in runs[1:3]:
        assert generated_ids(changed) == generated_ids(baseline)
        assert changed.grid_result.result_id != baseline.grid_result.result_id
        assert changed.result.result_id == baseline.result.result_id
        assert changed.comparison.result_id == baseline.comparison.result_id
    for changed in runs[3:]:
        assert generated_ids(changed) != generated_ids(baseline)
        assert changed.grid_result.result_id != baseline.grid_result.result_id
        assert changed.result.result_id != baseline.result.result_id
        assert changed.comparison.result_id != baseline.comparison.result_id


def test_grid_generation_failure_is_exit_six_before_provider_or_audit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("keep", encoding="utf-8")
    events: list[str] = []

    class FailingGenerator:
        def generate(self, specification):  # type: ignore[no-untyped-def]
            events.append("generate")
            raise HistoricalExperimentGridSizeError("deliberate grid failure")

    class ForbiddenCoordinator:
        def __init__(self, provider):  # type: ignore[no-untyped-def]
            raise AssertionError("historical provider must not be constructed")

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("audit builder must not run")

    monkeypatch.setattr(historical_experiment, "_grid_generator_type", FailingGenerator)
    monkeypatch.setattr(
        historical_experiment, "_coordinator_type", ForbiddenCoordinator
    )
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
    assert events == ["generate"]
    assert captured.out == ""
    assert "variant-grid generation failed" in captured.err
    assert output.read_text(encoding="utf-8") == "keep"
    assert not tuple(tmp_path.glob("*.tmp"))


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


@pytest.mark.parametrize(
    "arguments",
    (
        ("--compact-json", "compact.json"),
        ("--compact-csv", "compact.csv"),
        (
            "--compact-json",
            "compact.json",
            "--compact-csv",
            "compact.csv",
        ),
    ),
)
def test_compact_outputs_build_one_report_and_skip_full_audit(
    arguments: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = []
    original = HistoricalExperimentReportBuilder

    class RecordingBuilder:
        def build(
            self,
            experiment_result,
            *,
            grid_result,
            comparison_result,
            metadata,
        ):  # type: ignore[no-untyped-def]
            calls.append((experiment_result, grid_result, comparison_result, metadata))
            return original().build(
                experiment_result,
                grid_result=grid_result,
                comparison_result=comparison_result,
                metadata=metadata,
            )

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("full audit builder must not run")

    resolved = tuple(
        str(tmp_path / value) if value.endswith((".json", ".csv")) else value
        for value in arguments
    )
    monkeypatch.setattr(historical_experiment, "_report_builder_type", RecordingBuilder)
    monkeypatch.setattr(historical_experiment, "_audit_builder", forbidden)
    assert (
        historical_experiment.main(["--config", str(EXAMPLE), *resolved, "--quiet"])
        == 0
    )
    assert len(calls) == 1
    result, grid, comparison, metadata = calls[0]
    assert grid is not None
    assert comparison is not None
    assert comparison.experiment_result is result
    assert metadata == ()


def test_no_file_output_constructs_no_report_or_compact_serializer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ForbiddenBuilder:
        def __init__(self) -> None:
            raise AssertionError("compact report builder must not run")

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("compact serializer must not run")

    monkeypatch.setattr(historical_experiment, "_report_builder_type", ForbiddenBuilder)
    monkeypatch.setattr(historical_experiment, "_compact_json_serializer", forbidden)
    monkeypatch.setattr(historical_experiment, "_compact_csv_serializer", forbidden)
    assert historical_experiment.main(["--config", str(EXAMPLE), "--quiet"]) == 0


def test_full_only_constructs_no_compact_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class ForbiddenBuilder:
        def __init__(self) -> None:
            raise AssertionError("compact report builder must not run")

    monkeypatch.setattr(historical_experiment, "_report_builder_type", ForbiddenBuilder)
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--output",
                str(tmp_path / "audit.json"),
                "--quiet",
            ]
        )
        == 0
    )


def test_json_and_csv_serializers_reuse_exact_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen = []
    json_serializer = historical_experiment._compact_json_serializer
    csv_serializer = historical_experiment._compact_csv_serializer

    def json_recording(report, *, pretty):  # type: ignore[no-untyped-def]
        seen.append(("json", report))
        return json_serializer(report, pretty=pretty)

    def csv_recording(report):  # type: ignore[no-untyped-def]
        seen.append(("csv", report))
        return csv_serializer(report)

    monkeypatch.setattr(
        historical_experiment, "_compact_json_serializer", json_recording
    )
    monkeypatch.setattr(historical_experiment, "_compact_csv_serializer", csv_recording)
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--compact-json",
                str(tmp_path / "compact.json"),
                "--compact-csv",
                str(tmp_path / "compact.csv"),
                "--quiet",
            ]
        )
        == 0
    )
    assert [item[0] for item in seen] == ["json", "csv"]
    assert seen[0][1] is seen[1][1]


def test_normalized_duplicate_paths_are_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    destination = tmp_path / "same.json"
    with pytest.raises(SystemExit) as caught:
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--output",
                str(destination),
                "--compact-json",
                str(tmp_path / "." / "same.json"),
            ]
        )
    assert caught.value.code == 2
    assert "pairwise distinct" in capsys.readouterr().err


def test_all_destinations_are_preflighted_before_config_parsing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    existing = tmp_path / "existing.csv"
    existing.write_text("keep", encoding="utf-8")

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("config parsing must not run")

    monkeypatch.setattr(
        historical_experiment, "load_historical_experiment_config", forbidden
    )
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--compact-csv",
                str(existing),
            ]
        )
        == 7
    )
    assert "already exists" in capsys.readouterr().err
    assert existing.read_text(encoding="utf-8") == "keep"


def test_full_audit_is_byte_identical_with_compact_outputs(
    tmp_path: Path,
) -> None:
    full_only = tmp_path / "full-only.json"
    combined = tmp_path / "combined.json"
    assert (
        historical_experiment.main(
            ["--config", str(EXAMPLE), "--output", str(full_only), "--quiet"]
        )
        == 0
    )
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--output",
                str(combined),
                "--compact-json",
                str(tmp_path / "compact.json"),
                "--compact-csv",
                str(tmp_path / "compact.csv"),
                "--quiet",
            ]
        )
        == 0
    )
    assert full_only.read_bytes() == combined.read_bytes()
    audit = json.loads(combined.read_text(encoding="utf-8"))
    compact = json.loads((tmp_path / "compact.json").read_text(encoding="utf-8"))
    assert compact["report"]["metadata"] == []
    assert (
        compact["report"]["experiment_result_id"]
        == audit["experiment"]["result"]["result_id"]
    )
    assert [item["experiment_run_id"] for item in compact["report"]["variants"]] == [
        item["run_id"] for item in audit["experiment"]["result"]["runs"]
    ]
    assert [item["rolling_result_id"] for item in compact["report"]["variants"]] == [
        item["rolling"]["result"]["result_id"]
        for item in audit["experiment"]["result"]["runs"]
    ]
    assert (
        compact["report"]["grid_result_id"] == audit["variant_generation"]["result_id"]
    )
    assert (
        compact["report"]["ranking"]["comparison_result_id"]
        == audit["comparison"]["result_id"]
    )


def test_report_failure_is_exit_six_without_serialization_or_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "compact.json"

    class FailingBuilder:
        def build(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise HistoricalExperimentReportError("deliberate report failure")

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("serializer must not run")

    monkeypatch.setattr(historical_experiment, "_report_builder_type", FailingBuilder)
    monkeypatch.setattr(historical_experiment, "_compact_json_serializer", forbidden)
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--compact-json",
                str(destination),
            ]
        )
        == 6
    )
    assert not destination.exists()
    assert "compact report construction failed" in capsys.readouterr().err


def test_serialization_failure_preserves_every_destination(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    full = tmp_path / "full.json"
    compact = tmp_path / "compact.json"
    full.write_text("old full", encoding="utf-8")
    compact.write_text("old compact", encoding="utf-8")

    def failing(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        from trading_bot.cli.exceptions import (
            HistoricalExperimentReportOutputError,
        )

        raise HistoricalExperimentReportOutputError("deliberate serialization")

    monkeypatch.setattr(historical_experiment, "_compact_json_serializer", failing)
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--output",
                str(full),
                "--compact-json",
                str(compact),
                "--overwrite",
            ]
        )
        == 7
    )
    assert full.read_text(encoding="utf-8") == "old full"
    assert compact.read_text(encoding="utf-8") == "old compact"
    assert not tuple(tmp_path.glob("*.tmp"))
    assert "deliberate serialization" in capsys.readouterr().err


def test_staging_failure_preserves_destinations_and_cleans_temps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    full = tmp_path / "full.json"
    compact = tmp_path / "compact.json"
    full.write_text("old full", encoding="utf-8")
    compact.write_text("old compact", encoding="utf-8")

    def failing_fsync(descriptor):  # type: ignore[no-untyped-def]
        raise OSError("deliberate staging failure")

    monkeypatch.setattr(coordinated_output.os, "fsync", failing_fsync)
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--output",
                str(full),
                "--compact-json",
                str(compact),
                "--overwrite",
            ]
        )
        == 7
    )
    assert full.read_text(encoding="utf-8") == "old full"
    assert compact.read_text(encoding="utf-8") == "old compact"
    assert not tuple(tmp_path.glob("*.tmp"))
    assert "deliberate staging failure" in capsys.readouterr().err


def test_later_replacement_failure_keeps_earlier_replace_and_cleans_temps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    full = tmp_path / "full.json"
    compact = tmp_path / "compact.json"
    full.write_text("old full", encoding="utf-8")
    compact.write_text("old compact", encoding="utf-8")
    original_replace = coordinated_output.os.replace
    calls = 0

    def failing_second(source, destination):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("deliberate replacement failure")
        return original_replace(source, destination)

    monkeypatch.setattr(coordinated_output.os, "replace", failing_second)
    assert (
        historical_experiment.main(
            [
                "--config",
                str(EXAMPLE),
                "--output",
                str(full),
                "--compact-json",
                str(compact),
                "--overwrite",
            ]
        )
        == 7
    )
    assert json.loads(full.read_text(encoding="utf-8"))["schema_version"] == 3
    assert compact.read_text(encoding="utf-8") == "old compact"
    assert not tuple(tmp_path.glob("*.tmp"))
    assert "deliberate replacement failure" in capsys.readouterr().err
