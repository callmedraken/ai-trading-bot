"""CLI contract tests for the explicit authority command."""

from __future__ import annotations

import json
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
