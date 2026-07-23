import subprocess
import sys
from pathlib import Path

import pytest

from trading_bot.cli import historical_experiment

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "historical-experiment.example.json"


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
    assert "variant 0 | Shorter Window" in completed.stdout
    assert "variant 1 | Longer Window" in completed.stdout
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
        historical_experiment.main(["--config", str(EXAMPLE), *arguments])
    assert caught.value.code == 2
    assert message in capsys.readouterr().err


def test_required_config_is_a_usage_error() -> None:
    with pytest.raises(SystemExit):
        historical_experiment.build_parser().parse_args([])
