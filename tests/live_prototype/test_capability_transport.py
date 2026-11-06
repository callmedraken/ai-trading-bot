"""Fake-only tests for the bounded L41 MCP transport."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from trading_bot.live_prototype.capability_transport import (
    CapabilityTransportError,
    RobinhoodCapabilityTransport,
)

_ACCOUNT = "SECRET_ACCOUNT_NUMBER_4831"
_OAUTH = object()


def _accounts() -> dict[str, object]:
    return {
        "data": {
            "accounts": [
                {
                    "account_number": _ACCOUNT,
                    "agentic_allowed": True,
                    "brokerage_account_type": "individual",
                    "state": "active",
                    "deactivated": False,
                    "permanently_deactivated": False,
                }
            ]
        }
    }


def _tradability() -> dict[str, object]:
    return {
        "data": {
            "results": [
                {
                    "symbol": "SPY",
                    "tradeable": True,
                    "state": "active",
                    "fractional_tradability": "tradable",
                    "account_type_tradabilities": [
                        {
                            "account_type": "individual",
                            "account_type_tradability": "tradable",
                        }
                    ],
                }
            ]
        }
    }


class _FakeClient:
    def __init__(self, failure: Exception | None = None) -> None:
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []
        self.failure = failure

    async def list_tools(self, *, cursor: str | None = None) -> object:
        assert cursor is None
        return SimpleNamespace(
            tools=[
                SimpleNamespace(name="get_accounts"),
                SimpleNamespace(name="get_equity_tradability"),
            ],
            next_cursor=None,
        )

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        self.calls.append((name, dict(arguments)))
        if self.failure is not None:
            raise self.failure
        payload = _accounts() if name == "get_accounts" else _tradability()
        return SimpleNamespace(is_error=False, structured_content=payload)


class _SecretTransportError(CapabilityTransportError):
    def __init__(self) -> None:
        super().__init__("L41_TRANSPORT_FAILED")
        self.reason = "L41_SECRET_PROVIDER_TEXT"

    def __str__(self) -> str:
        return "SECRET_PROVIDER_TEXT"

    def __repr__(self) -> str:
        return "_SecretTransportError('SECRET_PROVIDER_TEXT')"


class _BlockingClient(_FakeClient):
    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        self.calls.append((name, dict(arguments)))
        await asyncio.Event().wait()


def _transport(
    client: _FakeClient,
    events: list[str],
    *,
    oauth_failure: Exception | None = None,
) -> RobinhoodCapabilityTransport:
    def oauth_factory() -> object:
        events.append("oauth_scope_entry")
        if oauth_failure is not None:
            raise oauth_failure
        return _OAUTH

    @asynccontextmanager
    async def session_factory(oauth: object) -> AsyncIterator[_FakeClient]:
        assert oauth is _OAUTH
        events.append("session_open")
        try:
            yield client
        finally:
            events.append("session_close")

    return RobinhoodCapabilityTransport(oauth_factory, session_factory=session_factory)


def test_one_session_performs_exactly_the_two_bound_reads() -> None:
    events: list[str] = []
    client = _FakeClient()
    transport = _transport(client, events)

    with transport as boundary:
        assert boundary.get_accounts() == _accounts()
        assert (
            boundary.get_equity_tradability(
                {"account_number": _ACCOUNT, "symbols": ["SPY"]}
            )
            == _tradability()
        )
        assert not any(
            hasattr(boundary, name)
            for name in (
                "review_equity_order",
                "place_equity_order",
                "cancel_equity_order",
            )
        )

    assert events == ["oauth_scope_entry", "session_open", "session_close"]
    assert client.calls == [
        ("get_accounts", {}),
        (
            "get_equity_tradability",
            {"account_number": _ACCOUNT, "symbols": ["SPY"]},
        ),
    ]
    counts = transport.call_counts
    assert counts.oauth_scope_entry_attempts == 1
    assert counts.mcp_session_open_attempts == 1
    assert counts.get_accounts_attempts == 1
    assert counts.get_equity_tradability_attempts == 1
    assert counts.other_tool_attempts == 0
    assert counts.review_equity_order_attempts == 0
    assert counts.place_equity_order_attempts == 0
    assert counts.cancel_equity_order_attempts == 0
    assert counts.native_credential_read_count is None
    assert "NOT_INDIVIDUALLY_COUNTED" in counts.credential_store_accounting


def test_oauth_scope_failure_is_sanitized_and_not_retried() -> None:
    events: list[str] = []
    transport = _transport(
        _FakeClient(),
        events,
        oauth_failure=RuntimeError(f"SECRET_PROVIDER_TEXT {_ACCOUNT}"),
    )

    with pytest.raises(CapabilityTransportError) as error:
        transport.__enter__()

    assert error.value.reason == "L41_OAUTH_INITIALIZATION_FAILED"
    assert "SECRET_PROVIDER_TEXT" not in repr(error.value)
    assert _ACCOUNT not in repr(error.value)
    assert events == ["oauth_scope_entry"]
    assert transport.call_counts.oauth_scope_entry_attempts == 1
    assert transport.call_counts.mcp_session_open_attempts == 0


def test_tool_failure_counts_one_attempt_and_never_retries() -> None:
    events: list[str] = []
    client = _FakeClient(RuntimeError(f"SECRET_PROVIDER_TEXT {_ACCOUNT}"))
    transport = _transport(client, events)

    with transport as boundary:
        with pytest.raises(CapabilityTransportError) as error:
            boundary.get_accounts()

    assert error.value.reason == "L41_MCP_REQUEST_FAILED"
    assert len(client.calls) == 1
    assert client.calls[0][0] == "get_accounts"
    assert transport.call_counts.get_accounts_attempts == 1
    assert transport.call_counts.get_equity_tradability_attempts == 0
    assert "SECRET_PROVIDER_TEXT" not in repr(error.value)
    assert _ACCOUNT not in repr(error.value)


def test_transport_error_subclass_cannot_leak_provider_text() -> None:
    events: list[str] = []
    client = _FakeClient(_SecretTransportError())
    transport = _transport(client, events)

    with transport as boundary:
        with pytest.raises(CapabilityTransportError) as error:
            boundary.get_accounts()

    assert type(error.value) is CapabilityTransportError
    assert error.value.reason == "L41_TRANSPORT_FAILED"
    assert "SECRET_PROVIDER_TEXT" not in str(error.value)
    assert "SECRET_PROVIDER_TEXT" not in repr(error.value)


def test_session_close_failure_is_sanitized_and_reported_separately() -> None:
    events: list[str] = []
    client = _FakeClient()

    @asynccontextmanager
    async def failing_close_session(oauth: object) -> AsyncIterator[_FakeClient]:
        assert oauth is _OAUTH
        events.append("session_open")
        yield client
        events.append("session_close")
        raise RuntimeError(f"SECRET_PROVIDER_TEXT {_ACCOUNT} https://token.invalid/x")

    transport = RobinhoodCapabilityTransport(
        lambda: _OAUTH,
        session_factory=failing_close_session,
    )

    with pytest.raises(CapabilityTransportError) as error:
        with transport as boundary:
            boundary.get_accounts()
            boundary.get_equity_tradability(
                {"account_number": _ACCOUNT, "symbols": ["SPY"]}
            )

    assert error.value.reason == "L41_MCP_SESSION_CLOSE_FAILED"
    assert transport.teardown_status.session_close_status == "FAILED"
    assert transport.teardown_status.loop_stop_status == "SUCCEEDED"
    assert transport.call_counts.get_accounts_attempts == 1
    assert transport.call_counts.get_equity_tradability_attempts == 1
    assert events == ["session_open", "session_close"]
    rendered = str(error.value) + repr(error.value)
    for secret in ("SECRET_PROVIDER_TEXT", _ACCOUNT, "token.invalid"):
        assert secret not in rendered
    with pytest.raises(CapabilityTransportError) as retry:
        transport.__enter__()
    assert retry.value.reason == "L41_TRANSPORT_ALREADY_USED"


def test_loop_stop_failure_is_sanitized_and_not_conflated_with_session_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    transport = _transport(_FakeClient(), events)
    stop = transport._loop_thread.stop

    def stop_then_fail() -> None:
        stop()
        raise RuntimeError("SECRET_PROVIDER_TEXT https://token.invalid/x")

    monkeypatch.setattr(transport._loop_thread, "stop", stop_then_fail)

    with pytest.raises(CapabilityTransportError) as error:
        with transport as boundary:
            boundary.get_accounts()
            boundary.get_equity_tradability(
                {"account_number": _ACCOUNT, "symbols": ["SPY"]}
            )

    assert error.value.reason == "L41_LOOP_STOP_FAILED"
    assert transport.teardown_status.session_close_status == "SUCCEEDED"
    assert transport.teardown_status.loop_stop_status == "FAILED"
    assert transport.call_counts.get_accounts_attempts == 1
    assert transport.call_counts.get_equity_tradability_attempts == 1
    rendered = str(error.value) + repr(error.value)
    assert "SECRET_PROVIDER_TEXT" not in rendered
    assert "token.invalid" not in rendered


def test_timeout_counts_one_attempt_and_blocks_same_read_retry(monkeypatch) -> None:
    monkeypatch.setattr(
        "trading_bot.live_prototype.capability_transport._OPERATION_TIMEOUT_SECONDS",
        0.03,
    )
    events: list[str] = []
    client = _BlockingClient()
    transport = _transport(client, events)

    with transport as boundary:
        with pytest.raises(CapabilityTransportError) as error:
            boundary.get_accounts()
        assert error.value.reason == "L41_MCP_TIMEOUT"
        with pytest.raises(CapabilityTransportError) as retry:
            boundary.get_accounts()
        assert retry.value.reason == "L41_ACCOUNTS_RETRY_BLOCKED"

    assert len(client.calls) == 1
    assert client.calls[0][0] == "get_accounts"
    assert transport.call_counts.get_accounts_attempts == 1


def test_discovery_failure_closes_entered_session_and_does_not_retry() -> None:
    events: list[str] = []
    client = _FakeClient()

    @asynccontextmanager
    async def bad_discovery_session(
        oauth: object,
    ) -> AsyncIterator[_FakeClient]:
        assert oauth is _OAUTH
        events.append("session_open")
        client.list_tools = _bad_list_tools  # type: ignore[method-assign]
        try:
            yield client
        finally:
            events.append("session_close")

    def oauth_factory() -> object:
        events.append("oauth_scope_entry")
        return _OAUTH

    async def _bad_list_tools(*, cursor: str | None = None) -> object:
        raise RuntimeError(f"SECRET_PROVIDER_TEXT {_ACCOUNT}")

    transport = RobinhoodCapabilityTransport(
        oauth_factory, session_factory=bad_discovery_session
    )

    with pytest.raises(CapabilityTransportError) as error:
        transport.__enter__()

    assert error.value.reason == "L41_MCP_SESSION_OPEN_FAILED"
    assert "SECRET_PROVIDER_TEXT" not in repr(error.value)
    assert _ACCOUNT not in repr(error.value)
    assert events == ["oauth_scope_entry", "session_open", "session_close"]
    assert transport.call_counts.oauth_scope_entry_attempts == 1
    assert transport.call_counts.mcp_session_open_attempts == 1
    assert transport.call_counts.get_accounts_attempts == 0
    assert transport.call_counts.get_equity_tradability_attempts == 0


def test_tradability_call_requires_resolved_account_and_fixed_symbol() -> None:
    events: list[str] = []
    client = _FakeClient()
    transport = _transport(client, events)

    with transport as boundary:
        with pytest.raises(CapabilityTransportError) as error:
            boundary.get_equity_tradability(
                {"account_number": _ACCOUNT, "symbols": ["AAPL"]}
            )
        assert error.value.reason == "L41_ACCOUNT_READ_REQUIRED"
        boundary.get_accounts()
        with pytest.raises(CapabilityTransportError) as error:
            boundary.get_equity_tradability(
                {"account_number": "OTHER", "symbols": ["SPY"]}
            )
        assert error.value.reason == "L41_TRADABILITY_ARGUMENTS_INVALID"
        boundary.get_equity_tradability(
            {"account_number": _ACCOUNT, "symbols": ["SPY"]}
        )

    assert [name for name, _ in client.calls] == [
        "get_accounts",
        "get_equity_tradability",
    ]
    assert transport.call_counts.get_equity_tradability_attempts == 1
