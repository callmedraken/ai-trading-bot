"""One immutable published session; automatic reconciliation never retries entry."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from trading_bot.review_paper import d1_session_authorization as prerequisite
from trading_bot.review_paper import d1_session_execution_store as execution_store
from trading_bot.review_paper import d1_session_supervisor_store as store
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)

INTERLOCK = "AUTHORIZE_ARCH134_D1R9_ONE_RECONCILING_SYNTHETIC_PAPER_SESSION"
MAX_WAIT_SECONDS = 60
NY = ZoneInfo("America/New_York")


class Runtime(Protocol):
    parent: Path

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


def select_target(observed: datetime) -> date:
    """Only the frozen NYSE authority can derive the authorization's target."""
    now = store.utc(observed)
    candidate = now.astimezone(NY).date()
    authority = NYSEPublishedRegularSessionAuthority()
    while True:
        schedule = authority.schedule_for(candidate)
        if schedule is not None and now < store.utc(schedule.closes_at) - timedelta(
            minutes=5
        ):
            return candidate
        candidate += timedelta(days=1)


def validate_binding(facts: dict) -> date:
    store.validate_facts(facts)
    target = select_target(datetime.fromisoformat(facts["authorized_at"]))
    if target.isoformat() != facts["target_session"]:
        raise ValueError("immutable derived target mismatch")
    return target


def make_facts(source: dict, at: datetime, binding: dict) -> dict:
    facts = dict(
        source=source,
        d1r7=store.D1R7,
        d1r8=store.D1R8,
        target_session=select_target(at).isoformat(),
        authorized_at=store.utc(at).isoformat(),
        symbol="SPY",
        runtime=binding,
    )
    validate_binding(facts)
    return facts


def guard(runtime: Runtime, journal: store.Journal) -> datetime:
    """Read-only re-admission; slow checks precede the final authoritative clock."""
    validate_binding(journal.facts)
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


def authorize(runtime: Runtime, source: dict, interlock: str) -> store.Journal:
    if type(interlock) is not str or interlock != INTERLOCK:
        raise ValueError("one-session interactive authority required")
    facts = make_facts(source, runtime.clock(), runtime.runtime_binding())
    runtime.admit(facts)
    runtime.predecessors()
    runtime.admit_runtime(facts["runtime"])
    if store.find_active(runtime.parent) is not None:
        raise ValueError("existing active authority must reconcile")
    journal = store.Journal.reserve(runtime.parent, facts)
    try:
        journal.append("SOURCES_ADMITTED", guard(runtime, journal))
        journal.append("TARGET_BOUND", guard(runtime, journal))
        # Maintenance precedes SUPERVISOR_READY. Resume never installs/updates tasks.
        if not runtime.scheduler_matches():
            journal.append("SCHEDULER_CREATE_INTENT", guard(runtime, journal))
            runtime.scheduler_create()
            if not runtime.scheduler_matches():
                raise ValueError("scheduler acknowledgement mismatch")
            journal.append("SCHEDULER_CREATE_ACK", guard(runtime, journal))
        journal.append("SUPERVISOR_READY", guard(runtime, journal))
        journal.append("SCHEDULER_RUN_INTENT", guard(runtime, journal))
        runtime.scheduler_run()
        journal.append("SCHEDULER_RUN_ACK", guard(runtime, journal))
    except Exception:
        status = (
            "INDETERMINATE"
            if journal.state in {"SCHEDULER_CREATE_INTENT", "SCHEDULER_RUN_INTENT"}
            else "BLOCKED"
        )
        finish(runtime, journal, status)
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
        if journal.state in (
            *store.INITIAL,
            "SCHEDULER_CREATE_INTENT",
            "SCHEDULER_CREATE_ACK",
            "SUPERVISOR_READY",
            "SCHEDULER_RUN_INTENT",
        ):
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
            "SCHEDULER_RUN_ACK",
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
