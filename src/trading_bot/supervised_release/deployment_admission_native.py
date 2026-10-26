"""Read-only native capability adapter; no privilege enable or mutation APIs.

Only fixed ancestors and the production Python binary may be opened. The
PowerShell child is a bounded local diagnostic, never a runtime/task launcher.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    inspect_directory_security,
)
from trading_bot.arch133_verifier.token import WindowsTradingTokenObserver
from trading_bot.supervised_release.bundle import MAX_FILE_BYTES
from trading_bot.supervised_release.deployment_admission import (
    QuiescenceObservation,
    SecurityObservation,
)
from trading_bot.supervised_release.installation_contract import (
    ANCESTORS,
    PYTHON_SHA256,
    PYTHON_VERSION,
    ObjectFacts,
    ReadSession,
    ReleasePaths,
)
from trading_bot.supervised_release.model import PRODUCTION_PYTHON, RELEASES_BASE
from trading_bot.supervised_release.native_read import WindowsReadSession, bind
from trading_bot.supervised_release.observer import check_object

POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
DIAGNOSTIC = "scripts/arch134_deployment_admission_observe.ps1"
RUNTIME_ROOT = r"F:\AITradingBot\runtime"


class ObservationPaths:
    def admit(self, path: str) -> str:
        if type(path) is not str or path not in (
            *ANCESTORS,
            RUNTIME_ROOT,
            PRODUCTION_PYTHON,
        ):
            raise ValueError("READ_NAMESPACE_CEILING")
        return path


class AdmissionReadSession(WindowsReadSession):
    def __init__(self, release_id: str) -> None:
        # Base construction is inert apart from binding native query libraries.
        super().__init__(ReleasePaths(release_id))
        self.paths = ObservationPaths()

    def read(self, path: str, limit: int) -> bytes:
        if path != PRODUCTION_PYTHON or limit != MAX_FILE_BYTES:
            raise ValueError("BINARY_READ_CEILING")
        # Rewind the read-only handle, not the file, for independent hash replay.
        if not bind(
            self.kernel,
            "SetFilePointerEx",
            [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_uint32],
            ctypes.c_int32,
        )(self.handles[path], 0, None, 0):
            raise ValueError("BINARY_POSITION")
        return super().read(path, limit)

    def namespace_metadata(self) -> tuple[tuple[str, int, int, str], ...]:
        query = bind(
            self.kernel,
            "GetFileInformationByHandleEx",
            [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32],
            ctypes.c_int32,
        )
        buffer = ctypes.create_string_buffer(65536)
        entries = []
        for page in range(20002):
            if not query(
                self.handles[RELEASES_BASE],
                11 if page == 0 else 10,
                buffer,
                len(buffer),
            ):
                if ctypes.get_last_error() == 18:
                    return tuple(entries)
                raise ValueError("NAMESPACE_QUERY")
            entries.extend(parse_namespace_page(buffer.raw))
            if len(entries) > 20002:
                raise ValueError("NAMESPACE_BOUND")
        raise ValueError("NAMESPACE_PAGE_BOUND")


def parse_namespace_page(raw: bytes) -> tuple[tuple[str, int, int, str], ...]:
    """Bounded FILE_ID_BOTH_DIR_INFO metadata, never a descendant open."""
    if type(raw) is not bytes or len(raw) != 65536:
        raise ValueError("NAMESPACE_PAGE")
    offset = 0
    rows = []
    while True:
        if offset + 104 > len(raw):
            raise ValueError("NAMESPACE_RECORD")
        next_offset = int.from_bytes(raw[offset : offset + 4], "little")
        length = int.from_bytes(raw[offset + 60 : offset + 64], "little")
        short_length = raw[offset + 68]
        if (
            length % 2
            or not 0 < length <= 510
            or offset + 104 + length > len(raw)
            or short_length % 2
            or short_length > 24
        ):
            raise ValueError("NAMESPACE_NAME_BOUND")
        name = raw[offset + 104 : offset + 104 + length].decode("utf-16-le")
        if name not in (".", ".."):
            rows.append(
                (
                    name,
                    int.from_bytes(raw[offset + 96 : offset + 104], "little"),
                    int.from_bytes(raw[offset + 56 : offset + 60], "little"),
                    raw[offset + 70 : offset + 70 + short_length].decode("utf-16-le"),
                )
            )
        if next_offset == 0:
            return tuple(rows)
        if next_offset < 104 + length or next_offset % 8:
            raise ValueError("NAMESPACE_OFFSET")
        offset += next_offset


class AdmissionNativeReader:
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id

    @contextmanager
    def read_session(self) -> Iterator[AdmissionReadSession]:
        session = AdmissionReadSession(self.release_id)
        try:
            for path in ANCESTORS:
                check_object(
                    session.object(path, directory=True),
                    path,
                    directory=True,
                    image_policy=False,
                )
            yield session
        finally:
            session.close()


def observe_python(
    session: ReadSession, volume: int
) -> tuple[ObjectFacts, ObjectFacts]:
    facts = []
    for path, directory in ((RUNTIME_ROOT, True), (PRODUCTION_PYTHON, False)):
        row = check_object(
            session.object(path, directory=directory),
            path,
            directory=directory,
            volume=volume,
            image_policy=False,
        )
        facts.append(row)
        if row.owner not in {ADMINISTRATORS_SID, SYSTEM_SID} or any(
            kind != 0
            or flags & ~0x13
            or (sid not in {ADMINISTRATORS_SID, SYSTEM_SID} and mask & ~0x1200A9)
            for sid, mask, kind, flags in row.aces
        ):
            raise ValueError("PYTHON_POLICY")
    data = session.read(PRODUCTION_PYTHON, MAX_FILE_BYTES)
    if (
        hashlib.sha256(data).hexdigest() != PYTHON_SHA256
        or session.python_version() != PYTHON_VERSION
    ):
        raise ValueError("PYTHON_IDENTITY")
    for row in facts:
        if session.object(row.path, directory=row.kind == "directory") != row:
            raise ValueError("PYTHON_DRIFT")
    return tuple(facts)


def observe_security(
    session: AdmissionReadSession, parent: ObjectFacts
) -> SecurityObservation:
    runtime, python = observe_python(session, parent.identity[0])
    kernel, advapi = session.kernel, session.advapi
    pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
    token = pointer()
    current = bind(kernel, "GetCurrentProcess", [], pointer)()
    close = bind(kernel, "CloseHandle", [pointer], boolean)
    if (
        not bind(advapi, "OpenProcessToken", [pointer, dword, pointer], boolean)(
            current, 0xA, ctypes.byref(token)
        )
        or not token.value
    ):
        raise ValueError("TOKEN_QUERY")
    try:
        query = bind(
            advapi,
            "GetTokenInformation",
            [pointer, ctypes.c_int32, pointer, dword, pointer],
            boolean,
        )
        size = dword()
        if (
            query(token, 3, None, 0, ctypes.byref(size))
            or ctypes.get_last_error() != 122
            or not 4 <= size.value <= 65536
        ):
            raise ValueError("PRIVILEGE_BOUND")
        buffer = ctypes.create_string_buffer(size.value)
        used = dword()
        if (
            not query(token, 3, buffer, size, ctypes.byref(used))
            or not 4 <= used.value <= size.value
        ):
            raise ValueError("PRIVILEGE_QUERY")
        count = int.from_bytes(buffer.raw[:4], "little")
        if count > 128 or used.value != 4 + count * 12:
            raise ValueError("PRIVILEGE_SHAPE")
        privileges = []
        for index in range(count):
            offset = 4 + index * 12
            name = ctypes.create_unicode_buffer(80)
            length = dword(len(name))
            if not bind(
                advapi,
                "LookupPrivilegeNameW",
                [ctypes.c_wchar_p, pointer, ctypes.c_wchar_p, pointer],
                boolean,
            )(
                None, ctypes.byref(buffer, offset), name, ctypes.byref(length)
            ) or not 0 < length.value < len(name):
                raise ValueError("PRIVILEGE_NAME")
            privileges.append(
                (
                    name.value,
                    int.from_bytes(buffer.raw[offset + 8 : offset + 12], "little"),
                )
            )
        handle = session.handles[RELEASES_BASE]
        observation, descriptor_sha = inspect_directory_security(handle, RELEASES_BASE)
        if (
            observation.identity != parent.identity
            or observation.owner_sid != parent.owner
            or observation.protected is not parent.protected
            or observation.aces != parent.aces
        ):
            raise ValueError("PARENT_IDENTITY")
        sacl, descriptor = pointer(), pointer()
        get = bind(
            advapi,
            "GetSecurityInfo",
            [pointer, dword, dword, pointer, pointer, pointer, pointer, pointer],
            dword,
        )
        status = get(
            handle, 1, 8, None, None, None, ctypes.byref(sacl), ctypes.byref(descriptor)
        )
        sacl_hash = None
        try:
            if status == 0 and descriptor.value:
                length = bind(advapi, "GetSecurityDescriptorLength", [pointer], dword)(
                    descriptor
                )
                if not 20 <= length <= 65536:
                    raise ValueError("SACL_BOUND")
                sacl_hash = hashlib.sha256(
                    ctypes.string_at(descriptor, length)
                ).hexdigest()
                sacl_status = "AVAILABLE"
            elif status in (5, 1314):
                sacl_status = "ACCESS_DENIED" if status == 5 else "PRIVILEGE_NOT_HELD"
            else:
                raise ValueError("SACL_UNAVAILABLE")
        finally:
            if descriptor.value:
                bind(kernel, "LocalFree", [pointer], pointer)(descriptor)
        # AccessCheck only queries rights. DuplicateToken does not impersonate or
        # enable privileges; the duplicate exists only as AccessCheck's input.
        duplicate, sd = pointer(), pointer()
        if not bind(
            advapi, "DuplicateToken", [pointer, ctypes.c_int32, pointer], boolean
        )(token, 1, ctypes.byref(duplicate)):
            raise ValueError("ACCESS_TOKEN")
        try:
            if (
                get(handle, 1, 7, None, None, None, None, ctypes.byref(sd))
                or not sd.value
            ):
                raise ValueError("ACCESS_DESCRIPTOR")
            mapping = (dword * 4)(0x120089, 0x120116, 0x1200A0, 0x1F01FF)
            privilege_set = ctypes.create_string_buffer(65536)
            privilege_size = dword(len(privilege_set))
            granted, allowed = dword(), boolean()
            if (
                not bind(
                    advapi,
                    "AccessCheck",
                    [
                        pointer,
                        pointer,
                        dword,
                        pointer,
                        pointer,
                        pointer,
                        pointer,
                        pointer,
                    ],
                    boolean,
                )(
                    sd,
                    duplicate,
                    0x02000000,
                    mapping,
                    privilege_set,
                    ctypes.byref(privilege_size),
                    ctypes.byref(granted),
                    ctypes.byref(allowed),
                )
                or not allowed.value
            ):
                raise ValueError("EFFECTIVE_ACCESS_UNAVAILABLE")
        finally:
            if sd.value:
                bind(kernel, "LocalFree", [pointer], pointer)(sd)
            if duplicate.value:
                close(duplicate)
        return SecurityObservation(
            WindowsTradingTokenObserver().observe(),
            tuple(sorted(privileges)),
            sacl_status,
            sacl_hash,
            granted.value,
            descriptor_sha,
            runtime.identity,
            python.identity,
        )
    finally:
        close(token)


def observe_quiescence(root: Path) -> QuiescenceObservation:
    result = subprocess.run(
        (
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(root / DIAGNOSTIC),
            str(os.getpid()),
        ),
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode or result.stderr or len(result.stdout) > 65536:
        raise ValueError("QUIESCENCE_UNAVAILABLE")
    raw = json.loads(result.stdout.decode("utf-8-sig"))
    if (
        type(raw) is not dict
        or set(raw)
        != {
            "schema",
            "tasks",
            "process_inventory_sha256",
            "relevant_process_count",
            "reboot_manual_start",
        }
        or raw["schema"] != "arch134-deployment-quiescence/v1"
    ):
        raise ValueError("QUIESCENCE_SCHEMA")
    return QuiescenceObservation(
        tuple(tuple(row) for row in raw["tasks"]),
        raw["process_inventory_sha256"],
        raw["relevant_process_count"],
        raw["reboot_manual_start"],
    )
