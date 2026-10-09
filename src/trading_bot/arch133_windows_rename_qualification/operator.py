"""Source-bound, real-TTY-only Y scratch qualification; production effects stay zero."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_windows_rename_qualification import native

SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133y")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133y"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
LAUNCHER = SOURCE_ROOT / "scripts/run_arch133_windows_rename_qualification.py"
NO_PYCACHE = SOURCE_ROOT / "no-pycache"
PRODUCTION_PYTHON = Path(r"F:\AITradingBot\runtime\python.exe")
PRODUCTION_PYTHON_VERSION = "3.14.3"
PRODUCTION_PYTHON_SHA256 = (
    "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
)
HOST_SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133g")
HOST_SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133g"
HOST_SOURCE_HEAD = "65f0d40217f8ce129224531a5151f4acea889d89"
HOST_SOURCE_TREE = "16cb734cbeaa9e97aaf9e2d521d922fbbc7b7ae2"
RESULT_SCHEMA = "arch133y-windows-rename-qualification/v1"
ZERO_EFFECTS = dict.fromkeys(
    (
        "credential_reads",
        "credential_writes",
        "provider_calls",
        "scheduler_reads",
        "scheduler_writes",
        "publication_writes",
        "archive_writes",
        "paper_mutations",
        "state_mutations",
        "acl_mutations",
        "wake_delegations",
        "execution_delegations",
        "consumed_wake_authority",
        "broker_effects",
        "manual_task_starts",
    ),
    0,
)
SCRATCH_COUNTERS = (
    "topology_creation_attempts",
    "topology_creations_completed",
    "first_rename_attempts",
    "first_renames_completed",
    "second_rename_attempts",
    "second_renames_completed",
    "cleanup_attempts",
    "cleanups_completed",
)


def _git(root: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    result = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(root),
            *args,
        ],
        input="",
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
        env=env,
    )
    if len(result.stdout) > 4096 or result.stderr:
        raise ValueError("source observation rejected")
    return result.stdout.strip()


def require_checkout(root: Path, branch: str) -> tuple[str, str]:
    """Require the exact fixed checkout, tracking branch, clean state and origin."""
    if (root, branch) not in (
        (SOURCE_ROOT, SOURCE_BRANCH),
        (HOST_SOURCE_ROOT, HOST_SOURCE_BRANCH),
    ):
        raise ValueError("source path rejected")
    head, tree = (_git(root, "rev-parse", n) for n in ("HEAD", "HEAD^{tree}"))
    ref = "refs/remotes/origin/" + branch
    if (
        any(re.fullmatch(r"[0-9a-f]{40}", v) is None for v in (head, tree))
        or Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
        != root.resolve(strict=True)
        or _git(root, "branch", "--show-current") != branch
        or _git(root, "remote", "get-url", "origin") != ORIGIN
        or _git(root, "status", "--porcelain=v1", "--untracked-files=all")
        or _git(
            root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
        )
        != "origin/" + branch
        or _git(root, "rev-parse", ref) != head
        or _git(root, "rev-parse", ref + "^{tree}") != tree
    ):
        raise ValueError("source rejected")
    return head, tree


def observe_runtime() -> dict:
    """Check only Y/accepted host source and interpreter; no production namespaces."""
    if (
        sys.argv[1:]
        or sys.platform != "win32"
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or sys.pycache_prefix != str(NO_PYCACHE)
        or NO_PYCACHE.exists()
        or NO_PYCACHE.is_symlink()
        or NO_PYCACHE.is_junction()
        or Path(__file__).resolve().parents[3] != SOURCE_ROOT.resolve(strict=True)
        or Path(sys.argv[0]).resolve(strict=True) != LAUNCHER.resolve(strict=True)
        or Path(sys.executable).resolve(strict=True)
        != PRODUCTION_PYTHON.resolve(strict=True)
        or ".".join(map(str, sys.version_info[:3])) != PRODUCTION_PYTHON_VERSION
        or hashlib.sha256(PRODUCTION_PYTHON.read_bytes()).hexdigest()
        != PRODUCTION_PYTHON_SHA256
    ):
        raise ValueError("runtime rejected")
    own = require_checkout(SOURCE_ROOT, SOURCE_BRANCH)
    if require_checkout(HOST_SOURCE_ROOT, HOST_SOURCE_BRANCH) != (
        HOST_SOURCE_HEAD,
        HOST_SOURCE_TREE,
    ):
        raise ValueError("host source rejected")
    return {
        "source_head": own[0],
        "source_tree": own[1],
        "source_branch": SOURCE_BRANCH,
        "python_path": str(PRODUCTION_PYTHON),
        "python_version": PRODUCTION_PYTHON_VERSION,
        "python_sha256": PRODUCTION_PYTHON_SHA256,
        "host_source_head": HOST_SOURCE_HEAD,
        "host_source_tree": HOST_SOURCE_TREE,
    }


def authorize(head: str) -> None:
    """Require one real interactive input bound to the source HEAD."""
    if re.fullmatch(r"[0-9a-f]{40}", head) is None or (
        not sys.stdin.isatty() or not sys.stdout.isatty()
    ):
        raise ValueError("interactive authorization rejected")
    phrase = "AUTHORIZE ARCH133Y " + head
    print(phrase, flush=True)
    if sys.stdin.readline(256).rstrip("\r\n") != phrase:
        raise ValueError("interactive authorization rejected")


def _result() -> dict:
    return {
        "schema": RESULT_SCHEMA,
        "status": "BLOCKED",
        "disposition": "QUALIFICATION_REJECTED",
        **ZERO_EFFECTS,
        "scratch": dict.fromkeys(SCRATCH_COUNTERS, 0),
    }


def run() -> tuple[int, dict]:
    """Qualify once, retain any ambiguous mutation, clean up only complete success."""
    result = _result()
    edge = None
    try:
        runtime = observe_runtime()
        admin = administrator_sid()
        authorize(runtime["source_head"])
        edge = native.WindowsScratch()
        edge.admit()
        if observe_runtime() != runtime or administrator_sid() != admin:
            raise ValueError("qualification admission changed")
        edge.create(result["scratch"])
        before = edge.snapshot()
        result["scratch"]["first_rename_attempts"] += 1
        edge.rename(native.ACTIVE, native.ARCHIVE)
        result["scratch"]["first_renames_completed"] += 1
        first = edge.verify(1)
        if first != before:
            raise ValueError("first rename identity drift")
        result["scratch"]["second_rename_attempts"] += 1
        edge.rename(native.STAGE, native.ACTIVE)
        result["scratch"]["second_renames_completed"] += 1
        final = edge.verify(2)
        if final != before:
            raise ValueError("second rename identity drift")
        edge.close()
        if observe_runtime() != runtime or administrator_sid() != admin:
            raise ValueError("qualification source changed")
        result["scratch"]["cleanup_attempts"] += 1
        edge.cleanup()
        result["scratch"]["cleanups_completed"] += 1
        result.update(
            status="PASS",
            disposition="RENAME_PRIMITIVE_QUALIFIED",
            runtime=runtime,
            administrator_sid=admin,
            scratch_root=native.SCRATCH_ROOT,
            before=before,
            after_first=first,
            after_second=final,
            handles_closed=True,
            scratch_root_absent=True,
        )
        return 0, result
    except BaseException as exc:
        if isinstance(exc, native.NativeError):
            value = exc.native_error_code
            result["native_error_code"] = (
                value if type(value) is int and 0 <= value <= 0xFFFFFFFF else 0
            )
        if edge is not None and edge.mutation_started:
            result.update(
                status="INDETERMINATE", disposition="PRESERVE_SCRATCH_NO_RETRY"
            )
        return 3, result
    finally:
        if edge is not None and not edge.closed:
            try:
                edge.close()
            except BaseException:
                # A close failure grants no cleanup or new effect authority.
                result.update(
                    status="INDETERMINATE" if edge.mutation_started else "BLOCKED",
                    disposition="PRESERVE_SCRATCH_NO_RETRY"
                    if edge.mutation_started
                    else "QUALIFICATION_REJECTED",
                )


def main() -> int:
    """Reject every semantic/path argument before observing source or scratch state."""
    code, result = (3, _result()) if sys.argv[1:] else run()
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return code
