from __future__ import annotations

import copy
import ctypes
import os
import pickle

import pytest

from trading_bot.runtime.windows_effectful_capture_native import (
    C3_CREATE_PROCESS_FLAGS,
    C3_OVERLAPPED_CANCEL_SETTLEMENT_TIMEOUT_MS,
    C3_REQUEST_HANDLE_ARGUMENT,
    C3_RESULT_HANDLE_ARGUMENT,
    C3_STAGING_HANDLE_ARGUMENT,
    CREATE_NO_WINDOW,
    CREATE_SUSPENDED,
    CREATE_UNICODE_ENVIRONMENT,
    EXTENDED_STARTUPINFO_PRESENT,
    FILE_FLAG_FIRST_PIPE_INSTANCE,
    FILE_FLAG_OVERLAPPED,
    PIPE_REJECT_REMOTE_CLIENTS,
    C3NativeWaitStatus,
    CtypesWindowsEffectfulCaptureNativeApi,
    NativeCreatedProcess,
    NativeFileIdentity,
    NativeOverlappedCompletion,
    NativePipePair,
    NativeStagingObject,
    SuspendedCaptureChild,
    WindowsEffectfulCaptureNativeError,
    WindowsEffectfulCaptureNativeUnsupportedError,
    build_c3_child_environment,
    create_suspended_capture_child_for_test,
    deliver_canonical_child_request,
    resume_suspended_capture_child,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    MAX_C3_CHILD_REQUEST_BYTES,
    MAX_C3_CHILD_RESULT_BYTES,
)

_APPLICATION = r"F:\AITradingBot\runtime\python.exe"
_CURRENT = r"F:\AITradingBot\runtime"
_TEMP = r"F:\AITradingBot\temp"
_STAGING = r"F:\AITradingBot\Authority\capture-output\.c3-capture-test.staging"
_PARENT_ENV = {
    "SystemRoot": r"C:\Windows",
    "WINDIR": r"C:\Windows",
    "PATH": r"C:\unsafe",
    "PYTHONPATH": r"F:\dev",
    "HTTPS_PROXY": "http://proxy.invalid",
    "APCA_API_KEY_ID": "must-not-pass",
}


class FakeNativeApi:
    def __init__(
        self,
        *,
        fail_at: str | None = None,
        write_chunk: int | None = None,
        write_wait_status: C3NativeWaitStatus = C3NativeWaitStatus.IO_COMPLETED,
        cancel_settles: bool = True,
        resume_result: int = 1,
    ) -> None:
        self.fail_at = fail_at
        self.write_chunk = write_chunk
        self.write_wait_status = write_wait_status
        self.cancel_settles = cancel_settles
        self.resume_result = resume_result
        self.events: list[str] = []
        self.written = bytearray()
        self.process_call: dict[str, object] | None = None
        self.staging_object: NativeStagingObject | None = None
        self._pipe_count = 0

    def _event(self, value: str) -> None:
        self.events.append(value)
        if self.fail_at == value:
            raise RuntimeError("injected native failure")

    def create_job_object(self) -> int:
        self._event("create_job")
        return 100

    def set_job_limits(self, job_handle: int) -> None:
        assert job_handle == 100
        self._event("set_job_limits")

    def create_request_pipe(self, buffer_size: int) -> NativePipePair:
        self._pipe_count += 1
        self._event(f"create_request_pipe:{buffer_size}")
        return NativePipePair(101, 102)

    def create_result_pipe(self, buffer_size: int) -> NativePipePair:
        self._pipe_count += 1
        self._event(f"create_result_pipe:{buffer_size}")
        return NativePipePair(103, 104)

    def set_handle_inheritable(self, handle: int, inheritable: bool) -> None:
        self._event(f"inherit:{handle}:{inheritable}")

    def create_staging_file(self, path: str) -> NativeStagingObject:
        assert path == _STAGING
        self._event("create_staging")
        self.staging_object = NativeStagingObject(
            105, 108, NativeFileIdentity(7, b"i" * 16), path
        )
        return self.staging_object

    def get_file_identity(self, handle: int) -> NativeFileIdentity:
        return NativeFileIdentity(7, b"i" * 16)

    def read_artifact_file(self, handle: int, max_bytes: int) -> bytes:
        raise AssertionError("artifact verification was not expected")

    def reject_casefold_collisions(
        self, directory: str, names: tuple[str, ...]
    ) -> None:
        raise AssertionError("artifact verification was not expected")

    def publish_staging_link(self, staging_handle: int, final_path: str) -> None:
        raise AssertionError("artifact verification was not expected")

    def open_final_artifact(self, path: str):
        raise AssertionError("artifact verification was not expected")

    def delete_staging_link(self, staging_handle: int) -> None:
        raise AssertionError("artifact verification was not expected")

    def create_suspended_process(self, **kwargs: object) -> NativeCreatedProcess:
        self.process_call = dict(kwargs)
        self._event("create_process")
        return NativeCreatedProcess(1234, 5678, 106, 107)

    def close_handle(self, handle: int) -> None:
        self._event(f"close:{handle}")

    def begin_overlapped_write(self, handle: int, payload: bytes) -> object:
        assert handle == 102
        self._event(f"write:{len(payload)}")
        return payload

    def begin_overlapped_read(self, handle: int, max_bytes: int) -> object:
        raise AssertionError("result observation was not expected")

    def wait_overlapped_or_process(
        self, operation: object, process_handle: int | None, timeout_ms: int
    ) -> C3NativeWaitStatus:
        assert process_handle is None
        assert timeout_ms > 0
        return self.write_wait_status

    def complete_overlapped(self, operation: object) -> NativeOverlappedCompletion:
        assert type(operation) is bytes
        payload = operation
        count = (
            len(payload)
            if self.write_chunk is None
            else min(self.write_chunk, len(payload))
        )
        self.written.extend(payload[:count])
        return NativeOverlappedCompletion(count, b"", False)

    def cancel_and_settle_overlapped(self, operation: object, timeout_ms: int) -> bool:
        self._event(f"cancel:{timeout_ms}")
        return self.cancel_settles

    def quarantine_overlapped(self, operation: object) -> None:
        self._event("quarantine")

    def wait_process(self, process_handle: int, timeout_ms: int) -> C3NativeWaitStatus:
        raise AssertionError("process wait was not expected")

    def get_exit_code_process(self, process_handle: int) -> int:
        raise AssertionError("process exit was not expected")

    def terminate_job_object(self, job_handle: int) -> None:
        self._event(f"terminate:{job_handle}")

    def resume_thread(self, thread_handle: int) -> int:
        assert thread_handle == 107
        self._event("resume:107")
        return self.resume_result


def _create(api: FakeNativeApi) -> SuspendedCaptureChild:
    return create_suspended_capture_child_for_test(
        application_name=_APPLICATION,
        arguments=("-m", "trading_bot.runtime.c3_child"),
        current_directory=_CURRENT,
        controlled_temp_directory=_TEMP,
        staging_path=_STAGING,
        parent_environment=_PARENT_ENV,
        native_api=api,
    )


def test_environment_is_exact_allowlist() -> None:
    environment = build_c3_child_environment(_PARENT_ENV, _TEMP)

    assert environment == {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "TEMP": _TEMP,
        "TMP": _TEMP,
        "PYTHONUTF8": "1",
    }
    assert "PATH" not in environment
    assert "PYTHONPATH" not in environment
    assert "HTTPS_PROXY" not in environment
    assert "APCA_API_KEY_ID" not in environment


def test_containment_prepares_job_channels_staging_and_suspended_process() -> None:
    api = FakeNativeApi()

    child = _create(api)

    assert child.process_id == 1234
    assert child.thread_id == 5678
    assert not child.closed
    assert api.events == [
        "create_job",
        "set_job_limits",
        f"create_request_pipe:{MAX_C3_CHILD_REQUEST_BYTES}",
        f"create_result_pipe:{MAX_C3_CHILD_RESULT_BYTES}",
        "create_staging",
        "create_process",
        "close:101",
        "close:104",
        "close:108",
    ]

    call = api.process_call
    assert call is not None
    assert call["application_name"] == _APPLICATION
    assert call["current_directory"] == _CURRENT
    assert call["inherited_handles"] == (101, 104, 108)
    assert call["job_handle"] == 100
    assert call["creation_flags"] == C3_CREATE_PROCESS_FLAGS
    assert call["inherit_handles"] is True
    assert call["environment"] == build_c3_child_environment(_PARENT_ENV, _TEMP)
    assert call["arguments"] == (
        "-m",
        "trading_bot.runtime.c3_child",
        C3_REQUEST_HANDLE_ARGUMENT,
        "101",
        C3_RESULT_HANDLE_ARGUMENT,
        "104",
        C3_STAGING_HANDLE_ARGUMENT,
        "108",
    )
    assert api.staging_object is not None
    assert api.staging_object.parent_inheritable is False
    assert api.staging_object.child_access_mask == 0x40000000
    assert api.staging_object.identity == NativeFileIdentity(7, b"i" * 16)


def test_flags_are_exact_and_have_no_breakaway_bits() -> None:
    assert C3_CREATE_PROCESS_FLAGS == (
        CREATE_SUSPENDED
        | EXTENDED_STARTUPINFO_PRESENT
        | CREATE_UNICODE_ENVIRONMENT
        | CREATE_NO_WINDOW
    )
    assert C3_CREATE_PROCESS_FLAGS & 0x01000000 == 0
    assert C3_CREATE_PROCESS_FLAGS & 0x04000000 == 0


def test_parent_retains_only_parent_endpoints_and_job_closes_last() -> None:
    api = FakeNativeApi()
    child = _create(api)

    child.close()
    child.close()

    assert child.closed
    assert api.events[-6:] == [
        "close:102",
        "close:103",
        "close:105",
        "close:107",
        "close:106",
        "close:100",
    ]
    assert api.events.count("close:100") == 1


def test_request_is_completely_written_before_writer_close_and_resume_once() -> None:
    api = FakeNativeApi(write_chunk=3)
    child = _create(api)

    deliver_canonical_child_request(child, b"canonical-request")
    resume_suspended_capture_child(child)

    assert bytes(api.written) == b"canonical-request"
    assert api.events[-8:] == [
        "write:17",
        "write:14",
        "write:11",
        "write:8",
        "write:5",
        "write:2",
        "close:102",
        "resume:107",
    ]
    with pytest.raises(WindowsEffectfulCaptureNativeError, match="already attempted"):
        resume_suspended_capture_child(child)
    assert api.events.count("resume:107") == 1
    child.close()


@pytest.mark.parametrize("resume_result", [0xFFFFFFFF, 0, 2])
def test_failed_or_unexpected_resume_return_is_one_shot(resume_result: int) -> None:
    api = FakeNativeApi(resume_result=resume_result)
    child = _create(api)
    deliver_canonical_child_request(child, b"request")

    with pytest.raises(WindowsEffectfulCaptureNativeError):
        resume_suspended_capture_child(child)
    with pytest.raises(WindowsEffectfulCaptureNativeError, match="already attempted"):
        resume_suspended_capture_child(child)

    assert api.events.count("resume:107") == 1
    child.close()


def test_request_failure_closes_writer_and_cannot_resume() -> None:
    api = FakeNativeApi(fail_at="write:7")
    child = _create(api)

    with pytest.raises(WindowsEffectfulCaptureNativeError, match="delivery failed"):
        deliver_canonical_child_request(child, b"request")
    with pytest.raises(WindowsEffectfulCaptureNativeError, match="closed"):
        resume_suspended_capture_child(child)

    assert "close:102" in api.events
    assert api.events[-1] == "close:100"
    assert "resume:107" not in api.events
    child.close()


def test_timed_out_request_is_quarantined_and_suspended_child_is_contained() -> None:
    api = FakeNativeApi(
        write_wait_status=C3NativeWaitStatus.TIMEOUT,
        cancel_settles=False,
    )
    child = _create(api)

    with pytest.raises(WindowsEffectfulCaptureNativeError, match="delivery failed"):
        deliver_canonical_child_request(child, b"request")

    assert child.closed
    assert api.events.count(f"cancel:{C3_OVERLAPPED_CANCEL_SETTLEMENT_TIMEOUT_MS}") == 1
    assert api.events.count("quarantine") == 1
    assert "close:102" not in api.events
    assert api.events[-1] == "close:100"
    assert "resume:107" not in api.events


def test_named_pipe_hardening_flags_are_fixed() -> None:
    assert FILE_FLAG_OVERLAPPED == 0x40000000
    assert FILE_FLAG_FIRST_PIPE_INSTANCE == 0x00080000
    assert PIPE_REJECT_REMOTE_CLIENTS == 0x00000008
    assert C3_OVERLAPPED_CANCEL_SETTLEMENT_TIMEOUT_MS == 1_000


def test_casefold_collision_check_rejects_exact_and_windows_folded_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = object.__new__(CtypesWindowsEffectfulCaptureNativeApi)
    monkeypatch.setattr(
        "trading_bot.runtime.windows_effectful_capture_native.os.listdir",
        lambda _directory: ["DAILY-MARKET-DATA-SNAPSHOT-X.JSON"],
    )

    with pytest.raises(WindowsEffectfulCaptureNativeError, match="collision"):
        api.reject_casefold_collisions(
            r"F:\AITradingBot\Authority\capture-output",
            ("daily-market-data-snapshot-x.json",),
        )


def test_live_resource_is_not_copyable_or_serializable() -> None:
    child = _create(FakeNativeApi())

    with pytest.raises(TypeError):
        copy.copy(child)
    with pytest.raises(TypeError):
        copy.deepcopy(child)
    with pytest.raises(TypeError):
        pickle.dumps(child)

    child.close()


@pytest.mark.parametrize(
    "fail_at,expected_closed",
    [
        ("set_job_limits", [100]),
        ("create_staging", [104, 103, 102, 101, 100]),
        (
            "create_process",
            [108, 105, 104, 103, 102, 101, 100],
        ),
    ],
)
def test_partial_failure_cleans_acquired_handles_with_job_last(
    fail_at: str,
    expected_closed: list[int],
) -> None:
    api = FakeNativeApi(fail_at=fail_at)

    with pytest.raises(WindowsEffectfulCaptureNativeError):
        _create(api)

    closed = [
        int(event.split(":", 1)[1])
        for event in api.events
        if event.startswith("close:")
    ]
    assert closed == expected_closed
    assert not closed or closed[-1] == 100


@pytest.mark.parametrize(
    "field,value",
    [
        ("application_name", "python.exe"),
        ("current_directory", "."),
        ("controlled_temp_directory", "temp"),
        ("staging_path", "snapshot.tmp"),
    ],
)
def test_relative_launch_paths_fail_before_native_effect(
    field: str, value: str
) -> None:
    api = FakeNativeApi()
    values = {
        "application_name": _APPLICATION,
        "arguments": (),
        "current_directory": _CURRENT,
        "controlled_temp_directory": _TEMP,
        "staging_path": _STAGING,
        "parent_environment": _PARENT_ENV,
        "native_api": api,
    }
    values[field] = value

    with pytest.raises(WindowsEffectfulCaptureNativeError, match="absolute Windows"):
        create_suspended_capture_child_for_test(**values)

    assert api.events == []


def test_case_insensitive_ambiguous_parent_environment_fails_closed() -> None:
    parent = dict(_PARENT_ENV)
    parent["SYSTEMROOT"] = r"D:\OtherWindows"

    with pytest.raises(WindowsEffectfulCaptureNativeError, match="duplicate"):
        build_c3_child_environment(parent, _TEMP)


def test_ctypes_adapter_is_import_safe_off_windows() -> None:
    if os.name == "nt":
        pytest.skip("non-Windows import-safety assertion")
    with pytest.raises(WindowsEffectfulCaptureNativeUnsupportedError):
        CtypesWindowsEffectfulCaptureNativeApi()


def test_ctypes_parent_overlapped_bindings_are_exact_on_windows() -> None:
    if os.name != "nt":
        pytest.skip("Windows ctypes binding assertion")
    from ctypes import wintypes

    api = CtypesWindowsEffectfulCaptureNativeApi()
    overlapped_pointer = ctypes.POINTER(api._overlapped)

    assert len(api._k32.CreateNamedPipeW.argtypes) == 8
    assert api._k32.CreateNamedPipeW.restype is wintypes.HANDLE
    assert api._k32.ConnectNamedPipe.argtypes == [wintypes.HANDLE, overlapped_pointer]
    assert api._k32.ReadFile.argtypes[-1] == overlapped_pointer
    assert api._k32.WriteFile.argtypes[-1] == overlapped_pointer
    assert api._k32.GetOverlappedResult.argtypes[1] == overlapped_pointer
    assert api._k32.CancelIoEx.argtypes[1] == overlapped_pointer
    assert api._k32.WaitForSingleObject.restype is wintypes.DWORD
    assert api._k32.WaitForMultipleObjects.restype is wintypes.DWORD
    assert api._k32.GetExitCodeProcess.restype is wintypes.BOOL
    assert api._k32.TerminateJobObject.restype is wintypes.BOOL


def test_real_named_pipe_pairs_have_exact_endpoint_inheritance_on_windows() -> None:
    if os.name != "nt":
        pytest.skip("Windows named-pipe inheritance assertion")
    from ctypes import wintypes

    api = CtypesWindowsEffectfulCaptureNativeApi()
    request = api.create_request_pipe(MAX_C3_CHILD_REQUEST_BYTES)
    result = api.create_result_pipe(MAX_C3_CHILD_RESULT_BYTES)
    get_flags = ctypes.WinDLL("kernel32", use_last_error=True).GetHandleInformation
    get_flags.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_flags.restype = wintypes.BOOL

    try:
        inherited = {request.read_handle, result.write_handle}
        for handle in (
            request.read_handle,
            request.write_handle,
            result.read_handle,
            result.write_handle,
        ):
            flags = wintypes.DWORD()
            assert get_flags(wintypes.HANDLE(handle), ctypes.byref(flags))
            assert bool(flags.value & 1) is (handle in inherited)
    finally:
        for handle in (
            request.read_handle,
            request.write_handle,
            result.read_handle,
            result.write_handle,
        ):
            api.close_handle(handle)
