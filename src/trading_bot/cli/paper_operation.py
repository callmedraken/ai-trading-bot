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
from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
    PaperOperationExecutionResult,
    execute_paper_operation_once,
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
    parser.add_argument("--execute-once", action="store_true")
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
    if args.inspect_only == args.execute_once:
        _minimal_failure("EXACTLY_ONE_OPERATION_MODE_REQUIRED")
        return 2
    try:
        calendar = BoundMarketCalendar(
            XNYS_CALENDAR_DESCRIPTOR,
            NYSEMarketCalendar(),
        )
        inputs = load_verified_paper_operation_inputs(args.config, calendar)
        if args.inspect_only:
            inspection = inspect_paper_operation_root(args.operation_root, inputs)
        else:
            execution = execute_paper_operation_once(args.operation_root, inputs)
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
    if args.inspect_only:
        _print_result(inspection)
        return _exit_code(inspection)
    _print_execution_result(execution)
    return _execution_exit_code(execution)


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


def _print_execution_result(result: PaperOperationExecutionResult) -> None:
    print(f"operation ID: {result.operation_id}")
    print(f"pre-execution classification: {result.pre_execution_classification.value}")
    print(f"classification: {result.classification.value}")
    print(f"terminal checkpoint ID: {result.terminal_checkpoint_id}")
    print(f"application ID: {result.application_id}")
    if result.cycle_result_id is not None:
        print(f"cycle-result ID: {result.cycle_result_id}")
    if result.successor_checkpoint_id is not None:
        print(f"successor checkpoint ID: {result.successor_checkpoint_id}")
    if result.transition_path is not None:
        print(f"transition path: {result.transition_path}")
    if result.outcome is not None:
        print(f"outcome: {result.outcome.value}")
    print(f"diagnostic: {result.diagnostic_code}")


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


def _execution_exit_code(result: PaperOperationExecutionResult) -> int:
    if (
        result.classification
        is PaperOperationExecutionClassification.TRANSITION_COMMITTED
    ):
        return 0
    if result.classification is PaperOperationExecutionClassification.EXECUTION_FAILED:
        return 6
    if result.classification is PaperOperationExecutionClassification.CONFLICTING:
        return 5
    if result.classification is PaperOperationExecutionClassification.ALREADY_APPLIED:
        return 0
    code = result.diagnostic_code
    if code == PaperOperationInspectionCode.STALE_TERMINAL_CHECKPOINT.value:
        return 5
    if code in {
        PaperOperationInspectionCode.FINALIZED_TRANSITION_WITHOUT_RECEIPT.value,
        PaperOperationInspectionCode.OPERATION_STAGING_EXISTS.value,
        PaperOperationInspectionCode.TRANSITION_STAGING_EXISTS.value,
        PaperOperationInspectionCode.AMBIGUOUS_OPERATION_STATE.value,
    }:
        return 8
    if code in {
        "PROSPECTIVE_EDGE_VERIFICATION_FAILED",
        "PROSPECTIVE_LINEAGE_VERIFICATION_FAILED",
        "PROSPECTIVE_VERIFICATION_EXCEPTION",
        "STAGED_EDGE_VERIFICATION_FAILED",
        "STAGED_LINEAGE_VERIFICATION_FAILED",
        "STAGED_VERIFICATION_EXCEPTION",
        "FINALIZED_EDGE_VERIFICATION_FAILED",
        "FINALIZED_LINEAGE_VERIFICATION_FAILED",
        "FINALIZED_VERIFICATION_EXCEPTION",
        PaperOperationInspectionCode.INVALID_RECEIPT.value,
        PaperOperationInspectionCode.INVALID_FOREIGN_RECEIPT.value,
        PaperOperationInspectionCode.INVALID_TRANSITION.value,
    }:
        return 4
    return 7


if __name__ == "__main__":
    raise SystemExit(main())
