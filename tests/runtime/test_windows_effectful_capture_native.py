from __future__ import annotations

import copy
import os
import pickle

import pytest

from trading_bot.runtime.windows_effectful_capture_native import (
    C3_CREATE_PROCESS_FLAGS,
    C3_REQUEST_HANDLE_ARGUMENT,
    C3_RESULT_HANDLE_ARGUMENT,
    C3_STAGING_HANDLE_ARGUMENT,
    CREATE_NO_WINDOW,
    CREATE_SUSPENDED,
    CREATE_UNICODE_ENVIRONMENT,
    EXTENDED_STARTUPINFO_PRESENT,
    NativeCreatedProcess,
    NativePipePair,
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
        resume_result: int = 1,
    ) -> None:
        self.fail_at = fail_at
        self.write_chunk = write_chunk
        self.resume_result = resume_result
        self.events: list[str] = []
        self.written = bytearray()
        self.process_call: dict[str, object] | None = None
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

    def create_pipe(self, buffer_size: int) -> NativePipePair:
        self._pipe_count += 1
        self._event(f"create_pipe:{buffer_size}")
        if self._pipe_count == 1:
            return NativePipePair(101, 102)
        return NativePipePair(103, 104)

    def set_handle_inheritable(self, handle: int, inheritable: bool) -> None:
        self._event(f"inherit:{handle}:{inheritable}")

    def create_staging_file(self, path: str) -> int:
        assert path == _STAGING
        self._event("create_staging")
        return 105

    def create_suspended_process(self, **kwargs: object) -> NativeCreatedProcess:
        self.process_call = dict(kwargs)
        self._event("create_process")
        return NativeCreatedProcess(1234, 5678, 106, 107)

    def close_handle(self, handle: int) -> None:
        self._event(f"close:{handle}")

    def write_file(self, handle: int, payload: bytes) -> int:
        assert handle == 102
        self._event(f"write:{len(payload)}")
        count = (
            len(payload)
            if self.write_chunk is None
            else min(self.write_chunk, len(payload))
        )
        self.written.extend(payload[:count])
        return count

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
        f"create_pipe:{MAX_C3_CHILD_REQUEST_BYTES}",
        "inherit:102:False",
        f"create_pipe:{MAX_C3_CHILD_RESULT_BYTES}",
        "inherit:103:False",
        "create_staging",
        "create_process",
        "close:101",
        "close:104",
        "inherit:105:False",
    ]

    call = api.process_call
    assert call is not None
    assert call["application_name"] == _APPLICATION
    assert call["current_directory"] == _CURRENT
    assert call["inherited_handles"] == (101, 104, 105)
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
        "105",
    )


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
    with pytest.raises(WindowsEffectfulCaptureNativeError, match="not completely"):
        resume_suspended_capture_child(child)

    assert "close:102" in api.events
    assert "resume:107" not in api.events
    child.close()


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
        (
            "create_process",
            [105, 104, 103, 102, 101, 100],
        ),
        (
            "inherit:105:False",
            [101, 104, 107, 106, 105, 103, 102, 100],
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
    from trading_bot.runtime.windows_effectful_capture_native import (
        CtypesWindowsEffectfulCaptureNativeApi,
    )

    with pytest.raises(WindowsEffectfulCaptureNativeUnsupportedError):
        CtypesWindowsEffectfulCaptureNativeApi()
