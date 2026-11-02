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
        or runner.execute_checkpoint is not runner._arch147_p6_execute_checkpoint
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


def _runner_callable_matches(
    value: object, expected_name: str, repo_root: Path
) -> bool:
    code = getattr(value, "__code__", None)
    return bool(
        callable(value)
        and getattr(value, "__name__", None) == expected_name
        and code is not None
        and Path(code.co_filename).resolve()
        == (repo_root / "scripts/checkpoint_runner.py").resolve()
    )


def _same_p6_registration(spec: object, canonical: object, repo_root: Path) -> bool:
    """Match P6 registration semantics without relying on module identity."""
    from scripts import checkpoint_runner as runner

    try:
        if any(
            getattr(spec, field) != getattr(canonical, field)
            for field in (
                "name",
                "description",
                "tests",
                "ruff_paths",
                "remote_branch",
                "remote_head_env",
            )
        ):
            return False
        return (
            _runner_callable_matches(
                spec.authority_check,
                "_arch147_p6_authority_check",
                repo_root,
            )
            and _runner_callable_matches(
                spec.preflight,
                "_arch147_p6_preflight",
                repo_root,
            )
            and _runner_callable_matches(
                spec.execute,
                "_arch147_p6_execute",
                repo_root,
            )
            and canonical.authority_check is runner._arch147_p6_authority_check
            and canonical.preflight is runner._arch147_p6_preflight
            and canonical.execute is runner._arch147_p6_execute
        )
    except AttributeError:
        return False


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


def _require_p6_source_admission(
    spec: object,
    *,
    repo_root: Path,
    before: dict[str, object],
    evidence_root: Path | None = None,
) -> None:
    """Require one clean, integrated, current-authority source before an attempt."""
    from scripts import checkpoint_runner as runner

    canonical = runner._checkpoint_specs()[runner.ARCH147_P6_NAME]
    if not _same_p6_registration(spec, canonical, repo_root) or authority_failures(
        repo_root
    ):
        raise RuntimeError("P6 source registration rejected")
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
    feature = runner._remote_branch_head(repo_root, runner.ARCH147_P6_BRANCH)
    develop = runner._remote_branch_head(repo_root, "develop")
    if feature != before["head"] or develop != before["head"]:
        raise RuntimeError("P6 accepted develop integration required")
    from scripts.current_source_authority import (
        PublicationContext,
        evaluate_source_authority,
    )

    authority = evaluate_source_authority(
        candidate_source=repo_root,
        publication_context=PublicationContext.PROSPECTIVE_DEVELOP,
    )
    if not authority.passed:
        raise RuntimeError("P6 integrated source authority rejected")
    if evidence_root is not None:
        _external_evidence_root(repo_root, evidence_root)


def require_protected_execution_source(
    spec: object,
    *,
    repo_root: Path,
    evidence_root: Path,
    state: dict[str, object],
) -> None:
    """Apply P6 source admission immediately before the runner attempt marker."""
    _require_p6_source_admission(
        spec,
        repo_root=repo_root,
        before=state,
        evidence_root=evidence_root,
    )


def run_preflight(
    spec: object, *, repo_root: Path, evidence_root: Path
) -> tuple[bool, Path | None]:
    """Run the reviewed P6 preflight only when explicitly requested."""

    from scripts import checkpoint_runner as runner

    before = runner._git_state(repo_root)
    _require_p6_source_admission(
        spec,
        repo_root=repo_root,
        before=before,
        evidence_root=evidence_root,
    )
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
