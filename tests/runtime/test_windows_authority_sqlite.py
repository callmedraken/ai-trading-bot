"""Read-only SQLite durability-contract tests using disposable databases."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from trading_bot.runtime.windows_authority_sqlite import (
    SqliteDurabilityError,
    validate_persistent_sqlite_contract,
)


def _configured_database(tmp_path: Path) -> tuple[sqlite3.Connection, Path, Path]:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "authority.sqlite3-journal"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=ON")
    assert connection.execute("PRAGMA journal_mode=PERSIST").fetchone()[0] == "persist"
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("CREATE TABLE sample (value INTEGER)")
    connection.commit()
    if not journal.is_file():
        journal.touch()
    return connection, database, journal


def test_persistent_sqlite_contract_is_read_only_and_exact(tmp_path: Path) -> None:
    connection, database, journal = _configured_database(tmp_path)
    try:
        evidence = validate_persistent_sqlite_contract(
            connection, database_path=database, journal_path=journal
        )
        assert evidence.foreign_keys is True
        assert evidence.journal_mode == "persist"
        assert evidence.synchronous == 2
        assert evidence.attached_database_count == 1
    finally:
        connection.close()


def test_attached_database_is_rejected_without_production_side_effects(
    tmp_path: Path,
) -> None:
    connection, database, journal = _configured_database(tmp_path)
    attached = tmp_path / "attached.sqlite3"
    try:
        connection.execute("ATTACH DATABASE ? AS extra", (str(attached),))
        with pytest.raises(SqliteDurabilityError):
            validate_persistent_sqlite_contract(
                connection, database_path=database, journal_path=journal
            )
        connection.execute("DETACH DATABASE extra")
    finally:
        connection.close()


def test_missing_persistent_journal_is_rejected(tmp_path: Path) -> None:
    connection, database, _journal = _configured_database(tmp_path)
    missing_journal = tmp_path / "missing-authority.sqlite3-journal"
    try:
        with pytest.raises(SqliteDurabilityError):
            validate_persistent_sqlite_contract(
                connection, database_path=database, journal_path=missing_journal
            )
    finally:
        connection.close()
