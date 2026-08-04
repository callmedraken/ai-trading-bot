"""Executable evidence for the normalized transactional authority design."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from dataclasses import FrozenInstanceError, dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    MAX_DAILY_SNAPSHOT_SYMBOLS,
)

SCHEMA_PATH = (
    Path(__file__).parents[1] / "fixtures" / "transactional_authority_schema.sql"
)
NAMESPACE = uuid.UUID("7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012")
EPOCH = "12345678-1234-5678-9abc-def012345678"
MACHINE = "87654321-4321-8765-cba9-876543210987"
PROVIDER = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
OPERATION = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
POLICY = "authority-policy/v1"
CLAIM_POLICY = "claim-policy/v1"
RELEASE = "release/v1"
TERMINAL_POLICY = "terminal-policy/v1"
SELECTION_POLICY = "selection-policy/v1"
RECOVERY_POLICY = "recovery-policy/v1"
TIMESTAMP = "2026-01-01T00:00:00Z"
PROCESS_INTENT_TIMESTAMP = "2026-01-01T00:00:30Z"
PROCESS_CREATED_TIMESTAMP = "2026-01-01T00:01:00Z"
RESUME_INTENT_TIMESTAMP = "2026-01-01T00:01:30Z"
PROCESS_FAILURE_TIMESTAMP = "2026-01-01T00:02:00Z"
MANUAL_REVIEW_TIMESTAMP = "2026-01-01T00:03:00Z"
TERMINAL_TIMESTAMP = "2026-01-01T00:04:00Z"
SELECTION_TIMESTAMP = "2026-01-01T00:05:00Z"
CLOSE_TIMESTAMP = "2026-01-01T00:06:00Z"
CAPTURE_REQUEST_FIELDS = frozenset(
    {
        "bar_interval",
        "child_operation_version",
        "ordered_universe",
        "output_policy_version",
        "permitted_provider_operation",
        "provider_id",
        "request_limit",
        "request_window_end_date",
        "request_window_start_date",
        "target_session_date",
    }
)
_RESUME_INTENT_ISSUER = object()
_PROCESS_INTENT_ISSUER = object()
_PROCESS_RESULT_ISSUER = object()
_ISSUED_RESUME_PERMITS_LOCK = threading.Lock()
_ISSUED_PROCESS_PERMITS_LOCK = threading.Lock()
_ISSUED_PROCESS_RESULTS_LOCK = threading.Lock()
_RESUME_LIFECYCLE_LOCKS_GUARD = threading.Lock()
_RESUME_LIFECYCLE_LOCKS: dict[str, threading.RLock] = {}


def _resume_lifecycle_lock(reservation_id: str) -> threading.RLock:
    with _RESUME_LIFECYCLE_LOCKS_GUARD:
        return _RESUME_LIFECYCLE_LOCKS.setdefault(reservation_id, threading.RLock())


@dataclass(eq=False)
class _ProcessPermit:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


@dataclass(eq=False)
class _ProcessResultPermit:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


@dataclass(eq=False)
class _ResumePermit:
    lock: threading.Lock = field(default_factory=threading.Lock)
    consumed: bool = False


_ISSUED_RESUME_PERMITS: set[_ResumePermit] = set()
_ISSUED_PROCESS_PERMITS: set[_ProcessPermit] = set()
_ISSUED_PROCESS_RESULTS: set[_ProcessResultPermit] = set()


@dataclass(frozen=True)
class FakeProcessIntent:
    """Opaque one-shot authority returned only by the intent transaction."""

    reservation_id: str
    intent_json: bytes
    intent_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ProcessPermit = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issuer is not _PROCESS_INTENT_ISSUER:
            raise TypeError("fake process intents can only be issued after commit")


@dataclass(frozen=True)
class FakeProcessCreationReceipt:
    """Canonical successful CreateProcessW and Job Object result."""

    reservation_id: str
    process_intent_digest: bytes
    process_json: bytes
    process_digest: bytes
    job_json: bytes
    job_digest: bytes
    resume_authorization_json: bytes
    resume_authorization_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ProcessResultPermit = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issuer is not _PROCESS_RESULT_ISSUER:
            raise TypeError("fake process receipts can only come from the adapter")


@dataclass(frozen=True)
class FakeProcessCreationFailure:
    """Canonical definitive CreateProcessW not-created result."""

    reservation_id: str
    process_intent_digest: bytes
    result_json: bytes
    result_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ProcessResultPermit = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issuer is not _PROCESS_RESULT_ISSUER:
            raise TypeError("fake process failures can only come from the adapter")


@dataclass(frozen=True)
class FakeResumeIntent:
    """Opaque one-shot authority returned only by the intent transaction."""

    execution_id: str
    intent_json: bytes
    intent_digest: bytes
    _issuer: object = field(repr=False, compare=False)
    _permit: _ResumePermit = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issuer is not _RESUME_INTENT_ISSUER:
            raise TypeError("fake resume intents can only be issued after commit")


@dataclass(frozen=True)
class FakeResumeReceipt:
    """Canonical result returned by the fake external ResumeThread boundary."""

    execution_id: str
    resume_intent_digest: bytes
    result_json: bytes
    result_digest: bytes


def test_fixed_authority_timestamps_are_causally_ordered() -> None:
    assert (
        TIMESTAMP
        < PROCESS_INTENT_TIMESTAMP
        < PROCESS_CREATED_TIMESTAMP
        < RESUME_INTENT_TIMESTAMP
        < PROCESS_FAILURE_TIMESTAMP
        < MANUAL_REVIEW_TIMESTAMP
        < TERMINAL_TIMESTAMP
        < SELECTION_TIMESTAMP
        < CLOSE_TIMESTAMP
    )


def test_authority_values_are_sourced_from_public_alpaca_descriptor() -> None:
    assert ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id == "alpaca-market-data"
    assert (
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
        == "historical-stock-bars-v2-raw-usd-no-asof"
    )
    assert (PROVIDER, OPERATION) == (
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
    )


def _frame(value: str) -> str:
    encoded = value.encode("utf-8")
    return f"{len(encoded)}:" + value


def _ordered_list(values: tuple[str, ...]) -> str:
    return _frame(str(len(values))) + "".join(_frame(value) for value in values)


def _identity(label: str, *values: str) -> str:
    material = _frame(label) + "".join(_frame(value) for value in values)
    return str(uuid.uuid5(NAMESPACE, material))


def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _evidence(label: str) -> tuple[bytes, bytes]:
    value = _json({"evidence": label, "schema": 1})
    return value, _digest(value)


def _insert_attempt_row_for_test(
    connection: sqlite3.Connection,
    session_id: str,
    ordinal: int,
    request_bytes: bytes,
    request_digest: bytes,
    *,
    attempt_policy_version: str | None = None,
    provider_id: str | None = None,
    permitted_provider_operation: str | None = None,
) -> str:
    parent = connection.execute(
        """
        SELECT s.claim_policy_version, m.provider_id,
               m.permitted_provider_operation
        FROM sessions s
        JOIN authority_metadata m
          ON m.authority_epoch_id = s.authority_epoch_id
        WHERE s.session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown raw attempt session")
    parent_policy, parent_provider, parent_operation = parent
    policy = parent_policy if attempt_policy_version is None else attempt_policy_version
    provider = parent_provider if provider_id is None else provider_id
    operation = (
        parent_operation
        if permitted_provider_operation is None
        else permitted_provider_operation
    )
    attempt_id = _attempt_id(session_id, ordinal, provider, operation, policy)
    allocation, allocation_digest = _evidence(f"raw-allocation:{ordinal}")
    attempt, attempt_digest = _evidence(f"raw-attempt:{ordinal}")
    connection.execute(
        """
        INSERT INTO attempts (
            attempt_id, session_id, ordinal, provider_id,
            permitted_provider_operation, provider_call_budget,
            request_json, request_digest, attempt_schema,
            attempt_policy_version, allocation_evidence_json,
            allocation_evidence_digest, attempt_evidence_json,
            attempt_evidence_digest, state, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1, ?, ?, ?, ?, ?, 'ALLOCATED', ?)
        """,
        (
            attempt_id,
            session_id,
            ordinal,
            provider,
            operation,
            request_bytes,
            request_digest,
            policy,
            allocation,
            allocation_digest,
            attempt,
            attempt_digest,
            TIMESTAMP,
        ),
    )
    return attempt_id


def _insert_claim_row_for_test(
    connection: sqlite3.Connection,
    attempt_id: str,
    request_bytes: bytes,
    request_digest: bytes,
    *,
    claim_policy_version: str | None = None,
) -> str:
    parent = connection.execute(
        """
        SELECT attempt_policy_version, provider_id,
               permitted_provider_operation, provider_call_budget
        FROM attempts WHERE attempt_id = ?
        """,
        (attempt_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown raw claim attempt")
    parent_policy, provider_id, operation, budget = parent
    policy = parent_policy if claim_policy_version is None else claim_policy_version
    claim_id = _claim_id(attempt_id, policy, provider_id, operation, budget)
    evidence, evidence_digest = _evidence(f"raw-claim:{attempt_id}")
    connection.execute(
        """
        INSERT INTO provider_call_claims (
            claim_id, attempt_id, claim_schema, claim_policy_version,
            provider_id, permitted_provider_operation, provider_call_budget,
            request_json, request_digest, claim_evidence_json,
            claim_evidence_digest, state, committed_at_utc
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 'COMMITTED', ?)
        """,
        (
            claim_id,
            attempt_id,
            policy,
            provider_id,
            operation,
            budget,
            request_bytes,
            request_digest,
            evidence,
            evidence_digest,
            TIMESTAMP,
        ),
    )
    return claim_id


def _insert_reservation_row_for_test(
    connection: sqlite3.Connection,
    claim_id: str,
    request_digest: bytes,
    reservation_state: str = "COMMITTED",
    failure_mode: bool = False,
    outcome_timestamp: str | None = None,
    *,
    authority_policy_version: str | None = None,
    claim_policy_version: str | None = None,
) -> str:
    parent = connection.execute(
        """
        SELECT c.claim_policy_version, s.authority_policy_version
        FROM provider_call_claims c
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE c.claim_id = ?
        """,
        (claim_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown raw reservation claim")
    parent_claim_policy, parent_authority_policy = parent
    claim_policy = (
        parent_claim_policy if claim_policy_version is None else claim_policy_version
    )
    authority_policy = (
        parent_authority_policy
        if authority_policy_version is None
        else authority_policy_version
    )
    reservation_id = _reservation_id(claim_id, RELEASE, authority_policy, claim_policy)
    evidence, evidence_digest = _evidence(f"raw-reservation:{claim_id}")
    failure = failure_digest = None
    if failure_mode:
        failure, failure_digest = _evidence(f"raw-failure:{claim_id}")
    connection.execute(
        """
        INSERT INTO launch_reservations (
            launch_reservation_id, claim_id, launch_reservation_schema,
            application_release_version, authority_policy_version,
            claim_policy_version, request_digest, reservation_evidence_json,
            reservation_evidence_digest, reservation_state,
            process_creation_failure_json, process_creation_failure_digest,
            committed_at_utc, outcome_recorded_at_utc
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            reservation_id,
            claim_id,
            RELEASE,
            authority_policy,
            claim_policy,
            request_digest,
            evidence,
            evidence_digest,
            reservation_state,
            failure,
            failure_digest,
            TIMESTAMP,
            outcome_timestamp,
        ),
    )
    return reservation_id


def _insert_terminal_row_for_test(
    connection: sqlite3.Connection,
    reservation_id: str,
    request_digest: bytes,
    state: str,
    disposition: str,
    snapshot_mode: str = "auto",
) -> str:
    terminal_id = _terminal_id(reservation_id, TERMINAL_POLICY)
    evidence, evidence_digest = _evidence(f"raw-terminal:{reservation_id}")
    diagnostics, diagnostics_digest = _evidence("raw-diagnostics")
    snapshot = (
        _digest(b"raw-snapshot")
        if snapshot_mode == "present"
        or (snapshot_mode == "auto" and state == "SUCCEEDED")
        else None
    )
    connection.execute(
        """
        INSERT INTO terminals (
            terminal_id, launch_reservation_id, terminal_schema,
            terminal_policy_version, terminal_state,
            provider_call_disposition, request_digest, evidence_json,
            evidence_digest, snapshot_digest, sanitized_diagnostics_json,
            sanitized_diagnostics_digest, recorded_at_utc
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            terminal_id,
            reservation_id,
            TERMINAL_POLICY,
            state,
            disposition,
            request_digest,
            evidence,
            evidence_digest,
            snapshot,
            diagnostics,
            diagnostics_digest,
            TERMINAL_TIMESTAMP,
        ),
    )
    return terminal_id


def _insert_execution_row_for_test(
    connection: sqlite3.Connection,
    reservation_id: str,
    *,
    authority_policy_version: str | None = None,
) -> str:
    parent = connection.execute(
        """
        SELECT application_release_version, authority_policy_version
        FROM launch_reservations WHERE launch_reservation_id = ?
        """,
        (reservation_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown raw execution reservation")
    application_release_version, parent_authority_policy = parent
    authority_policy = (
        parent_authority_policy
        if authority_policy_version is None
        else authority_policy_version
    )
    execution_id = _execution_id(
        reservation_id, application_release_version, authority_policy
    )
    process, process_digest = _evidence(f"raw-process:{reservation_id}")
    job, job_digest = _evidence(f"raw-job:{reservation_id}")
    resume, resume_digest = _evidence(f"raw-resume:{reservation_id}")
    connection.execute(
        """
        INSERT INTO launch_executions (
            launch_execution_id, launch_reservation_id, launch_schema,
            application_release_version, authority_policy_version, phase,
            process_creation_json, process_creation_digest, job_object_json,
            job_object_digest, resume_authorization_json,
            resume_authorization_digest, resume_intent_json,
            resume_intent_digest, resume_intent_committed_at_utc,
            post_resume_json, post_resume_digest, cleanup_json,
            cleanup_digest, created_at_utc
        ) VALUES (?, ?, 1, ?, ?, 'PRE_RESUME_READY', ?, ?, ?, ?, ?, ?,
                  NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)
        """,
        (
            execution_id,
            reservation_id,
            application_release_version,
            authority_policy,
            process,
            process_digest,
            job,
            job_digest,
            resume,
            resume_digest,
            TIMESTAMP,
        ),
    )
    return execution_id


def _request(target_date: str = "2026-01-01") -> dict[str, Any]:
    return {
        "bar_interval": "1d",
        "child_operation_version": "child/v1",
        "ordered_universe": ["QQQ", "SPY"],
        "output_policy_version": "output/v1",
        "permitted_provider_operation": OPERATION,
        "provider_id": PROVIDER,
        "request_limit": 2,
        "request_window_end_date": "2025-12-31",
        "request_window_start_date": "2025-12-01",
        "target_session_date": target_date,
    }


@dataclass(frozen=True, slots=True)
class ValidatedCaptureRequest:
    bar_interval: str
    child_operation_version: str
    ordered_universe: tuple[str, ...]
    output_policy_version: str
    permitted_provider_operation: str
    provider_id: str
    request_limit: int
    request_window_end_date: str
    request_window_start_date: str
    target_session_date: str

    def canonical_json(self) -> bytes:
        return _json(
            {
                "bar_interval": self.bar_interval,
                "child_operation_version": self.child_operation_version,
                "ordered_universe": list(self.ordered_universe),
                "output_policy_version": self.output_policy_version,
                "permitted_provider_operation": self.permitted_provider_operation,
                "provider_id": self.provider_id,
                "request_limit": self.request_limit,
                "request_window_end_date": self.request_window_end_date,
                "request_window_start_date": self.request_window_start_date,
                "target_session_date": self.target_session_date,
            }
        )


def _snapshot_capture_request(request: object) -> ValidatedCaptureRequest:
    if type(request) is not dict:
        raise ValueError("capture_request/v2 must be an exact object")
    captured = request.copy()
    if set(captured) != CAPTURE_REQUEST_FIELDS:
        raise ValueError("capture_request/v2 has a missing or unknown field")

    string_fields = CAPTURE_REQUEST_FIELDS - {"ordered_universe", "request_limit"}
    if any(type(captured[field]) is not str for field in string_fields):
        raise ValueError("capture_request/v2 string fields require exact strings")
    if type(captured["ordered_universe"]) is not list:
        raise ValueError("ordered_universe must be an exact list")
    captured_universe = tuple(captured["ordered_universe"])
    if not 1 <= len(captured_universe) <= MAX_DAILY_SNAPSHOT_SYMBOLS:
        raise ValueError("ordered_universe is empty or exceeds its bound")
    canonical_universe: list[str] = []
    for entry in captured_universe:
        if type(entry) is not str:
            raise ValueError("ordered_universe members must be exact strings")
        try:
            canonical_text = str(Symbol(entry))
        except (TypeError, ValueError) as error:
            raise ValueError("ordered_universe member is not a valid Symbol") from error
        canonical_universe.append(canonical_text)
    if len(set(canonical_universe)) != len(canonical_universe):
        raise ValueError("ordered_universe must be duplicate-free")
    if any(
        entry != canonical_text
        for entry, canonical_text in zip(
            captured_universe, canonical_universe, strict=True
        )
    ):
        raise ValueError("ordered_universe members must already be canonical Symbols")
    request_limit = captured["request_limit"]
    if type(request_limit) is not int or request_limit <= 0:
        raise ValueError("request_limit must be an exact positive integer")
    if (
        request_limit != len(canonical_universe)
        or request_limit > MAX_DAILY_SNAPSHOT_SYMBOLS
    ):
        raise ValueError("request_limit must equal the bounded universe size")

    for field_name in (
        "request_window_start_date",
        "request_window_end_date",
        "target_session_date",
    ):
        value = captured[field_name]
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{field_name} is not a canonical date") from error
        if parsed.isoformat() != value:
            raise ValueError(f"{field_name} is not a canonical date")
    window_start = date.fromisoformat(captured["request_window_start_date"])
    window_end = date.fromisoformat(captured["request_window_end_date"])
    target_session = date.fromisoformat(captured["target_session_date"])
    if not window_start <= window_end < target_session:
        raise ValueError("capture request dates are not causally ordered")

    fixed_values = {
        "bar_interval": "1d",
        "child_operation_version": "child/v1",
        "output_policy_version": "output/v1",
        "provider_id": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        "permitted_provider_operation": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
    }
    if any(captured[field] != value for field, value in fixed_values.items()):
        raise ValueError("capture_request/v2 fixed semantics are invalid")
    return ValidatedCaptureRequest(
        bar_interval=captured["bar_interval"],
        child_operation_version=captured["child_operation_version"],
        ordered_universe=tuple(canonical_universe),
        output_policy_version=captured["output_policy_version"],
        permitted_provider_operation=captured["permitted_provider_operation"],
        provider_id=captured["provider_id"],
        request_limit=request_limit,
        request_window_end_date=captured["request_window_end_date"],
        request_window_start_date=captured["request_window_start_date"],
        target_session_date=captured["target_session_date"],
    )


def _session_id(
    request: ValidatedCaptureRequest,
    *,
    machine_authority_id: str,
    authority_epoch_id: str,
    authority_policy_version: str,
    claim_policy_version: str,
) -> str:
    return _identity(
        "session_id/v2",
        machine_authority_id,
        authority_epoch_id,
        "1",
        authority_policy_version,
        claim_policy_version,
        "capture_request/v2",
        request.target_session_date,
        request.provider_id,
        request.permitted_provider_operation,
        _ordered_list(request.ordered_universe),
        request.bar_interval,
        request.request_window_start_date,
        request.request_window_end_date,
        str(request.request_limit),
        request.child_operation_version,
        request.output_policy_version,
    )


def _attempt_id(
    session_id: str,
    ordinal: int,
    provider_id: str,
    permitted_provider_operation: str,
    attempt_policy_version: str,
) -> str:
    return _identity(
        "attempt_id/v2",
        session_id,
        str(ordinal),
        provider_id,
        permitted_provider_operation,
        "1",
        attempt_policy_version,
    )


def _claim_id(
    attempt_id: str,
    claim_policy_version: str,
    provider_id: str,
    permitted_provider_operation: str,
    provider_call_budget: int,
) -> str:
    return _identity(
        "claim_id/v2",
        attempt_id,
        "1",
        claim_policy_version,
        provider_id,
        permitted_provider_operation,
        str(provider_call_budget),
    )


def _reservation_id(
    claim_id: str,
    application_release_version: str,
    authority_policy_version: str,
    claim_policy_version: str,
) -> str:
    return _identity(
        "launch_reservation_id/v2",
        claim_id,
        "1",
        application_release_version,
        authority_policy_version,
        claim_policy_version,
    )


def _execution_id(
    reservation_id: str,
    application_release_version: str,
    authority_policy_version: str,
) -> str:
    return _identity(
        "launch_execution_id/v2",
        reservation_id,
        "1",
        application_release_version,
        authority_policy_version,
    )


def _terminal_id(reservation_id: str, terminal_policy_version: str) -> str:
    return _identity("terminal_id/v2", reservation_id, "1", terminal_policy_version)


def _selection_id(
    session_id: str, terminal_id: str, selection_policy_version: str
) -> str:
    return _identity(
        "selection_id/v2",
        session_id,
        terminal_id,
        "1",
        selection_policy_version,
    )


def _recovery_id(
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    predecessor_state: str,
    resulting_state: str,
    ordinal: int,
    recovery_policy_version: str,
) -> str:
    return _identity(
        "recovery_id/v2",
        session_id,
        target_kind,
        target_id,
        action,
        predecessor_state,
        resulting_state,
        "1",
        recovery_policy_version,
        str(ordinal),
    )


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        path, timeout=5.0, isolation_level=None, check_same_thread=False
    )
    connection.create_function(
        "sha256",
        1,
        lambda value: hashlib.sha256(bytes(value)).digest(),
        deterministic=True,
    )
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _install_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute("PRAGMA foreign_keys = ON")


def _insert_metadata(
    connection: sqlite3.Connection,
    *,
    provider_id: str = PROVIDER,
    permitted_provider_operation: str = OPERATION,
    authority_policy_version: str = POLICY,
    claim_policy_version: str = CLAIM_POLICY,
) -> None:
    metadata = _json({"authority_epoch_id": EPOCH, "machine_authority_id": MACHINE})
    connection.execute(
        """
        INSERT INTO authority_metadata (
            authority_epoch_id, machine_authority_id, bootstrap_schema,
            bootstrap_generation, signing_key_id, approved_account_sid,
            provider_id, permitted_provider_operation, authority_policy_version,
            claim_policy_version, created_at_utc, bootstrap_digest,
            database_identity_digest, metadata_json, metadata_digest, singleton_key
        ) VALUES (?, ?, 1, 1, 'key/v1', 'S-1-5-21-test', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            EPOCH,
            MACHINE,
            provider_id,
            permitted_provider_operation,
            authority_policy_version,
            claim_policy_version,
            TIMESTAMP,
            _digest(b"bootstrap"),
            _digest(b"database"),
            metadata,
            _digest(metadata),
        ),
    )


def _insert_migration(connection: sqlite3.Connection) -> str:
    migration_id = _identity("migration_id/v1", EPOCH, "3", "migration-policy/v1")
    evidence, evidence_digest = _evidence("migration")
    connection.execute(
        """
        INSERT INTO schema_migrations (
            migration_id, authority_epoch_id, schema_version,
            migration_policy_version, migration_digest,
            application_release_digest, migration_json, applied_at_utc
        ) VALUES (?, ?, 3, 'migration-policy/v1', ?, ?, ?, ?)
        """,
        (
            migration_id,
            EPOCH,
            evidence_digest,
            _digest(b"release"),
            evidence,
            TIMESTAMP,
        ),
    )
    return migration_id


def _begin(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")


def _finish(connection: sqlite3.Connection, commit: bool) -> None:
    (connection.commit if commit else connection.rollback)()


def create_session(
    connection: sqlite3.Connection, request: dict[str, Any] | None = None
) -> str:
    snapshot = _snapshot_capture_request(_request() if request is None else request)
    _begin(connection)
    try:
        metadata = connection.execute(
            """
            SELECT authority_epoch_id, machine_authority_id, provider_id,
                   permitted_provider_operation, authority_policy_version,
                   claim_policy_version
            FROM authority_metadata
            WHERE singleton_key = 1
            """
        ).fetchone()
        if metadata is None:
            raise ValueError("authority metadata is missing")
        (
            authority_epoch_id,
            machine_authority_id,
            metadata_provider_id,
            metadata_operation,
            authority_policy_version,
            claim_policy_version,
        ) = metadata
        if authority_policy_version != POLICY:
            raise ValueError("authority policy is unsupported by this release")
        if claim_policy_version != CLAIM_POLICY:
            raise ValueError("claim policy is unsupported by this release")
        if (
            metadata_provider_id != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
            or metadata_operation != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
        ):
            raise ValueError("authority metadata does not match the Alpaca descriptor")
        request_provider_id = snapshot.provider_id
        request_operation = snapshot.permitted_provider_operation
        if request_provider_id != metadata_provider_id:
            raise ValueError("request provider_id does not match authority metadata")
        if request_operation != metadata_operation:
            raise ValueError(
                "request permitted_provider_operation does not match authority metadata"
            )
        request_bytes = snapshot.canonical_json()
        session_id = _session_id(
            snapshot,
            machine_authority_id=machine_authority_id,
            authority_epoch_id=authority_epoch_id,
            authority_policy_version=authority_policy_version,
            claim_policy_version=claim_policy_version,
        )
        connection.execute(
            """
            INSERT INTO sessions (
                session_id, authority_epoch_id, session_schema,
                authority_policy_version, claim_policy_version,
                target_session_date, state, next_attempt_ordinal,
                next_recovery_ordinal, request_json, request_digest,
                created_at_utc, closed_at_utc, close_reason
            ) VALUES (?, ?, 1, ?, ?, ?, 'OPEN', 0, 0, ?, ?, ?, NULL, NULL)
            """,
            (
                session_id,
                authority_epoch_id,
                authority_policy_version,
                claim_policy_version,
                snapshot.target_session_date,
                request_bytes,
                _digest(request_bytes),
                TIMESTAMP,
            ),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return session_id


def allocate_attempt(
    connection: sqlite3.Connection, session_id: str, ordinal: int | None = None
) -> str:
    _begin(connection)
    try:
        row = connection.execute(
            """
            SELECT s.next_attempt_ordinal, s.request_json, s.request_digest,
                   m.provider_id, m.permitted_provider_operation,
                   s.authority_policy_version, s.claim_policy_version,
                   m.authority_policy_version, m.claim_policy_version
            FROM sessions s
            JOIN authority_metadata m
              ON m.authority_epoch_id = s.authority_epoch_id
            WHERE s.session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown session")
        (
            current_ordinal,
            request_bytes,
            request_digest,
            provider_id,
            operation,
            authority_policy_version,
            claim_policy_version,
            metadata_authority_policy,
            metadata_claim_policy,
        ) = row
        if (
            authority_policy_version != metadata_authority_policy
            or claim_policy_version != metadata_claim_policy
        ):
            raise ValueError("session policy lineage does not match metadata")
        allocated_ordinal = current_ordinal if ordinal is None else ordinal
        attempt_id = _attempt_id(
            session_id,
            allocated_ordinal,
            provider_id,
            operation,
            claim_policy_version,
        )
        allocation_evidence, allocation_digest = _evidence(
            f"allocation:{allocated_ordinal}"
        )
        attempt_evidence, attempt_digest = _evidence(f"attempt:{allocated_ordinal}")
        connection.execute(
            """
            INSERT INTO attempts (
                attempt_id, session_id, ordinal, provider_id,
                permitted_provider_operation, provider_call_budget,
                request_json, request_digest, attempt_schema,
                attempt_policy_version, allocation_evidence_json,
                allocation_evidence_digest, attempt_evidence_json,
                attempt_evidence_digest, state, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1, ?, ?, ?, ?, ?, 'ALLOCATED', ?)
            """,
            (
                attempt_id,
                session_id,
                allocated_ordinal,
                provider_id,
                operation,
                request_bytes,
                request_digest,
                claim_policy_version,
                allocation_evidence,
                allocation_digest,
                attempt_evidence,
                attempt_digest,
                TIMESTAMP,
            ),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return attempt_id


def commit_claim(connection: sqlite3.Connection, attempt_id: str) -> str:
    evidence, evidence_digest = _evidence(f"claim:{attempt_id}")
    _begin(connection)
    try:
        attempt = connection.execute(
            """
            SELECT a.session_id, a.request_json, a.request_digest, a.provider_id,
                   a.permitted_provider_operation, a.provider_call_budget,
                   a.attempt_policy_version
            FROM attempts a WHERE attempt_id = ?
            """,
            (attempt_id,),
        ).fetchone()
        if attempt is None:
            raise ValueError("unknown attempt")
        (
            _,
            request_bytes,
            request_digest,
            provider_id,
            operation,
            budget,
            claim_policy_version,
        ) = attempt
        claim_id = _claim_id(
            attempt_id,
            claim_policy_version,
            provider_id,
            operation,
            budget,
        )
        connection.execute(
            """
            INSERT INTO provider_call_claims (
                claim_id, attempt_id, claim_schema, claim_policy_version,
                provider_id, permitted_provider_operation, provider_call_budget,
                request_json, request_digest, claim_evidence_json,
                claim_evidence_digest, state, committed_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 'COMMITTED', ?)
            """,
            (
                claim_id,
                attempt_id,
                claim_policy_version,
                provider_id,
                operation,
                budget,
                request_bytes,
                request_digest,
                evidence,
                evidence_digest,
                TIMESTAMP,
            ),
        )
        connection.execute(
            "UPDATE attempts SET state = 'CLAIM_COMMITTED' WHERE attempt_id = ?",
            (attempt_id,),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return claim_id


def reserve_launch(connection: sqlite3.Connection, claim_id: str) -> str:
    evidence, evidence_digest = _evidence(f"reservation:{claim_id}")
    _begin(connection)
    try:
        claim = connection.execute(
            """
            SELECT c.attempt_id, c.request_digest, c.claim_policy_version,
                   s.authority_policy_version
            FROM provider_call_claims c
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE c.claim_id = ?
            """,
            (claim_id,),
        ).fetchone()
        if claim is None:
            raise ValueError("unknown claim")
        attempt_id, request_digest, claim_policy_version, authority_policy_version = (
            claim
        )
        reservation_id = _reservation_id(
            claim_id,
            RELEASE,
            authority_policy_version,
            claim_policy_version,
        )
        connection.execute(
            """
            INSERT INTO launch_reservations (
                launch_reservation_id, claim_id, launch_reservation_schema,
                application_release_version, authority_policy_version,
                claim_policy_version, request_digest, reservation_evidence_json,
                reservation_evidence_digest, reservation_state,
                process_creation_failure_json, process_creation_failure_digest,
                committed_at_utc, outcome_recorded_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, 'COMMITTED', NULL, NULL, ?, NULL)
            """,
            (
                reservation_id,
                claim_id,
                RELEASE,
                authority_policy_version,
                claim_policy_version,
                request_digest,
                evidence,
                evidence_digest,
                TIMESTAMP,
            ),
        )
        connection.execute(
            "UPDATE attempts SET state = 'LAUNCH_RESERVED' WHERE attempt_id = ?",
            (attempt_id,),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return reservation_id


def _process_intent_json(
    reservation_id: str,
    request_digest: bytes,
    authority_policy_version: str,
    claim_policy_version: str,
) -> bytes:
    return _json(
        {
            "authority_policy_version": authority_policy_version,
            "claim_policy_version": claim_policy_version,
            "launch_reservation_id": reservation_id,
            "process_operation": "CreateProcessW",
            "request_digest": request_digest.hex(),
            "schema": 1,
        }
    )


def commit_process_intent(
    connection: sqlite3.Connection, reservation_id: str
) -> FakeProcessIntent:
    _begin(connection)
    try:
        row = connection.execute(
            """
            SELECT r.reservation_state, r.request_digest,
                   r.authority_policy_version, r.claim_policy_version,
                   r.reservation_evidence_json, r.reservation_evidence_digest,
                   c.state, c.request_json, c.request_digest,
                   c.claim_policy_version, c.claim_evidence_json,
                   c.claim_evidence_digest,
                   a.state, a.request_json, a.request_digest,
                   a.attempt_policy_version, a.provider_id,
                   a.permitted_provider_operation, a.provider_call_budget,
                   s.state, s.request_json, s.request_digest,
                   s.authority_policy_version, s.claim_policy_version,
                   m.provider_id, m.permitted_provider_operation,
                   m.authority_policy_version, m.claim_policy_version
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            JOIN authority_metadata m ON m.singleton_key = 1
            WHERE r.launch_reservation_id = ?
            """,
            (reservation_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown reservation")
        (
            reservation_state,
            request_digest,
            authority_policy_version,
            claim_policy_version,
            reservation_evidence,
            reservation_evidence_digest,
            claim_state,
            claim_request,
            claim_request_digest,
            claim_policy,
            claim_evidence,
            claim_evidence_digest,
            attempt_state,
            attempt_request,
            attempt_request_digest,
            attempt_policy,
            attempt_provider,
            attempt_operation,
            attempt_budget,
            session_state,
            session_request,
            session_request_digest,
            session_authority_policy,
            session_claim_policy,
            metadata_provider,
            metadata_operation,
            metadata_authority_policy,
            metadata_claim_policy,
        ) = row
        if reservation_state != "COMMITTED":
            raise ValueError("process intent requires COMMITTED")
        if (
            _digest(reservation_evidence) != reservation_evidence_digest
            or _digest(claim_evidence) != claim_evidence_digest
            or _digest(claim_request) != claim_request_digest
            or claim_request != attempt_request
            or claim_request != session_request
            or request_digest != claim_request_digest
            or request_digest != attempt_request_digest
            or request_digest != session_request_digest
        ):
            raise ValueError("process intent request or evidence binding is invalid")
        if (
            claim_state != "COMMITTED"
            or attempt_state != "LAUNCH_RESERVED"
            or session_state != "OPEN"
            or claim_policy_version != claim_policy
            or claim_policy != attempt_policy
            or claim_policy != session_claim_policy
            or claim_policy != metadata_claim_policy
            or authority_policy_version != session_authority_policy
            or authority_policy_version != metadata_authority_policy
            or attempt_provider != metadata_provider
            or attempt_provider != PROVIDER
            or attempt_operation != metadata_operation
            or attempt_operation != OPERATION
            or attempt_budget != 1
        ):
            raise ValueError("process intent policy or claim binding is invalid")
        intent_json = _process_intent_json(
            reservation_id,
            request_digest,
            authority_policy_version,
            claim_policy_version,
        )
        intent_digest = _digest(intent_json)
        cursor = connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'PROCESS_INTENT_COMMITTED',
                process_intent_json = ?, process_intent_digest = ?,
                process_intent_committed_at_utc = ?
            WHERE launch_reservation_id = ? AND reservation_state = 'COMMITTED'
            """,
            (intent_json, intent_digest, PROCESS_INTENT_TIMESTAMP, reservation_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("process intent ownership was not acquired")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    permit = _ProcessPermit()
    with _ISSUED_PROCESS_PERMITS_LOCK:
        _ISSUED_PROCESS_PERMITS.add(permit)
    return FakeProcessIntent(
        reservation_id=reservation_id,
        intent_json=intent_json,
        intent_digest=intent_digest,
        _issuer=_PROCESS_INTENT_ISSUER,
        _permit=permit,
    )


def _process_success_evidence(
    reservation_id: str, process_intent_digest: bytes
) -> tuple[bytes, bytes, bytes]:
    common = {
        "process_intent_digest": process_intent_digest.hex(),
        "reservation_id": reservation_id,
        "schema": 1,
    }
    return (
        _json({**common, "creation_result": "SUSPENDED_CHILD_CREATED"}),
        _json({**common, "job_object_result": "ASSIGNED"}),
        _json({**common, "resume_authorization": "SUSPENDED_THREAD_OWNED"}),
    )


def _process_failure_json(reservation_id: str, process_intent_digest: bytes) -> bytes:
    return _json(
        {
            "creation_result": "NOT_CREATED",
            "process_intent_digest": process_intent_digest.hex(),
            "reservation_id": reservation_id,
            "schema": 1,
        }
    )


def _require_issued_process_result(
    result: FakeProcessCreationReceipt | FakeProcessCreationFailure,
) -> None:
    if result._issuer is not _PROCESS_RESULT_ISSUER:
        raise TypeError("process result issuer is invalid")
    with result._permit.lock:
        with _ISSUED_PROCESS_RESULTS_LOCK:
            if result._permit.consumed or result._permit not in _ISSUED_PROCESS_RESULTS:
                raise ValueError("process result was already consumed or not issued")


def _consume_process_result(
    result: FakeProcessCreationReceipt | FakeProcessCreationFailure,
) -> None:
    with result._permit.lock:
        with _ISSUED_PROCESS_RESULTS_LOCK:
            if result._permit not in _ISSUED_PROCESS_RESULTS:
                raise ValueError("process result was already consumed or not issued")
            _ISSUED_PROCESS_RESULTS.remove(result._permit)
        result._permit.consumed = True


def record_execution(
    connection: sqlite3.Connection,
    reservation_id: str,
    receipt: FakeProcessCreationReceipt,
) -> str:
    if type(receipt) is not FakeProcessCreationReceipt:
        raise TypeError("record_execution requires a fake process creation receipt")
    if receipt.reservation_id != reservation_id:
        raise ValueError("process creation receipt belongs to another reservation")
    _require_issued_process_result(receipt)
    process, job, resume = _process_success_evidence(
        reservation_id, receipt.process_intent_digest
    )
    if (
        receipt.process_json != process
        or receipt.process_digest != _digest(process)
        or receipt.job_json != job
        or receipt.job_digest != _digest(job)
        or receipt.resume_authorization_json != resume
        or receipt.resume_authorization_digest != _digest(resume)
    ):
        raise ValueError("process creation receipt is not exact canonical evidence")
    _begin(connection)
    try:
        reservation = connection.execute(
            """
            SELECT application_release_version, authority_policy_version,
                   reservation_state, process_intent_json, process_intent_digest
            FROM launch_reservations WHERE launch_reservation_id = ?
            """,
            (reservation_id,),
        ).fetchone()
        if reservation is None:
            raise ValueError("unknown reservation")
        (
            application_release_version,
            authority_policy_version,
            reservation_state,
            intent_json,
            intent_digest,
        ) = reservation
        if reservation_state != "PROCESS_INTENT_COMMITTED":
            raise ValueError("execution requires PROCESS_INTENT_COMMITTED")
        if (
            intent_json is None
            or _digest(intent_json) != intent_digest
            or receipt.process_intent_digest != intent_digest
        ):
            raise ValueError("process creation receipt intent binding is invalid")
        execution_id = _execution_id(
            reservation_id,
            application_release_version,
            authority_policy_version,
        )
        connection.execute(
            """
            INSERT INTO launch_executions (
                launch_execution_id, launch_reservation_id, launch_schema,
                application_release_version, authority_policy_version, phase,
                process_creation_json, process_creation_digest, job_object_json,
                job_object_digest, resume_authorization_json,
                resume_authorization_digest, resume_intent_json,
                resume_intent_digest, resume_intent_committed_at_utc,
                post_resume_json, post_resume_digest, cleanup_json,
                cleanup_digest, created_at_utc
            ) VALUES (?, ?, 1, ?, ?, 'PRE_RESUME_READY', ?, ?, ?, ?, ?, ?,
                      NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)
            """,
            (
                execution_id,
                reservation_id,
                application_release_version,
                authority_policy_version,
                process,
                receipt.process_digest,
                job,
                receipt.job_digest,
                resume,
                receipt.resume_authorization_digest,
                PROCESS_CREATED_TIMESTAMP,
            ),
        )
        connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'PROCESS_CREATED', outcome_recorded_at_utc = ?
            WHERE launch_reservation_id = ?
            """,
            (PROCESS_CREATED_TIMESTAMP, reservation_id),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    _consume_process_result(receipt)
    return execution_id


def commit_resume_intent(
    connection: sqlite3.Connection, execution_id: str
) -> FakeResumeIntent:
    parent = connection.execute(
        "SELECT launch_reservation_id FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("cannot authorize resume for an unknown execution")
    with _resume_lifecycle_lock(parent[0]):
        return _commit_resume_intent_locked(connection, execution_id)


def _commit_resume_intent_locked(
    connection: sqlite3.Connection, execution_id: str
) -> FakeResumeIntent:
    intent_json = _json(
        {
            "execution_id": execution_id,
            "resume_operation": "ResumeThread",
            "schema": 1,
        }
    )
    intent_digest = _digest(intent_json)
    _begin(connection)
    try:
        row = connection.execute(
            """
            SELECT e.phase, e.process_creation_json, e.process_creation_digest,
                   e.job_object_json, e.job_object_digest,
                   e.resume_authorization_json, e.resume_authorization_digest,
                   r.reservation_state, s.state
            FROM launch_executions e
            JOIN launch_reservations r
              ON r.launch_reservation_id = e.launch_reservation_id
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE e.launch_execution_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
            """,
            (execution_id,),
        ).fetchone()
        if row is None:
            raise ValueError("resume intent active lineage is unavailable")
        if row[0] != "PRE_RESUME_READY":
            raise ValueError("resume intent requires PRE_RESUME_READY")
        if row[7] != "PROCESS_CREATED" or row[8] != "OPEN":
            raise ValueError("resume intent active parent lineage is revoked")
        for evidence_json, evidence_digest in (
            (row[1], row[2]),
            (row[3], row[4]),
            (row[5], row[6]),
        ):
            if evidence_json is None or _digest(evidence_json) != evidence_digest:
                raise ValueError("resume intent requires exact pre-resume evidence")
        cursor = connection.execute(
            """
            UPDATE launch_executions
            SET phase = 'RESUME_INTENT_COMMITTED', resume_intent_json = ?,
                resume_intent_digest = ?, resume_intent_committed_at_utc = ?
            WHERE launch_execution_id = ?
              AND phase = 'PRE_RESUME_READY'
              AND sha256(process_creation_json) IS process_creation_digest
              AND sha256(job_object_json) IS job_object_digest
              AND sha256(resume_authorization_json) IS resume_authorization_digest
              AND EXISTS (
                  SELECT 1
                  FROM launch_reservations r
                  JOIN provider_call_claims c ON c.claim_id = r.claim_id
                  JOIN attempts a ON a.attempt_id = c.attempt_id
                  JOIN sessions s ON s.session_id = a.session_id
                  WHERE r.launch_reservation_id =
                        launch_executions.launch_reservation_id
                    AND r.reservation_state = 'PROCESS_CREATED'
                    AND s.state = 'OPEN'
                    AND NOT EXISTS (
                        SELECT 1 FROM terminals t
                        WHERE t.launch_reservation_id = r.launch_reservation_id
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM session_selections ss
                        WHERE ss.session_id = s.session_id
                    )
              )
            """,
            (intent_json, intent_digest, RESUME_INTENT_TIMESTAMP, execution_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("resume intent ownership was not acquired")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    permit = _ResumePermit()
    with _ISSUED_RESUME_PERMITS_LOCK:
        _ISSUED_RESUME_PERMITS.add(permit)
    return FakeResumeIntent(
        execution_id=execution_id,
        intent_json=intent_json,
        intent_digest=intent_digest,
        _issuer=_RESUME_INTENT_ISSUER,
        _permit=permit,
    )


def record_process_creation_failure(
    connection: sqlite3.Connection,
    reservation_id: str,
    failure: FakeProcessCreationFailure,
) -> None:
    if type(failure) is not FakeProcessCreationFailure:
        raise TypeError(
            "record_process_creation_failure requires a fake process creation failure"
        )
    if failure.reservation_id != reservation_id:
        raise ValueError("process creation failure belongs to another reservation")
    _require_issued_process_result(failure)
    expected = _process_failure_json(reservation_id, failure.process_intent_digest)
    if failure.result_json != expected or failure.result_digest != _digest(expected):
        raise ValueError("process creation failure is not exact canonical evidence")
    _begin(connection)
    try:
        row = connection.execute(
            """
            SELECT reservation_state, process_intent_json, process_intent_digest
            FROM launch_reservations WHERE launch_reservation_id = ?
            """,
            (reservation_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown reservation")
        if (
            row[0] != "PROCESS_INTENT_COMMITTED"
            or row[1] is None
            or _digest(row[1]) != row[2]
            or failure.process_intent_digest != row[2]
        ):
            raise ValueError("process creation failure intent binding is invalid")
        connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'PROCESS_CREATION_FAILED',
                process_creation_failure_json = ?,
                process_creation_failure_digest = ?,
                outcome_recorded_at_utc = ?
            WHERE launch_reservation_id = ?
            """,
            (
                failure.result_json,
                failure.result_digest,
                PROCESS_FAILURE_TIMESTAMP,
                reservation_id,
            ),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    _consume_process_result(failure)


def record_post_resume_evidence(
    connection: sqlite3.Connection,
    execution_id: str,
    resume_receipt: FakeResumeReceipt,
) -> None:
    parent = connection.execute(
        "SELECT launch_reservation_id FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown launch execution")
    with _resume_lifecycle_lock(parent[0]):
        _record_post_resume_evidence_locked(connection, execution_id, resume_receipt)


def _record_post_resume_evidence_locked(
    connection: sqlite3.Connection,
    execution_id: str,
    resume_receipt: FakeResumeReceipt,
) -> None:
    if type(resume_receipt) is not FakeResumeReceipt:
        raise TypeError("post-resume evidence requires a fake resume receipt")
    if resume_receipt.execution_id != execution_id:
        raise ValueError("fake resume receipt belongs to another execution")
    cleanup, cleanup_digest = _evidence(f"cleanup:{execution_id}")
    if _digest(cleanup) != cleanup_digest:
        raise ValueError("cleanup evidence digest is invalid")
    _begin(connection)
    try:
        row = connection.execute(
            """
            SELECT e.phase, e.resume_intent_digest, e.resume_intent_json,
                   r.reservation_state, s.state
            FROM launch_executions e
            JOIN launch_reservations r
              ON r.launch_reservation_id = e.launch_reservation_id
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE e.launch_execution_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
            """,
            (execution_id,),
        ).fetchone()
        if row is None:
            raise ValueError("post-resume active lineage is unavailable")
        if row[0] != "RESUME_INTENT_COMMITTED":
            raise ValueError("post-resume evidence requires committed resume intent")
        if row[3] != "PROCESS_CREATED" or row[4] != "OPEN":
            raise ValueError("post-resume active parent lineage is revoked")
        if row[2] is None or _digest(row[2]) != row[1]:
            raise ValueError("post-resume committed intent evidence is invalid")
        if resume_receipt.resume_intent_digest != row[1]:
            raise ValueError("fake resume receipt binds another resume intent")
        expected_result = _json(
            {
                "execution_id": execution_id,
                "resume_intent_digest": row[1].hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        if resume_receipt.result_json != expected_result:
            raise ValueError("fake resume receipt is not the exact canonical success")
        if resume_receipt.result_digest != _digest(expected_result):
            raise ValueError("fake resume receipt digest is invalid")
        cursor = connection.execute(
            """
            UPDATE launch_executions
            SET phase = 'RESUME_RECORDED', post_resume_json = ?,
                post_resume_digest = ?, cleanup_json = ?, cleanup_digest = ?
            WHERE launch_execution_id = ?
              AND phase = 'RESUME_INTENT_COMMITTED'
              AND resume_intent_digest IS ?
              AND EXISTS (
                  SELECT 1
                  FROM launch_reservations r
                  JOIN provider_call_claims c ON c.claim_id = r.claim_id
                  JOIN attempts a ON a.attempt_id = c.attempt_id
                  JOIN sessions s ON s.session_id = a.session_id
                  WHERE r.launch_reservation_id =
                        launch_executions.launch_reservation_id
                    AND r.reservation_state = 'PROCESS_CREATED'
                    AND s.state = 'OPEN'
                    AND NOT EXISTS (
                        SELECT 1 FROM terminals t
                        WHERE t.launch_reservation_id = r.launch_reservation_id
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM session_selections ss
                        WHERE ss.session_id = s.session_id
                    )
              )
            """,
            (
                expected_result,
                resume_receipt.result_digest,
                cleanup,
                cleanup_digest,
                execution_id,
                row[1],
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("post-resume active lineage changed before persistence")
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise


def record_terminal(
    connection: sqlite3.Connection,
    reservation_id: str,
    state: str = "SUCCEEDED",
    disposition: str = "CONFIRMED",
) -> str:
    terminal_policy_version = TERMINAL_POLICY
    terminal_id = _terminal_id(reservation_id, terminal_policy_version)
    evidence, evidence_digest = _evidence(f"terminal:{reservation_id}")
    diagnostics, diagnostics_digest = _evidence("sanitized-diagnostics")
    snapshot = _digest(b"verified-snapshot") if state == "SUCCEEDED" else None
    _begin(connection)
    try:
        reservation = connection.execute(
            """
            SELECT claim_id, request_digest, reservation_state,
                   process_creation_failure_json, process_creation_failure_digest
            FROM launch_reservations WHERE launch_reservation_id = ?
            """,
            (reservation_id,),
        ).fetchone()
        if reservation is None:
            raise ValueError("unknown reservation")
        connection.execute(
            """
            INSERT INTO terminals (
                terminal_id, launch_reservation_id, terminal_schema,
                terminal_policy_version, terminal_state,
                provider_call_disposition, request_digest, evidence_json,
                evidence_digest, snapshot_digest, sanitized_diagnostics_json,
                sanitized_diagnostics_digest, recorded_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                terminal_id,
                reservation_id,
                terminal_policy_version,
                state,
                disposition,
                reservation[1],
                evidence,
                evidence_digest,
                snapshot,
                diagnostics,
                diagnostics_digest,
                TERMINAL_TIMESTAMP,
            ),
        )
        if reservation[2] != "MANUAL_REVIEW":
            connection.execute(
                """
                UPDATE launch_executions
                SET phase = 'TERMINAL_RECORDED'
                WHERE launch_reservation_id = ?
                """,
                (reservation_id,),
            )
        connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'TERMINAL_RECORDED'
            WHERE launch_reservation_id = ?
            """,
            (reservation_id,),
        )
        attempt_id = connection.execute(
            """
            SELECT c.attempt_id FROM provider_call_claims c
            JOIN launch_reservations r ON r.claim_id = c.claim_id
            WHERE r.launch_reservation_id = ?
            """,
            (reservation_id,),
        ).fetchone()[0]
        connection.execute(
            "UPDATE attempts SET state = 'TERMINAL_RECORDED' WHERE attempt_id = ?",
            (attempt_id,),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return terminal_id


def _insert_selection_in_transaction(
    connection: sqlite3.Connection, session_id: str, terminal_id: str
) -> str:
    snapshot = connection.execute(
        "SELECT snapshot_digest FROM terminals WHERE terminal_id = ?", (terminal_id,)
    ).fetchone()
    if snapshot is None or snapshot[0] is None:
        raise ValueError("terminal has no snapshot")
    selection_policy_version = SELECTION_POLICY
    selection_id = _selection_id(session_id, terminal_id, selection_policy_version)
    evidence, evidence_digest = _evidence(f"selection:{terminal_id}")
    connection.execute(
        """
        INSERT INTO session_selections (
            selection_id, session_id, terminal_id, selection_schema,
            selection_policy_version, snapshot_digest,
            selection_evidence_json, selection_evidence_digest,
            selected_at_utc
        ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
        """,
        (
            selection_id,
            session_id,
            terminal_id,
            selection_policy_version,
            snapshot[0],
            evidence,
            evidence_digest,
            SELECTION_TIMESTAMP,
        ),
    )
    attempt_id = connection.execute(
        """
        SELECT a.attempt_id
        FROM attempts a
        JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
        JOIN launch_reservations r ON r.claim_id = c.claim_id
        JOIN terminals t ON t.launch_reservation_id = r.launch_reservation_id
        WHERE t.terminal_id = ?
        """,
        (terminal_id,),
    ).fetchone()[0]
    connection.execute(
        "UPDATE attempts SET state = 'SUCCESS_SELECTED' WHERE attempt_id = ?",
        (attempt_id,),
    )
    connection.execute(
        "UPDATE sessions SET state = 'SUCCESS_SELECTED' WHERE session_id = ?",
        (session_id,),
    )
    return selection_id


def select_terminal(
    connection: sqlite3.Connection, session_id: str, terminal_id: str
) -> str:
    _begin(connection)
    try:
        selection_id = _insert_selection_in_transaction(
            connection, session_id, terminal_id
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return selection_id


def _target_state(
    connection: sqlite3.Connection, target_kind: str, target_id: str
) -> str:
    table, identity_column = {
        "SESSION": ("sessions", "session_id"),
        "ATTEMPT": ("attempts", "attempt_id"),
        "CLAIM": ("provider_call_claims", "claim_id"),
        "LAUNCH_RESERVATION": ("launch_reservations", "launch_reservation_id"),
        "TERMINAL": ("terminals", "terminal_id"),
    }[target_kind]
    state_column = {
        "SESSION": "state",
        "ATTEMPT": "state",
        "CLAIM": "state",
        "LAUNCH_RESERVATION": "reservation_state",
        "TERMINAL": "terminal_state",
    }[target_kind]
    row = connection.execute(
        f"SELECT {state_column} FROM {table} WHERE {identity_column} = ?", (target_id,)
    ).fetchone()
    if row is None:
        raise ValueError("unknown recovery target")
    return row[0]


_RECOVERY_ACTIONS: dict[str, tuple[str, str, str]] = {
    "RECORD_ATTEMPT_AMBIGUITY": (
        "ATTEMPT",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
    ),
    "RECORD_CLAIM_AMBIGUITY": (
        "CLAIM",
        "COMMITTED",
        "AMBIGUITY_RECORDED",
    ),
    "CLASSIFY_LAUNCH_RESERVATION": (
        "LAUNCH_RESERVATION",
        "COMMITTED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_PROCESS_OUTCOME_UNKNOWN": (
        "LAUNCH_RESERVATION",
        "PROCESS_INTENT_COMMITTED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_PRE_RESUME_READY": (
        "LAUNCH_RESERVATION",
        "PROCESS_CREATED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_RESUME_OUTCOME_UNKNOWN": (
        "LAUNCH_RESERVATION",
        "PROCESS_CREATED",
        "MANUAL_REVIEW",
    ),
    "SELECT_COMMITTED_SUCCESS": (
        "TERMINAL",
        "SUCCEEDED",
        "SUCCESS_SELECTED",
    ),
    "CLOSE_SESSION": ("SESSION", "OPEN", "CLOSED"),
    "ACKNOWLEDGE_RESTORE": (
        "SESSION",
        "OPEN",
        "RESTORE_ACKNOWLEDGED",
    ),
}


def record_recovery(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    ordinal: int | None = None,
) -> str:
    if target_kind == "LAUNCH_RESERVATION" and action.startswith("CLASSIFY_"):
        with _resume_lifecycle_lock(target_id):
            return _record_recovery_locked(
                connection,
                session_id,
                target_kind,
                target_id,
                action,
                ordinal,
            )
    return _record_recovery_locked(
        connection,
        session_id,
        target_kind,
        target_id,
        action,
        ordinal,
    )


def _record_recovery_locked(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    ordinal: int | None,
) -> str:
    _begin(connection)
    try:
        expected_kind, _, resulting = _RECOVERY_ACTIONS[action]
        if target_kind != expected_kind:
            raise ValueError("recovery action target kind is invalid")
        row = connection.execute(
            "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown recovery session")
        current_ordinal = row[0]
        recovery_ordinal = current_ordinal if ordinal is None else ordinal
        predecessor = _target_state(connection, target_kind, target_id)
        recovery_id = _recovery_id(
            session_id,
            target_kind,
            target_id,
            action,
            predecessor,
            resulting,
            recovery_ordinal,
            RECOVERY_POLICY,
        )
        evidence, evidence_digest = _evidence(f"recovery:{recovery_id}")
        recovery_timestamp = {
            "SELECT_COMMITTED_SUCCESS": SELECTION_TIMESTAMP,
            "CLOSE_SESSION": CLOSE_TIMESTAMP,
        }.get(action, MANUAL_REVIEW_TIMESTAMP)
        connection.execute(
            """
            INSERT INTO manual_recoveries (
                recovery_id, session_id, recovery_ordinal, target_kind,
                target_id, action, predecessor_state, resulting_state,
                recovery_schema, recovery_policy_version,
                operator_evidence_json, operator_evidence_digest,
                created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                recovery_id,
                session_id,
                recovery_ordinal,
                target_kind,
                target_id,
                action,
                predecessor,
                resulting,
                RECOVERY_POLICY,
                evidence,
                evidence_digest,
                recovery_timestamp,
            ),
        )
        if action in (
            "CLASSIFY_LAUNCH_RESERVATION",
            "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        ):
            connection.execute(
                """
                UPDATE launch_reservations
                SET reservation_state = 'MANUAL_REVIEW', outcome_recorded_at_utc = ?
                WHERE launch_reservation_id = ?
                """,
                (MANUAL_REVIEW_TIMESTAMP, target_id),
            )
        elif action in (
            "CLASSIFY_PRE_RESUME_READY",
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        ):
            connection.execute(
                """
                UPDATE launch_reservations
                SET reservation_state = 'MANUAL_REVIEW'
                WHERE launch_reservation_id = ?
                """,
                (target_id,),
            )
        elif action == "SELECT_COMMITTED_SUCCESS":
            _insert_selection_in_transaction(connection, session_id, target_id)
        elif action == "CLOSE_SESSION":
            connection.execute(
                """
                UPDATE sessions
                SET state = 'CLOSED', closed_at_utc = ?, close_reason = ?
                WHERE session_id = ?
                """,
                (CLOSE_TIMESTAMP, "recovery-approved-close", session_id),
            )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return recovery_id


class FakeSideEffects:
    """Test-only hooks that can observe committed authority facts."""

    def __init__(
        self,
        observer: sqlite3.Connection,
        events: list[str] | None = None,
        event_lock: threading.Lock | None = None,
    ) -> None:
        self.observer = observer
        self.events = [] if events is None else events
        self._event_lock = threading.Lock() if event_lock is None else event_lock

    def _emit(self, event: str) -> None:
        with self._event_lock:
            self.events.append(event)

    def construct_provider_after_claim(self, claim_id: str) -> None:
        assert self.observer.execute(
            "SELECT state FROM provider_call_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone() == ("COMMITTED",)
        self._emit("provider-constructed")

    def create_process(
        self, process_intent: FakeProcessIntent, *, fail: bool = False
    ) -> FakeProcessCreationReceipt | FakeProcessCreationFailure:
        if type(process_intent) is not FakeProcessIntent:
            raise TypeError("CreateProcessW requires an opaque fake process intent")
        if process_intent._issuer is not _PROCESS_INTENT_ISSUER:
            raise TypeError("CreateProcessW process intent issuer is invalid")
        reservation_id = process_intent.reservation_id
        row = self.observer.execute(
            """
            SELECT reservation_state, request_digest, authority_policy_version,
                   claim_policy_version, process_intent_json, process_intent_digest
            FROM launch_reservations WHERE launch_reservation_id = ?
            """,
            (reservation_id,),
        ).fetchone()
        if row is None:
            raise ValueError("CreateProcessW intent names an unknown reservation")
        expected_intent = _process_intent_json(reservation_id, row[1], row[2], row[3])
        if row[0] != "PROCESS_INTENT_COMMITTED":
            raise ValueError("CreateProcessW requires PROCESS_INTENT_COMMITTED")
        if (
            row[4] != process_intent.intent_json
            or row[5] != process_intent.intent_digest
            or process_intent.intent_json != expected_intent
            or process_intent.intent_digest != _digest(expected_intent)
        ):
            raise ValueError("CreateProcessW intent does not match durable authority")
        with process_intent._permit.lock:
            if process_intent._permit.consumed:
                raise ValueError("CreateProcessW process intent was already consumed")
            with _ISSUED_PROCESS_PERMITS_LOCK:
                if process_intent._permit not in _ISSUED_PROCESS_PERMITS:
                    raise ValueError(
                        "CreateProcessW process intent was not issued to this process"
                    )
                _ISSUED_PROCESS_PERMITS.remove(process_intent._permit)
            process_intent._permit.consumed = True

        self._emit("process-intent-committed")
        self._emit("create-process")
        result_permit = _ProcessResultPermit()
        with _ISSUED_PROCESS_RESULTS_LOCK:
            _ISSUED_PROCESS_RESULTS.add(result_permit)
        if fail:
            self._emit("process-creation-failed")
            result_json = _process_failure_json(
                reservation_id, process_intent.intent_digest
            )
            return FakeProcessCreationFailure(
                reservation_id=reservation_id,
                process_intent_digest=process_intent.intent_digest,
                result_json=result_json,
                result_digest=_digest(result_json),
                _issuer=_PROCESS_RESULT_ISSUER,
                _permit=result_permit,
            )
        self._emit("process-created")
        process_json, job_json, resume_json = _process_success_evidence(
            reservation_id, process_intent.intent_digest
        )
        return FakeProcessCreationReceipt(
            reservation_id=reservation_id,
            process_intent_digest=process_intent.intent_digest,
            process_json=process_json,
            process_digest=_digest(process_json),
            job_json=job_json,
            job_digest=_digest(job_json),
            resume_authorization_json=resume_json,
            resume_authorization_digest=_digest(resume_json),
            _issuer=_PROCESS_RESULT_ISSUER,
            _permit=result_permit,
        )

    def resume_thread(
        self, resume_intent: FakeResumeIntent, *, fail: bool = False
    ) -> FakeResumeReceipt:
        if type(resume_intent) is not FakeResumeIntent:
            raise TypeError("ResumeThread requires an opaque fake resume intent")
        parent = self.observer.execute(
            "SELECT launch_reservation_id FROM launch_executions "
            "WHERE launch_execution_id = ?",
            (resume_intent.execution_id,),
        ).fetchone()
        if parent is None:
            raise ValueError("cannot resume an unknown execution")
        with _resume_lifecycle_lock(parent[0]):
            return self._resume_thread_locked(resume_intent, fail=fail)

    def _resume_thread_locked(
        self, resume_intent: FakeResumeIntent, *, fail: bool
    ) -> FakeResumeReceipt:
        execution_id = resume_intent.execution_id
        row = self.observer.execute(
            """
            SELECT e.phase, e.process_creation_json, e.process_creation_digest,
                   e.job_object_json, e.job_object_digest,
                   e.resume_authorization_json, e.resume_authorization_digest,
                   e.resume_intent_json, e.resume_intent_digest,
                   r.reservation_state, s.state
            FROM launch_executions e
            JOIN launch_reservations r
              ON r.launch_reservation_id = e.launch_reservation_id
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE e.launch_execution_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
            """,
            (execution_id,),
        ).fetchone()
        if row is None:
            raise ValueError("ResumeThread active lineage is unavailable")
        if row[0] != "RESUME_INTENT_COMMITTED":
            raise ValueError("ResumeThread requires RESUME_INTENT_COMMITTED")
        if row[9] != "PROCESS_CREATED" or row[10] != "OPEN":
            raise ValueError("ResumeThread active parent lineage is revoked")
        for evidence_json, evidence_digest in (
            (row[1], row[2]),
            (row[3], row[4]),
            (row[5], row[6]),
        ):
            if evidence_json is None or evidence_digest != _digest(evidence_json):
                raise AssertionError("pre-resume evidence is not committed")
        if row[7] != resume_intent.intent_json or row[8] != resume_intent.intent_digest:
            raise ValueError("ResumeThread intent does not match committed authority")
        expected_intent = _json(
            {
                "execution_id": execution_id,
                "resume_operation": "ResumeThread",
                "schema": 1,
            }
        )
        if (
            resume_intent.intent_json != expected_intent
            or resume_intent.intent_digest != _digest(expected_intent)
        ):
            raise ValueError("ResumeThread intent is not canonical")
        with resume_intent._permit.lock:
            if resume_intent._permit.consumed:
                raise ValueError("ResumeThread intent was already consumed")
            with _ISSUED_RESUME_PERMITS_LOCK:
                if resume_intent._permit not in _ISSUED_RESUME_PERMITS:
                    raise ValueError(
                        "ResumeThread intent was not issued to this process"
                    )
                _ISSUED_RESUME_PERMITS.remove(resume_intent._permit)
            resume_intent._permit.consumed = True

        self._emit("resume-intent-committed")
        self._emit("resume-thread")
        if fail:
            self._emit("resume-thread-failed")
            raise RuntimeError("modeled ResumeThread failure")
        result_json = _json(
            {
                "execution_id": execution_id,
                "resume_intent_digest": resume_intent.intent_digest.hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        return FakeResumeReceipt(
            execution_id=execution_id,
            resume_intent_digest=resume_intent.intent_digest,
            result_json=result_json,
            result_digest=_digest(result_json),
        )

    def observe_post_resume_evidence(self, execution_id: str) -> None:
        assert (
            self.observer.execute(
                "SELECT phase, post_resume_json, post_resume_digest, cleanup_json, "
                "cleanup_digest FROM launch_executions "
                "WHERE launch_execution_id = ?",
                (execution_id,),
            ).fetchone()[0]
            == "RESUME_RECORDED"
        )
        self._emit("post-resume-evidence")

    def observe_terminal(self, reservation_id: str) -> None:
        assert (
            self.observer.execute(
                "SELECT terminal_id FROM terminals WHERE launch_reservation_id = ?",
                (reservation_id,),
            ).fetchone()
            is not None
        )
        self._emit("terminal")


def _create_process_receipt(
    connection: sqlite3.Connection, reservation_id: str
) -> FakeProcessCreationReceipt:
    intent = commit_process_intent(connection, reservation_id)
    result = FakeSideEffects(connection).create_process(intent)
    assert type(result) is FakeProcessCreationReceipt
    return result


def _record_successful_process(
    connection: sqlite3.Connection, reservation_id: str
) -> str:
    receipt = _create_process_receipt(connection, reservation_id)
    return record_execution(connection, reservation_id, receipt)


def _record_definitive_process_failure(
    connection: sqlite3.Connection, reservation_id: str
) -> None:
    intent = commit_process_intent(connection, reservation_id)
    result = FakeSideEffects(connection).create_process(intent, fail=True)
    assert type(result) is FakeProcessCreationFailure
    record_process_creation_failure(connection, reservation_id, result)


def _resume_and_persist(
    connection: sqlite3.Connection, execution_id: str
) -> FakeResumeReceipt:
    intent = commit_resume_intent(connection, execution_id)
    receipt = FakeSideEffects(connection).resume_thread(intent)
    record_post_resume_evidence(connection, execution_id, receipt)
    return receipt


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "authority.sqlite3"
    connection = _connect(path)
    _install_schema(connection)
    _insert_metadata(connection)
    _insert_migration(connection)
    connection.close()
    return path


@pytest.mark.parametrize(
    (
        "request_field",
        "request_value",
        "remove_field",
        "metadata_provider_id",
        "metadata_operation",
    ),
    [
        ("provider_id", "different-provider", False, PROVIDER, OPERATION),
        (
            "permitted_provider_operation",
            "different-operation",
            False,
            PROVIDER,
            OPERATION,
        ),
        (None, None, False, "different-provider", OPERATION),
        (None, None, False, PROVIDER, "different-operation"),
        ("provider_id", "", False, PROVIDER, OPERATION),
        ("permitted_provider_operation", "", False, PROVIDER, OPERATION),
        ("provider_id", "ALPACA_MARKET_DATA", False, PROVIDER, OPERATION),
        (
            "permitted_provider_operation",
            "HISTORICAL_DAILY_BARS",
            False,
            PROVIDER,
            OPERATION,
        ),
        ("provider_id", None, True, PROVIDER, OPERATION),
        ("permitted_provider_operation", None, True, PROVIDER, OPERATION),
        ("provider_id", 1, False, PROVIDER, OPERATION),
        ("permitted_provider_operation", [OPERATION], False, PROVIDER, OPERATION),
    ],
    ids=[
        "request-provider-mismatch",
        "request-operation-mismatch",
        "metadata-provider-mismatch",
        "metadata-operation-mismatch",
        "blank-provider",
        "blank-operation",
        "legacy-provider",
        "legacy-operation",
        "missing-provider",
        "missing-operation",
        "provider-wrong-type",
        "operation-wrong-type",
    ],
)
def test_session_creation_rejects_descriptor_drift_before_persistence(
    tmp_path: Path,
    request_field: str | None,
    request_value: object,
    remove_field: bool,
    metadata_provider_id: str,
    metadata_operation: str,
) -> None:
    path = tmp_path / "descriptor-drift.sqlite3"
    connection = _connect(path)
    _install_schema(connection)
    _insert_metadata(
        connection,
        provider_id=metadata_provider_id,
        permitted_provider_operation=metadata_operation,
    )
    _insert_migration(connection)
    side_effects = FakeSideEffects(connection)
    request = _request()
    if request_field is not None:
        if remove_field:
            del request[request_field]
        else:
            request[request_field] = request_value

    with pytest.raises(ValueError):
        create_session(connection, request)

    assert connection.execute(
        "SELECT count(*), coalesce(sum(next_attempt_ordinal), 0), "
        "coalesce(sum(next_recovery_ordinal), 0) FROM sessions"
    ).fetchone() == (0, 0, 0)
    assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (0,)
    assert side_effects.events == []
    connection.close()


def _assert_no_capture_authority_side_effects(
    connection: sqlite3.Connection,
) -> None:
    for table in (
        "sessions",
        "attempts",
        "provider_call_claims",
        "launch_reservations",
        "launch_executions",
        "terminals",
        "session_selections",
        "manual_recoveries",
    ):
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


def test_validated_capture_request_is_frozen_and_detached_from_caller() -> None:
    caller_request = _request()
    caller_universe = caller_request["ordered_universe"]
    assert type(caller_universe) is list
    snapshot = _snapshot_capture_request(caller_request)

    caller_universe.append("IWM")
    caller_request["ordered_universe"] = ["DIA"]
    caller_request["request_limit"] = 1
    caller_request["target_session_date"] = "2099-12-31"

    assert snapshot.ordered_universe == ("QQQ", "SPY")
    assert snapshot.request_limit == 2
    assert snapshot.target_session_date == "2026-01-01"
    assert snapshot.ordered_universe is not caller_universe
    assert not hasattr(snapshot, "__dict__")
    assert all(
        type(getattr(snapshot, field_name)) not in (dict, list)
        for field_name in snapshot.__dataclass_fields__
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.target_session_date = "2099-12-31"  # type: ignore[misc]


def test_capture_snapshot_recreates_existing_exact_canonical_json() -> None:
    snapshot = _snapshot_capture_request(_request())
    expected = (
        b'{"bar_interval":"1d","child_operation_version":"child/v1",'
        b'"ordered_universe":["QQQ","SPY"],"output_policy_version":"output/v1",'
        b'"permitted_provider_operation":"historical-stock-bars-v2-raw-usd-no-asof",'
        b'"provider_id":"alpaca-market-data","request_limit":2,'
        b'"request_window_end_date":"2025-12-31",'
        b'"request_window_start_date":"2025-12-01",'
        b'"target_session_date":"2026-01-01"}'
    )
    assert snapshot.canonical_json() == expected == _json(_request())


def test_caller_mutation_after_snapshot_cannot_desynchronize_session(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _connect(db_path)
    caller_request = _request()
    caller_universe = caller_request["ordered_universe"]
    assert type(caller_universe) is list
    snapshots: list[ValidatedCaptureRequest] = []
    snapshot_function = _snapshot_capture_request

    def snapshot_then_mutate(request: object) -> ValidatedCaptureRequest:
        snapshot = snapshot_function(request)
        snapshots.append(snapshot)
        assert type(request) is dict
        caller_universe.append("IWM")
        request["ordered_universe"] = ["DIA"]
        request["request_limit"] = 1
        request["target_session_date"] = "2099-12-31"
        return snapshot

    monkeypatch.setitem(globals(), "_snapshot_capture_request", snapshot_then_mutate)
    session_id = create_session(connection, caller_request)
    snapshot = snapshots[0]
    expected_bytes = snapshot.canonical_json()
    expected_id = _session_id(
        snapshot,
        machine_authority_id=MACHINE,
        authority_epoch_id=EPOCH,
        authority_policy_version=POLICY,
        claim_policy_version=CLAIM_POLICY,
    )
    assert session_id == expected_id
    assert connection.execute(
        "SELECT target_session_date, request_json, request_digest "
        "FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (
        snapshot.target_session_date,
        expected_bytes,
        _digest(expected_bytes),
    )
    assert caller_request != json.loads(expected_bytes)
    assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (0,)
    connection.close()


def test_capture_snapshot_accepts_canonical_period_and_hyphen_symbols() -> None:
    request = _request()
    request["ordered_universe"] = ["BRK.B", "ABC-1"]
    snapshot = _snapshot_capture_request(request)
    assert snapshot.ordered_universe == ("BRK.B", "ABC-1")
    assert json.loads(snapshot.canonical_json())["ordered_universe"] == [
        "BRK.B",
        "ABC-1",
    ]


def test_symbol_normalization_equivalence_is_detected_as_duplicate() -> None:
    request = _request()
    request["ordered_universe"] = ["SPY", "spy"]
    with pytest.raises(ValueError, match="duplicate-free"):
        _snapshot_capture_request(request)


@pytest.mark.parametrize(
    ("authority_policy_version", "claim_policy_version"),
    [
        ("authority-policy/v2", CLAIM_POLICY),
        (POLICY, "claim-policy/v2"),
    ],
    ids=["unsupported-authority-policy", "unsupported-claim-policy"],
)
def test_session_creation_rejects_unsupported_signed_policy_before_persistence(
    tmp_path: Path,
    authority_policy_version: str,
    claim_policy_version: str,
) -> None:
    path = tmp_path / "unsupported-policy.sqlite3"
    connection = _connect(path)
    _install_schema(connection)
    _insert_metadata(
        connection,
        authority_policy_version=authority_policy_version,
        claim_policy_version=claim_policy_version,
    )
    _insert_migration(connection)
    side_effects = FakeSideEffects(connection)

    with pytest.raises(ValueError, match="policy is unsupported"):
        create_session(connection)

    _assert_no_capture_authority_side_effects(connection)
    assert side_effects.events == []
    connection.close()


@pytest.mark.parametrize("missing_field", sorted(CAPTURE_REQUEST_FIELDS))
def test_capture_request_requires_every_exact_field(
    db_path: Path, missing_field: str
) -> None:
    connection = _connect(db_path)
    request = _request()
    del request[missing_field]
    with pytest.raises(ValueError):
        create_session(connection, request)
    _assert_no_capture_authority_side_effects(connection)
    connection.close()


def _invalid_capture_request(case: str) -> object:
    request: object = _request()
    assert isinstance(request, dict)
    if case == "not-exact-dict":
        return list(request.items())
    if case == "unknown-field":
        request["unknown"] = "value"
    elif case == "request-limit-string":
        request["request_limit"] = "2"
    elif case == "request-limit-bool":
        request["request_limit"] = True
    elif case == "request-limit-zero":
        request["request_limit"] = 0
    elif case == "request-limit-mismatch":
        request["request_limit"] = 1
    elif case == "tuple-universe":
        request["ordered_universe"] = ("QQQ", "SPY")
    elif case == "nonstring-universe-member":
        request["ordered_universe"] = ["QQQ", 1]
    elif case == "duplicate-universe":
        request["ordered_universe"] = ["QQQ", "QQQ"]
    elif case == "empty-universe":
        request["ordered_universe"] = []
        request["request_limit"] = 0
    elif case == "oversized-universe":
        request["ordered_universe"] = [
            f"SYM{index}" for index in range(MAX_DAILY_SNAPSHOT_SYMBOLS + 1)
        ]
        request["request_limit"] = MAX_DAILY_SNAPSHOT_SYMBOLS + 1
    elif case == "blank-universe-member":
        request["ordered_universe"] = ["QQQ", ""]
    elif case == "whitespace-universe-member":
        request["ordered_universe"] = ["QQQ", "   "]
    elif case == "lowercase-symbol":
        request["ordered_universe"] = ["QQQ", "spy"]
    elif case == "padded-symbol":
        request["ordered_universe"] = ["QQQ", " SPY "]
    elif case == "overlong-symbol":
        request["ordered_universe"] = ["QQQ", "ABCDEFGHIJK"]
    elif case == "unsupported-symbol-punctuation":
        request["ordered_universe"] = ["QQQ", "BRK_B"]
    elif case == "normalization-equivalent-symbols":
        request["ordered_universe"] = ["SPY", "spy"]
    elif case == "malformed-date":
        request["request_window_start_date"] = "2025-13-01"
    elif case == "noncanonical-date":
        request["target_session_date"] = "20260101"
    elif case == "window-reversed":
        request["request_window_start_date"] = "2026-01-01"
    elif case == "window-not-before-target":
        request["request_window_end_date"] = "2026-01-01"
    elif case.startswith("invalid-fixed-"):
        field_name = case.removeprefix("invalid-fixed-")
        request[field_name] = "invalid"
    elif case == "string-field-bool":
        request["bar_interval"] = True
    else:
        raise AssertionError(f"unhandled invalid capture request: {case}")
    return request


@pytest.mark.parametrize(
    "case",
    [
        "not-exact-dict",
        "unknown-field",
        "request-limit-string",
        "request-limit-bool",
        "request-limit-zero",
        "request-limit-mismatch",
        "tuple-universe",
        "nonstring-universe-member",
        "duplicate-universe",
        "empty-universe",
        "oversized-universe",
        "blank-universe-member",
        "whitespace-universe-member",
        "lowercase-symbol",
        "padded-symbol",
        "overlong-symbol",
        "unsupported-symbol-punctuation",
        "normalization-equivalent-symbols",
        "malformed-date",
        "noncanonical-date",
        "window-reversed",
        "window-not-before-target",
        "invalid-fixed-bar_interval",
        "invalid-fixed-child_operation_version",
        "invalid-fixed-output_policy_version",
        "invalid-fixed-provider_id",
        "invalid-fixed-permitted_provider_operation",
        "string-field-bool",
    ],
)
def test_capture_request_rejects_noncanonical_shapes_without_side_effects(
    db_path: Path, case: str
) -> None:
    connection = _connect(db_path)
    side_effects = FakeSideEffects(connection)
    with pytest.raises(ValueError):
        create_session(connection, _invalid_capture_request(case))  # type: ignore[arg-type]
    _assert_no_capture_authority_side_effects(connection)
    assert side_effects.events == []
    connection.close()


def test_invalid_alternate_request_cannot_collide_with_persisted_session(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    valid_request = _request()
    session_id = create_session(connection, valid_request)
    alternate = {**valid_request, "ordered_universe": ("QQQ", "SPY")}
    with pytest.raises(ValueError, match="exact list"):
        create_session(connection, alternate)  # type: ignore[arg-type]
    assert connection.execute(
        "SELECT session_id, request_json, next_attempt_ordinal, "
        "next_recovery_ordinal FROM sessions"
    ).fetchall() == [
        (
            session_id,
            _snapshot_capture_request(valid_request).canonical_json(),
            0,
            0,
        )
    ]
    connection.close()


def _seed_lifecycle(path: Path) -> dict[str, str]:
    connection = _connect(path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    _resume_and_persist(connection, execution_id)
    terminal_id = record_terminal(connection, reservation_id)
    connection.close()
    return {
        "session_id": session_id,
        "attempt_id": attempt_id,
        "claim_id": claim_id,
        "reservation_id": reservation_id,
        "execution_id": execution_id,
        "terminal_id": terminal_id,
    }


def test_complete_ddl_and_immediate_parent_chain(db_path: Path) -> None:
    connection = _connect(db_path)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert tables == {
        "authority_metadata",
        "schema_migrations",
        "sessions",
        "attempts",
        "provider_call_claims",
        "launch_reservations",
        "launch_executions",
        "terminals",
        "session_selections",
        "manual_recoveries",
    }
    parents = {
        "schema_migrations": "authority_metadata",
        "sessions": "authority_metadata",
        "attempts": "sessions",
        "provider_call_claims": "attempts",
        "launch_reservations": "provider_call_claims",
        "launch_executions": "launch_reservations",
        "terminals": "launch_reservations",
        "session_selections": "sessions,terminals",
        "manual_recoveries": "sessions",
    }
    for table, expected in parents.items():
        actual = {
            row[2] for row in connection.execute(f"PRAGMA foreign_key_list({table})")
        }
        assert actual == set(expected.split(","))
    execution_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(launch_executions)")
    }
    assert {
        "resume_intent_json",
        "resume_intent_digest",
        "resume_intent_committed_at_utc",
    } <= execution_columns
    assert connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'launch_executions_resume_intent_append_only'"
    ).fetchone() == (1,)
    reservation_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(launch_reservations)")
    }
    assert {
        "process_intent_json",
        "process_intent_digest",
        "process_intent_committed_at_utc",
    } <= reservation_columns
    assert connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'launch_reservations_process_intent_append_only'"
    ).fetchone() == (1,)
    policy_triggers = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' "
            "AND name IN ('sessions_before_insert', 'attempts_before_insert', "
            "'provider_call_claims_before_insert', "
            "'launch_reservations_before_insert', "
            "'launch_executions_parent_policy_before_insert')"
        )
    }
    assert policy_triggers == {
        "sessions_before_insert",
        "attempts_before_insert",
        "provider_call_claims_before_insert",
        "launch_reservations_before_insert",
        "launch_executions_parent_policy_before_insert",
    }
    connection.close()


def test_descendants_do_not_copy_ancestor_identity_columns(db_path: Path) -> None:
    connection = _connect(db_path)
    columns = {
        table: {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for table in (
            "provider_call_claims",
            "launch_reservations",
            "launch_executions",
            "terminals",
            "session_selections",
            "manual_recoveries",
        )
    }
    assert {"session_id", "authority_epoch_id", "ordinal"}.isdisjoint(
        columns["provider_call_claims"]
    )
    assert {
        "attempt_id",
        "session_id",
        "authority_epoch_id",
        "allocation_id",
    }.isdisjoint(columns["launch_reservations"])
    assert {
        "claim_id",
        "attempt_id",
        "session_id",
        "authority_epoch_id",
    }.isdisjoint(columns["launch_executions"])
    assert {
        "claim_id",
        "attempt_id",
        "session_id",
        "authority_epoch_id",
        "launch_execution_id",
    }.isdisjoint(columns["terminals"])
    assert {
        "claim_id",
        "attempt_id",
        "authority_epoch_id",
    }.isdisjoint(columns["session_selections"])
    assert {
        "target_allocation_id",
        "target_claim_id",
        "target_attempt_id",
        "target_epoch_id",
    }.isdisjoint(columns["manual_recoveries"])
    connection.close()


def test_identity_vectors_use_normalized_immediate_parent_material() -> None:
    request = _request()
    snapshot = _snapshot_capture_request(request)
    migration_id = _identity("migration_id/v1", EPOCH, "3", "migration-policy/v1")
    session_id = _session_id(
        snapshot,
        machine_authority_id=MACHINE,
        authority_epoch_id=EPOCH,
        authority_policy_version=POLICY,
        claim_policy_version=CLAIM_POLICY,
    )
    attempt_id = _attempt_id(session_id, 0, PROVIDER, OPERATION, CLAIM_POLICY)
    claim_id = _claim_id(attempt_id, CLAIM_POLICY, PROVIDER, OPERATION, 1)
    reservation_id = _reservation_id(claim_id, RELEASE, POLICY, CLAIM_POLICY)
    execution_id = _execution_id(reservation_id, RELEASE, POLICY)
    terminal_id = _terminal_id(reservation_id, TERMINAL_POLICY)
    selection_id = _selection_id(session_id, terminal_id, SELECTION_POLICY)
    recovery_id = _recovery_id(
        session_id,
        "ATTEMPT",
        attempt_id,
        "RECORD_ATTEMPT_AMBIGUITY",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
        0,
        RECOVERY_POLICY,
    )
    assert migration_id == "b1114fec-2247-506d-bfda-74008355b312"
    assert session_id == "80e64e2b-689f-5c0f-9076-bd251b55a9ee"
    assert attempt_id == "550d4a64-0306-5f15-a0ab-f65722c790a2"
    assert claim_id == "8a3ba04b-6548-577f-9773-2b30744b929f"
    assert reservation_id == "51e87e09-cea2-5828-8598-14dd053be048"
    assert execution_id == "f5727d7d-dd0b-50d8-8bf3-6ff2e44414e7"
    assert terminal_id == "bfee46cc-85a7-5fa7-88cd-0d5468dc51ef"
    assert selection_id == "f10c3fc1-49b0-554a-8fa7-d36fa4d1bee8"
    assert recovery_id == "9aaadbb2-62af-58db-af21-b5208551ec01"
    assert (
        _session_id(
            _snapshot_capture_request(_request()),
            machine_authority_id=MACHINE,
            authority_epoch_id=EPOCH,
            authority_policy_version=POLICY,
            claim_policy_version=CLAIM_POLICY,
        )
        == session_id
    )
    for field_name, value in (
        ("provider_id", "provider-drift"),
        ("permitted_provider_operation", "operation-drift"),
    ):
        drifted_request = {**request, field_name: value}
        with pytest.raises(ValueError):
            _snapshot_capture_request(drifted_request)
    assert (
        _session_id(
            snapshot,
            machine_authority_id=MACHINE,
            authority_epoch_id=EPOCH,
            authority_policy_version="authority-policy/drift",
            claim_policy_version=CLAIM_POLICY,
        )
        != session_id
    )
    assert (
        _session_id(
            snapshot,
            machine_authority_id=MACHINE,
            authority_epoch_id=EPOCH,
            authority_policy_version=POLICY,
            claim_policy_version="claim-policy/drift",
        )
        != session_id
    )
    assert (
        _attempt_id(session_id, 0, PROVIDER, OPERATION, "claim-policy/drift")
        != attempt_id
    )
    assert (
        _claim_id(attempt_id, "claim-policy/drift", PROVIDER, OPERATION, 1) != claim_id
    )
    assert (
        _reservation_id(claim_id, RELEASE, "authority-policy/drift", CLAIM_POLICY)
        != reservation_id
    )
    assert (
        _reservation_id(claim_id, RELEASE, POLICY, "claim-policy/drift")
        != reservation_id
    )
    assert (
        _execution_id(reservation_id, RELEASE, "authority-policy/drift") != execution_id
    )


def test_identity_helpers_require_explicit_persisted_policy_inputs() -> None:
    request = _snapshot_capture_request(_request())
    with pytest.raises(TypeError):
        _session_id(request)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _attempt_id("session", 0)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _claim_id("attempt")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _reservation_id("claim")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _execution_id("reservation")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _terminal_id("reservation")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _selection_id("session", "terminal")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _recovery_id(
            "session",
            "SESSION",
            "session",
            "ACKNOWLEDGE_RESTORE",
            "OPEN",
            "RESTORE_ACKNOWLEDGED",
            0,
        )  # type: ignore[call-arg]


def test_valid_lifecycle_from_metadata_to_selection(db_path: Path) -> None:
    connection = _connect(db_path)
    request = _request("2026-07-14")
    request.update(
        {
            "ordered_universe": ["DIA", "SPY", "QQQ"],
            "request_limit": 3,
        }
    )
    session_id = create_session(connection, request)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    _resume_and_persist(connection, execution_id)
    terminal_id = record_terminal(connection, reservation_id)
    selection_id = select_terminal(connection, session_id, terminal_id)
    expected_request = _snapshot_capture_request(request).canonical_json()
    expected_digest = _digest(expected_request)
    assert b"ALPACA_MARKET_DATA" not in expected_request
    assert b"HISTORICAL_DAILY_BARS" not in expected_request
    assert connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (expected_request, expected_digest)
    assert connection.execute(
        "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone() == (expected_request, expected_digest)
    assert connection.execute(
        "SELECT request_json, request_digest FROM provider_call_claims "
        "WHERE claim_id = ?",
        (claim_id,),
    ).fetchone() == (expected_request, expected_digest)
    assert connection.execute(
        "SELECT request_digest FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == (expected_digest,)
    assert connection.execute(
        "SELECT request_digest FROM terminals WHERE terminal_id = ?", (terminal_id,)
    ).fetchone() == (expected_digest,)
    assert connection.execute(
        "SELECT provider_id, permitted_provider_operation FROM authority_metadata"
    ).fetchone() == (PROVIDER, OPERATION)
    assert connection.execute(
        "SELECT provider_id, permitted_provider_operation FROM attempts "
        "WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone() == (PROVIDER, OPERATION)
    assert connection.execute(
        "SELECT provider_id, permitted_provider_operation FROM provider_call_claims "
        "WHERE claim_id = ?",
        (claim_id,),
    ).fetchone() == (PROVIDER, OPERATION)
    assert connection.execute(
        """
        SELECT m.authority_policy_version, m.claim_policy_version,
               s.authority_policy_version, s.claim_policy_version,
               a.attempt_policy_version, c.claim_policy_version,
               r.authority_policy_version, r.claim_policy_version,
               e.authority_policy_version
        FROM authority_metadata m
        JOIN sessions s ON s.authority_epoch_id = m.authority_epoch_id
        JOIN attempts a ON a.session_id = s.session_id
        JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
        JOIN launch_reservations r ON r.claim_id = c.claim_id
        JOIN launch_executions e
          ON e.launch_reservation_id = r.launch_reservation_id
        WHERE s.session_id = ?
        """,
        (session_id,),
    ).fetchone() == (
        POLICY,
        CLAIM_POLICY,
        POLICY,
        CLAIM_POLICY,
        CLAIM_POLICY,
        CLAIM_POLICY,
        POLICY,
        CLAIM_POLICY,
        POLICY,
    )
    assert connection.execute("SELECT state FROM sessions").fetchone() == (
        "SUCCESS_SELECTED",
    )
    assert connection.execute("SELECT state FROM attempts").fetchone() == (
        "SUCCESS_SELECTED",
    )
    assert connection.execute(
        "SELECT selection_id FROM session_selections"
    ).fetchone() == (selection_id,)
    terminal_recorded_at, selection_selected_at = connection.execute(
        """
        SELECT t.recorded_at_utc, ss.selected_at_utc
        FROM terminals t
        JOIN session_selections ss ON ss.terminal_id = t.terminal_id
        WHERE t.terminal_id = ?
        """,
        (terminal_id,),
    ).fetchone()
    assert (terminal_recorded_at, selection_selected_at) == (
        TERMINAL_TIMESTAMP,
        SELECTION_TIMESTAMP,
    )
    assert terminal_recorded_at <= selection_selected_at
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()


def test_immediate_parent_request_mismatches_are_rejected(db_path: Path) -> None:
    connection = _connect(db_path)
    request = _request("2026-07-15")
    session_id = create_session(connection, request)
    request_bytes = _snapshot_capture_request(request).canonical_json()
    request_digest = _digest(request_bytes)
    wrong_request = _json({**request, "request_limit": 99})
    wrong_digest = _digest(wrong_request)

    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_attempt_row_for_test(
            connection, session_id, 0, wrong_request, wrong_digest
        )
    connection.rollback()

    attempt_id = allocate_attempt(connection, session_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_claim_row_for_test(connection, attempt_id, wrong_request, wrong_digest)
    connection.rollback()

    claim_id = commit_claim(connection, attempt_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_reservation_row_for_test(connection, claim_id, wrong_digest)
    connection.rollback()

    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_reservation_row_for_test(
            connection, claim_id, request_digest, "PROCESS_CREATION_FAILED"
        )
    connection.rollback()

    reservation_id = reserve_launch(connection, claim_id)
    _record_definitive_process_failure(connection, reservation_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_terminal_row_for_test(
            connection,
            reservation_id,
            wrong_digest,
            "FAILED",
            "NOT_STARTED",
        )
    connection.rollback()
    assert connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (request_bytes, request_digest)
    connection.close()


def test_direct_sql_rejects_every_copied_parent_policy_drift(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    request_bytes, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()

    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_attempt_row_for_test(
            connection,
            session_id,
            0,
            request_bytes,
            request_digest,
            attempt_policy_version="claim-policy/drift",
        )
    connection.rollback()
    assert connection.execute(
        "SELECT next_attempt_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (0,)

    attempt_id = allocate_attempt(connection, session_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_claim_row_for_test(
            connection,
            attempt_id,
            request_bytes,
            request_digest,
            claim_policy_version="claim-policy/drift",
        )
    connection.rollback()

    claim_id = commit_claim(connection, attempt_id)
    for authority_policy, claim_policy in (
        ("authority-policy/drift", CLAIM_POLICY),
        (POLICY, "claim-policy/drift"),
    ):
        _begin(connection)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_reservation_row_for_test(
                connection,
                claim_id,
                request_digest,
                authority_policy_version=authority_policy,
                claim_policy_version=claim_policy,
            )
        connection.rollback()

    reservation_id = reserve_launch(connection, claim_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_execution_row_for_test(
            connection,
            reservation_id,
            authority_policy_version="authority-policy/drift",
        )
    connection.rollback()
    assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (1,)
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    assert connection.execute(
        "SELECT count(*) FROM launch_reservations"
    ).fetchone() == (1,)
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )
    connection.close()


def test_descendant_helpers_ignore_reset_release_constants_after_session_commit(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    monkeypatch.setitem(globals(), "POLICY", "authority-policy/reset")
    monkeypatch.setitem(globals(), "CLAIM_POLICY", "claim-policy/reset")

    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)

    assert connection.execute(
        """
        SELECT a.attempt_policy_version, c.claim_policy_version,
               r.authority_policy_version, r.claim_policy_version,
               e.authority_policy_version
        FROM attempts a
        JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
        JOIN launch_reservations r ON r.claim_id = c.claim_id
        JOIN launch_executions e
          ON e.launch_reservation_id = r.launch_reservation_id
        WHERE a.attempt_id = ?
        """,
        (attempt_id,),
    ).fetchone() == (
        "claim-policy/v1",
        "claim-policy/v1",
        "authority-policy/v1",
        "claim-policy/v1",
        "authority-policy/v1",
    )
    assert claim_id and reservation_id and execution_id
    connection.close()


def test_process_creation_failure_can_record_terminal_without_execution(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    _record_definitive_process_failure(connection, reservation_id)
    terminal_id = record_terminal(connection, reservation_id, "FAILED", "NOT_STARTED")
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )
    assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (1,)
    assert connection.execute(
        "SELECT terminal_id FROM terminals WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == (terminal_id,)
    connection.close()


@pytest.mark.parametrize(
    ("state", "disposition", "preparation", "valid", "snapshot_mode"),
    [
        ("SUCCEEDED", "CONFIRMED", "resumed", True, "auto"),
        ("FAILED", "NOT_STARTED", "process_failure", True, "auto"),
        ("FAILED", "CONFIRMED", "resumed", True, "auto"),
        ("AMBIGUOUS", "MAY_HAVE_OCCURRED", "resumed", True, "auto"),
        ("CLOSED", "MAY_HAVE_OCCURRED", "manual_review", True, "auto"),
        ("AMBIGUOUS", "NOT_STARTED", "resumed", False, "auto"),
        ("AMBIGUOUS", "CONFIRMED", "resumed", False, "auto"),
        ("SUCCEEDED", "CONFIRMED", "resumed", False, "none"),
        ("FAILED", "NOT_STARTED", "process_failure", False, "present"),
        ("FAILED", "MAY_HAVE_OCCURRED", "process_failure", False, "none"),
        ("CLOSED", "CONFIRMED", "manual_review", False, "none"),
    ],
)
def test_terminal_state_disposition_matrix(
    db_path: Path,
    state: str,
    disposition: str,
    preparation: str,
    valid: bool,
    snapshot_mode: str,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if preparation == "resumed":
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id)
    elif preparation == "process_failure":
        _record_definitive_process_failure(connection, reservation_id)
    else:
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_LAUNCH_RESERVATION",
        )

    if valid:
        terminal_id = record_terminal(connection, reservation_id, state, disposition)
        assert connection.execute(
            "SELECT terminal_state, provider_call_disposition, snapshot_digest "
            "FROM terminals WHERE terminal_id = ?",
            (terminal_id,),
        ).fetchone()[:2] == (state, disposition)
    else:
        request_digest = connection.execute(
            "SELECT request_digest FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone()[0]
        _begin(connection)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_terminal_row_for_test(
                connection,
                reservation_id,
                request_digest,
                state,
                disposition,
                snapshot_mode,
            )
        connection.rollback()
    connection.close()


def test_recovery_action_matrix_allows_documented_actions(db_path: Path) -> None:
    connection = _connect(db_path)

    claim_session = create_session(connection)
    claim_attempt = allocate_attempt(connection, claim_session)
    claim_id = commit_claim(connection, claim_attempt)
    claim_reservation = reserve_launch(connection, claim_id)
    claim_execution = _record_successful_process(connection, claim_reservation)
    _resume_and_persist(connection, claim_execution)
    claim_recovery = record_recovery(
        connection,
        claim_session,
        "CLAIM",
        claim_id,
        "RECORD_CLAIM_AMBIGUITY",
    )
    assert connection.execute(
        "SELECT state FROM provider_call_claims WHERE claim_id = ?", (claim_id,)
    ).fetchone() == ("COMMITTED",)
    assert connection.execute(
        "SELECT resulting_state FROM manual_recoveries WHERE recovery_id = ?",
        (claim_recovery,),
    ).fetchone() == ("AMBIGUITY_RECORDED",)

    review_session = create_session(connection, _request("2026-01-02"))
    review_attempt = allocate_attempt(connection, review_session)
    review_claim = commit_claim(connection, review_attempt)
    review_reservation = reserve_launch(connection, review_claim)
    review_recovery = record_recovery(
        connection,
        review_session,
        "LAUNCH_RESERVATION",
        review_reservation,
        "CLASSIFY_LAUNCH_RESERVATION",
    )
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (review_reservation,),
    ).fetchone() == ("MANUAL_REVIEW",)
    assert review_recovery

    select_session = create_session(connection, _request("2026-01-03"))
    select_attempt = allocate_attempt(connection, select_session)
    select_claim = commit_claim(connection, select_attempt)
    select_reservation = reserve_launch(connection, select_claim)
    select_execution = _record_successful_process(connection, select_reservation)
    _resume_and_persist(connection, select_execution)
    select_terminal = record_terminal(connection, select_reservation)
    select_recovery = record_recovery(
        connection,
        select_session,
        "TERMINAL",
        select_terminal,
        "SELECT_COMMITTED_SUCCESS",
    )
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (select_session,)
    ).fetchone() == ("SUCCESS_SELECTED",)
    assert connection.execute(
        "SELECT terminal_id FROM session_selections WHERE session_id = ?",
        (select_session,),
    ).fetchone() == (select_terminal,)
    terminal_recorded_at, recovery_created_at, selection_selected_at = (
        connection.execute(
            """
            SELECT t.recorded_at_utc, mr.created_at_utc, ss.selected_at_utc
            FROM terminals t
            JOIN manual_recoveries mr ON mr.target_id = t.terminal_id
            JOIN session_selections ss ON ss.terminal_id = t.terminal_id
            WHERE t.terminal_id = ?
              AND mr.action = 'SELECT_COMMITTED_SUCCESS'
            """,
            (select_terminal,),
        ).fetchone()
    )
    assert (terminal_recorded_at, recovery_created_at, selection_selected_at) == (
        TERMINAL_TIMESTAMP,
        SELECTION_TIMESTAMP,
        SELECTION_TIMESTAMP,
    )
    assert terminal_recorded_at <= selection_selected_at
    assert select_recovery

    close_session = create_session(connection, _request("2026-01-04"))
    close_recovery = record_recovery(
        connection,
        close_session,
        "SESSION",
        close_session,
        "CLOSE_SESSION",
    )
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (close_session,)
    ).fetchone() == ("CLOSED",)
    assert close_recovery

    restore_session = create_session(connection, _request("2026-01-05"))
    restore_recovery = record_recovery(
        connection,
        restore_session,
        "SESSION",
        restore_session,
        "ACKNOWLEDGE_RESTORE",
    )
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (restore_session,)
    ).fetchone() == ("OPEN",)
    assert restore_recovery
    connection.close()


def test_one_to_one_parent_fences(db_path: Path) -> None:
    values = _seed_lifecycle(db_path)
    connection = _connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        commit_claim(connection, values["attempt_id"])
    with pytest.raises(sqlite3.IntegrityError):
        reserve_launch(connection, values["claim_id"])
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        _record_successful_process(connection, values["reservation_id"])
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(connection, values["reservation_id"])
    select_terminal(connection, values["session_id"], values["terminal_id"])
    with pytest.raises(sqlite3.IntegrityError):
        select_terminal(connection, values["session_id"], values["terminal_id"])
    second_session = create_session(connection, _request("2026-01-02"))
    with pytest.raises(sqlite3.IntegrityError):
        select_terminal(connection, second_session, values["terminal_id"])
    connection.close()


def test_selection_and_recovery_lineage_is_session_scoped(db_path: Path) -> None:
    connection = _connect(db_path)
    first_session = create_session(connection)
    first_attempt = allocate_attempt(connection, first_session)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = reserve_launch(connection, first_claim)
    first_execution = _record_successful_process(connection, first_reservation)
    _resume_and_persist(connection, first_execution)
    first_terminal = record_terminal(connection, first_reservation)
    second_session = create_session(connection, _request("2026-01-02"))
    second_attempt = allocate_attempt(connection, second_session)
    second_claim = commit_claim(connection, second_attempt)
    second_reservation = reserve_launch(connection, second_claim)
    second_execution = _record_successful_process(connection, second_reservation)
    _resume_and_persist(connection, second_execution)
    second_terminal = record_terminal(connection, second_reservation)
    with pytest.raises(sqlite3.IntegrityError):
        select_terminal(connection, second_session, first_terminal)
    for target_kind, target_id, action in (
        ("SESSION", second_session, "CLOSE_SESSION"),
        ("ATTEMPT", second_attempt, "RECORD_ATTEMPT_AMBIGUITY"),
        ("CLAIM", second_claim, "RECORD_CLAIM_AMBIGUITY"),
        ("LAUNCH_RESERVATION", second_reservation, "CLASSIFY_LAUNCH_RESERVATION"),
        ("TERMINAL", second_terminal, "SELECT_COMMITTED_SUCCESS"),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            record_recovery(
                connection,
                first_session,
                target_kind,
                target_id,
                action,
            )
    assert first_execution != second_execution
    connection.close()


def test_attempt_ordinal_trigger_is_single_insert_and_atomic(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    with pytest.raises(sqlite3.IntegrityError):
        allocate_attempt(connection, session_id, ordinal=1)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET next_attempt_ordinal = 1 WHERE session_id = ?",
            (session_id,),
        )
    _begin(connection)
    request_bytes, request_digest, provider_id, operation, attempt_policy = (
        connection.execute(
            """
            SELECT s.request_json, s.request_digest, m.provider_id,
                   m.permitted_provider_operation, s.claim_policy_version
            FROM sessions s
            JOIN authority_metadata m
              ON m.authority_epoch_id = s.authority_epoch_id
            WHERE s.session_id = ?
            """,
            (session_id,),
        ).fetchone()
    )
    attempt_id = _attempt_id(session_id, 0, provider_id, operation, attempt_policy)
    allocation, allocation_digest = _evidence("rollback-allocation")
    attempt, attempt_digest = _evidence("rollback-attempt")
    connection.execute(
        """
        INSERT INTO attempts (
            attempt_id, session_id, ordinal, provider_id,
            permitted_provider_operation, provider_call_budget,
            request_json, request_digest, attempt_schema,
            attempt_policy_version, allocation_evidence_json,
            allocation_evidence_digest, attempt_evidence_json,
            attempt_evidence_digest, state, created_at_utc
        ) VALUES (?, ?, 0, ?, ?, 1, ?, ?, 1, ?, ?, ?, ?, ?, 'ALLOCATED', ?)
        """,
        (
            attempt_id,
            session_id,
            provider_id,
            operation,
            request_bytes,
            request_digest,
            attempt_policy,
            allocation,
            allocation_digest,
            attempt,
            attempt_digest,
            TIMESTAMP,
        ),
    )
    connection.rollback()
    assert connection.execute(
        "SELECT next_attempt_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (0,)
    assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
    committed_attempt = allocate_attempt(connection, session_id)
    assert committed_attempt == attempt_id
    assert connection.execute(
        "SELECT next_attempt_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (1,)
    with pytest.raises(sqlite3.IntegrityError):
        allocate_attempt(connection, session_id, ordinal=0)
    with pytest.raises(sqlite3.IntegrityError):
        allocate_attempt(connection, session_id, ordinal=2)
    connection.close()


def test_attempt_ordinals_serialize_across_connections_and_sessions(
    db_path: Path,
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    second_session = create_session(setup, _request("2026-01-02"))
    setup.close()
    barrier = threading.Barrier(2)
    results: list[tuple[str, int]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        connection = _connect(db_path)
        try:
            barrier.wait()
            attempt_id = allocate_attempt(connection, session_id)
            ordinal = connection.execute(
                "SELECT ordinal FROM attempts WHERE attempt_id = ?", (attempt_id,)
            ).fetchone()[0]
            with lock:
                results.append((attempt_id, ordinal))
        except BaseException as error:
            with lock:
                errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert sorted(ordinal for _, ordinal in results) == [0, 1]
    second_connection = _connect(db_path)
    assert allocate_attempt(second_connection, second_session) == _attempt_id(
        second_session, 0, PROVIDER, OPERATION, CLAIM_POLICY
    )
    second_connection.close()


def test_recovery_ordinal_trigger_is_atomic_and_session_local(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    target_attempt = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, target_attempt)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    _resume_and_persist(connection, execution_id)
    first_recovery = record_recovery(
        connection,
        session_id,
        "ATTEMPT",
        target_attempt,
        "RECORD_ATTEMPT_AMBIGUITY",
    )
    assert first_recovery == _recovery_id(
        session_id,
        "ATTEMPT",
        target_attempt,
        "RECORD_ATTEMPT_AMBIGUITY",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
        0,
        RECOVERY_POLICY,
    )
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "SESSION",
            session_id,
            "ACKNOWLEDGE_RESTORE",
            ordinal=0,
        )
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "SESSION",
            session_id,
            "ACKNOWLEDGE_RESTORE",
            ordinal=2,
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET next_recovery_ordinal = 3 WHERE session_id = ?",
            (session_id,),
        )
    _begin(connection)
    recovery_id = _recovery_id(
        session_id,
        "SESSION",
        session_id,
        "ACKNOWLEDGE_RESTORE",
        "OPEN",
        "RESTORE_ACKNOWLEDGED",
        1,
        RECOVERY_POLICY,
    )
    evidence, evidence_digest = _evidence("rollback-recovery")
    connection.execute(
        """
        INSERT INTO manual_recoveries (
            recovery_id, session_id, recovery_ordinal, target_kind, target_id,
            action, predecessor_state, resulting_state, recovery_schema,
            recovery_policy_version, operator_evidence_json,
            operator_evidence_digest, created_at_utc
        ) VALUES (?, ?, 1, 'SESSION', ?, 'ACKNOWLEDGE_RESTORE',
                  'OPEN', 'RESTORE_ACKNOWLEDGED', 1, ?, ?, ?, ?)
        """,
        (
            recovery_id,
            session_id,
            session_id,
            RECOVERY_POLICY,
            evidence,
            evidence_digest,
            TIMESTAMP,
        ),
    )
    connection.rollback()
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (1,)
    assert connection.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
        1,
    )
    second_recovery = record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "ACKNOWLEDGE_RESTORE",
    )
    assert second_recovery != first_recovery
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (2,)
    second_session = create_session(connection, _request("2026-01-02"))
    second_recovery = record_recovery(
        connection,
        second_session,
        "SESSION",
        second_session,
        "ACKNOWLEDGE_RESTORE",
    )
    assert second_recovery != first_recovery
    assert connection.execute(
        "SELECT recovery_ordinal FROM manual_recoveries WHERE session_id = ?",
        (second_session,),
    ).fetchone() == (0,)
    connection.close()


def test_recovery_after_absorbing_session_state_fails(db_path: Path) -> None:
    values = _seed_lifecycle(db_path)
    connection = _connect(db_path)
    select_terminal(connection, values["session_id"], values["terminal_id"])
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        record_recovery(
            connection,
            values["session_id"],
            "SESSION",
            values["session_id"],
            "CLOSE_SESSION",
        )
    connection.close()


def test_claim_and_launch_boundaries_commit_before_fake_side_effects(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    observer = _connect(db_path)
    hooks = FakeSideEffects(observer)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    hooks.construct_provider_after_claim(claim_id)
    reservation_id = reserve_launch(connection, claim_id)
    process_intent = commit_process_intent(connection, reservation_id)
    process_receipt = hooks.create_process(process_intent)
    assert type(process_receipt) is FakeProcessCreationReceipt
    execution_id = record_execution(connection, reservation_id, process_receipt)
    resume_intent = commit_resume_intent(connection, execution_id)
    resume_receipt = hooks.resume_thread(resume_intent)
    record_post_resume_evidence(connection, execution_id, resume_receipt)
    hooks.observe_post_resume_evidence(execution_id)
    terminal_id = record_terminal(
        connection, reservation_id, "AMBIGUOUS", "MAY_HAVE_OCCURRED"
    )
    assert terminal_id
    hooks.observe_terminal(reservation_id)
    with pytest.raises(sqlite3.IntegrityError):
        commit_claim(connection, attempt_id)
    assert hooks.events == [
        "provider-constructed",
        "process-intent-committed",
        "create-process",
        "process-created",
        "resume-intent-committed",
        "resume-thread",
        "post-resume-evidence",
        "terminal",
    ]
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    observer.close()
    connection.close()


@pytest.mark.parametrize(
    "blocked_case",
    [
        "claim_without_reservation",
        "committed_without_execution",
        "process_creation_failed_without_terminal",
        "process_created_without_execution",
        "manual_review_without_terminal",
        "pre_resume_ready",
        "resume_crash",
        "resume_recorded",
        "post_resume_ambiguous",
        "ambiguous_terminal",
        "closed_terminal",
        "closed_session",
        "failed_confirmed",
        "successful_terminal",
        "successful_selection",
    ],
)
def test_claim_admission_blocks_non_retry_safe_prior_outcomes(
    db_path: Path, blocked_case: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = (
        None
        if blocked_case == "claim_without_reservation"
        else reserve_launch(connection, first_claim)
    )
    second_attempt = allocate_attempt(connection, session_id)

    if blocked_case == "claim_without_reservation":
        pass
    elif blocked_case == "committed_without_execution":
        pass
    elif blocked_case == "process_creation_failed_without_terminal":
        assert first_reservation is not None
        _record_definitive_process_failure(connection, first_reservation)
    elif blocked_case == "process_created_without_execution":
        assert first_reservation is not None
        commit_process_intent(connection, first_reservation)
        connection.execute(
            "UPDATE launch_reservations SET reservation_state = ?, "
            "outcome_recorded_at_utc = ? WHERE launch_reservation_id = ?",
            ("PROCESS_CREATED", PROCESS_CREATED_TIMESTAMP, first_reservation),
        )
        connection.commit()
    elif blocked_case == "manual_review_without_terminal":
        assert first_reservation is not None
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            first_reservation,
            "CLASSIFY_LAUNCH_RESERVATION",
        )
    elif blocked_case == "pre_resume_ready":
        assert first_reservation is not None
        _record_successful_process(connection, first_reservation)
    elif blocked_case == "resume_crash":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        intent = commit_resume_intent(connection, execution_id)
        FakeSideEffects(connection).resume_thread(intent)
    elif blocked_case in ("resume_recorded", "post_resume_ambiguous"):
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id)
        if blocked_case == "post_resume_ambiguous":
            connection.execute(
                "UPDATE launch_executions SET phase = 'POST_RESUME_AMBIGUOUS' "
                "WHERE launch_execution_id = ?",
                (execution_id,),
            )
            connection.commit()
    elif blocked_case == "ambiguous_terminal":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id)
        record_terminal(connection, first_reservation, "AMBIGUOUS", "MAY_HAVE_OCCURRED")
    elif blocked_case == "closed_terminal":
        assert first_reservation is not None
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            first_reservation,
            "CLASSIFY_LAUNCH_RESERVATION",
        )
        record_terminal(connection, first_reservation, "CLOSED", "MAY_HAVE_OCCURRED")
    elif blocked_case == "closed_session":
        assert first_reservation is not None
        _record_definitive_process_failure(connection, first_reservation)
        record_terminal(connection, first_reservation, "FAILED", "NOT_STARTED")
        connection.execute(
            "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, "
            "close_reason = ? WHERE session_id = ?",
            (CLOSE_TIMESTAMP, "claim-admission-test-close", session_id),
        )
        connection.commit()
    elif blocked_case == "failed_confirmed":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id)
        record_terminal(connection, first_reservation, "FAILED", "CONFIRMED")
    elif blocked_case == "successful_terminal":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id)
        record_terminal(connection, first_reservation)
    elif blocked_case == "successful_selection":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id)
        terminal_id = record_terminal(connection, first_reservation)
        select_terminal(connection, session_id, terminal_id)
    else:
        raise AssertionError(f"unhandled blocked case: {blocked_case}")

    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        commit_claim(connection, second_attempt)
    request_bytes, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
        (second_attempt,),
    ).fetchone()
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        _insert_claim_row_for_test(
            connection, second_attempt, request_bytes, request_digest
        )
    connection.rollback()
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    connection.close()


@pytest.mark.parametrize("insertion_path", ["helper", "direct"])
def test_claim_admission_allows_only_retry_safe_failed_not_started(
    db_path: Path, insertion_path: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = reserve_launch(connection, first_claim)
    _record_definitive_process_failure(connection, first_reservation)
    record_terminal(connection, first_reservation, "FAILED", "NOT_STARTED")
    assert connection.execute(
        "SELECT reservation_state, outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (first_reservation,),
    ).fetchone() == ("TERMINAL_RECORDED", PROCESS_FAILURE_TIMESTAMP)

    second_attempt = allocate_attempt(connection, session_id)
    if insertion_path == "helper":
        second_claim = commit_claim(connection, second_attempt)
    else:
        request_bytes, request_digest = connection.execute(
            "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
            (second_attempt,),
        ).fetchone()
        _begin(connection)
        second_claim = _insert_claim_row_for_test(
            connection, second_attempt, request_bytes, request_digest
        )
        connection.commit()
    assert second_claim == _claim_id(
        second_attempt, CLAIM_POLICY, PROVIDER, OPERATION, 1
    )
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (2,)
    connection.close()


@pytest.mark.parametrize(
    ("reservation_state", "failure_mode", "outcome_timestamp"),
    [
        ("PROCESS_INTENT_COMMITTED", False, None),
        ("PROCESS_CREATED", False, None),
        ("PROCESS_CREATION_FAILED", True, None),
        ("MANUAL_REVIEW", False, None),
        ("TERMINAL_RECORDED", False, None),
        ("COMMITTED", True, None),
        ("COMMITTED", False, PROCESS_CREATED_TIMESTAMP),
    ],
)
def test_reservations_require_a_committed_initial_fence(
    db_path: Path,
    reservation_state: str,
    failure_mode: bool,
    outcome_timestamp: str | None,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    request_digest = connection.execute(
        "SELECT request_digest FROM provider_call_claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()[0]
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError, match="committed fences"):
        _insert_reservation_row_for_test(
            connection,
            claim_id,
            request_digest,
            reservation_state,
            failure_mode,
            outcome_timestamp,
        )
    connection.rollback()
    assert connection.execute(
        "SELECT count(*) FROM launch_reservations"
    ).fetchone() == (0,)
    connection.close()


@pytest.mark.parametrize("outcome_kind", ["process", "failure", "manual"])
def test_reservation_outcome_timestamp_is_preserved_and_write_once(
    db_path: Path, outcome_kind: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if outcome_kind == "process":
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id)
        expected_timestamp = PROCESS_CREATED_TIMESTAMP
        record_terminal(connection, reservation_id, "AMBIGUOUS", "MAY_HAVE_OCCURRED")
    elif outcome_kind == "failure":
        _record_definitive_process_failure(connection, reservation_id)
        expected_timestamp = PROCESS_FAILURE_TIMESTAMP
        record_terminal(connection, reservation_id, "FAILED", "NOT_STARTED")
    else:
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_LAUNCH_RESERVATION",
        )
        expected_timestamp = MANUAL_REVIEW_TIMESTAMP
        record_terminal(connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED")

    assert connection.execute(
        "SELECT outcome_recorded_at_utc FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == (expected_timestamp,)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_reservations SET outcome_recorded_at_utc = ? "
            "WHERE launch_reservation_id = ?",
            ("2026-01-09T00:00:00Z", reservation_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_reservations SET outcome_recorded_at_utc = NULL "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        )
    assert connection.execute(
        "SELECT outcome_recorded_at_utc FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == (expected_timestamp,)
    connection.close()


def test_terminal_transition_requires_a_prior_outcome_timestamp(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_reservations SET reservation_state = ? "
            "WHERE launch_reservation_id = ?",
            ("TERMINAL_RECORDED", reservation_id),
        )
    connection.rollback()
    assert connection.execute(
        "SELECT reservation_state, outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("COMMITTED", None)
    connection.close()


def test_resume_outcome_unknown_recovery_is_conservative_and_closable(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    reservation_id = reserve_launch(connection, first_claim)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id)
    FakeSideEffects(connection).resume_thread(intent)

    recovery_id = record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
    )
    assert recovery_id
    assert connection.execute(
        "SELECT reservation_state, outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("MANUAL_REVIEW", PROCESS_CREATED_TIMESTAMP)
    assert connection.execute(
        "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        )
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(connection, reservation_id, "SUCCEEDED", "CONFIRMED")
    terminal_id = record_terminal(
        connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED"
    )
    assert terminal_id
    record_recovery(connection, session_id, "SESSION", session_id, "CLOSE_SESSION")
    assert connection.execute(
        "SELECT state, closed_at_utc, close_reason FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == ("CLOSED", CLOSE_TIMESTAMP, "recovery-approved-close")
    connection.close()


def test_pre_resume_ready_has_separate_conservative_recovery_path(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        )
    recovery_id = record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PRE_RESUME_READY",
    )
    assert recovery_id
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("MANUAL_REVIEW",)
    assert connection.execute(
        "SELECT phase, resume_intent_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("PRE_RESUME_READY", None)
    connection.close()


def test_resume_outcome_unknown_recovery_grants_no_new_claim(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    reservation_id = reserve_launch(connection, first_claim)
    second_attempt = allocate_attempt(connection, session_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id)
    FakeSideEffects(connection).resume_thread(intent)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
    )

    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        commit_claim(connection, second_attempt)
    request_bytes, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
        (second_attempt,),
    ).fetchone()
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        _insert_claim_row_for_test(
            connection, second_attempt, request_bytes, request_digest
        )
    connection.rollback()
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    connection.close()


@pytest.mark.parametrize("failure_point", ["without_execution", "after_resume"])
def test_resume_outcome_unknown_requires_exact_unresolved_pre_resume_execution(
    db_path: Path, failure_point: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if failure_point == "after_resume":
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id)
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        )
    assert connection.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
        0,
    )
    connection.close()


def test_session_close_facts_are_write_once_and_only_close_with_state(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET closed_at_utc = ? WHERE session_id = ?",
            (CLOSE_TIMESTAMP, session_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET closed_at_utc = ?, close_reason = ? "
            "WHERE session_id = ?",
            (CLOSE_TIMESTAMP, "invalid-preclose", session_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET state = 'CLOSED', closed_at_utc = NULL, "
            "close_reason = ? WHERE session_id = ?",
            ("partial-close", session_id),
        )
    connection.execute(
        "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, close_reason = ? "
        "WHERE session_id = ?",
        (CLOSE_TIMESTAMP, "direct-close", session_id),
    )
    connection.commit()
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET closed_at_utc = ? WHERE session_id = ?",
            ("2026-01-10T00:00:00Z", session_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET close_reason = ? WHERE session_id = ?",
            ("replacement-close-reason", session_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET closed_at_utc = NULL, close_reason = NULL "
            "WHERE session_id = ?",
            (session_id,),
        )

    selected_session = create_session(connection, _request("2026-01-02"))
    selected_attempt = allocate_attempt(connection, selected_session)
    selected_claim = commit_claim(connection, selected_attempt)
    selected_reservation = reserve_launch(connection, selected_claim)
    selected_execution = _record_successful_process(connection, selected_reservation)
    _resume_and_persist(connection, selected_execution)
    selected_terminal = record_terminal(connection, selected_reservation)
    select_terminal(connection, selected_session, selected_terminal)
    connection.execute(
        "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, close_reason = ? "
        "WHERE session_id = ?",
        (CLOSE_TIMESTAMP, "selected-close", selected_session),
    )
    connection.commit()
    assert connection.execute(
        "SELECT state, closed_at_utc, close_reason FROM sessions WHERE session_id = ?",
        (selected_session,),
    ).fetchone() == ("CLOSED", CLOSE_TIMESTAMP, "selected-close")
    selection_selected_at, session_closed_at = connection.execute(
        """
        SELECT ss.selected_at_utc, s.closed_at_utc
        FROM session_selections ss
        JOIN sessions s ON s.session_id = ss.session_id
        WHERE ss.session_id = ?
        """,
        (selected_session,),
    ).fetchone()
    assert (selection_selected_at, session_closed_at) == (
        SELECTION_TIMESTAMP,
        CLOSE_TIMESTAMP,
    )
    assert selection_selected_at <= session_closed_at
    connection.close()


def test_process_intent_race_grants_exactly_one_process_call(db_path: Path) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    setup.close()

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    outcome_lock = threading.Lock()
    events: list[str] = []
    event_lock = threading.Lock()

    def worker() -> None:
        connection = _connect(db_path)
        hooks = FakeSideEffects(connection, events, event_lock)
        barrier.wait()
        try:
            intent = commit_process_intent(connection, reservation_id)
            result = hooks.create_process(intent)
            assert type(result) is FakeProcessCreationReceipt
            record_execution(connection, reservation_id, result)
            outcome = "winner"
        except ValueError:
            outcome = "loser"
        with outcome_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["loser", "winner"]
    assert events == [
        "process-intent-committed",
        "create-process",
        "process-created",
    ]
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state, process_intent_json IS NOT NULL, "
        "process_intent_digest IS NOT NULL, process_intent_committed_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("PROCESS_CREATED", 1, 1, PROCESS_INTENT_TIMESTAMP)
    assert verify.execute("SELECT count(*) FROM launch_executions").fetchone() == (1,)
    verify.close()


def test_process_hook_requires_matching_one_shot_opaque_permit(db_path: Path) -> None:
    connection = _connect(db_path)
    first_session = create_session(connection)
    first_attempt = allocate_attempt(connection, first_session)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = reserve_launch(connection, first_claim)
    hooks = FakeSideEffects(connection)
    with pytest.raises(TypeError, match="opaque fake process intent"):
        hooks.create_process(first_reservation)  # type: ignore[arg-type]

    intent = commit_process_intent(connection, first_reservation)
    second_session = create_session(connection, _request("2026-01-02"))
    second_attempt = allocate_attempt(connection, second_session)
    second_claim = commit_claim(connection, second_attempt)
    second_reservation = reserve_launch(connection, second_claim)
    cross_reservation = FakeProcessIntent(
        reservation_id=second_reservation,
        intent_json=intent.intent_json,
        intent_digest=intent.intent_digest,
        _issuer=_PROCESS_INTENT_ISSUER,
        _permit=intent._permit,
    )
    with pytest.raises(ValueError, match="PROCESS_INTENT_COMMITTED"):
        hooks.create_process(cross_reservation)

    result = hooks.create_process(intent)
    assert type(result) is FakeProcessCreationReceipt
    with pytest.raises(ValueError, match="already consumed"):
        hooks.create_process(intent)
    record_execution(connection, first_reservation, result)
    connection.close()


def test_process_success_receipt_is_exact_canonical_and_one_shot(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    with pytest.raises(TypeError, match="fake process creation receipt"):
        record_execution(connection, reservation_id, None)  # type: ignore[arg-type]

    intent = commit_process_intent(connection, reservation_id)
    receipt = FakeSideEffects(connection).create_process(intent)
    assert type(receipt) is FakeProcessCreationReceipt
    canonical_process = json.loads(receipt.process_json)
    malformed_receipts = [
        replace(receipt, process_json=b"{}", process_digest=_digest(b"{}")),
        replace(
            receipt,
            process_json=_json({**canonical_process, "extra": True}),
            process_digest=_digest(_json({**canonical_process, "extra": True})),
        ),
        replace(
            receipt,
            process_json=_json({**canonical_process, "creation_result": "UNKNOWN"}),
            process_digest=_digest(
                _json({**canonical_process, "creation_result": "UNKNOWN"})
            ),
        ),
        replace(receipt, process_json=b"not-json", process_digest=_digest(b"not-json")),
        replace(receipt, process_digest=b"x" * 32),
    ]
    for malformed in malformed_receipts:
        with pytest.raises(ValueError, match="canonical evidence"):
            record_execution(connection, reservation_id, malformed)
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )

    other_session = create_session(connection, _request("2026-01-02"))
    other_attempt = allocate_attempt(connection, other_session)
    other_claim = commit_claim(connection, other_attempt)
    other_reservation = reserve_launch(connection, other_claim)
    with pytest.raises(ValueError, match="another reservation"):
        record_execution(connection, other_reservation, receipt)

    execution_id = record_execution(connection, reservation_id, receipt)
    assert execution_id
    with pytest.raises(ValueError, match="already consumed"):
        record_execution(connection, reservation_id, receipt)
    connection.close()


def test_process_failure_result_is_exact_and_only_not_started_path(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    intent = commit_process_intent(connection, reservation_id)
    failure = FakeSideEffects(connection).create_process(intent, fail=True)
    assert type(failure) is FakeProcessCreationFailure
    with pytest.raises(TypeError, match="fake process creation receipt"):
        record_execution(connection, reservation_id, failure)  # type: ignore[arg-type]
    for malformed in (
        replace(failure, result_json=b"{}", result_digest=_digest(b"{}")),
        replace(failure, result_digest=b"x" * 32),
    ):
        with pytest.raises(ValueError, match="canonical evidence"):
            record_process_creation_failure(connection, reservation_id, malformed)
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("PROCESS_INTENT_COMMITTED",)

    other_session = create_session(connection, _request("2026-01-02"))
    other_attempt = allocate_attempt(connection, other_session)
    other_claim = commit_claim(connection, other_attempt)
    other_reservation = reserve_launch(connection, other_claim)
    with pytest.raises(ValueError, match="another reservation"):
        record_process_creation_failure(connection, other_reservation, failure)

    record_process_creation_failure(connection, reservation_id, failure)
    terminal_id = record_terminal(connection, reservation_id, "FAILED", "NOT_STARTED")
    assert terminal_id
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )
    with pytest.raises(ValueError, match="already consumed"):
        record_process_creation_failure(connection, reservation_id, failure)
    connection.close()


@pytest.mark.parametrize("invoke_create_process", [False, True])
def test_crash_around_process_call_is_unretryable_and_conservative(
    db_path: Path, invoke_create_process: bool
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    intent = commit_process_intent(connection, reservation_id)
    result: FakeProcessCreationReceipt | FakeProcessCreationFailure | None = None
    if invoke_create_process:
        result = FakeSideEffects(connection).create_process(intent)
    connection.close()
    with _ISSUED_PROCESS_PERMITS_LOCK:
        _ISSUED_PROCESS_PERMITS.discard(intent._permit)
    if result is not None:
        with _ISSUED_PROCESS_RESULTS_LOCK:
            _ISSUED_PROCESS_RESULTS.discard(result._permit)

    recovered = _connect(db_path)
    durable = recovered.execute(
        "SELECT reservation_state, process_intent_json, process_intent_digest, "
        "process_intent_committed_at_utc FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone()
    assert durable == (
        "PROCESS_INTENT_COMMITTED",
        intent.intent_json,
        intent.intent_digest,
        PROCESS_INTENT_TIMESTAMP,
    )
    with pytest.raises(ValueError, match="COMMITTED"):
        commit_process_intent(recovered, reservation_id)
    with pytest.raises(ValueError, match="already consumed|not issued"):
        FakeSideEffects(recovered).create_process(intent)
    second_attempt = allocate_attempt(recovered, session_id)
    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        commit_claim(recovered, second_attempt)

    record_recovery(
        recovered,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
    )
    assert recovered.execute(
        "SELECT reservation_state, process_intent_json, process_intent_digest, "
        "outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == (
        "MANUAL_REVIEW",
        intent.intent_json,
        intent.intent_digest,
        MANUAL_REVIEW_TIMESTAMP,
    )
    assert recovered.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (1,)
    assert recovered.execute(
        "SELECT action, predecessor_state, resulting_state "
        "FROM manual_recoveries WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        "PROCESS_INTENT_COMMITTED",
        "MANUAL_REVIEW",
    )
    with pytest.raises(ValueError, match="PROCESS_INTENT_COMMITTED"):
        FakeSideEffects(recovered).create_process(intent)
    recovered.close()


def test_process_unknown_recovery_allows_only_conservative_close_path(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    intent = commit_process_intent(connection, reservation_id)
    with _ISSUED_PROCESS_PERMITS_LOCK:
        _ISSUED_PROCESS_PERMITS.discard(intent._permit)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
    )
    terminal_id = record_terminal(
        connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED"
    )
    assert terminal_id
    record_recovery(connection, session_id, "SESSION", session_id, "CLOSE_SESSION")
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == ("CLOSED",)
    connection.close()


def test_process_intent_evidence_is_paired_digest_valid_and_append_only(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_reservations SET reservation_state = "
            "'PROCESS_INTENT_COMMITTED' WHERE launch_reservation_id = ?",
            (reservation_id,),
        )
    connection.rollback()

    intent = commit_process_intent(connection, reservation_id)
    assert connection.execute(
        "SELECT reservation_state, process_intent_json, process_intent_digest, "
        "process_intent_committed_at_utc, outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == (
        "PROCESS_INTENT_COMMITTED",
        intent.intent_json,
        _digest(intent.intent_json),
        PROCESS_INTENT_TIMESTAMP,
        None,
    )
    for assignment, values in (
        ("process_intent_json = NULL", ()),
        ("process_intent_digest = NULL", ()),
        ("process_intent_committed_at_utc = NULL", ()),
        (
            "process_intent_json = ?, process_intent_digest = ?",
            (b"replacement", _digest(b"replacement")),
        ),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"UPDATE launch_reservations SET {assignment} "
                "WHERE launch_reservation_id = ?",
                (*values, reservation_id),
            )
        connection.rollback()
    with pytest.raises(ValueError, match="COMMITTED"):
        commit_process_intent(connection, reservation_id)
    connection.close()


def test_pre_resume_recovery_revokes_intent_before_terminal_and_close(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    with _ISSUED_RESUME_PERMITS_LOCK:
        permits_before = set(_ISSUED_RESUME_PERMITS)

    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PRE_RESUME_READY",
    )
    with pytest.raises(ValueError, match="revoked|unavailable"):
        commit_resume_intent(connection, execution_id)
    with _ISSUED_RESUME_PERMITS_LOCK:
        assert _ISSUED_RESUME_PERMITS == permits_before
    assert events == []

    record_terminal(connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED")
    with pytest.raises(ValueError, match="revoked|unavailable"):
        commit_resume_intent(connection, execution_id)
    record_recovery(connection, session_id, "SESSION", session_id, "CLOSE_SESSION")
    with pytest.raises(ValueError, match="revoked|unavailable"):
        commit_resume_intent(connection, execution_id)
    assert connection.execute(
        "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("PRE_RESUME_READY",)
    assert hooks.events == []
    connection.close()


def test_resume_permit_is_revoked_by_unknown_outcome_recovery(db_path: Path) -> None:
    connection = _connect(db_path)
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
    )

    with pytest.raises(ValueError, match="revoked"):
        hooks.resume_thread(intent)
    assert not intent._permit.consumed
    assert events == []
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("MANUAL_REVIEW",)
    assert connection.execute(
        "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)

    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(connection, reservation_id)
    record_terminal(connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED")
    with pytest.raises(ValueError, match="revoked|unavailable"):
        hooks.resume_thread(intent)
    record_recovery(connection, session_id, "SESSION", session_id, "CLOSE_SESSION")
    with pytest.raises(ValueError, match="revoked|unavailable"):
        hooks.resume_thread(intent)
    assert connection.execute("SELECT count(*) FROM session_selections").fetchone() == (
        0,
    )
    with _ISSUED_RESUME_PERMITS_LOCK:
        _ISSUED_RESUME_PERMITS.discard(intent._permit)
    connection.close()


def test_delayed_resume_receipt_is_revoked_by_recovery(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id)
    receipt = FakeSideEffects(connection).resume_thread(intent)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
    )

    with pytest.raises(ValueError, match="revoked"):
        record_post_resume_evidence(connection, execution_id, receipt)
    assert json.loads(receipt.result_json)["resume_result"] == "RESUMED"
    assert connection.execute(
        "SELECT phase, post_resume_json, post_resume_digest, cleanup_json, "
        "cleanup_digest FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None, None, None)
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("MANUAL_REVIEW",)
    record_terminal(connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED")
    with pytest.raises(ValueError, match="revoked|unavailable"):
        record_post_resume_evidence(connection, execution_id, receipt)
    record_recovery(connection, session_id, "SESSION", session_id, "CLOSE_SESSION")
    with pytest.raises(ValueError, match="revoked|unavailable"):
        record_post_resume_evidence(connection, execution_id, receipt)
    connection.close()


@pytest.mark.parametrize("phase", ["PRE_RESUME_READY", "RESUME_INTENT_COMMITTED"])
def test_direct_sql_resume_phase_advance_fails_after_manual_review(
    db_path: Path, phase: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent_json = _json(
        {
            "execution_id": execution_id,
            "resume_operation": "ResumeThread",
            "schema": 1,
        }
    )
    if phase == "PRE_RESUME_READY":
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_PRE_RESUME_READY",
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE launch_executions SET phase = 'RESUME_INTENT_COMMITTED', "
                "resume_intent_json = ?, resume_intent_digest = ?, "
                "resume_intent_committed_at_utc = ? WHERE launch_execution_id = ?",
                (
                    intent_json,
                    _digest(intent_json),
                    RESUME_INTENT_TIMESTAMP,
                    execution_id,
                ),
            )
    else:
        intent = commit_resume_intent(connection, execution_id)
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        )
        post_json = _json(
            {
                "execution_id": execution_id,
                "resume_intent_digest": intent.intent_digest.hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        cleanup, cleanup_digest = _evidence(f"cleanup:{execution_id}")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE launch_executions SET phase = 'RESUME_RECORDED', "
                "post_resume_json = ?, post_resume_digest = ?, cleanup_json = ?, "
                "cleanup_digest = ? WHERE launch_execution_id = ?",
                (
                    post_json,
                    _digest(post_json),
                    cleanup,
                    cleanup_digest,
                    execution_id,
                ),
            )
        with _ISSUED_RESUME_PERMITS_LOCK:
            _ISSUED_RESUME_PERMITS.discard(intent._permit)
    connection.rollback()
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("MANUAL_REVIEW",)
    connection.close()


def test_recovery_race_with_resume_intent_has_one_valid_winner(db_path: Path) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    setup.close()
    barrier = threading.Barrier(2)
    outcomes: list[tuple[str, bool, FakeResumeIntent | None]] = []
    outcome_lock = threading.Lock()

    def intent_worker() -> None:
        connection = _connect(db_path)
        barrier.wait()
        intent: FakeResumeIntent | None = None
        try:
            intent = commit_resume_intent(connection, execution_id)
            success = True
        except (ValueError, sqlite3.IntegrityError):
            success = False
        with outcome_lock:
            outcomes.append(("intent", success, intent))
        connection.close()

    def recovery_worker() -> None:
        connection = _connect(db_path)
        barrier.wait()
        try:
            record_recovery(
                connection,
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_PRE_RESUME_READY",
            )
            success = True
        except (ValueError, sqlite3.IntegrityError):
            success = False
        with outcome_lock:
            outcomes.append(("recovery", success, None))
        connection.close()

    threads = [
        threading.Thread(target=intent_worker),
        threading.Thread(target=recovery_worker),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(success for _, success, _ in outcomes) == 1
    verify = _connect(db_path)
    intent_outcome = next(item for item in outcomes if item[0] == "intent")
    if intent_outcome[1]:
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("PROCESS_CREATED",)
        assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
            0,
        )
        assert intent_outcome[2] is not None
        with _ISSUED_RESUME_PERMITS_LOCK:
            _ISSUED_RESUME_PERMITS.discard(intent_outcome[2]._permit)
    else:
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("MANUAL_REVIEW",)
        assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
            1,
        )
    verify.close()


@pytest.mark.parametrize("winner", ["recovery", "hook"])
def test_recovery_race_with_resume_dispatch_is_serialized(
    db_path: Path, winner: str
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    intent = commit_resume_intent(setup, execution_id)
    setup.close()
    lifecycle_lock = _resume_lifecycle_lock(reservation_id)
    winner_has_lock = threading.Event()
    events: list[str] = []
    event_lock = threading.Lock()
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def run_recovery(first: bool) -> None:
        connection = _connect(db_path)
        try:
            if first:
                with lifecycle_lock:
                    winner_has_lock.set()
                    record_recovery(
                        connection,
                        session_id,
                        "LAUNCH_RESERVATION",
                        reservation_id,
                        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                    )
            else:
                winner_has_lock.wait()
                record_recovery(
                    connection,
                    session_id,
                    "LAUNCH_RESERVATION",
                    reservation_id,
                    "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                )
            outcome = "recovery"
        except (ValueError, sqlite3.IntegrityError):
            outcome = "recovery-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    def run_hook(first: bool) -> None:
        connection = _connect(db_path)
        hooks = FakeSideEffects(connection, events, event_lock)
        try:
            if first:
                with lifecycle_lock:
                    winner_has_lock.set()
                    hooks.resume_thread(intent)
            else:
                winner_has_lock.wait()
                hooks.resume_thread(intent)
            outcome = "hook"
        except ValueError:
            outcome = "hook-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [
        threading.Thread(target=run_recovery, args=(winner == "recovery",)),
        threading.Thread(target=run_hook, args=(winner == "hook",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if winner == "recovery":
        assert sorted(outcomes) == ["hook-rejected", "recovery"]
        assert events == []
        with _ISSUED_RESUME_PERMITS_LOCK:
            _ISSUED_RESUME_PERMITS.discard(intent._permit)
    else:
        assert sorted(outcomes) == ["hook", "recovery"]
        assert events == ["resume-intent-committed", "resume-thread"]
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("MANUAL_REVIEW",)
    verify.close()


@pytest.mark.parametrize("winner", ["recovery", "receipt"])
def test_recovery_race_with_receipt_persistence_is_serialized(
    db_path: Path, winner: str
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    intent = commit_resume_intent(setup, execution_id)
    receipt = FakeSideEffects(setup).resume_thread(intent)
    setup.close()
    lifecycle_lock = _resume_lifecycle_lock(reservation_id)
    winner_has_lock = threading.Event()
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def run_recovery(first: bool) -> None:
        connection = _connect(db_path)
        try:
            if first:
                with lifecycle_lock:
                    winner_has_lock.set()
                    record_recovery(
                        connection,
                        session_id,
                        "LAUNCH_RESERVATION",
                        reservation_id,
                        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                    )
            else:
                winner_has_lock.wait()
                record_recovery(
                    connection,
                    session_id,
                    "LAUNCH_RESERVATION",
                    reservation_id,
                    "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                )
            outcome = "recovery"
        except (ValueError, sqlite3.IntegrityError):
            outcome = "recovery-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    def run_receipt(first: bool) -> None:
        connection = _connect(db_path)
        try:
            if first:
                with lifecycle_lock:
                    winner_has_lock.set()
                    record_post_resume_evidence(connection, execution_id, receipt)
            else:
                winner_has_lock.wait()
                record_post_resume_evidence(connection, execution_id, receipt)
            outcome = "receipt"
        except (ValueError, sqlite3.IntegrityError):
            outcome = "receipt-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [
        threading.Thread(target=run_recovery, args=(winner == "recovery",)),
        threading.Thread(target=run_receipt, args=(winner == "receipt",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    verify = _connect(db_path)
    if winner == "recovery":
        assert sorted(outcomes) == ["receipt-rejected", "recovery"]
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("MANUAL_REVIEW",)
        assert verify.execute(
            "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    else:
        assert sorted(outcomes) == ["receipt", "recovery-rejected"]
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("PROCESS_CREATED",)
        assert verify.execute(
            "SELECT phase, post_resume_json IS NOT NULL, cleanup_json IS NOT NULL "
            "FROM launch_executions WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == ("RESUME_RECORDED", 1, 1)
    verify.close()


def test_process_receipt_cannot_persist_after_process_recovery(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    process_intent = commit_process_intent(connection, reservation_id)
    process_receipt = FakeSideEffects(connection).create_process(process_intent)
    assert type(process_receipt) is FakeProcessCreationReceipt
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
    )
    with pytest.raises(ValueError, match="PROCESS_INTENT_COMMITTED"):
        record_execution(connection, reservation_id, process_receipt)
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )
    with _ISSUED_PROCESS_RESULTS_LOCK:
        _ISSUED_PROCESS_RESULTS.discard(process_receipt._permit)
    connection.close()


def test_resume_boundary_requires_pre_resume_and_receipt(db_path: Path) -> None:
    connection = _connect(db_path)
    hooks = FakeSideEffects(connection)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    application_release, authority_policy = connection.execute(
        "SELECT application_release_version, authority_policy_version "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone()
    execution_id = _execution_id(reservation_id, application_release, authority_policy)

    with pytest.raises(ValueError, match="unknown execution"):
        hooks.resume_thread(commit_resume_intent(connection, execution_id))

    execution_id = _record_successful_process(connection, reservation_id)
    with pytest.raises(TypeError, match="fake resume receipt"):
        record_post_resume_evidence(connection, execution_id, None)  # type: ignore[arg-type]
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(connection, reservation_id)
    assert connection.execute(
        "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("PRE_RESUME_READY",)
    connection.close()


def test_resume_intent_race_grants_exactly_one_hook_authority(db_path: Path) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    setup.close()

    barrier = threading.Barrier(2)
    results: list[str] = []
    result_lock = threading.Lock()
    events: list[str] = []
    event_lock = threading.Lock()

    def worker() -> None:
        connection = _connect(db_path)
        hooks = FakeSideEffects(connection, events, event_lock)
        barrier.wait()
        try:
            intent = commit_resume_intent(connection, execution_id)
            hooks.resume_thread(intent)
            outcome = "winner"
        except ValueError:
            outcome = "loser"
        with result_lock:
            results.append(outcome)
        connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["loser", "winner"]
    assert events == ["resume-intent-committed", "resume-thread"]
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT phase, resume_intent_json IS NOT NULL, "
        "resume_intent_digest IS NOT NULL, resume_intent_committed_at_utc "
        "FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", 1, 1, RESUME_INTENT_TIMESTAMP)
    with pytest.raises(ValueError, match="PRE_RESUME_READY"):
        commit_resume_intent(verify, execution_id)
    verify.close()


@pytest.mark.parametrize("invoke_resume_thread", [False, True])
def test_crash_around_resume_leaves_same_unretryable_intent_state(
    db_path: Path, invoke_resume_thread: bool
) -> None:
    connection = _connect(db_path)
    hooks = FakeSideEffects(connection)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id)
    if invoke_resume_thread:
        hooks.resume_thread(intent)
    connection.close()
    with _ISSUED_RESUME_PERMITS_LOCK:
        _ISSUED_RESUME_PERMITS.discard(intent._permit)

    recovered = _connect(db_path)
    assert recovered.execute(
        "SELECT phase, resume_intent_json, resume_intent_digest, "
        "post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == (
        "RESUME_INTENT_COMMITTED",
        intent.intent_json,
        intent.intent_digest,
        None,
        None,
    )
    assert recovered.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("PROCESS_CREATED",)
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(recovered, reservation_id)
    with pytest.raises(ValueError, match="PRE_RESUME_READY"):
        commit_resume_intent(recovered, execution_id)
    with pytest.raises(ValueError, match="already consumed|not issued"):
        FakeSideEffects(recovered).resume_thread(intent)
    with pytest.raises(TypeError, match="opaque fake resume intent"):
        FakeSideEffects(recovered).resume_thread(execution_id)  # type: ignore[arg-type]
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            recovered,
            session_id,
            "ATTEMPT",
            attempt_id,
            "RECORD_ATTEMPT_AMBIGUITY",
        )

    second_attempt = allocate_attempt(recovered, session_id)
    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        commit_claim(recovered, second_attempt)
    assert recovered.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    assert recovered.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
        0,
    )
    recovered.close()


def test_resume_hook_failure_returns_no_receipt_and_consumes_permit(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id)
    hooks = FakeSideEffects(connection)
    with pytest.raises(RuntimeError, match="modeled ResumeThread failure"):
        hooks.resume_thread(intent, fail=True)
    with pytest.raises(ValueError, match="already consumed"):
        hooks.resume_thread(intent)
    assert connection.execute(
        "SELECT phase, post_resume_json, post_resume_digest FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    connection.close()


@pytest.mark.parametrize(
    "invalid_receipt",
    [
        "failed-result",
        "error-result",
        "unknown-result",
        "wrong-schema",
        "string-schema",
        "wrong-execution",
        "wrong-intent",
        "extra-field",
        "missing-field",
        "noncanonical-bytes",
        "wrong-digest",
    ],
)
def test_post_resume_evidence_requires_exact_canonical_success_receipt(
    db_path: Path, invalid_receipt: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id)
    valid = FakeSideEffects(connection).resume_thread(intent)
    envelope: dict[str, object] = json.loads(valid.result_json)
    receipt_execution = execution_id
    receipt_intent_digest = intent.intent_digest
    if invalid_receipt == "failed-result":
        envelope["resume_result"] = "FAILED"
    elif invalid_receipt == "error-result":
        envelope["resume_result"] = "ERROR"
    elif invalid_receipt == "unknown-result":
        envelope["resume_result"] = "UNKNOWN"
    elif invalid_receipt == "wrong-schema":
        envelope["schema"] = 2
    elif invalid_receipt == "string-schema":
        envelope["schema"] = "1"
    elif invalid_receipt == "wrong-execution":
        receipt_execution = str(uuid.UUID(int=0))
    elif invalid_receipt == "wrong-intent":
        receipt_intent_digest = _digest(b"wrong-intent")
    elif invalid_receipt == "extra-field":
        envelope["extra"] = True
    elif invalid_receipt == "missing-field":
        del envelope["resume_result"]
    result_json = _json(envelope)
    if invalid_receipt == "noncanonical-bytes":
        result_json = json.dumps(envelope, indent=2).encode("utf-8")
    result_digest = _digest(result_json)
    if invalid_receipt == "wrong-digest":
        result_digest = _digest(b"wrong-result")
    receipt = FakeResumeReceipt(
        execution_id=receipt_execution,
        resume_intent_digest=receipt_intent_digest,
        result_json=result_json,
        result_digest=result_digest,
    )
    with pytest.raises(ValueError):
        record_post_resume_evidence(connection, execution_id, receipt)
    assert connection.execute(
        "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(connection, reservation_id)
    connection.close()


def test_fake_resume_receipt_cannot_be_reused_for_another_execution(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_ids = [
        create_session(connection, _request("2026-01-01")),
        create_session(connection, _request("2026-01-02")),
    ]
    attempts: list[str] = []
    reservations: list[str] = []
    for session_id in session_ids:
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservations.append(reserve_launch(connection, claim_id))
        attempts.append(attempt_id)

    executions = [
        _record_successful_process(connection, reservation)
        for reservation in reservations
    ]
    hooks = FakeSideEffects(connection)
    intents = [commit_resume_intent(connection, execution) for execution in executions]
    reused_intent = FakeResumeIntent(
        execution_id=executions[1],
        intent_json=intents[0].intent_json,
        intent_digest=intents[0].intent_digest,
        _issuer=_RESUME_INTENT_ISSUER,
        _permit=intents[0]._permit,
    )
    with pytest.raises(ValueError, match="committed authority"):
        hooks.resume_thread(reused_intent)
    receipt = hooks.resume_thread(intents[0])
    with pytest.raises(ValueError, match="another execution"):
        record_post_resume_evidence(connection, executions[1], receipt)
    assert connection.execute(
        "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
        (executions[1],),
    ).fetchone() == ("RESUME_INTENT_COMMITTED",)
    record_post_resume_evidence(connection, executions[0], receipt)
    second_receipt = hooks.resume_thread(intents[1])
    record_post_resume_evidence(connection, executions[1], second_receipt)
    assert attempts
    connection.close()


def test_launch_execution_evidence_is_append_only(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    post_resume, post_digest = _evidence("post-resume-test")
    cleanup, cleanup_digest = _evidence("cleanup-test")
    intent_json = _json(
        {
            "execution_id": execution_id,
            "resume_operation": "ResumeThread",
            "schema": 1,
        }
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_INTENT_COMMITTED' "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET resume_intent_json = ?, "
            "resume_intent_digest = ?, resume_intent_committed_at_utc = ? "
            "WHERE launch_execution_id = ?",
            (
                intent_json,
                _digest(intent_json),
                RESUME_INTENT_TIMESTAMP,
                execution_id,
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET post_resume_json = ?, "
            "post_resume_digest = ? WHERE launch_execution_id = ?",
            (post_resume, post_digest, execution_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_RECORDED' "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_RECORDED', "
            "post_resume_json = ? WHERE launch_execution_id = ?",
            (post_resume, execution_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_RECORDED', "
            "post_resume_json = ?, post_resume_digest = ? "
            "WHERE launch_execution_id = ?",
            (post_resume, _digest(b"wrong-post-digest"), execution_id),
        )

    resume_intent = commit_resume_intent(connection, execution_id)
    reconstructed_intent = FakeResumeIntent(
        execution_id=execution_id,
        intent_json=resume_intent.intent_json,
        intent_digest=resume_intent.intent_digest,
        _issuer=_RESUME_INTENT_ISSUER,
        _permit=_ResumePermit(),
    )
    with pytest.raises(ValueError, match="not issued"):
        FakeSideEffects(connection).resume_thread(reconstructed_intent)
    for sql, params in (
        (
            "UPDATE launch_executions SET resume_intent_json = ? "
            "WHERE launch_execution_id = ?",
            (_json({"replacement": True}), execution_id),
        ),
        (
            "UPDATE launch_executions SET resume_intent_digest = ? "
            "WHERE launch_execution_id = ?",
            (_digest(b"replacement"), execution_id),
        ),
        (
            "UPDATE launch_executions SET resume_intent_committed_at_utc = ? "
            "WHERE launch_execution_id = ?",
            (MANUAL_REVIEW_TIMESTAMP, execution_id),
        ),
        (
            "UPDATE launch_executions SET resume_intent_json = NULL, "
            "resume_intent_digest = NULL, resume_intent_committed_at_utc = NULL "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql, params)
    invalid_receipt_json = _json(
        {
            "execution_id": execution_id,
            "resume_intent_digest": resume_intent.intent_digest.hex(),
            "resume_result": "FAILED",
            "schema": 1,
        }
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_RECORDED', "
            "post_resume_json = ?, post_resume_digest = ?, cleanup_json = ?, "
            "cleanup_digest = ? WHERE launch_execution_id = ?",
            (
                invalid_receipt_json,
                _digest(invalid_receipt_json),
                cleanup,
                cleanup_digest,
                execution_id,
            ),
        )
    resume_receipt = FakeSideEffects(connection).resume_thread(resume_intent)
    record_post_resume_evidence(connection, execution_id, resume_receipt)
    for sql, params in (
        (
            "UPDATE launch_executions SET post_resume_json = ? "
            "WHERE launch_execution_id = ?",
            (post_resume, execution_id),
        ),
        (
            "UPDATE launch_executions SET post_resume_digest = ? "
            "WHERE launch_execution_id = ?",
            (post_digest, execution_id),
        ),
        (
            "UPDATE launch_executions SET post_resume_json = NULL "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ),
        (
            "UPDATE launch_executions SET cleanup_json = ? "
            "WHERE launch_execution_id = ?",
            (cleanup, execution_id),
        ),
        (
            "UPDATE launch_executions SET cleanup_digest = ? "
            "WHERE launch_execution_id = ?",
            (cleanup_digest, execution_id),
        ),
        (
            "UPDATE launch_executions SET cleanup_digest = NULL "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql, params)

    record_terminal(connection, reservation_id)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET post_resume_json = ? "
            "WHERE launch_execution_id = ?",
            (post_resume, execution_id),
        )
    connection.close()


@pytest.mark.parametrize(
    "invalid_boundary",
    [
        "attempt",
        "claim",
        "reservation",
        "execution",
        "terminal",
        "selection",
        "recovery",
    ],
)
def test_invalid_lifecycle_transitions_are_rejected(
    db_path: Path, invalid_boundary: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)

    if invalid_boundary == "attempt":
        mutation = (
            "UPDATE attempts SET state = 'SUCCESS_SELECTED' WHERE attempt_id = ?",
            (attempt_id,),
        )
    elif invalid_boundary == "claim":
        claim_id = commit_claim(connection, attempt_id)
        mutation = (
            "UPDATE provider_call_claims SET state = 'INVALID' WHERE claim_id = ?",
            (claim_id,),
        )
    elif invalid_boundary == "reservation":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        mutation = (
            "UPDATE launch_reservations SET reservation_state = "
            "'TERMINAL_RECORDED' WHERE launch_reservation_id = ?",
            (reservation_id,),
        )
    elif invalid_boundary == "execution":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        mutation = (
            "UPDATE launch_executions SET phase = 'TERMINAL_RECORDED' "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        )
    elif invalid_boundary == "terminal":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id)
        terminal_id = record_terminal(connection, reservation_id)
        mutation = (
            "UPDATE terminals SET terminal_state = 'FAILED' WHERE terminal_id = ?",
            (terminal_id,),
        )
    elif invalid_boundary == "selection":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id)
        terminal_id = record_terminal(connection, reservation_id)
        selection_id = select_terminal(connection, session_id, terminal_id)
        mutation = (
            "UPDATE session_selections SET selection_policy_version = 'bad' "
            "WHERE selection_id = ?",
            (selection_id,),
        )
    else:
        mutation = None

    if mutation is not None:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(*mutation)
    else:
        with pytest.raises(sqlite3.IntegrityError):
            record_recovery(
                connection,
                session_id,
                "ATTEMPT",
                attempt_id,
                "RECORD_ATTEMPT_AMBIGUITY",
            )
    connection.close()


def test_recovery_race_produces_consecutive_ordinals(db_path: Path) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    target_attempt = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, target_attempt)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    _resume_and_persist(setup, execution_id)
    setup.close()
    barrier = threading.Barrier(2)
    results: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(target_kind: str, target_id: str, action: str) -> None:
        connection = _connect(db_path)
        try:
            barrier.wait()
            recovery_id = record_recovery(
                connection,
                session_id,
                target_kind,
                target_id,
                action,
            )
            with lock:
                results.append(recovery_id)
        except BaseException as error:
            with lock:
                errors.append(error)
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=worker,
            args=("ATTEMPT", target_attempt, "RECORD_ATTEMPT_AMBIGUITY"),
        ),
        threading.Thread(
            target=worker,
            args=("SESSION", session_id, "ACKNOWLEDGE_RESTORE"),
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(results) == 2
    connection = _connect(db_path)
    assert [
        row[0]
        for row in connection.execute(
            "SELECT recovery_ordinal FROM manual_recoveries ORDER BY recovery_ordinal"
        )
    ] == [0, 1]
    connection.close()
