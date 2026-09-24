"""Focused portable A124-2 fixed D10 guard-substrate tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts import run_personal_desktop_d10_launch_guard as guard
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as scheduler,
)


class FakeNative:
    def __init__(self) -> None:
        self.paths: dict[int, str] = {}
        self.closed: list[int] = []
        self.probed: list[str] = []
        self.read_handles: list[int] = []
        self.next_handle = 1
        self.overrides: dict[str, dict[str, object]] = {}
        self.after: dict[str, dict[str, object]] = {}
        self.present: set[str] = set()
        self.error: str | None = None
        self.inspections: dict[str, int] = {}
        self.data = {
            guard.D10_LAUNCH_GUARD: b"g",
            guard.D10_ATTESTATION: b"a",
            guard.D10_SIGNATURE: b"s" * 64,
            guard.D10_MANIFEST: b"m",
        }

    def open(self, path: str, *, directory: bool) -> int:
        guard._expected_path(path)
        handle = self.next_handle
        self.next_handle += 1
        self.paths[handle] = path
        return handle

    def close(self, handle: int) -> None:
        self.closed.append(handle)

    def require_absent(self, path: str) -> None:
        assert path in guard._ABSENT
        self.probed.append(path)
        if path in self.present or path == self.error:
            raise guard.GuardBlocked("presence probe blocked")

    def inspect(self, handle: int) -> guard.ObjectFacts:
        path = self.paths[handle]
        self.inspections[path] = self.inspections.get(path, 0) + 1
        directory = path in guard._DIRECTORIES or path not in self.data
        policy = guard.DIRECTORY_POLICY if directory else guard.FILE_POLICY
        values: dict[str, object] = {
            "final_path": path,
            "attributes": guard.FILE_ATTRIBUTE_DIRECTORY if directory else 0,
            "drive_type": guard.DRIVE_FIXED,
            "volume_root": "F:\\",
            "filesystem": "NTFS",
            "volume_serial": 41,
            "file_index": handle,
            "links": 1,
            "size": 0 if directory else len(self.data[path]),
            "owner": policy.owner,
            "protected": True,
            "aces": policy.aces,
        }
        values.update(self.overrides.get(path, {}))
        if self.inspections[path] > 1:
            values.update(self.after.get(path, {}))
        return guard.ObjectFacts(**values)

    def read_exact(self, handle: int, size: int) -> bytes:
        self.read_handles.append(handle)
        return self.data[self.paths[handle]]


def test_fixed_paths_and_measured_runtime_package_root() -> None:
    assert guard.D10_ROOT == r"F:\AITradingBot\D10"
    assert guard.D10_LAUNCH_GUARD == guard.D10_ROOT + r"\launch-guard.py"
    assert guard.D10_ATTESTATION == guard.D10_ROOT + r"\deployment.attestation.json"
    assert guard.D10_SIGNATURE == guard.D10_ROOT + r"\deployment.attestation.sig"
    assert guard.D10_MANIFEST == guard.D10_ROOT + r"\executable-manifest.json"
    assert guard.D10_SOURCE_ROOT == guard.D10_ROOT + r"\source"
    assert guard.D10_SOURCE_PACKAGE_ROOT == guard.D10_SOURCE_ROOT + r"\src"
    assert guard.D10_CACHE_PREFIX == guard.D10_ROOT + r"\no-pycache"
    assert guard.D10_PRODUCTION_PYTHON == r"F:\AITradingBot\runtime\python.exe"
    assert (
        guard.D10_PRODUCTION_SITE_PACKAGES
        == r"F:\AITradingBot\runtime\Lib\site-packages"
    )
    assert guard._INSTALLING == (
        guard.D10_LAUNCH_GUARD + ".installing",
        guard.D10_ATTESTATION + ".installing",
        guard.D10_SIGNATURE + ".installing",
        guard.D10_MANIFEST + ".installing",
        guard.D10_SOURCE_ROOT + ".installing",
    )
    assert guard._ABSENT[-1] == guard.D10_CACHE_PREFIX

    assert guard.D10_LAUNCH_GUARD == str(scheduler.D10_LAUNCH_GUARD)
    assert guard.D10_SOURCE_ROOT == str(scheduler.D10_SOURCE_ROOT)
    assert guard.D10_SECOND_STAGE_LAUNCHER == str(scheduler.D10_SECOND_STAGE_LAUNCHER)


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AITradingBot\D10\other",
        r"F:\AITradingBot\D10\source\..\launch-guard.py",
        r"f:\AITradingBot\D10\launch-guard.py",
        r"\\server\share\launch-guard.py",
        r"\\.\F:\AITradingBot\D10\launch-guard.py",
        r"\\?\F:\AITradingBot\D10\launch-guard.py",
        r"C:\AITradingBot\D10\launch-guard.py",
        guard.D10_CACHE_PREFIX,
        guard.D10_LAUNCH_GUARD + ".installing",
    ],
)
def test_arbitrary_absolute_path_cannot_open(path: str) -> None:
    with pytest.raises(guard.GuardBlocked):
        guard._Native().open(path, directory=False)


def test_exact_acl_and_mutation_rights() -> None:
    assert guard.DIRECTORY_POLICY.owner == guard.ADMINISTRATORS_SID
    assert guard.FILE_POLICY.owner == guard.ADMINISTRATORS_SID
    assert guard.DIRECTORY_POLICY.protected
    assert guard.FILE_POLICY.protected
    assert guard.DIRECTORY_POLICY.aces[:2] == (
        guard.Ace(guard.ADMINISTRATORS_SID, guard.FILE_ALL_ACCESS),
        guard.Ace(guard.SYSTEM_SID, guard.FILE_ALL_ACCESS),
    )
    assert guard.DIRECTORY_POLICY.aces[2].mask == 0x1200A9
    assert guard.FILE_POLICY.aces[2].mask == 0x120089
    forbidden = 0x0002 | 0x0004 | 0x0010 | 0x0040 | 0x0100 | 0x10000 | 0x40000 | 0x80000
    assert not guard.DIRECTORY_POLICY.aces[2].mask & forbidden
    assert not guard.FILE_POLICY.aces[2].mask & forbidden


@pytest.mark.parametrize(
    ("path", "change"),
    [
        (guard.D10_ROOT, {"owner": guard.SYSTEM_SID}),
        (guard.D10_ROOT, {"protected": False}),
        (guard.D10_ROOT, {"aces": tuple(reversed(guard.DIRECTORY_POLICY.aces))}),
        (guard.D10_ROOT, {"aces": guard.DIRECTORY_POLICY.aces[:2]}),
        (
            guard.D10_LAUNCH_GUARD,
            {
                "aces": (
                    *guard.FILE_POLICY.aces[:2],
                    guard.Ace(guard.TRADING_SID, guard.TRADING_FILE_READ | 2),
                )
            },
        ),
        (
            guard.D10_LAUNCH_GUARD,
            {"final_path": r"F:\AITradingBot\other\launch-guard.py"},
        ),
        (
            guard.D10_LAUNCH_GUARD,
            {"final_path": r"f:\AITradingBot\D10\launch-guard.py"},
        ),
        (guard.D10_LAUNCH_GUARD, {"attributes": guard.FILE_ATTRIBUTE_REPARSE_POINT}),
        (guard.D10_LAUNCH_GUARD, {"attributes": guard.FILE_ATTRIBUTE_DIRECTORY}),
        (guard.D10_LAUNCH_GUARD, {"drive_type": 4}),
        (guard.D10_LAUNCH_GUARD, {"volume_root": "E:\\"}),
        (guard.D10_LAUNCH_GUARD, {"filesystem": "ReFS"}),
        (guard.D10_LAUNCH_GUARD, {"links": 2}),
    ],
)
def test_exact_object_admission_fails_closed(
    path: str, change: dict[str, object]
) -> None:
    native = FakeNative()
    native.overrides[path] = change
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_trust_material(native)
    assert set(native.closed) == set(native.paths)


@pytest.mark.parametrize(
    "field", ["file_index", "volume_serial", "size", "owner", "aces"]
)
def test_final_reinspection_drift_blocks(field: str) -> None:
    native = FakeNative()
    drift = {
        "file_index": 99,
        "volume_serial": 99,
        "size": 99,
        "owner": guard.SYSTEM_SID,
        "aces": tuple(reversed(guard.FILE_POLICY.aces)),
    }
    native.after[guard.D10_SIGNATURE] = {field: drift[field]}
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_trust_material(native)


def test_same_handle_bounded_pinned_read_and_sanitized_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative()
    bundle = guard._read_fixed_trust_material(native)
    assert bundle.signature == b"s" * 64
    assert len(native.read_handles) == 4
    assert all(handle in native.paths for handle in native.read_handles)
    assert set(native.closed) == set(native.paths)
    assert native.probed == list(guard._ABSENT)
    assert all(value == 2 for value in native.inspections.values())
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    monkeypatch.setattr(guard, "_read_fixed_trust_material", lambda: bundle)
    assert guard.verify_fixed_trust_material() == (1, 1, 64, 1)


@pytest.mark.parametrize(
    "path",
    [
        guard.D10_LAUNCH_GUARD,
        guard.D10_ATTESTATION,
        guard.D10_SIGNATURE,
        guard.D10_MANIFEST,
    ],
)
def test_trust_file_bounds(path: str) -> None:
    native = FakeNative()
    native.overrides[path] = {"size": guard._FILE_LIMITS[path] + 1}
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_trust_material(native)


def test_signature_exact_length() -> None:
    native = FakeNative()
    native.data[guard.D10_SIGNATURE] = b"s" * 63
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_trust_material(native)


@pytest.mark.parametrize("path", guard._ABSENT)
def test_reserved_names_presence_blocks(path: str) -> None:
    native = FakeNative()
    native.present.add(path)
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_trust_material(native)


def test_presence_probe_ambiguity_blocks() -> None:
    native = FakeNative()
    native.error = guard.D10_CACHE_PREFIX
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_trust_material(native)


@pytest.mark.parametrize(
    ("token", "local"),
    [
        (("bad", False, False), guard.TRADING_SID),
        ((guard.TRADING_SID, False, False), "bad"),
        ((guard.TRADING_SID, True, False), guard.TRADING_SID),
        ((guard.TRADING_SID, False, True), guard.TRADING_SID),
    ],
)
def test_wrong_trading_principal_blocks(
    monkeypatch: pytest.MonkeyPatch, token: tuple[str, bool, bool], local: str
) -> None:
    monkeypatch.setattr(guard, "_current_token_facts", lambda: token)
    monkeypatch.setattr(guard, "_resolved_local_trading_sid", lambda: local)
    with pytest.raises(guard.GuardBlocked):
        guard.require_trading_principal()


@pytest.mark.parametrize(
    "relative",
    [
        "../src/trading_bot/x.py",
        "/src/trading_bot/x.py",
        "SRC/trading_bot/x.py",
        "src/Trading_bot/x.py",
        r"src\trading_bot\x.py",
        "src/trading_bot/../../x.py",
        "src/trading_bot/x.py:ads",
        "src/trading_bot/__pycache__/x.py",
        "src/trading_bot/x.pyc",
        "src/trading_bot/x.pyo",
        "src/trading_bot/con.py",
        "src/trading_bot/x.",
        "src/trading_bot/x ",
        "src/trading_bot//x.py",
        "src/trading_bot/x?.py",
        r"\\server\share\x.py",
    ],
)
def test_sealed_source_path_rejections(relative: str) -> None:
    with pytest.raises(guard.GuardBlocked):
        guard._source_path(relative)


def test_sealed_source_file_pins_ancestors() -> None:
    native = FakeNative()
    target = guard._source_path("src/trading_bot/mod.py")
    native.data[target] = b"x"
    result = guard.inspect_sealed_source_file("src/trading_bot/mod.py", native)
    assert result.final_path == target
    assert set(native.paths.values()) == {
        guard.D10_ROOT,
        guard.D10_SOURCE_ROOT,
        guard.D10_SOURCE_PACKAGE_ROOT,
        guard.D10_SOURCE_PACKAGE_ROOT + r"\trading_bot",
        target,
    }
    assert set(native.closed) == set(native.paths)


def test_stdlib_only_no_effects_and_arch77_separation() -> None:
    source = Path(guard.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imports <= {
        "__future__",
        "ctypes",
        "ntpath",
        "os",
        "re",
        "contextlib",
        "dataclasses",
    }
    assert not imports & {"site", "trading_bot", "subprocess", "scripts"}
    forbidden_calls = {
        "WriteFile",
        "CreateProcessW",
        "ShellExecuteW",
        "SetSecurityInfo",
        "CreateDirectoryW",
        "SetFileInformationByHandle",
        "site.main",
    }
    assert not any(name in source for name in forbidden_calls)
    assert not any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and "__name__" in ast.unparse(node.test)
        for node in tree.body
    )

    from trading_bot.runtime.windows_authority import PRODUCTION_AUTHORITY_PATHS

    assert guard.D10_ROOT not in {
        str(path) for path in PRODUCTION_AUTHORITY_PATHS.protected_objects
    }


def test_sealed_source_ancestor_drift_blocks() -> None:
    native = FakeNative()
    target = guard._source_path("src/trading_bot/mod.py")
    native.data[target] = b"x"
    native.after[guard.D10_SOURCE_PACKAGE_ROOT] = {"owner": guard.SYSTEM_SID}
    with pytest.raises(guard.GuardBlocked):
        guard.inspect_sealed_source_file("src/trading_bot/mod.py", native)
    assert set(native.closed) == set(native.paths)


@pytest.mark.parametrize(
    ("error", "accepted"), [(2, True), (3, True), (5, False), (0, False)]
)
def test_native_absence_requires_only_not_found_errors(
    monkeypatch: pytest.MonkeyPatch, error: int, accepted: bool
) -> None:
    class Function:
        argtypes = None
        restype = None

        def __call__(self, *args: object) -> int:
            return guard._INVALID_HANDLE

    class Kernel:
        CreateFileW = Function()

    monkeypatch.setattr(guard, "_win_dll", lambda _: Kernel())
    monkeypatch.setattr(guard.ctypes, "get_last_error", lambda: error, raising=False)
    if accepted:
        guard._Native().require_absent(guard.D10_CACHE_PREFIX)
    else:
        with pytest.raises(guard.GuardBlocked):
            guard._Native().require_absent(guard.D10_CACHE_PREFIX)


def test_native_open_uses_no_follow_and_read_only_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    class Function:
        argtypes = None
        restype = None

        def __call__(self, *args: object) -> int:
            calls.append(args)
            return 7

    class Kernel:
        CreateFileW = Function()

    monkeypatch.setattr(guard, "_win_dll", lambda _: Kernel())
    assert guard._Native().open(guard.D10_LAUNCH_GUARD, directory=False) == 7
    assert len(calls) == 1
    args = calls[0]
    assert args[0] == guard.D10_LAUNCH_GUARD
    assert args[1] == (
        guard.FILE_READ_DATA
        | guard.FILE_READ_ATTRIBUTES
        | guard.READ_CONTROL
        | guard.SYNCHRONIZE
    )
    assert args[2] == 1  # FILE_SHARE_READ
    assert args[4] == 3  # OPEN_EXISTING
    assert args[5] & guard.FILE_FLAG_OPEN_REPARSE_POINT
