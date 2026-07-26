"""Deterministic restoration of canonical research-bundle archives."""

import errno
import hashlib
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from trading_bot.cli.exceptions import (
    ResearchSessionArchiveStructureError,
    ResearchSessionBundlePlanError,
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
    ResearchSessionRestoreArgumentError,
    ResearchSessionRestoreOutputError,
)
from trading_bot.cli.research_session_archive import (
    CanonicalUstarEntry,
    ResearchSessionArchiveEntryEvidence,
    WalkForwardResearchArchiveVerificationResult,
    stream_canonical_walk_forward_research_bundle_archive,
    verify_walk_forward_research_bundle_archive,
)
from trading_bot.cli.research_session_bundle import (
    relocate_walk_forward_research_session_manifest_for_bundle,
)
from trading_bot.cli.research_session_manifest import (
    ResearchSessionArtifactVerificationStatus,
    ResearchSessionManifestVerificationResult,
    WalkForwardResearchSessionManifest,
    load_walk_forward_research_session_manifest,
    verify_walk_forward_research_session_manifest,
)


@dataclass(frozen=True, slots=True)
class ResearchSessionArchiveRestoreEntryEvidence:
    """Exact staged-file evidence for one restored archive entry."""

    position: int
    path: str
    byte_length: int
    sha256: str

    def __post_init__(self) -> None:
        CanonicalUstarEntry(self.position, self.path, self.byte_length)
        if (
            type(self.sha256) is not str
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise TypeError("sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class WalkForwardResearchArchiveRestoreResult:
    """Immutable evidence for one finalized restored portable bundle."""

    archive_path: Path
    bundle_path: Path
    manifest_path: Path
    manifest: WalkForwardResearchSessionManifest
    archive_byte_length: int
    archive_sha256: str
    entries: tuple[ResearchSessionArchiveRestoreEntryEvidence, ...]
    archive_verification: WalkForwardResearchArchiveVerificationResult
    verification: ResearchSessionManifestVerificationResult

    def __post_init__(self) -> None:
        for name in ("archive_path", "bundle_path", "manifest_path"):
            value = getattr(self, name)
            if not isinstance(value, Path) or not value.is_absolute():
                raise TypeError(f"{name} must be an absolute Path")
        if self.manifest_path != self.bundle_path / "manifest.json":
            raise ValueError("manifest_path must be bundle_path/manifest.json")
        if type(self.manifest) is not WalkForwardResearchSessionManifest:
            raise TypeError(
                "manifest must be an exact WalkForwardResearchSessionManifest"
            )
        if type(self.archive_byte_length) is not int or self.archive_byte_length < 0:
            raise TypeError("archive_byte_length must be an exact nonnegative integer")
        if (
            type(self.archive_sha256) is not str
            or len(self.archive_sha256) != 64
            or any(
                character not in "0123456789abcdef" for character in self.archive_sha256
            )
        ):
            raise TypeError("archive_sha256 must be a lowercase SHA-256 digest")
        if type(self.entries) is not tuple or not all(
            type(item) is ResearchSessionArchiveRestoreEntryEvidence
            for item in self.entries
        ):
            raise TypeError("entries must be an exact tuple of restore evidence")
        if tuple(item.position for item in self.entries) != tuple(
            range(1, len(self.entries) + 1)
        ):
            raise ValueError("restore entry positions must be contiguous")
        expected_paths = ("manifest.json",) + tuple(
            artifact.path for artifact in self.manifest.artifacts
        )
        if tuple(item.path for item in self.entries) != expected_paths:
            raise ValueError("restore evidence must retain exact manifest entry order")
        if (
            type(self.archive_verification)
            is not WalkForwardResearchArchiveVerificationResult
        ):
            raise TypeError(
                "archive_verification must be an exact archive verification result"
            )
        if (
            self.archive_verification.archive_path != self.archive_path
            or self.archive_verification.manifest != self.manifest
            or self.archive_verification.archive_byte_length != self.archive_byte_length
            or self.archive_verification.archive_sha256 != self.archive_sha256
            or tuple(
                (item.position, item.path, item.byte_length, item.sha256)
                for item in self.entries
            )
            != tuple(
                (item.position, item.path, item.byte_length, item.sha256)
                for item in self.archive_verification.entries
            )
        ):
            raise ValueError("archive verification must reconcile with restoration")
        if type(self.verification) is not ResearchSessionManifestVerificationResult:
            raise TypeError(
                "verification must be an exact manifest verification result"
            )
        if self.verification.manifest != self.manifest or not self.verification.passed:
            raise ValueError("verification must be a complete PASS for manifest")


def _is_reparse_point(result: os.stat_result) -> bool:
    attributes = getattr(result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ResearchSessionRestoreOutputError(
            "cannot inspect restoration destination entry"
        ) from error
    return True


def _accepted_real_directory(path: Path) -> bool:
    try:
        result = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(result.st_mode)
        and not stat.S_ISLNK(result.st_mode)
        and not _is_reparse_point(result)
    )


def _normalized_destination(path: Path) -> Path:
    absolute = path if path.is_absolute() else Path.cwd() / path
    if absolute.name in {"", ".", ".."}:
        raise ResearchSessionRestoreArgumentError(
            "destination must name one directory entry"
        )
    return Path(os.path.abspath(absolute))


def _fsync_directory(path: Path, *, best_effort: bool = False) -> None:
    if os.name == "nt":
        return
    descriptor: int | None = None
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
        if not best_effort and not unsupported:
            raise ResearchSessionRestoreOutputError(
                "cannot flush restoration directory"
            ) from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                if not best_effort:
                    raise ResearchSessionRestoreOutputError(
                        "cannot close restoration directory handle"
                    ) from error


def _staging_identity(path: Path) -> tuple[int, int]:
    try:
        result = path.lstat()
    except OSError as error:
        raise ResearchSessionRestoreOutputError(
            "cannot inspect created restoration staging directory"
        ) from error
    if (
        not stat.S_ISDIR(result.st_mode)
        or stat.S_ISLNK(result.st_mode)
        or _is_reparse_point(result)
    ):
        raise ResearchSessionRestoreOutputError(
            "created restoration staging entry is not a real directory"
        )
    return result.st_dev, result.st_ino


def _cleanup_staging(path: Path, identity: tuple[int, int] | None) -> str | None:
    if identity is None:
        return f"could not confirm restoration staging ownership: {path}"
    try:
        result = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        return f"could not inspect restoration staging directory: {path}"
    if (
        not stat.S_ISDIR(result.st_mode)
        or stat.S_ISLNK(result.st_mode)
        or _is_reparse_point(result)
        or (result.st_dev, result.st_ino) != identity
    ):
        return f"restoration staging entry changed; cleanup refused: {path}"
    try:
        shutil.rmtree(path)
    except OSError:
        return f"could not remove restoration staging directory: {path}"
    return None


def _fixed_bundle_manifest(
    manifest: WalkForwardResearchSessionManifest,
) -> WalkForwardResearchSessionManifest:
    try:
        expected = relocate_walk_forward_research_session_manifest_for_bundle(manifest)
    except ResearchSessionBundlePlanError as error:
        raise ResearchSessionArchiveStructureError(
            "embedded manifest bundle paths are invalid"
        ) from error
    if expected != manifest or expected.manifest_id != manifest.manifest_id:
        raise ResearchSessionArchiveStructureError(
            "embedded manifest does not use the fixed portable bundle layout"
        )
    expected_paths = ("manifest.json",) + tuple(
        artifact.path for artifact in manifest.artifacts
    )
    if len(set(expected_paths)) != len(expected_paths) or len(
        {path.casefold() for path in expected_paths}
    ) != len(expected_paths):
        raise ResearchSessionArchiveStructureError(
            "embedded manifest bundle paths collide"
        )
    return manifest


def _write_all(stream: BinaryIO, content: bytes) -> None:
    remaining = memoryview(content)
    while remaining:
        try:
            written = stream.write(remaining)
        except OSError as error:
            raise ResearchSessionRestoreOutputError(
                "cannot write staged restoration entry"
            ) from error
        if written is None or written < 1:
            raise ResearchSessionRestoreOutputError(
                "cannot complete staged restoration entry write"
            )
        remaining = remaining[written:]


class _RestoreConsumer:
    def __init__(
        self,
        *,
        staging_path: Path,
        manifest: WalkForwardResearchSessionManifest,
        staging_identity: tuple[int, int],
        artifacts_identity: tuple[int, int],
    ) -> None:
        self._staging_path = staging_path
        self._manifest = manifest
        self._staging_identity = staging_identity
        self._artifacts_identity = artifacts_identity
        self._expected_paths = ("manifest.json",) + tuple(
            artifact.path for artifact in manifest.artifacts
        )
        self._stream: BinaryIO | None = None
        self._entry: CanonicalUstarEntry | None = None
        self._digest = hashlib.sha256()
        self._byte_length = 0
        self._manifest_reconciled = False
        self.entries: list[ResearchSessionArchiveRestoreEntryEvidence] = []

    def start_entry(self, entry: CanonicalUstarEntry) -> None:
        if type(entry.position) is not int or entry.position < 1:
            raise ResearchSessionArchiveStructureError(
                "archive entry position must be an exact positive integer"
            )
        if self._stream is not None or self._entry is not None:
            raise ResearchSessionRestoreOutputError(
                "previous staged restoration entry is still open"
            )
        if entry.position > len(self._expected_paths):
            raise ResearchSessionArchiveStructureError(
                "archive contains an unexpected restoration entry"
            )
        expected_path = self._expected_paths[entry.position - 1]
        if entry.path != expected_path:
            raise ResearchSessionArchiveStructureError(
                "archive path does not match restored bundle layout"
            )
        if entry.position > 1 and not self._manifest_reconciled:
            raise ResearchSessionArchiveStructureError(
                "archive artifact preceded reconciled embedded manifest"
            )
        if _staging_identity(self._staging_path) != self._staging_identity:
            raise ResearchSessionRestoreOutputError(
                "restoration staging directory changed during extraction"
            )
        if entry.position > 1 and (
            _staging_identity(self._staging_path / "artifacts")
            != self._artifacts_identity
        ):
            raise ResearchSessionRestoreOutputError(
                "restoration artifacts directory changed during extraction"
            )
        destination = self._staging_path.joinpath(*PurePosixPath(entry.path).parts)
        try:
            stream = destination.open("xb")
        except OSError as error:
            raise ResearchSessionRestoreOutputError(
                "cannot create staged restoration entry"
            ) from error
        self._stream = stream
        self._entry = entry
        self._digest = hashlib.sha256()
        self._byte_length = 0

    def consume_payload_chunk(self, entry: CanonicalUstarEntry, chunk: bytes) -> None:
        if self._stream is None or self._entry != entry:
            raise ResearchSessionRestoreOutputError(
                "staged restoration entry stream is unavailable"
            )
        if type(chunk) is not bytes or len(chunk) > 64 * 1024:
            raise ResearchSessionArchiveStructureError(
                "archive reader exposed an invalid payload chunk"
            )
        _write_all(self._stream, chunk)
        self._digest.update(chunk)
        self._byte_length += len(chunk)

    def finish_entry(
        self,
        entry: CanonicalUstarEntry,
        evidence: ResearchSessionArchiveEntryEvidence,
        manifest: WalkForwardResearchSessionManifest | None,
    ) -> None:
        if self._stream is None or self._entry != entry:
            raise ResearchSessionRestoreOutputError(
                "staged restoration entry stream is unavailable"
            )
        actual_hash = self._digest.hexdigest()
        if self._byte_length != evidence.byte_length or actual_hash != evidence.sha256:
            raise ResearchSessionRestoreOutputError(
                "staged restoration bytes do not match archive evidence"
            )
        try:
            self._stream.flush()
            os.fsync(self._stream.fileno())
        except OSError as error:
            raise ResearchSessionRestoreOutputError(
                "cannot flush staged restoration entry"
            ) from error
        try:
            self._stream.close()
        except OSError as error:
            raise ResearchSessionRestoreOutputError(
                "cannot close staged restoration entry"
            ) from error
        self._stream = None
        self._entry = None
        if entry.position == 1:
            if (
                type(manifest) is not WalkForwardResearchSessionManifest
                or manifest != self._manifest
                or manifest.manifest_id != self._manifest.manifest_id
            ):
                raise ResearchSessionArchiveStructureError(
                    "second-pass embedded manifest does not reconcile"
                )
            self._manifest_reconciled = True
        elif manifest is not None:
            raise ResearchSessionArchiveStructureError(
                "artifact entry unexpectedly supplied a manifest"
            )
        self.entries.append(
            ResearchSessionArchiveRestoreEntryEvidence(
                position=entry.position,
                path=entry.path,
                byte_length=self._byte_length,
                sha256=actual_hash,
            )
        )

    def close(self) -> str | None:
        if self._stream is not None:
            try:
                self._stream.close()
            except OSError:
                return "could not close staged restoration entry"
            finally:
                self._stream = None
                self._entry = None
        return None


def _validate_staged_layout(
    staging_path: Path, manifest: WalkForwardResearchSessionManifest
) -> None:
    artifacts_path = staging_path / "artifacts"
    if not _accepted_real_directory(staging_path) or not _accepted_real_directory(
        artifacts_path
    ):
        raise ResearchSessionRestoreOutputError(
            "staged restoration directories are unsafe"
        )
    expected_root = {"manifest.json", "artifacts"}
    expected_artifacts = {
        PurePosixPath(artifact.path).name for artifact in manifest.artifacts
    }
    try:
        root_entries = tuple(staging_path.iterdir())
        artifact_entries = tuple(artifacts_path.iterdir())
    except OSError as error:
        raise ResearchSessionRestoreOutputError(
            "cannot enumerate staged restoration layout"
        ) from error
    if (
        {entry.name for entry in root_entries} != expected_root
        or len(root_entries) != len(expected_root)
        or {entry.name for entry in artifact_entries} != expected_artifacts
        or len(artifact_entries) != len(expected_artifacts)
        or len({entry.name.casefold() for entry in artifact_entries})
        != len(artifact_entries)
    ):
        raise ResearchSessionRestoreOutputError(
            "staged restoration layout does not match embedded manifest"
        )
    for path in (staging_path / "manifest.json",) + tuple(
        staging_path.joinpath(*PurePosixPath(artifact.path).parts)
        for artifact in manifest.artifacts
    ):
        try:
            result = path.lstat()
        except OSError as error:
            raise ResearchSessionRestoreOutputError(
                "cannot inspect staged restoration entry"
            ) from error
        if (
            not stat.S_ISREG(result.st_mode)
            or stat.S_ISLNK(result.st_mode)
            or _is_reparse_point(result)
        ):
            raise ResearchSessionRestoreOutputError(
                "staged restoration entry is not a regular file"
            )


def restore_walk_forward_research_bundle_archive(
    *,
    archive_path: Path,
    destination: Path,
    expected_sha256: str | None = None,
    expected_byte_length: int | None = None,
) -> WalkForwardResearchArchiveRestoreResult:
    """Restore one fully verified canonical archive to a portable bundle."""

    if not isinstance(archive_path, Path) or not isinstance(destination, Path):
        raise ResearchSessionRestoreArgumentError(
            "archive_path and destination must be Path values"
        )
    first_verification = verify_walk_forward_research_bundle_archive(
        archive_path=archive_path,
        expected_sha256=expected_sha256,
        expected_byte_length=expected_byte_length,
    )
    manifest = _fixed_bundle_manifest(first_verification.manifest)
    bundle_path = _normalized_destination(destination)
    if not _accepted_real_directory(bundle_path.parent):
        raise ResearchSessionRestoreOutputError(
            "restoration destination parent must be an existing real directory"
        )
    staging_path = bundle_path.parent / f".{bundle_path.name}.staging"
    if _entry_exists(bundle_path):
        raise ResearchSessionRestoreOutputError(
            "restoration destination already exists"
        )
    if _entry_exists(staging_path):
        raise ResearchSessionRestoreOutputError(
            "restoration staging entry already exists"
        )

    staging_created = False
    staging_identity: tuple[int, int] | None = None
    consumer: _RestoreConsumer | None = None
    try:
        try:
            staging_path.mkdir()
            staging_created = True
            staging_identity = _staging_identity(staging_path)
            (staging_path / "artifacts").mkdir()
            if _staging_identity(staging_path) != staging_identity:
                raise ResearchSessionRestoreOutputError(
                    "restoration staging directory changed during creation"
                )
            artifacts_identity = _staging_identity(staging_path / "artifacts")
        except ResearchSessionRestoreOutputError:
            raise
        except OSError as error:
            raise ResearchSessionRestoreOutputError(
                "cannot create restoration staging directories"
            ) from error
        consumer = _RestoreConsumer(
            staging_path=staging_path,
            manifest=manifest,
            staging_identity=staging_identity,
            artifacts_identity=artifacts_identity,
        )
        second_verification = stream_canonical_walk_forward_research_bundle_archive(
            archive_path=first_verification.archive_path,
            expected_sha256=first_verification.archive_sha256,
            expected_byte_length=first_verification.archive_byte_length,
            expected_manifest=manifest,
            consumer=consumer,
        )
        if (
            second_verification.manifest != manifest
            or second_verification.manifest.manifest_id != manifest.manifest_id
            or second_verification.archive_byte_length
            != first_verification.archive_byte_length
            or second_verification.archive_sha256 != first_verification.archive_sha256
            or second_verification.entries != first_verification.entries
        ):
            raise ResearchSessionArchiveStructureError(
                "archive changed between verification and restoration"
            )
        expected_entry_count = len(manifest.artifacts) + 1
        if len(consumer.entries) != expected_entry_count:
            raise ResearchSessionRestoreOutputError(
                "restoration did not write every archive entry"
            )
        _fsync_directory(staging_path / "artifacts")
        _fsync_directory(staging_path)
        _validate_staged_layout(staging_path, manifest)
        staged_manifest_path = staging_path / "manifest.json"
        try:
            staged_manifest = load_walk_forward_research_session_manifest(
                staged_manifest_path
            )
            staged_verification = verify_walk_forward_research_session_manifest(
                staged_manifest, manifest_path=staged_manifest_path
            )
        except (
            ResearchSessionManifestReadError,
            ResearchSessionManifestJsonError,
            ResearchSessionManifestError,
        ) as error:
            raise ResearchSessionRestoreOutputError(
                "cannot reload or verify staged restored manifest"
            ) from error
        if (
            staged_manifest != manifest
            or staged_manifest.manifest_id != manifest.manifest_id
            or not staged_verification.passed
            or any(
                item.status is not ResearchSessionArtifactVerificationStatus.PASS
                for item in staged_verification.artifacts
            )
        ):
            raise ResearchSessionRestoreOutputError(
                "staged restored bundle verification failed"
            )
        if _staging_identity(staging_path) != staging_identity:
            raise ResearchSessionRestoreOutputError(
                "restoration staging directory changed before finalization"
            )
        result = WalkForwardResearchArchiveRestoreResult(
            archive_path=first_verification.archive_path,
            bundle_path=bundle_path,
            manifest_path=bundle_path / "manifest.json",
            manifest=manifest,
            archive_byte_length=first_verification.archive_byte_length,
            archive_sha256=first_verification.archive_sha256,
            entries=tuple(consumer.entries),
            archive_verification=first_verification,
            verification=staged_verification,
        )
        _fsync_directory(bundle_path.parent)
        if _entry_exists(bundle_path):
            raise ResearchSessionRestoreOutputError(
                "restoration destination appeared before finalization"
            )
        try:
            staging_path.rename(bundle_path)
        except OSError as error:
            raise ResearchSessionRestoreOutputError(
                "cannot finalize restored bundle destination"
            ) from error
        staging_created = False
        _fsync_directory(bundle_path.parent, best_effort=True)
        return result
    except Exception as primary:
        close_message = None
        if consumer is not None:
            close_message = consumer.close()
        if not staging_created:
            raise
        cleanup_message = _cleanup_staging(staging_path, staging_identity)
        cleanup_parts = tuple(
            message
            for message in (close_message, cleanup_message)
            if message is not None
        )
        if not cleanup_parts:
            raise
        raise ResearchSessionRestoreOutputError(
            str(primary),
            cleanup_message="; ".join(cleanup_parts),
            primary_error=primary,
        ) from primary
