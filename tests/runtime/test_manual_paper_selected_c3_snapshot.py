from __future__ import annotations

import hashlib
import json
import pickle
import sqlite3
import uuid
from copy import copy, deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.runtime.manual_paper_selected_c3_snapshot as p2_module
import trading_bot.runtime.windows_authority_validation as validation_module
from trading_bot.domain import Symbol
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailyBarCandidate,
    DailyProviderResponse,
    DailySnapshotCaptureRequest,
    SourcePayloadEvidence,
    accept_daily_provider_response,
    build_daily_provider_request,
    serialize_daily_snapshot,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadError,
    WindowsSelectedC3SnapshotReadAuthority,
    open_disposable_selected_c3_snapshot_read_authority_for_test,
    require_disposable_selected_c3_snapshot_permit_for_test,
    require_selected_c3_snapshot_permit,
)
from trading_bot.runtime.windows_authority import (
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    ProductionAuthorityEvidence,
    execute_schema_artifact,
    validate_persisted_evidence_digests,
    validate_production_schema,
)
from trading_bot.runtime.windows_authority_sqlite import (
    open_disposable_read_only_sqlite_connection,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority_for_test,
)
from trading_bot.runtime.windows_effectful_capture_native import (
    NativeFileIdentity,
    NativeOpenedArtifact,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    C3ArtifactIdentityEvidence,
)

_NAMESPACE = UUID("7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012")
_EPOCH = "11111111-1111-4111-8111-111111111111"
_MACHINE = "22222222-2222-4222-8222-222222222222"
_PROVIDER = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
_OPERATION = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
_TIMESTAMP = "2026-08-29T00:00:00Z"


def _frame(value: str) -> str:
    return f"{len(value.encode('utf-8'))}:" + value


def _identity(label: str, *values: str) -> str:
    material = _frame(label) + "".join(_frame(value) for value in values)
    return str(uuid.uuid5(_NAMESPACE, material))


def _ordered_list(values: tuple[str, ...]) -> str:
    return _frame(str(len(values))) + "".join(_frame(value) for value in values)


def _json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _pair(value: object) -> tuple[bytes, bytes]:
    payload = _json(value)
    return payload, hashlib.sha256(payload).digest()


def _generic(label: str) -> tuple[bytes, bytes]:
    return _pair({"evidence": label, "schema": 1})


def _snapshot_bytes() -> bytes:
    requested_at = datetime(2026, 8, 29, 12, tzinfo=UTC)
    request = DailySnapshotCaptureRequest(
        request_id=UUID("33333333-3333-4333-8333-333333333333"),
        symbols=(Symbol("AAPL"),),
        requested_at=requested_at,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
    )
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    provider_request = build_daily_provider_request(
        request, ALPACA_DAILY_SNAPSHOT_DESCRIPTOR, calendar
    )
    session = provider_request.target_session
    source = b"offline selected C3 fixture"
    response = DailyProviderResponse(
        request=provider_request,
        candidates=(
            DailyBarCandidate(
                response_ordinal=0,
                symbol=Symbol("AAPL"),
                session=session,
                timestamp=datetime.combine(
                    session.session_date, datetime.min.time(), tzinfo=UTC
                )
                + timedelta(hours=20),
                open=Decimal("100"),
                high=Decimal("103"),
                low=Decimal("99"),
                close=Decimal("102"),
                volume=1000,
            ),
        ),
        captured_at=requested_at + timedelta(seconds=1),
        provider_as_of=requested_at,
        provider_request_id="offline-p2-fixture",
        source_payload=SourcePayloadEvidence(
            sha256=hashlib.sha256(source).hexdigest(),
            byte_length=len(source),
            media_type="application/json",
        ),
        pagination_complete=True,
    )
    accepted = accept_daily_provider_response(provider_request, response, calendar)
    assert accepted.snapshot is not None
    return serialize_daily_snapshot(accepted.snapshot)


class _ArtifactApi:
    def __init__(
        self, payload: bytes, identity: NativeFileIdentity, expected_path: str
    ) -> None:
        self.payload = payload
        self.identity = identity
        self.expected_path = expected_path
        self.open_error: BaseException | None = None
        self.close_error: BaseException | None = None
        self.paths: list[str] = []
        self.bounds: list[int] = []
        self.closed: list[int] = []

    def open_final_artifact(self, path: str) -> NativeOpenedArtifact:
        self.paths.append(path)
        if self.open_error is not None:
            raise self.open_error
        assert path == self.expected_path
        return NativeOpenedArtifact(101, self.identity)

    def read_artifact_file(self, handle: int, max_bytes: int) -> bytes:
        assert handle == 101
        self.bounds.append(max_bytes)
        return self.payload

    def close_handle(self, handle: int) -> None:
        self.closed.append(handle)
        if self.close_error is not None:
            raise self.close_error


def _disable_triggers(connection: sqlite3.Connection) -> None:
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, False)


def _enable_triggers(connection: sqlite3.Connection) -> None:
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, True)


def _build_database(
    database: Path, payload: bytes, identity: NativeFileIdentity
) -> dict[str, str]:
    connection = sqlite3.connect(database)
    execute_schema_artifact(connection)
    _disable_triggers(connection)
    try:
        metadata_json, metadata_digest = _pair({"schema": 1})
        connection.execute(
            """
            INSERT INTO authority_metadata (
                authority_epoch_id, machine_authority_id, bootstrap_schema,
                bootstrap_generation, signing_key_id, approved_account_sid,
                provider_id, permitted_provider_operation, authority_policy_version,
                claim_policy_version, created_at_utc, bootstrap_digest,
                database_identity_digest, metadata_json, metadata_digest,
                production_schema_id, production_schema_version,
                production_schema_digest, metadata_encoding_version,
                initialization_policy_version, singleton_key
            ) VALUES (?, ?, 1, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                _EPOCH,
                _MACHINE,
                "test-key/v1",
                "S-1-5-21-1-2-3-1009",
                _PROVIDER,
                _OPERATION,
                "authority-policy/v1",
                "claim-policy/v1",
                _TIMESTAMP,
                b"b" * 32,
                b"d" * 32,
                metadata_json,
                metadata_digest,
                PRODUCTION_SCHEMA_ID,
                PRODUCTION_SCHEMA_VERSION,
                bytes.fromhex(PRODUCTION_SCHEMA_ARTIFACT_SHA256),
                "authority-metadata/v1",
                "authority-initialization/v1",
            ),
        )
        request_material = {
            "bar_interval": "1d",
            "child_operation_version": "child/v1",
            "ordered_universe": ["AAPL"],
            "output_policy_version": "output/v1",
            "permitted_provider_operation": _OPERATION,
            "provider_id": _PROVIDER,
            "request_limit": 1,
            "request_window_end_date": "2026-08-27",
            "request_window_start_date": "2026-08-01",
            "target_session_date": "2026-08-28",
        }
        request_json, request_digest = _pair(request_material)
        session_id = _identity(
            "session_id/v2",
            _MACHINE,
            _EPOCH,
            "1",
            "authority-policy/v1",
            "claim-policy/v1",
            "capture_request/v2",
            request_material["target_session_date"],
            _PROVIDER,
            _OPERATION,
            _ordered_list(("AAPL",)),
            "1d",
            request_material["request_window_start_date"],
            request_material["request_window_end_date"],
            "1",
            "child/v1",
            "output/v1",
        )
        attempt_id = _identity(
            "attempt_id/v2",
            session_id,
            "0",
            _PROVIDER,
            _OPERATION,
            "1",
            "claim-policy/v1",
        )
        claim_id = _identity(
            "claim_id/v2",
            attempt_id,
            "1",
            "claim-policy/v1",
            _PROVIDER,
            _OPERATION,
            "1",
        )
        reservation_id = _identity(
            "launch_reservation_id/v2",
            claim_id,
            "1",
            "release/v1",
            "authority-policy/v1",
            "claim-policy/v1",
        )
        execution_id = _identity(
            "launch_execution_id/v2",
            reservation_id,
            "1",
            "release/v1",
            "authority-policy/v1",
        )
        terminal_id = _identity(
            "terminal_id/v2", reservation_id, "1", "terminal-policy/v1"
        )
        selection_id = _identity(
            "selection_id/v2", session_id, terminal_id, "1", "selection-policy/v1"
        )
        connection.execute(
            """
            INSERT INTO sessions VALUES (
                ?, ?, 1, ?, ?, '2026-08-28', 'SUCCESS_SELECTED', 1, 0,
                ?, ?, ?, NULL, NULL
            )
            """,
            (
                session_id,
                _EPOCH,
                "authority-policy/v1",
                "claim-policy/v1",
                request_json,
                request_digest,
                _TIMESTAMP,
            ),
        )
        allocation = _generic("allocation:0")
        attempt = _generic("attempt:0")
        connection.execute(
            """
            INSERT INTO attempts VALUES (
                ?, ?, 0, ?, ?, 1, ?, ?, 1, ?, ?, ?, ?, ?,
                'SUCCESS_SELECTED', ?
            )
            """,
            (
                attempt_id,
                session_id,
                _PROVIDER,
                _OPERATION,
                request_json,
                request_digest,
                "claim-policy/v1",
                *allocation,
                *attempt,
                _TIMESTAMP,
            ),
        )
        claim = _generic(f"claim:{attempt_id}")
        connection.execute(
            """
            INSERT INTO provider_call_claims VALUES (
                ?, ?, 1, ?, ?, ?, 1, ?, ?, ?, ?, 'COMMITTED', ?
            )
            """,
            (
                claim_id,
                attempt_id,
                "claim-policy/v1",
                _PROVIDER,
                _OPERATION,
                request_json,
                request_digest,
                *claim,
                _TIMESTAMP,
            ),
        )
        reservation = _generic(f"reservation:{claim_id}")
        process_intent = _pair(
            {
                "authority_policy_version": "authority-policy/v1",
                "claim_policy_version": "claim-policy/v1",
                "launch_reservation_id": reservation_id,
                "process_operation": "CreateProcessW",
                "request_digest": request_digest.hex(),
                "schema": 1,
            }
        )
        connection.execute(
            """
            INSERT INTO launch_reservations VALUES (
                ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                'TERMINAL_RECORDED', NULL, NULL, ?, ?
            )
            """,
            (
                reservation_id,
                claim_id,
                "release/v1",
                "authority-policy/v1",
                "claim-policy/v1",
                request_digest,
                *reservation,
                *process_intent,
                _TIMESTAMP,
                _TIMESTAMP,
                _TIMESTAMP,
            ),
        )
        process_common = {
            "process_intent_digest": process_intent[1].hex(),
            "reservation_id": reservation_id,
            "schema": 1,
        }
        process = _pair(
            {**process_common, "creation_result": "SUSPENDED_CHILD_CREATED"}
        )
        job = _pair({**process_common, "job_object_result": "ASSIGNED"})
        resume_authorization = _pair(
            {
                **process_common,
                "resume_authorization": "SUSPENDED_THREAD_OWNED",
            }
        )
        resume_intent = _pair(
            {
                "execution_id": execution_id,
                "resume_operation": "ResumeThread",
                "schema": 1,
            }
        )
        post_resume = _pair(
            {
                "execution_id": execution_id,
                "resume_intent_digest": resume_intent[1].hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        child_request_sha = "11" * 32
        child_result_sha = "22" * 32
        cleanup_material = {
            "child_fence_state": "ENTERED",
            "child_request_sha256": child_request_sha,
            "child_result_classification": "SUCCEEDED",
            "child_result_sha256": child_result_sha,
            "execution_id": execution_id,
            "http_status": None,
            "parent_cleanup": "COMPLETE",
            "process_outcome": "EXITED_ZERO",
            "provider_call_disposition": "CONFIRMED",
            "provider_request_id": None,
            "reservation_id": reservation_id,
            "result_transport": "COMPLETE",
            "schema": 2,
        }
        cleanup = _pair(cleanup_material)
        connection.execute(
            """
            INSERT INTO launch_executions VALUES (
                ?, ?, 1, ?, ?, 'TERMINAL_RECORDED', ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                execution_id,
                reservation_id,
                "release/v1",
                "authority-policy/v1",
                *process,
                *job,
                *resume_authorization,
                *resume_intent,
                _TIMESTAMP,
                *post_resume,
                *cleanup,
                _TIMESTAMP,
            ),
        )
        snapshot_id = UUID(json.loads(payload)["snapshot_id"])
        artifact_sha = hashlib.sha256(payload).hexdigest()
        identity_sha = C3ArtifactIdentityEvidence(
            snapshot_id=snapshot_id,
            final_canonical_filename=f"daily-market-data-snapshot-{snapshot_id}.json",
            artifact_sha256=artifact_sha,
            artifact_byte_length=len(payload),
            native_file_identity=identity,
        ).sha256
        terminal_material = {
            "artifact_identity_sha256": identity_sha,
            "artifact_sha256": artifact_sha,
            "artifact_verification": "VERIFIED",
            "attempt_id": attempt_id,
            "child_fence_state": "ENTERED",
            "child_request_sha256": child_request_sha,
            "child_result_classification": "SUCCEEDED",
            "child_result_sha256": child_result_sha,
            "claim_id": claim_id,
            "execution_id": execution_id,
            "http_status": None,
            "parent_cleanup": "COMPLETE",
            "process_outcome": "EXITED_ZERO",
            "provider_call_disposition": "CONFIRMED",
            "provider_request_id": None,
            "reservation_id": reservation_id,
            "result_transport": "COMPLETE",
            "schema": 2,
            "session_id": session_id,
            "snapshot_id": str(snapshot_id),
            "staging_cleanup": "COMPLETE",
            "terminal_state": "SUCCEEDED",
        }
        terminal = _pair(terminal_material)
        diagnostics = _pair(
            {
                "artifact_verification": "VERIFIED",
                "parent_cleanup": "COMPLETE",
                "reason": "VERIFIED_SNAPSHOT",
                "result_transport": "COMPLETE",
                "schema": 1,
                "staging_cleanup": "COMPLETE",
            }
        )
        connection.execute(
            """
            INSERT INTO terminals VALUES (
                ?, ?, 1, ?, 'SUCCEEDED', 'CONFIRMED', ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                terminal_id,
                reservation_id,
                "terminal-policy/v1",
                request_digest,
                *terminal,
                bytes.fromhex(artifact_sha),
                *diagnostics,
                _TIMESTAMP,
            ),
        )
        selection = _generic(f"selection:{terminal_id}")
        connection.execute(
            """
            INSERT INTO session_selections VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                selection_id,
                session_id,
                terminal_id,
                "selection-policy/v1",
                bytes.fromhex(artifact_sha),
                *selection,
                _TIMESTAMP,
            ),
        )
        connection.commit()
    finally:
        _enable_triggers(connection)
        connection.close()
    return {
        "selection_id": selection_id,
        "session_id": session_id,
        "attempt_id": attempt_id,
        "terminal_id": terminal_id,
        "snapshot_id": str(snapshot_id),
        "artifact_sha": artifact_sha,
        "identity_sha": identity_sha,
    }


@pytest.fixture
def selected_case(tmp_path: Path):
    payload = _snapshot_bytes()
    identity = NativeFileIdentity(7, b"i" * 16)
    database = tmp_path / "authority.sqlite3"
    output = tmp_path / "capture-output"
    output.mkdir()
    ids = _build_database(database, payload, identity)
    artifact = output / f"daily-market-data-snapshot-{ids['snapshot_id']}.json"
    artifact.write_bytes(payload)
    api = _ArtifactApi(payload, identity, str(artifact))
    authority = open_disposable_selected_c3_snapshot_read_authority_for_test(
        database_path=database,
        capture_output_root=output,
        artifact_api=api,
        authority_epoch_id=_EPOCH,
        provider_id=_PROVIDER,
        permitted_provider_operation=_OPERATION,
    )
    return SimpleNamespace(
        database=database,
        output=output,
        payload=payload,
        identity=identity,
        ids=ids,
        artifact=artifact,
        api=api,
        authority=authority,
    )


def _mutate(database: Path, sql: str, parameters: tuple[object, ...] = ()) -> None:
    connection = sqlite3.connect(database)
    _disable_triggers(connection)
    try:
        connection.execute(sql, parameters)
        connection.commit()
    finally:
        _enable_triggers(connection)
        connection.close()


def _mutate_terminal_material(database: Path, **changes: object) -> None:
    connection = sqlite3.connect(database)
    material = json.loads(
        connection.execute("SELECT evidence_json FROM terminals").fetchone()[0]
    )
    connection.close()
    material.update(changes)
    payload, digest = _pair(material)
    _mutate(
        database,
        "UPDATE terminals SET evidence_json = ?, evidence_digest = ?",
        (payload, digest),
    )


def _replace_request_lineage(database: Path, material: object) -> None:
    request_json, request_digest = _pair(material)
    connection = sqlite3.connect(database)
    _disable_triggers(connection)
    try:
        reservation_id = connection.execute(
            "SELECT launch_reservation_id FROM launch_reservations"
        ).fetchone()[0]
        process_intent = _pair(
            {
                "authority_policy_version": "authority-policy/v1",
                "claim_policy_version": "claim-policy/v1",
                "launch_reservation_id": reservation_id,
                "process_operation": "CreateProcessW",
                "request_digest": request_digest.hex(),
                "schema": 1,
            }
        )
        process_common = {
            "process_intent_digest": process_intent[1].hex(),
            "reservation_id": reservation_id,
            "schema": 1,
        }
        process = _pair(
            {**process_common, "creation_result": "SUSPENDED_CHILD_CREATED"}
        )
        job = _pair({**process_common, "job_object_result": "ASSIGNED"})
        resume_authorization = _pair(
            {
                **process_common,
                "resume_authorization": "SUSPENDED_THREAD_OWNED",
            }
        )
        connection.execute(
            "UPDATE sessions SET request_json = ?, request_digest = ?",
            (request_json, request_digest),
        )
        connection.execute(
            "UPDATE attempts SET request_json = ?, request_digest = ?",
            (request_json, request_digest),
        )
        connection.execute(
            "UPDATE provider_call_claims SET request_json = ?, request_digest = ?",
            (request_json, request_digest),
        )
        connection.execute(
            "UPDATE launch_reservations SET request_digest = ?, "
            "process_intent_json = ?, process_intent_digest = ?",
            (request_digest, *process_intent),
        )
        connection.execute(
            "UPDATE launch_executions SET process_creation_json = ?, "
            "process_creation_digest = ?, job_object_json = ?, "
            "job_object_digest = ?, resume_authorization_json = ?, "
            "resume_authorization_digest = ?",
            (*process, *job, *resume_authorization),
        )
        connection.execute("UPDATE terminals SET request_digest = ?", (request_digest,))
        connection.commit()
    finally:
        _enable_triggers(connection)
        connection.close()


def test_success_returns_exact_audit_and_deterministic_read_only_evidence(
    selected_case,
) -> None:
    before = selected_case.database.read_bytes()
    first = selected_case.authority.read_selected_snapshot(
        selected_case.ids["selection_id"], artifact_path=selected_case.artifact
    )
    second = selected_case.authority.read_selected_snapshot(
        selected_case.ids["selection_id"]
    )

    assert first.audit == second.audit
    assert first.permit is not second.permit
    assert first.snapshot_bytes == selected_case.payload
    assert first.verification.passed and first.verification.diagnostics == ()
    assert str(first.audit.selection_id) == selected_case.ids["selection_id"]
    assert str(first.audit.snapshot_id) == selected_case.ids["snapshot_id"]
    assert first.audit.artifact_sha256 == selected_case.ids["artifact_sha"]
    assert first.audit.artifact_byte_length == len(selected_case.payload)
    assert first.audit.artifact_identity_sha256 == selected_case.ids["identity_sha"]
    assert first.audit.terminal_state == "SUCCEEDED"
    assert first.audit.provider_call_disposition == "CONFIRMED"
    assert first.provider_call_performed is False
    assert first.database_mutation_performed is False
    assert selected_case.api.bounds == [4 * 1024 * 1024, 4 * 1024 * 1024]
    assert selected_case.api.closed == [101, 101]
    assert selected_case.database.read_bytes() == before
    require_disposable_selected_c3_snapshot_permit_for_test(first.permit, first.audit)
    with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
        require_selected_c3_snapshot_permit(first.permit, first.audit)


@pytest.mark.parametrize(
    "substituted",
    [
        lambda payload: payload[:-1] + bytes([payload[-1] ^ 1]),
        lambda payload: payload + b" ",
    ],
    ids=("same-length-substitution", "wrong-length"),
)
def test_result_rejects_substituted_snapshot_bytes(selected_case, substituted) -> None:
    result = selected_case.authority.read_selected_snapshot(
        selected_case.ids["selection_id"]
    )
    with pytest.raises(SelectedC3SnapshotReadError, match="inconsistent"):
        replace(result, snapshot_bytes=substituted(result.snapshot_bytes))


def test_result_rejects_mismatched_verified_snapshot_id(selected_case) -> None:
    result = selected_case.authority.read_selected_snapshot(
        selected_case.ids["selection_id"]
    )
    with pytest.raises(SelectedC3SnapshotReadError, match="inconsistent"):
        replace(
            result,
            audit=replace(
                result.audit,
                snapshot_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            ),
        )


def test_result_rejects_verification_snapshot_byte_disagreement(selected_case) -> None:
    result = selected_case.authority.read_selected_snapshot(
        selected_case.ids["selection_id"]
    )
    substituted_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    assert result.verification.snapshot is not None
    altered_snapshot = replace(result.verification.snapshot, snapshot_id=substituted_id)
    altered_verification = replace(result.verification, snapshot=altered_snapshot)
    altered_audit = replace(result.audit, snapshot_id=substituted_id)
    with pytest.raises(SelectedC3SnapshotReadError, match="snapshot bytes"):
        replace(
            result,
            audit=altered_audit,
            verification=altered_verification,
        )


def test_exact_selection_lookup_has_no_fallback(selected_case) -> None:
    with pytest.raises(SelectedC3SnapshotReadError, match="exactly one"):
        selected_case.authority.read_selected_snapshot(
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        )
    with pytest.raises(SelectedC3SnapshotReadError, match="canonical UUID"):
        selected_case.authority.read_selected_snapshot("latest")
    assert selected_case.api.paths == []


@pytest.mark.parametrize(
    ("sql", "parameters"),
    [
        (
            "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, "
            "close_reason = 'x'",
            (_TIMESTAMP,),
        ),
        ("UPDATE attempts SET state = 'TERMINAL_RECORDED'", ()),
        ("UPDATE attempts SET request_json = ?", (b"{}",)),
        ("UPDATE provider_call_claims SET claim_policy_version = 'wrong'", ()),
        ("UPDATE terminals SET terminal_state = 'FAILED'", ()),
        ("UPDATE terminals SET provider_call_disposition = 'MAY_HAVE_OCCURRED'", ()),
        ("UPDATE session_selections SET snapshot_digest = ?", (b"x" * 32,)),
        ("UPDATE session_selections SET selection_evidence_json = ?", (b"{}",)),
        ("UPDATE terminals SET evidence_digest = ?", (b"x" * 32,)),
        ("UPDATE launch_executions SET cleanup_digest = ?", (b"x" * 32,)),
        ("UPDATE launch_executions SET post_resume_json = ?", (b"{}",)),
        ("UPDATE authority_metadata SET authority_epoch_id = ?", ("wrong-epoch",)),
    ],
)
def test_conflicting_durable_state_and_evidence_fail_closed(
    selected_case, sql: str, parameters: tuple[object, ...]
) -> None:
    _mutate(selected_case.database, sql, parameters)
    with pytest.raises(SelectedC3SnapshotReadError):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )
    assert selected_case.api.paths == []


def test_terminal_semantics_and_lineage_mismatch_fail_closed(selected_case) -> None:
    _mutate_terminal_material(
        selected_case.database,
        attempt_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    with pytest.raises(SelectedC3SnapshotReadError):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )


def test_rehashed_noncanonical_capture_request_fails_before_artifact_authority(
    selected_case,
) -> None:
    _replace_request_lineage(
        selected_case.database,
        {"request": "internally-rehashed-but-invalid", "schema": 2},
    )
    with pytest.raises(SelectedC3SnapshotReadError, match="durable evidence"):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )
    assert selected_case.api.paths == []


def test_valid_request_inconsistent_with_deterministic_session_id_fails_closed(
    selected_case,
) -> None:
    _replace_request_lineage(
        selected_case.database,
        {
            "bar_interval": "1d",
            "child_operation_version": "child/v1",
            "ordered_universe": ["AAPL"],
            "output_policy_version": "output/v1",
            "permitted_provider_operation": _OPERATION,
            "provider_id": _PROVIDER,
            "request_limit": 1,
            "request_window_end_date": "2026-08-26",
            "request_window_start_date": "2026-08-01",
            "target_session_date": "2026-08-27",
        },
    )
    with pytest.raises(SelectedC3SnapshotReadError, match="durable evidence"):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )
    assert selected_case.api.paths == []


@pytest.mark.parametrize(
    ("json_column", "digest_column"),
    [
        ("process_creation_json", "process_creation_digest"),
        ("job_object_json", "job_object_digest"),
        ("resume_authorization_json", "resume_authorization_digest"),
    ],
)
def test_rehashed_semantically_wrong_process_evidence_fails_closed(
    selected_case, json_column: str, digest_column: str
) -> None:
    evidence_json, evidence_digest = _pair(
        {"evidence": f"wrong:{json_column}", "schema": 1}
    )
    _mutate(
        selected_case.database,
        f"UPDATE launch_executions SET {json_column} = ?, {digest_column} = ?",
        (evidence_json, evidence_digest),
    )
    with pytest.raises(SelectedC3SnapshotReadError, match="durable evidence"):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )
    assert selected_case.api.paths == []


def test_canonical_production_process_evidence_is_accepted(selected_case) -> None:
    connection = sqlite3.connect(selected_case.database)
    reservation_id, process_intent_digest = connection.execute(
        "SELECT launch_reservation_id, process_intent_digest FROM launch_reservations"
    ).fetchone()
    connection.close()
    process_common = {
        "process_intent_digest": process_intent_digest.hex(),
        "reservation_id": reservation_id,
        "schema": 1,
    }
    process = _pair(
        {
            **process_common,
            "application_name": r"C:\Python312\python.exe",
            "child_base_arguments": ["-m", "trading_bot.runtime.child"],
            "creation_flags_policy": "C3_EXACT_SUSPENDED_NO_WINDOW_V1",
            "creation_result": "SUSPENDED_CHILD_CREATED",
            "environment_policy": "C3_EXACT_FIVE_ENTRY_V1",
            "handle_list_count": 3,
            "handle_list_policy": "C3_EXACT_REQUEST_RESULT_STAGING_V1",
            "shell_or_path_resolution": False,
        }
    )
    job = _pair(
        {
            **process_common,
            "active_process_limit": 1,
            "breakaway_allowed": False,
            "job_assignment": "AT_PROCESS_CREATION",
            "job_object_result": "ASSIGNED",
            "kill_on_job_close": True,
        }
    )
    resume_authorization = _pair(
        {
            **process_common,
            "previous_suspend_count_required": 1,
            "resume_authorization": "EXACT_PRIMARY_THREAD_RETAINED",
        }
    )
    _mutate(
        selected_case.database,
        "UPDATE launch_executions SET process_creation_json = ?, "
        "process_creation_digest = ?, job_object_json = ?, "
        "job_object_digest = ?, resume_authorization_json = ?, "
        "resume_authorization_digest = ?",
        (*process, *job, *resume_authorization),
    )

    result = selected_case.authority.read_selected_snapshot(
        selected_case.ids["selection_id"]
    )

    assert result.snapshot_bytes == selected_case.payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_sha256", "bad"),
        ("artifact_sha256", "00" * 32),
        ("artifact_identity_sha256", "bad"),
        ("artifact_identity_sha256", "00" * 32),
    ],
)
def test_malformed_or_mismatched_terminal_artifact_evidence_fails_closed(
    selected_case, field: str, value: str
) -> None:
    _mutate_terminal_material(selected_case.database, **{field: value})
    with pytest.raises(SelectedC3SnapshotReadError):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )


def test_transport_path_cannot_nominate_another_file(selected_case) -> None:
    with pytest.raises(SelectedC3SnapshotReadError, match="transport hint"):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"],
            artifact_path=selected_case.output / "other.json",
        )
    assert selected_case.api.paths == []


@pytest.mark.parametrize("unsafe", ["reparse", "directory", "device", "outside"])
def test_unsafe_or_nonregular_artifact_open_fails_through_reviewed_seam(
    selected_case, unsafe: str
) -> None:
    selected_case.api.open_error = RuntimeError(unsafe)
    with pytest.raises(SelectedC3SnapshotReadError, match="safely reopened"):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )
    assert selected_case.api.bounds == []


def test_bounded_read_rejects_oversized_result(selected_case) -> None:
    selected_case.api.payload = b"x" * (4 * 1024 * 1024 + 1)
    with pytest.raises(SelectedC3SnapshotReadError, match="oversized"):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )
    assert selected_case.api.bounds == [4 * 1024 * 1024]


@pytest.mark.parametrize("change", ["sha", "length", "identity", "snapshot"])
def test_reread_and_artifact_identity_substitution_fail_closed(
    selected_case, change: str
) -> None:
    if change == "sha":
        selected_case.api.payload = selected_case.payload[:-1] + b"x"
    elif change == "length":
        selected_case.api.payload = selected_case.payload + b" "
    elif change == "identity":
        selected_case.api.identity = NativeFileIdentity(8, b"j" * 16)
    else:
        tree = json.loads(selected_case.payload)
        tree["snapshot_id"] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        changed = _json(tree)
        selected_case.api.payload = changed
        changed_sha = hashlib.sha256(changed).digest()
        _mutate(
            selected_case.database,
            "UPDATE terminals SET snapshot_digest = ?",
            (changed_sha,),
        )
        _mutate(
            selected_case.database,
            "UPDATE session_selections SET snapshot_digest = ?",
            (changed_sha,),
        )
    with pytest.raises(SelectedC3SnapshotReadError):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )


def test_strict_snapshot_verification_failure_blocks_permit(
    monkeypatch: pytest.MonkeyPatch, selected_case
) -> None:
    monkeypatch.setattr(
        p2_module,
        "verify_daily_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            passed=False,
            diagnostics=("failure",),
            snapshot=None,
        ),
    )
    with pytest.raises(SelectedC3SnapshotReadError, match="strict"):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )


def test_verified_snapshot_id_must_match_durable_terminal(selected_case) -> None:
    substituted = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    identity_sha = C3ArtifactIdentityEvidence(
        snapshot_id=substituted,
        final_canonical_filename=f"daily-market-data-snapshot-{substituted}.json",
        artifact_sha256=selected_case.ids["artifact_sha"],
        artifact_byte_length=len(selected_case.payload),
        native_file_identity=selected_case.identity,
    ).sha256
    _mutate_terminal_material(
        selected_case.database,
        snapshot_id=str(substituted),
        artifact_identity_sha256=identity_sha,
    )
    selected_case.api.expected_path = str(
        selected_case.output / f"daily-market-data-snapshot-{substituted}.json"
    )
    with pytest.raises(SelectedC3SnapshotReadError, match="strict"):
        selected_case.authority.read_selected_snapshot(
            selected_case.ids["selection_id"]
        )


def test_permit_is_sealed_noncopyable_and_bound_to_exact_audit(selected_case) -> None:
    result = selected_case.authority.read_selected_snapshot(
        selected_case.ids["selection_id"]
    )
    with pytest.raises(TypeError, match="issued by P2"):
        SelectedC3SnapshotPermit()
    with pytest.raises(TypeError, match="subclassed"):
        type("LookalikePermit", (SelectedC3SnapshotPermit,), {})
    for operation in (copy, deepcopy, pickle.dumps, json.dumps):
        with pytest.raises(TypeError):
            operation(result.permit)
    lookalike_audit = replace(result.audit)
    assert lookalike_audit == result.audit and lookalike_audit is not result.audit
    with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
        require_disposable_selected_c3_snapshot_permit_for_test(
            result.permit, lookalike_audit
        )
    forged = object.__new__(SelectedC3SnapshotPermit)
    with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
        require_disposable_selected_c3_snapshot_permit_for_test(forged, result.audit)


def test_unregistered_core_cannot_issue_production_permit_provenance(
    selected_case,
) -> None:
    result = selected_case.authority.read_selected_snapshot(
        selected_case.ids["selection_id"]
    )
    fake_core = object.__new__(p2_module._SelectedC3SnapshotReadCore)
    with pytest.raises(SelectedC3SnapshotReadError, match="core provenance"):
        p2_module._issue_permit(result.audit, core=fake_core)


def test_successful_read_issuance_cannot_be_forged_from_registered_core(
    monkeypatch: pytest.MonkeyPatch, selected_case
) -> None:
    genuine = SimpleNamespace(
        sqlite_build_manifest_digest="55" * 32,
        authority_epoch_id=_EPOCH,
        provider_id=_PROVIDER,
        permitted_provider_operation=_OPERATION,
    )

    def require_genuine(value: object) -> object:
        if value is not genuine:
            raise WindowsAuthorityError("not genuine")
        return value

    monkeypatch.setattr(
        p2_module, "require_validated_production_authority", require_genuine
    )
    monkeypatch.setattr(
        p2_module,
        "load_approved_sqlite_authority_build",
        lambda: SimpleNamespace(digest=b"U" * 32, vfs="approved-test-vfs"),
    )
    monkeypatch.setattr(
        p2_module,
        "PRODUCTION_AUTHORITY_PATHS",
        SimpleNamespace(
            database=selected_case.database,
            capture_output=selected_case.output,
        ),
    )
    monkeypatch.setattr(
        p2_module, "CtypesWindowsEffectfulCaptureNativeApi", lambda: selected_case.api
    )
    monkeypatch.setattr(
        p2_module,
        "open_read_only_sqlite_connection",
        lambda database_path, *, vfs: open_disposable_read_only_sqlite_connection(
            database_path
        ),
    )

    def validate_connection(
        authority: object,
        connection: sqlite3.Connection,
        *,
        allow_active_transaction: bool = False,
    ) -> object:
        assert authority is genuine
        assert connection.in_transaction
        assert allow_active_transaction is True
        validate_production_schema(connection)
        validate_persisted_evidence_digests(connection)
        return object()

    monkeypatch.setattr(
        p2_module,
        "require_open_connection_matches_validated_authority",
        validate_connection,
    )
    reader = WindowsSelectedC3SnapshotReadAuthority(genuine)  # type: ignore[arg-type]
    result = reader.read_selected_snapshot(selected_case.ids["selection_id"])
    lookalike_audit = replace(result.audit)
    fabricated_audit = replace(
        result.audit,
        selection_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    )

    for audit in (lookalike_audit, fabricated_audit):
        with pytest.raises(SelectedC3SnapshotReadError, match="successful-read"):
            p2_module._issue_permit(audit, core=reader._core)
    assert require_selected_c3_snapshot_permit(result.permit, result.audit) is (
        result.permit
    )


def test_production_constructor_rejects_test_and_lookalike_authority() -> None:
    with pytest.raises(WindowsAuthorityError):
        WindowsSelectedC3SnapshotReadAuthority(object())  # type: ignore[arg-type]
    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id=_MACHINE,
        authority_epoch_id=_EPOCH,
        signing_key_id="test-key/v1",
        approved_account_sid="S-1-5-21-1-2-3-1009",
        database_path=r"F:\AITradingBot\Authority\authority.sqlite3",
        provider_id=_PROVIDER,
        permitted_provider_operation=_OPERATION,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="11" * 32,
        output_root=r"F:\AITradingBot\Authority\capture-output",
    )
    evidence = ProductionAuthorityEvidence(
        database_path=bootstrap.database_path,
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="33" * 32,
        migration_id="migration/v1",
        release_manifest_digest="44" * 32,
        sqlite_build_manifest_digest="55" * 32,
    )
    test_authority = acquire_validated_production_authority_for_test(
        bootstrap=bootstrap,  # type: ignore[arg-type]
        bootstrap_digest=bootstrap.digest,
        production_evidence=evidence,
        trading_sid=bootstrap.approved_account_sid,
    )
    with pytest.raises(WindowsAuthorityError, match="non-production provenance"):
        WindowsSelectedC3SnapshotReadAuthority(test_authority)


def test_production_p2_uses_fixed_read_only_vfs_and_one_read_transaction(
    monkeypatch: pytest.MonkeyPatch, selected_case
) -> None:
    genuine = SimpleNamespace(
        sqlite_build_manifest_digest="55" * 32,
        authority_epoch_id=_EPOCH,
        machine_authority_id=_MACHINE,
        approved_account_sid="S-1-5-21-1-2-3-1009",
        provider_id=_PROVIDER,
        permitted_provider_operation=_OPERATION,
    )

    def require_genuine(value: object) -> object:
        if value is not genuine:
            raise WindowsAuthorityError("not genuine")
        return value

    opens: list[tuple[str, str]] = []

    def open_read_only(database_path: str, *, vfs: str) -> sqlite3.Connection:
        opens.append((str(database_path), vfs))
        return open_disposable_read_only_sqlite_connection(database_path)

    validations: list[tuple[bool, bool]] = []

    def validate_connection(
        authority: object,
        connection: sqlite3.Connection,
        *,
        allow_active_transaction: bool = False,
    ) -> object:
        assert authority is genuine
        validations.append((connection.in_transaction, allow_active_transaction))
        validate_production_schema(connection)
        validate_persisted_evidence_digests(connection)
        return object()

    monkeypatch.setattr(
        p2_module, "require_validated_production_authority", require_genuine
    )
    monkeypatch.setattr(
        p2_module,
        "load_approved_sqlite_authority_build",
        lambda: SimpleNamespace(digest=b"U" * 32, vfs="approved-test-vfs"),
    )
    monkeypatch.setattr(
        p2_module,
        "PRODUCTION_AUTHORITY_PATHS",
        SimpleNamespace(
            database=selected_case.database,
            capture_output=selected_case.output,
        ),
    )
    monkeypatch.setattr(
        p2_module, "CtypesWindowsEffectfulCaptureNativeApi", lambda: selected_case.api
    )
    monkeypatch.setattr(p2_module, "open_read_only_sqlite_connection", open_read_only)
    monkeypatch.setattr(
        p2_module,
        "require_open_connection_matches_validated_authority",
        validate_connection,
    )
    before = selected_case.database.read_bytes()

    authority = WindowsSelectedC3SnapshotReadAuthority(genuine)  # type: ignore[arg-type]
    result = authority.read_selected_snapshot(selected_case.ids["selection_id"])

    assert "authority" not in dir(authority)
    assert not hasattr(authority, "authority")
    assert opens == [(str(selected_case.database), "approved-test-vfs")]
    assert validations == [(True, True)]
    assert selected_case.database.read_bytes() == before
    assert require_selected_c3_snapshot_permit(result.permit, result.audit) is (
        result.permit
    )
    p2_module.require_selected_c3_snapshot_matches_authority(
        result.permit, result.audit, genuine
    )
    for field, changed in (
        ("machine_authority_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("approved_account_sid", "S-1-5-21-1-2-3-1010"),
        ("authority_epoch_id", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
    ):
        original = getattr(genuine, field)
        setattr(genuine, field, changed)
        with pytest.raises(SelectedC3SnapshotReadError, match="match C1"):
            p2_module.require_selected_c3_snapshot_matches_authority(
                result.permit, result.audit, genuine
            )
        setattr(genuine, field, original)
    with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
        require_selected_c3_snapshot_permit(result.permit, replace(result.audit))


def test_c1_connection_revalidation_explicitly_supports_one_read_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id=_MACHINE,
        authority_epoch_id=_EPOCH,
        signing_key_id="test-key/v1",
        approved_account_sid="S-1-5-21-1-2-3-1009",
        database_path=r"F:\AITradingBot\Authority\authority.sqlite3",
        output_root=r"F:\AITradingBot\Authority\capture-output",
        provider_id=_PROVIDER,
        permitted_provider_operation=_OPERATION,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="11" * 32,
    )
    expected = ProductionAuthorityEvidence(
        database_path=bootstrap.database_path,
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="33" * 32,
        migration_id="migration/v1",
        release_manifest_digest="44" * 32,
        sqlite_build_manifest_digest="55" * 32,
    )
    authority = SimpleNamespace(
        **{
            field: getattr(bootstrap, field)
            for field in (
                "authority_epoch_id",
                "machine_authority_id",
                "bootstrap_schema",
                "bootstrap_generation",
                "signing_key_id",
                "approved_account_sid",
                "provider_id",
                "permitted_provider_operation",
                "authority_policy_version",
                "claim_policy_version",
                "database_identity_digest",
                "database_path",
            )
        },
        bootstrap_digest=bootstrap.digest,
        schema_id=expected.schema_id,
        schema_version=expected.schema_version,
        schema_digest=expected.schema_digest,
        metadata_digest=expected.metadata_digest,
        migration_id=expected.migration_id,
        release_manifest_digest=expected.release_manifest_digest,
        sqlite_build_manifest_digest=expected.sqlite_build_manifest_digest,
    )
    monkeypatch.setattr(
        validation_module,
        "require_validated_production_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        validation_module,
        "load_approved_release_manifest",
        lambda: SimpleNamespace(digest=bytes.fromhex(expected.release_manifest_digest)),
    )
    monkeypatch.setattr(
        validation_module,
        "load_approved_sqlite_authority_build",
        lambda: SimpleNamespace(
            digest=bytes.fromhex(expected.sqlite_build_manifest_digest)
        ),
    )
    calls: list[bool] = []

    def validate(connection: sqlite3.Connection, **kwargs: object) -> object:
        assert connection.in_transaction
        calls.append(kwargs["allow_active_transaction"] is True)
        return expected

    monkeypatch.setattr(
        validation_module,
        "validate_production_authority_database_connection",
        validate,
    )
    connection = sqlite3.connect(":memory:")
    connection.execute("BEGIN")
    try:
        observed = (
            validation_module.require_open_connection_matches_validated_authority(
                authority,  # type: ignore[arg-type]
                connection,
                allow_active_transaction=True,
            )
        )
    finally:
        connection.rollback()
        connection.close()
    assert observed == expected
    assert calls == [True]


def test_p2_surface_exposes_no_c2_c3_or_external_effect_mutations(
    selected_case,
) -> None:
    forbidden = {
        "create_session",
        "allocate_attempt",
        "claim_provider_call",
        "reserve_launch",
        "create_process",
        "resume_thread",
        "record_terminal",
        "select_terminal",
        "recover",
        "construct_provider",
        "read_credentials",
    }
    assert forbidden.isdisjoint(dir(selected_case.authority))
    source = Path(p2_module.__file__).read_text(encoding="utf-8")
    assert "WindowsEffectfulDailySnapshotCapture" not in source
    assert "WindowsTransactionalAuthority" not in source
    assert "Credential" not in source
    assert "AlpacaDailySnapshotProvider" not in source
