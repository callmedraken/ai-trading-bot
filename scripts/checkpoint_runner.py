"""Unified source-checkpoint runner for AI Trading Bot development.

This module centralizes source-only verification. It intentionally does not
provide protected production execution in its first version. Local Windows host
preflight and protected actions will be added as separately reviewed commands.
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

SCHEMA: Final = "ai-trading-bot-checkpoint-runner/v1"


@dataclass(frozen=True, slots=True)
class CheckpointSpec:
    name: str
    description: str
    tests: tuple[str, ...]
    ruff_paths: tuple[str, ...]
    authority_check: Callable[[Path], tuple[str, ...]]


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
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


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
        failures.append(
            f"protected mode missing fixed bindings: {missing_execute}"
        )

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
            failures.append(f"operator contains forbidden authority surface: {forbidden}")

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

    return tuple(failures)


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
    return {
        "arch128-parent-acl-repair": CheckpointSpec(
            name="arch128-parent-acl-repair",
            description="Architecture 128 exact parent-ACL repair source gate",
            tests=parent_tests,
            ruff_paths=parent_ruff,
            authority_check=_parent_acl_authority_check,
        ),
        "arch128-r4": CheckpointSpec(
            name="arch128-r4",
            description="Architecture 128 protected replacement source gate",
            tests=r4_tests,
            ruff_paths=r4_ruff,
            authority_check=_r4_authority_check,
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
            "source gate requires a clean worktree; "
            f"found: {state_before['porcelain']}"
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


def _status(repo_root: Path, specs: Mapping[str, CheckpointSpec]) -> int:
    state = _git_state(repo_root)
    print(f"SCHEMA={SCHEMA}")
    print(f"REPO={repo_root}")
    print(f"HEAD={state['head']}")
    print(f"TREE={state['tree']}")
    print(f"BRANCH={state['branch']}")
    print(f"CLEAN={not bool(state['porcelain'])}")
    print("PROTECTED_EXECUTION=NOT_IMPLEMENTED_IN_UNIFIED_RUNNER_V1")
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
        passed, _ = verify_checkpoint(
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
