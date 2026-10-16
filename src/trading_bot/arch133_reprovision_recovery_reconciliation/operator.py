"""Fixed 133-X post-W reconciliation; no recovery, writer, or execution authority."""

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
from trading_bot.arch133_reprovision import generation, namespace, predecessor
from trading_bot.arch133_reprovision.material import read_material
from trading_bot.arch133_reprovision_recovery import admission
from trading_bot.arch133_verifier import binding

SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133x")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133x"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
LAUNCHER = SOURCE_ROOT / "scripts/run_arch133_reprovision_recovery_reconciliation.py"
NO_PYCACHE = SOURCE_ROOT / "no-pycache"
V_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133v")
V_BRANCH = "feature/robinhood-unattended-review-paper-133v"
V_HEAD = "432001e3dcae48e589adf8e60c7dac5ffc08d591"
V_TREE = "96f2f41caa6d17a32fe729ae8786560252a0c9a8"
W_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133w")
W_BRANCH = "feature/robinhood-unattended-review-paper-133w"
W_HEAD = "ca550cc9310aa59b2e42369491980402b2adf2c2"
W_TREE = "3bd825fdaba21037c3381b504f5b545b13702e2d"
REVIEWED_W_PLAN_SHA256 = (
    "a9a88fb1b505c138cb50887e9e06aebbfc7805c5a0a19d48f7f1f14dbeec60a4"
)
U_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133u")
U_BRANCH = "feature/robinhood-unattended-review-paper-133u"
U_HEAD = "49686d7f61717b9ee7452cee633d23b0c7db873e"
U_TREE = "12b430743786ba6650aa720fc27a6d9b0d95ea74"
MATERIAL_PATH = Path(r"F:\AI\temp\arch133q\fresh-material-2026-10-09.json")
MATERIAL_SHA256 = "7b55cb89e94f09a8271a7c28fad9737c0ddb1ef94aba719968ea2820ea24a686"
REVIEWED_U_PLAN_SHA256 = (
    "a223d8fa606da9cc129d5d095c6c94ec6be42f350da0bec7fe4825fe6ef8bb81"
)
RESULT_SCHEMA = "arch133x-reprovision-recovery-reconciliation/v1"
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
    """Admit the isolated production interpreter and exact X/W/V/U sources."""
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
    if require_checkout(V_ROOT, V_BRANCH) != (V_HEAD, V_TREE):
        raise ValueError("consumed V source rejected")
    if require_checkout(W_ROOT, W_BRANCH) != (W_HEAD, W_TREE):
        raise ValueError("consumed W source rejected")
    # The accepted host composition remains bound to the frozen published runtime.
    if require_checkout(binding.SOURCE_ROOT, binding.SOURCE_BRANCH) != (
        predecessor.PUBLISHED_RUNTIME_HEAD,
        predecessor.PUBLISHED_RUNTIME_TREE,
    ):
        raise ValueError("published runtime source rejected")
    return {
        "w_source_root": str(W_ROOT),
        "w_source_branch": W_BRANCH,
        "w_source_head": W_HEAD,
        "w_source_tree": W_TREE,
        "v_source_root": str(V_ROOT),
        "v_source_branch": V_BRANCH,
        "v_source_head": V_HEAD,
        "v_source_tree": V_TREE,
        "bound_source_head": predecessor.EXECUTABLE_SOURCE_HEAD,
        "bound_source_tree": predecessor.EXECUTABLE_SOURCE_TREE,
        "wake_launcher_sha256": hashlib.sha256(
            binding.LAUNCHER.read_bytes()
        ).hexdigest(),
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


def reconcile() -> dict:
    runtime = observe_runtime()
    admin_sid = administrator_sid()
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
                "W_ARCHIVE_RENAME_NOT_COMMITTED",
            )
            if active is not None
            else (
                generation.ARCHIVE,
                archive,
                generation.ACTIVE,
                "W_ARCHIVE_RENAME_COMMITTED",
            )
        )
        staging = read_only.open_directory(generation.STAGING_PARENT)
        held.callback(read_only.close_handle, staging)
        staging_security = read_only.inspect_directory_security(
            staging, generation.STAGING_PARENT
        )
        admission.require_staging_parent(*staging_security)
        observed = staging_security[0]
        if tuple(p.name for p in Path(generation.STAGING_PARENT).iterdir()) != (
            "generation",
        ):
            raise ValueError("staging namespace rejected")
        stage_handle = read_only.open_directory(generation.STAGE)
        held.callback(read_only.close_handle, stage_handle)
        sealed = admission.hold_generation(root, directory, held)
        admission.require_predecessor(sealed)
        stage = admission.hold_generation(generation.STAGE, stage_handle, held)
        fresh = generation.observe_generation(generation.STAGE, material)
        admission.require_stage(fresh)
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
        if administrator_sid() != admin_sid:
            raise ValueError("administrator changed")
        admission.reobserve(root, sealed)
        admission.reobserve(generation.STAGE, stage)
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
            "reviewed_w_plan_sha256": REVIEWED_W_PLAN_SHA256,
            "administrator_sid": admin_sid,
            "predecessor_root": root,
            "predecessor_root_identity": list(sealed["observation"].identity),
            "predecessor_security_sha256": sealed["security"],
            "predecessor_namespace": sealed["namespace"],
            "predecessor_files": {
                name: {
                    "identity": list(snapshot[0]),
                    "sha256": snapshot[1],
                    "policy": asdict(policy),
                }
                for name, (_, snapshot, policy) in sealed["files"].items()
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
