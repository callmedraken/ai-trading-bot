"""Deterministic constructors shared by daily snapshot tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailyBarCandidate,
    DailyProviderResponse,
    DailySnapshotCaptureRequest,
    ProviderDescriptor,
    SourcePayloadEvidence,
    accept_daily_provider_response,
    build_daily_provider_request,
)

SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
REQUESTED_AT = datetime(2025, 1, 7, 18, 0, tzinfo=UTC)
CAPTURED_AT = datetime(2025, 1, 7, 18, 0, 1, tzinfo=UTC)
TARGET_SESSION = TradingSession(date(2025, 1, 6))
PROVIDER = ProviderDescriptor("test-provider", 1, "daily-bars", "test-feed")
REQUEST_ID = UUID("98dbdaca-e14b-5f10-8ca9-3650e18aa1d8")
SOURCE_PAYLOAD = SourcePayloadEvidence(
    sha256=sha256(b"deterministic fake provider response").hexdigest(),
    byte_length=len(b"deterministic fake provider response"),
    media_type="application/json",
)


def calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def capture_request(
    *,
    request_id: UUID = REQUEST_ID,
    requested_at: datetime = REQUESTED_AT,
    symbols: tuple[Symbol, ...] = (SPY, QQQ),
) -> DailySnapshotCaptureRequest:
    return DailySnapshotCaptureRequest(
        request_id=request_id,
        symbols=symbols,
        requested_at=requested_at,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
    )


def candidate(
    symbol: Symbol,
    ordinal: int,
    *,
    session: TradingSession = TARGET_SESSION,
    timestamp: datetime | None = None,
    open_price: Decimal = Decimal("100.00"),
    high: Decimal = Decimal("103.500"),
    low: Decimal = Decimal("99.2500"),
    close: Decimal = Decimal("102.750"),
    volume: int = 1_000,
) -> DailyBarCandidate:
    return DailyBarCandidate(
        response_ordinal=ordinal,
        symbol=symbol,
        session=session,
        timestamp=timestamp or datetime(2025, 1, 6, 5, 0, tzinfo=UTC),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def accepted_result(
    *,
    request: DailySnapshotCaptureRequest | None = None,
    candidates: tuple[DailyBarCandidate, ...] | None = None,
    captured_at: datetime = CAPTURED_AT,
    provider_as_of: datetime | None = None,
    provider_request_id: str | None = "remote-request-17",
    source_payload: SourcePayloadEvidence = SOURCE_PAYLOAD,
):
    request = request or capture_request()
    bound_calendar = calendar()
    provider_request = build_daily_provider_request(request, PROVIDER, bound_calendar)
    response = DailyProviderResponse(
        request=provider_request,
        candidates=candidates
        or (
            candidate(
                QQQ,
                0,
                open_price=Decimal("200.00"),
                high=Decimal("205.00"),
                low=Decimal("198.00"),
                close=Decimal("203.00"),
                volume=2_000,
            ),
            candidate(SPY, 1),
        ),
        captured_at=captured_at,
        provider_as_of=provider_as_of,
        provider_request_id=provider_request_id,
        source_payload=source_payload,
        pagination_complete=True,
    )
    return accept_daily_provider_response(provider_request, response, bound_calendar)


def accepted_snapshot():
    result = accepted_result()
    assert result.snapshot is not None
    return result.snapshot
