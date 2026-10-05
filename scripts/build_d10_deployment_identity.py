"""Architecture-123 A2 certification-only builder; never import into runtime authority.

Run against a clean detached certification checkout. This module reads Git and
checkout bytes, returns unsigned artifacts in memory, and performs no writes.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_GUARD_RELATIVE_PATH,
    D10_LAUNCHER_RELATIVE_PATH,
    EXECUTABLE_MANIFEST_SCHEMA,
    DeploymentIdentityError,
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
    canonical_relative_path,
)


@dataclass(frozen=True, slots=True)
class D10BuildResult:
    executable_manifest_bytes: bytes
    executable_manifest_sha256: str
    unsigned_deployment_attestation_bytes: bytes
    deployment_id: str
    executable_file_count: int
    certified_source_head: str
    certified_source_tree: str


@dataclass(frozen=True, slots=True)
class _HeadBlob:
    relative_path: str
    mode: str
    oid: str


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        check=False,
        input=input_bytes,
        env={
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }
        | {"GIT_OPTIONAL_LOCKS": "0"},
    )
    if result.returncode:
        raise DeploymentIdentityError(f"Git verification failed: {arguments[0]}")
    return result.stdout


def _regular_no_reparse(path: Path, *, directory: bool = False) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise DeploymentIdentityError("governed path is missing or unreadable") from exc
    if (
        stat.S_ISLNK(info.st_mode)
        or bool(
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
        or (
            not stat.S_ISDIR(info.st_mode)
            if directory
            else not stat.S_ISREG(info.st_mode)
        )
    ):
        raise DeploymentIdentityError(
            "governed path is not a regular no-reparse object"
        )


def _tracked_governed_paths(root: Path) -> dict[str, _HeadBlob]:
    """Read the authoritative governed blob inventory from the certified HEAD."""
    paths: dict[str, _HeadBlob] = {}
    for record in _git(root, "ls-tree", "-r", "-z", "--full-tree", "HEAD").split(
        b"\x00"
    ):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, raw_oid = metadata.split(b" ")
            path = raw_path.decode("utf-8")
            oid = raw_oid.decode("ascii")
        except (ValueError, UnicodeError) as exc:
            raise DeploymentIdentityError("invalid HEAD tree inventory") from exc
        if not (
            path.casefold().startswith("src/trading_bot/")
            or path.casefold() == D10_LAUNCHER_RELATIVE_PATH.casefold()
            or path.casefold() == D10_GUARD_RELATIVE_PATH.casefold()
        ):
            continue
        if path != D10_GUARD_RELATIVE_PATH:
            canonical_relative_path(path)
        if (
            mode not in (b"100644", b"100755")
            or kind != b"blob"
            or re.fullmatch(r"[0-9a-f]{40}", oid) is None
        ):
            raise DeploymentIdentityError(
                "governed HEAD object is not a regular SHA-1 blob"
            )
        if path in paths:
            raise DeploymentIdentityError("duplicate HEAD governed path")
        paths[path] = _HeadBlob(path, mode.decode("ascii"), oid)
    if D10_LAUNCHER_RELATIVE_PATH not in paths:
        raise DeploymentIdentityError("D10 launcher is not tracked in HEAD")
    if D10_GUARD_RELATIVE_PATH not in paths:
        raise DeploymentIdentityError("D10 launch guard is not tracked in HEAD")
    if len(paths) != len({path.casefold() for path in paths}):
        raise DeploymentIdentityError("casefold-colliding governed HEAD inventory")
    return paths


def _local_governed_paths(root: Path) -> set[str]:
    _regular_no_reparse(root / "src", directory=True)
    _regular_no_reparse(root / "scripts", directory=True)
    source = root / "src" / "trading_bot"
    _regular_no_reparse(source, directory=True)
    paths: set[str] = set()
    for directory, dirs, files in os.walk(source, followlinks=False):
        base = Path(directory)
        _regular_no_reparse(base, directory=True)
        for name in (*dirs, *files):
            path = base / name
            _regular_no_reparse(path, directory=name in dirs)
            if name in files:
                relative = path.relative_to(root).as_posix()
                canonical_relative_path(relative)
                paths.add(relative)
    launcher = root / D10_LAUNCHER_RELATIVE_PATH
    _regular_no_reparse(launcher)
    paths.add(D10_LAUNCHER_RELATIVE_PATH)
    guard = root / D10_GUARD_RELATIVE_PATH
    _regular_no_reparse(guard)
    paths.add(D10_GUARD_RELATIVE_PATH)
    if len(paths) != len({path.casefold() for path in paths}):
        raise DeploymentIdentityError("casefold-colliding local inventory")
    return paths


def build_d10_deployment_identity(
    *,
    repository_root: Path,
    expected_head: str,
    expected_tree: str,
    production_python_version: str,
) -> D10BuildResult:
    """Build unsigned canonical artifacts from one exact clean Git checkout."""
    if not isinstance(repository_root, Path):
        raise DeploymentIdentityError("repository_root must be a Path")
    _regular_no_reparse(repository_root, directory=True)
    try:
        top = Path(
            os.fsdecode(_git(repository_root, "rev-parse", "--show-toplevel")).strip()
        )
        head = _git(repository_root, "rev-parse", "HEAD").decode("ascii").strip()
        tree = (
            _git(repository_root, "show", "-s", "--format=%T", "HEAD")
            .decode("ascii")
            .strip()
        )
    except UnicodeError as exc:
        raise DeploymentIdentityError("invalid Git identity encoding") from exc
    if top.resolve() != repository_root.resolve():
        raise DeploymentIdentityError("repository root is not the checkout top")
    if head != expected_head or tree != expected_tree:
        raise DeploymentIdentityError(
            "checkout HEAD or tree differs from explicit expected identity"
        )
    if _git(repository_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise DeploymentIdentityError(
            "certification checkout has dirty index, worktree, or untracked files"
        )
    tracked = _tracked_governed_paths(repository_root)
    local = _local_governed_paths(repository_root)
    if set(tracked) != local:
        raise DeploymentIdentityError("tracked and local governed inventories differ")
    entries = []
    guard_data: bytes | None = None
    for relative, head_blob in sorted(tracked.items()):
        path = repository_root / relative
        _regular_no_reparse(path)
        data = path.read_bytes()
        _regular_no_reparse(path)
        try:
            local_blob_oid = (
                _git(repository_root, "hash-object", "--stdin", input_bytes=data)
                .decode("ascii")
                .strip()
            )
        except UnicodeError as exc:
            raise DeploymentIdentityError("invalid local Git blob identity") from exc
        if local_blob_oid != head_blob.oid:
            raise DeploymentIdentityError(
                "local governed bytes do not match certified HEAD blob"
            )
        if relative == D10_GUARD_RELATIVE_PATH:
            guard_data = data
        else:
            entries.append(
                ExecutableManifestEntry(
                    relative, len(data), hashlib.sha256(data).hexdigest()
                )
            )
    if _git(repository_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise DeploymentIdentityError("certification checkout changed during build")
    if _local_governed_paths(repository_root) != set(tracked):
        raise DeploymentIdentityError("governed inventory changed during build")
    if guard_data is None:
        raise DeploymentIdentityError("D10 launch guard bytes are missing")
    manifest = ExecutableManifest(EXECUTABLE_MANIFEST_SCHEMA, tuple(entries))
    attestation = build_deployment_attestation(
        certified_source_head=expected_head,
        certified_source_tree=expected_tree,
        production_python_version=production_python_version,
        launch_guard_byte_length=len(guard_data),
        launch_guard_sha256=hashlib.sha256(guard_data).hexdigest(),
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(entries),
    )
    return D10BuildResult(
        executable_manifest_bytes=manifest.canonical_bytes(),
        executable_manifest_sha256=manifest.digest,
        unsigned_deployment_attestation_bytes=attestation.canonical_bytes(),
        deployment_id=attestation.deployment_id,
        executable_file_count=len(entries),
        certified_source_head=head,
        certified_source_tree=tree,
    )
