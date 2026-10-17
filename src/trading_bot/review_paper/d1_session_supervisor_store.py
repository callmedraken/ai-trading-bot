"""Closed D1R9 journal and locks. Standard library only for isolated adapters."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

SCHEMA = "arch134-d1r9-one-session-supervisor/v1"
BRANCH = "feature/robinhood-production-paper-d1-arbitrary-time-supervisor"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
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
MAX_BYTES = 131072
MAX_ROWS = 128
TERMINALS = frozenset(
    {
        "NO_SIGNAL",
        "RISK_REJECTED",
        "PAPER_EXECUTED",
        "SESSION_MISSED",
        "BLOCKED",
        "INDETERMINATE",
    }
)
BUDGETS = {
    "d1r7_attempts": 1,
    "d1r8_attempts": 1,
    "scheduler_creates": 1,
    "scheduler_updates": 0,
    "scheduler_runs": 1,
}
INITIAL = (
    "AUTHORIZATION_RESERVED",
    "SOURCES_ADMITTED",
    "TARGET_BOUND",
)
WAIT_STATES = frozenset({"NEXT_SESSION_WAIT", "PREMARKET_WAIT", "D1R8_WAIT"})


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


def validate_facts(facts: dict) -> None:
    if type(facts) is not dict or set(facts) != {
        "source",
        "d1r7",
        "d1r8",
        "target_session",
        "authorized_at",
        "symbol",
        "runtime",
    }:
        raise ValueError("closed authorization facts required")
    binding = facts["runtime"]
    if type(binding) is not dict or set(binding) != {"paper", "sessions", "python"}:
        raise ValueError("closed runtime binding required")
    for value in binding.values():
        if (
            type(value) is not dict
            or set(value) != {"device", "inode", "bytes", "sha256"}
            or any(
                type(value[k]) is not int or value[k] < 0
                for k in ("device", "inode", "bytes")
            )
            or value["inode"] == 0
            or not is_hash(value["sha256"])
        ):
            raise ValueError("runtime identity rejected")
    source = facts["source"]
    if (
        type(source) is not dict
        or set(source) != {"branch", "head", "tree"}
        or source["branch"] != BRANCH
        or not is_hash(source["head"], 40)
        or not is_hash(source["tree"], 40)
        or canonical(facts["d1r7"]) != canonical(D1R7)
        or canonical(facts["d1r8"]) != canonical(D1R8)
        or facts["symbol"] != "SPY"
        or date.fromisoformat(facts["target_session"]).isoformat()
        != facts["target_session"]
        or utc(datetime.fromisoformat(facts["authorized_at"])).isoformat()
        != facts["authorized_at"]
    ):
        raise ValueError("authorization binding rejected")


def reservation_name(target: str) -> str:
    if date.fromisoformat(target).isoformat() != target:
        raise ValueError("target rejected")
    material = [SCHEMA, "SPY", target, D1R7, D1R8]
    return f"arch134-d1r9-SPY-{target}-{digest(material)}.jsonl"


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


def _unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def parse(payload: bytes) -> tuple[dict, ...]:
    """Canonical prefixes are resumable; malformed/empty slots stay consumed."""
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
            raise ValueError
        rows = tuple(
            json.loads(line, object_pairs_hook=_unique)
            for line in payload.decode("utf-8").splitlines()
        )
        if not 0 < len(rows) <= MAX_ROWS:
            raise ValueError
        if b"".join(canonical(row) + b"\n" for row in rows) != payload:
            raise ValueError
        facts = rows[0]["facts"]
        validate_facts(facts)
        effects = dict.fromkeys(BUDGETS, 0)
        phase = "START"
        last_time = utc(datetime.fromisoformat(facts["authorized_at"]))
        ready = False
        for index, row in enumerate(rows):
            if (
                set(row)
                != {
                    "schema",
                    "event",
                    "classification",
                    "facts",
                    "binding",
                    "effects",
                    "budgets",
                    "observed_at",
                    "proof",
                }
                or row["schema"] != SCHEMA
                or row["binding"] != digest(facts)
                or canonical(row["facts"]) != canonical(facts if index == 0 else None)
                or canonical(row["budgets"]) != canonical(BUDGETS)
                or phase == "FINAL"
            ):
                raise ValueError
            now = utc(datetime.fromisoformat(row["observed_at"]))
            if now.isoformat() != row["observed_at"] or now < last_time:
                raise ValueError
            last_time = now
            event = row["event"]
            if event == "FINAL":
                if row["classification"] not in TERMINALS or index == 0:
                    raise ValueError
                success = row["classification"] in {
                    "NO_SIGNAL",
                    "RISK_REJECTED",
                    "PAPER_EXECUTED",
                }
                if success and phase != "D1R8_DELEGATION_INTENT":
                    raise ValueError
                if success != (row["proof"] is not None):
                    raise ValueError
                phase = "FINAL"
            else:
                if row["classification"] is not None:
                    raise ValueError
                allowed = {
                    "START": {INITIAL[0]},
                    INITIAL[0]: {INITIAL[1]},
                    INITIAL[1]: {INITIAL[2]},
                    INITIAL[2]: {"SCHEDULER_CREATE_INTENT", "SUPERVISOR_READY"},
                    "SCHEDULER_CREATE_INTENT": {"SCHEDULER_CREATE_ACK"},
                    "SCHEDULER_CREATE_ACK": {"SUPERVISOR_READY"},
                    "SUPERVISOR_READY": {"SCHEDULER_RUN_INTENT"},
                    "SCHEDULER_RUN_INTENT": {"SCHEDULER_RUN_ACK"},
                    "SCHEDULER_RUN_ACK": {
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
                }
                if event not in allowed[phase]:
                    raise ValueError
                for state, counter in (
                    ("D1R7_DELEGATION_INTENT", "d1r7_attempts"),
                    ("D1R8_DELEGATION_INTENT", "d1r8_attempts"),
                    ("SCHEDULER_CREATE_INTENT", "scheduler_creates"),
                    ("SCHEDULER_RUN_INTENT", "scheduler_runs"),
                ):
                    if event == state:
                        effects[counter] += 1
                if (event == "D1R7_READY") != (row["proof"] is not None):
                    raise ValueError
                if event == "D1R7_READY":
                    ready = True
                if event == "D1R8_DELEGATION_INTENT" and not ready:
                    raise ValueError
                phase = event
            if row["proof"] is not None and (
                type(row["proof"]) is not dict
                or set(row["proof"]) != {"bytes", "sha256"}
                or type(row["proof"]["bytes"]) is not int
                or not 0 < row["proof"]["bytes"] <= 1048576
                or not is_hash(row["proof"]["sha256"])
            ):
                raise ValueError
            if canonical(row["effects"]) != canonical(effects) or any(
                effects[k] > BUDGETS[k] for k in effects
            ):
                raise ValueError
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
        raise ValueError("D1R9 canonical journal rejected") from None


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


class Journal:
    def __init__(self, path: Path, payload: bytes, file_id: tuple[int, int]) -> None:
        self.path, self.payload, self.identity = path, payload, file_id
        self.rows = parse(payload)
        self.last_clock = utc(datetime.fromisoformat(self.rows[-1]["observed_at"]))
        if path.name != reservation_name(self.facts["target_session"]):
            raise ValueError("deterministic slot mismatch")

    @property
    def facts(self) -> dict:
        return self.rows[0]["facts"]

    @property
    def state(self) -> str:
        return self.rows[-1]["event"]

    @classmethod
    def reserve(cls, parent: Path, facts: dict) -> Journal:
        validate_facts(facts)
        row = dict(
            schema=SCHEMA,
            event=INITIAL[0],
            classification=None,
            facts=facts,
            binding=digest(facts),
            effects=dict.fromkeys(BUDGETS, 0),
            budgets=BUDGETS,
            observed_at=facts["authorized_at"],
            proof=None,
        )
        payload = canonical(row) + b"\n"
        parse(payload)
        path = parent / reservation_name(facts["target_session"])
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
            ("D1R7_DELEGATION_INTENT", "d1r7_attempts"),
            ("D1R8_DELEGATION_INTENT", "d1r8_attempts"),
            ("SCHEDULER_CREATE_INTENT", "scheduler_creates"),
            ("SCHEDULER_RUN_INTENT", "scheduler_runs"),
        ):
            if event == state:
                effects[counter] += 1
        row = dict(
            schema=SCHEMA,
            event=event,
            classification=classification,
            facts=None,
            binding=digest(self.facts),
            effects=effects,
            budgets=BUDGETS,
            observed_at=utc(at).isoformat(),
            proof=proof,
        )
        data = canonical(row) + b"\n"
        proposed = self.payload + data
        rows = parse(proposed)
        if read(self.path, MAX_BYTES, self.identity) != self.payload:
            raise ValueError("journal changed")
        flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(self.path, flags), "ab") as stream:
            if identity(os.fstat(stream.fileno())) != self.identity:
                raise ValueError("append handle changed")
            if stream.write(data) != len(data):
                raise OSError("short append")
            stream.flush()
            os.fsync(stream.fileno())
        if read(self.path, MAX_BYTES, self.identity) != proposed:
            raise ValueError("durable transition readback failed")
        self.payload, self.rows = proposed, rows


def find_active(parent: Path) -> Journal | None:
    """Closed deterministic namespace only; any malformed slot fails closed."""
    checked_path(parent)
    active = []
    for index, path in enumerate(parent.glob("arch134-d1r9-SPY-*.jsonl")):
        if index >= 1024:
            raise ValueError("authorization namespace bound exceeded")
        journal = Journal.load(path)
        if journal.state != "FINAL":
            active.append(journal)
    if len(active) > 1:
        raise ValueError("ambiguous active authorizations")
    return active[0] if active else None
