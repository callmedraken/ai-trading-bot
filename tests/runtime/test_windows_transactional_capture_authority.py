"""Executable evidence for the normalized transactional authority design."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

import pytest

SCHEMA_PATH = (
    Path(__file__).parents[1] / "fixtures" / "transactional_authority_schema.sql"
)
NAMESPACE = uuid.UUID("7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012")
EPOCH = "12345678-1234-5678-9abc-def012345678"
MACHINE = "87654321-4321-8765-cba9-876543210987"
PROVIDER = "ALPACA_MARKET_DATA"
OPERATION = "HISTORICAL_DAILY_BARS"
POLICY = "authority-policy/v1"
CLAIM_POLICY = "claim-policy/v1"
RELEASE = "release/v1"
TIMESTAMP = "2026-01-01T00:00:00Z"


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
) -> str:
    attempt_id = _attempt_id(session_id, ordinal)
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
            PROVIDER,
            OPERATION,
            request_bytes,
            request_digest,
            CLAIM_POLICY,
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
) -> str:
    claim_id = _claim_id(attempt_id)
    evidence, evidence_digest = _evidence(f"raw-claim:{attempt_id}")
    connection.execute(
        """
        INSERT INTO provider_call_claims (
            claim_id, attempt_id, claim_schema, claim_policy_version,
            provider_id, permitted_provider_operation, provider_call_budget,
            request_json, request_digest, claim_evidence_json,
            claim_evidence_digest, state, committed_at_utc
        ) VALUES (?, ?, 1, ?, ?, ?, 1, ?, ?, ?, ?, 'COMMITTED', ?)
        """,
        (
            claim_id,
            attempt_id,
            CLAIM_POLICY,
            PROVIDER,
            OPERATION,
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
) -> str:
    reservation_id = _reservation_id(claim_id)
    evidence, evidence_digest = _evidence(f"raw-reservation:{claim_id}")
    connection.execute(
        """
        INSERT INTO launch_reservations (
            launch_reservation_id, claim_id, launch_reservation_schema,
            application_release_version, authority_policy_version,
            claim_policy_version, request_digest, reservation_evidence_json,
            reservation_evidence_digest, reservation_state,
            process_creation_failure_json, process_creation_failure_digest,
            committed_at_utc, outcome_recorded_at_utc
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)
        """,
        (
            reservation_id,
            claim_id,
            RELEASE,
            POLICY,
            CLAIM_POLICY,
            request_digest,
            evidence,
            evidence_digest,
            reservation_state,
            TIMESTAMP,
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
    terminal_id = _terminal_id(reservation_id)
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
        ) VALUES (?, ?, 1, 'terminal-policy/v1', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            terminal_id,
            reservation_id,
            state,
            disposition,
            request_digest,
            evidence,
            evidence_digest,
            snapshot,
            diagnostics,
            diagnostics_digest,
            TIMESTAMP,
        ),
    )
    return terminal_id


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


def _session_id(request: dict[str, Any]) -> str:
    return _identity(
        "session_id/v2",
        MACHINE,
        EPOCH,
        "1",
        POLICY,
        CLAIM_POLICY,
        "capture_request/v2",
        request["target_session_date"],
        request["provider_id"],
        request["permitted_provider_operation"],
        _ordered_list(tuple(request["ordered_universe"])),
        request["bar_interval"],
        request["request_window_start_date"],
        request["request_window_end_date"],
        str(request["request_limit"]),
        request["child_operation_version"],
        request["output_policy_version"],
    )


def _attempt_id(session_id: str, ordinal: int) -> str:
    return _identity(
        "attempt_id/v2",
        session_id,
        str(ordinal),
        PROVIDER,
        OPERATION,
        "1",
        CLAIM_POLICY,
    )


def _claim_id(attempt_id: str) -> str:
    return _identity(
        "claim_id/v2", attempt_id, "1", CLAIM_POLICY, PROVIDER, OPERATION, "1"
    )


def _reservation_id(claim_id: str) -> str:
    return _identity(
        "launch_reservation_id/v2",
        claim_id,
        "1",
        RELEASE,
        POLICY,
        CLAIM_POLICY,
    )


def _execution_id(reservation_id: str) -> str:
    return _identity("launch_execution_id/v2", reservation_id, "1", RELEASE, POLICY)


def _terminal_id(reservation_id: str) -> str:
    return _identity("terminal_id/v2", reservation_id, "1", "terminal-policy/v1")


def _selection_id(session_id: str, terminal_id: str) -> str:
    return _identity(
        "selection_id/v2", session_id, terminal_id, "1", "selection-policy/v1"
    )


def _recovery_id(
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    predecessor_state: str,
    resulting_state: str,
    ordinal: int,
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
        "recovery-policy/v1",
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


def _insert_metadata(connection: sqlite3.Connection) -> None:
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
            PROVIDER,
            OPERATION,
            POLICY,
            CLAIM_POLICY,
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
    request = _request() if request is None else request
    session_id = _session_id(request)
    request_bytes = _json(request)
    _begin(connection)
    try:
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
                EPOCH,
                POLICY,
                CLAIM_POLICY,
                request["target_session_date"],
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
            SELECT next_attempt_ordinal, request_json, request_digest
            FROM sessions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown session")
        current_ordinal, request_bytes, request_digest = row
        allocated_ordinal = current_ordinal if ordinal is None else ordinal
        attempt_id = _attempt_id(session_id, allocated_ordinal)
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
                PROVIDER,
                OPERATION,
                request_bytes,
                request_digest,
                CLAIM_POLICY,
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
    claim_id = _claim_id(attempt_id)
    evidence, evidence_digest = _evidence(f"claim:{attempt_id}")
    _begin(connection)
    try:
        attempt = connection.execute(
            """
            SELECT request_json, request_digest, provider_id,
                   permitted_provider_operation, provider_call_budget
            FROM attempts WHERE attempt_id = ?
            """,
            (attempt_id,),
        ).fetchone()
        if attempt is None:
            raise ValueError("unknown attempt")
        request_bytes, request_digest, provider_id, operation, budget = attempt
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
                CLAIM_POLICY,
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
    reservation_id = _reservation_id(claim_id)
    evidence, evidence_digest = _evidence(f"reservation:{claim_id}")
    _begin(connection)
    try:
        claim = connection.execute(
            """
            SELECT attempt_id, request_digest
            FROM provider_call_claims WHERE claim_id = ?
            """,
            (claim_id,),
        ).fetchone()
        if claim is None:
            raise ValueError("unknown claim")
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
                POLICY,
                CLAIM_POLICY,
                claim[1],
                evidence,
                evidence_digest,
                TIMESTAMP,
            ),
        )
        connection.execute(
            "UPDATE attempts SET state = 'LAUNCH_RESERVED' WHERE attempt_id = ?",
            (claim[0],),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return reservation_id


def record_execution(connection: sqlite3.Connection, reservation_id: str) -> str:
    execution_id = _execution_id(reservation_id)
    process, process_digest = _evidence(f"process:{reservation_id}")
    job, job_digest = _evidence(f"job:{reservation_id}")
    resume, resume_digest = _evidence(f"resume:{reservation_id}")
    _begin(connection)
    try:
        connection.execute(
            """
            INSERT INTO launch_executions (
                launch_execution_id, launch_reservation_id, launch_schema,
                application_release_version, authority_policy_version, phase,
                process_creation_json, process_creation_digest, job_object_json,
                job_object_digest, resume_authorization_json,
                resume_authorization_digest, post_resume_json, post_resume_digest,
                cleanup_json, cleanup_digest, created_at_utc
            ) VALUES (?, ?, 1, ?, ?, 'PRE_RESUME_READY', ?, ?, ?, ?, ?, ?,
                      NULL, NULL, NULL, NULL, ?)
            """,
            (
                execution_id,
                reservation_id,
                RELEASE,
                POLICY,
                process,
                process_digest,
                job,
                job_digest,
                resume,
                resume_digest,
                TIMESTAMP,
            ),
        )
        connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'PROCESS_CREATED', outcome_recorded_at_utc = ?
            WHERE launch_reservation_id = ?
            """,
            (TIMESTAMP, reservation_id),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return execution_id


def record_process_creation_failure(
    connection: sqlite3.Connection, reservation_id: str
) -> None:
    failure, failure_digest = _evidence(f"process-failure:{reservation_id}")
    _begin(connection)
    try:
        connection.execute(
            """
            UPDATE launch_reservations
            SET reservation_state = 'PROCESS_CREATION_FAILED',
                process_creation_failure_json = ?,
                process_creation_failure_digest = ?,
                outcome_recorded_at_utc = ?
            WHERE launch_reservation_id = ?
            """,
            (failure, failure_digest, TIMESTAMP, reservation_id),
        )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise


def record_resume_evidence(connection: sqlite3.Connection, execution_id: str) -> None:
    post_resume, post_resume_digest = _evidence(f"post-resume:{execution_id}")
    cleanup, cleanup_digest = _evidence(f"cleanup:{execution_id}")
    _begin(connection)
    try:
        connection.execute(
            """
            UPDATE launch_executions
            SET phase = 'RESUME_RECORDED', post_resume_json = ?,
                post_resume_digest = ?, cleanup_json = ?, cleanup_digest = ?
            WHERE launch_execution_id = ?
            """,
            (post_resume, post_resume_digest, cleanup, cleanup_digest, execution_id),
        )
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
    terminal_id = _terminal_id(reservation_id)
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
            ) VALUES (?, ?, 1, 'terminal-policy/v1', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                terminal_id,
                reservation_id,
                state,
                disposition,
                reservation[1],
                evidence,
                evidence_digest,
                snapshot,
                diagnostics,
                diagnostics_digest,
                TIMESTAMP,
            ),
        )
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
            SET reservation_state = 'TERMINAL_RECORDED', outcome_recorded_at_utc = ?
            WHERE launch_reservation_id = ?
            """,
            (TIMESTAMP, reservation_id),
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
    selection_id = _selection_id(session_id, terminal_id)
    evidence, evidence_digest = _evidence(f"selection:{terminal_id}")
    connection.execute(
        """
        INSERT INTO session_selections (
            selection_id, session_id, terminal_id, selection_schema,
            selection_policy_version, snapshot_digest,
            selection_evidence_json, selection_evidence_digest,
            selected_at_utc
        ) VALUES (?, ?, ?, 1, 'selection-policy/v1', ?, ?, ?, ?)
        """,
        (
            selection_id,
            session_id,
            terminal_id,
            snapshot[0],
            evidence,
            evidence_digest,
            TIMESTAMP,
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
        )
        evidence, evidence_digest = _evidence(f"recovery:{recovery_id}")
        connection.execute(
            """
            INSERT INTO manual_recoveries (
                recovery_id, session_id, recovery_ordinal, target_kind,
                target_id, action, predecessor_state, resulting_state,
                recovery_schema, recovery_policy_version,
                operator_evidence_json, operator_evidence_digest,
                created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'recovery-policy/v1', ?, ?, ?)
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
                evidence,
                evidence_digest,
                TIMESTAMP,
            ),
        )
        if action == "CLASSIFY_LAUNCH_RESERVATION":
            connection.execute(
                """
                UPDATE launch_reservations
                SET reservation_state = 'MANUAL_REVIEW', outcome_recorded_at_utc = ?
                WHERE launch_reservation_id = ?
                """,
                (TIMESTAMP, target_id),
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
                (TIMESTAMP, "recovery-approved-close", session_id),
            )
        _finish(connection, True)
    except BaseException:
        _finish(connection, False)
        raise
    return recovery_id


class FakeSideEffects:
    """Test-only hooks that can observe committed authority facts."""

    def __init__(self, observer: sqlite3.Connection) -> None:
        self.observer = observer
        self.events: list[str] = []

    def construct_provider_after_claim(self, claim_id: str) -> None:
        assert self.observer.execute(
            "SELECT state FROM provider_call_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone() == ("COMMITTED",)
        self.events.append("provider-constructed")

    def create_process_after_reservation(self, reservation_id: str) -> None:
        assert self.observer.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("COMMITTED",)
        self.events.append("process-created")

    def resume_after_evidence(self, execution_id: str) -> None:
        assert self.observer.execute(
            "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == ("RESUME_RECORDED",)
        self.events.append("resumed")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "authority.sqlite3"
    connection = _connect(path)
    _install_schema(connection)
    _insert_metadata(connection)
    _insert_migration(connection)
    connection.close()
    return path


def _seed_lifecycle(path: Path) -> dict[str, str]:
    connection = _connect(path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = record_execution(connection, reservation_id)
    record_resume_evidence(connection, execution_id)
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
    migration_id = _identity("migration_id/v1", EPOCH, "3", "migration-policy/v1")
    session_id = _session_id(request)
    attempt_id = _attempt_id(session_id, 0)
    claim_id = _claim_id(attempt_id)
    reservation_id = _reservation_id(claim_id)
    execution_id = _execution_id(reservation_id)
    terminal_id = _terminal_id(reservation_id)
    selection_id = _selection_id(session_id, terminal_id)
    recovery_id = _recovery_id(
        session_id,
        "ATTEMPT",
        attempt_id,
        "RECORD_ATTEMPT_AMBIGUITY",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
        0,
    )
    assert migration_id == "b1114fec-2247-506d-bfda-74008355b312"
    assert session_id == "e5179727-d0f1-5eac-8c01-2e2105a1a9c1"
    assert attempt_id == "be483fa1-abe3-5721-90bc-84868cf3dd19"
    assert claim_id == "6ec45116-d8a8-50ea-8d94-7ac47329c7e9"
    assert reservation_id == "222adedb-e4e7-5bbc-acc2-e7022a1785ac"
    assert execution_id == "4ce95417-de13-569f-923b-e17d2d9854c6"
    assert terminal_id == "5fda0305-878a-550f-b724-a7ce775e6a30"
    assert selection_id == "77b12359-7413-536c-a03c-d6604588aee1"
    assert recovery_id == "4fa8af52-ab1d-50b5-ba95-540c4b0fbe94"


def test_valid_lifecycle_from_metadata_to_selection(db_path: Path) -> None:
    connection = _connect(db_path)
    request = _request("2026-07-14")
    request.update(
        {
            "ordered_universe": ["DIA", "SPY", "QQQ"],
            "request_limit": 3,
            "output_policy_version": "output/v2",
        }
    )
    session_id = create_session(connection, request)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = record_execution(connection, reservation_id)
    record_resume_evidence(connection, execution_id)
    terminal_id = record_terminal(connection, reservation_id)
    selection_id = select_terminal(connection, session_id, terminal_id)
    expected_request = _json(request)
    expected_digest = _digest(expected_request)
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
    assert connection.execute("SELECT state FROM sessions").fetchone() == (
        "SUCCESS_SELECTED",
    )
    assert connection.execute("SELECT state FROM attempts").fetchone() == (
        "SUCCESS_SELECTED",
    )
    assert connection.execute(
        "SELECT selection_id FROM session_selections"
    ).fetchone() == (selection_id,)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()


def test_immediate_parent_request_mismatches_are_rejected(db_path: Path) -> None:
    connection = _connect(db_path)
    request = _request("2026-07-15")
    request["request_limit"] = 9
    session_id = create_session(connection, request)
    request_bytes = _json(request)
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
    record_process_creation_failure(connection, reservation_id)
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


def test_process_creation_failure_can_record_terminal_without_execution(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    record_process_creation_failure(connection, reservation_id)
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
        execution_id = record_execution(connection, reservation_id)
        record_resume_evidence(connection, execution_id)
    elif preparation == "process_failure":
        record_process_creation_failure(connection, reservation_id)
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
    claim_execution = record_execution(connection, claim_reservation)
    record_resume_evidence(connection, claim_execution)
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
    select_execution = record_execution(connection, select_reservation)
    record_resume_evidence(connection, select_execution)
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
    with pytest.raises(sqlite3.IntegrityError):
        record_execution(connection, values["reservation_id"])
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
    first_execution = record_execution(connection, first_reservation)
    record_resume_evidence(connection, first_execution)
    first_terminal = record_terminal(connection, first_reservation)
    second_session = create_session(connection, _request("2026-01-02"))
    second_attempt = allocate_attempt(connection, second_session)
    second_claim = commit_claim(connection, second_attempt)
    second_reservation = reserve_launch(connection, second_claim)
    second_execution = record_execution(connection, second_reservation)
    record_resume_evidence(connection, second_execution)
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
    attempt_id = _attempt_id(session_id, 0)
    request_bytes, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
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
            PROVIDER,
            OPERATION,
            request_bytes,
            request_digest,
            CLAIM_POLICY,
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
        second_session, 0
    )
    second_connection.close()


def test_recovery_ordinal_trigger_is_atomic_and_session_local(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    target_attempts: list[str] = []
    for _ in range(2):
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = record_execution(connection, reservation_id)
        record_resume_evidence(connection, execution_id)
        target_attempts.append(attempt_id)
    first_recovery = record_recovery(
        connection,
        session_id,
        "ATTEMPT",
        target_attempts[0],
        "RECORD_ATTEMPT_AMBIGUITY",
    )
    assert first_recovery == _recovery_id(
        session_id,
        "ATTEMPT",
        target_attempts[0],
        "RECORD_ATTEMPT_AMBIGUITY",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
        0,
    )
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "ATTEMPT",
            target_attempts[1],
            "RECORD_ATTEMPT_AMBIGUITY",
            ordinal=0,
        )
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "ATTEMPT",
            target_attempts[1],
            "RECORD_ATTEMPT_AMBIGUITY",
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
        "ATTEMPT",
        target_attempts[1],
        "RECORD_ATTEMPT_AMBIGUITY",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
        1,
    )
    evidence, evidence_digest = _evidence("rollback-recovery")
    connection.execute(
        """
        INSERT INTO manual_recoveries (
            recovery_id, session_id, recovery_ordinal, target_kind, target_id,
            action, predecessor_state, resulting_state, recovery_schema,
            recovery_policy_version, operator_evidence_json,
            operator_evidence_digest, created_at_utc
        ) VALUES (?, ?, 1, 'ATTEMPT', ?, 'RECORD_ATTEMPT_AMBIGUITY',
                  'LAUNCH_RESERVED', 'AMBIGUITY_RECORDED', 1,
                  'recovery-policy/v1', ?, ?, ?)
        """,
        (
            recovery_id,
            session_id,
            target_attempts[1],
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
        "ATTEMPT",
        target_attempts[1],
        "RECORD_ATTEMPT_AMBIGUITY",
    )
    assert second_recovery != first_recovery
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (2,)
    second_session = create_session(connection, _request("2026-01-02"))
    second_attempt = allocate_attempt(connection, second_session)
    second_claim = commit_claim(connection, second_attempt)
    second_reservation = reserve_launch(connection, second_claim)
    second_execution = record_execution(connection, second_reservation)
    record_resume_evidence(connection, second_execution)
    second_recovery = record_recovery(
        connection,
        second_session,
        "ATTEMPT",
        second_attempt,
        "RECORD_ATTEMPT_AMBIGUITY",
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
    hooks.create_process_after_reservation(reservation_id)
    execution_id = record_execution(connection, reservation_id)
    assert observer.execute(
        "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("PRE_RESUME_READY",)
    record_resume_evidence(connection, execution_id)
    hooks.resume_after_evidence(execution_id)
    terminal_id = record_terminal(
        connection, reservation_id, "AMBIGUOUS", "MAY_HAVE_OCCURRED"
    )
    assert terminal_id
    with pytest.raises(sqlite3.IntegrityError):
        commit_claim(connection, attempt_id)
    assert hooks.events == ["provider-constructed", "process-created", "resumed"]
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    observer.close()
    connection.close()


def test_launch_execution_evidence_is_append_only(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = record_execution(connection, reservation_id)
    post_resume, post_digest = _evidence("post-resume-test")
    cleanup, cleanup_digest = _evidence("cleanup-test")

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

    record_resume_evidence(connection, execution_id)
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
        execution_id = record_execution(connection, reservation_id)
        mutation = (
            "UPDATE launch_executions SET phase = 'TERMINAL_RECORDED' "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        )
    elif invalid_boundary == "terminal":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = record_execution(connection, reservation_id)
        record_resume_evidence(connection, execution_id)
        terminal_id = record_terminal(connection, reservation_id)
        mutation = (
            "UPDATE terminals SET terminal_state = 'FAILED' WHERE terminal_id = ?",
            (terminal_id,),
        )
    elif invalid_boundary == "selection":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = record_execution(connection, reservation_id)
        record_resume_evidence(connection, execution_id)
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
    target_attempts: list[str] = []
    for _ in range(2):
        attempt_id = allocate_attempt(setup, session_id)
        claim_id = commit_claim(setup, attempt_id)
        reservation_id = reserve_launch(setup, claim_id)
        execution_id = record_execution(setup, reservation_id)
        record_resume_evidence(setup, execution_id)
        target_attempts.append(attempt_id)
    setup.close()
    barrier = threading.Barrier(2)
    results: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(target_attempt_id: str) -> None:
        connection = _connect(db_path)
        try:
            barrier.wait()
            recovery_id = record_recovery(
                connection,
                session_id,
                "ATTEMPT",
                target_attempt_id,
                "RECORD_ATTEMPT_AMBIGUITY",
            )
            with lock:
                results.append(recovery_id)
        except BaseException as error:
            with lock:
                errors.append(error)
        finally:
            connection.close()

    threads = [
        threading.Thread(target=worker, args=(target_attempt_id,))
        for target_attempt_id in target_attempts
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
