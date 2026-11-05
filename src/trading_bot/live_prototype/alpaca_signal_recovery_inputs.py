"""D34 successor inputs for one recovered Alpaca signal observation.

This module is additive to the consumed D33 implementation.  It keeps the
accepted D30/D31 math and Alpaca transport boundary while making the published
session cutoff a single value derived before credentials or transport are
constructed.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from trading_bot.live_prototype.alpaca_signal_inputs import (
    ALPACA_SIGNAL_ADJUSTMENT,
    ALPACA_SIGNAL_ASOF,
    ALPACA_SIGNAL_CURRENCY,
    ALPACA_SIGNAL_FEED,
    ALPACA_SIGNAL_LIMIT,
    ALPACA_SIGNAL_SORT,
    ALPACA_SIGNAL_TIMEFRAME,
    LIVE_SIGNAL_PRICE_BASIS,
    REQUIRED_COMPLETED_SESSIONS,
    SIGNAL_SYMBOL,
    SignalDecision,
    decide_35_50,
    moving_averages_35_50,
    select_latest_completed_sessions,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.market_data.alpaca_daily_snapshot import (
    parse_alpaca_historical_bars_response,
)
from trading_bot.market_data.alpaca_http import (
    ALPACA_DATA_HOST,
    AlpacaHistoricalBarsRequest,
    AlpacaHistoricalBarsTransport,
    AlpacaHttpResponse,
    StdlibAlpacaHistoricalBarsTransport,
)
from trading_bot.market_data.exceptions import (
    AlpacaHttpStatusError,
    AlpacaResponseError,
    AlpacaResponseMetadataFailureReason,
    AlpacaTransportError,
    AlpacaTransportFailureStage,
)
from trading_bot.review_paper.alpaca_windows_credentials import (
    read_current_product_alpaca_secrets,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
    UnsupportedNYSEPublishedSessionYearError,
)

D34_SIGNAL_USER_AGENT = "ai-trading-bot-live-signal-d34/1"
D34_SIGNAL_READY = "D34_ALPACA_SIGNAL_INPUTS_READY"
D34_MAX_PROVIDER_CODE = (1 << 63) - 1
D34_MAX_SIGNAL_VOLUME = (1 << 63) - 1

_NEW_YORK = ZoneInfo("America/New_York")
_REQUEST_ID_PATTERN = re.compile(r"^[!-~]{1,256}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SANITIZED_OBSERVATION = datetime(1970, 1, 1, tzinfo=UTC)
_PUBLIC_HEADERS = (
    ("Accept", "application/json"),
    ("Accept-Encoding", "identity"),
    ("User-Agent", D34_SIGNAL_USER_AGENT),
)


class D34FailureKind(StrEnum):
    """Closed categories for a blocked successor observation."""

    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    HTTP_FAILED = "HTTP_FAILED"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RESPONSE_SESSION_MISMATCH = "RESPONSE_SESSION_MISMATCH"
    CREDENTIALS_UNAVAILABLE = "CREDENTIALS_UNAVAILABLE"
    INTERNAL_FAILED = "INTERNAL_FAILED"


class D34SignalInputFailureReason(StrEnum):
    """Fixed, sanitized D34 result reasons."""

    OBSERVATION_INVALID = "D34_OBSERVATION_INVALID"
    SESSION_AUTHORITY_UNAVAILABLE = "D34_SESSION_AUTHORITY_UNAVAILABLE"
    CREDENTIALS_UNAVAILABLE = "D34_CREDENTIALS_UNAVAILABLE"
    TRANSPORT_FAILED = "D34_TRANSPORT_FAILED"
    HTTP_FAILED = "D34_HTTP_FAILED"
    RESPONSE_INVALID = "D34_RESPONSE_INVALID"
    RESPONSE_SESSION_MISMATCH = "D34_RESPONSE_SESSION_MISMATCH"
    INTERNAL_FAILED = "D34_INTERNAL_FAILED"
    OBSERVATION_CONSUMED = "D34_OBSERVATION_CONSUMED"


class _PublishedSessionAuthority(Protocol):
    def schedule_for(self, session_date: date) -> object | None: ...


class _ResponseSessionMismatch(ValueError):
    """Internal distinction for a valid response with the wrong sessions."""


@dataclass(frozen=True, slots=True)
class D34SignalInputResult:
    """Sanitized one-attempt input result and closed failure diagnostics."""

    status: str
    reason: str
    observation_as_of: datetime
    selected_sessions: tuple[date, ...]
    request: AlpacaHistoricalBarsRequest | None
    inputs: CompletedSignalInputs | None
    response_body_sha256: str | None
    response_body_byte_length: int | None
    request_id_digest: str | None
    fast_average: Decimal | None
    slow_average: Decimal | None
    flat_signal: SignalDecision | None
    invested_signal: SignalDecision | None
    provider_call_count: int
    credential_read_count: int
    failure_kind: D34FailureKind | None
    transport_stage: AlpacaTransportFailureStage | None
    metadata_reason: AlpacaResponseMetadataFailureReason | None
    http_status: int | None
    provider_code: int | None

    def __post_init__(self) -> None:
        if self.status not in {"READY", "BLOCKED"} or not self.reason:
            raise ValueError("invalid D34 result status")
        if self.failure_kind is not None and not isinstance(
            self.failure_kind, D34FailureKind
        ):
            raise ValueError("failure kind is not closed")
        if self.transport_stage is not None and not isinstance(
            self.transport_stage, AlpacaTransportFailureStage
        ):
            raise ValueError("transport stage is not closed")
        if self.metadata_reason is not None and not isinstance(
            self.metadata_reason, AlpacaResponseMetadataFailureReason
        ):
            raise ValueError("metadata reason is not closed")
        _utc_datetime(self.observation_as_of, "observation_as_of")
        if self.provider_call_count not in (0, 1) or self.credential_read_count not in (
            0,
            1,
        ):
            raise ValueError("D34 attempt counts are bounded")
        if self.response_body_sha256 is not None and (
            type(self.response_body_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.response_body_sha256) is None
        ):
            raise ValueError("response digest must be a SHA-256 hex digest")
        if self.response_body_byte_length is not None and (
            type(self.response_body_byte_length) is not int
            or self.response_body_byte_length < 0
        ):
            raise ValueError("response byte length must be nonnegative")
        if self.request_id_digest is not None and (
            type(self.request_id_digest) is not str
            or _SHA256_PATTERN.fullmatch(self.request_id_digest) is None
        ):
            raise ValueError("request ID must be digest-only")
        if self.http_status is not None and (
            type(self.http_status) is not int or not 100 <= self.http_status <= 599
        ):
            raise ValueError("HTTP status must be bounded")
        if self.provider_code is not None and (
            type(self.provider_code) is not int
            or not 0 <= self.provider_code <= D34_MAX_PROVIDER_CODE
        ):
            raise ValueError("provider code must be bounded")

        diagnostics = (
            self.transport_stage,
            self.metadata_reason,
            self.http_status,
            self.provider_code,
        )
        if self.status == "READY":
            if (
                self.inputs is None
                or self.request is None
                or self.response_body_sha256 is None
                or self.response_body_byte_length is None
                or self.request_id_digest is None
                or self.fast_average is None
                or self.slow_average is None
                or self.flat_signal is None
                or self.invested_signal is None
                or self.provider_call_count != 1
                or self.credential_read_count != 1
                or self.failure_kind is not None
                or any(value is not None for value in diagnostics)
            ):
                raise ValueError("ready D34 result is incomplete or inconsistent")
            return

        if (
            self.inputs is not None
            or self.failure_kind is None
            or self.response_body_sha256 is not None
            or self.response_body_byte_length is not None
            or self.fast_average is not None
            or self.slow_average is not None
            or self.flat_signal is not None
            or self.invested_signal is not None
        ):
            raise ValueError("blocked D34 result is incomplete")
        if self.failure_kind is D34FailureKind.TRANSPORT_FAILED:
            if (
                self.transport_stage is None
                or self.http_status is not None
                or self.provider_code is not None
                or self.request_id_digest is not None
            ):
                raise ValueError("transport diagnostics are inconsistent")
            if (
                self.transport_stage
                is not AlpacaTransportFailureStage.RESPONSE_METADATA
            ):
                if self.metadata_reason is not None:
                    raise ValueError("metadata reason requires metadata stage")
        elif self.failure_kind is D34FailureKind.HTTP_FAILED:
            if self.transport_stage is not None or self.metadata_reason is not None:
                raise ValueError("HTTP failure contains transport diagnostics")
        elif any(value is not None for value in diagnostics) or self.request_id_digest:
            raise ValueError("non-provider failure contains provider diagnostics")
        if self.failure_kind is not D34FailureKind.HTTP_FAILED and (
            self.request_id_digest is not None
        ):
            raise ValueError("request ID digest requires an HTTP failure")


class _CredentialScope(Protocol):
    def __enter__(self) -> object: ...

    def __exit__(self, *args: object) -> object: ...

    def use(self, consumer: Callable[[str, str], object]) -> object: ...


def derive_published_completion_cutoff(
    selected_sessions: tuple[date, ...],
    observation_as_of: datetime,
    *,
    authority: _PublishedSessionAuthority,
) -> datetime:
    """Return the exact published close for the final selected session."""

    sessions = tuple(selected_sessions)
    if len(sessions) != REQUIRED_COMPLETED_SESSIONS or any(
        type(value) is not date for value in sessions
    ):
        raise ValueError("exactly 60 selected session dates are required")
    if any(left >= right for left, right in zip(sessions, sessions[1:], strict=False)):
        raise ValueError("selected session dates must be strictly increasing")
    observation = _utc_datetime(observation_as_of, "observation_as_of")
    try:
        schedule = authority.schedule_for(sessions[-1])
    except (TypeError, ValueError, UnsupportedNYSEPublishedSessionYearError):
        raise ValueError("D34 final session has no published close") from None
    closes_at = getattr(schedule, "closes_at", None)
    if (
        schedule is None
        or getattr(schedule, "session_date", None) != sessions[-1]
        or type(closes_at) is not datetime
        or closes_at.tzinfo is None
        or closes_at.utcoffset() is None
    ):
        raise ValueError("D34 final session has an invalid published close")
    cutoff = closes_at.astimezone(UTC)
    if cutoff > observation:
        raise ValueError("D34 final session is not complete")
    return cutoff


def build_d34_alpaca_signal_request(
    selected_sessions: tuple[date, ...],
    cutoff: datetime,
) -> AlpacaHistoricalBarsRequest:
    """Build the one exact-range request using the already-derived cutoff."""

    sessions = tuple(selected_sessions)
    if len(sessions) != REQUIRED_COMPLETED_SESSIONS or any(
        type(value) is not date for value in sessions
    ):
        raise ValueError("exactly 60 selected session dates are required")
    if any(left >= right for left, right in zip(sessions, sessions[1:], strict=False)):
        raise ValueError("selected session dates must be strictly increasing")
    cutoff_utc = _utc_datetime(cutoff, "cutoff")
    if cutoff_utc.astimezone(_NEW_YORK).date() != sessions[-1]:
        raise ValueError("cutoff must belong to the final selected session")
    if cutoff_utc.time() == time.min:
        raise ValueError("cutoff must be after the final session midnight")

    start = datetime.combine(sessions[0], time.min, tzinfo=_NEW_YORK).astimezone(UTC)
    parameters = (
        ("symbols", SIGNAL_SYMBOL),
        ("timeframe", ALPACA_SIGNAL_TIMEFRAME),
        ("start", _timestamp(start)),
        ("end", _timestamp(cutoff_utc)),
        ("limit", str(ALPACA_SIGNAL_LIMIT)),
        ("adjustment", ALPACA_SIGNAL_ADJUSTMENT),
        ("asof", ALPACA_SIGNAL_ASOF),
        ("feed", ALPACA_SIGNAL_FEED),
        ("currency", ALPACA_SIGNAL_CURRENCY),
        ("sort", ALPACA_SIGNAL_SORT),
    )
    return AlpacaHistoricalBarsRequest(
        method="GET",
        host=ALPACA_DATA_HOST,
        target=f"/v2/stocks/bars?{urlencode(parameters)}",
        public_headers=_PUBLIC_HEADERS,
    )


class AlpacaSignalRecoveryInputService:
    """One-attempt, source-ready D34 signal-input service."""

    def __init__(
        self,
        *,
        transport_factory: Callable[[], AlpacaHistoricalBarsTransport] | None = None,
        credential_reader: Callable[[], _CredentialScope] | None = None,
        session_authority: _PublishedSessionAuthority | None = None,
    ) -> None:
        if transport_factory is not None and not callable(transport_factory):
            raise TypeError("transport_factory must be callable")
        if credential_reader is not None and not callable(credential_reader):
            raise TypeError("credential_reader must be callable")
        self._transport_factory = (
            StdlibAlpacaHistoricalBarsTransport
            if transport_factory is None
            else transport_factory
        )
        self._credential_reader = (
            read_current_product_alpaca_secrets
            if credential_reader is None
            else credential_reader
        )
        self._session_authority = session_authority
        self._consumed = False

    def observe(self, observation_as_of: datetime) -> D34SignalInputResult:
        """Attempt one read, preserving only closed diagnostics and no retry."""

        try:
            observation = _utc_datetime(observation_as_of, "observation_as_of")
        except (TypeError, ValueError):
            return _blocked(
                D34SignalInputFailureReason.OBSERVATION_INVALID,
                _SANITIZED_OBSERVATION,
                (),
                None,
                failure_kind=D34FailureKind.INTERNAL_FAILED,
                credential_reads=0,
                provider_calls=0,
            )
        if self._consumed:
            return _blocked(
                D34SignalInputFailureReason.OBSERVATION_CONSUMED,
                observation,
                (),
                None,
                failure_kind=D34FailureKind.INTERNAL_FAILED,
                credential_reads=0,
                provider_calls=0,
            )
        self._consumed = True

        authority = (
            NYSEPublishedRegularSessionAuthority()
            if self._session_authority is None
            else self._session_authority
        )
        try:
            selected = select_latest_completed_sessions(
                observation, authority=authority
            )
            cutoff = derive_published_completion_cutoff(
                selected,
                observation,
                authority=authority,
            )
            if cutoff > observation:
                raise ValueError("D34 cutoff exceeds observation")
            request = build_d34_alpaca_signal_request(selected, cutoff)
        except Exception:
            return _blocked(
                D34SignalInputFailureReason.SESSION_AUTHORITY_UNAVAILABLE,
                observation,
                (),
                None,
                failure_kind=D34FailureKind.INTERNAL_FAILED,
                credential_reads=0,
                provider_calls=0,
            )

        try:
            scope = self._credential_reader()
            if not callable(getattr(scope, "use", None)):
                raise TypeError("credential scope is invalid")
        except Exception:
            return _blocked(
                D34SignalInputFailureReason.CREDENTIALS_UNAVAILABLE,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.CREDENTIALS_UNAVAILABLE,
                credential_reads=1,
                provider_calls=0,
            )

        provider_calls = 0
        try:
            with scope:
                transport = self._transport_factory()

                def execute(key: str, secret: str) -> object:
                    nonlocal provider_calls
                    if provider_calls:
                        raise RuntimeError("D34 provider attempt already consumed")
                    provider_calls += 1
                    return transport.execute(
                        request,
                        api_key_id=key,
                        api_secret_key=secret,
                    )

                response = scope.use(execute)
        except AlpacaTransportError as error:
            return _blocked(
                D34SignalInputFailureReason.TRANSPORT_FAILED,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.TRANSPORT_FAILED,
                transport_stage=(
                    error.stage
                    if type(error.stage) is AlpacaTransportFailureStage
                    else AlpacaTransportFailureStage.UNKNOWN
                ),
                metadata_reason=(
                    error.metadata_reason
                    if type(error.metadata_reason)
                    is AlpacaResponseMetadataFailureReason
                    else None
                ),
                credential_reads=1,
                provider_calls=provider_calls,
            )
        except AlpacaHttpStatusError as error:
            return _blocked(
                D34SignalInputFailureReason.HTTP_FAILED,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.HTTP_FAILED,
                request_id_digest=_request_id_digest(error.request_id),
                http_status=_bounded_status(error.status),
                provider_code=_bounded_provider_code(error.provider_code),
                credential_reads=1,
                provider_calls=provider_calls,
            )
        except Exception:
            return _blocked(
                D34SignalInputFailureReason.INTERNAL_FAILED,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.INTERNAL_FAILED,
                credential_reads=1,
                provider_calls=provider_calls,
            )

        if type(response) is not AlpacaHttpResponse:
            return _blocked(
                D34SignalInputFailureReason.RESPONSE_INVALID,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.RESPONSE_INVALID,
                credential_reads=1,
                provider_calls=provider_calls,
            )

        try:
            inputs = _inputs_from_response(response, selected, observation, cutoff)
            fast, slow = moving_averages_35_50(inputs)
            flat = decide_35_50(inputs, invested=False)
            invested = decide_35_50(inputs, invested=True)
        except _ResponseSessionMismatch:
            return _blocked(
                D34SignalInputFailureReason.RESPONSE_SESSION_MISMATCH,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.RESPONSE_SESSION_MISMATCH,
                credential_reads=1,
                provider_calls=provider_calls,
            )
        except (AlpacaResponseError, TypeError, ValueError):
            return _blocked(
                D34SignalInputFailureReason.RESPONSE_INVALID,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.RESPONSE_INVALID,
                credential_reads=1,
                provider_calls=provider_calls,
            )
        except Exception:
            return _blocked(
                D34SignalInputFailureReason.INTERNAL_FAILED,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.INTERNAL_FAILED,
                credential_reads=1,
                provider_calls=provider_calls,
            )

        request_id_digest = _request_id_digest(response.request_id)
        if request_id_digest is None:
            return _blocked(
                D34SignalInputFailureReason.RESPONSE_INVALID,
                observation,
                selected,
                request,
                failure_kind=D34FailureKind.RESPONSE_INVALID,
                credential_reads=1,
                provider_calls=provider_calls,
            )
        return D34SignalInputResult(
            status="READY",
            reason=D34_SIGNAL_READY,
            observation_as_of=observation,
            selected_sessions=selected,
            request=request,
            inputs=inputs,
            response_body_sha256=response.body_sha256,
            response_body_byte_length=response.body_byte_length,
            request_id_digest=request_id_digest,
            fast_average=fast,
            slow_average=slow,
            flat_signal=flat,
            invested_signal=invested,
            provider_call_count=provider_calls,
            credential_read_count=1,
            failure_kind=None,
            transport_stage=None,
            metadata_reason=None,
            http_status=None,
            provider_code=None,
        )


def _inputs_from_response(
    response: AlpacaHttpResponse,
    selected_sessions: tuple[date, ...],
    observation: datetime,
    cutoff: datetime,
) -> CompletedSignalInputs:
    candidates, pagination_complete = parse_alpaca_historical_bars_response(
        response.body
    )
    if not pagination_complete or len(candidates) != REQUIRED_COMPLETED_SESSIONS:
        raise AlpacaResponseError("D34 response pagination or count is invalid")
    if any(candidate.symbol.value != SIGNAL_SYMBOL for candidate in candidates):
        raise AlpacaResponseError("D34 response symbol is invalid")

    sessions: list[date] = []
    closes: list[Decimal] = []
    previous_timestamp: datetime | None = None
    for candidate in candidates:
        timestamp = candidate.timestamp
        local = timestamp.astimezone(_NEW_YORK)
        if local.time() != time.min:
            raise AlpacaResponseError("D34 daily timestamp is not New York midnight")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise AlpacaResponseError("D34 timestamps are not strictly increasing")
        previous_timestamp = timestamp
        if candidate.volume < 0 or candidate.volume > D34_MAX_SIGNAL_VOLUME:
            raise AlpacaResponseError("D34 volume is outside its bound")
        sessions.append(local.date())
        closes.append(candidate.close)
    if tuple(sessions) != selected_sessions:
        raise _ResponseSessionMismatch("D34 response sessions do not match selection")
    if cutoff > observation:
        raise ValueError("D34 cutoff exceeds observation")
    return CompletedSignalInputs(
        symbol=SIGNAL_SYMBOL,
        selected_sessions=selected_sessions,
        sessions=tuple(sessions),
        closes=tuple(closes),
        price_basis=LIVE_SIGNAL_PRICE_BASIS,
        source_digest=response.body_sha256,
        as_of=observation,
        cutoff=cutoff,
    )


def _blocked(
    reason: D34SignalInputFailureReason,
    observation: datetime,
    sessions: tuple[date, ...],
    request: AlpacaHistoricalBarsRequest | None,
    *,
    failure_kind: D34FailureKind,
    credential_reads: int,
    provider_calls: int,
    request_id_digest: str | None = None,
    transport_stage: AlpacaTransportFailureStage | None = None,
    metadata_reason: AlpacaResponseMetadataFailureReason | None = None,
    http_status: int | None = None,
    provider_code: int | None = None,
) -> D34SignalInputResult:
    return D34SignalInputResult(
        status="BLOCKED",
        reason=reason.value,
        observation_as_of=observation,
        selected_sessions=sessions,
        request=request,
        inputs=None,
        response_body_sha256=None,
        response_body_byte_length=None,
        request_id_digest=request_id_digest,
        fast_average=None,
        slow_average=None,
        flat_signal=None,
        invested_signal=None,
        provider_call_count=provider_calls,
        credential_read_count=credential_reads,
        failure_kind=failure_kind,
        transport_stage=transport_stage,
        metadata_reason=metadata_reason,
        http_status=http_status,
        provider_code=provider_code,
    )


def _request_id_digest(value: object) -> str | None:
    if type(value) is not str or _REQUEST_ID_PATTERN.fullmatch(value) is None:
        return None
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _bounded_status(value: object) -> int | None:
    if type(value) is int and 100 <= value <= 599:
        return value
    return None


def _bounded_provider_code(value: object) -> int | None:
    if type(value) is int and 0 <= value <= D34_MAX_PROVIDER_CODE:
        return value
    return None


def _utc_datetime(value: object, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


__all__ = [
    "D34FailureKind",
    "D34SignalInputFailureReason",
    "D34SignalInputResult",
    "AlpacaSignalRecoveryInputService",
    "build_d34_alpaca_signal_request",
    "derive_published_completion_cutoff",
]
