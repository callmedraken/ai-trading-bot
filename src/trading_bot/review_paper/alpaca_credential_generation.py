"""D1R4 fixed v3 generation protocol. No native effects on import."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from trading_bot.review_paper.alpaca_windows_credentials import (
    API_KEY_TARGET,
    API_SECRET_TARGET,
    CREDENTIAL_POLICY,
    MAX_SECRET_BYTES,
    validate_alpaca_credential_bytes,
)

MUTEX_NAME = r"Global\AITradingBot-Arch134-D1R4-AlpacaV3-Provision-v1"
ROLES = ("api_key_id", "api_secret_key")
TARGETS = (API_KEY_TARGET, API_SECRET_TARGET)
SCHEMA = "alpaca-v3-credential-generation-journal/v1"
EVENTS = frozenset(
    {
        "PROVISIONING_RESERVED",
        "LOCK_ACQUIRED",
        "EXPECTED_GENERATION",
        "INITIAL_STATE_ACCEPTED",
        "KEY_WRITE_INTENT",
        "KEY_WRITE_CONFIRMED",
        "SECRET_WRITE_INTENT",
        "SECRET_WRITE_CONFIRMED",
        "KEY_DELETE_INTENT",
        "CLEANUP_CONFIRMED",
        "PAIR_CONFIRMED",
        "FINAL",
        "V3_PROVIDER_EFFECT_INTENT",
    }
)
MAX_JOURNAL_BYTES = 32768


class GenerationError(RuntimeError):
    """Fixed-text, nonsecret protocol failure."""


@dataclass(frozen=True, slots=True)
class Witness:
    """Comparison evidence only; never authentication or domain identity."""

    fingerprint: str
    utf8_length: int

    def __post_init__(self) -> None:
        if (
            type(self.fingerprint) is not str
            or len(self.fingerprint) != 64
            or any(c not in "0123456789abcdef" for c in self.fingerprint)
            or type(self.utf8_length) is not int
            or not 0 < self.utf8_length <= MAX_SECRET_BYTES
        ):
            raise GenerationError("invalid credential witness")


def credential_witness(role: str, value: bytearray) -> Witness:
    """Architecture-84 exact domain-separated UTF-8 byte witness."""
    if type(role) is not str or role not in ROLES:
        raise GenerationError("invalid credential role")
    validate_alpaca_credential_bytes(value)
    digest = hashlib.sha256(b"AITradingBot/C3CredentialWitness/v1\0")
    digest.update(role.encode("utf-8") + b"\0")
    digest.update(value)
    return Witness(digest.hexdigest(), len(value))


def clear_credential(value: bytearray | None) -> None:
    """Clear an owned mutable temporary, including failed readback."""
    if type(value) is bytearray:
        for i in range(len(value)):
            value[i] = 0


def _canonical(record: dict[str, object]) -> bytes:
    return (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()


@dataclass(frozen=True, slots=True)
class PreservedGeneration:
    head: str
    tree: str
    witnesses: tuple[Witness, Witness]
    provider_fenced: bool
    truncated: bool
    pair_accepted: bool


def parse_generation_journal(payload: bytes) -> PreservedGeneration:
    """Validate bounded canonical records; salvage only a truncated final record."""
    failed = False
    result = None
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_JOURNAL_BYTES:
            raise ValueError
        truncated = not payload.endswith(b"\n")
        lines = payload.split(b"\n")[:-1]
        witnesses = None
        head = tree = None
        frozen = False
        classification = None
        for seq, line in enumerate(lines):
            record = json.loads(line)
            if (
                type(record) is not dict
                or set(record)
                != {
                    "schema",
                    "seq",
                    "event",
                    "source_head",
                    "source_tree",
                    "policy",
                    "witnesses",
                    "classification",
                }
                or _canonical(record) != line + b"\n"
            ):
                raise ValueError
            if (
                record["schema"] != SCHEMA
                or record["policy"] != CREDENTIAL_POLICY
                or type(record["seq"]) is not int
                or record["seq"] != seq
                or record["event"] not in EVENTS
                or record["classification"] not in CLASSIFICATIONS | {None}
            ):
                raise ValueError
            for name in ("source_head", "source_tree"):
                value = record[name]
                if (
                    type(value) is not str
                    or len(value) != 40
                    or any(c not in "0123456789abcdef" for c in value)
                ):
                    raise ValueError
            if head is None:
                head, tree = record["source_head"], record["source_tree"]
            if (head, tree) != (record["source_head"], record["source_tree"]):
                raise ValueError
            raw = record["witnesses"]
            if raw is not None:
                if type(raw) is not dict or set(raw) != set(ROLES):
                    raise ValueError
                for role in ROLES:
                    if type(raw[role]) is not dict or set(raw[role]) != {
                        "fingerprint",
                        "utf8_length",
                    }:
                        raise ValueError
                pair = tuple(Witness(**raw[role]) for role in ROLES)
                if witnesses is not None and witnesses != pair:
                    raise ValueError
                witnesses = pair
            elif witnesses is not None:
                raise ValueError
            frozen |= record["event"] == "V3_PROVIDER_EFFECT_INTENT"
            if record["event"] == "FINAL":
                classification = record["classification"]
        if witnesses is None:
            raise ValueError
        result = PreservedGeneration(
            head,
            tree,
            witnesses,
            frozen or truncated,
            truncated,
            classification in {"LOCAL_EXACT_MATCH", "RECONCILED_PAIR_MATCH"},
        )
    except Exception:
        failed = True
    if failed or result is None:
        raise GenerationError("invalid preserved generation journal")
    return result


CLASSIFICATIONS = frozenset(
    {
        "LOCAL_EXACT_MATCH",
        "CONCURRENT_PROVISIONER",
        "ABANDONED_OWNER",
        "BLOCKED_EXISTING_V3_STATE",
        "INPUT_OR_ADMISSION_FAILED",
        "CLEANUP_CONFIRMED",
        "WRITE_OUTCOME_AMBIGUOUS",
        "CLEANUP_OUTCOME_AMBIGUOUS",
        "EXTERNAL_STATE_INTERFERENCE",
        "RECONCILED_ABSENT",
        "RECONCILED_PAIR_MATCH",
        "RECONCILED_PARTIAL_MATCH",
        "RECONCILED_UNKNOWN_OR_FOREIGN_STATE",
        "PROVIDER_STAGING_CLOSED",
    }
)


class GenerationJournal:
    """Exclusive external file owned by the host; every record is durable."""

    def __init__(self, output: BinaryIO, head: str, tree: str) -> None:
        self.output, self.head, self.tree = output, head, tree
        self.witnesses: tuple[Witness, Witness] | None = None
        self.seq = self.size = 0
        self.failed = False

    def record(self, event: str, classification: str | None = None) -> None:
        if self.failed:
            raise GenerationError("generation journal is consumed")
        if event not in EVENTS or classification not in CLASSIFICATIONS | {None}:
            raise GenerationError("invalid generation event")
        witnesses = (
            None
            if self.witnesses is None
            else {
                role: {"fingerprint": w.fingerprint, "utf8_length": w.utf8_length}
                for role, w in zip(ROLES, self.witnesses, strict=True)
            }
        )
        payload = _canonical(
            {
                "schema": SCHEMA,
                "seq": self.seq,
                "event": event,
                "source_head": self.head,
                "source_tree": self.tree,
                "policy": CREDENTIAL_POLICY,
                "witnesses": witnesses,
                "classification": classification,
            }
        )
        if self.size + len(payload) > MAX_JOURNAL_BYTES:
            raise GenerationError("generation journal bound exceeded")
        failed = False
        try:
            if self.output.write(payload) != len(payload):
                raise GenerationError("generation journal write failed")
            self.output.flush()
            os.fsync(self.output.fileno())
        except BaseException:
            self.failed = True
            failed = True
        if failed:
            raise GenerationError("generation journal durability failed")
        self.size += len(payload)
        self.seq += 1


class CredentialStore(Protocol):
    def read(self, target: str) -> bytearray | None: ...
    def write(self, target: str, value: bytearray) -> bool: ...
    def delete(self, target: str) -> bool: ...


class Exclusion(Protocol):
    owned: bool
    abandoned: bool

    def acquire(self) -> bool: ...
    def release(self) -> None: ...


def _state(
    store: CredentialStore, expected: tuple[Witness, Witness]
) -> tuple[str, str]:
    observations = []
    for role, target, witness in zip(ROLES, TARGETS, expected, strict=True):
        blob = None
        try:
            blob = store.read(target)
            observations.append(
                "ABSENT"
                if blob is None
                else "MATCH"
                if credential_witness(role, blob) == witness
                else "FOREIGN"
            )
        finally:
            clear_credential(blob)
    return tuple(observations)


def reconcile_generation(
    store: CredentialStore, expected: tuple[Witness, Witness]
) -> str:
    """Read-only observation; never repairs, deletes or retries."""
    try:
        state = _state(store, expected)
    except Exception:
        return "RECONCILED_UNKNOWN_OR_FOREIGN_STATE"
    if state == ("ABSENT", "ABSENT"):
        return "RECONCILED_ABSENT"
    if state == ("MATCH", "MATCH"):
        return "RECONCILED_PAIR_MATCH"
    if set(state) == {"ABSENT", "MATCH"}:
        return "RECONCILED_PARTIAL_MATCH"
    return "RECONCILED_UNKNOWN_OR_FOREIGN_STATE"


def operate_generation(
    *,
    store: CredentialStore,
    mutex: Exclusion,
    journal: GenerationJournal,
    admit_source: Callable[[], object],
    interactive_pair: Callable[[], tuple[bytearray, bytearray]] | None = None,
    preserved: PreservedGeneration | None = None,
) -> str:
    """One generation; ambiguity stops mutations; final evidence precedes release."""
    values: tuple[bytearray, bytearray] | None = None
    journal.record("PROVISIONING_RESERVED")
    if not mutex.acquire():
        journal.record("FINAL", "CONCURRENT_PROVISIONER")
        return "CONCURRENT_PROVISIONER"
    outcome = "INPUT_OR_ADMISSION_FAILED"
    key_confirmed = mutation_entered = False
    try:
        journal.record("LOCK_ACQUIRED")
        if not mutex.owned:
            raise GenerationError("exclusion unavailable")
        if preserved is not None:
            journal.witnesses = preserved.witnesses
            journal.record("EXPECTED_GENERATION")
            if preserved.provider_fenced:
                journal.record("V3_PROVIDER_EFFECT_INTENT")
            outcome = reconcile_generation(store, preserved.witnesses)
        elif mutex.abandoned:
            # With no preserved witness, observe fixed state but cannot adopt it.
            for target in TARGETS:
                blob = None
                try:
                    blob = store.read(target)
                finally:
                    clear_credential(blob)
            outcome = "ABANDONED_OWNER"
        else:
            if interactive_pair is None:
                raise GenerationError("interactive generation required")
            values = interactive_pair()
            if type(values) is not tuple or len(values) != 2:
                raise GenerationError("invalid generation input")
            journal.witnesses = tuple(
                credential_witness(role, value)
                for role, value in zip(ROLES, values, strict=True)
            )
            journal.record("EXPECTED_GENERATION")
            try:
                initial = _state(store, journal.witnesses)
            except Exception:
                initial = ("UNKNOWN", "UNKNOWN")
            if initial != ("ABSENT", "ABSENT"):
                outcome = "BLOCKED_EXISTING_V3_STATE"
            else:
                journal.record("INITIAL_STATE_ACCEPTED")
                for i, (role, target, value) in enumerate(
                    zip(ROLES, TARGETS, values, strict=True)
                ):
                    admit_source()
                    if not mutex.owned:
                        raise GenerationError("exclusion unavailable")
                    journal.record(
                        "KEY_WRITE_INTENT" if i == 0 else "SECRET_WRITE_INTENT"
                    )
                    if not mutex.owned:
                        raise GenerationError("exclusion unavailable")
                    # Any call entered without full durable confirmation is ambiguous.
                    mutation_entered = True
                    if store.write(target, value) is not True:
                        raise GenerationError("credential write unconfirmed")
                    blob = None
                    try:
                        blob = store.read(target)
                        if (
                            blob is None
                            or credential_witness(role, blob) != journal.witnesses[i]
                        ):
                            raise GenerationError("credential readback unconfirmed")
                    finally:
                        clear_credential(blob)
                    admit_source()
                    if not mutex.owned:
                        raise GenerationError("exclusion unavailable")
                    journal.record(
                        "KEY_WRITE_CONFIRMED" if i == 0 else "SECRET_WRITE_CONFIRMED"
                    )
                    mutation_entered = False
                    key_confirmed = True
                # Pair confirmation failure cannot trigger destructive cleanup.
                mutation_entered = True
                if (
                    _state(store, journal.witnesses) != ("MATCH", "MATCH")
                    or not mutex.owned
                ):
                    raise GenerationError("pair readback unconfirmed")
                admit_source()
                journal.record("PAIR_CONFIRMED")
                outcome = "LOCAL_EXACT_MATCH"
        if mutex.abandoned:
            outcome = "ABANDONED_OWNER"
        admit_source()
    except Exception:
        if mutation_entered or not mutex.owned:
            outcome = "WRITE_OUTCOME_AMBIGUOUS"
        elif key_confirmed:
            # Only a failure before entering the second write can reach here.
            outcome = "CLEANUP_OUTCOME_AMBIGUOUS"
            try:
                admit_source()
                journal.record("KEY_DELETE_INTENT")
                state = _state(store, journal.witnesses)
                if state != ("MATCH", "ABSENT") or not mutex.owned:
                    outcome = "EXTERNAL_STATE_INTERFERENCE"
                elif store.delete(API_KEY_TARGET) is True:
                    if (
                        _state(store, journal.witnesses) == ("ABSENT", "ABSENT")
                        and mutex.owned
                    ):
                        journal.record("CLEANUP_CONFIRMED")
                        outcome = "CLEANUP_CONFIRMED"
            except Exception:
                pass
    except BaseException:
        outcome = (
            "WRITE_OUTCOME_AMBIGUOUS"
            if mutation_entered or key_confirmed
            else "INPUT_OR_ADMISSION_FAILED"
        )
        raise
    finally:
        if values is not None:
            for value in values:
                clear_credential(value)
        try:
            journal.record("FINAL", outcome)
        finally:
            mutex.release()
    return outcome


def read_preserved_generation(path: Path) -> PreservedGeneration:
    """Bounded read of external nonsecret generation evidence."""
    with path.open("rb") as source:
        return parse_generation_journal(source.read(MAX_JOURNAL_BYTES + 1))
