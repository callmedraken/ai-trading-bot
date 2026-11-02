"""Current P5B source owner and unified-runner protected-read admission."""

from __future__ import annotations

import ast
import json
import os
import stat
from pathlib import Path

READ_TOOLS = (
    "get_accounts",
    "get_portfolio",
    "get_equity_positions",
    "get_equity_quotes",
    "get_equity_orders",
)
BASE = "6924085675d9058b79324120faec9cb4025b6329"
FROZEN_TRANSPORT = "src/trading_bot/robinhood_mcp/sdk_transport.py"
P5B_MODULES = (
    "src/trading_bot/robinhood_mcp/current_read_transport.py",
    "src/trading_bot/desktop_paper/robinhood_read.py",
    "src/trading_bot/desktop_paper/robinhood_reconciliation.py",
    "src/trading_bot/desktop_paper/robinhood_preflight.py",
)


def authority_failures(repo_root: Path) -> tuple[str, ...]:
    """Inspect source and immutable Git only; no provider/credential imports."""
    from scripts import checkpoint_runner as runner
    from scripts import run_test_certification as certification

    spec = runner._checkpoint_specs().get(runner.ARCH147_P5B_NAME)
    failures = []
    if (
        spec is None
        or spec.tests != runner.ARCH147_P5B_TESTS
        or spec.ruff_paths != runner.ARCH147_P5B_RUFF
        or spec.authority_check is not runner._arch147_p5b_authority_check
        or spec.remote_branch != runner.ARCH147_P5B_BRANCH
        or spec.preflight is not runner._arch147_p5b_preflight
        or spec.execute is not None
        or spec.remote_head_env is not None
        or runner.CURRENT_ACTIVE_CI_CHECKPOINTS[0] != runner.ARCH147_P5B_NAME
        or runner.CURRENT_ACTIVE_CI_CHECKPOINTS.count(runner.ARCH147_P5B_NAME) != 1
        or runner.CI_CERTIFICATION_PROFILES.get(runner.ARCH147_P5B_NAME) != "full"
        or runner.resolve_ci_checkpoint(
            runner._checkpoint_specs(), runner.ARCH147_P5B_BRANCH, "push"
        )
        != runner.ARCH147_P5B_NAME
    ):
        failures.append("147 P5B registration drift")
    inventory = set(
        certification.select_inventory(
            certification.discover_inventory(repo_root), "full"
        )
    )
    if (
        spec is not None
        and not (set(spec.tests) - set(runner.ARCH147_P5A_TESTS)) <= inventory
    ):
        failures.append("147 P5B tests missing FULL ownership")
    if runner._git_output(
        repo_root, "hash-object", FROZEN_TRANSPORT
    ) != runner._git_output(repo_root, "rev-parse", BASE + ":" + FROZEN_TRANSPORT):
        failures.append("147 P5B frozen 131 transport changed")
    workflow = (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    if not runner._arch147_current_batch_workflow_is_reviewed(workflow):
        failures.append("147 P5B workflow drift")
    forbidden = (
        "review_equity_order",
        "place_equity_order",
        "cancel_equity_order",
        "place_option_order",
        "cancel_option_order",
        "exercise_option",
        "place_crypto_order",
        "cancel_crypto_order",
    )
    for relative in P5B_MODULES:
        path = repo_root / relative
        if not path.is_file():
            failures.append("147 P5B missing source: " + relative)
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                failures.append("147 P5B mutation/review reference")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                claims = [a.name for a in node.names]
                if isinstance(node, ast.ImportFrom):
                    claims.append(node.module or "")
                    if (
                        node.module == "trading_bot.robinhood_mcp.sdk_transport"
                        and claims != ["ROBINHOOD_TRADING_MCP_URL", node.module]
                    ):
                        failures.append("147 P5B frozen transport private dependency")
                if any(
                    word in c.lower()
                    for c in claims
                    for word in (
                        "alpaca",
                        "final_holdout",
                        "sqlite",
                        "desktop_paper.engine",
                        "desktop_paper.store",
                        "desktop_paper.worker",
                    )
                ):
                    failures.append("147 P5B forbidden effect dependency")
        if relative.endswith("current_read_transport.py"):
            declarations = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
            transport = declarations.get("RobinhoodCurrentReadTransport")
            public = (
                set()
                if transport is None
                else {
                    n.name
                    for n in transport.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not n.name.startswith("_")
                }
            )
            if public != {
                *READ_TOOLS,
                "for_test",
                "call_counts",
                "observed_read_tools",
            }:
                failures.append("147 P5B read facade drift")
            tool_values = [
                n.value
                for n in tree.body
                if isinstance(n, ast.AnnAssign)
                and isinstance(n.target, ast.Name)
                and n.target.id == "READ_TOOLS"
            ]
            if len(tool_values) != 1 or ast.literal_eval(tool_values[0]) != READ_TOOLS:
                failures.append("147 P5B read allowlist drift")
    # P5A code cannot gain a dependency on any new read/preflight successor.
    for path in (repo_root / "src/trading_bot/desktop_paper").glob("*.py"):
        if str(path.relative_to(repo_root)).replace("\\", "/") in P5B_MODULES:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and "robinhood" in (node.module or ""):
                failures.append("147 P5A depends on broker context")
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


def _same_p5b_registration(spec: object, canonical: object, repo_root: Path) -> bool:
    """Match P5B registration without relying on duplicate module identity."""
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
            )
        ):
            return False
        if not (
            spec.remote_head_env is canonical.remote_head_env is None
            and spec.execute is canonical.execute is None
        ):
            return False
        return (
            _runner_callable_matches(
                spec.authority_check,
                "_arch147_p5b_authority_check",
                repo_root,
            )
            and _runner_callable_matches(
                spec.preflight,
                "_arch147_p5b_preflight",
                repo_root,
            )
            and canonical.authority_check is runner._arch147_p5b_authority_check
            and canonical.preflight is runner._arch147_p5b_preflight
        )
    except AttributeError:
        return False


def _external_evidence_root(repo_root: Path, evidence_root: Path) -> None:
    production = Path(r"F:\AI\desktop-bot-state")
    if (
        not evidence_root.is_absolute()
        or ".." in evidence_root.parts
        or any(
            evidence_root == p
            or p in evidence_root.parents
            or evidence_root in p.parents
            for p in (repo_root, production)
        )
    ):
        raise RuntimeError("P5B external evidence root rejected")
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
            raise RuntimeError("P5B evidence alias rejected")


def run_preflight(
    spec: object, *, repo_root: Path, evidence_root: Path
) -> tuple[bool, Path | None]:
    """Source gate before the single credential/provider read sequence.

    Feature and develop must identify the same exact accepted source. This
    guard supplies no review authorization; the operator invokes it only after
    the separate ChatGPT source/effect review. Never call from source gates.
    """
    from scripts import checkpoint_runner as runner

    canonical = runner._checkpoint_specs()[runner.ARCH147_P5B_NAME]
    if not _same_p5b_registration(spec, canonical, repo_root) or authority_failures(
        repo_root
    ):
        raise RuntimeError("P5B source registration rejected")
    resolved = repo_root.resolve()
    if resolved != Path(r"F:\AI\ai-trading-bot") and resolved.parent != Path(
        r"F:\AI\worktrees"
    ):
        raise RuntimeError("P5B worktree root rejected")
    before = runner._git_state(repo_root)
    if before["porcelain"] or before["branch"] not in (
        "develop",
        runner.ARCH147_P5B_BRANCH,
        "HEAD",
    ):
        raise RuntimeError("P5B clean source required")
    if (
        runner._git_output(repo_root, "remote", "get-url", "origin")
        != "https://github.com/callmedraken/ai-trading-bot.git"
    ):
        raise RuntimeError("P5B origin rejected")
    feature = runner._remote_branch_head(repo_root, runner.ARCH147_P5B_BRANCH)
    develop = runner._remote_branch_head(repo_root, "develop")
    if feature != before["head"] or develop != before["head"]:
        raise RuntimeError("P5B accepted develop integration required")
    from scripts.current_source_authority import (
        PublicationContext,
        evaluate_source_authority,
    )

    authority = evaluate_source_authority(
        candidate_source=repo_root,
        publication_context=PublicationContext.PROSPECTIVE_DEVELOP,
    )
    if not authority.passed:
        raise RuntimeError("P5B integrated source authority rejected")
    _external_evidence_root(repo_root, evidence_root)
    directory = evidence_root / spec.name / ("preflight-" + runner._stamp())
    directory.mkdir(parents=True, exist_ok=False)
    # A consumed attempt remains visible even if the process is interrupted.
    with (directory / "attempt.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "checkpoint": spec.name,
                "head": before["head"],
                "tree": before["tree"],
                "status": "ATTEMPT_STARTED_NO_RETRY",
            },
            stream,
            sort_keys=True,
        )
        stream.flush()
        os.fsync(stream.fileno())
    result = spec.preflight()
    after = runner._git_state(repo_root)
    stable = (
        before == after
        and runner._remote_branch_head(repo_root, "develop") == develop
        and runner._remote_branch_head(repo_root, runner.ARCH147_P5B_BRANCH) == feature
    )
    passed = result.get("status") == "PASS" and stable
    report = {
        "schema": "arch147-p5b-robinhood-read-reconcile/v1",
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
