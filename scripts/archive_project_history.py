"""Inventory and exact-archive tooling for the pre-cutover project history."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

CANONICAL_SOURCE_PATHS = (
    Path("docs/AI_TRADING_BOT_HANDOFF.md"),
    Path("docs/PROJECT_STATUS.md"),
)
LEGACY_ROOT = Path("docs/history/legacy")
MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "project-history-archive-manifest"
MANIFEST_VERSION = 1
_CUTOVER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ArchiveError(RuntimeError):
    """Raised when an exact archive cannot be proved safe and complete."""


@dataclass(frozen=True)
class RepositoryIdentity:
    """The Git source identity bound into an archive manifest."""

    head: str
    tree: str


@dataclass(frozen=True)
class SourceRecord:
    """Raw-byte measurements for one canonical source document."""

    source_path: str
    data: bytes
    byte_count: int
    sha256: str
    line_count: int


@dataclass(frozen=True)
class Inventory:
    """Read-only source inventory and its proposed archive destination."""

    repository_root: Path
    identity: RepositoryIdentity
    cutover_id: str | None
    destination: Path
    files: tuple[SourceRecord, ...]


@dataclass(frozen=True)
class ArchiveResult:
    """Result of a successfully verified exact archive."""

    repository_root: Path
    identity: RepositoryIdentity
    cutover_id: str
    destination: Path
    manifest_path: Path
    files: tuple[SourceRecord, ...]


def validate_cutover_id(cutover_id: str) -> str:
    """Validate and return a single safe archive-directory component."""

    if not isinstance(cutover_id, str) or not _CUTOVER_ID_PATTERN.fullmatch(cutover_id):
        raise ArchiveError(
            "malformed cutover identifier; use 1-64 ASCII letters, digits, "
            "dots, hyphens, or underscores, starting with a letter or digit"
        )
    return cutover_id


def _run_git(repository_root: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ArchiveError(
            f"Git command failed ({' '.join(arguments)}): {detail or 'unknown error'}"
        )
    return completed.stdout.strip()


def _resolve_repository_root(repository_root: Path | str | None) -> Path:
    if repository_root is None:
        resolved = Path(__file__).resolve().parents[1]
    else:
        resolved = Path(repository_root).resolve()
    if not resolved.is_dir():
        raise ArchiveError(f"repository root is not a directory: {resolved}")

    git_root = Path(_run_git(resolved, "rev-parse", "--show-toplevel")).resolve()
    if os.path.normcase(git_root) != os.path.normcase(resolved):
        raise ArchiveError(
            f"repository root does not match Git top-level: {resolved} != {git_root}"
        )
    return resolved


def _read_repository_identity(repository_root: Path) -> RepositoryIdentity:
    head = _run_git(repository_root, "rev-parse", "--verify", "HEAD^{commit}")
    tree = _run_git(repository_root, "rev-parse", "--verify", "HEAD^{tree}")
    if not re.fullmatch(r"[0-9a-f]{40}", head) or not re.fullmatch(
        r"[0-9a-f]{40}", tree
    ):
        raise ArchiveError("unable to prove a full 40-hex Git HEAD/TREE identity")
    return RepositoryIdentity(head=head, tree=tree)


def _require_clean_repository(
    repository_root: Path,
    *,
    allowed_untracked_paths: Sequence[Path] = (),
) -> None:
    status = _run_git(
        repository_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    allowed_status_lines = {
        f"?? {path.relative_to(repository_root).as_posix()}"
        for path in allowed_untracked_paths
    }
    unexpected_status = tuple(
        line for line in status.splitlines() if line not in allowed_status_lines
    )
    if unexpected_status:
        details = "\n".join(unexpected_status)
        raise ArchiveError(
            "repository is dirty; refusing an archive with ambiguous source identity:\n"
            f"{details}"
        )


def _source_file(repository_root: Path, relative_path: Path) -> Path:
    source = repository_root / relative_path
    if source.is_symlink() or not source.is_file():
        raise ArchiveError(f"missing canonical source file: {relative_path.as_posix()}")
    resolved = source.resolve()
    try:
        resolved.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ArchiveError(
            f"canonical source escapes the repository: {relative_path}"
        ) from exc
    if os.path.normcase(str(resolved.parent)) != os.path.normcase(
        str((repository_root / relative_path.parent).resolve())
    ):
        raise ArchiveError(f"canonical source escapes the repository: {relative_path}")
    return source


def _record_source(repository_root: Path, relative_path: Path) -> SourceRecord:
    source = _source_file(repository_root, relative_path)
    data = source.read_bytes()
    return SourceRecord(
        source_path=relative_path.as_posix(),
        data=data,
        byte_count=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        line_count=len(data.splitlines()),
    )


def _legacy_root(repository_root: Path) -> Path:
    history_root = repository_root / LEGACY_ROOT.parent
    if history_root.is_symlink() or not history_root.is_dir():
        raise ArchiveError(
            f"missing history directory: {LEGACY_ROOT.parent.as_posix()}"
        )
    legacy_root = repository_root / LEGACY_ROOT
    if legacy_root.is_symlink():
        raise ArchiveError("legacy archive root must not be a symlink")
    if legacy_root.exists() and not legacy_root.is_dir():
        raise ArchiveError("legacy archive root is not a directory")
    resolved_legacy_root = legacy_root.resolve()
    resolved_repository_root = repository_root.resolve()
    try:
        resolved_legacy_root.relative_to(resolved_repository_root)
    except ValueError as exc:
        raise ArchiveError("legacy archive root escapes the repository") from exc
    return legacy_root


def _destination(repository_root: Path, cutover_id: str | None) -> Path:
    legacy_root = _legacy_root(repository_root)
    component = cutover_id if cutover_id is not None else "<cutover-id>"
    return legacy_root / component


def inspect_repository(
    repository_root: Path | str | None = None,
    *,
    cutover_id: str | None = None,
) -> Inventory:
    """Read and measure canonical sources without writing any files."""

    root = _resolve_repository_root(repository_root)
    if cutover_id is not None:
        validate_cutover_id(cutover_id)
    _require_clean_repository(root)
    identity = _read_repository_identity(root)
    files = tuple(
        _record_source(root, relative_path) for relative_path in CANONICAL_SOURCE_PATHS
    )
    _require_clean_repository(root)
    final_identity = _read_repository_identity(root)
    if final_identity != identity:
        raise ArchiveError("Git HEAD/TREE changed during inventory capture")
    return Inventory(
        repository_root=root,
        identity=identity,
        cutover_id=cutover_id,
        destination=_destination(root, cutover_id),
        files=files,
    )


def _archive_relative_path(cutover_id: str, source_path: str) -> str:
    return (LEGACY_ROOT / cutover_id / Path(source_path).name).as_posix()


def _require_non_text_archive_paths(
    repository_root: Path,
    cutover_id: str,
    records: Sequence[SourceRecord],
) -> None:
    """Require every intended archive path to have an explicit ``-text`` rule."""

    relative_paths = tuple(
        _archive_relative_path(cutover_id, record.source_path) for record in records
    ) + (f"{LEGACY_ROOT.as_posix()}/{cutover_id}/{MANIFEST_NAME}",)
    output = _run_git(
        repository_root,
        "check-attr",
        "text",
        "--",
        *relative_paths,
    )
    observed: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split(": ", 2)
        if len(parts) != 3 or parts[1] != "text":
            raise ArchiveError(
                "Git text attribute output was not sufficient to prove archive "
                "byte preservation"
            )
        observed[parts[0]] = parts[2]
    for relative_path in relative_paths:
        if observed.get(relative_path) != "unset":
            value = observed.get(relative_path, "missing")
            raise ArchiveError(
                "archive path is not explicitly protected from Git text "
                f"normalization: {relative_path} (text={value})"
            )


def _write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        written = stream.write(data)
        if written != len(data):
            raise ArchiveError(f"short write while creating {path}")
        stream.flush()
        os.fsync(stream.fileno())


def _verify_archived_file(path: Path, expected: SourceRecord) -> None:
    actual = path.read_bytes()
    actual_sha256 = hashlib.sha256(actual).hexdigest()
    if len(actual) != expected.byte_count or actual_sha256 != expected.sha256:
        raise ArchiveError(
            f"archive verification failed for {expected.source_path}: "
            f"expected {expected.byte_count} bytes/{expected.sha256}, "
            f"got {len(actual)} bytes/{actual_sha256}"
        )
    if actual != expected.data:
        raise ArchiveError(f"archive byte mismatch for {expected.source_path}")


def _verify_sources_unchanged(
    repository_root: Path, records: Sequence[SourceRecord]
) -> None:
    for record in records:
        current = _source_file(repository_root, Path(record.source_path)).read_bytes()
        if current != record.data:
            raise ArchiveError(
                f"canonical source changed during archive: {record.source_path}"
            )


def _manifest_bytes(
    cutover_id: str,
    identity: RepositoryIdentity,
    records: Sequence[SourceRecord],
) -> bytes:
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "version": MANIFEST_VERSION,
        "cutover_id": cutover_id,
        "source_head": identity.head,
        "source_tree": identity.tree,
        "files": [
            {
                "source_path": record.source_path,
                "archive_path": _archive_relative_path(cutover_id, record.source_path),
                "byte_count": record.byte_count,
                "sha256": record.sha256,
            }
            for record in records
        ],
    }
    return (
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _cleanup_created_destination(destination: Path) -> None:
    if destination.is_dir() and not destination.is_symlink():
        shutil.rmtree(destination)


def archive_repository(
    repository_root: Path | str | None,
    cutover_id: str,
) -> ArchiveResult:
    """Write and independently verify one exact legacy archive."""

    validated_cutover_id = validate_cutover_id(cutover_id)
    inventory = inspect_repository(
        repository_root,
        cutover_id=validated_cutover_id,
    )
    _require_non_text_archive_paths(
        inventory.repository_root,
        validated_cutover_id,
        inventory.files,
    )
    destination = inventory.destination
    legacy_root = destination.parent
    if destination.exists() or destination.is_symlink():
        raise ArchiveError(f"archive destination already exists: {destination}")

    if not legacy_root.exists():
        legacy_root.mkdir()
    elif not legacy_root.is_dir() or legacy_root.is_symlink():
        raise ArchiveError("legacy archive root is not a normal directory")

    destination_created = False
    try:
        destination.mkdir()
        destination_created = True
        for record in inventory.files:
            _write_exclusive(destination / Path(record.source_path).name, record.data)
        for record in inventory.files:
            _verify_archived_file(destination / Path(record.source_path).name, record)
        _verify_sources_unchanged(inventory.repository_root, inventory.files)

        manifest_path = destination / MANIFEST_NAME
        manifest_data = _manifest_bytes(
            validated_cutover_id,
            inventory.identity,
            inventory.files,
        )
        _write_exclusive(
            manifest_path,
            manifest_data,
        )
        if manifest_path.read_bytes() != manifest_data:
            raise ArchiveError("manifest verification failed")

        _verify_sources_unchanged(inventory.repository_root, inventory.files)
        expected_archive_paths = tuple(
            destination / Path(record.source_path).name for record in inventory.files
        ) + (manifest_path,)
        _require_clean_repository(
            inventory.repository_root,
            allowed_untracked_paths=expected_archive_paths,
        )
        current_identity = _read_repository_identity(inventory.repository_root)
        if current_identity != inventory.identity:
            raise ArchiveError("Git HEAD/TREE changed during archive")
        return ArchiveResult(
            repository_root=inventory.repository_root,
            identity=inventory.identity,
            cutover_id=validated_cutover_id,
            destination=destination,
            manifest_path=manifest_path,
            files=inventory.files,
        )
    except Exception:
        if destination_created:
            _cleanup_created_destination(destination)
        raise


def _display_path(path: Path, repository_root: Path) -> str:
    if path.name == "<cutover-id>":
        return f"{LEGACY_ROOT.as_posix()}/<cutover-id>/"
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _print_inventory(inventory: Inventory) -> None:
    print("MODE DRY-RUN")
    print(f"REPOSITORY {inventory.repository_root}")
    print(f"SOURCE HEAD {inventory.identity.head}")
    print(f"SOURCE TREE {inventory.identity.tree}")
    print(
        "PROPOSED DESTINATION "
        f"{_display_path(inventory.destination, inventory.repository_root)}"
    )
    for record in inventory.files:
        print(
            f"FILE {record.source_path} BYTES {record.byte_count} "
            f"SHA256 {record.sha256} LINES {record.line_count}"
        )
    print("NO WRITES")


def _print_archive(result: ArchiveResult) -> None:
    print("MODE ARCHIVE")
    print(
        "ARCHIVE DESTINATION "
        f"{_display_path(result.destination, result.repository_root)}"
    )
    print(f"MANIFEST {_display_path(result.manifest_path, result.repository_root)}")
    print(f"SOURCE HEAD {result.identity.head}")
    print(f"SOURCE TREE {result.identity.tree}")
    for record in result.files:
        print(
            f"FILE {record.source_path} BYTES {record.byte_count} "
            f"SHA256 {record.sha256} VERIFIED"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory or exactly archive the two pre-cutover project documents."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="read and report source measurements without writing",
    )
    mode.add_argument(
        "--archive",
        "--write",
        dest="archive",
        action="store_true",
        help="write and verify an exact legacy archive",
    )
    parser.add_argument(
        "--cutover-id",
        help="single safe archive-directory identifier; required with --archive",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="repository root (defaults to the repository containing this script)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.dry_run:
            _print_inventory(
                inspect_repository(
                    arguments.repo_root,
                    cutover_id=arguments.cutover_id,
                )
            )
            return 0
        if arguments.cutover_id is None:
            parser.error("--cutover-id is required with --archive/--write")
        _print_archive(archive_repository(arguments.repo_root, arguments.cutover_id))
        return 0
    except ArchiveError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
