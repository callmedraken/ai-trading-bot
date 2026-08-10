"""Administrator-only validation/provisioning command for the fixed authority."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trading_bot.runtime.windows_authority import WindowsAuthorityError
from trading_bot.runtime.windows_authority_provisioning import (
    ProvisioningEvidence,
    provision_authority,
    validate_installed_authority,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit validate/provision parser."""

    parser = argparse.ArgumentParser(
        description="Validate or provision the fixed Windows trading authority."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="validate the installed authority read-only")
    provision = commands.add_parser("provision", help="install staged trust material")
    provision.add_argument("--bootstrap-source", required=True, type=Path)
    provision.add_argument("--signature-source", required=True, type=Path)
    return parser


def _evidence_json(evidence: ProvisioningEvidence) -> str:
    return json.dumps(
        {
            "authority_root": evidence.authority_root,
            "bootstrap_digest": evidence.bootstrap_digest,
            "database_initialization": evidence.database_initialization,
            "database_present": evidence.database_present,
            "inspected_objects": list(evidence.inspected_objects),
            "journal_present": evidence.journal_present,
            "signing_key_id": evidence.signing_key_id,
            "database_state": evidence.database_state,
            "state": evidence.state.value,
            "trading_sid": evidence.trading_sid,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def main(argv: list[str] | None = None) -> int:
    """Run one explicit administrator operation without self-elevation."""

    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            evidence = validate_installed_authority()
        else:
            evidence = provision_authority(
                bootstrap_source=args.bootstrap_source,
                signature_source=args.signature_source,
            )
    except WindowsAuthorityError as error:
        # Deliberately emit only the typed failure class, not native text,
        # paths outside the fixed deployment, or arbitrary exception details.
        print(f"authority operation blocked: {type(error).__name__}", file=sys.stderr)
        return 8
    print(_evidence_json(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
