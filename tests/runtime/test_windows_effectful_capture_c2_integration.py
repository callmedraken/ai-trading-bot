from __future__ import annotations

import hashlib
import pickle
from contextlib import nullcontext
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
    NativeCreatedProcess,
    NativePipePair,
    WindowsEffectfulCaptureNativeError,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    MAX_C3_CHILD_REQUEST_BYTES,
    MAX_C3_CHILD_RESULT_BYTES,
    parse_isolated_capture_child_request,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    C3C2NativeLaunchConfigurationForTest,
    WindowsEffectfulCaptureCompositionError,
    WindowsEffectfulDailySnapshotCapture,
    c3_c2_registry_snapshot_for_test,
    create_c3_c2_transactional_adapter_for_test,
    execute_c3_c2_resume_for_test,
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
    ) -> None:
        self.resume_result = resume_result
        self.fail_write = fail_write
        self.events: list[str] = []
        self.written = bytearray()
        self.connection = None
        self._pipe_count = 0

    def create_job_object(self) -> int:
        self.events.append("create_job")
        return 100

    def set_job_limits(self, job_handle: int) -> None:
        assert job_handle == 100
        self.events.append("set_job_limits")

    def create_pipe(self, buffer_size: int) -> NativePipePair:
        self._pipe_count += 1
        self.events.append(f"create_pipe:{buffer_size}")
        if self._pipe_count == 1:
            return NativePipePair(101, 102)
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

    def write_file(self, handle: int, payload: bytes) -> int:
        assert handle == 102
        assert self.connection is not None
        phase = self.connection.execute(
            "SELECT phase FROM launch_executions"
        ).fetchone()
        assert phase == ("PRE_RESUME_READY",)
        self.events.append("write_request")
        if self.fail_write:
            raise RuntimeError("injected request failure")
        count = min(7, len(payload))
        self.written.extend(payload[:count])
        return count

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
            (result.reservation_id, result.execution_id, True),
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
