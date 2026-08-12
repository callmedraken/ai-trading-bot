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
    UnsupportedWindowsPlatformError,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_schema import (
    AuthorityMetadataV1,
    AuthoritySchemaError,
    ReleaseManifestEvidence,
    SchemaMigrationV1,
    SchemaValidationError,
    SqliteAuthorityBuildEvidence,
    authority_metadata_from_bootstrap,
    create_schema_migration_v1,
    execute_schema_artifact,
    load_approved_release_manifest,
    load_approved_sqlite_authority_build,
    validate_production_authority_database_for_test,
    validate_production_authority_database_in_transaction,
    validate_schema_state,
)
from trading_bot.runtime.windows_authority_security import require_administrator_token
from trading_bot.runtime.windows_authority_sqlite import (
    SqliteDatabaseState,
    configure_and_validate_authority_sqlite_connection,
    open_disposable_read_only_sqlite_connection,
    open_writable_authority_sqlite_connection,
)
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    ValidatedProductionAuthority,
    acquire_validated_production_authority_for_test,
    require_validated_production_authority,
    validate_installed_authority_complete,
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
    authority: ValidatedProductionAuthority,
    state: SqliteDatabaseState,
) -> InitializationEvidence:
    return InitializationEvidence(
        state=state,
        database_path=authority.database_path,
        schema_id=authority.schema_id,
        schema_version=authority.schema_version,
        schema_digest=authority.schema_digest,
        metadata_digest=authority.metadata_digest,
        migration_id=authority.migration_id,
        release_manifest_digest=authority.release_manifest_digest,
        sqlite_build_manifest_digest=authority.sqlite_build_manifest_digest,
    )


def _require_same_installed_authority(
    expected: InstalledAuthorityValidation,
    actual: InstalledAuthorityValidation,
) -> None:
    """Reject changes in signed or resolved authority facts after commit."""

    expected_bootstrap = expected.bootstrap_verification.bootstrap
    actual_bootstrap = actual.bootstrap_verification.bootstrap
    if (
        actual_bootstrap.machine_authority_id != expected_bootstrap.machine_authority_id
        or actual_bootstrap.authority_epoch_id != expected_bootstrap.authority_epoch_id
        or actual_bootstrap.bootstrap_generation
        != expected_bootstrap.bootstrap_generation
        or actual_bootstrap.database_identity_digest
        != expected_bootstrap.database_identity_digest
        or actual.bootstrap_verification.bootstrap_digest
        != expected.bootstrap_verification.bootstrap_digest
        or actual.provisioning.trading_sid != expected.provisioning.trading_sid
    ):
        raise AuthorityInitializationError(
            "installed Windows authority facts changed after database commit"
        )


def _post_commit_installed_production_evidence(
    *,
    expected_validation: InstalledAuthorityValidation,
) -> ValidatedProductionAuthority:
    """Re-establish Windows trust, then consume its issued capability."""

    try:
        actual_validation = validate_installed_authority_complete()
    except WindowsAuthorityError as error:
        raise AuthorityInitializationError(
            "post-commit installed Windows validation failed"
        ) from error
    _require_same_installed_authority(expected_validation, actual_validation)
    try:
        return require_validated_production_authority(actual_validation)
    except WindowsAuthorityError as error:
        raise AuthorityInitializationError(
            "post-commit validation did not issue executable authority"
        ) from error


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
    post_commit_validator: Callable[[], ValidatedProductionAuthority],
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
                locked_state = SqliteDatabaseState(validate_schema_state(connection))
                if locked_state is SqliteDatabaseState.INITIALIZED_SUPPORTED:
                    # A competing initializer won the exclusive transaction.  Do
                    # not run DDL or commit an application transaction here; the
                    # post-close validator below performs the complete read-only
                    # verification on this connection's approved VFS.
                    connection.rollback()
                else:
                    if locked_state is not SqliteDatabaseState.PRECREATED_UNINITIALIZED:
                        raise AuthorityInitializationError(
                            "database changed before exclusive initialization"
                        )
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
        evidence = post_commit_validator()
        if type(evidence) is not ValidatedProductionAuthority:
            raise AuthorityInitializationError(
                "post-commit validator returned invalid production capability"
            )
    except (
        AuthorityInitializationError,
        AuthoritySchemaError,
        WindowsAuthorityError,
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

    def validate_disposable_after_commit() -> ValidatedProductionAuthority:
        connection = open_disposable_read_only_sqlite_connection(database_path)
        try:
            evidence = validate_production_authority_database_for_test(
                connection,
                database_path=database_path,
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap_digest,
                release_manifest=release_manifest,
                sqlite_build=sqlite_build,
            )
            return acquire_validated_production_authority_for_test(
                bootstrap=bootstrap,
                bootstrap_digest=bootstrap_digest,
                production_evidence=evidence,
            )
        finally:
            connection.close()

    return _initialize_database_transaction(
        database_path=database_path,
        journal_path=journal_path,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        release_manifest=release_manifest,
        sqlite_build=sqlite_build,
        now_utc=now_utc,
        connection_factory=connection_factory,
        post_commit_validator=validate_disposable_after_commit,
    )


def initialize_installed_authority_database() -> InitializationEvidence:
    """Run the fixed-path, elevated administrator initialization action."""

    if os.name != "nt":
        raise UnsupportedWindowsPlatformError("database initialization is Windows-only")
    require_administrator_token()
    selected_release = load_approved_release_manifest()
    selected_build = load_approved_sqlite_authority_build()
    preflight = validate_installed_authority_complete()
    provisioning = preflight.provisioning
    bootstrap = preflight.bootstrap_verification.bootstrap
    bootstrap_digest = preflight.bootstrap_verification.bootstrap_digest
    if provisioning.database_state == SqliteDatabaseState.INITIALIZED_SUPPORTED.value:
        authority = require_validated_production_authority(preflight)
        return _production_evidence(
            authority, SqliteDatabaseState.INITIALIZED_SUPPORTED
        )
    if (
        provisioning.database_state
        != SqliteDatabaseState.PRECREATED_UNINITIALIZED.value
    ):
        raise AuthorityInitializationError("database is not PRECREATED_UNINITIALIZED")
    return _initialize_database_transaction(
        database_path=PRODUCTION_AUTHORITY_PATHS.database,
        journal_path=PRODUCTION_AUTHORITY_PATHS.journal,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        release_manifest=selected_release,
        sqlite_build=selected_build,
        now_utc=_timestamp_now_utc(),
        post_commit_validator=lambda: _post_commit_installed_production_evidence(
            expected_validation=preflight,
        ),
    )
