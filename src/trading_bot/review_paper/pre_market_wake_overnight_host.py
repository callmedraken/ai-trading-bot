"""Fixed Windows source/principal/scheduler binding for D1R6; import is inert."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.review_paper import pre_market_wake_overnight as overnight
from trading_bot.review_paper.pre_market_wake_qualification import (
    QUALIFY_WAKE_INTERLOCK,
)

BRANCH = "feature/robinhood-production-paper-overnight-wake-arming"
TARGET_BRANCH = "feature/robinhood-production-paper-premarket-wake-qualification"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"


def admit_source(head: str, tree: str, *, target: bool = False) -> tuple[Path, ...]:
    """Admit exactly one of the two fixed sources; never adopt moved refs."""
    overnight.validate_source_identity(head)
    overnight.validate_source_identity(tree)
    own = Path(__file__).resolve().parents[3]
    if os.name != "nt" or own != Path(overnight.WORKTREE).resolve():
        raise ValueError("host location rejected")
    root = Path(overnight.TARGET_WORKTREE if target else overnight.WORKTREE).resolve()
    branch = TARGET_BRANCH if target else BRANCH
    if target and (head, tree) != (overnight.TARGET_HEAD, overnight.TARGET_TREE):
        raise ValueError("target identity rejected")

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
        or git("branch", "--show-current") != branch
        or git("rev-parse", "HEAD") != head
        or git("rev-parse", "HEAD^{tree}") != tree
        or git("status", "--porcelain=v1", "--untracked-files=all")
        or git("remote", "get-url", "origin") != ORIGIN
        or git("rev-parse", "origin/" + branch) != head
        or git("rev-parse", "origin/" + branch + "^{tree}") != tree
        or git("ls-remote", "origin", "refs/heads/" + branch)
        != head + "\trefs/heads/" + branch
    ):
        raise ValueError("source rejected")
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(own / "src"):
                raise ValueError("mixed imports rejected")
            for location in getattr(module, "__path__", ()):
                if not Path(location).resolve().is_relative_to(own / "src"):
                    raise ValueError("mixed package path rejected")
    roots = tuple(
        Path(line[9:]).resolve()
        for line in git("worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    )
    if root not in roots or own not in roots:
        raise ValueError("worktree registry rejected")
    return roots


class _WindowsRuntime:
    parent = Path(overnight.QUALIFICATION_PARENT)

    def source(self, head: str, tree: str) -> tuple[Path, ...]:
        return admit_source(head, tree)

    def target(self) -> tuple[Path, ...]:
        return admit_source(overnight.TARGET_HEAD, overnight.TARGET_TREE, target=True)

    def clock(self) -> datetime:
        return datetime.now(UTC)

    def _scheduler(
        self, mode: str, plan: overnight.Plan | None = None
    ) -> dict[str, object]:
        if mode not in {"Observe", "Principal", "Create"} or (mode == "Create") != (
            plan is not None
        ):
            raise ValueError("transport rejected")
        request = (
            {}
            if plan is None
            else {
                "start_boundary": plan.trigger.isoformat(),
                "end_boundary": plan.end.isoformat(),
                "principal_name": plan.principal.name,
                "principal_sid": plan.principal.sid,
            }
        )
        result = subprocess.run(
            [
                overnight.POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(
                    overnight.WORKTREE / "scripts" / "arch134_d1r6_scheduler_create.ps1"
                ),
                "-Mode",
                mode,
            ],
            input=overnight.canonical(request).decode() + "\n",
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        if result.returncode != 0 or len(result.stdout.encode("utf-8")) > 16384:
            raise ValueError("scheduler unavailable")

        # Duplicate fields and unexpected output fail before any further effect.
        def pairs(items):
            output = {}
            for key, value in items:
                if key in output:
                    raise ValueError("duplicate transport field")
                output[key] = value
            return output

        return json.loads(result.stdout, object_pairs_hook=pairs)

    def principal(self) -> overnight.Principal:
        result = self._scheduler("Principal")
        if type(result) is not dict or set(result) != {"name", "sid"}:
            raise ValueError("principal unavailable")
        return overnight.Principal(result["name"], result["sid"])

    def observe(self) -> dict[str, object]:
        return self._scheduler("Observe")

    def create(self, plan: overnight.Plan) -> dict[str, object]:
        return self._scheduler("Create", plan)

    def child(self, plan: overnight.Plan) -> int:
        # No shell, generic module/expression/executable or environment authority.
        result = subprocess.run(
            [
                str(overnight.PYTHON),
                "-I",
                "-B",
                str(overnight.WORKTREE / "scripts" / "arch134_d1r6_d1r5_child.py"),
                "--expected-head",
                overnight.TARGET_HEAD,
                "--expected-tree",
                overnight.TARGET_TREE,
                "--evidence",
                str(overnight.QUALIFICATION_PARENT / plan.result_name),
                "--qualify-wake",
                QUALIFY_WAKE_INTERLOCK,
            ],
            cwd=str(overnight.TARGET_WORKTREE),
            check=False,
            # The unchanged D1R5 host independently caps its sleep at 20 minutes.
            timeout=21 * 60,
        )
        return result.returncode


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("arguments rejected")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        description="D1R6 one overnight wake; no D1 authority.", allow_abbrev=False
    )
    parser.add_argument("mode", choices=("preflight", "arm", "launch", "reconcile"))
    parser.add_argument("--expected-head")
    parser.add_argument("--expected-tree")
    parser.add_argument("--arm", choices=(overnight.ARM_INTERLOCK,))
    return parser


def _current_identity() -> tuple[str, str]:
    # Only used to discover the matching immutable journal, then exact admission.
    root = str(overnight.WORKTREE)
    head = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()
    return head, tree


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.mode in {"preflight", "arm"}:
            if (
                not args.expected_head
                or not args.expected_tree
                or (args.mode == "arm") != (args.arm is not None)
            ):
                raise ValueError("explicit authority required")
            head, tree = args.expected_head, args.expected_tree
        else:
            if args.expected_head or args.expected_tree or args.arm:
                raise ValueError("launch arguments forbidden")
            head, tree = _current_identity()
        runtime = _WindowsRuntime()
        if args.mode == "launch":
            return overnight.launch(runtime, head, tree)
        if args.mode == "preflight":
            overnight.preflight(runtime, head, tree)
            result = {"disposition": "READY"}
        elif args.mode == "arm":
            result = {"disposition": overnight.arm(runtime, head, tree, args.arm)}
        else:
            result = overnight.reconcile(runtime, head, tree)
        print(
            overnight.canonical(
                {**result, "effects": dict.fromkeys(overnight.ZERO_EFFECTS, 0)}
            ).decode()
        )
        return (
            0 if result["disposition"] in {"READY", "ARMED", "PASS", "PENDING"} else 1
        )
    except (Exception, KeyboardInterrupt):
        print("D1R6_HOST_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
