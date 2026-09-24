"""Focused portable A124-2 fixed D10 guard-substrate tests."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_personal_desktop_d10_launch_guard as guard
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as scheduler,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    EXECUTABLE_MANIFEST_SCHEMA,
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
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
    monkeypatch.setattr(guard, "_require_standard_account", lambda _: None)
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
        "hashlib",
        "json",
        "subprocess",
        "sys",
        "uuid",
    }
    assert not imports & {"site", "trading_bot", "scripts"}
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
    assert any(
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


class FullNative(FakeNative):
    def __init__(self) -> None:
        super().__init__()
        self.extra: dict[str, set[str]] = {}
        self.hash_handles: list[int] = []
        self.data[guard._source_path("src/trading_bot/mod.py")] = b"module"
        self.data[guard.D10_SECOND_STAGE_LAUNCHER] = b"launcher"
        self.data[guard.D10_LAUNCH_GUARD] = b"guard source"
        self.data[guard.D10_SIGNATURE] = b"x" * 64
        self.make_signed_material()

    def make_signed_material(self, **changes: object) -> None:
        entries = tuple(
            ExecutableManifestEntry(
                relative,
                len(self.data[guard._source_path(relative)]),
                hashlib.sha256(self.data[guard._source_path(relative)]).hexdigest(),
            )
            for relative in (
                "scripts/run_personal_desktop_unattended_one_week_soak.py",
                "src/trading_bot/mod.py",
            )
        )
        manifest = ExecutableManifest(EXECUTABLE_MANIFEST_SCHEMA, entries)
        values = dict(
            certified_source_head="a" * 40,
            certified_source_tree="b" * 40,
            production_python_version=".".join(map(str, sys.version_info[:3])),
            launch_guard_byte_length=len(self.data[guard.D10_LAUNCH_GUARD]),
            launch_guard_sha256=hashlib.sha256(
                self.data[guard.D10_LAUNCH_GUARD]
            ).hexdigest(),
            executable_manifest_sha256=manifest.digest,
            executable_file_count=len(entries),
        )
        values.update(changes)
        self.data[guard.D10_MANIFEST] = manifest.canonical_bytes()
        self.data[guard.D10_ATTESTATION] = build_deployment_attestation(
            **values
        ).canonical_bytes()

    def listdir(self, path: str) -> tuple[str, ...]:
        prefix = path + chr(92)
        names: set[str] = set()
        for filepath in self.data:
            if filepath.startswith(prefix):
                names.add(filepath[len(prefix) :].split(chr(92), 1)[0])
        return tuple(sorted(names | self.extra.get(path, set())))

    def hash_exact(self, handle: int, size: int) -> str:
        self.hash_handles.append(handle)
        data = self.data[self.paths[handle]]
        if len(data) != size:
            raise guard.GuardBlocked("fake same-handle size drift")
        return hashlib.sha256(data).hexdigest()


def _admit(monkeypatch: pytest.MonkeyPatch, native: FullNative) -> None:
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    monkeypatch.setattr(guard, "_verify_d10_signature", lambda *args: None)
    monkeypatch.setattr(guard, "_require_runtime", lambda _: None)
    guard._verify_pre_source(native)


def test_a1243_complete_inventory_and_same_handle_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FullNative()
    _admit(monkeypatch, native)
    assert len(native.hash_handles) == 2
    assert all(native.paths[handle] in native.data for handle in native.hash_handles)
    assert set(native.hash_handles) <= set(native.closed)
    assert set(native.closed) == set(native.paths)
    assert native.inspections[guard.D10_LAUNCH_GUARD] == 4


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "signing_key_id",
        "source_root",
        "launch_guard",
        "launcher",
        "scheduler_contract_schema",
        "approved_trading_sid",
        "production_python",
        "production_python_version",
        "certified_source_head",
        "certified_source_tree",
        "deployment_id",
        "executable_manifest_sha256",
        "executable_file_count",
        "launch_guard_byte_length",
        "launch_guard_sha256",
    ],
)
def test_a1243_wrong_attestation_fact_blocks(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    native = FullNative()
    value = json.loads(native.data[guard.D10_ATTESTATION])
    value[field] = "wrong"
    native.data[guard.D10_ATTESTATION] = guard._canonical_json(value)
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data + b" ",
        lambda data: data.replace(
            b',"launcher":', b',"launcher":"duplicate","launcher":'
        ),
        lambda data: b"\xef\xbb\xbf" + data,
        lambda data: data.replace(b'"schema":', b'"extra":1,"schema":'),
    ],
)
def test_a1243_noncanonical_or_duplicate_attestation_blocks(
    monkeypatch: pytest.MonkeyPatch,
    mutation,
) -> None:
    native = FullNative()
    native.data[guard.D10_ATTESTATION] = mutation(native.data[guard.D10_ATTESTATION])
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data + b" ",
        lambda data: data.replace(b',"schema":', b',"schema":"duplicate","schema":'),
        lambda data: data.replace(b'"relative_path":', b'"other":1,"relative_path":'),
        lambda data: data.replace(
            b'"schema":"personal-desktop-d10-executable-manifest/v1"', b'"schema":"bad"'
        ),
    ],
)
def test_a1243_manifest_canonical_schema_and_fields_block(
    monkeypatch: pytest.MonkeyPatch,
    mutation,
) -> None:
    native = FullNative()
    native.data[guard.D10_MANIFEST] = mutation(native.data[guard.D10_MANIFEST])
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)


@pytest.mark.parametrize(
    "relative",
    [
        "src/trading_bot/../bad.py",
        "src/trading_bot/.git/config",
        "src/trading_bot/__pycache__/x.pyc",
        "src/trading_bot/x.pyo",
        "src/trading_bot/x.py:ads",
        "src/trading_bot/con.py",
    ],
)
def test_a1243_unsafe_manifest_path_blocks(relative: str) -> None:
    with pytest.raises(guard.GuardBlocked):
        guard._source_path(relative)


@pytest.mark.parametrize(
    "extra",
    [
        ".git",
        "__pycache__",
        "unexpected",
        "mod.pyc",
        "mod.pyo",
        "MOD.py",
    ],
)
def test_a1243_extra_or_case_colliding_inventory_blocks(
    monkeypatch: pytest.MonkeyPatch,
    extra: str,
) -> None:
    native = FullNative()
    native.extra[guard.D10_SOURCE_ROOT + r"\src\trading_bot"] = {extra}
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)


def test_a1243_missing_inventory_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    native = FullNative()
    del native.data[guard._source_path("src/trading_bot/mod.py")]
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)


@pytest.mark.parametrize(
    "change",
    [
        {"attributes": guard.FILE_ATTRIBUTE_REPARSE_POINT},
        {"links": 2},
        {"owner": guard.SYSTEM_SID},
    ],
)
def test_a1243_source_security_blocks(
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, object],
) -> None:
    native = FullNative()
    native.overrides[guard._source_path("src/trading_bot/mod.py")] = change
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)


def test_a1243_same_handle_source_drift_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FullNative()
    native.after[guard._source_path("src/trading_bot/mod.py")] = {"size": 99}
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)


def test_a1243_guard_and_manifest_digest_mismatch_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FullNative()
    native.data[guard.D10_LAUNCH_GUARD] += b"!"
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)
    native = FullNative()
    native.data[guard.D10_MANIFEST] += b" "
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)


def test_a1243_signature_precedes_attestation_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FullNative()
    native.data[guard.D10_ATTESTATION] = b"invalid"
    calls: list[str] = []
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)

    def reject(*_args: object) -> None:
        calls.append("signature")
        raise guard.GuardBlocked("signature rejected")

    monkeypatch.setattr(guard, "_verify_d10_signature", reject)
    monkeypatch.setattr(guard, "_parse_attestation", lambda _: calls.append("parse"))
    with pytest.raises(guard.GuardBlocked):
        guard._verify_pre_source(native)
    assert calls == ["signature"]


def test_a1243_account_drift_blocks_before_trust_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FullNative()
    monkeypatch.setattr(
        guard, "_current_token_facts", lambda: (guard.TRADING_SID, False, False)
    )
    monkeypatch.setattr(guard, "_resolved_local_trading_sid", lambda: guard.TRADING_SID)
    monkeypatch.setattr(
        guard,
        "_require_standard_account",
        lambda _: (_ for _ in ()).throw(guard.GuardBlocked("privileged group")),
    )
    with pytest.raises(guard.GuardBlocked):
        guard._verify_pre_source(native)
    assert native.paths == {}


def test_a1243_exact_one_child_and_zero_child_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(guard, "_verify_pre_source", lambda: None)
    monkeypatch.setattr(guard, "_require_active_lease", lambda: None)
    monkeypatch.setattr(
        guard,
        "_sanitized_environment",
        lambda: {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
    )

    def child(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(guard.subprocess, "run", child)
    assert guard.main() == 0
    assert calls == [
        (
            [
                guard.D10_PRODUCTION_PYTHON,
                "-I",
                "-S",
                "-B",
                "-X",
                f"pycache_prefix={guard.D10_CACHE_PREFIX}",
                guard.D10_SECOND_STAGE_LAUNCHER,
            ],
            {
                "check": False,
                "cwd": guard.D10_ROOT,
                "env": {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
                "close_fds": True,
            },
        )
    ]
    calls.clear()
    monkeypatch.setattr(
        guard,
        "_verify_pre_source",
        lambda: (_ for _ in ()).throw(guard.GuardBlocked("drift")),
    )
    assert guard.main() == 1
    assert not calls


def test_a1243_second_stage_bootstrap_is_fixed_and_fail_closed() -> None:
    path = (
        Path(__file__).parents[2]
        / "scripts"
        / "run_personal_desktop_unattended_one_week_soak.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "site.main" not in source
    assert ".pth" not in source
    assert "sitecustomize" not in source
    assert "usercustomize" not in source
    assert "F:\\AITradingBot\\D10\\source\\src" in source
    assert "F:\\AITradingBot\\runtime\\Lib\\site-packages" in source
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module
        == "trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract"  # noqa: E501
        for node in ast.walk(tree)
    )


def test_a1243_native_cng_positive_and_adversarial_signature() -> None:
    """Use an ephemeral CNG test key; no signing secret enters the repository."""
    import ctypes
    import os
    from ctypes import wintypes

    if os.name != "nt":
        pytest.skip("Windows CNG only")
    bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
    algorithm = ctypes.c_void_p()
    key = ctypes.c_void_p()
    open_algorithm = bcrypt.BCryptOpenAlgorithmProvider
    open_algorithm.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        wintypes.ULONG,
    ]
    open_algorithm.restype = ctypes.c_long
    generate = bcrypt.BCryptGenerateKeyPair
    generate.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.ULONG,
        wintypes.ULONG,
    ]
    generate.restype = ctypes.c_long
    finalize = bcrypt.BCryptFinalizeKeyPair
    finalize.argtypes = [ctypes.c_void_p, wintypes.ULONG]
    finalize.restype = ctypes.c_long
    export = bcrypt.BCryptExportKey
    export.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
        wintypes.ULONG,
    ]
    export.restype = ctypes.c_long
    sign = bcrypt.BCryptSignHash
    sign.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
        wintypes.ULONG,
    ]
    sign.restype = ctypes.c_long
    try:
        assert open_algorithm(ctypes.byref(algorithm), "ECDSA_P256", None, 0) == 0
        assert generate(algorithm, ctypes.byref(key), 256, 0) == 0
        assert finalize(key, 0) == 0
        size = wintypes.ULONG()
        assert export(key, None, "ECCPUBLICBLOB", None, 0, ctypes.byref(size), 0) == 0
        assert size.value == 72
        blob = (ctypes.c_ubyte * size.value)()
        assert (
            export(key, None, "ECCPUBLICBLOB", blob, size.value, ctypes.byref(size), 0)
            == 0
        )
        public = b"\x04" + bytes(blob)[8:]
        data = b"A124-3 ephemeral detached signature vector"
        digest = (ctypes.c_ubyte * 32).from_buffer_copy(hashlib.sha256(data).digest())
        signature_size = wintypes.ULONG()
        assert (
            sign(key, None, digest, 32, None, 0, ctypes.byref(signature_size), 0) == 0
        )
        assert signature_size.value == 64
        signature = (ctypes.c_ubyte * 64)()
        assert (
            sign(key, None, digest, 32, signature, 64, ctypes.byref(signature_size), 0)
            == 0
        )
        raw = bytes(signature)
        guard._verify_d10_signature(data, raw, public)
        with pytest.raises(guard.GuardBlocked):
            guard._verify_d10_signature(data + b"!", raw, public)
        with pytest.raises(guard.GuardBlocked):
            guard._verify_d10_signature(data, raw[:-1], public)
        with pytest.raises(guard.GuardBlocked):
            guard._verify_d10_signature(
                data, raw[:1] + bytes([raw[1] ^ 1]) + raw[2:], public
            )
        with pytest.raises(guard.GuardBlocked):
            guard._verify_d10_signature(data, raw, b"\x04" + b"\x00" * 64)
    finally:
        if key.value:
            assert bcrypt.BCryptDestroyKey(key) == 0
        if algorithm.value:
            assert bcrypt.BCryptCloseAlgorithmProvider(algorithm, 0) == 0


def test_a1243_runtime_mismatch_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    native = FullNative()
    value = guard._parse_attestation(native.data[guard.D10_ATTESTATION])
    fake = SimpleNamespace(
        executable=guard.D10_PRODUCTION_PYTHON,
        version_info=(3, 12, 0),
        flags=SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1),
        pycache_prefix=guard.D10_CACHE_PREFIX,
        argv=[guard.D10_LAUNCH_GUARD],
    )
    monkeypatch.setattr(guard, "sys", fake)
    with pytest.raises(guard.GuardBlocked):
        guard._require_runtime(value)
    fake.version_info = tuple(map(int, value["production_python_version"].split(".")))
    guard._require_runtime(value)
    fake.flags = SimpleNamespace(isolated=1, no_site=0, dont_write_bytecode=1)
    with pytest.raises(guard.GuardBlocked):
        guard._require_runtime(value)


def test_a1243_standard_account_proof_is_mandatory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        guard, "_current_token_facts", lambda: (guard.TRADING_SID, False, False)
    )
    monkeypatch.setattr(guard, "_resolved_local_trading_sid", lambda: guard.TRADING_SID)
    monkeypatch.setattr(
        guard, "_require_standard_account", lambda sid: calls.append(sid)
    )
    guard.require_trading_principal()
    assert calls == [guard.TRADING_SID]


def test_a1243_unimplemented_lease_prevents_real_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(guard, "_verify_pre_source", lambda: None)
    monkeypatch.setattr(
        guard.subprocess, "run", lambda *args, **kwargs: calls.append(args)
    )
    assert guard.main() == 1
    assert not calls


def test_a1243_second_stage_bootstrap_adds_only_fixed_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import run_personal_desktop_unattended_one_week_soak as launcher

    runtime = SimpleNamespace(
        executable=guard.D10_PRODUCTION_PYTHON,
        argv=[guard.D10_SECOND_STAGE_LAUNCHER],
        flags=SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1),
        pycache_prefix=guard.D10_CACHE_PREFIX,
        path=["stdlib"],
    )
    monkeypatch.setattr(launcher, "sys", runtime)
    assert launcher.main() == 1
    assert runtime.path == [
        guard.D10_SOURCE_PACKAGE_ROOT,
        "stdlib",
        guard.D10_PRODUCTION_SITE_PACKAGES,
    ]
    runtime.path = ["stdlib"]
    runtime.flags = SimpleNamespace(isolated=1, no_site=0, dont_write_bytecode=1)
    assert launcher.main() == 1
    assert runtime.path == ["stdlib"]


@pytest.mark.parametrize(
    ("privilege", "group_sid", "blocked"),
    [
        (1, "S-1-5-32-545", False),
        (2, "S-1-5-32-545", True),
        (1, "S-1-5-32-544", True),
        (1, "S-1-5-21-1-2-3-512", True),
    ],
)
def test_a1243_standalone_win32_account_and_group_proof(
    monkeypatch: pytest.MonkeyPatch,
    privilege: int,
    group_sid: str,
    blocked: bool,
) -> None:
    import ctypes
    from ctypes import wintypes

    class UserInfo1(ctypes.Structure):
        _fields_ = [
            ("name", ctypes.c_wchar_p),
            ("password", ctypes.c_wchar_p),
            ("password_age", wintypes.DWORD),
            ("privilege", wintypes.DWORD),
            ("home_dir", ctypes.c_wchar_p),
            ("comment", ctypes.c_wchar_p),
            ("flags", wintypes.DWORD),
            ("script_path", ctypes.c_wchar_p),
        ]

    class LocalGroupInfo0(ctypes.Structure):
        _fields_ = [("name", ctypes.c_wchar_p)]

    user = UserInfo1(privilege=privilege)
    groups = (LocalGroupInfo0 * 1)(LocalGroupInfo0("A group"))

    class Function:
        def __init__(self, value):
            self.value = value
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.value(*args)

    def info(_server, _name, _level, pointer):
        ctypes.cast(
            pointer, ctypes.POINTER(ctypes.c_void_p)
        ).contents.value = ctypes.addressof(user)
        return 0

    def local_groups(_server, _name, _level, _flags, pointer, _length, read, total):
        ctypes.cast(
            pointer, ctypes.POINTER(ctypes.c_void_p)
        ).contents.value = ctypes.addressof(groups)
        ctypes.cast(read, ctypes.POINTER(wintypes.DWORD)).contents.value = 1
        ctypes.cast(total, ctypes.POINTER(wintypes.DWORD)).contents.value = 1
        return 0

    netapi = SimpleNamespace(
        NetUserGetInfo=Function(info),
        NetUserGetLocalGroups=Function(local_groups),
        NetApiBufferFree=Function(lambda _buffer: 0),
    )
    monkeypatch.setattr(
        guard, "_win_dll", lambda name: netapi if name == "netapi32" else None
    )
    monkeypatch.setattr(guard, "_lookup_account_sid", lambda _name: group_sid)
    if blocked:
        with pytest.raises(guard.GuardBlocked):
            guard._require_standard_account(guard.TRADING_SID)
    else:
        guard._require_standard_account(guard.TRADING_SID)
