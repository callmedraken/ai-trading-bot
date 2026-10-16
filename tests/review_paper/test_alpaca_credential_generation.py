"""D1R4 fake-only generation, exclusion, ambiguity and witness regression."""

from __future__ import annotations

import ctypes
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.review_paper import alpaca_credential_generation as gen
from trading_bot.review_paper import alpaca_credential_host as host
from trading_bot.review_paper import alpaca_credential_native as native
from trading_bot.review_paper import alpaca_windows_credentials as creds

HEAD, TREE = "a" * 40, "b" * 40
KEY, SECRET = b"fake-key-v3", b"fake-secret-v3"


class Mutex:
    def __init__(self, *, busy=False, abandoned=False):
        self.busy, self.abandoned = busy, abandoned
        self.owned = self.released = False

    def acquire(self):
        self.owned = not self.busy
        return self.owned

    def release(self):
        self.released = True
        self.owned = False


class Store:
    def __init__(self, mutex, journal):
        self.mutex, self.journal = mutex, journal
        self.entries = {}
        self.calls = []
        self.fail = None
        self.foreign = None
        self.buffers = []

    def read(self, target):
        assert self.mutex.owned and target in gen.TARGETS
        self.calls.append(("read", target))
        if self.fail == ("read", target):
            raise OSError(SECRET.decode())
        blob = self.entries.get(target)
        if blob is not None:
            blob = bytearray(blob)
            self.buffers.append(blob)
        return blob

    def write(self, target, value):
        assert self.mutex.owned and target in gen.TARGETS
        self.journal.output.flush()
        events = [
            json.loads(line)["event"]
            for line in self.journal.path.read_bytes().splitlines()
        ]
        assert events[-1] == (
            "KEY_WRITE_INTENT" if target == gen.TARGETS[0] else "SECRET_WRITE_INTENT"
        )
        assert target not in self.entries
        self.calls.append(("write", target))
        self.entries[target] = bytes(value)
        if self.fail == ("write", target):
            raise OSError(SECRET.decode())
        if self.fail == ("false", target):
            return False
        if self.fail == ("missing", target):
            del self.entries[target]
        if self.foreign == target:
            self.entries[target] = b"foreign"
        return True

    def delete(self, target):
        assert self.mutex.owned and target == gen.TARGETS[0]
        self.calls.append(("delete", target))
        if self.fail == ("delete", target):
            raise OSError(SECRET.decode())
        if self.fail == ("delete-false", target):
            return False
        del self.entries[target]
        return True


@contextmanager
def harness(tmp_path, **mutex_kwargs):
    path = tmp_path / "generation.json"
    with path.open("xb") as output:
        journal = gen.GenerationJournal(output, HEAD, TREE)
        journal.path = path
        mutex = Mutex(**mutex_kwargs)
        store = Store(mutex, journal)
        values = (bytearray(KEY), bytearray(SECRET))
        state = SimpleNamespace(
            journal=journal, mutex=mutex, store=store, values=values, path=path
        )
        state.run = lambda **kw: gen.operate_generation(
            store=store,
            mutex=mutex,
            journal=journal,
            admit_source=lambda: (),
            interactive_pair=lambda: values,
            **kw,
        )
        yield state


def test_exact_v3_and_arch84_witness_vector():
    assert creds.CREDENTIAL_POLICY == "windows-credential-manager-alpaca-market-data/v3"
    assert gen.TARGETS == (
        "AITradingBot/MarketData/Alpaca/ApiKeyId/v3",
        "AITradingBot/MarketData/Alpaca/ApiSecretKey/v3",
    )
    for role in gen.ROLES:
        expected = hashlib.sha256(
            b"AITradingBot/C3CredentialWitness/v1\0" + role.encode() + b"\0" + KEY
        ).hexdigest()
        assert gen.credential_witness(role, bytearray(KEY)) == gen.Witness(
            expected, len(KEY)
        )
    assert gen.credential_witness(
        gen.ROLES[0], bytearray(KEY)
    ) != gen.credential_witness(gen.ROLES[1], bytearray(KEY))


@pytest.mark.parametrize(
    "value",
    [b"", b" leading", b"trailing ", b"x\r", b"x\n", b"x\0", b"\xff", b"a" * 1025],
)
def test_strict_shared_secret_validation(value):
    with pytest.raises(creds.AlpacaCredentialReadError):
        gen.credential_witness(gen.ROLES[0], bytearray(value))


def test_pair_provisioned_once_and_final_evidence_under_exclusion(tmp_path):
    with harness(tmp_path) as h:
        original = h.journal.record

        def record(event, classification=None):
            if event == "FINAL":
                assert h.mutex.owned
            original(event, classification)

        h.journal.record = record
        assert h.run() == "LOCAL_EXACT_MATCH"
        assert [c for c in h.store.calls if c[0] == "write"] == [
            ("write", t) for t in gen.TARGETS
        ]
        assert h.mutex.released and all(
            not any(v) for v in h.values + tuple(h.store.buffers)
        )
        payload = h.path.read_bytes()
        assert KEY not in payload and SECRET not in payload
        preserved = gen.parse_generation_journal(payload)
        assert preserved.pair_accepted and not preserved.provider_fenced


@pytest.mark.parametrize("mask", [1, 2, 3])
def test_existing_v3_blocks_without_overwrite(tmp_path, mask):
    with harness(tmp_path) as h:
        for i, target in enumerate(gen.TARGETS):
            if mask & (1 << i):
                h.store.entries[target] = KEY
        before = dict(h.store.entries)
        assert h.run() == "BLOCKED_EXISTING_V3_STATE"
        assert h.store.entries == before and all(c[0] == "read" for c in h.store.calls)


def test_busy_zero_reads_writes_deletes_or_input(tmp_path):
    with harness(tmp_path, busy=True) as h:
        assert h.run() == "CONCURRENT_PROVISIONER"
        assert h.store.calls == []
        assert not h.mutex.owned


def test_abandoned_only_observes_and_never_prompts(tmp_path):
    with harness(tmp_path, abandoned=True) as h:
        assert h.run() == "ABANDONED_OWNER"
        assert h.store.calls == [("read", t) for t in gen.TARGETS]
        assert all(any(v) for v in h.values)  # interactive input was not called


def test_abandoned_owner_read_failure_still_requires_reconciliation(tmp_path):
    with harness(tmp_path, abandoned=True) as h:
        h.store.fail = ("read", gen.TARGETS[0])
        assert h.run() == "ABANDONED_OWNER"
        assert all(c[0] == "read" for c in h.store.calls)
        assert h.mutex.released


@pytest.mark.parametrize(
    "kind", ["write", "false", "missing", "readback", "foreign", "confirmation"]
)
@pytest.mark.parametrize("role", [0, 1])
def test_ambiguous_write_stops_all_mutations_and_never_cleans(tmp_path, kind, role):
    with harness(tmp_path) as h:
        target = gen.TARGETS[role]
        if kind == "foreign":
            h.store.foreign = target
        elif kind in {"write", "false", "missing"}:
            h.store.fail = (kind, target)
        elif kind == "readback":
            write = h.store.write

            def fail_readback(t, value):
                result = write(t, value)
                if t == target:
                    h.store.fail = ("read", t)
                return result

            h.store.write = fail_readback
        else:
            original = h.journal.record

            def record(event, classification=None):
                if event == (
                    "KEY_WRITE_CONFIRMED" if role == 0 else "SECRET_WRITE_CONFIRMED"
                ):
                    raise OSError(SECRET.decode())
                original(event, classification)

            h.journal.record = record
        assert h.run() == "WRITE_OUTCOME_AMBIGUOUS"
        assert len([c for c in h.store.calls if c[0] == "write"]) == role + 1
        assert not any(c[0] == "delete" for c in h.store.calls)


@pytest.mark.parametrize(
    "cleanup", ["match", "foreign", "delete", "delete-false", "evidence"]
)
def test_failure_before_secret_write_cleanup_is_conditional(tmp_path, cleanup):
    with harness(tmp_path) as h:
        original = h.journal.record

        def record(event, classification=None):
            if event == "SECRET_WRITE_INTENT":
                if cleanup == "foreign":
                    h.store.entries[gen.TARGETS[0]] = b"foreign"
                if cleanup in {"delete", "delete-false"}:
                    h.store.fail = (cleanup, gen.TARGETS[0])
                raise OSError(SECRET.decode())
            if event == "KEY_DELETE_INTENT" and cleanup == "evidence":
                raise OSError(SECRET.decode())
            original(event, classification)

        h.journal.record = record
        expected = (
            "CLEANUP_CONFIRMED"
            if cleanup == "match"
            else "EXTERNAL_STATE_INTERFERENCE"
            if cleanup == "foreign"
            else "CLEANUP_OUTCOME_AMBIGUOUS"
        )
        assert h.run() == expected
        assert len([c for c in h.store.calls if c[0] == "write"]) == 1
        assert len([c for c in h.store.calls if c[0] == "delete"]) == (
            0 if cleanup in {"foreign", "evidence"} else 1
        )


def test_initial_intent_fsync_failure_prevents_native_write(tmp_path):
    with harness(tmp_path) as h:
        original = h.journal.record

        def record(event, classification=None):
            if event == "KEY_WRITE_INTENT":
                raise OSError(SECRET.decode())
            original(event, classification)

        h.journal.record = record
        assert h.run() == "INPUT_OR_ADMISSION_FAILED"
        assert all(c[0] == "read" for c in h.store.calls)


@pytest.mark.parametrize(
    "state,expected",
    [
        ((None, None), "RECONCILED_ABSENT"),
        ((KEY, SECRET), "RECONCILED_PAIR_MATCH"),
        ((KEY, None), "RECONCILED_PARTIAL_MATCH"),
        ((None, SECRET), "RECONCILED_PARTIAL_MATCH"),
        ((b"foreign", SECRET), "RECONCILED_UNKNOWN_OR_FOREIGN_STATE"),
    ],
)
@pytest.mark.parametrize("abandoned", [False, True])
def test_reconciliation_read_only(tmp_path, state, expected, abandoned):
    witnesses = tuple(
        gen.credential_witness(r, bytearray(v))
        for r, v in zip(gen.ROLES, (KEY, SECRET), strict=True)
    )
    preserved = gen.PreservedGeneration(HEAD, TREE, witnesses, False, False, False)
    with harness(tmp_path, abandoned=abandoned) as h:
        h.store.entries = {
            t: v for t, v in zip(gen.TARGETS, state, strict=True) if v is not None
        }
        assert h.run(preserved=preserved) == (
            "ABANDONED_OWNER" if abandoned else expected
        )
        assert all(c[0] == "read" for c in h.store.calls)


@pytest.mark.parametrize(
    "target",
    [
        "AITradingBot/MarketData/Alpaca/ApiKeyId/v2",
        "AITradingBot/MarketData/Alpaca/ApiSecretKey/v2",
        "alternate",
        None,
    ],
)
def test_native_never_accesses_v2_or_caller_targets(target, monkeypatch):
    monkeypatch.setattr(
        native.ctypes, "WinDLL", lambda *a, **k: pytest.fail("native call")
    )
    store = native.WindowsV3CredentialStore()
    for action in (
        lambda: store.read(target),
        lambda: store.write(target, bytearray(KEY)),
        lambda: store.delete(target),
    ):
        with pytest.raises(gen.GenerationError, match="fixed v3"):
            action()


@pytest.fixture
def kernel(monkeypatch):
    sid = "S-1-5-21-1-2-3-1001"
    state = SimpleNamespace(wait=0, calls=[], owner=sid, protected=True)
    policy = native.provisioning_mutex_policy(sid, sid)
    state.aces = policy.aces

    class Function:
        def __init__(self, name, callback):
            self.name, self.callback = name, callback

        def __call__(self, *a):
            state.calls.append((self.name, a))
            return self.callback(*a)

    api = SimpleNamespace(
        CreateMutexExW=Function("create", lambda *a: 1),
        WaitForSingleObject=Function("wait", lambda *a: state.wait),
        ReleaseMutex=Function("release", lambda *a: True),
        CloseHandle=Function("close", lambda *a: True),
    )

    @contextmanager
    def attributes(p):
        assert p == policy
        yield SimpleNamespace(attributes=ctypes.c_int())

    monkeypatch.setattr(native.ctypes, "WinDLL", lambda *a, **k: api)
    monkeypatch.setattr(native, "resolve_current_token_sid", lambda: sid)
    monkeypatch.setattr(native, "build_security_attributes", attributes)
    monkeypatch.setattr(
        native,
        "inspect_handle_security",
        lambda *a: (state.owner, state.protected, state.aces),
    )
    monkeypatch.setattr(native, "_POISONED", False)
    return state


@pytest.mark.parametrize("wait", [0, 0x80, 258, 0xFFFFFFFF, 9])
def test_fixed_global_zero_wait_native_outcomes(kernel, wait):
    kernel.wait = wait
    mutex = native.WindowsV3Exclusion()
    try:
        if wait in {0, 0x80, 258}:
            assert mutex.acquire() == (wait != 258)
            assert mutex.abandoned == (wait == 0x80)
        else:
            with pytest.raises(gen.GenerationError):
                mutex.acquire()
    finally:
        mutex.release()
    create = next(c for c in kernel.calls if c[0] == "create")
    assert create[1][1] == r"Global\AITradingBot-Arch134-D1R4-AlpacaV3-Provision-v1"
    assert [c[1][1] for c in kernel.calls if c[0] == "wait"] == [0]


@pytest.mark.parametrize("change", ["owner", "dacl", "protected"])
def test_hostile_global_mutex_security_rejected_before_wait(kernel, change):
    if change == "owner":
        kernel.owner = "unexpected"
    elif change == "dacl":
        kernel.aces = ()
    else:
        kernel.protected = False
    with pytest.raises(gen.GenerationError):
        native.WindowsV3Exclusion().acquire()
    assert not any(c[0] == "wait" for c in kernel.calls)


def test_reentrant_mutex_blocked_without_second_native_open(kernel):
    first, second = native.WindowsV3Exclusion(), native.WindowsV3Exclusion()
    assert first.acquire()
    try:
        assert not second.acquire()
    finally:
        first.release()
    assert len([c for c in kernel.calls if c[0] == "create"]) == 1


def _process_exclusion(lock, ready, release, results, owner):
    # Route both spawned source adapters through one disposable fake Win32 mutex.
    sid = "S-1-5-21-1-2-3-1001"
    policy = native.provisioning_mutex_policy(sid, sid)

    class Function:
        def __init__(self, callback):
            self.callback = callback

        def __call__(self, *args):
            return self.callback(*args)

    def create(attributes, name, flags, rights):
        assert name == gen.MUTEX_NAME and flags == 0
        return 1

    def wait(handle, milliseconds):
        assert milliseconds == 0
        return 0 if lock.acquire(False) else 258

    api = SimpleNamespace(
        CreateMutexExW=Function(create),
        WaitForSingleObject=Function(wait),
        ReleaseMutex=Function(lambda *a: lock.release() is None),
        CloseHandle=Function(lambda *a: True),
    )

    @contextmanager
    def attributes(p):
        assert p == policy
        yield SimpleNamespace(attributes=ctypes.c_int())

    native.ctypes.WinDLL = lambda *a, **kw: api
    native.resolve_current_token_sid = lambda: sid
    native.build_security_attributes = attributes
    native.inspect_handle_security = lambda *a: (sid, True, policy.aces)
    mutex = native.WindowsV3Exclusion()
    acquired = mutex.acquire()
    results.put((owner, acquired))
    if acquired:
        ready.set()
        release.wait(10)
        mutex.release()


def test_two_processes_cannot_both_enter_credential_boundary():
    ctx = multiprocessing.get_context("spawn")
    lock, ready, release, results = ctx.Lock(), ctx.Event(), ctx.Event(), ctx.Queue()
    first = ctx.Process(
        target=_process_exclusion, args=(lock, ready, release, results, 1)
    )
    second = ctx.Process(
        target=_process_exclusion, args=(lock, ready, release, results, 2)
    )
    first.start()
    try:
        assert ready.wait(10)
        second.start()
        second.join(10)
        assert not second.is_alive() and second.exitcode == 0
        assert sorted([results.get(timeout=5), results.get(timeout=5)]) == [
            (1, True),
            (2, False),
        ]
    finally:
        release.set()
        first.join(10)
        if first.is_alive():
            first.terminate()
            first.join(5)
    assert first.exitcode == 0


def test_truncated_evidence_conservatively_closes_provider_staging(tmp_path):
    with harness(tmp_path) as h:
        h.run()
        preserved = gen.parse_generation_journal(h.path.read_bytes() + b'{"partial"')
        assert preserved.truncated and preserved.provider_fenced


@pytest.mark.parametrize(
    "transform",
    [
        lambda b: b + b"\n",
        lambda b: b.replace(b'"seq":0', b'"seq":true'),
        lambda b: b.replace(b'"policy":', b'"unknown":'),
        lambda b: b"x" * 32769,
    ],
)
def test_journal_rejects_noncanonical_or_unbounded_input(tmp_path, transform):
    with harness(tmp_path) as h:
        h.run()
        with pytest.raises(gen.GenerationError) as caught:
            gen.parse_generation_journal(transform(h.path.read_bytes()))
        assert (
            SECRET.decode() not in str(caught.value)
            and caught.value.__context__ is None
        )


def test_host_source_failure_has_no_evidence_or_native_effect(
    tmp_path, monkeypatch, capsys
):
    def fail(*a):
        raise ValueError(SECRET.decode())

    monkeypatch.setattr(host, "admit_authentication_source", fail)
    monkeypatch.setattr(host, "WindowsV3Exclusion", lambda: pytest.fail("mutex"))
    args = [
        "--expected-head",
        HEAD,
        "--expected-tree",
        TREE,
        "--evidence",
        str(tmp_path / "out.json"),
        "--provision-v3",
        host.PROVISION_INTERLOCK,
    ]
    assert host.main(args) == 2
    assert not (tmp_path / "out.json").exists()
    assert SECRET.decode() not in capsys.readouterr().err


def test_interactive_input_rejects_redirected_stream(monkeypatch):
    monkeypatch.setattr(host.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(host.getpass, "getpass", lambda *a: pytest.fail("secret input"))
    with pytest.raises(gen.GenerationError):
        host.interactive_generation_pair()


def test_help_is_inert_with_no_target_or_secret_arguments():
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(creds.__file__).parents[2])
    result = subprocess.run(
        [sys.executable, "-B", "-m", host.__name__, "--help"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "--provision-v3" in result.stdout
    for forbidden in ("--target", "--api-key", "--api-secret", "/v2", "--cleanup"):
        assert forbidden not in result.stdout


@pytest.mark.parametrize("stage", ["KEY_WRITE_INTENT", "SECRET_WRITE_INTENT"])
def test_real_journal_fsync_failure_prevents_next_mutation(
    tmp_path, monkeypatch, stage
):
    with harness(tmp_path) as h:
        original = h.journal.record

        def record(event, classification=None):
            if event == stage:
                monkeypatch.setattr(
                    gen.os,
                    "fsync",
                    lambda *a: (_ for _ in ()).throw(OSError(SECRET.decode())),
                )
            original(event, classification)

        h.journal.record = record
        with pytest.raises(gen.GenerationError) as caught:
            h.run()
        assert SECRET.decode() not in str(caught.value)
        assert h.journal.failed and h.mutex.released
        assert len([c for c in h.store.calls if c[0] == "write"]) == (
            stage == "SECRET_WRITE_INTENT"
        )
        assert not any(c[0] == "delete" for c in h.store.calls)


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_interruption_after_entering_write_never_cleans(tmp_path, interrupt):
    with harness(tmp_path) as h:
        write = h.store.write

        def interrupted(target, value):
            write(target, value)
            raise interrupt()

        h.store.write = interrupted
        with pytest.raises(interrupt):
            h.run()
        records = [json.loads(line) for line in h.path.read_bytes().splitlines()]
        assert records[-1]["classification"] == "WRITE_OUTCOME_AMBIGUOUS"
        assert not any(c[0] == "delete" for c in h.store.calls)
        assert h.mutex.released and all(not any(v) for v in h.values)


def test_unknown_initial_state_blocks_without_mutation(tmp_path):
    with harness(tmp_path) as h:
        h.store.fail = ("read", gen.TARGETS[0])
        assert h.run() == "BLOCKED_EXISTING_V3_STATE"
        assert all(c[0] == "read" for c in h.store.calls)


def test_no_environment_or_v2_fallback_in_shared_reader(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", KEY.decode())
    monkeypatch.setenv("APCA_API_SECRET_KEY", SECRET.decode())
    monkeypatch.setenv(
        "ALPACA_API_KEY_ID_CREDENTIAL_TARGET",
        "AITradingBot/MarketData/Alpaca/ApiKeyId/v2",
    )
    calls = []

    class Reader:
        def read_fixed(self, target):
            calls.append(target)
            assert target in gen.TARGETS
            return None

    monkeypatch.setattr(creds, "_WindowsCredentialReader", Reader)
    with pytest.raises(creds.AlpacaCredentialReadError):
        creds.read_current_product_alpaca_secrets()
    assert calls == list(gen.TARGETS)


def test_fenced_generation_stays_fenced_after_read_only_reconciliation(tmp_path):
    witnesses = tuple(
        gen.credential_witness(r, bytearray(v))
        for r, v in zip(gen.ROLES, (KEY, SECRET), strict=True)
    )
    preserved = gen.PreservedGeneration(HEAD, TREE, witnesses, True, False, True)
    with harness(tmp_path) as h:
        h.store.entries = dict(zip(gen.TARGETS, (KEY, SECRET), strict=True))
        assert h.run(preserved=preserved) == "RECONCILED_PAIR_MATCH"
        assert gen.parse_generation_journal(h.path.read_bytes()).provider_fenced
        assert all(c[0] == "read" for c in h.store.calls)


def test_host_provision_and_reconciliation_are_distinct(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(host, "admit_authentication_source", lambda *a: ())
    mutex = Mutex()
    entries = {}

    class LocalStore:
        def read(self, target):
            assert mutex.owned and target in gen.TARGETS
            return None if target not in entries else bytearray(entries[target])

        def write(self, target, value):
            assert mutex.owned and target not in entries
            entries[target] = bytes(value)
            return True

        def delete(self, target):
            pytest.fail("delete")

    monkeypatch.setattr(host, "WindowsV3CredentialStore", LocalStore)
    monkeypatch.setattr(host, "WindowsV3Exclusion", lambda: mutex)
    monkeypatch.setattr(
        host, "interactive_generation_pair", lambda: (bytearray(KEY), bytearray(SECRET))
    )
    path = tmp_path / "provision.json"
    common = ["--expected-head", HEAD, "--expected-tree", TREE]
    assert (
        host.main(
            common
            + ["--evidence", str(path), "--provision-v3", host.PROVISION_INTERLOCK]
        )
        == 0
    )
    prior = path.read_bytes()
    monkeypatch.setattr(
        host, "interactive_generation_pair", lambda: pytest.fail("interactive")
    )
    digest = hashlib.sha256(prior).hexdigest()
    args = common + [
        "--evidence",
        str(tmp_path / "reconcile.json"),
        "--reconcile-v3",
        host.RECONCILE_INTERLOCK,
        "--preserved-evidence",
        str(path),
        "--preserved-sha256",
        digest,
    ]
    assert host.main(args) == 0 and path.read_bytes() == prior
    output = capsys.readouterr()
    assert (
        "RECONCILED_PAIR_MATCH" in output.out
        and SECRET.decode() not in output.out + output.err
    )


def test_native_writer_uses_fixed_generic_local_machine_and_clears_copy(monkeypatch):
    observed = []

    class Function:
        def __call__(self, pointer, flags):
            record = pointer._obj
            assert record.TargetName == gen.TARGETS[0]
            assert record.Type == 1 and record.Persist == 2 and flags == 0
            assert (
                ctypes.string_at(record.CredentialBlob, record.CredentialBlobSize)
                == KEY
            )
            return True

    def clear(copy):
        observed.append(copy)
        gen.clear_credential(copy)

    monkeypatch.setattr(native, "clear_credential", clear)
    monkeypatch.setattr(
        native.ctypes, "WinDLL", lambda *a, **kw: SimpleNamespace(CredWriteW=Function())
    )
    value = bytearray(KEY)
    assert native.WindowsV3CredentialStore().write(gen.TARGETS[0], value)
    assert value == bytearray(KEY)  # caller owns original, adapter clears only its copy
    assert len(observed) == 1 and not any(observed[0])


def test_getpass_echo_fallback_is_rejected_and_first_value_cleared(monkeypatch):
    monkeypatch.setattr(host.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(host.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda *a: host.STAGING_CONFIRMATION)
    calls = []

    def input_value(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return KEY.decode()
        import warnings

        warnings.warn("echo fallback", host.getpass.GetPassWarning, stacklevel=2)
        pytest.fail("echo fallback accepted")

    monkeypatch.setattr(host.getpass, "getpass", input_value)
    with pytest.raises(gen.GenerationError, match="input rejected"):
        host.interactive_generation_pair()


def test_mutex_continuity_loss_prevents_second_write_and_cleanup(tmp_path):
    with harness(tmp_path) as h:
        original = h.journal.record

        def record(event, classification=None):
            original(event, classification)
            if event == "SECRET_WRITE_INTENT":
                h.mutex.owned = False

        h.journal.record = record
        assert h.run() == "WRITE_OUTCOME_AMBIGUOUS"
        assert len([c for c in h.store.calls if c[0] == "write"]) == 1
        assert not any(c[0] == "delete" for c in h.store.calls)


def test_release_uncertainty_poisons_later_admission(kernel, monkeypatch):
    original = native.ctypes.WinDLL
    api = original("kernel32")
    api.ReleaseMutex.callback = lambda *a: False
    monkeypatch.setattr(native.ctypes, "WinDLL", lambda *a, **kw: api)
    mutex = native.WindowsV3Exclusion()
    assert mutex.acquire()
    with pytest.raises(gen.GenerationError, match="release uncertain"):
        mutex.release()
    count = len(kernel.calls)
    with pytest.raises(gen.GenerationError, match="unavailable"):
        native.WindowsV3Exclusion().acquire()
    assert len(kernel.calls) == count
