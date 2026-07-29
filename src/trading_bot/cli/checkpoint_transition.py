"""Offline genesis, one-edge run, and verification command adapters."""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from trading_bot.cli.checkpoint_lineage_config import (
    PaperAccountLineageManifest,
    PaperAccountLineageManifestReadError,
    PaperAccountLineageManifestSyntaxError,
    PaperAccountLineageManifestValidationError,
    load_paper_account_lineage_manifest,
    read_safe_regular_file,
)
from trading_bot.cli.checkpoint_transition_config import (
    CheckpointTransitionConfigReadError,
    CheckpointTransitionConfigSyntaxError,
    CheckpointTransitionConfigValidationError,
    load_checkpoint_transition_config,
    load_genesis_checkpoint_config,
)
from trading_bot.cli.checkpoint_transition_output import (
    CheckpointTransitionConflictError,
    CheckpointTransitionOutputError,
    GenesisDirectoryResult,
    TransitionDirectoryResult,
    inspect_transition_directory,
    install_genesis_directory,
    install_transition_directory,
    reject_prior_lineage_conflict,
    validate_output_parent,
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
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
    MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    CheckpointedPaperCycleReportVerificationStatus,
    PaperAccountCheckpointEdgeVerificationStatus,
    PaperAccountCheckpointVerificationStatus,
    PaperAccountLineageArtifact,
    PaperAccountLineageVerificationStatus,
    VerifiedPriorCheckpoint,
    checkpointed_paper_cycle_report_from_result,
    checkpointed_paper_cycle_report_reference,
    create_genesis_paper_account_checkpoint,
    create_successor_paper_account_checkpoint,
    derive_checkpointed_verified_snapshot_application_id,
    execute_checkpointed_verified_snapshot_paper_cycle,
    parse_successor_paper_account_checkpoint,
    serialize_checkpointed_paper_cycle_report,
    serialize_paper_account_checkpoint,
    serialize_successor_paper_account_checkpoint,
    verified_prior_from_full_lineage,
    verified_prior_from_genesis,
    verified_prior_from_successor_edge,
    verify_checkpointed_paper_cycle_report,
    verify_checkpointed_paper_cycle_successor_edge,
    verify_genesis_paper_account_checkpoint,
    verify_paper_account_lineage,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CheckpointTransitionArtifactReadError(Exception):
    """Raised when a supplied artifact cannot be read safely within its bound."""


class CheckpointTransitionVerificationError(Exception):
    """Raised when a required checkpoint or snapshot does not fully verify."""


class CheckpointTransitionExecutionError(Exception):
    """Raised when replay, execution, report, or successor reconciliation fails."""


@dataclass(frozen=True, slots=True)
class VerifyResult:
    checkpoint_id: str
    edge: bool
    successor_id: str | None = None


def create_genesis_checkpoint(
    *, config_path: Path, output_directory: Path
) -> GenesisDirectoryResult:
    """Create and stage one canonical verified genesis directory offline."""
    config = load_genesis_checkpoint_config(config_path)
    checkpoint = create_genesis_paper_account_checkpoint(config.request)
    payload = serialize_paper_account_checkpoint(checkpoint)
    verified = verify_genesis_paper_account_checkpoint(
        payload,
        expected_checkpoint_sha256=hashlib.sha256(payload).hexdigest(),
        expected_checkpoint_byte_length=len(payload),
    )
    if verified.status is not PaperAccountCheckpointVerificationStatus.PASS:
        raise CheckpointTransitionExecutionError(
            "in-memory genesis verification failed"
        )
    return install_genesis_directory(
        validate_output_parent(output_directory), checkpoint, payload
    )


def run_checkpointed_cycle(
    *,
    checkpoint_path: Path,
    snapshot_path: Path,
    config_path: Path,
    output_directory: Path,
    checkpoint_sha256: str | None = None,
    checkpoint_byte_length: int | None = None,
    snapshot_sha256: str | None = None,
    snapshot_byte_length: int | None = None,
    prior_checkpoint_path: Path | None = None,
    prior_cycle_report_path: Path | None = None,
    prior_snapshot_path: Path | None = None,
) -> TransitionDirectoryResult:
    """Execute at most one deterministic checkpoint-restored paper cycle."""
    _evidence(checkpoint_sha256, checkpoint_byte_length)
    _evidence(snapshot_sha256, snapshot_byte_length)
    config = load_checkpoint_transition_config(config_path)
    parent = validate_output_parent(output_directory)
    starting_payload = _read(
        checkpoint_path, MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES, "checkpoint"
    )
    snapshot_payload = _read(
        snapshot_path, MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES, "snapshot"
    )
    request = config.request
    if (
        checkpoint_sha256 is not None
        and checkpoint_sha256 != hashlib.sha256(starting_payload).hexdigest()
    ) or (
        checkpoint_byte_length is not None
        and checkpoint_byte_length != len(starting_payload)
    ):
        raise CheckpointTransitionVerificationError(
            "checkpoint command evidence mismatches artifact"
        )
    if (
        snapshot_sha256 is not None
        and snapshot_sha256 != request.snapshot_reference.artifact_sha256
    ) or (
        snapshot_byte_length is not None
        and snapshot_byte_length != request.snapshot_reference.artifact_byte_length
    ):
        raise CheckpointTransitionVerificationError(
            "snapshot command evidence conflicts with configuration"
        )
    supplied_starting_edge = (
        prior_checkpoint_path,
        prior_cycle_report_path,
        prior_snapshot_path,
    )
    genesis = verify_genesis_paper_account_checkpoint(
        starting_payload,
        expected_checkpoint_sha256=checkpoint_sha256,
        expected_checkpoint_byte_length=checkpoint_byte_length,
    )
    if (
        genesis.status is PaperAccountCheckpointVerificationStatus.PASS
        and genesis.checkpoint is not None
        and not genesis.diagnostics
    ):
        if any(item is not None for item in supplied_starting_edge):
            raise CheckpointTransitionVerificationError(
                "genesis starting checkpoint cannot receive predecessor-edge artifacts"
            )
        starting_prior = verified_prior_from_genesis(genesis)
    else:
        if any(item is None for item in supplied_starting_edge):
            raise CheckpointTransitionVerificationError(
                "successor starting checkpoint requires prior checkpoint, report, and snapshot"
            )
        try:
            parse_successor_paper_account_checkpoint(starting_payload)
        except ValueError as error:
            raise CheckpointTransitionVerificationError(
                "starting checkpoint verification did not pass"
            ) from error
        try:
            predecessor_payload = _read(
                prior_checkpoint_path,
                MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
                "prior checkpoint",
            )
            predecessor_report_payload = _read(
                prior_cycle_report_path,
                MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
                "prior cycle report",
            )
            predecessor_snapshot_payload = _read(
                prior_snapshot_path,
                MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
                "prior snapshot",
            )
        except CheckpointTransitionArtifactReadError as error:
            raise CheckpointTransitionVerificationError(
                "starting checkpoint verification did not pass"
            ) from error
        starting_edge = verify_checkpointed_paper_cycle_successor_edge(
            predecessor_report_payload,
            predecessor_payload,
            predecessor_snapshot_payload,
            starting_payload,
            _calendar(),
            expected_successor_sha256=checkpoint_sha256,
            expected_successor_byte_length=checkpoint_byte_length,
        )
        if (
            starting_edge.status
            is not PaperAccountCheckpointEdgeVerificationStatus.PASS
            or starting_edge.successor_checkpoint is None
            or starting_edge.restored_successor_ledger is None
            or starting_edge.diagnostics
        ):
            raise CheckpointTransitionVerificationError(
                "starting checkpoint verification did not pass"
            )
        starting_prior = verified_prior_from_successor_edge(starting_edge)
    if starting_prior is None:
        raise CheckpointTransitionVerificationError(
            "starting checkpoint verification did not pass"
        )
    calendar = _calendar()
    snapshot = verify_daily_snapshot(
        snapshot_payload,
        calendar,
        expected_sha256=request.snapshot_reference.artifact_sha256,
        expected_byte_length=request.snapshot_reference.artifact_byte_length,
    )
    if (
        snapshot.status is not DailySnapshotVerificationStatus.PASS
        or snapshot.snapshot is None
    ):
        raise CheckpointTransitionVerificationError(
            "snapshot verification did not pass"
        )
    application_id = derive_checkpointed_verified_snapshot_application_id(
        starting_prior.checkpoint_id, request.request_id
    )
    existing = inspect_transition_directory(
        parent,
        application_id=str(application_id),
        prior_payload=starting_payload,
        snapshot_payload=snapshot_payload,
        calendar=calendar,
        expected_request=request,
        verified_prior=starting_prior,
    )
    if existing is not None:
        return existing
    reject_prior_lineage_conflict(
        parent,
        prior_checkpoint_id=str(starting_prior.checkpoint_id),
        expected_application_id=str(application_id),
        prior_payload=starting_payload,
        snapshot_payload=snapshot_payload,
        calendar=calendar,
    )
    try:
        result = execute_checkpointed_verified_snapshot_paper_cycle(
            request, starting_prior, snapshot, calendar
        )
        report = checkpointed_paper_cycle_report_from_result(result)
        report_payload = serialize_checkpointed_paper_cycle_report(report)
        report_verified = verify_checkpointed_paper_cycle_report(
            report_payload,
            starting_payload,
            snapshot_payload,
            calendar,
            expected_report_sha256=hashlib.sha256(report_payload).hexdigest(),
            expected_report_byte_length=len(report_payload),
            verified_prior=starting_prior,
        )
        if (
            report_verified.status
            is not CheckpointedPaperCycleReportVerificationStatus.PASS
            or report_verified.cycle_result != result
        ):
            raise CheckpointTransitionExecutionError(
                "in-memory cycle report verification failed"
            )
        successor = create_successor_paper_account_checkpoint(
            report.evidence.prior_checkpoint,
            report.evidence.prior_lineage_id,
            result,
            checkpointed_paper_cycle_report_reference(report_payload),
        )
        successor_payload = serialize_successor_paper_account_checkpoint(successor)
        edge = verify_checkpointed_paper_cycle_successor_edge(
            report_payload,
            starting_payload,
            snapshot_payload,
            successor_payload,
            calendar,
            expected_successor_sha256=hashlib.sha256(successor_payload).hexdigest(),
            expected_successor_byte_length=len(successor_payload),
            verified_prior=starting_prior,
        )
    except CheckpointTransitionExecutionError:
        raise
    except Exception as error:
        raise CheckpointTransitionExecutionError(
            "checkpointed cycle execution failed"
        ) from error
    if (
        edge.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
        or edge.cycle_result != result
    ):
        raise CheckpointTransitionExecutionError(
            "in-memory successor edge verification failed"
        )
    return install_transition_directory(
        parent,
        result=result,
        report=report,
        report_payload=report_payload,
        successor=successor,
        successor_payload=successor_payload,
        prior_payload=starting_payload,
        snapshot_payload=snapshot_payload,
        calendar=calendar,
        verified_prior=starting_prior,
    )


def verify_checkpoint(
    *,
    checkpoint_path: Path,
    checkpoint_sha256: str | None = None,
    checkpoint_byte_length: int | None = None,
    prior_checkpoint_path: Path | None = None,
    cycle_report_path: Path | None = None,
    snapshot_path: Path | None = None,
    prior_lineage_manifest_path: Path | None = None,
) -> VerifyResult:
    """Verify one genesis checkpoint or exactly one predecessor-successor edge."""
    _evidence(checkpoint_sha256, checkpoint_byte_length)
    read = _read if prior_lineage_manifest_path is None else _read_safe
    payload = read(
        checkpoint_path,
        MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
        "checkpoint",
    )
    supplied = (prior_checkpoint_path, cycle_report_path, snapshot_path)
    if any(item is not None for item in supplied):
        if any(item is None for item in supplied):
            raise CheckpointTransitionVerificationError(
                "edge verification requires prior checkpoint, report, and snapshot"
            )
        prior = read(
            prior_checkpoint_path,
            (
                MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES
                if prior_lineage_manifest_path is None
                else MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES
            ),
            "prior checkpoint",
        )
        report = read(
            cycle_report_path, MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES, "cycle report"
        )
        snapshot = read(
            snapshot_path,
            MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
            "snapshot",
        )
        verified_prior = None
        if prior_lineage_manifest_path is not None:
            verified_prior = _verified_prior_from_manifest(
                prior_lineage_manifest_path,
                prior,
            )
        edge = verify_checkpointed_paper_cycle_successor_edge(
            report,
            prior,
            snapshot,
            payload,
            _calendar(),
            expected_successor_sha256=checkpoint_sha256,
            expected_successor_byte_length=checkpoint_byte_length,
            verified_prior=verified_prior,
        )
        if (
            edge.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
            or edge.successor_checkpoint is None
        ):
            raise CheckpointTransitionExecutionError(
                "checkpoint edge verification did not pass"
            )
        return VerifyResult(
            str(edge.successor_checkpoint.checkpoint_id),
            True,
            str(edge.successor_checkpoint.checkpoint_id),
        )
    if prior_lineage_manifest_path is not None:
        raise CheckpointTransitionVerificationError(
            "prior lineage manifest requires complete edge inputs"
        )
    verified = verify_genesis_paper_account_checkpoint(
        payload,
        expected_checkpoint_sha256=checkpoint_sha256,
        expected_checkpoint_byte_length=checkpoint_byte_length,
    )
    if (
        verified.status is not PaperAccountCheckpointVerificationStatus.PASS
        or verified.checkpoint is None
    ):
        raise CheckpointTransitionVerificationError(
            "checkpoint verification did not pass"
        )
    return VerifyResult(str(verified.checkpoint.checkpoint_id), False)


def build_genesis_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create one paper-account genesis checkpoint."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one checkpointed verified-snapshot paper cycle."
    )
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--checkpoint-byte-length", type=int)
    parser.add_argument("--snapshot-sha256")
    parser.add_argument("--snapshot-byte-length", type=int)
    parser.add_argument("--prior-checkpoint", type=Path)
    parser.add_argument("--prior-cycle-report", type=Path)
    parser.add_argument("--prior-snapshot", type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def build_verify_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify one paper-account checkpoint or edge offline."
    )
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--checkpoint-byte-length", type=int)
    parser.add_argument("--prior-checkpoint", type=Path)
    parser.add_argument("--cycle-report", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--prior-lineage-manifest", type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def genesis_main(argv: list[str] | None = None) -> int:
    args = build_genesis_parser().parse_args(argv)
    try:
        outcome = create_genesis_checkpoint(
            config_path=args.config, output_directory=args.output_directory
        )
    except (
        CheckpointTransitionConfigReadError,
        CheckpointTransitionConfigSyntaxError,
        CheckpointTransitionArtifactReadError,
    ) as error:
        return _failure(3, error)
    except CheckpointTransitionConfigValidationError as error:
        return _failure(5, error)
    except CheckpointTransitionExecutionError as error:
        return _failure(6, error)
    except CheckpointTransitionOutputError as error:
        return _failure(7, error)
    except Exception:
        return _failure(
            5, CheckpointTransitionExecutionError("genesis creation failed")
        )
    if not args.quiet:
        print(f"Genesis checkpoint: {outcome.checkpoint.checkpoint_id}")
        print(
            f"  sequence: 0\n  account-state ID: {outcome.checkpoint.account_state.account_state_id}"
        )
        print(
            f"  compact-ledger ID: {outcome.checkpoint.account_state.compact_ledger_state_id}"
        )
        print(f"  artifact: sha256={outcome.sha256} bytes={outcome.byte_length}")
        print(f"  final directory: {outcome.directory}")
    return 0


def run_main(argv: list[str] | None = None) -> int:
    args = build_run_parser().parse_args(argv)
    try:
        outcome = run_checkpointed_cycle(
            checkpoint_path=args.checkpoint,
            snapshot_path=args.snapshot,
            config_path=args.config,
            output_directory=args.output_directory,
            checkpoint_sha256=args.checkpoint_sha256,
            checkpoint_byte_length=args.checkpoint_byte_length,
            snapshot_sha256=args.snapshot_sha256,
            snapshot_byte_length=args.snapshot_byte_length,
            prior_checkpoint_path=args.prior_checkpoint,
            prior_cycle_report_path=args.prior_cycle_report,
            prior_snapshot_path=args.prior_snapshot,
        )
    except (
        CheckpointTransitionConfigReadError,
        CheckpointTransitionConfigSyntaxError,
        CheckpointTransitionArtifactReadError,
    ) as error:
        return _failure(3, error)
    except CheckpointTransitionVerificationError as error:
        return _failure(4, error)
    except CheckpointTransitionConfigValidationError as error:
        return _failure(5, error)
    except (
        CheckpointTransitionExecutionError,
        CheckpointTransitionConflictError,
    ) as error:
        return _failure(6, error)
    except CheckpointTransitionOutputError as error:
        return _failure(7, error)
    except Exception:
        return _failure(
            6, CheckpointTransitionExecutionError("transition execution failed")
        )
    if not args.quiet:
        print(f"Checkpoint transition: {outcome.status}")
        print(
            f"  prior checkpoint: {outcome.result.prior_checkpoint_id} sequence={outcome.result.prior_sequence}"
        )
        print(f"  application ID: {outcome.result.application_id}")
        print(f"  cycle result ID: {outcome.result.result_id}")
        print(
            f"  successor checkpoint: {outcome.successor.checkpoint_id} sequence={outcome.successor.sequence}"
        )
        print(
            f"  status: {outcome.result.status.value}; fills: {len(outcome.result.cycle_fills)}"
        )
        print(f"  final cash: {outcome.result.final_compact_state.cash}")
        print(
            f"  report: sha256={outcome.report_sha256} bytes={outcome.report_byte_length}"
        )
        print(
            f"  checkpoint: sha256={outcome.checkpoint_sha256} bytes={outcome.checkpoint_byte_length}"
        )
        print(f"  final transition directory: {outcome.directory}")
    return 0


def verify_main(argv: list[str] | None = None) -> int:
    args = build_verify_parser().parse_args(argv)
    try:
        outcome = verify_checkpoint(
            checkpoint_path=args.checkpoint,
            checkpoint_sha256=args.checkpoint_sha256,
            checkpoint_byte_length=args.checkpoint_byte_length,
            prior_checkpoint_path=args.prior_checkpoint,
            cycle_report_path=args.cycle_report,
            snapshot_path=args.snapshot,
            prior_lineage_manifest_path=args.prior_lineage_manifest,
        )
    except (
        CheckpointTransitionArtifactReadError,
        PaperAccountLineageManifestReadError,
        PaperAccountLineageManifestSyntaxError,
    ) as error:
        return _failure(3, error)
    except CheckpointTransitionVerificationError as error:
        return _failure(4, error)
    except PaperAccountLineageManifestValidationError as error:
        return _failure(5, error)
    except CheckpointTransitionExecutionError as error:
        return _failure(6, error)
    except Exception:
        return _failure(
            6, CheckpointTransitionExecutionError("checkpoint verification failed")
        )
    if not args.quiet:
        print(
            f"Paper-account verification: PASS\n  checkpoint ID: {outcome.checkpoint_id}"
        )
    return 0


def _read(path: Path, maximum: int, label: str) -> bytes:
    if not isinstance(path, Path):
        raise CheckpointTransitionArtifactReadError(f"{label} path is invalid")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise CheckpointTransitionArtifactReadError(
            f"{label} cannot be read"
        ) from error
    if len(payload) > maximum:
        raise CheckpointTransitionArtifactReadError(f"{label} exceeds its byte bound")
    return payload


def _read_safe(path: Path, maximum: int, label: str) -> bytes:
    return read_safe_regular_file(path, maximum, label)


def _verified_prior_from_manifest(
    manifest_path: Path,
    prior_payload: bytes,
) -> VerifiedPriorCheckpoint:
    manifest = load_paper_account_lineage_manifest(manifest_path)
    lineage = verify_paper_account_lineage(
        manifest.genesis_checkpoint,
        manifest.terminal_checkpoint_id,
        manifest.successor_checkpoints,
        manifest.cycle_reports,
        manifest.snapshots,
        _calendar(),
    )
    if (
        lineage.status is not PaperAccountLineageVerificationStatus.PASS
        or lineage.evidence is None
        or lineage.terminal_checkpoint is None
        or lineage.terminal_restored_ledger is None
        or lineage.diagnostics
    ):
        raise CheckpointTransitionVerificationError(
            "prior lineage verification did not pass"
        )
    verified_prior = verified_prior_from_full_lineage(lineage)
    terminal = _terminal_artifact(manifest)
    if (
        terminal is None
        or terminal.artifact_id != verified_prior.checkpoint_id
        or terminal.sha256 != verified_prior.checkpoint_sha256
        or terminal.byte_length != verified_prior.checkpoint_byte_length
        or hashlib.sha256(prior_payload).hexdigest() != terminal.sha256
        or len(prior_payload) != terminal.byte_length
        or prior_payload != terminal.payload
    ):
        raise CheckpointTransitionVerificationError(
            "prior checkpoint does not match verified lineage terminal"
        )
    return verified_prior


def _terminal_artifact(
    manifest: PaperAccountLineageManifest,
) -> PaperAccountLineageArtifact | None:
    if manifest.genesis_checkpoint.artifact_id == manifest.terminal_checkpoint_id:
        return manifest.genesis_checkpoint
    return next(
        (
            artifact
            for artifact in manifest.successor_checkpoints
            if artifact.artifact_id == manifest.terminal_checkpoint_id
        ),
        None,
    )


def _evidence(digest: str | None, length: int | None) -> None:
    if digest is not None and (
        type(digest) is not str or _SHA256.fullmatch(digest) is None
    ):
        raise CheckpointTransitionArtifactReadError(
            "optional SHA-256 evidence is invalid"
        )
    if length is not None and (type(length) is not int or length < 0):
        raise CheckpointTransitionArtifactReadError(
            "optional byte-length evidence is invalid"
        )


def _calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _failure(code: int, error: Exception) -> int:
    print(f"error: {error}", file=sys.stderr)
    return code
