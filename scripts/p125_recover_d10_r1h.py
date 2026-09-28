"""Explicit protected P125-R1H D10 recovery operator; inert at import."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts import d10_protected_replacement as replacement
from scripts.p125_recover_d10 import RecoveryOperations, run_admitted_recovery

EXPECTED_R1H_E_TRANSPORT_GENERATION = (
    "P125-R1H-E/NT_FILE_RENAME_INFORMATION_10/R_RWD/v1"
)


def run_recovery(
    repository_root: Path, operations: RecoveryOperations
) -> replacement.ReplacementResult:
    """Use only the frozen transport and reviewed OLD_CANONICAL recovery."""
    from scripts import d10_protected_replacement_windows as windows

    if windows.RENAME_TRANSPORT_GENERATION != EXPECTED_R1H_E_TRANSPORT_GENERATION:
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            replacement.NamespaceState.CONFLICTING,
            reason_code=replacement.BlockReason.NAMESPACE_CONFLICT,
        )
    return run_admitted_recovery(repository_root, operations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument(
        "--execute-protected-p125-r1h-recovery",
        action="store_true",
        help="explicitly run the Administrator-only protected recovery attempt",
    )
    arguments = parser.parse_args(argv)
    if not arguments.execute_protected_p125_r1h_recovery:
        parser.error(
            "P125-R1H remains inert without --execute-protected-p125-r1h-recovery"
        )

    from scripts import d10_protected_replacement_windows as windows

    try:
        result = run_recovery(arguments.repository_root, windows)
    except Exception:
        result = replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            replacement.NamespaceState.CONFLICTING,
            reason_code=replacement.BlockReason.NAMESPACE_CONFLICT,
        )
    sys.stdout.buffer.write(result.canonical_transcript())
    return 0 if result.phase is replacement.Phase.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
