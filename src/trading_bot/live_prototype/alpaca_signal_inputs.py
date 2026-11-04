"""Additive D33 Alpaca all-adjusted current signal inputs.

This module is a data-source successor for the live prototype.  It does not
replace the P6 Robinhood history implementation and it does not bind a
strategy to a runtime or grant any execution authority.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from trading_bot.live_prototype.configuration import (
    CompletedSignalInputs,
    SelectedStrategyBinding,
)
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
from trading_bot.market_data.exceptions import AlpacaResponseError
from trading_bot.review_paper.alpaca_windows_credentials import (
    read_current_product_alpaca_secrets,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
    UnsupportedNYSEPublishedSessionYearError,
)

LIVE_SIGNAL_PRICE_BASIS = "ALPACA_ALL_ADJUSTED_PRICE_V1"
SIGNAL_SYMBOL = "SPY"
REQUIRED_COMPLETED_SESSIONS = 60
ALPACA_SIGNAL_TIMEFRAME = "1Day"
ALPACA_SIGNAL_ADJUSTMENT = "all"
ALPACA_SIGNAL_ASOF = "-"
ALPACA_SIGNAL_FEED = "sip"
ALPACA_SIGNAL_CURRENCY = "USD"
ALPACA_SIGNAL_SORT = "asc"
ALPACA_SIGNAL_LIMIT = REQUIRED_COMPLETED_SESSIONS
ALPACA_SIGNAL_USER_AGENT = "ai-trading-bot-live-signal-d33/1"
MAX_SIGNAL_VOLUME = (1 << 63) - 1

RESEARCH_CONTROL_CANDIDATE = "BASE_MA35_50_V1"
RESEARCH_BUNDLE_SHA256 = (
    "94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11"
)
RESEARCH_DATASET_SHA256 = (
    "ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214"
)
RESEARCH_DATASET_ID = "d5aa8ed7-b5cd-53a3-8671-5370f976e8e3"
RESEARCH_CAMPAIGN_ID = "9b2a000e-3adc-50f4-ab47-2aa90665e3c9"
RESEARCH_BUNDLE_ID = "f01a39a7-0a65-55bb-9d38-608b1ce0bd21"
RESEARCH_SELECTED_RESULT = "NONE_QUALIFIES"
RESEARCH_CONTROL_CANDIDATE_ID = "21158358-75be-5597-b940-5bccdda1429c"

_NEW_YORK = ZoneInfo("America/New_York")
_ARITHMETIC_CONTEXT = Context(prec=50)
_SANITIZED_OBSERVATION = datetime(1970, 1, 1, tzinfo=UTC)
_PUBLIC_HEADERS = (
    ("Accept", "application/json"),
    ("Accept-Encoding", "identity"),
    ("User-Agent", ALPACA_SIGNAL_USER_AGENT),
)


class SignalInputFailureReason(StrEnum):
    """Fixed, sanitized D33 failure categories."""

    OBSERVATION_INVALID = "D33_OBSERVATION_INVALID"
    SESSION_AUTHORITY_UNAVAILABLE = "D33_SESSION_AUTHORITY_UNAVAILABLE"
    INSUFFICIENT_COMPLETED_SESSIONS = "D33_INSUFFICIENT_COMPLETED_SESSIONS"
    CREDENTIALS_UNAVAILABLE = "D33_CREDENTIALS_UNAVAILABLE"
    PROVIDER_REQUEST_FAILED = "D33_PROVIDER_REQUEST_FAILED"
    RESPONSE_INVALID = "D33_RESPONSE_INVALID"
    RESPONSE_SESSION_MISMATCH = "D33_RESPONSE_SESSION_MISMATCH"
    COMPLETED_INPUTS_INVALID = "D33_COMPLETED_INPUTS_INVALID"
    OBSERVATION_CONSUMED = "D33_OBSERVATION_CONSUMED"


class SignalDecision(StrEnum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class ResearchBindingProvenance:
    """Immutable D30/D31 comparison provenance; never live authority."""

    dataset_id: str = RESEARCH_DATASET_ID
    dataset_sha256: str = RESEARCH_DATASET_SHA256
    campaign_id: str = RESEARCH_CAMPAIGN_ID
    bundle_id: str = RESEARCH_BUNDLE_ID
    bundle_sha256: str = RESEARCH_BUNDLE_SHA256
    selected_result: str = RESEARCH_SELECTED_RESULT
    control_candidate_id: str = RESEARCH_CONTROL_CANDIDATE_ID
    candidate: str = RESEARCH_CONTROL_CANDIDATE
    price_basis: str = LIVE_SIGNAL_PRICE_BASIS
    purpose: str = "RESEARCH_COMPARISON"
    live_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.dataset_id != RESEARCH_DATASET_ID
            or self.dataset_sha256 != RESEARCH_DATASET_SHA256
            or self.campaign_id != RESEARCH_CAMPAIGN_ID
            or self.bundle_id != RESEARCH_BUNDLE_ID
            or self.bundle_sha256 != RESEARCH_BUNDLE_SHA256
            or self.selected_result != RESEARCH_SELECTED_RESULT
            or self.control_candidate_id != RESEARCH_CONTROL_CANDIDATE_ID
            or self.candidate != RESEARCH_CONTROL_CANDIDATE
            or self.price_basis != LIVE_SIGNAL_PRICE_BASIS
            or self.purpose != "RESEARCH_COMPARISON"
            or self.live_eligible is not False
        ):
            raise ValueError("accepted D30/D31 research provenance is frozen")


RESEARCH_BINDING_PROVENANCE = ResearchBindingProvenance()
RESEARCH_CONTROL_BINDING = SelectedStrategyBinding(
    candidate=RESEARCH_CONTROL_CANDIDATE,
    research_digest=RESEARCH_BUNDLE_SHA256,
    dataset_digest=RESEARCH_DATASET_SHA256,
    price_basis=LIVE_SIGNAL_PRICE_BASIS,
    purpose="RESEARCH_COMPARISON",
    live_eligible=False,
)


class _PublishedSessionAuthority(Protocol):
    def schedule_for(self, session_date: date) -> object | None: ...


def select_latest_completed_sessions(
    observation_as_of: datetime,
    *,
    authority: _PublishedSessionAuthority | None = None,
) -> tuple[date, ...]:
    """Select the latest 60 completed published XNYS sessions.

    The authority is the source-owned published-session manifest used by the
    current live path.  This deliberately walks calendar dates and asks the
    authority about each date; it never infers weekdays or repairs a provider
    response by sorting or filling it.
    """

    observation = _utc_datetime(observation_as_of, "observation_as_of")
    session_authority = (
        NYSEPublishedRegularSessionAuthority() if authority is None else authority
    )
    if not callable(getattr(session_authority, "schedule_for", None)):
        raise ValueError("published session authority is invalid")

    selected: list[date] = []
    current = observation.astimezone(_NEW_YORK).date()
    while len(selected) < REQUIRED_COMPLETED_SESSIONS:
        try:
            schedule = session_authority.schedule_for(current)
        except (UnsupportedNYSEPublishedSessionYearError, ValueError, TypeError):
            raise ValueError(
                "published session authority cannot cover observation"
            ) from None
        if schedule is not None:
            closes_at = getattr(schedule, "closes_at", None)
            if (
                type(closes_at) is not datetime
                or closes_at.tzinfo is None
                or closes_at.utcoffset() is None
            ):
                raise ValueError("published session authority returned invalid close")
            if observation >= closes_at.astimezone(UTC):
                selected.append(current)
        current -= timedelta(days=1)
        if current.year < 1998:
            raise ValueError("published session authority lacks 60 completed sessions")
    return tuple(reversed(selected))


def build_alpaca_signal_request(
    selected_sessions: tuple[date, ...],
) -> AlpacaHistoricalBarsRequest:
    """Build one deterministic exact-range, no-pagination Alpaca request."""

    sessions = tuple(selected_sessions)
    if len(sessions) != REQUIRED_COMPLETED_SESSIONS or any(
        type(value) is not date for value in sessions
    ):
        raise ValueError("exactly 60 selected session dates are required")
    if any(left >= right for left, right in zip(sessions, sessions[1:], strict=False)):
        raise ValueError("selected session dates must be strictly increasing")

    start = datetime.combine(sessions[0], time.min, tzinfo=_NEW_YORK).astimezone(UTC)
    end_exclusive = datetime.combine(
        sessions[-1] + timedelta(days=1), time.min, tzinfo=_NEW_YORK
    ).astimezone(UTC)
    end_inclusive = end_exclusive - timedelta(microseconds=1)
    parameters = (
        ("symbols", SIGNAL_SYMBOL),
        ("timeframe", ALPACA_SIGNAL_TIMEFRAME),
        ("start", _timestamp(start)),
        ("end", _timestamp(end_inclusive)),
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


def moving_averages_35_50(
    inputs: CompletedSignalInputs,
) -> tuple[Decimal, Decimal]:
    """Return fixed-context arithmetic means over the exact 35/50 closes."""

    _require_signal_inputs(inputs)
    with localcontext(_ARITHMETIC_CONTEXT):
        fast = sum(inputs.closes[-35:], start=Decimal("0")) / Decimal(35)
        slow = sum(inputs.closes[-50:], start=Decimal("0")) / Decimal(50)
    return fast, slow


def decide_35_50(
    inputs: CompletedSignalInputs,
    *,
    invested: bool,
) -> SignalDecision:
    """Apply the accepted BASE_MA35_50_V1 formula without runtime effects."""

    if type(invested) is not bool:
        raise TypeError("invested must be bool")
    fast, slow = moving_averages_35_50(inputs)
    if fast == slow:
        return SignalDecision.HOLD
    if fast > slow:
        return SignalDecision.HOLD if invested else SignalDecision.BUY
    return SignalDecision.SELL if invested else SignalDecision.HOLD


@dataclass(frozen=True, slots=True)
class SignalInputResult:
    """Sanitized one-attempt result; blocked results contain no provider text."""

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

    def __post_init__(self) -> None:
        if self.status not in {"READY", "BLOCKED"} or not self.reason:
            raise ValueError("invalid D33 result status")
        _utc_datetime(self.observation_as_of, "observation_as_of")
        if self.provider_call_count not in (0, 1) or self.credential_read_count not in (
            0,
            1,
        ):
            raise ValueError("D33 attempt counts are bounded")
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
            ):
                raise ValueError("ready D33 result is incomplete")
        elif self.inputs is not None or self.provider_call_count > 1:
            raise ValueError("blocked D33 result contains unsafe evidence")


class _CredentialScope(Protocol):
    def __enter__(self) -> object: ...

    def __exit__(self, *args: object) -> object: ...

    def use(self, consumer: Callable[[str, str], object]) -> object: ...


class AlpacaSignalInputService:
    """One-attempt injected service for the D33 current signal data leg."""

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

    def observe(self, observation_as_of: datetime) -> SignalInputResult:
        """Attempt one read; every failure is sanitized and never retried."""

        observation: datetime
        try:
            observation = _utc_datetime(observation_as_of, "observation_as_of")
        except (TypeError, ValueError):
            return _blocked(
                SignalInputFailureReason.OBSERVATION_INVALID,
                _SANITIZED_OBSERVATION,
                (),
                None,
                credential_reads=0,
                provider_calls=0,
            )
        if self._consumed:
            return _blocked(
                SignalInputFailureReason.OBSERVATION_CONSUMED,
                observation,
                (),
                None,
                credential_reads=0,
                provider_calls=0,
            )
        self._consumed = True

        try:
            selected = select_latest_completed_sessions(
                observation,
                authority=self._session_authority,
            )
            request = build_alpaca_signal_request(selected)
        except (TypeError, ValueError):
            return _blocked(
                SignalInputFailureReason.SESSION_AUTHORITY_UNAVAILABLE,
                observation,
                (),
                None,
                credential_reads=0,
                provider_calls=0,
            )

        try:
            scope = self._credential_reader()
            if not callable(getattr(scope, "use", None)):
                raise TypeError("credential scope is invalid")
        except Exception:
            return _blocked(
                SignalInputFailureReason.CREDENTIALS_UNAVAILABLE,
                observation,
                selected,
                request,
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
                        raise RuntimeError("D33 provider attempt already consumed")
                    provider_calls += 1
                    return transport.execute(
                        request,
                        api_key_id=key,
                        api_secret_key=secret,
                    )

                response = scope.use(execute)
        except Exception:
            return _blocked(
                SignalInputFailureReason.PROVIDER_REQUEST_FAILED,
                observation,
                selected,
                request,
                credential_reads=1,
                provider_calls=provider_calls,
            )

        if type(response) is not AlpacaHttpResponse:
            return _blocked(
                SignalInputFailureReason.RESPONSE_INVALID,
                observation,
                selected,
                request,
                credential_reads=1,
                provider_calls=provider_calls,
            )

        try:
            inputs = _inputs_from_response(
                response,
                selected,
                observation,
                session_authority=self._session_authority,
            )
            fast, slow = moving_averages_35_50(inputs)
            flat = decide_35_50(inputs, invested=False)
            invested = decide_35_50(inputs, invested=True)
        except AlpacaResponseError:
            return _blocked(
                SignalInputFailureReason.RESPONSE_INVALID,
                observation,
                selected,
                request,
                credential_reads=1,
                provider_calls=provider_calls,
            )
        except ValueError:
            return _blocked(
                SignalInputFailureReason.RESPONSE_SESSION_MISMATCH,
                observation,
                selected,
                request,
                credential_reads=1,
                provider_calls=provider_calls,
            )

        return SignalInputResult(
            status="READY",
            reason="D33_ALPACA_SIGNAL_INPUTS_READY",
            observation_as_of=observation,
            selected_sessions=selected,
            request=request,
            inputs=inputs,
            response_body_sha256=response.body_sha256,
            response_body_byte_length=response.body_byte_length,
            request_id_digest=hashlib.sha256(
                response.request_id.encode("ascii")
            ).hexdigest(),
            fast_average=fast,
            slow_average=slow,
            flat_signal=flat,
            invested_signal=invested,
            provider_call_count=provider_calls,
            credential_read_count=1,
        )


def _inputs_from_response(
    response: AlpacaHttpResponse,
    selected_sessions: tuple[date, ...],
    observation: datetime,
    *,
    session_authority: _PublishedSessionAuthority | None,
) -> CompletedSignalInputs:
    candidates, pagination_complete = parse_alpaca_historical_bars_response(
        response.body
    )
    if not pagination_complete or len(candidates) != REQUIRED_COMPLETED_SESSIONS:
        raise AlpacaResponseError("D33 response pagination or count is invalid")
    if any(candidate.symbol.value != SIGNAL_SYMBOL for candidate in candidates):
        raise AlpacaResponseError("D33 response symbol is invalid")

    sessions: list[date] = []
    closes: list[Decimal] = []
    previous_timestamp: datetime | None = None
    for candidate in candidates:
        timestamp = candidate.timestamp
        local = timestamp.astimezone(_NEW_YORK)
        if local.time() != time.min:
            raise AlpacaResponseError("D33 daily timestamp is not New York midnight")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise AlpacaResponseError("D33 timestamps are not strictly increasing")
        previous_timestamp = timestamp
        if candidate.volume < 0 or candidate.volume > MAX_SIGNAL_VOLUME:
            raise AlpacaResponseError("D33 volume is outside its bound")
        sessions.append(local.date())
        closes.append(candidate.close)

    if tuple(sessions) != selected_sessions:
        raise ValueError("D33 response sessions do not match selected sessions")
    cutoff = _completion_cutoff(
        selected_sessions[-1], observation, authority=session_authority
    )
    try:
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
    except ValueError as error:
        raise ValueError("D33 completed signal inputs are not admissible") from error


def _completion_cutoff(
    session_date: date,
    observation: datetime,
    *,
    authority: _PublishedSessionAuthority | None,
) -> datetime:
    session_authority = (
        NYSEPublishedRegularSessionAuthority() if authority is None else authority
    )
    try:
        schedule = session_authority.schedule_for(session_date)
    except (TypeError, ValueError, UnsupportedNYSEPublishedSessionYearError):
        raise ValueError("D33 final session has no published close") from None
    closes_at = getattr(schedule, "closes_at", None)
    if (
        schedule is None
        or getattr(schedule, "session_date", None) != session_date
        or type(closes_at) is not datetime
        or closes_at.tzinfo is None
        or closes_at.utcoffset() is None
    ):
        raise ValueError("D33 final session has an invalid published close")
    cutoff = closes_at.astimezone(UTC)
    if observation < cutoff:
        raise ValueError("D33 final session is not complete")
    return cutoff


def _require_signal_inputs(inputs: CompletedSignalInputs) -> None:
    if type(inputs) is not CompletedSignalInputs:
        raise TypeError("CompletedSignalInputs required")
    if (
        len(inputs.closes) != REQUIRED_COMPLETED_SESSIONS
        or inputs.price_basis != LIVE_SIGNAL_PRICE_BASIS
    ):
        raise ValueError("D33 requires exactly 60 all-adjusted closes")


def _blocked(
    reason: SignalInputFailureReason,
    observation: datetime,
    sessions: tuple[date, ...],
    request: AlpacaHistoricalBarsRequest | None,
    *,
    credential_reads: int,
    provider_calls: int,
) -> SignalInputResult:
    return SignalInputResult(
        status="BLOCKED",
        reason=reason.value,
        observation_as_of=observation,
        selected_sessions=sessions,
        request=request,
        inputs=None,
        response_body_sha256=None,
        response_body_byte_length=None,
        request_id_digest=None,
        fast_average=None,
        slow_average=None,
        flat_signal=None,
        invested_signal=None,
        provider_call_count=provider_calls,
        credential_read_count=credential_reads,
    )


def _utc_datetime(value: object, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


__all__ = [
    "ALPACA_SIGNAL_ADJUSTMENT",
    "ALPACA_SIGNAL_ASOF",
    "ALPACA_SIGNAL_CURRENCY",
    "ALPACA_SIGNAL_FEED",
    "ALPACA_SIGNAL_LIMIT",
    "ALPACA_SIGNAL_SORT",
    "ALPACA_SIGNAL_TIMEFRAME",
    "AlpacaSignalInputService",
    "LIVE_SIGNAL_PRICE_BASIS",
    "RESEARCH_BINDING_PROVENANCE",
    "RESEARCH_BUNDLE_ID",
    "RESEARCH_BUNDLE_SHA256",
    "RESEARCH_CAMPAIGN_ID",
    "RESEARCH_CONTROL_BINDING",
    "RESEARCH_CONTROL_CANDIDATE",
    "RESEARCH_CONTROL_CANDIDATE_ID",
    "RESEARCH_DATASET_ID",
    "RESEARCH_DATASET_SHA256",
    "RESEARCH_SELECTED_RESULT",
    "REQUIRED_COMPLETED_SESSIONS",
    "SIGNAL_SYMBOL",
    "SignalDecision",
    "SignalInputFailureReason",
    "SignalInputResult",
    "ResearchBindingProvenance",
    "build_alpaca_signal_request",
    "decide_35_50",
    "moving_averages_35_50",
    "select_latest_completed_sessions",
]
