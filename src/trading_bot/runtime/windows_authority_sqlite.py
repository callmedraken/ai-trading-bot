"""Read-only checks for the architecture-77 persistent-journal contract."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from trading_bot.runtime.windows_authority import WindowsAuthorityError


class SqliteDurabilityError(WindowsAuthorityError):
    """Raised when an opened authority database is not durably configured."""


@dataclass(frozen=True, slots=True)
class SqliteDurabilityEvidence:
    """Sanitized read-only SQLite configuration evidence."""

    database_path: str
    journal_path: str
    foreign_keys: bool
    journal_mode: str
    synchronous: int
    attached_database_count: int
    persistent_journal_present: bool


def validate_persistent_sqlite_contract(
    connection: sqlite3.Connection,
    *,
    database_path: str | Path,
    journal_path: str | Path,
) -> SqliteDurabilityEvidence:
    """Validate SQLite PRAGMAs and one fixed main database without mutation.

    The helper issues only read PRAGMAs and ``database_list``.  It never
    executes ATTACH, VACUUM, DDL, migration, journal-mode assignment, or an
    automatic repair.  Native handle/path inspection remains the authority for
    local NTFS and ACL properties.
    """

    if type(connection) is not sqlite3.Connection:
        raise SqliteDurabilityError("SQLite contract requires sqlite3.Connection")
    expected_database = str(database_path)
    expected_journal = str(journal_path)
    try:
        foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        journal_mode = str(
            connection.execute("PRAGMA journal_mode").fetchone()[0]
        ).lower()
        synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
        databases = connection.execute("PRAGMA database_list").fetchall()
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise SqliteDurabilityError(
            "SQLite durability facts could not be read"
        ) from error
    if foreign_keys != 1:
        raise SqliteDurabilityError("SQLite foreign keys are not enabled")
    if journal_mode != "persist":
        raise SqliteDurabilityError("SQLite journal mode is not PERSIST")
    if synchronous != 2:
        raise SqliteDurabilityError("SQLite synchronous mode is not FULL")
    if len(databases) != 1 or databases[0][1] != "main":
        raise SqliteDurabilityError("SQLite connection has an attached database")
    actual_database = str(databases[0][2] or "")
    if os.path.normcase(actual_database) != os.path.normcase(expected_database):
        raise SqliteDurabilityError("SQLite main database path is not the fixed target")
    if not Path(expected_journal).is_file():
        raise SqliteDurabilityError("SQLite persistent journal is not pre-created")
    return SqliteDurabilityEvidence(
        expected_database,
        expected_journal,
        True,
        journal_mode,
        synchronous,
        len(databases),
        True,
    )
