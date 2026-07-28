"""Read-only command adapter for one restart-safe paper-operation inspection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trading_bot.cli.checkpoint_lineage_config import (
    PaperAccountLineageManifestReadError,
    PaperAccountLineageManifestSyntaxError,
    PaperAccountLineageManifestValidationError,
)
from trading_bot.cli.checkpoint_transition_config import (
    CheckpointTransitionConfigSyntaxError,
)
from trading_bot.cli.paper_operation_config import (
    PaperOperationConfigReadError,
    PaperOperationConfigSyntaxError,
    PaperOperationConfigValidationError,
    PaperOperationInputVerificationError,
    load_verified_paper_operation_inputs,
)
from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
    inspect_paper_operation_root,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect one explicit paper operation without writing."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--operation-root", required=True, type=Path)
    parser.add_argument("--inspect-only", action="store_true")
    return parser


def inspect_operation(
    *,
    config_path: Path,
    operation_root: Path,
) -> PaperOperationInspectionResult:
    """Load explicit inputs and inspect one existing operation root read-only."""
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    inputs = load_verified_paper_operation_inputs(config_path, calendar)
    return inspect_paper_operation_root(operation_root, inputs)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.inspect_only:
        _minimal_failure("INSPECT_ONLY_REQUIRED")
        return 2
    try:
        result = inspect_operation(
            config_path=args.config,
            operation_root=args.operation_root,
        )
    except (
        PaperOperationConfigReadError,
        PaperOperationConfigSyntaxError,
        PaperOperationConfigValidationError,
        PaperAccountLineageManifestReadError,
        PaperAccountLineageManifestSyntaxError,
        PaperAccountLineageManifestValidationError,
        CheckpointTransitionConfigSyntaxError,
    ):
        _minimal_failure("CONFIGURATION_OR_ARTIFACT_READ_FAILURE")
        return 3
    except PaperOperationInputVerificationError as error:
        _minimal_failure(error.code.value)
        return 4
    except Exception:
        _minimal_failure("INPUT_VERIFICATION_FAILURE")
        return 4
    _print_result(result)
    return _exit_code(result)


def _print_result(result: PaperOperationInspectionResult) -> None:
    print(f"operation ID: {result.operation_id}")
    print(f"classification: {result.classification.value}")
    print(f"terminal checkpoint ID: {result.terminal_checkpoint_id}")
    print(f"application ID: {result.application_id}")
    if result.receipt_path is not None:
        print(f"receipt path: {result.receipt_path}")
    for code in result.diagnostics:
        print(f"diagnostic: {code.value}")


def _minimal_failure(code: str) -> None:
    print("classification: BLOCKED", file=sys.stderr)
    print(f"diagnostic: {code}", file=sys.stderr)


def _exit_code(result: PaperOperationInspectionResult) -> int:
    if result.classification in (
        PaperOperationClassification.PENDING,
        PaperOperationClassification.ALREADY_APPLIED,
    ):
        return 0
    if result.classification is PaperOperationClassification.CONFLICTING:
        return 5
    code = result.diagnostics[0]
    if code is PaperOperationInspectionCode.STALE_TERMINAL_CHECKPOINT:
        return 5
    if code in (
        PaperOperationInspectionCode.INVALID_RECEIPT,
        PaperOperationInspectionCode.INVALID_FOREIGN_RECEIPT,
        PaperOperationInspectionCode.INVALID_TRANSITION,
    ):
        return 4
    return 8


if __name__ == "__main__":
    raise SystemExit(main())
