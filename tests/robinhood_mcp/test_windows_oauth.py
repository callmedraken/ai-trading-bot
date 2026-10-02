from __future__ import annotations

import asyncio
import ctypes
import json
import socket
import sys
from types import ModuleType

import pytest

from trading_bot.robinhood_mcp import windows_oauth as oauth


class Model:
    required: tuple[str, ...] = ()

    def __init__(self, **values):
        self.__dict__.update(values)

    def model_dump_json(self):
        return json.dumps(self.__dict__)

    @classmethod
    def model_validate_json(cls, blob, *, strict):
        assert strict
        values = json.loads(blob)
        if not isinstance(values, dict) or any(
            not isinstance(values.get(key), str) or not values[key]
            for key in cls.required
        ):
            raise ValueError("secret validation detail")
        return cls(**values)


class Token(Model):
    required = ("access_token",)


class Client(Model):
    required = ("client_id",)


class Result(Model):
    required = ("code", "state")


@pytest.fixture(autouse=True)
def fake_sdk(monkeypatch):
    # Source gates intentionally do not require MCP or Pydantic. Exercise lazy
    # import with a schema double; optional real-SDK coverage is below.
    module = ModuleType("mcp.shared.auth")
    module.OAuthToken = Token
    module.OAuthClientInformationFull = Client
    module.AuthorizationCodeResult = Result
    monkeypatch.setitem(sys.modules, "mcp.shared.auth", module)


class Api:
    def __init__(self):
        self.records = {}
        self.reads = []
        self.writes = []
        self.buffers = []
        self.failure = None

    def read_generic(self, target):
        self.reads.append(target)
        if self.failure:
            raise self.failure
        value = self.records.get(target)
        if value is None:
            return None
        blob = bytearray(value)
        self.buffers.append(blob)
        return blob

    def write_generic(self, target, blob):
        self.buffers.append(blob)
        if self.failure:
            raise self.failure
        self.writes.append(target)
        self.records[target] = bytes(blob)


def run(awaitable):
    return asyncio.run(awaitable)


def test_complete_models_round_trip_exact_targets_and_redaction():
    api = Api()
    storage = oauth.WindowsOAuthStorage(native_api=api)
    client = Client(
        client_id="id",
        client_secret="SECRET",
        issuer="https://issuer.example",
        redirect_uris=["http://127.0.0.1:8765/oauth/callback"],
        client_id_issued_at=17,
        client_secret_expires_at=99,
        grant_types=["authorization_code", "refresh_token"],
        contacts=["operator@example.com"],
        jwks={"keys": []},
        software_id="bot",
        scope="read",
        custom_future_field={"full": True},
    )
    token = Token(
        access_token="ACCESS",
        refresh_token="REFRESH",
        token_type="Bearer",
        expires_in=123,
        scope="read",
        future_token_field=["preserved"],
    )
    run(storage.set_client_info(client))
    run(storage.set_tokens(token))
    returned_client = run(storage.get_client_info())
    returned_token = run(storage.get_tokens())
    assert returned_client.__dict__ == client.__dict__
    assert returned_token.__dict__ == token.__dict__
    assert api.writes == [oauth.CLIENT_INFO_TARGET, oauth.TOKEN_TARGET]
    assert set(api.reads) == {oauth.CLIENT_INFO_TARGET, oauth.TOKEN_TARGET}
    assert all(not any(buffer) for buffer in api.buffers)
    for value in (storage, returned_client, returned_token):
        for secret in ("SECRET", "ACCESS", "REFRESH"):
            assert secret not in repr(value) + str(value)


def test_missing_and_orphaned_state_fails_closed():
    api = Api()
    storage = oauth.WindowsOAuthStorage(native_api=api)
    assert run(storage.get_tokens()) is None
    assert run(storage.get_client_info()) is None
    with pytest.raises(oauth.WindowsOAuthStorageError, match="registration"):
        run(storage.set_tokens(Token(access_token="ACCESS")))
    assert not api.writes
    api.records[oauth.TOKEN_TARGET] = b'{"access_token":"ACCESS"}'
    for method in (storage.get_tokens, storage.get_client_info):
        with pytest.raises(oauth.WindowsOAuthStorageError, match="registration"):
            run(method())
    assert all(not any(buffer) for buffer in api.buffers)


@pytest.mark.parametrize("target", [oauth.TOKEN_TARGET, oauth.CLIENT_INFO_TARGET])
@pytest.mark.parametrize("blob", [b"", b"not json SECRET", b"\xff", b"{}", b"[]"])
def test_invalid_persistence_is_sanitized_and_zeroed(target, blob):
    api = Api()
    api.records[oauth.CLIENT_INFO_TARGET] = b'{"client_id":"id"}'
    api.records[target] = blob
    storage = oauth.WindowsOAuthStorage(native_api=api)
    method = (
        storage.get_tokens if target == oauth.TOKEN_TARGET else storage.get_client_info
    )
    with pytest.raises(oauth.WindowsOAuthStorageError) as caught:
        run(method())
    assert "SECRET" not in str(caught.value) + repr(caught.value)
    assert caught.value.__suppress_context__
    assert all(not any(buffer) for buffer in api.buffers)


@pytest.mark.parametrize("kind", ["token", "client"])
def test_size_error_no_split_or_fallback(kind):
    api = Api()
    storage = oauth.WindowsOAuthStorage(native_api=api)
    run(storage.set_client_info(Client(client_id="id")))
    api.writes.clear()
    value = "SECRET" * 1000
    method, model = (
        (storage.set_tokens, Token(access_token=value))
        if kind == "token"
        else (storage.set_client_info, Client(client_id=value))
    )
    with pytest.raises(oauth.WindowsOAuthStorageSizeError) as caught:
        run(method(model))
    assert "SECRET" not in str(caught.value)
    assert api.writes == []
    assert all(not any(buffer) for buffer in api.buffers)
    api.records[oauth.TOKEN_TARGET] = b"x" * 2561
    with pytest.raises(oauth.WindowsOAuthStorageSizeError):
        run(storage.get_tokens())


def test_native_exceptions_are_sanitized_and_write_buffer_zeroed():
    api = Api()
    storage = oauth.WindowsOAuthStorage(native_api=api)
    api.failure = RuntimeError("SECRET")
    with pytest.raises(oauth.WindowsOAuthStorageError) as caught:
        run(storage.get_client_info())
    assert "SECRET" not in str(caught.value)
    with pytest.raises(oauth.WindowsOAuthStorageError) as caught:
        run(storage.set_client_info(Client(client_id="id", client_secret="SECRET")))
    assert "SECRET" not in str(caught.value)
    assert all(not any(buffer) for buffer in api.buffers)


def native_double():
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

    native = object.__new__(oauth.WindowsCredentialApi)
    native._credential = Credential
    native._zero_memory = lambda address, length: ctypes.memset(address, 0, length)
    return native, Credential


@pytest.mark.parametrize("size", [1, 2560])
def test_native_exact_read_zeroes_before_free(size):
    native, credential_type = native_double()
    buffer = (ctypes.c_ubyte * size)(*([7] * size))
    record = credential_type(
        Type=1,
        TargetName=oauth.TOKEN_TARGET,
        Persist=2,
        CredentialBlobSize=size,
        CredentialBlob=buffer,
    )
    events = []

    class Native:
        def CredReadW(self, target, kind, flags, output):
            assert (target, kind, flags) == (oauth.TOKEN_TARGET, 1, 0)
            ctypes.cast(output, ctypes.POINTER(ctypes.POINTER(credential_type)))[0] = (
                ctypes.pointer(record)
            )
            events.append("read")
            return 1

        def CredFree(self, pointer):
            assert not any(buffer)
            events.append("free")

    native._api = Native()
    blob = native.read_generic(oauth.TOKEN_TARGET)
    assert blob == bytearray([7] * size)
    assert events == ["read", "free"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("Type", 2),
        ("Persist", 3),
        ("TargetName", "wrong"),
        ("CredentialBlobSize", 0),
        ("CredentialBlobSize", 2561),
        ("CredentialBlob", None),
    ],
)
def test_native_invalid_record_frees_once(field, value):
    native, credential_type = native_double()
    buffer = (ctypes.c_ubyte * 2560)(*([7] * 2560))
    record = credential_type(
        Type=1,
        TargetName=oauth.TOKEN_TARGET,
        Persist=2,
        CredentialBlobSize=2560,
        CredentialBlob=buffer,
    )
    setattr(record, field, value)
    events = []

    class Native:
        def CredReadW(self, target, kind, flags, output):
            ctypes.cast(output, ctypes.POINTER(ctypes.POINTER(credential_type)))[0] = (
                ctypes.pointer(record)
            )
            return 1

        def CredFree(self, pointer):
            events.append("free")

    native._api = Native()
    with pytest.raises(oauth.WindowsOAuthStorageError):
        native.read_generic(oauth.TOKEN_TARGET)
    assert events == ["free"]
    if field not in {"CredentialBlobSize", "CredentialBlob"}:
        assert not any(buffer)


@pytest.mark.parametrize("error", [1168, 5])
def test_native_missing_vs_error(monkeypatch, error):
    native, _ = native_double()
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)

    class Native:
        def CredReadW(self, *args):
            return 0

    native._api = Native()
    if error == 1168:
        assert native.read_generic(oauth.TOKEN_TARGET) is None
    else:
        with pytest.raises(oauth.WindowsOAuthStorageError):
            native.read_generic(oauth.TOKEN_TARGET)


@pytest.mark.parametrize("success", [True, False, "exception"])
def test_native_write_exact_generic_and_cleanup(success):
    native, credential_type = native_double()
    blob = bytearray(b"SECRET")
    calls = []

    class Native:
        def CredWriteW(self, pointer, flags):
            record = ctypes.cast(pointer, ctypes.POINTER(credential_type)).contents
            assert record.Type == 1 and record.Persist == 2 and flags == 0
            assert record.TargetName == oauth.CLIENT_INFO_TARGET
            assert record.CredentialBlobSize == len(blob)
            assert bytes(record.CredentialBlob[: len(blob)]) == b"SECRET"
            calls.append("write")
            if success == "exception":
                raise RuntimeError("SECRET")
            return success

    native._api = Native()
    if success is True:
        native.write_generic(oauth.CLIENT_INFO_TARGET, blob)
    else:
        with pytest.raises(oauth.WindowsOAuthStorageError) as caught:
            native.write_generic(oauth.CLIENT_INFO_TARGET, blob)
        assert "SECRET" not in str(caught.value)
    assert calls == ["write"]
    assert not any(blob)


def test_native_target_and_size_rejected_before_call():
    native, _ = native_double()
    with pytest.raises(oauth.WindowsOAuthStorageError):
        native.read_generic("wrong")
    with pytest.raises(oauth.WindowsOAuthStorageError):
        native.write_generic("wrong", bytearray(b"x"))
    with pytest.raises(oauth.WindowsOAuthStorageSizeError):
        native.write_generic(oauth.TOKEN_TARGET, bytearray(2561))


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def assert_closed(port):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


async def request(
    port,
    target="/callback?code=CODE&state=STATE",
    *,
    method="GET",
    host=None,
    extra="",
    raw=None,
):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    if raw is None:
        raw = (
            f"{method} {target} HTTP/1.1\r\nHost: {host or f'127.0.0.1:{port}'}\r\n"
            f"{extra}\r\n"
        ).encode()
    writer.write(raw)
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


@pytest.mark.parametrize("issuer", [None, "https://issuer.example/path?exact=yes"])
def test_loopback_success_exact_values_and_listener_before_browser(issuer):
    port = free_port()
    order = []

    def bound_opener(url):
        assert url == "https://auth.example/SECRET"
        with socket.socket() as sock:
            with pytest.raises(OSError):
                sock.bind(("127.0.0.1", port))
        order.append("listener")
        return True

    helper = oauth.LoopbackOAuthCallback(
        f"http://127.0.0.1:{port}/callback", browser_opener=bound_opener
    )

    async def scenario():
        await helper.redirect_handler("https://auth.example/SECRET")
        query = "/callback?code=CODE%2B%20&state=%20STATE%2B"
        if issuer is not None:
            from urllib.parse import quote

            query += "&iss=" + quote(issuer, safe="")
        response = await request(port, query)
        result = await helper.callback_handler()
        assert (result.code, result.state, result.iss) == ("CODE+ ", " STATE+", issuer)
        assert "CODE" not in repr(result) + str(result)
        assert b"200 OK" in response
        assert all(
            value not in response
            for value in (b"CODE", b"STATE", b"issuer.example", b"SECRET")
        )
        assert not helper._requests and not helper._writers

    run(scenario())
    assert order == ["listener"]
    assert_closed(port)


@pytest.mark.parametrize(
    "uri",
    [
        "http://localhost:8765/callback",
        "http://0.0.0.0:8765/callback",
        "http://[::1]:8765/callback",
        "http://192.168.1.2:8765/callback",
        "https://127.0.0.1:8765/callback",
        "http://127.0.0.1/callback",
        "http://127.0.0.1:0/callback",
        "http://127.0.0.1:65536/callback",
        "http://127.0.0.1:8765/",
        "http://user@127.0.0.1:8765/callback",
        "http://127.0.0.1:8765/callback?x=1",
        "http://127.0.0.1:8765/callback#",
        "http://127.0.0.1:08765/callback",
        " http://127.0.0.1:8765/callback",
        "http://127.0.0.1:8765/call%62ack",
    ],
)
def test_redirect_configuration_is_exact(uri):
    with pytest.raises(oauth.LoopbackOAuthError):
        oauth.LoopbackOAuthCallback(uri)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"method": "POST"},
        {"method": "HEAD"},
        {"host": "localhost:123"},
        {"host": "127.0.0.1"},
        {"host": "attacker.example:123"},
        {"target": "/wrong?code=CODE&state=STATE"},
        {"target": "/callback/extra?code=CODE&state=STATE"},
        {"target": "http://attacker.example/callback?code=CODE&state=STATE"},
        {"target": "/callback?state=STATE"},
        {"target": "/callback?code=CODE"},
        {"target": "/callback?code=CODE&code=SECOND&state=STATE"},
        {"target": "/callback?code=CODE&state=STATE&state=SECOND"},
        {"target": "/callback?code=CODE&state=STATE&iss=a&iss=b"},
        {"target": "/callback?code=&state=STATE"},
        {"target": "/callback?code=CODE&state="},
        {"target": "/callback?code=CODE&state=STATE&iss="},
        {"target": "/callback?code=%FF&state=STATE"},
        {"target": "/callback?code=%GG&state=STATE"},
        {"target": "/callback?code=CODE&state=STATE#fragment"},
        {"target": "/callback?error=SECRET&error_description=SECRET"},
        {"target": "/callback?code=CODE&state=STATE&error=SECRET"},
        {"target": "/callback?code=CODE&state=STATE&unknown=x"},
        {"target": "/callback?code=" + "x" * 4200 + "&state=STATE"},
        {"extra": "Host: attacker.example\r\n"},
        {"extra": "Content-Length: 1\r\n"},
        {"extra": "Transfer-Encoding: chunked\r\n"},
        {"extra": " folded: invalid\r\n"},
        {"extra": "X-Large: " + "x" * 8200 + "\r\n"},
        {"extra": "".join(f"X-{i}: x\r\n" for i in range(33))},
    ],
)
def test_bad_callback_fails_closed_and_closes_listener(kwargs):
    port = free_port()
    helper = oauth.LoopbackOAuthCallback(
        f"http://127.0.0.1:{port}/callback", browser_opener=lambda _: True
    )

    async def scenario():
        await helper.redirect_handler("https://auth.example")
        response = await request(port, **kwargs)
        with pytest.raises(oauth.LoopbackOAuthError) as caught:
            await helper.callback_handler()
        assert "SECRET" not in str(caught.value)
        assert all(value not in response for value in (b"CODE", b"STATE", b"SECRET"))
        assert b"400 Bad Request" in response

    run(scenario())
    assert_closed(port)


def test_timeout_closes_partial_request_even_without_callback_waiter():
    port = free_port()
    helper = oauth.LoopbackOAuthCallback(
        f"http://127.0.0.1:{port}/callback",
        browser_opener=lambda _: True,
        timeout_seconds=0.05,
    )

    async def scenario():
        await helper.redirect_handler("https://auth.example")
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /callback?code=SECRET")
        await writer.drain()
        flow = helper._flow
        with pytest.raises(oauth.LoopbackOAuthError, match="timed out"):
            await asyncio.wait_for(flow, timeout=2)
        assert await reader.read() == b""
        writer.close()
        await writer.wait_closed()
        assert not helper._writers and not helper._requests

    run(scenario())
    assert_closed(port)


@pytest.mark.parametrize("mode", ["false", "raise", "cancel"])
def test_browser_failure_or_redirect_cancellation_closes_resources(mode):
    port = free_port()
    started = __import__("threading").Event()
    finish = __import__("threading").Event()

    def opener(_):
        started.set()
        if mode == "raise":
            raise RuntimeError("SECRET")
        if mode == "cancel":
            finish.wait(1)
            return True
        return False

    helper = oauth.LoopbackOAuthCallback(
        f"http://127.0.0.1:{port}/callback", browser_opener=opener
    )

    async def scenario():
        task = asyncio.create_task(
            helper.redirect_handler("https://auth.example/SECRET")
        )
        if mode == "cancel":
            await asyncio.to_thread(started.wait, 1)
            task.cancel()
            finish.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(oauth.LoopbackOAuthError) as caught:
                await task
            assert "SECRET" not in str(caught.value)
        assert not helper._lock.locked()

    run(scenario())
    assert_closed(port)


def test_callback_cancellation_and_concurrent_redirect():
    port = free_port()
    calls = []
    helper = oauth.LoopbackOAuthCallback(
        f"http://127.0.0.1:{port}/callback",
        browser_opener=lambda url: calls.append(url) or True,
    )

    async def scenario():
        await helper.redirect_handler("first")
        with pytest.raises(oauth.LoopbackOAuthError, match="already active"):
            await helper.redirect_handler("second")
        task = asyncio.create_task(helper.callback_handler())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert calls == ["first"]
        assert not helper._requests and not helper._writers

    run(scenario())
    assert_closed(port)


def test_bind_failure_does_not_open_browser():
    port = free_port()
    calls = []
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))
        sock.listen()
        helper = oauth.LoopbackOAuthCallback(
            f"http://127.0.0.1:{port}/callback",
            browser_opener=lambda url: calls.append(url) or True,
        )
        with pytest.raises(oauth.LoopbackOAuthError):
            run(helper.redirect_handler("SECRET"))
    assert calls == []


def test_composition_is_inert_and_preserves_existing_factory(monkeypatch):
    from trading_bot.robinhood_mcp import sdk_transport

    captured = {}
    sentinel = object()

    def factory(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(sdk_transport, "create_robinhood_oauth_factory", factory)
    monkeypatch.setattr(oauth, "WindowsCredentialApi", Api)
    result = oauth.create_windows_robinhood_oauth_factory(
        redirect_uri="http://127.0.0.1:8765/callback"
    )
    assert result is sentinel
    assert isinstance(captured["storage"], oauth.WindowsOAuthStorage)
    assert captured["storage"]._native.reads == []
    assert captured["storage"]._native.writes == []
    assert (
        captured["redirect_handler"].__self__ is captured["callback_handler"].__self__
    )


def test_lazy_dependency_missing_is_sanitized(monkeypatch):
    monkeypatch.setitem(sys.modules, "mcp.shared.auth", None)
    storage = oauth.WindowsOAuthStorage(native_api=Api())
    with pytest.raises(oauth.WindowsOAuthStorageError, match="optional dependency"):
        run(storage.get_tokens())


def test_optional_real_sdk_full_models(monkeypatch):
    monkeypatch.delitem(sys.modules, "mcp.shared.auth")
    auth = pytest.importorskip("mcp.shared.auth")
    api = Api()
    storage = oauth.WindowsOAuthStorage(native_api=api)
    client = auth.OAuthClientInformationFull(
        client_id="id",
        client_secret="SECRET",
        issuer="https://issuer.example",
        redirect_uris=["http://127.0.0.1:8765/callback"],
        contacts=["operator@example.com"],
        client_id_issued_at=42,
        token_endpoint_auth_method="client_secret_post",
    )
    token = auth.OAuthToken(
        access_token="ACCESS", refresh_token="REFRESH", expires_in=600, scope="read"
    )
    run(storage.set_client_info(client))
    run(storage.set_tokens(token))
    assert run(storage.get_client_info()).model_dump(mode="json") == client.model_dump(
        mode="json"
    )
    assert run(storage.get_tokens()).model_dump(mode="json") == token.model_dump(
        mode="json"
    )
    _, _, result_model = oauth._models()
    result = result_model(code="CODE", state="STATE", iss="https://issuer.example/")
    assert isinstance(result, auth.AuthorizationCodeResult)
    assert result.iss == "https://issuer.example/"
    assert "SECRET" not in repr(run(storage.get_client_info()))


def test_generic_blob_exact_byte_limit_and_invalid_model_no_write():
    api = Api()
    storage = oauth.WindowsOAuthStorage(native_api=api)
    run(storage.set_client_info(Client(client_id="id")))
    overhead = len(Token(access_token="").model_dump_json().encode())
    value = Token(access_token="x" * (2560 - overhead))
    run(storage.set_tokens(value))
    assert len(api.records[oauth.TOKEN_TARGET]) == 2560
    assert run(storage.get_tokens()).access_token == value.access_token
    api.writes.clear()
    with pytest.raises(oauth.WindowsOAuthStorageSizeError):
        run(storage.set_tokens(Token(access_token=value.access_token + "x")))
    with pytest.raises(oauth.WindowsOAuthStorageError):
        run(storage.set_tokens(Client(client_id="wrong")))
    assert api.writes == []


def test_empty_sdk_fields_are_invalid_even_if_schema_accepts_them():
    # Deliberately emulate a permissive Pydantic string field.
    class PermissiveToken(Token):
        required = ()

    api = Api()
    storage = oauth.WindowsOAuthStorage(native_api=api)
    run(storage.set_client_info(Client(client_id="id")))
    with pytest.raises(oauth.WindowsOAuthStorageError):
        run(storage.set_tokens(PermissiveToken(access_token="")))


@pytest.mark.parametrize("failure", ["zero", "free", "read"])
def test_native_cleanup_failures_are_sanitized_and_allocation_freed(failure):
    native, credential_type = native_double()
    buffer = (ctypes.c_ubyte * 6)(*b"SECRET")
    record = credential_type(
        Type=1,
        TargetName=oauth.TOKEN_TARGET,
        Persist=2,
        CredentialBlobSize=6,
        CredentialBlob=buffer,
    )
    freed = []

    class Native:
        def CredReadW(self, target, kind, flags, output):
            ctypes.cast(output, ctypes.POINTER(ctypes.POINTER(credential_type)))[0] = (
                ctypes.pointer(record)
            )
            if failure == "read":
                raise RuntimeError("SECRET")
            return 1

        def CredFree(self, pointer):
            freed.append(pointer)
            if failure == "free":
                raise RuntimeError("SECRET")

    def fail_zero(address, size):
        raise RuntimeError("SECRET")

    native._api = Native()
    if failure == "zero":
        native._zero_memory = fail_zero
    with pytest.raises(oauth.WindowsOAuthStorageError) as caught:
        native.read_generic(oauth.TOKEN_TARGET)
    assert "SECRET" not in str(caught.value)
    assert len(freed) == 1
    if failure == "free":
        assert not any(buffer)


@pytest.mark.parametrize(
    "address,size", [(0, 1), (oauth._MAX_ADDRESS, 2), (1, 2561), (1, 0)]
)
def test_invalid_native_range_cannot_be_dereferenced(address, size):
    assert oauth._blob_range(address, size) is False


@pytest.mark.parametrize(
    "target",
    [
        "/callback?code=CODE&state=STATE#",
        "/callback?code=CO\tDE&state=STATE",
        "/callback?code=CODE&state=%00",
        "/callback?code=CODE&state=STATE&iss=%0A",
    ],
)
def test_callback_rejects_parser_normalization_and_control_characters(target):
    port = free_port()
    helper = oauth.LoopbackOAuthCallback(
        f"http://127.0.0.1:{port}/callback", browser_opener=lambda _: True
    )

    async def scenario():
        await helper.redirect_handler("auth")
        response = await request(port, target)
        with pytest.raises(oauth.LoopbackOAuthError):
            await helper.callback_handler()
        assert b"400 Bad Request" in response

    run(scenario())
    assert_closed(port)


def test_concurrent_callback_waiters_are_rejected():
    port = free_port()
    helper = oauth.LoopbackOAuthCallback(
        f"http://127.0.0.1:{port}/callback", browser_opener=lambda _: True
    )

    async def scenario():
        await helper.redirect_handler("auth")
        first = asyncio.create_task(helper.callback_handler())
        await asyncio.sleep(0)
        with pytest.raises(oauth.LoopbackOAuthError):
            await helper.callback_handler()
        await request(port)
        assert (await first).state == "STATE"

    run(scenario())
    assert_closed(port)


def test_browser_timeout_closes_listener():
    import threading

    finish = threading.Event()
    port = free_port()
    helper = oauth.LoopbackOAuthCallback(
        f"http://127.0.0.1:{port}/callback",
        browser_opener=lambda _: finish.wait(0.2),
        timeout_seconds=0.02,
    )

    async def scenario():
        try:
            with pytest.raises(oauth.LoopbackOAuthError):
                await helper.redirect_handler("auth")
            assert helper._server is None
            assert not helper._lock.locked()
            assert_closed(port)
        finally:
            finish.set()

    run(scenario())


def test_invalid_client_fails_closed_even_when_no_tokens_exist():
    api = Api()
    api.records[oauth.CLIENT_INFO_TARGET] = b"malformed SECRET"
    storage = oauth.WindowsOAuthStorage(native_api=api)
    with pytest.raises(oauth.WindowsOAuthStorageError):
        run(storage.get_tokens())


@pytest.mark.parametrize(
    "timeout", [0, -1, 301, float("inf"), float("nan"), True, "10"]
)
def test_timeout_configuration_is_bounded(timeout):
    with pytest.raises(oauth.LoopbackOAuthError):
        oauth.LoopbackOAuthCallback(
            "http://127.0.0.1:8765/callback", timeout_seconds=timeout
        )


def test_storage_construction_does_not_import_optional_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "mcp.shared.auth", None)
    api = Api()
    storage = oauth.WindowsOAuthStorage(native_api=api)
    assert storage._native is api
    assert not api.reads and not api.writes
