"""D1Q fake-only boundary tests: no production credentials, storage or network."""

from __future__ import annotations

import ctypes
import json
import os
import socket
import sqlite3
import stat
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.review_paper.test_armed_production_paper_session import (  # noqa: F401
    AlpacaTransport,
    Clock,
    harness,
    run,
)
from tests.review_paper.test_store import _intent, _review

from trading_bot.review_paper import alpaca_windows_credentials as creds
from trading_bot.review_paper import armed_session_host as host
from trading_bot.review_paper import production_paper_runtime as runtime
from trading_bot.review_paper.armed_session_store import ArmedSessionStore
from trading_bot.review_paper.store import ReviewPaperStore


@pytest.fixture
def paths(tmp_path, monkeypatch):
    root = tmp_path / "Arch134D1"
    monkeypatch.setattr(runtime, "RUNTIME_ROOT", root)
    monkeypatch.setattr(runtime, "PAPER_PATH", root / "paper.sqlite")
    monkeypatch.setattr(runtime, "SESSION_PATH", root / "armed-sessions.sqlite")
    return root


@pytest.fixture
def fixed_reader(monkeypatch):
    calls, blobs = [], []
    values = [b"fake-KEY", b"fake-SECRET"]

    class Reader:
        def read_fixed(self, target):
            calls.append(target)
            value = values[len(calls) - 1]
            if isinstance(value, Exception):
                raise value
            blob = None if value is None else bytearray(value)
            blobs.append(blob)
            return blob

    monkeypatch.setattr(creds, "_WindowsCredentialReader", Reader)
    return SimpleNamespace(calls=calls, blobs=blobs, values=values)


def test_pair_fixed_reads_redacted_and_mutable_storage_cleared(fixed_reader):
    f = fixed_reader
    with creds.read_current_product_alpaca_secrets() as pair:
        assert "fake" not in str(pair) + repr(pair)
        assert pair.use(lambda key, secret: (key, secret)) == (
            "fake-KEY",
            "fake-SECRET",
        )
        assert all(blob == bytearray(len(blob)) for blob in f.blobs)
    assert f.calls == [creds.API_KEY_TARGET, creds.API_SECRET_TARGET]
    with pytest.raises(creds.AlpacaCredentialReadError, match="scope closed"):
        pair.use(lambda *_: None)


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "value",
    [
        None,
        b"",
        b" ",
        b" secret",
        b"secret ",
        b"s\r",
        b"s\n",
        b"s\0",
        b"\xff",
        b"x" * 1025,
        OSError("fake-SECRET"),
    ],
)
def test_pair_invalid_and_native_failures_sanitized_cleanup(fixed_reader, index, value):
    f = fixed_reader
    f.values[index] = value
    with pytest.raises(creds.AlpacaCredentialReadError) as error:
        creds.read_current_product_alpaca_secrets()
    assert "fake-SECRET" not in str(error.value)
    assert all(blob is None or not any(blob) for blob in f.blobs)


def test_consumer_failure_sanitized(fixed_reader):
    with creds.read_current_product_alpaca_secrets() as pair:
        with pytest.raises(creds.AlpacaCredentialReadError) as error:
            pair.use(lambda *_: (_ for _ in ()).throw(ValueError("fake-SECRET")))
    assert "fake-SECRET" not in str(error.value)


def native_reader(*, target=None, kind=1, persist=2, size=11, fault=None):
    class Record(ctypes.Structure):
        _fields_ = [
            ("TargetName", ctypes.c_wchar_p),
            ("Type", ctypes.c_uint32),
            ("Persist", ctypes.c_uint32),
            ("CredentialBlobSize", ctypes.c_uint32),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ]

    buffer = (ctypes.c_ubyte * max(size, 1))(*([65] * max(size, 1)))
    record = Record(target or creds.API_KEY_TARGET, kind, persist, size, buffer)
    pointer = ctypes.pointer(record)
    freed, zeros = [], []

    def read(name, typ, flags, output):
        assert name == creds.API_KEY_TARGET and typ == 1 and flags == 0
        ctypes.cast(output, ctypes.POINTER(ctypes.POINTER(Record)))[0] = pointer
        if fault == "read":
            raise OSError("fake-SECRET")
        return True

    def free(ptr):
        freed.append(True)
        if fault == "free":
            raise OSError("fake-SECRET")

    def zero(address, length):
        zeros.append(length)
        if fault == "zero":
            raise OSError("fake-SECRET")
        ctypes.memset(address, 0, length)

    reader = creds._WindowsCredentialReader.__new__(creds._WindowsCredentialReader)
    reader._credential = Record
    reader._api = SimpleNamespace(CredReadW=read, CredFree=free)
    reader._zero_memory = zero
    return reader, buffer, freed, zeros


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": 2},
        {"persist": 1},
        {"target": "arbitrary"},
        {"size": 0},
        {"size": 1025},
        {"size": 2561},
        {"fault": "read"},
        {"fault": "free"},
        {"fault": "zero"},
    ],
)
def test_native_metadata_range_and_cleanup_fail_closed(changes):
    reader, buffer, freed, zeros = native_reader(**changes)
    with pytest.raises(creds.AlpacaCredentialReadError) as error:
        reader.read_fixed(creds.API_KEY_TARGET)
    assert freed == [True]
    assert "fake-SECRET" not in str(error.value)
    if 0 < changes.get("size", 11) <= 2560 and changes.get("fault") != "zero":
        assert not any(buffer)


def test_native_copy_zero_before_free_and_no_arbitrary_targets():
    reader, buffer, freed, zeros = native_reader()
    assert reader.read_fixed(creds.API_KEY_TARGET) == bytearray(b"A" * 11)
    assert zeros == [11] and freed == [True] and not any(buffer)
    with pytest.raises(creds.AlpacaCredentialReadError):
        reader.read_fixed("arbitrary")
    assert freed == [True]


def test_no_environment_fallback(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", "fake-KEY")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "fake-SECRET")
    monkeypatch.setattr(
        creds,
        "_WindowsCredentialReader",
        lambda: (_ for _ in ()).throw(OSError("fake-SECRET")),
    )
    with pytest.raises(creds.AlpacaCredentialReadError):
        creds.read_current_product_alpaca_secrets()


def test_exact_existing_provider_composition_no_request(fixed_reader, monkeypatch):
    monkeypatch.setattr(
        host,
        "read_current_product_alpaca_secrets",
        creds.read_current_product_alpaca_secrets,
    )
    provider = host.create_current_product_alpaca_provider()
    assert type(provider) is host.AlpacaDailySnapshotProvider
    assert type(provider._transport) is host.StdlibAlpacaHistoricalBarsTransport
    assert fixed_reader.calls == [creds.API_KEY_TARGET, creds.API_SECRET_TARGET]
    assert "fake" not in repr(provider)


def test_reservation_before_composition_and_four_reads(harness):  # noqa: F811
    h = harness
    original = h.kwargs["alpaca_provider"]
    composed = []

    def provider():
        with sqlite3.connect(h.kwargs["session_store"].path) as connection:
            rows = connection.execute(
                "SELECT evidence FROM armed_session_v1"
            ).fetchall()
        assert len(rows) == 1
        assert json.loads(rows[0][0])["status"] == "ADMITTED"
        composed.append(True)
        return original()

    result = run(h, alpaca_provider=provider)
    assert result["status"] == "PAPER_EXECUTED"
    assert composed == [True] and len(h.transport.calls) == 4


def test_absent_preflight_no_writes_or_reads(paths, monkeypatch):
    monkeypatch.setattr(
        runtime,
        "read_current_product_alpaca_secrets",
        lambda: pytest.fail("credential read"),
    )
    monkeypatch.setattr(
        runtime, "persisted_oauth_availability", lambda: pytest.fail("OAuth read")
    )
    result = runtime.preflight_runtime()
    assert result["status"] == "ABSENT" and not paths.exists()
    assert all(
        value == 0
        for key, value in result.items()
        if key.endswith(("reads", "calls", "mutations", "writes"))
    )


def test_fresh_exact_empty_stores_and_idempotent_readonly_preflight(paths):
    assert runtime.provision_runtime()["runtime_status"] == "PROVISIONED"
    assert {p.name for p in paths.iterdir()} == {
        "paper.sqlite",
        "armed-sessions.sqlite",
    }
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.iterdir()}
    assert runtime.preflight_runtime()["status"] == "PRESENT_COMPATIBLE"
    assert runtime.provision_runtime() == {
        "runtime_status": "ALREADY_PROVISIONED",
        "paper_records": 0,
        "session_reservations": 0,
    }
    assert before == {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.iterdir()
    }
    assert ArmedSessionStore(runtime.SESSION_PATH).qualify() == 0


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE metadata SET value='1' WHERE key='schema_version'",
        "UPDATE metadata SET value='9999' WHERE key='starting_cash'",
        "DELETE FROM metadata",
        "CREATE TABLE unexpected (x TEXT)",
        "DROP TABLE review_fills",
    ],
)
def test_incompatible_paper_never_reinitialized(paths, sql):
    runtime.provision_runtime()
    with sqlite3.connect(runtime.PAPER_PATH) as connection:
        connection.execute(sql)
    before = runtime.PAPER_PATH.read_bytes()
    assert runtime.preflight_runtime()["status"] == "BLOCKED"
    with pytest.raises(ValueError):
        runtime.provision_runtime()
    assert runtime.PAPER_PATH.read_bytes() == before


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE armed_session_v1",
        "CREATE TABLE unexpected (x TEXT)",
        "INSERT INTO armed_session_v1 VALUES ('fake', X'7b7d')",
    ],
)
def test_session_exact_schema_and_canonical_evidence(paths, sql):
    runtime.provision_runtime()
    with sqlite3.connect(runtime.SESSION_PATH) as connection:
        connection.execute(sql)
    before = runtime.SESSION_PATH.read_bytes()
    assert runtime.preflight_runtime()["status"] == "BLOCKED"
    with pytest.raises(ValueError):
        ArmedSessionStore(runtime.SESSION_PATH).initialize()
    assert runtime.SESSION_PATH.read_bytes() == before


def test_existing_nonempty_paper_preserved_with_bounded_counts(paths):
    runtime.provision_runtime()
    store = ReviewPaperStore(runtime.PAPER_PATH, starting_cash=Decimal("10000"))
    store.record_market_review(_intent(), _review())
    before = runtime.PAPER_PATH.read_bytes()
    result = runtime.provision_runtime()
    assert (
        result["runtime_status"] == "ALREADY_PROVISIONED"
        and result["paper_records"] == 1
    )
    assert runtime.PAPER_PATH.read_bytes() == before


@pytest.mark.parametrize("extra", ["unexpected", "paper.sqlite-wal", "no-pycache"])
def test_unexpected_runtime_contents_preserved_and_blocked(paths, extra):
    runtime.provision_runtime()
    (paths / extra).write_bytes(b"preserve")
    assert runtime.preflight_runtime()["status"] == "BLOCKED"
    with pytest.raises(ValueError):
        runtime.provision_runtime()
    assert (paths / extra).read_bytes() == b"preserve"


def test_incomplete_existing_directory_never_repaired(paths):
    paths.mkdir()
    with pytest.raises(ValueError):
        runtime.provision_runtime()
    assert list(paths.iterdir()) == []


def test_no_alternate_path(paths, monkeypatch):
    monkeypatch.setattr(runtime, "PAPER_PATH", paths / "alternate.sqlite")
    assert runtime.preflight_runtime()["status"] == "BLOCKED"
    assert not paths.exists()


@pytest.mark.parametrize(
    "mode",
    [
        "--runtime-root",
        "--provider",
        "--symbol",
        "--target-session",
        "--quantity",
        "--side",
        "--price",
    ],
)
def test_cli_rejects_semantics_and_runtime_paths(mode):
    with pytest.raises(ValueError):
        runtime.build_parser().parse_args(
            [
                "--expected-head",
                "a" * 40,
                "--expected-tree",
                "b" * 40,
                "--preflight",
                mode,
                "value",
            ]
        )


def cli_args(*extra):
    return ["--expected-head", "a" * 40, "--expected-tree", "b" * 40, *extra]


def deny_probe(monkeypatch, path, fault):
    """Inject VFS failures only on the existing-file native write connection."""
    connect = sqlite3.connect
    statements = []
    uri = path.resolve().as_uri()

    class Connection:
        def __init__(self, real):
            self.real = real
            self.wrote = False

        @property
        def in_transaction(self):
            return self.real.in_transaction

        def execute(self, sql, parameters=()):
            statements.append(sql)
            if (
                (fault == "begin" and sql == "BEGIN IMMEDIATE")
                or (fault in {"write", "journal"} and sql.startswith("INSERT"))
                or (fault == "rollback" and sql == "ROLLBACK")
            ):
                error = sqlite3.OperationalError("PRIVATE USER SID ACL PATH SECRET")
                error.sqlite_errorcode = (
                    sqlite3.SQLITE_READONLY
                    if fault == "write"
                    else sqlite3.SQLITE_IOERR
                )
                raise error
            if fault == "rollback_noop" and sql == "ROLLBACK":
                return self.real.execute("SELECT 1")
            cursor = self.real.execute(sql, parameters)
            if sql.startswith("INSERT"):
                self.wrote = True
            if (
                fault == "readback"
                and self.wrote
                and sql.startswith("SELECT")
                and parameters
            ):
                return SimpleNamespace(fetchone=lambda: ("wrong",))
            return cursor

        def close(self):
            self.real.close()

    def open_connection(database, *args, **kwargs):
        if database == uri + "?mode=rw":
            if fault == "readonly":
                database = uri + "?mode=ro"
            return Connection(connect(database, *args, **kwargs))
        if fault == "postcheck" and database == uri + "?mode=ro":
            raise sqlite3.OperationalError("PRIVATE USER SID ACL PATH SECRET")
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(runtime.sqlite3, "connect", open_connection)
    return statements


@pytest.mark.parametrize("store", ["paper", "session"])
@pytest.mark.parametrize(
    "fault",
    [
        "readonly",
        "begin",
        "write",
        "journal",
        "readback",
        "rollback",
        "rollback_noop",
        "postcheck",
    ],
)
def test_qualification_write_failure_blocks_without_semantic_mutation(
    paths, fixed_reader, monkeypatch, tmp_path, capsys, store, fault
):
    runtime.provision_runtime()
    before = {p.name: p.read_bytes() for p in paths.iterdir()}
    path = runtime.PAPER_PATH if store == "paper" else runtime.SESSION_PATH
    statements = deny_probe(monkeypatch, path, fault)
    monkeypatch.setattr(runtime, "_admit_source", lambda *_: ())
    monkeypatch.setattr(
        runtime,
        "persisted_oauth_availability",
        lambda: pytest.fail("OAuth after failed probe"),
    )
    evidence = tmp_path / "write-evidence.json"
    assert (
        runtime.main(
            cli_args(
                "--qualify", runtime.QUALIFY_INTERLOCK, "--evidence", str(evidence)
            )
        )
        == 3
    )
    result = json.loads(evidence.read_bytes())
    assert result["status"] == "BLOCKED"
    assert result[f"{store}_store_write_readiness"] == "BLOCKED"
    other = "session" if store == "paper" else "paper"
    assert result[f"{other}_store_write_readiness"] == "WRITE_READY"
    assert fixed_reader.calls == []
    assert result["paper_records"] == result["session_reservations"] == 0
    assert all(
        result[k] == 0
        for k in (
            "alpaca_http_calls",
            "robinhood_application_calls",
            "paper_trade_mutations",
            "scheduler_mutations",
            "broker_mutations",
        )
    )
    if fault == "write":
        assert (
            statements.index("BEGIN IMMEDIATE")
            < next(i for i, sql in enumerate(statements) if sql.startswith("INSERT"))
            < statements.index("ROLLBACK")
        )
    assert before == {p.name: p.read_bytes() for p in paths.iterdir()}
    assert "PRIVATE" not in evidence.read_text() + capsys.readouterr().out


@pytest.mark.skipif(os.name != "nt", reason="native Windows read-only file attribute")
@pytest.mark.parametrize("store", ["paper", "session"])
def test_native_windows_readonly_store_is_readable_but_not_write_ready(paths, store):
    runtime.provision_runtime()
    path = runtime.PAPER_PATH if store == "paper" else runtime.SESSION_PATH
    before = {p.name: p.read_bytes() for p in paths.iterdir()}
    # Test-only file attributes; no ACL/security API and no production path.
    path.chmod(stat.S_IREAD)
    try:
        assert runtime.preflight_runtime()["status"] == "PRESENT_COMPATIBLE"
        result = runtime.qualify_runtime_write_readiness()
        assert result[f"{store}_store_write_readiness"] == "BLOCKED"
        other = "session" if store == "paper" else "paper"
        assert result[f"{other}_store_write_readiness"] == "WRITE_READY"
        assert before == {p.name: p.read_bytes() for p in paths.iterdir()}
    finally:
        path.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_both_native_journals_readback_rollback_and_independent_reopen(
    paths, monkeypatch
):
    runtime.provision_runtime()
    before = {p.name: p.read_bytes() for p in paths.iterdir()}
    connect = sqlite3.connect
    events = []

    class Connection:
        def __init__(self, real, path):
            self.real, self.path = real, path

        @property
        def in_transaction(self):
            return self.real.in_transaction

        def execute(self, sql, parameters=()):
            cursor = self.real.execute(sql, parameters)
            if sql.startswith("INSERT"):
                assert Path(str(self.path) + "-journal").stat().st_size > 0
                events.append((self.path.name, "journal"))
            if sql == "ROLLBACK":
                events.append((self.path.name, "rollback"))
            assert sql != "COMMIT"
            return cursor

        def close(self):
            self.real.close()

    def open_connection(database, *args, **kwargs):
        real = connect(database, *args, **kwargs)
        for path in (runtime.PAPER_PATH, runtime.SESSION_PATH):
            if database == path.resolve().as_uri() + "?mode=rw":
                return Connection(real, path)
            if database == path.resolve().as_uri() + "?mode=ro":
                assert (path.name, "rollback") in events
                events.append((path.name, "reopen"))
        return real

    monkeypatch.setattr(runtime.sqlite3, "connect", open_connection)
    assert runtime.qualify_runtime_write_readiness() == {
        "paper_store_write_readiness": "WRITE_READY",
        "session_store_write_readiness": "WRITE_READY",
    }
    assert events == [
        (name, phase)
        for name in ("paper.sqlite", "armed-sessions.sqlite")
        for phase in ("journal", "rollback", "reopen")
    ]
    assert before == {p.name: p.read_bytes() for p in paths.iterdir()}
    state = runtime.preflight_runtime()
    assert state["paper_records"] == state["session_reservations"] == 0
    assert state["paper_store_write_readiness"] == "NOT_CHECKED"


@pytest.mark.parametrize("store", ["paper", "session"])
def test_write_probe_lock_contention_blocks(paths, store):
    runtime.provision_runtime()
    path = runtime.PAPER_PATH if store == "paper" else runtime.SESSION_PATH
    with sqlite3.connect(path) as lock:
        lock.execute("BEGIN IMMEDIATE")
        result = runtime.qualify_runtime_write_readiness()
        assert result[f"{store}_store_write_readiness"] == "BLOCKED"
        lock.rollback()
    assert runtime.preflight_runtime()["session_reservations"] == 0


@pytest.mark.parametrize("store", ["paper", "session"])
def test_incompatible_journal_mode_is_preserved_not_repaired(paths, store):
    runtime.provision_runtime()
    path = runtime.PAPER_PATH if store == "paper" else runtime.SESSION_PATH
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    before = path.read_bytes()
    assert (
        runtime.qualify_runtime_write_readiness()[f"{store}_store_write_readiness"]
        == "BLOCKED"
    )
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "readiness",
    [
        {},
        {"paper_store_write_readiness": "WRITE_READY"},
        {"session_store_write_readiness": "WRITE_READY"},
        {
            "paper_store_write_readiness": "WRITE_READY",
            "session_store_write_readiness": "NOT_CHECKED",
        },
    ],
)
def test_ready_requires_complete_both_store_evidence(
    paths, fixed_reader, monkeypatch, tmp_path, readiness
):
    monkeypatch.setattr(runtime, "_admit_source", lambda *_: ())
    monkeypatch.setattr(runtime, "qualify_runtime_write_readiness", lambda: readiness)
    evidence = tmp_path / "out.json"
    assert (
        runtime.main(
            cli_args(
                "--qualify", runtime.QUALIFY_INTERLOCK, "--evidence", str(evidence)
            )
        )
        == 3
    )
    assert json.loads(evidence.read_bytes())["status"] == "BLOCKED"
    assert fixed_reader.calls == []


def host_startup(monkeypatch, paths):
    # Redirect only the fixed namespace to isolated test storage; keep the real
    # host composition, store constructors, controller and provider factory.
    for name in ("RUNTIME_ROOT", "PAPER_PATH", "SESSION_PATH"):
        monkeypatch.setattr(host, name, getattr(runtime, name))
    monkeypatch.setattr(host, "admit_armed_session_host", lambda *_: ())
    clock = Clock()

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=UTC):
            return clock.at.astimezone(tz)

    monkeypatch.setattr(host, "datetime", FixedDateTime)
    return clock


@pytest.mark.parametrize("store", ["paper", "session"])
def test_fixed_host_main_stops_before_reservation_and_provider_on_readonly(
    paths, fixed_reader, monkeypatch, tmp_path, capsys, store
):
    runtime.provision_runtime()
    host_startup(monkeypatch, paths)
    before = {p.name: p.read_bytes() for p in paths.iterdir()}
    deny_probe(
        monkeypatch,
        runtime.PAPER_PATH if store == "paper" else runtime.SESSION_PATH,
        "write",
    )
    monkeypatch.setattr(
        host,
        "create_current_product_alpaca_provider",
        lambda: pytest.fail("Alpaca composition"),
    )
    monkeypatch.setattr(
        host,
        "create_current_product_quote_adapter",
        lambda: pytest.fail("Robinhood composition"),
    )
    assert (
        host.main(
            cli_args(
                "--arm",
                host.ARM_INTERLOCK,
                "--evidence",
                str(tmp_path / "session.json"),
            )
        )
        == 3
    )
    result = json.loads(capsys.readouterr().err)
    assert result["status"] == "BLOCKED"
    assert result[f"{store}_store_write_readiness"] == "BLOCKED"
    assert fixed_reader.calls == []
    assert before == {p.name: p.read_bytes() for p in paths.iterdir()}
    assert not (tmp_path / "session.json").exists()


def test_fixed_host_main_composes_provider_only_after_write_ready_and_reservation(
    paths, fixed_reader, monkeypatch, tmp_path, capsys
):
    runtime.provision_runtime()
    clock = host_startup(monkeypatch, paths)
    # A real no-signal strategy path avoids any quote or synthetic execution.
    transport = AlpacaTransport(closes=(10, 10, 12, 9))

    def compose_transport():
        assert ArmedSessionStore(runtime.SESSION_PATH).qualify() == 1
        assert runtime.preflight_runtime()["paper_records"] == 0
        return transport

    monkeypatch.setattr(host, "StdlibAlpacaHistoricalBarsTransport", compose_transport)
    monkeypatch.setattr(
        host,
        "create_current_product_quote_adapter",
        lambda: pytest.fail("NO_SIGNAL quote"),
    )
    monkeypatch.setattr(host.time, "sleep", clock.sleep)
    assert (
        host.main(
            cli_args(
                "--arm",
                host.ARM_INTERLOCK,
                "--evidence",
                str(tmp_path / "session.json"),
            )
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "NO_SIGNAL"
    assert len(transport.calls) == 4
    assert fixed_reader.calls == [creds.API_KEY_TARGET, creds.API_SECRET_TARGET]
    assert ArmedSessionStore(runtime.SESSION_PATH).qualify() == 1
    assert runtime.preflight_runtime()["paper_records"] == 0


def test_fixed_host_main_preflight_is_readonly_not_write_qualified(
    paths, fixed_reader, monkeypatch, tmp_path, capsys
):
    runtime.provision_runtime()
    host_startup(monkeypatch, paths)
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.iterdir()}
    monkeypatch.setattr(
        host, "qualify_runtime_write_readiness", lambda: pytest.fail("preflight writes")
    )
    assert (
        host.main(cli_args("--preflight", "--evidence", str(tmp_path / "session.json")))
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "RUNTIME_COMPATIBLE"
    assert (
        result["paper_store_write_readiness"]
        == result["session_store_write_readiness"]
        == "NOT_CHECKED"
    )
    assert fixed_reader.calls == []
    assert before == {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.iterdir()
    }


@pytest.mark.parametrize(
    "flags",
    [
        ["--arm", host.ARM_INTERLOCK, "--recover-history", host.RECOVERY_INTERLOCK],
        ["--preflight", "--recover-history", host.RECOVERY_INTERLOCK],
        ["--recover-history", host.RECOVERY_INTERLOCK],
        ["--arm", host.ARM_INTERLOCK, "--predecessor-execute-evidence", "unused.json"],
        ["--recover-history", "yes"],
    ],
)
def test_d1r2_cli_interlock_exclusion_before_source_or_effects(
    monkeypatch, tmp_path, flags
):
    monkeypatch.setattr(
        host, "admit_armed_session_host", lambda *_: pytest.fail("source access")
    )
    assert host.main(cli_args("--evidence", str(tmp_path / "out.json"), *flags)) == 3


def test_d1r2_host_routes_recovery_separate_from_arm_with_no_real_edges(
    paths, monkeypatch, tmp_path, capsys
):
    runtime.provision_runtime()
    host_startup(monkeypatch, paths)
    observed = []

    def recovery_controller(**kwargs):
        observed.append(kwargs)
        assert kwargs["arm_interlock"] is None
        assert kwargs["recovery_interlock"] == host.RECOVERY_INTERLOCK
        assert (
            kwargs["predecessor_execute_evidence_path"] == tmp_path / "old.execute.json"
        )
        return {"status": "NO_SIGNAL"}

    monkeypatch.setattr(host, "run_armed_production_paper_session", recovery_controller)
    monkeypatch.setattr(
        host,
        "create_current_product_alpaca_provider",
        lambda: pytest.fail("real credential/provider"),
    )
    monkeypatch.setattr(
        host,
        "create_current_product_quote_adapter",
        lambda: pytest.fail("real Robinhood"),
    )
    assert (
        host.main(
            cli_args(
                "--evidence",
                str(tmp_path / "new.json"),
                "--recover-history",
                host.RECOVERY_INTERLOCK,
                "--predecessor-execute-evidence",
                str(tmp_path / "old.execute.json"),
            )
        )
        == 0
    )
    assert (
        len(observed) == 1
        and json.loads(capsys.readouterr().out)["status"] == "NO_SIGNAL"
    )


def test_cli_preflight_completely_effect_free(paths, monkeypatch, capsys):
    monkeypatch.setattr(runtime, "_admit_source", lambda *_: ())
    monkeypatch.setattr(runtime, "provision_runtime", lambda: pytest.fail("provision"))
    monkeypatch.setattr(
        runtime,
        "read_current_product_alpaca_secrets",
        lambda: pytest.fail("credential"),
    )
    monkeypatch.setattr(
        runtime, "persisted_oauth_availability", lambda: pytest.fail("OAuth")
    )
    assert runtime.main(cli_args("--preflight")) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ABSENT"
    assert not paths.exists()


@pytest.mark.parametrize("available", [True, False])
def test_protected_fake_qualification_only_fixed_readiness(
    paths, fixed_reader, monkeypatch, tmp_path, capsys, available
):
    calls = []

    def forbid_network(*args, **kwargs):
        pytest.fail("qualification network effect")

    monkeypatch.setattr(socket, "create_connection", forbid_network)
    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    monkeypatch.setattr(runtime, "_admit_source", lambda *_: ())
    monkeypatch.setattr(
        runtime,
        "read_current_product_alpaca_secrets",
        creds.read_current_product_alpaca_secrets,
    )

    def oauth():
        calls.extend(["token", "client"])
        return SimpleNamespace(
            persisted_oauth_available=available, oauth_storage_reads=2
        )

    monkeypatch.setattr(runtime, "persisted_oauth_availability", oauth)
    evidence = tmp_path / "evidence.json"
    assert runtime.main(
        cli_args("--qualify", runtime.QUALIFY_INTERLOCK, "--evidence", str(evidence))
    ) == (0 if available else 3)
    result = json.loads(evidence.read_bytes())
    assert result["status"] == (
        "READY_FOR_MANUAL_PAPER_SESSION" if available else "BLOCKED"
    )
    assert fixed_reader.calls == [creds.API_KEY_TARGET, creds.API_SECRET_TARGET]
    assert calls == ["token", "client"] and result["robinhood_credential_reads"] == 2
    assert result["alpaca_credential_reads"] == 2 and result["effect_counts_complete"]
    assert result["paper_store_write_readiness"] == "WRITE_READY"
    assert result["session_store_write_readiness"] == "WRITE_READY"
    assert all(
        result[key] == 0
        for key in (
            "alpaca_http_calls",
            "robinhood_application_calls",
            "paper_trade_mutations",
            "scheduler_mutations",
            "broker_mutations",
        )
    )
    assert (
        len(evidence.read_bytes()) < 4096
        and "fake-" not in evidence.read_text() + capsys.readouterr().out
    )
    assert runtime.preflight_runtime()["session_reservations"] == 0
    assert runtime.preflight_runtime()["paper_records"] == 0


def test_invalid_interlock_and_evidence_stop_before_protected_effects(
    paths, fixed_reader, monkeypatch, tmp_path
):
    monkeypatch.setattr(runtime, "_admit_source", lambda *_: ())
    assert (
        runtime.main(cli_args("--qualify", "yes", "--evidence", str(tmp_path / "out")))
        == 3
    )
    assert (
        runtime.main(cli_args("--preflight", "--evidence", str(tmp_path / "out"))) == 3
    )
    assert not paths.exists() and fixed_reader.calls == []


def test_credential_failure_sanitized_evidence_with_unknown_counts(
    paths, fixed_reader, monkeypatch, tmp_path
):
    monkeypatch.setattr(runtime, "_admit_source", lambda *_: ())
    monkeypatch.setattr(
        runtime,
        "read_current_product_alpaca_secrets",
        creds.read_current_product_alpaca_secrets,
    )
    monkeypatch.setattr(
        runtime,
        "persisted_oauth_availability",
        lambda: pytest.fail("OAuth after failure"),
    )
    fixed_reader.values[1] = OSError("fake-SECRET")
    evidence = tmp_path / "out.json"
    assert (
        runtime.main(
            cli_args(
                "--qualify", runtime.QUALIFY_INTERLOCK, "--evidence", str(evidence)
            )
        )
        == 3
    )
    result = json.loads(evidence.read_bytes())
    assert result["status"] == "BLOCKED" and result["alpaca_credential_reads"] is None
    assert (
        not result["effect_counts_complete"]
        and "fake-SECRET" not in evidence.read_text()
    )


def test_registration_source_only_and_authority():
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    assert runner._arch134_production_paper_runtime_authority_check(root) == ()
    spec = runner._checkpoint_specs()[runner.ARCH134_PRODUCTION_PAPER_RUNTIME_NAME]
    assert spec.preflight is spec.execute is None
    assert runner.ACTIVE_CI_CHECKPOINTS[-2:] == (
        spec.name,
        runner.ARCH134_RUNTIME_ACL_NAME,
    )
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), host.BRANCH, "push")
        == spec.name
    )
    assert runner.CI_CERTIFICATION_PROFILES[spec.name] == "robinhood"


@pytest.mark.parametrize("which", ["root", "parent", "paper"])
def test_reparse_metadata_rejected_before_store_reads(paths, monkeypatch, which):
    runtime.provision_runtime()
    target = {"root": paths, "parent": paths.parent, "paper": runtime.PAPER_PATH}[which]
    original = Path.lstat

    def redirected(path):
        value = original(path)
        if path == target:
            return SimpleNamespace(
                st_mode=value.st_mode, st_nlink=value.st_nlink, st_file_attributes=1024
            )
        return value

    monkeypatch.setattr(Path, "lstat", redirected)
    assert runtime.preflight_runtime()["status"] == "BLOCKED"


def test_hardlinked_store_rejected(paths, monkeypatch):
    runtime.provision_runtime()
    original = Path.lstat

    def linked(path):
        value = original(path)
        if path == runtime.PAPER_PATH:
            return SimpleNamespace(
                st_mode=value.st_mode, st_nlink=2, st_file_attributes=0
            )
        return value

    monkeypatch.setattr(Path, "lstat", linked)
    assert runtime.preflight_runtime()["status"] == "BLOCKED"


def test_existing_session_and_fill_preserved(paths, harness):  # noqa: F811
    runtime.provision_runtime()
    result = run(harness)
    assert result["status"] == "PAPER_EXECUTED"
    runtime.PAPER_PATH.write_bytes(harness.store.path.read_bytes())
    runtime.SESSION_PATH.write_bytes(harness.kwargs["session_store"].path.read_bytes())
    before = {p.name: p.read_bytes() for p in paths.iterdir()}
    state = runtime.provision_runtime()
    assert state == {
        "runtime_status": "ALREADY_PROVISIONED",
        "paper_records": 1,
        "session_reservations": 1,
    }
    assert before == {p.name: p.read_bytes() for p in paths.iterdir()}
    assert runtime.qualify_runtime_write_readiness() == {
        "paper_store_write_readiness": "WRITE_READY",
        "session_store_write_readiness": "WRITE_READY",
    }
    assert before == {p.name: p.read_bytes() for p in paths.iterdir()}


def test_source_rejection_before_any_qualification_effect(
    paths, fixed_reader, monkeypatch, tmp_path
):
    monkeypatch.setattr(
        runtime,
        "_admit_source",
        lambda *_: (_ for _ in ()).throw(ValueError("untrusted")),
    )
    evidence = tmp_path / "out.json"
    assert (
        runtime.main(
            cli_args(
                "--qualify", runtime.QUALIFY_INTERLOCK, "--evidence", str(evidence)
            )
        )
        == 3
    )
    assert not evidence.exists() and not paths.exists() and fixed_reader.calls == []


def test_no_overwrite_existing_evidence(paths, fixed_reader, monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_admit_source", lambda *_: ())
    evidence = tmp_path / "out.json"
    evidence.write_bytes(b"preserve")
    assert (
        runtime.main(
            cli_args(
                "--qualify", runtime.QUALIFY_INTERLOCK, "--evidence", str(evidence)
            )
        )
        == 3
    )
    assert (
        evidence.read_bytes() == b"preserve"
        and not paths.exists()
        and fixed_reader.calls == []
    )


@pytest.mark.parametrize(
    "addition",
    [
        "import os\nos.environ['APCA_API_KEY_ID']\n",
        "import trading_bot.runtime.windows_effectful_capture_credentials\n",
        "def bad(reader):\n    reader.CredWriteW()\n",
        "def bad(reader):\n    reader.CredDeleteW()\n",
        "def bad(security):\n    security.SetNamedSecurityInfoW()\n",
        "def bad(security):\n    security.SetFileSecurityW()\n",
        "def bad(path):\n    path.chmod(0)\n",
        "def bad(client):\n    client.call_tool('x', {})\n",
        "def bad(client):\n    client.get_equity_historicals({})\n",
        "def bad(client):\n    client.place_equity_order({})\n",
        "def bad(client):\n    client.register_task({})\n",
        "import trading_bot.experiments\n",
    ],
)
def test_d1q_authority_rejects_forbidden_expansion_with_refreshed_pin(
    tmp_path, monkeypatch, addition
):
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    for relative in runner.ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((root / relative).read_text(encoding="utf-8"), encoding="utf-8")
    relative = "src/trading_bot/review_paper/production_paper_runtime.py"
    path = tmp_path / relative
    path.write_text(path.read_text() + addition, encoding="utf-8")
    pins = dict(runner.ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS)
    pins[relative] = runner._git_blob_sha1(path)
    monkeypatch.setattr(
        runner, "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS", pins
    )
    monkeypatch.setattr(runner, "_arch134_armed_paper_authority_check", lambda _: ())
    assert any(
        "import closure" in f or "forbidden authority" in f
        for f in runner._arch134_production_paper_runtime_authority_check(tmp_path)
    )


@pytest.mark.parametrize("suffix", ["", ".execute.json", ".history-failure.json"])
def test_d1r1_host_evidence_collision_before_runtime_credentials_and_reservation(
    paths, monkeypatch, tmp_path, suffix
):
    host_startup(monkeypatch, paths)
    evidence = tmp_path / "session.json"
    collision = evidence.with_name(evidence.name + suffix)
    collision.write_bytes(b"preserve")
    monkeypatch.setattr(
        host, "preflight_runtime", lambda: pytest.fail("runtime access")
    )
    monkeypatch.setattr(
        host,
        "create_current_product_alpaca_provider",
        lambda: pytest.fail("credentials/provider"),
    )
    assert (
        host.main(cli_args("--arm", host.ARM_INTERLOCK, "--evidence", str(evidence)))
        == 3
    )
    assert collision.read_bytes() == b"preserve" and not paths.exists()


def test_d1r1_host_history_failure_stdout_stderr_sanitized(
    paths, monkeypatch, tmp_path, capsys
):
    runtime.provision_runtime()
    host_startup(monkeypatch, paths)

    def construction():
        raise RuntimeError("FAKE-SENSITIVE Authorization F:/private/fake.key")

    monkeypatch.setattr(host, "create_current_product_alpaca_provider", construction)
    monkeypatch.setattr(
        host,
        "create_current_product_quote_adapter",
        lambda: pytest.fail("Robinhood factory"),
    )
    evidence = tmp_path / "session.json"
    assert (
        host.main(cli_args("--arm", host.ARM_INTERLOCK, "--evidence", str(evidence)))
        == 3
    )
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "BLOCKED"
    assert output.err == ""
    assert "FAKE-SENSITIVE" not in output.out + output.err + evidence.read_text()
    assert ArmedSessionStore(runtime.SESSION_PATH).qualify() == 1


def test_d1r1_canonical_stdin_entrypoint_calls_main_and_preserves_module_noop():
    import ast

    root = Path(__file__).resolve().parents[2]
    module = ast.parse(
        (root / "src/trading_bot/review_paper/armed_session_host.py").read_text()
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "main"
        for node in module.body
    )
    assert not any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and ast.unparse(node.test) == "__name__ == '__main__'"
        for node in module.body
    )
    docs = (
        root / "docs/validation/arch134-d1r1-history-failure-observability.md"
    ).read_text()
    assert "from trading_bot.review_paper.armed_session_host import main" in docs
    assert "raise SystemExit(main())" in docs
    assert "'@ | & $PythonExe -B -" in docs
    assert "python -c" not in docs
