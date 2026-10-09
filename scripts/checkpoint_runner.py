"""Unified source-checkpoint runner for AI Trading Bot development.

This module centralizes source verification, read-only host preflight, and
registered protected checkpoint execution. Protected execution remains opt-in,
checkpoint-specific, and authorization-gated.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_SRC_ROOT = _REPOSITORY_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

SCHEMA: Final = "ai-trading-bot-checkpoint-runner/v1"
REMOTE_LOOKUP_TIMEOUT_SECONDS: Final = 30
R5_TRADING_PID_ENV: Final = "AI_TRADING_BOT_ARCH128_R5_TRADING_PID"
R5_TRADING_REMOTE_HEAD_ENV: Final = "AI_TRADING_BOT_ARCH128_R5_ADMIN_REMOTE_HEAD"
R5_PRODUCTION_PYTHON: Final = Path(r"F:\AITradingBot\runtime\python.exe")
R5_PYCACHE_PREFIX: Final = r"F:\AITradingBot\D10\no-pycache"


@dataclass(frozen=True, slots=True)
class CheckpointSpec:
    name: str
    description: str
    tests: tuple[str, ...]
    ruff_paths: tuple[str, ...]
    authority_check: Callable[[Path], tuple[str, ...]]
    preflight: Callable[[], dict[str, object]] | None = None
    execute: Callable[[], dict[str, object]] | None = None
    remote_branch: str | None = None
    remote_head_env: str | None = None


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    argv: tuple[str, ...]
    diagnostic_argv: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    name: str
    argv: tuple[str, ...]
    exit_code: int
    stdout_bytes: int
    stderr_bytes: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_path: str
    stderr_path: str
    elapsed_seconds: float = 0.0


COMMON_TESTS: Final = (
    "tests/runtime/checkpoint_runner/test_core.py",
    "tests/runtime/checkpoint_runner/test_ci.py",
)
COMMON_RUFF_PATHS: Final = (
    "scripts/checkpoint_runner.py",
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/helpers.py",
    "tests/runtime/checkpoint_runner/__init__.py",
)
ARCH131_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_arch131.py",
)
ARCH131_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_arch131.py",
)
ARCH133_A_G_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
)
ARCH133_A_G_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
)
ARCH133_H_K_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
)
ARCH133_H_K_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
)
ARCH133_L_M_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
)
ARCH133_L_M_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
)
RETAINED_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_retained_arch128_130.py",
)
RETAINED_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_retained_arch128_130.py",
)


RETAINED_CHECKPOINTS: Final = (
    "arch128-parent-acl-repair",
    "arch128-r4",
    "arch128-r5-substrate",
    "arch128-r5-trading",
    "arch128-r6",
    "arch128-r7",
    "arch128-r8-terminal-halt",
    "arch130-r8i-d1",
)

ACTIVE_CI_CHECKPOINTS: Final = (
    "arch133-robinhood-supervised-release-foundation",
    "arch131-robinhood-review-paper",
    "arch131-robinhood-mcp-schema",
    "arch131-robinhood-paper-cycle",
    "arch131-robinhood-performance",
    "arch131-robinhood-direct-mcp",
    "arch131-robinhood-oauth-windows",
    "arch131-robinhood-agentic-account",
    "arch131-robinhood-paper-operator",
    "arch131-robinhood-paper-intent-bridge",
    "arch131-robinhood-deterministic-paper-pipeline",
    "arch131-robinhood-virtual-risk-context",
    "arch131-robinhood-forward-paper-cycle",
    "arch131-robinhood-live-qualification-verifier",
    "arch131-robinhood-session-admission",
    "arch131-robinhood-risk-price-snapshot",
    "arch131-robinhood-forward-paper-preview",
    "arch131-robinhood-risk-price-acquisition",
    "arch131-robinhood-supervised-forward-paper",
    "arch131-robinhood-supervised-prepare-qualification",
    "arch131-robinhood-supervised-prepare-verifier",
    "arch131-nyse-published-regular-session-authority",
    "arch131-robinhood-published-session-prepare",
    "arch131-robinhood-published-prepare-operator",
    "arch131-robinhood-supervised-qualification",
    "arch133-robinhood-unattended-activation-core",
    "arch133-robinhood-unattended-state-store",
    "arch133-robinhood-unattended-one-wake-composition",
    "arch133-robinhood-unattended-review-paper-execution",
    "arch133-robinhood-unattended-host-scheduler-surface",
    "arch133-robinhood-unattended-host-bootstrap",
    "arch133-robinhood-unattended-host-publication",
    "arch133-robinhood-scratch-root-acl-qualification",
    "arch133-robinhood-retained-root-diagnostic",
    "arch133-robinhood-retained-root-acl-recovery",
    "arch133-robinhood-post-publication-verifier",
    "arch133-robinhood-post-publication-stage-diagnostic",
    "arch133-robinhood-publication-state-paper-diagnostic",
    "arch133-robinhood-publication-state-paper-corrected",
    "arch133-robinhood-single-session-scheduler-installation",
    "arch133-robinhood-fresh-activation-reprovision",
    "arch133-robinhood-reprovision-admission-diagnostic",
    "arch133-robinhood-reprovision-parent-security-diagnostic",
    "arch133-robinhood-reprovision-parent-policy-diagnostic",
    "arch133-robinhood-fresh-activation-reprovision-corrected",
    "arch133-robinhood-reprovision-indeterminate-reconciliation",
    "arch133-robinhood-reprovision-sealed-predecessor-recovery",
    "arch133-robinhood-reprovision-recovery-reconciliation",
    "arch133-robinhood-windows-rename-qualification",
    "arch133-robinhood-closed-descendant-rename-qualification",
)


def _batch_workflow_is_reviewed(workflow: str) -> bool:
    # Freeze the executable active batch command, its participants and their order,
    # and exit propagation. Comments, duplicates and missing phases must drift.
    invocation = (
        "          & powershell.exe -NoProfile -ExecutionPolicy Bypass "
        "-File .\\ops.ps1 `\n"
        "            verify-batch `\n"
        + "".join(
            f"              {name}"
            + (" `\n" if index < len(ACTIVE_CI_CHECKPOINTS) - 1 else "\n")
            for index, name in enumerate(ACTIVE_CI_CHECKPOINTS)
        )
        + "          exit $LASTEXITCODE\n"
    )
    return (
        workflow.count("verify-batch") == 1
        and workflow.count(invocation) == 1
        and "verify arch" not in workflow
    )


def _git_blob_sha1(path: Path) -> str:
    # Text mode normalizes Git's LF source across Windows checkout CRLF.
    data = path.read_text(encoding="utf-8").encode("utf-8")
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
    ).hexdigest()


def _qualified_names(node: ast.AST) -> set[str]:
    result: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            result.add(item.id)
        elif isinstance(item, ast.Attribute):
            parts: list[str] = []
            current: ast.AST = item
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                result.add(".".join(reversed(parts)))
    return result


def _top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _r4_authority_check(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "scripts" / "d10_arch128_r4_operator.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level_functions(tree)
    failures: list[str] = []

    required_functions = {
        "_read_only_preflight",
        "_execute_once",
        "_dispatch",
        "main",
    }
    missing_functions = sorted(required_functions - set(functions))
    if missing_functions:
        failures.append(f"missing functions: {missing_functions}")
        return tuple(failures)

    readonly_names = _qualified_names(functions["_read_only_preflight"])
    forbidden_readonly = {
        "r4w.WindowsArch128StagingBackend",
        "r4w.rename_fixed_step",
        "r4c._construct_staging",
        "r4c._ReplacementSession",
    }
    bad_readonly = sorted(forbidden_readonly & readonly_names)
    if bad_readonly:
        failures.append(
            f"read-only mode references protected mutation symbols: {bad_readonly}"
        )

    execute_names = _qualified_names(functions["_execute_once"])
    required_execute = {
        "r4w.WindowsArch128StagingBackend",
        "r4w.WindowsArch128ReadOnlyReader",
        "r4c._construct_staging",
        "r4c._ReplacementSession",
        "r4w.rename_fixed_step",
    }
    missing_execute = sorted(required_execute - execute_names)
    if missing_execute:
        failures.append(f"protected mode missing fixed bindings: {missing_execute}")

    dispatch_source = ast.get_source_segment(source, functions["_dispatch"]) or ""
    for required in ("READ_ONLY_FLAG", "EXECUTE_FLAG", "AUTH_ENV", "AUTH_VALUE"):
        if required not in dispatch_source:
            failures.append(f"dispatch interlock missing: {required}")

    for forbidden in (
        "RegisterTask",
        "RegisterTaskDefinition",
        "DeleteTask",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "WindowsActivationLeaseBackend",
        "publish_activation",
        "rmtree",
        "unlink(",
        "os.rename",
    ):
        if forbidden in source:
            failures.append(
                f"operator contains forbidden authority surface: {forbidden}"
            )

    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    runner_source = runner_path.read_text(encoding="utf-8")
    runner_tree = ast.parse(runner_source, filename=str(runner_path))
    runner_functions = _top_level_functions(runner_tree)
    r4_execute = runner_functions.get("_r4_execute")
    if r4_execute is None:
        failures.append("runner missing _r4_execute")
    else:
        execute_names = _qualified_names(r4_execute)
        for required in (
            "operator._dispatch",
            "operator.EXECUTE_FLAG",
            "os.environ",
        ):
            if required not in execute_names:
                failures.append(
                    f"runner R4 execute missing reviewed dispatch binding: {required}"
                )
        for forbidden in (
            "operator._execute_once",
            "r4c._construct_staging",
            "r4c._ReplacementSession",
            "r4w.WindowsArch128StagingBackend",
            "r4w.rename_fixed_step",
        ):
            if forbidden in execute_names:
                failures.append(
                    f"runner R4 execute bypasses reviewed interlock: {forbidden}"
                )

    return tuple(failures)


def _r5_authority_check(repo_root: Path) -> tuple[str, ...]:
    child_path = repo_root / "scripts" / "d10_arch128_r5_trading_child.py"
    child_source = child_path.read_text(encoding="utf-8")
    child_tree = ast.parse(child_source, filename=str(child_path))
    child_functions = _top_level_functions(child_tree)
    failures: list[str] = []

    qualify = child_functions.get("_qualify")
    if qualify is None:
        failures.append("R5 Trading child missing _qualify")
    else:
        names = _qualified_names(qualify)
        for required in (
            "guard_module._verify_pre_source",
            "guard_module._Native",
            "guard_module._require_facts",
            "guard_module._stable",
            "backend.require_absent",
            "backend.listdir",
        ):
            if required not in names:
                failures.append(
                    f"R5 Trading child missing read-only binding: {required}"
                )
        for forbidden in (
            "guard_module.main",
            "guard_module._run_second_stage_with_evidence",
            "backend.append_exact",
            "backend.open_evidence_file",
        ):
            if forbidden in names:
                failures.append(
                    f"R5 Trading child references effect binding: {forbidden}"
                )

    for forbidden in (
        "RegisterTask",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "WindowsActivationLeaseBackend",
        "publish_activation",
        "WriteFile",
        "MoveFile",
        "os.rename",
        "unlink(",
        "rmtree",
    ):
        if forbidden in child_source:
            failures.append(f"R5 Trading child contains forbidden surface: {forbidden}")

    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    runner_source = runner_path.read_text(encoding="utf-8")
    runner_tree = ast.parse(runner_source, filename=str(runner_path))
    runner_functions = _top_level_functions(runner_tree)
    substrate = runner_functions.get("_r5_substrate_preflight")
    trading = runner_functions.get("_r5_trading_preflight")
    if substrate is None:
        failures.append("runner missing _r5_substrate_preflight")
    else:
        names = _qualified_names(substrate)
        for required in ("h.collect", "w.WindowsCollector", "os.environ"):
            if required not in names:
                failures.append(f"R5 substrate runner missing binding: {required}")
    if trading is None:
        failures.append("runner missing _r5_trading_preflight")
    else:
        names = _qualified_names(trading)
        for required in ("subprocess.run", "json.loads"):
            if required not in names:
                failures.append(f"R5 Trading runner missing binding: {required}")

    return tuple(failures)


def _r6_authority_check(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "scripts" / "d10_arch128_r6_reactivation.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level_functions(tree)
    failures: list[str] = []

    for required in (
        "derive_reactivation_plan",
        "_require_evidence",
        "_require_trading_probe",
        "_require_admission",
    ):
        if required not in functions:
            failures.append(f"R6 source missing required function: {required}")

    forbidden = (
        "subprocess",
        "ctypes",
        "Start-ScheduledTask",
        "RegisterTask",
        "RegisterTaskDefinition",
        "WindowsActivationLeaseBackend",
        "WindowsDeploymentBackend",
        "CreateFileW",
        "MoveFile",
        "os.remove",
        "os.unlink",
        "shutil.rmtree",
    )
    for token in forbidden:
        if token in source:
            failures.append(f"R6 source contains protected host surface: {token}")

    if "execute_r7: bool = False" not in source:
        failures.append("R6 execution interlock is not explicit")
    if '"manual_task_start": "NOT_RUN"' not in source:
        failures.append("R6 source does not freeze manual task start closed")
    if "LEASE_PUBLICATION_STEPS" not in source:
        failures.append("R6 source does not bind tmp/installing/final publication")

    return tuple(failures)


# Canonical AST pins freeze the complete reviewed incident policy, native helper,
# accepted observation chain, and runner composition. Formatting is not authority.
R8_HALT_SOURCE_PINS: Final = {
    "scripts/d10_arch128_r8_terminal_halt.py": (
        "45c7e7fab0e48ea74995211e59758b6f27ea974b785e62ab5c2510be43c851cf"
    ),
    "scripts/d10_arch128_r8_halt_windows.py": (
        "c85efb5913c986384608234c282191831d3f254784db225733465aeb1dfc98ff"
    ),
    "scripts/d10_arch128_r8_halt_diagnostic.py": (
        "6369c8fcfd719171538b34d4d0842735e863cfb5609c8de180569c2a28ef29e5"
    ),
    "scripts/d10_arch128_r8_terminal_halt_diagnose.ps1": (
        "c07c054b01fc1bb0e2b4a720e3b82ff85c2c100432f66854ab7e132ddc9a37ce"
    ),
    "scripts/d10_arch128_r8_terminal_halt.ps1": (
        "0a6001494e265e79d443d6aaa1506a9791bd97c30c775e99d050056b512eb9a5"
    ),
    "scripts/d10_arch128_r8_readonly.py": (
        "59762e5d7dbd748f9525b51ea67b5bcdf1d1b1f4ec177992fed3ac5a0e29bdfc"
    ),
    "scripts/d10_durable_wake_evidence_observe.py": (
        "db64b72f9daaf74c0ff73d52378d407a29fbc8aeabcb30b5e7d4b47f5994ddb3"
    ),
    "scripts/run_personal_desktop_d10_launch_guard.py": (
        "a2bd8eea6dcd5e4df78a6ce94f070ef3bbafc243d1c27d79fbeb93f3a30cd1f6"
    ),
    "scripts/d10_arch128_r3_scheduler_observe.ps1": (
        "e688aab821028cedfca4a6fc6ebff2af847e645f25f8442f5c2ba772c3413505"
    ),
    "scripts/d10_p1245_scheduler_observe.ps1": (
        "a1bc4ef906806014bf15bed1e02c69742870f9977e99621bef14619c00b6058e"
    ),
    "scripts/d10_arch128_r6_reactivation.py": (
        "369b0feec8421e6a3470171fdf1285cf4c6d22b5c99308c7b427b505b919dea9"
    ),
    "scripts/d10_arch128_r7_observation.py": (
        "84238e6f11cc8fb82b5f0c73eee0dfcc63a3f7bc14b24e42038304ce0533f978"
    ),
    "scripts/d10_arch128_r4_replacement.py": (
        "2ec31172f0daeef152b8e4b6cf03ee3674d82ea5f07208eda32de3a58ecad54f"
    ),
    (
        "src/trading_bot/runtime/"
        "personal_desktop_unattended_one_week_soak_scheduler_contract.py"
    ): ("64a6cc2e44e98e7f301a64ae6777f57f7ca19339419ce6b8d90820e9dd4addf2"),
    "src/trading_bot/runtime/personal_desktop_d10_activation_lease.py": (
        "ff2885d6ee5cfd3998cb8c1ece5462c48a70ce704ab335fb71f3f3173c8d4e54"
    ),
}
R8_HALT_RUNNER_PINS: Final = {
    "_r8_halt_authority_check": (
        "d0e00ab3d3596828592c94483c9a114588f81bf40daa00fca29208d31b5a0ff1"
    ),
    "_r8_halt_preflight": (
        "3a7244189088f41c17e001a7aad8c60c4c85bf5a9cbbab497a3a2f194019ec53"
    ),
    "_r8_halt_execute": (
        "f0a9c6388f63b1184426f6b7072213e3e7af4bb16f27435d81f98ad0566c97ef"
    ),
    "execute_checkpoint": (
        "031c22f037b6704ca50d68fc4445330edc0e38f1cd575f85e8dd9b3d81250eda"
    ),
    "preflight_checkpoint": (
        "686c25f4de2d3c01cbb146efc181c6ca295de766b19d8436bd427431cbc930ca"
    ),
    "_remote_branch_head": (
        "46ea1a2afa1e52622b257c9d635bb115529ae99b1c09aa6bb18ede99a5c2d27e"
    ),
    "_git_state": ("c63292862490a972afd8c7ffafe01dcdd90dc19d5973eca83be876ebd611c113"),
    "_write_json": ("bd3cabc882528e471e226c434eb3657c3f461b520112f60782eb0bda4b3d5f82"),
}
R8_HALT_REGISTRATION_PIN: Final = (
    "d610b7fc74b3c670d83188641d7f0e00425c1c83e052d32b08cf76b87bf1b991"
)

ARCH130_R8I_D1_SOURCE_BLOB_SHA1: Final = "4dece99d8993934e9747f091415927353b70a2e3"
ARCH130_R8I_D1_REMOTE_BRANCH: Final = "feature/d10c-r8-incident-reconciliation"
ARCH131_REVIEW_PAPER_REMOTE_BRANCH: Final = "feature/robinhood-review-paper-mode"
ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH: Final = (
    "feature/robinhood-review-paper-side-foundation"
)
ARCH131_LQ_SOURCE_BLOB_SHA1: Final = "3283793abed5320d778d28d72e49eeabed98ccf1"


def _arch131_windows_oauth_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/robinhood_mcp/windows_oauth.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = {
            node.target.id: node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        expected = {
            "TOKEN_TARGET": "AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1",
            "CLIENT_INFO_TARGET": (
                "AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1"
            ),
            "CRED_TYPE_GENERIC": 1,
            "CRED_PERSIST_LOCAL_MACHINE": 2,
            "CRED_MAX_CREDENTIAL_BLOB_SIZE": 2560,
            "LOOPBACK_HOST": "127.0.0.1",
        }
        for name, value in expected.items():
            if name not in constants or ast.literal_eval(constants[name]) != value:
                failures.append(f"131-F frozen constant drift: {name}")

        names = _qualified_names(tree)
        required = {
            "self._api.CredReadW",
            "self._api.CredWriteW",
            "self._api.CredFree",
            "WindowsCredentialApi",
            "WindowsOAuthStorage",
            "_require_target",
            "asyncio.start_server",
            "create_robinhood_oauth_factory",
        }
        if required - names:
            failures.append("131-F Windows storage/composition boundary is missing")
        forbidden_tools = {
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        }
        strings = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        identifiers = {name.rsplit(".", 1)[-1] for name in names}
        identifiers.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        if forbidden_tools & (strings | identifiers):
            failures.append("131-F exposes a forbidden Robinhood tool")
        forbidden = {
            "CredEnumerateW",
            "CredEnumerateA",
            "environ",
            "getenv",
            "Path",
            "write_text",
            "write_bytes",
            "read_text",
            "read_bytes",
            "load_dotenv",
            "call_tool",
            "socket",
            "bind",
            "listen",
        }
        unsafe_open = any(
            name == "open" or name.endswith(".open") and name != "webbrowser.open"
            for name in names
        )
        if forbidden & (identifiers | strings) or unsafe_open:
            failures.append("131-F enumeration/fallback/unreviewed effect boundary")
        allowed_imports = {
            "__future__",
            "asyncio",
            "ctypes",
            "ctypes.wintypes",
            "math",
            "os",
            "re",
            "threading",
            "webbrowser",
            "collections.abc",
            "typing",
            "urllib.parse",
            "mcp.shared.auth",
            "trading_bot.robinhood_mcp.sdk_transport",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name not in allowed_imports for alias in node.names):
                    failures.append("131-F unreviewed persistence/effect import")
            elif (
                isinstance(node, ast.ImportFrom) and node.module not in allowed_imports
            ):
                failures.append("131-F unreviewed persistence/effect import")
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "os" and node.attr != "name":
                    failures.append("131-F unreviewed OS boundary")
        listeners = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "start_server"
        ]
        if len(listeners) != 1:
            failures.append("131-F exact loopback listener is missing")
        else:
            keywords = {item.arg: item.value for item in listeners[0].keywords}
            host = keywords.get("host")
            port = keywords.get("port")
            if not (
                isinstance(host, ast.Name)
                and host.id == "LOOPBACK_HOST"
                and isinstance(port, ast.Attribute)
                and port.attr == "_port"
                and isinstance(port.value, ast.Name)
                and port.value.id == "self"
            ):
                failures.append("131-F loopback bind drift")
        native = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "WindowsCredentialApi"
        )
        for method_name, operation in (
            ("read_generic", "CredReadW"),
            ("write_generic", "CredWriteW"),
        ):
            method = next(
                node
                for node in native.body
                if isinstance(node, ast.FunctionDef) and node.name == method_name
            )
            method_names = _qualified_names(method)
            if "_require_target" not in method_names:
                failures.append("131-F exact target guard missing")
            if "CRED_TYPE_GENERIC" not in method_names:
                failures.append(f"131-F generic credential type missing: {operation}")
        guard = _top_level_functions(tree).get("_require_target")
        if guard is None or not any(
            isinstance(node, ast.Set)
            and {item.id for item in node.elts if isinstance(item, ast.Name)}
            == {"TOKEN_TARGET", "CLIENT_INFO_TARGET"}
            and len(node.elts) == 2
            for node in ast.walk(guard)
        ):
            failures.append("131-F exact target set drift")
        calls = [node for node in ast.walk(native) if isinstance(node, ast.Call)]
        for call in calls:
            if isinstance(call.func, ast.Attribute) and call.func.attr == "CredReadW":
                if not (
                    len(call.args) == 4
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == "target"
                    and isinstance(call.args[1], ast.Name)
                    and call.args[1].id == "CRED_TYPE_GENERIC"
                ):
                    failures.append("131-F exact generic read call drift")
            if isinstance(call.func, ast.Attribute) and call.func.attr == "_credential":
                fields = {item.arg: item.value for item in call.keywords}
                for field, constant in (
                    ("Type", "CRED_TYPE_GENERIC"),
                    ("Persist", "CRED_PERSIST_LOCAL_MACHINE"),
                    ("TargetName", "target"),
                ):
                    value = fields.get(field)
                    if not isinstance(value, ast.Name) or value.id != constant:
                        failures.append("131-F generic write record drift")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == "arch131-robinhood-oauth-windows"
                for item in node.keywords
            )
        ]
        if len(registrations) != 1:
            failures.append("131-F source-only registration missing")
        else:
            for item in registrations[0].keywords:
                if item.arg in {"preflight", "execute"} and not (
                    isinstance(item.value, ast.Constant) and item.value.value is None
                ):
                    failures.append("131-F checkpoint has host/effect capability")
        spec = _checkpoint_specs()["arch131-robinhood-oauth-windows"]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-F checkpoint has host/effect capability")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        StopIteration,
    ):
        failures.append("131-F source or structural boundary unavailable")
    return tuple(failures)


def _arch131_forward_paper_cycle_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (repo_root / "src/trading_bot/robinhood_forward_paper_cycle.py").read_text(
                encoding="utf-8"
            )
        )
        # Pin the entire narrow binder: closed imports and signature, one exact
        # 131-K call followed by one exact 131-J call, sole store identity,
        # unchanged explicit arguments/context/result, and no alternate effects.
        # Helpers, decorators, extra calls, loops, retries, UUID generation,
        # risk/operator/MCP/OAuth/config/host/performance access all drift.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "2528528ce13770c5aefe3481f3527d856c9d3ea19ffb3ab994de9b2b5fcb736a"
        ):
            failures.append("131-L sole-account/context/pipeline/effect boundary drift")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-forward-paper-cycle"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        # Pin source-only flags, authority, remote, and test/lint coverage.
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "15be2da1498de847845d155f0f0b5e65544fa6c307b9a5a3727a59250f976e07"
        ):
            failures.append("131-L source-only checkpoint registration drift")
        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-L checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-L workflow invocation/131-K ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-L source or structural boundary unavailable")
    return tuple(failures)


def _arch133_host_scheduler_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_host_identity.py": (
                "cb8b624c70f0792f8eba0336cf6e372d3b78f612"
            ),
            "src/trading_bot/review_paper/unattended_scheduler.py": (
                "153395ce66ff11f7d0978541cbf9193ae4df3f30"
            ),
            "src/trading_bot/review_paper/unattended_host.py": (
                "eb41d518af9ead0e4260b081af63d48b11560023"
            ),
            "scripts/run_arch133_unattended_review_paper.py": (
                "661023c46a3e088d338b67282effb7f35b00a93d"
            ),
        }
        for relative, expected in pins.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-E closed composition boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-host-scheduler-surface"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "9b526e5cca493208ec999ce427c09df0d731b039a897382f1b085d07f7481cbb"
        ):
            failures.append("133-E source-only registration drift")
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-E batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133e"
            or spec.authority_check is not _arch133_host_scheduler_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-E source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch133-robinhood-unattended-review-paper-execution"
            )
            + 1
        ):
            failures.append("133-E checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-E workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-E source or structural boundary unavailable")
    return tuple(failures)


ARCH133_RETAINED_SOURCES: Final = (
    "src/trading_bot/arch133_acl/__init__.py",
    "src/trading_bot/arch133_acl/read_only.py",
    "src/trading_bot/arch133_acl/retained_reads.py",
    "src/trading_bot/arch133_acl/retained_diagnostic.py",
    "scripts/run_arch133_retained_root_diagnostic.py",
)
ARCH133_RETAINED_PINS: Final = {
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/retained_reads.py": (
        "98fdab5017615be21bd95ec3f0ca25f792018f6325e20d11736df8842e47cbbb"
    ),
    "src/trading_bot/arch133_acl/retained_diagnostic.py": (
        "0ee93781d97db0b4377bbb0f724cf87d4329b05d18467d4687e965ee7eb72da6"
    ),
    "scripts/run_arch133_retained_root_diagnostic.py": (
        "cd35722017eca8560ccf0ca22a6be632e5581705db09441150d296ea87f2d0e9"
    ),
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
}
ARCH133_RETAINED_REGISTRATION_PIN: Final = (
    "f800d31cde47819f296db53593130d21b122139ca95383444f0debb7dd858246"
)


ARCH133_RECOVERY_SOURCES: Final = (
    "src/trading_bot/arch133_acl/__init__.py",
    "src/trading_bot/arch133_acl/read_only.py",
    "src/trading_bot/arch133_acl/retained_reads.py",
    "src/trading_bot/arch133_acl/root_policy_apply.py",
    "src/trading_bot/arch133_acl/administrator.py",
    "src/trading_bot/arch133_acl/recovery.py",
    "scripts/run_arch133_retained_root_acl_recovery.py",
)
ARCH133_RECOVERY_PINS: Final = {
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/retained_reads.py": (
        "98fdab5017615be21bd95ec3f0ca25f792018f6325e20d11736df8842e47cbbb"
    ),
    "src/trading_bot/arch133_acl/root_policy_apply.py": (
        "d3777322118c9fb1353102fd083251c4b59ac9ee552572818a87546a0cf41dde"
    ),
    "src/trading_bot/arch133_acl/administrator.py": (
        "286d4ab228fdad27b719a0673a19583bfe3cc667dcec958fa34bad30e8742611"
    ),
    "src/trading_bot/arch133_acl/recovery.py": (
        "7a7c8c058229665c89c7a3a8e736eb2d7cd141feee00812a27c03f8c391e4386"
    ),
    "scripts/run_arch133_retained_root_acl_recovery.py": (
        "524e622ae9653ed2c6f30fd056b97974c96aff04e485722ce8879e3ce58af75b"
    ),
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
}
ARCH133_RECOVERY_REGISTRATION_PIN: Final = (
    "825e732a03cf568a9b4be81e9ecd6d2b0707028a1fe7a2cb27f226888477d66c"
)


ARCH133_VERIFIER_MODULES: Final = (
    "trading_bot",
    "trading_bot.config",
    "trading_bot.arch133_acl",
    "trading_bot.arch133_acl.read_only",
    "trading_bot.arch133_acl.retained_reads",
    "trading_bot.arch133_verifier",
    "trading_bot.arch133_verifier.activation",
    "trading_bot.arch133_verifier.binding",
    "trading_bot.arch133_verifier.credentials",
    "trading_bot.arch133_verifier.file_policy",
    "trading_bot.arch133_verifier.operator",
    "trading_bot.arch133_verifier.scheduler",
    "trading_bot.arch133_verifier.sessions",
    "trading_bot.arch133_verifier.state",
    "trading_bot.arch133_verifier.state_schema",
    "trading_bot.arch133_verifier.token",
    "trading_bot.domain",
    "trading_bot.domain._validation",
    "trading_bot.domain.enums",
    "trading_bot.domain.market",
    "trading_bot.domain.orders",
    "trading_bot.domain.positions",
    "trading_bot.domain.proposals",
)
ARCH133_VERIFIER_PINS: Final = {
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/retained_reads.py": (
        "98fdab5017615be21bd95ec3f0ca25f792018f6325e20d11736df8842e47cbbb"
    ),
    "src/trading_bot/arch133_verifier/__init__.py": (
        "ece882f6a0f8605cae553bd80be524421a98f25c3d6fd2276c44558612cfc980"
    ),
    "src/trading_bot/arch133_verifier/activation.py": (
        "3e842e244576abcc5d560e942cd355c598ce42df5c2ffea71e120d1e254482b5"
    ),
    "src/trading_bot/arch133_verifier/binding.py": (
        "f24ee022779619e3a19915835ac3fd766135b1fba4f90f94a9e8b65764835262"
    ),
    "src/trading_bot/arch133_verifier/credentials.py": (
        "6896de10afc779a847a63640ffcf6fd5e9e634ba4199159599038e644de5c213"
    ),
    "src/trading_bot/arch133_verifier/file_policy.py": (
        "628d121da26a0474fc98e7f7556ce8d3dbc8c189d04a7ecc6b4ec47eb7bd6a08"
    ),
    "src/trading_bot/arch133_verifier/operator.py": (
        "a574acf2fa95e7623e8e8530728f33a82e9c273dec1006ce20c809eb54860572"
    ),
    "src/trading_bot/arch133_verifier/scheduler.py": (
        "327d092c852e762719e0c1d27eb9be0d1c470b6ffa5b7dd7a113352c1cf4946a"
    ),
    "src/trading_bot/arch133_verifier/sessions.py": (
        "278c43c61461c7163e8a641b27aaea8e2b9a6782b77ad805144c7137aa75b503"
    ),
    "src/trading_bot/arch133_verifier/state.py": (
        "0753b532ef58cc7699863e3114e1e3dd2caaa0e1aab7b48b2d546a7f8142d5e4"
    ),
    "src/trading_bot/arch133_verifier/state_schema.py": (
        "902525afadbaabd0afc997b7702de06b5160a7df61f8f97e6d38ec351b74c7d3"
    ),
    "src/trading_bot/arch133_verifier/token.py": (
        "b93236774ee2509947024786fd54ed6a9e702e8d68ef10a8a0ad6376706c5cb6"
    ),
    "src/trading_bot/domain/__init__.py": (
        "5d0baf9be17341641d07504176366c5041be9d73e17230377b8167e012f082ee"
    ),
    "src/trading_bot/domain/_validation.py": (
        "b94d183b2dceff5c844bf3584fabf4a21b4a58cabb0b3088e78099c0dbd7c101"
    ),
    "src/trading_bot/domain/enums.py": (
        "c47b5894f80cb271573e0be4869dde81a4b2a0cf9dc97019864f19f96712cd39"
    ),
    "src/trading_bot/domain/market.py": (
        "eb82f9727ce3fd83f41b96411f49b77e34ff5f75d39372bdb97ce94a3efc7040"
    ),
    "src/trading_bot/domain/orders.py": (
        "3f21c1f9ad197b187ac6a4588ef470ef7266a3b30e026df6288b7b2337a0070a"
    ),
    "src/trading_bot/domain/positions.py": (
        "e9a8d7615a6bd86ed206196d03ced50ae8aee273f632a56bece4427b212c68a9"
    ),
    "src/trading_bot/domain/proposals.py": (
        "eb47d71dcfab0ce64ff03a0d5b8a4091e6dca6d7a53c134f6f842ea40672d738"
    ),
    "scripts/run_arch133_post_publication_verifier.py": (
        "3503070f151862f9f11f3994003390ece6fbdf4205afd602975c8607f95c00e3"
    ),
}
ARCH133_VERIFIER_SOURCES: Final = tuple(ARCH133_VERIFIER_PINS)
ARCH133_VERIFIER_REGISTRATION_PIN: Final = (
    "478391462b59486e3a5432ec859eb8ec0bd867dbf8634c84df57e0043c7e4bb2"
)


ARCH133_DIAGNOSTIC_MODULES: Final = tuple(
    module
    for module in ARCH133_VERIFIER_MODULES
    if module
    not in {
        "trading_bot.arch133_verifier.credentials",
        "trading_bot.arch133_verifier.operator",
    }
) + ("trading_bot.arch133_diagnostic", "trading_bot.arch133_diagnostic.operator")
ARCH133_DIAGNOSTIC_PINS: Final = {
    path: digest
    for path, digest in ARCH133_VERIFIER_PINS.items()
    if path
    not in {
        "src/trading_bot/arch133_verifier/credentials.py",
        "src/trading_bot/arch133_verifier/operator.py",
        "scripts/run_arch133_post_publication_verifier.py",
    }
} | {
    "src/trading_bot/arch133_diagnostic/__init__.py": (
        "39dc89385e9450efec209706797f62de72d0e5a424dabf5edec0c2b1134dfb3e"
    ),
    "src/trading_bot/arch133_diagnostic/operator.py": (
        "61adcee90d2691bcaabaa85cf0329e8093e3570dd361d67f86532eff6613a78c"
    ),
    "scripts/run_arch133_post_publication_stage_diagnostic.py": (
        "6d8a6b54df85320eedb84bb1f6a15d218ab6f6260ab2dce620a2ec9f44aadce3"
    ),
}
ARCH133_DIAGNOSTIC_SOURCES: Final = tuple(ARCH133_DIAGNOSTIC_PINS)
ARCH133_DIAGNOSTIC_REGISTRATION_PIN: Final = (
    "3d91876e57fb5bfe7f2ce7ffb62040fe9f0953e9a5b33337692d2b1c4fe9653f"
)


ARCH133_PUBLICATION_DIAGNOSTIC_MODULES: Final = tuple(
    module
    for module in ARCH133_DIAGNOSTIC_MODULES
    if module
    not in {
        "trading_bot.arch133_verifier.scheduler",
        "trading_bot.arch133_verifier.sessions",
        "trading_bot.arch133_diagnostic",
        "trading_bot.arch133_diagnostic.operator",
    }
) + (
    "trading_bot.arch133_publication_diagnostic",
    "trading_bot.arch133_publication_diagnostic.operator",
)
ARCH133_PUBLICATION_DIAGNOSTIC_PINS: Final = {
    path: digest
    for path, digest in ARCH133_DIAGNOSTIC_PINS.items()
    if path
    not in {
        "src/trading_bot/arch133_verifier/scheduler.py",
        "src/trading_bot/arch133_verifier/sessions.py",
        "src/trading_bot/arch133_diagnostic/__init__.py",
        "src/trading_bot/arch133_diagnostic/operator.py",
        "scripts/run_arch133_post_publication_stage_diagnostic.py",
    }
} | {
    "src/trading_bot/arch133_publication_diagnostic/__init__.py": (
        "be2ef19da93cb7ea14b040db8fb7c97572ee7218f75699350f420570d0d4b692"
    ),
    "src/trading_bot/arch133_publication_diagnostic/operator.py": (
        "5eb8825eb4dc4aeb4d691efea5bb0fc7e50af4efbdac07e505c3c33d99331fb6"
    ),
    "scripts/run_arch133_publication_state_paper_diagnostic.py": (
        "8611b042fea0b8c925746593a30c2799652597c9be9b9ff9736b22ba029971e6"
    ),
}
ARCH133_PUBLICATION_DIAGNOSTIC_SOURCES: Final = tuple(
    ARCH133_PUBLICATION_DIAGNOSTIC_PINS
)
ARCH133_PUBLICATION_DIAGNOSTIC_REGISTRATION_PIN: Final = (
    "03f1c492c51dd6ca6e74f12bd6fb0fdf6f43464b8d815304b1aee98dd3e83c98"
)


ARCH133_PUBLICATION_CORRECTED_MODULES: Final = tuple(
    module
    for module in ARCH133_PUBLICATION_DIAGNOSTIC_MODULES
    if not module.startswith("trading_bot.arch133_publication_diagnostic")
) + (
    "trading_bot.arch133_publication_state_paper_corrected",
    "trading_bot.arch133_publication_state_paper_corrected.operator",
)
ARCH133_PUBLICATION_CORRECTED_PINS: Final = {
    path: digest
    for path, digest in ARCH133_PUBLICATION_DIAGNOSTIC_PINS.items()
    if "/arch133_publication_diagnostic/" not in path
    and path != "scripts/run_arch133_publication_state_paper_diagnostic.py"
} | {
    "src/trading_bot/arch133_publication_state_paper_corrected/__init__.py": (
        "819ac91ea5e47f258100c45c10f1c92f9624bfd23c9a04e608eebd1620a2ea5e"
    ),
    "src/trading_bot/arch133_publication_state_paper_corrected/operator.py": (
        "57743791949781089e2aa7f83d9b36d9a2aa10efcaba161cb941b84dbf055484"
    ),
    "scripts/run_arch133_publication_state_paper_corrected.py": (
        "353dea7dff0d0a2bffd85841e1c87bd8bd63aa4f2f7fe9ac2e9c0ac16bce75e4"
    ),
}
ARCH133_PUBLICATION_CORRECTED_SOURCES: Final = tuple(ARCH133_PUBLICATION_CORRECTED_PINS)
ARCH133_PUBLICATION_CORRECTED_REGISTRATION_PIN: Final = (
    "1e19a84ed6ae2a4be90b2245bee1ad38b7beceb1b4613b94c1201252472e6d5d"
)


ARCH133_SCHEDULER_MODULES: Final = (
    "trading_bot",
    "trading_bot.arch133_acl",
    "trading_bot.arch133_acl.read_only",
    "trading_bot.arch133_acl.retained_reads",
    "trading_bot.arch133_scheduler_installation",
    "trading_bot.arch133_scheduler_installation.admission",
    "trading_bot.arch133_scheduler_installation.operator",
    "trading_bot.arch133_scheduler_installation.specification",
    "trading_bot.arch133_verifier",
    "trading_bot.arch133_verifier.activation",
    "trading_bot.arch133_verifier.binding",
    "trading_bot.arch133_verifier.file_policy",
    "trading_bot.arch133_verifier.scheduler",
    "trading_bot.arch133_verifier.sessions",
    "trading_bot.arch133_verifier.state",
    "trading_bot.arch133_verifier.state_schema",
    "trading_bot.arch133_verifier.token",
    "trading_bot.config",
    "trading_bot.domain",
    "trading_bot.domain._validation",
    "trading_bot.domain.enums",
    "trading_bot.domain.market",
    "trading_bot.domain.orders",
    "trading_bot.domain.positions",
    "trading_bot.domain.proposals",
)
ARCH133_SCHEDULER_PINS: Final = {
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/retained_reads.py": (
        "98fdab5017615be21bd95ec3f0ca25f792018f6325e20d11736df8842e47cbbb"
    ),
    "src/trading_bot/arch133_scheduler_installation/__init__.py": (
        "67726876bbccbf569d95cc6e9c7dca42ca5d3cc50601cbbfd2f848bf98e08d21"
    ),
    "src/trading_bot/arch133_scheduler_installation/admission.py": (
        "2c426ea952ee109f26481003e53670f36054b09781385aec078bb60746ff931b"
    ),
    "src/trading_bot/arch133_scheduler_installation/operator.py": (
        "b6db26e036e52d688257e27723509c6e541f462a789c2044d0b6d01f80fcd27c"
    ),
    "src/trading_bot/arch133_scheduler_installation/specification.py": (
        "bdd841b4d2acfd7dec09cb9c7df16f14082602fd63f59e0351dac505cbd6d985"
    ),
    "src/trading_bot/arch133_verifier/__init__.py": (
        "ece882f6a0f8605cae553bd80be524421a98f25c3d6fd2276c44558612cfc980"
    ),
    "src/trading_bot/arch133_verifier/activation.py": (
        "3e842e244576abcc5d560e942cd355c598ce42df5c2ffea71e120d1e254482b5"
    ),
    "src/trading_bot/arch133_verifier/binding.py": (
        "f24ee022779619e3a19915835ac3fd766135b1fba4f90f94a9e8b65764835262"
    ),
    "src/trading_bot/arch133_verifier/file_policy.py": (
        "628d121da26a0474fc98e7f7556ce8d3dbc8c189d04a7ecc6b4ec47eb7bd6a08"
    ),
    "src/trading_bot/arch133_verifier/scheduler.py": (
        "327d092c852e762719e0c1d27eb9be0d1c470b6ffa5b7dd7a113352c1cf4946a"
    ),
    "src/trading_bot/arch133_verifier/sessions.py": (
        "278c43c61461c7163e8a641b27aaea8e2b9a6782b77ad805144c7137aa75b503"
    ),
    "src/trading_bot/arch133_verifier/state.py": (
        "0753b532ef58cc7699863e3114e1e3dd2caaa0e1aab7b48b2d546a7f8142d5e4"
    ),
    "src/trading_bot/arch133_verifier/state_schema.py": (
        "902525afadbaabd0afc997b7702de06b5160a7df61f8f97e6d38ec351b74c7d3"
    ),
    "src/trading_bot/arch133_verifier/token.py": (
        "b93236774ee2509947024786fd54ed6a9e702e8d68ef10a8a0ad6376706c5cb6"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
    "src/trading_bot/domain/__init__.py": (
        "5d0baf9be17341641d07504176366c5041be9d73e17230377b8167e012f082ee"
    ),
    "src/trading_bot/domain/_validation.py": (
        "b94d183b2dceff5c844bf3584fabf4a21b4a58cabb0b3088e78099c0dbd7c101"
    ),
    "src/trading_bot/domain/enums.py": (
        "c47b5894f80cb271573e0be4869dde81a4b2a0cf9dc97019864f19f96712cd39"
    ),
    "src/trading_bot/domain/market.py": (
        "eb82f9727ce3fd83f41b96411f49b77e34ff5f75d39372bdb97ce94a3efc7040"
    ),
    "src/trading_bot/domain/orders.py": (
        "3f21c1f9ad197b187ac6a4588ef470ef7266a3b30e026df6288b7b2337a0070a"
    ),
    "src/trading_bot/domain/positions.py": (
        "e9a8d7615a6bd86ed206196d03ced50ae8aee273f632a56bece4427b212c68a9"
    ),
    "src/trading_bot/domain/proposals.py": (
        "eb47d71dcfab0ce64ff03a0d5b8a4091e6dca6d7a53c134f6f842ea40672d738"
    ),
    "scripts/run_arch133_scheduler_installation.py": (
        "64f50e19cf72a234ae8cd76c01704fdea9a9d2ed10728545e30d72d62544800a"
    ),
    "scripts/arch133_scheduler_definition.ps1": (
        "e705dbd03ad10bbcd619538156d6f88c961fb074d35c9f7956b4fb04efa8e88e"
    ),
    "scripts/arch133_scheduler_observe.ps1": (
        "45e1c9dbf62738ff2667969ed3716b39313c1977ee7693572a17c078616c0a2a"
    ),
    "scripts/arch133_scheduler_install.ps1": (
        "9764b40dc6953b3fda2028e35f6e68a39d71c8b052dde9710fe60ce9bd4eaa8f"
    ),
    "src/trading_bot/review_paper/unattended_scheduler.py": (
        "79fe37f5e4c36c70096f86414f5e32151556c617b82bc086742a44470c7dde29"
    ),
}
ARCH133_SCHEDULER_SOURCES: Final = tuple(ARCH133_SCHEDULER_PINS)
ARCH133_SCHEDULER_REGISTRATION_PIN: Final = (
    "e6f119c53e5ecc7ea2d56fba3b0da9d661823f553b80bb64a5913877cb57206a"
)


ARCH133_REPROVISION_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision/__init__.py",
    "src/trading_bot/arch133_reprovision/predecessor.py",
    "src/trading_bot/arch133_reprovision/reads.py",
    "src/trading_bot/arch133_reprovision/material.py",
    "src/trading_bot/arch133_reprovision/generation.py",
    "src/trading_bot/arch133_reprovision/namespace.py",
    "src/trading_bot/arch133_reprovision/native.py",
    "src/trading_bot/arch133_reprovision/operator.py",
    "scripts/run_arch133_fresh_activation_reprovision.py",
)
ARCH133_REPROVISION_PINS: Final = {
    "src/trading_bot/arch133_reprovision/__init__.py": (
        "4a6c81929bd649707d26db3b7751e76c3fe6977be98fece1be65b6daae95fbfa"
    ),
    "src/trading_bot/arch133_reprovision/predecessor.py": (
        "22fa7166311b669314aabf76499ada463dd40290a23de8694e2f4668f4f9f59a"
    ),
    "src/trading_bot/arch133_reprovision/reads.py": (
        "48b42cb5d9fac1b88b5a532e4f4ad4e180556d222bc8da21c78be2ef3068bad7"
    ),
    "src/trading_bot/arch133_reprovision/material.py": (
        "fd6c2c3dd321e0b47cf0d344636a5b2ec4f2aec7feb981c0426b672eb19c0212"
    ),
    "src/trading_bot/arch133_reprovision/generation.py": (
        "8936195c3692f7654a5c692715ce9511a238a91019e06b67ca7c42ed5e47bfbe"
    ),
    "src/trading_bot/arch133_reprovision/namespace.py": (
        "b4afbba5d22e2874df2e3345f89c0764103b86ffb3729cc7a6e59380996e38d7"
    ),
    "src/trading_bot/arch133_reprovision/native.py": (
        "de93039a5a04053a51da6dd88e83aed121ca6debb4bcbbaa7e2f5b7246bf3bc8"
    ),
    "src/trading_bot/arch133_reprovision/operator.py": (
        "aa9eedd322bef79f61241864e954f281aefd6f9ea484b9907dca399a32c8a6a0"
    ),
    "scripts/run_arch133_fresh_activation_reprovision.py": (
        "d1824adb159ff11a171040ebab43c380ad27de13d897bff9cbe457c19f4d99df"
    ),
}
ARCH133_REPROVISION_REGISTRATION_PIN: Final = (
    "54882c9d46d181d465e03fdff642317c4af373c6bda759685c6dff745404df1b"
)


ARCH133U_REPROVISION_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_corrected/__init__.py",
    "src/trading_bot/arch133_reprovision_corrected/admission.py",
    "src/trading_bot/arch133_reprovision_corrected/operator.py",
    "scripts/run_arch133_fresh_activation_reprovision_corrected.py",
)
ARCH133U_REPROVISION_PINS: Final = {
    "src/trading_bot/arch133_reprovision_corrected/__init__.py": (
        "cc04b3a697950ac1d02ea39c1f57e5c2747430a2a0b9bbbd1f753d2ea4bba8f8"
    ),
    "src/trading_bot/arch133_reprovision_corrected/admission.py": (
        "62935b26f9cd2624ed89059987eeb38996d1c3288d2744640e0c84947531f349"
    ),
    "src/trading_bot/arch133_reprovision_corrected/operator.py": (
        "7d439154bd4c7713ee3a9c366f3c7c6db47438785f1796168c512b9fadbc665b"
    ),
    "scripts/run_arch133_fresh_activation_reprovision_corrected.py": (
        "03d61973408c4039e119ea4d06670c728cde411df05427cda9824127b90f8086"
    ),
}
ARCH133U_REPROVISION_REGISTRATION_PIN: Final = (
    "f8e25032969974459fd99e589831daaf8d30e0150656dd06c30f28a198297a60"
)


ARCH133_REPROVISION_DIAGNOSTIC_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_diagnostic/__init__.py",
    "src/trading_bot/arch133_reprovision_diagnostic/operator.py",
    "scripts/run_arch133_reprovision_admission_diagnostic.py",
)
ARCH133_REPROVISION_DIAGNOSTIC_PINS: Final = {
    "src/trading_bot/arch133_reprovision_diagnostic/__init__.py": (
        "a161e6533bcdc3bb7c9caa29cc27422fc2120b2d"
    ),
    "src/trading_bot/arch133_reprovision_diagnostic/operator.py": (
        "4699aac0761df76c2c9ed67f7c4810c98dabb8b0"
    ),
    "scripts/run_arch133_reprovision_admission_diagnostic.py": (
        "6479389ccbfc3da4401e38b338f979376a5f418f"
    ),
}


ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES: Final = (
    "src/trading_bot/arch133_parent_security_diagnostic/__init__.py",
    "src/trading_bot/arch133_parent_security_diagnostic/admission.py",
    "src/trading_bot/arch133_parent_security_diagnostic/operator.py",
    "scripts/run_arch133_parent_security_diagnostic.py",
)
ARCH133_PARENT_SECURITY_DIAGNOSTIC_PINS: Final = {
    "src/trading_bot/arch133_parent_security_diagnostic/__init__.py": (
        "c59623e697cd19f3fd9c6cc0d9b0774dfcc22bdd"
    ),
    "src/trading_bot/arch133_parent_security_diagnostic/admission.py": (
        "2b6039da799db0a4f15a883782858bfc87f1a492"
    ),
    "src/trading_bot/arch133_parent_security_diagnostic/operator.py": (
        "1659266adf9e1f82d338fba601810e6edd491dec"
    ),
    "scripts/run_arch133_parent_security_diagnostic.py": (
        "5e0c64b9fe4b627110deba75f5572cca0a7e1afc"
    ),
}
ARCH133_PARENT_SECURITY_DIAGNOSTIC_REGISTRATION_PIN: Final = (
    "f78ba2bfee91356acbc077cdddd1a52102a0d45a5a49058836ae1195390493e4"
)


def _arch133_parent_security_diagnostic_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the separate 133-S read-only surface and retained predecessor chain."""
    failures = list(_arch133_reprovision_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_PARENT_SECURITY_DIAGNOSTIC_PINS.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-S diagnostic source drift: {relative}")
        if (
            tuple(ARCH133_PARENT_SECURITY_DIAGNOSTIC_PINS)
            != ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES
        ):
            failures.append("133-S diagnostic inventory drift")
        name = "arch133-robinhood-reprovision-parent-security-diagnostic"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(inventories) != 1
            or ast.literal_eval(inventories[0]) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-S diagnostic active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_PARENT_SECURITY_DIAGNOSTIC_REGISTRATION_PIN
        ):
            failures.append("133-S diagnostic source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_parent_security_diagnostic_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133s"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-S diagnostic registration drift")
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 1
            ]
            != (
                "arch133-robinhood-reprovision-admission-diagnostic",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-S diagnostic ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-S diagnostic workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-S diagnostic boundary unavailable")
    return tuple(failures)


ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES: Final = (
    "src/trading_bot/arch133_parent_policy_diagnostic/__init__.py",
    "src/trading_bot/arch133_parent_policy_diagnostic/admission.py",
    "src/trading_bot/arch133_parent_policy_diagnostic/operator.py",
    "scripts/run_arch133_parent_policy_diagnostic.py",
)
ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS: Final = {
    "src/trading_bot/arch133_parent_policy_diagnostic/__init__.py": (
        "37a59becbfb288ed9ba61d2d30ee9ad4548acb1a"
    ),
    "src/trading_bot/arch133_parent_policy_diagnostic/admission.py": (
        "fa7d762d5699ec5fc19ed1948ebc1c328f2c1931"
    ),
    "src/trading_bot/arch133_parent_policy_diagnostic/operator.py": (
        "c06b3d575443ead6624b27cca5c95a3ce10d4206"
    ),
    "scripts/run_arch133_parent_policy_diagnostic.py": (
        "9e8d7aa959d40bc689cd1c3ae17506bdbddb16ba"
    ),
}
ARCH133_PARENT_POLICY_DIAGNOSTIC_REGISTRATION_PIN: Final = (
    "33753d52734b0358250e79b442ef6d5759fab043709154299a919aee594370b8"
)


def _arch133_parent_policy_diagnostic_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the separate 133-T read-only surface and retained predecessor chain."""
    failures = list(_arch133_parent_security_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-T diagnostic source drift: {relative}")
        if (
            tuple(ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS)
            != ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES
        ):
            failures.append("133-T diagnostic inventory drift")
        name = "arch133-robinhood-reprovision-parent-policy-diagnostic"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(inventories) != 1
            or ast.literal_eval(inventories[0]) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-T diagnostic active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_PARENT_POLICY_DIAGNOSTIC_REGISTRATION_PIN
        ):
            failures.append("133-T diagnostic source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_parent_policy_diagnostic_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133t"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-T diagnostic registration drift")
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 1
            ]
            != (
                "arch133-robinhood-reprovision-parent-security-diagnostic",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-T diagnostic ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-T diagnostic workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-T diagnostic boundary unavailable")
    return tuple(failures)


def _arch133_reprovision_corrected_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the corrected 133-U source surface and the complete T authority chain."""
    failures = list(_arch133_parent_policy_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133U_REPROVISION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-U reprovision source drift: {relative}")
        name = "arch133-robinhood-fresh-activation-reprovision-corrected"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133U_REPROVISION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "4759c440268cdb3a7d96b7449b1219a1dc4e6e8afa070d9ad098268257dad319"
            or tuple(ARCH133U_REPROVISION_PINS) != ARCH133U_REPROVISION_SOURCES
        ):
            failures.append("133-U source inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133U_REPROVISION_REGISTRATION_PIN
        ):
            failures.append("133-U registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_reprovision_corrected_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133u"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133U_REPROVISION_SOURCES,
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-U registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-reprovision-parent-policy-diagnostic",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-U ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-U workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-U source boundary unavailable")
    return tuple(failures)


ARCH133V_RECONCILIATION_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_reconciliation/__init__.py",
    "src/trading_bot/arch133_reprovision_reconciliation/operator.py",
    "scripts/run_arch133_reprovision_reconciliation.py",
)
ARCH133V_RECONCILIATION_PINS: Final = {
    "src/trading_bot/arch133_reprovision_reconciliation/__init__.py": (
        "292384cf303c6a68144ecebd4d3f51606c1427f1e647834688a08dc3e7b183fb"
    ),
    "src/trading_bot/arch133_reprovision_reconciliation/operator.py": (
        "260f337c627a195046eadfa0b00bdd131d51bb393cbbda2277a796442fa78f05"
    ),
    "scripts/run_arch133_reprovision_reconciliation.py": (
        "ea5730bb29cefac8b7355f8d5041d938bc39ab4937c20bf5cf58dcbe6b36e16f"
    ),
}
ARCH133V_RECONCILIATION_REGISTRATION_PIN: Final = (
    "ecfb923f10ce676138b34e422d28d2f387dd5f33f59116a69fabba6e58ede741"
)


def _arch133_reprovision_reconciliation_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the read-only 133-V surface and complete consumed U authority chain."""
    failures = list(_arch133_reprovision_corrected_authority_check(repo_root))
    try:
        for relative, expected in ARCH133V_RECONCILIATION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-V reprovision source drift: {relative}")
        name = "arch133-robinhood-reprovision-indeterminate-reconciliation"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133V_RECONCILIATION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "f9ef00b1314c337868a49894c201e936df01cf1ce549695b8812a7b2f9923394"
            or tuple(ARCH133V_RECONCILIATION_PINS) != ARCH133V_RECONCILIATION_SOURCES
        ):
            failures.append("133-V source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-V active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133V_RECONCILIATION_REGISTRATION_PIN
        ):
            failures.append("133-V registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_reprovision_reconciliation_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133v"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133V_RECONCILIATION_SOURCES,
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-V registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-fresh-activation-reprovision-corrected",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-V ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-V workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-V source boundary unavailable")
    return tuple(failures)


ARCH133W_RECOVERY_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_recovery/__init__.py",
    "src/trading_bot/arch133_reprovision_recovery/admission.py",
    "src/trading_bot/arch133_reprovision_recovery/native.py",
    "src/trading_bot/arch133_reprovision_recovery/operator.py",
    "scripts/run_arch133_reprovision_recovery.py",
)
ARCH133W_RECOVERY_PINS: Final = {
    "src/trading_bot/arch133_reprovision_recovery/__init__.py": (
        "61104f164e26ce56f30f981ac1263e817bc2e38643a5a27d84fddb6bd5445c08"
    ),
    "src/trading_bot/arch133_reprovision_recovery/admission.py": (
        "d974c87e07c081396ecad04ea7ef0ba1b39653d5ce6f8f820f7e64fae3693a64"
    ),
    "src/trading_bot/arch133_reprovision_recovery/native.py": (
        "0553efac4da5258b2fc8c9b5534d5aaee3aae52f4baa856182592d2747837d97"
    ),
    "src/trading_bot/arch133_reprovision_recovery/operator.py": (
        "fe8e57cb4b936b0552708801112a139a411e1c3aa3d76e412777475e6536cdb2"
    ),
    "scripts/run_arch133_reprovision_recovery.py": (
        "404912297cc3ff595491d38d8f3c746f0bf5e39086a2b08e79657e19723db194"
    ),
}
ARCH133W_RECOVERY_REGISTRATION_PIN: Final = (
    "5061f8dbbbff58794c7ee4f3b1266988fab1f7313c3e3570e1f2c7e1908b8736"
)


def _arch133_reprovision_recovery_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the read-only 133-W surface and complete accepted V authority chain."""
    failures = list(_arch133_reprovision_reconciliation_authority_check(repo_root))
    try:
        for relative, expected in ARCH133W_RECOVERY_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-W reprovision source drift: {relative}")
        name = "arch133-robinhood-reprovision-sealed-predecessor-recovery"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133W_RECOVERY_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "3d78d2447e55f43ada40c18aad6700d965158f34f33b87efdd8358c118f823af"
            or tuple(ARCH133W_RECOVERY_PINS) != ARCH133W_RECOVERY_SOURCES
        ):
            failures.append("133-W source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-W active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133W_RECOVERY_REGISTRATION_PIN
        ):
            failures.append("133-W registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check is not _arch133_reprovision_recovery_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133w"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_recovery.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133W_RECOVERY_SOURCES,
                "tests/review_paper/test_arch133_reprovision_recovery.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-W registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-reprovision-indeterminate-reconciliation",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-W ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-W workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-W source boundary unavailable")
    return tuple(failures)


ARCH133X_RECONCILIATION_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_recovery_reconciliation/__init__.py",
    "src/trading_bot/arch133_reprovision_recovery_reconciliation/operator.py",
    "scripts/run_arch133_reprovision_recovery_reconciliation.py",
)
ARCH133X_RECONCILIATION_PINS: Final = {
    "src/trading_bot/arch133_reprovision_recovery_reconciliation/__init__.py": (
        "ce48f46c0ee51292736cd61a658d8da43cc3ea0683a5b325a31a560deefc0b3d"
    ),
    "src/trading_bot/arch133_reprovision_recovery_reconciliation/operator.py": (
        "4ad752d4634075244ebe614a2da271741deeb759b59de801788d92e6ddf188b5"
    ),
    "scripts/run_arch133_reprovision_recovery_reconciliation.py": (
        "fad91e7fad8f1c9c52adc4e1b5ba8f7d79f382afc0fd8f0c8dbc9ecbf3c34b89"
    ),
}
ARCH133X_RECONCILIATION_REGISTRATION_PIN: Final = (
    "0a9ea47f85b1f5feca156c8720377c4a2ae9476ac474c5b9dc0739522906d710"
)


def _arch133_reprovision_recovery_reconciliation_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the read-only 133-X surface and complete accepted W authority chain."""
    failures = list(_arch133_reprovision_recovery_authority_check(repo_root))
    try:
        for relative, expected in ARCH133X_RECONCILIATION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-X reprovision source drift: {relative}")
        name = "arch133-robinhood-reprovision-recovery-reconciliation"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133X_RECONCILIATION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "a8510efa09c2293c965f6ce998f6be79850864859ad3bf67a76f26e5a6c78160"
            or tuple(ARCH133X_RECONCILIATION_PINS) != ARCH133X_RECONCILIATION_SOURCES
        ):
            failures.append("133-X source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-X active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133X_RECONCILIATION_REGISTRATION_PIN
        ):
            failures.append("133-X registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_reprovision_recovery_reconciliation_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133x"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133X_RECONCILIATION_SOURCES,
                "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-X registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-reprovision-sealed-predecessor-recovery",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-X ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-X workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-X source boundary unavailable")
    return tuple(failures)


ARCH133Y_QUALIFICATION_SOURCES: Final = (
    "src/trading_bot/arch133_windows_rename_qualification/__init__.py",
    "src/trading_bot/arch133_windows_rename_qualification/native.py",
    "src/trading_bot/arch133_windows_rename_qualification/operator.py",
    "scripts/run_arch133_windows_rename_qualification.py",
)
ARCH133Y_QUALIFICATION_PINS: Final = {
    "src/trading_bot/arch133_windows_rename_qualification/__init__.py": (
        "f0662e01d82fed62613c366bf4b83e351e5faa792ea5af4315f6493cb4ca8dec"
    ),
    "src/trading_bot/arch133_windows_rename_qualification/native.py": (
        "df75e8bbb291a01484510f1a3d373a3236e6ecd764fb06e7e821c8800ebc4b2f"
    ),
    "src/trading_bot/arch133_windows_rename_qualification/operator.py": (
        "65c30f88ac91bd2fbf816da02d8fce6a64b8d95d205dde40c74737c6b5ec0296"
    ),
    "scripts/run_arch133_windows_rename_qualification.py": (
        "d9ec4f0dfbf62ac373e9e6db159f1089d78372925f148d695b7067bbca16c89c"
    ),
}
ARCH133Y_QUALIFICATION_REGISTRATION_PIN: Final = (
    "1e923b6612c5abb15763dfe19281e02f8515287f654d2fbf577fbf1bc4511fde"
)


def _arch133_windows_rename_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the scratch-only 133-Y surface and complete accepted X authority chain."""
    failures = list(
        _arch133_reprovision_recovery_reconciliation_authority_check(repo_root)
    )
    try:
        for relative, expected in ARCH133Y_QUALIFICATION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-Y reprovision source drift: {relative}")
        name = "arch133-robinhood-windows-rename-qualification"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133Y_QUALIFICATION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "ff3b2b1ad278beaad14d996c5d523982edb419025e73728a29050ebaede9001a"
            or tuple(ARCH133Y_QUALIFICATION_PINS) != ARCH133Y_QUALIFICATION_SOURCES
        ):
            failures.append("133-Y source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-Y active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133Y_QUALIFICATION_REGISTRATION_PIN
        ):
            failures.append("133-Y registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_windows_rename_qualification_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133y"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_windows_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133Y_QUALIFICATION_SOURCES,
                "tests/review_paper/test_arch133_windows_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-Y registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-reprovision-recovery-reconciliation",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-Y ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-Y workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-Y source boundary unavailable")
    return tuple(failures)


ARCH133Z_QUALIFICATION_SOURCES: Final = (
    "src/trading_bot/arch133_closed_descendant_rename_qualification/__init__.py",
    "src/trading_bot/arch133_closed_descendant_rename_qualification/native.py",
    "src/trading_bot/arch133_closed_descendant_rename_qualification/operator.py",
    "scripts/run_arch133_closed_descendant_rename_qualification.py",
)
ARCH133Z_QUALIFICATION_PINS: Final = {
    "src/trading_bot/arch133_closed_descendant_rename_qualification/__init__.py": (
        "0600fc6ebb08096c191f7bb3e1c740e3e5e51bd513bc17fd9a7541b3cba18ad3"
    ),
    "src/trading_bot/arch133_closed_descendant_rename_qualification/native.py": (
        "b252da668fdffd24038307b0ca2849b15caa735a380d9b160a5b8ab40a624c6e"
    ),
    "src/trading_bot/arch133_closed_descendant_rename_qualification/operator.py": (
        "f9bb8a867a9afe1c20aed6b0387dffd6adc8eea17eee4ec391395cae8c07aeec"
    ),
    "scripts/run_arch133_closed_descendant_rename_qualification.py": (
        "bfd8a858a224ce7779ad16bba13585443f845cd2b1eb754d810f408e824761b9"
    ),
}
ARCH133Z_QUALIFICATION_REGISTRATION_PIN: Final = (
    "a9b6d9a36abd32929f33285065e9cfdc96c876e876b822bfac08a0c3347d9c23"
)


def _arch133_closed_descendant_rename_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the scratch-only 133-Z surface and complete accepted Y authority chain."""
    failures = list(_arch133_windows_rename_qualification_authority_check(repo_root))
    try:
        for relative, expected in ARCH133Z_QUALIFICATION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-Z reprovision source drift: {relative}")
        name = "arch133-robinhood-closed-descendant-rename-qualification"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133Z_QUALIFICATION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "f6d0914d71238b1d7a3c06a36240eb988918882246dc88cd473b78e568e5c967"
            or tuple(ARCH133Z_QUALIFICATION_PINS) != ARCH133Z_QUALIFICATION_SOURCES
        ):
            failures.append("133-Z source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-Z active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133Z_QUALIFICATION_REGISTRATION_PIN
        ):
            failures.append("133-Z registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_closed_descendant_rename_qualification_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133z"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133Z_QUALIFICATION_SOURCES,
                "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-Z registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-windows-rename-qualification",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-Z ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-Z workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-Z source boundary unavailable")
    return tuple(failures)


def _arch133_reprovision_diagnostic_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the 133-R zero-effect staged admission diagnostic."""
    failures = list(_arch133_reprovision_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_REPROVISION_DIAGNOSTIC_PINS.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-R diagnostic source drift: {relative}")
        if (
            tuple(ARCH133_REPROVISION_DIAGNOSTIC_PINS)
            != ARCH133_REPROVISION_DIAGNOSTIC_SOURCES
        ):
            failures.append("133-R diagnostic inventory drift")
        name = "arch133-robinhood-reprovision-admission-diagnostic"
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_reprovision_diagnostic_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133r"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_REPROVISION_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-R diagnostic registration drift")
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 1
            ]
            != (
                "arch133-robinhood-fresh-activation-reprovision",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-R diagnostic ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-R diagnostic workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-R diagnostic boundary unavailable")
    return tuple(failures)


def _arch133_reprovision_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin new source, workflow and registration; preserve consumed sources."""
    failures = list(_arch133_scheduler_installation_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_REPROVISION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-Q reprovision source drift: {relative}")
        name = "arch133-robinhood-fresh-activation-reprovision"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            n.value
            for n in tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "ARCH133_REPROVISION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "e8b866d14b9914dad4920ec6fb049c68f8aa5f4a0b0cb39f26dc65444a2edf21"
            or tuple(ARCH133_REPROVISION_PINS) != ARCH133_REPROVISION_SOURCES
        ):
            failures.append("133-Q source inventory drift")
        registrations = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_REPROVISION_REGISTRATION_PIN
        ):
            failures.append("133-Q registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check is not _arch133_reprovision_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133q"
        ):
            failures.append("133-Q source-only capability drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != ("arch133-robinhood-single-session-scheduler-installation", name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-Q ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-Q workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-Q source boundary unavailable")
    return tuple(failures)


def _arch133_scheduler_installation_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin full inert closure, canonical builder and native transport; no invocation."""
    failures = list(_arch133_publication_corrected_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_SCHEDULER_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8")
            material = (
                ast.dump(ast.parse(source), include_attributes=False)
                if relative.endswith(".py")
                else source
            )
            if hashlib.sha256(material.encode()).hexdigest() != expected:
                failures.append(f"133-P installation boundary drift: {relative}")
        name = "arch133-robinhood-single-session-scheduler-installation"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        registrations = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_SCHEDULER_REGISTRATION_PIN
        ):
            failures.append("133-P source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133p"
            or spec.authority_check
            is not _arch133_scheduler_installation_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *(p for p in ARCH133_SCHEDULER_SOURCES if p.endswith(".py")),
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-P source-only capability drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != ("arch133-robinhood-publication-state-paper-corrected", name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-P checkpoint ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-P source workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-P installation boundary unavailable")
    return tuple(failures)


def _arch133_publication_corrected_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the exact read-only import closure; never import/invoke the operator."""
    failures = list(_arch133_publication_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_PUBLICATION_CORRECTED_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-O verifier boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-publication-state-paper-corrected"
        registrations = [
            n
            for n in ast.walk(runner_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_PUBLICATION_CORRECTED_REGISTRATION_PIN
        ):
            failures.append("133-O source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133o"
            or spec.authority_check
            is not _arch133_publication_corrected_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PUBLICATION_CORRECTED_SOURCES,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-O source-only capability drift")
        predecessor = "arch133-robinhood-publication-state-paper-diagnostic"
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1] != (predecessor, name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-O checkpoint ordering drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-O verifier boundary unavailable")
    return tuple(failures)


def _arch133_publication_diagnostic_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the exact read-only import closure; never import/invoke the operator."""
    failures = list(_arch133_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_PUBLICATION_DIAGNOSTIC_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-N verifier boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-publication-state-paper-diagnostic"
        registrations = [
            n
            for n in ast.walk(runner_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_PUBLICATION_DIAGNOSTIC_REGISTRATION_PIN
        ):
            failures.append("133-N source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133n"
            or spec.authority_check
            is not _arch133_publication_diagnostic_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PUBLICATION_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-N source-only capability drift")
        predecessor = "arch133-robinhood-post-publication-verifier"
        prior = "arch133-robinhood-post-publication-stage-diagnostic"
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 2 : index + 1] != (predecessor, prior, name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-N checkpoint ordering drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-N verifier boundary unavailable")
    return tuple(failures)


def _arch133_diagnostic_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the exact read-only import closure; never import/invoke the operator."""
    failures = list(_arch133_verifier_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_DIAGNOSTIC_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-M verifier boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-post-publication-stage-diagnostic"
        registrations = [
            n
            for n in ast.walk(runner_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_DIAGNOSTIC_REGISTRATION_PIN
        ):
            failures.append("133-M source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133m"
            or spec.authority_check is not _arch133_diagnostic_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-M source-only capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 1
            ]
            != ("arch133-robinhood-post-publication-verifier", name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-M checkpoint ordering drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-M verifier boundary unavailable")
    return tuple(failures)


def _arch133_verifier_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the exact read-only import closure; never import/invoke the operator."""
    failures = list(_arch133_recovery_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_VERIFIER_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-L verifier boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-post-publication-verifier"
        registrations = [
            n
            for n in ast.walk(runner_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_VERIFIER_REGISTRATION_PIN
        ):
            failures.append("133-L source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133l"
            or spec.authority_check is not _arch133_verifier_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_VERIFIER_SOURCES,
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-L source-only capability drift")
        predecessor = "arch133-robinhood-retained-root-acl-recovery"
        successor = "arch133-robinhood-post-publication-stage-diagnostic"
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 2
            ]
            != (predecessor, name, successor)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-L checkpoint ordering drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-L verifier boundary unavailable")
    return tuple(failures)


def _arch133_recovery_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Source-only pins; never import or invoke either recovery operator mode."""
    failures = list(_arch133_retained_root_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_RECOVERY_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-K recovery boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-retained-root-acl-recovery"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_RECOVERY_REGISTRATION_PIN
        ):
            failures.append("133-K source-only registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133k"
            or spec.authority_check is not _arch133_recovery_authority_check
            or spec.tests
            != (
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_RECOVERY_SOURCES,
                "tests/review_paper/test_retained_root_acl_recovery.py",
            )
        ):
            failures.append("133-K runtime capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS.count(name) != 1
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) + 1]
            != "arch133-robinhood-post-publication-verifier"
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) - 1]
            != "arch133-robinhood-retained-root-diagnostic"
        ):
            failures.append("133-K batch successor registration drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-K recovery boundary unavailable")
    return tuple(failures)


def _arch133_retained_root_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Source-only pins; never import or invoke the operator diagnostic."""
    failures = list(_arch133_scratch_root_acl_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_RETAINED_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-J read-only boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-retained-root-diagnostic"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_RETAINED_REGISTRATION_PIN
        ):
            failures.append("133-J source-only registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133j"
            or spec.authority_check is not _arch133_retained_root_authority_check
            or spec.tests
            != (
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_RETAINED_SOURCES,
                "tests/review_paper/test_retained_root_diagnostic.py",
            )
        ):
            failures.append("133-J runtime capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS.count(name) != 1
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) - 1]
            != "arch133-robinhood-scratch-root-acl-qualification"
        ):
            failures.append("133-J batch successor registration drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-J read-only boundary unavailable")
    return tuple(failures)


ARCH133_SCRATCH_SOURCES: Final = (
    "src/trading_bot/arch133_acl/__init__.py",
    "src/trading_bot/arch133_acl/primitive.py",
    "src/trading_bot/arch133_acl/read_only.py",
    "src/trading_bot/arch133_acl/qualification.py",
    "scripts/run_arch133_scratch_root_acl.py",
    "src/trading_bot/arch133_acl/root_policy_apply.py",
    "src/trading_bot/arch133_acl/administrator.py",
)
ARCH133_SCRATCH_PINS: Final = {
    "src/trading_bot/arch133_acl/root_policy_apply.py": (
        "d3777322118c9fb1353102fd083251c4b59ac9ee552572818a87546a0cf41dde"
    ),
    "src/trading_bot/arch133_acl/administrator.py": (
        "286d4ab228fdad27b719a0673a19583bfe3cc667dcec958fa34bad30e8742611"
    ),
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/primitive.py": (
        "f68c54990fefc2f82eaf7758b41193b9450123cbb7fb13458576c8d427e3cd13"
    ),
    "src/trading_bot/arch133_acl/qualification.py": (
        "c798ee76ea0680395a0bb32223250fcb58c810afad4c771a5822157e4c47e7f1"
    ),
    "scripts/run_arch133_scratch_root_acl.py": (
        "6ef171aa76609dc48a4f3632b7e29845e1f5fe7e6cfadb6db946fb774252db73"
    ),
    # Pin package initializers too: fresh-process import closure is effect-free.
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
}
ARCH133_SCRATCH_REGISTRATION_PIN: Final = (
    "93e30428d22ce71372e9cd9d29b7511feb9875b1bd5830186404a8c307092afa"
)


def _arch133_scratch_root_acl_authority_check(repo_root: Path) -> tuple[str, ...]:
    """133-I is SOURCE ONLY: no preflight/execute callback or production import."""
    failures = list(_arch133_host_publication_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_SCRATCH_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            actual = hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode()
            ).hexdigest()
            if actual != expected:
                failures.append(f"133-I scratch boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-scratch-root-acl-qualification"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_SCRATCH_REGISTRATION_PIN
        ):
            failures.append("133-I source-only registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133i"
            or spec.authority_check is not _arch133_scratch_root_acl_authority_check
            or spec.tests
            != (
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_SCRATCH_SOURCES,
                "src/trading_bot/review_paper/unattended_publication_windows.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            )
        ):
            failures.append("133-I runtime capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS.count(name) != 1
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) - 1]
            != "arch133-robinhood-unattended-host-publication"
        ):
            failures.append("133-I batch successor registration drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-I scratch boundary unavailable")
    return tuple(failures)


def _arch133_host_publication_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin all 133-H operator/native composition and reused security boundaries."""
    failures: list[str] = []
    try:
        for relative, expected in ARCH133_PUBLICATION_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            actual = hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            if actual != expected:
                failures.append(f"133-H closed publication boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-host-publication"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != ARCH133_PUBLICATION_REGISTRATION_PIN
        ):
            failures.append("133-H source-only registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133h"
            or spec.authority_check is not _arch133_host_publication_authority_check
            or spec.tests
            != (*ARCH133_H_K_TESTS, "tests/review_paper/test_unattended_publication.py")
            or spec.ruff_paths
            != (
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_PUBLICATION_SOURCES,
                "tests/review_paper/test_unattended_publication.py",
            )
        ):
            failures.append("133-H runtime source-only registration drift")
        ci = next(
            n
            for n in runner_tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "ACTIVE_CI_CHECKPOINTS"
        )
        if (
            tuple(ast.literal_eval(ci.value)) != ACTIVE_CI_CHECKPOINTS
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) - 1]
            != "arch133-robinhood-unattended-host-bootstrap"
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-H batch registration drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-H workflow invocation drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        StopIteration,
    ):
        failures.append("133-H source or structural boundary unavailable")
    return tuple(failures)


ARCH133_PUBLICATION_SOURCES: Final = (
    "src/trading_bot/review_paper/unattended_publication.py",
    "src/trading_bot/review_paper/unattended_publication_windows.py",
    "scripts/run_arch133_host_publication.py",
    "src/trading_bot/arch133_acl/__init__.py",
    "src/trading_bot/arch133_acl/primitive.py",
    "src/trading_bot/arch133_acl/read_only.py",
    "src/trading_bot/arch133_acl/root_policy_apply.py",
    "src/trading_bot/arch133_acl/administrator.py",
)
ARCH133_PUBLICATION_PINS: Final = {
    "src/trading_bot/arch133_acl/root_policy_apply.py": (
        "d3777322118c9fb1353102fd083251c4b59ac9ee552572818a87546a0cf41dde"
    ),
    "src/trading_bot/arch133_acl/administrator.py": (
        "286d4ab228fdad27b719a0673a19583bfe3cc667dcec958fa34bad30e8742611"
    ),
    # 133-I successor owns the extracted native leaf; all other 133-H pins remain.
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/primitive.py": (
        "f68c54990fefc2f82eaf7758b41193b9450123cbb7fb13458576c8d427e3cd13"
    ),
    "src/trading_bot/review_paper/unattended_publication.py": (
        "820b6d0f86f56c22a03bbd734b6a3a98d0042d8ac167f28b39230d99d89da128"
    ),
    "src/trading_bot/review_paper/unattended_publication_windows.py": (
        "44397d1ba3594c12ab85e76d4bf891a424e646c67f12f20f67a9c36c2cce7756"
    ),
    "scripts/run_arch133_host_publication.py": (
        "5b5bb84080d916d18383657d8d6c2f96e7fa3a47d4e74b137cbe42b5ff7df5d1"
    ),
    "src/trading_bot/runtime/windows_authority_security.py": (
        "4412b3691d6c7f596ffab6e74d71aef438a653a9c03a21ff5cb6110190c80734"
    ),
    "src/trading_bot/runtime/personal_desktop_paper_account_security.py": (
        "8e81affbb85f98f6a6b11e65e9a97f6e66b9113a5aca22080d3fb4183748d95d"
    ),
    "src/trading_bot/review_paper/unattended_host_identity.py": (
        "987ea024d33025e3da26993df7768435e5a031666d72cdc73613f9b69a24a27c"
    ),
    "src/trading_bot/review_paper/unattended_activation.py": (
        "7fc65af97b2465d82b907a67365d898a028226c2145b4cc77f6cdc6634f60b27"
    ),
    "src/trading_bot/review_paper/unattended_state_schema.py": (
        "02859147d4d476c3b23b56f3c63f0ae5857caa372eaaf8cc9eeb230d88e34b77"
    ),
    "src/trading_bot/review_paper/unattended_scheduler.py": (
        "79fe37f5e4c36c70096f86414f5e32151556c617b82bc086742a44470c7dde29"
    ),
    "src/trading_bot/review_paper/store.py": (
        "880c295e03c9fd3b9cc2e187b4f5e23714e0477a543211479702bd6c5cebce76"
    ),
    "src/trading_bot/review_paper/unattended_state_store.py": (
        "93ffd82253c22803ff318721779e892f5f20dd9f996c8a2cdf3ba8f154ced822"
    ),
    "src/trading_bot/review_paper/unattended_state_verifier.py": (
        "95e20d01781879a8c0637973fdc0a6b5efaff17d8377ffa59dbe865cb9c14d1c"
    ),
    "src/trading_bot/robinhood_execute_qualification_verifier.py": (
        "e978006d124ff8945065b5e1ae240914068a80ce1ac3043174eb2e887e4043ff"
    ),
}
ARCH133_PUBLICATION_REGISTRATION_PIN: Final = (
    "14b2fabf7c5c7bcbc029bea006456f8dcc7ff54e329aaa09e3b389782d74c74a"
)


def _arch133_host_bootstrap_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_host_identity.py": (
                "cb8b624c70f0792f8eba0336cf6e372d3b78f612"
            ),
            "src/trading_bot/review_paper/unattended_scheduler.py": (
                "153395ce66ff11f7d0978541cbf9193ae4df3f30"
            ),
            "src/trading_bot/review_paper/unattended_host.py": (
                "eb41d518af9ead0e4260b081af63d48b11560023"
            ),
            "src/trading_bot/review_paper/unattended_host_bootstrap.py": (
                "54623c8c1933b227194532ca9d1ed702d3797279"
            ),
            "scripts/run_arch133_unattended_review_paper.py": (
                "661023c46a3e088d338b67282effb7f35b00a93d"
            ),
            "scripts/run_arch133_unattended_host_preflight.py": (
                "7916c2a9c90e33302e9313e5d35d9a282b90b149"
            ),
        }
        for relative, expected in pins.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-G closed bootstrap boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-host-bootstrap"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-G batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            len(registrations) != 1
            or spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133g"
            or spec.authority_check is not _arch133_host_bootstrap_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-G source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch133-robinhood-unattended-host-scheduler-surface"
            )
            + 1
        ):
            failures.append("133-G checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-G workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-G source or structural boundary unavailable")
    return tuple(failures)


def _arch133_execution_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_execution.py": (
                "2c74a68708b99f7813806c50f0519046b90982f3"
            ),
        }
        for relative, expected in pins.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-D closed composition boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-review-paper-execution"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "2ceac689f87333f29d7389a315199bd580fc250a45d00856efd3829e554475e9"
        ):
            failures.append("133-D source-only registration drift")
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-D batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133d"
            or spec.authority_check is not _arch133_execution_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/test_robinhood_paper_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_execution.py",
                "src/trading_bot/robinhood_paper_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-D source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch133-robinhood-unattended-one-wake-composition"
            )
            + 1
        ):
            failures.append("133-D checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-D workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-D source or structural boundary unavailable")
    return tuple(failures)


def _arch133_one_wake_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_one_wake.py": (
                "9fbcb9d303bc8aa52362a92eef472fd6419a8e66"
            ),
        }
        for relative, expected in pins.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-C closed composition boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-one-wake-composition"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "4cefb0203b851fde16f5ee5f35cbff4e54f3fae04df508bfe84a4341c460a10c"
        ):
            failures.append("133-C source-only registration drift")
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-C batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133c"
            or spec.authority_check is not _arch133_one_wake_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-C source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch133-robinhood-unattended-state-store") + 1
        ):
            failures.append("133-C checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-C workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-C source or structural boundary unavailable")
    return tuple(failures)


def _arch133_unattended_state_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_state_schema.py": (
                "02859147d4d476c3b23b56f3c63f0ae5857caa372eaaf8cc9eeb230d88e34b77"
            ),
            "src/trading_bot/review_paper/unattended_state_store.py": (
                "93ffd82253c22803ff318721779e892f5f20dd9f996c8a2cdf3ba8f154ced822"
            ),
            "src/trading_bot/review_paper/unattended_state_verifier.py": (
                "95e20d01781879a8c0637973fdc0a6b5efaff17d8377ffa59dbe865cb9c14d1c"
            ),
        }
        for relative, expected in pins.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode("utf-8")
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-B closed state boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-state-store"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "33a9e39be9c3094ee8cdd31c2b11b00e0a5bc3e7dfd6770a54f867f322fed594"
        ):
            failures.append("133-B source-only registration drift")
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-B batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133b"
            or spec.authority_check is not _arch133_unattended_state_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_state_store.py",
            )
        ):
            failures.append("133-B source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch133-robinhood-unattended-activation-core")
            + 1
        ):
            failures.append("133-B checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-B workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-B source or structural boundary unavailable")
    return tuple(failures)


def _arch133_unattended_activation_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/unattended_activation.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "7fc65af97b2465d82b907a67365d898a028226c2145b4cc77f6cdc6634f60b27"
        ):
            failures.append("133-A pure activation/wake boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-activation-core"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "fc97901789ef914ecc1550919cab9a04ab3f8969ea3a380a20b522d99b53221e"
        ):
            failures.append("133-A source-only checkpoint registration drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-A checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("133-A checkpoint has host/effect capability")
        if spec.remote_branch != "feature/robinhood-unattended-review-paper-133a":
            failures.append("133-A checkpoint remote branch drift")
        if (
            spec.tests
            != (*ARCH133_A_G_TESTS, "tests/review_paper/test_unattended_activation.py")
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_activation.py",
                "tests/review_paper/test_unattended_activation.py",
            )
            or spec.authority_check
            is not _arch133_unattended_activation_authority_check
        ):
            failures.append("133-A checkpoint coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-supervised-qualification")
            + 1
        ):
            failures.append("133-A checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-A workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-A source or structural boundary unavailable")
    return tuple(failures)


def _arch131_nyse_published_regular_session_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = (
            repo_root
            / "src/trading_bot/review_paper/nyse_published_regular_sessions.py"
        )
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "a71d7b4c0ff130fa32a11e5e827e41722dd2044940f4c2259b3d985cc893e7d6"
        ):
            failures.append("131-S published regular-session boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-nyse-published-regular-session-authority"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "0016427c31d574f73132803031404ff293ffdda00ef7f113d5bbb238177b1a71"
        ):
            failures.append("131-S source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-S remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-S checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-S checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-S checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-supervised-prepare-verifier")
            + 1
        ):
            failures.append("131-S checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-S workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-S source or structural boundary unavailable")
    return tuple(failures)


def _arch131_published_session_prepare_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/published_session_prepare.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "831c75256addd7a779a8f776c30c7ce9bbe2b16381f71231dbc71dfc9efde42a"
        ):
            failures.append("131-T published regular-session boundary drift")

        verifier = (
            repo_root / "src/trading_bot/robinhood_prepare_qualification_verifier.py"
        ).read_text(encoding="utf-8")
        if (
            hashlib.sha256(
                ast.dump(ast.parse(verifier), include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "c618e667286ff06fdda772ca78af29affb1b0cd9b9158c3267e42920b89d677a"
        ):
            failures.append("131-T canonical schedule verifier boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-published-session-prepare"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "0c83b9828c88cb93dce677e6bc229cff6070457146e659c344aa062b9db84a82"
        ):
            failures.append("131-T source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-T remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-T checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-T checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-T checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch131-nyse-published-regular-session-authority"
            )
            + 1
        ):
            failures.append("131-T checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-T workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-T source or structural boundary unavailable")
    return tuple(failures)


def _arch131_supervised_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        digests = {
            "src/trading_bot/robinhood_supervised_qualification.py": (
                "743d11a3bb049f33aacba0d6cda126580e9cf636e4899745999a08438cf63e86"
            ),
            "src/trading_bot/robinhood_execute_qualification_verifier.py": (
                "e978006d124ff8945065b5e1ae240914068a80ce1ac3043174eb2e887e4043ff"
            ),
            "scripts/robinhood_supervised_qualification.py": (
                "823ddad595d7d72068c5393bf7bcea81ff276685dc86e29be758480dbaf53fa9"
            ),
            "src/trading_bot/review_paper/__init__.py": (
                "bbbedff7dde18395e8576984a6e914c8cd761329ee5fc6d25defca5e43e1bd75"
            ),
        }
        for relative, expected in digests.items():
            source = (repo_root / relative).read_text(encoding="utf-8")
            actual = hashlib.sha256(
                ast.dump(ast.parse(source), include_attributes=False).encode()
            ).hexdigest()
            if actual != expected:
                failures.append(
                    "131-V qualification boundary drift: "
                    + relative
                    + " actual="
                    + actual
                )
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-supervised-qualification"
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != "66d7c5b592b044a3e6803c48d927d58688792df3fe7fa0c0da82617298972993"
        ):
            failures.append("131-V source-only registration drift")
        ci = [
            node
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci) != 1
            or hashlib.sha256(
                ast.dump(ci[0].value, include_attributes=False).encode()
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-V checkpoint batch drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_branch != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-V source-only capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS.count(name) != 1
            or ACTIVE_CI_CHECKPOINTS.index(name)
            != ACTIVE_CI_CHECKPOINTS.index(
                "arch131-robinhood-published-prepare-operator"
            )
            + 1
        ):
            failures.append("131-V checkpoint ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("131-V workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-V source or structural boundary unavailable")
    return tuple(failures)


def _arch131_published_prepare_operator_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/robinhood_prepare_operator.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "874122a602008c0e85cd9f3ac1cafc2d86acbd71581a47fe1dba23d39221785d"
        ):
            failures.append("131-U PREPARE composition/browser/effect boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-published-prepare-operator"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "284134d18999c57e6804b38aed32fe314a55997f64a4d2d398cec172bec892ed"
        ):
            failures.append("131-U source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-U remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-U checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-U checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-U checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-published-session-prepare")
            + 1
        ):
            failures.append("131-U checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-U workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-U source or structural boundary unavailable")
    return tuple(failures)


def _arch131_session_admission_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/session_admission.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "12afcc9014383695b0b10ca7a8d71bd61f40ebc60e07588eabe6dd98fba49d92"
        ):
            failures.append("131-M deterministic temporal boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-session-admission"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "1bc810681800fe4ee34053bb0dde0458f916ad1e445e2c8996a09e7754e8d95f"
        ):
            failures.append("131-M source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-M remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-M checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-M checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-M checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-live-qualification-verifier")
            + 1
        ):
            failures.append("131-M checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-M workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-M source or structural boundary unavailable")
    return tuple(failures)


def _arch131_risk_price_snapshot_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/risk_prices.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "5987785d351218fbd452bcd13dc5e9239341345a922f6d097d8f28c4ae68112b"
        ):
            failures.append("131-N canonical risk-price boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-risk-price-snapshot"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "8ce08250dfb33311c8755a086c93a5ef72618834c100b326662af1b50f6fa6cd"
        ):
            failures.append("131-N source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-N remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-N checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-N checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-N checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-session-admission") + 1):
            failures.append("131-N checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-N workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-N source or structural boundary unavailable")
    return tuple(failures)


def _arch131_forward_paper_preview_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/forward_preview.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "d5f9746abeb119336773a82e3a5d5de4e66c72147ee0a7eac45fd7e0a9b384b0"
        ):
            failures.append("131-O forward-preview boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-forward-paper-preview"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "aea7a5069b96a9d9467751fe4fb2a6a894967bb9115969bdda3f2cd9c02e8408"
        ):
            failures.append("131-O source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-O remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-O checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-O checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-O checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-risk-price-snapshot") + 1):
            failures.append("131-O checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-O workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-O source or structural boundary unavailable")
    return tuple(failures)


def _arch131_risk_price_acquisition_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/risk_price_acquisition.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "57f86533abdd21e3cc673dd5c0bcbfb14298b1fdc057de32e7aa458218425f61"
        ):
            failures.append("131-P risk-price acquisition boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-risk-price-acquisition"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "bdbab6decc92b66f3e7973910b4c0f8e4d6f552249ac5562dacaf1e5cd7b58a5"
        ):
            failures.append("131-P source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-P remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-P checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-P checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-P checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-preview") + 1
        ):
            failures.append("131-P checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-P workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-P source or structural boundary unavailable")
    return tuple(failures)


def _arch131_supervised_forward_paper_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/supervised_forward_paper.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "2f7c34cbe29fafac41ee004817b4dcd25f470a0962d716972e738b98253a76ee"
        ):
            failures.append("131-Q supervised forward-paper boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-supervised-forward-paper"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "883effee55b5a3e0ac0888575d0a3079ae33c0df22add5e8f9e46f651e5f696e"
        ):
            failures.append("131-Q source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-Q remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-Q checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-Q checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-Q checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-risk-price-acquisition") + 1
        ):
            failures.append("131-Q checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-Q workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-Q source or structural boundary unavailable")
    return tuple(failures)


def _arch131_prepare_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/prepare_qualification.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "b8d00a714e5bb8e8e05af950db0fb0b9e6634f4573149ba71dedd567a386b21d"
        ):
            failures.append("131-R PREPARE qualification boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-supervised-prepare-qualification"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "609db74ff7dc0436e06dfec6a2127ccd248882b1d4c1d5dcb722081c95769fbe"
        ):
            failures.append(
                "131-R PREPARE qualification source-only checkpoint registration drift"
            )

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-R PREPARE qualification remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append(
                "131-R PREPARE qualification checkpoint batch registration drift"
            )

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append(
                "131-R PREPARE qualification checkpoint has host/effect capability"
            )
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append(
                "131-R PREPARE qualification checkpoint remote branch drift"
            )
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-supervised-forward-paper")
            + 1
        ):
            failures.append("131-R PREPARE qualification checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append(
                "131-R PREPARE qualification workflow invocation/order drift"
            )
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append(
            "131-R PREPARE qualification source or structural boundary unavailable"
        )
    return tuple(failures)


def _arch131_prepare_verifier_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/robinhood_prepare_qualification_verifier.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        data = text_value.encode("utf-8")
        actual_blob = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
        ).hexdigest()
        if actual_blob != "8636e91df74ce8153930817c471043fdb21737f9":
            failures.append("131-R PREPARE verifier boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-supervised-prepare-verifier"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "b9efd873a9705fea3130b8d74e45d6d2628d499c85507504645b5bc5cf1a5a89"
        ):
            failures.append(
                "131-R PREPARE verifier source-only checkpoint registration drift"
            )

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-R PREPARE verifier remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "4cf4a5a3b124b459881b741bc9f93915b4dad10fbd5d55b77a0470912f3f60ef"
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append(
                "131-R PREPARE verifier checkpoint batch registration drift"
            )

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append(
                "131-R PREPARE verifier checkpoint has host/effect capability"
            )
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-R PREPARE verifier checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch131-robinhood-supervised-prepare-qualification"
            )
            + 1
        ):
            failures.append("131-R PREPARE verifier checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-R PREPARE verifier workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append(
            "131-R PREPARE verifier source or structural boundary unavailable"
        )
    return tuple(failures)


def _arch131_live_qualification_verifier_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/robinhood_live_qualification_verifier.py"
        text_value = path.read_text(encoding="utf-8")
        data = text_value.encode("utf-8")
        actual = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
        ).hexdigest()
        if actual != ARCH131_LQ_SOURCE_BLOB_SHA1:
            failures.append("131-LQ read-only reconciliation boundary drift")
        ast.parse(text_value)

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-live-qualification-verifier"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "e122534ab36defb989812bdf1575806a0eeada2c9a1db286b58d22fce848339c"
        ):
            failures.append("131-LQ source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-LQ remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-LQ checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-LQ checkpoint has host/effect capability")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-cycle") + 1):
            failures.append("131-LQ checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-LQ workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-LQ source or structural boundary unavailable")
    return tuple(failures)


def _arch131_virtual_risk_context_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (repo_root / "src/trading_bot/review_paper/risk_context.py").read_text(
                encoding="utf-8"
            )
        )
        # Pin the whole module: closed imports/calls, strict inputs, UTC ordering,
        # exact prices, one reconstruction, one snapshot, and all context fields.
        # Any added helper, risk/bridge/operator/performance use, identity creation
        # or network/host/config mutation changes this structural boundary.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "92f04d726f30bca61cb245456b782185fc183c10c71752664b0ba171e6a2d241"
        ):
            failures.append("131-K durable ledger/snapshot/context boundary drift")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-virtual-risk-context"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        # Pin test/lint coverage, authority binding, remote, and source-only flags.
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "94fc142aa4272e37708964b62244b280213a9a26b63fa3520c5d262a9b9f6cec"
        ):
            failures.append("131-K source-only checkpoint registration drift")
        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-K checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-K workflow invocation/131-J ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-K source or structural boundary unavailable")
    return tuple(failures)


def _arch131_deterministic_paper_pipeline_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (repo_root / "src/trading_bot/robinhood_paper_pipeline.py").read_text(
                encoding="utf-8"
            )
        )
        # Freeze the whole module: immutable result invariants, caller-owned
        # identities/context/limits, exactly one evaluation, rejected early
        # return, authoritative bridge, and one exact operator forwarding call.
        # Extra helpers/imports/calls, UUID creation, OrderEngine/MCP/OAuth,
        # config/logging/host effects, loops, retries and schedulers all drift.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "ee8b2a62bc434d4f611a27e786e3c30fcf1e7b0243f4b9fd70cb4686aae276b2"
        ):
            failures.append(
                "131-J deterministic composition/result/effect boundary drift"
            )
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-deterministic-paper-pipeline"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        # Also freeze test/lint surfaces, remote branch, authority binding and
        # explicit preflight=None/execute=None; no host capability is registered.
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "59c840ae9e36569ba06afc08624d9bb8e47de59bd19d20f217866c51d3fcc8dc"
        ):
            failures.append("131-J source-only checkpoint registration drift")
        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-J checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-J workflow invocation/131-I ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-J source or structural boundary unavailable")
    return tuple(failures)


def _arch131_paper_intent_bridge_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (repo_root / "src/trading_bot/review_paper/intent_bridge.py").read_text(
                encoding="utf-8"
            )
        )
        # Freeze every mapping, exact type guard, timestamp guard, and explicit
        # identity parameter. Whole-module coverage also forbids extra helpers,
        # dynamic calls, imports, logging, or module-level effects.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "48579d59a3940db668d2381b87a2ff63b02327f7f1bfca8d823926b78519054a"
        ):
            failures.append("131-I exact mapping/type/time/identity boundary drift")
        allowed_imports = {
            "__future__": {"annotations"},
            "uuid": {"UUID"},
            "trading_bot.execution.models": {"ExecutionInstruction"},
            "trading_bot.review_paper.models": {"ReviewPaperIntent"},
            "trading_bot.risk.models": {"RiskDecision", "RiskOutcome"},
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                failures.append("131-I unreviewed import/effect surface")
            elif isinstance(node, ast.ImportFrom):
                if (
                    node.level != 0
                    or node.module not in allowed_imports
                    or any(
                        name.asname is not None
                        or name.name not in allowed_imports[node.module]
                        for name in node.names
                    )
                ):
                    failures.append("131-I unreviewed import/effect surface")
            elif isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in {
                    "type",
                    "TypeError",
                    "ValueError",
                    "tuple",
                    "ReviewPaperIntent",
                }:
                    failures.append("131-I unreviewed call/effect surface")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-paper-intent-bridge"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1:
            failures.append("131-I source-only registration missing")
        else:
            fields = {item.arg: item.value for item in registrations[0].keywords}
            for field in ("preflight", "execute"):
                value = fields.get(field)
                if not isinstance(value, ast.Constant) or value.value is not None:
                    failures.append("131-I checkpoint has host/effect capability")
            check = fields.get("authority_check")
            if (
                not isinstance(check, ast.Name)
                or check.id != "_arch131_paper_intent_bridge_authority_check"
            ):
                failures.append("131-I authority registration drift")
        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-I checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-I workflow invocation/131-H ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-I source or structural boundary unavailable")
    return tuple(failures)


def _arch131_paper_operator_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = list(_arch131_agentic_account_authority_check(repo_root))
    failures.extend(_arch131_windows_oauth_authority_check(repo_root))
    try:
        source = (repo_root / "src/trading_bot/robinhood_paper_operator.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        # Freeze the complete composition, browser denial, path/source admission,
        # closed evidence schema and serialization boundary independent of format.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "d8ba2b1efdda9ea075e1cdf5b400742500bc4793af337351f7d35c566ed48b87"
        ):
            failures.append("131-H operator composition/redaction boundary drift")
        status_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_git"
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "status"
        ]
        if len(status_calls) != 1 or tuple(
            argument.value if isinstance(argument, ast.Constant) else None
            for argument in status_calls[0].args[1:]
        ) != ("status", "--porcelain=v1", "--untracked-files=all"):
            failures.append("131-H source cleanliness arguments drift")
        cycle_tree = ast.parse(
            (repo_root / "src/trading_bot/robinhood_paper_cycle.py").read_text(
                encoding="utf-8"
            )
        )
        cycle_runs = [
            node
            for node in ast.walk(cycle_tree)
            if isinstance(node, ast.FunctionDef) and node.name == "run"
        ]
        if (
            len(cycle_runs) != 1
            or hashlib.sha256(
                ast.dump(cycle_runs[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "a86c598165ddb9334c771f6490571f46f102575202ff477208e92f1d65e04bed"
        ):
            failures.append("131-H post-review failure guard drift")
        for token in (
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        ):
            if token in source:
                failures.append("131-H forbidden mutation surface")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == "arch131-robinhood-paper-operator"
                for item in node.keywords
            )
        ]
        if len(registrations) != 1:
            failures.append("131-H source-only registration missing")
        else:
            fields = {item.arg: item.value for item in registrations[0].keywords}
            for field in ("preflight", "execute"):
                value = fields.get(field)
                if not isinstance(value, ast.Constant) or value.value is not None:
                    failures.append("131-H checkpoint has host/effect capability")
        spec = _checkpoint_specs()["arch131-robinhood-paper-operator"]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-H checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-H workflow ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-H source or structural boundary unavailable")
    return tuple(failures)


def _arch131_agentic_account_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = list(_arch131_direct_mcp_authority_check(repo_root))
    failures.extend(_arch131_mcp_schema_authority_check(repo_root))
    failures.extend(_arch131_paper_cycle_authority_check(repo_root))
    # Freeze the reviewed dispatch/result boundaries by AST, independent of formatting.
    expected_boundaries = {
        "create_robinhood_agentic_account_resolver": (
            "46c9aefd35d30a33144f9c5df8e38f73440ae160c46c70ac01d29d7e4aef6e3d"
        ),
        "_accounts_structured_result": (
            "85c5807dffab7b33a9863e5d568fbe309159188374c0d7274cd19b153cd6a17c"
        ),
        "_require_review_read_tools": (
            "fa32303576c5bde08977352c878113bb7c687ae62c0863499c4fb56f70b41ad6"
        ),
        "_structured_result": (
            "d915278f59306fd2f4037859cbfa24e66886b96d9b79dd7fc71ee0eff87bba83"
        ),
        "review_equity_order": (
            "89462d4a8178a599feb6eaf076aceb8dba57f3dbb026c630f654fb86f732441c"
        ),
        "get_equity_quotes": (
            "d7abf621e34cd63b373bc1315a85f2a75cd960c3bbd43ff2f4dabe3b7526b182"
        ),
        "get_equity_orders": (
            "79ea648678d31543e48877310ea0862583ca769c06c781dddaf214dd02e88e21"
        ),
        "_invoke": ("43928e96254633e219999afaafb132755b23cc489fe73cc38b702c76f515b24e"),
        "_call_tool_once": (
            "684a89f8028f3deb6f4a84753b0b7cbe77be2e40293368837f5eb0d8cd0d2105"
        ),
        "_get_accounts": (
            "67bdf9bcf91217f7bb07a595882b72e1aa4e9347b7610d257892bae9ed8f1575"
        ),
        "_request_once": (
            "5fb0c878f9ead1b967cb1e996824e12c36674abcbd84ea8edceae17ea3530816"
        ),
    }
    try:
        sdk_source = (
            repo_root / "src/trading_bot/robinhood_mcp/sdk_transport.py"
        ).read_text(encoding="utf-8")
        sdk_tree = ast.parse(sdk_source)
        for name, expected in expected_boundaries.items():
            nodes = [
                node
                for node in ast.walk(sdk_tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name
            ]
            if (
                len(nodes) != 1
                or hashlib.sha256(
                    ast.dump(nodes[0], include_attributes=False).encode("utf-8")
                ).hexdigest()
                != expected
            ):
                failures.append(f"131-G internal/public MCP boundary drift: {name}")
        public_functions = {
            node.name
            for node in sdk_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        }
        if public_functions != {
            "create_robinhood_oauth_factory",
            "create_robinhood_agentic_account_resolver",
        }:
            failures.append("131-G exposes an unreviewed public MCP function")
        for relative in (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "src/trading_bot/robinhood_mcp/__init__.py",
        ):
            source = (repo_root / relative).read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and node.name in {"get_accounts", "call_tool"}:
                    failures.append("131-G exposes a raw account/generic MCP tool")
            for token in (
                "place_equity_order",
                "cancel_equity_order",
                "place_option_order",
                "cancel_option_order",
                "exercise_option",
                "place_crypto_order",
                "cancel_crypto_order",
            ):
                if token in source:
                    failures.append(f"131-G exposes forbidden tool: {token}")
            if relative.endswith("account_resolution.py"):
                names = _qualified_names(tree)
                if any(
                    name == "print"
                    or name == "open"
                    or name.endswith(
                        (
                            ".call_tool",
                            ".write_text",
                            ".write_bytes",
                            ".info",
                            ".debug",
                            ".warning",
                            ".error",
                        )
                    )
                    for name in names
                ):
                    failures.append(
                        "131-G resolver contains raw-tool/log/persistence exposure"
                    )
                if "rhs_account_number" in source:
                    failures.append(
                        "131-G resolver contains alternate account identity"
                    )
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == "arch131-robinhood-agentic-account"
                for item in node.keywords
            )
        ]
        if len(registrations) != 1:
            failures.append("131-G source-only registration missing")
        else:
            fields = {item.arg: item.value for item in registrations[0].keywords}
            for field in ("preflight", "execute"):
                value = fields.get(field)
                if not isinstance(value, ast.Constant) or value.value is not None:
                    failures.append("131-G checkpoint has host/effect capability")
        spec = _checkpoint_specs()["arch131-robinhood-agentic-account"]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-G checkpoint has host/effect capability")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-G source or structural boundary unavailable")
    return tuple(failures)


def _arch131_direct_mcp_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    relative = "src/trading_bot/robinhood_mcp/sdk_transport.py"
    try:
        source = (repo_root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        constants = {
            node.target.id: node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        expected_tools = (
            "get_equity_orders",
            "get_equity_quotes",
            "review_equity_order",
        )
        try:
            if ast.literal_eval(constants["_ALLOWED_TOOL_NAMES"]) != expected_tools:
                failures.append("Architecture 131-E direct MCP allowlist is not exact")
            if ast.literal_eval(constants["ROBINHOOD_TRADING_MCP_URL"]) != (
                "https://agent.robinhood.com/mcp/trading"
            ):
                failures.append("Architecture 131-E Robinhood endpoint drift")
        except (KeyError, ValueError, TypeError):
            failures.append("Architecture 131-E frozen constants are invalid")

        transport = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef)
                and node.name == "RobinhoodMcpStreamableHttpTransport"
            ),
            None,
        )
        if transport is None:
            failures.append("Architecture 131-E transport class is missing")
        else:
            public = {
                node.name
                for node in transport.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
            }
            expected_public = {
                "for_test",
                "review_equity_order",
                "get_equity_quotes",
                "get_equity_orders",
            }
            if public != expected_public:
                failures.append(
                    "Architecture 131-E public transport surface is not exact"
                )

        names = _qualified_names(tree)
        required = {
            "httpx2.AsyncClient",
            "streamable_http_client",
            "Client",
            "client.list_tools",
            "client.call_tool",
        }
        missing = sorted(required - names)
        if missing:
            failures.append(
                f"Architecture 131-E missing direct MCP bindings: {missing}"
            )
        for token in (
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        ):
            if token in source:
                failures.append(
                    f"Architecture 131-E exposes forbidden Robinhood tool: {token}"
                )
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 131-E direct MCP source unavailable")
    return tuple(failures)


def _arch131_performance_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    relative = "src/trading_bot/review_paper/performance.py"
    try:
        source = (repo_root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = _qualified_names(tree)
        forbidden = {
            "subprocess.run",
            "subprocess.Popen",
            "socket.socket",
            "requests.get",
            "requests.post",
            "httpx.get",
            "httpx.post",
            "urllib.request.urlopen",
        }
        if names & forbidden:
            failures.append("Architecture 131-D contains a network/effect boundary")
        for token in (
            "review_equity_order",
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "place_crypto_order",
        ):
            if token in source:
                failures.append(
                    f"Architecture 131-D references Robinhood effect tool: {token}"
                )
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 131-D performance source unavailable")
    return tuple(failures)


def _arch131_paper_cycle_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    relative = "src/trading_bot/robinhood_paper_cycle.py"
    try:
        source = (repo_root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = _qualified_names(tree)
        required = {
            "adapter.agentic_equity_orders",
            "self._adapter.review_market_order",
            "self._store.get_by_order_id",
            "self._store.record_market_review",
        }
        missing = sorted(required - names)
        if missing:
            failures.append(f"Architecture 131-C missing reviewed bindings: {missing}")
        forbidden = {
            "subprocess.run",
            "subprocess.Popen",
            "socket.socket",
            "requests.get",
            "requests.post",
            "httpx.get",
            "httpx.post",
            "urllib.request.urlopen",
        }
        if names & forbidden:
            failures.append("Architecture 131-C contains a concrete network boundary")
        for token in (
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        ):
            if token in source:
                failures.append(
                    f"Architecture 131-C exposes forbidden Robinhood tool: {token}"
                )
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 131-C paper cycle source unavailable")
    return tuple(failures)


def _arch131_mcp_schema_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    relative = "src/trading_bot/robinhood_mcp/adapter.py"
    try:
        source = (repo_root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        protocol = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef)
                and node.name == "RobinhoodReviewReadTransport"
            ),
            None,
        )
        if protocol is None:
            failures.append("Architecture 131-B transport protocol is missing")
        else:
            methods = {
                node.name for node in protocol.body if isinstance(node, ast.FunctionDef)
            }
            expected = {
                "review_equity_order",
                "get_equity_quotes",
                "get_equity_orders",
            }
            if methods != expected:
                failures.append(
                    "Architecture 131-B transport surface is not exact allowlist"
                )
        names = _qualified_names(tree)
        forbidden = {
            "subprocess.run",
            "subprocess.Popen",
            "socket.socket",
            "requests.get",
            "requests.post",
            "httpx.get",
            "httpx.post",
            "urllib.request.urlopen",
        }
        if names & forbidden:
            failures.append("Architecture 131-B contains a concrete network boundary")
        for token in (
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        ):
            if token in source:
                failures.append(
                    f"Architecture 131-B exposes forbidden Robinhood tool: {token}"
                )
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 131-B adapter source unavailable")
    return tuple(failures)


def _arch131_review_paper_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    names: set[str] = set()
    for relative in (
        "src/trading_bot/review_paper/models.py",
        "src/trading_bot/review_paper/store.py",
    ):
        path = repo_root / relative
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names.update(_qualified_names(tree))
        except (OSError, UnicodeError, SyntaxError):
            failures.append(f"Architecture 131 source unavailable: {relative}")
    forbidden = {
        "subprocess.run",
        "subprocess.Popen",
        "socket.socket",
        "requests.get",
        "requests.post",
        "httpx.get",
        "httpx.post",
        "urllib.request.urlopen",
    }
    if names & forbidden:
        failures.append("Architecture 131 phase A contains a network/effect boundary")
    return tuple(failures)


def _arch130_r8i_d1_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    path = repo_root / "scripts/d10_arch130_r8i_d1.py"
    try:
        text = path.read_text(encoding="utf-8")
        data = text.encode("utf-8")
        actual = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
        ).hexdigest()
        if actual != ARCH130_R8I_D1_SOURCE_BLOB_SHA1:
            failures.append("Architecture 130 D1 reconciler source drift")
        tree = ast.parse(text)
        names = _qualified_names(tree)
        forbidden = {
            "subprocess.run",
            "open_writable_authority_sqlite_connection",
            "run_personal_desktop_unattended_one_week_soak",
            "run_personal_desktop_unattended_market_data_capture",
        }
        if names & forbidden:
            failures.append("Architecture 130 D1 effect boundary appeared")
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 130 D1 reconciler source unavailable")
    return tuple(failures)


def _r8_halt_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    for name, expected in R8_HALT_SOURCE_PINS.items():
        try:
            text = (repo_root / name).read_text(encoding="utf-8")
            material = (
                ast.dump(ast.parse(text), include_attributes=False)
                if name.endswith(".py")
                else text
            )
            actual = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if actual != expected:
                failures.append(f"R8 halt frozen source drift: {name}")
        except (OSError, SyntaxError, UnicodeError):
            failures.append(f"R8 halt frozen source unavailable: {name}")
    try:
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        functions = _top_level_functions(tree)
        for name, expected in R8_HALT_RUNNER_PINS.items():
            material = ast.dump(functions[name], include_attributes=False)
            if hashlib.sha256(material.encode("utf-8")).hexdigest() != expected:
                failures.append(f"R8 halt runner composition drift: {name}")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                kw.arg == "name"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value == "arch128-r8-terminal-halt"
                for kw in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != R8_HALT_REGISTRATION_PIN
        ):
            failures.append("R8 halt registration drift")
    except (OSError, SyntaxError, UnicodeError, KeyError):
        failures.append("R8 halt runner source unavailable")
    return tuple(failures)


def _r8_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Freeze R8's public observer delegation, policy, and closed registration."""
    path = repo_root / "scripts" / "d10_arch128_r8_readonly.py"
    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        runner_tree = ast.parse(runner_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ("R8 source missing or invalid",)
    failures: list[str] = []
    functions = _top_level_functions(tree)
    preflight = functions.get("preflight")
    if set(functions) != {"_base", "_timestamp", "preflight"}:
        failures.append("R8 contains an unreviewed function surface")
    if preflight is None or ast.unparse(preflight.args) != "":
        failures.append("R8 requires zero-argument preflight")
    imports = {
        "from __future__ import annotations",
        "import re",
        "from datetime import UTC, datetime",
        "from typing import Final",
        "from scripts import d10_durable_wake_evidence_observe as observer",
        "from trading_bot.runtime.personal_desktop_d10_wake_evidence_log "
        "import MAX_D10_EVIDENCE_LOG_BYTES",
    }
    actual_imports = {
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    }
    if actual_imports != imports:
        failures.append("R8 contains unreviewed imports or direct host authority")
    allowed_calls = {
        "_base",
        "_timestamp",
        "type",
        "set",
        "dict",
        "any",
        "ValueError",
        "observer.observe",
        "EXPECTED_IDENTITY.items",
        "re.fullmatch",
        "datetime.fromisoformat",
        "parsed.isoformat",
        "parsed.isoformat().replace",
        "result.update",
    }
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    for call in calls:
        called = ast.unparse(call.func)
        if called not in allowed_calls:
            failures.append(f"R8 contains unreviewed authority call: {called}")
    observer_calls = [
        call for call in calls if ast.unparse(call.func) == "observer.observe"
    ]
    if (
        len(observer_calls) != 1
        or observer_calls[0].args
        or observer_calls[0].keywords
        or preflight is None
        or not any(
            isinstance(node, ast.Try)
            and isinstance(node.body[0], ast.Assign)
            and ast.unparse(node.body[0]) == "observation = observer.observe()"
            for node in preflight.body
        )
    ):
        failures.append("R8 must delegate exactly once to observer.observe()")
    for forbidden in (
        "ctypes",
        "subprocess",
        "os.system",
        "Popen",
        "guard.",
        "d10_arch128_r7",
        "scheduler_update",
        "_update_scheduler",
        "credential",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "RegisterTask",
        ".Run(",
    ):
        if forbidden in source:
            failures.append(f"R8 contains forbidden host/effect surface: {forbidden}")
    constants = {
        node.target.id: node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    expected_identity = {
        "schema": "personal-desktop-d10-evidence-observation/v1",
        "status": "OBSERVED",
        "deployment_id": "d2071f25-5a7c-5293-a28f-5b722c9917a2",
        "attestation_sha256": (
            "3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71"
        ),
        "soak_id": "30e31396-9f51-57ca-a480-d2a3e9cae4a0",
        "activation_utc": "2026-09-30T22:07:24.000000Z",
        "end_utc": "2026-10-07T22:07:24.000000Z",
        "evidence_path": (
            r"F:\AITradingBot\D10\evidence\wake-30e31396-9f51-57ca-a480-d2a3e9cae4a0.jsonl"
        ),
    }
    try:
        if ast.literal_eval(constants["EXPECTED_IDENTITY"]) != expected_identity:
            failures.append("R8 accepted R7 identity drift")
        if ast.literal_eval(constants["SCHEMA"]) != (
            "architecture-128-r8-readonly-first-wake/v1"
        ):
            failures.append("R8 schema drift")
    except (KeyError, ValueError, TypeError):
        failures.append("R8 frozen constants missing or invalid")
    effects = (
        "production_filesystem_mutation",
        "evidence_mutation",
        "scheduler_mutation",
        "lease_mutation",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    )
    expected_base = ast.parse(
        "def _base() -> dict[str, object]:\n    return "
        + repr(
            {
                "schema": "SCHEMA",
                "status": "BLOCKED",
                **dict.fromkeys(effects, "NOT_RUN"),
            }
        ).replace("'SCHEMA'", "SCHEMA")
    ).body[0]
    base = functions.get("_base")
    if base is None or ast.dump(base, include_attributes=False) != ast.dump(
        expected_base, include_attributes=False
    ):
        failures.append("R8 closed result effect fields drift")
    try:
        if (
            ast.literal_eval(constants["OBSERVER_EFFECT_FIELDS"])
            != effects[2:3] + effects[5:]
        ):
            failures.append("R8 accepted observer effect fields drift")
    except (KeyError, ValueError, TypeError):
        failures.append("R8 accepted observer effect fields invalid")
    comparisons = {
        ast.unparse(node)
        for node in ast.walk(preflight or tree)
        if isinstance(node, ast.Compare)
    }
    for required in (
        "type(observation) is not dict",
        "set(observation) != set(OBSERVATION_FIELDS)",
        "type(observation[field]) is not str",
        "observation[field] != expected",
        "observation[field] != 'NOT_RUN'",
        "type(observation['record_count']) is not int",
        "observation['record_count'] != 3",
        "type(observation['wake_count']) is not int",
        "observation['wake_count'] != 1",
        "observation['terminal'] is not False",
        "observation['terminal_kind'] is not None",
        "type(observation['last_outcome']) is not str",
        "observation['last_outcome'] not in ('COMPLETED', 'NO_ACTION')",
        "observation['last_stop_reason'] is not None",
        "observation['last_guard_reason'] is not None",
        "type(observation['evidence_byte_length']) is not int",
        "0 < observation['evidence_byte_length'] <= MAX_D10_EVIDENCE_LOG_BYTES",
        "type(observation['evidence_sha256']) is not str",
        "re.fullmatch('[0-9a-f]{64}', observation['evidence_sha256']) is None",
        "first > last",
    ):
        if required not in comparisons:
            failures.append(f"R8 acceptance policy drift: {required}")
    wrapper = _top_level_functions(runner_tree).get("_r8_preflight")
    if wrapper is None:
        failures.append("R8 runner missing read-only wrapper")
    else:
        wrapper_imports = [
            ast.unparse(node)
            for node in ast.walk(wrapper)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        if wrapper_imports != [
            "from scripts import d10_arch128_r8_readonly as admission"
        ]:
            failures.append("R8 wrapper contains unreviewed imports")
        for node in ast.walk(wrapper):
            if isinstance(node, ast.Call) and ast.unparse(node.func) not in {
                "admission.preflight",
                "_require_not_run",
                "primary.get",
                "type",
                "RuntimeError",
            }:
                failures.append("R8 wrapper contains direct host/effect authority")
        effects = (
            "production_filesystem_mutation",
            "evidence_mutation",
            "scheduler_mutation",
            "lease_mutation",
            "manual_task_start",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        )
        effect_calls = [
            node
            for node in ast.walk(wrapper)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "_require_not_run"
        ]
        try:
            if (
                len(effect_calls) != 1
                or ast.literal_eval(effect_calls[0].args[1]) != effects
            ):
                failures.append("R8 wrapper effect-field closure drift")
        except (IndexError, ValueError, TypeError):
            failures.append("R8 wrapper effect-field closure invalid")
    registrations = [
        node
        for node in ast.walk(runner_tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "CheckpointSpec"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "arch128-r8"
            for keyword in node.keywords
        )
    ]
    if len(registrations) != 1:
        failures.append("R8 registration missing or duplicated")
    else:
        keywords = {
            keyword.arg: ast.unparse(keyword.value)
            for keyword in registrations[0].keywords
        }
        for field, expected in (
            ("preflight", "_r8_preflight"),
            ("authority_check", "_r8_authority_check"),
            ("remote_branch", "'feature/d10c-durable-wake-evidence'"),
        ):
            if keywords.get(field) != expected:
                failures.append(f"R8 registration drift: {field}")
        if "execute" in keywords or "remote_head_env" in keywords:
            failures.append("R8 must have no execute or remote handoff surface")
    spec = _checkpoint_specs()["arch128-r8"]
    if spec.execute is not None or spec.preflight is not _r8_preflight:
        failures.append("R8 runtime registration must remain preflight-only")
    return tuple(failures)


def _r7_authority_check(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "scripts" / "d10_arch128_r7_readonly.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level_functions(tree)
    failures: list[str] = []

    preflight = functions.get("preflight")
    if preflight is None:
        failures.append("R7 read-only source missing preflight")
        return tuple(failures)

    names = _qualified_names(preflight)
    for required in (
        "r4c.observe_post",
        "r4w.WindowsArch128ReadOnlyReader",
        "WindowsCngVerifier",
        "r3._observe_scheduler",
        "r4.NamespaceState.COMPLETE",
    ):
        if required not in names:
            failures.append(f"R7 read-only source missing binding: {required}")

    for forbidden in (
        "WindowsArch128StagingBackend",
        "WindowsActivationLeaseBackend",
        "create_file",
        "publish_create_only",
        "rename_fixed_step",
        "RegisterTask",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "_update_scheduler",
        "_interactive_credential",
        "subprocess.run",
    ):
        if forbidden in source:
            failures.append(f"R7 read-only source contains effect surface: {forbidden}")

    protected_path = repo_root / "scripts" / "d10_arch128_r7_protected.py"
    if not protected_path.is_file():
        failures.append("R7 protected-dispatch source missing")
        return tuple(failures)
    protected_source = protected_path.read_text(encoding="utf-8")
    protected_tree = ast.parse(protected_source, filename=str(protected_path))
    protected_functions = _top_level_functions(protected_tree)
    dispatch = protected_functions.get("_dispatch")
    if dispatch is None:
        failures.append("R7 protected-dispatch source missing _dispatch")
    else:
        dispatch_source = ast.get_source_segment(protected_source, dispatch) or ""
        for required in (
            "EXECUTE_FLAG",
            "AUTH_ENV",
            "AUTH_VALUE",
            "r6.ReactivationOperator",
            "execute_r7=True",
        ):
            if required not in dispatch_source:
                failures.append(f"R7 protected dispatch missing: {required}")

    for forbidden in (
        "ctypes",
        "subprocess",
        "WindowsActivationLeaseBackend",
        "WindowsDeploymentBackend",
        "CreateFileW",
        "RegisterTask",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "_update_scheduler",
        "_interactive_credential",
    ):
        if forbidden in protected_source:
            failures.append(
                f"R7B dispatch contains premature host authority surface: {forbidden}"
            )

    failures.extend(_r7c_authority_check(repo_root))
    failures.extend(_r7d_authority_check(repo_root))
    return tuple(failures)


def _r7c_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Allow native bindings only in the separately reviewed fixed R7C surfaces."""
    import re

    failures = []
    sources = {}
    for name in ("d10_arch128_r7_windows.py", "d10_arch128_r7_observation.py"):
        path = repo_root / "scripts" / name
        if not path.is_file():
            failures.append(f"R7C source missing: {name}")
            continue
        source = path.read_text(encoding="utf-8")
        sources[name] = source
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = (
                    (node.module,)
                    if isinstance(node, ast.ImportFrom)
                    else tuple(alias.name for alias in node.names)
                )
                if isinstance(node, ast.ImportFrom) and node.module in (
                    "scripts",
                    "trading_bot.runtime",
                ):
                    modules = tuple(
                        node.module + "." + alias.name for alias in node.names
                    )
                allowed_imports = {
                    "__future__",
                    "ctypes",
                    "subprocess",
                    "getpass",
                    "json",
                    "os",
                    "re",
                    "sys",
                    "weakref",
                    "ntpath",
                    "collections.abc",
                    "concurrent.futures",
                    "dataclasses",
                    "datetime",
                    "pathlib",
                    "uuid",
                    "scripts.d10_arch128_r4_orchestration",
                    "scripts.d10_arch128_r4_windows",
                    "scripts.d10_arch128_r6_reactivation",
                    "scripts.d10_arch128_r7_observation",
                    "scripts.d10_python_substrate_windows",
                    "scripts.run_personal_desktop_d10_launch_guard",
                    "scripts.d10_protected_deployment",
                    "scripts.d10_protected_deployment_windows",
                    "scripts.d10_protected_replacement_windows",
                    "trading_bot.runtime.personal_desktop_d10_activation_lease",
                    "trading_bot.runtime.personal_desktop_d10_wake_evidence_log",
                    "trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract",
                }
                for module in modules:
                    if module not in allowed_imports:
                        failures.append(f"R7C unreviewed import: {module}")
            if isinstance(node, ast.Call):
                called = ast.unparse(node.func)
                if called in (
                    "eval",
                    "exec",
                    "__import__",
                    "open",
                    "os.system",
                    "subprocess.run",
                    "subprocess.call",
                ) or called.endswith(
                    (
                        ".unlink",
                        ".rmdir",
                        ".rmtree",
                        ".write_bytes",
                        ".write_text",
                        ".rename",
                        ".replace",
                    )
                ):
                    # datetime.replace is the fixed exact-second source clock.
                    if called != "datetime.now(UTC).replace":
                        failures.append(f"R7C unreviewed effect call: {called}")
                if called == "self._bind":
                    if (
                        len(node.args) < 2
                        or not isinstance(node.args[1], ast.Constant)
                        or node.args[1].value
                        not in (
                            "CreateFileW",
                            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                        )
                    ):
                        failures.append("R7C unreviewed native binding")
        for forbidden in (
            "DeleteFile",
            "ReplaceFile",
            "SetEndOfFile",
            "WriteFile",
            "FlushFileBuffers",
            "Start-ScheduledTask",
            "Enable-ScheduledTask",
            "schtasks",
            "RegisterTaskDefinition",
            "rollback(",
            "cleanup(",
            "retry(",
            "guard.main",
            "guard._run_second_stage",
        ):
            if forbidden in source:
                failures.append(f"R7C forbidden authority: {name}:{forbidden}")
    validation = sources.get("d10_arch128_r7_observation.py", "")
    for required in (
        "D10_WAKE_EVIDENCE_ROOT",
        "ntpath.dirname(path) != str(D10_WAKE_EVIDENCE_ROOT)",
        "r6.derive_reactivation_plan",
        "guard.TRADING_EVIDENCE_FILE_ACCESS",
        "item.aces != aces",
        "item.size != 0",
        "item.links != 1",
        "PREDECESSOR_XML_SHA256",
        "scheduler_semantics(spec)",
    ):
        if required not in validation:
            failures.append(f"R7C exact validation missing: {required}")
    host = sources.get("d10_arch128_r7_windows.py", "")
    for required in (
        "class WindowsR7Boundaries:",
        "class WindowsR7EvidenceBackend(WindowsDeploymentBackend):",
        'TRADING_PID_ENV = "AI_TRADING_BOT_ARCH128_R7_TRADING_PID"',
        "d10_arch128_r7_scheduler_update.ps1",
        "d10_arch128_r3_scheduler_observe.ps1",
        "r4c.observe_r7_complete",
        "substrate.probe_trading_evidence_append_open",
        "guard.TRADING_EVIDENCE_FILE_ACCESS",
        "observation.require_plan",
        "observation.require_evidence_path",
        "observation.require_scheduler",
        "WindowsActivationLeaseBackend()",
        'payload = b""',
        'credential.password = ""',
        'self._phase = "PROBE_ATTEMPTED"',
        'self._require_phase("PROBED")',
        'self._evidence.create_file(path, b"")',
        "sys.stdin is not sys.__stdin__",
    ):
        if required not in host:
            failures.append(f"R7C fixed binding missing: {required}")
    if host:
        tree = ast.parse(host)
        classes = {
            node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
        }
        boundary = classes.get("WindowsR7Boundaries")
        methods = (
            {}
            if boundary is None
            else {
                node.name: node
                for node in boundary.body
                if isinstance(node, ast.FunctionDef)
            }
        )
        for method in (
            "observe_admission",
            "create_empty_evidence",
            "observe_evidence",
            "probe_trading_append_open",
            "acquire_scheduler_credential",
            "update_scheduler",
            "read_scheduler",
            "publish_lease",
        ):
            if method not in methods:
                failures.append(f"R7C fixed R6 boundary missing: {method}")
        factory = _top_level_functions(tree).get("host_factory")
        if (
            factory is None
            or factory.args.args
            or factory.args.kwonlyargs
            or factory.args.vararg
            or factory.args.kwarg
        ):
            failures.append("R7C factory accepts caller authority")
        transport = _top_level_functions(tree).get("_transport")
        if (
            transport is None
            or "helper not in (OBSERVE_HELPER, UPDATE_HELPER)"
            not in ast.get_source_segment(host, transport)
        ):
            failures.append("R7C transport is not fixed")
    native_path = repo_root / "scripts" / "d10_python_substrate_windows.py"
    native_source = native_path.read_text(encoding="utf-8")
    probe = _top_level_functions(ast.parse(native_source)).get(
        "probe_trading_evidence_append_open"
    )
    probe_source = "" if probe is None else ast.get_source_segment(native_source, probe)
    for required in (
        "_trading_token(trading_pid)",
        "ImpersonateLoggedOnUser",
        "RevertToSelf",
        "CreateFileW",
        "r6.guard.TRADING_EVIDENCE_FILE_ACCESS",
        "FILE_SHARE_READ",
        "OPEN_EXISTING",
        "FILE_FLAG_OPEN_REPARSE_POINT | r6.guard.FILE_FLAG_WRITE_THROUGH",
        '_check(revert(), "RevertToSelf")',
        "owned.callback(_close, token)",
        "_close(int(handle))",
    ):
        if required not in probe_source:
            failures.append(f"R7C Trading zero-write binding missing: {required}")
    for forbidden in (
        "WriteFile",
        "FlushFileBuffers",
        "SetEndOfFile",
        "DeleteFile",
        "MoveFile",
        "ReplaceFile",
    ):
        if forbidden in probe_source:
            failures.append(f"R7C Trading probe has forbidden effect: {forbidden}")
    helper_path = repo_root / "scripts" / "d10_arch128_r7_scheduler_update.ps1"
    helper = helper_path.read_text(encoding="utf-8") if helper_path.is_file() else ""
    assignments = re.findall(
        r"(?m)^\s*(\$(?:definition|trigger|action)[.][\w.]+)\s*=", helper
    )
    if assignments != [
        "$trigger.StartBoundary",
        "$trigger.EndBoundary",
        "$definition.Settings.Enabled",
    ]:
        failures.append("R7C scheduler mutations exceed frozen three-field scope")
    for required in (
        "arch128-r7-scheduler-update/v1",
        "activation_utc,password",
        "Read-FixedTask",
        "State -ne 1",
        "enabled = $false",
        "8d592a71258529fa88cd85866b0be1e91cf407d91e9acf5891a1bd82c0bf09b0",
        "$definition, 4,",
        "$callAttempted = $true",
        "$activation.AddDays(7)",
    ):
        if required not in helper:
            failures.append(f"R7C scheduler helper missing: {required}")
    for forbidden in (
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        ".Run(",
        "NewTask",
        "TASK_CREATE",
        "Remove-Item",
        "schtasks",
        "Start-Process",
    ):
        if forbidden in helper:
            if forbidden != "TASK_CREATE" or "TASK_CREATE" in re.sub(
                r"(?m)#.*$", "", helper
            ):
                failures.append(
                    f"R7C scheduler helper forbidden authority: {forbidden}"
                )
    if re.search(
        r"[.]\s*(?:Run|CreateTask)\s*[(]|Invoke-Expression|Invoke-Command|[&]", helper
    ):
        failures.append("R7C scheduler contains arbitrary invocation or manual start")
    if helper.count("RegisterTaskDefinition(") != 1:
        failures.append("R7C scheduler mutation must be a single fixed TASK_UPDATE")
    if host:
        host_functions = _top_level_functions(ast.parse(host))
        transport = host_functions.get("_transport")
        launches = [
            node
            for node in ast.walk(ast.parse(host))
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "subprocess.Popen"
        ]
        expected_command = ast.parse(
            "(POWERSHELL, '-NoProfile', '-NonInteractive', "
            "'-ExecutionPolicy', 'Bypass', '-File', str(helper))",
            mode="eval",
        ).body
        if (
            len(launches) != 1
            or not launches[0].args
            or ast.dump(launches[0].args[0]) != ast.dump(expected_command)
            or transport is None
            or launches[0].lineno < transport.lineno
            or launches[0].lineno > transport.end_lineno
        ):
            failures.append("R7C process transport exceeds the fixed helper command")
        for node in ast.walk(ast.parse(host)):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in (
                "ctypes.CDLL",
                "os.open",
                "os.mkdir",
                "os.makedirs",
                "WindowsDeploymentBackend",
            ):
                failures.append(
                    "R7C contains unreviewed direct native/filesystem authority"
                )
    if host:
        console = _top_level_functions(ast.parse(host)).get(
            "_require_interactive_console"
        )
        dll_calls = [
            node
            for node in ast.walk(ast.parse(host))
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "ctypes.WinDLL"
        ]
        if (
            len(dll_calls) != 1
            or console is None
            or dll_calls[0].lineno < console.lineno
            or dll_calls[0].lineno > console.end_lineno
            or ast.literal_eval(dll_calls[0].args[0])
            != r"C:\Windows\System32\kernel32.dll"
        ):
            failures.append(
                "R7C native DLL binding exceeds the fixed read-only console proof"
            )
    if probe is not None:
        calls = [node for node in ast.walk(probe) if isinstance(node, ast.Call)]
        opens = [
            node
            for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == "create"
        ]
        expected_open = [
            "plan.evidence_path",
            "r6.guard.TRADING_EVIDENCE_FILE_ACCESS",
            "FILE_SHARE_READ",
            "None",
            "OPEN_EXISTING",
            "FILE_FLAG_OPEN_REPARSE_POINT | r6.guard.FILE_FLAG_WRITE_THROUGH",
            "None",
        ]
        if (
            len(opens) != 1
            or [ast.unparse(arg) for arg in opens[0].args] != expected_open
        ):
            failures.append("R7C Trading open policy is not exact")
        results = [
            node
            for node in calls
            if ast.unparse(node.func) == "r6.TradingOpenObservation"
        ]
        if len(results) != 1 or ast.unparse(results[0].args[-1]) != "0":
            failures.append("R7C Trading probe does not construct zero bytes written")
    return tuple(failures)


def _r7d_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Constrain the runner to reviewed dispatch and result classification."""
    path = repo_root / "scripts" / "checkpoint_runner.py"
    if not path.is_file():
        return ("R7D runner source missing",)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wrapper = _top_level_functions(tree).get("_r7_execute")
    if wrapper is None:
        return ("R7D runner missing _r7_execute",)
    failures: list[str] = []
    imports = [
        ast.unparse(node)
        for node in ast.walk(wrapper)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    if imports != [
        "from scripts import d10_arch128_r7_protected as r7_protected",
        "from scripts import d10_arch128_r7_windows as r7_windows",
    ]:
        failures.append("R7D runner imports are not the reviewed composition")
    calls = [node for node in ast.walk(wrapper) if isinstance(node, ast.Call)]
    dispatches = [
        node for node in calls if ast.unparse(node.func) == "r7_protected._dispatch"
    ]
    if (
        len(dispatches) != 1
        or [ast.unparse(arg) for arg in dispatches[0].args]
        != [
            "(r7_protected.EXECUTE_FLAG,)",
            "dict(os.environ)",
            "r7_windows.host_factory",
        ]
        or dispatches[0].keywords
    ):
        failures.append("R7D runner dispatch composition is not exact")
    effect_guards = [
        node for node in calls if ast.unparse(node.func) == "_require_not_run"
    ]
    expected_closed = (
        "production_filesystem_mutation",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    )
    if (
        len(effect_guards) != 1
        or len(effect_guards[0].args) != 2
        or ast.unparse(effect_guards[0].args[0]) != "primary"
        or ast.literal_eval(effect_guards[0].args[1]) != expected_closed
        or effect_guards[0].keywords
    ):
        failures.append("R7D runner forbidden-effect guard is not exact")
    allowed_calls = {
        "r7_protected._dispatch",
        "dict",
        "type",
        "_require_not_run",
        "primary.get",
        "RuntimeError",
        "any",
        "all",
        "completion.items",
        "blocked.items",
    }
    for node in calls:
        called = ast.unparse(node.func)
        if called not in allowed_calls:
            failures.append(f"R7D runner contains unreviewed authority call: {called}")
    for node in ast.walk(wrapper):
        if isinstance(node, (ast.For, ast.While, ast.Try, ast.With)):
            failures.append("R7D runner contains unreviewed retry/recovery flow")
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(
            node.ctx, ast.Store
        ):
            failures.append("R7D runner mutates external state")
    allowed_bindings = {
        "r7_protected._dispatch",
        "r7_protected.EXECUTE_FLAG",
        "r7_protected.SCHEMA",
        "r7_windows.host_factory",
        "os.environ",
    }
    for name in _qualified_names(wrapper):
        if name.startswith(("r7_protected.", "r7_windows.", "os.")):
            if name not in allowed_bindings:
                failures.append(f"R7D runner bypasses reviewed interlock: {name}")

    expected_completion = {
        "stage": "COMPLETE",
        "authorization": "ACCEPTED",
        "evidence_provision": "CALL_RETURNED",
        "scheduler_mutation": "CALL_RETURNED",
        "lease_publication": "PUBLISHED_VERIFIED",
        "reconciliation_required": False,
    }
    expected_blocked = {
        "stage": "EXECUTION_INTERLOCK",
        "authorization": "NOT_ACCEPTED",
        "evidence_provision": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "lease_publication": "NOT_RUN",
        "reconciliation_required": False,
    }
    for name, expected in (
        ("completion", expected_completion),
        ("blocked", expected_blocked),
    ):
        values = [
            node.value
            for node in ast.walk(wrapper)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            )
        ]
        if len(values) != 1 or ast.literal_eval(values[0]) != expected:
            failures.append(f"R7D runner {name} evidence contract changed")

    wrapper_source = ast.unparse(wrapper)
    for required in (
        "primary.get('automatic_retry') is not False",
        "primary.get('automatic_rollback') is not False",
        "primary.get('automatic_cleanup') is not False",
        "type(primary.get('reconciliation_required')) is not bool",
        "if status == 'PASS':",
        "any((primary.get(field) != value for field, value in completion.items()))",
        "elif status == 'BLOCKED' and all",
        "disposition = 'CONFIRMED'",
        "disposition = 'NOT_STARTED'",
        "disposition = 'MAY_HAVE_OCCURRED'",
    ):
        if required not in wrapper_source:
            failures.append(f"R7D runner missing conservative result guard: {required}")

    expected_classification = ast.parse(
        """
if status == "PASS":
    if any(primary.get(field) != value for field, value in completion.items()):
        raise RuntimeError("R7 PASS lacked exact verified completion evidence")
    disposition = "CONFIRMED"
elif status == "BLOCKED" and all(
    primary.get(field) == value for field, value in blocked.items()
):
    disposition = "NOT_STARTED"
else:
    disposition = "MAY_HAVE_OCCURRED"
"""
    ).body[0]
    classifications = [
        node
        for node in wrapper.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "status == 'PASS'"
    ]
    assignments = [
        node
        for node in ast.walk(wrapper)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "disposition"
            for target in node.targets
        )
    ]
    if (
        len(classifications) != 1
        or ast.dump(classifications[0]) != ast.dump(expected_classification)
        or len(assignments) != 3
    ):
        failures.append("R7D runner effect classification is not conservative")

    registrations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "CheckpointSpec"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "arch128-r7"
            for keyword in node.keywords
        )
    ]
    if len(registrations) != 1 or not any(
        keyword.arg == "execute" and ast.unparse(keyword.value) == "_r7_execute"
        for keyword in registrations[0].keywords
    ):
        failures.append("R7D runner registration is not the reviewed wrapper")
    if _checkpoint_specs()["arch128-r7"].execute is not _r7_execute:
        failures.append("R7D R7 execute wrapper is not registered")

    for filename, expected in (
        (
            "d10_arch128_r7_protected.py",
            {
                "EXECUTE_FLAG": "--execute-reviewed-r7-protected-activation",
                "AUTH_ENV": "AI_TRADING_BOT_ARCH128_R7_AUTHORIZATION",
                "AUTH_VALUE": "ARCH128_R7_PROTECTED_ACTIVATION_AUTHORIZED",
            },
        ),
        (
            "d10_arch128_r7_windows.py",
            {
                "TRADING_PID_ENV": "AI_TRADING_BOT_ARCH128_R7_TRADING_PID",
            },
        ),
    ):
        module = ast.parse(
            (repo_root / "scripts" / filename).read_text(encoding="utf-8")
        )
        constants = {}
        for node in module.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                constants[node.target.id] = node.value
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value
        for name, value in expected.items():
            literal = constants.get(name)
            if not isinstance(literal, ast.Constant) or literal.value != value:
                failures.append(f"R7D reviewed interlock changed: {name}")
    return tuple(failures)


def _parent_acl_authority_check(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "scripts" / "d10_arch128_parent_acl_repair.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level_functions(tree)
    failures: list[str] = []

    required_functions = {
        "_read_only",
        "_repair_once",
        "_dispatch",
        "_open_parent_for_acl",
        "main",
    }
    missing_functions = sorted(required_functions - set(functions))
    if missing_functions:
        failures.append(f"missing functions: {missing_functions}")
        return tuple(failures)

    readonly_names = _qualified_names(functions["_read_only"])
    for forbidden in (
        "_open_parent_for_acl",
        "apply_security_policy",
        "_repair_once",
    ):
        if forbidden in readonly_names:
            failures.append(f"read-only mode references mutation symbol: {forbidden}")

    repair_names = _qualified_names(functions["_repair_once"])
    for required in (
        "_observe_exact_drift",
        "_open_parent_for_acl",
        "apply_security_policy",
        "_target_policy",
        "_observe_exact_target",
    ):
        if required not in repair_names:
            failures.append(f"repair mode missing fixed binding: {required}")

    dispatch_source = ast.get_source_segment(source, functions["_dispatch"]) or ""
    for required in ("READ_ONLY_FLAG", "EXECUTE_FLAG", "AUTH_ENV", "AUTH_VALUE"):
        if required not in dispatch_source:
            failures.append(f"dispatch interlock missing: {required}")

    required_text = (
        "S-1-5-21-1397534616-3988210162-180023805-1005",
        "DRIFT_FLAGS: Final = 3",
        "_WRITE_DAC",
        "_WRITE_OWNER",
        "apply_security_policy(handle, _target_policy())",
        "STOPPED_AFTER_APPLY",
        "recursive_acl_mutation",
        "d10_child_mutation",
    )
    for required in required_text:
        if required not in source:
            failures.append(f"required repair invariant missing: {required}")

    for forbidden in (
        "os.walk",
        "rglob",
        "glob(",
        "SetNamedSecurityInfo",
        "icacls",
        "takeown",
        "RegisterTask",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "rename_fixed_step",
        "create_directory",
        "create_file",
        "publish_activation",
    ):
        if forbidden in source:
            failures.append(f"repair contains forbidden authority surface: {forbidden}")

    # Importing this source is deliberately side-effect free. Resolve the shared
    # fixed path from the reviewed contract rather than requiring a duplicated
    # raw literal in the repair module.
    from scripts import d10_arch128_parent_acl_repair as repair

    if repair.D10_PARENT != r"F:\AITradingBot":
        failures.append(f"fixed parent differs: {repair.D10_PARENT!r}")

    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    runner_source = runner_path.read_text(encoding="utf-8")
    runner_tree = ast.parse(runner_source, filename=str(runner_path))
    runner_functions = _top_level_functions(runner_tree)
    parent_execute = runner_functions.get("_parent_acl_execute")
    if parent_execute is None:
        failures.append("runner missing _parent_acl_execute")
    else:
        execute_names = _qualified_names(parent_execute)
        for required in ("repair._dispatch", "repair.EXECUTE_FLAG", "os.environ"):
            if required not in execute_names:
                failures.append(
                    "runner parent execute missing reviewed dispatch binding: "
                    f"{required}"
                )
        for forbidden in (
            "repair._repair_once",
            "repair._open_parent_for_acl",
            "apply_security_policy",
        ):
            if forbidden in execute_names:
                failures.append(
                    f"runner parent execute bypasses reviewed interlock: {forbidden}"
                )

    return tuple(failures)


def _require_not_run(
    result: Mapping[str, object],
    fields: Sequence[str],
) -> None:
    for field in fields:
        if result.get(field) != "NOT_RUN":
            raise RuntimeError(
                f"checkpoint result reported unexpected effect for {field}: "
                f"{result.get(field)!r}"
            )


def _parent_acl_preflight() -> dict[str, object]:
    from scripts import d10_arch128_parent_acl_repair as repair

    primary = repair._read_only()
    _require_not_run(
        primary,
        (
            "acl_mutation",
            "recursive_acl_mutation",
            "d10_child_mutation",
            "scheduler_mutation",
            "activation",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )
    return {
        "status": primary.get("status"),
        "primary": primary,
        "diagnostics": {},
    }


def _parent_acl_execute() -> dict[str, object]:
    from scripts import d10_arch128_parent_acl_repair as repair

    primary = repair._dispatch((repair.EXECUTE_FLAG,), dict(os.environ))
    _require_not_run(
        primary,
        (
            "recursive_acl_mutation",
            "d10_child_mutation",
            "scheduler_mutation",
            "activation",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )

    status = primary.get("status")
    if status == "PASS":
        if primary.get("acl_mutation") != "EXACT_PARENT_POLICY_APPLIED_AND_VERIFIED":
            raise RuntimeError(
                "parent ACL PASS lacked exact verified mutation evidence"
            )
        disposition = "CONFIRMED"
    elif status == "BLOCKED":
        if primary.get("acl_mutation") != "NOT_RUN":
            raise RuntimeError("blocked parent ACL execution reported a mutation")
        disposition = "NOT_STARTED"
    else:
        disposition = "MAY_HAVE_OCCURRED"

    return {
        "status": status,
        "primary": primary,
        "effect_disposition": disposition,
    }


def _r4_execute() -> dict[str, object]:
    from scripts import d10_arch128_r4_operator as operator

    primary = operator._dispatch((operator.EXECUTE_FLAG,), dict(os.environ))
    _require_not_run(
        primary,
        (
            "scheduler_mutation",
            "activation",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )

    status = primary.get("status")
    mutation = primary.get("production_filesystem_mutation")
    rename_1 = primary.get("rename_1")
    rename_2 = primary.get("rename_2")

    if status == "PASS":
        if (
            mutation != "REPLACEMENT_COMPLETE_AND_VERIFIED"
            or rename_1 != "SUCCESS"
            or rename_2 != "SUCCESS"
        ):
            raise RuntimeError(
                "R4 PASS lacked exact verified replacement completion evidence"
            )
        disposition = "CONFIRMED"
    elif status == "BLOCKED":
        if mutation != "NOT_RUN" or rename_1 != "NOT_RUN" or rename_2 != "NOT_RUN":
            raise RuntimeError("blocked R4 execution reported filesystem mutation")
        disposition = "NOT_STARTED"
    elif (
        status == "STOPPED"
        and mutation == "NOT_STARTED"
        and rename_1 == "NOT_RUN"
        and rename_2 == "NOT_RUN"
    ):
        disposition = "NOT_STARTED"
    else:
        disposition = "MAY_HAVE_OCCURRED"

    return {
        "status": status,
        "primary": primary,
        "effect_disposition": disposition,
    }


def _r5_effect_fields() -> tuple[str, ...]:
    return (
        "activation",
        "source_launch",
        "scheduler",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    )


def _r5_substrate_preflight() -> dict[str, object]:
    from scripts import d10_arch128_r4_replacement as r4
    from scripts import d10_python_substrate_harness as h
    from scripts import d10_python_substrate_windows as w

    raw_pid = os.environ.get(R5_TRADING_PID_ENV, "")
    if not raw_pid.isascii() or not raw_pid.isdigit() or int(raw_pid) <= 0:
        primary = {
            "status": "BLOCKED",
            "reason": "trading_pid_interlock_not_exact",
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
        return {"status": "BLOCKED", "primary": primary}

    try:
        transcript_bytes = h.collect(w.WindowsCollector(int(raw_pid)))
        transcript = json.loads(transcript_bytes.decode("utf-8"))
        signed = transcript.get("signed_a123")
        if (
            type(signed) is not dict
            or signed.get("attestation_sha256")
            != r4.NEW_IDENTITY.unsigned_attestation_sha256
            or signed.get("python") != str(R5_PRODUCTION_PYTHON)
            or signed.get("version") != "3.14.3"
        ):
            raise RuntimeError("r5_substrate_signed_identity_drift")
        primary = {
            "status": "PASS",
            "production_python_substrate": "PASS",
            "trading_pid": int(raw_pid),
            "transcript_sha256": hashlib.sha256(transcript_bytes).hexdigest(),
            "transcript_byte_length": len(transcript_bytes),
            "substrate_transcript": transcript,
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
    except Exception as exc:
        primary = {
            "status": "BLOCKED",
            "reason": type(exc).__name__,
            "detail": str(exc),
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }

    _require_not_run(primary, _r5_effect_fields())
    return {"status": primary.get("status"), "primary": primary}


def _r5_trading_preflight() -> dict[str, object]:
    helper = Path(__file__).resolve().with_name("d10_arch128_r5_trading_child.py")
    command = (
        str(R5_PRODUCTION_PYTHON),
        "-I",
        "-S",
        "-B",
        "-X",
        f"pycache_prefix={R5_PYCACHE_PREFIX}",
        str(helper),
    )
    try:
        completed = subprocess.run(
            command,
            input=b"",
            capture_output=True,
            cwd=str(_REPOSITORY_ROOT),
            env={"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        primary = {
            "status": "BLOCKED",
            "reason": type(exc).__name__,
            "detail": "r5_trading_child_transport_failed",
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
        return {"status": "BLOCKED", "primary": primary}

    if len(completed.stdout) > 2 * 1024 * 1024 or len(completed.stderr) > 64 * 1024:
        primary = {
            "status": "BLOCKED",
            "reason": "r5_trading_child_output_bound",
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
        return {"status": "BLOCKED", "primary": primary}

    try:
        primary = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, ValueError):
        primary = {
            "status": "BLOCKED",
            "reason": "r5_trading_child_json_invalid",
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
        return {"status": "BLOCKED", "primary": primary}

    if type(primary) is not dict:
        raise RuntimeError("R5 Trading child result type differs")
    _require_not_run(primary, _r5_effect_fields())
    if primary.get("second_stage_launch_trap") != "NOT_CALLED":
        raise RuntimeError("R5 Trading child reported second-stage launch")
    status = primary.get("status")
    if (completed.returncode == 0) != (status == "PASS"):
        raise RuntimeError("R5 Trading child exit/status disagree")
    if completed.returncode not in (0, 1):
        raise RuntimeError("R5 Trading child exit code differs")
    return {"status": status, "primary": primary}


def _r4_preflight() -> dict[str, object]:
    from scripts import d10_arch128_parent_acl_repair as repair
    from scripts import d10_arch128_r4_operator as operator

    primary = operator._read_only_preflight()
    _require_not_run(
        primary,
        (
            "production_filesystem_mutation",
            "rename_1",
            "rename_2",
            "scheduler_mutation",
            "activation",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )

    diagnostics: dict[str, object] = {}
    if (
        primary.get("status") != "PASS"
        and primary.get("detail") == "d10_parent_policy_mismatch"
    ):
        parent = repair._read_only()
        _require_not_run(
            parent,
            (
                "acl_mutation",
                "recursive_acl_mutation",
                "d10_child_mutation",
                "scheduler_mutation",
                "activation",
                "source_launch",
                "provider",
                "Paper-v2",
                "broker",
                "live",
            ),
        )
        diagnostics["parent_acl"] = parent

    return {
        "status": primary.get("status"),
        "primary": primary,
        "diagnostics": diagnostics,
    }


def _r7_preflight() -> dict[str, object]:
    from scripts import d10_arch128_r7_readonly as admission

    primary = admission.preflight()
    _require_not_run(
        primary,
        (
            "production_filesystem_mutation",
            "evidence_provision",
            "scheduler_mutation",
            "lease_publication",
            "manual_task_start",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )
    return {"status": primary.get("status"), "primary": primary}


def _arch130_r8i_d1_preflight() -> dict[str, object]:
    from scripts import d10_arch130_r8i_d1 as d1

    primary = d1.preflight()
    if type(primary) is not dict:
        raise RuntimeError("Architecture 130 D1 result must be an exact dictionary")
    _require_not_run(primary, d1.CLOSED_EFFECTS)
    return {"status": primary.get("status"), "primary": primary}


def _r8_preflight() -> dict[str, object]:
    from scripts import d10_arch128_r8_readonly as admission

    primary = admission.preflight()
    if type(primary) is not dict:
        raise RuntimeError("R8 preflight result must be an exact dictionary")
    _require_not_run(
        primary,
        (
            "production_filesystem_mutation",
            "evidence_mutation",
            "scheduler_mutation",
            "lease_mutation",
            "manual_task_start",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )
    return {"status": primary.get("status"), "primary": primary}


def _r8_halt_preflight() -> dict[str, object]:
    from scripts import d10_arch128_r8_halt_diagnostic as diagnostic
    from scripts import d10_arch128_r8_halt_windows as windows
    from scripts import d10_arch128_r8_terminal_halt as halt

    primary = halt.preflight(windows.ReadOnlyWindowsHost())
    closed = all(primary.get(field) == "NOT_RUN" for field in halt.CLOSED_EFFECTS)
    closed = closed and primary.get("scheduler_mutation") == "NOT_RUN"
    passed = primary.get("status") == "PASS" and closed
    passed = (
        passed
        and primary.get("call_attempted") is False
        and primary.get("disposition") == "NOT_CALLED"
    )
    if passed:
        try:
            halt.require_snapshot(
                halt.Snapshot(
                    primary["evidence"], primary["lease"], primary["scheduler"]
                ),
                enabled=True,
            )
        except Exception:
            passed = False

    diagnostics: dict[str, object] = {}
    if passed:
        try:
            native = diagnostic.observe()
        except Exception:
            native = {
                "status": "BLOCKED",
                "reason": "diagnostic_transport_failed",
            }
        diagnostics["native_pre_call"] = native
        expected_native = {
            "schema": diagnostic.SCHEMA,
            "status": diagnostic.READY,
            "reason": None,
            "call_attempted": False,
            "scheduler_mutation": "NOT_RUN",
        }
        native_ready = type(native) is dict and all(
            type(native.get(key)) is type(value) and native.get(key) == value
            for key, value in expected_native.items()
        )
        native_ready = native_ready and type(native.get("scheduler")) is dict
        if native_ready:
            try:
                halt.require_scheduler(native["scheduler"], enabled=True)
                halt.require_exact(
                    native["scheduler"],
                    primary["scheduler"],
                    "native_pre_call_scheduler_drift",
                )
            except Exception:
                native_ready = False
        passed = native_ready

    return {
        "status": "PASS" if passed else "BLOCKED",
        "primary": primary,
        "diagnostics": diagnostics,
    }


def _r8_halt_execute() -> dict[str, object]:
    from scripts import d10_arch128_r8_halt_windows as windows
    from scripts import d10_arch128_r8_terminal_halt as halt

    primary = halt.execute(
        (halt.EXECUTE_FLAG,), os.environ, windows.ProtectedWindowsHost
    )
    required = {
        "schema": halt.SCHEMA,
        "status": "PASS",
        "call_attempted": True,
        "disposition": "CALL_RETURNED",
        "incident": "EXACT_TERMINAL_FIRST_WAKE",
        "scheduler_pre": "ENABLED_NON_RUNNING_EXACT",
        "scheduler_mutation": "DISABLED_VERIFIED",
        "scheduler_post": "DISABLED_NON_RUNNING_EXACT",
        "evidence_before_after": "IDENTICAL",
        "lease_before_after": "IDENTICAL",
        "automatic_retry": False,
        "automatic_rollback": False,
        "automatic_cleanup": False,
        "failed_child_effects": "UNKNOWN_REQUIRES_READ_ONLY_RECONCILIATION",
        **dict.fromkeys(halt.CLOSED_EFFECTS, "NOT_RUN"),
    }
    passed = type(primary) is dict and all(
        type(primary.get(key)) is type(value) and primary.get(key) == value
        for key, value in required.items()
    )
    if passed:
        try:
            halt.require_snapshot(
                halt.Snapshot(
                    primary["evidence"], primary["lease"], primary["scheduler_before"]
                ),
                enabled=True,
            )
            halt.require_snapshot(
                halt.Snapshot(
                    primary["evidence"], primary["lease"], primary["scheduler_after"]
                ),
                enabled=False,
            )
        except Exception:
            passed = False
    not_called = (
        type(primary) is dict
        and primary.get("call_attempted") is False
        and primary.get("disposition") == "NOT_CALLED"
        and primary.get("scheduler_mutation") == "NOT_RUN"
        and all(primary.get(field) == "NOT_RUN" for field in halt.CLOSED_EFFECTS)
    )
    disposition = (
        "CONFIRMED" if passed else ("NOT_RUN" if not_called else "MAY_HAVE_OCCURRED")
    )
    return {
        "status": "PASS" if passed else "STOPPED",
        "primary": primary,
        "effect_disposition": disposition,
        "automatic_retry": "NOT_AUTHORIZED",
    }


def _r7_execute() -> dict[str, object]:
    from scripts import d10_arch128_r7_protected as r7_protected
    from scripts import d10_arch128_r7_windows as r7_windows

    primary = r7_protected._dispatch(
        (r7_protected.EXECUTE_FLAG,),
        dict(os.environ),
        r7_windows.host_factory,
    )
    if type(primary) is not dict or primary.get("schema") != r7_protected.SCHEMA:
        raise RuntimeError("R7 dispatch returned malformed evidence")
    _require_not_run(
        primary,
        (
            "production_filesystem_mutation",
            "manual_task_start",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )
    if (
        primary.get("automatic_retry") is not False
        or primary.get("automatic_rollback") is not False
        or primary.get("automatic_cleanup") is not False
        or type(primary.get("reconciliation_required")) is not bool
    ):
        raise RuntimeError("R7 dispatch returned invalid recovery evidence")

    status = primary.get("status")
    completion = {
        "stage": "COMPLETE",
        "authorization": "ACCEPTED",
        "evidence_provision": "CALL_RETURNED",
        "scheduler_mutation": "CALL_RETURNED",
        "lease_publication": "PUBLISHED_VERIFIED",
        "reconciliation_required": False,
    }
    blocked = {
        "stage": "EXECUTION_INTERLOCK",
        "authorization": "NOT_ACCEPTED",
        "evidence_provision": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "lease_publication": "NOT_RUN",
        "reconciliation_required": False,
    }
    if status == "PASS":
        if any(primary.get(field) != value for field, value in completion.items()):
            raise RuntimeError("R7 PASS lacked exact verified completion evidence")
        disposition = "CONFIRMED"
    elif status == "BLOCKED" and all(
        primary.get(field) == value for field, value in blocked.items()
    ):
        disposition = "NOT_STARTED"
    else:
        disposition = "MAY_HAVE_OCCURRED"
    return {
        "status": status,
        "primary": primary,
        "effect_disposition": disposition,
    }


SUPERVISED_RELEASE_SOURCES: Final = (
    "src/trading_bot/supervised_release/__init__.py",
    "src/trading_bot/supervised_release/model.py",
)
SUPERVISED_RELEASE_TESTS: Final = (
    *COMMON_TESTS,
    "tests/review_paper/test_supervised_release_foundation.py",
    "tests/scripts/certification_runner/test_profiles.py",
)
SUPERVISED_RELEASE_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    *SUPERVISED_RELEASE_SOURCES,
    "tests/review_paper/test_supervised_release_foundation.py",
    "tests/scripts/certification_runner/test_profiles.py",
)


def _supervised_release_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Source-only structural check; no host/native/scheduler callback."""
    failures = []
    try:
        spec = _checkpoint_specs()["arch133-robinhood-supervised-release-foundation"]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-supervised-release-foundation"
            or spec.tests != SUPERVISED_RELEASE_TESTS
            or spec.ruff_paths != SUPERVISED_RELEASE_RUFF_PATHS
            or spec.authority_check is not _supervised_release_authority_check
        ):
            failures.append("supervised release source-only registration drift")
        allowed = {
            "__future__",
            "hashlib",
            "json",
            "re",
            "dataclasses",
            "decimal",
            "pathlib",
            "uuid",
            "trading_bot.strategies",
            "trading_bot.supervised_release.model",
        }
        forbidden = {
            "open",
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "mkdir",
            "resolve",
            "exists",
            "run",
            "Popen",
            "system",
        }
        for relative in SUPERVISED_RELEASE_SOURCES:
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(alias.name not in allowed for alias in node.names):
                        failures.append("supervised release import boundary drift")
                if isinstance(node, ast.ImportFrom):
                    if node.module not in allowed or (
                        node.module == "pathlib"
                        and [alias.name for alias in node.names] != ["PureWindowsPath"]
                    ):
                        failures.append("supervised release import boundary drift")
                if isinstance(node, ast.Call):
                    function = node.func
                    name = (
                        function.id
                        if isinstance(function, ast.Name)
                        else getattr(function, "attr", "")
                    )
                    if name in forbidden:
                        failures.append("supervised release capability boundary drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("supervised release workflow drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("supervised release source unavailable")
    return tuple(failures)


def _checkpoint_specs() -> dict[str, CheckpointSpec]:
    parent_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_parent_acl_repair.py",
        "tests/runtime/test_d10_arch128_r4_operator.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_replacement.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_protected_deployment.py",
        "tests/runtime/test_d10_protected_replacement.py",
        "tests/runtime/test_d10_protected_replacement_windows.py",
        "tests/runtime/test_windows_authority.py",
    )
    parent_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_parent_acl_repair.py",
        "tests/runtime/test_d10_arch128_parent_acl_repair.py",
        "scripts/d10_arch128_r4_operator.py",
        "tests/runtime/test_d10_arch128_r4_operator.py",
        "scripts/d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "scripts/d10_arch128_r4_replacement.py",
        "tests/runtime/test_d10_arch128_r4_replacement.py",
        "scripts/d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
    )
    r4_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r4_operator.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_replacement.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r3_preflight.py",
        "tests/runtime/test_d10_activation_scheduler_operator.py",
        "tests/runtime/test_d10_protected_deployment.py",
        "tests/runtime/test_d10_protected_replacement.py",
        "tests/runtime/test_d10_protected_replacement_windows.py",
    )
    r4_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r4_operator.py",
        "tests/runtime/test_d10_arch128_r4_operator.py",
        "scripts/d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "scripts/d10_arch128_r4_replacement.py",
        "tests/runtime/test_d10_arch128_r4_replacement.py",
        "scripts/d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
    )
    r5_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r5_trading_child.py",
        "tests/runtime/test_d10_python_substrate_harness.py",
        "tests/runtime/test_d10_python_substrate_windows.py",
        "tests/runtime/test_personal_desktop_d10_python_substrate.py",
    )
    r5_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r5_trading_child.py",
        "tests/runtime/test_d10_arch128_r5_trading_child.py",
        "scripts/d10_python_substrate_harness.py",
        "scripts/d10_python_substrate_windows.py",
    )
    r6_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
        "tests/runtime/test_personal_desktop_d10_activation_lease.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_personal_desktop_unattended_scheduler_contract.py",
    )
    r6_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r6_reactivation.py",
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
    )
    r7_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r7_readonly.py",
        "tests/runtime/test_d10_arch128_r7_protected.py",
        "tests/runtime/test_d10_arch128_r7_windows.py",
        "tests/runtime/test_d10_python_substrate_windows.py",
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
        "tests/runtime/test_d10_activation_scheduler_operator.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r3_preflight.py",
    )
    r7_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r7_readonly.py",
        "tests/runtime/test_d10_arch128_r7_readonly.py",
        "scripts/d10_arch128_r7_protected.py",
        "tests/runtime/test_d10_arch128_r7_protected.py",
        "scripts/d10_arch128_r7_windows.py",
        "scripts/d10_arch128_r7_observation.py",
        "scripts/d10_arch128_r4_orchestration.py",
        "scripts/d10_python_substrate_windows.py",
        "tests/runtime/test_d10_arch128_r7_windows.py",
        "tests/runtime/test_d10_python_substrate_windows.py",
    )
    r8_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_durable_wake_evidence_observe.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_personal_desktop_d10_guard_evidence.py",
    )
    r8_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_arch128_r8_readonly.py",
    )
    return {
        "arch131-robinhood-paper-intent-bridge": CheckpointSpec(
            name="arch131-robinhood-paper-intent-bridge",
            description="Architecture 131-I deterministic risk-to-paper-intent bridge",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_intent_bridge.py",
                "tests/review_paper/test_store.py",
                "tests/risk/test_risk_models.py",
                "tests/risk/test_manager.py",
                "tests/execution/test_execution_models.py",
                "tests/execution/test_order_engine.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/intent_bridge.py",
                "src/trading_bot/review_paper/__init__.py",
                "tests/review_paper/test_intent_bridge.py",
            ),
            authority_check=_arch131_paper_intent_bridge_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-deterministic-paper-pipeline": CheckpointSpec(
            name="arch131-robinhood-deterministic-paper-pipeline",
            description="Architecture 131-J one-cycle deterministic paper pipeline",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_paper_pipeline.py",
                "tests/review_paper/test_intent_bridge.py",
                "tests/test_robinhood_paper_operator.py",
                "tests/test_robinhood_paper_cycle.py",
                "tests/risk/test_risk_models.py",
                "tests/risk/test_manager.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_paper_pipeline.py",
                "tests/test_robinhood_paper_pipeline.py",
            ),
            authority_check=_arch131_deterministic_paper_pipeline_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-virtual-risk-context": CheckpointSpec(
            name="arch131-robinhood-virtual-risk-context",
            description="Architecture 131-K durable virtual-paper risk context",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_risk_context.py",
                "tests/review_paper/test_store.py",
                "tests/ledger/test_ledger.py",
                "tests/risk/test_risk_models.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/risk_context.py",
                "src/trading_bot/review_paper/__init__.py",
                "tests/review_paper/test_risk_context.py",
            ),
            authority_check=_arch131_virtual_risk_context_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-forward-paper-cycle": CheckpointSpec(
            name="arch131-robinhood-forward-paper-cycle",
            description="Architecture 131-L human-started durable-context paper cycle",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_forward_paper_cycle.py",
                "tests/review_paper/test_risk_context.py",
                "tests/test_robinhood_paper_pipeline.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_forward_paper_cycle.py",
                "tests/test_robinhood_forward_paper_cycle.py",
            ),
            authority_check=_arch131_forward_paper_cycle_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-live-qualification-verifier": CheckpointSpec(
            name="arch131-robinhood-live-qualification-verifier",
            description="Architecture 131-LQ read-only live-qualification verifier",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_live_qualification_verifier.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_live_qualification_verifier.py",
                "tests/test_robinhood_live_qualification_verifier.py",
            ),
            authority_check=_arch131_live_qualification_verifier_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-session-admission": CheckpointSpec(
            name="arch131-robinhood-session-admission",
            description=(
                "Architecture 131-M explicit-schedule regular-session admission"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_session_admission.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/session_admission.py",
                "tests/review_paper/test_session_admission.py",
            ),
            authority_check=_arch131_session_admission_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-risk-price-snapshot": CheckpointSpec(
            name="arch131-robinhood-risk-price-snapshot",
            description=(
                "Architecture 131-N canonical Robinhood quote-to-risk-price snapshot"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_risk_prices.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/risk_prices.py",
                "tests/review_paper/test_risk_prices.py",
            ),
            authority_check=_arch131_risk_price_snapshot_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-forward-paper-preview": CheckpointSpec(
            name="arch131-robinhood-forward-paper-preview",
            description=(
                "Architecture 131-O effect-free durable forward-paper risk preview"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_forward_preview.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/forward_preview.py",
                "tests/review_paper/test_forward_preview.py",
            ),
            authority_check=_arch131_forward_paper_preview_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-risk-price-acquisition": CheckpointSpec(
            name="arch131-robinhood-risk-price-acquisition",
            description=(
                "Architecture 131-P bounded read-only Robinhood risk-price acquisition"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_risk_price_acquisition.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/risk_price_acquisition.py",
                "tests/review_paper/test_risk_price_acquisition.py",
            ),
            authority_check=_arch131_risk_price_acquisition_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-supervised-forward-paper": CheckpointSpec(
            name="arch131-robinhood-supervised-forward-paper",
            description=(
                "Architecture 131-Q two-phase supervised forward-paper "
                "operator composition"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_supervised_forward_paper.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/supervised_forward_paper.py",
                "tests/review_paper/test_supervised_forward_paper.py",
            ),
            authority_check=_arch131_supervised_forward_paper_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-supervised-prepare-qualification": CheckpointSpec(
            name="arch131-robinhood-supervised-prepare-qualification",
            description="Architecture 131-R supervised PREPARE qualification harness",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_prepare_qualification.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/prepare_qualification.py",
                "tests/review_paper/test_prepare_qualification.py",
            ),
            authority_check=_arch131_prepare_qualification_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-supervised-prepare-verifier": CheckpointSpec(
            name="arch131-robinhood-supervised-prepare-verifier",
            description="Architecture 131-R read-only PREPARE qualification verifier",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_prepare_qualification_verifier.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_prepare_qualification_verifier.py",
                "tests/test_robinhood_prepare_qualification_verifier.py",
            ),
            authority_check=_arch131_prepare_verifier_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-nyse-published-regular-session-authority": CheckpointSpec(
            name="arch131-nyse-published-regular-session-authority",
            description=("Architecture 131-S NYSE published regular-session authority"),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_nyse_published_regular_sessions.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/nyse_published_regular_sessions.py",
                "tests/review_paper/test_nyse_published_regular_sessions.py",
            ),
            authority_check=_arch131_nyse_published_regular_session_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-published-session-prepare": CheckpointSpec(
            name="arch131-robinhood-published-session-prepare",
            description=(
                "Architecture 131-T explicit-date published-session PREPARE binding"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_published_session_prepare.py",
                "tests/test_robinhood_prepare_qualification_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/published_session_prepare.py",
                "tests/review_paper/test_published_session_prepare.py",
                "src/trading_bot/robinhood_prepare_qualification_verifier.py",
                "tests/test_robinhood_prepare_qualification_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch131_published_session_prepare_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-published-prepare-operator": CheckpointSpec(
            name="arch131-robinhood-published-prepare-operator",
            description="Architecture 131-U source-owned PREPARE transport composition",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_prepare_operator.py",
                "tests/review_paper/test_published_session_prepare.py",
                "tests/review_paper/test_prepare_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_prepare_operator.py",
                "tests/test_robinhood_prepare_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch131_published_prepare_operator_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-supervised-qualification": CheckpointSpec(
            name="arch131-robinhood-supervised-qualification",
            description=("Architecture 131-V supervised qualification and verifier"),
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_supervised_qualification.py",
                "tests/review_paper/test_supervised_forward_paper.py",
                "tests/review_paper/test_prepare_qualification.py",
                "tests/test_robinhood_prepare_qualification_verifier.py",
                "tests/test_robinhood_prepare_operator.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_supervised_qualification.py",
                "src/trading_bot/robinhood_execute_qualification_verifier.py",
                "scripts/robinhood_supervised_qualification.py",
                "src/trading_bot/review_paper/__init__.py",
                "tests/test_robinhood_supervised_qualification.py",
            ),
            authority_check=_arch131_supervised_qualification_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-activation-core": CheckpointSpec(
            name="arch133-robinhood-unattended-activation-core",
            description=(
                "Architecture 133-A pure activation and wake identity/state core"
            ),
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_activation.py",
                "tests/review_paper/test_unattended_activation.py",
            ),
            authority_check=_arch133_unattended_activation_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133a",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-state-store": CheckpointSpec(
            name="arch133-robinhood-unattended-state-store",
            description="Architecture 133-B durable wake store and read-only verifier",
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_state_schema.py",
                "src/trading_bot/review_paper/unattended_state_store.py",
                "src/trading_bot/review_paper/unattended_state_verifier.py",
                "tests/review_paper/test_unattended_state_store.py",
            ),
            authority_check=_arch133_unattended_state_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133b",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-one-wake-composition": CheckpointSpec(
            name="arch133-robinhood-unattended-one-wake-composition",
            description="Architecture 133-C effect-free one-wake composition",
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_one_wake.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_one_wake_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133c",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-review-paper-execution": CheckpointSpec(
            name="arch133-robinhood-unattended-review-paper-execution",
            description="Architecture 133-D bounded unattended review-paper execution",
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/test_robinhood_paper_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_execution.py",
                "tests/review_paper/test_unattended_execution.py",
                "src/trading_bot/robinhood_paper_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_execution_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133d",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-host-scheduler-surface": CheckpointSpec(
            name="arch133-robinhood-unattended-host-scheduler-surface",
            description=(
                "Architecture 133-E zero-argument host and pure scheduler surface"
            ),
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_host_identity.py",
                "src/trading_bot/review_paper/unattended_scheduler.py",
                "src/trading_bot/review_paper/unattended_host.py",
                "scripts/run_arch133_unattended_review_paper.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_host_scheduler_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133e",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-post-publication-stage-diagnostic": CheckpointSpec(
            name="arch133-robinhood-post-publication-stage-diagnostic",
            description="Architecture 133-M source-only stage diagnostic",
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133m",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-publication-state-paper-diagnostic": CheckpointSpec(
            name="arch133-robinhood-publication-state-paper-diagnostic",
            description=(
                "Architecture 133-N source-only publication/state/paper diagnostic"
            ),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PUBLICATION_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_publication_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133n",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-admission-diagnostic": CheckpointSpec(
            name="arch133-robinhood-reprovision-admission-diagnostic",
            description=(
                "Architecture 133-R source-only reprovision admission diagnostic"
            ),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_REPROVISION_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133r",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-parent-security-diagnostic": CheckpointSpec(
            name="arch133-robinhood-reprovision-parent-security-diagnostic",
            description=("Architecture 133-S source-only parent-security diagnostic"),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_parent_security_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133s",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-parent-policy-diagnostic": CheckpointSpec(
            name="arch133-robinhood-reprovision-parent-policy-diagnostic",
            description=("Architecture 133-T source-only parent-security diagnostic"),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_parent_policy_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133t",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-fresh-activation-reprovision": CheckpointSpec(
            name="arch133-robinhood-fresh-activation-reprovision",
            description="Architecture 133-Q source-only fresh activation reprovision",
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_REPROVISION_SOURCES,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133q",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-fresh-activation-reprovision-corrected": CheckpointSpec(
            name="arch133-robinhood-fresh-activation-reprovision-corrected",
            description="Architecture 133-U source-only corrected fresh activation reprovision",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133U_REPROVISION_SOURCES,
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_corrected_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133u",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-indeterminate-reconciliation": CheckpointSpec(
            name="arch133-robinhood-reprovision-indeterminate-reconciliation",
            description="Architecture 133-V source-only indeterminate reconciliation",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133V_RECONCILIATION_SOURCES,
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_reconciliation_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133v",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-sealed-predecessor-recovery": CheckpointSpec(
            name="arch133-robinhood-reprovision-sealed-predecessor-recovery",
            description="Architecture 133-W source-only sealed-predecessor recovery",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_recovery.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133W_RECOVERY_SOURCES,
                "tests/review_paper/test_arch133_reprovision_recovery.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_recovery_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133w",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-recovery-reconciliation": CheckpointSpec(
            name="arch133-robinhood-reprovision-recovery-reconciliation",
            description="Architecture 133-X source-only post-W recovery reconciliation",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133X_RECONCILIATION_SOURCES,
                "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_recovery_reconciliation_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133x",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-windows-rename-qualification": CheckpointSpec(
            name="arch133-robinhood-windows-rename-qualification",
            description="Architecture 133-Y source-only scratch Windows rename qualification",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_windows_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133Y_QUALIFICATION_SOURCES,
                "tests/review_paper/test_arch133_windows_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_windows_rename_qualification_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133y",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-closed-descendant-rename-qualification": CheckpointSpec(
            name="arch133-robinhood-closed-descendant-rename-qualification",
            description="Architecture 133-Z source-only scratch Windows rename qualification",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133Z_QUALIFICATION_SOURCES,
                "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_closed_descendant_rename_qualification_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133z",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-supervised-release-foundation": CheckpointSpec(
            name="arch133-robinhood-supervised-release-foundation",
            description="Architecture 133 pure immutable-release foundation",
            tests=SUPERVISED_RELEASE_TESTS,
            ruff_paths=SUPERVISED_RELEASE_RUFF_PATHS,
            authority_check=_supervised_release_authority_check,
            remote_branch="feature/robinhood-supervised-release-foundation",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-single-session-scheduler-installation": CheckpointSpec(
            name="arch133-robinhood-single-session-scheduler-installation",
            description="Architecture 133-P source-only protected Q133-3 installation",
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *(p for p in ARCH133_SCHEDULER_SOURCES if p.endswith(".py")),
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_scheduler_installation_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133p",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-publication-state-paper-corrected": CheckpointSpec(
            name="arch133-robinhood-publication-state-paper-corrected",
            description=(
                "Architecture 133-O source-only publication/state/paper diagnostic"
            ),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PUBLICATION_CORRECTED_SOURCES,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_publication_corrected_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133o",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-post-publication-verifier": CheckpointSpec(
            name="arch133-robinhood-post-publication-verifier",
            description="Architecture 133-L source-only post-publication verifier",
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_VERIFIER_SOURCES,
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_verifier_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133l",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-retained-root-acl-recovery": CheckpointSpec(
            name="arch133-robinhood-retained-root-acl-recovery",
            description="Architecture 133-K source-only retained-root ACL recovery",
            tests=(
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            ),
            ruff_paths=(
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_RECOVERY_SOURCES,
                "tests/review_paper/test_retained_root_acl_recovery.py",
            ),
            authority_check=_arch133_recovery_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133k",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-retained-root-diagnostic": CheckpointSpec(
            name="arch133-robinhood-retained-root-diagnostic",
            description="Architecture 133-J source-only retained-root diagnostic",
            tests=(
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            ),
            ruff_paths=(
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_RETAINED_SOURCES,
                "tests/review_paper/test_retained_root_diagnostic.py",
            ),
            authority_check=_arch133_retained_root_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133j",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-scratch-root-acl-qualification": CheckpointSpec(
            name="arch133-robinhood-scratch-root-acl-qualification",
            description=(
                "Architecture 133-I source-only scratch native root ACL qualification"
            ),
            tests=(
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            ),
            ruff_paths=(
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_SCRATCH_SOURCES,
                "src/trading_bot/review_paper/unattended_publication_windows.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            ),
            authority_check=_arch133_scratch_root_acl_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133i",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-host-publication": CheckpointSpec(
            name="arch133-robinhood-unattended-host-publication",
            description=(
                "Architecture 133-H source-only Q133-2 publication prerequisite"
            ),
            tests=(
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_unattended_publication.py",
            ),
            ruff_paths=(
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_PUBLICATION_SOURCES,
                "tests/review_paper/test_unattended_publication.py",
            ),
            authority_check=_arch133_host_publication_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133h",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-host-bootstrap": CheckpointSpec(
            name="arch133-robinhood-unattended-host-bootstrap",
            description=(
                "Architecture 133-G pre-publication host/runtime bootstrap surface"
            ),
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_host_identity.py",
                "src/trading_bot/review_paper/unattended_scheduler.py",
                "src/trading_bot/review_paper/unattended_host.py",
                "src/trading_bot/review_paper/unattended_host_bootstrap.py",
                "scripts/run_arch133_unattended_review_paper.py",
                "scripts/run_arch133_unattended_host_preflight.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_host_bootstrap_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133g",
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-paper-operator": CheckpointSpec(
            name="arch131-robinhood-paper-operator",
            description="Architecture 131-H one-cycle Robinhood paper operator",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_paper_operator.py",
                "tests/test_robinhood_paper_cycle.py",
                "tests/robinhood_mcp/test_account_resolution.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
                "tests/robinhood_mcp/test_windows_oauth.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_paper_operator.py",
                "tests/test_robinhood_paper_operator.py",
            ),
            authority_check=_arch131_paper_operator_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-agentic-account": CheckpointSpec(
            name="arch131-robinhood-agentic-account",
            description="Architecture 131-G internal Agentic-account resolution",
            tests=(
                *ARCH131_TESTS,
                "tests/robinhood_mcp/test_account_resolution.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
                "tests/test_robinhood_paper_cycle.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_mcp/account_resolution.py",
                "src/trading_bot/robinhood_mcp/sdk_transport.py",
                "src/trading_bot/robinhood_mcp/__init__.py",
                "src/trading_bot/robinhood_paper_cycle.py",
                "tests/robinhood_mcp/test_account_resolution.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
                "tests/test_robinhood_paper_cycle.py",
            ),
            authority_check=_arch131_agentic_account_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-oauth-windows": CheckpointSpec(
            name="arch131-robinhood-oauth-windows",
            description="Architecture 131-F Windows OAuth persistence and callback",
            tests=(
                *ARCH131_TESTS,
                "tests/robinhood_mcp/test_windows_oauth.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_mcp/windows_oauth.py",
                "tests/robinhood_mcp/test_windows_oauth.py",
            ),
            authority_check=_arch131_windows_oauth_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-direct-mcp": CheckpointSpec(
            name="arch131-robinhood-direct-mcp",
            description="Architecture 131-E direct Robinhood MCP transport",
            tests=(
                *ARCH131_TESTS,
                "tests/robinhood_mcp/test_sdk_transport.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_mcp/__init__.py",
                "src/trading_bot/robinhood_mcp/sdk_transport.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
            ),
            authority_check=_arch131_direct_mcp_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch131-robinhood-performance": CheckpointSpec(
            name="arch131-robinhood-performance",
            description="Architecture 131-D durable Robinhood paper performance",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_performance.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/__init__.py",
                "src/trading_bot/review_paper/performance.py",
                "tests/review_paper/test_performance.py",
            ),
            authority_check=_arch131_performance_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch131-robinhood-paper-cycle": CheckpointSpec(
            name="arch131-robinhood-paper-cycle",
            description="Architecture 131-C fail-closed Robinhood paper cycle",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_paper_cycle.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_paper_cycle.py",
                "tests/test_robinhood_paper_cycle.py",
            ),
            authority_check=_arch131_paper_cycle_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch131-robinhood-mcp-schema": CheckpointSpec(
            name="arch131-robinhood-mcp-schema",
            description="Architecture 131-B typed Robinhood MCP read/review schema",
            tests=(
                *ARCH131_TESTS,
                "tests/robinhood_mcp/test_adapter.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_mcp/__init__.py",
                "src/trading_bot/robinhood_mcp/models.py",
                "src/trading_bot/robinhood_mcp/parsing.py",
                "src/trading_bot/robinhood_mcp/adapter.py",
                "tests/robinhood_mcp/test_adapter.py",
            ),
            authority_check=_arch131_mcp_schema_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch131-robinhood-review-paper": CheckpointSpec(
            name="arch131-robinhood-review-paper",
            description="Architecture 131 Robinhood review-based paper ledger",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_store.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/__init__.py",
                "src/trading_bot/review_paper/models.py",
                "src/trading_bot/review_paper/store.py",
                "tests/review_paper/test_store.py",
            ),
            authority_check=_arch131_review_paper_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch130-r8i-d1": CheckpointSpec(
            name="arch130-r8i-d1",
            description=(
                "Architecture 130 failed first-wake read-only effect reconciliation"
            ),
            tests=(
                *RETAINED_TESTS,
                "tests/runtime/test_d10_arch130_r8i_d1.py",
            ),
            ruff_paths=(
                *RETAINED_RUFF_PATHS,
                "scripts/d10_arch130_r8i_d1.py",
                "tests/runtime/test_d10_arch130_r8i_d1.py",
            ),
            authority_check=_arch130_r8i_d1_authority_check,
            preflight=_arch130_r8i_d1_preflight,
            remote_branch=ARCH130_R8I_D1_REMOTE_BRANCH,
        ),
        "arch128-r8-terminal-halt": CheckpointSpec(
            name="arch128-r8-terminal-halt",
            description="R8I-H1 exact terminal first-wake scheduler halt source",
            tests=(
                *RETAINED_TESTS,
                "tests/runtime/test_d10_arch128_r8_terminal_halt.py",
                "tests/runtime/test_d10_arch128_r8_readonly.py",
                "tests/runtime/test_d10_durable_wake_evidence_observe.py",
            ),
            ruff_paths=(
                *RETAINED_RUFF_PATHS,
                "scripts/d10_arch128_r8_terminal_halt.py",
                "scripts/d10_arch128_r8_halt_windows.py",
                "scripts/d10_arch128_r8_halt_diagnostic.py",
                "tests/runtime/test_d10_arch128_r8_terminal_halt.py",
            ),
            authority_check=_r8_halt_authority_check,
            preflight=_r8_halt_preflight,
            execute=_r8_halt_execute,
            remote_branch="feature/d10c-r8-terminal-halt",
        ),
        "arch128-r8": CheckpointSpec(
            name="arch128-r8",
            description="Architecture 128 first-wake read-only observation",
            tests=r8_tests,
            ruff_paths=r8_ruff,
            authority_check=_r8_authority_check,
            preflight=_r8_preflight,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-parent-acl-repair": CheckpointSpec(
            name="arch128-parent-acl-repair",
            description="Architecture 128 exact parent-ACL repair source gate",
            tests=parent_tests,
            ruff_paths=parent_ruff,
            authority_check=_parent_acl_authority_check,
            preflight=_parent_acl_preflight,
            execute=_parent_acl_execute,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-r4": CheckpointSpec(
            name="arch128-r4",
            description="Architecture 128 protected replacement source gate",
            tests=r4_tests,
            ruff_paths=r4_ruff,
            authority_check=_r4_authority_check,
            preflight=_r4_preflight,
            execute=_r4_execute,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-r5-substrate": CheckpointSpec(
            name="arch128-r5-substrate",
            description=(
                "Architecture 128 fresh protected Python substrate qualification"
            ),
            tests=r5_tests,
            ruff_paths=r5_ruff,
            authority_check=_r5_authority_check,
            preflight=_r5_substrate_preflight,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-r5-trading": CheckpointSpec(
            name="arch128-r5-trading",
            description="Architecture 128 non-admin Trading deployment qualification",
            tests=r5_tests,
            ruff_paths=r5_ruff,
            authority_check=_r5_authority_check,
            preflight=_r5_trading_preflight,
            remote_branch="feature/d10c-durable-wake-evidence",
            remote_head_env=R5_TRADING_REMOTE_HEAD_ENV,
        ),
        "arch128-r6": CheckpointSpec(
            name="arch128-r6",
            description="Architecture 128 source-only reactivation ordering gate",
            tests=r6_tests,
            ruff_paths=r6_ruff,
            authority_check=_r6_authority_check,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-r7": CheckpointSpec(
            name="arch128-r7",
            description="Architecture 128 R7 read-only activation admission",
            tests=r7_tests,
            ruff_paths=r7_ruff,
            authority_check=_r7_authority_check,
            preflight=_r7_preflight,
            execute=_r7_execute,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
    }


def _default_evidence_root(repo_root: Path) -> Path:
    configured = os.environ.get("AI_TRADING_BOT_CHECKPOINT_EVIDENCE_ROOT")
    if configured:
        return Path(configured)

    if os.name == "nt":
        preferred = Path(r"F:\AI\temp")
        if preferred.is_dir():
            return preferred / "ai-trading-bot-checkpoints"

    return Path(tempfile.gettempdir()) / "ai-trading-bot-checkpoints"


def _git_output(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _remote_branch_head(repo_root: Path, branch: str) -> str:
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    try:
        completed = subprocess.run(
            ("git", "ls-remote", "origin", f"refs/heads/{branch}"),
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
            timeout=REMOTE_LOOKUP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"git ls-remote timed out after {REMOTE_LOOKUP_TIMEOUT_SECONDS} seconds"
        ) from exc
    if completed.returncode != 0:
        raise RuntimeError(f"git ls-remote failed: {completed.stderr.strip()}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(
            f"remote branch lookup returned {len(lines)} rows for {branch}"
        )
    parts = lines[0].split()
    if len(parts) != 2 or parts[1] != f"refs/heads/{branch}":
        raise RuntimeError("remote branch lookup returned an unexpected row")
    return parts[0]


def _trusted_remote_head_from_env(variable: str) -> str:
    value = os.environ.get(variable, "")
    if (
        len(value) != 40
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeError(
            f"trusted remote-head handoff is missing or malformed: {variable}"
        )
    return value


def _git_state(repo_root: Path) -> dict[str, object]:
    return {
        "head": _git_output(repo_root, "rev-parse", "HEAD"),
        "tree": _git_output(repo_root, "rev-parse", "HEAD^{tree}"),
        "branch": _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "porcelain": _git_output(
            repo_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ),
    }


def build_verification_steps(
    spec: CheckpointSpec,
    *,
    python_executable: str,
    basetemp: Path,
) -> tuple[Step, ...]:
    return (
        Step(
            "pytest",
            (
                python_executable,
                "-m",
                "pytest",
                *spec.tests,
                f"--basetemp={basetemp}",
                "-p",
                "no:cacheprovider",
                "--durations=100",
                "--durations-min=0.0",
                f"--junitxml={basetemp.parent / 'pytest-results.xml'}",
            ),
        ),
        Step(
            "ruff_check",
            (
                python_executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                *spec.ruff_paths,
            ),
            (
                python_executable,
                "-m",
                "ruff",
                "check",
                "--diff",
                "--no-cache",
                *spec.ruff_paths,
            ),
        ),
        Step(
            "ruff_format",
            (
                python_executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "--no-cache",
                *spec.ruff_paths,
            ),
            (
                python_executable,
                "-m",
                "ruff",
                "format",
                "--diff",
                "--no-cache",
                *spec.ruff_paths,
            ),
        ),
        Step("git_diff_check", ("git", "diff", "--check")),
    )


def _safe_step_name(name: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in name)


def _execute_step(
    step: Step,
    *,
    repo_root: Path,
    command_dir: Path,
    index: int,
    diagnostic: bool = False,
) -> CommandOutcome:
    label = f"{step.name}_diagnostic" if diagnostic else step.name
    argv = step.diagnostic_argv if diagnostic else step.argv
    if argv is None:
        raise ValueError("diagnostic command is unavailable")

    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    elapsed_seconds = time.monotonic() - started
    stdout = completed.stdout
    stderr = completed.stderr
    prefix = f"{index:02d}-{_safe_step_name(label)}"
    stdout_path = command_dir / f"{prefix}.stdout.txt"
    stderr_path = command_dir / f"{prefix}.stderr.txt"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)

    if completed.returncode != 0:
        if stdout:
            sys.stdout.buffer.write(stdout)
        if stderr:
            sys.stderr.buffer.write(stderr)

    return CommandOutcome(
        name=label,
        argv=tuple(argv),
        exit_code=int(completed.returncode),
        stdout_bytes=len(stdout),
        stderr_bytes=len(stderr),
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        elapsed_seconds=elapsed_seconds,
    )


def run_verification_steps(
    steps: Sequence[Step],
    execute: Callable[[Step, bool], CommandOutcome],
) -> tuple[CommandOutcome, ...]:
    outcomes: list[CommandOutcome] = []
    for step in steps:
        primary = execute(step, False)
        outcomes.append(primary)
        if primary.exit_code != 0 and step.diagnostic_argv is not None:
            outcomes.append(execute(step, True))
    return tuple(outcomes)


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verify_checkpoint(
    spec: CheckpointSpec,
    *,
    repo_root: Path,
    evidence_root: Path,
) -> tuple[bool, Path]:
    state_before = _git_state(repo_root)
    if state_before["porcelain"]:
        raise RuntimeError(
            f"source gate requires a clean worktree; found: {state_before['porcelain']}"
        )

    evidence_dir = evidence_root / spec.name / f"source-gate-{_stamp()}"
    command_dir = evidence_dir / "commands"
    command_dir.mkdir(parents=True, exist_ok=False)
    basetemp = evidence_dir / "pytest"

    steps = build_verification_steps(
        spec,
        python_executable=sys.executable,
        basetemp=basetemp,
    )
    counter = 0

    def execute(step: Step, diagnostic: bool) -> CommandOutcome:
        nonlocal counter
        counter += 1
        return _execute_step(
            step,
            repo_root=repo_root,
            command_dir=command_dir,
            index=counter,
            diagnostic=diagnostic,
        )

    outcomes = run_verification_steps(steps, execute)
    authority_failures = spec.authority_check(repo_root)
    state_after = _git_state(repo_root)

    primary = {
        outcome.name: outcome.exit_code
        for outcome in outcomes
        if not outcome.name.endswith("_diagnostic")
    }
    commands_pass = all(
        primary.get(name) == 0
        for name in ("pytest", "ruff_check", "ruff_format", "git_diff_check")
    )
    identity_stable = (
        state_before["head"] == state_after["head"]
        and state_before["tree"] == state_after["tree"]
        and not state_after["porcelain"]
    )
    passed = commands_pass and not authority_failures and identity_stable

    report = {
        "schema": SCHEMA,
        "kind": "source_gate",
        "checkpoint": spec.name,
        "description": spec.description,
        "status": "PASS" if passed else "FAIL",
        "started_from": state_before,
        "finished_at": state_after,
        "identity_stable": identity_stable,
        "authority_failures": list(authority_failures),
        "commands": [asdict(outcome) for outcome in outcomes],
        "production_effects": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "provider_effects": "NOT_RUN",
        "broker_live_effects": "NOT_RUN",
    }
    report_path = evidence_dir / "report.json"
    _write_json(report_path, report)

    print(f"CHECKPOINT={spec.name}")
    for name in ("pytest", "ruff_check", "ruff_format", "git_diff_check"):
        exit_code = primary.get(name)
        status = "PASS" if exit_code == 0 else f"FAIL({exit_code})"
        print(f"{name.upper()}={status}")
    print(
        "AUTHORITY="
        + ("PASS" if not authority_failures else f"FAIL({len(authority_failures)})")
    )
    for failure in authority_failures:
        print(f"AUTHORITY_FAILURE={failure}")
    print(f"IDENTITY_STABLE={identity_stable}")
    print(f"EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'FAIL'}")
    return passed, report_path


def batch_requirements(
    specs: Sequence[CheckpointSpec],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Collect source requirements in deterministic caller/first-seen order."""
    if not specs or len({spec.name for spec in specs}) != len(specs):
        raise ValueError("batch requires distinct registered checkpoints")
    return (
        tuple(dict.fromkeys(path for spec in specs for path in spec.tests)),
        tuple(dict.fromkeys(path for spec in specs for path in spec.ruff_paths)),
    )


def verify_batch(
    specs: Sequence[CheckpointSpec],
    *,
    repo_root: Path,
    evidence_root: Path,
) -> tuple[bool, Path]:
    """Share source commands while independently checking every authority."""
    tests, ruff_paths = batch_requirements(specs)
    state_before = _git_state(repo_root)
    if state_before["porcelain"]:
        raise RuntimeError("source gate requires a clean worktree")
    evidence_dir = evidence_root / f"source-gate-batch-{_stamp()}"
    command_dir = evidence_dir / "commands"
    command_dir.mkdir(parents=True, exist_ok=False)
    shared = CheckpointSpec(
        name="source_gate_batch",
        description="shared source requirements",
        tests=tests,
        ruff_paths=ruff_paths,
        authority_check=lambda repo: (),
    )
    steps = build_verification_steps(
        shared, python_executable=sys.executable, basetemp=evidence_dir / "pytest"
    )
    counter = 0

    def execute(step: Step, diagnostic: bool) -> CommandOutcome:
        nonlocal counter
        counter += 1
        return _execute_step(
            step,
            repo_root=repo_root,
            command_dir=command_dir,
            index=counter,
            diagnostic=diagnostic,
        )

    outcomes = run_verification_steps(steps, execute)
    authority_failures: dict[str, tuple[str, ...]] = {}
    for spec in specs:
        try:
            authority_failures[spec.name] = spec.authority_check(repo_root)
        except Exception as exc:
            # One unavailable authority must fail closed without hiding others.
            authority_failures[spec.name] = (f"{type(exc).__name__}: {exc}",)
    state_after = _git_state(repo_root)
    commands_pass = all(
        outcome.exit_code == 0
        for outcome in outcomes
        if not outcome.name.endswith("_diagnostic")
    )
    identity_stable = (
        state_before["head"] == state_after["head"]
        and state_before["tree"] == state_after["tree"]
        and not state_after["porcelain"]
    )
    passed = commands_pass and identity_stable and not any(authority_failures.values())
    report_path = evidence_dir / "report.json"
    participants = {}
    for spec in specs:
        participants[spec.name] = {
            "checkpoint": spec.name,
            "batch_report": str(report_path),
            "tests": list(spec.tests),
            "ruff_paths": list(spec.ruff_paths),
            "tests_covered": all(path in tests for path in spec.tests),
            "ruff_paths_covered": all(path in ruff_paths for path in spec.ruff_paths),
            "authority_failures": list(authority_failures[spec.name]),
            "authority_status": "FAIL" if authority_failures[spec.name] else "PASS",
            "source_before": state_before,
            "source_after": state_after,
            "status": "PASS"
            if commands_pass and identity_stable and not authority_failures[spec.name]
            else "FAIL",
        }
    report = {
        "schema": SCHEMA,
        "kind": "source_gate_batch",
        "checkpoints": [spec.name for spec in specs],
        "source_before": state_before,
        "source_after": state_after,
        "identity_stable": identity_stable,
        "tests": list(tests),
        "ruff_paths": list(ruff_paths),
        "commands": [asdict(outcome) for outcome in outcomes],
        "authority_failures": authority_failures,
        "participants": participants,
        "production_effects": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "provider_effects": "NOT_RUN",
        "broker_live_effects": "NOT_RUN",
        "status": "PASS" if passed else "FAIL",
    }
    _write_json(report_path, report)
    print(
        f"CHECKPOINTS={len(specs)} TEST_PATHS={len(tests)} RUFF_PATHS={len(ruff_paths)}"
    )
    for outcome in outcomes:
        print(f"{outcome.name.upper()}={outcome.exit_code}")
    for name, failures in authority_failures.items():
        print(f"AUTHORITY[{name}]={'FAIL' if failures else 'PASS'}")
        for failure in failures:
            print(f"AUTHORITY_FAILURE[{name}]={failure}")
    print(f"IDENTITY_STABLE={identity_stable}")
    print(f"EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'FAIL'}")
    return passed, report_path


def classify_changed_paths(paths: Sequence[str]) -> str:
    """Only a nonempty, known set of strictly docs/ paths takes the fast path."""
    if paths and all(
        path.startswith("docs/")
        and all(part not in {"", ".", ".."} for part in path.split("/"))
        and "\\" not in path
        and "\x00" not in path
        for path in paths
    ):
        return "DOCS_ONLY"
    return "FULL"


def _ci_changes(repo_root: Path, head: str) -> dict[str, object]:
    """Read a closed event base; unavailable/unknown ranges always run FULL."""
    fallback = {
        "mode": "FULL",
        "base": None,
        "changed_paths": [],
        "reason": "event base unavailable",
    }
    try:
        event = json.loads(
            Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
        )
        if not isinstance(event, dict):
            return fallback
        event_name = os.environ.get("GITHUB_EVENT_NAME")
        if event_name == "push":
            base = event.get("before")
        elif event_name == "pull_request":
            base = event["pull_request"]["base"]["sha"]
        else:
            return fallback
        if (
            not isinstance(base, str)
            or len(base) != 40
            or set(base) == {"0"}
            or any(char not in "0123456789abcdef" for char in base)
        ):
            return fallback
        if _git_output(repo_root, "cat-file", "-t", base) != "commit":
            return fallback
        _git_output(repo_root, "merge-base", "--is-ancestor", base, head)
        # Disable rename detection: moving source into docs must include deletion
        # of the old source path. NUL delimiters preserve unusual filenames.
        changed = subprocess.run(
            ("git", "diff", "--name-only", "-z", "--no-renames", base, head, "--"),
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        raw = changed.stdout.decode("utf-8")
        if changed.returncode != 0 or (raw and not raw.endswith("\x00")):
            return fallback
        paths = raw.removesuffix("\x00").split("\x00") if raw else []
        mode = classify_changed_paths(paths)
        return {
            "mode": mode,
            "base": base,
            "changed_paths": paths,
            "reason": "all changed paths under docs/"
            if mode == "DOCS_ONLY"
            else "non-docs or empty diff",
        }
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RuntimeError):
        return fallback


def verify_ci_changes(
    *,
    repo_root: Path,
    evidence_root: Path,
    docs_only: bool = False,
) -> tuple[bool, Path]:
    """Classify CI changes or validate the docs-only range without dependencies."""
    before = _git_state(repo_root)
    if before["porcelain"]:
        raise RuntimeError("CI change gate requires a clean worktree")
    changes = _ci_changes(repo_root, str(before["head"]))
    evidence_dir = (
        evidence_root / f"{'docs-only' if docs_only else 'ci-changes'}-{_stamp()}"
    )
    evidence_dir.mkdir(parents=True, exist_ok=False)
    outcomes = ()
    if docs_only and changes["mode"] == "DOCS_ONLY":
        command_dir = evidence_dir / "commands"
        command_dir.mkdir()
        step = Step(
            "git_range_diff_check",
            ("git", "diff", "--check", str(changes["base"]), str(before["head"]), "--"),
        )
        outcomes = (
            _execute_step(step, repo_root=repo_root, command_dir=command_dir, index=1),
        )
    after = _git_state(repo_root)
    stable = (
        before["head"] == after["head"]
        and before["tree"] == after["tree"]
        and not after["porcelain"]
    )
    passed = stable and (
        not docs_only or (changes["mode"] == "DOCS_ONLY" and outcomes[0].exit_code == 0)
    )
    report_path = evidence_dir / "report.json"
    _write_json(
        report_path,
        {
            "schema": SCHEMA,
            "kind": "docs_only_gate" if docs_only else "ci_change_classification",
            **changes,
            "source_before": before,
            "source_after": after,
            "identity_stable": stable,
            "status": "PASS" if passed else "FAIL",
            "commands": [asdict(outcome) for outcome in outcomes],
            "production_effects": "NOT_RUN",
            "scheduler_mutation": "NOT_RUN",
            "provider_effects": "NOT_RUN",
            "broker_live_effects": "NOT_RUN",
        },
    )
    if not docs_only and os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"mode={changes['mode'] if passed else 'FULL'}\n")
    print(f"MODE={changes['mode']} EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'FAIL'}")
    return passed, report_path


def preflight_checkpoint(
    spec: CheckpointSpec,
    *,
    repo_root: Path,
    evidence_root: Path,
) -> tuple[bool, Path]:
    if spec.preflight is None:
        raise RuntimeError(f"checkpoint has no read-only preflight: {spec.name}")

    state_before = _git_state(repo_root)
    if state_before["porcelain"]:
        raise RuntimeError(
            f"preflight requires a clean worktree; found: {state_before['porcelain']}"
        )

    local_branch = str(state_before["branch"])
    remote_branch = spec.remote_branch
    if remote_branch is None:
        if local_branch == "HEAD":
            raise RuntimeError(
                "detached preflight requires a checkpoint-pinned remote branch"
            )
        remote_branch = local_branch

    if spec.remote_head_env is None:
        remote_head = _remote_branch_head(repo_root, remote_branch)
        remote_head_source = "LIVE_REMOTE_LOOKUP"
    else:
        remote_head = _trusted_remote_head_from_env(spec.remote_head_env)
        remote_head_source = f"TRUSTED_ENV:{spec.remote_head_env}"

    if remote_head != state_before["head"]:
        raise RuntimeError(
            "preflight source is not the live remote branch head: "
            f"local={state_before['head']} "
            f"remote={remote_head} branch={remote_branch}"
        )

    evidence_dir = evidence_root / spec.name / f"preflight-{_stamp()}"
    evidence_dir.mkdir(parents=True, exist_ok=False)

    result = spec.preflight()
    state_after = _git_state(repo_root)
    identity_stable = (
        state_before["head"] == state_after["head"]
        and state_before["tree"] == state_after["tree"]
        and state_before["branch"] == state_after["branch"]
        and not state_after["porcelain"]
    )
    passed = result.get("status") == "PASS" and identity_stable

    report = {
        "schema": SCHEMA,
        "kind": "read_only_preflight",
        "checkpoint": spec.name,
        "description": spec.description,
        "status": "PASS" if passed else "BLOCKED",
        "source": {
            "before": state_before,
            "after": state_after,
            "remote_branch": remote_branch,
            "remote_head": remote_head,
            "remote_head_source": remote_head_source,
            "identity_stable": identity_stable,
        },
        "result": result,
        "production_effects": "NOT_RUN",
        "protected_execution": "NOT_AUTHORIZED",
    }
    report_path = evidence_dir / "report.json"
    _write_json(report_path, report)

    primary = result.get("primary")
    if isinstance(primary, dict):
        print(f"PRIMARY_STATUS={primary.get('status')}")
        if primary.get("reason") is not None:
            print(f"PRIMARY_REASON={primary.get('reason')}")
        if primary.get("detail") is not None:
            print(f"PRIMARY_DETAIL={primary.get('detail')}")

    diagnostics = result.get("diagnostics")
    if isinstance(diagnostics, dict):
        for name, diagnostic in diagnostics.items():
            if isinstance(diagnostic, dict):
                print(f"DIAGNOSTIC={name}")
                print(f"DIAGNOSTIC_STATUS={diagnostic.get('status')}")
                if diagnostic.get("reason") is not None:
                    print(f"DIAGNOSTIC_REASON={diagnostic.get('reason')}")
                if diagnostic.get("detail") is not None:
                    print(f"DIAGNOSTIC_DETAIL={diagnostic.get('detail')}")

    print(f"IDENTITY_STABLE={identity_stable}")
    print(f"EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'BLOCKED'}")
    return passed, report_path


def execute_checkpoint(
    spec: CheckpointSpec,
    *,
    repo_root: Path,
    evidence_root: Path,
) -> tuple[bool, Path]:
    if spec.execute is None:
        raise RuntimeError(f"checkpoint has no protected execution: {spec.name}")

    state_before = _git_state(repo_root)
    if state_before["porcelain"]:
        raise RuntimeError(
            f"protected execution requires a clean worktree; "
            f"found: {state_before['porcelain']}"
        )

    local_branch = str(state_before["branch"])
    remote_branch = spec.remote_branch
    if remote_branch is None:
        if local_branch == "HEAD":
            raise RuntimeError(
                "detached protected execution requires a checkpoint-pinned "
                "remote branch"
            )
        remote_branch = local_branch

    remote_head = _remote_branch_head(repo_root, remote_branch)
    if remote_head != state_before["head"]:
        raise RuntimeError(
            "protected execution source is not the live remote branch head: "
            f"local={state_before['head']} "
            f"remote={remote_head} branch={remote_branch}"
        )

    evidence_dir = evidence_root / spec.name / f"execute-{_stamp()}"
    evidence_dir.mkdir(parents=True, exist_ok=False)
    attempt_path = evidence_dir / "attempt.json"
    _write_json(
        attempt_path,
        {
            "schema": SCHEMA,
            "kind": "protected_execution_attempt",
            "checkpoint": spec.name,
            "description": spec.description,
            "status": "STARTED",
            "source": {
                "before": state_before,
                "remote_branch": remote_branch,
                "remote_head": remote_head,
            },
            "automatic_retry": "NOT_AUTHORIZED",
        },
    )

    try:
        result = spec.execute()
    except Exception as exc:
        state_after = _git_state(repo_root)
        identity_stable = (
            state_before["head"] == state_after["head"]
            and state_before["tree"] == state_after["tree"]
            and state_before["branch"] == state_after["branch"]
            and not state_after["porcelain"]
        )
        report = {
            "schema": SCHEMA,
            "kind": "protected_execution",
            "checkpoint": spec.name,
            "description": spec.description,
            "status": "STOPPED",
            "source": {
                "before": state_before,
                "after": state_after,
                "remote_branch": remote_branch,
                "remote_head": remote_head,
                "identity_stable": identity_stable,
            },
            "runner_error": {
                "type": type(exc).__name__,
                "detail": str(exc),
            },
            "effect_disposition": "MAY_HAVE_OCCURRED",
            "protected_execution": "ATTEMPTED",
            "automatic_retry": "NOT_AUTHORIZED",
        }
        report_path = evidence_dir / "report.json"
        _write_json(report_path, report)
        print(f"RUNNER_EXECUTION_ERROR={type(exc).__name__}:{exc}", file=sys.stderr)
        print(f"IDENTITY_STABLE={identity_stable}")
        print(f"EVIDENCE={report_path}")
        print("OVERALL=STOPPED")
        return False, report_path

    state_after = _git_state(repo_root)
    identity_stable = (
        state_before["head"] == state_after["head"]
        and state_before["tree"] == state_after["tree"]
        and state_before["branch"] == state_after["branch"]
        and not state_after["porcelain"]
    )
    passed = result.get("status") == "PASS" and identity_stable
    effect_disposition = result.get("effect_disposition", "MAY_HAVE_OCCURRED")

    report = {
        "schema": SCHEMA,
        "kind": "protected_execution",
        "checkpoint": spec.name,
        "description": spec.description,
        "status": "PASS" if passed else "STOPPED",
        "source": {
            "before": state_before,
            "after": state_after,
            "remote_branch": remote_branch,
            "remote_head": remote_head,
            "identity_stable": identity_stable,
        },
        "result": result,
        "effect_disposition": effect_disposition,
        "protected_execution": "ATTEMPTED",
        "automatic_retry": "NOT_AUTHORIZED",
    }
    report_path = evidence_dir / "report.json"
    _write_json(report_path, report)

    primary = result.get("primary")
    if isinstance(primary, dict):
        print(f"PRIMARY_STATUS={primary.get('status')}")
        if primary.get("reason") is not None:
            print(f"PRIMARY_REASON={primary.get('reason')}")
        if primary.get("detail") is not None:
            print(f"PRIMARY_DETAIL={primary.get('detail')}")
    print(f"EFFECT_DISPOSITION={effect_disposition}")
    print(f"IDENTITY_STABLE={identity_stable}")
    print(f"EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'STOPPED'}")
    return passed, report_path


def _status(repo_root: Path, specs: Mapping[str, CheckpointSpec]) -> int:
    state = _git_state(repo_root)
    print(f"SCHEMA={SCHEMA}")
    print(f"REPO={repo_root}")
    print(f"HEAD={state['head']}")
    print(f"TREE={state['tree']}")
    print(f"BRANCH={state['branch']}")
    print(f"CLEAN={not bool(state['porcelain'])}")
    print("READ_ONLY_PREFLIGHT=IMPLEMENTED_FOR_REGISTERED_PROFILES")
    execute_specs = sorted(
        name for name, spec in specs.items() if spec.execute is not None
    )
    print(
        "PROTECTED_EXECUTION="
        + (
            "IMPLEMENTED_FOR_" + ",".join(execute_specs)
            if execute_specs
            else "NOT_IMPLEMENTED"
        )
    )
    print("CHECKPOINTS=" + ",".join(sorted(specs)))
    for name in sorted(specs):
        print(f"{name}: {specs[name].description}")
    return 0


def _parser(specs: Mapping[str, CheckpointSpec]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="show runner and repository status")

    verify = subparsers.add_parser(
        "verify",
        help="run a source-only checkpoint gate",
    )
    verify.add_argument("checkpoint", choices=sorted(specs))
    verify.add_argument(
        "--evidence-root",
        type=Path,
        help="override the external checkpoint evidence root",
    )

    batch = subparsers.add_parser("verify-batch", help="share registered source gates")
    batch.add_argument("checkpoints", nargs="+", choices=sorted(specs))
    batch.add_argument("--evidence-root", type=Path)
    for command in ("classify-ci", "verify-docs"):
        changes = subparsers.add_parser(command, help="source-only CI change gate")
        changes.add_argument("--evidence-root", type=Path)

    preflight_specs = sorted(
        name for name, spec in specs.items() if spec.preflight is not None
    )
    preflight = subparsers.add_parser(
        "preflight",
        help="run a registered read-only host preflight",
    )
    preflight.add_argument("checkpoint", choices=preflight_specs)
    preflight.add_argument(
        "--evidence-root",
        type=Path,
        help="override the external checkpoint evidence root",
    )

    execute_specs = sorted(
        name for name, spec in specs.items() if spec.execute is not None
    )
    execute = subparsers.add_parser(
        "execute",
        help="run a registered protected checkpoint after explicit authorization",
    )
    execute.add_argument("checkpoint", choices=execute_specs)
    execute.add_argument(
        "--evidence-root",
        type=Path,
        help="override the external checkpoint evidence root",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    specs = _checkpoint_specs()
    parser = _parser(specs)
    args = parser.parse_args(argv)
    if args.command == "verify-batch" and len(set(args.checkpoints)) != len(
        args.checkpoints
    ):
        parser.error("duplicate checkpoint names are not allowed")

    if args.command == "status":
        return _status(repo_root, specs)

    evidence_root = (
        args.evidence_root
        if args.evidence_root is not None
        else _default_evidence_root(repo_root)
    )

    try:
        if args.command == "verify-batch":
            passed, _ = verify_batch(
                [specs[name] for name in args.checkpoints],
                repo_root=repo_root,
                evidence_root=evidence_root,
            )
            return 0 if passed else 1
        if args.command in {"classify-ci", "verify-docs"}:
            passed, _ = verify_ci_changes(
                repo_root=repo_root,
                evidence_root=evidence_root,
                docs_only=args.command == "verify-docs",
            )
            return 0 if passed else 1
        spec = specs[args.checkpoint]
        if args.command == "verify":
            passed, _ = verify_checkpoint(
                spec,
                repo_root=repo_root,
                evidence_root=evidence_root,
            )
        elif args.command == "preflight":
            passed, _ = preflight_checkpoint(
                spec,
                repo_root=repo_root,
                evidence_root=evidence_root,
            )
        else:
            passed, _ = execute_checkpoint(
                spec,
                repo_root=repo_root,
                evidence_root=evidence_root,
            )
    except Exception as exc:
        print(f"RUNNER_ERROR={type(exc).__name__}:{exc}", file=sys.stderr)
        return 2

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
