from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

import pytest

import trading_bot.runtime.windows_effectful_capture_child as child_module
from trading_bot.domain import Symbol
from trading_bot.market_data import (
    AlpacaHttpResponse,
    AlpacaHttpStatusError,
    AlpacaTransportError,
    AlpacaTransportFailureStage,
    DailySnapshotSerializationError,
    verify_daily_snapshot,
)
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
    ScopedAlpacaSecrets,
    WindowsAlpacaCredentialManagerReader,
    WindowsCredentialNotFoundError,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    ChildCleanupStatus,
    ChildResultClassification,
    ProviderAttemptFenceState,
    WindowsEffectfulCaptureProtocolError,
    build_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
)

_RESERVATION = "11111111-1111-4111-8111-111111111111"
_EXECUTION = "33333333-3333-4333-8333-333333333333"
_APPROVED_SID = "S-1-5-21-111-222-333-1001"
_OTHER_SID = "S-1-5-21-999-888-777-1001"
_RELEASE = "11" * 32
_KEY = "TEST-KEY-ID-VALUE"
_SECRET = "TEST-SECRET-VALUE"
_CAPTURED_AT = datetime(2026, 8, 18, 14, 0, 1, tzinfo=UTC)


class FakeNativeCredentialApi:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = [] if events is None else events
        self.reads: list[str] = []
        self.releases: list[NativeCredentialEntry] = []
        self.entries: dict[str, NativeCredentialEntry | Exception] = {
            ALPACA_API_KEY_ID_CREDENTIAL_TARGET: _credential_entry(
                ALPACA_API_KEY_ID_CREDENTIAL_TARGET, _KEY
            ),
            ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET: _credential_entry(
                ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET, _SECRET
            ),
        }

    def read_generic(self, target_name: str) -> NativeCredentialEntry:
        self.events.append(f"read:{target_name}")
        self.reads.append(target_name)
        value = self.entries[target_name]
        if isinstance(value, Exception):
            raise value
        return value

    def release(self, entry: NativeCredentialEntry) -> None:
        if entry.released:
            return
        self.events.append(f"release:{entry.target_name}")
        for index in range(len(entry.blob)):
            entry.blob[index] = 0
        entry.released = True
        self.releases.append(entry)


class FakeTransport:
    def __init__(
        self,
        *,
        body: bytes | None = None,
        request_id: str = "alpaca-request-1",
        error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.body = _valid_body() if body is None else body
        self.request_id = request_id
        self.error = error
        self.events = [] if events is None else events
        self.calls = 0
        self.requests = []
        self.credentials: list[tuple[str, str]] = []

    def execute(
        self,
        request,
        *,
        api_key_id: str,
        api_secret_key: str,
    ) -> AlpacaHttpResponse:
        self.calls += 1
        self.events.append("transport")
        self.requests.append(request)
        self.credentials.append((api_key_id, api_secret_key))
        if self.error is not None:
            raise self.error
        return AlpacaHttpResponse(
            status=200,
            headers=(
                ("Content-Type", "application/json"),
                ("X-Request-ID", self.request_id),
            ),
            body=self.body,
            body_sha256=hashlib.sha256(self.body).hexdigest(),
            body_byte_length=len(self.body),
            request_id=self.request_id,
            media_type="application/json",
        )


class FakeStagingWriter:
    def __init__(
        self,
        *,
        fail_write: bool = False,
        fail_flush: bool = False,
        events: list[str] | None = None,
    ) -> None:
        self.fail_write = fail_write
        self.fail_flush = fail_flush
        self.events = [] if events is None else events
        self.payloads: list[bytes] = []
        self.flush_count = 0

    def write(self, payload: bytes) -> None:
        self.events.append("write")
        if self.fail_write:
            raise RuntimeError(f"write failed {_SECRET}")
        self.payloads.append(bytes(payload))

    def flush(self) -> None:
        self.events.append("flush")
        self.flush_count += 1
        if self.fail_flush:
            raise RuntimeError(f"flush failed {_SECRET}")


def _credential_entry(target: str, value: str) -> NativeCredentialEntry:
    return NativeCredentialEntry(
        target_name=target,
        credential_type=CRED_TYPE_GENERIC,
        persistence=CRED_PERSIST_LOCAL_MACHINE,
        blob=bytearray(value.encode()),
    )


def _reader(
    api: FakeNativeCredentialApi,
    *,
    sid: str = _APPROVED_SID,
) -> WindowsAlpacaCredentialManagerReader:
    return WindowsAlpacaCredentialManagerReader.for_test(
        native_api=api,
        sid_resolver=lambda: sid,
    )


def _child_request():
    request = ProductionCaptureRequest(
        ordered_universe=(Symbol("AAPL"), Symbol("MSFT")),
        request_window_start_date=date(2026, 8, 17),
        request_window_end_date=date(2026, 8, 17),
        target_session_date=date(2026, 8, 18),
    )
    plan = prepare_production_capture_plan(
        request,
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


def _valid_body(*, include_msft: bool = True) -> bytes:
    bars = {
        "AAPL": [
            {
                "c": 101,
                "h": 102,
                "l": 99,
                "o": 100,
                "t": "2026-08-17T20:00:00Z",
                "v": 1000,
            }
        ]
    }
    if include_msft:
        bars["MSFT"] = [
            {
                "c": 201,
                "h": 202,
                "l": 199,
                "o": 200,
                "t": "2026-08-17T20:00:00Z",
                "v": 2000,
            }
        ]
    return json.dumps(
        {"bars": bars, "currency": "USD", "next_page_token": None},
        separators=(",", ":"),
    ).encode()


def _attempt(
    *,
    api: FakeNativeCredentialApi | None = None,
    sid: str = _APPROVED_SID,
    transport: FakeTransport | None = None,
    writer: FakeStagingWriter | None = None,
):
    native_api = FakeNativeCredentialApi() if api is None else api
    selected_transport = FakeTransport() if transport is None else transport
    selected_writer = FakeStagingWriter() if writer is None else writer
    attempt = build_isolated_capture_child_attempt_for_test(
        _child_request(),
        credential_reader=_reader(native_api, sid=sid),
        transport=selected_transport,
        clock=lambda: _CAPTURED_AT,
        staging_writer=selected_writer,
    )
    return attempt, native_api, selected_transport, selected_writer


def test_success_is_one_fetch_canonical_verified_staged_and_sanitized() -> None:
    attempt, api, transport, writer = _attempt()

    result = attempt.run()

    assert result.classification is ChildResultClassification.SUCCEEDED
    assert result.fence_state is ProviderAttemptFenceState.ENTERED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert result.http_status == 200
    assert result.provider_request_id == "alpaca-request-1"
    assert transport.calls == 1
    assert transport.credentials == [(_KEY, _SECRET)]
    assert len(writer.payloads) == 1
    assert writer.flush_count == 1
    payload = writer.payloads[0]
    assert result.artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert result.artifact_byte_length == len(payload)
    verification = verify_daily_snapshot(
        payload,
        child_module.BoundMarketCalendar(
            child_module.XNYS_CALENDAR_DESCRIPTOR,
            child_module.NYSEMarketCalendar(),
        ),
        expected_sha256=result.artifact_sha256,
        expected_byte_length=result.artifact_byte_length,
    )
    assert verification.passed
    assert verification.snapshot is not None
    assert verification.snapshot.snapshot_id == result.snapshot_id
    assert len(api.releases) == 2
    serialized = serialize_isolated_capture_child_result(result)
    assert _KEY.encode() not in serialized
    assert _SECRET.encode() not in serialized


def test_attempt_reuse_is_rejected_before_second_transport() -> None:
    attempt, _api, transport, _writer = _attempt()
    first = attempt.run()
    assert first.classification is ChildResultClassification.SUCCEEDED

    with pytest.raises(WindowsEffectfulCaptureChildError, match="consumed"):
        attempt.run()

    assert transport.calls == 1


def test_post_admission_reparse_failure_is_request_invalid_after_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt, api, transport, writer = _attempt()

    def fail_parse(_payload: bytes):
        raise WindowsEffectfulCaptureProtocolError("tampered request")

    monkeypatch.setattr(
        child_module,
        "parse_isolated_capture_child_request",
        fail_parse,
    )
    result = attempt.run()

    assert result.classification is ChildResultClassification.REQUEST_INVALID
    assert result.fence_state is ProviderAttemptFenceState.ENTERED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert api.reads == []
    assert transport.calls == 0
    assert writer.payloads == []


def test_sid_rejection_happens_before_credential_or_transport() -> None:
    attempt, api, transport, writer = _attempt(sid=_OTHER_SID)

    result = attempt.run()

    assert result.classification is ChildResultClassification.SID_REJECTED
    assert result.fence_state is ProviderAttemptFenceState.ENTERED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert api.reads == []
    assert transport.calls == 0
    assert writer.payloads == []


def test_credential_failure_is_sanitized_and_never_calls_transport() -> None:
    api = FakeNativeCredentialApi()
    api.entries[ALPACA_API_KEY_ID_CREDENTIAL_TARGET] = WindowsCredentialNotFoundError(
        f"missing {_SECRET}"
    )
    attempt, _api, transport, writer = _attempt(api=api)

    result = attempt.run()

    assert result.classification is ChildResultClassification.CREDENTIAL_FAILED
    assert result.cleanup_status is ChildCleanupStatus.FAILED
    assert transport.calls == 0
    assert writer.payloads == []
    serialized = serialize_isolated_capture_child_result(result)
    assert _SECRET.encode() not in serialized


@pytest.mark.parametrize(
    ("stage", "classification"),
    [
        (
            AlpacaTransportFailureStage.REQUEST,
            ChildResultClassification.TRANSPORT_REQUEST_FAILED,
        ),
        (
            AlpacaTransportFailureStage.RESPONSE_START,
            ChildResultClassification.TRANSPORT_RESPONSE_START_FAILED,
        ),
        (
            AlpacaTransportFailureStage.RESPONSE_METADATA,
            ChildResultClassification.TRANSPORT_RESPONSE_METADATA_FAILED,
        ),
        (
            AlpacaTransportFailureStage.RESPONSE_BODY,
            ChildResultClassification.TRANSPORT_RESPONSE_BODY_FAILED,
        ),
        (
            AlpacaTransportFailureStage.UNKNOWN,
            ChildResultClassification.TRANSPORT_FAILED,
        ),
    ],
)
def test_transport_failure_stage_maps_without_fabricated_http_evidence(
    stage: AlpacaTransportFailureStage,
    classification: ChildResultClassification,
) -> None:
    transport = FakeTransport(error=AlpacaTransportError(stage))
    attempt, _api, _transport, writer = _attempt(transport=transport)

    result = attempt.run()

    assert result.classification is classification
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert result.http_status is None
    assert result.provider_request_id is None
    assert transport.calls == 1
    assert writer.payloads == []
    assert _SECRET.encode() not in serialize_isolated_capture_child_result(result)


def test_http_failure_retains_only_sanitized_response_evidence() -> None:
    transport = FakeTransport(
        error=AlpacaHttpStatusError(
            429,
            request_id="request-429",
            provider_code=42910000,
        )
    )
    attempt, _api, _transport, writer = _attempt(transport=transport)

    result = attempt.run()

    assert result.classification is ChildResultClassification.HTTP_FAILED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert result.http_status == 429
    assert result.provider_request_id == "request-429"
    assert transport.calls == 1
    assert writer.payloads == []


def test_http_200_malformed_provider_entity_is_provider_response_invalid() -> None:
    transport = FakeTransport(body=b'{"bars":[],"next_page_token":null}')
    attempt, _api, _transport, writer = _attempt(transport=transport)

    result = attempt.run()

    assert result.classification is ChildResultClassification.PROVIDER_RESPONSE_INVALID
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert result.http_status == 200
    assert result.provider_request_id == "alpaca-request-1"
    assert transport.calls == 1
    assert writer.payloads == []


def test_incomplete_successful_response_is_snapshot_rejected() -> None:
    transport = FakeTransport(body=_valid_body(include_msft=False))
    attempt, _api, _transport, writer = _attempt(transport=transport)

    result = attempt.run()

    assert result.classification is ChildResultClassification.SNAPSHOT_REJECTED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert result.http_status == 200
    assert transport.calls == 1
    assert writer.payloads == []


def test_serialization_failure_occurs_after_credentials_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    api = FakeNativeCredentialApi(events)
    transport = FakeTransport(events=events)
    writer = FakeStagingWriter(events=events)
    original_close = ScopedAlpacaSecrets.close

    def observed_close(self: ScopedAlpacaSecrets) -> None:
        events.append("scope-close")
        original_close(self)

    def fail_serialize(_snapshot):
        events.append("serialize")
        raise DailySnapshotSerializationError(f"serialize {_SECRET}")

    monkeypatch.setattr(ScopedAlpacaSecrets, "close", observed_close)
    monkeypatch.setattr(child_module, "serialize_daily_snapshot", fail_serialize)
    attempt, _api, _transport, _writer = _attempt(
        api=api,
        transport=transport,
        writer=writer,
    )

    result = attempt.run()

    assert result.classification is ChildResultClassification.SERIALIZATION_FAILED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert events.index("scope-close") < events.index("serialize")
    assert "write" not in events
    assert _SECRET.encode() not in serialize_isolated_capture_child_result(result)


def test_child_verification_failure_is_serialization_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailedVerification:
        passed = False
        snapshot = None

    monkeypatch.setattr(
        child_module,
        "verify_daily_snapshot",
        lambda *_args, **_kwargs: FailedVerification(),
    )
    attempt, _api, transport, writer = _attempt()

    result = attempt.run()

    assert result.classification is ChildResultClassification.SERIALIZATION_FAILED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert transport.calls == 1
    assert writer.payloads == []


@pytest.mark.parametrize("failure", ["write", "flush"])
def test_staging_failure_is_sanitized_after_one_provider_attempt(failure: str) -> None:
    writer = FakeStagingWriter(
        fail_write=failure == "write",
        fail_flush=failure == "flush",
    )
    attempt, _api, transport, _writer = _attempt(writer=writer)

    result = attempt.run()

    assert result.classification is ChildResultClassification.STAGING_FAILED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert transport.calls == 1
    assert result.http_status == 200
    assert result.snapshot_id is None
    assert result.artifact_sha256 is None
    assert result.artifact_byte_length is None
    assert _SECRET.encode() not in serialize_isolated_capture_child_result(result)


def test_unknown_child_failure_is_sanitized_without_raw_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_fetch(**_kwargs):
        raise RuntimeError(f"unexpected {_SECRET}")

    monkeypatch.setattr(child_module, "_fetch_and_accept", fail_fetch)
    attempt, _api, transport, writer = _attempt()

    result = attempt.run()

    assert result.classification is ChildResultClassification.INTERNAL_FAILED
    assert result.cleanup_status is ChildCleanupStatus.COMPLETE
    assert transport.calls == 0
    assert writer.payloads == []
    assert _SECRET.encode() not in serialize_isolated_capture_child_result(result)


def test_overlong_provider_request_id_is_omitted_from_success_result() -> None:
    transport = FakeTransport(request_id="r" * 129)
    attempt, _api, _transport, writer = _attempt(transport=transport)

    result = attempt.run()

    assert result.classification is ChildResultClassification.SUCCEEDED
    assert result.http_status == 200
    assert result.provider_request_id is None
    assert len(writer.payloads) == 1


def test_success_does_not_issue_parent_verified_snapshot_authority() -> None:
    attempt, _api, _transport, _writer = _attempt()

    result = attempt.run()

    assert result.classification is ChildResultClassification.SUCCEEDED
    assert not hasattr(child_module, "issue_verified_captured_snapshot")
    assert not hasattr(result, "_permit")
