"""Focused portable A124-2 fixed D10 guard-substrate tests."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_personal_desktop_d10_launch_guard as guard
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as scheduler,
)
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10_ACTIVATION_LEASE_INSTALLING_PATH,
    D10_ACTIVATION_LEASE_PATH,
    D10_ACTIVATION_LEASE_TEMP_PATH,
    D10_SCHEDULER_CONTRACT_ID,
    D10_SOAK_ID_NAMESPACE,
    build_activation_lease_model,
)
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    canonical_json_bytes as lease_canonical_json_bytes,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    EXECUTABLE_MANIFEST_SCHEMA,
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
)


def test_v3_public_point_is_exact_and_bootstrap_trust_is_unchanged() -> None:
    from scripts import d10_protected_deployment_windows as deployment_windows
    from scripts import d10_python_substrate_windows as substrate_windows
    from trading_bot.runtime import personal_desktop_d10_deployment_identity as identity
    from trading_bot.runtime.windows_authority import PRODUCTION_PINNED_BOOTSTRAP_KEYS

    approved = bytes.fromhex(
        "04f2e83034f58cc1e27b1ff6511df503c31d4103782b2992ee64ebb7a9e734a3"
        "548c5daaa5e5c69e83c2f2c2c825c26b61efd356680eed3d60822585c04493ba61"
    )
    legacy = bytes.fromhex(
        "04a73d90064e8b97e4a8373f48cac44718eb375ca52581233d614365294164efba"
        "40c6758f0f4cc455f6b2bf9b222696f9bc83c91ddf625fd01de46a6e7cd9c52e"
    )
    assert (
        guard.D10_SIGNING_KEY_ID
        == identity.D10_SIGNING_KEY_ID
        == ("AITradingBot/D10/DeploymentAttestation/v3")
    )
    assert (
        guard.D10_ATTESTATION_SCHEMA == "personal-desktop-d10-deployment-attestation/v2"
    )
    for point in (
        guard.D10_PUBLIC_KEY,
        deployment_windows.PUBLIC_KEY,
        substrate_windows._PUBLIC_KEY,
    ):
        assert point == approved
        assert len(point) == 65
        assert point[0] == 0x04
        assert point != legacy
        assert hashlib.sha256(point).hexdigest() == (
            "fb22627f6d01d63ecfcc02dbe6e34a5529bdde30ceb0fcb8037eead6f0c56b1e"
        )
    assert deployment_windows.PUBLIC_KEY == guard.D10_PUBLIC_KEY
    assert substrate_windows._PUBLIC_KEY == guard.D10_PUBLIC_KEY
    bootstrap = PRODUCTION_PINNED_BOOTSTRAP_KEYS.keys
    assert len(bootstrap) == 1
    assert bootstrap[0].key_id == "AITradingBot/Authority/Bootstrap/v1"
    assert bootstrap[0].public_key == legacy


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
    assert guard.D10_ACTIVATION_LEASE == D10_ACTIVATION_LEASE_PATH
    assert guard.D10_ACTIVATION_LEASE_INSTALLING == D10_ACTIVATION_LEASE_INSTALLING_PATH
    assert guard.D10_ACTIVATION_LEASE_TEMP == D10_ACTIVATION_LEASE_TEMP_PATH
    assert guard._INSTALLING == (
        guard.D10_LAUNCH_GUARD + ".installing",
        guard.D10_ATTESTATION + ".installing",
        guard.D10_SIGNATURE + ".installing",
        guard.D10_MANIFEST + ".installing",
        guard.D10_SOURCE_ROOT + ".installing",
        D10_ACTIVATION_LEASE_INSTALLING_PATH,
    )
    assert guard._ABSENT[-2:] == (
        D10_ACTIVATION_LEASE_TEMP_PATH,
        guard.D10_CACHE_PREFIX,
    )
    assert guard.D10_SCHEDULER_CONTRACT_ID == D10_SCHEDULER_CONTRACT_ID

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
        "datetime",
        "hashlib",
        "json",
        "subprocess",
        "sys",
        "uuid",
    }
    assert not imports & {"site", "trading_bot", "scripts"}
    forbidden_calls = {
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


def _sample_deployment() -> guard.VerifiedDeploymentFacts:
    return guard.VerifiedDeploymentFacts(
        deployment_id="12345678-1234-5678-1234-567812345678",
        attestation_sha256="a" * 64,
        certified_source_head="b" * 40,
        certified_source_tree="c" * 40,
        executable_file_count=2,
        schema=guard.D10_ATTESTATION_SCHEMA,
        signing_key_id=guard.D10_SIGNING_KEY_ID,
        source_root=guard.D10_SOURCE_ROOT,
        launch_guard=guard.D10_LAUNCH_GUARD,
        launcher=guard.D10_SECOND_STAGE_LAUNCHER,
        scheduler_contract_schema=guard.D10_SCHEDULER_SCHEMA,
        approved_trading_sid=guard.TRADING_SID,
        production_python=guard.D10_PRODUCTION_PYTHON,
        production_python_version=guard.D10_PRODUCTION_PYTHON_VERSION,
    )


def _sample_lease_bytes(
    deployment: guard.VerifiedDeploymentFacts,
    *,
    activation: datetime = datetime(2026, 9, 24, 18, 15, 30, 123456, tzinfo=UTC),
    **changes: object,
) -> bytes:
    model = build_activation_lease_model(
        deployment_id=deployment.deployment_id,
        attestation_sha256=deployment.attestation_sha256,
        accepted_activation_utc=activation,
        certified_source_head=deployment.certified_source_head,
        certified_source_tree=deployment.certified_source_tree,
    )
    value = model.to_dict()
    value.update(changes)
    material = {key: item for key, item in value.items() if key != "soak_id"}
    value["soak_id"] = str(
        uuid.uuid5(
            D10_SOAK_ID_NAMESPACE,
            lease_canonical_json_bytes(material).decode("utf-8"),
        )
    )
    return lease_canonical_json_bytes(value)


def test_a1246_guard_requires_deployment_and_active_lease_before_one_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _sample_deployment()
    activation = datetime(2026, 9, 24, 18, 15, 30, 123456, tzinfo=UTC)
    data = [_sample_lease_bytes(deployment, activation=activation)]
    observed = [activation]
    calls: list[tuple[object, object, object]] = []
    monkeypatch.setattr(guard, "_verify_pre_source", lambda: deployment)
    monkeypatch.setattr(guard, "_read_fixed_activation_lease_bytes", lambda: data[0])
    monkeypatch.setattr(guard, "_trusted_runtime_utc_now", lambda: observed[0])
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    monkeypatch.setattr(
        guard,
        "_sanitized_environment",
        lambda: {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
    )

    def guarded_wake(deployment_arg, lease_arg, environment_arg):
        calls.append((deployment_arg, lease_arg, environment_arg))
        return 0

    monkeypatch.setattr(guard, "_run_second_stage_with_evidence", guarded_wake)
    assert guard.main() == 0
    assert len(calls) == 1
    assert calls[0][0] is deployment
    assert calls[0][1].state == "ACTIVE"
    assert calls[0][1].soak_id
    assert calls[0][2] == {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"}

    failures = [
        (b"{", activation, "malformed"),
        (
            _sample_lease_bytes(
                deployment, activation=activation - timedelta(seconds=1)
            ),
            activation - timedelta(seconds=2),
            "before_start",
        ),
        (
            _sample_lease_bytes(deployment, activation=activation),
            activation + timedelta(days=7),
            "exact_end",
        ),
        (
            _sample_lease_bytes(deployment, activation=activation),
            activation + timedelta(days=7, microseconds=1),
            "expired",
        ),
        (
            _sample_lease_bytes(
                deployment,
                activation=activation,
                deployment_id="22345678-1234-5678-1234-567812345678",
            ),
            activation,
            "deployment",
        ),
        (
            _sample_lease_bytes(
                deployment, activation=activation, attestation_sha256="d" * 64
            ),
            activation,
            "attestation",
        ),
        (
            _sample_lease_bytes(
                deployment, activation=activation, certified_source_head="e" * 40
            ),
            activation,
            "source_head",
        ),
        (
            _sample_lease_bytes(
                deployment, activation=activation, certified_source_tree="f" * 40
            ),
            activation,
            "source_tree",
        ),
        (
            _sample_lease_bytes(
                deployment, activation=activation, scheduler_contract_schema="other/v1"
            ),
            activation,
            "scheduler_schema",
        ),
        (
            _sample_lease_bytes(
                deployment, activation=activation, scheduler_contract_id="0" * 64
            ),
            activation,
            "scheduler_id",
        ),
        (
            _sample_lease_bytes(
                deployment, activation=activation, trading_sid="S-1-5-18"
            ),
            activation,
            "sid",
        ),
        (
            _sample_lease_bytes(
                deployment,
                activation=activation,
                production_python=r"F:\wrong\python.exe",
            ),
            activation,
            "python",
        ),
        (
            _sample_lease_bytes(
                deployment, activation=activation, production_python_version="3.14.4"
            ),
            activation,
            "python_version",
        ),
    ]
    for invalid, instant, _reason in failures:
        data[0] = invalid
        observed[0] = instant
        calls.clear()
        assert guard.main() == 1
        assert not calls

    calls.clear()
    monkeypatch.setattr(
        guard,
        "_verify_pre_source",
        lambda: (_ for _ in ()).throw(guard.GuardBlocked("deployment mismatch")),
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


def test_token_scalar_dword_uses_exact_buffer_without_size_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ctypes
    from ctypes import wintypes

    calls: list[tuple[int, int, int, bool]] = []

    class Function:
        argtypes = None
        restype = None

        def __call__(
            self,
            token: int,
            information_class: int,
            buffer: object,
            length: int,
            returned: object,
        ) -> int:
            calls.append(
                (int(token), int(information_class), int(length), buffer is None)
            )
            assert buffer is not None
            assert length == ctypes.sizeof(wintypes.DWORD)
            ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value = 0
            ctypes.cast(
                returned, ctypes.POINTER(wintypes.DWORD)
            ).contents.value = ctypes.sizeof(wintypes.DWORD)
            return 1

    fake = SimpleNamespace(GetTokenInformation=Function())
    monkeypatch.setattr(guard, "_win_dll", lambda name: fake)

    assert guard._token_scalar_dword(7, 20) == 0
    assert calls == [(7, 20, ctypes.sizeof(wintypes.DWORD), False)]


def test_token_scalar_dword_rejects_wrong_returned_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ctypes
    from ctypes import wintypes

    class Function:
        argtypes = None
        restype = None

        def __call__(
            self,
            _token: int,
            _information_class: int,
            buffer: object,
            _length: int,
            returned: object,
        ) -> int:
            ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value = 1
            ctypes.cast(returned, ctypes.POINTER(wintypes.DWORD)).contents.value = 0
            return 1

    fake = SimpleNamespace(GetTokenInformation=Function())
    monkeypatch.setattr(guard, "_win_dll", lambda name: fake)

    with pytest.raises(guard.GuardBlocked, match="scalar length"):
        guard._token_scalar_dword(7, 20)


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


def test_a1246_absent_lease_prevents_real_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _sample_deployment()
    calls: list[object] = []
    monkeypatch.setattr(guard, "_verify_pre_source", lambda: deployment)
    monkeypatch.setattr(
        guard,
        "_read_fixed_activation_lease_bytes",
        lambda: (_ for _ in ()).throw(guard.GuardBlocked("lease absent")),
    )
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


def _mock_a1245_verification(
    monkeypatch: pytest.MonkeyPatch, native: FullNative
) -> object:
    from trading_bot.runtime import personal_desktop_d10_deployment_verifier as verifier

    c1 = object()
    monkeypatch.setattr(verifier, "_require_second_stage_runtime", lambda: None)
    monkeypatch.setattr(verifier, "_fixed_guard", lambda: guard)
    monkeypatch.setattr(verifier, "acquire_validated_production_authority", lambda: c1)
    monkeypatch.setattr(
        verifier, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    monkeypatch.setattr(guard, "_Native", lambda: native)
    monkeypatch.setattr(guard, "_verify_d10_signature", lambda *args: None)
    return verifier


def test_a1245_independent_reread_and_same_process_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    native = FullNative()
    verifier = _mock_a1245_verification(monkeypatch, native)
    proof = verifier.verify_d10_deployment()
    assert (
        proof.attestation_sha256
        == hashlib.sha256(native.data[guard.D10_ATTESTATION]).hexdigest()
    )
    assert proof.executable_file_count == 2
    assert verifier.require_verified_d10_deployment(proof) is proof
    assert len(native.hash_handles) == 2
    for path in guard._TRUST_FILES:
        assert sum(native.paths[handle] == path for handle in native.read_handles) == 2
    with pytest.raises(verifier.DeploymentVerificationBlocked):
        verifier.require_verified_d10_deployment(replace(proof))
    object.__setattr__(proof, "deployment_id", "forged")
    with pytest.raises(verifier.DeploymentVerificationBlocked):
        verifier.require_verified_d10_deployment(proof)


@pytest.mark.parametrize(
    "drift", ["signature", "manifest", "source", "inventory", "version", "c1"]
)
def test_a1245_reverification_fails_closed(
    monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    native = FullNative()
    verifier = _mock_a1245_verification(monkeypatch, native)
    if drift == "signature":

        def reject(*args: object) -> None:
            raise guard.GuardBlocked("signature rejected")

        monkeypatch.setattr(guard, "_verify_d10_signature", reject)
    elif drift == "manifest":
        native.data[guard.D10_MANIFEST] = b"{}"
    elif drift == "source":
        native.data[guard._source_path("src/trading_bot/mod.py")] = b"changed"
    elif drift == "inventory":
        native.extra[guard.D10_SOURCE_ROOT] = {"extra.py"}
    elif drift == "version":
        native.make_signed_material(production_python_version="3.14.4")
    else:
        first = object()
        second = object()
        observations = iter((first, second))
        monkeypatch.setattr(
            verifier,
            "acquire_validated_production_authority",
            lambda: next(observations),
        )
    monkeypatch.setenv("D10_GUARD_PASSED", "1")
    with pytest.raises(verifier.DeploymentVerificationBlocked):
        verifier.verify_d10_deployment()


def test_a1246_second_stage_requires_deployment_and_active_lease_before_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import run_personal_desktop_unattended_one_week_soak as launcher
    from trading_bot.runtime import personal_desktop_d10_deployment_verifier as verifier

    runtime = SimpleNamespace(
        executable=guard.D10_PRODUCTION_PYTHON,
        argv=[guard.D10_SECOND_STAGE_LAUNCHER],
        flags=SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1),
        pycache_prefix=guard.D10_CACHE_PREFIX,
        path=["stdlib"],
    )
    monkeypatch.setattr(launcher, "sys", runtime)
    deployment = object()
    lease = object()
    called: list[tuple[str, object | None, object | None]] = []
    monkeypatch.setattr(
        verifier,
        "verify_d10_deployment",
        lambda: called.append(("verify deployment", None, None)) or deployment,
    )
    monkeypatch.setattr(
        verifier,
        "require_verified_d10_deployment",
        lambda value: called.append(("deployment provenance", value, None)) or value,
    )
    monkeypatch.setattr(
        verifier,
        "verify_d10_activation_lease",
        lambda value: called.append(("verify lease", value, None)) or lease,
    )
    monkeypatch.setattr(
        verifier,
        "require_verified_d10_activation_lease",
        lambda value, bound: called.append(("lease provenance", value, bound)) or value,
    )
    from trading_bot.runtime import personal_desktop_unattended_one_week_soak as soak

    controller_calls: list[tuple[object, object]] = []
    evidence = SimpleNamespace(outcome=soak.D10WakeOutcome.NO_ACTION)
    monkeypatch.setattr(
        soak,
        "run_personal_desktop_unattended_one_week_soak",
        lambda source, active: controller_calls.append((source, active)) or evidence,
    )
    monkeypatch.setattr(soak, "serialize_d10_wake_evidence", lambda _value: "{}")
    assert launcher.main() == 0
    assert called == [
        ("verify deployment", None, None),
        ("deployment provenance", deployment, None),
        ("verify lease", deployment, None),
        ("lease provenance", lease, deployment),
    ]
    assert controller_calls == [(deployment, lease)]

    called.clear()

    def reject_lease(value: object) -> object:
        called.append(("verify lease", value, None))
        raise verifier.ActivationLeaseVerificationBlocked("expired")

    monkeypatch.setattr(verifier, "verify_d10_activation_lease", reject_lease)
    runtime.path = ["stdlib"]
    assert launcher.main() == 1
    assert [item[0] for item in called] == [
        "verify deployment",
        "deployment provenance",
        "verify lease",
    ]

    called.clear()

    def reject_deployment() -> object:
        called.append(("verify deployment", None, None))
        raise verifier.DeploymentVerificationBlocked("deployment mismatch")

    monkeypatch.setattr(verifier, "verify_d10_deployment", reject_deployment)
    runtime.path = ["stdlib"]
    assert launcher.main() == 1
    assert [item[0] for item in called] == ["verify deployment"]


def test_a1245_zero_argument_fixed_second_stage_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import inspect
    from pathlib import PureWindowsPath

    from trading_bot.runtime import personal_desktop_d10_deployment_verifier as verifier

    assert not inspect.signature(verifier.verify_d10_deployment).parameters
    expected_file = str(
        PureWindowsPath(verifier.D10_SOURCE_ROOT)
        / "src"
        / "trading_bot"
        / "runtime"
        / "personal_desktop_d10_deployment_verifier.py"
    )
    runtime = SimpleNamespace(
        executable=guard.D10_PRODUCTION_PYTHON,
        argv=[guard.D10_SECOND_STAGE_LAUNCHER],
        flags=SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1),
        pycache_prefix=guard.D10_CACHE_PREFIX,
    )
    monkeypatch.setattr(verifier, "__file__", expected_file)
    monkeypatch.setattr(verifier, "sys", runtime)
    verifier._require_second_stage_runtime()
    runtime.argv = ["caller-selected"]
    with pytest.raises(verifier.DeploymentVerificationBlocked):
        verifier._require_second_stage_runtime()
    runtime.argv = [guard.D10_SECOND_STAGE_LAUNCHER]
    runtime.flags.no_site = 0
    with pytest.raises(verifier.DeploymentVerificationBlocked):
        verifier._require_second_stage_runtime()
    runtime.flags.no_site = 1
    monkeypatch.setattr(verifier, "__file__", r"F:\AI\mutable\verifier.py")
    with pytest.raises(verifier.DeploymentVerificationBlocked):
        verifier._require_second_stage_runtime()


def test_a1246_fixed_lease_read_pins_read_only_object_and_reserved_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative()
    native.data[guard.D10_ACTIVATION_LEASE] = b"canonical lease"
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    assert guard._read_fixed_activation_lease_bytes(native) == b"canonical lease"
    assert set(native.paths.values()) == {guard.D10_ROOT, guard.D10_ACTIVATION_LEASE}
    assert native.read_handles == [
        next(
            handle
            for handle, path in native.paths.items()
            if path == guard.D10_ACTIVATION_LEASE
        )
    ]
    assert native.probed == [
        guard.D10_ACTIVATION_LEASE_INSTALLING,
        guard.D10_ACTIVATION_LEASE_TEMP,
        guard.D10_ACTIVATION_LEASE_INSTALLING,
        guard.D10_ACTIVATION_LEASE_TEMP,
    ]
    assert set(native.closed) == set(native.paths)
    assert native.inspections[guard.D10_ROOT] == 2
    assert native.inspections[guard.D10_ACTIVATION_LEASE] == 2


@pytest.mark.parametrize(
    "path",
    [guard.D10_ACTIVATION_LEASE_INSTALLING, guard.D10_ACTIVATION_LEASE_TEMP],
)
def test_a1246_reserved_lease_state_blocks(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    native = FakeNative()
    native.data[guard.D10_ACTIVATION_LEASE] = b"lease"
    native.present.add(path)
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_activation_lease_bytes(native)


@pytest.mark.parametrize(
    "change",
    [
        {"final_path": r"F:\AITradingBot\D10\other.json"},
        {"attributes": guard.FILE_ATTRIBUTE_REPARSE_POINT},
        {"attributes": guard.FILE_ATTRIBUTE_DIRECTORY},
        {"drive_type": 4},
        {"volume_root": "E:\\"},
        {"filesystem": "ReFS"},
        {"links": 2},
        {"owner": guard.SYSTEM_SID},
        {"protected": False},
        {
            "aces": (
                *guard.FILE_POLICY.aces[:2],
                guard.Ace(guard.TRADING_SID, guard.TRADING_FILE_READ | 2),
            )
        },
    ],
)
def test_a1246_lease_final_path_kind_and_acl_drift_block(
    monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    native = FakeNative()
    native.data[guard.D10_ACTIVATION_LEASE] = b"lease"
    native.overrides[guard.D10_ACTIVATION_LEASE] = change
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_activation_lease_bytes(native)
    assert set(native.closed) == set(native.paths)


@pytest.mark.parametrize(
    "field",
    ["file_index", "volume_serial", "size", "owner", "aces"],
)
def test_a1246_lease_final_reinspection_drift_blocks(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    native = FakeNative()
    native.data[guard.D10_ACTIVATION_LEASE] = b"lease"
    values = {
        "file_index": 99,
        "volume_serial": 99,
        "size": 99,
        "owner": guard.SYSTEM_SID,
        "aces": tuple(reversed(guard.FILE_POLICY.aces)),
    }
    native.after[guard.D10_ACTIVATION_LEASE] = {field: values[field]}
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    with pytest.raises(guard.GuardBlocked):
        guard._read_fixed_activation_lease_bytes(native)


def test_a1246_lease_native_open_is_no_follow_and_read_only(
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
    assert guard._Native().open(guard.D10_ACTIVATION_LEASE, directory=False) == 7
    args = calls[0]
    assert args[0] == guard.D10_ACTIVATION_LEASE
    assert args[1] == (
        guard.FILE_READ_DATA
        | guard.FILE_READ_ATTRIBUTES
        | guard.READ_CONTROL
        | guard.SYNCHRONIZE
    )
    assert args[2] == 1
    assert args[4] == 3
    assert args[5] & guard.FILE_FLAG_OPEN_REPARSE_POINT


def test_a1246_parser_matches_model_and_rejects_bad_bytes() -> None:
    deployment = _sample_deployment()
    encoded = _sample_lease_bytes(deployment)
    model = build_activation_lease_model(
        deployment_id=deployment.deployment_id,
        attestation_sha256=deployment.attestation_sha256,
        accepted_activation_utc=datetime(2026, 9, 24, 18, 15, 30, 123456, tzinfo=UTC),
        certified_source_head=deployment.certified_source_head,
        certified_source_tree=deployment.certified_source_tree,
    )
    assert encoded == model.canonical_bytes()
    assert guard._parse_active_lease_facts(encoded, deployment)[0] == model.to_dict()
    with pytest.raises(guard.GuardBlocked):
        guard._parse_active_lease_facts(
            encoded.replace(b'"schema":', b'"schema":"x","schema":', 1), deployment
        )
    extra = model.to_dict()
    extra["extra"] = True
    with pytest.raises(guard.GuardBlocked):
        guard._parse_active_lease_facts(lease_canonical_json_bytes(extra), deployment)


def test_a1246_launch_gate_has_no_caller_clock_or_path_inputs() -> None:
    import inspect

    assert not inspect.signature(guard.main).parameters
    assert guard._read_fixed_activation_lease_bytes.__defaults__ == (None,)
    assert (
        len(
            inspect.signature(
                guard.verify_fixed_activation_lease_for_second_stage
            ).parameters
        )
        == 0
    )


def _verified_facts_from_model(
    lease, state: str = "ACTIVE"
) -> guard.VerifiedActivationLeaseFacts:
    return guard.VerifiedActivationLeaseFacts(
        state=state,
        deployment_id=lease.deployment_id,
        attestation_sha256=lease.attestation_sha256,
        soak_id=lease.soak_id,
        accepted_activation_utc=(
            f"{lease.accepted_activation_utc.year:04d}-"
            f"{lease.accepted_activation_utc.month:02d}-"
            f"{lease.accepted_activation_utc.day:02d}T"
            f"{lease.accepted_activation_utc.hour:02d}:"
            f"{lease.accepted_activation_utc.minute:02d}:"
            f"{lease.accepted_activation_utc.second:02d}."
            f"{lease.accepted_activation_utc.microsecond:06d}Z"
        ),
        end_utc=(
            f"{lease.end_utc.year:04d}-{lease.end_utc.month:02d}-"
            f"{lease.end_utc.day:02d}T{lease.end_utc.hour:02d}:"
            f"{lease.end_utc.minute:02d}:{lease.end_utc.second:02d}."
            f"{lease.end_utc.microsecond:06d}Z"
        ),
        certified_source_head=lease.certified_source_head,
        certified_source_tree=lease.certified_source_tree,
        scheduler_contract_schema=lease.scheduler_contract_schema,
        scheduler_contract_id=lease.scheduler_contract_id,
        trading_sid=lease.trading_sid,
        production_python=lease.production_python,
        production_python_version=lease.production_python_version,
    )


def test_a1246_a4_independent_lease_reread_and_noncopyable_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    native = FullNative()
    verifier = _mock_a1245_verification(monkeypatch, native)
    deployment = verifier.verify_d10_deployment()
    activation = datetime(2026, 9, 24, 18, 15, 30, 123456, tzinfo=UTC)
    model = verifier.build_d10_activation_lease(deployment, activation)
    publication_bytes = verifier.build_d10_activation_lease_bytes(
        deployment, activation
    )
    assert publication_bytes == model.canonical_bytes()
    facts = _verified_facts_from_model(model)
    rereads: list[int] = []
    monkeypatch.setattr(
        guard,
        "verify_fixed_activation_lease_for_second_stage",
        lambda: rereads.append(1) or facts,
    )
    monkeypatch.setattr(verifier, "_trusted_runtime_utc_now", lambda: activation)
    assert verifier.verify_d10_activation_lease(deployment) is not None
    assert rereads == [1]
    evidence = verifier.verify_d10_activation_lease(deployment)
    assert (
        verifier.require_verified_d10_activation_lease(evidence, deployment) is evidence
    )
    assert rereads == [1, 1]
    with pytest.raises(verifier.ActivationLeaseVerificationBlocked):
        verifier.require_verified_d10_activation_lease(replace(evidence), deployment)
    with pytest.raises(verifier.ActivationLeaseVerificationBlocked):
        verifier.verify_d10_activation_lease(replace(deployment))
    with pytest.raises(verifier.DeploymentVerificationBlocked):
        verifier.require_verified_d10_activation_lease(evidence, replace(deployment))
    monkeypatch.setattr(
        verifier,
        "_trusted_runtime_utc_now",
        lambda: model.end_utc,
    )
    with pytest.raises(verifier.ActivationLeaseVerificationBlocked):
        verifier.require_verified_d10_activation_lease(evidence, deployment)


@pytest.mark.parametrize(
    "field",
    [
        "deployment_id",
        "attestation_sha256",
        "certified_source_head",
        "certified_source_tree",
        "scheduler_contract_schema",
        "scheduler_contract_id",
        "trading_sid",
        "production_python",
        "production_python_version",
    ],
)
def test_a1246_a4_rejects_lease_identity_or_runtime_mismatch(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    from dataclasses import replace

    native = FullNative()
    verifier = _mock_a1245_verification(monkeypatch, native)
    deployment = verifier.verify_d10_deployment()
    model = verifier.build_d10_activation_lease(
        deployment, datetime(2026, 9, 24, 18, 15, 30, 123456, tzinfo=UTC)
    )
    changed = {
        "deployment_id": "22345678-1234-5678-1234-567812345678",
        "attestation_sha256": "d" * 64,
        "certified_source_head": "e" * 40,
        "certified_source_tree": "f" * 40,
        "scheduler_contract_schema": "other/v1",
        "scheduler_contract_id": "0" * 64,
        "trading_sid": "S-1-5-18",
        "production_python": r"F:\wrong\python.exe",
        "production_python_version": "3.14.4",
    }[field]
    facts = replace(_verified_facts_from_model(model), **{field: changed})
    monkeypatch.setattr(
        guard, "verify_fixed_activation_lease_for_second_stage", lambda: facts
    )
    monkeypatch.setattr(
        verifier, "_trusted_runtime_utc_now", lambda: model.accepted_activation_utc
    )
    with pytest.raises(verifier.ActivationLeaseVerificationBlocked):
        verifier.verify_d10_activation_lease(deployment)


def test_a1246_pre_source_lease_time_interval_is_start_inclusive_end_exclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment = _sample_deployment()
    activation = datetime(2026, 9, 24, 18, 15, 30, 123456, tzinfo=UTC)
    end = activation + timedelta(days=7)
    data = [_sample_lease_bytes(deployment, activation=activation)]
    observed = [activation]
    monkeypatch.setattr(guard, "_read_fixed_activation_lease_bytes", lambda: data[0])
    monkeypatch.setattr(guard, "_trusted_runtime_utc_now", lambda: observed[0])
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    guard._require_active_lease(deployment)
    observed[0] = end - timedelta(microseconds=1)
    guard._require_active_lease(deployment)
    observed[0] = activation - timedelta(microseconds=1)
    with pytest.raises(guard.GuardBlocked):
        guard._require_active_lease(deployment)
    observed[0] = end
    with pytest.raises(guard.GuardBlocked):
        guard._require_active_lease(deployment)
    observed[0] = end + timedelta(microseconds=1)
    with pytest.raises(guard.GuardBlocked):
        guard._require_active_lease(deployment)


def test_a1246_second_stage_guard_independently_rereads_fixed_active_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FullNative()
    monkeypatch.setattr(guard, "require_trading_principal", lambda: None)
    monkeypatch.setattr(guard, "_verify_d10_signature", lambda *_args: None)
    monkeypatch.setattr(guard, "_require_runtime", lambda _attestation: None)
    deployment = guard._verify_pre_source(native)
    activation = datetime(2026, 9, 24, 18, 15, 30, 123456, tzinfo=UTC)
    native.data[guard.D10_ACTIVATION_LEASE] = _sample_lease_bytes(
        deployment, activation=activation
    )
    monkeypatch.setattr(guard, "_Native", lambda: native)
    monkeypatch.setattr(
        guard, "_require_runtime_for_second_stage_lease", lambda _attestation: None
    )
    monkeypatch.setattr(guard, "_trusted_runtime_utc_now", lambda: activation)
    proof = guard.verify_fixed_activation_lease_for_second_stage()
    assert proof.state == "ACTIVE"
    assert proof.deployment_id == deployment.deployment_id
    assert proof.attestation_sha256 == deployment.attestation_sha256
    assert (
        proof.soak_id
        == build_activation_lease_model(
            deployment_id=deployment.deployment_id,
            attestation_sha256=deployment.attestation_sha256,
            accepted_activation_utc=activation,
            certified_source_head=deployment.certified_source_head,
            certified_source_tree=deployment.certified_source_tree,
        ).soak_id
    )
    assert (
        sum(
            native.paths[handle] == guard.D10_ACTIVATION_LEASE
            for handle in native.read_handles
        )
        == 2
    )
    assert all(handle in native.closed for handle in native.read_handles)
    assert set(native.closed) == set(native.paths)


@pytest.mark.parametrize(
    "drift",
    ["executable", "version", "flags", "cache", "argv"],
)
def test_a1246_second_stage_python_identity_mismatch_blocks(
    monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    runtime = SimpleNamespace(
        executable=guard.D10_PRODUCTION_PYTHON,
        version_info=(3, 14, 3),
        flags=SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1),
        pycache_prefix=guard.D10_CACHE_PREFIX,
        argv=[guard.D10_SECOND_STAGE_LAUNCHER],
    )
    if drift == "executable":
        runtime.executable = r"F:\wrong\python.exe"
    elif drift == "version":
        runtime.version_info = (3, 14, 4)
    elif drift == "flags":
        runtime.flags.no_site = 0
    elif drift == "cache":
        runtime.pycache_prefix = r"F:\wrong\cache"
    else:
        runtime.argv = ["caller-selected"]
    monkeypatch.setattr(guard, "sys", runtime)
    with pytest.raises(guard.GuardBlocked):
        guard._require_runtime_for_second_stage_lease(
            {"production_python_version": guard.D10_PRODUCTION_PYTHON_VERSION}
        )


def test_a1252_guard_rejects_legacy_v2_signing_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FullNative()
    attestation = json.loads(native.data[guard.D10_ATTESTATION])
    attestation["signing_key_id"] = "AITradingBot/D10/DeploymentAttestation/v2"
    native.data[guard.D10_ATTESTATION] = guard._canonical_json(attestation)
    with pytest.raises(guard.GuardBlocked):
        _admit(monkeypatch, native)
