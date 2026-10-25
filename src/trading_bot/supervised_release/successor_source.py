"""Fresh post-R1 source generation only; no host observer or effect dispatcher.

The report declares a future rename-free destination. It never observes that
production destination, creates a latch, or admits installation/runtime use.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from decimal import Decimal
from pathlib import Path

from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    MAX_FILE_BYTES,
    VerifiedRelease,
    canonical_json,
    source_namespace,
)
from trading_bot.supervised_release.collector import collect_release_bundle
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
    release_root,
)

CHECKPOINT = "arch134-f1r1-d1s4-fresh-successor-source"
SCHEMA = CHECKPOINT + "/v1"
BRANCH = (
    "feature/robinhood-production-paper-134f1r1-d1s4-fresh-successor-source-current"
)
WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-"
    r"d1s4-fresh-successor-source-current"
)
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
BASE_HEAD = "47370fcb24baa0359ac741ee3ba2a14da6438f8d"
BASE_TREE = "9593c35799dc481ee5fba71666660c50e198c533"
REMOTE_HEAD_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_FRESH_ACCEPTED_HEAD"
SOURCE_TREE_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_FRESH_ACCEPTED_TREE"
ATTEMPT_SCHEMA = "arch134-f1r1-d1s4-rename-free-direct-install-attempt/v1"
ATTEMPT_ROOT = Path(r"F:\AI\temp")
INCIDENT_RELEASE_IDS = (
    "release-18d5d329c1d458558e98d7effe523c3b",
    "release-cb94451fc3295a97afffe9fac5d09ff3",
    "release-03c42597246752319956ab96e01ed61c",
)
INCIDENT_ROOTS = tuple(
    release_root(identifier) + (".installing" if ordinal else "")
    for ordinal, identifier in enumerate(INCIDENT_RELEASE_IDS)
)
RISK_MATERIAL = (
    b'{"schema":"arch133-installation-risk-declaration/v1",'
    b'"mode":"paper","instruments":"US-stocks-ETFs","long_only":true,'
    b'"margin":false,"leverage":false,"options":false,"shorts":false,'
    b'"crypto":false,"deterministic_risk_required":true}'
)


class ObservationDrift(ValueError):
    """Source collection changed during observation."""


def safe_ancestors(path: Path) -> None:
    """Reject links/reparse components before source traversal."""
    for ancestor in reversed(path.parents):
        fact = ancestor.lstat()
        if (
            not stat.S_ISDIR(fact.st_mode)
            or stat.S_ISLNK(fact.st_mode)
            or getattr(fact, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("ANCESTOR_REJECTED")


def read_record(path: Path, limit: int) -> tuple[bytes, tuple[int, int]]:
    """Bounded regular-file observation with stable path and open-handle facts."""
    safe_ancestors(path)
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or getattr(before, "st_file_attributes", 0) & 0x400
        or before.st_nlink != 1
        or not 0 <= before.st_size <= limit
    ):
        raise ValueError("RECORD_OBJECT_REJECTED")
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        data = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    final = path.lstat()
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
    signature = tuple(getattr(before, name) for name in fields)
    if (
        any(
            tuple(getattr(row, name) for name in fields) != signature
            for row in (opened, after, final)
        )
        or opened.st_ctime_ns != after.st_ctime_ns
        or before.st_ctime_ns != final.st_ctime_ns
        or len(data) != before.st_size
    ):
        raise ObservationDrift("RECORD_OBSERVATION_DRIFT")
    return data, (before.st_dev, before.st_ino)


def _git(*args: str) -> bytes:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        GIT_OPTIONAL_LOCKS="0",
        GIT_NO_LAZY_FETCH="1",
        GIT_TERMINAL_PROMPT="0",
        GCM_INTERACTIVE="Never",
    )
    result = subprocess.run(
        (
            "git",
            "--no-replace-objects",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(WORKTREE),
            *args,
        ),
        capture_output=True,
        check=False,
        timeout=30,
        env=environment,
    )
    if result.returncode:
        raise ValueError("SOURCE_OBSERVATION_REJECTED")
    return result.stdout


def admit_source() -> tuple[str, str]:
    """Prove exact local module/worktree and accepted live feature HEAD/tree."""
    head = os.environ.get(REMOTE_HEAD_ENV, "")
    tree = os.environ.get(SOURCE_TREE_ENV, "")
    if any(re.fullmatch("[0-9a-f]{40}", value) is None for value in (head, tree)):
        raise ValueError("SOURCE_INTERLOCK_REJECTED")
    if head == BASE_HEAD or tree == BASE_TREE:
        raise ValueError("FRESH_SOURCE_REQUIRED")
    safe_ancestors(WORKTREE / "source")
    expected_module = (
        WORKTREE / "src/trading_bot/supervised_release/successor_source.py"
    )
    if Path(__file__).resolve() != expected_module.resolve():
        raise ValueError("IMPORT_SOURCE_REJECTED")
    for args, expected in (
        (("rev-parse", "HEAD"), head),
        (("rev-parse", "HEAD^{tree}"), tree),
        (("branch", "--show-current"), BRANCH),
        (("remote", "get-url", "origin"), ORIGIN),
        (("status", "--porcelain=v1", "--untracked-files=all"), ""),
        (("diff", "--cached", "--name-only"), ""),
        (("merge-base", BASE_HEAD, "HEAD"), BASE_HEAD),
        (("rev-parse", BASE_HEAD + "^{tree}"), BASE_TREE),
    ):
        if _git(*args).decode("utf-8").strip() != expected:
            raise ValueError("SOURCE_REJECTED")
    if (
        Path(_git("rev-parse", "--show-toplevel").decode().strip()).resolve()
        != WORKTREE.resolve()
    ):
        raise ValueError("WORKTREE_REJECTED")
    if any(
        row and row[:1] != b"H" for row in _git("ls-files", "-v", "-z").split(b"\0")
    ):
        raise ValueError("HIDDEN_INDEX_FLAGS_REJECTED")
    remote_ref = "refs/heads/" + BRANCH
    rows = _git("ls-remote", "origin", remote_ref).decode().splitlines()
    if len(rows) != 1 or rows[0].split() != [head, remote_ref]:
        raise ValueError("REMOTE_REJECTED")
    return head, tree


def reconstruct_release() -> tuple[VerifiedRelease, RuntimeBinding]:
    """Collect only accepted current checkout bytes, preserving exact CRLF policy."""
    head, tree = admit_source()
    files = []
    for row in _git("ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if not row:
            continue
        metadata, raw_name = row.split(b"\t", 1)
        name = raw_name.decode("utf-8")
        if name in {"pyproject.toml", LAUNCHER_RELATIVE_PATH} or name.startswith(
            "src/trading_bot/"
        ):
            mode, kind, _ = metadata.decode().split()
            if mode not in {"100644", "100755"} or kind != "blob":
                raise ValueError("SOURCE_OBJECT_REJECTED")
            data, _ = read_record(WORKTREE / name, MAX_FILE_BYTES)
            files.append(ReleaseInventoryEntry(name, hashlib.sha256(data).hexdigest()))
    inventory = tuple(sorted(files, key=lambda row: row.relative_path))
    source_namespace(tuple(row.relative_path for row in inventory))
    manifest = ReleaseManifest(
        head,
        tree,
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
    release = collect_release_bundle(WORKTREE, declaration=manifest)
    if release.manifest != manifest or admit_source() != (head, tree):
        raise ObservationDrift("SOURCE_COLLECTION_DRIFT")
    binding = RuntimeBinding(release)
    if manifest.release_id in INCIDENT_RELEASE_IDS:
        raise ValueError("INCIDENT_RELEASE_FORBIDDEN")
    return release, binding


def require_fresh_release(release: VerifiedRelease) -> None:
    """Replay supplied evidence and reject all preserved identities without IO."""
    if type(release) is not VerifiedRelease:
        raise ValueError("EXACT_VERIFIED_RELEASE_REQUIRED")
    VerifiedRelease(
        release.bundle,
        release.expected_manifest_sha256,
        release.expected_source_head,
        release.expected_source_tree,
        release.expected_source_paths,
    )
    if (
        release.expected_source_head == BASE_HEAD
        or release.expected_source_tree == BASE_TREE
        or release.manifest.release_id in INCIDENT_RELEASE_IDS
    ):
        raise ValueError("HISTORICAL_RELEASE_FORBIDDEN")
    if (
        release.manifest.production_python_version != PYTHON_VERSION
        or release.manifest.production_python_sha256 != PYTHON_SHA256
    ):
        raise ValueError("PRODUCTION_PYTHON_DECLARATION_DRIFT")


def attempt_path(release: VerifiedRelease) -> Path:
    """Derive only; do not inspect or create any installation attempt."""
    require_fresh_release(release)
    return ATTEMPT_ROOT / (
        "arch134-f1r1-d1s4-direct-install-attempt-"
        + release.manifest.release_id
        + ".json"
    )


def attempt_bytes(release: VerifiedRelease) -> bytes:
    """Canonical prospective one-shot bytes, never persisted by this module."""
    require_fresh_release(release)
    return (
        canonical_json(
            {
                "schema": ATTEMPT_SCHEMA,
                "release_id": release.manifest.release_id,
                "source_head": release.expected_source_head,
                "source_tree": release.expected_source_tree,
                "status": "CONSUMED",
                "automatic_retry": "NOT_AUTHORIZED",
            }
        )
        + "\n"
    ).encode()


def classify_attempt(
    release: VerifiedRelease, payload: bytes | None, *, absence_proven: bool = False
) -> str:
    """Pure classification of supplied evidence, never effect authorization."""
    expected = attempt_bytes(release)
    if type(absence_proven) is not bool:
        raise ValueError("EXACT_ABSENCE_FACT_REQUIRED")
    if payload is None:
        return "AVAILABLE" if absence_proven else "INDETERMINATE"
    if absence_proven or type(payload) is not bytes:
        return "INDETERMINATE"
    return "CONSUMED" if payload == expected else "INDETERMINATE"


def source_report() -> dict[str, object]:
    """Generate exact published source evidence; never invoke host preflight."""
    release, binding = reconstruct_release()
    require_fresh_release(release)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "reason": "FRESH_SUCCESSOR_SOURCE_GENERATED",
        "source_head": release.expected_source_head,
        "source_tree": release.expected_source_tree,
        "manifest": json.loads(release.manifest.to_json()),
        "manifest_sha256": release.expected_manifest_sha256,
        "source_inventory_sha256": release.manifest.source_inventory_sha256,
        "binding_sha256": binding.sha256,
        "release_id": release.manifest.release_id,
        "final_path": release_root(release.manifest.release_id),
        "installation_attempt_path": str(attempt_path(release)),
        "installation_attempt_sha256": hashlib.sha256(
            attempt_bytes(release)
        ).hexdigest(),
        "forbidden_incident_release_ids": list(INCIDENT_RELEASE_IDS),
        "forbidden_incident_roots": list(INCIDENT_ROOTS),
        "shared_parent_acl": "RECOVERED_POLICY_REQUIRED_AT_LATER_HOST_PREFLIGHT",
        "production_python_observation": "NOT_RUN",
        "final_path_observation": "NOT_RUN",
        "fresh_final_absence": "REQUIRED_AT_LATER_HOST_PREFLIGHT",
        "unexpected_final_material": "BLOCK_PRESERVE_NO_REPAIR_OR_REUSE",
        "attempt_observation": "NOT_RUN",
        "runtime_binding_eligible": False,
        "successor_soak_eligible": False,
        "execute_eligible": False,
        "effect_disposition": "NOT_STARTED",
        "automatic_retry": "NOT_AUTHORIZED",
    }
