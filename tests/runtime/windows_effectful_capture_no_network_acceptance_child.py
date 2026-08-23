"""TEST-ONLY child for C3-E1 native topology acceptance; never uses credentials."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
from ctypes import wintypes


def _try_set_event(value: int) -> bool:
    set_event = ctypes.WinDLL("kernel32", use_last_error=True).SetEvent
    set_event.argtypes = [wintypes.HANDLE]
    set_event.restype = wintypes.BOOL
    return bool(set_event(wintypes.HANDLE(value)))


def _read_all(handle: int) -> bytes:
    import msvcrt

    descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    with os.fdopen(descriptor, "rb", closefd=True) as stream:
        return stream.read(4096)


def _write_all(handle: int, payload: bytes) -> None:
    import msvcrt

    descriptor = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sentinel-handle", type=int, required=True)
    parser.add_argument("--c3-request-handle", type=int, required=True)
    parser.add_argument("--c3-result-handle", type=int, required=True)
    parser.add_argument("--c3-staging-handle", type=int, required=True)
    arguments = parser.parse_args()

    request = _read_all(arguments.c3_request_handle)
    _write_all(arguments.c3_staging_handle, b"c3-e1-no-network-acceptance\n")
    try:
        subprocess.run(
            [sys.executable, "-c", "raise SystemExit(0)"],
            check=False,
            timeout=5,
        )
    except OSError as error:
        descendant_blocked = error.winerror in {5, 1816}
    except subprocess.SubprocessError:
        descendant_blocked = False
    else:
        descendant_blocked = False
    sentinel_set_event_succeeded = _try_set_event(arguments.sentinel_handle)
    result = json.dumps(
        {
            "descendant_blocked": descendant_blocked,
            "environment": dict(sorted(os.environ.items(), key=lambda item: item[0])),
            "request": request.decode("ascii", "strict"),
            "sentinel_set_event_succeeded": sentinel_set_event_succeeded,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _write_all(arguments.c3_result_handle, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
