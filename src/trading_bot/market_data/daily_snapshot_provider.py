"""Provider-neutral contracts for one-attempt daily snapshot capture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from trading_bot.market_calendar import (
    MarketCalendar,
    TradingSession,
    TradingSessionRange,
)
from trading_bot.market_data.daily_snapshot_models import (
    CalendarDescriptor,
    DailyProviderRequest,
    DailyProviderResponse,
    DailySnapshotAcceptanceResult,
    DailySnapshotCaptureRequest,
    ProviderDescriptor,
)
from trading_bot.market_data.exceptions import (
    InvalidDailySnapshotCalendarError,
    InvalidDailySnapshotProviderError,
    InvalidDailySnapshotResponseError,
)


class IdentifiedMarketCalendar(Protocol):
    """A market calendar bound to an exact stable descriptor."""

    @property
    def descriptor(self) -> CalendarDescriptor: ...

    def is_trading_session(self, value: datetime) -> bool: ...

    def next_session(self, value: datetime) -> TradingSession: ...

    def previous_session(self, value: datetime) -> TradingSession: ...

    def sessions_between(
        self, start: datetime, end: datetime
    ) -> TradingSessionRange: ...


@dataclass(frozen=True, slots=True)
class BoundMarketCalendar:
    """Expose an existing calendar through an explicit descriptor binding."""

    descriptor: CalendarDescriptor
    calendar: MarketCalendar

    def __post_init__(self) -> None:
        if type(self.descriptor) is not CalendarDescriptor:
            raise InvalidDailySnapshotCalendarError(
                "descriptor must be a CalendarDescriptor"
            )
        for method_name in (
            "is_trading_session",
            "next_session",
            "previous_session",
            "sessions_between",
        ):
            if not callable(getattr(self.calendar, method_name, None)):
                raise InvalidDailySnapshotCalendarError(
                    "calendar must implement the MarketCalendar protocol"
                )

    def is_trading_session(self, value: datetime) -> bool:
        return self.calendar.is_trading_session(value)

    def next_session(self, value: datetime) -> TradingSession:
        return self.calendar.next_session(value)

    def previous_session(self, value: datetime) -> TradingSession:
        return self.calendar.previous_session(value)

    def sessions_between(self, start: datetime, end: datetime) -> TradingSessionRange:
        return self.calendar.sessions_between(start, end)


class DailySnapshotProvider(Protocol):
    """One provider call represents exactly one request and one response."""

    @property
    def descriptor(self) -> ProviderDescriptor: ...

    def fetch(self, request: DailyProviderRequest) -> DailyProviderResponse: ...


def require_matching_calendar(
    request: DailySnapshotCaptureRequest,
    calendar: IdentifiedMarketCalendar,
) -> None:
    """Require the supplied implementation to expose the exact request descriptor."""
    descriptor = getattr(calendar, "descriptor", None)
    if type(descriptor) is not CalendarDescriptor:
        raise InvalidDailySnapshotCalendarError(
            "calendar must expose a CalendarDescriptor"
        )
    if descriptor != request.calendar:
        raise InvalidDailySnapshotCalendarError(
            "calendar descriptor does not match the capture request"
        )
    for method_name in (
        "is_trading_session",
        "next_session",
        "previous_session",
        "sessions_between",
    ):
        if not callable(getattr(calendar, method_name, None)):
            raise InvalidDailySnapshotCalendarError(
                "calendar must implement the identified calendar protocol"
            )


def derive_completed_session(
    request: DailySnapshotCaptureRequest,
    calendar: IdentifiedMarketCalendar,
) -> TradingSession:
    """Return the most recent modeled session strictly before the local date."""
    if type(request) is not DailySnapshotCaptureRequest:
        raise InvalidDailySnapshotCalendarError(
            "request must be a DailySnapshotCaptureRequest"
        )
    require_matching_calendar(request, calendar)
    target = calendar.previous_session(request.requested_at)
    if type(target) is not TradingSession:
        raise InvalidDailySnapshotCalendarError(
            "calendar previous_session must return TradingSession"
        )
    return target


def build_daily_provider_request(
    request: DailySnapshotCaptureRequest,
    provider: ProviderDescriptor,
    calendar: IdentifiedMarketCalendar,
) -> DailyProviderRequest:
    """Freeze the target session before any provider attempt."""
    if type(request) is not DailySnapshotCaptureRequest:
        raise InvalidDailySnapshotProviderError(
            "request must be a DailySnapshotCaptureRequest"
        )
    if type(provider) is not ProviderDescriptor:
        raise InvalidDailySnapshotProviderError("provider must be a ProviderDescriptor")
    target = derive_completed_session(request, calendar)
    return DailyProviderRequest(request, target, provider)


def capture_daily_snapshot(
    request: DailySnapshotCaptureRequest,
    provider: DailySnapshotProvider,
    calendar: IdentifiedMarketCalendar,
) -> DailySnapshotAcceptanceResult:
    """Call one provider exactly once and accept or reject its one response."""
    descriptor = getattr(provider, "descriptor", None)
    if type(descriptor) is not ProviderDescriptor:
        raise InvalidDailySnapshotProviderError(
            "provider must expose a ProviderDescriptor"
        )
    fetch = getattr(provider, "fetch", None)
    if not callable(fetch):
        raise InvalidDailySnapshotProviderError(
            "provider must implement fetch(request)"
        )
    provider_request = build_daily_provider_request(request, descriptor, calendar)
    response = fetch(provider_request)
    if type(response) is not DailyProviderResponse:
        raise InvalidDailySnapshotResponseError(
            "provider must return DailyProviderResponse"
        )

    from trading_bot.market_data.daily_snapshot_acceptance import (
        accept_daily_provider_response,
    )

    return accept_daily_provider_response(provider_request, response, calendar)
