"""Fixed-layout, no-clobber output and offline inspection for checkpoint edges."""

# ruff: noqa: E501

from __future__ import annotations

import errno
import hashlib
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.market_data import IdentifiedMarketCalendar
from trading_bot.runtime import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
    CheckpointedPaperCycleReport,
    CheckpointedVerifiedSnapshotPaperCycleResult,
    PaperAccountCheckpoint,
    PaperAccountCheckpointEdgeVerificationStatus,
    PaperAccountCheckpointVerificationStatus,
    PaperAccountSuccessorCheckpoint,
    VerifiedPriorCheckpoint,
    parse_checkpointed_paper_cycle_report,
    parse_successor_paper_account_checkpoint,
    verify_checkpointed_paper_cycle_successor_edge,
    verify_genesis_paper_account_checkpoint,
)


class CheckpointTransitionOutputError(Exception):
    """Raised for unsafe destination, staging, or finalization operations."""


class CheckpointTransitionConflictError(CheckpointTransitionOutputError):
    """Raised when a destination already contains conflicting checkpoint work."""


class TransitionCommitVerificationPhase(StrEnum):
    """The two durable reread points in a transition commit."""

    STAGED_REREAD = "STAGED_REREAD"
    FINALIZED_REREAD = "FINALIZED_REREAD"


@dataclass(frozen=True, slots=True)
class OutputParent:
    path: Path
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class GenesisDirectoryResult:
    checkpoint: PaperAccountCheckpoint
    directory: Path
    checkpoint_path: Path
    sha256: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class TransitionDirectoryResult:
    status: str
    result: CheckpointedVerifiedSnapshotPaperCycleResult
    report: CheckpointedPaperCycleReport
    successor: PaperAccountSuccessorCheckpoint
    directory: Path
    report_path: Path
    checkpoint_path: Path
    report_sha256: str
    report_byte_length: int
    checkpoint_sha256: str
    checkpoint_byte_length: int


def validate_output_parent(path: Path) -> OutputParent:
    """Require an existing real output parent with a safe real parent chain."""
    if not isinstance(path, Path):
        raise CheckpointTransitionOutputError("output parent is invalid")
    normalized = Path(os.path.abspath(path))
    _real_chain(normalized)
    try:
        retained = os.lstat(normalized)
    except OSError as error:
        raise CheckpointTransitionOutputError(
            "output parent must be an existing real directory"
        ) from error
    if not _real_directory(retained):
        raise CheckpointTransitionOutputError(
            "output parent must be an existing real directory"
        )
    return OutputParent(normalized, retained.st_dev, retained.st_ino)


def install_genesis_directory(
    parent: OutputParent,
    checkpoint: PaperAccountCheckpoint,
    payload: bytes,
) -> GenesisDirectoryResult:
    """Install one verified canonical genesis artifact in its fixed layout."""
    if type(checkpoint) is not PaperAccountCheckpoint or type(payload) is not bytes:
        raise CheckpointTransitionOutputError("genesis output input is invalid")
    digest = hashlib.sha256(payload).hexdigest()
    verification = verify_genesis_paper_account_checkpoint(
        payload,
        expected_checkpoint_sha256=digest,
        expected_checkpoint_byte_length=len(payload),
    )
    if (
        verification.status is not PaperAccountCheckpointVerificationStatus.PASS
        or verification.checkpoint != checkpoint
    ):
        raise CheckpointTransitionOutputError("genesis bytes do not verify in memory")
    name = f"paper-account-genesis-{checkpoint.checkpoint_id}"
    filename = f"paper-account-checkpoint-{checkpoint.checkpoint_id}.json"
    final = parent.path / name
    _preflight(parent, name)
    _install_directory(
        parent,
        name,
        {filename: payload},
        lambda root: _verify_genesis(root / filename, checkpoint, payload),
    )
    return GenesisDirectoryResult(
        checkpoint, final, final / filename, digest, len(payload)
    )


def inspect_transition_directory(
    parent: OutputParent,
    *,
    application_id: str,
    prior_payload: bytes,
    snapshot_payload: bytes,
    calendar: IdentifiedMarketCalendar,
    expected_request: object,
    verified_prior: VerifiedPriorCheckpoint | None = None,
) -> TransitionDirectoryResult | None:
    """Return a complete matching transition without execution, or reject it."""
    name = f"paper-account-transition-{application_id}"
    final = parent.path / name
    if _entry_exists(final):
        return _load_transition(
            final,
            prior_payload,
            snapshot_payload,
            calendar,
            expected_request,
            required_application_id=application_id,
            verified_prior=verified_prior,
        )
    return None


def reject_prior_lineage_conflict(
    parent: OutputParent,
    *,
    prior_checkpoint_id: str,
    expected_application_id: str,
    prior_payload: bytes,
    snapshot_payload: bytes,
    calendar: IdentifiedMarketCalendar,
) -> None:
    """Fail closed if any other valid or hostile transition binds this prior."""
    _require_parent(parent)
    try:
        entries = tuple(os.scandir(parent.path))
    except OSError as error:
        raise CheckpointTransitionOutputError("cannot inspect output parent") from error
    prefix = "paper-account-transition-"
    for entry in entries:
        if not entry.name.casefold().startswith(prefix) or entry.name == (
            f"paper-account-transition-{expected_application_id}"
        ):
            continue
        path = parent.path / entry.name
        if not entry.is_dir(follow_symlinks=False) or entry.is_symlink():
            raise CheckpointTransitionConflictError("invalid existing transition entry")
        try:
            contents = tuple(child.name for child in os.scandir(path))
        except OSError as error:
            raise CheckpointTransitionConflictError(
                "cannot inspect existing transition"
            ) from error
        checkpoints = tuple(
            name for name in contents if name.startswith("paper-account-checkpoint-")
        )
        if len(checkpoints) != 1:
            raise CheckpointTransitionConflictError(
                "invalid existing transition layout"
            )
        try:
            successor = parse_successor_paper_account_checkpoint(
                (path / checkpoints[0]).read_bytes()
            )
        except (OSError, ValueError) as error:
            raise CheckpointTransitionConflictError(
                "invalid existing transition"
            ) from error
        if str(successor.prior_checkpoint.checkpoint_id) != prior_checkpoint_id:
            continue
        # A same-prior successor in this root is a conflict even when its report
        # becomes unavailable: never attempt repair or replacement.
        raise CheckpointTransitionConflictError("LINEAGE_CONFLICT")


def install_transition_directory(
    parent: OutputParent,
    *,
    result: CheckpointedVerifiedSnapshotPaperCycleResult,
    report: CheckpointedPaperCycleReport,
    report_payload: bytes,
    successor: PaperAccountSuccessorCheckpoint,
    successor_payload: bytes,
    prior_payload: bytes,
    snapshot_payload: bytes,
    calendar: IdentifiedMarketCalendar,
) -> TransitionDirectoryResult:
    """Install one fully verified successor transition with no replacement path."""
    application = str(result.application_id)
    name = f"paper-account-transition-{application}"
    report_name = f"checkpointed-paper-cycle-report-{result.result_id}.json"
    checkpoint_name = f"paper-account-checkpoint-{successor.checkpoint_id}.json"
    _preflight(parent, name)
    _install_directory(
        parent,
        name,
        {report_name: report_payload, checkpoint_name: successor_payload},
        lambda root: _verify_transition(
            root / report_name,
            root / checkpoint_name,
            prior_payload,
            snapshot_payload,
            calendar,
            result,
            report,
            successor,
        ),
    )
    return _transition_result(
        "ACCEPTED",
        parent.path / name,
        report_name,
        checkpoint_name,
        result,
        report,
        successor,
        report_payload,
        successor_payload,
    )


def preflight_transition_directory(
    parent: OutputParent,
    *,
    application_id: str,
) -> None:
    """Require the exact final and staging transition names to be unoccupied."""
    if type(application_id) is not str or not application_id.strip():
        raise CheckpointTransitionOutputError("application ID is invalid")
    try:
        parsed_application = UUID(application_id)
    except ValueError as error:
        raise CheckpointTransitionOutputError("application ID is invalid") from error
    if str(parsed_application) != application_id:
        raise CheckpointTransitionOutputError("application ID is not canonical")
    _preflight(parent, f"paper-account-transition-{application_id}")


def commit_transition_directory(
    parent: OutputParent,
    *,
    result: CheckpointedVerifiedSnapshotPaperCycleResult,
    report: CheckpointedPaperCycleReport,
    report_payload: bytes,
    successor: PaperAccountSuccessorCheckpoint,
    successor_payload: bytes,
    verifier: Callable[[bytes, bytes, TransitionCommitVerificationPhase], None],
) -> TransitionDirectoryResult:
    """Commit one preverified transition and preserve every crash-left staging."""
    if (
        type(parent) is not OutputParent
        or type(result) is not CheckpointedVerifiedSnapshotPaperCycleResult
        or type(report) is not CheckpointedPaperCycleReport
        or type(report_payload) is not bytes
        or not report_payload
        or len(report_payload) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES
        or type(successor) is not PaperAccountSuccessorCheckpoint
        or type(successor_payload) is not bytes
        or not successor_payload
        or len(successor_payload) > MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES
        or not callable(verifier)
    ):
        raise CheckpointTransitionOutputError("transition commit input is invalid")
    application = str(result.application_id)
    if (
        report.evidence.application_id != result.application_id
        or successor.application_id != result.application_id
    ):
        raise CheckpointTransitionOutputError("transition commit identity is invalid")
    name = f"paper-account-transition-{application}"
    report_name = f"checkpointed-paper-cycle-report-{result.result_id}.json"
    checkpoint_name = f"paper-account-checkpoint-{successor.checkpoint_id}.json"
    staging = parent.path / f".{name}.staging"
    final = parent.path / name
    preflight_transition_directory(parent, application_id=application)
    try:
        os.mkdir(staging)
    except OSError as error:
        raise CheckpointTransitionOutputError(
            "cannot exclusively create staging directory"
        ) from error
    retained = _lstat_directory(staging, "staging directory")
    identity = (retained.st_dev, retained.st_ino)
    _write_file(staging / report_name, report_payload)
    _write_file(staging / checkpoint_name, successor_payload)
    _fsync_directory(staging)
    expected = {report_name, checkpoint_name}
    _verify_staging_layout(staging, expected)
    staged_report = _read_commit_regular(
        staging / report_name,
        MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
        "staged cycle report",
    )
    staged_checkpoint = _read_commit_regular(
        staging / checkpoint_name,
        MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
        "staged successor checkpoint",
    )
    verifier(
        staged_report,
        staged_checkpoint,
        TransitionCommitVerificationPhase.STAGED_REREAD,
    )
    _require_parent(parent)
    _require_directory_identity(staging, identity, "staging directory")
    _reject_collisions(parent.path, {name}, allowed={staging.name})
    if _entry_exists(final):
        raise CheckpointTransitionOutputError("final transition already exists")
    _fsync_directory(parent.path)
    try:
        os.rename(staging, final)
    except OSError as error:
        raise CheckpointTransitionOutputError(
            "cannot finalize staged directory"
        ) from error
    _fsync_directory(parent.path)
    _require_parent(parent)
    _require_directory_identity(final, identity, "final transition directory")
    _verify_staging_layout(final, expected)
    finalized_report = _read_commit_regular(
        final / report_name,
        MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
        "finalized cycle report",
    )
    finalized_checkpoint = _read_commit_regular(
        final / checkpoint_name,
        MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
        "finalized successor checkpoint",
    )
    verifier(
        finalized_report,
        finalized_checkpoint,
        TransitionCommitVerificationPhase.FINALIZED_REREAD,
    )
    _require_parent(parent)
    _require_directory_identity(final, identity, "final transition directory")
    return _transition_result(
        "ACCEPTED",
        final,
        report_name,
        checkpoint_name,
        result,
        report,
        successor,
        finalized_report,
        finalized_checkpoint,
    )


def _load_transition(
    directory: Path,
    prior_payload: bytes,
    snapshot_payload: bytes,
    calendar: IdentifiedMarketCalendar,
    expected_request: object,
    *,
    required_application_id: str,
    verified_prior: VerifiedPriorCheckpoint | None,
) -> TransitionDirectoryResult:
    _lstat_directory(directory, "existing transition directory")
    expected_name = f"paper-account-transition-{required_application_id}"
    if directory.name != expected_name:
        raise CheckpointTransitionConflictError(
            "existing transition directory is mismatched"
        )
    try:
        entries = {entry.name: entry for entry in os.scandir(directory)}
    except OSError as error:
        raise CheckpointTransitionConflictError(
            "cannot inspect existing transition"
        ) from error
    reports = tuple(
        name for name in entries if name.startswith("checkpointed-paper-cycle-report-")
    )
    checkpoints = tuple(
        name for name in entries if name.startswith("paper-account-checkpoint-")
    )
    if len(entries) != 2 or len(reports) != 1 or len(checkpoints) != 1:
        raise CheckpointTransitionConflictError("existing transition layout is invalid")
    report_path, checkpoint_path = directory / reports[0], directory / checkpoints[0]
    report_payload = _read_regular(report_path, "existing cycle report")
    checkpoint_payload = _read_regular(checkpoint_path, "existing successor checkpoint")
    try:
        report = parse_checkpointed_paper_cycle_report(report_payload)
        successor = parse_successor_paper_account_checkpoint(checkpoint_payload)
    except ValueError as error:
        raise CheckpointTransitionConflictError(
            "existing transition bytes are invalid"
        ) from error
    if (
        reports[0]
        != f"checkpointed-paper-cycle-report-{report.evidence.cycle_result_id}.json"
        or checkpoints[0] != f"paper-account-checkpoint-{successor.checkpoint_id}.json"
        or str(successor.application_id) != required_application_id
        or report.evidence.request != expected_request
    ):
        raise CheckpointTransitionConflictError(
            "existing transition identity is mismatched"
        )
    edge = verify_checkpointed_paper_cycle_successor_edge(
        report_payload,
        prior_payload,
        snapshot_payload,
        checkpoint_payload,
        calendar,
        expected_successor_sha256=hashlib.sha256(checkpoint_payload).hexdigest(),
        expected_successor_byte_length=len(checkpoint_payload),
        verified_prior=verified_prior,
    )
    if (
        edge.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
        or edge.cycle_result is None
    ):
        raise CheckpointTransitionConflictError(
            "existing transition edge verification failed"
        )
    if edge.cycle_result.application_id != successor.application_id:
        raise CheckpointTransitionConflictError(
            "existing transition application mismatches"
        )
    return _transition_result(
        "ALREADY_APPLIED",
        directory,
        reports[0],
        checkpoints[0],
        edge.cycle_result,
        report,
        successor,
        report_payload,
        checkpoint_payload,
    )


def _transition_result(
    status: str,
    directory: Path,
    report_name: str,
    checkpoint_name: str,
    result: CheckpointedVerifiedSnapshotPaperCycleResult,
    report: CheckpointedPaperCycleReport,
    successor: PaperAccountSuccessorCheckpoint,
    report_payload: bytes,
    checkpoint_payload: bytes,
) -> TransitionDirectoryResult:
    return TransitionDirectoryResult(
        status,
        result,
        report,
        successor,
        directory,
        directory / report_name,
        directory / checkpoint_name,
        hashlib.sha256(report_payload).hexdigest(),
        len(report_payload),
        hashlib.sha256(checkpoint_payload).hexdigest(),
        len(checkpoint_payload),
    )


def _verify_genesis(
    path: Path, checkpoint: PaperAccountCheckpoint, payload: bytes
) -> None:
    read = _read_regular(path, "staged genesis checkpoint")
    if read != payload:
        raise CheckpointTransitionOutputError("staged genesis bytes changed")
    verified = verify_genesis_paper_account_checkpoint(
        read,
        expected_checkpoint_sha256=hashlib.sha256(payload).hexdigest(),
        expected_checkpoint_byte_length=len(payload),
    )
    if (
        verified.status is not PaperAccountCheckpointVerificationStatus.PASS
        or verified.checkpoint != checkpoint
    ):
        raise CheckpointTransitionOutputError("staged genesis verification failed")


def _verify_transition(
    report_path: Path,
    checkpoint_path: Path,
    prior: bytes,
    snapshot: bytes,
    calendar: IdentifiedMarketCalendar,
    result: CheckpointedVerifiedSnapshotPaperCycleResult,
    report: CheckpointedPaperCycleReport,
    successor: PaperAccountSuccessorCheckpoint,
) -> None:
    report_payload = _read_regular(report_path, "staged cycle report")
    checkpoint_payload = _read_regular(checkpoint_path, "staged successor checkpoint")
    if (
        parse_checkpointed_paper_cycle_report(report_payload) != report
        or parse_successor_paper_account_checkpoint(checkpoint_payload) != successor
    ):
        raise CheckpointTransitionOutputError("staged transition bytes changed")
    verified = verify_checkpointed_paper_cycle_successor_edge(
        report_payload,
        prior,
        snapshot,
        checkpoint_payload,
        calendar,
        expected_successor_sha256=hashlib.sha256(checkpoint_payload).hexdigest(),
        expected_successor_byte_length=len(checkpoint_payload),
    )
    if (
        verified.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
        or verified.cycle_result != result
    ):
        raise CheckpointTransitionOutputError(
            "staged transition edge verification failed"
        )


def _install_directory(
    parent: OutputParent, name: str, files: dict[str, bytes], verifier
) -> None:
    _require_parent(parent)
    staging = parent.path / f".{name}.staging"
    final = parent.path / name
    _reject_collisions(parent.path, {name, staging.name})
    created = False
    identity: tuple[int, int] | None = None
    try:
        try:
            os.mkdir(staging)
        except OSError as error:
            raise CheckpointTransitionOutputError(
                "cannot exclusively create staging directory"
            ) from error
        created = True
        retained = _lstat_directory(staging, "staging directory")
        identity = (retained.st_dev, retained.st_ino)
        for filename, payload in files.items():
            _write_file(staging / filename, payload)
        _fsync_directory(staging)
        _verify_staging_layout(staging, set(files))
        verifier(staging)
        _require_parent(parent)
        _require_directory_identity(staging, identity, "staging directory")
        _reject_collisions(parent.path, {name}, allowed={staging.name})
        if _entry_exists(final):
            raise CheckpointTransitionOutputError("final transition already exists")
        _fsync_directory(parent.path)
        try:
            os.rename(staging, final)
        except OSError as error:
            raise CheckpointTransitionOutputError(
                "cannot finalize staged directory"
            ) from error
        created = False
    except Exception as primary:
        if created and identity is not None:
            cleanup = _cleanup(staging, identity)
            if cleanup is not None:
                raise CheckpointTransitionOutputError(
                    f"{primary}; {cleanup}"
                ) from primary
        raise


def _preflight(parent: OutputParent, name: str) -> None:
    _require_parent(parent)
    _reject_collisions(parent.path, {name, f".{name}.staging"})


def _write_file(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            retained = os.fstat(stream.fileno())
            if not stat.S_ISREG(retained.st_mode) or _reparse(retained):
                raise CheckpointTransitionOutputError("staging file is unsafe")
            if stream.write(payload) != len(payload):
                raise CheckpointTransitionOutputError("staging write was incomplete")
            stream.flush()
            os.fsync(stream.fileno())
    except CheckpointTransitionOutputError:
        raise
    except OSError as error:
        raise CheckpointTransitionOutputError(
            "cannot write staging artifact"
        ) from error


def _verify_staging_layout(path: Path, expected: set[str]) -> None:
    try:
        entries = tuple(path.iterdir())
    except OSError as error:
        raise CheckpointTransitionOutputError(
            "cannot inspect staging layout"
        ) from error
    if {item.name for item in entries} != expected:
        raise CheckpointTransitionOutputError("staging layout is unexpected")
    for item in entries:
        retained = os.lstat(item)
        if (
            not stat.S_ISREG(retained.st_mode)
            or stat.S_ISLNK(retained.st_mode)
            or _reparse(retained)
        ):
            raise CheckpointTransitionOutputError("staging layout is unsafe")


def _read_regular(path: Path, label: str) -> bytes:
    try:
        retained = os.lstat(path)
        if (
            not stat.S_ISREG(retained.st_mode)
            or stat.S_ISLNK(retained.st_mode)
            or _reparse(retained)
        ):
            raise CheckpointTransitionOutputError(f"{label} is not a real regular file")
        return path.read_bytes()
    except CheckpointTransitionOutputError:
        raise
    except OSError as error:
        raise CheckpointTransitionOutputError(f"{label} cannot be read") from error


def _read_commit_regular(path: Path, maximum: int, label: str) -> bytes:
    try:
        return read_safe_regular_file(path, maximum, label)
    except Exception as error:
        raise CheckpointTransitionOutputError(
            f"{label} cannot be read safely"
        ) from error


def _reject_collisions(
    directory: Path, names: set[str], *, allowed: set[str] | None = None
) -> None:
    wanted, accepted = (
        {name.casefold() for name in names},
        {name.casefold() for name in allowed or set()},
    )
    try:
        for entry in os.scandir(directory):
            if (
                entry.name.casefold() in wanted
                and entry.name.casefold() not in accepted
            ):
                raise CheckpointTransitionOutputError(
                    "final or staging entry already exists"
                )
    except CheckpointTransitionOutputError:
        raise
    except OSError as error:
        raise CheckpointTransitionOutputError("cannot inspect output parent") from error


def _entry_exists(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise CheckpointTransitionOutputError("cannot inspect output entry") from error
    return True


def _real_chain(path: Path) -> None:
    for item in (path, *path.parents):
        try:
            retained = os.lstat(item)
        except OSError as error:
            raise CheckpointTransitionOutputError(
                "output parent chain is unsafe"
            ) from error
        if stat.S_ISLNK(retained.st_mode) or _reparse(retained):
            raise CheckpointTransitionOutputError("output parent chain is unsafe")


def _real_directory(value: os.stat_result) -> bool:
    return (
        stat.S_ISDIR(value.st_mode)
        and not stat.S_ISLNK(value.st_mode)
        and not _reparse(value)
    )


def _lstat_directory(path: Path, label: str) -> os.stat_result:
    try:
        retained = os.lstat(path)
    except OSError as error:
        raise CheckpointTransitionOutputError(f"{label} is unavailable") from error
    if not _real_directory(retained):
        raise CheckpointTransitionOutputError(f"{label} is unsafe")
    return retained


def _require_parent(parent: OutputParent) -> None:
    retained = _lstat_directory(parent.path, "output parent")
    if (retained.st_dev, retained.st_ino) != (parent.device, parent.inode):
        raise CheckpointTransitionOutputError("output parent changed after preflight")


def _require_directory_identity(
    path: Path, identity: tuple[int, int], label: str
) -> None:
    retained = _lstat_directory(path, label)
    if (retained.st_dev, retained.st_ino) != identity:
        raise CheckpointTransitionOutputError(f"{label} changed during staging")


def _cleanup(path: Path, identity: tuple[int, int]) -> str | None:
    try:
        _require_directory_identity(path, identity, "staging directory")
        entries = tuple(path.iterdir())
        for item in entries:
            retained = os.lstat(item)
            if (
                not stat.S_ISREG(retained.st_mode)
                or stat.S_ISLNK(retained.st_mode)
                or _reparse(retained)
            ):
                return "staging identity changed; cleanup was not attempted"
        for item in entries:
            item.unlink()
        path.rmdir()
    except FileNotFoundError:
        return None
    except OSError:
        return "could not remove invocation-owned staging directory"
    except CheckpointTransitionOutputError:
        return "staging identity changed; cleanup was not attempted"
    return None


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        os.fsync(descriptor)
    except OSError as error:
        if error.errno not in {
            errno.EBADF,
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }:
            raise CheckpointTransitionOutputError(
                "cannot flush output directory"
            ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _reparse(value: os.stat_result) -> bool:
    return bool(
        getattr(value, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )
