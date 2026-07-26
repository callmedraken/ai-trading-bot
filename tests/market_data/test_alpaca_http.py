from __future__ import annotations

import hashlib
import socket
import ssl

import pytest

from trading_bot.market_data import (
    MAX_ALPACA_RESPONSE_BYTES,
    AlpacaHistoricalBarsRequest,
    AlpacaHttpStatusError,
    AlpacaTransportError,
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
    ) -> None:
        self.status = status
        self._body = body
        self._position = 0
        self._headers = headers or (
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("X-Request-ID", "request-123"),
        )
        self.read_sizes: list[int | None] = []

    def getheaders(self):
        return list(self._headers)

    def read(self, amount=None):
        self.read_sizes.append(amount)
        if self._position >= len(self._body):
            return b""
        end = len(self._body) if amount is None else self._position + amount
        chunk = self._body[self._position : end]
        self._position += len(chunk)
        return chunk


class FakeConnection:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.requests = []
        self.closed = False

    def request(self, method, url, body=None, headers=None):
        self.requests.append((method, url, body, dict(headers or {})))

    def getresponse(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def close(self):
        self.closed = True


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
    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timeout leaked transport-test-secret"),
        ssl.SSLError("tls leaked transport-test-secret"),
        OSError("socket leaked transport-test-secret"),
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

    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)


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
    ],
)
def test_security_relevant_response_headers_fail_closed(headers) -> None:
    connection = FakeConnection(FakeResponse(b"{}", headers=headers))
    transport, _ = _transport(connection)

    with pytest.raises(AlpacaTransportError):
        transport.execute(
            _request(),
            api_key_id=KEY,
            api_secret_key=SECRET,
        )


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

    with pytest.raises(AlpacaTransportError, match="4 MiB"):
        transport.execute(
            _request(),
            api_key_id=KEY,
            api_secret_key=SECRET,
        )


def test_public_request_rejects_authentication_headers() -> None:
    with pytest.raises(AlpacaTransportError):
        AlpacaHistoricalBarsRequest(
            method="GET",
            host="data.alpaca.markets",
            target=TARGET,
            public_headers=(("APCA-API-KEY-ID", KEY),),
        )
