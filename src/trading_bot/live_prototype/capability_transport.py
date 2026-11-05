"""Single-session, two-read Robinhood MCP transport for L41 only."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from types import TracebackType
from typing import Protocol

from trading_bot.desktop_paper.robinhood_read import resolve_account
from trading_bot.robinhood_mcp.sdk_transport import ROBINHOOD_TRADING_MCP_URL

_GET_ACCOUNTS = "get_accounts"
_GET_TRADABILITY = "get_equity_tradability"
_ALLOWED_TOOLS = frozenset({_GET_ACCOUNTS, _GET_TRADABILITY})
_MAX_DISCOVERY_PAGES = 20
_OPERATION_TIMEOUT_SECONDS = 90
_REASON_CODES = frozenset(
    {
        "L41_LOOP_ALREADY_STARTED",
        "L41_LOOP_START_FAILED",
        "L41_SESSION_NOT_OPEN",
        "L41_MCP_TIMEOUT",
        "L41_MCP_REQUEST_FAILED",
        "L41_LOOP_STOP_FAILED",
        "L41_TRANSPORT_FAILED",
        "L41_TRANSPORT_ALREADY_USED",
        "L41_OAUTH_INITIALIZATION_FAILED",
        "L41_MCP_SESSION_OPEN_FAILED",
        "L41_MCP_SESSION_CLOSE_FAILED",
        "L41_ACCOUNTS_RETRY_BLOCKED",
        "L41_ACCOUNT_IDENTITY_INVALID",
        "L41_ACCOUNT_READ_REQUIRED",
        "L41_TRADABILITY_RETRY_BLOCKED",
        "L41_TRADABILITY_ARGUMENTS_INVALID",
        "L41_TOOL_NOT_ALLOWED",
        "L41_MCP_TOOL_FAILED",
        "L41_MCP_RESULT_INVALID",
        "L41_TOOL_DISCOVERY_FAILED",
        "L41_TOOL_DISCOVERY_INVALID",
        "L41_TOOL_DISCOVERY_CURSOR_INVALID",
        "L41_TOOL_DISCOVERY_BOUND_EXCEEDED",
        "L41_REQUIRED_TOOL_MISSING",
        "L41_MCP_DEPENDENCY_UNAVAILABLE",
        "L41_MCP_SESSION_FAILED",
    }
)


class CapabilityTransportError(RuntimeError):
    """Fixed sanitized diagnostic for an L41 MCP transport failure."""

    def __init__(self, reason: str) -> None:
        if type(reason) is not str or reason not in _REASON_CODES:
            reason = "L41_TRANSPORT_FAILED"
        self.reason = reason
        super().__init__(reason)


class _McpClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object: ...


class _LoopThread:
    """Keep one async MCP client session alive behind a synchronous boundary."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self._run,
            name="arch147-l41-mcp-session",
            daemon=True,
        )
        self.ready = threading.Event()
        self.started = False

    def start(self) -> None:
        if self.started:
            raise CapabilityTransportError("L41_LOOP_ALREADY_STARTED")
        self.started = True
        self.thread.start()
        if not self.ready.wait(_OPERATION_TIMEOUT_SECONDS):
            raise CapabilityTransportError("L41_LOOP_START_FAILED")

    def run(self, awaitable: object) -> object:
        if not self.started or not self.thread.is_alive():
            if hasattr(awaitable, "close"):
                awaitable.close()  # type: ignore[union-attr]
            raise CapabilityTransportError("L41_SESSION_NOT_OPEN")
        future: Future[object] = asyncio.run_coroutine_threadsafe(
            awaitable,
            self.loop,  # type: ignore[arg-type]
        )
        try:
            return future.result(timeout=_OPERATION_TIMEOUT_SECONDS)
        except FutureTimeoutError:
            future.cancel()
            raise CapabilityTransportError("L41_MCP_TIMEOUT") from None
        except CapabilityTransportError as error:
            reason = (
                error.reason
                if type(error) is CapabilityTransportError
                and error.reason in _REASON_CODES
                else "L41_TRANSPORT_FAILED"
            )
            raise CapabilityTransportError(reason) from None
        except Exception:
            raise CapabilityTransportError("L41_MCP_REQUEST_FAILED") from None

    def stop(self) -> None:
        if not self.started:
            return
        if self.thread.is_alive():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=_OPERATION_TIMEOUT_SECONDS)
        if self.thread.is_alive():
            raise CapabilityTransportError("L41_LOOP_STOP_FAILED")
        self.loop.close()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.ready.set()
        self.loop.run_forever()
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        asyncio.set_event_loop(None)


@dataclass(frozen=True, slots=True)
class CapabilityTransportCounts:
    """Scope/session/tool attempts; native credential reads are not observed."""

    oauth_scope_entry_attempts: int
    mcp_session_open_attempts: int
    get_accounts_attempts: int
    get_equity_tradability_attempts: int
    other_tool_attempts: int = field(default=0, init=False)
    review_equity_order_attempts: int = field(default=0, init=False)
    place_equity_order_attempts: int = field(default=0, init=False)
    cancel_equity_order_attempts: int = field(default=0, init=False)
    native_credential_read_count: int | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        values = (
            self.oauth_scope_entry_attempts,
            self.mcp_session_open_attempts,
            self.get_accounts_attempts,
            self.get_equity_tradability_attempts,
        )
        if any(type(value) is not int or value < 0 or value > 1 for value in values):
            raise ValueError("L41_TRANSPORT_COUNT_INVALID")

    @property
    def credential_store_accounting(self) -> str:
        return "OAUTH_SCOPE_ONCE_NATIVE_READS_SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED"


class RobinhoodCapabilityTransport:
    """A one-shot source boundary exposing only the two permitted read methods."""

    __slots__ = (
        "_oauth_factory",
        "_session_factory",
        "_loop_thread",
        "_session_context",
        "_client",
        "_oauth_attempts",
        "_session_attempts",
        "_accounts_attempts",
        "_tradability_attempts",
        "_account_number",
        "_entered",
        "_closed",
    )

    def __init__(
        self,
        oauth_factory: Callable[[], object],
        *,
        session_factory: Callable[[object], AbstractAsyncContextManager[_McpClient]]
        | None = None,
    ) -> None:
        if not callable(oauth_factory):
            raise TypeError("oauth_factory must be callable")
        if session_factory is not None and not callable(session_factory):
            raise TypeError("session_factory must be callable")
        self._oauth_factory = oauth_factory
        self._session_factory = (
            _production_session if session_factory is None else session_factory
        )
        self._loop_thread = _LoopThread()
        self._session_context: AbstractAsyncContextManager[_McpClient] | None = None
        self._client: _McpClient | None = None
        self._oauth_attempts = 0
        self._session_attempts = 0
        self._accounts_attempts = 0
        self._tradability_attempts = 0
        self._account_number: str | None = None
        self._entered = False
        self._closed = False

    def __repr__(self) -> str:
        return "RobinhoodCapabilityTransport(<redacted>)"

    @property
    def call_counts(self) -> CapabilityTransportCounts:
        return CapabilityTransportCounts(
            self._oauth_attempts,
            self._session_attempts,
            self._accounts_attempts,
            self._tradability_attempts,
        )

    def __enter__(self) -> RobinhoodCapabilityTransport:
        if self._entered or self._closed:
            raise CapabilityTransportError("L41_TRANSPORT_ALREADY_USED")
        self._entered = True
        self._oauth_attempts += 1
        try:
            oauth = self._oauth_factory()
        except Exception:
            raise CapabilityTransportError("L41_OAUTH_INITIALIZATION_FAILED") from None

        self._loop_thread.start()
        self._session_attempts += 1
        try:
            self._loop_thread.run(self._open_session(oauth))
        except Exception:
            self._close_after_open_failure()
            raise CapabilityTransportError("L41_MCP_SESSION_OPEN_FAILED") from None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        close_failed = False
        try:
            if self._client is not None:
                self._loop_thread.run(self._close_session(exc_type, exc, traceback))
        except Exception:
            close_failed = True
        finally:
            self._closed = True
            self._loop_thread.stop()
        if close_failed and exc is None:
            raise CapabilityTransportError("L41_MCP_SESSION_CLOSE_FAILED") from None
        return False

    def get_accounts(self) -> Mapping[str, object]:
        self._require_open()
        if self._accounts_attempts != 0:
            raise CapabilityTransportError("L41_ACCOUNTS_RETRY_BLOCKED")
        self._accounts_attempts += 1
        result = self._run_tool(_GET_ACCOUNTS, {})
        try:
            identity = resolve_account(result)
        except Exception:
            raise CapabilityTransportError("L41_ACCOUNT_IDENTITY_INVALID") from None
        self._account_number = identity.account_number
        return result

    def get_equity_tradability(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._require_open()
        if self._accounts_attempts != 1 or self._account_number is None:
            raise CapabilityTransportError("L41_ACCOUNT_READ_REQUIRED")
        if self._tradability_attempts != 0:
            raise CapabilityTransportError("L41_TRADABILITY_RETRY_BLOCKED")
        if (
            not isinstance(arguments, Mapping)
            or set(arguments) != {"account_number", "symbols"}
            or arguments.get("account_number") != self._account_number
            or arguments.get("symbols") != ["SPY"]
        ):
            raise CapabilityTransportError("L41_TRADABILITY_ARGUMENTS_INVALID")
        self._tradability_attempts += 1
        return self._run_tool(_GET_TRADABILITY, dict(arguments))

    def _require_open(self) -> None:
        if not self._entered or self._closed or self._client is None:
            raise CapabilityTransportError("L41_SESSION_NOT_OPEN")

    def _run_tool(
        self, name: str, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if name not in _ALLOWED_TOOLS:
            raise CapabilityTransportError("L41_TOOL_NOT_ALLOWED")
        try:
            payload = self._loop_thread.run(self._call_tool(name, arguments))
        except CapabilityTransportError:
            raise
        except Exception:
            raise CapabilityTransportError("L41_MCP_TOOL_FAILED") from None
        if not isinstance(payload, Mapping):
            raise CapabilityTransportError("L41_MCP_RESULT_INVALID")
        return dict(payload)

    async def _open_session(self, oauth: object) -> None:
        self._session_context = self._session_factory(oauth)
        self._client = await self._session_context.__aenter__()
        await _require_allowed_tools(self._client)

    async def _close_session(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        context = self._session_context
        if context is not None:
            await context.__aexit__(exc_type, exc, traceback)
        self._client = None

    async def _call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        client = self._client
        if client is None:
            raise CapabilityTransportError("L41_SESSION_NOT_OPEN")
        if name == _GET_ACCOUNTS:
            result = await client.call_tool(_GET_ACCOUNTS, {})
        elif name == _GET_TRADABILITY:
            result = await client.call_tool(_GET_TRADABILITY, dict(arguments))
        else:
            raise CapabilityTransportError("L41_TOOL_NOT_ALLOWED")
        if getattr(result, "is_error", None) is not False:
            raise CapabilityTransportError("L41_MCP_TOOL_FAILED")
        payload = getattr(result, "structured_content", None)
        if not isinstance(payload, Mapping):
            raise CapabilityTransportError("L41_MCP_RESULT_INVALID")
        return dict(payload)

    def _close_after_open_failure(self) -> None:
        try:
            if self._session_context is not None:
                self._loop_thread.run(self._close_session(None, None, None))
        except Exception:
            pass
        self._closed = True
        self._loop_thread.stop()


async def _require_allowed_tools(client: _McpClient) -> None:
    cursor: str | None = None
    seen_cursors: set[str] = set()
    found: set[str] = set()
    for _ in range(_MAX_DISCOVERY_PAGES):
        try:
            listing = await client.list_tools(cursor=cursor)
        except Exception:
            raise CapabilityTransportError("L41_TOOL_DISCOVERY_FAILED") from None
        entries = getattr(listing, "tools", None)
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise CapabilityTransportError("L41_TOOL_DISCOVERY_INVALID")
        for entry in entries:
            name = getattr(entry, "name", None)
            if name in _ALLOWED_TOOLS:
                found.add(name)
        cursor = getattr(listing, "next_cursor", None)
        if cursor is None:
            break
        if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
            raise CapabilityTransportError("L41_TOOL_DISCOVERY_CURSOR_INVALID")
        seen_cursors.add(cursor)
    else:
        raise CapabilityTransportError("L41_TOOL_DISCOVERY_BOUND_EXCEEDED")
    if found != _ALLOWED_TOOLS:
        raise CapabilityTransportError("L41_REQUIRED_TOOL_MISSING")


@asynccontextmanager
async def _production_session(oauth: object) -> AsyncIterator[_McpClient]:
    try:
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
    except ImportError:
        raise CapabilityTransportError("L41_MCP_DEPENDENCY_UNAVAILABLE") from None

    try:
        async with httpx2.AsyncClient(auth=oauth, timeout=60) as http:
            async with Client(
                streamable_http_client(
                    ROBINHOOD_TRADING_MCP_URL,
                    http_client=http,
                )
            ) as client:
                yield client
    except CapabilityTransportError:
        raise
    except Exception:
        raise CapabilityTransportError("L41_MCP_SESSION_FAILED") from None
