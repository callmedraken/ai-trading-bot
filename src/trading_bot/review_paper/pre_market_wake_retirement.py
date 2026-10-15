"""Exact consumed October 15 wake retirement; no creation or delegation authority."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import BinaryIO, Protocol

from trading_bot.review_paper import pre_market_wake_overnight as incident
from trading_bot.review_paper.pre_market_wake_qualification import (
    validate_source_identity,
)

SCHEMA = "arch134-d1r7-stale-wake-retirement/v1"
INTERLOCK = "AUTHORIZE_ARCH134_D1R7_ONE_STALE_WAKE_RETIREMENT"
WORKTREE = PureWindowsPath(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-stale-wake-retirement"
)
EVIDENCE_NAME = "arch134-d1r7-stale-wake-retirement-2026-10-15.jsonl"
EVIDENCE_GLOB = "arch134-d1r7-stale-wake-retirement-*"
LAST_RUN = "2026-10-15T06:20:00"
TASK_DELETE_BUDGET = 1
TASK_CREATE_BUDGET = 0
TASK_UPDATE_BUDGET = 0
TASK_RUN_BUDGET = 0
D1R5_EXECUTION_BUDGET = 0
D1_OPERATIONS = 0
D2_OPERATIONS = 0
LIVE_EFFECTS = 0
BUDGETS = {
    "TASK_DELETE_BUDGET": TASK_DELETE_BUDGET,
    "TASK_CREATE_BUDGET": TASK_CREATE_BUDGET,
    "TASK_UPDATE_BUDGET": TASK_UPDATE_BUDGET,
    "TASK_RUN_BUDGET": TASK_RUN_BUDGET,
    "D1R5_EXECUTION_BUDGET": D1R5_EXECUTION_BUDGET,
    "D1_OPERATIONS": D1_OPERATIONS,
    "D2_OPERATIONS": D2_OPERATIONS,
    "LIVE_EFFECTS": LIVE_EFFECTS,
}
EVENTS = (
    "RETIREMENT_RESERVED",
    "D1R7_SOURCE_ADMITTED",
    "D1R5_TARGET_ADMITTED",
    "CONSUMED_INCIDENT_ADMITTED",
    "STALE_TASK_CONFIRMED",
    "TASK_DELETE_INTENT",
    "TASK_DELETE_RETURNED",
    "TASK_ABSENCE_CONFIRMED",
)
MAX_BYTES = 131072


class Runtime(Protocol):
    """Only fixed source admission, observation and one exact delete seam."""

    parent: Path

    def source(self, head: str, tree: str) -> tuple[Path, ...]: ...
    def target(self) -> tuple[Path, ...]: ...
    def frozen(self) -> tuple[Path, ...]: ...
    def observe(self) -> dict[str, object]: ...
    def delete(self, plan: incident.Plan) -> dict[str, object]: ...


def present(path: Path) -> bool:
    """Include dangling links and nonregular collisions."""
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def read_evidence(path: Path) -> bytes:
    """Bounded regular single-link file, checked across open and read."""
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or getattr(before, "st_file_attributes", 0) & 0x400
        or not 0 < before.st_size <= MAX_BYTES
    ):
        raise ValueError("retirement file rejected")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (
            (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or getattr(opened, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("retirement file changed")
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if (
        len(payload) != before.st_size
        or len(payload) > MAX_BYTES
        or after.st_size != before.st_size
        or after.st_mtime_ns != before.st_mtime_ns
    ):
        raise ValueError("retirement read changed")
    return payload


@dataclass(frozen=True, slots=True)
class Admission:
    head: str
    tree: str
    plan: incident.Plan

    @property
    def facts(self) -> dict[str, object]:
        return {
            "source_head": self.head,
            "source_tree": self.tree,
            "incident_name": incident.RECOVERY_PREDECESSOR_ARM_NAME,
            "incident_bytes": incident.RECOVERY_PREDECESSOR_ARM_BYTES,
            "incident_sha256": incident.RECOVERY_PREDECESSOR_ARM_SHA256,
            "incident": self.plan.facts,
            "budgets": BUDGETS,
        }


def _common(runtime: Runtime, head: str, tree: str) -> Admission:
    validate_source_identity(head)
    validate_source_identity(tree)
    roots = (*runtime.source(head, tree), *runtime.target(), *runtime.frozen())
    incident.checked_parent(runtime.parent, roots)
    plan = incident.read_consumed_predecessor(
        runtime.parent / incident.RECOVERY_PREDECESSOR_ARM_NAME
    )
    for name in (plan.result_name, plan.arm_name.replace(".jsonl", "-launch.jsonl")):
        if present(runtime.parent / name):
            raise ValueError("incident delegated")
    if any(runtime.parent.glob(incident.RECOVERY_GLOB)):
        raise ValueError("recovery exists")
    # No competing same-session arm may acquire deletion authority.
    if any(
        p.name != plan.arm_name
        for p in runtime.parent.glob(plan.arm_prefix + "*.jsonl")
    ):
        raise ValueError("competing incident")
    return Admission(head, tree, plan)


def checked_observation(
    value: object, plan: incident.Plan, *, absent: bool = False
) -> None:
    """Exact R3 canonical task, principal and post-trigger state fingerprint."""
    if type(value) is not dict or set(value) != {"principal", "observation"}:
        raise ValueError("observation rejected")
    expected_principal = {"name": plan.principal.name, "sid": plan.principal.sid}
    if incident.canonical(value["principal"]) != incident.canonical(expected_principal):
        raise ValueError("principal drift")
    expected = (
        {"status": "ABSENT"}
        if absent
        else {
            "status": "PRESENT",
            "task": plan.task,
            "state": 3,
            "last_result": 2,
            "last_run": LAST_RUN,
            "next_run": None,
        }
    )
    if incident.canonical(value["observation"]) != incident.canonical(expected):
        raise ValueError("stale task drift")


def _admit(runtime: Runtime, head: str, tree: str, *, own: bool = False) -> Admission:
    admitted = _common(runtime, head, tree)
    candidates = tuple(runtime.parent.glob(EVIDENCE_GLOB))
    if any(p.name != EVIDENCE_NAME or not own for p in candidates):
        raise ValueError("retirement already reserved")
    checked_observation(runtime.observe(), admitted.plan)
    return admitted


def preflight(runtime: Runtime, head: str, tree: str) -> Admission:
    """Read only. No journal reservation or native mutation is reachable."""
    return _admit(runtime, head, tree)


def serialize(records: tuple[dict[str, object], ...]) -> bytes:
    """Validate complete canonical prefixes; absence alone never grants PASS."""
    if type(records) is not tuple or not 1 <= len(records) <= 9:
        raise ValueError("retirement count rejected")
    initial = None
    for index, record in enumerate(records):
        if type(record) is not dict or set(record) != {
            "schema",
            "event",
            "facts",
            "effects",
            "delete_budget_consumed",
            "deletion_attempts",
            "classification",
        }:
            raise ValueError("retirement fields rejected")
        facts = record["facts"]
        if type(facts) is not dict or set(facts) != {
            "source_head",
            "source_tree",
            "incident_name",
            "incident_bytes",
            "incident_sha256",
            "incident",
            "budgets",
        }:
            raise ValueError("retirement facts rejected")
        validate_source_identity(facts["source_head"])
        validate_source_identity(facts["source_tree"])
        plan = incident.plan_from_facts(facts["incident"])
        if (
            plan.source_head != incident.RECOVERY_PREDECESSOR_HEAD
            or plan.source_tree != incident.RECOVERY_PREDECESSOR_TREE
            or plan.arm_name != incident.RECOVERY_PREDECESSOR_ARM_NAME
            or incident.canonical(facts)
            != incident.canonical(
                Admission(facts["source_head"], facts["source_tree"], plan).facts
            )
        ):
            raise ValueError("retirement incident rejected")
        frozen = incident.canonical(facts)
        if initial is not None and frozen != initial:
            raise ValueError("retirement facts changed")
        initial = frozen
        if record["schema"] != SCHEMA or incident.canonical(
            record["effects"]
        ) != incident.canonical(dict.fromkeys(incident.ZERO_EFFECTS, 0)):
            raise ValueError("retirement authority rejected")
        final = record["event"] == "FINAL"
        classification = record["classification"]
        if final:
            if (
                index != len(records) - 1
                or index < 1
                or not (
                    classification == "RETIRED"
                    and index == 8
                    or classification == "BLOCKED"
                    and index <= 6
                    or classification == "INDETERMINATE"
                    and 6 <= index <= 8
                )
            ):
                raise ValueError("retirement final rejected")
        elif (
            index >= len(EVENTS)
            or record["event"] != EVENTS[index]
            or classification is not None
        ):
            raise ValueError("retirement order rejected")
        consumed = int(index >= 5 and not (final and index == 5))
        calls = (
            0
            if not consumed or classification == "BLOCKED"
            else 1
            if index >= 7 or record["event"] == "TASK_DELETE_RETURNED"
            else None
        )
        if (
            type(record["delete_budget_consumed"]) is not int
            or record["delete_budget_consumed"] != consumed
            or incident.canonical(record["deletion_attempts"])
            != incident.canonical(calls)
        ):
            raise ValueError("retirement budget rejected")
    payload = b"".join(incident.canonical(r) + b"\n" for r in records)
    if len(payload) > MAX_BYTES:
        raise ValueError("retirement oversized")
    return payload


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    output = {}
    for key, value in items:
        if key in output:
            raise ValueError("duplicate retirement field")
        output[key] = value
    return output


def parse(payload: bytes) -> tuple[dict[str, object], ...]:
    """Reject malformed, duplicated, noncanonical and partial byte records."""
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("retirement bytes rejected")
    records = tuple(
        json.loads(line, object_pairs_hook=_pairs) for line in payload.splitlines()
    )
    if serialize(records) != payload:
        raise ValueError("retirement serialization rejected")
    return records


class DurabilityError(ValueError):
    """Never append/retry after an ambiguous write, flush or fsync."""


class _Journal:
    def __init__(self, stream: BinaryIO, admission: Admission) -> None:
        self.stream = stream
        self.admission = admission
        self.records: tuple[dict[str, object], ...] = ()

    def append(self, event: str, classification: str | None = None) -> None:
        index = len(self.records)
        consumed = int(index >= 5 and not (event == "FINAL" and index == 5))
        record = {
            "schema": SCHEMA,
            "event": event,
            "facts": self.admission.facts,
            "effects": dict.fromkeys(incident.ZERO_EFFECTS, 0),
            "delete_budget_consumed": consumed,
            "deletion_attempts": (
                0
                if not consumed or classification == "BLOCKED"
                else 1
                if index >= 7 or event == "TASK_DELETE_RETURNED"
                else None
            ),
            "classification": classification,
        }
        records = (*self.records, record)
        payload = serialize(records)
        before = len(serialize(self.records)) if self.records else 0
        try:
            chunk = payload[before:]
            if self.stream.write(chunk) != len(chunk):
                raise OSError("short write")
            self.stream.flush()
            os.fsync(self.stream.fileno())
        except (Exception, KeyboardInterrupt):
            raise DurabilityError("retirement durability uncertain") from None
        self.records = records


def retire(runtime: Runtime, head: str, tree: str, interlock: str) -> str:
    """Reserve once, durably consume intent, delete once, confirm absence twice."""
    if type(interlock) is not str or interlock != INTERLOCK:
        return "BLOCKED"
    consumed = False
    try:
        admission = preflight(runtime, head, tree)
        with (runtime.parent / EVIDENCE_NAME).open("xb") as stream:
            journal = _Journal(stream, admission)
            try:
                for event in EVENTS[:5]:
                    if _admit(runtime, head, tree, own=True) != admission:
                        raise ValueError("admission drift")
                    journal.append(event)
                if _admit(runtime, head, tree, own=True) != admission:
                    raise ValueError("final admission drift")
                # Mark uncertainty BEFORE attempting the durable intent write.
                consumed = True
                journal.append("TASK_DELETE_INTENT")
                response = runtime.delete(admission.plan)
                if incident.canonical(response) == incident.canonical(
                    {
                        "disposition": "NOT_CALLED",
                        "deletion_attempts": 0,
                    }
                ):
                    journal.append("FINAL", "BLOCKED")
                    return "BLOCKED"
                if incident.canonical(response) != incident.canonical(
                    {
                        "disposition": "CALL_RETURNED",
                        "deletion_attempts": 1,
                    }
                ):
                    raise ValueError("delete uncertain")
                journal.append("TASK_DELETE_RETURNED")
                for _ in range(2):
                    checked_observation(runtime.observe(), admission.plan, absent=True)
                if _common(runtime, head, tree) != admission:
                    raise ValueError("post-delete authority drift")
                journal.append("TASK_ABSENCE_CONFIRMED")
                journal.append("FINAL", "RETIRED")
            except DurabilityError:
                return "INDETERMINATE" if consumed else "BLOCKED"
            except (Exception, KeyboardInterrupt):
                result = "INDETERMINATE" if consumed else "BLOCKED"
                try:
                    journal.append("FINAL", result)
                except (Exception, KeyboardInterrupt):
                    pass
                return result
        # Close failures after intent are also ambiguous. Independently reread.
        records = parse(read_evidence(runtime.parent / EVIDENCE_NAME))
        if records[-1]["classification"] != "RETIRED":
            raise ValueError("retirement finalization rejected")
        return "RETIRED"
    except (Exception, KeyboardInterrupt):
        return "INDETERMINATE" if consumed else "BLOCKED"


def reconcile(runtime: Runtime, head: str, tree: str) -> dict[str, str]:
    """Read only; indeterminate evidence never becomes automatic retry authority."""
    try:
        admission = _common(runtime, head, tree)
        if tuple(runtime.parent.glob(EVIDENCE_GLOB)) != (
            runtime.parent / EVIDENCE_NAME,
        ):
            raise ValueError("retirement evidence ambiguous")
        records = parse(read_evidence(runtime.parent / EVIDENCE_NAME))
        if incident.canonical(records[0]["facts"]) != incident.canonical(
            admission.facts
        ):
            raise ValueError("retirement source drift")
        checked_observation(runtime.observe(), admission.plan, absent=True)
        if (
            records[-1]["event"] == "FINAL"
            and records[-1]["classification"] == "RETIRED"
            and records[-1]["deletion_attempts"] == 1
        ):
            return {"status": "PASS", "classification": "RETIRED"}
        return {"status": "STOP", "classification": "INDETERMINATE"}
    except (Exception, KeyboardInterrupt):
        return {"status": "STOP", "classification": "UNPROVEN"}
