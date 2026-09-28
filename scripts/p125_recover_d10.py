"""Explicit protected P125-R1G D10 recovery operator; inert at import."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Protocol

from scripts import d10_protected_replacement as replacement
from scripts.p125_replace_d10 import RenameOperations, run_admitted_replacement


class RecoveryOperations(RenameOperations, Protocol):
    def validate_recovery_material(self, repository_root: Path) -> None: ...


EXPECTED_R1G_TRANSPORT_GENERATION = "P125-R1G/WIN32_FILE_RENAME_INFO_3/R_R/v1"


def run_recovery(
    repository_root: Path, operations: RecoveryOperations
) -> replacement.ReplacementResult:
    """Fence the consumed R1G authority before any observation or effect."""
    from scripts import d10_protected_replacement_windows as windows

    if windows.RENAME_TRANSPORT_GENERATION != EXPECTED_R1G_TRANSPORT_GENERATION:
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            replacement.NamespaceState.CONFLICTING,
            reason_code=replacement.BlockReason.NAMESPACE_CONFLICT,
        )
    return run_admitted_recovery(repository_root, operations)


def run_admitted_recovery(
    repository_root: Path, operations: RecoveryOperations
) -> replacement.ReplacementResult:
    """Admit only fresh exact OLD_CANONICAL under separate recovery authority."""
    try:
        state = replacement.classify_namespace(operations.observe_namespace())
    except Exception:
        state = replacement.NamespaceState.CONFLICTING
    if state is not replacement.NamespaceState.OLD_CANONICAL:
        reason = (
            replacement.BlockReason.SEPARATE_RECOVERY_REQUIRED
            if state
            in (
                replacement.NamespaceState.OLD_RETIRED,
                replacement.NamespaceState.NEW_CANONICAL,
            )
            else replacement.BlockReason.NAMESPACE_CONFLICT
            if state is replacement.NamespaceState.CONFLICTING
            else replacement.BlockReason.ADMISSION_FAILED
        )
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED, state, reason_code=reason
        )
    try:
        operations.validate_recovery_material(repository_root)
    except Exception:
        return replacement.ReplacementResult(
            replacement.Phase.BLOCKED,
            state,
            reason_code=replacement.BlockReason.ADMISSION_FAILED,
        )
    return run_admitted_replacement(operations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument(
        "--execute-protected-p125-r1g-recovery",
        action="store_true",
        help="explicitly run the Administrator-only protected recovery attempt",
    )
    arguments = parser.parse_args(argv)
    if not arguments.execute_protected_p125_r1g_recovery:
        parser.error(
            "P125-R1G remains inert without --execute-protected-p125-r1g-recovery"
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
