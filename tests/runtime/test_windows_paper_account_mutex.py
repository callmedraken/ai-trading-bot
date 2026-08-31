"""Native-call contract tests use fake kernel handles; no global objects by default."""

from __future__ import annotations

import ctypes
import hashlib
import os
import threading
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.runtime.windows_paper_account_mutex as mutex
import trading_bot.runtime.windows_paper_account_security as security
from trading_bot.runtime.windows_authority import (
    AuthorityPathError,
    AuthoritySecurityError,
    require_fixed_authority_tree_path,
)
from trading_bot.runtime.windows_authority_security import (
    FILE_ALL_ACCESS,
    MUTEX_ALL_ACCESS,
    MUTEX_MODIFY_STATE,
    READ_CONTROL,
    SYNCHRONIZE,
    AuthorityObjectKind,
    SecurityAce,
    SecurityInspection,
    require_security_policy,
)

SID = "S-1-5-21-1-2-3-1009"
ACCOUNT = UUID("fd64eb7d-50c3-4ea4-9a5a-142c465f5a95")


class NativeFunction:
    def __init__(self, implementation):
        self.implementation = implementation

    def __call__(self, *args):
        return self.implementation(*args)


class Native:
    def __init__(
        self, wait_result=0, *, create_result=17, release_result=1, close_result=1
    ):
        self.calls = []
        self.CreateMutexExW = NativeFunction(
            lambda *args: self.call("create", args, create_result)
        )
        self.WaitForSingleObject = NativeFunction(
            lambda *args: self.call("wait", args, wait_result)
        )
        self.ReleaseMutex = NativeFunction(
            lambda *args: self.call("release", args, release_result)
        )
        self.CloseHandle = NativeFunction(
            lambda *args: self.call("close", args, close_result)
        )

    def call(self, name, args, result):
        self.calls.append((name, args))
        return result


def install_native(monkeypatch, native, *, owner=SID, protected=True, aces=None):
    policy = mutex.paper_account_mutex_security_policy(SID, owner_sid=SID)
    monkeypatch.setattr(mutex, "require_windows_platform", lambda: None)
    monkeypatch.setattr(mutex.ctypes, "WinDLL", lambda *a, **kw: native)
    monkeypatch.setattr(mutex, "resolve_current_token_sid", lambda: SID)
    monkeypatch.setattr(
        mutex,
        "inspect_handle_security",
        lambda *a: (owner, protected, policy.aces if aces is None else aces),
    )

    @contextmanager
    def attributes(observed):
        assert observed == policy
        yield SimpleNamespace(attributes=ctypes.c_int(0))

    monkeypatch.setattr(mutex, "build_security_attributes", attributes)


def test_exact_frozen_identity_material():
    material = (
        b'{"label":"manual-paper-account/v1",'
        b'"paper_account_id":"fd64eb7d-50c3-4ea4-9a5a-142c465f5a95"}'
    )
    assert mutex.canonical_paper_account_mutex_material(ACCOUNT) == material
    assert (
        mutex.paper_account_mutex_name(ACCOUNT)
        == "Global\\AITradingBot-Paper-v1-" + hashlib.sha256(material).hexdigest()
    )
    assert mutex.paper_account_mutex_name(
        UUID(int=1)
    ) != mutex.paper_account_mutex_name(ACCOUNT)
    with pytest.raises(mutex.PaperAccountMutexError):
        mutex.paper_account_mutex_name(str(ACCOUNT))
    lock = mutex.GlobalPaperAccountMutex(ACCOUNT, trading_sid=SID)
    with pytest.raises(AttributeError):
        lock.name = "Global\\wrong-account"
    with pytest.raises(AttributeError):
        lock.acquisition = object()


def test_mutex_exact_security_masks_and_protection():
    policy = mutex.paper_account_mutex_security_policy(SID, owner_sid=SID)
    assert policy.dacl_protected is True
    assert policy.aces == (
        SecurityAce("S-1-5-32-544", MUTEX_ALL_ACCESS),
        SecurityAce("S-1-5-18", MUTEX_ALL_ACCESS),
        SecurityAce(SID, MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE),
    )


@pytest.mark.parametrize(
    "token,elevated,admin,expected",
    [
        (SID, False, False, SID),
        ("S-1-5-18", False, False, "S-1-5-18"),
        ("S-1-5-21-9-8-7-1001", True, True, "S-1-5-32-544"),
        ("S-1-5-21-9-8-7-1001", False, True, None),
        ("S-1-5-21-9-8-7-1001", True, False, None),
    ],
)
def test_approved_owner_selection(token, elevated, admin, expected):
    if expected is None:
        with pytest.raises(mutex.PaperAccountMutexError):
            mutex.select_paper_account_mutex_owner(
                SID, token, token_is_elevated=elevated, token_is_administrator=admin
            )
    else:
        assert (
            mutex.select_paper_account_mutex_owner(
                SID, token, token_is_elevated=elevated, token_is_administrator=admin
            )
            == expected
        )


@pytest.mark.parametrize("wait_result", [0, 0x80])
def test_native_acquire_release_close_once_and_retain_abandonment(
    monkeypatch, wait_result
):
    native = Native(wait_result)
    install_native(monkeypatch, native)
    lock = mutex.GlobalPaperAccountMutex(ACCOUNT, trading_sid=SID)
    with lock:
        assert lock.acquisition.was_abandoned == (wait_result == 0x80)
        with pytest.raises(mutex.PaperAccountMutexError, match="already active"):
            lock.acquire()
    lock.release()
    assert [name for name, _ in native.calls] == ["create", "wait", "release", "close"]
    create = native.calls[0][1]
    assert create[1:] == (
        mutex.paper_account_mutex_name(ACCOUNT),
        0,
        MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE,
    )
    assert native.calls[1][1] == (17, 0xFFFFFFFF)


@pytest.mark.parametrize(
    "failure",
    [
        "owner",
        "unprotected",
        "aces",
        "wait_failed",
        "wait_timeout",
        "create",
        "release",
        "close",
    ],
)
def test_native_security_and_failure_cleanup(monkeypatch, failure):
    native = Native(
        0xFFFFFFFF
        if failure == "wait_failed"
        else 258
        if failure == "wait_timeout"
        else 0,
        create_result=0 if failure == "create" else 17,
        release_result=0 if failure == "release" else 1,
        close_result=0 if failure == "close" else 1,
    )
    install_native(
        monkeypatch,
        native,
        owner="S-1-5-21-9-9-9-999" if failure == "owner" else SID,
        protected=failure != "unprotected",
        aces=() if failure == "aces" else None,
    )
    with pytest.raises(mutex.PaperAccountMutexError):
        with mutex.GlobalPaperAccountMutex(ACCOUNT, trading_sid=SID):
            pass
    calls = [name for name, _ in native.calls]
    assert calls.count("close") == (0 if failure == "create" else 1)
    assert calls.count("release") == (1 if failure in {"release", "close"} else 0)
    if failure in {"owner", "unprotected", "aces"}:
        assert "wait" not in calls


def test_competing_holders_serialize_using_kernel_seam(monkeypatch):
    gate = threading.Lock()
    entered = threading.Event()
    attempting = threading.Event()
    second_entered = threading.Event()
    native = Native()
    native.WaitForSingleObject = NativeFunction(lambda *a: (gate.acquire(), 0)[1])
    native.ReleaseMutex = NativeFunction(lambda *a: (gate.release(), 1)[1])
    install_native(monkeypatch, native)

    def competitor():
        entered.wait(2)
        attempting.set()
        with mutex.GlobalPaperAccountMutex(ACCOUNT, trading_sid=SID):
            second_entered.set()

    thread = threading.Thread(target=competitor)
    thread.start()
    with mutex.GlobalPaperAccountMutex(ACCOUNT, trading_sid=SID):
        entered.set()
        assert attempting.wait(2)
        assert not second_entered.wait(0.05)
    thread.join(2)
    assert not thread.is_alive() and second_entered.is_set()


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AITradingBot\Authority",
        r"F:\AITradingBot\PaperElsewhere",
        r"F:\AITradingBot\Paper\..\Authority",
        r"F:\AITradingBot\Paper\anchor:stream",
        r"\\?\F:\AITradingBot\Paper",
        r"\\.\F:\AITradingBot\Paper",
        r"F:\AITradingBot\Paper\trailing.",
        r"F:/AITradingBot/Paper",
    ],
)
def test_paper_guard_rejects_aliases_and_does_not_widen_c1(path):
    with pytest.raises(security.PaperAccountSecurityError):
        security.require_fixed_paper_path(path)
    with pytest.raises(AuthorityPathError):
        require_fixed_authority_tree_path(r"F:\AITradingBot\Paper")


@pytest.mark.parametrize(
    "role",
    [
        "root",
        "anchor",
        "genesis-file",
        "genesis-directory",
        "output-file",
        "output-directory",
    ],
)
@pytest.mark.parametrize(
    "drift", ["owner", "dacl", "unprotected", "inherited", "reparse"]
)
def test_paper_security_policy_blocks_owner_acl_inheritance_drift(role, drift):
    policy = security.paper_account_security_policy(role, SID)
    inspection = SecurityInspection(
        r"F:\AITradingBot\Paper",
        r"F:\AITradingBot\Paper",
        AuthorityObjectKind.DIRECTORY,
        policy.owner_sid,
        True,
        policy.aces,
        False,
        "F:\\",
        "NTFS",
    )
    if drift == "owner":
        inspection = replace(inspection, owner_sid="S-1-5-21-9-9-9-999")
    elif drift == "dacl":
        inspection = replace(
            inspection, aces=(*policy.aces, SecurityAce("S-1-1-0", FILE_ALL_ACCESS))
        )
    elif drift == "unprotected":
        inspection = replace(inspection, dacl_protected=False)
    elif drift == "inherited":
        inspection = replace(
            inspection, aces=(*policy.aces[:-1], replace(policy.aces[-1], ace_flags=16))
        )
    else:
        inspection = replace(inspection, is_reparse_point=True)
    with pytest.raises(AuthoritySecurityError):
        require_security_policy(inspection, policy)


@pytest.mark.skipif(
    os.environ.get("AI_TRADING_BOT_P3_NATIVE_MUTEX_TEST") != "1" or os.name != "nt",
    reason="explicit opt-in native Windows mutex test",
)
def test_native_windows_mutex_opt_in():
    from trading_bot.runtime.windows_authority_security import resolve_current_token_sid

    # Dedicated test account identity, never the production account ID.
    account = UUID("6d9617f5-0922-4c91-a06b-bc82c1348780")
    with mutex.GlobalPaperAccountMutex(
        account, trading_sid=resolve_current_token_sid()
    ) as lock:
        assert lock.acquisition.name == mutex.paper_account_mutex_name(account)


class FileNative:
    """Minimal disk-handle simulator exercises the actual P3 native reader."""

    def __init__(self, payload=b"canonical bytes"):
        self.payload = payload
        self.opened = {}
        self.positions = {}
        self.closed = []
        self.opens = []
        self.unsafe = 0
        self.file_type = 1
        self.identity_delta = 0
        self.CreateFileW = NativeFunction(self.create)
        self.CloseHandle = NativeFunction(
            lambda handle: (self.closed.append(handle), 1)[1]
        )
        self.GetFileType = NativeFunction(lambda handle: self.file_type)
        self.GetFileInformationByHandle = NativeFunction(self.info)
        self.GetFinalPathNameByHandleW = NativeFunction(self.final)
        self.ReadFile = NativeFunction(self.read)
        self.SetFilePointerEx = NativeFunction(self.seek)

    def create(self, path, access, sharing, attrs, disposition, flags, template):
        handle = 100 + len(self.opened)
        self.opened[handle] = (path, bool(flags & security.FILE_FLAG_BACKUP_SEMANTICS))
        self.positions[handle] = 0
        self.opens.append((path, access, sharing, disposition, flags))
        return handle

    def info(self, handle, pointer):
        value = pointer._obj
        directory = self.opened[handle][1]
        value.attributes = (0x10 if directory else 0x80) | self.unsafe
        value.volume = 1
        value.index_low = handle + self.identity_delta
        value.size_low = 0 if directory else len(self.payload)
        value.links = 1
        return 1

    def final(self, handle, buffer, length, flags):
        buffer.value = "\\\\?\\" + self.opened[handle][0]
        return len(buffer.value)

    def seek(self, handle, distance, unused, method):
        self.positions[handle] = 0
        return 1

    def read(self, handle, buffer, size, count, unused):
        start = self.positions[handle]
        value = self.payload[start : start + size]
        ctypes.memmove(buffer, value, len(value))
        count._obj.value = len(value)
        self.positions[handle] += len(value)
        return 1


def install_file_native(monkeypatch, native, *, bad_acl=False):
    monkeypatch.setattr(security, "require_windows_platform", lambda: None)
    monkeypatch.setattr(security.ctypes, "WinDLL", lambda *a, **kw: native)
    monkeypatch.setattr(security, "enumerate_paper_directory", lambda *a: ())

    def inspection(handle, path, kind):
        if path.endswith("capture-output"):
            policy = security.authority_security_policy("capture-output", SID)
        elif path.endswith("Authority"):
            policy = security.authority_security_policy("authority", SID)
        else:
            policy = security.paper_account_security_policy(
                "root" if kind is AuthorityObjectKind.DIRECTORY else "anchor", SID
            )
        return SecurityInspection(
            path,
            path,
            kind,
            policy.owner_sid,
            not bad_acl,
            policy.aces,
            False,
            "F:\\",
            "NTFS",
        )

    monkeypatch.setattr(security, "inspect_open_authority_object", inspection)


def test_native_file_reader_pins_parent_and_never_requests_writes(monkeypatch):
    native = FileNative()
    install_file_native(monkeypatch, native)
    root = r"F:\AITradingBot\Paper"
    with security.WindowsPaperAccountReadSession(SID) as reader:
        reader.inventory(root, "root", 3)
        path = root + r"\manual-paper-account-authority.json"
        assert reader.read(path, "anchor", 100) == native.payload
        assert reader.read(path, "anchor", 100) == native.payload
        reader.finish()
        assert native.closed == []
    assert len(native.closed) == len(native.opened) == 3
    assert native.opens[0][:3] == (r"F:\AITradingBot", 0, 3)
    assert all(
        disposition == security.OPEN_EXISTING
        for _, _, _, disposition, _ in native.opens
    )
    assert all(
        flags & security.FILE_FLAG_OPEN_REPARSE_POINT for *_, flags in native.opens
    )
    assert native.opens[-1][1:3] == (
        security.FILE_READ_DATA | READ_CONTROL | security.FILE_READ_ATTRIBUTES,
        1,
    )


@pytest.mark.parametrize(
    "failure",
    [
        "acl",
        "reparse",
        "device_attribute",
        "pipe",
        "identity",
        "bound",
        "read_error",
        "parent_substitution",
    ],
)
def test_native_reader_fail_closed_and_closes_every_handle(monkeypatch, failure):
    native = FileNative()
    install_file_native(monkeypatch, native, bad_acl=failure == "acl")
    if failure == "reparse":
        native.unsafe = 0x400
    elif failure == "device_attribute":
        native.unsafe = 0x40
    elif failure == "pipe":
        native.file_type = 3
    elif failure == "parent_substitution":
        native.GetFinalPathNameByHandleW = NativeFunction(lambda *a: 0)
    with pytest.raises((security.PaperAccountSecurityError, AuthoritySecurityError)):
        with security.WindowsPaperAccountReadSession(SID) as reader:
            root = r"F:\AITradingBot\Paper"
            reader.inventory(root, "root", 3)
            if failure == "read_error":
                native.ReadFile = NativeFunction(lambda *a: 0)
            reader.read(
                root + r"\manual-paper-account-authority.json",
                "anchor",
                1 if failure == "bound" else 100,
            )
            if failure == "identity":
                native.identity_delta = 1
            reader.finish()
    assert len(native.closed) == len(native.opened)


def test_native_historical_reader_pins_exact_c1_parents_without_listing(monkeypatch):
    native = FileNative()
    install_file_native(monkeypatch, native)

    def forbidden(*args):
        raise AssertionError("capture-output listing forbidden")

    monkeypatch.setattr(security, "enumerate_paper_directory", forbidden)
    path = (
        r"F:\AITradingBot\Authority\capture-output\daily-market-data-snapshot-"
        + str(ACCOUNT)
        + ".json"
    )
    with security.WindowsPaperAccountReadSession(SID) as reader:
        assert reader.read(path, "snapshot", 100) == native.payload
        reader.finish()
    assert [item[0] for item in native.opens] == [
        r"F:\AITradingBot",
        r"F:\AITradingBot\Authority",
        r"F:\AITradingBot\Authority\capture-output",
        path,
    ]
