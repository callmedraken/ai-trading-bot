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
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from trading_bot.portfolio_manager.sec_native_observation import (
    SECFileEvidenceStore,
    SECObservationCounters,
    SECObservationError,
    SECObservationOutcome,
    SECObservationPlan,
    SECObservationResult,
    SECTransportResponse,
    _observe_sec_once_with_transport,
    _read_sec_response_bounded,
    _result,
    is_valid_sec_production_boundary,
    load_sec_effect_authorization_record,
    load_sec_source_admission_record,
)


def observe_sec_once(
    plan: SECObservationPlan,
    admission_evidence_path: str | Path,
    effect_authorization_path: str | Path,
) -> SECObservationResult:
    """Attempt one SEC GET after loading actual admission and review records.

    The operator cannot inject a transport, evidence store, clock, or typed
    authorization value into this production boundary.
    """

    if type(plan) is not SECObservationPlan:
        raise TypeError("the exact immutable SEC observation plan is required")
    checked_at = datetime.now(UTC)
    try:
        admission = load_sec_source_admission_record(admission_evidence_path, plan)
    except (OSError, ValueError, RuntimeError, TypeError):
        return _result(
            plan,
            SECObservationOutcome.SOURCE_ADMISSION_FAILED,
            "ACTUAL_SUCCESSFUL_PREPUBLICATION_ADMISSION_RECORD_REQUIRED",
            SECObservationCounters(),
        )
    try:
        authorization = load_sec_effect_authorization_record(
            effect_authorization_path, plan, admission, checked_at
        )
    except (OSError, ValueError, RuntimeError, TypeError):
        return _result(
            plan,
            SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED,
            "ACTUAL_CURRENT_PLAN_BOUND_EFFECT_AUTHORIZATION_RECORD_REQUIRED",
            SECObservationCounters(),
        )
    try:
        evidence_store = SECFileEvidenceStore(plan)
    except (OSError, ValueError, RuntimeError, TypeError):
        return _result(
            plan,
            SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED,
            "CANONICAL_ONE_SHOT_EVIDENCE_STORE_REQUIRED",
            SECObservationCounters(),
        )
    if not is_valid_sec_production_boundary(plan, evidence_store):
        return _result(
            plan,
            SECObservationOutcome.EFFECT_AUTHORIZATION_FAILED,
            "PRODUCTION_BOUNDARY_STORE_OR_ATTEMPT_ID_MISMATCH",
            SECObservationCounters(),
        )

    def recheck_authorization_evidence() -> bool:
        current_admission = load_sec_source_admission_record(
            admission_evidence_path, plan
        )
        if current_admission != admission:
            return False
        current_authorization = load_sec_effect_authorization_record(
            effect_authorization_path,
            plan,
            current_admission,
            datetime.now(UTC),
        )
        return current_authorization == authorization

    return _observe_sec_once_with_transport(
        plan,
        admission,
        authorization,
        _SECReadOnlyTransport(),
        evidence_store,
        authorization_recheck=recheck_authorization_evidence,
        require_response_receipt_timestamp=True,
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
        total_time_limit_seconds: float,
        max_bytes: int,
    ) -> SECTransportResponse:
        deadline = time.monotonic() + total_time_limit_seconds
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.sec.gov"
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
        try:
            response = opener.open(
                request, timeout=min(timeout_seconds, total_time_limit_seconds)
            )
        except urllib.error.HTTPError as error:
            try:
                body = _read_sec_response_bounded(
                    error, max_bytes, timeout_seconds, deadline
                )
                received_at = datetime.now(UTC)
                return SECTransportResponse(
                    error.code,
                    error.headers.get("Content-Type", ""),
                    body,
                    url,
                    received_at,
                )
            finally:
                error.close()
        with response:
            body = _read_sec_response_bounded(
                response, max_bytes, timeout_seconds, deadline
            )
            received_at = datetime.now(UTC)
            return SECTransportResponse(
                response.status,
                response.headers.get("Content-Type", ""),
                body,
                response.geturl(),
                received_at,
            )
