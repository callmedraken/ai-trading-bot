"""Read-only SQLite durability-contract tests using disposable databases."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from trading_bot.runtime.windows_authority import WindowsAuthorityError
from trading_bot.runtime.windows_authority_provisioning import (
    _validate_database_if_present,
)
from trading_bot.runtime.windows_authority_sqlite import (
    SqliteDurabilityError,
    configure_and_validate_authority_sqlite_connection,
    open_read_only_sqlite_connection,
    validate_installed_sqlite_prerequisites,
)


def _fresh_database(tmp_path: Path) -> tuple[sqlite3.Connection, Path, Path]:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "authority.sqlite3-journal"
    connection = sqlite3.connect(database)
    journal.touch()
    return connection, database, journal


def test_installed_validation_is_read_only_and_does_not_claim_runtime_pragmas(
    tmp_path: Path,
) -> None:
    connection, database, journal = _fresh_database(tmp_path)
    try:
        before = (
            connection.execute("PRAGMA foreign_keys").fetchone()[0],
            connection.execute("PRAGMA journal_mode").fetchone()[0],
            connection.execute("PRAGMA synchronous").fetchone()[0],
        )
        before_bytes = database.read_bytes()
        evidence = validate_installed_sqlite_prerequisites(
            connection, database_path=database, journal_path=journal
        )
        after = (
            connection.execute("PRAGMA foreign_keys").fetchone()[0],
            connection.execute("PRAGMA journal_mode").fetchone()[0],
            connection.execute("PRAGMA synchronous").fetchone()[0],
        )
        assert before == after
        assert evidence.database_openable is True
        assert evidence.attached_database_count == 1
        assert evidence.persistent_journal_present is True
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
        assert database.read_bytes() == before_bytes
    finally:
        connection.close()


@pytest.mark.parametrize(
    "payload",
    [
        b"not a SQLite database",
        b"SQLite format 3\x00" + b"\x00" * 16,
    ],
)
def test_installed_validation_rejects_non_sqlite_and_truncated_database(
    tmp_path: Path, payload: bytes
) -> None:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "authority.sqlite3-journal"
    database.write_bytes(payload)
    journal.touch()
    connection = sqlite3.connect(database)
    try:
        with pytest.raises(SqliteDurabilityError):
            validate_installed_sqlite_prerequisites(
                connection, database_path=database, journal_path=journal
            )
    finally:
        connection.close()


def test_installed_validation_uses_fixed_read_only_sqlite_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_provisioning as provisioning
    import trading_bot.runtime.windows_authority_sqlite as sqlite_runtime

    calls: list[tuple[object, dict[str, object]]] = []

    class FakeConnection:
        def close(self) -> None:
            return None

    def fake_connect(database: object, **kwargs: object) -> FakeConnection:
        calls.append((database, kwargs))
        return FakeConnection()

    monkeypatch.setattr(sqlite_runtime.sqlite3, "connect", fake_connect)
    monkeypatch.setattr(
        provisioning,
        "validate_installed_sqlite_prerequisites",
        lambda connection, *, database_path, journal_path: None,
    )

    assert provisioning._validate_database_if_present(True, True) == "VALIDATED"
    assert calls == [
        (
            "file:///F:/AITradingBot/Authority/authority.sqlite3?mode=ro",
            {"uri": True},
        )
    ]


def test_installed_validation_rejects_attached_database(
    tmp_path: Path,
) -> None:
    connection, database, journal = _fresh_database(tmp_path)
    attached = tmp_path / "attached.sqlite3"
    try:
        connection.execute("ATTACH DATABASE ? AS extra", (str(attached),))
        with pytest.raises(SqliteDurabilityError):
            validate_installed_sqlite_prerequisites(
                connection, database_path=database, journal_path=journal
            )
        connection.execute("DETACH DATABASE extra")
    finally:
        connection.close()


def test_read_only_sqlite_connection_rejects_writes_and_preserves_bytes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "authority.sqlite3"
    connection = sqlite3.connect(database)
    connection.close()
    before_bytes = database.read_bytes()

    read_only = open_read_only_sqlite_connection(database)
    try:
        assert read_only.execute("SELECT name FROM sqlite_schema").fetchall() == []
        with pytest.raises(sqlite3.OperationalError):
            read_only.execute("CREATE TABLE should_not_exist(value TEXT)")
    finally:
        read_only.close()

    assert database.read_bytes() == before_bytes


def test_runtime_connection_setup_configures_every_required_pragma(
    tmp_path: Path,
) -> None:
    connection, database, journal = _fresh_database(tmp_path)
    try:
        evidence = configure_and_validate_authority_sqlite_connection(
            connection, database_path=database, journal_path=journal
        )
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "persist"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert evidence.foreign_keys is True
        assert evidence.journal_mode == "persist"
        assert evidence.synchronous == 2
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            == []
        )
    finally:
        connection.close()


def test_runtime_setup_rejects_attached_database_before_configuration(
    tmp_path: Path,
) -> None:
    connection, database, journal = _fresh_database(tmp_path)
    attached = tmp_path / "attached.sqlite3"
    try:
        connection.execute("ATTACH DATABASE ? AS extra", (str(attached),))
        before = (
            connection.execute("PRAGMA foreign_keys").fetchone()[0],
            connection.execute("PRAGMA journal_mode").fetchone()[0],
        )
        with pytest.raises(SqliteDurabilityError):
            configure_and_validate_authority_sqlite_connection(
                connection, database_path=database, journal_path=journal
            )
        assert (
            connection.execute("PRAGMA foreign_keys").fetchone()[0],
            connection.execute("PRAGMA journal_mode").fetchone()[0],
        ) == before
        connection.execute("DETACH DATABASE extra")
    finally:
        connection.close()


def test_runtime_setup_rejects_active_transaction_before_configuration(
    tmp_path: Path,
) -> None:
    connection, database, journal = _fresh_database(tmp_path)
    try:
        connection.execute("BEGIN")
        with pytest.raises(SqliteDurabilityError):
            configure_and_validate_authority_sqlite_connection(
                connection, database_path=database, journal_path=journal
            )
        assert connection.in_transaction is True
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 0
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        connection.rollback()
    finally:
        connection.close()


def test_installed_validation_rejects_missing_persistent_journal(
    tmp_path: Path,
) -> None:
    database = tmp_path / "authority.sqlite3"
    missing_journal = tmp_path / "missing-authority.sqlite3-journal"
    connection = sqlite3.connect(database)
    try:
        with pytest.raises(SqliteDurabilityError):
            validate_installed_sqlite_prerequisites(
                connection, database_path=database, journal_path=missing_journal
            )
    finally:
        connection.close()


def test_installed_database_journal_pairing_remains_fail_closed() -> None:
    assert _validate_database_if_present(False, False) == "NOT_PRESENT"
    with pytest.raises(WindowsAuthorityError):
        _validate_database_if_present(True, False)
    with pytest.raises(WindowsAuthorityError):
        _validate_database_if_present(False, True)
