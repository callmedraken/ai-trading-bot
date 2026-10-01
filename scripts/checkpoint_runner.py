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


def _d10_soak_status_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Freeze S1's public observer delegation, policy, and closed registration."""
    path = repo_root / "scripts" / "d10_soak_status_readonly.py"
    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        runner_tree = ast.parse(runner_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ("S1 source missing or invalid",)
    failures: list[str] = []
    functions = _top_level_functions(tree)
    preflight = functions.get("preflight")
    if set(functions) != {"_base", "_timestamp", "preflight"}:
        failures.append("S1 contains an unreviewed function surface")
    if preflight is None or ast.unparse(preflight.args) != "":
        failures.append("S1 requires zero-argument preflight")
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
        failures.append("S1 contains unreviewed imports or direct host authority")
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
            failures.append(f"S1 contains unreviewed authority call: {called}")
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
        failures.append("S1 must delegate exactly once to observer.observe()")
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
            failures.append(f"S1 contains forbidden host/effect surface: {forbidden}")
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
            failures.append("S1 accepted R7 identity drift")
        if ast.literal_eval(constants["SCHEMA"]) != ("d10-readonly-soak-status/v1"):
            failures.append("S1 schema drift")
    except (KeyError, ValueError, TypeError):
        failures.append("S1 frozen constants missing or invalid")
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
        failures.append("S1 closed result effect fields drift")
    try:
        if (
            ast.literal_eval(constants["OBSERVER_EFFECT_FIELDS"])
            != effects[2:3] + effects[5:]
        ):
            failures.append("S1 accepted observer effect fields drift")
    except (KeyError, ValueError, TypeError):
        failures.append("S1 accepted observer effect fields invalid")
    expected_fields = (
        ast.parse(
            "OBSERVATION_FIELDS: Final = ("
            "*EXPECTED_IDENTITY, 'evidence_byte_length', 'evidence_sha256', "
            "'record_count', 'wake_count', 'terminal', 'terminal_kind', "
            "'first_observed_at_utc', 'last_observed_at_utc', 'last_outcome', "
            "'last_stop_reason', 'last_guard_reason', *OBSERVER_EFFECT_FIELDS)"
        )
        .body[0]
        .value
    )
    if "OBSERVATION_FIELDS" not in constants or ast.dump(
        constants["OBSERVATION_FIELDS"]
    ) != ast.dump(expected_fields):
        failures.append("S1 exact observer dictionary shape drift")
    timestamp = functions.get("_timestamp")
    timestamp_comparisons = {
        ast.unparse(node)
        for node in ast.walk(timestamp or tree)
        if isinstance(node, ast.Compare)
    }
    for required in (
        "type(value) is not str",
        "parsed.tzinfo is not UTC",
        "parsed.isoformat().replace('+00:00', 'Z') != value",
    ):
        if required not in timestamp_comparisons:
            failures.append("S1 canonical timestamp policy drift")
    # The observer call must stay in the one-shot top-level try, with no retry.
    expected_observe = ast.parse(
        "try:\n    observation = observer.observe()\n"
        "except Exception:\n"
        "    result.update(reason='observer_blocked', "
        "detail='Read-only observation failed.')\n    return result"
    ).body[0]
    if (
        preflight is None
        or len(preflight.body) != 7
        or ast.dump(preflight.body[2]) != ast.dump(expected_observe)
    ):
        failures.append("S1 observation must remain one-shot with bounded failure")
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
        "observation['record_count'] != 3 * observation['wake_count']",
        "type(observation['wake_count']) is not int",
        "observation['wake_count'] < 1",
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
            failures.append(f"S1 acceptance policy drift: {required}")
    expected_health_gate = ast.parse(
        "if (type(observation['wake_count']) is not int "
        "or observation['wake_count'] < 1 "
        "or type(observation['record_count']) is not int "
        "or observation['record_count'] != 3 * observation['wake_count'] "
        "or observation['terminal'] is not False "
        "or observation['terminal_kind'] is not None "
        "or type(observation['last_outcome']) is not str "
        "or observation['last_outcome'] not in ('COMPLETED', 'NO_ACTION') "
        "or observation['last_stop_reason'] is not None "
        "or observation['last_guard_reason'] is not None):\n    raise ValueError"
    ).body[0]
    validation = (
        preflight.body[4]
        if preflight is not None and len(preflight.body) == 7
        else None
    )
    if (
        not isinstance(validation, ast.Try)
        or len(validation.body) != 13
        or ast.dump(validation.body[6]) != ast.dump(expected_health_gate)
    ):
        failures.append("S1 healthy relation must reject every unhealthy observation")
    expected_blocked = ast.parse(
        "try:\n    pass\nexcept Exception:\n"
        "    result.update(reason=reason, "
        "detail='Read-only soak status policy blocked.')\n    return result"
    ).body[0]
    if (
        not isinstance(validation, ast.Try)
        or ast.dump(ast.Module(body=validation.handlers, type_ignores=[]))
        != ast.dump(ast.Module(body=expected_blocked.handlers, type_ignores=[]))
        or validation.orelse
        or validation.finalbody
    ):
        failures.append("S1 validation failure must return bounded BLOCKED")
    expected_rollup = ast.parse(
        "result.update(status='PASS', soak_state='HEALTHY', "
        "accepted_wake_count=observation['wake_count'], "
        "durable_record_count=observation['record_count'], "
        "last_outcome=observation['last_outcome'], "
        "first_observed_at_utc=observation['first_observed_at_utc'], "
        "last_observed_at_utc=observation['last_observed_at_utc'], "
        "evidence_byte_length=observation['evidence_byte_length'], "
        "evidence_sha256=observation['evidence_sha256'], "
        "observation=dict(observation))"
    ).body[0]
    if (
        preflight is None
        or len(preflight.body) != 7
        or ast.dump(preflight.body[5]) != ast.dump(expected_rollup)
        or ast.unparse(preflight.body[6]) != "return result"
    ):
        failures.append("S1 sanitized rollup or closed result effects drift")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.decorator_list or isinstance(node, ast.AsyncFunctionDef):
                failures.append("S1 contains an unreviewed function binding")
        if isinstance(node, ast.Assign):
            if any(not isinstance(target, ast.Name) for target in node.targets):
                failures.append("S1 contains an unreviewed object mutation")
            if any(
                isinstance(target, ast.Name)
                and target.id in {*constants, "observer", "datetime", "re"}
                for target in node.targets
            ):
                failures.append("S1 frozen source binding drift")
    wrapper = _top_level_functions(runner_tree).get("_d10_soak_status_preflight")
    if wrapper is None:
        failures.append("S1 runner missing read-only wrapper")
    else:
        wrapper_imports = [
            ast.unparse(node)
            for node in ast.walk(wrapper)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        if wrapper_imports != [
            "from scripts import d10_soak_status_readonly as admission"
        ]:
            failures.append("S1 wrapper contains unreviewed imports")
        for node in ast.walk(wrapper):
            if isinstance(node, ast.Call) and ast.unparse(node.func) not in {
                "admission.preflight",
                "_require_not_run",
                "primary.get",
                "type",
                "RuntimeError",
            }:
                failures.append("S1 wrapper contains direct host/effect authority")
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
                failures.append("S1 wrapper effect-field closure drift")
        except (IndexError, ValueError, TypeError):
            failures.append("S1 wrapper effect-field closure invalid")
    expected_wrapper = ast.parse(
        "def _d10_soak_status_preflight() -> dict[str, object]:\n"
        "    from scripts import d10_soak_status_readonly as admission\n"
        "    primary = admission.preflight()\n"
        "    if type(primary) is not dict:\n"
        "        raise RuntimeError("
        "'S1 preflight result must be an exact dictionary')\n"
        f"    _require_not_run(primary, {effects!r})\n"
        "    return {'status': primary.get('status'), 'primary': primary}"
    ).body[0]
    if wrapper is None or ast.dump(wrapper) != ast.dump(expected_wrapper):
        failures.append("S1 exact read-only wrapper contract drift")
    registrations = [
        node
        for node in ast.walk(runner_tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "CheckpointSpec"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "d10-soak-status"
            for keyword in node.keywords
        )
    ]
    if len(registrations) != 1:
        failures.append("S1 registration missing or duplicated")
    else:
        keywords = {
            keyword.arg: ast.unparse(keyword.value)
            for keyword in registrations[0].keywords
        }
        for field, expected in (
            ("preflight", "_d10_soak_status_preflight"),
            ("authority_check", "_d10_soak_status_authority_check"),
            ("remote_branch", "'feature/post-d10-observability'"),
        ):
            if keywords.get(field) != expected:
                failures.append(f"S1 registration drift: {field}")
        if "execute" in keywords or "remote_head_env" in keywords:
            failures.append("S1 must have no execute or remote handoff surface")
    spec = _checkpoint_specs()["d10-soak-status"]
    if spec.execute is not None or spec.preflight is not _d10_soak_status_preflight:
        failures.append("S1 runtime registration must remain preflight-only")
    return tuple(failures)


def _d10_soak_review_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Freeze S2A's pure policy and verify-only side-branch registration."""
    try:
        tree = ast.parse(
            (repo_root / "scripts/d10_end_of_soak_review.py").read_text(
                encoding="utf-8"
            )
        )
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
    except (OSError, SyntaxError):
        return ("S2A source missing or invalid",)
    failures: list[str] = []
    imports = {
        "from __future__ import annotations",
        "from datetime import UTC, datetime",
        "from typing import Final",
        "from trading_bot.runtime.personal_desktop_unattended_one_week_soak "
        "import D10OneWeekWakeEvidence, D10OneWeekWakeSummary, D10WakeOutcome, "
        "build_d10_one_week_wake_summary",
    }
    actual_imports = {
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    }
    if actual_imports != imports:
        failures.append("S2A contains unreviewed imports")
    allowed_calls = {
        "datetime",
        "type",
        "any",
        "_blocked",
        "_utc",
        "_timestamp",
        "value.isoformat",
        "value.isoformat(timespec='microseconds').replace",
        "build_d10_one_week_wake_summary",
    }
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    if any(ast.unparse(node.func) not in allowed_calls for node in calls):
        failures.append("S2A contains unreviewed I/O or effect calls")
    summary_calls = [
        node
        for node in calls
        if ast.unparse(node.func) == "build_d10_one_week_wake_summary"
    ]
    if len(summary_calls) != 1 or ast.unparse(summary_calls[0]) != (
        "build_d10_one_week_wake_summary(wakes)"
    ):
        failures.append("S2A must use the existing summary exactly once")
    # Pin the complete reviewed semantic AST, including all module statements.
    # This freezes exact input types, UTC review >= end, current-soak constants,
    # seven-wake minimum (never equality/coverage), provenance, nonterminal
    # outcomes, zero recovery/broker calls, final eight gates, external review,
    # and False/False/True acceptance/authorization/operator-decision fields.
    # Whitespace is irrelevant; every semantic addition or policy drift blocks.
    expected_ast_sha256 = (
        "81c49c386d2122f26071971be92ce479e321aa5c28dce7858541f7abb08c52a5"
    )
    actual_ast_sha256 = hashlib.sha256(ast.dump(tree).encode("utf-8")).hexdigest()
    if actual_ast_sha256 != expected_ast_sha256:
        failures.append("S2A frozen pure operator-review policy drift")

    registrations = [
        node
        for node in ast.walk(runner_tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "CheckpointSpec"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "d10-soak-review"
            for keyword in node.keywords
        )
    ]
    if len(registrations) != 1:
        failures.append("S2A registration missing or duplicated")
    else:
        expected = {
            "name": "'d10-soak-review'",
            "description": "'D10 pure end-of-soak operator-review source gate'",
            "tests": "soak_review_tests",
            "ruff_paths": "soak_review_ruff",
            "authority_check": "_d10_soak_review_authority_check",
            "remote_branch": "'feature/post-d10-observability'",
        }
        actual = {
            keyword.arg: ast.unparse(keyword.value)
            for keyword in registrations[0].keywords
        }
        if registrations[0].args or actual != expected:
            failures.append("S2A must remain verify-only with exact side registration")
    spec = _checkpoint_specs()["d10-soak-review"]
    if (
        spec.preflight is not None
        or spec.execute is not None
        or spec.remote_head_env is not None
        or spec.remote_branch != "feature/post-d10-observability"
    ):
        failures.append("S2A runtime registration must remain verify-only")
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


def _d10_soak_status_preflight() -> dict[str, object]:
    from scripts import d10_soak_status_readonly as admission

    primary = admission.preflight()
    if type(primary) is not dict:
        raise RuntimeError("S1 preflight result must be an exact dictionary")
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
    soak_status_tests = (
        *COMMON_TESTS,
        "tests/runtime/test_d10_soak_status_readonly.py",
        "tests/runtime/test_d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_durable_wake_evidence_observe.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
    )
    soak_status_ruff = (
        *COMMON_RUFF_PATHS,
        "scripts/d10_soak_status_readonly.py",
        "tests/runtime/test_d10_soak_status_readonly.py",
    )
    soak_review_tests = (
        *soak_status_tests,
        "tests/runtime/test_d10_end_of_soak_review.py",
        "tests/runtime/test_personal_desktop_unattended_one_week_soak_source.py",
        "tests/runtime/test_personal_desktop_unattended_one_week_soak_controller.py",
    )
    soak_review_ruff = (
        *COMMON_RUFF_PATHS,
        "scripts/d10_end_of_soak_review.py",
        "tests/runtime/test_d10_end_of_soak_review.py",
    )
    return {
        "d10-soak-status": CheckpointSpec(
            name="d10-soak-status",
            description="D10 read-only status of accepted durable wakes",
            tests=soak_status_tests,
            ruff_paths=soak_status_ruff,
            authority_check=_d10_soak_status_authority_check,
            preflight=_d10_soak_status_preflight,
            remote_branch="feature/post-d10-observability",
        ),
        "d10-soak-review": CheckpointSpec(
            name="d10-soak-review",
            description="D10 pure end-of-soak operator-review source gate",
            tests=soak_review_tests,
            ruff_paths=soak_review_ruff,
            authority_check=_d10_soak_review_authority_check,
            remote_branch="feature/post-d10-observability",
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
    args = _parser(specs).parse_args(argv)

    if args.command == "status":
        return _status(repo_root, specs)

    spec = specs[args.checkpoint]
    evidence_root = (
        args.evidence_root
        if args.evidence_root is not None
        else _default_evidence_root(repo_root)
    )

    try:
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
