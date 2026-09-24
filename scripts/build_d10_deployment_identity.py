"""Architecture-123 A2 certification-only builder; never import into runtime authority.

Run against a clean detached certification checkout. This module reads Git and
checkout bytes, returns unsigned artifacts in memory, and performs no writes.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
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


def _git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
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


def _tracked_governed_paths(root: Path) -> set[str]:
    paths: set[str] = set()
    for record in _git(root, "ls-files", "--stage", "-z").split(b"\x00"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, _oid, stage = metadata.split(b" ")
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeError) as exc:
            raise DeploymentIdentityError("invalid tracked inventory") from exc
        if not (
            path.startswith("src/trading_bot/") or path == D10_LAUNCHER_RELATIVE_PATH
        ):
            continue
        canonical_relative_path(path)
        if mode not in (b"100644", b"100755") or stage != b"0":
            raise DeploymentIdentityError(
                "governed Git object is not a regular stage-zero file"
            )
        if path in paths:
            raise DeploymentIdentityError("duplicate tracked governed path")
        paths.add(path)
    if D10_LAUNCHER_RELATIVE_PATH not in paths:
        raise DeploymentIdentityError("D10 launcher is not tracked")
    if len(paths) != len({path.casefold() for path in paths}):
        raise DeploymentIdentityError("casefold-colliding governed inventory")
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
    if tracked != local:
        raise DeploymentIdentityError("tracked and local governed inventories differ")
    entries = []
    for relative in sorted(tracked):
        path = repository_root / relative
        _regular_no_reparse(path)
        data = path.read_bytes()
        _regular_no_reparse(path)
        entries.append(
            ExecutableManifestEntry(
                relative, len(data), hashlib.sha256(data).hexdigest()
            )
        )
    if _git(repository_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise DeploymentIdentityError("certification checkout changed during build")
    if _local_governed_paths(repository_root) != tracked:
        raise DeploymentIdentityError("governed inventory changed during build")
    manifest = ExecutableManifest(EXECUTABLE_MANIFEST_SCHEMA, tuple(entries))
    attestation = build_deployment_attestation(
        certified_source_head=expected_head,
        certified_source_tree=expected_tree,
        production_python_version=production_python_version,
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
