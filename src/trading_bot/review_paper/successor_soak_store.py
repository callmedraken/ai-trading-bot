"""Closed canonical successor JSONL and disposable storage; no repair path."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Protocol

from trading_bot.review_paper.successor_soak_admission import ManualProcessObservation
from trading_bot.review_paper.successor_soak_contract import (
    EVIDENCE_SCHEMA,
    MAX_BYTES,
    MAX_RECORDS,
    PARENT_NAME,
    PROGRESSING,
    SESSION_NAMES,
    SESSIONS,
    SessionTerminal,
    SuccessorLineage,
    canonical,
    digest,
    ordinal_index,
    validate_counters,
    zero_counters,
)
from trading_bot.supervised_release.runtime_isolation import (
    DiagnosticReason,
    EffectOperation,
    EffectRecord,
    EffectStage,
    validate_effect_records,
)

NAMES = (PARENT_NAME, *SESSION_NAMES)
PARENT_PREFIX = (
    "PARENT_RESERVED",
    "SOURCE_ADMITTED",
    "RUNTIME_HOST_ADMITTED",
    "SESSION_TUPLE_BOUND",
)
CHILD_PREFIX = (
    "MANUAL_START_ADMITTED",
    "SOURCE_ADMITTED",
    "RUNTIME_HOST_ADMITTED",
    "PREREQUISITE_ADMITTED",
    "PREREQUISITE_PUBLISHED",
)


class SuccessorEvidenceError(ValueError):
    """Evidence is consumed, conflicting or unprovable; preserve it unchanged."""


class SuccessorStorage(Protocol):
    def read(self, name: str) -> bytes | None: ...

    def reserve(self, name: str, data: bytes) -> None: ...

    def append(self, name: str, expected: bytes, data: bytes) -> None: ...


def exact(value: object, fields: set[str]) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise SuccessorEvidenceError("closed successor fields required")
    return value


def _unique(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise SuccessorEvidenceError("duplicate successor field")
        value[key] = item
    return value


def _hash(value: object) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise SuccessorEvidenceError("canonical evidence digest required")


def _identity(value: object) -> None:
    if (
        type(value) is not list
        or len(value) != 2
        or any(type(v) is not int or v <= 0 for v in value)
    ):
        raise SuccessorEvidenceError("observed file identity required")


def runtime_observation(value: object) -> None:
    row = exact(value, {"image_identity", "python_identity", "store_identity"})
    for item in row.values():
        _identity(item)


def prerequisite_proof(lineage: SuccessorLineage, ordinal: int) -> str:
    return digest(
        canonical(
            {
                "schema": EVIDENCE_SCHEMA,
                "phase": "FRESH_SUCCESSOR_PREREQUISITE",
                "parent_id": lineage.parent_id,
                "child_id": lineage.child_id(ordinal),
                "runtime_id": lineage.material.runtime_id,
            }
        )
    )


def effect_record(value: object, operation: EffectOperation) -> EffectRecord:
    row = exact(value, {"schema", "sequence", "operation", "stage", "reason"})
    record = EffectRecord(
        row["sequence"],
        EffectOperation(row["operation"]),
        EffectStage(row["stage"]),
        None if row["reason"] is None else DiagnosticReason(row["reason"]),
    )
    if record.operation is not operation or record.to_dict() != row:
        raise SuccessorEvidenceError("effect operation or schema mismatch")
    return record


def session_counters(rows: tuple[dict, ...]) -> dict[str, int]:
    result = zero_counters()
    if rows:
        result["child_grants"] = result["manual_start_admissions"] = 1
    for row in rows:
        event, data = row["event"], row["data"]
        if event == "PREREQUISITE_ADMITTED":
            result["prerequisite_admissions"] = 1
        elif event == "PREREQUISITE_PUBLISHED":
            result["prerequisite_publications"] = 1
        elif event == "QUOTE_EFFECT" and data["stage"] == "ENTRY_ADMITTED":
            # One injected quote seam includes one bounded credential phase.
            result["provider_entries"] = result["credential_phases"] = 1
            result["paper_attempts"] = 1
        elif event == "PAPER_EFFECT" and data["stage"] == "ENTRY_ADMITTED":
            # Reserve the possible mutation even if ACK never becomes durable.
            result["paper_fills"] = 1
    return validate_counters(result, session=True)


def _validate_child(
    header: dict, rows: tuple[dict, ...], lineage: SuccessorLineage
) -> None:
    prefix = tuple(row["event"] for row in rows[: len(CHILD_PREFIX)])
    observed = header["process"]["observed_date"]
    target = SESSIONS[ordinal_index(header["ordinal"])]
    missed = (
        len(rows) == 2
        and rows[-1]["event"] == "SESSION_FINAL"
        and rows[-1]["data"].get("terminal") == "SESSION_MISSED"
    )
    if observed < target or (missed and observed <= target):
        raise SuccessorEvidenceError("observed date cannot replace the fixed session")
    if observed > target and len(rows) > 1 and not missed:
        raise SuccessorEvidenceError("missed date cannot enter a prerequisite/effect")
    # SESSION_MISSED is the short path without prerequisite or external entry.
    if (
        len(rows) == 2
        and rows[-1]["event"] == "SESSION_FINAL"
        and rows[-1]["data"].get("terminal") == "SESSION_MISSED"
    ):
        if rows[0]["event"] != "MANUAL_START_ADMITTED" or rows[0]["data"] != {}:
            raise SuccessorEvidenceError("missed session prefix rejected")
    else:
        if prefix != CHILD_PREFIX[: len(prefix)]:
            raise SuccessorEvidenceError("successor admission order rejected")
        for row in rows[: len(CHILD_PREFIX)]:
            if row["event"] == "RUNTIME_HOST_ADMITTED":
                runtime_observation(row["data"])
            elif row["event"] == "PREREQUISITE_PUBLISHED":
                if row["data"] != {
                    "proof_sha256": prerequisite_proof(lineage, header["ordinal"])
                }:
                    raise SuccessorEvidenceError("fresh prerequisite proof required")
            elif row["data"] != {}:
                raise SuccessorEvidenceError("unexpected admission fields")
        quote, paper = [], []
        decision = None
        for row in rows[len(CHILD_PREFIX) :]:
            event, data = row["event"], row["data"]
            if event == "QUOTE_EFFECT" and not paper and decision is None:
                quote.append(effect_record(data, EffectOperation.QUOTE_REQUEST))
                validate_effect_records(tuple(quote))
            elif (
                event == "QUOTE_DECISION"
                and decision is None
                and quote
                and quote[-1].stage is EffectStage.ACK
            ):
                if data not in (
                    {"decision": "NO_SIGNAL"},
                    {"decision": "RISK_REJECTED"},
                    {"decision": "PAPER_REQUIRED"},
                ):
                    raise SuccessorEvidenceError("closed quote disposition required")
                decision = data["decision"]
            elif event == "PAPER_EFFECT" and decision == "PAPER_REQUIRED":
                paper.append(effect_record(data, EffectOperation.PAPER_MUTATION))
                validate_effect_records(tuple(paper))
            elif event == "SESSION_FINAL" and row is rows[-1]:
                terminal = SessionTerminal(data.get("terminal"))
                effect = paper if paper else quote
                stage = effect[-1].stage if effect else None
                permitted = (
                    (
                        terminal is SessionTerminal.BLOCKED
                        and stage is EffectStage.PRE_ENTRY_REJECTED
                    )
                    or (
                        terminal is SessionTerminal.INDETERMINATE
                        and stage
                        in {EffectStage.ENTRY_ADMITTED, EffectStage.DIAGNOSTIC}
                    )
                    or (
                        terminal.value == decision
                        and decision in {"NO_SIGNAL", "RISK_REJECTED"}
                        and not paper
                    )
                    or (
                        terminal is SessionTerminal.PAPER_EXECUTED
                        and paper
                        and stage is EffectStage.ACK
                    )
                )
                if not permitted:
                    raise SuccessorEvidenceError("terminal/effect matrix rejected")
            else:
                raise SuccessorEvidenceError("invalid successor session transition")
    if rows and rows[-1]["event"] == "SESSION_FINAL":
        data = exact(rows[-1]["data"], {"terminal", "counters"})
        SessionTerminal(data["terminal"])
        validate_counters(data["counters"], session=True)
        if data["counters"] != session_counters(rows):
            raise SuccessorEvidenceError(
                "session counters differ from durable entry evidence"
            )


def _validate_parent(rows: tuple[dict, ...], lineage: SuccessorLineage) -> None:
    for index, row in enumerate(rows):
        event, data = row["event"], row["data"]
        if index < 4:
            if event != PARENT_PREFIX[index]:
                raise SuccessorEvidenceError("parent admission order rejected")
            if event == "RUNTIME_HOST_ADMITTED":
                runtime_observation(data)
            elif data != {}:
                raise SuccessorEvidenceError("unexpected parent admission fields")
        elif event in {"SERIES_COMPLETED", "SERIES_HALTED"}:
            if index not in (6, 8) or rows[index - 1]["event"] not in {
                "SESSION_01_FINAL",
                "SESSION_02_FINAL",
            }:
                raise SuccessorEvidenceError(
                    "parent requires exact closed child finals"
                )
            prior = SessionTerminal(rows[index - 1]["data"]["terminal"])
            if (event == "SERIES_COMPLETED") != (index == 8 and prior in PROGRESSING):
                raise SuccessorEvidenceError("parent terminal/progression mismatch")
            if event == "SERIES_HALTED" and prior in PROGRESSING:
                raise SuccessorEvidenceError("benign session cannot halt parent")
            if row is not rows[-1]:
                raise SuccessorEvidenceError("terminal parent extension rejected")
            exact(data, {"prefix_sha256", "session_digests", "terminals", "counters"})
            _hash(data["prefix_sha256"])
            validate_counters(data["counters"], session=False)
            finals = [
                r["data"]
                for r in rows[:index]
                if r["event"] in {"SESSION_01_FINAL", "SESSION_02_FINAL"}
            ]
            counts = zero_counters()
            counts["parent_creations"] = 1
            for final in finals:
                for key, value in final["counters"].items():
                    counts[key] += value
            if (
                data["session_digests"] != [f["child_sha256"] for f in finals]
                or data["terminals"] != [f["terminal"] for f in finals]
                or data["counters"] != counts
            ):
                raise SuccessorEvidenceError("closed parent terminal material required")
        else:
            ordinal = 1 if index < 6 else 2
            if index > 7:
                raise SuccessorEvidenceError("no third session representable")
            expected = f"SESSION_{ordinal:02d}_" + (
                "GRANT_INTENT" if index % 2 == 0 else "FINAL"
            )
            if event != expected:
                raise SuccessorEvidenceError("parent session order rejected")
            if index % 2 == 0:
                if data != {"child_id": lineage.child_id(ordinal)}:
                    raise SuccessorEvidenceError("exact fresh child required")
            else:
                exact(data, {"child_sha256", "terminal", "counters"})
                _hash(data["child_sha256"])
                SessionTerminal(data["terminal"])
                validate_counters(data["counters"], session=True)
                if (
                    SessionTerminal(data["terminal"]) not in PROGRESSING
                    and index != len(rows) - 1
                    and rows[index + 1]["event"] != "SERIES_HALTED"
                ):
                    raise SuccessorEvidenceError("halting session cannot progress")


@dataclass(frozen=True, slots=True)
class Replay:
    header: dict
    rows: tuple[dict, ...]
    payload: bytes

    @property
    def sha256(self) -> str:
        return digest(self.payload)


def replay(payload: bytes, lineage: SuccessorLineage, ordinal: int | None) -> Replay:
    if (
        type(payload) is not bytes
        or not 0 < len(payload) <= MAX_BYTES
        or not payload.endswith(b"\n")
    ):
        raise SuccessorEvidenceError("bounded complete successor JSONL required")
    lines = payload.split(b"\n")[:-1]
    if not 2 <= len(lines) <= MAX_RECORDS + 1:
        raise SuccessorEvidenceError("successor record budget rejected")
    try:
        values = [json.loads(line, object_pairs_hook=_unique) for line in lines]
        if any(
            canonical(value) != line for value, line in zip(values, lines, strict=True)
        ):
            raise SuccessorEvidenceError("noncanonical successor JSONL")
        header = values[0]
        common = {
            "schema": EVIDENCE_SCHEMA,
            "parent_id": lineage.parent_id,
            "runtime_id": lineage.material.runtime_id,
        }
        if ordinal is None:
            if header != common | {"kind": "PARENT", "lineage": lineage.facts()}:
                raise SuccessorEvidenceError("parent lineage/header mismatch")
        else:
            index = ordinal_index(ordinal)
            exact(
                header,
                set(common)
                | {
                    "kind",
                    "ordinal",
                    "target_session",
                    "child_id",
                    "grant_prefix",
                    "process",
                },
            )
            if any(
                header[k] != v
                for k, v in (
                    common
                    | {
                        "kind": "SESSION",
                        "ordinal": ordinal,
                        "target_session": SESSIONS[index],
                        "child_id": lineage.child_id(ordinal),
                    }
                ).items()
            ):
                raise SuccessorEvidenceError("child binding mismatch")
            _hash(header["grant_prefix"])
            process = exact(header["process"], {"pid", "birth", "observed_date"})
            ManualProcessObservation(**process)
        rows = tuple(values[1:])
        for sequence, row in enumerate(rows, 1):
            exact(
                row, {"schema", "parent_id", "runtime_id", "sequence", "event", "data"}
            )
            if (
                any(row[k] != v for k, v in common.items())
                or type(row["sequence"]) is not int
                or row["sequence"] != sequence
            ):
                raise SuccessorEvidenceError("runtime/parent/sequence mismatch")
            if type(row["event"]) is not str or type(row["data"]) is not dict:
                raise SuccessorEvidenceError("closed event/data required")
        if ordinal is None:
            _validate_parent(rows, lineage)
            if rows[-1]["event"] in {"SERIES_COMPLETED", "SERIES_HALTED"}:
                prefix = b"\n".join(lines[:-1]) + b"\n"
                if rows[-1]["data"]["prefix_sha256"] != digest(prefix):
                    raise SuccessorEvidenceError("parent terminal prefix mismatch")
        else:
            _validate_child(header, rows, lineage)
        return Replay(header, rows, payload)
    except (
        KeyError,
        TypeError,
        UnicodeError,
        json.JSONDecodeError,
        RecursionError,
    ) as exc:
        raise SuccessorEvidenceError("malformed successor evidence") from exc


def event_row(lineage: SuccessorLineage, sequence: int, event: str, data: dict) -> dict:
    return {
        "schema": EVIDENCE_SCHEMA,
        "parent_id": lineage.parent_id,
        "runtime_id": lineage.material.runtime_id,
        "sequence": sequence,
        "event": event,
        "data": data,
    }


class SuccessorJournal:
    def __init__(
        self,
        storage: SuccessorStorage,
        lineage: SuccessorLineage,
        ordinal: int | None = None,
    ) -> None:
        if type(lineage) is not SuccessorLineage:
            raise SuccessorEvidenceError("exact successor lineage required")
        self.storage, self.lineage, self.ordinal = storage, lineage, ordinal
        self.name = (
            PARENT_NAME if ordinal is None else SESSION_NAMES[ordinal_index(ordinal)]
        )

    def read(self) -> Replay:
        return replay(self.storage.read(self.name), self.lineage, self.ordinal)

    def reserve(self, header: dict, event: str) -> Replay:
        payload = (
            canonical(header)
            + b"\n"
            + canonical(event_row(self.lineage, 1, event, {}))
            + b"\n"
        )
        replay(payload, self.lineage, self.ordinal)
        self.storage.reserve(self.name, payload)
        result = self.read()
        if result.payload != payload:
            raise SuccessorEvidenceError("exclusive reservation readback mismatch")
        return result

    def append(self, event: str, data: dict | None = None) -> Replay:
        before = self.read()
        payload = (
            canonical(
                event_row(
                    self.lineage,
                    len(before.rows) + 1,
                    event,
                    {} if data is None else data,
                )
            )
            + b"\n"
        )
        replay(before.payload + payload, self.lineage, self.ordinal)
        self.storage.append(self.name, before.payload, payload)
        result = self.read()
        if result.payload != before.payload + payload:
            raise SuccessorEvidenceError("durable successor readback mismatch")
        return result


class DisposableSuccessorStorage:
    """Flush/fsync test adapter. Production and development roots rejected first.

    This is not a native production-store admission/ACL adapter. Production has
    no construction path in this source checkpoint.
    """

    def __init__(self, root: Path) -> None:
        text = str(root)
        windows = PureWindowsPath(text)
        for forbidden in (
            r"F:\AITradingBot",
            r"F:\AI\worktrees",
            r"F:\AI\ai-trading-bot",
            r"F:\AI\temp\qualification",
        ):
            parent = PureWindowsPath(forbidden)
            if windows == parent or parent in windows.parents:
                raise SuccessorEvidenceError("protected/development namespace excluded")
        if not root.is_absolute() or ".." in root.parts:
            raise SuccessorEvidenceError("canonical external test root required")
        self.root = root
        for path in (root, *root.parents):
            self._regular(path, directory=True)
        self.root_identity = self._identity(root)
        self.files: dict[str, tuple[int, int]] = {}
        self._check_root()

    @staticmethod
    def _identity(path: Path) -> tuple[int, int]:
        value = path.lstat()
        return value.st_dev, value.st_ino

    @staticmethod
    def _regular(path: Path, *, directory: bool = False) -> None:
        value = path.lstat()
        if (
            stat.S_ISLNK(value.st_mode)
            or getattr(value, "st_file_attributes", 0) & 0x400
            or (
                not directory
                and (not stat.S_ISREG(value.st_mode) or value.st_nlink != 1)
            )
            or (directory and not stat.S_ISDIR(value.st_mode))
        ):
            raise SuccessorEvidenceError("regular no-link evidence objects required")

    def _check_root(self) -> None:
        self._regular(self.root, directory=True)
        if self._identity(self.root) != self.root_identity or any(
            p.name not in NAMES for p in self.root.iterdir()
        ):
            raise SuccessorEvidenceError("foreign or replaced successor namespace")

    def _path(self, name: str) -> Path:
        if name not in NAMES:
            raise SuccessorEvidenceError("fixed successor filename required")
        self._check_root()
        return self.root / name

    def read(self, name: str) -> bytes | None:
        path = self._path(name)
        try:
            self._regular(path)
        except FileNotFoundError:
            if name in self.files:
                raise SuccessorEvidenceError("evidence disappeared") from None
            return None
        identity = self._identity(path)
        if name in self.files and self.files[name] != identity:
            raise SuccessorEvidenceError("evidence object replaced")
        self.files[name] = identity
        with path.open("rb") as handle:
            value = handle.read(MAX_BYTES + 1)
            info = os.fstat(handle.fileno())
            if (info.st_dev, info.st_ino) != identity or len(value) > MAX_BYTES:
                raise SuccessorEvidenceError("evidence drift/byte budget rejected")
        self._regular(path)
        if self._identity(path) != identity:
            raise SuccessorEvidenceError("evidence identity drift")
        return value

    def reserve(self, name: str, data: bytes) -> None:
        path = self._path(name)
        if name == PARENT_NAME and any(self.root.iterdir()):
            raise SuccessorEvidenceError("exclusive fresh parent namespace required")
        with path.open("xb") as handle:
            self.files[name] = self._identity(path)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

    def append(self, name: str, expected: bytes, data: bytes) -> None:
        if self.read(name) != expected:
            raise SuccessorEvidenceError("append-only prefix changed")
        path = self._path(name)
        with path.open("ab") as handle:
            info = os.fstat(handle.fileno())
            if (info.st_dev, info.st_ino) != self.files[name]:
                raise SuccessorEvidenceError("append object drift")
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
