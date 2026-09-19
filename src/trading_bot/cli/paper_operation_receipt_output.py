"""Fixed-layout, no-clobber finalization for immutable paper-operation receipts."""

from __future__ import annotations

import errno
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.cli.checkpoint_transition_output import OutputParent
from trading_bot.cli.paper_operation_output_capability import (
    PaperOperationOutputCapability,
    require_output_capability,
)
from trading_bot.runtime import MAX_PAPER_OPERATION_RECEIPT_BYTES

MAX_OPERATION_DIRECTORY_ENTRIES = 10_000
OPERATIONS_DIRECTORY_NAME = "paper-operations"


class PaperOperationReceiptOutputError(Exception):
    """Raised when receipt staging or finalization cannot proceed safely."""


class ReceiptCommitVerificationPhase(StrEnum):
    """The two durable reread points in a receipt commit."""

    STAGED_REREAD = "STAGED_REREAD"
    FINALIZED_REREAD = "FINALIZED_REREAD"


@dataclass(frozen=True, slots=True)
class PaperOperationReceiptDirectoryResult:
    directory: Path
    receipt_path: Path
    payload: bytes


@dataclass(frozen=True, slots=True)
class _DirectoryIdentity:
    path: Path
    device: int
    inode: int


def commit_paper_operation_receipt(
    parent: OutputParent,
    *,
    operation_id: UUID,
    receipt_payload: bytes,
    verifier: Callable[[bytes, ReceiptCommitVerificationPhase], None],
    output_capability: PaperOperationOutputCapability | None = None,
) -> PaperOperationReceiptDirectoryResult:
    """Stage, verify, and no-clobber finalize one canonical receipt."""
    if (
        type(parent) is not OutputParent
        or type(operation_id) is not UUID
        or type(receipt_payload) is not bytes
        or not receipt_payload
        or len(receipt_payload) > MAX_PAPER_OPERATION_RECEIPT_BYTES
        or not callable(verifier)
    ):
        raise PaperOperationReceiptOutputError("receipt commit input is invalid")

    try:
        capability = require_output_capability(output_capability)
    except TypeError as error:
        raise PaperOperationReceiptOutputError(
            "receipt output capability is invalid"
        ) from error
    _require_output_parent(parent)
    if capability is not None:
        capability.verify_parent(parent.path)
    operations = _ensure_operations_parent(parent, capability)
    operation_name = f"paper-operation-{operation_id}"
    staging_name = f".{operation_name}.staging"
    receipt_name = f"paper-operation-receipt-{operation_id}.json"
    staging = operations.path / staging_name
    final = operations.path / operation_name
    _reject_collisions(operations.path, {operation_name, staging_name})

    try:
        if capability is None:
            os.mkdir(staging)
        else:
            capability.create_staging_directory(staging)
            capability.verify_staged_directory(staging)
    except Exception as error:
        raise PaperOperationReceiptOutputError(
            "cannot exclusively create receipt staging directory"
        ) from error
    retained = _lstat_directory(staging, "receipt staging directory")
    staging_identity = (retained.st_dev, retained.st_ino)
    if capability is None:
        _write_file(staging / receipt_name, receipt_payload)
    else:
        capability.write_staged_file(staging / receipt_name, receipt_payload)
        capability.verify_staged_file(staging / receipt_name)
    _fsync_directory(staging)
    _verify_fixed_layout(staging, receipt_name)
    staged_payload = _read_receipt(staging / receipt_name, "staged receipt")
    verifier(staged_payload, ReceiptCommitVerificationPhase.STAGED_REREAD)

    _require_output_parent(parent)
    if capability is not None:
        capability.verify_parent(parent.path)
        capability.verify_parent(operations.path)
    _require_directory(operations, "paper-operations directory")
    _require_directory_identity(staging, staging_identity, "receipt staging directory")
    _verify_fixed_layout(staging, receipt_name)
    if _read_receipt(staging / receipt_name, "staged receipt") != staged_payload:
        raise PaperOperationReceiptOutputError(
            "staged receipt changed after verification"
        )
    _reject_collisions(
        operations.path,
        {operation_name},
        allowed={staging_name},
    )
    if _entry_exists(final):
        raise PaperOperationReceiptOutputError("final receipt directory already exists")
    _fsync_directory(operations.path)
    try:
        if capability is None:
            os.rename(staging, final)
        else:
            capability.finalize_directory(staging, final)
    except Exception as error:
        raise PaperOperationReceiptOutputError(
            "cannot finalize staged receipt directory"
        ) from error
    _fsync_directory(operations.path)

    _require_output_parent(parent)
    _require_directory(operations, "paper-operations directory")
    _require_directory_identity(final, staging_identity, "final receipt directory")
    _verify_fixed_layout(final, receipt_name)
    if capability is not None:
        capability.verify_finalized_directory(final)
        capability.verify_finalized_file(final / receipt_name)
    finalized_payload = _read_receipt(final / receipt_name, "finalized receipt")
    verifier(finalized_payload, ReceiptCommitVerificationPhase.FINALIZED_REREAD)
    _require_output_parent(parent)
    _require_directory(operations, "paper-operations directory")
    _require_directory_identity(final, staging_identity, "final receipt directory")
    _verify_fixed_layout(final, receipt_name)
    if _read_receipt(final / receipt_name, "finalized receipt") != finalized_payload:
        raise PaperOperationReceiptOutputError(
            "finalized receipt changed after verification"
        )
    return PaperOperationReceiptDirectoryResult(
        final,
        final / receipt_name,
        finalized_payload,
    )


def _ensure_operations_parent(
    parent: OutputParent,
    capability: PaperOperationOutputCapability | None = None,
) -> _DirectoryIdentity:
    _require_output_parent(parent)
    matches = _casefold_matches(parent.path, OPERATIONS_DIRECTORY_NAME)
    if matches:
        if matches != (OPERATIONS_DIRECTORY_NAME,):
            raise PaperOperationReceiptOutputError(
                "paper-operations directory has a case-fold collision"
            )
    else:
        if capability is not None:
            raise PaperOperationReceiptOutputError(
                "paper-operations directory must already exist"
            )
        try:
            os.mkdir(parent.path / OPERATIONS_DIRECTORY_NAME)
        except OSError as error:
            raise PaperOperationReceiptOutputError(
                "cannot create paper-operations directory"
            ) from error
        _fsync_directory(parent.path)
    _require_output_parent(parent)
    if _casefold_matches(parent.path, OPERATIONS_DIRECTORY_NAME) != (
        OPERATIONS_DIRECTORY_NAME,
    ):
        raise PaperOperationReceiptOutputError(
            "paper-operations directory has a case-fold collision"
        )
    path = parent.path / OPERATIONS_DIRECTORY_NAME
    if capability is not None:
        capability.verify_parent(path)
    retained = _lstat_directory(path, "paper-operations directory")
    return _DirectoryIdentity(path, retained.st_dev, retained.st_ino)


def _casefold_matches(directory: Path, wanted: str) -> tuple[str, ...]:
    try:
        entries = tuple(os.scandir(directory))
    except OSError as error:
        raise PaperOperationReceiptOutputError(
            "cannot inspect output directory"
        ) from error
    if len(entries) > MAX_OPERATION_DIRECTORY_ENTRIES:
        raise PaperOperationReceiptOutputError("output enumeration limit exceeded")
    folded: dict[str, str] = {}
    for entry in entries:
        key = entry.name.casefold()
        previous = folded.get(key)
        if previous is not None and previous != entry.name:
            raise PaperOperationReceiptOutputError(
                "output directory has a case-fold collision"
            )
        folded[key] = entry.name
    return tuple(
        entry.name for entry in entries if entry.name.casefold() == wanted.casefold()
    )


def _reject_collisions(
    directory: Path,
    names: set[str],
    *,
    allowed: set[str] | None = None,
) -> None:
    entries = _casefold_matches_for_names(directory, names)
    accepted = {name.casefold() for name in allowed or set()}
    if any(name.casefold() not in accepted for name in entries):
        raise PaperOperationReceiptOutputError(
            "receipt final or staging entry already exists"
        )


def _casefold_matches_for_names(directory: Path, names: set[str]) -> tuple[str, ...]:
    wanted = {name.casefold() for name in names}
    try:
        entries = tuple(os.scandir(directory))
    except OSError as error:
        raise PaperOperationReceiptOutputError(
            "cannot inspect receipt parent"
        ) from error
    if len(entries) > MAX_OPERATION_DIRECTORY_ENTRIES:
        raise PaperOperationReceiptOutputError("output enumeration limit exceeded")
    folded: set[str] = set()
    matches: list[str] = []
    for entry in entries:
        key = entry.name.casefold()
        if key in folded:
            raise PaperOperationReceiptOutputError(
                "receipt parent has a case-fold collision"
            )
        folded.add(key)
        if key in wanted:
            matches.append(entry.name)
    return tuple(matches)


def _write_file(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            retained = os.fstat(stream.fileno())
            if not stat.S_ISREG(retained.st_mode) or _reparse(retained):
                raise PaperOperationReceiptOutputError("receipt staging file is unsafe")
            if stream.write(payload) != len(payload):
                raise PaperOperationReceiptOutputError(
                    "receipt staging write was incomplete"
                )
            stream.flush()
            os.fsync(stream.fileno())
    except PaperOperationReceiptOutputError:
        raise
    except OSError as error:
        raise PaperOperationReceiptOutputError("cannot write staged receipt") from error


def _verify_fixed_layout(directory: Path, receipt_name: str) -> None:
    try:
        entries = tuple(os.scandir(directory))
    except OSError as error:
        raise PaperOperationReceiptOutputError(
            "cannot inspect receipt directory"
        ) from error
    if len(entries) != 1 or entries[0].name != receipt_name:
        raise PaperOperationReceiptOutputError("receipt directory layout is unexpected")
    entry = entries[0]
    try:
        retained = os.lstat(directory / entry.name)
    except OSError as error:
        raise PaperOperationReceiptOutputError("receipt file is unavailable") from error
    if (
        not stat.S_ISREG(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _reparse(retained)
    ):
        raise PaperOperationReceiptOutputError("receipt directory layout is unsafe")


def _read_receipt(path: Path, label: str) -> bytes:
    try:
        return read_safe_regular_file(
            path,
            MAX_PAPER_OPERATION_RECEIPT_BYTES,
            label,
        )
    except Exception as error:
        raise PaperOperationReceiptOutputError(
            f"{label} cannot be read safely"
        ) from error


def _require_output_parent(parent: OutputParent) -> None:
    if type(parent) is not OutputParent:
        raise PaperOperationReceiptOutputError("output parent is invalid")
    retained = _lstat_directory(parent.path, "output parent")
    if (retained.st_dev, retained.st_ino) != (parent.device, parent.inode):
        raise PaperOperationReceiptOutputError("output parent changed after preflight")


def _require_directory(directory: _DirectoryIdentity, label: str) -> None:
    retained = _lstat_directory(directory.path, label)
    if (retained.st_dev, retained.st_ino) != (directory.device, directory.inode):
        raise PaperOperationReceiptOutputError(f"{label} changed during commit")


def _require_directory_identity(
    path: Path,
    identity: tuple[int, int],
    label: str,
) -> None:
    retained = _lstat_directory(path, label)
    if (retained.st_dev, retained.st_ino) != identity:
        raise PaperOperationReceiptOutputError(f"{label} changed during commit")


def _lstat_directory(path: Path, label: str) -> os.stat_result:
    try:
        retained = os.lstat(path)
    except OSError as error:
        raise PaperOperationReceiptOutputError(f"{label} is unavailable") from error
    if (
        not stat.S_ISDIR(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _reparse(retained)
    ):
        raise PaperOperationReceiptOutputError(f"{label} is unsafe")
    return retained


def _entry_exists(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise PaperOperationReceiptOutputError(
            "cannot inspect receipt entry"
        ) from error
    return True


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
            raise PaperOperationReceiptOutputError(
                "cannot flush receipt directory"
            ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _reparse(value: os.stat_result) -> bool:
    return bool(
        getattr(value, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )
