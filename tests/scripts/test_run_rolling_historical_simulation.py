import subprocess
import sys
from pathlib import Path

import pytest

from trading_bot.cli import rolling_historical

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "rolling-historical-simulation.example.json"


def _command(*extra: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "scripts.run_rolling_historical_simulation",
        "--config",
        str(EXAMPLE),
        *extra,
    ]


def test_documented_repository_root_invocation_succeeds() -> None:
    completed = subprocess.run(
        _command(), cwd=ROOT, check=True, capture_output=True, text=True
    )
    assert "status: COMPLETED" in completed.stdout
    assert "historical frame count: 5" in completed.stdout
    assert "frame 1 | 2026-01-09T20:00:00+00:00" in completed.stdout
    assert completed.stderr == ""


@pytest.mark.parametrize(
    ("arguments", "message"),
    (
        (["--pretty"], "--pretty requires --output"),
        (["--overwrite"], "--overwrite requires --output"),
    ),
)
def test_dependent_arguments_are_usage_errors(
    arguments: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as caught:
        rolling_historical.main(["--config", str(EXAMPLE), *arguments])
    assert caught.value.code == 2
    assert message in capsys.readouterr().err


def test_required_config_and_unknown_flags_are_usage_errors() -> None:
    parser = rolling_historical.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(["--config", str(EXAMPLE), "--unknown"])
