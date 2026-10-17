"""D1R8 durable one-shot journal; no repair, retry, or compensation."""

from __future__ import annotations

import hashlib
import json
import os
from copy import copy
from datetime import datetime
from pathlib import Path

from trading_bot.review_paper import d1_session_authorization as prerequisite

SCHEMA = "arch134-d1r8-d1-session-execution-consumer/v1"
MAX_BYTES = 1048576
BRANCH = prerequisite.D1_BRANCH
PRODUCER_HEAD = "30322c49b13b80af8d20acee4bdb1efd83d86260"
PRODUCER_TREE = "b7dc7f054fca50c3ab784505f264b6f716a45dff"
BUDGETS = {
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
STATES = (
    "SESSION_RESERVED",
    "SOURCE_AND_D1R7_BOUND",
    "WRITE_READINESS_STARTED",
    "WRITE_READINESS_CONFIRMED",
    "LEGACY_SESSION_FENCE_CLAIMED",
    "CREDENTIAL_READ_INTENT",
    "CREDENTIAL_READ_CONFIRMED",
    *[s for _ in range(4) for s in ("HISTORY_READ_INTENT", "HISTORY_READ_CONFIRMED")],
    "HISTORY_READY",
    "STRATEGY_STARTED",
    "STRATEGY_DECIDED",
    "PREPARE_STARTED",
    "QUOTE_INTENT",
    "QUOTE_CONFIRMED",
    "PREPARED",
    "EXECUTE_STARTED",
    "ACCOUNT_READ",
    "BASELINE_ORDER_READS",
    "REVIEW_INTENT",
    "REVIEW_CONFIRMED",
    "POST_REVIEW_ORDER_READS",
    "PAPER_WRITE_INTENT",
    "PAPER_WRITE_ACKNOWLEDGED",
)
TERMINALS = {
    "NO_SIGNAL",
    "RISK_REJECTED",
    "PAPER_EXECUTED",
    "BLOCKED",
    "SESSION_EXPIRED",
    "INDETERMINATE",
}
FIELDS = {
    "schema",
    "event",
    "action",
    "counter",
    "facts",
    "binding_sha256",
    "budgets",
    "effects",
    "classification",
    "observed_at",
    "result_sha256",
}
HASHED_STATES = {
    "HISTORY_READY",
    "STRATEGY_DECIDED",
    "PREPARED",
    "PAPER_WRITE_ACKNOWLEDGED",
}
ALLOWED = {
    "write_readiness_attempts": "WRITE_READINESS_STARTED",
    "compatibility_reservations": "WRITE_READINESS_CONFIRMED",
    "alpaca_credential_reads": "CREDENTIAL_READ_INTENT",
    "robinhood_credential_reads": "PREPARE_STARTED",
    "alpaca_history_requests": "HISTORY_READ_INTENT",
    "strategy_evaluations": "STRATEGY_STARTED",
    "prepare_attempts": "PREPARE_STARTED",
    "quote_requests": "QUOTE_INTENT",
    "execute_attempts": "EXECUTE_STARTED",
    "account_resolutions": "ACCOUNT_READ",
    "order_history_attempts": ("BASELINE_ORDER_READS", "POST_REVIEW_ORDER_READS"),
    "order_reviews": "REVIEW_INTENT",
    "paper_fill_mutations": "PAPER_WRITE_INTENT",
}


def digest(value: object) -> str:
    return hashlib.sha256(prerequisite.canonical(value)).hexdigest()


def validate_facts(facts: dict) -> prerequisite.Plan:
    """Reconstruct the complete canonical contract rather than trusting labels."""
    if type(facts) is not dict or set(facts) != {
        "prerequisite",
        "d1r7_bytes",
        "d1r7_sha256",
        "publication_confirmed",
    }:
        raise ValueError("binding fields rejected")
    f = facts["prerequisite"]
    plan = prerequisite.Plan(
        prerequisite.Source(**f["source"]),
        prerequisite.Source(**f["intended_d1"]),
        datetime.fromisoformat(f["observed_at"]),
    )
    if (
        prerequisite.canonical(f) != prerequisite.canonical(plan.facts)
        or (plan.source.head, plan.source.tree) != (PRODUCER_HEAD, PRODUCER_TREE)
        or facts["publication_confirmed"] is not True
        or type(facts["d1r7_bytes"]) is not int
        or not 0 < facts["d1r7_bytes"] <= prerequisite.MAX_BYTES
        or type(facts["d1r7_sha256"]) is not str
        or len(facts["d1r7_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in facts["d1r7_sha256"])
    ):
        raise ValueError("binding rejected")
    return plan


def reservation_name(target: str) -> str:
    """The sole slot depends only on schema, SPY and the target session."""
    from datetime import date

    if date.fromisoformat(target).isoformat() != target:
        raise ValueError("target rejected")
    return f"arch134-d1r8-SPY-{target}.jsonl"


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


class _Replay:
    """Single closed reducer shared by independent parsing and durable appends."""

    def __init__(self, facts: dict) -> None:
        self.plan = validate_facts(facts)
        self.binding = digest(facts)
        self.effects = dict.fromkeys(BUDGETS, 0)
        self.pending = None
        self.phase = -1
        self.last_time = prerequisite.utc(self.plan.observed_at)
        self.terminal = False
        self.baseline_pages = 0
        self.index = 0

    def add(self, row: dict) -> None:
        if (
            set(row) != FIELDS
            or (self.index == 0 and row["event"] != "SESSION_RESERVED")
            or row["schema"] != SCHEMA
            or row["binding_sha256"] != self.binding
            or (
                prerequisite.canonical(row["budgets"])
                != prerequisite.canonical(BUDGETS)
            )
            or (self.index > 0 and row["facts"] is not None)
            or self.terminal
        ):
            raise ValueError
        result_hash = row["result_sha256"]
        needs_hash = row["event"] in HASHED_STATES and row["action"] is None
        if needs_hash:
            if (
                type(result_hash) is not str
                or len(result_hash) != 64
                or any(c not in "0123456789abcdef" for c in result_hash)
            ):
                raise ValueError
        elif result_hash is not None:
            raise ValueError
        at = prerequisite.utc(datetime.fromisoformat(row["observed_at"]))
        if at.isoformat() != row["observed_at"] or at < self.last_time:
            raise ValueError
        self.last_time = at
        event, action, counter = (row["event"], row["action"], row["counter"])
        if event == "FINAL":
            result = row["classification"]
            if action is not None or counter is not None or result not in TERMINALS:
                raise ValueError
            if self.pending is not None and result != "INDETERMINATE":
                raise ValueError
            if result in {"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"}:
                required = {
                    "NO_SIGNAL": "STRATEGY_DECIDED",
                    "RISK_REJECTED": "PREPARED",
                    "PAPER_EXECUTED": "PAPER_WRITE_ACKNOWLEDGED",
                }[result]
                if STATES[self.phase] != required or self.pending is not None:
                    raise ValueError
                self.plan.require_current(at)
                expected = {
                    "alpaca_credential_reads": 2,
                    "alpaca_history_requests": 4,
                    "strategy_evaluations": 1,
                }
                if result == "NO_SIGNAL":
                    expected.update(
                        robinhood_credential_reads=0,
                        prepare_attempts=0,
                        execute_attempts=0,
                        paper_fill_mutations=0,
                    )
                else:
                    expected.update(
                        robinhood_credential_reads=2,
                        prepare_attempts=1,
                        quote_requests=1,
                    )
                if result == "PAPER_EXECUTED":
                    expected.update(
                        execute_attempts=1,
                        account_resolutions=1,
                        order_reviews=1,
                        paper_fill_mutations=1,
                    )
                    if not 2 <= self.effects["order_history_attempts"] <= 200:
                        raise ValueError
                if any((self.effects[k] != v for k, v in expected.items())):
                    raise ValueError
            self.terminal = True
        else:
            if row["classification"] is not None:
                raise ValueError
            if action is None:
                if (
                    counter is not None
                    or self.pending is not None
                    or event != STATES[self.phase + 1]
                ):
                    raise ValueError
                self.phase += 1
                required = {
                    "WRITE_READINESS_CONFIRMED": {"write_readiness_attempts": 1},
                    "LEGACY_SESSION_FENCE_CLAIMED": {"compatibility_reservations": 1},
                    "CREDENTIAL_READ_CONFIRMED": {"alpaca_credential_reads": 2},
                    "HISTORY_READY": {"alpaca_history_requests": 4},
                    "STRATEGY_DECIDED": {"strategy_evaluations": 1},
                    "QUOTE_INTENT": {
                        "robinhood_credential_reads": 2,
                        "prepare_attempts": 1,
                    },
                    "QUOTE_CONFIRMED": {"quote_requests": 1},
                    "ACCOUNT_READ": {"execute_attempts": 1},
                    "BASELINE_ORDER_READS": {"account_resolutions": 1},
                    "REVIEW_CONFIRMED": {"order_reviews": 1},
                    "PAPER_WRITE_ACKNOWLEDGED": {"paper_fill_mutations": 1},
                }.get(event, {})
                if event == "HISTORY_READ_CONFIRMED":
                    required = {
                        "alpaca_history_requests": STATES[: self.phase + 1].count(event)
                    }
                if any((self.effects[k] != v for k, v in required.items())):
                    raise ValueError
                if event == "REVIEW_INTENT":
                    self.baseline_pages = self.effects["order_history_attempts"]
                    if not 1 <= self.baseline_pages <= 100:
                        raise ValueError
                if event == "PAPER_WRITE_INTENT" and (
                    not 1
                    <= self.effects["order_history_attempts"] - self.baseline_pages
                    <= 100
                ):
                    raise ValueError
            else:
                if (
                    self.phase < 0
                    or event != STATES[self.phase]
                    or counter not in ALLOWED
                ):
                    raise ValueError
                permitted = ALLOWED[counter]
                if event not in ((permitted,) if type(permitted) is str else permitted):
                    raise ValueError
                if action == "INTENT" and self.pending is None:
                    self.effects[counter] += 1
                    if counter.endswith("credential_reads"):
                        self.effects["credential_reads"] += 1
                    self.pending = counter
                elif action == "ACK" and self.pending == counter:
                    self.pending = None
                else:
                    raise ValueError
        if (
            type(row["effects"]) is not dict
            or set(row["effects"]) != set(BUDGETS)
            or any(
                (
                    type(v) is not int or not 0 <= v <= BUDGETS[k]
                    for k, v in row["effects"].items()
                )
            )
            or (row["effects"] != self.effects)
        ):
            raise ValueError
        self.index += 1


def parse_journal(payload: bytes, *, complete: bool = True) -> tuple[dict, ...]:
    """Replay exact state transitions and every attempt/ack; prefixes are consumed."""
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
            raise ValueError
        rows = tuple(
            json.loads(line, object_pairs_hook=_unique)
            for line in payload.decode("utf-8").splitlines()
        )
        if not rows or len(rows) > 600:
            raise ValueError
        if b"".join(prerequisite.canonical(r) + b"\n" for r in rows) != payload:
            raise ValueError
        replay = _Replay(rows[0]["facts"])
        for row in rows:
            replay.add(row)
        if complete and not replay.terminal:
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
        raise ValueError("D1R8 canonical journal rejected") from None


class Journal:
    """An exclusive create consumes the slot even if the first write fails."""

    def __init__(self, parent: Path, facts: dict) -> None:
        plan = validate_facts(facts)
        prerequisite.checked_path(parent)
        self.path = parent / reservation_name(plan.target.isoformat())
        self.facts = facts
        self.replay = _Replay(facts)
        self.effects = dict.fromkeys(BUDGETS, 0)
        self.pending = None
        self.phase = -1
        self.expected = b""
        self.broken = False
        self.stream = None
        fd = os.open(
            self.path,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            self.stream = os.fdopen(fd, "wb")
            info = os.fstat(self.stream.fileno())
            self.identity = info.st_dev, info.st_ino
            self.stream.flush()
            os.fsync(self.stream.fileno())
            if prerequisite.read_evidence(self.path, 0, self.identity) != b"":
                raise ValueError("reservation readback rejected")
        except BaseException:
            self.broken = True
            if self.stream is not None:
                self.stream.close()
            else:
                os.close(fd)
            raise

    def append(
        self,
        event: str,
        at: datetime,
        *,
        action: str | None = None,
        counter: str | None = None,
        classification: str | None = None,
        result_sha256: str | None = None,
    ) -> None:
        if self.broken or self.stream is None:
            raise ValueError("journal unavailable; consumed")
        effects = dict(self.effects)
        if action == "INTENT":
            effects[counter] += 1
            if counter.endswith("credential_reads"):
                effects["credential_reads"] += 1
        row = dict(
            schema=SCHEMA,
            event=event,
            action=action,
            counter=counter,
            facts=self.facts if not self.expected else None,
            binding_sha256=digest(self.facts),
            budgets=BUDGETS,
            effects=effects,
            classification=classification,
            observed_at=prerequisite.utc(at).isoformat(),
            result_sha256=result_sha256,
        )
        data = prerequisite.canonical(row) + b"\n"
        expected = self.expected + data
        if len(expected) > MAX_BYTES or self.replay.index >= 600:
            raise ValueError("journal bound exhausted")
        replay = copy(self.replay)
        replay.effects = dict(self.replay.effects)
        replay.add(row)
        try:
            if (
                prerequisite.read_evidence(self.path, len(self.expected), self.identity)
                != self.expected
            ):
                raise ValueError("journal changed")
            info = os.fstat(self.stream.fileno())
            if (info.st_dev, info.st_ino) != self.identity or info.st_nlink != 1:
                raise ValueError("journal handle changed")
            if self.stream.write(data) != len(data):
                raise OSError("short journal write")
            self.stream.flush()
            os.fsync(self.stream.fileno())
            if (
                prerequisite.read_evidence(self.path, len(expected), self.identity)
                != expected
            ):
                raise ValueError("journal readback rejected")
        except BaseException:
            self.broken = True
            raise
        self.replay = replay
        self.expected = expected
        self.effects = effects
        if action == "INTENT":
            self.pending = counter
        elif action == "ACK":
            self.pending = None
        elif event != "FINAL":
            self.phase += 1

    @property
    def state(self) -> str:
        return STATES[self.phase]

    def close(self) -> None:
        if self.stream is not None:
            stream, self.stream = self.stream, None
            try:
                stream.close()
                if (
                    prerequisite.read_evidence(
                        self.path, len(self.expected), self.identity
                    )
                    != self.expected
                ):
                    raise ValueError("closed journal changed")
            except BaseException:
                self.broken = True
                raise
