"""D1R4R fake-only incident cleanup and fresh-input regressions."""

from __future__ import annotations

import ctypes
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.review_paper import alpaca_authentication_host as auth
from trading_bot.review_paper import alpaca_credential_cleanup_host as host
from trading_bot.review_paper import alpaca_credential_generation as gen
from trading_bot.review_paper import alpaca_credential_host as fresh
from trading_bot.review_paper import alpaca_credential_native as native
from trading_bot.review_paper import alpaca_credential_staging_cleanup as cleanup
from trading_bot.review_paper import alpaca_windows_credentials as creds

HEAD, TREE = "a" * 40, "b" * 40
KEY, SECRET = b"k", b"s"  # Fake one-byte historical generation, never real secrets.


class Mutex:
    def __init__(self):
        self.owned = self.abandoned = self.busy = self.released = False

    def acquire(self):
        self.owned = not self.busy
        return self.owned

    def release(self):
        self.released = True
        self.owned = False


class Store:
    def __init__(self, h):
        self.h = h
        self.entries = dict(zip(gen.TARGETS, (KEY, SECRET), strict=True))
        self.calls, self.buffers = [], []
        self.fault = None

    def read(self, target):
        assert self.h.mutex.owned and target in gen.TARGETS
        self.calls.append(("read", target))
        if self.fault == ("read", target):
            raise OSError("FAKE_PRIVATE_ERROR")
        value = self.entries.get(target)
        if value is None:
            return None
        blob = bytearray(value)
        self.buffers.append(blob)
        return blob

    def delete(self, target):
        assert self.h.mutex.owned and target in gen.TARGETS
        event = (
            "KEY_DELETE_INTENT" if target == gen.TARGETS[0] else "SECRET_DELETE_INTENT"
        )
        assert self.h.durable[-1] == event
        assert (
            json.loads(cleanup.CLEANUP_LATCH.read_bytes().splitlines()[-1])["event"]
            == event
        )
        assert ("delete", target) not in self.calls
        self.calls.append(("delete", target))
        if self.fault == ("exception", target):
            raise OSError("FAKE_PRIVATE_ERROR")
        if self.fault == ("false", target):
            return False
        if self.fault != ("present", target):
            del self.entries[target]
        if self.fault == ("readback", target):
            self.fault = ("read", target)
        if self.fault == ("mutex", target):
            self.h.mutex.owned = False
        if self.fault == ("source", target):
            self.h.source_ok = False
        if self.fault == ("preserved", target):
            self.h.payload += b"x"
        return True


@pytest.fixture(autouse=True)
def no_real_boundaries(monkeypatch):
    monkeypatch.setattr(
        native.ctypes, "WinDLL", lambda *a, **kw: pytest.fail("real native boundary")
    )
    monkeypatch.setattr(
        auth,
        "StdlibAlpacaHistoricalBarsTransport",
        lambda: pytest.fail("provider transport"),
    )
    monkeypatch.setattr(
        auth,
        "qualify_alpaca_authentication",
        lambda **kw: pytest.fail("authentication"),
    )


@pytest.fixture
def h(tmp_path, monkeypatch):
    original = tmp_path / "generation.json"
    with original.open("xb") as output:
        journal = gen.GenerationJournal(
            output, cleanup.INCIDENT_HEAD, cleanup.INCIDENT_TREE
        )
        journal.record("PROVISIONING_RESERVED")
        journal.record("LOCK_ACQUIRED")
        journal.witnesses = tuple(
            gen.credential_witness(role, bytearray(value))
            for role, value in zip(gen.ROLES, (KEY, SECRET), strict=True)
        )
        for event in (
            "EXPECTED_GENERATION",
            "INITIAL_STATE_ACCEPTED",
            "KEY_WRITE_INTENT",
            "KEY_WRITE_CONFIRMED",
            "SECRET_WRITE_INTENT",
            "SECRET_WRITE_CONFIRMED",
            "PAIR_CONFIRMED",
        ):
            journal.record(event)
        journal.record("FINAL", "LOCAL_EXACT_MATCH")
    payload = original.read_bytes()
    assert len(payload) == cleanup.INCIDENT_BYTES
    monkeypatch.setattr(cleanup, "INCIDENT_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(cleanup, "CLEANUP_LATCH", tmp_path / "fixed-cleanup.json")
    state = SimpleNamespace(
        payload=payload, original=original, mutex=Mutex(), durable=[], source_ok=True
    )
    state.store = Store(state)
    real_fsync = cleanup.os.fsync

    def fsync(fd):
        real_fsync(fd)
        if cleanup.CLEANUP_LATCH.exists():
            state.durable.append(
                json.loads(cleanup.CLEANUP_LATCH.read_bytes().splitlines()[-1])["event"]
            )

    monkeypatch.setattr(cleanup.os, "fsync", fsync)

    def admit():
        if not state.source_ok:
            raise ValueError("FAKE_PRIVATE_ERROR")

    def run(record_hook=None):
        with cleanup.reserve_cleanup(HEAD, TREE) as journal:
            state.journal = journal
            record = journal.record

            def wrapped(event, classification=None):
                if event == "FINAL" and state.mutex.owned:
                    assert not state.mutex.released
                if record_hook:
                    record_hook(event)
                record(event, classification)

            journal.record = wrapped
            return cleanup.operate_cleanup(
                load_preserved=lambda: state.payload,
                store=state.store,
                mutex=state.mutex,
                journal=journal,
                admit_source=admit,
            )

    state.run = run
    return state


def test_fixed_incident_identity_and_latch_no_output_selection():
    assert (
        cleanup.INCIDENT_SHA256
        == "217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193"
    )
    assert cleanup.INCIDENT_BYTES == 4865
    assert cleanup.INCIDENT_HEAD == "41351ade6a2434adc26b9389106339e034b53a06"
    assert cleanup.INCIDENT_TREE == "6a6e6528c7e0bfb43835f70c620276f960f723ee"
    assert str(cleanup.CLEANUP_LATCH) == (
        "F:\\AI\\temp\\qualification\\arch134-d1r4r-cleanup-"
        + cleanup.INCIDENT_SHA256
        + ".json"
    )
    assert gen.MUTEX_NAME == r"Global\AITradingBot-Arch134-D1R4-AlpacaV3-Provision-v1"
    assert gen.TARGETS == (
        "AITradingBot/MarketData/Alpaca/ApiKeyId/v3",
        "AITradingBot/MarketData/Alpaca/ApiSecretKey/v3",
    )
    options = {
        option
        for action in host.build_parser()._actions
        for option in action.option_strings
    }
    assert options == {
        "-h",
        "--help",
        "--expected-head",
        "--expected-tree",
        "--preserved-evidence",
        "--cleanup-v3",
    }
    assert not hasattr(host.WindowsIncidentCleanupStore(), "write")


def test_success_durable_order_final_before_release_and_original_preserved(h):
    before = h.original.read_bytes()
    assert h.run() == "CLEANUP_EXACT_PAIR_REMOVED"
    records = [
        json.loads(line) for line in cleanup.CLEANUP_LATCH.read_bytes().splitlines()
    ]
    assert [r["event"] for r in records] == [*cleanup.SEQUENCE, "FINAL"]
    assert h.durable == [*cleanup.SEQUENCE, "FINAL"]
    assert records[-1]["classification"] == "CLEANUP_EXACT_PAIR_REMOVED"
    assert h.store.entries == {} and h.mutex.released
    assert h.original.read_bytes() == before
    assert h.store.calls.count(("delete", gen.TARGETS[0])) == 1
    assert h.store.calls.count(("delete", gen.TARGETS[1])) == 1
    assert all(not any(blob) for blob in h.store.buffers)
    # No raw material in evidence (single bytes are not meaningful substring tests).
    assert set(records[0]) == {
        "schema",
        "seq",
        "event",
        "source_head",
        "source_tree",
        "policy",
        "preserved_sha256",
        "preserved_bytes",
        "generation_head",
        "generation_tree",
        "classification",
    }
    assert b"FAKE_PRIVATE_ERROR" not in cleanup.CLEANUP_LATCH.read_bytes()


@pytest.mark.parametrize(
    "kind", ["length", "digest", "head", "tree", "truncated", "provider", "unaccepted"]
)
def test_bad_preserved_generation_zero_credentials(h, monkeypatch, kind):
    if kind == "length":
        h.payload += b"x"
    elif kind == "digest":
        h.payload = h.payload.replace(b'"utf8_length":1', b'"utf8_length":2')
    else:
        original = cleanup.parse_generation_journal

        def parsed(payload):
            p = original(payload)
            changes = {
                "head": {"head": HEAD},
                "tree": {"tree": TREE},
                "truncated": {"truncated": True},
                "provider": {"provider_fenced": True},
                "unaccepted": {"pair_accepted": False},
            }
            from dataclasses import replace

            return replace(p, **changes[kind])

        monkeypatch.setattr(cleanup, "parse_generation_journal", parsed)
    assert h.run() == "CLEANUP_ADMISSION_BLOCKED"
    assert h.store.calls == []


@pytest.mark.parametrize("mode", ["busy", "abandoned"])
def test_busy_and_abandoned_zero_credentials(h, mode):
    setattr(h.mutex, mode, True)
    assert h.run() == (
        "CONCURRENT_PROVISIONER" if mode == "busy" else "ABANDONED_OWNER"
    )
    assert h.store.calls == []


@pytest.mark.parametrize(
    "state",
    [
        "absent",
        "key-only",
        "secret-only",
        "foreign-key",
        "foreign-secret",
        "unreadable",
    ],
)
def test_initial_both_exact_required(h, state):
    if state == "absent":
        h.store.entries.clear()
    elif state == "key-only":
        del h.store.entries[gen.TARGETS[1]]
    elif state == "secret-only":
        del h.store.entries[gen.TARGETS[0]]
    elif state.startswith("foreign"):
        h.store.entries[gen.TARGETS[state == "foreign-secret"]] = b"foreign-fake"
    else:
        h.store.fault = ("read", gen.TARGETS[0])
    assert h.run() == "CLEANUP_ADMISSION_BLOCKED"
    assert not any(c[0] == "delete" for c in h.store.calls)


@pytest.mark.parametrize(
    "fault",
    ["exception", "false", "present", "readback", "mutex", "source", "preserved"],
)
@pytest.mark.parametrize("index", [0, 1])
def test_delete_uncertainty_stops_later_delete_and_consumes_latch(h, fault, index):
    h.store.fault = (fault, gen.TARGETS[index])
    assert h.run() == "DELETE_OUTCOME_AMBIGUOUS"
    assert len([c for c in h.store.calls if c[0] == "delete"]) == index + 1
    before = list(h.store.calls)
    with pytest.raises(FileExistsError):
        h.run()
    assert h.store.calls == before and h.mutex.released


@pytest.mark.parametrize("event", cleanup.SEQUENCE[1:] + ("FINAL",))
def test_evidence_failure_prevents_later_deletion(h, monkeypatch, event):
    def hook(current):
        if current == event:
            monkeypatch.setattr(
                cleanup.os,
                "fsync",
                lambda _: (_ for _ in ()).throw(OSError("FAKE_PRIVATE_ERROR")),
            )

    result = h.run(hook)
    deletes = len([c for c in h.store.calls if c[0] == "delete"])
    assert deletes == (
        0
        if event in cleanup.SEQUENCE[1:5]
        else 1
        if event in cleanup.SEQUENCE[5:7]
        else 2
    )
    assert result == (
        "DELETE_OUTCOME_AMBIGUOUS" if deletes else "CLEANUP_ADMISSION_BLOCKED"
    )
    assert h.journal.failed and h.mutex.released
    with pytest.raises(FileExistsError):
        h.run()


def test_reservation_fsync_failure_zero_native_entry(h, monkeypatch):
    monkeypatch.setattr(
        cleanup.os,
        "fsync",
        lambda _: (_ for _ in ()).throw(OSError("FAKE_PRIVATE_ERROR")),
    )
    with pytest.raises(gen.GenerationError) as caught:
        h.run()
    assert caught.value.__context__ is None
    assert h.store.calls == [] and not h.mutex.owned
    assert cleanup.CLEANUP_LATCH.exists()


@pytest.mark.parametrize(
    "event", ["PAIR_MATCH_CONFIRMED", "KEY_DELETE_INTENT", "SECRET_DELETE_INTENT"]
)
def test_source_or_remaining_secret_drift_prevents_next_delete(h, event):
    def hook(current):
        if current == event:
            h.store.entries[gen.TARGETS[1]] = b"foreign-fake"

    assert h.run(hook) == (
        "DELETE_OUTCOME_AMBIGUOUS"
        if event == "SECRET_DELETE_INTENT"
        else "CLEANUP_ADMISSION_BLOCKED"
    )
    assert len([c for c in h.store.calls if c[0] == "delete"]) == (
        event == "SECRET_DELETE_INTENT"
    )


def test_independent_final_pair_absence_required(h):
    def hook(event):
        if event == "SECRET_DELETE_CONFIRMED":
            h.store.entries[gen.TARGETS[0]] = KEY

    assert h.run(hook) == "DELETE_OUTCOME_AMBIGUOUS"
    assert h.store.entries == {gen.TARGETS[0]: KEY}


def test_consumed_latch_cannot_be_bypassed_by_copy_of_original(h):
    assert h.run() == "CLEANUP_EXACT_PAIR_REMOVED"
    copied = h.original.with_name("copied.json")
    copied.write_bytes(h.payload)
    h.payload = copied.read_bytes()
    before = list(h.store.calls)
    with pytest.raises(FileExistsError):
        h.run()
    assert h.store.calls == before


@pytest.mark.parametrize(
    "target",
    [
        "AITradingBot/MarketData/Alpaca/ApiKeyId/v2",
        "AITradingBot/MarketData/Alpaca/ApiSecretKey/v2",
        "foreign",
    ],
)
def test_v2_and_foreign_target_rejected_before_native(monkeypatch, target):
    monkeypatch.setattr(
        native.ctypes, "WinDLL", lambda *a, **kw: pytest.fail("native API")
    )
    with pytest.raises(creds.AlpacaCredentialReadError):
        host.WindowsIncidentCleanupStore().read(target)
    with pytest.raises(gen.GenerationError):
        host.WindowsIncidentCleanupStore().delete(target)


@pytest.mark.parametrize("values", [(b"x", b"valid-secret"), (b"valid-key", b"x")])
def test_fresh_one_byte_rejected_before_any_state_access(h, values):
    path = h.original.with_name("fresh.json")
    with path.open("xb") as output:
        journal = gen.GenerationJournal(output, HEAD, TREE)
        pair = tuple(bytearray(v) for v in values)
        assert (
            gen.operate_generation(
                store=h.store,
                mutex=h.mutex,
                journal=journal,
                admit_source=lambda: (),
                interactive_pair=lambda: pair,
            )
            == "INPUT_OR_ADMISSION_FAILED"
        )
    assert h.store.calls == [] and all(not any(v) for v in pair)
    assert cleanup.admit_incident(h.payload).witnesses[0] == gen.credential_witness(
        gen.ROLES[0], bytearray(KEY)
    )


@pytest.mark.parametrize(
    "mode", ["pass", "mismatch", "one-byte", "confirmation", "malformed"]
)
def test_fresh_repeated_input_floor_confirmation_and_redaction(
    monkeypatch, capsys, mode
):
    monkeypatch.setattr(fresh.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(
        fresh.sys,
        "stdout",
        SimpleNamespace(
            isatty=lambda: True, write=sys.stdout.write, flush=sys.stdout.flush
        ),
    )
    inputs = iter(
        (
            fresh.STAGING_CONFIRMATION,
            "bad" if mode == "confirmation" else fresh.LENGTH_CONFIRMATION,
        )
    )
    monkeypatch.setattr("builtins.input", lambda *a: next(inputs))
    key = "x" if mode == "one-byte" else "fake-key-value"
    secret = "bad secret\n" if mode == "malformed" else "fake-secret-value"
    prompts = iter((key, key, secret, "other-value" if mode == "mismatch" else secret))
    monkeypatch.setattr(fresh.getpass, "getpass", lambda *a: next(prompts))
    copies = []

    def mutable(value):
        blob = bytearray(value)
        copies.append(blob)
        return blob

    monkeypatch.setattr(fresh, "bytearray", mutable, raising=False)
    if mode == "pass":
        pair = fresh.interactive_generation_pair()
        assert pair == (bytearray(key.encode()), bytearray(secret.encode()))
        for value in pair:
            gen.clear_credential(value)
    else:
        with pytest.raises(gen.GenerationError) as caught:
            fresh.interactive_generation_pair()
        assert caught.value.__context__ is None
    assert all(not any(blob) for blob in copies)
    captured = str(capsys.readouterr())
    assert "fake-key-value" not in captured and "fake-secret-value" not in captured


def test_host_source_failure_sanitized_zero_native_and_no_latch(h, monkeypatch, capsys):
    monkeypatch.setattr(host, "INCIDENT_JOURNAL", h.original)
    monkeypatch.setattr(host, "CLEANUP_LATCH", cleanup.CLEANUP_LATCH)
    monkeypatch.setattr(
        host,
        "admit_authentication_source",
        lambda *a: (_ for _ in ()).throw(ValueError("FAKE_PRIVATE_ERROR")),
    )
    monkeypatch.setattr(host, "WindowsV3Exclusion", lambda: pytest.fail("mutex"))
    assert (
        host.main(
            [
                "--expected-head",
                HEAD,
                "--expected-tree",
                TREE,
                "--preserved-evidence",
                str(h.original),
                "--cleanup-v3",
                host.CLEANUP_INTERLOCK,
            ]
        )
        == 2
    )
    assert not cleanup.CLEANUP_LATCH.exists()
    assert "FAKE_PRIVATE_ERROR" not in capsys.readouterr().err


def test_host_fake_success_and_consumed_latch(h, monkeypatch, capsys):
    monkeypatch.setattr(host, "INCIDENT_JOURNAL", h.original)
    monkeypatch.setattr(host, "CLEANUP_LATCH", cleanup.CLEANUP_LATCH)
    monkeypatch.setattr(host, "admit_authentication_source", lambda *a: ())
    monkeypatch.setattr(host, "admit_authentication_evidence", lambda p, roots: p)
    monkeypatch.setattr(host, "WindowsV3Exclusion", lambda: h.mutex)
    monkeypatch.setattr(host, "WindowsIncidentCleanupStore", lambda: h.store)
    args = [
        "--expected-head",
        HEAD,
        "--expected-tree",
        TREE,
        "--preserved-evidence",
        str(h.original),
        "--cleanup-v3",
        host.CLEANUP_INTERLOCK,
    ]
    assert host.main(args) == 0
    before = list(h.store.calls)
    assert host.main(args) == 2
    assert h.store.calls == before
    assert "FAKE_PRIVATE_ERROR" not in str(capsys.readouterr())


def test_import_and_help_inert():
    root = Path(__file__).resolve().parents[2]
    command = (
        "import sys; sys.path.insert(0, 'src'); import ctypes; "
        "ctypes.WinDLL=lambda *a, **k: "
        "(_ for _ in ()).throw(AssertionError('native')); "
        "from trading_bot.review_paper.alpaca_credential_cleanup_host import main; "
        "main(['--help'])"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", command], cwd=root, capture_output=True, text=True
    )
    assert result.returncode == 0 and "D1R4R" in result.stdout and result.stderr == ""


@pytest.mark.parametrize(
    "field",
    [
        None,
        "Flags",
        "AttributeCount",
        "Attributes",
        "TargetAlias",
        "UserName",
        "Comment",
    ],
)
def test_cleanup_strict_native_metadata_and_one_byte_readability(monkeypatch, field):
    class Record(ctypes.Structure):
        _fields_ = [
            ("TargetName", ctypes.c_wchar_p),
            ("Type", ctypes.c_uint32),
            ("Persist", ctypes.c_uint32),
            ("Flags", ctypes.c_uint32),
            ("AttributeCount", ctypes.c_uint32),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("CredentialBlobSize", ctypes.c_uint32),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ]

    buffer = (ctypes.c_ubyte * 1)(ord("k"))
    record = Record()
    record.TargetName = creds.API_KEY_TARGET
    record.Type, record.Persist, record.CredentialBlobSize = 1, 2, 1
    record.CredentialBlob = buffer
    if field:
        setattr(
            record,
            field,
            "unexpected" if field in {"TargetAlias", "UserName", "Comment"} else 1,
        )
    pointer = ctypes.pointer(record)
    freed = []

    def read(target, kind, flags, output):
        assert target == gen.TARGETS[0] and kind == 1 and flags == 0
        ctypes.cast(output, ctypes.POINTER(ctypes.POINTER(Record)))[0] = pointer
        return True

    reader = creds._WindowsCredentialReader.__new__(creds._WindowsCredentialReader)
    reader._credential = Record
    reader._api = SimpleNamespace(CredReadW=read, CredFree=lambda _: freed.append(True))
    reader._zero_memory = lambda address, size: ctypes.memset(address, 0, size)
    monkeypatch.setattr(creds, "_WindowsCredentialReader", lambda: reader)
    if field:
        with pytest.raises(creds.AlpacaCredentialReadError):
            host.WindowsIncidentCleanupStore().read(gen.TARGETS[0])
    else:
        value = host.WindowsIncidentCleanupStore().read(gen.TARGETS[0])
        assert gen.credential_witness(gen.ROLES[0], value) == gen.credential_witness(
            gen.ROLES[0], bytearray(KEY)
        )
        gen.clear_credential(value)
    assert freed == [True] and list(buffer) == [0]


@pytest.mark.parametrize("event", ["KEY_DELETE_INTENT", "SECRET_DELETE_INTENT"])
@pytest.mark.parametrize("fault", ["source", "mutex", "preserved"])
def test_admission_lost_after_intent_prevents_native_entry(h, event, fault):
    def hook(current):
        if current == event:
            if fault == "source":
                h.source_ok = False
            elif fault == "mutex":
                h.mutex.owned = False
            else:
                h.payload += b"x"

    outcome = h.run(hook)
    expected_deletes = int(event == "SECRET_DELETE_INTENT")
    assert len([c for c in h.store.calls if c[0] == "delete"]) == expected_deletes
    assert outcome == (
        "DELETE_OUTCOME_AMBIGUOUS" if expected_deletes else "CLEANUP_ADMISSION_BLOCKED"
    )
    assert h.mutex.released


def test_journal_closed_sequence_rejects_extra_roles_and_false_success(h):
    with cleanup.reserve_cleanup(HEAD, TREE) as journal:
        for event in ("SECRET_DELETE_INTENT", "UNKNOWN"):
            with pytest.raises(gen.GenerationError):
                journal.record(event)
        with pytest.raises(gen.GenerationError):
            journal.record("FINAL", "CLEANUP_EXACT_PAIR_REMOVED")
        journal.record("FINAL", "CLEANUP_ADMISSION_BLOCKED")
        with pytest.raises(gen.GenerationError):
            journal.record("LOCK_ACQUIRED")


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("index", [0, 1])
def test_native_interruption_after_entry_is_ambiguous(h, interrupt, index):
    original = h.store.delete

    def interrupted(target):
        result = original(target)
        if target == gen.TARGETS[index]:
            raise interrupt("FAKE_PRIVATE_ERROR")
        return result

    h.store.delete = interrupted
    assert h.run() == "DELETE_OUTCOME_AMBIGUOUS"
    assert len([c for c in h.store.calls if c[0] == "delete"]) == index + 1
    assert h.mutex.released


def test_release_failure_cannot_report_success(h):
    original = h.mutex.release

    def release():
        original()
        raise OSError("FAKE_PRIVATE_ERROR")

    h.mutex.release = release
    assert h.run() == "DELETE_OUTCOME_AMBIGUOUS"
    assert h.mutex.released


@pytest.mark.parametrize("kind", ["short-write", "write", "flush"])
@pytest.mark.parametrize("stage", ["KEY_DELETE_INTENT", "SECRET_DELETE_INTENT"])
def test_journal_write_flush_failure_prevents_next_delete(h, kind, stage):
    class Output:
        def write(self, payload):
            if kind == "write":
                raise OSError("FAKE_PRIVATE_ERROR")
            if kind == "short-write":
                return 0
            return h.output.write(payload)

        def flush(self):
            raise OSError("FAKE_PRIVATE_ERROR")

    def hook(event):
        if event == stage:
            h.output = h.journal.output
            h.journal.output = Output()

    expected = int(stage == "SECRET_DELETE_INTENT")
    assert h.run(hook) == (
        "DELETE_OUTCOME_AMBIGUOUS" if expected else "CLEANUP_ADMISSION_BLOCKED"
    )
    assert len([c for c in h.store.calls if c[0] == "delete"]) == expected
    assert h.mutex.released


def test_host_rejects_copied_preserved_path_before_latch_or_credentials(
    h, monkeypatch, capsys
):
    monkeypatch.setattr(host, "INCIDENT_JOURNAL", h.original)
    monkeypatch.setattr(host, "CLEANUP_LATCH", cleanup.CLEANUP_LATCH)
    monkeypatch.setattr(host, "admit_authentication_source", lambda *a: ())
    monkeypatch.setattr(host, "admit_authentication_evidence", lambda p, roots: p)
    monkeypatch.setattr(host, "WindowsV3Exclusion", lambda: pytest.fail("mutex"))
    copied = h.original.with_name("copied-journal.json")
    copied.write_bytes(h.payload)
    assert (
        host.main(
            [
                "--expected-head",
                HEAD,
                "--expected-tree",
                TREE,
                "--preserved-evidence",
                str(copied),
                "--cleanup-v3",
                host.CLEANUP_INTERLOCK,
            ]
        )
        == 2
    )
    assert not cleanup.CLEANUP_LATCH.exists() and h.store.calls == []
    assert (
        capsys.readouterr().err
        == "ALPACA_V3_INCIDENT_CLEANUP_BLOCKED_REVIEW_REQUIRED\n"
    )
