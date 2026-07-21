import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.run_backtest import _print_summary, build_parser

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "backtesting"


def command(*extra: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "scripts.run_backtest",
        "--csv-root",
        str(FIXTURES),
        "--symbol",
        "MATEST",
        "--start",
        "2026-01-02T05:00:00Z",
        "--end",
        "2026-01-16T05:00:00Z",
        "--short-window",
        "2",
        "--long-window",
        "3",
        "--quantity",
        "10",
        *extra,
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--start", "2026-01-02T00:00:00"],
        ["--quantity", "NaN"],
    ],
)
def test_argument_validation(arguments: list[str]) -> None:
    parser = build_parser()
    base = [
        "--csv-root",
        str(FIXTURES),
        "--symbol",
        "MATEST",
        "--start",
        "2026-01-02T05:00:00Z",
        "--end",
        "2026-01-16T05:00:00Z",
        "--short-window",
        "2",
        "--long-window",
        "3",
        "--quantity",
        "10",
    ]
    option = arguments[0]
    index = base.index(option)
    base[index + 1] = arguments[1]
    with pytest.raises(SystemExit):
        parser.parse_args(base)


def test_exact_module_invocation_runs_offline_and_prints_complete_summary() -> None:
    completed = subprocess.run(
        command(),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "symbol: MATEST" in completed.stdout
    assert "bars processed: 10" in completed.stdout
    assert "approved risk decision count: 2" in completed.stdout
    assert "resized risk decision count: 0" in completed.stdout
    assert "rejected risk decision count: 0" in completed.stdout
    assert "unexecuted end of data proposal count: 0" in completed.stdout
    assert "fill count: 2" in completed.stdout
    assert "final position: flat" in completed.stdout
    assert "closed trade count: 1" in completed.stdout
    assert "maximum drawdown amount:" in completed.stdout
    assert "profit factor: 0" in completed.stdout
    assert completed.stderr == ""


def test_json_report_has_deliberate_versioned_schema(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    subprocess.run(
        command("--json-report", str(output)),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert set(report) == {
        "schema_version",
        "configuration",
        "summary",
        "final_positions",
        "proposals",
        "risk_decisions",
        "fills",
        "equity_history",
        "performance",
    }
    assert report["schema_version"] == 2
    assert report["configuration"]["symbol"] == "MATEST"
    assert report["configuration"]["fixed_commission"] == "0"
    assert report["summary"]["approved_risk_decision_count"] == 2
    assert report["summary"]["unexecuted_end_of_data_proposal_count"] == 0
    assert len(report["proposals"]) == 2
    assert len(report["risk_decisions"]) == 2
    assert len(report["fills"]) == 2
    assert len(report["equity_history"]) == 10
    assert isinstance(report["equity_history"][0]["equity"], str)
    assert set(report["performance"]["drawdowns"]) == {
        "maximum_amount",
        "maximum_percentage",
    }
    assert report["performance"]["trade_statistics"]["closed_trade_count"] == 1
    assert report["performance"]["trade_statistics"]["profit_factor"] == "0"


def test_repeated_module_runs_are_deterministic() -> None:
    first = subprocess.run(
        command(), cwd=ROOT, check=True, capture_output=True, text=True
    )
    second = subprocess.run(
        command(), cwd=ROOT, check=True, capture_output=True, text=True
    )
    assert first.stdout == second.stdout


def test_console_distinguishes_undefined_profit_factor_reasons(capsys) -> None:  # type: ignore[no-untyped-def]
    base = {"final_position": None, "gross_profit": "0", "gross_loss": "0"}
    _print_summary({**base, "profit_factor": None})
    assert "undefined (no profit-or-loss activity)" in capsys.readouterr().out

    _print_summary({**base, "gross_profit": "1", "profit_factor": None})
    assert "undefined (no gross loss)" in capsys.readouterr().out
