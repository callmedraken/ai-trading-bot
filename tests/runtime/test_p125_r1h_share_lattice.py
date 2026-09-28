"""Fake/source-only R1H-D tests; native loading and host mutation are denied."""

from __future__ import annotations

import ast
import ctypes
import inspect
import json
import runpy
import stat
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import p125_r1h_share_lattice as a


@pytest.fixture(autouse=True)
def deny_host_mutation(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("real host API forbidden in fake-only tests")

    monkeypatch.setattr(a.os, "mkdir", denied)
    monkeypatch.setattr(a.os, "rmdir", denied)
    monkeypatch.setattr(a.ctypes, "WinDLL", denied, raising=False)


class FakeSpace:
    def __init__(self):
        self.root = a._TEMP + "\\" + a._PREFIX + "a" * 32
        self.prepared = []
        self.cleanup_calls = 0
        self.cleanup_exact = True

    def paths(self, case):
        parent = self.root + "\\" + case.value.lower()
        return parent, parent + "\\source", parent + "\\destination"

    def guard(self, path, **kwargs):
        assert a._require_disposable_path(path) == self.root

    def create(self):
        pass

    def prepare(self, case):
        assert case not in self.prepared
        self.prepared.append(case)

    def cleanup(self):
        self.cleanup_calls += 1
        return self.cleanup_exact


class FakeNative:
    def __init__(self, space):
        self.space = space
        self.events = []
        self.objects = {}
        self.handles = {}
        self.next_handle = 100
        self.renamed = False
        self.call = a._Call(ntstatus=0, io_status=0, io_information=0)
        self.fault = None

    def open(self, path, *, share, parent=False, probe=False):
        self.events.append(("open", path, parent, probe, share))
        if self.fault == "open_source" and path.endswith("\\source"):
            raise OSError("SECRET path SID environment value")
        if path not in self.objects:
            self.objects[path] = a._Object(path, 12, 5 if parent else 6, 0x10, 1)
        handle = self.next_handle
        self.next_handle += 1
        self.handles[handle] = self.objects[path]
        return handle

    def inspect(self, handle):
        self.events.append(("inspect", handle))
        obj = self.handles[handle]
        if self.renamed:
            if self.fault == "inspect":
                raise OSError("SECRET")
            if self.fault == "pinned_wrong_id" and obj.file_id == 6:
                return replace(obj, file_id=99)
            if self.fault == "pinned_wrong_volume" and obj.file_id == 6:
                return replace(obj, volume=99)
            if self.fault == "pinned_wrong_path" and obj.file_id == 6:
                return replace(obj, final_path=obj.final_path + "wrong")
            if self.fault == "parent" and obj.file_id == 5:
                return replace(obj, file_id=99)
            if self.fault == "fresh_destination" and handle == 102:
                return replace(obj, file_id=99)
        return obj

    def present(self, path):
        self.events.append(("present", path))
        if not self.renamed and self.fault == "destination_before":
            return True
        if (
            self.renamed
            and self.fault == "source_still_present"
            and path.endswith("\\source")
        ):
            return True
        if self.renamed and self.fault == "destination_absent":
            return False
        return path in self.objects

    def rename(self, source, request):
        self.events.append(("rename", source, request))
        info = a._FileRenameInformation.from_buffer(request.buffer)
        source_object = self.handles[source]
        parent_path = source_object.final_path.rsplit("\\", 1)[0]
        assert self.handles[info.root_directory].final_path == parent_path
        assert info.replace_if_exists == 0
        assert info.file_name_length == 22
        self.renamed = True
        obj = self.handles[source]
        destination = obj.final_path.removesuffix("source") + "destination"
        self.handles[source] = obj.at(destination)
        self.objects.pop(obj.final_path)
        self.objects[destination] = obj.at(destination)
        return self.call

    def close(self, handle):
        self.events.append(("close", handle))
        if self.fault == "close_exception":
            raise OSError("SECRET")
        return self.fault != "close_false"


class FakeFunction:
    def __init__(self, result=1):
        self.result = result
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


def bound_native(monkeypatch):
    libraries = {}
    events = []

    def load(path, **kwargs):
        events.append((path, kwargs))
        library = SimpleNamespace()
        for name in (
            "CreateFileW",
            "CloseHandle",
            "GetFinalPathNameByHandleW",
            "GetFileInformationByHandle",
            "GetFileAttributesW",
            "NtSetInformationFile",
        ):
            setattr(library, name, FakeFunction(123 if name == "CreateFileW" else 1))
        libraries[path] = library
        return library

    monkeypatch.setattr(a.os, "name", "nt")
    monkeypatch.setattr(a.ctypes, "WinDLL", load)
    native = a._WindowsNative(FakeSpace())
    return native, libraries, events


def test_import_and_unflagged_entry_are_inert(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("entry crossed execution gate")

    monkeypatch.setattr(a.secrets, "token_hex", forbidden)
    monkeypatch.setattr(a, "_execute", forbidden)
    runpy.run_path(a.__file__, run_name="inert_import_test")
    assert a.main([]) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "path",
    [
        a._PRODUCTION,
        a._PRODUCTION + "\\D10",
        r"f:\aitradingbot\staging",
        r"F:\AITradingBot\retired\x",
        r"\\?\F:\AITradingBot\x",
        a._TEMP,
        a._TEMP + "\\other",
        a._TEMP + "\\" + a._PREFIX + "b" * 32 + "\\..\\..\\AITradingBot",
        a._TEMP
        + "\\"
        + a._PREFIX
        + "b" * 32
        + "\\win32_exact_length\\destination:stream",
        a._TEMP + "\\" + a._PREFIX + "b" * 32 + "\\unreviewed",
    ],
)
def test_namespace_rejects_production_aliases_and_escape(path):
    with pytest.raises(a._Blocked):
        a._require_disposable_path(path)


def test_independent_fresh_namespaces_and_unique_roots(monkeypatch):
    values = iter(("a" * 32, "b" * 32))
    monkeypatch.setattr(a.secrets, "token_hex", lambda n: next(values))
    first, second = a._DisposableSpace(), a._DisposableSpace()
    assert first.root != second.root
    triples = [first.paths(case) for case in a._Case]
    assert len({path for triple in triples for path in triple}) == 27
    assert all(
        a._require_disposable_path(path) == first.root
        for triple in triples
        for path in triple
    )
    with pytest.raises(a._Blocked):
        first.guard(second.root)


@pytest.mark.parametrize("value", [-(1 << 31) - 1, 1 << 32, True, "87"])
def test_status_range_is_bounded(value):
    with pytest.raises(a._Blocked):
        a._u32(value)


@pytest.mark.parametrize("case", list(a._Case))
def test_success_requires_all_handle_path_and_close_proofs(case):
    space = FakeSpace()
    native = FakeNative(space)
    evidence = a._run_case(case, space, native)
    assert evidence.status is a._Status.PASS
    assert evidence.RootDirectory_non_null
    assert evidence.source_present_after is False
    assert evidence.destination_present_after is True
    assert (
        evidence.same_object_after and evidence.parent_stable and evidence.close_exact
    )
    assert [event[1] for event in native.events if event[0] == "close"] == [
        102,
        101,
        100,
    ]
    assert space.prepared == [case]


@pytest.mark.parametrize(
    "fault",
    [
        "open_source",
        "destination_before",
        "inspect",
        "pinned_wrong_id",
        "pinned_wrong_volume",
        "pinned_wrong_path",
        "parent",
        "fresh_destination",
        "source_still_present",
        "destination_absent",
        "close_false",
        "close_exception",
    ],
)
def test_call_success_without_each_required_proof_never_passes(fault):
    space = FakeSpace()
    native = FakeNative(space)
    native.fault = fault
    evidence = a._run_case(a._Case.NT_SHARE_READ_CONTROL, space, native)
    assert evidence.status is not a._Status.PASS
    assert "SECRET" not in a._Transcript((evidence,), "PASS").canonical_json()
    if fault == "destination_before":
        assert not any(event[0] == "rename" for event in native.events)
    if fault == "open_source":
        assert [event[1] for event in native.events if event[0] == "close"] == [100]
    if fault in ("close_false", "close_exception"):
        assert [event[1] for event in native.events if event[0] == "close"] == [
            102,
            101,
            100,
        ]
        assert evidence.close_exact is False


@pytest.mark.parametrize(
    "status", [0x103, 1, 0x40000000, 0x80000000, 0xC000000D, 0xFFFFFFFF]
)
def test_every_nonzero_ntstatus_is_non_pass_even_with_rename_proof(status):
    space = FakeSpace()
    native = FakeNative(space)
    native.call = a._Call(ntstatus=status, io_status=0, io_information=0)
    result = a._run_case(a._Case.NT_SHARE_READ_CONTROL, space, native)
    assert result.same_object_after
    assert result.status is a._Status.NATIVE_FAILURE
    assert result.ntstatus == status


@pytest.mark.parametrize(
    "io_status,information", [(0x103, 0), (0xFFFFFFFF, 0), (0, a._POINTER_MAX)]
)
def test_malformed_or_unwritten_io_block_never_passes(io_status, information):
    space = FakeSpace()
    native = FakeNative(space)
    native.call = a._Call(ntstatus=0, io_status=io_status, io_information=information)
    assert (
        a._run_case(a._Case.NT_SHARE_READ_CONTROL, space, native).status
        is not a._Status.PASS
    )


class FakeFilesystem:
    def __init__(self, monkeypatch):
        self.dirs = {}
        self.created = []
        self.removed = []
        self.counter = 1
        for path in ("F:\\", r"F:\AI", a._TEMP):
            self.add(path)
        monkeypatch.setattr(a.os, "lstat", self.lstat)
        monkeypatch.setattr(a.os, "mkdir", self.mkdir)
        monkeypatch.setattr(a.os, "rmdir", self.rmdir)
        monkeypatch.setattr(a.Path, "resolve", lambda path, **kwargs: path)
        monkeypatch.setattr(a.secrets, "token_hex", lambda n: "a" * 32)

    def add(self, path, *, attributes=0x10):
        self.dirs[path] = SimpleNamespace(
            st_dev=12,
            st_ino=self.counter,
            st_mode=stat.S_IFDIR,
            st_file_attributes=attributes,
        )
        self.counter += 1

    def lstat(self, path):
        if path not in self.dirs:
            raise FileNotFoundError
        return self.dirs[path]

    def mkdir(self, path):
        assert path not in self.dirs
        self.created.append(path)
        self.add(path)

    def rmdir(self, path):
        assert path in self.dirs
        if any(other.startswith(path + "\\") for other in self.dirs if other != path):
            raise OSError("not empty SECRET")
        self.removed.append(path)
        del self.dirs[path]


def test_creation_and_cleanup_only_known_owned_empty_directories(monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    space = a._DisposableSpace()
    space.create()
    for case in a._Case:
        space.prepare(case)
    assert len(fs.created) == 19
    assert space.cleanup()
    assert set(fs.created) == set(fs.removed)
    assert set(fs.dirs) == {"F:\\", r"F:\AI", a._TEMP}


def test_cleanup_handles_renamed_source_without_traversal(monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    space = a._DisposableSpace()
    space.create()
    for case in a._Case:
        space.prepare(case)
        _, source, destination = space.paths(case)
        fs.dirs[destination] = fs.dirs.pop(source)
    assert space.cleanup()
    assert len(fs.removed) == 19


@pytest.mark.parametrize(
    "drift",
    [
        "junction_root",
        "junction_temp",
        "root_identity",
        "destination_identity",
        "unexpected_child",
    ],
)
def test_cleanup_cannot_follow_reparse_or_delete_unowned_content(drift, monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    space = a._DisposableSpace()
    space.create()
    for case in a._Case:
        space.prepare(case)
    parent, source, destination = space.paths(a._Case.NT_SHARE_READ_CONTROL)
    if drift == "junction_root":
        fs.dirs[space.root].st_file_attributes |= 0x400
    elif drift == "junction_temp":
        fs.dirs[a._TEMP].st_file_attributes |= 0x400
    elif drift == "root_identity":
        fs.add(space.root)
    elif drift == "destination_identity":
        fs.add(destination)
    else:
        fs.add(source + "\\unexpected")
    assert space.cleanup() is False
    if drift in ("junction_root", "junction_temp", "root_identity"):
        assert fs.removed == []
    elif drift == "destination_identity":
        assert destination not in fs.removed
    else:
        assert source not in fs.removed and source + "\\unexpected" in fs.dirs
    assert all(a._require_disposable_path(path) == space.root for path in fs.removed)


def test_existing_root_is_never_adopted_or_removed(monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    space = a._DisposableSpace()
    fs.add(space.root)
    with pytest.raises(a._Blocked):
        space.create()
    assert space.cleanup()
    assert fs.created == fs.removed == []


def test_creation_rejects_reparse_temp_before_mutation(monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    fs.dirs[a._TEMP].st_file_attributes |= 0x400
    space = a._DisposableSpace()
    with pytest.raises(a._Blocked):
        space.create()
    assert fs.created == []


@pytest.mark.parametrize("prepared_count", list(range(10)))
def test_cleanup_after_partial_case_setup(prepared_count, monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    space = a._DisposableSpace()
    space.create()
    for case in tuple(a._Case)[:prepared_count]:
        space.prepare(case)
    assert space.cleanup()
    assert set(fs.created) == set(fs.removed)


def test_unadmitted_created_root_is_retained_and_cleanup_reports_failure(monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    space = a._DisposableSpace()
    original = fs.mkdir

    def create_then_drift(path):
        original(path)
        fs.dirs[path].st_file_attributes |= 0x400

    monkeypatch.setattr(a.os, "mkdir", create_then_drift)
    with pytest.raises(a._Blocked):
        space.create()
    assert not space.cleanup()
    assert fs.removed == []
    assert space.root in fs.dirs


def test_cleanup_rejects_canonical_resolution_outside_root(monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    space = a._DisposableSpace()
    space.create()
    space.prepare(a._Case.NT_SHARE_READ_CONTROL)
    monkeypatch.setattr(a.Path, "resolve", lambda path, **kwargs: Path(a._PRODUCTION))
    assert space.cleanup() is False
    assert fs.removed == []


def test_creation_collision_does_not_adopt_or_remove_existing_root(monkeypatch):
    fs = FakeFilesystem(monkeypatch)
    space = a._DisposableSpace()

    def collide(path):
        fs.add(path)
        raise FileExistsError("SECRET")

    monkeypatch.setattr(a.os, "mkdir", collide)
    with pytest.raises(FileExistsError):
        space.create()
    assert space.cleanup()
    assert fs.removed == []


@pytest.mark.parametrize(
    "attributes,error,expected",
    [
        (0x10, None, True),
        (0xFFFFFFFF, 2, False),
        (0xFFFFFFFF, 3, False),
        (0xFFFFFFFF, 5, None),
        (0x410, None, None),
        (0x80, None, None),
    ],
)
def test_fresh_presence_never_treats_access_failure_or_reparse_as_absence(
    attributes, error, expected, monkeypatch
):
    native, _, _ = bound_native(monkeypatch)
    native._attributes.result = attributes
    monkeypatch.setattr(a.ctypes, "get_last_error", lambda: error, raising=False)
    path = native.space.paths(a._Case.NT_SHARE_READ_CONTROL)[2]
    if expected is None:
        with pytest.raises(a._Blocked):
            native.present(path)
    else:
        assert native.present(path) is expected


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "path",
        "zero_length",
        "long_path",
        "info_false",
        "id_zero",
        "reparse",
        "file",
        "links",
    ],
)
def test_handle_inspection_exact_identity_and_namespace(fault, monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    destination = native.space.paths(a._Case.NT_SHARE_READ_CONTROL)[2]

    def final(handle, buffer, capacity, flags):
        assert (handle, capacity, flags) == (101, 32768, 0)
        path = a._PRODUCTION if fault == "path" else destination
        buffer.value = "\\\\?\\" + path
        return (
            0
            if fault == "zero_length"
            else capacity
            if fault == "long_path"
            else len(buffer.value)
        )

    def info(handle, pointer):
        values = ctypes.cast(pointer, ctypes.POINTER(a._ByHandleInfo)).contents
        values.volume_serial = 12
        values.file_index_high = 2
        values.file_index_low = 3
        values.attributes = (
            0x410 if fault == "reparse" else 0x80 if fault == "file" else 0x10
        )
        values.links = 2 if fault == "links" else 1
        if fault == "id_zero":
            values.file_index_high = values.file_index_low = 0
        return 0 if fault == "info_false" else 1

    native._final = final
    native._info = info
    if fault is None:
        assert native.inspect(101) == a._Object(destination, 12, (2 << 32) | 3, 0x10, 1)
    else:
        with pytest.raises((a._Blocked, AssertionError)):
            native.inspect(101)


def test_rejected_cli_does_not_echo_caller_paths_or_secrets(capsys):
    with pytest.raises(SystemExit) as caught:
        a.main([a._EXECUTE, "--root", r"F:\AITradingBot\SECRET"])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "invalid_arguments\n"


@pytest.mark.parametrize(
    "argv",
    [
        ["--execute-disposable"],
        ["--execute-disposable-r1h-share-lattic"],
        ["--execute-disposable-r1h-acceptance"],
        ["--execute-disposable-r1h-share-diagnosis"],
        [a._EXECUTE, "--root", a._PRODUCTION],
        [a._EXECUTE, "--path", a._TEMP],
        [a._EXECUTE, a._PRODUCTION],
        [a._EXECUTE + "=true"],
        [a._EXECUTE, a._EXECUTE],
        [a._EXECUTE, "--"],
        ["--", a._EXECUTE],
    ],
)
def test_exact_cli_rejects_abbreviations_extras_and_duplicate_flag(
    argv, monkeypatch, capsys
):
    monkeypatch.setattr(a, "_execute", lambda: pytest.fail("must remain inert"))
    with pytest.raises(SystemExit) as caught:
        a.main(argv)
    assert caught.value.code == 2
    assert capsys.readouterr().err == "invalid_arguments\n"


def test_exact_flag_and_process_argv_emit_one_transcript(monkeypatch, capsys):
    space = FakeSpace()
    monkeypatch.setattr(a, "_DisposableSpace", lambda: space)
    monkeypatch.setattr(a, "_WindowsNative", FakeNative)
    transcript = a._execute()
    monkeypatch.setattr(a, "_execute", lambda: transcript)
    assert a.main([a._EXECUTE]) == 0
    assert capsys.readouterr().out == transcript.canonical_json() + "\n"
    monkeypatch.setattr(a.sys, "argv", ["script", a._EXECUTE])
    assert a.main() == 0
    assert capsys.readouterr().out == transcript.canonical_json() + "\n"
    assert list(inspect.signature(a._execute).parameters) == []
    assert list(inspect.signature(a._DisposableSpace).parameters) == []


def test_help_is_inert(monkeypatch, capsys):
    monkeypatch.setattr(a, "_execute", lambda: pytest.fail("help crossed gate"))
    with pytest.raises(SystemExit) as caught:
        a.main(["--help"])
    assert caught.value.code == 0
    assert a._EXECUTE in capsys.readouterr().out


@pytest.mark.parametrize("case", list(a._Case))
def test_exact_native_buffer_and_sentinel_fields(case):
    a._require_layout()
    request = a._request(0x1234)
    info = a._FileRenameInformation.from_buffer(request.buffer)
    assert info.root_directory == 0x1234
    assert info.flags == info.replace_if_exists == 0
    assert info.file_name_length == request.name_length == 22
    offset = a._FileRenameInformation.file_name.offset
    assert request.size == len(request.buffer.raw) == offset + 22
    assert request.buffer.raw[offset:] == "destination".encode("utf-16-le")
    assert request.buffer.raw[:offset] == (bytes(info)[:offset])
    assert request.io.status == -1 and request.io.information == a._POINTER_MAX
    assert request.size == (42 if ctypes.sizeof(ctypes.c_void_p) == 8 else 34)


@pytest.mark.parametrize(
    "handle", [0, a._INVALID_HANDLE, None, True, -1, a._POINTER_MAX + 1]
)
def test_invalid_root_handle_rejected(handle):
    with pytest.raises(a._Blocked):
        a._request(handle)


def test_exact_native_layout():
    width = ctypes.sizeof(ctypes.c_void_p)
    expected = (8, 16, 20, 24) if width == 8 else (4, 8, 12, 16)
    layout = a._FileRenameInformation
    assert (
        layout.root_directory.offset,
        layout.file_name_length.offset,
        layout.file_name.offset,
        ctypes.sizeof(layout),
    ) == expected
    assert layout.replace_if_exists.offset == 0
    assert ctypes.sizeof(a._RenameFlags) == 4
    assert ctypes.sizeof(layout._fields_[-1][1]) == 2
    assert a._IoStatusBlock.status.offset == a._IoStatusBlock.pointer.offset == 0
    assert a._IoStatusBlock.information.offset == width
    assert ctypes.sizeof(a._IoStatusBlock) == width * 2
    assert ctypes.sizeof(a._IoStatusUnion) == width
    assert ctypes.sizeof(a._IoStatusUnion._fields_[0][1]) == 4
    assert ctypes.sizeof(a._ByHandleInfo) == 52


def test_system_bindings_and_only_nt_mutation_api(monkeypatch):
    native, libraries, events = bound_native(monkeypatch)
    assert events == [
        (r"C:\Windows\System32\kernel32.dll", {"use_last_error": True}),
        (r"C:\Windows\System32\ntdll.dll", {}),
    ]
    assert (
        native._nt_set
        is libraries[r"C:\Windows\System32\ntdll.dll"].NtSetInformationFile
    )
    assert native._nt_set.argtypes == [
        ctypes.c_void_p,
        ctypes.POINTER(a._IoStatusBlock),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int32,
    ]
    assert native._nt_set.restype is ctypes.c_int32
    assert not hasattr(native, "_set")
    assert set(vars(libraries[r"C:\Windows\System32\kernel32.dll"])) == {
        "CreateFileW",
        "CloseHandle",
        "GetFinalPathNameByHandleW",
        "GetFileInformationByHandle",
        "GetFileAttributesW",
        "NtSetInformationFile",
    }


MATRIX = [
    ("NT_SHARE_READ_CONTROL", "READ", 1, "READ", 1),
    ("NT_SOURCE_SHARE_DELETE", "READ_DELETE", 5, "READ", 1),
    ("NT_PARENT_SHARE_DELETE", "READ", 1, "READ_DELETE", 5),
    ("NT_BOTH_SHARE_DELETE", "READ_DELETE", 5, "READ_DELETE", 5),
    ("NT_SOURCE_SHARE_ALL", "READ_WRITE_DELETE", 7, "READ", 1),
    ("NT_PARENT_SHARE_ALL", "READ", 1, "READ_WRITE_DELETE", 7),
    ("NT_SOURCE_SHARE_ALL_PARENT_DELETE", "READ_WRITE_DELETE", 7, "READ_DELETE", 5),
    ("NT_SOURCE_SHARE_DELETE_PARENT_ALL", "READ_DELETE", 5, "READ_WRITE_DELETE", 7),
    ("NT_BOTH_SHARE_ALL", "READ_WRITE_DELETE", 7, "READ_WRITE_DELETE", 7),
]


def test_frozen_nine_case_matrix_only_share_access_varies(monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    assert [case.value for case in a._Case] == [row[0] for row in MATRIX]
    normalized = []
    for case, row in zip(a._Case, MATRIX, strict=True):
        source_share, parent_share = a._MATRIX[case]
        assert (
            source_share.value,
            source_share.mask,
            parent_share.value,
            parent_share.mask,
        ) == row[1:]
        parent, source, destination = native.space.paths(case)
        native.open(parent, share=parent_share, parent=True)
        native.open(source, share=source_share)
        native.open(destination, share=a._Share.READ_WRITE_DELETE, probe=True)
        calls = native._create.calls[-3:]
        assert calls == [
            (parent, 0x1200A5, row[4], None, 3, 0x02200000, None),
            (source, 0x130081, row[2], None, 3, 0x02200000, None),
            (destination, 0x80, 7, None, 3, 0x02200000, None),
        ]
        normalized.append(tuple((call[1],) + call[3:] for call in calls))
        request = a._request(100)
        assert request.buffer.raw == a._request(100).buffer.raw
    assert all(value == normalized[0] for value in normalized)
    assert a._SOURCE_ACCESS & a._DELETE


@pytest.mark.parametrize(
    "status", [0, 0x103, 1, 0x40000000, -1073741757, -1073741811, -1]
)
def test_exact_nt_call_class_status_io_capture_and_storage_lifetime(
    status, monkeypatch
):
    native, _, _ = bound_native(monkeypatch)
    monkeypatch.setattr(
        a.ctypes,
        "get_last_error",
        lambda: pytest.fail("NT uses raw status"),
        raising=False,
    )
    request = a._request(100)

    def nt_set(handle, io_pointer, buffer_pointer, size, kind):
        assert (handle, size, kind) == (101, request.size, 10)
        io = ctypes.cast(io_pointer, ctypes.POINTER(a._IoStatusBlock)).contents
        assert io.status == -1 and io.information == a._POINTER_MAX
        io.status = status
        io.information = 0
        info = ctypes.cast(
            buffer_pointer, ctypes.POINTER(a._FileRenameInformation)
        ).contents
        assert info.root_directory == 100 and info.flags == 0
        assert info.file_name_length == 22
        return status

    native._nt_set = nt_set
    result = native.rename(101, request)
    assert result.ntstatus == result.io_status == status & 0xFFFFFFFF
    assert result.io_information == 0
    assert result.exact_success(request.size) is (status == 0)
    native.close(101)
    native.close(100)
    assert native._requests == [request]


def test_native_sharing_violation_preserves_unwritten_io_sentinels(monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    native._nt_set.result = -1073741757
    request = a._request(100)
    result = native.rename(101, request)
    assert result == a._Call(0xC0000043, 0xFFFFFFFF, a._POINTER_MAX)
    assert not result.exact_success(request.size)


@pytest.mark.parametrize("field", ["ntstatus", "io_status", "io_information"])
@pytest.mark.parametrize("value", [-1, True, "SECRET", 1.5, 1 << 65])
def test_call_fields_reject_unbounded_or_unsanitized_material(field, value):
    with pytest.raises(a._Blocked):
        a._Call(**{field: value})


@pytest.mark.parametrize(
    "information,passed",
    [(None, False), (0, True), (42, True), (43, False), (a._POINTER_MAX, False)],
)
def test_io_information_bound_is_exact(information, passed):
    assert a._Call(0, 0, information).exact_success(42) is passed


def test_missing_nt_or_io_status_never_passes():
    assert not a._Call(None, 0, 0).exact_success(42)
    assert not a._Call(0, None, 0).exact_success(42)


def test_execute_runs_nine_independent_cases_with_only_fakes(monkeypatch):
    space = FakeSpace()
    instances = []

    def native_factory(selected):
        result = FakeNative(selected)
        instances.append(result)
        return result

    monkeypatch.setattr(a, "_DisposableSpace", lambda: space)
    monkeypatch.setattr(a, "_WindowsNative", native_factory)
    transcript = a._execute()
    assert [record.case for record in transcript.cases] == list(a._Case)
    assert all(record.status is a._Status.PASS for record in transcript.cases)
    assert transcript.cleanup == "PASS"
    assert space.prepared == list(a._Case) and space.cleanup_calls == 1
    opens = [event for event in instances[0].events if event[0] == "open"]
    assert len(opens) == 27 and len({event[1] for event in opens}) == 27
    for index, case in enumerate(a._Case):
        source_share, parent_share = a._MATRIX[case]
        assert [event[4] for event in opens[index * 3 : index * 3 + 3]] == [
            parent_share,
            source_share,
            a._Share.READ_WRITE_DELETE,
        ]


def test_evidence_frozen_before_cleanup_even_when_cleanup_fails(monkeypatch):
    space = FakeSpace()
    records = []
    original = a._run_case

    def run_case(case, selected_space, native):
        assert selected_space is space and space.cleanup_calls == 0
        evidence = original(case, selected_space, native)
        records.append(evidence)
        return evidence

    def cleanup():
        assert len(records) == 9
        assert all(record.status is a._Status.PASS for record in records)
        with pytest.raises(FrozenInstanceError):
            records[0].status = a._Status.BLOCKED
        return False

    monkeypatch.setattr(a, "_DisposableSpace", lambda: space)
    monkeypatch.setattr(a, "_WindowsNative", FakeNative)
    monkeypatch.setattr(a, "_run_case", run_case)
    space.cleanup = cleanup
    transcript = a._execute()
    assert transcript.cases == tuple(records) and transcript.cleanup == "FAILURE"


def test_transcript_exact_fields_sanitization_determinism_and_bound():
    def transcript(character):
        space = FakeSpace()
        space.root = space.root[:-32] + character * 32
        records = tuple(a._run_case(case, space, FakeNative(space)) for case in a._Case)
        return a._Transcript(records, "PASS").canonical_json()

    encoded = transcript("a")
    assert encoded == transcript("b")
    decoded = json.loads(encoded)
    assert encoded == json.dumps(decoded, sort_keys=True, separators=(",", ":"))
    assert set(decoded) == {"cases", "cleanup"}
    expected = {
        "case",
        "source_share",
        "source_share_mask",
        "parent_share",
        "parent_share_mask",
        "passed_buffer_size",
        "FileNameLength",
        "RootDirectory_non_null",
        "ntstatus",
        "io_status",
        "io_information",
        "source_present_after",
        "destination_present_after",
        "same_object_after",
        "parent_stable",
        "close_exact",
        "status",
    }
    assert all(set(case) == expected for case in decoded["cases"])
    assert len(encoded) < 8192
    for case, row in zip(decoded["cases"], MATRIX, strict=True):
        assert (
            case["case"],
            case["source_share"],
            case["source_share_mask"],
            case["parent_share"],
            case["parent_share_mask"],
        ) == row
    for forbidden in (
        "F:",
        "C:",
        "SECRET",
        "S-1-",
        "handle",
        "environment",
        "traceback",
        "ACL",
        "SID",
    ):
        assert forbidden not in encoded


@pytest.mark.parametrize("failure", ["native_binding", "layout", "entropy", "cleanup"])
def test_host_failures_emit_only_bounded_transcript(failure, monkeypatch):
    space = FakeSpace()

    def failed(*args, **kwargs):
        raise OSError(r"SECRET SID ACL F:\AITradingBot environment")

    monkeypatch.setattr(a, "_DisposableSpace", lambda: space)
    monkeypatch.setattr(a, "_WindowsNative", FakeNative)
    if failure == "native_binding":
        monkeypatch.setattr(a, "_WindowsNative", failed)
    elif failure == "layout":
        monkeypatch.setattr(a, "_require_layout", failed)
    elif failure == "entropy":
        monkeypatch.setattr(a, "_DisposableSpace", failed)
    else:
        space.cleanup = failed
    transcript = a._execute()
    assert len(transcript.cases) == 9
    if failure == "cleanup":
        assert all(record.status is a._Status.PASS for record in transcript.cases)
        assert transcript.cleanup == "FAILURE"
    else:
        assert all(record.status is a._Status.BLOCKED for record in transcript.cases)
    encoded = transcript.canonical_json()
    assert len(encoded) < 8192
    for forbidden in ("SECRET", "SID", "ACL", "F:", "environment", "OSError"):
        assert forbidden not in encoded


@pytest.mark.parametrize("result", [None, 0, a._INVALID_HANDLE])
def test_native_open_failure_is_fail_closed(result, monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    native._create.result = result
    with pytest.raises(a._Blocked):
        native.open(
            native.space.paths(a._Case.NT_SHARE_READ_CONTROL)[1], share=a._Share.READ
        )


def test_native_open_rejects_unreviewed_share_and_probe_semantics(monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    path = native.space.paths(a._Case.NT_SHARE_READ_CONTROL)[1]
    for share, probe in [(1, False), ("READ", False), (a._Share.READ, True)]:
        with pytest.raises(a._Blocked):
            native.open(path, share=share, probe=probe)
    assert native._create.calls == []


@pytest.mark.parametrize(
    "cleanup,anchored,expected",
    [("PASS", True, 0), ("FAILURE", True, 1), ("PASS", False, 1)],
)
def test_cli_exit_reports_execution_not_native_success(
    cleanup, anchored, expected, monkeypatch, capsys
):
    space = FakeSpace()
    records = tuple(a._run_case(case, space, FakeNative(space)) for case in a._Case)
    records = tuple(
        replace(
            record,
            status=a._Status.NATIVE_FAILURE,
            ntstatus=0xC0000043,
            RootDirectory_non_null=anchored,
        )
        for record in records
    )
    result = a._Transcript(records, cleanup)
    monkeypatch.setattr(a, "_execute", lambda: result)
    assert a.main([a._EXECUTE]) == expected
    assert capsys.readouterr().out == result.canonical_json() + "\n"


def test_no_production_or_external_effect_surface_and_reference_invariants():
    source = Path(a.__file__).read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports <= {
        "__future__",
        "argparse",
        "ctypes",
        "json",
        "ntpath",
        "os",
        "re",
        "secrets",
        "stat",
        "sys",
        "dataclasses",
        "enum",
        "pathlib",
    }
    for forbidden in (
        "p125_replace_d10",
        "p125_recover_d10",
        "p125_retire_old_d10",
        "d10_protected",
        "subprocess",
        "scheduler",
        "sign_trust",
        "activate",
        "activation",
        "provider",
        "paper",
        "Paper-v2",
        "broker",
        "live",
        "SetFileInformationByHandle",
        "RtlNtStatusToDosError",
        "rmtree",
        "unlink",
        "scandir",
        "listdir",
        "walk(",
    ):
        assert forbidden not in source
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(
        isinstance(node.func, ast.Attribute)
        and node.func.attr in {"rename", "replace", "remove"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        for node in calls
    )
    parser_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "_ArgumentParser"
    ]
    assert len(parser_calls) == 1
    assert any(
        keyword.arg == "allow_abbrev" and ast.literal_eval(keyword.value) is False
        for keyword in parser_calls[0].keywords
    )
    arguments = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
    ]
    assert len(arguments) == 1 and ast.unparse(arguments[0].args[0]) == "_EXECUTE"
    reference = ast.parse(
        Path(a.__file__)
        .with_name("p125_r1h_share_diagnosis.py")
        .read_text(encoding="utf-8-sig")
    )

    def definitions(module):
        return {
            node.name: node
            for node in module.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        }

    current, accepted = definitions(tree), definitions(reference)
    for name in (
        "_RenameFlags",
        "_FileRenameInformation",
        "_IoStatusUnion",
        "_IoStatusBlock",
        "_ByHandleInfo",
        "_Object",
        "_DisposableSpace",
    ):
        assert ast.dump(current[name]) == ast.dump(accepted[name])
    for name in ("inspect", "present", "close"):
        current_method = next(
            node
            for node in current["_WindowsNative"].body
            if getattr(node, "name", None) == name
        )
        accepted_method = next(
            node
            for node in accepted["_WindowsNative"].body
            if getattr(node, "name", None) == name
        )
        assert ast.dump(current_method) == ast.dump(accepted_method)
    for name in (
        "_DELETE",
        "_READ_CONTROL",
        "_SYNCHRONIZE",
        "_SOURCE_ACCESS",
        "_PARENT_ACCESS",
        "_NOFOLLOW_DIRECTORY",
    ):

        def assignment(module, selected_name=name):
            return next(
                node.value
                for node in module.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == selected_name
                    for target in node.targets
                )
            )

        assert ast.dump(assignment(tree)) == ast.dump(assignment(reference))


def test_entire_accepted_case_proof_is_constant_except_shares_and_evidence():
    current_tree = ast.parse(Path(a.__file__).read_text(encoding="utf-8-sig"))
    accepted_tree = ast.parse(
        Path(a.__file__)
        .with_name("p125_r1h_share_diagnosis.py")
        .read_text(encoding="utf-8-sig")
    )

    class Normalize(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id == "_request":
                if len(node.args) == 2:
                    node.args.pop(0)
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {"rename", "exact_success"}:
                    if isinstance(node.args[0], ast.Name) and node.args[0].id == "case":
                        node.args.pop(0)
                if node.func.attr == "open":
                    node.keywords = [
                        keyword for keyword in node.keywords if keyword.arg != "share"
                    ]
            return node

    def proof(tree):
        function = next(
            node for node in tree.body if getattr(node, "name", None) == "_run_case"
        )
        # The only non-call differences are share selection and transcript fields.
        function.body = [
            node
            for node in function.body
            if not isinstance(node, ast.Return)
            and not (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Subscript)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "_MATRIX"
            )
        ]
        return ast.dump(Normalize().visit(function))

    assert proof(current_tree) == proof(accepted_tree)


@pytest.mark.parametrize(
    "fault",
    ["parent_path", "source_path", "volume", "parent_recheck", "source_recheck"],
)
def test_precall_path_volume_and_stability_failure_blocks_before_mutation(fault):
    space = FakeSpace()
    native = FakeNative(space)
    original = native.inspect
    seen = {}

    def inspect_handle(handle):
        obj = original(handle)
        seen[handle] = seen.get(handle, 0) + 1
        if fault == "parent_path" and handle == 100:
            return replace(obj, final_path=obj.final_path + "wrong")
        if fault == "source_path" and handle == 101:
            return replace(obj, final_path=obj.final_path + "wrong")
        if fault == "volume" and handle == 101:
            return replace(obj, volume=99)
        if fault == "parent_recheck" and handle == 100 and seen[handle] == 2:
            return replace(obj, file_id=99)
        if fault == "source_recheck" and handle == 101 and seen[handle] == 2:
            return replace(obj, file_id=99)
        return obj

    native.inspect = inspect_handle
    record = a._run_case(a._Case.NT_SHARE_READ_CONTROL, space, native)
    assert record.status is a._Status.BLOCKED
    assert not record.RootDirectory_non_null
    assert not any(event[0] == "rename" for event in native.events)
    assert [event[1] for event in native.events if event[0] == "close"] == [101, 100]


def test_failed_native_call_keeps_fresh_unchanged_namespace_evidence():
    space = FakeSpace()
    native = FakeNative(space)

    def unchanged(source, request):
        native.events.append(("rename", source, request))
        return a._Call(0xC0000043, 0xFFFFFFFF, a._POINTER_MAX)

    native.rename = unchanged
    record = a._run_case(a._Case.NT_SHARE_READ_CONTROL, space, native)
    assert record.status is a._Status.NATIVE_FAILURE
    assert (
        record.source_present_after is True
        and record.destination_present_after is False
    )
    assert (
        record.same_object_after is False
        and record.parent_stable
        and record.close_exact
    )
    assert record.ntstatus == 0xC0000043
    assert record.io_status == 0xFFFFFFFF and record.io_information == a._POINTER_MAX


def test_postcall_probe_open_failure_closes_both_pins_and_never_passes():
    space = FakeSpace()
    native = FakeNative(space)
    original = native.open

    def open_handle(path, **kwargs):
        if kwargs.get("probe"):
            raise OSError("SECRET")
        return original(path, **kwargs)

    native.open = open_handle
    record = a._run_case(a._Case.NT_SHARE_READ_CONTROL, space, native)
    assert record.status is a._Status.PROOF_FAILURE
    assert record.ntstatus == 0 and record.same_object_after is False
    assert [event[1] for event in native.events if event[0] == "close"] == [101, 100]


@pytest.mark.parametrize(
    "path",
    [
        r"\\?\F:\AITradingBot",
        r"\\.\F:\AITradingBot\D10",
        r"\??\F:\AITradingBot",
        r"F:\AITRAD~1\D10",
        r"F:\AI\temp\..\..\AITradingBot\D10",
        r"f:/aitradingbot/D10",
    ],
)
def test_other_production_aliases_are_never_admitted(path):
    with pytest.raises(a._Blocked):
        a._require_disposable_path(path)


# Pure review-rule oracle only. The host script never imports or calls this
# analysis, and its transcript carries no selection or production authority.
NO_SELECTION = "NO_SELECTION"


def strictly_narrower(left: a._Evidence, right: a._Evidence) -> bool:
    pairs = (
        (left.source_share_mask, right.source_share_mask),
        (left.parent_share_mask, right.parent_share_mask),
    )
    return all(narrow & broad == narrow for narrow, broad in pairs) and any(
        narrow != broad for narrow, broad in pairs
    )


def minimal_passes(records: tuple[a._Evidence, ...]) -> tuple[a._Case, ...]:
    return tuple(
        case
        for case in a._Case
        for record in records
        if record.case is case
        and record.status is a._Status.PASS
        and all(
            narrower.status is not a._Status.PASS
            for narrower in records
            if strictly_narrower(narrower, record)
        )
    )


def selection_analysis(transcript: a._Transcript) -> a._Case | str:
    """Pure test oracle for section 8.4.2; never part of the host entry point."""
    records = transcript.cases
    if (
        transcript.cleanup != "PASS"
        or len(records) != 9
        or {record.case for record in records} != set(a._Case)
    ):
        return NO_SELECTION
    for record in records:
        source_share, parent_share = a._MATRIX[record.case]
        if (
            record.source_share is not source_share
            or record.parent_share is not parent_share
            or record.source_share_mask != source_share.mask
            or record.parent_share_mask != parent_share.mask
            or record.passed_buffer_size != a._buffer_size()
            or record.FileNameLength != 22
            or record.RootDirectory_non_null is not True
            or record.parent_stable is not True
            or record.close_exact is not True
            or record.ntstatus is None
            or record.io_status is None
            or record.io_information is None
        ):
            return NO_SELECTION
        try:
            call = a._Call(record.ntstatus, record.io_status, record.io_information)
        except a._Blocked:
            return NO_SELECTION
        if record.status is a._Status.PASS:
            if not (
                call.exact_success(record.passed_buffer_size)
                and record.source_present_after is False
                and record.destination_present_after is True
                and record.same_object_after is True
            ):
                return NO_SELECTION
        elif record.status is a._Status.NATIVE_FAILURE:
            if not (
                record.ntstatus != 0
                and record.source_present_after is True
                and record.destination_present_after is False
                and record.same_object_after is False
            ):
                return NO_SELECTION
        else:
            return NO_SELECTION
    by_case = {record.case: record for record in records}
    # Reproduction controls gate review eligibility, never host row outcomes.
    if (
        by_case[a._Case.NT_SHARE_READ_CONTROL].ntstatus != 0xC0000043
        or by_case[a._Case.NT_BOTH_SHARE_ALL].status is not a._Status.PASS
    ):
        return NO_SELECTION
    minimal = minimal_passes(records)
    return minimal[0] if len(minimal) == 1 else NO_SELECTION


def fake_review_transcript(pass_cases: set[a._Case]) -> a._Transcript:
    records = []
    for case in a._Case:
        space = FakeSpace()
        native = FakeNative(space)
        if case not in pass_cases:

            def unchanged(source, request):
                return a._Call(0xC0000043, 0xFFFFFFFF, a._POINTER_MAX)

            native.rename = unchanged
        records.append(a._run_case(case, space, native))
    return a._Transcript(tuple(records), "PASS")


@pytest.mark.parametrize("candidate", list(a._Case)[1:])
def test_unique_minimal_pass_requires_all_strictly_narrower_pairs_non_pass(candidate):
    all_pass = fake_review_transcript(set(a._Case)).cases
    chosen = next(record for record in all_pass if record.case is candidate)
    pass_cases = {
        record.case
        for record in all_pass
        if record == chosen or strictly_narrower(chosen, record)
    }
    transcript = fake_review_transcript(pass_cases)
    assert minimal_passes(transcript.cases) == (candidate,)
    assert selection_analysis(transcript) is candidate
    assert (
        selection_analysis(replace(transcript, cases=transcript.cases[::-1]))
        is candidate
    )
    for narrower in transcript.cases:
        if strictly_narrower(narrower, chosen):
            assert narrower.status is a._Status.NATIVE_FAILURE
            changed = fake_review_transcript(pass_cases | {narrower.case})
            assert candidate not in minimal_passes(changed.cases)


def test_all_complete_pass_patterns_follow_partial_order_without_preference():
    cases = tuple(a._Case)
    ranks = ((0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2), (2, 1), (1, 2), (2, 2))
    # Both prior controls reproduced; enumerate every interior PASS pattern.
    for bits in range(1 << 7):
        indices = {8} | {index + 1 for index in range(7) if bits & (1 << index)}
        expected = tuple(
            cases[index]
            for index in sorted(indices)
            if not any(
                other != index
                and ranks[other][0] <= ranks[index][0]
                and ranks[other][1] <= ranks[index][1]
                for other in indices
            )
        )
        transcript = fake_review_transcript({cases[index] for index in indices})
        assert minimal_passes(transcript.cases) == expected
        assert selection_analysis(transcript) == (
            expected[0] if len(expected) == 1 else NO_SELECTION
        )


@pytest.mark.parametrize(
    "first,second",
    [
        (a._Case.NT_SOURCE_SHARE_DELETE, a._Case.NT_PARENT_SHARE_DELETE),
        (a._Case.NT_SOURCE_SHARE_ALL, a._Case.NT_PARENT_SHARE_ALL),
        (
            a._Case.NT_SOURCE_SHARE_ALL_PARENT_DELETE,
            a._Case.NT_SOURCE_SHARE_DELETE_PARENT_ALL,
        ),
    ],
)
def test_incomparable_minimal_pass_pairs_produce_no_selection(first, second):
    transcript = fake_review_transcript({first, second, a._Case.NT_BOTH_SHARE_ALL})
    assert set(minimal_passes(transcript.cases)) == {first, second}
    assert selection_analysis(transcript) == NO_SELECTION


@pytest.mark.parametrize("case", list(a._Case))
@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "blocked",
        "proof_failure",
        "missing_ntstatus",
        "missing_io_status",
        "missing_io_information",
        "unbounded_information",
        "no_anchor",
        "parent_drift",
        "close_failure",
        "missing_presence",
        "share_drift",
        "buffer_drift",
    ],
)
def test_missing_incomplete_or_unclean_evidence_produces_no_selection(case, fault):
    transcript = fake_review_transcript({a._Case.NT_BOTH_SHARE_ALL})
    index = tuple(a._Case).index(case)
    records = list(transcript.cases)
    if fault == "missing":
        records.pop(index)
    elif fault == "duplicate":
        records[index] = records[(index + 1) % 9]
    else:
        change = {
            "blocked": {"status": a._Status.BLOCKED},
            "proof_failure": {"status": a._Status.PROOF_FAILURE},
            "missing_ntstatus": {"ntstatus": None},
            "missing_io_status": {"io_status": None},
            "missing_io_information": {"io_information": None},
            "unbounded_information": {"io_information": a._POINTER_MAX + 1},
            "no_anchor": {"RootDirectory_non_null": False},
            "parent_drift": {"parent_stable": False},
            "close_failure": {"close_exact": False},
            "missing_presence": {"source_present_after": None},
            "share_drift": {"source_share_mask": 0},
            "buffer_drift": {"passed_buffer_size": a._buffer_size() + 4},
        }[fault]
        records[index] = replace(records[index], **change)
    assert selection_analysis(replace(transcript, cases=tuple(records))) == NO_SELECTION


@pytest.mark.parametrize(
    "control", [a._Case.NT_SHARE_READ_CONTROL, a._Case.NT_BOTH_SHARE_ALL]
)
def test_controls_must_reproduce_previous_evidence_before_review_selection(control):
    pass_cases = {a._Case.NT_BOTH_SHARE_ALL}
    if control is a._Case.NT_SHARE_READ_CONTROL:
        pass_cases.add(control)
    else:
        pass_cases.clear()
    assert selection_analysis(fake_review_transcript(pass_cases)) == NO_SELECTION


def test_cleanup_failure_and_no_pass_produce_no_selection():
    transcript = fake_review_transcript({a._Case.NT_BOTH_SHARE_ALL})
    assert selection_analysis(replace(transcript, cleanup="FAILURE")) == NO_SELECTION
    assert selection_analysis(fake_review_transcript(set())) == NO_SELECTION


@pytest.mark.parametrize("case", list(a._Case))
@pytest.mark.parametrize("passes", [False, True])
def test_every_row_including_both_controls_has_observed_not_hardcoded_outcome(
    case, passes
):
    transcript = fake_review_transcript({case} if passes else set())
    record = next(item for item in transcript.cases if item.case is case)
    assert record.status is (a._Status.PASS if passes else a._Status.NATIVE_FAILURE)
    assert record.ntstatus == (0 if passes else 0xC0000043)


def test_entire_host_module_is_accepted_reference_except_closed_matrix_and_namespace():
    current = ast.parse(Path(a.__file__).read_text(encoding="utf-8-sig"))
    reference = ast.parse(
        Path(a.__file__)
        .with_name("p125_r1h_share_diagnosis.py")
        .read_text(encoding="utf-8-sig")
    )

    def frozen(tree):
        tree.body = [
            node
            for node in tree.body[1:]  # Diagnostic module docstring.
            if not (isinstance(node, ast.ClassDef) and node.name == "_Case")
            and not (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id in {"_EXECUTE", "_PREFIX", "_MATRIX"}
                    for target in node.targets
                )
            )
        ]
        return ast.dump(tree)

    assert frozen(current) == frozen(reference)
    assert a._EXECUTE == "--execute-disposable-r1h-share-lattice"
    assert a._TEMP == r"F:\AI\temp"
    assert a._PREFIX == "p125-r1h-share-lattice-"


def test_all_rows_finish_before_any_cleanup_with_native_failures_preserved(monkeypatch):
    space = FakeSpace()
    records = []
    original = a._run_case

    def run_case(case, selected_space, native):
        assert space.cleanup_calls == 0
        native.call = a._Call(0xC0000043, 0xFFFFFFFF, a._POINTER_MAX)
        result = original(case, selected_space, native)
        records.append(result)
        return result

    def cleanup():
        assert len(records) == 9
        assert all(record.status is a._Status.NATIVE_FAILURE for record in records)
        space.cleanup_calls += 1
        return True

    monkeypatch.setattr(a, "_DisposableSpace", lambda: space)
    monkeypatch.setattr(a, "_WindowsNative", FakeNative)
    monkeypatch.setattr(a, "_run_case", run_case)
    space.cleanup = cleanup
    transcript = a._execute()
    assert transcript.cases == tuple(records)
    assert transcript.cleanup == "PASS" and space.cleanup_calls == 1
