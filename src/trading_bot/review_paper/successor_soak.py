"""Source-only two-session manual-start controller with injected effect seams.

No real provider, credentials, paper engine, launcher, native production store
or operational checkpoint is wired here. Interrupted evidence is consumed;
reopening it is read-only. There is no retry/resume entry point.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from trading_bot.review_paper.successor_soak_admission import (
    ManualAdmission,
    ManualStartBoundary,
)
from trading_bot.review_paper.successor_soak_contract import (
    EVIDENCE_SCHEMA,
    PARENT_NAME,
    PROGRESSING,
    SESSION_NAMES,
    SESSIONS,
    STORE_IDENTITY,
    QuoteDisposition,
    SessionTerminal,
    SuccessorLineage,
    digest,
    validate_counters,
    zero_counters,
)
from trading_bot.review_paper.successor_soak_store import (
    Replay,
    SuccessorEvidenceError,
    SuccessorJournal,
    SuccessorStorage,
    effect_record,
    prerequisite_proof,
    session_counters,
)
from trading_bot.supervised_release.runtime_host_composition import (
    SuccessorExternalEffectAdapter,
)
from trading_bot.supervised_release.runtime_isolation import (
    EffectOperation,
    EffectRecord,
    EffectStatus,
    InstalledRuntimeMaterial,
)


@dataclass(frozen=True, slots=True)
class SeriesSnapshot:
    parent: Replay
    children: tuple[Replay, ...]
    terminal: str | None
    counters: dict[str, int]


def snapshot(storage: SuccessorStorage, lineage: SuccessorLineage) -> SeriesSnapshot:
    """Read-only whole-series reconciliation; no lock/repair/effect authority."""
    parent = SuccessorJournal(storage, lineage).read()
    children = []
    counters = zero_counters()
    counters["parent_creations"] = 1
    for ordinal, name in enumerate(SESSION_NAMES, 1):
        child_data = storage.read(name)
        grants = [
            r
            for r in parent.rows
            if r["event"] == f"SESSION_{ordinal:02d}_GRANT_INTENT"
        ]
        finals = [
            r for r in parent.rows if r["event"] == f"SESSION_{ordinal:02d}_FINAL"
        ]
        if child_data is None:
            if grants or finals:
                raise SuccessorEvidenceError("parent references missing child")
            continue
        child = SuccessorJournal(storage, lineage, ordinal).read()
        if len(grants) != 1:
            raise SuccessorEvidenceError(
                "orphan or duplicate child reservation is consumed"
            )
        grant_index = parent.rows.index(grants[0])
        prefix = b"\n".join(parent.payload.split(b"\n")[: grant_index + 1]) + b"\n"
        if child.header["grant_prefix"] != digest(prefix):
            raise SuccessorEvidenceError("child grant-prefix binding mismatch")
        if ordinal == 2 and (
            not children
            or children[0].rows[-1]["event"] != "SESSION_FINAL"
            or SessionTerminal(children[0].rows[-1]["data"]["terminal"])
            not in PROGRESSING
        ):
            raise SuccessorEvidenceError(
                "session two requires benign terminal session one"
            )
        if children and tuple(
            child.header["process"][k] for k in ("pid", "birth")
        ) == tuple(children[0].header["process"][k] for k in ("pid", "birth")):
            raise SuccessorEvidenceError("fresh second manual admission required")
        child_counts = session_counters(child.rows)
        for key, value in child_counts.items():
            counters[key] += value
        if finals:
            if child.rows[-1]["event"] != "SESSION_FINAL" or finals[0]["data"] != {
                "child_sha256": child.sha256,
                "terminal": child.rows[-1]["data"]["terminal"],
                "counters": child_counts,
            }:
                raise SuccessorEvidenceError(
                    "parent/child terminal reconciliation mismatch"
                )
        children.append(child)
    validate_counters(counters, session=False)
    last = parent.rows[-1]
    terminal = (
        last["event"]
        if last["event"] in {"SERIES_COMPLETED", "SERIES_HALTED"}
        else None
    )
    if terminal:
        if not children or any(
            c.rows[-1]["event"] != "SESSION_FINAL" for c in children
        ):
            raise SuccessorEvidenceError(
                "parent terminal requires closed child evidence"
            )
        terminals = [child.rows[-1]["data"]["terminal"] for child in children]
        expected = (
            "SERIES_COMPLETED"
            if len(children) == 2
            and all(SessionTerminal(t) in PROGRESSING for t in terminals)
            else "SERIES_HALTED"
        )
        # Benign session one cannot halt or complete the parent early.
        if len(children) == 1 and SessionTerminal(terminals[0]) in PROGRESSING:
            raise SuccessorEvidenceError("premature parent terminal")
        prefix = b"\n".join(parent.payload.split(b"\n")[:-2]) + b"\n"
        if terminal != expected or last["data"] != {
            "prefix_sha256": digest(prefix),
            "session_digests": [c.sha256 for c in children],
            "terminals": terminals,
            "counters": counters,
        }:
            raise SuccessorEvidenceError(
                "parent terminal prefix/counters/digests mismatch"
            )
    return SeriesSnapshot(parent, tuple(children), terminal, counters)


def _observation(admission: ManualAdmission) -> dict:
    installed = admission.host.installed_evidence
    return {
        "image_identity": list(installed.image_identity),
        "python_identity": list(installed.python_identity),
        "store_identity": list(admission.store.identity),
    }


class _EffectJournal:
    def __init__(self, journal: SuccessorJournal, operation: EffectOperation):
        self.journal, self.operation = journal, operation
        self.event = (
            "QUOTE_EFFECT"
            if operation is EffectOperation.QUOTE_REQUEST
            else "PAPER_EFFECT"
        )

    def records(self) -> tuple[EffectRecord, ...]:
        return tuple(
            effect_record(row["data"], self.operation)
            for row in self.journal.read().rows
            if row["event"] == self.event
        )

    def append(self, record: EffectRecord) -> None:
        self.journal.append(self.event, record.to_dict())


class SuccessorController:
    """One explicit call models one manual process start. No production factory."""

    def __init__(
        self, boundary: ManualStartBoundary, storage: SuccessorStorage
    ) -> None:
        if type(boundary) is not ManualStartBoundary:
            raise ValueError("exact source-only manual-start composition required")
        self.boundary, self.storage = boundary, storage

    def manual_start(
        self,
        *,
        quote_seam: Callable[[], QuoteDisposition],
        paper_seam: Callable[[], bool],
        pre_entry_guard: Callable[[], bool],
    ) -> SessionTerminal | str:
        if self.storage.read(PARENT_NAME) is not None:
            # Terminal replay is read-only and cannot grant another host admission.
            expected = SuccessorLineage(
                InstalledRuntimeMaterial(
                    self.boundary.release.manifest,
                    self.boundary.binding.sha256,
                    (STORE_IDENTITY,),
                )
            )
            closed = snapshot(self.storage, expected)
            if closed.terminal:
                return closed.terminal
        admission = self.boundary.admit()
        lineage = admission.lineage
        parent = SuccessorJournal(self.storage, lineage)
        initial = self.storage.read(PARENT_NAME) is None
        if initial:
            if any(self.storage.read(name) is not None for name in SESSION_NAMES):
                raise SuccessorEvidenceError(
                    "foreign child state blocks parent creation"
                )
            ordinal = 1
        else:
            state = snapshot(self.storage, lineage)
            if state.terminal:
                return state.terminal
            # Only a benign first final may advance to session two.
            if (
                len(state.parent.rows) == 6
                and len(state.children) == 1
                and state.parent.rows[-1]["event"] == "SESSION_01_FINAL"
                and SessionTerminal(state.parent.rows[-1]["data"]["terminal"])
                in PROGRESSING
            ):
                ordinal = 2
            else:
                raise SuccessorEvidenceError(
                    "consumed manual start; read-only reconciliation only"
                )
            old_process = state.children[0].header["process"]
            if (old_process["pid"], old_process["birth"]) == (
                admission.process.pid,
                admission.process.birth,
            ):
                raise SuccessorEvidenceError(
                    "session two requires a fresh manual process"
                )
        target = SESSIONS[ordinal - 1]
        if admission.process.observed_date < target:
            raise SuccessorEvidenceError(
                "fixed session has not arrived; no early grant"
            )
        if initial:
            parent.reserve(
                {
                    "schema": EVIDENCE_SCHEMA,
                    "kind": "PARENT",
                    "parent_id": lineage.parent_id,
                    "runtime_id": lineage.material.runtime_id,
                    "lineage": lineage.facts(),
                },
                "PARENT_RESERVED",
            )
            parent.append("SOURCE_ADMITTED")
            parent.append("RUNTIME_HOST_ADMITTED", _observation(admission))
            parent.append("SESSION_TUPLE_BOUND")
        else:
            observed = next(
                r["data"]
                for r in parent.read().rows
                if r["event"] == "RUNTIME_HOST_ADMITTED"
            )
            if observed != _observation(admission):
                raise SuccessorEvidenceError(
                    "installed image or durable store identity changed"
                )
        child = SuccessorJournal(self.storage, lineage, ordinal)
        # Exclusive child reservation consumes the only manual start before any seam.
        child.reserve(
            {
                "schema": EVIDENCE_SCHEMA,
                "kind": "SESSION",
                "parent_id": lineage.parent_id,
                "runtime_id": lineage.material.runtime_id,
                "ordinal": ordinal,
                "target_session": target,
                "child_id": lineage.child_id(ordinal),
                "grant_prefix": parent.read().sha256,
                "process": admission.process.facts(),
            },
            "MANUAL_START_ADMITTED",
        )
        parent.append(
            f"SESSION_{ordinal:02d}_GRANT_INTENT",
            {"child_id": lineage.child_id(ordinal)},
        )
        try:
            if admission.process.observed_date > target:
                terminal = SessionTerminal.SESSION_MISSED
            else:
                child.append("SOURCE_ADMITTED")
                child.append("RUNTIME_HOST_ADMITTED", _observation(admission))
                # Fresh successor proof publication. Never D1R7/D1R8 evidence.
                child.append("PREREQUISITE_ADMITTED")
                child.append(
                    "PREREQUISITE_PUBLISHED",
                    {"proof_sha256": prerequisite_proof(lineage, ordinal)},
                )

                def guard() -> bool:
                    fresh = self.boundary.admit()
                    return fresh == admission and pre_entry_guard() is True

                disposition = None

                def quote() -> None:
                    nonlocal disposition
                    disposition = quote_seam()
                    if type(disposition) is not QuoteDisposition:
                        raise ValueError(
                            "closed quote/strategy/risk disposition required"
                        )

                result = SuccessorExternalEffectAdapter(
                    _EffectJournal(child, EffectOperation.QUOTE_REQUEST),
                    EffectOperation.QUOTE_REQUEST,
                ).execute(pre_entry_guard=guard, external_seam=quote)
                if result.status is EffectStatus.PRE_ENTRY_REJECTED:
                    terminal = SessionTerminal.BLOCKED
                elif result.status is EffectStatus.AMBIGUOUS:
                    terminal = SessionTerminal.INDETERMINATE
                else:
                    child.append("QUOTE_DECISION", {"decision": disposition.value})
                    if disposition is not QuoteDisposition.PAPER_REQUIRED:
                        terminal = SessionTerminal(disposition.value)
                    else:

                        def paper() -> None:
                            if paper_seam() is not True:
                                raise ValueError("paper acknowledgement unproven")

                        result = SuccessorExternalEffectAdapter(
                            _EffectJournal(child, EffectOperation.PAPER_MUTATION),
                            EffectOperation.PAPER_MUTATION,
                        ).execute(pre_entry_guard=guard, external_seam=paper)
                        terminal = (
                            SessionTerminal.PAPER_EXECUTED
                            if result.status is EffectStatus.ACKNOWLEDGED
                            else SessionTerminal.BLOCKED
                            if result.status is EffectStatus.PRE_ENTRY_REJECTED
                            else SessionTerminal.INDETERMINATE
                        )
            counts = session_counters(child.read().rows)
            child.append(
                "SESSION_FINAL", {"terminal": terminal.value, "counters": counts}
            )
            parent.append(
                f"SESSION_{ordinal:02d}_FINAL",
                {
                    "child_sha256": child.read().sha256,
                    "terminal": terminal.value,
                    "counters": counts,
                },
            )
            state = snapshot(self.storage, lineage)
            if terminal not in PROGRESSING or ordinal == 2:
                parent.append(
                    "SERIES_COMPLETED" if terminal in PROGRESSING else "SERIES_HALTED",
                    {
                        "prefix_sha256": parent.read().sha256,
                        "session_digests": [c.sha256 for c in state.children],
                        "terminals": [
                            c.rows[-1]["data"]["terminal"] for c in state.children
                        ],
                        "counters": state.counters,
                    },
                )
            snapshot(self.storage, lineage)
            return terminal
        except Exception:
            # A failed durable write/readback cannot justify another append. Preserve
            # the incomplete attempt. Subsequent starts reject it without seam entry.
            return SessionTerminal.INDETERMINATE
