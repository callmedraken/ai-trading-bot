"""Noninteractive D1R3 host; one external evidence file, no D1 launch."""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path

from trading_bot.market_data.alpaca_http import StdlibAlpacaHistoricalBarsTransport
from trading_bot.review_paper.alpaca_authentication_qualification import (
    QUALIFY_AUTH_INTERLOCK,
    qualify_alpaca_authentication,
    serialize_authentication_qualification,
)

BRANCH = "feature/robinhood-production-paper-alpaca-auth-qualification"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-alpaca-auth-qualification"
)
PRODUCTION_ROOT = Path(r"F:\AITradingBot")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid qualification arguments")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        description="Qualify one fixed Alpaca history authentication probe."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument(
        "--qualify-auth", required=True, choices=(QUALIFY_AUTH_INTERLOCK,)
    )
    return parser


def admit_authentication_source(head: str, tree: str) -> tuple[Path, ...]:
    """Exact executing/local/live-origin source, with unmixed package roots."""
    root = Path(__file__).resolve().parents[3]
    for value in (head, tree):
        if (
            type(value) is not str
            or len(value) != 40
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError("invalid source identity")
    if os.name != "nt" or root != WORKTREE.resolve():
        raise ValueError("qualification host mismatch")

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
        raise ValueError("qualification source mismatch")
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(
                root / "src"
            ):
                raise ValueError("mixed qualification import roots")
    roots = tuple(
        Path(line.removeprefix("worktree ")).resolve()
        for line in git("worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    )
    if root not in roots:
        raise ValueError("qualification repository boundaries unavailable")
    return roots


def admit_authentication_evidence(path: Path, roots: tuple[Path, ...]) -> Path:
    """Existing real external parent, fresh file, no linked/reparse ancestors."""
    if not isinstance(path, Path) or not path.is_absolute() or path.suffix != ".json":
        raise ValueError("invalid qualification evidence destination")
    resolved = path.resolve()
    if any(resolved.is_relative_to(root.resolve()) for root in roots) or (
        resolved.is_relative_to(PRODUCTION_ROOT.resolve())
    ):
        raise ValueError("qualification evidence must be external")
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("qualification evidence must be fresh")
    for parent in path.parents:
        metadata = parent.lstat()
        if stat.S_ISLNK(metadata.st_mode) or (
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError("linked qualification evidence parent")
    return resolved


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        roots = admit_authentication_source(args.expected_head, args.expected_tree)
        destination = admit_authentication_evidence(args.evidence, roots)
        # Reserve exclusive evidence ownership BEFORE any credentials or provider read.
        # Failure/crash consumes this destination; never reopen or overwrite it.
        with destination.open("xb") as output:
            result = qualify_alpaca_authentication(
                expected_head=args.expected_head,
                expected_tree=args.expected_tree,
                qualify_auth=args.qualify_auth,
                admit_source=lambda: admit_authentication_source(
                    args.expected_head, args.expected_tree
                ),
                transport=StdlibAlpacaHistoricalBarsTransport(),
            )
            payload = serialize_authentication_qualification(result)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        print(payload.decode("utf-8"), end="")
        return 0 if result.status == "PASS" else 1
    except Exception:
        # Never format an exception, source command output, path, or upstream text.
        print("ALPACA_AUTH_QUALIFICATION_HOST_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
