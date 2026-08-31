"""Opt-in disposable Win32 regression; never uses either production Paper path."""

import ctypes
import os
from contextlib import ExitStack
from ctypes import wintypes
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory

import pytest

import trading_bot.runtime.windows_paper_account_provisioning as p

_OPT_IN = "AI_TRADING_BOT_RUN_P3_R1_NATIVE_RENAME"


@pytest.mark.skipif(os.name != "nt", reason="requires native Windows")
@pytest.mark.parametrize("descendant", ["directory", "direct-file", "nested-file"])
@pytest.mark.parametrize("root_delete_share", [False, True])
def test_disposable_retained_descendant_denied_then_absolute_rename(
    descendant, root_delete_share
):
    if os.environ.get(_OPT_IN) != "1":
        pytest.skip(f"set {_OPT_IN}=1 for the disposable native regression")
    # Worktree-owned scratch only, independent of TEMP and pytest --basetemp.
    # Resolve and reject the entire production parent before creating anything.
    repository = Path(__file__).resolve().parents[2]
    production_parent = PureWindowsPath(r"F:\AITradingBot")
    assert not PureWindowsPath(repository).is_relative_to(production_parent)
    scratch = repository / ".pytest_cache"
    assert not PureWindowsPath(scratch.resolve()).is_relative_to(production_parent)
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="p3-r1-native-", dir=scratch) as temporary:
        parent = Path(temporary).resolve()
        assert parent.is_relative_to(scratch.resolve())
        assert not PureWindowsPath(parent).is_relative_to(production_parent)
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
                share=p.FILE_SHARE_READ
                | (p.FILE_SHARE_DELETE if root_delete_share else 0),
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
            size = max(
                ctypes.sizeof(p._PaperRootRenameInfo),
                p._PaperRootRenameInfo.name.offset + len(name),
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
                [wintypes.HANDLE, ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD],
                root.value,
                final_path,
                len(final_path),
                0,
            )
            assert 0 < count < len(final_path)
            assert final_path.value == "\\\\?\\" + str(final)
            assert session._facts(root.value, True) == root_identity
            assert final.is_dir() and not source.exists()
            assert (final / "anchor").read_bytes() == b"disposable direct child"
            assert (
                final / "child" / "genesis"
            ).read_bytes() == b"disposable nested child"
