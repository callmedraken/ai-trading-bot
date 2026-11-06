"""Fake-only tests for reusable current runtime Alpaca signal inputs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

import pytest

from trading_bot.live_prototype import alpaca_runtime_signal_provider as subject
from trading_bot.live_prototype import alpaca_signal_inputs as accepted
from trading_bot.market_data.alpaca_http import AlpacaHttpResponse
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)

NEW_YORK = ZoneInfo("America/New_York")


def _timestamp(session: date) -> str:
    return (
        datetime.combine(session, time.min, tzinfo=NEW_YORK)
        .astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _response(sessions: tuple[date, ...]) -> AlpacaHttpResponse:
    bars = [
        {
            "o": 100 + index,
            "h": 102 + index,
            "l": 99 + index,
            "c": 101 + index,
            "v": 1000 + index,
            "t": _timestamp(session),
        }
        for index, session in enumerate(sessions)
    ]
    body = json.dumps(
        {"bars": {"SPY": bars}, "next_page_token": None},
        separators=(",", ":"),
    ).encode("utf-8")
    return AlpacaHttpResponse(
        status=200,
        headers=(("Content-Type", "application/json"), ("X-Request-ID", "fake-id")),
        body=body,
        body_sha256=hashlib.sha256(body).hexdigest(),
        body_byte_length=len(body),
        request_id="fake-id",
        media_type="application/json",
    )


class _Scope:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def __enter__(self) -> _Scope:
        self.events.append("enter")
        return self

    def __exit__(self, *args: object) -> None:
        self.events.append("close")

    def use(self, consumer):  # type: ignore[no-untyped-def]
        self.events.append("use")
        return consumer("fake-key", "fake-secret")


class _Transport:
    def __init__(
        self,
        response: AlpacaHttpResponse | Exception | list[AlpacaHttpResponse | Exception],
    ) -> None:
        self.responses = response if isinstance(response, list) else [response]
        self.calls: list[object] = []

    def execute(self, request, *, api_key_id: str, api_secret_key: str):  # type: ignore[no-untyped-def]
        self.calls.append(request)
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def _provider(
    response: AlpacaHttpResponse | Exception,
    *,
    events: list[str] | None = None,
) -> tuple[subject.AlpacaRuntimeSignalProvider, _Transport, list[str]]:
    observed = [] if events is None else events
    transport = _Transport(response)
    provider = subject.AlpacaRuntimeSignalProvider(
        credential_reader=lambda: (observed.append("credentials"), _Scope(observed))[1],
        transport_factory=lambda: (observed.append("transport"), transport)[1],
    )
    return provider, transport, observed


@pytest.mark.parametrize(
    ("observation", "expected_latest"),
    (
        (datetime(2026, 11, 26, 18, tzinfo=UTC), date(2026, 11, 25)),
        (datetime(2026, 11, 2, 20, 59, 59, tzinfo=UTC), date(2026, 10, 30)),
        (datetime(2026, 11, 2, 21, tzinfo=UTC), date(2026, 11, 2)),
        (datetime(2026, 11, 27, 17, 59, 59, tzinfo=UTC), date(2026, 11, 25)),
        (datetime(2026, 11, 27, 18, tzinfo=UTC), date(2026, 11, 27)),
    ),
)
def test_calendar_cutoffs_cover_holiday_dst_and_early_close(
    observation: datetime, expected_latest: date
) -> None:
    selected = accepted.select_latest_completed_sessions(observation)
    provider, transport, _ = _provider(_response(selected))

    result = provider.snapshot(observation)

    assert result.status == "READY"
    assert result.selected_sessions[-1] == expected_latest
    assert result.display_inputs is not None
    schedule = NYSEPublishedRegularSessionAuthority().schedule_for(expected_latest)
    assert schedule is not None
    assert result.display_inputs.cutoff == schedule.closes_at.astimezone(UTC)
    assert result.display_inputs.cutoff <= observation
    assert result.inputs_for_trading is result.display_inputs
    assert len(result.display_inputs.closes) == 60
    assert len(transport.calls) == 1


def test_published_close_boundary_refreshes_once_with_exact_request() -> None:
    before = datetime(2026, 11, 3, 20, 59, 59, tzinfo=UTC)
    at_close = datetime(2026, 11, 3, 21, tzinfo=UTC)
    first_sessions = accepted.select_latest_completed_sessions(before)
    next_sessions = accepted.select_latest_completed_sessions(at_close)
    transport = _Transport([_response(first_sessions), _response(next_sessions)])
    events: list[str] = []
    provider = subject.AlpacaRuntimeSignalProvider(
        credential_reader=lambda: (events.append("credentials"), _Scope(events))[1],
        transport_factory=lambda: (events.append("transport"), transport)[1],
    )

    initial = provider.snapshot(before)
    unchanged = provider.snapshot(datetime(2026, 11, 3, 20, 59, 59, 500000, tzinfo=UTC))
    at_published_close = provider.snapshot(at_close)

    assert initial.status == "READY"
    assert initial.refreshed is True
    assert unchanged.status == "READY"
    assert unchanged.refreshed is False
    assert unchanged.credential_read_count == unchanged.provider_call_count == 0
    assert at_published_close.status == "READY"
    assert at_published_close.selected_sessions[-1] == date(2026, 11, 3)
    assert at_published_close.display_inputs is not None
    assert at_published_close.display_inputs.cutoff == at_close
    assert len(transport.calls) == 2
    assert events == [
        "credentials",
        "enter",
        "use",
        "transport",
        "close",
        "credentials",
        "enter",
        "use",
        "transport",
        "close",
    ]
    request = transport.calls[1]
    assert request.method == "GET"
    assert request.host == "data.alpaca.markets"
    assert parse_qsl(urlsplit(request.target).query, keep_blank_values=True) == [
        ("symbols", "SPY"),
        ("timeframe", "1Day"),
        ("start", "2026-08-11T04:00:00.000000Z"),
        ("end", "2026-11-03T21:00:00.000000Z"),
        ("limit", "60"),
        ("adjustment", "all"),
        ("asof", "-"),
        ("feed", "sip"),
        ("currency", "USD"),
        ("sort", "asc"),
    ]

    assert next_sessions[-1] == date(2026, 11, 3)
    assert next_sessions != first_sessions


def test_construction_is_inert_and_no_provider_fallback_occurs() -> None:
    events: list[str] = []
    provider = subject.AlpacaRuntimeSignalProvider(
        credential_reader=lambda: events.append("credentials"),
        transport_factory=lambda: events.append("transport"),
    )
    assert events == []

    # The only transport fails. The provider records that attempt and does not
    # construct a second transport or switch to a different data source.
    provider, fake_transport, observed = _provider(
        RuntimeError("SECRET_PROVIDER_TEXT"),
    )
    selected = accepted.select_latest_completed_sessions(
        datetime(2026, 11, 3, 21, tzinfo=UTC)
    )
    failed = provider.snapshot(datetime(2026, 11, 3, 21, tzinfo=UTC))
    repeated = provider.snapshot(datetime(2026, 11, 3, 21, 1, tzinfo=UTC))

    assert failed.status == "BLOCKED"
    assert failed.reason is subject.RuntimeSignalReason.PROVIDER_FAILED
    assert failed.credential_read_count == failed.provider_call_count == 1
    assert failed.inputs_for_trading is None
    assert repeated.reason is subject.RuntimeSignalReason.REFRESH_ALREADY_ATTEMPTED
    assert repeated.credential_read_count == repeated.provider_call_count == 0
    assert len(fake_transport.calls) == 1
    assert observed.count("transport") == 1
    assert "SECRET_PROVIDER_TEXT" not in repr(failed)
    assert len(selected) == 60


def test_new_session_failure_keeps_bounded_stale_display_and_blocks_trading() -> None:
    initial_observation = datetime(2026, 11, 3, 20, 59, 59, tzinfo=UTC)
    first_sessions = accepted.select_latest_completed_sessions(initial_observation)
    transport = _Transport(_response(first_sessions))
    events: list[str] = []

    def next_transport() -> _Transport:
        events.append("transport")
        if events.count("transport") == 1:
            return transport
        return _Transport(RuntimeError("SECRET_PROVIDER_TEXT"))

    provider = subject.AlpacaRuntimeSignalProvider(
        credential_reader=lambda: (events.append("credentials"), _Scope(events))[1],
        transport_factory=next_transport,
    )
    fresh = provider.snapshot(initial_observation)
    newly_completed = provider.snapshot(datetime(2026, 11, 3, 21, tzinfo=UTC))
    same_window = provider.snapshot(datetime(2026, 11, 3, 21, 1, tzinfo=UTC))

    assert fresh.status == "READY"
    assert newly_completed.status == "BLOCKED"
    assert newly_completed.reason is subject.RuntimeSignalReason.PROVIDER_FAILED
    assert newly_completed.stale is True
    assert newly_completed.display_inputs is fresh.display_inputs
    assert len(newly_completed.display_inputs.closes) == 60
    assert newly_completed.inputs_for_trading is None
    assert same_window.reason is subject.RuntimeSignalReason.REFRESH_ALREADY_ATTEMPTED
    assert same_window.stale is True
    assert events.count("transport") == 2


def test_runtime_input_basis_is_required_for_live_admission() -> None:
    observation = datetime(2026, 11, 3, 21, tzinfo=UTC)
    sessions = accepted.select_latest_completed_sessions(observation)
    provider, _, _ = _provider(_response(sessions))
    result = provider.snapshot(observation)
    assert result.display_inputs is not None
    assert result.display_inputs.price_basis == "ALPACA_ALL_ADJUSTED_PRICE_V1"
    assert result.inputs_for_trading is result.display_inputs

    wrong_basis = type(result.display_inputs)(
        symbol=result.display_inputs.symbol,
        selected_sessions=result.display_inputs.selected_sessions,
        sessions=result.display_inputs.sessions,
        closes=result.display_inputs.closes,
        price_basis="ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1",
        source_digest=result.display_inputs.source_digest,
        as_of=result.display_inputs.as_of,
        cutoff=result.display_inputs.cutoff,
    )
    blocked = subject.RuntimeSignalSnapshot(
        status="READY",
        reason=subject.RuntimeSignalReason.READY,
        observation_as_of=observation,
        selected_sessions=sessions,
        display_inputs=wrong_basis,
        stale=False,
        refreshed=False,
        credential_read_count=0,
        provider_call_count=0,
    )
    assert blocked.inputs_for_trading is None


def test_malformed_or_wrong_session_response_blocks_without_fallback() -> None:
    observation = datetime(2026, 11, 3, 21, tzinfo=UTC)
    sessions = accepted.select_latest_completed_sessions(observation)
    wrong_sessions = tuple(session - timedelta(days=1) for session in sessions)
    provider, transport, _ = _provider(_response(wrong_sessions))

    result = provider.snapshot(observation)

    assert result.status == "BLOCKED"
    assert result.reason is subject.RuntimeSignalReason.RESPONSE_SESSION_MISMATCH
    assert result.provider_call_count == 1
    assert result.display_inputs is None
    assert len(transport.calls) == 1


def test_provider_never_retries_same_window_after_failure() -> None:
    observation = datetime(2026, 11, 3, 21, tzinfo=UTC)
    provider, transport, _ = _provider(RuntimeError("secret"))
    first = provider.snapshot(observation)
    second = provider.snapshot(datetime(2026, 11, 3, 22, tzinfo=UTC))
    assert first.status == second.status == "BLOCKED"
    assert len(transport.calls) == 1
