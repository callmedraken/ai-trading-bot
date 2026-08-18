from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

import trading_bot.runtime.windows_effectful_capture_child as child_module
from trading_bot.domain import Symbol
from trading_bot.market_data import AlpacaHttpStatusError
from trading_bot.runtime.windows_effectful_capture import (
    ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
    ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
    ProductionCaptureRequest,
    bind_production_capture_plan,
    build_production_provider_launch_plan,
    prepare_production_capture_plan,
)
from trading_bot.runtime.windows_effectful_capture_child import (
    WindowsEffectfulCaptureChildError,
    build_isolated_capture_child_attempt_for_test,
)
from trading_bot.runtime.windows_effectful_capture_credentials import (
    CRED_PERSIST_LOCAL_MACHINE,
    CRED_TYPE_GENERIC,
    NativeCredentialEntry,
    WindowsAlpacaCredentialManagerReader,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    ChildCleanupStatus,
    ChildResultClassification,
    build_isolated_capture_child_request,
)

_RESERVATION = "11111111-1111-4111-8111-111111111111"
_EXECUTION = "33333333-3333-4333-8333-333333333333"
_APPROVED_SID = "S-1-5-21-111-222-333-1001"
_RELEASE = "11" * 32


class _CredentialApi:
    def __init__(self) -> None:
        self.entries = {
            ALPACA_API_KEY_ID_CREDENTIAL_TARGET: NativeCredentialEntry(
                ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
                CRED_TYPE_GENERIC,
                CRED_PERSIST_LOCAL_MACHINE,
                bytearray(b"test-key"),
            ),
            ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET: NativeCredentialEntry(
                ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
                CRED_TYPE_GENERIC,
                CRED_PERSIST_LOCAL_MACHINE,
                bytearray(b"test-secret"),
            ),
        }

    def read_generic(self, target_name: str) -> NativeCredentialEntry:
        return self.entries[target_name]

    def release(self, entry: NativeCredentialEntry) -> None:
        if entry.released:
            return
        for index in range(len(entry.blob)):
            entry.blob[index] = 0
        entry.released = True


class _Writer:
    def __init__(self) -> None:
        self.payloads: list[bytes] = []

    def write(self, payload: bytes) -> None:
        self.payloads.append(bytes(payload))

    def flush(self) -> None:
        return None


class _MalformedReturnTransport:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _request, *, api_key_id: str, api_secret_key: str):
        del api_key_id, api_secret_key
        self.calls += 1
        return object()


class _InvalidHttpFailureTransport:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _request, *, api_key_id: str, api_secret_key: str):
        del api_key_id, api_secret_key
        self.calls += 1
        raise AlpacaHttpStatusError(999, request_id="unsafe-status")


class _CountingTransport:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _request, *, api_key_id: str, api_secret_key: str):
        del api_key_id, api_secret_key
        self.calls += 1
        return object()


def _request():
    capture = ProductionCaptureRequest(
        ordered_universe=(Symbol("AAPL"), Symbol("MSFT")),
        request_window_start_date=date(2026, 8, 17),
        request_window_end_date=date(2026, 8, 17),
        target_session_date=date(2026, 8, 18),
    )
    plan = prepare_production_capture_plan(
        capture,
        datetime(2026, 8, 18, 14, tzinfo=UTC),
    )
    bound = bind_production_capture_plan(plan, _RESERVATION)
    launch = build_production_provider_launch_plan(bound)
    return build_isolated_capture_child_request(
        launch,
        _EXECUTION,
        approved_account_sid=_APPROVED_SID,
        release_manifest_sha256=_RELEASE,
    )


def _reader() -> WindowsAlpacaCredentialManagerReader:
    return WindowsAlpacaCredentialManagerReader.for_test(
        native_api=_CredentialApi(),
        sid_resolver=lambda: _APPROVED_SID,
    )


def _attempt(transport):
    writer = _Writer()
    attempt = build_isolated_capture_child_attempt_for_test(
        _request(),
        credential_reader=_reader(),
        transport=transport,
        clock=lambda: datetime(2026, 8, 18, 14, 0, 1, tzinfo=UTC),
        staging_writer=writer,
    )
    return attempt, writer


def test_malformed_transport_return_fails_closed_without_http_evidence() -> None:
    transport = _MalformedReturnTransport()
    attempt, writer = _attempt(transport)

    result = attempt.run()

    assert result.classification is ChildResultClassification.TRANSPORT_FAILED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert result.http_status is None
    assert result.provider_request_id is None
    assert transport.calls == 1
    assert writer.payloads == []


def test_invalid_http_status_exception_becomes_transport_failure() -> None:
    transport = _InvalidHttpFailureTransport()
    attempt, writer = _attempt(transport)

    result = attempt.run()

    assert result.classification is ChildResultClassification.TRANSPORT_FAILED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert result.http_status is None
    assert result.provider_request_id is None
    assert transport.calls == 1
    assert writer.payloads == []


def test_transport_guard_blocks_second_delegation() -> None:
    inner = _CountingTransport()
    guarded = child_module._ObservedSingleAttemptTransport(inner)

    guarded.execute(object(), api_key_id="key", api_secret_key="secret")
    with pytest.raises(WindowsEffectfulCaptureChildError, match="second"):
        guarded.execute(object(), api_key_id="key", api_secret_key="secret")

    assert inner.calls == 1
