import json
import subprocess
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.cli import optimized_simulation
from trading_bot.cli.config import load_config, parse_config
from trading_bot.cli.exceptions import (
    AuditOutputError,
    ConfigValidationError,
)
from trading_bot.cli.serialization import build_audit, write_atomic
from trading_bot.portfolio import OptimizationStatus
from trading_bot.simulation import (
    OptimizedPaperSimulationOptimizationError,
    PaperPortfolioSimulationCycleError,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "optimized-paper-simulation.example.json"


def _raw() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _write_config(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _command(*extra: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "scripts.run_optimized_paper_simulation",
        "--config",
        str(EXAMPLE),
        *extra,
    ]


def test_checked_in_example_parses_and_runs_from_repository_root() -> None:
    config = load_config(EXAMPLE)
    assert config.schema_version == 1
    assert tuple(str(item.symbol) for item in config.request.frames[0].prices) == (
        "SPY",
        "QQQ",
    )
    completed = subprocess.run(
        _command(), cwd=ROOT, check=True, capture_output=True, text=True
    )
    assert "status: COMPLETED" in completed.stdout
    assert "frame 0: 2026-07-21T20:00:00+00:00" in completed.stdout
    assert "optimization: OPTIMAL" in completed.stdout
    assert completed.stderr == ""


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--pretty"], "--pretty requires --output"),
        (["--overwrite"], "--overwrite requires --output"),
    ],
)
def test_dependent_arguments_are_usage_errors(
    arguments: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as caught:
        optimized_simulation.main(["--config", str(EXAMPLE), *arguments])
    assert caught.value.code == 2
    assert message in capsys.readouterr().err


def test_required_config_and_unknown_flags_are_argparse_errors() -> None:
    parser = optimized_simulation.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(["--config", str(EXAMPLE), "--unknown"])


@pytest.mark.parametrize(
    ("mutate", "path"),
    [
        (lambda raw: raw.update(schema_version=2), "$.schema_version"),
        (lambda raw: raw.update(extra=True), "$.extra"),
        (lambda raw: raw.pop("frames"), "$.frames"),
        (
            lambda raw: raw.update(simulation_request_id="not-a-uuid"),
            "$.simulation_request_id",
        ),
        (
            lambda raw: raw["initial_ledger"].update(as_of="2026-07-21T19:00:00"),
            "$.initial_ledger.as_of",
        ),
        (
            lambda raw: raw["frames"][0]["scenarios"].update(source="manual"),
            "$.frames[0].scenarios.source",
        ),
        (
            lambda raw: raw["frames"][0]["prices"][0].update(risk_price=500),
            "$.frames[0].prices[0].risk_price",
        ),
        (
            lambda raw: raw["frames"][0]["prices"][0].update(risk_price="5e2"),
            "$.frames[0].prices[0].risk_price",
        ),
        (
            lambda raw: raw["frames"][0]["prices"][0].update(risk_price="NaN"),
            "$.frames[0].prices[0].risk_price",
        ),
    ],
)
def test_strict_schema_errors_retain_json_paths(mutate, path: str) -> None:  # type: ignore[no-untyped-def]
    raw = _raw()
    mutate(raw)
    with pytest.raises(ConfigValidationError) as caught:
        parse_config(raw)
    assert caught.value.field_path == path


def test_ordered_universe_mismatch_is_rejected() -> None:
    raw = _raw()
    raw["frames"][0]["expected_returns"].reverse()
    with pytest.raises(ConfigValidationError, match="price order"):
        parse_config(raw)


def test_invalid_scenario_and_commission_policy_use_domain_validation() -> None:
    scenario = _raw()
    scenario["frames"][0]["scenarios"]["rows"][0]["probability"] = "0.40"
    with pytest.raises(ConfigValidationError, match="sum exactly to one"):
        parse_config(scenario)
    commission = _raw()
    commission["frames"][0]["fill_policy"]["fixed_commission"] = "1"
    with pytest.raises(ConfigValidationError, match="commissions must match"):
        parse_config(commission)


def test_cash_only_rejects_positions_and_empty_zero_cash() -> None:
    raw = _raw()
    raw["initial_ledger"]["positions"] = [
        {"symbol": "SPY", "quantity": "1", "average_cost": "100"}
    ]
    with pytest.raises(ConfigValidationError, match="CASH_ONLY"):
        parse_config(raw)
    raw = _raw()
    raw["initial_ledger"]["available_cash"] = "0"
    with pytest.raises(ConfigValidationError, match="cannot initialize"):
        parse_config(raw)


@pytest.mark.parametrize("field", ["quantity", "average_cost"])
def test_bootstrap_positions_require_positive_values(field: str) -> None:
    raw = _raw()
    raw["initial_ledger"]["initialization_mode"] = "BOOTSTRAP_FILLS"
    raw["initial_ledger"]["positions"] = [
        {"symbol": "SPY", "quantity": "1", "average_cost": "100"}
    ]
    raw["initial_ledger"]["positions"][0][field] = "0"
    with pytest.raises(ConfigValidationError) as caught:
        parse_config(raw)
    assert caught.value.field_path == f"$.initial_ledger.positions[0].{field}"


def test_bootstrap_fills_construct_exact_deterministic_opening_state() -> None:
    raw = _raw()
    raw["initial_ledger"].update(
        initialization_mode="BOOTSTRAP_FILLS",
        available_cash="1000",
        positions=[
            {"symbol": "SPY", "quantity": "2", "average_cost": "100"},
            {"symbol": "QQQ", "quantity": "3", "average_cost": "50"},
        ],
    )
    config = parse_config(raw)
    first_ledger, first_fills = optimized_simulation._initialize_ledger(config)
    second_ledger, second_fills = optimized_simulation._initialize_ledger(config)
    assert first_fills == second_fills
    assert first_fills[0].order_id != first_fills[0].fill_id
    assert tuple(first_ledger.fills) == first_fills
    assert first_ledger.cash == Decimal("1000")
    assert first_ledger.positions == second_ledger.positions
    assert first_ledger.positions[first_fills[0].symbol].average_cost == Decimal("100")


def test_bootstrap_audit_classifies_opening_and_simulation_fills(
    tmp_path: Path,
) -> None:
    raw = _raw()
    raw["initial_ledger"].update(
        initialization_mode="BOOTSTRAP_FILLS",
        available_cash="1000",
        positions=[{"symbol": "SPY", "quantity": "1", "average_cost": "400"}],
    )
    run = optimized_simulation.run_cli(_write_config(tmp_path, raw))
    audit = build_audit(run.config, run.result, run.ledger, run.bootstrap_fills)
    assert [item["origin"] for item in audit["initial_state"]["bootstrap_fills"]] == [
        "INITIAL_POSITION_BOOTSTRAP"
    ]
    origins = [item["origin"] for item in audit["final_state"]["ledger_fills"]]
    assert origins[0] == "INITIAL_POSITION_BOOTSTRAP"
    assert all(item["origin"] == "SIMULATION" for item in audit["frames"][0]["fills"])


def test_multi_frame_and_no_action_runs(tmp_path: Path) -> None:
    multi = _raw()
    second = deepcopy(multi["frames"][0])
    second["as_of"] = "2026-07-22T20:00:00+00:00"
    second["submitted_at"] = "2026-07-22T20:01:00+00:00"
    second["filled_at"] = "2026-07-22T20:02:00+00:00"
    second["scenarios"]["scenario_set_id"] = "00000000-0000-0000-0000-000000000102"
    second["scenarios"]["rows"][0]["scenario_id"] = (
        "00000000-0000-0000-0000-000000000203"
    )
    second["scenarios"]["rows"][1]["scenario_id"] = (
        "00000000-0000-0000-0000-000000000204"
    )
    multi["frames"].append(second)
    result = optimized_simulation.run_cli(_write_config(tmp_path, multi)).result
    assert len(result.evaluations) == 2

    no_action = _raw()
    no_action["frames"][0]["optimization"]["risk_aversion"] = "1"
    result = optimized_simulation.run_cli(_write_config(tmp_path, no_action)).result
    assert result.status.value == "NO_ACTION"


def test_infeasible_optimizer_maps_to_exit_five_without_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = _raw()
    raw["frames"][0]["optimization"]["minimum_expected_return"] = "1"
    config = _write_config(tmp_path, raw)
    output = tmp_path / "audit.json"
    assert (
        optimized_simulation.main(
            ["--config", str(config), "--output", str(output), "--quiet"]
        )
        == 5
    )
    assert "status=INFEASIBLE" in capsys.readouterr().err
    assert not output.exists()


def test_compact_and_pretty_outputs_repeat_byte_for_byte(tmp_path: Path) -> None:
    for pretty in (False, True):
        first = tmp_path / f"first-{pretty}.json"
        second = tmp_path / f"second-{pretty}.json"
        suffix = ["--pretty"] if pretty else []
        subprocess.run(
            _command("--output", str(first), "--quiet", *suffix),
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            _command("--output", str(second), "--quiet", *suffix),
            cwd=ROOT,
            check=True,
        )
        assert first.read_bytes() == second.read_bytes()
        report = json.loads(first.read_text(encoding="utf-8"))
        assert report["schema_version"] == 1
        assert report["configuration"]["frames"][0]["scenarios"]["symbols"] == [
            "SPY",
            "QQQ",
        ]
        assert isinstance(report["final_state"]["cash"], str)
        assert report["frames"][0]["optimization"]["status"] == "OPTIMAL"


def test_output_collision_and_overwrite_behavior(tmp_path: Path) -> None:
    output = tmp_path / "audit.json"
    output.write_text("old", encoding="utf-8")
    rejected = subprocess.run(
        _command("--output", str(output), "--quiet"),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 7
    assert output.read_text(encoding="utf-8") == "old"
    subprocess.run(
        _command("--output", str(output), "--overwrite", "--quiet"),
        cwd=ROOT,
        check=True,
    )
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == 1


def test_atomic_replace_failure_preserves_destination_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "audit.json"
    output.write_text("old", encoding="utf-8")

    def fail_replace(source, destination):  # type: ignore[no-untyped-def]
        raise OSError("forced")

    monkeypatch.setattr("trading_bot.cli.serialization.os.replace", fail_replace)
    with pytest.raises(AuditOutputError, match="forced"):
        write_atomic(output, "new", overwrite=True)
    assert output.read_text(encoding="utf-8") == "old"
    assert tuple(tmp_path.glob("*.tmp")) == ()


@pytest.mark.parametrize(
    ("error", "exit_code", "expected"),
    [
        (
            OptimizedPaperSimulationOptimizationError(
                0,
                "optimizer failed",
                status=OptimizationStatus.UNAVAILABLE,
                diagnostic_codes=("SCIPY_UNAVAILABLE",),
            ),
            5,
            'pip install -e ".[optimization-cpu]"',
        ),
        (PaperPortfolioSimulationCycleError(0, "runtime failed"), 6, "frame 0"),
    ],
)
def test_known_simulation_failures_map_to_stable_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    exit_code: int,
    expected: str,
) -> None:
    class FailedSimulator:
        def __init__(self, runtime):  # type: ignore[no-untyped-def]
            self.runtime = runtime

        def run(self, request):  # type: ignore[no-untyped-def]
            raise error

    output = tmp_path / "should-not-exist.json"
    monkeypatch.setattr(optimized_simulation, "_simulator_type", FailedSimulator)
    assert (
        optimized_simulation.main(
            ["--config", str(EXAMPLE), "--output", str(output), "--quiet"]
        )
        == exit_code
    )
    assert expected in capsys.readouterr().err
    assert not output.exists()


def test_configuration_input_is_not_mutated() -> None:
    raw = _raw()
    original = deepcopy(raw)
    parse_config(raw)
    assert raw == original
