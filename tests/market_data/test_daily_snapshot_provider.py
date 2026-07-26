from datetime import datetime

import pytest
from tests.market_data.daily_snapshot_test_support import (
    CAPTURED_AT,
    PROVIDER,
    QQQ,
    SOURCE_PAYLOAD,
    SPY,
    candidate,
    capture_request,
)

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    CalendarDescriptor,
    DailyProviderResponse,
    DailySnapshotAcceptanceStatus,
    InvalidDailySnapshotCalendarError,
    capture_daily_snapshot,
    derive_completed_session,
)


@pytest.mark.parametrize(
    ("requested_at", "expected"),
    [
        ("2025-01-07T18:00:00+00:00", "2025-01-06"),
        ("2025-01-06T18:00:00+00:00", "2025-01-03"),
        ("2025-01-05T18:00:00+00:00", "2025-01-03"),
        ("2025-01-01T18:00:00+00:00", "2024-12-31"),
    ],
)
def test_target_is_strictly_prior_exchange_session(
    requested_at: str, expected: str
) -> None:
    request = capture_request(requested_at=datetime.fromisoformat(requested_at))
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())

    assert (
        derive_completed_session(request, calendar).session_date.isoformat() == expected
    )


def test_calendar_descriptor_must_match_exactly() -> None:
    request = capture_request()
    wrong = BoundMarketCalendar(
        CalendarDescriptor("XNYS", "other-v1", "America/New_York"),
        NYSEMarketCalendar(),
    )

    with pytest.raises(InvalidDailySnapshotCalendarError):
        derive_completed_session(request, wrong)


def test_capture_calls_provider_once_with_frozen_target() -> None:
    request = capture_request()
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())

    class Provider:
        descriptor = PROVIDER

        def __init__(self) -> None:
            self.requests = []

        def fetch(self, provider_request):
            self.requests.append(provider_request)
            return DailyProviderResponse(
                provider_request,
                (candidate(QQQ, 0), candidate(SPY, 1)),
                CAPTURED_AT,
                None,
                "request-1",
                SOURCE_PAYLOAD,
                True,
            )

    provider = Provider()
    result = capture_daily_snapshot(request, provider, calendar)

    assert result.status is DailySnapshotAcceptanceStatus.ACCEPTED
    assert len(provider.requests) == 1
    assert provider.requests[0].target_session.session_date.isoformat() == "2025-01-06"
