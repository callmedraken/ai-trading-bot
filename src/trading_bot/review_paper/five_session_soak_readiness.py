"""F2 bounded observations only. A positive preview never consumes F1 authority."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from trading_bot.review_paper import d1_session_authorization as predecessor
from trading_bot.review_paper.five_session_soak import select_window
from trading_bot.review_paper.five_session_soak_store import checked_path, read, utc
from trading_bot.review_paper.production_paper_runtime import preflight_runtime

SCHEMA = "arch134-f2-five-session-soak-readiness/v1"
READY = "READY_FOR_SEPARATE_F1_AUTHORIZATION"
BRANCH = "feature/robinhood-production-paper-134f2-five-session-soak-readiness"
MAIN = Path(r"F:\AI\ai-trading-bot")
ROOT = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-134f2-five-session-soak-readiness"
)
F1_ROOT = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-134f-five-session-soak"
)
R7_ROOT = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-authorization"
)
R8_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-execution")
PARENT = Path(r"F:\AI\temp\qualification")
PYTHON = MAIN / ".venv/Scripts/python.exe"
POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
SOURCES = (
    (
        "f1",
        F1_ROOT,
        "feature/robinhood-production-paper-134f-five-session-soak",
        "b59ad3b44540a55a30f612d5c4e3e38e26a95b02",
        "e8a94e3512d7950f2fbc9c4d102a58b63e03244f",
    ),
    (
        "d1r7",
        R7_ROOT,
        "feature/robinhood-production-paper-d1-session-authorization",
        "30322c49b13b80af8d20acee4bdb1efd83d86260",
        "b7dc7f054fca50c3ab784505f264b6f716a45dff",
    ),
    (
        "d1r8",
        R8_ROOT,
        "feature/robinhood-production-paper-d1-session-execution",
        "aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2",
        "fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f",
    ),
)
F1_BLOBS = {
    "src/trading_bot/review_paper/five_session_soak_store.py": (
        "3813837e8d10ee2b19150405143704a7f03d474f"
    ),
    "src/trading_bot/review_paper/five_session_soak.py": (
        "9de15257fc9b6fe97e90314450b097849ff81320"
    ),
    "src/trading_bot/review_paper/five_session_soak_child.py": (
        "6afcdfe42ac1691bc477efcfb4764c227a0c1bc2"
    ),
    "src/trading_bot/review_paper/five_session_soak_host.py": (
        "9c3197005811ec0cd2b38f8ce4c7717f6c9e2108"
    ),
    "scripts/arch134_f1_bridge.py": "1e35f11bf623ac333df37a45dc45e4a0fe282427",
    "scripts/arch134_f1_scheduler.ps1": "0cb85477f4958cce32c5b409be66e6013aa9f575",
    "scripts/run_arch134_f1.py": "3528cd65d77484d9ab58868b75699a6edcc9aa84",
}
EFFECTS = (
    "F1_PARENT_RESERVATIONS",
    "F1_CHILD_RESERVATIONS",
    "F1_LOCK_CREATIONS",
    "F1_CLAIM_CREATIONS",
    "SCHEDULER_CREATES",
    "SCHEDULER_RUNS",
    "SCHEDULER_UPDATES",
    "SCHEDULER_DELETES",
    "CREDENTIAL_READS",
    "CREDENTIAL_WRITES",
    "PROVIDER_REQUESTS",
    "OAUTH_INTERACTIONS",
    "RUNTIME_SQLITE_WRITES",
    "RUNTIME_WRITE_PROBES",
    "D1R7_OPERATIONS",
    "D1R8_OPERATIONS",
    "PAPER_MUTATIONS",
    "BROKER_MUTATIONS",
    "D2_OPERATIONS",
    "STRATEGY_PROMOTIONS",
    "REAL_MONEY_EFFECTS",
)
OBSERVATIONS = (
    "git_commands",
    "filesystem_observations",
    "predecessor_reads",
    "runtime_inspections",
    "scheduler_observations",
)
FIELDS = frozenset(
    (
        "schema",
        "status",
        "observed_at",
        "f2_source_head",
        "f2_source_tree",
        "f1_source_head",
        "f1_source_tree",
        "d1r7_source_head",
        "d1r7_source_tree",
        "d1r8_source_head",
        "d1r8_source_tree",
        "f1_source_status",
        "predecessor_status",
        "runtime_status",
        "paper_records",
        "session_reservations",
        "runtime_write_readiness",
        "credential_readiness",
        "provider_readiness",
        "parent_slot_status",
        "child_artifact_count",
        "claim_artifact_count",
        "lock_artifact_count",
        "scheduler_status",
        "preview_targets",
        "effects",
        "observations",
    )
)


def _hash(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and all(c in "0123456789abcdef" for c in value)
    )


def validate_result(value: dict) -> None:
    """Closed sanitized evidence, including incomplete BLOCKED observations."""
    if type(value) is not dict or set(value) != FIELDS:
        raise ValueError("F2 result rejected")
    if value["schema"] != SCHEMA or value["status"] not in {READY, "BLOCKED"}:
        raise ValueError("F2 status rejected")
    positive = value["status"] == READY
    for key in (
        "runtime_write_readiness",
        "credential_readiness",
        "provider_readiness",
    ):
        if value[key] != "NOT_CHECKED":
            raise ValueError("F2 capability rejected")
    for key, expected in (
        ("f1_source_status", "EXACT"),
        ("predecessor_status", "ACCEPTED"),
        ("runtime_status", "PRESENT_COMPATIBLE"),
        ("parent_slot_status", "ABSENT"),
        ("scheduler_status", "ABSENT"),
    ):
        if value[key] not in {expected, "NOT_CHECKED"} or (
            positive and value[key] != expected
        ):
            raise ValueError("F2 observation rejected")
    for key in FIELDS:
        if key.endswith(("_head", "_tree")) and not (
            _hash(value[key]) or (not positive and value[key] is None)
        ):
            raise ValueError("F2 source rejected")
    for label, _, _, head, tree in SOURCES:
        for suffix, expected in (("head", head), ("tree", tree)):
            if value[label + "_source_" + suffix] not in (None, expected):
                raise ValueError("F2 frozen source rejected")
    for key in (
        "paper_records",
        "session_reservations",
        "child_artifact_count",
        "claim_artifact_count",
        "lock_artifact_count",
    ):
        item = value[key]
        if not (type(item) is int and 0 <= item <= 1000000) and not (
            not positive and item is None
        ):
            raise ValueError("F2 count rejected")
        if positive and key.endswith("artifact_count") and item != 0:
            raise ValueError("F2 namespace rejected")
    for key, names in (("effects", EFFECTS), ("observations", OBSERVATIONS)):
        items = value[key]
        if (
            type(items) is not dict
            or set(items) != set(names)
            or any(type(v) is not int or not 0 <= v <= 1000000 for v in items.values())
            or (key == "effects" and any(items.values()))
        ):
            raise ValueError("F2 accounting rejected")
    observed = value["observed_at"]
    if observed is not None:
        instant = datetime.fromisoformat(observed)
        if type(observed) is not str or utc(instant).isoformat() != observed:
            raise ValueError("F2 clock rejected")
    elif positive:
        raise ValueError("F2 clock required")
    targets = value["preview_targets"]
    if type(targets) is not list or (len(targets) != 5 and (positive or targets)):
        raise ValueError("F2 preview rejected")
    if targets:
        if any(
            type(t) is not str or date.fromisoformat(t).isoformat() != t
            for t in targets
        ):
            raise ValueError("F2 dates rejected")
        if observed is None or targets != select_window(
            datetime.fromisoformat(observed)
        ):
            raise ValueError("F2 published preview rejected")


class ReadOnlyHost:
    """Fixed host edges with no authority-creating interface."""

    def __init__(self) -> None:
        self.observations = dict.fromkeys(OBSERVATIONS, 0)

    def clock(self) -> datetime:
        return datetime.now(UTC)

    def f2_source(self) -> tuple[str, str]:
        self.directory(ROOT)
        if (
            os.name != "nt"
            or Path(__file__).resolve().parents[3] != ROOT
            or Path(sys.executable).resolve() != PYTHON.resolve()
        ):
            raise ValueError("F2 fixed host rejected")
        for args, expected in (
            (("branch", "--show-current"), BRANCH),
            (("status", "--porcelain=v1", "--untracked-files=all"), ""),
            (("remote", "get-url", "origin"), ORIGIN),
            (("remote", "get-url", "--push", "origin"), ORIGIN),
        ):
            if self.git(ROOT, *args) != expected:
                raise ValueError("F2 source rejected")
        source = (
            self.git(ROOT, "rev-parse", "HEAD"),
            self.git(ROOT, "rev-parse", "HEAD^{tree}"),
        )
        if (
            not all(_hash(v) for v in source)
            or self.git(ROOT, "ls-remote", "origin", "refs/heads/" + BRANCH)
            != source[0] + "\trefs/heads/" + BRANCH
        ):
            raise ValueError("F2 live source rejected")
        return source

    def git(self, root: Path, *args: str) -> str:
        self.observations["git_commands"] += 1
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        if result.returncode != 0 or result.stderr or len(result.stdout) > 262144:
            raise ValueError("F2 Git observation unavailable")
        return result.stdout.decode("utf-8").strip()

    def directory(self, path: Path) -> tuple[int, int]:
        self.observations["filesystem_observations"] += 1
        checked_path(path)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or path.resolve() != path or not info.st_ino:
            raise ValueError("F2 fixed directory rejected")
        return info.st_dev, info.st_ino

    def sources(self) -> tuple:
        registry = self.git(MAIN, "worktree", "list", "--porcelain")
        roots = tuple(
            Path(line[9:]).resolve()
            for line in registry.splitlines()
            if line.startswith("worktree ")
        )
        required = {MAIN.resolve(), ROOT.resolve(), *(s[1].resolve() for s in SOURCES)}
        if not required <= set(roots) or len(roots) != len(set(roots)):
            raise ValueError("F2 registry rejected")
        snapshots = []
        for _, root, branch, head, tree in SOURCES:
            identity = self.directory(root)
            if Path(self.git(root, "rev-parse", "--show-toplevel")).resolve() != root:
                raise ValueError("F2 source path rejected")
            common = Path(self.git(root, "rev-parse", "--git-common-dir"))
            if (root / common).resolve() != (MAIN / ".git").resolve():
                raise ValueError("F2 common repository rejected")
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
                (("worktree", "list", "--porcelain"), registry),
            )
            if any(self.git(root, *args) != expected for args, expected in checks):
                raise ValueError("F2 frozen source rejected")
            snapshots.append(identity)
        for relative, expected in F1_BLOBS.items():
            self.observations["filesystem_observations"] += 1
            payload = read(F1_ROOT / relative).replace(b"\r\n", b"\n")
            blob = hashlib.sha1(
                b"blob " + str(len(payload)).encode() + b"\0" + payload
            ).hexdigest()
            if blob != expected:
                raise ValueError("F2 frozen blob rejected")
        return registry, tuple(snapshots)

    def predecessors(self) -> tuple:
        identity = self.directory(PARENT)
        payloads = []
        identities = []
        for pin in (predecessor.D1R5, predecessor.D1R6):
            self.observations["predecessor_reads"] += 1
            path = PARENT / pin.basename
            payloads.append(predecessor.read_evidence(path, pin.size))
            info = path.lstat()
            identities.append((info.st_dev, info.st_ino))
        predecessor.bind_predecessors(*payloads)
        return (
            identity,
            tuple(identities),
            tuple(hashlib.sha256(p).hexdigest() for p in payloads),
        )

    def runtime(self) -> tuple:
        self.observations["runtime_inspections"] += 1
        result = preflight_runtime()
        expected = {
            "schema": "production-paper-runtime-preflight/v1",
            "status": "PRESENT_COMPATIBLE",
            "paper_store_write_readiness": "NOT_CHECKED",
            "session_store_write_readiness": "NOT_CHECKED",
            **dict.fromkeys(
                (
                    "alpaca_credential_reads",
                    "robinhood_credential_reads",
                    "alpaca_http_calls",
                    "robinhood_application_calls",
                    "paper_trade_mutations",
                    "runtime_writes",
                    "scheduler_mutations",
                    "broker_mutations",
                ),
                0,
            ),
        }
        if type(result) is not dict or set(result) != set(expected) | {
            "paper_records",
            "session_reservations",
        }:
            raise ValueError("F2 runtime result rejected")
        if any(
            type(result[k]) is not type(v) or result[k] != v
            for k, v in expected.items()
        ):
            raise ValueError("F2 runtime unavailable")
        counts = tuple(result[k] for k in ("paper_records", "session_reservations"))
        if any(type(n) is not int or not 0 <= n <= 1000000 for n in counts):
            raise ValueError("F2 runtime counts rejected")
        snapshots = []
        runtime_root = Path(r"F:\AITradingBot\Arch134D1")
        directory = self.directory(runtime_root)
        for name in ("paper.sqlite", "armed-sessions.sqlite"):
            self.observations["filesystem_observations"] += 1
            path = runtime_root / name
            payload = read(path, 134217728)
            info = path.lstat()
            snapshots.append(
                (info.st_dev, info.st_ino, hashlib.sha256(payload).hexdigest())
            )
        return counts, (directory, tuple(snapshots))

    def namespace(self) -> tuple:
        identity = self.directory(PARENT)
        self.observations["filesystem_observations"] += 1
        # Block every F1 artifact, including directories, dangling links, and
        # unexpected names. Never open a journal or take a lifetime lock.
        for index, path in enumerate(PARENT.iterdir()):
            if index >= 10000 or path.name.casefold().startswith("arch134-f1"):
                raise ValueError("F2 authority namespace occupied")
        return identity

    def scheduler(self) -> None:
        self.observations["scheduler_observations"] += 1
        result = subprocess.run(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(F1_ROOT / "scripts/arch134_f1_scheduler.ps1"),
                "-Mode",
                "Observe",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=45,
            check=False,
        )
        if (
            result.returncode != 0
            or result.stderr
            or not 0 < len(result.stdout) <= 8192
            or result.stdout.strip() != b'{"status":"ABSENT"}'
        ):
            raise ValueError("F2 scheduler absence unavailable")


def preflight() -> dict[str, object]:
    """Observe twice; fail closed without exposing native exception material."""
    host = ReadOnlyHost()
    result = dict.fromkeys(FIELDS)
    result.update(
        schema=SCHEMA,
        status="BLOCKED",
        preview_targets=[],
        effects=dict.fromkeys(EFFECTS, 0),
        observations=host.observations,
        **dict.fromkeys(
            (
                "runtime_write_readiness",
                "credential_readiness",
                "provider_readiness",
                "f1_source_status",
                "predecessor_status",
                "runtime_status",
                "parent_slot_status",
                "scheduler_status",
            ),
            "NOT_CHECKED",
        ),
    )
    try:
        f2 = host.f2_source()
        result.update(f2_source_head=f2[0], f2_source_tree=f2[1])
        observed = utc(host.clock())
        result["observed_at"] = observed.isoformat()
        first = (host.sources(), host.predecessors(), host.runtime(), host.namespace())
        host.scheduler()
        result["preview_targets"] = select_window(observed)
        final = (host.sources(), host.predecessors(), host.runtime(), host.namespace())
        host.scheduler()
        if first != final or host.f2_source() != f2:
            raise ValueError("F2 final readmission drift")
        for label, _, _, head, tree in SOURCES:
            result[label + "_source_head"] = head
            result[label + "_source_tree"] = tree
        result.update(
            f1_source_status="EXACT",
            predecessor_status="ACCEPTED",
            runtime_status="PRESENT_COMPATIBLE",
            paper_records=first[2][0][0],
            session_reservations=first[2][0][1],
            parent_slot_status="ABSENT",
            child_artifact_count=0,
            claim_artifact_count=0,
            lock_artifact_count=0,
            scheduler_status="ABSENT",
            status=READY,
        )
        validate_result(result)
    except (Exception, KeyboardInterrupt):
        # Stage details stay NOT_CHECKED on incomplete admission; no invented
        # positive readiness or raw exception string crosses this boundary.
        result["status"] = "BLOCKED"
    return result
