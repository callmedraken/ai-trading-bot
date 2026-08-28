from __future__ import annotations

import copy
import ctypes
import os
import pickle
from ctypes import wintypes

import pytest

import trading_bot.runtime.windows_effectful_capture_native as native_module
from trading_bot.runtime.windows_effectful_capture_native import (
    C3_CREATE_PROCESS_FLAGS,
    C3_OVERLAPPED_CANCEL_SETTLEMENT_TIMEOUT_MS,
    C3_REQUEST_HANDLE_ARGUMENT,
    C3_RESULT_HANDLE_ARGUMENT,
    C3_STAGING_HANDLE_ARGUMENT,
    CREATE_NEW,
    CREATE_NO_WINDOW,
    CREATE_SUSPENDED,
    CREATE_UNICODE_ENVIRONMENT,
    DELETE,
    EXTENDED_STARTUPINFO_PRESENT,
    FILE_ATTRIBUTE_NORMAL,
    FILE_FLAG_FIRST_PIPE_INSTANCE,
    FILE_FLAG_OPEN_REPARSE_POINT,
    FILE_FLAG_OVERLAPPED,
    FILE_SHARE_DELETE,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    GENERIC_READ,
    GENERIC_WRITE,
    OPEN_EXISTING,
    PIPE_REJECT_REMOTE_CLIENTS,
    PRODUCTION_C3_CHILD_BASE_ARGUMENTS,
    PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
    PRODUCTION_C3_PYTHON_EXECUTABLE,
    PRODUCTION_C3_RUNTIME_ROOT,
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
    WindowsEffectfulCaptureProcessNotCreatedError,
    WindowsEffectfulCaptureProcessOutcomeUnknownError,
    build_c3_child_environment,
    create_production_suspended_capture_child,
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
        self.expected_staging = _STAGING
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
        assert path == self.expected_staging
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

    def publish_staging_link(
        self, staging_handle: int, staging_path: str, final_path: str
    ) -> None:
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


def test_production_containment_uses_only_fixed_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reservation_id = "11111111-1111-4111-8111-111111111111"
    api = FakeNativeApi()
    api.expected_staging = (
        r"F:\AITradingBot\Authority\capture-output\.c3-capture-"
        f"{reservation_id}.staging"
    )
    monkeypatch.setattr(
        native_module, "CtypesWindowsEffectfulCaptureNativeApi", FakeNativeApi
    )
    monkeypatch.setattr(native_module.os, "environ", _PARENT_ENV)

    child = create_production_suspended_capture_child(reservation_id, api)

    call = api.process_call
    assert call is not None
    assert call["application_name"] == PRODUCTION_C3_PYTHON_EXECUTABLE
    assert call["current_directory"] == PRODUCTION_C3_RUNTIME_ROOT
    assert call["arguments"][:2] == PRODUCTION_C3_CHILD_BASE_ARGUMENTS
    assert call["environment"] == {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "TEMP": PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
        "TMP": PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
        "PYTHONUTF8": "1",
    }
    assert call["inherited_handles"] == (101, 104, 108)
    assert api.staging_object is not None
    assert api.staging_object.path == api.expected_staging
    child.close()


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


def test_publication_uses_create_hard_link_no_clobber_primitive() -> None:
    calls: list[tuple[object, ...]] = []

    class FakeKernel32:
        def CreateHardLinkW(self, *args: object) -> bool:
            calls.append(args)
            return True

    api = object.__new__(CtypesWindowsEffectfulCaptureNativeApi)
    api._k32 = FakeKernel32()
    staging_path = r"F:\AITradingBot\Authority\capture-output\.c3-capture-test.staging"
    final_path = (
        r"F:\AITradingBot\Authority\capture-output\daily-market-data-snapshot-x.json"
    )

    api.publish_staging_link(105, staging_path, final_path)

    assert calls == [(final_path, staging_path, None)]
    assert not hasattr(native_module, "FILE_LINK_INFO_CLASS")


@pytest.mark.parametrize(
    "staging_handle,staging_path,final_path,error",
    [
        (
            105,
            r"relative\.c3-capture-test.staging",
            r"F:\AITradingBot\temp\snapshot.json",
            "staging path must be absolute Windows text",
        ),
        (
            105,
            r"F:\AITradingBot\temp\.c3-capture-test.staging",
            r"relative\snapshot.json",
            "final artifact path must be absolute Windows text",
        ),
        (
            105,
            r"F:\AITradingBot\temp\.c3-capture-test.staging",
            r"F:\AITradingBot\other\snapshot.json",
            "same parent directory",
        ),
        (
            0,
            r"F:\AITradingBot\temp\.c3-capture-test.staging",
            r"F:\AITradingBot\temp\snapshot.json",
            "publication staging handle",
        ),
    ],
)
def test_publication_validates_source_destination_and_retained_handle(
    staging_handle: int,
    staging_path: str,
    final_path: str,
    error: str,
) -> None:
    class UnexpectedKernel32:
        def CreateHardLinkW(self, *_args: object) -> bool:
            raise AssertionError("invalid publication reached the native effect")

    api = object.__new__(CtypesWindowsEffectfulCaptureNativeApi)
    api._k32 = UnexpectedKernel32()

    with pytest.raises(WindowsEffectfulCaptureNativeError, match=error):
        api.publish_staging_link(staging_handle, staging_path, final_path)


def test_create_hard_link_failure_is_sanitized_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingKernel32:
        def CreateHardLinkW(self, *_args: object) -> bool:
            return False

    api = object.__new__(CtypesWindowsEffectfulCaptureNativeApi)
    api._k32 = FailingKernel32()
    monkeypatch.setattr(native_module.ctypes, "get_last_error", lambda: 183)
    staging_path = r"F:\AITradingBot\temp\.c3-private-source.staging"
    final_path = r"F:\AITradingBot\temp\final-private-name.json"

    with pytest.raises(WindowsEffectfulCaptureNativeError) as raised:
        api.publish_staging_link(105, staging_path, final_path)

    assert str(raised.value) == (
        "Windows operation failed: CreateHardLinkW (win32=183)"
    )
    assert staging_path not in str(raised.value)
    assert final_path not in str(raised.value)


def test_open_final_artifact_shares_with_retained_writable_master() -> None:
    calls: list[tuple[object, ...]] = []

    class FileAttributeTagInfo(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("ReparseTag", wintypes.DWORD),
        ]

    class FakeKernel32:
        def CreateFileW(self, *args: object) -> int:
            calls.append(args)
            return 201

        def GetFileInformationByHandleEx(self, *_args: object) -> bool:
            return True

    api = object.__new__(CtypesWindowsEffectfulCaptureNativeApi)
    api._k32 = FakeKernel32()
    api._w = wintypes
    api._file_attribute_tag_info = FileAttributeTagInfo
    identity = NativeFileIdentity(7, b"i" * 16)
    api.get_file_identity = lambda handle: identity
    api.close_handle = lambda handle: None
    final_path = r"F:\AITradingBot\temp\snapshot.json"

    opened = api.open_final_artifact(final_path)

    assert opened == native_module.NativeOpenedArtifact(201, identity)
    assert calls == [
        (
            final_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
    ]


def test_staging_master_still_does_not_share_writes() -> None:
    calls: list[tuple[object, ...]] = []

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [
            ("length", wintypes.DWORD),
            ("security_descriptor", ctypes.c_void_p),
            ("inherit_handle", wintypes.BOOL),
        ]

    class FakeKernel32:
        def CreateFileW(self, *args: object) -> int:
            calls.append(args)
            return 201

        def GetCurrentProcess(self) -> int:
            return 1

        def DuplicateHandle(
            self,
            _source_process: object,
            _source_handle: object,
            _target_process: object,
            target_handle: object,
            _desired_access: object,
            _inherit: object,
            _options: object,
        ) -> bool:
            ctypes.cast(target_handle, ctypes.POINTER(wintypes.HANDLE))[0] = 202
            return True

    api = object.__new__(CtypesWindowsEffectfulCaptureNativeApi)
    api._k32 = FakeKernel32()
    api._w = wintypes
    api._sa = SecurityAttributes
    api.reject_casefold_collisions = lambda directory, names: None
    identity = NativeFileIdentity(7, b"i" * 16)
    api.get_file_identity = lambda handle: identity
    api.close_handle = lambda handle: None
    staging_path = r"F:\AITradingBot\temp\.c3-capture-test.staging"

    staging = api.create_staging_file(staging_path)

    assert staging == NativeStagingObject(201, 202, identity, staging_path)
    assert len(calls) == 1
    call = calls[0]
    assert call[:3] == (
        staging_path,
        GENERIC_READ | GENERIC_WRITE | DELETE,
        FILE_SHARE_READ | FILE_SHARE_DELETE,
    )
    assert call[3] is not None
    assert call[4:] == (CREATE_NEW, FILE_ATTRIBUTE_NORMAL, None)
    assert not (int(call[2]) & FILE_SHARE_WRITE)


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


def test_native_failure_classification_never_fabricates_not_created() -> None:
    with pytest.raises(WindowsEffectfulCaptureProcessNotCreatedError):
        _create(FakeNativeApi(fail_at="set_job_limits"))

    with pytest.raises(WindowsEffectfulCaptureProcessOutcomeUnknownError):
        _create(FakeNativeApi(fail_at="create_process"))


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
    assert api._k32.CreateHardLinkW.argtypes == [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.POINTER(api._sa),
    ]
    assert api._k32.CreateHardLinkW.restype is wintypes.BOOL


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
