"""Explicit, manually invoked real SEC observation boundary.

This module is deliberately not imported by application startup, source
admission, pytest, or CI. Its only call path requires current source admission,
a separate plan-bound effect authorization, and a create-once evidence store.
The current readiness review does not authorize invoking this boundary.
"""

from __future__ import annotations

import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

from trading_bot.portfolio_manager.sec_native_observation import (
    SECEvidenceStore,
    SECObservationAuthorization,
    SECObservationError,
    SECObservationPlan,
    SECObservationResult,
    SECSourceAdmission,
    SECTransportResponse,
    _observe_sec_once_with_transport,
)


def observe_sec_once(
    plan: SECObservationPlan,
    admission: SECSourceAdmission,
    authorization: SECObservationAuthorization,
    evidence_store: SECEvidenceStore,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> SECObservationResult:
    """Attempt one SEC archive GET after the separate source/effect gates."""

    return _observe_sec_once_with_transport(
        plan,
        admission,
        authorization,
        _SECReadOnlyTransport(),
        evidence_store,
        now=now,
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _SECReadOnlyTransport:
    """Exact SEC-host HTTPS GET; never follows redirects or system proxies."""

    def get(
        self,
        url: str,
        *,
        user_agent: str,
        timeout_seconds: int,
        total_time_limit_seconds: int,
        max_bytes: int,
    ) -> SECTransportResponse:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "www.sec.gov"
            or parsed.query
            or parsed.fragment
        ):
            raise SECObservationError("request URL is outside the exact SEC boundary")
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "text/plain",
                "User-Agent": user_agent,
            },
            method="GET",
        )
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            _NoRedirect(),
        )
        deadline = time.monotonic() + total_time_limit_seconds
        try:
            response = opener.open(
                request, timeout=min(timeout_seconds, total_time_limit_seconds)
            )
        except urllib.error.HTTPError as error:
            try:
                body = _read_bounded(error, max_bytes, timeout_seconds, deadline)
                return SECTransportResponse(
                    error.code,
                    error.headers.get("Content-Type", ""),
                    body,
                    url,
                )
            finally:
                error.close()
        with response:
            body = _read_bounded(response, max_bytes, timeout_seconds, deadline)
            return SECTransportResponse(
                response.status,
                response.headers.get("Content-Type", ""),
                body,
                response.geturl(),
            )


def _read_bounded(
    response, max_bytes: int, timeout_seconds: int, deadline: float
) -> bytes:
    """Read bounded chunks while tightening socket timeout to the total deadline."""

    http_response = getattr(response, "fp", None)
    buffer = getattr(http_response, "fp", None)
    raw = getattr(buffer, "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is None:
        raise SECObservationError("bounded SEC response socket is unavailable")
    body = bytearray()
    while len(body) <= max_bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("SEC total observation time limit reached")
        sock.settimeout(min(timeout_seconds, remaining))
        chunk = response.read(min(64 * 1024, max_bytes + 1 - len(body)))
        if not chunk:
            break
        body.extend(chunk)
    return bytes(body)
