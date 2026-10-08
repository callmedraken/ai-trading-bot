"""133-R zero-effect staged diagnosis of 133-Q plan admission."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.arch133_acl import read_only, retained_reads
from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_reprovision import generation, namespace, predecessor, reads
from trading_bot.arch133_reprovision.material import (
    digest,
    read_material,
    require_fresh,
    require_stale,
)
from trading_bot.arch133_verifier import binding, file_policy

SCHEMA = "arch133r-reprovision-admission-diagnostic/v1"
SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133r")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133r"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
LAUNCHER = SOURCE_ROOT / "scripts" / "run_arch133_reprovision_admission_diagnostic.py"
NO_PYCACHE = SOURCE_ROOT / "no-pycache"
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


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _git(root: Path, *args: str) -> str:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
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
        raise ValueError("git observation rejected")
    return result.stdout.strip()


def _clean_source(root: Path, branch: str) -> tuple[str, str]:
    head, tree = (_git(root, "rev-parse", name) for name in ("HEAD", "HEAD^{tree}"))
    if (
        any(re.fullmatch(r"[0-9a-f]{40}", value) is None for value in (head, tree))
        or Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
        != root.resolve(strict=True)
        or _git(root, "branch", "--show-current") != branch
        or _git(root, "remote", "get-url", "origin") != ORIGIN
        or _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    ):
        raise ValueError("source rejected")
    return head, tree


def _runtime() -> dict:
    if (
        sys.platform != "win32"
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or sys.pycache_prefix != str(NO_PYCACHE)
        or NO_PYCACHE.exists()
        or Path(__file__).resolve().parents[3] != SOURCE_ROOT.resolve(strict=True)
        or Path(sys.argv[0]).resolve(strict=True) != LAUNCHER.resolve(strict=True)
        or Path(sys.executable).resolve(strict=True)
        != binding.PRODUCTION_PYTHON.resolve(strict=True)
        or ".".join(map(str, sys.version_info[:3])) != binding.PRODUCTION_PYTHON_VERSION
        or hashlib.sha256(binding.PRODUCTION_PYTHON.read_bytes()).hexdigest()
        != binding.PRODUCTION_PYTHON_SHA256
    ):
        raise ValueError("runtime rejected")
    own = _clean_source(SOURCE_ROOT, SOURCE_BRANCH)
    ref = "refs/remotes/origin/" + SOURCE_BRANCH
    if (
        _git(SOURCE_ROOT, "rev-parse", ref) != own[0]
        or _git(SOURCE_ROOT, "rev-parse", ref + "^{tree}") != own[1]
    ):
        raise ValueError("remote source rejected")
    bound = _clean_source(binding.SOURCE_ROOT, binding.SOURCE_BRANCH)
    if bound not in predecessor.BOUND_CHECKOUTS:
        raise ValueError("bound source rejected")
    return {
        "operator_source_head": own[0],
        "operator_source_tree": own[1],
        "bound_source_head": predecessor.EXECUTABLE_SOURCE_HEAD,
        "bound_source_tree": predecessor.EXECUTABLE_SOURCE_TREE,
        "python_sha256": binding.PRODUCTION_PYTHON_SHA256,
        "python_version": binding.PRODUCTION_PYTHON_VERSION,
        "wake_launcher_sha256": hashlib.sha256(
            binding.LAUNCHER.read_bytes()
        ).hexdigest(),
    }


def _observe_predecessor() -> tuple[object, dict]:
    runtime = _runtime()
    administrator_sid()
    with ExitStack() as held:
        root_handle = reads.open_generation_directory(retained_reads.TARGET_PATH)
        held.callback(read_only.close_handle, root_handle)
        root, security = read_only.inspect_directory_security(
            root_handle, retained_reads.TARGET_PATH
        )
        if (
            root.identity != predecessor.ROOT_IDENTITY
            or root.filesystem != "NTFS"
            or root.reparse is not False
            or root.classification() != "EXACT_INTENDED_ROOT"
            or security != predecessor.ROOT_SECURITY_SHA256
        ):
            raise ValueError("root rejected")
        names = retained_reads.namespace(root_handle)
        if tuple(name for name, _ in names) != retained_reads.FINAL_NAMES:
            raise ValueError("namespace rejected")
        files = []
        for name in retained_reads.FINAL_NAMES:
            handle = retained_reads.open_retained_file(name)
            held.callback(read_only.close_handle, handle)
            snapshot = retained_reads.file_snapshot(handle, name)
            policy = file_policy.observe_file_policy(handle)
            file_policy.require_file_policy(name, policy)
            if snapshot != (
                (predecessor.ROOT_IDENTITY[0], dict(names)[name]),
                predecessor.FILE_HASHES[name],
            ):
                raise ValueError("file rejected")
            files.append((handle, name, snapshot, policy))
        raw = predecessor._publication_path_read()
        activation, host = predecessor._publication_parse(raw)
        predecessor._publication_semantics(runtime, raw, activation, host)
        state_path = predecessor._state_path_resolution(activation)
        state_connection = sqlite3.connect(
            state_path.as_uri() + "?mode=ro", uri=True, timeout=0
        )
        held.callback(state_connection.close)
        state_connection.execute("BEGIN")
        state = predecessor.require_ready_state(state_connection, activation)
        paper_connection = sqlite3.connect(
            binding.PAPER_PATH.as_uri() + "?mode=ro", uri=True, timeout=0
        )
        held.callback(paper_connection.close)
        paper_connection.execute("BEGIN")
        paper = predecessor.require_empty_paper(paper_connection, activation, host)
        if (
            predecessor._publication_path_read() != raw
            or predecessor._state_path_resolution(activation) != state_path
            or predecessor.require_ready_state(state_connection, activation) != state
            or predecessor.require_empty_paper(paper_connection, activation, host)
            != paper
            or retained_reads.namespace(root_handle) != names
            or read_only.inspect_directory_security(
                root_handle, retained_reads.TARGET_PATH
            )
            != (root, security)
        ):
            raise ValueError("predecessor changed")
        for handle, name, snapshot, policy in files:
            if (
                retained_reads.file_snapshot(handle, name) != snapshot
                or file_policy.observe_file_policy(handle) != policy
            ):
                raise ValueError("predecessor file changed")
    if _runtime() != runtime:
        raise ValueError("runtime changed")
    administrator_sid()
    return activation, {
        "runtime": runtime,
        "publication_files": predecessor.FILE_HASHES,
        "root_identity": list(predecessor.ROOT_IDENTITY),
        "root_security_sha256": predecessor.ROOT_SECURITY_SHA256,
        "namespace": [list(item) for item in names],
        "store_identity": str(activation.store_identity),
        "paper_predecessor_sha256": paper,
        "state_sha256": state.fingerprint,
        "wake_revision": 0,
        "consumed_wake_authority": 0,
    }


def _require_retained(old: object) -> None:
    retained = generation.predecessor_material()
    if (
        retained.activation != old
        or digest(retained.host.to_json().encode())
        != predecessor.FILE_HASHES["host-binding.json"]
    ):
        raise ValueError("retained predecessor changed")


def _parent(path: str) -> None:
    handle = read_only.open_directory(path)
    try:
        observation, security = read_only.inspect_directory_security(handle, path)
        if (
            observation.filesystem != "NTFS"
            or observation.reparse
            or observation.owner_sid != read_only.ADMINISTRATORS_SID
            or any(
                sid not in (read_only.ADMINISTRATORS_SID, read_only.SYSTEM_SID)
                and not flags & 8
                and mask & 0xD0046
                for sid, mask, _, flags in observation.aces
            )
        ):
            raise ValueError("parent rejected")
        if read_only.inspect_directory_security(handle, path) != (
            observation,
            security,
        ):
            raise ValueError("parent changed")
    finally:
        read_only.close_handle(handle)


def stage_result(stage: str, *, passed: bool = False) -> dict:
    return {
        "schema": SCHEMA,
        "status": "PASS" if passed else "BLOCKED",
        "reason": (
            "REPROVISION_ADMISSION_DIAGNOSTIC_COMPLETE"
            if passed
            else "REPROVISION_ADMISSION_DIAGNOSTIC_BLOCKED"
        ),
        "stage": "ADMISSION_COMPLETE" if passed else stage,
        **ZERO_EFFECTS,
    }


def diagnose(path: Path) -> dict:
    stage = "MATERIAL_READ"
    try:
        material = read_material(path)
        stage = "PREDECESSOR_ADMISSION"
        old, facts = _observe_predecessor()
        stage = "PREDECESSOR_MATERIAL"
        _require_retained(old)
        stage = "PREDECESSOR_STALE"
        require_stale(old, datetime.now(UTC))
        stage = "FRESH_MATERIAL"
        require_fresh(
            material, old, facts["runtime"], datetime.now(UTC)
        )
        stage = "NAMESPACE_VACANCY"
        namespace.require_vacant()
        stage = "PARENT_VOLUME"
        _parent("F:\\")
        stage = "PARENT_HOST"
        _parent(r"F:\AITradingBot")
        stage = "PARENT_COMBINED"
        with namespace.parent_guard():
            pass
        return stage_result("ADMISSION_COMPLETE", passed=True)
    except BaseException:
        return stage_result(stage)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if (
        len(args) != 2
        or args[0] != "--material-file"
        or not Path(args[1]).is_absolute()
    ):
        result = stage_result("ARGUMENTS")
    else:
        result = diagnose(Path(args[1]))
    print(canonical(result))
    return 0 if result["status"] == "PASS" else 3
