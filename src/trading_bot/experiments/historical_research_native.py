"""Narrow native B2 credential and HTTPS adapters. Import/construction is inert."""

from __future__ import annotations

import http.client
import ssl
from collections.abc import Callable

from trading_bot.experiments.historical_research_acquisition import (
    MAX_RESPONSE_BYTES,
    AcquisitionCredentials,
    HistoricalResearchRequest,
    HistoricalResearchResponse,
)
from trading_bot.experiments.historical_research_custody import (
    HistoricalResearchCustodyError,
)
from trading_bot.market_data.alpaca_http import (
    ALPACA_DATA_HOST,
    ALPACA_HTTPS_PORT,
    ALPACA_RESPONSE_CHUNK_BYTES,
    ALPACA_SOCKET_TIMEOUT_SECONDS,
    _validated_response_headers,
)
from trading_bot.runtime.windows_effectful_capture import (
    ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
    ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
)
from trading_bot.runtime.windows_effectful_capture_credentials import (
    WindowsAlpacaCredentialManagerReader,
)

# The existing production Trading SID does not establish a B2 custodian-account
# binding. Independent source review must settle that binding, never host discovery.
CREDENTIAL_ACCOUNT_SID: str | None = None
CREDENTIAL_BINDING_DISPOSITION = "BLOCKED_SOURCE_OWNED_B2_CREDENTIAL_ACCOUNT_BINDING"
CREDENTIAL_TARGETS = (
    ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
    ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
)


class WindowsHistoricalResearchCredentialSource:
    """Bridge the established SID-scoped reader to B1's redacted in-memory pair."""

    def __init__(self) -> None:
        self._reader = None

    @classmethod
    def for_test(
        cls, reader: WindowsAlpacaCredentialManagerReader
    ) -> WindowsHistoricalResearchCredentialSource:
        if type(reader) is not WindowsAlpacaCredentialManagerReader:
            raise HistoricalResearchCustodyError("exact scoped reader required")
        result = cls()
        result._reader = reader
        return result

    def __repr__(self) -> str:
        return "WindowsHistoricalResearchCredentialSource(<redacted>)"

    def read(self) -> AcquisitionCredentials:
        if CREDENTIAL_ACCOUNT_SID is None:
            raise HistoricalResearchCustodyError(CREDENTIAL_BINDING_DISPOSITION)
        try:
            reader = self._reader or WindowsAlpacaCredentialManagerReader()
            with reader.read(CREDENTIAL_ACCOUNT_SID) as scoped:
                return scoped.use(AcquisitionCredentials)
        except Exception:
            raise HistoricalResearchCustodyError(
                "B2 credential source failed"
            ) from None


class HttpsHistoricalResearchTransport:
    """One TLS-verified fixed-host GET; no redirects, decompression or retries."""

    def __init__(self) -> None:
        self._connection_factory = http.client.HTTPSConnection
        self._context_factory = ssl.create_default_context

    @classmethod
    def for_test(
        cls, connection_factory: Callable, context_factory: Callable
    ) -> HttpsHistoricalResearchTransport:
        result = cls()
        result._connection_factory = connection_factory
        result._context_factory = context_factory
        return result

    def get(
        self, request: HistoricalResearchRequest, credentials: AcquisitionCredentials
    ) -> HistoricalResearchResponse:
        if (
            type(request) is not HistoricalResearchRequest
            or type(credentials) is not AcquisitionCredentials
        ):
            raise HistoricalResearchCustodyError("exact B1 HTTP contracts required")
        # Reconstruct from the closed request type, never accept caller URL/headers.
        canonical = HistoricalResearchRequest(request.stream, request.page_token)
        if request != canonical or request.descriptor != canonical.descriptor:
            raise HistoricalResearchCustodyError("HTTP request binding drift")
        connection = None
        failed = False
        response = None
        try:
            context = self._context_factory()
            if (
                type(context) is not ssl.SSLContext
                or context.verify_mode != ssl.CERT_REQUIRED
                or context.check_hostname is not True
                or context.minimum_version < ssl.TLSVersion.TLSv1_2
            ):
                raise ValueError
            connection = self._connection_factory(
                ALPACA_DATA_HOST,
                ALPACA_HTTPS_PORT,
                timeout=ALPACA_SOCKET_TIMEOUT_SECONDS,
                context=context,
            )
            connection.request(
                "GET",
                canonical.target,
                body=None,
                headers={
                    "APCA-API-KEY-ID": credentials.api_key_id,
                    "APCA-API-SECRET-KEY": credentials.api_secret_key,
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
            )
            raw = connection.getresponse()
            status = raw.status
            if type(status) is not int or not 100 <= status <= 599:
                raise ValueError
            # Reuse only reviewed framing checks. B1 owns status/body semantics;
            # request-id and success-only metadata are not an extra authority.
            framing = tuple(
                (name, value)
                for name, value in raw.getheaders()
                if name.casefold()
                in {"content-length", "content-encoding", "transfer-encoding"}
            )
            metadata = _validated_response_headers(
                framing, require_success_fields=False
            )
            chunks = []
            size = 0
            while True:
                chunk = raw.read(
                    min(ALPACA_RESPONSE_CHUNK_BYTES, MAX_RESPONSE_BYTES + 1 - size)
                )
                if type(chunk) is not bytes:
                    raise ValueError
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise ValueError
                if not chunk:
                    break
                chunks.append(chunk)
            if metadata["content_length"] not in (None, size):
                raise ValueError
            response = HistoricalResearchResponse(request, status, b"".join(chunks))
        except Exception:
            failed = True
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    failed = True
        if failed or response is None:
            raise HistoricalResearchCustodyError("B2 HTTPS exchange failed") from None
        return response
