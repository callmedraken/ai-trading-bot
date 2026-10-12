"""D1Q fake-only boundary tests: no production credentials, storage or network."""

from __future__ import annotations

import ctypes
import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.review_paper.test_armed_production_paper_session import (  # noqa: F401
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
    assert runner.ACTIVE_CI_CHECKPOINTS[-1] == spec.name
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
    for relative in runner.ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((root / relative).read_text(encoding="utf-8"), encoding="utf-8")
    relative = "src/trading_bot/review_paper/production_paper_runtime.py"
    path = tmp_path / relative
    path.write_text(path.read_text() + addition, encoding="utf-8")
    pins = dict(runner.ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS)
    pins[relative] = runner._git_blob_sha1(path)
    monkeypatch.setattr(runner, "ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS", pins)
    monkeypatch.setattr(runner, "_arch134_armed_paper_authority_check", lambda _: ())
    assert any(
        "import closure" in f or "forbidden authority" in f
        for f in runner._arch134_production_paper_runtime_authority_check(tmp_path)
    )
