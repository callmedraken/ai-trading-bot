from __future__ import annotations

import ctypes
import hashlib
import os
from datetime import UTC, date, datetime
from inspect import signature
from types import SimpleNamespace

import pytest

import trading_bot.runtime.windows_effectful_capture_child as child_module
from trading_bot.domain import Symbol
from trading_bot.market_data import MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
from trading_bot.runtime.windows_effectful_capture import (
    ProductionCaptureRequest,
    bind_production_capture_plan,
    build_production_provider_launch_plan,
    prepare_production_capture_plan,
)
from trading_bot.runtime.windows_effectful_capture_native import (
    C3_REQUEST_HANDLE_ARGUMENT,
    C3_RESULT_HANDLE_ARGUMENT,
    C3_STAGING_HANDLE_ARGUMENT,
    ERROR_BROKEN_PIPE,
    CtypesWindowsEffectfulCaptureChildIoApi,
    WindowsEffectfulCaptureNativeError,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    MAX_C3_CHILD_REQUEST_BYTES,
    MAX_C3_CHILD_RESULT_BYTES,
    ChildCleanupStatus,
    ChildResultClassification,
    IsolatedCaptureChildResult,
    ProviderAttemptFenceState,
    build_isolated_capture_child_request,
    serialize_isolated_capture_child_request,
    serialize_isolated_capture_child_result,
)

_REQUEST_HANDLE = 11
_RESULT_HANDLE = 12
_STAGING_HANDLE = 13
_ARGS = (
    C3_REQUEST_HANDLE_ARGUMENT,
    str(_REQUEST_HANDLE),
    C3_RESULT_HANDLE_ARGUMENT,
    str(_RESULT_HANDLE),
    C3_STAGING_HANDLE_ARGUMENT,
    str(_STAGING_HANDLE),
)


def _request_bytes() -> bytes:
    request = ProductionCaptureRequest(
        ordered_universe=(Symbol("AAPL"), Symbol("MSFT")),
        request_window_start_date=date(2026, 8, 17),
        request_window_end_date=date(2026, 8, 17),
        target_session_date=date(2026, 8, 18),
    )
    plan = prepare_production_capture_plan(
        request, datetime(2026, 8, 18, 14, tzinfo=UTC)
    )
    bound = bind_production_capture_plan(plan, "11111111-1111-4111-8111-111111111111")
    launch = build_production_provider_launch_plan(bound)
    child_request = build_isolated_capture_child_request(
        launch,
        "33333333-3333-4333-8333-333333333333",
        approved_account_sid="S-1-5-21-111-222-333-1001",
        release_manifest_sha256="11" * 32,
    )
    return serialize_isolated_capture_child_request(child_request)


def _result(request_bytes: bytes) -> IsolatedCaptureChildResult:
    return IsolatedCaptureChildResult(
        reservation_id="11111111-1111-4111-8111-111111111111",
        execution_id="33333333-3333-4333-8333-333333333333",
        child_request_sha256=hashlib.sha256(request_bytes).hexdigest(),
        fence_state=ProviderAttemptFenceState.ENTERED,
        classification=ChildResultClassification.INTERNAL_FAILED,
        cleanup_status=ChildCleanupStatus.COMPLETE,
    )


class _FakeChildIo:
    def __init__(
        self,
        request_payload: bytes,
        *,
        read_chunk: int = 7,
        write_chunk: int | None = None,
        read_error_at_eof: bool = False,
        fail_result_after: int | None = None,
        invalid_write_count: object | None = None,
        fail_flush: bool = False,
        fail_close: frozenset[int] = frozenset(),
    ) -> None:
        self.request_payload = request_payload
        self.read_chunk = read_chunk
        self.write_chunk = write_chunk
        self.read_error_at_eof = read_error_at_eof
        self.fail_result_after = fail_result_after
        self.invalid_write_count = invalid_write_count
        self.fail_flush = fail_flush
        self.fail_close = fail_close
        self.events: list[str] = []
        self.result = bytearray()
        self.staging = bytearray()
        self.closed: list[int] = []
        self._read_offset = 0

    def read_file(self, handle: int, max_bytes: int) -> bytes:
        assert handle == _REQUEST_HANDLE
        self.events.append(f"read:{max_bytes}")
        if self._read_offset < len(self.request_payload):
            count = min(
                self.read_chunk,
                max_bytes,
                len(self.request_payload) - self._read_offset,
            )
            chunk = self.request_payload[self._read_offset : self._read_offset + count]
            self._read_offset += count
            return chunk
        if self.read_error_at_eof:
            raise WindowsEffectfulCaptureNativeError("ReadFile failed")
        self.events.append("eof")
        return b""

    def write_file(self, handle: int, payload: bytes) -> int:
        self.events.append(f"write:{handle}:{len(payload)}")
        if self.invalid_write_count is not None:
            return self.invalid_write_count  # type: ignore[return-value]
        target = self.result if handle == _RESULT_HANDLE else self.staging
        if handle == _RESULT_HANDLE and (
            self.fail_result_after is not None and len(target) >= self.fail_result_after
        ):
            raise WindowsEffectfulCaptureNativeError("WriteFile failed")
        count = (
            len(payload)
            if self.write_chunk is None
            else min(self.write_chunk, len(payload))
        )
        target.extend(payload[:count])
        return count

    def flush_file_buffers(self, handle: int) -> None:
        assert handle == _STAGING_HANDLE
        self.events.append("flush")
        if self.fail_flush:
            raise WindowsEffectfulCaptureNativeError("FlushFileBuffers failed")

    def close_handle(self, handle: int) -> None:
        self.events.append(f"close:{handle}")
        self.closed.append(handle)
        if handle in self.fail_close:
            raise WindowsEffectfulCaptureNativeError("CloseHandle failed")


class _FakeAttempt:
    def __init__(
        self,
        result: IsolatedCaptureChildResult,
        staging_writer: object,
        events: list[str],
    ) -> None:
        self._result = result
        self.staging_writer = staging_writer
        self.events = events
        self.run_count = 0

    def run(self) -> IsolatedCaptureChildResult:
        self.run_count += 1
        self.events.append("run")
        return self._result


class _Factory:
    def __init__(self, result: IsolatedCaptureChildResult, events: list[str]) -> None:
        self.result = result
        self.events = events
        self.request_bytes: bytes | None = None
        self.attempt: _FakeAttempt | None = None

    def __call__(self, request_bytes: bytes, *, staging_writer: object) -> _FakeAttempt:
        self.events.append("factory")
        self.request_bytes = request_bytes
        self.attempt = _FakeAttempt(self.result, staging_writer, self.events)
        return self.attempt


def test_strict_handle_parser_accepts_only_three_distinct_canonical_values() -> None:
    handles = child_module._parse_child_bootstrap_handles(
        (
            C3_STAGING_HANDLE_ARGUMENT,
            "13",
            C3_REQUEST_HANDLE_ARGUMENT,
            "11",
            C3_RESULT_HANDLE_ARGUMENT,
            "12",
        )
    )

    assert (
        handles.request_read,
        handles.result_write,
        handles.staging_write,
    ) == (11, 12, 13)


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        _ARGS[:-1],
        (*_ARGS, "extra"),
        ("--unknown", "11", *_ARGS[2:]),
        (
            C3_REQUEST_HANDLE_ARGUMENT,
            "11",
            C3_REQUEST_HANDLE_ARGUMENT,
            "12",
            *_ARGS[4:],
        ),
        (C3_REQUEST_HANDLE_ARGUMENT, "0", *_ARGS[2:]),
        (C3_REQUEST_HANDLE_ARGUMENT, "-1", *_ARGS[2:]),
        (C3_REQUEST_HANDLE_ARGUMENT, "+1", *_ARGS[2:]),
        (C3_REQUEST_HANDLE_ARGUMENT, "01", *_ARGS[2:]),
        (C3_REQUEST_HANDLE_ARGUMENT, " 1", *_ARGS[2:]),
        (C3_REQUEST_HANDLE_ARGUMENT, "1.0", *_ARGS[2:]),
        (C3_REQUEST_HANDLE_ARGUMENT, "x", *_ARGS[2:]),
        (
            C3_REQUEST_HANDLE_ARGUMENT,
            str(child_module._MAX_UINT_PTR + 1),
            *_ARGS[2:],
        ),
        (C3_REQUEST_HANDLE_ARGUMENT, "12", *_ARGS[2:]),
    ],
)
def test_strict_handle_parser_rejects_every_other_shape(
    arguments: tuple[str, ...],
) -> None:
    with pytest.raises(child_module.WindowsEffectfulCaptureChildError):
        child_module._parse_child_bootstrap_handles(arguments)


def test_partial_request_and_result_io_preserve_exact_canonical_bytes() -> None:
    request_bytes = _request_bytes()
    io = _FakeChildIo(request_bytes, read_chunk=3, write_chunk=5)
    factory = _Factory(_result(request_bytes), io.events)

    exit_code = child_module.run_isolated_capture_child_bootstrap_for_test(
        _ARGS, native_io=io, attempt_factory=factory
    )

    expected_result = serialize_isolated_capture_child_result(_result(request_bytes))
    assert exit_code == child_module.C3_CHILD_BOOTSTRAP_EXIT_SUCCESS
    assert factory.request_bytes == request_bytes
    assert factory.attempt is not None and factory.attempt.run_count == 1
    assert bytes(io.result) == expected_result
    assert io.events.index("eof") < io.events.index("close:11")
    assert io.events.index("close:11") < io.events.index("factory")
    assert io.events.index("factory") < io.events.index("run")
    assert io.closed == [_REQUEST_HANDLE, _RESULT_HANDLE, _STAGING_HANDLE]


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b'{"truncated":',
        b" " + _request_bytes(),
        b"x" * (MAX_C3_CHILD_REQUEST_BYTES + 1),
    ],
)
def test_pre_admission_failure_emits_no_result_and_cleans_all_handles(
    payload: bytes, capsys: pytest.CaptureFixture[str]
) -> None:
    io = _FakeChildIo(payload)
    factory = _Factory(_result(_request_bytes()), io.events)

    exit_code = child_module.run_isolated_capture_child_bootstrap_for_test(
        _ARGS, native_io=io, attempt_factory=factory
    )

    assert exit_code == child_module.C3_CHILD_BOOTSTRAP_EXIT_FAILED
    assert factory.request_bytes is None
    assert io.result == b""
    assert io.closed == [_REQUEST_HANDLE, _RESULT_HANDLE, _STAGING_HANDLE]
    assert capsys.readouterr() == ("", "")


def test_exact_request_is_not_admitted_until_eof_is_proved() -> None:
    request_bytes = _request_bytes()
    io = _FakeChildIo(request_bytes, read_error_at_eof=True)
    factory = _Factory(_result(request_bytes), io.events)

    exit_code = child_module.run_isolated_capture_child_bootstrap_for_test(
        _ARGS, native_io=io, attempt_factory=factory
    )

    assert exit_code == child_module.C3_CHILD_BOOTSTRAP_EXIT_FAILED
    assert factory.request_bytes is None
    assert io.result == b""


def test_oversized_result_is_rejected_before_any_result_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_bytes = _request_bytes()
    io = _FakeChildIo(request_bytes)
    factory = _Factory(_result(request_bytes), io.events)
    monkeypatch.setattr(
        child_module,
        "serialize_isolated_capture_child_result",
        lambda _value: b"x" * (MAX_C3_CHILD_RESULT_BYTES + 1),
    )

    exit_code = child_module.run_isolated_capture_child_bootstrap_for_test(
        _ARGS, native_io=io, attempt_factory=factory
    )

    assert exit_code == child_module.C3_CHILD_BOOTSTRAP_EXIT_FAILED
    assert not any(event.startswith("write:12:") for event in io.events)
    assert io.result == b""


@pytest.mark.parametrize("invalid_count", [0, True, 100_000])
def test_invalid_result_write_count_fails_without_replacement(
    invalid_count: object,
) -> None:
    request_bytes = _request_bytes()
    io = _FakeChildIo(request_bytes, invalid_write_count=invalid_count)
    factory = _Factory(_result(request_bytes), io.events)

    exit_code = child_module.run_isolated_capture_child_bootstrap_for_test(
        _ARGS, native_io=io, attempt_factory=factory
    )

    assert exit_code == child_module.C3_CHILD_BOOTSTRAP_EXIT_FAILED
    assert sum(event.startswith("write:12:") for event in io.events) == 1
    assert io.result == b""


def test_partial_result_transport_failure_never_emits_a_second_result() -> None:
    request_bytes = _request_bytes()
    io = _FakeChildIo(
        request_bytes,
        write_chunk=5,
        fail_result_after=5,
    )
    factory = _Factory(_result(request_bytes), io.events)

    exit_code = child_module.run_isolated_capture_child_bootstrap_for_test(
        _ARGS, native_io=io, attempt_factory=factory
    )

    assert exit_code == child_module.C3_CHILD_BOOTSTRAP_EXIT_FAILED
    assert len(io.result) == 5
    assert sum(event.startswith("write:12:") for event in io.events) == 2


def test_inherited_staging_writer_completes_write_then_flushes_without_a_path() -> None:
    io = _FakeChildIo(b"", write_chunk=3)
    writer = child_module._InheritedHandleSnapshotStagingWriter(_STAGING_HANDLE, io)

    writer.write(b"canonical-snapshot")
    writer.flush()

    assert bytes(io.staging) == b"canonical-snapshot"
    assert io.events[-1] == "flush"
    assert not hasattr(writer, "path")


def test_inherited_staging_writer_enforces_artifact_bound_before_write() -> None:
    io = _FakeChildIo(b"")
    writer = child_module._InheritedHandleSnapshotStagingWriter(_STAGING_HANDLE, io)

    with pytest.raises(child_module.WindowsEffectfulCaptureChildError):
        writer.write(b"x" * (MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES + 1))

    assert not any(event.startswith("write:13:") for event in io.events)


def test_inherited_staging_writer_accepts_exact_artifact_bound() -> None:
    io = _FakeChildIo(b"")
    writer = child_module._InheritedHandleSnapshotStagingWriter(_STAGING_HANDLE, io)
    payload = b"x" * MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES

    writer.write(payload)
    writer.flush()

    assert len(io.staging) == MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
    assert io.events[-1] == "flush"


@pytest.mark.parametrize(
    "failed_handle", [_REQUEST_HANDLE, _RESULT_HANDLE, _STAGING_HANDLE]
)
def test_cleanup_attempts_each_owned_handle_once_when_any_close_fails(
    failed_handle: int,
) -> None:
    request_bytes = _request_bytes()
    io = _FakeChildIo(request_bytes, fail_close=frozenset({failed_handle}))
    factory = _Factory(_result(request_bytes), io.events)

    exit_code = child_module.run_isolated_capture_child_bootstrap_for_test(
        _ARGS, native_io=io, attempt_factory=factory
    )

    assert exit_code == child_module.C3_CHILD_BOOTSTRAP_EXIT_FAILED
    assert io.closed == [_REQUEST_HANDLE, _RESULT_HANDLE, _STAGING_HANDLE]
    assert all(io.closed.count(handle) == 1 for handle in io.closed)
    if failed_handle == _REQUEST_HANDLE:
        assert factory.request_bytes is None


def test_production_main_uses_only_internal_factory_and_suppresses_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    request_bytes = _request_bytes()
    io = _FakeChildIo(request_bytes)
    factory = _Factory(_result(request_bytes), io.events)
    monkeypatch.setattr(
        child_module, "CtypesWindowsEffectfulCaptureChildIoApi", lambda: io
    )
    monkeypatch.setattr(
        child_module, "_build_production_isolated_capture_child_attempt", factory
    )

    assert child_module.main(_ARGS) == child_module.C3_CHILD_BOOTSTRAP_EXIT_SUCCESS
    assert factory.request_bytes == request_bytes
    assert tuple(signature(child_module.main).parameters) == ("argv",)
    assert capsys.readouterr() == ("", "")

    failing_io = _FakeChildIo(b"secret C:\\path HANDLE=99")
    monkeypatch.setattr(
        child_module, "CtypesWindowsEffectfulCaptureChildIoApi", lambda: failing_io
    )
    assert child_module.main(_ARGS) == child_module.C3_CHILD_BOOTSTRAP_EXIT_FAILED
    assert capsys.readouterr() == ("", "")


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows ctypes bindings")
def test_ctypes_child_io_has_exact_signatures_and_broken_pipe_eof() -> None:
    api = CtypesWindowsEffectfulCaptureChildIoApi()
    from ctypes import wintypes

    expected_io_args = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    assert api._k32.ReadFile.argtypes == expected_io_args
    assert api._k32.WriteFile.argtypes == expected_io_args
    assert api._k32.ReadFile.restype is wintypes.BOOL
    assert api._k32.WriteFile.restype is wintypes.BOOL
    assert api._k32.FlushFileBuffers.argtypes == [wintypes.HANDLE]
    assert api._k32.FlushFileBuffers.restype is wintypes.BOOL
    assert api._k32.CloseHandle.argtypes == [wintypes.HANDLE]
    assert api._k32.CloseHandle.restype is wintypes.BOOL

    def broken_pipe(*_args: object) -> bool:
        ctypes.set_last_error(ERROR_BROKEN_PIPE)
        return False

    api._k32 = SimpleNamespace(ReadFile=broken_pipe)
    assert api.read_file(_REQUEST_HANDLE, 1) == b""


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows ctypes bindings")
def test_ctypes_child_io_sanitizes_non_eof_read_failure() -> None:
    api = CtypesWindowsEffectfulCaptureChildIoApi()

    def access_denied(*_args: object) -> bool:
        ctypes.set_last_error(5)
        return False

    api._k32 = SimpleNamespace(ReadFile=access_denied)
    with pytest.raises(
        WindowsEffectfulCaptureNativeError,
        match=r"^Windows operation failed: ReadFile \(win32=5\)$",
    ):
        api.read_file(_REQUEST_HANDLE, 1)
