"""Read-only SQLite durability-contract tests using disposable databases."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    BootstrapVerification,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_schema import SchemaValidationError
from trading_bot.runtime.windows_authority_sqlite import (
    InstalledSqliteEvidence,
    SqliteDatabaseState,
    SqliteDurabilityError,
    configure_and_validate_authority_sqlite_connection,
    open_read_only_sqlite_connection,
    validate_installed_sqlite_prerequisites,
)


def _verification() -> BootstrapVerification:
    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id="87654321-4321-8765-cba9-876543210987",
        authority_epoch_id="12345678-1234-5678-9abc-def012345678",
        signing_key_id="production-bootstrap-p256/v1",
        approved_account_sid="S-1-5-21-100-200-300-400",
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="a" * 64,
    )
    return BootstrapVerification(
        bootstrap=bootstrap,
        bootstrap_digest=hashlib.sha256(bootstrap.canonical_bytes()).hexdigest(),
        signing_key_id=bootstrap.signing_key_id,
        signature_length=64,
    )


# This Architecture-77-shaped table is a rejection-only test fixture. It is
# deliberately not imported by production validation and is not a schema
# manifest for Milestone A.
_METADATA_SCHEMA = """
CREATE TABLE authority_metadata (
    authority_epoch_id TEXT PRIMARY KEY,
    machine_authority_id TEXT NOT NULL,
    bootstrap_schema INTEGER NOT NULL,
    bootstrap_generation INTEGER NOT NULL,
    signing_key_id TEXT NOT NULL,
    approved_account_sid TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    permitted_provider_operation TEXT NOT NULL,
    authority_policy_version TEXT NOT NULL,
    claim_policy_version TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    bootstrap_digest BLOB NOT NULL,
    database_identity_digest BLOB NOT NULL,
    metadata_json BLOB NOT NULL,
    metadata_digest BLOB NOT NULL,
    singleton_key INTEGER NOT NULL
)
"""


def _metadata_database(
    tmp_path: Path, verification: BootstrapVerification
) -> tuple[Path, Path]:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "authority.sqlite3-journal"
    bootstrap = verification.bootstrap
    metadata_json = b'{"opaque":"test-only"}'
    connection = sqlite3.connect(database)
    try:
        connection.executescript(_METADATA_SCHEMA)
        connection.execute(
            """
            INSERT INTO authority_metadata VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                bootstrap.authority_epoch_id,
                bootstrap.machine_authority_id,
                bootstrap.bootstrap_schema,
                bootstrap.bootstrap_generation,
                bootstrap.signing_key_id,
                bootstrap.approved_account_sid,
                bootstrap.provider_id,
                bootstrap.permitted_provider_operation,
                bootstrap.authority_policy_version,
                bootstrap.claim_policy_version,
                "2026-01-01T00:00:00Z",
                bytes.fromhex(verification.bootstrap_digest),
                bytes.fromhex(bootstrap.database_identity_digest),
                metadata_json,
                hashlib.sha256(metadata_json).digest(),
                1,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    journal.touch()
    return database, journal


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
        assert connection.execute("PRAGMA trusted_schema").fetchone()[0] == 0
        assert evidence.database_openable is True
        assert evidence.database_state is SqliteDatabaseState.PRECREATED_UNINITIALIZED
        assert evidence.attached_database_count == 1
        assert evidence.persistent_journal_present is True
        assert evidence.trusted_schema_off is True
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
        assert database.read_bytes() == before_bytes
    finally:
        connection.close()


def test_installed_read_only_validation_proves_trusted_schema_off(
    tmp_path: Path,
) -> None:
    connection, database, journal = _fresh_database(tmp_path)
    connection.close()
    read_only = open_read_only_sqlite_connection(database)
    try:
        read_only.execute("PRAGMA trusted_schema = ON")
        assert read_only.execute("PRAGMA trusted_schema").fetchone()[0] == 1
        evidence = validate_installed_sqlite_prerequisites(
            read_only, database_path=database, journal_path=journal
        )
        assert read_only.execute("PRAGMA trusted_schema").fetchone()[0] == 0
        assert evidence.trusted_schema_off is True
    finally:
        read_only.close()


@pytest.mark.parametrize("validation_kind", ["installed", "runtime"])
def test_sqlite_evidence_fails_closed_when_trusted_schema_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    validation_kind: str,
) -> None:
    import trading_bot.runtime.windows_authority_sqlite as sqlite_runtime

    def fail_setup(connection: sqlite3.Connection) -> None:
        raise SchemaValidationError("trusted-schema setup failed")

    monkeypatch.setattr(sqlite_runtime, "configure_trusted_schema_off", fail_setup)
    connection, database, journal = _fresh_database(tmp_path)
    try:
        validator = (
            validate_installed_sqlite_prerequisites
            if validation_kind == "installed"
            else configure_and_validate_authority_sqlite_connection
        )
        with pytest.raises(SqliteDurabilityError, match="trusted-schema setup failed"):
            validator(connection, database_path=database, journal_path=journal)
    finally:
        connection.close()


@pytest.mark.parametrize("validation_kind", ["installed", "runtime"])
def test_sqlite_evidence_rejects_trusted_schema_remaining_on(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    validation_kind: str,
) -> None:
    import trading_bot.runtime.windows_authority_sqlite as sqlite_runtime

    monkeypatch.setattr(sqlite_runtime, "configure_trusted_schema_off", lambda _: None)
    connection, database, journal = _fresh_database(tmp_path)
    try:
        connection.execute("PRAGMA trusted_schema = ON")
        assert connection.execute("PRAGMA trusted_schema").fetchone()[0] == 1
        validator = (
            validate_installed_sqlite_prerequisites
            if validation_kind == "installed"
            else configure_and_validate_authority_sqlite_connection
        )
        with pytest.raises(SqliteDurabilityError, match="trusted_schema is not OFF"):
            validator(connection, database_path=database, journal_path=journal)
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


def _create_populated_database(tmp_path: Path) -> tuple[Path, Path]:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "authority.sqlite3-journal"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE disposable_data(value TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO disposable_data(value) VALUES (?)",
            ((f"value-{index}",) for index in range(256)),
        )
        connection.commit()
    finally:
        connection.close()
    journal.touch()
    return database, journal


def test_installed_validation_rejects_populated_non_authority_database(
    tmp_path: Path,
) -> None:
    database, journal = _create_populated_database(tmp_path)
    connection = open_read_only_sqlite_connection(database)
    try:
        with pytest.raises(SqliteDurabilityError):
            validate_installed_sqlite_prerequisites(
                connection, database_path=database, journal_path=journal
            )
    finally:
        connection.close()


def test_installed_validation_rejects_matching_metadata_only_database(
    tmp_path: Path,
) -> None:
    database, journal = _metadata_database(tmp_path, _verification())
    before_bytes = database.read_bytes()
    connection = open_read_only_sqlite_connection(database)
    try:
        with pytest.raises(SqliteDurabilityError, match="unsupported"):
            validate_installed_sqlite_prerequisites(
                connection, database_path=database, journal_path=journal
            )
    finally:
        connection.close()
    assert database.read_bytes() == before_bytes


def test_installed_validation_rejects_unapproved_legacy_schema(
    tmp_path: Path,
) -> None:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "authority.sqlite3-journal"
    connection = sqlite3.connect(database)
    try:
        # A minimal legacy marker is sufficient for the rejection contract;
        # this test must not maintain a second authority SQL schema.
        connection.execute(
            "CREATE TABLE legacy_authority_marker (marker TEXT NOT NULL)"
        )
        connection.commit()
    finally:
        connection.close()
    journal.touch()
    connection = open_read_only_sqlite_connection(database)
    try:
        with pytest.raises(SqliteDurabilityError, match="unsupported"):
            validate_installed_sqlite_prerequisites(
                connection, database_path=database, journal_path=journal
            )
    finally:
        connection.close()


def _corrupt_later_btree_page(database: Path) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA page_size = 1024")
        connection.execute("CREATE TABLE disposable_data(value TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO disposable_data(value) VALUES (?)",
            ((f"value-{index}",) for index in range(4096)),
        )
        connection.execute(
            "CREATE INDEX disposable_data_value_idx ON disposable_data(value)"
        )
        connection.commit()
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
    finally:
        connection.close()

    contents = bytearray(database.read_bytes())
    page_offset = next(
        (
            (page - 1) * page_size
            for page in range(2, page_count + 1)
            if contents[(page - 1) * page_size] in {0x02, 0x05, 0x0A, 0x0D}
        ),
        None,
    )
    assert page_offset is not None
    contents[page_offset] = 0
    database.write_bytes(contents)


def test_integrity_validation_rejects_corruption_in_a_later_database_page(
    tmp_path: Path,
) -> None:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "authority.sqlite3-journal"
    _corrupt_later_btree_page(database)
    journal.touch()
    before_bytes = database.read_bytes()
    connection = open_read_only_sqlite_connection(database)
    try:
        with pytest.raises(SqliteDurabilityError):
            validate_installed_sqlite_prerequisites(
                connection, database_path=database, journal_path=journal
            )
    finally:
        connection.close()
    assert database.read_bytes() == before_bytes


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
        lambda connection, *, database_path, journal_path: InstalledSqliteEvidence(
            database_path=str(database_path),
            journal_path=str(journal_path),
            database_openable=True,
            database_state=SqliteDatabaseState.PRECREATED_UNINITIALIZED,
            attached_database_count=1,
            persistent_journal_present=True,
            trusted_schema_off=True,
        ),
    )

    assert (
        provisioning._validate_database_if_present(True, True)
        is SqliteDatabaseState.PRECREATED_UNINITIALIZED
    )
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
        assert connection.execute("PRAGMA trusted_schema").fetchone()[0] == 0
        assert evidence.foreign_keys is True
        assert evidence.journal_mode == "persist"
        assert evidence.synchronous == 2
        assert evidence.trusted_schema_off is True
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
    import trading_bot.runtime.windows_authority_provisioning as provisioning

    assert provisioning._validate_database_if_present(False, False) == "NOT_PRESENT"
    with pytest.raises(WindowsAuthorityError):
        provisioning._validate_database_if_present(True, False)
    with pytest.raises(WindowsAuthorityError):
        provisioning._validate_database_if_present(False, True)
