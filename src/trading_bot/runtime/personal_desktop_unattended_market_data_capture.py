"""Effects-closed Architecture-111 unattended C3 production composition."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from importlib import import_module
from typing import Protocol
from uuid import UUID

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SessionIndexedSelectedC3SnapshotReadResult,
    WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority,
    personal_desktop_unattended_capture_request,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    completed_xnys_session_at,
    next_xnys_execution_session,
)
from trading_bot.runtime.windows_authority import PRODUCTION_AUTHORITY_PATHS
from trading_bot.runtime.windows_authority_schema import (
    load_approved_sqlite_authority_build,
)
from trading_bot.runtime.windows_authority_sqlite import (
    open_read_only_sqlite_connection,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    acquire_validated_production_authority,
    require_open_connection_matches_validated_authority,
    require_validated_production_authority,
)
from trading_bot.runtime.windows_effectful_capture import (
    ProductionCapturePlan,
    ProductionCaptureRequest,
    prepare_production_capture_plan,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    ProductionCaptureInvocationResult,
    WindowsEffectfulDailySnapshotCapture,
)

PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED = False


class PersonalDesktopUnattendedMarketDataCaptureError(Exception):
    """Unattended market-data qualification failed closed."""


class PersonalDesktopUnattendedMarketDataCaptureClassification(StrEnum):
    """Stable G5 read-only preflight classifications."""

    NO_NEW_COMPLETED_SESSION = "NO_NEW_COMPLETED_SESSION"
    CAPTURE_REQUIRED = "CAPTURE_REQUIRED"
    PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS = "PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS"
    SESSION_GAP = "SESSION_GAP"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedSelectedC3Evidence:
    """Non-authorizing selected-C3 evidence safe for G6 classification."""

    selection_id: UUID
    session_id: UUID
    attempt_id: UUID
    terminal_id: UUID
    snapshot_id: UUID
    artifact_sha256: str
    artifact_byte_length: int


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedMarketDataCaptureResult:
    """Immutable evidence from one qualification and optional C3 invocation."""

    classification: PersonalDesktopUnattendedMarketDataCaptureClassification
    eligible_completed_session: TradingSession
    capture_request: ProductionCaptureRequest
    canonical_c2_request_sha256: str
    selected_c3: PersonalDesktopUnattendedSelectedC3Evidence | None = None
    invocation: ProductionCaptureInvocationResult | None = None

    def __post_init__(self) -> None:
        classification_type = PersonalDesktopUnattendedMarketDataCaptureClassification
        if type(self.classification) is not classification_type:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "unattended capture classification is invalid"
            )
        if type(self.eligible_completed_session) is not TradingSession:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "eligible completed session is invalid"
            )
        expected_request = personal_desktop_unattended_capture_request(
            self.eligible_completed_session
        )
        if self.capture_request != expected_request:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "unattended capture request is not source-owned"
            )
        expected_digest = hashlib.sha256(
            expected_request.canonical_c2_request_json()
        ).hexdigest()
        if self.canonical_c2_request_sha256 != expected_digest:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "unattended capture request digest is invalid"
            )
        if self.selected_c3 is not None and (
            type(self.selected_c3) is not PersonalDesktopUnattendedSelectedC3Evidence
            or self.classification is not classification_type.NO_NEW_COMPLETED_SESSION
        ):
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "selected C3 evidence is inconsistent with classification"
            )
        if self.invocation is not None and (
            type(self.invocation) is not ProductionCaptureInvocationResult
            or self.classification is not classification_type.CAPTURE_REQUIRED
        ):
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "C3 invocation evidence is inconsistent with classification"
            )


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedC3PreflightReadResult:
    """Query-only durable C2/C3 facts for one nominated session."""

    classification: PersonalDesktopUnattendedMarketDataCaptureClassification
    selected_session_id: str | None = None
    selected_selection_id: str | None = None

    def __post_init__(self) -> None:
        classifications = PersonalDesktopUnattendedMarketDataCaptureClassification
        if type(self.classification) is not classifications:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "durable C3 preflight classification is invalid"
            )
        selected = (self.selected_session_id, self.selected_selection_id)
        if self.classification is classifications.NO_NEW_COMPLETED_SESSION:
            if any(value is None for value in selected):
                raise PersonalDesktopUnattendedMarketDataCaptureError(
                    "selected C3 preflight evidence is incomplete"
                )
            for field_name, value in zip(
                ("selected session ID", "selected selection ID"),
                selected,
                strict=True,
            ):
                _canonical_uuid_text(value, field_name)
        elif any(value is not None for value in selected):
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "non-selected C3 preflight cannot expose selected IDs"
            )


class _SelectedReader(Protocol):
    def read_selected_snapshot_for_session(
        self, session: TradingSession
    ) -> SessionIndexedSelectedC3SnapshotReadResult: ...


class _CaptureRoot(Protocol):
    def capture_prepared_once(
        self, plan: ProductionCapturePlan
    ) -> ProductionCaptureInvocationResult: ...

    def close(self) -> None: ...


class WindowsPersonalDesktopUnattendedC3PreflightAuthority:
    """Read-only C2/C3 state inspection bound to the current C1 authority."""

    __slots__ = ("_authority", "_sqlite_vfs")

    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        authority = require_validated_production_authority(authority)
        sqlite_build = load_approved_sqlite_authority_build()
        if sqlite_build.digest.hex() != authority.sqlite_build_manifest_digest:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "approved SQLite build does not match production authority"
            )
        self._authority = authority
        self._sqlite_vfs = sqlite_build.vfs

    def inspect(
        self, session: TradingSession
    ) -> PersonalDesktopUnattendedC3PreflightReadResult:
        connection: sqlite3.Connection | None = None
        try:
            connection = open_read_only_sqlite_connection(
                str(PRODUCTION_AUTHORITY_PATHS.database),
                vfs=self._sqlite_vfs,
            )
            require_open_connection_matches_validated_authority(
                self._authority,
                connection,
            )
            return _inspect_durable_c3_preflight(
                connection,
                self._authority.authority_epoch_id,
                session,
            )
        except PersonalDesktopUnattendedMarketDataCaptureError:
            raise
        except BaseException as error:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "unattended C3 preflight failed closed"
            ) from error
        finally:
            if connection is not None:
                connection.close()


def run_personal_desktop_unattended_market_data_capture() -> (
    PersonalDesktopUnattendedMarketDataCaptureResult
):
    """Qualify one unattended C3 attempt with no caller semantic arguments."""

    authority = acquire_validated_production_authority()
    observed_at = datetime.now(UTC)
    return reconcile_personal_desktop_unattended_market_data_capture(
        authority,
        observed_at,
    )


def reconcile_personal_desktop_unattended_market_data_capture(
    authority: ValidatedProductionAuthority,
    observed_at: datetime,
) -> PersonalDesktopUnattendedMarketDataCaptureResult:
    """Compose G5 from one already-validated C1 and factual observation.

    This is the production composition seam used by G6 so the daily controller
    owns the single wall-clock observation.  It does not add semantic caller
    input: both values are obtained inside the zero-argument G6 boundary.
    """

    authority = require_validated_production_authority(authority)
    return _run_personal_desktop_unattended_market_data_capture(
        authority,
        observed_at,
        preflight=WindowsPersonalDesktopUnattendedC3PreflightAuthority(authority),
        selected_reader=WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(
            authority
        ),
        capture_factory=WindowsEffectfulDailySnapshotCapture,
        production=True,
    )


def inspect_personal_desktop_unattended_c3_preflight_for_test(
    connection: sqlite3.Connection,
    authority_epoch_id: str,
    session: TradingSession,
) -> PersonalDesktopUnattendedC3PreflightReadResult:
    """Inspect disposable C2/C3 state without issuing production provenance."""

    return _inspect_durable_c3_preflight(connection, authority_epoch_id, session)


def run_personal_desktop_unattended_market_data_capture_for_test(
    authority: ValidatedProductionAuthority,
    observed_at: datetime,
    *,
    preflight: object,
    selected_reader: _SelectedReader,
    capture_factory: Callable[[ValidatedProductionAuthority], _CaptureRoot],
) -> PersonalDesktopUnattendedMarketDataCaptureResult:
    """Exercise G5 with explicit factual time and disposable fake boundaries."""

    return _run_personal_desktop_unattended_market_data_capture(
        authority,
        observed_at,
        preflight=preflight,
        selected_reader=selected_reader,
        capture_factory=capture_factory,
        production=False,
    )


def _run_personal_desktop_unattended_market_data_capture(
    authority: ValidatedProductionAuthority,
    observed_at: datetime,
    *,
    preflight: object,
    selected_reader: _SelectedReader,
    capture_factory: Callable[[ValidatedProductionAuthority], _CaptureRoot],
    production: bool,
) -> PersonalDesktopUnattendedMarketDataCaptureResult:
    if production:
        authority = require_validated_production_authority(authority)
    elif type(authority) is not ValidatedProductionAuthority:
        raise TypeError("disposable G5 seam requires test C1 authority evidence")
    session = completed_xnys_session_at(observed_at)
    request = personal_desktop_unattended_capture_request(session)
    plan = prepare_production_capture_plan(request, observed_at)
    digest = plan.c2_request_digest
    try:
        durable = preflight.inspect(session)  # type: ignore[attr-defined]
    except BaseException:
        return _result(
            PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED,
            session,
            request,
            digest,
        )
    if type(durable) is not PersonalDesktopUnattendedC3PreflightReadResult:
        return _result(
            PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED,
            session,
            request,
            digest,
        )
    classifications = PersonalDesktopUnattendedMarketDataCaptureClassification
    if durable.classification is classifications.NO_NEW_COMPLETED_SESSION:
        try:
            selected = selected_reader.read_selected_snapshot_for_session(session)
            evidence = _selected_evidence(selected)
        except BaseException:
            return _result(
                PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED,
                session,
                request,
                digest,
            )
        if (
            str(evidence.session_id) != durable.selected_session_id
            or str(evidence.selection_id) != durable.selected_selection_id
        ):
            return _result(
                PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED,
                session,
                request,
                digest,
            )
        return _result(
            durable.classification,
            session,
            request,
            digest,
            selected_c3=evidence,
        )
    if (
        durable.classification
        is not PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED
    ):
        return _result(durable.classification, session, request, digest)

    gate_state = _effect_gate_state()
    if gate_state == "CLOSED":
        return _result(durable.classification, session, request, digest)
    if gate_state != "OPEN":
        return _result(
            PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED,
            session,
            request,
            digest,
        )

    capture = capture_factory(authority)
    try:
        invocation = capture.capture_prepared_once(plan)
    finally:
        capture.close()
    return _result(
        durable.classification,
        session,
        request,
        digest,
        invocation=invocation,
    )


def _inspect_durable_c3_preflight(
    connection: sqlite3.Connection,
    authority_epoch_id: str,
    nominated_session: TradingSession,
) -> PersonalDesktopUnattendedC3PreflightReadResult:
    if type(connection) is not sqlite3.Connection:
        raise TypeError("C3 preflight requires an exact sqlite3.Connection")
    if type(authority_epoch_id) is not str or not authority_epoch_id:
        raise PersonalDesktopUnattendedMarketDataCaptureError(
            "authority epoch ID is invalid"
        )
    if type(nominated_session) is not TradingSession:
        raise PersonalDesktopUnattendedMarketDataCaptureError(
            "nominated session is invalid"
        )
    initial_changes = connection.total_changes
    original_query_only = connection.execute("PRAGMA query_only").fetchone()
    try:
        connection.execute("PRAGMA query_only = ON")
        if connection.execute("PRAGMA query_only").fetchone() != (1,):
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "C3 preflight is not query-only"
            )
        connection.execute("BEGIN")
        rows = connection.execute(
            """
            SELECT session_id, state, request_json, request_digest
            FROM sessions
            WHERE authority_epoch_id = ?
            ORDER BY created_at_utc, session_id
            """,
            (authority_epoch_id,),
        ).fetchall()
        result = _classify_durable_rows(connection, rows, nominated_session)
        if connection.total_changes != initial_changes:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "C3 preflight observed a database mutation"
            )
        connection.rollback()
        return result
    except PersonalDesktopUnattendedMarketDataCaptureError:
        if connection.in_transaction:
            connection.rollback()
        raise
    except BaseException as error:
        if connection.in_transaction:
            connection.rollback()
        raise PersonalDesktopUnattendedMarketDataCaptureError(
            "durable C2/C3 state is invalid"
        ) from error
    finally:
        if original_query_only == (0,):
            connection.execute("PRAGMA query_only = OFF")


def _classify_durable_rows(
    connection: sqlite3.Connection,
    rows: list[tuple[object, ...]],
    nominated_session: TradingSession,
) -> PersonalDesktopUnattendedC3PreflightReadResult:
    request = personal_desktop_unattended_capture_request(nominated_session)
    request_bytes = request.canonical_c2_request_json()
    exact: list[tuple[str, str]] = []
    selected_chain: list[TradingSession] = []
    selected_ids: dict[TradingSession, tuple[str, str]] = {}
    for raw_session_id, raw_state, raw_request, raw_digest in rows:
        session_id = _canonical_uuid_text(raw_session_id, "session ID")
        if type(raw_state) is not str:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "durable session state is invalid"
            )
        stored_request = bytes(raw_request)
        if (
            type(raw_digest) is not bytes
            or hashlib.sha256(stored_request).digest() != raw_digest
        ):
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "durable session request digest is invalid"
            )
        if stored_request == request_bytes:
            exact.append((session_id, raw_state))
        source_session = _source_owned_session(stored_request)
        if source_session is None or raw_state != "SUCCESS_SELECTED":
            continue
        selections = connection.execute(
            "SELECT selection_id FROM session_selections WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        if len(selections) != 1:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "selected unattended C3 lineage is not unique"
            )
        if not _selected_lineage_complete(_exact_session_facts(connection, session_id)):
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "selected unattended C3 lineage is incomplete"
            )
        selection_id = _canonical_uuid_text(selections[0][0], "selection ID")
        if source_session in selected_ids:
            raise PersonalDesktopUnattendedMarketDataCaptureError(
                "multiple selected unattended C3 lineages exist for one session"
            )
        selected_chain.append(source_session)
        selected_ids[source_session] = (session_id, selection_id)

    selected_chain.sort()
    for previous, current in zip(selected_chain, selected_chain[1:], strict=False):
        if next_xnys_execution_session(previous) != current:
            return PersonalDesktopUnattendedC3PreflightReadResult(
                PersonalDesktopUnattendedMarketDataCaptureClassification.SESSION_GAP
            )
    if len(exact) > 1:
        return PersonalDesktopUnattendedC3PreflightReadResult(
            PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED
        )
    if exact:
        session_id, state = exact[0]
        facts = _exact_session_facts(connection, session_id)
        attempts, claims, reservations, terminals, selections = facts
        if state == "SUCCESS_SELECTED" and _selected_lineage_complete(facts):
            ids = selected_ids.get(nominated_session)
            if ids is None or ids[0] != session_id:
                return PersonalDesktopUnattendedC3PreflightReadResult(
                    PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED
                )
            return PersonalDesktopUnattendedC3PreflightReadResult(
                PersonalDesktopUnattendedMarketDataCaptureClassification.NO_NEW_COMPLETED_SESSION,
                selected_session_id=session_id,
                selected_selection_id=ids[1],
            )
        if claims or reservations or terminals:
            return PersonalDesktopUnattendedC3PreflightReadResult(
                PersonalDesktopUnattendedMarketDataCaptureClassification.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
            )
        if attempts or selections or state != "OPEN":
            return PersonalDesktopUnattendedC3PreflightReadResult(
                PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED
            )
        return PersonalDesktopUnattendedC3PreflightReadResult(
            PersonalDesktopUnattendedMarketDataCaptureClassification.BLOCKED
        )

    if selected_chain:
        latest = selected_chain[-1]
        if latest >= nominated_session:
            return PersonalDesktopUnattendedC3PreflightReadResult(
                PersonalDesktopUnattendedMarketDataCaptureClassification.SESSION_GAP
            )
        if next_xnys_execution_session(latest) != nominated_session:
            return PersonalDesktopUnattendedC3PreflightReadResult(
                PersonalDesktopUnattendedMarketDataCaptureClassification.SESSION_GAP
            )
    return PersonalDesktopUnattendedC3PreflightReadResult(
        PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED
    )


def _exact_session_facts(
    connection: sqlite3.Connection,
    session_id: str,
) -> tuple[int, int, int, int, int]:
    row = connection.execute(
        """
        SELECT
          (SELECT count(*) FROM attempts a
           WHERE a.session_id = s.session_id),
          (SELECT count(*) FROM provider_call_claims c
           JOIN attempts a ON a.attempt_id = c.attempt_id
           WHERE a.session_id = s.session_id),
          (SELECT count(*) FROM launch_reservations r
           JOIN provider_call_claims c ON c.claim_id = r.claim_id
           JOIN attempts a ON a.attempt_id = c.attempt_id
           WHERE a.session_id = s.session_id),
          (SELECT count(*) FROM terminals t
           JOIN launch_reservations r
             ON r.launch_reservation_id = t.launch_reservation_id
           JOIN provider_call_claims c ON c.claim_id = r.claim_id
           JOIN attempts a ON a.attempt_id = c.attempt_id
           WHERE a.session_id = s.session_id),
          (SELECT count(*) FROM session_selections ss
           WHERE ss.session_id = s.session_id)
        FROM sessions s WHERE s.session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None or len(row) != 5 or any(type(value) is not int for value in row):
        raise PersonalDesktopUnattendedMarketDataCaptureError(
            "exact C3 session facts are invalid"
        )
    return row


def _selected_lineage_complete(facts: tuple[int, int, int, int, int]) -> bool:
    attempts, claims, reservations, terminals, selections = facts
    return (
        attempts >= 1
        and attempts == claims == reservations == terminals
        and selections == 1
    )


def _source_owned_session(request_bytes: bytes) -> TradingSession | None:
    try:
        payload = json.loads(request_bytes)
        start = date.fromisoformat(payload["request_window_start_date"])
        session = TradingSession(start)
        expected = personal_desktop_unattended_capture_request(session)
    except (KeyError, TypeError, ValueError):
        return None
    return session if request_bytes == expected.canonical_c2_request_json() else None


def _selected_evidence(
    selected: SessionIndexedSelectedC3SnapshotReadResult,
) -> PersonalDesktopUnattendedSelectedC3Evidence:
    if type(selected) is not SessionIndexedSelectedC3SnapshotReadResult:
        raise PersonalDesktopUnattendedMarketDataCaptureError(
            "selected C3 read result is invalid"
        )
    audit = selected.selected.audit
    return PersonalDesktopUnattendedSelectedC3Evidence(
        selection_id=audit.selection_id,
        session_id=audit.session_id,
        attempt_id=audit.attempt_id,
        terminal_id=audit.terminal_id,
        snapshot_id=audit.snapshot_id,
        artifact_sha256=audit.artifact_sha256,
        artifact_byte_length=audit.artifact_byte_length,
    )


def _effect_gate_state() -> str:
    security = import_module(
        "trading_bot.runtime.personal_desktop_paper_account_security"
    )
    receipt_recovery = import_module(
        "trading_bot.runtime.personal_desktop_paper_receipt_recovery_execution"
    )
    supervised_execution = import_module(
        "trading_bot.runtime.personal_desktop_supervised_paper_operation_execution"
    )
    decision_publication = import_module(
        "trading_bot.runtime.personal_desktop_unattended_paper_decision_publication"
    )
    unattended_execution = import_module(
        "trading_bot.runtime.personal_desktop_unattended_paper_operation_execution"
    )
    storage_provisioning = import_module(
        "trading_bot.runtime.personal_desktop_unattended_paper_storage_provisioning"
    )
    other_gates = (
        decision_publication.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        receipt_recovery.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        unattended_execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        storage_provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )
    if any(value is not False for value in other_gates):
        return "INVALID"
    if PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED is True:
        return "OPEN"
    if PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED is False:
        return "CLOSED"
    return "INVALID"


def _result(
    classification: PersonalDesktopUnattendedMarketDataCaptureClassification,
    session: TradingSession,
    request: ProductionCaptureRequest,
    digest: str,
    *,
    selected_c3: PersonalDesktopUnattendedSelectedC3Evidence | None = None,
    invocation: ProductionCaptureInvocationResult | None = None,
) -> PersonalDesktopUnattendedMarketDataCaptureResult:
    return PersonalDesktopUnattendedMarketDataCaptureResult(
        classification=classification,
        eligible_completed_session=session,
        capture_request=request,
        canonical_c2_request_sha256=digest,
        selected_c3=selected_c3,
        invocation=invocation,
    )


def _canonical_uuid_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise PersonalDesktopUnattendedMarketDataCaptureError(
            f"{field_name} must be canonical UUID text"
        )
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise PersonalDesktopUnattendedMarketDataCaptureError(
            f"{field_name} must be canonical UUID text"
        ) from None
    if str(parsed) != value:
        raise PersonalDesktopUnattendedMarketDataCaptureError(
            f"{field_name} must be canonical UUID text"
        )
    return value
