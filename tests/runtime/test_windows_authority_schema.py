from __future__ import annotations

import hashlib
import json
import sqlite3
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
    PRODUCTION_SCHEMA_ARTIFACT_BYTES,
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_MANIFEST_BYTES,
    RELEASE_MANIFEST_ID,
    SQLITE_BUILD_MANIFEST_ID,
    AuthorityMetadataV1,
    MetadataValidationError,
    SchemaMigrationV1,
    SqliteAuthorityBuildEvidence,
    authority_metadata_from_bootstrap,
    canonical_schema_manifest,
    configure_trusted_schema_off,
    create_schema_migration_v1,
    execute_schema_artifact,
    parse_authority_metadata_bytes,
    parse_release_manifest_bytes,
    parse_sqlite_authority_build_manifest,
    validate_production_authority_database,
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
        "vfs": "test-vfs",
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


def test_packaged_artifact_has_stable_identity_and_no_sql_udf() -> None:
    assert not PRODUCTION_SCHEMA_ARTIFACT_BYTES.startswith(b"\xef\xbb\xbf")
    assert hashlib.sha256(PRODUCTION_SCHEMA_ARTIFACT_BYTES).hexdigest() == (
        PRODUCTION_SCHEMA_ARTIFACT_SHA256
    )
    assert b"sha256(" not in PRODUCTION_SCHEMA_ARTIFACT_BYTES.lower()
    assert PRODUCTION_SCHEMA_ID.endswith("/v1")
    assert PRODUCTION_SCHEMA_MANIFEST_BYTES


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
    read_only = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        validated = validate_production_authority_database(
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
