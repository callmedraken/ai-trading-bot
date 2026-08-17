"""Narrow one-attempt HTTPS transport for Alpaca historical stock bars."""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from trading_bot.market_data.exceptions import (
    AlpacaHttpStatusError,
    AlpacaTimeoutError,
    AlpacaTransportError,
)

ALPACA_DATA_HOST = "data.alpaca.markets"
ALPACA_HTTPS_PORT = 443
ALPACA_SOCKET_TIMEOUT_SECONDS = 15.0
ALPACA_RESPONSE_CHUNK_BYTES = 64 * 1024
MAX_ALPACA_RESPONSE_BYTES = 4 * 1024 * 1024

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REQUEST_ID_PATTERN = re.compile(r"^[!-~]{1,256}$")


@dataclass(frozen=True, slots=True)
class AlpacaHistoricalBarsRequest:
    """Public nonsecret representation of one fixed Alpaca GET."""

    method: str
    host: str
    target: str
    public_headers: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if self.method != "GET":
            raise AlpacaTransportError("Alpaca request method must be GET")
        if self.host != ALPACA_DATA_HOST:
            raise AlpacaTransportError("Alpaca request host is unsupported")
        if (
            type(self.target) is not str
            or not self.target.startswith("/v2/stocks/bars?")
            or any(character in self.target for character in ("\r", "\n", "\0"))
        ):
            raise AlpacaTransportError("Alpaca request target is invalid")
        headers = tuple(self.public_headers)
        if any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not str
            for item in headers
        ):
            raise AlpacaTransportError("public headers must be string pairs")
        names = tuple(name.casefold() for name, _ in headers)
        if len(set(names)) != len(names):
            raise AlpacaTransportError("public request headers must be unique")
        if {
            "apca-api-key-id",
            "apca-api-secret-key",
            "authorization",
        } & set(names):
            raise AlpacaTransportError(
                "public request headers must not contain authentication"
            )
        object.__setattr__(self, "public_headers", headers)


@dataclass(frozen=True, slots=True)
class AlpacaHttpResponse:
    """Bounded successful entity and evidence from one HTTPS response."""

    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    body_sha256: str
    body_byte_length: int
    request_id: str
    media_type: str

    def __post_init__(self) -> None:
        if type(self.status) is not int or self.status != 200:
            raise AlpacaTransportError("successful response status must be 200")
        headers = tuple(self.headers)
        if any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not str
            for item in headers
        ):
            raise AlpacaTransportError("successful response headers are invalid")
        if any(
            name.casefold()
            in {
                "apca-api-key-id",
                "apca-api-secret-key",
                "authorization",
            }
            for name, _ in headers
        ):
            raise AlpacaTransportError(
                "successful response headers contain authentication material"
            )
        if type(self.body) is not bytes:
            raise AlpacaTransportError("response body must be exact bytes")
        if (
            type(self.body_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.body_sha256) is None
            or hashlib.sha256(self.body).hexdigest() != self.body_sha256
        ):
            raise AlpacaTransportError("response body SHA-256 is inconsistent")
        if type(self.body_byte_length) is not int or self.body_byte_length != len(
            self.body
        ):
            raise AlpacaTransportError("response body byte length is inconsistent")
        if _REQUEST_ID_PATTERN.fullmatch(self.request_id) is None:
            raise AlpacaTransportError("response request ID is invalid")
        if self.media_type != "application/json":
            raise AlpacaTransportError("response media type is unsupported")
        object.__setattr__(self, "headers", headers)


class AlpacaHistoricalBarsTransport(Protocol):
    """One nonsecret request plus ephemeral authentication values."""

    def execute(
        self,
        request: AlpacaHistoricalBarsRequest,
        *,
        api_key_id: str,
        api_secret_key: str,
    ) -> AlpacaHttpResponse: ...


class _HttpResponseLike(Protocol):
    status: int

    def getheaders(self) -> list[tuple[str, str]]: ...

    def read(self, amount: int | None = None) -> bytes: ...


class _HttpsConnectionLike(Protocol):
    def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    def getresponse(self) -> _HttpResponseLike: ...

    def close(self) -> None: ...


ConnectionFactory = Callable[..., _HttpsConnectionLike]
TlsContextFactory = Callable[[], ssl.SSLContext]


class StdlibAlpacaHistoricalBarsTransport:
    """Perform one fixed-host GET with bounded entity reading."""

    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory = http.client.HTTPSConnection,
        tls_context_factory: TlsContextFactory = ssl.create_default_context,
    ) -> None:
        if not callable(connection_factory) or not callable(tls_context_factory):
            raise AlpacaTransportError("transport factories must be callable")
        self._connection_factory = connection_factory
        self._tls_context_factory = tls_context_factory

    def execute(
        self,
        request: AlpacaHistoricalBarsRequest,
        *,
        api_key_id: str,
        api_secret_key: str,
    ) -> AlpacaHttpResponse:
        if type(request) is not AlpacaHistoricalBarsRequest:
            raise AlpacaTransportError("request must be an AlpacaHistoricalBarsRequest")
        _validate_runtime_credential(api_key_id)
        _validate_runtime_credential(api_secret_key)
        connection: _HttpsConnectionLike | None = None
        try:
            context = self._tls_context_factory()
            if not isinstance(context, ssl.SSLContext):
                raise AlpacaTransportError(
                    "TLS context factory returned an invalid context"
                )
            connection = self._connection_factory(
                ALPACA_DATA_HOST,
                ALPACA_HTTPS_PORT,
                timeout=ALPACA_SOCKET_TIMEOUT_SECONDS,
                context=context,
            )
            headers = dict(request.public_headers)
            headers["APCA-API-KEY-ID"] = api_key_id
            headers["APCA-API-SECRET-KEY"] = api_secret_key
            connection.request("GET", request.target, body=None, headers=headers)
            response = connection.getresponse()
            raw_headers = tuple(response.getheaders())
            metadata = _validated_response_headers(
                raw_headers,
                require_success_fields=response.status == 200,
            )
            body, body_hash, body_length = _read_bounded_entity(response)
            declared_length = metadata["content_length"]
            if declared_length is not None and declared_length != body_length:
                raise AlpacaTransportError(
                    "Alpaca response Content-Length does not match entity bytes"
                )
            if response.status != 200:
                raise AlpacaHttpStatusError(
                    response.status,
                    request_id=metadata["request_id"],
                    provider_code=_safe_provider_code(body),
                )
            request_id = metadata["request_id"]
            media_type = metadata["media_type"]
            if request_id is None or media_type is None:
                raise AlpacaTransportError(
                    "successful Alpaca response metadata is incomplete"
                )
            return AlpacaHttpResponse(
                status=200,
                headers=(
                    ("Content-Type", media_type),
                    ("X-Request-ID", request_id),
                ),
                body=body,
                body_sha256=body_hash,
                body_byte_length=body_length,
                request_id=request_id,
                media_type=media_type,
            )
        except (AlpacaHttpStatusError, AlpacaTransportError):
            raise
        except TimeoutError:
            raise AlpacaTimeoutError(
                "Alpaca HTTPS request reached the approved socket timeout"
            ) from None
        except (OSError, ssl.SSLError, http.client.HTTPException):
            raise AlpacaTransportError(
                "Alpaca HTTPS request failed before a safe response was obtained"
            ) from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass


def _validate_runtime_credential(value: object) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(character in value for character in ("\r", "\n", "\0"))
    ):
        raise AlpacaTransportError("runtime Alpaca credential is invalid")


def _validated_response_headers(
    headers: tuple[tuple[str, str], ...],
    *,
    require_success_fields: bool,
) -> dict[str, object]:
    selected: dict[str, list[str]] = {}
    relevant = {
        "content-length",
        "content-type",
        "content-encoding",
        "transfer-encoding",
        "x-request-id",
    }
    for item in headers:
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not str
        ):
            raise AlpacaTransportError("Alpaca response headers are malformed")
        name, value = item
        folded = name.casefold()
        if folded in relevant:
            if any(character in value for character in ("\r", "\n", "\0")):
                raise AlpacaTransportError(
                    "Alpaca response contains an unsafe header value"
                )
            selected.setdefault(folded, []).append(value)
    for name, values in selected.items():
        if len(values) != 1:
            raise AlpacaTransportError(
                f"Alpaca response has conflicting {name} headers"
            )

    encoding = _single(selected, "content-encoding")
    if encoding is not None and encoding.strip().casefold() != "identity":
        raise AlpacaTransportError("compressed Alpaca responses are unsupported")

    transfer_encoding = _single(selected, "transfer-encoding")
    if (
        transfer_encoding is not None
        and transfer_encoding.strip().casefold() != "chunked"
    ):
        raise AlpacaTransportError("unsupported Alpaca response transfer encoding")
    content_length_text = _single(selected, "content-length")
    if transfer_encoding is not None and content_length_text is not None:
        raise AlpacaTransportError(
            "Alpaca response has conflicting transfer-length headers"
        )
    content_length: int | None = None
    if content_length_text is not None:
        if not content_length_text.isascii() or not content_length_text.isdecimal():
            raise AlpacaTransportError("Alpaca Content-Length is invalid")
        content_length = int(content_length_text)
        if content_length > MAX_ALPACA_RESPONSE_BYTES:
            raise AlpacaTransportError("Alpaca response exceeds the 4 MiB limit")

    request_id = _single(selected, "x-request-id")
    if request_id is not None and _REQUEST_ID_PATTERN.fullmatch(request_id) is None:
        raise AlpacaTransportError("Alpaca X-Request-ID is invalid")
    if require_success_fields and request_id is None:
        raise AlpacaTransportError("successful Alpaca response is missing X-Request-ID")

    content_type = _single(selected, "content-type")
    media_type: str | None = None
    if content_type is not None:
        parts = [part.strip() for part in content_type.split(";")]
        if parts[0].casefold() != "application/json":
            raise AlpacaTransportError("Alpaca response media type is unsupported")
        for parameter in parts[1:]:
            if parameter.casefold() != "charset=utf-8":
                raise AlpacaTransportError(
                    "Alpaca response Content-Type parameters are unsupported"
                )
        media_type = "application/json"
    if require_success_fields and media_type is None:
        raise AlpacaTransportError("successful Alpaca response is missing Content-Type")
    return {
        "content_length": content_length,
        "request_id": request_id,
        "media_type": media_type,
    }


def _single(values: dict[str, list[str]], name: str) -> str | None:
    retained = values.get(name)
    return None if retained is None else retained[0]


def _read_bounded_entity(
    response: _HttpResponseLike,
) -> tuple[bytes, str, int]:
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    byte_length = 0
    while True:
        chunk = response.read(ALPACA_RESPONSE_CHUNK_BYTES)
        if type(chunk) is not bytes:
            raise AlpacaTransportError("Alpaca response read returned non-bytes")
        if not chunk:
            break
        byte_length += len(chunk)
        if byte_length > MAX_ALPACA_RESPONSE_BYTES:
            raise AlpacaTransportError("Alpaca response exceeds the 4 MiB limit")
        digest.update(chunk)
        chunks.append(chunk)
    return b"".join(chunks), digest.hexdigest(), byte_length


def _safe_provider_code(body: bytes) -> int | None:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if type(value) is not dict:
        return None
    code = value.get("code")
    return code if type(code) is int and code >= 0 else None
