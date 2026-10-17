"""D1R9 fixed process bridge. No trading_bot imports before child-root selection."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

ROOT = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-arbitrary-time-supervisor"
)
R7_ROOT = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-authorization"
)
R8_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-execution")
PARENT = Path(r"F:\AI\temp\qualification")
PYTHON = Path(r"F:\AI\ai-trading-bot\.venv\Scripts\python.exe")
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"


def load_store() -> ModuleType:
    """The journal codec is standard-library-only; child package roots stay unmixed."""
    path = ROOT / "src/trading_bot/review_paper/d1_session_supervisor_store.py"
    spec = importlib.util.spec_from_file_location("arch134_d1r9_codec", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()


def admit_sources(facts: dict) -> tuple[Path, ...]:
    if (
        os.name != "nt"
        or Path(__file__).resolve()
        != (ROOT / "scripts/arch134_d1r9_bridge.py").resolve()
        or Path(sys.executable).resolve() != PYTHON.resolve()
    ):
        raise ValueError("fixed Windows source/interpreter required")
    codec = load_store()
    codec.validate_facts(facts)
    registry = None
    for root, source in (
        (ROOT, facts["source"]),
        (R7_ROOT, codec.D1R7),
        (R8_ROOT, codec.D1R8),
    ):
        codec.checked_path(root)
        branch, head, tree = (source[k] for k in ("branch", "head", "tree"))
        checks = (
            (("branch", "--show-current"), branch),
            (("rev-parse", "HEAD"), head),
            (("rev-parse", "HEAD^{tree}"), tree),
            (("status", "--porcelain=v1", "--untracked-files=all"), ""),
            (("remote", "get-url", "origin"), ORIGIN),
            (("remote", "get-url", "--push", "origin"), ORIGIN),
            (
                ("rev-parse", "--symbolic-full-name", "@{upstream}"),
                "refs/remotes/origin/" + branch,
            ),
            (("rev-parse", "origin/" + branch), head),
            (("rev-parse", "origin/" + branch + "^{tree}"), tree),
            (
                ("ls-remote", "origin", "refs/heads/" + branch),
                head + "\trefs/heads/" + branch,
            ),
        )
        if Path(
            git(root, "rev-parse", "--show-toplevel")
        ).resolve() != root.resolve() or any(
            git(root, *args) != expected for args, expected in checks
        ):
            raise ValueError("exact source admission rejected")
        roots = tuple(
            Path(line[9:]).resolve()
            for line in git(root, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        )
        if root.resolve() not in roots or (registry is not None and registry != roots):
            raise ValueError("worktree registry drift")
        registry = roots
    return registry


def admit_imports(root: Path) -> None:
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            locations = [
                getattr(module, "__file__", None),
                *getattr(module, "__path__", ()),
            ]
            if any(
                not p or not Path(p).resolve().is_relative_to(root.resolve() / "src")
                for p in locations
            ):
                raise ValueError("mixed imports rejected")


def runtime_binding() -> dict:
    codec = load_store()
    result = {}
    for key, path in (
        ("paper", Path(r"F:\AITradingBot\Arch134D1\paper.sqlite")),
        ("sessions", Path(r"F:\AITradingBot\Arch134D1\armed-sessions.sqlite")),
        ("python", PYTHON),
    ):
        payload = codec.read(path, 134217728)
        info = path.lstat()
        result[key] = dict(
            device=info.st_dev,
            inode=info.st_ino,
            bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
    return result


def admit_runtime(binding: dict, *, entered: bool = False) -> None:
    actual = runtime_binding()
    for key in binding:
        expected = binding[key]
        if entered and key in {"paper", "sessions"}:
            if any(actual[key][k] != expected[k] for k in ("device", "inode")):
                raise ValueError("runtime file identity drift")
        elif actual[key] != expected:
            raise ValueError("runtime content drift")


def child_main(kind: str) -> int:
    """Fixed adapters have no arguments; durable parent intent is mandatory."""
    try:
        if kind not in {"d1r7", "d1r8"} or len(sys.argv) != 1:
            raise ValueError("child selectors forbidden")
        codec = load_store()
        with codec.lock(PARENT / "arch134-d1r9-child.lock"):
            journal = codec.find_active(PARENT)
            if journal is None or journal.state != kind.upper() + "_DELEGATION_INTENT":
                raise ValueError("durable parent delegation required")
            admit_sources(journal.facts)
            # No D1R9 trading_bot module is imported into either child environment.
            root = R7_ROOT if kind == "d1r7" else R8_ROOT
            if any(
                name == "trading_bot" or name.startswith("trading_bot.")
                for name in sys.modules
            ):
                raise ValueError("child import environment already occupied")
            sys.path.insert(0, str(root / "src"))
            from trading_bot.review_paper import d1_session_authorization as q
            from trading_bot.review_paper.nyse_published_regular_sessions import (
                NYSEPublishedRegularSessionAuthority,
            )

            source7, source8 = q.Source(**codec.D1R7), q.Source(**codec.D1R8)
            now = datetime.now(UTC)
            plan = q.Plan(source7, source8, now)
            schedule = NYSEPublishedRegularSessionAuthority().schedule_for(plan.target)
            threshold = q.utc(schedule.opens_at) + timedelta(
                minutes=5 if kind == "d1r8" else -10
            )
            if (
                plan.target.isoformat() != journal.facts["target_session"]
                or now < threshold
            ):
                raise ValueError("fixed target/window rejected")
            q.bind_predecessors(
                q.read_evidence(PARENT / q.D1R5.basename, q.D1R5.size),
                q.read_evidence(PARENT / q.D1R6.basename, q.D1R6.size),
            )
            if kind == "d1r7":
                from trading_bot.review_paper import (
                    d1_session_authorization_host as host,
                )

                runtime = host.EvidenceRuntime()
            else:
                from trading_bot.review_paper import d1_session_execution as consumer
                from trading_bot.review_paper import d1_session_execution_host as host

                data = q.read_evidence(PARENT / plan.name, q.MAX_BYTES)
                records = q.parse_authorization(data)
                publication = dict(
                    bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
                )
                saved = next(
                    r["proof"] for r in journal.rows if r["event"] == "D1R7_READY"
                )
                if (
                    publication != saved
                    or records[-1]["classification"] != q.READY
                    or records[0]["facts"]["source"] != source7.facts()
                    or records[0]["facts"]["intended_d1"] != source8.facts()
                    or records[0]["facts"]["target_session"] != plan.target.isoformat()
                ):
                    raise ValueError("independent D1R7 completion proof required")
                proof = consumer.ReviewedProof(
                    source8, len(data), publication["sha256"], True
                )
                runtime = host.FixedRuntime()
                runtime.admit_runtime()
            admit_imports(root)
            admit_runtime(journal.facts["runtime"])
            admit_sources(journal.facts)
            plan.require_current(datetime.now(UTC))
            if (
                codec.read(journal.path, codec.MAX_BYTES, journal.identity)
                != journal.payload
            ):
                raise ValueError("parent authority changed")
            # O_EXCL child claim is distinct from lifetime liveness. Even direct
            # relaunch of this adapter cannot enter the accepted implementation twice.
            codec.exclusive(
                journal.path.with_suffix("." + kind + ".claim"),
                codec.canonical(dict(binding=codec.digest(journal.facts), child=kind))
                + b"\n",
            )
            if kind == "d1r7":
                result = q.publish_prerequisite(runtime, source7, source8, q.INTERLOCK)
                return 0 if result == q.READY else 2
            result = consumer.run_session(runtime, proof, consumer.INTERLOCK)
            return (
                0 if result in {"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"} else 2
            )
    except (Exception, KeyboardInterrupt):
        # No raw exception/credential/provider output crosses this boundary.
        return 2


def scheduler_claim() -> str:
    """Maintenance-only durable native entry; never update, delete or retry."""
    try:
        if len(sys.argv) != 1:
            raise ValueError("scheduler selectors forbidden")
        codec = load_store()
        journal = codec.find_active(PARENT)
        if journal is None or journal.state not in {
            "SCHEDULER_CREATE_INTENT",
            "SCHEDULER_RUN_INTENT",
        }:
            raise ValueError("durable maintenance intent required")
        mode = "CREATE" if journal.state == "SCHEDULER_CREATE_INTENT" else "RUN"
        admit_sources(journal.facts)
        admit_runtime(journal.facts["runtime"])
        codec.exclusive(
            journal.path.with_suffix(".scheduler-" + mode.lower() + ".claim"),
            codec.canonical(
                dict(binding=codec.digest(journal.facts), task="D1R9", mode=mode)
            )
            + b"\n",
        )
        return mode
    except (Exception, KeyboardInterrupt):
        return "BLOCKED"


if __name__ == "__main__":
    disposition = scheduler_claim()
    print(disposition)
    raise SystemExit(0 if disposition in {"CREATE", "RUN"} else 2)
