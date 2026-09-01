"""Opt-in disposable Win32 regression; never uses either production Paper path."""

import ctypes
import os
from contextlib import ExitStack
from ctypes import wintypes
from pathlib import PureWindowsPath

import pytest

import trading_bot.runtime.windows_paper_account_provisioning as p

_OPT_IN = "AI_TRADING_BOT_RUN_P3_R1_NATIVE_RENAME"


@pytest.mark.skipif(os.name != "nt", reason="requires native Windows")
@pytest.mark.parametrize("descendant", ["directory", "direct-file", "nested-file"])
@pytest.mark.parametrize("root_delete_share", [False, True])
def test_disposable_retained_descendant_denied_then_absolute_rename(
    descendant, root_delete_share, tmp_path
):
    if os.environ.get(_OPT_IN) != "1":
        pytest.skip(f"set {_OPT_IN}=1 for the disposable native regression")
    # pytest-managed scratch is rooted by the mandatory external --basetemp.
    parent = (tmp_path / "p3-r1-native").resolve()
    production_roots = (
        PureWindowsPath(r"F:\AITradingBot\Paper"),
        PureWindowsPath(r"F:\AITradingBot\.Paper.provisioning-v1"),
    )
    assert all(
        not PureWindowsPath(parent).is_relative_to(root)
        and not root.is_relative_to(PureWindowsPath(parent))
        for root in production_roots
    )
    parent.mkdir()
    source = parent / "retained"
    final = parent / "published"
    source.mkdir()
    child = source / "child"
    child.mkdir()
    (source / "anchor").write_bytes(b"disposable direct child")
    (child / "genesis").write_bytes(b"disposable nested child")
    selected = {
        "directory": child,
        "direct-file": source / "anchor",
        "nested-file": child / "genesis",
    }[descendant]
    session = p._WindowsPublicationSession(p._P3_R1_BUNDLE)
    with ExitStack() as handles:
        handles.enter_context(
            session._open(
                PureWindowsPath(parent),
                True,
                access=p.FILE_READ_ATTRIBUTES,
                share=p.FILE_SHARE_READ | p.FILE_SHARE_WRITE,
            )
        )
        root = session._open(
            PureWindowsPath(source),
            True,
            access=p.FILE_READ_ATTRIBUTES | p.DELETE,
            share=p.FILE_SHARE_READ | (p.FILE_SHARE_DELETE if root_delete_share else 0),
        )
        handles.enter_context(root)
        retained_child = session._open(
            PureWindowsPath(selected),
            descendant == "directory",
            access=p.FILE_READ_ATTRIBUTES,
            share=p.FILE_SHARE_READ | p.FILE_SHARE_DELETE,
        )
        handles.enter_context(retained_child)
        root_identity = session._facts(root.value, True)
        name = str(final).encode("utf-16-le")
        terminator_size = len("\0".encode("utf-16-le"))
        terminator_offset = p._PaperRootRenameInfo.name.offset + len(name)
        size = max(
            ctypes.sizeof(p._PaperRootRenameInfo),
            terminator_offset + terminator_size,
        )
        buffer = ctypes.create_string_buffer(size)
        info = p._PaperRootRenameInfo.from_buffer(buffer)
        info.flags = 0
        info.root_directory = None
        info.name_length = len(name)
        ctypes.memmove(
            ctypes.addressof(buffer) + p._PaperRootRenameInfo.name.offset,
            name,
            len(name),
        )
        ctypes.memset(ctypes.addressof(buffer) + terminator_offset, 0, terminator_size)

        def rename():
            return session._call(
                "SetFileInformationByHandle",
                wintypes.BOOL,
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
                root.value,
                3,
                buffer,
                size,
            )

        assert not rename()
        assert ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED
        assert source.is_dir() and not final.exists()
        retained_child.close()
        assert retained_child.value == 0
        assert rename(), f"absolute root rename failed: {ctypes.get_last_error()}"
        # The very next native call proves the retained root's exact path.
        final_path = ctypes.create_unicode_buffer(32768)
        count = session._call(
            "GetFinalPathNameByHandleW",
            wintypes.DWORD,
            [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.WCHAR),
                wintypes.DWORD,
                wintypes.DWORD,
            ],
            root.value,
            final_path,
            len(final_path),
            0,
        )
        expected_final_path = "\\\\?\\" + str(final)
        observed_final_path = p._counted_wchar_text(final_path, count)
        assert count == len(expected_final_path)
        assert observed_final_path == expected_final_path
        assert session._facts(root.value, True) == root_identity
        assert final.is_dir() and not source.exists()
        assert (final / "anchor").read_bytes() == b"disposable direct child"
        assert (final / "child" / "genesis").read_bytes() == (
            b"disposable nested child"
        )
