"""Deterministic portable bundles for verified walk-forward research sessions."""

import errno
import hashlib
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from trading_bot.cli.exceptions import (
    ResearchSessionBundleOutputError,
    ResearchSessionBundlePlanError,
    ResearchSessionBundleSourceArtifactError,
    ResearchSessionBundleSourceVerificationError,
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
)
from trading_bot.cli.research_session_manifest import (
    ResearchSessionArtifactKind,
    ResearchSessionArtifactRecord,
    ResearchSessionArtifactVerificationStatus,
    ResearchSessionManifestVerificationResult,
    WalkForwardResearchSessionManifest,
    load_walk_forward_research_session_manifest,
    serialize_walk_forward_research_session_manifest_json,
    verify_walk_forward_research_session_manifest,
)

_COPY_CHUNK_BYTES = 64 * 1024
_ARTIFACT_SUFFIX = {
    ResearchSessionArtifactKind.WALK_FORWARD_JSON: "walk-forward.json",
    ResearchSessionArtifactKind.WALK_FORWARD_CSV: "walk-forward.csv",
    ResearchSessionArtifactKind.AGGREGATE_JSON: "aggregate.json",
    ResearchSessionArtifactKind.AGGREGATE_CSV: "aggregate.csv",
    ResearchSessionArtifactKind.STABILITY_JSON: "stability.json",
    ResearchSessionArtifactKind.STABILITY_CSV: "stability.csv",
}


@dataclass(frozen=True, slots=True)
class ResearchBundleArtifactCopyResult:
    """Immutable evidence for one exact artifact copy."""

    artifact: ResearchSessionArtifactRecord
    source_path: Path
    bundle_relative_path: str
    copied_byte_length: int
    copied_content_hash: str

    def __post_init__(self) -> None:
        if type(self.artifact) is not ResearchSessionArtifactRecord:
            raise TypeError("artifact must be an exact ResearchSessionArtifactRecord")
        if not isinstance(self.source_path, Path) or not self.source_path.is_absolute():
            raise TypeError("source_path must be an absolute Path")
        if type(self.bundle_relative_path) is not str or not self.bundle_relative_path:
            raise TypeError("bundle_relative_path must be a nonblank string")
        if self.bundle_relative_path != self.artifact.path:
            raise ValueError("bundle_relative_path must equal the artifact path")
        if type(self.copied_byte_length) is not int or self.copied_byte_length < 0:
            raise TypeError("copied_byte_length must be a nonnegative integer")
        if self.copied_byte_length != self.artifact.byte_length:
            raise ValueError("copied_byte_length must equal the artifact byte length")
        if (
            type(self.copied_content_hash) is not str
            or len(self.copied_content_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.copied_content_hash
            )
        ):
            raise TypeError("copied_content_hash must be a lowercase SHA-256 digest")
        if self.copied_content_hash != self.artifact.content_hash:
            raise ValueError("copied_content_hash must equal the artifact hash")


@dataclass(frozen=True, slots=True)
class WalkForwardResearchBundleResult:
    """Immutable evidence for one finalized portable research bundle."""

    source_manifest_path: Path
    bundle_path: Path
    manifest_path: Path
    manifest: WalkForwardResearchSessionManifest
    artifacts: tuple[ResearchBundleArtifactCopyResult, ...]
    verification: ResearchSessionManifestVerificationResult

    def __post_init__(self) -> None:
        for name in ("source_manifest_path", "bundle_path", "manifest_path"):
            value = getattr(self, name)
            if not isinstance(value, Path) or not value.is_absolute():
                raise TypeError(f"{name} must be an absolute Path")
        if self.manifest_path != self.bundle_path / "manifest.json":
            raise ValueError("manifest_path must be bundle_path/manifest.json")
        if type(self.manifest) is not WalkForwardResearchSessionManifest:
            raise TypeError(
                "manifest must be an exact WalkForwardResearchSessionManifest"
            )
        if type(self.artifacts) is not tuple or not all(
            type(item) is ResearchBundleArtifactCopyResult for item in self.artifacts
        ):
            raise TypeError("artifacts must be an exact tuple of copy results")
        if tuple(item.artifact for item in self.artifacts) != self.manifest.artifacts:
            raise ValueError(
                "copy results must retain the exact manifest artifact order"
            )
        if type(self.verification) is not ResearchSessionManifestVerificationResult:
            raise TypeError(
                "verification must be an exact "
                "ResearchSessionManifestVerificationResult"
            )
        if self.verification.manifest != self.manifest or not self.verification.passed:
            raise ValueError("verification must be a complete PASS for manifest")


def _bundle_artifact_path(
    position: int, artifact: ResearchSessionArtifactRecord
) -> str:
    suffix = _ARTIFACT_SUFFIX[artifact.kind]
    return f"artifacts/{position:02d}-{suffix}"


def relocate_walk_forward_research_session_manifest_for_bundle(
    manifest: WalkForwardResearchSessionManifest,
) -> WalkForwardResearchSessionManifest:
    """Rewrite only retained paths into the fixed bundle layout."""

    if type(manifest) is not WalkForwardResearchSessionManifest:
        raise ResearchSessionBundlePlanError(
            "manifest must be an exact WalkForwardResearchSessionManifest"
        )
    records = tuple(
        ResearchSessionArtifactRecord(
            ordinal=artifact.ordinal,
            kind=artifact.kind,
            artifact_schema_version=artifact.artifact_schema_version,
            result_id=artifact.result_id,
            path=_bundle_artifact_path(position, artifact),
            hash_algorithm=artifact.hash_algorithm,
            content_hash=artifact.content_hash,
            byte_length=artifact.byte_length,
        )
        for position, artifact in enumerate(manifest.artifacts, start=1)
    )
    paths = tuple(record.path for record in records)
    if len(set(paths)) != len(paths) or len({path.casefold() for path in paths}) != len(
        paths
    ):
        raise ResearchSessionBundlePlanError("generated bundle artifact paths collide")
    relocated = WalkForwardResearchSessionManifest(
        manifest_id=manifest.manifest_id,
        manifest_schema_version=manifest.manifest_schema_version,
        producer_protocol=manifest.producer_protocol,
        walk_forward_config_schema_version=(
            manifest.walk_forward_config_schema_version
        ),
        walk_forward_result_id=manifest.walk_forward_result_id,
        aggregate_result_id=manifest.aggregate_result_id,
        stability_result_id=manifest.stability_result_id,
        session_label=manifest.session_label,
        metadata=manifest.metadata,
        artifacts=records,
    )
    if relocated.manifest_id != manifest.manifest_id:
        raise ResearchSessionBundlePlanError(
            "relocated manifest identity does not match source manifest identity"
        )
    return relocated


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
        raise ResearchSessionBundleOutputError(
            "cannot inspect bundle destination entry"
        ) from error
    return True


def _normalized_destination(path: Path) -> Path:
    absolute = path if path.is_absolute() else Path.cwd() / path
    if absolute.name in {"", ".", ".."}:
        raise ResearchSessionBundlePlanError(
            "bundle destination must name one directory entry"
        )
    return absolute.parent.resolve(strict=False) / absolute.name


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


def _changed_during_read(before: os.stat_result, after: os.stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    return any(getattr(before, name) != getattr(after, name) for name in fields)


def _source_path(
    artifact: ResearchSessionArtifactRecord, manifest_parent: Path
) -> Path:
    return manifest_parent.joinpath(*PurePosixPath(artifact.path).parts)


def _inspect_source_path(
    artifact: ResearchSessionArtifactRecord, manifest_parent: Path
) -> tuple[Path, os.stat_result]:
    current = manifest_parent
    parts = PurePosixPath(artifact.path).parts
    for component in parts[:-1]:
        current = current / component
        try:
            component_stat = current.lstat()
        except FileNotFoundError as error:
            raise ResearchSessionBundleSourceArtifactError(
                artifact,
                ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
            ) from error
        except OSError as error:
            raise ResearchSessionBundleSourceArtifactError(
                artifact, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
            ) from error
        if (
            stat.S_ISLNK(component_stat.st_mode)
            or _is_reparse_point(component_stat)
            or not stat.S_ISDIR(component_stat.st_mode)
        ):
            raise ResearchSessionBundleSourceArtifactError(
                artifact,
                ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
            )
    path = manifest_parent.joinpath(*parts)
    try:
        retained_stat = path.lstat()
    except FileNotFoundError as error:
        raise ResearchSessionBundleSourceArtifactError(
            artifact,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        ) from error
    except OSError as error:
        raise ResearchSessionBundleSourceArtifactError(
            artifact, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        ) from error
    if (
        stat.S_ISLNK(retained_stat.st_mode)
        or _is_reparse_point(retained_stat)
        or not stat.S_ISREG(retained_stat.st_mode)
    ):
        raise ResearchSessionBundleSourceArtifactError(
            artifact,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        )
    return path, retained_stat


def _copy_artifact(
    source_artifact: ResearchSessionArtifactRecord,
    bundle_artifact: ResearchSessionArtifactRecord,
    *,
    source_manifest_parent: Path,
    staging_root: Path,
) -> ResearchBundleArtifactCopyResult:
    source, retained_stat = _inspect_source_path(
        source_artifact, source_manifest_parent
    )
    destination = staging_root.joinpath(*PurePosixPath(bundle_artifact.path).parts)
    try:
        source_stream = source.open("rb")
    except FileNotFoundError as error:
        raise ResearchSessionBundleSourceArtifactError(
            source_artifact,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        ) from error
    except OSError as error:
        raise ResearchSessionBundleSourceArtifactError(
            source_artifact, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        ) from error
    digest = hashlib.sha256()
    byte_length = 0
    try:
        with source_stream:
            try:
                opened_before = os.fstat(source_stream.fileno())
            except OSError as error:
                raise ResearchSessionBundleSourceArtifactError(
                    source_artifact,
                    ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
                ) from error
            if (
                not stat.S_ISREG(opened_before.st_mode)
                or _is_reparse_point(opened_before)
                or (retained_stat.st_dev, retained_stat.st_ino)
                != (opened_before.st_dev, opened_before.st_ino)
            ):
                raise ResearchSessionBundleSourceArtifactError(
                    source_artifact,
                    ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
                )
            try:
                destination_stream = destination.open("xb")
            except OSError as error:
                raise ResearchSessionBundleOutputError(
                    "cannot create staged artifact"
                ) from error
            with destination_stream:
                while True:
                    try:
                        chunk = source_stream.read(_COPY_CHUNK_BYTES)
                    except OSError as error:
                        raise ResearchSessionBundleSourceArtifactError(
                            source_artifact,
                            ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
                        ) from error
                    if not chunk:
                        break
                    try:
                        destination_stream.write(chunk)
                    except OSError as error:
                        raise ResearchSessionBundleOutputError(
                            "cannot write staged artifact"
                        ) from error
                    byte_length += len(chunk)
                    digest.update(chunk)
                try:
                    destination_stream.flush()
                    os.fsync(destination_stream.fileno())
                except OSError as error:
                    raise ResearchSessionBundleOutputError(
                        "cannot flush staged artifact"
                    ) from error
            try:
                opened_after = os.fstat(source_stream.fileno())
            except OSError as error:
                raise ResearchSessionBundleSourceArtifactError(
                    source_artifact,
                    ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
                ) from error
    except ResearchSessionBundleSourceArtifactError:
        raise
    actual_hash = digest.hexdigest()
    if _changed_during_read(opened_before, opened_after):
        raise ResearchSessionBundleSourceArtifactError(
            source_artifact, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        )
    if byte_length != source_artifact.byte_length:
        raise ResearchSessionBundleSourceArtifactError(
            source_artifact,
            ResearchSessionArtifactVerificationStatus.BYTE_LENGTH_MISMATCH,
        )
    if actual_hash != source_artifact.content_hash:
        raise ResearchSessionBundleSourceArtifactError(
            source_artifact, ResearchSessionArtifactVerificationStatus.SHA256_MISMATCH
        )
    return ResearchBundleArtifactCopyResult(
        artifact=bundle_artifact,
        source_path=source,
        bundle_relative_path=bundle_artifact.path,
        copied_byte_length=byte_length,
        copied_content_hash=actual_hash,
    )


def _fsync_directory(path: Path, *, best_effort: bool = False) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        os.fsync(descriptor)
    except OSError as error:
        unsupported = error.errno in {
            errno.EBADF,
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
        if not best_effort and not unsupported:
            raise ResearchSessionBundleOutputError(
                "cannot flush staging directory"
            ) from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                if not best_effort:
                    raise ResearchSessionBundleOutputError(
                        "cannot close staging directory handle"
                    ) from error


def _write_manifest(path: Path, manifest: WalkForwardResearchSessionManifest) -> None:
    content = serialize_walk_forward_research_session_manifest_json(manifest).encode(
        "utf-8"
    )
    try:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, UnicodeError) as error:
        raise ResearchSessionBundleOutputError(
            "cannot write staged bundle manifest"
        ) from error


def _cleanup_staging(path: Path) -> str | None:
    try:
        shutil.rmtree(path)
    except OSError:
        return f"could not remove staging directory: {path}"
    return None


def create_walk_forward_research_bundle(
    *,
    manifest_path: Path,
    destination: Path,
) -> WalkForwardResearchBundleResult:
    """Create an offline-verifiable bundle from an already valid session."""

    if not isinstance(manifest_path, Path) or not isinstance(destination, Path):
        raise ResearchSessionBundlePlanError(
            "manifest_path and destination must be exact Path values"
        )
    source_manifest_path = manifest_path.resolve(strict=False)
    bundle_path = _normalized_destination(destination)
    source_manifest = load_walk_forward_research_session_manifest(source_manifest_path)
    if not _accepted_real_directory(bundle_path.parent):
        raise ResearchSessionBundleOutputError(
            "bundle destination parent must be an existing real directory"
        )
    staging_path = bundle_path.parent / f".{bundle_path.name}.staging"
    if _entry_exists(bundle_path):
        raise ResearchSessionBundleOutputError("bundle destination already exists")
    if _entry_exists(staging_path):
        raise ResearchSessionBundleOutputError("bundle staging entry already exists")

    source_paths = tuple(
        _source_path(artifact, source_manifest_path.parent)
        for artifact in source_manifest.artifacts
    )
    generated_paths = ("manifest.json", "artifacts") + tuple(
        _bundle_artifact_path(position, artifact)
        for position, artifact in enumerate(source_manifest.artifacts, start=1)
    )
    if len(set(generated_paths)) != len(generated_paths) or len(
        {path.casefold() for path in generated_paths}
    ) != len(generated_paths):
        raise ResearchSessionBundlePlanError("generated bundle paths collide")
    if bundle_path == source_manifest_path or bundle_path in source_paths:
        raise ResearchSessionBundlePlanError(
            "bundle destination collides with a source path"
        )

    source_verification = verify_walk_forward_research_session_manifest(
        source_manifest, manifest_path=source_manifest_path
    )
    if not source_verification.passed:
        raise ResearchSessionBundleSourceVerificationError(source_verification)
    relocated = relocate_walk_forward_research_session_manifest_for_bundle(
        source_manifest
    )

    staging_created = False
    try:
        try:
            staging_path.mkdir()
            staging_created = True
            (staging_path / "artifacts").mkdir()
        except OSError as error:
            raise ResearchSessionBundleOutputError(
                "cannot create bundle staging directories"
            ) from error
        copies = tuple(
            _copy_artifact(
                source_artifact,
                bundle_artifact,
                source_manifest_parent=source_manifest_path.parent,
                staging_root=staging_path,
            )
            for source_artifact, bundle_artifact in zip(
                source_manifest.artifacts, relocated.artifacts, strict=True
            )
        )
        _fsync_directory(staging_path / "artifacts")
        staged_manifest_path = staging_path / "manifest.json"
        _write_manifest(staged_manifest_path, relocated)
        _fsync_directory(staging_path)
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
            raise ResearchSessionBundleOutputError(
                "cannot reload or verify staged bundle manifest"
            ) from error
        if (
            staged_manifest != relocated
            or staged_manifest.manifest_id != source_manifest.manifest_id
            or not staged_verification.passed
        ):
            raise ResearchSessionBundleOutputError("staged bundle verification failed")
        if _entry_exists(bundle_path):
            raise ResearchSessionBundleOutputError(
                "bundle destination appeared before finalization"
            )
        result = WalkForwardResearchBundleResult(
            source_manifest_path=source_manifest_path,
            bundle_path=bundle_path,
            manifest_path=bundle_path / "manifest.json",
            manifest=relocated,
            artifacts=copies,
            verification=staged_verification,
        )
        _fsync_directory(bundle_path.parent)
        try:
            staging_path.rename(bundle_path)
        except OSError as error:
            raise ResearchSessionBundleOutputError(
                "cannot finalize bundle destination"
            ) from error
        staging_created = False
        _fsync_directory(bundle_path.parent, best_effort=True)
        return result
    except Exception as primary:
        if not staging_created:
            raise
        cleanup_message = _cleanup_staging(staging_path)
        if cleanup_message is None:
            raise
        if isinstance(primary, ResearchSessionBundleOutputError):
            raise ResearchSessionBundleOutputError(
                str(primary),
                cleanup_message=cleanup_message,
                primary_error=primary,
            ) from primary
        raise ResearchSessionBundleOutputError(
            str(primary),
            cleanup_message=cleanup_message,
            primary_error=primary,
        ) from primary
