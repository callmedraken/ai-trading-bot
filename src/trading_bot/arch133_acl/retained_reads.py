"""Bounded retained-file reads and held-directory enumeration; no write capability."""

from __future__ import annotations

import ctypes
import hashlib
import ntpath

from trading_bot.arch133_acl import read_only

TARGET_PATH = r"F:\AITradingBot\Arch133"
FINAL_NAMES = ("activation.json", "host-binding.json", "paper.sqlite", "wake.sqlite")
MAX_FILE_BYTES = 256 * 1024 * 1024


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


class FileInformation(ctypes.Structure):
    _fields_ = [
        ("attributes", ctypes.c_uint32),
        ("times", ctypes.c_uint32 * 6),
        ("volume", ctypes.c_uint32),
        ("size_high", ctypes.c_uint32),
        ("size_low", ctypes.c_uint32),
        ("links", ctypes.c_uint32),
        ("index_high", ctypes.c_uint32),
        ("index_low", ctypes.c_uint32),
    ]


class DirectoryEntry(ctypes.Structure):
    _fields_ = [
        ("next", ctypes.c_uint32),
        ("index", ctypes.c_uint32),
        ("times", ctypes.c_int64 * 4),
        ("end", ctypes.c_int64),
        ("allocation", ctypes.c_int64),
        ("attributes", ctypes.c_uint32),
        ("name_bytes", ctypes.c_uint32),
        ("ea_size", ctypes.c_uint32),
        ("short_length", ctypes.c_ubyte),
        ("short_name", ctypes.c_wchar * 12),
        ("file_id", ctypes.c_int64),
        ("name", ctypes.c_wchar * 1),
    ]


def namespace(handle: int) -> tuple[tuple[str, int], ...]:
    """Enumerate only the pinned directory, never a path glob or alternate root open."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    query = _bind(
        kernel,
        "GetFileInformationByHandleEx",
        [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32],
        ctypes.c_int32,
    )
    buffer = ctypes.create_string_buffer(65536)
    found = []
    for page in range(16):
        if not query(handle, 11 if page == 0 else 10, buffer, len(buffer)):
            if ctypes.get_last_error() == 18:
                if tuple(sorted(name for name, _ in found)) != FINAL_NAMES:
                    raise read_only.RootAclError("retained namespace rejected")
                return tuple(sorted(found))
            raise read_only.RootAclError("retained enumeration rejected")
        offset = 0
        for _ in range(32):
            if offset + ctypes.sizeof(DirectoryEntry) > len(buffer):
                raise read_only.RootAclError("retained entry bound rejected")
            entry = DirectoryEntry.from_buffer(buffer, offset)
            length = int(entry.name_bytes)
            end = offset + DirectoryEntry.name.offset + length
            if length == 0 or length % 2 or length > 128 or end > len(buffer):
                raise read_only.RootAclError("retained name bound rejected")
            name = ctypes.string_at(
                ctypes.addressof(buffer) + offset + DirectoryEntry.name.offset, length
            ).decode("utf-16-le", errors="strict")
            if name not in (".", ".."):
                if name not in FINAL_NAMES or entry.attributes & (0x400 | 0x10):
                    raise read_only.RootAclError("retained entry rejected")
                found.append((name, entry.file_id & 0xFFFFFFFFFFFFFFFF))
                if len(found) > 4:
                    raise read_only.RootAclError("retained namespace bound rejected")
            if entry.next == 0:
                break
            if entry.next % 8 or entry.next < DirectoryEntry.name.offset + length:
                raise read_only.RootAclError("retained entry offset rejected")
            offset += entry.next
        else:
            raise read_only.RootAclError("retained enumeration bound rejected")
    raise read_only.RootAclError("retained enumeration bound rejected")


def open_retained_file(name: str) -> int:
    """Fixed four-name allowlist, read-only access, deny write/delete, no follow."""
    if name not in FINAL_NAMES:
        raise read_only.RootAclError("retained file name rejected")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = _bind(
        kernel,
        "CreateFileW",
        [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ],
        ctypes.c_void_p,
    )
    handle = create(TARGET_PATH + "\\" + name, 0x80000080, 1, None, 3, 0x00200000, None)
    if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
        raise read_only.RootAclError("retained read-only open rejected")
    return handle


def file_snapshot(handle: int, name: str) -> tuple[tuple[int, int], str]:
    if name not in FINAL_NAMES:
        raise read_only.RootAclError("retained file name rejected")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
    final = ctypes.create_unicode_buffer(512)
    count = _bind(
        kernel,
        "GetFinalPathNameByHandleW",
        [pointer, ctypes.c_wchar_p, dword, dword],
        dword,
    )(handle, final, len(final), 0)
    if not 0 < count < len(final) or ntpath.normcase(final.value) != ntpath.normcase(
        "\\\\?\\" + TARGET_PATH + "\\" + name
    ):
        raise read_only.RootAclError("retained final path rejected")
    info = FileInformation()
    if (
        not _bind(kernel, "GetFileInformationByHandle", [pointer, pointer], boolean)(
            handle, ctypes.byref(info)
        )
        or info.attributes & (0x400 | 0x10)
        or info.links != 1
    ):
        raise read_only.RootAclError("retained file identity rejected")
    size = (info.size_high << 32) | info.size_low
    if size > MAX_FILE_BYTES:
        raise read_only.RootAclError("retained file size rejected")
    if not _bind(
        kernel, "SetFilePointerEx", [pointer, ctypes.c_int64, pointer, dword], boolean
    )(handle, 0, None, 0):
        raise read_only.RootAclError("retained read position rejected")
    read = _bind(
        kernel, "ReadFile", [pointer, pointer, dword, pointer, pointer], boolean
    )
    digest = hashlib.sha256()
    buffer = ctypes.create_string_buffer(65536)
    total = 0
    while True:
        count = dword()
        if not read(handle, buffer, len(buffer), ctypes.byref(count), None):
            raise read_only.RootAclError("retained read rejected")
        if count.value > len(buffer) or total + count.value > size:
            raise read_only.RootAclError("retained read bound rejected")
        if not count.value:
            break
        digest.update(buffer.raw[: count.value])
        total += count.value
    if total != size:
        raise read_only.RootAclError("retained read size changed")
    return (info.volume, (info.index_high << 32) | info.index_low), digest.hexdigest()
