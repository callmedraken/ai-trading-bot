"""Fake SDK sessions prove the current boundary without OAuth or networking."""

import asyncio
from contextlib import asynccontextmanager
from threading import Thread
from types import SimpleNamespace as NS

import pytest

from trading_bot.robinhood_mcp.current_read_transport import (
    READ_TOOLS,
    CurrentReadError,
    RobinhoodCurrentReadTransport,
)
from trading_bot.robinhood_mcp.sdk_transport import _ALLOWED_TOOL_NAMES


class FakeSession:
    def __init__(
        self,
        *,
        tools=READ_TOOLS,
        cursor=None,
        failure=None,
        cleanup_failure=None,
    ):
        self.tools = tools
        self.cursor = cursor
        self.failure = failure
        self.cleanup_failure = cleanup_failure
        self.calls = []
        self.listings = 0
        self.opens = 0
        self.closes = 0
        self.tasks = []

    def _record_task(self):
        self.tasks.append(asyncio.current_task())

    async def list_tools(self, *, cursor):
        self._record_task()
        self.listings += 1
        return NS(tools=[NS(name=n) for n in self.tools], next_cursor=self.cursor)

    async def call_tool(self, name, arguments):
        self._record_task()
        self.calls.append((name, arguments))
        if self.failure:
            raise RuntimeError(self.failure)
        return NS(is_error=False, structured_content={"data": {}})

    @asynccontextmanager
    async def connect(self):
        self.opens += 1
        self._record_task()
        try:
            yield self
        finally:
            self.closes += 1
            self._record_task()
            if self.cleanup_failure:
                raise RuntimeError(self.cleanup_failure)


def test_exact_public_read_surface_and_frozen_131_contract():
    public = {n for n in dir(RobinhoodCurrentReadTransport) if not n.startswith("_")}
    assert public == {*READ_TOOLS, "for_test", "call_counts", "observed_read_tools"}
    assert _ALLOWED_TOOL_NAMES == (
        "get_equity_historicals",
        "get_equity_orders",
        "get_equity_quotes",
        "review_equity_order",
    )
    for name in (
        "review_equity_order",
        "place_equity_order",
        "cancel_equity_order",
        "place_option_order",
        "cancel_option_order",
        "exercise_option",
        "place_crypto_order",
        "cancel_crypto_order",
        "call_tool",
        "get_equity_historicals",
    ):
        assert not hasattr(RobinhoodCurrentReadTransport, name)


@pytest.mark.parametrize("name", READ_TOOLS)
def test_each_read_discovers_all_required_tools_before_one_dispatch(name):
    client = FakeSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    result = getattr(transport, name)(*(() if name == "get_accounts" else ({},)))
    assert result == {"data": {}}
    assert client.calls == [(name, {})]
    assert client.listings == 1
    assert client.opens == client.closes == 1
    assert len({id(task) for task in client.tasks}) == 1
    assert dict(transport.call_counts)[name] == 1
    assert sum(dict(transport.call_counts).values()) == 1
    assert transport.observed_read_tools == READ_TOOLS


@pytest.mark.parametrize("missing", READ_TOOLS)
def test_missing_capability_blocks_even_accounts_before_dispatch(missing):
    client = FakeSession(tools=tuple(t for t in READ_TOOLS if t != missing))
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    with pytest.raises(CurrentReadError):
        transport.get_accounts()
    assert client.calls == []
    assert client.opens == client.closes == 1
    assert sum(dict(transport.call_counts).values()) == 0


def test_mutation_inventory_is_unneeded_and_not_surfaced():
    client = FakeSession(tools=(*READ_TOOLS, "place_equity_order"))
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    transport.get_accounts()
    assert transport.observed_read_tools == READ_TOOLS


def test_repeated_discovery_cursor_is_bounded_before_dispatch():
    client = FakeSession(cursor="repeated")
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    with pytest.raises(CurrentReadError):
        transport.get_accounts()
    assert client.listings == 2
    assert not client.calls


def test_private_dispatch_still_rejects_arbitrary_methods():
    client = FakeSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    with pytest.raises(CurrentReadError):
        transport._invoke("place_equity_order", {})
    assert not client.calls and client.listings == 0


def test_composition_is_inert_and_provider_failures_sanitized():
    def forbidden():
        raise AssertionError("OAuth called at construction")

    RobinhoodCurrentReadTransport(forbidden)
    client = FakeSession(failure="secret-token raw-account-123")
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    with pytest.raises(CurrentReadError) as caught:
        transport.get_accounts()
    assert str(caught.value) == "READ_REQUEST_FAILED"
    assert caught.value.__suppress_context__
    assert len(client.calls) == 1
    assert client.opens == client.closes == 1


def test_multiple_reads_in_explicit_operation_share_session_and_discovery():
    client = FakeSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)

    with transport:
        transport.get_accounts()
        transport.get_equity_positions({})
        transport.get_equity_orders({})

    assert client.opens == client.closes == 1
    assert client.listings == 1
    assert client.calls == [
        ("get_accounts", {}),
        ("get_equity_positions", {}),
        ("get_equity_orders", {}),
    ]
    assert len({id(task) for task in client.tasks}) == 1


def test_new_operation_rediscovers_and_cannot_reuse_prior_capabilities():
    first = FakeSession()
    second = FakeSession(tools=READ_TOOLS[:-1])
    sessions = iter((first, second))
    transport = RobinhoodCurrentReadTransport.for_test(lambda: next(sessions).connect())

    with transport:
        transport.get_accounts()
    with pytest.raises(CurrentReadError, match="READ_REQUEST_FAILED"):
        with transport:
            transport.get_accounts()

    assert first.opens == first.closes == second.opens == second.closes == 1
    assert first.listings == second.listings == 1
    assert first.calls == [("get_accounts", {})]
    assert second.calls == []


def test_nested_scope_and_active_loop_rejection_preserve_outer_session():
    client = FakeSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)

    with transport:
        transport.get_accounts()
        with pytest.raises(CurrentReadError, match="READ_SESSION_REENTRY_REJECTED"):
            with transport:
                pass
        transport.get_equity_positions({})

    async def call_from_running_loop():
        return transport.get_accounts()

    with pytest.raises(CurrentReadError, match="READ_EVENT_LOOP_REJECTED"):
        asyncio.run(call_from_running_loop())

    assert client.opens == client.closes == 1
    assert client.listings == 1
    assert len(client.calls) == 2
    assert len({id(task) for task in client.tasks}) == 1


def test_cross_thread_use_is_rejected_without_opening_another_session():
    client = FakeSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    errors = []

    def invoke_from_other_thread():
        try:
            transport.get_accounts()
        except CurrentReadError as exc:
            errors.append(str(exc))

    with transport:
        thread = Thread(target=invoke_from_other_thread)
        thread.start()
        thread.join()
        assert errors == ["READ_SESSION_USE_REJECTED"]
        assert client.opens == 0
        transport.get_accounts()

    assert client.opens == client.closes == 1
    assert client.listings == 1


def test_body_and_tool_failures_close_and_cleanup_errors_are_sanitized():
    body_session = FakeSession()
    body_transport = RobinhoodCurrentReadTransport.for_test(body_session.connect)
    with pytest.raises(ValueError, match="body failure"):
        with body_transport:
            body_transport.get_accounts()
            raise ValueError("body failure")
    assert body_session.opens == body_session.closes == 1

    tool_session = FakeSession(
        failure="provider-token-secret",
        cleanup_failure="cleanup-token-secret",
    )
    tool_transport = RobinhoodCurrentReadTransport.for_test(tool_session.connect)
    with pytest.raises(CurrentReadError, match="READ_SESSION_CLEANUP_FAILED") as caught:
        tool_transport.get_accounts()
    assert "provider-token-secret" not in str(caught.value)
    assert "cleanup-token-secret" not in str(caught.value)
    assert tool_session.opens == tool_session.closes == 1
    assert len(tool_session.calls) == 1


def test_owner_task_loss_after_session_open_fails_without_hanging(monkeypatch):
    from trading_bot.robinhood_mcp._current_session import _RobinhoodSession

    client = FakeSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)

    async def end_owner_before_dispatch(owner, queue, ready):
        del queue
        async with owner._session_factory():
            ready.set_result(None)

    monkeypatch.setattr(_RobinhoodSession, "_serve", end_owner_before_dispatch)

    with pytest.raises(CurrentReadError, match="READ_SESSION_USE_REJECTED"):
        transport.get_accounts()

    assert client.opens == client.closes == 1
    assert client.listings == 0
    assert client.calls == []


def test_owner_cancelled_tool_reply_is_mapped_to_fixed_error():
    class CancelledSession(FakeSession):
        async def list_tools(self, *, cursor):
            del cursor
            self._record_task()
            raise asyncio.CancelledError

    client = CancelledSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)

    with pytest.raises(CurrentReadError, match="READ_SESSION_USE_REJECTED"):
        transport.get_accounts()

    assert client.opens == client.closes == 1
    assert client.listings == 0
    assert client.calls == []
