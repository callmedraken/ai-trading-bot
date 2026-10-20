"""Exactly five frozen published sessions under one durable F1 parent authority."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from trading_bot.review_paper import d1_session_execution_store as execution_store
from trading_bot.review_paper import five_session_soak_child as child
from trading_bot.review_paper import five_session_soak_store as store
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)

INTERLOCK = "AUTHORIZE_ARCH134_F1_FIVE_SESSION_LIVE_DATA_SYNTHETIC_PAPER_SOAK"
MAX_WAIT_SECONDS = 60
NY = ZoneInfo("America/New_York")


def select_window(observed: datetime) -> list[str]:
    now = store.utc(observed)
    target = now.astimezone(NY).date()
    authority = NYSEPublishedRegularSessionAuthority()
    result = []
    while len(result) < 5:
        schedule = authority.schedule_for(target)
        if schedule is not None and now < store.utc(schedule.closes_at) - timedelta(
            minutes=5
        ):
            result.append(target.isoformat())
        target += timedelta(days=1)
    return result


def validate_binding(facts: dict) -> None:
    store.validate_facts(facts)
    if (
        facts["kind"] != "parent"
        or select_window(datetime.fromisoformat(facts["authorized_at"]))
        != facts["targets"]
    ):
        raise ValueError("immutable published five-session window rejected")


def make_facts(source: dict, at: datetime, binding: dict) -> dict:
    targets = select_window(at)
    facts = dict(
        source=source,
        d1r7=store.D1R7,
        d1r8=store.D1R8,
        semantic_predecessor=store.D1R9_PREDECESSOR,
        symbol="SPY",
        targets=targets,
        contracts=[store.contract(t) for t in targets],
        policy=store.POLICY,
        scheduler=store.SCHEDULER,
        ceilings=store.CEILINGS,
        runtime=binding,
        authorized_at=store.utc(at).isoformat(),
        kind="parent",
    )
    validate_binding(facts)
    return facts


def children(parent: store.Journal) -> tuple[store.Journal, ...]:
    paths = tuple(parent.path.parent.glob("arch134-f1-child-*.jsonl"))
    if len(paths) > 5:
        raise ValueError("at most five child slots required")
    found = []
    ordinals = set()
    for path in paths:
        journal = store.Journal.load(path)
        ordinal = journal.facts["ordinal"]
        if ordinal in ordinals:
            raise ValueError("duplicate child grant")
        ordinals.add(ordinal)
        verify_child(parent, journal)
        found.append(journal)
    return tuple(sorted(found, key=lambda j: j.facts["ordinal"]))


def verify_child(parent: store.Journal, journal: store.Journal) -> None:
    """Bind a child to the exact immutable grant prefix, including after closure."""
    ordinal = journal.facts["ordinal"]
    event = f"SESSION_{ordinal}_GRANT_INTENT"
    index = next(i for i, r in enumerate(parent.rows) if r["event"] == event)
    payload = b"".join(store.canonical(r) + b"\n" for r in parent.rows[: index + 1])
    prefix = store.Journal(parent.path, payload, parent.identity)
    if datetime.fromisoformat(journal.rows[0]["observed_at"]) < datetime.fromisoformat(
        prefix.rows[-1]["observed_at"]
    ):
        raise ValueError("child reservation precedes grant")
    expected = store.grant_facts(prefix, ordinal, journal.facts["runtime"])
    if store.canonical(expected) != store.canonical(journal.facts):
        raise ValueError("immutable F1 child provenance changed")
    for key in ("paper", "sessions", "python"):
        fields = (
            ("device", "inode")
            if key != "python"
            else ("device", "inode", "bytes", "sha256")
        )
        if any(
            parent.facts["runtime"][key][f] != journal.facts["runtime"][key][f]
            for f in fields
        ):
            raise ValueError("child runtime identity changed")


def guard(runtime: child.Runtime, parent: store.Journal) -> datetime:
    validate_binding(parent.facts)
    if store.read(parent.path, store.MAX_BYTES, parent.identity) != parent.payload:
        raise ValueError("parent authority changed")
    roots = runtime.admit(parent.facts)
    store.checked_path(runtime.parent)
    if (
        not roots
        or not runtime.parent.is_dir()
        or any(runtime.parent.resolve().is_relative_to(r.resolve()) for r in roots)
        or runtime.parent.resolve().is_relative_to(Path(r"F:\AITradingBot").resolve())
    ):
        raise ValueError("existing external qualification parent required")
    runtime.predecessors()
    records = children(parent)
    by_ordinal = {j.facts["ordinal"]: j for j in records}
    for row in parent.rows:
        if row["event"].startswith("SESSION_") and row["event"].endswith("_FINAL"):
            saved = row["proof"]
            journal = by_ordinal.get(saved["ordinal"])
            if journal is None or reconcile_child(runtime, parent, journal) != saved:
                raise ValueError("previous child reconciliation drift")
    entered = any(j.rows[-1]["effects"]["d1r8_attempts"] for j in records)
    runtime.admit_runtime(parent.facts["runtime"], entered=entered)
    now = store.utc(runtime.clock())
    latest = max(
        [
            parent.last_clock,
            datetime.fromisoformat(parent.rows[-1]["observed_at"]),
            *(datetime.fromisoformat(j.rows[-1]["observed_at"]) for j in records),
        ]
    )
    if now < latest:
        raise ValueError("authoritative clock moved backward")
    parent.last_clock = now
    return now


def finish(
    runtime: child.Runtime,
    parent: store.Journal,
    status: str,
    proof: dict | None = None,
) -> str:
    at = max(
        store.utc(runtime.clock()),
        parent.last_clock,
        datetime.fromisoformat(parent.rows[-1]["observed_at"]),
    )
    parent.append("FINAL", at, classification=status, proof=proof)
    return status


def authorize(runtime: child.Runtime, source: dict, interlock: str) -> store.Journal:
    if type(interlock) is not str or interlock != INTERLOCK:
        raise ValueError("interactive five-session F1 authority required")
    facts = make_facts(source, runtime.clock(), runtime.runtime_binding())
    runtime.admit(facts)
    runtime.predecessors()
    runtime.admit_runtime(facts["runtime"])
    # The fixed series slot is irrevocable even after FINAL, malformed bytes,
    # or a crash before first write. No scan-for-a-new-date authority exists.
    parent = store.Journal.reserve(runtime.parent, facts)
    try:
        parent.append("SOURCES_ADMITTED", guard(runtime, parent))
        parent.append("WINDOW_BOUND", guard(runtime, parent))
        if not runtime.scheduler_matches():
            parent.append("SCHEDULER_CREATE_INTENT", guard(runtime, parent))
            runtime.scheduler_create()
            if not runtime.scheduler_matches():
                raise ValueError("scheduler acknowledgement mismatch")
            parent.append("SCHEDULER_CREATE_ACK", guard(runtime, parent))
        parent.append("SOAK_READY", guard(runtime, parent))
        parent.append("SCHEDULER_RUN_INTENT", guard(runtime, parent))
        runtime.scheduler_run()
        parent.append("SCHEDULER_RUN_ACK", guard(runtime, parent))
    except Exception:
        finish(
            runtime,
            parent,
            "INDETERMINATE"
            if parent.state in {"SCHEDULER_CREATE_INTENT", "SCHEDULER_RUN_INTENT"}
            else "BLOCKED",
        )
    return parent


def reconcile_child(
    runtime: child.Runtime, parent: store.Journal, journal: store.Journal
) -> dict:
    # Independent bounded re-read, never the child's in-memory success return.
    journal = store.Journal.load(journal.path)
    verify_child(parent, journal)
    if journal.state != "FINAL":
        raise ValueError("closed child required")
    status = journal.rows[-1]["classification"]
    effects = journal.rows[-1]["effects"]
    target = date.fromisoformat(journal.facts["target_session"])
    p7 = p8 = None
    counts = dict.fromkeys(store.D1R8_BUDGETS, 0)
    if any(r["event"] == "D1R7_READY" for r in journal.rows):
        p7, facts = child.proof_d1r7(runtime, target)
        saved = next(r["proof"] for r in journal.rows if r["event"] == "D1R7_READY")
        if p7 != saved or facts["strategy_contract"] != store.contract(
            target.isoformat()
        ):
            raise ValueError("D1R7 contract/proof drift")
    if status in store.PROGRESS:
        actual, p8 = child.proof_d1r8(runtime, target, p7, facts)
        if actual != status or p8 != journal.rows[-1]["proof"]:
            raise ValueError("D1R8 result/proof drift")
        payload = store.read(
            runtime.parent / execution_store.reservation_name(target.isoformat()),
            execution_store.MAX_BYTES,
        )
        rows = execution_store.parse_journal(payload)
        if hashlib.sha256(payload).hexdigest() != p8["sha256"]:
            raise ValueError("D1R8 reread drift")
        counts = rows[-1]["effects"]
    elif effects["d1r8_attempts"]:
        # Partial/ambiguous provider/paper evidence never gets invented counters.
        # It halts without a positive end-of-window summary.
        raise ValueError("ambiguous D1R8 effect accounting requires review")
    result = dict(
        ordinal=journal.facts["ordinal"],
        target_session=target.isoformat(),
        child_id=journal.domain_id,
        child_journal=dict(
            bytes=len(journal.payload),
            sha256=hashlib.sha256(journal.payload).hexdigest(),
        ),
        grant_prefix=journal.facts["parent_prefix"],
        classification=status,
        d1r7=p7,
        d1r8=p8,
        effects=effects,
        d1r8_effects=counts,
        contract=store.contract(target.isoformat()),
    )
    store.summary(result, parent.facts, journal.facts["ordinal"])
    return result


def reconcile_window(runtime: child.Runtime, parent: store.Journal) -> dict:
    guard(runtime, parent)
    if not runtime.child_idle() or not runtime.scheduler_matches():
        raise ValueError("scheduler/child reconciliation rejected")
    records = children(parent)
    if tuple(j.facts["ordinal"] for j in records) != (1, 2, 3, 4, 5):
        raise ValueError("five exact ordered child journals required")
    summaries = [reconcile_child(runtime, parent, j) for j in records]
    saved = [
        r["proof"]
        for r in parent.rows
        if r["event"].startswith("SESSION_") and r["event"].endswith("_FINAL")
    ]
    if summaries != saved or any(
        s["classification"] not in store.PROGRESS for s in summaries
    ):
        raise ValueError("end-of-window independent reconciliation mismatch")
    guard(runtime, parent)
    return dict(
        children=summaries,
        scheduler="MATCH",
        parent_prefix=dict(
            bytes=len(parent.payload), sha256=hashlib.sha256(parent.payload).hexdigest()
        ),
    )


def step(runtime: child.Runtime, parent: store.Journal) -> str:
    if parent.state == "FINAL":
        # Still verify the durable bytes on duplicate entry, with zero effects.
        if store.read(parent.path, store.MAX_BYTES, parent.identity) != parent.payload:
            raise ValueError("closed parent changed")
        return parent.rows[-1]["classification"]
    try:
        guard(runtime, parent)
        if not runtime.child_idle():
            return finish(runtime, parent, "INDETERMINATE")
        finals = [
            r
            for r in parent.rows
            if r["event"].startswith("SESSION_") and r["event"].endswith("_FINAL")
        ]
        if finals and finals[-1]["classification"] not in store.PROGRESS:
            return finish(runtime, parent, finals[-1]["classification"])
        if len(finals) == 5:
            return finish(
                runtime, parent, "COMPLETED", reconcile_window(runtime, parent)
            )
        ordinal = len(finals) + 1
        if parent.state in {"SCHEDULER_RUN_ACK", f"SESSION_{ordinal - 1}_FINAL"}:
            now = guard(runtime, parent)
            # Freeze/consume one child grant before entering its exclusive slot.
            parent.append(f"SESSION_{ordinal}_GRANT_INTENT", now)
            child.accept_grant(runtime, parent, ordinal)
        if parent.state != f"SESSION_{ordinal}_GRANT_INTENT":
            return finish(runtime, parent, "INDETERMINATE")
        records = children(parent)
        active = [j for j in records if j.facts["ordinal"] == ordinal]
        if len(active) != 1:
            # No replay of an interrupted grant reservation.
            return finish(runtime, parent, "INDETERMINATE")
        journal = active[0]
        runtime.admit_grant(journal)
        result = child.step(runtime, journal)
        if journal.state != "FINAL":
            return result
        summary = reconcile_child(runtime, parent, journal)
        parent.append(
            f"SESSION_{ordinal}_FINAL",
            guard(runtime, parent),
            classification=result,
            proof=summary,
        )
        if result not in store.PROGRESS:
            return finish(runtime, parent, result)
        if ordinal == 5:
            return finish(
                runtime, parent, "COMPLETED", reconcile_window(runtime, parent)
            )
        # The next target is frozen; it starts on the next controller iteration.
        return "NEXT_SESSION_WAIT"
    except Exception:
        # A durable grant/maintenance intent is consumed, never repeated.
        status = "INDETERMINATE" if parent.state.endswith("_INTENT") else "BLOCKED"
        return finish(runtime, parent, status)


def supervise(runtime: child.Runtime, parent: store.Journal) -> str:
    while True:
        result = step(runtime, parent)
        if parent.state == "FINAL":
            return result
        if result not in store.WAIT_STATES:
            raise ValueError("bounded wait state required")
        runtime.wait(MAX_WAIT_SECONDS)
