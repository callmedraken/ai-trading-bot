"""Read-only command adapter for deterministic full-lineage verification."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from trading_bot.cli.checkpoint_lineage_config import (
    PaperAccountLineageManifestReadError,
    PaperAccountLineageManifestSyntaxError,
    PaperAccountLineageManifestValidationError,
    load_paper_account_lineage_manifest,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.runtime import (
    PaperAccountLineageVerificationResult,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)


@dataclass(frozen=True, slots=True)
class VerifyPaperAccountLineageCommandResult:
    verification: PaperAccountLineageVerificationResult


def verify_lineage_manifest(
    manifest_path: Path,
) -> VerifyPaperAccountLineageCommandResult:
    """Load and verify one explicitly enumerated lineage without side effects."""
    manifest = load_paper_account_lineage_manifest(manifest_path)
    verification = verify_paper_account_lineage(
        manifest.genesis_checkpoint,
        manifest.terminal_checkpoint_id,
        manifest.successor_checkpoints,
        manifest.cycle_reports,
        manifest.snapshots,
        BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
    )
    return VerifyPaperAccountLineageCommandResult(verification)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify one explicit paper-account checkpoint lineage offline."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        outcome = verify_lineage_manifest(args.manifest)
    except (
        PaperAccountLineageManifestReadError,
        PaperAccountLineageManifestSyntaxError,
    ) as error:
        return _failure(3, error)
    except PaperAccountLineageManifestValidationError as error:
        return _failure(5, error)
    except Exception as error:
        return _failure(6, error)
    verification = outcome.verification
    if verification.status is not PaperAccountLineageVerificationStatus.PASS:
        diagnostic = verification.diagnostics[0]
        return _failure(
            4,
            RuntimeError(f"{diagnostic.code.value}: {diagnostic.detail}"),
        )
    assert verification.evidence is not None
    if not args.quiet:
        evidence = verification.evidence
        print("Paper-account lineage verification: PASS")
        print(f"  evidence ID: {evidence.evidence_id}")
        print(f"  genesis checkpoint: {evidence.genesis_checkpoint_id}")
        print(f"  terminal checkpoint: {evidence.terminal_checkpoint_id}")
        print(f"  edge count: {evidence.edge_count}")
    return 0


def _failure(code: int, error: Exception) -> int:
    print(f"error: {error}", file=sys.stderr)
    return code
