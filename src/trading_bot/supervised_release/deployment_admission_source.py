"""Bounded local Git observations; no fetch, credential helper or remote query.

Blob bytes are read from the frozen candidate object database, not newer
checkout bytes or a generated image. Nothing is installed or checked out.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release.bundle import (
    MAX_BUNDLE_BYTES,
    MAX_FILE_BYTES,
    MAX_FILES,
    source_namespace,
)
from trading_bot.supervised_release.deployment_admission import (
    DESIGN,
    ReviewedInvocation,
    SourceObservation,
)
from trading_bot.supervised_release.deployment_candidate import CANDIDATE, SUCCESSOR
from trading_bot.supervised_release.installation_contract import (
    PYTHON_SHA256,
    PYTHON_VERSION,
)
from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ReleaseInventoryEntry,
    ReleaseManifest,
)

ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
CLOSURE_PATH = "src/trading_bot/supervised_release/deployment_candidate.py"
CLOSURE_BLOB = "3bfe6666fe2b0ba151938c191289659eacd5a52b"
# Exact accepted successor_source.RISK_MATERIAL declaration, independently pinned
# by source authority. No import of its historical host/source dispatch occurs.
RISK_MATERIAL = (
    b'{"schema":"arch133-installation-risk-declaration/v1",'
    b'"mode":"paper","instruments":"US-stocks-ETFs","long_only":true,'
    b'"margin":false,"leverage":false,"options":false,"shorts":false,'
    b'"crypto":false,"deterministic_risk_required":true}'
)


def manifest_for(inventory: tuple[ReleaseInventoryEntry, ...]) -> ReleaseManifest:
    source_namespace(tuple(row.relative_path for row in inventory))
    return ReleaseManifest(
        CANDIDATE.head,
        CANDIDATE.tree,
        PYTHON_VERSION,
        PYTHON_SHA256,
        LAUNCHER_RELATIVE_PATH,
        next(
            row.sha256
            for row in inventory
            if row.relative_path == LAUNCHER_RELATIVE_PATH
        ),
        inventory,
        STRATEGY_ID,
        STRATEGY_VERSION,
        MovingAverageCrossoverConfig(5, 20, Decimal("1")),
        "arch133-long-only-review-paper",
        "1.0.0",
        hashlib.sha256(RISK_MATERIAL).hexdigest(),
    )


class LocalGitReader:
    """Fixed read-only Git vocabulary. Diagnostic children are separately counted."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.diagnostic_process_starts = 0

    def query(self, *args: str, input_bytes: bytes | None = None) -> bytes:
        fixed = {
            ("remote", "get-url", "origin"),
            ("branch", "--show-current"),
            ("status", "--porcelain=v1", "--untracked-files=all"),
            ("diff", "--cached", "--name-only"),
            ("ls-files", "-v", "-z"),
            ("rev-parse", "--is-shallow-repository"),
            ("rev-parse", "--show-toplevel"),
            ("rev-parse", "--git-path", "info/grafts"),
            ("ls-tree", "-r", "-z", CANDIDATE.head),
            ("cat-file", "blob", DESIGN.head + ":" + CLOSURE_PATH),
            (
                "config",
                "--local",
                "--get-regexp",
                r"^(extensions\.partialclone|remote\..*\.promisor|core\.worktree)$",
            ),
        }
        allowed = args in fixed
        if len(args) == 2 and args[0] == "rev-parse":
            allowed = (
                allowed
                or args[1]
                in {
                    "HEAD",
                    "HEAD^{tree}",
                    "refs/remotes/origin/develop",
                    "refs/remotes/origin/" + invocation_branch(),
                }
                or re.fullmatch(r"[0-9a-f]{40}\^\{tree\}", args[1]) is not None
            )
        if len(args) == 3 and args[0] == "merge-base":
            allowed = all(
                re.fullmatch("[0-9a-f]{40}", item) is not None for item in args[1:]
            )
        if args == ("cat-file", "--batch"):
            allowed = (
                type(input_bytes) is bytes
                and len(input_bytes) <= MAX_FILES * 41
                and re.fullmatch(rb"(?:[0-9a-f]{40}\n)+", input_bytes) is not None
            )
        elif input_bytes is not None:
            allowed = False
        if not allowed:
            raise ValueError("GIT_VOCABULARY")
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }
        env.update(
            GIT_OPTIONAL_LOCKS="0",
            GIT_NO_LAZY_FETCH="1",
            GIT_TERMINAL_PROMPT="0",
            GCM_INTERACTIVE="Never",
        )
        self.diagnostic_process_starts += 1
        result = subprocess.run(
            (
                "git",
                "--no-replace-objects",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-c",
                "core.hooksPath=",
                "-C",
                str(self.root),
                *args,
            ),
            input=input_bytes,
            capture_output=True,
            check=False,
            env=env,
            timeout=60,
        )
        absent_config = (
            args
            == (
                "config",
                "--local",
                "--get-regexp",
                r"^(extensions\.partialclone|remote\..*\.promisor|core\.worktree)$",
            )
            and result.returncode == 1
        )
        if (
            (result.returncode and not absent_config)
            or result.stderr
            or len(result.stdout) > MAX_BUNDLE_BYTES
        ):
            raise ValueError("LOCAL_GIT_OBSERVATION")
        return result.stdout


def invocation_branch() -> str:
    from trading_bot.supervised_release.deployment_admission import BRANCH

    return BRANCH


def require_checkout_path(root: Path) -> None:
    if not root.is_absolute() or any(
        part.casefold() == "aitradingbot" for part in root.parts
    ):
        raise ValueError("SOURCE_NAMESPACE")
    for path in (*reversed(root.parents), root):
        fact = path.lstat()
        if (
            not stat.S_ISDIR(fact.st_mode)
            or stat.S_ISLNK(fact.st_mode)
            or (
                os.name == "nt"
                and fact.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
            )
        ):
            raise ValueError("SOURCE_REPARSE")


def verify_tree_listing(rows: tuple[bytes, ...], expected_tree: str) -> None:
    """Rebuild the full Git tree, so omissions cannot masquerade as inventory."""
    directories: dict[str, dict[str, tuple[str, str]]] = {"": {}}
    if len(rows) > 50000:
        raise ValueError("TREE_BOUND")
    for row in rows:
        metadata, name = row.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        path = name.decode("utf-8")
        parts = path.split("/")
        if (
            mode not in {"100644", "100755"}
            or kind != "blob"
            or re.fullmatch("[0-9a-f]{40}", oid) is None
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ValueError("TREE_OBJECT")
        for index in range(len(parts)):
            parent = "/".join(parts[:index])
            leaf = parts[index]
            directory = index < len(parts) - 1
            entry = (
                ("40000", "/".join(parts[: index + 1])) if directory else (mode, oid)
            )
            entries = directories.setdefault(parent, {})
            if leaf in entries and (not directory or entries[leaf] != entry):
                raise ValueError("TREE_DUPLICATE")
            entries[leaf] = entry
    computed = {}
    for path in sorted(
        directories, key=lambda value: value.count("/") + bool(value), reverse=True
    ):
        entries = directories[path]
        material = b""
        for name in sorted(
            entries,
            key=lambda value: (
                value + ("/" if entries[value][0] == "40000" else "")
            ).encode("utf-8"),
        ):
            mode, identity = entries[name]
            oid = computed[identity] if mode == "40000" else identity
            material += (
                mode.encode() + b" " + name.encode("utf-8") + b"\0" + bytes.fromhex(oid)
            )
        computed[path] = hashlib.sha1(
            b"tree " + str(len(material)).encode() + b"\0" + material
        ).hexdigest()
    if computed[""] != expected_tree:
        raise ValueError("COMPLETE_TREE_IDENTITY")


class SourceReader(Protocol):
    root: Path

    def query(self, *args: str, input_bytes: bytes | None = None) -> bytes: ...


def observe_source(
    reader: SourceReader, invocation: ReviewedInvocation
) -> SourceObservation:
    def text(*args):
        return reader.query(*args).decode("utf-8").strip()

    expected = invocation.observer
    require_checkout_path(reader.root)
    if Path(text("rev-parse", "--show-toplevel")).resolve() != reader.root.resolve():
        raise ValueError("WORKTREE_IDENTITY")
    graft = Path(text("rev-parse", "--git-path", "info/grafts"))
    if not graft.is_absolute():
        graft = reader.root / graft
    try:
        graft.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError("GRAFTS_FORBIDDEN")
    for args, wanted in (
        (("rev-parse", "HEAD"), expected.head),
        (("rev-parse", "HEAD^{tree}"), expected.tree),
        (("branch", "--show-current"), expected.reference),
        (("remote", "get-url", "origin"), ORIGIN),
        (("status", "--porcelain=v1", "--untracked-files=all"), ""),
        (("diff", "--cached", "--name-only"), ""),
        (("rev-parse", "--is-shallow-repository"), "false"),
        (("rev-parse", "refs/remotes/origin/" + expected.reference), expected.head),
    ):
        if text(*args) != wanted:
            raise ValueError("SOURCE_ADMISSION")
    # No alternate object roots, grafts, lazy fetch or hidden index flags.
    if any(
        row and row[:1] != b"H"
        for row in reader.query("ls-files", "-v", "-z").split(b"\0")
    ):
        raise ValueError("INDEX_FLAGS")
    if text(
        "config",
        "--local",
        "--get-regexp",
        r"^(extensions\.partialclone|remote\..*\.promisor|core\.worktree)$",
    ):
        raise ValueError("PARTIAL_CLONE")
    for identity in (CANDIDATE, SUCCESSOR, DESIGN):
        if (
            text("rev-parse", identity.head + "^{tree}") != identity.tree
            or text("merge-base", identity.head, expected.head) != identity.head
        ):
            raise ValueError("SOURCE_LINEAGE")
    if (
        text("merge-base", SUCCESSOR.head, CANDIDATE.head) != SUCCESSOR.head
        or text("merge-base", CANDIDATE.head, DESIGN.head) != CANDIDATE.head
    ):
        raise ValueError("FROZEN_LINEAGE")
    closure = reader.query("cat-file", "blob", DESIGN.head + ":" + CLOSURE_PATH)
    if (
        hashlib.sha1(
            b"blob " + str(len(closure)).encode() + b"\0" + closure
        ).hexdigest()
        != CLOSURE_BLOB
    ):
        raise ValueError("R1_IMMUTABLE_CLOSURE")
    rows = tuple(
        row
        for row in reader.query("ls-tree", "-r", "-z", CANDIDATE.head).split(b"\0")
        if row
    )
    verify_tree_listing(rows, CANDIDATE.tree)
    selected = []
    for row in rows:
        if not row:
            continue
        metadata, raw_name = row.split(b"\t", 1)
        name = raw_name.decode("utf-8")
        if name in {"pyproject.toml", LAUNCHER_RELATIVE_PATH} or name.startswith(
            "src/trading_bot/"
        ):
            mode, kind, oid = metadata.decode("ascii").split()
            if (
                mode not in {"100644", "100755"}
                or kind != "blob"
                or re.fullmatch("[0-9a-f]{40}", oid) is None
            ):
                raise ValueError("CANDIDATE_OBJECT")
            selected.append((name, oid))
    selected.sort()
    source_namespace(tuple(name for name, _ in selected))
    if len(selected) > MAX_FILES:
        raise ValueError("INVENTORY_BOUND")
    data = reader.query(
        "cat-file",
        "--batch",
        input_bytes=b"".join(oid.encode() + b"\n" for _, oid in selected),
    )
    inventory = []
    offset = 0
    for name, oid in selected:
        end = data.index(b"\n", offset)
        supplied_oid, kind, size = data[offset:end].split()
        length = int(size)
        if (
            supplied_oid.decode() != oid
            or kind != b"blob"
            or not 0 <= length <= MAX_FILE_BYTES
        ):
            raise ValueError("BLOB_HEADER")
        start = end + 1
        content = data[start : start + length]
        if (
            len(content) != length
            or data[start + length : start + length + 1] != b"\n"
            or hashlib.sha1(
                b"blob " + str(length).encode() + b"\0" + content
            ).hexdigest()
            != oid
        ):
            raise ValueError("BLOB_IDENTITY")
        offset = start + length + 1
        inventory.append(
            ReleaseInventoryEntry(name, hashlib.sha256(content).hexdigest())
        )
    if offset != len(data):
        raise ValueError("BLOB_TRAILING_DATA")
    return SourceObservation(
        expected,
        CANDIDATE,
        DESIGN,
        SUCCESSOR,
        manifest_for(tuple(inventory)),
        "CONSUMED",
        CLOSURE_BLOB,
    )
