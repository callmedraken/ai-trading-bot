from __future__ import annotations

import hashlib
import json
import pickle
import sqlite3
from collections import deque
from contextlib import nullcontext
from copy import copy, deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from inspect import signature
from uuid import UUID

import pytest

import trading_bot.runtime.windows_effectful_capture_service as service_module
from trading_bot.domain import Symbol
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailyBarCandidate,
    DailyProviderResponse,
    DailySnapshotCaptureRequest,
    ProviderDescriptor,
    SourcePayloadEvidence,
    accept_daily_provider_response,
    build_daily_provider_request,
    serialize_daily_snapshot,
)
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityBootstrap,
)
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    ProductionAuthorityEvidence,
    execute_schema_artifact,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority_for_test,
)
from trading_bot.runtime.windows_effectful_capture import ProductionCaptureRequest
from trading_bot.runtime.windows_effectful_capture_native import (
    C3NativeWaitStatus,
    C3ParentCleanupStatus,
    C3ProcessOutcomeStatus,
    C3ResultTransportStatus,
    NativeCreatedProcess,
    NativeFileIdentity,
    NativeOpenedArtifact,
    NativeOverlappedCompletion,
    NativePipePair,
    NativeStagingObject,
    WindowsEffectfulCaptureNativeError,
    WindowsEffectfulCaptureProcessNotCreatedError,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    MAX_C3_CHILD_REQUEST_BYTES,
    MAX_C3_CHILD_RESULT_BYTES,
    ChildCleanupStatus,
    ChildResultClassification,
    IsolatedCaptureChildResult,
    ProviderAttemptFenceState,
    VerifiedCapturedSnapshot,
    WindowsEffectfulCaptureProtocolError,
    parse_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    C3C2NativeLaunchConfigurationForTest,
    WindowsEffectfulCaptureCompositionError,
    WindowsEffectfulDailySnapshotCapture,
    c3_c2_registry_snapshot_for_test,
    create_c3_c2_transactional_adapter_for_test,
    execute_c3_c2_resume_for_test,
    issue_c3_post_resume_evidence_for_test,
    observe_c3_c3b_for_test,
)
from trading_bot.runtime.windows_transactional_authority import (
    ExternalAuthorityBoundaryUnavailable,
    ProcessIntent,
    WindowsTransactionalAuthority,
    open_disposable_authority_database_for_test,
)

_APPLICATION = r"F:\AITradingBot\runtime\python.exe"
_CURRENT = r"F:\AITradingBot\runtime"
_TEMP = r"F:\AITradingBot\temp"
_STORAGE_ROOT = r"F:\AITradingBot\Authority\capture-output"
_PARENT_ENV = {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"}


class _FakeNativeApi:
    def __init__(
        self,
        *,
        resume_result: int | BaseException = 1,
        fail_write: bool = False,
        fail_close: int | None = None,
        fail_terminate: bool = False,
        request_wait_status: C3NativeWaitStatus = C3NativeWaitStatus.IO_COMPLETED,
        fail_create: bool = False,
    ) -> None:
        self.resume_result = resume_result
        self.fail_write = fail_write
        self.fail_close = fail_close
        self.fail_terminate = fail_terminate
        self.request_wait_status = request_wait_status
        self.fail_create = fail_create
        self.events: list[str] = []
        self.written = bytearray()
        self.connection = None
        self._pipe_count = 0
        self.result_chunks: deque[bytes | None] = deque()
        self.wait_events: deque[C3NativeWaitStatus] = deque()
        self.process_wait_events: deque[C3NativeWaitStatus] = deque()
        self.exit_code = 0
        self.cancel_settles = True
        self.file_identity = NativeFileIdentity(7, b"i" * 16)
        self.staging_bytes = b""
        self.final_bytes: bytes | None = None
        self.final_identity: NativeFileIdentity | None = None
        self.casefold_collision = False
        self.identity_results: deque[NativeFileIdentity] = deque()
        self.fail_publish = False
        self.fail_cleanup = False
        self.result_factory = None

    def create_job_object(self) -> int:
        self.events.append("create_job")
        return 100

    def set_job_limits(self, job_handle: int) -> None:
        assert job_handle == 100
        self.events.append("set_job_limits")

    def create_request_pipe(self, buffer_size: int) -> NativePipePair:
        self._pipe_count += 1
        self.events.append(f"create_request_pipe:{buffer_size}")
        return NativePipePair(101, 102)

    def create_result_pipe(self, buffer_size: int) -> NativePipePair:
        self._pipe_count += 1
        self.events.append(f"create_result_pipe:{buffer_size}")
        return NativePipePair(103, 104)

    def set_handle_inheritable(self, handle: int, inheritable: bool) -> None:
        self.events.append(f"inherit:{handle}:{inheritable}")

    def create_staging_file(self, path: str) -> NativeStagingObject:
        assert path.startswith(_STORAGE_ROOT + "\\.c3-capture-")
        assert path.endswith(".staging")
        self.events.append("create_staging")
        return NativeStagingObject(105, 108, self.file_identity, path)

    def get_file_identity(self, handle: int) -> NativeFileIdentity:
        self.events.append(f"identity:{handle}")
        return (
            self.identity_results.popleft()
            if self.identity_results
            else self.file_identity
        )

    def read_artifact_file(self, handle: int, max_bytes: int) -> bytes:
        self.events.append(f"read_artifact:{handle}")
        assert self.connection.execute(
            "SELECT phase FROM launch_executions"
        ).fetchone() == ("RESUME_RECORDED",)
        payload = self.staging_bytes if handle == 105 else self.final_bytes
        return b"" if payload is None else payload

    def reject_casefold_collisions(
        self, directory: str, names: tuple[str, ...]
    ) -> None:
        self.events.append("casefold_check")
        if self.casefold_collision:
            raise RuntimeError("collision")

    def publish_staging_link(self, staging_handle: int, final_path: str) -> None:
        assert staging_handle == 105
        self.events.append("publish")
        if self.fail_publish:
            raise RuntimeError("publication failure")
        if self.final_bytes is None:
            self.final_bytes = self.staging_bytes

    def open_final_artifact(self, path: str) -> NativeOpenedArtifact:
        self.events.append("open_final")
        return NativeOpenedArtifact(109, self.final_identity or self.file_identity)

    def delete_staging_link(self, staging_handle: int) -> None:
        assert staging_handle == 105
        assert self.connection is not None
        assert not self.connection.in_transaction
        self.events.append("delete_staging")
        if self.fail_cleanup:
            raise RuntimeError("cleanup failure")

    def create_suspended_process(self, **kwargs: object) -> NativeCreatedProcess:
        assert kwargs["application_name"] == _APPLICATION
        assert kwargs["current_directory"] == _CURRENT
        self.events.append("create_process")
        if self.fail_create:
            raise WindowsEffectfulCaptureProcessNotCreatedError(
                "sanitized not-created test result"
            )
        return NativeCreatedProcess(1234, 5678, 106, 107)

    def begin_overlapped_write(self, handle: int, payload: bytes) -> object:
        assert handle == 102
        assert self.connection is not None
        phase = self.connection.execute(
            "SELECT phase FROM launch_executions"
        ).fetchone()
        assert phase == ("PRE_RESUME_READY",)
        self.events.append("write_request")
        if self.fail_write:
            raise RuntimeError("injected request failure")
        return payload

    def begin_overlapped_read(self, handle: int, max_bytes: int) -> object:
        assert handle == 103
        self.events.append(f"begin_read:{max_bytes}")
        return {"kind": "read", "max_bytes": max_bytes}

    def wait_overlapped_or_process(
        self, operation: object, process_handle: int | None, timeout_ms: int
    ) -> C3NativeWaitStatus:
        if type(operation) is bytes:
            assert process_handle is None
            return self.request_wait_status
        self.events.append(f"wait_observation:{timeout_ms}")
        return (
            self.wait_events.popleft()
            if self.wait_events
            else C3NativeWaitStatus.FAILED
        )

    def complete_overlapped(self, operation: object) -> NativeOverlappedCompletion:
        if type(operation) is bytes:
            payload = operation
            count = min(7, len(payload))
            self.written.extend(payload[:count])
            return NativeOverlappedCompletion(count, b"", False)
        assert type(operation) is dict
        if not self.result_chunks and self.result_factory is not None:
            factory = self.result_factory
            self.result_factory = None
            self.result_chunks.extend((factory(), None))
        chunk = self.result_chunks.popleft()
        if chunk is None:
            return NativeOverlappedCompletion(0, b"", True)
        assert len(chunk) <= operation["max_bytes"]
        return NativeOverlappedCompletion(len(chunk), chunk, False)

    def cancel_and_settle_overlapped(self, operation: object, timeout_ms: int) -> bool:
        self.events.append("cancel")
        return self.cancel_settles

    def quarantine_overlapped(self, operation: object) -> None:
        self.events.append("quarantine")

    def wait_process(self, process_handle: int, timeout_ms: int) -> C3NativeWaitStatus:
        assert process_handle == 106
        self.events.append(f"wait_process:{timeout_ms}")
        return (
            self.process_wait_events.popleft()
            if self.process_wait_events
            else C3NativeWaitStatus.FAILED
        )

    def get_exit_code_process(self, process_handle: int) -> int:
        assert process_handle == 106
        self.events.append("get_exit_code")
        return self.exit_code

    def terminate_job_object(self, job_handle: int) -> None:
        assert job_handle == 100
        self.events.append(f"terminate:{job_handle}")
        if self.fail_terminate:
            raise RuntimeError("injected termination failure")

    def resume_thread(self, thread_handle: int) -> int:
        assert thread_handle == 107
        assert self.connection is not None
        phase = self.connection.execute(
            "SELECT phase FROM launch_executions"
        ).fetchone()
        assert phase == ("RESUME_INTENT_COMMITTED",)
        self.events.append("resume_thread")
        if isinstance(self.resume_result, BaseException):
            raise self.resume_result
        return self.resume_result

    def close_handle(self, handle: int) -> None:
        self.events.append(f"close:{handle}")
        if handle == self.fail_close:
            raise RuntimeError("injected close failure")


def _authority():
    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=7,
        machine_authority_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        authority_epoch_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        signing_key_id="test-key",
        approved_account_sid="S-1-5-21-1",
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="ab" * 32,
    )
    evidence = ProductionAuthorityEvidence(
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="33" * 32,
        migration_id="migration-v1",
        release_manifest_digest="11" * 32,
        sqlite_build_manifest_digest="22" * 32,
    )
    return acquire_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=evidence,
    )


def _request() -> ProductionCaptureRequest:
    return ProductionCaptureRequest(
        ordered_universe=(Symbol("AAPL"), Symbol("MSFT")),
        request_window_start_date=date(2026, 8, 17),
        request_window_end_date=date(2026, 8, 17),
        target_session_date=date(2026, 8, 18),
    )


def _initialize_database(connection) -> None:
    execute_schema_artifact(connection)
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "test-epoch",
            "test-machine",
            1,
            1,
            "test-key",
            "S-1-5-21-1",
            ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
            ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
            "authority-policy/v1",
            "claim-policy/v1",
            "2026-01-01T00:00:00Z",
            b"b" * 32,
            b"d" * 32,
            b"{}",
            b"m" * 32,
            PRODUCTION_SCHEMA_ID,
            PRODUCTION_SCHEMA_VERSION,
            bytes.fromhex(PRODUCTION_SCHEMA_ARTIFACT_SHA256),
            "authority-metadata/v1",
            "authority-initialization/v1",
            1,
        ),
    )


def _orchestration_case(api: _FakeNativeApi):
    capture = object.__new__(WindowsEffectfulDailySnapshotCapture)
    capture._authority = _authority()
    capture._closed = False
    capture._transactional = object()
    plan = capture.prepare_capture_plan(
        _request(), datetime(2026, 8, 18, 14, tzinfo=UTC)
    )
    launch = C3C2NativeLaunchConfigurationForTest(
        application_name=_APPLICATION,
        arguments=("-m", "trading_bot.runtime.c3_child"),
        current_directory=_CURRENT,
        controlled_temp_directory=_TEMP,
        storage_root=_STORAGE_ROOT,
        parent_environment=_PARENT_ENV,
    )
    adapter = create_c3_c2_transactional_adapter_for_test(capture, plan, launch, api)
    database = open_disposable_authority_database_for_test(":memory:")
    connection = database._connection
    _initialize_database(connection)
    transactional = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=lambda _reservation_id: nullcontext(),
        external_adapter=adapter,
    )
    capture._adapter = adapter
    capture._transactional = transactional
    api.connection = connection
    return capture, plan, adapter, transactional, connection


def _case(api: _FakeNativeApi):
    capture, plan, adapter, transactional, connection = _orchestration_case(api)

    session_id = transactional.create_session(plan.request.to_c2_request_dict())
    attempt_id = transactional.allocate_attempt(session_id)
    claim_id = transactional.commit_claim(attempt_id)
    permit = transactional.reserve_launch(claim_id)
    provider = transactional.construct_provider(permit)
    intent = transactional.commit_process_intent(permit.reservation_id, provider)
    assert type(intent) is ProcessIntent
    return capture, plan, adapter, transactional, connection, intent


def _close(adapter, transactional) -> None:
    adapter.close()
    transactional.close()


def test_exact_c3_c2_order_builds_bound_request_then_resumes_once() -> None:
    api = _FakeNativeApi()
    capture, plan, adapter, transactional, connection, intent = _case(api)
    try:
        result = execute_c3_c2_resume_for_test(
            capture, transactional, adapter, plan, intent
        )

        request = parse_isolated_capture_child_request(bytes(api.written))
        assert request.reservation_id == result.reservation_id
        assert request.execution_id == result.execution_id
        assert request.capture_request == plan.request
        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "RESUME_INTENT_COMMITTED",
        )
        assert api.events.index("create_process") < api.events.index("write_request")
        assert api.events.index("close:102") < api.events.index("resume_thread")
        assert api.events.count("resume_thread") == 1
        assert c3_c2_registry_snapshot_for_test(adapter) == (
            (result.reservation_id, result.execution_id, True, True, False),
        )
        with pytest.raises(TypeError):
            pickle.dumps(result)
        with pytest.raises(TypeError):
            pickle.dumps(adapter)
    finally:
        _close(adapter, transactional)


def test_request_delivery_failure_stays_pre_resume_and_closes_writer() -> None:
    api = _FakeNativeApi(fail_write=True)
    capture, plan, adapter, transactional, connection, intent = _case(api)
    try:
        with pytest.raises(WindowsEffectfulCaptureNativeError, match="delivery failed"):
            execute_c3_c2_resume_for_test(capture, transactional, adapter, plan, intent)

        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "PRE_RESUME_READY",
        )
        assert api.events.count("close:102") == 1
        assert "resume_thread" not in api.events
        session_id = connection.execute("SELECT session_id FROM sessions").fetchone()[0]
        reservation_id = connection.execute(
            "SELECT launch_reservation_id FROM launch_reservations"
        ).fetchone()[0]
        evidence = b'{"evidence":"explicit-test-operator-evidence","schema":1}'
        transactional.record_recovery(
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_PRE_RESUME_READY",
            operator_evidence_json=evidence,
            operator_evidence_digest=hashlib.sha256(evidence).digest(),
        )
    finally:
        _close(adapter, transactional)


def test_request_delivery_timeout_quarantines_without_resume_intent() -> None:
    api = _FakeNativeApi(request_wait_status=C3NativeWaitStatus.TIMEOUT)
    api.cancel_settles = False
    capture, plan, adapter, transactional, connection, intent = _case(api)
    try:
        with pytest.raises(WindowsEffectfulCaptureNativeError, match="delivery failed"):
            execute_c3_c2_resume_for_test(capture, transactional, adapter, plan, intent)

        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "PRE_RESUME_READY",
        )
        assert connection.execute(
            "SELECT resume_intent_json, resume_intent_digest FROM launch_executions"
        ).fetchone() == (None, None)
        assert api.events.count("cancel") == 1
        assert api.events.count("quarantine") == 1
        assert "close:102" not in api.events
        assert "resume_thread" not in api.events
    finally:
        _close(adapter, transactional)


@pytest.mark.parametrize(
    "resume_result",
    [0xFFFFFFFF, 0, 2, RuntimeError("injected native exception")],
)
def test_resume_failure_or_unexpected_return_is_one_shot_and_post_intent(
    resume_result: int | BaseException,
) -> None:
    api = _FakeNativeApi(resume_result=resume_result)
    capture, plan, adapter, transactional, connection, intent = _case(api)
    try:
        with pytest.raises(WindowsEffectfulCaptureNativeError):
            execute_c3_c2_resume_for_test(capture, transactional, adapter, plan, intent)

        execution_id, reservation_id = connection.execute(
            "SELECT launch_execution_id, launch_reservation_id FROM launch_executions"
        ).fetchone()
        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "RESUME_INTENT_COMMITTED",
        )
        with pytest.raises(ValueError, match="PRE_RESUME_READY"):
            transactional.commit_resume_intent(execution_id, reservation_id)
        assert api.events.count("resume_thread") == 1
    finally:
        _close(adapter, transactional)


def test_registry_rejects_wrong_or_duplicate_execution_binding_and_dies_on_close() -> (
    None
):
    api = _FakeNativeApi()
    capture, _plan, adapter, transactional, _connection, intent = _case(api)
    try:
        receipt = transactional.create_process(intent)
        execution_id = transactional.record_execution(intent.reservation_id, receipt)
        adapter.bind_execution(receipt, intent.reservation_id, execution_id)

        with pytest.raises(
            WindowsEffectfulCaptureCompositionError, match="binding is invalid"
        ):
            adapter.bind_execution(receipt, intent.reservation_id, execution_id)
        with pytest.raises(
            WindowsEffectfulCaptureCompositionError, match="exact execution binding"
        ):
            transactional.deliver_c3_child_request(
                execution_id, intent.reservation_id, b"not-the-canonical-request"
            )
        assert api.written == b""
        with pytest.raises(
            WindowsEffectfulCaptureCompositionError, match="stale or mismatched"
        ):
            adapter.deliver_c3_child_request(
                "wrong-execution", intent.reservation_id, b"x"
            )

        adapter.close()
        assert c3_c2_registry_snapshot_for_test(adapter) == ()
    finally:
        adapter.close()
        transactional.close()
        capture._closed = True


def test_recovery_first_revokes_request_delivery_before_native_write() -> None:
    api = _FakeNativeApi()
    capture, _plan, adapter, transactional, connection, intent = _case(api)
    try:
        receipt = transactional.create_process(intent)
        execution_id = transactional.record_execution(intent.reservation_id, receipt)
        adapter.bind_execution(receipt, intent.reservation_id, execution_id)
        session_id = connection.execute("SELECT session_id FROM sessions").fetchone()[0]
        evidence = b'{"evidence":"explicit-test-operator-evidence","schema":1}'
        transactional.record_recovery(
            session_id,
            "LAUNCH_RESERVATION",
            intent.reservation_id,
            "CLASSIFY_PRE_RESUME_READY",
            operator_evidence_json=evidence,
            operator_evidence_digest=hashlib.sha256(evidence).digest(),
        )

        with pytest.raises(ValueError, match="revoked"):
            transactional.deliver_c3_child_request(
                execution_id,
                intent.reservation_id,
                adapter.child_request_payload(intent.reservation_id, execution_id),
            )

        assert api.written == b""
        assert "resume_thread" not in api.events
    finally:
        _close(adapter, transactional)


def test_delivered_request_then_recovery_wins_before_resume_intent_never_resumes() -> (
    None
):
    api = _FakeNativeApi()
    capture, _plan, adapter, transactional, connection, intent = _case(api)
    try:
        receipt = transactional.create_process(intent)
        execution_id = transactional.record_execution(intent.reservation_id, receipt)
        adapter.bind_execution(receipt, intent.reservation_id, execution_id)
        payload = adapter.child_request_payload(intent.reservation_id, execution_id)

        transactional.deliver_c3_child_request(
            execution_id, intent.reservation_id, payload
        )

        assert bytes(api.written) == payload
        assert api.events.count("close:102") == 1
        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "PRE_RESUME_READY",
        )

        session_id = connection.execute("SELECT session_id FROM sessions").fetchone()[0]
        evidence = b'{"evidence":"explicit-test-operator-evidence","schema":1}'
        transactional.record_recovery(
            session_id,
            "LAUNCH_RESERVATION",
            intent.reservation_id,
            "CLASSIFY_PRE_RESUME_READY",
            operator_evidence_json=evidence,
            operator_evidence_digest=hashlib.sha256(evidence).digest(),
        )

        with pytest.raises(ValueError, match="revoked"):
            transactional.commit_resume_intent(execution_id, intent.reservation_id)

        assert connection.execute(
            "SELECT resume_intent_json, resume_intent_digest, "
            "resume_intent_committed_at_utc FROM launch_executions"
        ).fetchone() == (None, None, None)
        assert "resume_thread" not in api.events
    finally:
        _close(adapter, transactional)


def test_public_production_facade_still_has_no_native_or_resume_injection() -> None:
    forbidden = {
        "application_name",
        "child_entrypoint",
        "controlled_temp_directory",
        "staging_path",
        "native_api",
        "provider",
        "resume_policy",
    }
    assert tuple(signature(WindowsEffectfulDailySnapshotCapture).parameters) == (
        "authority",
    )
    assert forbidden.isdisjoint(
        signature(WindowsEffectfulDailySnapshotCapture).parameters
    )
    assert MAX_C3_CHILD_REQUEST_BYTES > 0
    assert MAX_C3_CHILD_RESULT_BYTES > 0


def _trusted_result_bytes(resumed, **changes: object) -> bytes:
    result = IsolatedCaptureChildResult(
        reservation_id=resumed.reservation_id,
        execution_id=resumed.execution_id,
        child_request_sha256=resumed.child_request_sha256,
        fence_state=ProviderAttemptFenceState.ENTERED,
        classification=ChildResultClassification.TRANSPORT_FAILED,
        cleanup_status=ChildCleanupStatus.COMPLETE,
    )
    if changes:
        result = replace(result, **changes)
    return serialize_isolated_capture_child_result(result)


def _resume_case(api: _FakeNativeApi):
    capture, plan, adapter, transactional, connection, intent = _case(api)
    resumed = execute_c3_c2_resume_for_test(
        capture, transactional, adapter, plan, intent
    )
    return capture, adapter, transactional, connection, resumed


def test_c3_c3b_result_before_exit_is_drained_reconciled_and_cleaned_once() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _trusted_result_bytes(resumed)
    api.result_chunks.extend((payload[:11], payload[11:], None))
    api.wait_events.extend(
        (
            C3NativeWaitStatus.IO_COMPLETED,
            C3NativeWaitStatus.IO_COMPLETED,
            C3NativeWaitStatus.IO_COMPLETED,
        )
    )
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.result_transport is C3ResultTransportStatus.COMPLETE
        assert observation.process_outcome is C3ProcessOutcomeStatus.EXITED_ZERO
        assert observation.parent_cleanup is C3ParentCleanupStatus.COMPLETE
        assert observation.trusted_result is not None
        assert observation.trusted_result.child_request_sha256 == (
            resumed.child_request_sha256
        )
        assert c3_c2_registry_snapshot_for_test(adapter) == (
            (resumed.reservation_id, resumed.execution_id, True, True, True),
        )
        assert "close:105" not in api.events
        for handle in (103, 107, 106, 100):
            assert api.events.count(f"close:{handle}") == 1
        assert connection.execute(
            "SELECT phase, post_resume_json, post_resume_digest, cleanup_json, "
            "cleanup_digest FROM launch_executions"
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None, None, None)
        with pytest.raises(TypeError):
            pickle.dumps(observation)
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3b_process_exit_before_partial_result_still_requires_eof() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, _connection, resumed = _resume_case(api)
    payload = _trusted_result_bytes(resumed)
    api.exit_code = 259
    api.result_chunks.extend((payload[:7], payload[7:], None))
    api.wait_events.extend(
        (
            C3NativeWaitStatus.PROCESS_EXITED,
            C3NativeWaitStatus.IO_COMPLETED,
            C3NativeWaitStatus.IO_COMPLETED,
            C3NativeWaitStatus.IO_COMPLETED,
        )
    )
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.result_transport is C3ResultTransportStatus.COMPLETE
        assert observation.process_outcome is C3ProcessOutcomeStatus.EXITED_NONZERO
        assert observation.trusted_result is not None
        assert api.events.index("get_exit_code") < api.events.index("close:103")
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    "payload,expected",
    [
        (b"", C3ResultTransportStatus.EMPTY),
        (b"not-json", C3ResultTransportStatus.COMPLETE),
        (b"x" * MAX_C3_CHILD_RESULT_BYTES, C3ResultTransportStatus.COMPLETE),
    ],
)
def test_c3_c3b_empty_malformed_and_exact_bound_are_untrusted(
    payload: bytes, expected: C3ResultTransportStatus
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, _connection, resumed = _resume_case(api)
    api.result_chunks.extend(((payload,) if payload else ()) + (None,))
    api.wait_events.extend(
        C3NativeWaitStatus.IO_COMPLETED for _ in range(2 if payload else 1)
    )
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.result_transport is expected
        assert observation.trusted_result is None
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    "field,value",
    [
        ("reservation_id", "11111111-1111-4111-8111-111111111111"),
        ("execution_id", "22222222-2222-4222-8222-222222222222"),
        ("child_request_sha256", "ab" * 32),
    ],
)
def test_c3_c3b_wrong_result_lineage_is_untrusted(field: str, value: str) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, _connection, resumed = _resume_case(api)
    payload = _trusted_result_bytes(resumed, **{field: value})
    api.result_chunks.extend((payload, None))
    api.wait_events.extend(
        (C3NativeWaitStatus.IO_COMPLETED, C3NativeWaitStatus.IO_COMPLETED)
    )
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.result_transport is C3ResultTransportStatus.COMPLETE
        assert observation.trusted_result is None
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3b_oversized_result_is_never_parsed_and_is_contained() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, _connection, resumed = _resume_case(api)
    api.result_chunks.append(b"x" * (MAX_C3_CHILD_RESULT_BYTES + 1))
    api.wait_events.append(C3NativeWaitStatus.IO_COMPLETED)
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.result_transport is C3ResultTransportStatus.OVERSIZED
        assert observation.process_outcome is (
            C3ProcessOutcomeStatus.OBSERVATION_FAILED_TERMINATED
        )
        assert observation.trusted_result is None
        assert api.events.count("terminate:100") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3b_wait_failure_cancels_contains_and_cleans_independently() -> None:
    api = _FakeNativeApi(fail_close=107)
    capture, adapter, transactional, _connection, resumed = _resume_case(api)
    api.wait_events.append(C3NativeWaitStatus.FAILED)
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.result_transport is C3ResultTransportStatus.READ_FAILED
        assert observation.process_outcome is (
            C3ProcessOutcomeStatus.WAIT_FAILED_TERMINATED
        )
        assert observation.parent_cleanup is C3ParentCleanupStatus.FAILED
        assert api.events.count("cancel") == 1
        assert api.events.count("terminate:100") == 1
        for handle in (103, 107, 106, 100):
            assert api.events.count(f"close:{handle}") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3b_timeout_terminates_once_under_bounded_termination_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, _connection, resumed = _resume_case(api)
    api.wait_events.append(C3NativeWaitStatus.TIMEOUT)
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    remaining = iter((100, 0, 0))
    monkeypatch.setattr(
        "trading_bot.runtime.windows_effectful_capture_native._remaining_timeout_ms",
        lambda _deadline: next(remaining, 0),
    )
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.process_outcome is (
            C3ProcessOutcomeStatus.TIMED_OUT_TERMINATED
        )
        assert api.events.count("terminate:100") == 1
        assert api.events.count("cancel") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3b_unsettled_result_is_quarantined_and_cleanup_unresolved() -> None:
    api = _FakeNativeApi()
    api.cancel_settles = False
    capture, adapter, transactional, _connection, resumed = _resume_case(api)
    api.wait_events.append(C3NativeWaitStatus.FAILED)
    api.process_wait_events.append(C3NativeWaitStatus.TIMEOUT)
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.parent_cleanup is C3ParentCleanupStatus.UNRESOLVED
        assert observation.process_outcome is (
            C3ProcessOutcomeStatus.TERMINATION_UNCONFIRMED
        )
        assert api.events.count("quarantine") == 1
        assert "close:103" not in api.events
        assert api.events.count("terminate:100") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3b_termination_failure_is_unconfirmed_without_retry_authority() -> None:
    api = _FakeNativeApi(fail_terminate=True)
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    api.wait_events.append(C3NativeWaitStatus.FAILED)
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)

        assert observation.process_outcome is (
            C3ProcessOutcomeStatus.TERMINATION_UNCONFIRMED
        )
        assert observation.parent_cleanup is C3ParentCleanupStatus.UNRESOLVED
        assert api.events.count("terminate:100") == 1
        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "RESUME_INTENT_COMMITTED",
        )
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3b_rejects_substituted_resume_receipt_and_is_one_shot() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, _connection, resumed = _resume_case(api)
    substituted = replace(resumed, resume_receipt=replace(resumed.resume_receipt))
    try:
        with pytest.raises(WindowsEffectfulCaptureCompositionError, match="provenance"):
            observe_c3_c3b_for_test(adapter, substituted)

        payload = _trusted_result_bytes(resumed)
        api.result_chunks.extend((payload, None))
        api.wait_events.extend(
            (C3NativeWaitStatus.IO_COMPLETED, C3NativeWaitStatus.IO_COMPLETED)
        )
        api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
        observe_c3_c3b_for_test(adapter, resumed)
        with pytest.raises(WindowsEffectfulCaptureCompositionError, match="provenance"):
            observe_c3_c3b_for_test(adapter, resumed)
    finally:
        _close(adapter, transactional)
        capture._closed = True


def _observe_c3c_case(
    api: _FakeNativeApi,
    adapter,
    resumed,
    *,
    result_changes: dict[str, object] | None = None,
    trusted_result: bool = True,
):
    if trusted_result:
        payload = _trusted_result_bytes(resumed, **(result_changes or {}))
        api.result_chunks.extend((payload, None))
        api.wait_events.extend(
            (C3NativeWaitStatus.IO_COMPLETED, C3NativeWaitStatus.IO_COMPLETED)
        )
    else:
        api.result_chunks.append(None)
        api.wait_events.append(C3NativeWaitStatus.IO_COMPLETED)
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    return observe_c3_c3b_for_test(adapter, resumed)


def _canonical_c3_snapshot(
    api: _FakeNativeApi,
    *,
    request_id: UUID | None = None,
    requested_at: datetime | None = None,
    symbols: tuple[Symbol, ...] | None = None,
    provider: ProviderDescriptor = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
) -> bytes:
    child = parse_isolated_capture_child_request(bytes(api.written))
    requested_at = child.requested_at_utc if requested_at is None else requested_at
    request = DailySnapshotCaptureRequest(
        request_id=child.daily_snapshot_request_id
        if request_id is None
        else request_id,
        symbols=child.capture_request.ordered_universe if symbols is None else symbols,
        requested_at=requested_at,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
    )
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    provider_request = build_daily_provider_request(request, provider, calendar)
    candidates = tuple(
        DailyBarCandidate(
            response_ordinal=ordinal,
            symbol=symbol,
            session=provider_request.target_session,
            timestamp=datetime.combine(
                provider_request.target_session.session_date,
                datetime.min.time(),
                tzinfo=UTC,
            )
            + timedelta(hours=20),
            open=Decimal("100"),
            high=Decimal("103"),
            low=Decimal("99"),
            close=Decimal("102"),
            volume=1000 + ordinal,
        )
        for ordinal, symbol in enumerate(request.symbols)
    )
    source = b"deterministic C3 parent verification response"
    response = DailyProviderResponse(
        request=provider_request,
        candidates=candidates,
        captured_at=requested_at + timedelta(seconds=1),
        provider_as_of=requested_at,
        provider_request_id="c3-parent-verification",
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


def _automatic_child_result(
    api: _FakeNativeApi,
    classification: ChildResultClassification,
    *,
    http_status: int = 403,
    provider_request_id: str | None = "c3-http-failure",
) -> bytes:
    request_bytes = bytes(api.written)
    child = parse_isolated_capture_child_request(request_bytes)
    values: dict[str, object] = {}
    if classification is ChildResultClassification.SUCCEEDED:
        payload = _canonical_c3_snapshot(api)
        api.staging_bytes = payload
        values = {
            "artifact_byte_length": len(payload),
            "artifact_sha256": hashlib.sha256(payload).hexdigest(),
            "http_status": 200,
            "provider_request_id": "c3-parent-verification",
            "snapshot_id": UUID(json.loads(payload)["snapshot_id"]),
        }
    elif classification is ChildResultClassification.HTTP_FAILED:
        values = {
            "http_status": http_status,
            "provider_request_id": provider_request_id,
        }
    result = IsolatedCaptureChildResult(
        reservation_id=child.reservation_id,
        execution_id=child.execution_id,
        child_request_sha256=hashlib.sha256(request_bytes).hexdigest(),
        fence_state=ProviderAttemptFenceState.ENTERED,
        classification=classification,
        cleanup_status=ChildCleanupStatus.COMPLETE,
        **values,
    )
    return serialize_isolated_capture_child_result(result)


def _run_complete_invocation(
    api: _FakeNativeApi,
    classification: ChildResultClassification | None,
    *,
    http_status: int = 403,
    provider_request_id: str | None = "c3-http-failure",
):
    capture, plan, adapter, transactional, connection = _orchestration_case(api)
    if classification is None:
        api.result_factory = lambda: b"not-canonical-child-result"
    else:
        api.result_factory = lambda: _automatic_child_result(
            api,
            classification,
            http_status=http_status,
            provider_request_id=provider_request_id,
        )
    api.wait_events.extend(
        (C3NativeWaitStatus.IO_COMPLETED, C3NativeWaitStatus.IO_COMPLETED)
    )
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    result = service_module._capture_prepared_once_for_test(capture, plan)
    return capture, adapter, transactional, connection, result


def test_c3_e31_complete_success_orders_evidence_verification_terminal_selection() -> (
    None
):
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, result = _run_complete_invocation(
        api, ChildResultClassification.SUCCEEDED
    )
    try:
        assert result.terminal_state == "SUCCEEDED"
        assert result.provider_call_disposition == "CONFIRMED"
        assert result.selection_id is not None
        assert result.snapshot_id is not None
        assert result.artifact_sha256 == hashlib.sha256(api.staging_bytes).hexdigest()
        assert result.artifact_byte_length == len(api.staging_bytes)
        assert connection.execute("SELECT count(*) FROM sessions").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM provider_call_claims"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM launch_reservations"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM launch_executions"
        ).fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT snapshot_digest FROM terminals WHERE terminal_id = ?",
            (result.terminal_id,),
        ).fetchone() == (bytes.fromhex(result.artifact_sha256),)
        assert connection.execute(
            "SELECT terminal_id FROM session_selections"
        ).fetchone() == (result.terminal_id,)
        assert api.events.count("create_process") == 1
        assert api.events.count("resume_thread") == 1
        assert api.events.count("publish") == 1
        assert api.events.index("resume_thread") < api.events.index("read_artifact:105")
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    ("classification", "expected_state", "expected_disposition"),
    [
        (ChildResultClassification.TRANSPORT_FAILED, "FAILED", "CONFIRMED"),
        (ChildResultClassification.TRANSPORT_REQUEST_FAILED, "FAILED", "CONFIRMED"),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_START_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_ACQUISITION_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_MALFORMED_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_DUPLICATE_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_CONTENT_ENCODING_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_TRANSFER_ENCODING_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_LENGTH_CONFLICT_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_CONTENT_LENGTH_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_REQUEST_ID_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_MISSING_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_MEDIA_TYPE_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_CHARSET_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_PARAMETER_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (
            ChildResultClassification.TRANSPORT_RESPONSE_BODY_FAILED,
            "FAILED",
            "CONFIRMED",
        ),
        (ChildResultClassification.HTTP_FAILED, "FAILED", "CONFIRMED"),
        (None, "AMBIGUOUS", "MAY_HAVE_OCCURRED"),
    ],
)
def test_c3_e31_non_success_is_terminal_unselected_and_never_retried(
    classification: ChildResultClassification | None,
    expected_state: str,
    expected_disposition: str,
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, result = _run_complete_invocation(
        api, classification
    )
    try:
        assert result.terminal_state == expected_state
        assert result.provider_call_disposition == expected_disposition
        assert result.selection_id is None
        assert result.snapshot_id is None
        assert result.artifact_sha256 is None
        assert connection.execute(
            "SELECT terminal_state, provider_call_disposition, snapshot_digest "
            "FROM terminals"
        ).fetchone() == (expected_state, expected_disposition, None)
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
        assert api.events.count("create_process") == 1
        assert api.events.count("resume_thread") == 1
        assert "publish" not in api.events
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    ("status", "request_id"),
    [(403, "durable-request-403"), (429, None)],
)
def test_c3_e35_http_failure_is_exact_durable_operator_evidence(
    status: int,
    request_id: str | None,
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, result = _run_complete_invocation(
        api,
        ChildResultClassification.HTTP_FAILED,
        http_status=status,
        provider_request_id=request_id,
    )
    try:
        row = connection.execute(
            "SELECT evidence_json, evidence_digest FROM terminals"
        ).fetchone()
        evidence = json.loads(row[0])

        assert result.terminal_state == "FAILED"
        assert result.provider_call_disposition == "CONFIRMED"
        assert result.http_status == status
        assert result.provider_request_id == request_id
        assert result.selection_id is None
        assert evidence["schema"] == 2
        assert evidence["child_result_classification"] == "HTTP_FAILED"
        assert evidence["http_status"] == status
        assert evidence["provider_request_id"] == request_id
        assert row[1] == hashlib.sha256(row[0]).digest()
        assert len(row[0]) <= 2048
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
        assert api.events.count("create_process") == 1
        assert api.events.count("resume_thread") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_e31_parent_verification_failure_uses_c3_terminal_mapping() -> None:
    api = _FakeNativeApi()
    api.fail_publish = True
    capture, adapter, transactional, connection, result = _run_complete_invocation(
        api, ChildResultClassification.SUCCEEDED
    )
    try:
        assert result.terminal_state == "FAILED"
        assert result.provider_call_disposition == "CONFIRMED"
        assert result.selection_id is None
        diagnostics = json.loads(
            connection.execute(
                "SELECT sanitized_diagnostics_json FROM terminals"
            ).fetchone()[0]
        )
        assert diagnostics["reason"] == "PARENT_ARTIFACT_VERIFICATION_FAILED"
        assert api.events.count("create_process") == 1
        assert api.events.count("resume_thread") == 1
        assert api.events.count("publish") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_e31_definitive_not_created_is_failed_terminal_without_resume() -> None:
    api = _FakeNativeApi(fail_create=True)
    capture, plan, adapter, transactional, connection = _orchestration_case(api)
    try:
        result = service_module._capture_prepared_once_for_test(capture, plan)

        assert result.terminal_state == "FAILED"
        assert result.provider_call_disposition == "NOT_STARTED"
        assert result.execution_id is None
        assert result.selection_id is None
        assert connection.execute(
            "SELECT terminal_state, provider_call_disposition, snapshot_digest "
            "FROM terminals"
        ).fetchone() == ("FAILED", "NOT_STARTED", None)
        assert api.events.count("create_process") == 1
        assert "resume_thread" not in api.events
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
    finally:
        _close(adapter, transactional)
        capture._closed = True


def _persist_successful_c3_observation(
    api: _FakeNativeApi,
    adapter,
    transactional,
    resumed,
    payload: bytes,
    *,
    child_changes: dict[str, object] | None = None,
    snapshot_id: UUID | None = None,
):
    api.staging_bytes = payload
    if snapshot_id is None:
        snapshot_id = UUID(json.loads(payload)["snapshot_id"])
    changes: dict[str, object] = {
        "classification": ChildResultClassification.SUCCEEDED,
        "snapshot_id": snapshot_id,
        "artifact_sha256": hashlib.sha256(payload).hexdigest(),
        "artifact_byte_length": len(payload),
        "http_status": 200,
        "provider_request_id": "c3-parent-verification",
    }
    changes.update(child_changes or {})
    child_payload = _trusted_result_bytes(
        resumed,
        **changes,
    )
    api.result_chunks.extend((child_payload, None))
    api.wait_events.extend(
        (C3NativeWaitStatus.IO_COMPLETED, C3NativeWaitStatus.IO_COMPLETED)
    )
    api.process_wait_events.append(C3NativeWaitStatus.PROCESS_EXITED)
    observation = observe_c3_c3b_for_test(adapter, resumed)
    evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
    transactional.record_c3_post_resume_evidence(
        resumed.execution_id, resumed.resume_receipt, evidence
    )
    return observation


def test_c3_d1_parent_verifies_publishes_reopens_and_issues_exact_capability() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        observation = _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        capability = transactional.verify_c3_captured_snapshot(
            resumed.execution_id, resumed.reservation_id
        )

        assert type(capability) is VerifiedCapturedSnapshot
        lineage = connection.execute(
            """
            SELECT s.session_id, a.attempt_id, c.claim_id
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            """
        ).fetchone()
        assert (
            capability.session_id,
            capability.attempt_id,
            capability.claim_id,
        ) == lineage
        assert capability.reservation_id == resumed.reservation_id
        assert capability.execution_id == resumed.execution_id
        assert capability.artifact_sha256 == hashlib.sha256(payload).hexdigest()
        assert capability.artifact_byte_length == len(payload)
        assert (
            capability.child_result_sha256
            == hashlib.sha256(
                serialize_isolated_capture_child_result(observation.trusted_result)
            ).hexdigest()
        )
        expected_name = f"daily-market-data-snapshot-{capability.snapshot_id}.json"
        expected_evidence = json.dumps(
            {
                "artifact_byte_length": len(payload),
                "artifact_sha256": hashlib.sha256(payload).hexdigest(),
                "final_canonical_filename": expected_name,
                "native_file_identity": api.file_identity.canonical_evidence(),
                "schema": 1,
                "snapshot_id": str(capability.snapshot_id),
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
        assert (
            capability.artifact_identity_sha256
            == hashlib.sha256(expected_evidence).hexdigest()
        )
        transactional.validate_c3_verified_snapshot(capability)
        with pytest.raises(WindowsEffectfulCaptureProtocolError, match="binding"):
            transactional.validate_c3_verified_snapshot(replace(capability))
        assert api.events.index("publish") < api.events.index("open_final")
        assert api.events.index("open_final") < api.events.index("delete_staging")
        assert api.events.count("close:105") == 1
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d1_recovery_before_verification_prevents_publication() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        session_id, attempt_id = connection.execute(
            "SELECT session_id, attempt_id FROM attempts"
        ).fetchone()
        operator = b'{"evidence":"recovery-first-c3-d1","schema":1}'
        transactional.record_recovery(
            session_id,
            "ATTEMPT",
            attempt_id,
            "RECORD_ATTEMPT_AMBIGUITY",
            operator_evidence_json=operator,
            operator_evidence_digest=hashlib.sha256(operator).digest(),
        )
        with pytest.raises(ValueError, match="unavailable"):
            transactional.verify_c3_captured_snapshot(
                resumed.execution_id, resumed.reservation_id
            )
        assert "publish" not in api.events
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d1_verified_capability_is_revoked_by_later_recovery() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        capability = transactional.verify_c3_captured_snapshot(
            resumed.execution_id, resumed.reservation_id
        )
        session_id, attempt_id = connection.execute(
            "SELECT session_id, attempt_id FROM attempts"
        ).fetchone()
        operator = b'{"evidence":"delayed-c3-d1","schema":1}'
        transactional.record_recovery(
            session_id,
            "ATTEMPT",
            attempt_id,
            "RECORD_ATTEMPT_AMBIGUITY",
            operator_evidence_json=operator,
            operator_evidence_digest=hashlib.sha256(operator).digest(),
        )
        with pytest.raises(ValueError, match="unavailable"):
            transactional.validate_c3_verified_snapshot(capability)
        with pytest.raises(ValueError, match="unavailable"):
            transactional.record_c3_terminal(
                resumed.execution_id, resumed.reservation_id, capability
            )
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    "case",
    [
        "staging_identity",
        "oversize",
        "truncated",
        "appended",
        "noncanonical",
        "invalid_utf8",
        "wrong_request_uuid",
        "wrong_requested_at",
        "wrong_session",
        "wrong_universe",
        "wrong_provider",
        "child_digest",
        "child_length",
        "final_collision",
        "publication_failure",
        "final_identity",
        "final_bytes",
        "cleanup_failure",
    ],
)
def test_c3_d1_parent_verification_failures_never_issue_authority(case: str) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    canonical = _canonical_c3_snapshot(api)
    original_id = UUID(json.loads(canonical)["snapshot_id"])
    payload = canonical
    child_changes: dict[str, object] = {}
    if case == "truncated":
        payload = canonical[:-8]
    elif case == "appended":
        payload = canonical + b"x"
    elif case == "noncanonical":
        payload = b" " + canonical
    elif case == "invalid_utf8":
        payload = b"\xff\n"
    elif case == "wrong_request_uuid":
        payload = _canonical_c3_snapshot(
            api, request_id=UUID("11111111-1111-4111-8111-111111111111")
        )
    elif case == "wrong_requested_at":
        payload = _canonical_c3_snapshot(
            api, requested_at=datetime(2026, 8, 18, 15, tzinfo=UTC)
        )
    elif case == "wrong_session":
        payload = _canonical_c3_snapshot(
            api, requested_at=datetime(2026, 8, 19, 14, tzinfo=UTC)
        )
    elif case == "wrong_universe":
        payload = _canonical_c3_snapshot(api, symbols=(Symbol("AAPL"),))
    elif case == "wrong_provider":
        payload = _canonical_c3_snapshot(
            api, provider=ProviderDescriptor("other", 1, "daily-bars", "sip")
        )
    elif case == "child_digest":
        child_changes["artifact_sha256"] = "12" * 32
    elif case == "child_length":
        child_changes["artifact_byte_length"] = len(canonical) + 1

    try:
        _persist_successful_c3_observation(
            api,
            adapter,
            transactional,
            resumed,
            payload,
            child_changes=child_changes,
            snapshot_id=(
                original_id
                if case in {"truncated", "appended", "noncanonical", "invalid_utf8"}
                else None
            ),
        )
        if case == "staging_identity":
            api.file_identity = NativeFileIdentity(8, b"x" * 16)
        elif case == "oversize":
            api.staging_bytes = b"x" * (4 * 1024 * 1024 + 1)
        elif case == "final_collision":
            api.casefold_collision = True
        elif case == "publication_failure":
            api.fail_publish = True
        elif case == "final_identity":
            api.final_identity = NativeFileIdentity(9, b"f" * 16)
        elif case == "final_bytes":
            api.final_bytes = b"changed\n"
        elif case == "cleanup_failure":
            api.fail_cleanup = True

        with pytest.raises(
            WindowsEffectfulCaptureCompositionError,
            match="parent artifact verification failed",
        ):
            transactional.verify_c3_captured_snapshot(
                resumed.execution_id, resumed.reservation_id
            )
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
        if case == "staging_identity":
            assert "delete_staging" not in api.events
        if case == "cleanup_failure":
            assert api.events.count("delete_staging") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d1_non_success_child_result_cannot_verify() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        observation = _observe_c3c_case(api, adapter, resumed)
        evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
        transactional.record_c3_post_resume_evidence(
            resumed.execution_id, resumed.resume_receipt, evidence
        )
        with pytest.raises(WindowsEffectfulCaptureCompositionError):
            transactional.verify_c3_captured_snapshot(
                resumed.execution_id, resumed.reservation_id
            )
        assert "publish" not in api.events
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d1_cleanup_identity_mismatch_is_not_blindly_deleted() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        changed = NativeFileIdentity(10, b"z" * 16)
        api.identity_results.extend(
            (api.file_identity, api.file_identity, changed, changed)
        )
        with pytest.raises(WindowsEffectfulCaptureCompositionError):
            transactional.verify_c3_captured_snapshot(
                resumed.execution_id, resumed.reservation_id
            )
        assert "publish" in api.events
        assert "delete_staging" not in api.events
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    ("result_changes", "trusted_result", "expected_disposition"),
    [
        ({}, True, "CONFIRMED"),
        (
            {
                "fence_state": ProviderAttemptFenceState.NOT_ENTERED,
                "classification": ChildResultClassification.REQUEST_INVALID,
            },
            True,
            "MAY_HAVE_OCCURRED",
        ),
        ({}, False, "MAY_HAVE_OCCURRED"),
    ],
)
def test_c3_c3c_cleanup_disposition_and_exact_persistence(
    result_changes: dict[str, object],
    trusted_result: bool,
    expected_disposition: str,
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        observation = _observe_c3c_case(
            api,
            adapter,
            resumed,
            result_changes=result_changes,
            trusted_result=trusted_result,
        )
        evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
        cleanup_json, cleanup_digest = adapter.validate_c3_post_resume_evidence(
            evidence,
            execution_id=resumed.execution_id,
            reservation_id=resumed.reservation_id,
            resume_receipt=resumed.resume_receipt,
        )
        cleanup = json.loads(cleanup_json)
        trusted = observation.trusted_result
        expected_child_sha = (
            None
            if trusted is None
            else hashlib.sha256(
                serialize_isolated_capture_child_result(trusted)
            ).hexdigest()
        )
        assert cleanup == {
            "child_fence_state": (
                None if trusted is None else trusted.fence_state.value
            ),
            "child_request_sha256": resumed.child_request_sha256,
            "child_result_classification": (
                None if trusted is None else trusted.classification.value
            ),
            "child_result_sha256": expected_child_sha,
            "execution_id": resumed.execution_id,
            "http_status": None,
            "parent_cleanup": observation.parent_cleanup.value,
            "process_outcome": observation.process_outcome.value,
            "provider_call_disposition": expected_disposition,
            "provider_request_id": None,
            "reservation_id": resumed.reservation_id,
            "result_transport": observation.result_transport.value,
            "schema": 2,
        }
        assert cleanup_json == json.dumps(
            cleanup,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        assert cleanup_digest == hashlib.sha256(cleanup_json).digest()
        assert cleanup["provider_call_disposition"] != "NOT_STARTED"

        transactional.record_c3_post_resume_evidence(
            resumed.execution_id, resumed.resume_receipt, evidence
        )

        assert connection.execute(
            "SELECT phase, post_resume_json, post_resume_digest, cleanup_json, "
            "cleanup_digest FROM launch_executions"
        ).fetchone() == (
            "RESUME_RECORDED",
            resumed.resume_receipt.result_json,
            resumed.resume_receipt.result_digest,
            cleanup_json,
            cleanup_digest,
        )
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
        assert "close:105" not in api.events
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3c_failed_parent_cleanup_is_eligible() -> None:
    api = _FakeNativeApi(fail_close=107)
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        observation = _observe_c3c_case(api, adapter, resumed)
        assert observation.parent_cleanup is C3ParentCleanupStatus.FAILED
        evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)

        transactional.record_c3_post_resume_evidence(
            resumed.execution_id, resumed.resume_receipt, evidence
        )

        cleanup_json = connection.execute(
            "SELECT cleanup_json FROM launch_executions"
        ).fetchone()[0]
        assert json.loads(cleanup_json)["parent_cleanup"] == "FAILED"
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3c_unresolved_cleanup_and_unconfirmed_termination_are_ineligible() -> None:
    api = _FakeNativeApi()
    api.cancel_settles = False
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    api.wait_events.append(C3NativeWaitStatus.FAILED)
    api.process_wait_events.append(C3NativeWaitStatus.TIMEOUT)
    try:
        observation = observe_c3_c3b_for_test(adapter, resumed)
        assert observation.parent_cleanup is C3ParentCleanupStatus.UNRESOLVED
        assert observation.process_outcome is (
            C3ProcessOutcomeStatus.TERMINATION_UNCONFIRMED
        )

        with pytest.raises(WindowsEffectfulCaptureCompositionError, match="unresolved"):
            issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)

        assert connection.execute(
            "SELECT phase, post_resume_json, cleanup_json FROM launch_executions"
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3c_exact_provenance_private_capability_and_one_shot() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        observation = _observe_c3c_case(api, adapter, resumed)
        with pytest.raises(WindowsEffectfulCaptureCompositionError, match="provenance"):
            issue_c3_post_resume_evidence_for_test(
                adapter, resumed, replace(observation)
            )
        with pytest.raises(WindowsEffectfulCaptureCompositionError, match="provenance"):
            issue_c3_post_resume_evidence_for_test(
                adapter,
                replace(resumed, resume_receipt=replace(resumed.resume_receipt)),
                observation,
            )

        evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
        for operation in (copy, deepcopy, pickle.dumps):
            with pytest.raises(TypeError):
                operation(evidence)
        with pytest.raises(TypeError):
            type(evidence)(object(), object(), object())
        for execution_id, reservation_id, receipt in (
            ("wrong-execution", resumed.reservation_id, resumed.resume_receipt),
            (resumed.execution_id, "wrong-reservation", resumed.resume_receipt),
            (
                resumed.execution_id,
                resumed.reservation_id,
                replace(resumed.resume_receipt),
            ),
        ):
            with pytest.raises(WindowsEffectfulCaptureCompositionError):
                adapter.validate_c3_post_resume_evidence(
                    evidence,
                    execution_id=execution_id,
                    reservation_id=reservation_id,
                    resume_receipt=receipt,
                )
        with pytest.raises(TypeError):
            adapter.validate_c3_post_resume_evidence(
                object(),
                execution_id=resumed.execution_id,
                reservation_id=resumed.reservation_id,
                resume_receipt=resumed.resume_receipt,
            )
        with pytest.raises(Exception, match="C3 post-resume evidence operation"):
            transactional.record_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt
            )

        transactional.record_c3_post_resume_evidence(
            resumed.execution_id, resumed.resume_receipt, evidence
        )
        with pytest.raises((ValueError, WindowsEffectfulCaptureCompositionError)):
            transactional.record_c3_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt, evidence
            )
        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "RESUME_RECORDED",
        )
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize("attribute", ["_issuer", "_permit"])
def test_c3_c3c_reflectively_mutated_capability_fails_closed(attribute: str) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        observation = _observe_c3c_case(api, adapter, resumed)
        evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
        object.__setattr__(evidence, attribute, object())

        with pytest.raises(
            WindowsEffectfulCaptureCompositionError, match="binding mismatch"
        ):
            transactional.record_c3_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt, evidence
            )
        assert connection.execute(
            "SELECT phase, post_resume_json, cleanup_json FROM launch_executions"
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3c_registry_close_revokes_stale_capability() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        observation = _observe_c3c_case(api, adapter, resumed)
        evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
        adapter.close()

        with pytest.raises(
            WindowsEffectfulCaptureCompositionError, match="stale or mismatched"
        ):
            transactional.record_c3_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt, evidence
            )
        assert connection.execute(
            "SELECT phase, post_resume_json, cleanup_json FROM launch_executions"
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize("tamper", ["bytes", "digest"])
def test_c3_c3c_tampered_adapter_pair_fails_without_consuming(
    monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        observation = _observe_c3c_case(api, adapter, resumed)
        evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
        adapter_type = type(adapter)
        original = adapter_type.validate_c3_post_resume_evidence

        def tampered_validate(self, candidate, **kwargs):
            cleanup_json, cleanup_digest = original(self, candidate, **kwargs)
            if tamper == "bytes":
                return cleanup_json + b" ", cleanup_digest
            return cleanup_json, b"x" * 32

        monkeypatch.setattr(
            adapter_type, "validate_c3_post_resume_evidence", tampered_validate
        )
        with pytest.raises(ValueError, match="digest"):
            transactional.record_c3_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt, evidence
            )
        assert connection.execute(
            "SELECT phase, post_resume_json, cleanup_json FROM launch_executions"
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)

        monkeypatch.setattr(adapter_type, "validate_c3_post_resume_evidence", original)
        transactional.record_c3_post_resume_evidence(
            resumed.execution_id, resumed.resume_receipt, evidence
        )
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3c_database_rollback_preserves_both_capabilities_for_retry() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        observation = _observe_c3c_case(api, adapter, resumed)
        evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
        connection.execute(
            """
            CREATE TRIGGER fail_c3_post_resume
            BEFORE UPDATE ON launch_executions
            WHEN NEW.phase = 'RESUME_RECORDED'
            BEGIN
                SELECT RAISE(ABORT, 'injected C3 rollback');
            END
            """
        )
        with pytest.raises(Exception, match="injected C3 rollback"):
            transactional.record_c3_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt, evidence
            )
        assert connection.execute(
            "SELECT phase, post_resume_json, cleanup_json FROM launch_executions"
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
        adapter.validate_c3_post_resume_evidence(
            evidence,
            execution_id=resumed.execution_id,
            reservation_id=resumed.reservation_id,
            resume_receipt=resumed.resume_receipt,
        )

        connection.execute("DROP TRIGGER fail_c3_post_resume")
        transactional.record_c3_post_resume_evidence(
            resumed.execution_id, resumed.resume_receipt, evidence
        )
        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "RESUME_RECORDED",
        )
        assert api.events.count("resume_thread") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_c3c_recovery_and_service_close_revoke_delayed_evidence() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    observation = _observe_c3c_case(api, adapter, resumed)
    evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
    session_id = connection.execute("SELECT session_id FROM sessions").fetchone()[0]
    operator_json = b'{"evidence":"c3-c3c-recovery","schema":1}'
    try:
        transactional.record_recovery(
            session_id,
            "LAUNCH_RESERVATION",
            resumed.reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
            operator_evidence_json=operator_json,
            operator_evidence_digest=hashlib.sha256(operator_json).digest(),
        )
        with pytest.raises(ValueError, match="revoked|unavailable"):
            transactional.record_c3_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt, evidence
            )
        assert connection.execute(
            "SELECT phase, post_resume_json, cleanup_json FROM launch_executions"
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
        assert connection.execute(
            "SELECT reservation_state FROM launch_reservations"
        ).fetchone() == ("MANUAL_REVIEW",)

        with pytest.raises(
            ExternalAuthorityBoundaryUnavailable,
            match="legacy terminal recording is unavailable",
        ):
            transactional.record_terminal(
                resumed.reservation_id,
                "CLOSED",
                "MAY_HAVE_OCCURRED",
                snapshot_digest=None,
            )
        with pytest.raises(ValueError, match="revoked|unavailable"):
            transactional.record_c3_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt, evidence
            )

        transactional.close()
        with pytest.raises(Exception, match="closed"):
            transactional.record_c3_post_resume_evidence(
                resumed.execution_id, resumed.resume_receipt, evidence
            )
    finally:
        adapter.close()
        transactional.close()
        capture._closed = True


def _c3_lineage(connection) -> tuple[str, str, str, str, str]:
    return connection.execute(
        """
        SELECT s.session_id, a.attempt_id, c.claim_id,
               r.launch_reservation_id, e.launch_execution_id
        FROM launch_executions e
        JOIN launch_reservations r
          ON r.launch_reservation_id = e.launch_reservation_id
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        """
    ).fetchone()


def _persist_c3_terminal_observation(
    api: _FakeNativeApi,
    adapter,
    transactional,
    resumed,
    *,
    result_changes: dict[str, object] | None = None,
    trusted_result: bool = True,
):
    observation = _observe_c3c_case(
        api,
        adapter,
        resumed,
        result_changes=result_changes,
        trusted_result=trusted_result,
    )
    evidence = issue_c3_post_resume_evidence_for_test(adapter, resumed, observation)
    transactional.record_c3_post_resume_evidence(
        resumed.execution_id, resumed.resume_receipt, evidence
    )
    return observation


def _terminal_row(connection):
    return connection.execute(
        "SELECT terminal_state, provider_call_disposition, snapshot_digest, "
        "evidence_json, evidence_digest, sanitized_diagnostics_json, "
        "sanitized_diagnostics_digest FROM terminals"
    ).fetchone()


def test_c3_d2_verified_snapshot_records_exact_success_without_selection() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        capability = transactional.verify_c3_captured_snapshot(
            resumed.execution_id, resumed.reservation_id
        )
        with pytest.raises(
            ExternalAuthorityBoundaryUnavailable,
            match="legacy terminal recording is unavailable",
        ):
            transactional.record_terminal(
                resumed.reservation_id,
                snapshot_digest=b"x" * 32,
            )

        terminal_id = transactional.record_c3_terminal(
            resumed.execution_id, resumed.reservation_id, capability
        )

        row = _terminal_row(connection)
        expected_digest = hashlib.sha256(payload).digest()
        assert row[:3] == ("SUCCEEDED", "CONFIRMED", expected_digest)
        evidence = json.loads(row[3])
        diagnostics = json.loads(row[5])
        assert row[4] == hashlib.sha256(row[3]).digest()
        assert row[6] == hashlib.sha256(row[5]).digest()
        assert len(row[3]) <= 2048
        assert evidence["terminal_state"] == "SUCCEEDED"
        assert evidence["provider_call_disposition"] == "CONFIRMED"
        assert evidence["artifact_sha256"] == hashlib.sha256(payload).hexdigest()
        assert evidence["snapshot_id"] == str(capability.snapshot_id)
        assert evidence["artifact_identity_sha256"] == (
            capability.artifact_identity_sha256
        )
        assert evidence["staging_cleanup"] == "COMPLETE"
        assert diagnostics == {
            "artifact_verification": "VERIFIED",
            "parent_cleanup": evidence["parent_cleanup"],
            "reason": "VERIFIED_SNAPSHOT",
            "result_transport": evidence["result_transport"],
            "schema": 1,
            "staging_cleanup": "COMPLETE",
        }
        assert connection.execute("SELECT state FROM sessions").fetchone() == ("OPEN",)
        assert connection.execute("SELECT state FROM attempts").fetchone() == (
            "TERMINAL_RECORDED",
        )
        assert connection.execute(
            "SELECT reservation_state FROM launch_reservations"
        ).fetchone() == ("TERMINAL_RECORDED",)
        assert connection.execute("SELECT phase FROM launch_executions").fetchone() == (
            "TERMINAL_RECORDED",
        )
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
        assert c3_c2_registry_snapshot_for_test(adapter) == ()
        with pytest.raises(
            (
                WindowsEffectfulCaptureCompositionError,
                WindowsEffectfulCaptureProtocolError,
            )
        ):
            transactional.validate_c3_verified_snapshot(capability)
        with pytest.raises(ValueError, match="unavailable"):
            transactional.record_c3_terminal(
                resumed.execution_id, resumed.reservation_id, capability
            )
        assert connection.execute("SELECT terminal_id FROM terminals").fetchone() == (
            terminal_id,
        )
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d2_copied_or_reconstructed_verified_snapshot_cannot_authorize() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        capability = transactional.verify_c3_captured_snapshot(
            resumed.execution_id, resumed.reservation_id
        )
        with pytest.raises(TypeError):
            copy(capability)
        for candidate in (
            replace(capability),
            replace(capability, artifact_sha256="12" * 32),
        ):
            with pytest.raises(
                (
                    WindowsEffectfulCaptureCompositionError,
                    WindowsEffectfulCaptureProtocolError,
                )
            ):
                transactional.record_c3_terminal(
                    resumed.execution_id, resumed.reservation_id, candidate
                )
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)

        transactional.record_c3_terminal(
            resumed.execution_id, resumed.reservation_id, capability
        )
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d2_success_rollback_preserves_exact_capability_for_retry() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        capability = transactional.verify_c3_captured_snapshot(
            resumed.execution_id, resumed.reservation_id
        )
        connection.execute(
            """
            CREATE TRIGGER fail_c3_terminal
            BEFORE INSERT ON terminals
            BEGIN
                SELECT RAISE(ABORT, 'injected C3 terminal rollback');
            END
            """
        )
        with pytest.raises(Exception, match="injected C3 terminal rollback"):
            transactional.record_c3_terminal(
                resumed.execution_id, resumed.reservation_id, capability
            )
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
        transactional.validate_c3_verified_snapshot(capability)

        connection.execute("DROP TRIGGER fail_c3_terminal")
        transactional.record_c3_terminal(
            resumed.execution_id, resumed.reservation_id, capability
        )
        assert api.events.count("delete_staging") == 1
        assert api.events.count("close:105") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    ("result_changes", "trusted_result", "expected_state", "expected_disposition"),
    [
        ({}, True, "FAILED", "CONFIRMED"),
        (
            {
                "fence_state": ProviderAttemptFenceState.NOT_ENTERED,
                "classification": ChildResultClassification.REQUEST_INVALID,
            },
            True,
            "AMBIGUOUS",
            "MAY_HAVE_OCCURRED",
        ),
        ({}, False, "AMBIGUOUS", "MAY_HAVE_OCCURRED"),
    ],
)
def test_c3_d2_non_success_mapping_and_safe_staging_cleanup(
    result_changes: dict[str, object],
    trusted_result: bool,
    expected_state: str,
    expected_disposition: str,
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        _persist_c3_terminal_observation(
            api,
            adapter,
            transactional,
            resumed,
            result_changes=result_changes,
            trusted_result=trusted_result,
        )
        transactional.record_c3_terminal(resumed.execution_id, resumed.reservation_id)

        row = _terminal_row(connection)
        evidence = json.loads(row[3])
        diagnostics = json.loads(row[5])
        assert row[:3] == (expected_state, expected_disposition, None)
        assert evidence["terminal_state"] != "NOT_STARTED"
        assert evidence["snapshot_id"] is None
        assert evidence["artifact_sha256"] is None
        assert evidence["artifact_identity_sha256"] is None
        assert evidence["staging_cleanup"] == "COMPLETE"
        assert evidence["artifact_verification"] == "NOT_ATTEMPTED"
        assert diagnostics["reason"] == (
            "POST_FENCE_CHILD_FAILURE"
            if expected_state == "FAILED"
            else "POST_RESUME_OUTCOME_AMBIGUOUS"
        )
        assert row[4] == hashlib.sha256(row[3]).digest()
        assert row[6] == hashlib.sha256(row[5]).digest()
        assert api.events.count("delete_staging") == 1
        assert api.events.count("close:105") == 1
        assert not any(event.startswith("read_artifact") for event in api.events)
        assert "publish" not in api.events
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    ("failure_mode", "expected_cleanup"),
    [("identity", "IDENTITY_MISMATCH"), ("delete", "FAILED")],
)
def test_c3_d2_staging_cleanup_failure_is_sanitized_without_remapping(
    failure_mode: str, expected_cleanup: str
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        _persist_c3_terminal_observation(api, adapter, transactional, resumed)
        if failure_mode == "identity":
            api.file_identity = NativeFileIdentity(42, b"q" * 16)
        else:
            api.fail_cleanup = True
        transactional.record_c3_terminal(resumed.execution_id, resumed.reservation_id)

        row = _terminal_row(connection)
        evidence = json.loads(row[3])
        assert row[:3] == ("FAILED", "CONFIRMED", None)
        assert evidence["staging_cleanup"] == expected_cleanup
        assert "RuntimeError" not in row[3].decode("utf-8")
        assert _STORAGE_ROOT not in row[3].decode("utf-8")
        if failure_mode == "identity":
            assert "delete_staging" not in api.events
        else:
            assert api.events.count("delete_staging") == 1
        assert api.events.count("close:105") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d2_non_success_rollback_reuses_issuance_and_cleanup_observation() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        _persist_c3_terminal_observation(api, adapter, transactional, resumed)
        lineage = _c3_lineage(connection)
        authorization = adapter.prepare_c3_terminal(lineage, None)
        for operation in (copy, deepcopy, pickle.dumps):
            with pytest.raises(TypeError):
                operation(authorization)
        connection.execute(
            """
            CREATE TRIGGER fail_c3_terminal_non_success
            BEFORE INSERT ON terminals
            BEGIN
                SELECT RAISE(ABORT, 'injected C3 non-success rollback');
            END
            """
        )
        with pytest.raises(Exception, match="injected C3 non-success rollback"):
            transactional.record_c3_terminal(
                resumed.execution_id, resumed.reservation_id
            )
        assert api.events.count("delete_staging") == 1
        assert api.events.count("close:105") == 1

        connection.execute("DROP TRIGGER fail_c3_terminal_non_success")
        transactional.record_c3_terminal(resumed.execution_id, resumed.reservation_id)
        assert api.events.count("delete_staging") == 1
        assert api.events.count("close:105") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d2_parent_verification_failure_maps_to_confirmed_failure() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        api.fail_publish = True
        with pytest.raises(WindowsEffectfulCaptureCompositionError):
            transactional.verify_c3_captured_snapshot(
                resumed.execution_id, resumed.reservation_id
            )
        transactional.record_c3_terminal(resumed.execution_id, resumed.reservation_id)

        row = _terminal_row(connection)
        evidence = json.loads(row[3])
        diagnostics = json.loads(row[5])
        assert row[:3] == ("FAILED", "CONFIRMED", None)
        assert evidence["child_result_classification"] == "SUCCEEDED"
        assert evidence["artifact_verification"] == "PUBLICATION_FAILED"
        assert diagnostics["reason"] == "PARENT_ARTIFACT_VERIFICATION_FAILED"
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d2_successful_child_requires_d1_before_terminal() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    payload = _canonical_c3_snapshot(api)
    try:
        _persist_successful_c3_observation(
            api, adapter, transactional, resumed, payload
        )
        with pytest.raises(
            WindowsEffectfulCaptureCompositionError,
            match="requires D1 verification first",
        ):
            transactional.record_c3_terminal(
                resumed.execution_id, resumed.reservation_id
            )
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
        assert "delete_staging" not in api.events
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    "tamper",
    [
        "digest",
        "raw_field",
        "diagnostic_raw",
        "durable_mismatch",
        "non_http_status",
    ],
)
def test_c3_d2_c2_rejects_tampered_terminal_material_without_consuming(
    monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        _persist_c3_terminal_observation(api, adapter, transactional, resumed)
        adapter_type = type(adapter)
        original = adapter_type.validate_c3_terminal

        def tampered_validate(self, authorization, lineage):
            material = list(original(self, authorization, lineage))
            if tamper == "digest":
                material[4] = b"x" * 32
            elif tamper == "diagnostic_raw":
                diagnostics = json.loads(material[5])
                diagnostics["raw_error"] = "native provider failure"
                material[5] = json.dumps(
                    diagnostics,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                material[6] = hashlib.sha256(material[5]).digest()
            else:
                evidence = json.loads(material[3])
                if tamper == "raw_field":
                    evidence["raw_error"] = _STORAGE_ROOT + r"\secret-provider-body"
                elif tamper == "non_http_status":
                    evidence["http_status"] = 403
                    evidence["provider_request_id"] = "not-permitted"
                else:
                    evidence["process_outcome"] = "TIMED_OUT_TERMINATED"
                material[3] = json.dumps(
                    evidence,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                material[4] = hashlib.sha256(material[3]).digest()
            return tuple(material)

        monkeypatch.setattr(adapter_type, "validate_c3_terminal", tampered_validate)
        with pytest.raises(
            ValueError,
            match="digest|schema|durable cleanup|non-HTTP",
        ):
            transactional.record_c3_terminal(
                resumed.execution_id, resumed.reservation_id
            )
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)

        monkeypatch.setattr(adapter_type, "validate_c3_terminal", original)
        transactional.record_c3_terminal(resumed.execution_id, resumed.reservation_id)
        assert api.events.count("delete_staging") == 1
        assert api.events.count("close:105") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d2_recovery_first_revokes_delayed_terminal_authority() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        _persist_c3_terminal_observation(api, adapter, transactional, resumed)
        session_id, attempt_id = connection.execute(
            "SELECT session_id, attempt_id FROM attempts"
        ).fetchone()
        operator = b'{"evidence":"c3-d2-recovery-first","schema":1}'
        transactional.record_recovery(
            session_id,
            "ATTEMPT",
            attempt_id,
            "RECORD_ATTEMPT_AMBIGUITY",
            operator_evidence_json=operator,
            operator_evidence_digest=hashlib.sha256(operator).digest(),
        )
        with pytest.raises(ValueError, match="unavailable"):
            transactional.record_c3_terminal(
                resumed.execution_id, resumed.reservation_id
            )
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
        assert "delete_staging" not in api.events
    finally:
        _close(adapter, transactional)
        capture._closed = True


def _record_c3_success_terminal(
    api: _FakeNativeApi, adapter, transactional, resumed
) -> tuple[bytes, str]:
    payload = _canonical_c3_snapshot(api)
    _persist_successful_c3_observation(api, adapter, transactional, resumed, payload)
    capability = transactional.verify_c3_captured_snapshot(
        resumed.execution_id, resumed.reservation_id
    )
    terminal_id = transactional.record_c3_terminal(
        resumed.execution_id, resumed.reservation_id, capability
    )
    return payload, terminal_id


def test_c3_d3_complete_deterministic_success_selects_exact_terminal() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        payload, terminal_id = _record_c3_success_terminal(
            api, adapter, transactional, resumed
        )
        session_id, attempt_id, claim_id, reservation_id, execution_id = _c3_lineage(
            connection
        )
        terminal = connection.execute(
            "SELECT terminal_state, provider_call_disposition, snapshot_digest "
            "FROM terminals WHERE terminal_id = ?",
            (terminal_id,),
        ).fetchone()
        events_after_terminal = tuple(api.events)
        assert terminal == (
            "SUCCEEDED",
            "CONFIRMED",
            hashlib.sha256(payload).digest(),
        )
        assert api.final_bytes == payload
        assert c3_c2_registry_snapshot_for_test(adapter) == ()

        with pytest.raises(
            sqlite3.IntegrityError, match="session is not open|does not belong"
        ):
            transactional.select_terminal(
                "11111111-1111-4111-8111-111111111111", terminal_id
            )
        with pytest.raises(ValueError, match="unavailable"):
            transactional.select_c3_terminal("22222222-2222-4222-8222-222222222222")

        selection_id = transactional.select_c3_terminal(terminal_id)

        selection = connection.execute(
            "SELECT selection_id, session_id, terminal_id, snapshot_digest "
            "FROM session_selections"
        ).fetchone()
        assert selection == (
            selection_id,
            session_id,
            terminal_id,
            terminal[2],
        )
        assert terminal[2] == hashlib.sha256(payload).digest()
        assert connection.execute(
            "SELECT state FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone() == ("SUCCESS_SELECTED",)
        assert connection.execute(
            "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone() == ("SUCCESS_SELECTED",)
        assert connection.execute(
            "SELECT state FROM provider_call_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone() == ("COMMITTED",)
        assert connection.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("TERMINAL_RECORDED",)
        assert connection.execute(
            "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == ("TERMINAL_RECORDED",)
        assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (1,)
        assert tuple(api.events) == events_after_terminal
        assert api.events.count("create_process") == 1
        assert api.events.count("resume_thread") == 1
        assert api.events.count("publish") == 1
        assert api.events.count("delete_staging") == 1

        with pytest.raises(ValueError, match="unavailable"):
            transactional.select_c3_terminal(terminal_id)
        assert tuple(api.events) == events_after_terminal
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d3_selection_rollback_is_atomic_and_retry_has_no_effects() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        payload, terminal_id = _record_c3_success_terminal(
            api, adapter, transactional, resumed
        )
        session_id, attempt_id, _claim_id, _reservation_id, _execution_id = _c3_lineage(
            connection
        )
        events_after_terminal = tuple(api.events)
        connection.execute(
            """
            CREATE TRIGGER fail_c3_selection_projection
            BEFORE UPDATE OF state ON sessions
            WHEN NEW.state = 'SUCCESS_SELECTED'
            BEGIN
                SELECT RAISE(ABORT, 'injected C3 selection rollback');
            END
            """
        )

        with pytest.raises(
            sqlite3.IntegrityError, match="injected C3 selection rollback"
        ):
            transactional.select_c3_terminal(terminal_id)

        assert connection.execute(
            "SELECT terminal_state, provider_call_disposition, snapshot_digest "
            "FROM terminals WHERE terminal_id = ?",
            (terminal_id,),
        ).fetchone() == (
            "SUCCEEDED",
            "CONFIRMED",
            hashlib.sha256(payload).digest(),
        )
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT state FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone() == ("OPEN",)
        assert connection.execute(
            "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone() == ("TERMINAL_RECORDED",)
        assert tuple(api.events) == events_after_terminal
        assert c3_c2_registry_snapshot_for_test(adapter) == ()

        connection.execute("DROP TRIGGER fail_c3_selection_projection")
        transactional.select_c3_terminal(terminal_id)
        assert connection.execute(
            "SELECT snapshot_digest FROM session_selections"
        ).fetchone() == (hashlib.sha256(payload).digest(),)
        assert tuple(api.events) == events_after_terminal
        assert api.events.count("create_process") == 1
        assert api.events.count("resume_thread") == 1
        assert api.events.count("publish") == 1
    finally:
        _close(adapter, transactional)
        capture._closed = True


def test_c3_d3_select_committed_success_recovery_remains_compatible() -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        payload, terminal_id = _record_c3_success_terminal(
            api, adapter, transactional, resumed
        )
        session_id = connection.execute("SELECT session_id FROM sessions").fetchone()[0]
        events_after_terminal = tuple(api.events)
        operator = b'{"evidence":"c3-d3-select-recovery","schema":1}'

        recovery_id = transactional.record_recovery(
            session_id,
            "TERMINAL",
            terminal_id,
            "SELECT_COMMITTED_SUCCESS",
            operator_evidence_json=operator,
            operator_evidence_digest=hashlib.sha256(operator).digest(),
        )

        assert recovery_id
        assert connection.execute(
            "SELECT terminal_id, snapshot_digest FROM session_selections"
        ).fetchone() == (terminal_id, hashlib.sha256(payload).digest())
        assert connection.execute("SELECT state FROM sessions").fetchone() == (
            "SUCCESS_SELECTED",
        )
        assert tuple(api.events) == events_after_terminal
        assert c3_c2_registry_snapshot_for_test(adapter) == ()
    finally:
        _close(adapter, transactional)
        capture._closed = True


@pytest.mark.parametrize(
    ("result_changes", "trusted_result", "expected_state"),
    [({}, True, "FAILED"), ({}, False, "AMBIGUOUS")],
)
def test_c3_d3_non_success_terminal_is_not_selectable(
    result_changes: dict[str, object], trusted_result: bool, expected_state: str
) -> None:
    api = _FakeNativeApi()
    capture, adapter, transactional, connection, resumed = _resume_case(api)
    try:
        _persist_c3_terminal_observation(
            api,
            adapter,
            transactional,
            resumed,
            result_changes=result_changes,
            trusted_result=trusted_result,
        )
        terminal_id = transactional.record_c3_terminal(
            resumed.execution_id, resumed.reservation_id
        )
        session_id = connection.execute("SELECT session_id FROM sessions").fetchone()[0]
        events_after_terminal = tuple(api.events)

        with pytest.raises(ValueError, match="unavailable"):
            transactional.select_c3_terminal(terminal_id)
        with pytest.raises(ValueError, match="has no snapshot"):
            transactional.select_terminal(session_id, terminal_id)

        assert connection.execute(
            "SELECT terminal_state, snapshot_digest FROM terminals"
        ).fetchone() == (expected_state, None)
        assert connection.execute(
            "SELECT count(*) FROM session_selections"
        ).fetchone() == (0,)
        assert connection.execute("SELECT state FROM sessions").fetchone() == ("OPEN",)
        assert tuple(api.events) == events_after_terminal
    finally:
        _close(adapter, transactional)
        capture._closed = True
