"""133-W fixed no-replace relative renames only; no staging or policy writers."""

from __future__ import annotations

import ctypes
import ntpath
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict

from trading_bot.arch133_acl import read_only
from trading_bot.arch133_reprovision import reads
from trading_bot.arch133_reprovision.generation import ACTIVE, ARCHIVE, STAGE
from trading_bot.arch133_verifier import file_policy


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


def _open_rename_root(root: str) -> int:
    if root not in (ACTIVE, STAGE, r"F:\AITradingBot"):
        raise ValueError("rename root rejected")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = _bind(
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
    )(
        root,
        0x20085 if root == r"F:\AITradingBot" else 0x30081,
        7,
        None,
        3,
        0x02200000,
        None,
    )
    if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
        raise ValueError("rename handle rejected")
    return handle


def _rename(handle: int, parent: int, source: str, destination: str) -> None:
    if (source, destination) not in ((ACTIVE, ARCHIVE), (STAGE, ACTIVE)):
        raise ValueError("rename target rejected")

    # Rename the held source object relative to the held protected parent.
    # ReplaceIfExists=False; no path reopen, overwrite, fallback or retry.
    class RenameInfo(ctypes.Structure):
        _fields_ = [
            ("replace", ctypes.c_ubyte),
            ("root", ctypes.c_void_p),
            ("length", ctypes.c_uint32),
            ("name", ctypes.c_wchar * 1),
        ]

    name = ntpath.basename(destination).encode("utf-16-le")
    buffer = ctypes.create_string_buffer(RenameInfo.name.offset + len(name))
    info = RenameInfo.from_buffer(buffer)
    info.replace, info.root, info.length = 0, parent, len(name)
    ctypes.memmove(ctypes.addressof(buffer) + RenameInfo.name.offset, name, len(name))
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    if not _bind(
        api,
        "SetFileInformationByHandle",
        [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32],
        ctypes.c_int32,
    )(handle, 3, buffer, len(buffer)):
        raise ValueError("rename rejected")


class WindowsEdges:
    """Hold rename-compatible roots and read/delete-only child sharing."""

    def __init__(self) -> None:
        self.roots: dict[str, int] = {}
        self.parent = 0

    @contextmanager
    def publication_guard(self) -> Iterator[dict]:
        with ExitStack() as held:
            self.parent = _open_rename_root(r"F:\AITradingBot")
            held.callback(read_only.close_handle, self.parent)
            parent_facts, parent_security = read_only.inspect_directory_security(
                self.parent, r"F:\AITradingBot"
            )
            observed = {
                "parent": {
                    "identity": list(parent_facts.identity),
                    "security_sha256": parent_security,
                }
            }
            for root in (ACTIVE, STAGE):
                self.roots[root] = _open_rename_root(root)
                held.callback(read_only.close_handle, self.roots[root])
                root_facts, security = read_only.inspect_directory_security(
                    self.roots[root], root
                )
                files = {}
                for name in reads.FINAL_NAMES:
                    handle = reads.open_generation_file(root, name, renaming=True)
                    held.callback(read_only.close_handle, handle)
                    identity, sha = reads.file_snapshot(handle, root, name)
                    files[name] = {
                        "identity": list(identity),
                        "sha256": sha,
                        "policy": asdict(file_policy.observe_file_policy(handle)),
                    }
                observed[root] = {
                    "root_identity": list(root_facts.identity),
                    "root_security_sha256": security,
                    "files": files,
                }
            yield observed

    def archive(self) -> None:
        _rename(self.roots[ACTIVE], self.parent, ACTIVE, ARCHIVE)

    def publish(self) -> None:
        _rename(self.roots[STAGE], self.parent, STAGE, ACTIVE)
