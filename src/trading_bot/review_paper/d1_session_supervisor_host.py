"""Fixed Windows D1R9 host. Import/help never touch the host or stores."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from scripts import arch134_d1r9_bridge as bridge
from trading_bot.review_paper import d1_session_authorization as prerequisite
from trading_bot.review_paper import d1_session_supervisor as supervisor
from trading_bot.review_paper import d1_session_supervisor_store as store

TASK_NAME = "AITradingBot-Arch134-D1R9-OneSessionSupervisor-v1"
POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")


class FixedRuntime:
    parent = bridge.PARENT

    def clock(self) -> datetime:
        return datetime.now(UTC)

    def admit(self, facts: dict) -> tuple[Path, ...]:
        roots = bridge.admit_sources(facts)
        bridge.admit_imports(bridge.ROOT)
        return roots

    def predecessors(self) -> None:
        prerequisite.bind_predecessors(
            prerequisite.read_evidence(
                self.parent / prerequisite.D1R5.basename, prerequisite.D1R5.size
            ),
            prerequisite.read_evidence(
                self.parent / prerequisite.D1R6.basename, prerequisite.D1R6.size
            ),
        )

    def runtime_binding(self) -> dict:
        return bridge.runtime_binding()

    def admit_runtime(self, binding: dict, *, entered: bool = False) -> None:
        from trading_bot.review_paper.production_paper_runtime import preflight_runtime

        bridge.admit_runtime(binding, entered=entered)
        if preflight_runtime()["status"] != "PRESENT_COMPATIBLE":
            raise ValueError("compatible existing runtime required")

    def scheduler(self, mode: str) -> dict:
        if mode not in {"Observe", "Create", "Run"}:
            raise ValueError("fixed scheduler transport required")
        result = subprocess.run(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(bridge.ROOT / "scripts/arch134_d1r9_scheduler.ps1"),
                "-Mode",
                mode,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=45,
            check=False,
        )
        if result.returncode != 0 or not 0 < len(result.stdout) <= 8192:
            raise ValueError("scheduler acknowledgement unavailable")
        value = json.loads(result.stdout)
        if value not in (
            {"status": "ABSENT"},
            {"status": "MATCH"},
            {"status": "CREATED"},
            {"status": "STARTED"},
        ):
            raise ValueError("scheduler projection rejected")
        return value

    def scheduler_matches(self) -> bool:
        return self.scheduler("Observe") == {"status": "MATCH"}

    def scheduler_create(self) -> None:
        if self.scheduler("Create") != {"status": "CREATED"}:
            raise ValueError("scheduler entry indeterminate")

    def scheduler_run(self) -> None:
        if self.scheduler("Run") != {"status": "STARTED"}:
            raise ValueError("scheduler launch indeterminate")

    def child_idle(self) -> bool:
        try:
            with store.lock(self.parent / "arch134-d1r9-child.lock"):
                return True
        except (OSError, ValueError):
            return False

    def child(self, kind: str) -> None:
        if kind not in {"d1r7", "d1r8"}:
            raise ValueError("fixed child required")
        with subprocess.Popen(
            [
                str(bridge.PYTHON),
                "-I",
                "-B",
                str(bridge.ROOT / "scripts" / ("arch134_d1r9_" + kind + "_child.py")),
            ],
            cwd=bridge.ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ) as child:
            while True:
                try:
                    child.wait(timeout=60)
                    break
                except subprocess.TimeoutExpired:
                    # Child effects are fenced by its accepted implementation.
                    # Never kill, restart or infer completion from stdout/exit code.
                    store.utc(self.clock())

    def wait(self, seconds: int) -> None:
        if type(seconds) is not int or not 0 < seconds <= supervisor.MAX_WAIT_SECONDS:
            raise ValueError("bounded wait quantum required")
        time.sleep(seconds)


@contextmanager
def supervisor_lock(parent: Path, *, resume: bool) -> Iterator[None]:
    # An initial demand-start may run while the authorizer still owns the lock.
    # Wait at most one bounded quantum for its durable ACK; no effect or retry
    # authority comes from this transient process-lifetime plumbing wait.
    context = None
    for attempt in range(61 if resume else 1):
        candidate = store.lock(parent / "arch134-d1r9-supervisor.lock")
        try:
            candidate.__enter__()
        except OSError:
            if not resume or attempt == 60:
                raise
            time.sleep(1)
        else:
            context = candidate
            break
    try:
        yield
    finally:
        context.__exit__(None, None, None)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("D1R9 arguments rejected")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(allow_abbrev=False)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--authorize", action="store_true")
    modes.add_argument("--resume", action="store_true")
    modes.add_argument("--status", action="store_true")
    parser.add_argument("--accepted-head")
    parser.add_argument("--accepted-tree")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if bool(args.accepted_head) != bool(args.accepted_tree) or (
            args.authorize != bool(args.accepted_head)
        ):
            raise ValueError(
                "reviewed source assertions required only for authorization"
            )
        if (
            os.name != "nt"
            or Path(__file__).resolve().parents[3] != bridge.ROOT.resolve()
        ):
            raise ValueError("fixed Windows supervisor required")
        runtime = FixedRuntime()
        if args.status:
            # No locks, scheduler, credentials, runtime or source-native probes.
            journal = store.find_active(runtime.parent)
            print("NO_ACTIVE_AUTHORIZATION" if journal is None else journal.state)
            return 0
        if args.authorize and not sys.stdin.isatty():
            raise ValueError("interactive one-session authority required")
        if args.resume and store.find_active(runtime.parent) is None:
            return 0
        with supervisor_lock(runtime.parent, resume=args.resume):
            if args.resume:
                journal = store.find_active(runtime.parent)
                if journal is None:
                    return 0
            else:
                source = dict(
                    branch=store.BRANCH,
                    head=args.accepted_head,
                    tree=args.accepted_tree,
                )
                interlock = input("D1R9 one-session authorization: ")
                journal = supervisor.authorize(runtime, source, interlock)
                if journal.state == "SCHEDULER_RUN_ACK":
                    print("AUTHORIZED_ONE_SESSION_TASK_STARTED")
                    return 0
            result = supervisor.supervise(runtime, journal)
            print(result)
            return (
                0 if result in {"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"} else 2
            )
    except (Exception, KeyboardInterrupt):
        print("D1R9_STOP_NO_RETRY", file=sys.stderr)
        return 2
