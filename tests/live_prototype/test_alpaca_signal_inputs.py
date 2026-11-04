"""Focused D33 current-data and read-only operator contract tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

import pytest

from trading_bot.live_prototype import alpaca_signal_inputs as subject
from trading_bot.live_prototype.alpaca_signal_operator import (
    SourceAdmission,
    run_d33_read_only_observation,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.market_data.alpaca_http import AlpacaHttpResponse

OBSERVATION = datetime(2026, 11, 4, 15, tzinfo=UTC)
NEW_YORK = subject._NEW_YORK


def _selected(observation: datetime = OBSERVATION) -> tuple[date, ...]:
    return subject.select_latest_completed_sessions(observation)


def _provider_timestamp(session: date, *, hour: int = 0) -> str:
    return (
        datetime.combine(session, time(hour), tzinfo=NEW_YORK)
        .astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _bar(session: date, close: int, **updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "o": close,
        "h": close + 1,
        "l": close - 1,
        "c": close,
        "v": 1000,
        "t": _provider_timestamp(session),
    }
    value.update(updates)
    return value


def _body(
    sessions: tuple[date, ...],
    *,
    bars: list[dict[str, object]] | None = None,
    currency: object = "USD",
    next_page_token: object = None,
    symbol: str = "SPY",
) -> bytes:
    payload: dict[str, object] = {
        "bars": {
            symbol: bars
            if bars is not None
            else [_bar(session, 100 + index) for index, session in enumerate(sessions)]
        },
        "next_page_token": next_page_token,
    }
    if currency is not None:
        payload["currency"] = currency
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _response(body: bytes) -> AlpacaHttpResponse:
    return AlpacaHttpResponse(
        status=200,
        headers=(("Content-Type", "application/json"), ("X-Request-ID", "d33-test")),
        body=body,
        body_sha256=hashlib.sha256(body).hexdigest(),
        body_byte_length=len(body),
        request_id="d33-test",
        media_type="application/json",
    )


class _Scope:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def __enter__(self) -> _Scope:
        self.calls.append("enter")
        return self

    def __exit__(self, *args: object) -> None:
        self.calls.append("close")

    def use(self, consumer):  # type: ignore[no-untyped-def]
        self.calls.append("use")
        return consumer("key", "secret")


class _Transport:
    def __init__(self, response: AlpacaHttpResponse | Exception) -> None:
        self.response = response
        self.calls: list[object] = []

    def execute(self, request, *, api_key_id: str, api_secret_key: str):  # type: ignore[no-untyped-def]
        self.calls.append((request, api_key_id, api_secret_key))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _service(
    response: AlpacaHttpResponse | Exception,
    *,
    credential_calls: list[str] | None = None,
) -> tuple[subject.AlpacaSignalInputService, _Transport]:
    calls = [] if credential_calls is None else credential_calls
    transport = _Transport(response)
    return (
        subject.AlpacaSignalInputService(
            transport_factory=lambda: transport,
            credential_reader=lambda: _Scope(calls),
        ),
        transport,
    )


def _completed_inputs(closes: tuple[Decimal, ...]) -> CompletedSignalInputs:
    sessions = tuple(date(2026, 1, 1) + timedelta(days=index) for index in range(60))
    return CompletedSignalInputs(
        "SPY",
        sessions,
        sessions,
        closes,
        subject.LIVE_SIGNAL_PRICE_BASIS,
        "a" * 64,
        datetime(2026, 4, 1, tzinfo=UTC),
        datetime(2026, 4, 1, tzinfo=UTC),
    )


def test_selection_uses_published_sessions_and_excludes_open_weekend_holiday() -> None:
    before_close = subject.select_latest_completed_sessions(
        datetime(2026, 11, 3, 20, 59, 59, tzinfo=UTC)
    )
    at_close = subject.select_latest_completed_sessions(
        datetime(2026, 11, 3, 21, tzinfo=UTC)
    )
    weekend = subject.select_latest_completed_sessions(
        datetime(2026, 11, 7, 17, tzinfo=UTC)
    )
    holiday = subject.select_latest_completed_sessions(
        datetime(2026, 11, 26, 18, tzinfo=UTC)
    )
    assert before_close[-1] == date(2026, 11, 2)
    assert at_close[-1] == date(2026, 11, 3)
    assert weekend[-1] == date(2026, 11, 6)
    assert holiday[-1] == date(2026, 11, 25)
    assert len(set(weekend)) == 60
    assert all(left < right for left, right in zip(holiday, holiday[1:], strict=False))


def test_selection_handles_premarket_regular_hours_dst_and_early_close() -> None:
    premarket = subject.select_latest_completed_sessions(
        datetime(2026, 11, 4, 13, tzinfo=UTC)
    )
    regular_hours = subject.select_latest_completed_sessions(
        datetime(2026, 11, 4, 15, tzinfo=UTC)
    )
    early_before = subject.select_latest_completed_sessions(
        datetime(2026, 11, 27, 17, 59, 59, tzinfo=UTC)
    )
    early_close = subject.select_latest_completed_sessions(
        datetime(2026, 11, 27, 18, tzinfo=UTC)
    )
    assert premarket[-1] == regular_hours[-1] == date(2026, 11, 3)
    assert early_before[-1] == date(2026, 11, 25)
    assert early_close[-1] == date(2026, 11, 27)
    assert _provider_timestamp(date(2026, 11, 2)) == "2026-11-02T05:00:00Z"
    assert _provider_timestamp(date(2026, 11, 3)) == "2026-11-03T05:00:00Z"


def test_request_is_exact_all_adjusted_sip_usd_one_day_ascending_and_bounded() -> None:
    request = subject.build_alpaca_signal_request(_selected())
    assert request.method == "GET"
    assert request.host == "data.alpaca.markets"
    assert dict(request.public_headers) == {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "User-Agent": subject.ALPACA_SIGNAL_USER_AGENT,
    }
    assert parse_qsl(urlsplit(request.target).query, keep_blank_values=True) == [
        ("symbols", "SPY"),
        ("timeframe", "1Day"),
        ("start", "2026-08-11T04:00:00.000000Z"),
        ("end", "2026-11-04T04:59:59.999999Z"),
        ("limit", "60"),
        ("adjustment", "all"),
        ("asof", "-"),
        ("feed", "sip"),
        ("currency", "USD"),
        ("sort", "asc"),
    ]


def test_service_constructs_no_credentials_or_provider_and_binds_digest() -> None:
    events: list[str] = []
    transport = _Transport(_response(_body(_selected())))
    service = subject.AlpacaSignalInputService(
        credential_reader=lambda: (_ for _ in ()).throw(AssertionError("read")),
        transport_factory=lambda: (_ for _ in ()).throw(AssertionError("construct")),
    )
    assert service is not None
    service = subject.AlpacaSignalInputService(
        credential_reader=lambda: _Scope(events),
        transport_factory=lambda: transport,
    )
    result = service.observe(OBSERVATION)
    assert result.status == "READY"
    assert result.inputs is not None
    body = _body(_selected())
    assert result.inputs.source_digest == hashlib.sha256(body).hexdigest()
    assert result.inputs.digest
    assert result.provider_call_count == 1
    assert result.credential_read_count == 1
    assert transport.calls[0][1:] == ("key", "secret")


@pytest.mark.parametrize(
    "mutation",
    (
        lambda body, sessions: b"{",
        lambda body, sessions: _body(sessions, symbol="QQQ"),
        lambda body, sessions: _body(sessions, currency="EUR"),
        lambda body, sessions: _body(sessions, next_page_token="page-2"),
        lambda body, sessions: _body(
            sessions, bars=[_bar(s, 100) for s in sessions[:-1]]
        ),
        lambda body, sessions: _body(
            sessions,
            bars=[
                *_body_bars(sessions),
                _bar(sessions[-1] + timedelta(days=1), 200),
            ],
        ),
        lambda body, sessions: _body(
            sessions,
            bars=[*_body_bars(sessions[:-1]), _body_bars(sessions)[-2]],
        ),
        lambda body, sessions: _body(
            sessions, bars=list(reversed(_body_bars(sessions)))
        ),
        lambda body, sessions: _body(
            sessions,
            bars=[_bar(s, 100, t=_provider_timestamp(s, hour=12)) for s in sessions],
        ),
        lambda body, sessions: _body(sessions, bars=[_bar(s, 0) for s in sessions]),
        lambda body, sessions: _body(
            sessions, bars=[_bar(s, 100, c=float("nan")) for s in sessions]
        ),
        lambda body, sessions: _body(
            sessions, bars=[_bar(s, 100, v=-1) for s in sessions]
        ),
        lambda body, sessions: _body(
            sessions, bars=[_bar(s, 100, unknown=1) for s in sessions]
        ),
    ),
)
def test_malformed_or_mismatched_response_is_fixed_blocked(mutation) -> None:  # type: ignore[no-untyped-def]
    sessions = _selected()
    body = mutation(b"", sessions)
    service, transport = _service(_response(body))
    result = service.observe(OBSERVATION)
    assert result.status == "BLOCKED"
    assert result.inputs is None
    assert result.provider_call_count == 1
    assert result.credential_read_count == 1
    assert transport.calls


def _body_bars(sessions: tuple[date, ...]) -> list[dict[str, object]]:
    return [_bar(session, 100) for session in sessions]


def test_failed_provider_is_sanitized_and_consumed_without_fallback_or_retry() -> None:
    service, transport = _service(RuntimeError("SECRET_PROVIDER_TEXT"))
    first = service.observe(OBSERVATION)
    second = service.observe(OBSERVATION)
    assert first.status == "BLOCKED"
    assert first.reason == subject.SignalInputFailureReason.PROVIDER_REQUEST_FAILED
    assert first.provider_call_count == 1
    assert second.reason == subject.SignalInputFailureReason.OBSERVATION_CONSUMED
    assert second.provider_call_count == 0
    assert len(transport.calls) == 1
    assert "SECRET_PROVIDER_TEXT" not in repr(first)


@pytest.mark.parametrize(
    ("closes", "invested", "expected"),
    (
        (tuple(Decimal(index) for index in range(1, 61)), False, "BUY"),
        (tuple(Decimal(index) for index in range(1, 61)), True, "HOLD"),
        (tuple(Decimal(100) for _ in range(60)), False, "HOLD"),
        (tuple(Decimal(100) for _ in range(60)), True, "HOLD"),
        (tuple(Decimal(61 - index) for index in range(60)), False, "HOLD"),
        (tuple(Decimal(61 - index) for index in range(60)), True, "SELL"),
    ),
)
def test_35_50_decision_is_fixed_context_and_investment_aware(
    closes: tuple[Decimal, ...], invested: bool, expected: str
) -> None:
    inputs = _completed_inputs(closes)
    with localcontext() as ambient:
        ambient.prec = 2
        assert subject.decide_35_50(inputs, invested=invested) == expected
    assert subject.moving_averages_35_50(inputs)[0].is_finite()


def test_research_binding_freezes_d30_d31_and_never_becomes_live() -> None:
    provenance = subject.RESEARCH_BINDING_PROVENANCE
    binding = subject.RESEARCH_CONTROL_BINDING
    assert provenance.dataset_id == "d5aa8ed7-b5cd-53a3-8671-5370f976e8e3"
    assert provenance.campaign_id == "9b2a000e-3adc-50f4-ab47-2aa90665e3c9"
    assert provenance.bundle_id == "f01a39a7-0a65-55bb-9d38-608b1ce0bd21"
    assert provenance.selected_result == "NONE_QUALIFIES"
    assert provenance.control_candidate_id == "21158358-75be-5597-b940-5bccdda1429c"
    assert binding.candidate == "BASE_MA35_50_V1"
    assert binding.research_digest == subject.RESEARCH_BUNDLE_SHA256
    assert binding.dataset_digest == subject.RESEARCH_DATASET_SHA256
    assert binding.live_eligible is False


def _fresh_operator_evidence() -> Path:
    parent = Path(r"F:\AI\temp")
    if not parent.is_dir():
        pytest.skip("F:\\AI\\temp is unavailable for operator evidence")
    candidate = parent / ("d33-focused-" + uuid4().hex)
    try:
        candidate.mkdir()
    except PermissionError:
        pytest.skip("F:\\AI\\temp is not writable for operator evidence")
    candidate.rmdir()
    return candidate


def _source() -> SourceAdmission:
    return SourceAdmission(
        "feature/robinhood-live-prototype-current",
        "a" * 40,
        "b" * 40,
        "c" * 40,
        "a" * 40,
    )


def test_operator_admission_precedes_provider_and_sanitizes_evidence() -> None:
    events: list[str] = []
    evidence = _fresh_operator_evidence()
    transport = _Transport(_response(_body(_selected())))
    try:
        result = run_d33_read_only_observation(
            observation_as_of=OBSERVATION,
            evidence_dir=evidence,
            source_admitter=lambda root: (events.append("source"), _source())[1],
            credential_reader=lambda: (events.append("credentials"), _Scope(events))[1],
            transport_factory=lambda: (events.append("transport"), transport)[1],
        )
        assert result.status == "READY"
        assert events[:3] == ["source", "credentials", "transport"]
        assert result.evidence_path is not None
        evidence_body = result.evidence_path.read_text(encoding="utf-8")
        assert "key" not in evidence_body
        assert "secret" not in evidence_body
        assert "SECRET" not in evidence_body
        assert "response_body_sha256" in evidence_body
        assert "campaign_runs" in evidence_body
        assert "final_holdout_accesses" in evidence_body
        assert len(transport.calls) == 1
    finally:
        if evidence.exists():
            for child in evidence.iterdir():
                child.unlink()
            evidence.rmdir()


def test_operator_source_failure_prevents_credential_and_transport_construction() -> (
    None
):
    events: list[str] = []
    evidence = _fresh_operator_evidence()
    try:
        result = run_d33_read_only_observation(
            observation_as_of=OBSERVATION,
            evidence_dir=evidence,
            source_admitter=lambda root: (_ for _ in ()).throw(
                RuntimeError("source detail")
            ),
            credential_reader=lambda: (events.append("credentials"), _Scope(events))[1],
            transport_factory=lambda: (
                events.append("transport"),
                _Transport(RuntimeError("provider")),
            )[1],
        )
        assert result.status == "BLOCKED"
        assert result.reason == "D33_SOURCE_ADMISSION_BLOCKED"
        assert events == []
        assert result.evidence_path is not None
    finally:
        if evidence.exists():
            for child in evidence.iterdir():
                child.unlink()
            evidence.rmdir()
