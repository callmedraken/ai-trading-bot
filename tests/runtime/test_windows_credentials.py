from __future__ import annotations

import os

import pytest

from trading_bot.runtime.windows_credentials import (
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


@pytest.mark.skipif(os.name == "nt", reason="non-Windows fail-closed assertion")
def test_real_adapter_is_unsupported_off_windows() -> None:
    with pytest.raises(WindowsCredentialUnsupportedError):
        CtypesWindowsCredentialNativeApi()
