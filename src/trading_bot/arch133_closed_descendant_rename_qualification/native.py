"""Fixed scratch-only Win32 primitive; no production paths or writer imports."""

from __future__ import annotations

import ctypes
import hashlib
import ntpath
from pathlib import Path

SCRATCH_ROOT = r"F:\AI\temp\arch133z-rename-qualification"
ACTIVE = SCRATCH_ROOT + r"\active"
STAGING_PARENT = SCRATCH_ROOT + r"\stage-parent"
STAGE = STAGING_PARENT + r"\generation"
ARCHIVE = SCRATCH_ROOT + r"\archive"
ANCESTORS = ("F:\\", r"F:\AI", r"F:\AI\temp")
DIRECTORIES = (SCRATCH_ROOT, ACTIVE, STAGING_PARENT, STAGE, ARCHIVE)
FINAL_NAMES = ("activation.json", "host-binding.json", "paper.sqlite", "wake.sqlite")
SYNTHETIC_BYTES = {
    role: {
        name: f"ARCH133Z SYNTHETIC ONLY v1 {role} {name}\n".encode("ascii")
        for name in FINAL_NAMES
    }
    for role in ("predecessor", "staged")
}
DELETE = 0x10000
DIRECTORY_ACCESS = 0x20081
SOURCE_ACCESS = DIRECTORY_ACCESS | DELETE
CHILD_ACCESS = 0x80020080
DIRECTORY_SHARE = 7
CHILD_SHARE = 5
NO_FOLLOW = 0x00200000
DIRECTORY_FLAGS = NO_FOLLOW | 0x02000000


class NativeError(RuntimeError):
    """Only a bounded unsigned Win32 number crosses the native boundary."""

    def __init__(self, code: int) -> None:
        super().__init__("scratch native operation rejected")
        self.native_error_code = (
            code if type(code) is int and 0 <= code <= 0xFFFFFFFF else 0
        )


class FileRenameInfo(ctypes.Structure):
    # WCHAR is always 16 bits, including in Linux fake/layout tests.
    _fields_ = [
        ("ReplaceIfExists", ctypes.c_ubyte),
        ("RootDirectory", ctypes.c_void_p),
        ("FileNameLength", ctypes.c_uint32),
        ("FileName", ctypes.c_uint16 * 1),
    ]


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


def rename_buffer(source: str, destination: str) -> ctypes.Array:
    """Encode only the two fixed absolute, no-replace, NULL-root destinations."""
    if (source, destination) not in ((ACTIVE, ARCHIVE), (STAGE, ACTIVE)) or (
        not ntpath.isabs(destination) or ntpath.splitdrive(destination)[0] != "F:"
    ):
        raise ValueError("scratch rename target rejected")
    name = destination.encode("utf-16-le")
    # Allocate at least sizeof(struct) for the short-name/layout case as well.
    buffer = ctypes.create_string_buffer(
        max(ctypes.sizeof(FileRenameInfo), FileRenameInfo.FileName.offset + len(name))
    )
    info = FileRenameInfo.from_buffer(buffer)
    info.ReplaceIfExists = 0
    info.RootDirectory = None
    info.FileNameLength = len(name)
    ctypes.memmove(
        ctypes.addressof(buffer) + FileRenameInfo.FileName.offset, name, len(name)
    )
    return buffer


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


class WindowsScratch:
    """One invocation owns only the fixed synthetic tree it creates successfully."""

    def __init__(self) -> None:
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.handles: dict[str, int] = {}
        # Includes transient observation and creation handles. Failed closes stay
        # live and cannot be retried or silently removed from this ledger.
        self.live_handles: dict[int, tuple[str, bool]] = {}
        self.close_attempts: set[int] = set()
        self.close_error: BaseException | None = None
        self.rename_attempts: set[tuple[str, str]] = set()
        self.counters: dict[str, int] | None = None
        self.parents: dict[str, tuple[int, int]] = {}
        self.directory_identities: dict[str, tuple[int, int]] = {}
        self.cleanup_started = False
        self.created_identity: tuple[int, int] | None = None
        self.baseline: dict | None = None
        self.rename_step = 0
        self.rename_success_step = 0
        self.snapshot_started = False
        self.closed = False
        self.verified = False
        self.first_verified = False
        self.mutation_started = False

    def _call(self, name: str, arguments: list, result: object, *values):
        return _bind(self.kernel, name, arguments, result)(*values)

    def _require(self, success: object) -> None:
        if not success:
            raise NativeError(ctypes.get_last_error())

    def _track(self, handle: int, path: str, *, directory: bool) -> int:
        if handle in self.live_handles:
            raise ValueError("scratch handle alias rejected")
        self.close_attempts.discard(handle)  # Windows may reuse a closed value.
        self.live_handles[handle] = (path, directory)
        self.closed = False
        return handle

    def _close(self, handle: int) -> None:
        if handle not in self.live_handles or handle in self.close_attempts:
            raise ValueError("scratch handle close reused")
        self.close_attempts.add(handle)
        try:
            self._require(
                self._call("CloseHandle", [ctypes.c_void_p], ctypes.c_int32, handle)
            )
        except BaseException as exc:
            self.close_error = exc
            raise
        del self.live_handles[handle]

    def _assert_descendants_closed(self, source: str) -> None:
        prefix = ntpath.normcase(source).rstrip("\\") + "\\"
        if self.close_error is not None or any(
            ntpath.normcase(path).startswith(prefix)
            for path, _ in self.live_handles.values()
        ):
            raise ValueError("scratch descendant handles remain open")

    def _observe_files(self, current: str, role: str) -> dict:
        self._names(current, FINAL_NAMES)
        files = {}
        for name, raw in SYNTHETIC_BYTES[role].items():
            path = ntpath.join(current, name)
            handle = self._open(path, directory=False)
            try:
                facts = self._file(handle, path)
                if facts["sha256"] != hashlib.sha256(raw).hexdigest():
                    raise ValueError("scratch synthetic bytes rejected")
                if (
                    list(self._temporary_facts(path, directory=False))
                    != facts["identity"]
                ):
                    raise ValueError("scratch child replacement")
                files[name] = facts
            finally:
                self._close(handle)
        self._names(current, FINAL_NAMES)
        self._assert_descendants_closed(current)
        return files

    def _open(self, path: str, *, directory: bool) -> int:
        if directory:
            if path not in (*ANCESTORS, *DIRECTORIES):
                raise ValueError("scratch directory rejected")
            access = SOURCE_ACCESS if path in (ACTIVE, STAGE) else DIRECTORY_ACCESS
            sharing, flags = DIRECTORY_SHARE, DIRECTORY_FLAGS
        else:
            if path not in tuple(
                ntpath.join(root, name)
                for root in (ACTIVE, STAGE, ARCHIVE)
                for name in FINAL_NAMES
            ):
                raise ValueError("scratch child rejected")
            access, sharing, flags = CHILD_ACCESS, CHILD_SHARE, NO_FOLLOW
        handle = self._call(
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
            path,
            access,
            sharing,
            None,
            3,
            flags,
            None,
        )
        if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
            raise NativeError(ctypes.get_last_error())
        return self._track(handle, path, directory=directory)

    def _facts(self, handle: int, path: str, *, directory: bool) -> tuple[int, int]:
        final = ctypes.create_unicode_buffer(512)
        count = self._call(
            "GetFinalPathNameByHandleW",
            [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32],
            ctypes.c_uint32,
            handle,
            final,
            len(final),
            0,
        )
        self._require(count)
        if count >= len(final) or ntpath.normcase(final.value).rstrip("\\") != (
            ntpath.normcase("\\\\?\\" + path).rstrip("\\")
        ):
            raise ValueError("scratch final path rejected")
        info = FileInformation()
        self._require(
            self._call(
                "GetFileInformationByHandle",
                [ctypes.c_void_p, ctypes.c_void_p],
                ctypes.c_int32,
                handle,
                ctypes.byref(info),
            )
        )
        if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
            raise ValueError("scratch reparse/type rejected")
        if not directory and (
            info.links != 1 or info.size_high or info.size_low > 1024
        ):
            raise ValueError("scratch child shape rejected")
        return info.volume, (info.index_high << 32) | info.index_low

    def _file(self, handle: int, path: str) -> dict:
        identity = self._facts(handle, path, directory=False)
        self._require(
            self._call(
                "SetFilePointerEx",
                [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_uint32],
                ctypes.c_int32,
                handle,
                0,
                None,
                0,
            )
        )
        buffer, count = ctypes.create_string_buffer(1025), ctypes.c_uint32()
        self._require(
            self._call(
                "ReadFile",
                [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                ],
                ctypes.c_int32,
                handle,
                buffer,
                len(buffer),
                ctypes.byref(count),
                None,
            )
        )
        if count.value > 1024:
            raise ValueError("scratch byte bound rejected")
        return {
            "identity": list(identity),
            "sha256": hashlib.sha256(buffer.raw[: count.value]).hexdigest(),
        }

    def _temporary_facts(self, path: str, *, directory: bool) -> tuple[int, int]:
        handle = self._open(path, directory=directory)
        try:
            return self._facts(handle, path, directory=directory)
        finally:
            self._close(handle)

    def _absent(self, path: str) -> None:
        try:
            handle = self._open(path, directory=True)
        except NativeError as exc:
            if exc.native_error_code in (2, 3):
                return
            raise
        self._close(handle)
        raise ValueError("scratch vacancy rejected")

    def _names(self, path: str, expected: tuple[str, ...]) -> None:
        self._temporary_facts(path, directory=True)
        if sorted(p.name for p in Path(path).iterdir()) != sorted(expected):
            raise ValueError("scratch namespace rejected")

    def _parents(self) -> None:
        for path, identity in self.parents.items():
            if self._facts(self.handles[path], path, directory=True) != identity:
                raise ValueError("scratch ancestor drift")
            if self._temporary_facts(path, directory=True) != identity:
                raise ValueError("scratch ancestor replacement")

        for original, identity in self.directory_identities.items():
            current = (
                ARCHIVE
                if original == ACTIVE and self.rename_step >= 1
                else ACTIVE
                if original == STAGE and self.rename_step == 2
                else original
            )
            if self._facts(self.handles[original], current, directory=True) != identity:
                raise ValueError("scratch held directory drift")
            if self._temporary_facts(current, directory=True) != identity:
                raise ValueError("scratch directory replacement")

    def admit(self) -> None:
        """Hold and verify each ancestor without following a reparse component."""
        if self.live_handles or self.close_attempts or self.mutation_started:
            raise ValueError("scratch invocation reused")
        filesystem = ctypes.create_unicode_buffer(32)
        self._require(
            self._call(
                "GetVolumeInformationW",
                [
                    ctypes.c_wchar_p,
                    ctypes.c_wchar_p,
                    ctypes.c_uint32,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_wchar_p,
                    ctypes.c_uint32,
                ],
                ctypes.c_int32,
                "F:\\",
                None,
                0,
                None,
                None,
                None,
                filesystem,
                len(filesystem),
            )
        )
        if (
            filesystem.value != "NTFS"
            or self._call("GetDriveTypeW", [ctypes.c_wchar_p], ctypes.c_uint32, "F:\\")
            != 3
        ):
            raise ValueError("scratch local NTFS rejected")
        for path in ANCESTORS:
            self._parents()
            self.handles[path] = self._open(path, directory=True)
            self.parents[path] = self._facts(self.handles[path], path, directory=True)
        self._absent(SCRATCH_ROOT)

    def create(self, counters: dict[str, int]) -> None:
        if self.mutation_started or not self.parents:
            raise ValueError("scratch creation authority rejected")
        self._parents()
        self._absent(SCRATCH_ROOT)
        # From this point even an ambiguous first mkdir preserves all scratch evidence.
        self.mutation_started = True
        self.counters = counters
        counters["topology_creation_attempts"] += 1
        for path in (SCRATCH_ROOT, ACTIVE, STAGING_PARENT, STAGE):
            self._parents()
            if path != SCRATCH_ROOT:
                self._temporary_facts(SCRATCH_ROOT, directory=True)
            self._require(
                self._call(
                    "CreateDirectoryW",
                    [ctypes.c_wchar_p, ctypes.c_void_p],
                    ctypes.c_int32,
                    path,
                    None,
                )
            )
            self.handles[path] = self._open(path, directory=True)
            identity = self._facts(self.handles[path], path, directory=True)
            self.directory_identities[path] = identity
            if path == SCRATCH_ROOT:
                self.created_identity = identity
        for root, role in ((ACTIVE, "predecessor"), (STAGE, "staged")):
            for name, raw in SYNTHETIC_BYTES[role].items():
                self._parents()
                self._facts(self.handles[root], root, directory=True)
                path = ntpath.join(root, name)
                handle = self._call(
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
                    path,
                    0x40000000,
                    0,
                    None,
                    1,
                    NO_FOLLOW,
                    None,
                )
                if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
                    raise NativeError(ctypes.get_last_error())
                self._track(handle, path, directory=False)
                try:
                    count = ctypes.c_uint32()
                    self._require(
                        self._call(
                            "WriteFile",
                            [
                                ctypes.c_void_p,
                                ctypes.c_void_p,
                                ctypes.c_uint32,
                                ctypes.c_void_p,
                                ctypes.c_void_p,
                            ],
                            ctypes.c_int32,
                            handle,
                            raw,
                            len(raw),
                            ctypes.byref(count),
                            None,
                        )
                    )
                    if count.value != len(raw):
                        raise ValueError("scratch short write")
                    self._require(
                        self._call(
                            "FlushFileBuffers",
                            [ctypes.c_void_p],
                            ctypes.c_int32,
                            handle,
                        )
                    )
                finally:
                    self._close(handle)
        counters["topology_creations_completed"] += 1

    def snapshot(self) -> dict:
        """Pin all synthetic identities/hashes and successfully close every child."""
        if self.snapshot_started or len(self.directory_identities) != 4:
            raise ValueError("scratch snapshot authority rejected")
        self.snapshot_started = True
        self._parents()
        self._absent(ARCHIVE)
        self._names(SCRATCH_ROOT, ("active", "stage-parent"))
        self._names(STAGING_PARENT, ("generation",))
        result = {
            "root": list(
                self._facts(self.handles[SCRATCH_ROOT], SCRATCH_ROOT, directory=True)
            ),
            "stage_parent": list(
                self._facts(
                    self.handles[STAGING_PARENT], STAGING_PARENT, directory=True
                )
            ),
        }
        for root, role in ((ACTIVE, "predecessor"), (STAGE, "staged")):
            self._names(root, FINAL_NAMES)
            files = self._observe_files(root, role)
            result[role] = {
                "identity": list(self._facts(self.handles[root], root, directory=True)),
                "files": files,
            }
        if (
            len(
                {
                    tuple(v)
                    for v in (
                        result["root"],
                        result["stage_parent"],
                        result["predecessor"]["identity"],
                        result["staged"]["identity"],
                    )
                }
            )
            != 4
        ):
            raise ValueError("scratch directory alias rejected")
        volume = self.parents[ANCESTORS[0]][0]
        identities = [result["root"], result["stage_parent"]]
        for role in ("predecessor", "staged"):
            identities.append(result[role]["identity"])
            identities.extend(f["identity"] for f in result[role]["files"].values())
        if any(i[0] != volume for i in (*self.parents.values(), *identities)) or (
            len({tuple(i) for i in identities}) != 12
        ):
            raise ValueError("scratch volume/file alias rejected")
        self.baseline = result
        return result

    def rename(self, source: str, destination: str) -> None:
        sequence = ((ACTIVE, ARCHIVE), (STAGE, ACTIVE))
        if (
            self.baseline is None
            or (source, destination) in self.rename_attempts
            or self.close_error is not None
            or (self.rename_step == 1 and not self.first_verified)
            or self.rename_step >= 2
            or (source, destination) != sequence[self.rename_step]
        ):
            raise ValueError("scratch rename order rejected")
        self.rename_attempts.add((source, destination))
        role = "predecessor" if self.rename_step == 0 else "staged"
        if self._observe_files(source, role) != self.baseline[role]["files"]:
            raise ValueError("scratch pre-rename child drift")
        self._parents()
        self._names(
            SCRATCH_ROOT,
            ("active", "stage-parent")
            if self.rename_step == 0
            else ("archive", "stage-parent"),
        )
        self._names(STAGING_PARENT, ("generation",))
        self._names(source, FINAL_NAMES)
        self._absent(destination)
        self._facts(self.handles[source], source, directory=True)
        buffer = rename_buffer(source, destination)
        self._assert_descendants_closed(source)
        # Consume the step before API entry: a failure cannot authorize another call.
        self.rename_step += 1
        counter = "first" if self.rename_step == 1 else "second"
        if self.counters is None:
            raise ValueError("scratch counters unavailable")
        self.counters[counter + "_rename_attempts"] += 1
        self._require(
            self._call(
                "SetFileInformationByHandle",
                [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32],
                ctypes.c_int32,
                self.handles[source],
                3,
                buffer,
                len(buffer),
            )
        )
        self.counters[counter + "_renames_completed"] += 1
        self.rename_success_step = self.rename_step

    def verify(self, step: int) -> dict:
        if (
            self.baseline is None
            or step != self.rename_step
            or step != self.rename_success_step
            or step not in (1, 2)
            or self.close_error is not None
        ):
            raise ValueError("scratch verification order rejected")
        self._parents()
        if self._facts(self.handles[SCRATCH_ROOT], SCRATCH_ROOT, directory=True) != (
            self.created_identity
        ):
            raise ValueError("scratch invocation root changed")
        self._names(
            SCRATCH_ROOT,
            ("archive", "stage-parent")
            if step == 1
            else ("active", "archive", "stage-parent"),
        )
        self._absent(ACTIVE if step == 1 else STAGE)
        self._names(STAGING_PARENT, ("generation",) if step == 1 else ())
        if (
            list(
                self._facts(
                    self.handles[STAGING_PARENT], STAGING_PARENT, directory=True
                )
            )
            != (self.baseline["stage_parent"])
        ):
            raise ValueError("scratch stage parent changed")
        result = {
            "root": self.baseline["root"],
            "stage_parent": self.baseline["stage_parent"],
        }
        for original, current, role in (
            (ACTIVE, ARCHIVE, "predecessor"),
            (STAGE, STAGE if step == 1 else ACTIVE, "staged"),
        ):
            self._names(current, FINAL_NAMES)
            identity = self._facts(self.handles[original], current, directory=True)
            if self._temporary_facts(current, directory=True) != identity:
                raise ValueError("scratch directory replacement")
            files = self._observe_files(current, role)
            result[role] = {"identity": list(identity), "files": files}
        self._parents()
        self._names(
            SCRATCH_ROOT,
            ("archive", "stage-parent")
            if step == 1
            else ("active", "archive", "stage-parent"),
        )
        self._names(STAGING_PARENT, ("generation",) if step == 1 else ())
        for current in (ARCHIVE, STAGE if step == 1 else ACTIVE):
            self._names(current, FINAL_NAMES)
        if result != self.baseline:
            raise ValueError("scratch reopened identity/hash drift")
        if step == 1:
            self.first_verified = True
        if step == 2:
            self.verified = True
        return result

    def close(self) -> None:
        failures = []
        for handle in reversed(tuple(self.live_handles)):
            if handle in self.close_attempts:
                continue
            try:
                self._close(handle)
            except BaseException as exc:
                failures.append(exc)
        if self.close_error is not None:
            failures.append(self.close_error)
        self.closed = not self.live_handles and not failures
        if failures:
            raise failures[0]
        if not self.closed:
            raise ValueError("scratch handles remain open")
        self.handles.clear()

    def cleanup(self) -> None:
        """Verify and delete only our successful fixed tree; no recursive deletion."""
        if not (
            not self.cleanup_started
            and self.closed
            and not self.live_handles
            and self.close_error is None
            and self.verified
            and self.rename_step == 2
            and self.baseline
            and self.created_identity
            and self.mutation_started
        ):
            raise ValueError("scratch cleanup authority rejected")
        # Reopen all fixed objects; forbid replacements, reparse points and extra names.
        self.cleanup_started = True
        self.closed = False
        try:
            for path, identity in self.parents.items():
                self.handles[path] = self._open(path, directory=True)
                if self._facts(self.handles[path], path, directory=True) != identity:
                    raise ValueError("scratch cleanup parent changed")
            self.handles[SCRATCH_ROOT] = self._open(SCRATCH_ROOT, directory=True)
            self.handles[STAGING_PARENT] = self._open(STAGING_PARENT, directory=True)
            for original, current in ((ACTIVE, ARCHIVE), (STAGE, ACTIVE)):
                self.handles[original] = self._open(current, directory=True)
            self.verify(2)
            for original, current in ((ACTIVE, ARCHIVE), (STAGE, ACTIVE)):
                role = "predecessor" if original == ACTIVE else "staged"
                for index, name in enumerate(FINAL_NAMES):
                    self._parents()
                    self._names(SCRATCH_ROOT, ("active", "archive", "stage-parent"))
                    self._names(STAGING_PARENT, ())
                    self._names(current, FINAL_NAMES[index:])
                    path = ntpath.join(current, name)
                    handle = self._open(path, directory=False)
                    try:
                        if (
                            self._file(handle, path)
                            != self.baseline[role]["files"][name]
                        ):
                            raise ValueError("scratch cleanup child changed")
                    finally:
                        self._close(handle)
                    self._assert_descendants_closed(current)
                    self._require(
                        self._call(
                            "DeleteFileW",
                            [ctypes.c_wchar_p],
                            ctypes.c_int32,
                            path,
                        )
                    )
            # All observation handles closed before deletion; release directory guards.
            self.close()
            for path, identity in (
                (ARCHIVE, self.baseline["predecessor"]["identity"]),
                (ACTIVE, self.baseline["staged"]["identity"]),
                (STAGING_PARENT, self.baseline["stage_parent"]),
                (SCRATCH_ROOT, self.baseline["root"]),
            ):
                for parent, expected in self.parents.items():
                    if self._temporary_facts(parent, directory=True) != expected:
                        raise ValueError("scratch cleanup ancestor changed")
                if list(self._temporary_facts(path, directory=True)) != identity:
                    raise ValueError("scratch cleanup directory changed")
                self._names(path, ())
                self._require(
                    self._call(
                        "RemoveDirectoryW",
                        [ctypes.c_wchar_p],
                        ctypes.c_int32,
                        path,
                    )
                )
            self._absent(SCRATCH_ROOT)
        finally:
            self.close()
