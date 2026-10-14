"""Noninteractive D1R5 host; real bounded clock/sleep and external journal only."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.review_paper.pre_market_wake_qualification import (
    QUALIFY_WAKE_INTERLOCK,
    WakeClassification,
    qualify_pre_market_wake,
    validate_source_identity,
)

BRANCH = "feature/robinhood-production-paper-premarket-wake-qualification"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-premarket-wake-qualification"
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid wake qualification arguments")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        description="D1R5: qualify one bounded pre-market wake; no D1 authority.",
        allow_abbrev=False,
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument(
        "--qualify-wake", required=True, choices=(QUALIFY_WAKE_INTERLOCK,)
    )
    return parser


def admit_wake_source(head: str, tree: str) -> tuple[Path, ...]:
    """Require published exact local/tracking/live-origin source and unmixed imports."""
    validate_source_identity(head)
    validate_source_identity(tree)
    root = Path(__file__).resolve().parents[3]
    if os.name != "nt" or root != WORKTREE.resolve():
        raise ValueError("wake qualification host mismatch")

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()

    if (
        Path(git("rev-parse", "--show-toplevel")).resolve() != root
        or git("branch", "--show-current") != BRANCH
        or git("rev-parse", "HEAD") != head
        or git("rev-parse", "HEAD^{tree}") != tree
        or git("status", "--porcelain=v1", "--untracked-files=all")
        or git("remote", "get-url", "origin") != ORIGIN
        or git("rev-parse", "origin/" + BRANCH) != head
        or git("rev-parse", "origin/" + BRANCH + "^{tree}") != tree
        or git("ls-remote", "origin", "refs/heads/" + BRANCH)
        != head + "\trefs/heads/" + BRANCH
    ):
        raise ValueError("wake qualification source mismatch")
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(
                root / "src"
            ):
                raise ValueError("mixed wake qualification import roots")
    roots = tuple(
        Path(line.removeprefix("worktree ")).resolve()
        for line in git("worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    )
    if root not in roots:
        raise ValueError("wake qualification repository boundaries unavailable")
    return roots


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        result = qualify_pre_market_wake(
            expected_head=args.expected_head,
            expected_tree=args.expected_tree,
            qualify_wake=args.qualify_wake,
            evidence=args.evidence,
            admit_source=lambda: admit_wake_source(
                args.expected_head, args.expected_tree
            ),
            clock=lambda: datetime.now(UTC),
            sleeper=time.sleep,
        )
        print("PRE_MARKET_WAKE_QUALIFICATION_" + result.value)
        return 0 if result is WakeClassification.PASS else 1
    except (Exception, KeyboardInterrupt):
        print("PRE_MARKET_WAKE_QUALIFICATION_HOST_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
