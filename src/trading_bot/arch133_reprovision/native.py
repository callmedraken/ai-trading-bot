"""One-shot fixed Win32/SQLite staging and rename edges. Never imported by plan."""

from __future__ import annotations

import ctypes
import os
import sqlite3
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from trading_bot.arch133_acl import primitive, read_only
from trading_bot.arch133_acl.root_policy_apply import apply_root_policy_status
from trading_bot.arch133_reprovision import reads
from trading_bot.arch133_reprovision.generation import (
    ACTIVE,
    ARCHIVE,
    STAGE,
    STAGING_PARENT,
)
from trading_bot.arch133_reprovision.material import Material
from trading_bot.arch133_verifier.activation import ReviewPaperWake
from trading_bot.arch133_verifier.state_schema import (
    APPLICATION_ID,
    METADATA,
    TABLES,
    USER_VERSION,
)


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


def _policy(handle: int, rights: int | None) -> None:
    # Protected owner/DACL only; no arbitrary ACL or native path transport.
    sddl = "O:BAG:BAD:P(A;;FA;;;BA)(A;;FA;;;SY)"
    if rights is not None:
        sddl += f"(A;;0x{rights:x};;;{read_only.TRADING_SID})"
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ptr, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
    descriptor, owner, dacl = ptr(), ptr(), ptr()
    present, default = boolean(), boolean()
    try:
        if not _bind(
            api,
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            [ctypes.c_wchar_p, dword, ptr, ptr],
            boolean,
        )(sddl, 1, ctypes.byref(descriptor), None):
            raise ValueError("policy conversion rejected")
        if (
            not _bind(api, "GetSecurityDescriptorOwner", [ptr, ptr, ptr], boolean)(
                descriptor, ctypes.byref(owner), ctypes.byref(default)
            )
            or not _bind(
                api, "GetSecurityDescriptorDacl", [ptr, ptr, ptr, ptr], boolean
            )(
                descriptor,
                ctypes.byref(present),
                ctypes.byref(dacl),
                ctypes.byref(default),
            )
            or not present.value
            or not dacl.value
            or not owner.value
        ):
            raise ValueError("policy rejected")
        if _bind(
            api, "SetSecurityInfo", [ptr, dword, dword, ptr, ptr, ptr, ptr], dword
        )(handle, 1, 0x80000005, owner, None, dacl, None):
            raise ValueError("policy application rejected")
    finally:
        if descriptor.value:
            _bind(kernel, "LocalFree", [ptr], ptr)(descriptor)


def _open_mutable_file(root: str, name: str) -> int:
    if root not in (ACTIVE, STAGE) or name not in reads.FINAL_NAMES:
        raise ValueError("file target rejected")
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
    )(root + "\\" + name, 0xE0000, 1, None, 3, 0x200000, None)
    if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
        raise ValueError("file handle rejected")
    return handle


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
        0x20085 if root == r"F:\AITradingBot" else 0xF0081,
        3,
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

    name = Path(destination).name.encode("utf-16-le")
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
    def __init__(self, counters: dict[str, int]) -> None:
        self.counters = counters
        self.roots: dict[str, int] = {}
        self.parent = 0

    def stage(self, material: Material) -> None:
        for root in (STAGING_PARENT, STAGE):
            self.counters["publication_writes"] += 1
            primitive.create_admin_directory(root)
        path = Path(STAGE)
        for name, raw in (
            ("activation.json", material.activation.to_json().encode()),
            ("host-binding.json", material.host.to_json().encode()),
        ):
            self.counters["publication_writes"] += 1
            with (path / name).open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        # Create-only inside an inaccessible admin staging parent. No domain
        # execution writer or consumed publisher is reachable from this module.
        for name in ("wake.sqlite", "paper.sqlite"):
            self.counters[
                "state_mutations" if name == "wake.sqlite" else "paper_mutations"
            ] += 1
            with (path / name).open("xb"):
                pass
            connection = sqlite3.connect(path / name, timeout=0)
            try:
                with connection:
                    if name == "wake.sqlite":
                        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                        connection.execute(f"PRAGMA user_version={USER_VERSION}")
                        for _, sql in TABLES:
                            connection.execute(sql)
                        connection.executemany(
                            "INSERT INTO metadata VALUES (?, ?)", METADATA
                        )
                        activation = material.activation
                        wake = ReviewPaperWake(
                            activation=activation, updated_at=activation.created_at
                        )
                        connection.execute(
                            "INSERT INTO activations VALUES (?, ?)",
                            (str(activation.activation_id), activation.to_json()),
                        )
                        connection.execute(
                            "INSERT INTO wakes VALUES (?, ?, ?, 0)",
                            (
                                str(activation.activation_id),
                                str(wake.wake_id),
                                wake.to_json(),
                            ),
                        )
                    else:
                        for sql in PAPER_TABLES:
                            connection.execute(sql)
                        connection.executemany(
                            "INSERT INTO metadata VALUES (?, ?)",
                            (
                                ("schema_version", "2"),
                                (
                                    "starting_cash",
                                    str(material.activation.starting_cash),
                                ),
                            ),
                        )
            finally:
                connection.close()
        with ExitStack() as held:
            for name in reads.FINAL_NAMES:
                handle = _open_mutable_file(STAGE, name)
                held.callback(read_only.close_handle, handle)
                self.counters["acl_mutations"] += 1
                _policy(handle, 0x12019F if name.endswith(".sqlite") else 0x120089)
            handle = read_only.open_directory(STAGE, mutable=True)
            held.callback(read_only.close_handle, handle)
            self.counters["acl_mutations"] += 1
            if apply_root_policy_status(handle) != 0:
                raise ValueError("staged root ACL rejected")

    @contextmanager
    def publication_guard(self) -> Iterator[None]:
        # Held file handles prohibit writers/deleters across final verification,
        # archive sealing and both root renames. Directory rename may fail under
        # a Windows sharing rule: that is INDETERMINATE, never weaker retry.
        with ExitStack() as held:
            self.parent = _open_rename_root(r"F:\AITradingBot")
            held.callback(read_only.close_handle, self.parent)
            for root in (ACTIVE, STAGE):
                self.roots[root] = _open_rename_root(root)
                held.callback(read_only.close_handle, self.roots[root])
                for name in reads.FINAL_NAMES:
                    handle = reads.open_generation_file(root, name, renaming=True)
                    held.callback(read_only.close_handle, handle)
            yield

    def archive(self) -> None:
        # Seal before rename. Never discard or rewrite predecessor file bytes.
        with ExitStack() as held:
            for name in reads.FINAL_NAMES:
                handle = _open_mutable_file(ACTIVE, name)
                held.callback(read_only.close_handle, handle)
                self.counters["acl_mutations"] += 1
                _policy(handle, 0x120089)
            handle = self.roots[ACTIVE]
            self.counters["acl_mutations"] += 1
            _policy(handle, None)
        self.counters["archive_writes"] += 1
        _rename(self.roots[ACTIVE], self.parent, ACTIVE, ARCHIVE)

    def publish(self) -> None:
        self.counters["publication_writes"] += 1
        _rename(self.roots[STAGE], self.parent, STAGE, ACTIVE)


PAPER_TABLES = (
    """CREATE TABLE metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )""",
    """CREATE TABLE review_fills (
                        paper_trade_id TEXT PRIMARY KEY,
                        proposal_id TEXT NOT NULL,
                        order_id TEXT NOT NULL UNIQUE,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        desired_quantity TEXT NOT NULL,
                        approved_quantity TEXT NOT NULL,
                        risk_outcome TEXT NOT NULL,
                        risk_reason_codes TEXT NOT NULL,
                        proposal_reason TEXT NOT NULL,
                        proposal_confidence TEXT,
                        order_type TEXT NOT NULL,
                        time_in_force TEXT NOT NULL,
                        proposed_at TEXT NOT NULL,
                        limit_price TEXT,
                        reviewed_at TEXT NOT NULL,
                        market_data_disclosure TEXT,
                        order_checks_json TEXT NOT NULL,
                        adjusted_previous_close TEXT NOT NULL,
                        ask_price TEXT NOT NULL,
                        bid_price TEXT NOT NULL,
                        has_traded INTEGER NOT NULL,
                        last_non_reg_trade_price TEXT,
                        last_trade_price TEXT NOT NULL,
                        previous_close TEXT NOT NULL,
                        previous_close_date TEXT,
                        quote_state TEXT NOT NULL,
                        venue_ask_time TEXT NOT NULL,
                        venue_bid_time TEXT NOT NULL,
                        venue_last_non_reg_trade_time TEXT,
                        venue_last_trade_time TEXT NOT NULL,
                        fill_id TEXT NOT NULL UNIQUE,
                        fill_price TEXT NOT NULL,
                        commission TEXT NOT NULL,
                        slippage_basis_points TEXT NOT NULL,
                        filled_at TEXT NOT NULL
                    )""",
)
