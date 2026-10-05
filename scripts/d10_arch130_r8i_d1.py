"""Architecture-130 R8I-D1 read-only first-wake incident reconciliation.

This observer never runs the unattended controller and owns no mutation/effect
boundary. It reconstructs durable C3, decision, invocation, transition, and
operation-receipt facts for the fixed failed first wake. Durable presence and
causal attribution are deliberately separate.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import UTC, datetime
from uuid import UUID

from scripts import d10_arch128_r8_halt_windows as halt_windows
from scripts import d10_arch128_r8_terminal_halt as halt
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.runtime import (
    personal_desktop_paper_account_read_authority as account_read,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_storage as decision_storage,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_invocation_storage as invocation_storage,
)
from trading_bot.runtime.paper_operation import parse_paper_operation_receipt
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_OPERATIONS,
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS,
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
    PinnedTradingPaperReadSession,
    WindowsPaperReadNativeApi,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    personal_desktop_unattended_capture_request,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    completed_xnys_session_at,
    next_xnys_execution_session,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    verify_personal_desktop_unattended_paper_invocation,
)
from trading_bot.runtime.windows_authority import PRODUCTION_AUTHORITY_PATHS
from trading_bot.runtime.windows_authority_schema import (
    load_approved_sqlite_authority_build,
)
from trading_bot.runtime.windows_authority_sqlite import (
    open_read_only_sqlite_connection,
)
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    require_initialized_supported_authority_evidence,
    validate_installed_authority_complete,
)

SCHEMA = "architecture-130-r8i-d1-incident-reconciliation/v1"
INCIDENT_START = datetime(2026, 10, 1, 8, 30, 9, 370767, tzinfo=UTC)
INCIDENT_END = datetime(2026, 10, 1, 8, 30, 21, 815609, tzinfo=UTC)
EXPECTED_COMPLETED_SESSION = "2026-09-30"
EXPECTED_NEXT_EXECUTION_SESSION = "2026-10-01"
MAX_C3_ATTEMPTS = 16
_UUID_TEXT = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_INVOCATION_FINAL = re.compile(rf"unattended-paper-invocation-({_UUID_TEXT})")
_INVOCATION_STAGING = re.compile(
    rf"\.unattended-paper-invocation-({_UUID_TEXT})\.staging"
)
_DECISION_FINAL = re.compile(rf"unattended-paper-decision-({_UUID_TEXT})")
_DECISION_STAGING = re.compile(rf"\.unattended-paper-decision-({_UUID_TEXT})\.staging")
_OPERATION = re.compile(rf"paper-operation-({_UUID_TEXT})")
_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
CLOSED_EFFECTS = (
    "production_filesystem_mutation",
    "evidence_mutation",
    "lease_mutation",
    "scheduler_mutation",
    "manual_task_start",
    "source_launch",
    "provider",
    "decision_publication",
    "Paper-v2",
    "broker",
    "live",
)


class IncidentReconciliationBlocked(RuntimeError):
    """Fixed incident durable truth could not be reconstructed safely."""


def _uuid(value: object, label: str) -> str:
    if type(value) is not str:
        raise IncidentReconciliationBlocked(f"{label}_uuid_type")
    try:
        parsed = UUID(value)
    except ValueError:
        raise IncidentReconciliationBlocked(f"{label}_uuid_invalid") from None
    if str(parsed) != value:
        raise IncidentReconciliationBlocked(f"{label}_uuid_noncanonical")
    return value


def _second_bucket(value: object) -> str | None:
    """Classify immutable DB second-resolution timestamps conservatively."""
    if value is None:
        return None
    if type(value) is not str or _TIMESTAMP.fullmatch(value) is None:
        raise IncidentReconciliationBlocked("authority_timestamp_invalid")
    if value == "2026-10-01T08:30:09Z":
        return "BOUNDARY_SECOND"
    if "2026-10-01T08:30:10Z" <= value <= "2026-10-01T08:30:21Z":
        return "DEFINITE_INCIDENT_SECOND"
    return "OUTSIDE_INCIDENT_SECONDS"


def _calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _sessions() -> tuple[object, object]:
    completed = completed_xnys_session_at(INCIDENT_START)
    execution = next_xnys_execution_session(completed)
    if (
        completed.session_date.isoformat() != EXPECTED_COMPLETED_SESSION
        or execution.session_date.isoformat() != EXPECTED_NEXT_EXECUTION_SESSION
    ):
        raise IncidentReconciliationBlocked("incident_session_derivation_drift")
    return completed, execution


def _read_c3_inventory(
    validation: InstalledAuthorityValidation,
    completed: object,
) -> dict[str, object]:
    production = require_initialized_supported_authority_evidence(validation)
    bootstrap = validation.bootstrap_verification.bootstrap
    request = personal_desktop_unattended_capture_request(completed)
    request_bytes = request.canonical_c2_request_json()
    request_digest = hashlib.sha256(request_bytes).digest()
    sqlite_build = load_approved_sqlite_authority_build()
    if sqlite_build.digest.hex() != production.sqlite_build_manifest_digest:
        raise IncidentReconciliationBlocked("sqlite_build_drift")

    connection: sqlite3.Connection | None = None
    try:
        connection = open_read_only_sqlite_connection(
            str(PRODUCTION_AUTHORITY_PATHS.database),
            vfs=sqlite_build.vfs,
        )
        changes = connection.total_changes
        connection.execute("PRAGMA query_only = ON")
        if connection.execute("PRAGMA query_only").fetchone() != (1,):
            raise IncidentReconciliationBlocked("c3_query_only_not_enabled")
        connection.execute("BEGIN")
        session_rows = connection.execute(
            """
            SELECT session_id, state, target_session_date, created_at_utc, closed_at_utc
            FROM sessions
            WHERE authority_epoch_id = ? AND request_json = ? AND request_digest = ?
            """,
            (bootstrap.authority_epoch_id, request_bytes, request_digest),
        ).fetchall()
        if len(session_rows) > 1:
            raise IncidentReconciliationBlocked("c3_duplicate_source_session")
        if not session_rows:
            if connection.total_changes != changes:
                raise IncidentReconciliationBlocked("c3_read_mutated_database")
            connection.rollback()
            return {
                "source_session": None,
                "attempt_count": 0,
                "attempts": [],
                "selected": None,
                "provider_attribution": "NO_DURABLE_SOURCE_SESSION",
            }

        session_id, state, target_date, created_at, closed_at = session_rows[0]
        session_id = _uuid(session_id, "c3_session")
        attempt_rows = connection.execute(
            """
            SELECT
                a.attempt_id, a.ordinal, a.state, a.created_at_utc,
                c.claim_id, c.committed_at_utc,
                r.launch_reservation_id, r.reservation_state,
                r.committed_at_utc, r.process_intent_committed_at_utc,
                r.outcome_recorded_at_utc,
                x.launch_execution_id, x.phase, x.created_at_utc,
                x.resume_intent_committed_at_utc,
                t.terminal_id, t.terminal_state, t.provider_call_disposition,
                t.recorded_at_utc,
                json_extract(t.evidence_json, '$.snapshot_id'),
                ss.selection_id, ss.selected_at_utc
            FROM attempts AS a
            LEFT JOIN provider_call_claims AS c ON c.attempt_id = a.attempt_id
            LEFT JOIN launch_reservations AS r ON r.claim_id = c.claim_id
            LEFT JOIN launch_executions AS x
                ON x.launch_reservation_id = r.launch_reservation_id
            LEFT JOIN terminals AS t
                ON t.launch_reservation_id = r.launch_reservation_id
            LEFT JOIN session_selections AS ss ON ss.terminal_id = t.terminal_id
            WHERE a.session_id = ?
            ORDER BY a.ordinal
            LIMIT ?
            """,
            (session_id, MAX_C3_ATTEMPTS + 1),
        ).fetchall()
        if len(attempt_rows) > MAX_C3_ATTEMPTS:
            raise IncidentReconciliationBlocked("c3_attempt_bound_exceeded")
        if connection.total_changes != changes:
            raise IncidentReconciliationBlocked("c3_read_mutated_database")
        connection.rollback()
    except IncidentReconciliationBlocked:
        if connection is not None and connection.in_transaction:
            connection.rollback()
        raise
    except BaseException as exc:
        if connection is not None and connection.in_transaction:
            connection.rollback()
        raise IncidentReconciliationBlocked("c3_inventory_read_failed") from exc
    finally:
        if connection is not None:
            connection.close()

    attempts: list[dict[str, object]] = []
    for row in attempt_rows:
        (
            attempt_id,
            ordinal,
            attempt_state,
            attempt_created,
            claim_id,
            claim_committed,
            reservation_id,
            reservation_state,
            reservation_committed,
            process_intent_committed,
            reservation_outcome,
            execution_id,
            execution_phase,
            execution_created,
            resume_intent_committed,
            terminal_id,
            terminal_state,
            disposition,
            terminal_recorded,
            snapshot_id,
            selection_id,
            selected_at,
        ) = row
        attempt = {
            "attempt_id": _uuid(attempt_id, "c3_attempt"),
            "ordinal": ordinal,
            "state": attempt_state,
            "created_at_utc": attempt_created,
            "created_bucket": _second_bucket(attempt_created),
            "claim_id": None if claim_id is None else _uuid(claim_id, "c3_claim"),
            "claim_committed_at_utc": claim_committed,
            "reservation_id": (
                None
                if reservation_id is None
                else _uuid(reservation_id, "c3_reservation")
            ),
            "reservation_state": reservation_state,
            "reservation_committed_at_utc": reservation_committed,
            "process_intent_committed_at_utc": process_intent_committed,
            "reservation_outcome_recorded_at_utc": reservation_outcome,
            "execution_id": (
                None if execution_id is None else _uuid(execution_id, "c3_execution")
            ),
            "execution_phase": execution_phase,
            "execution_created_at_utc": execution_created,
            "resume_intent_committed_at_utc": resume_intent_committed,
            "terminal_id": (
                None if terminal_id is None else _uuid(terminal_id, "c3_terminal")
            ),
            "terminal_state": terminal_state,
            "provider_call_disposition": disposition,
            "terminal_recorded_at_utc": terminal_recorded,
            "terminal_bucket": _second_bucket(terminal_recorded),
            "snapshot_id": (
                None if snapshot_id is None else _uuid(snapshot_id, "c3_snapshot")
            ),
            "selection_id": (
                None if selection_id is None else _uuid(selection_id, "c3_selection")
            ),
            "selected_at_utc": selected_at,
            "selected_bucket": _second_bucket(selected_at),
        }
        attempts.append(attempt)

    selected_rows = [item for item in attempts if item["selection_id"] is not None]
    if len(selected_rows) > 1:
        raise IncidentReconciliationBlocked("c3_multiple_selected_attempts")
    selected = None
    if selected_rows:
        item = selected_rows[0]
        selected = {
            "selection_id": item["selection_id"],
            "snapshot_id": item["snapshot_id"],
            "selected_at_utc": item["selected_at_utc"],
            "selected_bucket": item["selected_bucket"],
            "attempt_id": item["attempt_id"],
            "terminal_id": item["terminal_id"],
        }

    confirmed = [
        item
        for item in attempts
        if item["provider_call_disposition"] == "CONFIRMED"
        and item["terminal_state"] == "SUCCEEDED"
    ]
    definite = [
        item
        for item in confirmed
        if item["created_bucket"] == "DEFINITE_INCIDENT_SECOND"
        and item["terminal_bucket"] == "DEFINITE_INCIDENT_SECOND"
    ]
    boundary = [
        item
        for item in confirmed
        if item["created_bucket"] in {"BOUNDARY_SECOND", "DEFINITE_INCIDENT_SECOND"}
        and item["terminal_bucket"] in {"BOUNDARY_SECOND", "DEFINITE_INCIDENT_SECOND"}
    ]
    if definite:
        attribution = "CONFIRMED_INCIDENT_WINDOW"
    elif boundary:
        attribution = "MAY_HAVE_OCCURRED_IN_BOUNDARY_SECOND"
    elif any(
        item["created_bucket"] in {"BOUNDARY_SECOND", "DEFINITE_INCIDENT_SECOND"}
        or item["terminal_bucket"] in {"BOUNDARY_SECOND", "DEFINITE_INCIDENT_SECOND"}
        for item in attempts
    ):
        attribution = "INCIDENT_WINDOW_LINEAGE_WITHOUT_CONFIRMED_PROVIDER"
    else:
        attribution = "NO_INCIDENT_WINDOW_DURABLE_ATTEMPT"

    return {
        "source_session": {
            "session_id": session_id,
            "state": state,
            "target_session_date": target_date,
            "created_at_utc": created_at,
            "closed_at_utc": closed_at,
        },
        "attempt_count": len(attempts),
        "attempts": attempts,
        "selected": selected,
        "provider_attribution": attribution,
    }


class _TracingPaperReadNativeApi(WindowsPaperReadNativeApi):
    """Read-only native API wrapper that records only the last fixed PD1B role."""

    def __init__(self) -> None:
        super().__init__()
        self.last_role: str | None = None

    def inspect(self, handle: object, path: str, kind: object):
        self.last_role = self.object_spec(path).role.value
        return super().inspect(handle, path, kind)


def _paper_session(
    trading_sid: str,
    api: WindowsPaperReadNativeApi,
) -> PinnedTradingPaperReadSession:
    return PinnedTradingPaperReadSession(api, trading_sid)


def _decision_inventory(
    trading_sid: str,
    completed: object,
    execution: object,
    api: WindowsPaperReadNativeApi,
) -> dict[str, object]:
    calendar = personal_desktop_unattended_decision_calendar()
    final: list[dict[str, object]] = []
    staging: list[str] = []
    with _paper_session(trading_sid, api) as session:
        for name in session.names(PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS):
            match = _DECISION_FINAL.fullmatch(name)
            staged = _DECISION_STAGING.fullmatch(name)
            if staged is not None:
                identity = _uuid(staged.group(1), "decision_staging")
                session.pin(
                    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS + "\\" + name
                )
                staging.append(identity)
                continue
            if match is None:
                raise IncidentReconciliationBlocked("decision_namespace_unknown_entry")
            identity = UUID(_uuid(match.group(1), "decision"))
            directory = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS + "\\" + name
            artifact_name = decision_storage.unattended_paper_decision_artifact_name(
                identity
            )
            if session.names(directory) != (artifact_name,):
                raise IncidentReconciliationBlocked(
                    "decision_directory_contents_invalid"
                )
            binding = verify_personal_desktop_unattended_paper_decision_intent(
                session.read(directory + "\\" + artifact_name),
                calendar,
                expected_decision_id=identity,
            )
            decision = binding.decision
            final.append(
                {
                    "decision_id": str(decision.decision_id),
                    "selected_session": (
                        decision.selected_session.session_date.isoformat()
                    ),
                    "execution_session": (
                        decision.intended_execution_session.session_date.isoformat()
                    ),
                    "current_selection_id": str(decision.current_c3.selection_id),
                    "current_snapshot_id": str(decision.current_c3.snapshot_id),
                    "predecessor_checkpoint_id": str(
                        decision.predecessor_checkpoint_id
                    ),
                    "artifact_sha256": binding.artifact_sha256,
                    "artifact_byte_length": binding.artifact_byte_length,
                }
            )
    next_session = execution.session_date.isoformat()
    completed_session = completed.session_date.isoformat()
    relevant = [
        item
        for item in final
        if item["selected_session"] == completed_session
        and item["execution_session"] == next_session
    ]
    return {
        "finalized_count": len(final),
        "staging_count": len(staging),
        "staging_ids": sorted(staging),
        "incident_next_decisions": relevant,
    }


def _invocation_inventory(
    trading_sid: str,
    completed: object,
    api: WindowsPaperReadNativeApi,
) -> dict[str, object]:
    calendar = _calendar()
    final: list[dict[str, object]] = []
    staging: list[str] = []
    with _paper_session(trading_sid, api) as session:
        for name in session.names(PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS):
            match = _INVOCATION_FINAL.fullmatch(name)
            staged = _INVOCATION_STAGING.fullmatch(name)
            if staged is not None:
                identity = _uuid(staged.group(1), "invocation_staging")
                session.pin(
                    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS + "\\" + name
                )
                staging.append(identity)
                continue
            if match is None:
                raise IncidentReconciliationBlocked(
                    "invocation_namespace_unknown_entry"
                )
            identity = UUID(_uuid(match.group(1), "invocation"))
            directory = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS + "\\" + name
            artifact_name = (
                invocation_storage.unattended_paper_invocation_artifact_name(identity)
            )
            if session.names(directory) != (artifact_name,):
                raise IncidentReconciliationBlocked(
                    "invocation_directory_contents_invalid"
                )
            binding = verify_personal_desktop_unattended_paper_invocation(
                session.read(directory + "\\" + artifact_name),
                calendar,
                expected_invocation_id=identity,
            )
            invocation = binding.invocation
            final.append(
                {
                    "invocation_id": str(invocation.invocation_id),
                    "execution_session": (
                        invocation.execution_session.session_date.isoformat()
                    ),
                    "selection_id": str(invocation.selection_id),
                    "selected_snapshot_id": str(invocation.selected_snapshot_id),
                    "plan_id": str(invocation.plan_id),
                    "predecessor_checkpoint_id": str(
                        invocation.predecessor_checkpoint_id
                    ),
                    "artifact_sha256": binding.artifact_sha256,
                    "artifact_byte_length": binding.artifact_byte_length,
                }
            )
    completed_session = completed.session_date.isoformat()
    return {
        "finalized_count": len(final),
        "staging_count": len(staging),
        "staging_ids": sorted(staging),
        "incident_execution_invocations": [
            item for item in final if item["execution_session"] == completed_session
        ],
    }


def _paper_operation_inventory(
    trading_sid: str,
    api: WindowsPaperReadNativeApi,
) -> dict[str, object]:
    operations: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    with _paper_session(trading_sid, api) as session:
        operation_names = session.names(PERSONAL_DESKTOP_PAPER_V2_OPERATIONS)
        for name in operation_names:
            match = _OPERATION.fullmatch(name)
            if match is None:
                raise IncidentReconciliationBlocked("operation_namespace_unknown_entry")
            operation_id = _uuid(match.group(1), "operation")
            directory = PERSONAL_DESKTOP_PAPER_V2_OPERATIONS + "\\" + name
            contents = session.names(directory)
            expected = f"paper-operation-receipt-{operation_id}.json"
            if contents == ():
                operations.append(
                    {
                        "operation_id": operation_id,
                        "receipt_present": False,
                        "status": None,
                        "outcome": None,
                        "application_id": None,
                        "snapshot_id": None,
                    }
                )
                continue
            if contents != (expected,):
                raise IncidentReconciliationBlocked(
                    "operation_directory_contents_invalid"
                )
            receipt = parse_paper_operation_receipt(
                session.read(directory + "\\" + expected)
            )
            if str(receipt.receipt_id) != operation_id:
                raise IncidentReconciliationBlocked("operation_receipt_identity_drift")
            operations.append(
                {
                    "operation_id": operation_id,
                    "receipt_present": True,
                    "status": receipt.status.value,
                    "outcome": (
                        None if receipt.outcome is None else receipt.outcome.value
                    ),
                    "application_id": str(receipt.application_id),
                    "snapshot_id": str(
                        receipt.intent.completed_snapshot_artifact.artifact_id
                    ),
                }
            )

        runtime_names = session.names(PERSONAL_DESKTOP_PAPER_V2_RUNTIME)
        reserved = {
            PERSONAL_DESKTOP_PAPER_V2_OPERATIONS.rsplit("\\", 1)[-1],
            PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS.rsplit("\\", 1)[-1],
            PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS.rsplit("\\", 1)[-1],
        }
        for name in runtime_names:
            if name in reserved:
                continue
            transition = account_read._read_transition(session, name)
            evidence = transition.report.evidence
            transitions.append(
                {
                    "application_id": str(evidence.application_id),
                    "cycle_result_id": str(evidence.cycle_result_id),
                    "snapshot_id": str(evidence.request.snapshot_reference.snapshot_id),
                    "successor_checkpoint_id": str(transition.checkpoint.checkpoint_id),
                    "status": evidence.status.value,
                }
            )
    return {
        "operation_count": len(operations),
        "operations": operations,
        "transition_count": len(transitions),
        "transitions": transitions,
    }


def _decision_attribution(c3: dict[str, object], decisions: dict[str, object]) -> str:
    relevant = decisions["incident_next_decisions"]
    if type(relevant) is not list:
        raise IncidentReconciliationBlocked("decision_inventory_shape_invalid")
    if len(relevant) == 0:
        return "NO_DURABLE_INCIDENT_NEXT_DECISION"
    if len(relevant) != 1:
        return "CONFLICTING_INCIDENT_NEXT_DECISIONS"
    selected = c3["selected"]
    if type(selected) is not dict:
        return "PRESENT_WITHOUT_INCIDENT_C3_SELECTION"
    decision = relevant[0]
    if (
        decision["current_selection_id"] == selected["selection_id"]
        and decision["current_snapshot_id"] == selected["snapshot_id"]
    ):
        return "INCIDENT_C3_DEPENDENT_NO_PUBLICATION_TIMESTAMP"
    return "PRESENT_NOT_BOUND_TO_INCIDENT_C3"


def _paper_attribution(
    c3: dict[str, object],
    invocations: dict[str, object],
    operations: dict[str, object],
) -> str:
    selected = c3["selected"]
    if type(selected) is not dict or selected["snapshot_id"] is None:
        return "NO_INCIDENT_C3_SELECTION_FOR_PAPER_ATTRIBUTION"
    snapshot_id = selected["snapshot_id"]
    transition_match = any(
        item["snapshot_id"] == snapshot_id for item in operations["transitions"]
    )
    receipt_match = any(
        item["receipt_present"] is True and item["snapshot_id"] == snapshot_id
        for item in operations["operations"]
    )
    if transition_match or receipt_match:
        return "INCIDENT_C3_DEPENDENT_PAPER_STATE_NO_EFFECT_TIMESTAMP"
    invocation_match = any(
        item["selected_snapshot_id"] == snapshot_id
        for item in invocations["incident_execution_invocations"]
    )
    if invocation_match:
        return "INCIDENT_C3_DEPENDENT_INVOCATION_NO_EFFECT_TIMESTAMP"
    return "NO_INCIDENT_C3_DEPENDENT_PAPER_STATE"


def _highest_dependency(
    provider: str,
    decision: str,
    paper: str,
) -> str:
    if "PAPER_STATE" in paper:
        return "PAPER_V2_DURABLE_STATE"
    if "INVOCATION" in paper:
        return "PAPER_V2_INVOCATION"
    if "INCIDENT_C3_DEPENDENT" in decision:
        return "DECISION_ARTIFACT"
    if provider in {
        "CONFIRMED_INCIDENT_WINDOW",
        "MAY_HAVE_OCCURRED_IN_BOUNDARY_SECOND",
        "INCIDENT_WINDOW_LINEAGE_WITHOUT_CONFIRMED_PROVIDER",
    }:
        return "C3_PROVIDER_LINEAGE"
    return "NO_INCIDENT_DEPENDENT_DURABLE_STAGE"


def _base() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "incident": "EXACT_TERMINAL_FIRST_WAKE",
        "failed_child_output_bytes": "UNRECOVERABLE_NOT_PERSISTED",
        "failed_child_effects": "UNKNOWN_REQUIRES_READ_ONLY_RECONCILIATION",
        **dict.fromkeys(CLOSED_EFFECTS, "NOT_RUN"),
    }


def preflight() -> dict[str, object]:
    """Reconstruct fixed durable incident truth without any effect capability."""
    result = _base()
    paper_api: _TracingPaperReadNativeApi | None = None
    paper_read_stage: str | None = None
    try:
        snapshot = halt_windows.ReadOnlyWindowsHost().observe()
        halt.require_snapshot(snapshot, enabled=False)

        completed, execution = _sessions()
        before = validate_installed_authority_complete()
        production = require_initialized_supported_authority_evidence(before)
        c3 = _read_c3_inventory(before, completed)
        paper_api = _TracingPaperReadNativeApi()

        paper_read_stage = "decision_inventory"
        decisions = _decision_inventory(
            before.provisioning.trading_sid,
            completed,
            execution,
            paper_api,
        )
        paper_read_stage = "invocation_inventory"
        invocations = _invocation_inventory(
            before.provisioning.trading_sid,
            completed,
            paper_api,
        )
        paper_read_stage = "paper_operation_inventory"
        operations = _paper_operation_inventory(
            before.provisioning.trading_sid,
            paper_api,
        )
        paper_read_stage = None
        after = validate_installed_authority_complete()
        if after != before:
            raise IncidentReconciliationBlocked("authority_validation_drift")

        provider = c3["provider_attribution"]
        if type(provider) is not str:
            raise IncidentReconciliationBlocked("provider_attribution_invalid")
        decision = _decision_attribution(c3, decisions)
        paper = _paper_attribution(c3, invocations, operations)
        result.update(
            status="PASS",
            incident_start_utc=INCIDENT_START.isoformat().replace("+00:00", "Z"),
            incident_end_utc=INCIDENT_END.isoformat().replace("+00:00", "Z"),
            incident_completed_session=completed.session_date.isoformat(),
            incident_next_execution_session=execution.session_date.isoformat(),
            scheduler_state="DISABLED_NON_RUNNING_EXACT",
            incident_evidence_sha256=snapshot.evidence["evidence_sha256"],
            incident_evidence_byte_length=snapshot.evidence["evidence_byte_length"],
            activation_lease_sha256=snapshot.lease["sha256"],
            authority_database_path=production.database_path,
            authority_schema_id=production.schema_id,
            authority_schema_version=production.schema_version,
            c3=c3,
            decisions=decisions,
            invocations=invocations,
            paper_operations=operations,
            attribution={
                "provider": provider,
                "decision_publication": decision,
                "Paper-v2": paper,
                "highest_durable_dependency": _highest_dependency(
                    provider, decision, paper
                ),
                "causal_limit": (
                    "decision/invocation/receipt/transition artifacts have no "
                    "trusted wall-clock publication/effect timestamp; dependency "
                    "on incident C3 does not by itself prove failed-child authorship"
                ),
            },
            child_output_diagnosis={
                "exact_rejected_stdout": "UNRECOVERABLE",
                "exact_rejected_stderr": "UNRECOVERABLE",
                "guard_reason": "CHILD_OUTPUT_INVALID",
                "possible_rejection_classes": [
                    "CHILD_EXIT_NONZERO",
                    "NONEMPTY_STDERR",
                    "STDOUT_BOUND_OR_LINE_COUNT",
                    "STDOUT_JSON_PARSE",
                    "STDOUT_SCHEMA_OR_SEMANTIC_VALIDATION",
                ],
            },
        )
    except Exception as exc:
        result["reason"] = type(exc).__name__
        result["detail"] = str(exc)
        if paper_api is not None and paper_api.last_role is not None:
            result["paper_security_diagnostic"] = {
                "stage": paper_read_stage,
                "last_role": paper_api.last_role,
            }
    return result
