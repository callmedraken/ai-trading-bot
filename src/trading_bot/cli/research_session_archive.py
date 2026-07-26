"""Canonical uncompressed USTAR archives for completed research bundles."""

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import UUID

from trading_bot.cli.exceptions import (
    ResearchSessionArchiveArgumentError,
    ResearchSessionArchiveByteLengthMismatchError,
    ResearchSessionArchiveError,
    ResearchSessionArchiveHashMismatchError,
    ResearchSessionArchiveOutputError,
    ResearchSessionArchiveReadError,
    ResearchSessionArchiveSourceEntryError,
    ResearchSessionArchiveSourceVerificationError,
    ResearchSessionArchiveStructureError,
    ResearchSessionBundlePlanError,
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
)
from trading_bot.cli.research_session_bundle import (
    relocate_walk_forward_research_session_manifest_for_bundle,
)
from trading_bot.cli.research_session_manifest import (
    MAX_RESEARCH_SESSION_MANIFEST_BYTES,
    ResearchSessionArtifactVerificationStatus,
    WalkForwardResearchSessionManifest,
    load_walk_forward_research_session_manifest,
    parse_walk_forward_research_session_manifest_bytes,
    verify_walk_forward_research_session_manifest,
)

USTAR_BLOCK_SIZE = 512
USTAR_TERMINATOR_BLOCK_COUNT = 2
ARCHIVE_COPY_CHUNK_BYTES = 64 * 1024

_NAME_OFFSET, _NAME_WIDTH = 0, 100
_MODE_OFFSET, _MODE_WIDTH = 100, 8
_UID_OFFSET, _UID_WIDTH = 108, 8
_GID_OFFSET, _GID_WIDTH = 116, 8
_SIZE_OFFSET, _SIZE_WIDTH = 124, 12
_MTIME_OFFSET, _MTIME_WIDTH = 136, 12
_CHECKSUM_OFFSET, _CHECKSUM_WIDTH = 148, 8
_TYPE_OFFSET, _TYPE_WIDTH = 156, 1
_LINKNAME_OFFSET, _LINKNAME_WIDTH = 157, 100
_MAGIC_OFFSET, _MAGIC_WIDTH = 257, 6
_VERSION_OFFSET, _VERSION_WIDTH = 263, 2
_UNAME_OFFSET, _UNAME_WIDTH = 265, 32
_GNAME_OFFSET, _GNAME_WIDTH = 297, 32
_DEVMAJOR_OFFSET, _DEVMAJOR_WIDTH = 329, 8
_DEVMINOR_OFFSET, _DEVMINOR_WIDTH = 337, 8
_PREFIX_OFFSET, _PREFIX_WIDTH = 345, 155
_HEADER_PADDING_OFFSET, _HEADER_PADDING_WIDTH = 500, 12
_ZERO_BLOCK = bytes(USTAR_BLOCK_SIZE)
_MAX_USTAR_SIZE = (8**11) - 1


class ResearchSessionArchiveFormat(StrEnum):
    """The only supported version-one research archive format."""

    USTAR = "USTAR"


@dataclass(frozen=True, slots=True)
class ResearchSessionArchiveEntryEvidence:
    """Exact content evidence for one canonical archive entry."""

    position: int
    path: str
    byte_length: int
    sha256: str

    def __post_init__(self) -> None:
        if type(self.position) is not int or self.position < 1:
            raise TypeError("position must be an exact positive integer")
        _validate_entry_name(self.path)
        if type(self.byte_length) is not int or self.byte_length < 0:
            raise TypeError("byte_length must be an exact nonnegative integer")
        _validate_sha256(self.sha256, "sha256")


@dataclass(frozen=True, slots=True)
class WalkForwardResearchArchiveVerificationResult:
    """Immutable evidence from streaming canonical archive verification."""

    archive_path: Path
    archive_format: ResearchSessionArchiveFormat
    manifest: WalkForwardResearchSessionManifest
    archive_byte_length: int
    archive_sha256: str
    entries: tuple[ResearchSessionArchiveEntryEvidence, ...]
    expected_byte_length_matched: bool | None
    expected_sha256_matched: bool | None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.archive_path, Path)
            or not self.archive_path.is_absolute()
        ):
            raise TypeError("archive_path must be an absolute Path")
        if self.archive_format is not ResearchSessionArchiveFormat.USTAR:
            raise TypeError("archive_format must be USTAR")
        if type(self.manifest) is not WalkForwardResearchSessionManifest:
            raise TypeError(
                "manifest must be an exact WalkForwardResearchSessionManifest"
            )
        if type(self.archive_byte_length) is not int or self.archive_byte_length < 0:
            raise TypeError("archive_byte_length must be an exact nonnegative integer")
        _validate_sha256(self.archive_sha256, "archive_sha256")
        if type(self.entries) is not tuple or not all(
            type(item) is ResearchSessionArchiveEntryEvidence for item in self.entries
        ):
            raise TypeError("entries must be an exact tuple of entry evidence")
        if tuple(item.position for item in self.entries) != tuple(
            range(1, len(self.entries) + 1)
        ):
            raise ValueError("archive entry positions must be contiguous")
        expected_paths = ("manifest.json",) + tuple(
            artifact.path for artifact in self.manifest.artifacts
        )
        if tuple(item.path for item in self.entries) != expected_paths:
            raise ValueError("archive evidence must retain exact manifest entry order")
        for evidence, artifact in zip(
            self.entries[1:], self.manifest.artifacts, strict=True
        ):
            if (
                evidence.byte_length != artifact.byte_length
                or evidence.sha256 != artifact.content_hash
            ):
                raise ValueError(
                    "archive artifact evidence must match retained manifest"
                )
        for name in ("expected_byte_length_matched", "expected_sha256_matched"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise TypeError(f"{name} must be an exact bool or None")

    @property
    def passed(self) -> bool:
        """Whether canonical structure, contents, and supplied evidence passed."""

        return (
            self.expected_byte_length_matched is not False
            and self.expected_sha256_matched is not False
        )


@dataclass(frozen=True, slots=True)
class WalkForwardResearchArchiveResult:
    """Immutable evidence for one finalized canonical archive."""

    archive_path: Path
    manifest_id: UUID
    archive_byte_length: int
    archive_sha256: str
    verification: WalkForwardResearchArchiveVerificationResult

    def __post_init__(self) -> None:
        if (
            not isinstance(self.archive_path, Path)
            or not self.archive_path.is_absolute()
        ):
            raise TypeError("archive_path must be an absolute Path")
        if type(self.manifest_id) is not UUID:
            raise TypeError("manifest_id must be an exact UUID")
        if type(self.archive_byte_length) is not int or self.archive_byte_length < 0:
            raise TypeError("archive_byte_length must be an exact nonnegative integer")
        _validate_sha256(self.archive_sha256, "archive_sha256")
        if type(self.verification) is not WalkForwardResearchArchiveVerificationResult:
            raise TypeError("verification must be an exact archive verification result")
        if (
            not self.verification.passed
            or self.verification.manifest.manifest_id != self.manifest_id
            or self.verification.archive_byte_length != self.archive_byte_length
            or self.verification.archive_sha256 != self.archive_sha256
        ):
            raise ValueError("verification must reconcile with archive evidence")


def _validate_sha256(value: object, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ResearchSessionArchiveArgumentError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _validate_entry_name(value: object) -> str:
    if type(value) is not str or not value:
        raise ResearchSessionArchiveStructureError(
            "archive entry name must be a nonblank string"
        )
    try:
        encoded = value.encode("ascii", errors="strict")
    except UnicodeEncodeError as error:
        raise ResearchSessionArchiveStructureError(
            "archive entry names must use strict ASCII"
        ) from error
    path = PurePosixPath(value)
    if (
        value.startswith("/")
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        raise ResearchSessionArchiveStructureError(
            "archive entry name must be a normalized relative POSIX path"
        )
    if len(encoded) > _NAME_WIDTH:
        raise ResearchSessionArchiveStructureError(
            "archive entry name exceeds canonical USTAR name width"
        )
    return value


def _canonical_octal(value: int, width: int, name: str) -> bytes:
    if type(value) is not int or value < 0:
        raise ResearchSessionArchiveStructureError(
            f"{name} must be an exact nonnegative integer"
        )
    digits = width - 1
    text = format(value, "o")
    if len(text) > digits:
        raise ResearchSessionArchiveStructureError(
            f"{name} exceeds canonical USTAR numeric range"
        )
    return text.zfill(digits).encode("ascii") + b"\0"


def _put(header: bytearray, offset: int, width: int, value: bytes) -> None:
    if len(value) != width:
        raise RuntimeError("canonical USTAR field has incorrect width")
    header[offset : offset + width] = value


def build_canonical_ustar_header(path: str, byte_length: int) -> bytes:
    """Build the one canonical USTAR regular-file header."""

    _validate_entry_name(path)
    if type(byte_length) is not int or not 0 <= byte_length <= _MAX_USTAR_SIZE:
        raise ResearchSessionArchiveStructureError(
            "entry byte length exceeds canonical USTAR size range"
        )
    header = bytearray(USTAR_BLOCK_SIZE)
    name = path.encode("ascii")
    header[_NAME_OFFSET : _NAME_OFFSET + len(name)] = name
    _put(header, _MODE_OFFSET, _MODE_WIDTH, _canonical_octal(0o644, 8, "mode"))
    _put(header, _UID_OFFSET, _UID_WIDTH, _canonical_octal(0, 8, "uid"))
    _put(header, _GID_OFFSET, _GID_WIDTH, _canonical_octal(0, 8, "gid"))
    _put(
        header,
        _SIZE_OFFSET,
        _SIZE_WIDTH,
        _canonical_octal(byte_length, 12, "size"),
    )
    _put(header, _MTIME_OFFSET, _MTIME_WIDTH, _canonical_octal(0, 12, "mtime"))
    _put(header, _CHECKSUM_OFFSET, _CHECKSUM_WIDTH, b" " * _CHECKSUM_WIDTH)
    _put(header, _TYPE_OFFSET, _TYPE_WIDTH, b"0")
    _put(header, _LINKNAME_OFFSET, _LINKNAME_WIDTH, bytes(_LINKNAME_WIDTH))
    _put(header, _MAGIC_OFFSET, _MAGIC_WIDTH, b"ustar\0")
    _put(header, _VERSION_OFFSET, _VERSION_WIDTH, b"00")
    _put(header, _UNAME_OFFSET, _UNAME_WIDTH, bytes(_UNAME_WIDTH))
    _put(header, _GNAME_OFFSET, _GNAME_WIDTH, bytes(_GNAME_WIDTH))
    _put(
        header,
        _DEVMAJOR_OFFSET,
        _DEVMAJOR_WIDTH,
        _canonical_octal(0, 8, "devmajor"),
    )
    _put(
        header,
        _DEVMINOR_OFFSET,
        _DEVMINOR_WIDTH,
        _canonical_octal(0, 8, "devminor"),
    )
    _put(header, _PREFIX_OFFSET, _PREFIX_WIDTH, bytes(_PREFIX_WIDTH))
    _put(
        header,
        _HEADER_PADDING_OFFSET,
        _HEADER_PADDING_WIDTH,
        bytes(_HEADER_PADDING_WIDTH),
    )
    checksum = sum(header)
    checksum_bytes = format(checksum, "06o").encode("ascii") + b"\0 "
    _put(header, _CHECKSUM_OFFSET, _CHECKSUM_WIDTH, checksum_bytes)
    return bytes(header)


def _payload_padding(byte_length: int) -> int:
    return (-byte_length) % USTAR_BLOCK_SIZE


def _is_reparse_point(result: os.stat_result) -> bool:
    attributes = getattr(result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _changed_during_read(before: os.stat_result, after: os.stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    return any(getattr(before, name) != getattr(after, name) for name in fields)


def _entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ResearchSessionArchiveOutputError(
            "cannot inspect archive destination entry"
        ) from error
    return True


def _real_directory(path: Path) -> bool:
    try:
        result = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(result.st_mode)
        and not stat.S_ISLNK(result.st_mode)
        and not _is_reparse_point(result)
    )


def _normalized_final_component(path: Path, name: str) -> Path:
    absolute = path if path.is_absolute() else Path.cwd() / path
    if absolute.name in {"", ".", ".."}:
        raise ResearchSessionArchiveArgumentError(f"{name} must name one entry")
    return absolute.parent.resolve(strict=False) / absolute.name


def _source_error(path: str, status: ResearchSessionArtifactVerificationStatus):
    return ResearchSessionArchiveSourceEntryError(path, status)


def _inspect_regular_source(path: Path, logical_path: str) -> os.stat_result:
    try:
        parent_stat = path.parent.lstat()
    except FileNotFoundError as error:
        raise _source_error(
            logical_path,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        ) from error
    except OSError as error:
        raise _source_error(
            logical_path, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        ) from error
    if (
        not stat.S_ISDIR(parent_stat.st_mode)
        or stat.S_ISLNK(parent_stat.st_mode)
        or _is_reparse_point(parent_stat)
    ):
        raise _source_error(
            logical_path,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        )
    try:
        retained = path.lstat()
    except FileNotFoundError as error:
        raise _source_error(
            logical_path,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        ) from error
    except OSError as error:
        raise _source_error(
            logical_path, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        ) from error
    if (
        not stat.S_ISREG(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _is_reparse_point(retained)
    ):
        raise _source_error(
            logical_path,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        )
    return retained


def _secure_read_manifest(path: Path) -> bytes:
    retained = _inspect_regular_source(path, "manifest.json")
    try:
        stream = path.open("rb")
    except FileNotFoundError as error:
        raise _source_error(
            "manifest.json",
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        ) from error
    except OSError as error:
        raise _source_error(
            "manifest.json", ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        ) from error
    try:
        with stream:
            opened_before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened_before.st_mode)
                or _is_reparse_point(opened_before)
                or (retained.st_dev, retained.st_ino)
                != (opened_before.st_dev, opened_before.st_ino)
            ):
                raise _source_error(
                    "manifest.json",
                    ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
                )
            content = stream.read(MAX_RESEARCH_SESSION_MANIFEST_BYTES + 1)
            opened_after = os.fstat(stream.fileno())
    except ResearchSessionArchiveSourceEntryError:
        raise
    except OSError as error:
        raise _source_error(
            "manifest.json", ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        ) from error
    if _changed_during_read(opened_before, opened_after):
        raise _source_error(
            "manifest.json", ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        )
    if len(content) > MAX_RESEARCH_SESSION_MANIFEST_BYTES:
        raise ResearchSessionManifestReadError(
            "manifest exceeds maximum byte size of 4194304"
        )
    return content


def _validate_bundle_layout(
    bundle_path: Path, manifest: WalkForwardResearchSessionManifest
) -> None:
    if not _real_directory(bundle_path):
        raise ResearchSessionArchiveStructureError(
            "bundle path must be an existing real directory"
        )
    artifacts_path = bundle_path / "artifacts"
    expected_root = {"manifest.json", "artifacts"}
    expected_artifacts = {PurePosixPath(item.path).name for item in manifest.artifacts}
    try:
        root_entries = tuple(bundle_path.iterdir())
        artifact_entries = (
            tuple(artifacts_path.iterdir()) if _real_directory(artifacts_path) else ()
        )
    except OSError as error:
        raise ResearchSessionArchiveReadError(
            "cannot enumerate source bundle layout"
        ) from error
    root_names = tuple(item.name for item in root_entries)
    artifact_names = tuple(item.name for item in artifact_entries)
    if (
        set(root_names) != expected_root
        or len(root_names) != len(expected_root)
        or not _real_directory(artifacts_path)
        or set(artifact_names) != expected_artifacts
        or len(artifact_names) != len(expected_artifacts)
        or len({name.casefold() for name in artifact_names}) != len(artifact_names)
    ):
        raise ResearchSessionArchiveStructureError(
            "source bundle filesystem layout does not match its manifest"
        )
    _inspect_regular_source(bundle_path / "manifest.json", "manifest.json")
    for artifact in manifest.artifacts:
        _inspect_regular_source(
            bundle_path.joinpath(*PurePosixPath(artifact.path).parts), artifact.path
        )


def _fixed_bundle_manifest(
    manifest: WalkForwardResearchSessionManifest,
) -> WalkForwardResearchSessionManifest:
    try:
        expected = relocate_walk_forward_research_session_manifest_for_bundle(manifest)
    except ResearchSessionBundlePlanError as error:
        raise ResearchSessionArchiveStructureError(
            "bundle manifest paths are invalid"
        ) from error
    if expected != manifest:
        raise ResearchSessionArchiveStructureError(
            "manifest does not use the fixed portable bundle layout"
        )
    paths = ("manifest.json",) + tuple(item.path for item in manifest.artifacts)
    for path in paths:
        _validate_entry_name(path)
    if len(set(paths)) != len(paths) or len({path.casefold() for path in paths}) != len(
        paths
    ):
        raise ResearchSessionArchiveStructureError("archive entry paths collide")
    return manifest


class _HashingWriter:
    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream
        self.digest = hashlib.sha256()
        self.byte_length = 0

    def write(self, content: bytes) -> None:
        remaining = memoryview(content)
        while remaining:
            try:
                written = self.stream.write(remaining)
            except OSError as error:
                raise ResearchSessionArchiveOutputError(
                    "cannot write staged archive"
                ) from error
            if written is None or written < 1:
                raise ResearchSessionArchiveOutputError(
                    "cannot complete staged archive write"
                )
            emitted = remaining[:written]
            self.digest.update(emitted)
            self.byte_length += written
            remaining = remaining[written:]


class _HashingReader:
    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream
        self.digest = hashlib.sha256()
        self.byte_length = 0

    def read_exact(self, count: int, description: str) -> bytes:
        remaining = count
        chunks = []
        while remaining:
            try:
                chunk = self.stream.read(remaining)
            except OSError as error:
                raise ResearchSessionArchiveReadError(
                    f"cannot read archive {description}"
                ) from error
            if not chunk:
                raise ResearchSessionArchiveStructureError(
                    f"archive is truncated while reading {description}"
                )
            chunks.append(chunk)
            self.digest.update(chunk)
            self.byte_length += len(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def read_optional_byte(self) -> bytes:
        try:
            content = self.stream.read(1)
        except OSError as error:
            raise ResearchSessionArchiveReadError(
                "cannot finish archive read"
            ) from error
        if content:
            self.digest.update(content)
            self.byte_length += 1
        return content


def _parse_header(header: bytes) -> tuple[str, int]:
    if len(header) != USTAR_BLOCK_SIZE:
        raise ResearchSessionArchiveStructureError(
            "archive header has incorrect block size"
        )
    name_field = header[_NAME_OFFSET : _NAME_OFFSET + _NAME_WIDTH]
    name_bytes, separator, remainder = name_field.partition(b"\0")
    if not separator or any(remainder):
        raise ResearchSessionArchiveStructureError(
            "archive entry name field is noncanonical"
        )
    try:
        path = name_bytes.decode("ascii", errors="strict")
    except UnicodeDecodeError as error:
        raise ResearchSessionArchiveStructureError(
            "archive entry name is not strict ASCII"
        ) from error
    _validate_entry_name(path)
    size_field = header[_SIZE_OFFSET : _SIZE_OFFSET + _SIZE_WIDTH]
    if (
        len(size_field) != _SIZE_WIDTH
        or size_field[-1:] != b"\0"
        or any(character not in b"01234567" for character in size_field[:-1])
    ):
        raise ResearchSessionArchiveStructureError(
            "archive entry size field is noncanonical"
        )
    byte_length = int(size_field[:-1], 8)
    expected = build_canonical_ustar_header(path, byte_length)
    if header != expected:
        raise ResearchSessionArchiveStructureError(
            "archive entry header is not canonical USTAR"
        )
    return path, byte_length


def _read_payload(
    reader: _HashingReader, byte_length: int, description: str
) -> tuple[int, str, bytes | None]:
    digest = hashlib.sha256()
    content = bytearray() if description == "manifest.json" else None
    remaining = byte_length
    total = 0
    while remaining:
        requested = min(remaining, ARCHIVE_COPY_CHUNK_BYTES)
        chunk = reader.read_exact(requested, f"{description} payload")
        digest.update(chunk)
        if content is not None:
            content.extend(chunk)
        total += len(chunk)
        remaining -= len(chunk)
    padding = reader.read_exact(_payload_padding(byte_length), f"{description} padding")
    if any(padding):
        raise ResearchSessionArchiveStructureError(
            f"{description} payload padding is not zero"
        )
    return total, digest.hexdigest(), None if content is None else bytes(content)


def _open_regular_archive(path: Path) -> tuple[BinaryIO, os.stat_result]:
    try:
        retained = path.lstat()
    except (OSError, ValueError) as error:
        raise ResearchSessionArchiveReadError("cannot inspect archive") from error
    if (
        not stat.S_ISREG(retained.st_mode)
        or stat.S_ISLNK(retained.st_mode)
        or _is_reparse_point(retained)
    ):
        raise ResearchSessionArchiveReadError(
            "archive must be a non-symlink regular file"
        )
    try:
        stream = path.open("rb")
        opened = os.fstat(stream.fileno())
    except (OSError, ValueError) as error:
        raise ResearchSessionArchiveReadError("cannot open archive") from error
    if (
        not stat.S_ISREG(opened.st_mode)
        or _is_reparse_point(opened)
        or (retained.st_dev, retained.st_ino) != (opened.st_dev, opened.st_ino)
    ):
        stream.close()
        raise ResearchSessionArchiveReadError("archive changed while opening")
    return stream, opened


def verify_walk_forward_research_bundle_archive(
    *,
    archive_path: Path,
    expected_sha256: str | None = None,
    expected_byte_length: int | None = None,
) -> WalkForwardResearchArchiveVerificationResult:
    """Stream and verify one canonical USTAR archive without extraction."""

    if not isinstance(archive_path, Path):
        raise ResearchSessionArchiveArgumentError("archive_path must be a Path")
    if expected_sha256 is not None:
        _validate_sha256(expected_sha256, "expected_sha256")
    if expected_byte_length is not None and (
        type(expected_byte_length) is not int or expected_byte_length < 0
    ):
        raise ResearchSessionArchiveArgumentError(
            "expected_byte_length must be an exact nonnegative integer"
        )
    normalized = _normalized_final_component(archive_path, "archive_path")
    stream, opened_before = _open_regular_archive(normalized)
    reader = _HashingReader(stream)
    try:
        with stream:
            manifest_header = reader.read_exact(USTAR_BLOCK_SIZE, "manifest header")
            manifest_path, manifest_length = _parse_header(manifest_header)
            if manifest_path != "manifest.json":
                raise ResearchSessionArchiveStructureError(
                    "first archive entry must be manifest.json"
                )
            if manifest_length > MAX_RESEARCH_SESSION_MANIFEST_BYTES:
                raise ResearchSessionArchiveStructureError(
                    "embedded manifest exceeds maximum byte size of 4194304"
                )
            actual_length, actual_hash, manifest_bytes = _read_payload(
                reader, manifest_length, "manifest.json"
            )
            if manifest_bytes is None:
                raise RuntimeError("manifest payload was not retained")
            manifest = parse_walk_forward_research_session_manifest_bytes(
                manifest_bytes
            )
            _fixed_bundle_manifest(manifest)
            evidence = [
                ResearchSessionArchiveEntryEvidence(
                    1, "manifest.json", actual_length, actual_hash
                )
            ]
            seen = {"manifest.json"}
            seen_casefold = {"manifest.json"}
            for position, artifact in enumerate(manifest.artifacts, start=2):
                header = reader.read_exact(USTAR_BLOCK_SIZE, f"{artifact.path} header")
                path, header_length = _parse_header(header)
                if path in seen or path.casefold() in seen_casefold:
                    raise ResearchSessionArchiveStructureError(
                        "archive entry paths collide"
                    )
                seen.add(path)
                seen_casefold.add(path.casefold())
                if path != artifact.path:
                    raise ResearchSessionArchiveStructureError(
                        "archive entries do not match retained manifest order"
                    )
                if header_length != artifact.byte_length:
                    raise ResearchSessionArchiveByteLengthMismatchError(
                        f"archive entry byte length mismatch: {path}"
                    )
                entry_length, entry_hash, _ = _read_payload(reader, header_length, path)
                if entry_length != artifact.byte_length:
                    raise ResearchSessionArchiveByteLengthMismatchError(
                        f"archive entry byte length mismatch: {path}"
                    )
                if entry_hash != artifact.content_hash:
                    raise ResearchSessionArchiveHashMismatchError(
                        f"archive entry SHA-256 mismatch: {path}"
                    )
                evidence.append(
                    ResearchSessionArchiveEntryEvidence(
                        position, path, entry_length, entry_hash
                    )
                )
            for ordinal in range(1, USTAR_TERMINATOR_BLOCK_COUNT + 1):
                terminator = reader.read_exact(
                    USTAR_BLOCK_SIZE, f"terminator block {ordinal}"
                )
                if terminator != _ZERO_BLOCK:
                    raise ResearchSessionArchiveStructureError(
                        "archive must end with exactly two zero blocks"
                    )
            if reader.read_optional_byte():
                raise ResearchSessionArchiveStructureError(
                    "archive has trailing padding, data, or concatenated content"
                )
            opened_after = os.fstat(stream.fileno())
    except (
        ResearchSessionArchiveStructureError,
        ResearchSessionArchiveByteLengthMismatchError,
        ResearchSessionArchiveHashMismatchError,
        ResearchSessionManifestReadError,
        ResearchSessionManifestJsonError,
        ResearchSessionManifestError,
    ):
        raise
    except OSError as error:
        raise ResearchSessionArchiveReadError(
            "unexpected archive I/O failure"
        ) from error
    if _changed_during_read(opened_before, opened_after):
        raise ResearchSessionArchiveReadError("archive changed during verification")
    archive_hash = reader.digest.hexdigest()
    archive_length = reader.byte_length
    length_matched = (
        None if expected_byte_length is None else archive_length == expected_byte_length
    )
    hash_matched = None if expected_sha256 is None else archive_hash == expected_sha256
    if length_matched is False:
        raise ResearchSessionArchiveByteLengthMismatchError(
            "archive byte length does not match expected evidence"
        )
    if hash_matched is False:
        raise ResearchSessionArchiveHashMismatchError(
            "archive SHA-256 does not match expected evidence"
        )
    return WalkForwardResearchArchiveVerificationResult(
        archive_path=normalized,
        archive_format=ResearchSessionArchiveFormat.USTAR,
        manifest=manifest,
        archive_byte_length=archive_length,
        archive_sha256=archive_hash,
        entries=tuple(evidence),
        expected_byte_length_matched=length_matched,
        expected_sha256_matched=hash_matched,
    )


def _write_source_entry(
    writer: _HashingWriter,
    source_path: Path,
    logical_path: str,
    expected_length: int,
    expected_hash: str,
) -> ResearchSessionArchiveEntryEvidence:
    writer.write(build_canonical_ustar_header(logical_path, expected_length))
    retained = _inspect_regular_source(source_path, logical_path)
    try:
        stream = source_path.open("rb")
    except FileNotFoundError as error:
        raise _source_error(
            logical_path,
            ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
        ) from error
    except OSError as error:
        raise _source_error(
            logical_path, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        ) from error
    digest = hashlib.sha256()
    byte_length = 0
    try:
        with stream:
            opened_before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened_before.st_mode)
                or _is_reparse_point(opened_before)
                or (retained.st_dev, retained.st_ino)
                != (opened_before.st_dev, opened_before.st_ino)
            ):
                raise _source_error(
                    logical_path,
                    ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
                )
            while True:
                try:
                    chunk = stream.read(ARCHIVE_COPY_CHUNK_BYTES)
                except OSError as error:
                    raise _source_error(
                        logical_path,
                        ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
                    ) from error
                if not chunk:
                    break
                try:
                    writer.write(chunk)
                except OSError as error:
                    raise ResearchSessionArchiveOutputError(
                        "cannot write staged archive"
                    ) from error
                digest.update(chunk)
                byte_length += len(chunk)
            opened_after = os.fstat(stream.fileno())
    except ResearchSessionArchiveSourceEntryError:
        raise
    except OSError as error:
        raise _source_error(
            logical_path, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        ) from error
    actual_hash = digest.hexdigest()
    if _changed_during_read(opened_before, opened_after):
        raise _source_error(
            logical_path, ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
        )
    if byte_length != expected_length:
        raise _source_error(
            logical_path,
            ResearchSessionArtifactVerificationStatus.BYTE_LENGTH_MISMATCH,
        )
    if actual_hash != expected_hash:
        raise _source_error(
            logical_path, ResearchSessionArtifactVerificationStatus.SHA256_MISMATCH
        )
    writer.write(bytes(_payload_padding(expected_length)))
    return ResearchSessionArchiveEntryEvidence(
        1, logical_path, byte_length, actual_hash
    )


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
            raise ResearchSessionArchiveOutputError(
                "cannot flush archive destination directory"
            ) from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                if not best_effort:
                    raise ResearchSessionArchiveOutputError(
                        "cannot close archive destination directory"
                    ) from error


def _cleanup_staging(path: Path) -> str | None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return f"could not remove archive staging file: {path}"
    return None


def create_walk_forward_research_bundle_archive(
    *,
    bundle_path: Path,
    destination_directory: Path,
) -> WalkForwardResearchArchiveResult:
    """Verify and canonically archive one completed portable research bundle."""

    if not isinstance(bundle_path, Path) or not isinstance(destination_directory, Path):
        raise ResearchSessionArchiveArgumentError(
            "bundle_path and destination_directory must be Path values"
        )
    normalized_bundle = _normalized_final_component(bundle_path, "bundle_path")
    normalized_destination = _normalized_final_component(
        destination_directory, "destination_directory"
    )
    manifest_path = normalized_bundle / "manifest.json"
    manifest = load_walk_forward_research_session_manifest(manifest_path)
    _fixed_bundle_manifest(manifest)
    if not _real_directory(normalized_destination):
        raise ResearchSessionArchiveOutputError(
            "archive destination must be an existing real directory"
        )
    filename = f"walk-forward-research-bundle-{manifest.manifest_id}.tar"
    final_path = normalized_destination / filename
    staging_path = normalized_destination / f".{filename}.staging"
    if _entry_exists(final_path):
        raise ResearchSessionArchiveOutputError("archive destination already exists")
    if _entry_exists(staging_path):
        raise ResearchSessionArchiveOutputError("archive staging entry already exists")
    _validate_bundle_layout(normalized_bundle, manifest)
    verification = verify_walk_forward_research_session_manifest(
        manifest, manifest_path=manifest_path
    )
    if not verification.passed:
        raise ResearchSessionArchiveSourceVerificationError(verification)
    manifest_bytes = _secure_read_manifest(manifest_path)
    snapshot_manifest = parse_walk_forward_research_session_manifest_bytes(
        manifest_bytes
    )
    if snapshot_manifest != manifest:
        raise ResearchSessionArchiveStructureError(
            "source manifest changed before archive staging"
        )
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    plans = [("manifest.json", len(manifest_bytes), manifest_hash)]
    plans.extend(
        (artifact.path, artifact.byte_length, artifact.content_hash)
        for artifact in manifest.artifacts
    )
    for path, length, _ in plans:
        build_canonical_ustar_header(path, length)

    staging_created = False
    try:
        try:
            stream = staging_path.open("xb")
            staging_created = True
        except OSError as error:
            raise ResearchSessionArchiveOutputError(
                "cannot create archive staging file"
            ) from error
        try:
            with stream:
                writer = _HashingWriter(stream)
                source_paths = [manifest_path]
                source_paths.extend(
                    normalized_bundle.joinpath(*PurePosixPath(item.path).parts)
                    for item in manifest.artifacts
                )
                entries = []
                for position, (source, plan) in enumerate(
                    zip(source_paths, plans, strict=True), start=1
                ):
                    path, length, expected_hash = plan
                    evidence = _write_source_entry(
                        writer, source, path, length, expected_hash
                    )
                    entries.append(
                        ResearchSessionArchiveEntryEvidence(
                            position,
                            evidence.path,
                            evidence.byte_length,
                            evidence.sha256,
                        )
                    )
                writer.write(_ZERO_BLOCK * USTAR_TERMINATOR_BLOCK_COUNT)
                stream.flush()
                os.fsync(stream.fileno())
                archive_length = writer.byte_length
                archive_hash = writer.digest.hexdigest()
        except ResearchSessionArchiveError:
            raise
        except OSError as error:
            raise ResearchSessionArchiveOutputError(
                "cannot flush or close staged archive"
            ) from error
        _validate_bundle_layout(normalized_bundle, manifest)
        try:
            staged_verification = verify_walk_forward_research_bundle_archive(
                archive_path=staging_path,
                expected_sha256=archive_hash,
                expected_byte_length=archive_length,
            )
        except (
            ResearchSessionArchiveError,
            ResearchSessionManifestReadError,
            ResearchSessionManifestJsonError,
            ResearchSessionManifestError,
        ) as error:
            raise ResearchSessionArchiveOutputError(
                "staged archive verification failed"
            ) from error
        if (
            staged_verification.manifest != manifest
            or staged_verification.manifest.manifest_id != manifest.manifest_id
            or staged_verification.entries != tuple(entries)
        ):
            raise ResearchSessionArchiveOutputError(
                "staged archive verification did not reconcile"
            )
        if _entry_exists(final_path):
            raise ResearchSessionArchiveOutputError(
                "archive destination appeared before finalization"
            )
        final_verification = WalkForwardResearchArchiveVerificationResult(
            archive_path=final_path,
            archive_format=staged_verification.archive_format,
            manifest=staged_verification.manifest,
            archive_byte_length=staged_verification.archive_byte_length,
            archive_sha256=staged_verification.archive_sha256,
            entries=staged_verification.entries,
            expected_byte_length_matched=(
                staged_verification.expected_byte_length_matched
            ),
            expected_sha256_matched=staged_verification.expected_sha256_matched,
        )
        result = WalkForwardResearchArchiveResult(
            archive_path=final_path,
            manifest_id=manifest.manifest_id,
            archive_byte_length=archive_length,
            archive_sha256=archive_hash,
            verification=final_verification,
        )
        _fsync_directory(normalized_destination)
        try:
            staging_path.rename(final_path)
        except OSError as error:
            raise ResearchSessionArchiveOutputError(
                "cannot finalize archive destination"
            ) from error
        staging_created = False
        _fsync_directory(normalized_destination, best_effort=True)
        return result
    except Exception as primary:
        if not staging_created:
            raise
        cleanup_message = _cleanup_staging(staging_path)
        if cleanup_message is None:
            raise
        raise ResearchSessionArchiveOutputError(
            str(primary),
            cleanup_message=cleanup_message,
            primary_error=primary,
        ) from primary
