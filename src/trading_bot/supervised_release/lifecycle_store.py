"""Bounded durable lifecycle evidence for Architecture 134-F1R1-B.

The journal is deliberately narrower than a general-purpose log.  It stores
only a fixed runtime identity, a versioned schema, closed lifecycle events,
and monotonic sequence numbers.  Storage is injected so source tests can use
disposable files or an in-memory fake without touching the production path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from trading_bot.supervised_release.runtime_isolation import (
    MAX_LIFECYCLE_RECORDS,
    LifecycleEvent,
    LifecycleEvidence,
    LifecycleRecord,
    LifecycleStatus,
)

LIFECYCLE_JOURNAL_SCHEMA = "arch134-f1r1-b-lifecycle-journal/v1"
MAX_LIFECYCLE_JOURNAL_BYTES = 16 * 1024
PRODUCTION_LIFECYCLE_PATH = (
    r"F:\AITradingBot\data\lifecycle\arch134-f1r1-b-runtime.jsonl"
)


@runtime_checkable
class LifecycleStorage(Protocol):
    """The only storage capability required by the journal."""

    def read_bytes(self) -> bytes: ...

    def append_durable(self, data: bytes) -> None: ...


class LifecycleJournalError(ValueError):
    """Stored lifecycle state is malformed, partial, or no longer bounded."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LifecycleJournalError("duplicate lifecycle journal field")
        result[key] = value
    return result


def _exact_fields(value: object, expected: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise LifecycleJournalError("exact lifecycle journal fields required")
    return value


def _record_dict(runtime_id: str, record: LifecycleRecord) -> dict[str, object]:
    return {
        "schema": LIFECYCLE_JOURNAL_SCHEMA,
        "runtime_id": runtime_id,
        "sequence": record.sequence,
        "event": record.event.value,
    }


class DisposableLifecycleFileStorage:
    """A flush-and-fsync file adapter for disposable test paths only."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)

    def read_bytes(self) -> bytes:
        try:
            return self._path.read_bytes()
        except FileNotFoundError:
            return b""

    def append_durable(self, data: bytes) -> None:
        if type(data) is not bytes:
            raise LifecycleJournalError("lifecycle storage requires bytes")
        with self._path.open("ab") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())


class FixedProductionLifecycleStorage(DisposableLifecycleFileStorage):
    """Code-owned production destination; not used by source-only tests."""

    def __init__(self) -> None:
        super().__init__(PRODUCTION_LIFECYCLE_PATH)


class MemoryLifecycleStorage:
    """Disposable storage seam used by focused tests, not a production store."""

    def __init__(self, initial: bytes = b"") -> None:
        self._data = initial
        self.flushes = 0

    def read_bytes(self) -> bytes:
        return self._data

    def append_durable(self, data: bytes) -> None:
        if type(data) is not bytes:
            raise LifecycleJournalError("lifecycle storage requires bytes")
        self._data += data
        self.flushes += 1


class DurableLifecycleJournal:
    """Replay-before-append, append-only lifecycle evidence.

    A journal starts with one canonical header line.  Each subsequent line is
    one canonical event row.  The storage adapter must return only after its
    append has been flushed and durably committed; the journal then replays
    the bytes before acknowledging the append to its caller.
    """

    def __init__(self, runtime_id: str, storage: LifecycleStorage) -> None:
        try:
            LifecycleEvidence(runtime_id, ())
        except (TypeError, ValueError) as exc:
            raise LifecycleJournalError("canonical runtime identity required") from exc
        if not isinstance(storage, LifecycleStorage):
            raise LifecycleJournalError("injected lifecycle storage required")
        self._runtime_id = runtime_id
        self._storage = storage
        self._replay()

    @property
    def runtime_id(self) -> str:
        return self._runtime_id

    def _read(self) -> bytes:
        data = self._storage.read_bytes()
        if type(data) is not bytes or len(data) > MAX_LIFECYCLE_JOURNAL_BYTES:
            raise LifecycleJournalError("lifecycle journal byte budget exceeded")
        return data

    def _replay(self) -> tuple[LifecycleRecord, ...]:
        data = self._read()
        if not data:
            return ()
        if not data.endswith(b"\n"):
            raise LifecycleJournalError("partial lifecycle journal line")
        lines = data.split(b"\n")[:-1]
        if not lines:
            raise LifecycleJournalError("empty lifecycle journal record")
        try:
            header = json.loads(
                lines[0].decode("utf-8"), object_pairs_hook=_unique_object
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LifecycleJournalError("malformed lifecycle journal header") from exc
        header = _exact_fields(header, {"schema", "runtime_id"})
        if (
            header["schema"] != LIFECYCLE_JOURNAL_SCHEMA
            or header["runtime_id"] != self._runtime_id
            or _canonical(header) != lines[0]
        ):
            raise LifecycleJournalError("lifecycle journal header mismatch")

        records: list[LifecycleRecord] = []
        for line in lines[1:]:
            try:
                raw = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LifecycleJournalError("malformed lifecycle journal row") from exc
            raw = _exact_fields(raw, {"schema", "runtime_id", "sequence", "event"})
            if (
                raw["schema"] != LIFECYCLE_JOURNAL_SCHEMA
                or raw["runtime_id"] != self._runtime_id
                or _canonical(raw) != line
            ):
                raise LifecycleJournalError("noncanonical lifecycle journal row")
            try:
                records.append(
                    LifecycleRecord(raw["sequence"], LifecycleEvent(raw["event"]))
                )
            except (TypeError, ValueError) as exc:
                raise LifecycleJournalError("invalid lifecycle journal event") from exc

        if len(records) > MAX_LIFECYCLE_RECORDS:
            raise LifecycleJournalError("lifecycle record budget exceeded")
        try:
            LifecycleEvidence(self._runtime_id, tuple(records))
        except (TypeError, ValueError) as exc:
            raise LifecycleJournalError("lifecycle replay rejected") from exc
        return tuple(records)

    def records(self) -> tuple[LifecycleRecord, ...]:
        return self._replay()

    def snapshot(self) -> LifecycleEvidence:
        return LifecycleEvidence(self._runtime_id, self._replay())

    def append(self, event: LifecycleEvent) -> LifecycleEvidence:
        records = self._replay()
        candidate = records + (LifecycleRecord(len(records) + 1, event),)
        try:
            LifecycleEvidence(self._runtime_id, candidate)
        except (TypeError, ValueError) as exc:
            raise LifecycleJournalError("lifecycle transition rejected") from exc

        current = self._read()
        prefix = (
            _canonical(
                {"schema": LIFECYCLE_JOURNAL_SCHEMA, "runtime_id": self._runtime_id}
            )
            + b"\n"
            if not current
            else b""
        )
        line = _canonical(_record_dict(self._runtime_id, candidate[-1])) + b"\n"
        if len(current) + len(prefix) + len(line) > MAX_LIFECYCLE_JOURNAL_BYTES:
            raise LifecycleJournalError("lifecycle journal byte budget exhausted")
        self._storage.append_durable(prefix + line)
        replayed = self._replay()
        if replayed != candidate:
            raise LifecycleJournalError("lifecycle journal readback mismatch")
        return LifecycleEvidence(self._runtime_id, replayed)


def replay_lifecycle_journal(
    runtime_id: str, storage: LifecycleStorage
) -> LifecycleEvidence:
    """Read-only replay helper with no repair or truncation behavior."""

    return DurableLifecycleJournal(runtime_id, storage).snapshot()


__all__ = [
    "DisposableLifecycleFileStorage",
    "DurableLifecycleJournal",
    "FixedProductionLifecycleStorage",
    "LifecycleJournalError",
    "LifecycleStorage",
    "LifecycleStatus",
    "MemoryLifecycleStorage",
    "PRODUCTION_LIFECYCLE_PATH",
    "replay_lifecycle_journal",
]
