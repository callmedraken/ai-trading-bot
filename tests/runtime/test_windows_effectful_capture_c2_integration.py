from __future__ import annotations

import hashlib
import json
import pickle
from collections import deque
from contextlib import nullcontext
from copy import copy, deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from inspect import signature

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
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
    NativeOverlappedCompletion,
    NativePipePair,
    WindowsEffectfulCaptureNativeError,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    MAX_C3_CHILD_REQUEST_BYTES,
    MAX_C3_CHILD_RESULT_BYTES,
    ChildCleanupStatus,
    ChildResultClassification,
    IsolatedCaptureChildResult,
    ProviderAttemptFenceState,
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
    ProcessIntent,
    WindowsTransactionalAuthority,
    open_disposable_authority_database_for_test,
)

_APPLICATION = r"F:\AITradingBot\runtime\python.exe"
_CURRENT = r"F:\AITradingBot\runtime"
_TEMP = r"F:\AITradingBot\temp"
_STAGING = r"F:\AITradingBot\Authority\capture-output\.c3-c2.staging"
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
    ) -> None:
        self.resume_result = resume_result
        self.fail_write = fail_write
        self.fail_close = fail_close
        self.fail_terminate = fail_terminate
        self.request_wait_status = request_wait_status
        self.events: list[str] = []
        self.written = bytearray()
        self.connection = None
        self._pipe_count = 0
        self.result_chunks: deque[bytes | None] = deque()
        self.wait_events: deque[C3NativeWaitStatus] = deque()
        self.process_wait_events: deque[C3NativeWaitStatus] = deque()
        self.exit_code = 0
        self.cancel_settles = True

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

    def create_staging_file(self, path: str) -> int:
        assert path == _STAGING
        self.events.append("create_staging")
        return 105

    def create_suspended_process(self, **kwargs: object) -> NativeCreatedProcess:
        assert kwargs["application_name"] == _APPLICATION
        assert kwargs["current_directory"] == _CURRENT
        self.events.append("create_process")
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


def _case(api: _FakeNativeApi):
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
        staging_path=_STAGING,
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
    capture._transactional = transactional
    api.connection = connection

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
            "parent_cleanup": observation.parent_cleanup.value,
            "process_outcome": observation.process_outcome.value,
            "provider_call_disposition": expected_disposition,
            "reservation_id": resumed.reservation_id,
            "result_transport": observation.result_transport.value,
            "schema": 1,
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
        transactional.record_recovery(
            session_id,
            "SESSION",
            session_id,
            "CLOSE_SESSION",
            operator_evidence_json=operator_json,
            operator_evidence_digest=hashlib.sha256(operator_json).digest(),
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
