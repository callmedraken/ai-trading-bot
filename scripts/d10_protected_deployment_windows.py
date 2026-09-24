"""Windows native create-only adapter for the inert P124-2/P124-3 tools."""

from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes

from scripts import d10_python_substrate_windows as substrate
from scripts import run_personal_desktop_d10_launch_guard as guard
from scripts.d10_protected_deployment import (
    D10_GUARD,
    D10_GUARD_INSTALLING,
    D10_PARENT,
    D10_ROOT,
    D10_SIGNING_KEY_ID,
    D10_SOURCE,
    D10_SOURCE_INSTALLING,
    P1242_RESERVED_PATHS,
    P1243_RESERVED_PATHS,
    TRUST_FINAL_PATHS,
    TRUST_INSTALLING_PATHS,
    Ace,
    CheckedDirectory,
    CheckedFile,
    DeploymentBlocked,
    NativeObject,
    validate_source_relative_path,
)
from trading_bot.runtime import personal_desktop_d10_python_substrate as substrate_model
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_LAUNCHER_RELATIVE_PATH,
)

FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_WRITE_THROUGH = 0x80000000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
WRITE_OWNER = 0x00080000
SE_DACL_PROTECTED_SET = 0x80000000
SYSTEM32 = r"C:\Windows\System32"
PUBLIC_KEY = guard.D10_PUBLIC_KEY


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("descriptor", ctypes.c_void_p),
        ("inherit", wintypes.BOOL),
    ]


class WindowsDeploymentBackend:
    """Fixed-root Administrator writer. No path or namespace is caller selected."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise DeploymentBlocked("windows_native_backend_required")
        try:
            self._kernel = ctypes.WinDLL(
                SYSTEM32 + r"\kernel32.dll", use_last_error=True
            )
            self._advapi = ctypes.WinDLL(
                SYSTEM32 + r"\advapi32.dll", use_last_error=True
            )
        except Exception:
            raise DeploymentBlocked("windows_native_libraries_unavailable") from None
        self._source_files: frozenset[str] = frozenset()
        self._source_directories: frozenset[str] = frozenset()

    def bind_source_inventory(self, relative_paths: tuple[str, ...]) -> None:
        if (
            type(relative_paths) is not tuple
            or not relative_paths
            or any(type(path) is not str for path in relative_paths)
        ):
            raise DeploymentBlocked("source_inventory_binding_invalid")
        if relative_paths != tuple(sorted(relative_paths)):
            raise DeploymentBlocked("source_inventory_binding_not_canonical")
        if len(relative_paths) != len(set(relative_paths)) or len(
            relative_paths
        ) != len({path.casefold() for path in relative_paths}):
            raise DeploymentBlocked("source_inventory_binding_collision")
        try:
            for relative in relative_paths:
                validate_source_relative_path(relative)
        except DeploymentBlocked:
            raise DeploymentBlocked("source_inventory_binding_path_invalid") from None
        if D10_LAUNCHER_RELATIVE_PATH not in relative_paths or not any(
            path.startswith("src/trading_bot/") for path in relative_paths
        ):
            raise DeploymentBlocked(
                "source_inventory_binding_launcher_or_package_missing"
            )
        directories = {D10_SOURCE_INSTALLING}
        for relative in relative_paths:
            parts = relative.split("/")
            parent = D10_SOURCE_INSTALLING
            for component in parts[:-1]:
                parent += "\\" + component
                directories.add(parent)
        if not self._source_files and not self._source_directories:
            self._source_files = frozenset(
                D10_SOURCE_INSTALLING + "\\" + path.replace("/", "\\")
                for path in relative_paths
            )
            self._source_directories = frozenset(directories)
        elif self._source_files != frozenset(
            D10_SOURCE_INSTALLING + "\\" + path.replace("/", "\\")
            for path in relative_paths
        ) or self._source_directories != frozenset(directories):
            raise DeploymentBlocked("source_inventory_binding_conflict")

    def _allowed_directory_create(self, path: str) -> bool:
        return path == D10_ROOT or path in self._source_directories

    def _allowed_file_create(self, path: str) -> bool:
        return (
            path in {D10_GUARD_INSTALLING, *TRUST_INSTALLING_PATHS}
            or path in self._source_files
        )

    def _bind(self, lib: object, name: str, args: list[object], result: object):
        function = getattr(lib, name)
        function.argtypes = args
        function.restype = result
        return function

    def require_administrator(self) -> None:
        token = wintypes.HANDLE()
        open_token = self._bind(
            self._advapi,
            "OpenProcessToken",
            [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)],
            wintypes.BOOL,
        )
        process = self._bind(self._kernel, "GetCurrentProcess", [], wintypes.HANDLE)
        if not open_token(process(), 0x0008 | 0x0001, ctypes.byref(token)):
            raise DeploymentBlocked("administrator_token_unavailable")
        try:
            elevated, returned = wintypes.DWORD(), wintypes.DWORD()
            get_info = self._bind(
                self._advapi,
                "GetTokenInformation",
                [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            )
            if not get_info(
                token,
                20,
                ctypes.byref(elevated),
                ctypes.sizeof(elevated),
                ctypes.byref(returned),
            ):
                raise DeploymentBlocked("administrator_elevation_unavailable")
            admin_sid = ctypes.c_void_p()
            convert = self._bind(
                self._advapi,
                "ConvertStringSidToSidW",
                [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)],
                wintypes.BOOL,
            )
            from scripts.d10_protected_deployment import ADMINISTRATORS_SID

            if not convert(ADMINISTRATORS_SID, ctypes.byref(admin_sid)):
                raise DeploymentBlocked("administrator_sid_unavailable")
            try:
                member = wintypes.BOOL()
                check = self._bind(
                    self._advapi,
                    "CheckTokenMembership",
                    [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)],
                    wintypes.BOOL,
                )
                if not check(token, admin_sid, ctypes.byref(member)):
                    raise DeploymentBlocked("administrator_membership_unavailable")
                if not elevated.value or not member.value:
                    raise DeploymentBlocked("administrator_required")
            finally:
                self._bind(
                    self._kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p
                )(admin_sid)
        finally:
            if not self._bind(
                self._kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL
            )(token):
                raise DeploymentBlocked("administrator_token_close_failed")

    def _open_absence(self, path: str):
        if path not in {
            *P1242_RESERVED_PATHS,
            *P1243_RESERVED_PATHS,
            D10_ROOT,
            D10_SOURCE,
            D10_GUARD,
            *TRUST_FINAL_PATHS,
        }:
            raise DeploymentBlocked("absence_probe_path_unreviewed")
        create = self._bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ],
            wintypes.HANDLE,
        )
        return create(
            path,
            0x80,
            1,
            None,
            3,
            FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )

    def require_absent(self, path: str) -> None:
        handle = self._open_absence(path)
        if handle not in (None, 0, ctypes.c_void_p(-1).value):
            self._bind(self._kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL)(
                handle
            )
            raise DeploymentBlocked("reserved_or_final_path_present")
        if ctypes.get_last_error() not in (2, 3):
            raise DeploymentBlocked("absence_probe_indeterminate")

    def _build_security_descriptor(self, directory: bool) -> ctypes.c_void_p:
        from scripts.d10_protected_deployment import (
            TRADING_DIRECTORY_READ,
            TRADING_FILE_READ,
            TRADING_SID,
        )

        mask = TRADING_DIRECTORY_READ if directory else TRADING_FILE_READ
        sddl = f"O:BA D:P(A;;FA;;;BA)(A;;FA;;;SY)(A;;0x{mask:08X};;;{TRADING_SID})"
        descriptor = ctypes.c_void_p()
        convert = self._bind(
            self._advapi,
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_void_p,
            ],
            wintypes.BOOL,
        )
        if not convert(sddl, 1, ctypes.byref(descriptor), None):
            raise DeploymentBlocked("native_acl_descriptor_build_failed")
        return descriptor

    def _free_security_descriptor(self, descriptor: ctypes.c_void_p) -> None:
        result = self._bind(
            self._kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p
        )(descriptor)
        if result:
            raise DeploymentBlocked("native_acl_descriptor_release_failed")

    def _security_attributes(
        self, directory: bool
    ) -> tuple[ctypes.c_void_p, _SecurityAttributes]:
        descriptor = self._build_security_descriptor(directory)
        attributes = _SecurityAttributes(
            ctypes.sizeof(_SecurityAttributes), descriptor, False
        )
        return descriptor, attributes

    def _set_acl(self, handle: object, directory: bool) -> None:
        descriptor = self._build_security_descriptor(directory)
        try:
            owner, dacl = ctypes.c_void_p(), ctypes.c_void_p()
            defaulted, present = wintypes.BOOL(), wintypes.BOOL()
            get_owner = self._bind(
                self._advapi,
                "GetSecurityDescriptorOwner",
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(wintypes.BOOL),
                ],
                wintypes.BOOL,
            )
            get_dacl = self._bind(
                self._advapi,
                "GetSecurityDescriptorDacl",
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(wintypes.BOOL),
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(wintypes.BOOL),
                ],
                wintypes.BOOL,
            )
            if not get_owner(descriptor, ctypes.byref(owner), ctypes.byref(defaulted)):
                raise DeploymentBlocked("native_owner_descriptor_missing")
            if (
                not get_dacl(
                    descriptor,
                    ctypes.byref(present),
                    ctypes.byref(dacl),
                    ctypes.byref(defaulted),
                )
                or not present.value
                or not dacl.value
            ):
                raise DeploymentBlocked("native_dacl_descriptor_missing")
            set_info = self._bind(
                self._advapi,
                "SetSecurityInfo",
                [
                    wintypes.HANDLE,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                ],
                wintypes.DWORD,
            )
            status = set_info(
                handle, 1, 1 | 4 | SE_DACL_PROTECTED_SET, owner, None, dacl, None
            )
            if status:
                raise DeploymentBlocked("native_acl_application_failed")
        finally:
            self._free_security_descriptor(descriptor)

    def create_directory(self, path: str) -> None:
        if not self._allowed_directory_create(path):
            raise DeploymentBlocked("directory_creation_path_unreviewed")
        descriptor, attributes = self._security_attributes(directory=True)
        try:
            create_dir = self._bind(
                self._kernel,
                "CreateDirectoryW",
                [ctypes.c_wchar_p, ctypes.POINTER(_SecurityAttributes)],
                wintypes.BOOL,
            )
            if not create_dir(path, ctypes.byref(attributes)):
                raise DeploymentBlocked("create_only_directory_failed")
        finally:
            self._free_security_descriptor(descriptor)
        flags = FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
        create = self._bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ],
            wintypes.HANDLE,
        )
        handle = create(
            path,
            1 | 0x80 | READ_CONTROL | WRITE_DAC | WRITE_OWNER,
            0,
            None,
            3,
            flags,
            None,
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise DeploymentBlocked("new_directory_native_open_failed")
        try:
            self._set_acl(handle, directory=True)
        finally:
            if not self._bind(
                self._kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL
            )(handle):
                raise DeploymentBlocked("directory_handle_close_failed")

    def create_file(self, path: str, data: bytes) -> None:
        if not self._allowed_file_create(path) or type(data) is not bytes:
            raise DeploymentBlocked("file_creation_path_or_payload_invalid")
        descriptor, attributes = self._security_attributes(directory=False)
        try:
            create = self._bind(
                self._kernel,
                "CreateFileW",
                [
                    ctypes.c_wchar_p,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.POINTER(_SecurityAttributes),
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.HANDLE,
                ],
                wintypes.HANDLE,
            )
            handle = create(
                path,
                0x0002 | READ_CONTROL | WRITE_DAC | WRITE_OWNER,
                0,
                ctypes.byref(attributes),
                1,
                FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_WRITE_THROUGH,
                None,
            )
        finally:
            self._free_security_descriptor(descriptor)
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise DeploymentBlocked("create_new_file_failed")
        try:
            write = self._bind(
                self._kernel,
                "WriteFile",
                [
                    wintypes.HANDLE,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                    ctypes.c_void_p,
                ],
                wintypes.BOOL,
            )
            if data:
                payload = ctypes.create_string_buffer(data)
                written = wintypes.DWORD()
                if not write(
                    handle, payload, len(data), ctypes.byref(written), None
                ) or written.value != len(data):
                    raise DeploymentBlocked("file_write_incomplete")
            if not self._bind(
                self._kernel, "FlushFileBuffers", [wintypes.HANDLE], wintypes.BOOL
            )(handle):
                raise DeploymentBlocked("file_flush_failed")
            self._set_acl(handle, directory=False)
        finally:
            if not self._bind(
                self._kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL
            )(handle):
                raise DeploymentBlocked("file_handle_close_failed")

    def publish_create_only(self, installing_path: str, final_path: str) -> None:
        allowed = {
            (D10_GUARD_INSTALLING, D10_GUARD),
            (D10_SOURCE_INSTALLING, D10_SOURCE),
            *zip(TRUST_INSTALLING_PATHS, TRUST_FINAL_PATHS, strict=True),
        }
        if (installing_path, final_path) not in allowed:
            raise DeploymentBlocked("atomic_publication_path_unreviewed")
        move = self._bind(
            self._kernel,
            "MoveFileW",
            [ctypes.c_wchar_p, ctypes.c_wchar_p],
            wintypes.BOOL,
        )
        if not move(installing_path, final_path):
            raise DeploymentBlocked("create_only_atomic_publication_failed")

    def _read_pinned_file(self, handle: int, size: int) -> bytes:
        if size == 0:
            return b""
        if not 0 < size <= 1024 * 1024 * 1024:
            raise DeploymentBlocked("native_source_size_bound")
        seek = guard._win_dll("kernel32").SetFilePointerEx
        seek.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        seek.restype = wintypes.BOOL
        if not seek(handle, 0, None, 0):
            raise DeploymentBlocked("native_source_seek_failed")
        read = guard._win_dll("kernel32").ReadFile
        read.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        read.restype = wintypes.BOOL
        content = bytearray()
        remaining = size
        while remaining:
            chunk = min(remaining, 1024 * 1024)
            buffer = ctypes.create_string_buffer(chunk)
            received = wintypes.DWORD()
            if not read(handle, buffer, chunk, ctypes.byref(received), None):
                raise DeploymentBlocked("native_source_read_failed")
            if not received.value:
                raise DeploymentBlocked("native_source_read_short")
            content.extend(buffer.raw[: received.value])
            remaining -= received.value
        return bytes(content)

    def read_file(self, path: str, limit: int) -> CheckedFile:
        if not (
            path == D10_GUARD
            or path in TRUST_FINAL_PATHS
            or path.startswith(D10_SOURCE + "\\")
        ):
            raise DeploymentBlocked("native_read_path_unreviewed")
        native = guard._Native()
        try:
            handle = native.open(path, directory=False)
            try:
                before = native.inspect(handle)
                from scripts.d10_protected_deployment import require_native_object

                item = self._native_facts(path, before, directory=False)
                require_native_object(item, path, directory=False)
                if item.size > limit:
                    raise DeploymentBlocked("native_read_size_bound")
                data = self._read_pinned_file(handle, item.size)
                after = native.inspect(handle)
                if before != after or len(data) != item.size:
                    raise DeploymentBlocked("native_read_identity_or_size_drift")
                return CheckedFile(item, data, True)
            finally:
                native.close(handle)
        except DeploymentBlocked:
            raise
        except Exception:
            raise DeploymentBlocked("native_file_read_or_identity_failed") from None

    def _native_facts(
        self, path: str, facts: object, *, directory: bool
    ) -> NativeObject:
        return NativeObject(
            path,
            facts.final_path,
            bool(facts.attributes & guard.FILE_ATTRIBUTE_DIRECTORY),
            facts.owner,
            facts.protected,
            tuple(Ace(a.sid, a.mask, a.ace_type, a.flags) for a in facts.aces),
            bool(facts.attributes & guard.FILE_ATTRIBUTE_REPARSE_POINT),
            facts.drive_type,
            facts.volume_root,
            facts.filesystem,
            facts.volume_serial,
            facts.file_index,
            facts.links,
            facts.size,
        )

    def list_directory(self, path: str) -> CheckedDirectory:
        try:
            return self._list_directory_checked(path)
        except DeploymentBlocked:
            raise
        except Exception:
            raise DeploymentBlocked(
                "native_directory_read_or_identity_failed"
            ) from None

    def _list_directory_checked(self, path: str) -> CheckedDirectory:
        if path == D10_PARENT:
            handle = substrate._open(path)
            try:
                before, _ = substrate._inspect(path, handle)
                q = substrate_model
                if (
                    before.final_path != path
                    or before.kind is not q.Kind.DIRECTORY
                    or before.reparse
                    or before.owner_sid != q.ADMIN
                    or not before.dacl_protected
                    or before.aces
                    != (
                        q.Ace(q.ADMIN, q.ALL_ACCESS),
                        q.Ace(q.SYSTEM, q.ALL_ACCESS),
                        q.Ace(q.TRADING, q.DIRECTORY_READ),
                    )
                    or before.drive_type != 3
                    or before.volume_root != "F:\\"
                    or before.filesystem != "NTFS"
                    or before.links != 1
                ):
                    raise DeploymentBlocked("d10_parent_security_drift")
                names = self._list_names(path)
                after, _ = substrate._inspect(path, handle)
                if before != after:
                    raise DeploymentBlocked("d10_parent_identity_drift")
                item = NativeObject(
                    path,
                    path,
                    True,
                    before.owner_sid,
                    before.dacl_protected,
                    tuple(Ace(a.sid, a.mask, a.ace_type, a.flags) for a in before.aces),
                    False,
                    before.drive_type,
                    before.volume_root,
                    before.filesystem,
                    before.volume_serial,
                    before.file_index,
                    before.links,
                    0,
                )
                return CheckedDirectory(item, names, True)
            finally:
                substrate._close(handle)

        if path == D10_ROOT or path == D10_SOURCE or path.startswith(D10_SOURCE + "\\"):
            native = guard._Native()
            handle = native.open(path, directory=True)
            try:
                before = native.inspect(handle)
                item = self._native_facts(path, before, directory=True)
                names = native.listdir(path)
                after = native.inspect(handle)
                if before != after:
                    raise DeploymentBlocked("native_directory_identity_drift")
                return CheckedDirectory(item, names, True)
            finally:
                native.close(handle)
        raise DeploymentBlocked("native_inventory_path_unreviewed")

    def _list_names(self, path: str) -> tuple[str, ...]:
        class Data(ctypes.Structure):
            _fields_ = [
                ("attributes", wintypes.DWORD),
                ("creation", wintypes.FILETIME),
                ("access", wintypes.FILETIME),
                ("write", wintypes.FILETIME),
                ("size_high", wintypes.DWORD),
                ("size_low", wintypes.DWORD),
                ("reserved0", wintypes.DWORD),
                ("reserved1", wintypes.DWORD),
                ("name", ctypes.c_wchar * 260),
                ("alternate", ctypes.c_wchar * 14),
                ("file_type", wintypes.DWORD),
                ("creator_type", wintypes.DWORD),
                ("finder_flags", wintypes.WORD),
            ]

        first = self._bind(
            self._kernel,
            "FindFirstFileW",
            [ctypes.c_wchar_p, ctypes.POINTER(Data)],
            wintypes.HANDLE,
        )
        next_file = self._bind(
            self._kernel,
            "FindNextFileW",
            [wintypes.HANDLE, ctypes.POINTER(Data)],
            wintypes.BOOL,
        )
        data = Data()
        handle = first(path + r"\*", ctypes.byref(data))
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            if ctypes.get_last_error() == 2:
                return ()
            raise DeploymentBlocked("native_directory_enumeration_failed")
        names = []
        try:
            while True:
                if data.name not in (".", ".."):
                    names.append(data.name)
                if next_file(handle, ctypes.byref(data)):
                    continue
                if ctypes.get_last_error() != 18:
                    raise DeploymentBlocked("native_directory_enumeration_incomplete")
                break
        finally:
            if not self._bind(
                self._kernel, "FindClose", [wintypes.HANDLE], wintypes.BOOL
            )(handle):
                raise DeploymentBlocked("native_find_close_failed")
        return tuple(sorted(names))


class WindowsCngVerifier:
    """Verify the fixed D10 P-256 public key; it has no signing capability."""

    key_id = D10_SIGNING_KEY_ID

    def verify(self, message: bytes, signature: bytes) -> bool:
        if os.name != "nt" or len(PUBLIC_KEY) != 65 or PUBLIC_KEY[0] != 4:
            return False
        bcrypt = ctypes.WinDLL(SYSTEM32 + r"\bcrypt.dll", use_last_error=True)
        algorithm, key = ctypes.c_void_p(), ctypes.c_void_p()

        def bind(name: str, args: list[object], result: object):
            fn = getattr(bcrypt, name)
            fn.argtypes, fn.restype = args, result
            return fn

        open_algorithm = bind(
            "BCryptOpenAlgorithmProvider",
            [
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                wintypes.ULONG,
            ],
            ctypes.c_long,
        )
        import_key = bind(
            "BCryptImportKeyPair",
            [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_void_p,
                wintypes.ULONG,
                wintypes.ULONG,
            ],
            ctypes.c_long,
        )
        verify = bind(
            "BCryptVerifySignature",
            [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.ULONG,
                ctypes.c_void_p,
                wintypes.ULONG,
                wintypes.ULONG,
            ],
            ctypes.c_long,
        )
        try:
            if open_algorithm(ctypes.byref(algorithm), "ECDSA_P256", None, 0):
                return False
            blob = (ctypes.c_ubyte * 72).from_buffer_copy(
                (0x31534345).to_bytes(4, "little")
                + (32).to_bytes(4, "little")
                + PUBLIC_KEY[1:]
            )
            if import_key(
                algorithm,
                None,
                "ECCPUBLICBLOB",
                ctypes.byref(key),
                blob,
                len(blob),
                0,
            ):
                return False
            digest = (ctypes.c_ubyte * 32).from_buffer_copy(
                hashlib.sha256(message).digest()
            )
            raw = (ctypes.c_ubyte * 64).from_buffer_copy(signature)
            return verify(key, None, digest, 32, raw, 64, 0) == 0
        finally:
            if key.value:
                bind("BCryptDestroyKey", [ctypes.c_void_p], ctypes.c_long)(key)
            if algorithm.value:
                bind(
                    "BCryptCloseAlgorithmProvider",
                    [ctypes.c_void_p, wintypes.ULONG],
                    ctypes.c_long,
                )(algorithm, 0)
