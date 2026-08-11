"""SQLite prerequisites and connection setup for the authority runtime."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from trading_bot.runtime.windows_authority import WindowsAuthorityError
from trading_bot.runtime.windows_authority_schema import (
    SchemaValidationError,
    configure_trusted_schema_off,
    validate_schema_state,
)


class SqliteDurabilityError(WindowsAuthorityError):
    """Raised when an authority SQLite contract is not satisfied."""


class SqliteDatabaseState(StrEnum):
    """The explicit lifecycle state proven by installed SQLite validation."""

    NOT_PRESENT = "NOT_PRESENT"
    PRECREATED_UNINITIALIZED = "PRECREATED_UNINITIALIZED"
    INITIALIZED_SUPPORTED = "INITIALIZED_SUPPORTED"
    INITIALIZED_UNSUPPORTED = "INITIALIZED_UNSUPPORTED"
    INVALID_MISMATCHED = "INVALID_MISMATCHED"


@dataclass(frozen=True, slots=True)
class InstalledSqliteEvidence:
    """Read-only evidence about administrator-provisioned SQLite files."""

    database_path: str
    journal_path: str
    database_openable: bool
    database_state: SqliteDatabaseState
    attached_database_count: int
    persistent_journal_present: bool
    trusted_schema: bool = False


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
    trusted_schema: bool = False


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


def _determine_database_state(connection: sqlite3.Connection) -> SqliteDatabaseState:
    schema_objects = _schema_objects(connection)
    if not schema_objects:
        return SqliteDatabaseState.PRECREATED_UNINITIALIZED
    try:
        state = validate_schema_state(connection)
    except SchemaValidationError:
        state = SqliteDatabaseState.INITIALIZED_UNSUPPORTED.value
    return SqliteDatabaseState(state)


def validate_installed_sqlite_prerequisites(
    connection: sqlite3.Connection,
    *,
    database_path: str | Path,
    journal_path: str | Path,
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
    try:
        configure_trusted_schema_off(connection)
    except SchemaValidationError as error:
        raise SqliteDurabilityError(str(error)) from error
    databases = _main_database(connection, expected_database)
    _read_schema(connection)
    _require_integrity(connection)
    _require_persistent_journal(expected_journal)
    database_state = _determine_database_state(connection)
    if database_state in {
        SqliteDatabaseState.INITIALIZED_UNSUPPORTED,
        SqliteDatabaseState.INVALID_MISMATCHED,
    }:
        raise SqliteDurabilityError(
            f"{database_state.value}: initialized SQLite authority schema is "
            "unsupported or mismatched"
        )
    return InstalledSqliteEvidence(
        database_path=expected_database,
        journal_path=expected_journal,
        database_openable=True,
        database_state=database_state,
        attached_database_count=len(databases),
        persistent_journal_present=True,
        trusted_schema=True,
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
    try:
        configure_trusted_schema_off(connection)
    except SchemaValidationError as error:
        raise SqliteDurabilityError(str(error)) from error
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
        trusted_schema=True,
    )
