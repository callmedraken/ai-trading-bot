"""SQLite prerequisites and connection setup for the authority runtime."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from trading_bot.runtime.windows_authority import (
    BootstrapVerification,
    WindowsAuthorityError,
)


class SqliteDurabilityError(WindowsAuthorityError):
    """Raised when an authority SQLite contract is not satisfied."""


class SqliteDatabaseState(StrEnum):
    """The explicit lifecycle state proven by installed SQLite validation."""

    NOT_PRESENT = "NOT_PRESENT"
    PRECREATED_UNINITIALIZED = "PRECREATED_UNINITIALIZED"
    IDENTITY_BOUND = "IDENTITY_BOUND"
    INVALID_MISMATCHED = "INVALID_MISMATCHED"


_AUTHORITY_METADATA_COLUMNS = (
    ("authority_epoch_id", "TEXT"),
    ("machine_authority_id", "TEXT"),
    ("bootstrap_schema", "INTEGER"),
    ("bootstrap_generation", "INTEGER"),
    ("signing_key_id", "TEXT"),
    ("approved_account_sid", "TEXT"),
    ("provider_id", "TEXT"),
    ("permitted_provider_operation", "TEXT"),
    ("authority_policy_version", "TEXT"),
    ("claim_policy_version", "TEXT"),
    ("created_at_utc", "TEXT"),
    ("bootstrap_digest", "BLOB"),
    ("database_identity_digest", "BLOB"),
    ("metadata_json", "BLOB"),
    ("metadata_digest", "BLOB"),
    ("singleton_key", "INTEGER"),
)


@dataclass(frozen=True, slots=True)
class InstalledSqliteEvidence:
    """Read-only evidence about administrator-provisioned SQLite files."""

    database_path: str
    journal_path: str
    database_openable: bool
    database_state: SqliteDatabaseState
    attached_database_count: int
    persistent_journal_present: bool


@dataclass(frozen=True, slots=True)
class SqliteDurabilityEvidence:
    """Evidence returned after configuring one production authority connection."""

    database_path: str
    journal_path: str
    foreign_keys: bool
    journal_mode: str
    synchronous: int
    attached_database_count: int
    persistent_journal_present: bool


def _require_exact_connection(connection: sqlite3.Connection) -> None:
    if type(connection) is not sqlite3.Connection:
        raise SqliteDurabilityError("SQLite contract requires sqlite3.Connection")


def _main_database(
    connection: sqlite3.Connection,
    expected_database: str,
) -> tuple[tuple[object, ...], ...]:
    try:
        databases = tuple(
            tuple(row) for row in connection.execute("PRAGMA database_list").fetchall()
        )
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SqliteDurabilityError("SQLite database list could not be read") from error
    if len(databases) != 1 or databases[0][1] != "main":
        raise SqliteDurabilityError("SQLite connection has an attached database")
    actual_database = str(databases[0][2] or "")
    if os.path.normcase(actual_database) != os.path.normcase(expected_database):
        raise SqliteDurabilityError("SQLite main database path is not the fixed target")
    return databases


def _require_persistent_journal(journal_path: str) -> None:
    if not Path(journal_path).is_file():
        raise SqliteDurabilityError("SQLite persistent journal is not pre-created")


def _require_database_file(database_path: str) -> None:
    if not Path(database_path).is_file():
        raise SqliteDurabilityError("SQLite authority database is not pre-created")


def _read_only_sqlite_uri(database_path: str | Path) -> str:
    path = str(database_path)
    if len(path) >= 3 and path[1] == ":" and path[2] in {"\\", "/"}:
        normalized = path.replace("\\", "/")
        encoded = quote(normalized, safe="/:")
        return f"file:///{encoded}?mode=ro"
    return f"file:{quote(path, safe='/')}?mode=ro"


def open_read_only_sqlite_connection(database_path: str | Path) -> sqlite3.Connection:
    """Open one existing database read-only without an implicit create fallback."""

    try:
        return sqlite3.connect(_read_only_sqlite_uri(database_path), uri=True)
    except sqlite3.Error as error:
        raise SqliteDurabilityError(
            "SQLite read-only database could not be opened"
        ) from error


def _read_schema(connection: sqlite3.Connection) -> None:
    try:
        connection.execute(
            "SELECT type, name, tbl_name, rootpage, sql FROM sqlite_schema"
        ).fetchall()
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SqliteDurabilityError(
            "SQLite database schema could not be read"
        ) from error


def _require_integrity(connection: sqlite3.Connection) -> None:
    try:
        result = tuple(
            tuple(row)
            for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SqliteDurabilityError(
            "SQLite integrity check could not be read"
        ) from error
    if result != (("ok",),):
        raise SqliteDurabilityError("SQLite integrity check did not succeed")


def _schema_objects(
    connection: sqlite3.Connection,
) -> tuple[tuple[object, ...], ...]:
    try:
        rows = tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT type, name, tbl_name, rootpage, sql FROM sqlite_schema"
            ).fetchall()
        )
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SqliteDurabilityError(
            "SQLite schema objects could not be read"
        ) from error
    return tuple(
        row
        for row in rows
        if not (type(row[1]) is str and row[1].startswith("sqlite_"))
    )


def _require_metadata_schema(
    connection: sqlite3.Connection,
    schema_objects: tuple[tuple[object, ...], ...],
) -> None:
    metadata_objects = [row for row in schema_objects if row[1] == "authority_metadata"]
    if len(metadata_objects) != 1 or metadata_objects[0][0] != "table":
        raise SqliteDurabilityError(
            "populated SQLite database does not contain one authority_metadata table"
        )
    try:
        columns = tuple(
            tuple(row)
            for row in connection.execute(
                "PRAGMA table_info(authority_metadata)"
            ).fetchall()
        )
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SqliteDurabilityError(
            "authority_metadata schema could not be read"
        ) from error
    actual_columns = tuple((row[1], row[2]) for row in columns)
    if actual_columns != _AUTHORITY_METADATA_COLUMNS:
        raise SqliteDurabilityError("authority_metadata schema is incompatible")


def _require_exact_text(value: object, field: str) -> str:
    if type(value) is not str:
        raise SqliteDurabilityError(f"authority_metadata {field} is not text")
    return value


def _require_exact_integer(value: object, field: str) -> int:
    if type(value) is not int:
        raise SqliteDurabilityError(f"authority_metadata {field} is not an integer")
    return value


def _require_digest_blob(value: object, field: str) -> bytes:
    if type(value) is not bytes or len(value) != hashlib.sha256().digest_size:
        raise SqliteDurabilityError(
            f"authority_metadata {field} is not a 32-byte digest"
        )
    return value


def _validate_identity_bound_metadata(
    connection: sqlite3.Connection,
    schema_objects: tuple[tuple[object, ...], ...],
    verification: BootstrapVerification | None,
) -> SqliteDatabaseState:
    _require_metadata_schema(connection, schema_objects)
    if verification is None:
        raise SqliteDurabilityError(
            "identity-bound database requires a verified bootstrap"
        )
    try:
        rows = tuple(
            tuple(row)
            for row in connection.execute(
                """
                SELECT authority_epoch_id, machine_authority_id,
                       bootstrap_schema, bootstrap_generation, signing_key_id,
                       approved_account_sid, provider_id,
                       permitted_provider_operation, authority_policy_version,
                       claim_policy_version, created_at_utc, bootstrap_digest,
                       database_identity_digest, metadata_json, metadata_digest,
                       singleton_key
                FROM authority_metadata
                """
            ).fetchall()
        )
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SqliteDurabilityError(
            "authority_metadata rows could not be read"
        ) from error
    if len(rows) != 1:
        raise SqliteDurabilityError(
            "authority_metadata must contain exactly one active singleton row"
        )
    row = rows[0]
    (
        authority_epoch_id,
        machine_authority_id,
        bootstrap_schema,
        bootstrap_generation,
        signing_key_id,
        approved_account_sid,
        provider_id,
        permitted_provider_operation,
        authority_policy_version,
        claim_policy_version,
        created_at_utc,
        bootstrap_digest,
        database_identity_digest,
        metadata_json,
        metadata_digest,
        singleton_key,
    ) = row
    bootstrap = verification.bootstrap
    expected_text = {
        "authority_epoch_id": bootstrap.authority_epoch_id,
        "machine_authority_id": bootstrap.machine_authority_id,
        "signing_key_id": bootstrap.signing_key_id,
        "approved_account_sid": bootstrap.approved_account_sid,
        "provider_id": bootstrap.provider_id,
        "permitted_provider_operation": bootstrap.permitted_provider_operation,
        "authority_policy_version": bootstrap.authority_policy_version,
        "claim_policy_version": bootstrap.claim_policy_version,
    }
    actual_text = {
        "authority_epoch_id": _require_exact_text(
            authority_epoch_id, "authority_epoch_id"
        ),
        "machine_authority_id": _require_exact_text(
            machine_authority_id, "machine_authority_id"
        ),
        "signing_key_id": _require_exact_text(signing_key_id, "signing_key_id"),
        "approved_account_sid": _require_exact_text(
            approved_account_sid, "approved_account_sid"
        ),
        "provider_id": _require_exact_text(provider_id, "provider_id"),
        "permitted_provider_operation": _require_exact_text(
            permitted_provider_operation, "permitted_provider_operation"
        ),
        "authority_policy_version": _require_exact_text(
            authority_policy_version, "authority_policy_version"
        ),
        "claim_policy_version": _require_exact_text(
            claim_policy_version, "claim_policy_version"
        ),
    }
    if actual_text != expected_text:
        raise SqliteDurabilityError(
            "authority_metadata does not match the verified bootstrap"
        )
    if (
        _require_exact_integer(bootstrap_schema, "bootstrap_schema")
        != bootstrap.bootstrap_schema
    ):
        raise SqliteDurabilityError("authority_metadata bootstrap schema mismatches")
    if (
        _require_exact_integer(bootstrap_generation, "bootstrap_generation")
        != bootstrap.bootstrap_generation
    ):
        raise SqliteDurabilityError(
            "authority_metadata bootstrap generation mismatches"
        )
    if _require_exact_integer(singleton_key, "singleton_key") != 1:
        raise SqliteDurabilityError("authority_metadata singleton key is not one")
    _require_exact_text(created_at_utc, "created_at_utc")
    if type(metadata_json) is not bytes:
        raise SqliteDurabilityError("authority_metadata metadata_json is not a BLOB")
    if (
        _require_digest_blob(metadata_digest, "metadata_digest")
        != hashlib.sha256(metadata_json).digest()
    ):
        raise SqliteDurabilityError("authority_metadata metadata digest mismatches")
    expected_bootstrap_digest = bytes.fromhex(verification.bootstrap_digest)
    if (
        _require_digest_blob(bootstrap_digest, "bootstrap_digest")
        != expected_bootstrap_digest
    ):
        raise SqliteDurabilityError("authority_metadata bootstrap digest mismatches")
    expected_database_digest = bytes.fromhex(bootstrap.database_identity_digest)
    if (
        _require_digest_blob(database_identity_digest, "database_identity_digest")
        != expected_database_digest
    ):
        raise SqliteDurabilityError(
            "authority_metadata database identity digest mismatches"
        )
    return SqliteDatabaseState.IDENTITY_BOUND


def _determine_database_state(
    connection: sqlite3.Connection,
    verification: BootstrapVerification | None,
) -> SqliteDatabaseState:
    schema_objects = _schema_objects(connection)
    if not schema_objects:
        return SqliteDatabaseState.PRECREATED_UNINITIALIZED
    return _validate_identity_bound_metadata(connection, schema_objects, verification)


def validate_installed_sqlite_prerequisites(
    connection: sqlite3.Connection,
    *,
    database_path: str | Path,
    journal_path: str | Path,
    verification: BootstrapVerification | None = None,
) -> InstalledSqliteEvidence:
    """Validate installed SQLite files without configuring the connection.

    This read-only layer proves the fixed database format, schema, integrity,
    attachment, journal, and explicit lifecycle state. Runtime PRAGMAs are
    connection-local and are intentionally not read or changed here.
    """

    _require_exact_connection(connection)
    expected_database = str(database_path)
    expected_journal = str(journal_path)
    _require_database_file(expected_database)
    databases = _main_database(connection, expected_database)
    _read_schema(connection)
    _require_integrity(connection)
    _require_persistent_journal(expected_journal)
    database_state = _determine_database_state(connection, verification)
    return InstalledSqliteEvidence(
        database_path=expected_database,
        journal_path=expected_journal,
        database_openable=True,
        database_state=database_state,
        attached_database_count=len(databases),
        persistent_journal_present=True,
    )


def configure_and_validate_authority_sqlite_connection(
    connection: sqlite3.Connection,
    *,
    database_path: str | Path,
    journal_path: str | Path,
) -> SqliteDurabilityEvidence:
    """Configure and verify every runtime PRAGMA on one authority connection.

    The caller supplies the fixed production database and journal paths (or a
    disposable administrator-prepared acceptance pair).  This helper performs
    no schema initialization, migration, ATTACH, VACUUM, or DDL.
    """

    _require_exact_connection(connection)
    if connection.in_transaction:
        raise SqliteDurabilityError(
            "SQLite connection must not have an active transaction before setup"
        )
    expected_database = str(database_path)
    expected_journal = str(journal_path)
    _require_database_file(expected_database)
    _main_database(connection, expected_database)
    _require_persistent_journal(expected_journal)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = PERSIST").fetchone()
        connection.execute("PRAGMA synchronous = FULL")
        foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        journal_mode = str(
            connection.execute("PRAGMA journal_mode").fetchone()[0]
        ).lower()
        synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
        databases = _main_database(connection, expected_database)
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SqliteDurabilityError(
            "SQLite durability configuration could not be established"
        ) from error
    if foreign_keys != 1:
        raise SqliteDurabilityError("SQLite foreign keys are not enabled")
    if journal_mode != "persist":
        raise SqliteDurabilityError("SQLite journal mode is not PERSIST")
    if synchronous != 2:
        raise SqliteDurabilityError("SQLite synchronous mode is not FULL")
    _require_persistent_journal(expected_journal)
    return SqliteDurabilityEvidence(
        database_path=expected_database,
        journal_path=expected_journal,
        foreign_keys=True,
        journal_mode=journal_mode,
        synchronous=synchronous,
        attached_database_count=len(databases),
        persistent_journal_present=True,
    )
