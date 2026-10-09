"""Fixed 133-V reconciliation; no recovery, writer, or execution authority."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

from trading_bot.arch133_acl import read_only
from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_reprovision import generation, namespace, reads
from trading_bot.arch133_reprovision.material import read_material
from trading_bot.arch133_verifier import binding, file_policy

SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133v")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133v"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
LAUNCHER = SOURCE_ROOT / "scripts/run_arch133_reprovision_reconciliation.py"
NO_PYCACHE = SOURCE_ROOT / "no-pycache"
U_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133u")
U_BRANCH = "feature/robinhood-unattended-review-paper-133u"
U_HEAD = "49686d7f61717b9ee7452cee633d23b0c7db873e"
U_TREE = "12b430743786ba6650aa720fc27a6d9b0d95ea74"
MATERIAL_PATH = Path(r"F:\AI\temp\arch133q\fresh-material-2026-10-09.json")
MATERIAL_SHA256 = "7b55cb89e94f09a8271a7c28fad9737c0ddb1ef94aba719968ea2820ea24a686"
REVIEWED_U_PLAN_SHA256 = (
    "a223d8fa606da9cc129d5d095c6c94ec6be42f350da0bec7fe4825fe6ef8bb81"
)
ROOT_IDENTITY = (1855336320, 1407374886183770)
PREDECESSOR_NAMESPACE = (
    ("activation.json", 1407374886191165),
    ("host-binding.json", 562949956059198),
    ("paper.sqlite", 562949956054077),
    ("wake.sqlite", 1125899909477979),
)
FILE_HASHES = {
    "activation.json": (
        "37873b490c3f2ccced53431c599e40ca54fdc008e09e9bfdb38eb61d10f3cab2"
    ),
    "host-binding.json": (
        "c1106d1937dab615da0f12eb9170c020add2ffdece3d3b88a10d2edf26eb47ab"
    ),
    "paper.sqlite": "384828dd21e9abc82afabec955184eed22cf57839e72bcd43c74d162534663b9",
    "wake.sqlite": "210812b956aba6d59dcf3cfbf398ebd628c972cfffbb6dd39bd96ef308a6887f",
}
RESULT_SCHEMA = "arch133v-reprovision-reconciliation/v1"
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
    """Require a clean named tracking checkout with exact local origin identity."""
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
    """Admit only the isolated exact production interpreter and V/U sources."""
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
    own = require_checkout(SOURCE_ROOT, SOURCE_BRANCH)
    if require_checkout(U_ROOT, U_BRANCH) != (U_HEAD, U_TREE):
        raise ValueError("consumed source rejected")
    return {
        "source_root": str(SOURCE_ROOT),
        "source_branch": SOURCE_BRANCH,
        "source_head": own[0],
        "source_tree": own[1],
        "u_source_root": str(U_ROOT),
        "u_source_branch": U_BRANCH,
        "u_source_head": U_HEAD,
        "u_source_tree": U_TREE,
        "python_path": str(binding.PRODUCTION_PYTHON),
        "python_sha256": binding.PRODUCTION_PYTHON_SHA256,
        "python_version": binding.PRODUCTION_PYTHON_VERSION,
    }


def presence(path: str, held: ExitStack) -> int | None:
    """Read-only/no-follow open: only FILE/PATH_NOT_FOUND means absent."""
    if path not in (generation.ACTIVE, generation.ARCHIVE):
        raise ValueError("presence path rejected")
    try:
        handle = read_only.open_directory(path)
    except read_only.RootOpenError as exc:
        if exc.win32_error in (2, 3):
            return None
        raise
    held.callback(read_only.close_handle, handle)
    return handle


def hold_generation(root: str, directory: int, held: ExitStack) -> dict:
    """Pin every root/file security, namespace identity and byte observation."""
    observation, security = read_only.inspect_directory_security(directory, root)
    if observation.filesystem != "NTFS" or observation.reparse is not False:
        raise ValueError("root rejected")
    names = reads.namespace(directory)
    files = {}
    for name, identity in names:
        handle = reads.open_generation_file(root, name)
        held.callback(read_only.close_handle, handle)
        snapshot = reads.file_snapshot(handle, root, name)
        policy = file_policy.observe_file_policy(handle)
        if snapshot[0] != (observation.identity[0], identity):
            raise ValueError("file identity rejected")
        files[name] = (handle, snapshot, policy)
    return {
        "directory": directory,
        "observation": observation,
        "security": security,
        "namespace": names,
        "files": files,
    }


def require_predecessor(facts: dict) -> None:
    """Verify fixed consumed-plan identities/bytes and accepted sealed policies."""
    root = facts["observation"]
    if (
        root.identity != ROOT_IDENTITY
        or root.classification() != "ADMIN_SYSTEM_ONLY"
        or root.filesystem != "NTFS"
        or root.reparse is not False
        or facts["namespace"] != PREDECESSOR_NAMESPACE
    ):
        raise ValueError("predecessor rejected")
    for name, identity in PREDECESSOR_NAMESPACE:
        _, snapshot, policy = facts["files"][name]
        if snapshot != ((ROOT_IDENTITY[0], identity), FILE_HASHES[name]):
            raise ValueError("predecessor file rejected")
        generation.require_archive_file(name, policy)


def reobserve(root: str, facts: dict) -> None:
    if (
        read_only.inspect_directory_security(facts["directory"], root)
        != (facts["observation"], facts["security"])
        or reads.namespace(facts["directory"]) != facts["namespace"]
    ):
        raise ValueError("generation changed")
    for name, (handle, snapshot, policy) in facts["files"].items():
        if (
            reads.file_snapshot(handle, root, name) != snapshot
            or file_policy.observe_file_policy(handle) != policy
        ):
            raise ValueError("file changed")


def reconcile() -> dict:
    runtime = observe_runtime()
    administrator_sid()
    material = read_material(MATERIAL_PATH)
    if material.sha256 != MATERIAL_SHA256:
        raise ValueError("material rejected")
    with namespace.parent_guard() as parents, ExitStack() as held:
        active = presence(generation.ACTIVE, held)
        archive = presence(generation.ARCHIVE, held)
        if (active is None) == (archive is None):
            raise ValueError("topology rejected")
        root, directory, absent, disposition = (
            (
                generation.ACTIVE,
                active,
                generation.ARCHIVE,
                "ARCHIVE_RENAME_NOT_COMMITTED",
            )
            if active is not None
            else (
                generation.ARCHIVE,
                archive,
                generation.ACTIVE,
                "ARCHIVE_RENAME_COMMITTED",
            )
        )
        staging = read_only.open_directory(generation.STAGING_PARENT)
        held.callback(read_only.close_handle, staging)
        staging_security = read_only.inspect_directory_security(
            staging, generation.STAGING_PARENT
        )
        observed = staging_security[0]
        if (
            observed.classification() != "ADMIN_SYSTEM_ONLY"
            or observed.filesystem != "NTFS"
            or observed.reparse is not False
            or observed.identity[0] != ROOT_IDENTITY[0]
            or tuple(p.name for p in Path(generation.STAGING_PARENT).iterdir())
            != ("generation",)
        ):
            raise ValueError("staging parent rejected")
        stage_handle = read_only.open_directory(generation.STAGE)
        held.callback(read_only.close_handle, stage_handle)
        predecessor = hold_generation(root, directory, held)
        require_predecessor(predecessor)
        stage = hold_generation(generation.STAGE, stage_handle, held)
        fresh = generation.observe_generation(generation.STAGE, material)
        if (
            fresh["root_identity"] != list(stage["observation"].identity)
            or fresh["root_security_sha256"] != stage["security"]
        ):
            raise ValueError("stage changed")
        for name, (_, snapshot, policy) in stage["files"].items():
            if fresh["files"][name] != {
                "identity": list(snapshot[0]),
                "sha256": snapshot[1],
                "policy": asdict(policy),
            }:
                raise ValueError("stage changed")
        if (
            observe_runtime() != runtime
            or read_material(MATERIAL_PATH).raw != material.raw
            or generation.observe_generation(generation.STAGE, material) != fresh
        ):
            raise ValueError("admission changed")
        administrator_sid()
        reobserve(root, predecessor)
        reobserve(generation.STAGE, stage)
        if (
            presence(absent, held) is not None
            or read_only.inspect_directory_security(staging, generation.STAGING_PARENT)
            != staging_security
            or tuple(p.name for p in Path(generation.STAGING_PARENT).iterdir())
            != ("generation",)
        ):
            raise ValueError("namespace changed")
        evidence = {
            "runtime": runtime,
            "parents": parents,
            "material_sha256": MATERIAL_SHA256,
            "reviewed_u_plan_sha256": REVIEWED_U_PLAN_SHA256,
            "predecessor_root": root,
            "predecessor_root_identity": list(predecessor["observation"].identity),
            "predecessor_security_sha256": predecessor["security"],
            "predecessor_namespace": predecessor["namespace"],
            "predecessor_files": {
                name: {
                    "identity": list(snapshot[0]),
                    "sha256": snapshot[1],
                    "policy": asdict(policy),
                }
                for name, (_, snapshot, policy) in predecessor["files"].items()
            },
            "staging_parent_identity": list(observed.identity),
            "staging_parent_security_sha256": staging_security[1],
            "stage": fresh,
            "disposition": disposition,
        }
    # PASS is constructed only after all held closes and parent re-observation.
    return evidence


def run() -> tuple[int, dict]:
    try:
        evidence = reconcile()
        return 0, {
            "schema": RESULT_SCHEMA,
            "status": "PASS",
            **evidence,
            **ZERO_EFFECTS,
        }
    except BaseException:
        return 3, {
            "schema": RESULT_SCHEMA,
            "status": "BLOCKED",
            "disposition": "RECONCILIATION_UNRESOLVED",
            **ZERO_EFFECTS,
        }


def main() -> int:
    if sys.argv[1:]:
        code, evidence = (
            3,
            {
                "schema": RESULT_SCHEMA,
                "status": "BLOCKED",
                "disposition": "RECONCILIATION_UNRESOLVED",
                **ZERO_EFFECTS,
            },
        )
    else:
        code, evidence = run()
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return code
