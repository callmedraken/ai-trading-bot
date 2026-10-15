"""Fixed D1R7 Windows binding. Import is inert; no generic effect transport."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from trading_bot.review_paper import pre_market_wake_overnight as overnight
from trading_bot.review_paper import pre_market_wake_retirement as retirement

BRANCH = "feature/robinhood-production-paper-stale-wake-retirement"
FROZEN_BRANCH = "feature/robinhood-production-paper-overnight-wake-arming"
TARGET_BRANCH = "feature/robinhood-production-paper-premarket-wake-qualification"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
BASE_HEAD = "a36de3bfe81a6e1a94fb3deeec7e579145939f52"


def admit_source(
    head: str, tree: str, *, target: bool = False, frozen: bool = False
) -> tuple[Path, ...]:
    """Admit one fixed source/target/predecessor without adopting moved refs."""
    overnight.validate_source_identity(head)
    overnight.validate_source_identity(tree)
    own = Path(__file__).resolve().parents[3]
    if os.name != "nt" or own != Path(retirement.WORKTREE).resolve():
        raise ValueError("host location rejected")
    root = Path(
        overnight.TARGET_WORKTREE
        if target
        else overnight.WORKTREE
        if frozen
        else retirement.WORKTREE
    ).resolve()
    branch = TARGET_BRANCH if target else FROZEN_BRANCH if frozen else BRANCH
    if frozen and (head, tree) != (
        overnight.RECOVERY_PREDECESSOR_HEAD,
        overnight.RECOVERY_PREDECESSOR_TREE,
    ):
        raise ValueError("frozen identity rejected")
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
        or (
            not frozen
            and (
                git("rev-parse", "origin/" + branch) != head
                or git("rev-parse", "origin/" + branch + "^{tree}") != tree
                or git("ls-remote", "origin", "refs/heads/" + branch)
                != head + "\trefs/heads/" + branch
            )
        )
    ):
        raise ValueError("source rejected")
    if not frozen and not target and git("merge-base", BASE_HEAD, head) != BASE_HEAD:
        raise ValueError("source ancestry rejected")
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

    def frozen(self) -> tuple[Path, ...]:
        return admit_source(
            overnight.RECOVERY_PREDECESSOR_HEAD,
            overnight.RECOVERY_PREDECESSOR_TREE,
            frozen=True,
        )

    def _scheduler(
        self, mode: str, plan: overnight.Plan | None = None
    ) -> dict[str, object]:
        if mode not in {"Observe", "Delete"} or (mode == "Delete") != (
            plan is not None
        ):
            raise ValueError("transport rejected")
        request = (
            {}
            if plan is None
            else {
                "interlock": retirement.INTERLOCK,
            }
        )
        result = subprocess.run(
            [
                overnight.POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(
                    retirement.WORKTREE
                    / "scripts"
                    / "arch134_d1r7_scheduler_retire.ps1"
                ),
                "-Mode",
                mode,
            ],
            input=overnight.canonical(request) + b"\n",
            capture_output=True,
            timeout=45,
            check=False,
        )

        def pairs(items):
            output = {}
            for key, value in items:
                if key in output:
                    raise ValueError("duplicate transport field")
                output[key] = value
            return output

        if type(result.stdout) is not bytes or len(result.stdout) > 16384:
            raise ValueError("scheduler unavailable")
        response = json.loads(result.stdout, object_pairs_hook=pairs)
        # A proven helper pre-entry rejection is distinct from process ambiguity.
        if result.returncode != 0 and not (
            mode == "Delete"
            and result.returncode == 2
            and overnight.canonical(response)
            == overnight.canonical(
                {
                    "disposition": "NOT_CALLED",
                    "deletion_attempts": 0,
                }
            )
        ):
            raise ValueError("scheduler uncertain")
        return response

    def observe(self) -> dict[str, object]:
        return self._scheduler("Observe")

    def delete(self, plan: overnight.Plan) -> dict[str, object]:
        return self._scheduler("Delete", plan)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("arguments rejected")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Exact D1R7 stale wake retirement", allow_abbrev=False)
    parser.add_argument("mode", choices=("preflight", "retire", "reconcile"))
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--retire", choices=(retirement.INTERLOCK,))
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if (args.mode == "retire") != (args.retire is not None):
            raise ValueError("interlock rejected")
        runtime = _WindowsRuntime()
        if args.mode == "preflight":
            retirement.preflight(runtime, args.expected_head, args.expected_tree)
            output = {"status": "PASS", "classification": "RETIREMENT_READY"}
        elif args.mode == "retire":
            classification = retirement.retire(
                runtime, args.expected_head, args.expected_tree, args.retire
            )
            output = {
                "status": "PASS" if classification == "RETIRED" else "STOP",
                "classification": classification,
            }
        else:
            output = retirement.reconcile(
                runtime, args.expected_head, args.expected_tree
            )
        print(json.dumps(output, sort_keys=True))
        return 0 if output["status"] == "PASS" else 2
    except (Exception, KeyboardInterrupt):
        print('{"classification":"BLOCKED","status":"STOP"}')
        return 2
