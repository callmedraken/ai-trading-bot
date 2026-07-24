import json
import subprocess
import sys
from pathlib import Path

import pytest

from trading_bot.cli import historical_experiment

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment.example.json"
PAIRWISE_POLICY = (
    ROOT / "examples" / "historical-experiment-pairwise-policy.example.json"
)


def _command(*extra: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "scripts.run_historical_experiment",
        "--config",
        str(EXAMPLE),
        *extra,
    ]


def test_documented_repository_root_invocation_succeeds() -> None:
    completed = subprocess.run(
        _command(), cwd=ROOT, check=True, capture_output=True, text=True
    )
    assert "experiment result ID:" in completed.stdout
    assert "Variant grid:" in completed.stdout
    assert "generated variant count: 4" in completed.stdout
    assert "variant 0 | Grid Base | WINDOW_OBSERVATION_COUNT=3" in completed.stdout
    assert "variant 3 | Grid Base | WINDOW_OBSERVATION_COUNT=4" in completed.stdout
    assert "Ranking policy:" in completed.stdout
    assert "Ranked comparison:" in completed.stdout
    assert completed.stderr == ""


@pytest.mark.parametrize(
    ("arguments", "message"),
    (
        (["--pretty"], "--pretty requires --output"),
        (["--compact-json-pretty"], "--compact-json-pretty requires --compact-json"),
        (["--pairwise-json", "x.json"], "--pairwise-json requires --pairwise-policy"),
        (["--pairwise-csv", "x.csv"], "--pairwise-csv requires --pairwise-policy"),
        (
            ["--pairwise-json-pretty"],
            "--pairwise-json-pretty requires --pairwise-json",
        ),
        (["--overwrite"], "--overwrite requires an output destination"),
    ),
)
def test_dependent_arguments_are_usage_errors(
    arguments: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as caught:
        historical_experiment.main(["--config", str(EXAMPLE), *arguments])
    assert caught.value.code == 2
    assert message in capsys.readouterr().err


def test_required_config_is_a_usage_error() -> None:
    with pytest.raises(SystemExit):
        historical_experiment.build_parser().parse_args([])


def test_documented_compact_output_invocation_succeeds(tmp_path: Path) -> None:
    compact_json = tmp_path / "compact.json"
    compact_csv = tmp_path / "compact.csv"
    completed = subprocess.run(
        _command(
            "--compact-json",
            str(compact_json),
            "--compact-json-pretty",
            "--compact-csv",
            str(compact_csv),
        ),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Compact report:" in completed.stdout
    assert f"  JSON: {compact_json.resolve()}" in completed.stdout
    assert f"  CSV: {compact_csv.resolve()}" in completed.stdout
    assert json.loads(compact_json.read_text(encoding="utf-8"))["schema_version"] == 1
    assert compact_csv.read_text(encoding="utf-8").startswith("report_id,")


def test_documented_pairwise_output_invocation_succeeds(tmp_path: Path) -> None:
    pairwise_json = tmp_path / "pairwise.json"
    pairwise_csv = tmp_path / "pairwise.csv"
    completed = subprocess.run(
        _command(
            "--pairwise-policy",
            str(PAIRWISE_POLICY),
            "--pairwise-json",
            str(pairwise_json),
            "--pairwise-json-pretty",
            "--pairwise-csv",
            str(pairwise_csv),
        ),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Pairwise comparison:" in completed.stdout
    assert "  record count: 3" in completed.stdout
    assert "Compact report:" not in completed.stdout
    assert "Pairwise artifacts:" in completed.stdout
    assert f"  JSON: {pairwise_json.resolve()}" in completed.stdout
    assert f"  CSV: {pairwise_csv.resolve()}" in completed.stdout
    assert json.loads(pairwise_json.read_text(encoding="utf-8"))["schema_version"] == 1
    assert pairwise_csv.read_text(encoding="utf-8").startswith("pairwise_result_id,")
