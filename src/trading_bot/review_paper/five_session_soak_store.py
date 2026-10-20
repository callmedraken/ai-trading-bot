"""F1 closed parent/child evidence codecs and append-only durable slots.

Standard library only: fixed adapters can read authority before selecting the
accepted D1R7/D1R8 package root. No host operations occur on import.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID, uuid5

SCHEMA = "arch134-f1-five-session-soak/v1"
CHILD_SCHEMA = "arch134-f1-granted-session/v1"
BRANCH = "feature/robinhood-production-paper-134f-five-session-soak"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
TASK = "AITradingBot-Arch134-F1-FiveSessionSoak-v1"
MAX_BYTES = 2097152
MAX_ROWS = 128
NAMESPACE = UUID("e9dd0368-2ca4-536f-bc95-3cc510337aac")
PARENT_NAME = "arch134-f1-five-session-soak-v1.jsonl"
PROGRESS = frozenset({"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"})
TERMINALS = PROGRESS | {"SESSION_MISSED", "BLOCKED", "INDETERMINATE"}
WAIT_STATES = frozenset({"NEXT_SESSION_WAIT", "PREMARKET_WAIT", "D1R8_WAIT"})
INITIAL = ("CHILD_RESERVED", "SOURCES_ADMITTED", "TARGET_BOUND")
SCHEDULER = dict(
    task=TASK,
    logon_triggers=1,
    actions=1,
    semantic_arguments=0,
    elevation=False,
    wake=False,
    start_when_available=False,
    demand_start=True,
    instances="IgnoreNew",
    restarts=3,
    restart_interval="PT1M",
    time_limit="PT0S",
    repetition=False,
)
CEILINGS = dict(
    parent_series=1,
    frozen_sessions=5,
    d1r7_delegations=5,
    d1r8_delegations=5,
    per_target_d1r7=1,
    per_target_d1r8=1,
    scheduler_creates=1,
    scheduler_runs=1,
    provider_retries=0,
    replacement_sessions=0,
    broker_placements=0,
    d2=0,
    promotion=0,
    real_money=0,
)
BUDGETS = dict(
    child_grants=5,
    scheduler_creates=1,
    scheduler_updates=0,
    scheduler_runs=1,
)
CHILD_BUDGETS = dict(
    d1r7_attempts=1,
    d1r8_attempts=1,
    scheduler_creates=0,
    scheduler_updates=0,
    scheduler_runs=0,
)
D1R7 = {
    "branch": "feature/robinhood-production-paper-d1-session-authorization",
    "head": "30322c49b13b80af8d20acee4bdb1efd83d86260",
    "tree": "b7dc7f054fca50c3ab784505f264b6f716a45dff",
}
D1R8 = {
    "branch": "feature/robinhood-production-paper-d1-session-execution",
    "head": "aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2",
    "tree": "fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f",
}
D1R9_PREDECESSOR = {
    "branch": "feature/robinhood-production-paper-d1-arbitrary-time-supervisor",
    "head": "efd1e6763dc4663d9c4b2444e785eb1c32adf8e8",
    "tree": "25a962daf3922c4226c7e395eba8613e1b03bbaf",
}
POLICY = {
    "starting_synthetic_cash": "10000",
    "opening_buffer_seconds": 300,
    "closing_buffer_seconds": 300,
    "max_quote_age_seconds": 60,
    "max_snapshot_age_seconds": 600,
    "risk_limits": {
        "max_position_percent": "0.20",
        "max_total_exposure_percent": "0.80",
        "max_order_notional": None,
        "max_new_position_percent": None,
        "minimum_cash_reserve_percent": "0.10",
        "allow_fractional_shares": True,
        "fractional_increment": "0.001",
        "allow_buying": True,
        "allow_selling": True,
        "estimated_commission": "0",
    },
    "synthetic_execution": {
        "order_type": "MARKET",
        "time_in_force": "DAY",
        "slippage_basis_points": "0",
        "commission": "0",
        "broker_placement_budget": 0,
        "maximum_synthetic_paper_fills": 1,
    },
}
D1R8_BUDGETS = {
    "write_readiness_attempts": 1,
    "compatibility_reservations": 1,
    "alpaca_history_requests": 4,
    "alpaca_credential_reads": 2,
    "robinhood_credential_reads": 2,
    "credential_reads": 4,
    "credential_writes": 0,
    "credential_deletes": 0,
    "oauth_refresh": 0,
    "oauth_browser": 0,
    "oauth_callback": 0,
    "oauth_registration": 0,
    "strategy_evaluations": 1,
    "prepare_attempts": 1,
    "quote_requests": 1,
    "account_resolutions": 1,
    "order_history_attempts": 202,
    "order_reviews": 1,
    "execute_attempts": 1,
    "paper_fill_mutations": 1,
    "broker_placements": 0,
    "broker_cancellations": 0,
    "options_mutations": 0,
    "crypto_mutations": 0,
    "scheduler_operations": 0,
    "acl_mutations": 0,
    "d2_effects": 0,
    "live_effects": 0,
}


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware clock required")
    return value.astimezone(UTC)


def is_hash(value: object, length: int = 64) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and all(c in "0123456789abcdef" for c in value)
    )


def checked_path(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("absolute path required")
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("link or reparse point rejected")


def identity(info: os.stat_result) -> tuple[int, int]:
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or not info.st_ino
        or getattr(info, "st_file_attributes", 0) & 0x400
    ):
        raise ValueError("single-link regular file required")
    return info.st_dev, info.st_ino


def read(
    path: Path, maximum: int = MAX_BYTES, expected_id: tuple[int, int] | None = None
) -> bytes:
    checked_path(path)
    before = path.lstat()
    file_id = identity(before)
    if before.st_size > maximum or (expected_id is not None and file_id != expected_id):
        raise ValueError("evidence bound/identity rejected")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if identity(opened) != file_id:
            raise ValueError("opened identity changed")
        payload = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        checked_path(path)
        final = path.lstat()
        if (
            identity(after) != file_id
            or identity(final) != file_id
            or len(payload) != before.st_size
            or len(payload) > maximum
            or (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
            != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (final.st_size, final.st_mtime_ns, final.st_ctime_ns)
            or opened.st_size != before.st_size
        ):
            raise ValueError("unstable evidence")
    return payload


def exclusive(path: Path, payload: bytes) -> tuple[int, int]:
    checked_path(path.parent)
    fd = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(fd, "wb") as stream:
        file_id = identity(os.fstat(stream.fileno()))
        if stream.write(payload) != len(payload):
            raise OSError("short write")
        stream.flush()
        os.fsync(stream.fileno())
    if read(path, max(MAX_BYTES, len(payload)), file_id) != payload:
        raise ValueError("exclusive reservation readback failed")
    return file_id


@contextmanager
def lock(path: Path) -> Iterator[None]:
    """Nonblocking lifetime lock; process death releases the OS lock, never a claim."""
    checked_path(path.parent)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags, 0o600), "r+b") as stream:
        checked_path(path)
        file_id = identity(os.fstat(stream.fileno()))
        if identity(path.lstat()) != file_id:
            raise ValueError("lock identity changed")
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
        if identity(path.lstat()) != file_id:
            raise ValueError("lock identity changed")
        # Closing releases the lock even after an exception; never delete the file.


def proof(value: object) -> None:
    if (
        type(value) is not dict
        or set(value) != {"bytes", "sha256"}
        or type(value["bytes"]) is not int
        or not 0 < value["bytes"] <= MAX_BYTES
        or not is_hash(value["sha256"])
    ):
        raise ValueError("closed bounded proof required")


def contract(target: str) -> dict:
    material = [
        "production-strategy-contract-identity/v1",
        target,
        D1R8["head"],
        D1R8["tree"],
        "MovingAverageCrossoverStrategy",
        "1.0.0",
        "SPY",
        "2",
        "3",
        "1",
    ]
    framed = "".join(f"{len(v.encode('utf-8'))}:{v}" for v in material)
    return dict(
        contract_id=str(uuid5(UUID("c0867c3b-548e-5512-a135-3c4f1225e6fc"), framed)),
        schema="production-strategy-contract/v1",
        source_head=D1R8["head"],
        source_tree=D1R8["tree"],
        strategy_id="MovingAverageCrossoverStrategy",
        strategy_version="1.0.0",
        symbol="SPY",
        target_session_date=target,
        strategy_config=dict(desired_quantity="1", short_window=2, long_window=3),
    )


COMMON = {
    "source",
    "d1r7",
    "d1r8",
    "semantic_predecessor",
    "symbol",
    "targets",
    "contracts",
    "policy",
    "scheduler",
    "ceilings",
    "runtime",
    "authorized_at",
    "kind",
}
CHILD_EXTRA = {"parent_id", "parent_prefix", "ordinal", "target_session"}


def semantic(facts: dict) -> dict:
    # Domain identities bind semantic values; journal bytes and clocks are proof,
    # never UUID inputs. The source and contract identities remain explicit.
    return {
        "schema": CHILD_SCHEMA if facts["kind"] == "child" else SCHEMA,
        "facts": {
            k: v
            for k, v in facts.items()
            if k not in {"runtime", "authorized_at", "parent_prefix"}
        },
    }


def domain_id(facts: dict) -> str:
    material = canonical(semantic(facts)).decode("utf-8")
    return str(uuid5(NAMESPACE, "arch134-f1-identity/v1:" + material))


def validate_facts(facts: dict) -> None:
    if type(facts) is not dict or facts.get("kind") not in {"parent", "child"}:
        raise ValueError("closed F1 authority required")
    if set(facts) != (COMMON | (CHILD_EXTRA if facts["kind"] == "child" else set())):
        raise ValueError("closed F1 facts required")
    source = facts["source"]
    if (
        type(source) is not dict
        or set(source) != {"branch", "head", "tree"}
        or source["branch"] != BRANCH
        or not is_hash(source["head"], 40)
        or not is_hash(source["tree"], 40)
    ):
        raise ValueError("F1 source rejected")
    fixed = dict(
        d1r7=D1R7,
        d1r8=D1R8,
        semantic_predecessor=D1R9_PREDECESSOR,
        symbol="SPY",
        policy=POLICY,
        scheduler=SCHEDULER,
        ceilings=CEILINGS,
    )
    if any(canonical(facts[k]) != canonical(v) for k, v in fixed.items()):
        raise ValueError("fixed F1 policy rejected")
    targets = facts["targets"]
    if type(targets) is not list or len(targets) != 5 or len(set(targets)) != 5:
        raise ValueError("exact ordered five-session tuple required")
    if (
        any(
            type(t) is not str or date.fromisoformat(t).isoformat() != t
            for t in targets
        )
        or targets != sorted(targets)
        or canonical(facts["contracts"]) != canonical([contract(t) for t in targets])
    ):
        raise ValueError("immutable contracts/targets rejected")
    if (
        utc(datetime.fromisoformat(facts["authorized_at"])).isoformat()
        != facts["authorized_at"]
    ):
        raise ValueError("canonical UTC required")
    runtime = facts["runtime"]
    if type(runtime) is not dict or set(runtime) != {"paper", "sessions", "python"}:
        raise ValueError("runtime binding rejected")
    for v in runtime.values():
        if (
            type(v) is not dict
            or set(v) != {"device", "inode", "bytes", "sha256"}
            or any(
                type(v[k]) is not int or v[k] < 0 for k in ("device", "inode", "bytes")
            )
            or v["inode"] == 0
            or not is_hash(v["sha256"])
        ):
            raise ValueError("runtime identity rejected")
    if facts["kind"] == "child":
        if (
            type(facts["ordinal"]) is not int
            or not 1 <= facts["ordinal"] <= 5
            or facts["target_session"] != targets[facts["ordinal"] - 1]
            or str(UUID(facts["parent_id"])) != facts["parent_id"]
        ):
            raise ValueError("child ordinal/parent rejected")
        proof(facts["parent_prefix"])


def _unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def allowed(phase: str, child: bool, completed: list) -> set[str]:
    if child:
        return {
            "START": {"CHILD_RESERVED"},
            "CHILD_RESERVED": {"SOURCES_ADMITTED"},
            "SOURCES_ADMITTED": {"TARGET_BOUND"},
            "TARGET_BOUND": {"CHILD_READY"},
            "CHILD_READY": {
                "NEXT_SESSION_WAIT",
                "PREMARKET_WAIT",
                "D1R7_DELEGATION_INTENT",
            },
            "NEXT_SESSION_WAIT": {"PREMARKET_WAIT", "D1R7_DELEGATION_INTENT"},
            "PREMARKET_WAIT": {"D1R7_DELEGATION_INTENT"},
            "D1R7_DELEGATION_INTENT": {"D1R7_READY"},
            "D1R7_READY": {"D1R8_WAIT", "D1R8_DELEGATION_INTENT"},
            "D1R8_WAIT": {"D1R8_DELEGATION_INTENT"},
            "D1R8_DELEGATION_INTENT": set(),
        }[phase]
    if phase == "SCHEDULER_RUN_ACK" or phase.endswith("_FINAL"):
        if (
            any(r["classification"] not in PROGRESS for r in completed)
            or len(completed) == 5
        ):
            return set()
        return {f"SESSION_{len(completed) + 1}_GRANT_INTENT"}
    if phase.startswith("SESSION_") and phase.endswith("_GRANT_INTENT"):
        return {phase.replace("GRANT_INTENT", "FINAL")}
    return {
        "START": {"SOAK_RESERVED"},
        "SOAK_RESERVED": {"SOURCES_ADMITTED"},
        "SOURCES_ADMITTED": {"WINDOW_BOUND"},
        "WINDOW_BOUND": {"SCHEDULER_CREATE_INTENT", "SOAK_READY"},
        "SCHEDULER_CREATE_INTENT": {"SCHEDULER_CREATE_ACK"},
        "SCHEDULER_CREATE_ACK": {"SOAK_READY"},
        "SOAK_READY": {"SCHEDULER_RUN_INTENT"},
        "SCHEDULER_RUN_INTENT": {"SCHEDULER_RUN_ACK"},
    }[phase]


def summary(value: dict, facts: dict, ordinal: int) -> None:
    if type(value) is not dict or set(value) != {
        "ordinal",
        "target_session",
        "child_id",
        "child_journal",
        "grant_prefix",
        "classification",
        "d1r7",
        "d1r8",
        "effects",
        "d1r8_effects",
        "contract",
    }:
        raise ValueError("closed child reconciliation required")
    if (
        type(value["ordinal"]) is not int
        or value["ordinal"] != ordinal
        or value["target_session"] != facts["targets"][ordinal - 1]
        or value["classification"] not in TERMINALS
        or value["contract"] != facts["contracts"][ordinal - 1]
        or str(UUID(value["child_id"])) != value["child_id"]
    ):
        raise ValueError("ordered child identity rejected")
    proof(value["child_journal"])
    proof(value["grant_prefix"])
    for key in ("d1r7", "d1r8"):
        if value[key] is not None:
            proof(value[key])
    effects = value["effects"]
    if (
        type(effects) is not dict
        or set(effects) != set(CHILD_BUDGETS)
        or any(
            type(effects[k]) is not int or not 0 <= effects[k] <= b
            for k, b in CHILD_BUDGETS.items()
        )
    ):
        raise ValueError("child effects rejected")
    if value["classification"] in PROGRESS and (
        value["d1r7"] is None
        or value["d1r8"] is None
        or effects["d1r7_attempts"] != 1
        or effects["d1r8_attempts"] != 1
    ):
        raise ValueError("positive child proof required")
    counts = value["d1r8_effects"]
    if (
        type(counts) is not dict
        or set(counts) != set(D1R8_BUDGETS)
        or any(
            type(counts[k]) is not int or not 0 <= counts[k] <= b
            for k, b in D1R8_BUDGETS.items()
        )
    ):
        raise ValueError("D1R8 complete accounting rejected")


def parse(payload: bytes) -> tuple[dict, ...]:
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
            raise ValueError
        rows = tuple(
            json.loads(line, object_pairs_hook=_unique)
            for line in payload.decode().splitlines()
        )
        if (
            not 0 < len(rows) <= MAX_ROWS
            or b"".join(canonical(r) + b"\n" for r in rows) != payload
        ):
            raise ValueError
        facts = rows[0]["facts"]
        validate_facts(facts)
        child = facts["kind"] == "child"
        budgets = CHILD_BUDGETS if child else BUDGETS
        effects = dict.fromkeys(budgets, 0)
        phase = "START"
        completed = []
        last = utc(datetime.fromisoformat(facts["authorized_at"]))
        for i, row in enumerate(rows):
            if (
                type(row) is not dict
                or set(row)
                != {
                    "schema",
                    "event",
                    "classification",
                    "facts",
                    "binding",
                    "identity",
                    "effects",
                    "budgets",
                    "observed_at",
                    "proof",
                }
                or row["schema"] != (CHILD_SCHEMA if child else SCHEMA)
                or row["binding"] != digest(facts)
                or row["identity"] != domain_id(facts)
                or canonical(row["facts"]) != canonical(facts if i == 0 else None)
                or canonical(row["budgets"]) != canonical(budgets)
                or phase == "FINAL"
            ):
                raise ValueError
            now = utc(datetime.fromisoformat(row["observed_at"]))
            if now.isoformat() != row["observed_at"] or now < last:
                raise ValueError
            last = now
            event = row["event"]
            if event == "FINAL":
                status = row["classification"]
                if i == 0 or status not in (
                    TERMINALS if child else TERMINALS | {"COMPLETED"}
                ):
                    raise ValueError
                if child:
                    if status in PROGRESS:
                        if phase != "D1R8_DELEGATION_INTENT":
                            raise ValueError
                        proof(row["proof"])
                    elif row["proof"] is not None:
                        raise ValueError
                elif status == "COMPLETED":
                    expected = dict(
                        children=completed,
                        scheduler="MATCH",
                        parent_prefix=dict(
                            bytes=len(b"".join(canonical(r) + b"\n" for r in rows[:i])),
                            sha256=hashlib.sha256(
                                b"".join(canonical(r) + b"\n" for r in rows[:i])
                            ).hexdigest(),
                        ),
                    )
                    if (
                        len(completed) != 5
                        or any(c["classification"] not in PROGRESS for c in completed)
                        or canonical(row["proof"]) != canonical(expected)
                    ):
                        raise ValueError
                elif status in PROGRESS or row["proof"] is not None:
                    raise ValueError
            else:
                if event not in allowed(phase, child, completed):
                    raise ValueError
                session_final = (
                    not child
                    and event.startswith("SESSION_")
                    and event.endswith("_FINAL")
                )
                if session_final:
                    summary(row["proof"], facts, len(completed) + 1)
                    if row["classification"] != row["proof"]["classification"]:
                        raise ValueError
                    completed.append(row["proof"])
                elif row["classification"] is not None:
                    raise ValueError
                if child and event == "D1R7_READY":
                    proof(row["proof"])
                elif not session_final and row["proof"] is not None:
                    raise ValueError
                for state, counter in (
                    ("SCHEDULER_CREATE_INTENT", "scheduler_creates"),
                    ("SCHEDULER_RUN_INTENT", "scheduler_runs"),
                    ("D1R7_DELEGATION_INTENT", "d1r7_attempts"),
                    ("D1R8_DELEGATION_INTENT", "d1r8_attempts"),
                ):
                    if event == state:
                        effects[counter] += 1
                if not child and event.endswith("_GRANT_INTENT"):
                    effects["child_grants"] += 1
            if canonical(row["effects"]) != canonical(effects) or any(
                effects[k] > budgets[k] for k in effects
            ):
                raise ValueError
            phase = event
        return rows
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        UnicodeError,
        OverflowError,
        RecursionError,
    ):
        raise ValueError("F1 canonical journal rejected") from None


def reservation_name(facts: dict) -> str:
    return (
        f"arch134-f1-child-{facts['ordinal']}-{domain_id(facts)}.jsonl"
        if facts["kind"] == "child"
        else PARENT_NAME
    )


class Journal:
    def __init__(self, path: Path, payload: bytes, file_id: tuple[int, int]) -> None:
        self.path, self.payload, self.identity = path, payload, file_id
        self.rows = parse(payload)
        self.last_clock = utc(datetime.fromisoformat(self.rows[-1]["observed_at"]))
        if path.name != reservation_name(self.facts):
            raise ValueError("fixed authority slot rejected")

    @property
    def facts(self) -> dict:
        return self.rows[0]["facts"]

    @property
    def state(self) -> str:
        return self.rows[-1]["event"]

    @property
    def domain_id(self) -> str:
        return self.rows[0]["identity"]

    @classmethod
    def reserve(
        cls, parent: Path, facts: dict, *, observed_at: datetime | None = None
    ) -> Journal:
        validate_facts(facts)
        child = facts["kind"] == "child"
        row = dict(
            schema=CHILD_SCHEMA if child else SCHEMA,
            event="CHILD_RESERVED" if child else "SOAK_RESERVED",
            classification=None,
            facts=facts,
            binding=digest(facts),
            identity=domain_id(facts),
            effects=dict.fromkeys(CHILD_BUDGETS if child else BUDGETS, 0),
            budgets=CHILD_BUDGETS if child else BUDGETS,
            observed_at=(
                facts["authorized_at"]
                if observed_at is None
                else utc(observed_at).isoformat()
            ),
            proof=None,
        )
        payload = canonical(row) + b"\n"
        parse(payload)
        path = parent / reservation_name(facts)
        return cls(path, payload, exclusive(path, payload))

    @classmethod
    def load(cls, path: Path) -> Journal:
        file_id = identity(path.lstat())
        return cls(path, read(path, MAX_BYTES, file_id), file_id)

    def append(
        self,
        event: str,
        at: datetime,
        *,
        classification: str | None = None,
        proof: dict | None = None,
    ) -> None:
        effects = dict(self.rows[-1]["effects"])
        for state, counter in (
            ("SCHEDULER_CREATE_INTENT", "scheduler_creates"),
            ("SCHEDULER_RUN_INTENT", "scheduler_runs"),
            ("D1R7_DELEGATION_INTENT", "d1r7_attempts"),
            ("D1R8_DELEGATION_INTENT", "d1r8_attempts"),
        ):
            if event == state:
                effects[counter] += 1
        if event.startswith("SESSION_") and event.endswith("_GRANT_INTENT"):
            effects["child_grants"] += 1
        row = dict(
            schema=self.rows[0]["schema"],
            event=event,
            classification=classification,
            facts=None,
            binding=digest(self.facts),
            identity=self.domain_id,
            effects=effects,
            budgets=self.rows[0]["budgets"],
            observed_at=utc(at).isoformat(),
            proof=proof,
        )
        data = canonical(row) + b"\n"
        proposed = self.payload + data
        rows = parse(proposed)
        if read(self.path, MAX_BYTES, self.identity) != self.payload:
            raise ValueError("authority changed")
        with os.fdopen(
            os.open(self.path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_BINARY", 0)),
            "ab",
        ) as stream:
            if identity(os.fstat(stream.fileno())) != self.identity:
                raise ValueError("append handle changed")
            if stream.write(data) != len(data):
                raise OSError("short append")
            stream.flush()
            os.fsync(stream.fileno())
        if read(self.path, MAX_BYTES, self.identity) != proposed:
            raise ValueError("durable transition readback failed")
        self.payload, self.rows = proposed, rows


ChildJournal = Journal


def find_active(parent: Path) -> Journal | None:
    checked_path(parent)
    path = parent / PARENT_NAME
    if not path.exists():
        return None
    journal = Journal.load(path)
    return journal if journal.state != "FINAL" else None


def grant_facts(parent: Journal, ordinal: int, binding: dict) -> dict:
    if (
        parent.facts["kind"] != "parent"
        or type(ordinal) is not int
        or not 1 <= ordinal <= 5
        or parent.state != f"SESSION_{ordinal}_GRANT_INTENT"
    ):
        raise ValueError("durable parent grant intent required")
    facts = dict(
        parent.facts,
        kind="child",
        runtime=binding,
        parent_id=parent.domain_id,
        parent_prefix=dict(
            bytes=len(parent.payload), sha256=hashlib.sha256(parent.payload).hexdigest()
        ),
        ordinal=ordinal,
        target_session=parent.facts["targets"][ordinal - 1],
    )
    validate_facts(facts)
    return facts


def admit_grant(parent: Journal, child: Journal) -> None:
    expected = grant_facts(parent, child.facts["ordinal"], child.facts["runtime"])
    if datetime.fromisoformat(child.rows[0]["observed_at"]) < datetime.fromisoformat(
        parent.rows[-1]["observed_at"]
    ):
        raise ValueError("child reservation precedes durable grant")
    if (
        canonical(expected) != canonical(child.facts)
        or read(parent.path, MAX_BYTES, parent.identity) != parent.payload
        or read(child.path, MAX_BYTES, child.identity) != child.payload
    ):
        raise ValueError("parent/child durable grant mismatch")
    for key in ("paper", "sessions", "python"):
        fields = (
            ("device", "inode")
            if key != "python"
            else ("device", "inode", "bytes", "sha256")
        )
        if any(
            parent.facts["runtime"][key][k] != child.facts["runtime"][key][k]
            for k in fields
        ):
            raise ValueError("child runtime lineage rejected")


def active_child(parent: Journal) -> Journal:
    if not (
        parent.state.startswith("SESSION_") and parent.state.endswith("_GRANT_INTENT")
    ):
        raise ValueError("current durable F1 grant required")
    ordinal = int(parent.state.split("_")[1])
    paths = tuple(parent.path.parent.glob("arch134-f1-child-*.jsonl"))
    if len(paths) > 5:
        raise ValueError("child namespace bound exceeded")
    records = [Journal.load(p) for p in paths]
    active = [r for r in records if r.facts["ordinal"] == ordinal]
    if len(active) != 1:
        raise ValueError("one exact current child required")
    admit_grant(parent, active[0])
    return active[0]
