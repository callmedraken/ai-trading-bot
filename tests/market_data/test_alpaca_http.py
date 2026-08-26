from __future__ import annotations

import hashlib
import http.client
import socket
import ssl

import pytest

import trading_bot.market_data.alpaca_http as alpaca_http_module
from trading_bot.market_data import (
    MAX_ALPACA_RESPONSE_BYTES,
    AlpacaDailySnapshotError,
    AlpacaHistoricalBarsRequest,
    AlpacaHttpStatusError,
    AlpacaResponseMetadataFailureReason,
    AlpacaTransportError,
    AlpacaTransportFailureStage,
    StdlibAlpacaHistoricalBarsTransport,
)

KEY = "transport-test-key"
SECRET = "transport-test-secret"
TARGET = (
    "/v2/stocks/bars?symbols=SPY&timeframe=1Day"
    "&start=2025-01-06T05%3A00%3A00Z"
    "&end=2025-01-07T04%3A59%3A59.999999Z"
    "&limit=1&adjustment=raw&asof=-&feed=sip&currency=USD&sort=asc"
)


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        headers: tuple[tuple[str, str], ...] | None = None,
        headers_error: Exception | None = None,
        read_error: Exception | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self._position = 0
        self._headers = headers or (
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("X-Request-ID", "request-123"),
        )
        self._headers_error = headers_error
        self._read_error = read_error
        self.read_sizes: list[int | None] = []

    def getheaders(self):
        if self._headers_error is not None:
            raise self._headers_error
        return list(self._headers)

    def read(self, amount=None):
        self.read_sizes.append(amount)
        if self._read_error is not None:
            raise self._read_error
        if self._position >= len(self._body):
            return b""
        end = len(self._body) if amount is None else self._position + amount
        chunk = self._body[self._position : end]
        self._position += len(chunk)
        return chunk


class FakeConnection:
    def __init__(
        self,
        response: FakeResponse | Exception,
        *,
        request_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.response = response
        self.request_error = request_error
        self.close_error = close_error
        self.requests = []
        self.closed = False

    def request(self, method, url, body=None, headers=None):
        self.requests.append((method, url, body, dict(headers or {})))
        if self.request_error is not None:
            raise self.request_error

    def getresponse(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def _request() -> AlpacaHistoricalBarsRequest:
    return AlpacaHistoricalBarsRequest(
        method="GET",
        host="data.alpaca.markets",
        target=TARGET,
        public_headers=(
            ("Accept", "application/json"),
            ("Accept-Encoding", "identity"),
        ),
    )


def _transport(connection: FakeConnection):
    calls = []

    def factory(*args, **kwargs):
        calls.append((args, kwargs))
        return connection

    return StdlibAlpacaHistoricalBarsTransport(
        connection_factory=factory,
        tls_context_factory=ssl.create_default_context,
    ), calls


def test_transport_failure_stages_are_closed_and_retain_no_caller_text() -> None:
    assert tuple(AlpacaTransportFailureStage) == (
        AlpacaTransportFailureStage.REQUEST,
        AlpacaTransportFailureStage.RESPONSE_START,
        AlpacaTransportFailureStage.RESPONSE_METADATA,
        AlpacaTransportFailureStage.RESPONSE_BODY,
        AlpacaTransportFailureStage.UNKNOWN,
    )
    with pytest.raises(ValueError):
        AlpacaTransportFailureStage("HOST_SECRET_STAGE")

    for stage in AlpacaTransportFailureStage:
        error = AlpacaTransportError(stage)
        assert error.stage is stage
        assert SECRET not in str(error)
        assert SECRET not in repr(error)

    legacy = AlpacaTransportError(f"legacy caller detail {SECRET}")
    assert legacy.stage is AlpacaTransportFailureStage.UNKNOWN
    assert SECRET not in str(legacy)
    assert SECRET not in repr(legacy)


def test_http_status_error_is_distinct_from_transport_stage_failures() -> None:
    error = AlpacaHttpStatusError(
        429,
        request_id="safe-request-id",
        provider_code=42910000,
    )

    assert isinstance(error, AlpacaDailySnapshotError)
    assert not isinstance(error, AlpacaTransportError)
    assert error.status == 429
    assert error.request_id == "safe-request-id"
    assert error.provider_code == 42910000
    assert not hasattr(error, "stage")


def test_transport_uses_fake_connection_once_and_streams_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b'{"bars":{},"next_page_token":null}'
    response = FakeResponse(body)
    connection = FakeConnection(response)
    transport, factory_calls = _transport(connection)

    def fail_socket(*args, **kwargs):
        raise AssertionError("a real socket must never be opened")

    monkeypatch.setattr(socket, "create_connection", fail_socket)
    result = transport.execute(
        _request(),
        api_key_id=KEY,
        api_secret_key=SECRET,
    )

    assert len(factory_calls) == 1
    assert factory_calls[0][0] == ("data.alpaca.markets", 443)
    assert factory_calls[0][1]["timeout"] == 15.0
    assert isinstance(factory_calls[0][1]["context"], ssl.SSLContext)
    assert len(connection.requests) == 1
    method, target, request_body, headers = connection.requests[0]
    assert (method, target, request_body) == ("GET", TARGET, None)
    assert headers["APCA-API-KEY-ID"] == KEY
    assert headers["APCA-API-SECRET-KEY"] == SECRET
    assert result.body == body
    assert result.body_sha256 == hashlib.sha256(body).hexdigest()
    assert result.body_byte_length == len(body)
    assert result.request_id == "request-123"
    assert set(response.read_sizes) == {64 * 1024}
    assert connection.closed
    assert KEY not in repr(_request())
    assert SECRET not in repr(_request())


def test_403_is_sanitized_and_never_retried_or_fallen_back() -> None:
    body = (
        b'{"code":42210000,"message":"subscription denied for '
        + SECRET.encode()
        + b'"}'
    )
    response = FakeResponse(
        body,
        status=403,
        headers=(
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("X-Request-ID", "entitlement-request"),
        ),
    )
    connection = FakeConnection(response)
    transport, factory_calls = _transport(connection)

    with pytest.raises(AlpacaHttpStatusError) as caught:
        transport.execute(
            _request(),
            api_key_id=KEY,
            api_secret_key=SECRET,
        )

    assert caught.value.status == 403
    assert caught.value.provider_code == 42210000
    assert caught.value.request_id == "entitlement-request"
    assert len(factory_calls) == 1
    assert len(connection.requests) == 1
    assert "iex" not in connection.requests[0][1]
    assert not hasattr(caught.value, "stage")
    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)


@pytest.mark.parametrize(
    ("status", "content_type"),
    [(403, "text/plain"), (429, "text/html"), (404, None)],
)
def test_non_200_non_json_content_type_preserves_http_failure(
    status: int,
    content_type: str | None,
) -> None:
    body = b'{"code":42910000,"message":"not a supported JSON response"}'
    headers = [
        ("Content-Length", str(len(body))),
        ("X-Request-ID", "safe-error-request"),
    ]
    if content_type is not None:
        headers.append(("Content-Type", content_type))
    response = FakeResponse(
        body,
        status=status,
        headers=tuple(headers),
    )
    connection = FakeConnection(response)
    transport, factory_calls = _transport(connection)

    with pytest.raises(AlpacaHttpStatusError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.status == status
    assert caught.value.request_id == "safe-error-request"
    assert caught.value.provider_code is None
    assert len(factory_calls) == 1
    assert len(connection.requests) == 1
    assert set(response.read_sizes) == {64 * 1024}


def test_non_200_non_json_body_remains_bounded() -> None:
    response = FakeResponse(
        b"x" * (MAX_ALPACA_RESPONSE_BYTES + 1),
        status=429,
        headers=(
            ("Content-Type", "text/html"),
            ("X-Request-ID", "safe-error-request"),
        ),
    )
    connection = FakeConnection(response)
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_BODY
    assert len(connection.requests) == 1
    assert response.read_sizes
    assert set(response.read_sizes) == {64 * 1024}


@pytest.mark.parametrize(
    "headers",
    [
        (
            ("Content-Type", "text/plain"),
            ("Content-Type", "text/html"),
            ("X-Request-ID", "request-1"),
        ),
        (
            ("Content-Type", "text/plain"),
            ("Content-Encoding", "gzip"),
            ("X-Request-ID", "request-1"),
        ),
        (
            ("Content-Type", "text/plain"),
            ("Transfer-Encoding", "compress"),
            ("X-Request-ID", "request-1"),
        ),
        (
            ("Content-Type", "text/plain"),
            ("Content-Length", "2"),
            ("Transfer-Encoding", "chunked"),
            ("X-Request-ID", "request-1"),
        ),
    ],
)
def test_non_200_still_rejects_unsafe_framing_and_duplicate_headers(headers) -> None:
    connection = FakeConnection(FakeResponse(b"{}", status=403, headers=headers))
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_METADATA
    assert len(connection.requests) == 1


@pytest.mark.parametrize(
    "error",
    [
        OSError(f"request write leaked {SECRET}"),
        ssl.SSLError(f"request TLS leaked {SECRET}"),
        http.client.CannotSendRequest(f"request state leaked {SECRET}"),
    ],
)
def test_request_write_failure_is_classified_and_attempted_once(
    error: Exception,
) -> None:
    connection = FakeConnection(
        FakeResponse(b"{}"),
        request_error=error,
    )
    transport, factory_calls = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.REQUEST
    assert caught.value.__context__ is None
    assert len(factory_calls) == 1
    assert len(connection.requests) == 1
    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)


def test_connection_factory_failure_is_request_stage_and_attempted_once() -> None:
    factory_calls = 0

    def fail_connect(*args, **kwargs):
        nonlocal factory_calls
        factory_calls += 1
        raise OSError(f"connect leaked {SECRET}")

    transport = StdlibAlpacaHistoricalBarsTransport(
        connection_factory=fail_connect,
        tls_context_factory=ssl.create_default_context,
    )

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.REQUEST
    assert caught.value.__context__ is None
    assert factory_calls == 1
    assert SECRET not in repr(caught.value)


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timeout leaked transport-test-secret"),
        ssl.SSLError("tls leaked transport-test-secret"),
        OSError("socket leaked transport-test-secret"),
        http.client.BadStatusLine("status line leaked transport-test-secret"),
    ],
)
def test_lower_transport_failures_are_sanitized(error: Exception) -> None:
    connection = FakeConnection(error)
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(
            _request(),
            api_key_id=KEY,
            api_secret_key=SECRET,
        )

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_START
    assert caught.value.__context__ is None
    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)


def test_invalid_response_status_is_response_start() -> None:
    connection = FakeConnection(FakeResponse(b"{}", status=99))
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_START
    assert caught.value.__context__ is None


def test_tls_factory_failure_is_sanitized() -> None:
    def fail_tls():
        raise ssl.SSLError(f"TLS failed with {SECRET}")

    transport = StdlibAlpacaHistoricalBarsTransport(
        connection_factory=lambda *args, **kwargs: None,
        tls_context_factory=fail_tls,
    )

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(
            _request(),
            api_key_id=KEY,
            api_secret_key=SECRET,
        )

    assert caught.value.stage is AlpacaTransportFailureStage.REQUEST
    assert caught.value.__context__ is None
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize(
    "headers",
    [
        (
            ("Content-Type", "application/json"),
            ("Content-Encoding", "gzip"),
            ("X-Request-ID", "request-1"),
        ),
        (
            ("Content-Type", "application/json"),
            ("X-Request-ID", "request-1"),
            ("X-Request-ID", "request-2"),
        ),
        (
            ("Content-Type", "text/plain"),
            ("X-Request-ID", "request-1"),
        ),
        (("Content-Type", "application/json"),),
        (
            ("Content-Type", "application/json"),
            ("Content-Length", "1"),
            ("Transfer-Encoding", "chunked"),
            ("X-Request-ID", "request-1"),
        ),
        (
            ("Content-Type", "application/json"),
            ("Content-Length", "9" * 5000),
            ("X-Request-ID", "request-1"),
        ),
    ],
)
def test_security_relevant_response_headers_fail_closed(headers) -> None:
    connection = FakeConnection(FakeResponse(b"{}", headers=headers))
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(
            _request(),
            api_key_id=KEY,
            api_secret_key=SECRET,
        )

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_METADATA
    assert caught.value.__context__ is None


def test_response_header_acquisition_failure_is_response_metadata() -> None:
    response = FakeResponse(
        b"{}", headers_error=OSError(f"header read leaked {SECRET}")
    )
    transport, _ = _transport(FakeConnection(response))

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_METADATA
    assert caught.value.__context__ is None
    assert SECRET not in repr(caught.value)


@pytest.mark.parametrize(
    "error",
    [
        OSError(f"body read leaked {SECRET}"),
        http.client.IncompleteRead(SECRET.encode(), 1024),
    ],
)
def test_bounded_response_body_read_failure_is_response_body(
    error: Exception,
) -> None:
    response = FakeResponse(b"{}", read_error=error)
    transport, _ = _transport(FakeConnection(response))

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_BODY
    assert caught.value.__context__ is None
    assert SECRET not in repr(caught.value)


def test_content_length_reconciliation_failure_is_response_body() -> None:
    response = FakeResponse(
        b"{}",
        headers=(
            ("Content-Type", "application/json"),
            ("Content-Length", "3"),
            ("X-Request-ID", "request-123"),
        ),
    )
    transport, _ = _transport(FakeConnection(response))

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_BODY
    assert caught.value.__context__ is None


def test_response_body_limit_is_enforced_during_chunked_read() -> None:
    body = b"x" * (MAX_ALPACA_RESPONSE_BYTES + 1)
    connection = FakeConnection(
        FakeResponse(
            body,
            headers=(
                ("Content-Type", "application/json"),
                ("X-Request-ID", "request-1"),
            ),
        )
    )
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(
            _request(),
            api_key_id=KEY,
            api_secret_key=SECRET,
        )

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_BODY
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "defect_type",
    [
        AttributeError,
        KeyError,
        TypeError,
        AssertionError,
        RuntimeError,
    ],
)
@pytest.mark.parametrize("stage", ["request", "response_start", "metadata", "body"])
def test_unexpected_programming_defects_escape_transport_boundary(
    stage: str,
    defect_type: type[Exception],
) -> None:
    error = defect_type(f"unexpected programming defect {SECRET}")
    if stage == "request":
        connection = FakeConnection(FakeResponse(b"{}"), request_error=error)
    elif stage == "response_start":
        connection = FakeConnection(error)
    elif stage == "metadata":
        connection = FakeConnection(FakeResponse(b"{}", headers_error=error))
    else:
        connection = FakeConnection(FakeResponse(b"{}", read_error=error))
    transport, _ = _transport(connection)

    with pytest.raises(defect_type) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value is error
    assert not isinstance(caught.value, AlpacaTransportError)
    assert len(connection.requests) <= 1


def test_unexpected_close_programming_defect_escapes_transport_boundary() -> None:
    error = RuntimeError(f"unexpected close defect {SECRET}")
    connection = FakeConnection(
        FakeResponse(b"{}"),
        close_error=error,
    )
    transport, _ = _transport(connection)

    with pytest.raises(RuntimeError) as caught:
        transport.execute(
            _request(),
            api_key_id=KEY,
            api_secret_key=SECRET,
        )

    assert caught.value is error
    assert not isinstance(caught.value, AlpacaTransportError)
    assert len(connection.requests) == 1


def test_public_request_rejects_authentication_headers() -> None:
    with pytest.raises(AlpacaTransportError):
        AlpacaHistoricalBarsRequest(
            method="GET",
            host="data.alpaca.markets",
            target=TARGET,
            public_headers=(("APCA-API-KEY-ID", KEY),),
        )


@pytest.mark.parametrize(
    ("headers", "reason", "raw_marker"),
    [
        (
            ((SECRET, "value", "extra"),),
            AlpacaResponseMetadataFailureReason.MALFORMED,
            SECRET,
        ),
        (
            (
                ("Content-Type", "application/json"),
                ("Content-Type", SECRET),
                ("X-Request-ID", "request-1"),
            ),
            AlpacaResponseMetadataFailureReason.DUPLICATE_RELEVANT_HEADER,
            SECRET,
        ),
        (
            (
                ("Content-Type", "application/json"),
                ("Content-Encoding", SECRET),
                ("X-Request-ID", "request-1"),
            ),
            AlpacaResponseMetadataFailureReason.UNSUPPORTED_CONTENT_ENCODING,
            SECRET,
        ),
        (
            (
                ("Content-Type", "application/json"),
                ("Transfer-Encoding", SECRET),
                ("X-Request-ID", "request-1"),
            ),
            AlpacaResponseMetadataFailureReason.UNSUPPORTED_TRANSFER_ENCODING,
            SECRET,
        ),
        (
            (
                ("Content-Type", "application/json"),
                ("Content-Length", SECRET),
                ("Transfer-Encoding", "chunked"),
                ("X-Request-ID", "request-1"),
            ),
            AlpacaResponseMetadataFailureReason.TRANSFER_LENGTH_CONFLICT,
            SECRET,
        ),
        (
            (
                ("Content-Type", "application/json"),
                ("Content-Length", SECRET),
                ("X-Request-ID", "request-1"),
            ),
            AlpacaResponseMetadataFailureReason.INVALID_CONTENT_LENGTH,
            SECRET,
        ),
        (
            (
                ("Content-Type", "application/json"),
                ("X-Request-ID", SECRET + "x" * 257),
            ),
            AlpacaResponseMetadataFailureReason.INVALID_REQUEST_ID,
            SECRET,
        ),
        (
            (
                ("Content-Type", SECRET),
                ("X-Request-ID", "request-1"),
            ),
            AlpacaResponseMetadataFailureReason.UNSUPPORTED_MEDIA_TYPE,
            SECRET,
        ),
    ],
)
def test_response_metadata_validation_has_closed_sanitized_reason(
    headers,
    reason: AlpacaResponseMetadataFailureReason,
    raw_marker: str,
) -> None:
    connection = FakeConnection(FakeResponse(b"{}", headers=headers))
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_METADATA
    assert caught.value.metadata_reason is reason
    assert caught.value.__context__ is None
    assert raw_marker not in str(caught.value)
    assert raw_marker not in repr(caught.value)
    assert len(connection.requests) == 1


def test_response_metadata_acquisition_reason_is_closed_and_sanitized() -> None:
    raw_error = f"header acquisition leaked {SECRET}"
    response = FakeResponse(b"{}", headers_error=OSError(raw_error))
    connection = FakeConnection(response)
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert (
        caught.value.metadata_reason is AlpacaResponseMetadataFailureReason.ACQUISITION
    )
    assert caught.value.__context__ is None
    assert raw_error not in str(caught.value)
    assert raw_error not in repr(caught.value)
    assert len(connection.requests) == 1


def test_response_metadata_validator_programming_error_escapes_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_error = RuntimeError(f"validator programming defect leaked {SECRET}")
    validator_calls = []

    def fail_metadata(*_args, **_kwargs):
        validator_calls.append(True)
        raise raw_error

    monkeypatch.setattr(
        alpaca_http_module,
        "_validated_response_headers",
        fail_metadata,
    )
    response = FakeResponse(b"{}")
    connection = FakeConnection(response)
    transport, factory_calls = _transport(connection)

    with pytest.raises(RuntimeError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value is raw_error
    assert not isinstance(caught.value, AlpacaTransportError)
    assert validator_calls == [True]
    assert len(factory_calls) == 1
    assert len(connection.requests) == 1
    assert response.read_sizes == []


def test_response_metadata_failure_reasons_are_exactly_closed() -> None:
    assert tuple(AlpacaResponseMetadataFailureReason) == (
        AlpacaResponseMetadataFailureReason.ACQUISITION,
        AlpacaResponseMetadataFailureReason.MALFORMED,
        AlpacaResponseMetadataFailureReason.DUPLICATE_RELEVANT_HEADER,
        AlpacaResponseMetadataFailureReason.UNSUPPORTED_CONTENT_ENCODING,
        AlpacaResponseMetadataFailureReason.UNSUPPORTED_TRANSFER_ENCODING,
        AlpacaResponseMetadataFailureReason.TRANSFER_LENGTH_CONFLICT,
        AlpacaResponseMetadataFailureReason.INVALID_CONTENT_LENGTH,
        AlpacaResponseMetadataFailureReason.INVALID_REQUEST_ID,
        AlpacaResponseMetadataFailureReason.MISSING_CONTENT_TYPE,
        AlpacaResponseMetadataFailureReason.UNSUPPORTED_MEDIA_TYPE,
        AlpacaResponseMetadataFailureReason.UNSUPPORTED_CHARSET,
        AlpacaResponseMetadataFailureReason.INVALID_CONTENT_TYPE_PARAMETERS,
        AlpacaResponseMetadataFailureReason.UNSUPPORTED_CONTENT_TYPE,
        AlpacaResponseMetadataFailureReason.GENERIC,
    )

    with pytest.raises(ValueError):
        AlpacaResponseMetadataFailureReason("UNRECOGNIZED_METADATA_REASON")


@pytest.mark.parametrize(
    ("content_type", "reason"),
    [
        (None, AlpacaResponseMetadataFailureReason.MISSING_CONTENT_TYPE),
        ("text/plain", AlpacaResponseMetadataFailureReason.UNSUPPORTED_MEDIA_TYPE),
        (
            "application/json;charset=latin-1",
            AlpacaResponseMetadataFailureReason.UNSUPPORTED_CHARSET,
        ),
        (
            "application/json;profile=private-secret",
            AlpacaResponseMetadataFailureReason.INVALID_CONTENT_TYPE_PARAMETERS,
        ),
        (
            "application/json;charset=utf-8;charset=utf-8",
            AlpacaResponseMetadataFailureReason.INVALID_CONTENT_TYPE_PARAMETERS,
        ),
    ],
)
def test_success_content_type_failure_is_exact_and_sanitized(
    content_type: str | None,
    reason: AlpacaResponseMetadataFailureReason,
) -> None:
    headers = [("Content-Length", "2"), ("X-Request-ID", "request-1")]
    if content_type is not None:
        headers.append(("Content-Type", content_type))
    connection = FakeConnection(FakeResponse(b"{}", headers=tuple(headers)))
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.stage is AlpacaTransportFailureStage.RESPONSE_METADATA
    assert caught.value.metadata_reason is reason
    assert caught.value.__context__ is None
    assert content_type is None or content_type not in repr(caught.value)
    assert "private-secret" not in repr(caught.value)
    assert len(connection.requests) == 1


def test_response_metadata_error_sanitizes_arbitrary_reason() -> None:
    raw_reason = f"arbitrary metadata reason leaked {SECRET}"

    error = AlpacaTransportError(
        AlpacaTransportFailureStage.RESPONSE_METADATA,
        metadata_reason=raw_reason,
    )

    assert error.metadata_reason is AlpacaResponseMetadataFailureReason.GENERIC
    assert raw_reason not in str(error)
    assert raw_reason not in repr(error)


def test_response_metadata_generic_fallback_is_closed_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_error = f"generic metadata leaked {SECRET}"

    def fail_metadata(*_args, **_kwargs):
        raise AlpacaTransportError(raw_error)

    monkeypatch.setattr(
        alpaca_http_module,
        "_validated_response_headers",
        fail_metadata,
    )
    connection = FakeConnection(FakeResponse(b"{}"))
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError) as caught:
        transport.execute(_request(), api_key_id=KEY, api_secret_key=SECRET)

    assert caught.value.metadata_reason is AlpacaResponseMetadataFailureReason.GENERIC
    assert caught.value.__context__ is None
    assert raw_error not in str(caught.value)
    assert raw_error not in repr(caught.value)
    assert len(connection.requests) == 1
