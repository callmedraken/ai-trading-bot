from __future__ import annotations

import ctypes
import os

import pytest

from trading_bot.runtime.windows_credentials import (
    CRED_MAX_CREDENTIAL_BLOB_SIZE,
    CRED_PERSIST_LOCAL_MACHINE,
    CRED_TYPE_GENERIC,
    MAX_WINDOWS_CREDENTIAL_BLOB_BYTES,
    CtypesWindowsCredentialNativeApi,
    NativeCredentialEntry,
    WindowsCredentialInvalidError,
    WindowsCredentialManagerReader,
    WindowsCredentialNotFoundError,
    WindowsCredentialSidMismatchError,
    WindowsCredentialUnsupportedError,
)

from .isolated_capture_test_support import OWNER_SID, install_child_case

KEY = "TEST-KEY-ID-VALUE"
SECRET = "TEST-SECRET-VALUE"


class FakeNativeCredentialApi:
    def __init__(self, sid: str = OWNER_SID) -> None:
        self.sid = sid
        self.reads: list[str] = []
        self.releases: list[NativeCredentialEntry] = []
        self.entries: dict[str, NativeCredentialEntry | Exception] = {}

    def current_process_sid(self) -> str:
        return self.sid

    def read_generic(self, target_name: str) -> NativeCredentialEntry:
        self.reads.append(target_name)
        value = self.entries[target_name]
        if isinstance(value, Exception):
            raise value
        return value

    def release(self, entry: NativeCredentialEntry) -> None:
        for index in range(len(entry.blob)):
            entry.blob[index] = 0
        entry.released = True
        self.releases.append(entry)


def _reader_case(tmp_path):
    case = install_child_case(tmp_path)
    reference = case["credential"]
    api = FakeNativeCredentialApi()
    api.entries = {
        reference.api_key_id_target_name: NativeCredentialEntry(
            reference.api_key_id_target_name,
            CRED_TYPE_GENERIC,
            CRED_PERSIST_LOCAL_MACHINE,
            bytearray(KEY.encode()),
        ),
        reference.api_secret_key_target_name: NativeCredentialEntry(
            reference.api_secret_key_target_name,
            CRED_TYPE_GENERIC,
            CRED_PERSIST_LOCAL_MACHINE,
            bytearray(SECRET.encode()),
        ),
    }
    return reference, api, WindowsCredentialManagerReader(api)


def test_fake_credential_manager_success_and_cleanup(tmp_path) -> None:
    reference, api, reader = _reader_case(tmp_path)

    scope = reader.read(reference)
    mapping = scope.as_provider_mapping()
    scope.close()

    assert mapping == {
        "APCA_API_KEY_ID": KEY,
        "APCA_API_SECRET_KEY": SECRET,
    }
    assert api.reads == [
        reference.api_key_id_target_name,
        reference.api_secret_key_target_name,
    ]
    assert len(api.releases) == 2
    assert all(entry.released and not any(entry.blob) for entry in api.releases)
    assert KEY not in repr(scope)
    assert SECRET not in str(scope)


def test_sid_mismatch_happens_before_any_credential_read(tmp_path) -> None:
    reference, api, reader = _reader_case(tmp_path)
    api.sid = "S-1-5-21-999-888-777-1001"

    with pytest.raises(WindowsCredentialSidMismatchError):
        reader.read(reference)

    assert api.reads == []
    assert api.releases == []


def test_missing_key_is_sanitized(tmp_path) -> None:
    reference, api, reader = _reader_case(tmp_path)
    api.entries[reference.api_key_id_target_name] = WindowsCredentialNotFoundError(
        "credential was not found"
    )

    with pytest.raises(WindowsCredentialNotFoundError) as caught:
        reader.read(reference)

    message = str(caught.value)
    assert KEY not in message
    assert SECRET not in message
    assert reference.api_key_id_target_name not in message


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("credential_type", 2),
        ("persistence", 3),
        ("blob", bytearray()),
        ("blob", bytearray(b"x" * (MAX_WINDOWS_CREDENTIAL_BLOB_BYTES + 1))),
        ("native_blob_size", MAX_WINDOWS_CREDENTIAL_BLOB_BYTES + 1),
        ("blob", bytearray(b"bad\nvalue")),
        ("blob", bytearray(b"\xff")),
    ],
)
def test_invalid_credential_entries_fail_closed(
    tmp_path, field: str, value: object
) -> None:
    reference, api, reader = _reader_case(tmp_path)
    entry = api.entries[reference.api_key_id_target_name]
    assert isinstance(entry, NativeCredentialEntry)
    setattr(entry, field, value)

    with pytest.raises(WindowsCredentialInvalidError) as caught:
        reader.read(reference)

    assert KEY not in str(caught.value)
    assert SECRET not in str(caught.value)
    assert api.releases
    assert all(entry.released and not any(entry.blob) for entry in api.releases)


def test_native_entry_repr_and_str_are_redacted() -> None:
    entry = NativeCredentialEntry(
        "target",
        CRED_TYPE_GENERIC,
        CRED_PERSIST_LOCAL_MACHINE,
        bytearray(SECRET.encode()),
        native_pointer=object(),
    )

    assert SECRET not in repr(entry)
    assert SECRET not in str(entry)
    assert "target" not in repr(entry)


def test_native_cleanup_failure_fails_closed(tmp_path) -> None:
    reference, api, reader = _reader_case(tmp_path)

    def fail_release(entry) -> None:
        del entry
        raise RuntimeError(f"native cleanup failed {SECRET}")

    api.release = fail_release  # type: ignore[method-assign]

    with pytest.raises(WindowsCredentialInvalidError) as caught:
        reader.read(reference)

    assert SECRET not in str(caught.value)


@pytest.mark.parametrize(
    "size", [8, MAX_WINDOWS_CREDENTIAL_BLOB_BYTES + 1, CRED_MAX_CREDENTIAL_BLOB_SIZE]
)
def test_native_release_zeroes_entire_reported_blob_before_free(size: int) -> None:
    native_buffer = (ctypes.c_ubyte * size)(*([7] * size))
    zero_calls: list[tuple[int, int]] = []
    freed: list[object] = []
    events: list[str] = []

    api = object.__new__(CtypesWindowsCredentialNativeApi)

    def zero(address: int, length: int) -> None:
        events.append("zero")
        zero_calls.append((address, length))
        ctypes.memset(address, 0, length)

    class Advapi:
        def CredFree(self, pointer: object) -> None:
            events.append("free")
            freed.append(pointer)

    api._zero_memory = zero
    api._advapi32 = Advapi()
    entry = NativeCredentialEntry(
        "redacted-target",
        CRED_TYPE_GENERIC,
        CRED_PERSIST_LOCAL_MACHINE,
        bytearray(b"x" * MAX_WINDOWS_CREDENTIAL_BLOB_BYTES),
        native_pointer=object(),
        native_blob_address=ctypes.addressof(native_buffer),
        native_blob_size=size,
    )

    api.release(entry)
    api.release(entry)

    assert zero_calls == [(ctypes.addressof(native_buffer), size)]
    assert events == ["zero", "free"]
    assert not any(native_buffer)
    assert len(freed) == 1
    assert entry.released is True
    assert entry.native_pointer is None
    assert not any(entry.blob)


@pytest.mark.parametrize(
    ("address", "size"),
    [
        (0, 1),
        ((1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1, 2),
        (1, CRED_MAX_CREDENTIAL_BLOB_SIZE + 1),
    ],
)
def test_native_release_invalid_range_never_zeroes_and_frees_once(
    address: int, size: int
) -> None:
    events: list[str] = []
    api = object.__new__(CtypesWindowsCredentialNativeApi)

    def zero(_address: int, _length: int) -> None:
        events.append("zero")

    class Advapi:
        def CredFree(self, _pointer: object) -> None:
            events.append("free")

    api._zero_memory = zero
    api._advapi32 = Advapi()
    entry = NativeCredentialEntry(
        "redacted-target",
        CRED_TYPE_GENERIC,
        CRED_PERSIST_LOCAL_MACHINE,
        bytearray(b"x"),
        native_pointer=object(),
        native_blob_address=address,
        native_blob_size=size,
    )

    with pytest.raises(WindowsCredentialInvalidError) as caught:
        api.release(entry)
    assert str(caught.value) == "native credential cleanup failed"
    assert events == ["free"]
    api.release(entry)
    assert events == ["free"]


def test_native_read_copies_no_more_than_approved_bound() -> None:
    class Credential(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.c_uint32),
            ("Type", ctypes.c_uint32),
            ("TargetName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("LastWrittenLow", ctypes.c_uint32),
            ("LastWrittenHigh", ctypes.c_uint32),
            ("CredentialBlobSize", ctypes.c_uint32),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", ctypes.c_uint32),
            ("AttributeCount", ctypes.c_uint32),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]

    size = CRED_MAX_CREDENTIAL_BLOB_SIZE
    native_buffer = (ctypes.c_ubyte * size)(*([3] * size))
    credential = Credential(
        Type=CRED_TYPE_GENERIC,
        TargetName="target",
        CredentialBlobSize=size,
        CredentialBlob=ctypes.cast(native_buffer, ctypes.POINTER(ctypes.c_ubyte)),
        Persist=CRED_PERSIST_LOCAL_MACHINE,
    )

    class Advapi:
        def CredReadW(self, _target: str, _kind: int, _flags: int, output) -> int:
            ctypes.cast(output, ctypes.POINTER(ctypes.POINTER(Credential)))[0] = (
                ctypes.pointer(credential)
            )
            return 1

        def CredFree(self, _pointer: object) -> None:
            return None

    api = object.__new__(CtypesWindowsCredentialNativeApi)
    api._credential_type = Credential
    api._advapi32 = Advapi()
    api._zero_memory = lambda address, length: ctypes.memset(address, 0, length)

    entry = api.read_generic("target")
    assert len(entry.blob) == MAX_WINDOWS_CREDENTIAL_BLOB_BYTES
    assert entry.native_blob_size == size
    api.release(entry)
    assert not any(native_buffer)


@pytest.mark.parametrize("failure", ["overflow", "null-address", "address-overflow"])
def test_native_read_invalid_range_skips_zero_and_frees_once(failure: str) -> None:
    class Credential(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.c_uint32),
            ("Type", ctypes.c_uint32),
            ("TargetName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("LastWrittenLow", ctypes.c_uint32),
            ("LastWrittenHigh", ctypes.c_uint32),
            ("CredentialBlobSize", ctypes.c_uint64),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", ctypes.c_uint32),
            ("AttributeCount", ctypes.c_uint32),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]

    max_address = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1
    if failure == "overflow":
        size = CRED_MAX_CREDENTIAL_BLOB_SIZE + 1
        pointer = ctypes.POINTER(ctypes.c_ubyte)()
    elif failure == "null-address":
        size = 1
        pointer = ctypes.POINTER(ctypes.c_ubyte)()
    else:
        size = 2
        pointer = ctypes.cast(
            ctypes.c_void_p(max_address), ctypes.POINTER(ctypes.c_ubyte)
        )
    credential = Credential(
        Type=CRED_TYPE_GENERIC,
        TargetName="target",
        CredentialBlobSize=size,
        CredentialBlob=pointer,
        Persist=CRED_PERSIST_LOCAL_MACHINE,
    )
    events: list[str] = []
    zero_calls: list[tuple[int, int]] = []

    class Advapi:
        def CredReadW(self, _target: str, _kind: int, _flags: int, output) -> int:
            ctypes.cast(output, ctypes.POINTER(ctypes.POINTER(Credential)))[0] = (
                ctypes.pointer(credential)
            )
            return 1

        def CredFree(self, _pointer: object) -> None:
            events.append("free")

    api = object.__new__(CtypesWindowsCredentialNativeApi)
    api._credential_type = Credential
    api._advapi32 = Advapi()

    def zero(address: int, length: int) -> None:
        events.append("zero")
        zero_calls.append((address, length))

    api._zero_memory = zero
    with pytest.raises(WindowsCredentialInvalidError) as caught:
        api.read_generic("target")
    assert str(caught.value) == "credential read cleanup failed"
    assert zero_calls == []
    assert events == ["free"]


@pytest.mark.skipif(os.name == "nt", reason="non-Windows fail-closed assertion")
def test_real_adapter_is_unsupported_off_windows() -> None:
    with pytest.raises(WindowsCredentialUnsupportedError):
        CtypesWindowsCredentialNativeApi()
