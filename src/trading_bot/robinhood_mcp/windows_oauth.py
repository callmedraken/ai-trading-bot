"""131-F fixed Windows OAuth storage and bounded IPv4 loopback callbacks.

No authentication or credential access occurs during composition. Python/Pydantic
immutable strings cannot be guaranteed to be zeroized; mutable native/copy buffers
are cleared at their ownership boundary.
"""

from __future__ import annotations

import asyncio
import ctypes
import math
import os
import re
import threading
import webbrowser
from collections.abc import Callable
from typing import TYPE_CHECKING, Final, Protocol
from urllib.parse import parse_qs, urlsplit

if TYPE_CHECKING:
    from mcp.shared.auth import (
        AuthorizationCodeResult,
        OAuthClientInformationFull,
        OAuthToken,
    )

TOKEN_TARGET: Final = "AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1"
CLIENT_INFO_TARGET: Final = "AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1"
CRED_TYPE_GENERIC: Final = 1
CRED_PERSIST_LOCAL_MACHINE: Final = 2
CRED_MAX_CREDENTIAL_BLOB_SIZE: Final = 2560
LOOPBACK_HOST: Final = "127.0.0.1"
MAX_REQUEST_LINE: Final = 4096
MAX_HEADER_BYTES: Final = 8192
MAX_HEADERS: Final = 32
MAX_CALLBACK_TIMEOUT: Final = 300.0
_MAX_ADDRESS: Final = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1


class WindowsOAuthStorageError(RuntimeError):
    """Sanitized storage failure."""


class WindowsOAuthStorageSizeError(WindowsOAuthStorageError):
    """State exceeds the single Windows generic credential record limit."""


class LoopbackOAuthError(RuntimeError):
    """Sanitized local callback failure."""


class CredentialApi(Protocol):
    def read_generic(self, target: str) -> bytearray | None: ...

    def write_generic(self, target: str, blob: bytearray) -> None: ...


def _zero(blob: bytearray) -> None:
    for index in range(len(blob)):
        blob[index] = 0


def _require_target(target: str) -> None:
    if type(target) is not str or target not in {TOKEN_TARGET, CLIENT_INFO_TARGET}:
        raise WindowsOAuthStorageError("OAuth credential target is invalid")


def _blob_range(address: int | None, size: int) -> bool:
    return (
        type(size) is int
        and 0 < size <= CRED_MAX_CREDENTIAL_BLOB_SIZE
        and type(address) is int
        and 0 < address <= _MAX_ADDRESS
        and address + size <= _MAX_ADDRESS + 1
    )


class WindowsCredentialApi:
    """Exact CredReadW/CredWriteW generic records in the current Windows account."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsOAuthStorageError("Windows OAuth storage is unavailable")
        from ctypes import wintypes

        class Credential(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        self._credential = Credential
        self._api = ctypes.WinDLL("advapi32", use_last_error=True)
        pointer = ctypes.POINTER(Credential)
        self._api.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(pointer),
        ]
        self._api.CredReadW.restype = wintypes.BOOL
        self._api.CredWriteW.argtypes = [pointer, wintypes.DWORD]
        self._api.CredWriteW.restype = wintypes.BOOL
        self._api.CredFree.argtypes = [ctypes.c_void_p]
        self._api.CredFree.restype = None
        ntdll = ctypes.WinDLL("ntdll")
        self._zero_memory = getattr(ntdll, "RtlSecureZeroMemory", ntdll.RtlZeroMemory)
        self._zero_memory.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self._zero_memory.restype = ctypes.c_void_p

    def __repr__(self) -> str:
        return "WindowsCredentialApi(<redacted>)"

    __str__ = __repr__

    def read_generic(self, target: str) -> bytearray | None:
        _require_target(target)
        pointer = ctypes.POINTER(self._credential)()
        blob = bytearray()
        address = None
        size = 0
        failed = False
        oversized = False
        missing = False
        cleanup_failed = False
        try:
            if not self._api.CredReadW(
                target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)
            ):
                missing = ctypes.get_last_error() == 1168
                failed = not missing
            else:
                record = pointer.contents
                size = int(record.CredentialBlobSize)
                address = ctypes.cast(record.CredentialBlob, ctypes.c_void_p).value
                oversized = size > CRED_MAX_CREDENTIAL_BLOB_SIZE
                if (
                    record.TargetName != target
                    or record.Type != CRED_TYPE_GENERIC
                    or record.Persist != CRED_PERSIST_LOCAL_MACHINE
                    or not _blob_range(address, size)
                ):
                    failed = True
                else:
                    # Copy directly to mutable Python storage.
                    blob = bytearray(size)
                    destination = (ctypes.c_ubyte * size).from_buffer(blob)
                    ctypes.memmove(destination, address, size)
        except Exception:
            failed = True
        finally:
            if bool(pointer):
                try:
                    if _blob_range(address, size):
                        self._zero_memory(address, size)
                except Exception:
                    cleanup_failed = True
                finally:
                    try:
                        self._api.CredFree(pointer)
                    except Exception:
                        cleanup_failed = True
        if failed or oversized or cleanup_failed:
            _zero(blob)
            if oversized:
                raise WindowsOAuthStorageSizeError(
                    "OAuth credential exceeds record limit"
                )
            raise WindowsOAuthStorageError("OAuth credential read or cleanup failed")
        return None if missing else blob

    def write_generic(self, target: str, blob: bytearray) -> None:
        _require_target(target)
        if type(blob) is not bytearray or not blob:
            raise WindowsOAuthStorageError("OAuth credential value is invalid")
        if len(blob) > CRED_MAX_CREDENTIAL_BLOB_SIZE:
            raise WindowsOAuthStorageSizeError("OAuth credential exceeds record limit")
        failed = False
        try:
            buffer = (ctypes.c_ubyte * len(blob)).from_buffer(blob)
            record = self._credential(
                Type=CRED_TYPE_GENERIC,
                TargetName=target,
                CredentialBlobSize=len(blob),
                CredentialBlob=buffer,
                Persist=CRED_PERSIST_LOCAL_MACHINE,
            )
            if not self._api.CredWriteW(ctypes.byref(record), 0):
                failed = True
        except Exception:
            failed = True
        finally:
            _zero(blob)
        if failed:
            raise WindowsOAuthStorageError("OAuth credential write failed")


def _models() -> tuple[type, type, type]:
    try:
        from mcp.shared.auth import (
            AuthorizationCodeResult,
            OAuthClientInformationFull,
            OAuthToken,
        )
    except ImportError:
        raise WindowsOAuthStorageError(
            "Install the robinhood-mcp optional dependency"
        ) from None

    # Preserve the SDK's entire schema while preventing accidental repr/str leaks.
    class SafeToken(OAuthToken):
        def __repr__(self) -> str:
            return "OAuthToken(<redacted>)"

        __str__ = __repr__

    class SafeClient(OAuthClientInformationFull):
        def __repr__(self) -> str:
            return "OAuthClientInformationFull(<redacted>)"

        __str__ = __repr__

    class SafeResult(AuthorizationCodeResult):
        def __repr__(self) -> str:
            return "AuthorizationCodeResult(<redacted>)"

        __str__ = __repr__

    return SafeToken, SafeClient, SafeResult


def _validated_model(blob: bytearray, model: type) -> object:
    value = model.model_validate_json(blob, strict=True)
    # SDK string fields need not impose a nonempty minimum length.
    for name in ("access_token", "client_id"):
        if hasattr(value, name) and not getattr(value, name):
            raise ValueError
    return value


class WindowsOAuthStorage:
    """MCP TokenStorage protocol, with no alternate persistence boundary."""

    def __init__(self, *, native_api: CredentialApi | None = None) -> None:
        self._native = WindowsCredentialApi() if native_api is None else native_api

    def __repr__(self) -> str:
        return "WindowsOAuthStorage(<redacted>)"

    __str__ = __repr__

    def _read(self, target: str, model: type) -> object | None:
        blob = None
        try:
            blob = self._native.read_generic(target)
            if blob is None:
                return None
            if type(blob) is not bytearray or not blob:
                raise ValueError
            if len(blob) > CRED_MAX_CREDENTIAL_BLOB_SIZE:
                raise WindowsOAuthStorageSizeError(
                    "OAuth credential exceeds record limit"
                )
            return _validated_model(blob, model)
        except WindowsOAuthStorageSizeError:
            raise WindowsOAuthStorageSizeError(
                "OAuth credential exceeds record limit"
            ) from None
        except Exception:
            raise WindowsOAuthStorageError(
                "OAuth credential is invalid or unreadable"
            ) from None
        finally:
            if type(blob) is bytearray:
                _zero(blob)

    def _write(self, target: str, value: object, model: type) -> None:
        blob = bytearray()
        try:
            if not isinstance(value, model.__bases__[0]):
                raise ValueError
            # Revalidate the full SDK model, including models built without validation.
            blob.extend(value.model_dump_json().encode("utf-8"))
            if len(blob) > CRED_MAX_CREDENTIAL_BLOB_SIZE:
                raise WindowsOAuthStorageSizeError(
                    "OAuth credential exceeds record limit"
                )
            _validated_model(blob, model)
            self._native.write_generic(target, blob)
        except WindowsOAuthStorageSizeError:
            raise WindowsOAuthStorageSizeError(
                "OAuth credential exceeds record limit"
            ) from None
        except Exception:
            raise WindowsOAuthStorageError(
                "OAuth credential is invalid or unwritable"
            ) from None
        finally:
            _zero(blob)

    async def get_tokens(self) -> OAuthToken | None:
        token_model, client_model, _ = _models()
        tokens = self._read(TOKEN_TARGET, token_model)
        if self._read(CLIENT_INFO_TARGET, client_model) is None and tokens is not None:
            raise WindowsOAuthStorageError("OAuth tokens have no client registration")
        return tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        token_model, client_model, _ = _models()
        if self._read(CLIENT_INFO_TARGET, client_model) is None:
            raise WindowsOAuthStorageError("OAuth tokens require client registration")
        self._write(TOKEN_TARGET, tokens, token_model)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        token_model, client_model, _ = _models()
        client = self._read(CLIENT_INFO_TARGET, client_model)
        if client is None and self._read(TOKEN_TARGET, token_model) is not None:
            raise WindowsOAuthStorageError("OAuth tokens have no client registration")
        return client

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        _, client_model, _ = _models()
        self._write(CLIENT_INFO_TARGET, client_info, client_model)


def _redirect_parts(uri: str) -> tuple[str, str, int]:
    try:
        if type(uri) is not str or len(uri) > 2048:
            raise ValueError
        parsed = urlsplit(uri)
        port = parsed.port
        if (
            parsed.scheme != "http"
            or port is None
            or not 1 <= port <= 65535
            or parsed.netloc != f"{LOOPBACK_HOST}:{port}"
            or not re.fullmatch(r"/[A-Za-z0-9_./~-]+", parsed.path)
            or parsed.path == "/"
            or parsed.query
            or parsed.fragment
            or uri != f"http://{LOOPBACK_HOST}:{port}{parsed.path}"
        ):
            raise ValueError
        return parsed.path, parsed.netloc, port
    except Exception:
        raise LoopbackOAuthError("OAuth redirect URI is invalid") from None


class LoopbackOAuthCallback:
    """One bounded authorization flow; SDK retains state/issuer validation authority."""

    def __init__(
        self,
        redirect_uri: str,
        *,
        browser_opener: Callable[[str], object] = webbrowser.open,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._path, self._host, self._port = _redirect_parts(redirect_uri)
        if (
            type(timeout_seconds) not in {int, float}
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= MAX_CALLBACK_TIMEOUT
            or not callable(browser_opener)
        ):
            raise LoopbackOAuthError("OAuth callback configuration is invalid")
        self._timeout = float(timeout_seconds)
        self._opener = browser_opener
        self._lock = threading.Lock()
        self._flow: asyncio.Task | None = None
        self._result: asyncio.Future | None = None
        self._server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self._requests: set[asyncio.Task] = set()
        self._callback_waiting = False

    def __repr__(self) -> str:
        return "LoopbackOAuthCallback(<redacted>)"

    __str__ = __repr__

    async def redirect_handler(self, authorization_url: str) -> None:
        if self._flow is not None or not self._lock.acquire(blocking=False):
            raise LoopbackOAuthError("OAuth callback flow is already active")
        try:
            self._result = asyncio.get_running_loop().create_future()
            self._server = await asyncio.start_server(
                self._request,
                host=LOOPBACK_HOST,
                port=self._port,
                limit=MAX_HEADER_BYTES,
                reuse_address=False,
            )
            self._flow = asyncio.create_task(self._own_flow())
            # Retrieve abandoned errors; callback_handler can still await them.
            self._flow.add_done_callback(
                lambda task: None if task.cancelled() else task.exception()
            )
            opened = await asyncio.wait_for(
                asyncio.to_thread(self._opener, authorization_url),
                timeout=self._timeout,
            )
            if opened is not True:
                raise LoopbackOAuthError("OAuth browser open failed")
        except BaseException as error:
            await self._abort()
            if isinstance(error, asyncio.CancelledError):
                raise
            raise LoopbackOAuthError("OAuth browser or listener start failed") from None

    async def callback_handler(self) -> AuthorizationCodeResult:
        flow = self._flow
        if flow is None or self._callback_waiting:
            raise LoopbackOAuthError("OAuth callback flow is unavailable")
        self._callback_waiting = True
        try:
            return await flow
        except asyncio.CancelledError:
            await self._abort()
            raise
        finally:
            self._callback_waiting = False
            if self._flow is flow:
                self._flow = None

    async def _abort(self) -> None:
        flow = self._flow
        self._flow = None
        if flow is not None:
            flow.cancel()
            await asyncio.gather(flow, return_exceptions=True)
        await self._close()

    async def _close(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
        # Server.wait_closed waits for accepted connections on current Python.
        # Close those transports before waiting for the listener.
        for writer in tuple(self._writers):
            writer.close()
        for task in tuple(self._requests):
            task.cancel()
        await asyncio.gather(*tuple(self._requests), return_exceptions=True)
        if server is not None:
            await server.wait_closed()
        self._writers.clear()
        self._requests.clear()
        self._result = None
        if self._lock.locked():
            self._lock.release()

    async def _own_flow(self) -> AuthorizationCodeResult:
        try:
            return await asyncio.wait_for(self._result, timeout=self._timeout)
        except TimeoutError:
            raise LoopbackOAuthError("OAuth callback timed out") from None
        finally:
            await self._close()

    async def _request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        task = asyncio.current_task()
        self._requests.add(task)
        self._writers.add(writer)
        result = None
        failed = False
        try:
            line = await reader.readuntil(b"\r\n")
            if len(line) > MAX_REQUEST_LINE:
                raise ValueError
            method, target, version = line[:-2].decode("ascii").split(" ")
            if (
                method != "GET"
                or version not in {"HTTP/1.0", "HTTP/1.1"}
                or any(ord(char) <= 32 or ord(char) == 127 for char in target)
                or "#" in target
            ):
                raise ValueError
            headers: dict[str, list[str]] = {}
            total = 0
            for _ in range(MAX_HEADERS + 1):
                header = await reader.readuntil(b"\r\n")
                total += len(header)
                if total > MAX_HEADER_BYTES:
                    raise ValueError
                if header == b"\r\n":
                    break
                name, value = header[:-2].decode("ascii").split(":", 1)
                if not re.fullmatch(r"[A-Za-z0-9-]+", name):
                    raise ValueError
                if any(
                    ord(char) < 32 and char != "\t" or ord(char) == 127
                    for char in value
                ):
                    raise ValueError
                headers.setdefault(name.lower(), []).append(value.strip())
            else:
                raise ValueError
            if (
                headers.get("host") != [self._host]
                or "transfer-encoding" in headers
                or headers.get("content-length", ["0"]) != ["0"]
            ):
                raise ValueError
            parsed = urlsplit(target)
            if (
                parsed.scheme
                or parsed.netloc
                or parsed.fragment
                or parsed.path != self._path
                or not target.startswith(self._path + "?")
                or re.search(r"%(?![0-9A-Fa-f]{2})", parsed.query)
            ):
                raise ValueError
            params = parse_qs(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=16,
            )
            if (
                "error" in params
                or set(params) - {"code", "state", "iss"}
                or len(params.get("code", [])) != 1
                or len(params.get("state", [])) != 1
                or len(params.get("iss", [])) > 1
                or any(
                    not value
                    or any(ord(char) < 32 or ord(char) == 127 for char in value)
                    for values in params.values()
                    for value in values
                )
            ):
                raise ValueError
            _, _, result_model = _models()
            result = result_model(
                code=params["code"][0],
                state=params["state"][0],
                iss=params.get("iss", [None])[0],
            )
        except Exception:
            failed = True
        try:
            body = (
                b"Authorization failed. Return to the application."
                if failed
                else (b"Authorization received. Return to the application.")
            )
            status = b"400 Bad Request" if failed else b"200 OK"
            writer.write(
                b"HTTP/1.1 " + status + b"\r\nContent-Type: text/plain\r\n"
                b"Cache-Control: no-store\r\nConnection: close\r\nContent-Length: "
                + str(len(body)).encode("ascii")
                + b"\r\n\r\n"
                + body
            )
            await writer.drain()
        except Exception:
            failed = True
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                failed = True
            self._writers.discard(writer)
            self._requests.discard(task)
            future = self._result
            if future is not None and not future.done():
                if failed:
                    future.set_exception(LoopbackOAuthError("OAuth callback rejected"))
                else:
                    future.set_result(result)


def create_windows_robinhood_oauth_factory(
    *,
    redirect_uri: str,
    timeout_seconds: float = 120.0,
    browser_opener: Callable[[str], object] = webbrowser.open,
    client_name: str = "AI Trading Bot",
) -> Callable[[], object]:
    """Inert composition; no authentication, credential read, or MCP tool call."""
    from trading_bot.robinhood_mcp.sdk_transport import create_robinhood_oauth_factory

    callback = LoopbackOAuthCallback(
        redirect_uri, browser_opener=browser_opener, timeout_seconds=timeout_seconds
    )
    return create_robinhood_oauth_factory(
        storage=WindowsOAuthStorage(),
        redirect_handler=callback.redirect_handler,
        callback_handler=callback.callback_handler,
        redirect_uri=redirect_uri,
        client_name=client_name,
    )
