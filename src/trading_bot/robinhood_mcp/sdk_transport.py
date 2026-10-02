"""Direct allowlisted Streamable-HTTP transport for Robinhood paper mode."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Final, Protocol
from urllib.parse import urlparse

from trading_bot.robinhood_mcp.account_resolution import RobinhoodAgenticAccountResolver

ROBINHOOD_TRADING_MCP_URL: Final = "https://agent.robinhood.com/mcp/trading"
_ALLOWED_TOOL_NAMES: Final = (
    "get_equity_orders",
    "get_equity_quotes",
    "review_equity_order",
)
_MAX_TOOL_LIST_PAGES: Final = 20


class RobinhoodMcpClientError(RuntimeError):
    """Base error for the direct Robinhood MCP transport."""


class RobinhoodMcpDependencyError(RobinhoodMcpClientError):
    """The optional MCP runtime dependencies are unavailable."""


class RobinhoodMcpToolUnavailableError(RobinhoodMcpClientError):
    """The connected server does not advertise the reviewed tool surface."""


class RobinhoodMcpToolCallError(RobinhoodMcpClientError):
    """An allowlisted MCP tool returned an error result."""


class RobinhoodMcpStructuredResultError(RobinhoodMcpClientError):
    """An allowlisted tool did not return structured application data."""


class RobinhoodMcpEventLoopError(RobinhoodMcpClientError):
    """The blocking transport was invoked from an active event loop."""


class _ToolCaller(Protocol):
    async def __call__(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]: ...


OAuthFactory = Callable[[], object]


class RobinhoodMcpStreamableHttpTransport:
    """Blocking implementation of the exact review/read transport allowlist."""

    __slots__ = ("_oauth_factory", "_test_caller")

    def __init__(self, oauth_factory: OAuthFactory) -> None:
        if not callable(oauth_factory):
            raise TypeError("oauth_factory must be callable")
        self._oauth_factory: OAuthFactory | None = oauth_factory
        self._test_caller: _ToolCaller | None = None

    @classmethod
    def for_test(cls, caller: _ToolCaller) -> RobinhoodMcpStreamableHttpTransport:
        if not callable(caller):
            raise TypeError("caller must be callable")
        instance = cls.__new__(cls)
        instance._oauth_factory = None
        instance._test_caller = caller
        return instance

    def review_equity_order(
        self,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        return self._invoke("review_equity_order", arguments)

    def get_equity_quotes(
        self,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        return self._invoke("get_equity_quotes", arguments)

    def get_equity_orders(
        self,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        return self._invoke("get_equity_orders", arguments)

    def _invoke(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        if tool_name not in _ALLOWED_TOOL_NAMES:
            raise RobinhoodMcpToolUnavailableError("tool is outside paper allowlist")
        if not isinstance(arguments, Mapping):
            raise TypeError("arguments must be a mapping")
        copied = dict(arguments)
        caller = self._test_caller
        if caller is not None:
            return _run_blocking(lambda: caller(tool_name, copied))
        return _run_blocking(lambda: self._call_tool_once(tool_name, copied))

    async def _call_tool_once(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        if tool_name not in _ALLOWED_TOOL_NAMES:
            raise RobinhoodMcpToolUnavailableError("tool is outside paper allowlist")
        return await self._request_once(tool_name, arguments)

    def _get_accounts(self) -> Mapping[str, object]:
        caller = self._test_caller
        if caller is not None:
            return _run_blocking(lambda: caller("get_accounts", {}))
        return _run_blocking(lambda: self._request_once("get_accounts", {}))

    async def _request_once(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        if tool_name not in _ALLOWED_TOOL_NAMES and tool_name != "get_accounts":
            raise RobinhoodMcpToolUnavailableError("tool is outside paper boundary")
        if tool_name == "get_accounts" and arguments:
            raise RobinhoodMcpToolUnavailableError("account lookup takes no arguments")
        oauth_factory = self._oauth_factory
        if oauth_factory is None:
            raise RobinhoodMcpClientError("production OAuth factory is unavailable")
        try:
            import httpx2
            from mcp import Client
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            raise RobinhoodMcpDependencyError(
                "install the robinhood-mcp optional dependency"
            ) from None

        oauth_auth = oauth_factory()
        async with httpx2.AsyncClient(auth=oauth_auth) as http_client:
            stream = streamable_http_client(
                ROBINHOOD_TRADING_MCP_URL,
                http_client=http_client,
            )
            async with Client(stream) as client:
                await _require_review_read_tools(
                    client, require_accounts=tool_name == "get_accounts"
                )
                result = await client.call_tool(tool_name, dict(arguments))
        if tool_name == "get_accounts":
            return _accounts_structured_result(result)
        return _structured_result(tool_name, result)


def create_robinhood_agentic_account_resolver(
    transport: RobinhoodMcpStreamableHttpTransport,
) -> RobinhoodAgenticAccountResolver:
    """Bind canonical account resolution to the private transport read boundary."""
    if not isinstance(transport, RobinhoodMcpStreamableHttpTransport):
        raise TypeError("transport must be RobinhoodMcpStreamableHttpTransport")
    return RobinhoodAgenticAccountResolver(transport._get_accounts)


def _accounts_structured_result(result: object) -> Mapping[str, object]:
    if getattr(result, "is_error", None) is not False:
        raise RobinhoodMcpToolCallError("account metadata returned an MCP tool error")
    structured = getattr(result, "structured_content", None)
    if not isinstance(structured, Mapping):
        raise RobinhoodMcpStructuredResultError(
            "account metadata returned no structured content"
        )
    return dict(structured)


def create_robinhood_oauth_factory(
    *,
    storage: object,
    redirect_handler: Callable[[str], Awaitable[None]],
    callback_handler: Callable[[], Awaitable[object]],
    redirect_uri: str,
    client_name: str = "AI Trading Bot",
) -> OAuthFactory:
    """Create a lazy standard-MCP OAuth provider factory for Robinhood."""

    _require_token_storage(storage)
    if not callable(redirect_handler) or not callable(callback_handler):
        raise TypeError("OAuth handlers must be callable")
    local_redirect = _require_loopback_redirect_uri(redirect_uri)
    if (
        not isinstance(client_name, str)
        or not client_name.strip()
        or client_name != client_name.strip()
        or len(client_name) > 128
    ):
        raise ValueError("client_name must be exact nonblank text up to 128 chars")

    def factory() -> object:
        try:
            from mcp.client.auth import OAuthClientProvider
            from mcp.shared.auth import OAuthClientMetadata
        except ImportError:
            raise RobinhoodMcpDependencyError(
                "install the robinhood-mcp optional dependency"
            ) from None
        metadata = OAuthClientMetadata(
            client_name=client_name,
            redirect_uris=[local_redirect],
        )
        return OAuthClientProvider(
            server_url=ROBINHOOD_TRADING_MCP_URL,
            client_metadata=metadata,
            storage=storage,
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
        )

    return factory


async def _require_review_read_tools(
    client: object, *, require_accounts: bool = False
) -> None:
    expected = set(_ALLOWED_TOOL_NAMES)
    if require_accounts:
        expected.add("get_accounts")
    observed: set[str] = set()
    cursor: str | None = None
    seen_cursors: set[str] = set()
    pages = 0
    while True:
        listing = await client.list_tools(cursor=cursor)
        pages += 1
        if pages > _MAX_TOOL_LIST_PAGES:
            raise RobinhoodMcpToolUnavailableError(
                "MCP tool inventory exceeded pagination bound"
            )
        tools = getattr(listing, "tools", None)
        if not isinstance(tools, Sequence) or isinstance(
            tools, (str, bytes, bytearray)
        ):
            raise RobinhoodMcpToolUnavailableError("MCP tool inventory is malformed")
        for tool in tools:
            name = getattr(tool, "name", None)
            if not isinstance(name, str) or not name:
                raise RobinhoodMcpToolUnavailableError(
                    "MCP tool inventory contains invalid name"
                )
            observed.add(name)
        next_cursor = getattr(listing, "next_cursor", None)
        if next_cursor is None:
            break
        if not isinstance(next_cursor, str) or not next_cursor:
            raise RobinhoodMcpToolUnavailableError("MCP tool cursor is malformed")
        if next_cursor in seen_cursors:
            raise RobinhoodMcpToolUnavailableError("MCP tool cursor repeated")
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    missing = sorted(expected - observed)
    if missing:
        raise RobinhoodMcpToolUnavailableError(
            "required Robinhood MCP tools are unavailable: " + ",".join(missing)
        )


def _structured_result(
    tool_name: str,
    result: object,
) -> Mapping[str, object]:
    if tool_name not in _ALLOWED_TOOL_NAMES:
        raise RobinhoodMcpToolUnavailableError("tool is outside paper allowlist")
    if getattr(result, "is_error", None) is not False:
        raise RobinhoodMcpToolCallError(f"{tool_name} returned an MCP tool error")
    structured = getattr(result, "structured_content", None)
    if not isinstance(structured, Mapping):
        raise RobinhoodMcpStructuredResultError(
            f"{tool_name} returned no structured content"
        )
    return dict(structured)


def _run_blocking(
    operation: Callable[[], Awaitable[Mapping[str, object]]],
) -> Mapping[str, object]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(operation())
    raise RobinhoodMcpEventLoopError(
        "blocking Robinhood MCP transport cannot run inside an active event loop"
    )


def _require_token_storage(storage: object) -> None:
    required = (
        "get_tokens",
        "set_tokens",
        "get_client_info",
        "set_client_info",
    )
    if any(not callable(getattr(storage, name, None)) for name in required):
        raise TypeError("storage must implement the MCP TokenStorage protocol")


def _require_loopback_redirect_uri(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("redirect_uri must be exact nonblank text")
    parsed = urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path
        or parsed.path == "/"
    ):
        raise ValueError("redirect_uri must be loopback HTTP with port and path")
    return value
