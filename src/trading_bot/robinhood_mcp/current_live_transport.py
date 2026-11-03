"""Explicit, discovery-gated Robinhood MCP transport for P6 live execution.

The P5B read facade is intentionally not extended.  This module is the only
current Architecture 147 transport that exposes the bounded live mutation
surface, and it never offers arbitrary public tool dispatch.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from trading_bot.robinhood_mcp.sdk_transport import ROBINHOOD_TRADING_MCP_URL

LIVE_READ_TOOLS: Final = (
    "get_accounts",
    "get_portfolio",
    "get_equity_positions",
    "get_equity_quotes",
    "get_equity_orders",
    "get_equity_historicals",
    "get_equity_tradability",
    "get_trade_approval_setting",
)
LIVE_REVIEW_TOOLS: Final = ("review_equity_order",)
LIVE_MUTATION_TOOLS: Final = ("place_equity_order", "cancel_equity_order")
LIVE_TOOL_SURFACE: Final = LIVE_READ_TOOLS + LIVE_REVIEW_TOOLS + LIVE_MUTATION_TOOLS
MAX_DISCOVERY_PAGES: Final = 20


class CurrentLiveTransportError(RuntimeError):
    """Fixed sanitized diagnostic for discovery, transport, or schema failure."""


@dataclass(frozen=True, slots=True)
class AdvertisedTool:
    """The bounded portion of one advertised MCP tool schema."""

    name: str
    properties: frozenset[str]
    required: frozenset[str]


class RobinhoodCurrentLiveTransport:
    """Typed P6 transport with no public arbitrary ``call_tool`` method."""

    __slots__ = (
        "_oauth_factory",
        "_session_factory",
        "_counts",
        "_observed",
        "_schemas",
    )

    def __init__(self, oauth_factory: Callable[[], object]) -> None:
        if not callable(oauth_factory):
            raise TypeError("OAuth factory must be callable")
        self._oauth_factory = oauth_factory
        self._session_factory = None
        self._counts = dict.fromkeys(LIVE_TOOL_SURFACE, 0)
        self._observed: tuple[str, ...] = ()
        self._schemas: dict[str, AdvertisedTool] = {}

    @classmethod
    def for_test(
        cls, session_factory: Callable[[], object]
    ) -> RobinhoodCurrentLiveTransport:
        instance = cls(lambda: None)
        instance._session_factory = session_factory
        return instance

    @property
    def call_counts(self) -> tuple[tuple[str, int], ...]:
        """Count tool invocation attempts, including failed provider calls."""
        return tuple(self._counts.items())

    @property
    def observed_tools(self) -> tuple[str, ...]:
        return self._observed

    @property
    def advertised_schemas(self) -> tuple[AdvertisedTool, ...]:
        return tuple(self._schemas[name] for name in self._schemas)

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

    def get_equity_historicals(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("get_equity_historicals", arguments)

    def get_equity_tradability(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("get_equity_tradability", arguments)

    def get_trade_approval_setting(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("get_trade_approval_setting", arguments)

    def review_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("review_equity_order", arguments)

    def place_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("place_equity_order", arguments)

    def cancel_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._invoke("cancel_equity_order", arguments)

    def discover_required_capabilities(self) -> tuple[AdvertisedTool, ...]:
        """Discover all P6 tools and validate the exact mutation schemas."""
        return self._discover()

    def _invoke(
        self, name: str, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if name not in LIVE_TOOL_SURFACE or not isinstance(arguments, Mapping):
            raise CurrentLiveTransportError("LIVE_METHOD_REJECTED")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise CurrentLiveTransportError("LIVE_EVENT_LOOP_REJECTED")
        try:
            return asyncio.run(self._request(name, dict(arguments)))
        except CurrentLiveTransportError:
            raise
        except Exception:
            raise CurrentLiveTransportError("LIVE_REQUEST_FAILED") from None

    async def _request(
        self, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        if self._session_factory is not None:
            async with self._session_factory() as client:
                return await self._call(client, name, arguments)
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client

        async with httpx2.AsyncClient(auth=self._oauth_factory(), timeout=60) as http:
            async with Client(
                streamable_http_client(ROBINHOOD_TRADING_MCP_URL, http_client=http)
            ) as client:
                return await self._call(client, name, arguments)

    async def _call(
        self, client: object, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        await self._discover_from_client(client)
        self._validate_mutation_schemas()
        if name not in self._schemas:
            raise CurrentLiveTransportError("LIVE_CAPABILITY_MISSING")
        self._counts[name] += 1
        result = await client.call_tool(name, arguments)
        payload = getattr(result, "structured_content", None)
        if getattr(result, "is_error", None) is not False or not isinstance(
            payload, Mapping
        ):
            raise CurrentLiveTransportError("LIVE_RESULT_INVALID")
        return dict(payload)

    def _discover(self) -> tuple[AdvertisedTool, ...]:
        async def discover() -> tuple[AdvertisedTool, ...]:
            if self._session_factory is not None:
                async with self._session_factory() as client:
                    await self._discover_from_client(client)
            else:
                import httpx2
                from mcp import Client
                from mcp.client.streamable_http import streamable_http_client

                async with httpx2.AsyncClient(
                    auth=self._oauth_factory(), timeout=60
                ) as http:
                    async with Client(
                        streamable_http_client(
                            ROBINHOOD_TRADING_MCP_URL, http_client=http
                        )
                    ) as client:
                        await self._discover_from_client(client)
            self._validate_mutation_schemas()
            return self.advertised_schemas

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise CurrentLiveTransportError("LIVE_EVENT_LOOP_REJECTED")
        try:
            return asyncio.run(discover())
        except CurrentLiveTransportError:
            raise
        except Exception:
            raise CurrentLiveTransportError("LIVE_DISCOVERY_FAILED") from None

    async def _discover_from_client(self, client: object) -> None:
        cursor = None
        seen: set[str] = set()
        found: dict[str, AdvertisedTool] = {}
        for _ in range(MAX_DISCOVERY_PAGES):
            listing = await client.list_tools(cursor=cursor)
            entries = getattr(listing, "tools", None)
            if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
                raise CurrentLiveTransportError("LIVE_DISCOVERY_INVALID")
            for entry in entries:
                tool = _advertised_tool(entry)
                if tool.name in LIVE_TOOL_SURFACE:
                    found[tool.name] = tool
            cursor = getattr(listing, "next_cursor", None)
            if cursor is None:
                break
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise CurrentLiveTransportError("LIVE_DISCOVERY_CURSOR_INVALID")
            seen.add(cursor)
        else:
            raise CurrentLiveTransportError("LIVE_DISCOVERY_BOUND_EXCEEDED")
        if set(found) != set(LIVE_TOOL_SURFACE):
            raise CurrentLiveTransportError("LIVE_CAPABILITY_MISSING")
        self._schemas = found
        self._observed = LIVE_TOOL_SURFACE

    def _validate_mutation_schemas(self) -> None:
        review = self._schemas.get("review_equity_order")
        place = self._schemas.get("place_equity_order")
        cancel = self._schemas.get("cancel_equity_order")
        required_order = frozenset(
            {
                "account_number",
                "symbol",
                "side",
                "type",
                "market_hours",
                "time_in_force",
                "dollar_amount",
            }
        )
        if (
            review is None
            or place is None
            or cancel is None
            or not required_order <= review.properties
            or not required_order <= place.properties
            or "dollar_amount" not in review.required
            or "dollar_amount" not in place.required
            or not frozenset({"account_number", "order_id"}) <= cancel.properties
        ):
            raise CurrentLiveTransportError("LIVE_DOLLAR_ORDER_SCHEMA_MISSING")


def _advertised_tool(entry: object) -> AdvertisedTool:
    name = getattr(entry, "name", None)
    schema = getattr(entry, "inputSchema", None)
    if schema is None:
        schema = getattr(entry, "input_schema", None)
    if not isinstance(name, str) or not name or not isinstance(schema, Mapping):
        raise CurrentLiveTransportError("LIVE_DISCOVERY_INVALID")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, Mapping) or not isinstance(required, list):
        raise CurrentLiveTransportError("LIVE_SCHEMA_INVALID")
    if any(not isinstance(value, str) for value in required) or any(
        not isinstance(value, str) for value in properties
    ):
        raise CurrentLiveTransportError("LIVE_SCHEMA_INVALID")
    return AdvertisedTool(name, frozenset(properties), frozenset(required))
