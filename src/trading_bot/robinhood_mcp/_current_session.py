"""Private operation-scoped async ownership for current Robinhood transports."""

from __future__ import annotations

import asyncio
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
)
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from threading import Lock, get_ident
from typing import TypeVar, cast

from trading_bot.robinhood_mcp.sdk_transport import ROBINHOOD_TRADING_MCP_URL

_Result = TypeVar("_Result")
_SessionFactory = Callable[[], AbstractAsyncContextManager[object]]
_SessionOperation = Callable[[object], Awaitable[object]]
_STOP = object()


class _RobinhoodSessionError(RuntimeError):
    """Fixed private lifecycle failure without provider detail."""


class _RobinhoodSessionEventLoopError(_RobinhoodSessionError):
    pass


class _RobinhoodSessionScopeError(_RobinhoodSessionError):
    pass


class _RobinhoodSessionThreadError(_RobinhoodSessionError):
    pass


class _RobinhoodSessionConcurrentUseError(_RobinhoodSessionError):
    pass


class _RobinhoodSessionFailedError(_RobinhoodSessionError):
    pass


class _RobinhoodSessionCleanupError(_RobinhoodSessionError):
    """Fixed cleanup failure; raw SDK/context exceptions never escape here."""


@dataclass(slots=True)
class _PendingOperation:
    callback: _SessionOperation
    result: asyncio.Future[object]


@asynccontextmanager
async def _open_robinhood_client(
    oauth_factory: Callable[[], object],
    *,
    before_oauth: Callable[[], None] | None = None,
    before_mcp_session: Callable[[], None] | None = None,
) -> AsyncIterator[object]:
    """Open the fixed SDK stack lazily, with optional private attempt hooks."""
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    if before_oauth is not None:
        before_oauth()
    oauth = oauth_factory()
    async with httpx2.AsyncClient(auth=oauth, timeout=60) as http:
        stream = streamable_http_client(
            ROBINHOOD_TRADING_MCP_URL,
            http_client=http,
        )
        if before_mcp_session is not None:
            before_mcp_session()
        async with Client(stream) as client:
            yield client


class _RobinhoodSession:
    """Keep one async context and its owning task alive for one sync operation."""

    __slots__ = (
        "_session_factory",
        "_on_stop",
        "_lock",
        "_active",
        "_owner_thread",
        "_runner",
        "_queue",
        "_task",
        "_busy",
        "_failed",
        "_cleanup_failed",
    )

    def __init__(
        self,
        session_factory: _SessionFactory,
        *,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._on_stop = on_stop
        self._lock = Lock()
        self._active = False
        self._owner_thread: int | None = None
        self._runner: asyncio.Runner | None = None
        self._queue: asyncio.Queue[object] | None = None
        self._task: asyncio.Task[None] | None = None
        self._busy = False
        self._failed = False
        self._cleanup_failed = False

    @property
    def in_scope(self) -> bool:
        with self._lock:
            return self._active

    def start(self) -> None:
        self._reject_running_loop()
        thread_id = get_ident()
        with self._lock:
            if self._active:
                if self._owner_thread != thread_id:
                    raise _RobinhoodSessionThreadError
                raise _RobinhoodSessionScopeError
            runner = asyncio.Runner()
            self._active = True
            self._owner_thread = thread_id
            self._runner = runner
            self._queue = None
            self._task = None
            self._busy = False
            self._failed = False
            self._cleanup_failed = False

    def run(self, operation: Callable[[object], Awaitable[_Result]]) -> _Result:
        return self._drive(lambda: self._submit(operation))

    def _drive(self, async_factory: Callable[[], Awaitable[_Result]]) -> _Result:
        self._reject_running_loop()
        thread_id = get_ident()
        with self._lock:
            if not self._active:
                raise _RobinhoodSessionScopeError
            if self._owner_thread != thread_id:
                raise _RobinhoodSessionThreadError
            if self._busy:
                raise _RobinhoodSessionConcurrentUseError
            if self._failed:
                raise _RobinhoodSessionFailedError
            runner = self._runner
            if runner is None:
                raise _RobinhoodSessionScopeError
            self._busy = True
        try:
            return cast(_Result, runner.run(async_factory()))
        except BaseException:
            with self._lock:
                self._failed = True
            raise
        finally:
            with self._lock:
                self._busy = False

    def stop(self) -> None:
        self._reject_running_loop()
        thread_id = get_ident()
        with self._lock:
            if not self._active:
                return
            if self._owner_thread != thread_id:
                raise _RobinhoodSessionThreadError
            if self._busy:
                raise _RobinhoodSessionConcurrentUseError
            self._busy = True
            runner = self._runner

        cleanup_failed = self._cleanup_failed
        try:
            if runner is not None:
                try:
                    runner.run(self._shutdown())
                except BaseException:
                    cleanup_failed = True
                try:
                    runner.close()
                except BaseException:
                    cleanup_failed = True
        finally:
            with self._lock:
                cleanup_failed = cleanup_failed or self._cleanup_failed
                if self._on_stop is not None:
                    try:
                        self._on_stop()
                    except BaseException:
                        cleanup_failed = True
                self._active = False
                self._owner_thread = None
                self._runner = None
                self._queue = None
                self._task = None
                self._busy = False
                self._failed = False
                self._cleanup_failed = False

        if cleanup_failed:
            raise _RobinhoodSessionCleanupError("MCP session cleanup failed") from None

    async def _submit(
        self, operation: Callable[[object], Awaitable[_Result]]
    ) -> _Result:
        loop = asyncio.get_running_loop()
        if self._task is None:
            queue: asyncio.Queue[object] = asyncio.Queue()
            ready: asyncio.Future[None] = loop.create_future()
            self._queue = queue
            self._task = loop.create_task(self._serve(queue, ready))
            try:
                await ready
            except asyncio.CancelledError:
                current = asyncio.current_task()
                self._failed = True
                if current is not None and current.cancelling():
                    raise
                raise _RobinhoodSessionFailedError from None
            except BaseException:
                self._failed = True
                raise

        if self._failed:
            raise _RobinhoodSessionFailedError
        queue = self._queue
        if queue is None:
            raise _RobinhoodSessionScopeError
        result: asyncio.Future[object] = loop.create_future()
        callback = cast(_SessionOperation, operation)
        queue.put_nowait(_PendingOperation(callback, result))
        task = self._task
        if task is None:
            self._failed = True
            raise _RobinhoodSessionFailedError
        try:
            await asyncio.wait((result, task), return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            self._failed = True
            if result.done():
                try:
                    result.exception()
                except BaseException:
                    pass
            else:
                result.cancel()
            raise
        if not result.done():
            self._failed = True
            raise _RobinhoodSessionFailedError
        try:
            return cast(_Result, result.result())
        except asyncio.CancelledError:
            self._failed = True
            raise _RobinhoodSessionFailedError from None

    async def _serve(
        self,
        queue: asyncio.Queue[object],
        ready: asyncio.Future[None],
    ) -> None:
        entered = False
        dispatch_error: BaseException | None = None
        try:
            async with self._session_factory() as client:
                entered = True
                if not ready.done():
                    ready.set_result(None)
                while True:
                    request = await queue.get()
                    if request is _STOP:
                        return
                    if not isinstance(request, _PendingOperation):
                        self._failed = True
                        return
                    if request.result.cancelled():
                        continue
                    try:
                        value = await request.callback(client)
                    except BaseException as exc:
                        self._failed = True
                        dispatch_error = exc
                        if not request.result.done():
                            request.result.set_exception(exc)
                        raise
                    else:
                        if not request.result.done():
                            request.result.set_result(value)
        except BaseException as exc:
            self._failed = True
            if not ready.done():
                ready.set_exception(exc)
            elif entered and exc is not dispatch_error:
                self._cleanup_failed = True

    async def _shutdown(self) -> None:
        task = self._task
        queue = self._queue
        if task is None or task.done():
            return
        if queue is None:
            self._cleanup_failed = True
            return
        queue.put_nowait(_STOP)
        try:
            await task
        except BaseException:
            self._cleanup_failed = True

    @staticmethod
    def _reject_running_loop() -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise _RobinhoodSessionEventLoopError
