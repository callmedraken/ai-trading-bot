"""Static source owner and explicit operator-boundary runner for P6."""

from __future__ import annotations

import ast
import json
import os
import stat
from pathlib import Path

P6_BASE = "7ff86d06a99bcdf349d5e20846d139a554d8be46"
P6_MODULES = (
    "src/trading_bot/robinhood_mcp/current_live_transport.py",
    "src/trading_bot/desktop_live/__init__.py",
    "src/trading_bot/desktop_live/configuration.py",
    "src/trading_bot/desktop_live/strategy.py",
    "src/trading_bot/desktop_live/models.py",
    "src/trading_bot/desktop_live/risk.py",
    "src/trading_bot/desktop_live/preflight.py",
    "src/trading_bot/desktop_live/execution.py",
    "src/trading_bot/gui/live_state.py",
)


def authority_failures(repo_root: Path) -> tuple[str, ...]:
    """Inspect only source, Git identity, and workflow registration."""

    from scripts import checkpoint_runner as runner

    failures: list[str] = []
    spec = runner._checkpoint_specs().get(runner.ARCH147_P6_NAME)
    if (
        spec is None
        or spec.tests != runner.ARCH147_P6_TESTS
        or spec.ruff_paths != runner.ARCH147_P6_RUFF
        or spec.authority_check is not runner._arch147_p6_authority_check
        or spec.preflight is not runner._arch147_p6_preflight
        or spec.execute is not runner._arch147_p6_execute
        or spec.remote_branch != runner.ARCH147_P6_BRANCH
        or spec.remote_head_env is not None
        or runner.CURRENT_ACTIVE_CI_CHECKPOINTS[0] != runner.ARCH147_P6_NAME
        or runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(runner.ARCH147_P6_NAME) != 1
        or runner.CI_CERTIFICATION_PROFILES.get(runner.ARCH147_P6_NAME) != "full"
        or runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), runner.ARCH147_P6_BRANCH, "push"
        )
        != runner.ARCH147_P6_NAME
    ):
        failures.append("147 P6 registration drift")

    if runner._git_output(repo_root, "merge-base", P6_BASE, "HEAD") != P6_BASE:
        failures.append("147 P6 accepted base drift")

    workflow = (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    row = f"              {runner.ARCH147_P6_NAME} {chr(96)}\n"
    if workflow.count(
        row
    ) != 1 or not runner._arch147_current_batch_workflow_is_reviewed(workflow):
        failures.append("147 P6 workflow projection drift")

    forbidden_import_words = (
        "alpaca",
        "final_holdout",
        "desktop_paper.store",
        "desktop_paper.engine",
        "desktop_paper.worker",
    )
    for relative in P6_MODULES:
        path = repo_root / relative
        if not path.is_file():
            failures.append("147 P6 missing source: " + relative)
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imported = {
            (node.module or "")
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        if any(
            word in module.casefold()
            for module in imported
            for word in forbidden_import_words
        ):
            failures.append("147 P6 forbidden effect dependency: " + relative)
        if "PAPER_EVALUATION" in source and relative.endswith("execution.py"):
            failures.append("147 P6 execution crosses paper binding")

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "compile", "__import__"}:
                    failures.append("147 P6 dynamic execution capability: " + relative)
            if isinstance(node, ast.Attribute) and node.attr in {
                "place_option_order",
                "cancel_option_order",
                "exercise_option",
                "place_crypto_order",
                "cancel_crypto_order",
            }:
                failures.append("147 P6 forbidden order surface: " + relative)

    transport = repo_root / "src/trading_bot/robinhood_mcp/current_live_transport.py"
    if transport.is_file():
        tree = ast.parse(transport.read_text(encoding="utf-8"), filename=str(transport))
        classes = {
            node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
        }
        facade = classes.get("RobinhoodCurrentLiveTransport")
        public = (
            {
                node.name
                for node in facade.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
            }
            if facade is not None
            else set()
        )
        expected = {
            "for_test",
            "call_counts",
            "observed_tools",
            "advertised_schemas",
            "discover_required_capabilities",
            "get_accounts",
            "get_portfolio",
            "get_equity_positions",
            "get_equity_quotes",
            "get_equity_orders",
            "get_equity_historicals",
            "get_equity_tradability",
            "get_trade_approval_setting",
            "review_equity_order",
            "place_equity_order",
            "cancel_equity_order",
        }
        if public != expected or "def call_tool" in transport.read_text(
            encoding="utf-8"
        ):
            failures.append("147 P6 live transport public surface drift")

    live_gui = repo_root / "src/trading_bot/gui/live_state.py"
    if live_gui.is_file() and "QPushButton" in live_gui.read_text(encoding="utf-8"):
        failures.append("147 P6 GUI exposes a placement control")
    return tuple(failures)


def _external_evidence_root(repo_root: Path, evidence_root: Path) -> None:
    if (
        not evidence_root.is_absolute()
        or ".." in evidence_root.parts
        or evidence_root == repo_root
        or repo_root in evidence_root.parents
    ):
        raise RuntimeError("P6 external evidence root rejected")
    for path in (*reversed(evidence_root.parents), evidence_root):
        try:
            fact = path.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(fact.st_mode)
            or getattr(fact, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise RuntimeError("P6 evidence alias rejected")


def run_preflight(
    spec: object, *, repo_root: Path, evidence_root: Path
) -> tuple[bool, Path | None]:
    """Run the reviewed P6 preflight only when explicitly requested."""

    from scripts import checkpoint_runner as runner

    canonical = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    if spec != canonical or authority_failures(repo_root):
        raise RuntimeError("P6 source registration rejected")
    before = runner._git_state(repo_root)
    if before["porcelain"] or before["branch"] not in (
        "develop",
        runner.ARCH147_P6_BRANCH,
        "HEAD",
    ):
        raise RuntimeError("P6 clean source required")
    if runner._git_output(repo_root, "remote", "get-url", "origin") != (
        "https://github.com/callmedraken/ai-trading-bot.git"
    ):
        raise RuntimeError("P6 origin rejected")
    if (
        runner._remote_branch_head(repo_root, runner.ARCH147_P6_BRANCH)
        != before["head"]
    ):
        raise RuntimeError("P6 feature source is not the remote head")
    _external_evidence_root(repo_root, evidence_root)
    directory = evidence_root / spec.name / ("preflight-" + runner._stamp())
    directory.mkdir(parents=True, exist_ok=False)
    with (directory / "attempt.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {"checkpoint": spec.name, "head": before["head"], "status": "STARTED"},
            stream,
            sort_keys=True,
        )
        stream.flush()
        os.fsync(stream.fileno())
    result = spec.preflight()
    after = runner._git_state(repo_root)
    stable = before == after
    passed = result.get("status") == "PASS" and stable
    report = {
        "schema": "arch147-p6-tiny-live/v1",
        "checkpoint": spec.name,
        "source_head": before["head"],
        "source_tree": before["tree"],
        "identity_stable": stable,
        "status": "PASS" if passed else "BLOCKED",
        "result": result,
    }
    path = directory / "report.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(
        f"PREFLIGHT={'PASS' if passed else 'BLOCKED'} "
        f"IDENTITY_STABLE={stable} EVIDENCE={path}"
    )
    return passed, path
