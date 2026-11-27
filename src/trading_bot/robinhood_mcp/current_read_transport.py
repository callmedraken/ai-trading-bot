"""Current desktop read-only successor; the Architecture 131 transport is frozen."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Final, Self, cast

from trading_bot.robinhood_mcp._current_session import (
    _open_robinhood_client,
    _RobinhoodSession,
    _RobinhoodSessionCleanupError,
    _RobinhoodSessionConcurrentUseError,
    _RobinhoodSessionEventLoopError,
    _RobinhoodSessionFailedError,
    _RobinhoodSessionScopeError,
    _RobinhoodSessionThreadError,
)

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
    """Five explicit read methods, scoped to one reusable session per operation.

    OAuth and HTTP remain inert until the first read in an operation. A direct
    getter owns one independent operation; an explicit ``with`` scope lets a
    composed operation reuse one session and one read-capability discovery.
    """

    __slots__ = (
        "_oauth_factory",
        "_session_factory",
        "_session_owner",
        "_session_discovered",
        "_counts",
        "_observed",
        "_oauth_factory_attempts",
        "_mcp_session_open_attempts",
        "_tools_list_call_attempts",
        "_tools_list_pages_received",
    )

    def __init__(self, oauth_factory: Callable[[], object]) -> None:
        if not callable(oauth_factory):
            raise TypeError("OAuth factory must be callable")
        self._oauth_factory = oauth_factory
        self._session_factory: Callable[[], object] | None = None
        self._session_discovered = False
        self._counts = dict.fromkeys(READ_TOOLS, 0)
        self._observed: tuple[str, ...] = ()
        self._oauth_factory_attempts = 0
        self._mcp_session_open_attempts = 0
        self._tools_list_call_attempts = 0
        self._tools_list_pages_received = 0
        self._session_owner = _RobinhoodSession(
            self._new_session,
            on_stop=self._reset_session_state,
        )

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

    @property
    def _provider_attempt_counts(self) -> tuple[tuple[str, int], ...]:
        """Sanitized session and schema-discovery attempts for read evidence."""
        return (
            ("oauth_factory_attempts", self._oauth_factory_attempts),
            ("mcp_session_open_attempts", self._mcp_session_open_attempts),
            ("tools_list_call_attempts", self._tools_list_call_attempts),
            ("tools_list_pages_received", self._tools_list_pages_received),
        )

    def __enter__(self) -> Self:
        try:
            self._session_owner.start()
        except _RobinhoodSessionEventLoopError:
            raise CurrentReadError("READ_EVENT_LOOP_REJECTED") from None
        except _RobinhoodSessionThreadError:
            raise CurrentReadError("READ_SESSION_USE_REJECTED") from None
        except _RobinhoodSessionScopeError:
            raise CurrentReadError("READ_SESSION_REENTRY_REJECTED") from None
        self._session_discovered = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, exc, traceback
        try:
            self._session_owner.stop()
        except _RobinhoodSessionCleanupError:
            raise CurrentReadError("READ_SESSION_CLEANUP_FAILED") from None
        except _RobinhoodSessionEventLoopError:
            raise CurrentReadError("READ_EVENT_LOOP_REJECTED") from None
        except (_RobinhoodSessionThreadError, _RobinhoodSessionConcurrentUseError):
            raise CurrentReadError("READ_SESSION_USE_REJECTED") from None
        return False

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
            if self._session_owner.in_scope:
                return self._session_owner._drive(
                    lambda: self._request(name, dict(arguments))
                )
            with self:
                return self._session_owner._drive(
                    lambda: self._request(name, dict(arguments))
                )
        except _RobinhoodSessionCleanupError:
            raise CurrentReadError("READ_SESSION_CLEANUP_FAILED") from None
        except _RobinhoodSessionEventLoopError:
            raise CurrentReadError("READ_EVENT_LOOP_REJECTED") from None
        except (
            _RobinhoodSessionScopeError,
            _RobinhoodSessionThreadError,
            _RobinhoodSessionConcurrentUseError,
            _RobinhoodSessionFailedError,
        ):
            raise CurrentReadError("READ_SESSION_USE_REJECTED") from None
        except CurrentReadError as exc:
            if str(exc) in {
                "READ_EVENT_LOOP_REJECTED",
                "READ_SESSION_CLEANUP_FAILED",
                "READ_SESSION_REENTRY_REJECTED",
                "READ_SESSION_USE_REJECTED",
            }:
                raise
            raise CurrentReadError("READ_REQUEST_FAILED") from None
        except Exception:
            raise CurrentReadError("READ_REQUEST_FAILED") from None

    def _new_session(self) -> AbstractAsyncContextManager[object]:
        self._mcp_session_open_attempts += 1
        if self._session_factory is not None:
            return cast(AbstractAsyncContextManager[object], self._session_factory())
        return _open_robinhood_client(
            self._oauth_factory,
            before_oauth=self._record_oauth_factory_attempt,
        )

    def _record_oauth_factory_attempt(self) -> None:
        self._oauth_factory_attempts += 1

    async def _request(
        self, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        if name not in READ_TOOLS:
            raise CurrentReadError("READ_METHOD_REJECTED")
        return await self._session_owner._submit(
            lambda client: self._read(client, name, arguments)
        )

    def _reset_session_state(self) -> None:
        self._session_discovered = False

    async def _read(
        self, client: object, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        if name not in READ_TOOLS:
            raise CurrentReadError("READ_METHOD_REJECTED")
        if not self._session_discovered:
            await self._discover_read_tools(client)
            self._session_discovered = True
            self._observed = READ_TOOLS
        self._counts[name] += 1
        result = await client.call_tool(name, arguments)
        payload = getattr(result, "structured_content", None)
        if getattr(result, "is_error", None) is not False or not isinstance(
            payload, Mapping
        ):
            raise CurrentReadError("READ_RESULT_INVALID")
        return dict(payload)

    async def _discover_read_tools(self, client: object) -> None:
        cursor = None
        seen = set()
        advertised = set()
        for _ in range(MAX_DISCOVERY_PAGES):
            self._tools_list_call_attempts += 1
            listing = await client.list_tools(cursor=cursor)
            self._tools_list_pages_received += 1
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
