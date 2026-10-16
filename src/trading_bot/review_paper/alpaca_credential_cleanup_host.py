"""Protected D1R4R incident cleanup host; import/help perform no effects."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trading_bot.review_paper.alpaca_authentication_host import (
    admit_authentication_evidence,
    admit_authentication_source,
)
from trading_bot.review_paper.alpaca_credential_generation import GenerationError
from trading_bot.review_paper.alpaca_credential_native import (
    WindowsV3CredentialStore,
    WindowsV3Exclusion,
)
from trading_bot.review_paper.alpaca_credential_staging_cleanup import (
    CLEANUP_LATCH,
    INCIDENT_BYTES,
    INCIDENT_JOURNAL,
    operate_cleanup,
    reserve_cleanup,
)
from trading_bot.review_paper.alpaca_windows_credentials import (
    read_fixed_current_product_credential,
)

CLEANUP_INTERLOCK = "CLEANUP_ARCH134_D1R4R_ONE_EXACT_PRE_PROVIDER_V3_PAIR"


class WindowsIncidentCleanupStore:
    """Only fixed reads/deletes are exposed; no credential write surface."""

    def read(self, target: str) -> bytearray | None:
        return read_fixed_current_product_credential(target, cleanup_metadata=True)

    def delete(self, target: str) -> bool:
        return WindowsV3CredentialStore().delete(target)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise GenerationError("invalid incident cleanup arguments")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="D1R4R protected exact incident pair cleanup")
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--preserved-evidence", required=True, type=Path)
    parser.add_argument("--cleanup-v3", required=True, choices=(CLEANUP_INTERLOCK,))
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        roots = admit_authentication_source(args.expected_head, args.expected_tree)
        admit_authentication_evidence(CLEANUP_LATCH, roots)
        path = args.preserved_evidence
        if (
            not path.is_absolute()
            or path.is_symlink()
            or not path.is_file()
            or path.resolve() != INCIDENT_JOURNAL.resolve()
            or path.stat().st_nlink != 1
        ):
            raise GenerationError("preserved incident artifact unavailable")
        admit_authentication_evidence(
            path.parent / (path.name + ".read-check.json"), roots
        )
        # This fixed latch is consumed even if later admission fails. No output flag.
        with reserve_cleanup(args.expected_head, args.expected_tree) as journal:

            def load_preserved() -> bytes:
                if path.is_symlink() or path.stat().st_nlink != 1:
                    raise GenerationError("preserved incident identity changed")
                admit_authentication_evidence(
                    path.parent / (path.name + ".read-check.json"), roots
                )
                with path.open("rb") as source:
                    return source.read(INCIDENT_BYTES + 1)

            outcome = operate_cleanup(
                load_preserved=load_preserved,
                store=WindowsIncidentCleanupStore(),
                mutex=WindowsV3Exclusion(),
                journal=journal,
                admit_source=lambda: admit_authentication_source(
                    args.expected_head, args.expected_tree
                ),
            )
        print(outcome)
        return 0 if outcome == "CLEANUP_EXACT_PAIR_REMOVED" else 1
    except (Exception, KeyboardInterrupt):
        print("ALPACA_V3_INCIDENT_CLEANUP_BLOCKED_REVIEW_REQUIRED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
