"""CLI contract tests for the explicit authority command."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from trading_bot.cli import windows_authority
from trading_bot.runtime.windows_authority_provisioning import (
    ProvisioningEvidence,
    ProvisioningState,
)


def _evidence() -> ProvisioningEvidence:
    return ProvisioningEvidence(
        ProvisioningState.VALIDATED,
        r"F:\AITradingBot\Authority",
        "a" * 64,
        "test/v1",
        "S-1-5-21-100-200-300-400",
        ("root", "bootstrap"),
        False,
        False,
    )


def test_parser_has_explicit_validate_and_provision_modes() -> None:
    parser = windows_authority.build_parser()
    assert parser.parse_args(["validate"]).command == "validate"
    args = parser.parse_args(
        [
            "provision",
            "--bootstrap-source",
            "staging.bootstrap.json",
            "--signature-source",
            "staging.bootstrap.sig",
        ]
    )
    assert args.command == "provision"
    assert args.bootstrap_source == Path("staging.bootstrap.json")


def test_cli_emits_only_sanitized_evidence(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(windows_authority, "validate_installed_authority", _evidence)
    assert windows_authority.main(["validate"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["authority_root"] == r"F:\AITradingBot\Authority"
    assert output["bootstrap_digest"] == "a" * 64
    assert output["database_state"] == "NOT_PRESENT"
    assert set(output) == {
        "authority_root",
        "bootstrap_digest",
        "database_initialization",
        "database_present",
        "inspected_objects",
        "journal_present",
        "signing_key_id",
        "database_state",
        "state",
        "trading_sid",
    }


def test_source_checkout_script_help_is_cwd_and_package_root_independent(
    tmp_path: Path,
) -> None:
    alternate_root = tmp_path / "alternate-package"
    alternate_cli = alternate_root / "trading_bot" / "cli"
    alternate_cli.mkdir(parents=True)
    (alternate_root / "trading_bot" / "__init__.py").write_text("")
    (alternate_cli / "__init__.py").write_text("")
    (alternate_cli / "windows_authority.py").write_text(
        "def main(argv=None):\n    print('alternate package selected')\n    return 73\n"
    )
    away = tmp_path / "away-from-repository"
    away.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(alternate_root)
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / ("provision_windows_authority.py")
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
    assert "Validate or provision the fixed Windows trading authority." in (
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
    assert "Validate or provision the fixed Windows trading authority." in (
        package_selection.stdout
    )
    assert "alternate package selected" not in package_selection.stdout
