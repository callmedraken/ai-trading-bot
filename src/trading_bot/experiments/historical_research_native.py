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
from trading_bot.review_paper import alpaca_windows_credentials as current_credentials
from trading_bot.review_paper.alpaca_windows_credentials import (
    ScopedAlpacaSecrets,
    read_current_product_alpaca_secrets,
)
from trading_bot.review_paper.unattended_host_identity import TRADING_SID
from trading_bot.runtime.windows_authority_security import resolve_current_token_sid

# Reuse only the retained approved account identity, never D1/prepare/execute
# authority. The current token is independently observed before every read.
CREDENTIAL_ACCOUNT_SID = TRADING_SID
CREDENTIAL_POLICY = current_credentials.CREDENTIAL_POLICY
CREDENTIAL_BINDING_DISPOSITION = "SOURCE_OWNED_B2_TRADING_ACCOUNT_V3"
CREDENTIAL_TARGETS = (
    current_credentials.API_KEY_TARGET,
    current_credentials.API_SECRET_TARGET,
)


def credential_binding_is_current() -> bool:
    """Pure source binding; no host discovery, secret read or effect authority."""
    return (
        CREDENTIAL_ACCOUNT_SID == TRADING_SID
        and CREDENTIAL_POLICY
        == current_credentials.CREDENTIAL_POLICY
        == "windows-credential-manager-alpaca-market-data/v3"
        and CREDENTIAL_TARGETS
        == (current_credentials.API_KEY_TARGET, current_credentials.API_SECRET_TARGET)
        == (
            "AITradingBot/MarketData/Alpaca/ApiKeyId/v3",
            "AITradingBot/MarketData/Alpaca/ApiSecretKey/v3",
        )
    )


class WindowsHistoricalResearchCredentialSource:
    """Bridge the current v3 scoped reader after exact source-owned SID proof."""

    def __init__(self) -> None:
        self._reader = read_current_product_alpaca_secrets
        self._sid_resolver = resolve_current_token_sid

    @classmethod
    def for_test(
        cls,
        reader: Callable[[], ScopedAlpacaSecrets],
        sid_resolver: Callable[[], str],
    ) -> WindowsHistoricalResearchCredentialSource:
        result = cls()
        result._reader = reader
        result._sid_resolver = sid_resolver
        return result

    def __repr__(self) -> str:
        return "WindowsHistoricalResearchCredentialSource(<redacted>)"

    def read(self) -> AcquisitionCredentials:
        try:
            if (
                not credential_binding_is_current()
                or self._sid_resolver() != CREDENTIAL_ACCOUNT_SID
            ):
                raise ValueError("B2 credential account binding rejected")
            with self._reader() as scoped:
                if type(scoped) is not ScopedAlpacaSecrets:
                    raise ValueError("exact current credential scope required")
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
