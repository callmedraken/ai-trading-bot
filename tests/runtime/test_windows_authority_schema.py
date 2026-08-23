from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from importlib import resources
from pathlib import Path

import pytest

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityBootstrap,
)
from trading_bot.runtime.windows_authority_initialization import (
    AuthorityInitializationError,
    initialize_authority_database_for_test,
)
from trading_bot.runtime.windows_authority_schema import (
    INITIALIZATION_POLICY_VERSION,
    INITIALIZER_CONTRACT_VERSION,
    MIGRATION_POLICY_VERSION,
    PERSISTED_EVIDENCE_PAIR_INVENTORY,
    PRODUCTION_SCHEMA_ARTIFACT_BYTES,
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_MANIFEST_BYTES,
    RELEASE_MANIFEST_ID,
    SQLITE_BUILD_MANIFEST_ID,
    AuthorityMetadataV1,
    AuthoritySchemaError,
    InitializationBlockedError,
    MetadataValidationError,
    PersistedEvidencePair,
    SchemaMigrationV1,
    SchemaValidationError,
    SqliteAuthorityBuildEvidence,
    authority_metadata_from_bootstrap,
    canonical_schema_manifest,
    configure_trusted_schema_off,
    create_schema_migration_v1,
    execute_schema_artifact,
    load_approved_release_manifest,
    load_approved_sqlite_authority_build,
    parse_authority_metadata_bytes,
    parse_release_manifest_bytes,
    parse_sqlite_authority_build_manifest,
    validate_persisted_evidence_digests,
    validate_production_authority_database_for_test,
)
from trading_bot.runtime.windows_authority_sqlite import (
    open_read_only_sqlite_connection,
    validate_installed_sqlite_prerequisites,
)


def _bootstrap() -> WindowsAuthorityBootstrap:
    return WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=3,
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


def _release_manifest() -> object:
    payload = {
        "application_version": "0.1.0",
        "initializer_contract_version": INITIALIZER_CONTRACT_VERSION,
        "manifest_id": RELEASE_MANIFEST_ID,
        "production_schema_digest": PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        "production_schema_id": PRODUCTION_SCHEMA_ID,
    }
    return parse_release_manifest_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )


def _available_vfs_name() -> str:
    candidates = ("win32", "unix") if os.name == "nt" else ("unix", "win32")
    for vfs in candidates:
        try:
            connection = sqlite3.connect(
                f"file:authority-vfs-probe?mode=memory&vfs={vfs}", uri=True
            )
        except sqlite3.OperationalError:
            continue
        else:
            connection.close()
            return vfs
    raise AssertionError("no supported platform SQLite VFS was available")


def _sqlite_build() -> SqliteAuthorityBuildEvidence:
    connection = sqlite3.connect(":memory:")
    try:
        source_id = connection.execute("SELECT sqlite_source_id()").fetchone()[0]
        compile_options = sorted(
            row[0] for row in connection.execute("PRAGMA compile_options")
        )
    finally:
        connection.close()
    payload = {
        "compile_options": compile_options,
        "manifest_id": SQLITE_BUILD_MANIFEST_ID,
        "sqlite_source_id": source_id,
        "sqlite_version": sqlite3.sqlite_version,
        "trusted_schema_off": True,
        "vfs": _available_vfs_name(),
    }
    return parse_sqlite_authority_build_manifest(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )


def _precreated_pair(tmp_path: Path) -> tuple[Path, Path]:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "authority.sqlite3-journal"
    sqlite3.connect(database).close()
    journal.touch()
    return database, journal


def _harness_helpers() -> object:
    """Import lifecycle-only test helpers without making them production API."""

    from tests.runtime import test_windows_transactional_capture_authority as harness

    return harness


def _initialized_authority(
    tmp_path: Path,
) -> tuple[Path, Path, WindowsAuthorityBootstrap, object, SqliteAuthorityBuildEvidence]:
    database, journal = _precreated_pair(tmp_path)
    bootstrap = _bootstrap()
    release = _release_manifest()
    build = _sqlite_build()
    initialize_authority_database_for_test(
        database_path=database,
        journal_path=journal,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        release_manifest=release,  # type: ignore[arg-type]
        sqlite_build=build,
        now_utc="2026-01-01T00:00:00Z",
    )
    return database, journal, bootstrap, release, build


def _populated_authority(
    tmp_path: Path,
) -> tuple[Path, Path, WindowsAuthorityBootstrap, object, SqliteAuthorityBuildEvidence]:
    database, journal, bootstrap, release, build = _initialized_authority(tmp_path)
    harness = _harness_helpers()
    test_harness = harness.Architecture77HarnessAuthority.open_from_descriptor(
        harness.Architecture77HarnessDescriptor(
            root=str(tmp_path), database_path=str(database)
        )
    )
    try:
        with harness._bind_harness(test_harness):
            ids = harness._seed_lifecycle(database)
            connection = harness._connect(database)
            try:
                harness._insert_recovery_fact_for_test(
                    connection,
                    ids["session_id"],
                    "TERMINAL",
                    ids["terminal_id"],
                    "SELECT_COMMITTED_SUCCESS",
                    operator_evidence_json=harness.TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=harness.TEST_OPERATOR_EVIDENCE_DIGEST,
                    created_at_utc=harness.SELECTION_TIMESTAMP,
                )
            finally:
                connection.close()
            connection = harness._connect(database)
            try:
                harness.select_terminal(
                    connection, ids["session_id"], ids["terminal_id"]
                )
            finally:
                connection.close()
    finally:
        test_harness.close()
    journal.touch()
    return database, journal, bootstrap, release, build


def _failure_authority(
    tmp_path: Path,
) -> tuple[Path, Path, WindowsAuthorityBootstrap, object, SqliteAuthorityBuildEvidence]:
    database, journal, bootstrap, release, build = _initialized_authority(tmp_path)
    harness = _harness_helpers()
    test_harness = harness.Architecture77HarnessAuthority.open_from_descriptor(
        harness.Architecture77HarnessDescriptor(
            root=str(tmp_path), database_path=str(database)
        )
    )
    try:
        with harness._bind_harness(test_harness):
            connection = harness._connect(database)
            try:
                session_id = harness.create_session(connection)
                attempt_id = harness.allocate_attempt(connection, session_id)
                claim_id = harness.commit_claim(connection, attempt_id)
                reservation = harness.reserve_launch(connection, claim_id)
                harness._record_definitive_process_failure(connection, reservation)
            finally:
                connection.close()
    finally:
        test_harness.close()
    journal.touch()
    return database, journal, bootstrap, release, build


def _validate_populated(
    database: Path,
    bootstrap: WindowsAuthorityBootstrap,
    release: object,
    build: SqliteAuthorityBuildEvidence,
) -> None:
    connection = open_read_only_sqlite_connection(database, vfs=build.vfs)
    try:
        validate_production_authority_database_for_test(
            connection,
            database_path=database,
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap.digest,
            release_manifest=release,  # type: ignore[arg-type]
            sqlite_build=build,
        )
    finally:
        connection.close()


def _corrupt_evidence_pair(
    database: Path,
    table: str,
    evidence_column: str,
    digest_column: str,
    *,
    field: str = "evidence",
) -> None:
    """Use direct test SQL, then restore the exact trigger rows."""

    connection = sqlite3.connect(database)
    trigger_rows = connection.execute(
        "SELECT type, name, tbl_name, rootpage, sql "
        "FROM sqlite_schema WHERE type = 'trigger' AND tbl_name = ?",
        (table,),
    ).fetchall()
    connection.execute("PRAGMA writable_schema = ON")
    connection.executemany(
        "DELETE FROM sqlite_schema WHERE type = 'trigger' AND name = ?",
        [(row[1],) for row in trigger_rows],
    )
    connection.commit()
    connection.close()
    try:
        connection = sqlite3.connect(database)
        row = connection.execute(
            f'SELECT rowid, "{evidence_column}" FROM "{table}" LIMIT 1'
        ).fetchone()
        if row is None:
            raise AssertionError(f"{table} has no row for evidence corruption")
        if field == "evidence":
            connection.execute(
                f'UPDATE "{table}" SET "{evidence_column}" = ? WHERE rowid = ?',
                (row[1] + b"corruption", row[0]),
            )
        elif field == "digest":
            connection.execute(
                f'UPDATE "{table}" SET "{digest_column}" = ? WHERE rowid = ?',
                (b"0" * 32, row[0]),
            )
        elif field == "null-evidence":
            connection.execute(
                f'UPDATE "{table}" SET "{evidence_column}" = NULL WHERE rowid = ?',
                (row[0],),
            )
        elif field == "null-digest":
            connection.execute(
                f'UPDATE "{table}" SET "{digest_column}" = NULL WHERE rowid = ?',
                (row[0],),
            )
        else:
            raise AssertionError(f"unknown corruption field: {field}")
        connection.commit()
        connection.close()
        Path(f"{database}-journal").touch()
    finally:
        connection = sqlite3.connect(database)
        connection.execute("PRAGMA writable_schema = ON")
        connection.executemany(
            "INSERT INTO sqlite_schema(type, name, tbl_name, rootpage, sql) "
            "VALUES (?, ?, ?, ?, ?)",
            trigger_rows,
        )
        connection.commit()
        connection.close()
        Path(f"{database}-journal").touch()


def test_production_inventory_is_explicit_and_complete() -> None:
    pairs = {
        (pair.table, pair.evidence_column, pair.digest_column)
        for pair in PERSISTED_EVIDENCE_PAIR_INVENTORY
    }
    assert len(PERSISTED_EVIDENCE_PAIR_INVENTORY) == 21
    assert len(pairs) == 21
    assert {table for table, _, _ in pairs} == {
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


def test_production_validator_accepts_complete_populated_evidence(
    tmp_path: Path,
) -> None:
    # This fixture exercises non-null evidence in every lifecycle category and
    # exact (NULL, NULL) states in the optional append-only columns.
    database, _, bootstrap, release, build = _populated_authority(tmp_path)
    _validate_populated(database, bootstrap, release, build)


def test_production_validator_accepts_builtin_temp_after_installed_prerequisites(
    tmp_path: Path,
) -> None:
    database, journal, bootstrap, release, build = _initialized_authority(tmp_path)
    connection = open_read_only_sqlite_connection(database, vfs=build.vfs)
    try:
        installed = validate_installed_sqlite_prerequisites(
            connection, database_path=database, journal_path=journal
        )
        assert installed.database_state.value == "INITIALIZED_SUPPORTED"
        assert installed.attached_database_count == 1
        connection.execute("CREATE TEMP TABLE temp_probe(value TEXT NOT NULL)")
        assert {row[1] for row in connection.execute("PRAGMA database_list")} == {
            "main",
            "temp",
        }
        validated = validate_production_authority_database_for_test(
            connection,
            database_path=database,
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap.digest,
            release_manifest=release,  # type: ignore[arg-type]
            sqlite_build=build,
        )
        assert validated.schema_id == PRODUCTION_SCHEMA_ID
    finally:
        connection.close()


def test_production_validator_rejects_extra_attach_with_builtin_temp(
    tmp_path: Path,
) -> None:
    database, _, bootstrap, release, build = _initialized_authority(tmp_path)
    connection = open_read_only_sqlite_connection(database, vfs=build.vfs)
    try:
        connection.execute("CREATE TEMP TABLE temp_probe(value TEXT NOT NULL)")
        connection.execute("ATTACH DATABASE ':memory:' AS extra")
        with pytest.raises(SchemaValidationError, match="attachment"):
            validate_production_authority_database_for_test(
                connection,
                database_path=database,
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap.digest,
                release_manifest=release,  # type: ignore[arg-type]
                sqlite_build=build,
            )
    finally:
        connection.close()


def test_production_validator_rejects_wrong_main_database_path(
    tmp_path: Path,
) -> None:
    database, _, bootstrap, release, build = _initialized_authority(tmp_path)
    expected_database = tmp_path / "different.sqlite3"
    sqlite3.connect(expected_database).close()
    Path(f"{expected_database}-journal").touch()
    connection = open_read_only_sqlite_connection(database, vfs=build.vfs)
    try:
        with pytest.raises(SchemaValidationError, match="fixed target"):
            validate_production_authority_database_for_test(
                connection,
                database_path=expected_database,
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap.digest,
                release_manifest=release,  # type: ignore[arg-type]
                sqlite_build=build,
            )
    finally:
        connection.close()


_SUCCESS_POPULATED_PERSISTED_PAIRS = tuple(
    pair
    for pair in PERSISTED_EVIDENCE_PAIR_INVENTORY
    if not (
        pair.table == "launch_reservations"
        and pair.evidence_column == "process_creation_failure_json"
    )
)


@pytest.mark.parametrize(
    "pair",
    _SUCCESS_POPULATED_PERSISTED_PAIRS,
    ids=lambda pair: f"{pair.table}.{pair.evidence_column}",
)
def test_production_validator_rejects_corruption_in_every_nonnull_pair(
    tmp_path: Path, pair: PersistedEvidencePair
) -> None:
    database, _, bootstrap, release, build = _populated_authority(tmp_path)
    _corrupt_evidence_pair(
        database,
        pair.table,
        pair.evidence_column,
        pair.digest_column,
    )
    connection = open_read_only_sqlite_connection(database, vfs=build.vfs)
    try:
        with pytest.raises(AuthoritySchemaError):
            validate_production_authority_database_for_test(
                connection,
                database_path=database,
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap.digest,
                release_manifest=release,  # type: ignore[arg-type]
                sqlite_build=build,
            )
    finally:
        connection.close()


def test_production_validator_rejects_changed_session_digest(
    tmp_path: Path,
) -> None:
    database, _, bootstrap, release, build = _populated_authority(tmp_path)
    _corrupt_evidence_pair(
        database, "sessions", "request_json", "request_digest", field="digest"
    )
    connection = open_read_only_sqlite_connection(database, vfs=build.vfs)
    try:
        with pytest.raises(AuthoritySchemaError):
            validate_production_authority_database_for_test(
                connection,
                database_path=database,
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap.digest,
                release_manifest=release,  # type: ignore[arg-type]
                sqlite_build=build,
            )
    finally:
        connection.close()


def test_production_validator_rejects_optional_failure_pair_corruption(
    tmp_path: Path,
) -> None:
    database, _, bootstrap, release, build = _failure_authority(tmp_path)
    _corrupt_evidence_pair(
        database,
        "launch_reservations",
        "process_creation_failure_json",
        "process_creation_failure_digest",
    )
    connection = open_read_only_sqlite_connection(database, vfs=build.vfs)
    try:
        with pytest.raises(AuthoritySchemaError):
            validate_production_authority_database_for_test(
                connection,
                database_path=database,
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap.digest,
                release_manifest=release,  # type: ignore[arg-type]
                sqlite_build=build,
            )
    finally:
        connection.close()


@pytest.mark.parametrize("field", ("null-evidence", "null-digest"))
def test_production_validator_rejects_one_sided_nullable_pair(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    import trading_bot.runtime.windows_authority_schema as schema

    monkeypatch.setattr(
        schema,
        "PERSISTED_EVIDENCE_PAIR_INVENTORY",
        (
            schema.PersistedEvidencePair(
                "nullable_test",
                "evidence_bytes",
                "evidence_digest",
                True,
                "test",
            ),
        ),
    )
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE nullable_test(evidence_bytes BLOB, evidence_digest BLOB)"
        )
        connection.execute(
            "INSERT INTO nullable_test VALUES (?, ?)",
            (b"bytes", hashlib.sha256(b"bytes").digest()),
        )
        column = "evidence_bytes" if field == "null-evidence" else "evidence_digest"
        connection.execute(f"UPDATE nullable_test SET {column} = NULL")
        with pytest.raises(SchemaValidationError, match="one-sided NULL"):
            validate_persisted_evidence_digests(connection)
    finally:
        connection.close()


def test_persisted_sweep_rejects_malformed_digest_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_schema as schema

    monkeypatch.setattr(
        schema,
        "PERSISTED_EVIDENCE_PAIR_INVENTORY",
        (
            schema.PersistedEvidencePair(
                "evidence_test", "evidence_bytes", "evidence_digest", False, "test"
            ),
        ),
    )
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE evidence_test(evidence_bytes BLOB, evidence_digest BLOB)"
        )
        connection.execute(
            "INSERT INTO evidence_test VALUES (?, ?)", (b"bytes", b"short")
        )
        with pytest.raises(SchemaValidationError, match="32-byte digest"):
            validate_persisted_evidence_digests(connection)
    finally:
        connection.close()


def test_concurrent_initializers_recheck_state_under_exclusive_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import trading_bot.runtime.windows_authority_initialization as initialization

    database, journal = _precreated_pair(tmp_path)
    bootstrap = _bootstrap()
    release = _release_manifest()
    build = _sqlite_build()
    precheck_barrier = threading.Barrier(2, timeout=15)
    call_lock = threading.Lock()
    call_count = 0
    original = initialization.validate_schema_state

    def synchronized_precheck(connection: sqlite3.Connection) -> str:
        nonlocal call_count
        with call_lock:
            call_count += 1
            ordinal = call_count
        if ordinal <= 2:
            precheck_barrier.wait()
        return original(connection)

    monkeypatch.setattr(initialization, "validate_schema_state", synchronized_precheck)
    results: list[object] = []
    errors: list[BaseException] = []
    result_lock = threading.Lock()

    def worker() -> None:
        try:
            result = initialize_authority_database_for_test(
                database_path=database,
                journal_path=journal,
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap.digest,
                release_manifest=release,  # type: ignore[arg-type]
                sqlite_build=build,
                now_utc="2026-08-11T12:00:00Z",
                connection_factory=lambda path: sqlite3.connect(
                    path, timeout=15.0, isolation_level=None
                ),
            )
            with result_lock:
                results.append(result)
        except BaseException as error:
            with result_lock:
                errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(results) == 2
    assert results[0] == results[1]
    connection = sqlite3.connect(database)
    try:
        assert connection.execute(
            "SELECT count(*) FROM authority_metadata"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM schema_migrations"
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_initializer_rejects_database_changed_before_under_lock_recheck(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import trading_bot.runtime.windows_authority_initialization as initialization

    database, journal = _precreated_pair(tmp_path)
    bootstrap = _bootstrap()
    release = _release_manifest()
    build = _sqlite_build()
    precheck_ready = threading.Event()
    competitor_done = threading.Event()
    first_call = True
    original = initialization.validate_schema_state

    def delayed_precheck(connection: sqlite3.Connection) -> str:
        nonlocal first_call
        if first_call:
            first_call = False
            state = original(connection)
            precheck_ready.set()
            if not competitor_done.wait(15):
                raise TimeoutError("competitor did not change database")
            return state
        return original(connection)

    monkeypatch.setattr(initialization, "validate_schema_state", delayed_precheck)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            initialize_authority_database_for_test(
                database_path=database,
                journal_path=journal,
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap.digest,
                release_manifest=release,  # type: ignore[arg-type]
                sqlite_build=build,
                now_utc="2026-08-11T12:00:00Z",
                connection_factory=lambda path: sqlite3.connect(
                    path, timeout=15.0, isolation_level=None
                ),
            )
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    assert precheck_ready.wait(15)
    competitor = sqlite3.connect(database, timeout=15.0)
    try:
        competitor.execute("CREATE TABLE competing_object(value TEXT NOT NULL)")
        competitor.commit()
    finally:
        competitor.close()
        competitor_done.set()
    thread.join(30)
    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], AuthorityInitializationError)
    connection = sqlite3.connect(database)
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name"
        ).fetchall() == [("competing_object",)]
    finally:
        connection.close()


def test_packaged_artifact_has_stable_identity_and_no_sql_udf() -> None:
    assert len(PRODUCTION_SCHEMA_ARTIFACT_BYTES) == 118_896
    assert not PRODUCTION_SCHEMA_ARTIFACT_BYTES.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in PRODUCTION_SCHEMA_ARTIFACT_BYTES
    assert hashlib.sha256(PRODUCTION_SCHEMA_ARTIFACT_BYTES).hexdigest() == (
        PRODUCTION_SCHEMA_ARTIFACT_SHA256
    )
    assert b"sha256(" not in PRODUCTION_SCHEMA_ARTIFACT_BYTES.lower()
    assert PRODUCTION_SCHEMA_ID.endswith("/v1")
    assert PRODUCTION_SCHEMA_MANIFEST_BYTES


def test_approved_manifest_resources_are_exact_and_loadable() -> None:
    package = resources.files("trading_bot.runtime.schema")
    release_bytes = package.joinpath(
        "authority_initializer_release_manifest_v1.json"
    ).read_bytes()
    sqlite_build_bytes = package.joinpath(
        "sqlite_authority_build_manifest_v1.json"
    ).read_bytes()

    assert len(release_bytes) == 308
    assert hashlib.sha256(release_bytes).hexdigest() == (
        "6c5293d5b04f8f752d26c5cea10e1d146bbb6a65aacbfe729704fdef2278eb3f"
    )
    assert not release_bytes.startswith(b"\xef\xbb\xbf")
    assert not release_bytes.endswith(b"\n")
    release = load_approved_release_manifest()
    assert release.manifest_bytes == release_bytes
    assert release.application_version == "0.1.0"

    assert len(sqlite_build_bytes) == 1220
    assert hashlib.sha256(sqlite_build_bytes).hexdigest() == (
        "58cbd4cf228131a8c1894700760c95f4f76aa006c8b64ff29215bc92d8691dd3"
    )
    assert not sqlite_build_bytes.startswith(b"\xef\xbb\xbf")
    assert not sqlite_build_bytes.endswith(b"\n")
    sqlite_build = load_approved_sqlite_authority_build()
    assert sqlite_build.manifest_bytes == sqlite_build_bytes
    assert sqlite_build.sqlite_version == "3.50.4"
    assert sqlite_build.sqlite_source_id == (
        "2025-07-30 19:33:53 "
        "4d8adfb30e03f9cf27f800a2c1ba3c48fb4ca1b08b0f5ed59a4d5ecbf45e20a3"
    )
    assert sqlite_build.vfs == "win32"
    assert sqlite_build.trusted_schema_off is True
    assert len(sqlite_build.compile_options) == 43


def test_approved_manifest_resource_read_failures_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_schema as schema

    def inaccessible(_package: str) -> object:
        raise OSError("resource access denied")

    monkeypatch.setattr(schema.resources, "files", inaccessible)
    with pytest.raises(
        InitializationBlockedError,
        match="approved release manifest resource is unavailable",
    ):
        load_approved_release_manifest()
    with pytest.raises(
        InitializationBlockedError,
        match="approved SQLite build manifest resource is unavailable",
    ):
        load_approved_sqlite_authority_build()


def test_approved_manifest_resource_malformed_data_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_schema as schema

    class MalformedResource:
        def joinpath(self, _name: str) -> MalformedResource:
            return self

        def read_bytes(self) -> bytes:
            return b"{}"

    monkeypatch.setattr(schema.resources, "files", lambda _package: MalformedResource())
    with pytest.raises(InitializationBlockedError, match="field set is not exact"):
        load_approved_release_manifest()
    with pytest.raises(InitializationBlockedError, match="field set is not exact"):
        load_approved_sqlite_authority_build()


def test_release_manifest_binds_the_pinned_artifact_digest() -> None:
    payload = {
        "application_version": "0.1.0",
        "initializer_contract_version": INITIALIZER_CONTRACT_VERSION,
        "manifest_id": RELEASE_MANIFEST_ID,
        "production_schema_digest": "0" * 64,
        "production_schema_id": PRODUCTION_SCHEMA_ID,
    }
    with pytest.raises(InitializationBlockedError, match="digest does not match"):
        parse_release_manifest_bytes(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )


def test_artifact_materializes_exact_manifest_with_trusted_schema_off() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        execute_schema_artifact(connection)
        assert connection.execute("PRAGMA trusted_schema").fetchone()[0] == 0
        assert canonical_schema_manifest(connection) == PRODUCTION_SCHEMA_MANIFEST_BYTES
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema WHERE sql LIKE '%sha256(%'"
            ).fetchone()[0]
            == 0
        )
    finally:
        connection.close()


def test_trusted_schema_setup_is_read_back_and_rejects_bad_connection() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        configure_trusted_schema_off(connection)
        assert connection.execute("PRAGMA trusted_schema").fetchone()[0] == 0
    finally:
        connection.close()
    with pytest.raises(MetadataValidationError):
        parse_authority_metadata_bytes(b'{"authority_epoch_id":"x"}')


def test_metadata_is_exact_canonical_json_and_digest() -> None:
    bootstrap = _bootstrap()
    metadata = authority_metadata_from_bootstrap(
        bootstrap,
        bootstrap_digest=bootstrap.digest,
        created_at_utc="2026-08-11T12:00:00Z",
    )
    assert isinstance(metadata, AuthorityMetadataV1)
    assert parse_authority_metadata_bytes(metadata.canonical_bytes()) == metadata
    assert metadata.digest == hashlib.sha256(metadata.canonical_bytes()).digest()
    duplicate = metadata.canonical_bytes()[:-1] + b',"singleton_key":1}'
    with pytest.raises(MetadataValidationError):
        parse_authority_metadata_bytes(duplicate)


def test_migration_is_deterministic_and_immutable_model() -> None:
    migration = create_schema_migration_v1(
        _bootstrap().authority_epoch_id,
        release_manifest=_release_manifest(),  # type: ignore[arg-type]
        applied_at_utc="2026-08-11T12:00:00Z",
    )
    assert isinstance(migration, SchemaMigrationV1)
    assert migration.migration_policy_version == MIGRATION_POLICY_VERSION
    assert INITIALIZATION_POLICY_VERSION in migration.migration_json.decode()
    assert (
        migration.migration_id
        == create_schema_migration_v1(
            _bootstrap().authority_epoch_id,
            release_manifest=_release_manifest(),  # type: ignore[arg-type]
            applied_at_utc="2026-08-11T13:00:00Z",
        ).migration_id
    )


def test_disposable_initializer_commits_and_read_only_validation_succeeds(
    tmp_path: Path,
) -> None:
    database, journal = _precreated_pair(tmp_path)
    bootstrap = _bootstrap()
    release = _release_manifest()
    build = _sqlite_build()
    evidence = initialize_authority_database_for_test(
        database_path=database,
        journal_path=journal,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        release_manifest=release,  # type: ignore[arg-type]
        sqlite_build=build,
        now_utc="2026-08-11T12:00:00Z",
    )
    assert evidence.state.value == "INITIALIZED_SUPPORTED"
    repeated = initialize_authority_database_for_test(
        database_path=database,
        journal_path=journal,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        release_manifest=release,  # type: ignore[arg-type]
        sqlite_build=build,
        now_utc="2026-08-11T13:00:00Z",
    )
    assert repeated == evidence
    connection = sqlite3.connect(database)
    try:
        assert (
            connection.execute("SELECT count(*) FROM authority_metadata").fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
            == 1
        )
    finally:
        connection.close()
    read_only = open_read_only_sqlite_connection(database, vfs=build.vfs)
    try:
        validated = validate_production_authority_database_for_test(
            read_only,
            database_path=database,
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap.digest,
            release_manifest=release,  # type: ignore[arg-type]
            sqlite_build=build,
        )
        assert validated.schema_id == PRODUCTION_SCHEMA_ID
    finally:
        read_only.close()


def test_initializer_rolls_back_schema_when_statement_execution_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import trading_bot.runtime.windows_authority_initialization as initialization

    database, journal = _precreated_pair(tmp_path)

    def fail_after_ddl(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE partial_schema(value TEXT)")
        raise sqlite3.OperationalError("injected failure")

    monkeypatch.setattr(initialization, "execute_schema_artifact", fail_after_ddl)
    with pytest.raises(initialization.AuthorityInitializationError):
        initialize_authority_database_for_test(
            database_path=database,
            journal_path=journal,
            bootstrap=_bootstrap(),
            bootstrap_digest=_bootstrap().digest,
            release_manifest=_release_manifest(),  # type: ignore[arg-type]
            sqlite_build=_sqlite_build(),
            now_utc="2026-08-11T12:00:00Z",
        )
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
    finally:
        connection.close()


def test_initializer_rejects_active_transaction_before_schema_ddl(
    tmp_path: Path,
) -> None:
    database, journal = _precreated_pair(tmp_path)

    def active_connection(path: str) -> sqlite3.Connection:
        connection = sqlite3.connect(path)
        connection.execute("BEGIN")
        return connection

    with pytest.raises(AuthorityInitializationError):
        initialize_authority_database_for_test(
            database_path=database,
            journal_path=journal,
            bootstrap=_bootstrap(),
            bootstrap_digest=_bootstrap().digest,
            release_manifest=_release_manifest(),  # type: ignore[arg-type]
            sqlite_build=_sqlite_build(),
            now_utc="2026-08-11T12:00:00Z",
            connection_factory=active_connection,
        )
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
    finally:
        connection.close()
