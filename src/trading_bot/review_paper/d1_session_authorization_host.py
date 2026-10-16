"""Fixed D1R7 host: Git/clock/evidence only; import is inert."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.review_paper import d1_session_authorization as gate

WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-authorization"
)
D1_WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-execution"
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()


def admit_source(source: gate.Source) -> tuple[Path, ...]:
    """Independently prove local, tracking and live identity on either fixed branch."""
    if source.branch not in (gate.BRANCH, gate.D1_BRANCH):
        raise ValueError("fixed branch required")
    own = Path(__file__).resolve().parents[3]
    if os.name != "nt" or own != WORKTREE.resolve():
        raise ValueError("fixed Windows source location required")
    root = (WORKTREE if source.branch == gate.BRANCH else D1_WORKTREE).resolve()
    branch = source.branch
    if (
        Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root
        or _git(root, "branch", "--show-current") != branch
        or _git(root, "rev-parse", "HEAD") != source.head
        or _git(root, "rev-parse", "HEAD^{tree}") != source.tree
        or _git(root, "status", "--porcelain=v1", "--untracked-files=all")
        or _git(root, "remote", "get-url", "origin") != gate.ORIGIN
        or _git(root, "remote", "get-url", "--push", "origin") != gate.ORIGIN
        or _git(root, "rev-parse", "--symbolic-full-name", "@{upstream}")
        != "refs/remotes/origin/" + branch
        or _git(root, "rev-parse", "origin/" + branch) != source.head
        or _git(root, "rev-parse", "origin/" + branch + "^{tree}") != source.tree
        or _git(root, "ls-remote", "origin", "refs/heads/" + branch)
        != source.head + "\trefs/heads/" + branch
    ):
        raise ValueError("source identity drift")
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(own / "src"):
                raise ValueError("mixed source imports")
            for location in getattr(module, "__path__", ()):
                if not Path(location).resolve().is_relative_to(own / "src"):
                    raise ValueError("mixed package path")
    roots = tuple(
        Path(line[9:]).resolve()
        for line in _git(root, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    )
    if root not in roots or own not in roots:
        raise ValueError("worktree registry drift")
    return roots


class EvidenceRuntime:
    """The only production runtime capabilities are clock and Git admission."""

    parent = gate.PARENT

    def admit(self, source: gate.Source) -> tuple[Path, ...]:
        return admit_source(source)

    def clock(self) -> datetime:
        return datetime.now(UTC)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("D1R7 arguments rejected")


def build_parser() -> argparse.ArgumentParser:
    """No caller target date, destination, branch, policy or effect selection."""
    parser = _Parser(allow_abbrev=False)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--accepted-d1-head", required=True)
    parser.add_argument("--accepted-d1-tree", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Future reviewed publication only; accepted D1 pins are review assertions."""
    try:
        args = build_parser().parse_args(argv)
        source = gate.Source(gate.BRANCH, args.expected_head, args.expected_tree)
        intended = gate.Source(
            gate.D1_BRANCH, args.accepted_d1_head, args.accepted_d1_tree
        )
        # Real human authorization cannot be piped or confused with the D1 interlock.
        if not sys.stdin.isatty():
            raise ValueError("interactive D1R7 authorization required")
        interlock = input("D1R7 prerequisite record authorization: ")
        result = gate.publish_prerequisite(
            EvidenceRuntime(), source, intended, interlock
        )
        print(result)
        return 0
    except (Exception, KeyboardInterrupt):
        print("D1R7_STOP_NO_D1_AUTHORITY", file=sys.stderr)
        return 2
