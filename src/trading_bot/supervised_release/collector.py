"""Read-only collector for an explicitly supplied clean development checkout.

No installation, production observer, scheduler or unattended-host entry point.
Git is invoked only for local source facts with replacement objects disabled.
"""

from __future__ import annotations

import os
import stat
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path, PureWindowsPath

from trading_bot.supervised_release.bundle import (
    MAX_BUNDLE_BYTES,
    MAX_FILE_BYTES,
    MAX_FILES,
    ReleaseBundle,
    ReleaseFile,
    VerifiedRelease,
    source_name,
    source_namespace,
    verify_release_bundle,
)
from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    ReleaseInventoryEntry,
    ReleaseManifest,
)


@dataclass(frozen=True, slots=True)
class SourceState:
    head: str
    tree: str
    objects: tuple[tuple[str, str], ...]
    autocrlf: str


def _git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_NO_LAZY_FETCH"] = "1"
    result = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(root),
            *args,
        ],
        input=input_bytes,
        capture_output=True,
        check=False,
        env=environment,
        timeout=30,
    )
    if result.returncode and not (
        result.returncode == 1
        and args
        in {
            ("config", "--get", "core.autocrlf"),
            (
                "config",
                "--name-only",
                "--get-regexp",
                "^(extensions[.]partialclone|remote[.].*[.]promisor)$",
            ),
        }
    ):
        raise ValueError("local source Git observation failed")
    return result.stdout


def _fact(path: Path, *, directory: bool) -> os.stat_result:
    facts = path.lstat()
    if (
        stat.S_ISLNK(facts.st_mode)
        or getattr(facts, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or not (
            stat.S_ISDIR(facts.st_mode) if directory else stat.S_ISREG(facts.st_mode)
        )
    ):
        raise ValueError("source symlink/reparse/wrong object type")
    return facts


def _checkout(checkout: Path) -> Path:
    root = Path(checkout).absolute()
    windows = PureWindowsPath(str(checkout))
    if windows.drive.upper() in {"Y:", "Z:"} or any(
        part.casefold() == "aitradingbot" for part in windows.parts
    ):
        raise ValueError("production and scratch namespaces forbidden")
    # Check ancestors before resolving or invoking Git; never traverse links.
    for path in reversed((root, *root.parents)):
        _fact(path, directory=True)
    metadata = root / ".git"
    _fact(metadata, directory=stat.S_ISDIR(metadata.lstat().st_mode))
    if (
        Path(_git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        != root
    ):
        raise ValueError("explicit checkout root required")
    return root


def _state(root: Path, expected_head: str, expected_tree: str) -> SourceState:
    if _git(
        root,
        "config",
        "--name-only",
        "--get-regexp",
        "^(extensions[.]partialclone|remote[.].*[.]promisor)$",
    ):
        raise ValueError("partial/promisor source repositories forbidden")
    tracked = _git(root, "ls-files", "-z")
    attributes = _git(
        root,
        "check-attr",
        "-z",
        "--stdin",
        "filter",
        "working-tree-encoding",
        input_bytes=tracked,
    ).split(b"\0")
    if any(value not in {b"unspecified", b"unset"} for value in attributes[2::3]):
        raise ValueError("external Git source filters/encoding forbidden")
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    if (head, tree) != (expected_head, expected_tree):
        raise ValueError("wrong source HEAD/tree")
    if _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise ValueError("dirty tracked/index/untracked source checkout")
    if any(
        item and item[:1] != b"H"
        for item in _git(root, "ls-files", "-v", "-z").split(b"\0")
    ):
        raise ValueError("hidden source index flags forbidden")
    objects = []
    for item in _git(root, "ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if not item:
            continue
        metadata, raw_name = item.split(b"\t", 1)
        name = raw_name.decode("utf-8")
        if name in {"pyproject.toml", LAUNCHER_RELATIVE_PATH} or name.startswith(
            "src/trading_bot/"
        ):
            source_name(name)
            mode, kind, identity = metadata.decode("ascii").split()
            if mode not in {"100644", "100755"} or kind != "blob":
                raise ValueError("nonregular Git source object")
            objects.append((name, identity))
    objects.sort()
    source_namespace(tuple(name for name, _ in objects))
    # Only the standard Git newline checkout conversion is admitted. External
    # filters/encoding transformations are never invoked by this collector.
    autocrlf = _git(root, "config", "--get", "core.autocrlf").decode().strip()
    return SourceState(head, tree, tuple(objects), autocrlf or "false")


def _names(root: Path) -> tuple[str, ...]:
    names = ["pyproject.toml", LAUNCHER_RELATIVE_PATH]
    _fact(root / "src", directory=True)
    _fact(root / "scripts", directory=True)
    stack = [root / "src/trading_bot"]
    visited = 0
    while stack:
        directory = stack.pop()
        _fact(directory, directory=True)
        for path in directory.iterdir():
            visited += 1
            if visited > MAX_FILES * 2:
                raise ValueError("source namespace budget exceeded")
            facts = path.lstat()
            is_directory = stat.S_ISDIR(facts.st_mode)
            _fact(path, directory=is_directory)
            if is_directory:
                if path.name != "__pycache__":
                    stack.append(path)
            else:
                name = path.relative_to(root).as_posix()
                source_name(name)
                names.append(name)
    return source_namespace(tuple(sorted(names)))


def _read(root: Path, name: str) -> bytes:
    path = root / name
    before = _fact(path, directory=False)
    if before.st_size > MAX_FILE_BYTES:
        raise ValueError("source file byte budget exceeded")
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("source object identity drift")
        data = handle.read(MAX_FILE_BYTES + 1)
        after = os.fstat(handle.fileno())
    final = _fact(path, directory=False)
    # Windows path stat and handle fstat can expose different ctime semantics.
    # Compare ctime only within the same observation surface; exclude atime.
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
    stable = tuple(getattr(before, field) for field in fields)
    if (
        stable != tuple(getattr(after, field) for field in fields)
        or stable != tuple(getattr(final, field) for field in fields)
        or before.st_ctime_ns != final.st_ctime_ns
        or opened.st_ctime_ns != after.st_ctime_ns
        or len(data) != before.st_size
    ):
        raise ValueError("source object/byte drift")
    return data


def collect_release_bundle(
    checkout: Path, *, declaration: ReleaseManifest
) -> VerifiedRelease:
    """Collect complete source bytes, replacing only declaration inventory.

    The accepted declaration supplies exact expected HEAD/tree and launcher hash,
    plus reviewed Python/strategy/risk declarations. No host facts are invented.
    Exact checkout bytes (including admitted Git CRLF conversion) are hashed.
    """
    if type(declaration) is not ReleaseManifest:
        raise ValueError("reviewed release declaration required")
    root = _checkout(checkout)
    before = _state(root, declaration.source_head, declaration.source_tree)
    names = _names(root)
    if names != tuple(name for name, _ in before.objects):
        raise ValueError("source namespace drift")
    files = []
    total = 0
    for name, blob_id in before.objects:
        data = _read(root, name)
        total += len(data)
        if total > MAX_BUNDLE_BYTES:
            raise ValueError("source byte budget exceeded")
        blob_size = int(_git(root, "cat-file", "-s", blob_id))
        if blob_size > MAX_FILE_BYTES:
            raise ValueError("Git source byte budget exceeded")
        blob = _git(root, "cat-file", "blob", blob_id)
        if data != blob and not (
            before.autocrlf == "true"
            and b"\0" not in blob
            and b"\r" not in blob
            and data == blob.replace(b"\n", b"\r\n")
        ):
            raise ValueError("source bytes differ from exact Git object")
        files.append(ReleaseFile(name, data))
    launcher = next(
        item for item in files if item.relative_path == LAUNCHER_RELATIVE_PATH
    )
    if launcher.sha256 != declaration.launcher_sha256:
        raise ValueError("collected launcher mismatch")
    inventory = tuple(
        ReleaseInventoryEntry(item.relative_path, item.sha256) for item in files
    )
    manifest = replace(declaration, source_inventory=inventory)
    manifest_file = ReleaseFile("manifest.json", manifest.to_json().encode("utf-8"))
    bundle = ReleaseBundle(
        tuple(sorted((*files, manifest_file), key=lambda item: item.relative_path))
    )
    # Repeat namespace, object bytes and Git state; no mixed-generation bundle.
    if _names(root) != names or any(
        _read(root, item.relative_path) != item.data for item in files
    ):
        raise ValueError("source namespace or byte drift during collection")
    if _state(root, declaration.source_head, declaration.source_tree) != before:
        raise ValueError("before/after Git source drift")
    return verify_release_bundle(
        bundle,
        expected_manifest_sha256=manifest_file.sha256,
        expected_source_head=before.head,
        expected_source_tree=before.tree,
        expected_source_paths=names,
    )
