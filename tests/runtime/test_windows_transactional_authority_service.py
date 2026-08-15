from __future__ import annotations

import hashlib
import pickle
import sqlite3
import threading
from inspect import signature

import pytest

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    BootstrapVerification,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_mutex import GlobalLifecycleMutex
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    ProductionAuthorityEvidence,
    execute_schema_artifact,
)
from trading_bot.runtime.windows_authority_sqlite import SqliteDatabaseState
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    InstalledDatabaseValidation,
    ProvisioningEvidence,
    ProvisioningState,
    ValidatedProductionAuthority,
    acquire_validated_production_authority,
    acquire_validated_production_authority_for_test,
)
from trading_bot.runtime.windows_transactional_authority import (
    ConstructedProvider,
    DisposableAuthorityDatabaseForTest,
    ExternalAuthorityBoundaryUnavailable,
    ProcessCreationReceipt,
    ProcessIntent,
    ProviderConstructionPermit,
    ResumeIntent,
    ResumeReceipt,
    TransactionalAuthorityCore,
    WindowsTransactionalAuthority,
    consume_constructed_provider_for_test,
    consume_process_intent_for_test,
    consume_process_result_for_test,
    consume_provider_construction_permit_for_test,
    consume_resume_intent_for_test,
    consume_resume_result_for_test,
    issue_constructed_provider_for_test,
    issue_process_creation_failure_for_test,
    issue_process_creation_receipt_for_test,
    issue_resume_receipt_for_test,
    open_disposable_authority_database_for_test,
    process_success_evidence_for_test,
    snapshot_capture_request_for_test,
)


def _bootstrap() -> WindowsAuthorityBootstrap:
    return WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=7,
        machine_authority_id="11111111-1111-4111-8111-111111111111",
        authority_epoch_id="22222222-2222-4222-8222-222222222222",
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


def _production_evidence() -> ProductionAuthorityEvidence:
    return ProductionAuthorityEvidence(
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="33" * 32,
        migration_id="migration-v1",
        release_manifest_digest="11" * 32,
        sqlite_build_manifest_digest="22" * 32,
    )


def _validation() -> InstalledAuthorityValidation:
    bootstrap = _bootstrap()
    return InstalledAuthorityValidation(
        provisioning=ProvisioningEvidence(
            state=ProvisioningState.VALIDATED,
            authority_root=str(PRODUCTION_AUTHORITY_PATHS.root),
            bootstrap_digest=bootstrap.digest,
            signing_key_id=bootstrap.signing_key_id,
            trading_sid=bootstrap.approved_account_sid,
            inspected_objects=("root", "bootstrap", "signature"),
            database_present=True,
            journal_present=True,
            database_state=SqliteDatabaseState.INITIALIZED_SUPPORTED.value,
        ),
        bootstrap_verification=BootstrapVerification(
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap.digest,
            signing_key_id=bootstrap.signing_key_id,
            signature_length=64,
        ),
        production_evidence=_production_evidence(),
    )


def _production_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> ValidatedProductionAuthority:
    import trading_bot.runtime.windows_authority_validation as validation

    bootstrap = _bootstrap()
    evidence = _production_evidence()
    verification = BootstrapVerification(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        signing_key_id=bootstrap.signing_key_id,
        signature_length=64,
    )
    monkeypatch.setattr(validation, "resolve_current_token_sid", lambda: "S-1-5-21-1")
    monkeypatch.setattr(
        validation, "require_trading_standard_account", lambda: "S-1-5-21-1"
    )
    monkeypatch.setattr(validation, "is_current_token_elevated", lambda: False)
    monkeypatch.setattr(validation, "is_current_token_administrator", lambda: False)
    monkeypatch.setattr(
        validation,
        "validate_lifecycle_mutex_security_descriptor",
        lambda sid: None,
    )
    monkeypatch.setattr(
        validation, "verify_bootstrap_signature", lambda *args, **kwargs: verification
    )

    class Handle:
        def __init__(self, path: str) -> None:
            self.path = path

        def __enter__(self) -> Handle:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        validation,
        "open_authority_object",
        lambda path, kind: Handle(str(path)),
    )
    monkeypatch.setattr(
        validation,
        "inspect_open_authority_object",
        lambda handle, path, kind: object(),
    )
    monkeypatch.setattr(validation, "require_security_policy", lambda *args: None)
    monkeypatch.setattr(
        validation, "read_open_authority_file", lambda handle: b"material"
    )
    monkeypatch.setattr(validation.os.path, "lexists", lambda path: True)
    monkeypatch.setattr(
        validation,
        "validate_installed_database_complete",
        lambda *args, **kwargs: InstalledDatabaseValidation(
            SqliteDatabaseState.INITIALIZED_SUPPORTED, evidence
        ),
    )
    return acquire_validated_production_authority()


def _test_authority() -> ValidatedProductionAuthority:
    bootstrap = _bootstrap()
    return acquire_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=_production_evidence(),
    )


def _test_consumer_core() -> tuple[
    WindowsTransactionalAuthority, TransactionalAuthorityCore
]:
    database = open_disposable_authority_database_for_test(":memory:")
    service = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
            "machine", "epoch", reservation_id
        ),
    )
    return service, service._core_for_operation()


def _initialize_test_service_database(
    database: DisposableAuthorityDatabaseForTest,
) -> sqlite3.Connection:
    connection = database._connection
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
            "S-1-5-21-test",
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
    return connection


def _test_capture_request() -> dict[str, object]:
    return {
        "bar_interval": "1d",
        "child_operation_version": "child/v1",
        "ordered_universe": ["AAPL", "MSFT"],
        "output_policy_version": "output/v1",
        "permitted_provider_operation": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        "provider_id": ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        "request_limit": 2,
        "request_window_end_date": "2025-12-31",
        "request_window_start_date": "2025-01-01",
        "target_session_date": "2026-01-01",
    }


class _CountingExternalAdapter:
    def __init__(
        self,
        *,
        fail_operation: str | None = None,
        dispatch_started: threading.Event | None = None,
        dispatch_release: threading.Event | None = None,
    ) -> None:
        self.fail_operation = fail_operation
        self.dispatch_started = dispatch_started
        self.dispatch_release = dispatch_release
        self.calls = {"provider": 0, "process": 0, "resume": 0}
        self.results: list[object] = []
        self.connection: sqlite3.Connection | None = None
        self.transaction_states: list[bool] = []

    def reset(self) -> None:
        self.calls = {"provider": 0, "process": 0, "resume": 0}
        self.results.clear()
        self.transaction_states.clear()

    def _dispatch_started(self, operation: str) -> None:
        self.calls[operation] += 1
        if self.connection is not None:
            self.transaction_states.append(self.connection.in_transaction)
        if self.dispatch_started is not None:
            self.dispatch_started.set()
        if self.dispatch_release is not None:
            assert self.dispatch_release.wait(10)
        if self.fail_operation == operation:
            raise RuntimeError(f"{operation} adapter failed")

    def construct_provider(
        self, capability: ProviderConstructionPermit, *, fail: bool = False
    ) -> ConstructedProvider:
        self._dispatch_started("provider")
        if fail:
            raise RuntimeError("provider adapter failed")
        result = issue_constructed_provider_for_test(capability.reservation_id)
        self.results.append(result)
        return result

    def create_process(
        self, process_intent: ProcessIntent, *, fail: bool = False
    ) -> ProcessCreationReceipt:
        self._dispatch_started("process")
        if fail:
            raise RuntimeError("process adapter failed")
        process_json, job_json, resume_json = process_success_evidence_for_test(
            process_intent.reservation_id, process_intent.intent_digest
        )
        result = issue_process_creation_receipt_for_test(
            process_intent.reservation_id,
            process_intent.intent_digest,
            process_json,
            hashlib.sha256(process_json).digest(),
            job_json,
            hashlib.sha256(job_json).digest(),
            resume_json,
            hashlib.sha256(resume_json).digest(),
        )
        self.results.append(result)
        return result

    def resume_thread(
        self, resume_intent: ResumeIntent, *, fail: bool = False
    ) -> ResumeReceipt:
        self._dispatch_started("resume")
        if fail:
            raise RuntimeError("resume adapter failed")
        result_json = b'{"resume":"ok"}'
        result = issue_resume_receipt_for_test(
            resume_intent.execution_id,
            resume_intent.reservation_id,
            resume_intent.intent_digest,
            result_json,
            hashlib.sha256(result_json).digest(),
        )
        self.results.append(result)
        return result


class _TestLifecycleArbiter:
    def __enter__(self) -> _TestLifecycleArbiter:
        return self

    def __exit__(self, *args: object) -> None:
        del args


class _SerializedTestLifecycleArbiter:
    def __init__(self, lock: threading.Lock) -> None:
        self._lock = lock

    def __enter__(self) -> _SerializedTestLifecycleArbiter:
        self._lock.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        del args
        self._lock.release()


def _service_with_adapter(
    adapter: _CountingExternalAdapter,
    *,
    lifecycle_arbiter_factory: object | None = None,
) -> tuple[WindowsTransactionalAuthority, sqlite3.Connection]:
    database = open_disposable_authority_database_for_test(":memory:")
    connection = _initialize_test_service_database(database)
    if lifecycle_arbiter_factory is None:

        def lifecycle_arbiter_factory(reservation_id: str) -> _TestLifecycleArbiter:
            del reservation_id
            return _TestLifecycleArbiter()

    service = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=lifecycle_arbiter_factory,  # type: ignore[arg-type]
        external_adapter=adapter,
    )
    adapter.connection = connection
    return service, connection


def _prepare_external_case(
    service: WindowsTransactionalAuthority,
    adapter: _CountingExternalAdapter,
    operation: str,
) -> tuple[str, object, str, str]:
    session_id = service.create_session(_test_capture_request())
    attempt_id = service.allocate_attempt(session_id)
    claim_id = service.commit_claim(attempt_id)
    permit = service.reserve_launch(claim_id)
    reservation_id = str(permit)
    if operation == "provider":
        return session_id, permit, reservation_id, "COMMITTED"

    provider = service.construct_provider(permit)
    process_intent = service.commit_process_intent(reservation_id, provider)
    if operation == "process":
        adapter.reset()
        return session_id, process_intent, reservation_id, "PROCESS_INTENT_COMMITTED"

    process_result = service.create_process(process_intent)
    execution_id = service.record_execution(reservation_id, process_result)
    resume_intent = service.commit_resume_intent(execution_id, reservation_id)
    adapter.reset()
    return session_id, resume_intent, reservation_id, "PROCESS_CREATED"


def _prepare_external_input(
    service: WindowsTransactionalAuthority,
    adapter: _CountingExternalAdapter,
    operation: str,
) -> tuple[object, str, str]:
    _, capability, reservation_id, expected_state = _prepare_external_case(
        service, adapter, operation
    )
    return capability, reservation_id, expected_state


def _external_dispatch(
    service: WindowsTransactionalAuthority, operation: str, capability: object
) -> object:
    if operation == "provider":
        return service.construct_provider(capability)  # type: ignore[arg-type]
    if operation == "process":
        return service.create_process(capability)  # type: ignore[arg-type]
    if operation == "resume":
        return service.resume_thread(capability)  # type: ignore[arg-type]
    raise AssertionError(f"unsupported external operation: {operation}")


def _production_database_evidence(
    authority: ValidatedProductionAuthority,
    **overrides: object,
) -> ProductionAuthorityEvidence:
    values: dict[str, object] = {
        "database_path": authority.database_path,
        "schema_id": authority.schema_id,
        "schema_version": authority.schema_version,
        "schema_digest": authority.schema_digest,
        "metadata_digest": authority.metadata_digest,
        "migration_id": authority.migration_id,
        "release_manifest_digest": authority.release_manifest_digest,
        "sqlite_build_manifest_digest": authority.sqlite_build_manifest_digest,
    }
    values.update(overrides)
    return ProductionAuthorityEvidence(**values)  # type: ignore[arg-type]


def _patch_opened_connection_validation(
    monkeypatch: pytest.MonkeyPatch,
    authority: ValidatedProductionAuthority,
    observed: ProductionAuthorityEvidence,
) -> list[sqlite3.Connection]:
    import trading_bot.runtime.windows_authority_validation as validation

    seen: list[sqlite3.Connection] = []
    monkeypatch.setattr(
        validation,
        "load_approved_release_manifest",
        lambda: type(
            "ApprovedRelease",
            (),
            {"digest": bytes.fromhex(authority.release_manifest_digest)},
        )(),
    )
    monkeypatch.setattr(
        validation,
        "load_approved_sqlite_authority_build",
        lambda: type(
            "ApprovedBuild",
            (),
            {"digest": bytes.fromhex(authority.sqlite_build_manifest_digest)},
        )(),
    )

    def validate(
        connection: sqlite3.Connection, **kwargs: object
    ) -> ProductionAuthorityEvidence:
        seen.append(connection)
        assert kwargs["bootstrap_digest"] == authority.bootstrap_digest
        bootstrap = kwargs["bootstrap"]
        assert type(bootstrap) is WindowsAuthorityBootstrap
        assert bootstrap.machine_authority_id == authority.machine_authority_id
        assert bootstrap.authority_epoch_id == authority.authority_epoch_id
        assert bootstrap.database_identity_digest == authority.database_identity_digest
        return observed

    monkeypatch.setattr(
        validation, "validate_production_authority_database_connection", validate
    )
    return seen


def _patch_production_open(
    monkeypatch: pytest.MonkeyPatch,
    authority: ValidatedProductionAuthority,
    connection: sqlite3.Connection,
) -> None:
    import trading_bot.runtime.windows_transactional_authority as production

    monkeypatch.setattr(
        production,
        "_approved_sqlite_build_for_authority",
        lambda _: type(
            "ApprovedBuild",
            (),
            {
                "vfs": "test-vfs",
                "digest": bytes.fromhex(authority.sqlite_build_manifest_digest),
            },
        )(),
    )
    monkeypatch.setattr(
        production,
        "open_writable_authority_sqlite_connection",
        lambda *args, **kwargs: connection,
    )
    monkeypatch.setattr(
        production,
        "configure_and_validate_authority_sqlite_connection",
        lambda *args, **kwargs: None,
    )


def test_production_constructor_requires_genuine_capability() -> None:
    with pytest.raises(WindowsAuthorityError):
        WindowsTransactionalAuthority(_test_authority())

    with pytest.raises(WindowsAuthorityError):
        WindowsTransactionalAuthority(_validation())  # type: ignore[arg-type]


def test_genuine_capability_is_required_and_binds_the_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _production_validation(monkeypatch)
    service = WindowsTransactionalAuthority(authority)
    assert service.authority is authority
    assert service.database_path == authority.database_path
    service.close()


def test_open_revalidates_the_same_connection_before_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _production_validation(monkeypatch)
    connection = sqlite3.connect(":memory:")
    observed = _production_database_evidence(authority)
    seen = _patch_opened_connection_validation(monkeypatch, authority, observed)
    _patch_production_open(monkeypatch, authority, connection)
    service = WindowsTransactionalAuthority(authority)
    try:
        assert service._open_production_connection() is connection
        assert seen == [connection]
        assert service._connection is connection
    finally:
        service.close()


@pytest.mark.parametrize(
    "field",
    [
        "database_path",
        "schema_id",
        "schema_version",
        "schema_digest",
        "metadata_digest",
        "migration_id",
        "release_manifest_digest",
        "sqlite_build_manifest_digest",
    ],
)
def test_open_rejects_database_evidence_not_matching_authority(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    authority = _production_validation(monkeypatch)
    connection = sqlite3.connect(":memory:")
    mismatched = {
        "database_path": str(PRODUCTION_AUTHORITY_PATHS.root / "other.sqlite3"),
        "schema_id": "authority-schema/other",
        "schema_version": 2,
        "schema_digest": "00" * 32,
        "metadata_digest": "44" * 32,
        "migration_id": "migration-other",
        "release_manifest_digest": "55" * 32,
        "sqlite_build_manifest_digest": "66" * 32,
    }
    observed = _production_database_evidence(authority, **{field: mismatched[field]})
    _patch_opened_connection_validation(monkeypatch, authority, observed)
    _patch_production_open(monkeypatch, authority, connection)
    service = WindowsTransactionalAuthority(authority)

    with pytest.raises(WindowsAuthorityError, match="does not match"):
        service.create_session({})

    assert service._connection is None
    assert service._core is None
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    service.close()


def test_replacement_after_close_is_rejected_before_rebinding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_transactional_authority as production

    authority = _production_validation(monkeypatch)
    first = sqlite3.connect(":memory:")
    replacement = sqlite3.connect(":memory:")
    opened = [first, replacement]
    seen: list[sqlite3.Connection] = []
    monkeypatch.setattr(
        production,
        "_approved_sqlite_build_for_authority",
        lambda _: type(
            "ApprovedBuild",
            (),
            {
                "vfs": "test-vfs",
                "digest": bytes.fromhex(authority.sqlite_build_manifest_digest),
            },
        )(),
    )
    monkeypatch.setattr(
        production,
        "open_writable_authority_sqlite_connection",
        lambda *args, **kwargs: opened.pop(0),
    )
    monkeypatch.setattr(
        production,
        "configure_and_validate_authority_sqlite_connection",
        lambda *args, **kwargs: None,
    )

    def validate(
        expected: ValidatedProductionAuthority, connection: sqlite3.Connection
    ) -> None:
        assert expected is authority
        seen.append(connection)
        if connection is replacement:
            raise WindowsAuthorityError(
                "opened production connection does not match validated authority"
            )

    monkeypatch.setattr(
        production, "require_open_connection_matches_validated_authority", validate
    )
    service = WindowsTransactionalAuthority(authority)
    try:
        assert service._open_production_connection() is first
        service.close()
        with pytest.raises(WindowsAuthorityError, match="does not match"):
            service.create_session({})
        assert seen == [first, replacement]
        assert service._connection is None
        assert service._core is None
        with pytest.raises(sqlite3.ProgrammingError):
            replacement.execute("SELECT 1")
    finally:
        service.close()


def test_production_constructor_has_no_caller_path_or_connection_seam() -> None:
    parameters = signature(WindowsTransactionalAuthority).parameters
    assert tuple(parameters) == ("authority",)
    assert "database_path" not in parameters
    assert "connection" not in parameters
    assert "vfs" not in parameters


def test_public_capability_fields_cannot_reconstruct_authority() -> None:
    authority = _test_authority()
    fields = {
        field: getattr(authority, field)
        for field in authority.__slots__
        if field != "_provenance"
    }
    with pytest.raises(TypeError):
        ValidatedProductionAuthority(**fields)


def test_c2_external_effect_boundary_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WindowsTransactionalAuthority(_production_validation(monkeypatch))
    with pytest.raises(ExternalAuthorityBoundaryUnavailable):
        service.construct_provider(object())  # type: ignore[arg-type]
    with pytest.raises(ExternalAuthorityBoundaryUnavailable):
        service.create_process(object())  # type: ignore[arg-type]
    with pytest.raises(ExternalAuthorityBoundaryUnavailable):
        service.resume_thread(object())  # type: ignore[arg-type]


def test_test_factory_is_explicit_and_rejects_active_transaction_before_arbiter() -> (
    None
):
    database = open_disposable_authority_database_for_test(":memory:")
    connection = database._connection
    arbiter_calls: list[str] = []

    def arbiter(reservation_id: str):
        arbiter_calls.append(reservation_id)
        return GlobalLifecycleMutex("machine", "epoch", reservation_id)

    service = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=arbiter,
    )
    connection.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(ValueError, match="no active SQLite transaction"):
            service.create_session({})
        assert arbiter_calls == []
    finally:
        connection.rollback()
        connection.close()


def test_disposable_database_has_one_service_owner_and_preserves_first_owner() -> None:
    database = open_disposable_authority_database_for_test(":memory:")
    connection = _initialize_test_service_database(database)
    first_arbiter_calls: list[str] = []
    second_arbiter_calls: list[str] = []
    first = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=lambda reservation_id: (
            first_arbiter_calls.append(reservation_id)
            or GlobalLifecycleMutex("machine", "epoch", reservation_id)
        ),
    )
    before = connection.execute("SELECT count(*) FROM sessions").fetchone()
    try:
        with pytest.raises(
            ExternalAuthorityBoundaryUnavailable,
            match="already has a service owner",
        ):
            WindowsTransactionalAuthority.for_test(
                database=database,
                lifecycle_arbiter_factory=lambda reservation_id: (
                    second_arbiter_calls.append(reservation_id)
                    or GlobalLifecycleMutex("machine", "epoch", reservation_id)
                ),
            )
        assert second_arbiter_calls == []
        assert connection.execute("SELECT count(*) FROM sessions").fetchone() == before
        session_id = first.create_session(_test_capture_request())
        assert isinstance(session_id, str)
        assert first_arbiter_calls == []
        assert connection.execute("SELECT count(*) FROM sessions").fetchone() == (1,)
    finally:
        first.close()


def test_distinct_disposable_databases_have_independent_service_owners() -> None:
    first_database = open_disposable_authority_database_for_test(":memory:")
    second_database = open_disposable_authority_database_for_test(":memory:")
    first = WindowsTransactionalAuthority.for_test(
        database=first_database,
        lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
            "machine", "epoch", reservation_id
        ),
    )
    second = WindowsTransactionalAuthority.for_test(
        database=second_database,
        lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
            "machine", "epoch", reservation_id
        ),
    )
    try:
        assert first._connection is first_database._connection
        assert second._connection is second_database._connection
        assert first._connection is not second._connection
    finally:
        first.close()
        second.close()


def test_disposable_database_service_claim_is_atomic_under_concurrency() -> None:
    database = open_disposable_authority_database_for_test(":memory:")
    barrier = threading.Barrier(2)
    outcomes: list[tuple[str, object]] = []

    def claim() -> None:
        barrier.wait()
        try:
            service = WindowsTransactionalAuthority.for_test(
                database=database,
                lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
                    "machine", "epoch", reservation_id
                ),
            )
            outcomes.append(("success", service))
        except BaseException as error:
            outcomes.append(("failure", error))

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    successes = [value for kind, value in outcomes if kind == "success"]
    failures = [value for kind, value in outcomes if kind == "failure"]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], ExternalAuthorityBoundaryUnavailable)
    assert isinstance(successes[0], WindowsTransactionalAuthority)
    successes[0].close()


@pytest.mark.parametrize("operation", ["provider", "process", "resume"])
def test_service_consumes_external_input_before_duplicate_dispatch(
    operation: str,
) -> None:
    adapter = _CountingExternalAdapter()
    service, connection = _service_with_adapter(adapter)
    try:
        capability, reservation_id, expected_state = _prepare_external_input(
            service, adapter, operation
        )
        before = connection.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone()
        first_result = _external_dispatch(service, operation, capability)
        assert first_result is not None
        assert adapter.calls[operation] == 1
        assert len(adapter.results) == 1
        assert adapter.transaction_states == [False]

        with pytest.raises(ValueError, match="consumed"):
            _external_dispatch(service, operation, capability)
        assert adapter.calls[operation] == 1
        assert len(adapter.results) == 1
        assert (
            connection.execute(
                "SELECT reservation_state FROM launch_reservations "
                "WHERE launch_reservation_id = ?",
                (reservation_id,),
            ).fetchone()
            == before
            == (expected_state,)
        )
    finally:
        service.close()


@pytest.mark.parametrize("operation", ["provider", "process", "resume"])
def test_service_consumes_external_input_when_adapter_fails(
    operation: str,
) -> None:
    adapter = _CountingExternalAdapter(fail_operation=operation)
    service, connection = _service_with_adapter(adapter)
    try:
        capability, reservation_id, _ = _prepare_external_input(
            service, adapter, operation
        )
        before = connection.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone()
        with pytest.raises(RuntimeError, match="adapter failed"):
            _external_dispatch(service, operation, capability)
        assert adapter.calls[operation] == 1
        assert adapter.results == []
        assert adapter.transaction_states == [False]

        with pytest.raises(ValueError, match="consumed"):
            _external_dispatch(service, operation, capability)
        assert adapter.calls[operation] == 1
        assert (
            connection.execute(
                "SELECT reservation_state FROM launch_reservations "
                "WHERE launch_reservation_id = ?",
                (reservation_id,),
            ).fetchone()
            == before
        )
    finally:
        service.close()


@pytest.mark.parametrize("operation", ["provider", "process", "resume"])
def test_cross_service_external_input_provenance_fails_before_consumption(
    operation: str,
) -> None:
    first_adapter = _CountingExternalAdapter()
    second_adapter = _CountingExternalAdapter()
    first, first_connection = _service_with_adapter(first_adapter)
    second, _ = _service_with_adapter(second_adapter)
    try:
        capability, reservation_id, _ = _prepare_external_input(
            first, first_adapter, operation
        )
        with pytest.raises(TypeError, match="test service provenance"):
            _external_dispatch(second, operation, capability)
        assert second_adapter.calls[operation] == 0
        _external_dispatch(first, operation, capability)
        assert first_adapter.calls[operation] == 1
        assert (
            first_connection.execute(
                "SELECT reservation_state FROM launch_reservations "
                "WHERE launch_reservation_id = ?",
                (reservation_id,),
            ).fetchone()
            is not None
        )
    finally:
        first.close()
        second.close()


def test_concurrent_duplicate_external_dispatch_consumes_once() -> None:
    dispatch_started = threading.Event()
    dispatch_release = threading.Event()
    adapter = _CountingExternalAdapter(
        dispatch_started=dispatch_started,
        dispatch_release=dispatch_release,
    )
    service, connection = _service_with_adapter(adapter)
    try:
        capability, reservation_id, _ = _prepare_external_input(
            service, adapter, "provider"
        )
        outcomes: list[tuple[str, object]] = []
        start = threading.Barrier(2)

        def dispatch() -> None:
            start.wait()
            try:
                _external_dispatch(service, "provider", capability)
            except BaseException as error:
                outcomes.append(("failure", error))
            else:
                outcomes.append(("success", None))

        threads = [threading.Thread(target=dispatch) for _ in range(2)]
        for thread in threads:
            thread.start()
        assert dispatch_started.wait(10)
        dispatch_release.set()
        for thread in threads:
            thread.join(10)

        assert sorted(kind for kind, _ in outcomes) == ["failure", "success"]
        assert isinstance(outcomes[0][1], BaseException) or isinstance(
            outcomes[1][1], BaseException
        )
        assert adapter.calls["provider"] == 1
        assert len(adapter.results) == 1
        assert connection.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("COMMITTED",)
    finally:
        service.close()


_RECOVERY_ACTIONS = {
    "provider": "CLASSIFY_LAUNCH_RESERVATION",
    "process": "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
    "resume": "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
}
_RECOVERY_EVIDENCE = b'{"operator":"test"}'
_RECOVERY_EVIDENCE_DIGEST = hashlib.sha256(_RECOVERY_EVIDENCE).digest()


def _recover_reservation(
    service: WindowsTransactionalAuthority,
    session_id: str,
    reservation_id: str,
    operation: str,
) -> None:
    service.record_recovery(
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        _RECOVERY_ACTIONS[operation],
        operator_evidence_json=_RECOVERY_EVIDENCE,
        operator_evidence_digest=_RECOVERY_EVIDENCE_DIGEST,
    )


@pytest.mark.parametrize("operation", ["provider", "process", "resume"])
def test_recovery_wins_before_external_dispatch_rejects_stale_input(
    operation: str,
) -> None:
    adapter = _CountingExternalAdapter()
    service, connection = _service_with_adapter(adapter)
    try:
        session_id, capability, reservation_id, _ = _prepare_external_case(
            service, adapter, operation
        )
        _recover_reservation(service, session_id, reservation_id, operation)

        with pytest.raises(ValueError, match="active lineage|PROCESS|resume"):
            _external_dispatch(service, operation, capability)
        assert adapter.calls[operation] == 0
        assert not capability._permit.consumed  # type: ignore[attr-defined]
        assert connection.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("MANUAL_REVIEW",)
    finally:
        service.close()


@pytest.mark.parametrize("operation", ["provider", "process", "resume"])
def test_external_dispatch_holds_arbiter_against_recovery(
    operation: str,
) -> None:
    dispatch_started = threading.Event()
    dispatch_release = threading.Event()
    arbiter_lock = threading.Lock()
    adapter = _CountingExternalAdapter()
    service, connection = _service_with_adapter(
        adapter,
        lifecycle_arbiter_factory=lambda reservation_id: (
            _SerializedTestLifecycleArbiter(arbiter_lock)
        ),
    )
    try:
        session_id, capability, reservation_id, _ = _prepare_external_case(
            service, adapter, operation
        )
        adapter.dispatch_started = dispatch_started
        adapter.dispatch_release = dispatch_release
        effect_outcomes: list[object] = []
        recovery_outcomes: list[object] = []
        recovery_attempted = threading.Event()
        recovery_done = threading.Event()

        def run_effect() -> None:
            try:
                effect_outcomes.append(
                    _external_dispatch(service, operation, capability)
                )
            except BaseException as error:
                effect_outcomes.append(error)

        def run_recovery() -> None:
            recovery_attempted.set()
            try:
                _recover_reservation(service, session_id, reservation_id, operation)
            except BaseException as error:
                recovery_outcomes.append(error)
            else:
                recovery_outcomes.append("recovered")
            finally:
                recovery_done.set()

        effect_thread = threading.Thread(target=run_effect)
        effect_thread.start()
        assert dispatch_started.wait(10)
        recovery_thread = threading.Thread(target=run_recovery)
        recovery_thread.start()
        assert recovery_attempted.wait(10)
        assert not recovery_done.wait(0.1)
        dispatch_release.set()
        effect_thread.join(10)
        recovery_thread.join(10)

        assert len(effect_outcomes) == 1
        assert not isinstance(effect_outcomes[0], BaseException)
        assert recovery_outcomes == ["recovered"]
        assert adapter.calls[operation] == 1
        assert adapter.transaction_states == [False]
        assert capability._permit.consumed  # type: ignore[attr-defined]
        assert connection.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("MANUAL_REVIEW",)
    finally:
        dispatch_release.set()
        service.close()


@pytest.mark.parametrize("operation", ["process", "resume"])
def test_effect_result_persistence_after_recovery_is_conservative(
    operation: str,
) -> None:
    dispatch_started = threading.Event()
    dispatch_release = threading.Event()
    arbiter_lock = threading.Lock()
    adapter = _CountingExternalAdapter()
    service, connection = _service_with_adapter(
        adapter,
        lifecycle_arbiter_factory=lambda reservation_id: (
            _SerializedTestLifecycleArbiter(arbiter_lock)
        ),
    )
    try:
        session_id, capability, reservation_id, _ = _prepare_external_case(
            service, adapter, operation
        )
        adapter.dispatch_started = dispatch_started
        adapter.dispatch_release = dispatch_release
        effect_outcomes: list[object] = []

        def run_effect() -> None:
            effect_outcomes.append(_external_dispatch(service, operation, capability))

        effect_thread = threading.Thread(target=run_effect)
        effect_thread.start()
        assert dispatch_started.wait(10)
        dispatch_release.set()
        effect_thread.join(10)
        assert len(effect_outcomes) == 1
        result = effect_outcomes[0]

        _recover_reservation(service, session_id, reservation_id, operation)
        if operation == "process":
            with pytest.raises(ValueError, match="process creation|active lineage"):
                service.record_execution(reservation_id, result)  # type: ignore[arg-type]
        else:
            with pytest.raises(ValueError, match="resume"):
                service.record_post_resume_evidence(
                    capability.execution_id,
                    result,  # type: ignore[attr-defined,arg-type]
                )
        assert not result._permit.consumed  # type: ignore[attr-defined]
        assert adapter.calls[operation] == 1
        assert adapter.transaction_states == [False]
        assert connection.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == ("MANUAL_REVIEW",)
    finally:
        service.close()


def test_test_factory_rejects_raw_connection_before_callbacks() -> None:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    arbiter_calls: list[str] = []
    callback_calls: list[str] = []

    def arbiter(reservation_id: str):
        arbiter_calls.append(reservation_id)
        return GlobalLifecycleMutex("machine", "epoch", reservation_id)

    def capture_request(request: object):
        callback_calls.append("called")
        return snapshot_capture_request_for_test(request)

    try:
        with pytest.raises(TypeError, match="reviewed disposable database"):
            WindowsTransactionalAuthority.for_test(  # type: ignore[arg-type]
                database=connection,
                lifecycle_arbiter_factory=arbiter,
                capture_request_factory=capture_request,
            )
        assert arbiter_calls == []
        assert callback_calls == []
    finally:
        connection.close()


@pytest.mark.parametrize(
    "database_path",
    [
        str(PRODUCTION_AUTHORITY_PATHS.database),
        str(PRODUCTION_AUTHORITY_PATHS.root / "shadow.sqlite3"),
    ],
)
def test_disposable_opener_rejects_production_tree_before_sqlite_open(
    monkeypatch: pytest.MonkeyPatch,
    database_path: str,
) -> None:
    open_calls: list[tuple[object, ...]] = []

    def unexpected_open(*args: object, **kwargs: object) -> None:
        open_calls.append((args, kwargs))
        raise AssertionError("production path was opened")

    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.sqlite3.connect",
        unexpected_open,
    )
    with pytest.raises(
        ExternalAuthorityBoundaryUnavailable,
        match="anonymous in-memory SQLite",
    ):
        open_disposable_authority_database_for_test(database_path)
    assert open_calls == []


def test_anonymous_disposable_database_supports_the_test_service() -> None:
    database = open_disposable_authority_database_for_test(":memory:")
    service = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
            "machine", "epoch", reservation_id
        ),
    )
    try:
        assert database.database_identity == ((0, "main", ""),)
        assert hasattr(service, "create_session")
        assert not hasattr(service, "invoke_for_test")
    finally:
        service.close()


def test_file_backed_test_database_is_rejected_before_sqlite_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    file_path = tmp_path / "authority.sqlite3"
    open_calls: list[tuple[object, ...]] = []

    def unexpected_open(*args: object, **kwargs: object) -> None:
        open_calls.append((args, kwargs))
        raise AssertionError("file-backed disposable database was opened")

    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.sqlite3.connect",
        unexpected_open,
    )
    with pytest.raises(
        ExternalAuthorityBoundaryUnavailable,
        match="anonymous in-memory SQLite",
    ):
        open_disposable_authority_database_for_test(file_path)
    assert open_calls == []
    assert not file_path.exists()


def test_attached_disposable_database_is_rejected_before_callback_or_mutation() -> None:
    database = open_disposable_authority_database_for_test(":memory:")
    connection = database._connection
    connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
    service = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
            "machine", "epoch", reservation_id
        ),
    )
    try:
        connection.execute("ATTACH DATABASE ':memory:' AS attached")
        with pytest.raises(
            ExternalAuthorityBoundaryUnavailable,
            match="exactly one main database",
        ):
            service.create_session({})
        assert connection.execute("SELECT COUNT(*) FROM marker").fetchone() == (0,)
    finally:
        service.close()


def test_disposable_database_wrapper_cannot_be_reconstructed_or_serialized() -> None:
    database = open_disposable_authority_database_for_test(":memory:")
    try:
        with pytest.raises(TypeError, match="reviewed opener"):
            DisposableAuthorityDatabaseForTest(  # type: ignore[call-arg]
                object(), database._connection, database.database_identity
            )
        assert not hasattr(database, "connection")
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(database)
    finally:
        database.close()


def test_test_factory_has_no_production_authority_or_raw_connection_argument() -> None:
    parameters = signature(WindowsTransactionalAuthority.for_test).parameters
    assert "authority" not in parameters
    assert "connection" not in parameters
    assert "database" in parameters


def test_test_consumers_require_an_explicit_test_core() -> None:
    consumers = (
        consume_provider_construction_permit_for_test,
        consume_constructed_provider_for_test,
        consume_process_intent_for_test,
        consume_process_result_for_test,
        consume_resume_intent_for_test,
        consume_resume_result_for_test,
    )
    for consumer in consumers:
        parameter = signature(consumer).parameters["core"]
        assert parameter.kind is parameter.KEYWORD_ONLY
        assert parameter.default is parameter.empty


def test_production_module_has_no_raw_connection_mutator_surface() -> None:
    import trading_bot.runtime.windows_transactional_authority as production

    durable_names = (
        "create_session",
        "allocate_attempt",
        "commit_claim",
        "reserve_launch",
        "commit_process_intent",
        "record_execution",
        "commit_resume_intent",
        "record_process_creation_failure",
        "record_post_resume_evidence",
        "record_terminal",
        "select_terminal",
        "record_recovery",
    )
    assert all(not hasattr(production, name) for name in durable_names)
    assert not any(name.endswith("_locked_for_test") for name in vars(production))
    assert not hasattr(WindowsTransactionalAuthority, "invoke_for_test")
    assert not hasattr(WindowsTransactionalAuthority, "_invoke")


def test_production_instance_has_no_arbitrary_test_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WindowsTransactionalAuthority(_production_validation(monkeypatch))
    assert not hasattr(service, "invoke_for_test")


def test_production_connection_validation_failure_closes_local_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_transactional_authority as production

    authority = _production_validation(monkeypatch)
    connection = sqlite3.connect(":memory:")
    failure = RuntimeError("authority connection validation failed")
    monkeypatch.setattr(
        production,
        "_approved_sqlite_build_for_authority",
        lambda _: type("ApprovedBuild", (), {"vfs": "test-vfs"})(),
    )
    monkeypatch.setattr(
        production,
        "open_writable_authority_sqlite_connection",
        lambda *args, **kwargs: connection,
    )

    def fail_validation(*args: object, **kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(
        production,
        "configure_and_validate_authority_sqlite_connection",
        fail_validation,
    )
    service = WindowsTransactionalAuthority(authority)

    with pytest.raises(RuntimeError, match="authority connection validation failed"):
        service._open_production_connection()

    assert service._connection is None
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    service.close()


def test_production_rejects_test_external_effect_provenance_before_database_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WindowsTransactionalAuthority(_production_validation(monkeypatch))
    consumer_service, consumer_core = _test_consumer_core()
    open_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.open_writable_authority_sqlite_connection",
        lambda *args, **kwargs: open_calls.append((args, kwargs)),
    )
    with consumer_core.bind_external_effects():
        provider = issue_constructed_provider_for_test("reservation")
        process_receipt = issue_process_creation_receipt_for_test(
            "reservation",
            b"intent",
            b"process",
            b"process-digest",
            b"job",
            b"job-digest",
            b"resume",
            b"resume-digest",
        )
        process_failure = issue_process_creation_failure_for_test(
            "reservation",
            b"intent",
            b"failure",
            b"failure-digest",
        )
        resume_receipt = issue_resume_receipt_for_test(
            "execution",
            "reservation",
            b"resume-intent",
            b"resumed",
            b"resumed-digest",
        )
    try:
        with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="provenance"):
            service.commit_process_intent("reservation", provider)
        with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="provenance"):
            service.record_execution("reservation", process_receipt)
        with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="provenance"):
            service.record_process_creation_failure("reservation", process_failure)
        with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="provenance"):
            service.record_post_resume_evidence("execution", resume_receipt)
        assert open_calls == []
    finally:
        consume_constructed_provider_for_test(
            provider, "reservation", core=consumer_core
        )
        consume_process_result_for_test(
            process_receipt, "reservation", core=consumer_core
        )
        consume_process_result_for_test(
            process_failure, "reservation", core=consumer_core
        )
        consume_resume_result_for_test(
            resume_receipt, "execution", "reservation", core=consumer_core
        )
        consumer_service.close()
        service.close()


def test_production_lifecycle_factory_uses_reviewed_global_mutex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _production_validation(monkeypatch)
    calls: list[tuple[object, ...]] = []
    database = open_disposable_authority_database_for_test(":memory:")
    connection = database._connection

    class Probe:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls.append((*args, kwargs))

        def __enter__(self) -> Probe:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.GlobalLifecycleMutex",
        Probe,
    )
    monkeypatch.setattr(
        "trading_bot.runtime.windows_authority_schema.load_approved_sqlite_authority_build",
        lambda: type(
            "ApprovedBuild",
            (),
            {
                "vfs": "test-vfs",
                "digest": bytes.fromhex(authority.sqlite_build_manifest_digest),
            },
        )(),
    )
    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.open_writable_authority_sqlite_connection",
        lambda path, *, vfs: connection,
    )
    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.configure_and_validate_authority_sqlite_connection",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.require_open_connection_matches_validated_authority",
        lambda *args, **kwargs: None,
    )
    execute_schema_artifact(connection)
    service = WindowsTransactionalAuthority(authority)
    consumer_service, consumer_core = _test_consumer_core()
    with consumer_core.bind_external_effects():
        provider = issue_constructed_provider_for_test("durable-reservation")
    try:
        with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="provenance"):
            service.commit_process_intent("durable-reservation", provider)
        consume_constructed_provider_for_test(
            provider, "durable-reservation", core=consumer_core
        )

        with pytest.raises(ValueError, match="unknown recovery session"):
            service.record_recovery(
                "unknown-session",
                "LAUNCH_RESERVATION",
                "durable-reservation",
                "CLASSIFY_LAUNCH_RESERVATION",
                operator_evidence_json=b'{"operator":"test"}',
                operator_evidence_digest=hashlib.sha256(
                    b'{"operator":"test"}'
                ).digest(),
            )
        assert calls == [
            (
                authority.machine_authority_id,
                authority.authority_epoch_id,
                "durable-reservation",
                {"trading_sid": authority.approved_account_sid},
            )
        ]
    finally:
        try:
            consume_constructed_provider_for_test(
                provider, "durable-reservation", core=consumer_core
            )
        except ValueError:
            pass
        consumer_service.close()
        service.close()
        connection.close()


def test_transactional_capabilities_are_process_local_and_non_serializable() -> None:
    capability = issue_constructed_provider_for_test("reservation")
    assert isinstance(capability, ConstructedProvider)
    assert not isinstance(capability, ProviderConstructionPermit)
    with pytest.raises(TypeError, match="cannot be pickled"):
        pickle.dumps(capability)


def test_capture_request_vector_remains_exact() -> None:
    request = {
        "bar_interval": "1d",
        "child_operation_version": "child/v1",
        "ordered_universe": ["AAPL", "MSFT"],
        "output_policy_version": "output/v1",
        "permitted_provider_operation": "historical-stock-bars-v2-raw-usd-no-asof",
        "provider_id": "alpaca-market-data",
        "request_limit": 2,
        "request_window_end_date": "2025-12-31",
        "request_window_start_date": "2025-01-01",
        "target_session_date": "2026-01-01",
    }
    snapshot = snapshot_capture_request_for_test(request)
    assert snapshot.ordered_universe == ("AAPL", "MSFT")
    assert snapshot.canonical_json() == (
        b'{"bar_interval":"1d","child_operation_version":"child/v1",'
        b'"ordered_universe":["AAPL","MSFT"],"output_policy_version":'
        b'"output/v1","permitted_provider_operation":"historical-stock-bars-v2-raw-usd-no-asof",'
        b'"provider_id":"alpaca-market-data","request_limit":2,'
        b'"request_window_end_date":"2025-12-31","request_window_start_date":"2025-01-01",'
        b'"target_session_date":"2026-01-01"}'
    )
