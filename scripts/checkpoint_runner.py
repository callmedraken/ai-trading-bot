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


COMMON_TESTS: Final = ("tests/runtime/test_checkpoint_runner.py",)
COMMON_RUFF_PATHS: Final = (
    "scripts/checkpoint_runner.py",
    "tests/runtime/test_checkpoint_runner.py",
)


CI_CHECKPOINTS: Final = (
    "arch128-parent-acl-repair",
    "arch128-r4",
    "arch128-r5-substrate",
    "arch128-r5-trading",
    "arch128-r6",
    "arch128-r7",
    "arch128-r8-terminal-halt",
    "arch130-r8i-d1",
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
)


def _batch_workflow_is_reviewed(workflow: str) -> bool:
    # Freeze the executable batch command, all 21 participants and their order,
    # and exit propagation. Comments, duplicates and missing phases must drift.
    invocation = (
        "          & powershell.exe -NoProfile -ExecutionPolicy Bypass "
        "-File .\\ops.ps1 `\n"
        "            verify-batch `\n"
        + "".join(
            f"              {name}"
            + (" `\n" if index < len(CI_CHECKPOINTS) - 1 else "\n")
            for index, name in enumerate(CI_CHECKPOINTS)
        )
        + "          exit $LASTEXITCODE\n"
    )
    return (
        workflow.count("verify-batch") == 1
        and workflow.count(invocation) == 1
        and "verify arch" not in workflow
    )


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
    "cde19fec3d2899be468ae96247f8b4b7794cd176cbe79915a4adb33a331f9ee9"
)

ARCH130_R8I_D1_SOURCE_BLOB_SHA1: Final = "4dece99d8993934e9747f091415927353b70a2e3"
ARCH130_R8I_D1_REMOTE_BRANCH: Final = "feature/d10c-r8-incident-reconciliation"
ARCH131_REVIEW_PAPER_REMOTE_BRANCH: Final = "feature/robinhood-review-paper-mode"
ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH: Final = (\n    "feature/robinhood-review-paper-side-foundation"\n)


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
            != "8cf69056ebee325d28c2487709f121ca09796a1c6b301bec0e099b581a9ff67d"
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


def _arch131_live_qualification_verifier_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (
                repo_root / "src/trading_bot/robinhood_live_qualification_verifier.py"
            ).read_text(encoding="utf-8")
        )
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "a4d3d9a21b6799ba28efa6fe94d37254087c95ad84c60a79eb42803e967a4280"
        ):
            failures.append("131-LQ read-only reconciliation boundary drift")

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
            != "2c436c254f013788cb0a5f238687a386e6030e240047883695a3d07d598219ba"
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
            and node.target.id == "CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or tuple(ast.literal_eval(ci_assignments[0].value)) != CI_CHECKPOINTS
        ):
            failures.append("131-LQ checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-LQ checkpoint has host/effect capability")
        if CI_CHECKPOINTS.count(name) != 1 or CI_CHECKPOINTS.index(name) != (
            CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-cycle") + 1
        ):
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
            != "58e753d8d40f6323289a609960ec36e9abf68cb56207b5d205b1ac5ec8473b67"
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
            != "11a7b1d02f2809026c941643a380b5af23cf781f14c1a5b008e3c72373eba2f0"
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
            != "d17ea88426f21d540a6634ed90de622dba054375437f67be2d3571cbcc85268b"
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


def _checkpoint_specs() -> dict[str, CheckpointSpec]:
    parent_tests = (
        *COMMON_TESTS,
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
        *COMMON_RUFF_PATHS,
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
        *COMMON_TESTS,
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
        *COMMON_RUFF_PATHS,
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
        *COMMON_TESTS,
        "tests/runtime/test_d10_arch128_r5_trading_child.py",
        "tests/runtime/test_d10_python_substrate_harness.py",
        "tests/runtime/test_d10_python_substrate_windows.py",
        "tests/runtime/test_personal_desktop_d10_python_substrate.py",
    )
    r5_ruff = (
        *COMMON_RUFF_PATHS,
        "scripts/d10_arch128_r5_trading_child.py",
        "tests/runtime/test_d10_arch128_r5_trading_child.py",
        "scripts/d10_python_substrate_harness.py",
        "scripts/d10_python_substrate_windows.py",
    )
    r6_tests = (
        *COMMON_TESTS,
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
        "tests/runtime/test_personal_desktop_d10_activation_lease.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_personal_desktop_unattended_scheduler_contract.py",
    )
    r6_ruff = (
        *COMMON_RUFF_PATHS,
        "scripts/d10_arch128_r6_reactivation.py",
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
    )
    r7_tests = (
        *COMMON_TESTS,
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
        *COMMON_RUFF_PATHS,
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
        *COMMON_TESTS,
        "tests/runtime/test_d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_durable_wake_evidence_observe.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_personal_desktop_d10_guard_evidence.py",
    )
    r8_ruff = (
        *COMMON_RUFF_PATHS,
        "scripts/d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_arch128_r8_readonly.py",
    )
    return {
        "arch131-robinhood-paper-intent-bridge": CheckpointSpec(
            name="arch131-robinhood-paper-intent-bridge",
            description="Architecture 131-I deterministic risk-to-paper-intent bridge",
            tests=(
                *COMMON_TESTS,
                "tests/review_paper/test_intent_bridge.py",
                "tests/review_paper/test_store.py",
                "tests/risk/test_risk_models.py",
                "tests/risk/test_manager.py",
                "tests/execution/test_execution_models.py",
                "tests/execution/test_order_engine.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/test_robinhood_paper_pipeline.py",
                "tests/review_paper/test_intent_bridge.py",
                "tests/test_robinhood_paper_operator.py",
                "tests/test_robinhood_paper_cycle.py",
                "tests/risk/test_risk_models.py",
                "tests/risk/test_manager.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/review_paper/test_risk_context.py",
                "tests/review_paper/test_store.py",
                "tests/ledger/test_ledger.py",
                "tests/risk/test_risk_models.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/test_robinhood_forward_paper_cycle.py",
                "tests/review_paper/test_risk_context.py",
                "tests/test_robinhood_paper_pipeline.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/test_robinhood_live_qualification_verifier.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
                "src/trading_bot/robinhood_live_qualification_verifier.py",
                "tests/test_robinhood_live_qualification_verifier.py",
            ),
            authority_check=_arch131_live_qualification_verifier_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-paper-operator": CheckpointSpec(
            name="arch131-robinhood-paper-operator",
            description="Architecture 131-H one-cycle Robinhood paper operator",
            tests=(
                *COMMON_TESTS,
                "tests/test_robinhood_paper_operator.py",
                "tests/test_robinhood_paper_cycle.py",
                "tests/robinhood_mcp/test_account_resolution.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
                "tests/robinhood_mcp/test_windows_oauth.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/robinhood_mcp/test_account_resolution.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
                "tests/test_robinhood_paper_cycle.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/robinhood_mcp/test_windows_oauth.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/robinhood_mcp/test_sdk_transport.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/review_paper/test_performance.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/test_robinhood_paper_cycle.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/robinhood_mcp/test_adapter.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/review_paper/test_store.py",
            ),
            ruff_paths=(
                *COMMON_RUFF_PATHS,
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
                *COMMON_TESTS,
                "tests/runtime/test_d10_arch130_r8i_d1.py",
            ),
            ruff_paths=(
                "scripts/checkpoint_runner.py",
                "tests/runtime/test_checkpoint_runner.py",
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
                *COMMON_TESTS,
                "tests/runtime/test_d10_arch128_r8_terminal_halt.py",
                "tests/runtime/test_d10_arch128_r8_readonly.py",
                "tests/runtime/test_d10_durable_wake_evidence_observe.py",
            ),
            ruff_paths=(
                "scripts/checkpoint_runner.py",
                "tests/runtime/test_checkpoint_runner.py",
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

    completed = subprocess.run(
        argv,
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
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
