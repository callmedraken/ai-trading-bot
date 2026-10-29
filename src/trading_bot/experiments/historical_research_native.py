"""Narrow native B2 credential and HTTPS adapters. Import/construction is inert."""

from __future__ import annotations

import getpass
import http.client
import re
import ssl
import sys
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from trading_bot.arch133_verifier.token import WindowsTradingTokenObserver
from trading_bot.experiments.historical_research_acquisition import (
    MAX_RESPONSE_BYTES,
    AcquisitionCredentials,
    HistoricalResearchRequest,
    HistoricalResearchResponse,
)
from trading_bot.experiments.historical_research_custody import (
    HistoricalResearchCustodyError,
    HistoricalSessionAuthority,
)
from trading_bot.market_data.alpaca_http import (
    ALPACA_DATA_HOST,
    ALPACA_HTTPS_PORT,
    ALPACA_RESPONSE_CHUNK_BYTES,
    ALPACA_SOCKET_TIMEOUT_SECONDS,
    _validated_response_headers,
)
from trading_bot.review_paper.alpaca_windows_credentials import (
    validate_alpaca_credential_bytes,
)

if TYPE_CHECKING:
    from trading_bot.experiments.historical_research_b2_preflight import (
        AcceptedB2Preflight,
    )

CREDENTIAL_SOURCE = "EPHEMERAL_INTERACTIVE_RESEARCH_CREDENTIALS"
CREDENTIAL_PERSISTENCE = "NONE"


def credential_binding_is_current() -> bool:
    """Pure research policy; no stored targets or production account binding."""
    return (
        CREDENTIAL_SOURCE == "EPHEMERAL_INTERACTIVE_RESEARCH_CREDENTIALS"
        and CREDENTIAL_PERSISTENCE == "NONE"
    )


@dataclass(frozen=True, slots=True)
class ResearchOperatorToken:
    sid: str
    elevated: bool
    administrator: bool

    def verify_sid(self) -> None:
        if (
            type(self.sid) is not str
            or re.fullmatch(
                r"S-1-5-21-(?:[1-9][0-9]{0,9}-){3}[1-9][0-9]{0,9}", self.sid
            )
            is None
            or any(int(part) > 0xFFFFFFFF for part in self.sid.split("-")[4:])
        ):
            raise HistoricalResearchCustodyError("research operator SID class rejected")

    def verify(self) -> None:
        self.verify_sid()
        if self.elevated is not False or self.administrator is not False:
            raise HistoricalResearchCustodyError("research operator token rejected")


def observe_research_operator_token() -> ResearchOperatorToken:
    """Observe actual token facts; no supplied SID or account lookup is authority."""
    # Reuse only the bounded TOKEN_QUERY observer, never Trading admission.
    observed = WindowsTradingTokenObserver().observe()
    if observed.token_type != 1 or observed.thread_token_present is not False:
        raise HistoricalResearchCustodyError("research token identity unproven")
    # Include deny-only Administrators membership: a filtered admin token is
    # still an administrator account, even when CheckTokenMembership is false.
    return ResearchOperatorToken(
        observed.user_sid,
        observed.elevated,
        any(sid == "S-1-5-32-544" for sid, _ in observed.groups),
    )


def interactive_research_credentials() -> AcquisitionCredentials:
    """Reviewed getpass warning-as-error pattern, without provisioning authority.

    Called only inside the admitted one-shot credential source. Mutable UTF-8
    copies are cleared on every exit. Python/terminal immutable string copies
    cannot be guaranteed zeroized. Shape validation is not authentication.
    """
    values = []
    result = None
    failed = False
    try:
        if not all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)):
            raise ValueError
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            for prompt in ("Research Alpaca key ID: ", "Research Alpaca secret: "):
                values.append(bytearray(getpass.getpass(prompt).encode("utf-8")))
                validate_alpaca_credential_bytes(values[-1])
        result = AcquisitionCredentials(*(value.decode("utf-8") for value in values))
    except BaseException:
        failed = True
    finally:
        for value in values:
            for index in range(len(value)):
                value[index] = 0
    # Raise outside the handler: neither chaining nor __context__ retains input.
    if failed or result is None:
        raise HistoricalResearchCustodyError("research credential input rejected")
    return result


class EphemeralHistoricalResearchCredentialSource:
    """No default authority. READY and caller-supplied SIDs cannot prompt.

    A separately accepted real preflight and an exact B1 run are both required.
    There is deliberately no acquisition CLI or effect dispatcher here.
    """

    def __init__(self, accepted_preflight: AcceptedB2Preflight | None = None) -> None:
        self._accepted_preflight = accepted_preflight
        self._bound = False
        self._used = False

    def __repr__(self) -> str:
        return "EphemeralHistoricalResearchCredentialSource(<redacted>)"

    def bind_acquisition(
        self,
        *,
        source_head: str,
        source_tree: str,
        session_authority: HistoricalSessionAuthority,
    ) -> None:
        from trading_bot.experiments.historical_research_b2_preflight import (
            AcceptedB2Preflight,
        )

        if self._bound or self._used:
            raise HistoricalResearchCustodyError("research credential source consumed")
        self._used = True
        if type(self._accepted_preflight) is not AcceptedB2Preflight:
            raise HistoricalResearchCustodyError("accepted real preflight required")
        self._accepted_preflight.verify_acquisition(
            source_head, source_tree, session_authority
        )
        self._bound = True

    def read(self) -> AcquisitionCredentials:
        failed = False
        result = None
        try:
            if not self._bound or not credential_binding_is_current():
                raise ValueError
            self._bound = False
            # Recheck exact source/contracts and token immediately before input.
            self._accepted_preflight.recheck()
            result = interactive_research_credentials()
        except BaseException:
            failed = True
        if failed or type(result) is not AcquisitionCredentials:
            raise HistoricalResearchCustodyError("B2 credential source failed")
        return result


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
        credentials.verify()
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
