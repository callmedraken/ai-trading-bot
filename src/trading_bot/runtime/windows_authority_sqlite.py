"""SQLite prerequisites and connection setup for the authority runtime."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from trading_bot.runtime.windows_authority import WindowsAuthorityError


class SqliteDurabilityError(WindowsAuthorityError):
    """Raised when an authority SQLite contract is not satisfied."""


@dataclass(frozen=True, slots=True)
class InstalledSqliteEvidence:
    """Read-only evidence about administrator-provisioned SQLite files."""

    database_path: str
    journal_path: str
    database_openable: bool
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


def validate_installed_sqlite_prerequisites(
    connection: sqlite3.Connection,
    *,
    database_path: str | Path,
    journal_path: str | Path,
) -> InstalledSqliteEvidence:
    """Validate installed SQLite files without configuring the connection.

    This read-only layer proves that the fixed database is openable, that only
    its main database is attached, and that the administrator-precreated
    persistent journal exists.  Runtime PRAGMAs are connection-local and are
    intentionally not read or changed here.
    """

    _require_exact_connection(connection)
    expected_database = str(database_path)
    expected_journal = str(journal_path)
    _require_database_file(expected_database)
    databases = _main_database(connection, expected_database)
    _require_persistent_journal(expected_journal)
    return InstalledSqliteEvidence(
        database_path=expected_database,
        journal_path=expected_journal,
        database_openable=True,
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
