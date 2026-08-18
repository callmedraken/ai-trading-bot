from __future__ import annotations

import pytest

from trading_bot.runtime.windows_effectful_capture import (
    ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
    ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
)
from trading_bot.runtime.windows_effectful_capture_credentials import (
    CRED_PERSIST_LOCAL_MACHINE,
    CRED_TYPE_GENERIC,
    NativeCredentialEntry,
    WindowsAlpacaCredentialManagerReader,
    WindowsCredentialInvalidError,
)

_OWNER_SID = "S-1-5-21-111-222-333-1001"


class _Api:
    def __init__(self) -> None:
        self.reads: list[str] = []
        self.releases: list[NativeCredentialEntry] = []
        self.entries = {
            ALPACA_API_KEY_ID_CREDENTIAL_TARGET: NativeCredentialEntry(
                ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
                CRED_TYPE_GENERIC,
                CRED_PERSIST_LOCAL_MACHINE,
                bytearray(b"bad\nkey"),
            ),
            ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET: NativeCredentialEntry(
                ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
                CRED_TYPE_GENERIC,
                CRED_PERSIST_LOCAL_MACHINE,
                bytearray(b"secret-never-read"),
            ),
        }

    def read_generic(self, target_name: str) -> NativeCredentialEntry:
        self.reads.append(target_name)
        return self.entries[target_name]

    def release(self, entry: NativeCredentialEntry) -> None:
        if entry.released:
            return
        for index in range(len(entry.blob)):
            entry.blob[index] = 0
        entry.released = True
        self.releases.append(entry)


def test_malformed_resolved_sid_is_inspection_failure_before_credential_read() -> None:
    api = _Api()
    reader = WindowsAlpacaCredentialManagerReader.for_test(
        native_api=api,
        sid_resolver=lambda: "Trading",
    )

    with pytest.raises(
        WindowsCredentialInvalidError,
        match="current process SID inspection failed",
    ):
        reader.read(_OWNER_SID)

    assert api.reads == []
    assert api.releases == []


def test_invalid_api_key_is_decoded_before_secret_is_read() -> None:
    api = _Api()
    reader = WindowsAlpacaCredentialManagerReader.for_test(
        native_api=api,
        sid_resolver=lambda: _OWNER_SID,
    )

    with pytest.raises(WindowsCredentialInvalidError, match="malformed"):
        reader.read(_OWNER_SID)

    assert api.reads == [ALPACA_API_KEY_ID_CREDENTIAL_TARGET]
    assert len(api.releases) == 1
    assert api.releases[0].target_name == ALPACA_API_KEY_ID_CREDENTIAL_TARGET
    assert api.releases[0].released is True
    assert not any(api.releases[0].blob)
