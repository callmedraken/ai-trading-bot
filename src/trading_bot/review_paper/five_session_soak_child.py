"""F1 durable-grant child; D1R9-equivalent timing/proof/one-attempt reducer."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from trading_bot.review_paper import d1_session_authorization as prerequisite
from trading_bot.review_paper import d1_session_execution_store as execution_store
from trading_bot.review_paper import five_session_soak_store as store
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)

MAX_WAIT_SECONDS = 60
NY = ZoneInfo("America/New_York")


class Runtime(Protocol):
    parent: Path

    def admit_grant(self, journal: store.Journal) -> None: ...
    def clock(self) -> datetime: ...
    def admit(self, facts: dict) -> tuple[Path, ...]: ...
    def predecessors(self) -> None: ...
    def runtime_binding(self) -> dict: ...
    def admit_runtime(self, binding: dict, *, entered: bool = False) -> None: ...
    def scheduler_matches(self) -> bool: ...
    def scheduler_create(self) -> None: ...
    def scheduler_run(self) -> None: ...
    def child_idle(self) -> bool: ...
    def child(self, kind: str) -> None: ...
    def wait(self, seconds: int) -> None: ...


def validate_binding(facts: dict) -> date:
    store.validate_facts(facts)
    if facts["kind"] != "child":
        raise ValueError("F1 child grant required")
    target = date.fromisoformat(facts["target_session"])
    if NYSEPublishedRegularSessionAuthority().schedule_for(target) is None:
        raise ValueError("published target required")
    return target


def guard(runtime: Runtime, journal: store.Journal) -> datetime:
    """Read-only re-admission; slow checks precede the final authoritative clock."""
    validate_binding(journal.facts)
    runtime.admit_grant(journal)
    if store.read(journal.path, store.MAX_BYTES, journal.identity) != journal.payload:
        raise ValueError("authorization changed")
    roots = runtime.admit(journal.facts)
    store.checked_path(runtime.parent)
    if (
        not roots
        or not runtime.parent.is_dir()
        or any(
            runtime.parent.resolve().is_relative_to(root.resolve()) for root in roots
        )
        or runtime.parent.resolve().is_relative_to(Path(r"F:\AITradingBot").resolve())
    ):
        raise ValueError("existing external qualification parent required")
    runtime.predecessors()
    runtime.admit_runtime(
        journal.facts["runtime"],
        entered=bool(journal.rows[-1]["effects"]["d1r8_attempts"]),
    )
    now = store.utc(runtime.clock())
    if now < max(
        journal.last_clock,
        store.utc(datetime.fromisoformat(journal.rows[-1]["observed_at"])),
    ):
        raise ValueError("authoritative clock moved backward")
    journal.last_clock = now
    return now


def d1r7_path(parent: Path, target: date) -> Path:
    # The producer's slot is independent of observation instant; use its public Plan.
    plan = prerequisite.Plan(
        prerequisite.Source(**store.D1R7),
        prerequisite.Source(**store.D1R8),
        datetime.combine(target, time(12), UTC),
    )
    return parent / plan.name


def proof_d1r7(runtime: Runtime, target: date) -> tuple[dict, dict]:
    path = d1r7_path(runtime.parent, target)
    payload = prerequisite.read_evidence(path, prerequisite.MAX_BYTES)
    rows = prerequisite.parse_authorization(payload)
    facts = rows[0]["facts"]
    if (
        tuple(row["event"] for row in rows) != prerequisite.EVENTS
        or rows[-1]["classification"] != prerequisite.READY
        or facts["target_session"] != target.isoformat()
        or facts["source"] != prerequisite.Source(**store.D1R7).facts()
        or facts["intended_d1"] != prerequisite.Source(**store.D1R8).facts()
        or facts["reservation_basename"] != path.name
        or prerequisite.canonical(facts["d1_policy"])
        != prerequisite.canonical(prerequisite.fixed_policy())
    ):
        raise ValueError("complete exact D1R7 proof required")
    runtime.predecessors()
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}, facts


def proof_d1r8(
    runtime: Runtime, target: date, publication: dict, facts: dict
) -> tuple[str, dict]:
    path = runtime.parent / execution_store.reservation_name(target.isoformat())
    payload = prerequisite.read_evidence(path, execution_store.MAX_BYTES)
    rows = execution_store.parse_journal(payload)
    expected = dict(
        prerequisite=facts,
        d1r7_bytes=publication["bytes"],
        d1r7_sha256=publication["sha256"],
        publication_confirmed=True,
    )
    if prerequisite.canonical(rows[0]["facts"]) != prerequisite.canonical(expected):
        raise ValueError("D1R8 terminal binding mismatch")
    status = rows[-1]["classification"]
    if status == "SESSION_EXPIRED":
        status = "SESSION_MISSED"
    if status not in store.TERMINALS:
        raise ValueError("closed D1R8 terminal required")
    return status, {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def finish(
    runtime: Runtime, journal: store.Journal, status: str, proof: dict | None = None
) -> str:
    # A clock regression cannot rewrite history; record the safe terminal at the
    # last durable instant. It can never grant child-entry or session authority.
    at = max(
        store.utc(runtime.clock()),
        journal.last_clock,
        store.utc(datetime.fromisoformat(journal.rows[-1]["observed_at"])),
    )
    journal.append("FINAL", at, classification=status, proof=proof)
    return status


def accept_grant(
    runtime: Runtime, parent: store.Journal, ordinal: int
) -> store.Journal:
    """Exclusive child reservation, only after a durable parent grant intent.

    A crash before this reservation stays consumed at the parent; resume never
    calls this entry point. No historical human interlock is accepted.
    """
    facts = store.grant_facts(parent, ordinal, runtime.runtime_binding())
    runtime.admit(facts)
    runtime.predecessors()
    runtime.admit_runtime(facts["runtime"])
    observed = store.utc(runtime.clock())
    if observed < max(
        parent.last_clock, datetime.fromisoformat(parent.rows[-1]["observed_at"])
    ):
        raise ValueError("clock regressed before child reservation")
    journal = store.Journal.reserve(runtime.parent, facts, observed_at=observed)
    for event in ("SOURCES_ADMITTED", "TARGET_BOUND", "CHILD_READY"):
        journal.append(event, guard(runtime, journal))
    return journal


def step(runtime: Runtime, journal: store.Journal) -> str:
    """Recompute once; callers hold the process-lifetime supervisor lock."""
    if journal.state == "FINAL":
        return journal.rows[-1]["classification"]
    try:
        now = guard(runtime, journal)
        target = validate_binding(journal.facts)
        if not runtime.child_idle():
            return finish(runtime, journal, "INDETERMINATE")
        if journal.state in store.INITIAL:
            return finish(runtime, journal, "INDETERMINATE")
        # A durable intent is consumed even if the crash preceded process entry.
        # Only a complete independently accepted artifact may reconcile it.
        if journal.state == "D1R7_DELEGATION_INTENT":
            publication, _ = proof_d1r7(runtime, target)
            journal.append("D1R7_READY", guard(runtime, journal), proof=publication)
        if journal.state == "D1R8_DELEGATION_INTENT":
            publication, facts = proof_d1r7(runtime, target)
            saved = next(r["proof"] for r in journal.rows if r["event"] == "D1R7_READY")
            if publication != saved:
                raise ValueError("publication changed")
            result, proof = proof_d1r8(runtime, target, publication, facts)
            return finish(
                runtime,
                journal,
                result,
                proof
                if result
                in {
                    "NO_SIGNAL",
                    "RISK_REJECTED",
                    "PAPER_EXECUTED",
                }
                else None,
            )
        now = guard(runtime, journal)
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(target)
        close = store.utc(schedule.closes_at) - timedelta(minutes=5)
        if now >= close:
            return finish(runtime, journal, "SESSION_MISSED")
        if journal.state in {
            "CHILD_READY",
            "NEXT_SESSION_WAIT",
            "PREMARKET_WAIT",
        }:
            if now.astimezone(NY).date() < target:
                state = "NEXT_SESSION_WAIT"
            elif now < store.utc(schedule.opens_at) - timedelta(minutes=10):
                state = "PREMARKET_WAIT"
            else:
                state = "D1R7_DELEGATION_INTENT"
            if state != journal.state:
                if state == "D1R7_DELEGATION_INTENT":
                    if d1r7_path(runtime.parent, target).exists():
                        return finish(runtime, journal, "BLOCKED")
                    now = guard(runtime, journal)
                    if now >= close or now.astimezone(NY).date() != target:
                        return finish(runtime, journal, "SESSION_MISSED")
                journal.append(state, now)
                if state == "D1R7_DELEGATION_INTENT":
                    runtime.child("d1r7")
                    return step(runtime, journal)
            return state
        if journal.state in {"D1R7_READY", "D1R8_WAIT"}:
            publication, _ = proof_d1r7(runtime, target)
            saved = next(r["proof"] for r in journal.rows if r["event"] == "D1R7_READY")
            if publication != saved:
                raise ValueError("immutable D1R7 proof changed")
            now = guard(runtime, journal)
            if now >= close:
                return finish(runtime, journal, "SESSION_MISSED")
            if now < store.utc(schedule.opens_at) + timedelta(minutes=5):
                if journal.state != "D1R8_WAIT":
                    journal.append("D1R8_WAIT", now)
                return "D1R8_WAIT"
            if (
                runtime.parent / execution_store.reservation_name(target.isoformat())
            ).exists():
                return finish(runtime, journal, "BLOCKED")
            journal.append("D1R8_DELEGATION_INTENT", now)
            runtime.child("d1r8")
            return step(runtime, journal)
        raise ValueError("closed supervisor state required")
    except Exception:
        status = (
            "INDETERMINATE"
            if journal.state
            in {
                "D1R7_DELEGATION_INTENT",
                "D1R8_DELEGATION_INTENT",
            }
            else "BLOCKED"
        )
        return finish(runtime, journal, status)


def supervise(runtime: Runtime, journal: store.Journal) -> str:
    while True:
        result = step(runtime, journal)
        if journal.state == "FINAL":
            return result
        if result not in store.WAIT_STATES:
            raise ValueError("wait state required")
        runtime.wait(MAX_WAIT_SECONDS)
