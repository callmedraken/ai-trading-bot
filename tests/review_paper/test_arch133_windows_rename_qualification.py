"""Y source-only qualification tests: fake Win32 edges and external temp files only."""

from __future__ import annotations

import ast
import ctypes
import hashlib
import io
import json
import ntpath
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.arch133_windows_rename_qualification import native, operator

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-windows-rename-qualification"
X_NAME = "arch133-robinhood-reprovision-recovery-reconciliation"


class Function:
    def __init__(self, function):
        self.function = function

    def __call__(self, *args):
        return self.function(*args)


class FakeKernel:
    """Exercise Y native code against disposable synthetic objects."""

    def __init__(self, tmp_path):
        self.volume = tmp_path / "volume"
        (self.volume / "AI/temp").mkdir(parents=True)
        self.handles = {}
        self.next_handle = 100
        self.error = 0
        self.calls = []
        self.fail = None
        self.fail_rename = 0
        self.rename_calls = 0
        self.filesystem = "NTFS"
        self.drive = 3
        self.reparse = set()
        for name in (
            "CreateFileW",
            "CloseHandle",
            "GetFinalPathNameByHandleW",
            "GetFileInformationByHandle",
            "SetFilePointerEx",
            "ReadFile",
            "WriteFile",
            "FlushFileBuffers",
            "GetVolumeInformationW",
            "GetDriveTypeW",
            "CreateDirectoryW",
            "SetFileInformationByHandle",
            "DeleteFileW",
            "RemoveDirectoryW",
        ):
            method = getattr(self, name)
            setattr(self, name, Function(method))

    def path(self, windows_path):
        relative = ntpath.relpath(windows_path, "F:\\")
        return (
            self.volume
            if relative == "."
            else self.volume.joinpath(*relative.split("\\"))
        )

    def windows(self, path):
        if path == self.volume:
            return "F:\\"
        return "F:\\" + str(path.relative_to(self.volume)).replace("/", "\\").replace(
            ".\\", ""
        )

    def rejecting(self, name):
        self.calls.append(name)
        if self.fail == name:
            self.error = 87
            return True
        return False

    def CreateFileW(self, path, access, share, security, disposition, flags, template):
        self.calls.append(("open", path, access, share, disposition, flags))
        local = self.path(path)
        if disposition == 1:
            local.touch(exist_ok=False)
        if not local.exists():
            self.error = 2
            return None
        self.next_handle += 1
        self.handles[self.next_handle] = local
        return self.next_handle

    def CloseHandle(self, handle):
        self.handles.pop(handle)
        return 0 if self.rejecting("CloseHandle") else 1

    def GetFinalPathNameByHandleW(self, handle, buffer, size, flags):
        if self.rejecting("GetFinalPathNameByHandleW"):
            return 0
        buffer.value = "\\\\?\\" + self.windows(self.handles[handle])
        return len(buffer.value)

    def GetFileInformationByHandle(self, handle, pointer):
        if self.rejecting("GetFileInformationByHandle"):
            return 0
        local = self.handles[handle]
        info = ctypes.cast(pointer, ctypes.POINTER(native.FileInformation)).contents
        stat = local.stat()
        info.attributes = (0x10 if local.is_dir() else 0) | (
            0x400 if self.windows(local).rstrip("\\") in self.reparse else 0
        )
        info.volume = 123
        info.index_low, info.index_high = stat.st_ino & 0xFFFFFFFF, stat.st_ino >> 32
        info.links = stat.st_nlink
        info.size_low = 0 if local.is_dir() else stat.st_size
        return 1

    def SetFilePointerEx(self, *args):
        return 0 if self.rejecting("SetFilePointerEx") else 1

    def ReadFile(self, handle, buffer, bound, count, overlapped):
        if self.rejecting("ReadFile"):
            return 0
        raw = self.handles[handle].read_bytes()
        ctypes.memmove(buffer, raw, len(raw))
        ctypes.cast(count, ctypes.POINTER(ctypes.c_uint32)).contents.value = len(raw)
        return 1

    def WriteFile(self, handle, raw, size, count, overlapped):
        if self.rejecting("WriteFile"):
            return 0
        self.handles[handle].write_bytes(raw)
        ctypes.cast(count, ctypes.POINTER(ctypes.c_uint32)).contents.value = size
        return 1

    def FlushFileBuffers(self, handle):
        return 0 if self.rejecting("FlushFileBuffers") else 1

    def GetVolumeInformationW(
        self, drive, name, size, serial, maximum, flags, fs, bound
    ):
        fs.value = self.filesystem
        return 0 if self.rejecting("GetVolumeInformationW") else 1

    def GetDriveTypeW(self, drive):
        assert drive == "F:\\"
        return self.drive

    def CreateDirectoryW(self, path, security):
        if self.rejecting("CreateDirectoryW"):
            return 0
        self.path(path).mkdir()
        return 1

    def SetFileInformationByHandle(self, handle, kind, buffer, size):
        self.rename_calls += 1
        info = native.FileRenameInfo.from_buffer(buffer)
        assert kind == 3 and info.RootDirectory is None and info.ReplaceIfExists == 0
        raw = ctypes.string_at(
            ctypes.addressof(buffer) + native.FileRenameInfo.FileName.offset,
            info.FileNameLength,
        )
        destination = raw.decode("utf-16-le")
        assert ntpath.isabs(destination) and destination in (
            native.ARCHIVE,
            native.ACTIVE,
        )
        self.calls.append(("rename", self.windows(self.handles[handle]), destination))
        if self.rename_calls == self.fail_rename:
            self.error = 87
            return 0
        source, target = self.handles[handle], self.path(destination)
        assert not target.exists()
        source.rename(target)
        for number, path in tuple(self.handles.items()):
            if path == source or source in path.parents:
                self.handles[number] = target / path.relative_to(source)
        return 1

    def DeleteFileW(self, path):
        if self.rejecting("DeleteFileW"):
            return 0
        self.path(path).unlink()
        return 1

    def RemoveDirectoryW(self, path):
        if self.rejecting("RemoveDirectoryW"):
            return 0
        self.path(path).rmdir()
        return 1


@pytest.fixture
def fake(tmp_path, monkeypatch):
    kernel = FakeKernel(tmp_path)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: kernel, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: kernel.error, raising=False)
    monkeypatch.setattr(native, "Path", kernel.path)
    runtime = {"source_head": "a" * 40, "source_tree": "b" * 40}
    monkeypatch.setattr(operator, "observe_runtime", lambda: dict(runtime))
    monkeypatch.setattr(operator, "administrator_sid", lambda: "S-1-5-21-test-admin")
    monkeypatch.setattr(operator, "authorize", lambda head: None)
    return kernel


def assert_result(outcome, status):
    code, result = outcome
    assert code == (0 if status == "PASS" else 3)
    assert result["schema"] == operator.RESULT_SCHEMA
    assert result["status"] == status
    assert (
        result["disposition"]
        == {
            "PASS": "RENAME_PRIMITIVE_QUALIFIED",
            "BLOCKED": "QUALIFICATION_REJECTED",
            "INDETERMINATE": "PRESERVE_SCRATCH_NO_RETRY",
        }[status]
    )
    assert len(operator.ZERO_EFFECTS) == 15
    assert {key: result[key] for key in operator.ZERO_EFFECTS} == operator.ZERO_EFFECTS
    return result


def test_fixed_path_source_identity_and_synthetic_only_bytes():
    assert native.SCRATCH_ROOT == r"F:\AI\temp\arch133y-rename-qualification"
    assert operator.SOURCE_ROOT == Path(
        r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133y"
    )
    assert operator.SOURCE_BRANCH == "feature/robinhood-unattended-review-paper-133y"
    assert operator.PRODUCTION_PYTHON == Path(r"F:\AITradingBot\runtime\python.exe")
    assert operator.PRODUCTION_PYTHON_VERSION == "3.14.3"
    assert operator.PRODUCTION_PYTHON_SHA256 == (
        "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
    )
    assert operator.HOST_SOURCE_HEAD == "65f0d40217f8ce129224531a5151f4acea889d89"
    assert operator.HOST_SOURCE_TREE == "16cb734cbeaa9e97aaf9e2d521d922fbbc7b7ae2"
    assert tuple(native.SYNTHETIC_BYTES) == ("predecessor", "staged")
    for role, files in native.SYNTHETIC_BYTES.items():
        assert tuple(files) == native.FINAL_NAMES
        for name, raw in files.items():
            assert raw == f"ARCH133Y SYNTHETIC ONLY v1 {role} {name}\n".encode("ascii")


@pytest.mark.parametrize(
    "source,destination",
    [(native.ACTIVE, native.ARCHIVE), (native.STAGE, native.ACTIVE)],
)
def test_rename_info_layout_null_root_absolute_name_no_replace(source, destination):
    pointer_size = ctypes.sizeof(ctypes.c_void_p)
    assert native.FileRenameInfo.ReplaceIfExists.offset == 0
    assert native.FileRenameInfo.RootDirectory.offset == pointer_size
    assert native.FileRenameInfo.FileNameLength.offset == pointer_size * 2
    assert native.FileRenameInfo.FileName.offset == pointer_size * 2 + 4
    buffer = native.rename_buffer(source, destination)
    info = native.FileRenameInfo.from_buffer(buffer)
    assert info.RootDirectory is None and info.ReplaceIfExists == 0
    raw = ctypes.string_at(
        ctypes.addressof(buffer) + native.FileRenameInfo.FileName.offset,
        info.FileNameLength,
    )
    assert raw == destination.encode("utf-16-le")
    assert ntpath.isabs(raw.decode("utf-16-le"))


@pytest.mark.parametrize(
    "destination",
    [
        "archive",
        r"F:archive",
        r"C:\archive",
        native.STAGE,
        native.ARCHIVE + "-alternate",
    ],
)
def test_reject_nonfixed_or_relative_destinations(destination):
    with pytest.raises(ValueError):
        native.rename_buffer(native.ACTIVE, destination)


def test_exact_two_rename_order_identity_sharing_cleanup_and_zero_production(fake):
    result = assert_result(operator.run(), "PASS")
    assert result["before"] == result["after_first"] == result["after_second"]
    assert result["scratch"] == dict.fromkeys(operator.SCRATCH_COUNTERS, 1)
    assert result["handles_closed"] and result["scratch_root_absent"]
    assert not fake.path(native.SCRATCH_ROOT).exists() and not fake.handles
    renames = [c for c in fake.calls if isinstance(c, tuple) and c[0] == "rename"]
    assert renames == [
        ("rename", native.ACTIVE, native.ARCHIVE),
        ("rename", native.STAGE, native.ACTIVE),
    ]
    for call in fake.calls:
        if not isinstance(call, tuple) or call[0] != "open" or call[4] != 3:
            continue
        _, path, access, share, _, flags = call
        if flags == native.DIRECTORY_FLAGS:
            assert share == 7
            if path in (native.ACTIVE, native.STAGE):
                assert access == native.SOURCE_ACCESS and access & native.DELETE
        else:
            assert access == native.CHILD_ACCESS and share == 5 and not share & 2
    assert fake.calls.index("DeleteFileW") > max(
        i for i, c in enumerate(fake.calls) if isinstance(c, tuple) and c[0] == "rename"
    )


@pytest.mark.parametrize("boundary", ["runtime", "admin", "tty", "volume", "vacancy"])
def test_pre_mutation_failure_blocked_and_no_cleanup(fake, monkeypatch, boundary):
    def reject(*a):
        raise ValueError("PRIVATE SECRET PATH")

    if boundary == "runtime":
        monkeypatch.setattr(operator, "observe_runtime", reject)
    elif boundary == "admin":
        monkeypatch.setattr(operator, "administrator_sid", reject)
    elif boundary == "tty":
        monkeypatch.setattr(operator, "authorize", reject)
    elif boundary == "volume":
        fake.filesystem = "FAT32"
    else:
        fake.path(native.SCRATCH_ROOT).mkdir()
    result = assert_result(operator.run(), "BLOCKED")
    assert result["scratch"] == dict.fromkeys(operator.SCRATCH_COUNTERS, 0)
    assert "PRIVATE" not in json.dumps(result)
    assert not fake.handles and "DeleteFileW" not in fake.calls


@pytest.mark.parametrize(
    "boundary",
    [
        "CreateDirectoryW",
        "WriteFile",
        "FlushFileBuffers",
        "ReadFile",
        "CloseHandle",
        "first",
        "second",
        "verify1",
        "verify2",
        "source_after",
        "cleanup",
    ],
)
def test_post_mutation_failure_preserves_scratch_no_retry(fake, monkeypatch, boundary):
    if boundary in ("first", "second"):
        fake.fail_rename = 1 if boundary == "first" else 2
    elif boundary in ("verify1", "verify2"):
        previous = native.WindowsScratch.verify

        def corrupt(edge, step):
            result = previous(edge, step)
            if step == (1 if boundary == "verify1" else 2):
                result = {**result, "root": [999, 999]}
            return result

        monkeypatch.setattr(native.WindowsScratch, "verify", corrupt)
    elif boundary == "source_after":
        seen = []

        def runtime():
            seen.append(1)
            if len(seen) == 3:
                raise RuntimeError("SECRET")
            return {"source_head": "a" * 40}

        monkeypatch.setattr(operator, "observe_runtime", runtime)
    elif boundary == "cleanup":
        fake.fail = "DeleteFileW"
    elif boundary == "CloseHandle":
        # Fail the first held close after successful verification, not admission opens.
        previous = native.WindowsScratch.close

        def closing(edge):
            if edge.verified:
                fake.fail = "CloseHandle"
            previous(edge)

        monkeypatch.setattr(native.WindowsScratch, "close", closing)
    else:
        fake.fail = boundary
    result = assert_result(operator.run(), "INDETERMINATE")
    assert not fake.handles
    assert result["scratch"]["cleanups_completed"] == 0
    assert result["scratch"]["cleanup_attempts"] == (1 if boundary == "cleanup" else 0)
    assert fake.rename_calls <= 2
    if boundary == "first":
        assert fake.rename_calls == 1 and result["native_error_code"] == 87
    if boundary != "CreateDirectoryW":
        assert fake.path(native.SCRATCH_ROOT).exists()
    if boundary != "cleanup":
        assert "DeleteFileW" not in fake.calls and "RemoveDirectoryW" not in fake.calls


@pytest.mark.parametrize("step", [1, 2])
@pytest.mark.parametrize(
    "drift", ["directory", "child_identity", "child_bytes", "extra", "parent"]
)
def test_each_rename_rejects_object_or_held_child_drift(fake, monkeypatch, step, drift):
    previous = native.WindowsScratch.verify

    def verify(edge, current_step):
        if current_step == step:
            current = native.ARCHIVE
            if drift == "child_bytes":
                fake.path(ntpath.join(current, "activation.json")).write_bytes(b"DRIFT")
            elif drift == "child_identity":
                path = fake.path(ntpath.join(current, "activation.json"))
                old = path.read_bytes()
                path.rename(path.with_suffix(".retained"))
                path.write_bytes(old)
            elif drift == "extra":
                (fake.path(current) / "unexpected").write_bytes(b"EXTRA")
            elif drift == "directory":
                path = fake.path(current)
                path.rename(path.with_name("replaced"))
                path.mkdir()
            else:
                fake.reparse.add(native.STAGING_PARENT)
        return previous(edge, current_step)

    monkeypatch.setattr(native.WindowsScratch, "verify", verify)
    result = assert_result(operator.run(), "INDETERMINATE")
    assert fake.rename_calls == step and result["scratch"]["cleanup_attempts"] == 0
    assert fake.path(native.SCRATCH_ROOT).exists()


@pytest.mark.parametrize("ancestor", native.ANCESTORS)
def test_reparse_ancestors_rejected_before_scratch_mutation(fake, ancestor):
    fake.reparse.add(ancestor.rstrip("\\"))
    assert_result(operator.run(), "BLOCKED")
    assert not fake.path(native.SCRATCH_ROOT).exists()


@pytest.mark.parametrize(
    "field",
    [
        "closed",
        "verified",
        "rename_step",
        "baseline",
        "created_identity",
        "mutation_started",
        "cleanup_started",
    ],
)
def test_cleanup_requires_complete_same_invocation_authority(fake, field):
    edge = native.WindowsScratch()
    with pytest.raises(ValueError):
        edge.cleanup()
    edge.admit()
    counters = dict.fromkeys(operator.SCRATCH_COUNTERS, 0)
    edge.create(counters)
    edge.snapshot()
    edge.rename(native.ACTIVE, native.ARCHIVE)
    edge.verify(1)
    edge.rename(native.STAGE, native.ACTIVE)
    edge.verify(2)
    edge.close()
    setattr(edge, field, True if field == "cleanup_started" else None)
    with pytest.raises(ValueError):
        edge.cleanup()
    assert fake.path(native.SCRATCH_ROOT).exists()
    assert "DeleteFileW" not in fake.calls


@pytest.mark.parametrize("drift", ["extra", "replacement", "reparse"])
def test_cleanup_reobserves_invocation_tree_before_any_deletion(fake, drift):
    edge = native.WindowsScratch()
    edge.admit()
    edge.create(dict.fromkeys(operator.SCRATCH_COUNTERS, 0))
    edge.snapshot()
    edge.rename(native.ACTIVE, native.ARCHIVE)
    edge.verify(1)
    edge.rename(native.STAGE, native.ACTIVE)
    edge.verify(2)
    edge.close()
    path = fake.path(native.SCRATCH_ROOT)
    if drift == "extra":
        (path / "unrelated").write_bytes(b"PRESERVE")
    elif drift == "replacement":
        path.rename(path.with_name("preserved"))
        path.mkdir()
    else:
        fake.reparse.add(native.SCRATCH_ROOT)
    with pytest.raises((ValueError, native.NativeError)):
        edge.cleanup()
    assert "DeleteFileW" not in fake.calls and not fake.handles


@pytest.mark.parametrize(
    "code,expected",
    [
        (0, 0),
        (87, 87),
        (0xFFFFFFFF, 0xFFFFFFFF),
        (-1, 0),
        (0x100000000, 0),
        (True, 0),
        ("PRIVATE STRING", 0),
    ],
)
def test_native_diagnostics_are_bounded_numeric_only(fake, monkeypatch, code, expected):
    def rejected(edge):
        exc = native.NativeError(87)
        exc.native_error_code = code
        raise exc

    monkeypatch.setattr(native.WindowsScratch, "admit", rejected)
    result = assert_result(operator.run(), "BLOCKED")
    assert result["native_error_code"] == expected
    assert type(result["native_error_code"]) is int
    assert "PRIVATE" not in json.dumps(result)


def test_native_step_consumed_no_retry_or_alternate_destination(fake):
    edge = native.WindowsScratch()
    edge.admit()
    edge.create(dict.fromkeys(operator.SCRATCH_COUNTERS, 0))
    edge.snapshot()
    fake.fail_rename = 1
    with pytest.raises(native.NativeError):
        edge.rename(native.ACTIVE, native.ARCHIVE)
    with pytest.raises(ValueError):
        edge.rename(native.ACTIVE, native.ARCHIVE)
    with pytest.raises(ValueError):
        edge.rename(native.STAGE, native.ACTIVE + "-alternate")
    assert fake.rename_calls == 1
    edge.close()


@pytest.mark.parametrize(
    "args",
    [
        ["--root", "arbitrary"],
        ["--path", native.SCRATCH_ROOT],
        ["--execute"],
        [native.SCRATCH_ROOT],
    ],
)
def test_cli_and_launcher_reject_every_override_before_observation(
    tmp_path, monkeypatch, capsys, args
):
    monkeypatch.setattr(operator, "sys", SimpleNamespace(argv=["launcher", *args]))
    monkeypatch.setattr(operator, "run", lambda: pytest.fail("runtime reached"))
    assert operator.main() == 3
    assert_result((3, json.loads(capsys.readouterr().out)), "BLOCKED")
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(ROOT / "scripts/run_arch133_windows_rename_qualification.py"),
            *args,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert_result((child.returncode, json.loads(child.stdout)), "BLOCKED")
    assert child.stderr == ""


class Terminal(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.parametrize(
    "case", ["ok", "wrong", "old_head", "stdin_pipe", "stdout_pipe", "oversized"]
)
def test_tty_phrase_exactly_binds_current_source_once(monkeypatch, case):
    head = "a" * 40
    phrase = "AUTHORIZE ARCH133Y " + head
    value = (
        phrase + "\n"
        if case == "ok"
        else "PRIVATE\n"
        if case == "wrong"
        else (
            "AUTHORIZE ARCH133Y " + "b" * 40 + "\n"
            if case == "old_head"
            else phrase + " " * 300 + "\n"
            if case == "oversized"
            else phrase + "\n"
        )
    )
    stdin = io.StringIO(value) if case == "stdin_pipe" else Terminal(value)
    stdout = io.StringIO() if case == "stdout_pipe" else Terminal()
    monkeypatch.setattr(operator, "sys", SimpleNamespace(stdin=stdin, stdout=stdout))
    if case == "ok":
        operator.authorize(head)
    else:
        with pytest.raises(ValueError):
            operator.authorize(head)


@pytest.fixture
def runtime_fixture(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    host = tmp_path / "host"
    host.mkdir()
    launcher = root / "scripts/run_arch133_windows_rename_qualification.py"
    launcher.parent.mkdir()
    launcher.write_bytes(b"synthetic launcher")
    python = tmp_path / "python.exe"
    python.write_bytes(b"synthetic interpreter")
    cache = root / "no-pycache"
    monkeypatch.setattr(operator, "SOURCE_ROOT", root)
    monkeypatch.setattr(operator, "HOST_SOURCE_ROOT", host)
    monkeypatch.setattr(operator, "LAUNCHER", launcher)
    monkeypatch.setattr(operator, "NO_PYCACHE", cache)
    monkeypatch.setattr(operator, "PRODUCTION_PYTHON", python)
    monkeypatch.setattr(
        operator,
        "PRODUCTION_PYTHON_SHA256",
        hashlib.sha256(python.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        operator,
        "__file__",
        str(root / "src/trading_bot/arch133_windows_rename_qualification/operator.py"),
    )
    state = SimpleNamespace(
        argv=[str(launcher)],
        platform="win32",
        flags=SimpleNamespace(isolated=1),
        dont_write_bytecode=True,
        pycache_prefix=str(cache),
        executable=str(python),
        version_info=(3, 14, 3),
    )
    monkeypatch.setattr(operator, "sys", state)
    monkeypatch.setattr(
        operator,
        "require_checkout",
        lambda path, branch: (
            ("a" * 40, "b" * 40)
            if path == root
            else (operator.HOST_SOURCE_HEAD, operator.HOST_SOURCE_TREE)
        ),
    )
    return SimpleNamespace(
        root=root, host=host, launcher=launcher, python=python, cache=cache, sys=state
    )


def test_runtime_binding_admits_exact_fake_identity(runtime_fixture):
    result = operator.observe_runtime()
    assert result["source_head"] == "a" * 40
    assert result["host_source_head"] == operator.HOST_SOURCE_HEAD
    assert result["python_version"] == "3.14.3"


@pytest.mark.parametrize(
    "drift",
    [
        "args",
        "windows",
        "isolated",
        "bytecode",
        "cache_prefix",
        "cache_collision",
        "launcher",
        "module",
        "python_path",
        "version",
        "hash",
        "host_head",
        "host_tree",
    ],
)
def test_runtime_binding_fail_closed(runtime_fixture, monkeypatch, drift):
    f = runtime_fixture
    if drift == "args":
        f.sys.argv.append("--root")
    elif drift == "windows":
        f.sys.platform = "linux"
    elif drift == "isolated":
        f.sys.flags.isolated = 0
    elif drift == "bytecode":
        f.sys.dont_write_bytecode = False
    elif drift == "cache_prefix":
        f.sys.pycache_prefix = None
    elif drift == "cache_collision":
        f.cache.mkdir()
    elif drift == "launcher":
        f.sys.argv[0] = str(f.python)
    elif drift == "module":
        monkeypatch.setattr(operator, "__file__", str(f.python))
    elif drift == "python_path":
        f.sys.executable = str(f.launcher)
    elif drift == "version":
        f.sys.version_info = (3, 14, 4)
    elif drift == "hash":
        f.python.write_bytes(b"DRIFT")
    else:
        monkeypatch.setattr(
            operator,
            "require_checkout",
            lambda path, branch: (
                ("a" * 40, "b" * 40)
                if path == f.root
                else ("c" * 40, operator.HOST_SOURCE_TREE)
                if drift == "host_head"
                else (operator.HOST_SOURCE_HEAD, "d" * 40)
            ),
        )
    with pytest.raises((ValueError, FileNotFoundError, IndexError)):
        operator.observe_runtime()


@pytest.mark.parametrize(
    "drift",
    [
        None,
        "head",
        "tree",
        "root",
        "branch",
        "origin",
        "dirty",
        "upstream",
        "remote_head",
        "remote_tree",
    ],
)
def test_checkout_binding_exact_tracking_identity(tmp_path, monkeypatch, drift):
    monkeypatch.setattr(operator, "SOURCE_ROOT", tmp_path)
    branch = operator.SOURCE_BRANCH
    ref = "refs/remotes/origin/" + branch
    values = {
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "HEAD^{tree}"): "b" * 40,
        ("rev-parse", "--show-toplevel"): str(tmp_path),
        ("branch", "--show-current"): branch,
        ("remote", "get-url", "origin"): operator.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "origin/"
        + branch,
        ("rev-parse", ref): "a" * 40,
        ("rev-parse", ref + "^{tree}"): "b" * 40,
    }
    keys = dict(
        zip(
            (
                "head",
                "tree",
                "root",
                "branch",
                "origin",
                "dirty",
                "upstream",
                "remote_head",
                "remote_tree",
            ),
            values,
            strict=True,
        )
    )
    if drift:
        values[keys[drift]] = str(tmp_path.parent) if drift == "root" else "DRIFT"
    monkeypatch.setattr(operator, "_git", lambda root, *args: values[args])
    if drift:
        with pytest.raises(ValueError):
            operator.require_checkout(tmp_path, branch)
    else:
        assert operator.require_checkout(tmp_path, branch) == ("a" * 40, "b" * 40)
        with pytest.raises(ValueError):
            operator.require_checkout(tmp_path.parent, branch)


def test_import_closure_contains_only_inert_admin_reader_and_y(tmp_path):
    program = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'src')!r})\n"
        "import trading_bot.arch133_windows_rename_qualification.operator\n"
        "names = (n for n in sys.modules if n.startswith('trading_bot'))\n"
        "print('\\n'.join(sorted(names)))\n"
    )
    child = subprocess.run(
        [sys.executable, "-I", "-B", "-"],
        input=program,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert child.stderr == ""
    assert set(child.stdout.splitlines()) == {
        "trading_bot",
        "trading_bot.config",
        "trading_bot.arch133_acl",
        "trading_bot.arch133_acl.administrator",
        "trading_bot.arch133_acl.read_only",
        "trading_bot.arch133_windows_rename_qualification",
        "trading_bot.arch133_windows_rename_qualification.native",
        "trading_bot.arch133_windows_rename_qualification.operator",
    }
    source = (
        ROOT / "src/trading_bot/arch133_windows_rename_qualification/native.py"
    ).read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    constants = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    assert not {
        "MoveFile",
        "MoveFileW",
        "MoveFileEx",
        "MoveFileExW",
        "NtSetInformationFile",
    } & set(constants)
    assert constants.count("SetFileInformationByHandle") == 1
    assert not any("AITradingBot" in value for value in constants)


def test_y_real_complete_authority_and_source_only_registration():
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == operator.SOURCE_BRANCH
    assert runner.ACTIVE_CI_CHECKPOINTS[-3:-1] == (X_NAME, NAME)
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 56
    assert spec.tests == (
        *runner.ARCH133_L_M_TESTS,
        "tests/review_paper/test_arch133_windows_rename_qualification.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.authority_check(ROOT) == ()


def slim_authority(tmp_path, monkeypatch):
    # B4: local pin matrix copies bounded AST declarations/registration only.
    monkeypatch.setattr(
        runner,
        "_arch133_reprovision_recovery_reconciliation_authority_check",
        lambda _: (),
    )
    for relative in runner.ARCH133Y_QUALIFICATION_SOURCES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / relative).read_bytes())
    tree = ast.parse((ROOT / "scripts/checkpoint_runner.py").read_text())
    nodes = [
        n
        for n in tree.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id in ("ARCH133Y_QUALIFICATION_SOURCES", "ACTIVE_CI_CHECKPOINTS")
    ]
    reg = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "CheckpointSpec"
        and any(
            k.arg == "name"
            and isinstance(k.value, ast.Constant)
            and k.value.value == NAME
            for k in n.keywords
        )
    )
    path = tmp_path / "scripts/checkpoint_runner.py"
    path.write_text(
        "\n".join(ast.unparse(n) for n in nodes)
        + "\nregistration = "
        + ast.unparse(reg)
        + "\n"
    )
    workflow = tmp_path / ".github/workflows/checkpoint-source-gates.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_bytes(
        (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_bytes()
    )
    assert runner._arch133_windows_rename_qualification_authority_check(tmp_path) == ()
    return path, workflow


@pytest.mark.parametrize("relative", runner.ARCH133Y_QUALIFICATION_SOURCES)
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_y_all_source_pins_fail_closed(tmp_path, monkeypatch, relative, mutation):
    slim_authority(tmp_path, monkeypatch)
    path = tmp_path / relative
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text(path.read_text(encoding="utf-8-sig") + "\nDRIFT = True\n")
    assert runner._arch133_windows_rename_qualification_authority_check(tmp_path)


@pytest.mark.parametrize(
    "mutation",
    ["inventory", "registration", "active", "order", "duplicate", "workflow"],
)
def test_y_inventory_registration_order_workflow_fail_closed(
    tmp_path, monkeypatch, mutation
):
    path, workflow = slim_authority(tmp_path, monkeypatch)
    text = path.read_text()
    if mutation == "inventory":
        text = text.replace("ARCH133Y_QUALIFICATION_SOURCES", "MISSING_INVENTORY")
    elif mutation == "registration":
        text = text.replace("preflight=None", "preflight=effect")
    elif mutation == "active":
        text = text.replace("ACTIVE_CI_CHECKPOINTS", "MISSING_ACTIVE")
    elif mutation == "order":
        text = text.replace(f"'{X_NAME}', '{NAME}'", f"'{NAME}', '{X_NAME}'")
    elif mutation == "duplicate":
        text = text.replace(f"'{X_NAME}', '{NAME}'", f"'{NAME}', '{NAME}'")
    else:
        workflow.write_text(workflow.read_text().replace(NAME, "missing-checkpoint"))
    path.write_text(text)
    assert runner._arch133_windows_rename_qualification_authority_check(tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: None},
        {"execute": lambda: None},
        {"remote_head_env": "INJECTED"},
        {"remote_branch": "wrong"},
        {"tests": ()},
        {"ruff_paths": ()},
        {"authority_check": lambda _: ()},
    ],
)
def test_y_registration_runtime_capability_injection_rejected(
    tmp_path, monkeypatch, change
):
    slim_authority(tmp_path, monkeypatch)
    specs = runner._checkpoint_specs()
    specs[NAME] = replace(specs[NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._arch133_windows_rename_qualification_authority_check(tmp_path)


@pytest.mark.parametrize("failure", [(), ("X rejected",)])
def test_y_chains_complete_x_once_and_propagates_rejection(monkeypatch, failure):
    seen = []

    def predecessor(root):
        seen.append(root)
        return failure

    monkeypatch.setattr(
        runner,
        "_arch133_reprovision_recovery_reconciliation_authority_check",
        predecessor,
    )
    assert runner._arch133_windows_rename_qualification_authority_check(ROOT) == failure
    assert seen == [ROOT]


def test_second_rename_requires_first_complete_verification(fake):
    edge = native.WindowsScratch()
    edge.admit()
    edge.create(dict.fromkeys(operator.SCRATCH_COUNTERS, 0))
    edge.snapshot()
    edge.rename(native.ACTIVE, native.ARCHIVE)
    with pytest.raises(ValueError):
        edge.rename(native.STAGE, native.ACTIVE)
    assert fake.rename_calls == 1
    edge.verify(1)
    edge.rename(native.STAGE, native.ACTIVE)
    edge.verify(2)
    with pytest.raises(ValueError):
        edge.rename(native.STAGE, native.ACTIVE)
    assert fake.rename_calls == 2
    edge.close()
    edge.cleanup()
    with pytest.raises(ValueError):
        edge.cleanup()


def test_admission_runtime_or_admin_drift_before_create_has_zero_scratch(
    fake, monkeypatch
):
    seen = []

    def admin():
        seen.append(1)
        return "first" if len(seen) == 1 else "changed"

    monkeypatch.setattr(operator, "administrator_sid", admin)
    result = assert_result(operator.run(), "BLOCKED")
    assert result["scratch"] == dict.fromkeys(operator.SCRATCH_COUNTERS, 0)
    assert not fake.path(native.SCRATCH_ROOT).exists()


def test_dangling_cache_junction_blocks_runtime(runtime_fixture, monkeypatch):
    cache = runtime_fixture.cache
    assert not cache.exists()
    monkeypatch.setattr(Path, "is_junction", lambda path: path == cache)
    with pytest.raises(ValueError):
        operator.observe_runtime()
