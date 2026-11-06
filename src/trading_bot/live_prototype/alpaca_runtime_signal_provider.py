"""Reusable cached Alpaca signal inputs for the current desktop runtime.

The provider reuses the accepted pure published-session and request builders,
but owns its refresh lifecycle and never invokes either consumed observation
operator. One exact 60-session response is retained for display. It becomes
available to trading only while it matches the latest published completed
session window and the required all-adjusted price basis.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

from trading_bot.live_prototype.alpaca_signal_inputs import (
    LIVE_SIGNAL_PRICE_BASIS,
    REQUIRED_COMPLETED_SESSIONS,
    SIGNAL_SYMBOL,
    select_latest_completed_sessions,
)
from trading_bot.live_prototype.alpaca_signal_recovery_inputs import (
    build_d34_alpaca_signal_request,
    derive_published_completion_cutoff,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.market_data.alpaca_daily_snapshot import (
    parse_alpaca_historical_bars_response,
)
from trading_bot.market_data.alpaca_http import (
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
)

_NEW_YORK = ZoneInfo("America/New_York")
_MAX_SIGNAL_VOLUME = (1 << 63) - 1
_SANITIZED_OBSERVATION = datetime(1970, 1, 1, tzinfo=UTC)


class RuntimeSignalReason(StrEnum):
    """Closed public outcomes; provider details are deliberately omitted."""

    READY = "ALPACA_RUNTIME_SIGNAL_READY"
    OBSERVATION_INVALID = "ALPACA_RUNTIME_OBSERVATION_INVALID"
    SESSION_AUTHORITY_UNAVAILABLE = "ALPACA_RUNTIME_SESSION_AUTHORITY_UNAVAILABLE"
    CREDENTIALS_UNAVAILABLE = "ALPACA_RUNTIME_CREDENTIALS_UNAVAILABLE"
    PROVIDER_FAILED = "ALPACA_RUNTIME_PROVIDER_FAILED"
    RESPONSE_INVALID = "ALPACA_RUNTIME_RESPONSE_INVALID"
    RESPONSE_SESSION_MISMATCH = "ALPACA_RUNTIME_RESPONSE_SESSION_MISMATCH"
    REFRESH_ALREADY_ATTEMPTED = "ALPACA_RUNTIME_REFRESH_ALREADY_ATTEMPTED"
    CLOCK_REGRESSION = "ALPACA_RUNTIME_CLOCK_REGRESSION"


class _PublishedSessionAuthority(Protocol):
    def schedule_for(self, session_date: date) -> object | None: ...


class _CredentialScope(Protocol):
    def __enter__(self) -> _CredentialScope: ...

    def __exit__(self, *args: object) -> None: ...

    def use(
        self, consumer: Callable[[str, str], AlpacaHttpResponse]
    ) -> AlpacaHttpResponse: ...


@dataclass(frozen=True, slots=True)
class RuntimeSignalSnapshot:
    """One sanitized display snapshot and its independent trading gate."""

    status: str
    reason: RuntimeSignalReason
    observation_as_of: datetime
    selected_sessions: tuple[date, ...]
    display_inputs: CompletedSignalInputs | None
    stale: bool
    refreshed: bool
    credential_read_count: int
    provider_call_count: int

    def __post_init__(self) -> None:
        if self.status not in {"READY", "BLOCKED"}:
            raise ValueError("runtime signal status is invalid")
        if not isinstance(self.reason, RuntimeSignalReason):
            raise ValueError("runtime signal reason is not closed")
        if (
            type(self.observation_as_of) is not datetime
            or self.observation_as_of.tzinfo is None
            or self.observation_as_of.utcoffset() != UTC.utcoffset(None)
        ):
            raise ValueError("runtime observation must be UTC aware")
        if type(self.selected_sessions) is not tuple or len(
            self.selected_sessions
        ) not in {0, REQUIRED_COMPLETED_SESSIONS}:
            raise ValueError("runtime session window must contain exactly 60 dates")
        if any(type(item) is not date for item in self.selected_sessions) or any(
            left >= right
            for left, right in zip(
                self.selected_sessions, self.selected_sessions[1:], strict=False
            )
        ):
            raise ValueError("runtime sessions must be ordered dates")
        if type(self.stale) is not bool or type(self.refreshed) is not bool:
            raise ValueError("runtime freshness flags must be boolean")
        if self.credential_read_count not in (0, 1) or self.provider_call_count not in (
            0,
            1,
        ):
            raise ValueError("runtime read counts are bounded")
        if self.provider_call_count > self.credential_read_count:
            raise ValueError("runtime provider calls require a credential scope")
        if self.refreshed != (self.status == "READY" and self.provider_call_count == 1):
            raise ValueError("runtime refresh flag disagrees with provider result")
        if self.status == "READY":
            if (
                self.reason is not RuntimeSignalReason.READY
                or self.display_inputs is None
                or self.stale
                or self.selected_sessions != self.display_inputs.selected_sessions
            ):
                raise ValueError("ready runtime signal snapshot is inconsistent")
        elif self.reason is RuntimeSignalReason.READY:
            raise ValueError("blocked runtime signal snapshot has a ready reason")

    @property
    def inputs_for_trading(self) -> CompletedSignalInputs | None:
        """Return fresh signal data; this gate grants no mode or order authority."""

        inputs = self.display_inputs
        if (
            self.status != "READY"
            or self.stale
            or type(inputs) is not CompletedSignalInputs
            or inputs.symbol != SIGNAL_SYMBOL
            or inputs.price_basis != LIVE_SIGNAL_PRICE_BASIS
            or inputs.selected_sessions != self.selected_sessions
            or len(inputs.closes) != REQUIRED_COMPLETED_SESSIONS
        ):
            return None
        return inputs


class AlpacaRuntimeSignalProvider:
    """Refresh once per newly completed XNYS window and retain one bounded cache.

    Constructing the provider performs no clock, credential, or provider work.
    Calling :meth:`snapshot` is the explicit runtime read boundary. A failed
    refresh is attempted once for that completed-session window; cached inputs
    remain display-only until a later successful window refresh.
    """

    def __init__(
        self,
        *,
        transport_factory: Callable[[], AlpacaHistoricalBarsTransport] | None = None,
        credential_reader: Callable[[], _CredentialScope] | None = None,
        session_authority: _PublishedSessionAuthority | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if transport_factory is not None and not callable(transport_factory):
            raise TypeError("transport_factory must be callable")
        if credential_reader is not None and not callable(credential_reader):
            raise TypeError("credential_reader must be callable")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
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
        self._session_authority = (
            NYSEPublishedRegularSessionAuthority()
            if session_authority is None
            else session_authority
        )
        self._clock = clock
        self._cached_inputs: CompletedSignalInputs | None = None
        self._last_attempted_sessions: tuple[date, ...] | None = None

    def snapshot(
        self, observation_as_of: datetime | None = None
    ) -> RuntimeSignalSnapshot:
        """Return a fresh signal snapshot or a blocked stale/unavailable view."""

        try:
            raw_observation = (
                self._clock()
                if observation_as_of is None and self._clock is not None
                else datetime.now(UTC)
                if observation_as_of is None
                else observation_as_of
            )
            observation = _utc_datetime(raw_observation)
        except Exception:
            return self._blocked(
                RuntimeSignalReason.OBSERVATION_INVALID,
                _SANITIZED_OBSERVATION,
                (),
            )

        try:
            selected = select_latest_completed_sessions(
                observation,
                authority=self._session_authority,
            )
        except (TypeError, ValueError):
            return self._blocked(
                RuntimeSignalReason.SESSION_AUTHORITY_UNAVAILABLE,
                observation,
                (),
            )

        if self._cached_inputs is not None:
            cached_sessions = self._cached_inputs.selected_sessions
            if selected[-1] < cached_sessions[-1]:
                return self._blocked(
                    RuntimeSignalReason.CLOCK_REGRESSION,
                    observation,
                    selected,
                )
            if selected == cached_sessions:
                return RuntimeSignalSnapshot(
                    status="READY",
                    reason=RuntimeSignalReason.READY,
                    observation_as_of=observation,
                    selected_sessions=selected,
                    display_inputs=self._cached_inputs,
                    stale=False,
                    refreshed=False,
                    credential_read_count=0,
                    provider_call_count=0,
                )

        if self._last_attempted_sessions == selected:
            return self._blocked(
                RuntimeSignalReason.REFRESH_ALREADY_ATTEMPTED,
                observation,
                selected,
            )

        self._last_attempted_sessions = selected
        try:
            cutoff = derive_published_completion_cutoff(
                selected,
                observation,
                authority=self._session_authority,
            )
            request = build_d34_alpaca_signal_request(selected, cutoff)
        except (TypeError, ValueError):
            return self._blocked(
                RuntimeSignalReason.SESSION_AUTHORITY_UNAVAILABLE,
                observation,
                selected,
            )

        try:
            scope = self._credential_reader()
        except Exception:
            return self._blocked(
                RuntimeSignalReason.CREDENTIALS_UNAVAILABLE,
                observation,
                selected,
                credential_read_count=1,
            )
        if not callable(getattr(scope, "use", None)):
            return self._blocked(
                RuntimeSignalReason.CREDENTIALS_UNAVAILABLE,
                observation,
                selected,
                credential_read_count=1,
            )

        provider_calls = 0

        def execute(api_key_id: str, api_secret_key: str) -> AlpacaHttpResponse:
            nonlocal provider_calls
            if provider_calls:
                raise RuntimeError("runtime signal provider attempt consumed")
            provider_calls = 1
            transport = self._transport_factory()
            return transport.execute(
                request,
                api_key_id=api_key_id,
                api_secret_key=api_secret_key,
            )

        try:
            with scope:
                response = scope.use(execute)
        except Exception:
            return self._blocked(
                RuntimeSignalReason.PROVIDER_FAILED,
                observation,
                selected,
                credential_read_count=1,
                provider_call_count=provider_calls,
            )

        try:
            inputs = _inputs_from_response(
                response,
                selected,
                observation,
                cutoff,
            )
        except _ResponseSessionMismatch:
            return self._blocked(
                RuntimeSignalReason.RESPONSE_SESSION_MISMATCH,
                observation,
                selected,
                credential_read_count=1,
                provider_call_count=provider_calls,
            )
        except (AlpacaResponseError, TypeError, ValueError, AttributeError):
            return self._blocked(
                RuntimeSignalReason.RESPONSE_INVALID,
                observation,
                selected,
                credential_read_count=1,
                provider_call_count=provider_calls,
            )

        self._cached_inputs = inputs
        return RuntimeSignalSnapshot(
            status="READY",
            reason=RuntimeSignalReason.READY,
            observation_as_of=observation,
            selected_sessions=selected,
            display_inputs=inputs,
            stale=False,
            refreshed=True,
            credential_read_count=1,
            provider_call_count=provider_calls,
        )

    def _blocked(
        self,
        reason: RuntimeSignalReason,
        observation: datetime,
        selected: tuple[date, ...],
        *,
        credential_read_count: int = 0,
        provider_call_count: int = 0,
    ) -> RuntimeSignalSnapshot:
        cached = self._cached_inputs
        stale = cached is not None and selected != cached.selected_sessions
        return RuntimeSignalSnapshot(
            status="BLOCKED",
            reason=reason,
            observation_as_of=observation,
            selected_sessions=selected,
            display_inputs=cached,
            stale=stale,
            refreshed=False,
            credential_read_count=credential_read_count,
            provider_call_count=provider_call_count,
        )


class _ResponseSessionMismatch(ValueError):
    """The provider returned a different ordered session tuple."""


def _inputs_from_response(
    response: AlpacaHttpResponse,
    selected_sessions: tuple[date, ...],
    observation: datetime,
    cutoff: datetime,
) -> CompletedSignalInputs:
    if not isinstance(response, AlpacaHttpResponse):
        raise AlpacaResponseError("runtime response type is invalid")
    candidates, pagination_complete = parse_alpaca_historical_bars_response(
        response.body
    )
    if not pagination_complete or len(candidates) != REQUIRED_COMPLETED_SESSIONS:
        raise AlpacaResponseError("runtime response count or pagination is invalid")

    sessions: list[date] = []
    closes: list[Decimal] = []
    previous_timestamp: datetime | None = None
    for candidate in candidates:
        if candidate.symbol.value != SIGNAL_SYMBOL:
            raise AlpacaResponseError("runtime response symbol is invalid")
        timestamp = candidate.timestamp
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise AlpacaResponseError("runtime bar timestamp is not aware")
        local_timestamp = timestamp.astimezone(_NEW_YORK)
        if local_timestamp.time() != time.min:
            raise AlpacaResponseError("runtime daily bar is not New York midnight")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise AlpacaResponseError("runtime timestamps are not increasing")
        previous_timestamp = timestamp
        if (
            type(candidate.volume) is not int
            or not 0 <= candidate.volume <= _MAX_SIGNAL_VOLUME
        ):
            raise AlpacaResponseError("runtime volume is outside its bound")
        sessions.append(local_timestamp.date())
        closes.append(candidate.close)

    if tuple(sessions) != selected_sessions:
        raise _ResponseSessionMismatch

    if cutoff.tzinfo is None or cutoff.utcoffset() is None or cutoff > observation:
        raise ValueError("final published session is not complete")

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


def _utc_datetime(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("runtime observation must be timezone aware")
    return value.astimezone(UTC)


__all__ = [
    "AlpacaRuntimeSignalProvider",
    "RuntimeSignalReason",
    "RuntimeSignalSnapshot",
]
