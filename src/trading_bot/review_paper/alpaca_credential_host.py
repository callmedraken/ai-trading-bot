"""D1R4 protected interactive provisioning and separate read-only reconciliation."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import sys
import warnings
from pathlib import Path

from trading_bot.review_paper.alpaca_authentication_host import (
    admit_authentication_evidence,
    admit_authentication_source,
)
from trading_bot.review_paper.alpaca_credential_generation import (
    MAX_JOURNAL_BYTES,
    GenerationError,
    GenerationJournal,
    clear_credential,
    operate_generation,
    parse_generation_journal,
    validate_fresh_credential_pair,
)
from trading_bot.review_paper.alpaca_credential_native import (
    WindowsV3CredentialStore,
    WindowsV3Exclusion,
)

PROVISION_INTERLOCK = "PROVISION_ARCH134_D1R4_ONE_FRESH_V3_GENERATION"
RECONCILE_INTERLOCK = "RECONCILE_ARCH134_D1R4_V3_READ_ONLY"
LENGTH_CONFIRMATION = "CONFIRM_LENGTHS_MATCH_INTENDED_FRESH_DASHBOARD_GENERATION"
STAGING_CONFIRMATION = "NO_V3_PROVIDER_EFFECT_AND_NO_OUT_OF_BAND_CREDENTIAL_WRITERS"


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise GenerationError("invalid generation arguments")


def interactive_generation_pair() -> tuple[bytearray, bytearray]:
    """Real terminal only; suppress getpass's unsafe echo fallback."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise GenerationError("local interactive terminal required")
    # The staging assertion is human authority material, not a bypassable flag.
    if input("Confirm staging/exclusion contract: ") != STAGING_CONFIRMATION:
        raise GenerationError("staging/exclusion confirmation required")
    values = []
    repeats = []
    failed = False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            for prompt in ("Dashboard key ID: ", "Dashboard secret: "):
                values.append(bytearray(getpass.getpass(prompt).encode("utf-8")))
                repeats.append(
                    bytearray(getpass.getpass("Repeat " + prompt).encode("utf-8"))
                )
        pair = tuple(values)
        validate_fresh_credential_pair(pair)
        if values != repeats:
            raise GenerationError("fresh credential repeated entry mismatch")
        print(f"Fresh UTF-8 lengths: key={len(values[0])}, secret={len(values[1])}")
        if input("Confirm intended dashboard lengths: ") != LENGTH_CONFIRMATION:
            raise GenerationError("fresh credential length confirmation required")
    except BaseException:
        failed = True
    finally:
        for value in repeats:
            clear_credential(value)
        if failed:
            for value in values:
                clear_credential(value)
    if failed:
        raise GenerationError("fresh interactive credential input rejected")
    return pair


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        description="D1R4 fixed v3 provisioning/reconciliation preparation"
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--provision-v3", choices=(PROVISION_INTERLOCK,))
    mode.add_argument("--reconcile-v3", choices=(RECONCILE_INTERLOCK,))
    parser.add_argument("--preserved-evidence", type=Path)
    parser.add_argument("--preserved-sha256")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        roots = admit_authentication_source(args.expected_head, args.expected_tree)
        destination = admit_authentication_evidence(args.evidence, roots)
        preserved = None
        if args.reconcile_v3:
            path = args.preserved_evidence
            if path is None or not path.is_absolute() or path.is_symlink():
                raise GenerationError("preserved evidence required")
            # Reuse fresh destination admission to validate all external ancestors.
            admit_authentication_evidence(
                path.parent / (path.name + ".read-check.json"), roots
            )
            with path.open("rb") as source:
                payload = source.read(MAX_JOURNAL_BYTES + 1)
            if hashlib.sha256(payload).hexdigest() != args.preserved_sha256:
                raise GenerationError("preserved generation digest mismatch")
            preserved = parse_generation_journal(payload)
        elif args.preserved_evidence is not None or args.preserved_sha256 is not None:
            raise GenerationError("provisioning cannot adopt existing evidence")
        with destination.open("xb") as output:
            result = operate_generation(
                store=WindowsV3CredentialStore(),
                mutex=WindowsV3Exclusion(),
                journal=GenerationJournal(
                    output, args.expected_head, args.expected_tree
                ),
                admit_source=lambda: admit_authentication_source(
                    args.expected_head, args.expected_tree
                ),
                interactive_pair=interactive_generation_pair,
                preserved=preserved,
            )
        print(result)
        return (
            0
            if result
            in {"LOCAL_EXACT_MATCH", "RECONCILED_ABSENT", "RECONCILED_PAIR_MATCH"}
            else 1
        )
    except (Exception, KeyboardInterrupt):
        print("ALPACA_V3_GENERATION_HOST_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
