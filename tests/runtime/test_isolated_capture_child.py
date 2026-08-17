from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import pytest

import trading_bot.runtime.isolated_capture_child as child_module
from trading_bot.market_data import AlpacaHttpResponse
from trading_bot.market_data.exceptions import (
    AlpacaHttpStatusError,
    AlpacaTimeoutError,
    AlpacaTransportError,
    InvalidDailySnapshotResponseError,
)
from trading_bot.runtime.isolated_capture_artifacts import (
    IsolatedCaptureChildClassification,
    ProviderCallDisposition,
    parse_isolated_capture_child_result,
)
from trading_bot.runtime.isolated_capture_child import (
    OneCallProviderFence,
    execute_isolated_capture_child,
)
from trading_bot.runtime.windows_credentials import ScopedAlpacaSecrets

from .isolated_capture_test_support import OWNER_SID, REQUESTED_AT, install_child_case

KEY = "TEST-KEY-ID-VALUE"
SECRET = "TEST-SECRET-VALUE"


class FakeReader:
    def __init__(self) -> None:
        self.sid_checks = 0
        self.reads = 0

    def verify_current_sid(self, reference) -> str:
        self.sid_checks += 1
        assert reference.owner_account_sid == OWNER_SID
        return OWNER_SID

    def read_after_sid_verification(self, reference, verified_sid):
        self.reads += 1
        assert verified_sid == OWNER_SID
        return ScopedAlpacaSecrets(KEY, SECRET)


class FakeTransport:
    def __init__(self, body: bytes | None = None, error: Exception | None = None):
        self.body = _response_body() if body is None else body
        self.error = error
        self.calls = 0
        self.received_credentials: tuple[str, str] | None = None

    def execute(self, request, *, api_key_id: str, api_secret_key: str):
        self.calls += 1
        self.received_credentials = (api_key_id, api_secret_key)
        if self.error is not None:
            raise self.error
        return AlpacaHttpResponse(
            status=200,
            headers=(
                ("Content-Type", "application/json"),
                ("X-Request-ID", "request-safe-1"),
            ),
            body=self.body,
            body_sha256=hashlib.sha256(self.body).hexdigest(),
            body_byte_length=len(self.body),
            request_id="request-safe-1",
            media_type="application/json",
        )


def _response_body(*, token: str | None = None) -> bytes:
    return json.dumps(
        {
            "bars": {
                "SPY": [
                    {
                        "c": 101,
                        "h": 102,
                        "l": 99,
                        "o": 100,
                        "t": "2026-01-05T05:00:00Z",
                        "v": 1000,
                    }
                ],
                "QQQ": [
                    {
                        "c": 201,
                        "h": 202,
                        "l": 199,
                        "o": 200,
                        "t": "2026-01-05T05:00:00Z",
                        "v": 900,
                    }
                ],
            },
            "currency": "USD",
            "next_page_token": token,
        },
        separators=(",", ":"),
    ).encode()


def test_success_calls_provider_once_publishes_and_preserves_environment(
    tmp_path, capsys
) -> None:
    case = install_child_case(tmp_path)
    reader = FakeReader()
    transport = FakeTransport()
    before = dict(os.environ)

    execution = execute_isolated_capture_child(
        case["request_path"],
        credential_reader=reader,
        transport=transport,
        clock=lambda: REQUESTED_AT,
    )

    assert execution.result.classification is (
        IsolatedCaptureChildClassification.SUCCEEDED
    )
    assert execution.result.provider_call_disposition is (
        ProviderCallDisposition.RESPONSE_CONFIRMED
    )
    assert execution.result.provider_request_id == "request-safe-1"
    assert transport.calls == 1
    assert transport.received_credentials == (KEY, SECRET)
    assert reader.sid_checks == 1
    assert reader.reads == 1
    assert dict(os.environ) == before
    result_payload = case["request"].child_result_path.read_bytes()
    assert parse_isolated_capture_child_result(result_payload) == execution.result
    assert KEY.encode() not in result_payload
    assert SECRET.encode() not in result_payload
    captured = capsys.readouterr()
    assert KEY not in captured.out + captured.err
    assert SECRET not in captured.out + captured.err
    assert execution.snapshot_result is not None
    assert execution.snapshot_result.artifact_path.exists()


@pytest.mark.parametrize(
    ("error", "classification", "disposition"),
    [
        (
            AlpacaHttpStatusError(401, provider_code=40110000),
            IsolatedCaptureChildClassification.AUTHENTICATION_FAILED,
            ProviderCallDisposition.RESPONSE_CONFIRMED,
        ),
        (
            AlpacaHttpStatusError(429, provider_code=42910000),
            IsolatedCaptureChildClassification.PROVIDER_REJECTED,
            ProviderCallDisposition.RESPONSE_CONFIRMED,
        ),
        (
            AlpacaTransportError(f"network failure {SECRET}"),
            IsolatedCaptureChildClassification.NETWORK_FAILED,
            ProviderCallDisposition.MAY_HAVE_STARTED,
        ),
        (
            AlpacaTimeoutError(f"timeout {SECRET}"),
            IsolatedCaptureChildClassification.TIMEOUT,
            ProviderCallDisposition.MAY_HAVE_STARTED,
        ),
    ],
)
def test_sanitized_provider_failures(
    tmp_path, error, classification, disposition
) -> None:
    case = install_child_case(tmp_path)
    transport = FakeTransport(error=error)

    execution = execute_isolated_capture_child(
        case["request_path"],
        credential_reader=FakeReader(),
        transport=transport,
        clock=lambda: REQUESTED_AT,
    )

    assert execution.result.classification is classification
    assert execution.result.provider_call_disposition is disposition
    assert transport.calls == 1
    result_payload = execution.result_path.read_bytes()
    assert KEY.encode() not in result_payload
    assert SECRET.encode() not in result_payload


def test_incomplete_pagination_does_not_make_second_call(tmp_path) -> None:
    case = install_child_case(tmp_path)
    transport = FakeTransport(_response_body(token="next"))

    execution = execute_isolated_capture_child(
        case["request_path"],
        credential_reader=FakeReader(),
        transport=transport,
        clock=lambda: REQUESTED_AT,
    )

    assert execution.result.classification is (
        IsolatedCaptureChildClassification.INCOMPLETE_RESPONSE
    )
    assert execution.result.provider_call_disposition is (
        ProviderCallDisposition.RESPONSE_CONFIRMED
    )
    assert transport.calls == 1


def test_snapshot_publication_failure_is_stable_and_sanitized(
    tmp_path, monkeypatch
) -> None:
    case = install_child_case(tmp_path)

    def fail_output(**kwargs):
        del kwargs
        raise child_module.DailySnapshotArtifactOutputError(
            f"secret-bearing output failure {SECRET}"
        )

    monkeypatch.setattr(child_module, "install_daily_snapshot_artifact", fail_output)
    execution = execute_isolated_capture_child(
        case["request_path"],
        credential_reader=FakeReader(),
        transport=FakeTransport(),
        clock=lambda: REQUESTED_AT,
    )

    assert execution.result.classification is (
        IsolatedCaptureChildClassification.SNAPSHOT_OUTPUT_FAILED
    )
    assert SECRET.encode() not in execution.result_path.read_bytes()


def test_secret_bearing_internal_factory_error_is_reduced(tmp_path) -> None:
    case = install_child_case(tmp_path)

    def fail_factory(**kwargs):
        del kwargs
        raise RuntimeError(f"factory failed with {KEY} and {SECRET}")

    execution = execute_isolated_capture_child(
        case["request_path"],
        credential_reader=FakeReader(),
        transport=FakeTransport(),
        provider_factory=fail_factory,
        clock=lambda: REQUESTED_AT,
    )

    assert execution.result.classification is (
        IsolatedCaptureChildClassification.INTERNAL_FAILED
    )
    payload = execution.result_path.read_bytes()
    assert KEY.encode() not in payload
    assert SECRET.encode() not in payload
    assert execution.result.provider_call_disposition is (
        ProviderCallDisposition.NOT_STARTED
    )


def test_invalid_credential_reference_has_specific_child_fact(tmp_path) -> None:
    case = install_child_case(tmp_path)
    case["request"].credential_reference_path.write_bytes(b"{}\n")

    execution = execute_isolated_capture_child(
        case["request_path"],
        credential_reader=FakeReader(),
        transport=FakeTransport(),
        clock=lambda: REQUESTED_AT,
    )

    assert execution.result.classification is (
        IsolatedCaptureChildClassification.CREDENTIAL_REFERENCE_INVALID
    )
    assert execution.result.provider_call_disposition is (
        ProviderCallDisposition.NOT_STARTED
    )


@dataclass
class _FenceResponse:
    candidates: tuple[object, ...] = ()


class _FenceProvider:
    descriptor = object()

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, request):
        del request
        self.calls += 1
        return _FenceResponse()


def test_second_call_fence_blocks_before_provider() -> None:
    provider = _FenceProvider()
    fence = OneCallProviderFence(provider, 100)

    fence.fetch(object())
    with pytest.raises(
        InvalidDailySnapshotResponseError,
        match="ONE_CALL_FENCE_SECOND_INVOCATION_BLOCKED",
    ):
        fence.fetch(object())

    assert provider.calls == 1
