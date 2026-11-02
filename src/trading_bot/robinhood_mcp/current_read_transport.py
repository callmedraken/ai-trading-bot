"""Current desktop read-only successor; the Architecture 131 transport is frozen."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Final

from trading_bot.robinhood_mcp.sdk_transport import ROBINHOOD_TRADING_MCP_URL

READ_TOOLS: Final = (
    "get_accounts",
    "get_portfolio",
    "get_equity_positions",
    "get_equity_quotes",
    "get_equity_orders",
)
MAX_DISCOVERY_PAGES: Final = 20


class CurrentReadError(RuntimeError):
    """Fixed sanitized diagnostic; never include provider text or arguments."""


class RobinhoodCurrentReadTransport:
    """Five explicit read methods; OAuth and HTTP are inert until a read call.

    Each read uses one session and discovers the entire required read surface
    before dispatch. No review/mutation capability is required or retained.
    There is no retry, generic public dispatch, or arbitrary endpoint override.
    """

    __slots__ = ("_oauth_factory", "_session_factory", "_counts", "_observed")

    def __init__(self, oauth_factory: Callable[[], object]) -> None:
        if not callable(oauth_factory):
            raise TypeError("OAuth factory must be callable")
        self._oauth_factory = oauth_factory
        self._session_factory = None
        self._counts = dict.fromkeys(READ_TOOLS, 0)
        self._observed: tuple[str, ...] = ()

    @classmethod
    def for_test(
        cls, session_factory: Callable[[], object]
    ) -> RobinhoodCurrentReadTransport:
        instance = cls(lambda: None)
        instance._session_factory = session_factory
        return instance

    @property
    def call_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple(self._counts.items())

    @property
    def observed_read_tools(self) -> tuple[str, ...]:
        return self._observed

    def get_accounts(self) -> Mapping[str, object]:
        return self._invoke("get_accounts", {})

    def get_portfolio(self, arguments: Mapping[str, object]) -> Mapping[str, object]:
        return self._invoke("get_portfolio", arguments)

    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("get_equity_positions", arguments)

    def get_equity_quotes(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("get_equity_quotes", arguments)

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("get_equity_orders", arguments)

    def _invoke(
        self, name: str, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if name not in READ_TOOLS or not isinstance(arguments, Mapping):
            raise CurrentReadError("READ_METHOD_REJECTED")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise CurrentReadError("READ_EVENT_LOOP_REJECTED")
        try:
            return asyncio.run(self._request(name, dict(arguments)))
        except Exception:
            raise CurrentReadError("READ_REQUEST_FAILED") from None

    async def _request(
        self, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        if name not in READ_TOOLS:
            raise CurrentReadError("READ_METHOD_REJECTED")
        if self._session_factory is not None:
            async with self._session_factory() as client:
                return await self._read(client, name, arguments)
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client

        async with httpx2.AsyncClient(auth=self._oauth_factory(), timeout=60) as http:
            async with Client(
                streamable_http_client(ROBINHOOD_TRADING_MCP_URL, http_client=http)
            ) as client:
                return await self._read(client, name, arguments)

    async def _read(
        self, client: object, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        if name not in READ_TOOLS:
            raise CurrentReadError("READ_METHOD_REJECTED")
        cursor = None
        seen = set()
        advertised = set()
        for _ in range(MAX_DISCOVERY_PAGES):
            listing = await client.list_tools(cursor=cursor)
            entries = getattr(listing, "tools", None)
            if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
                raise CurrentReadError("READ_DISCOVERY_INVALID")
            for entry in entries:
                tool_name = getattr(entry, "name", None)
                if not isinstance(tool_name, str) or not tool_name:
                    raise CurrentReadError("READ_DISCOVERY_INVALID")
                # Discard unrelated/mutation names, even from sanitized evidence.
                if tool_name in READ_TOOLS:
                    advertised.add(tool_name)
            cursor = getattr(listing, "next_cursor", None)
            if cursor is None:
                break
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise CurrentReadError("READ_DISCOVERY_CURSOR_INVALID")
            seen.add(cursor)
        else:
            raise CurrentReadError("READ_DISCOVERY_BOUND_EXCEEDED")
        if advertised != set(READ_TOOLS):
            raise CurrentReadError("READ_CAPABILITY_MISSING")
        self._observed = READ_TOOLS
        self._counts[name] += 1
        result = await client.call_tool(name, arguments)
        payload = getattr(result, "structured_content", None)
        if getattr(result, "is_error", None) is not False or not isinstance(
            payload, Mapping
        ):
            raise CurrentReadError("READ_RESULT_INVALID")
        return dict(payload)
