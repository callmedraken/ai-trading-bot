"""D1R7 prerequisite evidence only; no D1 or operational effect authority."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO, Protocol
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.pre_market_wake_overnight import (
    parse_arm,
    plan_from_facts,
)
from trading_bot.review_paper.pre_market_wake_qualification import (
    parse_wake_journal,
    validate_source_identity,
)
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import ProductionStrategyContract

SCHEMA = "arch134-d1r7-d1-session-authorization/v1"
CHECKPOINT = "arch134-d1r7-d1-session-authorization"
BRANCH = "feature/robinhood-production-paper-d1-session-authorization"
D1_BRANCH = "feature/robinhood-production-paper-d1-session-execution"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
INTERLOCK = "AUTHORIZE_ARCH134_D1R7_ONE_D1_SESSION_PREREQUISITE_RECORD"
READY = "READY_FOR_SEPARATE_D1_SESSION_AUTHORIZATION"
QUALIFICATION_SESSION = "2026-10-16"
PARENT = Path(r"F:\AI\temp\qualification")
MAX_BYTES = 131072
EVENTS = (
    "AUTHORIZATION_RESERVED",
    "SOURCE_ADMITTED",
    "PREDECESSOR_BOUND",
    "SESSION_BOUND",
    "D1_POLICY_BOUND",
    "SOURCE_READMITTED",
    "FINAL",
)
COUNTERS = (
    "d1_invocations",
    "d1r5_invocations",
    "alpaca_requests",
    "provider_requests",
    "credential_reads",
    "credential_writes",
    "oauth_interactions",
    "robinhood_reads",
    "robinhood_reviews",
    "strategy_evaluations",
    "prepare_attempts",
    "execute_attempts",
    "paper_mutations",
    "broker_placements",
    "scheduler_reads",
    "scheduler_creates",
    "scheduler_updates",
    "scheduler_runs",
    "scheduler_deletes",
    "acl_mutations",
    "d2_invocations",
    "live_effects",
    "production_sqlite_reads",
    "production_sqlite_writes",
    "armed_session_store_reads",
    "armed_session_store_writes",
    "review_paper_store_reads",
    "review_paper_store_writes",
)
AUTHORITY = ("d1_execution_authorized", "prepare_authorized", "execute_authorized")


@dataclass(frozen=True, slots=True)
class EvidencePin:
    basename: str
    size: int
    sha256: str
    schema: str
    head: str
    tree: str


D1R5 = EvidencePin(
    "arch134-d1r5-2026-10-16-7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343.jsonl",
    6714,
    "9967e978cbf5f97afd9453e24fcfc3cdee4e864b589751fda3051c833b6d32cf",
    "arch134-d1r5-pre-market-wake-qualification/v1",
    "7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343",
    "c826c2a71e6d907866ce3f80afce479d38ab7842",
)
D1R6 = EvidencePin(
    "arch134-d1r6-2026-10-16-7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343-"
    "a36de3bfe81a6e1a94fb3deeec7e579145939f52-"
    "6cde732e02e92eb2b34281672cdb7744250355b1.jsonl",
    19321,
    "837825d8cb3042431276bf6b7bdee0580da40ee2ef6a761eace86976924275f2",
    "arch134-d1r6-overnight-wake-arming/v1",
    "a36de3bfe81a6e1a94fb3deeec7e579145939f52",
    "6cde732e02e92eb2b34281672cdb7744250355b1",
)


def canonical(value: object) -> bytes:
    """Canonical transport with exact numeric types and no nonfinite values."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def utc(value: datetime) -> datetime:
    """Reject naive or non-datetime clocks."""
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock rejected")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Source:
    branch: str
    head: str
    tree: str
    origin: str = ORIGIN

    def __post_init__(self) -> None:
        validate_source_identity(self.head)
        validate_source_identity(self.tree)
        if type(self.branch) is not str or self.origin != ORIGIN:
            raise ValueError("source identity rejected")

    def facts(self) -> dict[str, str]:
        return dict(
            origin=self.origin, branch=self.branch, head=self.head, tree=self.tree
        )


def fixed_policy() -> dict[str, object]:
    """Fresh inert policy material; decimal values have canonical string spelling."""
    return {
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


def _predecessor_facts(pin: EvidencePin, classification: str) -> dict[str, object]:
    return {
        "basename": pin.basename,
        "bytes": pin.size,
        "sha256": pin.sha256,
        "schema": pin.schema,
        "source_head": pin.head,
        "source_tree": pin.tree,
        "qualification_session": QUALIFICATION_SESSION,
        "final": classification,
    }


@dataclass(frozen=True, slots=True)
class Plan:
    source: Source
    intended_d1: Source
    observed_at: datetime

    def __post_init__(self) -> None:
        if (
            type(self.source) is not Source
            or type(self.intended_d1) is not Source
            or self.source.branch != BRANCH
            or self.intended_d1.branch != D1_BRANCH
        ):
            raise ValueError("fixed source branch rejected")
        instant = utc(self.observed_at)
        session = instant.astimezone(ZoneInfo("America/New_York")).date()
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(session)
        if schedule is None or instant >= utc(schedule.closes_at) - timedelta(
            minutes=5
        ):
            raise ValueError("current published session unavailable or expired")

    @property
    def target(self) -> date:
        return utc(self.observed_at).astimezone(ZoneInfo("America/New_York")).date()

    @property
    def expires_at(self) -> datetime:
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(self.target)
        return utc(schedule.closes_at) - timedelta(minutes=5)

    @property
    def name(self) -> str:
        # Neither source revision nor a caller destination changes the slot.
        material = [SCHEMA, self.target.isoformat(), D1R5.sha256, D1R6.sha256]
        digest = hashlib.sha256(canonical(material)).hexdigest()
        return f"arch134-d1r7-{self.target}-{digest}.jsonl"

    @property
    def facts(self) -> dict[str, object]:
        strategy = ProductionStrategyContract(
            self.target,
            self.intended_d1.head,
            self.intended_d1.tree,
            Symbol("SPY"),
            MovingAverageCrossoverConfig(2, 3, Decimal("1")),
        )
        return {
            "checkpoint": CHECKPOINT,
            "source": self.source.facts(),
            "intended_d1": self.intended_d1.facts(),
            "qualification_session": QUALIFICATION_SESSION,
            "target_session": self.target.isoformat(),
            "observed_at": utc(self.observed_at).isoformat(),
            "authorization_expires_at": self.expires_at.isoformat(),
            "reservation_basename": self.name,
            "d1r5": _predecessor_facts(D1R5, "PASS"),
            "d1r6": {
                **_predecessor_facts(D1R6, "ARMED"),
                "authority_kind": "ORDINARY_ARM",
                "historical_scheduler_create_calls": 1,
            },
            "strategy_contract": json.loads(strategy.to_json()),
            "d1_policy": fixed_policy(),
        }

    def require_current(self, observed: datetime) -> None:
        """No backdating, next-session rollover or extension of the admission close."""
        now = utc(observed)
        if (
            now < utc(self.observed_at)
            or now >= self.expires_at
            or now.astimezone(ZoneInfo("America/New_York")).date() != self.target
        ):
            raise ValueError("session expired or clock drift")


def bind_predecessors(d1r5: bytes, d1r6: bytes) -> None:
    """Exact accepted ordinary-arm lineage; pure public predecessor parsing only."""
    for payload, pin in ((d1r5, D1R5), (d1r6, D1R6)):
        if (
            type(payload) is not bytes
            or len(payload) != pin.size
            or hashlib.sha256(payload).hexdigest() != pin.sha256
        ):
            raise ValueError("predecessor bytes rejected")
    wake = parse_wake_journal(d1r5)
    if (
        tuple(r["event"] for r in wake)
        != (
            "QUALIFICATION_RESERVED",
            "SOURCE_ADMITTED",
            "WAITING_FOR_MARKET",
            "WAKE_OBSERVED",
            "SOURCE_READMITTED",
            "FINAL",
        )
        or wake[-1]["classification"] != "PASS"
    ):
        raise ValueError("D1R5 terminal PASS required")
    for r in wake:
        if (r["schema"], r["source_head"], r["source_tree"], r["target_session"]) != (
            D1R5.schema,
            D1R5.head,
            D1R5.tree,
            QUALIFICATION_SESSION,
        ):
            raise ValueError("D1R5 lineage rejected")
    arm = parse_arm(d1r6)
    if (
        tuple(r["event"] for r in arm)
        != (
            "ARMING_RESERVED",
            "D1R6_SOURCE_ADMITTED",
            "D1R5_TARGET_ADMITTED",
            "TASK_ABSENCE_CONFIRMED",
            "TASK_CREATE_INTENT",
            "TASK_CREATE_RETURNED",
            "TASK_CONFIRMED",
            "FINAL",
        )
        or arm[-1]["classification"] != "ARMED"
    ):
        raise ValueError("ordinary D1R6 FINAL ARMED required")
    plan = plan_from_facts(arm[-1]["facts"])
    if (
        plan.source_head,
        plan.source_tree,
        plan.schedule.session_date.isoformat(),
        plan.arm_name,
        plan.result_name,
    ) != (D1R6.head, D1R6.tree, QUALIFICATION_SESSION, D1R6.basename, D1R5.basename):
        raise ValueError("D1R6 lineage rejected")
    if any(
        r["schema"] != D1R6.schema
        or type(r["scheduler_task_create_calls"]) is not int
        or r["scheduler_task_create_calls"] != int(i >= 4)
        for i, r in enumerate(arm)
    ):
        raise ValueError("D1R6 historical one-create fact rejected")


def record(plan: Plan, event: str) -> dict[str, object]:
    """Closed record, with no executable authority even at FINAL."""
    return {
        "schema": SCHEMA,
        "event": event,
        "classification": READY if event == "FINAL" else None,
        "reason_code": "PREREQUISITES_BOUND" if event == "FINAL" else None,
        "facts": plan.facts,
        "budgets": dict.fromkeys(COUNTERS, 0),
        "effects": dict.fromkeys(COUNTERS, 0),
        "authority": dict.fromkeys(AUTHORITY, False),
    }


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def parse_authorization(payload: bytes) -> tuple[dict[str, object], ...]:
    """Validate complete canonical evidence; never confer D1 authority."""
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
            raise ValueError
        records = tuple(
            json.loads(line, object_pairs_hook=_pairs)
            for line in payload.decode("utf-8").splitlines()
        )
        if len(records) != len(EVENTS):
            raise ValueError
        f = records[0]["facts"]
        plan = Plan(
            Source(**f["source"]),
            Source(**f["intended_d1"]),
            datetime.fromisoformat(f["observed_at"]),
        )
        expected = b"".join(canonical(record(plan, event)) + b"\n" for event in EVENTS)
        if expected != payload:
            raise ValueError
        return records
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        UnicodeError,
        OverflowError,
    ):
        raise ValueError("D1R7 canonical evidence rejected") from None


def checked_path(path: Path) -> None:
    """Reject links/reparse points in every existing path component."""
    if not path.is_absolute():
        raise ValueError("absolute path required")
    for component in (path, *path.parents):
        metadata = component.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("link or reparse point rejected")


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or not metadata.st_ino
        or getattr(metadata, "st_file_attributes", 0) & 0x400
    ):
        raise ValueError("regular single-link file required")
    return metadata.st_dev, metadata.st_ino


def _same_file(path: Path, stream: BinaryIO, identity: tuple[int, int]) -> None:
    checked_path(path)
    if (
        _identity(path.lstat()) != identity
        or _identity(os.fstat(stream.fileno())) != identity
    ):
        raise ValueError("opened handle identity changed")


def read_evidence(
    path: Path, maximum: int, identity: tuple[int, int] | None = None
) -> bytes:
    """Bounded stable read through a regular single-link opened file handle."""
    checked_path(path)
    before = path.lstat()
    expected = _identity(before)
    if (identity is not None and identity != expected) or before.st_size > maximum:
        raise ValueError("evidence identity or size rejected")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        _same_file(path, stream, expected)
        opened = os.fstat(stream.fileno())
        payload = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        _same_file(path, stream, expected)
        if (
            len(payload) > maximum
            or len(payload) != before.st_size
            or (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
            != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or after.st_size != path.lstat().st_size
        ):
            raise ValueError("evidence read changed")
    return payload


class Runtime(Protocol):
    parent: Path

    def admit(self, source: Source) -> tuple[Path, ...]: ...
    def clock(self) -> datetime: ...


def publish_prerequisite(
    runtime: Runtime, source: Source, intended_d1: Source, interlock: str
) -> str:
    """Reserve one slot; every ambiguity after reservation consumes it."""
    if type(interlock) is not str or interlock != INTERLOCK:
        raise ValueError("D1R7-only interlock required")
    # Plan validates both fixed branches before any host seam or evidence access.
    plan = Plan(source, intended_d1, runtime.clock())
    roots = (*runtime.admit(source), *runtime.admit(intended_d1))
    parent = runtime.parent
    checked_path(parent)
    if (
        not parent.is_dir()
        or not roots
        or any(parent.resolve().is_relative_to(root.resolve()) for root in roots)
        or parent.resolve().is_relative_to(Path(r"F:\AITradingBot").resolve())
    ):
        raise ValueError("external existing parent required")

    def predecessors() -> None:
        bind_predecessors(
            read_evidence(parent / D1R5.basename, D1R5.size),
            read_evidence(parent / D1R6.basename, D1R6.size),
        )

    predecessors()
    plan.require_current(runtime.clock())
    path = parent / plan.name
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    # Exclusive create is the irrevocable fence, including an empty reservation.
    fd = os.open(path, flags, 0o600)
    stream = None
    try:
        stream = os.fdopen(fd, "wb")
        identity = _identity(os.fstat(stream.fileno()))
        expected = b""
        for event in EVENTS:
            _same_file(path, stream, identity)
            if event == "SOURCE_READMITTED":
                if (*runtime.admit(source), *runtime.admit(intended_d1)) != roots:
                    raise ValueError("source roots changed")
                predecessors()
            plan.require_current(runtime.clock())
            data = canonical(record(plan, event)) + b"\n"
            if stream.write(data) != len(data):
                raise OSError("short publication write")
            stream.flush()
            os.fsync(stream.fileno())
            expected += data
            _same_file(path, stream, identity)
            if read_evidence(path, MAX_BYTES, identity) != expected:
                raise ValueError("durable readback mismatch")
        closing = stream
        stream = None
        closing.close()
        payload = read_evidence(path, MAX_BYTES, identity)
        if payload != expected:
            raise ValueError("closed publication readback mismatch")
        parse_authorization(payload)
        plan.require_current(runtime.clock())
        return READY
    finally:
        # Never repair, overwrite, delete, rename, resume or retry the reserved slot.
        if stream is not None:
            stream.close()
