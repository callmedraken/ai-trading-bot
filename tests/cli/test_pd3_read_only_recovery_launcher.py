"""Source-checkout launcher regression for the PD3 read-only recovery harness."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_pd3_read_only_recovery_launcher_is_cwd_and_package_root_independent(
    tmp_path: Path,
) -> None:
    alternate_root = tmp_path / "alternate-package"
    alternate_cli = alternate_root / "trading_bot" / "cli"
    alternate_cli.mkdir(parents=True)
    (alternate_root / "trading_bot" / "__init__.py").write_text("")
    (alternate_cli / "__init__.py").write_text("")
    (alternate_cli / "pd3_read_only_recovery_validation.py").write_text(
        "def main(argv=None):\n"
        "    print('alternate package selected')\n"
        "    return 73\n"
    )

    away = tmp_path / "away-from-repository"
    away.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(alternate_root)
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "validate_pd3_read_only_recovery.py"
    )

    completed = subprocess.run(
        [sys.executable, "-I", str(script), "--help"],
        cwd=away,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "Validate the frozen healthy PD3 recovery path without effects." in (
        completed.stdout
    )
    assert "alternate package selected" not in completed.stdout
    assert completed.stderr == ""

    package_selection = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=away,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert package_selection.returncode == 0
    assert "Validate the frozen healthy PD3 recovery path without effects." in (
        package_selection.stdout
    )
    assert "alternate package selected" not in package_selection.stdout
    assert package_selection.stderr == ""
