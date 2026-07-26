"""No-clobber staged output for canonical daily-snapshot artifacts."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from trading_bot.cli.exceptions import DailySnapshotArtifactOutputError
from trading_bot.market_data import (
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    DailyMarketDataSnapshot,
    DailySnapshotVerificationResult,
    IdentifiedMarketCalendar,
    verify_daily_snapshot,
)


@dataclass(frozen=True, slots=True)
class ValidatedDailySnapshotDestination:
    """Identity of an existing real destination directory."""

    path: Path
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class DailySnapshotArtifactResult:
    """Immutable evidence for one finalized canonical snapshot artifact."""

    snapshot: DailyMarketDataSnapshot
    artifact_path: Path
    artifact_sha256: str
    artifact_byte_length: int
    staged_verification: DailySnapshotVerificationResult
    cleanup_warning: str | None = None

    def __post_init__(self) -> None:
        if type(self.snapshot) is not DailyMarketDataSnapshot:
            raise DailySnapshotArtifactOutputError("snapshot result is invalid")
        if not isinstance(self.artifact_path, Path):
            raise DailySnapshotArtifactOutputError("artifact path is invalid")
        if (
            type(self.artifact_sha256) is not str
            or len(self.artifact_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.artifact_sha256
            )
        ):
            raise DailySnapshotArtifactOutputError("artifact SHA-256 is invalid")
        if type(self.artifact_byte_length) is not int or self.artifact_byte_length < 0:
            raise DailySnapshotArtifactOutputError("artifact byte length is invalid")
        if (
            type(self.staged_verification) is not DailySnapshotVerificationResult
            or not self.staged_verification.passed
            or self.staged_verification.snapshot != self.snapshot
        ):
            raise DailySnapshotArtifactOutputError(
                "staged verification result is invalid"
            )
        if self.cleanup_warning is not None and (
            type(self.cleanup_warning) is not str or not self.cleanup_warning
        ):
            raise DailySnapshotArtifactOutputError("cleanup warning is invalid")


def validate_daily_snapshot_destination_directory(
    destination_directory: Path,
) -> ValidatedDailySnapshotDestination:
    """Require one existing, non-link, regular destination directory."""
    if not isinstance(destination_directory, Path):
        raise DailySnapshotArtifactOutputError("destination directory must be a Path")
    normalized = Path(os.path.abspath(destination_directory))
    try:
        retained = os.lstat(normalized)
    except OSError as error:
        raise DailySnapshotArtifactOutputError(
            "destination must be an existing real directory"
        ) from error
    if (
        not stat.S_ISDIR(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _is_reparse_point(retained)
    ):
        raise DailySnapshotArtifactOutputError(
            "destination must be an existing real directory"
        )
    return ValidatedDailySnapshotDestination(
        normalized,
        retained.st_dev,
        retained.st_ino,
    )


def install_daily_snapshot_artifact(
    *,
    destination: ValidatedDailySnapshotDestination,
    snapshot: DailyMarketDataSnapshot,
    payload: bytes,
    in_memory_verification: DailySnapshotVerificationResult,
    calendar: IdentifiedMarketCalendar,
) -> DailySnapshotArtifactResult:
    """Stage, verify, and atomically expose one no-clobber artifact."""
    if type(destination) is not ValidatedDailySnapshotDestination:
        raise DailySnapshotArtifactOutputError("destination plan is invalid")
    if type(snapshot) is not DailyMarketDataSnapshot or type(payload) is not bytes:
        raise DailySnapshotArtifactOutputError("snapshot artifact input is invalid")
    if (
        type(in_memory_verification) is not DailySnapshotVerificationResult
        or not in_memory_verification.passed
        or in_memory_verification.snapshot != snapshot
        or in_memory_verification.byte_length != len(payload)
        or in_memory_verification.sha256 != hashlib.sha256(payload).hexdigest()
    ):
        raise DailySnapshotArtifactOutputError(
            "in-memory snapshot verification did not reconcile"
        )
    _require_destination_identity(destination)
    filename = f"daily-market-data-snapshot-{snapshot.snapshot_id}.json"
    final_path = destination.path / filename
    staging_path = destination.path / f".{filename}.staging"
    _reject_casefold_entries(destination.path, {filename, staging_path.name})

    staging_created = False
    final_exposed = False
    staging_identity: tuple[int, int] | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(staging_path, flags, 0o600)
            staging_created = True
        except OSError as error:
            raise DailySnapshotArtifactOutputError(
                "cannot exclusively create snapshot staging file"
            ) from error
        try:
            with os.fdopen(descriptor, "wb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or _is_reparse_point(opened):
                    raise DailySnapshotArtifactOutputError(
                        "snapshot staging file is not regular"
                    )
                staging_identity = (opened.st_dev, opened.st_ino)
                written = stream.write(payload)
                if written != len(payload):
                    raise DailySnapshotArtifactOutputError(
                        "snapshot staging write was incomplete"
                    )
                stream.flush()
                os.fsync(stream.fileno())
        except DailySnapshotArtifactOutputError:
            raise
        except OSError as error:
            raise DailySnapshotArtifactOutputError(
                "cannot write or flush snapshot staging file"
            ) from error

        staged_bytes = _secure_read_staging(staging_path, staging_identity)
        staged_verification = verify_daily_snapshot(
            staged_bytes,
            calendar,
            expected_sha256=in_memory_verification.sha256,
            expected_byte_length=in_memory_verification.byte_length,
        )
        if (
            not staged_verification.passed
            or staged_verification.snapshot != snapshot
            or staged_verification.snapshot is None
            or staged_verification.snapshot.snapshot_id != snapshot.snapshot_id
        ):
            raise DailySnapshotArtifactOutputError(
                "staged snapshot verification failed"
            )

        _require_destination_identity(destination)
        _reject_casefold_entries(
            destination.path,
            {filename},
            allowed_names={staging_path.name},
        )
        _require_staging_identity(staging_path, staging_identity)
        _fsync_directory(destination.path, post_install=False)

        base_result = DailySnapshotArtifactResult(
            snapshot=snapshot,
            artifact_path=final_path,
            artifact_sha256=in_memory_verification.sha256,
            artifact_byte_length=in_memory_verification.byte_length,
            staged_verification=staged_verification,
        )
        try:
            os.link(staging_path, final_path, follow_symlinks=False)
        except (OSError, NotImplementedError) as error:
            raise DailySnapshotArtifactOutputError(
                "cannot install snapshot with a no-clobber hard link"
            ) from error
        final_exposed = True
        staging_created = False

        warnings: list[str] = []
        durability_warning = _fsync_directory(
            destination.path,
            post_install=True,
        )
        if durability_warning is not None:
            warnings.append(durability_warning)
        try:
            staging_path.unlink()
        except OSError:
            warnings.append("final artifact installed but staging unlink failed")
        durability_warning = _fsync_directory(
            destination.path,
            post_install=True,
        )
        if durability_warning is not None:
            warnings.append(durability_warning)
        if not warnings:
            return base_result
        return DailySnapshotArtifactResult(
            snapshot=base_result.snapshot,
            artifact_path=base_result.artifact_path,
            artifact_sha256=base_result.artifact_sha256,
            artifact_byte_length=base_result.artifact_byte_length,
            staged_verification=base_result.staged_verification,
            cleanup_warning="; ".join(dict.fromkeys(warnings)),
        )
    except Exception as primary:
        if final_exposed or not staging_created or staging_identity is None:
            raise
        cleanup_message = _cleanup_owned_staging(staging_path, staging_identity)
        if cleanup_message is None:
            raise
        raise DailySnapshotArtifactOutputError(
            str(primary),
            cleanup_message=cleanup_message,
            primary_error=primary,
        ) from primary


def _secure_read_staging(
    path: Path,
    expected_identity: tuple[int, int],
) -> bytes:
    retained = _require_staging_identity(path, expected_identity)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise DailySnapshotArtifactOutputError(
            "cannot reopen snapshot staging file"
        ) from error
    try:
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or _is_reparse_point(opened)
                or (opened.st_dev, opened.st_ino) != expected_identity
            ):
                raise DailySnapshotArtifactOutputError(
                    "snapshot staging file changed before verification"
                )
            chunks: list[bytes] = []
            length = 0
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                length += len(chunk)
                if length > MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES:
                    raise DailySnapshotArtifactOutputError(
                        "snapshot staging file exceeds the 4 MiB limit"
                    )
                chunks.append(chunk)
            after = os.fstat(stream.fileno())
    except DailySnapshotArtifactOutputError:
        raise
    except OSError as error:
        raise DailySnapshotArtifactOutputError(
            "cannot read snapshot staging file"
        ) from error
    if (
        (retained.st_dev, retained.st_ino) != (after.st_dev, after.st_ino)
        or retained.st_size != after.st_size
        or retained.st_mtime_ns != after.st_mtime_ns
    ):
        raise DailySnapshotArtifactOutputError(
            "snapshot staging file changed during verification"
        )
    return b"".join(chunks)


def _reject_casefold_entries(
    directory: Path,
    rejected_names: set[str],
    *,
    allowed_names: set[str] | None = None,
) -> None:
    rejected = {name.casefold() for name in rejected_names}
    allowed = (
        set() if allowed_names is None else {name.casefold() for name in allowed_names}
    )
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                folded = entry.name.casefold()
                if folded in rejected and folded not in allowed:
                    raise DailySnapshotArtifactOutputError(
                        "snapshot final or staging entry already exists"
                    )
    except DailySnapshotArtifactOutputError:
        raise
    except OSError as error:
        raise DailySnapshotArtifactOutputError(
            "cannot inspect snapshot destination entries"
        ) from error


def _require_destination_identity(
    destination: ValidatedDailySnapshotDestination,
) -> None:
    try:
        current = os.lstat(destination.path)
    except OSError as error:
        raise DailySnapshotArtifactOutputError(
            "snapshot destination changed after preflight"
        ) from error
    if (
        not stat.S_ISDIR(current.st_mode)
        or stat.S_ISLNK(current.st_mode)
        or _is_reparse_point(current)
        or (current.st_dev, current.st_ino) != (destination.device, destination.inode)
    ):
        raise DailySnapshotArtifactOutputError(
            "snapshot destination changed after preflight"
        )


def _require_staging_identity(
    path: Path,
    expected_identity: tuple[int, int],
) -> os.stat_result:
    try:
        retained = os.lstat(path)
    except OSError as error:
        raise DailySnapshotArtifactOutputError(
            "snapshot staging file is unavailable"
        ) from error
    if (
        not stat.S_ISREG(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _is_reparse_point(retained)
        or (retained.st_dev, retained.st_ino) != expected_identity
    ):
        raise DailySnapshotArtifactOutputError("snapshot staging file identity changed")
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
        return "could not inspect invocation-owned snapshot staging file"
    if (
        not stat.S_ISREG(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _is_reparse_point(retained)
        or (retained.st_dev, retained.st_ino) != expected_identity
    ):
        return "snapshot staging identity changed; cleanup was not attempted"
    try:
        path.unlink()
    except OSError:
        return "could not remove invocation-owned snapshot staging file"
    return None


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
        if unsupported:
            warning = None
        elif post_install:
            warning = "final artifact installed but directory durability flush failed"
        else:
            raise DailySnapshotArtifactOutputError(
                "cannot flush snapshot destination directory"
            ) from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                if post_install:
                    warning = (
                        "final artifact installed but directory handle close failed"
                    )
                else:
                    raise DailySnapshotArtifactOutputError(
                        "cannot close snapshot destination directory handle"
                    ) from error
    return warning


def _is_reparse_point(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)
