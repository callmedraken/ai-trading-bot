"""Strict one-shot run and verify commands for offline snapshot paper cycles."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from trading_bot.cli.exceptions import (
    VerifiedSnapshotPaperCycleArtifactOutputError,
    VerifiedSnapshotPaperCycleArtifactReadError,
    VerifiedSnapshotPaperCycleConfigJsonError,
    VerifiedSnapshotPaperCycleConfigReadError,
    VerifiedSnapshotPaperCycleConfigValidationError,
    VerifiedSnapshotPaperCycleExecutionCliError,
    VerifiedSnapshotPaperCyclePreparationCliError,
    VerifiedSnapshotPaperCycleSnapshotVerificationError,
)
from trading_bot.cli.verified_snapshot_cycle_config import (
    load_verified_snapshot_paper_cycle_config,
)
from trading_bot.cli.verified_snapshot_cycle_output import (
    VerifiedSnapshotPaperCycleArtifactResult,
    install_verified_snapshot_paper_cycle_report,
    validate_verified_snapshot_paper_cycle_destination_directory,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotVerificationStatus,
    verify_daily_snapshot,
)
from trading_bot.runtime import (
    MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_BYTES,
    VerifiedSnapshotPaperCycleReportVerificationCode,
    VerifiedSnapshotPaperCycleReportVerificationStatus,
    execute_prepared_verified_snapshot_paper_cycle,
    prepare_verified_snapshot_paper_cycle,
    serialize_verified_snapshot_paper_cycle_result,
    verify_verified_snapshot_paper_cycle_report,
)
from trading_bot.runtime.exceptions import (
    VerifiedSnapshotPaperCycleExecutionError,
    VerifiedSnapshotPaperCyclePreparationError,
    VerifiedSnapshotPaperCycleReportError,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleRunResult:
    """Complete in-memory and finalized evidence for the run command."""

    artifact: VerifiedSnapshotPaperCycleArtifactResult


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleVerifyResult:
    """Complete PASS evidence returned by the verify command."""

    snapshot_id: str
    preparation_id: str
    runtime_cycle_id: str
    result_id: str
    report_sha256: str
    report_byte_length: int


def run_verified_snapshot_paper_cycle(
    *,
    snapshot_path: Path,
    config_path: Path,
    output_directory: Path,
    snapshot_sha256: str | None = None,
    snapshot_byte_length: int | None = None,
) -> VerifiedSnapshotPaperCycleRunResult:
    """Run exactly one offline prepared cycle and expose one no-clobber report."""
    config = load_verified_snapshot_paper_cycle_config(config_path)
    _validate_optional_evidence(snapshot_sha256, snapshot_byte_length)
    destination = validate_verified_snapshot_paper_cycle_destination_directory(
        output_directory
    )
    snapshot_payload = _read_artifact(
        snapshot_path,
        MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
        "snapshot",
    )
    reference = config.preparation_request.snapshot_reference
    if (
        snapshot_sha256 is not None and snapshot_sha256 != reference.artifact_sha256
    ) or (
        snapshot_byte_length is not None
        and snapshot_byte_length != reference.artifact_byte_length
    ):
        raise VerifiedSnapshotPaperCycleSnapshotVerificationError(
            "snapshot command evidence conflicts with configuration"
        )
    calendar = _calendar()
    snapshot_verification = verify_daily_snapshot(
        snapshot_payload,
        calendar,
        expected_sha256=reference.artifact_sha256,
        expected_byte_length=reference.artifact_byte_length,
    )
    if (
        snapshot_verification.status is not DailySnapshotVerificationStatus.PASS
        or snapshot_verification.snapshot is None
    ):
        raise VerifiedSnapshotPaperCycleSnapshotVerificationError(
            "snapshot verification did not pass"
        )
    try:
        prepared = prepare_verified_snapshot_paper_cycle(
            config.preparation_request,
            snapshot_verification,
            calendar,
        )
    except VerifiedSnapshotPaperCyclePreparationError as error:
        raise VerifiedSnapshotPaperCyclePreparationCliError(
            "cycle preparation failed"
        ) from error
    try:
        result = execute_prepared_verified_snapshot_paper_cycle(prepared)
    except VerifiedSnapshotPaperCycleExecutionError as error:
        raise VerifiedSnapshotPaperCycleExecutionCliError(
            "paper-runtime execution failed"
        ) from error
    try:
        payload = serialize_verified_snapshot_paper_cycle_result(result)
        report_hash = hashlib.sha256(payload).hexdigest()
        in_memory_verification = verify_verified_snapshot_paper_cycle_report(
            payload,
            snapshot_payload,
            calendar,
            expected_report_sha256=report_hash,
            expected_report_byte_length=len(payload),
        )
    except VerifiedSnapshotPaperCycleReportError as error:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "in-memory report serialization or verification failed"
        ) from error
    if (
        in_memory_verification.status
        is not VerifiedSnapshotPaperCycleReportVerificationStatus.PASS
        or in_memory_verification.result != result
        or in_memory_verification.result is None
        or in_memory_verification.result.result_id != result.result_id
    ):
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "in-memory report verification did not reconcile"
        )
    artifact = install_verified_snapshot_paper_cycle_report(
        destination=destination,
        result=result,
        payload=payload,
        snapshot_payload=snapshot_payload,
        calendar=calendar,
        in_memory_verification=in_memory_verification,
    )
    return VerifiedSnapshotPaperCycleRunResult(artifact)


def verify_verified_snapshot_paper_cycle(
    *,
    snapshot_path: Path,
    report_path: Path,
    snapshot_sha256: str | None = None,
    snapshot_byte_length: int | None = None,
    report_sha256: str | None = None,
    report_byte_length: int | None = None,
) -> VerifiedSnapshotPaperCycleVerifyResult:
    """Verify one report and snapshot artifact fully offline."""
    _validate_optional_evidence(snapshot_sha256, snapshot_byte_length)
    _validate_optional_evidence(report_sha256, report_byte_length)
    snapshot_payload = _read_artifact(
        snapshot_path,
        MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
        "snapshot",
    )
    report_payload = _read_artifact(
        report_path,
        MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_BYTES,
        "report",
    )
    calendar = _calendar()
    snapshot_verification = verify_daily_snapshot(
        snapshot_payload,
        calendar,
        expected_sha256=snapshot_sha256,
        expected_byte_length=snapshot_byte_length,
    )
    if (
        snapshot_verification.status is not DailySnapshotVerificationStatus.PASS
        or snapshot_verification.snapshot is None
    ):
        raise VerifiedSnapshotPaperCycleSnapshotVerificationError(
            "snapshot verification did not pass"
        )
    verification = verify_verified_snapshot_paper_cycle_report(
        report_payload,
        snapshot_payload,
        calendar,
        expected_report_sha256=report_sha256,
        expected_report_byte_length=report_byte_length,
    )
    if (
        verification.status
        is not VerifiedSnapshotPaperCycleReportVerificationStatus.PASS
    ):
        codes = tuple(item.code for item in verification.diagnostics)
        if (
            VerifiedSnapshotPaperCycleReportVerificationCode.SNAPSHOT_LINKAGE_FAILURE
            in codes
        ):
            raise VerifiedSnapshotPaperCycleSnapshotVerificationError(
                "report does not link to a complete matching snapshot"
            )
        raise VerifiedSnapshotPaperCycleExecutionCliError(
            "cycle report verification did not pass"
        )
    result = verification.result
    if result is None:
        raise VerifiedSnapshotPaperCycleExecutionCliError(
            "cycle report verification did not reconstruct a result"
        )
    return VerifiedSnapshotPaperCycleVerifyResult(
        snapshot_id=str(result.preparation.snapshot_reference.snapshot_id),
        preparation_id=str(result.preparation.preparation_id),
        runtime_cycle_id=str(result.runtime_result.result_id),
        result_id=str(result.result_id),
        report_sha256=verification.report_sha256,
        report_byte_length=verification.report_byte_length,
    )


def build_run_parser() -> argparse.ArgumentParser:
    """Build the dedicated one-shot cycle-run command parser."""
    parser = argparse.ArgumentParser(
        description="Run one verified-snapshot paper cycle and write one report."
    )
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--snapshot-sha256")
    parser.add_argument("--snapshot-byte-length", type=int)
    parser.add_argument("--quiet", action="store_true")
    return parser


def build_verify_parser() -> argparse.ArgumentParser:
    """Build the dedicated fully offline cycle-report verification parser."""
    parser = argparse.ArgumentParser(
        description="Verify one verified-snapshot paper-cycle report offline."
    )
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--snapshot-sha256")
    parser.add_argument("--snapshot-byte-length", type=int)
    parser.add_argument("--report-sha256")
    parser.add_argument("--report-byte-length", type=int)
    parser.add_argument("--quiet", action="store_true")
    return parser


def run_main(argv: list[str] | None = None) -> int:
    """CLI entry point for one strict run invocation."""
    args = build_run_parser().parse_args(argv)
    try:
        outcome = run_verified_snapshot_paper_cycle(
            snapshot_path=args.snapshot,
            config_path=args.config,
            output_directory=args.output_directory,
            snapshot_sha256=args.snapshot_sha256,
            snapshot_byte_length=args.snapshot_byte_length,
        )
    except (
        VerifiedSnapshotPaperCycleArtifactReadError,
        VerifiedSnapshotPaperCycleConfigReadError,
        VerifiedSnapshotPaperCycleConfigJsonError,
    ) as error:
        return _failure(3, error)
    except VerifiedSnapshotPaperCycleSnapshotVerificationError as error:
        return _failure(4, error)
    except VerifiedSnapshotPaperCycleConfigValidationError as error:
        return _failure(5, error)
    except VerifiedSnapshotPaperCyclePreparationCliError as error:
        return _failure(5, error)
    except VerifiedSnapshotPaperCycleExecutionCliError as error:
        return _failure(6, error)
    except (
        VerifiedSnapshotPaperCycleArtifactOutputError,
        VerifiedSnapshotPaperCycleReportError,
    ) as error:
        return _failure(7, error)
    if not args.quiet:
        _print_run_success(outcome)
    if outcome.artifact.cleanup_warning is not None:
        print(f"warning: {outcome.artifact.cleanup_warning}", file=sys.stderr)
    return 0


def verify_main(argv: list[str] | None = None) -> int:
    """CLI entry point for one strict offline verification invocation."""
    args = build_verify_parser().parse_args(argv)
    try:
        outcome = verify_verified_snapshot_paper_cycle(
            snapshot_path=args.snapshot,
            report_path=args.report,
            snapshot_sha256=args.snapshot_sha256,
            snapshot_byte_length=args.snapshot_byte_length,
            report_sha256=args.report_sha256,
            report_byte_length=args.report_byte_length,
        )
    except VerifiedSnapshotPaperCycleArtifactReadError as error:
        return _failure(3, error)
    except VerifiedSnapshotPaperCycleSnapshotVerificationError as error:
        return _failure(4, error)
    except (
        VerifiedSnapshotPaperCycleExecutionCliError,
        VerifiedSnapshotPaperCycleReportError,
    ) as error:
        return _failure(5, error)
    if not args.quiet:
        print("Verified snapshot paper cycle: PASS")
        print(f"  snapshot ID: {outcome.snapshot_id}")
        print(f"  preparation ID: {outcome.preparation_id}")
        print(f"  runtime cycle ID: {outcome.runtime_cycle_id}")
        print(f"  result ID: {outcome.result_id}")
        print(
            f"  report: sha256={outcome.report_sha256} "
            f"bytes={outcome.report_byte_length}"
        )
    return 0


def _read_artifact(path: Path, maximum: int, label: str) -> bytes:
    if not isinstance(path, Path):
        raise VerifiedSnapshotPaperCycleArtifactReadError(f"{label} path is invalid")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise VerifiedSnapshotPaperCycleArtifactReadError(
            f"{label} artifact cannot be read"
        ) from error
    if len(payload) > maximum:
        raise VerifiedSnapshotPaperCycleArtifactReadError(
            f"{label} artifact exceeds the supported size limit"
        )
    return payload


def _validate_optional_evidence(
    sha256: str | None,
    byte_length: int | None,
) -> None:
    if sha256 is not None and (
        type(sha256) is not str or _SHA256_PATTERN.fullmatch(sha256) is None
    ):
        raise VerifiedSnapshotPaperCycleArtifactReadError(
            "optional SHA-256 evidence is invalid"
        )
    if byte_length is not None and (type(byte_length) is not int or byte_length < 0):
        raise VerifiedSnapshotPaperCycleArtifactReadError(
            "optional byte-length evidence is invalid"
        )


def _calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _failure(exit_code: int, error: Exception) -> int:
    print(f"error: {error}", file=sys.stderr)
    return exit_code


def _print_run_success(outcome: VerifiedSnapshotPaperCycleRunResult) -> None:
    artifact = outcome.artifact
    result = artifact.result
    risk = result.runtime_result.risk_result
    positions = ",".join(
        f"{item.symbol}:{item.quantity}"
        for item in result.final_account_state.positions
    )
    print("Verified snapshot paper cycle: PASS")
    print(f"  snapshot ID: {result.preparation.snapshot_reference.snapshot_id}")
    print(f"  preparation ID: {result.preparation.preparation_id}")
    print(f"  runtime cycle ID: {result.runtime_result.result_id}")
    print(f"  result ID: {result.result_id}")
    print(f"  status: {result.status.value}")
    print(
        "  risk: "
        f"approved={risk.approved_count} resized={risk.resized_count} "
        f"rejected={risk.rejected_count}"
    )
    print(f"  fills: {len(result.cycle_fills)}")
    print(f"  final cash: {result.final_account_state.cash}")
    print(f"  final positions: {positions}")
    print(
        f"  report: sha256={artifact.artifact_sha256} "
        f"bytes={artifact.artifact_byte_length}"
    )
    print(f"  path: {artifact.artifact_path}")
