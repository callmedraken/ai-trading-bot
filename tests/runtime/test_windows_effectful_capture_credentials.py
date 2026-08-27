from __future__ import annotations

import ctypes
import os

import pytest

from trading_bot.runtime.windows_effectful_capture import (
    ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
    ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
)
from trading_bot.runtime.windows_effectful_capture_credentials import (
    CRED_MAX_CREDENTIAL_BLOB_SIZE,
    CRED_PERSIST_LOCAL_MACHINE,
    CRED_TYPE_GENERIC,
    MAX_WINDOWS_CREDENTIAL_BLOB_BYTES,
    CtypesWindowsCredentialNativeApi,
    NativeCredentialEntry,
    ScopedAlpacaSecrets,
    WindowsAlpacaCredentialManagerReader,
    WindowsCredentialInvalidError,
    WindowsCredentialNotFoundError,
    WindowsCredentialSidMismatchError,
    WindowsCredentialUnsupportedError,
)

_OWNER_SID = "S-1-5-21-111-222-333-1001"
_OTHER_SID = "S-1-5-21-999-888-777-1001"
_KEY = "TEST-KEY-ID-VALUE"
_SECRET = "TEST-SECRET-VALUE"
_V1_KEY_TARGET = "AITradingBot/MarketData/Alpaca/ApiKeyId/v1"
_V1_SECRET_TARGET = "AITradingBot/MarketData/Alpaca/ApiSecretKey/v1"


class FakeNativeCredentialApi:
    def __init__(self) -> None:
        self.reads: list[str] = []
        self.releases: list[NativeCredentialEntry] = []
        self.entries: dict[str, NativeCredentialEntry | Exception] = {
            ALPACA_API_KEY_ID_CREDENTIAL_TARGET: _entry(
                ALPACA_API_KEY_ID_CREDENTIAL_TARGET, _KEY
            ),
            ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET: _entry(
                ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET, _SECRET
            ),
        }
        self.release_error: Exception | None = None

    def read_generic(self, target_name: str) -> NativeCredentialEntry:
        self.reads.append(target_name)
        value = self.entries[target_name]
        if isinstance(value, Exception):
            raise value
        return value

    def release(self, entry: NativeCredentialEntry) -> None:
        if entry.released:
            return
        for index in range(len(entry.blob)):
            entry.blob[index] = 0
        entry.released = True
        self.releases.append(entry)
        if self.release_error is not None:
            raise self.release_error


def _entry(target: str, value: str) -> NativeCredentialEntry:
    return NativeCredentialEntry(
        target_name=target,
        credential_type=CRED_TYPE_GENERIC,
        persistence=CRED_PERSIST_LOCAL_MACHINE,
        blob=bytearray(value.encode()),
    )


def _reader(
    api: FakeNativeCredentialApi,
    *,
    sid: str = _OWNER_SID,
) -> WindowsAlpacaCredentialManagerReader:
    return WindowsAlpacaCredentialManagerReader.for_test(
        native_api=api,
        sid_resolver=lambda: sid,
    )


def test_success_reads_only_fixed_targets_after_sid_and_releases_native_entries() -> (
    None
):
    api = FakeNativeCredentialApi()
    reader = _reader(api)

    scope = reader.read(_OWNER_SID)
    observed: list[tuple[str, str]] = []
    result = scope.use(lambda key, secret: observed.append((key, secret)) or "used")
    scope.close()

    assert result == "used"
    assert observed == [(_KEY, _SECRET)]
    assert api.reads == [
        ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
        ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
    ]
    assert len(api.releases) == 2
    assert all(entry.released and not any(entry.blob) for entry in api.releases)
    assert _KEY not in repr(scope)
    assert _SECRET not in str(scope)
    assert not hasattr(scope, "api_key_id")
    assert not hasattr(scope, "api_secret_key")


def test_sid_mismatch_fails_before_any_credential_read() -> None:
    api = FakeNativeCredentialApi()
    reader = _reader(api, sid=_OTHER_SID)

    with pytest.raises(WindowsCredentialSidMismatchError, match="Trading SID"):
        reader.read(_OWNER_SID)

    assert api.reads == []
    assert api.releases == []


def test_invalid_approved_sid_fails_before_resolver_or_credential_read() -> None:
    api = FakeNativeCredentialApi()
    resolver_calls = 0

    def resolver() -> str:
        nonlocal resolver_calls
        resolver_calls += 1
        return _OWNER_SID

    reader = WindowsAlpacaCredentialManagerReader.for_test(
        native_api=api,
        sid_resolver=resolver,
    )

    with pytest.raises(WindowsCredentialInvalidError, match="SID"):
        reader.read("Trading")

    assert resolver_calls == 0
    assert api.reads == []


def test_sid_resolver_failure_is_sanitized() -> None:
    api = FakeNativeCredentialApi()

    def resolver() -> str:
        raise RuntimeError(f"SID lookup exposed {_SECRET}")

    reader = WindowsAlpacaCredentialManagerReader.for_test(
        native_api=api,
        sid_resolver=resolver,
    )

    with pytest.raises(WindowsCredentialInvalidError) as caught:
        reader.read(_OWNER_SID)

    assert str(caught.value) == "current process SID inspection failed"
    assert _SECRET not in str(caught.value)
    assert api.reads == []


def test_missing_first_credential_is_sanitized() -> None:
    api = FakeNativeCredentialApi()
    api.entries[ALPACA_API_KEY_ID_CREDENTIAL_TARGET] = WindowsCredentialNotFoundError(
        f"missing {_SECRET}"
    )
    reader = _reader(api)

    with pytest.raises(WindowsCredentialNotFoundError) as caught:
        reader.read(_OWNER_SID)

    assert str(caught.value) == "credential was not found"
    assert _KEY not in str(caught.value)
    assert _SECRET not in str(caught.value)
    assert ALPACA_API_KEY_ID_CREDENTIAL_TARGET not in str(caught.value)
    assert api.releases == []


@pytest.mark.parametrize(
    ("missing_target", "error"),
    [
        (
            ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
            WindowsCredentialNotFoundError("credential was not found"),
        ),
        (
            ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
            WindowsCredentialInvalidError("credential value is malformed"),
        ),
    ],
)
def test_missing_or_malformed_v2_never_falls_back_to_v1(
    missing_target: str,
    error: Exception,
) -> None:
    api = FakeNativeCredentialApi()
    api.entries[_V1_KEY_TARGET] = _entry(_V1_KEY_TARGET, "QUARANTINED-V1-KEY")
    api.entries[_V1_SECRET_TARGET] = _entry(_V1_SECRET_TARGET, "QUARANTINED-V1-SECRET")
    api.entries[missing_target] = error
    reader = _reader(api)

    with pytest.raises((WindowsCredentialNotFoundError, WindowsCredentialInvalidError)):
        reader.read(_OWNER_SID)

    assert _V1_KEY_TARGET not in api.reads
    assert _V1_SECRET_TARGET not in api.reads
    assert api.reads[0] == ALPACA_API_KEY_ID_CREDENTIAL_TARGET
    assert all(target.endswith("/v2") for target in api.reads)


def test_native_read_error_is_sanitized() -> None:
    api = FakeNativeCredentialApi()
    api.entries[ALPACA_API_KEY_ID_CREDENTIAL_TARGET] = WindowsCredentialInvalidError(
        f"native read exposed {_SECRET}"
    )
    reader = _reader(api)

    with pytest.raises(WindowsCredentialInvalidError) as caught:
        reader.read(_OWNER_SID)

    assert str(caught.value) == "credential read failed"
    assert _SECRET not in str(caught.value)
    assert api.releases == []


def test_missing_second_credential_releases_first_entry() -> None:
    api = FakeNativeCredentialApi()
    api.entries[ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET] = (
        WindowsCredentialNotFoundError("credential was not found")
    )
    reader = _reader(api)

    with pytest.raises(WindowsCredentialNotFoundError):
        reader.read(_OWNER_SID)

    assert len(api.releases) == 1
    assert api.releases[0].target_name == ALPACA_API_KEY_ID_CREDENTIAL_TARGET
    assert not any(api.releases[0].blob)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("target_name", "alternate-target"),
        ("credential_type", 2),
        ("persistence", 3),
        ("blob", bytearray()),
        ("blob", bytearray(b"x" * (MAX_WINDOWS_CREDENTIAL_BLOB_BYTES + 1))),
        ("blob", bytearray(b" bad")),
        ("blob", bytearray(b"bad ")),
        ("blob", bytearray(b"bad\nvalue")),
        ("blob", bytearray(b"bad\0value")),
        ("blob", bytearray(b"\xff")),
    ],
)
def test_invalid_entries_fail_closed_and_are_released(
    field_name: str,
    value: object,
) -> None:
    api = FakeNativeCredentialApi()
    entry = api.entries[ALPACA_API_KEY_ID_CREDENTIAL_TARGET]
    assert isinstance(entry, NativeCredentialEntry)
    setattr(entry, field_name, value)
    reader = _reader(api)

    with pytest.raises(WindowsCredentialInvalidError) as caught:
        reader.read(_OWNER_SID)

    assert _KEY not in str(caught.value)
    assert _SECRET not in str(caught.value)
    assert api.releases == [entry]
    assert entry.released is True
    assert not any(entry.blob)


def test_native_metadata_requires_complete_bounded_exact_copy() -> None:
    api = FakeNativeCredentialApi()
    entry = api.entries[ALPACA_API_KEY_ID_CREDENTIAL_TARGET]
    assert isinstance(entry, NativeCredentialEntry)
    entry.native_pointer = object()
    entry.native_blob_address = 1
    entry.native_blob_size = len(entry.blob) + 1
    reader = _reader(api)

    with pytest.raises(WindowsCredentialInvalidError):
        reader.read(_OWNER_SID)

    assert entry.released is True


def test_cleanup_failure_fails_closed_and_does_not_expose_secret() -> None:
    api = FakeNativeCredentialApi()
    api.release_error = RuntimeError(f"cleanup leaked {_SECRET}")
    reader = _reader(api)

    with pytest.raises(WindowsCredentialInvalidError) as caught:
        reader.read(_OWNER_SID)

    assert str(caught.value) == "native credential cleanup failed"
    assert _SECRET not in str(caught.value)
    assert len(api.releases) == 2


def test_scoped_secrets_are_redacted_idempotently_closed_and_unusable_after_close() -> (
    None
):
    scope = ScopedAlpacaSecrets(_KEY, _SECRET)
    assert _KEY not in repr(scope)
    assert _SECRET not in str(scope)

    scope.close()
    scope.close()

    with pytest.raises(WindowsCredentialInvalidError, match="closed"):
        scope.use(lambda key, secret: (key, secret))
    with pytest.raises(WindowsCredentialInvalidError, match="closed"):
        scope.__enter__()


def test_native_entry_repr_and_str_are_fully_redacted() -> None:
    entry = NativeCredentialEntry(
        target_name=ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
        credential_type=CRED_TYPE_GENERIC,
        persistence=CRED_PERSIST_LOCAL_MACHINE,
        blob=bytearray(_SECRET.encode()),
        native_pointer=object(),
    )

    assert _SECRET not in repr(entry)
    assert ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET not in repr(entry)
    assert _SECRET not in str(entry)


@pytest.mark.parametrize(
    "size",
    [8, MAX_WINDOWS_CREDENTIAL_BLOB_BYTES, CRED_MAX_CREDENTIAL_BLOB_SIZE],
)
def test_native_release_zeroes_entire_reported_blob_before_free_and_is_idempotent(
    size: int,
) -> None:
    native_buffer = (ctypes.c_ubyte * size)(*([7] * size))
    events: list[str] = []
    api = object.__new__(CtypesWindowsCredentialNativeApi)

    def zero(address: int, length: int) -> None:
        events.append("zero")
        ctypes.memset(address, 0, length)

    class Advapi:
        def CredFree(self, pointer: object) -> None:
            del pointer
            events.append("free")

    api._zero_memory = zero
    api._advapi32 = Advapi()
    entry = NativeCredentialEntry(
        target_name=ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
        credential_type=CRED_TYPE_GENERIC,
        persistence=CRED_PERSIST_LOCAL_MACHINE,
        blob=bytearray(b"x" * min(size, MAX_WINDOWS_CREDENTIAL_BLOB_BYTES)),
        native_pointer=object(),
        native_blob_address=ctypes.addressof(native_buffer),
        native_blob_size=size,
    )

    api.release(entry)
    api.release(entry)

    assert events == ["zero", "free"]
    assert not any(native_buffer)
    assert not any(entry.blob)
    assert entry.released is True
    assert entry.native_pointer is None


@pytest.mark.parametrize(
    ("address", "size"),
    [
        (0, 1),
        ((1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1, 2),
        (1, CRED_MAX_CREDENTIAL_BLOB_SIZE + 1),
    ],
)
def test_native_release_invalid_range_skips_zero_but_frees_once(
    address: int,
    size: int,
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
        target_name=ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
        credential_type=CRED_TYPE_GENERIC,
        persistence=CRED_PERSIST_LOCAL_MACHINE,
        blob=bytearray(b"x"),
        native_pointer=object(),
        native_blob_address=address,
        native_blob_size=size,
    )

    with pytest.raises(WindowsCredentialInvalidError, match="cleanup"):
        api.release(entry)
    api.release(entry)

    assert events == ["free"]


def test_native_read_copies_no_more_than_application_bound() -> None:
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
        TargetName=ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
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

    entry = api.read_generic(ALPACA_API_KEY_ID_CREDENTIAL_TARGET)

    assert len(entry.blob) == MAX_WINDOWS_CREDENTIAL_BLOB_BYTES
    assert entry.native_blob_size == size
    api.release(entry)
    assert not any(native_buffer)


def test_native_api_rejects_nonfixed_target_before_credread() -> None:
    api = object.__new__(CtypesWindowsCredentialNativeApi)

    with pytest.raises(WindowsCredentialInvalidError, match="target"):
        api.read_generic("alternate-target")


@pytest.mark.skipif(os.name == "nt", reason="non-Windows fail-closed assertion")
def test_real_native_adapter_is_unsupported_off_windows() -> None:
    with pytest.raises(WindowsCredentialUnsupportedError):
        CtypesWindowsCredentialNativeApi()
