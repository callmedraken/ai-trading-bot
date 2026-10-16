"""Invoke the pinned canonical pure builder without importing writer packages.

Only its exact FunctionDef is compiled, unchanged. All names are bound to the
accepted inert verifier models. No imports or other canonical module statements
are executed. The full canonical AST is pinned before selecting that function.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from trading_bot.arch133_verifier.activation import ReviewPaperActivation
from trading_bot.arch133_verifier.scheduler import UnattendedSchedulerSpec
from trading_bot.arch133_verifier.sessions import NYSEPublishedRegularSessionAuthority

CANONICAL_AST_SHA256 = (
    "79fe37f5e4c36c70096f86414f5e32151556c617b82bc086742a44470c7dde29"
)


def build_unattended_scheduler_spec(
    activation: ReviewPaperActivation,
) -> UnattendedSchedulerSpec:
    path = Path(__file__).resolve().parents[1] / "review_paper/unattended_scheduler.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if (
        hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
        != CANONICAL_AST_SHA256
    ):
        raise ValueError("canonical scheduler source drift")
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "build_unattended_scheduler_spec"
    )
    namespace = {
        "ReviewPaperActivation": ReviewPaperActivation,
        "UnattendedSchedulerSpec": UnattendedSchedulerSpec,
        "NYSEPublishedRegularSessionAuthority": NYSEPublishedRegularSessionAuthority,
    }
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"),
        namespace,
    )
    return namespace["build_unattended_scheduler_spec"](activation)
