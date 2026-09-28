"""Fake/source-only acceptance tests: never invoke the disposable host harness."""

from __future__ import annotations

import ast
import ctypes
import inspect
import json
import runpy
import stat
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import p125_r1h_native_rename_acceptance as a


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
        self.call = a._Call(win32_bool=True)
        self.fault = None

    def open(self, path, *, parent=False, probe=False):
        self.events.append(("open", path, parent, probe))
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

    def rename(self, case, source, request):
        self.events.append(("rename", case, source, request))
        info_type = (
            a._FileRenameInformation
            if case is a._Case.NT_NATIVE_ANCHORED
            else a._FileRenameInfo
        )
        info = info_type.from_buffer(request.buffer)
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
        if case is a._Case.NT_NATIVE_ANCHORED and self.call == a._Call(win32_bool=True):
            return a._Call(ntstatus=0, io_status=0, io_information=0)
        return self.call

    def close(self, handle):
        self.events.append(("close", handle))
        if self.fault == "close_exception":
            raise OSError("SECRET")
        return self.fault != "close_false"


def test_import_and_unflagged_entry_are_inert(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("entry crossed execution gate")

    monkeypatch.setattr(a.secrets, "token_hex", forbidden)
    monkeypatch.setattr(a, "_execute", forbidden)
    runpy.run_path(a.__file__, run_name="inert_import_test")
    assert a.main([]) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "argv",
    [
        ["--execute-disposable"],
        ["--execute-disposable-r1h-acceptanc"],
        [a._EXECUTE, "--root", a._PRODUCTION],
        [a._EXECUTE, "--path", a._TEMP],
        [a._EXECUTE, a._PRODUCTION],
        [a._EXECUTE + "=true"],
    ],
)
def test_no_abbreviation_or_caller_path_surface(argv, monkeypatch):
    monkeypatch.setattr(a, "_execute", lambda: pytest.fail("must remain inert"))
    with pytest.raises(SystemExit) as caught:
        a.main(argv)
    assert caught.value.code == 2


def test_exact_flag_emits_one_canonical_transcript(monkeypatch, capsys):
    result = a._Transcript((), "PASS", "COMPLETE")
    monkeypatch.setattr(a, "_execute", lambda: result)
    assert a.main([a._EXECUTE]) == 0
    assert capsys.readouterr().out == result.canonical_json() + "\n"
    assert list(inspect.signature(a._execute).parameters) == []
    assert list(inspect.signature(a._DisposableSpace).parameters) == []


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
    assert len({path for triple in triples for path in triple}) == 9
    assert all(
        a._require_disposable_path(path) == first.root
        for triple in triples
        for path in triple
    )
    with pytest.raises(a._Blocked):
        first.guard(second.root)


@pytest.mark.parametrize("case", list(a._Case))
def test_buffer_layout_name_parent_and_no_replace(case):
    a._require_layout()
    request = a._request(case, 0x1234)
    layout = (
        a._FileRenameInformation
        if case is a._Case.NT_NATIVE_ANCHORED
        else a._FileRenameInfo
    )
    info = layout.from_buffer(request.buffer)
    assert info.root_directory == 0x1234
    assert info.replace_if_exists == 0
    assert info.file_name_length == request.name_length == 22
    encoded = ctypes.string_at(
        ctypes.addressof(request.buffer) + layout.file_name.offset, 22
    )
    assert encoded == "destination".encode("utf-16-le")
    if case is a._Case.WIN32_FROZEN_CONTROL:
        assert request.size == ctypes.sizeof(a._FileRenameInfo) + 22 + 2
        assert request.buffer.raw[layout.file_name.offset + 22 :] == b"\0" * 6
    elif case is a._Case.WIN32_EXACT_LENGTH:
        assert request.size == layout.file_name.offset + 22
        assert len(request.buffer.raw) == layout.file_name.offset + 22
    else:
        assert request.size == ctypes.sizeof(a._FileRenameInformation) + 22


@pytest.mark.parametrize("handle", [0, a._INVALID_HANDLE, None, True])
def test_null_or_invalid_root_handle_rejected(handle):
    with pytest.raises(a._Blocked):
        a._request(a._Case.WIN32_FROZEN_CONTROL, handle)


def test_exact_native_layout_assumptions():
    width = ctypes.sizeof(ctypes.c_void_p)
    expected = (8, 16, 20, 24) if width == 8 else (4, 8, 12, 16)
    for layout in (a._FileRenameInfo, a._FileRenameInformation):
        assert (
            layout.root_directory.offset,
            layout.file_name_length.offset,
            layout.file_name.offset,
            ctypes.sizeof(layout),
        ) == expected
        assert layout.replace_if_exists.offset == 0
    assert ctypes.sizeof(a._RenameFlags) == 4
    assert ctypes.sizeof(a._FileRenameInformation._fields_[-1][1]) == 2
    assert ctypes.sizeof(a._FileRenameInfo._fields_[-1][1]) == 1
    assert a._IoStatusBlock.status.offset == a._IoStatusBlock.pointer.offset == 0
    assert a._IoStatusBlock.information.offset == width
    assert ctypes.sizeof(a._IoStatusBlock) == width * 2
    assert ctypes.sizeof(a._IoStatusUnion) == width
    assert ctypes.sizeof(a._IoStatusUnion._fields_[0][1]) == 4
    assert ctypes.sizeof(a._ByHandleInfo) == 52


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
            "SetFileInformationByHandle",
            "NtSetInformationFile",
        ):
            setattr(library, name, FakeFunction(123 if name == "CreateFileW" else 1))
        libraries[path] = library
        return library

    monkeypatch.setattr(a.os, "name", "nt")
    monkeypatch.setattr(a.ctypes, "WinDLL", load)
    native = a._WindowsNative(FakeSpace())
    return native, libraries, events


def test_fixed_system_bindings_and_exact_native_signature(monkeypatch):
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
    assert native._set.argtypes == [
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    assert native._set.restype is ctypes.c_int32


def test_frozen_handle_open_semantics_and_fresh_probe(monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    parent, source, destination = native.space.paths(a._Case.WIN32_FROZEN_CONTROL)
    native.open(parent, parent=True)
    native.open(source)
    native.open(destination, probe=True)
    assert native._create.calls == [
        (parent, 0x1200A5, 1, None, 3, 0x02200000, None),
        (source, 0x130081, 1, None, 3, 0x02200000, None),
        (destination, 0x80, 7, None, 3, 0x02200000, None),
    ]
    assert a._SOURCE_ACCESS & a._DELETE


@pytest.mark.parametrize(
    "case", [a._Case.WIN32_FROZEN_CONTROL, a._Case.WIN32_EXACT_LENGTH]
)
def test_win32_class_and_immediate_last_error_order(case, monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    events = []
    monkeypatch.setattr(
        a.ctypes, "set_last_error", lambda n: events.append(("clear", n)), raising=False
    )
    monkeypatch.setattr(
        a.ctypes,
        "get_last_error",
        lambda: events.append(("error",)) or -1,
        raising=False,
    )

    def set_info(handle, kind, pointer, size):
        events.append(("set", handle, kind, size))
        return 0

    native._set = set_info
    request = a._request(case, 100)
    result = native.rename(case, 101, request)
    assert events == [("clear", 0), ("set", 101, 3, request.size), ("error",)]
    assert result == a._Call(win32_bool=False, win32_error=0xFFFFFFFF)


def test_win32_success_does_not_fetch_stale_error(monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    monkeypatch.setattr(a.ctypes, "set_last_error", lambda _: None, raising=False)
    monkeypatch.setattr(
        a.ctypes,
        "get_last_error",
        lambda: pytest.fail("stale error read"),
        raising=False,
    )
    result = native.rename(
        a._Case.WIN32_EXACT_LENGTH, 101, a._request(a._Case.WIN32_EXACT_LENGTH, 100)
    )
    assert result == a._Call(win32_bool=True)


@pytest.mark.parametrize("status", [0, 0x103, 1, -1073741811, -1])
def test_nt_call_class_status_and_io_capture(status, monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    monkeypatch.setattr(
        a.ctypes,
        "get_last_error",
        lambda: pytest.fail("NT uses raw status"),
        raising=False,
    )
    request = a._request(a._Case.NT_NATIVE_ANCHORED, 100)

    def nt_set(handle, io_pointer, buffer_pointer, size, kind):
        assert (handle, size, kind) == (101, request.size, 10)
        io = ctypes.cast(io_pointer, ctypes.POINTER(a._IoStatusBlock)).contents
        assert io.status == -1 and io.information == a._POINTER_MAX
        io.status = status
        io.information = 0
        info = ctypes.cast(
            buffer_pointer, ctypes.POINTER(a._FileRenameInformation)
        ).contents
        assert info.root_directory == 100 and info.replace_if_exists == 0
        return status

    native._nt_set = nt_set
    result = native.rename(a._Case.NT_NATIVE_ANCHORED, 101, request)
    assert result.ntstatus == result.io_status == status & 0xFFFFFFFF
    assert result.io_information == 0
    assert result.exact_success(a._Case.NT_NATIVE_ANCHORED, request.size) is (
        status == 0
    )
    assert native._requests == [request]


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
    evidence = a._run_case(a._Case.WIN32_EXACT_LENGTH, space, native)
    assert evidence.status is not a._Status.PASS
    assert (
        "SECRET" not in a._Transcript((evidence,), "PASS", "COMPLETE").canonical_json()
    )
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
    result = a._run_case(a._Case.NT_NATIVE_ANCHORED, space, native)
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
        a._run_case(a._Case.NT_NATIVE_ANCHORED, space, native).status
        is not a._Status.PASS
    )


def test_win32_failure_is_preserved_despite_later_proofs():
    space = FakeSpace()
    native = FakeNative(space)
    native.call = a._Call(win32_bool=False, win32_error=87)
    result = a._run_case(a._Case.WIN32_FROZEN_CONTROL, space, native)
    assert result.status is a._Status.NATIVE_FAILURE
    assert result.win32_error == 87 and result.same_object_after


def test_frozen_evidence_precedes_cleanup_and_cleanup_cannot_change_case(monkeypatch):
    space = FakeSpace()
    records = []

    def run_case(case, selected_space, native):
        assert selected_space is space and space.cleanup_calls == 0
        result = a._Evidence(case, a._Api.WIN32, 48, 22, status=a._Status.PASS)
        records.append(result)
        return result

    def cleanup():
        assert len(records) == 3
        assert all(record.status is a._Status.PASS for record in records)
        return False

    space.cleanup = cleanup
    monkeypatch.setattr(a, "_DisposableSpace", lambda: space)
    monkeypatch.setattr(a, "_WindowsNative", FakeNative)
    monkeypatch.setattr(a, "_run_case", run_case)
    transcript = a._execute()
    assert transcript.cases == tuple(records)
    assert transcript.cleanup == "FAILURE"


def test_transcript_is_fixed_sanitized_and_deterministic():
    def transcript(root_character):
        space = FakeSpace()
        space.root = space.root[:-32] + root_character * 32
        records = tuple(a._run_case(case, space, FakeNative(space)) for case in a._Case)
        return a._Transcript(records, "PASS", "COMPLETE").canonical_json()

    encoded = transcript("a")
    assert encoded == transcript("b")
    decoded = json.loads(encoded)
    assert encoded == json.dumps(decoded, sort_keys=True, separators=(",", ":"))
    assert set(decoded) == {"schema", "cases", "cleanup", "status"}
    expected = {
        "case",
        "api",
        "passed_buffer_size",
        "FileNameLength",
        "RootDirectory_non_null",
        "win32_bool",
        "win32_error",
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
    assert len(encoded) < 2048
    for forbidden in (
        "F:",
        "C:",
        "SECRET",
        "S-1-",
        "handle",
        "environment",
        "traceback",
    ):
        assert forbidden not in encoded


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
    assert len(fs.created) == 7
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
    assert len(fs.removed) == 7


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
    parent, source, destination = space.paths(a._Case.WIN32_FROZEN_CONTROL)
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


def test_no_production_or_external_effect_surface_and_frozen_control_source():
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
        "dataclasses",
        "enum",
        "pathlib",
    }
    for forbidden in (
        "p125_replace_d10",
        "p125_recover_d10",
        "d10_protected_replacement",
        "subprocess",
        "scheduler",
        "sign_trust",
        "activate",
        "provider",
        "broker",
    ):
        assert forbidden not in source
    assert "rmtree" not in source and "unlink" not in source
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"rename", "replace", "remove"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        for node in ast.walk(tree)
    )
    harness = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_FileRenameInfo"
    )
    assert ast.unparse(harness.body[0]) == (
        "_fields_ = [('replace_if_exists', ctypes.c_ubyte), "
        "('root_directory', ctypes.c_void_p), "
        "('file_name_length', ctypes.c_uint32), "
        "('file_name', ctypes.c_ubyte * 1)]"
    )
    buffer_size = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_buffer_size"
    )
    buffer_size_text = ast.unparse(buffer_size)
    assert "_Case.WIN32_FROZEN_CONTROL" in buffer_size_text
    assert "ctypes.sizeof(_FileRenameInfo) + name_length + 2" in buffer_size_text


@pytest.mark.parametrize("prepared_count", [0, 1, 2])
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
    space.prepare(a._Case.WIN32_FROZEN_CONTROL)
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
    assert len(transcript.cases) == 3
    if failure == "cleanup":
        assert all(record.status is a._Status.PASS for record in transcript.cases)
        assert transcript.cleanup == "FAILURE"
    else:
        assert transcript.status == "BLOCKED"
        assert all(record.status is a._Status.BLOCKED for record in transcript.cases)
    encoded = transcript.canonical_json()
    for forbidden in ("SECRET", "SID", "ACL", "F:", "environment", "OSError"):
        assert forbidden not in encoded


@pytest.mark.parametrize("result", [None, 0, a._INVALID_HANDLE])
def test_native_open_failure_is_fail_closed(result, monkeypatch):
    native, _, _ = bound_native(monkeypatch)
    native._create.result = result
    with pytest.raises(a._Blocked):
        native.open(native.space.paths(a._Case.WIN32_EXACT_LENGTH)[1])


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
    path = native.space.paths(a._Case.WIN32_EXACT_LENGTH)[2]
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
    destination = native.space.paths(a._Case.NT_NATIVE_ANCHORED)[2]

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


def test_evidence_record_is_immutable():
    from dataclasses import FrozenInstanceError

    record = a._Evidence(a._Case.WIN32_EXACT_LENGTH, a._Api.WIN32, 42, 22)
    with pytest.raises(FrozenInstanceError):
        record.status = a._Status.PASS


def test_execute_runs_three_independent_cases_in_order_using_only_fakes(monkeypatch):
    space = FakeSpace()
    monkeypatch.setattr(a, "_DisposableSpace", lambda: space)
    monkeypatch.setattr(a, "_WindowsNative", FakeNative)
    transcript = a._execute()
    assert [record.case for record in transcript.cases] == list(a._Case)
    assert all(record.status is a._Status.PASS for record in transcript.cases)
    assert transcript.status == "COMPLETE" and transcript.cleanup == "PASS"
    assert space.prepared == list(a._Case) and space.cleanup_calls == 1


def test_rejected_cli_does_not_echo_caller_paths_or_secrets(capsys):
    with pytest.raises(SystemExit) as caught:
        a.main([a._EXECUTE, "--root", r"F:\AITradingBot\SECRET"])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "invalid_arguments\n"
