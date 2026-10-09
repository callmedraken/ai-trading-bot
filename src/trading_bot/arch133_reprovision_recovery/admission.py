"""Independent read-only 133-W admission of the exact V-proven durable state."""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

from trading_bot.arch133_acl import read_only
from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_reprovision import generation, namespace, predecessor, reads
from trading_bot.arch133_reprovision.material import Material, digest, read_material
from trading_bot.arch133_verifier import binding, file_policy

SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133w")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133w"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
LAUNCHER = SOURCE_ROOT / "scripts/run_arch133_reprovision_recovery.py"
NO_PYCACHE = SOURCE_ROOT / "no-pycache"
V_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133v")
V_BRANCH = "feature/robinhood-unattended-review-paper-133v"
V_HEAD = "432001e3dcae48e589adf8e60c7dac5ffc08d591"
V_TREE = "96f2f41caa6d17a32fe729ae8786560252a0c9a8"
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
    if require_checkout(V_ROOT, V_BRANCH) != (V_HEAD, V_TREE):
        raise ValueError("consumed V source rejected")
    # The accepted host composition remains bound to the frozen published runtime.
    if require_checkout(binding.SOURCE_ROOT, binding.SOURCE_BRANCH) != (
        predecessor.PUBLISHED_RUNTIME_HEAD,
        predecessor.PUBLISHED_RUNTIME_TREE,
    ):
        raise ValueError("published runtime source rejected")
    return {
        "v_source_root": str(V_ROOT),
        "v_source_branch": V_BRANCH,
        "v_source_head": V_HEAD,
        "v_source_tree": V_TREE,
        "bound_source_head": predecessor.EXECUTABLE_SOURCE_HEAD,
        "bound_source_tree": predecessor.EXECUTABLE_SOURCE_TREE,
        "wake_launcher_sha256": digest(binding.LAUNCHER.read_bytes()),
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
    """Read-only no-follow observation compatible with held DELETE sources."""
    if path not in (generation.ACTIVE, generation.ARCHIVE, generation.STAGE):
        raise ValueError("presence path rejected")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    create = api.CreateFileW
    create.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create.restype = ctypes.c_void_p
    handle = create(path, 0x20081, 7, None, 3, 0x02200000, None)
    if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
        error = ctypes.get_last_error()
        if error in (2, 3):
            return None
        raise read_only.RootOpenError(error)
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
        handle = reads.open_generation_file(root, name, renaming=True)
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
        facts["security"] != SEALED_SECURITY_SHA256
        or root.identity != ROOT_IDENTITY
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


SEALED_SECURITY_SHA256 = (
    "d6f7112da6508b0413e243fb666e98d7711a8adffcd618623c1f4c78f68efdab"
)
STAGING_PARENT_IDENTITY = (1855336320, 2251799815590570)
STAGING_PARENT_SECURITY_SHA256 = (
    "b8fc336502437d1599a257da32a20bb62966663bb20fa44694d614c0f59361a3"
)
STAGE_IDENTITY = (1855336320, 844424933411687)
STAGE_SECURITY_SHA256 = (
    "6f37254510de5246c3d8427a49743f013c339f60c205a2464b46e8aa4f8ab5c7"
)
STAGE_FILES = {
    "activation.json": (
        281474979990386,
        "27600cc899eeeb22b81aff32e460299e1bf44c7e7ba00a42772d5808dc8aef24",
    ),
    "host-binding.json": (
        281474979990387,
        "1ad3ae62cca87c6d6ccbd5c08f48dd0c3199b0f857981a2295d114157dfe5a65",
    ),
    "paper.sqlite": (
        1970324840254325,
        "bc9cea80d7384106233adae55f858c39951194f06b504fb21ef18e1960e6a68d",
    ),
    "wake.sqlite": (
        281474979990388,
        "df74e849655832eb202876364aca1147f243624037631a0c9a0a358353661877",
    ),
}
STAGE_STATE_SHA256 = "6454b1132ee93ac5af6694b2c30ae3645ccf42ea0aed98e6bf4035cedf477967"
STAGE_PAPER_SHA256 = "bf437d0a1a0313dda9480f3a791fa711467f503a80302287e0f56751c32375c8"
STAGE_ACTIVATION_ID = "3ca52d02-55cf-57d2-a8c2-fd1020cd51f7"
STAGE_WAKE_ID = "917fed9a-2b0b-5fce-ba9e-2cfb94b51470"


def require_stage(fresh: dict) -> None:
    """Require exact V root/files plus the accepted fresh-generation policies."""
    if (
        fresh["root_identity"] != list(STAGE_IDENTITY)
        or fresh["root_security_sha256"] != STAGE_SECURITY_SHA256
        or fresh["state_sha256"] != STAGE_STATE_SHA256
        or fresh["paper_predecessor_sha256"] != STAGE_PAPER_SHA256
        or fresh["activation_id"] != STAGE_ACTIVATION_ID
        or fresh["wake_id"] != STAGE_WAKE_ID
        or type(fresh["wake_revision"]) is not int
        or fresh["wake_revision"] != 0
        or set(fresh["files"]) != set(STAGE_FILES)
    ):
        raise ValueError("V stage rejected")
    for name, (identity, sha) in STAGE_FILES.items():
        found = fresh["files"][name]
        if found["identity"] != [STAGE_IDENTITY[0], identity] or found["sha256"] != sha:
            raise ValueError("V stage file rejected")
        file_policy.require_file_policy(name, file_policy.FilePolicy(**found["policy"]))


def read_predecessor(root: str, facts: dict, held: ExitStack) -> tuple[Material, dict]:
    """Verify fixed sealed bytes and independent read-only READY/empty stores."""
    require_predecessor(facts)
    path = Path(root)
    raw = (
        (path / "activation.json").read_bytes(),
        (path / "host-binding.json").read_bytes(),
    )
    if any(
        digest(value) != FILE_HASHES[name]
        for name, value in zip(
            ("activation.json", "host-binding.json"), raw, strict=True
        )
    ):
        raise ValueError("predecessor publication rejected")
    from trading_bot.arch133_reprovision.material import canonical

    retained = Material.parse(
        canonical(
            {
                "schema": "arch133q-fresh-activation-material/v1",
                "activation": raw[0].decode(),
                "host_binding": raw[1].decode(),
            }
        ).encode()
    )
    if raw != (
        retained.activation.to_json().encode(),
        retained.host.to_json().encode(),
    ):
        raise ValueError("predecessor canonical material rejected")
    connections = []
    for name in ("wake.sqlite", "paper.sqlite"):
        connection = sqlite3.connect(
            (path / name).as_uri() + "?mode=ro", uri=True, timeout=0
        )
        held.callback(connection.close)
        connection.execute("BEGIN")
        connections.append(connection)
    state = predecessor.require_ready_state(connections[0], retained.activation)
    paper = predecessor.require_empty_paper(
        connections[1], retained.activation, retained.host
    )
    return retained, {
        "root_identity": list(facts["observation"].identity),
        "root_security_sha256": facts["security"],
        "files": {
            name: {
                "identity": list(snapshot[0]),
                "sha256": snapshot[1],
                "policy": asdict(policy),
            }
            for name, (_, snapshot, policy) in facts["files"].items()
        },
        "state_sha256": state.fingerprint,
        "paper_predecessor_sha256": paper,
        "wake_revision": 0,
        "activation_id": str(retained.activation.activation_id),
        "wake_id": str(state.current(retained.activation).wake.wake_id),
    }


def require_staging_parent(
    observation: read_only.DirectoryObservation, security: str
) -> None:
    if (
        observation.identity != STAGING_PARENT_IDENTITY
        or security != STAGING_PARENT_SECURITY_SHA256
        or observation.classification() != "ADMIN_SYSTEM_ONLY"
        or observation.filesystem != "NTFS"
        or observation.reparse is not False
    ):
        raise ValueError("V staging parent rejected")


def observe_state() -> tuple[dict, Material, Material]:
    """Complete independent V-state observation; no time or mutation authority."""
    runtime = observe_runtime()
    admin_sid = administrator_sid()
    material = read_material(MATERIAL_PATH)
    if material.sha256 != MATERIAL_SHA256:
        raise ValueError("material rejected")
    with namespace.parent_guard() as parents, ExitStack() as held:
        directory = presence(generation.ACTIVE, held)
        if directory is None or presence(generation.ARCHIVE, held) is not None:
            raise ValueError("V topology rejected")
        staging = reads.open_generation_directory(generation.STAGING_PARENT)
        held.callback(read_only.close_handle, staging)
        staging_security = read_only.inspect_directory_security(
            staging, generation.STAGING_PARENT
        )
        require_staging_parent(*staging_security)
        if tuple(p.name for p in Path(generation.STAGING_PARENT).iterdir()) != (
            "generation",
        ):
            raise ValueError("V staging namespace rejected")
        stage_handle = reads.open_generation_directory(generation.STAGE)
        held.callback(read_only.close_handle, stage_handle)
        sealed = hold_generation(generation.ACTIVE, directory, held)
        retained, previous = read_predecessor(generation.ACTIVE, sealed, held)
        stage = hold_generation(generation.STAGE, stage_handle, held)
        fresh = generation.observe_generation(generation.STAGE, material)
        require_stage(fresh)
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
        reobserve(generation.ACTIVE, sealed)
        reobserve(generation.STAGE, stage)
        if (
            presence(generation.ARCHIVE, held) is not None
            or read_only.inspect_directory_security(staging, generation.STAGING_PARENT)
            != staging_security
            or tuple(p.name for p in Path(generation.STAGING_PARENT).iterdir())
            != ("generation",)
        ):
            raise ValueError("namespace changed")
        facts = {
            "administrator_sid": admin_sid,
            "runtime": runtime,
            "parents": parents,
            "predecessor": previous,
            "material_sha256": MATERIAL_SHA256,
            "reviewed_u_plan_sha256": REVIEWED_U_PLAN_SHA256,
            "staging_parent_identity": list(STAGING_PARENT_IDENTITY),
            "staging_parent_security_sha256": STAGING_PARENT_SECURITY_SHA256,
            "stage": fresh,
            "active_root": generation.ACTIVE,
            "archive_root": generation.ARCHIVE,
            "staging_parent": generation.STAGING_PARENT,
            "staged_root": generation.STAGE,
        }
    return facts, material, retained
