from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

import pytest

from trading_bot.runtime.windows_authority import PRODUCTION_CAPTURE_OUTPUT_ROOT
from trading_bot.runtime.windows_effectful_capture_native import (
    PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
    PRODUCTION_C3_PYTHON_EXECUTABLE,
    PRODUCTION_C3_RUNTIME_ROOT,
    C3ProcessOutcomeStatus,
    C3ResultTransportStatus,
    CtypesWindowsEffectfulCaptureNativeApi,
    create_suspended_capture_child_for_test,
    deliver_canonical_child_request,
    observe_resumed_capture_child,
    resume_suspended_capture_child,
)

_ACCEPTANCE_ENV = "AI_TRADING_BOT_RUN_C3_E1_NATIVE_ACCEPTANCE"


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows Job Objects")
def test_opt_in_real_windows_no_network_process_topology() -> None:
    if os.environ.get(_ACCEPTANCE_ENV) != "1":
        pytest.skip(f"set {_ACCEPTANCE_ENV}=1 on the intended Windows host")
    required = (
        Path(PRODUCTION_C3_PYTHON_EXECUTABLE),
        Path(PRODUCTION_C3_RUNTIME_ROOT),
        Path(PRODUCTION_C3_CONTROLLED_TEMP_ROOT),
        Path(str(PRODUCTION_CAPTURE_OUTPUT_ROOT)),
    )
    if not all(path.exists() for path in required):
        pytest.skip("fixed C3 production deployment is not installed")

    child_script = (
        Path(__file__)
        .with_name("windows_effectful_capture_no_network_acceptance_child.py")
        .resolve()
    )
    api = CtypesWindowsEffectfulCaptureNativeApi()
    create_event = ctypes.WinDLL("kernel32", use_last_error=True).CreateEventW
    create_event.argtypes = [
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    create_event.restype = wintypes.HANDLE
    sentinel = int(create_event(None, True, False, None))
    assert sentinel > 0
    api.set_handle_inheritable(sentinel, True)
    staging_path = str(
        Path(str(PRODUCTION_CAPTURE_OUTPUT_ROOT))
        / ".c3-e1-no-network-acceptance.staging"
    )
    child = None
    staging_deleted = False
    try:
        child = create_suspended_capture_child_for_test(
            application_name=PRODUCTION_C3_PYTHON_EXECUTABLE,
            arguments=(
                str(child_script),
                "--sentinel-handle",
                str(sentinel),
            ),
            current_directory=PRODUCTION_C3_RUNTIME_ROOT,
            controlled_temp_directory=PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
            staging_path=staging_path,
            parent_environment=os.environ,
            native_api=api,
        )
        deliver_canonical_child_request(child, b"c3-e1-acceptance-request-v1")
        resume_suspended_capture_child(child)
        observation = observe_resumed_capture_child(child)

        assert observation.result_transport is C3ResultTransportStatus.COMPLETE
        assert observation.process_outcome is C3ProcessOutcomeStatus.EXITED_ZERO
        assert observation.result_payload is not None
        result = json.loads(observation.result_payload)
        assert result == {
            "descendant_blocked": True,
            "environment": {
                "PYTHONUTF8": "1",
                "SystemRoot": os.environ["SystemRoot"],
                "TEMP": PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
                "TMP": PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
                "WINDIR": os.environ["WINDIR"],
            },
            "request": "c3-e1-acceptance-request-v1",
            "sentinel_absent": True,
        }
        staging_handle, _identity, _path = child._retained_staging()
        assert api.read_artifact_file(staging_handle, 128) == (
            b"c3-e1-no-network-acceptance\n"
        )
        api.delete_staging_link(staging_handle)
        staging_deleted = True
    finally:
        if child is not None:
            if not staging_deleted:
                try:
                    staging_handle, _identity, _path = child._retained_staging()
                    api.delete_staging_link(staging_handle)
                except BaseException:
                    pass
            child.close()
        api.close_handle(sentinel)
