"""Explicit administrator-only transactional initialization of the v1 authority DB."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    UnsupportedWindowsPlatformError,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
    parse_bootstrap_bytes,
    verify_bootstrap_signature,
)
from trading_bot.runtime.windows_authority_provisioning import (
    ProvisioningEvidence,
    read_installed_authority_material,
    validate_installed_authority,
)
from trading_bot.runtime.windows_authority_schema import (
    AuthorityMetadataV1,
    AuthoritySchemaError,
    ProductionAuthorityEvidence,
    ReleaseManifestEvidence,
    SchemaMigrationV1,
    SchemaValidationError,
    SqliteAuthorityBuildEvidence,
    authority_metadata_from_bootstrap,
    create_schema_migration_v1,
    execute_schema_artifact,
    load_approved_release_manifest,
    load_approved_sqlite_authority_build,
    validate_production_authority_database,
    validate_production_authority_database_in_transaction,
    validate_schema_state,
)
from trading_bot.runtime.windows_authority_security import require_administrator_token
from trading_bot.runtime.windows_authority_sqlite import (
    SqliteDatabaseState,
    configure_and_validate_authority_sqlite_connection,
    open_writable_authority_sqlite_connection,
)


class AuthorityInitializationError(WindowsAuthorityError):
    """Raised when the one-time initialization boundary cannot be completed."""


@dataclass(frozen=True, slots=True)
class InitializationEvidence:
    """Sanitized evidence for one supported initialization or idempotent retry."""

    state: SqliteDatabaseState
    database_path: str
    schema_id: str
    schema_version: int
    schema_digest: str
    metadata_digest: str
    migration_id: str
    release_manifest_digest: str
    sqlite_build_manifest_digest: str


def _timestamp_now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _production_evidence(
    evidence: ProductionAuthorityEvidence,
    state: SqliteDatabaseState,
) -> InitializationEvidence:
    return InitializationEvidence(
        state=state,
        database_path=evidence.database_path,
        schema_id=evidence.schema_id,
        schema_version=evidence.schema_version,
        schema_digest=evidence.schema_digest,
        metadata_digest=evidence.metadata_digest,
        migration_id=evidence.migration_id,
        release_manifest_digest=evidence.release_manifest_digest,
        sqlite_build_manifest_digest=evidence.sqlite_build_manifest_digest,
    )


def _insert_metadata_and_migration(
    connection: sqlite3.Connection,
    *,
    metadata: object,
    migration: SchemaMigrationV1,
) -> None:
    if type(metadata) is not AuthorityMetadataV1:
        raise AuthorityInitializationError("initializer metadata type is invalid")
    # The exact typed model is intentionally converted to its public mapping;
    # no SQLite row is assembled from arbitrary caller-provided field names.
    metadata_model = metadata
    connection.execute(
        "INSERT INTO authority_metadata ("
        "authority_epoch_id, machine_authority_id, bootstrap_schema, "
        "bootstrap_generation, signing_key_id, approved_account_sid, provider_id, "
        "permitted_provider_operation, authority_policy_version, claim_policy_version, "
        "created_at_utc, bootstrap_digest, database_identity_digest, metadata_json, "
        "metadata_digest, production_schema_id, production_schema_version, "
        "production_schema_digest, metadata_encoding_version, "
        "initialization_policy_version, singleton_key"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            metadata_model.authority_epoch_id,  # type: ignore[union-attr]
            metadata_model.machine_authority_id,  # type: ignore[union-attr]
            metadata_model.bootstrap_schema,  # type: ignore[union-attr]
            metadata_model.bootstrap_generation,  # type: ignore[union-attr]
            metadata_model.signing_key_id,  # type: ignore[union-attr]
            metadata_model.approved_account_sid,  # type: ignore[union-attr]
            metadata_model.provider_id,  # type: ignore[union-attr]
            metadata_model.permitted_provider_operation,  # type: ignore[union-attr]
            metadata_model.authority_policy_version,  # type: ignore[union-attr]
            metadata_model.claim_policy_version,  # type: ignore[union-attr]
            metadata_model.created_at_utc,  # type: ignore[union-attr]
            bytes.fromhex(metadata_model.bootstrap_digest),  # type: ignore[union-attr]
            bytes.fromhex(metadata_model.database_identity_digest),  # type: ignore[union-attr]
            metadata_model.canonical_bytes(),  # type: ignore[union-attr]
            metadata_model.digest,  # type: ignore[union-attr]
            metadata_model.production_schema_id,  # type: ignore[union-attr]
            metadata_model.production_schema_version,  # type: ignore[union-attr]
            bytes.fromhex(metadata_model.production_schema_digest),  # type: ignore[union-attr]
            metadata_model.metadata_encoding_version,  # type: ignore[union-attr]
            metadata_model.initialization_policy_version,  # type: ignore[union-attr]
            metadata_model.singleton_key,  # type: ignore[union-attr]
        ),
    )
    connection.execute(
        "INSERT INTO schema_migrations ("
        "migration_id, authority_epoch_id, schema_version, migration_policy_version, "
        "migration_digest, application_release_digest, migration_json, applied_at_utc"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            migration.migration_id,
            migration.authority_epoch_id,
            migration.schema_version,
            migration.migration_policy_version,
            migration.migration_digest,
            migration.application_release_digest,
            migration.migration_json,
            migration.applied_at_utc,
        ),
    )


def _initialize_database_transaction(
    *,
    database_path: str | Path,
    journal_path: str | Path,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    release_manifest: ReleaseManifestEvidence,
    sqlite_build: SqliteAuthorityBuildEvidence,
    now_utc: str,
    connection_factory: Callable[..., sqlite3.Connection] | None = None,
) -> InitializationEvidence:
    """Initialize one already-precreated pair; all evidence is ready before BEGIN."""

    if connection_factory is not None and not callable(connection_factory):
        raise AuthorityInitializationError("SQLite connection factory is invalid")
    database = str(database_path)
    journal = str(journal_path)
    metadata = authority_metadata_from_bootstrap(
        bootstrap, bootstrap_digest=bootstrap_digest, created_at_utc=now_utc
    )
    migration = create_schema_migration_v1(
        bootstrap.authority_epoch_id,
        release_manifest=release_manifest,
        applied_at_utc=now_utc,
    )
    connection: sqlite3.Connection | None = None
    try:
        if connection_factory is None:
            connection = open_writable_authority_sqlite_connection(
                database, vfs=sqlite_build.vfs
            )
        else:
            connection = connection_factory(database)
        if type(connection) is not sqlite3.Connection:
            raise AuthorityInitializationError("SQLite connection type is not exact")
        if connection.in_transaction:
            raise AuthorityInitializationError(
                "initializer connection has an active transaction"
            )
        configure_and_validate_authority_sqlite_connection(
            connection, database_path=database, journal_path=journal
        )
        try:
            state = SqliteDatabaseState(validate_schema_state(connection))
        except (SchemaValidationError, ValueError) as error:
            raise AuthorityInitializationError(
                "database state could not be classified"
            ) from error
        already_supported = state is SqliteDatabaseState.INITIALIZED_SUPPORTED
        if (
            state is not SqliteDatabaseState.PRECREATED_UNINITIALIZED
            and not already_supported
        ):
            raise AuthorityInitializationError(
                "database is not PRECREATED_UNINITIALIZED"
            )
        if not already_supported:
            connection.execute("BEGIN EXCLUSIVE")
            try:
                execute_schema_artifact(connection)
                validate_production_schema_state = validate_schema_state(connection)
                if (
                    validate_production_schema_state
                    != SqliteDatabaseState.INITIALIZED_UNSUPPORTED.value
                ):
                    raise AuthorityInitializationError(
                        "schema did not remain transactional during initialization"
                    )
                _insert_metadata_and_migration(
                    connection, metadata=metadata, migration=migration
                )
                validate_production_authority_database_in_transaction(
                    connection,
                    database_path=database,
                    bootstrap=bootstrap,
                    bootstrap_digest=bootstrap_digest,
                    release_manifest=release_manifest,
                    sqlite_build=sqlite_build,
                )
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise
    except AuthorityInitializationError:
        raise
    except (
        sqlite3.Error,
        OSError,
        ValueError,
        TypeError,
        SchemaValidationError,
    ) as error:
        raise AuthorityInitializationError(
            "production database initialization failed"
        ) from error
    finally:
        if connection is not None:
            connection.close()
    try:
        evidence = validate_production_authority_database(
            database_path=database,
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap_digest,
            release_manifest=release_manifest,
            sqlite_build=sqlite_build,
        )
    except (
        AuthoritySchemaError,
        sqlite3.Error,
        OSError,
        ValueError,
        TypeError,
    ) as error:
        raise AuthorityInitializationError(
            "post-commit read-only validation failed"
        ) from error
    return _production_evidence(evidence, SqliteDatabaseState.INITIALIZED_SUPPORTED)


def initialize_authority_database_for_test(
    *,
    database_path: str | Path,
    journal_path: str | Path,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    release_manifest: ReleaseManifestEvidence,
    sqlite_build: SqliteAuthorityBuildEvidence,
    now_utc: str,
    connection_factory: Callable[..., sqlite3.Connection] = sqlite3.connect,
) -> InitializationEvidence:
    """Explicit test-injection boundary for disposable database acceptance tests."""

    return _initialize_database_transaction(
        database_path=database_path,
        journal_path=journal_path,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
        now_utc=now_utc,
        connection_factory=connection_factory,
    )


def initialize_installed_authority_database() -> InitializationEvidence:
    """Run the fixed-path, elevated administrator initialization action."""

    if os.name != "nt":
        raise UnsupportedWindowsPlatformError("database initialization is Windows-only")
    require_administrator_token()
    selected_release = load_approved_release_manifest()
    selected_build = load_approved_sqlite_authority_build()
    preflight: ProvisioningEvidence = validate_installed_authority()
    sid = preflight.trading_sid
    bootstrap_bytes, signature_bytes = read_installed_authority_material(sid)
    bootstrap = parse_bootstrap_bytes(bootstrap_bytes)
    verification = verify_bootstrap_signature(
        bootstrap_bytes,
        signature_bytes,
        key_registry=PRODUCTION_PINNED_BOOTSTRAP_KEYS,
    )
    if verification.bootstrap != bootstrap:
        raise AuthorityInitializationError(
            "verified bootstrap facts changed during initialization"
        )
    if preflight.database_state == SqliteDatabaseState.INITIALIZED_SUPPORTED.value:
        evidence = validate_production_authority_database(
            database_path=PRODUCTION_AUTHORITY_PATHS.database,
            bootstrap=bootstrap,
            bootstrap_digest=verification.bootstrap_digest,
            release_manifest=selected_release,
            sqlite_build=selected_build,
        )
        return _production_evidence(evidence, SqliteDatabaseState.INITIALIZED_SUPPORTED)
    if preflight.database_state != SqliteDatabaseState.PRECREATED_UNINITIALIZED.value:
        raise AuthorityInitializationError("database is not PRECREATED_UNINITIALIZED")
    return _initialize_database_transaction(
        database_path=PRODUCTION_AUTHORITY_PATHS.database,
        journal_path=PRODUCTION_AUTHORITY_PATHS.journal,
        bootstrap=bootstrap,
        bootstrap_digest=verification.bootstrap_digest,
        release_manifest=selected_release,
        sqlite_build=selected_build,
        now_utc=_timestamp_now_utc(),
    )
