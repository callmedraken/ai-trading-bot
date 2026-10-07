"""Binary final-file policy observation on already-held read-only handles."""

from __future__ import annotations

import ctypes
import hashlib
from dataclasses import dataclass

from trading_bot.arch133_acl.read_only import (
    ADMIN_ACES,
    ADMINISTRATORS_SID,
    TRADING_SID,
)


@dataclass(frozen=True, slots=True)
class FilePolicy:
    owner_sid: str
    protected: bool
    aces: tuple[tuple[str, int, int, int], ...]
    security_sha256: str


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


def observe_file_policy(handle: int) -> FilePolicy:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
    owner, dacl, descriptor = pointer(), pointer(), pointer()
    get = _bind(
        api,
        "GetSecurityInfo",
        [pointer, dword, dword, pointer, pointer, pointer, pointer, pointer],
        dword,
    )
    try:
        if get(
            handle,
            1,
            7,
            ctypes.byref(owner),
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        ) or not all((owner.value, dacl.value, descriptor.value)):
            raise ValueError
        control, revision = ctypes.c_uint16(), dword()
        if not _bind(
            api, "GetSecurityDescriptorControl", [pointer, pointer, pointer], boolean
        )(descriptor, ctypes.byref(control), ctypes.byref(revision)):
            raise ValueError

        class AclSize(ctypes.Structure):
            _fields_ = [("count", dword), ("used", dword), ("free", dword)]

        size = AclSize()
        if (
            not _bind(
                api, "GetAclInformation", [pointer, pointer, dword, dword], boolean
            )(dacl, ctypes.byref(size), ctypes.sizeof(size), 2)
            or size.count != 3
        ):
            raise ValueError

        def sid_text(sid):
            text = ctypes.c_wchar_p()
            if (
                not _bind(api, "ConvertSidToStringSidW", [pointer, pointer], boolean)(
                    sid, ctypes.byref(text)
                )
                or not text.value
            ):
                raise ValueError
            try:
                if len(text.value) > 184:
                    raise ValueError
                return text.value
            finally:
                _bind(kernel, "LocalFree", [pointer], pointer)(text)

        aces = []
        for index in range(size.count):
            raw = pointer()
            if (
                not _bind(api, "GetAce", [pointer, dword, pointer], boolean)(
                    dacl, index, ctypes.byref(raw)
                )
                or not raw.value
            ):
                raise ValueError
            header = ctypes.cast(raw, ctypes.POINTER(ctypes.c_ubyte * 4)).contents
            if header[0] != 0:
                raise ValueError
            mask = ctypes.cast(raw.value + 4, ctypes.POINTER(dword)).contents.value
            aces.append((sid_text(pointer(raw.value + 8)), mask, header[0], header[1]))
        length = _bind(api, "GetSecurityDescriptorLength", [pointer], dword)(descriptor)
        if not 20 <= length <= 65536:
            raise ValueError
        return FilePolicy(
            sid_text(owner),
            bool(control.value & 0x1000),
            tuple(aces),
            hashlib.sha256(ctypes.string_at(descriptor, length)).hexdigest(),
        )
    finally:
        if descriptor.value:
            _bind(kernel, "LocalFree", [pointer], pointer)(descriptor)


def require_file_policy(name: str, observed: FilePolicy) -> None:
    rights = {
        "activation.json": 0x120089,
        "host-binding.json": 0x120089,
        "paper.sqlite": 0x12019F,
        "wake.sqlite": 0x12019F,
    }
    if (
        type(observed) is not FilePolicy
        or name not in rights
        or observed.owner_sid != ADMINISTRATORS_SID
        or observed.protected is not True
        or observed.aces != ADMIN_ACES + ((TRADING_SID, rights[name], 0, 0),)
    ):
        raise ValueError("final file policy rejected")
