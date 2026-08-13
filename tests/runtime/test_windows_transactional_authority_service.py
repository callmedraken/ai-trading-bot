from __future__ import annotations

import pickle
import sqlite3
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
    ProviderConstructionPermit,
    WindowsTransactionalAuthority,
    commit_process_intent,
    consume_constructed_provider_for_test,
    consume_process_result_for_test,
    consume_resume_result_for_test,
    issue_constructed_provider_for_test,
    issue_process_creation_failure_for_test,
    issue_process_creation_receipt_for_test,
    issue_resume_receipt_for_test,
    open_disposable_authority_database_for_test,
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
    connection = database.connection
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
            service.invoke_for_test(commit_process_intent, "reservation", object())
        assert arbiter_calls == []
    finally:
        connection.rollback()
        connection.close()


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
        match="production authority tree",
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
        assert (
            service.invoke_for_test(
                lambda connection: connection.execute("SELECT 1").fetchone()[0]
            )
            == 1
        )
    finally:
        service.close()


def test_file_backed_test_database_requires_reviewed_opener_and_sqlite_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = open_disposable_authority_database_for_test("authority.sqlite3")
    service = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
            "machine", "epoch", reservation_id
        ),
    )
    try:
        sqlite_identity = tuple(
            tuple(row) for row in database.connection.execute("PRAGMA database_list")
        )
        assert database.database_identity == sqlite_identity
        assert database.database_identity[0][2] == str(
            (tmp_path / "authority.sqlite3").resolve()
        )
        assert database.database_identity[0][2] != "authority.sqlite3"
        assert (
            service.invoke_for_test(
                lambda connection: connection.execute("SELECT 1").fetchone()[0]
            )
            == 1
        )
    finally:
        service.close()

    raw_connection = sqlite3.connect(
        tmp_path / "authority.sqlite3", isolation_level=None
    )
    try:
        with pytest.raises(TypeError, match="reviewed disposable database"):
            WindowsTransactionalAuthority.for_test(  # type: ignore[arg-type]
                database=raw_connection,
                lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
                    "machine", "epoch", reservation_id
                ),
            )
    finally:
        raw_connection.close()


def test_attached_disposable_database_is_rejected_before_callback_or_mutation() -> None:
    database = open_disposable_authority_database_for_test(":memory:")
    connection = database.connection
    connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
    service = WindowsTransactionalAuthority.for_test(
        database=database,
        lifecycle_arbiter_factory=lambda reservation_id: GlobalLifecycleMutex(
            "machine", "epoch", reservation_id
        ),
    )
    callback_calls: list[str] = []

    def would_mutate(connection: sqlite3.Connection) -> None:
        callback_calls.append("called")
        connection.execute("INSERT INTO marker(value) VALUES ('unexpected')")

    try:
        connection.execute("ATTACH DATABASE ':memory:' AS attached")
        with pytest.raises(
            ExternalAuthorityBoundaryUnavailable,
            match="exactly one main database",
        ):
            service.invoke_for_test(would_mutate)
        assert callback_calls == []
        assert connection.execute("SELECT COUNT(*) FROM marker").fetchone() == (0,)
    finally:
        service.close()


def test_disposable_database_wrapper_cannot_be_reconstructed_or_serialized() -> None:
    database = open_disposable_authority_database_for_test(":memory:")
    try:
        with pytest.raises(TypeError, match="reviewed opener"):
            DisposableAuthorityDatabaseForTest(  # type: ignore[call-arg]
                object(), database.connection, database.database_identity
            )
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(database)
    finally:
        database.connection.close()


def test_test_factory_has_no_production_authority_or_raw_connection_argument() -> None:
    parameters = signature(WindowsTransactionalAuthority.for_test).parameters
    assert "authority" not in parameters
    assert "connection" not in parameters
    assert "database" in parameters


def test_production_instance_rejects_invoke_for_test_before_opening_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WindowsTransactionalAuthority(_production_validation(monkeypatch))
    open_calls: list[tuple[object, ...]] = []
    callback_calls: list[str] = []
    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.open_writable_authority_sqlite_connection",
        lambda *args, **kwargs: open_calls.append((args, kwargs)),
    )

    def arbitrary_callback(connection: sqlite3.Connection) -> None:
        del connection
        callback_calls.append("called")

    with pytest.raises(
        ExternalAuthorityBoundaryUnavailable,
        match="only on for_test services",
    ):
        service.invoke_for_test(arbitrary_callback)
    assert open_calls == []
    assert callback_calls == []


def test_production_rejects_test_external_effect_provenance_before_database_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WindowsTransactionalAuthority(_production_validation(monkeypatch))
    open_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        "trading_bot.runtime.windows_transactional_authority.open_writable_authority_sqlite_connection",
        lambda *args, **kwargs: open_calls.append((args, kwargs)),
    )
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
        consume_constructed_provider_for_test(provider, "reservation")
        consume_process_result_for_test(process_receipt, "reservation")
        consume_process_result_for_test(process_failure, "reservation")
        consume_resume_result_for_test(resume_receipt, "execution", "reservation")


def test_production_lifecycle_factory_uses_reviewed_global_mutex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _production_validation(monkeypatch)
    calls: list[tuple[object, ...]] = []
    database = open_disposable_authority_database_for_test(":memory:")
    connection = database.connection

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
    execute_schema_artifact(connection)
    service = WindowsTransactionalAuthority(authority)
    provider = issue_constructed_provider_for_test("durable-reservation")
    try:
        with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="provenance"):
            service.commit_process_intent("durable-reservation", provider)
        consume_constructed_provider_for_test(provider, "durable-reservation")

        with pytest.raises(ValueError, match="unknown recovery session"):
            service.record_recovery(
                "unknown-session",
                "LAUNCH_RESERVATION",
                "durable-reservation",
                "CLASSIFY_LAUNCH_RESERVATION",
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
            consume_constructed_provider_for_test(provider, "durable-reservation")
        except ValueError:
            pass
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
