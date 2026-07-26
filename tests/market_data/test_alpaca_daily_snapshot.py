from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    AlpacaCredentialError,
    AlpacaHttpResponse,
    AlpacaResponseError,
    BoundMarketCalendar,
    DailySnapshotAcceptanceStatus,
    DailySnapshotCaptureRequest,
    DailySnapshotRejectionClassification,
    alpaca_target_interval_utc,
    build_alpaca_historical_bars_request,
    build_daily_provider_request,
    capture_daily_snapshot,
    create_alpaca_daily_snapshot_provider,
    parse_alpaca_historical_bars_response,
)

REQUEST_ID = UUID("98dbdaca-e14b-5f10-8ca9-3650e18aa1d8")
KEY = "test-key-id"
SECRET = "test-secret-value"


def _calendar() -> BoundMarketCalendar:
    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())


def _provider_request(
    *,
    requested_at: datetime = datetime(2025, 1, 7, 18, tzinfo=UTC),
):
    request = DailySnapshotCaptureRequest(
        request_id=REQUEST_ID,
        symbols=(Symbol("SPY"), Symbol("QQQ")),
        requested_at=requested_at,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
    )
    return build_daily_provider_request(
        request,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        _calendar(),
    )


def _payload(*, token=None, currency: str | None = None) -> bytes:
    value = {
        "bars": {
            "QQQ": [
                {
                    "t": "2025-01-06T05:00:00Z",
                    "o": 200,
                    "h": 205.25,
                    "l": 198.5,
                    "c": 203.125,
                    "v": 2000,
                    "n": 100,
                    "vw": 202.75,
                    "x": "P",
                }
            ],
            "SPY": [
                {
                    "t": "2025-01-06T05:00:00Z",
                    "o": 100.00,
                    "h": 103.5,
                    "l": 99.25,
                    "c": 102.75,
                    "v": 1000,
                }
            ],
        },
        "next_page_token": token,
    }
    if currency is not None:
        value["currency"] = currency
    return json.dumps(value, separators=(",", ":")).encode()


def _http_response(payload: bytes) -> AlpacaHttpResponse:
    return AlpacaHttpResponse(
        status=200,
        headers=(
            ("Content-Type", "application/json"),
            ("X-Request-ID", "request-abc-123"),
        ),
        body=payload,
        body_sha256=hashlib.sha256(payload).hexdigest(),
        body_byte_length=len(payload),
        request_id="request-abc-123",
        media_type="application/json",
    )


def test_exact_est_and_edt_request_targets() -> None:
    est = build_alpaca_historical_bars_request(_provider_request())
    edt = build_alpaca_historical_bars_request(
        _provider_request(requested_at=datetime(2025, 7, 8, 18, tzinfo=UTC))
    )

    assert est.target == (
        "/v2/stocks/bars?symbols=SPY%2CQQQ&timeframe=1Day"
        "&start=2025-01-06T05%3A00%3A00Z"
        "&end=2025-01-07T04%3A59%3A59.999999Z"
        "&limit=2&adjustment=raw&asof=-&feed=sip&currency=USD&sort=asc"
    )
    assert edt.target == (
        "/v2/stocks/bars?symbols=SPY%2CQQQ&timeframe=1Day"
        "&start=2025-07-07T04%3A00%3A00Z"
        "&end=2025-07-08T03%3A59%3A59.999999Z"
        "&limit=2&adjustment=raw&asof=-&feed=sip&currency=USD&sort=asc"
    )
    assert "page_token" not in est.target
    assert KEY not in est.target
    assert SECRET not in est.target
    assert all(
        not name.casefold().startswith("apca-") for name, _ in est.public_headers
    )


def test_target_bounds_convert_each_new_york_midnight_independently() -> None:
    start, end = alpaca_target_interval_utc(date(2025, 3, 9))

    assert start == datetime(2025, 3, 9, 5, tzinfo=UTC)
    assert end == datetime(2025, 3, 10, 3, 59, 59, 999999, tzinfo=UTC)
    assert end - start == timedelta(hours=23) - timedelta(microseconds=1)


def test_provider_maps_one_response_and_reads_clock_after_transport() -> None:
    events: list[str] = []
    calls = []
    payload = _payload(currency="USD")

    class Transport:
        def execute(self, request, *, api_key_id, api_secret_key):
            events.append("transport")
            calls.append((request, api_key_id, api_secret_key))
            return _http_response(payload)

    def clock() -> datetime:
        events.append("clock")
        return datetime(2025, 1, 7, 18, 0, 1, tzinfo=UTC)

    provider = create_alpaca_daily_snapshot_provider(
        transport=Transport(),
        clock=clock,
        environment={
            "APCA_API_KEY_ID": KEY,
            "APCA_API_SECRET_KEY": SECRET,
        },
    )
    response = provider.fetch(_provider_request())

    assert KEY not in repr(provider)
    assert SECRET not in repr(provider)
    assert events == ["transport", "clock"]
    assert len(calls) == 1
    assert calls[0][1:] == (KEY, SECRET)
    assert tuple(item.response_ordinal for item in response.candidates) == (0, 1)
    assert tuple(item.symbol for item in response.candidates) == (
        Symbol("QQQ"),
        Symbol("SPY"),
    )
    assert response.candidates[0].open == Decimal("200")
    assert response.candidates[0].close == Decimal("203.125")
    assert response.provider_request_id == "request-abc-123"
    assert response.provider_as_of is None
    assert response.source_payload.sha256 == hashlib.sha256(payload).hexdigest()
    assert response.source_payload.byte_length == len(payload)


def test_provider_delegates_normalization_and_identity_to_milestone_a() -> None:
    payload = _payload()

    class Transport:
        calls = 0

        def execute(self, request, *, api_key_id, api_secret_key):
            self.calls += 1
            return _http_response(payload)

    transport = Transport()
    provider = create_alpaca_daily_snapshot_provider(
        transport=transport,
        clock=lambda: datetime(2025, 1, 7, 18, 0, 1, tzinfo=UTC),
        environment={
            "APCA_API_KEY_ID": KEY,
            "APCA_API_SECRET_KEY": SECRET,
        },
    )
    result = capture_daily_snapshot(
        _provider_request().capture_request,
        provider,
        _calendar(),
    )

    assert transport.calls == 1
    assert result.status is DailySnapshotAcceptanceStatus.ACCEPTED
    assert result.snapshot is not None
    assert tuple(item.bar.symbol for item in result.snapshot.bars) == (
        Symbol("SPY"),
        Symbol("QQQ"),
    )
    assert result.snapshot.audit.provider_response_symbols == (
        Symbol("QQQ"),
        Symbol("SPY"),
    )


def test_nonnull_page_token_is_rejected_without_followup() -> None:
    payload = _payload(token="next-page")

    class Transport:
        calls = 0

        def execute(self, request, *, api_key_id, api_secret_key):
            self.calls += 1
            return _http_response(payload)

    transport = Transport()
    provider = create_alpaca_daily_snapshot_provider(
        transport=transport,
        clock=lambda: datetime(2025, 1, 7, 18, 0, 1, tzinfo=UTC),
        environment={
            "APCA_API_KEY_ID": KEY,
            "APCA_API_SECRET_KEY": SECRET,
        },
    )
    result = capture_daily_snapshot(
        _provider_request().capture_request,
        provider,
        _calendar(),
    )

    assert transport.calls == 1
    assert (
        result.classification
        is DailySnapshotRejectionClassification.INCOMPLETE_RESPONSE
    )


@pytest.mark.parametrize(
    "payload",
    [
        b'{"bars":{},"bars":{},"next_page_token":null}',
        b'{"bars":{},"next_page_token":null,"unknown":1}',
        b'{"bars":{},"next_page_token":null,"currency":"EUR"}',
        b'{"bars":{"SPY":[{"t":"2025-01-06T05:00:00Z","o":1,"h":2,'
        b'"l":1,"c":1,"v":true}]},"next_page_token":null}',
        b'{"bars":{"SPY":[{"t":"2025-01-06T05:00:00Z","o":1,"h":2,'
        b'"l":1,"c":1,"v":1,"n":false}]},"next_page_token":null}',
        b'{"bars":{"SPY":[{"t":"2025-01-06T05:00:00Z","o":1,"h":2,'
        b'"l":1,"c":1,"v":1,"vw":"1"}]},"next_page_token":null}',
        b'{"bars":{"SPY":[{"t":"2025-01-06T05:00:00Z","o":NaN,"h":2,'
        b'"l":1,"c":1,"v":1}]},"next_page_token":null}',
        b'{"bars":{"SPY":[{"t":"2025-01-06T05:00:00.123456789Z","o":1,'
        b'"h":2,"l":1,"c":1,"v":1}]},"next_page_token":null}',
    ],
)
def test_response_parser_fails_closed(payload: bytes) -> None:
    with pytest.raises(AlpacaResponseError):
        parse_alpaca_historical_bars_response(payload)


@pytest.mark.parametrize(
    "value",
    [
        "",
        " padded",
        "padded ",
        "two\nlines",
        "carriage\rreturn",
        "nul\0value",
    ],
)
def test_credentials_are_rejected_without_entering_public_models(value: str) -> None:
    with pytest.raises(AlpacaCredentialError) as caught:
        create_alpaca_daily_snapshot_provider(
            transport=object(),
            clock=lambda: datetime.now(UTC),
            environment={
                "APCA_API_KEY_ID": value,
                "APCA_API_SECRET_KEY": SECRET,
            },
        )

    assert SECRET not in str(caught.value)


def test_missing_credentials_report_only_environment_variable_name() -> None:
    with pytest.raises(AlpacaCredentialError) as caught:
        create_alpaca_daily_snapshot_provider(
            transport=object(),
            clock=lambda: datetime.now(UTC),
            environment={},
        )

    assert "APCA_API_KEY_ID" in str(caught.value)
    assert KEY not in str(caught.value)
    assert SECRET not in str(caught.value)
