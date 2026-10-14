"""D1R4R incident-only pre-provider cleanup protocol; inert on import."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol

from trading_bot.review_paper.alpaca_credential_generation import (
    ROLES,
    TARGETS,
    Exclusion,
    GenerationError,
    PreservedGeneration,
    clear_credential,
    credential_witness,
    parse_generation_journal,
)
from trading_bot.review_paper.alpaca_windows_credentials import CREDENTIAL_POLICY

INCIDENT_SHA256 = "217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193"
INCIDENT_BYTES = 4865
INCIDENT_HEAD = "41351ade6a2434adc26b9389106339e034b53a06"
INCIDENT_TREE = "6a6e6528c7e0bfb43835f70c620276f960f723ee"
INCIDENT_JOURNAL = Path(
    r"F:\AI\temp\qualification\arch134-d1r4-v3-generation-"
    "77f1e13347fb4559b07523d30c4a7fb5.json"
)
# Independent of the supplied journal's path, filename, copy or alias.
CLEANUP_LATCH = Path(
    r"F:\AI\temp\qualification\arch134-d1r4r-cleanup-" + INCIDENT_SHA256 + ".json"
)
SCHEMA = "alpaca-v3-staging-cleanup/v1"
SEQUENCE = (
    "CLEANUP_RESERVED",
    "LOCK_ACQUIRED",
    "PRESERVED_GENERATION_ACCEPTED",
    "PAIR_MATCH_CONFIRMED",
    "KEY_DELETE_INTENT",
    "KEY_DELETE_CONFIRMED",
    "SECRET_DELETE_INTENT",
    "SECRET_DELETE_CONFIRMED",
    "PAIR_ABSENCE_CONFIRMED",
)
CLASSIFICATIONS = frozenset(
    {
        "CLEANUP_EXACT_PAIR_REMOVED",
        "CLEANUP_ADMISSION_BLOCKED",
        "CONCURRENT_PROVISIONER",
        "ABANDONED_OWNER",
        "DELETE_OUTCOME_AMBIGUOUS",
    }
)
MAX_CLEANUP_BYTES = 16384


class CleanupStore(Protocol):
    """Cleanup exposes no write capability."""

    def read(self, target: str) -> bytearray | None: ...
    def delete(self, target: str) -> bool: ...


def admit_incident(payload: bytes) -> PreservedGeneration:
    """Only the frozen complete, accepted, unfenced generation can enter."""
    if (
        type(payload) is not bytes
        or len(payload) != INCIDENT_BYTES
        or hashlib.sha256(payload).hexdigest() != INCIDENT_SHA256
    ):
        raise GenerationError("cleanup incident bytes mismatch")
    preserved = parse_generation_journal(payload)
    if (
        preserved.truncated
        or preserved.provider_fenced
        or not preserved.pair_accepted
        or (preserved.head, preserved.tree) != (INCIDENT_HEAD, INCIDENT_TREE)
        or any(w.utf8_length != 1 for w in preserved.witnesses)
    ):
        raise GenerationError("cleanup incident generation unavailable")
    return preserved


class CleanupJournal:
    """Closed canonical sequence; durable intent and confirmations; never reopen."""

    def __init__(self, output: BinaryIO, head: str, tree: str) -> None:
        for value in (head, tree):
            if (
                type(value) is not str
                or len(value) != 40
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise GenerationError("cleanup source identity invalid")
        self.output, self.head, self.tree = output, head, tree
        self.seq = self.size = 0
        self.failed = self.closed = False

    def record(self, event: str, classification: str | None = None) -> None:
        if (
            self.failed
            or self.closed
            or (
                event != "FINAL"
                and (self.seq >= len(SEQUENCE) or event != SEQUENCE[self.seq])
            )
            or (event == "FINAL" and classification not in CLASSIFICATIONS)
            or (event != "FINAL" and classification is not None)
            or (
                classification == "CLEANUP_EXACT_PAIR_REMOVED"
                and self.seq != len(SEQUENCE)
            )
        ):
            raise GenerationError("cleanup evidence sequence unavailable")
        payload = (
            json.dumps(
                {
                    "schema": SCHEMA,
                    "seq": self.seq,
                    "event": event,
                    "source_head": self.head,
                    "source_tree": self.tree,
                    "policy": CREDENTIAL_POLICY,
                    "preserved_sha256": INCIDENT_SHA256,
                    "preserved_bytes": INCIDENT_BYTES,
                    "generation_head": INCIDENT_HEAD,
                    "generation_tree": INCIDENT_TREE,
                    "classification": classification,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        if self.size + len(payload) > MAX_CLEANUP_BYTES:
            self.failed = True
            raise GenerationError("cleanup evidence bound exceeded")
        failed = False
        try:
            if self.output.write(payload) != len(payload):
                raise OSError
            self.output.flush()
            os.fsync(self.output.fileno())
        except BaseException:
            self.failed = failed = True
        if failed:
            raise GenerationError("cleanup evidence durability unavailable")
        self.seq += 1
        self.size += len(payload)
        self.closed = event == "FINAL"


@contextmanager
def reserve_cleanup(head: str, tree: str) -> Iterator[CleanupJournal]:
    """Fixed incident-wide exclusive latch. Existing/partial files always block."""
    # The host admits ancestors before entry; xb preserves every consumed latch.
    with CLEANUP_LATCH.open("xb") as output:
        journal = CleanupJournal(output, head, tree)
        journal.record("CLEANUP_RESERVED")
        yield journal


def operate_cleanup(
    *,
    load_preserved: Callable[[], bytes],
    store: CleanupStore,
    mutex: Exclusion,
    journal: CleanupJournal,
    admit_source: Callable[[], object],
) -> str:
    """Exact pair only, one delete per role, no repair/restoration/retry."""
    outcome = "CLEANUP_ADMISSION_BLOCKED"
    entered = acquired = False

    def guard() -> None:
        admit_source()
        admit_incident(load_preserved())
        if not mutex.owned or mutex.abandoned or journal.failed:
            raise GenerationError("cleanup authority unavailable")

    def observe(index: int, preserved: PreservedGeneration) -> str:
        guard()
        blob = None
        try:
            blob = store.read(TARGETS[index])
            state = (
                "ABSENT"
                if blob is None
                else "MATCH"
                if credential_witness(ROLES[index], blob) == preserved.witnesses[index]
                else "FOREIGN"
            )
            guard()
            return state
        finally:
            clear_credential(blob)

    def pair(preserved: PreservedGeneration) -> tuple[str, str]:
        return observe(0, preserved), observe(1, preserved)

    try:
        admit_source()
        if journal.seq != 1 or journal.failed or journal.closed:
            raise GenerationError("durable cleanup reservation required")
        preserved = admit_incident(load_preserved())
        acquired = mutex.acquire()
        if not acquired:
            outcome = "CONCURRENT_PROVISIONER"
        else:
            journal.record("LOCK_ACQUIRED")
            if mutex.abandoned:
                outcome = "ABANDONED_OWNER"
            else:
                guard()
                journal.record("PRESERVED_GENERATION_ACCEPTED")
                if pair(preserved) != ("MATCH", "MATCH"):
                    raise GenerationError("cleanup exact pair unavailable")
                journal.record("PAIR_MATCH_CONFIRMED")
                for index in range(2):
                    guard()
                    journal.record(SEQUENCE[4 + 2 * index])
                    # Recheck both records AFTER the durable fence, before native entry.
                    expected = ("MATCH", "MATCH") if index == 0 else ("ABSENT", "MATCH")
                    if pair(preserved) != expected:
                        raise GenerationError("cleanup exact state changed")
                    guard()
                    entered = True
                    if store.delete(TARGETS[index]) is not True:
                        raise GenerationError("cleanup delete unconfirmed")
                    if observe(index, preserved) != "ABSENT":
                        raise GenerationError("cleanup delete readback unconfirmed")
                    guard()
                    journal.record(SEQUENCE[5 + 2 * index])
                if pair(preserved) != ("ABSENT", "ABSENT"):
                    raise GenerationError("cleanup final absence unconfirmed")
                guard()
                journal.record("PAIR_ABSENCE_CONFIRMED")
                outcome = "CLEANUP_EXACT_PAIR_REMOVED"
    except BaseException:
        outcome = "DELETE_OUTCOME_AMBIGUOUS" if entered else "CLEANUP_ADMISSION_BLOCKED"
    finally:
        try:
            if acquired and not mutex.abandoned:
                guard()
            journal.record("FINAL", outcome)
        except BaseException:
            outcome = (
                "DELETE_OUTCOME_AMBIGUOUS" if entered else "CLEANUP_ADMISSION_BLOCKED"
            )
        finally:
            if acquired:
                try:
                    mutex.release()
                except BaseException:
                    outcome = (
                        "DELETE_OUTCOME_AMBIGUOUS"
                        if entered
                        else "CLEANUP_ADMISSION_BLOCKED"
                    )
    return outcome
