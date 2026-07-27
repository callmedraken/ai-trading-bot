"""No-clobber output for canonical verified-snapshot paper-cycle reports."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from trading_bot.cli.exceptions import VerifiedSnapshotPaperCycleArtifactOutputError
from trading_bot.market_data import IdentifiedMarketCalendar
from trading_bot.runtime import (
    MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_BYTES,
    VerifiedSnapshotPaperCycleReportVerificationResult,
    VerifiedSnapshotPaperCycleResult,
    verify_verified_snapshot_paper_cycle_report,
)


@dataclass(frozen=True, slots=True)
class ValidatedVerifiedSnapshotPaperCycleDestination:
    """Identity of one existing real report-output directory."""

    path: Path
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleArtifactResult:
    """Immutable evidence for one finalized report artifact."""

    result: VerifiedSnapshotPaperCycleResult
    artifact_path: Path
    artifact_sha256: str
    artifact_byte_length: int
    staged_verification: VerifiedSnapshotPaperCycleReportVerificationResult
    cleanup_warning: str | None = None

    def __post_init__(self) -> None:
        if type(self.result) is not VerifiedSnapshotPaperCycleResult:
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "report result is invalid"
            )
        if not isinstance(self.artifact_path, Path):
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "report artifact path is invalid"
            )
        if (
            type(self.artifact_sha256) is not str
            or len(self.artifact_sha256) != 64
            or any(item not in "0123456789abcdef" for item in self.artifact_sha256)
        ):
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "report artifact SHA-256 is invalid"
            )
        if type(self.artifact_byte_length) is not int or self.artifact_byte_length < 0:
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "report artifact byte length is invalid"
            )
        verification = self.staged_verification
        if (
            type(verification) is not VerifiedSnapshotPaperCycleReportVerificationResult
            or not verification.passed
            or verification.result != self.result
        ):
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "staged report verification is invalid"
            )
        if self.cleanup_warning is not None and (
            type(self.cleanup_warning) is not str or not self.cleanup_warning
        ):
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "cleanup warning is invalid"
            )


def validate_verified_snapshot_paper_cycle_destination_directory(
    destination_directory: Path,
) -> ValidatedVerifiedSnapshotPaperCycleDestination:
    """Require one existing non-link real directory before report construction."""
    if not isinstance(destination_directory, Path):
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report destination directory is invalid"
        )
    normalized = Path(os.path.abspath(destination_directory))
    _require_real_parent_chain(normalized)
    try:
        retained = os.lstat(normalized)
    except OSError as error:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report destination must be an existing real directory"
        ) from error
    if (
        not stat.S_ISDIR(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _is_reparse_point(retained)
    ):
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report destination must be an existing real directory"
        )
    return ValidatedVerifiedSnapshotPaperCycleDestination(
        normalized,
        retained.st_dev,
        retained.st_ino,
    )


def install_verified_snapshot_paper_cycle_report(
    *,
    destination: ValidatedVerifiedSnapshotPaperCycleDestination,
    result: VerifiedSnapshotPaperCycleResult,
    payload: bytes,
    snapshot_payload: bytes,
    calendar: IdentifiedMarketCalendar,
    in_memory_verification: VerifiedSnapshotPaperCycleReportVerificationResult,
) -> VerifiedSnapshotPaperCycleArtifactResult:
    """Stage, replay-verify, and expose one deterministic no-clobber report."""
    if type(destination) is not ValidatedVerifiedSnapshotPaperCycleDestination:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report destination plan is invalid"
        )
    if (
        type(result) is not VerifiedSnapshotPaperCycleResult
        or type(payload) is not bytes
        or type(snapshot_payload) is not bytes
    ):
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report artifact input is invalid"
        )
    expected_hash = hashlib.sha256(payload).hexdigest()
    if (
        type(in_memory_verification)
        is not VerifiedSnapshotPaperCycleReportVerificationResult
        or not in_memory_verification.passed
        or in_memory_verification.result != result
        or in_memory_verification.report_sha256 != expected_hash
        or in_memory_verification.report_byte_length != len(payload)
    ):
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "in-memory report verification did not reconcile"
        )
    _require_destination_identity(destination)
    filename = f"verified-snapshot-paper-cycle-{result.result_id}.json"
    final_path = destination.path / filename
    staging_path = destination.path / f".{filename}.staging"
    _reject_casefold_entries(destination.path, {filename, staging_path.name})

    staging_created = False
    final_exposed = False
    staging_identity: tuple[int, int] | None = None
    try:
        staging_identity = _write_staging(staging_path, payload)
        staging_created = True
        staged_payload = _secure_read_staging(staging_path, staging_identity)
        staged_verification = verify_verified_snapshot_paper_cycle_report(
            staged_payload,
            snapshot_payload,
            calendar,
            expected_report_sha256=expected_hash,
            expected_report_byte_length=len(payload),
        )
        if (
            not staged_verification.passed
            or staged_verification.result != result
            or staged_verification.result is None
            or staged_verification.result.result_id != result.result_id
        ):
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "staged report verification failed"
            )

        _require_destination_identity(destination)
        _reject_casefold_entries(
            destination.path,
            {filename},
            allowed_names={staging_path.name},
        )
        _require_staging_identity(staging_path, staging_identity)
        _fsync_directory(destination.path, post_install=False)
        try:
            os.link(staging_path, final_path, follow_symlinks=False)
        except (OSError, NotImplementedError) as error:
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "cannot install report with a no-clobber hard link"
            ) from error
        final_exposed = True
        staging_created = False

        warnings: list[str] = []
        warning = _fsync_directory(destination.path, post_install=True)
        if warning is not None:
            warnings.append(warning)
        try:
            staging_path.unlink()
        except OSError:
            warnings.append("final report installed but staging unlink failed")
        warning = _fsync_directory(destination.path, post_install=True)
        if warning is not None:
            warnings.append(warning)
        return VerifiedSnapshotPaperCycleArtifactResult(
            result,
            final_path,
            expected_hash,
            len(payload),
            staged_verification,
            None if not warnings else "; ".join(dict.fromkeys(warnings)),
        )
    except Exception as primary:
        if final_exposed or not staging_created or staging_identity is None:
            if isinstance(primary, VerifiedSnapshotPaperCycleArtifactOutputError):
                raise
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "report staging or verification failed",
                primary_error=primary,
            ) from primary
        cleanup_message = _cleanup_owned_staging(staging_path, staging_identity)
        if cleanup_message is None:
            if isinstance(primary, VerifiedSnapshotPaperCycleArtifactOutputError):
                raise
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "report staging or verification failed",
                primary_error=primary,
            ) from primary
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            str(primary),
            cleanup_message=cleanup_message,
            primary_error=primary,
        ) from primary


def _write_staging(path: Path, payload: bytes) -> tuple[int, int]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "cannot exclusively create report staging file"
        ) from error
    staging_identity: tuple[int, int] | None = None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _is_reparse_point(opened):
                raise VerifiedSnapshotPaperCycleArtifactOutputError(
                    "report staging file is not regular"
                )
            staging_identity = (opened.st_dev, opened.st_ino)
            written = stream.write(payload)
            if written != len(payload):
                raise VerifiedSnapshotPaperCycleArtifactOutputError(
                    "report staging write was incomplete"
                )
            stream.flush()
            os.fsync(stream.fileno())
            return staging_identity
    except VerifiedSnapshotPaperCycleArtifactOutputError as primary:
        if staging_identity is None:
            raise
        cleanup_message = _cleanup_after_write_failure(path, staging_identity)
        if cleanup_message is None:
            raise
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            str(primary),
            cleanup_message=cleanup_message,
            primary_error=primary,
        ) from primary
    except OSError as error:
        primary = VerifiedSnapshotPaperCycleArtifactOutputError(
            "cannot write or flush report staging file"
        )
        if staging_identity is None:
            raise primary from error
        cleanup_message = _cleanup_after_write_failure(path, staging_identity)
        if cleanup_message is not None:
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                str(primary),
                cleanup_message=cleanup_message,
                primary_error=primary,
            ) from primary
        raise primary from error


def _secure_read_staging(path: Path, expected_identity: tuple[int, int]) -> bytes:
    retained = _require_staging_identity(path, expected_identity)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "cannot reopen report staging file"
        ) from error
    try:
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or _is_reparse_point(opened)
                or (opened.st_dev, opened.st_ino) != expected_identity
            ):
                raise VerifiedSnapshotPaperCycleArtifactOutputError(
                    "report staging file changed before verification"
                )
            chunks: list[bytes] = []
            length = 0
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                length += len(chunk)
                if length > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_BYTES:
                    raise VerifiedSnapshotPaperCycleArtifactOutputError(
                        "report staging file exceeds the 16 MiB limit"
                    )
                chunks.append(chunk)
            after = os.fstat(stream.fileno())
    except VerifiedSnapshotPaperCycleArtifactOutputError:
        raise
    except OSError as error:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "cannot read report staging file"
        ) from error
    if (
        (retained.st_dev, retained.st_ino) != (after.st_dev, after.st_ino)
        or retained.st_size != after.st_size
        or retained.st_mtime_ns != after.st_mtime_ns
    ):
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report staging file changed during verification"
        )
    return b"".join(chunks)


def _reject_casefold_entries(
    directory: Path,
    rejected_names: set[str],
    *,
    allowed_names: set[str] | None = None,
) -> None:
    rejected = {item.casefold() for item in rejected_names}
    allowed = (
        set() if allowed_names is None else {item.casefold() for item in allowed_names}
    )
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                folded = entry.name.casefold()
                if folded in rejected and folded not in allowed:
                    raise VerifiedSnapshotPaperCycleArtifactOutputError(
                        "report final or staging entry already exists"
                    )
    except VerifiedSnapshotPaperCycleArtifactOutputError:
        raise
    except OSError as error:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "cannot inspect report destination entries"
        ) from error


def _require_destination_identity(
    destination: ValidatedVerifiedSnapshotPaperCycleDestination,
) -> None:
    try:
        current = os.lstat(destination.path)
    except OSError as error:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report destination changed after preflight"
        ) from error
    if (
        not stat.S_ISDIR(current.st_mode)
        or stat.S_ISLNK(current.st_mode)
        or _is_reparse_point(current)
        or (current.st_dev, current.st_ino) != (destination.device, destination.inode)
    ):
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report destination changed after preflight"
        )


def _require_real_parent_chain(path: Path) -> None:
    current = path
    while True:
        try:
            retained = os.lstat(current)
        except OSError as error:
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "report destination has an unsafe parent"
            ) from error
        if stat.S_ISLNK(retained.st_mode) or _is_reparse_point(retained):
            raise VerifiedSnapshotPaperCycleArtifactOutputError(
                "report destination has an unsafe parent"
            )
        parent = current.parent
        if parent == current:
            return
        current = parent


def _require_staging_identity(
    path: Path,
    expected_identity: tuple[int, int],
) -> os.stat_result:
    try:
        retained = os.lstat(path)
    except OSError as error:
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report staging file is unavailable"
        ) from error
    if (
        not stat.S_ISREG(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _is_reparse_point(retained)
        or (retained.st_dev, retained.st_ino) != expected_identity
    ):
        raise VerifiedSnapshotPaperCycleArtifactOutputError(
            "report staging file identity changed"
        )
    return retained


def _cleanup_owned_staging(
    path: Path,
    expected_identity: tuple[int, int],
) -> str | None:
    try:
        retained = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        return "could not inspect invocation-owned report staging file"
    if (
        not stat.S_ISREG(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _is_reparse_point(retained)
        or (retained.st_dev, retained.st_ino) != expected_identity
    ):
        return "report staging identity changed; cleanup was not attempted"
    try:
        path.unlink()
    except OSError:
        return "could not remove invocation-owned report staging file"
    return None


def _cleanup_after_write_failure(
    path: Path,
    identity: tuple[int, int],
) -> str | None:
    return _cleanup_owned_staging(path, identity)


def _fsync_directory(path: Path, *, post_install: bool) -> str | None:
    if os.name == "nt":
        return None
    descriptor: int | None = None
    warning: str | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        os.fsync(descriptor)
    except OSError as error:
        unsupported = error.errno in {
            errno.EBADF,
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
        if not unsupported:
            if post_install:
                warning = "final report installed but directory durability flush failed"
            else:
                raise VerifiedSnapshotPaperCycleArtifactOutputError(
                    "cannot flush report destination directory"
                ) from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                if post_install:
                    warning = "final report installed but directory handle close failed"
                else:
                    raise VerifiedSnapshotPaperCycleArtifactOutputError(
                        "cannot close report destination directory handle"
                    ) from error
    return warning


def _is_reparse_point(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)
