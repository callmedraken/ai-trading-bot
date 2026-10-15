"""One-session overnight wake wrapper; D1R5 remains the qualification authority."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath
from typing import BinaryIO, Protocol
from zoneinfo import ZoneInfo

from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.pre_market_wake_qualification import (
    MAX_JOURNAL_BYTES as D1R5_MAX_BYTES,
)
from trading_bot.review_paper.pre_market_wake_qualification import (
    parse_wake_journal,
    validate_source_identity,
)
from trading_bot.review_paper.session_admission import ReviewPaperSessionSchedule

SCHEMA = "arch134-d1r6-overnight-wake-arming/v1"
ARM_INTERLOCK = "AUTHORIZE_ARCH134_D1R6_ONE_OVERNIGHT_WAKE_ARMING"
TARGET_HEAD = "7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343"
TARGET_TREE = "c826c2a71e6d907866ce3f80afce479d38ab7842"
TASK_PATH = r"\AITradingBot-Arch134-D1R6-OvernightWake-v1"
WORKTREE = PureWindowsPath(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-overnight-wake-arming"
)
TARGET_WORKTREE = PureWindowsPath(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-premarket-wake-qualification"
)
QUALIFICATION_PARENT = PureWindowsPath(r"F:\AI\temp\qualification")
PYTHON = PureWindowsPath(r"F:\AI\ai-trading-bot\.venv\Scripts\python.exe")
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
MAX_BYTES = 65536
MAX_HORIZON = timedelta(hours=18)
EVENTS = (
    "ARMING_RESERVED",
    "D1R6_SOURCE_ADMITTED",
    "D1R5_TARGET_ADMITTED",
    "TASK_ABSENCE_CONFIRMED",
    "TASK_CREATE_INTENT",
    "TASK_CREATE_RETURNED",
    "TASK_CONFIRMED",
)
ZERO_EFFECTS = (
    "PRODUCTION_SQLITE_READS",
    "PRODUCTION_SQLITE_WRITES",
    "CREDENTIAL_READS",
    "CREDENTIAL_WRITES",
    "PROVIDER_CALLS",
    "ROBINHOOD_READS",
    "ROBINHOOD_REVIEWS",
    "PAPER_MUTATIONS",
    "BROKER_PLACEMENTS",
    "STRATEGY_EVALUATIONS",
    "PREPARE_ATTEMPTS",
    "EXECUTE_ATTEMPTS",
    "ACL_MUTATIONS",
    "REAL_TASK_RUNS",
    "D1_OPERATIONS",
    "D2_OPERATIONS",
    "LIVE_EFFECTS",
)
IMPLEMENTATION_ZERO_EFFECTS = (
    *ZERO_EFFECTS,
    "REAL_SCHEDULER_READS",
    "REAL_SCHEDULER_MUTATIONS",
    "REAL_D1R5_EXECUTIONS",
    "REAL_CLOCK_SLEEPS",
)


def utc(value: datetime) -> datetime:
    """Require an aware datetime and normalize to UTC."""
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock rejected")
    return value.astimezone(UTC)


def canonical(value: object) -> bytes:
    """Sorted compact JSON; no NaN or non-ASCII transport ambiguity."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class Principal:
    name: str
    sid: str

    def __post_init__(self) -> None:
        if (
            type(self.name) is not str
            or not 3 <= len(self.name) <= 256
            or re.fullmatch(r"[^\\\x00-\x1f<>\"&]+\\[^\\\x00-\x1f<>\"&]+", self.name)
            is None
            or type(self.sid) is not str
            or re.fullmatch(r"S-1-5-21-(?:[0-9]{1,10}-){3}[0-9]{1,10}", self.sid)
            is None
        ):
            raise ValueError("principal rejected")


@dataclass(frozen=True, slots=True)
class Plan:
    source_head: str
    source_tree: str
    observed_at: datetime
    principal: Principal

    def __post_init__(self) -> None:
        validate_source_identity(self.source_head)
        validate_source_identity(self.source_tree)
        utc(self.observed_at)
        if type(self.principal) is not Principal or self.schedule is None:
            raise ValueError("no eligible session")

    @property
    def schedule(self) -> ReviewPaperSessionSchedule | None:
        authority = NYSEPublishedRegularSessionAuthority()
        observed = utc(self.observed_at)
        first = observed.astimezone(ZoneInfo("America/New_York")).date()
        for offset in range(2):
            day = first + timedelta(days=offset)
            if day.year not in authority.supported_years:
                continue
            schedule = authority.schedule_for(day)
            if schedule is not None:
                lead = utc(schedule.opens_at) - timedelta(minutes=10) - observed
                if timedelta(0) < lead <= MAX_HORIZON:
                    return schedule
        return None

    @property
    def trigger(self) -> datetime:
        return utc(self.schedule.opens_at) - timedelta(minutes=10)

    @property
    def end(self) -> datetime:
        return utc(self.schedule.opens_at) + timedelta(minutes=5)

    @property
    def result_name(self) -> str:
        return f"arch134-d1r5-{self.schedule.session_date}-{TARGET_HEAD}.jsonl"

    @property
    def arm_prefix(self) -> str:
        return f"arch134-d1r6-{self.schedule.session_date}-{TARGET_HEAD}-"

    @property
    def arm_name(self) -> str:
        return f"{self.arm_prefix}{self.source_head}-{self.source_tree}.jsonl"

    @property
    def task(self) -> dict[str, object]:
        return {
            "task_path": TASK_PATH,
            "trigger_count": 1,
            "trigger_type": 1,
            "start_boundary": self.trigger.isoformat(),
            "end_boundary": self.end.isoformat(),
            "trigger_enabled": True,
            "repetition_interval": "",
            "repetition_duration": "",
            "repetition_stop": False,
            "random_delay": "",
            "principal_sid": self.principal.sid,
            "logon_type": 3,
            "run_level": 0,
            "action_count": 1,
            "action_type": 0,
            "command": POWERSHELL,
            "arguments": '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'
            + str(WORKTREE / "scripts" / "arch134_d1r6_task_launcher.ps1")
            + '"',
            "working_directory": str(WORKTREE),
            "enabled": True,
            "wake_to_run": True,
            "start_when_available": False,
            "restart_count": 0,
            "restart_interval": "",
            "allow_demand_start": False,
            "run_only_if_idle": False,
            "run_only_if_network_available": False,
            "disallow_start_if_on_batteries": False,
            "stop_if_going_on_batteries": False,
            "hidden": False,
            "multiple_instances": 2,
            "execution_time_limit": "PT20M",
            "allow_hard_terminate": True,
            "idle_stop": False,
            "idle_restart": False,
        }

    @property
    def facts(self) -> dict[str, object]:
        schedule = self.schedule
        return {
            "source_head": self.source_head,
            "source_tree": self.source_tree,
            "target_head": TARGET_HEAD,
            "target_tree": TARGET_TREE,
            "target_session": schedule.session_date.isoformat(),
            "regular_open": utc(schedule.opens_at).isoformat(),
            "regular_close": utc(schedule.closes_at).isoformat(),
            "admission_open": self.end.isoformat(),
            "admission_close": (
                utc(schedule.closes_at) - timedelta(minutes=5)
            ).isoformat(),
            "observed_at": utc(self.observed_at).isoformat(),
            "principal_name": self.principal.name,
            "principal_sid": self.principal.sid,
            "task": self.task,
            "result_path": str(QUALIFICATION_PARENT / self.result_name),
        }


def plan_from_facts(facts: dict[str, object]) -> Plan:
    """Reconstruct every frozen fact rather than trusting journal values."""
    plan = Plan(
        facts["source_head"],
        facts["source_tree"],
        datetime.fromisoformat(facts["observed_at"]),
        Principal(facts["principal_name"], facts["principal_sid"]),
    )
    if canonical(plan.facts) != canonical(facts):
        raise ValueError("arm facts rejected")
    return plan


def serialize_arm(records: tuple[dict[str, object], ...]) -> bytes:
    """Accept only closed, immutable durable prefixes or one terminal journal."""
    if type(records) is not tuple or not 1 <= len(records) <= 8:
        raise ValueError("arm event count rejected")
    initial = None
    for index, record in enumerate(records):
        if type(record) is not dict or set(record) != {
            "schema",
            "event",
            "facts",
            "effects",
            "scheduler_task_create_calls",
            "classification",
        }:
            raise ValueError("arm fields rejected")
        if record["schema"] != SCHEMA or type(record["schema"]) is not str:
            raise ValueError("arm schema rejected")
        plan_from_facts(record["facts"])
        facts = canonical(record["facts"])
        if initial is not None and facts != initial:
            raise ValueError("arm facts changed")
        initial = facts
        if canonical(record["effects"]) != canonical(dict.fromkeys(ZERO_EFFECTS, 0)):
            raise ValueError("arm effect rejected")
        event = record["event"]
        if type(event) is not str:
            raise ValueError("arm event rejected")
        final = event == "FINAL"
        if final:
            if index != len(records) - 1 or index < 1:
                raise ValueError("arm final rejected")
            classification = record["classification"]
            valid = (
                classification == "ARMED"
                and index == 7
                or classification == "BLOCKED"
                and index <= 4
                or classification == "INDETERMINATE"
                and 5 <= index <= 7
            )
            if type(classification) is not str or not valid:
                raise ValueError("arm terminal rejected")
        elif (
            index >= len(EVENTS)
            or event != EVENTS[index]
            or record["classification"] is not None
        ):
            raise ValueError("arm order rejected")
        # An intent reserves the sole possible native create budget conservatively.
        count = int(index >= 4 and not (final and index == 4))
        if (
            type(record["scheduler_task_create_calls"]) is not int
            or record["scheduler_task_create_calls"] != count
        ):
            raise ValueError("arm create budget rejected")
    payload = b"".join(canonical(record) + b"\n" for record in records)
    if len(payload) > MAX_BYTES:
        raise ValueError("arm size rejected")
    return payload


def parse_arm(payload: bytes) -> tuple[dict[str, object], ...]:
    """Canonical bounded parsing; incomplete durable prefixes never grant launch."""
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
            raise ValueError
        records = tuple(
            json.loads(line, object_pairs_hook=_pairs)
            for line in payload.decode("utf-8").splitlines()
        )
        if serialize_arm(records) != payload:
            raise ValueError
        return records
    except Exception:
        raise ValueError("arm evidence rejected") from None


def checked_parent(parent: Path, roots: tuple[Path, ...]) -> None:
    """Existing real external parent only; no filesystem provisioning."""
    if not parent.is_absolute() or not parent.is_dir() or not roots:
        raise ValueError("qualification parent rejected")
    for path in (parent, *parent.parents):
        metadata = path.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("qualification link rejected")
    resolved = parent.resolve()
    if any(
        resolved.is_relative_to(root.resolve()) for root in roots
    ) or resolved.is_relative_to(Path(r"F:\AITradingBot").resolve()):
        raise ValueError("qualification location rejected")


def read_bounded(path: Path, maximum: int) -> bytes:
    """Read a regular non-linked journal with a hard byte bound."""
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & 0x400
        or metadata.st_size > maximum
    ):
        raise ValueError("evidence file rejected")
    with path.open("rb") as stream:
        result = stream.read(maximum + 1)
    if len(result) > maximum:
        raise ValueError("evidence file oversized")
    return result


class Runtime(Protocol):
    """Closed effect seams; production binding is private to the fixed host."""

    parent: Path

    def source(self, head: str, tree: str) -> tuple[Path, ...]: ...
    def target(self) -> tuple[Path, ...]: ...
    def clock(self) -> datetime: ...
    def principal(self) -> Principal: ...
    def observe(self) -> dict[str, object]: ...
    def create(self, plan: Plan) -> dict[str, object]: ...
    def child(self, plan: Plan) -> int: ...


def _absence(runtime: Runtime, plan: Plan, own: bool = False) -> None:
    if (runtime.parent / plan.result_name).exists() or (
        runtime.parent / plan.result_name
    ).is_symlink():
        raise ValueError("result consumed")
    for path in runtime.parent.glob(plan.arm_prefix + "*.jsonl"):
        if not own or path.name != plan.arm_name:
            raise ValueError("arm consumed")
    if runtime.observe() != {"status": "ABSENT"}:
        raise ValueError("task not absent")


def preflight(runtime: Runtime, head: str, tree: str) -> Plan:
    """Read-only admission; no reservation, creation, sleep or delegation."""
    roots = (*runtime.source(head, tree), *runtime.target())
    checked_parent(runtime.parent, roots)
    plan = Plan(head, tree, utc(runtime.clock()), runtime.principal())
    _absence(runtime, plan)
    return plan


class JournalError(ValueError):
    """Durable append failed; caller must stop without retrying IO."""


class _Journal:
    def __init__(self, output: BinaryIO, plan: Plan) -> None:
        self.output = output
        self.plan = plan
        self.records: tuple[dict[str, object], ...] = ()

    def append(self, event: str, classification: str | None = None) -> None:
        index = len(self.records)
        record = {
            "schema": SCHEMA,
            "event": event,
            "facts": self.plan.facts,
            "effects": dict.fromkeys(ZERO_EFFECTS, 0),
            "scheduler_task_create_calls": int(
                index >= 4 and not (event == "FINAL" and index == 4)
            ),
            "classification": classification,
        }
        records = (*self.records, record)
        payload = serialize_arm(records)
        before = len(serialize_arm(self.records)) if self.records else 0
        try:
            chunk = payload[before:]
            if self.output.write(chunk) != len(chunk):
                raise OSError
            self.output.flush()
            os.fsync(self.output.fileno())
        except Exception:
            raise JournalError("arm durability rejected") from None
        self.records = records


def task_matches(observation: dict[str, object], plan: Plan) -> bool:
    """Exact typed projection; diagnostics are bounded and never authoritative."""
    if type(observation) is not dict or set(observation) != {
        "status",
        "task",
        "state",
        "last_result",
    }:
        return False
    return (
        observation["status"] == "PRESENT"
        and canonical(observation["task"]) == canonical(plan.task)
        and type(observation["state"]) is int
        and 0 <= observation["state"] <= 4
        and type(observation["last_result"]) is int
        and 0 <= observation["last_result"] <= 0xFFFFFFFF
    )


def arm(runtime: Runtime, head: str, tree: str, interlock: str) -> str:
    """One fenced scheduler attempt, callable only with the complete interlock."""
    if type(interlock) is not str or interlock != ARM_INTERLOCK:
        return "BLOCKED"
    try:
        plan = preflight(runtime, head, tree)
        with (runtime.parent / plan.arm_name).open("xb") as output:
            journal = _Journal(output, plan)
            entered = False
            try:
                journal.append(EVENTS[0])
                runtime.source(head, tree)
                journal.append(EVENTS[1])
                runtime.target()
                journal.append(EVENTS[2])
                _absence(runtime, plan, own=True)
                journal.append(EVENTS[3])
                # Re-admit all mutable authority immediately before durable intent.
                runtime.source(head, tree)
                runtime.target()
                observed = utc(runtime.clock())
                if (
                    observed < utc(plan.observed_at)
                    or observed >= plan.trigger
                    or runtime.principal() != plan.principal
                ):
                    raise ValueError("final admission rejected")
                _absence(runtime, plan, own=True)
                journal.append(EVENTS[4])
                entered = True
                response = runtime.create(plan)
                if (
                    response
                    != {"disposition": "CALL_RETURNED", "registration_attempts": 1}
                    or type(response["registration_attempts"]) is not int
                ):
                    raise ValueError("registration uncertain")
                journal.append(EVENTS[5])
                first, second = runtime.observe(), runtime.observe()
                if (
                    not task_matches(first, plan)
                    or not task_matches(second, plan)
                    or canonical(first["task"]) != canonical(second["task"])
                ):
                    raise ValueError("confirmation uncertain")
                journal.append(EVENTS[6])
                journal.append("FINAL", "ARMED")
                return "ARMED"
            except JournalError:
                return "INDETERMINATE" if entered else "BLOCKED"
            except (Exception, KeyboardInterrupt):
                result = "INDETERMINATE" if entered else "BLOCKED"
                try:
                    journal.append("FINAL", result)
                except (Exception, KeyboardInterrupt):
                    pass
                return result
    except (Exception, KeyboardInterrupt):
        return "BLOCKED"


def load_armed(runtime: Runtime, head: str, tree: str) -> Plan:
    """Discover only the single journal bound to the current D1R6 source."""
    roots = runtime.source(head, tree)
    checked_parent(runtime.parent, roots)
    candidates = []
    for path in runtime.parent.glob(
        f"arch134-d1r6-*-{TARGET_HEAD}-{head}-{tree}.jsonl"
    ):
        candidates.append(path)
        if len(candidates) > 1:
            raise ValueError("ambiguous arm evidence")
    if len(candidates) != 1:
        raise ValueError("arm evidence absent")
    records = parse_arm(read_bounded(candidates[0], MAX_BYTES))
    if records[-1]["event"] != "FINAL" or records[-1]["classification"] != "ARMED":
        raise ValueError("arm not final")
    plan = plan_from_facts(records[0]["facts"])
    if (
        plan.source_head != head
        or plan.source_tree != tree
        or candidates[0].name != plan.arm_name
    ):
        raise ValueError("arm source mismatch")
    return plan


def launch(runtime: Runtime, head: str, tree: str) -> int:
    """Delegate once to the external accepted D1R5 host; no trading continuation."""
    plan = load_armed(runtime, head, tree)
    runtime.source(head, tree)
    runtime.target()
    if runtime.principal() != plan.principal:
        raise ValueError("launch principal rejected")
    result = runtime.parent / plan.result_name
    if result.exists() or result.is_symlink():
        raise ValueError("result consumed")
    # D1R5 may reject before reserving its result. Fence delegation independently.
    fence = runtime.parent / plan.arm_name.replace(".jsonl", "-launch.jsonl")
    payload = (
        canonical(
            {
                "schema": "arch134-d1r6-overnight-wake-launch/v1",
                "event": "D1R5_LAUNCH_INTENT",
                "facts": plan.facts,
                "d1r5_delegation_budget": 1,
                "effects": dict.fromkeys(ZERO_EFFECTS, 0),
            }
        )
        + b"\n"
    )
    with fence.open("xb") as output:
        if output.write(payload) != len(payload):
            raise ValueError("launch fence failed")
        output.flush()
        os.fsync(output.fileno())
    return runtime.child(plan)


def reconcile(runtime: Runtime, head: str, tree: str) -> dict[str, str]:
    """Read-only evidence assessment; scheduler observations cannot confer PASS."""
    try:
        plan = load_armed(runtime, head, tree)
    except Exception:
        return {
            "disposition": "ARM_EVIDENCE_INVALID",
            "evidence": "ARM_EVIDENCE_INVALID",
            "task": "UNAVAILABLE",
        }
    try:
        task = (
            "MATCH"
            if task_matches(runtime.observe(), plan)
            else "TASK_DRIFT_OR_MISSING"
        )
    except Exception:
        task = "TASK_DRIFT_OR_MISSING"
    try:
        payload = read_bounded(runtime.parent / plan.result_name, D1R5_MAX_BYTES)
    except FileNotFoundError:
        evidence = (
            "PENDING"
            if utc(runtime.clock()) <= plan.end + timedelta(minutes=20)
            else "NO_D1R5_EVIDENCE"
        )
    except Exception:
        evidence = "D1R5_INVALID"
    else:
        try:
            records = parse_wake_journal(payload)
            first, final = records[0], records[-1]
            if (
                first["source_head"],
                first["source_tree"],
                first["target_session"],
            ) != (TARGET_HEAD, TARGET_TREE, plan.schedule.session_date.isoformat()):
                raise ValueError
            evidence = "D1R5_INCOMPLETE"
            if final["event"] == "FINAL":
                evidence = (
                    "PASS"
                    if final["classification"] == "PASS"
                    else "D1R5_TERMINAL_FAILURE"
                )
        except Exception:
            evidence = "D1R5_INVALID"
    return {
        "disposition": evidence if task == "MATCH" else "TASK_DRIFT_OR_MISSING",
        "evidence": evidence,
        "task": task,
    }
