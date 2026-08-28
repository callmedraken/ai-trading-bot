from __future__ import annotations

import ctypes
import json
import os
import secrets
from collections.abc import Mapping
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
_PUBLICATION_ACCEPTANCE_ENV = "AI_TRADING_BOT_RUN_C3_E37_PUBLICATION_ACCEPTANCE"
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102


def _assert_exact_environment(actual: object, expected: Mapping[str, str]) -> None:
    assert type(actual) is dict
    assert len(actual) == len(expected) == 5
    normalized_actual: dict[str, str] = {}
    for name, value in actual.items():
        assert type(name) is str
        assert type(value) is str
        normalized_name = name.casefold()
        assert normalized_name not in normalized_actual
        normalized_actual[normalized_name] = value
    normalized_expected = {name.casefold(): value for name, value in expected.items()}
    assert normalized_actual == normalized_expected


def _assert_sentinel_not_inherited(
    *, parent_wait_result: int, child_set_event_succeeded: object
) -> None:
    assert type(child_set_event_succeeded) is bool
    assert parent_wait_result in {_WAIT_OBJECT_0, _WAIT_TIMEOUT}
    assert parent_wait_result == _WAIT_TIMEOUT


def test_exact_environment_accepts_case_insensitive_names() -> None:
    expected = {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "TEMP": r"F:\AITradingBot\temp",
        "TMP": r"F:\AITradingBot\temp",
        "PYTHONUTF8": "1",
    }

    _assert_exact_environment(
        {
            "SYSTEMROOT": r"C:\Windows",
            "windir": r"C:\Windows",
            "Temp": r"F:\AITradingBot\temp",
            "tmp": r"F:\AITradingBot\temp",
            "pythonutf8": "1",
        },
        expected,
    )


@pytest.mark.parametrize(
    "environment",
    [
        {
            "SystemRoot": r"C:\Windows",
            "WINDIR": r"C:\Windows",
            "TEMP": r"F:\AITradingBot\temp",
            "TMP": r"F:\AITradingBot\temp",
        },
        {
            "SystemRoot": r"C:\Windows",
            "WINDIR": r"C:\Windows",
            "TEMP": r"F:\AITradingBot\temp",
            "TMP": r"F:\AITradingBot\temp",
            "PYTHONUTF8": "1",
            "EXTRA": "rejected",
        },
    ],
    ids=["missing", "additional"],
)
def test_exact_environment_rejects_missing_or_additional_entries(
    environment: dict[str, str],
) -> None:
    expected = {
        "SystemRoot": r"C:\Windows",
        "WINDIR": r"C:\Windows",
        "TEMP": r"F:\AITradingBot\temp",
        "TMP": r"F:\AITradingBot\temp",
        "PYTHONUTF8": "1",
    }

    with pytest.raises(AssertionError):
        _assert_exact_environment(environment, expected)


@pytest.mark.parametrize("child_set_event_succeeded", [False, True])
def test_parent_nonsignaled_sentinel_proves_no_identity_inheritance(
    child_set_event_succeeded: bool,
) -> None:
    _assert_sentinel_not_inherited(
        parent_wait_result=_WAIT_TIMEOUT,
        child_set_event_succeeded=child_set_event_succeeded,
    )


def test_parent_signaled_sentinel_fails_identity_acceptance() -> None:
    with pytest.raises(AssertionError):
        _assert_sentinel_not_inherited(
            parent_wait_result=_WAIT_OBJECT_0,
            child_set_event_succeeded=True,
        )


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows file primitives")
def test_opt_in_real_windows_zero_network_artifact_publication() -> None:
    if os.environ.get(_PUBLICATION_ACCEPTANCE_ENV) != "1":
        pytest.skip(f"set {_PUBLICATION_ACCEPTANCE_ENV}=1 on the intended Windows host")
    production_temp_root = Path(PRODUCTION_C3_CONTROLLED_TEMP_ROOT)
    temp_root = (
        production_temp_root
        if production_temp_root.is_dir()
        else Path(__file__).resolve().parents[2]
    )

    token = secrets.token_hex(12)
    staging_path = temp_root / f".c3-e37-publication-{token}.staging"
    final_path = temp_root / f"c3-e37-publication-{token}.json"
    api = CtypesWindowsEffectfulCaptureNativeApi()
    staging = None
    opened = None
    child_handle_closed = False
    master_handle_closed = False
    final_handle_closed = False
    try:
        staging = api.create_staging_file(str(staging_path))
        retained_identity = staging.identity
        assert api.get_file_identity(staging.parent_handle) == retained_identity

        api.close_handle(staging.child_write_handle)
        child_handle_closed = True
        api.publish_staging_link(
            staging.parent_handle, str(staging_path), str(final_path)
        )
        opened = api.open_final_artifact(str(final_path))

        assert opened.identity == retained_identity
        assert api.get_file_identity(staging.parent_handle) == retained_identity
    finally:
        if opened is not None and not final_handle_closed:
            api.close_handle(opened.handle)
            final_handle_closed = True
        if staging is not None:
            if not child_handle_closed:
                api.close_handle(staging.child_write_handle)
                child_handle_closed = True
            if not master_handle_closed:
                api.close_handle(staging.parent_handle)
                master_handle_closed = True
        for path in (final_path, staging_path):
            if path.exists():
                path.unlink()

    assert child_handle_closed
    assert master_handle_closed
    assert final_handle_closed
    assert not staging_path.exists()
    assert not final_path.exists()


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
    wait_for_single_object = ctypes.WinDLL(
        "kernel32", use_last_error=True
    ).WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD
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
        assert type(result) is dict
        assert set(result) == {
            "descendant_blocked",
            "environment",
            "request",
            "sentinel_set_event_succeeded",
        }
        assert result["descendant_blocked"] is True
        assert result["request"] == "c3-e1-acceptance-request-v1"
        _assert_exact_environment(
            result["environment"],
            {
                "PYTHONUTF8": "1",
                "SystemRoot": os.environ["SystemRoot"],
                "TEMP": PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
                "TMP": PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
                "WINDIR": os.environ["WINDIR"],
            },
        )
        _assert_sentinel_not_inherited(
            parent_wait_result=int(
                wait_for_single_object(wintypes.HANDLE(sentinel), 0)
            ),
            child_set_event_succeeded=result["sentinel_set_event_succeeded"],
        )
        assert {
            "descendant_blocked": result["descendant_blocked"],
            "request": result["request"],
        } == {
            "descendant_blocked": True,
            "request": "c3-e1-acceptance-request-v1",
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
